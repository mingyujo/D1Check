"""One preregistered legacy occupancy fit, followed by viewed-data transfer evaluation."""
import argparse
import copy
import csv
import json
from pathlib import Path
import numpy as np
from tools import d1_online_policy_model as m
from tools import d1_pooled_energy_candidate as pooled
from tools import d1_arrival_plan as p

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'docs/results/online_policy_study_01/legacy_transfer_v1/contract.json'
GEOMETRY=ROOT/'docs/results/online_policy_study_01/identifiability_v1/legacy_windows.csv'


def fit(rows,old):
    if not rows or any(r['role']!='legacy_development' for r in rows):raise ValueError('legacy development only')
    x=np.array([[5.,*[float(r[k]) for k in m.STATES]] for r in rows])
    y=np.array([r['observed_j'] for r in rows])
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.linalg.matrix_rank(x)!=5:raise ValueError('invalid or unidentified')
    z=m.nnls(x,y)
    if z[0]<=0:raise ValueError('nonpositive resident')
    model=copy.deepcopy(old)
    model.update(version='legacy-occupied-power-transfer-v1',energy_baseline_mode='pooled_resident_v1',resident_w=float(z[0]),
        energy_increment_w=dict(zip(m.STATES,z[1:].tolist())),candidate_posthoc=True,
        development_ids=['legacy_CC_DG','legacy_CG_DC','legacy_DC_DG'],
        scope='legacy occupied-state coefficients; online transfer unverified; no default or strict promotion',
        energy_design_singular_values=np.linalg.svd(x,compute_uv=False).tolist(),
        energy_fit_rmse_j=float(np.mean((x@z-y)**2)**.5),accuracy_pass=None,experiment_ready=False)
    return model,x@z-y


def training(archive):
    contract=p.read(CONTRACT);root=Path(archive)/'energy_ap_state_run_v5'
    if p.digest(GEOMETRY)!=contract['geometry_csv_sha256']:raise ValueError('geometry changed')
    file=root/'development_freeze.json'
    if p.digest(file)!=contract['old_frozen_sha256']:raise ValueError('legacy freeze changed')
    frozen=p.read(file);cases={};evidence={str(file):p.digest(file)}
    for i,pair in enumerate(('CC_DG','CG_DC','DC_DG')):
        folders=list(root.glob(f'{i:02d}_*'))
        if len(folders)!=1:raise ValueError('legacy source ambiguity')
        folder=folders[0];art=folder/'artifacts'
        for key,path in [('manifest',art/'manifest.json'),('progress',art/'progress.jsonl'),('thermal',folder/'thermal.jsonl')]:
            h=p.digest(path)
            if h!=frozen['input_hashes'][pair][key]:raise ValueError('legacy input drift')
            evidence[str(path)]=h
        if p.read(art/'cleanup.json')['status']!='completed':raise ValueError('legacy incomplete')
        events=[json.loads(s) for s in (art/'progress.jsonl').read_text(encoding='utf8').splitlines()]
        origin=[s['mono_ns'] for s in events if s['kind']=='phase_start' and s['phase']=='load']
        if len(origin)!=1:raise ValueError('legacy origin')
        cases[pair]=dict(origin_ns=origin[0],power_samples=[s for s in events if s['kind']=='power_sample'])
    with GEOMETRY.open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        a,b=float(r['start_s']),float(r['end_s'])
        if b-a!=5:raise ValueError('fixed5s only')
        r.update(observed_j=m.energy_at(cases[r['pair']],a,b),role='legacy_development')
    return rows,evidence


def run(archive,output):
    output=Path(output)
    if output.exists():raise ValueError('fresh output required')
    rows,evidence=training(archive);cases,old,online_evidence=pooled.inputs(archive)
    model,residual=fit(rows,old)
    for r,e in zip(rows,residual):r.update(predicted_j=r['observed_j']+float(e),signed_j=float(e))
    results=[]
    for c in cases:
        for name,which in [('original_frozen',old),('legacy_occupancy_transfer',model)]:
            pred,obs,err=pooled.error(c,which)
            results.append(dict(id=c['id'],policy=c['policy'],original_role=c['original_role'],evaluation_role='viewed_posthoc_transfer',
                mode=name,observed_j=obs,predicted_j=pred,signed_j=err,absolute_j=abs(err),future_signed_j=pooled.error(c,which,35,120)[2]))
    a=[r['absolute_j'] for r in results if r['mode']=='original_frozen'];b=[r['absolute_j'] for r in results if r['mode']=='legacy_occupancy_transfer']
    report=dict(contract_sha256=p.digest(CONTRACT),training_sessions=3,training_windows=len(rows),evaluation_sessions=13,
        independent_confirmation_sessions=0,original_mean_absolute_j=float(np.mean(a)),candidate_mean_absolute_j=float(np.mean(b)),
        original_max_absolute_j=max(a),candidate_max_absolute_j=max(b),advance_to_independent_confirmation=bool(np.mean(b)<np.mean(a) and max(b)<=max(a)),
        fit_families=1,ap_and_service_unchanged=model['ap']==old['ap'] and model['service']==old['service'],device_commands=0,experiment_ready=False)
    output.mkdir(parents=True)
    for n,v in [('candidate.json',model),('summary.json',report),('source_inventory.json',evidence|online_evidence)]:
        (output/n).write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
    for n,v in [('training.csv',rows),('evaluation.csv',results)]:
        with (output/n).open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(v[0]));writer.writeheader();writer.writerows(v)
    return report


def decompose_existing(archive,output):
    """Arithmetic residual split; observed idle power is never a prediction input."""
    output=Path(output);model=p.read(output/'candidate.json');summary=p.read(output/'summary.json')
    if summary['contract_sha256']!=p.digest(CONTRACT):raise ValueError('contract drift')
    destination=output/'segments.csv'
    if destination.exists():raise ValueError('preserve previous decomposition')
    cases,_,_=pooled.inputs(archive);rows=[]
    for c in cases:
        end=max(s['end_s'] for s in c['inputs']['segments'] if m.states.state_key(s['state'])!='resident_idle')
        if not 35<end<120:raise ValueError('actual workload boundary')
        total=0.
        for name,a,b in [('pre_load',0.,35.),('load_envelope',35.,end),('post_load',end,120.)]:
            pred,obs,err=pooled.error(c,model,a,b);total+=err
            rows.append(dict(id=c['id'],segment=name,start_s=a,end_s=b,observed_j=obs,predicted_j=pred,signed_j=err))
        if abs(total-pooled.error(c,model)[2])>1e-7:raise ValueError('integral decomposition closure')
    with destination.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return dict(refit=False,closure_cases=len(cases),segments=len(rows))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--decompose-existing',action='store_true')
    a=parser.parse_args();print(json.dumps((decompose_existing if a.decompose_existing else run)(a.archive,a.output),indent=2))
