"""One fixed30s past-average candidate, fitted on development only. No policy/device."""
import argparse
import datetime
import json
import math
from pathlib import Path
from statistics import mean
from tools import d1_power_residual_structure as diagnostic
from tools import d1_rolling_energy_shrink as shrink

BUNDLE=diagnostic.r.h.m.ROOT/'docs/results/energy_memory30_01'
OLD_ALPHA=.26268831243642554


def source_rows():
    rows=diagnostic.csv_rows(diagnostic.BUNDLE/'past_features.csv');result=[]
    for x in rows:
        if float(x['past_available_s'])>float(x['start_s']):raise ValueError('future prefix')
        result.append(dict(id=x['id'],block=x['block'],role=x['role'],gap=int(x['gap']) if x['gap'] else None,policy=x['policy'],
                           start_s=float(x['start_s']),end_s=float(x['end_s']),base_j=float(x['base_j']),observed_j=float(x['observed_j']),
                           correction_j=10*float(x['past30_residual_w']),past10_j=10*float(x['past10_residual_w']),past_available_s=float(x['past_available_s'])))
    if len(result)!=160 or len({x['id'] for x in result})!=20:raise ValueError('full20-session denominator')
    for identity in {x['id'] for x in result}:
        use=[x for x in result if x['id']==identity]
        if len(use)!=8 or {x['start_s'] for x in use}!=set(range(35,106,10)):
            raise ValueError('eight unique registered windows per session')
    for x in result:
        fields=('start_s','end_s','base_j','observed_j','correction_j','past10_j','past_available_s')
        if not all(math.isfinite(x[k]) for k in fields) or x['end_s']-x['start_s']!=10:
            raise ValueError('finite registered ten-second window')
        if min(x['base_j'],x['observed_j'])<=0 or (x['block'],x['role']) not in {
                ('history','development'),('history','confirmation'),('sustained','evaluation')}:
            raise ValueError('cost/role boundary')
    return result


def predict(c,frozen,now,alpha):
    if now not in range(35,106,10):raise ValueError('registered ten-second window')
    past=diagnostic.past_residual(c,now,30,frozen)
    base=c['pre_w']*10+diagnostic.r.state_energy(c,frozen,now,now+10)
    return shrink.apply(base,past['residual_w']*10,alpha)


def run(output):
    output=Path(output)
    if output.exists():raise FileExistsError('new output required')
    contract=diagnostic.r.h.m.read(BUNDLE/'contract.json')
    for p,digest in contract['source_hashes'].items():
        if diagnostic.r.h.m.sha(diagnostic.r.h.m.ROOT/p)!=digest:raise ValueError('source identity')
    if not diagnostic.r.h.m.read(diagnostic.BUNDLE/'summary.json')['candidate30_evidence']:raise ValueError('diagnostic gate missing')
    original=source_rows();fitted=shrink.freeze(original);output.mkdir(parents=True)
    diagnostic.r.h.m.write(output/'candidate_freeze.json',dict(fitted,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),past_seconds=30,
                             contract_sha256=diagnostic.r.h.m.sha(BUNDLE/'contract.json')))
    freeze_sha=diagnostic.r.h.m.sha(output/'candidate_freeze.json')
    methods=('FROZEN','FULL10','SHRINK10_FIXED','MEMORY30');windows=[];sessions=[];comparison=[]
    for x in original:
        for name in methods:
            correction=x['correction_j'] if name=='MEMORY30' else x['past10_j']
            alpha={'FROZEN':0.,'FULL10':1.,'SHRINK10_FIXED':OLD_ALPHA,'MEMORY30':fitted['diagnostic_alpha']}[name]
            pred=shrink.apply(x['base_j'],correction,alpha);error=pred-x['observed_j']
            windows.append(dict(**x,method=name,alpha=alpha,predicted_j=pred,signed_j=error,abs_j=abs(error),relative_j=error/x['observed_j'],future_observation_input=False))
    for identity in dict.fromkeys(x['id'] for x in windows):
        for name in methods:
            use=[x for x in windows if x['id']==identity and x['method']==name];x=use[0];error=sum(z['signed_j'] for z in use)
            sessions.append(dict(id=identity,block=x['block'],role=x['role'],gap=x['gap'],policy=x['policy'],method=name,windows=len(use),
                                 mae_10s_j=mean(z['abs_j'] for z in use),maximum_10s_j=max(z['abs_j'] for z in use),
                                 signed_net80_j=error,absolute_net80_j=abs(error),sum_absolute_window_errors_j=sum(z['abs_j'] for z in use),
                                 observed_80s_j=sum(z['observed_j'] for z in use),predicted_80s_j=sum(z['predicted_j'] for z in use),common120_error=None))
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        ref={x['id']:x for x in sessions if x['block']==block and x['role']==role and x['method']=='FROZEN'}
        for name in methods:
            use=[x for x in sessions if x['block']==block and x['role']==role and x['method']==name]
            comparison.append(dict(block=block,role=role,method=name,n=len(use),mae_10s_j=mean(x['mae_10s_j'] for x in use),net80_mae_j=mean(x['absolute_net80_j'] for x in use),
                                   maximum_10s_j=max(x['maximum_10s_j'] for x in use),local_worse_sessions=sum(x['mae_10s_j']>ref[x['id']]['mae_10s_j']+1e-10 for x in use),
                                   net_worse_sessions=sum(x['absolute_net80_j']>ref[x['id']]['absolute_net80_j']+1e-10 for x in use),
                                   both_improved_sessions=sum(x['mae_10s_j']<ref[x['id']]['mae_10s_j']-1e-10 and x['absolute_net80_j']<ref[x['id']]['absolute_net80_j']-1e-10 for x in use)))
    for name,values in [('window_errors.csv',windows),('session_errors.csv',sessions),('comparison.csv',comparison)]:diagnostic.r.h.m.table(output/name,values)
    summary=dict(candidate_alpha=fitted['diagnostic_alpha'],selected_alpha=fitted['selected_alpha'],development_gate=fitted['development_gate'],
                 past_seconds=30,candidate_structures=1,formal_fit_calls=3,rows=len(windows),sessions=20,freeze_sha256=freeze_sha,
                 model_sha256=diagnostic.r.h.m.sha(diagnostic.r.h.m.MODEL),contract_sha256=diagnostic.r.h.m.sha(BUNDLE/'contract.json'),
                 full120_error=None,posthoc=True,device_commands=0,rl_training=0,policy_simulations=0,apk_builds=0,
                 accuracy_pass=None,policy_winner=None,experiment_ready=False)
    diagnostic.r.h.m.write(output/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);run(p.parse_args().output)
