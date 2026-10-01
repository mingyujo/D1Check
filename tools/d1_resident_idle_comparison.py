"""PC-only posthoc idle power comparison; no fitting, device calls or policy cost."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_analysis as descriptive
from tools import d1_arrival_recorded_replay_analysis as replay
from tools import d1_energy_thermal as energy

FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'


def windows(samples, segments, origin, frozen):
    if not segments or abs(segments[0]['start_s']) > 1e-9 or abs(segments[-1]['end_s']-120) > 1e-8:
        raise ValueError('complete exact 120s state map required')
    if any(abs(a['end_s']-b['start_s']) > 1e-9 or a['end_s'] <= a['start_s']
           for a,b in zip(segments, segments[1:])) or segments[-1]['end_s'] <= segments[-1]['start_s']:
        raise ValueError('state gaps, overlap or empty interval')
    active = [s for s in segments if s['state'] != 'idle']
    if not active:
        raise ValueError('recorded load boundaries required')
    # Unsupported states reject the whole comparison, never zero-cost substitution.
    for s in segments:
        if replay.state_key(s['state']) not in frozen['whole_device_power_w']:
            raise ValueError('unsupported state')
    first, last = active[0]['start_s'], active[-1]['end_s']
    ranges = [('pre_load',0.,first),('load_envelope',first,last),('post_load_idle',last,120.)]
    result = []
    for phase,lo,hi in ranges:
        if hi <= lo:
            continue
        observed = energy.integrate(samples,origin+round(lo*1e9),origin+round(hi*1e9),1000)
        predicted = sum(max(0.,min(hi,s['end_s'])-max(lo,s['start_s'])) *
                        frozen['whole_device_power_w'][replay.state_key(s['state'])] for s in segments)
        actual = observed['full_energy_j']
        result.append(dict(phase=phase,start_s=lo,end_s=hi,duration_s=hi-lo,
            observed_j=actual,predicted_j=predicted,signed_error_j=None if actual is None else predicted-actual,
            observed_mean_w=None if actual is None else actual/(hi-lo),predicted_mean_w=predicted/(hi-lo),
            missing_seconds=observed['missing_s'],interpretation='phase arithmetic; not causal or fitted power'))
    # Long idle only, trimming to observed sensor midpoints excludes every
    # trapezoid crossing a lane boundary. Report omitted time instead of filling.
    times=sorted(set(s['mono_ns'] for s in samples))
    for s in segments:
        if s['state'] != 'idle' or s['end_s']-s['start_s'] < 10:
            continue
        points=[t for t in times if origin+round(s['start_s']*1e9)<=t<=origin+round(s['end_s']*1e9)]
        if len(points)<2:
            result.append(dict(phase='sensor_pure_long_idle',start_s=s['start_s'],end_s=s['end_s'],
                duration_s=s['end_s']-s['start_s'],observed_j=None,predicted_j=None,signed_error_j=None,
                observed_mean_w=None,predicted_mean_w=None,missing_seconds=s['end_s']-s['start_s'],
                interpretation='no valid interior bracket; not zero'))
            continue
        observed=energy.integrate(samples,points[0],points[-1],1000)
        duration=(points[-1]-points[0])/1e9
        predicted=duration*frozen['whole_device_power_w']['resident_idle']
        actual=observed['full_energy_j']
        result.append(dict(phase='sensor_pure_long_idle',start_s=(points[0]-origin)/1e9,
            end_s=(points[-1]-origin)/1e9,duration_s=duration,observed_j=actual,predicted_j=predicted,
            signed_error_j=None if actual is None else predicted-actual,
            observed_mean_w=None if actual is None else actual/duration,
            predicted_mean_w=frozen['whole_device_power_w']['resident_idle'],
            missing_seconds=observed['missing_s'],
            interpretation=f"boundary_trimmed_seconds={s['end_s']-s['start_s']-duration:.9f}; not whole120s"))
    return result


def compare(source_root, frozen_file, output):
    source_root, frozen_file, output = map(Path,(source_root,frozen_file,output))
    if output.exists():
        raise FileExistsError('fresh comparison output only')
    if p.digest(frozen_file) != FROZEN_SHA:
        raise ValueError('original frozen coefficients changed')
    frozen=p.read(frozen_file)
    specifications=[('B2_queue_seen','energy_ap_recorded_b2_diag_run_v6','00_'),
        ('idle_development_seen','energy_ap_idle_response_run_v1','00_'),
        ('idle_confirmation_seen','energy_ap_idle_response_run_v1','01_'),
        ('CGDC_transfer_seen','energy_ap_cgdc_transfer_run_v2','00_')]
    rows=[]; sources={}; metadata=[]
    for name,run,prefix in specifications:
        root=source_root/run
        folders=list(root.glob(prefix+'*'))
        if len(folders)!=1:
            raise ValueError('one exact recorded session required: '+name)
        folder=folders[0]; a=folder/'artifacts'
        required=[root/'FINAL_RECEIPT.json',folder/'validated.json',a/'common_boundary.json',
            a/'requests.json',a/'progress.jsonl',a/'manifest.json',a/'start_ap.accepted.json',
            folder/'before_session_battery.txt',folder/'thermal.jsonl']
        for f in required:
            sources[name+'/'+f.name]=p.digest(f)
        if p.read(root/'FINAL_RECEIPT.json')['status']!='completed_descriptive_only' or \
                p.read(folder/'validated.json')['status']!='eligible_descriptive_only':
            raise ValueError('incomplete recorded session: '+name)
        boundary=p.read(a/'common_boundary.json'); req=p.read(a/'requests.json')
        if len(req)!=24 or any(r['terminal_status']!='succeeded' for r in req):
            raise ValueError('complete 24 planned denominator required')
        origin=boundary['start_ns']
        if boundary['planned_end_ns']-origin != 120_000_000_000:
            raise ValueError('changed window')
        segments=replay.observed_segments(req,origin)
        events=descriptive.read_lines(a/'progress.jsonl')
        samples=[dict(x,mono_ns=(x['snapshot_start_ns']+x['sensor_read_end_ns'])//2)
                 for x in events if x['kind']=='power_sample']
        case=windows(samples,segments,origin,frozen)
        whole=energy.integrate(samples,origin,origin+120_000_000_000,1000)
        phases=[r for r in case if r['phase']!='sensor_pure_long_idle']
        if whole['full_energy_j'] is not None and all(x['observed_j'] is not None for x in phases):
            if abs(sum(x['observed_j'] for x in phases)-whole['full_energy_j'])>1e-8:
                raise ValueError('phase conservation failed')
        rows.extend(dict(case=name,**x) for x in case)
        manifest=p.read(a/'manifest.json'); battery=(folder/'before_session_battery.txt').read_text(encoding='utf-8')
        value=lambda k: re.search(r'(?m)^\s*'+k+r':\s*(\d+)\s*$',battery).group(1)
        metadata.append(dict(case=name,initial_ap_c=p.read(a/'start_ap.accepted.json')['ap_c'],
            battery_percent=int(value('level')),bat_c=int(value('temperature'))/10,
            scenario=manifest['scenario'],data_role='posthoc comparison of already seen sessions',
            observation_protocol=manifest.get('start_ap_gate'),
            whole_observed_j=whole['full_energy_j'],missing_seconds=whole['missing_s']))
    output.mkdir(parents=True)
    with (output/'idle_power.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(version='resident-idle-posthoc-comparison-v1',starting_inputs_sha256=sources,
        frozen_sha256=FROZEN_SHA,analysis_code_sha256=p.digest(__file__),cases=metadata,
        frozen_idle_w=frozen['whole_device_power_w']['resident_idle'],new_fitted_parameters=0,
        device_commands=0,strict_support=False,accuracy_pass=None,policy_rank=None,experiment_ready=False,
        interpretation='sensor-pure long idle after boundary trimming; context/history differ; no causal temperature-power law')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    plot(rows, summary['frozen_idle_w'], output)
    if p.digest(frozen_file)!=FROZEN_SHA:
        raise ValueError('frozen file changed during analysis')
    return summary


def plot(rows, frozen_w, output):
    """Descriptive intervals, not confidence bounds or a fitted idle coefficient."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    idle=[r for r in rows if r['phase']=='sensor_pure_long_idle']
    fig,ax=plt.subplots(figsize=(10,4.6))
    for i,r in enumerate(idle):
        if r['observed_mean_w'] is not None:
            ax.bar(i,r['observed_mean_w'],color='#326b8e')
            ax.text(i,r['observed_mean_w']+.015,f"{r['observed_mean_w']:.3f}",ha='center')
        else:
            ax.text(i,0.1,'MISSING',ha='center')
    ax.axhline(frozen_w,color='#a64936',linestyle='--',label=f'Original frozen resident idle: {frozen_w:.3f} W')
    ax.set_xticks(range(len(idle)),[r['case'].replace('_seen','').replace('_',' ')+'\n'+
        f"{r['start_s']:.1f}–{r['end_s']:.1f} s" for r in idle],rotation=20,ha='right',fontsize=8)
    ax.set_ylabel('Observed whole-device mean W (raw=mA conditional)')
    ax.set_title('Recorded long idle: boundary-crossing sensor intervals excluded\nPosthoc; context/history differ; no causal law or policy ranking')
    ax.set_ylim(0,max([frozen_w]+[r['observed_mean_w'] or 0 for r in idle])*1.2)
    ax.legend(loc='upper right',fontsize=8)
    fig.tight_layout()
    for extension in ('png','svg'):
        fig.savefig(Path(output)/('idle_power.'+extension),dpi=160)
    plt.close(fig)


def main():
    q=argparse.ArgumentParser(description=__doc__)
    for name in ('source-root','frozen','output'):q.add_argument('--'+name,required=True)
    a=q.parse_args();print(json.dumps(compare(a.source_root,a.frozen,a.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
