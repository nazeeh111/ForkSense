# FORKSENSE research and differentiation

Inspected 2026-10-26. Research observations below are source reports, not local replications. Repository pages are live, unpinned observations; do not turn their descriptions into compatibility guarantees. No third-party source code was copied.

## Decisive findings

FORKSENSE should optimize **which discriminating observation to buy next**, rather than claim that worktrees, multiple attempts, runtime debugging, frozen verification, or tree search are new. The promising contribution is a small adaptive policy over explicit hypotheses and executable diagnostics, with cost-aware stopping and measured outcomes. Novelty remains a research hypothesis, not an established result.

1. **Scaling Test-Time Compute for Agentic Coding**, Kim et al., arXiv:2604.16529v1, submitted 16 Apr 2026. The supplied title and identifier match. The method summarizes completed rollouts, selects them through Recursive Tournament Voting, and conditions new attempts on multiple summaries through Parallel-Distill-Refine. Main experiments use 16 rollouts per iteration, two iterations, four reused summaries, groups of two, and eight votes. It reports improvements on SWE-bench Verified and Terminal-Bench, but does not establish that a lightweight diagnostic policy beats one ordinary installed CLI agent at matched small budgets. Transfer: compact evidence summaries and reuse. Distinction: select cheap experiments before spending whole rollouts. Paper license shown is CC BY-NC-SA 4.0; cite ideas rather than transplanting figures, prompts, or text into a permissively licensed product. [Abstract/version](https://arxiv.org/abs/2604.16529), [method and setup, sections 2–3.1](https://arxiv.org/html/2604.16529v1).

2. **RippleCP: Measuring Counterfactual Checkpoint Advantage in Coding Agents**, Akewar and Ranjan, arXiv:2610.09088v1, submitted 6 Oct 2026. The identifier matches. It measures matched checkpoint/skip futures and recovery cost, not adaptive hypothesis testing. Its 12-task pilot includes 106 recovery branches; the authors explicitly report no trained predictor or matched-budget policy study. Their 24 labeled cells are described as insufficient for fitting and honestly evaluating a predictor. Checkpoints archive files, transcript, and discovered facts; they do not snapshot process/model state. Transfer: pair executions, randomize order, charge experiment overhead, keep task-level statistical independence, and compare to the strongest simple rule. Do not describe it as a demonstrated learned checkpoint policy. [Abstract/version](https://arxiv.org/abs/2610.09088), [sections 3, 6, appendices A, D](https://arxiv.org/html/2610.09088v1).

3. **agent-mcts 0.1.0**, released 2 Aug 2026, MIT, Python ≥3.11. Already offers UCT search, Git worktrees, test-driven values, budgets, inspect/apply, and journaling. Its README distinguishes working Claude Code support from planned Codex v0.2 support, despite the broad introductory pitch. Current repository documentation acknowledges post-episode cost accounting, unknown interrupted costs, process-group termination, partial-state preservation, and worktree virtualenv issues. Transfer: use installed headless CLIs, preserve failed artifacts, terminate children, report unknown usage honestly. Differentiation cannot rest on adapters plus isolated attempts alone. These are documentation observations, not an executed compatibility audit. [PyPI](https://pypi.org/project/agent-mcts/), [repository README](https://github.com/natsu0529/mcts-llm-agent).

4. **Saplings**, Apache-2.0. A Python library for tool-use trajectory search through MCTS, A*, and greedy policies; it uses LiteLLM and an LLM evaluator by default, with custom execution evaluators supported. Its headline benchmark table cites the LATS paper, so do not present those values as independent Saplings replication or compare FORKSENSE directly to them. Its integration surface requires model/tool definitions rather than merely supervising an installed CLI. Transfer: algorithm baselines and configurable evaluation. For this subscription-only objective, reusing its provider stack would add credential/dependency work without solving the product's distinctive problem. [README](https://github.com/shobrook/saplings).

5. **SWE-Search**, Antoniades et al., arXiv:2410.20285v2. MCTS with action, value, and discriminator agents; combines numerical values and qualitative feedback. The paper reports relative improvement across five models. It is a relevant research comparator, but a small local UCT implementation must be labeled a UCT-inspired baseline, not a replication of SWE-Search or agent-mcts. [Paper](https://arxiv.org/html/2410.20285v2), [authors' implementation](https://github.com/aorwall/moatless-tree-search).

6. **ExecCritic**, Tao et al., arXiv:2609.09133v1, 8 Sep 2026. Separates test construction, qualification/freezing, and source repair. Its reported base-test condition reduces repair success, while stronger tests help. This directly motivates protecting independent verification and avoiding a patch's own tests as its sole judge. It also means frozen verification is prior art. [Paper](https://arxiv.org/abs/2609.09133).

7. **Debug2Fix**, Garg and Huang, arXiv:2602.18571v2, revised 21 Apr 2026. Adds interactive Java/Python debugging through a subagent design; evaluates on GitBug-Java and SWE-bench-Live and reports gains for particular models. Runtime observation alone is not a new contribution. [Current paper/version](https://arxiv.org/abs/2602.18571).

8. **Using Hypotheses as a Debugging Aid**, Alaboudi and LaToza, VL/HCC 2020, arXiv:2005.13652v1. A 20-developer study links early correct hypotheses to success and tests hypothesis support. Useful motivation for making explanations explicit, not evidence for FORKSENSE's own performance. [Paper](https://arxiv.org/abs/2005.13652).

## Architecture proposal, not an observed result

Use one planner call to propose a bounded structured experiment manifest: task, two or more competing hypotheses, diagnostic commands, predicted observation under each hypothesis, estimated cost, and a separate repair prompt. The scheduler runs low-cost diagnostic experiments first, updates the surviving explanations from actual observations, then asks the installed agent to implement the most supported explanation. Diagnostic predictions are model proposals and can be wrong; unsupported or contradictory outcomes must leave the case inconclusive rather than creating certainty.

Start with deterministic cost-normalized discrimination: score an experiment by its partition of currently viable hypotheses divided by estimated cost. Stop when an independent verifier passes, no affordable informative experiment remains, observations contradict all predictions, or the budget expires. Keep the full observation matrix inspectable. Estimates are scheduling features, not calibrated confidence.

An optional compact model can learn whether experiments proved useful from completed reports, using only pre-experiment features such as hypothesis count, predicted split, test-failure diversity, observed progress, and cost. A ridge/logistic ranking model is enough initially. Train/evaluate by task or task family, never by randomly splitting sibling experiment rows. Do not add or claim a trained model just to satisfy a checklist when the effective sample is too small. A genuine negative result should keep the simpler policy as default.

The wrapper controls filesystem snapshots and external prompts. It cannot fork an active model's hidden reasoning or restore arbitrary process state. Worktrees isolate edits, not OS effects, network, credentials, or malicious code. Run only trusted repositories with ordinary host execution; containerized evaluation is a separate explicit mode or requirement.

## Minimum credible evaluation

Freeze a manifest and independent evaluator before agents see tasks. The manifest records each repository/base SHA, issue text, dependency environment, allowed source paths, visible tests, hidden evaluator hash, family/split, and timeout. Exclude reference patches and gold-test material from agent workspaces. Publish the manifest, seeds/order, hashes, raw per-run reports, failed runs, commands, and aggregation script. Claim only the split and environment actually run.

Use two tiers and report them separately:

- **Controlled debugging:** heterogeneous mechanisms with known diagnoses, such as cache invalidation, off-by-one boundary, parser normalization, mutation aliasing, timezone conversion, and iterator consumption. Include easy/no-branch cases and wrong-diagnostic-prediction cases. Distinct constants applied to the same template are correlated repetitions, not independent held-out tasks.
- **Real issue cases:** a predeclared small subset of real frozen issue/base-commit tasks, preferably spanning repositories. If full SWE-bench evaluation is unavailable, describe these as selected issue reproductions, never a SWE-bench score.

Compare ordinary installed agent, fixed-budget multiple attempts, random experiment choice, simple uncertainty-triggered branching, adaptive discrimination/cost policy, and a clearly labeled UCT-inspired comparator. Use the same task/agent/model/repair verifier and an identical maximum wall-clock/episode budget. Report actual spend because adaptive stopping may use less. The ordinary agent can naturally run diagnostics; do not handicap it. Charge planning, diagnostic execution, repair, and verification. Fixed parallel's total compute and wall time differ, so show both rather than equating attempts with cost.

Predeclare primary metric: independently verified resolution rate at a budget. Secondary: actual wall time, model calls/tokens when reported, diagnostic correctness on known-ground-truth cases, wrong-selection rate, number of diagnostics/repairs, and resolution per unit cost. Missing token usage stays null, never zero. Treat unresolved/timeouts as failures for resolution rate and retain their incurred cost. Run at least three repetitions per real task where feasible, randomizing mode order. Use paired task-level bootstrap intervals for differences; do not treat correlated branches as independent samples. A tiny pilot can establish execution and estimate effects, but cannot establish broad superiority.

For the learned policy, freeze train/validation/test families before fitting. Compare learned to the strongest heuristic and ablate information gain, cost normalization, and early stopping. Report a negative learned-policy result if appropriate. Simulation or trace replay can test scheduler mechanics but cannot establish live coding-agent improvement because the intervention can change future trajectories.

**SWE-bench practical limits:** the official harness uses Docker, recommends substantial x86 resources, and flags ARM support as experimental; current documentation supports local task-repository builds on M-series Macs. Validate environment before launching downloads. Unique run IDs matter because cached evaluation can otherwise reuse earlier results. [Official repository setup and usage](https://github.com/SWE-bench/SWE-bench).

## Presentation foundations

**PaperVizAgent** is the official renamed PaperBanana implementation, Apache-2.0. Its five-agent diagram pipeline includes model/image generation and API/cloud configuration. The repository says it is a demonstration framework. Investigated as requested; for this free-subscription-only task, hand-authored SVG diagrams rendered from actual method data avoid provider setup and are more directly auditable. [Repository](https://github.com/google-research/papervizagent).

**/brag** is an MIT agent skill that creates short launch videos through HyperFrames; it lists Node 22+, FFmpeg, and HyperFrames. It can use local Kokoro narration when explicitly enabled. Use the installed local brag skill if useful, but an authentic terminal/video capture of a successful current run should remain the evidence. Avoid calling a designed reenactment a recording. Preserve license notices for any bundled music/SFX used. [Repository](https://github.com/latent-spaces/brag).

## Claims to avoid at release

- “First” or “state of the art” from this bounded research pass.
- Performance gains copied from any cited paper as if FORKSENSE measured them.
- A “SWE-bench score” from hand-selected extracted cases.
- “Independent hidden tests” when agents can read them or their reference solution.
- Hard token/dollar caps when only post-run usage is available.
- “Sandboxed” solely because experiments use worktrees.
- “Learned adaptive policy improves agents” based only on synthetic replay or same-family train/test variants.

The honest initial position is a research preview: a small, auditable experimentation layer with a testable adaptive policy and reproducible pilot evidence. The supported marketing claim should be selected only after actual results are available.
