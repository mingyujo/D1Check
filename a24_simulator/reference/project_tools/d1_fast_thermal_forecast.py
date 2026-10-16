"""Exact fast forecast of the frozen linear AP model and Band suffix.

Lightweight hypothetical EMA avoids copying thermal histories. Vector pulses
replace scalar grid integration without changing the original cost function.
"""
from __future__ import annotations
import copy,math,time
import numpy as np
from tools import d1_thermal_load_gate as prior
from tools import d1_thermal_slack_v3 as old
p=old.p;PHASES=old.PHASES;EPS=old.EPS;ProjectionUnavailable=old.ProjectionUnavailable
FAST='IE_FAST_BAND_EDD_SLACK_LOAD_GATE_025_V4'

class LightBand(old.external.BandController):
    def __init__(self,band,estimates):
        self.expected=dict(band.expected);self.estimates={k:list(v) for k,v in estimates.items()}
        self.running={b:dict(q=dict(j['q']),dispatch=j['dispatch']) for b,j in band.running.items()};self.t=band.t
    def observe(self,now,lanes):
        for b,job in list(self.running.items()):
            current=lanes[b]['request']
            if current is None or current['id']!=job['q']['id']:
                cell=p.key(job['q'],b);before=self.expected[cell]
                self.expected[cell]=int(.1*round(now-job['dispatch'])+.9*before)
                factor=self.expected[cell]/before;self.estimates[cell]=[d*factor for d in self.estimates[cell]]
                del self.running[b]
        for b,lane in lanes.items():
            if lane['request'] is not None:self.running[b]=dict(q=lane['request'],dispatch=lane['dispatch'])

