"""Engine-only replay of frozen potentials, separate from public actor inputs.

The actor receives SavedNominal only. No latent vectors, future admission times
or future arrivals are returned to the actor. Original engine and Physics run.
All ten guard-on neural episodes must exactly reproduce the original bank/model.
"""
import copy
from timing_model import context_of


class BankModel:
    def __init__(self,jobs,contexts):
        self.jobs={j['request_id']:j for j in jobs};self.contexts=contexts

    def request_context(self,public,q):
        return context_of(self.contexts[q['request_id']],q,True)

    def admission(self,context,task,potential,protocol):
        if protocol!='SERIAL':raise ValueError('Only original SERIAL admission')
        j=self.jobs[potential[2]]
        if j['task']!=task:raise ValueError('Admission binding')
        return copy.deepcopy(j['admission'])

    def draw_latent_serial(self,action,state,potential):
        if action['request_id']!=potential[2]:raise ValueError('Frozen potential binding')
        return copy.deepcopy(self.jobs[action['request_id']]['routes'][action['route']])


class SavedNominal:
    def __init__(self,public,original_calls):
        self.values={}
        for call in original_calls:
            for key,value in (call.get('nominal_vectors') or {}).items():
                vector=tuple(value)
                if key in self.values and self.values[key]!=vector:raise ValueError('State-dependent estimate cannot be silently cached')
                self.values[key]=vector
        for q in public['requests']:
            for route in ('CPU','GPU'):
                if q['request_id']+'|'+route not in self.values:raise ValueError('Missing public nominal estimate')

    def vector(self,q,route,state):
        # These are the ORIGINAL public nominal estimates, never the realized
        # phase vectors in BankModel. Values must remain constant per request.
        return list(self.values[q['request_id']+'|'+route])
