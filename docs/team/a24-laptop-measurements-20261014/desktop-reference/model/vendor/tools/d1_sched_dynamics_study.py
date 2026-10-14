"""Registered, finite dynamics17 comparison. Original sources remain untouched."""
from __future__ import annotations
import argparse
import collections
import copy
import csv
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import numpy as np
import torch
from tools import d1_sched_dynamics_profiles as profiles
from tools import d1_sched_dynamics_plant as plant
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_cases as cases
from tools import d1_sched_dynamics_ppo as rl

ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT.parent.parent
WORK=ROOT.parent/'D1-SCHED-DYNAMICS-17'; OUT=BASE/'outputs/D1-SCHED-DYNAMICS-17'
TASK='D1-SCHED-DYNAMICS-17'; SEEDS=(1171,1181,1193)
FILES=tuple(f'd1_sched_dynamics_{k}.py' for k in ('profiles','plant','policy','cases','ppo','study'))+tuple(f'test_d1_sched_dynamics_{k}.py' for k in ('plant','policy','ppo'))
CAP=3100; WALL=7200; RESERVE=1800

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');os.replace(tmp,p)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def csvout(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r));p=Path(p)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def service_means(p):
    out={}
    for key,ds in p['service_anchor']['means'].items():
        parts=key.split('|');task,b=parts[-2:]
        if len(parts)==2 or parts[0]=='CPU_URGENT' or task=='classification':out[task+'_'+b]=ds
    return out

