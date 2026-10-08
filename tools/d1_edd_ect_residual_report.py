"""Analyze sealed prototype files, figures and offline dashboard. No engine calls."""
from __future__ import annotations
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import html
import json
from pathlib import Path
import statistics
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/edd_ect_residual_prototype_01'
LOCAL=ROOT/'output/edd_ect_residual_prototype_20261008_v1'
BASE='IE_EDD_ECT_LANE_PC_V1'
SHARED='SHARED_EFT'
BAND='BAND_HEFT_WHOLE_REQUEST_ADAPT_V1'
PRIOR='EDD_ECT_FEASIBILITY_PRIOR_V1'
GREEDY='EDD_ECT_THERMAL_GREEDY_V1'
LABELS={BASE:'기한 우선 + ECT',SHARED:'공용 EFT 기준',BAND:'Band 요청 적용',PRIOR:'기한 검사 + 기본 판단',GREEDY:'기한 검사 + 열 규칙'}
EPS=1e-9


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8',newline='\n')
def csv_write(path,rows):
    with Path(path).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)


def compare(row,ref):
    full=(row['completed']==row['planned'] and row['energy_full_work_eligible']
          and ref['completed']==ref['planned'] and ref['energy_full_work_eligible'])
    metrics=['energy_j','peak_ap_c','urgent_p95_ms']
    finite=all(row[k] is not None and ref[k] is not None for k in metrics)
    service=full and finite and row['urgent_service_failure']<=ref['urgent_service_failure'] and row['normal_service_failure']<=ref['normal_service_failure'] and row['urgent_p95_ms']<=ref['urgent_p95_ms']+EPS
    d={k:row[k]-ref[k] if row[k] is not None and ref[k] is not None else None for k in metrics+['normal_mean_ms']}
    absolute=row['deadline_met']==row['planned'] and ref['deadline_met']==ref['planned']
    nonworse=service and d['energy_j']<=EPS and d['peak_ap_c']<=EPS
    return dict(service_preserved=service,all_deadlines_met=absolute,nonworse=nonworse,
        heat_gain=nonworse and d['peak_ap_c'] < -EPS,
        joint_gain=nonworse and d['peak_ap_c'] < -EPS and d['energy_j'] < -EPS,
        absolute_heat_gain=nonworse and absolute and d['peak_ap_c'] < -EPS,
        delta_energy_j=d['energy_j'],delta_peak_ap_c=d['peak_ap_c'],delta_urgent_p95_ms=d['urgent_p95_ms'],delta_normal_mean_ms=d['normal_mean_ms'])


def gain_signal(row,refs,primary):
    ps={r['policy']:compare(row,r) for r in refs}
    good=primary and all(p['nonworse'] and p['all_deadlines_met'] for p in ps.values())
    return bool(good and ps[SHARED]['heat_gain'] and ps[BAND]['heat_gain'] and
        (ps[BASE]['delta_energy_j'] < -EPS or ps[BASE]['delta_peak_ap_c'] < -EPS))


def physical(item,point):
    rows=item['result']['ledger']
    next_event=min((t['at_ns'] for t in item['result']['transitions'] if t['at_ns']>point),default=point+1)
    immediate=sorted((r['id'],r.get('backend')) for r in rows if r.get('dispatch_ns')==point)
    occupancy=sorted((r['id'],r.get('backend')) for r in rows if r.get('dispatch_ns',float('inf'))<=next_event and r.get('lane_available_ns',120e9)>next_event)
    return dict(dispatch_set=immediate,next_event_ns=next_event,next_occupancy=occupancy)


def load():
    done=read(BUNDLE/'completion.json')
    assert done['status']=='completed' and done['results_sha256']==sha(BUNDLE/'results.csv')
    items=[];by={}
    for identity,h in done['item_hashes'].items():
        path=LOCAL/'items'/f'{identity}.json.gz'
        assert sha(path)==h
        item=json.loads(gzip.decompress(path.read_bytes()));items.append(item)
        row=item['row'];by[(row['family'],row['context'],row['policy'])]=item
    assert len(items)==len(by)==60
    return done,items,by


