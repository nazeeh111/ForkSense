# Controlled policy results

These are measured results on nine held-out synthetic tasks in three held-out cause families, repeated with 10 random seeds. Repairs are prepared templates and likelihoods are oracle-informed. There are zero live model calls. This is not evidence of SWE-bench or general coding-agent improvement.

| Policy | Resolved | Diagnosis | Probes | Prepared repairs | Commands | Wall s | Summed subprocess s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 33.3% | 33.3% | 0.00 | 1.00 | 1.00 | 0.249 | 0.248 |
| fixed-3 | 100.0% | 100.0% | 0.00 | 3.00 | 3.00 | 0.376 | 0.713 |
| random | 80.0% | 80.0% | 1.36 | 1.00 | 2.36 | 0.372 | 0.370 |
| uncertainty | 100.0% | 100.0% | 1.67 | 1.00 | 2.67 | 0.275 | 0.273 |
| adaptive | 100.0% | 100.0% | 1.67 | 1.00 | 2.67 | 0.256 | 0.254 |
| learned-cost | 100.0% | 100.0% | 1.67 | 1.00 | 2.67 | 0.291 | 0.288 |
| root-uct-proxy | 66.7% | 66.7% | 0.00 | 2.00 | 2.00 | 0.524 | 0.522 |

Values are means per trial. Fixed-3 executes three prepared repairs and independent verifiers concurrently. A smaller summed subprocess time means less measured process work; wall time includes host scheduling and startup effects.

## Paired differences from concurrent fixed-3

Positive values mean the named policy used more time or commands. Primary intervals resample three whole cause families with all task and seed pairs together. Three clusters are too few for strong population inference.

| Policy | Resolution difference | Wall difference s, 95% interval | Command difference, 95% interval |
| --- | ---: | ---: | ---: |
| single | -66.7% | -0.126 [-0.143, -0.113] | -2.00 [-2.00, -2.00] |
| random | -20.0% | -0.004 [-0.088, +0.085] | -0.64 [-1.27, -0.33] |
| uncertainty | +0.0% | -0.101 [-0.168, -0.038] | -0.33 [-0.33, -0.33] |
| adaptive | +0.0% | -0.120 [-0.148, -0.084] | -0.33 [-0.33, -0.33] |
| learned-cost | +0.0% | -0.084 [-0.116, -0.040] | -0.33 [-0.33, -0.33] |
| root-uct-proxy | -33.3% | +0.148 [+0.117, +0.189] | -1.00 [-1.00, -1.00] |

## Setup and limits

Oracle-informed prediction setup used 54 subprocess executions and 6.968 summed seconds. Observed-cost learning used 81 subprocess executions and 10.671 summed seconds, plus 0.000680 seconds to fit. These setup costs are excluded from the per-trial table. Learned-policy successes per wall second including training: 2.439.

No improvement in task-resolution rate over fixed-3 should be claimed when the resolution difference is zero. A learned cost ranking on this suite does not establish learned optimal branching, likelihood calibration, or stopping.

Harness SHA256: `100c2081e866e38ff75dc4cc0008d3b1dabeb7c0c7e368f80cef36c68b7fcb77`.

All source, task hashes, commands, observed outcomes, posteriors, candidate hashes, external verifier outputs and timing receipts are retained in the adjacent JSON and JSONL files. See [methodology](../README.md).

- 18 synthetic microtasks total, 9 held-out tasks in 3 held-out families; not SWE-bench.
- Repairs are prepared causal templates, not agent-generated patches; model calls are zero.
- Hypotheses and likelihoods are oracle-informed from the three known fault interventions.
- Bulk probe p0 repeats 4000 times; the other probes execute once. This intentionally varies diagnostic cost.
- Fixed-3 runs three prepared repairs and independent verifiers concurrently; subprocess time sums compute, wall time measures concurrency.
- Root UCT is a root-only two-pull proxy over prepared repairs, not agent-mcts, Saplings or full MCTS.
- Primary bootstrap clusters by three held-out families; task-level intervals are secondary. Seeds are repeats, not independent tasks.
- Training cost regression sees only train-family measured durations and command features.
- Small suite, hand-built causes and predicted outcomes do not establish broad agent performance gains.
