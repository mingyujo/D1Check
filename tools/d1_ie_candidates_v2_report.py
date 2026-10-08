"""Read-only paired KPI reporting and selection frozen before confirmation."""
from __future__ import annotations
import csv,gzip,hashlib,html,json,statistics
from pathlib import Path
from tools import d1_edd_ect_residual_report as comparison

ROOT=Path(__file__).resolve().parents[1];BUNDLE=ROOT/'docs/results/ie_candidates_v2';LOCAL=ROOT/'output/ie_candidates_20261008_v2'
BAND='BAND_HEFT_WHOLE_REQUEST_ADAPT_V1';TRITON='TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1';BASE='IE_EDD_ECT_LANE_PC_V1'
LABELS={BAND:'Band 요청 적용',TRITON:'Triton 요청 적용','SHARED_EFT':'공용 EFT',BASE:'기한 우선 ECT',
    'IE_ENERGY_AP_LIST_V2':'열·에너지 리스트','IE_ROLLING_ENERGY_CPSAT_AP_FILTER_V2':'구간 재계획 CP-SAT'}
LABELS.update({f'{a}_seed{s}':f'{"마스크 PPO" if a=="PPO" else "Double DQN"} · {s}' for a in ('PPO','DDQN') for s in (11,23,37)})
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8',newline='\n')
def csv_write(path,rows):
    with Path(path).open('w',encoding='utf8',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)


def full_mean(rows,key):
    values=[r[key] for r in rows]
    return statistics.mean(values) if values and all(v is not None for v in values) else None


