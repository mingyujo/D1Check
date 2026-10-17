"""Saved-data accounting/selection/semantic supplement; no policy, cost replay or fit."""
import datetime,hashlib,importlib.util,json,msvcrt,sys,traceback
from pathlib import Path

def main(op_path):
 op=json.loads(Path(op_path).read_text(encoding='utf-8-sig'));s=importlib.util.spec_from_file_location('registered_owner',op['owner_source']);owner=importlib.util.module_from_spec(s);s.loader.exec_module(owner);owner.verify(op);census=owner.Census();handle=None;locked=False;out=Path(op['output_dir']);checks=0
 def test(x,label):
  nonlocal checks
  checks+=1
  if not x:raise AssertionError(label)
 try:
  own=census.get();handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;out.mkdir();owner.save(out/'OWNER.json',own['self']);production=owner.read(op['production_operation']);root=Path(production['output_dir']);audit=owner.read(root/'AUDIT_V1/FINAL_AUDIT.json');test(audit['status']=='PASS' and audit['cases']==3240,'full independent audit prerequisite')
  rowbytes=(root/'ROWS.jsonl').read_bytes();lines=rowbytes.splitlines(keepends=True);rows=[json.loads(l) for l in lines if l.strip()];test(len(rows)==3240,'all3240rows');receipts=[json.loads(l) for l in Path(production['receipts_path']).read_text(encoding='utf-8-sig').splitlines() if l.strip()];ids={r['logical_identity'] for r in rows};test(len(ids)==3240,'unique identities')
  for event in ('START','PREPARED','COMPLETE'):test(len([r for r in receipts if r['event']==event])==3240 and {r['id'] for r in receipts if r['event']==event}==ids,'full event coverage '+event)
  test(not any(r['event']=='FAIL' for r in receipts),'G004 no FAIL');dev=[r for r in rows if r['phase']=='DEV'];test(len(dev)==576,'DEV576');freeze=owner.read(root/'DEV_SELECTION_FREEZE.json');test(hashlib.sha256(b''.join(lines[:648])).hexdigest()==freeze['DEV_rows_sha256'],'exact prefix byte SHA beforeEVAL');scores={}
  for allocator in ('WEIGHTED','NO_THERMAL_HARM'):
   selected=[r for r in dev if r['config']['allocator']==allocator];harm=peak=0
   for r in selected:
    matches=[x for x in dev if x['config']['allocator']=='WEIGHTED' and all(x['config'][k]==r['config'][k] for k in ('bank','burst','context_index','model','stream','policy','capacity'))];test(len(matches)==1,'unique matched DEV');m=matches[0];harm+=max(0,r['AP35_180_mean']-m['AP35_180_mean']);peak+=max(0,r['AP_peak_sampled']-m['AP_peak_sampled'])
   scores[allocator]=[sum(128-r['service']['all']['on_time'] for r in selected),sum(r['unfinished'] for r in selected),harm,peak,sum(r['J_API0_180'] for r in selected),int(allocator!='WEIGHTED')]
  test(scores==freeze['scores'],'exact registered lexicographic scores');test(min(scores,key=lambda k:tuple(scores[k]))==freeze['allocator'],'single global DEV selection');frozen_time=datetime.datetime.fromisoformat(freeze['utc']);starts=[x for x in receipts if x['event']=='START'];phase={r['logical_identity']:r['phase'] for r in rows};test(all(datetime.datetime.fromisoformat(x['utc'])>frozen_time for x in starts if phase[x['id']]=='EVAL'),'all EVAL START afterfreeze');recipe=owner.read(production['eval_recipe_path']);sealed=owner.read(root/'EVAL_CASE_PLAN_SEALED.json');expected=[]
  for r in recipe:
   r=dict(r);r['allocator']=freeze['allocator'];r['identity']=r['identity'].replace('SELECTED_AFTER_DEV',freeze['allocator']);expected.append(r)
  test(sealed==expected,'no EVAL reselection or recipe mutation');test(len(sealed)==2592,'EVAL2592')
  packet=owner.read(production['packet_path']);overlay=owner.read(op['overlay']);packet_sha=owner.sha(production['packet_path']);test(packet_sha==overlay['actual_packet_sha256'],'packet overlay');modes=[]
  def scan(x):
   if isinstance(x,dict):
    if 'mode' in x:modes.append(x['mode'])
    for v in x.values():scan(v)
   elif isinstance(x,list):
    for v in x:scan(v)
  scan(packet);test('POSITIVE_ADDITIVE' in modes and 'POSITIVE_ACTIVITY_DYNAMIC' in modes,'actual numeric model modes');lineage=rows[0]['evidence']['calibration_lineage']
  for i,r in enumerate(rows):
   if i%128==0:census.get()
   test(r['packet_sha256']==packet_sha and r['generation']=='MULTI001_G004','row sealed numeric binding');test(r['work_rate_sampling']=='MIDPOINT_WITH_EVENT_ROOT_V1','actual numerical scheme');test(r['evidence']['calibration_lineage']==lineage and lineage['fits']==56,'measurement-only fit lineage');test(r['evidence']['new_RL']==0 and r['evidence']['new_fit']==0,'no policyfit/RL');test(r['evidence']['new_pairs']==rows[0]['evidence']['new_pairs'],'transfer assumption preserved')
  test(owner.sha(lineage['audit_result_path'])==lineage['audit_result_sha256'],'independent calibration audit SHA');test(owner.read(lineage['audit_result_path'])['status']=='PASS','calibration independent PASS')
  ledgers=[];seen=set();global_starts=0
  for p in production['global_accounting_ledgers']+op['additional_global_ledgers']+[production['receipts_path']]:
   canonical=str(Path(p).resolve()).lower()
   if canonical in seen:continue
   seen.add(canonical);f=Path(p);events=[json.loads(l) for l in f.read_text(encoding='utf-8-sig').splitlines() if l.strip()] if f.exists() else [];n=sum(r.get('event')=='START' for r in events);global_starts+=n;ledgers.append(dict(path=p,canonical=canonical,START=n,sha256=owner.sha(f) if f.exists() else None))
  budget=owner.read(op['budget_path']);test(global_starts<=production['global_cap'] and production['global_reserved']==124574 and budget['global_reserved']==124574,'global budget');extra=sum(x['START'] for x in ledgers if x['canonical'] in {str(Path(p).resolve()).lower() for p in op['additional_global_ledgers']});latest=owner.read(op['latest_budget_path']);test(latest['global_reserved']==124582 and latest['previous_global_reserved']==124574,'new A24 reservation chain');test(global_starts==budget['actual_prior_START']+3240+extra,'all known current START counts, no duplicate path');test(extra==7,'A24 RR seven starts within cap8 consumed separately');test(all(x['global_START_after']==budget['actual_prior_START']+i+1+(extra if i>=2711 else 0) for i,x in enumerate(starts)),'every recorded global START progression across recovery');test(all('continuation_operation_sha256' in x for x in starts[2711:]),'recovery START binding');test(budget['parent_consumed']==20 and 3240+20<=3328,'shared reservation and consumed predecessors');cost=[]
  for name,n in [('P0_COST_REPLAY_RECEIPTS.jsonl',72),('AUDIT_V1/COST_REPLAY_RECEIPTS.jsonl',3240)]:
   f=root/name;es=[json.loads(l) for l in f.read_text().splitlines() if l.strip()];counts={k:sum(x['event']==k for x in es) for k in ('START','COMPLETE')};test(counts=={'START':n,'COMPLETE':n},'separate physical audit consumption '+name);cost.append(dict(path=str(f),sha256=owner.sha(f),**counts))
  owner.verify(op);owner.save(out/'RESULT.json',dict(status='PASS',checks=checks,rows=3240,exact_DEV_scores=scores,selected_allocator=freeze['allocator'],global_START=global_starts,global_reserved=124582,original_G004_reserved=124574,global_cap=137712,multi_reserved=3328,multi_consumed=3260,multi_unused=68,ledgers=ledgers,separate_cost_replay=cost,evidence_overlay_sha256=owner.sha(op['overlay']),actual_AP='POSITIVE_ACTIVITY_DYNAMIC',actual_power='POSITIVE_ADDITIVE',separate_calibration_fits=56,original_evidence_strings_preserved=True,new_policy_environments=0,new_cost_replay=0,new_fit=0,new_RL=0))
 except BaseException:
  if out.exists():owner.save(out/'FAILURE.json',dict(status='FAILED_PRESERVED',traceback=traceback.format_exc()))
  raise
 finally:
  if handle:
   if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
   handle.close()
  census.close()
if __name__=='__main__':main(sys.argv[1])
