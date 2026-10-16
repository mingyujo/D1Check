"""Constraint-first Pareto readout of existing PC results; not an online policy.

No model fitting, new simulation, device command or assumed accuracy bound.
Different input seeds/registration blocks are never compared as paired trials.
"""
import argparse
import csv
import html
import json
import math
from pathlib import Path
from tools import d1_method_followup_report as source

METRICS=('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms')
TOL=1e-8  # Floating-point readout only, never a measured accuracy tolerance.


def dominates(left,right):
    if not left['complete_service_and_metrics'] or not right['complete_service_and_metrics']:return False
    a=[left['max_delta_'+k] for k in METRICS];b=[right['max_delta_'+k] for k in METRICS]
    return all(x<=y+TOL for x,y in zip(a,b)) and any(x<y-TOL for x,y in zip(a,b))


def summarize(records,block,stage,caps):
    if set(caps)-set(METRICS) or any(type(x) not in (int,float) or not math.isfinite(x) for x in caps.values()):
        raise ValueError('caps must be explicitly named finite relative quantities')
    selected=[z['meta'] for z in records if z['meta']['stage']==stage]
    rows=[]
    for envelope in sorted(set(z['envelope'] for z in selected)):
        members=[z for z in selected if z['envelope']==envelope]
        refs={(z['seed'],z['scenario']):z for z in members if z['policy']=='EFT_REFERENCE'}
        expected={(seed,context) for seed in set(z['seed'] for z in refs.values())
                  for context in ('mean','short_context','long_context')}
        if len(refs)!=6 or set(refs)!=expected:raise ValueError('incomplete registered seed/context reference')
        local=[]
        for policy in sorted(set(z['policy'] for z in members)):
            ms=[z for z in members if z['policy']==policy]
            coordinates={(z['seed'],z['scenario']) for z in ms}
            if len(ms)!=6 or coordinates!=expected:raise ValueError('partial or duplicated candidate block')
            if any(z['planned']!=48 for z in ms):raise ValueError('full arrival denominator must be 48 per case')
            known=all(type(z.get(k)) in (int,float) and math.isfinite(z[k]) for z in [*ms,*refs.values()] for k in METRICS)
            complete=known and all(z['deadline_met']==z['completed']==z['planned'] for z in ms)
            row=dict(comparison_block=block,stage=stage,envelope=envelope,policy=policy,
                seed_ids=','.join(map(str,sorted(set(z['seed'] for z in ms)))),cases=len(ms),
                planned=sum(z['planned'] for z in ms),deadline_met=sum(z['deadline_met'] for z in ms),
                complete_service_and_metrics=complete,model_metrics_known=known,
                **{'max_delta_'+k:max(z[k]-refs[z['seed'],z['scenario']][k] for z in ms) if known else None for k in METRICS},
                equivalent_to_reference=(known and all(abs(z[k]-refs[z['seed'],z['scenario']][k])<=TOL for z in ms for k in METRICS)),
                epsilon_feasible=(complete and all(max(z[k]-refs[z['seed'],z['scenario']][k] for z in ms)<=v+TOL for k,v in caps.items())),
                pareto_candidate=False,accuracy_pass=None,device_policy_winner=None,deployment_allowed=False)
            local.append(row)
        for row in local:
            row['pareto_candidate']=row['complete_service_and_metrics'] and not any(dominates(other,row) for other in local)
        rows.extend(local)
    return rows


def readout(root,stage,caps):
    root=Path(root);source.f.x.p.inputs(source.f.x.p.BUNDLE)
    rows=[];checks={}
    for block in ('run_v1','beam_v1','beam_v2'):
        registration=json.loads((root/block/'registered_before_run.json').read_text(encoding='utf8'))
        checks[block]={f:source.verify_registered_source(f,digest,root) for f,digest in registration['hashes'].items()}
        rows.extend(summarize(source.records(root/block/'records.jsonl.gz'),block,stage,caps))
    return dict(protocol='registered-pc-method-readout-v1',selection_type='posthoc evidence; not a causal controller',
        stage=stage,explicit_relative_caps=caps,metric_directions='all smaller is preferred; service before cost',
        comparison='within one registration block/envelope, exact same seeds and full five-phase contexts',
        delta_aggregation='maximum candidate minus its own EFT across six saved cases; not future confidence bounds',
        counterfactual_accuracy_bounds=None,accuracy_pass=None,device_policy_winner=None,deployment_allowed=False,
        physical_cost_hash=source.f.x.p.MODEL_SHA,initial_hash=source.f.x.p.INITIAL_SHA,
        registered_source_checks=checks,rows=rows,new_simulations=0,device_commands=0,experiment_ready=False)


def save(result,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source.f.x.p.write(output/'result.json',result)
    source.f.x.old.csv_write(output/'constraints_and_frontiers.csv',result['rows'])
    columns=('comparison_block','envelope','policy','seed_ids','deadline_met','planned',
        'complete_service_and_metrics','equivalent_to_reference','epsilon_feasible','pareto_candidate',*('max_delta_'+k for k in METRICS))
    headers=''.join('<th>'+html.escape(k)+'</th>' for k in columns)
    body=''.join('<tr>'+''.join('<td>'+html.escape('미판정' if row[k] is None else str(round(row[k],6) if type(row[k]) is float else row[k]))+'</td>' for k in columns)+'</tr>' for row in result['rows'])
    (output/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>기한 제약과 모형 상충 판독</title>
    <style>body{font:16px system-ui;margin:24px;color:#203347}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #bbb;padding:6px}th{background:#eaf0f6}.note{background:#fff2ce;padding:16px}.tablewrap{overflow-x:auto}</style>
    <h1>저장된 방법론 비교: 기한→지원된 비용→상충</h1>
    <p class="note">새 시뮬레이션·실측·재학습0. 이 표는 사후 PC 결과 판독이며 실제 승자/배포 추천은 null입니다. 기한 충족은 전체48요청×6사례(2seed×3문맥) 기준이며 모형 정확도 PASS가 아닙니다. 각 block/입력 내부에서만 같은 seed의 EFT와 대조합니다.</p>
    <p>각 Δ는 여섯 저장 사례의 최댓값입니다. 미래 오차한도/WCET가 아닙니다. Pareto 표시는5지표 상충을 보여주고, epsilon 표시는 사용자가 명시한 상대 제약을 판독합니다. 허용폭은 연구 합격선·안전 인증이 아닙니다.</p>
    <p>명시한 상대 제약: '''+html.escape(json.dumps(result['explicit_relative_caps'],ensure_ascii=False))+'''</p>
    <p><a href="constraints_and_frontiers.csv">CSV</a> · <a href="result.json">출처·미확인·기준</a></p>
    <div class="tablewrap"><table><tr>'''+headers+'</tr>'+body+'</table></div></html>',encoding='utf8')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(source.f.ROOT));ap.add_argument('--output',required=True)
    ap.add_argument('--stage',choices=('stored_regression','new_seed_confirmation'),default='new_seed_confirmation')
    caps=ap.add_mutually_exclusive_group()
    caps.add_argument('--relative-caps-json',default='{}',help='Explicit PC exploratory relative constraints; no automatic objective weights')
    caps.add_argument('--relative-caps-file',help='UTF-8 JSON of explicitly declared PC relative caps')
    args=ap.parse_args();limits=json.loads(Path(args.relative_caps_file).read_text(encoding='utf-8-sig') if args.relative_caps_file else args.relative_caps_json)
    save(readout(args.root,args.stage,limits),args.output)
