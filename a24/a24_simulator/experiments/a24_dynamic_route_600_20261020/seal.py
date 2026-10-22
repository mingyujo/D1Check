"""Final evidence snapshot; no scientific execution."""
import ast
import json
import re
import subprocess
from pathlib import Path
from study import H,O,R,read,new,stamp,pin,verify

def main():
    assert not (O/'FINAL_HANDOFF_PROOF.json').exists()
    op=read(H/'OPERATION.json');verify(op['pins']);verify([op['authorization']])
    auth=read(R/op['authorization']['path']);assert auth['user_message']=='그럼 한번 해보자' and auth['authorized_units']==6 and auth['numeric_total_explicitly_stated_by_user'] is False
    assert op['authorized_total']==137725
    result=read(O/'RESULT.json');assert (result['START'],result['COMPLETE'],result['FAIL'])==(6,6,0)
    assert all(result[k]==0 for k in ('new_training','new_BC_fit','new_PPO','new_NN_execution','new_fit','new_device'))
    verify([r['raw'] for r in result['rows']])
    receipts=[json.loads(l) for l in (O/'receipts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts=[r for r in receipts if r['event']=='START'];ends=[r for r in receipts if r['event']=='COMPLETE']
    assert len(receipts)==12 and len(starts)==len(ends)==6 and {r['start_id'] for r in starts}=={r['start_id'] for r in ends}
    assert len(set(r['start_id'] for r in starts))==6
    for name in ('AUDIT.json','REPLAY.json','ROUTE_DIAGNOSIS.json'):assert read(O/name)['status']=='PASS'
    assert read(O/'AUDIT.json')['rows']==20 and read(O/'REPLAY.json')['calls']==5160
    summary=read(O/'SUMMARY.json');assert len(summary['groups'])==10 and summary['old_results_rerun']==0
    assert summary['new_EVAL_START']==6
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    tests=(H/'TESTS.log').read_text(encoding='utf-8');assert 'Ran 24 tests' in tests and '\nOK' in tests
    files=[p for d in (H,O) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files+=[R/p for p in ('docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/docs/LATEST_EXECUTION_FILES.md','a24_simulator/docs/A24_POLICY_METHODOLOGY_KO.md')]
    links=0
    for p in [O/'INTERPRETATION_KO.md',O/'REPORT_KO.md',R/'a24_simulator/docs/A24_POLICY_METHODOLOGY_KO.md']:
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            assert (p.parent/target.split('#')[0]).resolve().exists(),(p,target);links+=1
    git=lambda *args:subprocess.check_output(['git',*args],cwd=R,text=True,encoding='utf-8').strip()
    assert git('rev-parse','HEAD')==op['HEAD'] and git('branch','--show-current')==op['branch']
    new(O/'FINAL_HANDOFF_PROOF.json',dict(status='PASS',schema='A24_DYNAMIC_ROUTE600_FINAL_V1',utc=stamp(),HEAD=op['HEAD'],branch=op['branch'],working_tree=git('status','--short'),published=False,operation_sha256=pin(H/'OPERATION.json')['sha256'],authorization=op['authorization'],registered_pins_verified=len(op['pins']),new_START=6,new_COMPLETE=6,new_FAIL=0,new_training=0,new_BC_fit=0,new_NN_execution=0,new_physical_fit=0,new_device=0,old_completed_environments_rerun=0,budget=dict(previous_closed_total=137719,current_requested_EVAL=6,current_consumed=6,conservative_total=137725,automatic_extra_experiments=0,refund=0),links_verified=links,files=[pin(p) for p in sorted(set(files))]))
    print('DYNAMIC600_SEALED',len(files),'files;',len(op['pins']),'source pins;',links,'links')
if __name__=='__main__':main()
