"""Derive isolated BC guard sources,44 input identities and finite148 registration."""
import datetime,hashlib,json,random,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent/'conclusion_extension_20261020';G=H.parent/'route_group_learning_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def source(p,s):
 with p.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
assert not (H/'OPERATION.json').exists();assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=R,text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='6cd0321ad87df72c8d24f94b0e3b8d66b604ae5f'
original=(E/'policy.cjs').read_text(encoding='utf-8-sig');text=original;edits=[]
def change(old,new):
 global text
 assert text.count(old)==1,old
 text=text.replace(old,new);edits.append(dict(old=old,new=new))
change("const WEIGHTS=", "const guard=require('./service_guard.cjs');\nconst WEIGHTS=")
change('state={...options,waitByHead:', "state={...options,guardMode:options.guardMode??'BC_FULL',waitByHead:")
change('rollout_calls:0};}', 'rollout_calls:0,guard_none:0,guard_timing_calls:0,guard_reason_counts:{}};}')
needle=' const memo=new Map;const x='
insert=""" let guardPlan=null;
 if(state.guardMode!=='BC_FULL'){
  const np=state.guardMode==='BC_RESOURCE_GUARD'?tm.lengths(packet,nom,'classification_NPU',obs.sensor.AP,[],model,'urgent'):null;
  if(np)state.guard_timing_calls++;
  guardPlan=guard.plan(state.guardMode,obs,actions,all.map(c=>({ordinal:c.q.ordinal,route:c.route,response:c.p.response,occupied:c.p.occupied})),np&&{response:np.response,occupied:np.occupied});
  if(!guardPlan.allowed_indices.length){state.guard_none++;return {kind:'NONE',candidates:[]};}
  state.guard_reason_counts[guardPlan.reason]=(state.guard_reason_counts[guardPlan.reason]??0)+1;
 }
 const memo=new Map;const x="""
