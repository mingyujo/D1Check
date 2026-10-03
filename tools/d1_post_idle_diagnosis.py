"""Read-only, post-hoc localization of separated-power idle prediction error."""
import argparse
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from tools import d1_online_policy_model as model
from tools import d1_energy_thermal as energy


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x]


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def csv_write(path, rows):
    with Path(path).open('w', encoding='utf8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def kind(command):
    args = command[3:]
    if args == ['exec-out', 'cat', '/proc/uptime']: return 'uptime'
    if args == ['shell', 'dumpsys', 'thermalservice']: return 'thermal'
    if args[:2] == ['shell', 'run-as'] and 'ls' in args: return 'listing'
    if args[:3] == ['shell', 'sh', '-c']: return 'screen'
    return 'other'


def host_record(file):
    r = read(file)
    item = dict(index=int(file.parents[1].name), kind=kind(r['command']),
                start=r['monotonic_start'], end=r['monotonic_end'],
                status=r['status'], exit=r.get('returncode'))
    if item['kind'] == 'uptime' and item['exit'] == 0:
        item['uptime'] = float((file.parent/'stdout.bin').read_text().split()[0])
    return item


def clock_map(records, origin_s):
    """Approximate host->device map from read brackets, not wall-clock equality.

    Uptime emission falls inside client start/end, with 10ms text quantization.
    Interpolation assumes locally stable offset; uncertainty is diagnostic only.
    """
    anchors = [r for r in records if 'uptime' in r]
    if len(anchors) < 2: raise ValueError('missing clock anchors')
    xs = [(r['start']+r['end'])/2 for r in anchors]
    ys = [r['uptime']-origin_s for r in anchors]
    widths = [(r['end']-r['start'])/2+.01 for r in anchors]
    def convert(t):
        if t < xs[0] or t > xs[-1]: return None
        return float(np.interp(t, xs, ys))
    return convert, max(widths)


def export(root, output):
    root, output = Path(root), Path(output)
    cases = read(root/'confirmation_cases.json')
    if len(cases) != 6: raise ValueError('retain all six confirmation sessions')
    if output.exists() and any(output.iterdir()): raise ValueError('output already populated')
    output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        host = sorted(pool.map(host_record, (root/'confirmation/host_commands').glob('*/client/result.json')), key=lambda r:r['index'])
    summaries=[]; windows=[]; power=[]; thermal=[]; lifecycle=[]
    bindings={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
              for name in ['confirmation_cases.json','model_freeze.json']}
    for i,c in enumerate(cases):
        folder=next((root/'confirmation').glob(f'{i:02d}_*')); origin=c['origin_ns']; last=c['last_lane_s']
        ev=lines(folder/'artifacts/progress.jsonl'); th=lines(folder/'thermal.jsonl')
        raw_power=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
                   for e in ev if e['kind']=='power_sample']
        raw_rows=read(folder/'artifacts/requests.json')
        if (raw_power!=c['power_samples'] or read(folder/'artifacts/common_boundary.json')['start_ns']!=origin
                or len(raw_rows)!=96 or any(r['terminal_status']!='succeeded' for r in raw_rows)
                or abs((max(r['lane_available_ns'] for r in raw_rows)-origin)/1e9-last)>1e-9):
            raise ValueError('raw/case origin, sample or lane identity mismatch')
        for f in [folder/'thermal.jsonl',folder/'artifacts/progress.jsonl',folder/'artifacts/requests.json',folder/'artifacts/common_boundary.json']:
            bindings[str(f.relative_to(root)).replace('\\','/')]=hashlib.sha256(f.read_bytes()).hexdigest()
        convert,uncertainty=clock_map(host,origin/1e9)
        commands=[]
        for r in host:
            t=convert((r['start']+r['end'])/2)
            if t is not None and -30<=t<=180: commands.append(dict(r,t=t))
        samples=c['power_samples']; post=[s for s in samples if last<(s['mono_ns']-origin)/1e9<120]
        times=[(s['mono_ns']-origin)/1e9 for s in samples]
        for s,t in zip(samples,times):
            power.append(dict(case=i,t_s=t,watts=energy.discharge_w(s,1000),active_lanes=len(s['active']),
                              waiting=s.get('waiting_requests'),charge_raw=s['charge_counter_raw'],voltage_mv=s['voltage_mV']))
        for t in th:
            thermal.append(dict(case=i,t_s=(t['mono_ns']-origin)/1e9,uncertainty_s=t['sampling_uncertainty_ns']/1e9,
                                **{k:float(t[k]) for k in ['AP','BAT','SKIN','PA']}))
        for e in ev:
            if e['kind'] in ('activity_lifecycle','phase_start','phase_end','session_failure','finish_request'):
                lifecycle.append(dict(case=i,t_s=(e['mono_ns']-origin)/1e9,kind=e['kind'],phase=e['phase'],callback=e.get('callback','')))
        for a in range(0,120,5):
            b=a+5; selected=[r for r in commands if a<=r['t']<b]
            windows.append(dict(case=i,start_s=a,end_s=b,observed_j=model.energy_at(c,a,b),
                                lane_occupied_s=float(sum(model.exposure(c['inputs']['segments'],a,b))),
                                commands=len(selected),client_wait_s=sum(r['end']-r['start'] for r in selected),
                                **{k:sum(r['kind']==k for r in selected) for k in ['uptime','thermal','listing','screen','other']}))
        common=[s for s in samples if 0<=(s['mono_ns']-origin)/1e9<=120]
        last_events=[e for e in ev if e['mono_ns']>origin+last*1e9 and e['mono_ns']<origin+120e9]
        screens=[read(f) for f in (folder/'screen_observations').glob('*.json')]
        summaries.append(dict(case=i,policy=c['policy'],last_lane_s=last,
            observed_120s_j=model.energy_at(c,0,120),post75_120_j=model.energy_at(c,75,120),
            post_lane_energy_j=model.energy_at(c,last,120),post_lane_samples=len(post),
            post_lane_active_samples=sum(bool(s['active']) for s in post),
            post_lane_waiting_samples=sum(s['waiting_requests']!=0 for s in post),
            max_power_sample_gap_s=max(np.diff(times)),max_sensor_read_s=max((s['sensor_read_end_ns']-s['snapshot_start_ns'])/1e9 for s in common),
            plugged_values=sorted({s['plugged'] for s in common}),thermal_values=sorted({s['thermal_status'] for s in common}),
            battery_temperature_range_c=[min(s['battery_temperature_deci_c'] for s in common)/10,max(s['battery_temperature_deci_c'] for s in common)/10],
            all_interactive=all(s['interactive'] for s in common),all_memory_admitted=all(s['admission_reason']=='admit' for s in common),
            screen_statuses=sorted({s['status'] for s in screens}),
            post_lane_event_kinds=sorted({e['kind'] for e in last_events}),
            host_map_max_half_bracket_s=uncertainty,
            common_host_commands=sum(0<=r['t']<120 for r in commands),
            common_host_failures=sum(0<=r['t']<120 and (r['status']!='returned' or r['exit']!=0) for r in commands)))
        assert abs(sum(r['observed_j'] for r in windows if r['case']==i)-c['observed_120s_j'])<1e-6
    write(output/'summary.json',summaries);write(output/'source_hashes.json',bindings)
    for name,rows in [('windows.csv',windows),('power.csv',power),('thermal.csv',thermal),('lifecycle.csv',lifecycle)]:csv_write(output/name,rows)
    write(output/'scope.json',dict(post_hoc=True,refits=0,excluded_sessions=0,device_commands=0,
        cause='unidentified; benchmark idle does not identify whole-device idle',
        clock='device elapsedRealtime/uptime bracket; host interpolation approximate, not event causality',
        current_unit='raw=mA conditional; absolute accuracy uncalibrated',
        uncertainty_interval=None,experiment_ready=False))
    plot(output)
    return dict(output=str(output),sessions=len(cases),device_commands=0)


