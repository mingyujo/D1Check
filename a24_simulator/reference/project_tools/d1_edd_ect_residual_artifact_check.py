"""Portable read-only evidence check; no raw checkpoint or simulator required."""
import csv
import hashlib
import json
from pathlib import Path
from tools import d1_edd_ect_residual_report as report

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/edd_ect_residual_prototype_01'


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def typed(row):
    out={}
    for key,value in row.items():
        if value=='':out[key]=None
        elif value in ('True','False'):out[key]=value=='True'
        else:
            try:out[key]=json.loads(value)
            except ValueError:out[key]=value
    return out


def check():
    seal=read(BUNDLE/'share_verification.json')
    for rel,h in seal['artifact_hashes'].items():assert sha(ROOT/rel)==h,rel
    summary=read(BUNDLE/'summary.json');done=read(BUNDLE/'completion.json')
    assert done['results_sha256']==sha(BUNDLE/'results.csv')
    with (BUNDLE/'results.csv').open(encoding='utf8',newline='') as f:rows=[typed(row) for row in csv.DictReader(f)]
    assert len(rows)==60
    assert len({(r['seed'],r['family'],r['context'],r['policy']) for r in rows})==60
    assert sum(r['planned'] for r in rows)==sum(r['completed'] for r in rows)==3960
    by={(r['family'],r['context'],r['policy']):r for r in rows}
    witnesses=[]
    for r in rows:
        if r['policy'] not in (report.PRIOR,report.GREEDY):continue
        refs=[by[(r['family'],r['context'],p)] for p in (report.BASE,report.SHARED,report.BAND)]
        if report.gain_signal(r,refs,r['family'] in ('low','sustained')):
            witnesses.append(dict(family=r['family'],context=r['context'],policy=r['policy']))
    assert witnesses==summary['gates']['witnesses']
    assert summary['gates']['C']=='PASS' and not summary['gates']['training_allowed']
    branches=read(BUNDLE/'physical_branches.json')
    assert len(branches)==12 and all(b['actual_physical_difference'] for b in branches)
    with (BUNDLE/'execution_receipts.csv').open(encoding='utf8',newline='') as f:receipts=list(csv.DictReader(f))
    assert len(receipts)==91 and sum(r['status']=='failed' for r in receipts)==1
    assert [int(r['cumulative_number']) for r in receipts]==list(range(2826,2917))
    assert done['consumption']['cumulative_starts']==2916
    assert done['training_episodes']==done['device_commands']==0
    return dict(status='PASS',comparison_rows=60,scheduled_completed=3960,actual_environment_starts=91,
        cumulative_environment_starts=2916,physical_branches=12,c_signal_conditions=3,
        scope='frozen prototype only; later learning work has a separate journal',engine_calls=0)


if __name__=='__main__':print(json.dumps(check(),indent=2))
