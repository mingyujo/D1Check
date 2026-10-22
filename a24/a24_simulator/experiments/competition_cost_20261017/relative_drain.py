"""Native current ratio model for already-received M8 data, with no unit repair.

This predicts a sensor response index. It is not a substitute for calibrated
energy, output-quality validation, installed-delegate proof or a physical CI.
"""
import math,statistics
from state_cost import STATES,ANCHOR,BASELINE,exposures,fit,predict,state_key
from fit_cost import zoh_mean,mean

ALL_STATES=tuple(sorted((*STATES,'detection_GPU','classification_CPU+classification_GPU',
                        'classification_CPU+detection_GPU','detection_CPU+detection_GPU')))
OLD=dict(zip(STATES,ANCHOR));OLD['detection_GPU']=.6013808404579677
PRIOR=tuple((OLD.get(s,sum(OLD.get(p,0.) for p in s.split('+'))))/BASELINE for s in ALL_STATES)
SPEC=dict(schema='A24-native-current-relative-state-v1',unit='dimensionless current magnitude / causal pre-work median',
          scale_correction=0,voltage_to_energy_conversion=False,charge_to_current_scale_fit=False,
          tau_candidates_s=[0.,.9,3.,10.],ridge=.01,coefficient_bounds=[0,10],
          bin_s=5,maxgap_s=2.,minimum_pre_samples=10,minimum_positive_activity_s=1.,
          minimum_support_sessions=3,minimum_support_s=5.,
          validation='cohort holdout; inner cohort holdout tau selection; all sources previously seen',
          adoption='cohort-equal MAE at least2% below anchored state model and constant normalized baseline',
          measured_J=None,independent_confirmation=False)

def exclusive(owners,lo,hi):
    edges=sorted(set([lo,hi]+[max(lo,min(hi,r[k])) for r in owners for k in ('start_s','end_s')]))
    ans=[]
    for a,b in zip(edges,edges[1:]):
        active=[r for r in owners if r['start_s']<b and r['end_s']>a]
        if len(active)>2 or len({r['route'] for r in active})!=len(active):raise ValueError('Resource ownership conflict')
        state='+'.join(sorted(('classification' if r['task']=='C' else 'detection')+'_'+r['route'] for r in active)) or 'idle'
        if state!='idle' and state not in ALL_STATES:raise ValueError('Unknown owner state')
        ans.append(dict(start_s=a,end_s=b,state=state))
    return ans

def prepare(s):
    raw=s.get('battery',{}).get('raw_samples',[])
    if not raw:raise ValueError('NO_NATIVE_CURRENT_SERIES')
    coverage=s.get('activity_coverage_s');owners=s.get('owner_intervals',[])
    if not coverage or s.get('clock_issues'):raise ValueError('UNQUALIFIED_ACTIVITY_CLOCK')
    if s.get('execution',{}).get('unclosed_owners'):raise ValueError('UNCLOSED_OWNER')
    first=min((r['start_s'] for r in owners),default=35.)
    pre=[r for r in raw if max(coverage[0],first-30)<=r['t_s']<first-1]
    samples=[r for r in raw if type(r.get('current_raw')) in (int,float) and math.isfinite(r['current_raw']) and
             r['current_raw']<0 and r['current_raw']!=-2147483648 and r.get('plugged')==0]
    invalid=len(raw)-len(samples)
    allowed={r['source_line'] for r in samples}
    pre=[r for r in pre if r['source_line'] in allowed]
    if len(pre)<10:raise ValueError('INSUFFICIENT_CAUSAL_PRE_CURRENT')
    base=statistics.median(-r['current_raw'] for r in pre)
    units=sorted(set(str(r.get('current_unit')) for r in samples))
    if len(units)!=1:raise ValueError('WITHIN_SESSION_UNIT_CHANGE')
    if len({r['t_s'] for r in samples})!=len(samples):raise ValueError('DUPLICATE_CLOCK')
    samples=sorted(samples,key=lambda r:r['t_s']);t=[r['t_s'] for r in samples];v=[-r['current_raw']/base for r in samples]
    start=max(coverage[0],first,0.);end=min(coverage[1],t[-1],180.)
    windows=[(start+5*i,start+5*(i+1)) for i in range(max(0,int((end-start)/5)))]
    ys=[zoh_mean(t,v,*w) for w in windows]
    good=[(w,y) for w,y in zip(windows,ys) if y is not None]
    if len(good)<3:raise ValueError('INSUFFICIENT_CURRENT_COVERAGE')
    windows=[w for w,y in good];ys=[y for w,y in good]
    seg=exclusive(owners,coverage[0],coverage[1])
    feature={tau:exposures(seg,windows,tau,ALL_STATES) for tau in SPEC['tau_candidates_s']}
    return dict(id=s['session_id'],cohort=s['cohort_id'],baseline=1.,raw_baseline_current=base,
                declared_unit=units[0],feature=feature,truth=ys,windows=windows,rows=len(ys),
                raw_samples=len(raw),invalid_current_samples=invalid,causal_pre_samples=len(pre),
                invalid_samples_omitted_not_zero=True,relative_sensor_only=True,
                sensor_refresh_time_known=False,initial_history_verified=False,
                no_new_independent_confirmation=True)

