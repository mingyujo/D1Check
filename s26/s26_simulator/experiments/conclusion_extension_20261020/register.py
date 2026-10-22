"""New finite follow-up; preserve every adopted/previous artifact. No plant here."""
import datetime, hashlib, json, random, subprocess
from pathlib import Path
H=Path(__file__).resolve().parent; R=H.parents[2]; S=R/'s26_simulator'
F=S/'experiments/rolling_rl_ablation_v1'; G=S/'experiments/route_group_learning_v1'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 with p.open('x',encoding='utf-8',newline='\n') as f: json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False); f.write('\n')
assert not (H/'OPERATION.json').exists(), 'Registration already consumed'
assert subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='codex/s26-simulator-handoff-20261016'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='6cd0321ad87df72c8d24f94b0e3b8d66b604ae5f'
assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=R,text=True).strip()
original=(G/'policy.cjs').read_text(encoding='utf-8-sig'); text=original; changes=[]
text=text.replace("require('./source/","require('../route_group_learning_v1/source/").replace("require('./physics.cjs')","require('../route_group_learning_v1/physics.cjs')").replace("require('./public_observer.cjs')","require('../route_group_learning_v1/public_observer.cjs')")
def change(a,b):
 global text
 assert text.count(a)==1,a
 changes.append(dict(old=a,new=b)); text=text.replace(a,b)
change('numerical_failures:0};}', 'numerical_failures:0,ATC_evaluations:0,nominal_timing_calls:0,rollout_calls:0};}')
change('const p=tm.lengths(packet,nom,r,obs.sensor.AP,[],model,q.priority);', 'const p=tm.lengths(packet,nom,r,obs.sensor.AP,[],model,q.priority);state.nominal_timing_calls++;')
change('const mean=candidates.reduce', 'if(!state.useATC){for(const c of candidates)c.ATC=0;return candidates;}state.ATC_evaluations+=candidates.length;const mean=candidates.reduce')
change('function evaluate(obs,packet,nom,model,first,past){const physics=', 'function evaluate(obs,packet,nom,model,first,past){state.rollout_calls++;const physics=')
change('state.calls++;if(state.balance)obs=routeContext(obs);', "state.calls++;if(state.balance)obs=routeContext(obs);if(state.standalone)return require('../teacher_components_20261019/helpers.cjs').standalone(obs,config,state,rc);")
change('const ranked=all.slice().sort((a,b)=>b.ATC-a.ATC||FIFO(a.q,b.q)||a.p.response-b.p.response||a.p.occupied-b.p.occupied||a.route.localeCompare(b.route));', 'const ranked=state.useATC?all.slice().sort((a,b)=>b.ATC-a.ATC||FIFO(a.q,b.q)||a.p.response-b.p.response||a.p.occupied-b.p.occupied||a.route.localeCompare(b.route)):all.slice().sort((a,b)=>a.q.deadline-b.q.deadline||FIFO(a.q,b.q)||rc.ROUTES.indexOf(a.route)-rc.ROUTES.indexOf(b.route));')
change("if(state.variant!=='FROZEN_BASE')for(let k=0;", "if(state.useRolling&&state.variant!=='FROZEN_BASE')for(let k=0;")
change("const forecastReady=state.variant!=='FROZEN_BASE'?queue.filter(q=>forecastSet.has(q.ordinal)):ready;", "const forecastReady=state.useRolling&&state.variant!=='FROZEN_BASE'?queue.filter(q=>forecastSet.has(q.ordinal)):ready;")
change('const publicWork=forecastReady.reduce', 'const publicWork=!state.useRolling?0:forecastReady.reduce')
change("const forecastHorizon=state.variant!=='FROZEN_BASE'?", "const forecastHorizon=!state.useRolling?obs.time:state.variant!=='FROZEN_BASE'?")
change("else{f=evaluate(visible,packet,nom,model,a.kind==='WAIT_EVENT'", "else{f=!state.useRolling?{cost:[0,0,0,0,0],AP_end:30,candidate_response:null,nominal_unfinished:0,ablated:true}:evaluate(visible,packet,nom,model,a.kind==='WAIT_EVENT'")
change('past);state.actual++;', 'past);if(state.useRolling)state.actual++;')
change('forecasts.push(f);state.forecasts++;', 'forecasts.push(f);if(state.useRolling)state.forecasts++;')
change("if(row.length!==WIDTH||row.some", "if(!state.useRolling)for(let k=21;k<=29;k++)row[k]=0;if(row.length!==WIDTH||row.some")
change('forecast_calls:actions.length,decision_index:index', 'forecast_calls:state.useRolling?actions.length:0,decision_index:index')
text+='\nmodule.exports.telemetry=()=>({ATC_evaluations:state.ATC_evaluations,nominal_timing_calls:state.nominal_timing_calls,rollout_calls:state.rollout_calls,selector_calls:state.calls});\n'
with (H/'policy.cjs').open('x',encoding='utf-8',newline='\n') as f: f.write(text)
save(H/'SOURCE_DERIVATION.json',dict(original_path=(G/'policy.cjs').relative_to(R).as_posix(),original_sha256=sha(G/'policy.cjs'),new_sha256=sha(H/'policy.cjs'),edits=changes,relative_require_relocation=True,originals_modified=False))

