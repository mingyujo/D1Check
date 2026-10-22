"""Saved-data readiness only; no environment or neural inference."""
import ast
import shutil
import subprocess
import sys
import study
from study import H,O,R,old,read,new,stamp,verify,DynamicPolicy,C,B,MODES,VERSION

def main():
    assert not O.exists() and not (H/'OPERATION.json').exists()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    subprocess.run(['node','--check',str(H/'audit_report.cjs')],check=True)
    op=read(H/'PROPOSAL.json');verify(op['pins'])
    assert op['planned_START']==6 and op['budget']['derived_total']==137725
    assert op['new_training']==op['new_NN_execution']==op['new_fit']==0
    states=0;cases=[]
    for case in old.cases():
        public,contexts,parent=old.public_and_contexts(case)
        assert len(public['requests'])==len(contexts)==case['n']
        bank=read(old.D/'banks'/(case['id']+'.BANK.json.gz'))
        nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])])
        physics=C.Physics(read(old.A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**parent['physics']),'ORIGINAL',read(old.PORT/'SHAPE.json'))
        raw=read(old.P/('ORIGINAL__DURATION__'+case['id']+'__FIFO_CPU.raw.json.gz'))
        for mode in MODES:
            actor=DynamicPolicy(nominal,physics,mode)
            for dec in raw['result']['decisions'][:20]:
                action=actor(dec['public_state']);assert action['kind']=='DISPATCH';states+=1
        cases.append(dict(case=case['id'],n=case['n']))
    assert [c['n'] for c in cases]==[760,960]
    tests=(H/'TESTS.log').read_text(encoding='utf-8');assert 'Ran 24 tests' in tests and '\nOK' in tests
    for fn in (study.register,study.run):
        try:fn()
        except FileNotFoundError:pass
        else:raise AssertionError('Missing authorization/registration not rejected')
    import psutil
    new(H/'READINESS.json',dict(status='PASS',utc=stamp(),version=VERSION,pins_verified=len(op['pins']),cases=cases,regression_tests=24,saved_state_decisions=states,missing_registration_fail_closed=True,new_environment=0,new_training=0,new_fit=0,new_NN_execution=0,available_disk_bytes=shutil.disk_usage(R).free,available_memory_bytes=psutil.virtual_memory().available,python=sys.version,HEAD=op['HEAD']))
    print('DYNAMIC600_READY',len(op['pins']),'pins;',states,'saved decisions; scientific START 0')
if __name__=='__main__':main()
