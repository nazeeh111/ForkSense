"""Render an evidence table from a completed benchmark summary, without inference."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def render(summary):
    lines = [
        '# Controlled policy results', '',
        'These are measured results on nine held-out synthetic tasks in three held-out cause families, repeated with '
        f"{summary['seeds']} random seeds. Repairs are prepared templates and likelihoods are oracle-informed. "
        'There are zero live model calls. This is not evidence of SWE-bench or general coding-agent improvement.', '',
        '| Policy | Resolved | Diagnosis | Probes | Prepared repairs | Commands | Wall s | Summed subprocess s |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for name, row in summary['policies'].items():
        lines.append(f"| {name} | {row['resolution_rate']:.1%} | {row['diagnosis_accuracy']:.1%} | "
                     f"{row['mean_probe_calls']:.2f} | {row['mean_prepared_repair_calls']:.2f} | "
                     f"{row['mean_command_calls']:.2f} | {row['mean_wall_seconds']:.3f} | "
                     f"{row['mean_subprocess_seconds']:.3f} |")
    lines.extend(['', 'Values are means per trial. Fixed-3 executes three prepared repairs and independent verifiers concurrently. '
                  'A smaller summed subprocess time means less measured process work; wall time includes host scheduling and startup effects.', '',
                  '## Paired differences from concurrent fixed-3', '',
                  'Positive values mean the named policy used more time or commands. Primary intervals resample three whole cause families '
                  'with all task and seed pairs together. Three clusters are too few for strong population inference.', '',
                  '| Policy | Resolution difference | Wall difference s, 95% interval | Command difference, 95% interval |',
                  '| --- | ---: | ---: | ---: |'])
    for name, row in summary['paired_comparisons']['policies'].items():
        wall = row['wall_seconds']; calls = row['command_calls']
        wi = wall['family_cluster_bootstrap_95']; ci = calls['family_cluster_bootstrap_95']
        lines.append(f"| {name} | {row['resolved']['mean_difference']:+.1%} | "
                     f"{wall['mean_difference']:+.3f} [{wi[0]:+.3f}, {wi[1]:+.3f}] | "
                     f"{calls['mean_difference']:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}] |")
    costs = summary['setup_costs']
    lines.extend(['', '## Setup and limits', '',
                  f"Oracle-informed prediction setup used {costs['oracle_prediction_executions']} subprocess executions "
                  f"and {costs['oracle_prediction_subprocess_seconds']:.3f} summed seconds. "
                  f"Observed-cost learning used {costs['learned_cost_training_executions']} subprocess executions "
                  f"and {costs['learned_cost_training_subprocess_seconds']:.3f} summed seconds, plus "
                  f"{costs['learned_cost_fit_seconds']:.6f} seconds to fit. These setup costs are excluded from the per-trial table. "
                  f"Learned-policy successes per wall second including training: "
                  f"{costs['learned_success_per_wall_second_including_training']:.3f}.", '',
                  'No improvement in task-resolution rate over fixed-3 should be claimed when the resolution difference is zero. '
                  'A learned cost ranking on this suite does not establish learned optimal branching, likelihood calibration, or stopping.', '',
                  f"Harness SHA256: `{summary['harness_sha256']}`.", '',
                  'All source, task hashes, commands, observed outcomes, posteriors, candidate hashes, external verifier outputs '
                  'and timing receipts are retained in the adjacent JSON and JSONL files. See [methodology](../README.md).', ''])
    lines.extend('- ' + text for text in summary['limitations'])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    summary = json.loads((args.directory / 'summary.json').read_text())
    target = args.directory / 'REPORT.md'
    if target.exists():
        parser.error('REPORT.md already exists; preserve prior render')
    target.write_text(render(summary))
    print(target)


if __name__ == '__main__':
    main()
