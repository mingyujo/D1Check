"""Analyze completed PPO evidence only. No learner/environment/device imports."""
from __future__ import annotations
import argparse,csv,gzip,html,json,math,statistics
from collections import defaultdict
from pathlib import Path

BASES=('L0','Band','Triton')
KPI=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
NAMES={'L0':'서비스 우선 리스트','GREEDY':'같은 후보 규칙 선택','EDD':'기한·완료 예측',
       'Band':'Band 요청 단위 적용','Triton':'Triton 요청 단위 적용','ListV2':'이전 열·에너지 리스트',
       'PPO64':'리스트+RL 64회','PPO128':'리스트+RL 128회'}
FAMILY={'low':'낮은 부하','queue':'큐 몰림','burst':'순간 몰림','sustained':'지속 부하'}

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def finite(x):return x is not None and math.isfinite(x)
def gate(rows,policy,conditions):
    baseline={(r['condition'],r['policy']):r for r in rows if r['policy'] in BASES}
    agents=[r for r in rows if r['policy']==policy]
    differences=[];maintenance=True;passing=[]
    for r in agents:
        for base in BASES:
            b=baseline[(r['condition'],base)]
            delta={k:r[k]-b[k] if finite(r[k]) and finite(b[k]) else None for k in KPI}
            full=r['completed']==r['planned']==b['completed']==b['planned']
            nonworse=full and all(v is not None and v<=0 for v in delta.values())
            primary=r['case']['family'] in ('low','sustained')
            absolute=not primary or all(r[k]==0 for k in ('incomplete','urgent_failure','normal_failure'))
            passed=nonworse and absolute;maintenance &= passed
            differences.append(dict(condition=r['condition'],case=r['case'],policy=policy,seed=r['seed'],baseline=base,
              full_completion=full,all_KPI_nonworse=nonworse,primary_absolute_service=absolute,cell_pass=passed,**{'delta_'+k:v for k,v in delta.items()}))
    for family in ('low','sustained'):
        subset=[d for d in differences if d['case']['family']==family]
        if maintenance and subset and all(d['cell_pass'] and (d['delta_energy_j']<0 or d['delta_peak_ap_c']<0) for d in subset):passing.append(family)
    return dict(policy=policy,conditions=conditions,learners=3,maintenance_pass=maintenance,promising_families=passing,
      promising=maintenance and bool(passing),paired_comparisons=len(differences),
      passing_cells=sum(d['cell_pass'] for d in differences),
      service_worse_cells=sum(any(d['delta_'+k] is None or d['delta_'+k]>0 for k in KPI[:4]) for d in differences),
      AP_worse_cells=sum(d['delta_peak_ap_c'] is None or d['delta_peak_ap_c']>0 for d in differences),
      J_worse_cells=sum(d['delta_energy_j'] is None or d['delta_energy_j']>0 for d in differences),differences=differences,
      epsilon=0,scope='fixed measured-coefficient simulation; not physical policy superiority')

def csv_write(p,rows):
    if not rows:return
    fields=list(rows[0]);
    with Path(p).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)

def datasets(run):
    output={}
    p=run/'evaluation_development_64.json'
    if p.exists():output['pilot_development']=read(p)['rows']
    p=run/'evaluation_main_development_128.json'
    if p.exists():
        bases=[dict(r,evidence_origin='cached pilot baseline; no new native start') for r in output['pilot_development'] if r['seed'] is None]
        output['main_development']=bases+[dict(r,evidence_origin='new terminal128 actor evaluation') for r in read(p)['rows']]
    p=run/'evaluation_confirmation_128.json'
    if p.exists():output['confirmation']=read(p)['rows']
    p=run/'evaluation_ablation_128.json'
    if p.exists():output['no_wait']=read(p)['rows']
    return output

def resource_metrics(run,stage,row):
    label='development' if stage=='pilot_development' or row.get('evidence_origin','').startswith('cached') else stage
    if stage=='no_wait':label='ablation'
    role=row['policy']+(f"_s{row['seed']}" if row['seed'] else '')
    identity=f"{label}_{role}_{row['condition']:03d}"
    ledger=json.loads(gzip.decompress((run/'items'/(identity+'.json.gz')).read_bytes()))['result']['ledger']
    cpu=[q for q in ledger if q.get('backend')=='CPU' and 'lane_available_ns' in q]
    gpu=[q for q in ledger if q.get('backend')=='GPU' and 'lane_available_ns' in q]
    overlap=lambda a,b,start,end:max(0,min(a[end],b[end])-max(a[start],b[start]))/1e9
    return dict(CPU_lane_occupied_s=sum(q['lane_available_ns']-q['dispatch_ns'] for q in cpu)/1e9,
      GPU_lane_occupied_s=sum(q['lane_available_ns']-q['dispatch_ns'] for q in gpu)/1e9,
      scheduled_parallel_lane_s=sum(overlap(a,b,'dispatch_ns','lane_available_ns') for a in cpu for b in gpu),
      simulated_parallel_execution_phase_s=sum(overlap(a,b,'execution_start_ns','output_ready_ns') for a in cpu for b in gpu))

