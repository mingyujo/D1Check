"""Verify preservation of all prior followup files and new60 identities, catalog outputs."""
import datetime,hashlib,importlib.util,json,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent/'conclusion_extension_20261020';O=H/'artifacts/G001'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
 branch=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();tracked=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=R,text=True).splitlines();assert branch=='codex/s26-simulator-handoff-20261016' and head=='6cd0321ad87df72c8d24f94b0e3b8d66b604ae5f' and not tracked
 analysis=read(H/'ANALYSIS.json');summary=read(H/'IMPROVEMENT_SUMMARY.json');op=read(H/'OPERATION.json');assert analysis['status']=='PASS_GUARDED_BC_REPAIR_SAVED_AUDIT' and summary['adopted'] is False
 prior=read(E/'FILES_AFTER_RESEARCH.json')
 for p in prior['files']:assert sha(R/p['path'])==p['sha256'],'Prior512 research file changed: '+p['path']
 first=read(H.parent/'bc_service_repair_20261020/FILES.json')
 for p in first['files']:assert sha(R/p['path'])==p['sha256'],'First148 repair file changed: '+p['path']
 for p in op['original_pins']+op['new_source_pins']:assert sha(R/p['path'])==p['sha256'],'Source/original pin changed: '+p['path']
 receipts=[json.loads(line) for line in (O/'receipts.jsonl').read_text(encoding='utf-8').splitlines()];starts=[v for v in receipts if v['event']=='START'];assert len(starts)==len({v['identity'] for v in starts})==60
 prior_ids=set()
 for folder in [E,E.parent/'conclusion_candidate_20261020',E.parent/'conclusion_candidate_bridge_20261020',E.parent/'conclusion_atc_order_20261020',E.parent/'bc_service_repair_20261020']:
  prior_ids.update(v['identity'] for v in map(json.loads,(folder/'artifacts/G001/receipts.jsonl').read_text(encoding='utf-8').splitlines()) if v['event']=='START')
 assert not prior_ids&{v['identity'] for v in starts}
 result=read(O/'RESULT.json');assert sum(v['event']=='COMPLETE' for v in receipts)==result['COMPLETE'] and sum(v['event']=='FAIL' for v in receipts)==result['FAIL'] and result['COMPLETE']+result['FAIL']==60
 for row in result['rows']:
  assert read(O/(row['label']+'.json'))==row
  for suffix,key in [('.raw.json.gz','raw_sha256'),('.banks.jsonl.gz','banks_sha256')]:assert sha(O/(row['label']+suffix))==row[key]
 status=dict(status='COMPLETE_GUARDED_BC_REVIEW_NOT_ADOPTED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),official_final_unchanged=True,START=60,COMPLETE=result['COMPLETE'],FAIL=result['FAIL'],selected_candidate=summary['selected_before_confirm8'],next_actions=['Review explicit guarded-BC improvement and all scope/failure conditions','User alone decides adoption; existing official final remains unchanged','Further variants/learning/measurement require a new distinct registration'],blockers=[])
 (H/'STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 files=[dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['FILES.json','PRESERVATION.json']]
 save(H/'FILES.json',dict(files=files,count=len(files),exclusions=['__pycache__','FILES.json self','PRESERVATION.json']))
 save(H/'PRESERVATION.json',dict(status='PASS_OLD_FINAL_AND_PREVIOUS512_PRESERVED',utc=status['utc'],branch=branch,HEAD=head,tracked_changes=tracked,prior_followup_files_verified=len(prior['files']),prior_file_catalog_sha256=sha(E/'FILES_AFTER_RESEARCH.json'),original_and_source_pins_verified=len(op['original_pins'])+len(op['new_source_pins']),START=60,COMPLETE=result['COMPLETE'],FAIL=result['FAIL'],new_training=0,new_measurements=0,new_fit=0,completed_reruns=0,replacement_seeds=0,refunds=0,automation_or_reservation_queries=0,adopted=False,official_final='Original rolling+ATC+teacher initialization+PPO881087 unchanged',selected_followup=summary['selected_before_confirm8'],new_files=len(files),new_file_bytes=sum(v['bytes'] for v in files),file_catalog_sha256=sha(H/'FILES.json'),publication='Local only; no commit/push/release'))
 print('PRESERVATION_PASS',len(prior['files']),'prior files and',len(files),'new files; original final unchanged',flush=True)
if __name__=='__main__':
 spec=importlib.util.spec_from_file_location('delivery_shared_guard',E/'analyze.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.guarded(H,main)
