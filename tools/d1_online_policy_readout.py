"""Portable plots and explicitly scoped policy-model replay; no device operations."""
import argparse
import csv
import html
import json
from pathlib import Path
from tools import d1_online_policy_model as model
from tools import d1_arrival_plan as p


def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def export(root,output):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=False)
    freeze=p.read(root/'model_freeze.json');rows=[];cases=[]
    for phase in ('development','confirmation'):
        for c in p.read(root/(phase+'_cases.json')):
            cases.append(dict(id=c['id'],phase=phase,policy=c['policy'],initial={'preload':c['inputs']['preload'],'preload_power_w':c['preload_power_w']},manifest_requests=c['manifest_requests']))
        rows+=p.read(root/(phase+'_evaluation.json'))
    write(output/'model.json',freeze['model']);write(output/'initial_inputs.json',cases)
    write(output/'evaluation.json',rows)
    flat=[]
    for r in rows:
        for mode,out in r['outputs'].items():
            flat.append(dict(id=r['id'],phase=r['phase'],policy=r['policy'],prediction=mode,
                observed_120s_j=r['observed_120s_j'],predicted_120s_j=out['whole_120s_j'],energy_signed_error_j=out['energy_signed_error_j'],
                energy_relative_error=out['energy_relative_error'],**out['ap_scores'],
                actual_urgent_p95_ms=r['service']['actual_urgent']['p95_ms'],predicted_urgent_p95_ms=r['service']['predicted_urgent']['p95_ms'],
                actual_deadline_met=r['service']['actual_all']['deadline_met'],planned=96,accuracy_pass=None))
    with (output/'summary.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    pairs=[];confirmed=[r for r in rows if r['phase']=='confirmation']
    for index in range(2):
        selected={policy:[r for r in confirmed if r['policy']==policy][index] for policy in model.POLICIES}
        for policy in model.POLICIES[1:]:
            cpu,alt=selected[model.POLICIES[0]],selected[policy]
            pairs.append(dict(repeat=index,policy=policy,observed_j_difference=alt['observed_120s_j']-cpu['observed_120s_j'],
                predicted_j_difference=alt['outputs']['arrival_forecast']['whole_120s_j']-cpu['outputs']['arrival_forecast']['whole_120s_j'],
                observed_urgent_p95_ms_difference=alt['service']['actual_urgent']['p95_ms']-cpu['service']['actual_urgent']['p95_ms'],
                observed_peak_ap_difference=max(alt['observed_ap_c'])-max(cpu['observed_ap_c']),
                initial_ap_difference=alt['common_start_ap_c']-cpu['common_start_ap_c'],
                interpretation='separate session arithmetic difference; initial/history variation retained, not causal confidence interval'))
    write(output/'policy_differences.json',pairs)
    write(output/'resources.json',dict(files={f.name:p.digest(f) for f in output.iterdir() if f.is_file()},source_freeze_sha256=p.digest(root/'model_freeze.json'),
        experiment_ready=False,accuracy_pass=None,scope=freeze['model']['scope']))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    links=[]
    for r in rows:
        fig,axes=plt.subplots(1,3,figsize=(15,3.4),constrained_layout=True)
        energy=r['observed_energy_path'];axes[0].plot([x['common_s'] for x in energy],[x['observed_j'] for x in energy],label='observed',color='black')
        axes[1].plot(r['ap_query_s'],r['observed_ap_c'],label='observed',color='black')
        for mode,out in r['outputs'].items():
            axes[0].plot([x['common_s'] for x in out['energy_path']],[x['predicted_j'] for x in out['energy_path']],label=mode)
            axes[1].plot(r['ap_query_s'],out['ap_path'],label=mode)
            axes[2].plot(r['ap_query_s'],[v-y for v,y in zip(out['ap_path'],r['observed_ap_c'])],label=mode)
        axes[1].plot(r['ap_query_s'],r['outputs']['actual_schedule_conditional']['original_m0_ap_path'],label='previous M0',linestyle=':')
        for ax,label in zip(axes,['Cumulative J','AP C','Predicted - observed C']):ax.set_xlabel('Common seconds');ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(fontsize=7)
        fig.suptitle(r['id']+'; '+r['phase']+'; no universal accuracy PASS')
        name=r['id']+'.svg';fig.savefig(output/name);plt.close(fig);links.append('<h2>'+html.escape(r['id'])+'</h2><img width="100%" src="'+name+'">')
    table='<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in flat[0])+'</tr>'
    for r in flat:table+='<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r.values())+'</tr>'
    table+='</table>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>D1Check 온라인 정책 모형</title><style>body{font:15px system-ui;margin:30px}table{border-collapse:collapse;font-size:12px}td,th{padding:6px;border:1px solid #ccc}</style><h1>도착·배정·대기 → 일정·에너지·AP</h1><p>개발3과 확인6을 분리합니다. 확인은 정책별2회이며 독립 세션 변동성의 정밀 추정이 아닙니다. 부하 전 AP/전력은 허용 초기 입력이고 이후 관측값은 예측에 사용하지 않습니다. 실제 일정 조건부와 예정 도착 예측을 별도로 표시합니다. 전류 raw=mA 조건부, 절대 정확도 미인증. 기본/strict/experiment_ready=false 유지.</p>'+table+''.join(links),encoding='utf8')
    return dict(output=str(output),cases=len(rows),device_commands=0)


def predict(bundle,case_id,policy,output):
    bundle,output=Path(bundle),Path(output);resources=p.read(bundle/'resources.json')
    for name,digest in resources['files'].items():
        f=(bundle/name).resolve()
        if f.parent!=bundle.resolve() or p.digest(f)!=digest:raise ValueError('bundle identity')
    cases=[c for c in p.read(bundle/'initial_inputs.json') if c['id']==case_id]
    if len(cases)!=1 or policy not in model.POLICIES:raise ValueError('registered initial input/policy required')
    c=cases[0];frozen=p.read(bundle/'model.json');ledger,segments=model.forecast(c['initial'],c['manifest_requests'],policy,frozen)
    costs=model.costs(segments,c['initial'],list(range(35,181)),frozen,180)
    output.mkdir(parents=True,exist_ok=False)
    write(output/'result.json',dict(route='online-policy',policy=policy,initial_case_id=case_id,forecast=ledger,costs=costs,
        uses_future_measurements=False,initialization='registered pre35 AP and pre10..30 W',
        scope=frozen['scope'],accuracy_pass=None,experiment_ready=False,device_commands=0))
    return dict(output=str(output),whole_120s_j=costs['whole_120s_j'],device_commands=0)


def main():
    q=argparse.ArgumentParser();sub=q.add_subparsers(dest='action',required=True)
    a=sub.add_parser('export');a.add_argument('--root',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('predict')
    for k in ('bundle','case-id','policy','output'):a.add_argument('--'+k,required=True)
    a=q.parse_args();r=export(a.root,a.output) if a.action=='export' else predict(a.bundle,a.case_id,a.policy,a.output)
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
