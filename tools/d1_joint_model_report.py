"""Postprocess the single frozen candidate, never refit or select on evaluation."""
import argparse
import csv
import html
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_joint_model_refinement as j


def rows(path):
    with path.open(encoding='utf8') as f:return list(csv.DictReader(f))


def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=150,bbox_inches='tight')
    svg=path.with_suffix('.svg');fig.savefig(svg,bbox_inches='tight')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    plt.close(fig)


def run(output):
    summary=j.m.read(output/'summary.json');freeze=j.m.read(output/'candidate_freeze.json')
    data=rows(output/'session_errors.csv');paths=rows(output/'paths.csv');pairs=rows(output/'paired_errors.csv');rolling=rows(output/'memory30_paired_errors.csv')
    identities=[r['id'] for r in data if r['mode']=='A_conditional' and r['model']=='FROZEN']
    original=j.m.read(j.m.MODEL);cases,_=j.panel();byid={c['id']:c for c in cases}
    models=[('JOINT_all9',freeze['final']['model'])]+[(f"exclude_{f['block']}",f['fit']['model']) for f in freeze['folds']]
    stability=[]
    for name,model in [('FROZEN',original)]+models:
        stability.extend(dict(fit=name,parameter=k,value=v) for k,v in model['energy_increment_w'].items())
        stability.extend(dict(fit=name,parameter=k,value=model['ap'][k]) for k in ('beta','k'))
    sensitivity=[]
    for pair in [p for p in pairs if p['model']=='FROZEN' and p['mode']=='A_conditional']:
        a,b=byid[pair['cpu']],byid[pair['par']]
        for name,model in models:
            ap_a,_,=j.m.predict(a,a['actual'],model,dict(name='FROZEN'))
            ap_b,_,=j.m.predict(b,b['actual'],model,dict(name='FROZEN'))
            energy=lambda c:j.m.energy_prediction(c,c['actual'],model,dict(name='FROZEN'),120)
            sensitivity.append(dict(cpu=a['id'],par=b['id'],fit=name,
                                    predicted_difference_j=energy(b)-energy(a),predicted_peak_difference_c=max(ap_b)-max(ap_a),
                                    observed_difference_j=float(pair['observed_difference_j']),
                                    interpretation='development block sensitivity, not confidence interval or causal policy effect'))
    j.m.table(output/'coefficient_stability.csv',stability);j.m.table(output/'policy_model_sensitivity.csv',sensitivity)
    fig,axes=plt.subplots(2,1,figsize=(14,8),sharex=True)
    for ax,metric,title in zip(axes,['abs_j','mae_c'],['120 s total energy absolute error (J)','AP path MAE (C); session-specific post35 sensor window']):
        for shift,name,color in [(-.18,'FROZEN','#2563eb'),(.18,'JOINT','#e67e22')]:
            values=[float(next(r for r in data if r['id']==i and r['mode']=='A_conditional' and r['model']==name)[metric]) for i in identities]
            ax.bar(np.arange(20)+shift,values,.36,label=name,color=color)
        ax.set_ylabel(title);ax.grid(axis='y',alpha=.2);ax.legend()
    axes[-1].set_xticks(range(20),identities,rotation=75,ha='right',fontsize=8)
    fig.suptitle('All 20 archived evaluation sessions; posthoc, no accuracy PASS');fig.tight_layout();save(fig,output/'session_errors')
    fig,axes=plt.subplots(5,4,figsize=(16,16))
    for ax,identity in zip(axes.flat,identities):
        for name,color in [('FROZEN','#2563eb'),('JOINT','#e67e22')]:
            use=[r for r in paths if r['id']==identity and r['mode']=='A_conditional' and r['model']==name and r['observed_ap_c']!='']
            ax.plot([float(r['t_s']) for r in use],[float(r['predicted_ap_c']) for r in use],color=color,label=name)
            if name=='FROZEN':ax.plot([float(r['t_s']) for r in use],[float(r['observed_ap_c']) for r in use],color='black',label='Observed')
        ax.set_title(identity,fontsize=9);ax.set_xlabel('s');ax.set_ylabel('AP C');ax.grid(alpha=.2)
        c=byid[identity];ax.axvspan(35,c['last_lane_s'],alpha=.10,color='red')
    axes.flat[0].legend(fontsize=7);fig.suptitle('Absolute AP / actual schedule A; red = load span, not continuous lane occupancy');fig.tight_layout();save(fig,output/'ap_paths')
    representatives=['confirmation_5','confirmation_180_PAR','sustained_1']
    fig,axes=plt.subplots(3,2,figsize=(13,11))
    for row,identity in enumerate(representatives):
        for name,color in [('FROZEN','#2563eb'),('JOINT','#e67e22')]:
            power=[r for r in paths if r['id']==identity and r['mode']=='A_conditional' and r['model']==name and r['observed_energy_j']!='']
            ap=[r for r in paths if r['id']==identity and r['mode']=='A_conditional' and r['model']==name and r['observed_ap_c']!='']
            axes[row,0].plot([float(r['t_s']) for r in power],[float(r['predicted_energy_j'])-float(r['observed_energy_j']) for r in power],label=name,color=color)
            axes[row,1].plot([float(r['t_s']) for r in ap],[float(r['signed_ap_c']) for r in ap],label=name,color=color)
        for ax,title in zip(axes[row],['Cumulative energy residual J, 0..120s','Signed AP residual C, observed sensor window']):
            ax.set_title(identity+' / '+title,fontsize=9);ax.axhline(0,color='black',lw=.7);ax.grid(alpha=.2);ax.set_xlabel('s');ax.legend()
            ax.axvspan(35,byid[identity]['last_lane_s'],alpha=.1,color='red')
    fig.tight_layout();save(fig,output/'residual_paths')
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for ax,source,names,title in [(axes[0],pairs,['FROZEN','JOINT'],'Full 120s pair-difference prediction error'),(axes[1],rolling,['FROZEN','MEMORY30'],'35..115s sequential-observation pair error')]:
        source=[p for p in source if p.get('mode','A_conditional')=='A_conditional'];labels=[p['cpu'] for p in source if p.get('model',p.get('method'))=='FROZEN']
        for shift,name,color in [(-.18,names[0],'#2563eb'),(.18,names[1],'#e67e22')]:
            values=[float(next(p for p in source if p['cpu']==i and p.get('model',p.get('method'))==name)['abs_difference_error_j']) for i in labels]
            ax.bar(np.arange(len(labels))+shift,values,.36,label=name,color=color)
        ax.set_xticks(range(len(labels)),labels,rotation=60,ha='right',fontsize=8);ax.set_ylabel('Absolute delta-J error');ax.set_title(title,fontsize=10);ax.legend();ax.grid(axis='y',alpha=.2)
    fig.tight_layout();save(fig,output/'paired_errors')
    def table(use,keys):
        return '<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in keys)+'</tr>' for r in use)+'</table>'
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>공동 개발자료 모형 보완</title>
    <style>body{font:16px/1.7 system-ui;max-width:1200px;margin:30px auto;padding:16px}img{max-width:100%}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ddd;padding:6px}.notice{background:#fff2dc;padding:20px}.scroll{overflow:auto}</style>
    <h1>공동 개발 9세션 계수 재추정: 일반 적용 보류</h1><p class="notice">개발 묶음 제외 검증에서 에너지·AP 선택 기준을 통과하지 못했습니다. 후보 하나를 동결해 기존 평가 20세션에서 사후 판독했습니다. 기본 모형·RL·strict·experiment_ready=false 유지. 기기 명령 0회.</p>
    <p>실제 일정 조건부 A와 저장된 예정 도착 예측 일정 B를 구분합니다. B 일정은 기존 서비스 모형 결과를 재사용하며 새 일정 생성·정책 환경 실행이 없습니다. 에너지 전체 0–120초와 AP 실제 표본창의 경계는 CSV에 있습니다.</p>
    <p>APK·준비 이력이 달라 프로토콜 전이 후보입니다. 평가 자료는 이미 열람한 자료이며 맹검 확인이 아닙니다. 35–115초 MEMORY30은 각 실행의 순차 관측을 사용하는 실행 중 보정으로, 미래 정책 선택에 사용할 수 없습니다.</p>
    <p><a href="../README.md">재현·계약</a> · <a href="../../../JOINT_MODEL_REFINEMENT_RESULTS_20261008.md">한국어 보고서</a> · <a href="session_errors.csv">세션 오차 CSV</a> · <a href="paired_errors.csv">전체 정책 차이</a> · <a href="memory30_paired_errors.csv">80초 보정 차이</a> · <a href="policy_model_sensitivity.csv">개발 묶음 민감도</a></p>'''
    text+='<h2>조건별 집계</h2><div class="scroll">'+table(summary['comparison'],['block','mode','model','n','energy_mae_j','energy_max_j','ap_mae_c','ap_max_c','opposite_cooling'])+'</div>'
    for name,title in [('session_errors','모든 평가 세션의 개선·악화'),('ap_paths','관측·원모형·후보 AP 경로'),('residual_paths','누적 에너지 잔차와 AP 잔차'),('paired_errors','정책 차이: 전체창과 순차 보정창 구분')]:
        text+=f'<h2>{title}</h2><img src="{name}.png" alt="{title}">'
    text+='<h2>모든 세션별 값</h2><div class="scroll">'+table(data,['id','block','mode','model','signed_j','abs_j','pre_signed_j','load_signed_j','post_signed_j','mae_c','max_absolute_error_c','peak_signed_error_c','ap_start_s','ap_end_s'])+'</div></html>'
    (output/'index.html').write_text(text,encoding='utf8')
    print(json.dumps(dict(figures=4,images=8,session_rows=len(data),sensitivity_rows=len(sensitivity),no_refit=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(Path(p.parse_args().output))
