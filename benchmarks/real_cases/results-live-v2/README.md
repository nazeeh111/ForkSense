# Live pilot: execution works, an advantage is unproven

On the corrected route-display case, ordinary Codex and FORKSENSE each resolved **3/3 attempts**, with **57 external tests passing in every attempt**. Mean trial time was **69.8 seconds for both**. This establishes an end-to-end integration on one selected issue, not a performance improvement.

| Cohort | Ordinary Codex | FORKSENSE | Interpretation |
| --- | --- | --- | --- |
| `pallets__flask-5063`, corrected v2 | 3/3 external resolutions; 69.8 s mean | 3/3 external resolutions; 69.8 s mean | Matched instructions; one unique task, three paired repeats |
| `pallets__flask-4045`, v1 | 3/3 public smoke passes; 0/3 strict external resolutions | 3/3 public smoke passes; 0/3 strict external resolutions | Descriptive only: instruction asymmetry and expanded external contract |
| `5063`, invalid v1 | Two executed attempts | Two executed attempts | Defective public verifier; excluded from comparison |
| Remaining `5063` v1 schedule | One cancelled before the agent | One cancelled before the agent | Zero repair calls |

These are separate cohorts, not twelve clean comparative trials. There were **16 actual CLI repair episodes**: six descriptive 4045 calls, four invalid 5063 v1 calls and six corrected 5063 v2 calls. Two further scheduled trials were cancelled before invoking Codex. Failures, invalid runs and cancellations remain in [the ledger](trials.jsonl).

## Method

Agents received the original issue, frozen upstream source, existing tests, allowed source scope and a public smoke verifier. Official post-PR test patches stayed outside their workspaces and entered a fresh offline judge only after repair and selection ended. No reference source solution was retained or supplied. The judge captured source changes, asserted the exact frozen base and ran both issue and regression tests. This is a selected issue reproduction, **not an official SWE-bench score**.

Each attempt allowed 180 seconds and one Codex CLI invocation. Both modes reserved 25% of remaining time for extraction and public verification. One CLI episode can contain many internal model/tool calls. Mode order was seeded and randomized, with at most two episodes concurrent. Recorded trial durations include diagnostics and repair; final external evaluation time is separate. Runtime plan construction was measured; manual authoring time was unknown and excluded.

FORKSENSE used predeclared **manual** hypotheses and qualitative 0.95/0.05 likelihoods, not automatic planning or calibrated probabilities. It selected one metadata probe and one repair hypothesis in each corrected attempt. Declared probe costs were equal, so this study does not isolate cost normalization, learned ranking or automatic hypothesis generation.

The installed agent was `codex-cli 0.164.0`; native login status reported ChatGPT authentication. No model/effort override, API key, purchase or reset credit was used. The model identifier was not independently observed; it remained the user's configured default. Orchestration used Python 3.14.7; historical Flask/tests used pinned Python 3.12.14 environments. Dependencies were trusted local tools, not a hermetic container image.

## Corrections and descriptive failures

The first 5063 smoke invoked the application's custom command group through `app.test_cli_runner()`. Built-in `routes` belongs to `FlaskGroup`, so it failed with `SystemExit(2)` before the domain assertion. Four completed attempts are invalid for comparison. Two remaining calls were cancelled before Codex execution; artifacts were preserved.

The corrected smoke uses `CliRunner().invoke(FlaskGroup(create_app=...), ["routes"])`. Before rerunning, the command exited successfully on the base and the smoke failed specifically because domain strings were absent. A controlled metadata-rendering callback passed the same smoke, checking its oracle without a reference repair. An independent reviewer checked the correction. V2 also matched explicit parent/reference-access restrictions across modes. Hashes of seven imported core modules were frozen and remained unchanged during all six calls.

V1's `launch_order` labels contain a bookkeeping bug: labels duplicate while actual schedule-list order remains intact. Public receipts preserve those labels and add `schedule_index`. V2 fixes the labels. The interrupted v1 runner's individual receipts are authoritative where its aggregate summary was incomplete.

All six 4045 attempts rejected dotted blueprint names and preserved ordinary routing under the public contract. The official patch additionally changed dotted **endpoint** validation from `AssertionError` to `ValueError`, although original visible tests expected the older exception. Each attempt therefore had one strict external failure and 51 passes. This does not by itself establish that the narrower constructor fix was incorrect. Those v1 prompts also differed in explicit anti-leak instructions, so their outcomes are descriptive, not a clean causal comparison.

## Usage and limits

| Corrected v2 total, three attempts | Ordinary | FORKSENSE |
| --- | --- | --- |
| CLI episodes | 3 | 3 |
| Wrapper diagnostics | 0 | 3 |
| Reported input tokens | 766,132 | 695,324 |
| Reported cached input tokens | 692,864 | 613,248 |
| Reported output tokens | 6,636 | 6,954 |

Cached input is not interchangeable with uncached computation. No dollar cost or cost saving was estimated; missing usage remains `null`. Ordinary Codex could diagnose freely, so zero wrapper diagnostics does not mean no investigation.

Retained stdout was capped at 64 KiB. All three corrected ordinary logs were truncated; usage was parsed from their final tail, which was not retained. Corrected FORKSENSE logs were complete. No reference access was observed in retained command events, but a complete ordinary trace audit is unavailable. Raw retained logs, attempted patches and judge artifacts remain private. Public receipts omit usernames, full issue prose, raw logs and test patches, retaining hashes instead. Hashes do not recover missing trace bytes.

Three repetitions are not three independent tasks. Historical cases may occur in model training data. One matched task supports no task-population confidence interval or general superiority claim. There is no live fixed-parallel, random-branching, full MCTS, Claude Code or learned-policy comparison here. The controlled prepared-repair benchmark is separate.

## Evidence and reproduction

- [Summary and paired observations](summary.json)
- [All sanitized trial receipts](trials.jsonl)
- [V2 schedule and source hashes](v2/predeclared.json), [source integrity](v2/source-integrity.json), [normalized manual plans](v2/public-plans.json)
- [V1 descriptive, invalid and cancelled receipts](v1/receipts.json)
- Exact v2 [runner](v2/execution-source/pilot.py), [public contracts](v2/execution-source/pilot_specs.py) and [evaluator](v2/execution-source/evaluate.py) at execution

Use the current runner for a fresh reproduction; its post-study environment lookup also accepts the per-case environments created by `fetch.py`. Choose fresh external directories and an existing Python 3.12 executable:

```sh
python benchmarks/real_cases/fetch.py \
  --output /tmp/forksense-real-repro \
  --case pallets__flask-5063 --python python3.12 --install

PYTHONPATH=src python -u -m benchmarks.real_cases.pilot \
  --setup /tmp/forksense-real-repro \
  --output /tmp/forksense-live-new \
  --case pallets__flask-5063 --seconds 180 --seed 20261026
```

This consumes existing Codex subscription usage and downloads public source/dependencies. It does not reproduce identical stochastic outputs or guarantee an unchanged default model.

Provenance: [SWE-bench Lite](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite), [Flask issue 4041](https://github.com/pallets/flask/issues/4041), [Flask issue 5004](https://github.com/pallets/flask/issues/5004), and Flask's [BSD-3-Clause license](../FLASK_LICENSE.txt). The SWE-bench harness is MIT-licensed; the inspected dataset card did not establish a separate dataset-wide license. Original full prose and test patches are fetched at runtime rather than redistributed here.
