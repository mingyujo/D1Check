"""Fixed separated-development and mixed-confirmation input; no device calls."""
import argparse
import csv
import json
from pathlib import Path
from tools import d1_online_policy_model as m
from tools import d1_energy_identifiability as ident
from tools import d1_arrival_plan as p

VERSION='separated-power-input-v1'


def requests(role,session='pc'):
    if role not in ('development','confirmation'):raise ValueError('role')
    out=[]
    for i in range(96):
        if role=='development':
            classification=i<32 or (i>=64 and i%2==0)
            offset=(35000 if i<32 else 55000 if i<64 else 85000)+(i%32)*100
        else:
            classification=i%2==0;offset=35000+i*350
        out.append(dict(ordinal=i,request_id=f'{session}-{i}',task_id='classification' if classification else 'detection',
            priority='urgent' if classification else 'normal',offset_ms=offset,deadline_ms=1500 if classification else 6000))
    return out


def validate(role,rows):
    expected=requests(role)
    if len(rows)!=96 or len({r['request_id'] for r in rows})!=96:raise ValueError('denominator/id')
    for a,b in zip(rows,expected):
        if any(a[k]!=b[k] for k in b if k!='request_id'):raise ValueError('fixed input differs')


def preview(freeze,output):
    output=Path(output)
    if output.exists():raise ValueError('fresh output')
    if p.digest(freeze)!='557fbe5be8a9c9ba5f5911d44d1c19611710cbe5b80e015d1b965b777357bcf2':raise ValueError('planning service source drift')
    model=p.read(freeze)['model'];rows=[];windows=[];inputs={}
    for role in ('development','confirmation'):
        inputs[role]=requests(role)
        for policy in m.POLICIES:
            schedule,segments=m.forecast({},inputs[role],policy,model,planning_input_role=role)
            last=max(r['lane_available_ns'] for r in schedule['ledger'])/1e9
            if last>=120:raise ValueError('planned common window insufficient')
            exp=m.exposure(segments,0,120)
            rows.append(dict(role=role,policy=policy,requests=96,last_lane_s=last,
                **dict(zip(m.STATES,exp.tolist()))))
            if role=='development':
                for a in range(0,120,5):windows.append([5.,*m.exposure(segments,a,a+5)])
    summary=dict(status='PC_INPUT_PREVIEW_NOT_DEVICE_PLAN',forecast_geometry=ident.geometry(windows),
        source_sha256=p.digest(freeze),actual_measurement=False,accuracy_pass=None,
        limitation='Old service means for sizing only. New mix and backlog may change latency. No future actual duration or energy used to select input.',
        device_commands=0)
    output.mkdir(parents=True)
    for name,value in [('requests.json',inputs),('summary.json',summary)]:
        (output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    with (output/'planned_occupancy.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return summary


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--freeze',required=True);a.add_argument('--output',required=True)
    x=a.parse_args();print(json.dumps(preview(x.freeze,x.output),indent=2))
