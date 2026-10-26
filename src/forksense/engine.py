"""Observe, probe, repair, independently verify, retain evidence, stop."""
from __future__ import annotations
import json
import shutil
import time
import math
import contextlib
import uuid
from pathlib import Path
from . import agents
from . import git
from .models import validate
from .policy import normalize, rank, update
from .process import run, ok

class EngineError(RuntimeError): pass

class Budget:
    def __init__(self, seconds=180, agent_calls=2, max_experiments=3, token_limit=None):
        if not math.isfinite(seconds) or seconds<=0 or not isinstance(agent_calls,int) or agent_calls<0 or not isinstance(max_experiments,int) or max_experiments<0 or (token_limit is not None and (not isinstance(token_limit,int) or token_limit<=0)):
            raise EngineError('budgets must be positive (calls and probes may be zero)')
        self.seconds=seconds; self.agent_calls=agent_calls; self.max_experiments=max_experiments
        self.token_limit=token_limit; self.started=time.monotonic(); self.calls=0; self.tokens=0
    def remaining(self): return max(0.,self.seconds-(time.monotonic()-self.started))
    def can_call(self): return self.calls<self.agent_calls and self.remaining()>0 and (self.token_limit is None or self.tokens<self.token_limit)


def write_json(path,value):
    dest=Path(path); temp=dest.with_suffix('.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n'); temp.replace(dest)