def plot(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=Path(folder)
    def rows(name):
        with (folder/name).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))
    windows=rows('windows.csv');thermal=rows('thermal.csv')
    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
    for i,label,color in [(0,'CPU first','#2471a3'),(5,'CPU last','#c0392b')]:
        ws=[r for r in windows if int(r['case'])==i]
        ts=[r for r in thermal if int(r['case'])==i and 0<=float(r['t_s'])<=120]
        axes[0].plot([float(r['start_s'])+2.5 for r in ws],[float(r['observed_j'])/5 for r in ws],label=label,color=color)
        axes[1].plot([float(r['t_s']) for r in ts],[float(r['AP']) for r in ts],'.-',label=label+' AP',color=color)
        axes[2].step([float(r['start_s']) for r in ws],[int(r['commands']) for r in ws],where='post',label=label,color=color)
    for ax in axes:
        ax.axvspan(75,120,color='gray',alpha=.12,label='Both benchmark lanes idle')
        ax.legend(fontsize=8);ax.grid(alpha=.2);ax.set_xlim(0,120)
    axes[0].set_ylabel('Observed whole-device W\n5-second mean')
    axes[1].set_ylabel('HAL AP (C)')
    axes[2].set(ylabel='Host commands / 5 seconds\napproximate clock mapping',xlabel='Common time (s)')
    axes[2].set_ylim(0,18)
    fig.suptitle('Post-hoc localization: observation co-occurrence, not causal attribution')
    target=folder/'post_idle.svg';fig.savefig(target);plt.close(fig)
    target.write_text('\n'.join(s.rstrip() for s in target.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')


if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--root',required=True);q.add_argument('--output',required=True);a=q.parse_args()
    print(export(a.root,a.output))
