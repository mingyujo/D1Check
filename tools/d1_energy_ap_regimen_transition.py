"""Frozen A24 regimen model: observed-schedule protocol-transfer diagnosis only.

This module has no device or fitting path. Arbitrary arrival schedules remain unsupported.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path

from tools import d1_energy_state_collection as state
from tools.d1_energy_ap_collect05_partial import paths_for_confirmation

FROZEN_SHA256 = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'
STATES = ('classification_GPU+detection_CPU', 'resident_idle', 'detection_CPU',
          'resident_idle', 'classification_GPU', 'resident_idle', 'resident_idle')
BLOCKS = ('pair', 'idle_1', 'solo_b', 'idle_2', 'solo_a', 'idle_tail', 'post_work_wait')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def support(stats, manifest, development_manifest, frozen, *, mode='observed_regimen_schedule'):
    """Return a reason, not a zero prediction, for any unsupported condition."""
    if mode != 'observed_regimen_schedule':
        return 'unsupported_arrival_or_unobserved_schedule'
    if (stats.get('status') != 'eligible_regimen_only' or stats.get('condition') != 'CG_DC'
            or stats.get('phase') != 'confirmation'):
        return 'unsupported_session_or_pair'
    if (manifest.get('session_control') != 'device-after-probe-diagnostic-v1'
            or manifest.get('autonomous_diagnostic_only') is not True
            or manifest.get('mode') != 'calibration'):
        return 'unsupported_protocol'
    if ([x.get('state') for x in stats.get('blocks',[])] != list(STATES)
            or [x.get('name') for x in stats.get('blocks',[])] != list(BLOCKS)):
        return 'unsupported_state_sequence'
    if manifest.get('device_fingerprint') != development_manifest.get('device_fingerprint'):
        return 'unsupported_device'
    if manifest.get('images') != development_manifest.get('images'):
        return 'unsupported_input'
    if manifest.get('cpu_threads') != development_manifest.get('cpu_threads') or len(manifest.get('models',{})) != 4:
        return 'unsupported_resident_configuration'
    for key, spec in manifest['models'].items():
        old = development_manifest['models'].get(key)
        if old is None or spec['model']['sha256'] != old['model']['sha256'] or spec['runtime'] != old['runtime']:
            return 'unsupported_model_or_runtime'
    low, high = frozen['initial_ap_development_range_c']
    if not low <= stats['start_ap_c'] <= high:
        return 'unsupported_initial_ap_outside_development_start_range'
    if stats.get('common_window',{}).get('full_energy_j') is None:
        return 'unsupported_energy_coverage'
    return 'posthoc_protocol_transfer_only'


def calculate(stats, manifest, development_manifest, frozen):
    verdict = support(stats, manifest, development_manifest, frozen)
    if verdict != 'posthoc_protocol_transfer_only':
        return dict(status=verdict, energy_j=None, ap_c=None)
    errors = state.evaluate(stats, frozen, {})
    errors['meaning'] = 'DIAG-04 posthoc protocol transfer, not formal confirmation or independent validation'
    energy_rows, ap_rows = paths_for_confirmation(stats, frozen)
    block_rows = []
    for block in stats['blocks']:
        seconds = (block['end_ns']-block['start_ns'])/1e9
        predicted = frozen['whole_device_power_w'][block['state']]*seconds
        observed = block['power']['full_energy_j']
        if observed is None:
            return dict(status='unsupported_block_energy_coverage',energy_j=None,ap_c=None)
        ap = [r for r in ap_rows if r['block']==block['name']]
        block_rows.append(dict(block=block['name'],state=block['state'],duration_s=seconds,
                               observed_energy_j=observed,predicted_energy_j=predicted,
                               signed_energy_error_j=predicted-observed,
                               ap_samples=len(ap),ap_mae_c=sum(abs(r['predicted_ap_c']-r['observed_ap_c']) for r in ap)/len(ap),
                               ap_max_absolute_error_c=max(abs(r['predicted_ap_c']-r['observed_ap_c']) for r in ap)))
    mapped_s = sum(r['duration_s'] for r in block_rows)
    mapped_observed = sum(r['observed_energy_j'] for r in block_rows)
    mapped_predicted = sum(r['predicted_energy_j'] for r in block_rows)
    assert abs(mapped_predicted-errors['common_energy_predicted_full_window_j']) < 1e-8
    assert abs(energy_rows[-1]['observed_energy_j']-stats['common_window']['full_energy_j']) < 1e-8
    return dict(status=verdict,errors=errors,block_rows=block_rows,energy_rows=energy_rows,ap_rows=ap_rows,
                mapped_seconds=mapped_s,unmapped_seconds=stats['common_window']['duration_s']-mapped_s,
                mapped_observed_energy_j=mapped_observed,mapped_predicted_energy_j=mapped_predicted,
                mapped_signed_error_j=mapped_predicted-mapped_observed,
                unmapped_observed_energy_j=stats['common_window']['full_energy_j']-mapped_observed)


def write_csv(path, rows):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def write_dashboard(output, summary, blocks):
    errors=summary['errors']
    old=summary['previous_dc_dc_confirmation']
    def f(value):return f'{value:.3f}'
    rows=''.join('<tr>'+''.join(f'<td>{html.escape(str(value))}</td>' for value in (
        b['block'],b['state'],f(b['duration_s']),f(b['observed_energy_j']),
        f(b['predicted_energy_j']),f(b['signed_energy_error_j']),f(b['ap_mae_c'])))+'</tr>' for b in blocks)
    arrival_audit = '''<h2>짧은 도착 상태의 표본 해상도 감사 (별도 PC 일정)</h2>
<p>사전 고정한 queue·seed 201·strict 24요청의 CPU_URGENT/FIXED_SPLIT 일정입니다. 실기기 수집이 아니며 에너지·AP 예측값을 생성하지 않습니다. <a href="short_transition_occupancy.csv">상태별 초·구간 수 CSV</a> · <a href="short_transition_audit.json">입력 해시·가정</a>.</p>
<img src="short_transition_occupancy.svg" alt="PC 일정의 단독 lane 점유시간; 병행 구간은 없음">
<p>이 일정에서 FIXED_SPLIT의 분류 CPU＋탐지 GPU 병행 구간은 없었습니다. 짧은 단독 실행은 1초 전류·약 2.65초 AP 표본에서 상태별 계수를 분리할 근거가 아닙니다. 기존 120초 공통창에는 긴 완료 후 유휴가 포함됩니다. 동결 모형의 임의 도착 지원은 계속 불가입니다.</p>''' if (output/'short_transition_occupancy.svg').is_file() else ''
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 상태 모형 전이 평가</title>
<style>body{{font:16px/1.55 system-ui,'Malgun Gothic';max-width:1100px;margin:2em auto;padding:0 1em;color:#183246}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd8e1;padding:.4em;text-align:right}}td:first-child,th:first-child{{text-align:left}}img{{width:100%}}.warn{{background:#fff0cf;padding:1em}}</style>
<h1>동결 A24 에너지·AP 상태 모형: CG_DC 전이 진단</h1>
<p class="warn">새 APK의 DIAG-04 1세션을 과거 개발3세션 동결 모형에 사후 적용했습니다. 실행된 블록 상태·전환 시각과 관측 시작 AP 32.6°C를 예측 입력으로 사용했습니다. 미래 일정 자체를 예측하지 않았습니다. 확인 결과를 본 뒤의 분석이며 독립 사전등록 평가나 정확도 PASS가 아닙니다.</p>
<p><a href="../energy_ap_state_collect05/README.md">기존 개발3·DC_DG 확인</a> · <a href="summary.json">전이 결과 JSON</a> · <a href="blocks.csv">구간 잔차 CSV</a> · <a href="energy_path.csv">에너지 경로 CSV</a> · <a href="ap_path.csv">AP 경로 CSV</a> · <a href="README.md">재현·지원 범위</a></p>
<table><tr><th>자료 역할</th><th>조건</th><th>관측 J</th><th>예측−관측 J</th><th>AP 경로 MAE °C</th><th>AP 최고 예측−관측 °C</th></tr>
<tr><td>기존 개발 적합</td><td>CC_DG, CG_DC, DC_DG</td><td colspan="4">3세션·동결 파일 SHA {FROZEN_SHA256[:12]}…; 독립 확인 아님</td></tr>
<tr><td>기존 확인</td><td>DC_DG</td><td>{f(old['common_energy_observed_covered_j'])}</td><td>{f(old['signed_energy_error_on_covered_time_j'])}</td><td>{f(old['ap_path_mae_c'])}</td><td>{f(old['ap_peak_signed_error_c'])}</td></tr>
<tr><td>새 프로토콜 전이</td><td>CG_DC</td><td>{f(summary['observed_common_energy_j'])}</td><td>{f(summary['mapped_signed_error_j'])}*</td><td>{f(errors['ap_path_mae_c'])}</td><td>{f(errors['ap_peak_signed_error_c'])}</td></tr></table>
<p>*전이의 공통창 {f(summary['common_window_s'])}초 중 상태 매핑 {f(summary['mapped_seconds'])}초에서만 비교: 관측 {f(summary['mapped_observed_energy_j'])}J·예측 {f(summary['mapped_predicted_energy_j'])}J. 미매핑 {f(summary['unmapped_seconds'])}초의 관측 {f(summary['unmapped_observed_energy_j'])}J를 예측 0으로 채우지 않았습니다. 전체 관측은 {f(summary['observed_common_energy_j'])}J입니다. 기존 평가 함수의 전체 관측 대비 잔차 {f(errors['signed_energy_error_on_covered_time_j'])}J와 경계가 다릅니다.</p>
<img src="paths.svg" alt="공통창 누적 기기 에너지·AP 실측 대 개발 동결 예측, 누적 에너지 잔차">
<h2>상태 구간별 예측−관측 잔차</h2><table><tr><th>구간</th><th>상태</th><th>초</th><th>관측 J</th><th>예측 J</th><th>잔차 J</th><th>AP MAE °C</th></tr>{rows}</table>
<h2>시뮬레이터 지원 경계</h2>
<p><b>계산 가능:</b> 동일 A24·두 exact 모델/입력·네 resident runtime·CPU 1 thread에서 이 CG_DC의 실제 600초 블록 일정과 개발 시작 AP 범위 32.5–34.0°C가 주어진 조건부 사후 진단. 계산된 오차는 프로토콜 변경의 한 세션 사례다.</p>
<p><b>계산 불가:</b> 임의 도착·짧은 병행·큐/callback 전력·다른 초기 AP·CC_DG 새 프로토콜 확인·배터리 온도/잔량·throttling. 기존 합성 정책 화면의 에너지/AP 수치는 별도 탐색 가정이다. 새 동결 profile을 그 엔진에 넣으면 수치 대신 UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS를 반환한다.</p>
{arrival_audit}
<p>J는 A24 raw=mA 조건부 기기 전체 소비이며 절대 정확도 미인증입니다. AP는 mType=0 센서이며 BAT·표면 온도·안전 한도가 아닙니다. 30°C 초과시간은 기존 연구용 지표로, 양쪽 유효 AP 구간 {f(errors['ap_threshold_observed_exceedance_s'])}초에서 오차 {f(errors['ap_threshold_exceedance_error_s'])}초입니다. 전체 600초의 한도 준수 증명이 아닙니다.</p>
<p><a href="../energy_ap_short_transition_01/dashboard.html">CC_DG 짧은 전환 진단(시작 AP 지원 범위 밖 외삽)</a> · <a href="../energy_model_bridge_02/dashboard.html">기존 고정870건 모형</a> · <a href="../arrival_policy_screen_01/dashboard.html">통합 정책 탐색</a></p></html>'''
    (output/'dashboard.html').write_text(page,encoding='utf-8')


def main():
    p=argparse.ArgumentParser()
    for name in ('run','development-run','frozen','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    if digest(a.frozen)!=FROZEN_SHA256:raise ValueError('frozen model byte identity changed')
    frozen=read(a.frozen)
    s=list(a.run.glob('00_*'))
    if len(s)!=1:raise ValueError('expected one diagnostic session')
    s=s[0];stats=read(s/'validated.json');manifest=read(s/'artifacts/manifest.json')
    dev=list(a.development_run.glob('01_*'))
    if len(dev)!=1:raise ValueError('development CG_DC manifest missing')
    development_manifest=read(dev[0]/'artifacts/manifest.json')
    prior=list(a.development_run.glob('03_*'))
    if len(prior)!=1:raise ValueError('prior DC_DG confirmation missing')
    prior_stats=read(prior[0]/'validated.json')
    if prior_stats.get('condition')!='DC_DG' or prior_stats.get('phase')!='confirmation':
        raise ValueError('prior confirmation lineage mismatch')
    for name,path in [('manifest',s/'artifacts/manifest.json'),('progress',s/'artifacts/progress.jsonl'),('thermal',s/'thermal.jsonl')]:
        if digest(path)!=stats['input_hashes'][name]:raise ValueError('diagnostic raw hash mismatch '+name)
    result=calculate(stats,manifest,development_manifest,frozen)
    if result['status']!='posthoc_protocol_transfer_only':
        raise ValueError(result['status'])
    a.output.mkdir(parents=True,exist_ok=True)
    for name,key in [('blocks.csv','block_rows'),('energy_path.csv','energy_rows'),('ap_path.csv','ap_rows')]:
        write_csv(a.output/name,result[key])
    summary={k:v for k,v in result.items() if not k.endswith('_rows')}
    summary.update(dict(version='energy-ap-regimen-transition-pc-v1',frozen_sha256=FROZEN_SHA256,
                        diagnostic_manifest_sha256=digest(s/'artifacts/manifest.json'),
                        diagnostic_progress_sha256=digest(s/'artifacts/progress.jsonl'),
                        scope='observed CG_DC regimen schedule; protocol-transfer diagnosis; not arbitrary arrivals',
                        data_role='posthoc transfer diagnostic; already viewed diagnostic and DC_DG summary',
                        apk_change=[development_manifest['apk_sha256'],manifest['apk_sha256']],
                        previous_dc_dc_confirmation=prior_stats['confirmation_errors'],
                        observed_common_energy_j=stats['common_window']['full_energy_j'],
                        common_window_s=stats['common_window']['duration_s'],
                        initial_ap_c=stats['start_ap_c'],
                        frozen_coefficients=dict(whole_device_power_w=frozen['whole_device_power_w'],
                                                 ap_slope_at_30_c_per_s=frozen['ap_slope_at_30_c_per_s'],
                                                 ap_cooling_rate_per_s=frozen['ap_cooling_rate_per_s'],
                                                 initial_ap_development_range_c=frozen['initial_ap_development_range_c']),
                        experiment_ready=False,independent_validation=False))
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
    e=result['energy_rows'];t=result['ap_rows']
    axes[0].plot([r['time_s'] for r in e],[r['observed_energy_j'] for r in e],label='관측, 조건부 J')
    axes[0].plot([r['time_s'] for r in e],[r['predicted_energy_j'] for r in e],label='개발 동결, 실제 일정 입력',ls='--')
    axes[0].set_ylabel('누적 기기 전체 J');axes[0].legend()
    axes[1].plot([r['time_s'] for r in t],[r['observed_ap_c'] for r in t],label='AP 관측')
    axes[1].plot([r['time_s'] for r in t],[r['predicted_ap_c'] for r in t],label='개발 동결',ls='--')
    axes[1].set_ylabel('AP °C');axes[1].legend()
    axes[2].plot([r['time_s'] for r in e],[r['predicted_energy_j']-r['observed_energy_j'] for r in e],label='에너지 예측−관측 J')
    axes[2].axhline(0,color='gray',lw=.8);axes[2].set_ylabel('누적 잔차 J');axes[2].set_xlabel('공통창 시작 후 초')
    fig.suptitle('CG_DC DIAG-04 프로토콜 전이 사후 진단 — 새 APK, 실제 일정 입력')
    fig.tight_layout()
    svg=a.output/'paths.svg'
    fig.savefig(svg,metadata={'Date':None});fig.savefig(a.output/'paths.png',dpi=120);plt.close(fig)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                   encoding='utf-8')
    write_dashboard(a.output,summary,result['block_rows'])
    print(json.dumps({k:summary[k] for k in ('status','mapped_signed_error_j','unmapped_seconds','errors')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
