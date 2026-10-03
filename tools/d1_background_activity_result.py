"""PC-only, unfitted readout of the four acquired background contrasts."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from tools import d1_background_activity_plan as plan_code
from tools import d1_background_activity_readout as trace
from tools import d1_online_policy_model as online
from tools import d1_arrival_recorded_replay_analysis as states
from tools import d1_energy_thermal as energy
from tools import d1_resident_control_readout as idle

p = plan_code.p


def interpolate(points, queries, max_gap_ns):
    if len(points) < 2 or any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError('unordered or missing observations')
    if not all(np.isfinite(v) for _, v in points):
        raise ValueError('nonfinite observation')
    result = []
    for q in queries:
        pair = next(((a, b) for a, b in zip(points, points[1:]) if a[0] <= q <= b[0]), None)
        if pair is None or pair[1][0]-pair[0][0] > max_gap_ns:
            result.append(None)
        else:
            a, b = pair
            result.append(a[1]+(b[1]-a[1])*(q-a[0])/(b[0]-a[0]))
    return result


def session(file, plan, entry, model, export_folder):
    folder = Path(plan['output_root'])/f"{entry['index']:02d}_{entry['session_id']}"
    art = folder/'artifacts'
    if p.read(folder/'validated.json')['status'] != 'eligible_descriptive_only':
        raise ValueError('not a validated completed session')
    if p.read(art/'manifest.json') != p.read(Path(file).parent/entry['manifest']):
        raise ValueError('manifest mismatch')
    rows = p.read(art/'requests.json')
    if len(rows) != entry['requests'] or any(r['terminal_status'] != 'succeeded' for r in rows):
        raise ValueError('incomplete request denominator')
    if p.read(art/'cleanup.json')['status'] != 'completed':
        raise ValueError('app cleanup incomplete')
    origin = p.read(art/'common_boundary.json')['start_ns']
    end = origin+120_000_000_000
    events = online.logs.read_lines(art/'progress.jsonl')
    counts = {kind:sum(e['kind']==kind for e in events) for kind in
              ('runtime_start','runtime_return','warmup_start','warmup_return')}
    if counts != dict(runtime_start=4,runtime_return=4,warmup_start=8,warmup_return=8):
        raise ValueError('runtime/warmup consumption unconfirmed')
    power = [dict(e, mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
             for e in events if e['kind'] == 'power_sample']
    points = [(e['mono_ns'], float(e['AP'])) for e in online.logs.read_lines(folder/'thermal.jsonl')
              if e.get('AP') not in (None, '') and e.get('thermal_status') == '0']
    segments = states.observed_segments(rows, origin) if rows else [dict(start_s=0., end_s=120., state='idle')]
    if rows:
        case = online.load_case(file, plan, entry)
    else:
        baselines = [e['mono_ns'] for e in events if (e.get('phase'), e['kind']) == ('resident_baseline', 'phase_start')]
        cooling = [e['mono_ns'] for e in events if (e.get('phase'), e['kind']) == ('resident_cooling', 'phase_end')]
        if len(baselines) != 1 or len(cooling) != 1:
            raise ValueError('missing phase boundaries')
        thermal = online.logs.read_lines(folder/'thermal.jsonl')
        pre = [dict(t=(e['mono_ns']-origin)/1e9, ap=float(e['AP']), lo=(e['before_ns']-origin)/1e9,
                    hi=(e['after_ns']-origin)/1e9) for e in thermal if e.get('AP') not in (None, '') and
               baselines[0] <= e['before_ns'] <= e['after_ns'] < origin+35e9 and e.get('thermal_status') == '0']
        post = [e for e in thermal if e.get('AP') not in (None, '') and e.get('thermal_status') == '0' and
                origin+35e9 <= e['before_ns'] <= e['after_ns'] <= cooling[0]]
        case = dict(inputs=dict(preload=pre, query_s=[(e['mono_ns']-origin)/1e9 for e in post],
                    segments=segments+[dict(start_s=120., end_s=(cooling[0]-origin)/1e9, state='idle')]),
                    observed_ap_c=[float(e['AP']) for e in post], origin_ns=origin, power_samples=power)
        case['preload_power_w'] = online.energy_at(case, 10, 30)/20
    out = online.costs(case['inputs']['segments'], dict(preload=case['inputs']['preload'],
        preload_power_w=case['preload_power_w']), case['inputs']['query_s'], model, case['inputs']['segments'][-1]['end_s'])
    actual = energy.integrate(power, origin, end, 1000)
    if actual['full_energy_j'] is None:
        raise ValueError('missing common-window power; no full energy')
    exposures = {}
    for s in segments:
        key = states.state_key(s['state'])
        exposures[key] = exposures.get(key, 0.)+s['end_s']-s['start_s']
    if abs(sum(exposures.values())-120) > 1e-6:
        raise ValueError('common state coverage')
    causal = [e for e in events if e['kind'] == 'causal_power_input']
    if any(e['window_end_ns'] > e['issue_ns'] or e['latest_ready_ns'] > e['issue_ns'] or e['future_ap_used'] for e in causal):
        raise ValueError('future input leaked')
    counter = [(e['mono_ns'], float(e['self_cpu_ms'])) for e in power]
    if any(b[1] < a[1] for a, b in zip(counter, counter[1:])):
        raise ValueError('self CPU counter regressed')
    cpu = interpolate(counter, [origin, end], 2_500_000_000)
    self_cpu_s = None if None in cpu else (cpu[1]-cpu[0])/1000
    try:
        activity = trace.summarize(export_folder, origin, end,plan.get('trace_content_audit',{}).get('expected_cpus'))
        trace_status = activity['status']; trace_error = None
    except ValueError as error:
        activity = None; trace_status = 'contract_ineligible'; trace_error = str(error)
    initial = p.read(art/'start_ap.accepted.json')
    n = entry['requests']
    response_ms = [(r['output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns']-r['scheduled_arrival_ns'])/1e6 for r in rows]
    successes = sum(r['output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns'] <= r['deadline_ns'] for r in rows)
    summary = dict(condition=entry['condition'], role='development', planned=n, completed=n,
        warmup=counts['warmup_return'], runtime=counts['runtime_return'], consumption_event_counts=counts,
        common_seconds=120, observed_energy_j=actual['full_energy_j'], predicted_energy_j=out['whole_120s_j'],
        signed_energy_error_j=out['whole_120s_j']-actual['full_energy_j'],
        energy_prediction_inputs='frozen increments + this session pre-load10-30s mean power + actual schedule; not E2E',
        ap_scores=online.common.score(case['observed_ap_c'], out['ap_path']), ap_score_window_s=[35.,case['inputs']['query_s'][-1]],
        ap_prediction_inputs='frozen AP coefficients + pre-load AP only + actual schedule; no post-load feedback',
        common_start_ap_c=initial['ap_c'], initial_in_original_development_range=initial['initial_ap_in_frozen_development_range'],
        common_ap=idle.ap_window(points, origin, end), state_seconds=exposures, power_samples=sum(origin<=e['mono_ns']<=end for e in power),
        max_power_gap_s=max((b['mono_ns']-a['mono_ns'])/1e9 for a,b in zip(power,power[1:])),
        self_cpu_seconds=self_cpu_s, causal_inputs=len(causal), available_causal_inputs=sum(e['status']=='available' for e in causal),
        trace_status=trace_status, trace_error=trace_error, system_cpu_activity=None if activity is None else activity,
        deadline_service_success_rate=None if not n else successes/n, response_p95_ms=None if not n else float(np.percentile(response_ms,95)),
        independent_validation=False, accuracy_pass=None, experiment_ready=False)
    curve=[]
    for second in range(1,121):
        j=energy.integrate(power,origin,origin+second*1_000_000_000,1000)['full_energy_j']
        pred=out['energy_path'][second]['predicted_j']
        curve.append(dict(condition=entry['condition'], common_s=second, observed_j=j, predicted_j=pred,
                          residual_j=None if j is None else pred-j))
    aps=[dict(condition=entry['condition'],common_s=t, observed_ap_c=v, predicted_ap_c=w,residual_c=w-v)
         for t,v,w in zip(case['inputs']['query_s'],case['observed_ap_c'],out['ap_path'])]
    return summary, curve, aps, causal


def run(file, exports, output, allow_partial=False):
    file=Path(file);output=Path(output)
    if output.exists():raise FileExistsError('fresh readout output required')
    plan=p.read(file)
    if p.digest(plan['activity_model']['path']) != plan['activity_model']['sha256']:raise ValueError('frozen model drift')
    receipt=p.read(Path(plan['output_root'])/'FINAL_RECEIPT.json')
    complete=receipt['status']=='completed_descriptive_only'
    if not complete and not (allow_partial and receipt['status']=='stopped_no_resume'):raise ValueError('not completed block; explicit partial opt-in required')
    eligible=[e for e in plan['entries'] if (Path(plan['output_root'])/f"{e['index']:02d}_{e['session_id']}"/'validated.json').is_file()]
    if len(eligible)!=(receipt['sessions'] if complete else receipt['completed_sessions']):raise ValueError('eligible session denominator mismatch')
    output.mkdir(parents=True);model=p.read(plan['activity_model']['path']);results=[];curves=[];aps=[]
    for e in eligible:
        exported=Path(exports)/f"{e['index']:02d}_trace_export"
        if not exported.exists():exported=Path(exports)/f"{e['index']:02d}_{e['session_id']}"/'trace_export'
        s, c, a, inputs=session(file,plan,e,model,exported)
        results.append(s);curves.extend(c);aps.extend(a)
    result=dict(status='acquisition_completed_trace_contract_ineligible' if any(x['trace_error'] for x in results) else 'descriptive_only',
                acquisition_status=receipt['status'],full_planned_block_completed=complete,completed_sessions=len(eligible),planned_sessions=len(plan['entries']),
                plan_sha256=p.digest(file),model_sha256=p.digest(plan['activity_model']['path']),sessions=results,
                coefficient_fit=False,candidate_adopted=False,independent_confirmation_sessions=0,experiment_ready=False)
    (output/'summary.json').write_bytes(p.canonical(result))
    for name,rows in [('energy_paths.csv',curves),('ap_paths.csv',aps)]:
        with (output/name).open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return result


if __name__=='__main__':
    q=argparse.ArgumentParser()
    for key in ('plan','exports','output'):q.add_argument('--'+key,required=True)
    q.add_argument('--allow-partial',action='store_true')
    a=q.parse_args();r=run(a.plan,a.exports,a.output,a.allow_partial)
    print(json.dumps({k:v for k,v in r.items() if k!='sessions'},indent=2))
