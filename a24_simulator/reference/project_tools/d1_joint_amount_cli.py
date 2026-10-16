"""Verify-only by default; explicit prepare/run for bounded desktop V1 amount.

No assistant should run the run command without a new explicit run scope.
One continuation adds8..480 episodes per learner, with full shared-session
archives. Supports the original terminal64 as parent; completed parent500/192
is never reopened. This is not a V2/new-objective learner.
"""
import argparse,gzip,json,os,re,sys,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_service_joint_rl_run as x
from tools import d1_joint_amount_session as session

ROOT=x.ROOT
class PauseRequested(Exception):pass
def validate_registry(registry):
    if registry.get('version')!='arrival_seed_registry_v1':raise ValueError('arrival registry version')
    seeds=registry.get('seeds');ranges=registry.get('ranges')
    if not isinstance(seeds,list) or not isinstance(ranges,list) or any(type(q) is not int or q<0 for q in seeds):raise ValueError('integer arrival seeds required')
    if any(not isinstance(q,list) or len(q)!=2 or any(type(v) is not int or v<0 for v in q) or q[0]>q[1] for q in ranges):raise ValueError('ordered closed arrival seed ranges required')
    return registry
def reject_reserved_seeds(seeds,registry):
    registry=validate_registry(registry);known=set(registry['seeds'])
    if any(q in known or any(lo<=q<=hi for lo,hi in registry['ranges']) for q in seeds):raise ValueError('arrival seed already reserved/used')
def registry():
    path=ROOT/'arrival_seed_registry.json'
    if path.exists():return validate_registry(x.read(path)),x.sha(path)
    if not (ROOT/'.git').exists():raise FileNotFoundError('standalone requires locked arrival_seed_registry.json from the original workspace')
    return None,None
def original_dependencies():
    reg=x.read(x.LOCAL/'registration.json')
    return dict(contract_sha256=x.sha(x.LOCAL/'registration.json'),model=x.h.UPSTREAM_SHA,sources=reg['source_sha256'],objective=x.n.objective.OBJECTIVE)
def source_check(manifest_path=None):
    import hashlib
    identity=x.read(x.PUBLIC/'source_identity.json');manifest=Path(manifest_path) if manifest_path else ROOT/'core_manifest.json';patches={};receipt=None
    if manifest.exists():
        receipt_path=manifest.parent/'portable_patch_receipt.json';receipt=x.read(receipt_path);core=x.read(manifest)
        allowed={'tools/d1_arrival_ap_confirmation.py','tools/d1_arrival_energy_collection.py','tools/d1_energy_collection.py'}
        for q in receipt['patches']:
            if q['logical_path'] not in allowed or not q['structural_AST_unchanged'] or q['original_source_modified'] or q['replacement']!='$env:D1CHECK_ADB':raise ValueError('unapproved portable source change')
            patches[q['logical_path']]=q
        entries={q['logical_path']:q for q in core['files']}
    for name,entry in identity['sources'].items():
        raw=(ROOT/name).read_bytes();actual=hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
        if actual==entry['canonical_lf_sha256']:continue
        if name not in patches:raise ValueError('policy/source changed '+name)
        patch=patches[name]
        if patch['old_canonical_lf_sha256']!=entry['canonical_lf_sha256'] or actual!=patch['new_canonical_lf_sha256'] or entries[name]['portable_canonical_lf_sha256']!=actual:raise ValueError('portable receipt/source mismatch')
    reserved,registry_sha=registry()
    return dict(status='PASS_locked_original_or_three_unused_ADB_defaults',arrival_seed_registry_sha256=registry_sha,portable_manifest_sha256=x.sha(manifest) if manifest.exists() else None,portable_patch_receipt_sha256=x.sha(manifest.parent/'portable_patch_receipt.json') if manifest.exists() else None)

def verify(manifest_path=None):
    receipt=source_check(manifest_path)
    paths={s:x.LOCAL/'checkpoints'/f'seed{s}_ep64.pt' for s in x.SEEDS}
    missing=[p.relative_to(ROOT).as_posix() for p in paths.values() if not p.exists()]
    if missing:return dict(status='shared_metadata_verified_local_payload_missing',missing=missing,native=0,learning=0)
    expected={q['seed']:q['sha256'] for q in x.read(x.PUBLIC/'checkpoint_inventory.json') if q['episodes']==64}
    if any(x.sha(paths[seed])!=expected[seed] for seed in x.SEEDS):raise ValueError('terminal64 hash differs from the published original archive')
    public=x.read(x.PUBLIC/'source_identity.json')
    if x.sha(x.LOCAL/'registration.json')!=public['original_contract_sha256']:raise ValueError('transported original private contract differs from published contract')
    if x.sha(x.h.MODEL)!=x.read(x.LOCAL/'registration.json')['exported_model_sha256']:raise ValueError('original thermal model changed')
    x.h.load()
    learners=session.initial(paths,original_dependencies());p=session.snapshot(learners,dict(case=0,next_seed=0),dict(native=0,learning=0));restored,cursor,consumption=session.restore(p)
    assert all(session.digest(p['learners'][str(s)])==session.digest(restored[s].snapshot()) for s in x.SEEDS)
    return dict(status='PASS_V1_payload_and_shared_session_restore',source_receipt=receipt,base_episodes=64,objective=x.n.objective.OBJECTIVE,schema=x.n.SCHEMA,native=0,learning=0,unseen_PC_execution_tested=False)

