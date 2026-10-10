"""Read-only shared-artifact check; recognizes recorded Git LF/Windows CRLF.

Does not import experiment code or create budget/activation/owner artifacts.
The actual execution contract retains its original strict byte hashes.
"""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/results/rolling_hybrid_pilot_07'


def digest(value):return hashlib.sha256(value).hexdigest()


def validate_source(raw,entry):
    if digest(raw.replace(b'\r\n',b'\n'))!=entry['canonical_lf_sha256']:
        raise ValueError('source content changed beyond recorded LF/CRLF conversion')


def check():
    reg=json.loads((PUBLIC/'execution_contract.json').read_text(encoding='utf-8'))
    index=json.loads((PUBLIC/'source_index_equivalence.json').read_text(encoding='utf-8'))
    if digest((PUBLIC/'execution_contract.json').read_bytes())!=index['execution_contract_sha256']:
        raise ValueError('execution contract changed')
    if set(index['sources'])!=set(reg['source_sha256']):raise ValueError('source closure changed')
    for name,entry in index['sources'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or entry['executed_file_sha256']!=reg['source_sha256'][name]:raise ValueError('source provenance')
        validate_source(path.read_bytes(),entry)
    if digest((PUBLIC/'model.json').read_bytes())!=reg['exported_hybrid_sha256']:raise ValueError('model changed')
    cases=json.loads((PUBLIC/'cases.json').read_text(encoding='utf-8'))['cases']
    if len(cases)!=24 or digest(json.dumps(cases,sort_keys=True,separators=(',',':')).encode())!=reg['inputs_sha256']:raise ValueError('cases changed')
    return dict(status='PASS',conditions=24,source_files=len(index['sources']),scope='shared read-only, no native authorization',native_starts=0,device_commands=0,accepted_conversion='only recorded LF/CRLF, all other content exact')

if __name__=='__main__':print(json.dumps(check(),indent=2))
