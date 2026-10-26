"""Transparent controlled demo. Prepared patches by default; real CLI is opt-in."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from .engine import execute, Budget

SOURCE='''"""A tiny checkout service with a cache correctness bug."""
_cache = {}

def total(price, *, tax=0, discount=0):
    key = (price, discount)
    if key not in _cache:
        _cache[key] = round(price * (1 - discount) * (1 + tax), 2)
    return _cache[key]
'''
VERIFIER='''import importlib.util, pathlib, sys, unittest
p=pathlib.Path.cwd()/"checkout.py"
spec=importlib.util.spec_from_file_location("checkout",p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class CheckoutContract(unittest.TestCase):
    def setUp(self): m._cache.clear()
    def test_tax_separation(self):
        self.assertEqual(m.total(100,tax=0),100)
        self.assertEqual(m.total(100,tax=.2),120)
    def test_discount(self):
        self.assertEqual(m.total(100,discount=.1),90)
        self.assertEqual(m.total(100,discount=.2),80)
    def test_repeat(self):
        self.assertEqual(m.total(39.99,tax=.1,discount=.2),35.19)
        self.assertEqual(m.total(39.99,tax=.1,discount=.2),35.19)
    def test_order(self):
        for price in (0,1,19.99,102.1):
            for tax in (.2,0,.05):
                for discount in (.1,0,.2):
                    self.assertEqual(m.total(price,tax=tax,discount=discount),round(price*(1-discount)*(1+tax),2))
unittest.main()
'''

def create(output):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('demo output exists; choose a fresh directory')
    output.mkdir(parents=True)
    repo=output/'checkout'; repo.mkdir()
    (repo/'checkout.py').write_text(SOURCE)
    (repo/'README.md').write_text('Controlled checkout debugging fixture. The checkout cache returns incorrect totals.\n')
    (output/'verify_checkout.py').write_text(VERIFIER)
    def g(*args):
        subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(repo),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    g('init','-b','main'); g('add','checkout.py','README.md')
    g('-c','user.name=ForkSense Demo','-c','user.email=demo@example.invalid','commit','-m','Frozen buggy checkout fixture')
    hs=[{'id':'tax-key','description':'The cache key omits the tax rate','prior':.4},{'id':'discount-key','description':'The cache key omits the discount','prior':.35},{'id':'rounding','description':'Rounding occurs before the final calculation','prior':.25}]
    def probe(name,label,code,passes,cost):
        return {'id':name,'label':label,'command':[sys.executable,'-c',code],'cost_seconds':cost,'likelihoods':{h['id']:{'pass':1. if h['id'] in passes else 0.,'fail':0. if h['id'] in passes else 1.} for h in hs}}
    es=[probe('vary-tax','Change only tax, hold price and discount fixed','from checkout import total; assert total(100,tax=0)==100; assert total(100,tax=.2)==120',{'discount-key','rounding'},.1),probe('vary-discount','Change only discount','from checkout import total; assert total(100,discount=.1)==90; assert total(100,discount=.2)==80',{'tax-key','rounding'},.2)]
    plan={'version':1,'task':'Fix checkout totals when tax and discount vary between requests. Preserve cache behavior.','verify':[sys.executable,str(output/'verify_checkout.py')],'editable_paths':['checkout.py'],'hypotheses':hs,'experiments':es}
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    # Prepared candidates remain outside the target repository, and are never
    # included in real-agent prompts. This is a mechanics demo, not an agent score.
    patches={}
    for hid,before,after in [('tax-key','key = (price, discount)','key = (price, discount, tax)'),('discount-key','key = (price, discount)','key = (price,)'),('rounding','round(price * (1 - discount) * (1 + tax), 2)','round(price, 2) * (1 - discount) * (1 + tax)')]:
        lines=SOURCE.splitlines(True); revised=SOURCE.replace(before,after).splitlines(True)
        import difflib
        patch=''.join(difflib.unified_diff(lines,revised,fromfile='a/checkout.py',tofile='b/checkout.py'))
        path=output/f'{hid}.patch'; path.write_text(patch); patches[hid]=str(path)
    return repo,plan,patches

def demo(output,agent='patch',seconds=180):
    repo,plan,patches=create(output)
    print('FORKSENSE  /  Stop guessing. Test the alternatives.')
    print('CONTROLLED DEMO  '+('prepared candidate patches; no model called' if agent=='patch' else f'live {agent} repair; no prepared patch supplied'))
    result=execute(plan,repo,Path(output)/'run',agent=agent,budget=Budget(seconds,2,3),trusted=True,candidate_patches=patches if agent=='patch' else None)
    print(f"REPORT  {Path(output).resolve()/'run'/'report.html'}")
    print(f"ACCEPT  forksense accept {Path(output).resolve()/'run'/'report.json'} --repo {repo} --yes")
    return result
