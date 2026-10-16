"""Read-only CSV/representative-record report; never starts a simulator."""
from __future__ import annotations
import argparse
import csv
import gzip
import html
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from tools import d1_external_rules_study as study
from tools import d1_external_rules as r

LABELS={'CPU_REFERENCE':'순차 CPU 기준', 'SPLIT_REFERENCE':'고정 분류GPU·탐지CPU',
        'EFT_REFERENCE':'기존 예상 응답 우선', 'SHARED_EDF':'공유 기한 우선',
        'SHARED_EFT':'강한 예상 응답 우선', 'ENERGY_AP_REQUEST_V1':'우리 에너지·AP 규칙',
        r.joint.LABEL:'우리 큐 에너지·AP 규칙', r.BAND:'Band HEFT 요청 단위 적용',
        r.ALWAYS:'배경 시작 항상 허용',r.ENTE:'Ente 시작 허용 적용'}
ENVS={'quiet_healthy':'활동 없음·건강', 'intermittent_activity':'36·50초 활동',
      'continuous_activity':'10초마다 계속 활동', 'battery_recovers':'배터리19→20%',
      'battery_low_persistent':'배터리19% 지속', 'battery_heat_recovers':'BAT43→42°C',
      'os_thermal_recovers':'OS 열 serious→moderate'}
FAMILIES={'low':'저부하','queue':'큐 밀집','burst':'버스트','sustained':'지속 도착'}
COLORS=['#63758b','#ad8054','#2487a3','#9a70aa','#176a48','#bd4f5b','#d89c24','#2e3e76']


def typed_rows(path):
    rows=[]
    for row in csv.DictReader(Path(path).open(encoding='utf8',newline='')):
        obj={}
        for k,v in row.items():
            if v=='':obj[k]=None
            elif v in ('True','False'):obj[k]=v=='True'
            else:
                try:obj[k]=float(v) if any(x in v for x in '.eE') else int(v)
                except ValueError:obj[k]=v
        rows.append(obj)
    return rows


def mean(rows,key):
    values=[row[key] for row in rows if row.get(key) is not None]
    return statistics.mean(values) if values else None


def group_summary(rows):
    groups={}
    for row in rows:
        key=tuple(row[k] for k in ('scope','environment','family','policy'))
        groups.setdefault(key,[]).append(row)
    result=[]
    for key,items in groups.items():
        planned=sum(x['planned'] for x in items)
        urgent=sum(x['urgent_n'] for x in items);normal=sum(x['normal_n'] for x in items)
        result.append(dict(zip(('scope','environment','family','policy'),key),cases=len(items),
            planned=planned,completed=sum(x['completed'] for x in items),
            completion_rate=sum(x['completed'] for x in items)/planned,
            timely_rate=sum(x['deadline_met'] for x in items)/planned,
            urgent_failure_rate=sum(x['urgent_service_failure'] for x in items)/urgent,
            normal_failure_rate=sum(x['normal_service_failure'] for x in items)/normal,
            full_work_cases=sum(x['completed']==x['planned'] for x in items),
            full_timely_cases=sum(x['deadline_met']==x['planned'] for x in items),
            ap_complete_cases=sum(x['peak_ap_c'] is not None for x in items),
            **{k:mean(items,k) for k in ('urgent_p95_ms','normal_mean_ms','energy_j','peak_ap_c',
                'thermal_degree_seconds','overlap_s','cpu_occupied_s','gpu_occupied_s','decision_host_total_s')}))
    for group in result:
        if group['ap_complete_cases']!=group['cases']:
            group['peak_ap_c']=group['thermal_degree_seconds']=None
    return result


