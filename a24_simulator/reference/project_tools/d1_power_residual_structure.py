"""Recorded current changes and residual persistence; no device or policy actions."""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_rolling_forecast as r

BUNDLE=r.h.m.ROOT/'docs/results/power_residual_structure_01'


def csv_rows(p):
    with Path(p).open(encoding='utf-8') as f:return list(csv.DictReader(f))


def correlation(a,b):
    if len(a)<3 or np.std(a)<1e-12 or np.std(b)<1e-12:return None
    return float(np.corrcoef(a,b)[0,1])


def runs(samples,key):
    result=[];start=0
    for i in range(1,len(samples)+1):
        if i==len(samples) or samples[i][key]!=samples[start][key]:
            result.append(dict(first_s=samples[start]['t_s'],last_s=samples[i-1]['t_s'],samples=i-start,
                               observed_span_s=samples[i-1]['t_s']-samples[start]['t_s'],value=samples[start][key]))
            start=i
    return result


def past_residual(c,now,seconds,frozen):
    if seconds not in (10,30):raise ValueError('fixed diagnostic periods only')
    power=r.available(c['power_observations'],now)
    if not power:raise ValueError('missing past power')
    latest=max(power,key=lambda x:x['t']);end=latest['t'];start=now-seconds
    if start<0 or now-end>2.5 or end-start<5:raise ValueError('past window not eligible')
    observations=dict(power_t=[x['t'] for x in power],power_w=[x['value'] for x in power])
    observed=r.h.m.integral(observations,start,end);expected=c['pre_w']*(end-start)+r.state_energy(c,frozen,start,end)
    return dict(residual_w=(observed-expected)/(end-start),observed_mean_w=observed/(end-start),
                start_s=start,end_s=end,latest_available_s=latest['available'],seconds=seconds)


