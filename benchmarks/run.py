"""Execute a frozen policy microbenchmark, with external oracle tests.

python -m benchmarks.run --output benchmarks/results --seeds 10

Prepared repair catalogs replace the coding model in this benchmark. All probes
and verification are real subprocess executions. This is not an agent benchmark.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from benchmarks.tasks import all_tasks, FAMILIES, frozen_manifest, materialize, probe_source
from forksense.learning import CostModel
from forksense.policy import normalize, entropy, rank, update

POLICIES = ('single', 'fixed-3', 'random', 'uncertainty', 'adaptive', 'learned-cost', 'root-uct-proxy')


def execute(argv, cwd, timeout=15):
    start = time.monotonic()
    try:
        process = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                                 env={'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin',
                                      'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'})
        return {'command': argv, 'returncode': process.returncode,
                'stdout': process.stdout[-2000:], 'stderr': process.stderr[-2000:],
                'seconds': time.monotonic() - start, 'status': 'completed'}
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
        return {'command': argv, 'returncode': None, 'stdout': decoded(error.stdout)[-2000:],
                'stderr': decoded(error.stderr)[-2000:], 'seconds': time.monotonic() - start,
                'status': 'timeout'}
    except OSError as error:
        return {'command': argv, 'returncode': None, 'stdout': '', 'stderr': str(error),
                'seconds': time.monotonic() - start, 'status': 'error'}


def make_experiments(task, predictions):
    return [{
        'id': p['id'], 'label': task.hypotheses[index],
        'command': [sys.executable, '-B', '-c', probe_source(p['expression'], p['repetitions'])],
        'cost_seconds': p['cost'],
        'likelihoods': {f'h{h}': {'pass': .98 if predictions[p['id']][h] == 'pass' else .02,
                                 'fail': .98 if predictions[p['id']][h] == 'fail' else .02}
                        for h in range(3)},
    } for index, p in enumerate(task.experiments)]


def calibrate_predictions(tasks, work):
    """Evaluator creates oracle-informed likelihoods from known interventions.

    No hidden test is used to generate the predictions. This assumption is explicit
    and optimistic; generated likelihood calibration is an unevaluated limitation.
    """
    by_family = defaultdict(list)
    for task in tasks:
        by_family[task.family].append(task)
    predictions = {}
    receipts = []
    for family, variants in by_family.items():
        predictions[family] = {f'p{i}': [] for i in range(3)}
        for task in variants:
            directory = work / ('prediction-' + task.id)
            materialize(task, directory)
            for probe in task.experiments:
                argv = [sys.executable, '-B', '-c', probe_source(probe['expression'])]
                result = execute(argv, directory)
                if result['returncode'] or result['stdout'].strip() not in ('pass', 'fail'):
                    raise RuntimeError(f'probe failed: {task.id}: {result}')
                predictions[family][probe['id']].append(result['stdout'].strip())
                receipts.append(dict(task_id=task.id, probe_id=probe['id'], **result))
    return predictions, receipts


def repair_and_verify(task, hypothesis, root, verifier, attempt):
    candidate = root / f'candidate-{attempt}'
    candidate.mkdir()
    old, new = task.repairs[hypothesis]
    candidate_source = task.source.replace(old, new, 1)
    (candidate / 'subject.py').write_text(candidate_source)
    result = execute([sys.executable, '-B', '-c', verifier.read_text()], candidate)
    result.update(hypothesis=hypothesis, changed=candidate_source != task.source,
                  patch_sha256=hashlib.sha256(candidate_source.encode()).hexdigest())
    return result


def trial(task, policy, seed, experiments, model, work):
    root = work / f'{task.id}-{policy}-{seed}'
    root.mkdir()
    repository = root / 'repo'
    materialize(task, repository)
    private = root / 'oracle'
    private.mkdir()
    verifier = private / 'verify.py'
    verifier.write_text(task.verifier_source)
    started = time.monotonic()
    p = normalize({f'h{i}': 1.0 for i in range(3)})
    events = []
    repairs = []
    remaining = list(experiments)
    rng = random.Random(seed)
    if policy in ('random', 'uncertainty', 'adaptive', 'learned-cost'):
        for step in range(2):
            if max(p.values()) >= .9:
                break
            mode = {'learned-cost': 'adaptive'}.get(policy, policy)
            ranked = rank(p, remaining, mode, seed=seed * 100 + step,
                          model=model if policy == 'learned-cost' else None)
            if not ranked or ranked[0]['information_gain'] < .02:
                break
            selected = ranked[0]['experiment']
            result = execute(selected['command'], repository)
            outcome = result['stdout'].strip()
            if result['returncode'] or outcome not in ('pass', 'fail'):
                events.append(dict(experiment_id=selected['id'], **dict(result, status='error')))
                break
            previous = dict(p)
            p = update(p, selected, outcome)
            events.append(dict(experiment_id=selected['id'], outcome=outcome,
                               before=previous, after=dict(p), **result))
            remaining = [e for e in remaining if e['id'] != selected['id']]
        candidates = [max(p, key=p.get)]
    elif policy == 'fixed-3':
        candidates = list(p)
    elif policy == 'root-uct-proxy':
        # Root-only UCB over prepared repairs: cold-start equal priors, two pulls.
        # No LLM, rollout, simulation, or implementation of external MCTS methods.
        visits = {h: 0 for h in p}
        candidates = []
        for step in range(2):
            h = max(p, key=lambda h: (p[h] + math.sqrt(2 * math.log(step + 2)/(1 + visits[h])), -int(h[1:])))
            visits[h] += 1
            candidates.append(h)
    else:
        candidates = ['h0']
    if policy == 'fixed-3':
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(repair_and_verify, task, h, root, verifier, i)
                       for i, h in enumerate(candidates)]
            repairs = [future.result() for future in futures]
    else:
        for index, hypothesis in enumerate(candidates):
            repairs.append(repair_and_verify(task, hypothesis, root, verifier, index))
    passed = [r for r in repairs if r['returncode'] == 0]
    chosen = passed[0]['hypothesis'] if passed else candidates[0]
    return {
        'task_id': task.id, 'family': task.family, 'split': task.split, 'seed': seed,
        'policy': policy, 'resolved': bool(passed), 'diagnosis_correct': chosen == task.ground_truth,
        'incorrect_selection': not passed and chosen != task.ground_truth,
        'probe_calls': len(events), 'prepared_repair_calls': len(repairs), 'model_calls': 0,
        'command_calls': len(events) + len(repairs),
        'wall_seconds': time.monotonic() - started,
        'subprocess_seconds': sum(e['seconds'] for e in events + repairs),
        'truth': task.ground_truth, 'selected': chosen,
        'posterior': p, 'events': events, 'repairs': repairs,
    }


def bootstrap_cluster_interval(rows, key='resolved', samples=2000, cluster='family'):
    """Resample whole families by default; seeds are not new tasks."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[cluster]].append(float(row[key]))
    means = [statistics.mean(v) for v in grouped.values()]
    rng = random.Random(6217)
    replicates = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(samples))
    return [replicates[int(.025 * samples)], replicates[int(.975 * samples)]]


