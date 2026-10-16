"""Independent saved-trace audit. No Simulator, NN, fit, or policy environments.
Python direct interval convolutions independently check JS event-sweep arithmetic.
"""
import collections,hashlib,importlib.util,json,math,os,time
from pathlib import Path
import numpy as np
from timing_model import read,save,duration

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def append(p,v):
 with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def fnv(s):
 h=2166136261
 for c in s:h=((h^ord(c))*16777619)&0xffffffff
 h^=h>>16;h=h*0x7feb352d&0xffffffff;h^=h>>15
 return h&0xffffffff
def predict(model,ints,ctx,ts,old):
 if model['target']=='AP':
  a=ctx['AP']['anchor'];at=a.get('time_s',a.get('t_s'));hist=[a.get('AP_c',a.get('AP')),a.get('SKIN_c',a.get('SKIN')),a.get('BAT_c',a.get('BAT')),a.get('pre20_AP_slope_c_s',a.get('pre20_AP_slope'))];X=np.column_stack([*(old.filtered_activity(ints,ts,b,-30)-old.filtered_activity(ints,np.array([at]),b,-30)[0] for b in (.06,1/60)),*(np.outer(-np.expm1(-(ts-at)/tau),[1,*hist]) for tau in (20,120))]);return hist[0]+((X-np.array(model['mean']))/np.array(model['scale']))@np.array(model['coef'])
 box=old.windowed_activity(ints,ts,.5,-30);cols=[np.ones(len(ts)),np.full(len(ts),math.log(ctx['POWER_API']['baseline']['median_api_w'])),box]
 for tau in (1,10,60):cols.append(old.filtered_activity(ints,ts,1/tau,-30))
 cols.extend([box[:,0]*box[:,1],box[:,1]*box[:,2],box[:,1]*box[:,3]])
 a=ctx['AP']['anchor'];h=[a.get('AP_c',a.get('AP')),a.get('SKIN_c',a.get('SKIN')),a.get('BAT_c',a.get('BAT')),a.get('pre20_AP_slope_c_s',a.get('pre20_AP_slope'))];known=all(isinstance(v,(int,float)) and math.isfinite(v) for v in h) and a.get('available_upper_s',a.get('completion_upper_s',1))<=0;cols.append(np.tile(h+[0] if known else [0,0,0,0,1],(len(ts),1)));X=np.column_stack(cols);return np.exp(((X-np.array(model['mean']))/np.array(model['scale']))@np.array(model['coef']))