def diagnose(output):
    output=Path(output)
    if output.exists():raise FileExistsError('new diagnostic output required')
    output.mkdir(parents=True);cases=r.h.m.read(r.BUNDLE/'inputs.json.gz');frozen=r.h.m.read(r.h.m.MODEL)
    contract=r.h.m.read(BUNDLE/'contract.json')
    if any(r.h.m.sha(r.h.m.ROOT/p)!=h for p,h in contract['source_hashes'].items()):raise ValueError('registered source identity')
    raw=csv_rows(BUNDLE/'electrical_samples.csv')
    for row in raw:
        for key in ('t_s','available_s','current_raw','voltage_mv','watts'):row[key]=float(row[key])
        if abs(row['watts']+row['current_raw']*row['voltage_mv']/1e6)>1e-12:raise ValueError('unit reproduction')
    telemetry=[];holds=[];residuals=[];features=[];sessions=[]
    for c in cases:
        samples=sorted([x for x in raw if x['id']==c['id'] and 0<=x['t_s']<=120],key=lambda x:x['t_s'])
        intervals=np.diff([x['t_s'] for x in samples])
        if len(samples)<100 or not np.all(intervals>0):raise ValueError('sample coverage/order')
        current_runs=runs(samples,'current_raw');power_runs=runs(samples,'watts')
        change_times=[samples[i]['t_s'] for i in range(1,len(samples)) if samples[i]['current_raw']!=samples[i-1]['current_raw']]
        telemetry.append(dict(id=c['id'],block=c['block'],role=c['role'],samples=len(samples),sample_median_s=float(np.median(intervals)),
                              sample_p95_s=float(np.quantile(intervals,.95)),sample_max_gap_s=float(max(intervals)),
                              current_repeat_pairs=sum(a['current_raw']==b['current_raw'] for a,b in zip(samples,samples[1:])),
                              voltage_repeat_pairs=sum(a['voltage_mv']==b['voltage_mv'] for a,b in zip(samples,samples[1:])),
                              power_repeat_pairs=sum(a['watts']==b['watts'] for a,b in zip(samples,samples[1:])),
                              voltage_only_power_changes=sum(a['current_raw']==b['current_raw'] and a['voltage_mv']!=b['voltage_mv'] for a,b in zip(samples,samples[1:])),
                              max_current_constant_observed_span_s=max(x['observed_span_s'] for x in current_runs),
                              current_recorded_change_median_s=float(np.median(np.diff(change_times))) if len(change_times)>1 else None,
                              hardware_refresh_period_s=None))
        holds.extend(dict(id=c['id'],block=c['block'],role=c['role'],**x,hardware_hold_certified=False) for x in current_runs)
        data=dict(power_t=[x['t'] for x in c['power_observations']],power_w=[x['value'] for x in c['power_observations']])
        residual=[]
        for start in range(35,120,5):
            obs=r.h.m.integral(data,start,start+5);expected=c['pre_w']*5+r.state_energy(c,frozen,start,start+5)
            value=(obs-expected)/5;residual.append(value)
            residuals.append(dict(id=c['id'],block=c['block'],role=c['role'],start_s=start,end_s=start+5,residual_w=value,
                                  segment_type=r.classify(c,start,start+5)))
        local=[]
        for now in range(35,106,10):
            before={n:past_residual(c,now,n,frozen) for n in (10,30)}
            future=(r.h.m.integral(data,now,now+10)-(c['pre_w']*10+r.state_energy(c,frozen,now,now+10)))/10
            row=dict(id=c['id'],block=c['block'],role=c['role'],gap=c['gap'],policy=c['policy'],start_s=now,end_s=now+10,
                     past10_residual_w=before[10]['residual_w'],past30_residual_w=before[30]['residual_w'],
                     past30_start_s=before[30]['start_s'],past30_end_s=before[30]['end_s'],past_available_s=before[30]['latest_available_s'],
                     future_residual_w=future,observed_j=r.h.m.integral(data,now,now+10),base_j=c['pre_w']*10+r.state_energy(c,frozen,now,now+10),
                     future_observation_input=False)
            features.append(row);local.append(row)
        sessions.append(dict(id=c['id'],block=c['block'],role=c['role'],mean5s_residual_w=float(np.mean(residual)),
                             within_session_residual_sd_w=float(np.std(residual,ddof=1)),residual_lag5s_corr=correlation(residual[:-1],residual[1:]),
                             residual_lag10s_corr=correlation(residual[:-2],residual[2:]),
                             past10_sd_w=float(np.std([x['past10_residual_w'] for x in local],ddof=1)),
                             past30_sd_w=float(np.std([x['past30_residual_w'] for x in local],ddof=1)),
                             within_session_past10_future_corr=correlation([x['past10_residual_w'] for x in local],[x['future_residual_w'] for x in local]),
                             within_session_past30_future_corr=correlation([x['past30_residual_w'] for x in local],[x['future_residual_w'] for x in local])))
    groups=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        use=[x for x in features if x['block']==block and x['role']==role];ss=[x for x in sessions if x['block']==block and x['role']==role]
        groups.append(dict(block=block,role=role,n=len(ss),windows=len(use),
                           descriptive_past10_future_corr=correlation([x['past10_residual_w'] for x in use],[x['future_residual_w'] for x in use]),
                           descriptive_past30_future_corr=correlation([x['past30_residual_w'] for x in use],[x['future_residual_w'] for x in use]),
                           mean_past10_sd_w=float(np.mean([x['past10_sd_w'] for x in ss])),mean_past30_sd_w=float(np.mean([x['past30_sd_w'] for x in ss])),
                           between_session_mean_residual_sd_w=float(np.std([x['mean5s_residual_w'] for x in ss],ddof=1)),
                           mean_within_session_residual_sd_w=float(np.mean([x['within_session_residual_sd_w'] for x in ss])),
                           independent_unit='session; pooled correlations descriptive, not independent-window evidence'))
    dev=next(x for x in groups if x['role']=='development')
    evidence=dev['descriptive_past30_future_corr'] is not None and dev['descriptive_past30_future_corr']>max(0.,dev['descriptive_past10_future_corr'])
    for name,rows in [('telemetry.csv',telemetry),('current_holds.csv',holds),('residual_5s.csv',residuals),('past_features.csv',features),('sessions.csv',sessions),('groups.csv',groups)]:r.h.m.table(output/name,rows)
    r.h.m.write(output/'summary.json',dict(status='diagnostic_complete',candidate30_evidence=bool(evidence),evidence_gate_uses='development descriptive association only',
        candidate_fitted=False,sessions=20,past_feature_rows=len(features),hardware_refresh_period_s=None,physical_cause=None,
        model_sha256=r.h.m.sha(r.h.m.MODEL),device_commands=0,rl_training=0,policy_simulations=0,posthoc=True,accuracy_pass=None,experiment_ready=False))
    print(json.dumps(r.h.m.read(output/'summary.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);diagnose(p.parse_args().output)
