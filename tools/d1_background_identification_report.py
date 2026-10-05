"""Render the registered PC identification result without fitting or device access."""
import argparse
import csv
import html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_background_identification as d


def render(folder):
    folder=Path(folder);ev=folder/'evaluation';summary=d.c.read(ev/'summary.json')
    candidate=d.c.read(ev/'candidate.json');assoc=d.c.read(ev/'association.json')
    cases=d.c.read(folder/'bundle/inputs.json');model=d.c.read(folder/'bundle/model.json')
    with (ev/'ap_paths.csv').open(encoding='utf8') as f:
        curves=list(csv.DictReader(f))
    fig,axes=plt.subplots(4,2,figsize=(12,12),layout='constrained');energies=[]
    for i,(s,case) in enumerate(zip(summary,cases)):
        rows=[r for r in curves if r['id']==s['id']];times=[float(r['t_s']) for r in rows]
        for key,label in [('observed_ap_c','Observed AP'),('frozen_ap_c','Frozen AP')]:
            axes[i,0].plot(times,[float(r[key]) for r in rows],label=label)
        axes[i,0].set(title=s['id']+' | gamma=0 (not adopted)',ylabel='AP (C)',xlabel='Common time (s)')
        for t in range(1,121):
            obs=d.c.integral(case['power'],0,t)
            fixed=case['preload_w']*t+d.c.task_j(case['actual_segments'],model,0,t)
            old=case['legacy_preload_w']*t+d.c.task_j(case['actual_segments'],model,0,t)
            if obs is None:raise ValueError('missing energy, no fill')
            energies.append(dict(id=case['id'],t_s=t,observed_j=obs,legacy_predicted_j=old,
                                 corrected_predicted_j=fixed,corrected_error_j=fixed-obs,legacy_error_j=old-obs))
        local=energies[-120:]
        for key,label in [('legacy_error_j','Legacy input (10..30s)'),('corrected_error_j','Frozen input (-20..30s)')]:
            axes[i,1].plot([r['t_s'] for r in local],[r[key] for r in local],label=label)
        axes[i,1].axhline(0,color='black',linewidth=.5)
        axes[i,1].set(title='Prediction minus observation',ylabel='Cumulative J residual',xlabel='Common time (s)')
        for ax in axes[i]:ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('Four development sessions / two blocks: conditional, post-hoc; no independent PASS')
    fig.savefig(ev/'paths.png',dpi=120);plt.close(fig)
    d.c.csv_write(ev/'energy_paths.csv',energies)
    cross=candidate['cross_validation'];stats={}
    for mode in ('session','block'):
        sub=[r for r in cross if r['exclusion']==mode]
        stats[mode]={k:float(np.mean([r[k]['mae_c'] for r in sub])) for k in ('frozen','candidate')}
    forecasts=d.c.read(ev/'forecasts.json');future={}
    for h in (10,30):
        sub=[r for r in forecasts if r['horizon_s']==h]
        # Equal session weight, not pooled sensor samples. Only bounded common-window J.
        values={}
        for key in ('frozen_ap_error_c','ap_error_c','frozen_j_error','j_error'):
            per={s['id']:[abs(r[key]) for r in sub if r['id']==s['id'] and r[key] is not None] for s in summary}
            values[key]=dict(equal_session_mae=float(np.mean([np.mean(v) for v in per.values() if v])),
                             counts={k:len(v) for k,v in per.items()})
        future[str(h)]=values
    d.c.write(ev/'display_metrics.json',dict(exclusion_mae_c=stats,future_diagnostic=future,
        energy_mae_j={k:float(np.mean([abs(s[k]) for s in summary])) for k in ('legacy_error_j','corrected_error_j')}))
    table=''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in [s['id'],f"{s['observed_120s_j']:.3f}",
        f"{s['legacy_error_j']:+.3f}",f"{s['corrected_error_j']:+.3f}",f"{s['frozen']['mae_c']:.3f}"] )+'</tr>' for s in summary)
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>배경 보정 후보 판정</title>
<style>body{{max-width:1100px;margin:2rem auto;font:17px/1.6 system-ui;padding:1rem}}td,th{{padding:.5rem;border:1px solid #ccc}}table{{border-collapse:collapse}}img{{width:100%}}.warning{{background:#fff1cc;padding:1rem}}</style>
<h1>전력 초기화 수정 · gamma 후보 미채택</h1><p class="warning">개발 4세션 / 별도 수집 block 2개. 새 독립 확인 0. 기본 모형·strict·experiment_ready=false 유지. 기기 명령 0.</p>
<p>동결 모형의 −20~30초 전력 입력을 복원했습니다. 원본과 기존 10~30초 결과는 보존합니다. AP 초기화·계수는 그대로이며 gamma≥0 최적값은 0입니다.</p>
<table><tr><th>세션</th><th>관측 120초 J</th><th>기존 J 오차</th><th>수정 J 오차</th><th>AP MAE °C</th></tr>{table}</table>
<p>세션 제외 평균 MAE: {stats['session']['frozen']:.6f} → {stats['session']['candidate']:.6f}°C.
block 제외: {stats['block']['frozen']:.6f} → {stats['block']['candidate']:.6f}°C.
gamma의 세션별 방향이 일관되지 않아 배경 전력을 AP 오차의 단일 원인으로 채택할 근거가 없습니다.</p>
<img src="evaluation/paths.png" alt="네 개발 세션의 관측·동결 AP와 초기화 수정 전후 누적 에너지 잔차">
<p>AP는 common 35초~각 냉각 종료(관측점), J는 common 0~120초. 실제 lane 일정 조건부 계산이며 온라인 정책 우월성 검증이 아닙니다.
전류 raw=mA 가정, 절대 에너지 정확도 미인증. CPU 활동은 기술적 동시성 관측이며 GPU·무선 전력 귀속이 아닙니다.</p>
<p><a href="README.md">판정·한계·재현 명령</a> · <a href="evaluation/candidate.json">후보와 제외 평가</a> · <a href="evaluation/association.json">CPU 동시성</a> · <a href="evaluation/display_metrics.json">미래 예측 진단 수치</a></p></html>'''
    (folder/'index.html').write_text(page,encoding='utf8')
    return stats


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);a=p.parse_args();print(render(a.folder))