def load(split):
    receipts=[json.loads(s) for s in (LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()]
    items=[]
    for p in sorted((LOCAL/'items').glob(split+'__*.json.gz')):
        item=json.loads(gzip.decompress(p.read_bytes()));identity=item['row']['identity']
        done=[r for r in receipts if r['event']=='completed' and r['identity']==identity]
        if len(done)!=1 or done[0]['artifact_sha256']!=sha(p):raise ValueError('unsealed '+identity)
        item['row']['policy']=identity.split('/')[1];items.append(item)
    expected=(24 if split=='validation' else 48)*12
    if len(items)!=expected:raise ValueError(f'{split} incomplete: {len(items)}/{expected}')
    return items


def eligibility(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};out=[]
    for p in LABELS:
        group=[r for r in rows if r['policy']==p];services=[];nonworse=[];joint=[]
        for r in group:
            paired=[comparison.compare(r,by[r['seed'],r['family'],r['context'],b]) for b in (BAND,TRITON)]
            primary=r['family'] in ('low','sustained')
            service=all(t['service_preserved'] and (not primary or t['all_deadlines_met']) for t in paired)
            services.append(service);nonworse.append(service and all(t['nonworse'] for t in paired));joint.append(service and all(t['joint_gain'] for t in paired))
        out.append(dict(policy=p,conditions=len(group),service_good=sum(services),nonworse_conditions=sum(nonworse),joint_gain_conditions=sum(joint),
            eligible=bool(group) and all(nonworse) and any(joint)))
    return out


def freeze_selection():
    target=BUNDLE/'selection_after_validation.json'
    if target.exists():return read(target)
    rows=[i['row'] for i in load('validation')];status=eligibility(rows)
    candidates=[]
    for p in list(LABELS)[4:6]:
        if next(r for r in status if r['policy']==p)['eligible']:candidates.append(p)
    for a in ('PPO','DDQN'):
        if all(next(r for r in status if r['policy']==f'{a}_seed{s}')['eligible'] for s in (11,23,37)):candidates.append(a)
    def cost(p):
        rs=[r for r in rows if (r['policy']==p or r['policy'].startswith(p+'_seed')) and r['family'] in ('low','sustained')]
        return (statistics.mean(r['peak_ap_c'] for r in rs),statistics.mean(r['energy_j'] for r in rs),p)
    result=dict(chosen=min(candidates,key=cost) if candidates else None,all_candidates=candidates,eligibility=status,
        frozen_before_final=True,validation_rows_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
        policy='all conditions no worse versus both Band/Triton, primary absolute deadlines, at least one strict joint reduction; every RL seed must qualify')
    write(target,result);return result


def report():
    done=read(BUNDLE/'completion.json');assert done['status']=='completed'
    vrows=[i['row'] for i in load('validation')];items=load('final');rows=[i['row'] for i in items]
    chosen=read(BUNDLE/'selection_after_validation.json');status=eligibility(rows);pairs=[]
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows}
    for r in rows:
        for b in (BAND,TRITON,BASE):
            if r['policy']==b:continue
            pairs.append(dict(seed=r['seed'],family=r['family'],context=r['context'],policy=r['policy'],baseline=b,**comparison.compare(r,by[r['seed'],r['family'],r['context'],b])))
    summaries=[]
    for scope,families in [('all',('low','queue','burst','sustained')),('primary',('low','sustained'))]:
        for p in LABELS:
            rs=[r for r in rows if r['policy']==p and r['family'] in families]
            summaries.append(dict(scope=scope,policy=p,conditions=len(rs),planned=sum(r['planned'] for r in rs),completed=sum(r['completed'] for r in rs),
                urgent_failures=sum(r['urgent_service_failure'] for r in rs),normal_failures=sum(r['normal_service_failure'] for r in rs),
                absolute_deadline_conditions=sum(r['deadline_met']==r['planned'] for r in rs),
                mean_urgent_p95_ms=full_mean(rs,'urgent_p95_ms'),mean_normal_mean_ms=full_mean(rs,'normal_mean_ms'),
                mean_energy_j=full_mean(rs,'energy_j'),mean_peak_ap_c=full_mean(rs,'peak_ap_c'),
                supported_full_ap_conditions=sum(r['peak_ap_c'] is not None for r in rs),
                informative_choices=sum(r.get('informative_choices',0) for r in rs),nonbase_choices=sum(r.get('nonbase_choices',0) for r in rs),
                solver_calls=sum(r.get('solver_calls',0) for r in rs),solver_accepted=sum(r.get('solver_accepted',0) for r in rs),solver_unknown=sum(r.get('solver_unknown',0) for r in rs),
                total_host_wall_s=sum(r['host_wall_s'] for r in rs)))
    training=[]
    for a in ('PPO','DDQN'):
        for s in (11,23,37):
            data=read(LOCAL/f'{a}_seed{s}_done.json');rs=data['rows']
            training.append(dict(algorithm=a,seed=s,episodes=data['cursor'],updates=len(data['updates']),optimizer_steps=sum(r['optimizer_steps'] for r in data['updates']),
                transitions=sum(r['decision_choices'] for r in rs),informative=sum(r['informative'] for r in rs),nonbase=sum(r['nonbase_choices'] for r in rs),
                wall_s=sum(r['host_wall_s'] for r in rs),mean_energy_j=full_mean(rs,'energy_j'),mean_ap_c=full_mean(rs,'peak_ap_c')))
    p=chosen['chosen'];qualified={r['policy']:r['eligible'] for r in status}
    confirmed=bool(p and (all(qualified[f'{p}_seed{s}'] for s in (11,23,37)) if p in ('PPO','DDQN') else qualified[p]))
    result=dict(chosen_after_validation=p,final_confirmed=confirmed,selected_new_policy=p if confirmed else None,
        final_eligibility=status,consumption=done['consumption'],final_rows=len(rows),validation_rows=len(vrows),training=training,policy_summaries=summaries,
        planned=sum(r['planned'] for r in rows),completed=sum(r['completed'] for r in rows),
        scope='same measured-coefficient PC model, AP channel; no physical/surface temperature or whole-product superiority claim',
        no_post_final_selection=True,uncertainty='four independent final trace seeds, three correlated context vectors, three learning seeds; not phone confidence intervals')
    csv_write(BUNDLE/'validation_results.csv',vrows);csv_write(BUNDLE/'final_results.csv',rows);csv_write(BUNDLE/'pairs.csv',pairs)
    csv_write(BUNDLE/'policy_summary.csv',summaries);csv_write(BUNDLE/'training_summary.csv',training);csv_write(BUNDLE/'final_eligibility.csv',status)
    write(BUNDLE/'summary.json',result)
    reps={p:next(i for i in items if i['row']['policy']==p and i['row']['seed']==812020001 and i['row']['family']=='queue' and i['row']['context']=='mean') for p in LABELS}
    write(BUNDLE/'representatives.json',reps);plots(rows,summaries,pairs,reps);dashboard(rows,summaries,result)
    receipts=[json.loads(s) for s in (LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()]
    csv_write(BUNDLE/'execution_receipts.csv',[dict(event=r['event'],utc=r['utc'],number=r['number'],kind=r['kind'],identity=r['identity']) for r in receipts])
    return result


def plots(rows,summaries,pairs,reps):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False})
    out=BUNDLE/'figures';out.mkdir(exist_ok=True);policies=list(LABELS);allrows={r['policy']:r for r in summaries if r['scope']=='all'}
    fig,axes=plt.subplots(1,2,figsize=(15,5),layout='constrained')
    for i,p in enumerate(policies):axes[0].bar(i,allrows[p]['mean_urgent_p95_ms'] if allrows[p]['mean_urgent_p95_ms'] is not None else float('nan'));axes[1].bar(i,allrows[p]['normal_failures'])
    for ax in axes:ax.set_xticks(range(len(policies)),list(LABELS.values()),rotation=60,ha='right');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('조건별 긴급 P95 평균 ms');axes[1].set_ylabel('일반 기한 실패 건');fig.suptitle('공통 확인 48조건의 응답과 기한')
    fig.savefig(out/'01_응답과기한.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,6),layout='constrained')
    for ax,b in zip(axes,(BAND,TRITON)):
        for p in policies[4:]:
            rs=[r for r in pairs if r['policy']==p and r['baseline']==b and r['family'] in ('low','sustained') and r['delta_peak_ap_c'] is not None and r['delta_energy_j'] is not None]
            ax.scatter([r['delta_energy_j'] for r in rs],[r['delta_peak_ap_c'] for r in rs],label=LABELS[p],s=22,alpha=.6)
        ax.axhline(0,color='grey');ax.axvline(0,color='grey');ax.set_xlabel('전체 에너지 차이 J');ax.set_title(LABELS[b]+' 대비');ax.grid(alpha=.2)
    axes[0].set_ylabel('최고 모형 AP 차이 °C');axes[1].legend(fontsize=7,bbox_to_anchor=(1,1));fig.suptitle('주 부하 비용 차이 — 서비스 조건도 함께 충족해야 함')
    fig.savefig(out/'02_에너지와열차이.png',dpi=150);plt.close(fig)
    shown=[BAND,TRITON,BASE,*policies[4:6],'PPO_seed11','DDQN_seed11']
    fig,axes=plt.subplots(len(shown),1,figsize=(13,12),sharex=True,layout='constrained')
    for ax,p in zip(axes,shown):
        for r in reps[p]['ledger']:
            if 'dispatch_ns' not in r:continue
            a=r['dispatch_ns']/1e9;b=r.get('lane_available_ns',120e9)/1e9;y=0 if r['backend']=='CPU' else 1
            ax.broken_barh([(a,b-a)],(y-.3,.6),facecolors='#387fba' if r['priority']=='urgent' else '#eda344')
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(LABELS[p],loc='left',fontsize=10);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlim(35,65);axes[-1].set_xlabel('공통 시간 초');fig.suptitle('사전 지정 첫 확인 trace — 막대는 실제 lane 재사용까지')
    fig.savefig(out/'03_대표시간표.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,5),layout='constrained')
    for p in shown:ax.plot(reps[p]['curves']['ap_times_s'],reps[p]['curves']['ap_path'],label=LABELS[p])
    ax.set_xlabel('공통 시간 초');ax.set_ylabel('모형 AP °C');ax.legend(fontsize=8);ax.grid(alpha=.2);ax.set_title('대표 trace의 동일 AP 채널 — 표면온도 아님')
    fig.savefig(out/'04_대표온도경로.png',dpi=150);plt.close(fig)
    conditions=sorted({(r['seed'],r['family'],r['context']) for r in rows});by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows}
    values=[]
    for p in policies:
        line=[]
        for s,f,c in conditions:
            row=by[s,f,c,p];pairs2=[comparison.compare(row,by[s,f,c,b]) for b in (BAND,TRITON)]
            line.append(3 if all(r['joint_gain'] and r['all_deadlines_met'] for r in pairs2) else 2 if all(r['nonworse'] for r in pairs2) else 1 if all(r['service_preserved'] for r in pairs2) else 0)
        values.append(line)
    from matplotlib.colors import ListedColormap
    fig,ax=plt.subplots(figsize=(17,6),layout='constrained');ax.imshow(values,aspect='auto',vmin=0,vmax=3,cmap=ListedColormap(['#e5b4b4','#eee0a9','#c8dfcf','#76bb91']))
    fam={'low':'낮음','queue':'대기열','burst':'몰림','sustained':'지속'};ctx={'mean':'평균','short_context':'짧음','long_context':'김'}
    ax.set_xticks(range(len(conditions)),[f'{s-812020000} {fam[f]} {ctx[c]}' for s,f,c in conditions],rotation=90,fontsize=7);ax.set_yticks(range(len(policies)),list(LABELS.values()))
    ax.set_title('Band·Triton 양쪽 대비 — 진초록 전기한·공동감소 / 연초록 비용 비악화 / 노랑 서비스 유지 / 빨강 서비스 악화')
    fig.savefig(out/'05_조건별결과지도.png',dpi=150);plt.close(fig)


def dashboard(rows,summaries,result):
    def table(rs,fields):
        head=''.join('<th>'+html.escape(label)+'</th>' for _,label in fields);body=''
        for r in rs:
            cells=[]
            for key,_ in fields:
                v=r[key];v=LABELS.get(v,v) if isinstance(v,str) else v
                cells.append('<td>'+html.escape(f'{v:.6f}' if isinstance(v,float) else str(v))+'</td>')
            body+='<tr>'+''.join(cells)+'</tr>'
        return '<div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    body='<h1>산업공학 스케줄링 네 후보 비교</h1><p>공통 CPU/GPU 조건 · PPO/Double DQN 각각 3seed×64episode · 확인48조건×12정책.</p>'
    body+='<p><a href="README.md">결과 보고서</a> · <a href="final_results.csv">전체 CSV</a> · <a href="registration.json">사전 계약</a></p>'
    body+='<p>에너지는 공통120초 기기 전체 모형값, 온도는 AP 추정값입니다. 실제 제품 전체·휴대폰 실측·표면온도 우위가 아닙니다.</p>'
    body+='<p>새 정책 채택: '+html.escape(str(result['selected_new_policy']))+'</p><input id="filter" placeholder="정책 또는 부하 검색">'
    body+=table(summaries,[('scope','범위'),('policy','정책'),('completed','완료'),('urgent_failures','긴급 실패'),('normal_failures','일반 실패'),('mean_urgent_p95_ms','긴급 P95 ms'),('mean_energy_j','전체 J'),('mean_peak_ap_c','AP °C')])
    body+=table(rows,[('seed','trace seed'),('family','부하'),('context','문맥'),('policy','정책'),('planned','예정'),('completed','완료'),('urgent_p95_ms','긴급 P95 ms'),('normal_service_failure','일반 실패'),('energy_j','전체 J'),('peak_ap_c','AP °C')])
    for f in sorted((BUNDLE/'figures').glob('*.png')):body+=f'<img src="figures/{f.name}" alt="{f.stem}">'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>산업공학 CPU GPU 후보 비교</title><style>body{font-family:Malgun Gothic,sans-serif;margin:24px;color:#243142;max-width:1450px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #ddd;padding:7px}th{background:#edf3f8}.scroll{overflow:auto;margin:16px 0}input{padding:10px;width:300px}img{width:100%;max-width:1300px;margin:20px 0}</style>'+body+'<script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'
    (BUNDLE/'index.html').write_text(page,encoding='utf8',newline='\n')


if __name__=='__main__':print(json.dumps({k:v for k,v in report().items() if k not in ('policy_summaries','training','final_eligibility')},ensure_ascii=False,indent=2))
