"""Describe stopped separated-power study without fitting incomplete development."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from tools import d1_online_policy_model as m
from tools import d1_online_policy_readout as shared


def export(plan_file, output):
    plan_file, output = Path(plan_file), Path(output)
    plan = m.p.read(plan_file); root = Path(plan['output_root'])
    receipt = m.p.read(root.parent/'FINAL_RECEIPT.json')
    if receipt['status'] != 'stopped_no_resume':
        raise ValueError('stopped study required')
    rows=[]; observed=[]; occupancy=[]; totals=Counter(); partial=[]
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        if not folder.exists():continue
        progress=folder/'artifacts/progress.jsonl'
        if not progress.exists():progress=folder/'failure_prefix/progress.jsonl'
        events=m.logs.read_lines(progress) if progress.exists() else []
        count=Counter(e['kind'] for e in events);totals.update(count)
        if not (folder/'validated.json').exists():
            partial.append(dict(index=entry['index'],event_counts=dict(count),last_phase=events[-1].get('phase') if events else None,
                                app_cleanup='unrecovered',missing_calls_not_zero=True));continue
        case=m.load_case(plan_file,plan,entry)
        requests=m.p.read(folder/'artifacts/requests.json')
        row=dict(index=entry['index'],policy=case['policy'],requests=len(requests),
                 deadline_met=sum(r['persist_complete_ns']<=r['deadline_ns'] for r in requests),
                 observed_120s_j=case['observed_120s_j'],initial_ap_c=case['common_start_ap_c'],
                 last_lane_s=case['last_lane_s'],preload_50s_w=m.energy_at(case,-20,30)/50,
                 ap_samples=len(case['observed_ap_c']),post35_peak_ap_c=max(case['observed_ap_c']))
        rows.append(row)
        durations=defaultdict(float)
        for s in case['inputs']['segments']:
            durations[s['state']]+=max(0,min(120,s['end_s'])-max(0,s['start_s']))
        if abs(sum(durations.values())-120)>1e-6:raise ValueError('state coverage')
        occupancy += [dict(index=entry['index'],state=k,seconds=v) for k,v in durations.items()]
        observed.append(dict(index=entry['index'],energy=[dict(seconds=t,j=m.energy_at(case,0,t)) for t in range(1,121)],
                             ap_seconds=case['inputs']['query_s'],ap_c=case['observed_ap_c']))
    commands=[]
    for f in sorted((root/'host_commands').glob('*/client/result.json')):
        c=m.p.read(f);args=c['command'];kind=' '.join(args[3:6])
        commands.append(dict(index=int(f.parents[1].name),kind=kind,status=c['status'],exit=c['returncode'],
                             elapsed_s=c['elapsed_seconds'],timeout_s=c['timeout_seconds'],stdout_bytes=c['stdout_bytes'],stderr_bytes=c['stderr_bytes']))
    summary=dict(status='partial_development_only',receipt_sha256=m.p.digest(root.parent/'FINAL_RECEIPT.json'),
                 root_seconds=receipt['elapsed_seconds'],adb_commands=len(commands),completed=rows,partial=partial,
                 event_counts=dict(totals),model_fitted=False,confirmation_sessions=0,accuracy_pass=None,experiment_ready=False)
    output.mkdir(parents=True,exist_ok=False)
    shared.write(output/'summary.json',summary);shared.write(output/'observed.json',observed)
    for name,data in [('commands.csv',commands),('occupancy.csv',occupancy),('sessions.csv',rows)]:
        with (output/name).open('w',encoding='utf8',newline='') as f:
            if data:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for c in observed:
        fig,ax=plt.subplots(1,2,figsize=(10,3),constrained_layout=True)
        ax[0].plot([x['seconds'] for x in c['energy']],[x['j'] for x in c['energy']]);ax[0].set(xlabel='Common seconds',ylabel='Observed cumulative J (raw=mA conditional)')
        ax[1].plot(c['ap_seconds'],c['ap_c']);ax[1].set(xlabel='Common seconds',ylabel='Observed AP C (post35 and cooling)')
        fig.suptitle('Completed development only; no new model or confirmation')
        svg=output/f"development_{c['index']}.svg"
        fig.savefig(svg);plt.close(fig)
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(export(args.plan,args.output),indent=2))
