"""Explicit objective / declared workload envelope lookup, development-only fit.

Designed after the first condition study was observed. Fresh-seed confirmation
is a second PC block, not a new device experiment or unseen model family.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
import time
from tools import d1_scheduler_conditions as s
from tools.d1_scheduler_conditions_report import read,group_result,COSTS
p=s.p
MODES=('energy','thermal')


def fit(rows):
    dev=[r for r in rows if r['stage']=='development'];out={}
    if not dev:raise ValueError('development missing')
    for e in s.envelopes():
        candidates=[]
        for pol in s.POLICIES:
            xs=[r for r in dev if r['envelope']==e['id'] and r['policy']==pol]
            if len(xs)!=6:raise ValueError('development envelope incomplete')
            if all(x['completed']==x['planned']==x['deadline_met'] and all(x[k] is not None for k in COSTS) for x in xs):
                candidates.append(dict(policy=pol,**{k:statistics.mean(x[k] for x in xs) for k in COSTS}))
        out[e['id']]={mode:(min(candidates,key=lambda x:(x['energy_j'],x['peak_ap_c'],x['policy']))['policy'] if mode=='energy' else
                           min(candidates,key=lambda x:(x['peak_ap_c'],x['thermal_degree_seconds'],x['energy_j'],x['policy']))['policy'])
                     if candidates else None for mode in MODES}
    return out


def choose(selection,envelope,mode):
    if mode not in MODES or envelope not in selection:raise ValueError('unregistered objective/envelope')
    pol=selection[envelope][mode]
    if pol is None:raise ValueError('no development-feasible policy; do not promise service')
    return pol


def run(source,output):
    source=Path(source).resolve();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    rows=read(source/'results.csv');selection=fit(rows)
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial']
    paths=[Path(__file__),Path(s.__file__),Path(p.__file__),source/'results.csv',p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']
    hashes={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in paths}
    spec=dict(id='condition-selector-fresh-pc-v1',designed_after_first_test_seen=True,
        fitting_rows='development 81001/81002 only',selection=selection,seeds=[102001,102002,102003],
        selection_input='declared envelope and objective before arrivals; no future realized trace',
        objectives=dict(energy='min mean J, then peak AP',thermal='min mean peak AP, then AP area, then J'),
        feasibility='all six development contexts meet every deadline; not a guarantee for future input',
        references=['EFT_REFERENCE','SPLIT_REFERENCE'],max_unique_simulations=972,max_wall_s=900,
        no_further_fit=True,accuracy_pass=None,device_commands=0,experiment_ready=False)
    p.write(out/'freeze_before_confirmation.json',dict(spec=spec,hashes=hashes,utc=datetime.now(timezone.utc).isoformat()))
    began=time.monotonic();resultrows=[];curves=[];runs=0
    with (out/'local_ledgers.jsonl').open('w',encoding='utf8') as raw:
        for e in s.envelopes():
            policies=sorted(set(['EFT_REFERENCE','SPLIT_REFERENCE']+[x for x in selection[e['id']].values() if x]))
            for seed in spec['seeds']:
                tickets=s.workload(e,seed)
                for scenario in s.a.old.SCENARIOS:
                    for pol in policies:
                        if time.monotonic()-began>spec['max_wall_s']:raise TimeoutError('no automatic new run')
                        row,rr,_,_=s.simulate(frozen,initial,tickets,scenario,pol);runs+=1
                        row={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
                        row.update(envelope=e['id'],seed=seed,scenario=scenario,policy=pol)
                        resultrows.append(row);raw.write(json.dumps(dict(meta=row,ledger=rr['ledger']))+'\n')
                        if e['id']=='g0.45_c0.75_b4' and seed==102001 and scenario=='mean':
                            seg,costs,end=p.account(rr,initial,frozen)
                            curves.append(dict(policy=pol,energy_path=costs['energy_path'],ap_path=costs['ap_path'],segments=seg))
            s.save_rows(out/'results.csv',resultrows);raw.flush()
            print(e['id'],runs,round(time.monotonic()-began,2),flush=True)
    assert hashes=={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in paths}
    index={(r['envelope'],r['seed'],r['scenario'],r['policy']):r for r in resultrows};summaries=[]
    for e in s.envelopes():
        for mode in MODES:
            pol=selection[e['id']][mode]
            if pol is None:
                summaries.append(dict(envelope=e['id'],mode=mode,policy=None,status='no_development_feasible_policy'))
                continue
            xs=[r for r in resultrows if r['envelope']==e['id'] and r['policy']==pol]
            for ref in spec['references']:
                bs=[index[r['envelope'],r['seed'],r['scenario'],ref] for r in xs]
                summaries.append(dict(envelope=e['id'],mode=mode,policy=pol,reference=ref,status='evaluated',**group_result(xs,bs)))
    s.save_rows(out/'selector_confirmation.csv',summaries)
    p.write(out/'representative_curves.json',curves)
    p.write(out/'summary.json',dict(runs=runs,elapsed_s=time.monotonic()-began,rows=len(resultrows),
        supported_envelopes=sum(v['energy'] is not None for v in selection.values()),device_commands=0,
        validation='fresh synthetic seeds, same frozen model and distribution, no physical confirmation',experiment_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.source,args.output)