def project(estimates, profiles, queue, public_lanes, now_ns, action, context, band, probes=()):
    """Hypothetical Band suffix against one declared possible plant context.

    Running phases use mean residuals on mean/short paths and long on long.
    An already elapsed predicted phase end is unavailable, never a fake zero.
    The observed phase cannot be moved backwards or progressed retroactively.
    """
    qlist = copy.deepcopy(queue)
    now = float(now_ns)
    virtual = {'CPU': None, 'GPU': None}
    jobs, responses, transitions, dispatches = {}, {}, [], []
    for b, lane in public_lanes.items():
        if lane['request'] is None:
            continue
        q = copy.deepcopy(lane['request'])
        ds = profiles['long_context' if context == 'long_context' else 'mean'][p.key(q, b)]
        stage = PHASES.index(lane['phase'])
        next_at = lane['dispatch'] + sum(ds[:stage+1])
        if next_at <= now + .0001:
            raise ProjectionUnavailable('observed_phase_residual_unavailable')
        virtual[b] = dict(ticket=q, stage=stage, since=lane['since'], dispatch=lane['dispatch'],
                          durations=ds, next_at=next_at)
        responded = stage >= (2 if q['priority'] == 'urgent' else 3)
        jobs[q['id']] = dict(id=q['id'], state=q['task']+'_'+b, backend=b, start=now/1e9,
                             already_responded=responded, deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9)

    delegate = LightBand(band, estimates)
    future = sorted(copy.deepcopy(probes),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
    if any(q['arrival_ns']<=now for q in future) or ({q['id'] for q in future}&(set(jobs)|{q['id'] for q in qlist})):
        raise ProjectionUnavailable('invalid_future_probe')
    prefix = list(action.get('jobs', []))
    prefix_wait = action.get('wait_until_ns')
    wake = None

    def public():
        return {b: dict(request=x['ticket'] if x else None,
                        phase=PHASES[x['stage']] if x else 'AVAILABLE',
                        since=x['since'] if x else now, dispatch=x['dispatch'] if x else None)
                for b, x in virtual.items()}

    def dispatch(selected):
        nonlocal qlist
        b = selected['backend']
        if virtual[b] is not None:
            raise ValueError('projection double lane assignment')
        q = next(q for q in qlist if q['id'] == selected['request_id'])
        p.state([x['ticket']['task']+'_'+lane for lane, x in virtual.items() if x] + [q['task']+'_'+b])
        qlist = [x for x in qlist if x['id'] != q['id']]
        ds = profiles[context][p.key(q, b)]
        virtual[b] = dict(ticket=q, stage=0, since=now, dispatch=now, durations=ds, next_at=now+ds[0])
        jobs[q['id']] = dict(id=q['id'], state=q['task']+'_'+b, backend=b, start=now/1e9,
                             already_responded=False, deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9)
        dispatches.append(dict(request_id=q['id'], backend=b, at_ns=round(now)))

    for _ in range(10000):
        progressed = False
        for b in ('CPU', 'GPU'):
            x = virtual[b]
            while x and x['next_at'] <= now+.0001:
                stage, q = x['stage'], x['ticket']
                transitions.append(dict(request_id=q['id'], backend=b, stage=stage, at_ns=round(now)))
                if stage == (1 if q['priority'] == 'urgent' else 2) and not jobs[q['id']]['already_responded']:
                    responses[q['id']] = round(now)/1e9
                if stage == 4:
                    jobs[q['id']]['end'] = now/1e9
                    virtual[b] = None
                    x = None
                else:
                    x['stage'] += 1
                    x['since'] = now
                    x['next_at'] = now+x['durations'][x['stage']]
                progressed = True
        arrived=False
        while future and future[0]['arrival_ns']<=now:
            qlist.append(future.pop(0));arrived=True
        delegate.observe(now, public())
        # A public phase event interrupts a selected wait exactly as the plant does.
        if progressed or arrived:
            prefix_wait = None
        if prefix_wait is not None and prefix_wait <= now:
            prefix_wait = None
        if wake is not None and wake <= now:
            wake = None
        if prefix:
            dispatch(prefix.pop(0))
            continue
        if qlist and prefix_wait is None:
            out = delegate.decide(None, qlist, public(), now, {}, None, None)
            wake = out.get('wait_until_ns')
            if out['selected']:
                dispatch(out['selected'])
                continue
        if not qlist and not any(virtual.values()) and not future:
            break
        events = [x['next_at'] for x in virtual.values() if x]
        if future:events.append(float(future[0]['arrival_ns']))
        if prefix_wait is not None:
            events.append(prefix_wait)
        if wake is not None:
            events.append(wake)
        if not events:
            raise ProjectionUnavailable('projection_has_no_progress_event')
        nxt = min(events)
        if nxt <= now or not math.isfinite(nxt):
            raise ProjectionUnavailable('projection_nonpositive_time_progress')
        now = nxt
    else:
        raise ProjectionUnavailable('projection_event_bound')
    if any('end' not in j for j in jobs.values()):
        raise ProjectionUnavailable('projection_incomplete')
    for rid, response in responses.items():
        jobs[rid]['response'] = response
    pending = [j for j in jobs.values() if not j['already_responded']]
    if any('response' not in j for j in pending):
        raise ProjectionUnavailable('projection_missing_response')
    return dict(jobs=list(jobs.values()), dispatches=dispatches, transitions=transitions,
                deadline_misses=sum(j['response'] > j['deadline']+EPS for j in pending),
                lane_end_s=max((j['end'] for j in jobs.values()), default=now_ns/1e9))


def convolution(beta,dt):
    return dt*np.exp(-beta*dt) if abs(beta-1/30.)<1e-10 else (np.exp(-dt/30.)-np.exp(-beta*dt))/(beta-1/30.)

def kernel(ap,dt):
    dt=np.maximum(0.,dt)
    return (ap['k']+ap['g'])*(-np.expm1(-ap['beta']*dt))/ap['beta']-ap['g']*convolution(ap['beta'],dt)

def costs(controller,jobs,now_ns):
    now=now_ns/1e9;segments=p.segments(jobs,now,180.);ap=controller.frozen['ap'];reference=controller.init['reference_c']
    times=np.arange(max(35,math.ceil(now)),181.,dtype=float);dt=times-now
    path=reference+(controller.t-reference)*np.exp(-ap['beta']*dt)+controller.h*convolution(ap['beta'],dt)
    slopes=ap['parameters']['ap_slope_at_30_c_per_s'];volumes={label:0. for label in controller.frozen['energy_increment_w']};energy=0.
    for segment in segments:
        label='resident_idle' if segment['state']=='idle' else segment['state'];a=segment['start_s'];b=segment['end_s']
        if label!='resident_idle':
            if label not in controller.frozen['energy_increment_w']:raise ProjectionUnavailable('unsupported_energy_state')
            duration=max(0.,min(120.,b)-a);energy+=duration*controller.frozen['energy_increment_w'][label];volumes[label]+=duration
        u=slopes[label]-slopes['resident_idle']
        if u:path+=u*(kernel(ap,times-a)-kernel(ap,times-b))
    peak=max(controller.t,float(path.max()) if len(path) else controller.t)
    return dict(remaining_increment_j=energy,peak_ap_c=peak,global_peak_ap_c=max(peak,max(controller.grid.values(),default=peak)),volumes=volumes)

def forecast(controller,queue,lanes,now,action,context,probes=()):
    if controller.execution_deadline is not None and time.monotonic()>=controller.execution_deadline:raise TimeoutError('forecast save boundary')
    controller.projection_calls+=1;began=time.perf_counter()
    try:
        result=project(controller.estimates,controller.profiles,queue,lanes,now,action,context,controller.band,probes)
        value=costs(controller,result['jobs'],now)
        known={q['id']:q for q in list(queue)+[l['request'] for l in lanes.values() if l['request']]};by={**known,**{q['id']:q for q in probes}}
        pending=[j for j in result['jobs'] if not j['already_responded']];actual=[j for j in pending if j['id'] in known]
        margins={priority:[j['deadline']-j['response'] for j in actual if by[j['id']]['priority']==priority] for priority in ('urgent','normal')}
        urgent=sorted([r['response_ms'] for r in controller.observed_responses.values() if r['priority']=='urgent']+
            [(j['response']-by[j['id']]['arrival_ns']/1e9)*1000 for j in actual if by[j['id']]['priority']=='urgent'])
        return dict(valid=True,feasible=result['deadline_misses']==0 and result['lane_end_s']<=120.+EPS,**value,
            urgent_margin=min(margins['urgent'],default=None),normal_margin=min(margins['normal'],default=None),
            urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1] if urgent else None,dispatches=result['dispatches'],lane_end_s=result['lane_end_s'],deadline_misses=result['deadline_misses'],
            urgent_misses=sum(j['response']>j['deadline']+EPS for j in actual if by[j['id']]['priority']=='urgent'),
            normal_misses=sum(j['response']>j['deadline']+EPS for j in actual if by[j['id']]['priority']=='normal'),
            probe_urgent_ms={j['id']:(j['response']-by[j['id']]['arrival_ns']/1e9)*1000 for j in pending if j['id'] not in known and by[j['id']]['priority']=='urgent'},
            projection=result if controller.record_forecasts else None)
    except ProjectionUnavailable as error:return dict(valid=False,feasible=False,reason=str(error))
    finally:controller.projection_seconds+=time.perf_counter()-began

class Controller(prior.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial);self.public_policy=FAST
    def forecast(self,queue,lanes,now,action,context):return forecast(self,queue,lanes,now,action,context)
