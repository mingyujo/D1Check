"""Explicit no-NN rule identities; all run in the same event-driven engine."""
from contextlib import contextmanager

SPEC={
 'ROLLING_ATC':dict(order='native ATC joint public request/available-route score',
    score='log(w/p_occ)-max(deadline-now-p_response,0)/(2*mean_p_occ)',urgent_weight=2,normal_weight=1,
    route_selection='joint ATC score; response/occupancy ties as native engine',
    candidate_scope='all currently ready requests x free CPU/GPU',voluntary_WAIT=False,NN=False,
    uses_thermal_or_energy_for_action=False,uses_realized_future=False),
 'FIFO_CPU_FIRST':dict(order=['scheduled_arrival_ns','ordinal','request_id'],route_selection=['CPU','GPU'],
    nominal_time_for_selection=False,voluntary_WAIT=False,NN=False),
 'EDF_CPU_FIRST':dict(order=['deadline_ns','scheduled_arrival_ns','ordinal','request_id'],route_selection=['CPU','GPU'],
    nominal_time_for_selection=False,voluntary_WAIT=False,NN=False),
 'shared_execution':dict(events=['ENQUEUE','phase/AVAILABLE','SERVICE_STOP','DRAIN_STOP','END'],
    event_reselection=True,multi_step_lookahead_optimization=False,preemption=False,maximum_owners=2,
    both_tasks_routes=['CPU','GPU'],resource_owned_until='AVAILABLE')}

def select_fifo(state):
    owners=state.get('owners',[]);busy={r['route'] for r in owners}
    if not busy<=set(('CPU','GPU')):raise ValueError('Unknown resource')
    free=[r for r in ('CPU','GPU') if r not in busy]
    q=list(state['queue'])
    if any(r['queue_entry_ns']>state['now_ns'] for r in q):raise ValueError('Future queue member')
    if not free or not q:return dict(kind='RESOURCE_WAIT')
    head=min(q,key=lambda r:(r['scheduled_arrival_ns'],r['ordinal'],r['request_id']))
    return dict(kind='DISPATCH',request_id=head['request_id'],route=free[0])

@contextmanager
def installed(kernel,trace=None):
    original=kernel._rule_action;policies=kernel.POLICIES
    def hook(policy,snapshot,rows,model,pair_scope,mobile_energy,allow_busy=False):
        if policy=='FIFO_CPU_FIRST':return select_fifo(snapshot)
        if policy=='ROLLING_ATC':
            # Record the native rule's own nominal queries, without repeating a
            # draw or a lookup, so a saved-only auditor can reconstruct scores.
            calls=[];nominal=model.nominal
            free=[r for r in ('CPU','GPU') if all(o['route']!=r for o in snapshot['owners'])]
            expected=[(q,r) for q in snapshot['queue'] for r in free]
            def recording(*args,**kw):
                i=len(calls);q,r=expected[i]
                try:
                    value=nominal(*args,**kw)
                    calls.append(dict(request_id=q['request_id'],route=r,status='OK',occupancy_ns=value['occupancy_ns'],response_ns=value['response_ns']))
                    return value
                except Exception as e:
                    calls.append(dict(request_id=q['request_id'],route=r,status='UNSUPPORTED',error=str(e)));raise
            model.nominal=recording
            try:action=original('ATC',snapshot,rows,model,pair_scope,mobile_energy,allow_busy)
            finally:model.nominal=nominal
            if trace is not None and action['kind']=='DISPATCH':trace.append(dict(time_ns=snapshot['now_ns'],nominal_calls=calls,action=dict(action)))
            return action
        return original(policy,snapshot,rows,model,pair_scope,mobile_energy,allow_busy)
    kernel._rule_action=hook;kernel.POLICIES=(*policies,'FIFO_CPU_FIRST','ROLLING_ATC')
    try:yield
    finally:kernel._rule_action=original;kernel.POLICIES=policies