def execute(plan, repo, output, *, agent='codex', budget=None, policy='adaptive', seed=0, trusted=False, candidate_patches=None, model=None, progress=print):
    validate(plan)
    if not trusted: raise EngineError('execution requires --trust-repo; worktrees are not security sandboxes')
    repo=git.root(repo); git.require_clean(repo); base=git.head(repo)
    output=Path(output).resolve()
    if output == repo or repo in output.parents:
        raise EngineError('reports must be outside the source repository to keep its checkout clean')
    if output.exists(): raise EngineError('output directory already exists; use a fresh path')
    output.mkdir(parents=True)
    budget=budget or Budget()
    p=normalize({h['id']:h['prior'] for h in plan['hypotheses']})
    report={'schema_version':1,'run_id':str(uuid.uuid4())[:8],'task':plan['task'],'status':'running','reason':'','base_commit':base,'repo':str(repo),'policy':policy,'budgets':{'seconds':budget.seconds,'agent_calls':budget.agent_calls,'max_experiments':budget.max_experiments,'token_limit_soft':budget.token_limit},'plan':plan,'hypotheses':[dict(h,posterior=p[h['id']]) for h in plan['hypotheses']],'steps':[],'selected':None,'warnings':['Trusted local execution only. Git worktrees are not security sandboxes.','Predicted likelihoods are assumptions; test execution determines verification.'],'totals':{'agent_calls':0,'input_tokens':0,'output_tokens':0,'cached_input_tokens':0}}
    # Files explicitly referenced by external argv are copied before the first
    # execution. Interpreters and the installed dependency environment remain
    # trusted host tools, not a hermetic container image.
    verifier=list(plan['verify']); frozen=[]; protected_verifier_paths=set()
    for i,arg in enumerate(verifier):
        # Ordinary PATH executables and binary interpreters are trusted host tools.
        if i==0 and '/' not in arg and '\\' not in arg: continue
        path_part,sep,node=arg.partition('::')
        try:
            path=Path(path_part)
            path=(repo/path).resolve() if not path.is_absolute() else path.resolve()
            if path.is_dir() and repo not in path.parents and path!=repo:
                raise EngineError('external verifier directories are unsupported; use committed tests or explicit self-contained verifier files')
            if not path.is_file(): continue
            if i==0:
                with path.open('rb') as stream: is_script=stream.read(2)==b'#!'
                if not is_script: continue
        except (OSError,ValueError):
            continue
        if repo in path.parents:
            rel=path.relative_to(repo).as_posix(); protected_verifier_paths.add(rel)
            if Path(path_part).is_absolute(): verifier[i]=('./' if i==0 else '')+rel+(sep+node if sep else '')
        else:
            folder=output/'verifier'; folder.mkdir(exist_ok=True)
            target=folder/f'{i}-{path.name}'; shutil.copy2(path,target)
            frozen.append({'source':str(path),'snapshot':str(target),'sha256':git.digest(target.read_bytes())})
            # Preserve original argv location and sibling discovery semantics.
    report['verifier_files']=frozen
    report['effective_verify']=verifier
    def verify_at(cwd):
        def intact(): return all(all(Path(f[k]).is_file() and git.digest(Path(f[k]).read_bytes())==f['sha256'] for k in ('source','snapshot')) for f in frozen)
        if not intact():
            return {'command':verifier,'returncode':None,'duration':0.,'stdout':'','stderr':'Frozen verifier bytes changed','error':'verifier_drift'}
        result=run(verifier,cwd,budget.remaining())
        result.pop('stdout_tail',None)
        if not intact(): result['error']='verifier_drift'
        return result
    if budget.token_limit:
        report['warnings'].append('Token limit stops subsequent calls after reported usage; it cannot cap an in-flight CLI turn.')
    def save():
        for h in report['hypotheses']: h['posterior']=p[h['id']]
        report['totals']['duration']=time.monotonic()-budget.started
        write_json(output/'report.json',report)
    def finish(status,reason):
        report['status']=status; report['reason']=reason
        for unfinished in report['steps']:
            if unfinished.get('status')=='running':
                unfinished['status']='inconclusive'; unfinished['error']=reason
        if git.head(repo)!=base or git.status(repo):
            report['status']='unsafe'; report['reason']='source checkout changed during execution; do not apply this result'
        save()
        from .report import write_report
        write_report(report,output/'report.html')
        progress(f"{report['status'].upper()}  {report['reason']}")
        return report
    @contextlib.contextmanager
    def repair_tree(step):
        with git.worktree(repo,base,output/'worktrees',preserve=lambda:step.get('preserve_worktree',False)) as wt:
            try:
                yield wt
            finally:
                # Even exceptional failures/interruptions preserve attempted bytes.
                try:
                    raw_patch,raw_files,_=git.snapshot_patch(wt,base)
                    artifact=output/f'{step["id"]}-attempt.patch'
                    artifact.write_bytes(raw_patch)
                    step['attempt_patch_path']=artifact.name; step['attempt_files']=raw_files
                except (git.GitError,OSError,UnicodeError) as exc:
                    step['artifact_note']=str(exc)
                    if 'no source changes' not in str(exc):
                        step['preserve_worktree']=True
                        step['worktree_path']=str(wt)
                        report['warnings'].append('Candidate worktree retained because a complete diff could not be captured: '+str(wt))
                save()
    save()
    try:
        # Baseline always has the exact same frozen commit and verifier as candidates.
        with git.worktree(repo,base,output/'worktrees') as wt:
            progress('OBSERVE  Run the original verifier on the base commit')
            baseline=verify_at(wt)
        report['baseline']=baseline; save()
        if ok(baseline): return finish('already-passing','The supplied verifier already passes. No repair needed under this test contract.')
        if baseline.get('returncode') is None or baseline.get('error'):
            return finish('inconclusive','Baseline verifier could not complete; fix the verifier or budget first.')
        progress('UNCERTAINTY  '+', '.join(f'{h}: {v:.0%}' for h,v in p.items()))
        remaining=list(plan.get('experiments',[]))
        if policy not in ('single','fixed'):
            for index in range(budget.max_experiments):
                if budget.remaining()<=0 or not remaining: break
                rows=rank(p,remaining,policy,seed+index,model)
                choice=rows[0]; experiment=choice['experiment']
                if policy=='adaptive' and (max(p.values())>=.9 or choice['information_gain']<.02):
                    progress('STOP PROBING  Additional probes have little predicted value'); break
                if choice['cost_seconds']>=budget.remaining()/2:
                    progress('STOP PROBING  Preserve the remaining budget for repair and verification'); break
                remaining=[e for e in remaining if e['id']!=experiment['id']]
                progress(f"PROBE  {experiment.get('label',experiment['id'])}  ({choice['information_gain']:.3f} expected bits / {choice['cost_seconds']:.3g}s)")
                with git.worktree(repo,base,output/'worktrees') as wt:
                    result=run(experiment['command'],wt,min(budget.remaining(),max(5.,choice['cost_seconds']*4)))
                result.pop('stdout_tail',None)
                outcome='error' if result.get('error') or result['returncode'] is None else ('pass' if ok(result) else 'fail')
                step={'id':experiment['id'],'kind':'probe','label':experiment.get('label',experiment['id']),**{k:choice[k] for k in ('score','information_gain','cost_seconds')},**result,'outcome':outcome,'status':'observed' if outcome!='error' else 'inconclusive'}
                if outcome!='error':
                    try: p=update(p,experiment,outcome)
                    except ValueError:
                        report['warnings'].append(f"Probe {experiment['id']} contradicted all predictions; retain prior and treat the plan as misspecified.")
                        step['status']='contradiction'
                step['posterior']=dict(p); report['steps'].append(step); save()
                progress('EVIDENCE  '+outcome+' → '+', '.join(f'{h}: {v:.0%}' for h,v in p.items()))
        tried=set()
        while budget.remaining()>0:
            candidates=[h for h in plan['hypotheses'] if h['id'] not in tried and p[h['id']]>0]
            if not candidates: break
            # Failed verification excludes the attempted implementation, not its
            # causal hypothesis. Keep posterior intact and move to the next cause.
            hypothesis=max(candidates,key=lambda h:p[h['id']]); hid=hypothesis['id']; tried.add(hid)
            if policy=='single' and len(tried)>1: break
            patch_source=(candidate_patches or {}).get(hid)
            if not patch_source and not budget.can_call(): break
            progress(f"FORK  Repair hypothesis {hid}: {hypothesis['description']}")
            step={'id':f'repair-{hid}','kind':'repair','hypothesis':hid,'label':hypothesis['description'],'posterior':dict(p),'status':'running'}
            report['steps'].append(step); save()
            with repair_tree(step) as wt:
                if patch_source:
                    patch=Path(patch_source).read_bytes()
                    supplied=output/f'{step["id"]}-input.patch'; supplied.write_bytes(patch)
                    step['input_patch_path']=supplied.name
                    git.apply_bytes(wt,patch)
                    result={'returncode':0,'duration':0.,'stdout':'User-supplied candidate patch; no agent invoked.','stderr':'','command':[]}
                else:
                    budget.calls+=1; report['totals']['agent_calls']+=1
                    prompt=(f"Fix this trusted local repository. Task: {plan['task']}\n"
                            f"Investigate this specific hypothesis: {hypothesis['description']}\n"
                            f"Observed diagnostics: {json.dumps([{'id':s['id'],'outcome':s.get('outcome'),'stdout':s.get('stdout','')[:4000]} for s in report['steps']])}\n"
                            f"Edit ONLY these source paths: {json.dumps(plan['editable_paths'])}. Preserve all tests and configuration. "
                            "Do not commit, push, use network, inspect credentials, install packages, change Git state, or modify other worktrees. "
                            f"Verifier command (argv): {json.dumps(plan['verify'])}. Implement a real fix, not a test-specific workaround.\n"
                            f"{plan.get('repair_constraints','')}\n")
                    result=agents.invoke(agent,prompt,wt,budget.remaining()*.75)
                    for k in ('input_tokens','output_tokens','cached_input_tokens'):
                        value=result.get('usage',{}).get(k)
                        previous=report['totals'][k]
                        report['totals'][k]=previous+value if value is not None and previous is not None else None
                    known=all(report['totals'][k] is not None for k in ('input_tokens','output_tokens'))
                    budget.tokens=sum(report['totals'][k] for k in ('input_tokens','output_tokens')) if known else float('inf')
                    if not known: report['warnings'].append('Agent token usage unavailable; it is not zero. A soft token cap prevents subsequent calls when usage is unknown.')
                step.update(result)
                if ok(result):
                    try:
                        patch,files=git.extract_patch(wt,base,plan['editable_paths'])
                        # Test/fixture edits cannot silently weaken the original judge.
                        if any(_is_test_path(n) or n in protected_verifier_paths for n in files): raise git.GitError('candidate modified test/fixture/verifier paths')
                        patch_file=output/f'{step["id"]}.patch'; patch_file.write_bytes(patch)
                        step.update({'patch_path':patch_file.name,'sha256':git.digest(patch),'files':files,'diff':patch.decode('utf-8','replace')})
                    except git.GitError as exc:
                        step['status']='rejected'; step['error']=str(exc)
                else:
                    step['status']='inconclusive'
            if step.get('patch_path'):
                progress('VERIFY  Apply source patch to a fresh base worktree with the original verifier')
                with git.worktree(repo,base,output/'worktrees') as judge:
                    git.apply_bytes(judge,patch)
                    verification=verify_at(judge)
                step['verification']=verification
                step['status']='verified' if ok(verification) else ('inconclusive' if verification.get('error') else 'failed')
                if ok(verification):
                    report['selected']={k:step[k] for k in ('id','patch_path','sha256','files','verification')}
            save()
            if report['selected']: return finish('verified','A source patch passed the supplied independent verifier. Review it before accepting.')
        return finish('inconclusive','No patch passed verification within the budget. The active checkout is unchanged.')
    except (git.GitError,agents.AgentError,OSError) as exc:
        return finish('inconclusive',str(exc))
    except KeyboardInterrupt:
        return finish('interrupted','Interrupted; completed evidence and patches retained.')

def _is_test_path(name):
    p=Path(name)
    return any(s.lower() in ('test','tests','fixtures','__tests__') for s in p.parts) or p.name.startswith(('test_','conftest.')) or p.name.endswith(('_test.py','.test.js','.spec.js','.test.ts','.spec.ts'))

def accept(report_path, repo, *, yes=False):
    """Review-only by default. Never commits; refuses drift or altered patch bytes."""
    report_path=Path(report_path).resolve(); report=json.loads(report_path.read_text())
    if report.get('status')!='verified' or not report.get('selected'): raise EngineError('only a verified report can be accepted')
    repo=git.root(repo); git.require_clean(repo)
    if git.head(repo)!=report['base_commit']: raise EngineError('HEAD differs from verified base; rerun experiments')
    selected=report['selected']; patch_path=(report_path.parent/selected['patch_path']).resolve()
    if patch_path.parent!=report_path.parent: raise EngineError('patch path must be beside report')
    patch=patch_path.read_bytes()
    if git.digest(patch)!=selected['sha256']: raise EngineError('patch hash differs from verified bytes')
    git.git(repo,'apply','--check','-',input_bytes=patch)
    if yes: git.apply_bytes(repo,patch)
    return patch.decode('utf-8','replace')
