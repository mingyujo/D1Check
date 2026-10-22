"""Request order followed by a common public, one-request response estimator."""
import copy
import hashlib
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a24_rr_600_20261020.rr_policy import RoundRobin

VERSION = 'A24_DYNAMIC_RESPONSE_ROUTE_V1'
MODES = ('FIFO_DYN', 'EDF_DYN', 'RR_DYN')

def tie(q):
    return q['scheduled_arrival_ns'], q['ordinal'], q['request_id']

def route_tie(request_id, route):
    return hashlib.sha256((request_id+'|'+route).encode('utf-8')).hexdigest()

class DynamicPolicy:
    def __init__(self, nominal, physics, mode):
        if mode not in MODES or physics.cpu_slots != 3:
            raise ValueError('Unsupported policy or capacity')
        self.nominal, self.physics, self.mode = nominal, physics, mode
        self.rr = RoundRobin() if mode == 'RR_DYN' else None
        self.calls = []

    def __call__(self, s):
        queue, owners = s['queue'], s['owners']
        counts = {r:sum(o['route']==r for o in owners) for r in ('CPU','GPU')}
        if (any(o['route'] not in counts for o in owners) or counts['CPU']>3 or counts['GPU']>1
            or len({q['request_id'] for q in queue}) != len(queue)
            or any(q['task'] not in ('C','D') or q['queue_entry_ns']>s['now_ns']
                   or q['scheduled_arrival_ns']>s['now_ns'] for q in queue)):
            raise ValueError('Invalid public state')
        free = [r for r in ('CPU','GPU') if counts[r] < (3 if r=='CPU' else 1)]
        before = self.rr.turn if self.rr else None
        if not queue or not free:
            return dict(kind='RESOURCE_WAIT')
        if self.rr:
            original = self.rr(s)
            q = next(q for q in queue if q['request_id']==original['request_id'])
        else:
            q = min(queue, key=tie if self.mode=='FIFO_DYN' else lambda q:(q['deadline_ns'],*tie(q)))
        T = s['sensor']['temperature_c']
        if not math.isfinite(T):raise ValueError('Invalid temperature')
        cpu_infer = sum(o['route']=='CPU' and o['stage']==1 for o in owners)
        estimates = []
        for route in free:
            v = list(self.nominal.vector(q, route, s))
            if len(v)!=5 or any(not math.isfinite(x) or x<0 for x in v):
                raise ValueError('Invalid public nominal vector')
            thermal_rate = self.physics.speed(T, route, 1, q['task'])
            contention = 1+self.physics.beta*cpu_infer if route=='CPU' else 1.
            rate = thermal_rate/contention
            if not math.isfinite(rate) or rate<=0:raise ValueError('Invalid public speed')
            boundary = 2 if q['task']=='C' else 3
            response = sum(v[:boundary])-v[1]+v[1]/rate
            estimates.append(dict(route=route, nominal_vector_s=v, thermal_rate=thermal_rate,
                contention_factor=contention, progress_rate=rate,
                response_after_dispatch_s=response, tie_sha256=route_tie(q['request_id'], route)))
        best = min(estimates, key=lambda x:(x['response_after_dispatch_s'],x['tie_sha256']))
        action = dict(kind='DISPATCH', request_id=q['request_id'], route=best['route'])
        self.calls.append(dict(time_ns=s['now_ns'],action=copy.deepcopy(action),mode=self.mode,
            selected_task=q['task'],owner_counts=counts,free_routes=free,estimates=estimates,
            turn_before=before,turn_after=self.rr.turn if self.rr else None,
            direct_baseline=True,future_information=False,NN_execution=False,
            rolling_horizon=False,voluntary_WAIT=False,post_NN_override=False,version=VERSION))
        return action
