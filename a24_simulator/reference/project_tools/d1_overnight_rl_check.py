"""Portable shared read-only verification; never imports the native runner."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PUBLIC=ROOT/'docs/results/overnight_rl_20261011'
def sha(data):return hashlib.sha256(data).hexdigest()
def check():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    reg=read(PUBLIC/'execution_contract.json');record=read(PUBLIC/'source_identity.json')
    if sha((PUBLIC/'execution_contract.json').read_bytes())!=record['contract_sha256']:raise ValueError('shared contract changed')
    if set(record['sources'])!=set(reg['source_sha256']):raise ValueError('source closure mismatch')
    amendment=read(PUBLIC/'host_save_amendment.json') if record.get('host_save_amendment_sha256') else None
    if amendment and sha((PUBLIC/'host_save_amendment.json').read_bytes())!=record['host_save_amendment_sha256']:raise ValueError('host-only source amendment changed')
    storage=read(PUBLIC/'storage_hold_amendment.json') if record.get('storage_hold_amendment_sha256') else None
    if storage and (sha((PUBLIC/'storage_hold_amendment.json').read_bytes())!=record['storage_hold_amendment_sha256'] or storage['prior_host_amendment_sha256']!=record['host_save_amendment_sha256']):raise ValueError('storage lineage changed')
    for name,entry in record['sources'].items():
        path=(ROOT/name).resolve()
        expected=amendment['repaired_driver_sha256'] if amendment and name=='tools/d1_overnight_rl_amount.py' else reg['source_sha256'][name]
        if storage and name=='tools/d1_overnight_rl_amount.py':expected=storage['repaired_driver_sha256']
        if not path.is_relative_to(ROOT) or reg['source_sha256'][name]!=entry['original_registered_file_sha256'] or expected!=entry['executed_file_sha256']:raise ValueError('source provenance mismatch')
        if sha(path.read_bytes().replace(b'\r\n',b'\n'))!=entry['canonical_lf_sha256']:raise ValueError('source content changed '+name)
    if amendment and sha((PUBLIC/'source_versions/d1_overnight_rl_amount_v1.py').read_bytes())!=amendment['old_driver_sha256']:raise ValueError('original executed driver bytes changed')
    if storage and sha((PUBLIC/'source_versions/d1_overnight_rl_amount_v2_host_save.py').read_bytes())!=storage['previous_driver_sha256']:raise ValueError('host-save stage bytes changed')
    if sha((ROOT/'docs/results/rolling_hybrid_pilot_07/model.json').read_bytes())!=reg['exported_model_sha256']:raise ValueError('model changed')
    arithmetic=reg['arithmetic']
    if arithmetic['normal']!=sum(arithmetic[k] for k in ('reference','train','development','confirmation','no_wait')) or arithmetic['conditional_total']>reg['native_cap'] or arithmetic['learning']!=reg['learning_cap']:raise ValueError('budget arithmetic')
    verified=read(PUBLIC/'verification.json')
    plan=read(PUBLIC/'input_plan.json')
    if plan['inputs_sha256']!=reg['inputs_sha256'] or plan['training_seeds']!=list(range(*[reg['training_seed_range'][0],reg['training_seed_range'][1]+1])) or plan['confirmation_seeds']!=reg['confirmation_seeds']:raise ValueError('declared input generation changed')
    if verified['all_new_scheduled_requests']!=verified['all_new_completed_requests'] or verified['new_learning']!=1440:raise ValueError('completion consumption')
    return dict(status='PASS',scope='shared read-only source/model/contracts, no run authorization or local checkpoints required',
        checked_source_files=len(record['sources']),new_native=verified['new_native'],new_learning=verified['new_learning'],new_native_starts=0,new_training_starts=0,device_commands=0)
if __name__=='__main__':print(json.dumps(check(),indent=2))
