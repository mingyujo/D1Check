"""Opt-in read-only sensitivity of archived PC schedules; no scheduler or fitting."""
import argparse
import copy
import csv
import gzip
import json
import math
import time
from pathlib import Path
import numpy as np
from tools import d1_joint_model_refinement as j

BUNDLE=j.m.ROOT/'docs/results/policy_coefficient_sensitivity_01'
IE=j.m.ROOT/'docs/results/ie_dispatch_01'
PRIOR=j.m.ROOT/'docs/results/reserved_thermal_01/final_rule_only'
FREEZE=j.BUNDLE/'run/candidate_freeze.json'
SEED=610880001
FAMILIES=('low','queue','burst','sustained')
CONTEXTS=('mean','short_context','long_context')
TARGETS=('RESERVED_THERMAL_REQUEST_V1_NUMERIC_R2','IE_EDD_ECT_LANE_PC_V1')
BASELINES=('SHARED_EFT','EFT_REFERENCE','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1','TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1')
POLICIES=TARGETS+BASELINES
FIELDS=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
EPS=1e-9


def csv_rows(path):
    with path.open(encoding='utf8') as f:return list(csv.DictReader(f))


def key(row):return (int(row['seed']),row['family'],row['context'],row['policy'])


def segments(ledger):
    if not ledger or len({r['id'] for r in ledger})!=len(ledger):raise ValueError('missing/duplicate request ledger')
    for r in ledger:
        if r['status']!='succeeded' or any(k not in r for k in FIELDS):raise ValueError('incomplete lane boundary')
        times=[r[k] for k in FIELDS]
        if any(not math.isfinite(v) for v in times) or times!=sorted(times):raise ValueError('boundary order')
        if r['dispatch_ns']<r['arrival_ns'] or r['dispatch_ns']<35e9 or r['lane_available_ns']>120e9:
            raise ValueError('release outside common window')
    # Reuses the existing actual-lane occupancy reader, not the scheduler.
    return j.m.screen.occupancy(dict(ledger=ledger),'stored_pc_schedule',1,201,'read_only')


def models():
    f=j.m.read(FREEZE);original=j.m.read(j.m.MODEL)
    return [('FROZEN',original),('JOINT_all9',f['final']['model'])]+[(f"exclude_{x['block']}",x['fit']['model']) for x in f['folds']]


def guard(values, service, all_deadlines):
    if len(values)!=5 or len({x['model'] for x in values})!=5:raise ValueError('complete five paired models required')
    fields=('delta_energy_j','delta_peak_ap_c')
    if any(x[k] is None or not math.isfinite(x[k]) for x in values for k in fields):
        return dict(status='unavailable',energy_min_j=None,energy_max_j=None,ap_min_c=None,ap_max_c=None,
                    joint_direction_all_five=False,all_deadline_joint_direction=False)
    lo,hi=min(x['delta_energy_j'] for x in values),max(x['delta_energy_j'] for x in values)
    al,ah=min(x['delta_peak_ap_c'] for x in values),max(x['delta_peak_ap_c'] for x in values)
    joint=hi < -EPS and ah < -EPS
    if not service:status='service_ineligible'
    elif not all_deadlines:status='deadline_ineligible'
    elif joint:status='joint_direction_all_five'
    elif (lo < -EPS and hi > EPS) or (al < -EPS and ah > EPS):status='sign_sensitive'
    elif hi<=EPS and ah < -EPS:status='heat_down_energy_nonincrease'
    elif lo>EPS and ah < -EPS:status='heat_energy_tradeoff_all_five'
    elif hi < -EPS and al>EPS:status='energy_heat_tradeoff_all_five'
    elif max(abs(lo),abs(hi),abs(al),abs(ah))<=EPS:status='numerical_tie'
    else:status='no_joint_direction'
    return dict(status=status,energy_min_j=lo,energy_max_j=hi,ap_min_c=al,ap_max_c=ah,
                joint_direction_all_five=joint,all_deadline_joint_direction=joint and service and all_deadlines)


