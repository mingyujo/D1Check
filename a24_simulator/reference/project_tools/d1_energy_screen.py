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
PROTO_VERSION='power-proto-complete-v1'
PROTO_SCRIPT='dumpsys power --proto; rc=$?; printf "\\n__D1_PROTO_EXIT_%s\\n" "$rc"'


def proto_fields(data):
    """Bounded protobuf wire reader. Unknown fields skipped; truncation never passes."""
    if not 0<len(data)<=1_000_000:raise ValueError('power protobuf size')
    offset=0;fields=[]
    def varint():
        nonlocal offset
        value=0
        for shift in range(0,70,7):
            if offset>=len(data):raise ValueError('truncated power varint')
            byte=data[offset];offset+=1;value|=(byte&127)<<shift
            if byte<128:return value
        raise ValueError('overflow power varint')
    while offset<len(data):
        begin=offset;tag=varint();number,wire=tag>>3,tag&7
        if not number:raise ValueError('invalid power protobuf tag')
        if wire==0:value=varint()
        elif wire in (1,5):
            size=8 if wire==1 else 4
            if offset+size>len(data):raise ValueError('truncated fixed power field')
            value=data[offset:offset+size];offset+=size
        elif wire==2:
            size=varint()
            if offset+size>len(data):raise ValueError('truncated length power field')
            value=data[offset:offset+size];offset+=size
        else:raise ValueError('unsupported power protobuf wire type')
        fields.append((number,wire,value,data[begin:offset]))
    return fields


def parse_proto(raw):
    marker=b'\n__D1_PROTO_EXIT_'
    if raw.count(marker)!=1:raise ValueError('missing/duplicate producer completion')
    body,exit_code=raw.split(marker)
    if exit_code!=b'0\n':raise ValueError('power producer failed/incomplete')
    # AOSP PowerManagerServiceDumpProto: WAKEFULNESS=3,
    # IS_HAL_AUTO_INTERACTIVE_MODE_ENABLED=15, backed by mHalInteractiveModeEnabled.
    values={3:[],15:[]}
    for number,wire,value,_ in proto_fields(body):
        if number==1 and wire!=2:raise ValueError('wrong constants wire;binary text translation unsupported')
        if number in values:
            if wire!=0:raise ValueError('wrong screen field wire type')
            values[number].append(value)
    if any(len(x)!=1 for x in values.values()) or values[3][0] not in (0,1,2,3) or values[15][0] not in (0,1):
        raise ValueError('missing/duplicate/unknown screen state')
    return dict(awake=values[3][0]==1,interactive=values[15][0]==1)

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
        proto=getattr(device,'screen_version',None)==PROTO_VERSION
        if proto:
            raw=device.call('exec-out','sh','-c',PROTO_SCRIPT,timeout=2).stdout
            result.update(version=PROTO_VERSION,producer='same power-service state variables;binary proto+remote producer exit;no text history/no cached state')
        else:raw=device.call('shell','sh','-c',shlex.quote(SCRIPT),timeout=2).stdout
        result['query_end']=time.monotonic()
        (folder/(label+('_power.pb' if proto else '_power.txt'))).write_bytes(raw)
        result.update(parse_proto(raw) if proto else parse(raw))
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
