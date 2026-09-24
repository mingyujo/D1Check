"""Read-only bounded host snapshots, independent of app executors/journal locks.

No signals, debugger attachment, app IPC, retries or synthetic measurements.
Host monotonic timestamps are never subtracted from Android timestamps.
"""
from pathlib import Path
import time

from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_dev as v

CONTRACT = dict(version='arrival-host-observation-v1', offsets_seconds=[5, 35, 105],
                snapshot_seconds=8, command_seconds=2, poll_seconds=125,
                signals=False, performance_eligible=False)


def snapshot(device, remote, folder, pid, poll_start, offset):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    previous = device.deadline
    start = time.monotonic()
    device.deadline = min(previous, start + CONTRACT['snapshot_seconds'])
    commands = [
        ('journal', ('shell', 'run-as', legacy.PACKAGE, 'cat', remote+'/failure_progress.jsonl')),
        ('power', ('shell', 'dumpsys', 'power')),
        ('activity_process', ('shell', 'dumpsys', 'activity', 'processes', legacy.PACKAGE)),
    ]
    if pid and str(pid).isdigit():
        commands += [
            ('threads', ('shell', 'ps', '-T', '-p', str(pid))),
            ('process_status', ('shell', 'run-as', legacy.PACKAGE, 'cat', '/proc/'+str(pid)+'/status')),
            ('kernel_stack', ('shell', 'run-as', legacy.PACKAGE, 'cat', '/proc/'+str(pid)+'/stack')),
        ]
    rows = []
    try:
        for name, args in commands:
            row = dict(name=name, host_start=time.monotonic())
            if device.deadline-row['host_start'] < 0.05:
                row['status'] = 'skipped_budget'
                rows.append(row)
                continue
            try:
                response = device.call(*args, timeout=CONTRACT['command_seconds'], check=False)
                raw = response.stdout[:262144]
                (folder/(name+'.txt')).write_bytes(raw)
                row.update(status='captured' if response.returncode == 0 else 'unavailable',
                           returncode=response.returncode, stderr=response.stderr.decode(errors='replace')[:1024],
                           truncated=len(raw) != len(response.stdout))
            except Exception as exc:
                row.update(status='capture_failed', error=repr(exc))
            row['host_end'] = time.monotonic()
            rows.append(row)
    finally:
        device.deadline = previous
    report = dict(utc=legacy.utc(), scheduled_poll_offset=offset, poll_start= poll_start,
                  host_start=start, host_end=time.monotonic(), pid=pid, commands=rows,
                  app_outcome='not_inferred_from_capture', performance_eligible=False)
    legacy.write_new(folder/'capture.json', report)
    return report


def wait_for_cleanup(device, remote, output, pid):
    start = time.monotonic()
    end = min(device.deadline, start+CONTRACT['poll_seconds'])
    previous = device.deadline
    device.deadline = end
    pending = iter(CONTRACT['offsets_seconds'])
    offset = next(pending, None)
    report = dict(host_start=start, absolute_deadline=end, snapshots=[], status='polling')
    try:
        while time.monotonic() < end:
            probe = device.call('shell','run-as',legacy.PACKAGE,'test','-s',remote+'/cleanup.json',
                                timeout=2,check=False)
            v.require(not probe.stderr.strip() and not probe.stdout.strip(), 'ADB poll unavailable')
            if probe.returncode == 0:
                report['status'] = 'cleanup_marker_present_not_validated'
                return
            v.require(probe.returncode == 1, 'ADB poll failure')
            if offset is not None and time.monotonic()-start >= offset:
                capture = snapshot(device, remote, Path(output)/('at_'+str(offset)), pid, start, offset)
                report['snapshots'].append(dict(offset=offset, host_start=capture['host_start'], host_end=capture['host_end']))
                offset = next(pending, None)
            time.sleep(max(0, min(1, end-time.monotonic())))
        raise TimeoutError('host completion poll exhausted; app outcome unknown')
    except BaseException as exc:
        report.update(status='poll_failed_app_outcome_unknown', error=repr(exc))
        raise
    finally:
        device.deadline = previous
        report['host_end'] = time.monotonic()
        Path(output).mkdir(parents=True, exist_ok=True)
        legacy.write_new(Path(output)/'poll.json', report)
