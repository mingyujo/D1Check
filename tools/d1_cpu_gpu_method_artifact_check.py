"""Portable method-pilot evidence validation; no training/engine imports."""
import csv
import hashlib
import json
from pathlib import Path
from tools import d1_cpu_gpu_method_report as report

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/cpu_gpu_method_01'


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):
    with Path(path).open(encoding='utf8',newline='') as f:
        return [typed(r) for r in csv.DictReader(f)]


def typed(row):
    out={}
    for k,v in row.items():
        if v=='':out[k]=None
        elif v in ('True','False'):out[k]=v=='True'
        else:
            try:out[k]=json.loads(v)
            except ValueError:out[k]=v
    return out


def check():
    seal=read(BUNDLE/'verification.json')
    for rel,h in seal['artifact_hashes'].items():assert sha(ROOT/rel)==h,rel
    c=read(BUNDLE/'registration.json');repair=read(BUNDLE/'repair.json')
    assert repair['registration_sha256']==sha(BUNDLE/'registration.json') and not repair['clock_reset']
    assert c['episodes_per_variant_seed']==32 and c['learning_seeds']==[11,23,37]
    train=rows(BUNDLE/'training_summary.csv')
    assert len(train)==6 and sum(r['episodes'] for r in train)==192
    assert all(r['episodes']==32 and r['updates']==4 for r in train)
    final=rows(BUNDLE/'final_results.csv');validation=rows(BUNDLE/'validation_results.csv')
    assert len(final)==264 and len(validation)==132
    for data,n in ((final,24),(validation,12)):
        assert len({(r['seed'],r['family'],r['context'],r['policy']) for r in data})==len(data)
        assert all(sum(r['policy']==p for r in data)==n for p in report.LABELS)
    actual=report.eligibility(final);stored=rows(BUNDLE/'final_eligibility.csv')
    assert actual==stored
    assert not read(BUNDLE/'selection.json')['no_global_optimality'] is False
    receipt=read(BUNDLE/'completion.json');budget=receipt['consumption']
    journal=rows(BUNDLE/'execution_receipts.csv')
    assert len(journal)==budget['new_starts']
    assert budget['cumulative']==2916+len(journal)<=20000
    assert [r['cumulative_number'] for r in journal]==list(range(2917,budget['cumulative']+1))
    assert budget['learning_episodes']==sum(r['kind'] in ('train','learning_fixture') for r in journal)<=228
    assert sum(r['status']=='failed' for r in journal)==budget['failed']==1
    assert receipt['device_commands']==budget['device_commands']==0
    return dict(status='PASS',scope='frozen matched small pilot, no device/algorithm-universal claim',
        final_rows=264,validation_rows=132,matched_training=192,actual_learning_starts=budget['learning_episodes'],
        cumulative_environment_starts=budget['cumulative'],new_environment_starts=budget['new_starts'],engine_calls=0)


if __name__=='__main__':print(json.dumps(check(),indent=2))
