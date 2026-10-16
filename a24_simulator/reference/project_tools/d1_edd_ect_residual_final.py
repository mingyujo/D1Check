"""Fresh frozen final cases. Eligibility is fixed before opening final outcomes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools import d1_edd_ect_residual_learning_study as s


def run_one(case,index,policy,selected=None):
    path=s.LOCAL/'final'/f'{index:03d}_{policy}.json'
    if path.exists():return s.read(path)
    identity=f'final/{index}/{policy}'
    number,deadline=s.begin('final',identity,'final')
    try:
        if selected is None:row=s.fixed_result(case,policy,deadline)
        else:
            payload=s.nn.torch.load(selected,map_location='cpu',weights_only=False)
            network=s.nn.ActorCritic();network.load_state_dict(payload['network']);network.eval()
            if s.nn.model_hash(network)!=payload['network_sha256']:raise ValueError('selected actor drift')
            frozen,_=s.core.p.inputs(s.core.p.BUNDLE);initial=s.read(s.proto.INPUT)['initial'];tickets=s.core.ie.old.workload(case['family'],case['seed'])
            controller=s.nn.Controller(frozen,initial,network,deterministic=True);controller.execution_deadline=deadline
            actual=s.core.p.profile(frozen,case['context'])
            vectors=dict(cells={k:[dict(source_request_id='common_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
            result=s.core.ie.old.engine.simulate(dict(protocol=s.core.p.VERSION,cells=s.core.p.profile(frozen)),vectors,tickets,
                policy=controller.policy,settings=s.core.ie.external.settings(),seed=201,decision_provider=controller)
            s.audit.audit(result,tickets);row,_=s.audit.metrics(result,controller,initial,frozen);row.update(case,policy=policy)
        s.write(path,row);s.finish(number,identity,row,'final');return row
    except BaseException as error:s.failed(number,identity,'final',error);raise


def worker(part):
    spec=s.read(s.BUNDLE/'registration.json');s.check_sources(spec);s.nn.seed_all(900+part)
    selection=s.read(s.BUNDLE/'final_selection.json')
    cases=s.read(s.BUNDLE/'inputs.json')['final']
    try:
        for i,case in enumerate(cases):
            if i%3!=part:continue
            for policy in selection['policies']:
                run_one(case,i,policy,selection['selected_paths'].get(policy))
            print(f'final {part}: condition {i}',flush=True)
    except TimeoutError as error:s.write(s.LOCAL/f'final_worker{part}.json',dict(status='budget_stopped',reason=str(error)))


def run():
    spec=s.read(s.BUNDLE/'registration.json');selected={};states=[]
    for seed in spec['learning_seeds']:
        state=s.read(s.LOCAL/f'worker_seed{seed}.json');states.append(state)
        if state['selected'] is not None:
            policy=f'EDD_ECT_SLACK_RESIDUAL_PPO_V1_SEED{seed}'
            selected[policy]=str(s.LOCAL/f'selected_seed{seed}.pt')
    selection=dict(utc=s.utc(),policies=spec['final_fixed_policies']+list(selected),
        selected_paths=selected,learner_results=[dict(seed=t['seed'],episodes=t['cursor'],status=t['status'],selected=t['selected']) for t in states],
        no_selection_is_not_a_final_actor=True)
    # Local absolute checkpoint paths never go into the shared selection manifest.
    s.write(s.LOCAL/'final_selection_private.json',selection)
    public=dict(selection,selected_paths={p:Path(path).relative_to(s.ROOT).as_posix() for p,path in selected.items()})
    s.write(s.BUNDLE/'final_selection.json',public)
    children=[]
    for part in range(3):
        log=(s.LOCAL/f'final_worker{part}.log').open('ab')
        process=subprocess.Popen([sys.executable,'-B','-m','tools.d1_edd_ect_residual_final','worker','--part',str(part)],
            cwd=s.ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        children.append((process,log))
    while any(p.poll() is None for p,_ in children):
        count=len(list((s.LOCAL/'final').glob('*.json')))
        print(f'final rows {count}/{192*len(public["policies"])}',flush=True);time.sleep(10)
    for process,log in children:
        log.close()
        if process.returncode!=0:raise RuntimeError('final worker failed; preserve partial results')
    rows=[s.read(path) for path in sorted((s.LOCAL/'final').glob('*.json'))]
    if rows:s.audit.csv_write(s.BUNDLE/'final_results.csv',rows)
    receipt=dict(utc=s.utc(),status='completed' if len(rows)==192*len(public['policies']) else 'budget_stopped',
        expected_rows=192*len(public['policies']),actual_rows=len(rows),consumption=s.consumption(),
        selection_sha256=s.sha(s.BUNDLE/'final_selection.json'),training_episodes=s.consumption()['learning_episodes'],
        device_commands=0,experiment_ready=False)
    s.write(s.BUNDLE/'completion.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('run','worker'));parser.add_argument('--part',type=int)
    args=parser.parse_args()
    if args.action=='worker':worker(args.part)
    else:print(json.dumps(run(),indent=2))
