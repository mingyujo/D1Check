"""Offline nonpreemptive mixed-integer reference, replayed in the real PC engine.

Knows all arrivals and fixed service scenario. Planning rounds lane occupancy up
to a registered time grid; replay uses original five phases. No online-policy,
physical optimum, thermal safety, or independent device validation claim.
"""
import math
import time
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, csr_matrix, eye, hstack, vstack
from tools import d1_industrial_scheduling as x


def plan(frozen,initial,tickets,scenario='mean',grid_s=.02,timeout_s=60.,ap_cap_c=None):
    if grid_s<=0 or timeout_s<=0:raise ValueError('positive bounded planning settings required')
    fc=x.p.Controller(frozen,initial,x.p.profile(frozen,scenario),'EFT_REFERENCE')
    profile=fc.estimates; t0=35.;choices=[];by_id={q['id']:i for i,q in enumerate(tickets)}
    for q in tickets:
        for b in x.p.backends(q):
            phases=profile[x.p.key(q,b)];hold=sum(phases)/1e9
            response=sum(phases[:2 if q['priority']=='urgent' else 3])/1e9
            first=math.ceil((q['arrival_ns']/1e9-t0)/grid_s-1e-8)
            last=math.floor(((q['arrival_ns']+q['deadline_offset_ns'])/1e9-t0-response)/grid_s+1e-8)
            length=math.ceil(hold/grid_s-1e-8)
            for k in range(max(0,first),last+1):
                if t0+(k+length)*grid_s<=120+1e-9:
                    choices.append(dict(q=q,backend=b,k=k,length=length,hold=hold,response=response))
    covered={c['q']['id'] for c in choices}
    if covered!=set(by_id):return dict(status='no_admissible_start',jobs=None,grid_s=grid_s)
    n=len(choices);bins=max(c['k']+c['length'] for c in choices);v=n+bins
    # Occupancy per grid interval for each task/backend and the request denominator.
    matrices={}
    for label in ('classification_CPU','classification_GPU','detection_CPU'):
        rr=[];cc=[]
        for j,c in enumerate(choices):
            if c['q']['task']+'_'+c['backend']==label:
                rr.extend(range(c['k'],c['k']+c['length']));cc.extend([j]*c['length'])
        matrices[label]=coo_matrix((np.ones(len(rr)),(rr,cc)),shape=(bins,n)).tocsr()
    C,G,D=(matrices[label] for label in ('classification_CPU','classification_GPU','detection_CPU'))
    Z=csr_matrix((bins,bins));I=eye(bins,format='csr')
    req=coo_matrix((np.ones(n),([by_id[c['q']['id']] for c in choices],range(n))),shape=(len(tickets),n)).tocsr()
    pieces=[hstack([req,csr_matrix((len(tickets),bins))]),hstack([C+D,Z]),hstack([G,Z]),hstack([C+G,Z]),
        hstack([-G,I]),hstack([-D,I]),hstack([G+D,-I])]
    lb=[np.ones(len(tickets)),np.full(bins,-np.inf),np.full(bins,-np.inf),np.full(bins,-np.inf),
        np.full(bins,-np.inf),np.full(bins,-np.inf),np.full(bins,-np.inf)]
    ub=[np.ones(len(tickets)),np.ones(bins),np.ones(bins),np.ones(bins),np.zeros(bins),np.zeros(bins),np.ones(bins)]
    slopes=frozen['ap']['parameters']['ap_slope_at_30_c_per_s'];idle=slopes['resident_idle']
    uC,uG,uD=(slopes[k]-idle for k in ('classification_CPU','classification_GPU','detection_CPU'))
    uPair=slopes['classification_GPU+detection_CPU']-idle-uG-uD
    query=np.arange(35.,181.)
    kernel=np.zeros((len(query),bins));base=[]
    for i,qtime in enumerate(query):
        base.append(x.p.thermal_step(fc.init['anchor_ap_c'],fc.init['h_last_c_per_s'],0.,fc.init['reference_c'],
            frozen['ap'],qtime-fc.init['anchor_s'])[0])
        for k in range(min(bins,math.ceil((qtime-t0)/grid_s-1e-9))):
            start=t0+k*grid_s;dt=min(grid_s,qtime-start)
            if dt<=0:continue
            a,h=x.p.thermal_step(0.,0.,1.,0.,frozen['ap'],dt)
            kernel[i,k]=x.p.thermal_step(a,h,0.,0.,frozen['ap'],max(0.,qtime-start-dt))[0]
    base=np.array(base)
    thermal=hstack([csr_matrix(kernel@(uC*C+uG*G+uD*D)),csr_matrix(kernel*uPair)])
    if ap_cap_c is not None:
        if not math.isfinite(ap_cap_c):raise ValueError('finite model peak comparison required')
        pieces.append(thermal);lb.append(np.full(len(query),-np.inf));ub.append(ap_cap_c-base)
    watts=frozen['energy_increment_w']
    wPair=watts['classification_GPU+detection_CPU']-watts['classification_GPU']-watts['detection_CPU']
    obj=np.r_[grid_s*np.asarray((watts['classification_CPU']*C+watts['classification_GPU']*G+
        watts['detection_CPU']*D).sum(axis=0)).ravel(),np.full(bins,grid_s*wPair)]
    began=time.monotonic()
    fit=milp(obj,integrality=np.r_[np.ones(n),np.zeros(bins)],bounds=Bounds(np.zeros(v),np.ones(v)),
        constraints=LinearConstraint(vstack(pieces,format='csr'),np.concatenate(lb),np.concatenate(ub)),
        options=dict(time_limit=timeout_s,mip_rel_gap=1e-5))
    meta=dict(status_code=int(fit.status),message=fit.message,elapsed_s=time.monotonic()-began,
        grid_s=grid_s,binaries=n,overlap_variables=bins,rows=sum(a.shape[0] for a in pieces),
        planning_ap_cap_c=ap_cap_c,solver_dual_bound_incremental_j=getattr(fit,'mip_dual_bound',None),
        solver_gap=getattr(fit,'mip_gap',None),grid_optimality_only=fit.status==0,
        original_continuous_optimality_proved=False,information='all future arrivals and fixed scenario service')
    if fit.x is None:return dict(meta,status='no_incumbent',jobs=None)
    values=np.asarray(fit.x);constraint=vstack(pieces,format='csr')@values
    lower=np.concatenate(lb);upper=np.concatenate(ub)
    if (np.max(np.maximum(0.,lower-constraint))>1e-5 or np.max(np.maximum(0.,constraint-upper))>1e-5 or
            np.max(np.abs(values[:n]-np.round(values[:n])))>1e-5):
        return dict(meta,status='invalid_incumbent',jobs=None)
    chosen=[c for c,value in zip(choices,values[:n]) if value>.5]
    jobs=[]
    for c in chosen:
        q=c['q'];start=t0+c['k']*grid_s
        jobs.append(dict(id=q['id'],state=q['task']+'_'+c['backend'],backend=c['backend'],start=start,
            end=start+c['hold'],response=start+c['response'],
            deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9,already_responded=False))
    x.validate_schedule(jobs,tickets,profile)
    # Only replay can establish the metric in the unchanged, unrounded plant.
    row,rr,_,ss,cost=x.simulate(frozen,initial,tickets,scenario,x.REPLAY,jobs)
    if row['deadline_met']!=len(tickets) or row['completed']!=len(tickets):raise ValueError('solver calendar replay service failed')
    replay_deviation=max(abs(r['dispatch_ns']/1e9-next(j['start'] for j in jobs if j['id']==r['id'])) for r in rr['ledger'])
    if replay_deviation>5e-9:raise ValueError('solver calendar replay start drift')
    return dict(meta,status='replayed_incumbent',jobs=jobs,metrics=row,
        rounded_planning_incremental_j=float(fit.fun),
        rounded_planning_peak_ap_c=float(max(base+thermal@values)),
        actual_replay_within_model_ap_cap=ap_cap_c is None or row['peak_ap_c']<=ap_cap_c+1e-8,
        ledger=rr['ledger'],segments=ss,predicted_ap_path=cost['ap_path'])
