"""Portable verification of frozen inputs and exhaustive calendar certificates."""
import csv,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];BUNDLE=ROOT/'docs/results/micro_oracle_01'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check():
    c=read(BUNDLE/'registration.json');s=read(BUNDLE/'summary.json');done=read(BUNDLE/'completion.json')
    for rel,h in c['sources'].items():assert sha(ROOT/rel)==h,rel
    assert sha(BUNDLE/'inputs.json')==c['inputs_sha256']
    assert done['status']=='completed' and s['consumption']==done['consumption']
    cases=[read(p) for p in sorted(BUNDLE.glob('case_*.json'))];assert len(cases)==24
    for r in cases:
        a=r['oracle'];counts=a['counts'];assert a['status']=='exhaustive_complete'
        assert counts['raw']==counts['visited']+counts['pruned']
        assert counts['capacity_valid']>=counts['service_valid']>=counts['joint_gain']>=0
        for row in list(r['baselines'].values())+list(r['verified'].values()):assert row['completed']==row['planned']==4
        for key in ('energy_min_ap_cap','ap_min_energy_cap'):
            w=a[key]
            assert len(w['calendar'])==4 and len({j['request_id'] for j in w['calendar']})==4
            for job in w['calendar']:
                q=next(q for q in r['case']['tickets'] if q['id']==job['request_id'])
                assert job['start_ns'] in a['domains_ns'][r['case']['tickets'].index(q)] and job['start_ns']>=q['arrival_ns']
                assert job['backend'] in (('CPU','GPU') if q['task']=='classification' else ('CPU',))
    assert sum(r['oracle']['counts']['raw'] for r in cases)==s['raw_calendars']==91541016
    assert sum(r['oracle']['counts']['visited'] for r in cases)==s['visited_calendars']==288486
    assert s['joint_gain_calendars']==0 and s['native_witnesses_nonworse']==24
    assert s['total_planned']==s['total_completed']==800
    with (BUNDLE/'execution_receipts.csv').open(encoding='utf8') as f:receipts=list(csv.DictReader(f))
    starts=[r for r in receipts if r['event']=='start'];completed=[r for r in receipts if r['event']=='completed']
    assert len(starts)==len(completed)==200 and len({r['identity'] for r in starts})==200
    assert s['consumption']['cumulative_environment_starts']==5255 and s['consumption']['new_learning_starts']==0
    manifest=read(BUNDLE/'artifact_manifest.json')
    for rel,h in manifest['artifacts'].items():assert sha(ROOT/rel)==h,rel
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        cases=24,raw_calendars=91541016,visited_calendars=288486,engine_runs=200,all_completed=True,
        source_hashes=len(c['sources']),artifact_hashes=len(manifest['artifacts']),environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':check()
