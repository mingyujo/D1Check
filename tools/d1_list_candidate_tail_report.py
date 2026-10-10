"""Completed evidence to tables, six Korean figures and an offline page.

No simulation, prediction, learner update or device operation is performed.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import html
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from tools import d1_list_candidate_rl_main_report as old

NAMES={'L0':'기한 우선 리스트','Band':'Band 요청 단위 적용','Triton':'Triton 요청 단위 적용',
       'TailRule':'전체 도착 큐·공통창 규칙','currentPPO':'기존 구조 PPO','tailPPO':'보완 구조 PPO'}
STAGES={'pilot_development':'32회 개발','main_development':'64회 개발','confirmation':'새 확인'}
FILES=('01_학습과_서비스.png','02_응답과_완료.png','03_에너지와_AP.png',
       '04_조건별_성적.png','05_같은_요청_실행표.png','06_같은_요청_AP.png')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def csv_write(path,rows):
    if not rows:return
    keys=list(rows[0])
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=keys,lineterminator='\n');w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)


def datasets(run):
    return {stage:read(run/(stage+'_results.json')) for stage in STAGES if (run/(stage+'_results.json')).exists()}


def flat_rows(data,run):
    rows=[]
    for stage,result in data.items():
        for r in result['rows']:
            control=r.get('control') or {};times=sorted(control.get('decision_seconds',[]))
            p95=times[math.ceil(.95*len(times))-1]*1000 if times else None
            raw=json.loads(gzip.decompress((run/'items'/(r['identity']+'.json.gz')).read_bytes()))
            ledger=raw['result']['ledger']
            cpu=[q for q in ledger if q.get('backend')=='CPU' and 'dispatch_ns' in q]
            gpu=[q for q in ledger if q.get('backend')=='GPU' and 'dispatch_ns' in q]
            end=lambda q:q.get('lane_available_ns',120e9)
            overlap=sum(max(0,min(end(a),end(b))-max(a['dispatch_ns'],b['dispatch_ns']))/1e9 for a in cpu for b in gpu)
            rows.append(dict(stage=stage,condition=r['condition'],arrival_seed=r['case']['seed'],family=r['case']['family'],
                context=r['case']['context'],policy=r['policy'],learning_seed=r['seed'],training_episodes=r['training_episodes'],
                planned=r['planned'],completed=r['completed'],incomplete=r['incomplete'],
                urgent_failure=r['urgent_failure'],urgent_scheduled=r['urgent_scheduled'],urgent_p95_ms=r['urgent_p95_ms'],
                normal_failure=r['normal_failure'],normal_scheduled=r['normal_scheduled'],normal_mean_ms=r['normal_mean_ms'],
                normal_timely_rate=(r['normal_scheduled']-r['normal_failure'])/r['normal_scheduled'] if r['normal_scheduled'] else None,
                energy_j=r['energy_j'],peak_ap_c=r['peak_ap_c'],AP_threshold_exceedance_s=None,surface_temperature_c=None,
                phone_control_energy_j=None,decision_p95_ms=p95,decision_max_ms=max(times)*1000 if times else None,
                decision_total_s=sum(times) if times else None,native_seconds=r['native_seconds'],voluntary_wait_s=control.get('defer_seconds'),
                holds=control.get('holds'),fallbacks=control.get('fallbacks'),physical_multi_decisions=control.get('physical_multi_decisions'),
                effective_multi_decisions=control.get('effective_multi_decisions'),chosen_nonL0=control.get('chosen_nonL0'),
                chosen_nonrule=control.get('chosen_nonrule'),CPU_occupation_s=sum(end(q)-q['dispatch_ns'] for q in cpu)/1e9,
                GPU_occupation_s=sum(end(q)-q['dispatch_ns'] for q in gpu)/1e9,scheduled_parallel_lane_s=overlap,
                evidence_origin='reused32 baseline: native0' if stage=='main_development' and r['seed'] is None else 'new completed evaluation',
                identity=r['identity']))
    return rows


def aggregate(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['stage'],r['policy'],r['learning_seed'])].append(r)
    result=[]
    for (stage,policy,seed),items in groups.items():
        mean=lambda key:statistics.mean(r[key] for r in items if old.finite(r[key])) if any(old.finite(r[key]) for r in items) else None
        result.append(dict(stage=stage,policy=policy,seed=seed,conditions=len(items),planned=sum(r['planned'] for r in items),
            completed=sum(r['completed'] for r in items),incomplete=sum(r['incomplete'] for r in items),
            urgent_failure=sum(r['urgent_failure'] for r in items),normal_failure=sum(r['normal_failure'] for r in items),
            mean_urgent_p95_ms=mean('urgent_p95_ms'),mean_normal_ms=mean('normal_mean_ms'),mean_energy_j=mean('energy_j'),
            mean_peak_ap_c=mean('peak_ap_c'),mean_decision_p95_ms=mean('decision_p95_ms'),
            voluntary_wait_s=sum(r['voluntary_wait_s'] or 0. for r in items),
            cost_complete_conditions=sum(old.finite(r['energy_j']) and old.finite(r['peak_ap_c']) for r in items)))
    return result


def marginal(data):
    comparisons=[]
    for stage,result in data.items():
        refs={r['condition']:r for r in result['rows'] if r['policy']=='TailRule'}
        for r in result['rows']:
            if r['policy']!='tailPPO':continue
            b=refs[r['condition']]
            differences={k:r[k]-b[k] if old.finite(r[k]) and old.finite(b[k]) else None for k in old.KPI}
            nonworse=r['completed']==r['planned']==b['completed']==b['planned'] and all(v is not None and v<=0 for v in differences.values())
            comparisons.append(dict(stage=stage,condition=r['condition'],family=r['case']['family'],context=r['case']['context'],seed=r['seed'],
                policy='tailPPO',baseline='TailRule',all_KPI_nonworse=nonworse,
                strict_cost_improvement=nonworse and (differences['energy_j']<0 or differences['peak_ap_c']<0),
                **{'delta_'+k:v for k,v in differences.items()}))
    return comparisons


def figures(run,out,rows,reg):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    for variant in ('current','tail'):
        for seed in (11,23,37):
            p=run/f'learner_{variant}_seed{seed}.json'
            if not p.exists():continue
            log=read(p)['episode_logs'];xs=[];values=[[],[],[]]
            for i in range(0,len(log),8):
                batch=log[i:i+8];xs.append(i+len(batch))
                for j,key in enumerate(('urgent_failure','normal_failure','peak_ap_c')):
                    vv=[r['row'][key] for r in batch if old.finite(r['row'][key])]
                    values[j].append(statistics.mean(vv) if len(vv)==len(batch) else float('nan'))
            for ax,v in zip(axes,values):ax.plot(xs,v,label=('보완' if variant=='tail' else '기존')+f' seed{seed}',ls='-' if variant=='tail' else '--')
    for ax,title in zip(axes,('학습 긴급 위반 평균','학습 일반 위반 평균','학습 최고 모형 AP 평균 (°C)')):
        ax.axvline(32,color='gray',lw=.6);ax.set_title(title);ax.set_xlabel('각 learner의 학습 에피소드')
    axes[0].legend(fontsize=8);fig.tight_layout();fig.savefig(out/FILES[0],dpi=160);plt.close(fig)
    stage='confirmation' if any(r['stage']=='confirmation' for r in rows) else ('main_development' if any(r['stage']=='main_development' for r in rows) else 'pilot_development')
    agg=[r for r in aggregate(rows) if r['stage']==stage]
    labels=[NAMES[r['policy']]+(f"\nseed{r['seed']}" if r['seed'] is not None else '') for r in agg]
    for filename,keys,titles in ((FILES[1],('normal_failure','mean_urgent_p95_ms'),('일반 기한 위반 총수','조건별 긴급 P95 평균 (ms)')),
                                (FILES[2],('mean_energy_j','mean_peak_ap_c'),('Band 대비 공통120초 에너지 평균 차이 (J)','Band 대비 공통35~180초 최고 AP 평균 차이 (°C)'))):
        fig,axes=plt.subplots(1,2,figsize=(15,5.5))
        for ax,key,title in zip(axes,keys,titles):
            offset=next(r[key] for r in agg if r['policy']=='Band') if filename==FILES[2] else 0.
            ax.bar(range(len(agg)),[r[key]-offset if old.finite(r[key]) else float('nan') for r in agg],color=['#2b7a78' if r['policy'] in ('tailPPO','TailRule') else '#8191a2' for r in agg])
            if filename==FILES[2]:ax.axhline(0,color='black',lw=.7)
            ax.set_xticks(range(len(agg)),labels,rotation=55,ha='right',fontsize=8);ax.set_title(title)
        fig.suptitle(STAGES[stage]+' · 같은 예정 요청/기한 · 모형 결과');fig.tight_layout();fig.savefig(out/filename,dpi=160);plt.close(fig)
    own=[r for r in rows if r['stage']==stage and r['policy'] in ('TailRule','tailPPO')]
    bases={(r['condition'],r['policy']):r for r in rows if r['stage']==stage and r['policy'] in ('Band','L0')}
    fig,axes=plt.subplots(2,2,figsize=(14,7),sharex=True)
    for policy,seed in [('TailRule',None),('tailPPO',11),('tailPPO',23),('tailPPO',37)]:
        rr=[r for r in own if r['policy']==policy and r['learning_seed']==seed]
        label=NAMES[policy]+(f' seed{seed}' if seed else '')
        for ax,key,base in ((axes[0,0],'urgent_p95_ms','Band'),(axes[0,1],'normal_failure','Band'),(axes[1,0],'energy_j','Band'),(axes[1,1],'peak_ap_c','Band')):
            ax.plot([r['condition'] for r in rr],[r[key]-bases[(r['condition'],base)][key] if old.finite(r[key]) else float('nan') for r in rr],label=label)
    for ax,title in zip(axes.flat,('Band 대비 긴급 P95 차이 (ms)','Band 대비 일반 위반 차이','Band 대비 에너지 차이 (J)','Band 대비 최고 AP 차이 (°C)')):
        ax.axhline(0,color='black',lw=.6);ax.set_title(title);ax.set_xlabel('사전 고정 조건 번호')
    axes[0,0].legend(fontsize=8);fig.tight_layout();fig.savefig(out/FILES[3],dpi=160);plt.close(fig)
    representative=reg['representative'];condition=representative['condition']
    examples=[]
    for policy,seed in [('Band',None),('TailRule',None),('tailPPO',representative['learning_seed'])]:
        found=next((r for r in rows if r['stage']==stage and r['policy']==policy and r['learning_seed']==seed and r['condition']==condition),None)
        if found:
            item=json.loads(gzip.decompress((run/'items'/(found['identity']+'.json.gz')).read_bytes()))
            examples.append((policy,item))
    fig,axes=plt.subplots(3,1,figsize=(14,6),sharex=True)
    lo,hi=representative['window_s']
    for ax,(policy,item) in zip(axes,examples):
        for q in item['result']['ledger']:
            if 'dispatch_ns' not in q:continue
            start=max(lo,q['dispatch_ns']/1e9);end=min(hi,q.get('lane_available_ns',120e9)/1e9)
            if end>start:
                y=0 if q['backend']=='CPU' else 1
                ax.broken_barh([(start,end-start)],(y-.3,.6),facecolors='#377eb8' if q['task']=='classification' else '#4daf4a')
                response=q['arrival_ns']/1e9+q.get('response_ns',0)/1e9
                if lo<=response<=hi:ax.plot(response,y,'k.',ms=3)
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_xlim(lo,hi);ax.set_title(NAMES[policy],loc='left')
    axes[-1].set_xlabel('같은 대표 요청의 시각 (초)');fig.suptitle('lane 점유 · 파랑 분류/초록 탐지/점 응답');fig.tight_layout();fig.savefig(out/FILES[4],dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(13,4))
    for policy,item in examples:ax.plot([p[0] for p in item['curve']],[p[1] for p in item['curve']],label=NAMES[policy])
    ax.set_xlabel('시각 (초)');ax.set_ylabel('모형 AP (°C)');ax.set_title('사전 고정 대표 조건의 AP 경로 · 180초 꼬리 포함');ax.legend();fig.tight_layout();fig.savefig(out/FILES[5],dpi=160);plt.close(fig)


def publish(run,out):
    run,out=Path(run),Path(out);out.mkdir(parents=True,exist_ok=True)
    data=datasets(run);rows=flat_rows(data,run)
    reg=read(run/'registration_effective.json');agg=aggregate(rows);effects=marginal(data)
    gates={stage:{policy:{k:v for k,v in g.items() if k!='differences'} for policy,g in result['gates'].items()} for stage,result in data.items()}
    paired=[dict(stage=stage,**d) for stage,result in data.items() for g in result['gates'].values() for d in g['differences']]
    summary=dict(task='LIST-CANDIDATE-RL-TAIL-08',status='completed_analysis',rows=len(rows),aggregate=agg,gates=gates,
        consumption=read(run/'progress.json')['consumption'],budget_arithmetic_correction=read(run/'budget_arithmetic_correction.json'),
        current_phase=read(run/'progress.json')['phase'],new_learning_episode_plan=404,
        new_learning_per_variant_seed=64,learning_seed_selection=False,physical_improvement_claim=False,
        strict_or_default_changed=False,experiment_ready=False,
        marginal={stage:dict(paired=len([r for r in effects if r['stage']==stage]),
            all_KPI_nonworse=sum(r['all_KPI_nonworse'] for r in effects if r['stage']==stage),
            strict_cost_improvement=sum(r['strict_cost_improvement'] for r in effects if r['stage']==stage)) for stage in data},
        recommended_adoption=[policy for policy,g in gates.get('confirmation',{}).items() if g['promising']],
        service_guarantee_from_prediction_mask=False,independent_sampling_units='4 fresh arrival seeds; 3 service contexts are sensitivity, not independent replications')
    write(out/'summary.json',summary);csv_write(out/'evaluation.csv',rows);csv_write(out/'policy_summary.csv',agg)
    csv_write(out/'paired_differences.csv',paired);csv_write(out/'RL_added_effect.csv',effects)
    for name in ('registration.json','registration_effective.json','gate_verification.json','opportunity_verification.json',
                 'resume_verification.json','budget_arithmetic_correction.json','extension_decision.json'):
        if (run/name).exists():(out/name).write_bytes((run/name).read_bytes())
    figures(run,out,rows,reg)
    columns=('stage','policy','learning_seed','condition','family','context','completed','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>도착 큐 공통창과 PPO</title><style>body{font:15px system-ui;margin:24px;max-width:1600px}img{max-width:100%}table{border-collapse:collapse;margin:16px 0}td,th{border:1px solid #ddd;padding:6px}th{background:#eee}p{line-height:1.6}</style>'
    page+='<h1>전체 도착 큐·공통창 비용과 PPO</h1><p>동일 CPU/GPU·요청·기한·동결 모형. 새 학습 '+str(summary['consumption']['new_learning_starts'])+'회, 환경 '+str(summary['consumption']['new_environment_starts'])+'회, 기기 0회. AP는 표면 온도가 아니며 실제 제품 우위가 아니다.</p>'
    page+='<p>최종 적격: '+(' / '.join(NAMES[p] for p in summary['recommended_adoption']) if summary['recommended_adoption'] else '없음 · 기존 기준선 유지')+'. 보상값 대신 완료·기한·P95·J·AP로 판정했다.</p><p><a href="README.md">보고서와 재현</a> · <a href="evaluation.csv">전체 CSV</a> · <a href="RL_added_effect.csv">같은 후보에서 RL 추가 효과</a></p>'
    page+='<h2>어떤 판단이 바뀌었나</h2><table><thead><tr><th>구성</th><th>기존 PPO</th><th>보완 규칙·PPO</th></tr></thead><tbody id="design"><tr><td>행동</td><td>원8 물리후보</td><td>같은8후보＋현재 큐 서비스/J 예측 제한</td></tr><tr><td>비용 예측</td><td>첫 atom의 서로 다른 짧은 창</td><td>도착 전체 큐의 고정 L0 후속＋AP180/J120</td></tr><tr><td>선택</td><td>PPO · 동률L0</td><td>비학습 순위 / 같은 후보 PPO · exact동률 규칙</td></tr><tr><td>보상/계수</td><td colspan="2">동일 L0 참조/AP 주보상·J와 서비스 비용·동결 계수</td></tr></tbody></table>'
    page+=''.join('<img alt="'+html.escape(name)+'" src="'+name+'">' for name in FILES)
    page+='<h2>전체 조건</h2><p>필터 <input id="filter" aria-label="조건 필터" placeholder="새 확인 / seed11 / Band / 지속"></p><table><thead><tr>'
    page+=''.join('<th>'+label+'</th>' for label in ('자료','정책','학습seed','조건','부하','문맥','완료','일반위반','긴급 P95 ms','J120','최고 AP °C'))+'</tr></thead><tbody id="results">'
    families={'low':'낮은 부하','queue':'큐 몰림','burst':'순간 몰림','sustained':'지속 부하'}
    for row in rows:
        def cell(k):
            v=row[k]
            return STAGES[v] if k=='stage' else NAMES[v] if k=='policy' else families[v] if k=='family' else 'seed'+str(v) if k=='learning_seed' and v is not None else f'{v:.4f}' if isinstance(v,float) else '계산 불가' if v is None else str(v)
        page+='<tr>'+''.join('<td>'+html.escape(cell(k))+'</td>' for k in columns)+'</tr>'
    page+="</tbody></table><script>document.querySelector('#filter').oninput=function(){let q=this.value.toLowerCase();document.querySelectorAll('#results tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}</script></html>"
    (out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    (out/'README.md').write_text('# 도착 큐 공통창과 PPO\n\n[상세 보고서](../../LIST_CANDIDATE_RL_TAIL_20261010.md) · [오프라인 화면](index.html) · [전체 조건 CSV](evaluation.csv) · [RL 추가 효과](RL_added_effect.csv)\n\n원 결과·모형·기한·CPU/GPU 지원 보존. 기기 실행0회. 32회/64회 개발과 새48조건 확인을 분리한다. 새 학습은 두 구조×3seed 각64이며 원 actor128 연장으로 해석하지 않는다.\n\n완료 원자료 분석: `python -B -X utf8 -m tools.d1_list_candidate_tail_report --run output/list_candidate_tail_20261010_v1 --output docs/results/list_candidate_tail_01`\n',encoding='utf-8',newline='\n')
    return dict(status='PASS',rows=len(rows),summary=summary)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=publish(a.run,a.output);print(json.dumps(dict(status=result['status'],rows=result['rows'],consumption=result['summary']['consumption'],gates=result['summary']['gates']),ensure_ascii=False,indent=2))
