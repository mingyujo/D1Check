"""Opt-in bounded progress gap; mandatory environment observations remain fatal."""
import json
import time
import traceback
from pathlib import Path

VERSION = 'postapproval-listing-gap-v1'
PERIOD_SECONDS = 2


def enabled(plan, manifest):
    version = plan.get('postapproval_observation')
    if version is None:
        return False
    if (version != VERSION or plan.get('history_control') is not True
            or manifest.get('history_control_version') != 'registered-history-control-v1'
            or manifest.get('start_ap_gate') != 'numeric-ap-observe-v2'):
        raise ValueError('postapproval observation protocol/context mismatch')
    return True


def listing(device, remote, folder, package, state, poll_deadline):
    args = ('shell', 'run-as', package, 'ls', remote)
    sequence = device.sequence
    try:
        return device.call(*args, timeout=3).stdout.decode().splitlines()
    except RuntimeError as error:
        path = Path(device.root)/f'{sequence:04d}'/'client/result.json'
        if state['gaps'] or device.sequence != sequence+1 or not path.exists():
            raise
        result = json.loads(path.read_text(encoding='utf8'))
        if (result.get('command') != [device.adb, '-s', device.serial, *args]
                or result.get('status') != 'timeout' or result.get('root_reaped') is not True
                or result.get('returncode') is None
                or result.get('stdout_bytes') != 0 or result.get('stderr_bytes') != 0
                or result.get('timeout_seconds') != 3
                or min(device.deadline, poll_deadline)-time.monotonic() <= 30):
            raise
        evidence = dict(version=VERSION, command_index=sequence, result=result,
            original_error=repr(error), original_stack=traceback.format_exc(),
            interpretation='progress/terminal state unknown; not app failure or completion',
            next_action='next regular poll: fresh mandatory thermal and screen, then progress query',
            maximum_gaps=1, used_gaps=1, original_poll_deadline=poll_deadline,
            approval_reissued=False, inference_reissued=False)
        try:
            with (Path(folder)/'postapproval_observation_gap.json').open('x',encoding='utf8') as stream:
                json.dump(evidence,stream,ensure_ascii=False,indent=2)
                stream.flush()
        except OSError as recording_error:
            raise error from recording_error
        state['gaps'] = 1
        state['refresh_environment'] = True
        return None
