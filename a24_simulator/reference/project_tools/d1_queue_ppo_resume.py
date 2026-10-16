"""Durable unit-boundary pause/resume for queue PPO, plus bounded legacy import.

Original queue runner stays byte-identical so an active old run is unaffected.
Resume is explicit, source-bound and never changes the policy or physical model.
"""
from __future__ import annotations
import argparse
import copy
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import time
import traceback
import uuid

import numpy as np
import torch
from tools import d1_queue_ppo as q

VERSION = 'queue-ppo-durable-resume-v1'


def source_hashes():
    return dict(q.hashes(), **{str(f.relative_to(q.p.ROOT)).replace('\\', '/'): q.p.digest(f) for f in
                [Path(__file__), q.p.ROOT/'tools/RUN_QUEUE_PPO_RESUMABLE.ps1']})


def require_sources(expected):
    for name, sha in expected.items():
        if q.p.digest(q.p.ROOT/name) != sha: raise ValueError('resume source drift: '+name)


def owner_absent(lock):
    if not lock.exists(): return
    record = json.loads(lock.read_text(encoding='utf8'))
    pid = record['pid']
    # An existing/reused/unknown PID blocks recovery. Never kill or infer identity
    # solely from PID. Normal graceful cancellation releases its own lock.
    if os.name != 'nt':
        try: os.kill(pid, 0)
        except ProcessLookupError: return
        raise ValueError('active or unknown owner: '+str(pid))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87: return
        raise ValueError('owner status unknown; no lock removal')
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]; kernel.CloseHandle(handle)
    raise ValueError('active/reused owner PID; wait for verified exit: '+str(pid))


def fixture_config():
    return dict(fixture=True, learners=[('HEAD',101),('QUEUE',101)], train=[(101,'queue','mean'),(102,'low','mean')],
        validation=[(103,'burst','mean')], test=[(104,'queue','short_context')], updates=2, batch=1,
        validation_updates=[1,2], expected=dict(training=4,validation=6,test=6,reference=4,smoke=0))


def config(plan):
    train, val, test = q.cases(plan)
    return dict(fixture=False, learners=[(v,s) for v in plan['variants'] for s in plan['learning_seeds']],
        train=train, validation=val, test=test, updates=256,batch=8,validation_updates=[64,128,192,256],
        expected=dict(training=12288,validation=1440,test=1920,reference=2288,smoke=0))


