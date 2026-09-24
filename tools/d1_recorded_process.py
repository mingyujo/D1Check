"""Bounded host command receipts with incremental output. No shell, no retries."""
from pathlib import Path
import datetime
import json
import os
import signal
import subprocess
import time


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def run(command, output, timeout, display, cleanup_seconds=5):
    """display is caller-supplied non-secret argv. Output may end mid-line on failure.

    Timeout kills only the launched client tree, never an existing ADB server.
    Windows taskkill failure is explicitly unconfirmed even if the root is reaped.
    File redirection avoids PIPE/descendant drain deadlocks and keeps partial bytes.
    """
    output=Path(output);output.mkdir(parents=True, exist_ok=False)
    start=time.monotonic()
    receipt=dict(command=display,utc_start=utc(),monotonic_start=start,timeout_seconds=timeout,
                 cleanup_seconds=cleanup_seconds,status='starting',returncode=None)
    write(output/'start.json',receipt)
    proc=None
    try:
        with (output/'stdout.bin').open('xb',buffering=0) as stdout, (output/'stderr.bin').open('xb',buffering=0) as stderr:
            options=dict(start_new_session=True) if os.name!='nt' else dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            proc=subprocess.Popen(command,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,**options)
            receipt['pid']=proc.pid
            try:
                proc.wait(timeout=max(.01,timeout-(time.monotonic()-start)))
                receipt['status']='returned' if proc.returncode==0 else 'nonzero_exit'
            except BaseException as error:
                receipt.update(status='timeout' if isinstance(error,subprocess.TimeoutExpired) else 'host_interrupted',
                               stop_reason=type(error).__name__,stop_utc=utc(),stop_monotonic=time.monotonic())
                end=time.monotonic()+cleanup_seconds
                receipt['termination_start_utc']=utc()
                try:
                    if os.name=='nt':
                        killed=subprocess.run(['taskkill.exe','/PID',str(proc.pid),'/T','/F'],capture_output=True,
                                              timeout=max(.01,min(3,end-time.monotonic())))
                        (output/'termination_stdout.bin').write_bytes(killed.stdout)
                        (output/'termination_stderr.bin').write_bytes(killed.stderr)
                        receipt['tree_termination']='command_succeeded' if killed.returncode==0 else 'unconfirmed'
                        receipt['termination_returncode']=killed.returncode
                    else:
                        os.killpg(proc.pid,signal.SIGKILL);receipt['tree_termination']='signal_sent'
                except Exception as kill_error:
                    receipt.update(tree_termination='unconfirmed',termination_error=type(kill_error).__name__)
                try:
                    if proc.poll() is None:proc.kill()
                    proc.wait(timeout=max(.01,end-time.monotonic()))
                    receipt['root_reaped']=True
                except Exception as reap_error:
                    receipt.update(root_reaped=False,reap_error=type(reap_error).__name__)
                receipt['termination_end_utc']=utc()
            receipt['returncode']=proc.poll()
    except Exception as error:
        receipt.update(status='host_command_error',stop_reason=type(error).__name__)
    finally:
        receipt.update(utc_end=utc(),monotonic_end=time.monotonic(),elapsed_seconds=time.monotonic()-start)
        for name in ('stdout','stderr'):
            f=output/(name+'.bin');receipt[name+'_bytes']=f.stat().st_size if f.exists() else 0
        write(output/'result.json',receipt)
    return receipt
