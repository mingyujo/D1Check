"""Replay completed post-main diagnosis and two selector development results."""
import argparse,csv,html,json,statistics
from pathlib import Path

NAMES={'L0':'서비스 우선 리스트','Band':'Band 요청 단위 적용','Triton':'Triton 요청 단위 적용','GREEDY':'기존 두head 규칙',
 'PPO128':'리스트+RL128','LIST_PPO128_POSTENCODE_NOWAIT_DIAGNOSTIC_V1':'입력 보존 대기제거',
 'LIST_SERVICE_EQUAL_WORK_BOUNDED_D_WAIT_PC_V1':'같은 작업량 비용 비교 V1','LIST_SERVICE_EQUAL_WORK_BACKLOG_PC_V2':'탐지 적체 보호 V2'}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def csv_write(p,rows):
    with Path(p).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def publish(run,out):
    run,out=Path(run),Path(out);out.mkdir(parents=True,exist_ok=True)
    prior=run.parent/'list_candidate_rl_train_main_20261010_v1'
    bases=[r for r in read(prior/'evaluation_development_64.json')['rows'] if r['policy'] in ('L0','Band','Triton','GREEDY') and r['seed'] is None]
    allrows=[*bases,*read(prior/'evaluation_main_development_128.json')['rows'],*read(run/'nowait_results.json')['rows']]
    for name in ('candidate_development_results.json','backlog_development_results.json'):
        allrows.extend(r for r in read(run/name)['rows'] if r['policy'].startswith('LIST_SERVICE_EQUAL'))
    flat=[dict(condition=r['condition'],arrival_seed=r['case']['seed'],family=r['case']['family'],context=r['case']['context'],policy=r['policy'],learning_seed=r['seed'],planned=r['planned'],completed=r['completed'],incomplete=r['incomplete'],urgent_failure=r['urgent_failure'],normal_failure=r['normal_failure'],urgent_p95_ms=r['urgent_p95_ms'],normal_mean_ms=r['normal_mean_ms'],energy_j=r['energy_j'],peak_ap_c=r['peak_ap_c'],defer_s=(r.get('control') or {}).get('defer_seconds'),new_native=(r['policy'].startswith('LIST_SERVICE_EQUAL') or r['policy'].startswith('LIST_PPO128_POSTENCODE'))) for r in allrows]
    csv_write(out/'evaluation.csv',flat)
    groups={}
    for r in flat:groups.setdefault((r['policy'],r['learning_seed']),[]).append(r)
    aggregates=[]
    for (policy,seed),rr in groups.items():
        aggregates.append(dict(policy=policy,seed=seed,conditions=len(rr),planned=sum(r['planned'] for r in rr),completed=sum(r['completed'] for r in rr),urgent_failure=sum(r['urgent_failure'] for r in rr),normal_failure=sum(r['normal_failure'] for r in rr),urgent_p95_mean_ms=statistics.mean(r['urgent_p95_ms'] for r in rr),energy_mean_j=statistics.mean(r['energy_j'] for r in rr),peak_ap_mean_c=statistics.mean(r['peak_ap_c'] for r in rr),defer_sum_s=sum(r['defer_s'] or 0 for r in rr)))
    csv_write(out/'policy_summary.csv',aggregates)
    gates={n:read(run/(n+'_gate.json')) for n in ('nowait','candidate_development','backlog_development')}
    differences=[dict(stage=stage,condition=r['condition'],seed=r['seed'],baseline=r['baseline'],family=r['case']['family'],context=r['case']['context'],**{k:v for k,v in r.items() if k.startswith('delta_')}) for stage,g in gates.items() for r in g['differences']]
    csv_write(out/'paired_differences.csv',differences)
    summary=dict(task='LIST-CANDIDATE-RL-DEVELOP-07',consumption=read(run/'progress.json')['consumption'],aggregate=aggregates,gates={k:{a:v for a,v in g.items() if a!='differences'} for k,g in gates.items()},rows=len(flat),new_native_rows=120,reused_rows=len(flat)-120,new_learning_starts=0,device_commands=0,policy_selected=False,fresh_confirmation=False)
    write(out/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    labels=[NAMES[r['policy']]+(f"\nseed{r['seed']}" if r['seed'] else '') for r in aggregates]
    for name,keys,titles in [('01_서비스_회복.png',('normal_failure','urgent_p95_mean_ms'),('일반 기한 위반 합','조건별 긴급 P95 평균 (ms)')),('02_비용과_상충.png',('energy_mean_j','peak_ap_mean_c'),('공통120초 기기 에너지 평균 (J)','최고 모형 AP 평균 (°C)'))]:
        fig,axes=plt.subplots(1,2,figsize=(16,6))
        for ax,key,title in zip(axes,keys,titles):
            ax.bar(range(len(aggregates)),[r[key] for r in aggregates]);ax.set_xticks(range(len(aggregates)),labels,rotation=65,ha='right',fontsize=8);ax.set_title(title)
        fig.suptitle('같은 개발24조건·전량1584: 개선과 상충을 함께 표시');fig.tight_layout();fig.savefig(out/name,dpi=160);plt.close(fig)
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>RL128 이후 서비스 보완</title><style>body{font:15px system-ui;margin:24px}img{max-width:100%}table{border-collapse:collapse}th,td{border:1px solid #ddd;padding:6px}th{background:#eee}</style><h1>RL128 이후 서비스 보완</h1><p>120환경·실행실패0·7920/7920완료·학습/기기0. 모두 개발 진단이며 새 독립 확인이 아니다.</p><p>탐지 적체 보호 V2는 서비스와 에너지를 보존했지만 Band/L0 대비 AP악화9조건이 남아 미채택이다. 모형 결과를 제품 전체·실물 표면온도 개선으로 해석하지 않는다.</p><p><a href="README.md">보고서</a> · <a href="evaluation.csv">전체 CSV</a> · <a href="summary.json">판정</a></p><img src="01_서비스_회복.png"><img src="02_비용과_상충.png"><p>필터 <input id="filter"></p><table><thead><tr>'
    columns=('policy','learning_seed','condition','family','context','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
    page+=''.join('<th>'+s+'</th>' for s in ('정책','학습seed','조건','부하','문맥','일반위반','긴급P95 ms','J120','최고AP °C'))+'</tr></thead><tbody>'
    for row in flat:
        page+='<tr>'+''.join('<td>'+html.escape(NAMES[row[k]] if k=='policy' else 'seed'+str(row[k]) if k=='learning_seed' and row[k] is not None else f'{row[k]:.3f}' if isinstance(row[k],float) else str(row[k]))+'</td>' for k in columns)+'</tr>'
    page+="</tbody></table><script>document.querySelector('#filter').oninput=function(){let q=this.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}</script></html>"
    (out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    return dict(status='PASS',rows=len(flat),aggregates=aggregates)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(publish(a.run,a.output),ensure_ascii=False,indent=2))
