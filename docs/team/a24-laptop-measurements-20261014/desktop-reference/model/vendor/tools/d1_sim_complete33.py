"""Explicit active deadlines and separate legacy metrics; no new physical fit."""
import copy,math,types
from tools import d1_exploration31 as explore
from tools import d1_sched_dynamics_policy as policy
base=explore.base
VERSION='dual-device-deadline-contract-v33'
RULES=(*policy.RULES,'ENERGY_EDD','THERMAL_EDD')
def validate(q):
    if set(q)not in(base.old.REQUEST_FIELDS,base.PUBLIC_FIELDS):raise ValueError('public fields only')
    if not isinstance(q['id'],str)or not q['id']or q['priority']not in('urgent','normal'):raise ValueError('request ID/priority')
    if any(type(q[k])is not int for k in('ordinal','arrival_ns','deadline_offset_ns'))or not 0<=q['arrival_ns']<base.HORIZON_NS or q['ordinal']<0:raise ValueError('public integer times')
    if not 0<q['deadline_offset_ns']<=base.HORIZON_NS:raise ValueError('registered relative-deadline bound120s')
    if type(q.get('work_units',1))is not int or not 1<=q.get('work_units',1)<=3:raise ValueError('work units')
    base.routes(q)
class ContractMixin:
    def dispatch(self,jobs):
        scope=dict(base.Device.dispatch.__globals__);scope['validate_request']=validate
        fn=types.FunctionType(base.Device.dispatch.__code__,scope,'contract33_dispatch',base.Device.dispatch.__defaults__)
        return fn(self,jobs)
class ExploreDevice(ContractMixin,explore.Device):pass
class A24Device(ContractMixin,explore.measured.prior.A24Device):pass
class S26Device(ContractMixin,explore.measured.Device):pass
def active_metrics(ledger,previous,end_ns):
    out=copy.deepcopy(previous)
    for key in('urgent_failure','normal_failure','weighted_declared_misses','weighted_tardiness_s','service_cost'):out['legacy_'+key]=previous[key]
    pairs=[]
    for pr in('urgent','normal'):
        qs=[q for q in ledger if q['priority']==pr];on_time=overdue=pending=0;late=[]
        for q in qs:
            r=q.get('response_ns');deadline=q['arrival_ns']+q['deadline_offset_ns']
            if r is not None:
                if r<=q['deadline_offset_ns']:on_time+=1
                else:overdue+=1
                late.append(max(r-q['deadline_offset_ns'],0)/1e9)
            elif deadline<=end_ns:overdue+=1;late.append(max(end_ns-deadline,0)/1e9)
            else:pending+=1;late.append(0.)
        out.update({pr+'_failure':overdue,pr+'_declared_failure':overdue,pr+'_on_time':on_time,pr+'_pending_not_due':pending,
            pr+'_success_pct':100*on_time/len(qs)if qs else None,pr+'_failure_pct':100*overdue/len(qs)if qs else None,
            pr+'_tardiness_mean_s':sum(late)/len(qs)if qs else None})
        pairs.extend(late)
    out['active_deadline_success_pct']=100*(out['urgent_on_time']+out['normal_on_time'])/len(ledger)
    out['active_deadline_failure_pct']=100*(out['urgent_failure']+out['normal_failure'])/len(ledger)
    out['pending_not_due']=out['urgent_pending_not_due']+out['normal_pending_not_due']
    out['active_tardiness_mean_s']=sum(pairs)/len(ledger)
    out['weighted_declared_misses']=2*out['urgent_failure']+out['normal_failure']
    out['weighted_tardiness_s']=sum((2 if q['priority']=='urgent'else 1)*max(q.get('response_ns',end_ns-q['arrival_ns'])-q['deadline_offset_ns'],0)/1e9 for q in ledger)
    out['service_cost']=None # no scalar tradeoff weights adopted in v33
    return out
def simulate(profile,requests,controller,**kwargs):
    for q in requests:validate(q)
    scope=dict(base.simulate.__globals__);scope['validate_request']=validate
    scope['Device']=ExploreDevice if 'exploration31'in profile else A24Device if profile['device']=='A24'else S26Device
    fn=types.FunctionType(base.simulate.__code__,scope,'contract33_loop',base.simulate.__defaults__);r=fn(profile,requests,controller,**kwargs)
    r['metrics']=active_metrics(r['ledger'],r['metrics'],r['end_ns'])
    r.update(schema=VERSION,deadline_contract='arrival + request deadline; legacy1.5/6 metrics explicit only',physical_evidence='exploratory'if'exploration31'in profile else'measurement-based development, not new hardware validation',PPO_role='old fixed ABI with legacy-cap features; transfer diagnostic only')
    return r
def local_cost(dev,q,b,ds):
    """One action proxy from public current estimates; never a queue rollout."""
    profile=dev.profile;pub=dev.public();execute=ds[1]/1e9;other=(sum(ds)-ds[1])/1e9
    if 'exploration31'in profile:
        cfg=profile['exploration31'];w=cfg['route_w'][q['task']+'|'+b];active=pub.get('activation_memory',{}).get(b,0.)
        startup=cfg['startup_j'][b]*(1-active);cross=cfg['parallel_w']if any(v for lane,v in pub['lanes'].items()if lane!=b)else 0.
        energy=(cfg['baseline_w']+w+cross)*execute+(cfg['baseline_w']+.15*w)*other+startup
        return energy,w+cross
    if profile['device']=='A24':
        w=profile['cost_anchor']['energy_increment_w'][q['task']+'_'+b];baseline=pub['power_w']
    else:
        c=profile['refine26_anchor']['model']['power']['coefficients'];i={('classification','CPU'):4,('detection','CPU'):5,('classification','GPU'):6,('classification','NPU'):7}[q['task'],b]
        w=c[i]/(1+4*pub.get('recent_activity',{}).get(b,0.))+c[10];baseline=pub['power_w']
    return max(0,baseline)*sum(ds)/1e9+w*execute,w
class CostController:
    def __init__(self,kind):
        if kind not in('ENERGY_EDD','THERMAL_EDD'):raise ValueError('cost rule')
        self.kind=kind;self.errors=[];self.decisions=[]
    def choose(self,dev,waiting):
        bank=policy.build(dev,waiting);legal=[i for i in range(len(bank['actions']))if bank['mask'][i]];execs=[i for i in legal if bank['actions'][i]]
        if not execs:i=legal[0];jobs=[]
        else:
            # Same EDD request, then choose economical immediately on-time path.
            best=min(execs,key=lambda i:(bank['ranks']['EDD'][bank['actions'][i][0][0]['id']],i));q=bank['actions'][best][0][0]
            paths=[i for i in execs if bank['actions'][i][0][0]['id']==q['id']]
            on_time=[i for i in paths if dev.now+policy.response(bank['paths'][q['id'],bank['actions'][i][0][1]],q)<=q['arrival_ns']+q['deadline_offset_ns']]
            if on_time:
                def key(i):
                    b=bank['actions'][i][0][1];ds=bank['paths'][q['id'],b];energy,power=local_cost(dev,q,b,ds)
                    return (energy,power,i)if self.kind=='ENERGY_EDD'else(power,energy,i)
                i=min(on_time,key=key)
            else:i=min(paths,key=lambda i:(policy.response(bank['paths'][q['id'],bank['actions'][i][0][1]],q),i))
            jobs=bank['actions'][i]
        self.decisions.append(dict(now_ns=dev.now,policy=self.kind,legal=len(legal),chosen=[(q['id'],b)for q,b in jobs],**bank['diagnostics']))
        return jobs or None
