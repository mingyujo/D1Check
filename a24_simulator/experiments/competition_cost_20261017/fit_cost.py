"""Registered saved-only cost identification. No environment or neural update."""
from pathlib import Path
import argparse, gzip, json, math, os, statistics, sys
ROOT=Path(__file__).resolve().parents[2];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
from state_cost import SPEC,STATES,ANCHOR,BASELINE,exposures,fit,predict,state_key
G.OWN_TOKENS+=('competition_cost_20261017','protected48_v2_20261016','s26-state-aware-atc-','state_recovery_owner')

def cohort(s):
    sid=s['id']
    if sid.startswith('session_'):return 'macro'
    if '_LONG' in sid:return 'long'
    if '_30_' in sid:return 'history30'
    if '_180_' in sid:return 'history180'
    return 'old_short'

def mean(values): return sum(values)/len(values)

def zoh_mean(t,v,lo,hi,maxgap=2.):
    total=covered=0.
    for i in range(len(t)-1):
        a=max(lo,t[i]);b=min(hi,t[i+1])
        if b>a:
            if t[i+1]-t[i]>maxgap:return None
            total+=(b-a)*v[i];covered+=b-a
    return total/(hi-lo) if covered>=hi-lo-1e-7 else None

def prepare(s):
    t=s['power_t'];v=s['power_w']
    if len(t)!=len(v) or any(not math.isfinite(a+b) or b<0 for a,b in zip(t,v)):
        raise ValueError('Sensor type/range')
    if any(t[i+1]<=t[i] for i in range(len(t)-1)):raise ValueError('Sensor clock')
    # Pre-origin observations only. Do not normalize by a future active mean.
    pre=[p for q,p in zip(t,v) if -30<=q<0]
    if len(pre)<10:raise ValueError('Insufficient causal baseline samples')
    baseline=statistics.median(pre)
    seg=s['actual'];end=min(t[-1],max(r['end_s'] for r in seg),s.get('common_end_s',180.))
    windows=[(35.+5*i,40.+5*i) for i in range(max(0,int((end-35)/5)))]
    ys=[zoh_mean(t,v,*w) for w in windows]
    windows=[w for w,y in zip(windows,ys) if y is not None];ys=[y for y in ys if y is not None]
    allx={tau:exposures(seg,windows,tau) for tau in SPEC['tau_candidates_s']}
    return dict(id=s['id'],cohort=cohort(s),baseline=baseline,windows=windows,truth=ys,
                feature=allx,rows=len(ys),causal_pre_samples=len(pre),
                observed_period_median_s=statistics.median([b-a for a,b in zip(t,t[1:])]),
                unit_qualification='legacy derived power_w; raw current/charge calibration not established')

def rows(sessions,tau):
    return [dict(x=x,y=y-s['baseline'],session=s['id']) for s in sessions for x,y in zip(s['feature'][tau],s['truth'])]

def errors(sessions,tau,beta):
    ans=[]
    for s in sessions:
        y=s['truth']; pred=[s['baseline']+predict(x,beta) for x in s['feature'][tau]]
        fixed=[BASELINE+predict(x,ANCHOR) for x in s['feature'][0.]]
        same=[s['baseline']+predict(x,ANCHOR) for x in s['feature'][0.]]
        ans.append(dict(id=s['id'],cohort=s['cohort'],bins=len(y),baseline=s['baseline'],
                        MAE_W_proxy=mean([abs(a-b) for a,b in zip(y,pred)]),
                        fixed_anchor_MAE_W_proxy=mean([abs(a-b) for a,b in zip(y,fixed)]),
                        causal_baseline_anchor_MAE_W_proxy=mean([abs(a-b) for a,b in zip(y,same)]),
                        integrated_bias_J_proxy=sum((a-b)*5 for a,b in zip(pred,y)),
                        truth_unit='historical derived projection, not calibrated energy'))
    return ans

def select_tau(train):
    scores=[]
    # Entire sessions are left out; no random sensor-row split.
    for tau in SPEC['tau_candidates_s']:
        e=[]
        for held in train:
            remaining=[s for s in train if s['id']!=held['id']]
            beta=fit(rows(remaining,tau));e+=errors([held],tau,beta)
        scores.append(dict(tau_s=tau,MAE_W_proxy=mean([r['MAE_W_proxy'] for r in e])))
    return min(scores,key=lambda s:(s['MAE_W_proxy'],s['tau_s']))['tau_s'],scores

