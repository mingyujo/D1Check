"""PC-only replay of saved ADB bytes through the actual collection gate functions.

No subprocess/ADB transport exists here. Fault injection tests host semantics,
not device stability. Original fixtures are only read; output must be new.
"""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from tools import d1_energy_collection as c
from tools import d1_energy_collection_device as device


class Replay(device.legacy.Device):
    def __init__(self, roots, fault=None):
        self.records = {}
        self.calls = []
        self.used = {}
        self.fault = fault
        self.deadline = time.monotonic() + 60
        self.serial = None
        for root in roots:
            for f in sorted((root / 'host_commands').glob('*/client/result.json')):
                r = c.p.read(f)
                if r.get('returncode') != 0:
                    continue
                args = tuple(r['command'][3:])
                self.records.setdefault(args, []).append((f, r))

    def call(self, *args, timeout=30, check=True):
        self.calls.append((args, timeout))
        is_screen = args[:3] == ('shell', 'sh', '-c')
        if is_screen and self.fault == 'timeout':
            assert timeout == 2
            raise TimeoutError('injected client timeout; no retry')
        if is_screen and self.fault == 'exit':
            raise RuntimeError('injected nonzero client exit; transport rejects before parser')
        records = self.records.get(args)
        if not records:
            raise AssertionError('No recorded transport fixture: ' + repr(args))
        # Preserve the first real before/after uptime bracket, not a fabricated clock.
        index = sum(a == args for a, _ in self.calls) - 1 if args == ('exec-out', 'cat', '/proc/uptime') else 0
        f, r = records[index]
        raw = (f.parent / 'stdout.bin').read_bytes()
        err = (f.parent / 'stderr.bin').read_bytes()
        self.used[str(f)] = dict(receipt_sha256=c.p.digest(f), stdout_sha256=c.p.digest(f.parent / 'stdout.bin'))
        if is_screen and self.fault == 'marker':
            raw = raw.replace(b'__D1_POWER_EXIT_0', b'__D1_POWER_EXIT_1')
        if is_screen and self.fault == 'asleep':
            raw = raw.replace(b'mWakefulness=Awake', b'mWakefulness=Asleep')
        return subprocess.CompletedProcess(args, r['returncode'], raw, err)


def verify(root, plan_file):
    plan = c.p.read(plan_file)
    roots = [root / 'energy_screen_observe_run_v2', root / 'energy_collection_run_v2']
    results = []
    provenance = {}
    for fault in (None, 'timeout', 'exit', 'marker', 'asleep'):
        replay = Replay(roots, fault)
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            if fault is None:
                device.gates(replay, plan, folder, 'gate')
                assert c.p.read(folder / 'screen_observations/gate.json')['status'] == 'sample_pass'
                # Actual cleanup function, but all force-stop/ps/thermal responses are saved bytes.
                previous = replay.deadline
                assert device.shared.cleanup(replay, previous)['status'] == 'completed'
                assert replay.deadline == previous
            else:
                try:
                    device.gates(replay, plan, folder, 'gate')
                except (ValueError, RuntimeError, TimeoutError):
                    pass
                else:
                    raise AssertionError('Gate accepted faulty observation')
                actual = c.p.read(folder / 'screen_observations/gate.json')['status']
                assert actual == ('state_violation' if fault == 'asleep' else 'query_unavailable')
                assert not (folder / 'gate_identity.json').exists()
            assert sum(a[:3] == ('shell', 'sh', '-c') for a, _ in replay.calls) == 1
            assert all(a[0] not in ('push', 'install') for a, _ in replay.calls)
            provenance.update(replay.used)
            results.append(dict(case=fault or 'real_bytes_gate_and_cleanup', status='PASS', commands_replayed=len(replay.calls)))
    # The historical failed cleanup pull returned cat error text, not app cleanup JSON.
    candidates = list((root / 'energy_collection_run_v2').rglob('cleanup.json'))
    bad = next(f for f in candidates if f.read_bytes().startswith(b'cat:'))
    class PullReplay:
        def call(self, *args, **kw):
            return subprocess.CompletedProcess(args, 0, bad.read_bytes(), b'')
    with tempfile.TemporaryDirectory() as t:
        try:
            device.pull_file(PullReplay(), 'saved/remote', 'cleanup.json', t)
        except ValueError:
            pass
        else:
            raise AssertionError('Retrieval error accepted as app cleanup')
        assert not (Path(t) / 'cleanup.json').exists()
        assert (Path(t) / 'cleanup.json.invalid.bin').read_bytes() == bad.read_bytes()
    results.append(dict(case='real_partial_recovery_not_app_cleanup', status='PASS'))
    provenance[str(bad)] = dict(sha256=c.p.digest(bad))
    return dict(status='PC_FIXTURE_PASS_NOT_DEVICE_VALIDATION', results=results,
                device_commands=0, plan_sha256=c.p.digest(plan_file), source_code=c.identity(),
                fixtures=provenance, limitation='Gate bytes from separate historical observations; not one current device state')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new verification output required')
    result = verify(args.root, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    c.cal.write_new(args.output, result)
    print(json.dumps(dict(status=result['status'], cases=len(result['results']), device_commands=0)))


if __name__ == '__main__':
    main()
