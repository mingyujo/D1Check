"""Small matched C/E method pilot. Every environment start is durable and capped."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools import d1_cpu_gpu_method_candidates as candidates
from tools import d1_edd_ect_residual_learning_study as parent

nn=candidates.current;core=nn.core
ROOT=core.p.ROOT
BUNDLE=ROOT/'docs/results/cpu_gpu_method_01'
LOCAL=ROOT/'output/cpu_gpu_method_20261008_v1'
REFS=(core.BASE,'SHARED_EFT',core.ie.external.BAND)
FIXED=(core.ie.external.BAND,'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1','SHARED_EFT',core.BASE,candidates.ENERGY_RULE)


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return core.p.digest(path)
def write(path,value):return parent.write(path,value)
def utc():return datetime.now(timezone.utc).isoformat()


@contextmanager
def lock():
    import msvcrt
    with (LOCAL/'budget.lock').open('a+b') as f:
        if f.tell()==0:f.write(b'0');f.flush()
        f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)


def events():
    path=LOCAL/'executions.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []


def used():
    if parent.proto.consumption()['cumulative_starts']!=2916 or parent.consumption()['new_environment_starts']:
        raise RuntimeError('prior budget changed; preserve and register actual total')
    starts=[e for e in events() if e['event']=='start']
    return dict(previous=2916,new_starts=len(starts),cumulative=2916+len(starts),
        learning_episodes=sum(e['kind'] in ('train','learning_fixture') for e in starts),
        failed=sum(e['event']=='failed' for e in events()),device_commands=0)


def append(event,**values):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(dict(event=event,utc=utc(),**values),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def check():
    c=read(BUNDLE/'registration.json')
    if read(LOCAL/'registration.json')!=c:raise ValueError('registration drift')
    sources=dict(c['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(read(BUNDLE/'repair.json')['source_overrides'])
    for rel,h in sources.items():
        if sha(ROOT/rel)!=h:raise ValueError('source/input drift: '+rel)
    if sha(BUNDLE/'inputs.json')!=c['inputs_sha256']:raise ValueError('pilot input drift')
    return c


def begin(kind,identity):
    c=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(c['registered_utc'])).total_seconds()
    if elapsed>=c['wall_seconds']-300:raise TimeoutError('pilot save reserve')
    with lock():
        u=used()
        if u['new_starts']>=1024 or u['cumulative']>=20000:raise RuntimeError('environment ceiling')
        learning_cap=read(BUNDLE/'repair.json')['all_learning_cap'] if (BUNDLE/'repair.json').exists() else 224
        if kind in ('train','learning_fixture') and u['learning_episodes']>=learning_cap:raise RuntimeError('pilot learning ceiling')
        if any(e['event']=='start' and e['identity']==identity for e in events()):raise RuntimeError('charged item already started: '+identity)
        number=u['new_starts']+1;append('start',number=number,cumulative_number=u['cumulative']+1,kind=kind,identity=identity)
    return number,time.monotonic()+c['wall_seconds']-300-elapsed


def finish(n,kind,identity,row,artifact=None):
    with lock():append('completed',number=n,kind=kind,identity=identity,row=row,artifact=artifact)


def fail(n,kind,identity,error):
    with lock():append('failed',number=n,kind=kind,identity=identity,error=repr(error))


def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    LOCAL.mkdir(parents=True,exist_ok=True);BUNDLE.mkdir(parents=True,exist_ok=True)
    if (parent.LOCAL/'owner.json').exists() or (parent.proto.LOCAL/'owner.json').exists():raise RuntimeError('other active owner; do not change it')
    old_inputs=read(parent.BUNDLE/'inputs.json');old_reg=read(parent.BUNDLE/'registration.json')
    cases=dict(train=old_inputs['train'][:32],validation=old_inputs['validation'][:12],final=old_inputs['final'][24:48],fixtures=old_inputs['train'][:8])
    assert len(cases['train'])==32 and len(cases['final'])==24
    hashes=[{parent.ticket_hash(c) for c in cases[group]} for group in ('train','validation','final')]
    assert not any(hashes[i]&hashes[j] for i in range(3) for j in range(i))
    assert used()['new_starts']==0
    sources=dict(old_reg['source_hashes'])
    for rel in ('tools/d1_cpu_gpu_method_candidates.py','tools/d1_cpu_gpu_method_study.py',
        'tools/test_d1_cpu_gpu_method_candidates.py','docs/results/edd_ect_residual_design_01/design_contract.json',
        'docs/results/external_rules_02/inputs.json'):
        sources[rel]=sha(ROOT/rel)
    write(BUNDLE/'inputs.json',cases)
    c=dict(version='cpu-gpu-method-pilot-v1',registered_utc=utc(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),parent_registration_sha256=sha(parent.BUNDLE/'registration.json'),
        inherited_seed_audit=old_reg['seed_audit'],seed_assignment='reserved but never executed prior registration subsets, disjoint hashes',
        variants=['C','E'],learning_seeds=[11,23,37],episodes_per_variant_seed=32,updates_per_variant_seed=4,
        matched_learning_total=192,learning_fixture_total=32,all_learning_cap=224,environment_cap=1024,
        wall_seconds=7200,save_reserve_seconds=300,previous_environment_starts=2916,
        fixed_policies=list(FIXED),validation_conditions=12,final_conditions=24,
        model_sha256=core.p.MODEL_SHA,initial_sha256=core.p.INITIAL_SHA,device_commands=0,experiment_ready=False,
        C=dict(id='EDD_ECT_SLACK_RESIDUAL_PPO_V1',objective='AP first; J/service/P95 nonworsening costs',mask='physical support plus arrived-queue three-context predicted SLA/completion'),
        E=dict(id=candidates.ENERGY_RL,objective_version='ENERGY_AP_NONWORSE_V1',objective='whole-window J reduction; model AP/service/P95 nonworsening costs',mask='physical support, actual lane ownership, slot presence and cumulative cooling credit only'),
        comparison_scope='same native masked PPO network/optimizer/budget; E changes mask and objective, not an algorithm comparison',
        no_tuning=True,no_extra_algorithms=True,initial_heat='one unchanged empirically initialized preload; no synthetic hot/cold range',
        selection='full denominator, primary absolute deadlines, no P95/service or AP regression versus independent strong references, then energy; all three RL seeds reported',
        old_2032_episode_study_not_started=True,representative=dict(case_index=0,family='queue',context='mean'),
        source_information='public arrived queue, phases and timestamps, calibrated forecast parameters; model AP/h are estimates, not simulator ground-truth sensors')
    write(BUNDLE/'registration.json',c);write(LOCAL/'registration.json',c)
    return c


def simulate(case,policy,network=None,variant=None,deadline=None,no_wait=False,no_heat=False):
    frozen,_=core.p.inputs(core.p.BUNDLE);initial=read(parent.proto.INPUT)['initial'];tickets=core.ie.old.workload(case['family'],case['seed'])
    if policy not in (candidates.ENERGY_RULE,'C','E'):
        if policy==core.BASE:result,c=core.ie.simulate(frozen,initial,tickets,case['context'],policy)
        elif policy.startswith('TRITON_'):
            from tools import d1_triton_rules as triton
            result,c=triton.simulate(frozen,initial,tickets,case['context'],policy)
        else:result,c=core.ie.external.simulate(frozen,initial,tickets,case['context'],policy)
        parent.audit.audit(result,tickets);row,curves=parent.audit.metrics(result,c,initial,frozen)
        row.update(case,policy=policy);return row,(result,curves),c
    controller=(candidates.CurrentController(frozen,initial,network) if policy=='C' else
        candidates.Controller(frozen,initial,network,deterministic=variant=='evaluation',no_wait=no_wait,no_heat=no_heat))
    if policy=='C':controller.deterministic=variant=='evaluation'
    controller.execution_deadline=deadline
    profile=core.p.profile(frozen,case['context'])
    vectors=dict(cells={key:[dict(source_request_id='common_context_'+case['context'],durations_ns=v) for _ in range(4)] for key,v in profile.items()})
    result=core.ie.old.engine.simulate(dict(protocol=core.p.VERSION,cells=core.p.profile(frozen)),vectors,tickets,
        policy=controller.policy,settings=core.ie.external.settings(),seed=201,decision_provider=controller)
    parent.audit.audit(result,tickets);row,curves=parent.audit.metrics(result,controller,initial,frozen)
    row.update(case,policy=policy,projection_calls=controller.projection_calls,projection_seconds=controller.projection_seconds)
    return row,(result,curves),controller


def reference(case,policy):
    key=hashlib.sha256(json.dumps([case,policy,read(BUNDLE/'registration.json')['sources']],sort_keys=True).encode()).hexdigest()
    path=LOCAL/'cache'/f'{key}.json';claim=LOCAL/'cache'/f'{key}.owner'
    path.parent.mkdir(exist_ok=True)
    while True:
        with lock():
            if path.exists():
                item=read(path);done=[e for e in events() if e['event']=='completed' and e['identity']=='reference/'+key]
                if done:
                    if len(done)!=1 or done[0]['row']!=item['row']:raise ValueError('sealed reference mismatch')
                    return item['row']
            if not claim.exists():
                with claim.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid()),f)
                mine=True
            else:mine=False
        if mine:break
        time.sleep(.1)
    n=None;identity='reference/'+key
    try:
        n,deadline=begin('reference',identity);row,_,_=simulate(case,policy,deadline=deadline)
        if row['completed']!=row['planned']:raise ValueError('incomplete reference')
        write(path,dict(row=row));finish(n,'reference',identity,row)
        return row
    except BaseException as error:
        if n is not None:fail(n,'reference',identity,error)
        raise
    finally:
        if claim.exists() and read(claim)['pid']==os.getpid():claim.unlink()


def episode(case,network,variant,identity,kind='train'):
    refs=[reference(case,p) for p in REFS]
    n,deadline=begin(kind,identity);began=time.perf_counter()
    try:
        row,_,controller=simulate(case,variant,network,deadline=deadline)
        data,costs,valid=(nn.target_data(controller,row,refs) if variant=='C' else candidates.targets(controller,row,refs))
        row.update(host_wall_s=time.perf_counter()-began,informative=sum(s['informative'] for s in data),costs=costs.tolist(),cost_valid=valid.tolist())
        return dict(data=data,costs=costs,valid=valid,row=row,number=n,identity=identity,kind=kind)
    except BaseException as error:fail(n,kind,identity,error);raise


def archive(path,net,opt,state):
    state['consumption']=used();state['registration_sha256']=sha(BUNDLE/'registration.json')
    return nn.archive(path,net,opt,state)


def fixtures():
    if (LOCAL/'fixtures_complete.json').exists():return
    repair=read(BUNDLE/'repair.json') if (BUNDLE/'repair.json').exists() else {}
    if used()['learning_episodes'] and not repair:raise RuntimeError('partial fixture is not free to repeat')
    cases=read(BUNDLE/'inputs.json')['fixtures'];checks=[]
    for variant in ('C','E'):
        initial=LOCAL/f'fixture_{variant}_initial.pt'
        if initial.exists():network,opt,state=nn.restore(initial)
        else:
            nn.seed_all(11);network=nn.ActorCritic();opt=nn.torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5)
            state=dict(variant=variant,batch=[],cursor=0,multipliers=[1.,10.,10.,10.,10.]);archive(initial,network,opt,state)
        for arm in ('continuous','resumed'):
            partial=LOCAL/f'fixture_{variant}_{arm}.pt'
            if partial.exists():network,opt,state=nn.restore(partial)
            elif arm=='resumed':network,opt,state=nn.restore(initial)
            for i,case in enumerate(cases):
                if i<state['cursor']:continue
                identity=f'fixture/{variant}/{arm}/{i}'
                if identity==repair.get('failed_identity'):identity=repair['charged_retry_identity']
                ep=episode(case,network,variant,identity,'learning_fixture')
                state['batch'].append(ep);state['cursor']=i+1
                path=LOCAL/f'fixture_{variant}_{arm}.pt';archive(path,network,opt,state)
                finish(ep['number'],ep['kind'],ep['identity'],ep['row'])
                if arm=='resumed' and i==3:network,opt,state=nn.restore(path)
            stats=nn.update(network,opt,state['batch'],state['multipliers']);state['batch']=[]
            archive(LOCAL/f'fixture_{variant}_{arm}_terminal.pt',network,opt,state)
            value=(nn.model_hash(network),state['multipliers'].copy(),nn.torch.get_rng_state().clone())
            if arm=='continuous':expected=value
            else:
                assert value[0]==expected[0] and value[1]==expected[1] and nn.torch.equal(value[2],expected[2]),'actual resume mismatch'
            print('fixture '+variant+' '+arm+' '+json.dumps(stats),flush=True)
        checks.append(dict(variant=variant,status='PASS',model_sha256=value[0]))
    write(LOCAL/'fixtures_complete.json',dict(checks=checks,learning_starts=32,optimizer_and_rng_match=True))
    write(BUNDLE/'actual_resume_verification.json',read(LOCAL/'fixtures_complete.json'))


def train(variant,seed):
    check();nn.seed_all(seed);network=nn.ActorCritic();opt=nn.torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5)
    state=dict(variant=variant,seed=seed,cursor=0,updates=0,batch=[],multipliers=[1.,10.,10.,10.,10.],rows=[])
    path=LOCAL/f'{variant}_seed{seed}_state.pt'
    if path.exists():network,opt,state=nn.restore(path)
    if path.exists() and state['registration_sha256']!=sha(BUNDLE/'registration.json'):raise ValueError('checkpoint binding')
    cases=read(BUNDLE/'inputs.json')['train']
    while state['cursor']<32:
        ep=episode(cases[state['cursor']],network,variant,f'train/{variant}/{seed}/{state["cursor"]}')
        state['batch'].append(ep);state['rows'].append(ep['row']);state['cursor']+=1
        archive(path,network,opt,state);finish(ep['number'],ep['kind'],ep['identity'],ep['row'])
        if len(state['batch'])==8:
            stats=nn.update(network,opt,state['batch'],state['multipliers']);state['batch']=[];state['updates']+=1
            archive(path,network,opt,state)
            print(f'{variant} seed{seed} episodes={state["cursor"]} '+json.dumps(stats),flush=True)
    archive(LOCAL/f'{variant}_seed{seed}_terminal.pt',network,opt,state)
    write(LOCAL/f'{variant}_seed{seed}_done.json',{k:v for k,v in state.items() if k!='batch'})


def evaluate(split,variant=None,seed=None):
    cases=read(BUNDLE/'inputs.json')[split];policies=FIXED if variant is None else [variant]
    network=None
    if variant is not None:network,_,_=nn.restore(LOCAL/f'{variant}_seed{seed}_terminal.pt')
    for i,case in enumerate(cases):
        for policy in policies:
            label=policy if variant is None else f'{variant}_seed{seed}'
            identity=f'{split}/{label}/{i}';path=LOCAL/'items'/f'{split}_{label}_{i:03d}.json.gz'
            if path.exists():continue
            n,deadline=begin(split,identity);began=time.perf_counter()
            try:
                row,extra,c=simulate(case,policy,network,'evaluation',deadline)
                row.update(policy=label,split=split,host_wall_s=time.perf_counter()-began)
                item=dict(row=row,ledger=extra[0]['ledger'] if extra else None,curves=extra[1] if extra else None)
                path.parent.mkdir(exist_ok=True)
                with path.open('xb') as f:f.write(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0))
                finish(n,split,identity,row,sha(path))
            except BaseException as error:fail(n,split,identity,error);raise
    print(split+' '+str(variant)+' '+str(seed)+' done',flush=True)


def jobs(commands):
    for start in range(0,len(commands),3):
        children=[]
        for args in commands[start:start+3]:
            name='_'.join(args);log=(LOCAL/(name+'.log')).open('ab')
            proc=subprocess.Popen([sys.executable,'-B','-m','tools.d1_cpu_gpu_method_study',*args],cwd=ROOT,
                stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            children.append((proc,log,name))
        while any(p.poll() is None for p,_,_ in children):
            print(json.dumps(used()),flush=True);time.sleep(10)
        for p,log,name in children:
            log.close()
            if p.returncode:raise RuntimeError('owned worker failed: '+name)


def run():
    prepare();owner=LOCAL/'owner.json'
    with owner.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid(),utc=utc()),f)
    try:
        fixtures()
        jobs([['train','--variant',v,'--seed',str(seed)] for v in ('C','E') for seed in (11,23,37)])
        for split in ('validation','final'):
            jobs([[split]]+[[split,'--variant',v,'--seed',str(seed)] for v in ('C','E') for seed in (11,23,37)])
        check();write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),
            matched_training=192,fixture_learning=32,validation_rows=132,final_rows=264,device_commands=0,experiment_ready=False))
        return used()
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run','train','validation','final','status'))
    parser.add_argument('--variant',choices=('C','E'));parser.add_argument('--seed',type=int)
    args=parser.parse_args()
    if args.action=='train':train(args.variant,args.seed)
    elif args.action in ('validation','final'):evaluate(args.action,args.variant,args.seed)
    else:
        result=run() if args.action=='run' else prepare() if args.action=='prepare' else used()
        print(json.dumps({k:v for k,v in result.items() if k not in ('sources','inherited_seed_audit')},indent=2))