def summarize(trials):
    summary = {}
    for policy in POLICIES:
        rows = [r for r in trials if r['policy'] == policy and r['split'] == 'heldout']
        seconds = sum(r['wall_seconds'] for r in rows)
        summary[policy] = {
            'unique_tasks': len({r['task_id'] for r in rows}), 'trials': len(rows),
            'resolution_rate': statistics.mean(r['resolved'] for r in rows),
            'resolution_family_cluster_bootstrap_95': bootstrap_cluster_interval(rows),
            'resolution_task_cluster_bootstrap_95': bootstrap_cluster_interval(rows, cluster='task_id'),
            'diagnosis_accuracy': statistics.mean(r['diagnosis_correct'] for r in rows),
            'incorrect_selection_rate': statistics.mean(r['incorrect_selection'] for r in rows),
            'mean_probe_calls': statistics.mean(r['probe_calls'] for r in rows),
            'mean_prepared_repair_calls': statistics.mean(r['prepared_repair_calls'] for r in rows),
            'mean_command_calls': statistics.mean(r['command_calls'] for r in rows),
            'mean_wall_seconds': seconds / len(rows),
            'mean_subprocess_seconds': statistics.mean(r['subprocess_seconds'] for r in rows),
            'success_per_wall_second': sum(r['resolved'] for r in rows) / seconds,
            'model_calls': 0,
        }
    return summary


