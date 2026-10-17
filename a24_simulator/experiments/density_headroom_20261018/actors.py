"""Offline feasible-witness heuristics. Future route work is deliberately known.

Knowledge is relaxed; physical ownership, release times, five phases, original
nominal WAIT mask and its caps remain unchanged. No global-optimality claim.
"""
import copy
import math

RECIPES = ('ENERGY', 'TOTAL', 'REGRET', 'LP_ROUTE', 'HEAT', 'COOL35', 'COOL36', 'SLA_ENERGY')


class Replay:
    def __init__(self, decisions): self.decisions = decisions; self.i = 0; self.calls = []
    def __call__(self, state):
        old = self.decisions[self.i]
        if state['now_ns'] != old['time_ns']: raise ValueError('Exact replay decision clock')
        self.i += 1
        self.calls.append(dict(time_ns=state['now_ns'],action=copy.deepcopy(old['action']),common_coalescing=True))
        return copy.deepcopy(old['action'])


class Actor:
    def __init__(self, recipe, jobs, physics, nominal, preferred, protected):
        self.recipe = recipe; self.jobs = {j['request_id']: j for j in jobs}
        self.physics = physics; self.nominal = nominal; self.preferred = preferred
        self.protected = set(protected); self.waited = set(); self.wait_per_head = {}; self.calls = []

    def __call__(self, state):
        q = state['queue']; busy = {o['route'] for o in state['owners']}
        free = [r for r in ('CPU', 'GPU') if r not in busy]
        now = state['now_ns']/1e9; T = state['sensor']['temperature_c']; c = self.physics.c; H = self.physics.shared
        head = min(q, key=lambda x: (x['scheduled_arrival_ns'], x['ordinal'], x['request_id']))
        def nominal_occ(j,r):
            return sum(self.nominal.vector(j,r,state))/self.physics.speed(T,r,1)
        def legal(dose):
            return state['wait_used_ns']/1e9+dose <= 12+1e-10 and self.wait_per_head.get(head['request_id'],0)+dose <= 1.5+1e-10 and all(
                j['priority'] != 'U' or now+dose+min(nominal_occ(j,r) for r in ('CPU','GPU')) <= j['deadline_ns']/1e9 for j in q)
        def finish(action, common=False):
            self.calls.append(dict(time_ns=state['now_ns'], action=copy.deepcopy(action), recipe=self.recipe,
                                   common_coalescing=common, wait_200ms_legal=legal(.2), queue_size=len(q)))
            return action
        if len(q)==1 and not busy and head['request_id'] not in self.waited and state['wait_used_ns']+50_000_000<=12_000_000_000:
            if min(nominal_occ(head,r) for r in free)+.05 < head['deadline_ns']/1e9-now:
                self.waited.add(head['request_id'])
                return finish(dict(kind='WAIT',wait_ns=50_000_000), True)
        threshold = {'COOL35':35.25,'COOL36':36.0}.get(self.recipe)
        if threshold is not None and T > threshold and legal(.2):
            self.wait_per_head[head['request_id']] = self.wait_per_head.get(head['request_id'],0)+.2
            return finish(dict(kind='WAIT',wait_ns=200_000_000))
        options = []
        for j in q:
            values = {}
            for r in ('CPU','GPU'):
                v = [t/1e9 for t in self.jobs[j['request_id']]['routes'][r]['stages_ns']]
                f = self.physics.speed(T,r,1); non = sum(v)-v[1]; duration = non+v[1]/f
                response = sum(v[:2 if j['task']=='C' else 3])-v[1]+v[1]/f
                A = self.physics.solo[('classification' if j['task']=='C' else 'detection')+'_'+r]-H
                leak = math.exp(c.leakage_per_c*(T-c.reference_c))
                energy = (A*(1-c.leakage_fraction)+A*c.leakage_fraction*leak+H/2)*non
                energy += (A*(1-c.leakage_fraction)*f*f+(A*c.leakage_fraction*leak+H/2)/f)*v[1]
                values[r] = (energy, duration, response)
            for r in free:
                energy,duration,response = values[r]; other='GPU' if r=='CPU' else 'CPU'
                slack = j['deadline_ns']/1e9-now-response
                protected = j['request_id'] in self.protected
                rescue = protected and slack <= .15+min(v[1] for v in values.values())
                # Rescue policy is a heuristic, never a substitute for the
                # final count-SLA check on the actual resulting schedule.
                prefix = (0 if rescue and slack>=0 else 1, 0 if protected and slack>=0 else 1)
                total = energy+c.baseline*.5*duration
                if self.recipe == 'ENERGY': score=energy
                elif self.recipe in ('TOTAL','COOL35','COOL36','SLA_ENERGY'): score=total
                elif self.recipe == 'REGRET': score=total-(values[other][0]+c.baseline*.5*values[other][1])
                elif self.recipe == 'LP_ROUTE': score=total+(0 if self.preferred.get(j['request_id'])==r else 10)
                elif self.recipe == 'HEAT': score=energy/max(.001,duration)
                else: raise ValueError('Unregistered recipe')
                if self.recipe=='SLA_ENERGY' and protected: prefix=(0 if slack>=0 else 1,0)
                options.append(((*prefix,score,j['deadline_ns'],j['ordinal'],r!='CPU'),j,r))
        _, j, r = min(options,key=lambda x:x[0])
        return finish(dict(kind='DISPATCH',request_id=j['request_id'],route=r))
