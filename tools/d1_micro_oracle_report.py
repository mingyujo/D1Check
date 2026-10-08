"""Sealed micro-oracle results, discrete-space certificates and offline charts."""
from __future__ import annotations
import csv,gzip,hashlib,html,json,statistics
from pathlib import Path
from tools.d1_edd_ect_residual_report import compare

ROOT=Path(__file__).resolve().parents[1];BUNDLE=ROOT/'docs/results/micro_oracle_01';LOCAL=ROOT/'output/micro_oracle_20261009_v1'
BAND='BAND_HEFT_WHOLE_REQUEST_ADAPT_V1';TRITON='TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1'
LABELS={BAND:'Band 요청 적용',TRITON:'Triton 요청 적용','IE_EDD_ECT_LANE_PC_V1':'기한 우선 ECT',
    'IE_RESPONSE_SLACK_ECT_MICRO_V1':'응답 여유시간 ECT','IE_RESPONSE_SLACK_CPU_FLEX_MICRO_V1':'여유시간·CPU 보호'}
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8',newline='\n')
def csv_write(p,rows):
    with Path(p).open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)


def load_items():
    es=[json.loads(line) for line in (LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()];done={e['identity']:e for e in es if e['event']=='completed'};out={}
    for p in (LOCAL/'items').glob('*.json.gz'):
        item=json.loads(gzip.decompress(p.read_bytes()));id=item['row']['identity']
        assert done[id]['artifact_sha256']==sha(p),'unsealed replay'
        out[id]=item
    return out,es


def report():
    complete=read(BUNDLE/'completion.json');assert complete['status']=='completed'
    cases=[read(p) for p in sorted(BUNDLE.glob('case_*.json'))];assert len(cases)==24
    items,es=load_items();rows=[];proofs=[];paired=[]
    for i,case in enumerate(cases):
        base=case['baselines'][BAND];ref=[case['baselines'][b] for b in (BAND,TRITON)];answer=case['oracle'];counts=answer['counts']
        assert counts['raw']==counts['visited']+counts['pruned'] and answer['status']=='exhaustive_complete'
        for policy,row in case['baselines'].items():
            rows.append(row)
            if policy!=BAND:paired.append(dict(case=i,seed=row['seed'],family=row['family'],context=row['context'],policy=policy,**compare(row,base)))
        j=answer['energy_min_ap_cap'];ap=answer['ap_min_energy_cap']
        verified=case['verified']['min_J'];ps=[compare(verified,r) for r in ref]
        proofs.append(dict(case=i,seed=case['case']['seed'],family=case['case']['family'],context=case['case']['context'],
            **counts,band_j=base['energy_j'],band_ap_c=base['peak_ap_c'],grid_min_j=j['energy_j'],grid_min_ap_c=ap['peak_ap_c'],
            delta_min_j_vs_band=j['energy_j']-base['energy_j'],delta_min_ap_vs_band=ap['peak_ap_c']-base['peak_ap_c'],
            relaxed_lower_bound_j=answer['energy_relaxation_lower_bound_j'],band_above_lower_bound_j=base['energy_j']-answer['energy_relaxation_lower_bound_j'],
            native_witness_nonworse_both=all(p['nonworse'] for p in ps),native_witness_joint_gain_both=all(p['joint_gain'] for p in ps),
            pulse_j_error=j['energy_j']-verified['energy_j'],pulse_ap_error=j['peak_ap_c']-verified['peak_ap_c'],oracle_wall_s=answer['host_wall_s']))
    robust=[];by={(c['case']['seed'],c['case']['family'],c['case']['context']):c for c in cases}
    for row in read(BUNDLE/'robustness.json'):
        actual=row['row'];base=by[actual['seed'],actual['family'],actual['context']]['baselines'][BAND]
        robust.append(dict(nominal_case=row['nominal_case'],role=row['role'],seed=actual['seed'],family=actual['family'],actual_context=actual['context'],
            planned=actual['planned'],completed=actual['completed'],urgent_failures=actual['urgent_service_failure'],normal_failures=actual['normal_service_failure'],
            **compare(actual,base)))
    summaries=[]
    for p in LABELS:
        group=[r for r in rows if r['policy']==p]
        summaries.append(dict(policy=p,conditions=24,planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),
            urgent_failures=sum(r['urgent_service_failure'] for r in group),normal_failures=sum(r['normal_service_failure'] for r in group),
            urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in group),normal_mean_ms=statistics.mean(r['normal_mean_ms'] for r in group),
            energy_j=statistics.mean(r['energy_j'] for r in group),peak_ap_c=statistics.mean(r['peak_ap_c'] for r in group)))
    protection_calls=sum(d.get('reason')=='protect_arrived_cpu_only_deadline' for item in items.values() for d in item['result']['decisions'])
    summary=dict(cases=24,variable_requests_per_case=4,original_engine_runs=len(items),consumption=complete['consumption'],
        raw_calendars=sum(p['raw'] for p in proofs),visited_calendars=sum(p['visited'] for p in proofs),safe_pruned=sum(p['pruned'] for p in proofs),
        capacity_valid=sum(p['capacity_valid'] for p in proofs),service_valid=sum(p['service_valid'] for p in proofs),joint_gain_calendars=sum(p['joint_gain'] for p in proofs),
        joint_gain_conditions=sum(p['joint_gain']>0 for p in proofs),native_witnesses_nonworse=sum(p['native_witness_nonworse_both'] for p in proofs),
        maximum_min_j_difference_j=max(abs(p['delta_min_j_vs_band']) for p in proofs),maximum_min_ap_difference_c=max(abs(p['delta_min_ap_vs_band']) for p in proofs),
        relaxed_energy_gap_range_j=[min(p['band_above_lower_bound_j'] for p in proofs),max(p['band_above_lower_bound_j'] for p in proofs)],
        robust_replays=len(robust),robust_nonworse=sum(p['nonworse'] for p in robust),robust_service_preserved=sum(p['service_preserved'] for p in robust),
        robust_urgent_failures=sum(p['urgent_failures'] for p in robust),robust_normal_failures=sum(p['normal_failures'] for p in robust),
        robust_max_p95_regression_ms=max(p['delta_urgent_p95_ms'] for p in robust),protection_calls=protection_calls,
        total_planned=sum(i['row']['planned'] for i in items.values()),total_completed=sum(i['row']['completed'] for i in items.values()),
        scope='exact declared discrete calendar space plus native engine replay; small already-consumed development subsets; not continuous/online/global/phone optimality',
        no_policy_promotion=True,thermal_error_to_service_effect='unsupported; no invented coupling')
    csv_write(BUNDLE/'policy_results.csv',rows);csv_write(BUNDLE/'policy_summary.csv',summaries);csv_write(BUNDLE/'pairs_vs_band.csv',paired)
    csv_write(BUNDLE/'oracle_certificates.csv',proofs);csv_write(BUNDLE/'robustness_results.csv',robust)
    csv_write(BUNDLE/'execution_receipts.csv',[{k:e.get(k) for k in ('event','utc','number','identity','kind')} for e in es])
    write(BUNDLE/'summary.json',summary)
    representative=3 # first seed queue mean, fixed before seeing outcomes
    reps={p:items[f'base/{representative}/{p}'] for p in LABELS}
    witness=cases[representative]['verified']['min_J']['identity'];reps['ORACLE']=items[witness]
    write(BUNDLE/'representatives.json',reps);plots(proofs,robust,reps);dashboard(proofs,robust,summaries,summary)
    return summary


