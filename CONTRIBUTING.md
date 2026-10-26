# Contributing

ForkSense is a small research preview. Contributions should improve an observable workflow, a documented limitation or the quality of its evidence.

## Run the local checks

From a clone, with Python 3.11+ and Git:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m unittest benchmarks.test_benchmarks -v
forksense demo --output /tmp/forksense-contributor-demo
```

Choose a fresh demo path. The demo commits only its own disposable fixture. No model credentials are needed for these checks. Live agent runs are optional and consume the installed CLI's access; do not place credentials or raw private transcripts in CI or issue reports.

Before changing experiment or verification behavior, read [usage](docs/usage.md), [method](docs/method.md) and [limits](docs/limitations.md). Preserve independent tests, failed-attempt artifacts, clean-checkout requirements and explicit acceptance. A test should exercise an actual failure or safety property, not merely mirror the implementation.

## Submit a focused change

Explain the concrete trigger, the previous behavior, the new behavior and the checks you ran. Keep unrelated source edits separate. Do not replace a measured negative result with a stronger marketing claim.

For agent compatibility changes, include the native CLI version, supported documented options and an actual execution receipt where available. Mock command construction does not establish live compatibility. Never add a permission bypass as a convenience fix.

For report or media changes, inspect the current rendered output and preserve the last valid artifact until its replacement succeeds. Source-controlled SVG or data-driven figures are preferable to untraceable screenshots of invented results.

## Propose a benchmark case

Use the benchmark issue template. A useful case includes a public repository and frozen base commit, a small task description, independent test provenance, setup requirements and an explicit budget. Keep reference patches and evaluator-only tests outside agent workspaces. Describe any information the agent can access.

Compare the same starting state and test contract. Ordinary agents may run their own diagnostics. Record planning, diagnostics, repairs, verification, failed runs, missing usage and environment limits. Report wall time and total compute separately for parallel methods. Repeat trials when feasible and cluster correlated tasks appropriately.

Changing `benchmarks/tasks.py` changes the frozen suite. Introduce a new version and manifest, explain why, and preserve prior result artifacts. Do not silently regenerate hashes or overwrite published receipts to make a changed suite look like the original study.

## Report a bug

Provide the ForkSense and native CLI versions, operating system, minimal reproduction and relevant status/error fields. Share a small redacted report rather than a complete private transcript. Verify that logs contain no secrets or proprietary data before attaching them.

The project has no hosted execution service. Please do not send credentials, ask maintainers to run untrusted code without a stated trust boundary, or file promotional issues in unrelated projects.

Contributions to this repository are accepted under its [MIT license](LICENSE). Preserve necessary upstream attribution and disclose the provenance of copied material or benchmark cases.
