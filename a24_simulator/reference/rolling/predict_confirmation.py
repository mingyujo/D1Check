"""Prepare and, only after separate parent registration, predict new CONFIRM8.

--prepare: pure input/schema/source binding only; no environment/CostState/NN.
--execute: exactly eight frozen A24INT_G002 environments, TREND27; cost-only
MEASURED35 observes the same saved dispatch/AVAILABLE trace. Never opens new
measured output/summary/runtime request results or post-common sensor payloads.

Parent registration O/NEW_CONFIRM_OPERATION_REGISTERED.json must contain:
schema=A24-new-confirm-prediction-operation-v1, operator_sha256, generation,
generation_sha256, registration_sha256, execution_plan_sha256, input_plan_sha256,
input_audit_sha256, max_environment_starts=8, allow_execution=true.
It must also pin trace_auditor_path/trace_auditor_sha256 before any START.
"""
from __future__ import annotations
import argparse, copy, gzip, hashlib, json, os, pathlib, sys, time

B=pathlib.Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
W=B/'work/A24-INTEGRATED-SIM-20261016-G002';O=B/'outputs/A24-INTEGRATED-SIM-20261016-G002'
I=O/'new_confirmation_inputs';P=O/'new_confirmation_predictions'
GENERATION='A24INT_G002';G=W/'source_generations'/GENERATION
STAGE='NEW_CONFIRM_PREDICTION'
POLICY_MAP={
 'R02_SUITE_C252_CPU':'FIFO_SERIAL_CPU',
 'R02_SUITE_C252_GPU':'FIFO_SERIAL_CG',
 'R02_SUITE_M128_BASE':'FIFO_SERIAL_CG',
 'R02_SUITE_M128_PAIR_G':'FIFO_PAIR_CG',
 'R02_SUITE_M128_WAIT200':'FIFO_WAIT_CG',
 'R02_SUITE_L64_PAIR_G':'FIFO_PAIR_CG',
}
EXPECTED_IDS={
 'c8e507d1-6c8a-5886-b1a1-6aa57592ca7f','f4509bdc-0506-5d01-a6c7-86aea91f4bdc',
 '1fcf4cae-cc5d-5f3a-9cff-b16fd51354b2','218e1e4a-a0f0-5877-8128-a98d2e16b95c',
 '6ef44c80-c6e0-5170-9f2a-9eabc5dda4ba','d779348d-80ea-5cad-94cb-4ae7842a8812',
 '3f895cc8-8e5d-5aa5-9f54-16641274b7e6','a3f3e308-51d7-57c9-9ed7-c4a0e4b8d001'}

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def modules():
 # Production code and registry are imported from exact immutable generation.
 sys.path.insert(0,str(G))
 import registry,a24_engine,a24_cost_adapter,timing_bridge
 return registry,a24_engine,a24_cost_adapter,timing_bridge

def verify_source_bindings(registry):
 reg=read(O/'REGISTRATION.json');gen=read(G/'GENERATION.json')
 for path,h in {**reg['protected'],**gen['source_hashes']}.items():
  if sha(path)!=h:raise RuntimeError('Protected/frozen SHA mismatch: '+path)
 if reg['budget']['new_confirmation_cap']!=8:raise RuntimeError('Registered new confirmation cap must be8')
 return reg,gen

def initial_projection(sid):
 ap_path=I/sid/'INITIAL_AP_PRECOMMON_60S.json';ap=read(ap_path)
 source=I/sid/'INITIAL_AP_SOURCE_LINES.jsonl'
 if ap['session_id']!=sid or ap['after_common_temperature_payloads_interpreted']!=0:raise ValueError('Initial AP provenance')
 pre=[]
 for row in sorted(ap['points'],key=lambda r:r['relative_read_end_ns']):
  lo,hi=row['relative_read_start_ns'],row['relative_read_end_ns']
  if not -60*10**9<=lo<=hi<=0:raise ValueError('Future/outside initial read')
  # Existing adapter takes completed read upper bound, not unobserved sensor time.
  pre.append({'t':hi/1e9,'lo':lo/1e9,'hi':hi/1e9,'ap':float(row['AP_c'])})
 return {'device':'A24','context_id':'NEW_CONFIRM_'+sid+'_PRECOMMON60','pre':pre,
  'energy_baseline_mode':'HISTORICAL_A24_FIXED_GAUGE_MODEL',
  'provenance':{'source_path':str(source),'source_sha256':sha(source),'session_id':sid,
   'common_ns':ap['common_origin_ns'],'temperature_channel':'AP','clock':'device_uptime_bracket',
   'source_role':'completed_precommon','initial_AP_projection_path':str(ap_path),
   'initial_AP_projection_sha256':sha(ap_path),'full_HAL_member_binding':ap['HAL_binding'],
   'common_event_binding':ap['common_binding'],'source_line_bindings':[
     {'line':x['source_line'],'sha256':x['source_line_sha256']} for x in ap['points']],
   'time_axis':'read-completion upper bound relative to common_start.origin_ns',
   'sensor_timestamp_provided':False,'cache_age_known':False,'future_values_used':0}}

