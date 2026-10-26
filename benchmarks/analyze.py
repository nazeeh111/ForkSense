"""Additional paired checks for an already completed frozen run."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import statistics

from benchmarks.run import paired_comparisons


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    rows = [json.loads(line) for line in (args.directory / 'trials.jsonl').read_text().splitlines()]
    lookup = {(r['task_id'], r['seed'], r['policy']): r for r in rows}
    comparisons = {}
    for left, right in (('learned-cost', 'adaptive'), ('adaptive', 'uncertainty')):
        pairs = [(r, lookup[(r['task_id'], r['seed'], right)]) for r in rows if r['policy'] == left]
        comparisons[f'{left}_vs_{right}'] = {
            'pairs': len(pairs),
            'different_experiment_sequences': sum(
                [e['experiment_id'] for e in a['events']] != [e['experiment_id'] for e in b['events']]
                for a, b in pairs),
            'mean_wall_difference': statistics.mean(a['wall_seconds'] - b['wall_seconds'] for a, b in pairs),
            'resolution_difference': statistics.mean(float(a['resolved']) - float(b['resolved']) for a, b in pairs),
            'command_difference': statistics.mean(a['command_calls'] - b['command_calls'] for a, b in pairs),
        }
    result = {
        'learned_vs_heuristic': paired_comparisons(rows, baseline='adaptive'),
        'trajectory_checks': comparisons,
        'interpretation': 'The learned cost ranking changes some experiment sequences but does not improve resolution or command count over the heuristic. Observed timings do not establish a learned advantage.',
    }
    target = args.directory / 'additional-analysis.json'
    if target.exists():
        parser.error('additional-analysis.json exists; preserve earlier evidence')
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(target)


if __name__ == '__main__':
    main()
