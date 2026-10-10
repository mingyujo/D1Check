"""Fixed-parameter arithmetic and C0 evaluation-only oracle AP; never a forecast."""
import argparse
import csv
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_conditioned_power as m


def observed_AP_mean(c,lo,hi):
    pairs=[(p['t'],p['ap']) for p in c['pre']]+list(zip(c['q'],c['ap']))
    points=sorted(set((float(t),float(y)) for t,y in pairs));times=np.array([p[0] for p in points]);values=np.array([p[1] for p in points])
    if len(times)<2 or np.any(np.diff(times)<=0) or not np.isfinite(values).all() or not times[0]<=lo<hi<=times[-1]:
        raise ValueError('observed AP coverage; no endpoint fill')
    for a,b in zip(times,times[1:]):
        if min(b,hi)>max(a,lo) and b-a>10:raise ValueError('observed AP gap')
    q=np.array([lo,*[float(t) for t in times if lo<t<hi],hi]);y=np.interp(q,times,values)
    return float(np.sum(np.diff(q)*(y[:-1]+y[1:])/2)/(hi-lo))


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);source=m.BUNDLE/'run_v1';m.assets(source)
    receipt=m.old.old.read(source/'fit_receipt.json')
    for key,h in receipt['model_hashes'].items():
        if m.old.old.sha(source/('candidate_'+key+'.json'))!=h:raise ValueError('candidate changed')
    errors=m.table(source/'energy_errors.csv');prior=m.table(m.old.BUNDLE/'readout_v1/fixed_head_errors.csv')
    original=m.old.old.read(m.old.old.prior.prior.old.analysis.j.m.MODEL);states=m.old.old.prior.prior.STATES
    constants={r['id']:r for r in m.old.old.history()};decomp=[];oracle=[];drift=[];powers=[];ranges=[]
    for p in m.public_cases(source):
        c=constants[p['id']];key=str(p['gap']) if p['role']=='development' else 'final'
        a=m.old.old.read(source/('candidate_MATCH_CPU_'+key+'.json'));b=m.old.old.read(source/('candidate_CPU_AP_'+key+'.json'))
        dt=85.;f=p['features'];forecast_mean=m.idle_integral(p['pre_init'],35,120)/dt
        CPUterm=(b['CPU_slope_W_per_core_s_per_s']-a['CPU_slope_W_per_core_s_per_s'])*(f['persistent_other_proxy']-f['pre_full_mean_other'])*dt
        APterm=b['AP_slope_W_per_C']*(forecast_mean-f['pre_mean_AP_c'])*dt
        for head,oldhead in [('original_frozen','original_frozen'),('zero_offset','existing_zero_offset')]:
            use={r['method']:r for r in errors if r['session']==p['id'] and r['head']==head and r['phase']=='future85'}
            values={r['method']:r for r in errors if r['session']==p['id'] and r['head']==head and r['phase']=='reference120'}
            for newname,oldname in [('P50','P50'),('PRIOR_FULL_CPU','FULL_CPU')]:
                old=next(r for r in prior if r['session']==p['id'] and r['head']==oldhead and r['initializer']==oldname and r['phase']=='reference120')
                assert abs(float(values[newname]['predicted_J'])-float(old['predicted_J']))<1e-12
            if use['CPU_AP']['predicted_J'] and use['MATCH_CPU']['predicted_J']:
                diff=float(use['CPU_AP']['predicted_J'])-float(use['MATCH_CPU']['predicted_J'])
                assert abs(diff-CPUterm-APterm)<1e-9
                decomp.append(dict(session=p['id'],role=p['role'],head=head,window_s='35..120',CPU_slope_shift_J=CPUterm,
                    forecast_AP_term_J=APterm,total_change_J=diff,pre_mean_AP_c=f['pre_mean_AP_c'],
                    forecast_idle_mean_AP_c=forecast_mean,future_AP_used=False))
            phases={phase:{r['method']:r for r in errors if r['session']==p['id'] and r['head']==head and r['phase']==phase}
                    for phase in ('future85','post_lane_idle','work_present')}
            for method in m.METHODS:
                future=phases['future85'][method];idle=phases['post_lane_idle'][method];work=phases['work_present'].get(method)
                if future['signed_J'] and idle['signed_J']:
                    parts=float(idle['signed_J'])+(float(work['signed_J']) if work and work['signed_J'] else 0.)
                    assert abs(float(future['signed_J'])-parts)<1e-9
        idle_start=max(35.,c['last_lane_s'] or 35.)
        cov=m.old.old.prior.prior.old.observed.measured_energy(c,idle_start,120.)
        idle_mean_power=cov['full_energy_j']/(120-idle_start) if cov['full_energy_j'] is not None else None
        const=f['pre_full_mean_W']+b['CPU_slope_W_per_core_s_per_s']*(f['persistent_other_proxy']-f['pre_full_mean_other'])-b['AP_slope_W_per_C']*f['pre_mean_AP_c']
        drift.append(dict(session=p['id'],role=p['role'],gap=p['gap'],policy=p['policy'],pre_mean_AP_c=f['pre_mean_AP_c'],
            predicted_idle_AP_at35_c=m.idle_AP(p['pre_init'],35.),predicted_idle_AP_at120_c=m.idle_AP(p['pre_init'],120.),
            predicted_idle_mean_AP_c=forecast_mean,pre_mean_W=f['pre_full_mean_W'],observed_post_lane_mean_W=idle_mean_power,
            predicted_mean_baseline_W=const+b['AP_slope_W_per_C']*forecast_mean,
            predicted_mean_baseline_window_s='35..120',observed_post_lane_start_s=idle_start,observed_post_lane_end_s=120.,
            predicted_matched_post_lane_mean_W=const+b['AP_slope_W_per_C']*m.idle_integral(p['pre_init'],idle_start,120.)/(120-idle_start),
            observed_post_lane_power_is_target_not_input=True))
        if p['id'].endswith('_C0'):
            obsAP=observed_AP_mean(c,35,120)
            e=next(r for r in errors if r['session']==p['id'] and r['head']=='original_frozen' and r['method']=='CPU_AP' and r['phase']=='future85')
            signed=float(e['signed_J']);replace=b['AP_slope_W_per_C']*(obsAP-forecast_mean)*dt
            obsAPterm=b['AP_slope_W_per_C']*(obsAP-f['pre_mean_AP_c'])*dt
            oracle.append(dict(session=p['id'],role=p['role'],gap=p['gap'],window_s='35..120',pre_mean_AP_c=f['pre_mean_AP_c'],
                predicted_idle_mean_AP_c=forecast_mean,observed_AP_mean_c=obsAP,AP_mean_forecast_error_c=forecast_mean-obsAP,
                forecast_AP_term_J=APterm,oracle_observed_AP_term_J=obsAPterm,AP_forecast_error_contribution_J=-replace,
                CPU_AP_future_signed_error_J=signed,oracle_AP_future_signed_error_J=signed+replace,
                forbidden_future_AP_substitution_for_diagnosis_only=True,new_forecast_or_candidate=False))
        for t in range(35,121):
            powers.append(dict(session=p['id'],role=p['role'],t_s=t,baseline_AP_term_W=b['AP_slope_W_per_C']*(m.idle_AP(p['pre_init'],t)-f['pre_mean_AP_c']),
                baseline_CPUterm_W=b['CPU_slope_W_per_core_s_per_s']*(f['persistent_other_proxy']-f['pre_full_mean_other']),
                baseline_total_W=m.baseline(p,b,t),idle_counterfactual_AP_c=m.idle_AP(p['pre_init'],t)))
        trained=[z for z in m.public_cases(source) if z['id'] in b['development_ids']]
        fields=('pre_mean_AP_c','pre_full_mean_W','pre_full_mean_other','persistent_other_proxy')
        outside=[k for k in fields if not min(z['features'][k] for z in trained)<=f[k]<=max(z['features'][k] for z in trained)]
        ranges.append(dict(session=p['id'],role=p['role'],outside_training_features=';'.join(outside),excluded=False,strict_support=False))
    for name,data in [('AP_CPU_arithmetic',decomp),('C0_oracle_attribution',oracle),('drift_and_baseline',drift),('component_paths',powers),('feature_ranges',ranges)]:
        m.old.old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),data)
    m.old.old.write(out/'receipt.json',dict(status='fixed_parameter_attribution_complete',contract_sha256=m.old.old.sha(m.BUNDLE/'attribution_contract.json'),
        old_predictions_reproduced=True,AP_CPU_arithmetic_tolerance_J=1e-9,partition_tolerance_J=1e-9,
        oracle_C0_controls=4,oracle_is_not_a_forecast=True,additional_fits=0,new_AP_initializations=0,device_commands=0,
        default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False))
    print(m.old.old.prior.prior.terminal_json(oracle))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
