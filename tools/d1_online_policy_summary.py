"""Post-freeze descriptive tables only; never fit/select a model or operate a device."""
import argparse
import csv
import json
from pathlib import Path
from tools import d1_arrival_plan as p


def summarize(bundle, output):
    bundle,output=Path(bundle),Path(output)
    values=p.read(bundle/'evaluation.json');rows=[];windows=[]
    for c in values:
        observed={x['common_s']:x['observed_j'] for x in c['observed_energy_path']};observed[0]=0.
        for kind,v in c['outputs'].items():
            predicted={x['common_s']:x['predicted_j'] for x in v['energy_path']}
            # Fixed 5s arithmetic decomposition, not independently measured state power.
            residual=[]
            for a in range(0,120,5):
                b=a+5;error=(predicted[b]-predicted[a])-(observed[b]-observed[a]);residual.append(error)
                states=sorted({s['state'] for s in c['actual_segments'] if s['end_s']>a and s['start_s']<b})
                windows.append(dict(id=c['id'],phase=c['phase'],mode=kind,start_s=a,end_s=b,observed_j=observed[b]-observed[a],
                    predicted_j=predicted[b]-predicted[a],signed_error_j=error,states='|'.join(states),mixed=len(states)>1))
            total=sum(residual)
            if abs(total-v['energy_signed_error_j'])>1e-8:raise ValueError('energy accounting does not close')
            timing=c['timing'];dt=[abs(x['dispatch_error_ms']) for x in timing];lane=[abs(x['lane_error_ms']) for x in timing]
            rows.append(dict(id=c['id'],phase=c['phase'],policy=c['policy'],mode=kind,initial_ap_c=c['common_start_ap_c'],
                observed_120_j=c['observed_120s_j'],predicted_120_j=v['whole_120s_j'],signed_120_j=total,
                observed_future_35_120_j=observed[120]-observed[35],predicted_future_35_120_j=predicted[120]-predicted[35],
                signed_future_35_120_j=(predicted[120]-predicted[35])-(observed[120]-observed[35]),
                positive_5s_residual_j=sum(max(0,x) for x in residual),negative_5s_residual_j=sum(min(0,x) for x in residual),
                cumulative_abs_max_j=max(abs(predicted[t]-observed[t]) for t in observed),
                dispatch_mae_ms=sum(dt)/len(dt),lane_mae_ms=sum(lane)/len(lane),
                parallel_s=sum(max(0,min(120,s['end_s'])-s['start_s']) for s in c['actual_segments'] if '+' in s['state']),
                observed_urgent_p95_ms=c['service']['actual_urgent']['p95_ms'],predicted_urgent_p95_ms=c['service']['predicted_urgent']['p95_ms'],
                observed_deadline_met=c['service']['actual_all']['deadline_met'],predicted_deadline_met=c['service']['predicted_all']['deadline_met'],
                **v['ap_scores']))
    output.mkdir(parents=True,exist_ok=False)
    for name,data in [('detailed_metrics.csv',rows),('energy_windows.csv',windows)]:
        with (output/name).open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    metadata=dict(source_evaluation_sha256=p.digest(bundle/'evaluation.json'),fitting=0,device_commands=0,
        interval_interpretation='5s arithmetic differences; mixed states not separate power identification',
        prediction_inputs='AP before35s and W10..30s; 35..120 is prospective; full120 includes initialization period',
        timing_interpretation='forecast schedule errors, repeated for both cost output rows; actual schedule conditional is not a schedule prediction',
        accuracy_pass=None,experiment_ready=False)
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    return rows

def render_schedules(bundle,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records=[r for r in p.read(Path(bundle)/'evaluation.json') if r['phase']=='confirmation']
    if len(records)!=6:raise ValueError('six completed confirmations required')
    fig,axes=plt.subplots(3,2,figsize=(15,9),constrained_layout=True)
    rows=[]
    for c,ax in zip(records,axes.flat):
        for source,key in [('actual','actual_rows'),('forecast','forecast_ledger')]:
            for r in c[key]:
                backend=r['selected_backend'] if source=='actual' else r['backend']
                lane=(0 if source=='actual' else 2)+(backend=='GPU')
                begin=r['dispatch_ns']/1e9;end=r['lane_available_ns']/1e9
                if not 0<=begin<end<=120:raise ValueError('schedule outside full observation')
                ax.broken_barh([(begin,end-begin)],(lane-.35,.7),facecolors='#e58532' if r['priority']=='urgent' else '#3682b5')
                rows.append(dict(case=c['id'],source=source,request_id=r.get('request_id',r.get('id')),backend=backend,priority=r['priority'],
                    scheduled_s=(r['scheduled_arrival_ns'] if source=='actual' else r['arrival_ns'])/1e9,
                    dispatch_s=begin,output_ready_s=r['output_ready_ns']/1e9,persist_s=r['persist_complete_ns']/1e9,
                    worker_release_s=r['worker_release_ns']/1e9,lane_available_s=end))
        ax.set_yticks([0,1,2,3],['actual CPU','actual GPU','forecast CPU','forecast GPU']);ax.set_xlim(30,100)
        ax.set_title(c['id'],fontsize=9);ax.set_xlabel('Common seconds');ax.grid(axis='x',alpha=.2)
    fig.suptitle('Independent confirmation: orange urgent classification, blue normal detection; actual lane occupancy')
    output=Path(output);fig.savefig(output/'schedules.svg');fig.savefig(output/'schedules.png',dpi=130);plt.close(fig)
    with (output/'request_boundaries.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return len(rows)

def compare_same_initial(bundle,output):
    from tools import d1_online_policy_model as model
    import math
    bundle=Path(bundle);entries=p.read(bundle/'initial_inputs.json')
    # Fixed first confirmation CPU case, not the best observed outcome.
    candidates=[c for c in entries if c['phase']=='confirmation' and c['policy']==model.POLICIES[0]]
    if len(candidates)!=2:raise ValueError('two CPU confirmations required')
    c=candidates[0];frozen=p.read(bundle/'model.json');rows=[]
    for policy in model.POLICIES:
        result,segments=model.forecast(c['initial'],c['manifest_requests'],policy,frozen)
        costs=model.costs(segments,c['initial'],list(range(35,181)),frozen,180)
        # Engine response_ns is a duration from scheduled arrival, not an event timestamp.
        urgent=[r['response_ns']/1e6 for r in result['ledger'] if r['priority']=='urgent']
        rows.append(dict(initial_case_id=c['id'],policy=policy,whole_120_j=costs['whole_120s_j'],future_35_120_j=costs['prospective_35_120s_j'],
            peak_ap_35_180_c=max(costs['ap_path']),urgent_p95_ms=sorted(urgent)[math.ceil(.95*len(urgent))-1],
            deadline_met=sum(r['response_ns']<=r['deadline_offset_ns'] for r in result['ledger']),planned=96,
            interpretation='same-initial-condition model counterfactual; not a measured matched pair; no superiority PASS'))
    with (Path(output)/'same_initial_policy_predictions.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return rows

if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--bundle',required=True);q.add_argument('--output',required=True);a=q.parse_args()
    rows=summarize(a.bundle,a.output);requests=render_schedules(a.bundle,a.output);compare_same_initial(a.bundle,a.output)
    print(json.dumps(dict(rows=len(rows),request_rows=requests,device_commands=0)))
