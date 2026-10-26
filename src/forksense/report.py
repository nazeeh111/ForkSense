"""Portable, offline experiment reports. No assets, server, or dependencies required."""
from __future__ import annotations

from .process import ok
import html
import json
from pathlib import Path
from typing import Any


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _number(value: Any, places: int = 2) -> str:
    try:
        return f"{float(value):,.{places}f}"
    except (ValueError, TypeError, OverflowError):
        return "unreported"


def _status(value: Any) -> str:
    return str(value or "unreported").replace("_", " ")


def _log(label: str, value: Any) -> str:
    if value in (None, "", []):
        return ""
    return f'<details class="log"><summary>{_escape(label)}</summary><pre>{_escape(value)}</pre></details>'


def _command(value: Any) -> str:
    import shlex
    if isinstance(value, (list, tuple)):
        return shlex.join(str(item) for item in value)
    return str(value or "Command not reported")


def _verification(value: Any) -> str:
    if not isinstance(value, dict):
        return '<p class="muted">Verification not reported.</p>'
    code = value.get("returncode")
    passed = ok(value)
    label = "Passed" if passed else "Inconclusive" if value.get("error") or value.get("timed_out") or code is None else "Failed"
    return (
        f'<p class="verify-result"><span class="pill {"ok" if passed else "neutral"}">{label}</span>'
        f' <span>exit {_escape(code if code is not None else "?")} · {_number(value.get("duration"))} s</span></p>'
        + _log("Verifier stdout", value.get("stdout"))
        + _log("Verifier stderr", value.get("stderr"))
    )


def _step(step: dict[str, Any], index: int) -> str:
    kind = str(step.get("kind", "experiment"))
    command = _command(step.get("command"))
    details = (
        f'<div class="command-label">Executed command</div><pre class="command">{_escape(command)}</pre>'
        '<dl class="facts">'
        f'<div><dt>Duration</dt><dd>{_number(step.get("duration"))} s</dd></div>'
        f'<div><dt>Outcome</dt><dd>{_escape(step.get("outcome", "unreported"))}</dd></div>'
        f'<div><dt>Hypothesis</dt><dd>{_escape(step.get("hypothesis", "not assigned"))}</dd></div>'
        f'<div><dt>Policy score</dt><dd>{_number(step.get("score"), 4)}</dd></div>'
        f'<div><dt>Expected information</dt><dd>{_number(step.get("information_gain"), 4)} bits</dd></div>'
        f'<div><dt>Estimated cost</dt><dd>{_number(step.get("cost_seconds"))} s</dd></div>'
        '</dl>'
        + _log("Experiment stdout", step.get("stdout"))
        + _log("Experiment stderr", step.get("stderr"))
    )
    details += _log("Source patch", step.get("diff"))
    if step.get("attempt_patch_path") and not step.get("patch_path"):
        details += f'<p>Unverified attempt retained: <code>{_escape(step["attempt_patch_path"])}</code></p>'
    if "verification" in step:
        details += f'<h4 id="verification-{index - 1}" tabindex="-1">Independent verification</h4>' + _verification(step["verification"])
    if step.get("patch_path"):
        details += f'<p class="patch-location">Patch artifact <code>{_escape(step["patch_path"])}</code></p>'
    return (
        f'<li class="step" data-kind="{_escape(kind)}">'
        f'<span class="step-number" aria-hidden="true">{index:02}</span>'
        f'<details class="step-detail" id="evidence-step-{index - 1}">'
        f'<summary><span class="step-main"><span class="eyebrow">{_escape(kind)}</span>'
        f'<span class="step-title">{_escape(step.get("label") or step.get("id") or "Experiment")}</span></span>'
        f'<span class="step-state">{_escape(_status(step.get("status")))}<span class="chevron" aria-hidden="true">+</span></span></summary>'
        f'<div class="step-body">{details}</div></details></li>'
    )


