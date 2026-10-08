"""Band fallback with EDD/slack candidates and bounded thermal receding planning.

Pure projection adapted from the existing EDD event projector, isolated here.
Online input is public arrived queue/lane/history only; no plant context is read.
"""
from __future__ import annotations
import copy,math,time
from tools import d1_edd_ect_residual_controller as core
from tools import d1_external_rules as external
p=core.p;ie=core.ie;BASE=core.BASE;PHASES=core.PHASES;EPS=core.EPS
ProjectionUnavailable=core.ProjectionUnavailable
SHORT='IE_BAND_EDD_SLACK_THERMAL_025_V3'
LONG='IE_BAND_EDD_SLACK_THERMAL_100_V3'
NOWAIT='IE_BAND_EDD_SLACK_THERMAL_NOWAIT_V3'
LIMITS={SHORT:.25,LONG:1.,NOWAIT:0.}

def project_band(estimates, profiles, queue, public_lanes, now_ns, action, context, band):
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

    delegate = copy.deepcopy(band)
    delegate.estimates = copy.deepcopy(estimates)
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
        delegate.observe(now, public())
        # A public phase event interrupts a selected wait exactly as the plant does.
        if progressed:
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
        if not qlist and not any(virtual.values()):
            break
        events = [x['next_at'] for x in virtual.values() if x]
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


