"""Explicit evaluation-only follow-up of a sealed budget-stopped PPO v2 run."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
import uuid

from tools import d1_queue_ppo_v2 as v

VERSION = 'queue-ppo-frozen-evaluation-v1'
PLAN = v.design.BUNDLE/'evaluation_followup_plan_v1.json'


def load_plan():
    plan=json.loads(PLAN.read_text(encoding='utf8'))
    if plan['version']!=VERSION or plan['training_updates']!=0 or plan['device_commands']!=0:
        raise ValueError('evaluation-only contract')
    for name,sha in plan['runner_sources'].items():
        if v.q.p.digest(v.q.p.ROOT/name)!=sha:raise ValueError('evaluation source drift: '+name)
    return plan


def claim_path():
    return v.q.p.ROOT/'output'/('.queue_ppo_evaluation_'+v.q.p.digest(PLAN)+'.json')


def load_source(plan):
    root=v.q.p.ROOT/plan['source_output']
    for name,sha in plan['source_files'].items():
        if Path(name).name!=name or v.q.p.digest(root/name)!=sha:raise ValueError('sealed source changed: '+name)
    meta=json.loads((root/'checkpoint.json').read_text(encoding='utf8'))
    if meta['file'] not in ('state_0.pt','state_1.pt') or meta['status']!='budget_stopped':
        raise ValueError('source must remain budget_stopped')
    source=v.torch.load(root/meta['file'],map_location='cpu',weights_only=False)
    manifest=json.loads((root/'run_manifest.json').read_text(encoding='utf8'))
    if manifest['runtime']!=v.durable.Session.runtime() or source['plan']!=v.load_plan():
        raise ValueError('original runtime/analysis contract changed')
    receipt_name=json.loads((root/'LATEST_RECEIPT.json').read_text(encoding='utf8'))['file']
    receipt=json.loads((root/receipt_name).read_text(encoding='utf8'))
    if (source['version']!=v.VERSION or source['status']!='budget_stopped' or source['phase']!='test'
            or receipt['status']!='budget_stopped' or receipt['phase']!='test' or receipt['original_error'] is not None
            or source['counts']!=receipt['counts'] or source['counts']!=meta['counts']
            or source['generation']!=meta['generation'] or source['counts']!=plan['source_counts']):
        raise ValueError('source checkpoint/receipt boundary mismatch')
    v.durable.require_sources(source['sources'])
    freeze=json.loads((root/'freeze_before_test.json').read_text(encoding='utf8'))
    if freeze['selected']!=source['freeze'] or source['freeze']!=plan['actors']:
        raise ValueError('actors must be frozen before the original test')
    for actor in source['freeze']:
        if v.q.p.digest(root/actor['filename'])!=actor['sha256']:raise ValueError('frozen actor drift')
    start=source['test_index']; cases=source['config']['test']
    policies=source['plan']['baselines']+[f'{a["variant"]}_seed{a["seed"]}' for a in source['freeze']]
    expected=[(tuple(case),policy) for case in cases[:start] for policy in policies]
    rows=[((r['trace_seed'],r['family'],r['context']),r['policy']) for r in source['test_rows']]
    ledgers=[(tuple(r['case']),r['policy']) for r in source['test_ledgers']]
    if (start!=plan['completed_cases'] or len(cases)!=plan['total_cases'] or rows!=expected or ledgers!=expected
            or [list(case) for case in cases[start:]]!=plan['remaining_cases'] or len(set(rows))!=len(rows)
            or any(tuple(case) in source['refs'] for case in cases[start:])):
        raise ValueError('only a complete, unique case prefix can be continued without repetition')
    tests=len(cases[start:])*(len(policies)-1); refs=len(cases[start:])
    if plan['budget']['test']!=tests or plan['budget']['reference']!=refs:
        raise ValueError('evaluation budget mismatch')
    return source


def check(output=None):
    if v.q.LOCK.exists():raise ValueError('active or unresolved shared owner')
    if claim_path().exists():raise ValueError('evaluation already claimed; use clean Resume only')
    if output and Path(output).exists():raise ValueError('existing evaluation output; no restart')
    plan=load_plan();load_source(plan)
    return dict(status='CHECK_PASSED_NOT_STARTED',version=VERSION,plan_sha256=v.q.p.digest(PLAN),
        completed_cases=plan['completed_cases'],remaining_cases=len(plan['remaining_cases']),
        budget=plan['budget'],training_updates=0,device_commands=0,policy_simulations=0,claim_created=False)


class Session:
    def __init__(self,folder,resume=False,fixture=False,lock=None):
        self.folder=Path(folder);self.lock=lock or v.q.LOCK;self.id=uuid.uuid4().hex
        self.started=time.monotonic();self.pause_requested=False;self.inflight=None;self.pending=None
        v.q.prev.seed_all(0)
        if self.lock.exists():raise ValueError('active or unresolved shared owner')
        self.plan=load_plan();self.source=load_source(self.plan)
        if not fixture and resume:
            claim=json.loads(claim_path().read_text(encoding='utf8'))
            if claim['output']!=str(self.folder.resolve()):raise ValueError('evaluation claim ownership')
        if resume:
            meta=json.loads((self.folder/'checkpoint.json').read_text(encoding='utf8'))
            path=self.folder/meta['file']
            if meta['file'] not in ('state_0.json','state_1.json') or v.q.p.digest(path)!=meta['sha256']:
                raise ValueError('evaluation checkpoint integrity')
            self.s=json.loads(path.read_text(encoding='utf8'))
            latest=json.loads((self.folder/'LATEST_RECEIPT.json').read_text(encoding='utf8'))
            receipt=json.loads((self.folder/latest['file']).read_text(encoding='utf8'))
            if (self.s['status']!='paused' or receipt['status']!='paused' or self.s['version']!=VERSION
                    or self.s['counts']!=receipt['counts'] or self.s['plan_sha256']!=v.q.p.digest(PLAN)
                    or self.s['runtime']!=v.durable.Session.runtime() or self.s['generation']!=meta['generation']
                    or self.s['counts']!=meta['counts'] or len(self.s['artifacts'])!=self.s['cursor']
                    or receipt['completed_cases']!=self.plan['completed_cases']+self.s['cursor']):
                raise ValueError('no identical clean evaluation pause')
            for item in self.s['artifacts']:
                if v.q.p.digest(self.folder/item['file'])!=item['sha256']:raise ValueError('evaluation artifact drift')
            self.s['elapsed_s']=max(self.s['elapsed_s'],receipt['elapsed_s'])
            self.s['pause_intervals'].append(dict(start_utc=receipt['utc'],end_utc=datetime.now(timezone.utc).isoformat()))
            self.s['status']='running'
        else:
            if self.folder.exists():raise ValueError('existing evaluation output; no restart')
            if not fixture:
                if claim_path().exists():raise ValueError('evaluation already claimed')
                claim_path().parent.mkdir(parents=True,exist_ok=True)
                with claim_path().open('x',encoding='utf8') as f:
                    json.dump(dict(plan_sha256=v.q.p.digest(PLAN),output=str(self.folder.resolve()),run_id=self.id),f)
            self.folder.mkdir(parents=True,exist_ok=False)
            self.s=dict(version=VERSION,status='running',phase='evaluation',generation=0,cursor=0,elapsed_s=0.,
                counts=dict(test=0,reference=0),artifacts=[],pause_intervals=[],plan_sha256=v.q.p.digest(PLAN),
                runtime=v.durable.Session.runtime(),fixture_only=fixture)
            v.q.atomic(self.folder/'run_manifest.json',dict(version=VERSION,plan=self.plan,fixture_only=fixture,
                original_status_preserved='budget_stopped',training_updates=0,device_commands=0))
        self.elapsed_base=self.s['elapsed_s']
        with self.lock.open('x',encoding='utf8') as f:
            json.dump(dict(run_id=self.id,pid=os.getpid(),output=str(self.folder.resolve()),command=sys.argv),f)
        self.note('resumed' if resume else 'started')

    def elapsed(self):return self.elapsed_base+time.monotonic()-self.started

    def budget(self):
        b=self.plan['budget']
        if self.elapsed()>=b['active_limit_s']-b['receipt_reserve_s']:
            raise v.ActiveBudgetExceeded('evaluation budget; reserve termination time')

    def note(self,stage,**extra):
        data=dict(stage=stage,utc=datetime.now(timezone.utc).isoformat(),elapsed_s=self.elapsed(),
            completed_cases=self.plan['completed_cases']+self.s['cursor'],total_cases=self.plan['total_cases'],
            remaining_cases=len(self.plan['remaining_cases'])-self.s['cursor'],counts=self.s['counts'],**extra)
        v.q.atomic(self.folder/'progress.json',data)
        with (self.folder/'journal.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(data,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        print(json.dumps(data,allow_nan=False),flush=True)

    def save(self):
        self.s['generation']+=1;self.s['elapsed_s']=self.elapsed()
        name=f'state_{self.s["generation"]%2}.json'
        v.q.atomic(self.folder/name,self.s)
        v.q.atomic(self.folder/'checkpoint.json',dict(file=name,sha256=v.q.p.digest(self.folder/name),
            generation=self.s['generation'],status=self.s['status'],counts=self.s['counts']))

    def step(self):
        if self.s['cursor']==len(self.plan['remaining_cases']):
            self.write_report();self.s['phase']='done';return
        case=self.plan['remaining_cases'][self.s['cursor']];seed,family,context=case
        rows=[];ledgers=[]
        self.pending=dict(case=case,rows=rows,ledgers=ledgers)
        actors={f'{a["variant"]}_seed{a["seed"]}':a for a in self.plan['actors']}
        for policy in self.source['plan']['baselines']+list(actors):
            self.budget();actor=actors.get(policy);network=None
            if actor:
                path=v.q.p.ROOT/self.plan['source_output']/actor['filename']
                if v.q.p.digest(path)!=actor['sha256']:raise ValueError('frozen actor drift')
                network=v.q.load_actor(path)
            self.inflight=dict(case=case,policy=policy)
            row,result,_,_=v.simulate(self.source['frozen'],self.source['initial'],v.q.old.workload(family,seed),
                context,actor['variant'] if actor else policy,network,True)
            self.s['counts']['reference' if policy=='SHARED_EFT' else 'test']+=1;self.inflight=None
            rows.append(dict(trace_seed=seed,family=family,context=context,policy=policy,**row))
            ledgers.append(dict(case=case,policy=policy,ledger=result['ledger'],decisions=result.get('decisions')))
        name=f'case_{self.plan["completed_cases"]+self.s["cursor"]:03d}.json'
        path=self.folder/name
        if path.exists():raise ValueError('case artifact already exists; no repetition')
        v.q.atomic(path,dict(case=case,rows=rows,ledgers=ledgers))
        self.s['artifacts'].append(dict(file=name,sha256=v.q.p.digest(path),case=case))
        self.pending=None
        self.s['cursor']+=1;self.note('final_test')

    def write_report(self):
        self.budget()
        if v.q.p.digest(PLAN)!=self.s['plan_sha256'] or load_plan()!=self.plan:
            raise ValueError('evaluation plan changed during execution')
        v.durable.require_sources(self.source['sources'])
        for name,sha in self.plan['source_files'].items():
            if v.q.p.digest(v.q.p.ROOT/self.plan['source_output']/name)!=sha:
                raise ValueError('sealed source changed before report')
        if self.s['counts']!={k:self.plan['budget'][k] for k in ('test','reference')}:raise ValueError('evaluation counts')
        rows=list(self.source['test_rows'])
        def ledgers():
            yield from self.source['test_ledgers']
            for item in self.s['artifacts']:
                if v.q.p.digest(self.folder/item['file'])!=item['sha256']:raise ValueError('artifact drift')
                yield from json.loads((self.folder/item['file']).read_text(encoding='utf8'))['ledgers']
        for item in self.s['artifacts']:
            data=json.loads((self.folder/item['file']).read_text(encoding='utf8'));rows.extend(data['rows'])
        policies=len(self.source['plan']['baselines'])+len(self.plan['actors'])
        identities=[(r['trace_seed'],r['family'],r['context'],r['policy']) for r in rows]
        if len(rows)!=self.plan['total_cases']*policies or len(set(identities))!=len(rows):raise ValueError('combined evaluation denominator')
        v.q.old.csv_write(self.folder/'test.csv',rows)
        v.q.old.csv_write(self.folder/'validation.csv',self.source['validation_rows'])
        with (self.folder/'test_ledgers.jsonl').open('w',encoding='utf8') as f:
            for item in ledgers():f.write(json.dumps(item)+'\n')
            f.flush();os.fsync(f.fileno())
        v.report(self.folder,rows,self.source['plan'])
        v.q.atomic(self.folder/'summary.json',dict(version=VERSION,original_run_status='budget_stopped',
            combined_evaluation_complete=True,original_cases=self.plan['completed_cases'],followup_cases=self.s['cursor'],
            table_rows=len(rows),selected=self.plan['actors'],training_updates=0,policy_winner=None,accuracy_pass=None,
            logical_original_plus_followup={k:self.plan['source_counts'][k]+self.s['counts'].get(k,0) for k in self.plan['source_counts']},
            separate_time_budgets=True,experiment_ready=False,device_commands=0))

    def execute(self,pause_after=None):
        error=None;units=0
        try:
            self.save()
            while self.s['phase']!='done':
                try:self.budget();self.step()
                except v.ActiveBudgetExceeded as exc:
                    self.s['status']='budget_stopped';self.s['stop_reason']=str(exc);self.save();break
                units+=1;self.save()
                if self.pause_requested or (pause_after is not None and units>=pause_after):
                    self.s['status']='paused';self.save();break
            if self.s['phase']=='done':self.s['status']='completed';self.save()
        except BaseException as exc:
            error=dict(type=type(exc).__name__,message=str(exc),stack=traceback.format_exc())
            self.s['status']='interrupted_not_clean';v.q.atomic(self.folder/'ORIGINAL_ERROR.json',error);raise
        finally:
            partial_error=None
            if self.pending is not None:
                try:v.q.atomic(self.folder/'PARTIAL_CASE.json',self.pending)
                except Exception as later:partial_error=repr(later)
            receipt=dict(version=VERSION,status=self.s['status'],utc=datetime.now(timezone.utc).isoformat(),counts=self.s['counts'],
                completed_cases=self.plan['completed_cases']+self.s['cursor'],elapsed_s=self.elapsed(),
                original_error=error,inflight=self.inflight,stop_reason=self.s.get('stop_reason'),
                partial_case_completed_policies=len(self.pending['rows']) if self.pending else 0,
                partial_preservation_error=partial_error,
                training_updates=0,device_commands=0,experiment_ready=False)
            later_error=None
            try:
                name='RECEIPT_'+self.id+'.json';v.q.atomic(self.folder/name,receipt)
                v.q.atomic(self.folder/'LATEST_RECEIPT.json',dict(file=name,status=self.s['status']))
                self.note(self.s['status'],original_error=error)
            except Exception as later:
                later_error=later
                try:v.q.atomic(self.folder/'RECEIPT_ERROR.json',dict(original_error=error,receipt_error=repr(later)))
                except Exception:pass
            finally:
                if self.lock.exists() and json.loads(self.lock.read_text(encoding='utf8'))['run_id']==self.id:self.lock.unlink()
            if later_error and error is None:raise later_error
        return self.s['status']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action',choices=['check','run','resume','status'],default='check')
    parser.add_argument('--output',default='output/queue_ppo_v2_evaluation_v1')
    args=parser.parse_args()
    if args.action=='check':print(json.dumps(check(args.output),ensure_ascii=False,indent=2));return
    if args.action=='status':print((Path(args.output)/'progress.json').read_text(encoding='utf8'));return
    session=Session(args.output,resume=args.action=='resume')
    def pause(*_):
        if session.pause_requested:raise KeyboardInterrupt('second interrupt; not a clean pause')
        session.pause_requested=True;session.note('pause_requested_finish_current_case')
    signal.signal(signal.SIGINT,pause);session.execute()


if __name__=='__main__':main()
