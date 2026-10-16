"""Offline frozen-plan readout. New phone outcomes are never used for fitting."""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path
import statistics

from tools import d1_overnight_device_replay as replay
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_analysis as observed
from tools import d1_energy_thermal as energy
from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v3_thermal as thermal


def csv_write(file,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with Path(file).open('x',encoding='utf-8-sig',newline='') as f:
        out=csv.DictWriter(f,fieldnames=fields);out.writeheader();out.writerows(rows)


def cost_validation(folder,expected,plan):
    a=folder/'artifacts';bound=p.read(a/'common_boundary.json');origin=bound['start_ns']
    readings=observed.read_lines(folder/'thermal.jsonl')
    pre=[]
    for e in readings:
        lo=(e['before_ns']-origin)/1e9;hi=(e['after_ns']-origin)/1e9
        if -20<=lo<=hi<30 and e['AP']!='':
            pre.append(dict(lo=lo,hi=hi,t=(lo+hi)/2,ap=float(e['AP'])))
    target=[e for e in readings if 35<=(e['mono_ns']-origin)/1e9<=180 and e['AP']!='']
    q=[(e['mono_ns']-origin)/1e9 for e in target];actual_ap=[float(e['AP']) for e in target]
    events=observed.read_lines(a/'progress.jsonl');samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
        for e in events if e['kind']=='power_sample']
    pre_power=energy.integrate(samples,origin-20_000_000_000,origin+30_000_000_000,1000)
    if pre_power['full_energy_j'] is None:raise ValueError('causal pre power window incomplete')
    actual_rows=p.read(a/'requests.json')
    relative=[dict(r,dispatch_ns=r['dispatch_ns']-origin,lane_available_ns=r['lane_available_ns']-origin) for r in actual_rows]
    future_a=v2.occupancy(relative,0,180_000_000_000)
    future_b=v2.occupancy([dict(q,task=q['task_id'],backend=q['recorded_backend'],dispatch_ns=q['pc_dispatch_ns'],
        lane_available_ns=q['pc_lane_available_ns']) for q in expected['requests']],0,180_000_000_000)
    original=p.read(plan['original_model']['path']);candidate=p.read(plan['thermal_model']['path'])['model']
    observed_j=energy.integrate(samples,origin,origin+120_000_000_000,1000)['full_energy_j']
    case=dict(pre=pre,q=q,pre_w=pre_power['mean_power_w'],history=[])
    results={};curves=[]
    for role,segments in [('A_actual_occupancy_conditional',future_a),('B_frozen_pc_plan',future_b)]:
        c=dict(case,actual=segments)
        values,initial=thermal.predict(c,candidate['thermal'],original)
        original_values=v2.prior.thermal.predict(v2.prior.case_input(c,segments),original['ap'])[0]
        pred_j=case['pre_w']*120+float(v2.prior.base.exposure(segments,0,120)@__import__('numpy').array(
            [original['energy_increment_w'][k] for k in v2.STATES]))
        results[role]=dict(ap_mae_c=statistics.mean(abs(x-y) for x,y in zip(values,actual_ap)),
            original_ap_mae_c=statistics.mean(abs(x-y) for x,y in zip(original_values,actual_ap)),
            ap_peak_error_c=max(values)-max(actual_ap),predicted_J120=pred_j,
            observed_J120=observed_j,energy_error_j=pred_j-observed_j if observed_j is not None else None,
            initial_input_latest_hi=max(e['hi'] for e in pre),initial_model_state=initial,
            new_fit_calls=0,actual_future_schedule_used=(role.startswith('A')))
        curves.extend(dict(role=role,elapsed_s=t,observed_ap_c=a,predicted_hybrid_ap_c=v,predicted_original_ap_c=o)
            for t,a,v,o in zip(q,actual_ap,values,original_values))
    return results,curves


