"""Prepare saved TRAIN labels now; fit/evaluate only with extra budget approval."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import copy
import gc
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

H=Path(__file__).resolve().parent
A=H.parents[1]
R=A.parent
O=A/'results/A24_ATC_BC600_20261019_01'
S=A/'results/A24_S26_METHOD_20261019_01'
sys.path.insert(0,str(H.parent))
from a24_atc_bc_20261019 import load_components,VERSION
C=load_components()
from a24_atc_bc_20261019.learner import Learner
from a24_atc_bc_20261019.candidates import compatible_targets
from a24_bc_600_20261019 import study as old
from common_transfer import B,read,loadpt,pt,saved,np,torch,equal
sha,pin,new,stamp,verify=old.sha,old.pin,old.new,old.stamp,old.verify


class SavedNominal:
    """Public medians only. No realized bank.jobs or future data is exposed."""
    def __init__(self,values):self.values=values
    def vector(self,q,route,s):return list(self.values[q['request_id']+'|'+route])


def prepare():
    assert not (H/'TRAIN_FRAMES.pt.gz').exists()
    design=read(A/'experiments/a24_s26_method_20261019/INPUTS.json')
    rows=read(S/'RESULT.json')['rows']
    frames=[];sources=[];groups={};changed=ties=capped=0;records=[]
    power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
    config=read(A/'experiments/a24_parallel_20261018/OPERATION.json')['physics']
    shape=read(A/'experiments/a24_s26_method_20261019/SHAPE.json')
    for case in design['training']:
        row=next(r for r in rows if r['kind']=='DEMO' and r['profile']['id']=='ORIGINAL' and r['case']==case['id'])
        rawfile=S/(row['label']+'.raw.json.gz');bankfile=S/(case['id']+'.BANK.json.gz')
        assert sha(rawfile)==row['raw_sha256'] and sha(bankfile)==row['bank_sha256']
        raw=read(rawfile);nominal=SavedNominal(read(bankfile)['nominal_vectors'])
        physics=C.Physics(power,B.Config(**config),'ORIGINAL',shape)
        actor=C.Policy(nominal,physics,case,'TEACHER')
        before=len(frames)
        for d in raw['result']['decisions']:
            s=d['public_state']
            assert all(q['queue_entry_ns']<=s['now_ns'] for q in s['queue'])
            bank,actions=actor.encode(s)
            i=min(range(len(actions)),key=lambda i:(bank['scores'][i],i))
            target=np.zeros(36,bool);target[:len(actions)]=compatible_targets(s,actions,i)
            a=actions[i]
            group=(a['kind'] if a['kind']!='DISPATCH' else next(q for q in s['queue'] if q['request_id']==a['request_id'])['task']+'_'+a['route'])
            changed+=a!=d['action'];ties+=int(target.sum()>1)
            capped+=sum(f['capped'] for f in bank['forecasts'])
            groups[group]=groups.get(group,0)+1
            frames.append(dict(x=bank['x'],mask=bank['mask'],scores=bank['scores'],index=i,
                teacher_mask=target,group=group,time_ns=s['now_ns'],case=case['id'],
                source_decision_index=len(frames)-before,public_state_sha256=B.L.digest(s)))
        records.append(dict(case=case['id'],frames=len(frames)-before,source_raw=pin(rawfile),nominal_bank=pin(bankfile)))
        sources.extend([pin(rawfile),pin(bankfile)])
        print('PREPARED_TRAIN_STATES',case['id'],len(frames)-before,flush=True)
    assert len(frames)==1320 and all(f['x'].shape==(36,50) for f in frames)
    pt(H/'TRAIN_FRAMES.pt.gz',dict(version=VERSION,frames=frames,source=records))
    new(H/'DATASET.json',dict(status='PREPARED_NOT_TRAINED',utc=stamp(),version=VERSION,
        frames=len(frames),groups=groups,changed_teacher_actions=changed,
        compatible_multi_target_frames=ties,capped_forecasts=capped,source=sources,
        dataset=pin(H/'TRAIN_FRAMES.pt.gz'),train_case_ids=[c['id'] for c in design['training']],
        evaluation_cases_used=0,behavior_states='Archived original teacher trajectory states',
        labels='Relabelled by ATC candidate + corrected public rolling teacher',
        new_environment=0,new_BC_fit=0,new_PPO=0,new_measurement=0))


def propose():
    assert not (H/'PROPOSAL.json').exists()
    data=read(H/'DATASET.json');paths=[R/p['path'] for p in data['source']]
    ancestor=read(A/'experiments/a24_duration_040_20261019/OPERATION.json')
    for p in ancestor['pins']:
        local=old.relocate(p['path']);assert sha(local)==p['sha256'];paths.append(local)
    paths += [p for p in H.iterdir() if p.is_file() and p.suffix in ('.py','.md','.cjs','.json','.gz')]
    paths += list((H.parent/'a24_logic_repair_20261019').glob('*.py'))
    # Same frozen source S26 ATC formula, never its device coefficients.
    paths.append(H.parent/'s26_virtual_transfer_20261018/vendor/s26_simulator/experiments/route_group_learning_v1/policy.cjs')
    oldrows=read(A/'results/A24_BC_600_20261019_01/RESULT.json')['rows']
    paths += [R/r['raw']['path'] for r in oldrows]
    paths += [A/'results/A24_BC_600_20261019_01/RESULT.json']
    paths += [old.P/'RESULT.json',H.parent/'a24_bc_600_20261019/study.py']
    for case in old.cases():
        paths.append(old.P/(case['id']+'.PUBLIC.json'))
        for policy in ('FIFO_CPU','EDF_CPU','OLD_PPO'):
            paths.append(old.P/('ORIGINAL__DURATION__'+case['id']+'__'+policy+'.raw.json.gz'))
    git=lambda *a:subprocess.check_output(['git',*a],cwd=R,text=True,encoding='utf-8').strip()
    new(H/'PROPOSAL.json',dict(schema=VERSION,utc=stamp(),HEAD=git('rev-parse','HEAD'),
        working_tree=git('status','--short'),status='AWAITING_BUDGET_APPROVAL',
        budget=dict(current=137712,existing_cap=137712,new_BC_fit=1,new_EVAL=2,
                    additional_units=3,requested_cap=137715,refund=0),
        seed=20261019,BC_epochs=64,output_dir=O.relative_to(R).as_posix(),
        planned_START=3,new_training_environments=0,new_PPO=0,new_physical_fit=0,new_device=0,
        evaluation_cases=[c['id'] for c in old.cases()],dataset=data['dataset'],
        code_version=VERSION,pins=[pin(p) for p in sorted(set(paths))]))


def register():
    # This file may only be created after explicit human approval of the cap.
    approval=read(H/'BUDGET_APPROVAL.json')
    assert approval['approved'] is True and approval['approved_cap']>=137715
    assert isinstance(approval['user_message'],str) and len(approval['user_message'])>1
    op=read(H/'PROPOSAL.json');verify(op['pins'])
    assert not O.exists()
    op.update(status='APPROVED_REGISTERED',approval=pin(H/'BUDGET_APPROVAL.json'),
              approved_cap=approval['approved_cap'],registered_utc=stamp())
    new(H/'OPERATION.json',op)


def run():
    import msvcrt,psutil
    op=read(H/'OPERATION.json');verify(op['pins']);verify([op['approval']])
    assert op['status']=='APPROVED_REGISTERED' and op['approved_cap']>=137715 and not O.exists()
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False
    deadline=time.monotonic()+3600
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        if locked and len(processes)<=3 and psutil.virtual_memory().available>=1024**3 and __import__('shutil').disk_usage(R).free>=8*1024**3:break
        assert time.monotonic()<deadline,'Finite resource wait'
        time.sleep(5)
    rows=[];envcount=0;begin=time.monotonic();opsha=sha(H/'OPERATION.json');active_start=[None]
    try:
        O.mkdir();new(O/'START.json',dict(utc=stamp(),operation_sha256=opsha,HEAD=op['HEAD'],processes=processes))
        def receipt(event,label,kind,**extra):
            r=dict(event=event,label=label,kind=kind,utc=stamp(),durable_START_consumed=True,
                   start_id=B.L.digest([opsha,label]),**extra)
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
            active_start[0]=(label,kind) if event=='START' else None
            return r
        data=loadpt(R/op['dataset']['path']);assert data['version']==VERSION
        fit=receipt('START','ATC_BC_FIT','FIT')
        learner=Learner(op['seed'],True);pt(O/'BC.INITIAL.pt.gz',learner.snapshot())
        trace=learner.distill(data['frames'],op['BC_epochs'])
        snap=learner.snapshot();pt(O/'BC.FINAL.pt.gz',snap);pt(O/'BC.TRACE.pt.gz',trace)
        new(O/'BC_TRAINING.json',dict(status='COMPLETE',version=VERSION,epochs=len(trace['logs']),
            frames=len(data['frames']),groups=trace['groups'],final=trace['logs'][-1],
            network_sha256=snap['network_sha256'],EVAL_used_for_selection=False))
        receipt('COMPLETE','ATC_BC_FIT','FIT',checkpoint_sha256=sha(O/'BC.FINAL.pt.gz'))
        replayed=0
        for case in old.cases():
            assert envcount<2 and time.monotonic()-begin<3600
            public,contexts,parent=old.public_and_contexts(case)
            bankfile=old.D/'banks'/(case['id']+'.BANK.json.gz');bank=read(bankfile)
            physics=C.Physics(read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),
                B.Config(**parent['physics']),'ORIGINAL',read(old.PORT/'SHAPE.json'))
            model=B.BankModel(bank['jobs'],contexts)
            nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])])
            learner=Learner(state=snap);before=learner.snapshot()
            actor=C.Policy(nominal,physics,case,'BC',learner,False)
            label='ORIGINAL__ATC_BC600__'+case['id']+'__ATC_BC'
            rec=receipt('START',label,'EVAL');envcount+=1;episode=time.monotonic();last=[None]
            try:
                def guarded(s):
                    last[0]=s
                    if time.monotonic()-episode>1200 or time.monotonic()-begin>3600:raise ValueError('Finite wall cap')
                    if len(actor.calls)>max(1024,20*case['n']):raise ValueError('Finite policy call cap')
                    if __import__('shutil').disk_usage(R).free<4*1024**3:raise ValueError('Disk guard')
                    return actor(s)
                result=C.engine.run(public,model,guarded,physics,case['common_potential_key'],rec)
                metrics=C.engine.metrics(result,case,physics);score=old.objective.outcome(result,case,physics)
                raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id='ORIGINAL',slots=3,beta=.25)))
                pt(O/(label+'.FRAMES.pt.gz'),dict(frames=actor.frames,network_sha256=snap['network_sha256'],collect=False))
                replica=Learner(state=before)
                for f in actor.frames:
                    i,a=replica.choose({k:f[k] for k in ('x','mask','scores')},False)
                    assert i==f['index'] and a['old_logp']==f['old_logp'] and np.array_equal(a['value'],f['value']);replayed+=1
                equal(learner.snapshot(),before);equal(replica.snapshot(),before)
                row=dict(label=label,case=case['id'],condition=case['condition'],policy='ATC_BC',kind='EVAL',status='COMPLETE',n=case['n'],metrics=metrics,score=score,raw=pin(raw),bank=pin(bankfile),network_sha256=snap['network_sha256'])
                receipt('COMPLETE',label,'EVAL',raw_sha256=sha(raw));del result,replica
            except ValueError as e:
                if str(e) not in ('Decision cap','Integration cap','Finite wall cap','Finite policy call cap','Disk guard'):raise
                raw=O/(label+'.FAILED.json.gz');saved(raw,dict(calls=actor.calls,case=case,last_public_state=last[0],error=str(e),partial_not_complete_trace=True))
                row=dict(label=label,case=case['id'],policy='ATC_BC',status='FAIL',failure=str(e),metrics=None,score=None,raw=pin(raw),automatic_retry=False)
                receipt('FAIL',label,'EVAL',error=str(e),automatic_retry=False)
            new(O/(label+'.json'),row);rows.append(row)
            del actor,learner,model,bank;gc.collect()
        verify(op['pins']);failed=sum(r['status']=='FAIL' for r in rows)
        new(O/'REPLAY.json',dict(status='PASS',frames=replayed,collect=False,whole_checkpoint_two_Adam_and_all_RNG_unchanged=True,new_environment=0))
        new(O/'RESULT.json',dict(status='BATCH_COMPLETE',START=2,COMPLETE=2-failed,FAIL=failed,
            FIT_START=1,FIT_COMPLETE=1,total_scientific_START=3,rows=rows,checkpoint=pin(O/'BC.FINAL.pt.gz'),
            new_training=0,new_BC_fit=1,new_PPO=0,new_fit=0,new_device=0,elapsed_s=time.monotonic()-begin))
    except BaseException as e:
        if active_start[0] is not None:
            receipt('FAIL',active_start[0][0],active_start[0][1],error=str(e),automatic_retry=False)
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()


if __name__=='__main__':
    if '--prepare' in sys.argv:prepare()
    elif '--propose' in sys.argv:propose()
    elif '--register' in sys.argv:register()
    elif '--run' in sys.argv:run()
    else:print('Explicit --prepare/--propose/--register/--run required; no automatic work')