def paired_comparisons(trials, baseline='fixed-3'):
    """Paired differences, clustered by held-out family (only three clusters)."""
    reference = {(r['task_id'], r['seed']): r for r in trials if r['policy'] == baseline}
    comparisons = {}
    for policy in POLICIES:
        if policy == baseline:
            continue
        pairs = []
        for row in trials:
            if row['policy'] != policy:
                continue
            base = reference[(row['task_id'], row['seed'])]
            pairs.append({'family': row['family'], 'task_id': row['task_id'],
                          'resolved': float(row['resolved']) - float(base['resolved']),
                          'wall_seconds': row['wall_seconds'] - base['wall_seconds'],
                          'subprocess_seconds': row['subprocess_seconds'] - base['subprocess_seconds'],
                          'command_calls': row['command_calls'] - base['command_calls'],
                          'repair_calls': row['prepared_repair_calls'] - base['prepared_repair_calls']})
        comparisons[policy] = {key: {'mean_difference': statistics.mean(p[key] for p in pairs),
                                    'family_cluster_bootstrap_95': bootstrap_cluster_interval(pairs, key=key)}
                               for key in ('resolved', 'wall_seconds', 'subprocess_seconds', 'command_calls', 'repair_calls')}
    return {'baseline': baseline, 'paired_by': ['task_id', 'seed'], 'primary_cluster': 'family',
            'clusters': 3, 'warning': 'Only three hand-built family clusters; intervals are exploratory.',
            'policies': comparisons}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('benchmarks/results'))
    parser.add_argument('--seeds', type=int, default=10)
    args = parser.parse_args(argv)
    if not 1 <= args.seeds <= 100:
        parser.error('seeds must be between 1 and 100')
    if args.output.exists():
        parser.error('output must be a fresh directory so earlier evidence is preserved')
    args.output.mkdir(parents=True)
    tasks = all_tasks()
    manifest = frozen_manifest()
    expected = json.loads((Path(__file__).parent / 'tasks-v1.json').read_text())
    if expected != manifest:
        raise ValueError('task suite differs from frozen manifest')
    with tempfile.TemporaryDirectory(prefix='forksense-benchmark-') as temporary:
        work = Path(temporary)
        predictions, receipts = calibrate_predictions(tasks, work)
        observations = []
        for task in tasks:
            if task.split != 'train':
                continue
            experiments = make_experiments(task, predictions[task.family])
            directory = work / ('training-' + task.id)
            materialize(task, directory)
            for repeat in range(3):
                for e in experiments:
                    result = execute(e['command'], directory)
                    if result['status'] != 'completed' or result['returncode'] != 0:
                        raise RuntimeError(f'training probe failed: {result}')
                    observations.append({'experiment': e, 'hypothesis_count': 3, 'seconds': result['seconds'],
                                         'task_id': task.id, 'repeat': repeat})
        fit_started = time.monotonic()
        model = CostModel.fit(observations, provenance={
            'suite_version': 1, 'training_families': ['cache', 'pagination', 'csv'],
            'heldout_families': ['retry', 'path', 'datetime'],
            'training_task_hashes': {t.id: t.sha256 for t in tasks if t.split == 'train'},
            'warning': 'Small controlled cost model; exploratory, no correctness calibration.',
        })
        fit_seconds = time.monotonic() - fit_started
        model.save(args.output / 'cost-model.json')
        trials = []
        schedule = [(task, policy, seed) for task in tasks if task.split == 'heldout'
                    for seed in range(args.seeds) for policy in POLICIES]
        random.Random(74219).shuffle(schedule)
        with (args.output / 'trials.jsonl').open('w') as stream:
            for index, (task, policy, seed) in enumerate(schedule):
                result = trial(task, policy, seed, make_experiments(task, predictions[task.family]), model, work)
                stream.write(json.dumps(result, sort_keys=True) + '\n')
                stream.flush()
                trials.append(result)
                if (index + 1) % 50 == 0:
                    print(f'Executed {index + 1}/{len(schedule)} trials', flush=True)
        (args.output / 'prediction-receipts.json').write_text(json.dumps(receipts, indent=2))
        (args.output / 'cost-observations.json').write_text(json.dumps(observations, indent=2))
        report = {
            'kind': 'controlled prepared-repair policy microbenchmark', 'suite': manifest,
            'environment': {'python': platform.python_version(), 'platform': platform.platform()},
            'seeds': args.seeds, 'policies': summarize(trials),
            'paired_comparisons': paired_comparisons(trials),
            'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'setup_costs': {
                'oracle_prediction_executions': len(receipts),
                'oracle_prediction_subprocess_seconds': sum(r['seconds'] for r in receipts),
                'learned_cost_training_executions': len(observations),
                'learned_cost_training_subprocess_seconds': sum(r['seconds'] for r in observations),
                'learned_cost_fit_seconds': fit_seconds,
                'learned_success_per_wall_second_including_training':
                    sum(r['resolved'] for r in trials if r['policy'] == 'learned-cost') /
                    (sum(r['wall_seconds'] for r in trials if r['policy'] == 'learned-cost') +
                     sum(r['seconds'] for r in observations) + fit_seconds),
                'note': 'Per-trial policy metrics exclude one-time oracle setup and cost training; this field exposes overhead.',
            },
            'limitations': [
                '18 synthetic microtasks total, 9 held-out tasks in 3 held-out families; not SWE-bench.',
                'Repairs are prepared causal templates, not agent-generated patches; model calls are zero.',
                'Hypotheses and likelihoods are oracle-informed from the three known fault interventions.',
                'Bulk probe p0 repeats 4000 times; the other probes execute once. This intentionally varies diagnostic cost.',
                'Fixed-3 runs three prepared repairs and independent verifiers concurrently; subprocess time sums compute, wall time measures concurrency.',
                'Root UCT is a root-only two-pull proxy over prepared repairs, not agent-mcts, Saplings or full MCTS.',
                'Primary bootstrap clusters by three held-out families; task-level intervals are secondary. Seeds are repeats, not independent tasks.',
                'Training cost regression sees only train-family measured durations and command features.',
                'Small suite, hand-built causes and predicted outcomes do not establish broad agent performance gains.',
            ],
        }
        (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['policies'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
