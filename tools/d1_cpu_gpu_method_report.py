"""Read sealed pilot schedules; KPI/paired comparisons and coefficient stress."""
from __future__ import annotations
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import html
import json
from pathlib import Path
import statistics
from tools import d1_edd_ect_residual_report as compare

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/cpu_gpu_method_01'
LOCAL=ROOT/'output/cpu_gpu_method_20261008_v1'
BASE='IE_EDD_ECT_LANE_PC_V1';SHARED='SHARED_EFT';BAND='BAND_HEFT_WHOLE_REQUEST_ADAPT_V1';TRITON='TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1'
RULE='EDD_ECT_ENERGY_AP_GUARD_PC_V1'
LABELS={BAND:'Band 요청 적용',TRITON:'Triton 요청 적용',SHARED:'공용 EFT 기준',BASE:'기한 우선 ECT',RULE:'기한·AP 검사 에너지 규칙'}
LABELS.update({f'{v}_seed{s}':f'{"현재" if v=="C" else "보완"} PPO · {s}' for v in ('C','E') for s in (11,23,37)})
EPS=1e-9


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8',newline='\n')
def csv_write(path,rows):
    with Path(path).open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)


def load(split):
    receipts=[json.loads(line) for line in (LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()]
    result=[]
    for path in sorted((LOCAL/'items').glob(split+'_*.json.gz')):
        item=json.loads(gzip.decompress(path.read_bytes()));row=item['row']
        identity=f'{split}/{row["policy"]}/'+str(int(path.name.split('_')[-1].split('.')[0]))
        records=[r for r in receipts if r['event']=='completed' and r['identity']==identity]
        assert len(records)==1 and records[0]['artifact']==sha(path),'unsealed evaluation item'
        result.append(item)
    assert len(result)==(132 if split=='validation' else 264)
    return result


def eligibility(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};results=[]
    for policy in LABELS:
        group=[r for r in rows if r['policy']==policy];strict=[];service=[]
        for r in group:
            primary=r['family'] in ('low','sustained')
            refs=[by[(r['seed'],r['family'],r['context'],p)] for p in (SHARED,BAND)]
            ps=[compare.compare(r,ref) for ref in refs]
            strict.append(all(p['nonworse'] and (not primary or p['all_deadlines_met']) for p in ps))
            service.append(all(p['service_preserved'] and (not primary or p['all_deadlines_met']) for p in ps))
        energy_gain=any(r['energy_j']<by[(r['seed'],r['family'],r['context'],SHARED)]['energy_j']-EPS and
            r['energy_j']<by[(r['seed'],r['family'],r['context'],BAND)]['energy_j']-EPS for r in group)
        results.append(dict(policy=policy,conditions=len(group),service_good=sum(service),strict_good=sum(strict),
            all_conditions_nonworse=all(strict),energy_gain_somewhere=energy_gain,eligible=all(strict) and energy_gain))
    return results


def report():
    done=read(BUNDLE/'completion.json');assert done['status']=='completed'
    validation=load('validation');final=load('final');rows=[i['row'] for i in final];vrows=[i['row'] for i in validation]
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows}
    pairs=[]
    for r in rows:
        for base in (BASE,SHARED,BAND,TRITON):
            if r['policy']==base:continue
            ref=by[(r['seed'],r['family'],r['context'],base)]
            pairs.append(dict(seed=r['seed'],family=r['family'],context=r['context'],policy=r['policy'],baseline=base,**compare.compare(r,ref)))
    summaries=[]
    for scope,families in [('all',('low','queue','burst','sustained')),('primary',('low','sustained'))]:
        for p in LABELS:
            rs=[r for r in rows if r['policy']==p and r['family'] in families]
            timings=[r['decision_host_max_ms'] for r in rs if r['decision_host_max_ms'] is not None]
            summaries.append(dict(scope=scope,policy=p,conditions=len(rs),planned=sum(r['planned'] for r in rs),completed=sum(r['completed'] for r in rs),
                urgent_failures=sum(r['urgent_service_failure'] for r in rs),normal_failures=sum(r['normal_service_failure'] for r in rs),
                absolute_deadline_conditions=sum(r['deadline_met']==r['planned'] for r in rs),
                mean_urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in rs),mean_normal_mean_ms=statistics.mean(r['normal_mean_ms'] for r in rs),
                mean_energy_j=statistics.mean(r['energy_j'] for r in rs),mean_peak_ap_c=statistics.mean(r['peak_ap_c'] for r in rs),
                total_host_wall_s=sum(r['host_wall_s'] for r in rs),mean_judgment_host_ms=statistics.mean(timings) if timings else None))
    validation_eligible=eligibility(vrows);final_eligible=eligibility(rows)
    rl_promising={v:all(next(r for r in validation_eligible if r['policy']==f'{v}_seed{s}')['eligible'] for s in (11,23,37)) for v in ('C','E')}
    selected=[r['policy'] for r in final_eligible if r['eligible']]
    if selected:
        selected.sort(key=lambda p:next(r['mean_energy_j'] for r in summaries if r['scope']=='primary' and r['policy']==p))
    recommendation=dict(selected_new_policy=selected[0] if selected else None,rl_all_seeds_validation_promising=rl_promising,
        strict_selection='full work/service/P95/model AP/J nonworse versus Shared and Band on every condition; primary absolute deadlines; energy improvement',
        fallback='keep current strong expected-completion baseline; no automatic default or strict-support change',
        no_global_optimality=True,no_physical_savings_claim=True)
    chosen=read(BUNDLE/'method_choice_after_validation.json')['chosen_policy']
    final_check=next((r for r in final_eligible if r['policy']==chosen),None)
    recommendation.update(chosen_from_validation=chosen,final_confirmation_nonworse=bool(final_check and final_check['all_conditions_nonworse']),
        confirmed_method=chosen if final_check and final_check['all_conditions_nonworse'] else None,
        fallback_choice_changes_after_final=False)
    csv_write(BUNDLE/'validation_results.csv',vrows);csv_write(BUNDLE/'final_results.csv',rows)
    csv_write(BUNDLE/'pairs.csv',pairs);csv_write(BUNDLE/'policy_summary.csv',summaries)
    csv_write(BUNDLE/'validation_eligibility.csv',validation_eligible);csv_write(BUNDLE/'final_eligibility.csv',final_eligible)
    write(BUNDLE/'selection.json',recommendation)
    train=[]
    for v in ('C','E'):
        for seed in (11,23,37):
            obj=read(LOCAL/f'{v}_seed{seed}_done.json')
            rs=obj['rows']
            train.append(dict(variant=v,learning_seed=seed,episodes=obj['cursor'],updates=obj['updates'],
                planned=sum(r['planned'] for r in rs),completed=sum(r['completed'] for r in rs),
                informative=sum(r['informative'] for r in rs),host_wall_s=sum(r['host_wall_s'] for r in rs),
                mean_energy_j=statistics.mean(r['energy_j'] for r in rs),mean_peak_ap_c=statistics.mean(r['peak_ap_c'] for r in rs),
                mean_urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in rs)))
    csv_write(BUNDLE/'training_summary.csv',train)
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),final_rows=264,validation_rows=132,policies=11,
        training=train,policy_summaries=summaries,selection=recommendation,consumption=done['consumption'],
        planned=sum(r['planned'] for r in rows),completed=sum(r['completed'] for r in rows),
        uncertainty='two final trace seeds, correlated three service contexts, three learning seeds; insufficient independent phone repetitions for narrow confidence intervals')
    write(BUNDLE/'summary.json',summary)
    reps={p:next(i for i in final if i['row']['policy']==p and i['row']['seed']==711020003 and i['row']['family']=='queue' and i['row']['context']=='mean') for p in LABELS}
    write(BUNDLE/'representatives.json',reps)
    coefficient_sensitivity(final)
    plots(rows,pairs,summaries,reps);dashboard(rows,summaries,summary)
    return summary


