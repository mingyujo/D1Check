"""Frozen v3 thermal-only hybrid on the existing CPU/GPU event ABI.

Exact streaming form of the delivered v3 head. No fitting, service feedback,
new power coefficients, unseen arrivals, or device operations. The scoped
forecast hook is restored even on failure; original source files are untouched.
"""
import copy, hashlib, json, math
from contextlib import contextmanager
from pathlib import Path
import numpy as np
from tools import d1_rolling_execution_pilot as prior

p = prior.new.p
ROOT = p.ROOT
MODEL = ROOT/'docs/results/rolling_hybrid_pilot_07/model.json'
UPSTREAM_SHA = '6dd806bc30c5d69dd07237dc8fbe0bc09ed90a86fede4d86294ae14be2eb1196'
STATES = ('classification_CPU', 'detection_CPU', 'classification_GPU', 'classification_GPU+detection_CPU')


def load():
    candidate = json.loads(MODEL.read_text(encoding='utf-8'))
    frozen, initial = p.inputs(p.BUNDLE)
    if candidate['variant'] != 'thermal_only_hybrid_v1' or candidate['energy']['gain'] != 0:
        raise ValueError('requires delivered frozen thermal-only hybrid')
    if candidate['energy']['increments'] != frozen['energy_increment_w'] or candidate['service']['sha256'] != p.MODEL_SHA:
        raise ValueError('original energy/service identity changed')
    return frozen, initial, candidate


def initialize(initial, candidate):
    """Same alpha-regularized R/H estimate from pre-issue AP; no known load history.

This pilot uses the original measured idle preload. Nonempty earlier workload
history is unsupported here, rather than silently initializing its slow state0.
"""
    if initial.get('history'):
        raise ValueError('pilot initialization supports the fixed idle preload only')
    pre = initial['preload']; head = candidate['thermal']
    ts = np.array([r['t'] for r in pre], dtype=float)
    ys = np.array([r['ap'] for r in pre], dtype=float)
    if len(pre)<8 or not np.all(np.isfinite(ys)) or any(not r['lo']<=r['t']<=r['hi']<35 for r in pre):
        raise ValueError('invalid/future preload')
    if np.any(np.diff(ts)<=0) or ts[-1]-ts[0]<20 or np.any(np.diff(ts)>10):
        raise ValueError('preload time coverage')
    beta = head['beta']; dt = ts-ts[0]; eb = np.exp(-beta*dt)
    matrix = np.column_stack((1-eb, [p.memory.convolution(beta,30.,float(t)) for t in dt]))
    norms = np.linalg.norm(matrix,axis=0)
    if min(norms)<=0 or np.linalg.matrix_rank(matrix)<2: raise ValueError('unidentified preload')
    alpha = head['alpha']
    if not 0<=alpha<=1: raise ValueError('invalid frozen alpha')
    target = ys-ys[0]*eb
    if alpha==0:
        reference = float(matrix[:,0]@target/(matrix[:,0]@matrix[:,0])); h0=0.
    else:
        aug = np.vstack((matrix/norms,[0.,math.sqrt((1-alpha)/alpha)]))
        reference,h0 = map(float,np.linalg.lstsq(aug,np.r_[target,0.],rcond=None)[0]/norms)
    return dict(anchor_s=float(ts[-1]),reference_c=reference,t=float(ys[-1]),
                h=h0*math.exp(-(ts[-1]-ts[0])/30.),slow=0.,label='resident_idle')


def advance(state, label, dt, candidate):
    if not math.isfinite(dt) or dt<0: raise ValueError('invalid time progress')
    label = 'resident_idle' if label=='idle' else label
    if label not in ('resident_idle',)+STATES: raise ValueError('unmeasured thermal state')
    head=candidate['thermal']; beta=head['beta']; tau=head['slow_tau_s']; theta=head['coefficients']
    u=0. if label=='resident_idle' else theta[STATES.index(label)]
    power=0. if label=='resident_idle' else candidate['energy']['increments'][label]
    eb=math.exp(-beta*dt); es=math.exp(-dt/tau)
    slow=state['slow']*es+theta[4]*power*tau*(-math.expm1(-dt/tau))
    fast=state['reference_c']+(state['t']-state['slow']-state['reference_c'])*eb+u*(-math.expm1(-beta*dt))/beta+state['h']*p.memory.convolution(beta,30.,dt)
    return dict(state,t=fast+slow,h=state['h']*math.exp(-dt/30.),slow=slow)


