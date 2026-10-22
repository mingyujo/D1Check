"""Sparse LP lower bound with route choice and explicit work/capacity coupling."""
import datetime,json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
H=Path(__file__).resolve().parent
source=json.loads((H/'ROUTE_BOUND_INPUT.json').read_text())
c=np.array(source['coef']);rows=[]
for case in source['rows']:
    options=[(q['ordinal'],o) for q in case['options'] for o in q['options']]
    n=len(case['options']);nx=len(options);tails=[(k,tau,c[j]) for k in range(5) for tau,j in [(.5,2+k),(1,7+k),(10,12+k),(60,17+k)] if c[j]>0]
    nv=nx+5+len(tails)
    eq=lil_matrix((n,nv));
    for j,(ordinal,o) in enumerate(options):eq[ordinal,j]=1
    for K in [1,3]:
        constraints=[];rhs=[]
        def constraint(d,b):constraints.append(d);rhs.append(b)
        # Every CPU grant consumes work; K changes parallel capacity, never work.
        for channel,factor in [(0,lambda o:o['cpu_work']/K),(0,lambda o:o['cpu_wall']/3),(0,lambda o:o['infer'] if o['slot']=='CPU' else 0),(1,lambda o:o['infer'] if o['route']=='detection_CPU' else 0),(2,lambda o:o['infer'] if o['slot']=='GPU' else 0),(3,lambda o:o['infer'] if o['slot']=='NPU' else 0)]:
            d={j:factor(o) for j,(_,o) in enumerate(options)};d[nx+channel]=-1;constraint(d,0)
        for slot in ['CPU','GPU','NPU']:
            d={j:o['occupied'] if o['slot']==slot else 0 for j,(_,o) in enumerate(options)};d[nx+4]=-1;constraint(d,0)
        for k in range(4):constraint({nx+k:1,nx+4:-1},0)
        objective=np.zeros(nv)
        for a,(k,tau,weight) in enumerate(tails):
            objective[nx+5+a]=weight;constraint({nx+k:1,nx+5+a:-1},tau)
        ub=lil_matrix((len(constraints),nv))
        for i,d in enumerate(constraints):
            for j,v in d.items():
                if v:ub[i,j]=v
        result=linprog(objective,A_ub=ub.tocsr(),b_ub=rhs,A_eq=eq.tocsr(),b_eq=np.ones(n),bounds=[(0,1)]*nx+[(0,case['T']-35)]*5+[(0,None)]*len(tails),method='highs')
        assert result.success,result.message
        lower=case['baseline']+result.fun
        counts={route:sum(result.x[j] for j,(_,o) in enumerate(options) if o['route']==route) for route in ['classification_CPU','classification_GPU','classification_NPU','detection_CPU']}
        rows.append(dict(input=case['input'],load=case['load'],mix=case['mix'],cpu_workers=K,lower_API_J=lower,EDF_API_J=case['EDF_J'],old_RL_API_J=case['old_RL_J'],upper_saving_vs_EDF_percent=100*(1-lower/case['EDF_J']),upper_saving_vs_RL_percent=100*(1-lower/case['old_RL_J']),fractional_route_counts=counts,channel_duration_lower_s=result.x[nx:nx+5].tolist(),max_eq_residual=float(np.max(np.abs(eq@result.x-1))),max_ub_residual=float(np.max(ub@result.x-np.array(rhs))),solver=result.message))
groups=[]
for K in [1,3]:
    for load in [.4,.65,.85,1.05]:
        rr=[r for r in rows if r['cpu_workers']==K and r['load']==load]
        groups.append(dict(cpu_workers=K,load=load,EDF_API_J=np.mean([r['EDF_API_J'] for r in rr]),lower_API_J=np.mean([r['lower_API_J'] for r in rr]),optimistic_upper_saving_vs_EDF_percent=100*(1-sum(r['lower_API_J'] for r in rr)/sum(r['EDF_API_J'] for r in rr))))
output=dict(status='CONDITIONAL_ROUTE_CHOICE_LP_COMPLETE',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=rows,grouped=groups,scope=source['scope'],gate_5percent_at85=any(g['load']==.85 and g['optimistic_upper_saving_vs_EDF_percent']>=5 for g in groups),new_policy_environments=0,new_fits=0,physical_validation=False)
with (H/'ROUTE_BOUND_RESULT.json').open('x',encoding='utf-8') as f:json.dump(output,f,ensure_ascii=False,indent=2)
print(json.dumps({k:output[k] for k in ['status','grouped','gate_5percent_at85']},indent=2))
