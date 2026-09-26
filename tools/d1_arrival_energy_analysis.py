"""Strict descriptive accounting for completed synthetic-arrival Android sessions.

No fitting, no device access, no imputation. A24 whole-device current uses the
explicit likely-mA hypothesis; absolute joules are not certified.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_energy_thermal as energy


def require(ok, message):
    if not ok: raise ValueError(message)


def read_lines(path):
    raw=Path(path).read_bytes()
    require(not raw or raw.endswith(b'\n'),'incomplete final record')
    return [json.loads(line) for line in raw.splitlines()]


def lane_overlap_s(rows):
    """API/worker occupancy overlap, never a GPU-kernel overlap claim."""
    cpu=sorted((r['execution_start_ns'],r['lane_available_ns']) for r in rows if r['selected_backend']=='CPU')
    gpu=sorted((r['execution_start_ns'],r['lane_available_ns']) for r in rows if r['selected_backend']=='GPU')
    i=j=0;total=0
    while i<len(cpu) and j<len(gpu):
        total+=max(0,min(cpu[i][1],gpu[j][1])-max(cpu[i][0],gpu[j][0]))
        if cpu[i][1]<gpu[j][1]:i+=1
        else:j+=1
    return total/1e9


def summarize(folder):
    folder=Path(folder); a=folder/'artifacts'
    m=p.read(a/'manifest.json'); boundary=p.read(a/'common_boundary.json')
    rows=p.read(a/'requests.json'); summary=p.read(a/'summary.json');cleanup=p.read(a/'cleanup.json')
    require(summary['status']=='completed' and cleanup['status']=='completed','completed app only')
    require(len(rows)==24 and len({x['request_id'] for x in rows})==24,'request denominator')
    events=read_lines(a/'progress.jsonl')
    require([x['sequence'] for x in events]==list(range(len(events))),'journal continuity')
    samples=[]
    for e in events:
        if e['kind']!='power_sample':continue
        require(e['snapshot_start_ns']<=e['sensor_read_end_ns']<=e['state_snapshot_ns']<=e['mono_ns'], 'clock bracket')
        require(e['sensor_read_end_ns']-e['snapshot_start_ns']<=2_000_000_000,'slow device sample')
        s=dict(e);s['mono_ns']=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2;samples.append(s)
    thermal=read_lines(folder/'thermal.jsonl')
    require(all(t['sampling_uncertainty_ns']<=2_000_000_000 for t in thermal),'AP clock bracket')
    baseline_start=[e['mono_ns'] for e in events if e['phase']=='resident_baseline' and e['kind']=='phase_start']
    baseline_end=[e['mono_ns'] for e in events if e['phase']=='resident_baseline' and e['kind']=='phase_end']
    cooling_end=[e['mono_ns'] for e in events if e['phase']=='resident_cooling' and e['kind']=='phase_end']
    require(len(baseline_start)==len(baseline_end)==len(cooling_end)==1,'phase bounds')
    origin=boundary['start_ns']; common_end=boundary['planned_end_ns']
    require(common_end-origin==120_000_000_000 and boundary['end_ns']>=common_end,'common window')
    ap_base=[float(t['AP']) for t in thermal if baseline_start[0]<=t['mono_ns']<=baseline_end[0] and t['AP']!='']
    require(len(ap_base)>=8,'baseline AP coverage')
    baseline=energy.integrate(samples,baseline_start[0],baseline_end[0],1000)
    require(baseline['covered_s']>=.95*baseline['duration_s'],'baseline current coverage')
    reference_power=baseline['mean_power_w']
    completion=max(r['persist_complete_ns'] for r in rows if r['terminal_status']=='succeeded')
    unfinished=sum(r['terminal_status']!='succeeded' or r.get('persist_complete_ns',10**30)>common_end for r in rows)
    urgent=[r for r in rows if r['priority']=='urgent']; normal=[r for r in rows if r['priority']=='normal']
    require(len(urgent)==6 and len(normal)==18,'priority denominators')
    def response_ns(r):return r.get('output_ready_ns') if r['priority']=='urgent' else r.get('persist_complete_ns')
    def served(r):
        response=response_ns(r)
        return r['terminal_status']=='succeeded' and response is not None and response<=common_end
    urgent_times=sorted((response_ns(r)-r['scheduled_arrival_ns'])/1e6 for r in urgent if served(r))
    normal_times=[(response_ns(r)-r['scheduled_arrival_ns'])/1e6 for r in normal if served(r)]
    def missed(r):
        response=response_ns(r)
        return not served(r) or response>r['deadline_ns']
    def window(label,start,end):
        power=energy.integrate(samples,start,end,1000)
        relevant=[t for t in thermal if start<=t['mono_ns']<=end and t['AP']!='']
        gaps=[relevant[0]['mono_ns']-start,end-relevant[-1]['mono_ns']] + [b['mono_ns']-a['mono_ns'] for a,b in zip(relevant,relevant[1:])] if relevant else [end-start]
        ap_covered=len(relevant)>=2 and max(gaps)<=10_000_000_000
        return dict(label=label,start_ns=start,end_ns=end,duration_s=(end-start)/1e9,
                    energy_j_conditional_mA=power['full_energy_j'],energy_coverage_s=power['covered_s'],
                    excess_vs_resident_j=(power['full_energy_j']-reference_power*power['duration_s']) if power['full_energy_j'] is not None else None,
                    ap_start_c=float(relevant[0]['AP']) if ap_covered else None,
                    ap_peak_c=max(float(t['AP']) for t in relevant) if ap_covered else None,
                    ap_end_c=float(relevant[-1]['AP']) if ap_covered else None,
                    ap_covered=ap_covered)
    return dict(session_id=m['session_id'],session_order=int(folder.name[:2]),phase=m['phase'],scenario=m['scenario'],policy=m['policy'],
                planned=24,completed=sum(r['terminal_status']=='succeeded' for r in rows),
                common_unfinished=unfinished,baseline_ap_median_c=statistics.median(ap_base),
                first_measured_battery_percent=samples[0].get('battery_level'),
                last_measured_battery_percent=samples[-1].get('battery_level'),
                urgent_denominator=6,urgent_completed_in_window=len(urgent_times),
                urgent_p95_ms=urgent_times[math.ceil(.95*len(urgent_times))-1] if urgent_times else None,
                urgent_deadline_miss=sum(missed(r) for r in urgent),
                normal_denominator=18,normal_completed_in_window=len(normal_times),
                normal_mean_response_ms=statistics.mean(normal_times) if normal_times else None,
                normal_deadline_miss=sum(missed(r) for r in normal),
                work_completion_ns=completion,final_lane_release_ns=max(r['lane_available_ns'] for r in rows),
                work_completion_s=(completion-origin)/1e9,
                api_worker_overlap_s=lane_overlap_s(rows),
                current_unit='A24 likely mA raw; absolute accuracy uncertified',
                sampling='whole-device ~1s battery / ~2s host AP; not request-level or CPU/GPU rail energy',
                windows=[window('resident_baseline',baseline_start[0],baseline_end[0]),
                         window('common_120s',origin,common_end),
                         window('task_completion',origin,completion) if completion>=origin else None,
                         window('measured_preparation_and_cooling',samples[0]['mono_ns'],cooling_end[0])])


def main():
    cli=argparse.ArgumentParser();cli.add_argument('--run',required=True);cli.add_argument('--output',required=True)
    a=cli.parse_args();root=Path(a.run);out=Path(a.output)
    require(not out.exists(),'write-once output')
    rows=[]
    for folder in sorted(root.glob('[0-9][0-9]_*')):
        if (folder/'validated.json').is_file():rows.append(summarize(folder))
    require(rows,'no completed eligible session')
    out.mkdir(parents=True)
    (out/'session_metrics.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'session_windows.csv').open('x',newline='',encoding='utf-8') as f:
        names=['session_id','session_order','phase','scenario','policy','planned','completed','common_unfinished','label',
               'baseline_ap_median_c','first_measured_battery_percent','last_measured_battery_percent',
               'urgent_denominator','urgent_completed_in_window','urgent_p95_ms','urgent_deadline_miss',
               'normal_denominator','normal_completed_in_window','normal_mean_response_ms','normal_deadline_miss',
               'work_completion_s','api_worker_overlap_s',
               'duration_s','energy_j_conditional_mA','energy_coverage_s','excess_vs_resident_j',
               'ap_start_c','ap_peak_c','ap_end_c','ap_covered']
        writer=csv.DictWriter(f,fieldnames=names);writer.writeheader()
        for row in rows:
            for window in row['windows']:
                if window: writer.writerow({k:(row|window).get(k) for k in names})
    grouped={(r['phase'],r['scenario'],r['policy']):r for r in rows}
    with (out/'pair_differences.csv').open('x',newline='',encoding='utf-8') as f:
        names=['phase','scenario','status','metric','fixed_minus_cpu','unit','meaning']
        writer=csv.DictWriter(f,fieldnames=names);writer.writeheader()
        for phase in ('development','confirmation'):
            for scenario in ('low','queue','burst'):
                cpu=grouped.get((phase,scenario,'CPU_URGENT'))
                fixed=grouped.get((phase,scenario,'FIXED_SPLIT'))
                if not (cpu and fixed):
                    writer.writerow(dict(phase=phase,scenario=scenario,status='incomplete_pair'))
                    continue
                metrics=[('work_completion_s',fixed['work_completion_s'],cpu['work_completion_s'],'s'),
                         ('urgent_p95_ms',fixed['urgent_p95_ms'],cpu['urgent_p95_ms'],'ms'),
                         ('common_energy_j',fixed['windows'][1]['energy_j_conditional_mA'],cpu['windows'][1]['energy_j_conditional_mA'],'J_conditional_mA'),
                         ('common_ap_peak_c',fixed['windows'][1]['ap_peak_c'],cpu['windows'][1]['ap_peak_c'],'degC')]
                for name,a,b,unit in metrics:
                    writer.writerow(dict(phase=phase,scenario=scenario,status='descriptive_only',metric=name,
                                         fixed_minus_cpu=a-b if a is not None and b is not None else None,
                                         unit=unit,meaning='different sessions; order/start-temperature confounding; not causal'))
    print(json.dumps(dict(sessions=len(rows),output=str(out)),ensure_ascii=False))

if __name__=='__main__':main()
