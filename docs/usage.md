# Using ForkSense

ForkSense needs Python 3.11+, Git and a clean repository with an existing commit. Live planning and repair also need an installed agent CLI with its own working login. Use existing subscription access where supported; ForkSense does not create credentials or require a separately billed API.

## Commands

| Command | Result |
| --- | --- |
| `forksense doctor --repo PATH` | Show executable paths, commit and cleanliness; no credential inspection. |
| `forksense demo --output FRESH_DIR` | Create a controlled fixture and run prepared candidate patches. |
| `forksense plan TASK ...` | Launch an agent to propose explicit hypotheses and probes. |
| `forksense inspect PLAN.json` | Validate and print the plan; execute no commands. |
| `forksense run PLAN.json ...` | Run the original verifier, diagnostics, repair and independent verification. |
| `forksense report REPORT.json --output NEW.html` | Render an offline report from saved JSON. |
| `forksense accept REPORT.json --repo PATH` | Check and print the verified patch. Add `--yes` to apply it. |

Use `forksense COMMAND --help` for the current options. Commands return zero for successful actions. `run` returns zero only for `verified` or `already-passing`; incomplete or rejected execution returns 2.

## Start with the test contract

Choose an existing failing test or an independently written regression test that covers the required behavior. The verifier is a command represented as an argument array, for example:

```json
["python", "-m", "unittest", "discover", "-s", "tests"]
```

`plan --verify "python -m unittest discover -s tests"` splits the supplied text into arguments without invoking a shell. Pipes, redirects, wildcard expansion and shell variables are not expanded. If a task requires a wrapper script, review and explicitly name that script. A wrapper can execute arbitrary code, so argument arrays are a quoting boundary, not a security sandbox.

Install project dependencies in an appropriate environment before running. Worktrees do not copy ignored virtual environments or arbitrary untracked fixtures. Prefer an interpreter path or test command that works from a fresh checkout. ForkSense forwards a small environment allowlist, including `PATH`, `HOME` and locale values. Ambient provider keys, GitHub tokens, `PYTHONPATH` and arbitrary project environment variables are not forwarded. Repository code and native CLI logins still have ordinary host capabilities.

## Plan and inspect

```sh
forksense plan "Fix requests sharing an incorrect cached total" \
  --repo /path/to/repo \
  --verify "/path/to/venv/bin/python -m unittest discover -s tests" \
  --editable src/checkout.py \
  --agent codex \
  --seconds 120 \
  --output /tmp/checkout-plan.json \
  --trust-repo

forksense inspect /tmp/checkout-plan.json
```

Planning uses a read-only agent session and a bounded snapshot of permitted source files. The planner is told to inspect source, avoid executing repository code, and propose cheap probes. The user-supplied verifier and editable paths override any planner changes to those fields. Planning cost is separate from the subsequent run budget; include it in comparisons.

Review each hypothesis, the predicted pass/fail outcome under each cause, the actual command and the cost estimate. Prefer a probe that distinguishes explanations over one that simply repeats the original failure. Probabilities are proposed assumptions. They may be wrong.

A version 1 plan has this structure:

```json
{
  "version": 1,
  "task": "Fix a cached total when tax changes",
  "verify": ["python", "-m", "unittest", "discover", "-s", "tests"],
  "editable_paths": ["src/checkout.py"],
  "hypotheses": [
    {"id": "cache-key", "description": "The key omits tax", "prior": 0.6},
    {"id": "rounding", "description": "Rounding happens too early", "prior": 0.4}
  ],
  "experiments": [
    {
      "id": "vary-tax",
      "label": "Vary only tax on repeated requests",
      "command": ["python", "-m", "unittest", "tests.test_checkout.TestCheckout.test_tax_change"],
      "cost_seconds": 1.0,
      "likelihoods": {
        "cache-key": {"pass": 0.05, "fail": 0.95},
        "rounding": {"pass": 0.9, "fail": 0.1}
      }
    }
  ]
}
```

This is an illustrative plan. The test path must exist in your repository. `editable_paths` must explicitly name relative, non-hidden source files or directories. Traversal paths, symlinks and submodule changes are rejected. Conventional test and fixture edits are rejected even if accidentally included in source scope; unusual test layouts still require careful scope review.

## Run within an explicit budget

```sh
forksense run /tmp/checkout-plan.json \
  --repo /path/to/repo \
  --output /tmp/checkout-run \
  --agent codex \
  --seconds 180 \
  --agent-calls 2 \
  --max-experiments 3 \
  --token-limit 200000 \
  --policy adaptive \
  --trust-repo
```