def paired(rows):
    references={(x['scope'],x['environment'],x['seed'],x['family'],x['context']):x for x in rows
                if x['policy']==('SHARED_EFT' if x['scope']=='resource' else r.ALWAYS)}
    pairs=[]
    for row in rows:
        ref=references[row['scope'],row['environment'],row['seed'],row['family'],row['context']]
        value={k:row[k] for k in ('scope','environment','seed','family','context','policy')}
        value['reference']=ref['policy']
        value['full_work']=row['completed']==row['planned'] and ref['completed']==ref['planned']
        value['both_full_timely']=row['deadline_met']==row['planned'] and ref['deadline_met']==ref['planned']
        value['planned']=row['planned']
        value['policy_deadline_met']=row['deadline_met']
        value['reference_deadline_met']=ref['deadline_met']
        for name in ('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms','overlap_s'):
            value['delta_'+name]=row[name]-ref[name] if row[name] is not None and ref[name] is not None else None
        value['extra_service_failures']=ref['deadline_met']-row['deadline_met']
        ds=[value['delta_'+k] for k in ('energy_j','peak_ap_c','thermal_degree_seconds')]
        value['joint_nonworsening']=value['both_full_timely'] and all(v is not None and v<=1e-9 for v in ds)
        value['joint_strict']=value['joint_nonworsening'] and any(v < -1e-9 for v in ds)
        pairs.append(value)
    return pairs


def record(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return json.load(f)


def collect_representatives(folder,spec):
    records={}
    for file in sorted((Path(folder)/'items').glob('*.json.gz')):
        item=record(file);row=item['row'];rule=spec['representative_'+row['scope']]
        if any(row[k]!=v for k,v in rule.items()):continue
        wanted=('EFT_REFERENCE',r.BAND) if row['scope']=='resource' else (r.ALWAYS,r.ENTE)
        if row['policy'] in wanted:records[row['policy']]=item
    if len(records)!=4:raise ValueError('four preregistered representative records required')
    return records


def first_difference(records,scope):
    ids=('EFT_REFERENCE',r.BAND) if scope=='resource' else (r.ALWAYS,r.ENTE)
    a,b=(records[name] for name in ids);out=[]
    for x,y in zip(a['ledger'],b['ledger']):
        if x.get('backend')!=y.get('backend') or x.get('dispatch_ns')!=y.get('dispatch_ns'):
            out.append(dict(scope=scope,request_id=x['id'],task=x['task'],arrival_s=x['arrival_ns']/1e9,
                reference=ids[0],adaptation=ids[1],reference_backend=x.get('backend'),adaptation_backend=y.get('backend'),
                reference_start_s=x.get('dispatch_ns',0)/1e9 if 'dispatch_ns' in x else None,
                adaptation_start_s=y.get('dispatch_ns',0)/1e9 if 'dispatch_ns' in y else None,
                reference_response_ms=x.get('response_ns',0)/1e6 if 'response_ns' in x else None,
                adaptation_response_ms=y.get('response_ns',0)/1e6 if 'response_ns' in y else None))
    return out


def setup_plots():
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10,
                         'svg.hashsalt':'d1-external-rules-11','figure.dpi':110})


def save(fig,out,name):
    fig.savefig(out/(name+'.png'),dpi=200,bbox_inches='tight')
    fig.savefig(out/(name+'.svg'),bbox_inches='tight',metadata={'Date':None})
    plt.close(fig)


