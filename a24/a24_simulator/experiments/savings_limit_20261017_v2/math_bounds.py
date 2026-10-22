"""Optimistic lower bounds; no alteration of the coupled-345 physics.

At k<=2 owners, H dt >= sum_owners H/2 dt. For execution work dw=f dt,
allocated energy/dw >= A(1-l)f^2 + (A*l*leak + H/2)/f, A=p_solo-H.
Non-execution work advances at 1. Temperature is >= idle/reference26C.
Independent per-job minima ignore thermal reachability and lane conflicts,
so they are LOWER bounds, never achievable schedule claims.
"""
import hashlib
import json
import math
import warnings
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_array

ROUTES=('CPU','GPU')
EPS_COEFFICIENT=1e-9
SOLVER_MARGIN=1e-5


def coefficients(physics,initial_temperature,step=.01):
    c=physics.c;H=physics.shared
    if c.reference_c!=c.idle_c or c.strength!=1 or c.idle_c!=26:
        raise ValueError('This proof is registered for the frozen strength1/26C reference model')
    cpu=max(v for k,v in physics.solo.items() if k.endswith('_CPU'))
    gpu=max(v for k,v in physics.solo.items() if k.endswith('_GPU'))
    pmax=H+(cpu+gpu-2*H)*(1-c.leakage_fraction+3*c.leakage_fraction)
    tmax=max(initial_temperature,c.idle_c+c.thermal_resistance*pmax)
    cells={}
    for cell,p in physics.solo.items():
        A=p-H;B=A*c.leakage_fraction+H/2
        fstar=max(c.minimum_speed,min(1.,(B/(2*A*(1-c.leakage_fraction)))**(1/3)))
        free=A*(1-c.leakage_fraction)*fstar*fstar+B/fstar
        # On each interval, f decreases and leakage increases. Taking the
        # separate favorable endpoints gives a conservative interval bound.
        route=cell.rsplit('_',1)[1];intervals=[];lo=c.idle_c
        while lo<tmax:
            hi=min(tmax,lo+step)
            fmin=physics.speed(hi,route,1);fmax=physics.speed(lo,route,1)
            leakmin=math.exp(min(math.log(3.),max(-math.log(3.),c.leakage_per_c*(lo-c.reference_c))))
            lb=A*(1-c.leakage_fraction)*fmin*fmin+(A*c.leakage_fraction*leakmin+H/2)/fmax
            intervals.append(lb);lo=hi
        thermal=max(free,min(intervals))
        cells[cell]=dict(nonexecution=max(0.,A+H/2-EPS_COEFFICIENT),
            execution_free=max(0.,free-EPS_COEFFICIENT),execution=max(0.,thermal-EPS_COEFFICIENT),
            relaxed_optimal_speed=fstar,interval_count=len(intervals))
    return dict(cells=cells,temperature_upper=tmax,increment_power_upper=pmax,shared=H,
        temperature_grid_step=step,coefficient_margin=EPS_COEFFICIENT)


def work_energy(job,route,coeff,prefix=False,free=False):
    v=[x/1e9 for x in job['routes'][route]['stages_ns']]
    if prefix:v=v[:2 if job['task']=='C' else 3]
    cell=('classification' if job['task']=='C' else 'detection')+'_'+route
    z=coeff['cells'][cell];e=z['execution_free' if free else 'execution']
    return sum(t*(e if stage==1 else z['nonexecution']) for stage,t in enumerate(v))


def passive_mean(case,physics):
    c=physics.c;dur=case['service_stop_s']-35
    return c.idle_c+(case['temperature_c']-c.idle_c)*c.thermal_tau_s*(-math.expm1(-dur/c.thermal_tau_s))/dur


