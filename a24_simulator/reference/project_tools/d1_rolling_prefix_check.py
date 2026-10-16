"""Portable independent audit of shared inputs, selection, guards and budgets."""
import csv,gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/results/rolling_prefix_01';D=ROOT/'docs/results/rolling_diagnosis_01'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def full(r):return r['planned']==r['completed'] and r['energy_full_work_eligible']
def pair(r,b):
    service=full(r) and full(b) and r['urgent_service_failure']<=b['urgent_service_failure'] and r['normal_service_failure']<=b['normal_service_failure'] and r['urgent_p95_ms']<=b['urgent_p95_ms']+1e-9
    good=service and r['energy_j']<=b['energy_j']+1e-9 and r['peak_ap_c']<=b['peak_ap_c']+1e-9
    return good,good and r['peak_ap_c']<b['peak_ap_c']-1e-9,good and r['peak_ap_c']<b['peak_ap_c']-1e-9 and r['energy_j']<b['energy_j']-1e-9
def guard(f,r):
    return f['valid'] and r['valid'] and f['lane_end_s']<=120+1e-9 and all(f[k]<=r[k]+1e-9 for k in ('urgent_misses','normal_misses','remaining_increment_j','global_peak_ap_c')) and (f['urgent_p95_ms'] is None or r['urgent_p95_ms'] is None or f['urgent_p95_ms']<=r['urgent_p95_ms']+1e-9)
def receipts(folder,n,reused):
    with (folder/'execution_receipts.csv').open(encoding='utf8') as f:events=list(csv.DictReader(f))
    starts=[r for r in events if r['event']=='start'];ends=[r for r in events if r['event']=='completed']
    assert len(starts)==len(ends)==n and {r['identity'] for r in starts}=={r['identity'] for r in ends} and len({r['identity'] for r in starts})==n
    assert len([r for r in events if r['event']=='reused'])==reused and not any(r['event']=='failed' for r in events)
    return events
def check():
    reg=read(B/'registration.json');dreg=read(D/'registration.json');v=read(B/'verification.json')
    for path,h in {**reg['sources'],**v['analysis_sources']}.items():assert sha(ROOT/path)==h,path
    for folder in (B,D):
        for path,h in read(folder/'artifact_manifest.json')['artifacts'].items():assert sha(ROOT/path)==h,path
    assert sha(B/'inputs.json')==reg['inputs_sha256'];diagnosis=json.loads(gzip.decompress((D/'diagnosis_details.json.gz').read_bytes()))
    canonical=(json.dumps(diagnosis,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    assert hashlib.sha256(canonical).hexdigest()==reg['diagnosis_sha256']
    assert len(diagnosis)==24 and all(r['exact_replay'] and r['selected_metric_recoveries']==len(r['prefixes']) for r in diagnosis)
    for item in diagnosis:
        for r in item['prefixes']:
            assert r['full_guard_pass']
            assert r['actual_prefix_guard_pass']==all(guard(r['first'][c],r['references'][c]) for c in ('mean','short_context','long_context'))
        for r in item['shortlist_snapshots']:
            assert 8<r['candidate_count']<=72 and len(r['evaluated'])==r['valid_mean_count'] and r['shortlist_count']<=8
            eligible=[p for p in r['evaluated'] if p['score'] is not None];chosen=[p for p in eligible if p['in_shortlist']]
            best=min(eligible,key=lambda p:p['score']) if eligible else None;short=min(chosen,key=lambda p:p['score']) if chosen else None
            assert best==r['full_finite_best'] and short==r['shortlist_best']
            assert r['omitted_improving_plan']==bool(best and (short is None or tuple(best['score'][:3])<tuple(short['score'][:3])))
    receipts(D,24,0);es=receipts(B,146,96);data=read(B/'inputs.json');dev=read(B/'development_rows.json');final=read(B/'final_rows.json')
    assert len(dev)==len(final)==120 and {c['seed'] for c in data['cases']['development']}.isdisjoint({c['seed'] for c in data['cases']['final']})
    old={r['identity']:r for r in read(ROOT/'docs/results/rolling_joint_01/development_rows.json')}
    for r in dev:
        if r['policy']!=reg['policies'][-1]:assert r==old[r['identity']]
    for split,rows in (('development',dev),('final',final)):
        by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};assert len(by)==120
        for c in data['cases'][split]:
            n=192 if c['family']=='sustained' else 24;assert len(c['tickets'])==n and len({q['id'] for q in c['tickets']})==n
            for p in reg['policies']:
                r=by[c['seed'],c['family'],c['context'],p];assert r['completed']==r['planned']==n and r['urgent_n']+r['normal_n']==n
                assert r['deadline_met']+r['urgent_service_failure']+r['normal_service_failure']==n and r['ap_safety_limit_c'] is None and r['ap_safety_limit_exceed_s'] is None
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in dev};good=0;seeds=set();candidate=reg['policies'][-1]
    for r in dev:
        if r['policy']!=candidate:continue
        pairs=[pair(r,by[r['seed'],r['family'],r['context'],p]) for p in reg['policies'][:2]];good+=all(p[0] for p in pairs)
        if r['family'] in ('low','sustained') and all(p[1] for p in pairs):seeds.add(r['seed'])
    chosen=candidate if good==24 and seeds=={813010101,813010102} else None;selection=read(B/'selection.json');assert selection['chosen']==chosen
    assert selection['utc']<min(e['utc'] for e in es if e['event']=='start' and e['identity'].startswith('final/'))
    guards=json.loads(gzip.decompress((B/'prefix_guard_events.json.gz').read_bytes()));byguards={}
    for g in guards:
        passed=all(guard(g['first'][c],g['references'][c]) for c in ('mean','short_context','long_context'));assert passed==g['passed']
        n,b=byguards.get(g['identity'],(0,0));byguards[g['identity']]=(n+1,b+int(not passed))
    for r in dev+final:
        if r['policy']==candidate:assert byguards.get(r['identity'],(0,0))==(r['prefix_checks'],r['prefix_blocked_calls'])
    summary=read(B/'summary.json');assert summary['final_planned']==summary['final_completed']==7920 and summary['combined_new_environment_starts']==170 and summary['combined_new_requests']==14120
    assert read(B/'completion.json')['consumption']['cumulative_environment_starts']==6466 and summary['consumption']['cumulative_learning_starts']==641
    final_by={(r['seed'],r['family'],r['context'],r['policy']):r for r in final};g=[r for r in final if r['policy']==candidate]
    heat=joint=0
    for r in g:
        pairs=[pair(r,final_by[r['seed'],r['family'],r['context'],p]) for p in reg['policies'][:2]];heat+=all(p[1] for p in pairs);joint+=all(p[2] for p in pairs)
    assert heat==12 and joint==3 and read(B/'browser_verification.json')['status']=='PASS'
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=len(reg['sources']),diagnostic_exact_replays=24,
        selection_recomputed=True,final_rows=120,final_complete_requests=7920,live_guard_records=len(guards),heat_gain_conditions=heat,joint_gain_conditions=joint,new_environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result
if __name__=='__main__':check()