def register():
    if WORK.exists():raise ValueError('new task never overwrites consumed registration')
    WORK.mkdir();OUT.mkdir(exist_ok=True)
    s26path=BASE/'outputs/S26-PAIR-OBSERVER-06/repaired_final_model_START0.json'
    ps={'A24':profiles.profiles('A24'),'S26':profiles.profiles('S26',read(s26path))}
    save(WORK/'profiles.json',ps);save(OUT/'profiles.json',ps)
    dev=[];final=[];abl=[];train=[]
    for device,pp in ps.items():
        means=service_means(pp['neutral'])
        for name in profiles.PRIMARY:
            for c in cases.grid(device,'dev',means):dev.append(dict(c,profile=name,identity=f'{device}_{name}_{c["family"]}_{c["deadline_mode"]}_{c["arrival_seed"]}'))
            for c in cases.grid(device,'final',means):final.append(dict(c,profile=name,identity=f'{device}_{name}_{c["family"]}_{c["deadline_mode"]}_{c["arrival_seed"]}'))
        for name in profiles.ABLATIONS:
            for c in cases.grid(device,'final',means,seeds=cases.SPLIT_SEEDS['final'][:1]):abl.append(dict(c,profile=name,identity=f'{device}_{name}_{c["family"]}_{c["deadline_mode"]}_{c["arrival_seed"]}'))
    # Balanced, predeclared training permutation. Each seed shares cases, not action RNG.
    factorial=[(d,p,f,dd) for d in ps for p in profiles.PRIMARY for f in cases.FAMILIES for dd in cases.DEADLINE_MODES]
    for i in range(256):
        d,p,f,dd=factorial[(i*17)%len(factorial)];seed=cases.SPLIT_SEEDS['train'][(i//len(factorial))*19+i%len(factorial)]
        c=cases.make_case(d,'train',seed,f,dd,service_means(ps[d]['neutral']));train.append(dict(c,profile=p,identity=f'TRAIN_{i:03}_{d}_{p}_{f}_{dd}_{seed}'))
    for name,rows in [('train',train),('dev',dev),('final',final),('ablation',abl)]:save(WORK/'inputs'/f'{name}.json',rows);save(OUT/'inputs'/f'{name}.json',rows)
    source={str(ROOT/'tools'/n):sha(ROOT/'tools'/n) for n in FILES};source[str(ROOT/'docs/SCHED_DYNAMICS_DESIGN_20261012.md')]=sha(ROOT/'docs/SCHED_DYNAMICS_DESIGN_20261012.md')
    parent={str(p):sha(p) for p in [profiles.A24_MODEL,profiles.A24_RAW,s26path,*[BASE/'outputs'/n for n in ('S26-INTEGRATED-SIM-03-runtime.zip','S26-COST-REFINE-04-research.zip','S26-DYNAMIC-COST-05-research.zip','S26-PAIR-OBSERVER-06-research.zip')]]}
    deps={str(ROOT/'tools'/n):sha(ROOT/'tools'/n) for n in ('d1_s26_npu_engine.py','d1_s26_observer_separate_heat.py','d1_s26_pair_observer_model.py','d1_s26_pair_observer_runtime.py','d1_s26_dynamic_cost_model.py','d1_s26_cost_refine_model.py','d1_s26_integrated.py','d1_s26_npu_ppo.py')}
    inputs={str(p):sha(p) for p in (WORK/'inputs').glob('*.json')};inputs[str(WORK/'profiles.json')]=sha(WORK/'profiles.json')
    reg=dict(task=TASK,created_utc=utc(),head='12d64923be824ce4c88fca074fbe38820f5a7d25',sources=source,parents=parent,dependencies=deps,inputs=inputs,
        schema=policy.SCHEMA,dimensions=[policy.STATE_DIM,policy.SLOTS,policy.ACTION_DIM],seeds=list(SEEDS),train_stages=[128,256],stage_cases=96,final_cases=96,ablation_cases=48,
        environment_cap=CAP,wall_cap_s=WALL,final_save_reserve_s=RESERVE,fit=0,device=0,apk=0,external_messages=0,external_power_reference_available=False,
        profiles_hypotheses=True,physical_anchors_previously_seen=True,default_replacement=False,
        expansion='stage128 allseeds stable + anyseed DEV original/declared failure decrease vs ATC OR completed equal-service J/AP opportunity improvement; remaining wall>=1800s',
        selection='stage128/256 only; lex incomplete, weighted original failures, weighted declared failures, weighted tardiness, mean totalJ, meanAP, earlier stage; all cases kept',
        representative='same DEV selection key then seed; freeze before reading FINAL',
        final_roles=[*policy.RULES,*[f'PPO_{seed}' for seed in SEEDS]],ablation_roles=['FIFO_READY','ATC','RR_READY','PPO_REP'],
        synthetic_fixture_updates_agent=6,synthetic_fixture_adam_agent=6)
    save(WORK/'registration.json',reg);save(OUT/'registration.json',reg)
    for path in source:
        dst=OUT/'source'/Path(path).name;dst.parent.mkdir(exist_ok=True);shutil.copy2(path,dst)
    print(json.dumps(dict(stage='registered',dev=len(dev),final=len(final),ablations=len(abl),train_per_seed=256,environment_cap=CAP)))

class AuditedController:
    def __init__(self,inner):self.inner=inner;self.audit=[]
    def __getattr__(self,name):return getattr(self.inner,name)
    def choose(self,dev,waiting):
        if not waiting:raise ValueError('empty candidate decision')
        pub=dev.public();ordered=sorted(waiting,key=policy.tie);actions=[[(q,b)] for q in ordered for b in dev.routes(q)]+[[]]
        legal=[i for i,jobs in enumerate(actions[:-1]) if dev.feasible(jobs)]
        if not legal and any(pub['lanes'].values()):legal=[len(actions)-1]
        jobs=self.inner.choose(dev,waiting);jobs=jobs or []
        choice=[(q['id'],b) for q,b in jobs];lookup={tuple((q['id'],b) for q,b in a):i for i,a in enumerate(actions)}
        idx=lookup.get(tuple(choice))
        if idx not in legal:raise ValueError('independent physical/common-mask audit')
        if self.inner.errors:raise ValueError('controller model error/fallback')
        d=self.inner.decisions[-1]
        if d.get('legal',len(legal))!=len(legal):raise ValueError('controller legal count mismatch')
        self.audit.append(dict(time_ns=dev.now,waiting=[q['id'] for q in ordered],owners={b:dict(id=v['request']['id'],task=v['request']['task'],phase=v['phase']) if v else None for b,v in pub['lanes'].items()},legal_indices=legal,chosen_index=idx,chosen=choice,
            sensor_age_s=pub.get('sensor_age_s'),mask_sha256=digest(legal),future_input=False))
        return jobs or None

def affinity(p):
    means=service_means(p);routes=[b for b in plant.BACKENDS if 'classification_'+b in means]
    return dict(classification=min(routes,key=lambda b:(sum(means['classification_'+b]),plant.BACKENDS.index(b))),detection='CPU')

def physical_audit(raw,requests):
    source={q['id']:q for q in requests};owners={};stages={};responses={};last=-1
    for ev in raw['events']:
        t=ev['time_ns'];rid=ev['id'];b=ev['backend'];phase=ev['phase'];q=source[rid]
        if t<last:raise ValueError('event order');
        last=t
        if phase=='ASSIGNED':
            if b in owners or rid in stages or q['arrival_ns']>t or b not in plant.routes(q,raw['device'],raw['npu']):raise ValueError('owner/support/duplicate')
            owners[b]=rid;stages[rid]=0
        else:
            if owners.get(b)!=rid:raise ValueError('release owner mismatch')
            expected=('EXECUTING','OUTPUT_READY','PERSISTED','WORKER_RELEASED','AVAILABLE')[stages[rid]]
            if phase!=expected:raise ValueError('phase progression')
            stages[rid]+=1
            if phase==('OUTPUT_READY' if q['priority']=='urgent' else 'PERSISTED'):responses[rid]=t-q['arrival_ns']
            if phase=='AVAILABLE':del owners[b]
        labels={(source[x]['task'],bb) for bb,x in owners.items()}
        allowed=[{('classification','GPU'),('detection','CPU')}]
        if raw['npu']:allowed.append({('classification','NPU'),('detection','CPU')})
        if len(owners)>2 or len(owners)==2 and labels not in allowed:raise ValueError('unsupported concurrency')
    for r in raw['ledger']:
        if r.get('response_ns')!=responses.get(r['id']):raise ValueError('response phase mismatch')
        if r['status']=='succeeded' and stages.get(r['id'])!=5:raise ValueError('completion withoutAVAILABLE')
    if raw['metrics']['completed']!=sum(r['status']=='succeeded' for r in raw['ledger']):raise ValueError('completed arithmetic')
    return dict(events=len(raw['events']),actual_available_contract=True,nonpreemptive=True)

class Budget:
    def __init__(self):
        self.reg=read(WORK/'registration.json');self.start=time.perf_counter();self.n=0;self.training=0;self.rows=[]
        if (WORK/'environment_receipts.jsonl').exists():raise ValueError('study already consumed')
        for k in ('sources','parents','dependencies','inputs'):
            for p,h in self.reg[k].items():
                if sha(p)!=h:raise ValueError('registered material changed:'+p)
    def receipt(self,**r):
        with (WORK/'environment_receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(at_utc=utc(),**r))+'\n')
    def run(self,c,p,role,controller,phase,training=False):
        if self.n>=CAP or time.perf_counter()-self.start>WALL-60:raise RuntimeError('finite environment/time budget')
        self.n+=1;self.training+=int(training);identity=f'{phase}_{role}_{c["identity"]}';tick=time.perf_counter()
        self.receipt(number=self.n,identity=identity,status='started',training=training)
        ctl=AuditedController(controller)
        try:
            physical_split='train' if phase=='TRAIN' else 'dev' if phase.startswith('DEV') else 'confirm'
            environment_seed=(947100000 if physical_split=='train' else 947200000 if physical_split=='dev' else 947300000)+c['arrival_seed']%100000
            raw=plant.simulate(p,c['requests'],ctl,split=physical_split,environment_seed=environment_seed)
            checks=physical_audit(raw,c['requests']);raw.update(identity=identity,case=c,role=role,phase=phase,decisions=ctl.decisions,decision_audits=ctl.audit,verification=checks,model_errors=ctl.errors)
            path=OUT/'raw'/f'{self.n:04}_{phase}_{role}.json.gz';path.parent.mkdir(exist_ok=True)
            with gzip.open(path,'wt',encoding='utf-8',compresslevel=4) as f:json.dump(raw,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            row=dict(number=self.n,phase=phase,role=role,case=c['identity'],device=c['device'],profile=c['profile'],family=c['family'],deadline_mode=c['deadline_mode'],arrival_seed=c['arrival_seed'],request_sha=c['request_sha256'],path=str(path.relative_to(OUT)),raw_sha=sha(path),ledger_sha=digest(raw['ledger']),events_sha=digest(raw['events']),**raw['metrics'])
            row.update(additional_energy_j=raw['cost_120']['additional_energy_j'],anchor_energy_j=raw['cost_120']['anchor_energy_j'],decisions=len(ctl.decisions),mask_audits=len(ctl.audit),model_errors=len(ctl.errors),active_pc_s=time.perf_counter()-tick)
            self.rows.append(row)
            table=OUT/'all_rows.csv';exists=table.exists()
            with table.open('a',encoding='utf-8-sig' if not exists else 'utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(row))
                if not exists:w.writeheader()
                w.writerow(row)
        except Exception as exc:
            self.receipt(number=self.n,identity=identity,status='failed',error=repr(exc));raise
        self.receipt(number=self.n,identity=identity,status='completed',training=training,active_pc_s=time.perf_counter()-tick,path=row['path'],sha=row['raw_sha'])
        return raw,ctl,row
    def progress(self,stage,**extra):
        save(OUT/'progress.json',dict(task=TASK,stage=stage,at_utc=utc(),environments=self.n,training_episodes=self.training,active_pc_s=time.perf_counter()-self.start,**extra))
        print(json.dumps(read(OUT/'progress.json')),flush=True)

def selection_key(rows):
    return (sum(r['incomplete'] for r in rows),sum(2*r['urgent_failure']+r['normal_failure'] for r in rows),sum(2*r['urgent_declared_failure']+r['normal_declared_failure'] for r in rows),sum(r['weighted_tardiness_s'] for r in rows),float(np.mean([r['energy_j'] if r['energy_j'] is not None else 1e9 for r in rows])),float(np.mean([r['mean_ap_c'] if r['mean_ap_c'] is not None else 1e9 for r in rows])))

def execute():
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    b=Budget();ps=read(WORK/'profiles.json');dev=read(WORK/'inputs/dev.json');train=read(WORK/'inputs/train.json');dependencies={Path(p).name:h for p,h in b.reg['sources'].items() if p.endswith('.py')};dependencies.update(policy_schema=policy.SCHEMA,profiles=sha(WORK/'profiles.json'))
    reference={};stage_rows={};learners={seed:rl.Learner(seed,dependencies) for seed in SEEDS};cp={};proof=[]
    for c in dev:
        p=ps[c['device']][c['profile']]
        for rule in policy.RULES:
            _,_,r=b.run(c,p,rule,policy.Controller(rule,affinity(p)), 'DEV_RULE')
            if rule=='ATC':reference[c['identity']]=r
        if b.n%48==0:b.progress('DEV_RULE')
    b.progress('TRAIN_128_START',planned_learning=384)
    for stage in (128,256):
        if stage==256:
            opportunity=False
            for seed in SEEDS:
                rows=stage_rows[seed,128]
                for r in rows:
                    ref=reference[r['case']]
                    a=(r['incomplete'],2*r['urgent_failure']+r['normal_failure'],2*r['urgent_declared_failure']+r['normal_declared_failure'])
                    z=(ref['incomplete'],2*ref['urgent_failure']+ref['normal_failure'],2*ref['urgent_declared_failure']+ref['normal_declared_failure'])
                    if a<z or a==z and a[0]==0 and r['energy_j'] is not None and ref['energy_j'] is not None and r['energy_j']<ref['energy_j']-1e-9 and r['mean_ap_c']<=ref['mean_ap_c']:opportunity=True
            stable=all(all(x['actor_changed'] and np.isfinite(x['actor_gradient_max']) for x in l.logs) for l in learners.values())
            reserve=time.perf_counter()-b.start<WALL-RESERVE
            save(OUT/'expansion_decision.json',dict(stage=128,opportunity=opportunity,stable=stable,reserve=reserve,expanded=opportunity and stable and reserve))
            if not(opportunity and stable and reserve):break
        for seed,l in learners.items():
            for i in range(l.episodes,stage):
                c=train[i];p=ps[c['device']][c['profile']];raw,ctl,r=b.run(c,p,f'PPO_{seed}',l.controller(deterministic=False,collect=True),'TRAIN',True)
                l.add(ctl,raw)
                if i==58:
                    path=WORK/'checkpoints'/f'PPO_{seed}_partial59.pt';l.save(path);saved=rl.canonical(l.snapshot());loaded=rl.Learner.load(path,dependencies)
                    if saved!=rl.canonical(loaded.snapshot()):raise ValueError('real partial59 optimizer/pending/RNG mismatch')
                    proof.append(dict(seed=seed,episode=59,partial=len(l.pending),optimizer_steps=l.steps,restore_exact=True,checkpoint_sha=sha(path)));learners[seed]=loaded;l=loaded
                if (i+1)%32==0:b.progress(f'TRAIN_{stage}',seed=seed,learner_episodes=l.episodes,updates=len(l.logs),optimizer_steps=l.steps)
            if l.pending:raise ValueError('stage pending experience')
            path=WORK/'checkpoints'/f'PPO_{seed}_ep{stage}.pt';l.save(path);cp[seed,stage]=path
            before=rl.canonical(l.snapshot());rows=[]
            for c in dev:
                _,_,r=b.run(c,ps[c['device']][c['profile']],f'PPO_{seed}_ep{stage}',l.controller(deterministic=True,collect=False),f'DEV_{stage}');rows.append(r)
            if rl.canonical(l.snapshot())!=before:raise ValueError('DEV changed weight/Adam/RNG')
            stage_rows[seed,stage]=rows;b.progress(f'DEV_{stage}_DONE',seed=seed,selection=list(selection_key(rows)))
    chosen={};selected=[]
    for seed in SEEDS:
        options=[(selection_key(rows),stage,rows) for (s,stage),rows in stage_rows.items() if s==seed];key,stage,rows=min(options,key=lambda v:(v[0],v[1]));path=cp[seed,stage];chosen[seed]=rl.Learner.load(path,dependencies)
        selected.append(dict(seed=seed,stage=stage,key=list(key),path=str(path),sha=sha(path)))
    representative=min(selected,key=lambda v:(v['key'],v['stage'],v['seed']))['seed']
    save(OUT/'selected_before_final.json',dict(at_utc=utc(),selected=selected,representative=representative,source_sha=b.reg['sources'],input_final_sha=b.reg['inputs'][str(WORK/'inputs/final.json')],read_final_for_selection=False))
    save(OUT/'partial59_proof.json',proof)
    states={seed:rl.canonical(l.snapshot()) for seed,l in chosen.items()}
    b.progress('FINAL_FIXED_START',representative=representative)
    final=read(WORK/'inputs/final.json');ablation=read(WORK/'inputs/ablation.json')
    for c in final:
        p=ps[c['device']][c['profile']]
        for rule in policy.RULES:b.run(c,p,rule,policy.Controller(rule,affinity(p)),'FINAL')
        for seed,l in chosen.items():b.run(c,p,f'PPO_{seed}',l.controller(deterministic=True,collect=False),'FINAL')
        if b.n%36==0:b.progress('FINAL_FIXED')
    for c in ablation:
        p=ps[c['device']][c['profile']]
        for rule in ('FIFO_READY','ATC','RR_READY'):b.run(c,p,rule,policy.Controller(rule,affinity(p)),'ABLATION')
        b.run(c,p,'PPO_REP',chosen[representative].controller(deterministic=True,collect=False),'ABLATION')
        if b.n%32==0:b.progress('ABLATION_FIXED')
    if any(states[seed]!=rl.canonical(l.snapshot()) for seed,l in chosen.items()):raise ValueError('FINAL changed frozenlearner')
    for seed,l in learners.items():save(OUT/'learning'/f'PPO_{seed}.json',dict(episodes=l.episodes,updates=len(l.logs),optimizer_steps=l.steps,logs=l.logs,episode_logs=l.episode_logs))
    save(OUT/'consumption.json',dict(environments_started=b.n,environments_completed=b.n,environments_failed=0,policy_training_episodes=b.training,native_updates=sum(len(l.logs) for l in learners.values()),optimizer_steps=sum(l.steps for l in learners.values()),fit=0,device=0,apk=0,external_messages=0,active_pc_s=time.perf_counter()-b.start,synthetic_fixture_updates_agent=6,synthetic_fixture_adam_agent=6))
    b.progress('COMPARISON_COMPLETE',final_cases=len(final),ablation_cases=len(ablation));shutil.copy2(WORK/'environment_receipts.jsonl',OUT/'environment_receipts.jsonl')

def main():
    a=argparse.ArgumentParser();a.add_argument('stage',choices=('register','execute'));args=a.parse_args();register() if args.stage=='register' else execute()
if __name__=='__main__':main()
