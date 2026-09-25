"""Prospective operational comparison, not equal-initial-temperature calibration.

PC-only rules shared by preparation, host and tests. No device commands.
"""
import math

VERSION = 'resident-fixed-preparation-v1'
EXPERIMENT = 'ENERGY-OPERATIONAL-PAIR-01'
PREPARATION = dict(version=VERSION, max_wait_seconds=360, fixed_seconds=120,
    min_samples=20, max_sample_gap_seconds=10, max_sample_uncertainty_seconds=2,
    sensor='AP', thermal_equilibrium_claim=False,
    basis='fixed observation exposure, not a cooling-to-target or equilibrium guarantee')
ORDER = [('development', 'CC_DG', 'serial'), ('development', 'CC_DG', 'parallel'),
         ('confirmation', 'CC_DG', 'parallel'), ('confirmation', 'CC_DG', 'serial')]


def assess(samples, ready_ns, contract=PREPARATION):
    """No anchor, stable-window search, future readings or repeated baseline."""
    rows = [x for x in samples if x['mono_ns'] >= ready_ns]
    if not rows:
        return dict(ready=False, reason='no_readings')
    for x in rows:
        try:
            valid = (math.isfinite(float(x['AP'])) and x['thermal_status'] == '0'
                     and 0 <= x['sampling_uncertainty_ns'] <= contract['max_sample_uncertainty_seconds'] * 1e9)
        except (ValueError, TypeError, KeyError):
            valid = False
        if not valid:
            return dict(ready=False, reason='invalid_sensor_or_thermal')
    gaps = [(b['mono_ns']-a['mono_ns'])/1e9 for a,b in zip(rows,rows[1:])]
    if any(x <= 0 or x > contract['max_sample_gap_seconds'] for x in gaps):
        return dict(ready=False, reason='invalid_sensor_or_thermal')
    if (rows[0]['mono_ns']-ready_ns)/1e9 > contract['max_sample_gap_seconds']:
        return dict(ready=False, reason='invalid_sensor_or_thermal')
    elapsed = (rows[-1]['mono_ns']-ready_ns)/1e9
    if elapsed >= contract['max_wait_seconds']-10:
        return dict(ready=False, reason='preparation_deadline', elapsed_s=elapsed)
    return dict(ready=elapsed >= contract['fixed_seconds'] and len(rows) >= contract['min_samples'],
                reason='fixed_exposure_not_equilibrium', elapsed_s=elapsed,
                samples=len(rows), thermal_equilibrium_claim=False)


def probe_specs(operational, mode):
    return ([('eligibility_serial_probe', 'serial'), ('eligibility_parallel_probe', 'parallel')]
            if operational else [('eligibility_probe', mode)])


def budget(base):
    return dict(base, sessions=4, development=2, confirmation=2, work_requests=3480,
                eligibility_requests=16, diagnostic_requests=3496, warmup=32,
                explicit_inference=3528, runtime_creations=16, total_seconds=8640,
                launch_seconds=20,validation_slack_seconds=35)


def reserve_summary(b):
    assert b['total_seconds'] == b['installation_seconds'] + b['sessions']*b['session_seconds'] + b['freeze_seconds']
    return dict(fixed_observation_seconds=4*(120+120+480+180),
                nested_timeout_reservation_seconds=600+4*(120+20+1580+60+45)+600,
                hard_seconds=b['total_seconds'], normal_duration_seconds=None,
                battery_completion_guaranteed=False)
