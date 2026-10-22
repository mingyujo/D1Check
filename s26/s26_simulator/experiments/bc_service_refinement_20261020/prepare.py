"""One fixed normal-EDF refinement, separately registered60; preserve first148."""
import datetime,hashlib,json,random
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parents[2];H=D.parent/'bc_service_repair_20261020'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def source(name,text):
 with (D/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
assert not (D/'OPERATION.json').exists();edits=[]
def replace(text,old,new):
 assert text.count(old)==1,old
 edits.append(dict(old=old,new=new));return text.replace(old,new)
text=(H/'service_guard.cjs').read_text(encoding='utf-8-sig')
text=replace(text,"'BC_RESOURCE_GUARD'].includes(mode)","'BC_RESOURCE_GUARD','BC_RESOURCE_EDF_NORMAL'].includes(mode)")
text=replace(text,"mode==='BC_RESOURCE_GUARD'&&classes.length","['BC_RESOURCE_GUARD','BC_RESOURCE_EDF_NORMAL'].includes(mode)&&classes.length")
text=replace(text,"normal.length&&obs.time>=normal[0].deadline","normal.length&&(mode==='BC_RESOURCE_EDF_NORMAL'||obs.time>=normal[0].deadline)")
text=replace(text,"reason='NORMAL_ALREADY_LATE_PROGRESS';forced=normal[0].ordinal;","reason=mode==='BC_RESOURCE_EDF_NORMAL'?'NORMAL_EDF_PROGRESS':'NORMAL_ALREADY_LATE_PROGRESS';forced=normal[0].ordinal;")
source('service_guard.cjs',text)
text=(H/'policy.cjs').read_text(encoding='utf-8-sig');text=replace(text,"state.guardMode==='BC_RESOURCE_GUARD'?tm.lengths","['BC_RESOURCE_GUARD','BC_RESOURCE_EDF_NORMAL'].includes(state.guardMode)?tm.lengths");source('policy.cjs',text)
for name in ['server.cjs','physical_auditor.py','abi_preflight.cjs']:source(name,(H/name).read_text(encoding='utf-8-sig'))
text=(H/'preflight.cjs').read_text(encoding='utf-8-sig');text=text.replace("['BC_DISPATCH_ONLY','BC_PROGRESS_GUARD','BC_RESOURCE_GUARD']","['BC_DISPATCH_ONLY','BC_PROGRESS_GUARD','BC_RESOURCE_GUARD','BC_RESOURCE_EDF_NORMAL']")
text=replace(text,"const out={status:'PASS'", "x=p('BC_RESOURCE_EDF_NORMAL',1,[fresh,n]);check(x.v.reason==='NORMAL_EDF_PROGRESS');check(x.v.allowed_indices.every(i=>x.a[i].ordinal===1));\nconst out={status:'PASS'");source('preflight.cjs',text)
source('evaluate.py',(H/'evaluate.py').read_text(encoding='utf-8-sig').replace('148','60'))
text=(H/'analyze.py').read_text(encoding='utf-8-sig').replace('148','60')
text=replace(text,"mode=='BC_RESOURCE_GUARD' and classes","mode in ['BC_RESOURCE_GUARD','BC_RESOURCE_EDF_NORMAL'] and classes")
text=replace(text,"normal and c['time']>=normal[0]['deadline']","normal and (mode=='BC_RESOURCE_EDF_NORMAL' or c['time']>=normal[0]['deadline'])")
text=replace(text,"reason='NORMAL_ALREADY_LATE_PROGRESS';forced=normal[0]['ordinal']","reason='NORMAL_EDF_PROGRESS' if mode=='BC_RESOURCE_EDF_NORMAL' else 'NORMAL_ALREADY_LATE_PROGRESS';forced=normal[0]['ordinal']")
text=replace(text,"(H.parent/'conclusion_candidate_bridge_20261020',['CPU_RESERVE_SLACK'])", "(H.parent/'conclusion_candidate_bridge_20261020',['CPU_RESERVE_SLACK']),(H.parent/'bc_service_repair_20261020',['BC_RESOURCE_GUARD'])")
text=replace(text,"if row['method'] not in wanted:continue", "if row['method'] not in wanted or row.get('cohort','development32')!='development32':continue")
text=replace(text,"['PPO_FULL','CPU_RESERVE_SLACK'] if name=='development32'", "['PPO_FULL','CPU_RESERVE_SLACK','BC_RESOURCE_GUARD'] if name=='development32'");source('analyze.py',text)
text=(H/'report.py').read_text(encoding='utf-8-sig');text=text.replace("'BC_FULL':'기존 롤링+ATC+BC',","'BC_RESOURCE_EDF_NORMAL':'BC+자원보호+일반 EDF','BC_FULL':'기존 롤링+ATC+BC',")
text=text.replace('기존 32특징·최대27행동 BC 가중치를 유지하고','첫148회에서 드러난 일반 정시율 손실을 보완해 일반 CPU 순위를 EDF로 고정했다. 기존 32특징·최대27행동 BC 가중치를 유지하고')
text=text.replace('기존 추가 입력32 × 새 후보3 =96회, 원 최종4입력 × 새 후보3 =12회, 별도 새8입력 × BC·후보3·EDF =40회, 합계148회다.','기존 추가 입력32 × 새 후보1 =32회, 원 최종4입력 × 새 후보1 =4회, 다시 별도 새8입력 × BC·새 후보·EDF =24회, 합계60회다. 앞선148회와 선정 기록은 그대로 보존했다. 일반 EDF 보완은 개발32의 첫 보호 후보가 일반 정시율을 낮춘 결과를 본 뒤 설계했다.')
text=text.replace('<h2>세 가지 보호 규칙</h2>','<h2>보존한 첫 비교와 이번 추가 규칙</h2><p>이번에는 자원·진행 보호에 일반 EDF를 결합한 한 가지 고정 규칙만 새로 평가했다. 아래 앞선 세 후보는 보존한148회에 속하며, 개발32 표에서 그 결과를 재사용한다. 일반 CPU 경로가 실행 가능하면 가장 이른 납기의 일반 요청을 선택하므로, 일반 순서에는 BC가 개입하지 않는다. 이 구성의 성능을 BC 독립 기여로 주장하지 않는다.</p>')
source('report.py',text)
text=(H/'deliver.py').read_text(encoding='utf-8-sig').replace('148','60');text=replace(text,"E.parent/'conclusion_atc_order_20261020']", "E.parent/'conclusion_atc_order_20261020',E.parent/'bc_service_repair_20261020']")
text=replace(text,"for p in op['original_pins']+op['new_source_pins']:","first=read(H.parent/'bc_service_repair_20261020/FILES.json')\n for p in first['files']:assert sha(R/p['path'])==p['sha256'],'First148 repair file changed: '+p['path']\n for p in op['original_pins']+op['new_source_pins']:")
source('deliver.py',text)
cases=read(H/'INPUTS.json')['cases'];old=[c for c in cases if c['repair_cohort']!='confirm8'];fresh=[]
for ref in [c for c in cases if c['repair_cohort']=='confirm8']:
 c=dict(ref);c['id']=ref['id'].replace('REPAIR_CONFIRM_','REFINEMENT_CONFIRM_')
 def seed(k):return int(hashlib.sha256(('BC_SERVICE_REFINEMENT_20261020|'+c['id']+'|'+k).encode()).hexdigest()[:8],16)
 c.update(stream=seed('latent'),request_seed=seed('requests'),arrival_seed=seed('arrivals'));tasks=['classification']*round(1024*c['mix'])+['detection']*(1024-round(1024*c['mix']));random.Random(c['request_seed']).shuffle(tasks);ar=random.Random(c['arrival_seed']);offsets=[];t=35
 for i in range(1024):
  if c['shape']=='poisson':
   if i:t+=ar.expovariate(c['rate'])
   offsets.append(t)
  else:offsets.append(35+(i//c['burst'])*c['burst']/c['rate'])
 end=offsets[-1]+1/c['rate'] if c['shape']=='poisson' else 35+1024/c['rate'];c.update(duration=end-35,empirical_rate=1024/(end-35),horizon_s=end+90,dispatch_stop_s=end+45,censor_s=end+60,requests=[dict(ordinal=i,offset_ns=round(offsets[i]*1e9),task_id=task,priority='urgent' if task=='classification' else 'normal',deadline_ms=800 if task=='classification' else 2000) for i,task in enumerate(tasks)]);fresh.append(c)
assert len(old)==36 and len(fresh)==8 and not {c['stream'] for c in fresh}&{c['stream'] for c in cases};save(D/'INPUTS.json',dict(cases=old+fresh))
p=read(H/'PROTOCOL.json');p.update(schema='BC_NORMAL_EDF_REFINEMENT60',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='One fixed correction of normal on-time regression seen in development32 of first148; no parameter search.',methods=[dict(id='BC_RESOURCE_EDF_NORMAL',selector='BC_REPAIR',rolling=True,ATC=True),dict(id='BC_FULL',selector='BC',rolling=True,ATC=True),dict(id='EDF_NPU',selector='EDF',rolling=False,ATC=False,mode='EDF_NPU_FIRST')],environment_cap=60,method_groups={'development32':['BC_RESOURCE_EDF_NORMAL'],'original4':['BC_RESOURCE_EDF_NORMAL'],'confirm8':['BC_FULL','BC_RESOURCE_EDF_NORMAL','EDF_NPU']},cases=[c['id'] for c in old+fresh],normal_refinement='Same frozen BC/logits/planner/features/cache/resource/urgent guards. Only change: choose earliest normal request when its CPU action is available regardless of lateness; urgent guard still evaluated first and cannot use reserved CPU. No BC control of normal queue order; report explicitly.',development_evidence='First148 development32 completed: BC_RESOURCE_GUARD nominal85 on91.4754% vs BC94.6737%, urgent100/unfinished0/J778.5017/AP38.7063. This normal-service regression motivates the new EDF rule. Original selection and all first148 outcomes remain intact. New fresh8 uses a new namespace generated before all refinement environments.',automatic_followup='Close this refinement after60; do not automatically add more variants. Further evidence gaps are reported, not patched by seed replacement.')
save(D/'PROTOCOL.json',p)
evidence=[p for p in sorted((H/'artifacts/G001').glob('REPAIR_NEW_*.json')) if read(p).get('cohort')=='development32'];assert len(evidence)==96
save(D/'DEVELOPMENT_EVIDENCE.json',dict(files=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p)) for p in evidence],new_refinement_results_seen=0,new_fresh8_seen=0))
save(D/'SOURCE_DERIVATION.json',dict(parent=H.relative_to(R).as_posix(),parent_guard_sha256=sha(H/'service_guard.cjs'),guard_sha256=sha(D/'service_guard.cjs'),edits=edits,first148_preserved=True,originals_modified=False))
parent=read(H/'OPERATION.json');pins=parent['original_pins']+[dict(path=(H/n).relative_to(R).as_posix(),sha256=sha(H/n)) for n in ['OPERATION.json','PROTOCOL.json','service_guard.cjs','policy.cjs','server.cjs','evaluate.py','physical_auditor.py']]
names=['prepare.py','policy.cjs','service_guard.cjs','server.cjs','preflight.cjs','abi_preflight.cjs','evaluate.py','INPUTS.json','SOURCE_DERIVATION.json','physical_auditor.py','analyze.py','report.py','deliver.py','DEVELOPMENT_EVIDENCE.json']
save(D/'OPERATION.json',dict(schema='NEW_LOCAL_FIXED_REFINEMENT60',utc=p['utc'],environment_cap=60,wall_cap_s=7200,per_case_wall_cap_s=180,ownheavy_limit=1,global_Python_limit=2,minimum_free_memory_bytes=1536*1024**2,disk_min_free_bytes=8*1024**3,shared_mutex=parent['shared_mutex'],python=parent['python'],node=parent['node'],protocol_sha256=sha(D/'PROTOCOL.json'),original_pins=pins,new_source_pins=[dict(path=(D/n).relative_to(R).as_posix(),sha256=sha(D/n)) for n in names],authorization=p['authorization'],budget_lineage='New separate60 within requested BC improvement; first148 preserved, total208 new guard evaluations. Previous512/historicalSIM512500/12 untouched, no reservation/automation query/refund.'))
save(D/'STATUS.json',dict(status='REGISTERED_WAIT_FIRST148_COMPLETE_AND_AUDITED',official_final_unchanged=True,cap=60,next_actions=['Preflight once after first148 releases common mutex','Evaluate one fixed normal-EDF refinement and new fresh8, no more variants','Audit all outcomes and preserve first148 and official final'],blockers=[]))
print('REGISTERED_FIXED_REFINEMENT60, first148 unchanged; total208',flush=True)