| Option | Meaning |
| --- | --- |
| `--seconds` | Shared elapsed-time budget used to bound baseline, probe, agent and verification child executions. Default 180. |
| `--agent-calls` | Maximum repair CLI invocations. Planning is additional. Default 2. |
| `--max-experiments` | Maximum diagnostic executions. Default 3. |
| `--token-limit` | Soft cap on reported input plus output tokens, including cached input in the reported input count. Stops subsequent calls after usage arrives. |
| `--seed` | Seed used by random experiment ordering. Default 0. |
| `--cost-model` | Optional observed-cost regression JSON. Exploratory; the controlled model did not beat the default heuristic. |

The seconds setting is not an exact command-level wall-clock guarantee: Git operations have their own 15-second limits, and worktree cleanup/report generation add overhead. A diagnostic gets at most the remaining time and a timeout based on four times its predicted cost, with a five-second minimum. The engine reserves time for repair and verification and stops buying diagnostics that would consume too much of the remaining budget.

Token usage may be unavailable. Unknown usage is recorded as `null`, not zero; a configured soft token cap then prevents subsequent calls. ForkSense cannot stop an in-flight turn exactly at a token count or convert subscription usage into a reliable dollar cost.

## Policies

- `adaptive`: expected information gain per estimated cost; stop probing at a maximum hypothesis weight of 0.90 or expected gain below 0.02 bits.
- `uncertainty`: expected information gain without cost normalization.
- `random`: seeded ordering of remaining diagnostic experiments.
- `single`: skip probes and attempt only the highest-prior cause.
- `fixed`: skip probes and attempt causes in prior order, within the repair-call budget; stop after the first verified patch.

The CLI `fixed` policy executes repairs sequentially. The controlled benchmark's `fixed-3` baseline is a separate concurrent prepared-repair implementation. Neither name implies a full MCTS comparison.

A failed implementation does not prove its causal hypothesis false. The engine keeps the posterior unchanged and can attempt another untried cause while budget remains. An impossible observation produces a contradiction warning and retains the prior rather than fabricating certainty.

## Read and accept

Run output contains `report.json`, `report.html`, retained candidate patches and verifier snapshots where applicable. Logs are bounded and may be marked truncated. Failed or interrupted agent attempts retain a diff where it can be captured; if a complete diff cannot be captured, the report can retain the candidate worktree and identify it for recovery.

`verified` means the source patch passed the supplied verifier in a new base worktree. `already-passing` means the original verifier passed, so no repair was attempted. `inconclusive`, `interrupted` and `unsafe` are not successful repairs. A weak verifier can accept a bad implementation; choose the contract carefully.

```sh
forksense accept /tmp/checkout-run/report.json --repo /path/to/repo
forksense accept /tmp/checkout-run/report.json --repo /path/to/repo --yes
```

Acceptance requires a verified report, the same base commit, a clean checkout and the exact recorded patch hash. It performs `git apply --check` before application. It does not commit, push or rerun the entire verifier. Review the patch, rerun your normal checks after application and make your own commit.

## Codex and Claude Code

Codex uses documented non-interactive `codex exec`, JSON events, read-only planning and workspace-write repair. Permission requests are not bypassed; unavailable operations fail. The tool does not fork hidden reasoning or intercept an active interactive session. [Official Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

Claude uses `claude -p` with JSON output and explicit permitted tool names. Its adapter supplies empty MCP configuration and disables hooks for that invocation; it does not use permission-bypass flags. It avoids `--bare` because that mode requires API authentication rather than the subscription login. This adapter was not executed locally. Check your installed version's `--help` and [official headless documentation](https://code.claude.com/docs/en/headless) before relying on compatibility.

Optional project-local integration skills are in [integrations](../integrations). Installing them is separate from running the CLI. They do not add hidden hooks, automatic acceptance or credentials.

## Common failures

| Observation | Next step |
| --- | --- |
| Repository is dirty, including untracked files | Preserve your work and choose a clean committed starting point. ForkSense does not stash or discard it. |
| Output already exists | Choose a fresh path; keep the earlier evidence. |
| Verifier already passes | Improve the reproducer or accept that no repair is needed under that contract. |
| Baseline times out or cannot launch | Fix the environment or raise the budget before judging a patch. |
| Verifier drift | Restore/review the external verifier and start a new run; changed bytes invalidate the result. |
| Agent returns a permissions or login failure | Resolve that CLI's native permission/login flow; ForkSense does not bypass it. |
| Candidate edits tests or another source path | Narrow the prompt/scope and rerun. Rejected edits are not accepted. |
| Patch hash or base differs at acceptance | Inspect the drift and run new experiments on the intended base. |