def relaxation(jobs,case,reference,physics,coeff):
    """A superset of every complete physical schedule with EDF count SLA.

    x[j,r] assigns a lane, z[j,r] claims that route's response is on time.
    Interval demand uses only unthrottled prefix work and omits suffix blocking,
    hence is necessary but deliberately NOT sufficient for a real schedule.
    """
    n=len(jobs);width=4*n;rr=[];cc=[];dd=[];lower=[];upper=[];tags=[]
    def add(items,lo=-np.inf,hi=np.inf,tag='structural'):
        row=len(lower)
        for col,value in items:
            if value:rr.append(row);cc.append(col);dd.append(value)
        lower.append(lo);upper.append(hi);tags.append(tag)
    for j in range(n):
        add([(2*j,1.),(2*j+1,1.)],1.,1.)
        for r in range(2):add([(2*n+2*j+r,1.),(2*j+r,-1.)],hi=0.)
    add([(2*n+2*j+r,1.) for j in range(n) for r in range(2)],lo=reference['on_time'],tag='count_SLA')
    add([(2*n+2*j+r,1.) for j,q in enumerate(jobs) if q['priority']=='U' for r in range(2)],lo=reference['urgent_on_time'],tag='count_SLA')
    release=np.array([q['queue_entry_ns']/1e9 for q in jobs]);due=np.array([q['deadline_ns']/1e9 for q in jobs])
    total=np.array([[sum(q['routes'][r]['stages_ns'])/1e9 for r in ROUTES] for q in jobs])
    prefix=np.array([[sum(q['routes'][r]['stages_ns'][:2 if q['task']=='C' else 3])/1e9 for r in ROUTES] for q in jobs])
    starts=sorted(set([35.,*release.tolist()]));ends=sorted(set(due.tolist()))
    for a in starts:
        for r in range(2):
            add([(2*j+r,total[j,r]) for j in range(n) if release[j]>=a-1e-10],hi=case['drain_stop_s']-a)
        for b in ends:
            if b<=a or b>case['drain_stop_s']:continue
            eligible=[j for j in range(n) if release[j]>=a-1e-10 and due[j]<=b+1e-10]
            if not eligible:continue
            for r in range(2):add([(2*n+2*j+r,prefix[j,r]) for j in eligible],hi=b-a)
    ub=np.ones(width)
    for j in range(n):
        for r in range(2):
            if release[j]+total[j,r]>case['drain_stop_s']+1e-10:ub[2*j+r]=0.
            if release[j]+prefix[j,r]>due[j]+1e-10:ub[2*n+2*j+r]=0.
    A=coo_array((np.array(dd),(np.array(rr),np.array(cc))),shape=(len(lower),width)).tocsc()
    energy=np.zeros(width);heat=np.zeros(width);dur=case['service_stop_s']-35;c=physics.c
    for j,q in enumerate(jobs):
        # RC area kernel decreases with the time of energy deposition. All
        # response-prefix energy of an on-time job is paid no later than due.
        kernel=c.thermal_resistance*(-math.expm1(-max(0.,case['service_stop_s']-due[j])/c.thermal_tau_s))/dur
        for r,route in enumerate(ROUTES):
            energy[2*j+r]=work_energy(q,route,coeff)
            heat[2*n+2*j+r]=kernel*work_energy(q,route,coeff,prefix=True)
    fingerprint=hashlib.sha256(json.dumps(dict(rows=rr,cols=cc,values=dd,
        lower=[None if not math.isfinite(x) else x for x in lower],
        upper=[None if not math.isfinite(x) else x for x in upper],variable_upper=ub.tolist()),sort_keys=True).encode()).hexdigest()
    return dict(A=A,lower=np.array(lower),upper=np.array(upper),bounds=ub,tags=tags,
        energy=energy,heat=heat,fingerprint=fingerprint,rows=len(lower),variables=width)


def observed_vector(jobs,requests,drain):
    q={r['request_id']:r for r in requests};n=len(jobs);v=np.zeros(4*n)
    for j,job in enumerate(jobs):
        actual=q[job['request_id']];r=ROUTES.index(actual['route']);v[2*j+r]=1
        if actual['response_ns'] is not None and actual['response_ns']<=min(actual['deadline_ns'],round(drain*1e9)):
            v[2*n+2*j+r]=1
    return v


def feasibility(problem,v,include_counts=True):
    value=problem['A']@v
    selected=np.array([include_counts or t!='count_SLA' for t in problem['tags']])
    errors=np.concatenate((np.maximum(0.,problem['lower'][selected]-value[selected]),
        np.maximum(0.,value[selected]-problem['upper'][selected]),np.maximum(0.,v-problem['bounds']),np.maximum(0.,-v)))
    return float(np.max(errors))


def solve(problem,kind,time_limit=10):
    objective=problem[kind]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        answer=milp(objective,integrality=np.ones(len(objective)),bounds=Bounds(0.,problem['bounds']),
            constraints=LinearConstraint(problem['A'],problem['lower'],problem['upper']),
            options=dict(time_limit=time_limit,node_limit=100000,mip_rel_gap=1e-9,presolve=True,threads=1))
    if answer.status in (2,3,4):raise RuntimeError('Invalid relaxation solve: '+str(answer.message))
    def finite(x):return float(x) if x is not None and math.isfinite(float(x)) else None
    dual=finite(getattr(answer,'mip_dual_bound',None));primal=finite(answer.fun)
    return dict(status=int(answer.status),message=str(answer.message),primal=primal,
        reported_dual_bound=dual,conservative_lower_bound=max(0.,(dual or 0.)-SOLVER_MARGIN),
        MIP_gap=finite(getattr(answer,'mip_gap',None)),nodes=finite(getattr(answer,'mip_node_count',None)),
        seconds_cap=time_limit,numerical_margin=SOLVER_MARGIN,warnings=[str(w.message) for w in caught],
        threads_option='1 explicitly forwarded by SciPy to HiGHS')
