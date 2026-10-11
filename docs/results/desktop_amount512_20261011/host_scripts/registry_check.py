import hashlib
import json
from pathlib import Path

base = Path(__file__).resolve().parent
bundle = base / 'bundle/D1Check-desktop-cpu-20261011'
registry = json.loads((bundle/'arrival_seed_registry.json').read_text())
seeds = set(range(860010001, 860010113)) | {860020101,860020102,860020103,860020104}
assert not seeds.intersection(registry['seeds'])
assert not any(lo <= s <= hi for s in seeds for lo,hi in registry['ranges'])
names = {'registration.json','contract.json','execution_contract.json','inputs.json','cases.json'}
paths = [p for p in (base/'repo/docs/results').rglob('*.json') if p.name in names]
paths += list((bundle/'output').rglob('registration.json'))
conflicts = [p.relative_to(base).as_posix() for p in paths if any(str(s) in p.read_text(encoding='utf-8') for s in seeds)]
assert not conflicts, conflicts
available, missing, byte_match, line_endings_or_export_revision = [], [], [], []
for e in registry['source_receipts']:
    p = base/'repo'/e['logical_path']
    if not p.exists():
        missing.append(e['logical_path'])
        continue
    available.append(e['logical_path'])
    if hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256']:
        byte_match.append(e['logical_path'])
    else:
        line_endings_or_export_revision.append(e['logical_path'])
receipt = dict(status='PASS_no_registered_seed_conflict', public_history_files_checked=len(paths), conflicts=conflicts,
    frozen_registry_sha256=hashlib.sha256((bundle/'arrival_seed_registry.json').read_bytes()).hexdigest(),
    reserved_individual_seeds=len(registry['seeds']), reserved_ranges=registry['ranges'],
    source_receipts_available=available, source_receipts_byte_matches=byte_match,
    source_receipts_not_publicly_available=missing, source_receipts_other_bytes=line_endings_or_export_revision,
    repository_head='8175aac95c82fa70860e07e2e7566797b92b7736',
    new_training_seed_range=[860010001,860010112], new_confirmation_seeds=[860020101,860020102,860020103,860020104],
    not_cross_computer_live_registry=True, private_original_history_preserved_in_frozen_registry=True)
(base/'registry_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if not k.startswith('source_receipts')},indent=2))
