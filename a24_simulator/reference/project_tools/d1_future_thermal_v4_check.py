"""Portable verification of exact-speed pairs and isolated virtual forecasts."""
import csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUNDLE=ROOT/'docs/results/future_thermal_v4'
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def paired(r,b):
    full=r['completed']==r['planned'] and b['completed']==b['planned'] and r['energy_full_work_eligible'] and b['energy_full_work_eligible']
    service=full and r['urgent_service_failure']<=b['urgent_service_failure'] and r['normal_service_failure']<=b['normal_service_failure'] and r['urgent_p95_ms']<=b['urgent_p95_ms']+1e-9
    nonworse=service and r['energy_j']<=b['energy_j']+1e-9 and r['peak_ap_c']<=b['peak_ap_c']+1e-9
    return nonworse,nonworse and r['peak_ap_c']<b['peak_ap_c']-1e-9
def check():
    reg=read(BUNDLE/'registration.json');summary=read(BUNDLE/'summary.json');done=read(BUNDLE/'completion.json');data=read(BUNDLE/'inputs.json');selection=read(BUNDLE/'selection.json')
    for path,h in reg['sources'].items():assert sha(ROOT/path)==h,path
    for path,h in read(BUNDLE/'verification.json')['analysis_sources'].items():assert sha(ROOT/path)==h,path
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'] and done['status']==summary['status']=='completed' and done['consumption']==summary['consumption']
    dev=read(BUNDLE/'development_rows.json');final=read(BUNDLE/'final_rows.json');assert len(dev)==144 and len(final)==168
    assert {c['seed'] for c in data['cases']['development']}.isdisjoint({c['seed'] for c in data['cases']['final']})
    for split,rows,policies in (('development',dev,reg['development_policies']),('final',final,reg['final_policies'])):
        by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};assert len(by)==len(rows)
        for case in data['cases'][split]:
            n=192 if case['family']=='sustained' else 24;assert len(case['tickets'])==n and len({q['id'] for q in case['tickets']})==n
            assert not any(q['id'].startswith('__forecast_v4__') for q in case['tickets'])
            for policy in policies:
                r=by[case['seed'],case['family'],case['context'],policy];assert r['planned']==r['completed']==n
                assert r['deadline_met']+r['urgent_service_failure']+r['normal_service_failure']==n and r['urgent_n']+r['normal_n']==n
                assert r['ap_safety_limit_c'] is None and r['ap_safety_limit_exceed_s'] is None
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in dev};eligible=[]
    for policy in reg['final_policies'][-2:]:
        rows=[r for r in dev if r['policy']==policy];all_ok=True;gains=set()
        for r in rows:
            ps=[paired(r,by[r['seed'],r['family'],r['context'],ref]) for ref in reg['final_policies'][:2]];all_ok&=all(n for n,h in ps)
            if r['family'] in ('low','sustained') and all(h for n,h in ps):gains.add(r['seed'])
        if all_ok and gains=={813010101,813010102}:
            worst=max(r['peak_ap_c']-by[r['seed'],r['family'],r['context'],ref]['peak_ap_c'] for r in rows for ref in reg['final_policies'][:2]);key=(worst,sum(r['energy_j'] for r in rows)/24,policy!=reg['final_policies'][-2]);eligible.append((key,policy))
    assert selection['chosen']==(min(eligible)[1] if eligible else None)
    with (BUNDLE/'execution_receipts.csv').open(encoding='utf8') as f:events=list(csv.DictReader(f))
    starts=[r for r in events if r['event']=='start'];completed=[r for r in events if r['event']=='completed'];assert len(starts)==len(completed)==225
    assert {r['identity'] for r in starts}=={r['identity'] for r in completed} and len({r['identity'] for r in starts})==225
    assert len([r for r in events if r['event']=='reused'])==96 and selection['utc']<min(r['utc'] for r in starts if r['identity'].startswith('final/'))
    parent=read(ROOT/'docs/results/thermal_load_gate_01/development_rows.json');pby={r['identity']:r for r in parent}
    for r in dev:
        if r['policy'] not in reg['final_policies'][-2:]:assert r==pby[r['identity']]
    assert summary['final_planned']==summary['final_completed']==11088 and summary['total_planned']==summary['total_completed']==14790
    assert summary['old_fast_fresh_equal']==24 and len(read(BUNDLE/'preservation.json'))==8 and all(r['ledger_equal'] for r in read(BUNDLE/'preservation.json'))
    fixture=read(BUNDLE/'fixture_verification.json');assert fixture['no_virtual_admission'] and fixture['virtual_scenario_batches']>0
    assert done['consumption']['cumulative_environment_starts']==6029 and done['consumption']['new_learning_starts']==0 and done['consumption']['device_commands']==0
    for path,h in read(BUNDLE/'artifact_manifest.json')['artifacts'].items():assert sha(ROOT/path)==h,path
    assert read(BUNDLE/'browser_verification.json')['status']=='PASS'
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=len(reg['sources']),final_rows=168,complete_final_requests=11088,source_selection_recomputed=True,
        exact_native_parity_cases=32,known_virtual_work_isolated=True,new_environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result
if __name__=='__main__':check()
