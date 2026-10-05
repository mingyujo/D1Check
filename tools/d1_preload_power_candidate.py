"""One opt-in, posthoc preload power candidate. No device calls or model fitting."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_analysis as descriptive
from tools import d1_arrival_recorded_replay_analysis as replay
from tools import d1_energy_thermal as energy
from tools.d1_resident_idle_comparison import FROZEN_SHA

ORIGIN = 1_000_000_000_000  # Portable artificial origin, not device boot time.
SPECS = [('B2_queue_seen', 'energy_ap_recorded_b2_diag_run_v6', '00_'),
         ('idle_development_seen', 'energy_ap_idle_response_run_v1', '00_'),
         ('idle_confirmation_seen', 'energy_ap_idle_response_run_v1', '01_'),
         ('CGDC_transfer_seen', 'energy_ap_cgdc_transfer_run_v2', '00_')]


def export(source_root, frozen_file, reference_file, output):
    """Reuse previously audited source hashes; export no hardware/session identifiers."""
    if Path(output).exists():
        raise FileExistsError('fresh portable input only')
    if p.digest(frozen_file) != FROZEN_SHA:
        raise ValueError('original freeze mismatch')
    reference = p.read(reference_file)
    cases = []
    for name, run, prefix in SPECS:
        root = Path(source_root)/run
        matches = list(root.glob(prefix+'*'))
        if len(matches) != 1:
            raise ValueError('one source session required')
        folder = matches[0]; a = folder/'artifacts'
        for key, sha in reference['starting_inputs_sha256'].items():
            case, filename = key.split('/')
            if case != name:
                continue
            base = root if filename == 'FINAL_RECEIPT.json' else (
                folder if filename in ('validated.json', 'before_session_battery.txt', 'thermal.jsonl') else a)
            if p.digest(base/filename) != sha:
                raise ValueError('source changed: '+key)
        b = p.read(a/'common_boundary.json'); origin = b['start_ns']
        requests = p.read(a/'requests.json')
        if len(requests) != 24 or any(r['terminal_status'] != 'succeeded' for r in requests):
            raise ValueError('incomplete planned denominator')
        events = descriptive.read_lines(a/'progress.jsonl')
        baseline = [x['mono_ns'] for x in events if x['kind'] == 'phase_start' and x['phase'] == 'resident_baseline']
        if len(baseline) != 1:
            raise ValueError('baseline boundary missing')
        samples = []
        for x in events:
            if x['kind'] != 'power_sample' or x['snapshot_start_ns'] < baseline[0]:
                continue
            samples.append(dict(relative_ns=(x['snapshot_start_ns']+x['sensor_read_end_ns'])//2-origin,
                read_start_ns=x['snapshot_start_ns']-origin, read_end_ns=x['sensor_read_end_ns']-origin,
                current_raw=x['current_raw'], current_valid=x['current_valid'], voltage_mV=x['voltage_mV'],
                plugged=x['plugged'], active_count=len(x['active']), resident_keys=x['resident_keys'], phase=x['phase']))
        cases.append(dict(case=name, source_context=next(x for x in reference['cases'] if x['case'] == name),
            baseline_start_ns=baseline[0]-origin, samples=samples,
            states=replay.observed_segments(requests, origin)))
    bundle = dict(version='preload-power-portable-v1', frozen_sha256=FROZEN_SHA,
        original_power_w=p.read(frozen_file)['whole_device_power_w'], cases=cases,
        source_hashes=reference['starting_inputs_sha256'], raw_source_reference_sha256=p.digest(reference_file))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return bundle


def prepare(case, contract, powers):
    expected = {'prefix_window_seconds':20.0, 'prefix_end_before_first_dispatch_seconds':2.5,
                'minimum_observed_prefix_span_seconds':15.0, 'max_sensor_gap_seconds':2.5,
                'prefix_endpoint_max_trim_seconds':2.5}
    if any(contract.get(k) != v for k,v in expected.items()):
        raise ValueError('candidate v1 contract changed; no adaptive windows')
    states = case['states']
    if not states or states[0]['start_s'] != 0 or states[-1]['end_s'] != 120:
        raise ValueError('complete 120s state map required')
    for i, s in enumerate(states):
        if not all(math.isfinite(s[k]) for k in ('start_s', 'end_s')) or s['end_s'] <= s['start_s']:
            raise ValueError('invalid state interval')
        if i and abs(states[i-1]['end_s']-s['start_s']) > 1e-9:
            raise ValueError('state gap or overlap')
        key = replay.state_key(s['state'])
        if key not in powers or not math.isfinite(powers[key]) or powers[key] <= 0:
            raise ValueError('unsupported state or power')
    active = [s for s in states if s['state'] != 'idle']
    if not active:
        raise ValueError('load boundary required')
    first, last = active[0]['start_s'], active[-1]['end_s']
    cutoff = round((first-contract['prefix_end_before_first_dispatch_seconds'])*1e9)
    begin = cutoff-round(contract['prefix_window_seconds']*1e9)
    if begin < case['baseline_start_ns']:
        raise ValueError('prefix precedes resident preparation')
    samples = [dict(x, mono_ns=ORIGIN+x['relative_ns']) for x in case['samples']]
    samples = energy.canonical_samples(samples)[0]
    prefix = [x for x in samples if begin <= x['relative_ns'] <= cutoff and x['read_end_ns'] <= cutoff]
    if len(prefix) < 2:
        raise ValueError('prefix missing')
    edge_ns = round(contract['max_sensor_gap_seconds']*1e9)
    if prefix[0]['relative_ns']-begin > edge_ns or cutoff-prefix[-1]['relative_ns'] > edge_ns:
        raise ValueError('prefix edge missing or stale; no window shift')
    for x in prefix:
        if (not x['read_start_ns'] <= x['relative_ns'] <= x['read_end_ns'] or
                x['active_count'] != 0 or set(x['resident_keys']) != set(contract['required_resident_keys']) or
                x['phase'] not in ('resident_baseline', 'common_window')):
            raise ValueError('prefix not resident idle or invalid read clock')
    span = (prefix[-1]['mono_ns']-prefix[0]['mono_ns'])/1e9
    if span < contract['minimum_observed_prefix_span_seconds']:
        raise ValueError('prefix too short')
    value = energy.integrate(prefix, prefix[0]['mono_ns'], prefix[-1]['mono_ns'], 1000,
                             contract['max_sensor_gap_seconds'])
    if value['full_energy_j'] is None:
        raise ValueError('prefix missing, invalid or charging; no fallback')
    baseline = value['full_energy_j']/span
    offset = baseline-powers['resident_idle']
    candidate = {k: v+offset for k, v in powers.items()}
    if any(not math.isfinite(v) or v <= 0 for v in candidate.values()):
        raise ValueError('nonpositive candidate power; no clipping')
    info = dict(mean_preload_w=baseline, additive_offset_w=offset,
        prefix_start_s=prefix[0]['relative_ns']/1e9, prefix_end_s=prefix[-1]['relative_ns']/1e9,
        prefix_span_s=span, prefix_samples=len(prefix), latest_read_end_s=max(x['read_end_ns'] for x in prefix)/1e9,
        information_time_s=first, score_end_s=120., last_lane_release_s=last)
    return info, candidate, samples


def predicted_j(states, lo, hi, powers):
    return sum(max(0., min(hi,s['end_s'])-max(lo,s['start_s']))*powers[replay.state_key(s['state'])] for s in states)


def evaluate_case(case, contract, powers):
    info, candidate, samples = prepare(case, contract, powers)
    first, last = info['information_time_s'], info['last_lane_release_s']
    rows = []
    for label, lo, hi in [('future_total',first,120.), ('load_envelope',first,last), ('post_load_idle',last,120.)]:
        if hi <= lo:
            continue
        observed = energy.integrate(samples, ORIGIN+round(lo*1e9), ORIGIN+round(hi*1e9), 1000,
                                    contract['max_sensor_gap_seconds'])
        actual = observed['full_energy_j']
        old = predicted_j(case['states'],lo,hi,powers)
        new = predicted_j(case['states'],lo,hi,candidate)
        rows.append(dict(case=case['case'], phase=label, start_s=lo, end_s=hi, duration_s=hi-lo,
            observed_j=actual, original_j=old, candidate_j=new, missing_s=observed['missing_s'],
            original_error_j=None if actual is None else old-actual,
            candidate_error_j=None if actual is None else new-actual,
            candidate_relative_error=None if actual in (None,0) else (new-actual)/actual))
    path = []
    for t in sorted({first, last, 120., *[float(i) for i in range(math.ceil(first),121)]}):
        observed = energy.integrate(samples,ORIGIN+round(first*1e9),ORIGIN+round(t*1e9),1000,
                                    contract['max_sensor_gap_seconds'])
        actual = 0. if t == first else observed['full_energy_j']
        old, new = (predicted_j(case['states'],first,t,powermap) for powermap in (powers,candidate))
        path.append(dict(case=case['case'],elapsed_s=t,observed_j=actual,original_j=old,candidate_j=new,
            original_error_j=None if actual is None else old-actual,
            candidate_error_j=None if actual is None else new-actual))
    return dict(case=case['case'], status='posthoc_evaluable' if all(r['observed_j'] is not None for r in rows)
        else 'partial_score_missing', **info, full_120s_candidate_j=None), rows, path


def run(bundle_file, contract_file, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError('fresh candidate output only')
    bundle, contract = p.read(bundle_file), p.read(contract_file)
    if bundle['frozen_sha256'] != FROZEN_SHA or contract['frozen_sha256'] != FROZEN_SHA:
        raise ValueError('frozen identity mismatch')
    infos, rows, paths = [], [], []
    for case in bundle['cases']:
        try:
            info, result, path = evaluate_case(case,contract,bundle['original_power_w'])
        except ValueError as e:
            infos.append(dict(case=case['case'],status='not_evaluable',reason=str(e)))
            continue
        infos.append(info); rows.extend(result); paths.extend(path)
    output.mkdir(parents=True)
    for name, data in [('scores.csv',rows),('energy_paths.csv',paths)]:
        if data:
            with (output/name).open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    summary=dict(candidate_id=contract['candidate_id'],cases=infos,bundle_sha256=p.digest(bundle_file),
        contract_sha256=p.digest(contract_file),code_sha256=p.digest(__file__),frozen_sha256=FROZEN_SHA,
        evaluation='posthoc; all outcomes previously seen; actual schedule conditioned',
        independent_confirmation_sessions=0,cross_session_fitted_coefficients=0,
        ap_model_changed=False,strict_support=False,policy_rank=None,accuracy_pass=None,experiment_ready=False,
        device_commands=0)
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if paths:
        plot(paths, output)
    return summary


def plot(paths, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2,2,figsize=(10,7))
    for ax, name in zip(axes.flat,dict.fromkeys(x['case'] for x in paths)):
        points=[x for x in paths if x['case']==name]
        for key, label in [('original_error_j','Original frozen'),('candidate_error_j','Preload offset candidate')]:
            ax.plot([x['elapsed_s'] for x in points],[float('nan') if x[key] is None else x[key] for x in points],label=label)
        ax.axhline(0,color='gray',linewidth=.8);ax.set_title(name.replace('_',' '))
        ax.set_xlabel('Common-window seconds (score starts at first dispatch)')
        ax.set_ylabel('Cumulative predicted - observed J');ax.legend(fontsize=8)
    fig.suptitle('One posthoc candidate: observed preload baseline + frozen state increments\nNo independent validation; raw=mA conditional; no policy rank')
    fig.tight_layout()
    for ext in ('png','svg'):
        f=output/('comparison.'+ext);fig.savefig(f,dpi=150)
        if ext=='svg':f.write_text('\n'.join(x.rstrip() for x in f.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


def main():
    q=argparse.ArgumentParser(description=__doc__);s=q.add_subparsers(dest='action',required=True)
    ex=s.add_parser('export')
    for name in ('source-root','frozen','reference','output'):ex.add_argument('--'+name,required=True)
    ev=s.add_parser('evaluate')
    for name in ('bundle','contract','output'):ev.add_argument('--'+name,required=True)
    a=q.parse_args()
    if a.action=='export':
        out=export(a.source_root,a.frozen,a.reference,a.output); print('exported cases:',len(out['cases']))
    else:print(json.dumps(run(a.bundle,a.contract,a.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
