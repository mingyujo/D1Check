"""One posthoc preparation-memory candidate; never changes a frozen/default model."""
from __future__ import annotations
import math
import numpy as np
from tools.d1_ap_idle_response import preload_reference
from tools.d1_arrival_recorded_replay_analysis import state_key

VERSION = 'ap-preparation-memory-v1'


def convolution(beta, tau, dt):
    difference = beta - 1/tau
    eb = math.exp(-beta*dt)
    return dt*eb if abs(difference) < 1e-10 else (math.exp(-dt/tau)-eb)/difference


def advance(t, h, u, reference, beta, tau, gamma, dt):
    if not all(math.isfinite(x) for x in (t,h,u,reference,beta,tau,gamma,dt)) or min(beta,tau)<=0 or min(dt,gamma)<0:
        raise ValueError('invalid state/parameter')
    target_h = gamma*u
    eb, eh = math.exp(-beta*dt), math.exp(-dt/tau)
    return (reference+(t-reference)*eb+(u+target_h)*(1-eb)/beta+
            (h-target_h)*convolution(beta,tau,dt), target_h+(h-target_h)*eh)


def initialize(preload, beta, tau):
    samples=[(float(p['t']),float(p['ap'])) for p in preload]
    # Reuse the existing duration, sample count, finite and gap checks.
    preload_reference(samples,beta)
    if not math.isfinite(tau) or tau<=0:
        raise ValueError('invalid tau')
    if any(not p['lo']<=p['t']<=p['hi'] for p in preload):
        raise ValueError('invalid sensor time bracket')
    t0,y0=samples[0]
    matrix=np.array([[1-math.exp(-beta*(t-t0)),convolution(beta,tau,t-t0)] for t,y in samples])
    target=np.array([y-y0*math.exp(-beta*(t-t0)) for t,y in samples])
    norms=np.linalg.norm(matrix,axis=0)
    if min(norms)<=0:
        raise ValueError('unidentified initial memory')
    scaled=matrix/norms
    singular=np.linalg.svd(scaled,compute_uv=False)
    if singular[-1] <= singular[0]*1e-12:
        raise ValueError('rank deficient initial memory')
    coefficients=np.linalg.lstsq(scaled,target,rcond=None)[0]/norms
    reference,h0=map(float,coefficients)
    residual=matrix@coefficients-target
    return dict(reference_c=reference,h_first_c_per_s=h0,
        h_last_c_per_s=h0*math.exp(-(samples[-1][0]-t0)/tau),
        anchor_s=samples[-1][0],anchor_ap_c=samples[-1][1],
        input_end_s=preload[-1]['hi'],samples=len(samples),duration_s=samples[-1][0]-t0,
        scaled_condition=float(singular[0]/singular[-1]),singular_values=singular.tolist(),
        preload_rmse_c=float(np.sqrt(np.mean(residual**2))),
        reference_is_ambient=False,latent_is_measured_internal_temperature=False)


def predict(case, parameters, tau, gamma):
    p=case['inputs'];segments=p['segments'];queries=p['query_s']
    beta=parameters['ap_cooling_rate_per_s'];slopes=parameters['ap_slope_at_30_c_per_s']
    first=min(s['start_s'] for s in segments if s['state']!='idle')
    if (not queries or any(not math.isfinite(q) for q in queries) or
        any(a>=b for a,b in zip(queries,queries[1:])) or queries[0]<first or
        any(x['hi']>=first for x in p['preload'])):
        raise ValueError('future/preload boundary or unordered queries')
    cursor=0.
    for s in segments:
        if abs(s['start_s']-cursor)>1e-6 or not math.isfinite(s['end_s']) or s['end_s']<cursor:
            raise ValueError('noncontiguous schedule')
        if state_key(s['state']) not in slopes:
            raise ValueError('unsupported state')
        cursor=s['end_s']
    if queries[-1]>cursor:
        raise ValueError('query beyond schedule')
    init=initialize(p['preload'],beta,tau)
    anchor=init['anchor_s']
    if anchor<0 or anchor>=first:
        raise ValueError('last preload must be after common start, before load')
    return _propagate(segments,queries,slopes,beta,tau,gamma,init),init


