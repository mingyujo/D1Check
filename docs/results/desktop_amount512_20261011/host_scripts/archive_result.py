"""Preserve complete local state; excludes virtualenv and repository checkout."""
import hashlib
import json
from pathlib import Path
import zipfile

base=Path(__file__).resolve().parent
out=base.parent/'outputs'
archive=out/'full_state.zip'
assert not archive.exists(), 'never overwrite an existing state archive'
bundle=base/'bundle/D1Check-desktop-cpu-20261011'
assert json.loads((bundle/'output/desktop_joint_amount_amount512_desktop_20261011_a/completion.json').read_text())['status']=='completed'
entries=[]
def add(z,p,name):
    data=p.read_bytes()
    entries.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    z.writestr(name,data)
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
    for p in sorted(bundle.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            add(z,p,'bundle/'+p.relative_to(bundle).as_posix())
    for p in sorted((base/'logs').glob('*')):
        if p.is_file():add(z,p,'host_logs/'+p.name)
    for p in sorted(base.glob('*.py')):
        add(z,p,'host_scripts/'+p.name)
    for p in sorted(base.glob('*.json')):
        add(z,p,'host_receipts/'+p.name)
    add(z,base/'paused_session.pt','host_receipts/paused_session.pt')
    add(z,base/'D1Check-desktop-cpu-20261011.zip','original/D1Check-desktop-cpu-20261011.zip')
    z.writestr('archive_manifest.json',json.dumps(entries,ensure_ascii=False,indent=2).encode('utf-8'))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for e in entries:
        data=z.read(e['path'])
        assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256'],e['path']
receipt=dict(status='PASS_full_local_archive_CRC_and_all_entry_SHA',file='full_state.zip',bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),entry_count=len(entries),includes_original_bundle=True,includes_all_task_ledgers_raw_and_checkpoints=True,includes_real_paused_partial_session=True,venv_included=False,private_keys_included=False,not_for_Git=True)
(out/'archive_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
