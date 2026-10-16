"""One prespecified AP family. Only designated development sessions may be fitted."""
import copy
import math
import numpy as np
from tools import d1_ap_preparation_memory as memory
from tools import d1_ap_model_completion as common
from tools.d1_arrival_recorded_replay_analysis import state_key


def basis(case, parameters, beta):
    x=case['inputs'];pre=x['preload'];q=x['query_s'];segments=x['segments']
    if not pre or not q or not math.isfinite(beta) or beta<=0:
        raise ValueError('missing inputs or invalid beta')
    if any(p['hi']>=35 or not p['lo']<=p['t']<=p['hi'] for p in pre) or q[0]<35 or \
            any(not math.isfinite(t) for t in q) or any(not 0<b-a<=10 for a,b in zip(q,q[1:])):
        raise ValueError('future AP, unordered or gapped query')
    cursor=0.;slopes=parameters['ap_slope_at_30_c_per_s']
    for s in segments:
        if not math.isfinite(s['end_s']) or abs(s['start_s']-cursor)>1e-6 or s['end_s']<cursor:
            raise ValueError('schedule gap')
        if state_key(s['state']) not in slopes:raise ValueError('unsupported state')
        if s['state']!='idle' and s['start_s']<35:raise ValueError('work before cutoff')
        cursor=s['end_s']
    if q[-1]>cursor:raise ValueError('incomplete schedule')
    init=memory.initialize(pre,beta,30.)
    if not 0<=init['anchor_s']<35:raise ValueError('initial anchor')
    zero={k:slopes['resident_idle'] for k in slopes}
    a=np.array(memory._propagate(segments,q,zero,beta,30.,0.,init))
    b=np.array(memory._propagate(segments,q,slopes,beta,30.,0.,init))
    c=np.array(memory._propagate(segments,q,slopes,beta,30.,1.,init))
    # H'= -H/30 + g*u/30. Existing gamma=1 produces this delayed column.
    return a,np.column_stack((b-a,c-b)),init


def predict(case, frozen):
    beta,k,g=(float(frozen[n]) for n in ('beta','k','g'))
    if not all(math.isfinite(v) for v in (beta,k,g)) or min(k,g)<0:
        raise ValueError('invalid frozen coefficient')
    a,x,init=basis(case,frozen['parameters'],beta)
    y=a+x@np.array([k,g])
    if not np.all(np.isfinite(y)):raise ValueError('nonfinite prediction')
    return y.tolist(),init


def nnls2(x,y):
    solutions=[np.zeros(2)]
    both=np.linalg.lstsq(x,y,rcond=None)[0]
    if np.all(both>=0):solutions.append(both)
    for j in range(2):
        z=np.zeros(2);den=float(x[:,j]@x[:,j])
        if den>1e-20:z[j]=max(0.,float(x[:,j]@y)/den)
        solutions.append(z)
    return min(solutions,key=lambda z:(float(np.mean((x@z-y)**2)),float(z[1]),float(z[0])))


def fit(cases,parameters):
    if not cases or any(c.get('study_phase')!='development' for c in cases):
        raise ValueError('development-only fit; confirmation forbidden')
    beta0=parameters['ap_cooling_rate_per_s'];betas=beta0*np.geomspace(.2,5,61);betas[30]=beta0
    rows=[]
    for beta in betas:
        xs=[];ys=[]
        for c in cases:
            y=np.array(c['observed_ap_c']);a,x,_=basis(c,parameters,float(beta))
            if len(y)!=len(a) or not np.all(np.isfinite(y)):raise ValueError('missing development targets')
            weight=1/math.sqrt(len(y)*len(cases));xs.append(x*weight);ys.append((y-a)*weight)
        x=np.vstack(xs);y=np.concatenate(ys);kg=nnls2(x,y)
        norms=np.linalg.norm(x,axis=0);sv=np.linalg.svd(x/np.maximum(norms,1e-30),compute_uv=False)
        rank=int(np.sum(sv>sv[0]*1e-12)) if sv[0]>0 else 0
        rows.append(dict(beta=float(beta),k=float(kg[0]),g=float(kg[1]),
            mse=float(np.sum((x@kg-y)**2)),load_rank=rank,load_singular_values=sv.tolist()))
    best=min(rows,key=lambda r:(r['mse'],r['g'],abs(math.log(r['beta']/beta0)),abs(r['k']-1),r['beta']))
    best=dict(best,beta_boundary=best['beta'] in (float(betas[0]),float(betas[-1])),parameters=copy.deepcopy(parameters))
    columns=[];eps=1e-4
    for name in ('beta','k','g'):
        changed=copy.deepcopy(best);step=eps*max(best[name],.1) if name!='beta' else eps*best[name]
        changed[name]+=step
        columns.append(np.concatenate([(np.array(predict(c,changed)[0])-predict(c,best)[0])/
            step/math.sqrt(len(c['observed_ap_c'])*len(cases)) for c in cases]))
    j=np.array(columns).T;norm=np.linalg.norm(j,axis=0);sv=np.linalg.svd(j/np.maximum(norm,1e-30),compute_uv=False)
    best['numerical_rank']=int(np.sum(sv>sv[0]*1e-12)) if sv[0]>0 else 0
    best['scaled_singular_values']=sv.tolist()
    best['practical_identification']='not certified by numerical rank; profile/LOSO retained'
    return best,rows


