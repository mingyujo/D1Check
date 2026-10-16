"""Revalidate all56 complete saved audit proofs; repair only P0/main summary split.
No Simulator, forward policy call, cost integration, fitting or NN is performed.
"""
import collections,hashlib,json,os,time
from pathlib import Path
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def main(op):
 out=Path(op['output_dir']);out.mkdir();prior=read(op['prior_audit_operation']);prod=read(prior['production_operation']);failure=read(Path(prior['runtime_dir'])/'FAILED.json');assert failure['traceback'].endswith('ValueError: all48 dynamic cases\n');assert not Path(prior['result_path']).exists()
 plan=read(prod['case_plan_path']);rows=[json.loads(l) for l in (Path(prod['output_dir'])/'ROWS.jsonl').read_text().splitlines()];receipts=collections.defaultdict(list)
 for l in (Path(prior['output_dir'])/'COST_REPLAY_RECEIPTS.jsonl').read_text().splitlines():
  e=json.loads(l);receipts[e['id']].append(e)
 checks=0;previous_checks=0;maxerror=0.;dynamic=[];counts=collections.Counter();candidate_counts=collections.Counter();proof_links=[]
 def test(v,s):
  nonlocal checks;checks+=1
  if not v:raise ValueError(s)
 test(len(rows)==len(plan)==len(receipts)==56,'56 exact saved proofs and rows')
 for cfg,row in zip(plan,rows):
  identity=cfg['identity'];test(identity==row['logical_identity'],'exact identity order');proofpath=Path(prior['output_dir'])/(identity+'_PROOF.json');proof=read(proofpath);events=receipts[identity];test([e['event'] for e in events]==['START','COMPLETE'],'cost replay already fully terminal');test(sha(proofpath)==events[1]['proof_sha256'],'saved proof digest');test(sha(row['raw_path'])==row['raw_sha256']==proof['raw_sha256']==events[0]['raw_sha256'],'exact saved raw binding');test(proof['status']=='PASS' and proof['max_abs_error']<1e-8,'individual action and cost replay passed');test(proof['checks_so_far']>previous_checks,'complete ordered prior audit coverage');previous_checks=proof['checks_so_far'];maxerror=max(maxerror,proof['max_abs_error']);proof_links.append(dict(id=identity,proof=str(proofpath),sha256=sha(proofpath),completed_checks=previous_checks))
  if cfg['phase']!='RESOURCE_DYNAMIC':continue
  test(cfg['policy']=='ROLLING_ATC_ROUTE_V2','main own policy');raw=read(row['raw_path']);dynamic.append(raw);counts.update(raw['policy_route_counts']);test(raw['routing_contract']['classification_routes']==['classification_CPU','classification_GPU','classification_NPU'],'all3 routes enabled');test(raw['policy_decisions'],'actual action log present')
  for d in raw['policy_decisions']:
   a=d['action'];candidate_counts.update(c['route'] for c in a['candidates']);
   if a['kind']=='DISPATCH':
    task=next(q['task'] for q in d['public_observation']['ready'] if q['ordinal']==a['ordinal']);routes={c['route'] for c in a['candidates'] if c['ordinal']==a['ordinal']};test(routes==({'classification_CPU','classification_GPU','classification_NPU'} if task=='classification' else {'detection_CPU'}),'complete per-request route candidates')
 test(len(dynamic)==48,'P0 excluded, exactly48 main');test(all(candidate_counts[r]>0 for r in ('classification_CPU','classification_GPU','classification_NPU')),'all3 considered');test(sum(counts.values())==48*128,'all128 requests retained in main aggregate')
 result=dict(status='PASS',meaning='SAVED56_ACTION_COST_PROOFS_REVALIDATED_AND_MAIN48_SUMMARY_REPAIRED_NOT_PHYSICAL_ACCURACY_OR_RL',checks=previous_checks+checks,prior_completed_checks=previous_checks,new_binding_summary_checks=checks,new_policy_environments=0,new_cost_replays=0,new_NN=0,new_RL=0,production_cases=56,P0_cases=8,dynamic_cases=48,cost_replays=56,max_abs_error=maxerror,candidate_route_counts=dict(candidate_counts),selected_route_counts=dict(counts),feasible_conditions=sum(r['hard_feasible'] for r in dynamic),on_time_mean=sum(r['service']['all']['on_time'] for r in dynamic)/48,J_mean=sum(r['J_API0_180'] for r in dynamic)/48,AP_mean=sum(r['AP35_180_mean'] for r in dynamic)/48,all_losses_retained=True,original_audit_failed_preserved=True,repair='Prior summary counted2 dynamic P0 cases plus48 main=50; only filter phase RESOURCE_DYNAMIC for summary. All56 prior per-case audits had completed.',source_proofs=proof_links)
 save(op['result_path'],result)
if __name__=='__main__':main(read(os.environ['S26_UNIFIED_OPERATION']))
