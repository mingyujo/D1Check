"""One preselected pooled-background candidate; previously viewed data only."""
import argparse
import copy
import csv
import json
import math
import shutil
from collections import Counter
from pathlib import Path
import numpy as np
from tools import d1_online_policy_model as m
from tools import d1_arrival_plan as p

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'docs/results/online_policy_study_01/pooled_candidate_v1/contract.json'


def inputs(archive):
    archive=Path(archive);old=archive/'online_policy_study_run_v4'
    freeze=old/'model_freeze.json';contract=p.read(CONTRACT)
    if p.digest(freeze)!=contract['old_model_sha256']:raise ValueError('original freeze differs')
    cases=p.read(old/'development_cases.json')+p.read(old/'confirmation_cases.json')
    evidence={str(old/f):p.digest(old/f) for f in ['model_freeze.json','development_cases.json','confirmation_cases.json']}
    follow=archive/'online_power_sampling_plan_v2/collection_plan.json';plan=p.read(follow)
    for file,h in plan['imported_completed']['files'].items():
        if p.digest(file)!=h:raise ValueError('sampling import drift')
    for file,indices in [(Path(plan['imported_completed']['plan']),[0,1]),(follow,[0,1])]:
        source=p.read(file);evidence[str(file)]=p.digest(file)
        for i in indices:
            e=source['entries'][i];cases.append(m.load_case(file,source,e))
            folder=Path(source['output_root'])/f"{e['index']:02d}_{e['session_id']}"
            for f in [folder/'validated.json',folder/'thermal.jsonl',*sorted((folder/'artifacts').glob('*'))]:
                if f.is_file():evidence[str(f)]=p.digest(f)
    if len(cases)!=13 or len({c['id'] for c in cases})!=13:raise ValueError('exact thirteen eligible sessions')
    for c in cases:
        c['original_role']=c['study_phase'];c['study_phase']='candidate_posthoc_development'
    return cases,p.read(freeze)['model'],evidence


def design(cases):
    counts=Counter(c['policy'] for c in cases);x=[];y=[]
    if set(counts)!=set(m.POLICIES):raise ValueError('three policy support required')
    for c in cases:
        w=1/math.sqrt(counts[c['policy']]*24)
        for a in range(0,120,5):
            x.append(np.r_[5.,m.exposure(c['inputs']['segments'],a,a+5)]*w)
            y.append(m.energy_at(c,a,a+5)*w)
    return np.asarray(x),np.asarray(y)


def fit(cases,old):
    if any(c['study_phase']!='candidate_posthoc_development' for c in cases):raise ValueError('only designated candidate development')
    x,y=design(cases);rank=int(np.linalg.matrix_rank(x))
    if rank!=5:raise ValueError('pooled energy coefficients unidentified')
    z=m.nnls(x,y)
    if z[0]<=0:raise ValueError('invalid resident baseline')
    model=copy.deepcopy(old)
    model.update(version='online-policy-pooled-energy-v1',energy_baseline_mode='pooled_resident_v1',resident_w=float(z[0]),
        energy_increment_w=dict(zip(m.STATES,z[1:].tolist())),candidate_posthoc=True,
        development_ids=[c['id'] for c in cases],energy_design_singular_values=np.linalg.svd(x,compute_uv=False).tolist(),
        energy_fit_rmse_j=float(np.mean((x@z-y)**2)**.5),scope='registered A24 policies and96 requests500/550ms; pooled resident statistical estimate; fresh900ms confirmation pending',
        accuracy_pass=None,experiment_ready=False)
    return model


def error(c,model,a=0,b=120):
    base=model['resident_w'] if model.get('energy_baseline_mode')=='pooled_resident_v1' else c['preload_power_w']
    predicted=(b-a)*base+float(m.exposure(c['inputs']['segments'],a,b)@np.array([model['energy_increment_w'][k] for k in m.STATES]))
    observed=m.energy_at(c,a,b)
    return predicted,observed,predicted-observed


