"""Explicit opt-in device operations for calibration; never imported by prepare/check."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_calibration as c
from tools import d1_arrival_timing_dev as v
from tools import d1_arrival_plan as p
from tools import d1_arrival_failure_evidence as failure_evidence


def package(output):
    output = Path(output).resolve()
    v.require(not output.exists(), "isolated build root must be new")
    output.mkdir(parents=True)
    before = c.code_identity()
    env = dict(os.environ, D1_TIMING_BUILD_ROOT=str(output / "build"))
    command = [str(c.ROOT / "gradlew.bat"), "--no-configuration-cache", "--init-script",
               str(c.ROOT / "tools/arrival_timing_isolated_build.gradle"),
               ":benchmark-runner:assembleModelProbe", "-PenableModelProbe=true", "--console=plain"]
    c.write_new(output / "build_attempt.json", dict(utc=legacy.utc(), command=command, source_code=before))
    with (output / "build.log").open("xb") as log:
        subprocess.run(command, cwd=c.ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    v.require(c.code_identity() == before, "source changed during build")
    apks = list((output / "build").glob("*/outputs/apk/modelProbe/*.apk"))
    v.require(len(apks) == 1, "one isolated modelProbe APK required")
    receipt = dict(status="built_not_device_verified", utc=legacy.utc(), source_code=before,
                   apk_path=str(apks[0]), apk_sha256=p.digest(apks[0]), command=command)
    c.write_new(output / "build_receipt.json", receipt)
    return receipt


def pull(device, sid, output):
    remote = f"files/{v.CAL_PROTOCOL}/{sid}"
    listing = device.call("shell", "run-as", legacy.PACKAGE, "ls", remote, check=False)
    if listing.returncode:
        if b'No such file or directory' in listing.stderr + listing.stdout:
            return {"status": "output_missing", "files": []}
        raise RuntimeError('artifact listing unavailable; not proof that app output is missing')
    output.mkdir(parents=True, exist_ok=True)
    files = []
    names = listing.stdout.decode().splitlines()
    # Preserve the identity/progress prefix first if a bounded failure pull is cut short.
    priority = {"manifest.json": 0, "failure_progress.jsonl": 1, "cleanup.json": 2}
    for name in sorted(names, key=lambda name: (priority.get(name, 3), name)):
        v.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,126}", name), "unsafe remote filename")
        data = device.call("exec-out", "run-as", legacy.PACKAGE, "cat", remote + "/" + name, timeout=45).stdout
        target = output / name
        if target.exists():
            v.require(target.read_bytes() == data, "recovery conflict; preserve both by using a new recovery root")
        else:
            with target.open("xb") as stream:
                stream.write(data)
        files.append({"name": name, "sha256": p.digest(target), "bytes": len(data)})
    return {"status": "recovered", "files": files}


def cleanup(device, hard_deadline=None):
    previous = device.deadline
    device.deadline = min(time.monotonic() + 45, hard_deadline if hard_deadline is not None else float('inf'))
    try:
        device.call("shell", "am", "force-stop", legacy.PACKAGE, timeout=15)
        legacy.require_stopped(device)
        thermal = device.call("shell", "dumpsys", "thermalservice", timeout=15).stdout
        v.require(re.search(rb"Thermal Status:\s*0\b", thermal), "post-session thermal gate")
        return {"status": "completed", "utc": legacy.utc(), "thermal": thermal.decode(errors="replace")}
    finally:
        device.deadline = previous


def stage_inputs(device, sid, manifest, sources):
    remote_input = f"files/arrival-scheduler-inputs/{sid}"
    remote_output = f"files/{v.CAL_PROTOCOL}/{sid}"
    shared = f"/data/local/tmp/d1check-timing-calibration/{sid}"
    for path, prefix in ((remote_input, ("run-as", legacy.PACKAGE)), (remote_output, ("run-as", legacy.PACKAGE)), (shared, ())):
        probe = device.call("shell", *prefix, "test", "-e", path, check=False)
        v.require(probe.returncode == 1 and not probe.stderr.strip() and not probe.stdout.strip(), "stale path or unavailable ADB; no reuse")
    device.call("shell", "mkdir", "-p", shared)
    device.call("shell", "run-as", legacy.PACKAGE, "mkdir", "-p", remote_input)
    for name, path in dict(sources, **{"manifest.json": manifest}).items():
        v.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,126}", name), "unsafe source filename")
        device.call("push", path, shared + "/" + name + ".part", timeout=90)
        target = remote_input + "/" + name
        device.call("shell", "run-as", legacy.PACKAGE, "cp", shared + "/" + name + ".part", target + ".part")
        actual = device.call("shell", "run-as", legacy.PACKAGE, "sha256sum", target + ".part").stdout.decode().split()[0]
        v.require(actual == p.digest(path), "staged input hash")
        device.call("shell", "run-as", legacy.PACKAGE, "mv", target + ".part", target)
    return remote_output


def backend_gate(row, backend):
    # Preserve the adapter's raw GPU "unverified" value. delegate_proof below supplies separate proof.
    expected = "CPU" if backend == "CPU" else "unverified_requires_host_delegate_log"
    v.require(row["selected_backend"] == backend and row["actual_backend"] == expected, "raw backend identity")


def wait_for_cleanup(device, remote, seconds=125, screen_contract=None, folder=None):
    end = min(device.deadline, time.monotonic() + seconds) if device.deadline is not None else time.monotonic()+seconds
    next_screen = time.monotonic()
    index = 0
    while time.monotonic() < end:
        if screen_contract and time.monotonic() >= next_screen:
            screen_snapshot(device, folder, f'poll_{index:02d}', screen_contract)
            index += 1
            next_screen = time.monotonic()+screen_contract['poll_interval_seconds']
        probe = device.call('shell', 'run-as', legacy.PACKAGE, 'test', '-s', remote + '/cleanup.json', check=False)
        v.require(not probe.stderr.strip() and not probe.stdout.strip(), 'ADB poll unavailable')
        if probe.returncode == 0:
            if screen_contract:screen_snapshot(device, folder, 'poll_complete', screen_contract)
            return
        v.require(probe.returncode == 1, 'ADB poll failure')
        time.sleep(max(0,min(1,end-time.monotonic())))
    raise TimeoutError('host completion poll exhausted; app outcome unknown')


def failed_attempt_evidence(device, sid, folder, pid):
    """At most5s evidence +5s partial pull within the phase budget; caller always cleans up."""
    try:
        failure_evidence.collect_failure(device, folder / 'pre_cleanup_evidence', pid)
    except Exception as error:
        c.write_new(folder / 'evidence_capture_error.json', dict(error=repr(error)))
    previous = device.deadline
    device.deadline = min(previous if previous is not None else float('inf'), time.monotonic()+5)
    try:
        c.write_new(folder / 'recovery.json', pull(device, sid, folder / 'partial'))
    except Exception as error:
        c.write_new(folder / 'recovery_error.json', dict(error=repr(error)))
    finally:
        device.deadline = previous


def screen_snapshot(device, folder, label, contract, settings=False):
    """Read-only host observation. Sparse samples are not proof of continuous wakefulness."""
    folder=Path(folder)/'screen_observations'
    folder.mkdir(exist_ok=True)
    start=time.monotonic()
    result=dict(utc=legacy.utc(),host_start=start,status='unconfirmed',label=label)
    try:
        power=device.call('shell','dumpsys','power',timeout=2).stdout
        (folder/(label+'_power.txt')).write_bytes(power)
        result.update(awake=bool(re.search(rb'^\s*mWakefulness=Awake\s*$',power,re.M)),
                      interactive=bool(re.search(rb'^\s*mHalInteractiveModeEnabled=true\s*$',power,re.M)))
        v.require(result['awake'] and result['interactive'],'screen state left awake/interactive; stop without wake/retry')
        if settings:
            for key in ('screen_brightness','screen_brightness_mode','screen_off_timeout'):
                value=device.call('shell','settings','get','system',key,timeout=2).stdout.decode().strip()
                result[key]=value
                v.require(value==str(contract[key]),'screen setting changed: '+key)
        result['status']='sample_pass'
        return result
    except Exception as exc:
        result.update(status='sample_failed',error=repr(exc))
        raise
    finally:
        result['host_end']=time.monotonic()
        c.write_new(folder/(label+'.json'),result)


def awake_gate(device, plan, folder):
    """New CAL-03 only: observe, never wake/unlock/change settings."""
    if plan.get('screen_contract'):
        screen_snapshot(device,folder,'before_launch',plan['screen_contract'],settings=True)
        return
    if not plan.get('require_awake_interactive'):
        return
    power = device.call('shell','dumpsys','power',timeout=2).stdout
    (Path(folder)/'before_power.txt').write_bytes(power)
    v.require(re.search(rb'^\s*mWakefulness=Awake\s*$', power, re.M)
              and re.search(rb'^\s*mHalInteractiveModeEnabled=true\s*$', power, re.M),
              'awake/interactive gate failed; user must prepare screen; no automatic wake or retry')


def run(plan_file, phase, output, adb, serial, approved_total_cap, expected_sha, freeze=None):
    v.require(approved_total_cap == 16 and p.digest(plan_file) == expected_sha, "explicit approved total cap/plan hash required")
    c.check(plan_file, for_execution=True)  # Rejects adaptive experiment and unbound APK before Device construction.
    plan, output = p.read(plan_file), Path(output).resolve()
    phase_deadline = time.monotonic() + plan['host_phase_wall_seconds']
    # Reject prior consumption before even a read-only device inspection.
    registry = Path(plan['registry'])
    v.require(not any(registry.glob('*_stopped.json')) and not (registry / f'{phase}_consumed.json').exists()
              and not output.exists(), 'consumed/stopped phase; no restart')
    if phase == "confirmation":
        v.require(freeze is not None and p.read(freeze)["plan_sha256"] == expected_sha, "freeze plan mismatch")
        frozen = p.read(freeze)
        for path, sha in frozen["input_hashes"].items():
            v.require(p.digest(path) == sha, "development artifacts changed")
    if 'apk_preflight' in plan:
        from tools import d1_apk_identity as apk_identity
        # Separate receipt root: signature failure is NOT an install or session attempt.
        preflight_root = output.parent / (output.name + '_preflight_' + uuid.uuid4().hex)
        inspection_plan = dict(plan, _plan_file=str(plan_file))
        inspection_device = legacy.Device(adb, serial)
        inspection_device.deadline = phase_deadline
        try:
            apk_identity.preflight(inspection_device, inspection_plan, preflight_root)
        except Exception as error:
            raise RuntimeError(f'preflight failed; phase/install/session not consumed; evidence: {preflight_root}') from error
    else:
        v.require(plan['experiment_id'] == c.EXPERIMENT, 'new plans require signature preflight')
    c.claim(plan, phase, output, freeze)
    registry = Path(plan["registry"])
    device = legacy.Device(adb, serial)
    device.deadline = phase_deadline-10 if plan.get("screen_contract") else phase_deadline
    identified, completed = False, 0
    c.write_new(output / "phase_attempt.json", dict(utc=legacy.utc(), phase=phase, plan_sha256=expected_sha, session_cap=8))
    try:
        identity = device.identify(plan["device_fingerprint"])
        identified = True
        c.write_new(output / "device_identity.json", identity)
        v.require(p.digest(plan['apk_path']) == plan['apk_sha256'], 'APK changed after preflight')
        c.write_new(output / 'install_attempt.json', dict(utc=legacy.utc(), apk_sha256=plan['apk_sha256'],
                    preflight_root=str(preflight_root) if 'apk_preflight' in plan else None, session_attempts=0))
        installed = device.call("install", "-r", plan["apk_path"], timeout=120)  # No clear/uninstall fallback.
        c.write_new(output / 'install_result.json', dict(utc=legacy.utc(), status='installed',
                    stdout=installed.stdout.decode(errors='replace')))
        legacy.bounded_cool(device, plan["initial_cool_seconds"])
        entries = [e for e in plan["entries"] if e["phase"] == phase]
        for position, entry in enumerate(entries):
            sid = entry["session_id"]
            folder = output / f"{entry['index']:02d}_{sid}"
            folder.mkdir()
            c.write_new(folder / "attempt.json", dict(utc=legacy.utc(), entry=entry, device=identity, plan_sha256=expected_sha))
            pid, stage = None, 'environment_gate'
            try:
                thermal = device.call("shell", "dumpsys", "thermalservice").stdout
                (folder / "before_thermal.txt").write_bytes(thermal)
                v.require(re.search(rb"Thermal Status:\s*0\b", thermal), "thermal gate")
                battery = device.call("shell", "dumpsys", "battery").stdout.decode()
                (folder / "before_battery.txt").write_text(battery, encoding="utf-8")
                legacy.battery_gate(plan, battery, position == 0)
                awake_gate(device, plan, folder)
                device.call("shell", "am", "force-stop", legacy.PACKAGE)
                legacy.require_stopped(device)
                if plan.get('screen_contract'):
                    v.require(device.deadline-time.monotonic()>=165,'insufficient launch30/poll125/evidence10; do not stage/launch')
                manifest_file = Path(plan_file).parent / entry["manifest"]
                remote = stage_inputs(device, sid, manifest_file, {k: info["path"] for k, info in plan["source_files"].items()})
                if plan.get('screen_contract'):
                    v.require(device.deadline-time.monotonic()>=165,'insufficient launch30/poll125/evidence10 after staging')
                c.write_new(folder / "launch_attempt.json", dict(utc=legacy.utc(), session_id=sid))
                stage = 'activity_launch'
                launch = device.call("shell", "am", "start", "-W", "-n", legacy.PACKAGE + "/" + legacy.ACTIVITY,
                                     "-a", legacy.ACTION, "--es", "session_id", sid)
                (folder / "launch_stdout.txt").write_bytes(launch.stdout)
                pid = device.call("shell", "pidof", legacy.PACKAGE + ":model_probe").stdout.decode().strip()
                v.require(re.fullmatch(r"\d+", pid), "model probe PID missing")
                stage = 'completion_poll'
                if plan.get('followup'):
                    previous_deadline = device.deadline
                    device.deadline = min(previous_deadline, time.monotonic()+125)
                    try:wait_for_cleanup(device, remote,screen_contract=plan.get('screen_contract'),folder=folder)
                    finally:device.deadline = previous_deadline
                else:
                    wait_for_cleanup(device, remote)
                stage = 'artifact_recovery'
                recovery = pull(device, sid, folder / "artifacts")
                if plan.get('screen_contract'):
                    screen_snapshot(device,folder,'after_recovery',plan['screen_contract'],settings=True)
                stage = 'artifact_validation'
                artifacts = folder / "artifacts"
                v.require(p.digest(artifacts / "manifest.json") == entry["manifest_sha256"], "device manifest changed")
                samples = c.observations(artifacts)
                summary, rows, env = (p.read(artifacts / f"{name}.json") for name in ("summary", "requests", "environment"))
                legacy.quality_gate(summary, rows, env)
                for row in rows:
                    backend_gate(row, entry["backend"])
                    v.require(p.digest(artifacts / f"{row['request_id']}.result.json") == row["result_sha256"], "result payload changed")
                log_bytes = device.call("logcat", "-d", "-v", "threadtime", "--pid=" + pid, "-s", "D1ARRIVAL:I", "tflite:I").stdout
                (folder / "delegate_log.txt").write_bytes(log_bytes)
                gpu = legacy.delegate_proof(p.read(manifest_file), log_bytes.decode(errors="replace"))
                c.write_new(folder / "validated.json", dict(utc=legacy.utc(), request_count=len(samples), warmup_calls=8,
                             timing=v.validate_artifacts(artifacts), gpu=gpu, recovery=recovery))
            except BaseException as error:
                c.write_new(folder / "error.json", dict(utc=legacy.utc(), error=repr(error), host_stage=stage,
                            application_failure='unknown_unless_app_artifact_confirms'))
                if plan.get('screen_contract'):
                    device.deadline=min(phase_deadline,time.monotonic()+10)
                failed_attempt_evidence(device, sid, folder, pid)
                raise
            finally:
                try:
                    c.write_new(folder / "host_cleanup.json", cleanup(device,hard_deadline=phase_deadline+45) if plan.get("screen_contract") else cleanup(device))
                    device.deadline=phase_deadline-10 if plan.get("screen_contract") else phase_deadline
                except BaseException as cleanup_error:
                    c.write_new(folder / "cleanup_error.json", dict(error=repr(cleanup_error)))
                    raise
            completed += 1
            if position < 7:
                legacy.bounded_cool(device, plan["cool_down_seconds"])
        receipt = dict(status="completed", utc=legacy.utc(), phase=phase, plan_sha256=expected_sha,
                       sessions=completed, diagnostic_requests=completed * 4, warmup_calls=completed * 8)
        c.write_new(output / "complete.json", receipt)
        c.write_new(registry / f"{phase}_complete.json", receipt)
        return receipt
    except BaseException as error:
        stopped = dict(status="stopped_no_retry", utc=legacy.utc(), error=repr(error), completed=completed,
                       attempts=len(list(output.glob("*/attempt.json"))), plan_sha256=expected_sha,
                       rule="no restart/replacement/additional sessions; recovery only")
        c.write_new(output / "stopped.json", stopped)
        c.write_new(registry / f"{phase}_stopped.json", stopped)
        if identified and not list(output.glob("*/host_cleanup.json")) and not list(output.glob("*/cleanup_error.json")):
            try:
                c.write_new(output / "early_cleanup.json", cleanup(device))
            except BaseException as cleanup_error:
                c.write_new(output / "early_cleanup_error.json", dict(error=repr(cleanup_error)))
        raise


def recover(plan_file, adb, serial, sid, output):
    plan = p.read(plan_file)
    v.require(plan["protocol"] == c.PROTOCOL, "calibration plan required")
    entry = next(e for e in plan["entries"] if e["session_id"] == sid)
    registry = Path(plan["registry"])
    claim = p.read(registry / f"{entry['phase']}_consumed.json")
    prior = Path(claim["output"]) / f"{entry['index']:02d}_{sid}" / "attempt.json"
    v.require(prior.is_file() and p.read(prior)["plan_sha256"] == p.digest(plan_file), "no matching prior attempt")
    output = Path(output)
    v.require(not output.exists(), "new recovery root required")
    device = legacy.Device(adb, serial)
    device.deadline = time.monotonic() + 300
    device.identify(plan["device_fingerprint"])
    output.mkdir(parents=True)
    try:
        result = pull(device, sid, output / "artifacts")
        c.write_new(output / "recovery.json", result)
        return result
    finally:
        c.write_new(output / "cleanup.json", cleanup(device))