def prepare():
    if BUNDLE.exists():raise FileExistsError('new study required; do not overwrite')
    # Selection is independent of sensitivity results and uses all 12 predefined contexts.
    select={(SEED,f,c,p) for f in FAMILIES for c in CONTEXTS for p in POLICIES}
    stored={};raw_hashes={}
    parent=j.m.ROOT/'output/reserved_thermal_20261008_v1/final_rule_only_v1'
    for path in sorted((parent/'items').glob('*.json.gz')):
        item=j.m.read(path);row=item['row'];k=key(row)
        if k in select and row['policy']!='IE_EDD_ECT_LANE_PC_V1':
            if k in stored:raise ValueError('duplicate archived identity')
            stored[k]=item;raw_hashes[path.relative_to(j.m.ROOT).as_posix()]=j.m.sha(path)
        if int(row['seed'])>SEED:break
    for f in FAMILIES:
        for c in CONTEXTS:
            path=j.m.ROOT/'output/ie_dispatch_20261008_v1/items'/f'{SEED}_{f}_{c}_IE_EDD_ECT_LANE_PC_V1.json.gz'
            item=j.m.read(path);stored[key(item['row'])]=item;raw_hashes[path.relative_to(j.m.ROOT).as_posix()]=j.m.sha(path)
    if set(stored)!=select:raise ValueError('missing registered stored schedule')
    initial=j.m.read(parent/'inputs.json')['initial']
    ie_inputs=j.m.read(j.m.ROOT/j.m.read(IE/'contract.json')['input_path'])
    if ie_inputs['initial']!=initial:raise ValueError('different initial conditions')
    metrics={key(r):r for path in (PRIOR/'results.csv',IE/'results.csv') for r in csv_rows(path)}
    cases=[]
    for k,item in sorted(stored.items()):
        row=item['row'];expected=metrics[k]
        for field in ('planned','completed','deadline_met','urgent_service_failure','normal_service_failure','urgent_p95_ms','energy_j','peak_ap_c'):
            if abs(float(row[field])-float(expected[field]))>1e-9:raise ValueError('stored summary mismatch')
        ledger=[{field:r[field] for field in ('id','ordinal','task','backend','priority','arrival_ns','deadline_offset_ns','status')+FIELDS} for r in item['result']['ledger']]
        if len(ledger)!=row['planned'] or row['completed']!=row['planned']:raise ValueError('work denominator')
        seg=segments(ledger);j.m.base.exposure(seg,0,120)
        cases.append(dict(seed=k[0],family=k[1],context=k[2],policy=k[3],row=row,ledger=ledger,segments=seg))
    BUNDLE.mkdir()
    with (BUNDLE/'inputs.json.gz').open('xb') as f:
        f.write(gzip.compress(json.dumps(dict(initial=initial,cases=cases),ensure_ascii=False,allow_nan=False).encode('utf8'),mtime=0))
    shared=[j.m.MODEL,FREEZE,IE/'results.csv',PRIOR/'results.csv',IE/'contract.json',PRIOR/'registration.json',BUNDLE/'inputs.json.gz']
    contract=dict(id='POLICY-COEFFICIENT-SENSITIVITY-01',utc=j.now(),source_head='7734e668be8bededb59ccfd98436c73d06d05629',
                  input_hashes={p.relative_to(j.m.ROOT).as_posix():j.m.sha(p) for p in shared},archived_item_hashes=raw_hashes,
                  seed=SEED,families=list(FAMILIES),contexts=list(CONTEXTS),targets=list(TARGETS),baselines=list(BASELINES),
                  scheduled_cases=72,paired_comparisons=96,model_variants=5,cost_evaluations=360,new_environment_starts=0,new_fits=0,
                  selection='first registered seed; all four families and three contexts; frozen before rescore',
                  question='direction across development-block coefficient variants conditional on fixed stored PC lane schedule',
                  limitations=['not rerunning B policy with changed costs','not physical uncertainty bounds or confidence interval',
                               'four rejected development-refit variants are stress probes, not validated models',
                               'does not perturb service/throttle/environment/control costs','posthoc previously seen input/results'],
                  energy_window=[0,120],ap_window=[35,180],ap_period_s=1,numerical_tie_epsilon=EPS,
                  guard='same variant paired; full work+no extra failures+urgent P95 nonincrease, both all-deadlines required for joint status',
                  defaults_changed=False,accuracy_pass=None,experiment_ready=False,device_commands=0)
    j.m.write(BUNDLE/'contract.json',contract)
    print(json.dumps(dict(prepared=72,pairs=96,device_commands=0)))


