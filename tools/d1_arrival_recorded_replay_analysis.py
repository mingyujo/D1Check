"""Conditional A24 frozen-model readout of an observed recorded-dispatch replay.

This diagnostic deliberately does not change the regimen-only strict support mask.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_policy_screen as screen
from tools import d1_arrival_energy_analysis as descriptive
from tools import d1_energy_thermal as energy
from tools import d1_arrival_recorded_replay as replay


def state_key(state):
    if state == 'idle':return 'resident_idle'
    return '+'.join(':'.join(member.split(':')[:2]).replace(':','_') for member in state.split('+'))


def observed_segments(rows, origin):
    ledger=[]
    for r in rows:
        if r.get('selected_backend') is None or r.get('dispatch_ns') is None:
            raise ValueError('unfinished dispatch: full-state prediction unavailable')
        q=dict(arrival_ns=r['scheduled_arrival_ns']-origin,
               task=r['task_id'],backend=r['selected_backend'],priority=r['priority'])
        for field in ('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns',
                      'worker_release_ns','lane_available_ns'):
            if r.get(field) is not None:q[field]=r[field]-origin
        ledger.append(q)
    return screen.occupancy({'ledger':ledger},'queue',1.5,201,replay.POLICY)


def forecast(segments, frozen, initial_ap, times_s):
    """Exact piecewise constant power and continuous first-order AP; no later sensor input."""
    lo,hi=frozen['initial_ap_development_range_c']
    if not lo<=initial_ap<=hi:raise ValueError('unsupported initial AP')
    beta=frozen['ap_cooling_rate_per_s'];ref=frozen['ap_reference_c']
    power=frozen['whole_device_power_w'];slope=frozen['ap_slope_at_30_c_per_s']
    if not beta>0 or any(state_key(x['state']) not in power or state_key(x['state']) not in slope for x in segments):
        raise ValueError('unsupported frozen state')
    if (not segments or abs(segments[0]['start_s'])>1e-9 or abs(segments[-1]['end_s']-120)>1e-6 or
            any(abs(a['end_s']-b['start_s'])>1e-9 for a,b in zip(segments,segments[1:]))):
        raise ValueError('noncontiguous common window')
    queried=sorted(set([0.,120.,*times_s,*[s['end_s'] for s in segments]]));out=[];position=0;t=initial_ap;j=0.
    for target in queried:
        if not 0<=target<=120:raise ValueError('query outside common window')
        while position<target-1e-10:
            segment=next((s for s in segments if s['start_s']<=position+1e-10<s['end_s']-1e-10),None)
            if segment is None:raise ValueError('missing state interval')
            end=min(target,segment['end_s']);dt=end-position;key=state_key(segment['state'])
            j+=power[key]*dt
            equilibrium=ref+slope[key]/beta
            t=energy.transition(t,equilibrium,1/beta,dt)
            position=end
        out.append(dict(elapsed_s=target,predicted_energy_j=j,predicted_ap_c=t))
        observed_range=frozen.get('ap_development_observed_range_c')
        if observed_range and not observed_range[0]<=t<=observed_range[1]:
            raise ValueError('predicted AP exits development path range')
    return out


def analyze(session, frozen_file, output):
    session,output=Path(session),Path(output)
    if output.exists():raise FileExistsError(output)
    frozen=p.read(frozen_file)
    if p.digest(frozen_file)!=replay.FROZEN_SHA or frozen['version']!='energy-ap-state-regimen-fit-v1':
        raise ValueError('frozen model changed')
    source_rows=replay.source_check()['requests']
    artifact=session/'artifacts';manifest=p.read(artifact/'manifest.json')
    if manifest['policy']!=replay.POLICY or manifest['replay_source_sha256']!=p.digest(replay.BUNDLE):
        raise ValueError('not this recorded replay')
    boundary=p.read(artifact/'common_boundary.json');rows=p.read(artifact/'requests.json')
    origin=boundary['start_ns'];end=boundary['planned_end_ns']
    if end-origin!=120_000_000_000 or len(rows)!=24:raise ValueError('common denominator/window')
    initial=p.read(artifact/'start_ap.accepted.json')
    if initial['common_start_ns']!=origin:raise ValueError('initial AP origin')
    segments=observed_segments(rows,origin)
    if any(state_key(s['state']) not in frozen['states'] for s in segments):
        raise ValueError('actual unsupported state')
    events=descriptive.read_lines(artifact/'progress.jsonl')
    samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
             for e in events if e['kind']=='power_sample']
    thermal=descriptive.read_lines(session/'thermal.jsonl')
    ap=[(x['mono_ns'],float(x['AP'])) for x in thermal if origin<=x['mono_ns']<=end and x['AP']!='']
    if len(ap)<2 or max([ap[0][0]-origin,end-ap[-1][0]]+
                        [b[0]-a[0] for a,b in zip(ap,ap[1:])])>10_000_000_000:
        raise ValueError('incomplete AP path')
    ap_range=frozen['ap_development_observed_range_c']
    if any(not ap_range[0]<=value<=ap_range[1] for _,value in ap):
        raise ValueError('observed AP exits development path range')
    observed=energy.integrate(samples,origin,end,1000)
    if observed['full_energy_j'] is None:raise ValueError('incomplete common current/voltage; no full J')
    query=[(t-origin)/1e9 for t,_ in ap]
    for s in samples:
        if origin<=s['mono_ns']<=end:query.append((s['mono_ns']-origin)/1e9)
    path=forecast(segments,frozen,float(initial['ap_c']),query)
    bytime={round(x['elapsed_s'],9):x for x in path}
    ap_rows=[]
    for t,value in ap:
        at=round((t-origin)/1e9,9);prediction=bytime[at]['predicted_ap_c']
        ap_rows.append(dict(elapsed_s=at,observed_ap_c=value,predicted_ap_c=prediction,
                            signed_error_c=prediction-value))
    energy_rows=[]
    for s in samples:
        t=s['mono_ns']
        if not origin<t<=end:continue
        actual=energy.integrate(samples,origin,t,1000)
        predicted=bytime[round((t-origin)/1e9,9)]['predicted_energy_j']
        energy_rows.append(dict(elapsed_s=(t-origin)/1e9,observed_cumulative_j=actual['full_energy_j'],
                                predicted_cumulative_j=predicted,
                                signed_error_j=predicted-actual['full_energy_j'] if actual['full_energy_j'] is not None else None,
                                covered_s=actual['covered_s']))
    state_rows=[]
    for seg in segments:
        a=origin+round(seg['start_s']*1e9);b=origin+round(seg['end_s']*1e9)
        actual=energy.integrate(samples,a,b,1000)
        estimate=frozen['whole_device_power_w'][state_key(seg['state'])]*(seg['end_s']-seg['start_s'])
        state_rows.append(dict(**seg,frozen_state=state_key(seg['state']),predicted_j=estimate,
            observed_j=actual['full_energy_j'],observed_coverage_s=actual['covered_s'],
            signed_error_j=estimate-actual['full_energy_j'] if actual['full_energy_j'] is not None else None))
    source={r['source_request_id']:r for r in source_rows}
    timing=[]
    for r in rows:
        src=source[r['source_request_id']]
        timing.append(dict(source_request_id=r['source_request_id'],ordinal=r['ordinal'],
            task=r['task_id'],backend=r['selected_backend'],
            planned_arrival_s=src['offset_ms']/1000,
            actual_enqueue_s=(r['queue_entry_ns']-origin)/1e9,
            recorded_release_s=src['release_offset_ns']/1e9,
            actual_dispatch_s=(r['dispatch_ns']-origin)/1e9,
            dispatch_delay_vs_pc_s=(r['dispatch_ns']-origin-src['release_offset_ns'])/1e9,
            worker_start_s=(r['execution_start_ns']-origin)/1e9,
            inference_start_s=(r['host_inference_start_ns']-origin)/1e9,
            inference_return_s=(r['host_inference_return_ns']-origin)/1e9,
            output_ready_delta_vs_pc_s=(r['output_ready_ns']-origin-src['pc_output_ready_ns'])/1e9,
            persist_delta_vs_pc_s=(r['persist_complete_ns']-origin-src['pc_persist_complete_ns'])/1e9,
            worker_release_s=(r['worker_release_ns']-origin)/1e9,
            lane_available_delta_vs_pc_s=(r['lane_available_ns']-origin-src['pc_lane_available_ns'])/1e9))
    state_seconds={key:sum(s['end_s']-s['start_s'] for s in segments if s['state']==key)
                   for key in sorted({s['state'] for s in segments})}
    full_pred=path[-1]['predicted_energy_j'];ap_error=[abs(x['signed_error_c']) for x in ap_rows]
    summary=dict(status='conditional_diagnostic_not_strict_support',planned=24,
        terminal_completed=sum(x['terminal_status']=='succeeded' for x in rows),
        failed=sum(x['terminal_status']=='failed' for x in rows),
        unfinished_at_120s=sum(x.get('persist_complete_ns',10**30)>end for x in rows),
        initial_ap_c=initial['ap_c'],frozen_sha256=replay.FROZEN_SHA,
        observed_energy_120s_j=observed['full_energy_j'],predicted_energy_120s_j=full_pred,
        signed_energy_error_j=full_pred-observed['full_energy_j'],
        absolute_energy_error_j=abs(full_pred-observed['full_energy_j']),
        relative_energy_error=abs(full_pred-observed['full_energy_j'])/observed['full_energy_j'],
        ap_mae_c=sum(ap_error)/len(ap_error),ap_max_absolute_error_c=max(ap_error),
        ap_peak_observed_c=max(x['observed_ap_c'] for x in ap_rows),
        ap_peak_predicted_c=max(x['predicted_ap_c'] for x in path),
        ap_peak_signed_error_c=max(x['predicted_ap_c'] for x in path)-max(x['observed_ap_c'] for x in ap_rows),
        observed_state_seconds=state_seconds,
        observed_parallel_seconds=sum(v for k,v in state_seconds.items() if '+' in k),
        max_dispatch_delay_vs_pc_s=max(x['dispatch_delay_vs_pc_s'] for x in timing),
        power_sample_count=len(samples),ap_sample_count=len(ap),
        power_max_sample_gap_s=max((b['mono_ns']-a['mono_ns'])/1e9 for a,b in zip(samples,samples[1:])),
        ap_max_sample_gap_s=max((b[0]-a[0])/1e9 for a,b in zip(ap,ap[1:])),
        accuracy_pass=None,policy_selection_pass=None,
        meaning='actual lane schedule and observed initial AP supplied; later current/AP used only as targets; one protocol-transfer session')
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,items in [('states.csv',state_rows),('ap_path.csv',ap_rows),
                       ('energy_path.csv',energy_rows),('timing.csv',timing)]:
        with (output/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)
    return summary


def analyze_or_mark(session, frozen_file, output):
    """Record ineligible partial evidence without inventing full-window predictions."""
    try:return analyze(session,frozen_file,output)
    except (ValueError,FileNotFoundError) as error:
        output=Path(output)
        if output.exists():raise
        output.mkdir(parents=True)
        result=dict(status='not_evaluable',reason=str(error),
                    predicted_energy_120s_j=None,observed_energy_120s_j=None,
                    ap_mae_c=None,accuracy_pass=None,policy_selection_pass=None,
                    meaning='data/support failure; no full-window error or model PASS')
        (output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--session',required=True);cli.add_argument('--frozen',required=True)
    cli.add_argument('--output',required=True);a=cli.parse_args()
    print(json.dumps(analyze_or_mark(a.session,a.frozen,a.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
