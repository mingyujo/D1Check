"""Saved-data necessary-condition LP with service-count and interval demand."""
import datetime,gzip,json,os
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
H=Path(__file__).resolve().parent;R=H.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
source=read(H/'ROUTE_BOUND_INPUT.json');old=read(R/'experiments/a24_stable_learning_v1/artifacts/G001/COMPARISON_SUMMARY.json');inputs=read(R/'experiments/a24_stable_learning_v1/INPUTS.json')['cases']
packet=json.loads(gzip.decompress((R/'experiments/multiresource_v1/PACKET.json.gz').read_bytes()));templates={p['id']:p for p in packet['templates']};evidence={p['route']:p for p in packet['multi']['evidence']};c=np.array(source['coef']);rows=[]
registration=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_environments=0,new_training=0,new_physical_fits=0,LP_cap=32,per_solve_time_cap_s=20,workload='Original R7 cases only; no new simulation. Preserve same potential route draws and physical models.',scope='Necessary interval demand plus class ontime counts; fractional route/on-time variables. Not a feasible schedule or a proof that a policy can achieve the bound. Does not become a runtime deadline mask.')
with (H/'SERVICE_BOUND_OPERATION.json').open('x',encoding='utf-8') as f:json.dump(registration,f,ensure_ascii=False,indent=2)
for case in source['rows']:
    inp=next(i for i in inputs if i['id']==case['input']);reqs={q['ordinal']:q for q in inp['requests']};options=[(q['ordinal'],o) for q in case['options'] for o in q['options']];n=inp['n'];nx=len(options);starts=sorted({q['offset_ns']/1e9 for q in inp['requests']})
    parent=next(r for r in old['rows'] if r['kind']=='EVAL' and r['input']==case['input'] and r['variant']=='REPAIR')
    tails=[(k,tau,c[j]) for k in range(5) for tau,j in [(.5,2+k),(1,7+k),(10,12+k),(60,17+k)] if c[j]>0];nv=2*nx+5+len(tails);u=2*nx
    eq=lil_matrix((n,nv))
    early=[]
    for j,(ordinal,o) in enumerate(options):
        eq[ordinal,j]=1;q=reqs[ordinal];p=templates[o['template']];v=p['offset_s'];post=v['lane_available_ns']-v['output_ready_ns'];adm=v['host_inference_start_ns']-v['execution_start_ns'];rb=0 if q['priority']=='urgent' else v['readback_end_ns']-v['output_ready_ns'];a=q['offset_ns']/1e9
        early.append(dict(a=a,d=a+q['deadline_ms']/1000,slot=o['slot'],owner=o['occupied']-post+rb,cpu=min(adm,evidence[o['route']]['admission_service_reference_s'])+(o['infer'] if o['slot']=='CPU' else 0)+min(rb,evidence[o['route']]['post_service_reference_s']),priority=q['priority']))
    for K in [1,3]:
        for target in ['OLD_RL_CLASS_COUNTS','ALL_ON_TIME']:
            cons=[];rhs=[]
            def add(d,b):cons.append(d);rhs.append(b)
            for channel,factor in [(0,lambda o:o['cpu_work']/K),(0,lambda o:o['cpu_wall']/3),(0,lambda o:o['infer'] if o['slot']=='CPU' else 0),(1,lambda o:o['infer'] if o['route']=='detection_CPU' else 0),(2,lambda o:o['infer'] if o['slot']=='GPU' else 0),(3,lambda o:o['infer'] if o['slot']=='NPU' else 0)]:
                d={j:factor(o) for j,(_,o) in enumerate(options)};d[u+channel]=-1;add(d,0)
            for slot in ['CPU','GPU','NPU']:
                d={j:o['occupied'] if o['slot']==slot else 0 for j,(_,o) in enumerate(options)};d[u+4]=-1;add(d,0)
            for k in range(4):add({u+k:1,u+4:-1},0)
            objective=np.zeros(nv)
            for j,(k,tau,w) in enumerate(tails):objective[u+5+j]=w;add({u+k:1,u+5+j:-1},tau)
            for j in range(nx):add({nx+j:1,j:-1},0) # timely route fraction <= total route fraction
            for priority in ['urgent','normal']:
                planned=sum(q['priority']==priority for q in inp['requests']);needed=planned if target=='ALL_ON_TIME' else parent['service'][priority]['on_time']
                add({nx+j:-1 for j,e in enumerate(early) if e['priority']==priority},-needed)
            interval_count=0
            for begin,a in enumerate(starts):
                for length in [1,4,16,64]:
                    end=min(len(starts)-1,begin+length-1)
                    if end-begin+1!=length and end!=len(starts)-1:continue
                    for tail in [.8,2.]:
                        b=starts[end]+tail;ix=[j for j,e in enumerate(early) if e['a']>=a-1e-9 and e['d']<=b+1e-9]
                        if not ix:continue
                        add({nx+j:early[j]['cpu'] for j in ix},K*(b-a));interval_count+=1
                        for slot in ['CPU','GPU','NPU']:add({nx+j:early[j]['owner'] for j in ix if early[j]['slot']==slot},b-a)
            ub=lil_matrix((len(cons),nv))
            for i,d in enumerate(cons):
                for j,v in d.items():
                    if v:ub[i,j]=v
            solved=linprog(objective,A_ub=ub.tocsr(),b_ub=rhs,A_eq=eq.tocsr(),b_eq=np.ones(n),bounds=[(0,1)]*(2*nx)+[(0,case['T']-35)]*5+[(0,None)]*len(tails),method='highs',options={'time_limit':20})
            row=dict(input=case['input'],load=case['load'],mix=case['mix'],cpu_workers=K,target=target,solver_status=int(solved.status),solver_message=solved.message,necessary_interval_families=interval_count,constraint_rows=len(cons),EDF_API_J=case['EDF_J'],lower_API_J=None,upper_saving_vs_EDF_percent=None)
            if solved.success:
                lower=case['baseline']+solved.fun
                assert target!='OLD_RL_CLASS_COUNTS' or lower<=case['old_RL_J']+1e-4,'Necessary bound exceeds observed feasible old RL; investigate constraints'
                row.update(lower_API_J=lower,upper_saving_vs_EDF_percent=100*(1-lower/case['EDF_J']),max_eq_residual=float(np.max(abs(eq@solved.x-1))),max_ub_residual=float(np.max(ub@solved.x-np.array(rhs))),fractional_route_counts={route:sum(solved.x[j] for j,(_,o) in enumerate(options) if o['route']==route) for route in ['classification_CPU','classification_GPU','classification_NPU','detection_CPU']})
            rows.append(row);print(json.dumps({k:row[k] for k in ['input','cpu_workers','target','solver_status','upper_saving_vs_EDF_percent']}),flush=True)
