"""Registered round-robin learning-amount study, unchanged PPO v2 numerics."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import signal
import sys
import time
import traceback
import uuid
from tools import d1_queue_ppo_v2 as v
from tools import d1_rules_rl_common as common

IDENTITIES=[(variant,seed) for variant in ('HEAD','QUEUE') for seed in (11,23,37)]
MILESTONES=[128,256,512,1024]
VERSION='queue-ppo-learning-amount-campaign-v1'


def training_cases(n=8192):
    result=[]
    for i in range(n):
        if i<1024:seed=610700000+i//2
        elif i<4096:seed=610730000+(i-1024)//2
        else:seed=610750000+(i-4096)//2
        result.append((seed,('low','sustained')[i%2],v.q.old.SCENARIOS[(i//2+i%2)%3]))
    return result


def configuration():
    old=v.load_plan();train=training_cases()
    _,val,test=v.design.cases(old)
    return dict(version=VERSION,source_design=old,identities=IDENTITIES,
        batch=8,validation_period=32,milestones=MILESTONES,train=train,validation=val,test=test,
        first1024='exact original v2 ordered cases',additional='previously registered extension range, then fixed unused range; context follows cumulative episode index',
        validation_exposure='same old development validation24; not holdout',
        test_exposure='same previously seen v2 test192, retrospective common comparison; no new device/independent holdout claim',
        selection='unchanged v2 lexicographic key + earlier update; cumulative best never reset',
        extension=dict(window_updates=[416,448,480,512],
            improving='latest validation key at512 lexicographically improves vs416 OR new cumulative best after416',
            plateau='all four latest validation key vectors equal within 1e-9 AND no new best after416',
            uncertain='neither improving nor plateau, including fluctuation/regression',
            decision='any learner improving/uncertain -> extend all6 to8192 if counts/time allow; never use final test'),
        episode_caps=dict(per_learner=8192,total=49152),
        max_formal_environment=dict(training=49152,validation=4752,reference=8216,test=9216,total=71336),
        formal_to4096=dict(training=24576,validation=2448,reference=4120,test=6912,total=38056),
        fixtures_and_recovery_in_80000=True,learning_rate='constant0.0003; no budget-dependent schedule',
        normalization='advantage per optimizer batch only; no running statistics',
        no_environment_state_at_checkpoint='only after complete episodes and optimizer update/validation block; no pending environment',
        training_reserve_s=5400,device_commands=0,experiment_ready=False)


def register(folder=common.OUTPUT):
    folder=Path(folder);cfg=configuration()
    for name,sha in cfg['source_design']['frozen_files'].items():
        if common.digest(common.ROOT/name)!=sha:raise ValueError('frozen plant drift')
    original=v.design.cases(cfg['source_design'])[0]
    if cfg['train'][:1024]!=original:raise ValueError('original prefix changed')
    frozen,_=v.q.p.inputs(v.q.p.BUNDLE)
    certificates=[]
    # This is feasibility arithmetic, not policy environment execution. No
    # replacement of a failing registered input by a more favorable seed.
    for split,cases in [('train',cfg['train']),('validation',cfg['validation']),('test',cfg['test'])]:
        for seed,family,context in cases:
            tickets=v.q.old.workload(family,seed)
            cert=v.design.classify(tickets,frozen,context)
            if split!='test' and cert['status']!='feasible_witness':
                raise ValueError(f'registered main input blocked: {split}/{seed}/{family}/{context}')
            certificates.append(dict(split=split,case=[seed,family,context],
                input_sha256=v.design.digest_value([{k:q[k] for k in ('task','priority','arrival_ns','deadline_offset_ns')} for q in tickets]),
                status=cert['status'],witness_sha256=cert.get('witness_sha256')))
    hashes=[{r['input_sha256'] for r in certificates if r['split']==split} for split in ('train','validation','test')]
    if any(hashes[i]&hashes[j] for i in range(3) for j in range(i)):raise ValueError('physical input split collision')
    # The long-range training seeds were not previously used to generate policy
    # outcomes. Existing registrations are documented instead of falsely claimed
    # as fresh validation/test sets. Preserve the inventory of actual prior runs.
    sources={str(p.relative_to(common.ROOT)).replace('\\','/'):common.digest(p) for p in [
        Path(__file__),Path(common.__file__),Path(v.__file__),Path(v.q.__file__),Path(v.q.prev.__file__),
        Path(v.q.p.__file__),Path(v.q.old.__file__),Path(v.q.old.engine.__file__),v.design.PLAN]}
    common.atomic(folder/'rl_contract_before_run.json',dict(configuration=cfg,sources=sources,
        registered_utc=common.utc(),certificate_sha256=v.design.digest_value(certificates),
        runtime=v.durable.Session.runtime(),retraining=True,exact_old_extension=False))
    common.atomic(folder/'rl_input_manifest.json',certificates)
    return cfg


def save_pt(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('wb') as f:v.torch.save(payload,f);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def rng():return dict(python=random.getstate(),numpy=v.np.random.get_state(),torch=v.torch.get_rng_state())
def restore_rng(r):
    random.setstate(r['python']);v.np.random.set_state(r['numpy']);v.torch.set_rng_state(r['torch'])


def exact_equal(a,b):
    if isinstance(a,v.torch.Tensor):return isinstance(b,v.torch.Tensor) and v.torch.equal(a,b)
    if isinstance(a,v.np.ndarray):return isinstance(b,v.np.ndarray) and v.np.array_equal(a,b)
    if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(exact_equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return type(a)==type(b) and len(a)==len(b) and all(exact_equal(x,y) for x,y in zip(a,b))
    return a==b


def extension_decision(learners):
    decisions=[]
    for identity,learner in learners.items():
        keys=[learner['validation_history'][str(i)]['key'] for i in (416,448,480,512)]
        improving=tuple(keys[-1])<tuple(keys[0]) or learner['best_update']>416
        flat=all(all(abs(a-b)<=1e-9 for a,b in zip(keys[0],key)) for key in keys[1:])
        state='improving' if improving else 'plateau' if flat else 'uncertain'
        decisions.append(dict(identity=identity,state=state,keys=keys,best_update=learner['best_update']))
    return dict(extend=any(x['state']!='plateau' for x in decisions),learners=decisions,
        based_on='development validation only',final_test_opened=False,not_global_convergence=True)


class Session:
    def __init__(self,folder=common.OUTPUT,resume=False,fixture_config=None):
        self.folder=Path(folder);self.root=self.folder/'rl';self.fixture=fixture_config is not None
        self.budget=common.Budget(self.folder,fixture=self.fixture)
        self.registered=common.read(self.folder/'rl_contract_before_run.json')
        self.cfg=fixture_config or self.registered['configuration']
        self.lock=self.folder/'rl_owner.json';self.id=uuid.uuid4().hex;self.pause=False
        self.network=self.optimizer=None
        if v.q.LOCK.exists():raise ValueError('existing unrelated PPO owner; do not modify')
        if self.lock.exists():raise ValueError('active/unresolved campaign owner; no duplicate run')
        v.q.prev.seed_all(0)
        for name,sha in self.registered['sources'].items():
            if common.digest(common.ROOT/name)!=sha:raise ValueError('source changed before execution: '+name)
        if not self.fixture and self.registered['runtime']!=v.durable.Session.runtime():raise ValueError('runtime changed')
        self.frozen,case=v.q.p.inputs(v.q.p.BUNDLE)
        self.initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
        if resume:
            self.state=common.read(self.root/'state.json')
            if self.state['status'] not in ('paused','failed_io'):raise ValueError('not an eligible resume state')
        else:
            self.root.mkdir(exist_ok=False)
            self.state=dict(version=VERSION,status='running',phase='training',learners={},
                stage_index=0,round_index=0,learner_index=0,committed_units=0,
                milestones=[],evaluation_cursor=0,errors=[],run_id=self.id)
            common.atomic(self.root/'state.json',self.state)
        self.state['status']='running'
        self.refs={}
        for path in (self.root/'references').glob('*.json'):
            item=common.read(path);self.refs[tuple(item['case'])]=item['row']
        self.owner_pid=os.getpid()
        with self.lock.open('x',encoding='utf8') as f:
            json.dump(dict(pid=self.owner_pid,run_id=self.id,command=sys.argv,started_utc=common.utc()),f)

    def reference(self,case):
        case=tuple(case)
        if case not in self.refs:
            seed,family,context=case
            row,_,_,_=self.budget.execute('rl','reference',lambda:v.simulate(self.frozen,self.initial,
                v.q.old.workload(family,seed),context,'SHARED_EFT'),case=list(case),reserve=self.cfg.get('training_reserve_s',5400))
            common.atomic(self.root/'references'/f'{seed}_{family}_{context}.json',dict(case=list(case),row=row))
            self.refs[case]=row
        return self.refs[case]

    def metadata(self,identity,payload):
        return dict(update=payload['update'],episodes=payload['update']*self.cfg['batch'],
            file=payload['_file'],sha256=common.digest(self.root/payload['_file']),
            best_update=payload['best_update'],best=payload['best'],last_key=payload.get('last_key'),
            validation_history=payload['validation_history'])

    def load(self,identity):
        meta=self.state['learners'][identity]
        if common.digest(self.root/meta['file'])!=meta['sha256']:raise ValueError('learner checkpoint integrity')
        payload=v.torch.load(self.root/meta['file'],map_location='cpu',weights_only=False)
        self.network=v.q.ActorCritic();self.network.load_state_dict(payload['network'])
        self.optimizer=v.torch.optim.Adam(self.network.parameters(),lr=.0003,eps=1e-5)
        self.optimizer.load_state_dict(payload['optimizer']);restore_rng(payload['rng'])
        return payload

    def save(self,identity,payload,milestone=False):
        payload.update(network=copy.deepcopy(self.network.state_dict()),optimizer=copy.deepcopy(self.optimizer.state_dict()),rng=rng(),
            exact_episode_boundary=True,normalization='per_optimizer_batch_only',lr_schedule='constant')
        generation=payload.get('generation',0)+1;payload['generation']=generation
        name=f'learners/{identity}/state_{generation%2}.pt';payload['_file']=name
        save_pt(self.root/name,payload)
        metadata=self.metadata(identity,payload)
        if milestone:
            file=f'learners/{identity}/terminal_update{payload["update"]}.pt'
            if (self.root/file).exists():
                prior=v.torch.load(self.root/file,map_location='cpu',weights_only=False)
                keys=('identity','update','network','optimizer','rng','multipliers','best_actor','best_update','best')
                if not all(exact_equal(prior[k],payload[k]) for k in keys):raise ValueError('milestone overwrite forbidden')
            else:save_pt(self.root/file,payload)
            # Both latest and best contain full actor+critic tensors, but only
            # terminal/rolling archives include the exact optimizer/RNG state.
            latest=v.q.ActorCritic();latest.load_state_dict(payload['network'])
            best=v.q.ActorCritic();best.load_state_dict(payload['best_actor'])
            (self.root/'actors').mkdir(exist_ok=True)
            for kind,net in [('latest',latest),('best',best)]:
                actor_path=self.root/f'actors/{identity}_{payload["update"]}_{kind}.json'
                if actor_path.exists():
                    if common.read(actor_path)['sha256']!=v.q.prev.model_hash(net):raise ValueError('actor overwrite forbidden')
                else:v.q.save_actor(actor_path,net)
            restore_rng(payload['rng'])  # Serialization helpers must not consume the learner's future RNG.
            record=dict(identity=identity,variant=payload['variant'],seed=payload['seed'],update=payload['update'],
                episodes=payload['update']*self.cfg['batch'],best_update=payload['best_update'],latest_key=payload['last_key'],
                best_key=payload['best'],terminal_file=file,terminal_sha256=common.digest(self.root/file),
                latest_actor=f'actors/{identity}_{payload["update"]}_latest.json',
                best_actor=f'actors/{identity}_{payload["update"]}_best.json')
            self.state['milestones'].append(record)
        self.state['learners'][identity]=metadata
        self.state['committed_units']+=1
        common.atomic(self.root/'state.json',self.state)

    def validate(self,identity,payload):
        rows=[];refs=[];before=v.q.prev.model_hash(self.network)
        for case in self.cfg['validation']:
            seed,family,context=case
            row,_,_,_=self.budget.execute('rl','validation',lambda:v.simulate(self.frozen,self.initial,
                v.q.old.workload(family,seed),context,payload['variant'],self.network,True),
                reserve=self.cfg.get('training_reserve_s',5400),identity=identity,update=payload['update'],case=list(case))
            rows.append(row);refs.append(self.reference(case))
        if v.q.prev.model_hash(self.network)!=before:raise ValueError('validation changed learner')
        key=v.validation_key(rows,refs)
        if payload['best'] is None or key<tuple(payload['best']):
            payload.update(best=list(key),best_update=payload['update'],best_actor=copy.deepcopy(self.network.state_dict()))
        record=dict(identity=identity,variant=payload['variant'],seed=payload['seed'],update=payload['update'],
            episodes=payload['update']*self.cfg['batch'],key=list(key),best_key=payload['best'],best_update=payload['best_update'],
            mean_J=float(v.np.mean([r['energy_j'] for r in rows])),mean_peak=float(v.np.mean([r['peak_ap_c'] for r in rows])),
            mean_area=float(v.np.mean([r['thermal_degree_seconds'] for r in rows])),
            incomplete=sum(r['planned']-r['completed'] for r in rows),
            urgent_failures=sum(r['urgent_service_failure'] for r in rows),normal_failures=sum(r['normal_service_failure'] for r in rows),
            mean_urgent_p95=float(v.np.mean([r['urgent_p95_ms'] for r in rows])),mean_normal_response=float(v.np.mean([r['normal_mean_ms'] for r in rows])),
            latest_model_sha256=before)
        payload['last_key']=list(key);payload['validation_history'][str(payload['update'])]=record
        # Publish once with the checkpoint commit: a crash before commit may
        # repeat this block, but the separate environment ledger retains both.
        payload.setdefault('validation_records',[]).append(record)

    def initialize_learner(self,variant,seed):
        identity=f'{variant}_{seed}'
        v.q.prev.seed_all(seed);self.network=v.q.ActorCritic()
        self.optimizer=v.torch.optim.Adam(self.network.parameters(),lr=.0003,eps=1e-5)
        payload=dict(identity=identity,variant=variant,seed=seed,update=0,multipliers=v.np.array([10.,10.,1.,1.]),
            best=None,best_update=0,best_actor=None,validation_history={},training_records=[],validation_records=[],
            sources=self.registered['sources'],runtime=self.registered['runtime'])
        self.validate(identity,payload);self.save(identity,payload)

    def update(self,identity,payload):
        update=payload['update']+1;episodes=[];violations=[];metrics=[];waits=single=0
        reserve=self.cfg.get('training_reserve_s',5400)
        self.budget.check('rl',identity,reserve)
        for case in self.cfg['train'][(update-1)*self.cfg['batch']:update*self.cfg['batch']]:
            seed,family,context=case
            row,result,c,extra=self.budget.execute('rl','training',lambda:v.simulate(self.frozen,self.initial,
                v.q.old.workload(family,seed),context,payload['variant'],self.network,False),
                training_identity=identity,reserve=reserve,update=update,case=list(case))
            ref=self.reference(case);violations.append(v.costs(row,ref));metrics.append(row)
            episodes.append((c,v.rewards(c,result,extra,self.initial,self.frozen,row,ref)))
            waits+=c.action_counts[16];single+=sum(int(t['mask'].sum())==1 for t in c.rollout_data)
        if len(episodes)!=self.cfg['batch']:raise ValueError('incomplete registered rollout')
        packed=v.q.pack(episodes);stats=v.q.prev.optimize(self.network,self.optimizer,packed,payload['multipliers'])
        self.budget.optimized(identity,update,stats['minibatch_updates'])
        payload['multipliers']=v.np.clip(payload['multipliers']+5*v.np.mean(violations,axis=0),0.,100.)
        payload['update']=update
        record=dict(identity=identity,variant=payload['variant'],seed=payload['seed'],update=update,
            episodes=update*self.cfg['batch'],energy_J=float(v.np.mean([r['energy_j'] for r in metrics])),
            mean_costs=v.np.mean(violations,axis=0).tolist(),multipliers=payload['multipliers'].tolist(),
            rollout_transitions=len(packed['actions']),WAIT_actions=waits,single_legal_decisions=single,
            returns_abs_mean=packed['returns'].abs().mean(0).tolist(),advantages_std=packed['advantages'].std(0,unbiased=False).tolist(),**stats)
        payload['training_records'].append(record)
        if update%self.cfg['validation_period']==0:self.validate(identity,payload)
        self.save(identity,payload,milestone=update in self.cfg['milestones'])

    def progress(self,**extra):
        obj=dict(status=self.state['status'],phase=self.state['phase'],utc=common.utc(),
            learners={k:dict(update=m['update'],episodes=m['episodes'],best_update=m['best_update']) for k,m in self.state['learners'].items()},
            milestones=len(self.state['milestones']),**extra)
        common.atomic(self.root/'progress.json',obj);self.budget.publish(stage=self.state['phase'])
        print(json.dumps(obj,ensure_ascii=False),flush=True)

    def train(self,stop_after_units=None):
        identities=[f'{a}_{b}' for a,b in self.cfg['identities']]
        for variant,seed in self.cfg['identities']:
            if f'{variant}_{seed}' not in self.state['learners']:
                self.initialize_learner(variant,seed);self.progress(stage='initialized')
        targets=self.cfg['milestones']
        while self.state['stage_index']<len(targets):
            target=targets[self.state['stage_index']]
            for identity in identities:
                if self.state['learners'][identity]['update']>=target:continue
                payload=self.load(identity)
                end=min(target,payload['update']+self.cfg['validation_period'])
                while payload['update']<end:
                    self.update(identity,payload)
                    if self.pause or (stop_after_units is not None and self.state['committed_units']>=stop_after_units):
                        self.state['status']='paused';common.atomic(self.root/'state.json',self.state);return 'paused'
                self.progress(stage='validation_block_committed',current_identity=identity)
            if all(self.state['learners'][k]['update']>=target for k in identities):
                self.state['stage_index']+=1
                if not self.fixture and target==512:
                    decision=extension_decision(self.state['learners'])
                    common.atomic(self.root/'extension_decision_before_test.json',decision)
                    if not decision['extend']:self.state['stage_index']=len(targets)
                common.atomic(self.root/'state.json',self.state)
                self.progress(stage='common_milestone',episodes=target*self.cfg['batch'])
        self.state.update(phase='frozen',status='training_completed')
        common.atomic(self.root/'freeze_before_test.json',dict(milestones=self.state['milestones'],
            learners=self.state['learners'],final_test_opened=False,frozen_utc=common.utc(),
            contract_sha256=common.digest(self.folder/'rl_contract_before_run.json')))
        common.atomic(self.root/'state.json',self.state);return 'training_completed'

    def execute(self,stop_after_units=None):
        previous=signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT,lambda *_:setattr(self,'pause',True))
        try:
            status=self.train(stop_after_units)
            self.progress();return status
        except common.BudgetStop as e:
            self.state.update(status='budget_stopped',phase='partial_training',stop_reason=str(e))
            common.atomic(self.root/'state.json',self.state);self.progress();return 'budget_stopped'
        except BaseException as e:
            error=dict(type=type(e).__name__,message=str(e),stack=traceback.format_exc(),utc=common.utc())
            self.state['errors'].append(error)
            self.state['status']='failed_io' if isinstance(e,OSError) else 'failed_numeric_or_contract'
            common.atomic(self.root/'state.json',self.state);common.atomic(self.root/f'error_{len(self.state["errors"])}.json',error)
            self.progress();raise
        finally:
            signal.signal(signal.SIGINT,previous)
            if self.lock.exists() and common.read(self.lock).get('run_id')==self.id:self.lock.unlink()
            self.budget.publish(stage=self.state['status'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['Register','Run','Resume','Status'],default='Status')
    args=parser.parse_args()
    if args.action=='Register':register()
    elif args.action in ('Run','Resume'):
        print(Session(resume=args.action=='Resume').execute(),flush=True)
    else:
        print(json.dumps(common.read(common.OUTPUT/'rl/progress.json'),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
