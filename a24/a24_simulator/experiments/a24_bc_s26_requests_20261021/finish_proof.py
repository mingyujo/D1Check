"""Standard-library saved artifact seal/recheck. No scientific execution."""
import ast,collections,datetime,hashlib,json,re,subprocess,sys
from pathlib import Path
from urllib.parse import unquote
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_BC_S26_REQUESTS_20261021_01'

def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def check(v):
    p=Path(v['path']);p=p if p.is_absolute() else R/p
    assert p.is_file() and p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],str(p)
def walk(x):
    if isinstance(x,dict):
        if all(k in x for k in ('path','bytes','sha256')):yield x
        for v in x.values():yield from walk(v)
    elif isinstance(x,list):
        for v in x:yield from walk(v)
def write(name,v):
    with (O/name).open('x',encoding='utf8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    op=read(H/'OPERATION.json');result=read(O/'RESULT.json');pins=list(walk(op))+list(walk(result))+list(walk(read(H/'SUPPLEMENTAL_SOURCES.json')))
    previous=read(R/'a24_simulator/results/A24_BC_RECOVERY_20261021_01/FINAL_PROOF.json')
    preserved=read(R/'a24_simulator/experiments/a24_s26_common_20261020/SOURCE_BINDING.json')['preserved_completed_files']
    pins+=previous['files']+preserved;unique={}
    for p in pins:
        if p['path'] in unique:assert unique[p['path']]['sha256']==p['sha256']
        else:check(p);unique[p['path']]=p
    assert result['network_sha256']=='cec00807e6729c4f59bbb74723749eeb2db722786c55a7d754b1253477eb6ad7'
    receipts=[json.loads(s) for s in (O/'receipts.jsonl').read_text(encoding='utf8').splitlines()]
    events=collections.Counter(x['event'] for x in receipts)
    starts={x['start_id']:x['label'] for x in receipts if x['event']=='START'}
    terminal={x['start_id']:x['label'] for x in receipts if x['event'] in ('COMPLETE','FAIL')}
    assert len(starts)<=20 and starts==terminal and result['science_START']==len(starts)
    assert all(read(O/f)['status']=='PASS' for f in ('AUDIT_JS.json','AUDIT_PY.json','DIAGNOSTICS.json'))
    audit_ast=lambda p:ast.dump(next(x for x in ast.parse(p.read_text(encoding='utf8')).body if isinstance(x,ast.FunctionDef) and x.name=='audit'),include_attributes=False)
    assert audit_ast(H/'post.py')==audit_ast(H/'POST_BEFORE_ANALYSIS_FIX.py.txt')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
    assert head=='ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf'
    control=[R/p for p in ('docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/docs/LATEST_EXECUTION_FILES.md')]
    if sys.argv[1:]==['--seal']:
        files=[pin(p) for folder in (H,O) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('FINAL_PROOF.json','FINAL_RECHECK.json')]
        write('FINAL_PROOF.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=head,working_tree_uncommitted=True,
              files=files,source_and_prior_unique_files_verified=len(unique),prior_recovery_files=len(previous['files']),preserved_original_files=len(preserved),
              scientific_receipts=dict(events),audit_function_unchanged_after_saved_report_fix=True,original_policy_unchanged=True,new_training=0,new_fit=0,new_measurement=0,new_physical_fit=0,adopted=False,published=False))
    elif sys.argv[1:]==['--verify']:
        proof=read(O/'FINAL_PROOF.json')
        for v in proof['files']:check(v)
        targets=0
        texts=[(p,p.read_text(encoding='utf8')) for p in list(H.glob('*.md'))+list(O.glob('*.md'))]
        texts += [(p,p.read_text(encoding='utf8').split('\n## ',1)[0]) for p in control]
        for p,text in texts:
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
                if link.startswith(('https:','http:','codex:','#')):continue
                q=(p.parent/unquote(link.split('#',1)[0].strip('<>'))).resolve()
                if q!=(O/'FINAL_RECHECK.json').resolve():assert q.exists(),f'{p}: {link}'
                targets+=1
        subprocess.run(['git','diff','--check'],cwd=R,check=True)
        write('FINAL_RECHECK.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=head,
            proof_sha256=sha(O/'FINAL_PROOF.json'),sealed_files=len(proof['files']),source_and_prior_unique_files_verified=len(unique),
            scientific_receipts=dict(events),linked_targets=targets,control_docs=[pin(p) for p in control],git_diff_check='PASS',new_environment=0,new_fit=0))
    else:raise SystemExit('Explicit --seal or --verify required')
    print('FINAL_SAVED_CHECK_PASS',dict(events),len(unique),flush=True)
if __name__=='__main__':main()