def _propagate(segments,queries,slopes,beta,tau,gamma,init):
    """Internal propagation after predict() validates the complete input boundary."""
    anchor=init['anchor_s']
    t,h=init['anchor_ap_c'],init['h_last_c_per_s']
    result=[];pos=0
    for s in segments:
        start,end=max(anchor,s['start_s']),s['end_s']
        if end<=anchor:continue
        u=slopes[state_key(s['state'])]-slopes['resident_idle']
        while pos<len(queries) and queries[pos]<=end:
            result.append(advance(t,h,u,init['reference_c'],beta,tau,gamma,queries[pos]-start)[0]);pos+=1
        t,h=advance(t,h,u,init['reference_c'],beta,tau,gamma,end-start)
    if len(result)!=len(queries):raise ValueError('incomplete prediction')
    return result


def decompose(case,parameters,tau,gamma,existing):
    """Arithmetic path attribution at fixed coefficients, never another fit."""
    candidate,init=predict(case,parameters,tau,gamma)
    p=case['inputs'];beta=parameters['ap_cooling_rate_per_s'];slopes=parameters['ap_slope_at_30_c_per_s']
    anchor=dict(init,reference_c=p['reference_c'],h_last_c_per_s=0.)
    reference=dict(init,h_last_c_per_s=0.)
    anchored=_propagate(p['segments'],p['query_s'],slopes,beta,tau,0.,anchor)
    replaced=_propagate(p['segments'],p['query_s'],slopes,beta,tau,0.,reference)
    memory=_propagate(p['segments'],p['query_s'],slopes,beta,tau,0.,init)
    return [dict(anchor_change_c=a-old,reference_change_c=b-a,
                 preparation_state_change_c=h-b,work_memory_change_c=c-h,
                 total_change_c=c-old)
            for old,a,b,h,c in zip(existing,anchored,replaced,memory,candidate)]


def fit(development, parameters, tau_grid):
    """Only designated development targets enter estimation. Gamma is linear."""
    if development['id']!='idle_development':raise ValueError('development role required')
    y=np.array(development['observed_ap_c'],dtype=float)
    if not np.all(np.isfinite(y)):raise ValueError('missing target')
    profile=[]
    for tau in tau_grid:
        a,init=predict(development,parameters,tau,0.)
        b,_=predict(development,parameters,tau,1.)
        a=np.array(a);basis=np.array(b)-a;information=float(basis@basis)
        if information<1e-12:raise ValueError('unidentified workload gain')
        unconstrained=float(basis@(y-a)/information);gamma=max(0.,unconstrained)
        error=a+gamma*basis-y
        profile.append(dict(tau_s=tau,gamma=gamma,unconstrained_gamma=unconstrained,
            rmse_c=float(np.sqrt(np.mean(error**2))),gain_information=information,
            initial_condition=init['scaled_condition'],reference_c=init['reference_c']))
    if not profile:raise ValueError('empty parameter profile')
    best=min(profile,key=lambda r:(r['rmse_c'],r['tau_s']))
    return dict(best),profile


def preload_sensitivity(case, parameters, tau, gamma, half_step=.05):
    """Affine worst-case independent +/- perturbations; NOT a confidence band."""
    import copy
    baseline,_=predict(case,parameters,tau,gamma)
    amplification=np.zeros(len(baseline))
    for i in range(len(case['inputs']['preload'])):
        changed=copy.deepcopy(case);changed['inputs']['preload'][i]['ap']+=1.
        predicted,_=predict(changed,parameters,tau,gamma)
        amplification+=np.abs(np.array(predicted)-baseline)
    return dict(assumed_independent_preload_half_step_c=half_step,
        maximum_output_change_bound_c=float(max(amplification)*half_step),
        pointwise_change_bounds_c=(amplification*half_step).tolist(),
        meaning='deterministic rounding sensitivity, not measured uncertainty or confidence')