def report():
    done,items,by=load();rows=[i['row'] for i in items];pairs=[];witnesses=[]
    for item in items:
        row=item['row']
        if row['policy'] not in (PRIOR,GREEDY):continue
        refs=[by[(row['family'],row['context'],p)]['row'] for p in (BASE,SHARED,BAND)]
        for ref in refs:pairs.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],baseline=ref['policy'],**compare(row,ref)))
        if gain_signal(row,refs,row['family'] in ('low','sustained')):
            witnesses.append(dict(family=row['family'],context=row['context'],policy=row['policy']))
    branches=read(BUNDLE/'branches.json');physical_branches=[]
    for b in branches:
        if not b['record']:continue
        point=b['record']['now_ns']
        arm=[json.loads(gzip.decompress((LOCAL/'items'/(b[k]+'.json.gz')).read_bytes())) for k in ('base_identity','alt_identity')]
        states=[physical(item,point) for item in arm]
        distinct=states[0]!=states[1]
        # Require actual dispatch-set/occupancy difference, not time alone.
        distinct=states[0]['dispatch_set']!=states[1]['dispatch_set'] or states[0]['next_occupancy']!=states[1]['next_occupancy']
        refs=[by[(b['family'],b['context'],p)]['row'] for p in (BASE,SHARED,BAND)]
        eligible=gain_signal(arm[1]['row'],refs,b['family'] in ('low','sustained'))
        physical_branches.append(dict(seed=b['seed'],family=b['family'],context=b['context'],at_ns=point,
            actual_physical_difference=distinct,base_state=states[0],alt_state=states[1],gate_c_witness=eligible))
        if eligible:witnesses.append(dict(family=b['family'],context=b['context'],policy='causal first alternative'))
    summaries=[]
    for scope,families in [('all',('low','queue','burst','sustained')),('primary',('low','sustained'))]:
        for policy in LABELS:
            group=[r for r in rows if r['policy']==policy and r['family'] in families]
            summaries.append(dict(scope=scope,policy=policy,conditions=len(group),planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),
                urgent_failures=sum(r['urgent_service_failure'] for r in group),normal_failures=sum(r['normal_service_failure'] for r in group),
                all_deadline_conditions=sum(r['deadline_met']==r['planned'] for r in group),
                mean_urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in group),
                mean_normal_ms=statistics.mean(r['normal_mean_ms'] for r in group),mean_energy_j=statistics.mean(r['energy_j'] for r in group),
                mean_peak_ap_c=statistics.mean(r['peak_ap_c'] for r in group),
                multi_physical_decisions=sum(r['multi_physical_decisions'] for r in group),
                cool_wait_decisions=sum(r['cool_wait_decisions'] for r in group),forced_decisions=sum(r['forced_decisions'] for r in group),
                projections=sum(r['projection_calls'] for r in group),projection_seconds=sum(r['projection_seconds'] for r in group)))
    csv_write(BUNDLE/'pairs.csv',pairs);csv_write(BUNDLE/'policy_summary.csv',summaries)
    write(BUNDLE/'physical_branches.json',physical_branches)
    gate=dict(A='NONLEARNING_SEMANTICS_PASS_RL_ARCHIVE_NOT_IMPLEMENTED',
        B='PASS' if any(b['actual_physical_difference'] for b in physical_branches) else 'FAIL',
        C='PASS' if witnesses else 'FAIL',D='PROTOTYPE_PROFILE_COMPLETE_TRAINING_CONTRACT_NOT_REGISTERED',E='NOT_RUN',
        training_allowed=False,training_episodes=0,witnesses=witnesses,
        decision='NO_TRAINING_NO_C_SIGNAL' if not witnesses else 'C_SIGNAL_ONLY_REGISTER_D_BEFORE_TRAINING')
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),conditions=12,policies=5,comparison_rows=60,
        planned=sum(r['planned'] for r in rows),completed=sum(r['completed'] for r in rows),
        branch_conditions=len(physical_branches),different_actual_branches=sum(b['actual_physical_difference'] for b in physical_branches),
        gates=gate,consumption=done['consumption'],policy_summaries=summaries,
        limits=['already consumed synthetic development inputs','model AP not surface temperature','no physical gain inference from small deltas','no trained actor or mobile controller overhead'],
        baseline_agreement={p:sum(by[(f,c,p)]['result']['ledger']==by[(f,c,BASE)]['result']['ledger'] for f in ('low','queue','burst','sustained') for c in ('mean','short_context','long_context')) for p in (PRIOR,GREEDY)})
    write(BUNDLE/'summary.json',summary)
    spec=read(BUNDLE/'registration.json');rep=spec['representative']
    repitems={p:by[(rep['family'],rep['context'],p)] for p in LABELS}
    compact={p:dict(row=i['row'],ledger=i['result']['ledger'],curves=i['curves']) for p,i in repitems.items()}
    write(BUNDLE/'representatives.json',dict(selection=rep,policies=compact))
    # Separate sensitivity output; never replace the frozen one-second KPI.
    from tools import d1_empirical_request_policy as physics
    frozen,_=physics.inputs(physics.BUNDLE)
    initial=read(ROOT/spec['input_path'])['initial']
    sensitivity=[]
    for item in items:
        row=item['row'];ss=item['curves']['segments']
        query=sorted(set([35+i/10 for i in range(1451)]+[s[k] for s in ss for k in ('start_s','end_s') if 35<=s[k]<=180]))
        sampled=max(physics.model.costs(ss,initial,query,frozen,180.)['ap_path'])
        sensitivity.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],
            peak_grid_1s_c=row['peak_ap_c'],peak_extra_samples_c=sampled,continuous_peak_certified=False))
    csv_write(BUNDLE/'ap_sampling_sensitivity.csv',sensitivity)
    figures(rows,pairs,summaries,repitems)
    dashboard(rows,pairs,summaries,summary)
    return summary


