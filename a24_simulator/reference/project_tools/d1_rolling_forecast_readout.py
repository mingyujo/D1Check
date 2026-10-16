"""Saved forecast diagnostics and figures; never re-fit or replay a policy engine."""
import argparse
import csv
import html
from pathlib import Path
import numpy as np
from tools import d1_rolling_forecast as r


def read(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def analyze(output):
    out=Path(output);rows=read(out/'window_errors.csv')
    snapshots={(x['id'],float(x['cutoff_s'])):x for x in read(out/'snapshots.csv')}
    strata=[];totals=[];signals=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        for kind in ('resident_idle','transition_or_mixed','single_state_load'):
            for method in r.METHODS:
                use=[x for x in rows if x['block']==block and x['role']==role and x['segment_type']==kind and x['method']==method]
                j=[float(x['abs_j']) for x in use if x['abs_j']];ap=[float(x['ap_mae_c']) for x in use if x['ap_mae_c']]
                strata.append(dict(block=block,role=role,segment_type=kind,method=method,energy_windows=len(j),
                                   energy_mae_10s_j=float(np.mean(j)) if j else None,ap_windows=len(ap),
                                   ap_mae_10s_c=float(np.mean(ap)) if ap else None,independent_unit='session; window aggregate descriptive only'))
        for identity in dict.fromkeys(x['id'] for x in rows if x['block']==block and x['role']==role):
            for method in r.METHODS:
                use=[x for x in rows if x['id']==identity and x['method']==method and x['signed_j']]
                totals.append(dict(id=identity,block=block,role=role,method=method,observed_union_s='35..115',
                                   signed_error_80s_j=sum(float(x['signed_j']) for x in use),
                                   absolute_net_error_80s_j=abs(sum(float(x['signed_j']) for x in use)),
                                   sum_absolute_window_errors_j=sum(float(x['abs_j']) for x in use),common120_error_j=None,
                                   interpretation='eight forecasts issued sequentially; not one forecast at 35s'))
    for x in rows:
        if x['method']=='FROZEN_OPEN_LOOP' and x['signed_j']:
            s=snapshots[(x['id'],float(x['start_s']))];past=float(s['power_delta_w']);future=-float(x['signed_j'])/10
            signals.append(dict(id=x['id'],block=x['block'],role=x['role'],start_s=x['start_s'],past_residual_w=past,
                                future_residual_w=future,same_sign=past*future>0,diagnostic_only=True))
    r.h.m.table(out/'segment_summary.csv',strata);r.h.m.table(out/'partial_totals.csv',totals);r.h.m.table(out/'past_future_residual.csv',signals)
    summary=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        use=[x for x in signals if x['block']==block and x['role']==role]
        item=dict(block=block,role=role,windows=len(use),same_sign=sum(x['same_sign'] for x in use),
                  past_future_residual_correlation=float(np.corrcoef([x['past_residual_w'] for x in use],[x['future_residual_w'] for x in use])[0,1]),
                  correlation_is_not_causal=True)
        for method in r.METHODS:
            group=[x for x in totals if x['block']==block and x['role']==role and x['method']==method]
            item[method+'_net80_mae_j']=float(np.mean([x['absolute_net_error_80s_j'] for x in group]))
        summary.append(item)
    r.h.m.write(out/'diagnostics.json',summary)
    plot(out,rows,totals)


def plot(out,rows,totals):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    comparison=read(out/'comparison.csv');positions=[('history','development'),('history','confirmation'),('sustained','evaluation')]
    colors={'FROZEN_OPEN_LOOP':'#bf4b40','OBSERVATION_PERSISTENCE':'#7d8391','ROLLING_OFFSET':'#237b67'}
    names={'FROZEN_OPEN_LOOP':'부하 전 동결 예측','OBSERVATION_PERSISTENCE':'관측값 유지','ROLLING_OFFSET':'관측 잔차 갱신'}
    fig,axes=plt.subplots(1,3,figsize=(16,4.7),constrained_layout=True)
    for ax,metric,title,unit in zip(axes,('energy_mae_10s_j','ap_mae_10s_c','net80'),
                                  ('다음10초 J 절대오차','다음10초 AP 경로오차','갱신8회 합산80초 순오차'),('J','°C','J')):
        highest=0.
        for i,method in enumerate(r.METHODS):
            values=[]
            for b,role in positions:
                if metric=='net80':
                    values.append(float(np.mean([x['absolute_net_error_80s_j'] for x in totals if x['block']==b and x['role']==role and x['method']==method])))
                else:values.append(float(next(x for x in comparison if x['block']==b and x['role']==role and x['method']==method)[metric]))
            bars=ax.bar(np.arange(3)+(i-1)*.24,values,width=.24,color=colors[method],label=names[method]);highest=max(highest,max(values))
            for bar,v in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,v,f'{v:.3f}',ha='center',va='bottom',fontsize=8)
        ax.set_ylim(0,highest*1.4);ax.set_ylabel(unit);ax.set_xticks(range(3),['개발6','확인6','기존 지속8']);ax.set_title(title)
        ax.legend(fontsize=7,loc='upper center')
    fig.suptitle('같은 10초 창에서 비교 · AP 개선/개별 J 악화/합산 상쇄를 구분 · 120초 예측 아님')
    fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    paths=read(out/'ap_paths.csv');ids=['confirmation_180_C0','confirmation_30_CPU','confirmation_180_PAR','confirmation_30_C0']
    fig,axes=plt.subplots(2,2,figsize=(13,7),constrained_layout=True)
    for ax,identity in zip(axes.ravel(),ids):
        observed=[x for x in paths if x['id']==identity and x['method']=='FROZEN_OPEN_LOOP']
        ax.plot([float(x['t_s']) for x in observed],[float(x['observed']) for x in observed],color='#25303b',label='관측',lw=1.4)
        for method in ('FROZEN_OPEN_LOOP','ROLLING_OFFSET'):
            for j,start in enumerate(sorted({x['window_start_s'] for x in paths if x['id']==identity},key=float)):
                use=[x for x in paths if x['id']==identity and x['method']==method and x['window_start_s']==start]
                ax.plot([float(x['t_s']) for x in use],[float(x['predicted']) for x in use],color=colors[method],lw=1.2,label=names[method] if j==0 else None)
        ax.set_title(identity,fontsize=10);ax.set_xlabel('공통창 기준 초');ax.set_ylabel('AP °C');ax.legend(fontsize=8)
    fig.suptitle('각 10초 조각은 해당 시점에 새로 발행한 예측 · 한 번의 180초 예측곡선 아님')
    fig.savefig(out/'confirmation_AP.png',dpi=140);plt.close(fig)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>10초 관측 갱신 예측</title>
    <style>body{font:16px sans-serif;max-width:1200px;margin:30px auto;padding:20px}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:9px}img{max-width:100%}aside{padding:18px;background:#fff1cf}</style>
    <h1>기록 관측으로 갱신한 다음10초 예측</h1><aside>AP 평균오차는확인0.258→0.156°C/지속0.383→0.209°C로개선.
    개별10초J오차는악화(확인0.870→1.268J). 80초갱신예측합의순오차감소는상쇄를포함하며120초전체예측개선이아님.
    실제 미래 일정이 주어진 조건부 비용 예측·이미본자료 사후평가, 온라인정책·실기기절감 미검증.</aside>
    <p>AP after_ns와전력기록시점이발행시점이전인표본만입력. host전달지연·센서내부갱신보장·앱numeric AP경로는실기기미확인.
    에너지J35..115초8창, AP35..175초14창. 같은겹치지않는10초창에서세션평균을비교한다.</p>
    <p><a href="README.md">범위·재현</a> · <a href="window_errors.csv">840행 전체창</a> · <a href="session_errors.csv">20세션별오차·악화</a> · <a href="partial_totals.csv">합산상쇄</a></p>'''
    page+='<table><tr><th>자료</th><th>역할</th><th>방식</th><th>세션</th><th>10초 J MAE</th><th>10초 AP MAE</th><th>J 악화</th><th>AP 악화</th></tr>'
    for row in comparison:page+='<tr>'+''.join('<td>'+html.escape(row[k])+'</td>' for k in ('block','role','method','n','energy_mae_10s_j','ap_mae_10s_c','energy_worse_sessions','ap_worse_sessions'))+'</tr>'
    page+='</table><img src="comparison.png" alt="같은10초창오차와합산상쇄"><img src="confirmation_AP.png" alt="시점마다발행한AP예측조각"></html>'
    (out/'index.html').write_text(page,encoding='utf-8')
    print('Saved diagnostics and 2 figures; new fit/device/policy execution0')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);analyze(Path(p.parse_args().output))
