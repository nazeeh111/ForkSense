"""Versioned causal debugging microtasks.

Evaluator-only repair catalogs and verifier source are never copied into a task repo.
These tasks test experiment selection, not autonomous coding or SWE-bench performance.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import sys


@dataclass(frozen=True)
class Task:
    id: str
    family: str
    split: str
    ground_truth: str
    hypotheses: tuple[str, ...]
    experiments: tuple[dict, ...]
    source: str
    public_source: str
    verifier_source: str
    repairs: dict[str, tuple[str, str]]

    @property
    def sha256(self) -> str:
        content = {k: v for k, v in self.__dict__.items()}
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


# Independent specifications include multiple unseen edge cases for every cause.
FAMILIES = {
    "cache": {
        "split": "train",
        "source": '''def cache_key(path, params):
    path = path.rstrip('/') or '/'
    pairs = sorted((str(k), str(v)) for k, v in params.items())
    return path, tuple(pairs)
''',
        "mutations": [
            ("path = path.rstrip('/') or '/'", "path = path"),
            ("pairs = sorted((str(k), str(v)) for k, v in params.items())", "pairs = [(str(k), str(v)) for k, v in params.items()]"),
            ("return path, tuple(pairs)", "return path, tuple((k.lower(), v) for k, v in pairs)"),
        ],
        "hypotheses": ("trailing separator normalization", "parameter ordering", "parameter name case"),
        "calls": ["cache_key('/api/', {}) == cache_key('/api', {})", "cache_key('/x', {'b': 2, 'a': 1}) == cache_key('/x', {'a': 1, 'b': 2})", "cache_key('/x', {'A': 1}) != cache_key('/x', {'a': 1})"],
        "public": "assert cache_key('/api/', {'b': 2, 'A': 1}) == ('/api', (('A', '1'), ('b', '2')))\n",
        "verify": """assert cache_key('/', {}) == ('/', ())
assert cache_key('/a///', {'z': 9}) == ('/a', (('z', '9'),))
assert cache_key('/a', {'z': 9, 'b': 0}) == ('/a', (('b', '0'), ('z', '9')))
assert cache_key('/a', {'Token': 'Ab'}) != cache_key('/a', {'token': 'Ab'})
assert cache_key('/a', {'x': 'A'}) != cache_key('/a', {'x': 'a'})
""",
    },
    "pagination": {
        "split": "train",
        "source": '''def page(items, number, size):
    if number < 1 or size < 1:
        raise ValueError('positive page and size required')
    start = (number - 1) * size
    return items[start:start + size]
''',
        "mutations": [
            ("start = (number - 1) * size", "start = number * size"),
            ("return items[start:start + size]", "return items[start:start + size - 1]"),
            ("if number < 1 or size < 1:", "if number < 0 or size < 0:"),
        ],
        "hypotheses": ("page numbering origin", "exclusive slice end", "zero input validation"),
        "calls": ["page([1, 2, 3, 4], 1, 2) == [3, 4]", "len(page(list(range(20)), 1, 4)) == 4", "rejects(lambda: page([1, 2], 0, 1))"],
        "public": "assert page([1, 2, 3, 4], 1, 2) == [1, 2]\nassert rejects(lambda: page([1], 0, 1))\n",
        "verify": """assert page(list(range(11)), 3, 4) == [8, 9, 10]
assert page([5], 1, 1) == [5]
assert page([], 1, 2) == []
assert page([1, 2], 9, 1) == []
assert rejects(lambda: page([1], 0, 1))
assert rejects(lambda: page([1], 1, 0))
assert rejects(lambda: page([1], -1, 2))
""",
    },
    "csv": {
        "split": "train",
        "source": '''import csv
import io

def parse_row(text):
    return next(csv.reader(io.StringIO(text), skipinitialspace=True))
''',
        "mutations": [
            ("return next(csv.reader(io.StringIO(text), skipinitialspace=True))", "return text.strip().split(',')"),
            ("skipinitialspace=True", "skipinitialspace=False"),
            ("return next(csv.reader(io.StringIO(text), skipinitialspace=True))", "return [x.lower() for x in next(csv.reader(io.StringIO(text), skipinitialspace=True))]"),
        ],
        "hypotheses": ("quoted field parsing", "spaces after delimiter", "field case preservation"),
        "calls": ["parse_row('a,\"b,c\"') == ['a', 'b,c']", "parse_row('a, b') == ['a', 'b']", "parse_row('a,B') == ['a', 'B']"],
        "public": "assert parse_row('A, \"B,C\"') == ['A', 'B,C']\n",
        "verify": """assert parse_row('x,"y,z",q') == ['x', 'y,z', 'q']
assert parse_row('left, right') == ['left', 'right']
assert parse_row('MiXeD,UPPER') == ['MiXeD', 'UPPER']
assert parse_row('a,"b""c"') == ['a', 'b"c']
assert parse_row('a,,c') == ['a', '', 'c']
""",
    },
    "retry": {
        "split": "heldout",
        "source": '''def retry(operation, attempts):
    if attempts < 1:
        raise ValueError('positive attempts required')
    for index in range(attempts):
        try:
            return operation()
        except RuntimeError:
            if index == attempts - 1:
                raise
''',
        "mutations": [
            ("range(attempts)", "range(attempts - 1)"),
            ("return operation()", "operation()\n            return None"),
            ("except RuntimeError:", "except Exception:"),
        ],
        "hypotheses": ("attempt limit", "successful return propagation", "exception class filtering"),
        "calls": ["retry(fails_then(2, 'ok'), 3) == 'ok'", "retry(lambda: 'ok', 2) == 'ok'", "count_nonretryable() == 1"],
        "public": "assert retry(fails_then(2, 'ok'), 3) == 'ok'\nassert count_nonretryable() == 1\n",
        "verify": """assert retry(fails_then(0, 47), 1) == 47