groups=[]
for K in [1,3]:
    for load in [.4,.65,.85,1.05]:
        for target in ['OLD_RL_CLASS_COUNTS','ALL_ON_TIME']:
            rr=[r for r in rows if r['cpu_workers']==K and r['load']==load and r['target']==target];ok=all(r['lower_API_J'] is not None for r in rr)
            groups.append(dict(cpu_workers=K,load=load,target=target,optimal_rows=sum(r['solver_status']==0 for r in rr),necessary_infeasible_rows=sum(r['solver_status']==2 for r in rr),rows=len(rr),lower_mean_API_J=float(np.mean([r['lower_API_J'] for r in rr])) if ok else None,upper_saving_vs_EDF_percent=100*(1-sum(r['lower_API_J'] for r in rr)/sum(r['EDF_API_J'] for r in rr)) if ok else None))
out=dict(status='SAVED_SERVICE_CONSTRAINED_NECESSARY_ROUTE_LP_COMPLETE',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),solves=len(rows),groups=groups,rows=rows,new_environments=0,new_training=0,new_physical_fits=0,physical_validation=False,scope=registration['scope'])
with (H/'ROUTE_SERVICE_BOUND_RESULT.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print('SERVICE_ROUTE_BOUND_COMPLETE',len(rows),flush=True)
