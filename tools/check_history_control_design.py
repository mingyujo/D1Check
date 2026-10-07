"""PC design arithmetic only. No collector imports, device access or Run action."""
import hashlib
import json
from pathlib import Path


def check(path):
    plan=json.loads(Path(path).read_text(encoding='utf8'))
    e=plan['entries'];b=plan['budget']
    assert plan['status']=='DESIGN_CHECKED_NOT_EXECUTABLE'
    assert plan['approval']=='not_approved' and not plan['consumed']
    assert len(e)==12 and len({x['id'] for x in e})==12
    for role in ('development','confirmation'):
        assert {(x['recovery_pause_seconds'],x['target_policy']) for x in e if x['role']==role}=={(g,p) for g in (30,180) for p in ('C0','CPU','PAR')}
    assert sum(x['conditioning_requests']+x['target_requests']+x['warmup'] for x in e)==b['explicit_inferences']==2016
    assert sum(x['runtime_creations'] for x in e)==b['runtime_creations']==48
    assert sum(x['conditioning_requests'] for x in e)==1152
    assert sum(x['target_requests'] for x in e)==768
    assert sum(x['warmup'] for x in e)==96
    assert sum(x['conditioning_window_seconds']+x['recovery_pause_seconds']+x['target_observation_seconds'] for x in e)==5220
    assert b['fixed_total_seconds']==5220+11*90==6210
    assert b['verified_execution_upper_seconds'] is None and b['verified_adb_upper'] is None
    assert b['retry']==b['replacement']==b['additional']==0
    return dict(status='PC_DESIGN_ARITHMETIC_PASS_NOT_RUN_READY',sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),sessions=12,explicit_inferences=2016,fixed_seconds=6210,device_commands=0)


if __name__=='__main__':
    print(json.dumps(check('docs/results/history_control_plan_01/design.json'),indent=2))
