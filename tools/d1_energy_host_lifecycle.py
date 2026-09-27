"""Identify one collection host and decide whether one-shot recovery is safe.

This module never kills a process. An old heartbeat is evidence of a recording
gap, not evidence that the runner has stopped.
"""

import json
import os
from pathlib import Path
import subprocess
import sys


def process_snapshot(pid):
    """Read PID, creation time, executable and command line; fail closed."""
    if not isinstance(pid, int) or pid <= 0:
        return dict(status='query_failed', error='invalid pid')
    if os.name != 'nt':
        return dict(status='query_failed', error='Windows process identity required')
    script = ("$p=Get-CimInstance Win32_Process -Filter 'ProcessId=%d' -ErrorAction Stop; "
              "if ($null -eq $p) { 'null' } else { "
              "$p | Select-Object ProcessId,CreationDate,ExecutablePath,CommandLine "
              "| ConvertTo-Json -Compress }") % pid
    try:
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                                capture_output=True,timeout=5)
        if result.returncode:
            return dict(status='query_failed',exit_code=result.returncode,
                        error=result.stderr.decode(errors='replace')[:300])
        value=json.loads(result.stdout.decode('utf-8-sig'))
        if value is None:
            return dict(status='absent',pid=pid)
        fields=dict(pid=int(value['ProcessId']),creation_date=str(value.get('CreationDate') or ''),
                    executable=str(value.get('ExecutablePath') or ''),
                    command_line=str(value.get('CommandLine') or ''))
        if not all(fields.values()) or fields['pid']!=pid:
            return dict(status='query_failed',error='incomplete process identity')
        return dict(status='present',**fields)
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as error:
        return dict(status='query_failed',error=repr(error))


def host_identity():
    child=process_snapshot(os.getpid())
    parent=process_snapshot(os.getppid())
    return dict(child=child,parent=parent)


def identity_state(record, query=process_snapshot):
    """Only an exact live identity is active. Unverifiable identity blocks recovery."""
    if not record or record.get('status')!='present':
        return 'unknown'
    current=query(record['pid'])
    if current['status']=='absent':
        return 'exited'
    if current['status']!='present':
        return 'unknown'
    fields=('pid','creation_date','executable','command_line')
    return 'active' if all(current.get(k)==record.get(k) for k in fields) else 'replaced'


def inspect_run(run_root, registry, plan_sha256, query=process_snapshot):
    run_root=Path(run_root);registry=Path(registry)
    claim=registry/'claimed.json'
    if not claim.exists():
        return dict(status='unclaimed',recoverable=False)
    try:
        info=json.loads(claim.read_text(encoding='utf-8-sig'))
        if info['plan_sha256']!=plan_sha256:
            return dict(status='identity_mismatch',recoverable=False)
        records=sorted((run_root/'host_checkpoints').glob('*.json'))
        first=json.loads(records[0].read_text(encoding='utf-8-sig')) if records else {}
        if first.get('plan_sha256')!=plan_sha256 or first.get('host_run_id')!=info.get('host_run_id') or \
           first.get('host_identity')!=info.get('host_identity'):
            return dict(status='identity_unconfirmed',recoverable=False)
        identity=first.get('host_identity') or {}
        child=identity_state(identity.get('child'),query)
        parent=identity_state(identity.get('parent'),query)
        if child=='active' or parent=='active':
            status='active'
        elif child=='unknown' or parent=='unknown':
            status='identity_unconfirmed'
        else:
            status='host_exited'
        terminal='completed' if (registry/'completed.json').exists() else 'stopped' if (registry/'stopped.json').exists() else 'unconfirmed'
        return dict(status=status,recoverable=status=='host_exited' and terminal!='completed',
                    child=child,parent=parent,terminal=terminal,host_run_id=info.get('host_run_id'),
                    last_stage=json.loads(records[-1].read_text(encoding='utf-8-sig')).get('stage'),
                    checkpoint_count=len(records))
    except (OSError,ValueError,KeyError,IndexError) as error:
        return dict(status='identity_unconfirmed',recoverable=False,error=repr(error))