def figures(out,rows,groups,pairs,reps):
    setup_plots();out=Path(out)
    fig,ax=plt.subplots(figsize=(13,3.7));ax.axis('off')
    cells=[['강한 예상 응답 우선','도착 큐·공개 lane·개발 시간','공유 가드 안의 예상 응답','즉시 또는 실제 lane 반환 대기'],
           ['우리 에너지·AP 규칙','동일 입력과 현재 모형 상태','기한·열 제약 아래 예측 J','자원 선택 또는 제한된 대기'],
           ['Band HEFT 요청 적용','도착 작업·예상시간·자원 대기','최선 배정의 예상시간이 큰 작업','최선 자원이 바쁘면 다른 작업 확인'],
           ['Ente 시작 허용 적용','과거 활동·배터리·OS 열 상태','기기 상태 허용 + 활동 후15초','배경 시작 허용 또는 보류']]
    table=ax.table(cellText=cells,colLabels=['판단 규칙','관측 정보','선택 조건','행동'],cellLoc='left',loc='center',colWidths=[.19,.28,.26,.27])
    table.auto_set_font_size(False);table.set_fontsize(10);table.scale(1,2.6)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor('#dae0e7');cell.set_facecolor('#eaf0f7' if row==0 else 'white')
    ax.set_title('어떤 판단이 다른가: 자원 배정과 배경 시작 허용',fontsize=16,pad=15)
    save(fig,out,'01_판단규칙')
    for scope,ids in [('resource',('EFT_REFERENCE',r.BAND)),('gate',(r.ALWAYS,r.ENTE))]:
        fig,axes=plt.subplots(2,1,figsize=(12,5.8),sharex=True)
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        for ax,name in zip(axes,ids):
            item=reps[name]
            for row in item['ledger']:
                if 'dispatch_ns' not in row:continue
                y=0 if row['backend']=='CPU' else 1;start=row['dispatch_ns']/1e9;end=row['lane_available_ns']/1e9
                ax.broken_barh([(start,end-start)],(y-.28,.56),facecolors='#3e9c98' if row['task']=='classification' else '#c98542',edgecolors='white')
                ax.plot(start+row['response_ns']/1e9-(start-row['arrival_ns']/1e9),y,'k|',markersize=9)
            ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[name],loc='left');ax.grid(axis='x',alpha=.25)
            handles=[Patch(facecolor='#3e9c98',label='분류'),Patch(facecolor='#c98542',label='탐지'),
                     Line2D([],[],marker='|',color='black',linestyle='None',label='응답 준비/저장 경계')]
            if scope=='gate':
                ax.axvspan(36,65,color='#d65868',alpha=.10,label='활동 때문에 배경 시작 보류')
                handles.append(Patch(facecolor='#d65868',alpha=.15,label='활동 후 배경 시작 보류'))
            ax.legend(handles=handles,loc='upper right',fontsize=8)
        end=max(row['lane_available_ns']/1e9 for name in ids for row in reps[name]['ledger'] if 'lane_available_ns' in row)
        axes[-1].set_xlim(34.8,end+.6);axes[-1].set_xlabel('공통 원점 이후 초 · 막대=dispatch부터 실제 lane 반환 · 검은 표식=응답 경계')
        fig.suptitle('같은 대표 입력의 실행 시간표 · '+('큐 밀집' if scope=='resource' else '저부하·36/50초 활동'),fontsize=15)
        fig.tight_layout();save(fig,out,'02_'+('자원시간표' if scope=='resource' else '시작허용시간표'))
    policies=list(r.RESOURCE_POLICIES);primary=[x for x in rows if x['scope']=='resource' and x['family'] in ('low','sustained')]
    policy_labels=[LABELS[policy]+'\n기한 '+str(sum(x['deadline_met']==x['planned'] for x in primary if x['policy']==policy))+'/24조건'
                   for policy in policies]
    fig,axes=plt.subplots(1,3,figsize=(15,5.3));ys=np.arange(len(policies))
    for ax,name,title in zip(axes,['urgent_p95_ms','normal_mean_ms','service_failure'],['긴급 응답 P95 평균 (ms)','일반 완료 응답 평균 (ms)','전체 예정 요청 기한·서비스 실패 (%)']):
        values=[]
        for policy in policies:
            items=[x for x in primary if x['policy']==policy]
            values.append(100*(1-sum(x['deadline_met'] for x in items)/sum(x['planned'] for x in items)) if name=='service_failure' else mean(items,name))
        ax.barh(ys,values,color=COLORS);ax.set_yticks(ys,policy_labels if ax is axes[0] else []);ax.invert_yaxis();ax.set_title(title,fontsize=10);ax.grid(axis='x',alpha=.2)
    fig.suptitle('저부하·지속 도착의 응답과 전체 요청 서비스 · 전 조건 공개',fontsize=15)
    fig.tight_layout();save(fig,out,'03_응답완료비교')
    fig,axes=plt.subplots(1,3,figsize=(15,5.3))
    keys=['delta_energy_j','delta_peak_ap_c','delta_thermal_degree_seconds']
    for ax,key,title in zip(axes,keys,['전체120초 J 차이','최고 AP 차이 (°C)','유휴 기준 초과면적 차이 (°C·s)']):
        values=[mean([x for x in pairs if x['scope']=='resource' and x['family'] in ('low','sustained') and x['policy']==policy],key) for policy in policies]
        ax.barh(ys,values,color=COLORS);ax.set_yticks(ys,policy_labels if ax is axes[0] else []);ax.invert_yaxis();ax.axvline(0,color='#333',lw=.7);ax.set_title(title);ax.grid(axis='x',alpha=.2)
    fig.suptitle('강한 예상 응답 규칙 대비 동결 모형의 차이 · 작은 값은 실기기 개선 근거가 아님',fontsize=14)
    fig.tight_layout();save(fig,out,'04_에너지열비교')
    fig,axes=plt.subplots(1,2,figsize=(13,5.2))
    for ax,(scope,ids,title) in zip(axes,[('resource',('EFT_REFERENCE',r.BAND),'큐 밀집 · 자원 배정'),('gate',(r.ALWAYS,r.ENTE),'저부하 · 시작 허용')]):
        for i,name in enumerate(ids):
            item=reps[name];ax.plot(item['ap_times_s'],item['ap_path'],label=LABELS[name],lw=2,linestyle='-' if i==0 else '--')
        ax.set_title(title);ax.set_xlabel('원점 이후 초');ax.set_ylabel('모형 AP (°C)');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('같은 대표 입력의 AP 경로 · BAT·표면온도와 구분',fontsize=15)
    fig.tight_layout();save(fig,out,'05_온도경로')
    band=[x for x in pairs if x['policy']==r.BAND];families=list(r.old.FAMILIES)
    matrix=np.zeros((12,4));text=np.empty((12,4),dtype=object)
    for i,(seed,context) in enumerate((s,c) for s in study.SEEDS for c in r.old.SCENARIOS):
        for j,family in enumerate(families):
            x=next(v for v in band if v['seed']==seed and v['context']==context and v['family']==family)
            matrix[i,j]=3 if not x['both_full_timely'] else 2 if x['joint_strict'] else 1 if x['joint_nonworsening'] else 0
            text[i,j]=f"ΔJ {x['delta_energy_j']:+.4f}J\nΔAP {x['delta_peak_ap_c']:+.4f}°C\n기한 {x['policy_deadline_met']}/{x['planned']}"
    fig,ax=plt.subplots(figsize=(10,9));from matplotlib.colors import ListedColormap
    ax.imshow(matrix,cmap=ListedColormap(['#f4dab0','#d9e8ef','#a0d7bd','#e7b1b7']),vmin=0,vmax=3,aspect='auto')
    for i in range(12):
        for j in range(4):ax.text(j,i,text[i,j],ha='center',va='center',fontsize=8)
    ax.set_xticks(range(4),[FAMILIES[x] for x in families]);ax.set_yticks(range(12),[f'seed{str(s)[-1]} · {c}' for s in study.SEEDS for c in r.old.SCENARIOS])
    ax.set_xlabel('seed1~4 = 610810001~610810004 · 같은 입력의 Band 적용값에서 강한 EFT 값을 뺀 차이')
    ax.set_title('강한 예상 응답 규칙 대비 Band 요청 적용의 조건별 차이\n주황=상충 / 하늘=동률·공동 비악화 / 초록=공동 감소 / 분홍=비교쌍 기한 부적격',fontsize=12)
    fig.tight_layout();save(fig,out,'06_조건지도')
    gate=[g for g in groups if g['scope']=='gate' and g['policy']==r.ENTE and g['family']=='low']
    fig,axes=plt.subplots(1,3,figsize=(14,4.7));names=[ENVS[x['environment']] for x in gate]
    for ax,key,title in zip(axes,['completion_rate','timely_rate','energy_j'],['예정 요청 완료 (%)','예정 요청 기한 준수 (%)','전체120초 J (부분 처리 포함)']):
        values=[100*x[key] if key.endswith('rate') else x[key] for x in gate]
        ax.barh(range(len(gate)),values,color='#b47e80');ax.set_yticks(range(len(gate)),names if ax is axes[0] else []);ax.invert_yaxis();ax.set_title(title);ax.grid(axis='x',alpha=.2)
    fig.suptitle('Ente 시작 허용 · 같은 EFT 배정 / 합성 상태별 저부하 결과',fontsize=14)
    fig.tight_layout();save(fig,out,'07_시작허용조건')