def analyze():
    root=replay.BASE/'run';out=replay.PUBLIC
    plan=p.read(root/'frozen_collection_plan.json');terminal=p.read(root/'FINAL_RECEIPT.json')
    if (out/'summary.json').exists():raise ValueError('write-once readout; do not overwrite')
    bundle=p.read(plan['source_schedules']['path']);expected=bundle['policies']
    session=[];request=[];costcurves=[];series=[];costerrors=[]
    raw_hashes={};validation_predictions=0
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}";row=dict(index=e['index'],arm=e['arm'],source_policy=e['source_policy'],
            planned=96,status='not_validated',completed=None,common_unfinished=96,energy_j_conditional_mA=None,
            ap_peak_c=None,urgent_failures=None,normal_failures=None,urgent_p95_ms=None)
        if (folder/'validated.json').exists():
            row.update(p.read(folder/'validated.json'))
            try:
                costs,curves=cost_validation(folder,expected[e['arm']],plan);validation_predictions+=2
                costcurves.extend(dict(index=e['index'],**x) for x in curves)
                row['cost_validation']=costs
                costerrors.extend(dict(index=e['index'],source_policy=e['source_policy'],role=role,
                    **{k:v for k,v in value.items() if k!='initial_model_state'}) for role,value in costs.items())
            except Exception as ex:
                row['cost_validation_error']=repr(ex)
            a=folder/'artifacts';origin=p.read(a/'common_boundary.json')['start_ns']
            lookup={q['source_request_id']:q for q in expected[e['arm']]['requests']}
            for r in p.read(a/'requests.json'):
                q=lookup[r['source_request_id']]
                z=dict(index=e['index'],arm=e['arm'],ordinal=r['ordinal'],task_id=r['task_id'],priority=r['priority'],
                    backend=r['selected_backend'],terminal_status=r['terminal_status'],
                    planned_arrival_ms=q['offset_ms'],deadline_ms=q['deadline_ms'])
                for k in ('actual_arrival_ns','dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns',
                    'worker_release_ns','lane_available_ns'):
                    z[k.removesuffix('_ns')+'_ms']=(r[k]-origin)/1e6
                    if 'pc_'+k in q:z['pc_'+k.removesuffix('_ns')+'_ms']=q['pc_'+k]/1e6
                response=r['output_ready_ns'] if r['priority']=='urgent' else r['persist_complete_ns']
                z.update(response_ms=(response-r['scheduled_arrival_ns'])/1e6,
                    response_minus_pc_ms=(response-r['scheduled_arrival_ns']-q['pc_response_duration_ns'])/1e6,
                    actual_late=response>r['deadline_ns'],pc_late=q['pc_late'],
                    dispatch_delay_from_plan_ms=(r['dispatch_ns']-origin-q['release_offset_ns'])/1e6)
                request.append(z)
            for t in observed.read_lines(folder/'thermal.jsonl'):
                elapsed=(t['mono_ns']-origin)/1e9
                if 0<=elapsed<=180 and t['AP']!='':series.append(dict(index=e['index'],elapsed_s=elapsed,ap_c=float(t['AP'])))
            for file in [folder/'validated.json',folder/'thermal.jsonl',*a.iterdir()]:
                if file.is_file():raw_hashes[str(file.relative_to(root))]=p.digest(file)
        session.append(row)
    pairs=[]
    metrics=('energy_j_conditional_mA','ap_peak_c','urgent_p95_ms','normal_mean_response_ms','urgent_failures','normal_failures')
    for band,candidate in ((0,1),(3,2)):
        aa,bb=session[band],session[candidate]
        matched=aa.get('initial_ap_c') is not None and bb.get('initial_ap_c') is not None and abs(bb['initial_ap_c']-aa['initial_ap_c'])<=.5
        for metric in metrics:
            av,bv=aa.get(metric),bb.get(metric)
            pairs.append(dict(band_index=band,candidate_index=candidate,initial_ap_matched=matched,metric=metric,
                candidate_minus_band=bv-av if av is not None and bv is not None else None,
                meaning='two order-reversed descriptive pairs; no significance or online superiority claim'))
    verdict=dict(online_policy_superiority=None,physical_saving_established=False,measurement_repeat_per_arm=2,
        new_data_fit_calls=0,model_validation_cost_predictions=validation_predictions,
        criteria='same full input and measured responses; actual SLA first; AP initial covariate and energy unit limits retained',
        strict_support=False,experiment_ready=False)
    result=dict(status=terminal['status'],sessions=session,pairs=pairs,verdict=verdict,
        terminal_receipt_sha256=p.digest(root/'FINAL_RECEIPT.json'),plan_sha256=p.digest(root/'frozen_collection_plan.json'),
        raw_sha256=raw_hashes,additional_inference_consumption=terminal.get('explicit_inference'),
        physical_sessions=terminal.get('sessions',terminal.get('launch_attempts')),installs=(terminal.get('installation')or{}).get('install_attempts'),
        current_unit='whole-device likely mA interpretation; absolute energy accuracy uncertified',
        thermal_channel='AP, not highest surface temperature',
        prediction_scope='A actual occupancy conditional and B frozen planned occupancy; pre AP/power only for initial state; new fit=0')
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    csv_write(out/'sessions.csv',[{k:v for k,v in r.items() if k not in ('cost_validation','cost_validation_error')} for r in session])
    csv_write(out/'pairs.csv',pairs);csv_write(out/'requests.csv',request);csv_write(out/'model_errors.csv',costerrors)
    csv_write(out/'AP_curve.csv',series);csv_write(out/'model_AP_curve.csv',costcurves)
    figures(session,request,series,costcurves)
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in
        ('index','source_policy','completed','urgent_failures','normal_failures','urgent_p95_ms','energy_j_conditional_mA','ap_peak_c','initial_ap_c'))+'</tr>' for r in session)
    names=('실측 실행 시간표','실측 AP 경로','서비스와 비용','원 계획 대비 응답 오차','조건부 모형 AP 검증')
    images=''.join(f'<h2>{name}</h2><img src="figure_{i}.png" alt="{name}">' for i,name in enumerate(names) if (out/f'figure_{i}.png').exists())
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>동결 일정 A24 실측</title>'
        '<style>body{font-family:Arial,Malgun Gothic,sans-serif;margin:32px;max-width:1250px;color:#263043}table{border-collapse:collapse;font-size:14px}td,th{padding:8px;border:1px solid #ddd}img{max-width:100%}.note{background:#fff2d9;padding:16px}a{color:#126bbb}</style>'
        '<h1>A24 동결 일정 실측 · Band 대응 vs 리스트 선택</h1><div class="note">온라인 스케줄러 직접 실행이 아닙니다. 사전 고정한 PC 일정의 CPU/GPU 배정·출시 시점을 재생하고 실제 AVAILABLE까지 기다렸습니다. 반복은 정책별 2회이며 실제 절감·제품 우월성은 확정하지 않습니다. 에너지는 기기 전체 전류의 mA 해석에 따른 조건부 J, 온도는 AP 채널입니다.</div>'
        '<p><a href="sessions.csv">전체 세션</a> · <a href="requests.csv">384 예정 요청과 실제 응답</a> · <a href="pairs.csv">두 순서 반전 쌍</a> · <a href="model_errors.csv">A/B 모형 오차</a> · <a href="summary.json">근거·누락·해시</a></p>'
        '<table><tr><th>순서</th><th>PC 원 정책</th><th>완료</th><th>긴급 실패</th><th>일반 실패</th><th>긴급 P95 ms</th><th>조건부 J</th><th>최고 AP °C</th><th>초기 AP °C</th></tr>'+rows+'</table>'+images+'</html>',encoding='utf-8')
    report(session,pairs,terminal,result)
    return dict(status=result['status'],sessions=len(session),completed=sum(r.get('completed') or 0 for r in session),
        cost_validation_predictions=validation_predictions,output=str(out))


