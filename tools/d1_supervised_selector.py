"""History-only, episode-level supervised selector. PC exploration, not deployment.

No future trace, workload ID, realized service context or outcome enters predict().
The synthetic preceding window is independent of the next episode conditional on
the workload envelope. Stationarity and reset initial thermal state are assumptions.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import pickle
import statistics
import time

import numpy as np
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
import sklearn

from tools import d1_scheduler_conditions as s
from tools.d1_scheduler_conditions_report import read, group_result

p = s.p
POLICIES = tuple(s.POLICIES)
TARGETS = ('miss_fraction', 'energy_j', 'peak_ap_c', 'thermal_degree_seconds')
FEATURES = ('class_share', 'mean_gap_s', 'median_gap_s', 'gap_cv', 'short_gap_share')
MODELS = ('tree', 'boosting')
MODES = ('energy', 'thermal')
SOURCE = s.ROOT / 'run_v2/results.csv'
ROOT = p.ROOT / 'docs/results/supervised_selector_01'


def holdout(e):
    return (s.GAPS.index(e['gap_s']) + s.SHARES.index(e['class_share']) +
            s.BURSTS.index(e['burst'])) % 3 == 0


def features(history, cutoff_ns):
    """Only fully arrived historical requests, exactly 48 for this version."""
    if len(history) != 48:
        raise ValueError('requires registered 48-request history; cold start unsupported')
    ts = [q['arrival_ns'] for q in history]
    if any(not math.isfinite(t) or t > cutoff_ns for t in ts):
        raise ValueError('future/nonfinite observation')
    gaps = [(b-a)/1e9 for a, b in zip(ts, ts[1:])]
    if any(g <= 0 for g in gaps):
        raise ValueError('unordered/duplicate arrival')
    if any(q['task'] not in ('classification', 'detection') for q in history):
        raise ValueError('unsupported task')
    mean = statistics.mean(gaps)
    return [sum(q['task']=='classification' for q in history)/48,
            mean, statistics.median(gaps), statistics.pstdev(gaps)/mean,
            sum(g < .05 for g in gaps)/len(gaps)]


def previous(e, seed):
    # Separate RNG window, not the first part of the evaluation episode.
    hist = s.workload(e, seed + 700000)
    shift = hist[-1]['arrival_ns'] + 1000000000
    hist = [dict(q, arrival_ns=q['arrival_ns']-shift) for q in hist]
    return hist


def vector(x, policy):
    if policy not in POLICIES:
        raise ValueError('unsupported policy')
    return list(x) + [float(policy == z) for z in POLICIES]


def training(rows):
    groups = defaultdict(list)
    allowed = {e['id']:e for e in s.envelopes() if not holdout(e)}
    for r in rows:
        if r['stage']=='development' and r['envelope'] in allowed:
            groups[r['envelope'], int(r['seed']), r['policy']].append(r)
    if len(groups) != 18*2*len(POLICIES):
        raise ValueError('incomplete training groups')
    X, Y, histories = [], [], []
    for (eid, seed, policy), xs in sorted(groups.items()):
        if {x['scenario'] for x in xs} != set(s.a.old.SCENARIOS) or len(xs)!=3:
            raise ValueError('incomplete service contexts')
        if any(x[k] is None for x in xs for k in TARGETS[1:]):
            raise ValueError('missing cost cannot become zero')
        h = previous(allowed[eid], seed); x = features(h, 0)
        X.append(vector(x, policy))
        Y.append([max(1-r['deadline_met']/r['planned'] for r in xs)] +
                 [statistics.mean(r[k] for r in xs) for k in TARGETS[1:]])
        histories.append(dict(envelope=eid, seed=seed, policy=policy, features=x))
    return np.asarray(X), np.asarray(Y), histories


def fit(X, Y, kind):
    # Four separate regressors: J magnitude must not dominate AP/risk tree splits.
    models=[]
    for i in range(4):
        m = (DecisionTreeRegressor(max_depth=5, min_samples_leaf=4, random_state=20261005)
             if kind=='tree' else HistGradientBoostingRegressor(
                 max_iter=100, max_depth=3, min_samples_leaf=5, learning_rate=.05,
                 early_stopping=False, random_state=20261005))
        m.fit(X, Y[:, i]); models.append(m)
    return models


def choose(models, history, mode, bounds, cutoff_ns=0):
    if mode not in MODES:
        raise ValueError('unknown objective')
    x = features(history, cutoff_ns)
    if any(v < lo-1e-9 or v > hi+1e-9 for v, lo, hi in zip(x, *bounds)):
        return dict(policy='EFT_REFERENCE', reason='feature_box_outside', predictions=None)
    z = np.asarray([vector(x, pol) for pol in POLICIES])
    pred = np.column_stack([m.predict(z) for m in models])
    if not np.isfinite(pred).all():
        raise ValueError('nonfinite prediction')
    # Less than half a predicted missed request; this is NOT a safety guarantee.
    feasible = [i for i in range(len(POLICIES)) if pred[i,0] <= .5/48]
    record = {pol:dict(zip(TARGETS, map(float, pred[i]))) for i, pol in enumerate(POLICIES)}
    if not feasible:
        return dict(policy='EFT_REFERENCE', reason='no_predicted_feasible', predictions=record)
    order = (1,2,3) if mode=='energy' else (2,3,1)
    idx = min(feasible, key=lambda i:tuple(round(float(pred[i,j]),6) for j in order)+(POLICIES[i],))
    return dict(policy=POLICIES[idx], reason='learned_cost_choice', predictions=record)


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    began=time.monotonic()
    paths=[Path(__file__), SOURCE, p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json',
           Path(s.__file__),Path(p.__file__),Path(s.a.__file__),Path(s.a.old.engine.__file__)]
    hashes={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    spec=dict(id='history-supervised-selector-v1', utc=datetime.now(timezone.utc).isoformat(),
        base_head='f4f6049826807ed5f7e4471ef6ae7f7cd82724bb', features=FEATURES, targets=TARGETS,
        train_seeds=[81001,81002], validation_seed=91001, final_seeds=[123001,123002],
        withheld_envelopes=[e['id'] for e in s.envelopes() if holdout(e)],
        selection='validation missed requests, then objective delta vs EFT; no refit after selection',
        history='independent preceding 48 arrivals, same stationary envelope; reset initial0; not continuous history thermal simulation',
        risk_cutoff=.5/48, fallback='EFT, not a service guarantee', models=MODELS,
        max_simulations=1296,max_wall_s=1200,sklearn=sklearn.__version__,
        prior_study_seen=True,accuracy_pass=None,device_commands=0,experiment_ready=False)
    p.write(out/'preregistered.json',dict(spec=spec,hashes=hashes))
    rows=read(SOURCE);X,Y,meta=training(rows)
    models={k:fit(X,Y,k) for k in MODELS}
    bounds=(X[:,:5].min(axis=0).tolist(),X[:,:5].max(axis=0).tolist())
    serialized=pickle.dumps(models,protocol=4)
    (out/'local_models.pkl').write_bytes(serialized)
    s.save_rows(out/'training_targets.csv',[dict(**m,**dict(zip(TARGETS,map(float,y)))) for m,y in zip(meta,Y)])
    index={(r['envelope'],int(r['seed']),r['scenario'],r['policy']):r for r in rows}
    validation=[];scores={};selected={}
    for mode in MODES:
        for name, ms in models.items():
            misses=0;deltas=[]
            for e in s.envelopes():
                if holdout(e):continue
                c=choose(ms,previous(e,91001),mode,bounds)
                for scenario in s.a.old.SCENARIOS:
                    r=index[e['id'],91001,scenario,c['policy']]
                    b=index[e['id'],91001,scenario,'EFT_REFERENCE']
                    misses+=r['planned']-r['deadline_met']
                    cost='energy_j' if mode=='energy' else 'peak_ap_c'
                    deltas.append(r[cost]-b[cost])
                    validation.append(dict(model=name,mode=mode,envelope=e['id'],scenario=scenario,
                        policy=c['policy'],reason=c['reason'],missed=r['planned']-r['deadline_met'],delta=r[cost]-b[cost]))
            scores[name,mode]=(misses,statistics.mean(deltas),name)
        selected[mode]=min(MODELS,key=lambda name:scores[name,mode])
    s.save_rows(out/'validation.csv',validation)
    decisions=[]
    for e in s.envelopes():
        for seed in spec['final_seeds']:
            for name, ms in models.items():
                for mode in MODES:
                    c=choose(ms,previous(e,seed),mode,bounds)
                    decisions.append(dict(envelope=e['id'],seed=seed,model=name,mode=mode,
                        withheld=holdout(e),**c))
    frozen=dict(selected=selected,bounds=bounds,model_sha256=hashlib.sha256(serialized).hexdigest(),
        train_rows=len(X),independent_synthetic_history_windows=36,selected_before_final=True,
        decisions=decisions,hashes=hashes)
    p.write(out/'freeze_before_final.json',frozen)
    model,case=p.inputs(p.BUNDLE);initial=case['initial'];results=[];count=0
    with (out/'local_ledgers.jsonl').open('w',encoding='utf8') as raw:
        for e in s.envelopes():
            for seed in spec['final_seeds']:
                ds=[d for d in decisions if d['envelope']==e['id'] and d['seed']==seed]
                policies=sorted(set(['EFT_REFERENCE','SPLIT_REFERENCE','CPU_REFERENCE']+[d['policy'] for d in ds]))
                for scenario in s.a.old.SCENARIOS:
                    for pol in policies:
                        if count>=spec['max_simulations'] or time.monotonic()-began>spec['max_wall_s']:
                            raise TimeoutError('fixed PC budget, no auto retry')
                        r,rr,_,_=s.simulate(model,initial,s.workload(e,seed),scenario,pol)
                        r={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
                        r.update(envelope=e['id'],seed=seed,scenario=scenario,policy=pol,withheld=holdout(e))
                        results.append(r);count+=1
                        raw.write(json.dumps(dict(meta=r,ledger=rr['ledger']))+'\n')
            s.save_rows(out/'results.csv',results);raw.flush()
            print(e['id'],count,round(time.monotonic()-began,1),flush=True)
    if hashes!={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}:
        raise RuntimeError('source/model changed')
    ix={(r['envelope'],r['seed'],r['scenario'],r['policy']):r for r in results}
    comparisons=[]
    for name in MODELS:
        for mode in MODES:
            for e in s.envelopes():
                xs=[]
                for seed in spec['final_seeds']:
                    d=next(d for d in decisions if (d['envelope'],d['seed'],d['model'],d['mode'])==(e['id'],seed,name,mode))
                    xs.extend(ix[e['id'],seed,scenario,d['policy']] for scenario in s.a.old.SCENARIOS)
                for ref in ('EFT_REFERENCE','SPLIT_REFERENCE','CPU_REFERENCE'):
                    bs=[ix[r['envelope'],r['seed'],r['scenario'],ref] for r in xs]
                    comparisons.append(dict(model=name,mode=mode,envelope=e['id'],withheld=holdout(e),
                        selected=selected[mode]==name,reference=ref,**group_result(xs,bs)))
    s.save_rows(out/'comparison.csv',comparisons)
    p.write(out/'summary.json',dict(simulations=count,elapsed_s=time.monotonic()-began,selected=selected,
        hashes_unchanged=True,device_commands=0,experiment_ready=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True)
    run(ap.parse_args().output)