def _fork_map(steps: list[dict[str, Any]], base_commit: Any) -> str:
    """Show actual execution ancestry, separately from chronological evidence."""
    branches = []
    for index, step in enumerate(steps):
        kind = str(step.get("kind", "experiment"))
        label = step.get("label") or step.get("id") or "Experiment"
        target = f"evidence-step-{index}"
        node = (
            f'<button class="fork-node" type="button" data-fork-target="{target}" aria-controls="{target}">'
            f'<span class="fork-kind">{_escape(kind)} {index + 1:02}</span>'
            f'<strong>{_escape(label)}</strong><span class="fork-state">{_escape(_status(step.get("status")))}</span></button>'
        )
        verifier = step.get("verification")
        child = ""
        if kind == "repair" and isinstance(verifier, dict):
            state = "Passed" if ok(verifier) else "Inconclusive" if verifier.get("error") or verifier.get("timed_out") or verifier.get("returncode") is None else "Failed"
            child = (
                '<ul class="fork-verification"><li>'
                f'<button class="fork-node fork-verifier" type="button" data-fork-target="verification-{index}" aria-controls="verification-{index}">'
                '<span class="fork-kind">Fresh verification</span>'
                '<strong>Base + candidate patch</strong>'
                f'<span class="fork-state">{state}</span></button></li></ul>'
            )
        branches.append(f'<li class="fork-branch">{node}{child}</li>')
    children = '<ul class="fork-branches">' + ''.join(branches) + '</ul>' if branches else '<p class="empty">No experiment worktrees were recorded.</p>'
    return (
        '<section class="fork-map" aria-labelledby="fork-map-title">'
        '<div class="section-heading"><div><p class="eyebrow">Execution topology</p>'
        '<h2 id="fork-map-title">Worktree forks</h2></div><span class="fork-hint">Select a node to inspect evidence</span></div>'
        '<p class="section-copy">Every probe and repair starts from the frozen base. Verification uses a fresh base with the candidate patch.</p>'
        '<div class="fork-tree"><button class="fork-node fork-root" type="button" data-fork-target="baseline-evidence" aria-controls="baseline-evidence">'
        '<span class="fork-kind">Frozen base</span>'
        f'<strong><code>{_escape(str(base_commit or "unreported")[:12])}</code></strong><span class="fork-state">Baseline verifier</span></button>'
        + children + '</div></section>'
    )


