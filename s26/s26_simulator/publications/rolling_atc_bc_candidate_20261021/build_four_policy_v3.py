"""Compare the selected saved candidate against FIFO/EDF/RR on exact common inputs.

Only saved-file arithmetic, plotting and writing are performed. No simulator,
model forward, training, physical fitting, policy query or budget action.
"""
from pathlib import Path
import csv
import datetime
import gzip
import hashlib
import html
from html.parser import HTMLParser
import json
import math
import os
import re
import subprocess

H = Path(__file__).resolve().parent
R = H.parents[2]
E = R / 's26_simulator/experiments'
B = E / 'final_four_rr_v1'
C = E / 'bc_service_refinement_20261020'
METHODS = ['FIFO', 'EDF', 'RR', 'OURS']
NAMES = dict(FIFO='FIFO', EDF='EDF', RR='RR', OURS='우리 롤링+ATC+BC')

def read(path):
    raw = Path(path).read_bytes()
    if str(path).endswith('.gz'):
        raw = gzip.decompress(raw)
    return json.loads(raw.decode('utf-8-sig'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value, exclusive=True):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8', newline='\n') as dest:
        json.dump(value, dest, ensure_ascii=False, allow_nan=False, indent=2)
        dest.write('\n')

def table(headers, rows):
    top = ''.join('<th scope="col">'+html.escape(str(v))+'</th>' for v in headers)
    body = ''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)
    return '<div class="table-wrap"><table><thead><tr>'+top+'</tr></thead><tbody>'+body+'</tbody></table></div>'

def q95(xs):
    return sorted(xs)[math.ceil(.95*len(xs))-1] if xs else None

class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.rows=[]; self.cells=0; self.links=[]; self.images=[]
    def handle_starttag(self, tag, attrs):
        if tag=='table': self.rows=[]
        if tag=='tr': self.cells=0
        if tag in ('td','th'): self.cells+=1
        if tag=='a': self.links.append(dict(attrs)['href'])
        if tag=='img': self.images.append(dict(attrs)['src'])
    def handle_endtag(self, tag):
        if tag=='tr': self.rows.append(self.cells)
        if tag=='table': self.tables.append(self.rows.copy())

