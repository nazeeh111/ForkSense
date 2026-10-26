# Method and research evidence

ForkSense investigates one practical question: **can a cheap diagnostic distinguish competing causes before another full coding attempt is worth its cost?** The current preview makes that decision explicit and reproducible. It does not establish a new search algorithm or broad coding-agent superiority.

## The experiment contract

A plan contains a task, a verifier, permitted source paths, hypotheses with prior weights, and diagnostic commands with predicted pass/fail likelihoods under each hypothesis. Planning can use an installed agent, but the plan is inspectable data. It does not authorize execution by itself.

Each diagnostic runs on the same frozen base commit in a disposable detached worktree. The engine records the real exit status and bounded output. Exit zero is `pass`, nonzero is `fail`; a timeout, launch error or output limit is inconclusive and does not update hypothesis weights.

Let `p(h)` be the current weight of hypothesis `h` and `P(o | h, e)` the plan's predicted probability of outcome `o` under experiment `e`. After a completed observation:

```text
p(h | o, e) ∝ p(h) × P(o | h, e)
```

The result is normalized to sum to one. These are standard Bayesian updates over supplied assumptions. A high weight is not a calibrated probability of patch correctness. If the observed outcome has zero probability under every hypothesis, the engine records a contradiction and retains the earlier weights.

The default experiment score is:

```text
expected reduction in hypothesis entropy / estimated execution seconds
```

Entropy measures uncertainty in the hypothesis distribution; information gain measures the predicted reduction in that uncertainty. The engine computes both possible outcomes, weights them by their predicted probabilities, and ranks available experiments. This is standard cost-sensitive experimental design.

The adaptive policy stops probing when the largest hypothesis weight is at least 0.90, expected information gain is below 0.02 bits, no experiment remains, or the budget should be reserved for repair and verification. These are explicit engineering rules, not learned optimal stopping conditions. Ordinary tasks can use `single` or a plan with no probes. A baseline that already passes triggers no repair call.

## Repair and verification

The repair CLI receives the task, one hypothesis and observed diagnostics. It operates in a separate worktree and is told to edit only the allowed source paths. ForkSense captures the actual diff, rejects changed paths outside scope, rejects conventional test/fixture changes and symlink/submodule changes, and applies the resulting source patch to a fresh base worktree.

The original verifier judges that fresh candidate. Agent-generated tests are never sufficient as the sole judge. A candidate's own changed test files do not travel into verification. The result is `verified` only when the supplied verifier completes successfully and the active source checkout still matches its starting commit and clean state.

External regular files explicitly named in verifier arguments are hashed and copied as evidence before baseline execution. The original paths still execute so `__file__`, sibling imports and fixture discovery retain their meaning. Hashes of both original files and evidence copies are checked before and after verification. This freezes those explicit file bytes, not every imported dependency, external fixture, interpreter or service. It is not a hermetic runtime.

A failing implementation does not logically disprove its causal explanation. ForkSense retains the hypothesis weights and can attempt another untried cause within the repair-call budget. It records failed and partial attempts. Acceptance is a separate operation that checks the base commit, checkout cleanliness and patch hash before applying; it never commits.

## Learned component

The optional cost model is regularized log-linear regression over four pre-execution features: an intercept, logarithmic declared cost, logarithmic command length and logarithmic hypothesis count. It predicts execution cost, which changes the experiment ranking. It does not predict whether an implementation is correct.

The controlled model was fitted to 81 observed probe durations from nine training tasks in the cache, pagination and CSV families. Held-out retry, path and datetime families were excluded from fitting. Training used no pass/fail labels, hidden-test results or held-out durations. The model records training task hashes and provenance.

On the held-out controlled suite, learned cost ranking changed 30 of 90 experiment sequences relative to the heuristic. It achieved the same resolution and command count, used 0.035 seconds more mean wall time per trial on this host, and required 10.67 seconds of training subprocess executions. Including training, its observed success per wall second was below fixed-three. The learned component did not earn a default position. The heuristic remains the default.

This is a small exploratory cost model, not a demonstrated original ML contribution. Learning when to branch, calibrated likelihoods, useful experiment generation and optimal stopping remain open research work.

## What was measured

### Controlled policy study

The [frozen suite](../benchmarks/README.md) has six hand-built causal families and three fault interventions per family. Three complete families form the training split; three different families form the held-out split. The held-out set therefore contains nine distinct tasks. Ten seeds repeat each task across seven policies, giving 630 trials in total.

Every selected diagnostic and verifier is a real subprocess execution. Forecasts are oracle-informed by known fault interventions, with fixed likelihood reliability of 0.98. Prepared targeted source transformations stand in for model-generated repairs. The first probe in each family performs a deliberately more expensive bulk repetition, while other probes perform one focused observation. These assumptions isolate policy behavior and deliberately vary cost. They do not represent an ordinary distribution of agent tasks.

The strongest prepared baseline executes three candidate repairs and their independent verifiers concurrently. The adaptive heuristic matches its 100% resolution with 2.67 commands rather than 3 and one prepared repair rather than 3. Random diagnostic selection resolves 80%; the root-only UCT proxy resolves 66.7%. The proxy has no tree rollouts or model calls and is not a replication of an external search system.

