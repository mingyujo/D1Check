from pathlib import Path
import datetime,hashlib,json,re,shutil
W=Path(__file__).resolve().parents[1];R=W/'S26-D1Check';S=R/'s26_simulator';H=S/'experiments/final_three_policy_v1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
for n in ['MANIFEST.json','FINAL_PROOF.json']:shutil.copyfile(H/n,H/'history'/('BEFORE_FINAL_SEAL__'+n))
shutil.copyfile(S/'CORE_MANIFEST.json',H/'history/CORE_MANIFEST_BEFORE_FINAL_SEAL.json')
for rel in ['s26_simulator/START_HERE.md','s26_simulator/STATUS.md','s26_simulator/HANDOFF.md','s26_simulator/docs/NEXT_STEPS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']:
 p=R/rel;shutil.copyfile(p,H/'history'/('BEFORE_ADMIN_REORDER__'+rel.replace('/','__')))
 text=p.read_text(encoding='utf-8-sig');match=re.search(r'<!-- S26_FINAL_THREE_CURRENT_BEGIN -->.*?<!-- S26_FINAL_THREE_CURRENT_END -->\s*',text,re.S);assert match
 new=match.group().strip()+'\n\n';text=text[:match.start()]+text[match.end():];adopt=re.match(r'<!-- S26_FINAL_POLICY_ADOPTED_BEGIN -->.*?<!-- S26_FINAL_POLICY_ADOPTED_END -->\s*',text,re.S);assert adopt
 text=text[:adopt.end()]+new+text[adopt.end():];p.write_text(text,encoding='utf-8',newline='\n')
report=S/'S26_FINAL_THREE_POLICY_RESULTS_KO.md';report.write_text(report.read_text(encoding='utf-8-sig'),encoding='utf-8',newline='\n')
note={'utc':utc,'kind':'administrative verification repair','cause':'Existing policy verifier requires adopted-policy marker at first byte. New comparison marker was prepended; Python Windows default also expanded line endings.','repair':'Keep original adoption first, put new comparison immediately after it, normalize only touched documents to LF. Preserve all previous versions and verification contract unchanged.','scientific_data_changed':False,'new_environment':0,'manifest_inventory_repair':'Include core-before-extension backup created after initial inventory.'}
(H/'ADMIN_SEAL_REPAIR.json').write_text(json.dumps(note,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
shutil.copyfile(Path(__file__),H/'workspace_recovery'/Path(__file__).name)
files=[dict(path=p.relative_to(H).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and p.name not in ['MANIFEST.json','FINAL_PROOF.json']]
# Exclude just the two current output files; historical copies remain included.
files=[dict(path=p.relative_to(H).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and p not in [H/'MANIFEST.json',H/'FINAL_PROOF.json']]
(H/'MANIFEST.json').write_text(json.dumps(dict(schema='S26_FINAL_THREE_MANIFEST_V1',utc=utc,files=files,new_FIFO=4,REUSE=12,physical_validation=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
core=S/'CORE_MANIFEST.json';m=read(core)
for entry in m['files']:
 if entry['path'] in ['START_HERE.md','STATUS.md','HANDOFF.md','docs/NEXT_STEPS.md']:
  p=S/entry['path'];entry.update(bytes=p.stat().st_size,sha256=sha(p))
for entry in m.get('local_document_changes',[]):
 p=S/entry['path']
 if p.exists():entry['local_sha256']=sha(p)
m['final_three_policy_extension']['sha256']=sha(H/'MANIFEST.json');core.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
proof=read(H/'FINAL_PROOF.json');proof.update(utc=utc,manifest_sha256=sha(H/'MANIFEST.json'),core_manifest_sha256=sha(core),report_sha256=sha(report),all_inventory_files_covered_except_manifest_and_final_proof=True,admin_contract_repair=True)
(H/'FINAL_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for item in files:assert sha(H/item['path'])==item['sha256']
expected={item['path'] for item in files};actual={p.relative_to(H).as_posix() for p in H.rglob('*') if p.is_file() and p not in [H/'MANIFEST.json',H/'FINAL_PROOF.json']};assert expected==actual
print(json.dumps(dict(status='PASS_COMPLETE_INVENTORY_AND_ORIGINAL_POLICY_ADMIN_CONTRACT',files=len(files),manifest_sha256=sha(H/'MANIFEST.json'))))
