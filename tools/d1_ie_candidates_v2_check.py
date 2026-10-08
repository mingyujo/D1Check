"""Portable shared-artifact checks; no simulator/torch/solver import or starts."""
from __future__ import annotations
import csv,hashlib,json,subprocess
from pathlib import Path
from tools import d1_ie_candidates_v2_report as report

ROOT=report.ROOT;BUNDLE=report.BUNDLE
def read_csv(path):
    with path.open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def check():
    contract=report.read(BUNDLE/'registration.json');completion=report.read(BUNDLE/'completion.json');summary=report.read(BUNDLE/'summary.json')
    sources=dict(contract['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(report.read(BUNDLE/'repair.json')['source_overrides'])
    for rel,digest in sources.items():
        if report.sha(ROOT/rel)!=digest:raise AssertionError('source hash: '+rel)
    assert report.sha(BUNDLE/'inputs.json')==contract['inputs_sha256']
    rows=read_csv(BUNDLE/'final_results.csv');validation=read_csv(BUNDLE/'validation_results.csv')
    assert len(rows)==576 and len(validation)==288
    for r in rows:
        assert 0<=int(r['completed'])<=int(r['planned'])
        assert (r['energy_full_work_eligible']=='True')==(int(r['planned'])==int(r['completed']))
        for key in ('planned','completed','deadline_met','urgent_service_failure','normal_service_failure','seed'):r[key]=int(r[key])
        for key in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms'):r[key]=float(r[key]) if r[key] not in ('','None') else None
    recomputed=report.eligibility(rows);assert recomputed==summary['final_eligibility']
    chosen=report.read(BUNDLE/'selection_after_validation.json');assert chosen['frozen_before_final'] and summary['no_post_final_selection']
    assert completion['consumption']==summary['consumption']
    ledger=read_csv(BUNDLE/'execution_receipts.csv');starts=[r for r in ledger if r['event']=='start'];ends=[r for r in ledger if r['event']=='completed'];failures=[r for r in ledger if r['event']=='failed']
    assert len(starts)==summary['consumption']['new_environment_starts']<=1536
    assert len({r['identity'] for r in starts})==len(starts)
    assert len(ends)+len(failures)==len(starts)
    assert summary['consumption']['cumulative_environment_starts']==3633+len(starts)<=20000
    assert summary['consumption']['cumulative_learning_starts']<=6144
    assert len(report.read(BUNDLE/'representatives.json'))==12
    assert len(list((BUNDLE/'figures').glob('*.png')))==5
    frozen=report.read(BUNDLE/'artifact_manifest.json')
    for rel,digest in frozen['artifacts'].items():assert report.sha(ROOT/rel)==digest,rel
    result=dict(status='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        final_rows=576,validation_rows=288,policies=12,all_completed=all(r['planned']==r['completed'] for r in rows),eligibility_recomputed=True,
        artifact_hashes=len(frozen['artifacts']),environment_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':check()
