import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from forksense import git
from forksense.agents import command
from forksense.demo import create
from forksense.engine import execute, Budget, accept, EngineError
from forksense.models import validate, PlanError
from forksense.policy import entropy, information_gain, update, rank
from forksense.process import run

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.repo,self.plan,self.patches=create(self.root/'demo')
    def tearDown(self): self.temp.cleanup()
    def execute(self,**kw):
        return execute(self.plan,self.repo,self.root/'run',trusted=True,candidate_patches=self.patches,progress=lambda _:None,**kw)
    def test_evidence_to_verified_apply_preserves_head(self):
        before=(self.repo/'checkout.py').read_bytes(); base=git.head(self.repo)
        result=self.execute()
        self.assertEqual(result['status'],'verified')
        self.assertEqual(result['steps'][0]['outcome'],'fail')
        self.assertEqual(result['hypotheses'][0]['posterior'],1)
        self.assertEqual((self.repo/'checkout.py').read_bytes(),before)
        self.assertFalse(git.status(self.repo))
        self.assertIn('discount, tax',accept(self.root/'run/report.json',self.repo))
        self.assertEqual((self.repo/'checkout.py').read_bytes(),before)
        accept(self.root/'run/report.json',self.repo,yes=True)
        self.assertEqual(git.head(self.repo),base)
        self.assertEqual(run(self.plan['verify'],self.repo,10)['returncode'],0)
    def test_untrusted_never_executes(self):
        with self.assertRaises(EngineError): execute(self.plan,self.repo,self.root/'run')
        self.assertFalse((self.root/'run').exists())
    def test_dirty_untracked_never_overwritten(self):
        (self.repo/'keep.txt').write_text('original')
        with self.assertRaises(git.GitError): self.execute()
        self.assertEqual((self.repo/'keep.txt').read_text(),'original')
    def test_candidate_cannot_modify_verifier(self):
        import difflib
        before=(self.repo/'README.md').read_text()
        patch=''.join(difflib.unified_diff(before.splitlines(True),['tampered\n'],fromfile='a/README.md',tofile='b/README.md'))
        p=self.root/'bad.patch'; p.write_text(patch)
        self.patches={h['id']:str(p) for h in self.plan['hypotheses']}
        result=self.execute()
        self.assertIsNone(result['selected'])
        self.assertTrue(all(s['status']=='rejected' for s in result['steps'] if s['kind']=='repair'))
    def test_apply_rejects_changed_patch(self):
        result=self.execute()
        (self.root/'run'/result['selected']['patch_path']).write_text('modified')
        with self.assertRaises(EngineError): accept(self.root/'run/report.json',self.repo,yes=True)
        self.assertFalse(git.status(self.repo))
    def test_apply_rejects_head_drift(self):
        self.execute()
        (self.repo/'README.md').write_text('new base\n')
        git.git(self.repo,'add','README.md')
        git.git(self.repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','new')
        with self.assertRaises(EngineError): accept(self.root/'run/report.json',self.repo,yes=True)
    def test_apply_refuses_dirty_files(self):
        self.execute(); (self.repo/'checkout.py').write_text('unrelated')
        with self.assertRaises(git.GitError): accept(self.root/'run/report.json',self.repo,yes=True)
        self.assertEqual((self.repo/'checkout.py').read_text(),'unrelated')
    def test_already_passing_runs_no_agent(self):
        git.apply_bytes(self.repo,Path(self.patches['tax-key']).read_bytes())
        git.git(self.repo,'add','checkout.py'); git.git(self.repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixed')
        result=self.execute()
        self.assertEqual(result['status'],'already-passing'); self.assertEqual(result['steps'],[])
    def test_inconclusive_when_verifier_invalid(self):
        self.plan['verify']=['does-not-exist-forksense']
        result=self.execute()
        self.assertEqual(result['status'],'inconclusive'); self.assertEqual(result['steps'],[])
    def test_timeout_never_passes(self):
        self.plan['verify']=[sys.executable,'-c','import time; time.sleep(20)']
        result=self.execute(budget=Budget(.2,0,0))
        self.assertEqual(result['status'],'inconclusive'); self.assertTrue(result['baseline']['timed_out'])
    def test_output_cannot_pollute_source(self):
        with self.assertRaises(EngineError): execute(self.plan,self.repo,self.repo/'out',trusted=True)
    def test_validation_rejects_traversal_nonfinite_and_shell(self):
        for field,value in [('editable_paths',['../other']),('verify','python -m unittest')]:
            p=copy.deepcopy(self.plan); p[field]=value
            with self.assertRaises(PlanError): validate(p)
        p=copy.deepcopy(self.plan); p['hypotheses'][0]['prior']=float('nan')
        with self.assertRaises(PlanError): validate(p)
    def test_policy_bayes_and_cost_rank(self):
        p={'a':.5,'b':.5}
        def e(name,cost): return {'id':name,'cost_seconds':cost,'likelihoods':{'a':{'pass':1.,'fail':0.},'b':{'pass':0.,'fail':1.}}}
        self.assertEqual(entropy(p),1)
        self.assertEqual(information_gain(p,e('cheap',1)),1)
        self.assertEqual(update(p,e('cheap',1),'pass'),{'a':1.,'b':0.})
        self.assertEqual(rank(p,[e('slow',10),e('cheap',1)])[0]['experiment']['id'],'cheap')
    def test_spawn_error_and_secrets_not_forwarded(self):
        result=run(['missing-forksense-binary'],self.repo,1)
        self.assertIsNone(result['returncode'])
        os.environ['FORKSENSE_TEST_SECRET']='must-not-propagate'
        try:
            r=run([sys.executable,'-c','import os; print(os.getenv("FORKSENSE_TEST_SECRET", "absent"))'],self.repo,10)
            self.assertEqual(r['stdout'].strip(),'absent')
        finally: del os.environ['FORKSENSE_TEST_SECRET']
    def test_cli_adapters_preserve_permissions(self):
        args=command('codex','x'); self.assertIn('workspace-write',args); self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',args)
        args=command('claude','x'); self.assertNotIn('--dangerously-skip-permissions',args); self.assertNotIn('--bare',args)
    def test_report_does_not_execute_log_html(self):
        from forksense.report import write_report
        dest=self.root/'evil.html'
        write_report({'task':'</script><script>alert(1)</script>','steps':[{'stdout':'<img src=x onerror=alert(1)>'}]},dest)
        data=dest.read_text(); self.assertNotIn('</script><script>alert(1)',data); self.assertNotIn('<img src=x',data)

if __name__=='__main__': unittest.main()

class ReviewRegressionTests(unittest.TestCase):
    def test_external_verifier_is_frozen_before_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); repo,plan,patches=create(root/'fixture')
            plan['hypotheses']=[h for h in plan['hypotheses'] if h['id']=='discount-key']
            plan['experiments']=[]
            def progress(message):
                if message.startswith('VERIFY'):
                    (root/'fixture/verify_checkout.py').write_text('raise SystemExit(0)\n')
            result=execute(plan,repo,root/'run',trusted=True,candidate_patches=patches,progress=progress)
            self.assertEqual(result['status'],'inconclusive')
            self.assertIsNone(result['selected'])
            self.assertNotEqual(result['steps'][0]['verification']['returncode'],0)
            self.assertTrue(result['verifier_files'])
    def test_frozen_copy_tampering_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); repo,plan,patches=create(root/'fixture')
            def progress(message):
                if message.startswith('VERIFY'):
                    next((root/'run/verifier').iterdir()).write_text('raise SystemExit(0)\n')
            result=execute(plan,repo,root/'run',trusted=True,candidate_patches=patches,progress=progress)
            self.assertIsNone(result['selected'])
            self.assertEqual(result['steps'][-1]['verification']['error'],'verifier_drift')
    def test_partial_agent_failure_retains_diff(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); repo,plan,_=create(root/'fixture')
            def failed(name,prompt,cwd,*args,**kwargs):
                (cwd/'checkout.py').write_text('partial implementation\n')
                return {'returncode':1,'duration':.01,'error':'timeout','stdout':'partial','stderr':'','usage':{'input_tokens':None,'output_tokens':None,'cached_input_tokens':None}}
            with patch('forksense.agents.invoke',side_effect=failed):
                result=execute(plan,repo,root/'run',trusted=True,budget=Budget(30,1,0),progress=lambda _:None)
            self.assertEqual(result['status'],'inconclusive')
            path=root/'run'/result['steps'][0]['attempt_patch_path']
            self.assertIn('partial implementation',path.read_text())
            self.assertIsNone(result['totals']['input_tokens'])
    def test_report_does_not_call_output_limit_passed(self):
        from forksense.report import _verification
        self.assertIn('Inconclusive',_verification({'returncode':0,'error':'output_limit'}))
        self.assertNotIn('>Passed<',_verification({'returncode':0,'error':'output_limit'}))
    def test_missing_usage_is_unknown(self):
        from forksense.agents import usage
        self.assertIsNone(usage('{"type":"turn.failed"}')["input_tokens"])

