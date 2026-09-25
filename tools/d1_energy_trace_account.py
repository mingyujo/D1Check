"""Observed two-model replay only. No fitted parallel model or future policy input.

Disjoint accounting includes unlabelled gate/transition costs. Windows overlap by
definition and must NOT be added to each other. Missing endpoints stay missing.
"""
from tools.d1_energy_thermal import integrate, require

VERSION = 'observed-energy-ledger-v1'


def service_summary(requests, planned_by_priority):
    """Completed latency plus full planned denominators; no invented deadlines."""
    result={}
    for priority,planned in planned_by_priority.items():
        rows=[r for r in requests if r.get('priority')==priority]
        complete=[r for r in rows if r.get('terminal_status')=='succeeded']
        values=sorted((r['output_ready_ns' if priority=='urgent' else 'persist_complete_ns']-
                       r['scheduled_arrival_ns'])/1e9 for r in complete)
        require(0<=len(complete)<=len(rows)<=planned and all(v>=0 for v in values),'service denominator/order')
        p95=None
        if values:
            pos=.95*(len(values)-1);i=int(pos)
            p95=values[i]+(values[min(i+1,len(values)-1)]-values[i])*(pos-i)
        result[priority]=dict(planned=planned,completed=len(complete),
            not_confirmed_complete=planned-len(complete),failed_recorded=len(rows)-len(complete),
            completion_rate=len(complete)/planned if planned else None,
            completed_mean_s=sum(values)/len(values) if values else None,completed_p95_s=p95,
            p95_method='linear empirical quantile, completed requests only; correlated within one session',
            deadline_violation_rate=None,service_pass=None)
    return result


def replay(events, requests, *, planned_work=870, unit_scale=1000):
    require(events and all(a['mono_ns'] <= b['mono_ns'] for a,b in zip(events,events[1:])), 'event order')
    require(len({e['session_id'] for e in events}) == 1, 'mixed sessions')
    samples = [e for e in events if e['kind'] == 'power_sample']
    start, end = events[0]['mono_ns'], events[-1]['mono_ns']
    intervals = []
    opened = None
    for e in events:
        if e['kind'] == 'phase_start':
            require(opened is None, 'overlapping explicit phases')
            opened = e
        elif e['kind'] == 'phase_end':
            require(opened is not None and opened['phase'] == e['phase'], 'unmatched phase')
            intervals.append((opened['mono_ns'],e['mono_ns'],e['phase'],True));opened=None
    if opened:
        intervals.append((opened['mono_ns'],end,opened['phase'],False))
    partition = []
    cursor = start
    for a,b,label,complete in intervals:
        require(a >= cursor and b >= a, 'phase overlap')
        if a > cursor:partition.append((cursor,a,'setup_gate_or_transition',False))
        partition.append((a,b,label,complete));cursor=b
    if cursor < end:partition.append((cursor,end,'setup_gate_or_transition',False))
    parts = [dict(start_ns=a,end_ns=b,phase=label,phase_end_observed=done,
                  energy=integrate(samples,a,b,unit_scale)) for a,b,label,done in partition]
    total = integrate(samples,start,end,unit_scale)
    energy_sum = sum(x['energy']['covered_energy_j'] or 0 for x in parts)
    require(abs(energy_sum-(total['covered_energy_j'] or 0)) < 1e-6, 'double counted/lost energy')
    require(abs(sum(x['energy']['covered_s'] for x in parts)-total['covered_s']) < 1e-6, 'coverage mismatch')
    require(len(requests) <= planned_work and len({r['id'] for r in requests}) == len(requests), 'request denominator')
    completed = [r for r in requests if r.get('terminal_status') == 'succeeded' and 'persist_complete_ns' in r]
    full_work = len(completed) == planned_work
    windows = {'observed_session_prefix':total}
    load = next((x for x in parts if x['phase']=='load'),None)
    wait = next((x for x in parts if x['phase']=='post_work_wait' and x['phase_end_observed']),None)
    if load and full_work:
        completion=max(r['persist_complete_ns'] for r in completed)
        require(load['start_ns']<=completion<=end,'completion outside evidence')
        windows['work_to_persist_complete']=integrate(samples,load['start_ns'],completion,unit_scale)
        windows['session_to_work_complete']=integrate(samples,start,completion,unit_scale)
    if load and wait:
        windows['common_work_window']=integrate(samples,load['start_ns'],wait['end_ns'],unit_scale)
    return dict(version=VERSION,mode='observed_replay_only',partition=parts,windows=windows,
                planned_work=planned_work,confirmed_work_completed=len(completed),
                work_not_confirmed_complete=planned_work-len(completed),
                equal_work_completion_observed=full_work,
                full_operation_energy_j=None,
                exclusions='before session_start and after recovered last event, including host cleanup; no extrapolation',
                fit_or_prediction=False,absolute_accuracy_certified=False,experiment_ready=False)