def prepare():
 registry,engine,adapter,timing=modules();reg,gen=verify_source_bindings(registry)
 if (P/'PREDICTION_EXECUTION_PLAN.json').exists():raise RuntimeError('Immutable execution plan exists')
 inp=read(I/'PREDICTION_PLAN.json');audit=read(I/'INPUT_AUDIT.json')
 if audit['status']!='PASS' or audit['plan_sha256']!=sha(I/'PREDICTION_PLAN.json'):raise RuntimeError('Input audit not bound')
 if inp['new_sessions']!=8 or {x['session_id'] for x in inp['sessions']}!=EXPECTED_IDS:raise RuntimeError('Exact new8 roster')
 cases=[]
 def save_exact(path,obj):
  if pathlib.Path(path).exists():
   if pathlib.Path(path).read_bytes()!=registry.canonical(obj):raise RuntimeError('Partial input differs; no overwrite '+str(path))
  else:registry.save(path,obj)
 for i,s in enumerate(inp['sessions']):
  sid=s['session_id'];folder=I/sid
  for name,h in s['files'].items():
   if sha(folder/name)!=h:raise RuntimeError('Frozen input artifact SHA')
  recipe=read(folder/'RECIPE_COMPATIBLE_INPUT.json');comp=read(folder/'CONTRACT_COMPARISON.json')
  if not comp['controller_and_model_binding_compatible'] or comp['contract_differences']:raise ValueError('Unsupported contract '+sid)
  rule=POLICY_MAP[recipe['policy_id']]
  if rule=='FIFO_WAIT_CG' and (recipe['wait_ms']!=200 or recipe['wait_groups']!=list(range(16))):raise ValueError('WAIT recipe mismatch')
  sc=timing.compile_scenario(recipe,split=STAGE)
  initial=adapter.validate_initial(initial_projection(sid)) # validates only, no CostState.
  dest=P/'prepared_inputs'/sid
  save_exact(dest/'INITIAL_PUBLIC.json',initial)
  save_exact(dest/'SCENARIO.json',engine.wire(sc))
  source_inputs={str(folder/name):h for name,h in s['files'].items()}
  source_inputs[str(dest/'INITIAL_PUBLIC.json')]=sha(dest/'INITIAL_PUBLIC.json')
  source_inputs[str(dest/'SCENARIO.json')]=sha(dest/'SCENARIO.json')
  label=f'NEW_CONFIRM_{GENERATION}_{i+1:02}_{sid}'
  cfg={'stage':STAGE,'generation':GENERATION,'session_id':sid,'bank':recipe['bank'],
   'rule':rule,'model':'TREND27','secondary_observer_model':'MEASURED35','sample_seed':491000+i,
   'family':rule,'alpha':.95,'allow_wait':rule=='FIFO_WAIT_CG','decision_mode':'EVENT',
   'scenario_sha256':digest(engine.wire(sc)),'initial_binding_sha256':digest(initial),
   'initial_path':str(dest/'INITIAL_PUBLIC.json'),'scenario_path':str(dest/'SCENARIO.json'),
   'recipe_input_sha256':sha(folder/'RECIPE_COMPATIBLE_INPUT.json'),
   'input_manifest_sha256':sha(folder/'INPUT_MANIFEST.public.json'),
   'policy_mapping_sha256':digest(POLICY_MAP),'input_plan_sha256':sha(I/'PREDICTION_PLAN.json'),
   'operator_sha256':sha(__file__),'bound_source_inputs':source_inputs}
  cases.append({'session_id':sid,'label':label,'config':cfg,'expected_identity':registry.digest([GENERATION,label,cfg])[:28]})
 plan={'schema':'A24-new-confirm8-execution-plan-v1','status':'INPUTS_AND_OPERATOR_BOUND_NOT_EXECUTED',
  'generation':GENERATION,'generation_sha256':sha(G/'GENERATION.json'),'registration_sha256':sha(O/'REGISTRATION.json'),
  'operator_sha256':sha(__file__),'input_plan_sha256':sha(I/'PREDICTION_PLAN.json'),'input_audit_sha256':sha(I/'INPUT_AUDIT.json'),
  'profile_path':str(O/'DEV_PROFILE_NORMALIZED.json'),'profile_sha256':sha(O/'DEV_PROFILE_NORMALIZED.json'),
  'policy_map':POLICY_MAP,'cases':cases,'environments':8,'cost_wrapper_instances':16,
  'sample_seed_rule':'491000+i; i follows the previously sealed PREDICTION_PLAN.sessions order',
  'stage':STAGE,'observed_outputs_parsed':0,'postcommon_observed_temperature_parsed':0,'new_NN':0,'fit':0,
  'assumptions':['shared canonical SERIAL whole DEV vectors; ideal redispatch0; no heat→time feedback',
   'FIFO_WAIT_CG nominal200ms once per first16burst; measured timer overrun is not replayed',
   'new measured J unqualified; historical cost predictions are conditional',
   'same ownership trace for two cost observers; no second environment',
   'published normal-completion selection; offline result-blind ordering is not contemporaneous prospective validation']}
 registry.save(P/'PREDICTION_EXECUTION_PLAN.json',plan)
 print(json.dumps({'status':plan['status'],'execution_plan_sha256':sha(P/'PREDICTION_EXECUTION_PLAN.json'),'environment_starts':0}))

