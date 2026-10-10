"""Arrived-queue L0 continuation forecasts; fixed AP/J windows, no future trace.

The physical bank is unchanged. Prediction admission is an explicit policy
restriction, never a physical capability or a guarantee of actual service.
"""
from __future__ import annotations
import copy
import math
import time
import numpy as np
import torch
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_service_backlog as previous
from tools import d1_list_candidate_rl_training as training

RULE = 'LIST_ARRIVED_QUEUE_TAIL_PC_V3'
PPO = 'LIST_ARRIVED_QUEUE_TAIL_PPO_PC_V1'
VERSION = 'arrived-queue-l0-continuation-tail-v1'
REPLACEMENTS = {
    'proxy_span_duration_over_6s': 'arrived_queue_drain_over_6s',
    'proxy_span_whole_device_J_over_1J': 'arrived_queue_J120_difference_from_L0_over_1J',
    'proxy_end_AP_delta_over_1C': 'arrived_queue_AP180_difference_from_L0_over_1C',
    'proxy_span_peak_AP_delta_over_1C': 'arrived_queue_grid_peak_difference_from_L0_over_1C',
}
RESPONSE_NAMES = {name:name.replace('predicted_response','L0_suffix_predicted_response').replace('slack_after_this_atom','slack_after_L0_suffix')
    for name in c.CANDIDATE_FIELDS if 'predicted_response' in name or 'slack_after_this_atom' in name}


def continuation(queue, owned, action, now, means, deadline=None):
    """Commit one physical atom, then dispatch currently legal L0 FIFO heads.

    Never reserve a currently occupied faster lane. A prefix hold blocks all
    dispatch until its timer or a predicted actual-lane-available interrupt.
    Mean phase callbacks do not release lanes or cancel holds.
    """
    if any(q['arrival_ns']/1e9 > now for q in queue):
        raise ValueError('future request in arrived-queue forecast')
    if len({q['id'] for q in queue}) != len(queue):
        raise ValueError('duplicate arrived request')
    jobs = copy.deepcopy(owned)
    waiting = {q['id']: copy.deepcopy(q) for q in queue}
    if any(j['end'] <= now for j in jobs):
        raise c.formula.PredictionUnknown('public owned mean forecast overrun')
    predictions = {}

    def can_start(q, backend, at):
        candidate = dict(task=q['task'], backend=backend)
        return backend in c.p.backends(q) and all(
            j['end'] <= at or c.formula.compatible(candidate, j) for j in jobs)

    def place(q, backend, at):
        if not can_start(q, backend, at):
            raise ValueError('forecast duplicates occupied/incompatible lane')
        mean = means[(q['task'], backend)]
        job = dict(id=q['id'], task=q['task'], backend=backend,
                   start=at, end=at+sum(mean))
        jobs.append(job)
        predictions[q['id']] = dict(backend=backend, start=at, end=job['end'],
            response=at+sum(mean[:2 if q['task']=='classification' else 3]))
        del waiting[q['id']]

    for immediate in action['jobs']:
        rid = immediate['request_id']
        if rid not in waiting:
            raise ValueError('unknown/duplicate committed atom')
        place(waiting[rid], immediate['backend'], now)
    at = now
    if action['wait']:
        # No unseen arrival is invented. Any lane release ends an armed hold.
        at = min([now+action['wait']] + [j['end'] for j in jobs if j['end']>now])
    rounds = 0
    while waiting:
        if deadline is not None and time.time()>=deadline:
            raise TimeoutError('forecast saving reserve reached')
        rounds += 1
        if rounds > 3*len(queue)+4:
            raise ValueError('forecast failed finite time progression')
        heads = c.heads_of(list(waiting.values()))
        ordered = sorted((q for q in heads.values() if q),
            key=lambda q:(c.due(q),q['arrival_ns'],q['ordinal'],q['id']))
        placed = False
        for q in ordered:
            options = [b for b in c.p.backends(q) if can_start(q,b,at)]
            if options:
                backend = min(options, key=lambda b:(sum(means[(q['task'],b)]),b!='CPU'))
                place(q,backend,at); placed = True
        if not placed:
            following = [j['end'] for j in jobs if j['end']>at]
            if not following:
                raise c.formula.PredictionUnknown('no supported continuation')
            at = min(following)
    if max((j['end'] for j in jobs),default=now)>120:
        raise c.formula.PredictionUnknown('arrived work cannot drain by common120s')
    return dict(jobs=jobs,prediction=predictions,drain=max((j['end'] for j in jobs),default=now))


