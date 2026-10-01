"""Write-once observed ABBA comparison; no policy fitting or accuracy verdict."""
import argparse
import csv
import json
import statistics
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_analysis as observed
from tools import d1_arrival_recorded_replay_analysis as replay
from tools import d1_energy_thermal as energy


def pairs(rows):
    result=[]
    for cpu,b2 in ((0,1),(3,2)):
        for metric in ('energy_j','ap_peak_c','ap_change_c','urgent_p95_ms','normal_mean_response_ms','timely_count'):
            a,b=rows[cpu].get(metric),rows[b2].get(metric)
            result.append(dict(cpu_index=cpu,b2_index=b2,metric=metric,
                b2_minus_cpu=b-a if a is not None and b is not None else None,
                status='descriptive_only' if a is not None and b is not None else 'incomplete'))
    return result


def csv_write(file,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with file.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def session(folder,out,index,policy):
    stats=observed.summarize(folder)
    common=stats['windows'][1]
    if common['energy_j_conditional_mA'] is None or not common['ap_covered']:
        raise ValueError('incomplete whole common window; no pair result')
    artifact=folder/'artifacts';boundary=p.read(artifact/'common_boundary.json')
    origin,end=boundary['start_ns'],boundary['planned_end_ns']
    rows=p.read(artifact/'requests.json');manifest=p.read(artifact/'manifest.json')
    if manifest['source_policy']!=policy:raise ValueError('source policy differs')
    segments=replay.observed_segments(rows,origin)
    state_seconds={}
    for s in segments:state_seconds[s['state']]=state_seconds.get(s['state'],0)+s['end_s']-s['start_s']
    events=observed.read_lines(artifact/'progress.jsonl')
    samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
             for e in events if e['kind']=='power_sample']
    ap=[dict(elapsed_s=(e['mono_ns']-origin)/1e9,observed_ap_c=float(e['AP']))
        for e in observed.read_lines(folder/'thermal.jsonl') if origin<=e['mono_ns']<=end and e['AP']!='']
    cumulative=[]
    for t in sorted(set([end]+[s['mono_ns'] for s in samples if origin<s['mono_ns']<end])):
        cumulative.append(dict(elapsed_s=(t-origin)/1e9,
                              observed_cumulative_j=energy.integrate(samples,origin,t,1000)['full_energy_j']))
    initial=p.read(artifact/'start_ap.accepted.json')
    lane=[]
    for r in rows:
        lane.append(dict(ordinal=r['ordinal'],task=r['task_id'],backend=r['selected_backend'],
            scheduled_arrival_s=(r['scheduled_arrival_ns']-origin)/1e9,
            dispatch_s=(r['dispatch_ns']-origin)/1e9,lane_available_s=(r['lane_available_ns']-origin)/1e9,
            terminal_status=r['terminal_status']))
    csv_write(out/f'{index}_ap.csv',ap);csv_write(out/f'{index}_energy.csv',cumulative)
    csv_write(out/f'{index}_states.csv',segments);csv_write(out/f'{index}_schedule.csv',lane)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(3,1,figsize=(10,7),sharex=True)
    for r in lane:
        y=0 if r['backend']=='CPU' else 1
        ax[0].broken_barh([(r['dispatch_s'],r['lane_available_s']-r['dispatch_s'])],(y-.3,.6))
    ax[0].set_yticks([0,1],['CPU','GPU']);ax[0].set_title(f'{index}: {policy} recorded schedule (observed)')
    ax[1].plot([x['elapsed_s'] for x in cumulative],[x['observed_cumulative_j'] for x in cumulative]);ax[1].set_ylabel('Energy J (conditional mA)')
    ax[2].plot([x['elapsed_s'] for x in ap],[x['observed_ap_c'] for x in ap]);ax[2].set_ylabel('AP C');ax[2].set_xlabel('Common window seconds')
    fig.tight_layout();fig.savefig(out/f'{index}_observed.png',dpi=140);plt.close(fig)
    return dict(index=index,source_policy=policy,status='observed_complete_descriptive_only',planned=24,
        completed=stats['completed'],common_unfinished=stats['common_unfinished'],energy_j=common['energy_j_conditional_mA'],
        ap_start_c=float(initial['ap_c']),ap_peak_c=common['ap_peak_c'],ap_change_c=common['ap_end_c']-float(initial['ap_c']),
        ap_first_sample_c=common['ap_start_c'],ap_last_sample_c=common['ap_end_c'],
        urgent_p95_ms=stats['urgent_p95_ms'],normal_mean_response_ms=stats['normal_mean_response_ms'],
        timely_count=24-stats['urgent_deadline_miss']-stats['normal_deadline_miss'],
        actual_parallel_s=sum(v for k,v in state_seconds.items() if '+' in k),state_seconds=state_seconds,
        battery_start=stats['first_measured_battery_percent'],battery_end=stats['last_measured_battery_percent'])


def analyze(run,output):
    root,out=Path(run),Path(output)
    if out.exists():raise FileExistsError(out)
    plan=p.read(root/'frozen_collection_plan.json');receipt=p.read(root/'FINAL_RECEIPT.json')
    out.mkdir(parents=True);rows=[]
    for entry in plan['entries']:
        index=entry['index'];folder=root/f"{index:02d}_{entry['session_id']}"
        row=dict(index=index,source_policy=entry['source_policy'],status='not_validated',planned=24)
        if (folder/'validated.json').exists():
            try:row=session(folder,out,index,entry['source_policy'])
            except Exception as error:row.update(status='analysis_ineligible',error=repr(error))
        rows.append(row)
    differences=pairs(rows)
    aggregate={}
    for metric in dict.fromkeys(d['metric'] for d in differences):
        values=[d['b2_minus_cpu'] for d in differences if d['metric']==metric and d['b2_minus_cpu'] is not None]
        aggregate[metric]=dict(complete_pairs=len(values),mean=statistics.mean(values) if len(values)==2 else None,
                               minimum=min(values) if values else None,maximum=max(values) if values else None)
    result=dict(status=receipt['status'],sessions=rows,pairs=differences,descriptive_pair_summary=aggregate,
        plan_sha256=p.digest(root/'frozen_collection_plan.json'),receipt_sha256=p.digest(root/'FINAL_RECEIPT.json'),
        meaning='Recorded schedules only; two order-reversed pairs are not precision/causal/model validation',
        accuracy_pass=None,policy_superiority=None,strict_support=False,experiment_ready=False)
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    csv_write(out/'sessions.csv',[{k:v for k,v in r.items() if k!='state_seconds'} for r in rows]);csv_write(out/'pairs.csv',differences)
    images=''.join(f'<h2>{r["index"]} {r["source_policy"]}</h2><img width="900" src="{r["index"]}_observed.png">'
                   for r in rows if r['status']=='observed_complete_descriptive_only')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>기록 일정 비교</title><h1>기록 일정 직접 관측 비교</h1><p>온라인 정책 검증·일반 모형 정확도·우월성 PASS 아님. 조건부 전류 단위, 절대 정확도 미인증.</p><a href="summary.json">수치와 누락</a> · <a href="pairs.csv">B2−CPU 사전 두 쌍</a>'+images,encoding='utf-8')
    return result


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--run',required=True);cli.add_argument('--output',required=True)
    args=cli.parse_args();print(json.dumps(analyze(args.run,args.output),ensure_ascii=False,indent=2))
