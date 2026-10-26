# Controlled causal debugging benchmark

This suite measures experiment selection on **18 hand-built Python microtasks**, with nine tasks from three held-out cause families. It does not measure autonomous coding performance and is not SWE-bench.

## Reproduce

From the repository root, with the package installed or `PYTHONPATH=src`:

```sh
python -m unittest benchmarks.test_benchmarks -v
python -m benchmarks.run --output /tmp/forksense-benchmark-new --seeds 10
```

The output directory must be fresh. Earlier evidence is never replaced. No model, API key, network call, third-party Python package, or paid service is used. Python and its subprocess startup contribute to measured wall time. The fixed-3 baseline actually runs its three prepared repairs and independent verifiers concurrently; other policies run their chosen actions serially. Subprocess seconds sum actual execution time while wall seconds reflect concurrency. These are prepared repairs, not parallel coding agents.

## Frozen task specification

`tasks.py` defines six families, each with three distinct causal fault interventions. `tasks-v1.json` freezes hashes of all source, public symptom tests, external verifier source, diagnostics, and evaluator-only repair catalogs. The runner refuses to run after an unacknowledged fixture change.

| Training families | Held-out families |
| --- | --- |
| Cache key normalization | Retry semantics |
| Pagination | Path normalization |
| CSV parsing | UTC date conversion |

Each task exposes only buggy `subject.py` and a public symptom test in its own directory. Independent verifier source and prepared cause-specific repairs stay outside that directory, in the evaluator. The verifier covers multiple boundary cases, not just the diagnostic observation. A fixture check confirms that every original program fails, its specified repair passes, and the other two repair templates fail.

## Experimental assumptions

The engine receives three explicit hypotheses and likelihood tables. In this controlled suite those predictions come from actually executing probes under each known causal intervention. They are **oracle-informed** and given a fixed 0.98 reliability. The values are a policy input, not measured probability calibration or confidence that a repair is correct. This optimistic assumption isolates selection from hypothesis generation and must not be read as a result for model-created plans.

The first diagnostic in each family performs 4000 repeated evaluations, representing a bulk regression diagnostic; the other two execute a single focused diagnostic. These deliberate cost differences test whether selection avoids unnecessary work. The suite does not claim that this artificial cost distribution represents ordinary projects. A process invocation runs the selected probe; passing and failing outputs both constitute legitimate observations.

After diagnostics, a prepared targeted source transformation substitutes for an agent's repair. Wrong transformations leave the causal defect unresolved. These are called **prepared repair calls**, never model calls. A correct selection can still be rejected by the independent verifier; only a verifier exit status of zero counts as resolved. The suite has zero model calls and cannot establish token savings.

## Compared policies

| Policy | Diagnostics | Repair budget |
| --- | --- | --- |
| `single` | None | One fixed first hypothesis |
| `fixed-3` | None | All three prepared repairs, concurrently verified |
| `random` | Random remaining probe | At most two probes, one repair |
| `uncertainty` | Maximum expected information gain | At most two probes, one repair |
| `adaptive` | Maximum information gain per declared cost | At most two probes, one repair |
| `learned-cost` | Information gain per fitted observed cost | At most two probes, one repair |
| `root-uct-proxy` | None | Two root UCB pulls over prepared repairs |

For diagnostic policies, stop when a hypothesis has posterior weight at least 0.90 or all remaining probes have expected information gain below 0.02 bits. These thresholds are explicit engineering defaults, not learned or optimal stopping claims.

The root UCT baseline is intentionally labeled a proxy. It has no tree rollouts, LLM calls, checkpointing, or repository actions and is not an implementation or evaluation of agent-mcts, Saplings, RippleCP, or other full tree-search systems. Strong full-method comparisons and ordinary Codex/Claude trials require a separate live-agent study.

## Learned cost model

`forksense.learning.CostModel` uses regularized log-linear regression, a standard method. Its four features are an intercept, the logarithm of declared cost, logarithmic command length, and logarithmic hypothesis count. Training uses 81 measured probe costs: nine training-family tasks, three probes, three repeats. It uses no pass/fail outcomes, ground truth labels, verifier results, or held-out durations. The model's JSON records training task hashes, families and sample count. The summary reports one-time training and oracle-setup costs separately, plus learned-policy success per wall second including training. Per-trial policy timings exclude that setup overhead.

The learned component changes the ranking through predicted execution cost. It does not learn hypothesis correctness, calibrated likelihoods, value of branching, or an optimal stopping policy. On this small suite it is exploratory; lack of improvement is a result to report, not a reason to relabel it as novel ML.

## Evidence and uncertainty

The runner randomizes task/policy scheduling with a fixed seed, emits an immediate JSONL receipt for every trial, and saves every diagnostic command, actual outcome, posterior update, attempted repair hash, external verifier output and measured duration. Summary metrics include resolution rate, causal selection accuracy, incorrect selection rate, commands, prepared repair calls, wall time and successes per wall second.

Random seeds repeat the same tasks. A 2000-sample primary bootstrap resamples **whole held-out families with their tasks and seed repeats together**. Only three family clusters exist, so these are exploratory intervals. Secondary intervals resample task IDs; seeds do not inflate either sample count. Paired differences against fixed-3 match task and seed, then resample whole families. There are only nine held-out tasks in three families. The task-level interval remains conditional on those hand-built families and is not a population-wide agent-performance interval. Timing depends on the host, Python version, load and filesystem; interpret small timing differences cautiously.

## Next evidence needed

A credible extension would freeze real repository issues and executable tests before running ordinary agents, fixed-budget independent attempts, full search implementations, and FORKSENSE on identical starting commits and compute budgets. Separate discovery and evaluation partitions; freeze agent versions, task access, verification and selection rules; repeat trials; retain failures and inconclusive cases. This repository's live-agent receipts, if provided, must be assessed separately from these prepared-repair results.