def rows(ss,tau):return [dict(x=x,y=y-1.,session=s['id']) for s in ss for x,y in zip(s['feature'][tau],s['truth'])]
def train(ss,tau):return fit(rows(ss,tau),prior=PRIOR,upper=10.)
def errors(ss,tau,beta):
    ans=[]
    for s in ss:
        pred=[1+predict(x,beta) for x in s['feature'][tau]]
        anchor=[1+predict(x,PRIOR) for x in s['feature'][0.]]
        ans.append(dict(id=s['id'],cohort=s['cohort'],MAE_index=mean([abs(a-b) for a,b in zip(pred,s['truth'])]),
                        anchor_MAE_index=mean([abs(a-b) for a,b in zip(anchor,s['truth'])]),
                        constant_MAE_index=mean([abs(y-1) for y in s['truth']])))
    return ans
def select(ss):
    groups=sorted(set(s['cohort'] for s in ss));scores=[]
    for tau in SPEC['tau_candidates_s']:
        e=[]
        for g in groups:
            tr=[s for s in ss if s['cohort']!=g];te=[s for s in ss if s['cohort']==g]
            if tr:e+=errors(te,tau,train(tr,tau))
        scores.append(dict(tau_s=tau,score=mean([r['MAE_index'] for r in e])))
    return min(scores,key=lambda r:(r['score'],r['tau_s']))['tau_s'],scores

def fit_all(dataset):
    ss=[];excluded=[];folds=[];outer=[]
    for s in dataset['sessions']:
        try:ss.append(prepare(s))
        except (ValueError,KeyError,TypeError) as e:excluded.append(dict(id=s.get('session_id'),reason=str(e)))
    groups=sorted(set(s['cohort'] for s in ss))
    if len(groups)<3:return dict(status='INSUFFICIENT_GROUPS',excluded=excluded,model=None)
    for g in groups:
        tr=[s for s in ss if s['cohort']!=g];te=[s for s in ss if s['cohort']==g]
        tau,scores=select(tr);beta=train(tr,tau);outer+=errors(te,tau,beta)
        folds.append(dict(held_cohort=g,train_ids=[s['id'] for s in tr],test_ids=[s['id'] for s in te],tau_s=tau,inner_scores=scores))
    scores={k:mean([mean([r[k] for r in outer if r['cohort']==g]) for g in groups])
            for k in ('MAE_index','anchor_MAE_index','constant_MAE_index')}
    adopted=scores['MAE_index']<=.98*min(scores['anchor_MAE_index'],scores['constant_MAE_index'])
    tau,_=select(ss);beta=train(ss,tau)
    support=[]
    for i,state in enumerate(ALL_STATES):
        exposure=[sum(x[i]*(b-a) for x,(a,b) in zip(s['feature'][0.],s['windows'])) for s in ss]
        support.append(dict(state=state,sessions=sum(t>0 for t in exposure),seconds=sum(exposure),
                            qualified=sum(t>0 for t in exposure)>=3 and sum(exposure)>=5))
    return dict(status='SAVED_NATIVE_RELATIVE_DIAGNOSIS_COMPLETE',spec=SPEC,scores=scores,folds=folds,per_session=outer,
                sensor_audit=[{k:v for k,v in s.items() if k not in ('feature','truth','windows')} for s in ss],excluded=excluded,
                model=dict(schema=SPEC['schema'],states=list(ALL_STATES),coefficients=beta,tau_s=tau,support=support,
                           adopted_as_relative_sensor_predictor=adopted,measured_J=None,absolute_energy=False),
                all_sources_previously_seen=True,new_device_confirm=False,scale_corrected=False)

def observe(owners,lo,hi,model,history_start=0.):
    if not model or not model['adopted_as_relative_sensor_predictor']:
        return dict(status='UNQUALIFIED_MODEL',mean_index=None,measured_J=None)
    intervals=exclusive(owners,history_start,hi)
    unqualified=[r for r in model['support'] if not r['qualified']]
    actual={r['state'] for r in intervals if r['end_s']>lo and r['start_s']<hi}
    if any(r['state'] in actual for r in unqualified):
        return dict(status='UNQUALIFIED_ROUTE_SUPPORT',mean_index=None,measured_J=None,
                    unsupported_states=[r['state'] for r in unqualified if r['state'] in actual])
    x=exposures(intervals,[(lo,hi)],model['tau_s'],model['states'])[0]
    inc=predict(x,model['coefficients'])*(hi-lo)
    return dict(status='CONDITIONAL_NATIVE_SENSOR_INDEX',mean_index=1+inc/(hi-lo),
                baseline_device_seconds=hi-lo,increment_baseline_seconds=inc,total_baseline_seconds=hi-lo+inc,
                measured_J=None,quality_or_installation_verified=False)
