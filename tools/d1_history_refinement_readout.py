"""Plot saved candidate readout, without re-fitting or launching simulations."""
import argparse
import csv
import gzip
import html
import json
from pathlib import Path
import numpy as np
from tools import d1_history_model_refinement as study


def rows(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def plot(output,summary_only=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic'
    plt.rcParams['axes.unicode_minus']=False
    output=Path(output);paths=json.loads(gzip.decompress((output/'paths.json.gz').read_bytes()))
    cases={x['id']:x for x in study.m.read(study.BUNDLE/'inputs.json.gz')}
    images=['history_development_paths.png','history_confirmation_paths.png','sustained_evaluation_paths.png'] if summary_only else []
    for block,role in ([] if summary_only else [('history','development'),('history','confirmation'),('sustained','evaluation')]):
        ids=list(dict.fromkeys(x['id'] for x in paths if x['block']==block and x['role']==role))
        fig,axes=plt.subplots(len(ids),4,figsize=(16,2.25*len(ids)),squeeze=False,constrained_layout=True)
        for i,identity in enumerate(ids):
            case=cases[identity]
            for j,kind in enumerate(('AP','AP','J','J')):
                ax=axes[i,j];names=['FROZEN','AP_RIDGE'] if kind=='AP' else ['FROZEN','E_CONTROL']
                for name,color,label in zip(names,('#bd433c','#247c68'),('기존 동결','진단 후보')):
                    use=[x for x in paths if x['id']==identity and x['kind']==kind and x['candidate']==name]
                    t=[x['t_s'] for x in use];values=[x['predicted'] if j%2==0 else x['residual'] for x in use]
                    ax.plot(t,values,color=color,label=label,lw=1.4)
                    if name=='FROZEN' and j%2==0:ax.plot(t,[x['observed'] for x in use],color='#202e39',label='관측',lw=1.2)
                if j%2:ax.axhline(0,color='#777',lw=.6)
                # Load envelope includes internal idle gaps; actual overlap separately marked.
                ax.axvspan(35,case['last_lane_s'],color='#e9b266',alpha=.13)
                for segment in case['actual']:
                    if '+' in segment['state']:
                        ax.axvspan(segment['start_s'],segment['end_s'],color='#557abb',alpha=.12)
                ax.set_title(identity.replace('confirmation','확인').replace('development','개발').replace('sustained','지속')+
                             (' · 경로' if j%2==0 else ' · 예측-관측 누적잔차' if kind=='J' else ' · 예측-관측 잔차'),fontsize=8)
                ax.set_ylabel('°C' if kind=='AP' else 'J');ax.set_xlabel('공통창 기준 초',fontsize=8);ax.tick_params(labelsize=7)
                if i==0:ax.legend(fontsize=7)
        fig.suptitle('실제 일정 조건부 · 주황: 부하 span(내부 유휴 포함), 파랑: 실제 병행 · 후보는 기본 미적용',fontsize=12)
        name=f'{block}_{role}_paths'
        fig.savefig(output/(name+'.png'),dpi=125);fig.savefig(output/(name+'.svg'))
        plt.close(fig);images.append(name+'.png')
        svg=output/(name+'.svg');svg.write_text('\n'.join(s.rstrip() for s in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    comparison=rows(output/'comparison.csv')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    for ax,metric,model,unit in zip(axes,('energy_mae_j','ap_mae_c'),('E_CONTROL','AP_RIDGE'),('J','°C')):
        highest=0.
        for k,name in enumerate(('FROZEN',model)):
            values=[float(next(x for x in comparison if x['block']==b and x['role']==r and x['candidate']==name)[metric]) for b,r in
                    [('history','development'),('history','confirmation'),('sustained','evaluation')]]
            bars=ax.bar(np.arange(3)+(.18 if k else -.18),values,width=.36,label='기존 동결' if k==0 else '사전 고정 진단 후보',color='#bd433c' if k==0 else '#247c68')
            highest=max(highest,max(values))
            for bar,v in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,v,format(v,'.3f' if metric.startswith('energy') else '.4f'),ha='center',va='bottom',fontsize=9)
        ax.set_ylim(0,highest*1.28)
        ax.set_xticks(range(3),['개발6','확인6\n이미 본 자료','기존 지속8\n이미 본 자료']);ax.set_ylabel(unit);ax.set_title('세션 평균 '+('에너지 절대오차' if metric.startswith('energy') else 'AP 경로 절대오차'));ax.legend(fontsize=9,loc='upper center',ncol=2)
    fig.suptitle('동일 평가 자료에서 기존/후보 비교 · 평가 결과로 재선택하지 않음')
    fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    images.insert(0,'comparison.png')
    cells=''.join('<tr>'+''.join('<td>'+html.escape(x[key])+'</td>' for key in
                  ('block','role','candidate','n','energy_mae_j','ap_mae_c','energy_worse_sessions','ap_worse_sessions','cooling_opposite'))+'</tr>' for x in comparison)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>새 이력 자료 모형 보완</title>
    <style>body{font:16px sans-serif;max-width:1300px;margin:30px auto;padding:20px}td,th{padding:8px;border:1px solid #ddd}table{border-collapse:collapse}img{max-width:100%}aside{background:#fff2ce;padding:18px}</style>
    <h1>새 이력 12세션을 활용한 모형 보완</h1>
    <aside>특정 조건에서 개선. 에너지 후보는 새 확인6에서 악화(3.913→4.694J), 기존 지속8에서 개선(4.624→4.140J).
    AP 정규화 후보는 확인6에서 개선(0.260→0.233°C)했지만 개발 선택을 통과하지 못하고 지속8 평균/최대오차도 악화.
    기본 모형·RL·strict·experiment_ready=false 유지. 전부 이미 본 자료의 사후 평가.</aside>
    <p>개발6에서 추정/선택을 봉인한 뒤 확인6+지속8을 평가했다. A 실제 일정 조건부 비용 예측이며 B 일정·응답 모형 보완이 아니다.
    에너지와 AP 출력별 후보 및 그 단순 조합을 표시한다. 조합은 별도 적합/선택 후보가 아니다. 고정g 비교는 같은 fresh target 초기입력의 보조 분석이다.</p>
    <p><a href="README.md">범위·재현</a> · <a href="session_errors.csv">100개 계산행·조건별 악화</a> · <a href="sustained_pairs.csv">4쌍 정책차이 오차</a> · <a href="candidate_freeze.json">개발 동결</a></p>
    <table><thead><tr><th>자료</th><th>역할</th><th>모형</th><th>세션</th><th>J MAE</th><th>AP MAE</th><th>J 악화</th><th>AP 악화</th><th>냉각 반대</th></tr></thead><tbody>'''+cells+'</tbody></table>'
    page+=''.join('<img src="'+f+'" alt="'+f+'">' for f in images)+'</html>'
    (output/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(saved_rows=len(rows(output/'session_errors.csv')),images=len(images),new_fits=0,device_commands=0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--summary-only',action='store_true')
    args=parser.parse_args();plot(args.output,args.summary_only)