class VerifierLocationTests(unittest.TestCase):
    def test_external_verifier_keeps_sibling_discovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); repo,plan,patches=create(root/'fixture')
            (root/'fixture/sibling.py').write_text('raise AssertionError("external sibling executed")\n')
            verifier=root/'fixture/verify_checkout.py'
            verifier.write_text('from pathlib import Path\nexec((Path(__file__).parent/"sibling.py").read_text())\n')
            result=execute(plan,repo,root/'run',trusted=True,candidate_patches=patches,progress=lambda _:None)
            self.assertEqual(result['status'],'inconclusive')
            self.assertIn('external sibling executed',result['baseline']['stderr'])
            self.assertIsNone(result['selected'])

class AttemptExceptionTests(unittest.TestCase):
    def test_invalid_input_patch_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); repo,plan,patches=create(root/'fixture')
            invalid=root/'invalid.patch'; invalid.write_text('not a patch\n')
            patches={h['id']:str(invalid) for h in plan['hypotheses']}
            result=execute(plan,repo,root/'run',trusted=True,candidate_patches=patches,progress=lambda _:None)
            repair=[s for s in result['steps'] if s['kind']=='repair'][0]
            self.assertEqual(repair['status'],'inconclusive')
            self.assertIn('error',repair)
            self.assertEqual((root/'run'/repair['input_patch_path']).read_text(),'not a patch\n')
    def test_agent_interrupt_retains_partial_source(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); repo,plan,_=create(root/'fixture')
            def interrupted(name,prompt,cwd,*args,**kwargs):
                (cwd/'checkout.py').write_text('partial before interrupt\n')
                raise KeyboardInterrupt()
            with patch('forksense.agents.invoke',side_effect=interrupted):
                result=execute(plan,repo,root/'run',trusted=True,budget=Budget(30,1,0),progress=lambda _:None)
            self.assertEqual(result['status'],'interrupted')
            step=result['steps'][0]
            self.assertIn('partial before interrupt',(root/'run'/step['attempt_patch_path']).read_text())