def plots(proofs,robust,reps):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False});out=BUNDLE/'figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    axes[0].bar(range(24),[p['delta_min_j_vs_band'] for p in proofs]);axes[1].bar(range(24),[p['delta_min_ap_vs_band'] for p in proofs])
    for ax in axes:ax.axhline(0,color='grey');ax.set_xlabel('고정 조건 번호 0…23');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('최소 J와 Band 차이 J');axes[1].set_ylabel('최소 AP와 Band 차이 °C');fig.suptitle('유한 공간 최적해와 Band — 수치 반올림 수준의 차이')
    fig.savefig(out/'01_최적일정과기준차이.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,5),layout='constrained');ax.bar(range(24),[p['band_above_lower_bound_j'] for p in proofs]);ax.set_xlabel('고정 조건 번호');ax.set_ylabel('Band J - 낙관적 에너지 하한 J');ax.set_title('서비스·AP를 무시한 에너지 하한 — 달성 가능한 이득이 아님');ax.grid(axis='y',alpha=.2)
    fig.savefig(out/'02_에너지하한과여지.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(6,1,figsize=(12,10),sharex=True,layout='constrained')
    for ax,(p,item) in zip(axes,reps.items()):
        for row in item['result']['ledger']:
            start=row['dispatch_ns']/1e9;end=row['lane_available_ns']/1e9;y=0 if row['backend']=='CPU' else 1
            ax.broken_barh([(start,end-start)],(y-.3,.6),facecolors='#397cb3' if row['priority']=='urgent' else '#eda040')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS.get(p,'유한 최적 일정'),loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(35,39);axes[-1].set_xlabel('공통 시간 초');fig.suptitle('사전 지정 첫 queue/mean — 전체 lane 점유를 비교')
    fig.savefig(out/'03_대표작업시간표.png',dpi=150);plt.close(fig)
    unique=[r for r in robust if r['role']=='min_J'];fig,ax=plt.subplots(figsize=(12,5),layout='constrained');ax.bar(range(len(unique)),[r['delta_urgent_p95_ms'] for r in unique])
    ax.set_xticks(range(len(unique)),[f'{r["seed"]-812000000} {r["family"]} {r["actual_context"].split("_")[0]}' for r in unique],rotation=65,ha='right');ax.set_ylabel('같은 문맥 Band 대비 긴급 P95 차이 ms');ax.grid(axis='y',alpha=.2);ax.set_title('같은 평균 일정의 실행시간 오차 반응 — 양수는 응답 악화')
    fig.savefig(out/'04_처리시간문맥교차.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,5),layout='constrained');ax.semilogy(range(24),[p['raw'] for p in proofs],label='전체 선언 공간');ax.semilogy(range(24),[p['visited'] for p in proofs],label='안전 제거 후 방문');ax.semilogy(range(24),[p['service_valid'] for p in proofs],label='용량·서비스 적격');ax.set_xlabel('고정 조건 번호');ax.set_ylabel('일정 수 로그축');ax.legend();ax.grid(alpha=.2);ax.set_title('전수 보존 — 제거 근거는 기한·응답의 필요조건')
    fig.savefig(out/'05_전수공간과제약.png',dpi=150);plt.close(fig)


def dashboard(proofs,robust,summaries,summary):
    def table(rows,fields):
        body=''
        for row in rows:
            cells=[]
            for k,_ in fields:
                v=row[k];v=LABELS.get(v,v) if isinstance(v,str) else v
                cells.append('<td>'+html.escape(f'{v:.9g}' if isinstance(v,float) else str(v))+'</td>')
            body+='<tr>'+''.join(cells)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+label+'</th>' for _,label in fields)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    body='<h1>작은 요청열의 최적 일정 비교</h1><p>4요청·24조건. Band보다 공동 개선하는 일정0. 정확성은100ms/3s + Band시각의 유한 공간에 한정합니다.</p>'
    body+='<p><a href="README.md">범위와 결과</a> · <a href="oracle_certificates.csv">전수 인증 CSV</a> · <a href="robustness_results.csv">문맥 교차 CSV</a></p><p>최고 AP는 모형값이고 표면온도가 아닙니다. 미래를 아는 참고 일정이며 온라인 정책 최적성이나 실제 폰 우위가 아닙니다.</p><input id="filter" placeholder="정책/부하 검색">'
    body+=table(summaries,[('policy','규칙'),('completed','완료'),('urgent_p95_ms','긴급 P95 ms'),('normal_mean_ms','일반 평균 ms'),('energy_j','전체 J'),('peak_ap_c','최고 AP °C')])
    body+=table(proofs,[('case','조건'),('family','부하'),('context','문맥'),('raw','전체 공간'),('visited','방문'),('joint_gain','공동감소 일정'),('band_above_lower_bound_j','에너지 하한 차이 J'),('delta_min_j_vs_band','최소 J 차이'),('delta_min_ap_vs_band','최소 AP 차이')])
    body+=table(robust,[('nominal_case','원 조건'),('role','목적'),('actual_context','실행 문맥'),('service_preserved','서비스 유지'),('nonworse','비용 포함 비악화'),('delta_urgent_p95_ms','긴급 P95 차이 ms'),('delta_energy_j','J 차이'),('delta_peak_ap_c','AP 차이 °C')])
    for p in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{p.name}" alt="{p.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>작은 최적 일정 확인</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;max-width:1450px;color:#263142}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:18px 0}input{padding:10px;width:300px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')


if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False,indent=2))