class TailController(previous.BacklogList):
    def __init__(self,*args,learned=False,forced_first=None,fixture_suffix=False,**kwargs):
        super().__init__(*args,**kwargs)
        if learned and (forced_first is not None or fixture_suffix):
            raise ValueError('forced diagnostic choices cannot be used as on-policy learning')
        self.learned = learned
        self.forced_first = forced_first
        self.fixture_suffix = fixture_suffix
        self.forecast_deadline = None
        self.public_policy = PPO if learned else RULE
        self.candidate_fields = tuple(REPLACEMENTS.get(k,RESPONSE_NAMES.get(k,k)) for k in c.CANDIDATE_FIELDS)
        self.schema_id = c.digest(dict(version=VERSION,parent_schema=self.schema_id,
            state=self.state_fields,candidate=self.candidate_fields,physical_bank='unchanged8',
            admission='per-arrived-C response/per-D tardiness/J120 vsL0; V2wait/backlog',
            forecast='first atom then no-wait actual-L0 heads; arrived queue only',
            AP_grid='integer35..180 including public past',J_window='0..120'))

    def tail_cost(self,work,now):
        if abs(now-self.now)>1e-9 or any(point>now for point in self.grid):
            raise ValueError('public thermal observer/forecast time mismatch')
        segments = c.p.segments([dict(state=j['task']+'_'+j['backend'],
            start=j['start'],end=j['end']) for j in work['jobs']],now,180.)
        t,h = self.t,self.h
        # Only the KPI's one-second grid, not invented transition maxima.
        peak = max(self.grid.values(),default=-math.inf)
        energy = self.initial['preload_power_w']*max(0.,120.-now)
        slopes = self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        for segment in segments:
            if self.forecast_deadline is not None and time.time()>=self.forecast_deadline:
                raise TimeoutError('thermal forecast saving reserve reached')
            a,b = segment['start_s'],segment['end_s']
            label = 'resident_idle' if segment['state']=='idle' else segment['state']
            if label!='resident_idle' and label not in self.frozen['energy_increment_w']:
                raise c.formula.PredictionUnknown('unsupported arrived-queue energy state')
            energy += max(0.,min(120.,b)-a)*self.frozen['energy_increment_w'].get(label,0.)
            u = slopes[label]-slopes['resident_idle']
            for point in range(max(35,math.floor(a)+1),min(180,math.floor(b))+1):
                peak = max(peak,c.p.thermal_step(t,h,u,self.init['reference_c'],self.frozen['ap'],point-a)[0])
            t,h = c.p.thermal_step(t,h,u,self.init['reference_c'],self.frozen['ap'],b-a)
        if not math.isfinite(peak):
            raise c.formula.PredictionUnknown('missing AP observation grid')
        return dict(energy=energy,peak_ap=peak,end_ap=t,end_h=h,
                    work_count=len(work['jobs']),drain=work['drain'])

    def encode(self,queue,lanes,now_ns,actions):
        encoded = super().encode(queue,lanes,now_ns,actions)
        physical = encoded['mask'].copy()
        now = now_ns/1e9
        base = encoded['base']
        forecasts = []
        for action in actions:
            if self.forecast_deadline is not None and time.time()>=self.forecast_deadline:
                raise TimeoutError('candidate forecast saving reserve reached')
            try:
                work = continuation(queue,self._active(lanes,now),action,now,self.means,self.forecast_deadline)
                forecast = dict(known=True,**work)
                forecast.update(self.tail_cost(work,now))
                forecasts.append(forecast)
            except c.formula.PredictionUnknown:
                forecasts.append(dict(known=False))
        admission = np.zeros(8,dtype=bool)
        reference = forecasts[base]
        admission[base] = True # Physical L0 remains possible even with unknown forecasts.
        for i,(action,forecast) in enumerate(zip(actions,forecasts)):
            if i==base or not forecast['known'] or not reference['known']:
                continue
            if (action['wait']>0 and sum(q['task']=='detection' for q in queue)>1
                or any(self.request_wait.get(rid,0.)+action['wait']>.25 for rid in action['held'])
                or any(q['task']=='classification' and q['id'] in action['held'] for q in queue)):
                continue
            nonworse = forecast['energy']<=reference['energy']
            for q in queue:
                new,old = forecast['prediction'][q['id']]['response'],reference['prediction'][q['id']]['response']
                if q['task']=='classification':nonworse &= new<=old
                else:nonworse &= max(0.,new-c.due(q)/1e9)<=max(0.,old-c.due(q)/1e9)
            admission[i] = nonworse
        costs = {i:f for i,f in enumerate(forecasts) if admission[i] and f['known']}
        rule = min(costs,key=lambda i:(costs[i]['peak_ap'],costs[i]['end_ap'],costs[i]['energy'],i!=base,i)) if costs else base
        for i,forecast in enumerate(forecasts):
            encoded['candidates'][i,c.CANDIDATE_FIELDS.index('prediction_supported')] = float(forecast['known'])
            for task,prefix in (('classification','C_head'),('detection','D_head')):
                head = c.heads_of(queue)[task]
                names=(prefix+'.predicted_response_over_own_deadline',prefix+'_slack_after_this_atom_over_own_deadline')
                response = forecast['prediction'][head['id']]['response'] if head and forecast['known'] else None
                values = ((response-head['arrival_ns']/1e9)/(head['deadline_offset_ns']/1e9),
                          (c.due(head)/1e9-response)/(head['deadline_offset_ns']/1e9)) if response is not None else (0.,0.)
                for name,value in zip(names,values):encoded['candidates'][i,c.CANDIDATE_FIELDS.index(name)]=value
            for old,new in REPLACEMENTS.items():
                value = 0.
                if forecast['known'] and reference['known']:
                    value = ((forecast['drain']-now)/6 if old=='proxy_span_duration_over_6s'
                             else forecast['energy']-reference['energy'] if 'whole_device_J' in old
                             else forecast['end_ap']-reference['end_ap'] if 'end_AP' in old
                             else forecast['peak_ap']-reference['peak_ap'])
                encoded['candidates'][i,c.CANDIDATE_FIELDS.index(old)] = value
            for name in ('proxy_span_duration_known','span_J_known','end_AP_known','span_peak_known'):
                encoded['candidates'][i,c.CANDIDATE_FIELDS.index(name)] = float(forecast['known'] and reference['known'])
        encoded.update(mask=admission,physical_mask=physical,prediction_admission_mask=admission.copy(),
            tail_forecasts=forecasts,rule_reference=rule,candidate_names=self.candidate_fields,
            schema_id=self.schema_id,prediction_guard_is_service_guarantee=False)
        if not encoded['mask'][base] or (encoded['mask'] & ~physical).any():
            raise ValueError('forecast admission removed L0/introduced unsupported action')
        return encoded

    def choose(self,encoded,actions,queue):
        reference = encoded['rule_reference']
        if not encoded['tail_forecasts'][encoded['base']]['known']:
            self.fallbacks += 1
        if self.forced_first is not None and not self.snapshots:
            permitted = np.flatnonzero(encoded['mask'])
            return int(permitted[self.forced_first%len(permitted)])
        if self.fixture_suffix and self.snapshots:
            return encoded['base']
        if not self.learned:
            return reference
        with torch.no_grad():
            distribution,values = self.network(torch.from_numpy(encoded['state'])[None],
                torch.from_numpy(encoded['candidates'])[None],torch.from_numpy(encoded['mask'])[None])
        encoded['old_value'] = values[0].numpy().copy()
        if self.deterministic:
            scores = distribution.logits[0].numpy()
            index = reference if scores[reference]==scores.max() else int(scores.argmax())
        else:index = int(distribution.sample().item())
        encoded['logprob'] = float(distribution.log_prob(torch.tensor([index])).item())
        return index

    def __call__(self,*args,**kwargs):
        before = len(self.snapshots)
        out = super().__call__(*args,**kwargs)
        if len(self.snapshots)>before:
            step = self.snapshots[-1]
            step['informative'] = int(step['mask'].sum())>1
            step['actor_eligible'] = self.learned and not self.deterministic and step['informative']
        return out


class TailLearner(training.Learner):
    def fresh_controller(self,frozen,initial):
        controller = TailController(frozen,initial,network=self.network,
            learned=True,deterministic=False,feature_variant='head2+C_next')
        if controller.schema_id!=self.schema_id:
            raise ValueError('tail controller schema mismatch')
        return controller
