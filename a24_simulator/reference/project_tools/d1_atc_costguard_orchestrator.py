"""One six-hour registered run, exact boundary stops and one final freeze."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from tools import d1_atc_costguard_study as s


def status(root, **values):
    path=Path(root)/"orchestration.json"
    old=s.budget.read(path)
    old.update(values,updated_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid())
    s.write(path,old)


def start(root,label,args):
    reg=s.check(root)
    (root/"logs").mkdir(exist_ok=True)
    stream=(root/"logs"/(label+".log")).open("a",encoding="utf8")
    command=[sys.executable,"-B","-m","tools.d1_atc_costguard_study",*args,"--run-root",str(root)]
    env=os.environ.copy()
    patch=Path(reg["io_supplement"]["path"])
    env["PYTHONPATH"]=str(patch.parent)+os.pathsep+str(s.ROOT)+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["D1_ATC_IO_PATCH_SHA"]=reg["io_supplement"]["sha256"]
    env["D1_ATC_IO_RETRY_LOG"]=str(root/"io_retry_events.jsonl")
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    process=subprocess.Popen(command,cwd=s.ROOT,stdout=stream,stderr=subprocess.STDOUT,env=env,creationflags=flags)
    stream.close()
    return label,process,command


def await_all(root,jobs):
    pending=list(jobs)
    while pending:
        for job in list(pending):
            label,process,command=job;code=process.poll()
            if code is None:continue
            if code:
                (root/"models"/"REQUEST_STOP").touch()
                status(root,status="needs_attention",failed_label=label,exit_code=code,command=command)
                raise RuntimeError("worker failed; preserve consumed ledger and checkpoint: "+label)
            pending.remove(job)
        if pending:time.sleep(2)


def shared_stop(stops):
    damage=next((value for value in stops.values() if value=="two_transition_service_P95_damage_at_two_seeds"),None)
    if damage:return damage
    if all(value=="three_additional_stage_stagnation" for value in stops.values()):return "all_reward_arms_three_stage_stagnation"
    return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-root",type=Path,required=True)
    args=parser.parse_args();root=args.run_root.resolve()
    # Registration is deliberately a separate explicit command.
    reg=s.check(root)
    if (root/"final_rows.json").exists():return
    status(root,status="running",deadline_unix=reg["deadline_unix"],learning_episode_count_cap=None)
    try:
        if not (root/"freeze.json").exists():
            if not(root/"partial59_audit.json").exists():
                status(root,phase="actual59_firstseed_native_partial")
                await_all(root,[start(root,"partial59",["train","--through","512","--stop-after","59","--first-seed-only"])])
                pause=s.budget.read(root/"models/pause_receipt.json");proof={}
                import torch
                for role,item in pause["models"].items():
                    arm,ss=role.rsplit("_",1);learner=s.learning.Learner.load(root/"models/paused_checkpoints"/(role+".pt"),s.deps(reg,arm))
                    if s.parent.payload_digest(learner.snapshot())!=item["digest"]:raise ValueError("actual59 payload mismatch")
                    clone=s.learning.Learner.from_snapshot(learner.snapshot(),learner.dependencies)
                    if not torch.equal(torch.rand(5,generator=learner.action_rng),torch.rand(5,generator=clone.action_rng)) or not torch.equal(torch.randperm(17,generator=learner.shuffle_rng),torch.randperm(17,generator=clone.shuffle_rng)):raise ValueError("actual59 RNG mismatch")
                    proof[role]=dict(episodes=learner.episodes,pending=len(learner.pending),native_updates=len(learner.logs),Adam_steps=learner.steps,exact=True)
                s.write(root/"partial59_audit.json",dict(status="PASS_actual59_native",models=proof,new_environments_in_audit=0,new_learning_in_audit=0))
            done=s.completed_stages(root);target=512 if not done else done[-1]*2
            durations=s.budget.read(root/"orchestration.json").get("stage_durations",[])
            while True:
                if time.time()+s.FINAL_RESERVE>=reg["deadline_unix"] or shutil.disk_usage(root).free<12*1024**3:
                    reason="time_or_disk_training_reserve";break
                status(root,phase="singleworker_roundrobin_fresh_reward_training",target_per_model=target,stage_durations=durations,concurrency=1,shared_host_with12=True)
                began=time.time();await_all(root,[start(root,f"train_{target}",["train","--through",str(target)])])
                elapsed=time.time()-began;completed=s.completed_stages(root)
                if target not in completed:reason="controlled_partial_boundary_stop";break
                durations.append(dict(stage=target,wall_seconds=elapsed))
                stops={}
                for arm in s.ARMS:
                    histories={seed:[s.budget.read(root/"models"/f"stage{episode}.json")["models"][f"{arm}_{seed}"] for episode in completed] for seed in s.SEEDS}
                    stops[arm]=s.continuation_stop(histories)
                stop=shared_stop(stops)
                s.write(root/"development_continuation.json",dict(completed_by_all_models=completed,stage_durations=durations,arm_three_seed_stops=stops,
                    stop_scope="shared stop if anyarm meets2ofits3seeds damage over2transitions; stagnation onlyifall3arms meet3additionalstage criterion; firsttrained512 isreference checkpoint",confirmation_read=False))
                status(root,phase="completed_development_stage",completed_by_all_models=completed,stage_durations=durations)
                if stop:reason="development_stop_"+stop;break
                if time.time()+max(elapsed*2,900)+s.FINAL_RESERVE>=reg["deadline_unix"]:reason="predicted_next_stage_time_reserve";break
                target*=2
            status(root,phase="development_only_selection",training_stop_reason=reason)
            s.select_and_freeze(root)
        status(root,phase="one_frozen_new_confirmation")
        jobs=[start(root,"control_confirmation",["controls","--phase","confirmation"])]
        jobs += [start(root,"model_confirmation",["confirm"])]
        await_all(root,jobs)
        result=s.merge(root)
        status(root,status="completed",phase="report_pending",result=result)
        from tools import d1_atc_costguard_report as report
        report.report(root)
        status(root,status="completed",phase="reported")
    except BaseException as error:
        status(root,status="needs_attention",error=repr(error),traceback=traceback.format_exc())
        raise


if __name__=="__main__":main()