def main():
    assert not (H/'FOUR_POLICY_DATA.json').exists(), 'Completed registration: use a new version.'
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
    branch = subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()
    changes = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True).splitlines()
    assert branch=='codex/s26-simulator-handoff-20261016'
    source_paths = {Path(__file__),B/'INPUTS.json',B/'PROTOCOL.json',B/'artifacts/G001/RESULT.json',
        B/'artifacts/G001/SUMMARY.json',B/'artifacts/G001/AUDIT.json',C/'INPUTS.json',C/'PROTOCOL.json',
        C/'ANALYSIS.json',C/'artifacts/G001/RESULT.json',C/'policy.cjs',C/'service_guard.cjs',
        C/'CONFIRMATION_ASSESSMENT.json',R/'s26_simulator/FINAL_POLICY.json',
        E/'route_group_learning_v1/artifacts/G001/BC_COMMON_FINAL.pt.gz',
        E/'route_group_learning_v1/artifacts/G001/S881087_FINAL.pt.gz'}
    left=read(B/'INPUTS.json')['cases']
    right={v['id']:v for v in read(C/'INPUTS.json')['cases']}
    input_keys=['n','mix','stream','requests','context','horizon_s','dispatch_stop_s','censor_s','model']
    input_matches=[]
    for case in left:
        other=right[case['id']]
        assert all(case[k]==other[k] for k in input_keys),case['id']
        signature={k:case[k] for k in input_keys}
        digest=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        input_matches.append(dict(input=case['id'],keys=input_keys,common_input_sha256=digest))
    assert len(left)==4
    engine_matches=[]
    for name in ['source/multi_simulator.cjs','source/multi_timing.cjs','source/resource_contract.cjs',
                 'source/midpoint_work.cjs','source/s26_simulator.cjs','physics.cjs']:
        a=B/name; b=E/'rolling_rl_ablation_v1'/name
        assert sha(a)==sha(b),name
        source_paths.update([a,b])
        engine_matches.append(dict(file=name,sha256=sha(a),equal=True))

    rows=[]
    raws={}
    for method in METHODS:
        if method=='OURS':
            originals=[v for v in read(C/'artifacts/G001/RESULT.json')['rows']
                       if v['cohort']=='original4' and v['method']=='BC_RESOURCE_EDF_NORMAL']
            folder=C/'artifacts/G001'
        else:
            originals=[v for v in read(B/'artifacts/G001/RESULT.json')['rows'] if v['method']==method]
            folder=B/'artifacts/G001'
        assert len(originals)==4
        for row in originals:
            raw_path=folder/(row['label']+'.raw.json.gz')
            assert sha(raw_path)==row['raw_sha256'],raw_path.name
            raw=read(raw_path)
            case=next(v for v in left if v['id']==row['input'])
            assert row['stream']==case['stream'] and row['n']==case['n']==1024
            assert abs(raw['dispatch_stop_s']-case['dispatch_stop_s'])<1e-8
            assert abs(raw['censor_s']-case['censor_s'])<1e-8
            assert abs(raw['observation_end_s']-case['horizon_s'])<1e-8
            assert raw['cpu_workers']==3 and raw['routing_contract']['slots']==dict(CPU=1,GPU=1,NPU=1)
            assert raw['routing_contract']['nonpreemptive'] and raw['routing_contract']['reserve_until']=='AVAILABLE'
            assert abs(raw['physics_J']-row['J'])<1e-8 and abs(raw['AP_mean']-row['AP_mean'])<1e-10
            assert abs(sum(v[2] for v in raw['integrals'])+35*raw['baseline_API_W']-row['J'])<1e-7
            assert abs(sum(v[3] for v in raw['integrals'])/(raw['observation_end_s']-35)-row['AP_mean'])<1e-8
            assert row['unfinished']==sum(q['available'] is None for q in raw['requests'])
            for pr in ('all','urgent','normal'):
                qs=[q for q in raw['requests'] if pr=='all' or q['priority']==pr]
                done=[q for q in qs if q['response'] is not None]
                assert row['service'][pr]['planned']==len(qs)
                assert row['service'][pr]['on_time']==sum(q['response']<=q['deadline']+1e-9 for q in done)
                assert abs(row['service'][pr]['p95_s']-q95([q['response']-q['arrival'] for q in done]))<1e-8
            rows.append(dict(method=method,input=case['id'],mix=case['mix'],stream=case['stream'],
                n=case['n'],J=row['J'],AP_mean=row['AP_mean'],service=row['service'],unfinished=row['unfinished'],
                source_label=row['label'],raw_path=raw_path.relative_to(R).as_posix(),raw_sha256=sha(raw_path)))
            raws[(method,case['id'])]=raw
            source_paths.add(raw_path)
    assert len(rows)==16
    # Same planned arrivals and policy-independent enqueue draw, not just same IDs.
    common_plan_checks=[]
    for case in left:
        ref=raws[('FIFO',case['id'])]
        keys=['ordinal','task','priority','arrival','deadline','readyAt','enqueueTemplate']
        planned=[{k:q[k] for k in keys} for q in ref['planned_requests']]
        for method in METHODS:
            raw=raws[(method,case['id'])]
            assert [{k:q[k] for k in keys} for q in raw['planned_requests']]==planned
            assert raw['baseline_API_W']==ref['baseline_API_W']
        common_plan_checks.append(dict(input=case['id'],methods=4,requests=1024,same_plan_and_enqueue_draw=True))

    summary={}
    baseline_summary=read(B/'artifacts/G001/SUMMARY.json')
    for method in METHODS:
        sub=[r for r in rows if r['method']==method]
        v=dict(cases=4,requests=4096,J=sum(r['J'] for r in sub)/4,
               AP_mean=sum(r['AP_mean'] for r in sub)/4,unfinished=sum(r['unfinished'] for r in sub),service={})
        for pr in ('all','urgent','normal'):
            s={k:sum(r['service'][pr][k] for r in sub) for k in ('planned','completed','on_time')}
            s['on_percent']=100*s['on_time']/s['planned']
            s['mean_case_P95_s']=sum(r['service'][pr]['p95_s'] for r in sub)/4
            s['failed_deadlines']=s['planned']-s['on_time']
            v['service'][pr]=s
        if method!='OURS':
            old=baseline_summary[method]
            assert abs(v['J']-old['J'])<1e-9 and abs(v['AP_mean']-old['AP_mean'])<1e-10
            for pr in ('all','urgent','normal'):
                assert v['service'][pr]['on_time']==old['service'][pr]['on_time']
        summary[method]=v
    ours=summary['OURS']
    assert abs(ours['J']-769.2674435652561)<1e-9
    contrasts={}
    for method in ['FIFO','EDF','RR']:
        b=summary[method]
        contrasts[method]=dict(API_usage_change_percent=100*(ours['J']/b['J']-1),
            AP_delta_C=ours['AP_mean']-b['AP_mean'],whole_on_delta_pp=ours['service']['all']['on_percent']-b['service']['all']['on_percent'],
            normal_on_delta_pp=ours['service']['normal']['on_percent']-b['service']['normal']['on_percent'],
            urgent_P95_delta_s=ours['service']['urgent']['mean_case_P95_s']-b['service']['urgent']['mean_case_P95_s'])
    for value in summary.values():
        assert value['service']['urgent']['on_percent']==100 and value['unfinished']==0
    source_pins=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p)) for p in sorted(source_paths)]
    dump(H/'SOURCE_MANIFEST_V3.json',dict(utc=stamp,HEAD=head,branch=branch,tracked_changes=changes,files=source_pins,
        scope='Four saved common inputs; FIFO/EDF/RR plus selected BC_RESOURCE_EDF_NORMAL, not former official OURS row.',
        new_environments=0,new_training=0,new_measurements=0,policy_queries=0))
    dump(H/'FOUR_POLICY_INPUT_MATCH.json',dict(utc=stamp,status='PASS_EXACT_COMMON_INPUTS_AND_ENGINE_BYTES',
        input_matches=input_matches,engine_matches=engine_matches,raw_plan_matches=common_plan_checks,
        raw_results=16,completed_experiments_repeated=0))
    dump(H/'FOUR_POLICY_DATA.json',dict(utc=stamp,primary_methods=METHODS,summary=summary,contrasts=contrasts,rows=rows,
        input_count=4,requests_per_method=4096,policy_candidate='BC_RESOURCE_EDF_NORMAL',adopted=False,
        P95_aggregation='Unweighted mean of four within-session P95s, not pooled P95.',new_environments=0,new_training=0))

    # Standard plotting from saved data only. API usage is an absolute API-J axis.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_manager.findfont('Malgun Gothic',fallback_to_default=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'svg.fonttype':'none','font.size':10})
    figdir=H/'figures_v3'
    figdir.mkdir(exist_ok=False)
    colors=['#55616b','#377eb8','#df8a35','#137e78']
    labels=[NAMES[m] for m in METHODS]
    figures=[]
    def export(fig,name):
        for ext in ('png','svg'):
            target=figdir/(name+'.'+ext)
            fig.savefig(target,dpi=170,bbox_inches='tight')
            figures.append(target)
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(9.2,4.3))
    values=[summary[m]['J'] for m in METHODS]
    bars=ax.bar(labels,values,color=colors,width=.58)
    ax.set_ylim(0,max(values)*1.14)
    ax.set_ylabel('전체 사용량 (API-J)')
    ax.set_title('동일 4입력의 평균 API 사용량')
    ax.axhline(values[0],color=colors[0],ls='--',lw=1,label='FIFO 기준')
    for bar,value in zip(bars,values):
        ax.text(bar.get_x()+bar.get_width()/2,value+11,f'{value:.3f}',ha='center',va='bottom')
    ax.legend(loc='upper right')
    ax.grid(axis='y',alpha=.18); ax.set_axisbelow(True)
    export(fig,'api_usage')
    fig,axes=plt.subplots(1,2,figsize=(11,4.1))
    aps=[summary[m]['AP_mean'] for m in METHODS]
    for i,value in enumerate(aps):
        axes[0].scatter(i,value,color=colors[i],s=70,zorder=3)
        axes[0].text(i,value+.055,f'{value:.3f}',ha='center',fontsize=9)
    axes[0].set_xticks(range(4),labels,rotation=12)
    axes[0].set_ylim(min(aps)-.18,max(aps)+.22)
    axes[0].set_ylabel('평균 AP (℃, 확대축)')
    axes[0].set_title('평균 AP — 점그래프 확대축')
    axes[0].axhline(aps[0],color=colors[0],ls='--',lw=1)
    ps=[summary[m]['service']['urgent']['mean_case_P95_s'] for m in METHODS]
    bars=axes[1].bar(labels,ps,color=colors,width=.58)
    axes[1].set_ylim(0,max(ps)*1.23)
    axes[1].set_ylabel('긴급 응답 P95 (초, 세션별 P95의 평균)')
    axes[1].set_title('긴급 응답 지연')
    axes[1].tick_params(axis='x',rotation=12)
    axes[1].axhline(ps[0],color=colors[0],ls='--',lw=1)
    for bar,value in zip(bars,ps):
        axes[1].text(bar.get_x()+bar.get_width()/2,value+.018,f'{value:.3f}',ha='center')
    for ax in axes:
        ax.grid(axis='y',alpha=.18); ax.set_axisbelow(True)
    fig.tight_layout()
    export(fig,'temperature_and_urgent_latency')
    fig,axes=plt.subplots(2,2,figsize=(11,7.3))
    for idx,(case,ax) in enumerate(zip(left,axes.flat),1):
        first=min(q['offset_ns']/1e9 for q in case['requests'])
        for method,color in zip(METHODS,colors):
            raw=raws[(method,case['id'])]
            curve=[p for p in raw['curve'] if p[0]>=first-1e-9]
            ax.plot([p[0]-first for p in curve],[p[1] for p in curve],color=color,
                    lw=1.8 if method=='OURS' else 1.2,ls='--' if method=='FIFO' else '-',label=NAMES[method])
        ax.set_title(f"입력 {idx} · 분류 {100*case['mix']:.0f}%")
        ax.set_xlim(0,case['horizon_s']-first)
        ax.set_xlabel('첫 계획 도착 이후 실제 경과 시간 (초)')
        ax.set_ylabel('AP (℃)'); ax.grid(alpha=.18)
    handles,legend_labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,ncol=4,loc='upper center',bbox_to_anchor=(.5,1.01))
    fig.tight_layout(rect=(0,0,1,.96))
    export(fig,'AP_elapsed_seconds')

    # Preserve previous drafts, then replace the report at the same user-facing URL.
    revision=H/'revisions'/'before_four_policy_v3'
    revision.mkdir(parents=True,exist_ok=False)
    for name in ['RESULTS_KO.html','RESULTS_KO.txt','RESULTS_TABLES.csv','REPORT_QA.json','STATUS.json','FILES.json']:
        with (revision/name).open('xb') as dest:
            dest.write((H/name).read_bytes())
    old_html=(H/'RESULTS_KO.html').read_text(encoding='utf-8')
    method_section=re.search(r'<section><h2>1\. 롤링 ATC BC의 역할과 실행 흐름</h2>.*?</section>',old_html,re.S)
    assert method_section
    method_section=method_section.group(0)
    assert 'PPO 이력' not in method_section
    style=re.search(r'<style>.*?</style>',old_html,re.S).group(0)
    style=style.replace('</style>','figure{margin:20px 0}figure img{width:100%;height:auto}figcaption{color:#526779;font-size:14px}</style>')
    intro=(f"동일한 원4입력·방법별4,096요청에서 우리 롤링+ATC+BC 후보의 평균 전체 사용량은 {ours['J']:.3f} API-J, "
           f"평균 AP는 {ours['AP_mean']:.3f}℃, 전체 정시율은 {ours['service']['all']['on_percent']:.3f}%였다. "
           f"FIFO 대비 사용량은 {-contrasts['FIFO']['API_usage_change_percent']:.3f}% 낮고, 평균 AP는 {-contrasts['FIFO']['AP_delta_C']:.3f}℃ 낮았다. "
           '네 방법 모두 긴급 정시율100%, 미완료0건이다. 우리 후보의 긴급 응답 P95는 기준정책보다 길다.')
    parts=['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>S26 롤링 ATC BC와 FIFO EDF RR 비교 결과</title>'+style+'</head><body><main>']
    parts.append('<header><p class="meta">2026년 10월 21일 · 공통 입력의 네 정책 비교 · 결과 초안 3판</p>'
        '<h1>S26 롤링 ATC BC와 FIFO EDF RR 비교 결과</h1>'
        '<p>주 비교는 지금까지 검토한 정책 중 명목 부하에서 서비스와 사용량의 균형이 좋았던 롤링+ATC+BC 후보와 FIFO·EDF·RR의 네 방법으로 구성한다.</p>'
        '<div class="summary">'+html.escape(intro)+'</div>'
        '<p class="meta">우리 후보에는 자원·납기 보완 규칙이 포함된다. 같은 입력에 보관된 결과만 재집계했으며 새 시뮬레이션·학습은 없다.</p></header>')
    parts.append(method_section)
    parts.append('<section><h2>2. 비교 방법과 공통 평가 조건</h2>'+table(['방법','요청 선택','분류 경로 선택'],[
        ['FIFO','실행 가능한 관측 큐에서 도착 순서','GPU → NPU → CPU'],
        ['EDF','실행 가능한 관측 큐에서 절대 납기 순서','GPU → NPU → CPU'],
        ['RR','분류·탐지 큐를 한 요청씩 순환, 큐 안은 FIFO','GPU → NPU → CPU'],
        ['우리 롤링+ATC+BC','ATC·EDF 후보, 롤링 특징, 동결 BC 점수와 서비스 보완','현재 슬롯과 정책이 허용한 경로에서 선택']])
        +'<p>RR은 비선점 작업종류별 큐 순환이다. CPU 시간을 나누는 OS 타임퀀텀 RR이 아니다. 실행 가능한 요청이 없는 큐는 건너뛰며 최초 포인터는 분류 큐다. 네 방법 모두 탐지는 CPU만 지원한다.</p>'
        +table(['항목','공통 조건'],[
        ['입력','원 명목85% 입력4개: 분류50%·75% × 잠재 스트림2개'],
        ['규모','세션당1,024요청, 방법별4,096요청'],
        ['기기 제약','CPU 작업자3, CPU/GPU/NPU 추론 슬롯 각1, 최대3요청 점유'],
        ['물리 점유','비선점, 응답 뒤에도 실제 AVAILABLE까지 점유'],
        ['납기·응답','긴급 분류0.8초/output_ready, 일반 탐지2초/readback_end'],
        ['관측 창','동일 입력끼리 같은 공급·dispatch stop·censor·관측 종료'],
        ['대응 확인','요청·도착·초기 맥락·잠재 스트림·enqueue 표본·공통 엔진 일치']])
        +'<p>같은 물리 제약에서 경로 선택까지 포함한 전체 정책을 비교한다. 기준정책은 고정 경로 순서, 우리 후보는 학습 선택과 자원 보완을 사용하므로 차이를 BC만의 독립 효과로 해석하지 않는다. GPU 우선 기준이며 최강의 모든 경로 기준정책을 이겼다는 주장은 하지 않는다.</p>'
        '<p>API-J와 AP는4개 세션 평균, 정시율은 전체 도착을 합친 비율이다. 미응답도 실패로 남기고 미완료는 AVAILABLE 미도달로 센다. P95는 각 세션의 응답 완료 P95를 평균한 값이며 전체 요청을 합친 pooled P95가 아니다.</p>'
        '<p class="note">앞선 초안의6입력 평균778.996 API-J와 이번4입력 평균769.267 API-J는 평가 묶음이 다르다. 현재 네 방법의 수치는 전부 동일한 원4입력 기준이며 두 평균을 개선 전후 값으로 비교하지 않는다.</p></section>')
    parts.append('<section><h2>3. FIFO EDF RR과 우리 정책의 결과</h2>'+table(
        ['방법','평균 API-J','평균 AP℃','전체 정시%','긴급 정시%','일반 정시%','미완료'],[
        [NAMES[m],f"{summary[m]['J']:.3f}",f"{summary[m]['AP_mean']:.3f}",
         f"{summary[m]['service']['all']['on_percent']:.3f}",f"{summary[m]['service']['urgent']['on_percent']:.3f}",
         f"{summary[m]['service']['normal']['on_percent']:.3f}",summary[m]['unfinished']] for m in METHODS])
        +table(['대조','우리 사용량 변화%','우리 평균 AP 차이℃','전체 정시 차이%p','일반 정시 차이%p'],[
        [m,f"{contrasts[m]['API_usage_change_percent']:+.3f}",f"{contrasts[m]['AP_delta_C']:+.3f}",
         f"{contrasts[m]['whole_on_delta_pp']:+.3f}",f"{contrasts[m]['normal_on_delta_pp']:+.3f}"] for m in METHODS[:3]])
        +f"<p>우리 후보는 전체4,096건 중{ours['service']['all']['on_time']:,}건을 정시에 처리했다. 긴급2,560건은 모두 정시이며 일반1,536건 중1,416건이 정시다. "
        '일반 납기 실패120건은 남아 있지만 모든 요청이 AVAILABLE에 도달했다. FIFO와 RR보다 일반 요청6건, EDF보다15건을 더 정시에 처리했다. '
        '정시율 차이는 작으므로 큰 서비스 도약으로 포장하지 않는다.</p>'
        '<figure><img src="figures_v3/api_usage.png" alt="FIFO EDF RR 우리 정책의 절대 API 사용량"><figcaption>사용량은 변화율이 아닌 API-J이며 막대 축은0에서 시작한다. 점선은FIFO 평균이다.</figcaption></figure>'
        '<p>이 결과의 주된 이점은 같은 긴급 정시율과 전량 완료를 유지하면서 전체 API 사용량과 평균 AP가 낮아진 점이다. 이는 롤링·ATC·BC와 자원·납기 보완이 결합된 정책의 조건부 결과다.</p></section>')
    parts.append('<section><h2>4. 응답 지연과 실제 경과 시간</h2>'+table(
        ['방법','전체 P95초','긴급 P95초','일반 P95초'],[
        [NAMES[m],*[f"{summary[m]['service'][p]['mean_case_P95_s']:.3f}" for p in ('all','urgent','normal')]] for m in METHODS])
        +f"<p>우리 후보의 긴급 P95는 {ours['service']['urgent']['mean_case_P95_s']:.3f}초로 FIFO의 {summary['FIFO']['service']['urgent']['mean_case_P95_s']:.3f}초, "
        f"EDF의 {summary['EDF']['service']['urgent']['mean_case_P95_s']:.3f}초, RR의 {summary['RR']['service']['urgent']['mean_case_P95_s']:.3f}초보다 길다. "
        '긴급 납기는 모두 지켰지만 지연 분포까지 모든 지표에서 우월한 것은 아니다.</p>'
        '<figure><img src="figures_v3/temperature_and_urgent_latency.png" alt="평균 AP와 긴급 P95의 상충"><figcaption>평균 AP는 확대축 점그래프, 긴급 P95 막대는0초부터 시작한다. 점선은FIFO 기준이며 신뢰구간은 표시하지 않는다.</figcaption></figure>'
        '<figure><img src="figures_v3/AP_elapsed_seconds.png" alt="4개 공통 입력의 실제 경과 초에 따른 AP"><figcaption>X축은 첫 계획 도착 이후 실제 경과 초다. 요청 번호나 샘플 인덱스를 시간으로 사용하지 않았다. 각 패널은 같은 입력에 대한 네 정책의 모형 AP이며 입력별 관측 길이를 유지한다.</figcaption></figure></section>')
    fifo=contrasts['FIFO']; edf=contrasts['EDF']; rr=contrasts['RR']
    conclusion=(f"S26의 자원 제약을 반영한 롤링 예측·ATC 후보 구성·BC 행동 선택과 서비스 보완을 결합한 후보를 FIFO·EDF·비선점 큐 RR과 비교하였다. "
        f"동일한 명목85%의4입력에서 후보는 긴급 정시율100%와 미완료0건을 유지했고 전체 정시율97.070%를 기록하였다. "
        f"평균 API 사용량은 FIFO 대비 {-fifo['API_usage_change_percent']:.3f}%, EDF 대비 {-edf['API_usage_change_percent']:.3f}%, RR 대비 {-rr['API_usage_change_percent']:.3f}% 낮았다. "
        f"평균 AP도 각각 {-fifo['AP_delta_C']:.3f}℃, {-edf['AP_delta_C']:.3f}℃, {-rr['AP_delta_C']:.3f}℃ 낮았다. "
        '다만 긴급 응답 P95는 기준정책보다 길었다. 따라서 전체 정책이 사용량·평균 AP와 납기 충족 사이에서 유리한 균형을 보였다는 조건부 결과로 해석한다.')
    parts.append('<section><h2>5. 결과 해석과 결론</h2><blockquote>'+html.escape(conclusion)+'</blockquote>'
        '<p>이4입력은 후보 검토 과정에서 이미 관측된 조건이다. 결과를 본 뒤 추천 후보를 정한 후향적 비교이며 새 독립 확인 실험이 아니다. '
        '같은 후보의 별도105% 과부하에서는 긴급 정시율이 약92.97%로 하락했으므로 모든 부하에 대한 납기 보장으로 확대하지 않는다.</p>'
        '<p>보완 규칙도 실제 행동에 영향을 주므로 BC·ATC·롤링 각각의 독립 성과나 필수성이 이 표로 증명되는 것은 아니다. '
        '기존 예측 캐시의 동등성 한계도 보존하며 저장 결과의 회계·NN 검산을 예측 모형의 완전한 정확성으로 확대하지 않는다.</p>'
        '<p class="note">전력·열 물리 정확도 gate는FAIL이다. API-J와 AP는 조건부 모형 출력이며 실제 S26 소비·온도 절감 인증이 아니다. '
        'CPU3 추가 코어의 전력·열·간섭과 실제 모바일에서의 예측·NN·제어 비용은 미측정이다. 호스트 계산 시간을 가상 납기나 API-J에 추가하지 않았다.</p></section>')
    parts.append('<section><h2>부록 입력별 네 정책 결과</h2>'+table(
        ['입력','방법','API-J','AP℃','전체 정시/도착','일반 정시/도착','미완료'],[
        [f"입력{i} / 분류{100*case['mix']:.0f}%",NAMES[m],f"{r['J']:.3f}",f"{r['AP_mean']:.3f}",
         str(r['service']['all']['on_time'])+'/1024',str(r['service']['normal']['on_time'])+'/'+str(r['service']['normal']['planned']),r['unfinished']]
        for i,case in enumerate(left,1) for m in METHODS for r in rows if r['input']==case['id'] and r['method']==m])
        +'<p>原자료의16결과를 재사용했고 완료된 실험을 재실행하지 않았다. 기존 공식 정책 채택 기록과 과거 결과는 보존했다. '
        '본 문서는 추천 후보를 중심으로 비교 구성을 바꾼 결과 초안이다.</p>'
        '<p><a href="FOUR_POLICY_DATA.json">네 정책 집계·대조</a> · <a href="FOUR_POLICY_INPUT_MATCH.json">공통 입력·물리 엔진 일치</a> · '
        '<a href="SOURCE_MANIFEST_V3.json">근거 파일 SHA</a> · <a href="RESULTS_KO.txt">결과·결론 텍스트</a> · '
        '<a href="RESULTS_TABLES.csv">입력별 표</a> · <a href="REPORT_QA.json">문서 검사</a></p></section></main></body></html>')
    new_html='\n'.join(parts)
    (H/'RESULTS_KO.html').write_text(new_html,encoding='utf-8')
    text=('S26 롤링 ATC BC와 FIFO EDF RR 비교 결과\n2026-10-21 · 결과 초안3판\n\n'
          '비교 조건\n동일한 원 명목85% 입력4개, 세션당1,024건, 방법별4,096건. CPU작업자3, CPU/GPU/NPU 추론 슬롯각1, '
          '비선점·실제AVAILABLE까지 점유, 탐지CPU 전용이다. FIFO·EDF·RR은 분류GPU→NPU→CPU 순서다. '
          'RR은분류/탐지큐를한요청씩순환하는방식이며OS타임퀀텀RR이아니다.\n\n'
          '우리 방법\n롤링 예측으로 행동 이후의 명목 영향을 평가하고, ATC·EDF로 후보를 구성하며, 동결된32특징 BC 단계 모델로 행동 점수를 만든다. '
          '자원·납기 보완이 허용한 행동에서 최고 BC 점수를 선택한다. 실행 때도 롤링을 사용한다.\n\n'
          '결과\n'+intro+'\n\n'
          + '\n'.join(f"{NAMES[m]}: {summary[m]['J']:.3f} API-J / 평균AP {summary[m]['AP_mean']:.3f}℃ / 전체정시 {summary[m]['service']['all']['on_percent']:.3f}% / 긴급정시100% / 일반정시 {summary[m]['service']['normal']['on_percent']:.3f}% / 미완료0" for m in METHODS)
          +'\n\n결론\n'+conclusion+'\n\n'
          '범위\n原4입력은개발중관측된조건이며사후추천비교다. 새독립확인실험이아니다. 6입력평균778.996과이번4입력평균769.267을개선전후로비교하지않는다. '
          'BC·롤링·ATC각각의독립효과는미입증이며서비스보완의영향을포함한다. 물리gateFAIL·CPU3와모바일계산비용미측정이므로실기기절감인증이아니다. '
          '새환경·학습·실측·정책질의0. 기존공식정책과과거원자료보존.\n')
    (H/'RESULTS_KO.txt').write_text(text,encoding='utf-8')
    with (H/'RESULTS_TABLES.csv').open('w',encoding='utf-8-sig',newline='') as dest:
        writer=csv.writer(dest)
        writer.writerow(['input','method','API_J','AP_C','all_planned','all_on_time','urgent_planned','urgent_on_time','normal_planned','normal_on_time','unfinished'])
        for row in rows:
            writer.writerow([row['input'],row['method'],row['J'],row['AP_mean'],row['service']['all']['planned'],row['service']['all']['on_time'],
                row['service']['urgent']['planned'],row['service']['urgent']['on_time'],row['service']['normal']['planned'],row['service']['normal']['on_time'],row['unfinished']])
    inspector=Inspector(); inspector.feed(new_html)
    assert all(len(set(t))==1 and t[0]>1 for t in inspector.tables)
    assert all((H/path).resolve().is_file() for path in inspector.links+inspector.images)
    assert len(inspector.images)==3
    assert 'PPO 이력' not in new_html and '서비스 중심 롤링 교사' not in new_html
    assert new_html.count('769.267')>=2
    assert all(sha(R/p['path'])==p['sha256'] for p in source_pins)
    assert subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True).splitlines()==changes
    dump(H/'REPORT_QA.json',dict(utc=stamp,status='PASS_V3_FOUR_POLICIES_INPUT_ENGINE_MATCH_RAW_ACCOUNTING_TABLES_LINKS',
        report_sha256=sha(H/'RESULTS_KO.html'),text_sha256=sha(H/'RESULTS_KO.txt'),
        methods=METHODS,cases=4,requests_per_method=4096,raw_results_verified=16,
        tables=len(inspector.tables),links=len(inspector.links),images=len(inspector.images),
        source_files_unchanged=True,tracked_tree_unchanged=True,visual_render_verified=False,
        new_environments=0,new_training=0,new_measurements=0,policy_queries=0),exclusive=False)
    dump(H/'STATUS.json',dict(utc=stamp,status='FOUR_POLICY_RESULTS_DRAFT_COMPLETE_NOT_OFFICIAL_ADOPTION',
        document_revision=3,candidate='BC_RESOURCE_EDF_NORMAL',focus='rolling+ATC+BC versus FIFO EDF RR',
        HEAD=head,official_policy_unchanged=True,report='RESULTS_KO.html',source='RESULTS_KO.txt',verification='REPORT_QA.json',
        new_environments=0,new_training=0,new_measurements=0,policy_queries=0,
        next=['Review the four-policy comparison','User decides formal adoption or further validation purpose','Preserve sources; no automatic new experiments']),exclusive=False)
    files=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p),bytes=p.stat().st_size)
           for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p!=H/'FILES.json']
    dump(H/'FILES.json',dict(utc=stamp,files=files,excluded=['FILES.json self','__pycache__']),exclusive=False)
    assert all(sha(R/p['path'])==p['sha256'] for p in files)
    print(json.dumps(dict(status='COMPLETE_FOUR_POLICY_REPORT',summary=summary,contrasts=contrasts,files=len(files)),ensure_ascii=False))

if __name__=='__main__':
    main()