def main(op):
 out=Path(op['output_dir']);out.mkdir();spec=importlib.util.spec_from_file_location('independent_direct_intervals',op['direct_math']);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);prod=read(op['production_operation']);plan=read(prod['case_plan_path']);packet=read(prod['packet_path']);receipts=[];rows=[]
 for source in op['production_operations']:
  pr=read(source);receipts.extend(json.loads(l) for l in Path(pr['receipts_path']).read_text(encoding='utf-8-sig').splitlines() if l.strip());rows.extend(json.loads(l) for l in (Path(pr['output_dir'])/'ROWS.jsonl').read_text(encoding='utf-8-sig').splitlines() if l.strip())
 rowby={r['logical_identity']:r for r in rows};checks=0;maxerr=0.;proofs=[];rate=[]
 def test(ok,label):
  nonlocal checks;checks+=1
  if not ok:raise ValueError(label)
 test(len(rows)==len(plan)==444,'exact sealed444 coverage');test(len(rowby)==len(rows),'unique identities');test(all('observed' not in s for s in packet['scenarios']),'no actual outcomes in controller packet');test(all(all(r<=0 for l,r,w in xs) for s in packet['scenarios'] for xs in s['context']['pre_activity9']['intervals']),'precommon activity has no target future');events=collections.defaultdict(list)
 for e in receipts:events[e['id']].append(e)
 test(set(events)=={c['identity'] for c in plan},'exact ledger identities')
 for i,cfg in enumerate(plan):
  identity=cfg['identity'];es=events[identity];test([e['event'] for e in es]==['START','PREPARED','COMPLETE'],'raw-prepared-row-terminal order '+identity);row=rowby[identity];p=Path(row['raw_path']);raw=read(p);test(sha(p)==row['raw_sha256']==es[1]['raw_sha256']==es[2]['raw_sha256'],'raw SHA '+identity);cp=p.parent.parent/'configurations'/(identity+'.json');test(read(cp)==cfg and sha(cp)==raw['configuration_sha256']==es[0]['config_sha256'],'config binding');test(raw['packet_sha256']==sha(prod['packet_path'])==es[0]['packet_sha256'],'packet binding');s=next(s for s in packet['scenarios'] if s['id']==cfg['scenario']);models=packet['fold_models'][s['block']] if cfg['cost_model']=='BLOCK_OUT' else packet;planned=raw['planned_requests'];by={q['ordinal']:q for q in planned};done={q['ordinal']:q for q in raw['requests']};test(len(planned)==128 and len(by)==128,'whole planned manifest');test(len(done)==len(raw['requests']),'no request duplicate')
  if cfg['cost_model']=='BLOCK_OUT':
   test('M8_R21_'+s['block'] not in models['AP']['training_groups'] and 'M8_R21_'+s['block'] not in models['power']['training_groups'],'whole R21 block excluded from reproduction cost fits')
  for q in planned:
   exact=next(x for x in s['requests'] if x['ordinal']==q['ordinal']);test(q['arrival']==exact['offset_ns']/1e9 and q['deadline']==q['arrival']+exact['deadline_ms']/1000,'unchanged fixed deadlines');test(q['readyAt']>=q['arrival'],'enqueue causal');test(q['completed']==(q['ordinal'] in done),'no filtered unfinished');eroute='classification_GPU' if q['task']=='classification' else 'detection_CPU';pool=[p for p in packet['templates'] if p['route']==eroute and p['priority']==q['priority']];selected=pool[fnv(str(cfg['stream'])+'|enqueue|'+str(q['ordinal']))%len(pool)];test(selected['id']==q['enqueueTemplate'] and q['readyAt']==q['arrival']+selected['enqueue_delay_s'],'exact old-data enqueue draw, no R21 future realized timing')
  owners={};dispatched=set();waited=set();dose=0.;policy=cfg['policy'];isserial='SERIAL' in policy or 'WAIT' in policy;isedf=policy.startswith(('EDF','EDD'));last=-math.inf
  for e in raw['events']:
   t,kind,ordinal=e[:3];test(t>=last-1e-9,'event chronology');last=t
   if kind=='AVAILABLE':test(ordinal in owners,'owner release');owners.pop(ordinal);continue
   qs=[q for q in planned if q['ordinal'] not in dispatched and q['readyAt']<=t+1e-9];qs.sort(key=lambda q:((q['deadline'] if isedf else 0),q['arrival'],q['ordinal']));test(qs and qs[0]['ordinal']==ordinal,'public strict head '+identity)
   if kind=='WAIT_START':
    q=by[ordinal];args=s['policy_args'];test(not owners and q['burstIndex'] not in waited and q['burstIndex']<args['first_n_bursts'],'WAIT eligible');waited.add(q['burstIndex']);dose+=e[3];test(abs(e[3]-args['wait_ms']/1000)<1e-8,'WAIT dose');continue
   test(kind=='DISPATCH' and ordinal not in dispatched and t<120,'dispatch uniqueness/window');q=by[ordinal];r=e[3];test(r==('detection_CPU' if q['task']=='detection' else 'classification_NPU' if '_CN' in policy else 'classification_GPU'),'fixed route');test(not owners if isserial else len(owners)<2,'common lane capacity')
   if owners:test(set([r,*owners.values()]) in ({'classification_GPU','detection_CPU'},{'classification_NPU','detection_CPU'}),'supported pair mask')
   dispatched.add(ordinal);owners[ordinal]=r
  test(bool(owners)==bool(raw['active_at_censor']),'remaining owner inventory');test(abs(dose-raw['wait_s'])<1e-8,'actual WAIT totals')
  for pri in ('urgent','normal','all'):
   pp=[q for q in planned if pri=='all' or q['priority']==pri];dd=[q for q in done.values() if pri=='all' or q['priority']==pri];on=sum(q['response']<=q['deadline']+1e-9 for q in dd);rr=raw['service'][pri];test(rr['planned']==len(pp) and rr['completed']==len(dd) and rr['on_time']==on and rr['late_or_unfinished']==len(pp)-on,'service arithmetic')
  for q in done.values():
   t=q['times'];test(t['dispatch']<=t['execution_start']<=t['host_inference_start']<=t['host_inference_return']<=t['output_ready']<=t['persist_complete']<=t['worker_release']<=t['AVAILABLE'],'full response/release order');test(q['response']==(t['output_ready'] if q['priority']=='urgent' else t['readback_end']),'priority response boundary');pool=[p for p in packet['templates'] if p['route']==q['route'] and p['priority']==q['priority']];chosen=pool[fnv(str(cfg['stream'])+'|phase|'+str(q['ordinal'])+'|'+q['route'])%len(pool)];test(q['template_id']==chosen['id'],'source-bound whole phase draw');reference=duration(packet['timing'],{**chosen,'domain':'M8_READBACK_RENAME_RESPONSE'},chosen['AP'] if chosen['AP'] is not None else 30.,chosen['overlap_fraction'] or 0);test(abs(q['residual']-chosen['inference_s']/reference)<1e-10,'independent learned timing residual binding')
  test(raw['hard_feasible']==(raw['service']['all']['on_time']==128 and len(done)==128),'hard goal arithmetic');test(raw['unfinished']==128-len(done),'unfinished denominator');test(raw['evidence']['new_RL']==0,'RL remains deferred')
  append(out/'COST_REPLAY_RECEIPTS.jsonl',dict(event='START',id=identity,raw_sha256=sha(p),replay_only=True,new_policy_environments=0))
  dt=cfg['power_dt_s'];end=150 if raw['right_censored_at150'] else 180;ts=np.arange(round(end/dt)+1)*dt;AP=predict(models['AP'],raw['activity'],s['context']['initial_context']['targets'],ts,old);power=predict(models['power'],raw['activity'],s['context']['initial_context']['targets'],ts,old);J=float(np.trapezoid(power,ts));apmean=float(np.trapezoid(AP[ts>=35],ts[ts>=35])/145);curve=np.array(raw['curve']);apcurve=predict(models['AP'],raw['activity'],s['context']['initial_context']['targets'],curve[:,0],old);pcurve=predict(models['power'],raw['activity'],s['context']['initial_context']['targets'],curve[:,0],old);err=max(float(np.max(abs(curve[:,1]-apcurve))),float(np.max(abs(curve[:,2]-pcurve))))
  if not raw['right_censored_at150']:err=max(err,abs(J-raw['J_API0_180']),abs(apmean-raw['AP35_180_mean']),abs(float(AP[-1])-raw['AP180']))
  if raw['sensor']:
   sensor=raw['sensor'];st=np.array([x['time'] for x in sensor]);sa=predict(models['AP'],raw['activity'],s['context']['initial_context']['targets'],st,old);err=max(err,float(np.max(abs(sa-np.array([x['AP'] for x in sensor])))));test(all(abs(x['available']-x['time']-.2)<1e-8 for x in sensor),'held sensor availability')
  maxerr=max(maxerr,err);test(err<1e-8,'independent offline AP/power/online-sensor replay '+identity)
  pr=dict(id=identity,raw_sha256=sha(p),max_abs_error=err,checks_so_far=checks,source_input_only=True,no_new_environment=True);proof=out/(identity+'_PROOF.json');save(proof,pr);append(out/'COST_REPLAY_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity,proof_sha256=sha(proof),max_abs_error=err));proofs.append(pr)
  save(out/('PROGRESS_'+str(i+1).zfill(4)+'.json'),dict(completed=i+1,total=len(plan),checks=checks,max_abs_error=maxerr,unix=time.time()))
 save(op['result_path'],dict(status='PASS',meaning='SAVED_TRACE_ARITHMETIC_AND_PUBLIC_RULES_AUDITED_NOT_PHYSICAL_ACCURACY',environments=len(plan),checks=checks,cost_replays=len(proofs),max_abs_error=maxerr,new_policy_environments=0,new_NN=0,new_RL=0,limitations='Monte Carlo draws are not independent phones; API-scale energy not external-meter calibration; R21 seen-development model. Full accuracy requires result comparison.'))
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
