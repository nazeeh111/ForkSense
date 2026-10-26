# Selected real issue reproductions

The corrected live pilot resolved the route-display case in 3/3 ordinary Codex attempts and 3/3 FORKSENSE attempts, with the same rounded mean time of 69.8 seconds. An advantage is unproven. See the [cohort report and receipts](results-live-v2/README.md).

These are selected [SWE-bench Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite) issue reproductions, not the official Docker evaluation or a leaderboard score.

| Instance | Original issue | Frozen base | Study status |
| --- | --- | --- | --- |
| `pallets__flask-4045` | [Dotted blueprint names](https://github.com/pallets/flask/issues/4041) | `d8c37f43724cd9fb0870f77877b7c4c7e38a19e0` | Six descriptive v1 calls; expanded external contract and instruction-asymmetry limits |
| `pallets__flask-4992` | [Binary config loading](https://github.com/pallets/flask/issues/4989) | `4c288bc97ea371817199908d0d9b12de9dae327e` | Base failure reproduced; no agent trial because the issue/API interface is ambiguous |
| `pallets__flask-5063` | [Route domain display](https://github.com/pallets/flask/issues/5004) | `182ce3dd15dfa3537391c3efaf9c3ff407d134d4` | Six corrected matched v2 calls; earlier defective-verifier runs retained separately |

The dataset suffix identifies a fixing pull request, not necessarily the original issue. `manifest.json` contains our summaries, URLs, base commits, dependency pins and original-prose/test-patch hashes. Full issue prose, judge nodes, test patches, hints and reference repairs are not bundled in the public manifest. Runtime setup fetches original issue/test material into external storage and never saves the reference source solution.

`base-verification.json` records substrate checks: 4045 produced 2 failures and 50 passes; 4992 produced 1 failure and 18 passes; 5063 produced 2 failures and 55 passes. These are base checks, not agent outcomes.

## Setup

Use Git and an existing Python 3.12 executable. Python 3.14 removes `pkgutil.get_loader`, used by these historical Flask versions. Free compatibility dependencies are pinned per case. Output must be fresh and outside the product and all agent workspaces.

```sh
python benchmarks/real_cases/fetch.py \
  --output /tmp/forksense-real-repro \
  --python python3.12 --install
```

Each case directory contains `repo/`, `problem.txt`, `metadata.json`, `test.patch` and optional `venv/`. Keep sibling test/judge material outside the agent workspace. Give repair agents original issue text, source, existing tests, the public smoke command and a fixed budget. Disable repair-network access and forbid parent/reference access. Path separation is not a security boundary against an adversarial agent with broader access.

For visible tests, use the case environment with `PYTHONPATH=src` and `-m pytest -q -W ignore::DeprecationWarning`. This avoids modern deprecation-as-error failures in historical projects; keep it identical across policies.

## Planning and offline final evaluation

`pilot_specs.py` defines issue-derived public smoke checks and possible diagnostics. `pilot.py` supplies frozen manual hypotheses and qualitative likelihoods. No automatic planner or learned policy produced these live-study plans.

Leave repairs uncommitted on the exact base. After the counted attempt ends, evaluate into a fresh external directory:

```sh
PYTHONPATH=src python benchmarks/real_cases/evaluate.py \
  --case-folder /tmp/forksense-real-repro/pallets__flask-5063 \
  --candidate /tmp/agent-candidate \
  --python /tmp/forksense-real-repro/pallets__flask-5063/venv/bin/python \
  --output /tmp/forksense-offline-judge
```

The evaluator captures staged, unstaged and untracked source through a private Git index. It rejects edits outside `src/flask`, clones a fresh judge, explicitly checks out and verifies the frozen base, applies candidate source, then applies the upstream test patch. Agent tests cannot replace the independent judge. The original candidate is unchanged.

Both issue and regression functions run. Historical pytest parameter IDs differ, so recorded functions expand to all their current parameters. Receipts retain commands, effective nodes, hashes, duration, status and exit code. Timeout, incomplete evaluation and nonzero exit never count as resolution. Do not feed final judge failures back into the same counted attempt.

Retained logs and candidate/judge artifacts stay private. Public receipts are sanitized. Retained stdout is capped at 64 KiB; the report identifies truncated trace audits.

Source/tests retain Flask's [BSD-3-Clause license](FLASK_LICENSE.txt). The SWE-bench evaluation repository is MIT-licensed. The inspected dataset card did not establish a separate dataset-wide license, so original prose/test bytes are fetched at runtime instead of redistributed here.