class Controller(core.Controller):
    def __init__(self,frozen,initial,policy):
        if policy not in LIMITS:raise ValueError('unregistered thermal slack policy')
        super().__init__(frozen,initial,core.PRIOR,record_forecasts=False)
        self.public_policy=policy;self.max_credit=LIMITS[policy];self.credit=self.max_credit
        self.band=external.BandController(frozen,initial);self.choice_records=[]

    def observe(self,now,lanes):
        old={l['request']['id'] for l in self.previous_lanes.values() if l['request']}
        current={l['request']['id'] for l in lanes.values() if l['request']}
        super().observe(now,lanes)
        if current-old:self.credit=self.max_credit
        else:self.credit=min(self.credit,self.max_credit)
        self.band.observe(now,lanes);self.estimates=copy.deepcopy(self.band.estimates)

    def physical_candidates(self,queue,lanes,now,base):
        actions=[dict(kind='single' if base['selected'] else 'event_wait',jobs=[base['selected']] if base['selected'] else [],base=True)]
        active=self.active_jobs(lanes,now/1e9)
        if active is None:return actions
        ordered=sorted(queue,key=core.due)[:4]
        cpu_only=[q for q in queue if len(p.backends(q))==1]
        if cpu_only:
            protected=min(cpu_only,key=lambda q:((q['arrival_ns']+q['deadline_offset_ns'])/1e9-self.place(q,'CPU',now/1e9,active)['response'],core.due(q)))
            if protected not in ordered:ordered.append(protected)
        for q in ordered:
            for b in p.backends(q):
                if lanes[b]['request'] is not None:continue
                try:p.state([l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]+[q['task']+'_'+b])
                except ValueError:continue
                actions.append(dict(kind='single',jobs=[dict(request_id=q['id'],backend=b)],base=False))
        empty=not any(l['request'] for l in lanes.values())
        if empty:
            for c in ordered:
                if c['task']!='classification':continue
                for d in ordered:
                    if d['task']!='detection':continue
                    pair=sorted((c,d),key=core.due)
                    actions.append(dict(kind='bundle',jobs=[dict(request_id=q['id'],backend='GPU' if q['task']=='classification' else 'CPU') for q in pair],base=False))
        # Only normal arrived work can use discretionary idle cooling. An urgent
        # arrival interrupts it; credit cannot be renewed by another wait/event.
        if empty and queue and not any(q['priority']=='urgent' for q in queue) and self.credit>EPS and base['selected']:
            actions.append(dict(kind='cool_wait',jobs=[],wait_until_ns=now+min(self.credit,max(0.,120.-now/1e9))*1e9,base=False))
        unique={}
        for a in actions:
            k=core.signature(a)
            if k in unique:unique[k]['base']|=a['base']
            else:unique[k]=a
        assert len(unique)<=20
        return list(unique.values())

    @staticmethod
    def select(actions):
        base=next(a for a in actions if a['base']);safe=[]
        for action in actions:
            if action['base']:continue
            good=True;deltas=[]
            for context in core.CONTEXTS:
                f=action['forecasts'][context];r=base['forecasts'][context]
                if not f['valid'] or not r['valid']:good=False;break
                if (f['lane_end_s']>120.+EPS or f['urgent_misses']>r['urgent_misses'] or f['normal_misses']>r['normal_misses'] or
                    f['remaining_increment_j']>r['remaining_increment_j']+EPS or f['global_peak_ap_c']>r['global_peak_ap_c']+EPS):good=False;break
                if f['urgent_p95_ms'] is not None and r['urgent_p95_ms'] is not None and f['urgent_p95_ms']>r['urgent_p95_ms']+EPS:good=False;break
                deltas.append(f['peak_ap_c']-r['peak_ap_c'])
            if good and max(deltas)<-EPS:safe.append((max(deltas),max(action['forecasts'][ctx]['remaining_increment_j'] for ctx in core.CONTEXTS),core.signature(action),action))
        return min(safe,key=lambda t:t[:2])[3] if safe else base

    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        if self.pending:
            pending,self.pending=self.pending,None;first,second=pending['first'],pending['second']
            if now==pending['now_ns'] and lanes[first['backend']]['request'] and lanes[first['backend']]['request']['id']==first['request_id'] and lanes[second['backend']]['request'] is None and any(q['id']==second['request_id'] for q in queue):
                p.state([l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]+[next(q['task'] for q in queue if q['id']==second['request_id'])+'_'+second['backend']])
                return dict(now_ns=now,selected=second,reason='bundle_commit',action_kind='bundle_commit')
            self.cancelled_bundles+=1
        signature=core.public_signature(queue,lanes,now)
        if signature==self.last_signature:return copy.deepcopy(self.last_reply)
        base=self.band.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        if not queue or not self.response_counters_valid or self.active_jobs(lanes,now/1e9) is None:return dict(base,public_policy=self.public_policy,forced=True)
        actions=self.physical_candidates(queue,lanes,now,base)
        for a in actions:a['forecasts']={ctx:self.forecast(queue,lanes,now,a,ctx) for ctx in core.CONTEXTS}
        chosen=self.select(actions)
        out=dict(base,public_policy=self.public_policy) if chosen['base'] else self._reply(chosen,now)
        self.choice_records.append(dict(t_s=now/1e9,kind=chosen['kind'],chosen_base=chosen['base'],credit_s=self.credit,available=len(actions),
            forecasts={ctx:{k:f.get(k) for k in ('valid','peak_ap_c','global_peak_ap_c','remaining_increment_j','urgent_misses','normal_misses','urgent_p95_ms')} for ctx,f in chosen['forecasts'].items()}))
        self.last_signature=signature;self.last_reply=copy.deepcopy(out);return out

    def forecast(self, queue, lanes, now_ns, action, context):
        if self.execution_deadline is not None and time.monotonic() >= self.execution_deadline:
            raise TimeoutError('prototype save reserve reached during projection')
        began = time.perf_counter()
        self.projection_calls += 1
        try:
            result = project_band(self.estimates, self.profiles, queue, lanes, now_ns, action, context, self.band)
            ss = p.segments(result['jobs'], now_ns/1e9, 180.)
            t, h = self.t, self.h
            peak = self.t
            energy = 0.
            volumes = {s: 0. for s in ('classification_CPU', 'classification_GPU', 'detection_CPU', 'classification_GPU+detection_CPU')}
            slopes = self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
            for segment in ss:
                label = 'resident_idle' if segment['state'] == 'idle' else segment['state']
                a, b = segment['start_s'], segment['end_s']
                dt = max(0., min(120., b)-a)
                if label != 'resident_idle':
                    if label not in self.frozen['energy_increment_w']:
                        raise ProjectionUnavailable('unsupported_energy_state')
                    energy += dt*self.frozen['energy_increment_w'][label]
                    volumes[label] += dt
                u = slopes[label]-slopes['resident_idle']
                for second in range(max(35, math.ceil(a)), min(180, math.floor(b))+1):
                    peak = max(peak, p.thermal_step(t, h, u, self.init['reference_c'], self.frozen['ap'], second-a)[0])
                t, h = p.thermal_step(t, h, u, self.init['reference_c'], self.frozen['ap'], b-a)
            pending = [j for j in result['jobs'] if not j['already_responded']]
            margins = {priority: [j['deadline']-j['response'] for j in pending
                        if next(q['priority'] for q in list(queue)+[l['request'] for l in lanes.values() if l['request']] if q['id']==j['id']) == priority]
                       for priority in ('urgent', 'normal')}
            observed_urgent = [r['response_ms'] for r in self.observed_responses.values() if r['priority']=='urgent']
            byid = {q['id']: q for q in list(queue)+[l['request'] for l in lanes.values() if l['request']]}
            predicted_urgent = [(j['response']-byid[j['id']]['arrival_ns']/1e9)*1000 for j in pending if byid[j['id']]['priority']=='urgent']
            values = sorted(observed_urgent+predicted_urgent)
            return dict(valid=True, feasible=result['deadline_misses']==0 and result['lane_end_s']<=120.+EPS,
                remaining_increment_j=energy, peak_ap_c=peak, global_peak_ap_c=max(peak,max(self.grid.values(),default=peak)), volumes=volumes,
                urgent_margin=min(margins['urgent'], default=None), normal_margin=min(margins['normal'], default=None),
                urgent_p95_ms=values[math.ceil(.95*len(values))-1] if values else None,
                dispatches=result['dispatches'], lane_end_s=result['lane_end_s'], deadline_misses=result['deadline_misses'],
                urgent_misses=sum(j['response'] > j['deadline']+EPS for j in pending if byid[j['id']]['priority']=='urgent'),
                    normal_misses=sum(j['response'] > j['deadline']+EPS for j in pending if byid[j['id']]['priority']=='normal'),
                    projection=result if self.record_forecasts else None)
        except ProjectionUnavailable as error:
            return dict(valid=False, feasible=False, reason=str(error))
        finally:
            self.projection_seconds += time.perf_counter()-began
