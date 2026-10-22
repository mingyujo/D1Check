"""Post-audit descriptive comparison. No policy environment, fitting, or cost replay.
CI resamples four extraction streams, preserving every shared fixed design cell.
"""
import csv,datetime,gzip,hashlib,importlib.util,json,math,msvcrt,random,sys,traceback
from pathlib import Path
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def mean(xs):
 xs=[x for x in xs if x is not None];return sum(xs)/len(xs) if xs else None
def percentile(xs,q):
 xs=sorted(xs);i=(len(xs)-1)*q;lo=math.floor(i);hi=math.ceil(i);return xs[lo]+(xs[hi]-xs[lo])*(i-lo)
def ci(rows,field):
 units=[mean([r[field] for r in rows if r['draw']==d]) for d in range(4)];units=[v for v in units if v is not None]
 if len(units)<2:return dict(mean=mean(units),low=None,high=None,stream_clusters=len(units))
 rng=random.Random(271019099);samples=[sum(rng.choice(units) for _ in units)/len(units) for _ in range(2000)];return dict(mean=mean(units),low=percentile(samples,.025),high=percentile(samples,.975),stream_clusters=len(units),method='Conditional paired extraction-stream bootstrap2000; fixed design cells retained, not independent phone uncertainty')
def main(op_path):
 op=json.loads(Path(op_path).read_text(encoding='utf-8-sig'));owner=module('registered_owner',op['owner_source']);owner.verify(op);census=owner.Census();handle=None;locked=False;out=Path(op['output_dir'])
 def table(name,rows):
  if not rows:return
  keys=list(rows[0]);f=(out/name).open('x',encoding='utf-8-sig',newline='')
  with f:
   w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
   for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else 'NA' if v is None else v for k,v in r.items()})
 try:
  own=census.get();handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;out.mkdir();owner.save(out/'OWNER.json',own['self']);root=Path(op['production_dir']);audit=root/'AUDIT_V1';proof=owner.read(audit/'FINAL_AUDIT.json');assert proof['status']=='PASS' and proof['cases']==3240
  allrows=[json.loads(l) for l in (root/'ROWS.jsonl').read_text().splitlines() if l];evalrows=[r for r in allrows if r['phase']=='EVAL'];assert len(evalrows)==2592;rows=[];view=[];raw_bindings=[]
  for index,r in enumerate(evalrows):
   if index%64==0:census.get()
   c=r['config'];identity=r['logical_identity'];p=owner.read(audit/(identity+'.proof.json'));assert p['status']=='PASS' and p['raw_sha256']==r['raw_sha256'];raw=Path(r['raw_path']);assert owner.sha(raw)==r['raw_sha256'];x=json.loads(gzip.decompress(raw.read_bytes()));assert x['logical_identity']==identity
   row=dict(id=identity,policy=c['policy'],capacity=c['capacity'],model=c['model'],bank=c['bank'],burst=c['burst'],context=c['context_index'],draw=c['draw'],allocator=c['allocator'],hard_feasible=r['hard_feasible'],completed=r['service']['all']['completed'],planned=r['service']['all']['planned'],U_on=r['service']['urgent']['on_time'],U_planned=r['service']['urgent']['planned'],N_on=r['service']['normal']['on_time'],N_planned=r['service']['normal']['planned'],all_on=r['service']['all']['on_time'],unfinished=r['unfinished'],completed_tardiness_s=r['tardiness_s'],U_p95_s=r['service']['urgent']['p95_s'],N_p95_s=r['service']['normal']['p95_s'],all_p95_s=r['service']['all']['p95_s'],J120=p['physical']['J120'],J180=r['J_API0_180'],APmean=r['AP35_180_mean'],AP180=r['AP180'],peak=r['AP_peak_sampled'],three_infer_s=p['physical']['actual_three_inference_s'],two_plus_infer_s=p['physical']['actual_two_or_more_inference_s'],CPU_busy_s=p['physical']['CPU_busy_s'],CPU_wait_s=r['shared_cpu_wait_s'],max_owners=r['max_owners'],max_ready=r['max_ready_queue'],routes=r['policy_route_counts'],nominal_compute=r['nominal_compute'],WAIT_s=r['wait_s'],right_censored=r['right_censored_at150'],raw_sha256=r['raw_sha256'],audit_proof_sha256=owner.sha(audit/(identity+'.proof.json')));rows.append(row)
   routes=['classification_CPU','classification_GPU','classification_NPU','detection_CPU'];phases=['ADMISSION','INFER','POST'];req=[]
   for q in x['requests']:
    t=q['times'];req.append([q['ordinal'],routes.index(q['route']),q['priority']=='normal',q['arrival'],q['deadline'],q['response']]+[t.get(k) for k in ('dispatch','execution_start','host_inference_start','host_inference_return','output_ready','persist_complete','worker_release','readback_start','readback_end','AVAILABLE')])
   for q in x['active_at_censor']:
    t=q['times'];planned=next(v for v in x['planned_requests'] if v['ordinal']==q['ordinal']);req.append([q['ordinal'],routes.index(q['route']),planned['priority']=='normal',planned['arrival'],planned['deadline'],None]+[t.get(k) for k in ('dispatch','execution_start','host_inference_start','host_inference_return','output_ready','persist_complete','worker_release','readback_start','readback_end','AVAILABLE')])
   view.append(dict(row=row,curve=x['curve'],requests=req,cpu=[[v['start'],v['end'],v['ordinal'],routes.index(v['route']),phases.index(v['phase'])] for v in x['cpu_intervals']],planned=[[v['ordinal'],v['priority']=='normal',v['arrival'],v['deadline'],v['readyAt']] for v in x['planned_requests']]));raw_bindings.append(dict(id=identity,raw_sha256=r['raw_sha256'],proof_sha256=row['audit_proof_sha256']))
  def key(r):return tuple(r[k] for k in ('capacity','model','bank','burst','context','draw'))
  by={(r['policy'],key(r)):r for r in rows};details={(c['row']['policy'],key(c['row'])):c for c in view};pairs=[];levels=[]
  for own in [r for r in rows if r['policy']=='ATC']:
   for policy in ('FIFO','EDF'):
    base=by[(policy,key(own))];finite=all(r['J180'] is not None and r['APmean'] is not None for r in (own,base));dJ=own['J180']-base['J180'] if finite else None;dAP=own['APmean']-base['APmean'] if finite else None;both=own['hard_feasible'] and base['hard_feasible'];no_service_loss=own['U_on']>=base['U_on'] and own['N_on']>=base['N_on'] and own['completed']>=base['completed'];joint=finite and dJ<-1e-8 and dAP<-1e-8
    pair={k:own[k] for k in ('capacity','model','bank','burst','context','draw')};pair.update(id=own['id'],baseline_id=base['id'],baseline=policy,dJ180=dJ,dJ_pct=100*dJ/base['J180'] if finite else None,dAPmean=dAP,dPeak=own['peak']-base['peak'],dAP180=own['AP180']-base['AP180'] if finite else None,dU_on=own['U_on']-base['U_on'],dN_on=own['N_on']-base['N_on'],dCompleted=own['completed']-base['completed'],dTardiness_completed_s=own['completed_tardiness_s']-base['completed_tardiness_s'],own_hard=own['hard_feasible'],base_hard=base['hard_feasible'],both_hard=both,no_service_loss=no_service_loss,valid_full_cost_pair=finite,joint_decrease=joint,deadline_safe_joint=bool(joint and own['hard_feasible'] and no_service_loss),both_hard_joint=bool(joint and both),strict10pct_05C=bool(finite and own['hard_feasible'] and no_service_loss and dJ/base['J180']<=-.1 and dAP<=-.5));pairs.append(pair)
    qa={q[0]:q for q in details[('ATC',key(own))]['requests']};qb={q[0]:q for q in details[(policy,key(own))]['requests']};shared=set(qa)&set(qb);pair['route_changed_requests']=sum(qa[i][1]!=qb[i][1] for i in shared);pair['dispatch_time_changed_requests']=sum(abs(qa[i][6]-qb[i][6])>1e-8 for i in shared);pair['response_changed_requests']=sum(qa[i][5] is not None and qb[i][5] is not None and abs(qa[i][5]-qb[i][5])>1e-8 for i in shared);pair['common_started_requests']=len(shared)
    for service in (70,80,90,95,100):
     for priority in ('urgent','normal','all'):
      a,b,pn=('U_on','U_planned',own['U_planned']) if priority=='urgent' else ('N_on','N_planned',own['N_planned']) if priority=='normal' else ('all_on','planned',own['planned']);eligible=own['completed']==own['planned'] and base['completed']==base['planned'] and pn>0 and own[a]/own[b]>=service/100 and base[a]/base[b]>=service/100;levels.append(dict(**{k:pair[k] for k in ('capacity','model','bank','burst','context','draw','baseline')},service=service,priority=priority,priority_has_requests=pn>0,eligible_both=eligible,dJ180=dJ,dAPmean=dAP,joint_at_service=bool(eligible and joint),own_priority_on=own[a],base_priority_on=base[a],priority_planned=pn,own_completed=own['completed'],base_completed=base['completed']))
  assert len(pairs)==1728 and len(levels)==25920
  summary=[];comparison=[]
  for cap in (1,2,3):
   for model in ('LOW','CENTRAL','HIGH'):
    for policy in ('FIFO','EDF','ATC'):
     rs=[r for r in rows if r['capacity']==cap and r['model']==model and r['policy']==policy];summary.append(dict(policy=policy,capacity=cap,model=model,cases=len(rs),hard_feasible_cases=sum(r['hard_feasible'] for r in rs),full_cost_cases=sum(r['J180'] is not None for r in rs),U_on=sum(r['U_on'] for r in rs),U_planned=sum(r['U_planned'] for r in rs),N_on=sum(r['N_on'] for r in rs),N_planned=sum(r['N_planned'] for r in rs),completed=sum(r['completed'] for r in rs),planned=sum(r['planned'] for r in rs),unfinished=sum(r['unfinished'] for r in rs),mean_J180=mean([r['J180'] for r in rs]),mean_AP=mean([r['APmean'] for r in rs]),mean_peak=mean([r['peak'] for r in rs]),mean_AP180=mean([r['AP180'] for r in rs]),mean_case_P95_s=mean([r['all_p95_s'] for r in rs]),mean_CPU_wait_s=mean([r['CPU_wait_s'] for r in rs]),mean_three_infer_s=mean([r['three_infer_s'] for r in rs]),actual_three_infer_cases=sum(r['three_infer_s']>1e-9 for r in rs)))
    for base in ('FIFO','EDF'):
     ps=[p for p in pairs if p['capacity']==cap and p['model']==model and p['baseline']==base];comparison.append(dict(capacity=cap,model=model,baseline=base,cases=len(ps),both_hard=sum(p['both_hard'] for p in ps),deadline_safe_joint=sum(p['deadline_safe_joint'] for p in ps),both_hard_joint=sum(p['both_hard_joint'] for p in ps),strict10pct_05C=sum(p['strict10pct_05C'] for p in ps),dJ180_CI=ci(ps,'dJ180'),dJpct_CI=ci(ps,'dJ_pct'),dAP_CI=ci(ps,'dAPmean'),dU_on=mean([p['dU_on'] for p in ps]),dN_on=mean([p['dN_on'] for p in ps])))
  reversals=[]
  for cap in (1,2,3):
   for base in ('FIFO','EDF'):
    for bank in ('C_ONLY','MIX'):
     for burst in (4,8,16,32):
      for context in (0,1,2):
       values={m:{k:mean([p[k] for p in pairs if p['capacity']==cap and p['baseline']==base and p['model']==m and p['bank']==bank and p['burst']==burst and p['context']==context]) for k in ('dJ180','dAPmean')} for m in ('LOW','CENTRAL','HIGH')};J=[v['dJ180'] for v in values.values() if v['dJ180'] is not None];AP=[v['dAPmean'] for v in values.values() if v['dAPmean'] is not None];reversals.append(dict(capacity=cap,baseline=base,bank=bank,burst=burst,context=context,values=values,J_sign_reversal=bool(J and min(J)<-1e-8 and max(J)>1e-8),AP_sign_reversal=bool(AP and min(AP)<-1e-8 and max(AP)>1e-8)))
  owner.save(out/'SUMMARY.json',summary);owner.save(out/'PAIRED.json',pairs);owner.save(out/'SERVICE_LEVELS.json',levels);owner.save(out/'COMPARISONS.json',comparison);owner.save(out/'MODEL_REVERSALS.json',reversals);owner.save(out/'RAW_BINDINGS.json',raw_bindings)
  for n,rs in [('all_conditions.csv',rows),('summary.csv',summary),('paired_ATC.csv',pairs),('service_levels.csv',levels),('comparisons.csv',comparison),('model_reversals.csv',reversals)]:table(n,rs)
  metadata=dict(schema='S26_MULTIRESOURCE_VIEW_DATA_V1',generation='MULTI001_G004',registered_policy_environments=3240,EVAL_rows=2592,policy_set=['FIFO','EDF','ATC'],fit_count_separate=56,new_RL=0,raw_fit_inventory=228,AP_fit_sessions=210,power_fit_sessions=209,calibration_error=dict(AP_session_MAE_C=1.0976044119413273,power_median_abs_relative_area_error=.14640071021202408),uncertainty='Conditional synthetic empirical-population comparison. The four extraction streams are not independent phone samples; transfer pairs/triples, CPU service and phase-power proxies remain assumptions. HAL AP is not skin; API-unit hypothesis energy is not external-meter calibrated.',default_case=dict(capacity=3,model='CENTRAL',bank='MIX',burst=16,context=0,draw=0),analysis_operation_sha256=owner.sha(op_path),audit_sha256=owner.sha(audit/'FINAL_AUDIT.json'),registration_sha256=op['registration_sha256'],summary=summary,comparisons=comparison,model_reversals=reversals)
  payload=json.dumps(dict(metadata=metadata,cases=view),ensure_ascii=False,allow_nan=False,separators=(',',':')).encode();gz=gzip.compress(payload,compresslevel=6,mtime=0);assert gzip.decompress(gz)==payload;(out/'VIEW_DATA.json.gz').write_bytes(gz);owner.save(out/'VIEW_DATA_RECEIPT.json',dict(status='PASS',compressed_sha256=hashlib.sha256(gz).hexdigest(),payload_sha256=hashlib.sha256(payload).hexdigest(),compressed_bytes=len(gz),payload_bytes=len(payload),EVAL_rows=2592));owner.verify(op);owner.save(out/'RESULT.json',dict(status='PASS',EVAL_rows=2592,pairs=1728,service_level_rows=25920,raw_and_audit_bindings=2592,CI='Four extraction-stream conditional bootstrap2000, seed271019099',models_not_random_samples=True,no_policy_selection_from_EVAL=True,new_policy_environments=0,new_cost_replay=0,new_fit=0,new_RL=0))
 except BaseException:
  if out.exists():owner.save(out/'FAILURE.json',dict(status='FAILED_PRESERVED',traceback=traceback.format_exc()))
  raise
 finally:
  if handle:
   if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
   handle.close()
  census.close()
if __name__=='__main__':main(Path(sys.argv[1]))