def path(segments, queries, initial, candidate):
    state=initialize(initial,candidate); cursor=state['anchor_s']; out=[]; pos=0
    if not queries or queries[0]<35 or any(b<=a for a,b in zip(queries,queries[1:])): raise ValueError('query grid')
    # Validate the complete covered schedule including idle intervals.
    end=segments[0]['start_s']
    for s in segments:
        if abs(s['start_s']-end)>1e-6 or s['end_s']<end: raise ValueError('incomplete schedule')
        end=s['end_s']
        a=max(cursor,s['start_s']); b=s['end_s']
        if b<=a: continue
        if a>cursor+1e-6: raise ValueError('uncovered post-anchor interval')
        while pos<len(queries) and queries[pos]<=b:
            out.append(advance(state,s['state'],queries[pos]-a,candidate)['t']); pos+=1
        state=advance(state,s['state'],b-a,candidate); cursor=b
    if pos!=len(queries): raise ValueError('query beyond schedule')
    return out


class ThermalMixin:
    def __init__(self, frozen, initial, *args):
        super().__init__(frozen,initial,*args)
        self.hybrid_candidate=load()[2]; self.hybrid_initial=copy.deepcopy(initial)
        self.hybrid_state=initialize(initial,self.hybrid_candidate)
        self.init.update(anchor_s=self.hybrid_state['anchor_s'],reference_c=self.hybrid_state['reference_c'])
        self.t=self.hybrid_state['t']; self.h=self.hybrid_state['h']
    def observe(self, now_ns, lanes):
        previous_now=self.now; previous_label=self.label; state=self.hybrid_state
        start=max(previous_now,state['anchor_s']); now=now_ns/1e9
        super().observe(now_ns,lanes)  # Preserve counters/credit/EMA/phase semantics.
        if hasattr(self,'grid'):
            for second in range(max(35,math.floor(previous_now)+1),min(180,math.floor(now))+1):
                if second>=start:self.grid[second]=advance(state,previous_label,second-start,self.hybrid_candidate)['t']
        if now>start: state=advance(state,previous_label,now-start,self.hybrid_candidate)
        self.hybrid_state=state; self.t=state['t']; self.h=state['h']


class ExecutionController(ThermalMixin,prior.new.Controller): pass
class OriginalController(ThermalMixin,prior.original.Controller): pass
class FixtureController(ThermalMixin,prior.FixtureController): pass
class BandController(ThermalMixin,prior.external.BandController): pass
class TritonController(ThermalMixin,prior.triton.Controller): pass


def controller(role,frozen,initial):
    return {'Band':BandController,'Triton':TritonController,'OriginalV2':OriginalController,
            'ExecutionPrefix':ExecutionController}[role](frozen,initial,*([prior.triton.OFF] if role=='Triton' else []))


def costs(controller,jobs,now_ns):
    if not hasattr(controller,'hybrid_state'):raise ValueError('hybrid forecast requires corrected online state')
    now=now_ns/1e9; candidate=controller.hybrid_candidate; head=candidate['thermal']; beta=head['beta']; tau=head['slow_tau_s']; state=controller.hybrid_state
    times=np.arange(max(35,math.ceil(now)),181.,dtype=float); dt=times-now
    prediction=(state['reference_c']+(state['t']-state['slow']-state['reference_c'])*np.exp(-beta*dt)+state['h']*prior.new.old.fast.convolution(beta,dt)+state['slow']*np.exp(-dt/tau))
    segments=p.segments(jobs,now,180.); volumes={s:0. for s in candidate['energy']['increments']}; energy=0.
    for segment in segments:
        label=segment['state']; a=segment['start_s']; b=segment['end_s']
        if label=='idle':continue
        if label not in STATES:raise ValueError('unmeasured forecast state')
        duration=max(0.,min(120.,b)-a); power=candidate['energy']['increments'][label]
        energy+=duration*power;volumes[label]+=duration
        da=np.maximum(0.,times-a);db=np.maximum(0.,times-b)
        prediction+=head['coefficients'][STATES.index(label)]*((-np.expm1(-beta*da))-(-np.expm1(-beta*db)))/beta
        prediction+=head['coefficients'][4]*power*tau*((-np.expm1(-da/tau))-(-np.expm1(-db/tau)))
    peak=max(controller.t,float(prediction.max()) if len(prediction) else controller.t)
    return dict(remaining_increment_j=energy,peak_ap_c=peak,global_peak_ap_c=max(peak,max(controller.grid.values(),default=peak)),volumes=volumes)


@contextmanager
def forecast_scope():
    fast=prior.new.old.fast; old_costs=fast.costs; old_key=prior.new.state_key
    def key(c,q,l,n):
        value=[old_key(c,q,l,n),c.hybrid_state,UPSTREAM_SHA]
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    fast.costs=costs; prior.new.state_key=key
    try:yield
    finally:fast.costs=old_costs;prior.new.state_key=old_key


def account(result,initial,frozen):
    segments,original,end=p.account(result,initial,frozen)
    values=path(segments,list(range(35,end+1)),initial,load()[2])
    return segments,dict(original,ap_path=values),end
