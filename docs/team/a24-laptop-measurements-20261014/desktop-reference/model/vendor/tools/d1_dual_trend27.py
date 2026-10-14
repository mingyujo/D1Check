"""Common, offset-invariant thermal trend scoring and bounded calibration.

Targets are used by offline fitting/scoring only. Prediction accepts a causal
initial state and current physical forcing, never a measured future curve.
"""
import math
import numpy as np
from tools.d1_s26_refine26_model import bounded_fit

VERSION='dual-device-thermal-trend-v27'
DEADBAND_C=.2
EDGE_WIDTH_S=5.

def phase_rows(times,windows):
    times=np.asarray(times,float);rows=[]
    for name,start,end in windows:
        if end-start<10:continue
        width=min(EDGE_WIDTH_S,(end-start)/3)
        left=np.flatnonzero((times>=start)&(times<=start+width))
        right=np.flatnonzero((times>=end-width)&(times<=end))
        if len(left)<2 or len(right)<2:continue
        v=np.zeros(len(times));v[left]-=1/len(left);v[right]+=1/len(right)
        elapsed=float(times[right].mean()-times[left].mean())
        if elapsed<=0:continue
        rows.append(dict(name=name,start_s=start,end_s=end,contrast=v,elapsed_s=elapsed,left_n=len(left),right_n=len(right)))
    return rows

def direction(value,deadband=DEADBAND_C):return 1 if value>deadband else -1 if value< -deadband else 0

def score(case,prediction,deadband=DEADBAND_C):
    times=np.asarray(case['times']);truth=np.asarray(case['truth']);pred=np.asarray(prediction)
    if pred.shape!=truth.shape or not np.isfinite(pred).all():raise ValueError('finite, identical query grid')
    deltas=[]
    for row in phase_rows(times,case['windows']):
        a=float(row['contrast']@truth);b=float(row['contrast']@pred)
        deltas.append(dict(phase=row['name'],window_s=[row['start_s'],row['end_s']],
            actual_delta_c=a,predicted_delta_c=b,absolute_delta_error_c=abs(a-b),
            actual_direction=direction(a,deadband),predicted_direction=direction(b,deadband),
            direction_match=direction(a,deadband)==direction(b,deadband),slope_error_c_per_min=abs(a-b)/row['elapsed_s']*60,
            relative_amplitude_error_percent=abs(a-b)/abs(a)*100 if abs(a)>=.5 else None,
            measured_edge_counts=[row['left_n'],row['right_n']]))
    # This centered diagnostic removes one additive level difference only;
    # no time warping or target-dependent shift enters prediction.
    centered=(pred-pred[0])-(truth-truth[0])
    return dict(identity=case['identity'],device=case['device'],cohort=case['cohort'],sensor=case['sensor'],
        kind=case['kind'],absolute_MAE_c=float(np.mean(abs(pred-truth))),centered_path_MAE_c=float(np.mean(abs(centered))),
        phase_rows=deltas,scorable_phases=len(deltas),unscorable_windows=len(case['windows'])-len(deltas),
        phase_delta_MAE_c=float(np.mean([r['absolute_delta_error_c']for r in deltas]))if deltas else None,
        direction_matches=sum(r['direction_match']for r in deltas),direction_cases=len(deltas),
        peak_time_difference_s=float(times[np.argmax(pred)]-times[np.argmax(truth)]),
        peak_rise_error_c=float((pred.max()-pred[0])-(truth.max()-truth[0])))

def aggregate(rows):
    usable=[r for r in rows if r['phase_delta_MAE_c']is not None]
    if not usable:raise ValueError('no observable trends')
    groups={r['cohort']for r in usable};macro=np.mean([np.mean([r['phase_delta_MAE_c']for r in usable if r['cohort']==g])for g in groups])
    direction_total=sum(r['direction_cases']for r in usable);matches=sum(r['direction_matches']for r in usable)
    slopes=[p['slope_error_c_per_min']for r in usable for p in r['phase_rows']]
    metrics=dict(cohort_equal_delta_MAE_c=float(macro),session_mean_delta_MAE_c=float(np.mean([r['phase_delta_MAE_c']for r in usable])),
        worst_session_delta_MAE_c=max(r['phase_delta_MAE_c']for r in usable),direction_matches=matches,direction_cases=direction_total,
        direction_rate=matches/direction_total,mean_slope_error_c_per_min=float(np.mean(slopes)),
        mean_absolute_MAE_c=float(np.mean([r['absolute_MAE_c']for r in rows])),mean_centered_path_MAE_c=float(np.mean([r['centered_path_MAE_c']for r in rows])),
        unscorable_windows=sum(r['unscorable_windows']for r in rows),evaluated_sessions=len(rows))
    value=metrics['cohort_equal_delta_MAE_c']+.25*metrics['worst_session_delta_MAE_c']+.25*(1-metrics['direction_rate'])+.1*metrics['mean_slope_error_c_per_min']
    return float(value),metrics

def fit(cases,prior,lower,upper,level_weight,ridge):
    groups={c['cohort']for c in cases};counts={g:sum(c['cohort']==g for c in cases)for g in groups};xs=[];ys=[]
    for case in cases:
        x=np.asarray(case['design']);y=np.asarray(case['truth'])-case['initial_c'];w=1/math.sqrt(len(groups)*counts[case['cohort']]);phases=phase_rows(case['times'],case['windows'])
        contrasts=[r['contrast']for r in phases]
        # Fixed20s local contrasts supply timing information. They use the
        # same5s edge means and are targets, never initialization inputs.
        first=case['times'][0];last=case['times'][-1]
        short=[('local',t,t+20)for t in np.arange(math.ceil(first/20)*20,last-20,20)]
        contrasts += [r['contrast']for r in phase_rows(case['times'],short)]
        if contrasts:
            c=np.stack(contrasts);xs.append(c@x*w/math.sqrt(len(contrasts)));ys.append(c@y*w/math.sqrt(len(contrasts)))
        if level_weight:
            xs.append(x*w*math.sqrt(level_weight/len(y)));ys.append(y*w*math.sqrt(level_weight/len(y)))
    if not xs:raise ValueError('no trend observations')
    x=np.concatenate(xs);y=np.concatenate(ys)
    result=bounded_fit(x,y,ridge,lower,upper,prior)
    return dict(coefficients=result.tolist(),level_weight=level_weight,ridge=ridge,rank=int(np.linalg.matrix_rank(x)),dimension=x.shape[1],
                objective='fixed phase and20s temperature contrasts; optional small absolute-level anchor',
                prior_conditional=True,new_independent_confirmation=False)
