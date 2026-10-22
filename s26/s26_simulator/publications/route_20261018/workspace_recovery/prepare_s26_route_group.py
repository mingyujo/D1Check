"""Finite rare-route learning repair after V1 TRAIN/DEV diagnosis, before new holdout."""
import copy,datetime,hashlib,json,shutil
from pathlib import Path
W=Path(__file__).resolve().parent.parent;R=W/'S26-D1Check/s26_simulator';P=R/'experiments/route_event_learning_v1';H=R/'experiments/route_group_learning_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not H.exists();H.mkdir();shutil.copytree(P/'source',H/'source')
for name in ['physics.cjs','public_observer.cjs','policy.cjs','result.cjs','server.cjs','nn_train.py','dynamics.py','controller.py']:
    shutil.copy2(P/name,H/name)
cases=copy.deepcopy(read(P/'INPUTS.json')['cases']);fresh=[]
for c in cases:
    if c['phase']=='P0':continue
    if c['phase']=='TRAIN':fresh.append(c);continue
    rep={'DEV':25,'EVAL':26 if c['replicate']==22 else 27}[c['phase']]
    c.update(replicate=rep,stream=981000000+rep*100000+len(fresh)*109,id=f"{c['phase']}_N{c['n']}_C{c['mix']}_U{c['nominal_load_ratio']}_R{rep}_CPU3");fresh.append(c)
