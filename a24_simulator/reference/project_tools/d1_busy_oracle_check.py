"""Portable stdlib verification of the bounded occupied-prefix comparison."""
import csv,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BUNDLE=ROOT/'docs/results/busy_oracle_01'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def check():
    reg=read(BUNDLE/'registration.json');summary=read(BUNDLE/'summary.json');done=read(BUNDLE/'completion.json');repair=read(BUNDLE/'repair.json')
    sources=dict(reg['sources']);sources.update(repair['source_overrides'])
    for rel,h in sources.items():assert sha(ROOT/rel)==h,rel
    for rel,h in read(BUNDLE/'verification.json')['analysis_sources'].items():assert sha(ROOT/rel)==h,rel
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'];data=read(BUNDLE/'inputs.json');cases=[read(p) for p in sorted(BUNDLE.glob('case_*.json'))]
    assert len(data['screening'])==48 and sum(r['eligible'] for r in data['screening'])==len(cases)==len(data['cases'])==4
    assert done['status']==summary['status']=='completed' and done['consumption']==summary['consumption']
    for i,r in enumerate(cases):
        assert r['case']==data['cases'][i];c=r['case'];a=r['oracle'];counts=a['counts'];assert a['status']=='exhaustive_complete'
        assert counts['visited']+counts['pruned']==counts['raw'];assert counts['capacity_valid']>=counts['service_valid']>=counts['joint_gain']>=0
        prefix={j['request_id'] for j in c['prefix_calendar']};variable=set(c['variable_ids']);kept={q['id'] for q in c['tickets']}
        assert len(prefix)==11 and len(variable)==4 and not prefix&variable and prefix|variable==kept and len(kept)==15
        assert len(kept)+len(c['omitted_ids'])==c['original_requests']==24 and not kept&set(c['omitted_ids'])
        for j in c['prefix_calendar']:assert j['start_ns']<c['snapshot_ns']
        for row in list(r['baselines'].values())+list(r['verified'].values()):
            assert row['planned']==row['completed']==15 and row['incomplete']==0
        assert set(r['baselines'])==set(reg['baselines'])
        for role,w in a['witnesses'].items():
            if w is None:assert role not in r['verified'];continue
            assert len(w['calendar'])==4 and {j['request_id'] for j in w['calendar']}==variable
            for j in w['calendar']:
                index=c['variable_ids'].index(j['request_id']);q=next(q for q in c['tickets'] if q['id']==j['request_id'])
                assert j['start_ns'] in a['domains_ns'][index] and j['start_ns']>=max(q['arrival_ns'],c['snapshot_ns'])
                assert j['backend'] in (('CPU','GPU') if q['task']=='classification' else ('CPU',))
            for k in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms'):assert abs(w[k]-r['verified'][role][k])<1e-8
    assert sum(r['oracle']['counts']['raw'] for r in cases)==summary['raw_calendars']==17842176
    assert sum(r['oracle']['counts']['visited'] for r in cases)==summary['visited_calendars']==460378
    assert sum(r['oracle']['counts']['joint_gain'] for r in cases)==summary['joint_gain_calendars']==0
    assert summary['total_planned']==summary['total_completed']==630
    with (BUNDLE/'execution_receipts.csv').open(encoding='utf8') as f:es=list(csv.DictReader(f))
    starts=[r for r in es if r['event']=='start'];completed=[r for r in es if r['event']=='completed'];failed=[r for r in es if r['event']=='failed']
    assert len(starts)==43 and len(completed)==42 and len(failed)==1 and len({r['identity'] for r in starts})==43
    assert {r['identity'] for r in starts}=={r['identity'] for r in completed+failed}
    assert summary['consumption']['cumulative_environment_starts']==5298 and summary['consumption']['cumulative_learning_starts']==641 and summary['consumption']['new_learning_starts']==0
    robust=read(BUNDLE/'robustness.json');assert len(robust)==4
    for r in robust:
        assert r['row']['completed']==r['row']['planned']==r['reference']['planned']==r['reference']['completed']==15
        assert r['row']['context']==r['reference']['context']==r['actual_context'] and r['row']['seed']==r['reference']['seed']
    manifest=read(BUNDLE/'artifact_manifest.json')
    for rel,h in manifest['artifacts'].items():assert sha(ROOT/rel)==h,rel
    browser=read(BUNDLE/'browser_verification.json');assert browser['status']=='PASS' and browser['images_loaded']==5
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=len(sources),artifacts=len(manifest['artifacts']),
        cases=4,original_engine_successes=42,failed_starts_preserved=1,retained_work_complete=630,new_environment_starts=0,new_learning_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':check()