Wall time and summed subprocess time are reported separately. One-time oracle-setup and learned-cost training overhead are retained. The primary 2000-sample bootstrap resamples whole held-out cause families, keeping sibling tasks and repeated seeds together. Only three family clusters exist, so intervals are exploratory. Secondary task-cluster intervals and paired differences against concurrent fixed-three are also published. Repeated seeds are not counted as additional independent tasks.

[Results table](../benchmarks/results-v2/REPORT.md), [raw receipts](../benchmarks/results-v2/trials.jsonl), [paired learned-policy analysis](../benchmarks/results-v2/additional-analysis.json) and [frozen hashes](../benchmarks/results-v2/artifact-manifest.json) preserve the actual evidence. Reproduce with:

```sh
python -m unittest benchmarks.test_benchmarks -v
python -m benchmarks.run --output /tmp/forksense-benchmark-new --seeds 10
python -m benchmarks.report /tmp/forksense-benchmark-new
python -m benchmarks.analyze /tmp/forksense-benchmark-new
```

Run from a cloned repository with ForkSense installed. Chart regeneration uses `benchmarks/plot.py`; SVG generation uses the standard library and PNG generation additionally needs Pillow. These are development/rendering tools, not runtime CLI dependencies.

### Recorded live Codex fixture

A [recorded controlled checkout run](evidence/live-codex-demo/report.json) used the installed Codex CLI for the actual repair, without supplying its prepared patch. One probe identified the omitted tax component of a cache key; one repair call produced a patch that passed four independent contract tests. The run took 63.70455 seconds and preserved the active checkout.

Its reported usage was 106,604 input tokens, including 91,392 cached input tokens, and 427 output tokens. This is one execution receipt, not a comparison to ordinary Codex. The default demo's hypotheses and probes were prepared; this receipt does not establish autonomous hypothesis discovery. Public exports redact machine-local paths and omit raw agent transcripts, so they are not directly reusable acceptance directories.

Structured planning and real-repository pilots must be reported separately from this prepared-plan fixture. A plausible plan alone does not prove a useful diagnosis. No result from selected issue reproductions should be called a SWE-bench score. Full repeated live-agent comparisons, matched model budgets and full external tree-search methods are not established by the controlled benchmark.

## Prior work and differentiation

| Foundation | What it contributes | What ForkSense can fairly claim |
| --- | --- | --- |
| [Scaling Test-Time Compute for Agentic Coding](https://arxiv.org/abs/2604.16529), v1 | Selects and reuses summaries of full coding rollouts through Recursive Tournament Voting and Parallel-Distill-Refine. | A smaller pre-repair diagnostic interface; no replication or superiority claim. |
| [RippleCP](https://arxiv.org/abs/2610.09088), v1 | Measures paired checkpoint-versus-skip recovery futures; placement learning is future work. | Pair costs and outcomes carefully; do not call file snapshots hidden model-state forks. |
| [agent-mcts](https://pypi.org/project/agent-mcts/) and its [implementation](https://github.com/natsu0529/mcts-llm-agent) | Existing UCT search, worktrees, budgets, test-based values and installed-agent integration. | Worktree branching and CLI adapters are existing foundations, not novelty. |
| [Saplings](https://github.com/shobrook/saplings) | MCTS, A* and greedy search over tool-use trajectories, with configurable evaluators. | An alternative integration surface focused on installed CLIs and explicit diagnostic plans. |
| [SWE-Search](https://arxiv.org/abs/2410.20285) | Tree search with action, value and discriminator agents. | A relevant future full-method comparator; the root proxy is not its replication. |
| [ExecCritic](https://arxiv.org/abs/2609.09133) | Separates test construction, qualification/freezing and repair. | Independent verification is essential prior art and a safeguard. |
| [Debug2Fix](https://arxiv.org/abs/2602.18571) | Interactive runtime debugging for coding agents. | Runtime observation alone is not a new contribution. |
| [Using Hypotheses as a Debugging Aid](https://arxiv.org/abs/2005.13652) | Studies explicit hypotheses in human debugging. | Motivation for inspectable explanations, not evidence of this tool's performance. |

The relevant opportunity is a useful experiment-selection layer with measurable benefit per cost. The present policy uses established mathematics, and this bounded review does not establish novelty. Published results in the cited papers are their authors' reports; they are not ForkSense results.

The [official SWE-bench harness](https://github.com/SWE-bench/SWE-bench) is the reference for full SWE-bench evaluation. This project does not substitute hand-selected reproductions or synthetic tasks for that harness.

[PaperVizAgent](https://github.com/google-research/papervizagent) was investigated for diagrams. Its model/API pipeline would add provider setup, so the project uses original, source-controlled SVG figures instead. The [brag project](https://github.com/latent-spaces/brag) informed launch-video investigation; the project's actual captures and media provenance remain the evidence. See [third-party notices](../THIRD_PARTY_NOTICES.md).