class VerifierEntrypointTests(unittest.TestCase):
    @unittest.skipIf(os.name=='nt','POSIX executable script')
    def test_direct_external_script_is_hashed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,plan,patches=create(root/'fixture')
            script=root/'check.sh';script.write_text('#!/bin/sh\nexit 1\n');script.chmod(0o700)
            plan['verify']=[str(script)]
            def progress(message):
                if message.startswith('VERIFY'): script.write_text('#!/bin/sh\nexit 0\n')
            result=execute(plan,repo,root/'run',trusted=True,candidate_patches=patches,progress=progress)
            self.assertEqual(result['status'],'inconclusive');self.assertTrue(result['verifier_files'])
    def test_source_named_verifier_cannot_be_modified(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,plan,_=create(root/'fixture')
            (repo/'judge.py').write_text('raise SystemExit(1)\n')
            git.git(repo,'add','judge.py');git.git(repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','judge')
            plan['verify']=[sys.executable,str(repo/'judge.py')];plan['editable_paths'].append('judge.py');plan['experiments']=[]
            def fake(name,prompt,cwd,*args,**kwargs):
                (cwd/'judge.py').write_text('raise SystemExit(0)\n')
                return {'returncode':0,'duration':.01,'stdout':'','stderr':'','usage':{'input_tokens':1,'output_tokens':1,'cached_input_tokens':0}}
            with patch('forksense.agents.invoke',side_effect=fake):
                result=execute(plan,repo,root/'run',trusted=True,budget=Budget(30,1,0),progress=lambda _:None)
            self.assertIsNone(result['selected']);self.assertEqual(result['steps'][0]['status'],'rejected')
            self.assertEqual(result['effective_verify'][1],'judge.py')

class EvaluationConstraintTests(unittest.TestCase):
    def test_explicit_evaluation_constraints_reach_agent(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo,plan,_=create(root/'fixture')
            plan['repair_constraints']='Do not inspect sibling benchmark artifacts.'
            prompts=[]
            def fake(name,prompt,cwd,*args,**kwargs):
                prompts.append(prompt)
                return {'returncode':1,'duration':.01,'stdout':'','stderr':'','usage':{'input_tokens':1,'output_tokens':1,'cached_input_tokens':0}}
            with patch('forksense.agents.invoke',side_effect=fake):
                execute(plan,repo,root/'run',trusted=True,budget=Budget(30,1,0),progress=lambda _:None)
            self.assertIn(plan['repair_constraints'],prompts[0])