def scores(case,values):
    s=common.score(case['observed_ap_c'],values);s['absolute_peak_error_c']=abs(s['peak_signed_error_c'])
    return s


def directions(case,values,windows):
    q=case['inputs']['query_s'];obs=case['observed_ap_c'];out=[]
    for a,b in windows:
        oa,ob=[common.interpolate(q,obs,t) for t in (a,b)]
        pa,pb=[common.interpolate(q,values,t) for t in (a,b)]
        if None in (oa,ob,pa,pb):raise ValueError('direction endpoint missing')
        change=ob-oa;pred=pb-pa;low,high=change-.1,change+.1
        # Tolerance avoids labeling 0.1C quantization as a strictly positive interval.
        opposite=(low>1e-10 and pred< -1e-10) or (high< -1e-10 and pred>1e-10)
        out.append(dict(start_s=a,end_s=b,observed_change_c=change,predicted_change_c=pred,
            rounding_sensitivity_interval_c=[low,high],opposite=opposite,
            observed_direction='positive' if low>1e-10 else 'negative' if high< -1e-10 else 'unresolved'))
    return out


def develop(cases,parameters,contract):
    expected=contract['development_order']
    if len(cases)!=6 or [c['condition'] for c in cases]!=expected or len({c['id'] for c in cases})!=6:
        raise ValueError('complete designated development six required')
    m0=dict(beta=parameters['ap_cooling_rate_per_s'],k=1.,g=0.,parameters=copy.deepcopy(parameters))
    m1,profile=fit(cases,parameters)
    result=dict(status='unidentified_stop',selected_model=None,profile=profile,m1=m1,m0=m0,
        loso=[],control_directions=[],accuracy_pass=None,default=False,strict_support=False,experiment_ready=False)
    if m1['load_rank']<2 or m1['numerical_rank']<3 or m1['beta_boundary']:
        result['reason']='rank deficient or beta boundary; no confirmation';return result
    for i,c in enumerate(cases):
        local,_=fit([x for j,x in enumerate(cases) if j!=i],parameters)
        row=dict(id=c['id'],condition=c['condition'],excluded_fit=local,
            m0=scores(c,predict(c,m0)[0]),m1=scores(c,predict(c,local)[0]))
        result['loso'].append(row)
    comparisons=[]
    for condition in dict.fromkeys(expected):
        rows=[r for r in result['loso'] if r['condition']==condition]
        for metric in ('mae_c','max_absolute_error_c','absolute_peak_error_c'):
            comparisons.append(dict(condition=condition,metric=metric,
                m0=sum(r['m0'][metric] for r in rows)/len(rows),m1=sum(r['m1'][metric] for r in rows)/len(rows)))
    result['condition_comparisons']=comparisons
    eligible_loso=all(r['excluded_fit']['load_rank']==2 and r['excluded_fit']['numerical_rank']==3 and
        not r['excluded_fit']['beta_boundary'] for r in result['loso'])
    improved=eligible_loso and all(r['m1']<=r['m0']+1e-12 for r in comparisons) and any(r['m1']<r['m0']-1e-12 for r in comparisons)
    selected=copy.deepcopy(m1 if improved else m0)
    result['selected_name']='M1' if improved else 'M0'
    for c in cases:
        if c['condition']=='C':
            d=directions(c,predict(c,selected)[0],contract['direction_windows_s'])
            result['control_directions'].append(dict(id=c['id'],windows=d))
    if any(w['opposite'] for d in result['control_directions'] for w in d['windows']):
        result['reason']='selected model control direction opposite beyond rounding sensitivity; no confirmation';return result
    result.update(status='ready_to_freeze',selected_model=selected,
        reason='prespecified development selection only; independent accuracy still pending')
    return result