# New random namespaces and arrival shapes, not a repeat of a completed case.
old=read(F/'INPUTS.json')['cases']; cases=[]
families=[('BURST16_085','burst',16,.85),('SMOOTH_085','smooth',1,.85),('POISSON_085','poisson',1,.85),('BURST32_105','burst',32,1.05)]
for family,shape,burst,load in families:
 for mix in [.5,.75]:
  reference=next(c for c in old if c['mix']==mix)
  for rep in range(4):
   label=f'NEW_{family}_C{int(mix*100)}_R{rep}'
   def seed(kind): return int(hashlib.sha256(('S26_CONCLUSION_EXTENSION_20261020|'+label+'|'+kind).encode()).hexdigest()[:8],16)
   rng=random.Random(seed('requests')); arrivals=random.Random(seed('arrivals'))
   tasks=['classification']*round(1024*mix)+['detection']*(1024-round(1024*mix));rng.shuffle(tasks)
   rate=reference['nominal_capacity_requests_s']*load; duration=1024/rate; offsets=[]; t=35.
   for i in range(1024):
    if shape=='poisson':
     if i:t+=arrivals.expovariate(rate)
     offsets.append(t)
    else: offsets.append(35+(i//burst)*burst/rate)
   supply_end=(offsets[-1]+1/rate) if shape=='poisson' else 35+duration
   requests=[dict(ordinal=i,offset_ns=round(offsets[i]*1e9),task_id=task,priority='urgent' if task=='classification' else 'normal',deadline_ms=800 if task=='classification' else 2000) for i,task in enumerate(tasks)]
   cases.append(dict(id=label,n=1024,mix=mix,nominal_load_ratio=load,nominal_capacity_requests_s=reference['nominal_capacity_requests_s'],rate=rate,duration=supply_end-35,empirical_rate=1024/(supply_end-35),family=family,shape=shape,burst=burst,replicate=rep,phase='FOLLOWUP_EVAL',model='CPU3',stream=seed('latent'),request_seed=seed('requests'),arrival_seed=seed('arrivals'),context=reference['context'],requests=requests,horizon_s=supply_end+90,dispatch_stop_s=supply_end+45,censor_s=supply_end+60))
assert len(cases)==32 and len({c['stream'] for c in cases})==32
assert not ({c['stream'] for c in cases}&{c['stream'] for c in old})
save(H/'INPUTS.json',dict(schema='NEW_FOLLOWUP_INPUTS32',cases=cases))
methods=[dict(id='TEACHER_ONLY',rolling=False,ATC=False,standalone=True,selector='TEACHER'),dict(id='EDF_NPU',rolling=False,ATC=False,mode='EDF_NPU_FIRST',selector='EDF'),dict(id='EDF_GPU',rolling=False,ATC=False,mode='EDF_GPU_FIRST',selector='EDF'),dict(id='BC_FULL',rolling=True,ATC=True,selector='BC'),dict(id='BC_NO_ROLLING',rolling=False,ATC=True,selector='BC'),dict(id='BC_NO_ATC',rolling=True,ATC=False,selector='BC'),dict(id='BC_NO_BOTH',rolling=False,ATC=False,selector='BC'),dict(id='PPO_FULL',rolling=True,ATC=True,selector='PPO'),dict(id='ROLLING_COST',rolling=True,ATC=True,selector='COST'),dict(id='ROLLING_SERVICE_FIRST',rolling=True,ATC=True,selector='SERVICE_FIRST')]
bc=read(S/'experiments/bc_matched_eval_20261019/PROTOCOL.json')
protocol=dict(schema='S26_CONCLUSION_EXTENSION_20261020',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),user_request='Preserve existing official final; additional research authorized; user alone decides adoption.',
 purpose='Test whether learned policies justify planning/ATC complexity and generalize beyond previously observed burst16 FAIR8; assess a fixed service-first rolling selector without fitting.',
 cases=[c['id'] for c in cases],methods=methods,environment_cap=320,training=0,measurements=0,physical_fits=0,
 inputs='4 arrival/load families x 2 previously calibrated mix-reference capacities x 4 new request/arrival/latent seeds. N1024, classification urgent0.8s/detection normal2s only. Exact mix totals shuffled. Poisson first arrival35 then independent exponential gaps, no rescaling; empirical rate reported. Same observed initial context. Nominal capacity inherited as reference, not measured actual saturation.',
 selection='One frozen BC and adopted frozen PPO881087, physical mask then argmax, temperature0.35, same32/27 ABI. No retraining, search, fallback or deadline shield.',
 BC_lineage='BC_COMMON_FINAL includes earlier PPO ancestry; BC means frozen immediately before the last PPO stage, not a PPO-free training lineage.',
 ablations='BC_NO_ROLLING skips future rollout/publicWork/horizon extension and zeros features21..29, retaining measured-state power18 and instantaneous timing9,10. BC_NO_ATC zeros feature11, skips ATC scoring and uses EDF/FIFO/route fill for candidate selection. Both retain original8 candidates and causal route preference. Frozen runtime/input intervention, not retrained architecture; distribution shift limits interpretation.',
 service_first='Fixed lexicographic minimize [predicted urgent lateness cost2, unfinished cost4, normal lateness cost3, cost0/0.6215900945595554+cost1/0.42450663682233236], each rounded to1e-12; then max ATC11, ordinal, index. Uses only public nominal predictions. No parameter tuning or hard action mask.',
 primary_comparisons=['BC_FULL vs TEACHER_ONLY','PPO_FULL vs BC_FULL','BC_NO_ROLLING/BC_NO_ATC/BC_NO_BOTH vs BC_FULL','ROLLING_SERVICE_FIRST vs TEACHER_ONLY and EDF_NPU'],
 practical_thresholds=dict(service_gain_pp=1.,urgent_noninferiority_pp=.1,energy_gain_percent=1.,service_equivalence_pp=.1,unfinished_increase_allowed=0),
 decision_rule='Meaningful candidate improvement requires >=1pp overall on-time gain with urgent loss<=0.1pp, no more unfinished; OR >=1% paired mean API-J reduction with both urgent and overall on-time within0.1pp and no more unfinished. Report all families/cases/worst-case, P95 and failures. Passing is conditional model evidence, not adoption or real-device proof. No significance claim from requests as independent samples.',
 order='Fixed case order; rotate10 method order by case index. One attempt per identity, preserve every failure; no replacement seed or completed rerun.',
 offline='Existing8 BC banks: exact saved argmax reproducibility and masking21..29/11/both/31 sensitivity, no plant. Mechanism diagnosis on prior cohort, not new validation.',
 preflight='No plant: exact full-mode bank/action compatibility versus original FAIR policy on saved public/crowded fixtures; ablation feature/guard tests and deterministic selector fixtures. Pin sources, checkpoints, input before new plant.',
 common='Original FAIR physical engine/power/thermal/CPU3/nonpreemptive actual AVAILABLE and full observation horizon unchanged. No fabricated task-priority transfer or thermal modification.',
 checkpoint=bc['checkpoint'],checkpoint_sha256=bc['checkpoint_sha256'],network_sha256=bc['network_sha256'],ppo_checkpoint='s26_simulator/experiments/route_group_learning_v1/artifacts/G001/S881087_FINAL.pt.gz',ppo_checkpoint_sha256='4a2c5b1d38da76bdef7f33c6eee6a4c69451130a68eb8e7168f0d760d37e2e34',
 shared_scores=dict(scales=[.6215900945595554,.42450663682233236],dual=[.98,.98]),
 physical_gate='FAIL remains: API-J/AP only; CPU3 extra-core, interference and mobile NN/planner costs unmeasured; fixed measured template pools and shared initial context constrain generality.',adopted=False,automatic_retry=False,refunds=0,completed_reruns=0)
save(H/'PROTOCOL.json',protocol)
prev=read(S/'experiments/bc_matched_eval_20261019/OPERATION.json')
pins=[p for p in prev['original_pins'] if '.raw.json.gz' not in p['path'] and '.frames.pt.gz' not in p['path']]
extra=[S/'experiments/teacher_components_20261019/helpers.cjs',S/'experiments/teacher_components_20261019/policy.cjs']+list((S/'experiments/bc_matched_eval_20261019/artifacts/G001').glob('*.banks.jsonl.gz'))
teacher_row=next(r for r in read(F/'artifacts/G001/RESULT.json')['rows'] if r['method']=='TEACHER_RULE')
extra.append(F/'artifacts/G001'/(teacher_row['label']+'.raw.json.gz'))
for p in extra:pins.append(dict(path=p.relative_to(R).as_posix(),sha256=sha(p)))
for p in pins:assert sha(R/p['path'])==p['sha256'],p['path']
names=['register.py','policy.cjs','server.cjs','worker.py','preflight.cjs','SOURCE_DERIVATION.json','INPUTS.json']
op=dict(schema='NEW_LOCAL_FINITE320_NOT_PREVIOUS_QUOTA',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),environment_cap=320,wall_cap_s=7200,per_case_wall_cap_s=180,ownheavy_limit=1,global_Python_limit=2,minimum_free_memory_bytes=1536*1024**2,disk_min_free_bytes=8*1024**3,shared_mutex=prev['shared_mutex'],python=prev['python'],node=prev['node'],protocol_sha256=sha(H/'PROTOCOL.json'),original_pins=pins,new_source_pins=[dict(path=(H/n).relative_to(R).as_posix(),sha256=sha(H/n)) for n in names],authorization=protocol['user_request'],budget_lineage='New separately authorized local follow-up cap320; no refund, previous-quota reset, reservation/automation query or cross-host ledger edit.')
save(H/'OPERATION.json',op)
save(H/'STATUS.json',dict(status='REGISTERED_NOT_STARTED',HEAD='6cd0321ad87df72c8d24f94b0e3b8d66b604ae5f',official_final_unchanged=True,next_actions=['Preflight and frozen-feature mechanism diagnosis','Execute registered320 once only','Audit and propose conclusion; user decides adoption'],blockers=[]))
print('REGISTERED new32 inputs x10 methods =320, no training, no final replacement',flush=True)
