"""Non-learning EDD/ECT residual prototype on the unchanged measured PC plant.

Forecasts are a pure event projection, not calls to the environment simulator.
Only the runner may start an environment and must journal it first.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
import time
from tools import d1_ie_dispatch as ie

p = ie.p
BASE = 'IE_EDD_ECT_LANE_PC_V1'
PRIOR = 'EDD_ECT_FEASIBILITY_PRIOR_V1'
GREEDY = 'EDD_ECT_THERMAL_GREEDY_V1'
CONTEXTS = ('mean', 'short_context', 'long_context')
PHASES = ('ASSIGNED', 'EXECUTING', 'OUTPUT_READY', 'PERSISTED', 'WORKER_RELEASED')
EPS = 1e-9


def due(q):
    return (q['arrival_ns'] + q['deadline_offset_ns'], q['arrival_ns'], q['ordinal'], q['id'])


def signature(action):
    return (tuple((x['request_id'], x['backend']) for x in action.get('jobs', [])),
            action.get('wait_until_ns'))


def public_signature(queue, lanes, now_ns):
    return json.dumps([now_ns, sorted(queue, key=due), lanes], sort_keys=True, separators=(',', ':'))


def empty_lanes(now_ns):
    return {b: dict(request=None, phase='AVAILABLE', since=now_ns, dispatch=None) for b in ('CPU', 'GPU')}


class ProjectionUnavailable(ValueError):
    pass


def project(estimates, profiles, queue, public_lanes, now_ns, action, context):
    """Exact source EDD decisions against a declared future plant context.

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

    delegate = object.__new__(ie.Controller)
    delegate.public_policy, delegate.rule, delegate.t = BASE, 'EDD', 0.
    delegate.estimates = estimates
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