assert retry(fails_then(3, 'final'), 4) == 'final'
assert raises_type(lambda: retry(fails_then(9, 1), 3), RuntimeError)
assert raises_type(lambda: retry(lambda: 1, 0), ValueError)
assert count_nonretryable() == 1
""",
    },
    "path": {
        "split": "heldout",
        "source": '''import posixpath

def normalize_path(path):
    path = path.replace('\\\\', '/')
    result = posixpath.normpath(path)
    return result
''',
        "mutations": [
            ("path = path.replace('\\\\', '/')", "path = path"),
            ("result = posixpath.normpath(path)", "result = path.rstrip('/')"),
            ("return result", "return result.lower()"),
        ],
        "hypotheses": ("separator conversion", "dot component collapse", "path case preservation"),
        "calls": ["normalize_path('a\\\\b') == 'a/b'", "normalize_path('a/./b/../c') == 'a/c'", "normalize_path('A/b') == 'A/b'"],
        "public": "assert normalize_path('A\\\\b/./c/..') == 'A/b'\n",
        "verify": """assert normalize_path('Root\\\\child\\\\leaf') == 'Root/child/leaf'
assert normalize_path('a/b/../c') == 'a/c'
assert normalize_path('A/B') == 'A/B'
assert normalize_path('a/./b//') == 'a/b'
assert normalize_path('.') == '.'
assert normalize_path('') == '.'
""",
    },
    "datetime": {
        "split": "heldout",
        "source": '''from datetime import datetime, timezone

def utc_day(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date().isoformat()
''',
        "mutations": [
            ("value.astimezone(timezone.utc).date().isoformat()", "value.date().isoformat()"),
            ("text.replace('Z', '+00:00')", "text.replace('Z', '+00:00').replace('+', '-')"),
            ("return value.astimezone(timezone.utc).date().isoformat()", "return value.astimezone(timezone.utc).strftime('%Y-%d-%m')"),
        ],
        "hypotheses": ("timezone day conversion", "positive offset sign parsing", "month day formatting"),
        "calls": ["utc_day('2026-10-26T00:30:00+02:00') == '2026-10-25'", "utc_day('2026-10-26T23:30:00-02:00') == '2026-10-27'", "utc_day('2026-10-26T12:00:00Z') == '2026-10-26'"],
        "public": "assert utc_day('2026-10-26T00:30:00+02:00') == '2026-10-25'\n",
        "verify": """assert utc_day('2026-03-02T00:01:00+12:00') == '2026-03-01'
assert utc_day('2026-03-02T23:59:00-12:00') == '2026-03-03'
assert utc_day('2026-12-04T12:00:00Z') == '2026-12-04'
assert utc_day('2026-02-03T12:00:00') == '2026-02-03'
""",
    },
}

SUPPORT = '''from subject import *

def raises_type(fn, kind):
    try:
        fn()
    except kind:
        return True
    return False

def rejects(fn):
    return raises_type(fn, ValueError)

def fails_then(count, result):
    state = [0]
    def operation():
        state[0] += 1
        if state[0] <= count:
            raise RuntimeError('transient')
        return result
    return operation

def count_nonretryable():
    state = [0]
    def operation():
        state[0] += 1
        raise ValueError('permanent')
    try:
        retry(operation, 3)
    except ValueError:
        pass
    return state[0]
'''


def all_tasks() -> list[Task]:
    """Return the frozen v1 suite: 18 tasks, three unseen causal families."""
    tasks = []
    for family, spec in FAMILIES.items():
        for truth, (correct, faulty) in enumerate(spec['mutations']):
            assert correct in spec['source'], (family, correct)
            source = spec['source'].replace(correct, faulty, 1)
            probes = tuple({
                'id': f'p{index}',
                'expression': expression,
                'cost': 0.04 if index != 0 else 0.15,
                'repetitions': 1 if index != 0 else 4000,
                'reliability': 0.98,
            } for index, expression in enumerate(spec['calls']))
            tasks.append(Task(
                id=f'{family}-{truth}', family=family, split=spec['split'],
                ground_truth=f'h{truth}', hypotheses=tuple(spec['hypotheses']),
                experiments=probes, source=source,
                public_source=SUPPORT + spec['public'],
                verifier_source=SUPPORT + spec['verify'],
                repairs={f'h{i}': (bad, good) for i, (good, bad) in enumerate(spec['mutations'])},
            ))
    return tasks


def materialize(task: Task, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    (root / 'subject.py').write_text(task.source)
    (root / 'test_public.py').write_text(task.public_source)
    (root / '.gitignore').write_text('__pycache__/\n')


def probe_source(expression: str, repetitions: int = 1) -> str:
    return SUPPORT + '\ntry:\n    for _ in range(' + str(repetitions) + '):\n        outcome = bool(' + expression + ')\n    print("pass" if outcome else "fail")\nexcept Exception:\n    print("fail")\n'


def frozen_manifest() -> dict:
    return {'version': 1, 'tasks': [{'id': t.id, 'family': t.family, 'split': t.split, 'sha256': t.sha256} for t in all_tasks()]}


if __name__ == '__main__':
    print(json.dumps(frozen_manifest(), indent=2))