def coefficient_sensitivity(items):
    from tools import d1_policy_coefficient_sensitivity as sensitivity
    initial=read(ROOT/'docs/results/external_rules_02/inputs.json')['initial'];models=sensitivity.models();scores=[]
    for item in items:
        row=item['row']
        if row['seed']!=711020003:continue # fixed first final seed, all cases/policies
        if row['completed']!=row['planned']:continue
        segments=sensitivity.segments(item['ledger'])
        for name,model in models:
            costs=sensitivity.j.m.base.costs(segments,initial,list(range(35,181)),model,180.)
            scores.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],model=name,
                energy_j=costs['whole_120s_j'],peak_ap_c=max(costs['ap_path']),physical_saving_verified=False))
    if scores:csv_write(BUNDLE/'coefficient_sensitivity.csv',scores)
    write(BUNDLE/'sensitivity_contract.json',dict(selection='first final seed711020003, all four families and contexts, all policies',
        model_names=[name for name,_ in models],freeze_sha256=sha(sensitivity.FREEZE),original_model_sha256=sha(sensitivity.j.m.MODEL),
        scope='fixed simulated schedules, empirically fitted rejected development variants; no recalibration, no changed-model policy replay, no confidence interval',new_environment_starts=0))


def plots(rows,pairs,summaries,reps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False})
    out=BUNDLE/'figures';out.mkdir(exist_ok=True)
    allrows={r['policy']:r for r in summaries if r['scope']=='all'}
    fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for i,p in enumerate(LABELS):
        axes[0].bar(i,allrows[p]['mean_urgent_p95_ms']);axes[1].bar(i,allrows[p]['normal_failures'])
    for ax in axes:ax.set_xticks(range(11),list(LABELS.values()),rotation=55,ha='right');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('조건별 긴급 P95 평균 (ms)');axes[1].set_ylabel('일반 기한 실패 (건)');fig.suptitle('같은 확인24조건 — 완료량과 함께 평가')
    fig.savefig(out/'01_응답과기한.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for ax,base in zip(axes,(SHARED,BAND)):
        for p in LABELS:
            if p==base:continue
            ps=[r for r in pairs if r['policy']==p and r['baseline']==base and r['family'] in ('low','sustained')]
            ax.scatter([r['delta_energy_j'] for r in ps],[r['delta_peak_ap_c'] for r in ps],label=LABELS[p],alpha=.55)
        ax.axhline(0,color='grey',lw=.8);ax.axvline(0,color='grey',lw=.8);ax.grid(alpha=.2);ax.set_title(LABELS[base]+' 대비');ax.set_xlabel('기기 전체 J 차이')
    axes[0].set_ylabel('최고 모형 AP 차이 (°C)');axes[1].legend(fontsize=7,loc='upper left',bbox_to_anchor=(1,1))
    fig.suptitle('주12조건의 비용 차이 — 비용 감소도 서비스 guard 필요');fig.savefig(out/'02_에너지와AP차이.png',dpi=160);plt.close(fig)
    policies=[BAND,SHARED,BASE,RULE,'C_seed11','E_seed11']
    fig,axes=plt.subplots(6,1,figsize=(12,11),sharex=True,layout='constrained')
    for ax,p in zip(axes,policies):
        for r in reps[p]['ledger']:
            if 'dispatch_ns' not in r:continue
            start=r['dispatch_ns']/1e9;end=r.get('lane_available_ns',120e9)/1e9;y=0 if r['backend']=='CPU' else 1
            ax.broken_barh([(start,end-start)],(y-.3,.6),facecolors='#397db8' if r['priority']=='urgent' else '#ee9d44')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[p],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(35,65);axes[-1].set_xlabel('공통 시간 (초)');fig.suptitle('첫 확인seed queue/mean — 막대는 전체 lane 점유')
    fig.savefig(out/'03_대표실행시간표.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
    for p in policies:ax.plot(reps[p]['curves']['ap_times_s'],reps[p]['curves']['ap_path'],label=LABELS[p])
    ax.set_xlabel('공통 시간 (초)');ax.set_ylabel('모형 AP (°C)');ax.grid(alpha=.2);ax.legend();ax.set_title('같은 대표 조건의 AP 경로 — 표면온도 아님')
    fig.savefig(out/'04_대표AP경로.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,6),layout='constrained')
    conditions=sorted({(r['seed'],r['family'],r['context']) for r in rows});by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows}
    values=[]
    for p in LABELS:
        line=[]
        for seed,f,c in conditions:
            row=by[seed,f,c,p];ref=[by[seed,f,c,b] for b in (SHARED,BAND)];ps=[compare.compare(row,b) for b in ref]
            line.append(2 if all(q['nonworse'] and q['all_deadlines_met'] for q in ps) else 1 if all(q['service_preserved'] for q in ps) else 0)
        values.append(line)
    from matplotlib.colors import ListedColormap
    ax.imshow(values,aspect='auto',vmin=0,vmax=2,cmap=ListedColormap(['#e8bcbc','#e7dfb1','#b5dbc6']))
    ax.set_yticks(range(11),list(LABELS.values()));ax.set_xticks(range(24),[f'{str(s)[-1]} {f[:2]} {c[:1]}' for s,f,c in conditions],rotation=90)
    ax.set_title('조건별 두 강한 기준 대비 · 초록 전기한/비악화 · 노랑 서비스 유지 · 빨강 서비스 악화')
    fig.savefig(out/'05_조건별판정지도.png',dpi=160);plt.close(fig)


def dashboard(rows,summaries,summary):
    def table(data,fields):
        head=''.join('<th>'+html.escape(label)+'</th>' for _,label in fields);body=''
        for r in data:
            cells=[]
            for key,_ in fields:
                v=LABELS.get(r[key],r[key]) if isinstance(r[key],str) else r[key]
                if isinstance(v,float):v=f'{v:.6f}'
                cells.append('<td>'+html.escape(str(v))+'</td>')
            body+='<tr>'+''.join(cells)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    body=f'<h1>CPU/GPU 스케줄링 방법론 파일럿</h1><p>같은 PPO · 두 설계 · 각각3학습seed×32episode. 확인24조건×11정책={len(rows)}행. 원단위 KPI로 판정합니다.</p>'
    body+='<p><a href="README.md">선정 보고서</a> · <a href="../../CPU_GPU_METHOD_IMPLEMENTATION_AUDIT_20261008.md">구현 감사</a> · <a href="final_results.csv">전체 CSV</a> · <a href="pairs.csv">대응 차이</a></p>'
    body+='<p>AP는 모형 채널, 표면온도와 안전한도 초과시간은 계산 불가. 32episode는 수렴 완료 판정이 아닙니다.</p><input id="filter" placeholder="정책/부하 검색">'
    body+=table(summaries,[('scope','범위'),('policy','정책'),('completed','완료'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('mean_urgent_p95_ms','긴급 P95 ms'),('mean_energy_j','기기 J'),('mean_peak_ap_c','AP °C')])
    body+=table(rows,[('seed','trace seed'),('family','부하'),('context','문맥'),('policy','정책'),('planned','예정'),('completed','완료'),('urgent_p95_ms','긴급 P95 ms'),('normal_service_failure','일반 실패'),('energy_j','기기 J'),('peak_ap_c','AP °C')])
    for p in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CPU/GPU 방법론 선정</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;color:#243142;max-width:1450px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px;text-align:left}th{background:#edf3f8}.scroll{overflow:auto;margin:16px 0}input{padding:10px;width:300px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')


if __name__=='__main__':
    r=report();print(json.dumps({k:v for k,v in r.items() if k not in ('policy_summaries','training')},ensure_ascii=False,indent=2))
