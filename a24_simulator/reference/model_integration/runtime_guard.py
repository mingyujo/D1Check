"""Local-only operations for the separately registered A24 model improvement.

No worker is started or resumed by importing this module. A completed or failed
operation is never automatically retried. Original artifacts are read-only.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

MIN_FREE = 8 * 1024 ** 3
OWN_TOKENS = (
    'a24-integrated-sim-', 'a24-model-integration-', 's26-integrated-model-',
    's26-scheduling-causality-', 's26-rolling-atc-rl-', 's26-ie-rollout-',
    'scheduler-integrated-s26-', 'rolling-atc-rl-37-v2',
    'continue_independent_models.py', 'execute_calibration', 'm8_calibrate',
)


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 ** 2), b''):
            h.update(block)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def relocated(path):
    root = Path(__file__).resolve().parents[2]
    key = str(path).replace('\\','/').lower()
    table = json.loads((root/'data/PATH_MAP.json').read_text(encoding='utf-8'))
    if key in table:
        spec = table[key]
        target = root/'.cache'/spec['sha256']
        if not target.exists():
            import gzip
            target.parent.mkdir(parents=True, exist_ok=True)
            source = root/spec['stored']
            opener = gzip.open if spec['gzip'] else open
            temp = target.with_suffix('.tmp')
            with opener(source,'rb') as a, temp.open('wb') as b: shutil.copyfileobj(a,b)
            require(sha(temp) == spec['sha256'], 'Packaged input SHA mismatch')
            os.replace(temp,target)
        return target
    return Path(path)

def read(path):
    path = relocated(path)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(spec):
    path = relocated(spec['path'])
    require(path.is_file(), 'Pinned input absent: ' + str(path))
    require(sha(path) == spec['sha256'], 'Pinned SHA differs: ' + str(path))
    if 'bytes' in spec:
        require(path.stat().st_size == spec['bytes'], 'Pinned size differs: ' + str(path))
    return path


def write_new(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(canonical(obj) + '\n')
        f.flush()
        os.fsync(f.fileno())


def append(path, obj):
    with Path(path).open('a', encoding='utf-8', newline='\n') as f:
        f.write(canonical(obj) + '\n')
        f.flush()
        os.fsync(f.fileno())


def _same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def process_guard(entry, known_ps=()):
    command = ('[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); '
               'Get-CimInstance Win32_Process | Select-Object '
               'ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Compress')
    raw = subprocess.check_output(['powershell', '-NoProfile', '-Command', command],
                                  creationflags=0x08000000)
    rows = json.loads(raw.decode('utf-8-sig'))
    rows = rows if isinstance(rows, list) else [rows]
    by_id = {int(x['ProcessId']): x for x in rows}
    ancestors, parent = set(), os.getpid()
    while parent in by_id and parent not in ancestors:
        ancestors.add(parent)
        parent = int(by_id[parent].get('ParentProcessId') or 0)
    excluded_shims, python_rows = [], []
    for row in rows:
        pid = int(row['ProcessId'])
        name = str(row.get('Name') or '').lower()
        text = str(row.get('CommandLine') or '')
        normalized = text.replace('\\', '/').lower()
        if pid == os.getpid():
            continue
        if 'python' in name:
            match = re.search(r'(?i)(?:"([^"\r\n]+\.py)"|([^\s"]+\.py))(?:\s|$)', text)
            same_entry = match and _same(match.group(1) or match.group(2), entry)
            if pid in ancestors and same_entry:
                excluded_shims.append(pid)
                continue
            require(not any(token in normalized for token in OWN_TOKENS),
                    'Other own Python producer alive: ' + str(pid))
            python_rows.append(row)
        if 'pwsh' in name or 'powershell' in name:
            for path in known_ps:
                needle = str(path).replace('\\', '/').lower()
                invoked = re.search(r'(?:-file\s+|&\s*)["\x27]?' + re.escape(needle) + r'(?:["\x27\s]|$)', normalized)
                require(not invoked, 'Registered PowerShell producer alive: ' + str(pid))
    require(len(python_rows) < 2, 'Global Python leaf limit2 would be exceeded')
    return {'checked_utc': now(), 'actual_pid': os.getpid(),
            'actual_process': by_id.get(os.getpid()), 'excluded_same_entry_ancestor_shims': excluded_shims,
            'other_python': python_rows, 'own_limit': 1, 'global_limit': 2}


def free_guard(paths):
    volumes = {}
    for value in paths:
        path = Path(value).absolute()
        for ancestor in (path, *path.parents):
            if ancestor.exists():
                require(not ancestor.is_symlink(), 'Symlink source/output ancestor: ' + str(ancestor))
                attrs = getattr(ancestor.stat(), 'st_file_attributes', 0)
                require(not (attrs & 0x400), 'Reparse source/output ancestor: ' + str(ancestor))
        anchor = path.anchor
        require(bool(anchor), 'Absolute volume anchor required')
        space = shutil.disk_usage(anchor)
        require(space.free >= MIN_FREE, '8GiB reserve violated: ' + anchor)
        volumes[anchor] = {'free': space.free, 'minimum_free': MIN_FREE}
    return volumes


def protected_check(specs):
    seen = {}
    for spec in specs:
        key = os.path.normcase(os.path.abspath(spec['path']))
        require(key not in seen, 'Duplicate protected path')
        pin(spec)
        seen[key] = spec['sha256']
    return {'count': len(seen), 'digest': hashlib.sha256(canonical(seen).encode()).hexdigest()}


@contextlib.contextmanager
def operation(operation_path, entry):
    op_path = Path(operation_path)
    op_sha = sha(op_path)
    op = read(op_path)
    require(op.get('schema') == 'A24-local-model-improvement-operation-v1', 'Operation schema')
    require(op.get('allow_execution') is True, 'Operation not authorized for execution')
    require(op.get('HTTP') == 0 and op.get('device_commands') == 0 and op.get('new_environment') == 0,
            'Local saved-data-only operation required')
    require(op.get('automatic_retry') is False, 'Automatic retry forbidden')
    for spec in op['source_pins']:
        pin(spec)
    for spec in op['input_pins']:
        pin(spec)
    require(any(_same(x['path'], entry) for x in op['source_pins']), 'Entry not source-pinned')
    state = process_guard(entry, op.get('known_PS_producer_paths', []))
    volumes = free_guard([op_path, op['output_dir'], *[x['path'] for x in op['input_pins']], 'D:/'])
    before = protected_check(op['protected_pins'])
    out = Path(op['output_dir'])
    require(not out.exists(), 'Consumed output namespace exists; do not retry')
    lock_path = Path(op['worker_lock_path'])
    import msvcrt
    lock = lock_path.open('r+b')
    acquired = False
    try:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        acquired = True
        out.mkdir(parents=True, exist_ok=False)
        write_new(out / 'START.json', {'operation_sha256': op_sha, 'started_utc': now(),
                  'process': state, 'volumes': volumes, 'protection_before': before, 'mode': op['mode']})
        try:
            yield op, out
            require(sha(op_path) == op_sha, 'Operation mutated')
            for spec in op['source_pins']:
                pin(spec)
            for spec in op['input_pins']:
                pin(spec)
            after = protected_check(op['protected_pins'])
            require(before == after, 'Original protected inputs changed')
            outputs = {str(p.relative_to(out)): {'sha256': sha(p), 'bytes': p.stat().st_size}
                       for p in sorted(out.rglob('*')) if p.is_file()}
            write_new(out / 'COMPLETE.json', {'operation_sha256': op_sha, 'completed_utc': now(),
                      'mode': op['mode'], 'protection_after': after, 'outputs': outputs,
                      'new_environment': 0, 'HTTP': 0, 'device_commands': 0})
        except BaseException as exc:
            if not (out / 'FAILURE.json').exists():
                write_new(out / 'FAILURE.json', {'operation_sha256': op_sha, 'failed_utc': now(),
                          'exception': type(exc).__name__, 'message': str(exc), 'automatic_retry': False})
            raise
    finally:
        try:
            if acquired:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lock.close()


class FitBudget:
    def __init__(self, cap, out):
        self.cap, self.out, self.used = int(cap), Path(out), 0
        require(self.cap > 0, 'Positive registered fit cap required')

    def consume(self, label):
        require(self.used < self.cap, 'Registered fit budget exhausted')
        self.used += 1
        append(self.out / 'fit_receipts.jsonl', {'index': self.used, 'cap': self.cap,
               'label': label, 'utc': now()})

    def summary(self):
        return {'parameter_fit_cap': self.cap, 'parameter_fits_consumed': self.used,
                'unused': self.cap - self.used, 'simulated_environment_START': 0}