def cost_observe_trace(result,initial,models,adapter,registry,env_identity,raw_sha):
 name='MEASURED35';sid=result['manifest']['config']['session_id']
 wrapper_id=digest([env_identity,name,'SAME_DISPATCH_AVAILABLE_TRACE'])[:28]
 registry.append(P/'cost_observer_receipts.jsonl',{'event':'COST_START','wrapper_identity':wrapper_id,
  'environment_identity':env_identity,'session_id':sid,'model':name,'environment_starts':0,'unix':time.time()})
 state=adapter.OnlineCost(models,initial,name);by={r['request_id']:r for r in result['requests']};curve=[]
 events=result['events'];physical=[]
 for e in events:
  now=int(e['logical_time_ns']);state.advance(now);kind=e['kind'];rid=e.get('request_id')
  if kind=='DISPATCH':
   state.dispatch(rid,by[rid]['task'],e['owner']);physical.append(e)
  elif kind=='AVAILABLE':state.available(rid,e['owner']);physical.append(e)
  elif kind in ('EXECUTION_START','HOST_INFERENCE_START','HOST_INFERENCE_RETURN','OUTPUT_READY'):
   state.phase(rid,kind)
  elif kind=='SENSOR':
   x=state.snapshot();curve.append({'time_s':now/1e9,'J':x['continuous_energy_j'],'AP_c':x['AP_c'],'power_w':x['power_w']})
 state.advance(int(result['observation_end_ns']))
 observer={'schema':'A24-fixed-ownership-cost-observer-v1','model':name,'environment_identity':env_identity,
  'source_environment_raw_sha256':raw_sha,'ownership_trace_sha256':digest(physical),
  'same_dispatch_AVAILABLE_trace':True,'source_engine_model':'TREND27','initial_binding_sha256':digest(initial),
  'model_binding_sha256':models['binding_sha256'],'metrics':state.totals(),'curve':curve,
  'new_environment':0,'new_wrapper_instances':1,'NN':0,'fit':0,'measured_J':None}
 return observer,wrapper_id

