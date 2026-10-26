"""A small CLI. Inspect first, execute explicitly, accept separately."""
from __future__ import annotations
import argparse
import json
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from . import __version__, agents, git
from .engine import Budget, EngineError, execute, accept, write_json
from .models import PlanError, load, schema, from_agent
from .process import ok


def parser():
    p=argparse.ArgumentParser(prog='forksense',description='Stop guessing. Test the alternatives. Bounded diagnostic experiments for coding agents.')
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor',help='Check local executables and repository state without reading credentials')
    d.add_argument('--repo',default='.')
    d=sub.add_parser('demo',help='One-command controlled demo, no account needed by default')
    d.add_argument('--output',required=True); d.add_argument('--agent',choices=['patch','codex','claude'],default='patch'); d.add_argument('--seconds',type=float,default=180)
    d=sub.add_parser('plan',help='Ask an installed CLI to propose explicit hypotheses and discriminating probes')
    d.add_argument('task'); d.add_argument('--repo',default='.'); d.add_argument('--verify',required=True,help='Verifier command, split as argv without a shell'); d.add_argument('--editable',action='append',required=True,help='Source path allowed to change; repeat as needed'); d.add_argument('--agent',choices=['codex','claude'],default='codex'); d.add_argument('--output',required=True); d.add_argument('--seconds',type=float,default=120); d.add_argument('--trust-repo',action='store_true')
    d=sub.add_parser('inspect',help='Validate a plan and print commands without running them'); d.add_argument('plan')
    d=sub.add_parser('run',help='Execute a reviewed plan on trusted local code')
    d.add_argument('plan'); d.add_argument('--repo',default='.'); d.add_argument('--output',required=True); d.add_argument('--agent',choices=['codex','claude'],default='codex'); d.add_argument('--seconds',type=float,default=180); d.add_argument('--agent-calls',type=int,default=2); d.add_argument('--max-experiments',type=int,default=3); d.add_argument('--token-limit',type=int); d.add_argument('--policy',choices=['adaptive','single','fixed','random','uncertainty'],default='adaptive'); d.add_argument('--seed',type=int,default=0); d.add_argument('--trust-repo',action='store_true'); d.add_argument('--cost-model',help='Optional exploratory cost-model JSON trained with benchmarks')
    d=sub.add_parser('report',help='Render offline HTML from a saved report'); d.add_argument('json'); d.add_argument('--output',required=True)
    d=sub.add_parser('accept',help='Print verified patch; --yes applies it without committing'); d.add_argument('report'); d.add_argument('--repo',default='.'); d.add_argument('--yes',action='store_true')
    return p


