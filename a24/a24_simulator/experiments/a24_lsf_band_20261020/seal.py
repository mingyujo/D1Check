"""Final saved-only proof for request-level LSF/Band comparison."""
import ast,json,re,subprocess
from study import H,O,R,read,new,stamp,pin,verify

def main():
    assert not (O/'FINAL_HANDOFF_PROOF.json').exists()
    op=read(H/'OPERATION.json');verify(op['pins']);verify([op['authorization']])
    auth=read(R/op['authorization']['path'])
    assert auth['authorized_units']==18 and auth['numeric_total_explicitly_stated_by_user'] is False
    result=read(O/'RESULT.json');assert result['START']==18 and result['COMPLETE']+result['FAIL']==18
    assert all(result[k]==0 for k in ('new_training','new_BC_fit','new_PPO','new_fit','new_device','new_NN_execution'))
    receipts=[json.loads(l) for l in (O/'receipts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts=[r for r in receipts if r['event']=='START'];terminals=[r for r in receipts if r['event'] in ('COMPLETE','FAIL')]
    assert len(receipts)==36 and len(starts)==len(terminals)==18 and len({r['start_id'] for r in starts})==18
    assert {r['start_id'] for r in starts}=={r['start_id'] for r in terminals}
    verify([r['raw'] for r in result['rows']])
    for name in ('AUDIT.json','REPLAY.json'):assert read(O/name)['status']=='PASS'
    assert read(O/'AUDIT.json')['rows']==42 and len(read(O/'SUMMARY.json')['groups'])==21
    assert read(O/'SUMMARY.json')['full_Band_runtime'] is False
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    for name,count in (('TESTS_V3.log',21),('DROP_TESTS.log',2)):
        t=(H/name).read_text(encoding='utf-8');assert f'Ran {count} tests' in t and '\nOK' in t
    helper=json.loads((H/'AUDIT_HELPER_TESTS.log').read_text(encoding='utf-8'));assert helper['status']=='PASS' and helper['synthetic_states']==21
    files=[p for d in (H,O) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [R/p for p in ('docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/docs/LATEST_EXECUTION_FILES.md','a24_simulator/docs/A24_POLICY_METHODOLOGY_KO.md')]
    links=0
    for p in [O/'INTERPRETATION_KO.md',O/'REPORT_KO.md',R/'a24_simulator/docs/A24_POLICY_METHODOLOGY_KO.md']:
        for t in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if '://' in t or t.startswith('#'):continue
            assert (p.parent/t.split('#')[0]).resolve().exists(),(p,t);links+=1
    git=lambda *a:subprocess.check_output(['git',*a],cwd=R,text=True,encoding='utf-8').strip()
    assert git('rev-parse','HEAD')==op['HEAD'] and git('branch','--show-current')==op['branch']
    new(O/'FINAL_HANDOFF_PROOF.json',dict(status='PASS',schema='A24_LSF_BAND_FINAL_V1',utc=stamp(),HEAD=op['HEAD'],branch=op['branch'],working_tree=git('status','--short'),published=False,full_Band_runtime=False,operation_sha256=pin(H/'OPERATION.json')['sha256'],registered_pins_verified=len(op['pins']),authorization=op['authorization'],new_START=18,new_COMPLETE=result['COMPLETE'],new_FAIL=result['FAIL'],new_training=0,new_BC_fit=0,new_PPO=0,new_fit=0,new_device=0,new_NN_execution=0,old_completed_environments_rerun=0,budget=dict(previous_closed_total=137741,current_requested_EVAL=18,current_consumed=18,conservative_total=137759,automatic_extra_experiments=0,refund=0),links_verified=links,files=[pin(p) for p in sorted(set(files))]))
    print('LSF_BAND_SEALED',len(files),'files;',len(op['pins']),'pins;',links,'links')

if __name__=='__main__':main()