def flat_rows(data,run):
    result=[]
    for stage,rows in data.items():
        for r in rows:
            control=r.get('control') or {};times=sorted(control.get('decision_seconds',[]))
            percentile=lambda f:times[math.ceil(f*len(times))-1]*1000 if times else None
            result.append(dict(stage=stage,condition=r['condition'],arrival_seed=r['case']['seed'],family=r['case']['family'],context=r['case']['context'],
              policy=r['policy'],learning_seed=r['seed'],training_episodes=r['training_episodes'],
              planned=r['planned'],completed=r['completed'],incomplete=r['incomplete'],
              urgent_scheduled=r.get('urgent_scheduled'),urgent_failure=r['urgent_failure'],
              urgent_violation_rate=r['urgent_failure']/r['urgent_scheduled'] if r.get('urgent_scheduled') else None,
              urgent_p95_ms=r['urgent_p95_ms'],normal_scheduled=r.get('normal_scheduled'),normal_failure=r['normal_failure'],
              normal_timely_rate=(r['normal_scheduled']-r['normal_failure'])/r['normal_scheduled'] if r.get('normal_scheduled') else None,
              normal_mean_ms=r['normal_mean_ms'],energy_j=r['energy_j'],peak_ap_c=r['peak_ap_c'],
              AP_threshold_exceedance_s=None,surface_temperature_c=None,phone_control_energy_j=None,
              decision_p50_ms=percentile(.5),decision_p95_ms=percentile(.95),decision_max_ms=max(times)*1000 if times else None,
              voluntary_defer_s=control.get('defer_seconds'),hold_selections=control.get('holds'),
              forced_waits=control.get('forced_waits'),fallbacks=control.get('fallbacks'),native_seconds=r['native_seconds'],
              evidence_origin=r.get('evidence_origin','new completed evaluation'),**resource_metrics(run,stage,r)))
    return result

def aggregate(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['stage'],r['policy'],r['learning_seed'])].append(r)
    result=[]
    for (stage,policy,seed),items in groups.items():
        mean=lambda key:statistics.mean(r[key] for r in items if finite(r[key])) if any(finite(r[key]) for r in items) else None
        result.append(dict(stage=stage,policy=policy,seed=seed,conditions=len(items),planned=sum(r['planned'] for r in items),
          completed=sum(r['completed'] for r in items),incomplete=sum(r['incomplete'] for r in items),
          urgent_failure=sum(r['urgent_failure'] for r in items),normal_failure=sum(r['normal_failure'] for r in items),
          mean_urgent_p95_ms=mean('urgent_p95_ms'),mean_normal_ms=mean('normal_mean_ms'),
          mean_energy_j=mean('energy_j') if all(finite(r['energy_j']) for r in items) else None,
          mean_peak_ap_c=mean('peak_ap_c') if all(finite(r['peak_ap_c']) for r in items) else None,
          cost_valid_conditions=sum(finite(r['energy_j']) and finite(r['peak_ap_c']) for r in items)))
    return result

