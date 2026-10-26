"""Small opt-in cost model fitted only to measured experiment durations.

This is regularized log-linear regression, not a learned correctness estimator.
Unseen repository costs and model calls can differ substantially.
"""
from __future__ import annotations
import json
import math
from pathlib import Path


def features(experiment, hypothesis_count):
    command_chars = len(' '.join(experiment.get('command', [])))
    return [1.0, math.log(max(0.001, experiment['cost_seconds'])),
            math.log1p(command_chars / 1000), math.log1p(hypothesis_count)]


def solve(matrix, target):
    """Pivoted Gaussian elimination for this fixed, tiny regularized system."""
    rows = [list(row) + [value] for row, value in zip(matrix, target)]
    n = len(rows)
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(rows[i][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        if abs(scale) < 1e-12:
            raise ValueError('cost model is singular')
        rows[col] = [x / scale for x in rows[col]]
        for i in range(n):
            if i != col:
                factor = rows[i][col]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[col])]
    return [row[-1] for row in rows]


class CostModel:
    version = 1

    def __init__(self, coefficients, provenance=None):
        if len(coefficients) != 4 or not all(math.isfinite(c) for c in coefficients):
            raise ValueError('expected four finite cost coefficients')
        self.coefficients = list(coefficients)
        self.provenance = provenance or {}

    def predict(self, experiment, hypothesis_count):
        log_cost = sum(a * b for a, b in zip(self.coefficients, features(experiment, hypothesis_count)))
        return max(0.001, math.exp(max(-7, min(14, log_cost))))

    def as_dict(self):
        return {'version': self.version, 'kind': 'log-linear-observed-cost',
                'coefficients': self.coefficients, 'provenance': self.provenance}

    def save(self, path):
        Path(path).write_text(json.dumps(self.as_dict(), indent=2) + '\n')

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data.get('version') != 1 or data.get('kind') != 'log-linear-observed-cost':
            raise ValueError('unsupported cost model')
        return cls(data['coefficients'], data.get('provenance'))

    @classmethod
    def fit(cls, observations, provenance=None, ridge=0.1):
        """Rows: {experiment, hypothesis_count, seconds}; no outcome labels used."""
        if len(observations) < 12:
            raise ValueError('need at least 12 measured costs to fit the model')
        matrix = [[ridge if i == j else 0.0 for j in range(4)] for i in range(4)]
        target = [0.0] * 4
        for row in observations:
            seconds = float(row['seconds'])
            if seconds <= 0 or not math.isfinite(seconds):
                raise ValueError('training durations must be positive and finite')
            x = features(row['experiment'], row['hypothesis_count'])
            y = math.log(seconds)
            for i in range(4):
                target[i] += x[i] * y
                for j in range(4):
                    matrix[i][j] += x[i] * x[j]
        provenance = dict(provenance or {}, observations=len(observations), ridge=ridge,
                          target='log measured subprocess wall seconds', outcome_labels_used=False)
        return cls(solve(matrix, target), provenance)
