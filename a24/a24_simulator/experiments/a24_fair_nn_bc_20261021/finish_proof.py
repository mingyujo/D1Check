"""Saved-only final seal/recheck; no training/simulation."""
import ast,collections,datetime,hashlib,json,re,subprocess,sys
from pathlib import Path
from urllib.parse import unquote
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_FAIR_NN_BC_20261021_01'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def check(p):
    f=R/p['path'];assert f.is_file() and f.stat().st_size==p['bytes'] and sha(f)==p['sha256'],str(f)
def walk(x):
    if isinstance(x,dict):
        if all(k in x for k in ('path','bytes','sha256')):yield x
        for v in x.values():yield from walk(v)
    elif isinstance(x,list):
        for v in x:yield from walk(v)
def new(n,x):
    with (O/n).open('x',encoding='utf8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
op=read(H/'OPERATION.json');result=read(O/'RESULT.json');previous=read(R/'a24_simulator/results/A24_SERVICE_BC_REPAIR_20261021_01/FINAL_PROOF.json');older=read(R/'a24_simulator/results/A24_BC_S26_REQUESTS_20261021_01/FINAL_PROOF.json');oldest=read(R/'a24_simulator/results/A24_BC_RECOVERY_20261021_01/FINAL_PROOF.json')
preserved=read(H.parent/'a24_s26_common_20261020/SOURCE_BINDING.json')['preserved_completed_files'];unique={}
for p in list(walk(op))+list(walk(result))+previous['files']+older['files']+oldest['files']+preserved:
    if p['path'] in unique:assert unique[p['path']]['sha256']==p['sha256']
    else:check(p);unique[p['path']]=p
receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text(encoding='utf8').splitlines()];counts=collections.Counter(x['event'] for x in receipts);starts={x['start_id']:x['label'] for x in receipts if x['event']=='START'};ends={x['start_id']:x['label'] for x in receipts if x['event']=='COMPLETE'}
assert counts=={'START':12,'COMPLETE':12} and starts==ends and result['science_START']==12
assert collections.Counter(x['kind'] for x in receipts if x['event']=='START')=={'BC_FIT':2,'TRAIN':6,'EVAL':4}
assert all(x['status']=='COMPLETE' for x in result['rows']) and not (O/'BATCH_FAILURE.json').exists()
for f in ('AUDIT_JS.json','AUDIT_PY.json','AUDIT_LABELS_JS.json','DIAGNOSTICS.json'):assert read(O/f)['status']=='PASS'
assert len(read(O/'ACCOUNTING.json')['rows'])==32 and len(read(O/'ACCOUNTING.json')['aggregates'])==16
for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head=='ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf'
controls=[R/p for p in ('docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/docs/LATEST_EXECUTION_FILES.md')]
if sys.argv[1:]==['--seal']:
    files=[pin(p) for folder in (H,O) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('FINAL_PROOF.json','FINAL_RECHECK.json')]
    new('FINAL_PROOF.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=head,working_tree_uncommitted=True,files=files,source_and_prior_unique_files_verified=len(unique),scientific_receipts=dict(counts),new_TRAIN=6,new_BC_fit=2,new_EVAL=4,new_cost_regression_fit=0,new_measurement=0,new_PPO=0,new_physical_fit=0,science_retried=0,original_neural_architecture_unchanged=True,original_checkpoint_unchanged=True,automatic_adoption=False,published=False))
elif sys.argv[1:]==['--verify']:
    proof=read(O/'FINAL_PROOF.json')
    for p in proof['files']:check(p)
    texts=[(p,p.read_text(encoding='utf8')) for folder in (H,O) for p in folder.glob('*.md')];texts += [(p,p.read_text(encoding='utf8').split('\n## ',1)[0]) for p in controls];targets=0
    for p,text in texts:
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            if link.startswith(('http:','https:','#','codex:')):continue
            q=(p.parent/unquote(link.split('#',1)[0].strip('<>'))).resolve()
            if q!=(O/'FINAL_RECHECK.json').resolve():assert q.exists(),f'{p}: {link}'
            targets+=1
    for p in controls:assert p.read_text(encoding='utf8').splitlines()[0].startswith('## 2026-10-21 A24-FAIR-NNBC-03')
    subprocess.run(['git','diff','--check'],cwd=R,check=True)
    new('FINAL_RECHECK.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=head,proof_sha256=sha(O/'FINAL_PROOF.json'),sealed_files=len(proof['files']),source_and_prior_unique_files_verified=len(unique),scientific_receipts=dict(counts),linked_targets=targets,control_docs=[pin(p) for p in controls],git_diff_check='PASS',new_environment=0,new_fit=0))
else:raise SystemExit('Explicit --seal / --verify')
print('FINAL_SAVED_CHECK_PASS',dict(counts),len(unique),flush=True)
