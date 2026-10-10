"""One pre-event CPU baseline candidate. Offline, opt-in, no device/RL path."""
import argparse
import csv
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np
from tools import d1_session_contrast_cost as prior

ROOT = prior.ROOT
BUNDLE = ROOT / 'docs/results/cpu_prebaseline_01'
CLASSES = ('benchmark', 'tracer', 'idle', 'other', 'unknown')
ISSUE = 35.
END = 120.


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write(path, value):
    prior.prior.write(path, value)


def sha(path):
    return prior.prior.old.scope_api.sha(path)


def history():
    return [c for c in prior.cases() if c.get('block') == 'history']


def cpu_bins(path, origin_ns, left=-20, right=30, width=5):
    """Clip BOOTTIME slices; gaps/overlap/unknown do not become zero activity."""
    edges = list(range(left, right + 1, width))
    if edges[-1] != right or not left < right < ISSUE:
        raise ValueError('pre-event window')
    totals = [{k: 0 for k in CLASSES} for _ in edges[:-1]]
    coverage = [[0] * 8 for _ in totals]
    a0, b0 = origin_ns + left * 10**9, origin_ns + right * 10**9
    last = {}
    with Path(path).open(encoding='utf8', newline='') as f:
        rows = csv.DictReader(f)
        if not {'ts', 'dur', 'cpu', 'activity_class'} <= set(rows.fieldnames or []):
            raise ValueError('sched schema')
        for r in rows:
            a, dur, cpu, kind = int(r['ts']), int(r['dur']), int(r['cpu']), r['activity_class']
            if dur <= 0 or not 0 <= cpu < 8 or kind not in CLASSES:
                raise ValueError('invalid scheduler slice')
            b = a + dur
            if b <= a0 or a >= b0:
                continue
            if cpu in last and a < last[cpu]:
                raise ValueError('overlapping or unsorted CPU slices')
            last[cpu] = b
            first = max(0, (a - a0) // (width * 10**9))
            stop = min(len(totals), (b - 1 - a0) // (width * 10**9) + 1)
            for i in range(first, stop):
                n = max(0, min(b, origin_ns + edges[i+1]*10**9) - max(a, origin_ns + edges[i]*10**9))
                totals[i][kind] += n
                coverage[i][cpu] += n
    if any(any(n != width*10**9 for n in cpus) for cpus in coverage):
        raise ValueError('incomplete per-CPU coverage')
    if any(row['unknown'] for row in totals):
        raise ValueError('unknown process classification')
    return [dict(lo_s=edges[i], hi_s=edges[i+1],
                 other_rate_core_s_per_s=row['other']/1e9/width,
                 **{k+'_cpu_seconds': row[k]/1e9 for k in CLASSES})
            for i, row in enumerate(totals)]


def pre_power_bins(c, bins):
    # A right bracketing sample is allowed only before hypothetical issue35.
    t, w = np.asarray(c['power_t']), np.asarray(c['power_w'])
    if len(t) != len(w) or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError('power clock')
    rows = []
    for b in bins:
        lo, hi = b['lo_s'], b['hi_s']
        i = int(np.searchsorted(t, lo, side='right'))-1
        j = int(np.searchsorted(t, hi, side='left'))
        if i < 0 or j >= len(t) or t[j] >= ISSUE:
            raise ValueError('pre power bracket unavailable before issue')
        cov = prior.prior.old.observed.measured_energy(dict(power_t=t[i:j+1], power_w=w[i:j+1]), lo, hi)
        if cov['full_energy_j'] is None:
            raise ValueError('pre power gap; no filling')
        rows.append(dict(b, mean_power_W=cov['full_energy_j']/(hi-lo),
                         latest_power_event_s=float(t[j])))
    return rows


def feature(rows):
    if len(rows) != 10 or [r['lo_s'] for r in rows] != list(range(-20, 30, 5)):
        raise ValueError('fixed pre50 bins required')
    if any(r['latest_power_event_s'] >= ISSUE or r['hi_s'] > 30 for r in rows):
        raise ValueError('future event in pre input')
    rates = [r['other_rate_core_s_per_s'] for r in rows]
    if not all(math.isfinite(v) and 0 <= v <= 8 for v in rates):
        raise ValueError('invalid CPU feature')
    return dict(pre50_other_rate=float(np.mean(rates)), late20_other_rate=float(np.mean(rates[6:])),
                contrast_core_s_per_s=float(np.mean(rates[6:])-np.mean(rates)),
                event_cutoff_s=30., hypothetical_issue_s=ISSUE,
                export_available_live=False)


def fit(rows, registered_ids):
    ids = {r['session'] for r in rows}
    if len(ids) < 3 or not ids <= set(registered_ids) or any(r['role'] != 'development' for r in rows):
        raise ValueError('registered development sessions only')
    X, Y = [], []
    for identity in sorted(ids):
        use = [r for r in rows if r['session'] == identity]
        feature(use)
        x = np.array([r['other_rate_core_s_per_s'] for r in use])
        y = np.array([r['mean_power_W'] for r in use])
        if not np.isfinite(y).all():
            raise ValueError('missing pre power')
        X.extend((x-x.mean())/math.sqrt(len(use)*len(ids)))
        Y.extend((y-y.mean())/math.sqrt(len(use)*len(ids)))
    x, y = np.array(X), np.array(Y)
    information = float(x @ x)
    if information <= np.finfo(float).eps:
        raise ValueError('CPU slope not identified; no invented coefficient')
    unconstrained = float(x@y / information)
    b = max(0., unconstrained)
    return dict(version='pre-event-other-CPU-baseline-v1', slope_W_per_core_s_per_s=b,
                unconstrained_slope=unconstrained, information=information,
                development_ids=sorted(ids), session_count=len(ids), pre_bins=len(rows),
                coefficient_count=1, within_session_pre_RMSE_W=float(np.sqrt(np.mean((y-b*x)**2)*len(ids))),
                formula='P50 + b*(other_CPU_rate[10,30]-other_CPU_rate[-20,30]); applied only after35 through120',
                future_CPU_or_power_used=False, physical_CPU_power_identified=False,
                default=False, strict_support=False, accuracy_pass=None, experiment_ready=False)


def predict(public, model, fixed_power, lo, hi, *, opt_in=False):
    if not opt_in:
        raise ValueError('explicit offline diagnostic opt-in required')
    if not 0 <= lo < hi <= END:
        raise ValueError('fixed120 horizon; no extrapolation')
    f = public['cpu_feature']
    if f['event_cutoff_s'] > 30 or f['hypothetical_issue_s'] != ISSUE or not public['trace_complete']:
        raise ValueError('unavailable pre-event CPU feature')
    b, delta = model['slope_W_per_core_s_per_s'], f['contrast_core_s_per_s']
    if not all(math.isfinite(v) for v in (b, delta, public['pre_w'])) or b < 0 or public['pre_w']+b*delta <= 0:
        raise ValueError('invalid or nonpositive baseline; no clipping')
    base = prior.prior.energy(dict(pre_w=public['pre_w']), public['actual'], fixed_power, lo, hi)
    return base + b*delta*(max(0., hi-ISSUE)-max(0., lo-ISSUE))


def prepare(external, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    old = read(ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')
    cases = history(); bins = []; inputs = []; hashes = {}; availability = []
    for c in cases:
        folder = Path(external)/old['source_locations'][c['id']]
        boundary = folder/'artifacts/history_boundary.json'
        if sha(boundary) != old['raw_files'][c['id']+'/history_boundary.json']:
            raise ValueError('source boundary hash mismatch')
        h = read(boundary); trace = folder/'trace_export'
        audit = read(trace/'audit.json')
        if audit['status'] != 'content_eligible_descriptive_only' or audit['expected_cpus'] != list(range(8)):
            raise ValueError('existing trace audit not eligible')
        clocks = list(csv.DictReader((trace/'clock.csv').open(encoding='utf8', newline='')))
        if not clocks or any(int(r['clock_id']) != 6 or int(r['ts']) != int(r['clock_value']) for r in clocks):
            raise ValueError('BOOTTIME equality not verified')
        if list(csv.DictReader((trace/'loss.csv').open(encoding='utf8', newline=''))):
            raise ValueError('trace loss/error')
        for name in ('sched.csv', 'clock.csv', 'loss.csv', 'audit.json', 'cpu.csv', 'export_binding.json'):
            hashes[c['id']+'/trace_export/'+name] = sha(trace/name)
        hashes[c['id']+'/history_boundary.json'] = sha(boundary)
        binding = read(trace/'export_binding.json')
        if binding['trace_sha256'] != audit['trace_sha256']:
            raise ValueError('trace provenance mismatch')
        rows = pre_power_bins(c, cpu_bins(trace/'sched.csv', h['target_start_ns']))
        f = feature(rows)
        pre_mean = float(np.mean([r['mean_power_W'] for r in rows]))
        if abs(pre_mean-c['pre_w']) > 1e-10:
            raise ValueError('existing P50 not reproduced')
        bins.extend(dict(session=c['id'], role=c['role'], gap=c['gap'], **r) for r in rows)
        inputs.append(dict(id=c['id'], role=c['role'], gap=c['gap'], policy=c['policy'], pre_w=c['pre_w'],
                           actual=c['actual'], cpu_feature=f, trace_complete=True))
        availability.append(dict(session=c['id'], role=c['role'], gap=c['gap'], policy=c['policy'], **f,
                                 pre50_W=pre_mean, trace_loss=0, full_8_CPU_coverage=True,
                                 future_events_excluded=True, live_export_path_available=False))
        print(json.dumps(dict(stage='pre_only_extract', session=c['id']), ensure_ascii=False), flush=True)
    write(out/'pre_inputs.json', inputs)
    prior.prior.old.scope_api.tail.s.csv_write(out/'pre_bins.csv', bins)
    prior.prior.old.scope_api.tail.s.csv_write(out/'pre_features.csv', availability)
    write(out/'source_inventory.json', dict(files=hashes, source_locations=old['source_locations'], device_commands=0))
    sources = dict(prior.prior.registration()['sources'])
    sources['docs/results/energy_ap_zero_offset_01/run_v1/candidate.json'] = sha(prior.prior.BUNDLE/'run_v1/candidate.json')
    sources['tools/d1_cpu_prebaseline.py'] = sha(Path(__file__))
    sources['docs/results/cpu_prebaseline_01/analysis_contract.json'] = sha(BUNDLE/'analysis_contract.json')
    sources = {p: sha(ROOT/p) for p in sources}
    write(out/'registration.json', dict(id='CPU-PREBASELINE-PC-01', contract=read(BUNDLE/'analysis_contract.json'),
        sources=sources, input_hashes={p: sha(out/p) for p in ('pre_inputs.json','pre_bins.csv','source_inventory.json','pre_features.csv')},
        development_ids=[c['id'] for c in cases if c['role']=='development'],
        evaluation_ids=[c['id'] for c in cases if c['role']=='confirmation']))


def run(output):
    out = Path(output); started = time.monotonic(); calls = 0
    if (out/'fit_receipt.json').exists() or (out/'FAIL.json').exists() or (out/'receipt.json').exists():
        raise ValueError('analysis already consumed; no automatic restart')
    reg = read(out/'registration.json')
    for p,h in reg['sources'].items():
        if sha(ROOT/p) != h: raise ValueError('registered source changed '+p)
    for p,h in reg['input_hashes'].items():
        if sha(out/p) != h: raise ValueError('registered pre input changed '+p)
    write(out/'started.json', dict(status='PC analysis started', device_commands=0))
    try:
        bins = prior.prior.old.table(out/'pre_bins.csv')
        for r in bins:
            for k in ('lo_s','hi_s','other_rate_core_s_per_s','mean_power_W','latest_power_event_s'):
                r[k] = float(r[k])
            r['gap'] = int(r['gap'])
        dev = [r for r in bins if r['session'] in reg['development_ids']]
        models = {}; model_hashes = {}
        for excluded in (30,180,None):
            calls += 1
            write(out/('fit_started_'+str(calls)+'.json'), dict(call=calls, maximum=3, excluded_gap=excluded))
            m = fit([r for r in dev if r['gap'] != excluded], reg['development_ids'])
            key = str(excluded) if excluded else 'final'; models[key] = m
            write(out/('candidate_'+key+'.json'), m); model_hashes[key] = sha(out/('candidate_'+key+'.json'))
        write(out/'fit_receipt.json', dict(status='frozen_before_future_evaluation', fits=calls, maximum=3,
            model_hashes=model_hashes, registration_sha256=sha(out/'registration.json'),
            future_evaluation_targets_used_in_fit=False, targets_seen_in_prior_work=True))
        lookup = {c['id']:c for c in history()}; fixed,_ = prior.prior.read_candidate(prior.prior.BUNDLE/'run_v1')
        original = read(prior.prior.old.analysis.j.m.MODEL)
        frozen = dict(idle_bias_w=0., increments=original['energy_increment_w'])
        errors = []; curves = []
        for public in read(out/'pre_inputs.json'):
            c = lookup[public['id']]
            model = models[str(c['gap'])] if c['role']=='development' else models['final']
            phase = 'development_gap_excluded' if c['role']=='development' else 'already_seen_confirmation'
            last = max(ISSUE, c['last_lane_s'] or ISSUE)
            windows = [('reference120',0.,120.),('future85',35.,120.),('post_lane_idle',last,120.)]
            if last > ISSUE: windows.append(('work_present',ISSUE,last))
            for name, lo, hi in windows:
                observed = prior.prior.old.observed.measured_energy(c,lo,hi)
                obs = observed['full_energy_j']
                values = dict(original_frozen=prior.prior.energy(public,public['actual'],frozen,lo,hi),
                              fixed_zero_offset=prior.prior.energy(public,public['actual'],fixed,lo,hi),
                              CPU_prebaseline=predict(public,model,fixed,lo,hi,opt_in=True))
                for variant,y in values.items():
                    errors.append(dict(session=c['id'],role=c['role'],evaluation=phase,gap=c['gap'],policy=c['policy'],
                        phase=name,lo_s=lo,hi_s=hi,variant=variant,**observed,predicted_J=y,
                        signed_J=y-obs if obs is not None else None,absolute_J=abs(y-obs) if obs is not None else None,
                        relative_signed=(y-obs)/obs if obs else None,baseline_correction_W=model['slope_W_per_core_s_per_s']*public['cpu_feature']['contrast_core_s_per_s'],
                        real_schedule_conditional=True,future_CPU_or_power_used_as_input=False))
            for t in range(1,121):
                obs = prior.prior.old.observed.measured_energy(c,0.,float(t))['full_energy_j']
                base = prior.prior.energy(public,public['actual'],fixed,0.,float(t))
                new = predict(public,model,fixed,0.,float(t),opt_in=True)
                curves.append(dict(session=c['id'],role=c['role'],t_s=t,observed_J=obs,
                                   fixed_zero_offset_J=base,CPU_prebaseline_J=new,
                                   baseline_residual_J=base-obs if obs is not None else None,
                                   CPU_residual_J=new-obs if obs is not None else None))
        for name, rows in [('energy_errors',errors),('energy_curves',curves)]:
            prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
        summary = []
        for role in ('development','confirmation'):
            for phase in ('reference120','future85','post_lane_idle','work_present'):
                for variant in ('original_frozen','fixed_zero_offset','CPU_prebaseline'):
                    use = [r for r in errors if r['role']==role and r['phase']==phase and r['variant']==variant and r['absolute_J'] is not None]
                    if use:
                        summary.append(dict(role=role,phase=phase,variant=variant,sessions=len(use),
                                            mean_absolute_J=float(np.mean([r['absolute_J'] for r in use])),
                                            mean_signed_J=float(np.mean([r['signed_J'] for r in use])),
                                            maximum_absolute_J=max(r['absolute_J'] for r in use)))
        prior.prior.old.scope_api.tail.s.csv_write(out/'summary.csv',summary)
        write(out/'receipt.json', dict(status='finite_posthoc_PC_evaluation_complete',global_fits=calls,AP_fits=0,
            history_sessions=12,development_sessions=6,already_seen_confirmation_sessions=6,
            learned_coefficients=1,other_source_sessions_not_applied=23,
            elapsed_s=time.monotonic()-started,device_commands=0,new_device_plan=0,
            default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False,
            forecast_event_cutoff_s=30.,forecast_issue_s=35.,forecast_end_s=120.,
            event_time_causal=True,online_CPU_feature_export_implemented=False,
            AP_unchanged=True,accuracy_pass=None,automatic_refit=False))
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    except BaseException:
        write(out/'FAIL.json', dict(original_stack=traceback.format_exc(),fits_started=calls,device_commands=0,automatic_retry=False))
        raise


def main():
    p = argparse.ArgumentParser(); p.add_argument('--action', choices=('prepare','run'), required=True)
    p.add_argument('--output', required=True); p.add_argument('--external-root'); a = p.parse_args()
    if a.action=='prepare': prepare(a.external_root,a.output)
    else: run(a.output)


if __name__=='__main__': main()
