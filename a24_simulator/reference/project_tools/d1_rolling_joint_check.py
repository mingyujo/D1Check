"""Portable audit of shared rolling-horizon inputs, selection and full work."""
import csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUNDLE=ROOT/'docs/results/rolling_joint_01'
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pair(r,b):
    full=r['completed']==r['planned'] and b['completed']==b['planned'] and r['energy_full_work_eligible'] and b['energy_full_work_eligible']
    service=full and r['urgent_service_failure']<=b['urgent_service_failure'] and r['normal_service_failure']<=b['normal_service_failure'] and r['urgent_p95_ms']<=b['urgent_p95_ms']+1e-9
    good=service and r['energy_j']<=b['energy_j']+1e-9 and r['peak_ap_c']<=b['peak_ap_c']+1e-9
    return good,good and r['peak_ap_c']<b['peak_ap_c']-1e-9
def check():
    reg=read(BUNDLE/'registration.json');data=read(BUNDLE/'inputs.json');done=read(BUNDLE/'completion.json');summary=read(BUNDLE/'summary.json');selection=read(BUNDLE/'selection.json')
    for path,h in reg['sources'].items():assert sha(ROOT/path)==h,path
    for path,h in read(BUNDLE/'verification.json')['analysis_sources'].items():assert sha(ROOT/path)==h,path
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'] and done['status']==summary['status']=='completed' and done['consumption']==summary['consumption']
    dev=read(BUNDLE/'development_rows.json');final=read(BUNDLE/'final_rows.json');assert len(dev)==len(final)==168
    assert {c['seed'] for c in data['cases']['development']}.isdisjoint({c['seed'] for c in data['cases']['final']})
    for split,rows in (('development',dev),('final',final)):
        by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};assert len(by)==168
        for case in data['cases'][split]:
            n=192 if case['family']=='sustained' else 24;assert len(case['tickets'])==n and len({q['id'] for q in case['tickets']})==n
            for policy in reg['policies']:
                r=by[case['seed'],case['family'],case['context'],policy];assert r['planned']==r['completed']==n
                assert r['deadline_met']+r['urgent_service_failure']+r['normal_service_failure']==n and r['urgent_n']+r['normal_n']==n
                assert r['ap_safety_limit_c'] is None and r['ap_safety_limit_exceed_s'] is None
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in dev};eligible=[]
    for policy in reg['policies'][-2:]:
        group=[r for r in dev if r['policy']==policy];good=True;seeds=set()
        for r in group:
            pairs=[pair(r,by[r['seed'],r['family'],r['context'],p]) for p in reg['policies'][:2]];good&=all(n for n,h in pairs)
            if r['family'] in ('low','sustained') and all(h for n,h in pairs):seeds.add(r['seed'])
        if good and seeds=={813010101,813010102}:
            worst=max(r['peak_ap_c']-by[r['seed'],r['family'],r['context'],p]['peak_ap_c'] for r in group for p in reg['policies'][:2]);eligible.append(((worst,sum(r['energy_j'] for r in group)/24,policy!=reg['policies'][-2]),policy))
    assert selection['chosen']==(min(eligible)[1] if eligible else None)
    with (BUNDLE/'execution_receipts.csv').open(encoding='utf8') as f:events=list(csv.DictReader(f))
    starts=[r for r in events if r['event']=='start'];completed=[r for r in events if r['event']=='completed'];assert len(starts)==len(completed)==267
    assert {r['identity'] for r in starts}=={r['identity'] for r in completed} and len({r['identity'] for r in starts})==267
    assert len([r for r in events if r['event']=='reused'])==72 and selection['utc']<min(r['utc'] for r in starts if r['identity'].startswith('final/'))
    parent={r['identity']:r for r in read(ROOT/'docs/results/future_thermal_v4/development_rows.json')}
    for r in dev:
        if r['policy'] in reg['policies'][:3]:assert r==parent[r['identity']]
    assert summary['final_planned']==summary['final_completed']==11088 and done['consumption']['cumulative_environment_starts']==6296
    assert done['consumption']['new_learning_starts']==done['consumption']['device_commands']==0
    for record in read(BUNDLE/'selected_forecast_plans.json'):
        assert 0<len(record['window_ids'])<=4 and record['candidate_count']<=72 and record['full_plan_count']<=8
        plan=record['selected_plan'];assert len(plan)==len(record['window_ids']) and {j['request_id'] for j in plan}==set(record['window_ids'])
        assert sum(bool(j['delay_ns']) for j in plan)<=1 and all(0<=j['delay_ns']<=250000000. for j in plan)
    for path,h in read(BUNDLE/'artifact_manifest.json')['artifacts'].items():assert sha(ROOT/path)==h,path
    assert read(BUNDLE/'browser_verification.json')['status']=='PASS'
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hashes=len(reg['sources']),selection_recomputed=True,final_rows=168,complete_final_requests=11088,
        bounded_joint_plan_scope_verified=True,new_environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result
if __name__=='__main__':check()
