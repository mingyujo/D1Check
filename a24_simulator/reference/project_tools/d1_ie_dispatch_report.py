"""Read completed IE results, make CSV/figures/offline report; no plant starts."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import html
import json
from pathlib import Path
import statistics
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/ie_dispatch_01'
LOCAL=ROOT/'output/ie_dispatch_20261008_v1'
NEW=('IE_FIFO_ECT_LANE_PC_V1','IE_SPT_ECT_LANE_PC_V1','IE_EDD_ECT_LANE_PC_V1')
BASES=('SHARED_EFT','EFT_REFERENCE','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1',
       'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1','ENERGY_AP_REQUEST_V1','ARRIVED_QUEUE_J_PEAK_AREA_V1')
LABELS=dict(zip(NEW,('선착순 + ECT','짧은 작업 우선 + ECT','기한 우선 + ECT')))
LABELS.update(SHARED_EFT='우리 공용 EFT 기준',EFT_REFERENCE='우리 선두 EFT 기준',
    BAND_HEFT_WHOLE_REQUEST_ADAPT_V1='Band 전체 요청 적용',
    TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1='Triton 제한 해제 적용',
    ENERGY_AP_REQUEST_V1='우리 에너지·AP 규칙',ARRIVED_QUEUE_J_PEAK_AREA_V1='우리 도착 큐 열 규칙')
EPS=1e-9


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8',newline='\n')
def csv_write(path,rows):
    with Path(path).open('w',encoding='utf8',newline='') as stream:
        writer=csv.DictWriter(stream,list(rows[0]));writer.writeheader();writer.writerows(rows)


def scalar(value):
    if value=='':return None
    if value=='True':return True
    if value=='False':return False
    try:return json.loads(value)
    except ValueError:return value


def load_rows(path=None):
    with Path(path or BUNDLE/'results.csv').open(encoding='utf8',newline='') as stream:
        return [{k:scalar(v) for k,v in r.items()} for r in csv.DictReader(stream)]


def key(r):return (r['seed'],r['family'],r['context'])
def delta(a,b):return None if a is None or b is None else a-b


def compare(rows):
    by={(key(r),r['policy']):r for r in rows};out=[]
    if len(by)!=len(rows):raise ValueError('duplicate identity')
    conditions={key(r) for r in rows}
    for k in sorted(conditions):
        for policy in NEW:
            r=by[(k,policy)]
            for base in BASES:
                b=by[(k,base)]
                full=r['completed']==r['planned'] and b['completed']==b['planned']
                p95=delta(r['urgent_p95_ms'],b['urgent_p95_ms'])
                service=full and p95 is not None and p95<=EPS and \
                    r['urgent_service_failure']<=b['urgent_service_failure'] and \
                    r['normal_service_failure']<=b['normal_service_failure']
                ap=delta(r['peak_ap_c'],b['peak_ap_c']);j=delta(r['energy_j'],b['energy_j'])
                eligible=service and ap is not None and j is not None
                out.append(dict(seed=k[0],family=k[1],context=k[2],policy=policy,baseline=base,
                    full_work=full,service_preserved=service,cost_eligible=eligible,
                    all_deadlines_met=r['deadline_met']==r['planned'],
                    delta_urgent_p95_ms=p95,delta_normal_mean_ms=delta(r['normal_mean_ms'],b['normal_mean_ms']),
                    delta_completed=r['completed']-b['completed'],delta_deadline_met=r['deadline_met']-b['deadline_met'],
                    delta_energy_j=j,delta_peak_ap_c=ap,
                    heat_with_nonincreasing_energy=eligible and ap < -EPS and j<=EPS,
                    joint_gain=eligible and ap < -EPS and j < -EPS,
                    joint_gain_all_deadlines=eligible and r['deadline_met']==r['planned'] and ap < -EPS and j < -EPS))
    return out


def average(values):
    xs=[x for x in values if x is not None];return statistics.mean(xs) if xs else None


def summaries(rows, pairs):
    summaries=[];pair_summaries=[]
    for scope,families in [('all',('low','queue','burst','sustained')),('primary',('low','sustained'))]:
        for policy in (*BASES,*NEW):
            rs=[r for r in rows if r['policy']==policy and r['family'] in families]
            summaries.append(dict(scope=scope,policy=policy,conditions=len(rs),
                planned=sum(r['planned'] for r in rs),completed=sum(r['completed'] for r in rs),
                incomplete=sum(r['incomplete'] for r in rs),urgent_failures=sum(r['urgent_service_failure'] for r in rs),
                normal_failures=sum(r['normal_service_failure'] for r in rs),
                all_deadline_conditions=sum(r['deadline_met']==r['planned'] for r in rs),
                mean_condition_urgent_p95_ms=average(r['urgent_p95_ms'] for r in rs),
                mean_condition_normal_ms=average(r['normal_mean_ms'] for r in rs),
                mean_energy_j=average(r['energy_j'] for r in rs),mean_peak_ap_c=average(r['peak_ap_c'] for r in rs),
                mean_overlap_s=average(r['overlap_s'] for r in rs),
                mean_gpu_requests=average(r['classification_gpu'] for r in rs)))
        for policy in NEW:
            for base in BASES:
                ps=[r for r in pairs if r['policy']==policy and r['baseline']==base and r['family'] in families]
                es=[r for r in ps if r['cost_eligible']]
                pair_summaries.append(dict(scope=scope,policy=policy,baseline=base,conditions=len(ps),
                    service_preserved=sum(r['service_preserved'] for r in ps),
                    cost_eligible=len(es),heat_nonincreasing_energy=sum(r['heat_with_nonincreasing_energy'] for r in ps),
                    joint_gain=sum(r['joint_gain'] for r in ps),
                    joint_gain_all_deadlines=sum(r['joint_gain_all_deadlines'] for r in ps),
                    mean_delta_urgent_p95_ms=average(r['delta_urgent_p95_ms'] for r in ps),
                    mean_delta_normal_mean_ms=average(r['delta_normal_mean_ms'] for r in ps),
                    mean_delta_energy_j_all=average(r['delta_energy_j'] for r in ps),
                    mean_delta_peak_ap_c_all=average(r['delta_peak_ap_c'] for r in ps),
                    mean_delta_energy_j_eligible=average(r['delta_energy_j'] for r in es),
                    mean_delta_peak_ap_c_eligible=average(r['delta_peak_ap_c'] for r in es)))
    return summaries,pair_summaries


def representatives():
    c=read(BUNDLE/'contract.json');rep=c['representative'];items={}
    done=read(BUNDLE/'completion.json')
    for path in (LOCAL/'items').glob('*.gz'):
        if path.name.startswith(f"{rep['seed']}_{rep['family']}_{rep['context']}_"):
            if sha(path)!=done['new_item_hashes'][path.name]:raise ValueError('new representative drift')
            item=json.loads(gzip.decompress(path.read_bytes()));items[item['row']['policy']]=item
    previous=ROOT/'output/reserved_thermal_20261008_v1/final_rule_only_v1/items'
    oldcheck=read(ROOT/c['prior_verification_path'])
    oldreg_path=ROOT/'docs/results/reserved_thermal_01/final_rule_only/registration.json'
    if sha(oldreg_path)!=oldcheck['outputs']['registration.json']:raise ValueError('old registration drift')
    oldreg=read(oldreg_path);inputs=read(ROOT/c['input_path'])
    work_index=next(i for i,w in enumerate(inputs['workloads']) if (w['seed'],w['family'])==(rep['seed'],rep['family']))
    condition_index=work_index*len(oldreg['contexts'])+oldreg['contexts'].index(rep['context'])
    for policy in BASES:
        index=condition_index*len(oldreg['policies'])+oldreg['policies'].index(policy)
        name=f'{index:04d}.json.gz';path=previous/name
        if sha(path)!=oldcheck['local_item_hashes'][name]:raise ValueError('representative SHA drift')
        item=json.loads(gzip.decompress(path.read_bytes()));r=item['row']
        if key(r)!=(rep['seed'],rep['family'],rep['context']) or r['policy']!=policy:raise ValueError('representative identity')
        items[policy]=item
    if set(items)!=set(NEW+BASES):raise ValueError('representative missing')
    # Share complete representative request ledgers and modeled paths. Detailed
    # callback/candidate logs stay in their immutable local raw items.
    items={policy:dict(row=item['row'],result=dict(ledger=item['result']['ledger'],
           metrics=item['result']['metrics']),curves=item['curves']) for policy,item in items.items()}
    write(BUNDLE/'representatives.json',dict(selection='pre-registered first seed/queue/mean',condition=rep,items=items))
    return items


def figures(rows,pairs,summary,reps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    import numpy as np
    plt.rcParams.update({'font.family':['Malgun Gothic','DejaVu Sans'],'axes.unicode_minus':False,'font.size':9})
    folder=BUNDLE/'figures';folder.mkdir(exist_ok=True)
    def save(fig,name):
        fig.tight_layout();fig.savefig(folder/(name+'.png'),dpi=150,bbox_inches='tight');plt.close(fig)
    policies=(*BASES,*NEW)
    fig,axes=plt.subplots(2,2,figsize=(14,10))
    rs=[r for r in summary if r['scope']=='all']
    names=[LABELS[r['policy']] for r in rs]
    for ax,field,title in zip(axes.flat,('urgent_failures','normal_failures','mean_condition_urgent_p95_ms','mean_condition_normal_ms'),
          ('긴급 서비스 실패 수','일반 서비스 실패 수','조건별 긴급 P95 평균(ms)','조건별 일반 완료시간 평균(ms)')):
        ax.barh(names,[r[field] for r in rs]);ax.set_title(title);ax.invert_yaxis();ax.grid(axis='x',alpha=.25)
    fig.suptitle('전체 192조건 · 같은 요청 전량을 기준으로 평가',fontsize=14)
    save(fig,'01_응답과기한')
    fig,axes=plt.subplots(1,2,figsize=(14,6))
    for ax,base in zip(axes,('SHARED_EFT','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1')):
        for policy,marker,color in zip(NEW,('o','s','^'),('#277cbd','#d66a29','#6b4595')):
            ps=[r for r in pairs if r['policy']==policy and r['baseline']==base]
            good=[r for r in ps if r['cost_eligible'] and r['all_deadlines_met']]
            bad=[r for r in ps if not (r['cost_eligible'] and r['all_deadlines_met'])]
            ax.scatter([r['delta_energy_j'] for r in bad],[r['delta_peak_ap_c'] for r in bad],marker=marker,color=color,alpha=.18)
            ax.scatter([r['delta_energy_j'] for r in good],[r['delta_peak_ap_c'] for r in good],marker=marker,color=color,s=35,label=LABELS[policy])
        ax.axhline(0,color='gray');ax.axvline(0,color='gray');ax.set_xlabel('전체 기기 에너지 차이(J)');ax.set_ylabel('최고 모형 AP 차이(°C)')
        ax.set_title(LABELS[base]+' 대비\n연한 점: 전체 기한 또는 상대 서비스 조건 미충족');ax.legend(fontsize=8);ax.grid(alpha=.2)
    save(fig,'02_에너지와AP차이')
    fig,axes=plt.subplots(len(policies),1,figsize=(14,15),sharex=True)
    for ax,policy in zip(axes,policies):
        for r in reps[policy]['result']['ledger']:
            if 'dispatch_ns' not in r:continue
            start=r['dispatch_ns']/1e9;end=r.get('lane_available_ns',120e9)/1e9
            ax.broken_barh([(start,end-start)],(0 if r['backend']=='CPU' else 1,.7),facecolors='#2378ae' if r['task']=='classification' else '#dc8a32')
            boundary=r.get('output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns')
            if boundary is not None:ax.plot(boundary/1e9,.35 if r['backend']=='CPU' else 1.35,'k.',markersize=3)
        ax.set_yticks([.35,1.35],['CPU','GPU']);ax.set_title(LABELS[policy],loc='left');ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlabel('시각(초) · 막대 끝=실제 lane 반환 · 점=응답 완료')
    fig.suptitle('사전 고정 대표 조건: 첫 seed · 큐 부하 · mean',fontsize=14)
    save(fig,'03_대표실행시간표')
    fig,ax=plt.subplots(figsize=(13,6))
    for policy in policies:
        curves=reps[policy]['curves'];ax.plot(curves['ap_times_s'],curves['ap_path'],label=LABELS[policy],linewidth=1.4)
    ax.set_xlabel('시각(초)');ax.set_ylabel('모형 AP 온도(°C)');ax.set_title('같은 대표 조건의 35..180초 AP 경로 · 표면 온도 아님')
    ax.legend(ncol=3,fontsize=8);ax.grid(alpha=.2);save(fig,'04_대표AP경로')
    fig,axes=plt.subplots(3,1,figsize=(15,9),sharex=True)
    keys=sorted({key(r) for r in rows});cmap=ListedColormap(['#c75252','#bcbcbc','#edba64','#3d9e78'])
    for ax,policy in zip(axes,NEW):
        data=[]
        for base in ('SHARED_EFT','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1'):
            ps={key(r):r for r in pairs if r['policy']==policy and r['baseline']==base}
            data.append([3 if ps[k]['joint_gain_all_deadlines'] else 2 if ps[k]['heat_with_nonincreasing_energy'] and ps[k]['all_deadlines_met'] else 1 if ps[k]['service_preserved'] else 0 for k in keys])
        ax.imshow(np.array(data),aspect='auto',cmap=cmap,vmin=0,vmax=3,interpolation='nearest')
        ax.set_yticks([0,1],['공용 EFT 대비','Band 적용 대비']);ax.set_title(LABELS[policy],loc='left')
    axes[-1].set_xlabel('전체 192조건(고정 seed/부하/문맥 순서)');fig.suptitle('빨강: 서비스 악화 · 회색: 전체기한/비용 개선 미충족 · 노랑: 전기한+열 감소/J동률 · 초록: 전기한+J/AP공동감소')
    save(fig,'05_조건별판정지도')


def table(rows,fields,labels=None):
    labels=labels or fields
    text='<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in labels)+'</tr></thead><tbody>'
    for row in rows:
        text+='<tr>'+''.join('<td>'+html.escape(LABELS.get(row[f],row[f]) if isinstance(row[f],str) else
            '계산 불가' if row[f] is None else f'{row[f]:.4f}' if isinstance(row[f],float) else str(row[f]))+'</td>' for f in fields)+'</tr>'
    return text+'</tbody></table>'


def render(summary,pairsummary,completion):
    s=[r for r in summary if r['scope']=='all'];ps=[r for r in pairsummary if r['scope']=='primary' and r['baseline'] in ('SHARED_EFT','BAND_HEFT_WHOLE_REQUEST_ADAPT_V1')]
    parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>산업공학 규칙 비교</title>',
        '<style>body{font:16px "Malgun Gothic",sans-serif;background:#f4f7fa;color:#183044;margin:32px auto;max-width:1500px;padding:0 24px}h1,h2{color:#122c45}table{border-collapse:collapse;background:white;font-size:14px;width:100%;margin:20px 0}th,td{border:1px solid #d6dfe7;padding:10px;text-align:right}th{background:#e4eef6}td:first-child{text-align:left}img{max-width:100%;background:white;margin:14px 0}p{line-height:1.65}.scroll{overflow:auto}input{font-size:17px;padding:10px}a{color:#145b9c}</style>',
        '<h1>산업공학 규칙을 휴대폰 자원 배정에 적용하면?</h1>',
        '<p>완료된 192조건 × 9정책 = 1,728행. 새 규칙 576실행 + 기존 완료 결과 1,152행 재사용. 튜닝·RL학습·기기 실행 0회. 이미 본 합성 조건의 진단 비교이며 독립 확인이 아니다.</p>',
        '<p><b>ECT는 자원 선택, FIFO/SPT/EDD는 요청 순서다.</b> ECT는 전체 5단계의 lane 반환을 최소화한다. 긴급 응답은 OUTPUT_READY, 일반 완료는 PERSISTED에서 별도로 측정한다. 원 제조 알고리즘·현업 제품 전체의 실행 결과가 아니다.</p>',
        '<p>FIFO=도착순 · SPT=지원 자원 중 최소 mean 전체 점유시간순 · EDD=절대 응답 기한순. 세 정책은 동일 ECT 자원 선택을 사용한다. 원 출처·동점·대기·변경 범위는 <a href="mapping.md">대응표</a>, 수치는 <a href="results.csv">전체 CSV</a>와 <a href="pairs.csv">모든 쌍</a>에 보존한다.</p>',
        '<h2>전체 요청과 서비스</h2>',table(s,['policy','conditions','planned','completed','incomplete','urgent_failures','normal_failures','all_deadline_conditions','mean_condition_urgent_p95_ms','mean_condition_normal_ms'],
            ['정책','조건','예정','완료','미완료','긴급 실패','일반 실패','전기한 충족 조건','긴급 P95 평균(ms)','일반 평균(ms)']),
        '<h2>주평가 96조건의 엄격 비교</h2><p>전량 완료·긴급/일반 실패 비증가·긴급 P95 비악화를 먼저 확인한다. 비용 감소만으로 성공 처리하지 않는다. 평균 차이는 조건별 차이 평균이며 미적격 조건도 포함한 원 수치를 표시한다.</p>',
        table(ps,['policy','baseline','conditions','service_preserved','joint_gain','mean_delta_energy_j_all','mean_delta_peak_ap_c_all','mean_delta_urgent_p95_ms'],
              ['정책','기준','조건','서비스 유지','J/AP공동감소','J차이 평균','AP차이 평균','긴급P95차이 평균(ms)']),
        '<p>전체192에서 Band 대비 상대적 공동감소 1조건은 양쪽 일반 기한 위반이 남아 있다. 모든 실제 기한 충족까지 요구한 공동감소는0이다. CSV는 상대적 service_preserved/joint_gain과 절대 all_deadlines_met/joint_gain_all_deadlines를 나누어 보존한다.</p>',
        '<p>J는 같은0..120초 기기 전체 모형 에너지, AP는35..180초1초격자 모형 온도다. 안전 온도 한도·표면 온도·미지원 자원은 계산 불가. 실제 열·에너지 절감/제품 우월성/기본 정책 채택은 미입증이다. 차등 제어비용0은 모형 가정이며 host시간은 휴대폰 비용이 아니다.</p>']
    for path in sorted((BUNDLE/'figures').glob('*.png')):parts.append('<img alt="'+html.escape(path.stem)+'" src="figures/'+html.escape(path.name)+'">')
    parts += ['<h2>전체 결과 검색</h2><input id="filter" placeholder="정책·부하·seed 검색"><div class="scroll">',
        table(load_rows(),['seed','family','context','policy','planned','completed','urgent_service_failure','normal_service_failure','urgent_p95_ms','normal_mean_ms','energy_j','peak_ap_c']),
        '</div><script>document.querySelector("#filter").addEventListener("input",e=>{for(const r of document.querySelectorAll("tbody tr"))r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase())});</script></html>']
    (BUNDLE/'index.html').write_text(''.join(parts),encoding='utf8',newline='\n')


def main():
    completion=read(BUNDLE/'completion.json');contract=read(BUNDLE/'contract.json')
    if completion['status']!='completed' or sha(BUNDLE/'results.csv')!=completion['results_sha256']:
        raise ValueError('completed results binding')
    rows=load_rows();pairs=compare(rows)
    if len(rows)!=1728 or len(pairs)!=3456 or len({key(r) for r in rows})!=192:raise ValueError('denominator')
    summary,ps=summaries(rows,pairs)
    csv_write(BUNDLE/'pairs.csv',pairs);csv_write(BUNDLE/'policy_summary.csv',summary);csv_write(BUNDLE/'pair_summary.csv',ps)
    reps=representatives();figures(rows,pairs,summary,reps);render(summary,ps,completion)
    write(BUNDLE/'summary.json',dict(policy_summary=summary,pair_summary=ps,consumption=completion['consumption']))
    verification=dict(utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        command='python -B -m tools.d1_ie_dispatch_report',read_only_plant=True,environment_starts=0,training_episodes=0,device_commands=0,
        source_sha256=sha(__file__),rows=1728,pairs=3456,conditions=192,
        outputs={p.relative_to(BUNDLE).as_posix():sha(p) for p in BUNDLE.rglob('*') if p.is_file() and p.name!='report_verification.json'})
    write(BUNDLE/'report_verification.json',verification)
    print(json.dumps(dict(status='PASS',rows=1728,pairs=3456,consumption=completion['consumption']),ensure_ascii=False))


if __name__=='__main__':main()
