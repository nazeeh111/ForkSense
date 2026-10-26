"""Small, strict plan contract. A plan is a proposal, never execution authority."""
from __future__ import annotations
import json
import math
import re
from pathlib import Path, PurePosixPath

ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")

class PlanError(ValueError):
    pass

def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise PlanError(f"{label} must be finite and >= {minimum}")
    return float(value)

def argv(value, label):
    if not isinstance(value, list) or not value or len(value) > 100 or not all(isinstance(s, str) and s and '\x00' not in s for s in value):
        raise PlanError(f"{label} must be a nonempty argv array (no shell expansion)")
    return value

def validate(plan):
    if not isinstance(plan, dict) or plan.get('version') != 1:
        raise PlanError('plan.version must be 1')
    if not isinstance(plan.get('task'), str) or not plan['task'].strip():
        raise PlanError('task must be a nonempty string')
    if 'repair_constraints' in plan and (not isinstance(plan['repair_constraints'],str) or len(plan['repair_constraints'])>4000):
        raise PlanError('repair_constraints must be at most 4000 text characters')
    argv(plan.get('verify'), 'verify')
    paths = plan.get('editable_paths')
    if not isinstance(paths, list) or not paths:
        raise PlanError('editable_paths must explicitly name source files or directories')
    for name in paths:
        if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
            raise PlanError('invalid editable path')
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or any(x.startswith('.') for x in p.parts) or name == '.':
            raise PlanError('editable_paths must be relative non-hidden source paths')
    hs = plan.get('hypotheses')
    if not isinstance(hs, list) or not 1 <= len(hs) <= 12:
        raise PlanError('provide 1..12 hypotheses')
    ids = set()
    for h in hs:
        if not isinstance(h, dict) or not ID.fullmatch(str(h.get('id', ''))) or h['id'] in ids:
            raise PlanError('hypothesis IDs must be unique simple identifiers')
        ids.add(h['id'])
        if not isinstance(h.get('description'), str) or not h['description'].strip():
            raise PlanError('hypothesis description required')
        number(h.get('prior'), 'prior', 1e-9)
    es = plan.get('experiments', [])
    if not isinstance(es, list) or len(es) > 32:
        raise PlanError('experiments must be a list of at most 32 probes')
    seen = set()
    for e in es:
        if not isinstance(e, dict) or not ID.fullmatch(str(e.get('id', ''))) or e['id'] in seen:
            raise PlanError('experiment IDs must be unique simple identifiers')
        seen.add(e['id'])
        argv(e.get('command'), 'experiment.command')
        number(e.get('cost_seconds'), 'cost_seconds', .001)
        predictions = e.get('likelihoods')
        if not isinstance(predictions, dict) or set(predictions) != ids:
            raise PlanError('each probe needs likelihoods for every hypothesis')
        for outcomes in predictions.values():
            if not isinstance(outcomes, dict) or set(outcomes) != {'pass', 'fail'}:
                raise PlanError('likelihood outcomes must be pass and fail')
            values = [number(outcomes[x], 'likelihood') for x in ('pass', 'fail')]
            if abs(sum(values) - 1) > 1e-6:
                raise PlanError('likelihoods must sum to 1')
    return plan

def load(path):
    try:
        return validate(json.loads(Path(path).read_text()))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(str(exc)) from exc

def schema():
    """JSON schema used only to constrain an external planner's final answer."""
    def obj(props):
        return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
    hyp = obj({'id':{'type':'string'}, 'description':{'type':'string'}, 'prior':{'type':'number'}})
    # Named rows avoid open-ended dictionaries in strict structured-output schemas.
    pred = obj({'hypothesis':{'type':'string'},'pass_probability':{'type':'number'}})
    exp = obj({'id':{'type':'string'},'label':{'type':'string'},'command':{'type':'array','items':{'type':'string'}},'cost_seconds':{'type':'number'},'predictions':{'type':'array','items':pred}})
    return obj({'version':{'type':'integer'},'task':{'type':'string'},'verify':{'type':'array','items':{'type':'string'}},'editable_paths':{'type':'array','items':{'type':'string'}},'hypotheses':{'type':'array','items':hyp},'experiments':{'type':'array','items':exp}})

def from_agent(value):
    for exp in value.get('experiments', []):
        exp['likelihoods'] = {p['hypothesis']:{'pass':p['pass_probability'],'fail':1-p['pass_probability']} for p in exp.pop('predictions', [])}
    return validate(value)
