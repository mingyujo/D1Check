"""Record boundary-safe storage pause; resume only with4GiB and same clock."""
import argparse,json,shutil
from datetime import datetime,timezone
from tools import d1_overnight_rl_amount as x

def register():
    path=x.LOCAL/'storage_hold_amendment.json'
    if path.exists():raise FileExistsError('storage hold amendment immutable')
    prior=x.read(x.LOCAL/'host_save_amendment.json');old=x.PUBLIC/'source_versions/d1_overnight_rl_amount_v2_host_save.py'
    if x.sha(old)!=prior['repaired_driver_sha256']:raise ValueError('prior host-save driver missing')
    state=x.read(x.LOCAL/'WORKING_STATE.json')
    if (x.LOCAL/'owner.lock').exists() or state['consumption']['learning_starts']!=0 or state['consumption']['failed']!=0:raise ValueError('not safe completed-native boundary before training')
    rows=[]
    for line in (x.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        q=json.loads(line)
        if q.get('event'):rows[q['number']-1].update(q)
        else:rows.append(q)
    if any(q['status']!='completed' for q in rows):raise ValueError('native in-flight or failed cannot pause as completed')
    amendment=dict(task=x.TASK,recorded_utc=datetime.now(timezone.utc).isoformat(),reason='root requested storage hold after C drive free375MB',
        original_contract_sha256=x.sha(x.LOCAL/'registration.json'),prior_host_amendment_sha256=x.sha(x.LOCAL/'host_save_amendment.json'),
        previous_driver_sha256=x.sha(old),repaired_driver_sha256=x.sha(x.ROOT/'tools/d1_overnight_rl_amount.py'),
        scope='host storage hold marker before each native check; chained source validation; policy/learner/model unchanged',
        completed_native_boundary=len(rows),new_learning=0,minimum_free_bytes=4294967296,environment_replay=0,clock_and_caps_reset=False)
    x.write(path,amendment);x.write(x.PUBLIC/'storage_hold_amendment.json',amendment)
    x.write(x.LOCAL/'WORKING_STATE.json',dict(task=x.TASK,phase='storage_hold',consumption=state['consumption'],next_action='same clock resume after4GiB free; no native/model checkpoint deletion'))
    print(json.dumps(dict(status='PASS_boundary_storage_hold',native_completed=len(rows),learning=0,clock_reset=False)))

def resume():
    if shutil.disk_usage(x.ROOT).free<4294967296:raise ValueError('still below4GiB; preserve clock and do not start')
    path=x.LOCAL/'storage_hold.json'
    if not path.exists():raise FileNotFoundError('hold already cleared')
    receipt=dict(resumed_utc=datetime.now(timezone.utc).isoformat(),free_bytes=shutil.disk_usage(x.ROOT).free,clock_reset=False,hold=x.read(path))
    x.write(x.LOCAL/'storage_resume_receipt.json',receipt);x.write(x.PUBLIC/'storage_resume_receipt.json',receipt)
    path.rename(x.LOCAL/'storage_hold_preserved.json');x.check()
    print(json.dumps(dict(status='PASS_storage_resume_check',free_bytes=receipt['free_bytes'],native_replay=0)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','resume'));a=p.parse_args();register() if a.command=='register' else resume()
