"""One fixed 192-request transfer input; legacy 96-input validation stays strict."""
import argparse
import math
from pathlib import Path
from tools import d1_policy_resolution as evidence

VERSION='sustained-confirmation-v1'
COUNT=192
POLICIES=(evidence.CPU,evidence.PAR)


def requests(session='pc'):
    return [dict(request_id=f'{session}-{i}',ordinal=i,
        task_id='classification' if i%2==0 else 'detection',
        priority='urgent' if i%2==0 else 'normal',offset_ms=35000+i*400,
        deadline_ms=1500 if i%2==0 else 6000) for i in range(COUNT)]


def validate(rows,policy):
    if policy not in POLICIES or len(rows)!=COUNT or len({r['request_id'] for r in rows})!=COUNT:
        raise ValueError('sustained input count/policy/id')
    for actual,expected in zip(rows,requests()):
        if any(actual[k]!=expected[k] for k in expected if k!='request_id'):
            raise ValueError('fixed sustained input differs')


def preview(bundle,output):
    resource,frozen,inputs,_=evidence.load(bundle)
    initial=inputs[evidence.IDS[0]]['initial']
    rows=requests();reports=[]
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    for policy in POLICIES:
        validate(rows,policy)
        result,segments=evidence.replay.shared.model.forecast(initial,rows,policy,frozen,planning_input_role=VERSION)
        met=0;urgent=[];last=max(r['lane_available_ns'] for r in result['ledger'])/1e9
        for r in result['ledger']:
            field='output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns'
            response=r[field]-r['arrival_ns'];met+=response<=r['deadline_offset_ns']
            if r['priority']=='urgent':urgent.append(response/1e6)
        costs=evidence.replay.shared.model.costs(segments,initial,list(range(35,181)),frozen,180)
        exposure=evidence.replay.shared.model.exposure(segments,0,120)
        report=dict(policy=policy,planned=COUNT,completed=len(result['ledger']),deadline_met=met,
            last_lane_s=last,urgent_p95_ms=sorted(urgent)[math.ceil(.95*len(urgent))-1],
            exposure_s=dict(zip(evidence.replay.shared.model.STATES,exposure.tolist())),
            whole_120s_j=costs['whole_120s_j'],predicted_peak_ap_c=max(costs['ap_path']))
        reports.append(report)
        evidence.write(out/(policy+'.json'),dict(forecast=result,segments=segments,costs=costs))
    evidence.write(out/'requests.json',rows)
    evidence.csv_write(out/'preview.csv',reports)
    result=dict(version=VERSION,source_files=resource['files'],source_freeze_sha256=resource['source_freeze_sha256'],
        initial_case_id=evidence.IDS[0],policies=reports,
        deadline_and_window_gate=all(r['completed']==COUNT and r['deadline_met']==COUNT and r['last_lane_s']<120 for r in reports),
        energy_delta_j=reports[1]['whole_120s_j']-reports[0]['whole_120s_j'],
        peak_ap_delta_c=reports[1]['predicted_peak_ap_c']-reports[0]['predicted_peak_ap_c'],
        actual_measurement=False,accuracy_pass=None,strict_supported=False,experiment_ready=False,device_commands=0)
    evidence.write(out/'summary.json',result)
    evidence.load(bundle)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(preview(a.bundle,a.output))