class Controller(ie.Controller):
    def __init__(self, frozen, initial, policy=PRIOR, *, branch=None, record_forecasts=False):
        if policy not in (PRIOR, GREEDY, BASE):
            raise ValueError('non-learning prototype policy')
        super().__init__(frozen, initial, BASE)
        self.public_policy = policy
        self.profiles = {c: p.profile(frozen, c) for c in CONTEXTS}
        self.credit = .25
        self.cool_since = None
        self.pending = None
        self.previous_lanes = empty_lanes(0)
        self.last_reply = None
        self.last_signature = None
        self.observed_responses = {}
        self.response_counters_valid = True
        self.arrival_times = {}
        self.grid = {}
        self.last_grid = 34
        self.branch = branch
        self.branch_record = None
        self.record_forecasts = record_forecasts
        self.projection_calls = 0
        self.projection_seconds = 0.
        self.actions = []
        self.cancelled_bundles = 0
        self.execution_deadline = None

    def observe(self, now_ns, lanes):
        if self.cool_since is not None:
            self.credit = max(0., self.credit-(now_ns-self.cool_since)/1e9)
            self.cool_since = None
        previous_ids = {l['request']['id'] for l in self.previous_lanes.values() if l['request']}
        current_ids = {l['request']['id'] for l in lanes.values() if l['request']}
        if current_ids-previous_ids:
            self.credit = .25
        # Compute grid samples within the publicly known constant-occupancy past.
        slopes = self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        start = max(self.now, self.init['anchor_s'])
        u = slopes[self.label]-slopes['resident_idle']
        for second in range(max(35, self.last_grid+1), min(180, math.floor(now_ns/1e9))+1):
            if second >= start:
                self.grid[second] = p.thermal_step(self.t, self.h, u, self.init['reference_c'],
                                                 self.frozen['ap'], second-start)[0]
                self.last_grid = second
        for b, lane in lanes.items():
            q = lane['request']
            if not q or q['id'] in self.observed_responses:
                continue
            if lane['phase'] == ('OUTPUT_READY' if q['priority'] == 'urgent' else 'PERSISTED'):
                self.observed_responses[q['id']] = dict(priority=q['priority'],
                    response_ms=(lane['since']-q['arrival_ns'])/1e6,
                    failed=lane['since']-q['arrival_ns'] > q['deadline_offset_ns'])
            elif PHASES.index(lane['phase']) >= (2 if q['priority']=='urgent' else 3):
                # A skipped zero-duration public response phase has no exact
                # response timestamp in this ABI. Do not infer it from costs.
                self.response_counters_valid = False
        super().observe(now_ns, lanes)
        self.previous_lanes = copy.deepcopy(lanes)

    def forecast(self, queue, lanes, now_ns, action, context):
        if self.execution_deadline is not None and time.monotonic() >= self.execution_deadline:
            raise TimeoutError('prototype save reserve reached during projection')
        began = time.perf_counter()
        self.projection_calls += 1
        try:
            result = project(self.estimates, self.profiles, queue, lanes, now_ns, action, context)
            ss = p.segments(result['jobs'], now_ns/1e9, 180.)
            t, h = self.t, self.h
            peak = max(self.grid.values(), default=-math.inf)
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
                remaining_increment_j=energy, peak_ap_c=peak, volumes=volumes,
                urgent_margin=min(margins['urgent'], default=None), normal_margin=min(margins['normal'], default=None),
                urgent_p95_ms=values[math.ceil(.95*len(values))-1] if values else None,
                dispatches=result['dispatches'], lane_end_s=result['lane_end_s'], deadline_misses=result['deadline_misses'],
                projection=result if self.record_forecasts else None)
        except ProjectionUnavailable as error:
            return dict(valid=False, feasible=False, reason=str(error))
        finally:
            self.projection_seconds += time.perf_counter()-began

    def candidates(self, queue, lanes, now_ns, base):
        ordered = sorted(queue, key=due)[:8]
        active = self.active_jobs(lanes, now_ns/1e9)
        actions = []
        if base['selected']:
            actions.append(dict(kind='single', jobs=[base['selected']], base=True))
        else:
            actions.append(dict(kind='ect_resource_wait' if base.get('wait_until_ns') else 'event_wait',
                                jobs=[], base=True, **({'wait_until_ns':base['wait_until_ns']} if base.get('wait_until_ns') else {})))
        if active is not None:
            for q in ordered:
                for b in p.backends(q):
                    if lanes[b]['request'] is None and self.place(q,b,now_ns/1e9,active)['start'] <= now_ns/1e9+EPS:
                        actions.append(dict(kind='single', jobs=[dict(request_id=q['id'],backend=b)], base=False))
            if all(l['request'] is None for l in lanes.values()):
                for qc in ordered:
                    if qc['task']!='classification':
                        continue
                    for qd in ordered:
                        if qd['task']!='detection':
                            continue
                        requests = sorted([qc,qd],key=due)
                        actions.append(dict(kind='bundle', jobs=[dict(request_id=q['id'],backend='GPU' if q['task']=='classification' else 'CPU') for q in requests],base=False))
            delay = min(self.credit, min(q['arrival_ns']+q['deadline_offset_ns'] for q in queue)/1e9-now_ns/1e9, 120.-now_ns/1e9)
            if any(a['jobs'] for a in actions) and delay>EPS:
                actions.append(dict(kind='cool_wait',jobs=[],wait_until_ns=now_ns+delay*1e9,base=False))
        unique = {}
        for a in actions:
            key = signature(a)
            if key not in unique:
                unique[key] = a
            else:
                unique[key]['base'] |= a['base']
        result = list(unique.values())
        assert len(result)<=30
        return result

    def tensors(self, queue, lanes, now_ns, candidates):
        """Named 109/68 causal features; masks distinguish padding from costs."""
        contract = json.loads((p.ROOT/'docs/results/edd_ect_residual_design_01/design_contract.json').read_text(encoding='utf8'))
        ordered = sorted(queue,key=due)
        now = now_ns/1e9
        byid = {q['id']:q for q in ordered}
        rank = {q['id']:i for i,q in enumerate(ordered)}
        for q in ordered:
            self.arrival_times.setdefault(q['id'],q['arrival_ns']/1e9)
        for lane in lanes.values():
            if lane['request']:
                q = lane['request']
                self.arrival_times.setdefault(q['id'],q['arrival_ns']/1e9)
        times = sorted(set(self.arrival_times.values()))
        gaps = [b-a for a,b in zip(times,times[1:])]
        responses = list(self.observed_responses.values())
        urg = sorted(r['response_ms'] for r in responses if r['priority']=='urgent')
        past_j = sum(max(0.,min(120.,s['end_s'])-s['start_s'])*
            (0. if s['state']=='idle' else self.frozen['energy_increment_w'][s['state']]) for s in self.history)
        values = dict(time_s_over_120=now/120,remaining_s_over_120=(120-now)/120,
            modeled_ap_minus_reference_over_10c=(self.t-self.init['reference_c'])/10,
            modeled_h_over_0_1c_per_s=self.h/.1,
            modeled_grid_peak_minus_reference_over_10c=(max(self.grid.values(),default=self.t)-self.init['reference_c'])/10,
            modeled_increment_j_over_10j=past_j/10,arrival_gap_mean_over_2s=statistics.mean(gaps)/2 if gaps else 0.,
            arrival_gap_std_over_2s=statistics.pstdev(gaps)/2 if gaps else 0.,has_arrival_gaps=bool(gaps),
            observed_urgent_responses_over_192=len(urg)/192,
            observed_normal_responses_over_192=sum(r['priority']=='normal' for r in responses)/192,
            observed_urgent_p95_over_1500ms=urg[math.ceil(.95*len(urg))-1]/1500 if urg else 0.,
            observed_urgent_failures_over_192=sum(r['failed'] and r['priority']=='urgent' for r in responses)/192,
            observed_normal_failures_over_192=sum(r['failed'] and r['priority']=='normal' for r in responses)/192,
            response_counters_valid=self.response_counters_valid,cool_credit_over_0_25s=self.credit/.25,
            has_modeled_grid_sample=bool(self.grid))
        for priority,scale in [('urgent',1.5),('normal',6.)]:
            group=[q for q in ordered if q['priority']==priority]
            values['queued_'+priority+'_over_192']=len(group)/192
            values['has_'+priority]=bool(group)
            values['min_'+priority+'_slack_over_'+('1_5s' if priority=='urgent' else '6s')]=min(
                ((q['arrival_ns']+q['deadline_offset_ns'])/1e9-now for q in group),default=0.)/scale
        for b,lane in lanes.items():
            prefix='lane_'+b+'.'
            q=lane['request'];values[prefix+'busy']=q is not None
            for task in ('classification','detection'):values[prefix+task]=bool(q and q['task']==task)
            for phase in ('AVAILABLE',*PHASES):values[prefix+'phase_'+phase]=lane['phase']==phase
            values[prefix+'elapsed_over_6s']=(now_ns-lane['dispatch'])/6e9 if q else 0.
            values[prefix+'modeled_overrun']=bool(q and lane['dispatch']+sum(self.estimates[p.key(q,b)])<=now_ns+.0001)
        for i in range(8):
            prefix='queue_'+str(i)+'.';q=ordered[i] if i<len(ordered) else None
            values[prefix+'present']=q is not None
            for attr in ('classification','detection','urgent','normal'):
                values[prefix+attr]=bool(q and attr in (q['task'],q['priority']))
            values[prefix+'age_over_2s']=(now_ns-q['arrival_ns'])/2e9 if q else 0.
            values[prefix+'slack_over_own_deadline']=((q['arrival_ns']+q['deadline_offset_ns'])-now_ns)/q['deadline_offset_ns'] if q else 0.
            values[prefix+'is_edd_head']=bool(q and i==0)
        state=[float(values[field]) for field in contract['observation']['state_fields']]
        vectors=[]
        active=self.active_jobs(lanes,now)
        for action in candidates:
            v={field:0. for field in contract['observation']['candidate_fields']}
            v['kind_'+action['kind']]=1.;v['is_baseline']=float(action['base'])
            v['has_timer']=float(action.get('wait_until_ns') is not None)
            v['timer_over_120s']=max(0.,action.get('wait_until_ns',now_ns)-now_ns)/120e9
            for i,job in enumerate(action['jobs']):
                prefix='job_'+str(i)+'.';q=byid[job['request_id']];b=job['backend']
                v[prefix+'present']=1.
                for attr in ('classification','detection','urgent','normal','CPU','GPU'):
                    v[prefix+attr]=float(attr in (q['task'],q['priority'],b))
                v[prefix+'age_over_2s']=(now_ns-q['arrival_ns'])/2e9
                v[prefix+'slack_over_own_deadline']=(q['arrival_ns']+q['deadline_offset_ns']-now_ns)/q['deadline_offset_ns']
                v[prefix+'edd_rank_over_192']=rank[q['id']]/192
                placements=[self.place(q,x,now,active) for x in p.backends(q)]
                ect=min(placements,key=lambda x:(x['end'],x['backend']!='CPU'))
                selected=next(x for x in placements if x['backend']==b)
                v[prefix+'is_ect_backend']=float(b==ect['backend'])
                v[prefix+'ect_lane_excess_over_6s']=(selected['end']-ect['end'])/6
            for ctx,f in action['forecasts'].items():
                prefix=ctx+'.';v[prefix+'forecast_valid']=float(f['valid'])
                if not f['valid']:continue
                v[prefix+'delta_j_over_1j']=f['delta_j']
                v[prefix+'delta_grid_peak_over_1c']=f['delta_ap']
                for pri in ('urgent','normal'):
                    v[prefix+'has_'+pri]=float(f[pri+'_margin'] is not None)
                    v[prefix+'min_'+pri+'_margin_s']=f[pri+'_margin'] or 0.
                v[prefix+'urgent_p95_over_1500ms']=(f['urgent_p95_ms'] or 0.)/1500
                for label,dt in f['volumes'].items():v[prefix+'remaining_lane_state_s.'+label]=dt
            vectors.append([float(v[field]) for field in contract['observation']['candidate_fields']])
        assert len(state)==109 and all(len(v)==68 for v in vectors)
        assert all(math.isfinite(x) for row in [state,*vectors] for x in row)
        return state,vectors

    def _reply(self, action, now_ns):
        result = dict(now_ns=now_ns, selected=action['jobs'][0] if action['jobs'] else None,
                      reason=self.public_policy, action_kind=action['kind'])
        if action.get('wait_until_ns') is not None:
            result['wait_until_ns'] = action['wait_until_ns']
        if action['kind']=='cool_wait':
            self.cool_since = now_ns
        if len(action['jobs'])==2:
            self.pending = dict(now_ns=now_ns, first=action['jobs'][0], second=action['jobs'][1])
        return result

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        self.validate_public(queue, lanes, now_ns)
        if self.pending:
            pending, self.pending = self.pending, None
            first, second = pending['first'], pending['second']
            valid = (now_ns==pending['now_ns'] and lanes[first['backend']]['request'] is not None
                and lanes[first['backend']]['request']['id']==first['request_id']
                and lanes[second['backend']]['request'] is None
                and any(q['id']==second['request_id'] for q in queue))
            if valid:
                p.state([l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]
                    + [next(q['task'] for q in queue if q['id']==second['request_id'])+'_'+second['backend']])
                return dict(now_ns=now_ns,selected=second,reason='bundle_commit',action_kind='bundle_commit')
            self.cancelled_bundles += 1
        key = public_signature(queue,lanes,now_ns)
        if key == self.last_signature:
            return copy.deepcopy(self.last_reply)
        base = ie.Controller.decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if self.public_policy==BASE or not queue:
            return base
        if self.active_jobs(lanes,now_ns/1e9) is None:
            return dict(base,reason='unknown_overrun_exact_base',forced=True)
        candidates = self.candidates(queue,lanes,now_ns,base)
        for a in candidates:
            a['forecasts'] = {c:self.forecast(queue,lanes,now_ns,a,c) for c in CONTEXTS}
            a['valid'] = all(f['valid'] and f['feasible'] for f in a['forecasts'].values())
        # Merge actions producing the same complete forecast execution in all
        # three paths. A bundle tag alone must not inflate the action space.
        merged={}
        for a in candidates:
            if all(f['valid'] for f in a['forecasts'].values()):
                key_projection=tuple(tuple((j['request_id'],j['backend'],j['at_ns']) for j in a['forecasts'][ctx]['dispatches']) for ctx in CONTEXTS)
            else:key_projection=('unavailable',signature(a))
            if key_projection not in merged:merged[key_projection]=a
            else:merged[key_projection]['base'] |= a['base']
        candidates=list(merged.values())
        original = next(a for a in candidates if a['base'])
        if not all(f['valid'] for f in original['forecasts'].values()):
            out = dict(base, reason='unavailable_forecast_exact_base', forced=True,
                       forecast_reasons=[f.get('reason') for f in original['forecasts'].values() if not f['valid']])
            self.last_signature, self.last_reply = key, copy.deepcopy(out)
            return out
        for a in candidates:
            for c in CONTEXTS:
                f, r = a['forecasts'][c], original['forecasts'][c]
                if f['valid']:
                    f['delta_j'] = f['remaining_increment_j']-r['remaining_increment_j']
                    f['delta_ap'] = f['peak_ap_c']-r['peak_ap_c']
        legal = [a for a in candidates if a['valid']]
        if not legal:
            out = dict(base,reason='infeasible_exact_base',forced=True)
        else:
            chosen = original if original['valid'] else legal[0]
            if self.public_policy==GREEDY:
                lower_j = [a for a in legal if all(f['delta_j']<=EPS for f in a['forecasts'].values())]
                if lower_j:
                    chosen = min(lower_j,key=lambda a:(max(f['delta_ap'] for f in a['forecasts'].values()),
                        max(f['delta_j'] for f in a['forecasts'].values()),not a['base'],candidates.index(a)))
                elif not original['valid']:
                    chosen = min(legal,key=lambda a:(max(f['delta_j'] for f in a['forecasts'].values()),candidates.index(a)))
            physical = {tuple((j['request_id'],j['backend'],j['at_ns']) for j in a['forecasts']['mean']['dispatches']
                        if j['at_ns']<=now_ns+1): a for a in legal}
            if self.branch and self.branch_record is None and original['valid']:
                same = tuple((j['request_id'],j['backend'],j['at_ns']) for j in original['forecasts']['mean']['dispatches'] if j['at_ns']<=now_ns+1)
                alt = next((a for a in legal if not a['base'] and tuple((j['request_id'],j['backend'],j['at_ns'])
                    for j in a['forecasts']['mean']['dispatches'] if j['at_ns']<=now_ns+1)!=same),None)
                if alt:
                    self.branch_record = dict(now_ns=now_ns,public_state_sha256=hashlib.sha256(key.encode()).hexdigest(),
                        base_signature=signature(original),alternative_signature=signature(alt))
                    if self.branch in ('base','alt'):
                        chosen = original if self.branch=='base' else alt
            out = self._reply(chosen,now_ns)
            out.update(chosen_base=chosen['base'],valid_actions=len(legal),physical_immediate_groups=len(physical),
                chosen_delta_j=[chosen['forecasts'][c]['delta_j'] for c in CONTEXTS],
                chosen_delta_ap=[chosen['forecasts'][c]['delta_ap'] for c in CONTEXTS])
        out.update(public_policy=self.public_policy,credit_s=self.credit,candidate_count=len(candidates),
                   modeled_ap_c=self.t)
        if self.record_forecasts:
            out['candidates'] = candidates
            out['state_features'],out['candidate_features']=self.tensors(queue,lanes,now_ns,candidates)
        self.actions.append(copy.deepcopy(out))
        self.last_signature, self.last_reply = key, copy.deepcopy(out)
        return out


def simulate(frozen, initial, tickets, context, policy, *, branch=None, record_forecasts=False, deadline=None):
    c = Controller(frozen,initial,policy,branch=branch,record_forecasts=record_forecasts)
    c.execution_deadline = deadline
    actual = p.profile(frozen,context)
    vectors = dict(cells={k:[dict(source_request_id='shared_development_context_'+context,durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    result = ie.old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=c.policy,settings=ie.external.settings(),seed=201,decision_provider=c)
    return result,c
