"""Portable v2 demo: planned arrivals, empirical timing, modeled costs. No phone APIs."""
import argparse
import copy
import csv
import html
import json
from pathlib import Path
from tools import d1_simulation_model_v2 as m
from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v2_campaign as campaign


def demo(model_file,output,seed=1,mode='mean'):
    model_file=Path(model_file);output=Path(output)
    if output.exists():raise ValueError('new output only')
    frozen=p.read(model_file);model=frozen.get('model',frozen)
    if model.get('version')!=m.VERSION:raise ValueError('v2 model required')
    init=p.read(m.ROOT/'docs/results/online_policy_study_01/overnight_sustained_run01/initial_inputs.json')[0]['initial']
    case=dict(pre=copy.deepcopy(init['preload']),pre_w=init['preload_power_w'],q=list(range(35,181)))
    tickets=[dict(id=f'v2-{i}',ordinal=i,task='classification' if i%2==0 else 'detection',priority='urgent' if i%2==0 else 'normal',arrival_ns=(35000+i*350)*1000000,deadline_offset_ns=(1500 if i%2==0 else 6000)*1000000) for i in range(96)]
    results=[];table=[];curves=[]
    for policy in ('CPU','PAR','EFT'):
        result=m.simulate(tickets,model['service'],policy,seed,mode)
        complete=all(r['status']=='succeeded' for r in result['ledger']);result['costs']=None
        if complete:
            ss=m.occupancy(result['ledger'],0,180000000000);c=dict(case,actual=ss)
            ap,initial=m.ap_prediction(c,model)
            result['costs']=dict(energy_120s_j=m.energy_at(c,model,120),peak_AP_35_180_c=max(ap),AP_c=ap,initial=initial)
            curves.extend(dict(policy=policy,time_s=t,predicted_AP_c=y) for t,y in zip(case['q'],ap))
        table.append(dict(policy=policy,planned=96,completed=sum(r['status']=='succeeded' for r in result['ledger']),urgent_timely=result['metrics']['urgent']['timely'],normal_timely=result['metrics']['normal']['timely'],
            urgent_response_P95_ms=result['metrics']['urgent']['response_P95_ms'],energy_120s_j=result['costs']['energy_120s_j'] if complete else None,peak_AP_c=result['costs']['peak_AP_35_180_c'] if complete else None))
        results.append(result)
    output.mkdir(parents=True)
    campaign.write(output/'result.json',dict(model_sha256=p.digest(model_file),seed=seed,mode=mode,results=results,requests=tickets,initial_inputs=case,
        evidence='model conditional exploration; initial inputs from archived example; no matched actual observations',experiment_ready=False,accuracy_pass=None))
    for name,rows in [('summary.csv',table),('AP_curve.csv',curves)]:
        if rows:
            with (output/name).open('x',encoding='utf8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cells=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r.values())+'</tr>' for r in table)
    headings=''.join('<th>'+html.escape(k)+'</th>' for k in table[0])
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>D1Check v2 재생</title><style>body{font:16px system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:8px}</style><h1>새 시뮬레이션 모형 v2 · 입력 재생</h1><p>96개 예정 도착, CPU/GPU 실제 추론을 대체하는 PC 예측입니다. 상태 비용·초기조건·처리시간 전이는 모형 가정이며 실제 정책 우월성/절감 검증이 아닙니다. experiment_ready=false</p><p><a href="result.json">전체 원장/입력/모형 해시</a> · <a href="summary.csv">요약</a> · <a href="AP_curve.csv">AP 곡선</a></p><table><tr>'+headings+'</tr>'+cells+'</table>',encoding='utf8')
    return dict(runs=3,rows=table,device_commands=0,experiment_ready=False)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--model',required=True);a.add_argument('--output',required=True);a.add_argument('--seed',type=int,default=1);a.add_argument('--mode',choices=['mean','session_replay'],default='mean');x=a.parse_args()
    print(json.dumps(demo(x.model,x.output,x.seed,x.mode),ensure_ascii=False,indent=2))
