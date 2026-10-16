"""New CONFIRM8 observed residuals, inaccessible until all predictions are sealed.

SOURCE PREPARATION ONLY unless --execute is explicitly called after a separate
parent NEW_CONFIRM_COMPARISON_OPERATION_REGISTERED.json. --test-boundaries uses
synthetic arrays only. No model/engine/CostState/NN/fit/selection calls exist.

Parent operation schema A24-new-confirm8-observed-comparison-operation-v1:
operator_sha256, predictions_frozen_sha256, execution_plan_sha256,
input_plan_sha256, input_audit_sha256, forecast_operation_sha256,
algorithm_spec_sha256, max_sessions=8, allow_observed_access=true, fit=0.
"""
from __future__ import annotations
from collections import Counter
import argparse,bisect,gzip,hashlib,json,math,os,pathlib,re,shutil,statistics,sys,time,zipfile

B=pathlib.Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
W=B/'work/A24-INTEGRATED-SIM-20261016-G002';O=B/'outputs/A24-INTEGRATED-SIM-20261016-G002'
I=O/'new_confirmation_inputs';P=O/'new_confirmation_predictions';C=O/'new_confirmation_comparison'
G=W/'source_generations/A24INT_G002';NS=10**9
ALGORITHM_SPEC={
 'schema':'A24-new8-observed-residual-method-v1',
 'roster':'Exactly forecast-sealed eight original CONFIRM normal/published sessions; all planned requests within each retained.',
 'forecast_gate':'Exact parent SHA of PREDICTIONS_FROZEN plus all8 raw/prepared/row/START/PREPARED/COMPLETE, inputs and initial SHA before observed access.',
 'clock':'Same exact common_start.origin_ns as precommon initial binding; observed response and HAL read-completion upper bounds subtract that origin.',
 'response':{'C':'output_ready_ns','D':'persist_complete_ns','AVAILABLE':'lane_available_ns, separate from response',
  'p95':'nearest-rank ceil(.95*n), valid completed task-boundary responses <=210s only; missing rows never become zero latency',
  'service':'all planned denominator; deadline_met and <=120s separately, service_success requires both',
  'phase_DAG':'scheduled<=actual<=queue<=dispatch<=execution<=output<=persist<=worker_release<=AVAILABLE for recorded phases; no missing phase invented'},
 'AP':{'source':'Unique AP type0 in CURRENT_HAL; finite value; integer device_elapsed_before/after_ns, nonreversed.',
  'coordinate':'device_elapsed_after_ns-common_ns; completed read upper bound, not sensor-update time',
  'window_ns':[35_000_000_000,180_000_000_000],
  'boundary_rule':'At35 and180 require both inclusive last<=boundary and first>=boundary; exact read can serve both. Each side distance<=5s.',
  'interior_rule':'Every consecutive completion gap intersecting [35,180] <=5s; duplicate completion times invalidate window.',
  'mean':'Zero-order hold last completed report; exact rectangular area of report step function/145s. No physical sensor interpolation or gap fill.',
  'peak_reported':'Max of held report at35 and completed reports inside(35,180]; reported-step peak, not continuous physical peak.',
  'AP180_reported':'Last completed report <=180, qualifying boundary limits still required; no future report substituted.',
  'residual':'AP180_reported minus frozen last complete precommon AP input.',
  'failed_coverage':'mean/peak_reported/AP180/residual and their prediction residuals null; explicit evidence reasons retained.',
  'predicted_peak_comparison':'Saved model curve max over35..180 (0.5s grid); global model AP0..180 peak is not compared to a35..180 measured peak.',
  'uncertainty':'Read cadence is not sensor refresh; update timestamps/cache age unknown; HAL AP is not verified surface temperature.'},
 'residual_sign':'prediction minus observed; descriptive bias/MAE/RMSE and count; no CI/p-value/superiority promotion.',
 'energy':'Observed J=null and prediction error=null absent separately verified device unit/sign/counter calibration. No factor1000 fix.',
 'selection_boundary':'Already measured, closed normal/published subset; offline results-blind forecasting is not contemporaneous prospective validation. Keep original40 failures/rejects/unpublished slots and separate revised4/supplement12 denominators.',
 'fit':0,'model_changes':0,'environment_starts':0,'NN':0,'optimizer':0,
}

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def number(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def ns(x):
 if type(x)==int:return x
 if isinstance(x,str) and re.fullmatch(r'-?\d+',x):return int(x)
 return None
def p95(values):
 x=sorted(values);return x[math.ceil(.95*len(x))-1] if x else None
def residual(values):
 if not values:return {'n':0,'bias':None,'MAE':None,'RMSE':None,'median':None,'min':None,'max':None}
 return {'n':len(values),'bias':statistics.mean(values),'MAE':statistics.mean(abs(x) for x in values),
  'RMSE':math.sqrt(statistics.mean(x*x for x in values)),'median':statistics.median(values),'min':min(values),'max':max(values)}

def ap_report_step(points,initial_ap):
 """Pure predeclared read-completion ZOH arithmetic; no physical interpolation."""
 lo,hi=35*NS,180*NS;limit=5*NS;reasons=[]
 pts=sorted(points,key=lambda p:p['t_ns']);times=[p['t_ns'] for p in pts]
 evidence={'samples':len(pts),'boundaries':{},'long_gaps':[],'duplicate_completion_ns':[]}
 evidence['duplicate_completion_ns']=[a for a,b in zip(times,times[1:]) if a==b]
 if evidence['duplicate_completion_ns']:reasons.append('DUPLICATE_READ_COMPLETION_CLOCK')
 if any(type(p['t_ns'])!=int or not number(p['AP_c']) for p in pts):reasons.append('INVALID_PROJECTED_POINT')
 boundary_values={}
 for target in [lo,hi]:
  left=bisect.bisect_right(times,target)-1;right=bisect.bisect_left(times,target)
  l=pts[left] if left>=0 else None;r=pts[right] if right<len(pts) else None
  item={'target_ns':target,'left':l,'right':r,'qualified':False}
  if l is None or r is None:reasons.append('MISSING_TWO_SIDED_READ_BOUNDARY_'+str(target//NS))
  elif target-l['t_ns']>limit or r['t_ns']-target>limit:reasons.append('BOUNDARY_SIDE_MORE_THAN5S_'+str(target//NS))
  else:item['qualified']=True;boundary_values[target]=l['AP_c']
  evidence['boundaries'][str(target)]=item
 for a,b in zip(pts,pts[1:]):
  if a['t_ns']<hi and b['t_ns']>lo and b['t_ns']-a['t_ns']>limit:
   evidence['long_gaps'].append({'left_ns':a['t_ns'],'right_ns':b['t_ns'],'gap_ns':b['t_ns']-a['t_ns']})
 if evidence['long_gaps']:reasons.append('INTERIOR_COMPLETION_GAP_MORE_THAN5S')
 out={'qualified':not reasons,'reasons':sorted(set(reasons)),'evidence':evidence,
  'AP35_180_reported_step_mean_c':None,'AP35_180_reported_step_peak_c':None,
  'AP180_reported_c':None,'AP180_reported_residual_from_initial_c':None,
  'physical_interpolation':False,'sensor_update_time_known':False,'surface_temperature_verified':False}
 if reasons:return out
 last_t=lo;last_v=boundary_values[lo];area=0.;peak=last_v
 for point in pts:
  if not lo<point['t_ns']<=hi:continue
  area+=(point['t_ns']-last_t)/NS*last_v
  last_t=point['t_ns'];last_v=point['AP_c'];peak=max(peak,last_v)
 area+=(hi-last_t)/NS*last_v
 out.update(AP35_180_reported_step_mean_c=area/145,AP35_180_reported_step_peak_c=peak,
  AP180_reported_c=boundary_values[hi],
  AP180_reported_residual_from_initial_c=boundary_values[hi]-initial_ap if number(initial_ap) else None)
 return out

def observed_requests(raw,recipe,common):
 by={};errors=[]
 for q in raw:
  rid=q.get('request_id')
  if rid in by:raise ValueError('Duplicate observed request identity')
  by[rid]=q
 planned=recipe['requests'];ids={q['id'] for q in planned}
 if set(by)-ids:raise ValueError('Unplanned observed request identities')
 rows=[]
 fields=('actual_arrival_ns','queue_entry_ns','dispatch_ns','execution_start_ns','output_ready_ns',
         'persist_complete_ns','worker_release_ns','lane_available_ns')
 for p in planned:
  q=by.get(p['id']);issues=[];times={k:None for k in fields};response=None;available=None
  if q is None:issues.append('MISSING_OBSERVED_RECORD')
  else:
   for k,want in [('ordinal',p['ordinal']),('task',p['task']),('group',p['group']),
    ('scheduled_arrival_ns',common+p['arrival_ns']),('deadline_ns',common+p['deadline_ns'])]:
    if q.get(k)!=want:issues.append('PLAN_BINDING_MISMATCH_'+k)
   for k in fields:
    if q.get(k) is not None:
     if type(q[k])!=int:issues.append('INVALID_CLOCK_'+k)
     else:times[k]=q[k]-common
   known=[p['arrival_ns']]+[times[k] for k in fields if times[k] is not None]
   if any(a>b for a,b in zip(known,known[1:])):issues.append('REVERSED_RECORDED_PHASE_DAG')
   rf='output_ready_ns' if p['task']=='C' else 'persist_complete_ns'
   response=times[rf]
   if response is not None and q.get('response_complete_ns')!=common+response:issues.append('TASK_RESPONSE_BOUNDARY_MISMATCH')
   if times['dispatch_ns'] is not None and times['dispatch_ns']>=recipe['service_cutoff_ns']:issues.append('DISPATCH_AFTER_SERVICE_STOP')
   if response is not None and not(p['arrival_ns']<=response<=recipe['sensor_end_ns']):response=None
   available=times['lane_available_ns']
   if available is not None and not(p['arrival_ns']<=available<=recipe['sensor_end_ns']):available=None
   if issues:response=None;available=None
  status=q.get('terminal_status') if q else 'MISSING_OBSERVED_RECORD'
  rows.append({'request_id':p['id'],'ordinal':p['ordinal'],'task':p['task'],
   'priority':{'urgent':'U','normal':'N','U':'U','N':'N'}[p['priority']],
   'scheduled_arrival_ns':p['arrival_ns'],'deadline_ns':p['deadline_ns'],
   'backend':q.get('backend') if q else None,'declared_terminal_status':status,
   'response_boundary':'output_ready' if p['task']=='C' else 'persist_complete',
   'response_ns':response,'lane_available_ns':available,
   'response_latency_ns':response-p['arrival_ns'] if response is not None else None,
   'raw_phase_common_ns':times,'issues':issues})
 return rows

def cohorts(rows,service):
 out={}
 for cohort in ['ALL','U','N','C','D','CU','CN','DU','DN']:
  selected=[r for r in rows if cohort in ['ALL',r['priority'],r['task'],r['task']+r['priority']]]
  responded=[r for r in selected if r['response_ns'] is not None];available=[r for r in selected if r['lane_available_ns'] is not None]
  failed=[r for r in selected if r['declared_terminal_status']=='FAILED' and r['lane_available_ns'] is None]
  n=len(selected);met=sum(r['response_ns']<=r['deadline_ns'] for r in responded)
  success=sum(r['response_ns']<=min(service,r['deadline_ns']) for r in responded)
  out[cohort]={'planned':n,'responded':len(responded),'available':len(available),'deadline_met':met,
   'in_service_window':sum(r['response_ns']<=service for r in responded),'service_success':success,
   'failed':len(failed),'incomplete':n-len(available)-len(failed),
   'missing_observed_records':sum('MISSING_OBSERVED_RECORD' in r['issues'] for r in selected),
   'invalid_records':sum(bool(r['issues']) for r in selected),
   'deadline_missed_or_no_valid_response':n-met,'service_loss_or_unfinished':n-success,
   'response_p95_ns':p95([r['response_latency_ns'] for r in responded]),
   'response_p95_denominator':'valid completed task response only; missing/unfinished retained in planned service counts',
   'service_rate':success/n if n else None,
   'targets':{str(alpha):success/n>=alpha if n else None for alpha in [.70,.80,.90,.95,1.]}}
 return {'by_cohort':out,**out['ALL']}

def parse_hal(raw,common):
 points=[];invalid=[]
 for no,line in enumerate(raw.splitlines(),1):
  if not line.strip():continue
  try:q=json.loads(line)
  except (ValueError,UnicodeError):invalid.append({'line':no,'reason':'MALFORMED_RAW_JSON'});continue
  lo,hi=q.get('device_elapsed_before_ns'),q.get('device_elapsed_after_ns')
  if type(lo)!=int or type(hi)!=int or lo>hi:
   invalid.append({'line':no,'reason':'DEVICE_READ_BRACKET_MISSING_OR_REVERSED'});continue
  ap=[s for s in q.get('sensors',[]) if s.get('sensor_name')=='AP' and s.get('sensor_type')==0]
  if q.get('sensor_source_section')!='CURRENT_HAL' or len(ap)!=1 or not number(ap[0].get('value_c')):
   invalid.append({'line':no,'relative_read_end_ns':hi-common,'reason':'UNIQUE_CURRENT_HAL_AP_TYPE0_NOT_AVAILABLE'});continue
  points.append({'t_ns':hi-common,'lo_ns':lo-common,'hi_ns':hi-common,'AP_c':ap[0]['value_c'],
   'source_line':no,'line_sha256':hashlib.sha256(line).hexdigest(),
   'sensor_timestamp_ns':ap[0].get('sensor_timestamp_ns'),'cache_age_ns':ap[0].get('cache_age_ns')})
 return points,invalid

def seal_gate(registry):
 op_path=O/'NEW_CONFIRM_COMPARISON_OPERATION_REGISTERED.json';op=read(op_path)
 freeze_path=P/'PREDICTIONS_FROZEN.json';frozen=read(freeze_path)
 expected={'schema':'A24-new-confirm8-observed-comparison-operation-v1','operator_sha256':sha(__file__),
  'predictions_frozen_sha256':sha(freeze_path),'execution_plan_sha256':sha(P/'PREDICTION_EXECUTION_PLAN.json'),
  'input_plan_sha256':sha(I/'PREDICTION_PLAN.json'),'input_audit_sha256':sha(I/'INPUT_AUDIT.json'),
  'forecast_operation_sha256':sha(O/'NEW_CONFIRM_OPERATION_REGISTERED.json'),
  'algorithm_spec_sha256':digest(ALGORITHM_SPEC),'max_sessions':8,'allow_observed_access':True,'fit':0}
 for k,v in expected.items():
  if op.get(k)!=v:raise RuntimeError('Comparison registration mismatch '+k)
 if frozen['status']!='PREDICTIONS_FROZEN_BEFORE_NEW_OBSERVED_COMPARISON' or frozen['environment_starts']!=8 or len(frozen['predictions'])!=8:raise RuntimeError('All8 forecast seal required')
 if frozen['operation_sha256']!=expected['forecast_operation_sha256'] or frozen['execution_plan_sha256']!=expected['execution_plan_sha256'] or frozen['input_plan_sha256']!=expected['input_plan_sha256']:raise RuntimeError('Forecast seal lineage mismatch')
 if frozen['observed_response_postcommon_AP_or_J_metrics_parsed']!=0:raise RuntimeError('Forecast prior observed access')
 if frozen['generation_sha256']!=sha(G/'GENERATION.json'):raise RuntimeError('Forecast generation changed')
 if frozen['operator_sha256']!=sha(W/'predict_confirmation.py'):raise RuntimeError('Forecast operator changed')
 generation=read(G/'GENERATION.json')
 for path,h in generation['source_hashes'].items():
  if sha(path)!=h:raise RuntimeError('Frozen core SHA changed')
 plan=read(P/'PREDICTION_EXECUTION_PLAN.json');cases={c['expected_identity']:c for c in plan['cases']}
 receipts=registry.events(O/'receipts.jsonl');rows=registry.events(O/'rows.jsonl')
 if len([e for e in receipts if e.get('event')=='START' and e.get('manifest',{}).get('config',{}).get('stage')=='NEW_CONFIRM_PREDICTION'])!=8:raise RuntimeError('newCONF START coverage')
 forecast={}
 for entry in frozen['predictions']:
  identity=entry['identity'];case=cases[identity]
  if entry['config']!=case['config'] or entry['session_id']!=case['session_id']:raise RuntimeError('Forecast roster/config binding')
  for path,h in case['config']['bound_source_inputs'].items():
   if sha(path)!=h:raise RuntimeError('Bound raw input/initial changed')
  rr=[r for r in rows if r['identity']==identity]
  if len(rr)!=1 or digest(rr[0])!=entry['row_sha256']:raise RuntimeError('Forecast durable row SHA')
  prep=read(entry['prepared_path'])
  if sha(entry['prepared_path'])!=entry['prepared_sha256'] or prep!=rr[0]:raise RuntimeError('Forecast prepared-row chain')
  for kind in ['START','PREPARED','COMPLETE']:
   chain=[e for e in receipts if e.get('identity')==identity and e.get('event')==kind]
   if len(chain)!=1:raise RuntimeError('Forecast terminal chain '+kind)
   if kind=='START' and chain[0]['manifest']['config']!=entry['config']:raise RuntimeError('Forecast START manifest')
   if kind=='PREPARED' and chain[0]['prepared_sha256']!=entry['prepared_sha256']:raise RuntimeError('Forecast PREPARED SHA')
   if kind=='COMPLETE' and chain[0]['raw_sha256']!=entry['raw_sha256']:raise RuntimeError('Forecast COMPLETE SHA')
  if any(e.get('event')=='FAIL' and e.get('identity')==identity for e in receipts):raise RuntimeError('Forecast FAIL cannot be promoted')
  for path,h in [(entry['raw_path'],entry['raw_sha256']),(entry['secondary_cost_path'],entry['secondary_cost_sha256']),(entry['trace_audit_path'],entry['trace_audit_sha256'])]:
   if sha(path)!=h:raise RuntimeError('Forecast raw/audit SHA')
  audit=read(entry['trace_audit_path'])
  if audit['status']!='PASS' or audit['raw_sha256']!=entry['raw_sha256']:raise RuntimeError('Forecast raw audit required')
  primary=json.loads(gzip.decompress(pathlib.Path(entry['raw_path']).read_bytes()))
  secondary=json.loads(gzip.decompress(pathlib.Path(entry['secondary_cost_path']).read_bytes()))
  if primary['manifest']['identity']!=identity or primary['model']!='TREND27' or secondary['model']!='MEASURED35' or secondary['source_environment_raw_sha256']!=entry['raw_sha256']:raise RuntimeError('Two cost models forecast binding')
  forecast[entry['session_id']]={'entry':entry,'primary':primary,'secondary':secondary}
 if len(forecast)!=8:raise RuntimeError('Unique forecast eight')
 return op,frozen,forecast

def execute():
 # These checks all precede any new measured runtime/AP outcome file access.
 sys.path.insert(0,str(G));import registry
 op,frozen,forecast=seal_gate(registry)
 registry.process_guard()
 if shutil.disk_usage(O).free<8*1024**3:raise RuntimeError('Disk8GiB guard')
 lock=registry.owner_lock()
 if (C/'OBSERVED_COMPARISON.json').exists():raise RuntimeError('Immutable comparison exists')
 if (C/'OBSERVED_ACCESS_STARTED.json').exists():raise RuntimeError('Prior observed access exists; preserve history and audit before any continuation')
 registry.save(C/'ALGORITHM_SPEC.json',ALGORITHM_SPEC)
 registry.save(C/'OBSERVED_ACCESS_STARTED.json',{'unix':time.time(),'actual_pid':os.getpid(),
  'operator_sha256':sha(__file__),'operation_sha256':sha(O/'NEW_CONFIRM_COMPARISON_OPERATION_REGISTERED.json'),
  'predictions_frozen_sha256':sha(P/'PREDICTIONS_FROZEN.json'),'algorithm_spec_sha256':digest(ALGORITHM_SPEC)})
 inputs=read(I/'PREDICTION_PLAN.json');sources={s['session_id']:s for s in inputs['sessions']};comparisons=[]
 for sid,s in sources.items():
  registry.append(C/'access_receipts.jsonl',{'event':'OBSERVED_SESSION_ACCESS_START','session_id':sid,'unix':time.time()})
  src=s['source'];archive=pathlib.Path(src['archive'])
  if sha(archive)!=src['archive_sha256']:raise RuntimeError('Observed archive SHA')
  folder=I/sid;recipe=read(folder/'RECIPE_COMPATIBLE_INPUT.json');initial=read(forecast[sid]['entry']['config']['initial_path'])
  common=initial['provenance']['common_ns'];apbind=read(folder/'INITIAL_AP_PRECOMMON_60S.json')
  with zipfile.ZipFile(archive) as z:
   hashes={m['path']:m['sha256'] for m in json.loads(z.read('FILE_SHA256.json'))['members']}
   names=[f'raw/{sid}/requests.json',f'raw/{sid}/host_hal_raw.jsonl',f'raw/{sid}/events.jsonl']
   data={}
   for name in names:
    value=z.read(name)
    if hashlib.sha256(value).hexdigest()!=hashes.get(name):raise RuntimeError('Observed internal member SHA')
    data[name]=value
   # Recheck the already bound common event without substituting a later origin.
   eb=apbind['common_binding'];line=data[names[2]].splitlines()[eb['source_line']-1]
   if hashlib.sha256(line).hexdigest()!=eb['line_sha256'] or json.loads(line)['origin_ns']!=common:raise RuntimeError('Exact common origin mismatch')
   obsrows=observed_requests(json.loads(data[names[0]]),recipe,common)
   appts,invalid_ap=parse_hal(data[names[1]],common)
  obsmetric=cohorts(obsrows,recipe['service_cutoff_ns'])
  observed_ap=ap_report_step(appts,initial['pre'][-1]['ap']);observed_ap['invalid_raw_records']=invalid_ap
  f=forecast[sid];pred=f['primary'];model_costs={'TREND27':(pred['cost']['metrics'],pred['curve']),
   'MEASURED35':(f['secondary']['metrics'],f['secondary']['curve'])}
  bypred={r['request_id']:r for r in pred['requests']};response_errors=[];available_errors=[];per_request=[]
  if set(bypred)!={r['request_id'] for r in obsrows}:raise RuntimeError('Forecast/observed planned roster mismatch')
  for r in obsrows:
   p=bypred[r['request_id']];pr=ns(p.get('response_ns'));pa=ns(p.get('lane_available_ns'))
   re=(pr-r['response_ns']) if pr is not None and r['response_ns'] is not None else None
   ae=(pa-r['lane_available_ns']) if pa is not None and r['lane_available_ns'] is not None else None
   if re is not None:response_errors.append(re/1e6)
   if ae is not None:available_errors.append(ae/1e6)
   per_request.append({'observed':r,'predicted_response_ns':pr,'predicted_AVAILABLE_ns':pa,
    'response_error_ns':re,'AVAILABLE_error_ns':ae})
  aps={}
  for name,(metrics,curve) in model_costs.items():
   values=[p['AP_c'] for p in curve if 35<=p['time_s']<=180]
   prediction={'AP35_180_mean_c':metrics.get('AP35_180_mean_c'),'AP35_180_saved_grid_peak_c':max(values) if values else None,
    'AP180_c':metrics.get('AP180_c'),'AP180_residual_from_initial_c':metrics.get('AP180_residual_from_initial_c'),
    'J0_180_conditional':metrics.get('continuous_J0_180')}
   pairs={'mean_c':('AP35_180_mean_c','AP35_180_reported_step_mean_c'),
    'reported_peak_vs_saved_model_grid_c':('AP35_180_saved_grid_peak_c','AP35_180_reported_step_peak_c'),
    'AP180_c':('AP180_c','AP180_reported_c'),
    'residual_from_initial_c':('AP180_residual_from_initial_c','AP180_reported_residual_from_initial_c')}
   errors={key:prediction[pk]-observed_ap[ok] if observed_ap['qualified'] and number(prediction[pk]) and number(observed_ap[ok]) else None for key,(pk,ok) in pairs.items()}
   aps[name]={'prediction':prediction,'prediction_minus_observed':errors,'measured_J':None,'energy_prediction_error':None,
    'energy_status':'DEVICE_CURRENT_CHARGE_UNIT_UNRESOLVED; no calibration or x1000 correction applied'}
  metric_residual={co:{k:pred['metrics']['by_cohort'][co][k]-v for k,v in observed.items() if k in ['planned','responded','available','deadline_met','in_service_window','service_success','failed','incomplete']}
    for co,observed in obsmetric['by_cohort'].items()}
  item={'session_id':sid,'label':recipe['label'],'source_archive_sha256':src['archive_sha256'],
   'common_origin_ns':common,'planned':len(recipe['requests']),'observed_metrics':obsmetric,
   'metric_prediction_minus_observed':metric_residual,'response_latency_errors_ms':residual(response_errors),
   'AVAILABLE_time_errors_ms':residual(available_errors),'observed_AP':observed_ap,'models':aps,
   'requests':per_request,'forecast_identity':f['entry']['identity'],'forecast_raw_sha256':f['entry']['raw_sha256'],
   'measured_J':None,'energy_prediction_error':None,'confidence_interval':None,'new_fit':0}
  registry.save(C/'sessions'/(sid+'.json'),item);comparisons.append(item)
  registry.append(C/'access_receipts.jsonl',{'event':'OBSERVED_SESSION_ACCESS_COMPLETE','session_id':sid,
   'output_sha256':sha(C/'sessions'/(sid+'.json')),'unix':time.time()})
 denominator=B/'outputs/A24-INTEGRATED-SIM-20261016/intake/snapshots/d5491239abd75a63b0ae018dc171026ac07a9ea2/DENOMINATORS.json'
 output={'schema':'A24-new8-sealed-forecast-observed-residuals-v1','status':'DESCRIPTIVE_COMPARISON_COMPLETE',
  'operator_sha256':sha(__file__),'predictions_frozen_sha256':sha(P/'PREDICTIONS_FROZEN.json'),
  'algorithm_spec_sha256':digest(ALGORITHM_SPEC),'sessions':comparisons,'sessions_count':len(comparisons),
  'planned_requests':sum(s['planned'] for s in comparisons),'full_plan_denominator_path':str(denominator),
  'full_plan_denominator_sha256':sha(denominator),'full_plan_denominators':read(denominator),
  'selection_bias':ALGORITHM_SPEC['selection_boundary'],'physical_independent_accuracy_confirmed':False,
  'measured_J':None,'energy_prediction_error':None,'confidence_interval':None,'new_environment':0,'NN':0,'fit':0,'optimizer':0}
 registry.save(C/'OBSERVED_COMPARISON.json',output)
 print(json.dumps({'status':output['status'],'sessions':len(comparisons),'sha256':sha(C/'OBSERVED_COMPARISON.json')}))

def test_boundaries():
 checks=[]
 def point(t,v=31.):return {'t_ns':int(t*NS),'AP_c':v}
 base=[point(t) for t in range(30,186,5)]
 def check(name,ok):assert ok,name;checks.append(name)
 x=ap_report_step(base,30.)
 check('5s gaps inclusive/exact boundaries',x['qualified'] and x['AP35_180_reported_step_mean_c']==31.)
 check('reported residual from initial',x['AP180_reported_residual_from_initial_c']==1.)
 check('duplicate completion rejected',not ap_report_step(base+[point(35)],30.)['qualified'])
 check('interior gap above5 rejected',not ap_report_step([p for p in base if p['t_ns']!=70*NS],30.)['qualified'])
 check('missing left35 rejected',not ap_report_step([point(t) for t in range(40,186,5)],30.)['qualified'])
 check('missing right180 rejected',not ap_report_step([point(t) for t in range(30,180,5)],30.)['qualified'])
 check('future boundary not substituted',ap_report_step([point(t,30. if t<181 else 90.) for t in range(31,187,5)],30.)['AP180_reported_c']==30.)
 check('empty is null',ap_report_step([],30.)['AP35_180_reported_step_mean_c'] is None)
 check('empty residual no NaN',residual([])['MAE'] is None)
 check('nearest-rank P95',p95(list(range(20)))==18)
 print(json.dumps({'status':'PASS','checks':len(checks),'algorithm_spec_sha256':digest(ALGORITHM_SPEC),'new_observed_access':0}))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--execute',action='store_true');group.add_argument('--test-boundaries',action='store_true');a=parser.parse_args()
 execute() if a.execute else test_boundaries()
