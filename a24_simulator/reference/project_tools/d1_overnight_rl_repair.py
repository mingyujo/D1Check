"""One explicit host-save recovery, never simulator/learner execution."""
from datetime import datetime,timezone
import json
from tools import d1_overnight_rl_amount as x

def run():
    path=x.LOCAL/'host_save_amendment.json'
    already=x.read(path) if path.exists() else None
    reg=x.read(x.LOCAL/'registration.json');original=x.PUBLIC/'source_versions/d1_overnight_rl_amount_v1.py'
    if x.sha(original)!=reg['source_sha256']['tools/d1_overnight_rl_amount.py']:raise ValueError('original registered runner not preserved')
    records=[json.loads(v) for v in (x.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines()]
    state=x.read(x.LOCAL/'WORKING_STATE.json');error=x.read(x.LOCAL/'last_error.json')
    if state['consumption']['native_starts']!=120 or state['consumption']['learning_starts']!=0 or 'os.replace(tmp,path)' not in error['traceback'] or 'progress.json' not in error['traceback'] or 'PermissionError' not in error['traceback']:raise ValueError('not the exact known progress-save failure')
    identity='reference_119';events=[v for v in records if v['identity']==identity]
    if [v['status'] for v in events]!=['started','completed','failed']:raise ValueError('native completion not committed before host error')
    artifact=x.LOCAL/'items'/(identity+'.json.gz');raw=x.read_raw(identity)
    if x.sha(artifact)!=events[1]['sha256'] or events[-1]['number']!=120 or events[-1]['learning']:raise ValueError('artifact SHA/native identity')
    x.x.previous.audit(raw['result'],events[-1]['case']['tickets'])
    if raw['row']['planned']!=raw['row']['completed']:raise ValueError('incomplete artifact cannot be recovered as completed')
    amendment=dict(task=x.TASK,recorded_utc=datetime.now(timezone.utc).isoformat(),reason='Windows progress.json reader blocks atomic rename after native artifact+completed ledger were durably saved',
        original_contract_sha256=x.sha(x.LOCAL/'registration.json'),old_driver_sha256=x.sha(original),repaired_driver_sha256=x.sha(x.ROOT/'tools/d1_overnight_rl_amount.py'),
        repair_scope='only report JSON save PermissionError bounded20x50ms retry and source-amendment validation; policy/schema/model/PPO/reward unchanged',
        recovered_identity=identity,recovered_native_number=120,artifact_sha256=x.sha(artifact),native_replay=0,new_learning=0,original_clock_and_caps_unchanged=True,original_failure_preserved=True)
    if already:
        if any(already[k]!=amendment[k] for k in ('original_contract_sha256','old_driver_sha256','repaired_driver_sha256','artifact_sha256','recovered_identity')):raise ValueError('previous repair contract differs')
    else:x.write(path,amendment);x.write(x.PUBLIC/'host_save_amendment.json',amendment)
    budget=x.Budget();v=budget.rows[119]
    v.update(status='completed',host_save_failure_preserved=True,host_save_failure=v['error'],recovery='original durable native result audited, not replayed')
    v.pop('event',None)
    budget.append(dict(event='host_save_recovery',**v));x.write(x.LOCAL/'progress.json',budget.used())
    x.write(x.LOCAL/'WORKING_STATE.json',dict(task=x.TASK,phase='registered_host_repaired',consumption=budget.used(),next_action='continue original references120..479 and same32 learners, clock/caps unchanged'))
    print(json.dumps(dict(status='PASS_host_save_recovered',consumption=budget.used(),native_replay=0)))

if __name__=='__main__':run()