def run(output):
    if output.exists():raise FileExistsError('new output required')
    contract=j.m.read(BUNDLE/'contract.json')
    for p,digest in contract['input_hashes'].items():
        if j.m.sha(j.m.ROOT/p)!=digest:raise ValueError('input changed')
    inputs=j.m.read(BUNDLE/'inputs.json.gz');cases=inputs['cases'];initial=inputs['initial'];variants=models()
    if len(cases)!=72 or len(variants)!=5:raise ValueError('complete denominator')
    output.mkdir(parents=True);started=time.monotonic();scores=[];exposures=[];curves=[]
    for c in cases:
        seg=c['segments'];exposure=j.m.base.exposure(seg,0,120)
        exposures.append(dict(seed=c['seed'],family=c['family'],context=c['context'],policy=c['policy'],
                              **dict(zip(j.m.base.STATES,map(float,exposure))),idle_s=120-float(sum(exposure))))
        for name,model in variants:
            costs=j.m.base.costs(seg,initial,list(range(35,181)),model,180)
            peak=max(costs['ap_path']);energy=costs['whole_120s_j']
            if name=='FROZEN' and max(abs(energy-c['row']['energy_j']),abs(peak-c['row']['peak_ap_c']))>1e-6:
                raise ValueError('original cost did not reproduce')
            reference=costs['initial']['reference_c']
            area=float(np.trapezoid([max(0,t-reference) for t in costs['ap_path']],range(35,181)))
            if name=='FROZEN' and abs(area-c['row']['thermal_degree_seconds'])>1e-6:
                raise ValueError('original AP area did not reproduce')
            scores.append(dict(seed=c['seed'],family=c['family'],context=c['context'],policy=c['policy'],model=name,
                               energy_j=energy,peak_ap_c=peak,thermal_degree_seconds=area,ap_area_reference_c=reference,
                               planned=c['row']['planned'],completed=c['row']['completed'],deadline_met=c['row']['deadline_met'],
                               urgent_p95_ms=c['row']['urgent_p95_ms'],normal_mean_ms=c['row']['normal_mean_ms']))
            if c['context']=='mean' and c['family']=='sustained':
                curves.extend(dict(policy=c['policy'],model=name,t_s=t,ap_c=a) for t,a in zip(range(35,181),costs['ap_path']))
    by={(r['family'],r['context'],r['policy'],r['model']):r for r in scores}
    original={(c['family'],c['context'],c['policy']):c['row'] for c in cases}
    deltas=[];guarded=[]
    for family in FAMILIES:
        for context in CONTEXTS:
            for policy in TARGETS:
                for baseline in BASELINES:
                    a=original[family,context,policy];b=original[family,context,baseline]
                    service=(a['completed']==a['planned']==b['completed']==b['planned'] and
                             a['urgent_service_failure']<=b['urgent_service_failure'] and a['normal_service_failure']<=b['normal_service_failure'] and
                             a['urgent_p95_ms']<=b['urgent_p95_ms']+EPS)
                    all_deadlines=a['deadline_met']==a['planned'] and b['deadline_met']==b['planned']
                    identity=dict(seed=SEED,family=family,context=context,policy=policy,baseline=baseline)
                    local=[]
                    for name,_ in variants:
                        p=by[family,context,policy,name];q=by[family,context,baseline,name]
                        row=dict(**identity,model=name,delta_energy_j=p['energy_j']-q['energy_j'],delta_peak_ap_c=p['peak_ap_c']-q['peak_ap_c'],
                                 delta_ap_area_cs=p['thermal_degree_seconds']-q['thermal_degree_seconds'])
                        local.append(row);deltas.append(row)
                    frozen=local[0]
                    guarded.append(dict(**identity,service_preserved=service,both_all_deadlines=all_deadlines,
                                        policy_deadline_failures=a['planned']-a['deadline_met'],baseline_deadline_failures=b['planned']-b['deadline_met'],
                                        frozen_delta_energy_j=frozen['delta_energy_j'],frozen_delta_peak_ap_c=frozen['delta_peak_ap_c'],
                                        original_joint_direction=frozen['delta_energy_j'] < -EPS and frozen['delta_peak_ap_c'] < -EPS,
                                        **guard(local,service,all_deadlines),physical_saving_verified=False))
    summary=[]
    for scope,families in [('primary',('low','sustained')),('all',FAMILIES)]:
        for policy in TARGETS:
            for baseline in BASELINES:
                use=[r for r in guarded if r['family'] in families and r['policy']==policy and r['baseline']==baseline]
                summary.append(dict(scope=scope,policy=policy,baseline=baseline,comparisons=len(use),
                                    full_deadline_service=sum(r['both_all_deadlines'] and r['service_preserved'] for r in use),
                                    original_full_deadline_joint=sum(r['original_joint_direction'] and r['both_all_deadlines'] and r['service_preserved'] for r in use),
                                    joint_direction_all_five=sum(r['all_deadline_joint_direction'] for r in use),
                                    status_counts={name:sum(r['status']==name for r in use) for name in sorted({r['status'] for r in use})}))
    for name,rows in [('costs.csv',scores),('state_exposure.csv',exposures),('paired_variants.csv',deltas),('direction_guard.csv',guarded),('ap_curves.csv',curves)]:j.m.table(output/name,rows)
    result=dict(id=contract['id'],utc=j.now(),active_seconds=time.monotonic()-started,stored_schedules=72,model_costs=360,paired_variants=480,guarded_comparisons=96,
                summary=summary,new_environment_starts=0,new_fit_calls=0,device_commands=0,rl_training=0,posthoc=True,
                confidence_interval=False,physical_saving_verified=False,default_changed=False,accuracy_pass=None,experiment_ready=False)
    j.m.write(output/'summary.json',result);print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--output',default=str(BUNDLE/'run'))
    a=p.parse_args();prepare() if a.action=='prepare' else run(Path(a.output))
