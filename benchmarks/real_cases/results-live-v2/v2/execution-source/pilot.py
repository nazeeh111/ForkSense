"""Two-case paired live Codex pilot with external official final evaluation.

This intentionally uses frozen manual plans and the installed CLI's configured
model/subscription. It measures neither automatic planning nor model training.
Run with an external fresh --output directory; no reference solution is loaded.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import threading
import time

from forksense import agents, git
from forksense import engine, policy, process, models, learning
from forksense.engine import Budget, execute
from forksense.process import clean_env, ok, run
from benchmarks.real_cases.pilot_specs import case_spec

CASES = ("pallets__flask-4045", "pallets__flask-5063")
LOCK = threading.Lock()
COMMON = ("This is a frozen trusted-repository benchmark. You have one repair attempt within a 180-second trial. "
          "Edit only the permitted source paths. Preserve all tests and configuration. "
          "Do not commit, push, use network, inspect credentials, install packages, change Git state, "
          "read sibling or parent directories, or modify other worktrees. "
          "Use only this workspace's source and existing tests, the original task text and the supplied public smoke command. "
          "Do not retrieve original issues, fixing pull requests, reference material, evaluator tests or solutions. "
          "Implement a real fix rather than a test-specific workaround.")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def announce(message: str) -> None:
    with LOCK:
        print(message, flush=True)


def command_for(source: str, python: str) -> list[str]:
    # clean_env intentionally strips PYTHONPATH; insert the current worktree's
    # src path in the public command so every fresh worktree imports its bytes.
    wrapper = "import os,sys;sys.path.insert(0,os.path.join(os.getcwd(),'src'));exec(" + repr(source) + ")"
    return [python, "-W", "ignore::DeprecationWarning", "-c", wrapper]


def make_plan(case: str, python: str, problem: str) -> dict:
    spec = case_spec(case, python)
    if case.endswith("4045"):
        hs = [
            ("construction", "Blueprint construction lacks validation of dots in its name; enforce the requested rejection without breaking ordinary blueprints."),
            ("ordinary_registration", "The visible symptom is caused by ordinary blueprint registration or routing being broken, rather than missing name validation."),
            ("namespace", "The naming problem is in later namespace or nested-blueprint handling while construction already validates the requested invariant."),
        ]
        predicted_pass = {
            "dotted-construction-rejected": {"construction": .05, "ordinary_registration": .95, "namespace": .95},
            "ordinary-blueprint-works": {"construction": .95, "ordinary_registration": .05, "namespace": .95},
        }
    else:
        hs = [
            ("rendering", "Routing retains subdomain metadata, but the routes CLI omits it when formatting output; fix the display without changing route registration."),
            ("routing", "Routing itself loses declared subdomain metadata before the CLI sees it; investigate rule construction and retention."),
            ("blueprint", "Blueprint registration loses its assigned subdomain, although direct rule registration retains it; investigate blueprint option propagation."),
        ]
        predicted_pass = {
            "direct-rule-has-subdomain": {"rendering": .95, "routing": .05, "blueprint": .95},
            "blueprint-rule-has-subdomain": {"rendering": .95, "routing": .05, "blueprint": .05},
            "routes-displays-subdomain": {"rendering": .05, "routing": .05, "blueprint": .05},
        }
    experiments = []
    for probe in spec["probes"]:
        experiments.append({"id": probe["id"], "label": probe["label"],
                            "command": command_for(probe["source"], python), "cost_seconds": 1.0,
                            "likelihoods": {h: {"pass": p, "fail": 1-p} for h,p in predicted_pass[probe["id"]].items()}})
    return {"version": 1, "task": problem, "verify": command_for(spec["smoke_source"], python),
            "editable_paths": spec["editable_paths"],
            "repair_constraints": COMMON,
            "hypotheses": [{"id": hid, "description": desc, "prior": 1/len(hs)} for hid,desc in hs],
            "experiments": experiments}


def baseline(plan: dict, repo: Path, out: Path, seconds: float) -> dict:
    out.mkdir()
    budget = Budget(seconds=seconds, agent_calls=1, max_experiments=0)
    base = git.head(repo)
    receipt = {"mode": "ordinary", "base_commit": base, "agent_calls": 0, "status": "inconclusive", "usage": {k:None for k in ("input_tokens", "output_tokens", "cached_input_tokens")}}
    with git.worktree(repo, base, out / "worktrees") as tree:
        receipt["baseline"] = run(plan["verify"], tree, budget.remaining())
    base_result = receipt["baseline"]
    if not ok(base_result) and base_result.get("returncode") is not None and not base_result.get("error") and not base_result.get("timed_out"):
        prompt = ("Fix this trusted local repository. Task: " + plan["task"] + "\n"
                  "Investigate and diagnose freely using the source and existing tests. "
                  "Edit ONLY these source paths: " + json.dumps(plan["editable_paths"]) + ". Preserve all tests and configuration. "
                  + plan["repair_constraints"] + "\n"
                  "Public smoke verifier argv: " + json.dumps(plan["verify"]) + ".\n")
        (out / "prompt.txt").write_text(prompt)
        with git.worktree(repo, base, out / "worktrees") as tree:
            receipt["agent_calls"] = 1
            result = agents.invoke("codex", prompt, tree, budget.remaining() * .75)
            receipt["agent"] = result
            receipt["usage"] = result.get("usage", receipt["usage"])
            try:
                patch, names, _ = git.snapshot_patch(tree, base)
                (out / "attempt.patch").write_bytes(patch)
                receipt["attempt_files"] = names
            except git.GitError as exc:
                receipt["attempt_note"] = str(exc)
            if ok(result):
                try:
                    patch, names = git.extract_patch(tree, base, plan["editable_paths"])
                    (out / "candidate.patch").write_bytes(patch)
                    receipt["patch_path"] = "candidate.patch"
                    receipt["files"] = names
                    receipt["patch_sha256"] = digest(patch)
                except git.GitError as exc:
                    receipt["scope_error"] = str(exc)
        if receipt.get("patch_path"):
            with git.worktree(repo, base, out / "worktrees") as tree:
                git.apply_bytes(tree, (out / receipt["patch_path"]).read_bytes())
                receipt["verification"] = run(plan["verify"], tree, budget.remaining())
            if ok(receipt["verification"]):
                receipt["status"] = "verified"
    receipt["duration"] = time.monotonic() - budget.started
    write(out / "receipt.json", receipt)
    return receipt


def final_judge(case_folder: Path, patch: bytes | None, python: str, output: Path) -> dict:
    if patch is None:
        return {"resolved": False, "status": "no_eligible_patch", "elapsed_seconds": 0.0, "returncode": None}
    candidate = output / "gold-candidate"
    subprocess.run(["git", "-c", "advice.detachedHead=false", "clone", "--quiet", "--no-hardlinks", str(case_folder / "repo"), str(candidate)], check=True, env=clean_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git.apply_bytes(candidate, patch)
    command = [sys.executable, str(Path(__file__).with_name("evaluate.py")), "--case-folder", str(case_folder),
               "--candidate", str(candidate), "--python", python, "--output", str(output / "gold-judge")]
    result = subprocess.run(command, env=clean_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=150)
    (output / "gold-command.txt").write_text(result.stdout)
    if result.returncode:
        return {"resolved": False, "status": "judge_error", "elapsed_seconds": 0.0, "returncode": result.returncode}
    return json.loads((output / "gold-judge" / "receipt.json").read_text())


def trial(spec: dict, setup: Path, output: Path, seconds: float) -> dict:
    case, mode, repeat = spec["case"], spec["mode"], spec["repeat"]
    name = f"{case}-{repeat}-{mode}"
    out = output / name
    out.mkdir()
    case_folder = setup / case
    python = str(setup / ("compat-venv312" if case.endswith("4045") else "modern-venv312") / "bin/python")
    plan = json.loads((output / "plans" / (case + ".json")).read_text())
    repo = case_folder / "repo"
    started = time.monotonic()
    announce("START " + name)
    try:
        if mode == "ordinary":
            raw = baseline(plan, repo, out / "ordinary", seconds)
            patch = (out / "ordinary" / raw["patch_path"]).read_bytes() if raw.get("patch_path") else None
            public_status = raw["status"]
            usage = raw["usage"]
            calls = raw["agent_calls"]
            diagnostic_count = 0
            trial_seconds = raw["duration"]
            agent_result = raw.get("agent", {})
        else:
            raw = execute(plan, repo, out / "forksense", agent="codex", budget=Budget(seconds=seconds, agent_calls=1,max_experiments=3), policy="adaptive", trusted=True,
                          progress=lambda message: announce(name + " " + message))
            selected = raw.get("selected")
            repair = next((s for s in raw["steps"] if s.get("kind") == "repair"), {})
            patch_path = selected["patch_path"] if selected else repair.get("patch_path")
            patch = (out / "forksense" / patch_path).read_bytes() if patch_path else None
            public_status = raw["status"]
            usage = {k:raw["totals"].get(k) for k in ("input_tokens", "output_tokens", "cached_input_tokens")}
            calls = raw["totals"]["agent_calls"]
            diagnostic_count = sum(s.get("kind") == "probe" for s in raw["steps"])
            trial_seconds = raw["totals"]["duration"]
            agent_result = repair
        # Hidden official tests are first introduced after the repair/selection
        # attempt ends. Their feedback is never sent back to that trial's agent.
        judge_start = time.monotonic()
        gold = final_judge(case_folder, patch, python, out)
        judge_seconds = time.monotonic() - judge_start
        receipt = {**spec, "trial_id": name, "status": public_status, "agent_calls": calls,
                   "usage": usage, "diagnostic_count": diagnostic_count, "trial_seconds": trial_seconds,
                   "gold_evaluation_seconds": judge_seconds, "total_seconds": time.monotonic()-started,
                   "gold_resolved": bool(gold.get("resolved")), "resolved": bool(gold.get("resolved")) and patch is not None,
                   "accepted_patch": public_status == "verified", "gold_status": gold.get("status"), "gold_returncode": gold.get("returncode"),
                   "patch_sha256": digest(patch) if patch is not None else None,
                   "agent_returncode": agent_result.get("returncode"), "agent_error": agent_result.get("error"),
                   "agent_log_truncated": bool(agent_result.get("truncated")),
                   "raw_receipt_sha256": digest(json.dumps(raw,sort_keys=True).encode()),
                   "base_commit": plan_base(case), "plan_sha256": digest((output / "plans" / (case + ".json")).read_bytes())}
    except Exception as exc:
        receipt = {**spec,"trial_id":name,"status":"harness_error","resolved":False,"gold_resolved":False,
                   "accepted_patch":False,"agent_calls":None,"usage":{k:None for k in ("input_tokens","output_tokens","cached_input_tokens")},
                   "total_seconds":time.monotonic()-started,"error_type":type(exc).__name__}
        (out / "error.txt").write_text(repr(exc))
    write(out / "public-receipt.json", receipt)
    with LOCK:
        with (output / "receipts.jsonl").open("a") as stream:
            stream.write(json.dumps(receipt,sort_keys=True)+"\n")
    announce("DONE " + name + " status=" + receipt["status"] + " gold=" + str(receipt["resolved"]))
    return receipt


def plan_base(case: str) -> str:
    return case_spec(case, "unused")["base_commit"]


def summarize(receipts: list[dict], schedule: list[dict]) -> dict:
    cases = list(dict.fromkeys(s["case"] for s in schedule))
    result = {"schema_version":1,"study":"live manual-plan Codex pilot","unique_tasks":len(cases),"repositories":1,"repeats_per_task":len({s['repeat'] for s in schedule}),
              "planned_attempts":len(schedule),"completed_receipts":len(receipts),"modes":{},"paired_by_task":[],
              "limits":["Hand-selected tasks from one repository; repeats do not create independent tasks.",
                        "Manual plans and qualitative likelihoods, not automatic hypothesis generation or calibrated probabilities.",
                        "Manual authoring time is unmeasured and excluded; runtime plan construction is recorded separately.",
                        "Official source/test material remains external until final offline judging; public historical tasks may occur in pretraining.",
                        "Selected issue reproduction under pinned host dependencies, not official Docker SWE-bench evaluation.",
                        "No full tree-search or fixed-parallel comparator in this live pilot; prepared-repair benchmarks are separate."]}
    for mode in ("ordinary","forksense"):
        rows = [r for r in receipts if r["mode"]==mode]
        times = [r.get("trial_seconds",r.get("total_seconds",0)) for r in rows]
        result["modes"][mode] = {"attempts":len(rows),"resolved":sum(r["resolved"] for r in rows),
                                "resolution_rate":sum(r["resolved"] for r in rows)/len(rows) if rows else None,
                                "mean_trial_seconds":sum(times)/len(times) if times else None,
                                "reported_agent_calls":sum(r.get("agent_calls") or 0 for r in rows),
                                "unknown_agent_call_rows":sum(r.get("agent_calls") is None for r in rows),
                                "input_tokens":sum(r["usage"]["input_tokens"] for r in rows) if all(r["usage"]["input_tokens"] is not None for r in rows) else None,
                                "output_tokens":sum(r["usage"]["output_tokens"] for r in rows) if all(r["usage"]["output_tokens"] is not None for r in rows) else None}
    for case in cases:
        row={"case":case}
        for mode in ("ordinary","forksense"):
            rs=[r for r in receipts if r["case"]==case and r["mode"]==mode]
            row[mode]={"attempts":len(rs),"resolved":sum(r["resolved"] for r in rs)}
        result["paired_by_task"].append(row)
    return result


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--seconds",type=float,default=180)
    parser.add_argument("--seed",type=int,default=20261026)
    parser.add_argument("--case",choices=CASES,action="append",help="Restrict a corrected run to predeclared cases")
    parser.add_argument("--smoke-only",action="store_true",help="Run first paired repeat only; no restart or extra calls")
    args=parser.parse_args()
    output=args.output.resolve();setup=args.setup.resolve()
    if output.exists():parser.error("output must be fresh")
    output.mkdir(parents=True);(output/"plans").mkdir()
    setup_start=time.monotonic()
    core_modules = (engine,policy,process,agents,git,models,learning)
    core_files = {Path(module.__file__).name:Path(module.__file__) for module in core_modules}
    core_hashes = {name:digest(path.read_bytes()) for name,path in core_files.items()}
    (output/"core-source").mkdir()
    for name,path in core_files.items():shutil.copy2(path,output/"core-source"/name)
    shutil.copy2(Path(__file__),output/"pilot-executed.py")
    shutil.copy2(Path(__file__).with_name("pilot_specs.py"),output/"pilot-specs-executed.py")
    shutil.copy2(Path(__file__).with_name("evaluate.py"),output/"evaluate-executed.py")
    cases = tuple(args.case or CASES)
    for case in cases:
        python=str(setup/("compat-venv312" if case.endswith("4045") else "modern-venv312")/"bin/python")
        plan=make_plan(case,python,(setup/case/"problem.txt").read_text())
        write(output/"plans"/(case+".json"),plan)
        if git.head(setup/case/"repo")!=plan_base(case):raise RuntimeError("base drift")
        git.require_clean(setup/case/"repo")
    pairs=[(case,repeat) for repeat in range(3) for case in cases]
    rng=random.Random(args.seed)
    # First pair acts as a smoke check and remains in the denominator.
    first=pairs.pop(0);rng.shuffle(pairs);pairs=[first]+pairs
    schedule=[]
    for pair_index,(case,repeat) in enumerate(pairs):
        modes=["ordinary","forksense"];rng.shuffle(modes)
        first_order = len(schedule)
        schedule.extend({"case":case,"repeat":repeat,"mode":mode,"launch_order":first_order+i,"pair_index":pair_index} for i,mode in enumerate(modes))
    if args.smoke_only:schedule=schedule[:2]
    versions={"codex":subprocess.run(["codex","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=clean_env()).stdout.strip(),
              "python":sys.version,"model_override":None}
    freeze={"seed":args.seed,"schedule":schedule,"maximum_trial_seconds":args.seconds,"maximum_agent_calls_per_trial":1,"process_id":os.getpid(),
            "agent_timeout_rule":"Both modes reserve 25 percent of remaining time for extraction and public verification.",
            "manual_plan_authoring_seconds":None,"runtime_plan_setup_seconds":time.monotonic()-setup_start,
            "core_source_sha256":core_hashes,
            "versions":versions,"files":{str(p.relative_to(Path(__file__).parents[2])):digest(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name("pilot_specs.py"),Path(__file__).with_name("manifest.json"),Path(__file__).with_name("evaluate.py")]},
            "plan_sha256":{case:digest((output/"plans"/(case+".json")).read_bytes()) for case in cases}}
    write(output/"predeclared.json",freeze)
    receipts=[]
    # No concurrent mutation of source bases. Each trial uses detached worktrees.
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_jobs=[pool.submit(trial,s,setup,output,args.seconds) for s in schedule[:2]]
        for job in as_completed(first_jobs):receipts.append(job.result())
        write(output/"summary.json",summarize(receipts,schedule))
        announce("SMOKE PAIR COMPLETE: " + json.dumps([{k:r.get(k) for k in ("trial_id","status","resolved","agent_error")} for r in receipts]))
        pending=[pool.submit(trial,s,setup,output,args.seconds) for s in schedule[2:]]
        for job in as_completed(pending):
            receipts.append(job.result());write(output/"summary.json",summarize(receipts,schedule))
    write(output/"summary.json",summarize(receipts,schedule))
    after_hashes={name:digest(path.read_bytes()) for name,path in core_files.items()}
    write(output/"source-integrity.json",{"before":core_hashes,"after":after_hashes,"unchanged":core_hashes==after_hashes})
    announce("PILOT COMPLETE " + str(output/"summary.json"))


if __name__=="__main__":main()