def make_plan(args):
    if not args.trust_repo: raise EngineError('planning launches an agent CLI; use --trust-repo only for trusted local code')
    repo=git.root(args.repo); git.require_clean(repo); base=git.head(repo)
    dest=Path(args.output).resolve()
    if dest.exists(): raise EngineError('plan output already exists')
    if dest==repo or repo in dest.parents: raise EngineError('save plan outside target repository')
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='forksense-plan-') as temp:
        schema_path=Path(temp)/'schema.json'; result_path=Path(temp)/'answer.json'
        schema_path.write_text(json.dumps(schema()))
        listed=git.git(repo,'ls-tree','-r','--name-only',base).decode().splitlines()
        sources=[]; source_bytes=0
        for name in listed:
            if len(sources)>=8 or source_bytes>=48000: break
            if not git.allowed(name,args.editable): continue
            content=git.git(repo,'show',f'{base}:{name}')
            if b'\x00' in content: continue
            text=content[:min(12000,48000-source_bytes)].decode('utf-8','replace')
            sources.append({'path':name,'source':text,'truncated':len(content)>len(text.encode())}); source_bytes+=len(text.encode())
        prompt=(f"Inspect this trusted local code repository without changing anything or running code. Task: {args.task}\n"
                f"Return a version 1 ForkSense plan. verify must be exactly {json.dumps(shlex.split(args.verify))}; editable_paths exactly {json.dumps(args.editable)}. "
                "State 2-4 plausible competing causal hypotheses with priors summing to 1. Design 1-4 inexpensive diagnostic commands (argv arrays) to distinguish them before full repair. "
                "Use only existing dependencies. Each probe executes on the original code in its own worktree, with pass meaning exit zero and fail nonzero. "
                "Provide a pass_probability conditional on every hypothesis and a conservative cost_seconds. These are inspectable predictions, not measured confidence. "
                "Do not run tests or execute repository code, install packages, use network, read credentials, or inspect files outside the repository. Read-only file listing and file-reading commands are allowed. "
                f"Use source inspection only. Here are bounded source bytes from the frozen commit: {json.dumps(sources)}\n"
                "Do not include patches or reference solutions. Output only the schema-conforming JSON.")
        with git.worktree(repo,base,Path(temp)/'trees') as wt:
            result=agents.invoke(args.agent,prompt,wt,args.seconds,planning=True,schema_path=schema_path,output_path=result_path)
        if not ok(result) or not result_path.exists():
            raise EngineError('planner did not produce a valid completed result: '+result.get('stderr','')[-1500:])
        try: plan=from_agent(json.loads(result_path.read_text()))
        except (ValueError,TypeError,KeyError) as exc: raise EngineError('invalid planner output: '+str(exc)) from exc
        # The user, not the planner, chooses the test contract and change scope.
        plan['verify']=shlex.split(args.verify); plan['editable_paths']=args.editable
        from .models import validate
        validate(plan)
        write_json(dest,plan)
        write_json(dest.with_suffix('.planning.json'),{'base_commit':base,'agent':args.agent,'duration':result['duration'],'usage':result.get('usage',{}),'source_files':[v['path'] for v in sources],'source_bytes':source_bytes,'note':'Planning cost is additional to run budget; include it in evaluations.'})
    print(f'PLAN  {dest}\nInspect with: forksense inspect {dest}\nNo experiment has run.')


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='doctor':
            print(f'FORKSENSE {__version__} / Python {sys.version.split()[0]}')
            for name in ('git','codex','claude'): print(f'{name}: {shutil.which(name) or "not installed"}')
            try:
                repo=git.root(args.repo); print(f'repo: {repo}\nHEAD: {git.head(repo)}\nclean: {not bool(git.status(repo))}')
            except git.GitError: print('repo: no committed Git repository')
            print('No credential stores inspected. CLI login is handled by each installed agent.')
        elif args.command=='demo':
            from .demo import demo
            result=demo(args.output,args.agent,args.seconds)
            return 0 if result['status']=='verified' else 2
        elif args.command=='plan': make_plan(args)
        elif args.command=='inspect':
            plan=load(args.plan); print(json.dumps(plan,indent=2)); print('\nValidated only. Commands have NOT run. Review predictions, argv, test independence and editable paths.')
        elif args.command=='run':
            model=None
            if args.cost_model:
                from .learning import CostModel
                model=CostModel.load(args.cost_model)
            result=execute(load(args.plan),args.repo,args.output,agent=args.agent,budget=Budget(args.seconds,args.agent_calls,args.max_experiments,args.token_limit),policy=args.policy,seed=args.seed,trusted=args.trust_repo,model=model)
            print(f'REPORT  {Path(args.output).resolve()/"report.html"}')
            return 0 if result['status'] in ('verified','already-passing') else 2
        elif args.command=='report':
            from .report import write_report
            output=Path(args.output)
            if output.exists(): raise EngineError('report output exists; choose a fresh path')
            write_report(json.loads(Path(args.json).read_text()),output); print(output.resolve())
        elif args.command=='accept':
            patch=accept(args.report,args.repo,yes=args.yes)
            print(patch)
            print('APPLIED  Verified source patch applied. Nothing committed.' if args.yes else 'REVIEW ONLY  Add --yes to apply this patch.')
        return 0
    except (EngineError,git.GitError,PlanError,agents.AgentError,OSError,ValueError) as exc:
        print(f'forksense: {exc}',file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
