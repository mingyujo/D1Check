"""Post-main fixed-weight diagnosis; separate ledger, no training/devices."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import torch
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_rl_run as r

ROOT=c.ROOT
PRIOR=ROOT/'output/list_candidate_rl_train_main_20261010_v1'
PUBLIC=ROOT/'docs/results/list_candidate_rl_train_main_01'
POLICY='LIST_PPO128_POSTENCODE_NOWAIT_DIAGNOSTIC_V1'

class EncodedNoWait(c.Controller):
    """Keep original bank/state/candidates/physical mask; restrict selection."""
    def choose(self,encoded,actions,queue):
        before=[encoded[k].tobytes() for k in ('state','candidates','mask')]
        with torch.no_grad():
            distribution,values=self.network(torch.from_numpy(encoded['state'])[None],
                torch.from_numpy(encoded['candidates'])[None],torch.from_numpy(encoded['mask'])[None])
        permitted=[i for i,a in enumerate(actions) if a['wait']==0.]
        if not permitted:raise ValueError('L0 immediate candidate missing from physical bank')
        scores=distribution.logits[0].numpy()
        maximum=max(scores[i] for i in permitted)
        base=encoded['base']
        selected=base if base in permitted and scores[base]==maximum else min(permitted,key=lambda i:(-scores[i],i))
        encoded['old_value']=values[0].numpy().copy()
        encoded['logprob']=float(distribution.log_prob(torch.tensor([selected])).item())
        encoded['diagnostic_selection_mask']=[i in permitted for i in range(len(actions))]
        encoded['probability_scope']='original physical distribution; not restricted-distribution max probability'
        if before!=[encoded[k].tobytes() for k in ('state','candidates','mask')]:raise ValueError('diagnostic changed actor input')
        return selected

class Budget(r.Budget):
    def __init__(self,output,phase):
        self.output=Path(output);self.reg=r.read(self.output/'registration.json');self.phase=phase
        self.path=self.output/'execution.jsonl';self.rows=[]
        for line in self.path.read_text(encoding='utf-8').splitlines() if self.path.exists() else []:
            row=json.loads(line)
            if 'event' not in row:self.rows.append(row)
            else:self.rows[row['number']-1].update(row)
        self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+self.reg['active_seconds']-300
        self.work_guard()
    def consumption(self):
        return dict(new_environment_starts=len(self.rows),design_environment_starts=1228+len(self.rows),
          cumulative_environment_starts=7745+len(self.rows),new_learning_starts=0,cumulative_learning_starts=1045,
          failed=sum(r['status']=='failed' for r in self.rows),device_commands=0)
    def guard(self,learning=False):
        if learning:raise ValueError('post-main development does not authorize training')
        self.work_guard()
        if len(self.rows)>=308:raise TimeoutError('remaining design environment cap308')
        if self.phase=='nowait' and sum(row['phase']=='nowait' for row in self.rows)>=72:raise TimeoutError('NoWait diagnosis cap72')

def register(output):
    progress=r.read(PRIOR/'progress.json')['consumption']
    if progress['cumulative_environment_starts']!=7745 or progress['cumulative_learning_starts']!=1045:
        raise ValueError('prior consumption changed; never reset counters')
    if (PRIOR/'owner.lock').exists():raise ValueError('prior learning still owned')
    output.mkdir(parents=True,exist_ok=False)
    old=r.read(PRIOR/'registration_effective.json')
    registry=dict(task='LIST-CANDIDATE-RL-DEVELOP-07',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      registered_utc=datetime.now(timezone.utc).isoformat(),active_seconds=7200,save_reserve_seconds=300,
      previous_cumulative_environment_starts=7745,previous_cumulative_learning_starts=1045,
      previous_design_environment_starts=1228,remaining_design_environment_cap=308,remaining_design_learning_cap=12,
      new_learning_starts=0,device_commands=0,source_sha256=r.closure_sources(),
      development=old['development'],learning_seeds=[11,23,37],fixed_terminal_episodes=128,
      input_sha256=old['input_sha256']['development'],selection_intervention='postencoding positive-wait candidate restriction; mixed action families also excluded',
      original_bank_state_candidates_physical_mask_preserved=True,physics_or_future_service_guarantee=False,
      baseline_rows_reused=72,baseline_native_calls=0,normalizations_hyperparameters_model_SLA_unchanged=True,
      inherited_prior_clock=False,new_clock_registered=True,
      checkpoint_sha256={str(seed):r.sha(PRIOR/f'checkpoints/seed{seed}_terminal128.pt') for seed in (11,23,37)},
      phase_expected=dict(nowait=72),conditional_sampling_not_default=True,
      conditional_followup='if evidence supports a service-aware same-bank selector, freeze one candidate on development; fresh confirmation needs separate before-result registration within308',
      original_experiment_ready=False)
    registry['source_sha256']['tools/d1_list_candidate_rl_develop.py']=r.sha(Path(__file__))
    r.write(output/'registration.json',registry)
    return registry

def network(seed,registration):
    path=PRIOR/f'checkpoints/seed{seed}_terminal128.pt'
    if r.sha(path)!=registration['checkpoint_sha256'][str(seed)]:raise ValueError('terminal actor changed')
    payload=torch.load(path,map_location='cpu',weights_only=False)
    if payload['accepted_episodes']!=128:raise ValueError('not terminal128')
    model=c.ActorCritic();model.load_state_dict(payload['network']);model.eval()
    return model

def nowait(budget):
    frozen,initial,_=r.inputs();rows=[]
    for seed in (11,23,37):
        model=network(seed,budget.reg);before=r.training.state_digest(model.state_dict())
        for i,q in enumerate(budget.reg['development']):
            controller=EncodedNoWait(frozen,initial,c.PPO,network=model,deterministic=True,feature_variant='head2+C_next')
            item=budget.call(f'nowait_s{seed}_{i:03d}',controller,q)
            if controller.deferred_seconds or any(s['action']['wait'] for s in controller.snapshots):raise ValueError('WAIT restriction failed')
            rows.append(dict(condition=i,case=q,policy=POLICY,seed=seed,training_episodes=128,**item['row'],control=item.get('control')))
        if before!=r.training.state_digest(model.state_dict()):raise ValueError('diagnosis updated weights')
    result=dict(status='completed',scope='fixed-actor development diagnosis, not new-policy independent confirmation',
      rows=rows,consumption=budget.consumption(),original_tensor_encoding_retained=True,new_learning_starts=0,optimizer_steps=0)
    r.write(budget.output/'nowait_results.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--phase',required=True,choices=('register','nowait'))
    args=p.parse_args();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if args.phase=='register':print(json.dumps(register(args.output),ensure_ascii=False,indent=2));return
    if (args.output/'nowait_results.json').exists():raise FileExistsError('completed diagnosis preserved; do not repeat consumed IDs')
    owner=args.output/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget(args.output,args.phase);result=nowait(budget)
        print(json.dumps(dict(status=result['status'],rows=len(result['rows']),consumption=result['consumption']),indent=2))
    except BaseException as error:
        r.write(args.output/'nowait_error.json',dict(status='stopped_error',error=repr(error),consumption=budget.consumption() if budget else None))
        raise
    finally:
        if owner.exists() and owner.read_text(encoding='ascii')==str(os.getpid()):owner.unlink()

if __name__=='__main__':main()