write(H/'INPUTS.json',dict(cases=fresh,scope='Same TRAIN demonstrations/references reused as saved data, no environment replay. Fresh DEV/EVAL latent streams25/26/27, burst16/rates/deadlines/windows preserved.'))
selected=read(P/'artifacts/G001/SELECTION_FROZEN.json')['selected']
write(H/'PROTOCOL.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),schema='S26_RARE_ROUTE_GROUP_LEARNING_V1',reason='V1 TRAIN demonstration accuracy92.42%; DEV C75U65 NN GPU2/NPU369 vs teacher GPU96/NPU288, urgent367/384 vs384. Fix rare-route distillation rather than add deadline guard.',deadline_protection=False,post_NN_override=False,physics='Byte-identical Event V1 source/power/thermal/context/event actions; CPU3 still unmeasured and common to controls.',BC='Reuse four saved TRAIN demonstrations only. Initialize V1 common BC network. Inverse-frequency weights for teacher action/route groups, compatible EDF ties share target probability. Up to64epochs, stop only if total compatible accuracy>=99.5%, each action/route group>=99%, loss<=0.05. No runtime teacher override.',PPO='3 fresh seeds881081/83/87, same common BC network, LR.0001/temp.35/RMS/dual unchanged. Each2 episodes (N512 primary85 two mixes), one PPO update. New optimizer/RNG and complete CP.',comparison='9 policies: plainEDF,ATC,softATC,old frozen481083,V1 DEV-selected event frozen,BC frozen,3PPO. 4DEV N512 then freeze seed before8 freshEVAL N1024. All65/85 and50/75 mixes.',planned_START=114,environment_cap=128,allocation=dict(TRAIN=6,DEV=36,EVAL=72),new_BC_fit=1,new_measurements=0,new_physical_fits=0,reused_demonstration_environments=4,reused_TRAIN_reference_environments=8,old_event_selected=selected,no_generalization='No105/LOWHIGH or real-device certification. Final results can reject this repair. All older outcomes preserved.'))
write(H/'BUDGET_RESERVATION.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),known_conservative_before=129366,new_reservation=128,known_conservative_after=129494,shared_cap=137712,planned_environments=114,BC_actor_fit=1,own_wave_reserved=820,own_wave_planned_environments=740,own_wave_scientific_units=790,unused_reserved=30,not_fresh_all_host_census=True,no_refunds=True))
write(H/'WAVE_BUDGET_TOTALS.json',dict(own_reserved=820,known_conservative_union=129494,planned_environments=740,training_episodes=126,PPO_updates=63,BC_actor_fits=2,LP_solves=48,new_reserved=128,new_scientific_units=115,unused_reserved=30,previous_allocation_sha256=sha(P.parent/'route_energy_v1/NUMERICAL_BUDGET_ALLOCATION.json')))
# Reuse runner's audited physics/RNG/reward path, change only registration/initialization/case counts.
s=(P/'run.py').read_text(encoding='utf-8')
a=s.index("        c=phase['P0'][0]");b=s.index('        nets={};dual_history=[]',a)
s=s[:a]+'''        oldO=Path(op['reuse_directory']);old_result=read(oldO/'RESULT.json')
        references={r['input']:r for r in old_result['rows'] if r['kind']=='TRAIN_REFERENCE'}
        scales=read(oldO/'TRAINING_COMPLETE.json')['scales'];demos=[]
        for name in op['demo_labels']:demos.append(load(oldO/(name+'.demonstrations.pt.gz')))
        parent=load(op['parent_checkpoint']);frozen=Learner(481083);frozen.restore(parent);frozen_sha=digest(frozen.net)
        older=load(op['old_event_checkpoint']);old_event=Learner(op['old_event_seed']);old_event.restore(older['learner']);old_event.balance=copy.deepcopy(older['balance']);old_event_sha=digest(old_event.net)
        warm,bc_trace=pretrain(load(op['BC_initial_checkpoint'])['learner'],demos,op['BC_seed']);warm.balance=dict(scales=scales,dual=[1.,1.],classFactors=[1,1],tail=.02)
        pt(O/'BC_TRACE.pt.gz',bc_trace);pt(O/'BC_COMMON_FINAL.pt.gz',dict(learner=warm.snapshot(),balance=warm.balance));save(O/'BC_TRAINING.json',dict(logs=bc_trace['logs'],steps=bc_trace['steps'],frames=bc_trace['frames'],not_RL=True,new_PPO_updates=0,weight_sha256=digest(warm.net)));warm_sha=digest(warm.net)
        save(O/'SAVED_TRAIN_REUSE.json',dict(references=8,demonstrations=4,new_environment=0,source=op['reuse_directory']))
        save(O/'P0_PROOF.json',dict(source_byte_identical_to_event_v1=True,new_environment=0,public_preflight='SAVED_PUBLIC_PREFLIGHT.json'))
        del demos
        train_cases=[c for c in phase['TRAIN'] if c['n']==512 and c['nominal_load_ratio']==.85]
''' +s[b:]
s=s.replace('permutation(8).tolist()','permutation(2).tolist()').replace("phase['TRAIN'][j]['id']","train_cases[j]['id']").replace("c=phase['TRAIN'][j];ref=", "c=train_cases[j];ref=")
s=s.replace('learner.episodes==8 and learner.updates==4','learner.episodes==2 and learner.updates==1').replace('TRAIN_REFERENCE=8,DEMO=4,TRAIN=24,PPO_updates=12','TRAIN_REFERENCE_reused=8,DEMO_reused=4,TRAIN=6,PPO_updates=3')
s=s.replace("            for label,learner in [('WARM_FROZEN',warm)","            old_balance=copy.deepcopy(old_event.balance);old_balance['classFactors']=[1/c['mix'],1/(1-c['mix'])];simulate(c,'RL',f'{phase}_{i}_OLD_EVENT',phase,'CPU3',old_event,balance=old_balance)\n            for label,learner in [('WARM_FROZEN',warm)")
s=s.replace('count==134 and len(rows)==134','count==114 and len(rows)==114 and digest(old_event.net)==old_event_sha').replace('PPO_updates=12,BC_steps','PPO_updates=3,BC_steps')
(H/'run.py').write_text(s,encoding='utf-8')
# Independent physical arithmetic and causal input checks, now9 policies per case.
s=(P/'audit.cjs').read_text(encoding='utf-8').replace('134','114').replace("rr.length===8,'All8", "rr.length===9,'All9")
(H/'audit.cjs').write_text(s,encoding='utf-8')
s=(P/'audit_nn.py').read_text(encoding='utf-8');a=s.index('    demonstrations=[]');b=s.index('    for seed in op[\'seeds\']:',a)
s=s[:a]+'''    demonstrations=[];oldO=Path(op['reuse_directory'])
    for label in op['demo_labels']:
        data=load(oldO/(label+'.demonstrations.pt.gz'));demonstrations.append(data)
        for f in data['frames']:need(teacher(dict(x=f['x'],mask=f['mask'],actions=f['candidate_actions']))==f['index'],'Original public teacher reproduced')
    warm,bc_trace=pretrain(load(op['BC_initial_checkpoint'])['learner'],demonstrations,op['BC_seed']);saved_trace=load(O/'BC_TRACE.pt.gz');equal(bc_trace,saved_trace);equal(warm.snapshot(),load(O/'BC_COMMON_FINAL.pt.gz')['learner']);bc_steps=bc_trace['steps'];del demonstrations
''' +s[b:]
s=s.replace('permutation(8).tolist()','permutation(2).tolist()').replace('range(1,9)','range(1,3)').replace("learner.updates==4,'Four PPO", "learner.updates==1,'One PPO").replace("updates==12,'All12", "updates==3,'All3").replace("row['seed']==781000", "row['seed']==881000")
s=s.replace("else load(O/f'S{row[\"seed\"]}_FINAL.pt.gz')['learner']", "else load(op['old_event_checkpoint'])['learner'] if row['seed']==op['old_event_seed'] else load(O/f'S{row[\"seed\"]}_FINAL.pt.gz')['learner']")
(H/'audit_nn.py').write_text(s,encoding='utf-8')
# Reports retain all eight original result columns; add old event control explicitly.
s=(P/'report.py').read_text(encoding='utf-8').replace('781000','881000').replace("if r['seed'] is not None else r['mode']", "if r['seed'] is not None else r['mode']")
s=s.replace("else 'BC_FROZEN'",f"else 'OLD_EVENT_RL' if r['seed']=={selected} else 'BC_FROZEN'")
s=s.replace("'OLD_RL','BC_FROZEN'", "'OLD_RL','OLD_EVENT_RL','BC_FROZEN'").replace("'OLD_RL':'기존 RL 고정'", "'OLD_RL':'기존 RL 고정','OLD_EVENT_RL':'앞 사건 RL 고정'")
s=s.replace('EVENT_ROUTE_ALL64','GROUP_ROUTE_ALL72').replace('PPO_updates=12','PPO_updates=3').replace('S26_ROUTE_EVENT_RESULTS_KO.md','S26_ROUTE_GROUP_RESULTS_KO.md').replace('P0 2·TRAIN 참조8·규칙 시연4·PPO 학습24·DEV32·새 EVAL64, 실제 PPO update12','저장 TRAIN 참조8·규칙 시연4 재사용(새 실행0)·PPO 학습6·DEV36·새 EVAL72, 실제 PPO update3')
s=s.replace("[앞 단계 전체 결과](S26_ROUTE_ENERGY_RESULTS_KO.md)","[앞 단계 사건 RL 결과](S26_ROUTE_EVENT_RESULTS_KO.md)")
s=s.replace('공통 actor를 학습한 뒤3개 PPO seed', '경로별 역빈도 가중치와 동일 EDF 동률 행동의 합산 확률로 공통 actor를 최대64epoch 학습한 뒤3개 PPO seed')
(H/'report.py').write_text(s,encoding='utf-8')
for name in ['figure.py','fixed_family_energy.cjs']:
    s=(P/name).read_text(encoding='utf-8').replace('route_event_learning_v1','route_group_learning_v1').replace('S26_ROUTE_EVENT_RESULTS_KO.md','S26_ROUTE_GROUP_RESULTS_KO.md')
    if name.endswith('.cjs'):s=s.replace('r.seed!==null&&r.seed!==481083&&r.seed!==781000','[881081,881083,881087].includes(r.seed)')
    (H/name).write_text(s,encoding='utf-8')
write(H/'PENDING_OPERATION.json',dict(schema='S26_RARE_ROUTE_GROUP_EXECUTION_V1',planned_START=114,environment_cap=128,wall_cap_s=7200,seeds=[881081,881083,881087],BC_seed=881000,parent_checkpoint=read(P/'OPERATION.json')['parent_checkpoint'],BC_initial_checkpoint=str(P/'artifacts/G001/BC_COMMON_FINAL.pt.gz'),old_event_seed=selected,old_event_checkpoint=str(P/f'artifacts/G001/S{selected}_FINAL.pt.gz'),reuse_directory=str(P/'artifacts/G001'),demo_labels=[f'DEMO_{i}' for i in range(4)],shared_mutex=read(P/'OPERATION.json')['shared_mutex'],ownheavy_limit=1,global_Python_limit=3,initial_min_free_MiB=1536,new_measurements=0,new_physical_fits=0,deadline_protection=False,post_NN_override=False,physical_validation=False))
write(H/'SOURCE_DERIVATION.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),parent=str(P),byte_identical=[dict(path=n,sha256=sha(H/n)) for n in ['physics.cjs','public_observer.cjs','policy.cjs','result.cjs','server.cjs','nn_train.py','dynamics.py','controller.py']],changed='Run registration/input streams, rare-route supervised initial learning and bounded6PPO episodes only. Physics/action banks remain byte identical.'))
print('GROUP114_PREPARED128; seal after BC source/preflight and parent saved audit complete; not started')