def dashboard(out,rows,groups,pairs,reps,summary):
    data=json.dumps(dict(rows=rows,pairs=pairs,labels=LABELS,environments=ENVS,families=FAMILIES),ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    images=''.join(f'<a href="{html.escape(x.name)}"><img src="{html.escape(x.name)}" alt="{html.escape(x.stem)}"></a>' for x in sorted(Path(out).glob('*.png')))
    sources=study.read(study.BUNDLE/'sources.json')
    links=' · '.join(f'<a href="{html.escape(x["url"])}">{html.escape(x["system"]+" / "+Path(x["path"]).name)}</a>' for x in sources['files'] if Path(x['path']).name in ('compute_controller.dart','device_health_policy.dart','heterogeneous_earliest_finish_time_scheduler.cc','least_slack_first_scheduler.cc'))
    body='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>기존 시스템 판단 규칙 비교</title><style>
body{font-family:"Malgun Gothic",sans-serif;color:#18273b;background:#f4f7fa;margin:0}main{max-width:1320px;margin:auto;padding:30px}h1{font-size:29px;margin-bottom:12px}h2{font-size:21px}p{line-height:1.65}section{background:white;border:1px solid #dce3eb;border-radius:12px;padding:22px;margin:18px 0}.notice{border-left:5px solid #bd8054;background:#fff8ed;padding:15px}.cards{display:flex;gap:14px;flex-wrap:wrap}.card{background:#eaf1f7;padding:16px;min-width:170px}.card strong{font-size:23px;display:block}label{display:inline-block;margin:8px 15px 8px 0}select{padding:8px;max-width:230px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:9px;text-align:right;border-bottom:1px solid #dfe6ed;white-space:nowrap}th:first-child,td:first-child{text-align:left}thead{background:#edf2f7}.scroll{overflow:auto;max-height:650px}.figures{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:16px}.figures img{width:100%;border:1px solid #dbe2ea}a{color:#17658d}small{color:#4b6176}.bad{color:#a02740}.ok{color:#176a48}details{margin-top:16px}pre{white-space:pre-wrap;font-size:12px}button{padding:8px;background:#edf2f7;border:1px solid #ccd7e3;border-radius:5px}</style>
<main><h1>기존 시스템의 판단 규칙을 같은 모형에서 비교</h1>
<p>Ente의 배경 시작 허용과 Band HEFT의 요청 배정 흐름을 옮겼습니다. 실행 단위·자원을 바꾼 <b>제한적 재현 B</b>이며, 외부 앱 전체나 실제 제품을 실행한 비교는 아닙니다.</p>
<div class="cards"><div class="card"><strong>2개</strong>외부 규칙의 제한적 재현</div><div class="card"><strong>1,056행</strong>4 seed × 4 부하 × 3 시간문맥</div><div class="card"><strong>0회</strong>기기·ADB·학습 실행</div></div>
<section><h2>결과를 읽는 기준</h2><p id="headline"></p><p class="notice">Ente 활동·배터리·BAT·OS 열 상태는 합성 입력입니다. AP를 BAT로 바꾸지 않았습니다. 미완료로 에너지가 작아진 조건은 완료율·기한 위반과 함께 표시합니다. J/AP는 동결 A24 모형의 값이며 작은 차이를 실기기 개선으로 주장하지 않습니다. AP 안전 한도와 한도 초과 시간은 계산 불가입니다.</p>
<p><a href="../../REQUEST_EXTERNAL_RULES_PC_20261007.md">한국어 보고서</a> · <a href="README.md">재현·계약</a> · <a href="mapping.md">원 규칙 대응표</a> · <a href="results.csv">전체 결과 CSV</a> · <a href="paired_differences.csv">같은 입력 차이</a></p></section>
<section><h2>동일 입력 조건별 비교</h2><label>비교 대상 <select id="scope"><option value="resource">자원 배정 · 시작 항상 허용</option><option value="gate">배경 시작 허용 · 하위 EFT 동일</option></select></label>
<label>부하 <select id="family"><option value="all">전체 부하</option><option value="low">저부하</option><option value="sustained">지속 도착</option><option value="queue">큐 밀집</option><option value="burst">버스트</option></select></label>
<label>처리 문맥 <select id="context"><option value="all">전체 문맥</option><option value="mean">개발 평균</option><option value="short_context">짧은 전체 시간벡터</option><option value="long_context">긴 전체 시간벡터</option></select></label>
<label>상태 시나리오 <select id="environment"><option value="all">전체 상태</option></select></label><label>seed <select id="seed"><option value="all">전체 seed</option></select></label>
<p id="selected"></p><div class="scroll"><table><thead><tr><th>규칙 · 상태</th><th>조건</th><th>예정 요청</th><th>완료</th><th>기한 준수</th><th>긴급 P95 평균 ms</th><th>일반 응답 평균 ms</th><th>전체120초 J</th><th>AP 최고 °C</th><th>유휴 초과면적 °C·s</th><th>병행 초</th></tr></thead><tbody id="groups"></tbody></table></div>
<small>P95는 조건별 완료 응답 P95의 평균입니다. pooled P95·독립 기기 반복이 아닙니다. AP180 계산이 안 된 조건이 섞인 그룹은 AP 요약을 계산 불가로 표시합니다.</small>
<details><summary>개별 조건 전체 보기</summary><div class="scroll"><table><thead><tr><th>정책</th><th>seed / 부하 / 문맥 / 상태</th><th>완료/예정</th><th>기한/예정</th><th>긴급 P95 ms</th><th>J 차이</th><th>AP 최고 차이</th><th>동일 완료량</th></tr></thead><tbody id="details"></tbody></table></div></details></section>
<section><h2>판단 차이와 대표 일정</h2><p>대표는 결과 전에 최소 seed의 큐 밀집/mean과 저부하/mean/36·50초 활동으로 고정했습니다. 시간표 막대는 응답 이후 저장·worker 반환·lane 반환까지 포함합니다. 미지원 동시 실행은 금지합니다.</p><div class="figures">IMAGES</div></section>
<section><h2>원 출처와 재현 범위</h2><p>SOURCE_LINKS</p><p>Band LSF의 예상 기한 초과 early-drop과 MediaPipe LIVE_STREAM의 busy-frame 무시는 전량 완료 요구를 바꾸므로 비교를 보류했습니다. LiteRT priority 전달 API와 NPU Manager의 load/선점 기능은 현재 CPU/GPU 전체 요청 모형의 독립 정책으로 대체하지 않았습니다.</p><details><summary>실행·검증 수치</summary><pre>SUMMARY</pre></details></section>
</main><script>const DATA=DATA_JSON;
const fmt=(x,n=3)=>x===null||x===undefined?'계산 불가':Number(x).toFixed(n);const sum=(a,k)=>a.reduce((v,x)=>v+x[k],0);const mean=(a,k)=>a.some(x=>x[k]===null)?null:sum(a,k)/a.length;
for(const [k,v] of Object.entries(DATA.environments))environment.add(new Option(v,k));for(const v of [...new Set(DATA.rows.map(x=>x.seed))])seed.add(new Option(v,v));
const pairMap=new Map(DATA.pairs.map(x=>[[x.scope,x.environment,x.seed,x.family,x.context,x.policy].join('/'),x]));
function redraw(){const a=DATA.rows.filter(x=>x.scope===scope.value&&(family.value==='all'||x.family===family.value)&&(context.value==='all'||x.context===context.value)&&(seed.value==='all'||x.seed===Number(seed.value))&&(scope.value==='resource'||environment.value==='all'||x.environment===environment.value));environment.disabled=scope.value==='resource';
selected.textContent=`선택 ${a.length}행 · 같은 입력 기준: ${scope.value==='resource'?'강한 예상 응답 우선':'배경 시작 항상 허용 EFT'}`;const g=new Map();for(const x of a){const k=x.policy+'/'+x.environment; if(!g.has(k))g.set(k,[]);g.get(k).push(x)}
groups.innerHTML=[...g.values()].map(b=>`<tr><td>${DATA.labels[b[0].policy]}${b[0].scope==='gate'?' · '+DATA.environments[b[0].environment]:''}</td><td>${b.length}</td><td>${sum(b,'planned')}</td><td>${fmt(100*sum(b,'completed')/sum(b,'planned'),2)}%</td><td>${fmt(100*sum(b,'deadline_met')/sum(b,'planned'),2)}%</td><td>${fmt(mean(b,'urgent_p95_ms'))}</td><td>${fmt(mean(b,'normal_mean_ms'))}</td><td>${fmt(mean(b,'energy_j'),5)}</td><td>${fmt(mean(b,'peak_ap_c'),5)}</td><td>${fmt(mean(b,'thermal_degree_seconds'),5)}</td><td>${fmt(mean(b,'overlap_s'))}</td></tr>`).join('');
details.innerHTML=a.map(x=>{const p=pairMap.get([x.scope,x.environment,x.seed,x.family,x.context,x.policy].join('/'));return `<tr><td>${DATA.labels[x.policy]}</td><td>${x.seed} / ${DATA.families[x.family]} / ${x.context} / ${DATA.environments[x.environment]||'즉시 허용'}</td><td>${x.completed}/${x.planned}</td><td>${x.deadline_met}/${x.planned}</td><td>${fmt(x.urgent_p95_ms)}</td><td>${fmt(p.delta_energy_j,6)}</td><td>${fmt(p.delta_peak_ap_c,6)}</td><td>${p.full_work?'예':'아니오 · 부분 처리'}</td></tr>`}).join('');document.documentElement.dataset.filteredRows=String(a.length);}
for(const x of [scope,family,context,environment,seed])x.onchange=redraw;redraw();headline.textContent=HEADLINE_JSON;
</script></html>'''
    headline='Band 요청 단위 적용은 지속 도착12조건에서 전량·기한을 지키며 강한 EFT 대비 평균0.1317J·최고AP0.0218°C를 줄였습니다. 긴급P95는 동률입니다. 우리 열·에너지 규칙 두 개는 같은 지속 조건에서 기한 위반이 있었습니다. Ente 시작 허용은 일부 합성 상태에서 큰 지연·미완료가 생겼습니다. 차이는 동결 모형과 제한적 재현의 범위입니다.'
    body=body.replace('IMAGES',images).replace('SOURCE_LINKS',links).replace('SUMMARY',html.escape(json.dumps(summary,ensure_ascii=False,indent=2))).replace('DATA_JSON',data).replace('HEADLINE_JSON',json.dumps(headline,ensure_ascii=False))
    (Path(out)/'index.html').write_text(body,encoding='utf8')


def integrity(folder,rows):
    inputs=study.read(study.BUNDLE/'inputs.json');frozen,_=r.p.inputs(r.p.BUNDLE)
    by={(x['seed'],x['family']):x['tickets'] for x in inputs['workloads']}
    counts=0;rounding=0;source=study.check_frozen();canonical={};quiet=[];cost_error=0.;ap_error=0.
    for file in sorted((Path(folder)/'items').glob('*.gz')):
        item=record(file);row=item['row'];study.audit(item,by[row['seed'],row['family']]);counts+=len(item['ledger'])
        for x in item['ledger']:
            if x['status']=='succeeded':
                boundary=x['output_ready_ns' if x['priority']=='urgent' else 'persist_complete_ns']
                rounding=max(rounding,abs(x['response_ns']-(boundary-x['arrival_ns'])))
        if row['seed']==study.SEEDS[0]:
            actual= r.p.model.costs(item['segments'],inputs['initial'],item['ap_times_s'],frozen,float(item['ap_end_s']))
            cost_error=max(cost_error,abs(actual['whole_120s_j']-row['energy_j']))
            ap_error=max(ap_error,max(abs(a-b) for a,b in zip(actual['ap_path'],item['ap_path'])))
        keys=('id','status','backend','dispatch_ns','lane_available_ns','response_ns')
        schedule=tuple(tuple(x.get(k) for k in keys) for x in item['ledger'])
        key=(row['seed'],row['family'],row['context'])
        if row['policy']=='EFT_REFERENCE':canonical[key]=schedule
        elif row['policy']==r.ALWAYS:
            if canonical[key]!=schedule:raise ValueError('common lower EFT changed by environment')
        elif row['policy']==r.ENTE and row['environment']=='quiet_healthy':
            quiet.append(canonical[key]==schedule)
    if counts!=sum(x['planned'] for x in rows) or not all(quiet):raise ValueError('denominator/quiet gate equivalence')
    users=study.read(Path(folder)/'preserved_user_files.json')
    assert all(r.p.digest(study.ROOT/name)==sha for name,sha in users.items())
    return dict(status='PASSED',utc=study.utc(),source_head=source['base_head'],source_dirty=True,
                rows=len(rows),requests_audited=counts,max_response_representation_difference_ns=rounding,
                first_seed_J_recalculation_max_difference_j=cost_error,first_seed_recalculations=264,
                first_seed_AP_recalculation_max_difference_c=ap_error,
                always_EFT_same_schedule_all_environments=True,quiet_gate_same_schedule_cases=len(quiet),
                old_source_files=len(source['old_sources']),user_files=len(users),
                device_commands=0,environment_runs=0)


def run(folder,out,shared=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    source=study.BUNDLE
    result_source=source/'results.csv' if shared else Path(folder)/'results.csv'
    rows=typed_rows(result_source);spec=study.read(source/'contract.json')
    if len(rows)!=spec['logical_rows']:raise ValueError('complete registered result table required')
    groups=group_summary(rows);pairs=paired(rows)
    if result_source.resolve()!=(out/'results.csv').resolve():
        import shutil
        shutil.copyfile(result_source,out/'results.csv')
    reps=study.read(source/'representatives.json') if shared else collect_representatives(folder,spec)
    study.write(out/'representatives.json',reps)
    differences=first_difference(reps,'resource')+first_difference(reps,'gate')
    study.csv_write(out/'policy_summary.csv',groups);study.csv_write(out/'paired_differences.csv',pairs)
    study.csv_write(out/'representative_differences.csv',differences)
    band=[x for x in pairs if x['policy']==r.BAND]
    completion=study.read(source/'completion.json') if shared else study.read(Path(folder)/'completion.json')
    summary=dict(completion=completion,band_vs_strong_EFT=dict(cases=len(band),
                 full_timely_cases=sum(x['both_full_timely'] for x in band),
                 strict_joint_reduction=sum(x['joint_strict'] for x in band),
                 mean_delta_urgent_p95_ms=mean(band,'delta_urgent_p95_ms'),
                 mean_delta_energy_j=mean(band,'delta_energy_j'),
                 mean_delta_peak_ap_c=mean(band,'delta_peak_ap_c')),
                 resource_primary_groups=[x for x in groups if x['scope']=='resource' and x['family'] in ('low','sustained')],
                 gate_groups=[x for x in groups if x['scope']=='gate' and x['policy']==r.ENTE],
                 conditions=48,policy_tuning=0,active_external_rules=2,reproduction_level='B',
                 AP_safety_limit=None,device_commands=0,physical_advantage_proven=False)
    if not shared:
        study.write(out/'integrity_verification.json',integrity(folder,rows))
    study.write(out/'summary.json',summary);study.write(out/'completion.json',completion)
    figures(out,rows,groups,pairs,reps);dashboard(out,rows,groups,pairs,reps,summary)
    study.write(out/'report_verification.json',dict(utc=study.utc(),command='CSV and saved representative records -> figures/dashboard; no simulator calls',
                report_source_sha256=r.p.digest(Path(__file__)),environment_runs=0,
                files={x.name:r.p.digest(x) for x in sorted(out.iterdir()) if x.is_file() and x.name!='report_verification.json'}))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default=str(study.LOCAL/'comparison'))
    parser.add_argument('--output',default=str(study.BUNDLE));parser.add_argument('--shared',action='store_true');args=parser.parse_args()
    run(args.folder,args.output,args.shared)
