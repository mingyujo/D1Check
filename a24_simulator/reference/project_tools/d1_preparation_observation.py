"""Bounded pre-approval observation loss; never skips a gate or retries a mutation."""
import json
import time
import traceback
from pathlib import Path

VERSION = 'prewarmup-listing-gap-v1'
ENV_VERSION = 'prewarmup-observation-gap-v2'


def thermal(device, folder, index, state, armed, read, version=ENV_VERSION):
    """No approval on a failed sample; next poll must obtain a fresh full bracket."""
    sequence=device.sequence
    try:
        read(device,folder,index)
        return True
    except RuntimeError as error:
        path=Path(device.root)/f'{device.sequence-1:04d}'/'client/result.json'
        if armed or state['gaps'] or not sequence<device.sequence<=sequence+3 or not path.exists():raise
        result=json.loads(path.read_text(encoding='utf8'))
        allowed=[['exec-out','cat','/proc/uptime'],['shell','dumpsys','thermalservice']]
        cmd=result.get('command',[])
        if (cmd[:3]!=[device.adb,'-s',device.serial] or cmd[3:] not in allowed
                or result.get('status')!='timeout' or result.get('root_reaped') is not True
                or result.get('stdout_bytes')!=0 or result.get('stderr_bytes')!=0
                or result.get('timeout_seconds')!=2 or device.deadline-time.monotonic()<=30):raise
        with (Path(folder)/'prewarmup_observation_gap.json').open('x',encoding='utf8') as stream:
            json.dump(dict(version=version,command_index=device.sequence-1,result=result,
                           original_error=repr(error),original_stack=traceback.format_exc(),
                           interpretation='environment unknown; no approval; fresh bracket required next poll',
                           used_gaps=1,maximum_gaps=1),stream,indent=2)
        state['gaps']=1
        return False


def listing(device, remote, folder, package, state, armed, version=VERSION):
    args = ('shell', 'run-as', package, 'ls', remote)
    sequence = device.sequence
    try:
        return device.call(*args, timeout=3).stdout.decode().splitlines()
    except RuntimeError as error:
        # Only evidence of this exact, reaped, silent timeout permits one gap.
        # Server/precheck failures, explicit disconnects, missing evidence fail closed.
        path = Path(device.root)/f'{sequence:04d}'/'client/result.json'
        if armed or state['gaps'] or device.sequence != sequence+1 or not path.exists():
            raise
        result = json.loads(path.read_text(encoding='utf8'))
        if (result.get('command') != [device.adb, '-s', device.serial, *args]
                or result.get('status') != 'timeout' or result.get('root_reaped') is not True
                or result.get('stdout_bytes') != 0 or result.get('stderr_bytes') != 0
                or result.get('timeout_seconds') != 3
                or device.deadline-time.monotonic() <= 30):
            raise
        evidence = dict(version=version, command_index=sequence, result=result,
                        original_error=repr(error), original_stack=traceback.format_exc(),
                        interpretation='pre-approval observation unknown; no gate granted',
                        next_action='next regular poll, same transport and deadline',
                        maximum_gaps=1, used_gaps=1)
        with (Path(folder)/'prewarmup_observation_gap.json').open('x',encoding='utf8') as stream:
            json.dump(evidence,stream,indent=2)
        state['gaps'] = 1
        return None
