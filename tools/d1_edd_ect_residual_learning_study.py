"""Budgeted three-learner study; closed references, checkpoint resume, no devices."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from tools import d1_edd_ect_residual_ppo as nn
from tools import d1_edd_ect_residual_study as proto
from tools import d1_external_rules_study as audit

core=nn.core
ROOT=core.p.ROOT
BUNDLE=ROOT/'docs/results/edd_ect_residual_learning_01'
LOCAL=ROOT/'output/edd_ect_residual_learning_20261008_v1'
REFS=(core.BASE,'SHARED_EFT',core.ie.external.BAND)
FIXED=REFS+('TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1','RESERVED_THERMAL_REQUEST_V1_NUMERIC_R2',core.PRIOR,core.GREEDY)


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):return core.p.digest(path)
def write(path,obj):return proto.write(path,obj)


@contextmanager
def lock():
    import msvcrt
    path=LOCAL/'budget.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        if path.stat().st_size==0:f.write(b'0');f.flush()
        f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)


def events():
    path=LOCAL/'executions.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []


def consumption():
    if proto.consumption()['cumulative_starts']!=2916:
        raise RuntimeError('historical environment consumption changed; do not reset or ignore it')
    starts=[e for e in events() if e['event']=='start']
    kinds={k:sum(e['kind']==k for e in starts) for k in ('train_fixture','main_training','training_reference','validation_rl','validation_fixed','final','recovery')}
    return dict(prior_environment_starts=2916,new_environment_starts=len(starts),cumulative_environment_starts=2916+len(starts),
        learning_episodes=kinds['train_fixture']+kinds['main_training'],by_kind=kinds,
        environment_ceiling=20000,learning_ceiling=6144,device_commands=0)


def append(event,**values):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as stream:
        stream.write(json.dumps(dict(event=event,utc=utc(),**values),allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def elapsed(spec):return (datetime.now(timezone.utc)-datetime.fromisoformat(spec['registered_utc'])).total_seconds()


def check_sources(spec):
    for rel,h in spec['source_hashes'].items():
        if sha(ROOT/rel)!=h:raise ValueError('active source drift: '+rel)
    if sha(BUNDLE/'inputs.json')!=spec['inputs_sha256']:raise ValueError('input drift')


def begin(kind,identity,stage='training'):
    spec=read(BUNDLE/'registration.json')
    check_sources(spec)
    limit=spec['training_phase_seconds'] if stage=='training' else spec['wall_seconds']-300
    if elapsed(spec)>=limit or (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('stop boundary before next environment')
    with lock():
        used=consumption()
        caps=dict(train_fixture=48,main_training=6096,training_reference=6240,validation_rl=288,validation_fixed=168,final=3264,recovery=256)
        if used['by_kind'][kind]>=caps[kind] or used['cumulative_environment_starts']>=20000:raise RuntimeError('registered kind/whole budget exhausted')
        if kind in ('train_fixture','main_training') and used['learning_episodes']>=6144:raise RuntimeError('all learning cap')
        old=[e for e in events() if e['event']=='start' and e['identity']==identity]
        if old:raise RuntimeError('already started environment, no free replay: '+identity)
        number=used['new_environment_starts']+1
        append('start',number=number,cumulative_number=used['cumulative_environment_starts']+1,kind=kind,identity=identity)
    return number,time.monotonic()+limit-elapsed(spec)


def finish(number,identity,row,kind):
    with lock():append('completed',number=number,identity=identity,kind=kind,row=row)


def failed(number,identity,kind,error):
    with lock():append('failed',number=number,identity=identity,kind=kind,error=repr(error))


def ticket_hash(case):
    tickets=core.ie.old.workload(case['family'],case['seed'])
    return hashlib.sha256(json.dumps(tickets,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def collision_audit(cases):
    candidates={c['seed'] for group in cases.values() for c in group};hits=[];checked=0
    pattern=re.compile(r'"(?:seed|trace_seed|arrival_seed)"\s*:\s*(\d+)|\[\s*(7110\d+)\s*,')
    for folder in (ROOT/'docs/results',ROOT/'output'):
        for path in folder.rglob('*.json'):
            if 'edd_ect_residual_learning_20261008_v1' in str(path) or 'edd_ect_residual_learning_01' in str(path):continue
            if path.stat().st_size>20_000_000:continue
            text=path.read_text(encoding='utf8',errors='replace');checked+=1
            if any(int(a or b) in candidates for a,b in pattern.findall(text)):hits.append(path.relative_to(ROOT).as_posix())
    # Headers distinguish actual trace seeds from neural initialization seeds.
    import csv
    for path in (ROOT/'docs/results').rglob('*.csv'):
        with path.open(encoding='utf8',newline='') as f:
            reader=csv.DictReader(f);fields=[k for k in reader.fieldnames or [] if k in ('seed','trace_seed','arrival_seed')]
            if not fields:continue
            for row in reader:
                if any(row[k].isdigit() and int(row[k]) in candidates for k in fields):hits.append(path.relative_to(ROOT).as_posix());break
    import gzip
    compressed=0
    binary_pattern=re.compile(rb'"(?:seed|trace_seed|arrival_seed)"\s*:\s*(\d+)|\[\s*(7110\d+)\s*,')
    for path in (ROOT/'output').rglob('*.gz'):
        # Full streaming metadata scan, without materializing neural weights.
        tail=b''
        with gzip.open(path,'rb') as f:
            while True:
                chunk=f.read(262144)
                if not chunk:break
                block=tail+chunk
                if any(int(a or b) in candidates for a,b in binary_pattern.findall(block)):
                    hits.append(path.relative_to(ROOT).as_posix());break
                tail=block[-128:]
        compressed+=1
        if compressed%5000==0:print(f'seed audit compressed histories {compressed}',flush=True)
    if hits:raise ValueError('registered trace seed collision: '+str(hits[:10]))
    return dict(json_metadata_files=checked,compressed_histories=compressed,trace_seed_collisions=0,
        scope='accessible repository/output registered JSON and CSV metadata plus full streamed gzip history seed metadata; binary tensor checkpoints governed by their registered manifests; external unregistered histories unknown',
        generated_input_hashes={str(c['seed'])+'/'+c['family']:ticket_hash(c) for group in cases.values() for c in group})


def prepare(hours=6):
    if (BUNDLE/'registration.json').exists():
        spec=read(BUNDLE/'registration.json');check_sources(spec);return spec
    if hours not in (2,6,16):raise ValueError('bounded PC wall setting')
    proto.check()
    for rel in ('output/reserved_thermal_20261008_v1/owner.json','output/ie_dispatch_20261008_v1/owner.json'):
        if (ROOT/rel).exists():raise RuntimeError('other experiment owner is active; preserve and stop')
    summary=read(proto.BUNDLE/'summary.json')
    if summary['gates']['B']!='PASS' or summary['gates']['C']!='PASS':raise ValueError('prototype B/C gate')
    LOCAL.mkdir(parents=True,exist_ok=True);BUNDLE.mkdir(parents=True,exist_ok=True)
    if (proto.LOCAL/'owner.json').exists():raise RuntimeError('prototype still running')
    train=[dict(seed=711000001+i,family=family,context=core.CONTEXTS[(i+j)%3]) for i in range(508) for j,family in enumerate(core.ie.old.FAMILIES)]
    validation=[dict(seed=711010001+i,family=family,context=c) for i in range(2) for family in core.ie.old.FAMILIES for c in core.CONTEXTS]
    final=[dict(seed=711020001+i,family=family,context=c) for i in range(16) for family in core.ie.old.FAMILIES for c in core.CONTEXTS]
    cases=dict(train=train,validation=validation,final=final,fixtures=train[:8])
    inventory=collision_audit(cases)
    hashes=[{ticket_hash(c) for c in group} for group in (train,validation,final)]
    if any(hashes[i]&hashes[j] for i in range(3) for j in range(i)):raise ValueError('input split hash collision')
    write(BUNDLE/'inputs.json',cases)
    from tools import d1_triton_rules as triton
    from tools import d1_reserved_thermal_numeric_study as numeric
    sources=dict(read(proto.BUNDLE/'registration.json')['source_hashes'])
    sources['tools/d1_edd_ect_residual_study.py']=sha(ROOT/'tools/d1_edd_ect_residual_study.py')
    for module in (nn,sys.modules[__name__],triton,numeric.r2,numeric.r2.rule):
        rel=Path(module.__file__).relative_to(ROOT).as_posix();sources[rel]=sha(ROOT/rel)
    for rel in ('tools/test_d1_edd_ect_residual_ppo.py','tools/d1_edd_ect_residual_final.py'):
        sources[rel]=sha(ROOT/rel)
    spec=dict(version='edd-ect-residual-learning-v1',registered_utc=utc(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        source_hashes=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),
        prototype_summary_sha256=sha(proto.BUNDLE/'summary.json'),seed_audit=inventory,
        prior_consumption=proto.consumption(),base_environment_starts=2916,whole_environment_cap=20000,
        main_per_seed=2032,main_total=6096,learning_fixture_cap=48,all_learning_cap=6144,
        learning_seeds=[11,23,37],checkpoints=[512,1024,1536,2032],reference_policies=list(REFS),
        fixed_validation_policies=list(FIXED),final_fixed_policies=read(ROOT/'docs/results/edd_ect_residual_design_01/design_contract.json')['selection_proposal']['final_policies'][:14],
        validation_conditions=24,final_conditions=192,wall_seconds=hours*3600,
        training_phase_seconds=max(3600,hours*3600-3600),save_reserve_seconds=300,
        time_setting='user preference requested asynchronously; default recommended six hours if unanswered; no old clocks reset',
        workers=3,host_logical_cpus=os.cpu_count(),torch_threads_per_worker=1,
        model_sha256=core.p.MODEL_SHA,initial_sha256=core.p.INITIAL_SHA,
        training_allowed_after_actual_resume_fixture=True,experiment_ready=False,device_commands=0,
        reference_cache_rule='same trace hash/context/realization/model/initial/policy source; complete receipt required; no lost-cache auto recomputation',
        no_eligible='report all seeds; no replacement checkpoint; final learned performance null',
        stop_rule='current episode then archive partial batch; time timeout inside projection records a failed charged episode and no replay',
        expected_parameters_source='frozen edd-ect-residual-design-v1, no tuning',
        controller_overhead='PC measured; physical differential overhead remains unmeasured zero-assumption model')
    write(BUNDLE/'registration.json',spec);write(LOCAL/'registration.json',spec)
    return spec


def fixed_result(case,policy,deadline):
    frozen,_=core.p.inputs(core.p.BUNDLE);initial=read(proto.INPUT)['initial'];tickets=core.ie.old.workload(case['family'],case['seed'])
    if policy in (core.BASE,core.PRIOR,core.GREEDY):result,c=core.simulate(frozen,initial,tickets,case['context'],policy,deadline=deadline)
    elif policy.startswith('TRITON_'):
        from tools import d1_triton_rules as triton
        result,c=triton.simulate(frozen,initial,tickets,case['context'],policy)
    elif policy=='RESERVED_THERMAL_REQUEST_V1_NUMERIC_R2':
        from tools import d1_reserved_thermal_numeric_study as numeric
        _,result,c,_=numeric.r2.simulate(frozen,initial,tickets,case['context'],lambda:None)
    else:result,c=core.ie.external.simulate(frozen,initial,tickets,case['context'],policy)
    audit.audit(result,tickets);row,_=audit.metrics(result,c,initial,frozen)
    row.update(case,policy=policy);return row


def cached_fixed(case,policy,kind='training_reference',stage='training'):
    binding=dict(trace_sha256=ticket_hash(case),context=case['context'],model=core.p.MODEL_SHA,initial=core.p.INITIAL_SHA,policy=policy,realization_seed=201,
        sources=read(BUNDLE/'registration.json')['source_hashes'])
    key=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
    folder=LOCAL/'reference_cache';folder.mkdir(exist_ok=True);path=folder/(key+'.json');claim=folder/(key+'.owner')
    while True:
        with lock():
            if path.exists():
                item=read(path)
                if item['binding']!=binding or item['status']!='completed':raise ValueError('reference cache drift')
                completed=[e for e in events() if e['event']=='completed' and e['identity']=='reference/'+key]
                if completed:
                    if len(completed)!=1 or completed[0]['row']!=item['row']:raise ValueError('reference completed receipt drift')
                    return item['row']
                if not claim.exists():raise ValueError('reference cache has no completed receipt')
            if not claim.exists():
                with claim.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid()),f)
                mine=True
            else:mine=False
        if mine:break
        spec=read(BUNDLE/'registration.json')
        if elapsed(spec)>=spec['training_phase_seconds'] and stage=='training':raise TimeoutError('reference wait reached time cap')
        if (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('stop requested')
        time.sleep(.1)
    identity='reference/'+key;number=None
    try:
        number,deadline=begin(kind,identity,stage)
        row=fixed_result(case,policy,deadline)
        if row['completed']!=row['planned']:raise ValueError('reference unfinished; do not invent whole costs')
        write(path,dict(status='completed',binding=binding,row=row))
        finish(number,identity,row,kind)
        return row
    except BaseException as error:
        if number is not None:failed(number,identity,kind,error)
        raise
    finally:
        if claim.exists() and read(claim)['pid']==os.getpid():claim.unlink()


def learning_episode(case,network,identity,kind):
    references=[cached_fixed(case,p) for p in REFS]
    number,deadline=begin(kind,identity);began=time.perf_counter()
    try:
        frozen,_=core.p.inputs(core.p.BUNDLE);initial=read(proto.INPUT)['initial'];tickets=core.ie.old.workload(case['family'],case['seed'])
        c=nn.Controller(frozen,initial,network);c.execution_deadline=deadline
        profile=core.p.profile(frozen,case['context'])
        vectors=dict(cells={k:[dict(source_request_id='common_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
        result=core.ie.old.engine.simulate(dict(protocol=core.p.VERSION,cells=core.p.profile(frozen)),vectors,tickets,
            policy=c.policy,settings=core.ie.external.settings(),seed=201,decision_provider=c)
        audit.audit(result,tickets);row,_=audit.metrics(result,c,initial,frozen)
        data,costs,valid=nn.target_data(c,row,references)
        row.update(case,policy='EDD_ECT_SLACK_RESIDUAL_PPO_V1',host_wall_s=time.perf_counter()-began,
            projection_calls=c.projection_calls,projection_seconds=c.projection_seconds,informative=sum(s['informative'] for s in data),
            costs=costs.tolist(),cost_channel_valid=valid.tolist())
        episode=dict(data=data,costs=costs,valid=valid,row=row,number=number,identity=identity,kind=kind)
        return episode
    except BaseException as error:failed(number,identity,kind,error);raise


def new_state(seed):
    return dict(seed=seed,cursor=0,updates=0,batch=[],multipliers=[1.,10.,10.,10.,10.],selected=None,
                validations=[],sources_sha256=sha(BUNDLE/'registration.json'),reference_cache_root='reference_cache',
                consumption_at_save=consumption(),status='initialized')


def save(path,net,opt,state):
    state['consumption_at_save']=consumption()
    return nn.archive(path,net,opt,state)


def fixtures():
    ready=LOCAL/'fixtures_complete.json'
    if ready.exists():return read(ready)
    spec=read(BUNDLE/'registration.json');cases=read(BUNDLE/'inputs.json')['fixtures']
    if consumption()['by_kind']['train_fixture']:
        raise RuntimeError('partial actual learning fixture; review instead of repeating charged episodes')
    results=[]
    for seed in spec['learning_seeds']:
        nn.seed_all(seed);network=nn.ActorCritic();optimizer=nn.torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5);state=new_state(seed)
        initial=LOCAL/f'fixture_seed{seed}_initial.pt';save(initial,network,optimizer,state)
        for arm in ('continuous','resumed'):
            if arm=='resumed':network,optimizer,state=nn.restore(initial)
            for index,case in enumerate(cases):
                episode=learning_episode(case,network,f'fixture/{seed}/{arm}/{index}','train_fixture')
                state['batch'].append(episode);state['cursor']=index+1
                path=LOCAL/f'fixture_seed{seed}_{arm}.pt'
                save(path,network,optimizer,state)
                finish(episode['number'],episode['identity'],episode['row'],'train_fixture')
                if arm=='resumed' and index==3:network,optimizer,state=nn.restore(path)
            update=nn.update(network,optimizer,state['batch'],state['multipliers']);state['batch']=[];state['updates']=1
            terminal=LOCAL/f'fixture_seed{seed}_{arm}_terminal.pt';save(terminal,network,optimizer,state)
            if arm=='continuous':expected=(nn.model_hash(network),state['multipliers'].copy(),nn.torch.get_rng_state().clone())
            else:
                if expected[0]!=nn.model_hash(network) or expected[1]!=state['multipliers'] or not nn.torch.equal(expected[2],nn.torch.get_rng_state()):
                    raise ValueError('actual episode/Adam/partial batch/RNG resume mismatch')
            print(f'fixture seed{seed} {arm} eight episodes {update}',flush=True)
        results.append(dict(seed=seed,status='PASS',continuous_vs_resumed_hash=expected[0]))
    receipt=dict(status='PASS',learning_fixture_starts=48,learners=results,consumption=consumption(),utc=utc(),
        preserved_actor_critic_adam_rng_partial_batch=True)
    write(ready,receipt);write(BUNDLE/'actual_resume_verification.json',receipt)
    return receipt


def validate(network,state):
    from tools import d1_edd_ect_residual_report as report
    spec=read(BUNDLE/'registration.json');cases=read(BUNDLE/'inputs.json')['validation'];rows=[];pairgroups=[]
    for index,case in enumerate(cases):
        refs=[cached_fixed(case,p,'validation_fixed') for p in FIXED]
        identity=f'validation/{state["seed"]}/{state["cursor"]}/{index}'
        path=LOCAL/'validation'/f'{state["seed"]}_{state["cursor"]}_{index}.json'
        if path.exists():item=read(path);row=item['row']
        else:
            number,deadline=begin('validation_rl',identity)
            try:
                frozen,_=core.p.inputs(core.p.BUNDLE);initial=read(proto.INPUT)['initial'];tickets=core.ie.old.workload(case['family'],case['seed'])
                c=nn.Controller(frozen,initial,network,deterministic=True);c.execution_deadline=deadline
                profile=core.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='common_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
                result=core.ie.old.engine.simulate(dict(protocol=core.p.VERSION,cells=core.p.profile(frozen)),vectors,tickets,
                    policy=c.policy,settings=core.ie.external.settings(),seed=201,decision_provider=c)
                audit.audit(result,tickets);row,_=audit.metrics(result,c,initial,frozen);row.update(case,policy=f'RL_seed{state["seed"]}')
                write(path,dict(row=row,actor_sha256=nn.model_hash(network),identity=identity));finish(number,identity,row,'validation_rl')
            except BaseException as error:failed(number,identity,'validation_rl',error);raise
        pairs=[report.compare(row,r) for r in refs[:4]]
        rows.append(row);pairgroups.append(pairs)
    all_good=all(all(p['nonworse'] for p in group) for group in pairgroups)
    primary_indices=[i for i,c in enumerate(cases) if c['family'] in ('low','sustained')]
    absolute=all(all(p['all_deadlines_met'] for p in pairgroups[i]) for i in primary_indices)
    gain=any(report.gain_signal(rows[i],[cached_fixed(cases[i],p,'validation_fixed') for p in REFS],True) for i in primary_indices)
    delta=[g[0]['delta_peak_ap_c'] for g in pairgroups];dj=[g[0]['delta_energy_j'] for g in pairgroups]
    key=(float(nn.np.mean(delta)),max(delta),float(nn.np.mean(dj)),state['cursor']) if all(d is not None for d in delta+dj) else None
    result=dict(episodes=state['cursor'],seed=state['seed'],eligible=bool(all_good and absolute and gain),key=key,
        validation_rows=len(rows),nonworse_conditions=sum(all(p['nonworse'] for p in g) for g in pairgroups))
    state['validations'].append(result)
    if result['eligible'] and key is not None and (state['selected'] is None or tuple(key)<tuple(state['selected']['key'])):
        state['selected']=result
        save(LOCAL/f'selected_seed{state["seed"]}.pt',network,NoneOptimizerProxy(network),state)
    print('validation '+json.dumps(result),flush=True)
    return result


class NoneOptimizerProxy:
    # Selected actor is independent of final training archive and not resumable.
    def __init__(self,network):self.network=network
    def state_dict(self):return {'selected_actor_only':True}


def worker(seed):
    spec=read(BUNDLE/'registration.json');check_sources(spec)
    if read(LOCAL/'fixtures_complete.json')['status']!='PASS':raise ValueError('actual resume fixture gate')
    nn.seed_all(seed)
    path=LOCAL/f'train_seed{seed}_state.pt'
    if path.exists():network,optimizer,state=nn.restore(path)
    else:
        nn.seed_all(seed);network=nn.ActorCritic();optimizer=nn.torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5);state=new_state(seed)
    cases=read(BUNDLE/'inputs.json')['train']
    try:
        while state['cursor']<2032:
            if len(state['batch'])==8:
                stats=nn.update(network,optimizer,state['batch'],state['multipliers']);state['batch']=[];state['updates']+=1
                save(path,network,optimizer,state)
                print(f'seed{seed} episodes={state["cursor"]} '+json.dumps(stats),flush=True)
            if state['cursor'] in spec['checkpoints'] and not any(v['episodes']==state['cursor'] for v in state['validations']):
                validate(network,state);save(path,network,optimizer,state)
            episode=learning_episode(cases[state['cursor']],network,f'train/{seed}/{state["cursor"]}','main_training')
            state['batch'].append(episode);state['cursor']+=1;state['status']='training'
            save(path,network,optimizer,state)
            finish(episode['number'],episode['identity'],episode['row'],'main_training')
        if state['batch']:nn.update(network,optimizer,state['batch'],state['multipliers']);state['batch']=[];state['updates']+=1
        if not any(v['episodes']==2032 for v in state['validations']):validate(network,state)
        state['status']='completed'
    except TimeoutError as error:state['status']='budget_stopped';state['stop_reason']=str(error)
    except BaseException as error:
        state['status']='failed';state['error']=repr(error);raise
    finally:
        save(path,network,optimizer,state)
        terminal=LOCAL/f'terminal_seed{seed}_{state["cursor"]}.pt'
        save(terminal,network,optimizer,state)
        write(LOCAL/f'worker_seed{seed}.json',{k:v for k,v in state.items() if k not in ('batch',)})


def run(hours=6):
    spec=prepare(hours);owner=LOCAL/'owner.json'
    with owner.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid(),utc=utc()),f)
    children=[]
    try:
        fixtures()
        for seed in spec['learning_seeds']:
            log=(LOCAL/f'worker_seed{seed}.log').open('ab')
            process=subprocess.Popen([sys.executable,'-B','-m','tools.d1_edd_ect_residual_learning_study','worker','--seed',str(seed)],
                cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            children.append((seed,process,log))
        last=''
        while any(p.poll() is None for _,p,_ in children):
            used=consumption();message=json.dumps(used)
            if message!=last:print(message,flush=True);last=message
            time.sleep(5)
        for seed,process,log in children:
            log.close()
            if process.returncode!=0:raise RuntimeError('learner process failed: '+str(seed))
        from tools import d1_edd_ect_residual_final as final
        final.run()
        return consumption()
    finally:
        # Never terminate unrelated processes; owned workers save on shared stop.
        if any(p.poll() is None for _,p,_ in children):
            write(LOCAL/'STOP_REQUEST.json',dict(reason='parent exit',utc=utc()))
            for _,process,log in children:process.wait();log.close()
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run','worker','status','stop'))
    parser.add_argument('--hours',type=int,default=6);parser.add_argument('--seed',type=int)
    args=parser.parse_args()
    if args.action=='worker':worker(args.seed)
    elif args.action=='stop':write(LOCAL/'STOP_REQUEST.json',dict(utc=utc(),reason='explicit user stop'))
    else:
        result=run(args.hours) if args.action=='run' else prepare(args.hours) if args.action=='prepare' else consumption()
        print(json.dumps({k:v for k,v in result.items() if k not in ('source_hashes','seed_audit')},indent=2))
