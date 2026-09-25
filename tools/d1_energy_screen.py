"""Energy collection v2 host observation revision; no standalone device execution.

Filter output on device, but still run the same dumpsys power producer to completion.
Producer exit marker prevents a successful grep from hiding producer failure.
The existing 2-second client bound, fresh queries and stop-on-unknown remain.
"""
import re
import shlex
import time
from pathlib import Path
from tools import d1_recorded_process as rp

SCRIPT = "{ dumpsys power; echo __D1_POWER_EXIT_$?; } | grep -E '^[[:space:]]*(mWakefulness=|mHalInteractiveModeEnabled=)|^__D1_POWER_EXIT_'"

def parse(raw):
    text=raw.decode('utf-8',errors='strict')
    values=[re.findall(pattern,text,re.M) for pattern in (
        r'^\s*mWakefulness=([^\s]+)\s*$',
        r'^\s*mHalInteractiveModeEnabled=(true|false)\s*$',
        r'^__D1_POWER_EXIT_(\d+)\s*$')]
    if any(len(x)!=1 for x in values) or values[2][0]!='0':
        raise ValueError('incomplete/duplicate/failed fresh power observation')
    return dict(awake=values[0][0]=='Awake',interactive=values[1][0]=='true')

def snapshot(device,folder,label,contract,settings=False):
    folder=Path(folder)/'screen_observations';folder.mkdir(exist_ok=True)
    result=dict(version='energy-screen-filter-v1',utc=rp.utc(),host_start=time.monotonic(),
        status='query_unavailable',label=label,timeout_seconds=2,
        producer='dumpsys power unchanged; filtered transport; no cached state')
    try:
        result['query_start']=time.monotonic()
        raw=device.call('shell','sh','-c',shlex.quote(SCRIPT),timeout=2).stdout
        result['query_end']=time.monotonic()
        (folder/(label+'_power.txt')).write_bytes(raw)
        result.update(parse(raw))
        if not result['awake'] or not result['interactive']:
            result['status']='state_violation';raise ValueError('not awake/interactive')
        if settings:
            for key in ('screen_brightness','screen_brightness_mode','screen_off_timeout'):
                value=device.call('shell','settings','get','system',key,timeout=2).stdout.decode().strip()
                result[key]=value
                if value!=str(contract[key]):
                    result['status']='setting_violation';raise ValueError('screen setting changed: '+key)
        result['status']='sample_pass';return result
    except Exception as exc:
        result['error']=repr(exc);raise
    finally:
        result['host_end']=time.monotonic()
        rp.write(folder/(label+'.json'),result)
