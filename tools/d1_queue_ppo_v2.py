"""Feasible-primary queue PPO v2; explicit Run only, PC-only, original v1 intact."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import signal
import sys
import time
import traceback
import uuid

import numpy as np
import torch
from tools import d1_queue_ppo as q
from tools import d1_queue_ppo_resume as durable
from tools import d1_queue_ppo_design as design

VERSION = 'queue-ppo-feasible-durable-v2'


def load_plan():
    plan=json.loads(design.PLAN.read_text(encoding='utf8'))
    if plan!=design.specification(): raise ValueError('v2 contract/code mismatch')
    if plan['frozen_files']!={str(f.relative_to(q.p.ROOT)).replace('\\','/'):sha for f,sha in
                            [(q.p.BUNDLE/'model.json',q.p.MODEL_SHA),(q.p.BUNDLE/'initial_inputs.json',q.p.INITIAL_SHA)]}:
        raise ValueError('original model/initial SHA changed')
    q.p.inputs(q.p.BUNDLE)
    return plan


def source_hashes():
    return dict(durable.source_hashes(),**{str(f.relative_to(q.p.ROOT)).replace('\\','/'):q.p.digest(f) for f in
        [Path(__file__),Path(design.__file__),q.p.ROOT/'tools/RUN_QUEUE_PPO_V2.ps1',design.PLAN,design.BUNDLE/'preflight.json']})


def check_history(plan):
    groups=design.cases(plan); seeds={s for group in groups for s,_,_ in group}; conflicts=[]
    def scan(obj,path):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key=='seed' or key.endswith('_seed') or key.endswith('_seeds') or key.endswith('_seed_range'):
                    items=value if isinstance(value,list) else [value]
                    if any(type(v) is int and v in seeds for v in items): conflicts.append(str(path))
                scan(value,path)
        elif isinstance(obj,list):
            for value in obj: scan(value,path)
    for path in (q.p.ROOT/'docs/results').rglob('*.json'):
        if design.BUNDLE in path.parents or path.stat().st_size>20_000_000 or 'actor' in path.name: continue
        try: scan(json.loads(path.read_text(encoding='utf8')),path.relative_to(q.p.ROOT))
        except (UnicodeError,json.JSONDecodeError): continue
    # Original terminal-run plans are explicit accessible prior-run evidence.
    for path in (q.p.ROOT/'output').glob('queue_ppo_run_*/**/run_manifest.json'):
        obj=json.loads(path.read_text(encoding='utf8'))
        if obj.get('version')==VERSION: continue  # same-plan use is blocked by owner/output identity instead
        scan(obj,path.relative_to(q.p.ROOT))
        prior_cases=obj.get('inputs',{}).get('ordered_cases',[])
        if any(c[0] in seeds for group in prior_cases for c in group): conflicts.append(str(path))
    if conflicts: raise ValueError('registered seed already used: '+','.join(sorted(set(conflicts))))
    import csv
    for path in (q.p.ROOT/'docs/results').rglob('*.csv'):
        if design.BUNDLE in path.parents: continue
        with path.open(encoding='utf8',newline='') as f:
            reader=csv.DictReader(f);names=[k for k in (reader.fieldnames or []) if k in ('seed','trace_seed','arrival_seed')]
            if names and any(any(row[k].isdigit() and int(row[k]) in seeds for k in names) for row in reader):conflicts.append(str(path))
    if conflicts:raise ValueError('registered CSV seed already used: '+','.join(sorted(set(conflicts))))
    return 'accessible registered JSON/CSV/explicit prior terminal manifests; external unregistered history unknown'


def claim_path():
    return q.p.ROOT/'output'/('.queue_ppo_v2_consumed_'+q.p.digest(design.PLAN)+'.json')


def check(output=None):
    plan=load_plan()
    if q.LOCK.exists(): raise ValueError('active or unresolved owner; no duplicate execution')
    if claim_path().exists(): raise ValueError('v2 plan already claimed; no additional run/new-output bypass')
    if output is not None and Path(output).exists(): raise ValueError('existing/consumed output; no restart')
    certificate=design.preflight(plan,json.loads((q.p.BUNDLE/'model.json').read_text()))
    expected=json.loads((design.BUNDLE/'preflight.json').read_text(encoding='utf8'))
    if certificate!=expected: raise ValueError('frozen feasibility/input certificate mismatch')
    scope=check_history(plan)
    return dict(version=VERSION,status='CHECK_PASSED_NOT_STARTED',plan_sha256=q.p.digest(design.PLAN),
        certificate_sha256=q.p.digest(design.BUNDLE/'preflight.json'),sources=source_hashes(),
        input_and_certificate_sha256=certificate['input_and_certificate_sha256'],admission=certificate['counts'],
        budget=plan['budget'],runtime=durable.Session.runtime(),seed_history_scope=scope,
        device_commands=0,policy_simulations=0,training_updates=0,consumption_claim_created=False)


class Controller(q.Controller):
    """Same actions/features; causal decision evidence is logged separately."""
    def legal(self,queue,lanes,now):
        candidates,mask,delay,reason=super().legal(queue,lanes,now)
        active=self.active_jobs(lanes,now)
        if active is not None:
            for i,request in enumerate(candidates):
                legal=[a for a in (2*i,2*i+1) if mask[a]]
                predictions={a:self.place(request,('CPU','GPU')[a%2],now,active) for a in legal}
                on_time=[a for a,j in predictions.items() if j['response']<=j['deadline']+design.EPS]
                if on_time:
                    for a,j in predictions.items():
                        if j['response']>j['deadline']+design.EPS:mask[a]=False
        # Preserve progress when all routes are late; no fake feasibility claim.
        return candidates,mask,delay,reason

    def __call__(self,config,queue,lanes,now_ns,cfg,thermal_model,current_ap):
        out=super().__call__(config,queue,lanes,now_ns,cfg,thermal_model,current_ap)
        out['queue_snapshot']=[{k:x[k] for k in ('id','ordinal','task','priority','arrival_ns','deadline_offset_ns')} for x in queue]
        out['lane_snapshot']=copy.deepcopy(lanes)
        out['evidence_only_not_actor_features']=True
        now=now_ns/1e9; active=self.active_jobs(lanes,now)
        ordered=sorted(queue,key=lambda x:(0 if now-x['arrival_ns']/1e9>=self.age_limit(x) else 1 if x['priority']=='urgent' else 2,*self.due_key(x)))
        if ordered and active is not None:
            delay=min([.25]+[max(0.,self.age_limit(x)-(now-x['arrival_ns']/1e9)) for x in ordered])
            out['guard_mean_schedule_before']=self.schedule_score(ordered,active,now)
            out['guard_mean_schedule_after_wait']=self.schedule_score(ordered,active,now+delay)
            out['guard_wait_delay_s']=delay
        return out


def simulate(frozen,initial,tickets,context,variant,network=None,deterministic=True):
    if variant in ('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE'):
        row,result,controller,extra=q.simulate(frozen,initial,tickets,context,variant,network,deterministic)
        add_service_metrics(row,result);return row,result,controller,extra
    controller=Controller(frozen,initial,variant,network,deterministic)
    vectors=dict(cells={k:[dict(source_request_id='common_context_'+context,durations_ns=v) for _ in range(4)]
                       for k,v in q.p.profile(frozen,context).items()})
    result=q.old.engine.simulate(dict(protocol=q.p.VERSION,cells=q.p.profile(frozen)),vectors,tickets,
        policy=q.p.PPO_POLICY,settings=q.prev.settings(),seed=201,decision_provider=controller)
    row,extra=q.prev.outcome(result,initial,frozen)
    row.update(equal_work=all(r.get('lane_available_ns',math.inf)<=120e9 for r in result['ledger']),
        actions=controller.action_counts,controllable_decisions=controller.choices)
    add_service_metrics(row,result)
    return row,result,controller,extra


def add_service_metrics(row,result):
    missing=sum('response_ns' not in r for r in result['ledger'])
    lateness=[max(0.,(r['response_ns']-r['deadline_offset_ns'])/1e9) for r in result['ledger'] if 'response_ns' in r]
    row.update(total_lateness_s=sum(lateness) if not missing else None,max_lateness_s=max(lateness) if not missing else None,
        unrecorded_responses=missing,service_success_fraction=(row['planned']-row['urgent_service_failure']-row['normal_service_failure'])/row['planned'])


def costs(row,reference):
    values=q.costs(row,reference)
    values[2]=max(0.,values[2]) if row['thermal_degree_seconds']-reference['thermal_degree_seconds']>design.EPS else 0.
    values[3]=max(0.,values[3]) if row['peak_ap_c']-reference['peak_ap_c']>design.EPS else 0.
    return values


def rewards(controller,result,extra,initial,frozen,row,reference):
    channels=q.rewards(controller,result,extra,initial,frozen)
    # Same full J/service accounting, but thermal penalties cannot cancel
    # across episodes. Zero nonnegative expectation matches per-case intent.
    channels[:,3:]=0.
    channels[-1,3:]=costs(row,reference)[2:]
    return channels


def validation_key(rows,refs):
    values=[costs(r,ref) for r,ref in zip(rows,refs)]
    key=(sum(not r['equal_work'] for r in rows),sum(x[0]>0 or x[1]>0 for x in values),
        float(sum(x[0]+x[1] for x in values)),sum(x[2]>0 or x[3]>0 for x in values),
        float(sum(x[2]+x[3] for x in values)),float(np.mean([r['energy_j'] for r in rows])),
        float(np.mean([r['urgent_p95_ms'] if r['urgent_p95_ms'] is not None else math.inf for r in rows])),
        float(np.mean([r['normal_mean_ms'] if r['normal_mean_ms'] is not None else math.inf for r in rows])))
    return tuple(float(x) for x in key)  # JSON-safe, including numpy boolean sums


def fixture_config():
    return dict(fixture=True,learners=[('QUEUE',101)],train=[(101,'low','mean')],
        validation=[(102,'low','mean')],test=[(103,'low','mean'),(103,'queue','mean')],
        updates=1,batch=1,validation_updates=[1],expected=dict(training=1,validation=2,test=10,reference=4,smoke=0),
        active_limit_s=900,receipt_reserve_s=120)


def config(plan):
    train,val,test=design.cases(plan); b=plan['budget']
    return dict(fixture=False,learners=[(v,s) for v in plan['variants'] for s in plan['learning_seeds']],
        train=train,validation=val,test=test,updates=b['updates_per_learner'],batch=b['batch'],
        validation_updates=b['validation_updates'][1:],expected=b['counts'],
        active_limit_s=b['active_limit_s'],receipt_reserve_s=b['receipt_reserve_s'])


class Session(durable.Session):
    def __init__(self,folder,state=None,fixture=False,lock=None):
        self.folder=Path(folder); self.lock=lock or q.LOCK
        self.segment_start=time.monotonic(); self.pause_requested=False; self.network=self.optimizer=None
        self.id=uuid.uuid4().hex; q.prev.seed_all(0)
        durable.owner_absent(self.lock)
        if self.lock.exists(): raise ValueError('unresolved owner; no lock deletion')
        if state is None:
            plan=load_plan()
            if not fixture:
                prepared=check(self.folder)
                claim=claim_path();claim.parent.mkdir(parents=True,exist_ok=True)
                with claim.open('x',encoding='utf8') as f:
                    json.dump(dict(plan_sha256=q.p.digest(design.PLAN),output=str(self.folder.resolve()),run_id=self.id,
                                   created_utc=datetime.now(timezone.utc).isoformat(),automatic_restart=False),f)
            self.folder.mkdir(parents=True,exist_ok=False)
            frozen,case=q.p.inputs(q.p.BUNDLE); cfg=fixture_config() if fixture else config(plan)
            self.s=dict(version=VERSION,status='running',generation=0,elapsed_s=0.,sources=source_hashes(),
                config=cfg,plan=plan,frozen=frozen,initial={k:case['initial'][k] for k in ('preload','preload_power_w')},
                phase='init',learner=0,update=0,validation_index=0,test_index=0,refs={},ref_ledgers={},
                validation_rows=[],current_validation=[],selected=[],test_rows=[],test_ledgers=[],
                counts=dict(training=0,validation=0,test=0,reference=0,smoke=0),
                recovery={},pause_intervals=[],multipliers=None,best=None,best_update=None,best_actor=None,network=None,optimizer=None)
            q.atomic(self.folder/'run_manifest.json',dict(version=VERSION,plan=plan,sources=self.s['sources'],
                fixture_only=fixture,preflight={} if fixture else prepared,runtime=self.runtime(),device_commands=0))
        else:
            if state.get('version')!=VERSION or state['status']!='paused': raise ValueError('v2 requires its own clean paused state')
            durable.require_sources(state['sources']); self.s=state
            manifest=json.loads((self.folder/'run_manifest.json').read_text())
            if manifest['runtime']!=self.runtime(): raise ValueError('runtime changed')
            if q.p.digest(design.PLAN)!=manifest['sources'][str(design.PLAN.relative_to(q.p.ROOT)).replace('\\','/')]: raise ValueError('plan changed')
            if not state['config']['fixture']:
                claim=json.loads(claim_path().read_text())
                if claim['output']!=str(self.folder.resolve()) or claim['plan_sha256']!=q.p.digest(design.PLAN):raise ValueError('claim ownership mismatch')
            previous=json.loads((self.folder/'progress.json').read_text())
            now=datetime.now(timezone.utc); start=datetime.fromisoformat(previous['utc'])
            self.s['pause_intervals'].append(dict(start_utc=start.isoformat(),end_utc=now.isoformat(),wall_seconds=(now-start).total_seconds()))
            self.s['status']='running'; self.restore_network()
            random.setstate(state['python_rng']);np.random.set_state(state['numpy_rng']);torch.set_rng_state(state['torch_rng'])
        self.elapsed_base=self.s['elapsed_s'];self.lock.parent.mkdir(parents=True,exist_ok=True)
        with self.lock.open('x',encoding='utf8') as f:
            json.dump(dict(run_id=self.id,pid=durable.os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),output=str(self.folder.resolve()),command=sys.argv),f)
        self.note('resumed' if state else 'started')

    def episode(self,case,variant,network=None,deterministic=True):
        seed,family,context=case
        return simulate(self.s['frozen'],self.s['initial'],q.old.workload(family,seed),context,variant,network,deterministic)

    def reference(self,case):
        case=tuple(case)
        if case not in self.s['refs']:
            self.budget();row,result,_,_=self.episode(case,'SHARED_EFT')
            self.s['refs'][case]=row;self.s['counts']['reference']+=1
            if case in set(map(tuple,self.s['config']['test'])):
                self.s['ref_ledgers'][case]=dict(ledger=result['ledger'],decisions=result['decisions'])
        return self.s['refs'][case]

    def admit(self,case):
        seed,family,context=case
        cert=design.classify(q.old.workload(family,seed),self.s['frozen'],context)
        if family not in self.s['plan']['data']['primary_families'] or cert['status']!='feasible_witness':
            raise ValueError('no overload/unknown in primary training or validation')

    def step(self):
        s=self.s;cfg=s['config'];phase=s['phase']
        if phase=='train':
            variant,seed=cfg['learners'][s['learner']];update=s['update']+1
            episodes=[];violations=[];metrics=[];single=waits=0
            for case in cfg['train'][(update-1)*cfg['batch']:update*cfg['batch']]:
                self.admit(case);self.budget()
                row,result,c,extra=self.episode(case,variant,self.network,False);s['counts']['training']+=1
                ref=self.reference(case);violations.append(costs(row,ref));metrics.append(row)
                episodes.append((c,rewards(c,result,extra,s['initial'],s['frozen'],row,ref)))
                single+=sum(int(x['mask'].sum())==1 for x in c.rollout_data);waits+=c.action_counts[16]
            packed=q.pack(episodes); stats=q.prev.optimize(self.network,self.optimizer,packed,s['multipliers'])
            mean=np.mean(violations,axis=0);s['multipliers']=np.clip(s['multipliers']+5*mean,0.,100.);s['update']=update
            if update in cfg['validation_updates']: s.update(phase='validate',validation_index=0,current_validation=[])
            self.note('training',variant=variant,seed=seed,total_updates=cfg['updates'],learner_episodes=update*cfg['batch'],
                energy_J=float(np.mean([x['energy_j'] for x in metrics])),mean_costs=mean.tolist(),multipliers=s['multipliers'].tolist(),
                WAIT_actions=waits,single_legal_decisions=single,decisions=len(packed['actions']),
                returns_abs_mean=packed['returns'].abs().mean(0).tolist(),advantages_std=packed['advantages'].std(0,unbiased=False).tolist(),**stats)
            return
        if phase=='validate':
            variant,seed=cfg['learners'][s['learner']];case=cfg['validation'][s['validation_index']];self.admit(case)
            before=q.prev.model_hash(self.network);row=self.episode(case,variant,self.network)[0];ref=self.reference(case)
            if before!=q.prev.model_hash(self.network): raise ValueError('validation mutated actor')
            s['current_validation'].append((row,ref));s['counts']['validation']+=1
            s['validation_rows'].append(dict(variant=variant,seed=seed,update=s['update'],trace_seed=case[0],family=case[1],context=case[2],**row))
            s['validation_index']+=1
            if s['validation_index']==len(cfg['validation']):
                key=validation_key(*zip(*s['current_validation']))
                if s['best'] is None or key<tuple(s['best']): s.update(best=key,best_update=s['update'],best_actor=copy.deepcopy(self.network.state_dict()))
                self.note('validation_primary_only',variant=variant,seed=seed,selection_key=key)
                if s['update']==cfg['updates']:
                    s['selected'].append(dict(variant=variant,seed=seed,update=s['best_update'],key=s['best'],actor=copy.deepcopy(s['best_actor']),eligible=s['best'][0]==s['best'][1]==s['best'][3]==0))
                    s['learner']+=1;self.network=self.optimizer=None;s.update(network=None,optimizer=None,phase='init' if s['learner']<len(cfg['learners']) else 'freeze')
                else: s['phase']='train'
            return
        if phase=='test':
            case=cfg['test'][s['test_index']];ref=self.reference(case)
            for policy in s['plan']['baselines']:
                if policy=='SHARED_EFT': row=ref;result=s['ref_ledgers'][tuple(case)]
                else: row,result,_,_=self.episode(case,policy);s['counts']['test']+=1
                s['test_rows'].append(dict(trace_seed=case[0],family=case[1],context=case[2],policy=policy,**row))
                s['test_ledgers'].append(dict(case=case,policy=policy,ledger=result['ledger'],decisions=result.get('decisions'),
                    reference_decisions_recorded=policy=='SHARED_EFT'))
            for item in s['freeze']:
                path=self.folder/item['filename']
                if q.p.digest(path)!=item['sha256']: raise ValueError('frozen actor drift')
                row,result,_,_=self.episode(case,item['variant'],q.load_actor(path));s['counts']['test']+=1
                policy=f'{item["variant"]}_seed{item["seed"]}'
                s['test_rows'].append(dict(trace_seed=case[0],family=case[1],context=case[2],policy=policy,**row))
                s['test_ledgers'].append(dict(case=case,policy=policy,ledger=result['ledger'],decisions=result['decisions']))
            s['test_index']+=1
            if s['test_index']==len(cfg['test']):s['phase']='report'
            self.note('final_test',finished_cases=s['test_index'],total_cases=len(cfg['test']));return
        if phase=='report':
            if s['counts']!=cfg['expected']:raise ValueError('v2 exact budget mismatch')
            durable.require_sources(s['sources']);q.old.csv_write(self.folder/'test.csv',s['test_rows'])
            q.old.csv_write(self.folder/'validation.csv',s['validation_rows'])
            with (self.folder/'test_ledgers.jsonl').open('w',encoding='utf8') as f:
                for row in s['test_ledgers']:f.write(json.dumps(row)+'\n')
            report(self.folder,s['test_rows'],s['plan']);q.atomic(self.folder/'summary.json',dict(version=VERSION,
                counts=s['counts'],fixture_only=cfg['fixture'],selected=s['freeze'],policy_winner=None,accuracy_pass=None,device_commands=0))
            s['phase']='done';return
        return super().step()  # existing init/freeze/durable machinery

    def budget(self):
        c=self.s['config']
        if self.elapsed()>=c['active_limit_s']-c['receipt_reserve_s']:raise TimeoutError('active budget; reserve receipt time')

    def execute(self,pause_after=None):
        units=0;error=None
        try:
            self.save()
            while self.s['phase']!='done':
                try:self.budget()
                except TimeoutError:self.s['status']='budget_stopped';self.save();break
                self.step();units+=1;self.save()
                if self.pause_requested or (pause_after is not None and units>=pause_after):self.s['status']='paused';self.save();break
            if self.s['phase']=='done':self.s['status']='completed';self.save()
        except BaseException as exc:
            error=dict(type=type(exc).__name__,message=str(exc),stack=traceback.format_exc())
            self.s['status']='interrupted_not_clean';q.atomic(self.folder/'ORIGINAL_ERROR.json',error);raise
        finally:
            receipt=dict(version=VERSION,status=self.s['status'],phase=self.s['phase'],counts=self.s['counts'],
                elapsed_s=self.elapsed(),pause_intervals=self.s['pause_intervals'],original_error=error,
                device_commands=0,experiment_ready=False)
            later_error=None
            try:
                name='RECEIPT_'+self.id+'.json';q.atomic(self.folder/name,receipt)
                q.atomic(self.folder/'LATEST_RECEIPT.json',dict(file=name,status=receipt['status']));self.note(self.s['status'],original_error=error)
            except Exception as later:
                later_error=later
                try:q.atomic(self.folder/'RECEIPT_ERROR.json',dict(original_error=error,receipt_error=repr(later)))
                except Exception:pass
            finally:
                if self.lock.exists() and json.loads(self.lock.read_text())['run_id']==self.id:self.lock.unlink()
            if later_error is not None and error is None:raise later_error
        return self.s['status']


def report(folder,rows,plan):
    refs={(r['trace_seed'],r['family'],r['context']):r for r in rows if r['policy']=='SHARED_EFT'};paired=[]
    for row in rows:
        ref=refs[(row['trace_seed'],row['family'],row['context'])]
        eligible=all(x['equal_work'] and x['urgent_service_failure']==x['normal_service_failure']==0 for x in (row,ref))
        metrics=('energy_j','peak_ap_c','thermal_degree_seconds');valid=all(x[k] is not None for x in (row,ref) for k in metrics)
        item=dict(trace_seed=row['trace_seed'],family=row['family'],context=row['context'],policy=row['policy'],
            stratum='primary' if row['family'] in plan['data']['primary_families'] else 'overload_stress',
            planned=row['planned'],completed=row['completed'],urgent_failure=row['urgent_service_failure'],normal_failure=row['normal_service_failure'],
            urgent_failure_delta=row['urgent_service_failure']-ref['urgent_service_failure'],normal_failure_delta=row['normal_service_failure']-ref['normal_service_failure'],
            total_lateness_s=row['total_lateness_s'],max_lateness_s=row['max_lateness_s'],
            total_lateness_delta_s=row['total_lateness_s']-ref['total_lateness_s'] if row['total_lateness_s'] is not None and ref['total_lateness_s'] is not None else None,
            comparison_eligible=eligible and valid)
        for k in metrics:item['delta_'+k]=row[k]-ref[k] if eligible and valid else None
        ds=[item['delta_'+k] for k in metrics];item['joint_nonworsening']=bool(eligible and valid and all(d<=design.EPS for d in ds) and any(d < -design.EPS for d in ds))
        item['strict_joint_improvement']=bool(eligible and valid and all(d < -design.EPS for d in ds));paired.append(item)
    design.save_csv(Path(folder)/'paired_differences.csv',paired)
    text='<h1>PPO v2: primary / overload stress</h1><p>PC model results; accuracy and physical savings unverified. All cases in test.csv; stress cannot certify zero-miss adoption. Joint nonworsening and strict joint are separate.</p>'
    (Path(folder)/'index.html').write_text('<!doctype html><meta charset="utf-8">'+text,encoding='utf8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--action',choices=['check','run','resume','status','fixture'],default='check');parser.add_argument('--output')
    args=parser.parse_args()
    if args.action=='check':print(json.dumps(check(args.output),ensure_ascii=False,indent=2));return
    if not args.output:parser.error('--output is required')
    if args.action=='status':print((Path(args.output)/'progress.json').read_text(encoding='utf8'));return
    if args.action=='resume':session=Session(args.output,durable.read_state(args.output))
    else:session=Session(args.output,fixture=args.action=='fixture')
    def request_pause(*_):
        if session.pause_requested:raise KeyboardInterrupt('second interrupt; not a clean pause')
        session.pause_requested=True;session.note('pause_requested_finish_current_unit')
    signal.signal(signal.SIGINT,request_pause);session.execute()


if __name__=='__main__':main()
