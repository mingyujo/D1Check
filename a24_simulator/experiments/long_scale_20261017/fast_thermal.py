"""Exact causal exponential-state accumulator; no coefficients/physics changed.

Coefficient resolution still calls the frozen predictor for the states observed
so far. The .9s electrical observer is separate from this AP basis.
"""
import copy,math
import numpy as np

class FastThermal:
    def __init__(self,module,original,public,model):
        self.module,self.original,self.public,self.model=module,original,public,model
        self.time=0.;self.z=np.zeros(len(module.STATES));self.seen=set();self.cache={}
        self.initial,self.anchor,self.hi,self.slope,self.slope_known=module._initial(public)
        self.config=model['config'];self.maximum_validation_error=0.
    def advance(self,owners,t):
        if t<self.time:raise ValueError('Nonmonotonic AP state')
        recent=[r for r in owners if r['end_s']>self.time and r['start_s']<t]
        edges=sorted(set([self.time,t]+[max(self.time,min(t,r[k])) for r in recent for k in ('start_s','end_s')]))
        for a,b in zip(edges,edges[1:]):
            active=[r for r in recent if r['start_s']<b and r['end_s']>a]
            labels=sorted(('classification' if r['task']=='C' else 'detection')+'_'+r['route'] for r in active)
            s='+'.join(labels) or 'idle';k=-math.expm1(-(b-a)/self.config['activity_tau_s'])
            self.z*=1-k
            if s!='idle':self.z[self.module.STATES.index(s)]+=k;self.seen.add(s)
        self.time=t
    def coefficients(self):
        key=tuple(sorted(self.seen))
        if key not in self.cache:
            # A basis probe only resolves the same fixed coefficients. Its
            # synthetic activity/temperature prediction is never a measurement.
            session=copy.deepcopy(self.public);session.pop('owner_intervals',None)
            states=list(key) or ['idle'];session['state_intervals']=[dict(start_s=i,end_s=i+1,state=s) for i,s in enumerate(states)]
            p=self.original(self.model,session,times=[float(len(states))],include_features=True,allow_extrapolation=True)
            if p['status']!='CONDITIONAL_AP_PREDICTION':raise ValueError(p)
            self.cache[key]=p['local_coefficients']
        return self.cache[key]
    def predict(self,model,session,times,include_features=False,allow_extrapolation=True):
        if len(times)!=1:raise ValueError('Streaming AP is single-time only')
        t=float(times[0]);self.advance(session['owner_intervals'],t);coef=self.coefficients()
        elapsed=t-self.anchor;decay=math.exp(-elapsed/self.config['cooling_tau_s']);eq=1-decay
        ambient=session.get('ambient_c');known=isinstance(ambient,(int,float)) and math.isfinite(ambient)
        momentum=self.slope*self.config['pre_slope_tau_s']*(-math.expm1(-elapsed/self.config['pre_slope_tau_s']))*decay
        baseline=self.initial*decay+(ambient*eq if known else 0)
        value=baseline+coef[0]*(0 if known else eq)+coef[1]*(eq if known else 0)+coef[2]*momentum+float(self.z@np.asarray(coef[3:]))
        return dict(status='CONDITIONAL_AP_PREDICTION',ap_c=[value],local_coefficients=coef,
                    streaming_exact_basis=True,coefficient_fitting=False)
