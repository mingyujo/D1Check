"""Export small, identifier-free confirmation results; no device or fitting calls."""
import argparse
import csv
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, values):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(values[0]))
        w.writeheader(); w.writerows(values)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError('fresh share output required')
    s = read(a.source/'summary.json')
    assert all(x['status'] == 'evaluated_fixed_candidate' for x in s['sessions'])
    a.output.mkdir(parents=True)
    # Strip raw thermalservice text from host cleanup. Keep separate app/host facts.
    for c in s['consumption']:
        c['host_cleanup'] = {k:v for k,v in c['host_cleanup'].items() if k != 'thermal'}
    s['device_commands'] = s['receipt']['adb_commands']
    s['analysis_device_commands'] = 0
    s['execution_base_head'] = '4c8be6678cceb684c76ce4de14852f0e806719ee'
    (a.output/'summary.json').write_text(json.dumps(s, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    metrics = []
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), constrained_layout=True)
    ef, ea = plt.subplots(2, 2, figsize=(13, 6), constrained_layout=True)
    colors = {'idle':'#cbd5e1', 'classification:GPU':'#0284c7', 'detection:CPU':'#d97706',
              'classification:GPU+detection:CPU':'#7c3aed'}
    for col, x in enumerate(s['sessions']):
        role = x['role']; src = a.source/role; dest = a.output/role; dest.mkdir()
        for name in ('ap_paths.csv', 'prediction_inputs.json'):
            shutil.copyfile(src/name, dest/name)
        for name in ('energy_path.csv', 'phase_energy_residuals.csv'):
            shutil.copyfile(src/'legacy'/name, dest/name)
        # Original path rows are at sensor timestamps, not necessarily at 0/120.
        # The readout summary integrates the bracketed exact window. Add those
        # already-computed boundaries, without extrapolating a final sample.
        legacy = x['legacy_comparison']
        energy_rows = rows(dest/'energy_path.csv')
        assert 0 < float(energy_rows[0]['elapsed_s']) < float(energy_rows[-1]['elapsed_s']) < 120
        energy_rows = [dict(elapsed_s=0, observed_j=0, predicted_j=0, signed_error_j=0),
                       *energy_rows, dict(elapsed_s=120,
                       observed_j=legacy['observed_energy_120s_j'],
                       predicted_j=legacy['predicted_energy_120s_j'],
                       signed_error_j=legacy['signed_energy_error_j'])]
        write_csv(dest/'energy_path.csv', energy_rows)
        phases = rows(dest/'phase_energy_residuals.csv')
        assert abs(sum(float(z['observed_j']) for z in phases)-legacy['observed_energy_120s_j'])<1e-8
        assert abs(sum(float(z['predicted_j']) for z in phases)-legacy['predicted_energy_120s_j'])<1e-8
        # The legacy helper emits a default scenario=queue label. Actual frozen
        # manifest is burst201. Export only numeric state boundaries, no relabelled raw.
        state = [{k:r[k] for k in ('start_s','end_s','state')} for r in rows(src/'legacy/actual_states.csv')]
        write_csv(dest/'actual_states.csv', state)
        table = rows(dest/'ap_paths.csv'); ts = [float(r['elapsed_s']) for r in table]
        inp = read(dest/'prediction_inputs.json')
        for key, label, color in [('observed_ap_c','Observed','#111827'),
                                 ('candidate_ap_c','Fixed memory candidate','#047857'),
                                 ('existing_preload_ap_c','Existing preload candidate','#c2410c')]:
            axes[0,col].plot(ts, [float(r[key]) for r in table], label=label, color=color)
        for key, label, color in [('candidate_ap_c','Memory - observed','#047857'),
                                 ('existing_preload_ap_c','Preload - observed','#c2410c')]:
            axes[1,col].plot(ts,[float(r[key])-float(r['observed_ap_c']) for r in table], label=label,color=color)
        axes[1,col].axhline(0,color='#64748b',lw=.8)
        for ax in axes[:2,col]:
            ax.axvspan(inp['first_dispatch_s'],inp['last_lane_s'],color='#fbbf24',alpha=.17)
            ax.set_xlim(0,180); ax.grid(alpha=.2)
        axes[0,col].set_title(f"Pre-idle +{35 if col==0 else 65}s | new independent session")
        axes[0,col].set_ylabel('AP (C)'); axes[1,col].set_ylabel('Prediction - observed (C)')
        plotted_state = state + [z for z in inp['case']['segments'] if float(z['start_s']) >= 120]
        for i,(label,color) in enumerate(colors.items()):
            spans=[(float(z['start_s']),float(z['end_s'])-float(z['start_s'])) for z in plotted_state if z['state']==label]
            axes[2,col].broken_barh(spans,(i-.3,.6),facecolors=color)
        assert set(z['state'] for z in state)<=set(colors)
        axes[2,col].set_yticks(range(4),['Idle','CG','DC','CG + DC'])
        axes[2,col].set_xlim(0,180); axes[2,col].set_xlabel('Seconds from common start (120-180: cooling)')
        for ax in axes[:,col]: ax.axvline(120,color='#64748b',ls=':',lw=.8)
        energy=rows(dest/'energy_path.csv'); et=[float(r['elapsed_s']) for r in energy]
        for key,label in [('observed_j','Observed'),('predicted_j','Original frozen W diagnostic')]:
            ea[0,col].plot(et,[float(r[key]) for r in energy],label=label)
        ea[1,col].plot(et,[float(r['signed_error_j']) for r in energy],color='#b45309')
        ea[1,col].axhline(0,color='#64748b',lw=.8)
        for ax in ea[:,col]: ax.set_xlim(0,120); ax.grid(alpha=.2)
        ea[0,col].set_title(f'Pre-idle +{35 if col==0 else 65}s'); ea[0,col].set_ylabel('Cumulative J')
        ea[1,col].set_ylabel('Prediction - observed J'); ea[1,col].set_xlabel('Seconds from common start')
        y=[float(r['observed_ap_c']) for r in table]; v=[float(r['candidate_ap_c']) for r in table]
        assert abs(sum(abs(b-c) for b,c in zip(v,y))/len(y)-x['scores']['mae_c'])<1e-12
        legacy=x['legacy_comparison']
        assert abs(float(energy[-1]['elapsed_s'])-120)<1e-9
        assert abs(float(energy[-1]['observed_j'])-legacy['observed_energy_120s_j'])<1e-8
        assert abs(sum(float(z['end_s'])-float(z['start_s']) for z in state)-120)<1e-8
        metrics.append(dict(role=role,ap_start_s=ts[0],ap_end_s=ts[-1],ap_samples=len(y),
            initial_ap_c=x['initial_ap_c'],**x['scores'],preload_mae_c=x['existing_preload_scores']['mae_c'],
            observed_j=legacy['observed_energy_120s_j'],original_predicted_j=legacy['predicted_energy_120s_j'],
            signed_energy_error_j=legacy['signed_energy_error_j'],parallel_s=legacy['actual_parallel_seconds']))
    axes[0,0].legend(fontsize=8); axes[1,0].legend(fontsize=8); ea[0,0].legend(fontsize=8)
    fig.suptitle('Fixed candidate: actual schedule + pre-load AP only; no refit / no strict promotion')
    ef.suptitle('Original W model: exact 120 s diagnostic, outside original initial AP range')
    for f,name in [(fig,'ap_confirmation'),(ef,'energy_diagnostic')]:
        f.savefig(a.output/(name+'.svg')); f.savefig(a.output/(name+'.png'),dpi=140); plt.close(f)
        svg = a.output/(name+'.svg')
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    write_csv(a.output/'metrics.csv',metrics)
    tr=''.join(f"<tr><td>+{35 if i==0 else 65}초</td><td>{x['scores']['mae_c']:.3f}</td><td>{x['existing_preload_scores']['mae_c']:.3f}</td><td>{x['scores']['max_absolute_error_c']:.3f}</td><td>{x['scores']['peak_signed_error_c']:+.3f}</td></tr>" for i,x in enumerate(s['sessions']))
    (a.output/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AP 준비 이력 확인 결과</title><style>body{font:16px/1.7 system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#213547}img{width:100%}table{border-collapse:collapse}td,th{padding:10px;border:1px solid #ccd}aside{background:#fff4d6;padding:16px}a{color:#0369a1}</style><h1>고정 AP 후보 · 두 새 세션 확인</h1><p>2026-10-02 · completed_descriptive_only · 추가 적합0 · 추론64 · ADB1,698 · 581.797초</p><aside>자료 적격성과 오차 산출 완료. 정확도 PASS·정책 우월성·strict 지원 확대는 미판정입니다. 실제 일정과 부하 전 AP에 조건부인 예측이며, 조건당 독립 세션은 1개입니다.</aside><table><tr><th>부하 허용</th><th>새 후보 MAE °C</th><th>기존 preload MAE °C</th><th>새 후보 최대오차 °C</th><th>최고온도 부호오차 °C</th></tr>'''+tr+'''</table><p>AP 비교창: +35초 조건 35.631–179.801초(56표본), +65초 조건 67.616–177.656초(43표본). 빈 앞부분을 0으로 채우지 않았습니다. 노란 음영은 첫 dispatch부터 마지막 lane 해제까지이며 실제 병행과 같지 않습니다.</p><img src="ap_confirmation.svg" alt="AP 관측·고정 후보·기존 preload 및 부호 잔차, 실제 상태"><p>+35초 조건 후기 150–175초: 관측 +0.100°C, 후보 +0.001°C. 평균오차 감소가 후기 반응 크기 해결을 뜻하지 않습니다. 두 조건의 평가 길이·초기조건 차이로 MAE 간 차이를 인과 효과로 해석하지 않습니다.</p><img src="energy_diagnostic.svg" alt="공통120초 관측과 기존 동결 전력식 누적 J 및 잔차"><p>시작 AP27.4/27.9°C는 원래32.5–34.0°C 밖입니다. 에너지 진단 차이 +11.536/+14.880J이며 AP 후보 보완과 별개입니다. 전류 raw=mA 해석은 조건부이고 절대 J 정확도는 인증되지 않았습니다. 현재 APK로의 전이·짧은 상태 전환·일반 동적 정책 비용은 자동 검증되지 않습니다.</p><p><a href="metrics.csv">오차 CSV</a> · <a href="summary.json">작은 결과</a> · <a href="../../../AP_MEMORY_CONFIRM_RUN01_20261002.md">한국어 보고서</a> · <a href="../README.md">사전 계약/재현</a></p></html>''',encoding='utf-8')
    print(json.dumps({'sessions':2,'csv_plot_metric_checks':'passed','device_commands':0}))


if __name__=='__main__':
    main()
