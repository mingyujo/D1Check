import datetime,hashlib,json
from pathlib import Path
W=Path(__file__).resolve().parent.parent;R=W/'S26-D1Check/s26_simulator';H=R/'experiments/route_energy_v1'
assert not (H/'OPERATION.json').exists()
p=H/'policy.cjs';s=p.read_text(encoding='utf-8')
old="obs.wait_used_s+wait_s<=12+1e-9&&(state.waitByHead.get(head.ordinal)??0)+wait_s<=1.5+1e-9"
assert s.count(old)==1
s=s.replace(old,"((state.balance||state.mode==='ENERGY_ONLY')||(obs.wait_used_s+wait_s<=12+1e-9&&(state.waitByHead.get(head.ordinal)??0)+wait_s<=1.5+1e-9))")
p.write_text(s,encoding='utf-8')
protocol=json.loads((H/'PROTOCOL.json').read_text(encoding='utf-8'))
protocol['WAIT']='Balanced/energy-only keep all physical-legal dispatch candidates and WAIT. Remove old artificial total12s/head1.5s wait caps; retain registered dispatch_stop and horizon. Frozen RL preserves old caps. No deadline mask or forced choice.'
(H/'PROTOCOL.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
parent=R/'experiments/a24_policy_repair_v1/artifacts/G001/REPAIR_S481083_EP032.pt.gz'
files=[*H.glob('*.py'),*H.glob('*.cjs'),*H.glob('*.json'),*H.joinpath('source').glob('*.cjs'),parent,R/'experiments/plain_edf_v1/select.cjs',R/'experiments/capacity_power_v1/replay.cjs',R/'experiments/capacity_power_v1/artifacts/G001/MODEL.json',R/'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json',R/'experiments/multiresource_v1/PACKET.json.gz',*R.joinpath('experiments/a24_stable_learning_v1/source').glob('*.cjs'),*R.joinpath('experiments/a24_stable_learning_v1').glob('*.cjs')]
op=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),output=str(H/'artifacts/G001'),shared_mutex=str(W/'D1Check/a24_simulator/runtime/worker.lock'),planned_START=420,environment_cap=448,wall_cap_s=10800,seeds=[681081,681083,681087],parent_checkpoint=str(parent),own_S26_limit=1,global_Python_limit=3,single_thread=True,initial_min_free_MiB=2048,between8_min_free_MiB=1024,pins=[dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in dict.fromkeys(files)],no_automatic_retry=True)
with (H/'OPERATION.json').open('x',encoding='utf-8') as f:json.dump(op,f,ensure_ascii=False,indent=2)
flow=dict(utc=op['utc'],status='SEALED_NOT_STARTED',directory=str(H),planned_START=420,cap=448,active_entry='route_energy_v1/run.py',step='Route LP complete, gate true; next counted P0, TRAIN_REFERENCE, TRAIN, DEV freeze, fresh EVAL, saved audit/report.',parent_sources_untouched=True,deadline_protection=False,CPU_scenarios=['CENTRAL_1','CPU3_parallel'],operation_sha256=hashlib.sha256((H/'OPERATION.json').read_bytes()).hexdigest())
(W/'recovery/S26_ROUTE_ACTIVE_FLOW.json').write_text(json.dumps(flow,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ['START_HERE.md','STATUS.md']:
    p=R/name;s=p.read_text(encoding='utf-8');line='\n<!-- S26_ROUTE_CURRENT_BEGIN -->\n2026-10-18 사용자 명시 지시로 경로선택 완화하한과 균형보상/무보호RL·CPU서비스 병렬화 후속을 별도 등록했다. `experiments/route_energy_v1/OPERATION.json` 봉인, 예정420/cap448. 기존 물리 후보/정확도FAIL·원결과 보존, CPU3은 미측정 동시CPU가정이다. `../../recovery/S26_ROUTE_ACTIVE_FLOW.json`와 새 receipts를 먼저 확인하고 중복실행하지 않는다. 납기보호/새실측/새fit/업로드0.\n<!-- S26_ROUTE_CURRENT_END -->\n'
    s=s.replace('\n',line,1);p.write_text(s,encoding='utf-8')
print('SEALED',len(op['pins']),'files;420 planned;448 reserved')