def execute():
 registry,engine,adapter,timing=modules();reg,gen=verify_source_bindings(registry)
 op_path=O/'NEW_CONFIRM_OPERATION_REGISTERED.json'
 if not op_path.exists():raise RuntimeError('Parent NEW_CONFIRM_OPERATION_REGISTERED.json required')
 op=read(op_path);plan=read(P/'PREDICTION_EXECUTION_PLAN.json')
 expected={'schema':'A24-new-confirm-prediction-operation-v1','operator_sha256':sha(__file__),
  'generation':GENERATION,'generation_sha256':sha(G/'GENERATION.json'),
  'registration_sha256':sha(O/'REGISTRATION.json'),'execution_plan_sha256':sha(P/'PREDICTION_EXECUTION_PLAN.json'),
  'input_plan_sha256':sha(I/'PREDICTION_PLAN.json'),'input_audit_sha256':sha(I/'INPUT_AUDIT.json'),
  'max_environment_starts':8,'allow_execution':True}
 for k,v in expected.items():
  if op.get(k)!=v:raise RuntimeError('Parent registration field mismatch: '+k)
 audit_path=op.get('trace_auditor_path')
 if not audit_path or sha(audit_path)!=op.get('trace_auditor_sha256'):raise RuntimeError('Registered trace auditor required before START')
 if plan['operator_sha256']!=sha(__file__) or plan['cases'].__len__()!=8:raise RuntimeError('Operator/roster not frozen')
 if plan['profile_sha256']!=sha(plan['profile_path']):raise RuntimeError('Timing profile changed')
 if {case['session_id'] for case in plan['cases']}!=EXPECTED_IDS:raise RuntimeError('Execution roster changed')
 for i,case in enumerate(plan['cases']):
  cfg=case['config']
  if cfg['sample_seed']!=491000+i or cfg['stage']!=STAGE:raise RuntimeError('Pre-START sample seed/stage schema')
  for path,h in cfg['bound_source_inputs'].items():
   if sha(path)!=h:raise RuntimeError('Pre-START full batch input/source SHA changed')
  if registry.digest([GENERATION,case['label'],cfg])[:28]!=case['expected_identity']:raise RuntimeError('Pre-START identity schema')
 starts=[e for e in registry.events(O/'receipts.jsonl') if e.get('event')=='START' and e.get('manifest',{}).get('config',{}).get('stage')==STAGE]
 if starts:raise RuntimeError('Prior newCONF START exists; exact saved recovery audit required, no automatic rerun')
 registry.guard(GENERATION) # includes actual process leaves/old+new caps/free8GiB/frozen SHA.
 lock=registry.owner_lock()
 registry.save(P/'WORKER_OWNER.json',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'argv':sys.argv,
  'unix':time.time(),'operator_sha256':sha(__file__),'operation_sha256':sha(op_path),'generation':GENERATION})
 profile=read(plan['profile_path']);models=adapter.modelsload();journal=registry.Journal(GENERATION);saved=[]
 for case in plan['cases']:
  cfg=case['config'];sid=case['session_id']
  if cfg['sample_seed']!=491000+len(saved) or cfg['stage']!=STAGE:raise RuntimeError('Seed/stage plan mismatch')
  for path,h in cfg['bound_source_inputs'].items():
   if sha(path)!=h:raise RuntimeError('Raw/input/initial SHA changed')
  initial=adapter.validate_initial(read(cfg['initial_path']));sc=read(cfg['scenario_path'])
  # Engine expects integers, while the frozen scenario file uses exact decimal wire strings.
  sc=timing.compile_scenario(read(I/sid/'RECIPE_COMPATIBLE_INPUT.json'),split=STAGE)
  if digest(engine.wire(sc))!=cfg['scenario_sha256'] or digest(initial)!=cfg['initial_binding_sha256']:raise RuntimeError('Schema/digest changed')
  if cfg['rule']!=POLICY_MAP[read(I/sid/'RECIPE_COMPATIBLE_INPUT.json')['policy_id']]:raise RuntimeError('Policy mapping changed')
  stage_starts=[e for e in registry.events(O/'receipts.jsonl') if e.get('event')=='START' and e.get('manifest',{}).get('config',{}).get('stage')==STAGE]
  if len(stage_starts)>=8 or len(stage_starts)!=len(saved):raise RuntimeError('new_confirmation_cap8/consumption mismatch')
  if sha(op['trace_auditor_path'])!=op['trace_auditor_sha256']:raise RuntimeError('Trace auditor changed before START')
  registry.guard(GENERATION)
  def callback(manifest):
   registry.append(P/'cost_observer_receipts.jsonl',{'event':'COST_START','wrapper_identity':digest([manifest['identity'],'TREND27'])[:28],
    'environment_identity':manifest['identity'],'session_id':sid,'model':'TREND27','environment_starts':1,'unix':time.time()})
   result,costs,frames=engine.simulate(profile,sc,manifest,models,initial,'TREND27',controller=None,
     family=cfg['rule'],rule=cfg['rule'],sample_seed=cfg['sample_seed'],alpha=.95,
     allow_wait=cfg['allow_wait'],decision_mode='EVENT')
   return result,{'result':result,'initial':initial}
  def extras(identity,aux):
   raw=O/'raw'/GENERATION/(identity+'.json.gz');rawsha=registry.sha(raw)
   registry.append(P/'cost_observer_receipts.jsonl',{'event':'COST_COMPLETE','wrapper_identity':digest([identity,'TREND27'])[:28],
    'environment_identity':identity,'model':'TREND27','source_environment_raw_sha256':rawsha,'unix':time.time()})
   secondary,wrapper=cost_observe_trace(aux['result'],aux['initial'],models,adapter,registry,identity,rawsha)
   secondary_path=P/'cost_raw'/(identity+'_MEASURED35.json.gz')
   registry.atomic(secondary_path,gzip.compress(registry.canonical(secondary),mtime=0))
   registry.append(P/'cost_observer_receipts.jsonl',{'event':'COST_COMPLETE','wrapper_identity':wrapper,
    'environment_identity':identity,'model':'MEASURED35','raw_path':str(secondary_path),'raw_sha256':registry.sha(secondary_path),'unix':time.time()})
   # External stronger saved-trace auditor is separately pinned by the parent operation.
   audit_path=op.get('trace_auditor_path')
   if not audit_path or sha(audit_path)!=op.get('trace_auditor_sha256'):raise RuntimeError('Registered trace auditor required')
   import importlib.util
   spec=importlib.util.spec_from_file_location('new_confirmation_registered_auditor',audit_path)
   auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
   trace=auditor.inspect_result(aux['result'],profile,models=models)
   trace_path=P/'audits'/(identity+'.json')
   registry.save(trace_path,{'status':'PASS','trace':trace,'raw_sha256':rawsha,
    'secondary_cost_sha256':registry.sha(secondary_path),'same_ownership_trace':True,'new_environment':0})
   return {'secondary_cost_path':str(secondary_path),'secondary_cost_sha256':registry.sha(secondary_path),
    'trace_audit_path':str(trace_path),'trace_audit_sha256':registry.sha(trace_path)}
  result,aux,row=journal.run(case['label'],cfg,callback,extras)
  if row['identity']!=case['expected_identity']:raise RuntimeError('Prebound identity mismatch')
  prep=O/'prepared'/(row['identity']+'.json')
  saved.append({'session_id':sid,'identity':row['identity'],'label':row['label'],'config':cfg,
   'raw_path':row['raw_path'],'raw_sha256':row['raw_sha256'],'prepared_path':str(prep),'prepared_sha256':sha(prep),
   'row_sha256':registry.digest(row),'primary_model':'TREND27','primary_metrics':result['metrics'],
   'primary_cost_metrics':result['cost']['metrics'],'secondary_cost_path':row['secondary_cost_path'],
   'secondary_cost_sha256':row['secondary_cost_sha256'],'trace_audit_path':row['trace_audit_path'],
   'trace_audit_sha256':row['trace_audit_sha256']})
 current=registry.events(O/'receipts.jsonl');ids={x['identity'] for x in saved}
 if len(ids)!=8 or any(sum(e.get('event')==k and e.get('identity')==i for e in current)!=1 for i in ids for k in ['START','PREPARED','COMPLETE']):raise RuntimeError('Eight durable terminal chains required')
 if any(e.get('event')=='FAIL' and e.get('identity') in ids for e in current):raise RuntimeError('Failed identity cannot be promoted')
 cost_events=registry.events(P/'cost_observer_receipts.jsonl')
 cost_starts=[x for x in cost_events if x['event']=='COST_START'];cost_done=[x for x in cost_events if x['event']=='COST_COMPLETE']
 if len(cost_starts)!=16 or len(cost_done)!=16 or len({x['wrapper_identity'] for x in cost_starts})!=16 or {x['wrapper_identity'] for x in cost_starts}!={x['wrapper_identity'] for x in cost_done}:raise RuntimeError('Exact16 cost wrapper accounting required')
 frozen={'schema':'A24-new-confirm8-predictions-frozen-v1','status':'PREDICTIONS_FROZEN_BEFORE_NEW_OBSERVED_COMPARISON',
  'generation':GENERATION,'generation_sha256':sha(G/'GENERATION.json'),'operator_sha256':sha(__file__),
  'operation_sha256':sha(op_path),'execution_plan_sha256':sha(P/'PREDICTION_EXECUTION_PLAN.json'),
  'input_plan_sha256':sha(I/'PREDICTION_PLAN.json'),'predictions':saved,'environment_starts':8,
  'cost_wrapper_instances':16,'cost_observer_receipts_sha256':sha(P/'cost_observer_receipts.jsonl'),
  'observed_response_postcommon_AP_or_J_metrics_parsed':0,'NN':0,'fit':0,'optimizer':0,
  'measured_J':None,'energy_error_qualified':False,'confidence_interval':None,
  'claim_boundary':'Offline results-blind prediction of already measured, published normal sessions; not contemporaneous prospective validation.'}
 registry.save(P/'PREDICTIONS_FROZEN.json',frozen)
 print(json.dumps({'status':frozen['status'],'predictions':8,'sha256':sha(P/'PREDICTIONS_FROZEN.json')}))

def main():
 p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
 m.add_argument('--prepare',action='store_true');m.add_argument('--execute',action='store_true');a=p.parse_args()
 prepare() if a.prepare else execute()

if __name__=='__main__':main()
