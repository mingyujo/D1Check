"""Portable source/version, common-terminal, pilot and stop-contract audit."""
import csv,gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/results/rolling_terminal_01'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csv_read(p):
    with p.open(encoding='utf8') as f:return list(csv.DictReader(f))
def pair(r,b):
    service=r['completed']==r['planned']==b['completed']==b['planned'] and r['energy_full_work_eligible'] and b['energy_full_work_eligible'] and r['urgent_service_failure']<=b['urgent_service_failure'] and r['normal_service_failure']<=b['normal_service_failure'] and r['urgent_p95_ms']<=b['urgent_p95_ms']+1e-9
    good=service and r['energy_j']<=b['energy_j']+1e-9 and r['peak_ap_c']<=b['peak_ap_c']+1e-9
    return good,good and r['peak_ap_c']<b['peak_ap_c']-1e-9
def check():
    reg=read(B/'registration.json');repair=read(B/'repair.json');pilot=read(B/'pilot/registration.json');verification=read(B/'verification.json')
    for p,h in {**pilot['sources'],**verification['analysis_sources']}.items():assert sha(ROOT/p)==h,p
    for p,h in repair['preserved_original_sources'].items():assert sha(ROOT/p)==h,p
    assert reg['sources']['tools/d1_rolling_terminal_study.py']==sha(B/'source_v1/d1_rolling_terminal_study.py')
    assert reg['sources']['tools/test_d1_rolling_terminal.py']==sha(B/'source_v1/test_d1_rolling_terminal.py')
    for p,h in read(B/'artifact_manifest.json')['artifacts'].items():assert sha(ROOT/p)==h,p
    assert sha(B/'inputs.json')==reg['inputs_sha256']==pilot['input_sha256'] and sha(B/'probe_records.json.gz')==pilot['probe_sha256']
    assert sha(B/'completion.json')==pilot['probe_completion_sha256'];data=read(B/'inputs.json');probe=json.loads(gzip.decompress((B/'probe_records.json.gz').read_bytes()))
    assert len(probe)==24 and sum(r['completed'] for r in probe)==1584 and all(r['exact_replay'] and r['planned']==r['completed'] for r in probe)
    records=[r for i in probe for r in i['records']];assert len(records)==655 and sum(i['recovered_first_forecasts'] for i in probe)==655
    useful=0;first_pass=terminal_pass=cool=0
    for r in records:
        results=r['contexts'];assert r['unchanged_g']==0
        for c in results.values():
            if not c['valid']:continue
            assert c['common_end_s']==max(c['baseline_lane_end_s'],c['candidate_lane_end_s']) and c['common_end_s']<=120+1e-9
            assert c['delta_ap_c']==c['candidate']['ap_c']-c['baseline']['ap_c'] and c['delta_h_c_per_s']==c['candidate']['h_c_per_s']-c['baseline']['h_c_per_s']
            assert abs(c['delta_h_c_per_s'])<1e-15 and c['passed']==(c['delta_ap_c']<=1e-9 and c['delta_h_c_per_s']<=1e-9)
        terminal=all(c.get('valid',False) and c.get('passed',False) for c in results.values());assert terminal==r['terminal_pass']
        valid=all(r['first'][c]['valid'] and r['references'][c]['valid'] for c in results)
        da=max(r['first'][c]['peak_ap_c']-r['references'][c]['peak_ap_c'] for c in results) if valid else None
        dj=max(r['first'][c]['remaining_increment_j']-r['references'][c]['remaining_increment_j'] for c in results) if valid else None
        strict=valid and (da<-1e-9 or dj<-1e-9);assert strict==r['first_prefix_strict_gain'] and da==r['worst_first_AP_delta_c'] and dj==r['worst_first_J_delta']
        good=r['first_guard_pass'] and terminal and strict;assert good==r['useful'];useful+=good
        if r['first_guard_pass']:
            first_pass+=1;terminal_pass+=terminal
            if r['action_kind']=='cool_wait':cool+=1;assert not terminal
    assert useful==2 and first_pass==633 and terminal_pass==338 and cool==269
    es=csv_read(B/'probe_execution_receipts.csv');starts=[e for e in es if e['event']=='start'];ends=[e for e in es if e['event']=='completed'];failed=[e for e in es if e['event']=='failed']
    assert len(starts)==25 and len(ends)==24 and len(failed)==1 and len({r['identity'] for r in starts})==25
    assert {r['identity'] for r in starts}=={r['identity'] for r in ends+failed}
    assert repair['clock_reset'] is False and repair['original_registration_utc']==reg['registered_utc'] and read(B/'repair_verification.json')['status']=='PASS'
    assert set(repair['retry_identity_map'].values()).issubset({r['identity'] for r in ends}) and repair['failure_partial_completed_requests'] is None
    es=csv_read(B/'pilot_execution_receipts.csv');assert sum(r['event']=='start' for r in es)==sum(r['event']=='completed' for r in es)==26 and sum(r['event']=='reused' for r in es)==72 and not any(r['event']=='failed' for r in es)
    rows=read(B/'pilot/development_rows.json');assert len(rows)==96;by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};assert len(by)==96
    old={r['identity']:r for r in read(ROOT/'docs/results/rolling_prefix_01/development_rows.json')};p=pilot['policies'][-1];good=0;seeds=set()
    for case in data['development']:
        n=len(case['tickets']);assert n==(192 if case['family']=='sustained' else 24)
        for policy in pilot['policies']:
            r=by[case['seed'],case['family'],case['context'],policy];assert r['planned']==r['completed']==n and r['deadline_met']+r['urgent_service_failure']+r['normal_service_failure']==n
            assert r['ap_safety_limit_c'] is None and r['ap_safety_limit_exceed_s'] is None
            if policy!=p:assert r==old[r['identity']]
        r=by[case['seed'],case['family'],case['context'],p];base=by[case['seed'],case['family'],case['context'],pilot['policies'][0]]
        assert all(r[k]==base[k] for k in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms'))
        ps=[pair(r,by[case['seed'],case['family'],case['context'],q]) for q in pilot['policies'][:2]];good+=all(a for a,b in ps)
        if case['family'] in ('low','sustained') and all(b for a,b in ps):seeds.add(case['seed'])
    chosen=p if good==24 and seeds=={813010101,813010102} else None;assert read(B/'pilot/selection.json')['chosen']==chosen is None
    certificates=csv_read(B/'ledger_equality.csv');assert len(certificates)==24 and all(r['baseline_ledger_sha256']==r['candidate_ledger_sha256'] and r['excluded_field']=='source_request_id only' for r in certificates)
    term=json.loads(gzip.decompress((B/'pilot_terminal_records.json.gz').read_bytes()));assert len(term)==540 and sum(not r['passed'] for r in term)==377
    for r in term:assert r['passed']==all(c.get('valid',False) and c.get('passed',False) for c in r['contexts'].values())
    summary=read(B/'summary.json');assert summary['combined_new_starts']==51 and summary['combined_failed_starts']==1 and summary['validated_completed_requests']==3176
    assert summary['all_attempt_planned_requests']==3368 and summary['failed_partial_completed_requests'] is None
    assert summary['consumption']['cumulative_environment_starts']==6517 and summary['consumption']['cumulative_learning_starts']==641
    assert summary['independent_final_started']==summary['new_learning_starts']==summary['device_commands']==0 and not summary['adopted'] and not summary['experiment_ready']
    assert read(B/'browser_verification.json')['status']=='PASS'
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=len(pilot['sources']),exact_development_replays=24,first_forecast_recoveries=655,
        candidate_Band_ledger_equal_conditions=24,selection_recomputed=True,stop_contract_verified=True,cumulative_environment_starts=6517,new_environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result
if __name__=='__main__':check()