class Session:
    def __init__(self, folder, state=None, fixture=False, lock=None):
        self.folder = Path(folder); self.lock = lock or q.LOCK
        self.segment_start = time.monotonic(); self.pause_requested = False; self.network = self.optimizer = None
        self.id = uuid.uuid4().hex
        q.prev.seed_all(0)  # Thread1 and deterministic kernels also on resume.
        owner_absent(self.lock)
        if self.lock.exists(): raise ValueError('unresolved stale lock; original evidence must be reviewed')
        if state is None:
            self.folder.mkdir(parents=True, exist_ok=False)
            plan = q.load_plan(); cfg = fixture_config() if fixture else config(plan)
            frozen, case = q.p.inputs(q.p.BUNDLE)
            self.s = dict(version=VERSION,status='running',generation=0,elapsed_s=0.,sources=source_hashes(),
                config=cfg,plan=plan,frozen=frozen,initial={k:case['initial'][k] for k in ('preload','preload_power_w')},
                phase='init',learner=0,update=0,validation_index=0,test_index=0,refs={},ref_ledgers={},
                validation_rows=[],current_validation=[],selected=[],test_rows=[],test_ledgers=[],
                counts=dict(training=0,validation=0,test=0,reference=0,smoke=0),
                recovery=dict(reference_rebuild=0,replayed_training_max=0,replayed_validation_max=0),
                pause_intervals=[],
                multipliers=None,best=None,best_update=None,best_actor=None,network=None,optimizer=None)
            q.atomic(self.folder/'run_manifest.json',dict(version=VERSION,plan=plan,sources=self.s['sources'],
                fixture_only=fixture, inputs={} if fixture else q.input_manifest(plan),
                runtime=self.runtime(),observations=85,device_commands=0))
        else:
            self.s = state
            require_sources(state['sources'])
            if state['version'] != VERSION or state['status'] != 'paused': raise ValueError('no clean pause checkpoint')
            manifest = json.loads((self.folder/'run_manifest.json').read_text(encoding='utf8'))
            if manifest['runtime'] != self.runtime(): raise ValueError('runtime changed; exact resume refused')
            prior_progress=json.loads((self.folder/'progress.json').read_text(encoding='utf8'))
            if prior_progress['stage']=='paused':
                started=datetime.fromisoformat(prior_progress['utc'])
                now=datetime.now(timezone.utc)
                self.s.setdefault('pause_intervals',[]).append(dict(start_utc=started.isoformat(),end_utc=now.isoformat(),
                    wall_seconds=(now-started).total_seconds()))
            self.s['status'] = 'running'
            self.restore_network()
            random.setstate(state['python_rng']); np.random.set_state(state['numpy_rng']); torch.set_rng_state(state['torch_rng'])
        self.elapsed_base = self.s['elapsed_s']
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        with self.lock.open('x',encoding='utf8') as f:
            json.dump(dict(run_id=self.id,pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
                output=str(self.folder.resolve()),command=q.sys.argv),f)
        self.note('resumed' if state else 'started')

    @staticmethod
    def runtime():
        return dict(python=q.sys.version,torch=torch.__version__,numpy=np.__version__)

    def restore_network(self):
        if self.s['network'] is None: return
        self.network = q.ActorCritic(); self.network.load_state_dict(self.s['network'])
        self.optimizer = torch.optim.Adam(self.network.parameters(),lr=.0003,eps=1e-5)
        self.optimizer.load_state_dict(self.s['optimizer'])

    def elapsed(self): return self.elapsed_base+time.monotonic()-self.segment_start

    def note(self,stage,**fields):
        obj = dict(stage=stage,utc=datetime.now(timezone.utc).isoformat(),elapsed_s=self.elapsed(),
            phase=self.s['phase'],learner=self.s['learner'],update=self.s['update'],counts=self.s['counts'],**fields)
        q.atomic(self.folder/'progress.json',obj)
        with (self.folder/'journal.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(obj,allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())
        print(json.dumps(obj,allow_nan=False),flush=True)

    def save(self):
        self.s['generation'] += 1
        self.s['elapsed_s'] = self.elapsed()
        self.s.update(python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state())
        if self.network is not None:
            self.s.update(network=self.network.state_dict(),optimizer=self.optimizer.state_dict())
        filename = 'state_'+str(self.s['generation'] % 2)+'.pt'
        path = self.folder/filename; temporary = path.with_suffix('.tmp')
        with temporary.open('wb') as f:
            torch.save(self.s,f); f.flush(); os.fsync(f.fileno())
        os.replace(temporary,path)
        q.atomic(self.folder/'checkpoint.json',dict(version=VERSION,file=filename,sha256=q.p.digest(path),
            generation=self.s['generation'],status=self.s['status'],phase=self.s['phase'],counts=self.s['counts']))

    def reference(self,case):
        case = tuple(case)
        if case not in self.s['refs']:
            seed,family,context = case
            row,result,_,_ = q.simulate(self.s['frozen'],self.s['initial'],q.old.workload(family,seed),context,'SHARED_EFT')
            self.s['refs'][case] = row; self.s['counts']['reference'] += 1
            if case in set(map(tuple,self.s['config']['test'])): self.s['ref_ledgers'][case] = result['ledger']
        return self.s['refs'][case]

    def episode(self,case,variant,network=None,deterministic=True):
        seed,family,context = case
        return q.simulate(self.s['frozen'],self.s['initial'],q.old.workload(family,seed),context,variant,network,deterministic)

    def step(self):
        s = self.s; cfg = s['config']; phase = s['phase']
        if phase == 'restore_reference_cache':
            start=s['cache_restore_index']; end=min(start+16,len(s['cache_restore_cases']))
            for case in s['cache_restore_cases'][start:end]:
                s['refs'][tuple(case)]=self.episode(case,'SHARED_EFT')[0]
                s['recovery']['reference_rebuild']+=1
                if s['recovery']['reference_rebuild']>2096: raise ValueError('legacy cache rebuild bound')
            s['cache_restore_index']=end
            if end==len(s['cache_restore_cases']): s['phase']=s['after_cache_restore_phase']
            self.note('legacy_cache_rebuild',finished=end,total=len(s['cache_restore_cases']),recovery=s['recovery'])
            return
        if phase == 'init':
            variant,seed = cfg['learners'][s['learner']]
            q.prev.seed_all(seed); self.network = q.ActorCritic()
            self.optimizer = torch.optim.Adam(self.network.parameters(),lr=.0003,eps=1e-5)
            s.update(update=0,multipliers=np.array([10.,10.,1.,1.]),best=None,best_update=0,best_actor=None,
                     phase='validate',validation_index=0,current_validation=[])
            return
        if phase == 'train':
            variant,seed = cfg['learners'][s['learner']]; update = s['update']+1
            episodes=[]; violations=[]
            for case in cfg['train'][(update-1)*cfg['batch']:update*cfg['batch']]:
                row,result,c,extra = self.episode(case,variant,self.network,False)
                s['counts']['training'] += 1
                violations.append(q.costs(row,self.reference(case)))
                episodes.append((c,q.rewards(c,result,extra,s['initial'],s['frozen'])))
            stats = q.prev.optimize(self.network,self.optimizer,q.pack(episodes),s['multipliers'])
            s['multipliers'] = np.clip(s['multipliers']+5*np.mean(violations,axis=0),0.,100.)
            s['update'] = update
            if update in cfg['validation_updates']:
                s.update(phase='validate',validation_index=0,current_validation=[])
            self.note('training',variant=variant,seed=seed,total_updates=cfg['updates'],**stats)
            return
        if phase == 'validate':
            variant,seed = cfg['learners'][s['learner']]
            case = cfg['validation'][s['validation_index']]
            before = q.prev.model_hash(self.network)
            row = self.episode(case,variant,self.network)[0]; ref = self.reference(case)
            if before != q.prev.model_hash(self.network): raise ValueError('validation mutated actor')
            s['current_validation'].append((row,ref)); s['counts']['validation'] += 1
            s['validation_rows'].append(dict(variant=variant,seed=seed,update=s['update'],trace_seed=case[0],family=case[1],context=case[2],**row))
            s['validation_index'] += 1
            if s['validation_index'] == len(cfg['validation']):
                key = tuple(float(x) for x in q.validation_key(*zip(*s['current_validation'])))
                if s['best'] is None or key < tuple(s['best']):
                    s.update(best=key,best_update=s['update'],best_actor=copy.deepcopy(self.network.state_dict()))
                self.note('validation',variant=variant,seed=seed,selection_key=key)
                if s['update'] == cfg['updates']:
                    s['selected'].append(dict(variant=variant,seed=seed,update=s['best_update'],key=s['best'],
                        actor=copy.deepcopy(s['best_actor']),eligible=s['best'][0]==s['best'][1]==s['best'][3]==0))
                    s['learner'] += 1; self.network = self.optimizer = None
                    s.update(network=None,optimizer=None,phase='init' if s['learner'] < len(cfg['learners']) else 'freeze')
                else: s['phase'] = 'train'
            return
        if phase == 'freeze':
            require_sources(s['sources'])
            metadata=[]
            for item in s['selected']:
                net=q.ActorCritic(); net.load_state_dict(item['actor'])
                name=f'{item["variant"]}_seed{item["seed"]}.json'
                q.save_actor(self.folder/name,net)
                metadata.append(dict(variant=item['variant'],seed=item['seed'],update=item['update'],eligible=item['eligible'],
                    filename=name,sha256=q.p.digest(self.folder/name)))
            q.atomic(self.folder/'freeze_before_test.json',dict(selected=metadata,test_started=False,source_hashes=s['sources']))
            s.update(phase='test',test_index=0,freeze=metadata)
            self.note('actors_frozen',actors=len(metadata)); return
        if phase == 'test':
            case=cfg['test'][s['test_index']]; ref=self.reference(case)
            for policy in s['plan']['baselines']:
                if policy == 'SHARED_EFT': row=ref; ledger=s['ref_ledgers'][tuple(case)]
                else:
                    row,result,_,_=self.episode(case,policy); ledger=result['ledger']; s['counts']['test'] += 1
                s['test_rows'].append(dict(trace_seed=case[0],family=case[1],context=case[2],policy=policy,**row))
                s['test_ledgers'].append(dict(case=case,policy=policy,ledger=ledger))
            for item in s['freeze']:
                path=self.folder/item['filename']
                if q.p.digest(path) != item['sha256']: raise ValueError('frozen actor drift')
                net=q.load_actor(path); row,result,_,_=self.episode(case,item['variant'],net)
                s['counts']['test'] += 1
                policy=f'{item["variant"]}_seed{item["seed"]}'
                s['test_rows'].append(dict(trace_seed=case[0],family=case[1],context=case[2],policy=policy,**row))
                s['test_ledgers'].append(dict(case=case,policy=policy,ledger=result['ledger']))
            s['test_index'] += 1
            if s['test_index'] == len(cfg['test']): s['phase']='report'
            self.note('final_test',finished_cases=s['test_index'],total_cases=len(cfg['test'])); return
        if phase == 'report':
            if s['counts'] != cfg['expected']: raise ValueError('logical formal budget mismatch')
            require_sources(s['sources'])
            q.old.csv_write(self.folder/'test.csv',s['test_rows'])
            q.old.csv_write(self.folder/'validation.csv',s['validation_rows'])
            with (self.folder/'test_ledgers.jsonl').open('w',encoding='utf8') as f:
                for row in s['test_ledgers']: f.write(json.dumps(row)+'\n')
            if not cfg['fixture']: q.report(self.folder,s['test_rows'])
            q.atomic(self.folder/'summary.json',dict(counts=s['counts'],recovery=s['recovery'],fixture_only=cfg['fixture'],policy_winner=None))
            s['phase']='done'; return
        raise ValueError('unknown phase: '+phase)

    def execute(self,pause_after=None):
        units=0; error=None
        try:
            self.save()
            while self.s['phase'] != 'done':
                if self.elapsed() >= (900 if self.s['config']['fixture'] else 7200)-120:
                    self.s['status']='budget_stopped'; self.save(); break
                self.step(); units+=1; self.save()
                if self.pause_requested or (pause_after is not None and units >= pause_after):
                    self.s['status']='paused'; self.save(); break
            if self.s['phase']=='done': self.s['status']='completed'; self.save()
        except BaseException as exc:
            error=dict(type=type(exc).__name__,message=str(exc),stack=traceback.format_exc())
            # Do not certify an in-flight failure as an exact pause.
            self.s['status']='interrupted_not_clean'; q.atomic(self.folder/'ORIGINAL_ERROR.json',error)
            raise
        finally:
            receipt=dict(status=self.s['status'],phase=self.s['phase'],counts=self.s['counts'],
                elapsed_s=self.elapsed(),pause_intervals=self.s.get('pause_intervals',[]),
                recovery=self.s['recovery'],original_error=error,device_commands=0)
            receipt_error=None
            try:
                name='RECEIPT_'+self.id+'.json'; q.atomic(self.folder/name,receipt)
                q.atomic(self.folder/'LATEST_RECEIPT.json',dict(file=name,status=receipt['status']))
                self.note(self.s['status'],original_error=error)
            except Exception as later:
                receipt_error=later
                try: q.atomic(self.folder/'RECEIPT_ERROR.json',dict(original_error=error,receipt_error=repr(later)))
                except Exception: pass
                print('Receipt error: '+repr(later)+'; original='+repr(error),flush=True)
            finally:
                if self.lock.exists() and json.loads(self.lock.read_text())['run_id']==self.id: self.lock.unlink()
            if receipt_error is not None and error is None: raise receipt_error
        return self.s['status']


def read_state(folder):
    folder=Path(folder); meta=json.loads((folder/'checkpoint.json').read_text(encoding='utf8'))
    path=folder/meta['file']
    if meta['file'] not in ('state_0.pt','state_1.pt') or q.p.digest(path)!=meta['sha256']: raise ValueError('checkpoint integrity')
    state=torch.load(path,map_location='cpu',weights_only=False)
    if meta['generation'] != state['generation'] or state['status'] != 'paused': raise ValueError('checkpoint is not a clean pause')
    latest=folder/'LATEST_RECEIPT.json'
    if latest.exists():
        receipt=json.loads((folder/json.loads(latest.read_text())['file']).read_text())
        if receipt['status'] not in ('paused',): raise ValueError('receipt refuses resume')
        if receipt['counts']!=state['counts'] or receipt['phase']!=state['phase']:
            raise ValueError('stale receipt/checkpoint pair')
        state['elapsed_s']=max(state['elapsed_s'],receipt['elapsed_s'])
    return state


def import_legacy(root):
    """Import a gracefully stopped training checkpoint; preserve original folder.

    Legacy did not save the cache. Rebuild only deterministic SHARED_EFT rows,
    record recovery consumption, and never call the learner during the rebuild.
    """
    recovery_start=time.monotonic(); recovery_wall=datetime.now(timezone.utc)
    root=Path(root); owner_absent(q.LOCK)
    if q.LOCK.exists(): raise ValueError('unresolved owner lock')
    manifest=json.loads((root/'run_manifest.json').read_text(encoding='utf8'))
    require_sources(manifest['source_hashes'])
    if manifest['runtime'] != Session.runtime(): raise ValueError('legacy runtime mismatch')
    receipt=json.loads((root/'FINAL_RECEIPT.json').read_text(encoding='utf8'))
    if receipt['status'] != 'stopped_no_automatic_restart' or receipt.get('error',{}).get('type') != 'KeyboardInterrupt':
        raise ValueError('legacy import requires confirmed normal Ctrl+C; no completed/unknown/error run')
    if (root/'freeze_before_test.json').exists(): raise ValueError('legacy final-test resume lacks a durable case cursor; refused')
    notes=[json.loads(line) for line in (root/'journal.jsonl').read_text(encoding='utf8').splitlines()]
    training=[n for n in notes if n['stage']=='training']
    if not training: raise ValueError('no completed training boundary')
    last=training[-1]; plan=manifest['plan']; cfg=config(plan)
    pair=(last['variant'],last['seed']); index=cfg['learners'].index(pair)
    folder=root/f'{pair[0]}_seed{pair[1]}'; path=folder/'checkpoint.pt'; bootstrap=False
    if not path.exists() and index>0:
        index-=1; pair=cfg['learners'][index]; folder=root/f'{pair[0]}_seed{pair[1]}'; path=folder/'checkpoint.pt'
        if not path.exists(): raise ValueError('previous learner checkpoint missing')
    if path.exists(): ckpt=torch.load(path,map_location='cpu',weights_only=False)
    else:
        # Before the very first 16-update checkpoint, the registered seed and
        # persisted update0 actor bind the exact initial network/RNG boundary.
        q.prev.seed_all(pair[1]); initial_actor=q.ActorCritic()
        source=json.loads((folder/'selected_actor.json').read_text())
        if q.prev.model_hash(initial_actor)!=source['sha256']: raise ValueError('initial actor cannot be reconstructed')
        opt=torch.optim.Adam(initial_actor.parameters(),lr=.0003,eps=1e-5)
        ckpt=dict(network=initial_actor.state_dict(),optimizer=opt.state_dict(),update=0,
            multipliers=np.array([10.,10.,1.,1.]),torch_rng=torch.get_rng_state(),source_hashes=q.hashes())
        bootstrap=True
    update=ckpt['update']
    require_sources(ckpt['source_hashes'])
    if (last['variant'],last['seed'])==tuple(pair) and not 0<=last['update']-update<16:
        raise ValueError('ambiguous legacy checkpoint cursor')
    validation_notes=[n for n in notes if n['stage']=='validation' and
        (cfg['learners'].index((n['variant'],n['seed']))<index or
         ((n['variant'],n['seed'])==pair and n['update']<=update))]
    pending_validation=update in cfg['validation_updates'] and not any(
        (n['variant'],n['seed'])==pair and n['update']==update for n in validation_notes)
    # Build the durable shell in a new child directory. The old source/data and
    # original receipts remain untouched. Counts represent unique formal cases;
    # additional legacy replay is explicitly separate and bounded.
    restored_training=index*cfg['updates']*cfg['batch']+update*cfg['batch']
    replay=receipt['counts']['training']-restored_training
    if not 0<=replay<=127: raise ValueError('legacy replay bound')
    shell=Session(root/'resume_v1',fixture=False)
    shell.segment_start=recovery_start
    s=shell.s; s['elapsed_s']=receipt['elapsed_s']; shell.elapsed_base=receipt['elapsed_s']
    progress=json.loads((root/'progress.json').read_text(encoding='utf8'))
    if progress['stage']=='stopped_no_automatic_restart':
        since=datetime.fromisoformat(progress['utc'])
        s['pause_intervals'].append(dict(start_utc=since.isoformat(),end_utc=recovery_wall.isoformat(),
            wall_seconds=(recovery_wall-since).total_seconds(),kind='legacy_pause'))
    s.update(learner=index,update=update,phase='validate' if pending_validation else 'train')
    s['recovery'].update(replayed_training_max=replay,replayed_validation_max=0,
        unrecorded_inflight_simulation_range=[0,1])
    # Cache required by all past completed learners/current checkpoint.
    prefix=cfg['train'] if index else cfg['train'][:update*cfg['batch']]
    known=list(dict.fromkeys(map(tuple,[*prefix,*cfg['validation']])))
    try:
        import csv
        with (root/'validation.csv').open(encoding='utf8') as csv_stream:
            saved_rows=list(csv.DictReader(csv_stream))
        def parse_row(row):
            result={}
            for key,value in row.items():
                if key in ('variant','family','context'): result[key]=value
                elif not value: result[key]=None
                elif value in ('True','False'): result[key]=value=='True'
                else:
                    try: result[key]=json.loads(value)
                    except json.JSONDecodeError: result[key]=value
            return result
        for learner,p in enumerate(cfg['learners'][:index+1]):
            eligible_notes=[n for n in validation_notes if (n['variant'],n['seed'])==tuple(p)]
            if not eligible_notes: raise ValueError('missing legacy validation selection')
            best=min(eligible_notes,key=lambda n:(tuple(n['selection_key']),n['update']))
            source=root/f'{p[0]}_seed{p[1]}'/'selected_actor.json'
            actor=json.loads(source.read_text(encoding='utf8'))
            tensors={k:torch.tensor(v,dtype=torch.float32) for k,v in actor['tensors'].items()}
            net=q.ActorCritic(); net.load_state_dict(tensors)
            if q.prev.model_hash(net)!=actor['sha256']: raise ValueError('legacy selected tensor hash')
            if learner==index:
                if best['update']==update: tensors=copy.deepcopy(ckpt['network'])
                s.update(best=tuple(best['selection_key']),best_update=best['update'],best_actor=tensors)
            else:
                s['selected'].append(dict(variant=p[0],seed=p[1],update=best['update'],key=best['selection_key'],
                    actor=tensors,eligible=best['selection_key'][0]==best['selection_key'][1]==best['selection_key'][3]==0))
        allowed={(n['variant'],n['seed'],n['update']) for n in validation_notes}
        s['validation_rows']=[parse_row(r) for r in saved_rows if (r['variant'],int(r['seed']),int(r['update'])) in allowed]
        s['counts'].update(training=restored_training,validation=len(s['validation_rows']),reference=len(known))
        s['recovery']['discarded_legacy_reference']=receipt['counts']['reference']-len(known)
        if not 0<=s['recovery']['discarded_legacy_reference']<=127: raise ValueError('ambiguous discarded references')
        s['recovery']['replayed_validation_max']=receipt['counts']['validation']-len(s['validation_rows'])
        if not 0<=s['recovery']['replayed_validation_max']<=48: raise ValueError('ambiguous replay validation')
        if update==cfg['updates'] and not pending_validation:
            s['selected'].append(dict(variant=pair[0],seed=pair[1],update=s['best_update'],key=s['best'],actor=s['best_actor'],
                eligible=s['best'][0]==s['best'][1]==s['best'][3]==0))
            s['learner']+=1; s['phase']='init' if s['learner']<len(cfg['learners']) else 'freeze'
        else:
            s.update(network=ckpt['network'],optimizer=ckpt['optimizer'],multipliers=ckpt['multipliers'])
            shell.restore_network()
        s.update(after_cache_restore_phase=s['phase'],phase='restore_reference_cache',
                 cache_restore_cases=known,cache_restore_index=0)
        q.prev.seed_all(pair[1]); torch.set_rng_state(ckpt['torch_rng'])
        s['status']='paused'; shell.save()
        q.atomic(shell.folder/'LEGACY_IMPORT.json',dict(original=str(root),checkpoint_sha256=q.p.digest(path) if path.exists() else None,
            initial_actor_bootstrap=bootstrap,
            recovery=s['recovery'],original_counts=receipt['counts'],logical_restored_counts=s['counts'],
            cache_rebuild_target=len(known),
            exactness='Torch randomness restored; legacy uses no Python/NumPy random sampling after initialization',
            elapsed_total=shell.elapsed(),device_commands=0))
    finally:
        if shell.lock.exists() and json.loads(shell.lock.read_text())['run_id']==shell.id: shell.lock.unlink()
    return shell.folder


def run_cli(action,output,fixture=False,pause_after=None):
    folder=Path(output)
    if action=='resume':
        if not (folder/'checkpoint.json').exists():
            owner_absent(q.LOCK)
            folder=folder/'resume_v1' if (folder/'resume_v1/checkpoint.json').exists() else import_legacy(folder)
        state=read_state(folder)
        session=Session(folder,state,lock=folder.parent/'.resume_fixture_lock.json' if state['config']['fixture'] else None)
    else:
        if not fixture: q.check()
        session=Session(folder,fixture=fixture,lock=folder.parent/'.resume_fixture_lock.json' if fixture else None)
    def interrupt(*_):
        if session.pause_requested: raise KeyboardInterrupt('second interrupt: in-flight state not certified')
        session.pause_requested=True
        print('Pause requested: finishing this durable unit; wait for paused.',flush=True)
    original=signal.signal(signal.SIGINT,interrupt)
    try: return session.execute(pause_after=pause_after)
    finally: signal.signal(signal.SIGINT,original)


def main():
    parser=argparse.ArgumentParser(description='Explicit exact queue PPO pause/resume; PC only')
    parser.add_argument('--action',choices=['check','run','resume','status','smoke'],default='check')
    parser.add_argument('--output'); args=parser.parse_args()
    if args.action=='check': print(json.dumps(q.check(),indent=2),flush=True); return
    if not args.output: parser.error('--output required')
    if args.action=='status':
        folder=Path(args.output)
        if (folder/'resume_v1/progress.json').exists(): folder=folder/'resume_v1'
        print((folder/'progress.json').read_text(encoding='utf8'),flush=True); return
    run_cli(args.action,args.output,fixture=args.action=='smoke')


if __name__=='__main__': main()
