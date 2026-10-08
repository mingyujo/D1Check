"""Portable stdlib audit of frozen selection and full-work thermal comparisons."""
import argparse,csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def paired(row,ref):
    complete=row['completed']==row['planned'] and ref['completed']==ref['planned'] and row['energy_full_work_eligible'] and ref['energy_full_work_eligible']
    finite=all(row[k] is not None and ref[k] is not None for k in ('energy_j','peak_ap_c','urgent_p95_ms'))
    service=complete and finite and row['urgent_service_failure']<=ref['urgent_service_failure'] and row['normal_service_failure']<=ref['normal_service_failure'] and row['urgent_p95_ms']<=ref['urgent_p95_ms']+1e-9
    nonworse=bool(service and row['energy_j']<=ref['energy_j']+1e-9 and row['peak_ap_c']<=ref['peak_ap_c']+1e-9)
    return nonworse,bool(nonworse and row['peak_ap_c']<ref['peak_ap_c']-1e-9)

def check(name):
    assert name in ('thermal_slack_v3','thermal_load_gate_01');bundle=ROOT/'docs/results'/name
    reg=read(bundle/'registration.json');done=read(bundle/'completion.json');summary=read(bundle/'summary.json');inputs=read(bundle/'inputs.json');selection=read(bundle/'selection.json')
    for path,h in reg['sources'].items():assert sha(ROOT/path)==h,path
    for path,h in read(bundle/'verification.json')['analysis_sources'].items():assert sha(ROOT/path)==h,path
    assert sha(bundle/'inputs.json')==reg['inputs_sha256'] and done['status']==summary['status']=='completed'
    assert done['consumption']==summary['consumption']
    dev=read(bundle/'development_rows.json');final=read(bundle/'final_rows.json');policies=reg['policies'];count=len(policies)
    assert len(dev)==len(final)==24*count
    assert len(inputs['cases']['development'])==len(inputs['cases']['final'])==24
    assert {c['seed'] for c in inputs['cases']['development']}.isdisjoint({c['seed'] for c in inputs['cases']['final']})
    for split,rows in (('development',dev),('final',final)):
        by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};assert len(by)==len(rows)
        for case in inputs['cases'][split]:
            expected=192 if case['family']=='sustained' else 24;assert len(case['tickets'])==expected
            assert len({q['id'] for q in case['tickets']})==expected
            assert all(q['task'] in ('classification','detection') and q['deadline_offset_ns']==(1500000000 if q['priority']=='urgent' else 6000000000) for q in case['tickets'])
            for policy in policies:
                row=by[case['seed'],case['family'],case['context'],policy];assert row['planned']==expected and row['completed']<=row['planned']
                assert row['urgent_n']+row['normal_n']==row['planned'] and row['deadline_met']+row['urgent_service_failure']+row['normal_service_failure']==row['planned']
                assert row['ap_safety_limit_c'] is None and row['ap_safety_limit_exceed_s'] is None
    refs=policies[:2];by={(r['seed'],r['family'],r['context'],r['policy']):r for r in dev};candidates=[p for p in policies if p.endswith(('_025_V3','_100_V3','_025_V3_1'))];eligible=[]
    for policy in candidates:
        comparisons=[];heat_seeds=set()
        for row in (r for r in dev if r['policy']==policy):
            ps=[paired(row,by[row['seed'],row['family'],row['context'],p]) for p in refs];comparisons.append(ps)
            if row['family'] in ('low','sustained') and all(h for n,h in ps):heat_seeds.add(row['seed'])
        good=all(all(n for n,h in ps) for ps in comparisons) and heat_seeds=={c['seed'] for c in inputs['cases']['development']}
        if good:
            group=[r for r in dev if r['policy']==policy]
            worst=max(row['peak_ap_c']-by[row['seed'],row['family'],row['context'],p]['peak_ap_c'] for row in group for p in refs)
            credit=1. if policy.endswith('_100_V3') else .25
            eligible.append(((worst,sum(r['energy_j'] for r in group)/24,credit),policy))
    assert selection['chosen']==(min(eligible)[1] if eligible else None)
    with (bundle/'execution_receipts.csv').open(encoding='utf8') as f:events=list(csv.DictReader(f))
    starts=[r for r in events if r['event']=='start'];completed=[r for r in events if r['event']=='completed'];failed=[r for r in events if r['event']=='failed']
    assert len(starts)==len(completed)+len(failed)==done['consumption']['new_environment_starts']
    assert len({r['identity'] for r in starts})==len(starts) and {r['identity'] for r in starts}=={r['identity'] for r in completed+failed}
    assert len(starts)<=reg['environment_cap'] and selection['utc']<min(r['utc'] for r in starts if r['identity'].startswith('final/'))
    assert summary['final_planned']==summary['final_completed']==1584*count
    if name=='thermal_load_gate_01':
        parent=read(ROOT/'docs/results/thermal_slack_v3/development_rows.json');pby={r['identity']:r for r in parent}
        reused=[r for r in events if r['event']=='reused'];assert len(reused)==120
        for row in dev:
            if row['policy']!=policies[-1]:assert row==pby[row['identity']]
    assert done['consumption']['new_learning_starts']==done['consumption']['device_commands']==0
    assert done['consumption']['cumulative_learning_starts']==641 and summary['no_policy_default_change'] and not summary['experiment_ready']
    for path,h in read(bundle/'artifact_manifest.json')['artifacts'].items():assert sha(ROOT/path)==h,path
    browser=read(bundle/'browser_verification.json');assert browser['status']=='PASS' and browser['images_loaded']==5
    result=dict(status='PASS',bundle=name,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=len(reg['sources']),policies=count,conditions=24,final_rows=24*count,
        complete_final_requests=1584*count,source_selection_independently_recomputed=True,charged_environment_starts=len(starts),new_environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',choices=['thermal_slack_v3','thermal_load_gate_01']);check(parser.parse_args().bundle)
