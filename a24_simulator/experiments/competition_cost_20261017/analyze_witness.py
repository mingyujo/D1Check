"""Saved-only input competition and two explicitly separated cost observers."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
import state_cost as C,relative_drain as R
G.OWN_TOKENS+=('competition_cost_20261017','s26-state-aware-atc-','state_recovery_owner')

def competition(row):
    n=dict(actor_calls=0,dispatch_calls=0,multiple_ready_dispatch=0,different_task_dispatch=0,
           different_deadline_dispatch=0,different_priority_dispatch=0,FIFO_EDF_head_diff=0,
           RL_EDF_head_diff=0,free_two_resource_dispatch=0,voluntary_WAIT=0)
    for d in row['protection_decisions']:
        n['actor_calls']+=1;n['voluntary_WAIT']+=d['action']['kind']=='WAIT'
        if d['action']['kind']!='DISPATCH':continue
        q=d['public_state']['queue'];n['dispatch_calls']+=1
        n['free_two_resource_dispatch']+=len(d['public_state']['owners'])==0
        n['multiple_ready_dispatch']+=len(q)>1
        n['different_task_dispatch']+=len(set(r['task'] for r in q))>1
        n['different_deadline_dispatch']+=len(set(r['deadline_ns'] for r in q))>1
        n['different_priority_dispatch']+=len(set(r['priority'] for r in q))>1
        tie=lambda r:(r['scheduled_arrival_ns'],r['ordinal'],r['request_id'])
        fifo=min(q,key=tie);edf=min(q,key=lambda r:(r['deadline_ns'],*tie(r)))
        n['FIFO_EDF_head_diff']+=fifo['request_id']!=edf['request_id']
        n['RL_EDF_head_diff']+=edf['request_id']!=d['action']['request_id']
    return n

def run(path):
    op=G.read(path);sha=G.sha(path);reg=G.read(ROOT/'models/registration.json')
    for p in op['source_pins']+op['input_pins']:G.pin(p)
    G.process_guard(ENTRY,reg['known_PS_producer_paths']);G.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];G.require(not out.exists(),'Consumed analysis')
    out.mkdir(parents=True,exist_ok=False)
    G.write_new(out/'START.json',dict(operation_sha256=sha,utc=G.now()))
    try:
        w=G.read(G.pin(op['witness_pin']));model=G.read(G.pin(op['cost_model_pin']))
        native=G.read(G.pin(op['relative_model_pin']));old=G.read(G.pin(op['old_diagnosis_pin']))
        cases=[]
        for c in w['cases']:
            lo,hi=c['common_work_window_s'];metrics=[]
            for row,m in zip(c['rows'],c['metrics']):
                intervals=R.exclusive(row['gantt'],0.,210.)
                new=C.observe(intervals,lo,hi,model)
                relative=R.observe(row['gantt'],lo,hi,native.get('model'))
                requests=row['requests'];res=[r for r in requests if r['response_ns'] is not None]
                latency=sorted((r['response_ns']-r['scheduled_arrival_ns'])/1e9 for r in res)
                # P95 uses all completed responses; missing denominator stays visible.
                p95=latency[max(0,__import__('math').ceil(.95*len(latency))-1)] if latency else None
                metrics.append(dict(**m,new_state_cost=new,native_current_index=relative,
                                    by_priority=row['by_priority'],P95_completed_response_s=p95,
                                    missing=len(requests)-len(res)))
            a,b=metrics;bounds_a=a['new_state_cost']['sensitivity_total_J_proxy'];bounds_b=b['new_state_cost']['sensitivity_total_J_proxy']
            delta=dict(total_J_proxy=b['new_state_cost']['total_J_proxy']-a['new_state_cost']['total_J_proxy'],
                       increment_J_proxy=b['new_state_cost']['increment_J_proxy']-a['new_state_cost']['increment_J_proxy'],
                       state_cost_sensitivity_delta=[bounds_b[0]-bounds_a[1],bounds_b[1]-bounds_a[0]],
                       mean_AP_c=b['mean_AP_c']-a['mean_AP_c'],on_time=b['on_time']-a['on_time'],
                       interpretation='RL minus EDF, same input-defined window; sensitivity is not a confidence interval')
            cases.append(dict(index=c['index'],label=c['label'],condition=c['condition'],input=c['input'],
                              window_s=[lo,hi],metrics=metrics,delta=delta,competition=competition(c['rows'][1])))
        keys=cases[0]['competition'].keys();stats={k:sum(c['competition'][k] for c in cases) for k in keys}
        original=old['decision_stats'];rates={}
        for k,oldkey in [('multiple_ready_dispatch','multiple_ready_dispatch'),('different_task_dispatch','heterogeneous_task_dispatch'),
                         ('different_deadline_dispatch','heterogeneous_deadline_dispatch'),('different_priority_dispatch','heterogeneous_priority_dispatch')]:
            rates[k]=dict(original=original[oldkey]/original['dispatch_calls'],new=stats[k]/stats['dispatch_calls'])
        outdata=dict(schema='A24-competition-cost-saved-comparison-v1',cases=cases,competition=stats,competition_rates=rates,
                     cost_model_adopted=model['adopted_for_qualified_states'],cost_model_tau_s=model['tau_s'],
                     native_relative_model_adopted=native.get('model',{}).get('adopted_as_relative_sensor_predictor',False),
                     new_START=w['budget']['new_START'],budget=w['budget'],NN_training=0,
                     cost_fitting_used_policy_results=False,existing24_preserved=True,
                     measured_J=None,energy_error_J=None,physical_goal_verified=False,
                     policy_cost_training='Frozen EP024 trained with preceding cost model, not retrained against new observer',
                     selection='four input-only preregistered witnesses, not a broad confirmatory claim')
        G.write_new(out/'RESULT.json',outdata)
        for p in op['source_pins']+op['input_pins']:G.pin(p)
        G.write_new(out/'COMPLETE.json',dict(result_sha256=G.sha(out/'RESULT.json'),operation_sha256=sha,utc=G.now()))
        print(json.dumps(dict(competition=stats,rates=rates)),flush=True)
    except BaseException as e:
        G.write_new(out/'FAILURE.json',dict(error=str(e),automatic_retry=False,utc=G.now()));raise
if __name__=='__main__':run(sys.argv[1])
