import datetime,hashlib,json,shutil,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[1];R=W/'S26-D1Check';S=R/'s26_simulator';H=S/'final_policy_20261019'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
assert not (H/'MANIFEST.json').exists()
runtime=r'C:\Users\user\anaconda3\python.exe';proc=subprocess.run([runtime,'-X','utf8','-B',str(S/'verify_final_policy.py')],cwd=R,capture_output=True,text=True,encoding='utf-8',check=True);verification=json.loads(proc.stdout);assert verification['status']=='PASS_ADOPTED_FROZEN_POLICY_BINDING';put(H/'VERIFICATION.json',verification)
shutil.copyfile(Path(__file__),H/'workspace_recovery'/Path(__file__).name)
entries=['s26_simulator/START_HERE.md','s26_simulator/STATUS.md','s26_simulator/HANDOFF.md','s26_simulator/docs/NEXT_STEPS.md','s26_simulator/AGENTS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']
files=[dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted([p for p in H.rglob('*') if p.is_file() and p.name not in ['MANIFEST.json','FINALIZATION_RECEIPT.json']]+[S/'FINAL_POLICY.json',S/'FINAL_POLICY_KO.md',S/'verify_final_policy.py',*[R/x for x in entries]])]
utc=datetime.datetime.now(datetime.timezone.utc).isoformat();manifest=dict(schema='S26_FINAL_POLICY_ADOPTION_MANIFEST_V1',utc=utc,root='repository',files=files,count=len(files),scope='Final adoption contract, entry-point administrative updates and their complete pre-adoption history, read-only SHA/source/result verification and recovery scripts. Frozen scientific source/checkpoint/result bytes are referenced by39 published source pins in FINAL_POLICY.json, not modified.',new_environment=0,new_training=0,new_fits=0,new_measurements=0,new_reservation=0)
put(H/'MANIFEST.json',manifest)
core=S/'CORE_MANIFEST.json';cd=read(core);changed=[Path(x).relative_to('s26_simulator').as_posix() for x in entries if x.startswith('s26_simulator/')]
for x in cd['files']:
 if x['path'] in changed:x.update(bytes=(S/x['path']).stat().st_size,sha256=sha(S/x['path']))
local=cd.setdefault('local_document_changes',[])
for rel in changed:
 prior=H/'history'/('s26_simulator/'+rel).replace('/','__');record=next((x for x in local if x['path']==rel),None)
 if record is None:record=dict(path=rel,parent_sha256=sha(prior));local.append(record)
 record['local_sha256']=sha(S/rel)
cd['final_policy_adoption']=dict(path='final_policy_20261019/MANIFEST.json',sha256=sha(H/'MANIFEST.json'),contract='FINAL_POLICY.json',contract_sha256=sha(S/'FINAL_POLICY.json'),model='route_group_learning_v1/S881087_FINAL',seed=881087,checkpoint_sha256=read(S/'FINAL_POLICY.json')['representative']['checkpoint']['file_sha256'],new_environment=0,new_training=0,new_fits=0,uploaded=False)
put(core,cd)
for item in files:
 p=R/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],item['path']
for item in local:assert sha(S/item['path'])==item['local_sha256']
receipt=dict(status='PASS_FINAL_POLICY_ADOPTED_AND_BOUND_TO_PUBLISHED_CHECKPOINT',utc=utc,seed=881087,manifest_sha256=sha(H/'MANIFEST.json'),core_sha256=sha(core),contract_sha256=sha(S/'FINAL_POLICY.json'),verification_checks=verification['checks'],published_scientific_pins=verification['source_pins'],new_environment=0,new_training=0,new_measurements=0,new_fits=0,new_reservation=0,uploaded=False,local_uncommitted=True)
put(H/'FINALIZATION_RECEIPT.json',receipt);put(W/'recovery/S26_FINAL_POLICY_ADOPTION_RECEIPT.json',receipt);print(json.dumps(receipt))
