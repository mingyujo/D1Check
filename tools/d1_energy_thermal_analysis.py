"""Reproducible legacy data reanalysis, ENERGY-THERMAL-PC-01. No ADB.

Blocks 1..3 fit; 4..5 retrospective internal check. Source data already inspected.
Unit candidates 1/1000 uA per raw, never a freely fitted scale coefficient.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

import numpy as np

from tools import d1_energy_thermal as core

VERSION = 'energy-thermal-analysis-v1'
SENSORS = ('AP','BAT','PA','SKIN')
METHOD = dict(version=VERSION, fit_blocks=[1,2,3], internal_check_blocks=[4,5],
    split_role='post-hoc internal session/block check, not independent validation',
    current_candidates_ua_per_raw=[1,1000], selected_hypothesis={'A24':1000,'S26':1},
    max_power_gap_s=2.5, counter_window_s=[60,120],
    tau_grid_s=np.geomspace(1,1200,90).tolist(),
    identification='diagnostic only: profile SSE <= 1.05 min (floor 1e-9); band ratio <=4, not grid edge; median range >=0.3 C',
    thermal='state-based equilibrium relative to per-session baseline median, not ambient',
    limits=['no absolute energy accuracy certification','no current two-model measured power',
            'no resident idle transfer','no parallel power addition','no high-temperature throttle curve'])


def write_json(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def write_csv(path, rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)


class Source:
    def __init__(self, path, device):
        self.path=Path(path);self.device=device;self.z=zipfile.ZipFile(path) if self.path.is_file() else None
        self.inventory={}

    def read(self, tail):
        if self.z:
            # Explicit canonical archive locations, not duplicated reference exports.
            tail=tail.replace('runs/','02_runs/',1) if tail.startswith('runs/') else tail
            if tail.startswith('exports-v2/'):tail='12_'+tail
            if tail=='experiment_manifest.json':tail='01_experiment_manifest/'+tail
            ns=[n for n in self.z.namelist() if n.endswith('/'+tail)]
            core.require(len(ns)==1,'ambiguous/missing source '+tail)
            data=self.z.read(ns[0]);identity=ns[0]
        else:
            data=(self.path/tail).read_bytes();identity=tail
        self.inventory[identity]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        return data.decode('utf-8-sig')

    def json(self, tail):return json.loads(self.read(tail))

    def load(self):
        manifest=self.json('experiment_manifest.json')
        summaries=list(csv.DictReader(io.StringIO(self.read('exports-v2/run_summary.csv'))))
        thermal=list(csv.DictReader(io.StringIO(self.read('exports-v2/thermal_timeseries.csv'))))
        runs=[]
        for row in summaries:
            rid=row['run_id'];prefix=f'runs/{rid}/'
            summary=self.json(prefix+'merged/summary.json')
            raw=self.read(prefix+'raw/logcat.jsonl')
            samples=[json.loads(l) for l in raw.splitlines() if '"source":"d1check"' in l and '"event":"sample"' in l]
            samples,duplicates=core.canonical_samples(samples)
            core.require(len({s.get('boot_id') for s in samples})==1, 'mixed boot clock')
            # Read the merged event source once; non-inference lifecycle records only.
            text=self.read(prefix+'merged/events.jsonl')
            events=[json.loads(l) for l in text.splitlines() if '"source":"gpu"' in l and '"event":"inference"' not in l]
            metadata=next(e for e in events if e.get('event')=='run_metadata')
            events=[e for e in events if e.get('event') not in ('run_metadata','file_summary')]
            def at(name):return next(e['mono_ns'] for e in events if e.get('event')==name)
            warm=[e for e in events if e.get('event')=='warmup']
            wstart=min(e['start_mono_ns'] for e in warm);wend=max(e['mono_ns'] for e in warm)
            shutdown=max((e['mono_ns'] for e in events if e.get('event')=='shutdown'),default=summary['load_end_mono_ns'])
            boundaries=[('pre_baseline',summary['run_start_mono_ns']),('baseline',at('baseline_start')),
                        ('setup',at('baseline_end')),('warmup',wstart),('ready',wend),
                        ('load',summary['load_start_mono_ns']),('shutdown',summary['load_end_mono_ns']),
                        ('cooling',shutdown),('end',summary['run_stop_mono_ns'])]
            core.require(all(a[1]<=b[1] for a,b in zip(boundaries,boundaries[1:])), 'phase order')
            phases={a[0]:(a[1],b[1]) for a,b in zip(boundaries,boundaries[1:])}
            tr=[]
            for t in thermal:
                if t['run_id']!=rid:continue
                tr.append(dict(mono_ns=int(t['mono_ns']),phase=t['phase'],
                    sampling_uncertainty_ns=int(t['sampling_uncertainty_ns']),
                    thermal_status=int(t['thermal_status']),**{s:float(t[s]) for s in SENSORS if t[s]}))
            tr,td=core.canonical_samples(tr)
            runs.append(dict(device=self.device,run_id=rid,condition=row['condition_id'],
                block=int(row['block']),backend=row['resource'],threads=row['cpu_threads'],
                duty=float(row['requested_duty_cycle_percent']),model=summary['model_id'],
                model_sha256=summary['model_sha256'],fingerprint=manifest['device']['fingerprint'],
                runtime_version=metadata.get('litert_version','unrecorded'),
                precision=metadata.get('precision','unrecorded'),
                protocol='legacy formal v2 tensor-only',completed=int(row['completed_inference_count']),
                latency_ms=float(row['latency_median_ms']),samples=samples,thermal=tr,phases=phases,
                duplicate_samples=duplicates,duplicate_thermal=td))
        return runs


def identity(r):
    return {k:r[k] for k in ('device','run_id','condition','block','backend','threads','duty','model','model_sha256','fingerprint','protocol','runtime_version','precision')}


def counter_checks(r):
    ss=r['samples'];windows=[('whole',ss[0]['mono_ns'],ss[-1]['mono_ns'])]
    for duration in METHOD['counter_window_s']:
        step=int(duration*1e9);lo=ss[0]['mono_ns']
        while lo+step<=ss[-1]['mono_ns']:
            windows.append((str(duration),lo,lo+step));lo+=step
    rows=[]
    for label,lo,hi in windows:
        s=[x for x in ss if lo<=x['mono_ns']<=hi]
        if len(s)<2:continue
        valid=all(x.get('charge_valid') is True and x.get('charge_counter_raw',-1)>0
                  and core.discharge_w(x,1) is not None for x in s)
        delta=s[0].get('charge_counter_raw',0)-s[-1].get('charge_counter_raw',0)
        dt=(s[-1]['mono_ns']-s[0]['mono_ns'])/1e9
        maxgap=max((b['mono_ns']-a['mono_ns'])/1e9 for a,b in zip(s,s[1:]))
        valid=valid and delta>0 and maxgap<=METHOD['max_power_gap_s']
        integral=sum(-(a['current_raw']+b['current_raw'])/2*(b['mono_ns']-a['mono_ns'])/1e9/3600 for a,b in zip(s,s[1:])) if valid else None
        qstep=4000 if r['device']=='A24' else 4275
        for scale in (1,1000):
            rows.append(dict(**identity(r),window=label,start_ns=s[0]['mono_ns'],end_ns=s[-1]['mono_ns'],
                elapsed_s=dt,scale_ua_per_raw=scale,counter_delta_assuming_uah=delta,
                integrated_current_uah=integral*scale if integral is not None else None,
                ratio=integral*scale/delta if integral is not None else None,
                counter_steps=delta/qstep,endpoint_one_step_relative=qstep/delta if delta>0 else None,
                usable=valid,note='counter quantization/update delay; same fuel gauge, not independent truth'))
    return rows


def extract(r):
    power=[];energy=[];scale=METHOD['selected_hypothesis'][r['device']]
    for s in r['samples']:
        phase=next((p for p,(a,b) in r['phases'].items() if a<=s['mono_ns']<b),'outside')
        core.require(s['run_id']==r['run_id'],'sample session mismatch')
        power.append(dict(identity(r),**s,phase=phase,
            current_ua_hypothesis=s['current_raw']*scale,
            power_w_conditional=core.discharge_w(s,scale),scale_ua_per_raw=scale))
    baseline=core.integrate(r['samples'],*r['phases']['baseline'],scale)
    for phase,(a,b) in r['phases'].items():
        v=core.integrate(r['samples'],a,b,scale,METHOD['max_power_gap_s'])
        e=v['full_energy_j'];bp=baseline['mean_power_w']
        extra=e-bp*v['duration_s'] if e is not None and bp is not None and baseline['missing_s']<1e-6 else None
        energy.append(dict(**identity(r),phase=phase,start_ns=a,end_ns=b,**v,
            incremental_vs_pre_runtime_baseline_j=extra,
            completed_load_inferences=r['completed'] if phase=='load' else None,
            total_j_per_completed=e/r['completed'] if phase=='load' and e is not None else None,
            incremental_j_per_completed=extra/r['completed'] if phase=='load' and extra is not None else None,
            unit_status='conditional likely scale; absolute accuracy not certified'))
    return power,energy


def series(r,sensor,phase):
    a,b=r['phases'][phase]
    points=[x for x in r['thermal'] if a<=x['mono_ns']<=b and sensor in x]
    baseline=[x[sensor] for x in r['thermal'] if r['phases']['baseline'][0]<=x['mono_ns']<r['phases']['baseline'][1] and sensor in x]
    if len(points)<3 or not baseline:return None
    ts=np.array([(p['mono_ns']-points[0]['mono_ns'])/1e9 for p in points]);ys=np.array([p[sensor] for p in points])
    return dict(t=ts,y=ys,base=statistics.median(baseline),run=r,phase=phase,sensor=sensor)


def fit_phase(data):
    """Equal session weight least squares; profile range is NOT a confidence interval."""
    candidates=[]
    for tau in METHOD['tau_grid_s']:
        numerator=denominator=0.
        for d in data:
            x=1-np.exp(-d['t']/tau)
            residual=d['y']-(d['base']+(d['y'][0]-d['base'])*np.exp(-d['t']/tau))
            numerator+=float(np.mean(x*residual));denominator+=float(np.mean(x*x))
        gain=numerator/denominator
        loss=statistics.mean(float(np.mean((predict(d,tau,gain)-d['y'])**2)) for d in data)
        candidates.append((loss,tau,gain))
    loss,tau,gain=min(candidates)
    near=[x[1] for x in candidates if x[0]<=loss*1.05+1e-9]
    signal=statistics.median(float(np.ptp(d['y'])) for d in data)
    identified=near[0]>METHOD['tau_grid_s'][0] and near[-1]<METHOD['tau_grid_s'][-1] and max(near)/min(near)<=4 and signal>=.3
    return dict(tau_s=tau,equilibrium_offset_from_baseline_c=gain,train_mse_c2=loss,
        profile_tau_low_s=min(near),profile_tau_high_s=max(near),median_signal_c=signal,
        identified=bool(identified),identification_is_diagnostic_not_pass=True)


def predict(d,tau,gain):
    equilibrium=d['base']+gain
    return equilibrium+(d['y'][0]-equilibrium)*np.exp(-d['t']/tau)


def analyze(a24,s26,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    write_json(out/'METHOD_FROZEN_BEFORE_FIT.json',METHOD)
    sources=[Source(a24,'A24'),Source(s26,'S26')];runs=[]
    for src in sources:runs+=src.load()
    power=[];energy=[];unit=[];thermal=[];coverage=[]
    for r in runs:
        p,e=extract(r);power+=p;energy+=e;unit+=counter_checks(r)
        thermal += [dict(**identity(r),**v) for v in r['thermal']]
        dt=[(b['mono_ns']-a['mono_ns'])/1e9 for a,b in zip(r['samples'],r['samples'][1:])]
        coverage.append(dict(**identity(r),samples=len(p),thermal_samples=len(r['thermal']),
            interval_median_s=statistics.median(dt),interval_max_s=max(dt),
            duplicates=r['duplicate_samples'],thermal_duplicates=r['duplicate_thermal'],
            invalid_power=sum(v['power_w_conditional'] is None for v in p)))
    fits=[];errors=[];curves=[];profiles=[]
    for device,condition in sorted({(r['device'],r['condition']) for r in runs}):
        rr=[r for r in runs if r['device']==device and r['condition']==condition]
        for sensor in SENSORS:
            fby={}
            for phase in ('load','cooling'):
                data=[series(r,sensor,phase) for r in rr];data=[d for d in data if d]
                train=[d for d in data if d['run']['block'] in METHOD['fit_blocks']]
                if len(train)<2:continue
                f=fit_phase(train);fby[phase]=f
                fits.append(dict(device=device,condition=condition,sensor=sensor,phase=phase,**f,
                    fit_sessions=len(train),check_sessions=len(data)-len(train)))
                for d in data:
                    pred=predict(d,f['tau_s'],f['equilibrium_offset_from_baseline_c']);resid=pred-d['y']
                    role='fit' if d['run']['block'] in METHOD['fit_blocks'] else 'internal_check'
                    lag=float(np.corrcoef(resid[:-1],resid[1:])[0,1]) if np.std(resid[:-1])>1e-12 and np.std(resid[1:])>1e-12 else None
                    errors.append(dict(**identity(d['run']),sensor=sensor,phase=phase,role=role,
                        samples=len(pred),mae_c=float(np.mean(abs(resid))),rmse_c=float(np.sqrt(np.mean(resid**2))),
                        max_abs_error_c=float(max(abs(resid))),residual_lag1=lag,
                        note='phase conditional prediction anchored at first observed temperature'))
                    curves += [dict(device=device,condition=condition,run_id=d['run']['run_id'],block=d['run']['block'],
                        sensor=sensor,phase=phase,role=role,t_s=float(t),observed_c=float(y),predicted_c=float(p)) for t,y,p in zip(d['t'],d['y'],pred)]
            if len(fby)==2:
                train=[r for r in rr if r['block'] in METHOD['fit_blocks']]
                base=statistics.median(series(r,sensor,'load')['base'] for r in train)
                states={}
                for phase,f in fby.items():
                    ee=[x for x in energy if x['device']==device and x['condition']==condition and x['phase']==phase and x['covered_s'] >= .95*x['duration_s'] and x['mean_power_w'] is not None]
                    if not ee:continue
                    temps=[x[sensor] for r in train for x in r['thermal'] if sensor in x]
                    states['legacy_'+phase]=dict(power_w=statistics.median(x['mean_power_w'] for x in ee),
                        power_scope='observed coverage >=95%; missing tails not integrated as measured energy',
                        max_observed_duration_s=max(x['duration_s'] for x in ee),identified=f['identified'],
                        thermal={sensor:dict(tau_s=f['tau_s'],equilibrium_c=base+f['equilibrium_offset_from_baseline_c'],
                            observed_min_c=min(temps),observed_max_c=max(temps))})
                profiles.append(dict(version=core.VERSION,device=device,model=rr[0]['model'],condition=condition,
                    fingerprint=rr[0]['fingerprint'],model_sha256=rr[0]['model_sha256'],sensors=[sensor],states=states,
                    evidence='legacy_mobilenet_conditional',unit_status='likely scale, absolute accuracy not certified',
                    source=dict(fit_run_ids=[r['run_id'] for r in train],method=VERSION),
                    limitations=['pre-runtime baseline and stopped-runner cooling, not resident idle','no arbitrary duty transfer']))
    for name,rows in [('power_samples',power),('thermal_samples',thermal),('coverage',coverage),('unit_windows',unit),('phase_energy',energy),('thermal_fit',fits),('thermal_errors',errors),('thermal_curves',curves)]:
        write_csv(out/(name+'.csv'),rows)
    write_json(out/'profiles.json',profiles)
    write_json(out/'provenance.json',dict(version=VERSION,sources=[dict(path=str(s.path),device=s.device,inputs=s.inventory) for s in sources],
        source_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(core.__file__)]}))
    overview=[]
    for dev in ('A24','S26'):
        ratios=[r['ratio'] for r in unit if r['device']==dev and r['window']=='whole' and r['scale_ua_per_raw']==METHOD['selected_hypothesis'][dev] and r['usable']]
        ee=[r for r in energy if r['device']==dev and r['phase']=='load'];ff=[f for f in fits if f['device']==dev]
        overview.append(dict(device=dev,sessions=sum(r['device']==dev for r in runs),samples=sum(r['device']==dev for r in power),
            thermal_samples=sum(r['device']==dev for r in thermal),likely_scale_ua=METHOD['selected_hypothesis'][dev],
            ratio_min=min(ratios),ratio_median=statistics.median(ratios),ratio_max=max(ratios),
            complete_load_energy=sum(r['full_energy_j'] is not None for r in ee),
            load_energy_min_j=min(r['covered_energy_j'] for r in ee),load_energy_max_j=max(r['covered_energy_j'] for r in ee),
            thermal_fits=len(ff),identified_fits=sum(f['identified'] for f in ff)))
    write_csv(out/'device_summary.csv',overview)
    plots(out,curves,energy,errors)
    write_json(out/'receipt.json',dict(status='PC_ANALYSIS_COMPLETED_CONDITIONAL_NOT_PERFORMANCE_PASS',version=VERSION,
        sessions=len(runs),unit_certified=False,experiment_ready=False,overview=overview,
        thermal_fits=len(fits),internal_check_sessions_per_condition=2))
    return overview


def plots(out,curves,energy,errors):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # Predeclared representative: alphabetical first condition, block 4, all sensors.
    for dev in ('A24','S26'):
        condition=min(c['condition'] for c in curves if c['device']==dev)
        fig,axes=plt.subplots(2,4,figsize=(14,6))
        for i,phase in enumerate(('load','cooling')):
            for j,sensor in enumerate(SENSORS):
                cc=[c for c in curves if c['device']==dev and c['condition']==condition and c['block']==4 and c['sensor']==sensor and c['phase']==phase]
                ax=axes[i,j];ax.plot([c['t_s'] for c in cc],[c['observed_c'] for c in cc],label='observed')
                ax.plot([c['t_s'] for c in cc],[c['predicted_c'] for c in cc],label='fit blocks 1-3',linestyle='--')
                ax.set(title=f'{sensor} {phase}',xlabel='phase-relative s',ylabel='HAL degrees C');ax.legend(fontsize=7)
        fig.suptitle(f'{dev} {condition}, block 4: post-hoc internal check; no CI / no PASS')
        fig.tight_layout();fig.savefig(out/f'{dev}_thermal.png',dpi=150);fig.savefig(out/f'{dev}_thermal.svg');plt.close(fig)
        fig,ax=plt.subplots(figsize=(11,4));conditions=sorted({r['condition'] for r in energy if r['device']==dev})
        for idx,cond in enumerate(conditions):
            ee=[r for r in energy if r['device']==dev and r['condition']==cond and r['phase']=='load' and r['total_j_per_completed'] is not None]
            ax.scatter([idx]*len(ee),[r['total_j_per_completed']*1000 for r in ee],color='tab:blue',s=15)
        ax.set_xticks(range(len(conditions)),conditions,rotation=60,ha='right');ax.set_ylabel('whole-device load mJ / completed inference')
        ax.set_title(f'{dev}: conditional unit scale; five sessions/cell; no CI; tensor-only MobileNet')
        fig.tight_layout();fig.savefig(out/f'{dev}_energy.png',dpi=150);fig.savefig(out/f'{dev}_energy.svg');plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--a24',required=True);p.add_argument('--s26',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(analyze(a.a24,a.s26,a.output),indent=2))


if __name__=='__main__':main()
