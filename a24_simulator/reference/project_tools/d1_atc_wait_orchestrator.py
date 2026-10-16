"""Overnight continuation with unbounded episode-count milestones and one final freeze."""
import argparse,json,os,shutil,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_atc_wait_study as s

def write_status(root,**values):
    path=root/'orchestration.json';old=s.budget.read(path) if path.exists() else {}
    old.update(values,updated_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid())
    s.write(path,old)
def start(root,label,args):
    logs=root/'logs';logs.mkdir(exist_ok=True)
    f=(logs/(label+'.log')).open('a',encoding='utf8')
    cmd=[sys.executable,'-B','-m','tools.d1_atc_wait_study',*args,'--run-root',str(root)]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    p=subprocess.Popen(cmd,cwd=s.ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=flags)
    f.close();return label,p,cmd
def await_all(root,jobs):
    pending=list(jobs)
    while pending:
        for job in list(pending):
            label,p,cmd=job;code=p.poll()
            if code is not None:
                if code:
                    for _,other,_ in pending:
                        if other is not p and other.poll() is None:
                            # Stop only at the next environment boundary; preserve state.
                            for seed in s.SEEDS:(root/f'seed{seed}'/'REQUEST_STOP').touch()
                    write_status(root,status='needs_attention',failed_label=label,exit_code=code,command=cmd)
                    raise RuntimeError(f'{label} failed, inspect saved log without resetting')
                pending.remove(job)
        if pending:time.sleep(2)
def stages_done(root):
    sets=[{int(p.stem[5:]) for p in (root/f'seed{seed}').glob('stage*.json')} for seed in s.SEEDS]
    return sorted(set.intersection(*sets)) if all(sets) else []
def stage_improvement(root,stage):
    teacher=[r for r in s.rows(root/'controls','development_') if r['policy']=='RuleATC'];ref={r['condition']:r for r in teacher}
    arm_success={arm:[] for arm in s.ARMS}
    for seed in s.SEEDS:
        rr=s.rows(root/f'seed{seed}',f'dev{stage}_')
        for arm in s.ARMS:
            q=[r for r in rr if r['policy']==f'{arm}_{seed}'];good=s.eligible(q,teacher)
            for r in s.primary(q):
                for key in ('energy_j','peak_ap_c'):
                    good=good and r[key] is not None and ref[r['condition']][key] is not None and r[key]<=ref[r['condition']][key]
            gain=sum(ref[r['condition']]['energy_j']-r['energy_j'] for r in s.primary(q))/max(len(s.primary(q)),1)
            arm_success[arm].append(bool(good and gain>=.005))
    return {arm:all(v) for arm,v in arm_success.items()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--run-root',type=Path,required=True);p.add_argument('--hours',type=float,default=6);x=p.parse_args();root=x.run_root
    if not root.exists():s.register(root)
    s.check(root)
    if (root/'final_rows.json').exists():return
    status=s.budget.read(root/'orchestration.json') if (root/'orchestration.json').exists() else {}
    deadline=status.get('deadline_unix',time.time()+x.hours*3600)
    write_status(root,status='running',deadline_unix=deadline,learning_episode_count_cap=None)
    try:
        if not (root/'controls/cursor.json').exists() or s.budget.read(root/'controls/cursor.json').get('stage') not in ('development','confirmation'):
            write_status(root,phase='teacher_and_control_development')
            await_all(root,[start(root,'control_development',['controls','--phase','development'])])
        done=stages_done(root);target=512 if not done else done[-1]*2
        history=status.get('stage_history',[])
        # Previously consumed identities are never reset; resume partial accepted rollouts.
        if not (root/'freeze.json').exists():
            if not (root/f'seed{s.SEEDS[0]}/pause_receipt.json').exists():
                write_status(root,phase='native_partial_resume_proof')
                await_all(root,[start(root,'partial59',['train','--seed',str(s.SEEDS[0]),'--through','512','--stop-after','59'])])
                child=root/f'seed{s.SEEDS[0]}';reg=s.check(root);proof=s.budget.read(child/'pause_receipt.json')
                checked={}
                for arm in s.ARMS:
                    l=s.learning.Learner.load(child/'paused_checkpoints'/f'{arm}_{s.SEEDS[0]}.pt',s.deps(reg,arm))
                    if s.payload_digest(l.snapshot())!=proof['digests'][arm]:raise ValueError('partial snapshot mismatch')
                    import torch
                    clone=s.learning.Learner.from_snapshot(l.snapshot(),l.dependencies)
                    if not torch.equal(torch.rand(5,generator=l.action_rng),torch.rand(5,generator=clone.action_rng)):raise ValueError('action RNG restore')
                    if not torch.equal(torch.randperm(17,generator=l.shuffle_rng),torch.randperm(17,generator=clone.shuffle_rng)):raise ValueError('shuffle RNG restore')
                    checked[arm]=dict(partial=len(l.pending),episodes=l.episodes,steps=l.steps,exact=True)
                s.write(root/'partial59_audit.json',dict(status='PASS',models=checked,new_environments=0,new_learning=0))
            while True:
                write_status(root,phase='parallel_training',target_per_model=target,stage_history=history)
                began=time.time();await_all(root,[start(root,f'train_{seed}_{target}',['train','--seed',str(seed),'--through',str(target)]) for seed in s.SEEDS])
                elapsed=time.time()-began;success=stage_improvement(root,target)
                history.append(dict(stage=target,wall_seconds=elapsed,all_three_seed_arms_nondegrading=success))
                s.write(root/'development_continuation.json',dict(history=history,criterion='preregistered percondition service/P95/cost dev improvement3seed stable2windows, else continue while time/disk permits; not final-guided'))
                write_status(root,phase='development_checkpoint',completed_stage=target,stage_history=history)
                stable=target>=2048 and len(history)>=2 and any(success[arm] and history[-2]['all_three_seed_arms_nondegrading'].get(arm,False) for arm in s.ARMS)
                enough_time=time.time()+max(2*elapsed,900)+1800<deadline
                enough_disk=shutil.disk_usage(root).free>12*1024**3
                if stable or not enough_time or not enough_disk:
                    write_status(root,training_stop_reason='stable_development_evidence' if stable else 'overnight_time_and_checkpoint_reserve' if not enough_time else 'raw_disk_preservation_reserve')
                    break
                target*=2
            write_status(root,phase='development_only_selection')
            for seed in s.SEEDS:s.select(root,seed)
            s.freeze(root)
        write_status(root,phase='frozen_new_confirmation')
        jobs=[start(root,'control_confirmation',['controls','--phase','confirmation'])]
        jobs += [start(root,f'confirm_{seed}',['confirm','--seed',str(seed)]) for seed in s.SEEDS]
        await_all(root,jobs);result=s.merge(root)
        write_status(root,status='completed',phase='report_pending',result=result)
        from tools import d1_atc_wait_report as report
        report.report(root)
        write_status(root,status='completed',phase='reported',report=str(s.ROOT.parent.parent/'outputs/ATC-WAIT-EXPAND-10/RESULTS.md'))
    except BaseException as error:
        write_status(root,status='needs_attention',error=repr(error),traceback=traceback.format_exc())
        raise
if __name__=='__main__':main()
