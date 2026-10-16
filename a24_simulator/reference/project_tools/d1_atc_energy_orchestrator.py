"""One serial worker for fresh paired rewards; no registration side effect."""
import argparse
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from tools import d1_atc_energy_study as s


def status(root, **values):
    path = Path(root) / "orchestration.json"; previous = s.budget.read(path)
    previous.update(values, updated_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid())
    s.write(path, previous)


def run_worker(root, label, arguments):
    reg = s.check(root); (root / "logs").mkdir(exist_ok=True)
    command = [sys.executable, "-B", "-m", "tools.d1_atc_energy_study", *arguments, "--run-root", str(root)]
    env = os.environ.copy(); supplement = Path(reg["io_supplement"]["path"])
    env["PYTHONPATH"] = str(supplement.parent) + os.pathsep + str(s.ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["D1_ATC_IO_PATCH_SHA"] = reg["io_supplement"]["sha256"]
    env["D1_ATC_IO_RETRY_LOG"] = str(root / "io_retry_events.jsonl")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (root / "logs" / (label + ".log")).open("a", encoding="utf8") as stream:
        process = subprocess.Popen(command, cwd=s.ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, creationflags=flags)
        status(root, worker_pid=process.pid, worker_label=label, worker_command=command)
        code = process.wait()
    if code:
        (root / "worker" / "REQUEST_STOP").touch()
        raise RuntimeError(f"serial worker failed: {label}, exit={code}; preserve ledger/checkpoints")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--run-root", type=Path, required=True)
    root = parser.parse_args().run_root.resolve(); reg = s.check(root)
    if (root / "final_rows.json").exists():
        return
    lock = root / "orchestrator.lock"
    with lock.open("x", encoding="utf8") as stream:
        stream.write(str(os.getpid()))
    try:
        status(root, status="running", phase="serial_fresh_training", deadline_unix=reg["deadline_unix"], workers=1,
               shared_host_with12=True, numerical_episode_environment_cap=None)
        if not (root / "freeze.json").exists():
            stages = s.completed_stages(root); target = 512 if not stages else stages[-1] * 2
            durations = s.budget.read(root / "orchestration.json").get("stage_durations", [])
            while True:
                if time.time() + s.FINAL_RESERVE >= reg["deadline_unix"] or shutil.disk_usage(root).free < 8 * 1024 ** 3:
                    reason = "wall_or_disk_training_reserve"; break
                began = time.time()
                for seed in s.SEEDS:
                    if s.stage_path(root, seed, target).exists():
                        continue
                    status(root, phase="serial_fresh_training", target_episode=target, seed=seed)
                    run_worker(root, f"train_{seed}_{target}", ["train", "--seed", str(seed), "--through", str(target)])
                    if not s.stage_path(root, seed, target).exists():
                        break
                completed = s.completed_stages(root); elapsed = time.time() - began
                if target not in completed:
                    reason = "controlled_partial_boundary_stop"; break
                durations.append(dict(stage=target, wall_seconds=elapsed, shared_host=True))
                history = s.histories(root, completed); stop = s.continuation_stop(history)
                s.write(root / "development_continuation.json", dict(completed_by_all12=completed, histories=history,
                        stage_durations=durations, stop_reason=stop, stop_receipt=s.continuation_receipt(history), confirmation_read=False))
                status(root, phase="common12_development_stage_completed", completed_by_all12=completed, stage_durations=durations)
                if stop:
                    reason = stop; break
                if time.time() + max(elapsed * 2, 900) + s.FINAL_RESERVE >= reg["deadline_unix"]:
                    reason = "predicted_next_stage_wall_reserve"; break
                target *= 2
            status(root, phase="development_only_selection", training_stop_reason=reason)
            s.select_and_freeze(root)
        status(root, phase="frozen_final176x21")
        run_worker(root, "confirm_all21_serial", ["confirm"])
        result = s.merge(root)
        status(root, status="completed", phase="report_pending", result=result)
        from tools import d1_atc_energy_report as report
        report.report(root)
        status(root, status="completed", phase="reported")
    except BaseException as error:
        status(root, status="needs_attention", error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
