"""Registered four-candidate development pilot, durable accounting and resume."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import copy,csv,gzip,hashlib,json,os,random,re,subprocess,sys,time
from pathlib import Path
from tools import d1_ie_candidates_v2 as x
from tools import d1_cpu_gpu_method_study as previous

ROOT=x.core.p.ROOT;BUNDLE=ROOT/'docs/results/ie_candidates_v2';LOCAL=ROOT/'output/ie_candidates_20261008_v2'
FIXED=(x.core.ie.external.BAND,'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1','SHARED_EFT',x.core.BASE,x.LIST,x.ROLL)
REFS=FIXED[:2];ALGORITHMS=('PPO','DDQN');SEEDS=(11,23,37)
read=previous.read;write=previous.write;sha=previous.sha;utc=previous.utc


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
    return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines()] if path.exists() else []


def used():
    old=previous.used()
    if old['cumulative']!=3633 or old['learning_episodes']!=225:raise RuntimeError('historical consumption changed, re-register actual totals')
    entries=events();starts=[r for r in entries if r['event']=='start']
    return dict(previous_environment_starts=3633,new_environment_starts=len(starts),cumulative_environment_starts=3633+len(starts),
        previous_learning_starts=225,new_learning_starts=sum(r['kind'] in ('train','learning_fixture') for r in starts),
        cumulative_learning_starts=225+sum(r['kind'] in ('train','learning_fixture') for r in starts),
        failed=sum(r['event']=='failed' for r in entries),device_commands=0)


def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def check():
    c=read(BUNDLE/'registration.json')
    if read(LOCAL/'registration.json')!=c:raise ValueError('registration drift')
    sources=dict(c['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(read(BUNDLE/'repair.json')['source_overrides'])
    for path,digest in sources.items():
        if sha(ROOT/path)!=digest:raise ValueError('source drift: '+path)
    if sha(BUNDLE/'inputs.json')!=c['inputs_sha256']:raise ValueError('input drift')
    return c


def begin(kind,identity):
    c=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(c['registered_utc'])).total_seconds()
    if elapsed>=c['wall_seconds']-300 or (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('registered save/stop boundary')
    with lock():
        u=used()
        if u['new_environment_starts']>=1536 or u['cumulative_environment_starts']>=20000:raise RuntimeError('environment ceiling')
        if kind in ('train','learning_fixture') and (u['new_learning_starts']>=420 or u['cumulative_learning_starts']>=6144):raise RuntimeError('learning ceiling')
        if any(e['identity']==identity and e['event']=='start' for e in events()):raise RuntimeError('charged identity already started, preserve failure')
        n=u['new_environment_starts']+1;append('start',number=n,kind=kind,identity=identity,cumulative_number=3633+n)
    return n,time.monotonic()+c['wall_seconds']-300-elapsed


def seed_audit(cases):
    desired={c['seed'] for group in cases.values() for c in group};hits=[];plain=compressed=0
    pattern=re.compile(r'"(?:seed|trace_seed|arrival_seed)"\s*:\s*(\d+)|\[\s*(8120\d+)\s*,')
    for folder in (ROOT/'docs/results',ROOT/'output'):
        for path in folder.rglob('*.json'):
            if BUNDLE in path.parents or LOCAL in path.parents or 'ie_scheduler_v2_deps' in path.parts:continue
            if path.stat().st_size>20_000_000:continue
            values=pattern.findall(path.read_text(encoding='utf8',errors='replace'));plain+=1
            if any(int(a or b) in desired for a,b in values):hits.append(path.relative_to(ROOT).as_posix())
    for path in (ROOT/'docs/results').rglob('*.csv'):
        if BUNDLE in path.parents:continue
        with path.open(encoding='utf8',newline='') as f:
            reader=csv.DictReader(f);fields=[k for k in reader.fieldnames or [] if k in ('seed','trace_seed','arrival_seed')]
            if not fields:continue
            if any(any((r.get(k) or '').isdigit() and int(r[k]) in desired for k in fields) for r in reader):hits.append(path.relative_to(ROOT).as_posix())
    binary=re.compile(pattern.pattern.encode())
    for path in (ROOT/'output').rglob('*.gz'):
        if LOCAL in path.parents or 'ie_scheduler_v2_deps' in path.parts:continue
        tail=b''
        with gzip.open(path,'rb') as f:
            while True:
                chunk=f.read(262144)
                if not chunk:break
                block=tail+chunk
                if b'8120' in block and any(int(a or b) in desired for a,b in binary.findall(block)):hits.append(path.relative_to(ROOT).as_posix());break
                tail=block[-128:]
        compressed+=1
    if hits:raise ValueError('trace seed collision: '+repr(hits[:8]))
    return dict(json_files=plain,fully_streamed_gzip_files=compressed,trace_seed_collisions=0,
        scope='repository metadata JSON <=20 MB, shared CSV seed columns, full streamed gzip metadata; external unregistered histories unknown')


def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    if (previous.LOCAL/'owner.json').exists():raise RuntimeError('preserve existing active learner')
    def split(first,count,all_contexts):
        raw=[dict(seed=first+i,family=f,context=ctx) for i in range(count) for f in ('low','queue','burst','sustained') for ctx in (x.core.CONTEXTS if all_contexts else ('mean',))]
        if not all_contexts:
            for i,c in enumerate(raw):c['context']=x.core.CONTEXTS[i%3]
        return raw
    cases=dict(train=split(812000001,16,False),validation=split(812010001,2,True),final=split(812020001,4,True))
    inventory=seed_audit(cases)
    hashes=[{previous.parent.ticket_hash(c) for c in group} for group in cases.values()]
    if any(hashes[i]&hashes[j] for i in range(3) for j in range(i)):raise ValueError('input overlap')
    sources=dict(read(previous.BUNDLE/'registration.json')['sources']);sources.update(read(previous.BUNDLE/'repair.json')['source_overrides'])
    for rel in ('tools/d1_ie_candidates_v2.py','tools/d1_ie_candidates_v2_study.py','tools/test_d1_ie_candidates_v2.py',
        'tools/d1_ie_candidates_v2_report.py','tools/test_d1_ie_candidates_v2_report.py'):
        sources[rel]=sha(ROOT/rel)
    import importlib.metadata
    write(BUNDLE/'inputs.json',cases)
    c=dict(version='ie-four-candidates-v2',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),seed_audit=inventory,
        input_hashes={str(c['seed'])+'/'+c['family']:previous.parent.ticket_hash(c) for group in cases.values() for c in group},
        prior=used(),environment_cap=1536,learning_cap=420,wall_seconds=7200,save_reserve_seconds=300,
        main_learning_starts=384,learning_fixture_starts=32,planned_environment_starts=1422,learning_seeds=list(SEEDS),episodes_per_seed=64,
        policies=list(FIXED)+[f'{a}_seed{s}' for a in ALGORITHMS for s in SEEDS],references=list(REFS),validation_conditions=24,final_conditions=48,
        objective='ENERGY_AP_BAND_TRITON_NONWORSE_V2',objective_description='Band whole-120s J minus policy J; positive AP/missing/urgent-failure/normal-failure/P95 worsening costs versus both Band and Triton',
        reward_gamma=1.,mask='physical support/actual lane ownership/8 request slots/cooling credit only; no predicted SLA guarantee',
        initial_prior='uniform valid actions for PPO; zero Q for DDQN; no fixed BASE logit bonus',
        ppo=dict(native_masked=True,network='same 109/68/32/6 architecture; original source preserved',lr=.0003,epochs=4,batch_episodes=8,minibatch=256,clip=.2,entropy=.01,target_kl=.03),
        ddqn=dict(network='same 109/68 encoders, candidate six-channel Q head',lr=.0003,epochs=4,batch_episodes=8,minibatch=256,target_sync_gradient_steps=32,replay_episodes=32,epsilon='0.30 linearly to 0.10 over 64 episodes',double_target='online masked argmax, separate target network evaluation'),
        common_constraints=dict(multiplier_initial=[1.,10.,10.,10.,10.],multiplier_lr=.01),
        list_rule='three-context local service/P95/J/AP nonworse versus exact EDD suffix; minimize worst AP then J; no eligible -> BASE',
        rolling=dict(arrived_jobs=4,integer_tick_ms=1,solver='ortools CP-SAT '+importlib.metadata.version('ortools'),deterministic_limit=.05,wall_limit_s=.25,workers=1,seed=0,
            objective='lexicographic deadline misses/total lateness/overlap-aware measured energy',thermal='exact original three-context first-action AP filter; NOT exact thermal CP-SAT',fallback='registered list rule'),
        selection='validation-before-final freeze; all 3 learning seeds must pass; full work + primary absolute deadlines + no service/P95/J/AP regression versus BOTH Band/Triton in every condition; strict joint cost gain separately required',
        representative=dict(seed=812020001,family='queue',context='mean'),tuning_budget=0,device_commands=0,experiment_ready=False,
        model_sha256=x.core.p.MODEL_SHA,initial_sha256=x.core.p.INITIAL_SHA,
        simulator_scope='original measured A24 coefficients; declared transferred phase-vector contexts; fixed calibrated preload, model AP/h estimate, no surface-temperature or physical savings claim',
        algorithm_comparison='PPO/DDQN same state/actions/reward/mask/episodes; architectures, replay and transition/gradient counts reported',
        old_runs_checkpoints_clocks_preserved=True)
    write(BUNDLE/'registration.json',c);write(LOCAL/'registration.json',c)
    return c


def simulate(case,policy,network=None,multipliers=None,epsilon=0.,evaluation=True,deadline=None,no_wait=False,no_heat=False):
    if policy in FIXED[:4]:return previous.simulate(case,policy,deadline=deadline)
    frozen,_=x.core.p.inputs(x.core.p.BUNDLE);initial=read(previous.parent.proto.INPUT)['initial']
    tickets=x.core.ie.old.workload(case['family'],case['seed'])
    c=x.Controller(frozen,initial,policy,network,deterministic=evaluation,multipliers=multipliers,epsilon=epsilon,no_wait=no_wait,no_heat=no_heat)
    c.execution_deadline=deadline
    profile=x.core.p.profile(frozen,case['context']);vectors=dict(cells={key:[dict(source_request_id='common_context_'+case['context'],durations_ns=v) for _ in range(4)] for key,v in profile.items()})
    result=x.core.ie.old.engine.simulate(dict(protocol=x.core.p.VERSION,cells=x.core.p.profile(frozen)),vectors,tickets,
        policy=c.policy,settings=x.core.ie.external.settings(),seed=201,decision_provider=c)
    previous.parent.audit.audit(result,tickets);row,curves=previous.parent.audit.metrics(result,c,initial,frozen)
    row.update(case,policy=policy,nonbase_choices=sum(not r['chosen_base'] for r in c.choice_records),
        informative_choices=sum(r['valid_actions']>1 for r in c.choice_records),decision_choices=len(c.choice_records),
        solver_calls=len(c.plans),solver_accepted=sum(r.get('first_action_accepted',False) for r in c.plans),
        solver_unknown=sum(r['status'] not in ('OPTIMAL','FEASIBLE') for r in c.plans))
    return row,(result,curves),c


def sealed(path,identity):
    if not path.exists():return False
    done=[e for e in events() if e['event']=='completed' and e['identity']==identity]
    if len(done)!=1 or done[0]['artifact_sha256']!=sha(path):raise ValueError('unsealed artifact '+identity)
    return True


def execution(case,policy,identity,kind='evaluation',network=None,multipliers=None,epsilon=0.,learning=False):
    path=LOCAL/'items'/(identity.replace('/','__')+('.pt' if learning else '.json.gz'));path.parent.mkdir(exist_ok=True)
    if sealed(path,identity):
        if learning:
            item=x.torch.load(path,map_location='cpu',weights_only=False);restore_rng(item['rng']);return item
        return json.loads(gzip.decompress(path.read_bytes()))
    n,deadline=begin(kind,identity);began=time.perf_counter()
    try:
        row,extra,c=simulate(case,policy,network,multipliers,epsilon,not learning,deadline)
        row.update(host_wall_s=time.perf_counter()-began,identity=identity)
        item=dict(row=row,ledger=extra[0]['ledger'],curves=extra[1])
        if learning:
            refs=[reference(case,p) for p in REFS]
            data,costs,valid=x.targets(c,row,refs)
            row.update(informative=sum(r['informative'] for r in data),costs=costs.tolist(),cost_valid=valid.tolist())
            item.update(data=data,costs=costs,valid=valid,rng=rng())
            x.torch.save(item,path)
        else:path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0))
        with lock():append('completed',number=n,kind=kind,identity=identity,row=row,artifact_sha256=sha(path))
        return item
    except BaseException as error:
        with lock():append('failed',number=n,kind=kind,identity=identity,error=repr(error))
        raise


def reference(case,policy):
    ident='reference/'+str(case['seed'])+'/'+case['family']+'/'+case['context']+'/'+policy
    return execution(case,policy,ident,'reference')['row']


def rng():return dict(python=random.getstate(),numpy=np_random_state(),torch=x.torch.get_rng_state())
def np_random_state():return x.np.random.get_state()
def restore_rng(r):random.setstate(r['python']);x.np.random.set_state(r['numpy']);x.torch.set_rng_state(r['torch'])


def new_learner(algorithm,seed):
    oldnn=x.old.current;oldnn.seed_all(seed)
    network=x.UnbiasedPPO() if algorithm=='PPO' else x.DoubleQ()
    optimizer=x.torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5)
    return dict(network=network,optimizer=optimizer,target=copy.deepcopy(network) if algorithm=='DDQN' else None,
        state=dict(algorithm=algorithm,seed=seed,cursor=0,batch=[],replay=[],rows=[],updates=[],gradient_steps=0,multipliers=[1.,10.,10.,10.,10.]))


def archive(path,learner):
    payload=dict(algorithm=learner['state']['algorithm'],network=learner['network'].state_dict(),optimizer=learner['optimizer'].state_dict(),
        target_network=learner['target'].state_dict() if learner['target'] is not None else None,state=learner['state'],rng=rng(),
        registration_sha256=sha(BUNDLE/'registration.json'),schema=dict(state=109,candidate=68,slots=32,channels=6))
    temp=path.with_suffix('.tmp')
    with temp.open('wb') as f:x.torch.save(payload,f);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def restore(path):
    p=x.torch.load(path,map_location='cpu',weights_only=False)
    if p['registration_sha256']!=sha(BUNDLE/'registration.json'):raise ValueError('archive binding')
    learner=new_learner(p['algorithm'],p['state']['seed']);learner['network'].load_state_dict(p['network']);learner['optimizer'].load_state_dict(p['optimizer'])
    if learner['target'] is not None:learner['target'].load_state_dict(p['target_network'])
    learner['state']=p['state'];restore_rng(p['rng']);return learner


def update(learner):
    s=learner['state'];batch=s['batch']
    if s['algorithm']=='PPO':stats=x.old.current.update(learner['network'],learner['optimizer'],batch,s['multipliers'])
    else:
        s['replay']=(s['replay']+batch)[-32:]
        stats=x.dqn_update(learner['network'],learner['target'],learner['optimizer'],s['replay'],sum(len(e['data']) for e in batch),s['multipliers'],s['gradient_steps'])
        s['gradient_steps']=stats['gradient_steps']
        for i in range(5):
            costs=[e['costs'][i] for e in batch if e['valid'][i+1]]
            if costs:s['multipliers'][i]=max(0.,s['multipliers'][i]+.01*float(x.np.mean(costs)))
    s['updates'].append(stats);s['batch']=[];return stats


def train_one(learner,case,identity,kind):
    s=learner['state'];epsilon=.30-.20*min(s['cursor'],63)/63
    item=execution(case,x.PPO if s['algorithm']=='PPO' else x.DQN,identity,kind,learner['network'],s['multipliers'],epsilon,True)
    s['batch'].append({k:item[k] for k in ('data','costs','valid')});s['rows'].append(item['row']);s['cursor']+=1
    return item


def fixtures():
    if (BUNDLE/'resume_verification.json').exists():return
    cases=read(BUNDLE/'inputs.json')['train'][:8];results=[]
    for algorithm in ALGORITHMS:
        initial=new_learner(algorithm,97);archive(LOCAL/(algorithm+'_fixture_initial.pt'),initial)
        values=[]
        for arm in ('continuous','resumed'):
            learner=restore(LOCAL/(algorithm+'_fixture_initial.pt'))
            for i,c in enumerate(cases):
                train_one(learner,c,f'fixture/{algorithm}/{arm}/{i}','learning_fixture');archive(LOCAL/(algorithm+'_fixture_'+arm+'.pt'),learner)
                if arm=='resumed' and i==3:learner=restore(LOCAL/(algorithm+'_fixture_'+arm+'.pt'))
            stats=update(learner);archive(LOCAL/(algorithm+'_fixture_'+arm+'_terminal.pt'),learner)
            values.append((x.old.current.model_hash(learner['network']),learner['state']['multipliers'],x.torch.get_rng_state().clone()))
        if values[0][:2]!=values[1][:2] or not x.torch.equal(values[0][2],values[1][2]):raise AssertionError('actual resume mismatch')
        payloads=[x.torch.load(LOCAL/(algorithm+'_fixture_'+arm+'_terminal.pt'),map_location='cpu',weights_only=False) for arm in ('continuous','resumed')]
        def equal(a,b):
            if isinstance(a,x.torch.Tensor):return isinstance(b,x.torch.Tensor) and x.torch.equal(a,b)
            if isinstance(a,x.np.ndarray):return isinstance(b,x.np.ndarray) and x.np.array_equal(a,b)
            if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
            if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(v,w) for v,w in zip(a,b))
            return a==b
        for field in ('network','optimizer','target_network','rng'):
            if not equal(payloads[0][field],payloads[1][field]):raise AssertionError('resume archive mismatch: '+field)
        for field in ('cursor','batch','replay','multipliers','gradient_steps','updates'):
            if not equal(payloads[0]['state'][field],payloads[1]['state'][field]):raise AssertionError('resume learner mismatch: '+field)
        results.append(dict(algorithm=algorithm,status='PASS',actor_or_q_sha256=values[0][0],adam_rng_and_partial_batch_equal=True,stats=stats))
    write(BUNDLE/'resume_verification.json',dict(results=results,learning_starts=32))


def train(algorithm,seed):
    path=LOCAL/f'{algorithm}_seed{seed}_state.pt';learner=restore(path) if path.exists() else new_learner(algorithm,seed)
    cases=read(BUNDLE/'inputs.json')['train'];s=learner['state']
    while s['cursor']<64:
        i=s['cursor'];train_one(learner,cases[i],f'train/{algorithm}/{seed}/{i}','train');archive(path,learner)
        if len(s['batch'])==8:
            stats=update(learner);archive(path,learner);print(f'{algorithm} seed{seed} {s["cursor"]}/64 '+json.dumps(stats),flush=True)
    archive(LOCAL/f'{algorithm}_seed{seed}_terminal.pt',learner)
    write(LOCAL/f'{algorithm}_seed{seed}_done.json',dict(algorithm=algorithm,seed=seed,cursor=s['cursor'],rows=s['rows'],updates=s['updates'],multipliers=s['multipliers']))


def evaluate(split,algorithm=None,seed=None):
    learner=restore(LOCAL/f'{algorithm}_seed{seed}_terminal.pt') if algorithm else None
    for i,case in enumerate(read(BUNDLE/'inputs.json')[split]):
        for policy in ([x.PPO if algorithm=='PPO' else x.DQN] if algorithm else FIXED):
            label=f'{algorithm}_seed{seed}' if algorithm else policy
            execution(case,policy,f'{split}/{label}/{i}',split,learner['network'] if learner else None,learner['state']['multipliers'] if learner else None)


def children(tasks):
    pending=list(tasks);running=[];failures=[]
    while pending or running:
        while pending and len(running)<3:
            args=pending.pop(0);log=(LOCAL/('_'.join(args)+'.log')).open('ab')
            proc=subprocess.Popen([sys.executable,'-B','-X','utf8','-m','tools.d1_ie_candidates_v2_study',*args],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            running.append((proc,log,args))
        for job in running[:]:
            proc,log,args=job;code=proc.poll()
            if code is not None:
                log.close();running.remove(job)
                if code:failures.append(args);pending=[] # let other owned workers archive and finish
        time.sleep(.2)
    if failures:raise RuntimeError('child failures preserved, see logs: '+repr(failures))


def run():
    prepare();owner=LOCAL/'owner.json'
    if owner.exists():raise RuntimeError('owner exists; inspect without killing any process')
    write(owner,dict(pid=os.getpid(),utc=utc()))
    try:
        cases=read(BUNDLE/'inputs.json')['train']
        for c in cases:
            for p in REFS:reference(c,p)
        fixtures()
        # Three load regimes for each candidate, fixed handoff smoke; no tuning.
        for f in ('low','burst','sustained'):
            case=next(c for c in cases if c['family']==f)
            for p in (x.LIST,x.ROLL,x.PPO,x.DQN):
                l=new_learner('PPO' if p==x.PPO else 'DDQN',11) if p in (x.PPO,x.DQN) else None
                execution(case,p,f'smoke/{p}/{f}','smoke',l['network'] if l else None,l['state']['multipliers'] if l else None)
        # Original baseline output is independently reproduced and physically checked.
        for p in (x.core.BASE,REFS[0]):execution(cases[0],p,'preservation/'+p,'preservation')
        children([['train','--algorithm',a,'--seed',str(s)] for a in ALGORITHMS for s in SEEDS])
        children([['evaluate','--split','validation']]+[['evaluate','--split','validation','--algorithm',a,'--seed',str(s)] for a in ALGORITHMS for s in SEEDS])
        from tools import d1_ie_candidates_v2_report as report
        report.freeze_selection()
        children([['evaluate','--split','final']]+[['evaluate','--split','final','--algorithm',a,'--seed',str(s)] for a in ALGORITHMS for s in SEEDS])
        write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used()))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','train','evaluate','status']);p.add_argument('--algorithm',choices=ALGORITHMS);p.add_argument('--seed',type=int);p.add_argument('--split',choices=['validation','final'])
    args=p.parse_args()
    if args.command=='prepare':prepare();print(json.dumps(used()))
    elif args.command=='run':run()
    elif args.command=='train':train(args.algorithm,args.seed)
    elif args.command=='evaluate':evaluate(args.split,args.algorithm,args.seed)
    else:print(json.dumps(used(),indent=2))
