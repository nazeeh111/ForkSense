"""Cost-sensitive experimental design over explicit, uncalibrated predictions.

Entropy and Bayes updates are mechanics, not a probability that a fix is correct.
"""
from __future__ import annotations
import math
import random

def normalize(weights):
    total = sum(weights.values())
    if total <= 0:
        raise ValueError('observation has zero likelihood under all hypotheses')
    return {k:v/total for k,v in weights.items()}

def entropy(p):
    return -sum(v * math.log2(v) for v in p.values() if v > 0)

def update(p, experiment, outcome):
    return normalize({h:p[h]*experiment['likelihoods'][h][outcome] for h in p})

def information_gain(p, experiment):
    residual = 0.
    for o in ('pass','fail'):
        weights = {h:p[h]*experiment['likelihoods'][h][o] for h in p}
        mass = sum(weights.values())
        if mass:
            residual += mass * entropy(normalize(weights))
    return max(0., entropy(p)-residual)

def rank(p, experiments, policy='adaptive', seed=0, model=None):
    rows=[]
    rng=random.Random(seed)
    for e in experiments:
        gain=information_gain(p,e)
        cost=e['cost_seconds']
        if model:
            # Cost only, trained on observed durations. No outcome/test labels.
            cost=max(.001, model.predict(e, len(p)))
        score=gain/cost
        if policy == 'random': score=rng.random()
        elif policy == 'uncertainty': score=gain
        rows.append({'experiment':e,'information_gain':gain,'cost_seconds':cost,'score':score})
    return sorted(rows,key=lambda r:(-r['score'],r['experiment']['id']))
