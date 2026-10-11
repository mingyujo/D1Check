"""Shared read-only normalized source/archive metadata verification."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PUBLIC=ROOT/'docs/results/service_joint_rl_20261011'
def run():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));identity=read(PUBLIC/'source_identity.json')
    if hashlib.sha256((PUBLIC/'execution_contract.json').read_bytes()).hexdigest()!=identity['original_contract_sha256']:raise ValueError('original contract changed')
    if hashlib.sha256((PUBLIC/'label_only_revision.json').read_bytes()).hexdigest()!=identity['revision_sha256']:raise ValueError('display/runner amendment changed')
    for name,entry in identity['sources'].items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=entry['canonical_lf_sha256']:raise ValueError('source content differs '+name)
    v=read(PUBLIC/'checkpoint_roundtrip.json');assert len(v['archives'])==6 and all(all(q['all_fields_exact'].values()) for q in v['archives'])
    return dict(status='PASS_shared_source_and6archive_metadata',sources=len(identity['sources']),environment_starts=0,learning_starts=0,device_commands=0)
if __name__=='__main__':print(json.dumps(run(),indent=2))
