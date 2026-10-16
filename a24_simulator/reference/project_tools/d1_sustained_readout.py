"""Offline, frozen-model transfer readout. Never fits or calls ADB."""
import argparse
import csv
import html
import json
import statistics
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_online_policy_model as model
from tools import d1_sustained_protocol as protocol
from tools import d1_sustained_plan as plan_source


def write(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def csv_write(path,rows):
    if not rows:return
    with Path(path).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def consumption(root,plan):
    root=Path(root);sessions=[]
    kinds=('runtime_start','runtime_return','warmup_start','warmup_return','request_start',
           'host_inference_start','host_inference_return','output_ready','persist_complete','lane_available')
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        files=[folder/x for x in ('artifacts/progress.jsonl','failure_prefix/progress.jsonl','recovery_prefix/progress.jsonl')]
        f=next((f for f in files if f.is_file()),None)
        events,partial=[],0
        if f:
            from tools.d1_energy_collection import progress_prefix
            events,partial=progress_prefix(f.read_bytes())
        launched=(folder/'launch_attempt.json').is_file()
        counts={k:(sum(e.get('kind')==k for e in events) if f else (None if launched else 0)) for k in kinds}
        sessions.append(dict(index=entry['index'],policy=entry['policy'],attempted=(folder/'attempt.json').is_file(),
            launch_attempted=launched,completed=(folder/'validated.json').is_file(),
            durable_progress_available=f is not None,partial_lines=partial,counts=counts,
            unrecorded_explicit_upper_bound=(max(0,200-(counts['warmup_start'] or 0)-(counts['request_start'] or 0))
                if launched and not (folder/'validated.json').is_file() else 0)))
    commands=[]
    for folder in sorted((root/'host_commands').glob('*')):
        f=folder/'client/result.json'
        if f.is_file():commands.append(p.read(f))
    argv=[r.get('command',[]) for r in commands]
    # Transport is retained only in external originals; counters omit identifiers.
    def tail(a):return a[3:] if len(a)>2 and a[1]=='-s' else a[1:]
    args=[tail(a) for a in argv]
    installed=root/'installation/installation_receipt.json'
    install=p.read(installed) if installed.is_file() else {}
    result=dict(sessions=sessions,session_attempts=sum(s['attempted'] for s in sessions),
        completed_sessions=sum(s['completed'] for s in sessions),unattempted_sessions=sum(not s['attempted'] for s in sessions),
        confirmed_counts={k:sum(s['counts'][k] or 0 for s in sessions) for k in kinds},
        unknown_progress_sessions=sum(s['launch_attempted'] and not s['durable_progress_available'] for s in sessions),
        adb_command_slots=len(list((root/'host_commands').glob('*'))),recorded_client_results=len(commands),
        installed_host_pulls=sum(bool(a) and a[0]=='pull' for a in args),
        apk_push_attempts=sum(bool(a) and a[0]=='push' and str(a[1]).lower().endswith('.apk') for a in args),
        install_attempts=sum(a[:3]==['shell','pm','install'] for a in args),
        staging_file_push_attempts=sum(bool(a) and a[0]=='push' and not str(a[1]).lower().endswith('.apk') for a in args),
        host_force_stop_commands=sum(a[:3]==['shell','am','force-stop'] for a in args),
        installation_verified=install.get('status')=='verified',
        installed_sha256=install.get('installed_sha256'),missing_calls_not_zero=True)
    return result


def analyze(plan_file,output):
    plan_file,output=Path(plan_file),Path(output)
    plan=p.read(plan_file);root=Path(plan['output_root']);receipt=p.read(root/'FINAL_RECEIPT.json')
    if p.digest(plan['study_freeze']['path'])!=plan_source.MODEL_SHA:raise ValueError('frozen model drift')
    if p.digest(plan_file)!=p.digest(root/'frozen_collection_plan.json'):raise ValueError('plan drift')
    frozen=p.read(plan['study_freeze']['path']);cases=[];excluded=[]
    for entry in plan['entries']:
        if not (root/f"{entry['index']:02d}_{entry['session_id']}"/'validated.json').is_file():continue
        try:
            c=model.load_case(plan_file,plan,entry)
            # This is the unchanged frozen model's declared initial window.
            c['preload_power_w']=model.energy_at(c,-20,30)/50
            c['index']=entry['index'];cases.append(c)
        except Exception as e:excluded.append(dict(index=entry['index'],reason=repr(e),prediction=None))
    evaluation=model.evaluate(cases,frozen,planning_input_role=protocol.VERSION)
    output.mkdir(parents=True,exist_ok=False);rows=[];curves=[];timing=[];segments=[];initial=[]
    for c,r in zip(cases,evaluation):
        initial.append(dict(id=r['id'],index=c['index'],policy=r['policy'],initial=dict(
            preload=c['inputs']['preload'],preload_power_w=c['preload_power_w']),manifest_requests=c['manifest_requests']))
        exposure=model.exposure(c['inputs']['segments'],0,120)
        ap_gaps=[b-a for a,b in zip(c['inputs']['query_s'],c['inputs']['query_s'][1:])]
        power_times=sorted((s['mono_ns']-c['origin_ns'])/1e9 for s in c['power_samples'] if 0<=s['mono_ns']-c['origin_ns']<=120e9)
        power_gaps=[b-a for a,b in zip(power_times,power_times[1:])]
        for mode,out in r['outputs'].items():
            rows.append(dict(index=c['index'],pair=c['index']//2,policy=r['policy'],prediction=mode,
                observed_120s_j=r['observed_120s_j'],predicted_120s_j=out['whole_120s_j'],
                energy_signed_error_j=out['energy_signed_error_j'],energy_absolute_error_j=abs(out['energy_signed_error_j']),
                energy_relative_error=out['energy_relative_error'],**out['ap_scores'],
                common_start_ap_c=c['common_start_ap_c'],preload_power_w=c['preload_power_w'],
                ap_window_start_s=c['inputs']['query_s'][0],ap_window_end_s=c['inputs']['query_s'][-1],
                ap_samples=len(c['observed_ap_c']),observed_peak_ap_c=max(c['observed_ap_c']),predicted_peak_ap_c=max(out['ap_path']),
                ap_median_interval_s=statistics.median(ap_gaps),ap_max_gap_s=max(ap_gaps),
                power_common_samples=len(power_times),power_median_interval_s=statistics.median(power_gaps),power_max_gap_s=max(power_gaps),
                actual_urgent_p95_ms=r['service']['actual_urgent']['p95_ms'],predicted_urgent_p95_ms=r['service']['predicted_urgent']['p95_ms'],
                actual_deadline_met=r['service']['actual_all']['deadline_met'],predicted_deadline_met=r['service']['predicted_all']['deadline_met'],
                planned=192,overlap_s=float(exposure[3]),last_lane_s=c['last_lane_s'],
                strict_supported=False,accuracy_pass=None,protocol_transfer=True))
            for a,b in zip(out['energy_path'][1:],r['observed_energy_path']):
                curves.append(dict(index=c['index'],mode=mode,common_s=a['common_s'],observed_j=b['observed_j'],predicted_j=a['predicted_j'],residual_j=a['predicted_j']-b['observed_j']))
            for t,y,v in zip(r['ap_query_s'],r['observed_ap_c'],out['ap_path']):
                curves.append(dict(index=c['index'],mode=mode,common_s=t,observed_j=None,predicted_j=None,residual_j=None,
                    observed_ap_c=y,predicted_ap_c=v,residual_ap_c=v-y))
        for t in r['timing']:timing.append(dict(index=c['index'],**t))
        for s in r['actual_segments']:segments.append(dict(index=c['index'],**s))
    counterfactual=[]
    for c in cases:
        initial_input=dict(preload=c['inputs']['preload'],preload_power_w=c['preload_power_w'])
        outputs=[]
        for policy in protocol.POLICIES:
            _,predicted_segments=model.forecast(initial_input,c['manifest_requests'],policy,frozen,planning_input_role=protocol.VERSION)
            costs=model.costs(predicted_segments,initial_input,c['inputs']['query_s'],frozen,c['inputs']['segments'][-1]['end_s'])
            outputs.append(costs)
        counterfactual.append(dict(initial_index=c['index'],par_minus_cpu_j=outputs[1]['whole_120s_j']-outputs[0]['whole_120s_j'],
            peak_ap_difference_c=max(outputs[1]['ap_path'])-max(outputs[0]['ap_path']),
            observed_policy_comparison=False,uses_future_measurements=False,policy_winner=None))
    pairs=[]
    for pair in range(4):
        selected={r['policy']:r for r in rows if r['pair']==pair and r['prediction']=='arrival_forecast'}
        complete=all(k in selected for k in protocol.POLICIES)
        row=dict(pair=pair,complete=complete,observed_par_minus_cpu_j=None,predicted_par_minus_cpu_j=None,
            observed_peak_ap_difference_c=None,initial_ap_difference_c=None,preload_power_difference_w=None,urgent_p95_difference_ms=None)
        if complete:
            a,b=[selected[k] for k in protocol.POLICIES]
            for key,field in (('observed_par_minus_cpu_j','observed_120s_j'),('predicted_par_minus_cpu_j','predicted_120s_j'),
                ('observed_peak_ap_difference_c','observed_peak_ap_c'),('initial_ap_difference_c','common_start_ap_c'),
                ('preload_power_difference_w','preload_power_w'),('urgent_p95_difference_ms','actual_urgent_p95_ms')):row[key]=b[field]-a[field]
        pairs.append(row)
    # Heterogeneous AP/J rows retain blank fields; never zero-fill missing outputs.
    fields=list(dict.fromkeys(k for r in curves for k in r))
    csv_write(output/'curves.csv',[{k:r.get(k) for k in fields} for r in curves])
    csv_write(output/'metrics.csv',rows);csv_write(output/'timing.csv',timing);csv_write(output/'segments.csv',segments)
    csv_write(output/'pair_differences.csv',pairs)
    csv_write(output/'counterfactual_differences.csv',counterfactual)
    write(output/'initial_inputs.json',initial)
    (output/'model.json').write_bytes(Path(plan['study_freeze']['path']).read_bytes())
    differences=[x['observed_par_minus_cpu_j'] for x in pairs if x['complete']]
    pair_summary=dict(complete_pairs=len(differences),mean_observed_par_minus_cpu_j=statistics.mean(differences) if differences else None,
        min_observed_difference_j=min(differences) if differences else None,max_observed_difference_j=max(differences) if differences else None,
        descriptive_sd_j=statistics.stdev(differences) if len(differences)>1 else None,
        future_error_bound=None,causal_effect_established=False)
    result=dict(version=protocol.VERSION,plan_sha256=p.digest(plan_file),model_sha256=plan_source.MODEL_SHA,
        receipt_status=receipt['status'],elapsed_seconds=receipt['elapsed_seconds'],planned_sessions=8,
        prediction_eligible_sessions=len(cases),prediction_exclusions=excluded,metrics=rows,pairs=pairs,
        consumption=consumption(root,plan),counterfactual=counterfactual,pair_summary=pair_summary,accuracy_pass=None,policy_winner=None,strict_supported=False,
        experiment_ready=False,fitting_performed=False,ap_limit_seconds_error=None,
        limitation='독립 전이 block. 작은 J/AP 정책 우열/미래 오차 한도 미검증. raw current=mA 조건부/절대 정확도 미인증',
        source_files=dict(receipt=p.digest(root/'FINAL_RECEIPT.json'),analysis_contract=plan['analysis_contract']['sha256']))
    write(output/'summary.json',result)
    render(output,evaluation,result)
    write(output/'resources.json',dict(files={f.name:p.digest(f) for f in output.iterdir() if f.is_file()},
        source_plan_sha256=p.digest(plan_file),source_receipt_sha256=p.digest(root/'FINAL_RECEIPT.json'),
        analysis_code_sha256=p.digest(__file__),device_commands=0))
    if p.digest(plan['study_freeze']['path'])!=plan_source.MODEL_SHA:raise ValueError('frozen drift after analysis')
    return result


def predict(bundle,index,policy,output,purpose='descriptive'):
    from tools.d1_separated_power_readout import decision_support
    support=decision_support(purpose)
    bundle,output=Path(bundle),Path(output);resources=p.read(bundle/'resources.json')
    for name,digest in resources['files'].items():
        f=(bundle/name).resolve()
        if f.parent!=bundle.resolve() or p.digest(f)!=digest:raise ValueError('bundle hash')
    frozen=p.read(bundle/'model.json')
    if p.digest(bundle/'model.json')!=plan_source.MODEL_SHA:raise ValueError('frozen model bytes')
    matches=[c for c in p.read(bundle/'initial_inputs.json') if c['index']==index]
    if len(matches)!=1:raise ValueError('one registered initial input required')
    c=matches[0];protocol.validate(c['manifest_requests'],policy)
    initial={k:c['initial'][k] for k in ('preload','preload_power_w')}
    forecast,segments=model.forecast(initial,c['manifest_requests'],policy,frozen,planning_input_role=protocol.VERSION)
    costs=model.costs(segments,initial,list(range(35,181)),frozen,180)
    output.mkdir(parents=True,exist_ok=False)
    result=dict(protocol=protocol.VERSION,initial_index=index,policy=policy,forecast=forecast,costs=costs,
        initial_input='observed pre-load AP history and [-20,30] mean W only',uses_future_measurements=False,
        strict_supported=False,accuracy_pass=None,experiment_ready=False,decision_support=support,device_commands=0)
    write(output/'result.json',result);return dict(output=str(output),whole_120s_j=costs['whole_120s_j'],device_commands=0)


def render(output,evaluation,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    links=[]
    for i,r in enumerate(evaluation):
        fig,ax=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
        e=r['observed_energy_path'];ax[0,0].plot([x['common_s'] for x in e],[x['observed_j'] for x in e],color='black',label='observed')
        ax[0,1].plot(r['ap_query_s'],r['observed_ap_c'],color='black',label='observed')
        for mode,out in r['outputs'].items():
            ax[0,0].plot([x['common_s'] for x in out['energy_path']],[x['predicted_j'] for x in out['energy_path']],label=mode)
            ax[0,1].plot(r['ap_query_s'],out['ap_path'],label=mode)
            ax[1,0].plot(r['ap_query_s'],[v-y for v,y in zip(out['ap_path'],r['observed_ap_c'])],label=mode)
        for source,rows in [('actual',r['actual_rows']),('forecast',r['forecast_ledger'])]:
            for q in rows:
                backend=q.get('selected_backend',q.get('backend'))
                start=q['dispatch_ns']/1e9;end=q['lane_available_ns']/1e9
                ax[1,1].barh(source+' '+str(backend),end-start,left=start,
                    color='tab:blue' if q.get('task_id',q.get('task'))=='classification' else 'tab:orange')
        for a,title in zip(ax.flat,['Common0..120 cumulative J','AP common35..cooling_end C','Predicted - observed AP C','Actual vs forecast lane occupation (blue classification)']):
            a.set_title(title);a.set_xlabel('Common seconds');a.grid(alpha=.2)
        for a in ax.flat[:3]:a.legend(fontsize=7)
        fig.suptitle(r['id']+'; independent transfer / no accuracy PASS')
        name=f'session_{i:02d}.png';fig.savefig(output/name,dpi=130);plt.close(fig)
        links.append(f'<h2>{html.escape(r["id"])}</h2><img src="{name}" width="100%">')
    dashboard(output,summary,links)


def dashboard(output,summary,links=None):
    output=Path(output)
    if links is None:
        cases=[r for r in summary['metrics'] if r['prediction']=='arrival_forecast']
        links=[f'<h2>Session {r["index"]}: {html.escape(r["policy"])}</h2><img src="session_{i:02d}.png" width="100%">' for i,r in enumerate(cases)]
    fields=('index','policy','prediction','observed_120s_j','energy_signed_error_j','mae_c','max_absolute_error_c','actual_deadline_met')
    table='<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in fields)+'</tr>'
    for r in summary['metrics']:table+='<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in fields)+'</tr>'
    pairs='<table><tr><th>쌍</th><th>관측 PAR−CPU J</th><th>최고 AP 차이 °C</th><th>초기 AP 차이 °C</th><th>부하 전 W 차이</th><th>긴급 P95 차이 ms</th></tr>'
    for r in summary['pairs']:
        pairs+='<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ('pair','observed_par_minus_cpu_j','observed_peak_ap_difference_c','initial_ap_difference_c','preload_power_difference_w','urgent_p95_difference_ms'))+'</tr>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>D1Check sustained CPU/PAR</title><style>body{font:15px system-ui;max-width:1300px;margin:30px auto}td,th{border:1px solid #bbb;padding:6px}table{border-collapse:collapse;font-size:12px}pre{white-space:pre-wrap}img{max-width:100%}</style><h1>192요청 CPU/PAR 전이 비교</h1><p>실측·실제 일정 조건부 A·예정 도착 예측 B를 구분. 모형 재적합 없음. 예측 입력은 부하 전 AP 이력/전력과 등록된 입력이며 미래 AP/전류는 사용하지 않음. 기존96요청 확인과 별도 block.</p><p>strict=false, accuracy_pass=null, policy_winner=null, experiment_ready=false. raw 전류=mA 조건부 해석·절대 에너지 정확도 미인증. 전체 기기 J이며 CPU/GPU rail 전력 아님.</p><p>지원: 등록된 192요청/400ms CPU·PAR 입력에 대한 제한 전이 평가·초기조건부 예측. 임의 도착/온도/기기/열에 따른 처리율, 작은 에너지·열 차이에 의한 정책 선택은 미지원.</p><p><a href="README.md">판독·재현</a> · <a href="metrics.csv">오차표</a> · <a href="curves.csv">경로 CSV</a> · <a href="timing.csv">일정 차이</a> · <a href="segments.csv">실제 상태</a> · <a href="pair_differences.csv">관측 쌍별 차이</a> · <a href="counterfactual_differences.csv">동일 초기조건의 모형 차이</a></p><pre>'+html.escape(json.dumps({k:summary[k] for k in ('receipt_status','planned_sessions','prediction_eligible_sessions','prediction_exclusions')},ensure_ascii=False,indent=2))+'</pre><h2>세션별 관측·예측</h2>'+table+'</table><h2>쌍별 관측 비교</h2><p>서로 다른 초기 AP·배경 전력·실행 시각을 그대로 표시. 인과 효과·미래 오차 한도·정책 우월성 미판정. 동일 초기조건의 모형 PAR−CPU −2.091J는 실제 쌍별 관측 차이와 구분.</p>'+pairs+'</table><pre>'+html.escape(json.dumps(summary['pair_summary'],ensure_ascii=False,indent=2))+'</pre>'+''.join(links),encoding='utf8')


if __name__=='__main__':
    a=argparse.ArgumentParser();sub=a.add_subparsers(dest='action',required=True)
    x=sub.add_parser('analyze');x.add_argument('--plan',required=True);x.add_argument('--output',required=True)
    x=sub.add_parser('predict');x.add_argument('--bundle',required=True);x.add_argument('--index',type=int,required=True)
    x.add_argument('--policy',required=True);x.add_argument('--output',required=True)
    x.add_argument('--purpose',choices=['descriptive','energy-ap-policy-selection'],default='descriptive')
    q=a.parse_args()
    if q.action=='analyze':
        r=analyze(q.plan,q.output);r=dict(status=r['receipt_status'],eligible=r['prediction_eligible_sessions'],consumption=r['consumption'])
    else:r=predict(q.bundle,q.index,q.policy,q.output,q.purpose)
    print(json.dumps(r,indent=2))