def folder(task):
    if not re.fullmatch('[a-z0-9_]{1,48}',task):raise ValueError('safe unique task id required')
    return ROOT/'output'/('desktop_joint_amount_'+task)

def prepare(args):
    verify(args.portable_manifest);dest=folder(args.task)
    if dest.exists():raise FileExistsError('same task cannot reset clock or budget')
    additional=args.target-64
    if additional<=0 or additional%8 or additional>480:raise ValueError('one task adds8..480 whole episodes/learner; target multiples8')
    expected=additional+3*additional+72+336
    if args.native_cap<expected or args.native_cap>3072 or args.learning_cap<3*additional or args.learning_cap>1440:raise ValueError('explicit tighter budget insufficient/outside one-task ceiling')
    if args.reserve_minutes<1 or args.active_minutes<=args.reserve_minutes:raise ValueError('positive immutable save reserve')
    seeds=range(args.arrival_start,args.arrival_start+additional//4)
    history=list((ROOT/'output').rglob('registration.json'))+list((ROOT/'docs/results').glob('*/execution_contract.json'))
    new_seeds=list(seeds)+list(args.confirm_seeds)
    reserved,registry_sha=registry()
    if reserved is not None:reject_reserved_seeds(new_seeds,reserved)
    for path in history:
        text=path.read_text(encoding='utf-8')
        previous=json.loads(text);bounds=previous.get('training_seed_range')
        if any(str(seed) in text for seed in new_seeds) or bounds and any(bounds[0]<=seed<=bounds[1] for seed in new_seeds):raise ValueError('training/final seed already registered')
    if len(set(args.confirm_seeds))!=4 or set(seeds)&set(args.confirm_seeds):raise ValueError('four fresh confirmation seeds separated from training')
    inputs=dict(train=x.old.x.cases(seeds,True),development=x.read(x.LOCAL/'inputs.json')['development'],confirmation=x.old.x.cases(args.confirm_seeds))
    from tools.d1_service_joint_rl_check import PUBLIC
    source_identity=x.read(PUBLIC/'source_identity.json');sources={name:entry['canonical_lf_sha256'] for name,entry in source_identity['sources'].items()}
    import hashlib
    for name in sources:sources[name]=hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    for name in ('tools/d1_joint_amount_session.py','tools/d1_joint_amount_cli.py'):sources[name]=hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    paths={s:x.LOCAL/'checkpoints'/f'seed{s}_ep64.pt' for s in x.SEEDS};learners=session.initial(paths,original_dependencies())
    reg=dict(task=args.task,registered_utc=datetime.now(timezone.utc).isoformat(),parent_task='SERVICE-JOINT-FRESH-RL-02',parent_closed_native=500,parent_closed_learning=192,
        parent_checkpoints={str(s):dict(path=p.relative_to(ROOT).as_posix(),sha256=x.sha(p)) for s,p in paths.items()},target_episodes=args.target,additional_per_learner=additional,
        native_cap=args.native_cap,learning_cap=args.learning_cap,expected_native=expected,active_seconds=args.active_minutes*60,reserve_seconds=args.reserve_minutes*60,
        canonical_source_sha256=sources,arrival_seed_registry_sha256=registry_sha,portable_source_receipt=source_check(args.portable_manifest),inputs_sha256=x.r.c.digest(inputs),schema=x.n.SCHEMA,objective=x.n.objective.OBJECTIVE,
        training_seed_order=list(x.SEEDS),sampling='same original shared global RNG; full3learner/session/case-nextseed snapshot',common_settings=x.read(x.LOCAL/'registration.json')['common_settings'],
        phase_caps=dict(reference=additional,train=3*additional,development=72,confirmation=336),model_sha256=x.h.UPSTREAM_SHA,model_export_sha256=x.sha(x.h.MODEL),
        confirmation_seeds=args.confirm_seeds,training_seed_range=[args.arrival_start,args.arrival_start+additional//4-1],development_already_seen=True,V2_actor_reuse=False,
        device_commands=0,strict_changed=False,experiment_ready=False,automatic_adoption=False)
    dest.mkdir();x.write(dest/'registration.json',reg);x.write(dest/'inputs.json',inputs);x.write(dest/'clock.json',dict(consumed_active_seconds=0.,running_since=None));session.save(dest/'session_latest.pt',session.snapshot(learners,dict(case=0,next_seed=0),dict(native=0,learning=0)))
    x.write(dest/'WORKING_STATE.json',dict(phase='prepared_not_run',native=0,learning=0,next_action='explicit run only; do not reset task/budget'))
    return dict(status='prepared_not_run',task=args.task,expected_native=expected,learning=3*additional)

def check_task(dest):
    import hashlib
    reg=x.read(dest/'registration.json')
    if reg.get('arrival_seed_registry_sha256'):
        if x.sha(ROOT/'arrival_seed_registry.json')!=reg['arrival_seed_registry_sha256']:raise ValueError('locked arrival registry changed')
    elif not (ROOT/'.git').exists():raise ValueError('standalone task requires a preregistered seed registry; no automatic amendment')
    for name,digest in reg['canonical_source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=digest:raise ValueError('locked policy/source changed '+name)
    if x.r.c.digest(x.read(dest/'inputs.json'))!=reg['inputs_sha256'] or x.sha(x.h.MODEL)!=reg['model_export_sha256']:raise ValueError('locked input/model changed')
    for v in reg['parent_checkpoints'].values():
        if x.sha(ROOT/v['path'])!=v['sha256']:raise ValueError('original terminal64 changed')
    return reg

class Budget(x.old.Budget):
    def __init__(self,dest,activate=False):
        self.dest=dest;self.reg=check_task(dest);self.rows=[];self.clock=x.read(dest/'clock.json') if (dest/'clock.json').exists() else dict(consumed_active_seconds=0.,running_since=None)
        if self.clock['running_since'] is not None:raise ValueError('previous active clock has no safe close; fail closed, no automatic reset')
        self.deadline=time.time()+self.reg['active_seconds']-self.clock['consumed_active_seconds']-self.reg['reserve_seconds']
        if activate:
            if time.time()>=self.deadline:raise TimeoutError('remaining active budget is reserved for saving')
            self.clock['running_since']=time.time();x.write(dest/'clock.json',self.clock)
        for line in (dest/'executions.jsonl').read_text(encoding='utf-8').splitlines() if (dest/'executions.jsonl').exists() else []:
            q=json.loads(line)
            if q.get('event'):self.rows[q['number']-1].update(q)
            else:self.rows.append(q)
    def used(self):return dict(native_starts=len(self.rows),learning_starts=sum(q['learning'] for q in self.rows),native_cap=self.reg['native_cap'],learning_cap=self.reg['learning_cap'],parent_closed_native=500,parent_closed_learning=192,cumulative_V1_lineage_native=500+len(self.rows),cumulative_V1_lineage_learning=192+sum(q['learning'] for q in self.rows),device_commands=0)
    def append(self,q):
        with (self.dest/'executions.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(q,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,phase,case,agent,learning=False):
        if (self.dest/'REQUEST_STOP').exists():raise PauseRequested('safe stop before '+phase+' environment')
        if not any(q['identity']==identity for q in self.rows) and (len(self.rows)>=self.reg['native_cap'] or learning and self.used()['learning_starts']>=self.reg['learning_cap']):raise TimeoutError('explicit desktop budget')
        previous_local,previous_check=x.old.LOCAL,x.old.check;x.old.LOCAL=self.dest;x.old.check=lambda:check_task(self.dest)
        try:return x.old.Budget.call(self,identity,phase,case,agent,learning)
        finally:x.old.LOCAL,x.old.check=previous_local,previous_check
    def close_clock(self):
        if self.clock['running_since'] is None:return
        self.clock['consumed_active_seconds']+=max(0.,time.time()-self.clock['running_since']);self.clock['running_since']=None;x.write(self.dest/'clock.json',self.clock)

def run(task):
    dest=folder(task)
    if (dest/'completion.json').exists():raise FileExistsError('completed desktop task cannot reset')
    owner=dest/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget(dest,activate=True);data=x.read(dest/'inputs.json');payload=x.r.torch.load(dest/'session_latest.pt',map_location='cpu',weights_only=False);learners,cursor,old_consumption=session.restore(payload)
        for seed in x.SEEDS:
            consumed=sum(q['learning'] and q['identity'].startswith(f'train_{seed}_') for q in budget.rows)
            if consumed!=learners[seed].accepted_episodes-64:raise ValueError('consumed training differs from atomic shared session; no cached replay')
        refs=[]
        for index,case in enumerate(data['train']):
            if (dest/'REQUEST_STOP').exists():x.write(dest/'WORKING_STATE.json',dict(phase='paused_at_reference_boundary',consumption=budget.used(),cursor=cursor));return
            raw=budget.call(f'reference_{index:04d}','reference',case,x.teacher(case));refs.append(dict(row=raw['row'],sha256=x.sha(dest/'items'/f'reference_{index:04d}.json.gz')))
        for index in range(cursor['case'],len(data['train'])):
            for slot in range(cursor['next_seed'] if index==cursor['case'] else 0,3):
                if (dest/'REQUEST_STOP').exists():x.write(dest/'WORKING_STATE.json',dict(phase='paused_at_episode_boundary',consumption=budget.used(),cursor=cursor));return
                seed=x.SEEDS[slot];learner=learners[seed];f,initial,_=x.h.load();a=learner.fresh_controller(f,initial['initial']);raw=budget.call(f'train_{seed}_{index:04d}','train',data['train'][index],a,True)
                frames,rewards,costs,valid,diag=x.n.objective.episode_targets(a,raw['row'],raw['curve'],refs[index]['row']);learner.add_episode(frames,raw['row'],costs,valid,controller=a,cursor=dict(next_episode=65+index),consumption=budget.used(),reference_hash=refs[index]['sha256'],metadata=dict(desktop_case=index,objective_diag=diag));learner.update_if_ready()
                cursor=dict(case=index+(slot==2),next_seed=(slot+1)%3);session.save(dest/'session_latest.pt',session.snapshot(learners,cursor,budget.used()))
        rows=[]
        for role in ('Band','Triton','JointList','CostList'):
            for case in data['confirmation']:
                if role in ('Band','Triton'):agent=x.old.x.agent(role)
                else:
                    f,initial,_=x.h.load();agent=x.e.Controller(f,initial['initial'],x.e.JOINT if role=='JointList' else x.e.COST)
                raw=budget.call(f'confirmation_{role}_{case["condition"]:02d}','confirmation',case,agent);rows.append(dict(scope='confirmation',**x.row(raw,case,role)))
        for phase,cases in (('development',data['development']),('confirmation',data['confirmation'])):
            for seed in x.SEEDS:
                for case in cases:
                    raw=budget.call(f'{phase}_{seed}_{case["condition"]:02d}',phase,case,x.actor(learners[seed].network));rows.append(dict(scope=phase,**x.row(raw,case,f'PPO{seed}_{learners[seed].accepted_episodes}',seed,learners[seed].accepted_episodes)))
        for seed in x.SEEDS:learners[seed].save(dest/'checkpoints'/f'seed{seed}_ep{learners[seed].accepted_episodes}.pt')
        final=[dict(q,policy='Rule') if q['policy']=='CostList' else q for q in rows if q['scope']=='confirmation']
        gates={f'PPO{seed}_{learners[seed].accepted_episodes}':x.old.gate_rows(final,f'PPO{seed}_{learners[seed].accepted_episodes}',48) for seed in x.SEEDS}
        x.write(dest/'completion.json',dict(status='completed',rows=rows,gates=gates,consumption=budget.used(),automatic_adoption=False,final_regression_KPI='same48 Band/Triton/samecandidateCostList and JointList, original allcondition service/AP/J and absolute primary family gate'))
        x.write(dest/'WORKING_STATE.json',dict(phase='completed',budget_closed=True,consumption=budget.used()))
    except PauseRequested as error:
        x.write(dest/'WORKING_STATE.json',dict(phase='paused_at_environment_boundary',reason=str(error),consumption=budget.used(),cursor=cursor))
    finally:
        if budget is not None:budget.close_clock()
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',nargs='?',default='verify',choices=('verify','prepare','run'));p.add_argument('--portable-manifest');p.add_argument('--task');p.add_argument('--target',type=int,default=128);p.add_argument('--arrival-start',type=int,default=860010001);p.add_argument('--confirm-seeds',type=int,nargs=4);p.add_argument('--native-cap',type=int);p.add_argument('--learning-cap',type=int);p.add_argument('--active-minutes',type=int);p.add_argument('--reserve-minutes',type=int);a=p.parse_args()
    if a.command=='verify':print(json.dumps(verify(a.portable_manifest),indent=2))
    elif a.command=='prepare':
        if any(getattr(a,k) is None for k in ('task','confirm_seeds','native_cap','learning_cap','active_minutes','reserve_minutes')):p.error('prepare needs explicit task/seeds/native/learning/time/reserve budget')
        print(json.dumps(prepare(a),indent=2))
    else:
        if not a.task:p.error('run requires existing prepared --task')
        run(a.task)
