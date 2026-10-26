"""Bench fixture and evaluator checks, separate from product test assertions."""
from pathlib import Path
import json
import tempfile
import unittest
import sys
from unittest.mock import patch
import threading

from benchmarks.tasks import all_tasks, FAMILIES, frozen_manifest, materialize, probe_source
from benchmarks.run import execute, calibrate_predictions, make_experiments, trial
from forksense.learning import CostModel


class FixtureTests(unittest.TestCase):
    def test_frozen_hashes(self):
        expected = json.loads((Path(__file__).parent / 'tasks-v1.json').read_text())
        self.assertEqual(expected, frozen_manifest())

    def test_causal_repairs_and_independent_verification(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for task in all_tasks():
                path = root / task.id
                materialize(task, path)
                self.assertNotEqual(execute(['python3', '-B', '-c', task.public_source], path)['returncode'], 0, task.id)
                self.assertNotEqual(execute(['python3', '-B', '-c', task.verifier_source], path)['returncode'], 0, task.id)
                successes = []
                for hypothesis, (old, new) in task.repairs.items():
                    (path / 'subject.py').write_text(task.source.replace(old, new, 1))
                    result = execute(['python3', '-B', '-c', task.verifier_source], path)
                    if result['returncode'] == 0:
                        successes.append(hypothesis)
                self.assertEqual(successes, [task.ground_truth], task.id)
                (path / 'subject.py').write_text(FAMILIES[task.family]['source'])
                self.assertEqual(execute(['python3', '-B', '-c', task.verifier_source], path)['returncode'], 0, task.id)

    def test_probe_vectors_distinguish_faults(self):
        with tempfile.TemporaryDirectory() as d:
            predictions, _ = calibrate_predictions(all_tasks(), Path(d))
            for family, probes in predictions.items():
                vectors = [tuple(probes[f'p{i}'][h] for i in range(3)) for h in range(3)]
                self.assertEqual(len(set(vectors)), 3, (family, vectors))


    def test_timeout_and_missing_command_are_failures(self):
        with tempfile.TemporaryDirectory() as d:
            result = execute([sys.executable, '-c', 'import time; time.sleep(1)'], Path(d), timeout=.02)
            self.assertEqual(result['status'], 'timeout')
            self.assertIsNone(result['returncode'])
            missing = execute(['/nonexistent/forksense-benchmark-command'], Path(d))
            self.assertEqual(missing['status'], 'error')
            self.assertIsNone(missing['returncode'])

    def test_fixed_three_runs_concurrently(self):
        barrier = threading.Barrier(3, timeout=5)
        def verify(task, hypothesis, root, verifier, attempt):
            barrier.wait()
            return {'returncode': 0 if hypothesis == task.ground_truth else 1,
                    'hypothesis': hypothesis, 'seconds': .01, 'status': 'completed'}
        with tempfile.TemporaryDirectory() as d:
            task = all_tasks()[0]
            with patch('benchmarks.run.repair_and_verify', side_effect=verify):
                result = trial(task, 'fixed-3', 0, [], None, Path(d))
            self.assertTrue(result['resolved'])
            self.assertEqual(result['command_calls'], 3)
            self.assertEqual(result['prepared_repair_calls'], 3)

    def test_cost_model_fit_and_roundtrip(self):
        observations = []
        for count in range(1, 6):
            for cost in (.02, .05, .2):
                observations.append({'experiment': {'cost_seconds': cost, 'command': ['a' * count]},
                                     'hypothesis_count': count, 'seconds': cost * 2})
        model = CostModel.fit(observations, {'training_families': ['example']})
        cheap = model.predict({'cost_seconds': .02, 'command': ['a']}, 3)
        costly = model.predict({'cost_seconds': .2, 'command': ['a']}, 3)
        self.assertLess(cheap, costly)
        self.assertFalse(model.provenance['outcome_labels_used'])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'model.json'
            model.save(path)
            self.assertEqual(CostModel.load(path).as_dict(), model.as_dict())


if __name__ == '__main__':
    unittest.main()
