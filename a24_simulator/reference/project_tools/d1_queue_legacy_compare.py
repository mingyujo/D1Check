"""Preregister frozen legacy weights before new confirmation; PC paired replay only."""
import argparse,json,sys,copy,time
from pathlib import Path
import torch
from tools import d1_queue_direct_study as study
from tools import d1_queue_legacy_budget as budget
from tools import d1_service_joint_rl as future
from tools import d1_atc_direct_ppo as head
from tools import d1_atc_direct_policy as oldpolicy

ROOT=study.ROOT
SEEDS=(11,23,37)
ROLES=tuple(f'{kind}_{seed}' for kind in ('Future64','HeadDirect') for seed in SEEDS)

def register(folder,main,old):
    # Explicit iterator, because confirmation must not have started when registering.
    if any((main/'rows').glob('confirmation_*.json')):raise ValueError('comparison contract must precede confirmation')
    oldfreeze=study.budget.read(old/'freeze.json')
    oldreg=study.budget.read(old/'registration.json')
    models={}
    for seed in SEEDS:
        path=folder/f'seed{seed}_ep64.pt'
        d=torch.load(path,map_location='cpu',weights_only=False)
        if d['schema_id']!=future.SCHEMA or d['accepted_episodes']!=64:raise ValueError('legacy future schema')
        models[f'Future64_{seed}']=dict(path=path.resolve().as_posix(),sha256=budget.digest(path),episodes=64,schema=future.SCHEMA)
        ep=oldfreeze['best_validation_epochs'][str(seed)];path=old/'checkpoints'/f'seed{seed}_ep{ep}.pt'
        d=torch.load(path,map_location='cpu',weights_only=False)
        if d['schema']!=oldpolicy.SCHEMA:raise ValueError('old head schema')
        models[f'HeadDirect_{seed}']=dict(path=path.resolve().as_posix(),sha256=budget.digest(path),episodes=ep,schema=oldpolicy.SCHEMA)
    # This folder already contains only extracted frozen model files, so use a child for fresh budget.
    run=folder/'run';b=budget.Budget.register(run,dict(learning=0,scope='frozen historical auxiliary comparators; all3 weights, no bestseed from new final',main_registration_sha256=study.budget.digest(main/'registration.json')))
    src=study.sources();src[Path(__file__).resolve().relative_to(ROOT).as_posix()]=budget.digest(__file__)
    budget.write(run/'registration.json',dict(task=budget.TASK,caps=budget.CAPS,models=models,sources=src,main_registration_sha256=study.budget.digest(main/'registration.json'),inputs=study.budget.read(main/'inputs.json')['confirmation'],realization_seed=study.REALIZATION,
        frozen_before_new_confirmation=True,adoption_reference=False,training=0,model_fit=0,device_runs=0,expected=288,
        past_training='Future64 original64 (latest512 weights unavailable here); HeadDirect original devselected32/64. No relabel as newly-trained512.',old_registration_sha256=study.budget.digest(old/'registration.json')))
    return dict(status='registered',models=6,confirmation_cases=48,native=288,learning=0)

class LegacyProxy(study.Proxy):
    @property
    def on_public_event(self):
        # A historical controller without this hook keeps the engine's original
        # no-journal path. Its original observe(lanes) input is unchanged.
        if getattr(self.controller,"on_public_event",None) is None:return None
        return super().on_public_event


def run(folder):
    runroot=folder/'run';reg=budget.read(runroot/'registration.json');b=budget.Budget(runroot)
    repair=budget.read(runroot/'source_repairs.json') if (runroot/'source_repairs.json').exists() else None
    if repair and repair['registration_sha256']!=budget.digest(runroot/'registration.json'):raise ValueError('repair lineage mismatch')
    for name,sha in reg['sources'].items():
        if repair and name in repair['effective_sources']:
            r=repair['effective_sources'][name]
            if r['original_sha256']!=sha or repair['scope']!='legacy_event_hook_adapter_only':raise ValueError('repair scope')
            sha=r['effective_sha256']
        if budget.digest(ROOT/name)!=sha:raise ValueError('auxiliary source changed '+name)
    networks={}
    for role,m in reg['models'].items():
        if budget.digest(m['path'])!=m['sha256']:raise ValueError('legacy weights mutated')
        d=torch.load(m['path'],map_location='cpu',weights_only=False)
        net=future.r.c.ActorCritic() if role.startswith('Future') else head.ActorCritic()
        net.load_state_dict(d['network']);net.eval();networks[role]=net
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    f,i,_=study.a.hybrid.load();initial=i['initial']
    with b.session(),study.patch.object(study,"Proxy",LegacyProxy):
        for case in reg['inputs']:
            for role in ROLES:
                identity=f'confirmation_{case["condition"]:02d}_{role}'
                if role.startswith('Future'):
                    c=future.Controller(f,initial,networks[role],True)
                    # Original thermal forecast is used only by this explicitly labelled legacy baseline.
                    with study.a.hybrid.forecast_scope():
                        study.collected(runroot,b,identity,'confirmation',dict(case,role=role),c)
                else:
                    c=oldpolicy.Controller(f,initial,networks[role],True)
                    study.collected(runroot,b,identity,'confirmation',dict(case,role=role),c)
    budget.write(runroot/'completion.json',dict(status='completed',rows=len(study.rows(runroot,'confirmation_')),consumption=b.used(),weights_unchanged=True,learning=0))
    return dict(status='completed',consumption=b.used())

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','run'));p.add_argument('--folder',type=Path,required=True);p.add_argument('--main',type=Path);p.add_argument('--old',type=Path)
    x=p.parse_args();r=register(x.folder,x.main,x.old) if x.command=='register' else run(x.folder)
    print(json.dumps(study.serial(r),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
