"""One development-calibrated residual gain. Saved cost rows only, no RL or device."""
import argparse
import csv
import datetime
import json
import math
from pathlib import Path
from statistics import mean
from tools import d1_rolling_forecast as previous

BUNDLE=previous.h.m.ROOT/'docs/results/rolling_energy_shrink_01'


def csv_rows(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def load_rows():
    meta={c['id']:c for c in previous.h.m.read(previous.BUNDLE/'inputs.json.gz')}
    saved=csv_rows(previous.BUNDLE/'window_errors.csv');snaps={(x['id'],float(x['cutoff_s'])):x for x in csv_rows(previous.BUNDLE/'snapshots.csv')}
    full={(x['id'],float(x['start_s'])):x for x in saved if x['method']=='ROLLING_OFFSET'}
    rows=[]
    for old in saved:
        if old['method']!='FROZEN_OPEN_LOOP' or old['energy_status']!='complete_10s':continue
        start,end=float(old['start_s']),float(old['end_s']);snapshot=snaps[(old['id'],start)]
        if end-start!=10 or snapshot['power_status']!='available' or float(snapshot['power_available'])>start:
            raise ValueError('invalid or future power prefix')
        c=meta[old['id']];base=float(old['predicted_j']);obs=float(old['observed_j']);x=float(snapshot['power_delta_w'])*10
        if abs(base+x-float(full[(old['id'],start)]['predicted_j']))>1e-9:raise ValueError('previous full correction mismatch')
        if not all(math.isfinite(v) for v in (base,obs,x)) or min(base,obs,base+x)<=0:raise ValueError('nonfinite/nonpositive saved cost')
        rows.append(dict(id=old['id'],block=c['block'],role=c['role'],gap=c['gap'],policy=c['policy'],start_s=start,end_s=end,
                         segment_type=old['segment_type'],base_j=base,observed_j=obs,correction_j=x,
                         past_available_s=float(snapshot['power_available'])))
    if len(rows)!=160 or len({x['id'] for x in rows})!=20:raise ValueError('20 complete sessions,160 windows required')
    if any(sum(y['id']==x['id'] for y in rows)!=8 for x in rows):raise ValueError('eight complete windows per session')
    return rows


def apply(base_j,correction_j,alpha):
    if not all(math.isfinite(v) for v in (base_j,correction_j,alpha)) or not 0<=alpha<=1:
        raise ValueError('finite bounded gain required')
    value=base_j+alpha*correction_j
    if value<=0:raise ValueError('nonpositive forecast; not clipped')
    return value


def predict(case,frozen,snapshot,alpha,end):
    if snapshot.get('power_status')!='available' or snapshot.get('power_available',float('inf'))>snapshot['cutoff_s']:
        raise ValueError('missing or future residual input')
    if end-snapshot['cutoff_s']!=10:raise ValueError('complete fixed10s horizon required')
    original=previous.forecast_energy(case,frozen,snapshot,'FROZEN_OPEN_LOOP',end)
    return apply(original,snapshot['power_delta_w']*10,alpha)


def loss(rows,alpha):
    ids=set(x['id'] for x in rows)
    return mean(mean(abs(apply(x['base_j'],x['correction_j'],alpha)-x['observed_j']) for x in rows if x['id']==identity) for identity in ids)


def fit_alpha(rows):
    if not rows or any(x['block']!='history' or x['role']!='development' for x in rows):
        raise ValueError('designated history development only')
    ids={x['id'] for x in rows};counts={identity:sum(x['id']==identity for x in rows) for identity in ids}
    ratios=[];information=0.
    for x in rows:
        correction=x['correction_j'];weight=1/(len(ids)*counts[x['id']]);information+=weight*correction**2
        if abs(correction)>1e-12:
            ratios.append(((x['observed_j']-x['base_j'])/correction,weight*abs(correction)))
    if information<=1e-12 or not ratios:raise ValueError('residual gain unidentified')
    ratios.sort();half=sum(w for value,w in ratios)/2;cum=0.
    for median,w in ratios:
        cum+=w
        if cum>=half-1e-14:break
    alpha=min(1.,max(0.,median))
    return dict(alpha=float(alpha),unconstrained_median=float(median),information=float(information),
                development_ids=sorted(ids),windows=len(rows),primary_training_mae_j=loss(rows,alpha),
                practical_identification='one scalar projection, not a new physical power coefficient or population guarantee')


def net_loss(rows,alpha):
    return mean(abs(sum(apply(x['base_j'],x['correction_j'],alpha)-x['observed_j'] for x in rows if x['id']==identity)) for identity in set(x['id'] for x in rows))


def freeze(rows):
    development=[x for x in rows if x['role']=='development' and x['block']=='history']
    if len(development)!=48 or len({x['id'] for x in development})!=6 or {x['gap'] for x in development}!={30,180}:
        raise ValueError('six development sessions required')
    fitted=fit_alpha(development);folds=[]
    for gap in (30,180):
        train=[x for x in development if x['gap']!=gap];test=[x for x in development if x['gap']==gap]
        local=fit_alpha(train)
        folds.append(dict(held_out_gap=gap,fit=local,base_mae_10s_j=loss(test,0),candidate_mae_10s_j=loss(test,local['alpha']),
                          base_net80_mae_j=net_loss(test,0),candidate_net80_mae_j=net_loss(test,local['alpha'])))
    passed=all(x['candidate_mae_10s_j']<=x['base_mae_10s_j']+1e-12 and x['candidate_net80_mae_j']<=x['base_net80_mae_j']+1e-12 for x in folds)
    passed=passed and any(x['candidate_mae_10s_j']<x['base_mae_10s_j']-1e-12 for x in folds)
    return dict(candidate=fitted,history_folds=folds,development_gate=bool(passed),selected_alpha=fitted['alpha'] if passed else 0.,
                diagnostic_alpha=fitted['alpha'],confirmation_used_for_fit=False,selection_before_evaluation=True,
                posthoc=True,accuracy_pass=None,strict_support=False,default=False,experiment_ready=False)


def run(output):
    output=Path(output)
    if output.exists():raise FileExistsError('new output required')
    contract=previous.h.m.read(BUNDLE/'contract.json')
    for path,digest in contract['source_hashes'].items():
        if previous.h.m.sha(previous.h.m.ROOT/path)!=digest:raise ValueError('registered source changed')
    original=load_rows();fitted=freeze(original);output.mkdir(parents=True)
    previous.h.m.write(output/'candidate_freeze.json',dict(fitted,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),contract_sha256=previous.h.m.sha(BUNDLE/'contract.json')))
    freeze_sha=previous.h.m.sha(output/'candidate_freeze.json')
    # Only after this durable record do evaluation targets participate in scoring.
    rows=[];sessions=[];methods={'FROZEN':0.,'FULL_CORRECTION':1.,'DEV_MAE_SHRINK':fitted['diagnostic_alpha']}
    for x in original:
        for name,alpha in methods.items():
            pred=apply(x['base_j'],x['correction_j'],alpha);error=pred-x['observed_j']
            rows.append(dict(**x,method=name,alpha=alpha,predicted_j=pred,signed_j=error,abs_j=abs(error),relative_j=error/x['observed_j'],future_observation_input=False))
    for identity in dict.fromkeys(x['id'] for x in rows):
        for name,alpha in methods.items():
            use=[x for x in rows if x['id']==identity and x['method']==name];x=use[0];error=sum(z['signed_j'] for z in use)
            sessions.append(dict(id=identity,block=x['block'],role=x['role'],gap=x['gap'],policy=x['policy'],method=name,alpha=alpha,windows=len(use),
                                 mae_10s_j=mean(z['abs_j'] for z in use),max_absolute_10s_j=max(z['abs_j'] for z in use),
                                 signed_net80_j=error,absolute_net80_j=abs(error),sum_absolute_10s_errors_j=sum(z['abs_j'] for z in use),
                                 observed_80s_j=sum(z['observed_j'] for z in use),predicted_80s_j=sum(z['predicted_j'] for z in use),
                                 common120_error=None,scope='eight sequential10s forecasts35..115; not single80s or full120s forecast'))
    summary=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        baseline={x['id']:x for x in sessions if x['block']==block and x['role']==role and x['method']=='FROZEN'}
        for method in methods:
            use=[x for x in sessions if x['block']==block and x['role']==role and x['method']==method]
            summary.append(dict(block=block,role=role,method=method,n=len(use),mae_10s_j=mean(x['mae_10s_j'] for x in use),
                                net80_mae_j=mean(x['absolute_net80_j'] for x in use),max_absolute_10s_j=max(x['max_absolute_10s_j'] for x in use),
                                local_worse_sessions=sum(x['mae_10s_j']>baseline[x['id']]['mae_10s_j']+1e-10 for x in use),
                                net_worse_sessions=sum(x['absolute_net80_j']>baseline[x['id']]['absolute_net80_j']+1e-10 for x in use),
                                both_improved_sessions=sum(x['mae_10s_j']<baseline[x['id']]['mae_10s_j']-1e-10 and x['absolute_net80_j']<baseline[x['id']]['absolute_net80_j']-1e-10 for x in use)))
    strata=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        for kind in ('resident_idle','transition_or_mixed'):
            for method in methods:
                use=[x for x in rows if x['block']==block and x['role']==role and x['segment_type']==kind and x['method']==method]
                strata.append(dict(block=block,role=role,segment_type=kind,method=method,windows=len(use),mae_10s_j=mean(x['abs_j'] for x in use) if use else None,independent_unit='session, not window'))
    for name,values in [('window_errors.csv',rows),('session_errors.csv',sessions),('comparison.csv',summary),('strata.csv',strata)]:previous.h.m.table(output/name,values)
    previous.h.m.write(output/'summary.json',dict(candidate_alpha=fitted['diagnostic_alpha'],selected_alpha=fitted['selected_alpha'],development_gate=fitted['development_gate'],
          candidate_structures=1,formal_fit_calls=3,sessions=20,scored_window_rows=len(rows),freeze_sha256=freeze_sha,
          source_contract_sha256=previous.h.m.sha(BUNDLE/'contract.json'),device_commands=0,rl_training=0,policy_simulations=0,apk_builds=0,
          posthoc=True,full120_error=None,accuracy_pass=None,policy_winner=None,experiment_ready=False))
    print(json.dumps(previous.h.m.read(output/'summary.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);run(p.parse_args().output)