def run(archive,output):
    output=Path(output)
    if output.exists():raise ValueError('fresh analysis directory required')
    cases,old,evidence=inputs(archive);model=fit(cases,old);rows=[]
    for i,c in enumerate(cases):
        loo=fit(cases[:i]+cases[i+1:],old)
        for name,which in [('original_frozen',old),('pooled_in_sample',model),('pooled_leave_session_out',loo)]:
            pred,obs,err=error(c,which)
            rows.append(dict(id=c['id'],policy=c['policy'],original_role=c['original_role'],evaluation_role='viewed_data_posthoc',
                mode=name,observed_j=obs,predicted_j=pred,signed_j=err,absolute_j=abs(err),
                future_signed_j=error(c,which,35,120)[2],resident_w=which.get('resident_w'),
                smallest_singular_value=which['energy_design_singular_values'][-1]))
    a=[r['absolute_j'] for r in rows if r['mode']=='original_frozen'];b=[r['absolute_j'] for r in rows if r['mode']=='pooled_leave_session_out']
    advance=bool(np.mean(b)<np.mean(a) and max(b)<=max(a))
    report=dict(contract_sha256=p.digest(CONTRACT),original_frozen_sha256=p.read(CONTRACT)['old_model_sha256'],
        source_cases=13,original_mean_absolute_j=float(np.mean(a)),pooled_loso_mean_absolute_j=float(np.mean(b)),
        original_max_absolute_j=max(a),pooled_loso_max_absolute_j=max(b),advance_to_independent_confirmation=advance,
        selection='preselected one family, rank/positive b all folds, lower mean abs and no worse max; not accuracy PASS',
        independent_confirmation_sessions=0,fit_families=1,ap_and_service_unchanged=model['ap']==old['ap'] and model['service']==old['service'],experiment_ready=False)
    output.mkdir(parents=True)
    for name,value in [('candidate.json',model),('summary.json',report),('source_inventory.json',evidence)]:
        (output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    with (output/'evaluation.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return report


def render(output,shared):
    """Export existing fit evidence without re-fitting or device access."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=Path(output);shared=Path(shared);shared.mkdir(parents=True,exist_ok=True)
    report=p.read(output/'summary.json')
    if report['contract_sha256']!=p.digest(CONTRACT):raise ValueError('render contract drift')
    with (output/'evaluation.csv').open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    original=[r for r in rows if r['mode']=='original_frozen']
    held=[r for r in rows if r['mode']=='pooled_leave_session_out']
    if len(original)!=13 or [r['id'] for r in original]!=[r['id'] for r in held]:raise ValueError('case alignment')
    fig,ax=plt.subplots(figsize=(11,5))
    x=np.arange(13)
    ax.bar(x-.18,[float(r['signed_j']) for r in original],.36,label='Original frozen')
    ax.bar(x+.18,[float(r['signed_j']) for r in held],.36,label='Pooled candidate: leave-session-out')
    ax.axhline(0,color='black',lw=.6);ax.set_xticks(x,[str(i+1) for i in x])
    ax.set(xlabel='Case order in evaluation.csv (all previously viewed)',ylabel='Predicted minus observed, J / 120 s',title='Posthoc evaluation; candidate screen failed; no independent candidate validation')
    ax.legend();fig.tight_layout()
    fig.savefig(shared/'energy_errors.svg');fig.savefig(shared/'energy_errors.png',dpi=130);plt.close(fig)
    svg=shared/'energy_errors.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    for name in ['candidate.json','summary.json','evaluation.csv']:
        shutil.copyfile(output/name,shared/name)
    return report


if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--archive',required=True);q.add_argument('--output',required=True)
    q.add_argument('--render-existing',action='store_true');q.add_argument('--share')
    a=q.parse_args()
    result=p.read(Path(a.output)/'summary.json') if a.render_existing else run(a.archive,a.output)
    if a.share:render(a.output,a.share)
    print(json.dumps(result,indent=2))
