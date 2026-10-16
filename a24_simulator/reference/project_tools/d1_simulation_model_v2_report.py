"""Read completed model-v2/archived evidence; never controls a device or fits coefficients."""
import argparse
import copy
import csv
import json
import math
import statistics
from pathlib import Path
from tools import d1_simulation_model_v2 as m
from tools import d1_simulation_model_v2_campaign as campaign
from tools import d1_arrival_plan as p


def write(folder,name,value):
    campaign.write(Path(folder)/name,value)


def csv_write(folder,name,rows):
    if not rows:return
    with (Path(folder)/name).open('x',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));writer.writeheader();writer.writerows(rows)


def history_check(archive,folder):
    from tools import d1_session_contrast_cost as study
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    candidate=p.read(Path(archive)/'candidate.json');original=p.read(m.prior.MODEL)
    sources=p.read(m.ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')['source_locations']
    expected=p.read(m.ROOT/'docs/results/recovery_service_01/run_v1/inputs.json')['raw_hashes'];scores=[];inventory={}
    for case in study.cases():
        if case['id'] not in sources:continue
        c=copy.deepcopy(case);root=campaign.EXTERNAL/sources[c['id']]
        names={'history_boundary.json':root/'artifacts/history_boundary.json','conditioning_requests.json':root/'artifacts/conditioning_requests.json'}
        for name,path in names.items():
            h=p.digest(path)
            if h!=expected[c['id']+'/'+name]:raise ValueError('raw conditioning source drift')
            inventory[c['id']+'/'+name]=h
        boundary=p.read(names['history_boundary.json']);rows=p.read(names['conditioning_requests.json']);origin=boundary['target_start_ns']
        relative=[dict(r,dispatch_ns=r['dispatch_ns']-origin,lane_available_ns=r['lane_available_ns']-origin) for r in rows]
        c['history']=m.occupancy(relative,boundary['conditioning_start_ns']-origin,0)
        without=m.ap_prediction(case,candidate)[0];with_history,initial=m.ap_prediction(c,candidate)
        a=m.prior.base.common.score(c['ap'],without);b=m.prior.base.common.score(c['ap'],with_history)
        scores.append(dict(id=c['id'],role=c['role'],without_history_mae_c=a['mae_c'],with_history_mae_c=b['mae_c'],
            without_history_max_c=a['max_absolute_error_c'],with_history_max_c=b['max_absolute_error_c'],conditioning_requests=len(rows),
            worsening=b['mae_c']>a['mae_c'],history_intervals=len(c['history']),initial_condition=initial['pre_condition']))
    csv_write(folder,'initial_history.csv',scores)
    write(folder,'summary.json',dict(rows=scores,raw_hashes=inventory,fit_calls=0,device_commands=0,
        evidence='fixed archive coefficients; causal recorded conditioning; posthoc diagnostic, not new holdout',default_change=False))
    return dict(cases=len(scores),worsened=sum(r['worsening'] for r in scores),
        mean_without_c=statistics.mean(r['without_history_mae_c'] for r in scores),mean_with_c=statistics.mean(r['with_history_mae_c'] for r in scores),fit_calls=0)


def actual_service(c):
    rows=c['actual_requests'];out={}
    for priority in ('urgent','normal'):
        group=[r for r in rows if r['priority']==priority];field='output_ready_ns' if priority=='urgent' else 'persist_complete_ns'
        values=sorted((r[field]-r['scheduled_arrival_ns'])/1e6 for r in group if r['terminal_status']=='succeeded' and r.get(field) is not None)
        timely=sum(r['terminal_status']=='succeeded' and r.get(field,math.inf)<=r['deadline_ns'] for r in group)
        completed=sum(r['terminal_status']=='succeeded' for r in group)
        out[priority]=dict(planned=len(group),timely=timely,service_success_rate=timely/len(group),completed=completed)
        out[priority].update(response_P95_ms=values[math.ceil(.95*len(values))-1] if values else None,
            completion_success_rate=completed/len(group),timely_success_rate=timely/len(group),
            terminal_counts={status:sum(r['terminal_status']==status for r in group) for status in ('succeeded','failed','rejected','expired','unfinished')})
    return out


def arrival_assessment(c,model,original):
    tickets=[dict(id=r['request_id'],ordinal=r['ordinal'],task=r['task_id'],priority=r['priority'],arrival_ns=r['offset_ms']*1000000,deadline_offset_ns=r['deadline_ms']*1000000) for r in c['manifest_requests']]
    policy='CPU' if c['policy']=='ARRIVAL_CPU96' else 'PAR';result=m.simulate(tickets,model['service'],policy=policy,mode='mean')
    if any(r['status']!='succeeded' for r in result['ledger']):return dict(status='forecast_unfinished',metrics=result['metrics'],ledger=result['ledger'])
    end=max(c['q'][-1],180.);future=m.occupancy(result['ledger'],0,round(end*1e9));scoped=dict(c,actual=future)
    ap,init=m.ap_prediction(scoped,model);observed_j=m.prior.integral(c,0,120)
    initial=dict(preload=c['pre'],preload_power_w=c['pre_w'])
    legacy_policy='CPU_URGENT_ONLINE_V1' if policy=='CPU' else 'B2_PARALLEL_ONLINE_V1'
    legacy,legacy_ss=m.prior.base.forecast(initial,c['manifest_requests'],legacy_policy,original,planning_input_role='confirmation')
    legacy_cost=m.prior.base.costs(legacy_ss,initial,c['q'],original,end)
    legacy_scores=dict(urgent_response_P95_ms=legacy['metrics']['urgent_p95_ms'],normal_response_mean_ms=legacy['metrics']['normal_mean_ms'],
        energy_signed_j=legacy_cost['whole_120s_j']-observed_j,AP_scores=m.prior.base.common.score(c['ap'],legacy_cost['ap_path']))
    normals=sorted(r['response_ns']/1e6 for r in legacy['ledger'] if r['priority']=='normal' and 'response_ns' in r)
    legacy_scores['normal_response_P95_ms']=normals[math.ceil(.95*len(normals))-1] if normals else None
    legacy_scores['service']={priority:dict(planned=sum(r['priority']==priority for r in legacy['ledger']),
        timely=sum(r['priority']==priority and r['status']=='succeeded' and r.get('response_ns',math.inf)<=r['deadline_offset_ns'] for r in legacy['ledger'])) for priority in ('urgent','normal')}
    return dict(status='forecast_complete',observed_service=actual_service(c),predicted_service=result['metrics'],original_forecast=legacy_scores,
        energy_signed_j=m.energy_at(c,model,120,future)-observed_j,AP_scores=m.prior.base.common.score(c['ap'],ap),
        AP_query_s=c['q'],predicted_AP_c=ap,ledger=result['ledger'],segments=future,initial=init,
        scope='planned arrivals -> fixed CPU/PAR policy -> predicted schedule -> J/AP; new actual targets unused as predictor inputs',accuracy_pass=None)


def report(run,folder):
    run=Path(run);folder=Path(folder)
    terminal=run/'FINAL_RECEIPT.json'
    if not terminal.is_file():
        stops=[f for f in run.glob('*.json') if 'stop' in f.name.lower()]
        if not stops:raise ValueError('run has no terminal receipt; do not publish active work')
        terminal=stops[0]
    receipt=p.read(terminal);plan_file=run.parent/'plan/collection_plan.json';plan=p.read(plan_file)
    if folder.exists():raise ValueError('new report folder required')
    folder.mkdir(parents=True);sessions=[];cases=[];input_hashes={str(terminal):p.digest(terminal),str(plan_file):p.digest(plan_file),str(Path(__file__)):p.digest(__file__)}
    frozen=p.read(run/'development_freeze.json') if (run/'development_freeze.json').is_file() else None
    if p.digest(plan['original_model']['path'])!=plan['original_model']['sha256']:raise ValueError('original model source drift')
    if frozen:
        f=run/'development_freeze.json';fr=run/'freeze_receipt.json'
        if p.digest(f)!=p.read(fr)['sha256']:raise ValueError('frozen model bytes changed')
        if plan.get('prior_freeze') and p.digest(f)!=plan['prior_freeze']['sha256']:raise ValueError('prior frozen model drift')
        input_hashes[str(f)]=p.digest(f);input_hashes[str(fr)]=p.digest(fr)
        for name,h in frozen['development_validated_sha256'].items():
            if p.digest(run/name)!=h:raise ValueError('frozen development data drift')
    original=p.read(plan['original_model']['path']);metrics=[];curves=[];arrivals=[]
    for e in plan['entries']:
        path=run/f"{e['index']:02d}_{e['session_id']}"/'validated.json';row=dict(index=e['index'],role=e['role'],profile=e['profile'],planned_work_cap=e['work_requests'],status='not_validated')
        if path.is_file():
            s=p.read(path);c=s['analysis_case'];cases.append(c);input_hashes[str(path)]=p.digest(path)
            for raw in sorted((path.parent/'artifacts').rglob('*')):
                if raw.is_file():input_hashes[str(raw)]=p.digest(raw)
            for raw in (path.parent/'thermal.jsonl',path.parent/'input_manifest.json',path.parent/'host_cleanup.json'):
                if raw.is_file():input_hashes[str(raw)]=p.digest(raw)
            cleanup=p.read(path.parent/'artifacts/cleanup.json')
            row.update(status='validated',actual_work=s['work_calls'],warmup=s['warmup_calls'],eligibility=s['eligibility_calls'])
            row.update(reused_evidence=e.get('completed_reuse',False) or s.get('reused_evidence',False),post_cleanup_failure=bool(s.get('post_cleanup_failure')),
                application_lifecycle_pass=s.get('application_lifecycle_pass'),APK=p.read(path.parent/'input_manifest.json')['apk_sha256'],
                native_cleanup_status=cleanup['status'],recorded_app_failure_files=[f.name for f in (path.parent/'artifacts').glob('*failure.json')],
                initial_AP_anchor_c=c['pre'][-1]['ap'],initial_power_w=c['pre_w'])
            if frozen:
                score=m.assess(c,frozen['model'],original)
                for name,v in score['scores'].items():metrics.append(dict(session=c['id'],role=c['role'],profile=c['policy'],model=name,**v))
                curves.extend(dict(session=c['id'],role=c['role'],time_s=t,observed_AP_c=y,predicted_AP_c=z) for t,y,z in zip(c['q'],c['ap'],score['predicted_AP_c']))
                if 'manifest_requests' in c:arrivals.append(dict(session=c['id'],result=arrival_assessment(c,frozen['model'],original)))
        sessions.append(row)
    recovery=campaign.recovery_contrasts(cases)
    arrival_rows=[]
    for a in arrivals:
        r=a['result']
        if r['status']!='forecast_complete':continue
        for priority in ('urgent','normal'):
            observed=r['observed_service'][priority];predicted=r['predicted_service'][priority]
            arrival_rows.append(dict(session=a['session'],priority=priority,planned=observed['planned'],
                observed_completed=observed['completed'],observed_timely=observed['timely'],
                observed_P95_ms=observed['response_P95_ms'],v2_P95_ms=predicted['response_P95_ms'],
                original_P95_ms=r['original_forecast'][priority+'_response_P95_ms'],
                v2_completed=predicted['completed'],v2_timely=predicted['timely'],
                v2_J120_signed=r['energy_signed_j'],original_J120_signed=r['original_forecast']['energy_signed_j'],
                v2_AP_MAE_c=r['AP_scores']['mae_c'],original_AP_MAE_c=r['original_forecast']['AP_scores']['mae_c']))
    csv_write(folder,'arrival_scores.csv',arrival_rows)
    csv_write(folder,'sessions.csv',sessions);csv_write(folder,'conditional_scores.csv',metrics);csv_write(folder,'AP_curves.csv',curves);csv_write(folder,'recovery.csv',recovery)
    ledger=[]
    past=[('original_cleanup_failure',dict(path=str(Path(plan['original_run_root'])/'FINAL_RECEIPT.json')))] if plan.get('original_run_root') else []
    for key in ('prior_stopped_receipt','user_pause_source'):
        if plan.get(key):past.append((key,plan[key]))
    for label,spec in past:
        value=p.read(spec['path']);input_hashes[spec['path']]=p.digest(spec['path'])
        if spec.get('sha256') and input_hashes[spec['path']]!=spec['sha256']:raise ValueError('prior terminal receipt changed')
        ledger.append(dict(label=label,path=spec['path'],sha256=input_hashes[spec['path']],status=value['status'],error=value.get('error'),
            completed_sessions=value.get('completed_sessions',value.get('validated_sessions')),physical_attempts=value.get('current_physical_attempts')))
    summary=dict(version=m.VERSION,receipt=receipt,session_roster=sessions,conditional_metrics=metrics,recovery=recovery,
        arrival_forecasts=arrivals,source_hashes=input_hashes,confirmed_sessions=sum(r['status']=='validated' and r['role']=='confirmation' for r in sessions),
        fresh_model_frozen=frozen is not None,thermal_service_feedback=None,accuracy_pass=None,default=False,experiment_ready=False,
        frozen_model_sha256=p.digest(run/'development_freeze.json') if frozen else None,
        experiment_ledger=ledger,cohort_application_lifecycle_pass=False if any(r.get('post_cleanup_failure') for r in sessions) else None,
        source_code_used_for_report={str(Path(module.__file__)):p.digest(module.__file__) for module in (m,campaign,m.prior,m.prior.base)},
        service_success_definition='all planned arrivals denominator; service_success_rate is deadline-met successful completion; completion_success_rate is successful completion regardless of deadline',
        limitations=['fixed1920s slow decay not uniquely identified','one CPU/PAR arrival session per policy; PAR resumed after travel, not simultaneous paired measurement','no new PPO device overhead','no absolute current calibration','stochastic failures unsupported'])
    write(folder,'summary.json',summary)
    if frozen:write(folder,'model.json',frozen['model'])
    import html
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in ('index','role','profile','status','actual_work'))+'</tr>' for r in sessions)
    figures=plots(folder,curves,metrics,recovery)
    headers=('session','priority','observed_completed','observed_timely','observed_P95_ms','original_P95_ms','v2_P95_ms','original_J120_signed','v2_J120_signed','original_AP_MAE_c','v2_AP_MAE_c')
    arrivals_table='<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(round(r[k],4) if isinstance(r[k],float) else r[k]))+'</td>' for k in headers)+'</tr>' for r in arrival_rows)+'</table>'
    (folder/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>D1Check 새 모형 v2</title><style>body{font:16px system-ui;margin:28px;max-width:1200px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:8px}img{max-width:100%}.scroll{overflow-x:auto}h2{margin-top:30px}</style><h1>D1Check 새 시뮬레이션 모형 v2</h1><p>독립 실측/조건부 비용/예정 도착 예측을 구분합니다. 기본 모형 채택·정책 우월성·정확도 PASS는 미판정입니다. 원 종료 실패 계측1의 재사용은 앱 lifecycle PASS가 아니며 CSV에 별도 표시합니다.</p><p><a href="summary.json">전체 수치·근거</a> · <a href="model.json">동결 계수</a> · <a href="sessions.csv">전체8세션 분모</a> · <a href="conditional_scores.csv">조건부 J/AP 오차</a> · <a href="arrival_scores.csv">예정 도착 예측</a> · <a href="recovery.csv">동일 세션 속도/회복</a></p><table><tr><th>순서</th><th>역할</th><th>입력</th><th>상태</th><th>실제 작업</th></tr>'+rows+'</table><h2>예정 도착부터의 예측과 새 실측</h2><p>정책마다 분류/탐지 각48요청입니다. 성공·기한 내 성공의 분모는 전체 도착이며 P95는 완료 요청만 사용합니다. CPU/PAR 각1회이고 PAR은 사용자 이동 후 재개했으므로 초기 조건과 시간 차이가 포함됩니다. 표의 에너지 오차는 예측-관측 J, 온도 오차는 MAE °C입니다.</p><div class="scroll">'+arrivals_table+'</div>'+''.join('<img src="'+f+'" alt="'+f+'">' for f in figures),encoding='utf8')
    return dict(status=receipt['status'],validated=sum(r['status']=='validated' for r in sessions),fresh_model=frozen is not None,confirmed=summary['confirmed_sessions'])


def plots(folder,curves,metrics,recovery):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False;files=[]
    if curves:
        ids=list(dict.fromkeys(r['session'] for r in curves));fig,axes=plt.subplots(math.ceil(len(ids)/2),2,figsize=(12,3*math.ceil(len(ids)/2)),squeeze=False)
        for ax,sid in zip(axes.flat,ids):
            rows=[r for r in curves if r['session']==sid]
            ax.plot([r['time_s'] for r in rows],[r['observed_AP_c'] for r in rows],label='관측',lw=1.3)
            ax.plot([r['time_s'] for r in rows],[r['predicted_AP_c'] for r in rows],label='동결 v2',lw=1.3)
            ax.set_title(sid);ax.set_ylabel('HAL AP °C');ax.set_xlabel('공통 원점 이후 초');ax.legend()
        for ax in list(axes.flat)[len(ids):]:ax.axis('off')
        fig.suptitle('실제 일정 조건부 AP — 개발과 새 확인을 분리');fig.tight_layout();fig.savefig(Path(folder)/'AP_paths.png',dpi=140);plt.close(fig);files.append('AP_paths.png')
    if metrics:
        ids=list(dict.fromkeys(r['session'] for r in metrics));fig,ax=plt.subplots(figsize=(12,4));x=list(range(len(ids)))
        for name,shift,color in [('original',-.18,'#b45309'),('v2',.18,'#0e7490')]:
            vals=[abs(next(r['120s_energy_signed_j'] for r in metrics if r['session']==sid and r['model']==name)) for sid in ids]
            ax.bar([v+shift for v in x],vals,width=.36,label=name,color=color)
        ax.set_xticks(x,ids,rotation=30,ha='right');ax.set_ylabel('|예측-관측| J / 공통120초');ax.set_title('기기 전체 조건부 에너지 오차 — mA 단위 해석, 절대 정확도 미인증');ax.legend();fig.tight_layout();fig.savefig(Path(folder)/'energy_error.png',dpi=140);plt.close(fig);files.append('energy_error.png')
    if recovery:
        fig,axes=plt.subplots(1,3,figsize=(12,4));labels=['before','immediate','after90','after240']
        for ax,key in zip(axes,('classification_CPU','classification_GPU','detection_CPU')):
            for sid in dict.fromkeys(r['session'] for r in recovery):
                use=[r for r in recovery if r['session']==sid and r['key']==key];role=use[0]['role']
                ax.plot(range(4),[next(r['change_from_before_percent'] for r in use if r['stage']==s) for s in labels],marker='o',alpha=.65,color='#0e7490' if role=='confirmation' else '#b45309',label=role)
            ax.axhline(0,color='gray',lw=.7);ax.set_xticks(range(4),['부하 전','직후','약90초','약240초']);ax.set_title(key);ax.set_ylabel('같은 세션 부하 전 대비 추론시간 %')
        fig.suptitle('동일 요청 탐침: 주황=개발, 파랑=새 확인 · 온도의 인과효과는 미확정');fig.tight_layout();fig.savefig(Path(folder)/'recovery_probe.png',dpi=140);plt.close(fig);files.append('recovery_probe.png')
    return files


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['history','report']);a.add_argument('--output',required=True);a.add_argument('--archive');a.add_argument('--run');x=a.parse_args()
    print(json.dumps(history_check(x.archive,x.output) if x.action=='history' else report(x.run,x.output),ensure_ascii=False,indent=2))