def write_report(report: dict[str, Any], path: Path) -> None:
    """Write a readable single-file HTML report, safely escaping all run content.

    The report contains local execution logs. Review them before sharing. Paths
    are displayed as text, never interpreted as arbitrary hyperlinks or commands.
    """
    path = Path(path)
    hypotheses = [h for h in (report.get("hypotheses") or []) if isinstance(h, dict)]
    steps = [s for s in (report.get("steps") or []) if isinstance(s, dict)]
    selected = report.get("selected")
    totals = report.get("totals") or {}
    budgets = report.get("budgets") or {}
    baseline = report.get("baseline") or {}
    warnings = report.get("warnings") or []
    task = report.get("task") or "Untitled experiment"
    status = _status(report.get("status"))
    # Escaping '<' blocks closing-script attacks even in application/json tags.
    serialized = json.dumps(report, ensure_ascii=True, allow_nan=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    initial_bars = "".join(
        f'<li><div class="hypothesis-label"><code>{_escape(h.get("id", "?"))}</code>'
        f'<span>{_escape(h.get("description", ""))}</span></div>'
        '<div class="bar-row"><div class="bar-track"><div class="bar-fill"></div></div>'
        '<output class="bar-value">unreported</output></div></li>' for h in hypotheses
    )
    warning_html = ('<aside class="warning" aria-label="Run warnings"><h2>Read before using this result</h2><ul>'
                    + "".join(f'<li>{_escape(w)}</li>' for w in warnings) + '</ul></aside>') if warnings else ""
    if isinstance(selected, dict):
        files = selected.get("files") or []
        selection_html = (
            '<div class="selected-heading"><span class="signal-dot" aria-hidden="true"></span><h2>Candidate selected</h2></div>'
            f'<p class="selected-id">{_escape(selected.get("id", "Candidate"))}</p>'
            '<p>Verification evidence is shown below. Inspect the diff before accepting it.</p>'
            f'<dl class="artifact"><dt>Patch</dt><dd><code>{_escape(selected.get("patch_path", "unreported"))}</code></dd>'
            f'<dt>SHA-256</dt><dd><code>{_escape(selected.get("sha256", "unreported"))}</code></dd>'
            f'<dt>Changed files</dt><dd>{", ".join(_escape(f) for f in files) or "unreported"}</dd></dl>'
            + _verification(selected.get("verification"))
        )
    else:
        selection_html = ('<h2>No candidate selected</h2><p>There is no verified patch to accept from this run.</p>'
                          '<p class="muted">Failed and inconclusive experiments remain in the evidence below.</p>')
    result_html = ''.join(_step(step, i) for i, step in enumerate(steps, 1))
    if not result_html:
        result_html = '<li class="empty">No experiments were recorded. The run may have stopped at the baseline or a budget limit.</li>'
    options = '<option value="initial">Before experiments</option>' + ''.join(
        f'<option value="{i}">After {i + 1:02} · {_escape(s.get("label") or s.get("id") or "Experiment")}</option>'
        for i, s in enumerate(steps) if isinstance(s.get("posterior"), dict)
    ) + '<option value="final" selected>Final evidence</option>'
    document = TEMPLATE.replace("__STYLE__", STYLE).replace("__SCRIPT__", SCRIPT)
    replacements = {
        "__TASK__": _escape(task), "__STATUS__": _escape(status),
        "__REASON__": _escape(report.get("reason") or "No stopping reason was recorded."),
        "__RUN_ID__": _escape(report.get("run_id", "unreported")),
        "__BASE__": _escape(report.get("base_commit", "unreported")),
        "__POLICY__": _escape(report.get("policy", "unreported")),
        "__DURATION__": _number(totals.get("duration")),
        "__CALLS__": _escape(totals.get("agent_calls", "unreported")),
        "__INPUT__": _number(totals.get("input_tokens"), 0),
        "__OUTPUT__": _number(totals.get("output_tokens"), 0),
        "__BUDGET_SECONDS__": _escape(budgets.get("seconds", "unreported")),
        "__BUDGET_CALLS__": _escape(budgets.get("agent_calls", "unreported")),
        "__BUDGET_EXPERIMENTS__": _escape(budgets.get("max_experiments", "unreported")),
        "__WARNINGS__": warning_html, "__SELECTION__": selection_html,
        "__BASELINE__": _verification(baseline), "__STEPS__": result_html,
        "__FORK_MAP__": _fork_map(steps, report.get("base_commit")),
        "__BARS__": initial_bars or '<li class="muted">No hypotheses were reported.</li>',
        "__OPTIONS__": options, "__DATA__": serialized,
    }
    # One pass prevents report text containing a placeholder from being replaced.
    import re
    document = re.sub("|".join(re.escape(k) for k in replacements), lambda match: replacements[match.group()], document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<meta name="color-scheme" content="light"><title>FORKSENSE · __TASK__</title><style>__STYLE__</style></head>
<body><a class="skip-link" href="#main">Skip to evidence</a><div class="page">
<header class="masthead"><div class="brand"><svg viewBox="0 0 36 36" aria-hidden="true"><path d="M8 29V21C8 16 18 18 18 12V6M18 12C18 18 28 16 28 21V29"/><circle cx="18" cy="6" r="3"/><circle cx="8" cy="29" r="3"/><circle cx="28" cy="29" r="3"/></svg><span>FORKSENSE<span class="brand-sub">EXPERIMENT RECORD</span></span></div><div class="offline">LOCAL FILE <span aria-hidden="true">/</span> NO EXTERNAL ASSETS</div></header>
<main id="main"><section class="intro"><p class="eyebrow">Stop guessing. Test the alternatives.</p><h1>__TASK__</h1><div class="decision"><span class="status">__STATUS__</span><p>__REASON__</p></div></section>
<div class="metrics" aria-label="Run totals"><div><span>Wall time</span><strong>__DURATION__<small> s</small></strong></div><div><span>Agent calls</span><strong>__CALLS__</strong></div><div><span>Input tokens</span><strong>__INPUT__</strong></div><div><span>Output tokens</span><strong>__OUTPUT__</strong></div></div>
__WARNINGS__
__FORK_MAP__
<div class="workspace"><section class="evidence"><div class="section-heading"><div><p class="eyebrow">01 / Execution</p><h2>Follow the evidence</h2></div><button id="expand-all" type="button">Expand all steps</button></div><p class="section-copy">Open an experiment to inspect its command, observed outcome, and verification.</p><details class="baseline" id="baseline-evidence"><summary><span>Baseline verification</span><span class="chevron" aria-hidden="true">+</span></summary><div class="step-body">__BASELINE__</div></details><div class="filters" role="group" aria-label="Filter experiment steps"><button type="button" data-filter="all" aria-pressed="true">All experiments</button><button type="button" data-filter="probe" aria-pressed="false">Probes</button><button type="button" data-filter="repair" aria-pressed="false">Repairs</button></div><p id="filter-empty" class="empty" hidden>No experiments match this filter.</p><ol class="timeline">__STEPS__</ol></section>
<aside class="right-column"><section class="beliefs" aria-labelledby="belief-title"><p class="eyebrow">02 / Interpretation</p><h2 id="belief-title">Which cause fits?</h2><label for="evidence-point">Evidence checkpoint</label><select id="evidence-point">__OPTIONS__</select><ul id="hypotheses">__BARS__</ul><p class="model-note">Posterior weights reflect the supplied prediction model. They are not calibrated probabilities that a patch is correct.</p></section><section class="selection">__SELECTION__</section></aside></div>
<section class="provenance"><div><p class="eyebrow">03 / Reproduction</p><h2>A record you can inspect</h2></div><dl><div><dt>Run</dt><dd><code>__RUN_ID__</code></dd></div><div><dt>Base commit</dt><dd><code>__BASE__</code></dd></div><div><dt>Policy</dt><dd>__POLICY__</dd></div><div><dt>Configured limits</dt><dd>__BUDGET_SECONDS__ s · __BUDGET_CALLS__ agent calls · __BUDGET_EXPERIMENTS__ experiments</dd></div></dl><button type="button" id="download-json">Download run JSON</button></section></main><footer><span>FORKSENSE</span><p>Execution evidence, preserved. Review logs before sharing.</p></footer></div>
<script id="run-data" type="application/json">__DATA__</script><script>__SCRIPT__</script></body></html>'''

STYLE = '''
:root{--paper:#f6f5ef;--ink:#242923;--muted:#5e665c;--line:#cdd1c5;--accent:#b44831;--signal:#31614a;--wash:#eceee5;--mono:ui-monospace,SFMono-Regular,Consolas,monospace;--sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.55}.page{max-width:1440px;margin:auto;padding:0 56px}button,select{font:inherit;color:inherit}button{cursor:pointer;border:1px solid var(--line);border-radius:2px;background:transparent;padding:9px 13px;font-size:12px;font-weight:600}button:hover{background:var(--wash);border-color:var(--muted)}button:focus-visible,select:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid var(--accent);outline-offset:4px}.skip-link{position:fixed;left:20px;top:-80px;padding:12px;background:var(--ink);color:white;z-index:10}.skip-link:focus{top:12px}.masthead{display:flex;justify-content:space-between;align-items:center;min-height:108px;border-bottom:1px solid var(--ink);gap:20px}.brand{display:flex;align-items:center;gap:13px;font-size:19px;font-weight:850;letter-spacing:.065em}.brand svg{width:39px;height:39px;stroke:var(--accent);fill:var(--paper);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}.brand-sub{display:block;letter-spacing:.15em;font:9px/1.9 var(--mono);font-weight:500}.offline{font:10px var(--mono);letter-spacing:.065em;color:var(--muted);text-align:right}.offline span{padding:0 9px;color:var(--accent)}.intro{padding:45px 0 30px}.eyebrow{font:10px/1.6 var(--mono);letter-spacing:.105em;text-transform:uppercase;color:var(--muted);margin:0 0 11px}h1{font-size:clamp(28px,3.8vw,51px);font-weight:600;line-height:1.14;letter-spacing:-.04em;max-width:1050px;margin:0 0 28px;overflow-wrap:anywhere}h2{font-size:21px;line-height:1.25;font-weight:600;letter-spacing:-.025em;margin:0}h4{font-size:12px;margin:22px 0 9px}.decision{display:flex;gap:16px;align-items:baseline}.decision p{margin:0;max-width:900px;font-size:14px}.status{text-transform:uppercase;letter-spacing:.06em;font:600 11px var(--mono);padding:6px 8px;background:var(--ink);color:var(--paper);white-space:nowrap}.metrics{display:grid;grid-template-columns:repeat(4,1fr);border-block:1px solid var(--line);margin-bottom:40px}.metrics>div{padding:19px 25px;border-right:1px solid var(--line)}.metrics>div:first-child{padding-left:0}.metrics>div:last-child{border:0}.metrics span{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}.metrics strong{font:500 28px/1.2 var(--mono);letter-spacing:-.06em}.metrics small{font-size:13px;color:var(--muted);letter-spacing:0}.workspace{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,1fr);gap:55px}.section-heading{display:flex;justify-content:space-between;align-items:flex-end;gap:15px}.section-copy{font-size:13px;max-width:560px;color:var(--muted);margin:14px 0 24px}.baseline{border-block:1px solid var(--line);margin-bottom:20px}.baseline>summary{padding:15px 0;display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:600;cursor:pointer;list-style:none}.baseline .step-body{padding-left:0;padding-right:0}.filters{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:22px}.filters button{border-color:transparent;padding:6px 10px;font-size:11px}.filters button[aria-pressed=true]{background:var(--ink);color:var(--paper)}.timeline{list-style:none;margin:0;padding:0}.step{position:relative;padding-left:43px;min-width:0}.step:before{content:"";position:absolute;top:20px;bottom:-20px;left:12px;width:1px;background:var(--line)}.step:last-child:before{bottom:35px}.step-number{position:absolute;left:0;top:23px;font:10px var(--mono);background:var(--paper);color:var(--muted);padding:4px 1px;z-index:1}.step-detail{border-bottom:1px solid var(--line)}.step-detail>summary{list-style:none;display:flex;justify-content:space-between;gap:20px;align-items:center;min-height:88px;cursor:pointer;padding:16px 0}.step-detail>summary:hover .step-title{color:var(--accent)}summary::-webkit-details-marker{display:none}.step-main{display:flex;flex-direction:column;min-width:0}.step-main .eyebrow{font-size:9px;margin-bottom:3px;color:var(--accent)}.step-title{font-size:15px;font-weight:550;overflow-wrap:anywhere}.step-state{display:flex;align-items:center;gap:16px;font:10px var(--mono);white-space:nowrap;text-transform:uppercase;color:var(--muted)}.chevron{font:20px var(--mono);color:var(--accent)}details[open]>summary .chevron{font-size:0}details[open]>summary .chevron:after{content:"−";font:20px var(--mono)}.step-body{padding:0 0 25px;min-width:0}.command-label{font:9px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:4px 0 8px}pre{font:11px/1.65 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;margin:0;max-height:350px;overflow:auto}.command{background:var(--wash);padding:13px 15px;border-left:2px solid var(--line)}.facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px 16px;margin:20px 0}.facts dt,.artifact dt{font-size:10px;color:var(--muted);margin-bottom:4px}.facts dd{margin:0;font:11px/1.6 var(--mono);overflow-wrap:anywhere}.log{border-top:1px solid var(--line);font-size:11px}.log summary{padding:11px 0;cursor:pointer;color:var(--muted)}.log pre{padding:4px 0 16px}.right-column{border-left:1px solid var(--line);padding-left:36px;min-width:0}.beliefs label{display:block;font-size:11px;color:var(--muted);margin:20px 0 7px}select{width:100%;padding:9px 28px 9px 9px;background:var(--paper);border:1px solid var(--line);border-radius:2px;font-size:12px;max-width:100%}#hypotheses{list-style:none;padding:0;margin:25px 0}#hypotheses li{margin-bottom:20px}.hypothesis-label{display:flex;gap:9px;align-items:baseline;line-height:1.45;font-size:12px}.hypothesis-label code{font-size:10px;flex:none;color:var(--accent)}.bar-row{display:flex;gap:12px;align-items:center;margin-top:9px}.bar-track{height:6px;background:#e0e4d8;flex:1}.bar-fill{height:100%;background:var(--signal);width:0}.bar-value{font:10px var(--mono);width:65px;text-align:right;color:var(--muted)}.model-note{font-size:11px;line-height:1.6;color:var(--muted);border-top:1px dotted var(--line);padding-top:14px}.selection{border-top:1px solid var(--ink);padding-top:24px;margin-top:28px}.selection>p{font-size:12px;margin:12px 0}.selected-heading{display:flex;align-items:center;gap:9px}.signal-dot{height:7px;width:7px;background:var(--signal);border-radius:50%;flex:none}.selection .selected-id{font:15px var(--mono);margin-top:17px}.artifact{margin:20px 0}.artifact dt{margin-top:12px}.artifact dd{margin:0;font:10px/1.6 var(--mono);overflow-wrap:anywhere}.verify-result{display:flex;align-items:center;gap:8px;font:10px var(--mono)}.pill{display:inline-block;border:1px solid var(--line);padding:3px 7px;line-height:1.4}.pill.ok{color:var(--signal);border-color:#8fac97;background:#e9efe6}.pill.neutral{color:var(--muted)}.patch-location{font-size:11px;overflow-wrap:anywhere}.muted{color:var(--muted)}.empty{font-size:12px;color:var(--muted);padding:18px 0}.provenance{border-top:1px solid var(--ink);margin-top:55px;padding:28px 0;display:grid;grid-template-columns:1fr 1.65fr auto;gap:30px;align-items:start}.provenance dl{margin:0;min-width:0}.provenance dl>div{display:grid;grid-template-columns:120px minmax(0,1fr);gap:10px;margin-bottom:8px;font-size:11px}.provenance dt{color:var(--muted)}.provenance dd{margin:0;overflow-wrap:anywhere}.provenance code{font-size:10px}.provenance button{white-space:nowrap}.warning{border-left:3px solid var(--accent);padding:12px 20px;background:#eee6da;margin-bottom:30px}.warning h2{font-size:14px}.warning ul{font-size:12px;margin:10px 0 0;padding-left:17px}.warning li{margin-top:5px;overflow-wrap:anywhere}footer{display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--line);padding:20px 0 35px;gap:20px;font-size:10px;color:var(--muted)}footer>span{font-weight:800;letter-spacing:.08em}footer p{margin:0}[hidden]{display:none!important}
@media(max-width:1100px){.page{padding:0 32px}.workspace{gap:30px;grid-template-columns:minmax(0,1.4fr) minmax(280px,1fr)}.right-column{padding-left:26px}.provenance{grid-template-columns:1fr 1.5fr}.provenance button{grid-column:2;justify-self:start}.facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.page{padding:0 22px}.masthead{min-height:90px}.offline{font-size:8px;max-width:125px;line-height:1.7}.offline span{padding:0 4px}.brand{font-size:16px;gap:9px}.brand svg{width:31px;height:31px}.brand-sub{font-size:7px}.intro{padding:30px 0 25px}h1{font-size:30px;margin-bottom:22px}.decision{align-items:flex-start;flex-direction:column;gap:10px}.decision p{font-size:12px}.metrics{grid-template-columns:repeat(2,1fr);margin-bottom:30px}.metrics>div{padding:15px 18px}.metrics>div:nth-child(2){border-right:0}.metrics>div:nth-child(3){padding-left:0;border-top:1px solid var(--line)}.metrics>div:nth-child(4){border-top:1px solid var(--line)}.metrics strong{font-size:25px}.workspace{grid-template-columns:1fr;gap:34px}.right-column{border-left:0;padding-left:0;border-top:1px solid var(--ink);padding-top:27px}.section-heading{align-items:start}h2{font-size:20px}.section-heading button{font-size:10px;padding:7px 8px}.step{padding-left:30px}.step:before{left:9px}.step-number{font-size:9px}.step-title{font-size:13px}.step-detail>summary{gap:10px}.step-state{font-size:8px;gap:8px}.step-main .eyebrow{font-size:8px}.provenance{grid-template-columns:1fr;gap:23px;margin-top:34px}.provenance button{grid-column:1}.provenance dl>div{grid-template-columns:100px minmax(0,1fr)}.selection{margin-top:28px}footer{font-size:9px;align-items:start}footer p{text-align:right;max-width:220px}.facts{gap:14px}}

.fork-map{margin:0 0 40px;padding:0 0 32px;border-bottom:1px solid var(--line)}.fork-map .section-copy{max-width:none;margin-bottom:21px}.fork-hint{font:10px var(--mono);color:var(--muted);text-align:right}.fork-tree{display:grid;grid-template-columns:180px minmax(0,1fr);gap:40px;align-items:center}.fork-node{display:flex;flex-direction:column;align-items:flex-start;gap:4px;padding:13px 15px;text-align:left;min-width:0;width:100%;background:var(--paper);position:relative}.fork-node strong{font-size:12px;font-weight:550;line-height:1.4;overflow-wrap:anywhere}.fork-node .fork-kind{font:9px var(--mono);color:var(--accent);text-transform:uppercase;letter-spacing:.07em}.fork-node .fork-state{font:9px var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.03em}.fork-node[data-selected=true]{border-color:var(--accent);background:#efece2}.fork-root{border-color:var(--ink)}.fork-root:after{content:"";position:absolute;width:21px;height:1px;background:var(--line);right:-22px;top:50%}.fork-branches,.fork-verification{list-style:none;margin:0;padding:0}.fork-branches{position:relative;display:flex;flex-direction:column;gap:12px}.fork-branches:before{display:none}.fork-branch:after{content:"";position:absolute;left:-20px;top:0;bottom:-12px;width:1px;background:var(--line)}.fork-branch:first-child:after{top:50%}.fork-branch:last-child:after{bottom:50%}.fork-branch{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.72fr);gap:32px;position:relative;align-items:center;min-width:0}.fork-branch:before{content:"";position:absolute;left:-20px;top:50%;width:20px;height:1px;background:var(--line)}.fork-branch>.fork-node{grid-column:1}.fork-verification{position:relative;grid-column:2}.fork-verification:before{content:"";position:absolute;left:-32px;top:50%;width:32px;height:1px;background:var(--line)}.fork-verification:after{content:"";position:absolute;left:-6px;top:calc(50% - 3px);width:5px;height:5px;border-top:1px solid var(--muted);border-right:1px solid var(--muted);transform:rotate(45deg)}.fork-verifier{border-color:#8fac97}.fork-verifier .fork-kind{color:var(--signal)}h4[tabindex]:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
@media(max-width:760px){.fork-map{margin-bottom:30px;padding-bottom:27px}.fork-map .section-heading{display:block}.fork-hint{display:block;text-align:left;margin-top:10px}.fork-tree{grid-template-columns:minmax(0,1fr);gap:18px}.fork-root{max-width:230px}.fork-root:after{width:1px;height:19px;left:15px;right:auto;top:100%}.fork-branches{margin-left:30px;gap:14px}.fork-branches:before{display:none}.fork-branch:after{left:-15px;top:-14px;bottom:-14px}.fork-branch:first-child:after{top:-18px}.fork-branch:last-child:after{bottom:calc(100% - 44px)}.fork-branch{grid-template-columns:minmax(0,1fr);gap:14px}.fork-branch:before{left:-15px;top:44px;width:15px}.fork-verification{grid-column:1;margin-left:26px}.fork-verification:before{left:-13px;top:-14px;width:1px;height:calc(50% + 14px)}.fork-verification:after{left:-13px;width:13px;height:1px;background:var(--line);border:0;transform:none;top:50%}}

@media print{.page{padding:0}.skip-link,.filters,button{display:none}.workspace{display:block}.right-column{border:0;padding:0}.step-body{display:block}details>summary{break-after:avoid}pre{max-height:none}.metrics{margin-bottom:20px}.provenance{grid-template-columns:1fr}.offline{display:none}.selection{break-inside:avoid}body{font-size:11px}}
'''

SCRIPT = '''
'use strict';
const run=JSON.parse(document.getElementById('run-data').textContent);
const hypotheses=Array.isArray(run.hypotheses)?run.hypotheses.filter(h=>h&&typeof h==='object'):[];
const steps=Array.isArray(run.steps)?run.steps.filter(s=>s&&typeof s==='object'):[];
const point=document.getElementById('evidence-point');
function updateBeliefs(){
  const val=point.value;let weights={};
  if(val==='initial'){hypotheses.forEach(h=>weights[h.id]=h.prior)}
  else if(val==='final'){hypotheses.forEach(h=>weights[h.id]=h.posterior)}
  else {const s=steps[Number(val)];weights=(s&&s.posterior)||{}}
  document.querySelectorAll('#hypotheses li').forEach((row,i)=>{
    const h=hypotheses[i];if(!h)return;const n=weights[h.id];
    const valid=typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=1;
    row.querySelector('.bar-fill').style.width=valid?(100*n)+'%':'0%';
    row.querySelector('.bar-value').textContent=valid?(100*n).toFixed(1)+'%':'unreported';
  });
}
point.addEventListener('change',updateBeliefs);updateBeliefs();
let filter='all';
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{
  filter=button.dataset.filter;let count=0;
  document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  document.querySelectorAll('.step').forEach(row=>{const visible=filter==='all'||row.dataset.kind===filter;row.hidden=!visible;if(visible)count++});
  document.getElementById('filter-empty').hidden=count>0||steps.length===0;
}));
const expand=document.getElementById('expand-all');
expand.addEventListener('click',()=>{
  const visible=Array.from(document.querySelectorAll('.step:not([hidden]) .step-detail'));
  const open=!visible.length||!visible.every(el=>el.open);
  visible.forEach(el=>el.open=open);expand.textContent=open?'Collapse all steps':'Expand all steps';
});

document.querySelectorAll('[data-fork-target]').forEach(button=>button.addEventListener('click',()=>{
  const target=document.getElementById(button.dataset.forkTarget);if(!target)return;
  const row=target.closest('.step');
  if(row&&row.hidden){document.querySelector('[data-filter="all"]').click()}
  const details=target.tagName==='DETAILS'?target:target.closest('.step-detail');
  if(details)details.open=true;
  document.querySelectorAll('[data-fork-target]').forEach(node=>node.dataset.selected=String(node===button));
  const focusTarget=target.tagName==='DETAILS'?target.querySelector('summary'):target;
  target.scrollIntoView({block:'center',behavior:'auto'});if(focusTarget)focusTarget.focus({preventScroll:true});
}));

document.getElementById('download-json').addEventListener('click',()=>{
  const blob=new Blob([JSON.stringify(run,null,2)+'\\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob);const a=document.createElement('a');
  a.href=url;a.download='forksense-'+String(run.run_id||'report').replace(/[^a-zA-Z0-9_-]/g,'_')+'.json';
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
'''
