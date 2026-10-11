import collections
import datetime as dt
import json
from pathlib import Path
import time

base=Path(__file__).resolve().parent
task=base/'bundle/D1Check-desktop-cpu-20261011/output/desktop_joint_amount_amount512_desktop_20261011_a'
rows={}
path=task/'executions.jsonl'
if path.exists():
    for line in path.read_text().splitlines():
        try:q=json.loads(line)
        except ValueError:continue
        if q.get('event'):rows[q['number']].update(q)
        else:rows[q['number']]=q
clock=json.loads((task/'clock.json').read_text())
active=clock['consumed_active_seconds']+(max(0,time.time()-clock['running_since']) if clock['running_since'] is not None else 0)
finished=[q for q in rows.values() if q['status']=='completed']
print(json.dumps(dict(native_starts=len(rows),native_completed=len(finished),learning_starts=sum(q['learning'] for q in rows.values()),completed_by_phase=dict(collections.Counter(q['phase'] for q in finished)),completed_training_by_seed={s:sum(q['learning'] and q['identity'].startswith('train_'+str(s)+'_') for q in finished) for s in (11,23,37)},failed=sum(q['status']=='failed' for q in rows.values()),active_minutes=active/60,remaining_execution_minutes=max(0,13800-active)/60,remaining_total_minutes=max(0,14400-active)/60,clock_running=clock['running_since'] is not None,last_identity=rows[max(rows)]['identity'] if rows else None,checkpoint_last_saved=dt.datetime.fromtimestamp((task/'session_latest.pt').stat().st_mtime).isoformat(),completed=(task/'completion.json').exists()),indent=2))
