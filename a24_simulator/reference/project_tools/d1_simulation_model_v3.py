"""Source-balanced correction, bounded conditional nested validation, no device API."""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v3_thermal as thermal
from tools import d1_simulation_model_v3_energy as energy
from tools import d1_simulation_model_v3_inputs as inputs

ROOT=v2.ROOT
VERSION='empirical-simulation-model-v3'
LAMBDAS=(0.,.01,.1,1.,10.,100.)
VALUES=(0.,.5,1.)
FIT_LIMIT=1000
PLAN=ROOT/'docs/SIMULATION_MODEL_V3_PLAN_20261010.md'


def write(path,value):
    from tools.d1_arrival_timing_calibration import write_new
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);write_new(path,value)


def digest_value(value):
    return hashlib.sha256(p.canonical(value)).hexdigest()


def source_identity():
    names=('tools/d1_simulation_model_v3.py','tools/d1_simulation_model_v3_thermal.py',
        'tools/d1_simulation_model_v3_energy.py','tools/d1_simulation_model_v3_inputs.py',
        'tools/d1_simulation_model_v2.py','tools/d1_model_refinement.py','tools/d1_online_policy_model.py',
        'docs/SIMULATION_MODEL_V3_PLAN_20261010.md','docs/SIMULATION_MODEL_V3_EXPERT_MEETING_20261010.md')
    return {name:p.digest(ROOT/name) for name in names}


def candidate_choices(head):
    return [dict(lambda_=lam,**({'alpha':value} if head=='thermal' else {'gain':value}))
            for value in VALUES for lam in LAMBDAS]


def safe_case(c):
    return inputs.public_input(c)


def head_prediction(public,head,kind,original):
    if kind=='thermal':
        base,matrix,_=thermal.design(public,original,head['alpha'])
        return (base+matrix@head['coefficients']).tolist()
    safe={k:public[k] for k in ('pre_w','initial_power_late_w','actual') if k in public}
    return energy.predict(safe,head,120.)


def head_score(c,public,head,kind,original):
    predicted=head_prediction(public,head,kind,original)
    if kind=='thermal':return v2.prior.base.common.score(c['ap'],predicted)['mae_c']
    return abs(predicted-v2.prior.integral(c,0,120))


def aggregate_rows(rows):
    b=[r for r in rows if r['mode']=='B']
    used=b if b else [r for r in rows if r['mode']=='A']
    groups=sorted({r['group'] for r in used})
    means={g:statistics.mean(r['error'] for r in used if r['group']==g) for g in groups}
    a=[r for r in rows if r['mode']=='A']
    return dict(primary_mode='B' if b else 'A_fallback_no_arrival_contract',
        primary_mean=statistics.mean(means.values()),worst_group=max(means.values()),
        worst_session=max(r['error'] for r in used),source_means=means,
        A_source_means={g:statistics.mean(r['error'] for r in a if r['group']==g) for g in sorted({r['group'] for r in a})})


def choice_key(score,choice,kind):
    value=choice['alpha'] if kind=='thermal' else choice['gain']
    return (score['primary_mean'],score['worst_group'],score['worst_session'],-choice['lambda_'],value)


def baseline_head(original,kind):
    if kind=='thermal':return dict(coefficients=thermal.prior_coefficients(original).tolist(),alpha=1.,lambda_=100.)
    return dict(increments=copy.deepcopy(original['energy_increment_w']),lambda_=100.,gain=0.,relaxation_tau_s=30.)


