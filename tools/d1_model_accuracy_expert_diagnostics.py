"""Reproduce expert-review component/pre-initialization arithmetic; no new fit/device."""
import argparse
import csv
import math
from pathlib import Path

from tools import d1_energy_ap_joint_followup as e


def read_csv(path):
    with Path(path).open(encoding='utf8', newline='') as f:
        return list(csv.DictReader(f))


def orient_policy_pair(first, second):
    pair={first['policy']:first['session'],second['policy']:second['session']}
    if set(pair)!={'CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1'}:
        raise ValueError('registered CPU/PAR pair required')
    return pair['CPU_URGENT_ONLINE_V1'],pair['B2_PARALLEL_ONLINE_V1']


def component_diagnostic(candidate_j, idle_bias_w, pre50_w, pre20_w, lo, hi):
    """Keep the historical prefix through t=35; change only the future component."""
    if not all(math.isfinite(x) for x in (candidate_j,idle_bias_w,pre50_w,pre20_w,lo,hi)) or not 0 <= lo < hi:
        raise ValueError('invalid diagnostic window/value')
    duration=max(0.,hi-35)-max(0.,lo-35)
    no_offset=candidate_j-idle_bias_w*duration
    return no_offset,no_offset+(pre20_w-pre50_w)*duration


def run(output):
    e.validate_sources()
    root=e.ROOT
    source=e.BUNDLE/'run_v1'
    candidate=e.analysis.j.m.read(source/'candidate.json')
    receipt=e.analysis.j.m.read(source/'fit_receipt.json')
    if e.scope_api.sha(source/'candidate.json') != receipt['candidate_sha256']:
        raise ValueError('energy candidate bytes changed')
    macro=e.analysis.j.m.read(e.scope_api.tail.s.INPUTS)
    archive,_=e.analysis.j.panel()
    long=e.analysis.j.m.read(root/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
    cases={c['id']:c for c in macro+archive+long}
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    result=[]
    for row in read_csv(source/'energy_errors.csv'):
        c=cases[row['session']]
        model=e.analysis.j.m.read(source/('fold_'+c['id']+'.json'))['model'] if row['stage']=='development_loso' else candidate
        lo,hi=float(row['lo_s']),float(row['hi_s'])
        recent=e.analysis.j.m.integral(c,10.,30.)/20.
        no_offset,recent_variant=component_diagnostic(float(row['candidate_j']),model['idle_bias_w'],c['pre_w'],recent,lo,hi)
        observed=float(row['observed_j']) if row['observed_j'] else None
        result.append(dict(session=c['id'],stage=row['stage'],phase=row['phase'],lo_s=lo,hi_s=hi,
            observed_j=observed,frozen_j=row['frozen_j'],offset_model_j=row['candidate_j'],
            fixed_p4_no_offset_j=no_offset,pre20_initialization_diagnostic_j=recent_variant,
            no_offset_signed_j=no_offset-observed if observed is not None else None,
            pre20_signed_j=recent_variant-observed if observed is not None else None,
            pre50_w=c['pre_w'],pre20_w=recent,fit_calls=0,
            interpretation='posthoc arithmetic,not constrained-p4 refit or prospective validation'))
    e.scope_api.tail.s.csv_write(out/'energy_component_diagnostics.csv',result)
    power=[]
    for c in macro+long:
        end=min(c['actual'][-1]['end_s'],c['power_t'][-1])
        windows=[('pre_early',-20.,0.),('pre_recent',10.,30.),('registered600',35.,635.),
                 ('first180_recovery',635.,min(815.,end)),('last180',end-180.,end)]
        if c['policy'] in ('C0_LONG','LOAD_A_LONG'):
            windows += [('review1200_1800',1200.,1800.),('review1800_2400',1800.,2400.),
                        ('review995_1175',995.,1175.),('review1735_1915',1735.,1915.)]
        for name,lo,hi in windows:
            coverage=e.observed.measured_energy(c,lo,hi)
            mean=coverage['full_energy_j']/(hi-lo) if coverage['full_energy_j'] is not None else None
            power.append(dict(session=c['id'],policy=c['policy'],window=name,lo_s=lo,hi_s=hi,
                pre50_w=c['pre_w'],mean_w=mean,residual_vs_pre50_w=mean-c['pre_w'] if mean is not None else None,
                **coverage,clock='canonical model clock;load onset35s'))
    e.scope_api.tail.s.csv_write(out/'canonical_power_windows.csv',power)
    original=e.analysis.j.m.read(e.analysis.j.m.MODEL)
    AP_model=e.analysis.j.m.read(root/'docs/results/ap_tail_identification_01/run_v2/candidates.json')['LOAD_SLOW']
    ap=[]
    for c in long:
        full,parts=e.scope_api.tail.predict(c,original,AP_model)
        fast=[a+b for a,b in zip(parts['initial_path_c'],parts['fast_path_c'])]
        old=e.analysis.j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]
        spans=[('registered600',35.,635.),('recovery',635.,c['actual'][-1]['end_s'])]
        if c['last_lane_s'] is not None:spans.append(('work_present',35.,c['last_lane_s']))
        matched_lo=max(35.,c['q'][0],c['power_t'][0])
        matched_hi=min(c['q'][-1],c['power_t'][-1],c['actual'][-1]['end_s'])
        spans.append(('common_AP_power_observation',matched_lo,matched_hi))
        for phase,lo,hi in spans:
            for name,pred in [('FROZEN',old),('LOAD_SLOW_full',full),('fixed_fast_without_slow',fast)]:
                score=e.observed.phase_score(c,pred,lo,hi)
                ap.append(dict(session=c['id'],phase=phase,lo_s=lo,hi_s=hi,variant=name,
                    **score,fit_calls=0,interpretation='fixed component decomposition,not independent new candidate'))
        cov=e.observed.measured_energy(c,matched_lo,matched_hi)
        old_j=e.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),matched_hi)-e.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),matched_lo)
        no_offset_j=e.prediction(dict(pre_w=c['pre_w'],actual=c['actual']),dict(candidate,idle_bias_w=0.),matched_lo,matched_hi)
        e.scope_api.tail.s.write(out/(c['policy']+'_matched_window.json'),dict(lo_s=matched_lo,hi_s=matched_hi,
            energy_coverage=cov,original_energy_j=old_j,fixed_p4_no_offset_energy_j=no_offset_j,
            original_AP=e.observed.phase_score(c,old,matched_lo,matched_hi),
            fixed_AP=e.observed.phase_score(c,full,matched_lo,matched_hi),
            prediction_layer='actual_schedule_conditional',new_fit_calls=0,strict_support=False,
            prospective_confirmation=False))
    e.scope_api.tail.s.csv_write(out/'AP_component_diagnostics.csv',ap)
    pairs=[]
    cached=read_csv(source/'energy_errors.csv')
    source_pairs=read_csv(root/'docs/results/model_refinement_01/paired_errors.csv')
    for n in range(4):
        first,second=['sustained_'+str(2*n+i) for i in (0,1)]
        new={r['session']:r for r in result if r['phase']=='reference120'}
        metadata={r['session']:r for r in cached if r['phase']=='reference120'}
        a,b=orient_policy_pair(metadata[first],metadata[second])
        original_pair=next(r for r in source_pairs if r['pair']==str(n) and r['mode']=='A_conditional' and r['candidate']=='FROZEN')
        measured=float(original_pair['observed_delta_j'])
        if abs(float(new[b]['observed_j'])-float(new[a]['observed_j'])-measured)>1e-7:
            raise ValueError('observed policy orientation differs from stored pair')
        pred=float(new[b]['fixed_p4_no_offset_j'])-float(new[a]['fixed_p4_no_offset_j'])
        recent=float(new[b]['pre20_initialization_diagnostic_j'])-float(new[a]['pre20_initialization_diagnostic_j'])
        pairs.append(dict(pair=n,baseline_session=a,parallel_session=b,
            original_predicted_delta_j=original_pair['predicted_delta_j'],observed_delta_j=measured,
            fixed_p4_no_offset_delta_j=pred,pre20_diagnostic_delta_j=recent,
            no_offset_delta_error_j=pred-measured,pre20_delta_error_j=recent-measured,
            no_offset_sign_wrong=pred*measured<0,pre20_sign_wrong=recent*measured<0,
            fixed_initial_counterfactual_not_same_as_separate_recorded_sessions=True))
    e.scope_api.tail.s.csv_write(out/'paired_difference_diagnostics.csv',pairs)
    summary=[]
    for stage in ('development_loso','archive_posthoc','seen_long_posthoc_energy'):
        use=[r for r in result if r['stage']==stage and r['phase']=='reference120' and r['observed_j'] is not None]
        summary.append(dict(stage=stage,sessions=len(use),
            original_abs_J_mean=sum(abs(float(r['frozen_j'])-r['observed_j']) for r in use)/len(use),
            no_offset_abs_J_mean=sum(abs(r['no_offset_signed_j']) for r in use)/len(use),
            pre20_abs_J_mean=sum(abs(r['pre20_signed_j']) for r in use)/len(use),
            no_offset_worse=sum(abs(r['no_offset_signed_j'])>abs(float(r['frozen_j'])-r['observed_j'])+1e-9 for r in use),
            pre20_worse=sum(abs(r['pre20_signed_j'])>abs(float(r['frozen_j'])-r['observed_j'])+1e-9 for r in use)))
    e.scope_api.tail.s.write(out/'summary.json',dict(groups=summary,new_model_fits=0,
        numerical_fixed_AP_replays=2,policy_simulator_runs=0,device_commands=0,
        candidate_adoption=False,source_registration_verified=True))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    print(run(args.output))