def run(operation):
    op=G.read(operation);sha=G.sha(operation);reg=G.read(ROOT/'models/registration.json')
    G.require(op['schema']=='A24-cost-identification-operation-v1' and op['model_spec']==SPEC,'Freeze')
    for p in op['source_pins']+op['input_pins']:G.pin(p)
    known=reg['known_PS_producer_paths']+op['known_PS_producer_paths']
    G.process_guard(ENTRY,known);G.free_guard([ROOT,'D:/',reg['worker_lock_path']])
    out=ROOT/op['output_dir'];G.require(not out.exists(),'Consumed output')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        out.mkdir(parents=True,exist_ok=False);G.write_new(out/'START.json',dict(operation_sha256=sha,utc=G.now()))
        try:
            source=op['historical_power_pin'];raw=gzip.decompress((ROOT/source['stored']).read_bytes())
            import hashlib
            G.require(hashlib.sha256(raw).hexdigest()==source['sha256'],'Historical source bytes')
            sessions=[prepare(s) for s in json.loads(raw)]
            G.require(len(sessions)==35 and len(set(s['id'] for s in sessions))==35,'Historical scope')
            audits=[{k:v for k,v in s.items() if k not in ('feature','truth','windows')} for s in sessions]
            G.write_new(out/'SENSOR_AUDIT.json',dict(sessions=audits,measured_J=None,
                         raw_sensor_calibration_verified=False,microphase_fitting=False,
                         microphase_reason='0.9s sensor cadence/5s bins cannot identify millisecond callback energy',
                         new_data_unit_audit_pins=op['new_data_unit_audit_pins']))
            outer=[];folds=[]
            for group in sorted(set(s['cohort'] for s in sessions)):
                G.process_guard(ENTRY,known)
                train=[s for s in sessions if s['cohort']!=group];test=[s for s in sessions if s['cohort']==group]
                tau,ranking=select_tau(train);beta=fit(rows(train,tau))
                outer+=errors(test,tau,beta)
                folds.append(dict(held_cohort=group,train_ids=[s['id'] for s in train],test_ids=[s['id'] for s in test],
                                  tau_s=tau,coefficients_W_proxy=beta,inner_scores=ranking))
            groups=sorted(set(r['cohort'] for r in outer))
            scores={k:mean([mean([r[k] for r in outer if r['cohort']==g]) for g in groups])
                    for k in ('MAE_W_proxy','fixed_anchor_MAE_W_proxy','causal_baseline_anchor_MAE_W_proxy')}
            adopt=scores['MAE_W_proxy']<=.98*scores['causal_baseline_anchor_MAE_W_proxy']
            tau,ranking=select_tau(sessions);beta=fit(rows(sessions,tau))
            model=dict(schema=SPEC['schema'],tau_s=tau,coefficients_W_proxy=beta,
                       supported_states=list(STATES),baseline_source='causal pre-origin sensor median or explicit reference scenario',
                       reference_baseline_W_proxy=BASELINE,adopted_for_qualified_states=adopt,
                       adoption_reason='predeclared grouped validation threshold',
                       coefficients_are_conditional_proxy=True,measured_J=None,
                       unsupported_policy='additive transfer plus 0..2x sensitivity envelope, no universal pair discount',
                       initial_state='zero before supplied history; missing history unqualified',
                       deployment_selection=ranking,training_sessions=35,
                       independent_confirmation=False,new_device_data_fit=False)
            G.write_new(out/'MODEL.json',model)
            G.write_new(out/'VALIDATION.json',dict(scores=scores,folds=folds,per_session=outer,
                         model_adopted=adopt,all_sessions_previously_seen=True,
                         no_future_AP_or_outcome_features=True,absolute_energy_accuracy_PASS=False,
                         calibration_limit='W*/J* derived historical scale; new raw-current scale not repaired'))
            # New measurements inform a separate native-current ratio response.
            # No arbitrary conversion is used to mix its numerical scale with J*.
            from relative_drain import fit_all, SPEC as RELATIVE_SPEC
            G.require(op['relative_model_spec']==RELATIVE_SPEC,'Relative contract drift')
            G.process_guard(ENTRY,known);G.free_guard([ROOT,'D:/'])
            dataset=G.read(G.pin(op['combined_dataset_pin']))
            relative=fit_all(dataset)
            G.write_new(out/'NATIVE_RELATIVE_MODEL.json',relative)
            for p in op['source_pins']+op['input_pins']:G.pin(p)
            G.require(G.sha(operation)==sha,'Operation drift')
            G.write_new(out/'COMPLETE.json',dict(status='SAVED_COST_IDENTIFICATION_COMPLETE',utc=G.now(),
                         model_sha256=G.sha(out/'MODEL.json'),validation_sha256=G.sha(out/'VALIDATION.json'),
                         relative_model_sha256=G.sha(out/'NATIVE_RELATIVE_MODEL.json'),
                         operation_sha256=sha,adopted=adopt,new_START=0,NN_updates=0,measured_J=None))
            print(json.dumps(dict(scores=scores,adopted=adopt,model=model)),flush=True)
        except BaseException as e:
            G.write_new(out/'FAILURE.json',dict(error=str(e),utc=G.now(),automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);run(p.parse_args().operation)
