"""Shared read-only source/input/model check, no native runner imports."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];PUBLIC=ROOT/'docs/results/rolling_list_rl_pilot_08'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def validate_source(raw,entry):
    if sha(raw.replace(b'\r\n',b'\n'))!=entry['canonical_lf_sha256']:raise ValueError('source content changed')
def check():
    reg=json.loads((PUBLIC/'execution_contract.json').read_text(encoding='utf-8'));record=json.loads((PUBLIC/'source_identity.json').read_text(encoding='utf-8'))
    if sha((PUBLIC/'execution_contract.json').read_bytes())!=record['contract_sha256']:raise ValueError('contract changed')
    if set(record['sources'])!=set(reg['source_sha256']):raise ValueError('closure changed')
    for name,entry in record['sources'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or entry['executed_file_sha256']!=reg['source_sha256'][name]:raise ValueError('source provenance')
        validate_source(path.read_bytes(),entry)
    parent=ROOT/'docs/results/rolling_hybrid_pilot_07'
    if sha((parent/'model.json').read_bytes())!=reg['exported_model_sha256']:raise ValueError('model changed')
    inputs=json.loads((PUBLIC/'cases.json').read_text(encoding='utf-8'))
    inputs['initial']=json.loads((parent/'thermal_equivalence_fixture.json').read_text(encoding='utf-8'))['initial']
    if sha(json.dumps(inputs,sort_keys=True,separators=(',',':'),allow_nan=False).encode())!=reg['inputs_sha256']:raise ValueError('inputs changed')
    return dict(status='PASS',scope='shared read-only; no execution/learning authorization',source_files=len(record['sources']),train_cases=len(inputs['train']),development_cases=len(inputs['development']),native_starts=0,learning_starts=0,device_commands=0)
if __name__=='__main__':print(json.dumps(check(),indent=2))