change(needle,insert)
change(' const index=['," if(guardPlan){bank.guard=guardPlan;bank.constraints={base_physical_mask_only:true,post_neural_guard:true,deadline_protection:state.guardMode!=='BC_DISPATCH_ONLY',new_training:false};}\n const index=[")
change('selector_calls:state.calls});','selector_calls:state.calls,guard_none:state.guard_none,guard_timing_calls:state.guard_timing_calls,guard_reason_counts:state.guard_reason_counts});')
source(H/'policy.cjs',text)
server=(E/'server.cjs').read_text(encoding='utf-8-sig')
server=server.replace('standalone:m.standalone??false,','standalone:m.standalone??false,guardMode:cmd.method,')
server=server.replace("send({type:'BANK',bank});", "send({type:'BANK',bank});")
# Original4 guard checks use the same original input IDs but NEW guard method identities, never an old run.
dev=read(E/'INPUTS.json')['cases'];old=[c for c in read(G/'INPUTS.json')['cases'] if c.get('phase')=='EVAL' and c['nominal_load_ratio']==.85]
assert len(dev)==32 and len(old)==4
old=[dict(c,family='ORIGINAL85',replicate=c.get('replicate',i),rate=c['nominal_capacity_requests_s']*.85,empirical_rate=c['nominal_capacity_requests_s']*.85) for i,c in enumerate(old)]
fresh=[]
for ref in [c for c in dev if c['replicate']==0]:
 c=dict(ref);c['id']='REPAIR_CONFIRM_'+ref['family']+'_C'+str(int(ref['mix']*100))+'_R0';c['phase']='REPAIR_CONFIRM'
 def seed(k):return int(hashlib.sha256(('BC_SERVICE_REPAIR_20261020|'+c['id']+'|'+k).encode()).hexdigest()[:8],16)
 c.update(stream=seed('latent'),request_seed=seed('requests'),arrival_seed=seed('arrivals'),replicate=0)
 tasks=['classification']*round(1024*c['mix'])+['detection']*(1024-round(1024*c['mix']));random.Random(c['request_seed']).shuffle(tasks);ar=random.Random(c['arrival_seed']);offsets=[];t=35
 for i in range(1024):
  if c['shape']=='poisson':
   if i:t+=ar.expovariate(c['rate'])
   offsets.append(t)
  else:offsets.append(35+(i//c['burst'])*c['burst']/c['rate'])
 end=offsets[-1]+1/c['rate'] if c['shape']=='poisson' else 35+1024/c['rate']
 c.update(duration=end-35,empirical_rate=1024/(end-35),horizon_s=end+90,dispatch_stop_s=end+45,censor_s=end+60,requests=[dict(ordinal=i,offset_ns=round(offsets[i]*1e9),task_id=task,priority='urgent' if task=='classification' else 'normal',deadline_ms=800 if task=='classification' else 2000) for i,task in enumerate(tasks)]);fresh.append(c)
assert len(fresh)==8 and len({c['stream'] for c in dev+old+fresh})==44
cases=[dict(c,repair_cohort=cohort) for cohort,items in [('development32',dev),('original4',old),('confirm8',fresh)] for c in items]
save(H/'INPUTS.json',dict(cases=cases))
methods=['BC_DISPATCH_ONLY','BC_PROGRESS_GUARD','BC_RESOURCE_GUARD'];eprotocol=read(E/'PROTOCOL.json')
p={**eprotocol,'schema':'BC_SERVICE_REPAIR148_PRE_REGISTERED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authorization':'User explicitly requests reducing urgent deadline failures/unfinished while retaining rolling+ATC+BC energy/heat savings; preserve existing official policy.','purpose':'Frozen32-feature BC plus transparent post-neural progress/resource safeguards, no retraining.','methods':[dict(id=m,selector='BC_REPAIR',rolling=True,ATC=True) for m in methods]+[dict(id='BC_FULL',selector='BC',rolling=True,ATC=True),dict(id='EDF_NPU',selector='EDF',rolling=False,ATC=False,mode='EDF_NPU_FIRST')],'environment_cap':148,'method_groups':{'development32':methods,'original4':methods,'confirm8':['BC_FULL']+methods+['EDF_NPU']},'cases':[c['id'] for c in cases],
 'guards':{'BC_DISPATCH_ONLY':'Choose maximum unchanged BC logit among physical DISPATCH actions, prohibit voluntary WAIT only.','BC_PROGRESS_GUARD':'Dispatch-only plus earliest urgent nominal response+one occupancy deadline-risk protection; if risky prefer nominal-on-time routes, else fastest. If not urgent-risk and oldest normal already late, dispatch that oldest normal.','BC_RESOURCE_GUARD':'Progress guard plus CPU inference slot reserved for detection and NPU-first classification; GPU allowed only when NPU occupied and visible NPU-only EDF prefix projects a missed deadline. Same nominal predictor and zero extra margin. Owner charged one full nominal occupancy, no hidden remaining progress.'},
 'architecture':'Original frozen BC network,32 features/27 original physical-mask logits unchanged. A separate explicit guard selects the greatest original logit among its admissible original actions. Empty resource envelope returns NONE before rollout/NN. Not pure BC, not PPO, and no learned improvement claim.',
 'selection_rule':'Before any confirm8 execution, choose one fixed guard using development32+original4 only. Eligible: all original4 urgent100%/unfinished0, original4 on-time no worse than BC by0.1pp, mean J <=1.01*BC and AP<=BC+0.1C; development nominal85 unfinished0, urgent>=99.9%, J<=1.01*BC and AP<=BC+0.1C. If any eligible, minimize development stress urgent misses, then nominal85 J, then method order. Otherwise choose lexicographically [original4 urgent misses+unfinished,nominal85 unfinished,nominal85 urgent misses,nominal85 J] and mark target unmet. Confirm8 cannot change this selection.',
 'reporting':'Separate original4/development32/confirm8 and85/105 subgroups; all methods/cases/failures. Raw BC energy includes missing work, so do not call its difference equal-service savings. Compare service-qualified savings against same-input completed EDF; report both NPU/GPU reference where available, retained gap and extra completed work. Max normal latency included.',
 'confirmation':'8 new synthetic inputs, one per family/mix, generated before all new evaluations. Limited repetition and same measured pools/model/initial context; not independent device confirmation. All3 guards disclosed even if selected guard fails.','cache':'Retain existing cached original features to isolate service-guard contribution. Known cache-equivalence FAIL is preserved; this study does not fix/calibrate predictor.','common':'No original physical engine/coefficients/deadlines/observation window/model/NN weights changed; no new learning/device measurement/fit. Separate method identities for old inputs; completed original methods never rerun. No parameter search, retry, seed replacement, refund, reservation/automation query or resume.','adopted':False}
save(H/'PROTOCOL.json',p)
source(H/'server.cjs',server)
source(H/'abi_preflight.cjs',(E/'preflight.cjs').read_text(encoding='utf-8-sig').replace('PREFLIGHT.json','PREFLIGHT_ABI.json'))
# Audit source version is isolated; account physical execution independently and explicitly permit the declared post-NN guard contract.
audit=(E/'analyze.py').read_text(encoding='utf-8-sig');audit=audit.replace("need(b['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False),'No hidden deadline mask')", "need(b['constraints']==(dict(base_physical_mask_only=True,post_neural_guard=True,deadline_protection=m['id']!='BC_DISPATCH_ONLY',new_training=False) if m['selector']=='BC_REPAIR' else dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)),'Explicit original/repair constraints')")
source(H/'physical_auditor.py',audit)
save(H/'SOURCE_DERIVATION.json',dict(parent_policy_sha256=sha(E/'policy.cjs'),policy_sha256=sha(H/'policy.cjs'),edits=edits,parent_auditor_sha256=sha(E/'analyze.py'),physical_auditor_sha256=sha(H/'physical_auditor.py'),originals_modified=False))
parent=read(E/'OPERATION.json');pins=parent['original_pins']+[dict(path=(E/n).relative_to(R).as_posix(),sha256=sha(E/n)) for n in ['OPERATION.json','PROTOCOL.json','INPUTS.json','policy.cjs','worker.py','ANALYSIS.json','artifacts/G001/RESULT.json']]
for pp in [G/'INPUTS.json',R/'s26_simulator/FINAL_POLICY.json',R/'s26_simulator/FINAL_POLICY_KO.md',H.parent/'conclusion_extension_20261020/DELIVERY_CHECK.json']:
 pins.append(dict(path=pp.relative_to(R).as_posix(),sha256=sha(pp)))
names=['prepare.py','policy.cjs','service_guard.cjs','server.cjs','preflight.cjs','abi_preflight.cjs','evaluate.py','INPUTS.json','SOURCE_DERIVATION.json','physical_auditor.py']
save(H/'OPERATION.json',dict(schema='NEW_LOCAL_BC_REPAIR148',utc=p['utc'],environment_cap=148,wall_cap_s=10800,per_case_wall_cap_s=180,ownheavy_limit=1,global_Python_limit=2,minimum_free_memory_bytes=1536*1024**2,disk_min_free_bytes=8*1024**3,shared_mutex=parent['shared_mutex'],python=parent['python'],node=parent['node'],protocol_sha256=sha(H/'PROTOCOL.json'),original_pins=pins,new_source_pins=[dict(path=(H/n).relative_to(R).as_posix(),sha256=sha(H/n)) for n in names],authorization=p['authorization'],budget_lineage='New finite148 authorization; prior512 and historical SIM512500/12 preserved, no new remote reservation query/refund/reset.'))
save(H/'STATUS.json',dict(status='REGISTERED_NOT_STARTED',official_final_unchanged=True,cap=148,next_actions=['Preflight new guards, confirm full feature ABI and independent guard oracle','Evaluate new guards on development32 and original4; freeze selection before confirm8','Run confirm8 once, audit saved results, report all tradeoffs without adoption'],blockers=[]))
print('REGISTERED isolated BC repair148; training0; original final preserved',flush=True)