class Study:
    def __init__(self,cases,original,folder):
        self.cases=cases;self.original=original;self.folder=Path(folder);self.start=time.monotonic()
        self.groups=sorted({inputs.group(c) for c in cases});self.cache={};self.fit_calls=0
        self.by_id={c['id']:c for c in cases};self.public={c['id']:dict(safe_case(c),actual=c['actual']) for c in cases}
        self.b={r['case']['id']:r for r in inputs.development_B_cases(cases,original)}
        if len(cases)!=17 or len(self.groups)!=5 or len(self.b)!=6:raise ValueError('development17/source5/B6 roster')

    def fit(self,train,kind,choice):
        key=(kind,tuple(sorted(c['id'] for c in train)),digest_value(choice))
        if key not in self.cache:
            if self.fit_calls>=FIT_LIMIT or time.monotonic()-self.start>=3600:raise RuntimeError('bounded development fit/time cap')
            self.fit_calls+=1
            write(self.folder/f'fit_ledger/{self.fit_calls:04d}_intent.json',dict(call=self.fit_calls,head=kind,choice=choice,development_ids=list(key[1])))
            module=thermal if kind=='thermal' else energy
            result=module.fit(train,self.original,**choice)
            write(self.folder/f'fit_ledger/{self.fit_calls:04d}_model.json',result)
            self.cache[key]=result
        return self.cache[key]

    def rows(self,held,head,kind):
        rows=[]
        for c in held:
            rows.append(dict(id=c['id'],group=inputs.group(c),mode='A',error=head_score(c,self.public[c['id']],head,kind,self.original)))
            if c['id'] in self.b:
                rows.append(dict(id=c['id'],group=inputs.group(c),mode='B',error=head_score(c,self.b[c['id']]['public'],head,kind,self.original)))
        return rows

    def choose(self,train,kind):
        profiles=[]
        for choice in candidate_choices(kind):
            rows=[]
            for g in sorted({inputs.group(c) for c in train}):
                remaining=[c for c in train if inputs.group(c)!=g];held=[c for c in train if inputs.group(c)==g]
                head=self.fit(remaining,kind,choice);rows.extend(self.rows(held,head,kind))
            profile=dict(choice=choice,score=aggregate_rows(rows),rows=rows);profiles.append(profile)
        winner=min(profiles,key=lambda item:choice_key(item['score'],item['choice'],kind))
        return winner,profiles

    def run(self):
        nested=[]
        for g in self.groups:
            train=[c for c in self.cases if inputs.group(c)!=g];held=[c for c in self.cases if inputs.group(c)==g]
            for kind in ('thermal','energy'):
                selected,profiles=self.choose(train,kind);head=self.fit(train,kind,selected['choice'])
                row=dict(held_source=g,head=kind,inner_selected=selected,inner_profiles=profiles,
                    held_rows=self.rows(held,head,kind),baseline_rows=self.rows(held,baseline_head(self.original,kind),kind))
                nested.append(row);write(self.folder/f'nested/{g}_{kind}.json',row)
            print(json.dumps(dict(stage='outer_source_completed',source=g,fit_calls=self.fit_calls)),flush=True)
        heads={};selection={}
        for kind in ('thermal','energy'):
            chosen,profiles=self.choose(self.cases,kind);heads[kind]=self.fit(self.cases,kind,chosen['choice'])
            selection[kind]=dict(selected=chosen,profiles=profiles)
        model=dict(version=VERSION,**heads,original_model=dict(path=str(v2.prior.MODEL),sha256=v2.prior.MODEL_SHA),
            service=dict(mode='frozen_original_forecast',sha256=v2.prior.MODEL_SHA),
            development_ids=[c['id'] for c in self.cases],default=False,strict_support=False,
            experiment_ready=False,thermal_service_feedback=None,accuracy_pass=None,
            evidence='source-balanced development correction; nested selection conditional on fixed prior and service, not full-family independent OOF')
        frozen=dict(version='simulation-model-v3-freeze-v1',model=model,selection=selection,nested=nested,
            development_validated_sha256={},source_code=source_identity(),source_inventory=inputs.source_inventory(),
            plan_sha256=p.digest(PLAN),fit_calls=self.fit_calls,confirmation_fit_forbidden=True)
        write(self.folder/'development_freeze.json',frozen);write(self.folder/'model.json',model)
        write(self.folder/'freeze_receipt.json',dict(sha256=p.digest(self.folder/'development_freeze.json'),
            fit_calls=self.fit_calls,elapsed_s=time.monotonic()-self.start,source_code=source_identity(),
            status='frozen_before_posthoc_and_new_confirmation',experiment_ready=False))
        return frozen


def cost_assessment(c,model,original,public=None):
    public=dict(safe_case(c),actual=c['actual']) if public is None else public
    ap,initial=thermal.predict(public,model['thermal'],original)
    score=v2.prior.base.common.score(c['ap'],ap)
    safe={k:public[k] for k in ('pre_w','initial_power_late_w','actual') if k in public}
    for name,t in (('120s',120.),('registered',c.get('common_end_s',120.))):
        score[name+'_energy_signed_j']=energy.predict(safe,model['energy'],t)-v2.prior.integral(c,0,t)
    return dict(scores=score,predicted_AP_c=ap,AP_query_s=c['q'],initial=initial,
        scope='A actual schedule conditional' if public['actual'] is c.get('actual') else 'explicit supplied schedule; A/B marked by caller',accuracy_pass=None)


def develop(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    original=p.read(v2.prior.MODEL)
    if p.digest(v2.prior.MODEL)!=v2.prior.MODEL_SHA:raise ValueError('original model changed')
    cases=inputs.load_development()
    write(folder/'registration.json',dict(plan_sha256=p.digest(PLAN),source_code=source_identity(),
        source_inventory=inputs.source_inventory(),development_ids=[c['id'] for c in cases],
        head_choices={head:candidate_choices(head) for head in ('thermal','energy')},max_head_fits=FIT_LIMIT,
        reference_v2_sha256=p.digest(ROOT/'docs/results/simulation_model_v2_01/run_v1/model.json')))
    try:
        frozen=Study(cases,original,folder).run()
        return dict(status='MODEL_FROZEN',fit_calls=frozen['fit_calls'],model_sha256=p.digest(folder/'model.json'),
            freeze_sha256=p.digest(folder/'development_freeze.json'),selected={k:v['selected']['choice'] for k,v in frozen['selection'].items()})
    except BaseException as exc:
        import traceback
        write(folder/'FAILED_development.json',dict(error=repr(exc),stack=traceback.format_exc(),automatic_retry=False,device_commands=0))
        raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['develop']);parser.add_argument('--output',required=True)
    a=parser.parse_args();print(json.dumps(develop(a.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
