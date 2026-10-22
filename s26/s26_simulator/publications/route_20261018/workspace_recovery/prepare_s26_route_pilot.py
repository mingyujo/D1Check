"""Finite TRAIN-only pilot; amend unstarted full witness to avoid any rerun."""
import datetime,hashlib,json,shutil
from pathlib import Path
W=Path(__file__).resolve().parent.parent;R=W/'S26-D1Check/s26_simulator';B=R/'experiments/route_witness_v1';H=R/'experiments/route_witness_pilot_v1';P=R/'experiments/route_energy_v1'
assert not H.exists() and not (B/'OPERATION.json').exists()
H.mkdir()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
s=(B/'run.cjs').read_text(encoding='utf-8')
a="parent=read(path.join(P,'artifacts/G001/RESULT.json'))"
b="parent={rows:fs.readdirSync(path.join(P,'artifacts/G001')).filter(n=>/^REFERENCE_.*\\.json$/.test(n)).map(n=>read(path.join(P,'artifacts/G001',n)))}"
assert s.count(a)==1;s=s.replace(a,b).replace("['TRAIN','DEV','EVAL']","['TRAIN']").replace('count!==72||rows.length!==72','count!==18||rows.length!==18').replace('Full72','Full18').replace('ALL72_CAUSAL_ROUTE_WITNESSES_COMPLETE','ALL18_TRAIN_ROUTE_PILOTS_COMPLETE')
(H/'run.cjs').write_text(s,encoding='utf-8')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
save(H/'PROTOCOL.json',dict(utc=now,schema='S26_ROUTE_TRAIN_PILOT_V1',planned_START=18,cap=20,models=['CENTRAL','CPU3'],modes=['CPU_ONLY','GPU_ONLY','NPU_ONLY','SPLIT75','SPLIT87'],data='Only parent TRAIN N1024 primary85% two mixes. CPU_ONLY CPU3 duplicates skipped. No DEV/EVAL access.',parent_study_unchanged=True,resource_exception='User explicitly permits logically justified constraint relaxation. Brief18 fixed-rule single-thread Node cases may run alongside one main S26 learner, using <=2 of20 logical cores and initial freeRAM>=2GiB, globalPython<=3. Parent retains shared byte0 exclusion; pilot takes byte1 sublease after proving live parent owns byte0. No parent scientific/input/RNG/clock changes; no unrelated peers allowed.',no_new_RL=True,physical_validation=False))
save(H/'BUDGET_RESERVATION.json',dict(utc=now,known_conservative_before=128994,new_global_reservation=20,known_conservative_after=129014,shared_cap=137712,planned_START=18,cap=20,automatic_retry=False,not_fresh_all_host_census=True,full_witness_avoids_duplicate_pilot_TRAIN=True,other_caps_unspent_not_refunded=True))
# The previously unstarted full witness reuses these18 TRAIN results by link.
for name in ['PROTOCOL.json','OPERATION_BASE.json','BUDGET_RESERVATION.json']:
    shutil.copyfile(B/name,B/(name+'.BEFORE_TRAIN_PILOT_REUSE'))
proto=read(B/'PROTOCOL.json');proto.update(planned_START=54,allocation=dict(DEV=18,EVAL=36),TRAIN_DIAGNOSIS='18 results owned by route_witness_pilot_v1; linked, never rerun',prestart_pilot_reuse_utc=now);(B/'PROTOCOL.json').write_text(json.dumps(proto,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
op=read(B/'OPERATION_BASE.json');op['planned_START']=54
for p in op['pins']:p['sha256']=sha(p['path'])
(B/'OPERATION_BASE.json').write_text(json.dumps(op,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
s=(B/'run.cjs').read_text(encoding='utf-8').replace("['TRAIN','DEV','EVAL']","['DEV','EVAL']").replace('count!==72||rows.length!==72','count!==54||rows.length!==54').replace('Full72','Full54').replace('ALL72_CAUSAL_ROUTE_WITNESSES_COMPLETE','ALL54_CAUSAL_ROUTE_WITNESSES_COMPLETE');(B/'run.cjs').write_text(s,encoding='utf-8')
s=(B/'audit_report.cjs').read_text(encoding='utf-8').replace('72','54');(B/'audit_report.cjs').write_text(s,encoding='utf-8')
save(H/'OPERATION_BASE.json',dict(utc=now,planned_START=18,environment_cap=20,wall_cap_s=600,shared_mutex=str(W/'D1Check/a24_simulator/runtime/worker.lock'),parent_pid=read(P/'artifacts/G001/START.json')['pid'],parent_operation_sha256=sha(P/'OPERATION.json'),pins=[dict(path=str(p),sha256=sha(p)) for p in [H/'run.cjs',H/'PROTOCOL.json',H/'BUDGET_RESERVATION.json',P/'OPERATION.json',P/'INPUTS.json',*P.joinpath('source').glob('*.cjs'),*[P/n for n in ['policy.cjs','physics.cjs','public_observer.cjs','result.cjs']],*P.joinpath('artifacts/G001').glob('REFERENCE_*.json')]]))
print('PILOT18_REGISTERED;unstarted_witness54_reuses_TRAIN;parent_untouched')
