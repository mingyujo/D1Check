"""Portable read-only verification of shared CSV/inputs/receipts; zero engine starts."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/reserved_thermal_01'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_read(path):
    with path.open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def verify():
    manifest=read(BUNDLE/'share_manifest.json')
    for name,sha in manifest['files'].items():
        path=ROOT/name
        assert path.is_file() and digest(path)==sha,'shared byte mismatch: '+name
    final=BUNDLE/'final_rule_only';reg=read(final/'registration.json')
    for name,sha in reg['source_hashes'].items():
        assert digest(ROOT/name)==sha,'registered source mismatch: '+name
    assert digest(final/'inputs.json')==reg['inputs_sha256']
    inputs=read(final/'inputs.json');conditions={(w['seed'],w['family'],ctx)
        for w in inputs['workloads'] for ctx in reg['contexts']}
    assert len(conditions)==192 and len(reg['policies'])==11
    planned={(w['seed'],w['family']):len(w['tickets']) for w in inputs['workloads']}
    for w in inputs['workloads']:
        assert [q['ordinal'] for q in w['tickets']]==list(range(len(w['tickets'])))
        assert all(q['deadline_offset_ns']==(1500000000 if q['priority']=='urgent' else 6000000000) for q in w['tickets'])
        assert len({q['id'] for q in w['tickets']})==len(w['tickets'])
    rows=csv_read(final/'results.csv');assert len(rows)==2112
    keys={(int(r['seed']),r['family'],r['context'],r['policy']) for r in rows}
    assert len(keys)==2112 and keys=={c+(p,) for c in conditions for p in reg['policies']}
    for r in rows:
        assert int(r['planned'])==planned[(int(r['seed']),r['family'])]
        assert int(r['completed'])+int(r['incomplete'])==int(r['planned'])
        assert int(r['deadline_met'])+int(r['urgent_service_failure'])+int(r['normal_service_failure'])==int(r['planned'])
        assert bool(r['peak_ap_c'])==(r['completed']==r['planned'])
    sums=read(final/'summary.json')['policy_summary']
    for summary in sums:
        chosen=[r for r in rows if r['policy']==summary['policy']]
        for field in ('planned','completed','incomplete','deadline_met','urgent_service_failure','normal_service_failure'):
            assert sum(int(r[field]) for r in chosen)==summary[field],field
    pp=csv_read(final/'pairs.csv');assert len(pp)==1920
    by={(int(r['seed']),r['family'],r['context'],r['policy']):r for r in rows}
    new=reg['policies'][-1]
    for pair in pp:
        c=(int(pair['seed']),pair['family'],pair['context']);a=by[c+(new,)];b=by[c+(pair['baseline'],)]
        for field,delta in (('energy_j','delta_energy_j'),('peak_ap_c','delta_peak_ap_c'),('urgent_p95_ms','delta_urgent_p95_ms')):
            if not a[field] or not b[field]:assert pair[delta]==''
            else:assert abs(float(a[field])-float(b[field])-float(pair[delta]))<1e-10,delta
    journal=csv_read(BUNDLE/'execution_receipts.csv')
    assert [int(r['number']) for r in journal]==list(range(1,len(journal)+1))
    assert len(journal)==manifest['consumption']['environment_starts']
    assert sum(r['status']=='failed' for r in journal)==manifest['consumption']['failed_starts']
    assert sum(r['kind']=='evaluation' and r['status']=='completed' for r in journal)==2112
    return dict(status='PASS',shared_files=len(manifest['files']),rows=2112,pairs=1920,
        inputs_conditions=192,receipt_starts=len(journal),engine_starts_for_check=0,device_commands=0)


if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
