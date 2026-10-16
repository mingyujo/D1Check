"""Add explicit AP/SKIN observation windows after the frozen v1 readout."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import statistics

from tools import d1_overnight_device_report as original
from tools import d1_overnight_device_replay as r
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_analysis as observed
from tools import d1_energy_thermal as energy
from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v3_thermal as thermal


def corrected_cost_validation(folder,expected,plan):
    """Use the existing causal resident-baseline AP rule, not the power window."""
    a=folder/'artifacts';origin=p.read(a/'common_boundary.json')['start_ns']
    events=observed.read_lines(a/'progress.jsonl')
    begins=[e['mono_ns'] for e in events if e['kind']=='phase_start' and e['phase']=='resident_baseline']
    ends=[e['mono_ns'] for e in events if e['kind']=='phase_end' and e['phase']=='resident_baseline']
    if len(begins)!=1 or len(ends)!=1:raise ValueError('actual resident baseline boundaries missing')
    first=origin+min(q['offset_ms'] for q in expected['requests'])*1_000_000
    warmups=[e['mono_ns'] for e in events if e['kind']=='warmup_return']
    if not warmups or max(warmups)>begins[0]:raise ValueError('baseline prefix includes warmup execution')
    work=[e['mono_ns'] for e in events if e['kind']=='request_start']
    if not work or min(work)<first:raise ValueError('work began before the registered first arrival')
    readings=observed.read_lines(folder/'thermal.jsonl')
    pre=[dict(lo=(e['before_ns']-origin)/1e9,hi=(e['after_ns']-origin)/1e9,
        t=(e['mono_ns']-origin)/1e9,ap=float(e['AP'])) for e in readings
        if e.get('AP') not in ('',None) and begins[0]<=e['before_ns']<=e['after_ns']<first]
    if not pre:raise ValueError('no measured baseline-to-first-arrival AP prefix')
    target=[e for e in readings if e.get('AP') not in ('',None) and 35<=(e['mono_ns']-origin)/1e9<=180]
    q=[(e['mono_ns']-origin)/1e9 for e in target];ap=[float(e['AP']) for e in target]
    samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2) for e in events if e['kind']=='power_sample']
    pre_power=energy.integrate(samples,origin-20_000_000_000,origin+30_000_000_000,1000)
    if pre_power['full_energy_j'] is None:raise ValueError('same causal -20..30 power input incomplete')
    relative=[dict(r,dispatch_ns=r['dispatch_ns']-origin,lane_available_ns=r['lane_available_ns']-origin) for r in p.read(a/'requests.json')]
    actual=v2.occupancy(relative,0,180_000_000_000)
    planned=v2.occupancy([dict(r,task=r['task_id'],backend=r['recorded_backend'],dispatch_ns=r['pc_dispatch_ns'],
        lane_available_ns=r['pc_lane_available_ns']) for r in expected['requests']],0,180_000_000_000)
    source=p.read(plan['original_model']['path']);candidate=p.read(plan['thermal_model']['path'])['model']
    actual_j=energy.integrate(samples,origin,origin+120_000_000_000,1000)['full_energy_j']
    case=dict(pre=pre,q=q,pre_w=pre_power['mean_power_w'],history=[])
    curves=[];scores={}
    for role,segments in [('A_actual_occupancy_conditional',actual),('B_frozen_pc_plan',planned)]:
        c=dict(case,actual=segments)
        predicted,initial=thermal.predict(c,candidate['thermal'],source)
        baseline_error=None
        try:baseline=v2.prior.thermal.predict(v2.prior.case_input(c,segments),source['ap'])[0]
        except ValueError as ex:
            baseline=[None]*len(q);baseline_error=repr(ex)
        pred_j=case['pre_w']*120+float(v2.prior.base.exposure(segments,0,120)@__import__('numpy').array(
            [source['energy_increment_w'][k] for k in v2.STATES]))
        scores[role]=dict(ap_mae_c=statistics.mean(abs(x-y) for x,y in zip(predicted,ap)),
            original_ap_mae_c=statistics.mean(abs(x-y) for x,y in zip(baseline,ap)) if baseline_error is None else None,
            original_AP_initialization_error=baseline_error,ap_peak_error_c=max(predicted)-max(ap),
            predicted_J120=pred_j,observed_J120=actual_j,energy_error_j=pred_j-actual_j if actual_j is not None else None,
            actual_resident_baseline_start_s=(begins[0]-origin)/1e9,actual_resident_baseline_end_s=(ends[0]-origin)/1e9,
            registered_first_arrival_s=(first-origin)/1e9,initial_AP_first_t=pre[0]['t'],initial_AP_last_t=pre[-1]['t'],
            initial_AP_observed_duration_s=pre[-1]['t']-pre[0]['t'],initial_AP_samples=len(pre),
            initial_input_latest_hi=max(e['hi'] for e in pre),pre_work_or_warmup_included=False,
            AP_initialization_rule='same existing baseline_start <= read bracket < first_arrival35; original55s gate unchanged',
            power_initialization_rule='unchanged -20..30s integral',initial_model_state=initial,
            coefficient_fit_calls=0,initial_state_estimated_from_causal_pre_AP=True,actual_future_schedule_used=role.startswith('A'))
        curves.extend(dict(role=role,elapsed_s=t,observed_ap_c=a,predicted_hybrid_ap_c=x,predicted_original_ap_c=b)
            for t,a,x,b in zip(q,ap,predicted,baseline))
    return scores,curves


def main():
    original_result=original.analyze()
    out=r.PUBLIC;root=r.BASE/'run';plan=p.read(root/'frozen_collection_plan.json')
    previous=r.BASE/'analysis_report_v1';previous.mkdir(exist_ok=False)
    for name in ('summary.json','sessions.csv','model_errors.csv','index.html'):
        if (out/name).exists():shutil.copy2(out/name,previous/name)
    for image in out.glob('figure_*.png'):shutil.copy2(image,previous/image.name)
    shutil.copy2(r.ROOT/'docs/OVERNIGHT_DEVICE_REPLAY_20261011.md',previous/'report.md')
    result=p.read(out/'summary.json');windows=[];skin=[];dispatcher=[];corrected_curves=[];corrected_scores=[]
    expected=p.read(plan['source_schedules']['path'])['policies']
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}";a=folder/'artifacts'
        if not (folder/'validated.json').exists():continue
        try:
            scores,curves=corrected_cost_validation(folder,expected[e['arm']],plan)
            result['sessions'][e['index']]['cost_validation_v2']=scores
            corrected_curves.extend(dict(index=e['index'],**x) for x in curves)
            corrected_scores.extend(dict(index=e['index'],source_policy=e['source_policy'],role=role,
                **{k:v for k,v in value.items() if k!='initial_model_state'}) for role,value in scores.items())
        except Exception as ex:
            result['sessions'][e['index']]['cost_validation_v2_error']=repr(ex)
        boundary=p.read(a/'common_boundary.json');origin=boundary['start_ns']
        readings=observed.read_lines(folder/'thermal.jsonl')
        events=observed.read_lines(a/'progress.jsonl')
        durations=sorted((x['decision_end_ns']-x['decision_start_ns'])/1e6 for x in events if x['kind']=='decision')
        if durations and any(x<0 for x in durations):raise ValueError('negative decision bracket')
        dispatcher.append(dict(index=e['index'],measured_decision_brackets=len(durations),
            decision_total_ms=sum(durations) if durations else None,
            decision_p50_ms=statistics.median(durations) if durations else None,
            decision_p95_ms=durations[math.ceil(.95*len(durations))-1] if durations else None,
            scope='fixed-plan selector elapsed bracket only; no Rolling forecaster/PPO inference or controller energy measured'))
        phase=[x for x in events if x['kind'] in ('phase_start','phase_end') and x['phase']=='resident_cooling']
        bounds={x['kind']:(x['mono_ns']-origin)/1e9 for x in phase}
        for channel in ('AP','SKIN'):
            all_samples=[dict(t=(x['mono_ns']-origin)/1e9,value=float(x[channel]),
                uncertainty_s=x['sampling_uncertainty_ns']/1e9) for x in readings if x.get(channel) not in ('',None)]
            for label,start,end in [('common_0_120',0,120),('policy_requested_35_180',35,180)]:
                selected=[x for x in all_samples if start<=x['t']<=end]
                first=selected[0]['t'] if selected else None;last=selected[-1]['t'] if selected else None
                gaps=[b['t']-a['t'] for a,b in zip(selected,selected[1:])]
                windows.append(dict(index=e['index'],source_policy=e['source_policy'],channel=channel,
                    requested_window=label,requested_start_s=start,requested_end_s=end,
                    measured_samples=len(selected),first_measured_s=first,last_measured_s=last,
                    left_edge_without_sample_s=first-start if first is not None else None,
                    right_edge_without_sample_s=end-last if last is not None else None,
                    maximum_between_sample_gap_s=max(gaps) if gaps else None,
                    maximum_timestamp_uncertainty_s=max(x['uncertainty_s'] for x in selected) if selected else None,
                    maximum_observed_sample_c=max(x['value'] for x in selected) if selected else None,
                    exact_continuous_window_peak_c=None,
                    app_cooling_phase_start_s=bounds.get('phase_start'),app_cooling_phase_end_s=bounds.get('phase_end'),
                    full_180s_actual_temperature_imputed=False,
                    meaning='finite actual channel samples only; no edge extrapolation or continuous peak guarantee'))
                if channel=='SKIN' and label=='policy_requested_35_180':
                    skin.extend(dict(index=e['index'],elapsed_s=x['t'],HAL_SKIN_c=x['value']) for x in selected)
    original.csv_write(out/'temperature_observation_windows.csv',windows)
    original.csv_write(out/'HAL_SKIN_curve.csv',skin)
    original.csv_write(out/'frozen_dispatcher_timing.csv',dispatcher)
    original.csv_write(out/'model_errors_v2.csv',corrected_scores)
    original.csv_write(out/'model_AP_curve_v2.csv',corrected_curves)
    physical_requests=[]
    import csv
    with (out/'requests.csv').open(encoding='utf-8-sig',newline='') as f:
        for x in csv.DictReader(f):
            row={k:v for k,v in x.items()}
            for k in ('index','ordinal'):row[k]=int(row[k])
            for k in ('dispatch_ms','lane_available_ms','dispatch_delay_from_plan_ms','response_minus_pc_ms'):row[k]=float(row[k])
            physical_requests.append(row)
    original.figures(result['sessions'],physical_requests,observed_csv(out/'AP_curve.csv'),corrected_curves)
    aggregates={}
    for metric in dict.fromkeys(x['metric'] for x in result['pairs']):
        seq=[x['candidate_minus_band'] for x in result['pairs'] if x['metric']==metric and x['candidate_minus_band'] is not None]
        aggregates[metric]=dict(complete_pairs=len(seq),mean=statistics.mean(seq) if len(seq)==2 else None,
            minimum=min(seq) if seq else None,maximum=max(seq) if seq else None,
            confidence_interval=None,statistical_effect_or_equivalence=None)
    notes=dict(report_version=2,original_readout_preserved_private=True,
        frozen_report_source_changed=False,criteria_policy_seed_trace_model_changed=False,
        J_window='same common0..120 seconds for all four arms',
        physical_AP_common_peak='actual samples within0..120; not the PC policy35..180 criterion',
        physical_AP_policy_window='actual samples35..180 only; missing edges reported and not imputed',
        model_AP_errors='A and B evaluated at identical actual AP sample query times35..180, not an invented180s endpoint',
        HAL_SKIN='reported sensor-name channel; neither highest measured phone surface nor a supported thermal model',
        original_summary_sha256=p.digest(previous/'summary.json'),
        original_model_readout_error_preserved='ValueError(pre-load idle too short): AP was mistakenly cut to the 50s power prefix',
        AP_prefix_correction_scope='postprocess only; existing idle-prefix construction; no native rerun or55s gate relaxation',
        coefficient_fit_calls=0,initial_state_estimation='per-session pre-issue AP; not coefficient fitting',
        windows_sha256=p.digest(out/'temperature_observation_windows.csv'),
        source_sha256=p.digest(__file__),new_fit_calls=0)
    (out/'analysis_window_note.json').write_bytes(p.canonical(notes))
    result['analysis_window_note']=notes;result['temperature_observation_windows']=windows
    result['descriptive_order_pair_summary']=aggregates;result['frozen_dispatcher_timing']=dispatcher
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    for x in windows:
        if x['channel']=='AP' and x['requested_window']=='policy_requested_35_180':
            rows.append(f"<tr><td>{x['index']}</td><td>{x['first_measured_s']:.3f}</td><td>{x['last_measured_s']:.3f}</td><td>{x['right_edge_without_sample_s']:.3f}</td><td>{x['maximum_observed_sample_c']:.3f}</td></tr>")
    paragraph='''<h2>온도 관측창을 구분해 읽기</h2>
<p>위 성적표 AP 최고는 공통0..120초에서 읽은 표본최고입니다. PC 정책판정은35..180초이므로 그 두 최고를 같은 기준으로 섞지 않습니다. 아래는 실제 확보한35..180초 AP 표본이며 끝의 미관측 부분을 실측으로 채우지 않았습니다. A/B 모형오차는 같은 실제 query시각에서 계산했습니다. J는 네 세션 모두 같은120초입니다.</p>
<table><tr><th>순서</th><th>첫 AP표본 s</th><th>마지막 AP표본 s</th><th>180초까지 표본없는 edge s</th><th>관측 표본최고 °C</th></tr>'''+''.join(rows)+'''</table>
<p><a href="temperature_observation_windows.csv">AP/SKIN 전체 관측창·gap·clock 불확실성</a> · <a href="HAL_SKIN_curve.csv">HAL SKIN 보조채널</a> · <a href="analysis_window_note.json">보고 개정과 원 판독 해시</a></p>
<p><a href="model_errors_v2.csv">보완한 A/B 모형오차</a> · <a href="model_AP_curve_v2.csv">같은 실제 query시각의 예측</a>. 원 판독의50초 AP입력 오류를 보존한 채, 실제 resident_baseline 시작부터 첫 도착35초 전 read_bracket만 사용했습니다. 원 AP의55초 gate는 그대로이며 계수 적합0, 초기 R/H 추정은 별도입니다.</p>
<p>HAL SKIN은 기기가 보고한 센서명 채널입니다. 최고 표면온도나 시뮬레이터의 지원 열 상태로 승격하지 않습니다.</p>'''
    pair_rows=''.join(f"<tr><td>{metric}</td><td>{v['complete_pairs']}</td><td>{v['mean']}</td><td>{v['minimum']}</td><td>{v['maximum']}</td></tr>" for metric,v in aggregates.items())
    paragraph+='''<h2>두 순서 반전 쌍의 기술통계</h2><p>평균과 범위는 관측한 두 쌍의 값일 뿐입니다. 같은 초기 AP가 같은 열 이력·시스템 활동·SOC를 보장하지 않으며, 효과·동등성·무효과를 통계적으로 증명하지 않습니다.</p><table><tr><th>리스트−Band 지표</th><th>쌍 수</th><th>평균</th><th>최소</th><th>최대</th></tr>'''+pair_rows+'''</table><p><a href="frozen_dispatcher_timing.csv">동결 replay 선택기의 판단 bracket</a>은 온라인 롤링/PPO 계산 비용이나 제어 에너지 측정이 아닙니다.</p>'''
    page=(out/'index.html').read_text(encoding='utf-8').replace('</html>',paragraph+'</html>')
    (out/'index.html').write_text(page,encoding='utf-8')
    lines=[]
    for x in windows:
        if x['channel']=='AP' and x['requested_window']=='policy_requested_35_180':
            lines.append(f"| {x['index']} | {x['first_measured_s']:.3f} | {x['last_measured_s']:.3f} | {x['right_edge_without_sample_s']:.3f} | {x['maximum_observed_sample_c']:.3f} |")
    doc=r.ROOT/'docs/OVERNIGHT_DEVICE_REPLAY_20261011.md'
    body=doc.read_text(encoding='utf-8')+'''\n## 보고 v2: 관측창을 구분한 AP·SKIN\n\n앞 성적표 AP 최고는 실제0..120초 표본최고이며, PC 정책판정35..180초와 다른 창이다. 아래는 실제확보된35..180초 AP표본범위다. 표본없는180초끝부분을실측으로채우지않았고연속최고값은계산불가다. A/B오차는동일한실제query시각만비교한다. J는공통120초를그대로유지한다.\n\n| 순서 | 첫 AP표본 초 | 마지막 AP표본 초 | 180초까지 표본없는 edge 초 | 관측 AP표본최고 °C |\n|---:|---:|---:|---:|---:|\n'''+ '\n'.join(lines)+'''\n\n[관측창CSV](results/overnight_device_20261011/temperature_observation_windows.csv)에AP/SKIN별시작/끝/gap/clock오차/실제cooling끝을공개했다. HAL SKIN은보고된센서명채널이고최고표면온도또는지원열모형으로승격하지않는다. [별도source prerequisite](results/overnight_device_20261011/source_bundle/README.md)와manifest/patch를사용하면원user WIP를stage하지않고필요code를별도checkout에서검증할수있다. 원source와frozen판정은변경하지않았다.\n'''
    body+='\n## 두 순서 반전 쌍의 평균과 범위\n\n| 지표(리스트−Band) | 완료 쌍 | 평균 | 최소 | 최대 |\n|---|---:|---:|---:|---:|\n'
    body+='\n'.join(f"| {metric} | {v['complete_pairs']} | {v['mean']} | {v['minimum']} | {v['maximum']} |" for metric,v in aggregates.items())
    body+='\n\n이는 두 관측 쌍의 기술통계다. 효과·동등성·무효과의 통계적 증명이 아니다. 동일 초기 AP라도 열 이력·시스템 활동·SOC와 전체 에너지 변동이 같다는 보장은 없다. 실제 업무 완료·출력 품질·실제 AVAILABLE 준수는 새 검증 근거로 남기지만, 온라인 롤링/PPO의 기기 판단 비용·제어 에너지·전체 조건 우위는 미검증이다.\n'
    body+='\n## 보고 초기 입력 오류와 보완\n\n원 v1은 AP도 전력의−20..30초창으로잘라 원 AP초기화의55초 gate를통과하지못했다. 원 source와실패를private analysis_report_v1 및최종summary의cost_validation_error에보존했다. 보고v2는기존resident 분석과같이실제baseline 시작≤read_bracket<첫도착35초의전체idle AP를사용하고, warmup 완료≤baseline시작·최초실제work≥35초를검사했다. 전력은그대로−20..30초다. 새계수fit0이며, 측정된초기AP에서R/H를추정하는초기화와계수보정을구분했다. 기존55초검사를통과하지못하면원AP오차는null이며gate를낮추지않는다. 이는사후판독수정일뿐새기기실행0·정책/계수/seed/판정불변이다. [보완오차CSV](results/overnight_device_20261011/model_errors_v2.csv)에시작/끝/표본수·실제baseline·도착시각·지원여부를전량기록했다.\n'
    doc.write_text(body,encoding='utf-8')
    # Keep the historical storage block, then explicitly mark the new measurement.
    (out/'README.md').write_text('''# A24 동결 일정 전향 실측\n\n호스트 저장공간 부족을 NTFS 무손실 압축으로 해결한 뒤, 같은 미소비 계획에서 ABBA4를 실행했습니다. 실제 값은 [화면](index.html)·[요약](summary.json)·[관측창](temperature_observation_windows.csv)을 보세요. 온라인 스케줄러 직접 실행이나 실제 절감 확정은 아닙니다.\n\n초기실측0회/저장차단은 historical `preparation_verification.json`에 보존했고, `storage_resume_receipt.json`은 내용변경 없는 복구를 기록합니다. [source prerequisite](source_bundle/README.md)는 사용자 WIP를 원위치에 보존한 공유 재현 경로입니다.\n''',encoding='utf-8')
    print(json.dumps(dict(original_result,report_version=2,temperature_window_rows=len(windows),skin_rows=len(skin),
        corrected_cost_assessments=len(corrected_scores)),ensure_ascii=False,indent=2))


def observed_csv(file):
    import csv
    with Path(file).open(encoding='utf-8-sig',newline='') as f:
        return [dict(index=int(x['index']),elapsed_s=float(x['elapsed_s']),ap_c=float(x['ap_c'])) for x in csv.DictReader(f)]


def finalize():
    """Presentation repair only; metric CSV bytes and registered sources stay put."""
    out=r.PUBLIC;result=p.read(out/'summary.json')
    before={x.name:p.digest(x) for x in out.glob('*.csv')}
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    with (out/'requests.csv').open(encoding='utf-8-sig',newline='') as f:requests=list(csv.DictReader(f))
    colors=['#2c78b5','#ec882e','#ec882e','#2c78b5']
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for i in range(4):
        seq=[x for x in requests if int(x['index'])==i]
        axes[0].plot([int(x['ordinal']) for x in seq],[float(x['dispatch_delay_from_plan_ms']) for x in seq],
            color=colors[i],ls='-' if i<2 else '--',label=str(i))
        axes[1].plot([int(x['ordinal']) for x in seq],[float(x['response_minus_pc_ms']) for x in seq],
            color=colors[i],ls='-' if i<2 else '--',label=str(i))
    axes[0].set_title('실제 dispatch - 계획 dispatch (ms)');axes[1].set_title('실제 응답시간 - PC 응답시간 (ms)')
    for ax in axes:ax.set_xlabel('예정 요청 번호');ax.axhline(0,color='#999',lw=.7);ax.legend()
    fig.tight_layout();fig.savefig(out/'figure_3.png',dpi=160);plt.close(fig)
    model_rows=[]
    for s in result['sessions']:
        for role,v in s['cost_validation_v2'].items():
            model_rows.append(f"<tr><td>{s['index']}</td><td>{'A 실제점유 조건부' if role.startswith('A') else 'B 동결 PC계획'}</td><td>{v['ap_mae_c']:.6f}</td><td>{v['original_ap_mae_c']:.6f}</td><td>{v['energy_error_j']:.6f}</td><td>{v['initial_AP_observed_duration_s']:.3f}</td></tr>")
    block='''<h2>같은 실제 표본시각의 모형 예측 오차</h2><p>계수 적합0, 실제 idle AP에서의 초기 R/H 추정만 사용했습니다. A는 실제 미래점유를 알고 하는 조건부 검증이며, B는 실험의 예정 trace를 재생한 동결PC계획입니다. 온라인 정책의 실제 판단 비용·효과를 측정한 결과가 아닙니다.</p><table><tr><th>순서</th><th>예측 범위</th><th>v3 AP MAE °C</th><th>원 AP MAE °C</th><th>J120 예측-실측 J</th><th>실제 idle 초기입력 초</th></tr>'''+''.join(model_rows)+'''</table><img src="figure_4.png" alt="같은 실제 query시각에서 AP모형과 실측 비교"><p>공유값 검산: <code>python -B -X utf8 -m tools.d1_overnight_device_verify</code>. 이는 읽기 전용이며 기기·학습·새환경·새clock을 만들지 않습니다.</p>'''
    page=(out/'index.html').read_text(encoding='utf-8').replace('href="model_errors.csv"','href="model_errors_v2.csv"')
    (out/'index.html').write_text(page.replace('</html>',block+'</html>'),encoding='utf-8')
    after={x.name:p.digest(x) for x in out.glob('*.csv')}
    if before!=after:raise ValueError('presentation repair changed a numeric CSV')
    note=p.read(out/'analysis_window_note.json');note['prior_analysis_source_sha256']=note['source_sha256']
    note['source_sha256']=p.digest(__file__);note['presentation_repair_numeric_CSV_unchanged']=True
    note['presentation_repairs']='missing old-error CSV link redirected to v2; figure4 shown; unsupported minus glyph replaced with ASCII'
    (out/'analysis_window_note.json').write_bytes(p.canonical(note));result['analysis_window_note']=note
    result['ADB_accounting']=dict(collection_clock_after_claim_commands=1748,
        separately_journaled_preparation_read_only_commands=6,
        initial_interactive_read_only_commands_in_tool_history_not_collector_ledger=True,
        collection_count_is_not_whole_conversation_ADB_total=True,
        scope='1748 includes installation/session gates/poll/recovery/cleanup after immutable claim only')
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    cleanup=[dict(index=s['index'],path=f"output/overnight_device_20261011_v1/run/{s['index']:02d}_"
        +p.read(r.BASE/'run/frozen_collection_plan.json')['entries'][s['index']]['session_id']+'/host_cleanup.json') for s in result['sessions']]
    verification=dict(status='PASS_completed_ABBA4_and_public_readout',requests=384,completed=384,
        urgent_failures=0,normal_failures=0,warmup=32,explicit_inference=416,physical_sessions=4,installs=1,
        coefficient_fit_calls=0,online_policy_runs=0,native_execution_errors=0,
        postprocess_v1_error='AP initializer55s gate rejected wrong50s window; originalerror/source preserved; correctedv2 uses actual idleprefix',
        original_user_Android_changes=0,registered_native_sources_unchanged=True,owner_lock=False,
        collection_ADB_commands=1748,preparation_read_only_journal_commands=6,
        extra_initial_read_only_commands='preserved in tool history; not included in1748; do not treat1748 as conversation total',
        final_receipt_sha256=result['terminal_receipt_sha256'],metric_csv_sha256=before,
        source_bundle_manifest_sha256=p.digest(out/'source_bundle/manifest.json'),
        source_integrity_closed_after4=True,additional_automatic_measurements=0,cleanup_paths=cleanup,
        physical_effect_or_equivalence_proven=False,experiment_ready=False)
    (out/'completion_verification.json').write_bytes(p.canonical(verification))
    doc=r.ROOT/'docs/OVERNIGHT_DEVICE_REPLAY_20261011.md'
    doc.write_text(doc.read_text(encoding='utf-8')+'''\n## 실행 장부와 재현 검산\n\nADB1748은 불변claim 후 수집기의 설치·session gate·poll·회수·cleanup 장부다. 별도사전읽기전용6명령은 device_identity_observation.json에보존했고, 최초대화의수동연결·battery·screen조회는tool history에별도로남는다. 따라서1748을대화전체명령수라고표시하지않는다. 설치1·실제4세션·본384＋warmup32=416·계수fit0·업무실패0이며4회등록은닫혔다. 새실측자동시작0이다.\n\n공유결과의읽기전용재현검산: `python -B -X utf8 -m tools.d1_overnight_device_verify`. private raw가없으면공유CSV/patch/SHA/판정계약검산이라고표시하고, raw가있으면추가원본hash를검사한다. ADB·기기·학습·새환경·clock생성0이다. 원자료생성보고서는write-once이므로완료폴더에다시쓰기위해재실행하지않는다.\n''',encoding='utf-8')
    print(json.dumps({k:v for k,v in verification.items() if k not in ('metric_csv_sha256','cleanup_paths')},ensure_ascii=False,indent=2))


def display_rounding():
    """Round presentation only; do not change recorded metric precision."""
    import re
    out=r.PUBLIC;result=p.read(out/'summary.json')
    before={x.name:p.digest(x) for x in out.glob('*.csv')}
    rows=[]
    for s in result['sessions']:
        name='Band 대응' if s['index'] in (0,3) else '리스트 선택'
        rows.append(f"<tr><td>{s['index']}</td><td title=\"{s['source_policy']}\">{name}</td><td>{s['completed']}/{s['planned']}</td><td>{s['urgent_failures']}</td><td>{s['normal_failures']}</td><td>{s['urgent_p95_ms']:.3f}</td><td>{s['energy_j_conditional_mA']:.3f}</td><td>{s['ap_peak_c']:.1f}</td><td>{s['initial_ap_c']:.1f}</td></tr>")
    table='<table><tr><th>순서</th><th>PC 원 정책</th><th>완료/예정</th><th>긴급 기한 위반</th><th>일반 기한 위반</th><th>긴급 P95 ms</th><th>조건부 J</th><th>최고 AP °C</th><th>초기 AP °C</th></tr>'+''.join(rows)+'</table>'
    page=(out/'index.html').read_text(encoding='utf-8')
    page,count=re.subn(r'<table>.*?</table>',lambda _:table,page,count=1,flags=re.S)
    if count!=1:raise ValueError('main result table missing')
    (out/'index.html').write_text(page,encoding='utf-8')
    after={x.name:p.digest(x) for x in out.glob('*.csv')}
    if before!=after:raise ValueError('display rounding changed numeric CSV')
    note=p.read(out/'analysis_window_note.json');note['display_rounding']='main HTML J/P95 3 decimals, physical AP1 decimal; CSV raw values unchanged; failure headers identify deadline misses'
    note['source_sha256']=p.digest(__file__);(out/'analysis_window_note.json').write_bytes(p.canonical(note))
    result['analysis_window_note']=note;(out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    qa=p.read(out/'browser_verification.json');qa['index_sha256']=p.digest(out/'index.html')
    qa['prior_screenshot_source_is_before_display_rounding']=True
    qa['display_rounding_numeric_CSV_unchanged']=True
    (out/'browser_verification.json').write_bytes(p.canonical(qa))
    print(json.dumps(dict(status='PASS_display_rounding_only',metric_CSV_unchanged=True,index_sha256=p.digest(out/'index.html'),new_native_or_device_runs=0),indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['analyze','finalize','display'],nargs='?',default='analyze')
    a=parser.parse_args();main() if a.action=='analyze' else finalize() if a.action=='finalize' else display_rounding()