def figures(rows,pairs,summaries,repitems):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for font in ('Malgun Gothic','NanumGothic','DejaVu Sans'):
        if any(f.name==font for f in font_manager.fontManager.ttflist):plt.rcParams['font.family']=font;break
    plt.rcParams['axes.unicode_minus']=False
    folder=BUNDLE/'figures';folder.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    allrows={r['policy']:r for r in summaries if r['scope']=='all'}
    colors=['#3366aa','#888888','#ee9944','#44aa88','#bb5577']
    for i,p in enumerate(LABELS):
        r=allrows[p];axes[0].bar(i,r['mean_urgent_p95_ms'],color=colors[i]);axes[1].bar(i,r['normal_failures'],color=colors[i])
    for ax in axes:ax.set_xticks(range(5),list(LABELS.values()),rotation=20,ha='right');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('조건별 긴급 P95 평균 (ms)');axes[1].set_ylabel('전체 일반 기한 실패 (건)')
    fig.suptitle('같은 12조건의 응답과 일반 서비스');fig.savefig(folder/'01_응답과기한.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,4.2),layout='constrained')
    for ax,base in zip(axes,(BASE,SHARED,BAND)):
        for p,color in [(PRIOR,'#44aa88'),(GREEDY,'#bb5577')]:
            ps=[r for r in pairs if r['policy']==p and r['baseline']==base]
            good=[r for r in ps if r['service_preserved'] and r['all_deadlines_met']]
            bad=[r for r in ps if r not in good]
            ax.scatter([r['delta_energy_j'] for r in good],[r['delta_peak_ap_c'] for r in good],c=color,label=LABELS[p],alpha=.8)
            ax.scatter([r['delta_energy_j'] for r in bad],[r['delta_peak_ap_c'] for r in bad],c=color,marker='x',alpha=.35)
        ax.axhline(0,color='grey',lw=.8);ax.axvline(0,color='grey',lw=.8);ax.set_title(LABELS[base]+' 대비');ax.set_xlabel('기기 전체 에너지 차이 (J)');ax.grid(alpha=.2)
    axes[0].set_ylabel('최고 모형 AP 차이 (°C)');axes[0].legend(fontsize=8)
    fig.suptitle('왼쪽 아래가 비용 감소 · 흐린 ×는 전기한 또는 서비스 비악화 실패');fig.savefig(folder/'02_에너지와AP차이.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(5,1,figsize=(11,10),sharex=True,layout='constrained')
    for ax,(p,item) in zip(axes,repitems.items()):
        for r in item['result']['ledger']:
            if 'dispatch_ns' not in r:continue
            start=r['dispatch_ns']/1e9;end=r.get('lane_available_ns',120e9)/1e9
            y=0 if r['backend']=='CPU' else 1
            ax.broken_barh([(start,end-start)],(y-.3,.6),facecolors='#3366aa' if r['priority']=='urgent' else '#ee9944')
            boundary=r.get('output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns')
            if boundary:ax.plot([boundary/1e9]*2,[y-.3,y+.3],color='black',lw=.7)
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[p],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlabel('공통 시간 (초)');axes[-1].set_xlim(35,60)
    fig.suptitle('사전 지정 대표 queue/mean — 막대는 lane 점유, 검은 선은 응답');fig.savefig(folder/'03_대표실행시간표.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
    for (p,item),color in zip(repitems.items(),colors):ax.plot(item['curves']['ap_times_s'],item['curves']['ap_path'],label=LABELS[p],color=color)
    ax.set_xlabel('공통 시간 (초)');ax.set_ylabel('모형 AP (°C)');ax.legend();ax.grid(alpha=.2)
    ax.set_title('같은 대표 조건의 AP 경로 — 표면온도 아님');fig.savefig(folder/'04_대표AP경로.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    families=('low','queue','burst','sustained');contexts=('mean','short_context','long_context')
    by={(r['family'],r['context'],r['policy']):r for r in rows}
    for ax,p in zip(axes,(PRIOR,GREEDY)):
        values=[]
        for f in families:
            line=[]
            for c in contexts:
                row=by[(f,c,p)];refs=[by[(f,c,b)] for b in (BASE,SHARED,BAND)]
                if gain_signal(row,refs,f in ('low','sustained')):value=2
                elif all(compare(row,r)['nonworse'] for r in refs):value=1
                else:value=0
                line.append(value)
            values.append(line)
        from matplotlib.colors import ListedColormap
        ax.imshow(values,vmin=0,vmax=2,cmap=ListedColormap(['#e8c3c3','#e6dfbd','#b4ddc6']),aspect='auto')
        for i,line in enumerate(values):
            for j,value in enumerate(line):ax.text(j,i,['비악화 실패','비악화','개선 신호'][value],ha='center',va='center',fontsize=10)
        ax.set_xticks(range(3),['평균','짧은 문맥','긴 문맥']);ax.set_yticks(range(4),['낮은 부하','대기열','급증','지속']);ax.set_title(LABELS[p])
    fig.suptitle('조건별 세 기준 대비 판정 — 평균으로 실패를 상쇄하지 않음');fig.savefig(folder/'05_조건별판정지도.png',dpi=170);plt.close(fig)


def dashboard(rows,pairs,summaries,summary):
    def table(data,columns):
        head=''.join('<th>'+html.escape(label)+'</th>' for _,label in columns)
        body=''
        for row in data:
            cells=[]
            for key,_ in columns:
                value=LABELS.get(row[key],row[key]) if isinstance(row[key],str) else row[key]
                if isinstance(value,float):value=f'{value:.6f}'
                cells.append('<td>'+html.escape(str(value))+'</td>')
            body+='<tr>'+''.join(cells)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    body=f'<h1>EDD+ECT 보정 정책 개발 검증</h1><p>12조건 × 5정책 = 60행. Gate B {summary["gates"]["B"]}, Gate C {summary["gates"]["C"]}. 학습 0회·기기 0회. 최고 모형 AP는 표면온도가 아닙니다.</p>'
    body+='<p><a href="README.md">한국어 보고서</a> · <a href="results.csv">전체 결과 CSV</a> · <a href="pairs.csv">조건별 비교 CSV</a> · <a href="physical_branches.json">실제 분기 근거</a></p>'
    body+='<h2>판단 규칙의 역할</h2><table><thead><tr><th>규칙</th><th>판단</th></tr></thead><tbody>'
    for p,desc in [(BASE,'EDD 순서·ECT lane 완료 자원·필요 자원 대기'),(SHARED,'공용 예상 응답 최소·aging'),(BAND,'공개 HEFT 코드의 전체 요청 제한 적용'),(PRIOR,'도착 큐 실제 기한 검사 후 EDD 기본 우선'),(GREEDY,'같은 검사 뒤 에너지 비증가·최고 AP 최소')]:body+=f'<tr><td>{LABELS[p]}</td><td>{desc}</td></tr>'
    body+='</tbody></table><input id="filter" placeholder="정책·조건 검색">'
    body+=table(summaries,[('scope','범위'),('policy','정책'),('conditions','조건'),('completed','완료'),('normal_failures','일반 실패'),('mean_urgent_p95_ms','긴급 P95 ms'),('mean_energy_j','전체 J'),('mean_peak_ap_c','모형 AP °C')])
    body+='<h2>전체 60조건 결과</h2>'+table(rows,[('family','부하'),('context','처리문맥'),('policy','정책'),('planned','예정'),('completed','완료'),('normal_service_failure','일반 실패'),('urgent_p95_ms','긴급 P95 ms'),('energy_j','전체 J'),('peak_ap_c','AP °C')])
    for name in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{name.name}" alt="{name.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EDD+ECT 개발 검증</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;color:#243142;max-width:1450px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dde3e8;padding:7px;text-align:left}th{background:#edf3f8}.scroll{overflow:auto;margin:16px 0}input{padding:10px;width:320px}img{width:100%;max-width:1200px;margin:20px 0}h2{margin-top:28px}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')


if __name__=='__main__':
    summary=report()
    print(json.dumps({k:v for k,v in summary.items() if k!='policy_summaries'},ensure_ascii=False,indent=2))
