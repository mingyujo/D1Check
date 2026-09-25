"""COLLECT-05 resident AP preparation gate; no device access or post-hoc baseline selection."""
import statistics

PREPARATION = dict(version='resident-ap-preparation-v1', max_wait_seconds=360,
    window_seconds=60, min_samples=20, max_sample_gap_seconds=10,
    max_sample_uncertainty_seconds=2, max_window_range_c=0.3,
    paired_window_median_margin_c=0.25, sensor='AP',
    basis='HAL AP, quantized 0.1 C in COLLECT-04; thresholds are prospective PC design, not validated stability')

def expired(now_ns, ready_ns, contract=PREPARATION):
    # Stop before the app's own 360-second arm timeout to preserve failure evidence.
    return now_ns-ready_ns >= (contract['max_wait_seconds']-10)*1_000_000_000

def assess(samples, ready_ns, anchor_c, contract=PREPARATION):
    """Use only completed readings after ready; caller supplies no future readings."""
    if not samples:
        return dict(ready=False, reason='no_readings')
    now=samples[-1]['mono_ns']; start=max(ready_ns,now-int(contract['window_seconds']*1e9))
    rows=[x for x in samples if start<=x['mono_ns']<=now]
    if now-ready_ns<int(contract['window_seconds']*1e9) or len(rows)<contract['min_samples']:
        return dict(ready=False, reason='insufficient_window', samples=len(rows))
    if rows[-1]['mono_ns']-rows[0]['mono_ns']<int((contract['window_seconds']-5)*1e9):
        return dict(ready=False, reason='incomplete_window', samples=len(rows))
    if any(x.get('thermal_status')!='0' or x.get('AP','')=='' or
           x.get('sampling_uncertainty_ns',10**20)>contract['max_sample_uncertainty_seconds']*1e9 for x in rows):
        return dict(ready=False, reason='invalid_sensor_or_thermal', samples=len(rows))
    if any(b['mono_ns']<=a['mono_ns'] or b['mono_ns']-a['mono_ns']>contract['max_sample_gap_seconds']*1e9
           for a,b in zip(rows,rows[1:])):
        return dict(ready=False, reason='sample_gap', samples=len(rows))
    values=[float(x['AP']) for x in rows]
    median=statistics.median(values); span=max(values)-min(values)
    out=dict(ready=False, reason='unstable', samples=len(rows),
             start_ns=rows[0]['mono_ns'], end_ns=rows[-1]['mono_ns'],
             median_c=median, range_c=span, anchor_c=anchor_c)
    if span>contract['max_window_range_c']+1e-9:return out
    if anchor_c is not None and abs(median-anchor_c)>contract['paired_window_median_margin_c']+1e-9:
        out['reason']='off_anchor';return out
    out.update(ready=True,reason='stable_window_before_one_official_baseline')
    return out
