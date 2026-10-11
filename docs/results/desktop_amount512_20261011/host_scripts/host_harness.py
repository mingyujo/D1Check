"""Host-only timing/logging wrapper; never modifies frozen execution sources."""
import ctypes
from ctypes import wintypes
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
BUNDLE = BASE / 'bundle/D1Check-desktop-cpu-20261011'
PYTHON = BASE / 'cpuenv/Scripts/python.exe'
TASK = BUNDLE / 'output/desktop_joint_amount_amount512_desktop_20261011_a'

def process_times(proc):
    times = [wintypes.FILETIME() for _ in range(4)]
    ok = ctypes.windll.kernel32.GetProcessTimes(wintypes.HANDLE(int(proc._handle)), *[ctypes.byref(t) for t in times])
    if not ok:
        return None
    seconds = lambda t: ((t.dwHighDateTime << 32) | t.dwLowDateTime) / 10**7
    return {'kernel_seconds': seconds(times[2]), 'user_seconds': seconds(times[3]), 'cpu_seconds': seconds(times[2]) + seconds(times[3])}

class JobAccounting(ctypes.Structure):
    _fields_ = [('user', ctypes.c_longlong), ('kernel', ctypes.c_longlong), ('period_user', ctypes.c_longlong), ('period_kernel', ctypes.c_longlong), ('page_faults', wintypes.DWORD), ('total_processes', wintypes.DWORD), ('active_processes', wintypes.DWORD), ('terminated_processes', wintypes.DWORD)]

def create_job():
    api = ctypes.windll.kernel32
    api.CreateJobObjectW.restype = wintypes.HANDLE
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError()
    return job

def job_times(job):
    data = JobAccounting()
    if not ctypes.windll.kernel32.QueryInformationJobObject(wintypes.HANDLE(job), 1, ctypes.byref(data), ctypes.sizeof(data), None):
        raise ctypes.WinError()
    return {'kernel_seconds': data.kernel/10**7, 'user_seconds': data.user/10**7, 'cpu_seconds': (data.kernel+data.user)/10**7, 'process_count': data.total_processes, 'scope': 'Windows job including venv redirector and child; assignment immediately after Popen'}

if __name__ == '__main__':
    stage, *args = sys.argv[1:]
    logs = BASE / 'logs'
    logs.mkdir(exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    env = dict(os.environ, MKL_THREADING_LAYER='SEQUENTIAL', PYTHONNOUSERSITE='1')
    command = [str(PYTHON), '-B', '-X', 'utf8', *args]
    log = logs / (stage + '.log')
    if log.exists():
        raise FileExistsError('preserve prior stage log; use a distinct stage label')
    start = time.perf_counter()
    job = create_job()
    with log.open('w', encoding='utf-8') as out:
        proc = subprocess.Popen(command, cwd=BUNDLE, env=env, stdout=out, stderr=subprocess.STDOUT)
        if not ctypes.windll.kernel32.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(int(proc._handle))):
            raise ctypes.WinError()
        print(json.dumps({'stage': stage, 'pid': proc.pid, 'started_utc': started}), flush=True)
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            if TASK.exists():
                (TASK / 'REQUEST_STOP').touch()
                code = proc.wait()
            else:
                raise
        timing = job_times(job)
        ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(job))
    receipt = {'stage': stage, 'started_utc': started, 'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'wall_seconds': time.perf_counter()-start, 'exit_code': code, 'command': ['venv-python', '-B', '-X', 'utf8', *args], 'cpu': timing}
    with (logs / 'stages.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps(receipt, ensure_ascii=False) + '\n')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    print(log.read_text(encoding='utf-8'), flush=True)
    sys.exit(code)