def figures(run,output,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    saved=[]
    # Learning uses 8-episode update bins; no performance-based checkpoint selection.
    fig,axes=plt.subplots(1,3,figsize=(13,3.8))
    for seed in (11,23,37):
        p=run/f'learner_seed{seed}.json'
        if not p.exists():continue
        episodes=read(p)['episode_logs']
        for j,channel in enumerate(('AP','J','일반 위반')):
            values=[];xs=[]
            for i in range(0,len(episodes),8):
                batch=episodes[i:i+8];xs.append(i+len(batch))
                if j==0:
                    valid_peaks=[e['row']['peak_ap_c'] for e in batch if finite(e['row']['peak_ap_c'])]
                    values.append(statistics.mean(valid_peaks) if len(valid_peaks)==len(batch) else float('nan'))
                else:values.append(statistics.mean(e['costs'][0 if j==1 else 3] for e in batch))
            axes[j].plot(xs,values,label=f'seed{seed}');axes[j].axvline(64,color='gray',ls='--')
            axes[j].set_title(('학습 조건 평균 최고 AP (°C)','L0 대비 학습 에너지 차이 (J)','L0 대비 학습 일반 위반 증가')[j]);axes[j].set_xlabel('학습 에피소드')
    axes[0].legend();fig.tight_layout();fig.savefig(output/'01_학습_변화.png',dpi=160);plt.close(fig);saved.append('01_학습_변화.png')
    stage='confirmation' if any(r['stage']=='confirmation' for r in rows) else ('main_development' if any(r['stage']=='main_development' for r in rows) else 'pilot_development')
    agg=[r for r in aggregate(rows) if r['stage']==stage]
    labels=[NAMES[r['policy']]+(f"\nseed{r['seed']}" if r['seed'] else '') for r in agg]
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    for ax,key,title in zip(axes,('normal_failure','mean_urgent_p95_ms'),('일반 기한 위반 총수','조건별 긴급 P95 평균 (ms)')):
        ax.bar(range(len(agg)),[r[key] if finite(r[key]) else float('nan') for r in agg]);ax.set_xticks(range(len(agg)),labels,rotation=65,ha='right',fontsize=8);ax.set_title(title)
    fig.suptitle('같은 예정 요청·기한에서 서비스 비교');fig.tight_layout();fig.savefig(output/'02_응답과_기한.png',dpi=160);plt.close(fig);saved.append('02_응답과_기한.png')
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    for ax,key,title in zip(axes,('mean_energy_j','mean_peak_ap_c'),('조건별 기기 에너지 평균 (J120)','조건별 최고 모형 AP 평균 (°C)')):
        ax.bar(range(len(agg)),[r[key] if finite(r[key]) else float('nan') for r in agg]);ax.set_xticks(range(len(agg)),labels,rotation=65,ha='right',fontsize=8);ax.set_title(title)
    fig.suptitle('완료·기한 결과를 함께 해석해야 하는 모형 비용');fig.tight_layout();fig.savefig(output/'03_에너지와_AP.png',dpi=160);plt.close(fig);saved.append('03_에너지와_AP.png')
    selected=[r for r in rows if r['stage']==stage and r['policy'] in ('PPO64','PPO128')]
    bases={(r['condition'],r['policy']):r for r in rows if r['stage']==stage and r['policy'] in BASES}
    fig,axes=plt.subplots(3,2,figsize=(13,8))
    for i,seed in enumerate((11,23,37)):
        own=[r for r in selected if r['learning_seed']==seed]
        for j,key in enumerate(('normal_failure','peak_ap_c')):
            for base in BASES:axes[i,j].plot([r['condition'] for r in own],[r[key]-bases[(r['condition'],base)][key] for r in own],label=base)
            axes[i,j].axhline(0,color='black',lw=.7);axes[i,j].set_title(f'seed{seed}: '+('일반 위반 차이','최고 AP 차이 (°C)')[j]);axes[i,j].set_xlabel('사전 등록 조건 번호')
    axes[0,0].legend();fig.tight_layout();fig.savefig(output/'04_조건별_차이.png',dpi=160);plt.close(fig);saved.append('04_조건별_차이.png')
    # Representative selection is registered before held-out evaluation.
    rule=read(run/'representative_rule.json') if (run/'representative_rule.json').exists() else None
    if rule and stage=='confirmation':
        fig,axes=plt.subplots(3,1,figsize=(13,5),sharex=True)
        for ax,(role,identity) in zip(axes,rule['runs'].items()):
            p=run/'items'/(identity+'.json.gz')
            if not p.exists():continue
            ledger=json.loads(gzip.decompress(p.read_bytes()))['result']['ledger']
            for q in ledger:
                if 'dispatch_ns' not in q or 'lane_available_ns' not in q:continue
                start=max(35.,q['dispatch_ns']/1e9);end=min(55.,q['lane_available_ns']/1e9)
                if end>start:
                    y=0 if q['backend']=='CPU' else 1
                    ax.broken_barh([(start,end-start)],(y-.3,.6),facecolors='#377eb8' if q['task']=='classification' else '#4daf4a')
                    response=q['arrival_ns']/1e9+q['response_ns']/1e9
                    if 35<=response<=55:ax.plot(response,y,'k.',ms=3)
            ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(role,loc='left');ax.set_xlim(35,55)
        axes[-1].set_xlabel('같은 대표 trace의 시각 (s)')
        fig.suptitle('실제 lane 점유: 파랑 분류·초록 탐지·검은점 응답 완료');fig.tight_layout();fig.savefig(output/'05_대표_실행시간표.png',dpi=160);plt.close(fig);saved.append('05_대표_실행시간표.png')
        fig,ax=plt.subplots(figsize=(12,4))
        for role,identity in rule['runs'].items():
            p=run/'items'/(identity+'.json.gz')
            if p.exists():
                curve=json.loads(gzip.decompress(p.read_bytes()))['curve']
                ax.plot([t for t,v in curve],[v for t,v in curve],label=role)
        ax.set_xlabel('시각 (초)');ax.set_ylabel('모형 AP (°C)');ax.set_title('같은 대표 trace의 AP 경로와 180초 꼬리');ax.legend()
        fig.tight_layout();fig.savefig(output/'06_대표_AP경로.png',dpi=160);plt.close(fig);saved.append('06_대표_AP경로.png')
    return saved

def publish(run,output,plots=False):
    run,output=Path(run),Path(output);output.mkdir(parents=True,exist_ok=True)
    data=datasets(run);rows=flat_rows(data,run);gates={}
    for label,dataset in data.items():
        if label=='no_wait':continue
        policy='PPO64' if label=='pilot_development' else 'PPO128'
        gates[label]=gate(dataset,policy,24 if 'development' in label else 48)
        write(run/(label+'_gate.json'),gates[label])
    csv_write(output/'evaluation.csv',rows);csv_write(output/'policy_summary.csv',aggregate(rows))
    comparisons=[dict(stage=k,**d) for k,g in gates.items() for d in g['differences']]
    csv_write(output/'paired_differences.csv',comparisons)
    progress=read(run/'progress.json')
    effective=run/'registration_effective.json'
    summary=dict(task='LIST-CANDIDATE-RL-TRAIN-MAIN-05',registered=read(effective if effective.exists() else run/'registration.json'),
      original_registration=read(run/'registration.json'),
      resume=read(run/'resume_verification.json'),representation=read(run/'chronological_representation_certificate.json'),
      consumption=progress['consumption'],gates={k:{x:v for x,v in g.items() if x!='differences'} for k,g in gates.items()},
      aggregate=aggregate(rows),rows=len(rows),physical_improvement_claim=False,final_policy_selected=False,
      current_phase=progress['phase'],deadline_and_thermal_limit_invented=False,
      AP_threshold_not_defined=True,phone_control_energy_unmeasured=True,surface_temperature_unsupported=True)
    images=figures(run,output,rows) if plots and rows else [p.name for p in sorted(output.glob('0[1-6]_*.png'))]
    summary['figures']=images;write(output/'summary.json',summary)
    table='<table><thead><tr>'+''.join('<th>'+x+'</th>' for x in ('단계','조건','부하','정책·학습seed','완료/예정','긴급위반','일반위반','긴급P95 ms','J120','최고AP °C'))+'</tr></thead><tbody>'
    for r in rows:
        label=NAMES[r['policy']]+(f" seed{r['learning_seed']}" if r['learning_seed'] else '')
        values=[r['stage'],r['condition'],FAMILY[r['family']],label,f"{r['completed']}/{r['planned']}",r['urgent_failure'],r['normal_failure'],r['urgent_p95_ms'],r['energy_j'],r['peak_ap_c']]
        table+='<tr>'+''.join('<td>'+html.escape('계산 불가' if v is None else f'{v:.3f}' if isinstance(v,float) else str(v))+'</td>' for v in values)+'</tr>'
    table+='</tbody></table>'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>리스트 + RL 학습 비교</title><style>body{font:15px system-ui;margin:24px}table{border-collapse:collapse}td,th{padding:6px;border:1px solid #ddd}th{position:sticky;top:0;background:#eee}img{max-width:100%}.note{padding:12px;background:#fff3da}</style><h1>리스트 + RL: 64회 → 128회</h1>'
    page+='<p class="note">동결 모형의 CPU/GPU 시뮬레이션 비교다. 기한 위반을 무시한 에너지 절감과 실제 제품 우월성을 주장하지 않는다. AP는 같은 모형 채널이며 표면온도·기기 제어 에너지는 미지원이다.</p>'
    page+='<p><a href="README.md">보고서</a> · <a href="summary.json">판정·예산·재개 검증</a> · <a href="evaluation.csv">전체 CSV</a> · <a href="paired_differences.csv">대응 차이</a></p><p>필터: <input id="filter" placeholder="정책·단계·seed·부하"></p>'
    page+=''.join('<p><img src="'+html.escape(name)+'"></p>' for name in images)+table
    page+="<script>document.querySelector('#filter').oninput=function(){let q=this.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}</script></html>"
    (output/'index.html').write_text(page,encoding='utf-8',newline='\n')
    return dict(status='PASS',stages=list(data),rows=len(rows),gates=summary['gates'],consumption=summary['consumption'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);p.add_argument('--plots',action='store_true');args=p.parse_args()
    print(json.dumps(publish(args.run,args.output,args.plots),ensure_ascii=False,indent=2))