def figures(session,request,series,costcurves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    colors=['#2c78b5','#ec882e','#ec882e','#2c78b5'];out=replay.PUBLIC
    fig,axes=plt.subplots(4,1,figsize=(12,8),sharex=True)
    for i,ax in enumerate(axes):
        for r in request:
            if r['index']!=i:continue
            y=0 if r['backend']=='CPU' else 1
            color='#589a75' if r['task_id']=='detection' else '#b685ba'
            ax.broken_barh([(r['dispatch_ms']/1000,(r['lane_available_ms']-r['dispatch_ms'])/1000)],(y-.3,.6),facecolors=color)
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(f'{i}: '+('Band 대응 일정' if i in (0,3) else '리스트 선택 일정'))
    axes[-1].set_xlabel('공통 관측창 경과 시간 (초)');axes[-1].set_xlim(34,72)
    fig.tight_layout();fig.savefig(out/'figure_0.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,5))
    for i in range(4):
        seq=[r for r in series if r['index']==i]
        ax.plot([r['elapsed_s'] for r in seq],[r['ap_c'] for r in seq],color=colors[i],ls='-' if i<2 else '--',label=f'{i} '+('Band 대응' if i in (0,3) else '리스트 선택'))
    ax.set(xlabel='공통 시작 후 시간 (초)',ylabel='AP 온도 (°C)',title='실측 AP · 초기 상태 차이와 경로 전체 공개');ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'figure_1.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,key,title in zip(axes,('urgent_p95_ms','energy_j_conditional_mA','ap_peak_c'),('긴급 응답 P95 (ms)','공통 120초 기기 에너지 (조건부 J)','같은 AP 채널 최고값 (°C)')):
        ax.bar(range(4),[r[key] if r.get(key) is not None else float('nan') for r in session],color=colors);ax.set_title(title);ax.set_xticks(range(4),['Band 0','선택 1','선택 2','Band 3']);ax.grid(axis='y',alpha=.2)
        if any(r.get(key) is None for r in session):ax.text(.5,.5,'결측은 막대 표시하지 않음',transform=ax.transAxes)
    fig.tight_layout();fig.savefig(out/'figure_2.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for i in range(4):
        seq=[r for r in request if r['index']==i]
        axes[0].plot([r['ordinal'] for r in seq],[r['dispatch_delay_from_plan_ms'] for r in seq],color=colors[i],ls='-' if i<2 else '--',label=str(i))
        axes[1].plot([r['ordinal'] for r in seq],[r['response_minus_pc_ms'] for r in seq],color=colors[i],ls='-' if i<2 else '--',label=str(i))
    axes[0].set_title('실제 dispatch − 계획 dispatch (ms)');axes[1].set_title('실제 응답시간 − PC 응답시간 (ms)')
    for ax in axes:ax.set_xlabel('예정 요청 번호');ax.axhline(0,color='#999',lw=.7);ax.legend()
    fig.tight_layout();fig.savefig(out/'figure_3.png',dpi=160);plt.close(fig)
    if costcurves:
        fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
        for i,ax in enumerate(axes.flat):
            for role,label in [('A_actual_occupancy_conditional','실제 점유 조건부 A'),('B_frozen_pc_plan','고정 PC 계획 B')]:
                seq=[r for r in costcurves if r['index']==i and r['role']==role]
                if seq:ax.plot([r['elapsed_s'] for r in seq],[r['predicted_hybrid_ap_c'] for r in seq],label=label)
            seq=[r for r in costcurves if r['index']==i and r['role'].startswith('A')]
            if seq:ax.plot([r['elapsed_s'] for r in seq],[r['observed_ap_c'] for r in seq],label='실측',color='#111')
            ax.set(title=f'{i} AP 검증 · 새 fit 0',ylabel='AP °C');ax.legend(fontsize=8)
        fig.tight_layout();fig.savefig(out/'figure_4.png',dpi=160);plt.close(fig)


def report(session,pairs,terminal,result):
    rows='\n'.join(f"| {r['index']} | {'Band 대응' if r['index'] in (0,3) else '리스트 선택'} | {r.get('completed')} /96 | {r.get('urgent_failures')} / {r.get('normal_failures')} | {r.get('urgent_p95_ms')} | {r.get('energy_j_conditional_mA')} | {r.get('ap_peak_c')} | {r.get('initial_ap_c')} |" for r in session)
    text=f'''# A24 동결 일정 전향 실측 — OVERNIGHT-FROZEN-PLAN-DEVICE-01

사용자가 A24 연결과 필요한 실측·오류 수정·회의 준비를 승인한 2026-10-11 작업이다. PC 후보와 모형 선택에 새 실측 결과를 사용하지 않았다. 기존 중단 실험·실패·체크포인트·사용자 Android 변경을 보존하고 새 ID/clock/계획으로 실행했다.

## 무엇을 실제로 실행했는가

사전 고정한 같은 96건(공통 시작 +35초부터 350ms 교대, 긴급 분류48·일반 탐지48, 1.5초·6초 기한)에 대한 Band 대응 일정과 기존 리스트 선택 일정이다. ABBA 4세션, 설치 상한1·요청384·warmup32·runtime16이다. 원 APK의 replay는 CPU 일괄/B2 일괄과24건만 허용해, 별도 전체 소스 스냅샷에 opt-in `{replay.build.VERSION}`를 추가했다. 기존 Android 작업트리와 앱 기본 정책은 수정하지 않았다. 프로젝트와 동일한 서명·패키지·버전을 확인하고 `pm install -r`로 자료를 보존했다.

판단 자체를 휴대폰에서 다시 계산한 온라인 Band/RL 실행은 아니다. PC 계획의 backend와 release 시각을 재생하며, 실제 lane가 AVAILABLE이 될 때까지 기다렸다. 분류CPU/GPU·탐지CPU만, CG_DC 두 작업 병행만 허용한다. CPU/GPU 분류 두 작업의 미검증 병행은 현재 owner로 차단하며 요청을 보존한다. 응답은 긴급 OUTPUT_READY/일반 PERSISTED, lane 재사용은 실제 AVAILABLE이다.

원 export가 common−35초 상대 좌표인 ABI 오류는 실측 전에 발견했다. PC 원장 자체는 이미35초도착이었으며 원장과 roundtrip 검산한 common0 export를 사용했다. 원 상대 자료와 빌드 오류·미설치 APK를 보존했다. 첫 Gradle SDK 환경 누락, sourceSets override와 기본서명 차이를 검사에서 차단하고 전체 프로젝트 스냅샷·설치 APK와 같은 기존 서명 경로로 보완했다. 서명 키·모델 원binary·대용량 raw는 공유하지 않는다.

## 실제 결과

| 순서 | 일정 | 완료 | 긴급 / 일반 기한 실패 | 긴급 P95 ms | 공통120초 조건부 J | 최고 AP °C | 초기 AP °C |
|---:|---|---:|---:|---:|---:|---:|---:|
{rows}

종료 상태 `{terminal['status']}`. 새 자료의 계수 적합0·온라인 정책 실행0이며, 실제 계획 재생은 {result['physical_sessions']}회·설치 {result['installs']}회다. 각 예정 요청의 실제 도착·응답·저장·AVAILABLE·기한 결과를 전량 CSV에 남겼다. 기한 지연이나 미완료가 있으면 비용 감소만으로 우위를 선언하지 않는다.

## 적용 범위와 모형 검증

두 순서 반전 쌍의 초기 AP 차이가 기존 환경매칭 폭0.5°C 안인지 별도로 표시했다. 이는 효과 허용 오차·열 안전 한도가 아니다. 배터리≥20%·비충전·BAT≤35°C·thermal status0·기존 화면 조건을 유지하며 절전 상태와 잔량을 기록했다. 초기 AP/잔량/배경 상태가 완전히 같다는 주장은 하지 않는다.

공통120초 J는 기기 전체 배터리 전류 raw를 mA로 해석한 조건부 추정이며 절대 계측기 정확도가 인증되지 않았다. 온도는 같은 HAL AP 채널이며 표면 온도·안전 한도 초과시간은 계산 불가다. 1초 전류·약2초 AP 관측은 요청 단위 에너지나 GPU kernel 병행 측정이 아니다. 각 정책 n=2이므로 작은 차이의 유의성·실제품 우월성·전체 조건 채택 근거로 삼지 않는다.

모형 오차는 새 결과 fit0인 상태에서, 도착 전−20..30초 AP/전력만 초기 입력으로 쓴 A(실제 점유 조건부)와 B(동결 PC 점유 계획)를 나누어 계산했다. A는 실제 미래 점유를 알고 하는 사후 모형 검증이며 온라인 예측이 아니다. B는 기기별 실제 점유·미래 AP/전력을 입력에 넣지 않았다. 예정 service/실행 지연 오차는 각 요청의 PC 값과 실제 값으로 공개했다. 고정5phase·냉각에 따른 속도 회복 미지원·같은 초기조건 가정의 한계는 유지한다.

## 열어볼 파일과 재현

- [오프라인 화면](results/overnight_device_20261011/index.html)
- [384 요청 원장](results/overnight_device_20261011/requests.csv), [세션 성적](results/overnight_device_20261011/sessions.csv), [A/B 오차](results/overnight_device_20261011/model_errors.csv)
- [사전 실행 계약](results/overnight_device_20261011/execution_contract.json), [원본·계획 해시](results/overnight_device_20261011/summary.json)
- opt-in patch와 JVM 검증 코드는 같은 결과 폴더에 있다. 실제 APK에 포함된 사용자 WIP는 별도 private 스냅샷/전체 hash로 보존했으며 Git 원본과 조용히 합치지 않았다.

PC 기능 검증: `python -B -X utf8 -m unittest tools.test_d1_overnight_device_replay -v`. 결과 판독: `python -B -X utf8 -m tools.d1_overnight_device_report`. 실제 실행은 immutable local plan/동결 source/APK SHA와 미소비 registry가 필요하며, 이미 소비한 이번 ID를 새 기기실행으로 재사용하지 않는다. 측정 원자료는 `output/overnight_device_20261011_v1/run`에 보존한다.
'''
    (replay.ROOT/'docs/OVERNIGHT_DEVICE_REPLAY_20261011.md').write_text(text,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.parse_args();print(json.dumps(analyze(),ensure_ascii=False,indent=2))
