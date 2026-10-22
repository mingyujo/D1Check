"""Visible-queue fixed-temperature fluid cost, not a physical schedule oracle.

Two task classes on two lanes give a rectangle cut by one balance line.
The linear objective's minimum occurs at its corners or balance intersections.
No future requests, sampled route work, actual remaining work or EDF H is used.
"""
import math
ROUTES=('CPU','GPU')

def vector_cost(v,task,route,T,physics,stage=0,progress=0.):
    v=list(v);v[stage]=max(0.,v[stage]-progress);v=[0. if i<stage else x for i,x in enumerate(v)]
    c=physics.c;f=physics.speed(T,route,1);A=physics.solo[('classification' if task=='C' else 'detection')+'_'+route]-physics.shared
    leak=math.exp(min(math.log(3.),max(-math.log(3.),c.strength*c.leakage_per_c*(T-c.reference_c))))
    non=sum(v)-v[1];duration=non+v[1]/f
    energy=A*(1-c.leakage_fraction+c.leakage_fraction*leak)*non+A*((1-c.leakage_fraction)*f*f+c.leakage_fraction*leak/f)*v[1]
    response=sum(v[:2 if task=='C' else 3])-v[1]+v[1]/f
    return dict(duration=duration,energy=energy,response=max(0.,response))

def optimum(groups,owners,rail_baseline):
    """Aggregate means per task; exact fluid minimum for those aggregate means."""
    n={t:groups[t]['n'] for t in ('C','D')};p={t:{r:groups[t][r]['duration'] for r in ROUTES} for t in ('C','D')};e={t:{r:groups[t][r]['energy'] for r in ROUTES} for t in ('C','D')}
    cpu=owners['CPU']+sum(n[t]*p[t]['CPU'] for t in n);gpu=owners['GPU'];target=cpu-gpu;a=p['C']['CPU']+p['C']['GPU'];b=p['D']['CPU']+p['D']['GPU']
    vertices=[(x,y) for x in (0.,n['C']) for y in (0.,n['D'])]
    for x in (0.,n['C']):
        y=(target-a*x)/b if b>0 else -1.
        if -1e-10<=y<=n['D']+1e-10:vertices.append((x,max(0.,min(n['D'],y))))
    for y in (0.,n['D']):
        x=(target-b*y)/a if a>0 else -1.
        if -1e-10<=x<=n['C']+1e-10:vertices.append((max(0.,min(n['C'],x)),y))
    def evaluate(xy):
        x,y=xy;g={'C':x,'D':y};lc=cpu-sum(g[t]*p[t]['CPU'] for t in n);lg=gpu+sum(g[t]*p[t]['GPU'] for t in n);finish=max(lc,lg)
        energy=sum(n[t]*e[t]['CPU']+g[t]*(e[t]['GPU']-e[t]['CPU']) for t in n)
        return dict(objective=energy+rail_baseline*finish,finish=finish,gpu_counts=g,lane_loads=dict(CPU=lc,GPU=lg))
    return min((evaluate(v) for v in vertices),key=lambda x:(math.floor(x['objective']*1e9+.5),math.floor(x['finish']*1e9+.5),x['gpu_counts']['C']))

class VisibleFluid:
    def __init__(self,state,vectors,physics):
        self.state,self.vectors,self.physics=state,vectors,physics;T=state['sensor']['temperature_c'];self.profiles={};self.groups={};self.owner_loads={r:0. for r in ROUTES}
        for q in state['queue']:
            self.profiles[q['request_id']]={r:vector_cost(vectors[q['request_id'],r],q['task'],r,T,physics) for r in ROUTES}
        for task in ('C','D'):
            local=[q for q in state['queue'] if q['task']==task];self.groups[task]=dict(n=len(local))
            for r in ROUTES:self.groups[task][r]={k:sum(self.profiles[q['request_id']][r][k] for q in local)/max(1,len(local)) for k in ('duration','energy','response')}
        for o in state['owners']:
            self.owner_loads[o['route']]=vector_cost(vectors[o['request_id'],o['route']],o['task'],o['route'],T,physics,o['stage'],o['public_progress_s'])['duration']
        self.rate=physics.c.baseline+physics.shared;self.base=optimum(self.groups,self.owner_loads,self.rate)
        self.feasible={q['request_id']:min(self.profiles[q['request_id']][r]['response']+self.owner_loads[r] for r in ROUTES)+state['now_ns']/1e9<=q['deadline_ns']/1e9 for q in state['queue']}
    def first(self,q,route):
        groups={t:{**g,**{r:dict(g[r]) for r in ROUTES}} for t,g in self.groups.items()};g=groups[q['task']];n=g['n'];g['n']-=1;v=self.profiles[q['request_id']]
        for r in ROUTES:
            for k in ('duration','energy','response'):g[r][k]=(g[r][k]*n-v[r][k])/max(1,n-1)
        loads=dict(self.owner_loads);loads[route]+=v[route]['duration'];after=optimum(groups,loads,self.rate)
        return dict(regret=after['objective']+v[route]['energy']-self.base['objective'],finish_increase=after['finish']-self.base['finish'])
