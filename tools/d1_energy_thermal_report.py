"""Summaries and small demonstrations from existing extraction; no measurement or fit rerun."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np

from tools import d1_energy_thermal as e
from tools.d1_energy_thermal_analysis import Source,write_csv,write_json


def read(p):return list(csv.DictReader(p.open(encoding='utf-8')))


def summarize(root):
    root=Path(root)
    energy=read(root/'phase_energy.csv');unit=read(root/'unit_windows.csv')
    fits=read(root/'thermal_fit.csv');errors=read(root/'thermal_errors.csv')
    rows=[]
    for device in ('A24','S26'):
        for window in ('whole','60','120'):
            for scale in ('1','1000'):
                rr=[r for r in unit if r['device']==device and r['window']==window and r['scale_ua_per_raw']==scale and r['usable']=='True']
                vals=[float(r['ratio']) for r in rr]
                rows.append(dict(device=device,window_s=window,scale_ua_per_raw=scale,n=len(rr),
                    ratio_median=statistics.median(vals) if vals else None,ratio_min=min(vals) if vals else None,
                    ratio_max=max(vals) if vals else None,
                    sum_integral_over_sum_counter=sum(float(r['integrated_current_uah']) for r in rr)/sum(float(r['counter_delta_assuming_uah']) for r in rr) if rr else None,
                    windows_at_least_two_counter_steps=sum(float(r['counter_steps'])>=2 for r in rr),
                    absolute_accuracy_certified=False))
    write_csv(root/'unit_summary.csv',rows)
    summary=[]
    for dev,cond in sorted({(r['device'],r['condition']) for r in energy}):
        for phase in ('baseline','setup','warmup','load','cooling'):
            rr=[r for r in energy if r['device']==dev and r['condition']==cond and r['phase']==phase]
            row=dict(device=dev,condition=cond,phase=phase,sessions=len(rr))
            for key in ('mean_power_w','full_energy_j','total_j_per_completed','incremental_vs_pre_runtime_baseline_j','incremental_j_per_completed','missing_s'):
                v=[float(r[key]) for r in rr if r[key]!=''];row[key+'_n']=len(v);row[key+'_median']=statistics.median(v) if v else None
            summary.append(row)
    write_csv(root/'condition_energy_summary.csv',summary)
    # Existing run-level latency/temperature associations, five sessions/cell.
    # Never infer DVFS/thermal causation from this association.
    import io
    joined=[];associations=[]
    for source in json.loads((root/'provenance.json').read_text(encoding='utf-8'))['sources']:
        src=Source(source['path'],source['device'])
        for row in csv.DictReader(io.StringIO(src.read('exports-v2/run_summary.csv'))):
            er=next(r for r in energy if r['run_id']==row['run_id'] and r['device']==source['device'] and r['phase']=='load')
            joined.append(dict(device=source['device'],condition=row['condition_id'],run_id=row['run_id'],block=row['block'],
                latency_median_ms=float(row['latency_median_ms']),load_power_w=float(er['mean_power_w']),
                AP_start_c=float(row['ap_load_start_temperature_c']),AP_change_c=float(row['ap_load_change_c']),
                evidence='fixed-duty legacy association; not thermal causal slope'))
    for dev,cond in sorted({(r['device'],r['condition']) for r in joined}):
        rr=[r for r in joined if r['device']==dev and r['condition']==cond]
        for key in ('AP_start_c','AP_change_c','load_power_w'):
            x=[r[key] for r in rr];y=[r['latency_median_ms'] for r in rr]
            corr=float(np.corrcoef(x,y)[0,1]) if np.std(x)>1e-12 and np.std(y)>1e-12 else None
            associations.append(dict(device=dev,condition=cond,x=key,y='latency_median_ms',sessions=len(rr),pearson_r=corr,
                interpretation='exploratory within-condition association; no CI, no throttle model'))
    write_csv(root/'session_energy_temperature_latency.csv',joined)
    write_csv(root/'association_summary.csv',associations)
    rows=[]
    for dev in ('A24','S26'):
        for sensor in ('AP','BAT','PA','SKIN'):
            for phase in ('load','cooling'):
                rr=[r for r in errors if r['device']==dev and r['sensor']==sensor and r['phase']==phase and r['role']=='internal_check']
                ff=[r for r in fits if r['device']==dev and r['sensor']==sensor and r['phase']==phase]
                rows.append(dict(device=dev,sensor=sensor,phase=phase,check_sessions=len(rr),
                    median_session_mae_c=statistics.median(float(r['mae_c']) for r in rr),
                    worst_sample_abs_error_c=max(float(r['max_abs_error_c']) for r in rr),
                    median_session_rmse_c=statistics.median(float(r['rmse_c']) for r in rr),
                    identified_models=sum(r['identified']=='True' for r in ff),models=len(ff),
                    median_residual_lag1=statistics.median(float(r['residual_lag1']) for r in rr if r['residual_lag1']),
                    evidence='post-hoc internal check; phase-start anchored, not full open-loop prediction'))
    write_csv(root/'error_summary.csv',rows)
    # Stable numerical limits are not evidence for a long-time physical equilibrium.
    write_csv(root/'long_horizon_diagnostics.csv',[
        dict(device=f['device'],condition=f['condition'],sensor=f['sensor'],phase=f['phase'],
             tau_s=f['tau_s'],identified=f['identified'],
             equilibrium_offset_c=f['equilibrium_offset_from_baseline_c'],
             offset_at_600s_from_baseline_c=e.transition(0,float(f['equilibrium_offset_from_baseline_c']),float(f['tau_s']),600),
             role='numerical boundedness only; physical extrapolation unsupported') for f in fits])
    profiles=json.loads((root/'profiles.json').read_text(encoding='utf-8'))
    for p in profiles:
        p['supported_state_sequence']=['legacy_load','legacy_cooling']
        p['source']['analysis_provenance_sha256']=hashlib.sha256((root/'provenance.json').read_bytes()).hexdigest()
        # Rebuild state power from cached extraction; 1 Hz endpoint tails remain missing energy.
        # This repairs v2's initially omitted cooling states without rerunning the fits.
        sensor=p['sensors'][0]
        ff={f['phase']:f for f in fits if f['device']==p['device'] and f['condition']==p['condition'] and f['sensor']==sensor}
        load=p['states']['legacy_load']['thermal'][sensor]
        baseline=load['equilibrium_c']-float(ff['load']['equilibrium_offset_from_baseline_c'])
        for phase in ('load','cooling'):
            ee=[r for r in energy if r['device']==p['device'] and r['condition']==p['condition'] and r['phase']==phase and int(r['block'])<=3 and r['mean_power_w'] and float(r['covered_s'])>=.95*float(r['duration_s'])]
            if not ee:continue
            f=ff[phase]
            p['states']['legacy_'+phase]=dict(power_w=statistics.median(float(r['mean_power_w']) for r in ee),
                max_observed_duration_s=max(float(r['duration_s']) for r in ee),identified=f['identified']=='True',
                power_scope='observed coverage >=95%; missing tails not measured energy',
                thermal={sensor:dict(tau_s=float(f['tau_s']),equilibrium_c=baseline+float(f['equilibrium_offset_from_baseline_c']),
                    observed_min_c=load['observed_min_c'],observed_max_c=load['observed_max_c'])})
    write_json(root/'profiles_connected_v1.json',profiles)
    # Representative is fixed by alphabetical order and sensor AP, not low residual.
    demos=[]
    for dev in ('A24','S26'):
        p=next(p for p in profiles if p['device']==dev and p['sensors']==['AP'])
        source=p['source']['fit_run_ids'][0]
        ee=[r for r in energy if r['run_id']==source and r['phase'] in ('load','cooling')]
        segments=[];end=0.
        for phase in ('load','cooling'):
            row=next(r for r in ee if r['phase']==phase);duration=float(row['duration_s'])
            segments.append(dict(start_s=end,end_s=end+duration,state='legacy_'+phase));end+=duration
        thermal=read(root/'thermal_samples.csv');target=next(r for r in ee if r['phase']=='load')
        initial=next(float(r['AP']) for r in thermal if r['run_id']==source and int(r['mono_ns'])>=int(target['start_ns']))
        pp=copy.deepcopy(p);pp['recorded_schedule']=segments
        modeled=e.account(segments,pp,device=dev,model=p['model'],mode='observed_replay',
            scope={k:p[k] for k in ('fingerprint','model_sha256','condition')},
            initial_temperature={'AP':initial},planned=int(target['completed_load_inferences']),completed=int(target['completed_load_inferences']))
        modeled['recorded_covered_energy_j']=sum(float(r['covered_energy_j']) for r in ee if r['covered_energy_j'])
        modeled['recorded_missing_s']=sum(float(r['missing_s']) for r in ee)
        modeled['meaning']='state-model replay on recorded duration; not exact reconstruction of measured temperature/power'
        demos.append(modeled)
    write_json(root/'legacy_replay_demo.json',demos)
    # Partition conservation on predeclared representative raw sessions.
    raw=read(root/'power_samples.csv');checks=[]
    for dev in ('A24','S26'):
        rid=next(p for p in profiles if p['device']==dev)['source']['fit_run_ids'][0]
        ss=[dict(mono_ns=int(r['mono_ns']),current_raw=float(r['current_raw']),voltage_mV=float(r['voltage_mV']),
                 current_valid=r['current_valid']=='True',plugged=int(r['plugged'])) for r in raw if r['run_id']==rid and r['device']==dev]
        ee=[r for r in energy if r['run_id']==rid and r['device']==dev]
        whole=e.integrate(ss,min(int(r['start_ns']) for r in ee),max(int(r['end_ns']) for r in ee),1000 if dev=='A24' else 1)
        phased=sum(float(r['covered_energy_j']) for r in ee if r['covered_energy_j'])
        delta=abs(whole['covered_energy_j']-phased);e.require(delta<1e-6,'real-record phase energy double count')
        checks.append(dict(device=dev,run_id=rid,whole_covered_energy_j=whole['covered_energy_j'],phase_sum_j=phased,
            difference_j=delta,uncovered_s=whole['missing_s'],scope='arithmetic replay only'))
    write_json(root/'real_record_partition_check.json',checks)
    return rows


def engine_demo(root):
    # Synthetic fixed ns fixtures already used by the legacy engine tests; no calibration fit.
    from tools.test_d1_cal03_connection import fixture,request
    from tools.test_d1_arrival_explore import settings
    from tools import d1_arrival_explore as engine
    c,v=fixture();queries=[request(priority='normal'),request('u',arrival=31,ordinal=1)]
    result=engine.simulate(c,v,queries,policy='CPU_URGENT',settings=settings(),seed=7,horizon_ns=400)
    original=copy.deepcopy(result);segments=e.ledger_segments(result,400)
    states={s['state']:dict(power_w=1 if s['state']=='idle' else 4,
        thermal={'SKIN':dict(equilibrium_c=20 if s['state']=='idle' else 40,tau_s=10)}) for s in segments}
    p=dict(version=e.VERSION,device='synthetic',model='synthetic-two-model',sensors=['SKIN'],
        evidence='explicit_assumptions',unit_status='synthetic W',states=states,source='hand-check fixture; not empirical coefficients')
    out=e.account(segments,p,device=p['device'],model=p['model'],mode='assumption_exploration',
        initial_temperature={'SKIN':20},planned=2,completed=2,service_constraints_met=None)
    e.require(original==result,'legacy engine mutation')
    # Two occupied lanes serially for 140 ns and idle for 260 ns.
    e.require(abs(out['energy_j']-820e-9)<1e-18,'manual common-window energy')
    write_json(Path(root)/'engine_demo.json',dict(engine_result=result,energy_thermal=out,
        hand_expected_energy_j=820e-9,assumptions=p,legacy_output_unchanged=True))


def main():
    p=argparse.ArgumentParser();p.add_argument('--analysis',required=True);a=p.parse_args()
    summarize(a.analysis);engine_demo(a.analysis)
    print('summaries and bounded legacy/synthetic demonstrations complete; no performance PASS')


if __name__=='__main__':main()
