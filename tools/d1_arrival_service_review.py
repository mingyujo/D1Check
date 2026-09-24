"""Post-hoc service review of preserved v3 results; no batch or device execution.

Only three missing representative traces may be replayed: worst P/B3 urgent
loss scenario, smallest stored seed, B2/B3/P. Their metrics must match the CSV.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics as st
from tools import d1_arrival_plan as io
from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch

MAIN=('B2_PC','B3_SOLO_EFT_PC','P_PAIR_COST_PC')
BASE='CPU_URGENT'
NAMES={'B2_PC':'B2','B3_SOLO_EFT_PC':'B3','P_PAIR_COST_PC':'P','CPU_URGENT':'CPU urgent','FIXED_SPLIT':'Fixed split'}
FLOATS=('urgent_p95_ms','urgent_deadline_violation','normal_mean_ms','normal_timely','completion','makespan_s','throughput')
INTS=('seed','planned','arrived','urgent_n','normal_n','response_ready','unfinished','not_arrived','late_success')

def csv_write(path,rows):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def load(path):
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        for k in FLOATS:r[k]=float(r[k]) if r[k] else None
        for k in INTS:r[k]=int(r[k])
    return rows

def dominance(a,b,keys=('urgent_p95_ms','normal_mean_ms')):
    da=[a[k]-b[k] for k in keys]
    if all(abs(x)<1e-9 for x in da):return 'equal'
    if all(x<=1e-9 for x in da):return 'B2_weakly_dominates'
    if all(x>=-1e-9 for x in da):return 'P_weakly_dominates'
    return 'tradeoff'

def thresholds(row,ref):
    return dict(mean_loss_pct=100*(row['normal_mean_ms']/ref['normal_mean_ms']-1),
        miss_increase_pp=100*(row['normal_deadline_violation']-ref['normal_deadline_violation']))

def select(rows,ref,epsilon,delta):
    eligible=[r for r in rows if r['completion']==1 and thresholds(r,ref)['mean_loss_pct']<=epsilon+1e-9
              and thresholds(r,ref)['miss_increase_pp']<=delta+1e-9]
    return min(eligible,key=lambda r:(r['urgent_deadline_violation'],r['urgent_p95_ms'],r['normal_mean_ms'],r['policy']))['policy'] if eligible else 'none'

def paired_relative(data, references, key):
    if {x['seed'] for x in data} != set(references):
        raise ValueError('paired seed mismatch')
    return st.mean(100*(x[key]/references[x['seed']][key]-1) for x in data)


def trace_summary(result,label,policy_label=None):
    rows=result['ledger'];ds=result['decisions'];answer=[]
    for priority in ('urgent','normal'):
        group=[r for r in rows if r['priority']==priority];values=sorted(r['response_ns']/1e6 for r in group)
        waits=[(r['dispatch_ns']-r['arrival_ns'])/1e6 for r in group]
        answer.append(dict(case=label,policy=policy_label or result['policy'],priority=priority,n=len(group),
            response_mean_ms=st.mean(values),response_p95_ms=values[math.ceil(.95*len(values))-1],
            wait_mean_ms=st.mean(waits),wait_max_ms=max(waits),
            dispatch_to_response_mean_ms=st.mean((r['response_ns']-(r['dispatch_ns']-r['arrival_ns']))/1e6 for r in group),
            gpu_count=sum(r['backend']=='GPU' for r in group),late_count=sum(r['late_success'] for r in group),
            no_selection_calls=sum(d['selected']is None for d in ds),
            unknown_pair_wait_calls=sum(d['selected']is None and d['reason']=='wait_unknown_overrun_pair_cost' for d in ds),
            decision_record_budget_ms=len(ds)*(result['settings']['decision_ns']+result['settings']['record_ns'])/1e6,
            dispatch_budget_ms=len(rows)*result['settings']['dispatch_ns']/1e6))
    return answer

def tables(out,absolute,relative,dom):
    index={(r['mode'],r['scenario'],r['policy']):r for r in absolute}
    combined=[]
    for r in relative:
        own=index[r['mode'],r['scenario'],r['policy']]
        comparator=index[r['mode'],r['scenario'],r['comparator']]
        combined.append({**own,**r,**{'comparator_'+k:comparator[k] for k in
            ('urgent_p95_ms','normal_mean_ms','urgent_deadline_violation','normal_deadline_violation','completion','makespan_s','throughput')}})
    csv_write(out/'service_comparison.csv',combined)
    lines=['# 기존 탐색 결과의 서비스 비교 표', '',
        'explore 모드. 각 칸은 모델 반복 5개의 평균이며 실측 세션 CI가 아니다. 긴급 P95는 반복별 nearest-rank 최댓값의 평균이다.',
        '각 정책·조건 planned=arrived=완료 120/120, 미완료·미도착 0. 실패·거절·만료 과정은 미모델링이다. 긴급/일반 분모는 아래에 별도 표시한다.',
        '일반 완료율 100%와 기한 내 완료율은 다르다. 기존 시나리오 기한은 긴급 1500ms, 일반 6000ms이며 UX SLA가 아니다. 일반 P95는 전체 배치에 미저장되어 아래 표에서 미산출; trace_summary.csv에 대표 반복만 제공한다.', '',
        '| 조건 | 정책 | 긴급 P95 ms | 긴급 위반 건/분모 (%) | 일반 평균 ms | 일반 위반 건/분모 (%) | 일반 기한 내 % | makespan s | 처리량 req/s |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in absolute:
        if r['mode']!='explore' or r['policy'] not in NAMES:continue
        lines.append(f"| {r['scenario']} | {NAMES[r['policy']]} | {r['urgent_p95_ms']:.2f} | {r['urgent_misses']}/{r['urgent_n']} ({100*r['urgent_deadline_violation']:.2f}) | {r['normal_mean_ms']:.2f} | {r['normal_misses']}/{r['normal_n']} ({100*r['normal_deadline_violation']:.2f}) | {100*r['normal_timely']:.2f} | {r['makespan_s']:.3f} | {r['throughput']:.3f} |")
    lines+=['', '## P의 paired 상대차', '', '반복별 `(P−대조)/대조`를 동일 가중 평균. +는 지연 증가. 위 절대 평균의 비율과 다르다.', '',
        '| 조건 | P/B2 긴급 % | P/B2 일반 % | P/B3 긴급 % | P/B3 일반 % | B2/P 지연 2지표 | 기한 위반율도 포함 |',
        '|---|---:|---:|---:|---:|---|---|']
    terms={'B2_weakly_dominates':'B2 표본 우세','P_weakly_dominates':'P 표본 우세','tradeoff':'상충','equal':'같음'}
    for d in dom:
        if d['mode']!='explore':continue
        get=lambda p:next(r for r in relative if (r['mode'],r['scenario'],r['policy'],r['comparator'])==('explore',d['scenario'],'P_PAIR_COST_PC',p))
        b,p=get('B2_PC'),get('B3_SOLO_EFT_PC')
        lines.append(f"| {d['scenario']} | {b['urgent_relative_pct']:+.2f} | {b['normal_relative_pct']:+.2f} | {p['urgent_relative_pct']:+.2f} | {p['normal_relative_pct']:+.2f} | {terms[d['two_latency_metrics']]} | {terms[d['with_deadline_rates']]} |")
    (out/'service_tables.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def run(source,bundle,out):
    source,bundle,out=map(Path,(source,bundle,out));out.mkdir(parents=True,exist_ok=False)
    metrics=load(source/'metrics.csv');contract=io.read(source/'contract_before_development.json');freeze=io.read(source/'freeze_before_evaluation.json')
    # Exact input and fixed policy contract; no B2 reselection or threshold refitting.
    receipt=io.read(source/'receipt.json')
    for name in ('metrics.csv','development_selection.json','freeze_before_evaluation.json'):
        if io.digest(source/name)!=receipt['artifacts'][name]:raise ValueError('preserved result changed')
    if len(metrics)!=960 or len({(r['mode'],r['scenario'],r['seed'],r['policy']) for r in metrics})!=960:raise ValueError('run denominator')
    for r in metrics:
        if r['planned']!=24 or r['urgent_n']+r['normal_n']!=24:raise ValueError('request denominator')
        if r['completion']!=1 or r['unfinished'] or r['not_arrived'] or r['response_ready']!=24:raise ValueError('noncomplete data need per-priority ledger')
    groups={}
    for r in metrics:groups.setdefault((r['mode'],r['scenario'],r['policy']),[]).append(r)
    absolute=[]
    for (mode,scenario,policy),rs in groups.items():
        row=dict(mode=mode,scenario=scenario,policy=policy,replicates=len(rs),planned=sum(x['planned'] for x in rs),
            arrived=sum(x['arrived'] for x in rs),urgent_n=sum(x['urgent_n'] for x in rs),normal_n=sum(x['normal_n'] for x in rs),
            unfinished=sum(x['unfinished'] for x in rs),not_arrived=sum(x['not_arrived'] for x in rs),
            simulated_failures=0,simulated_rejections=0,simulated_expirations=0,failure_model='not_modeled_success_only',
            normal_completion=1.,normal_p95_ms=None,normal_p95_scope='not_stored_for_all_replicates; representative_only')
        for k in FLOATS:
            row[k]=st.mean(x[k] for x in rs);row[k+'_min']=min(x[k] for x in rs);row[k+'_max']=max(x[k] for x in rs)
        row['normal_deadline_violation']=1-row['normal_timely']
        row['urgent_misses']=sum(round(x['urgent_deadline_violation']*x['urgent_n']) for x in rs)
        row['normal_misses']=sum(round((1-x['normal_timely'])*x['normal_n']) for x in rs)
        absolute.append(row)
    index={(r['mode'],r['scenario'],r['policy']):r for r in absolute}
    relative=[];dom=[];bounds=[];sensitivity=[]
    for mode,scenario in dict.fromkeys((r['mode'],r['scenario']) for r in absolute):
        ref=index[mode,scenario,BASE]
        b=index[mode,scenario,'B2_PC'];p=index[mode,scenario,'P_PAIR_COST_PC']
        row=dict(mode=mode,scenario=scenario,two_latency_metrics=dominance(b,p),
            with_deadline_rates=dominance(b,p,('urgent_p95_ms','normal_mean_ms','urgent_deadline_violation','normal_deadline_violation')),
            B2_normal_misses=b['normal_misses'],P_normal_misses=p['normal_misses'],normal_n=b['normal_n'],
            support='model_only; arbitrary_overlap_not_device_validated' if mode=='explore' else 'global_serial_queue_transfer_assumed')
        pairs={r['seed']:r for r in groups[mode,scenario,'B2_PC']};pp={r['seed']:r for r in groups[mode,scenario,'P_PAIR_COST_PC']}
        ds=[dominance(pairs[s],pp[s]) for s in pairs]
        row.update(B2_dominant_replicates=ds.count('B2_weakly_dominates'),P_dominant_replicates=ds.count('P_weakly_dominates'),tradeoff_replicates=ds.count('tradeoff'),equal_replicates=ds.count('equal'))
        dom.append(row)
        for policy in (*MAIN,BASE,'FIXED_SPLIT'):
            r=index[mode,scenario,policy];bounds.append(dict(mode=mode,scenario=scenario,policy=policy,reference=BASE,**thresholds(r,ref)))
            for comparator in (BASE,'B2_PC','B3_SOLO_EFT_PC'):
                refs={x['seed']:x for x in groups[mode,scenario,comparator]}
                data=groups[mode,scenario,policy];other=index[mode,scenario,comparator]
                relative.append(dict(mode=mode,scenario=scenario,policy=policy,comparator=comparator,replicates=5,
                    urgent_delta_ms=r['urgent_p95_ms']-other['urgent_p95_ms'],normal_delta_ms=r['normal_mean_ms']-other['normal_mean_ms'],
                    urgent_relative_pct=paired_relative(data,refs,'urgent_p95_ms'),
                    normal_relative_pct=paired_relative(data,refs,'normal_mean_ms'),
                    urgent_miss_delta_pp=100*(r['urgent_deadline_violation']-other['urgent_deadline_violation']),
                    normal_miss_delta_pp=100*(r['normal_deadline_violation']-other['normal_deadline_violation']),
                    throughput_delta=r['throughput']-other['throughput'],makespan_delta_s=r['makespan_s']-other['makespan_s']))
        candidates=[index[mode,scenario,p] for p in (*MAIN,BASE,'FIXED_SPLIT')]
        for eps in (0,5,10,20,50,100):
            for delta in (0,5,10,25,100):
                sensitivity.append(dict(mode=mode,scenario=scenario,reference=BASE,allowed_normal_mean_loss_pct=eps,
                    allowed_normal_miss_increase_pp=delta,selected=select(candidates,ref,eps,delta),
                    role='posthoc_selection_boundary_not_new_success_criterion'))
    for name,rows in (('absolute.csv',absolute),('relative.csv',relative),('dominance.csv',dom),('constraint_boundaries.csv',bounds),('sensitivity.csv',sensitivity)):
        csv_write(out/name,rows)
    tables(out,absolute,relative,dom)
    # All existing base-queue traces retained, no replay. Add only the missing worst loss stratum.
    adverse=[r for r in relative if r['mode']=='explore' and r['policy']=='P_PAIR_COST_PC' and r['comparator']=='B3_SOLO_EFT_PC']
    worst=max(adverse,key=lambda r:(r['urgent_relative_pct'],r['scenario']))['scenario'];seed=min(contract['evaluation_seed'])
    cases={};trace_rows=[]
    for policy in (*MAIN,BASE,'FIXED_SPLIT','P_NO_PAIR_COST_PC','P_NO_PARALLEL_PC'):
        x=io.read(source/'representative'/f'{policy}.json');cases['queue/'+policy]=x;trace_rows+=trace_summary(x,'queue/seed201/existing',policy)
    scenario=next(s for s in contract['scenarios'] if s['id']==worst)
    config=io.read(bundle/'estimates.json');vectors=io.read(bundle/'realizations.json')
    for policy in MAIN:
        settings=dict(freeze['policy_parameters']['explore']);settings.update(scenario['changes'])
        settings.update({k:freeze['B2']['explore']['settings'][k] for k in ('static_map','static_parallel')})
        x=engine.simulate(config,vectors,batch.workload(scenario['workload'],'evaluation'),policy=policy,settings=settings,seed=seed)
        expected=next(r for r in metrics if (r['mode'],r['scenario'],r['seed'],r['policy'])==('explore',worst,seed,policy))
        for k in (*FLOATS,*[k for k in INTS if k!='seed']):
            if not math.isclose(x['metrics'][k],expected[k],rel_tol=1e-12,abs_tol=1e-9):raise ValueError('targeted replay mismatch '+k)
        cases[worst+'/'+policy]=x;trace_rows+=trace_summary(x,worst+'/seed201/replay')
    csv_write(out/'trace_summary.csv',trace_rows)
    # Cases selected by base condition, minimum seed, first differing decision; no favorable selection.
    details={}
    for case in ('queue',worst):
        x=cases[case+'/P_PAIR_COST_PC'];records=[]
        for d in x['decisions']:
            alternative=engine.choose(config,d['queue'],d['lanes'],d['now_ns'],'B3_SOLO_EFT_PC',x['settings'])
            if d['selected']!=alternative['selected']:
                records.append(dict(at_ns=d['now_ns'],observed_P=d,B3_same_state=alternative))
                if len(records)==2:break
        details[case]=records
    (out/'decision_cases.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    (out/'trace_replay_summary.json').write_text(json.dumps(dict(rule='existing queue seed201 + largest mean paired P/B3 urgent loss scenario, smallest seed; first 2 differing P decisions',worst=worst,simulations=3,matched_preserved_metrics=True),indent=2),encoding='utf-8')
    plot(out,absolute,sensitivity)
    result=dict(version='arrival-service-review-v2',source_code_commit='7402a0a6973ad19148be3ee3d406eb282e8410b2',
        source_metrics_sha256=io.digest(source/'metrics.csv'),freeze_sha256=io.digest(source/'freeze_before_evaluation.json'),
        sim_engine_sha256=io.digest(engine.__file__),posthoc=True,device_calls=0,full_batch_reruns=0,minimal_trace_replays=3,
        policy_tuning=False,original_metrics_changed=False,normal_p95='representative only; no new whole-batch execution',experiment_ready=False)
    (out/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def plot(out,rows,sensitivity):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scenarios=list(dict.fromkeys(r['scenario'] for r in rows));colors=dict(zip(NAMES,['C0','C1','C2','C3','C4']))
    markers=dict(zip(NAMES,['o','s','x','+','D']))
    fig,axes=plt.subplots(3,4,figsize=(17,12))
    for ax,scenario in zip(axes.flat,scenarios):
        for policy in NAMES:
            r=next(x for x in rows if (x['mode'],x['scenario'],x['policy'])==('explore',scenario,policy))
            ax.scatter(r['normal_mean_ms'],r['urgent_p95_ms'],color=colors[policy],label=NAMES[policy],s=65,marker=markers[policy])
        ax.set_title(scenario,fontsize=10);ax.set_xlabel('Normal mean (ms)');ax.set_ylabel('Urgent P95 (ms)');ax.grid(alpha=.2)
    fig.suptitle('Service trade-offs: lower-left preferred; mean of 5 model replicates\n24 arrivals/replicate (6 urgent +18 normal; urgent_heavy:12+12); model assumptions, not device superiority')
    fig.legend(*axes.flat[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.945),ncol=5)
    fig.tight_layout(rect=(0,0,1,.91))
    for ext in ('png','svg'):fig.savefig(out/f'tradeoff.{ext}',dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4));eps=[0,5,10,20,50,100];deltas=[0,5,10,25,100];policies=[BASE,'FIXED_SPLIT',*MAIN]
    for ax,sc in zip(axes,('queue','classification_mix','queue_interference_2.0')):
        grid=[]
        for d in deltas:
            grid.append([policies.index(next(r['selected'] for r in sensitivity if r['mode']=='explore' and r['scenario']==sc and r['allowed_normal_mean_loss_pct']==e and r['allowed_normal_miss_increase_pp']==d)) for e in eps])
        ax.imshow(grid,cmap='tab10',vmin=0,vmax=9,origin='lower',aspect='auto')
        for i,d in enumerate(deltas):
            for j,e in enumerate(eps):ax.text(j,i,NAMES[policies[grid[i][j]]],ha='center',va='center',fontsize=7)
        ax.set_xticks(range(len(eps)),eps);ax.set_yticks(range(len(deltas)),deltas);ax.set_xlabel('Allowed normal mean loss (%)');ax.set_ylabel('Allowed normal miss increase (pp)');ax.set_title(sc)
    fig.suptitle('Post-hoc policy choice boundaries vs CPU urgent; not adopted service margins')
    fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(out/f'constraint_map.{ext}',dpi=150)
    plt.close(fig)
    for path in out.glob('*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('source','bundle','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args();print(json.dumps(run(a.source,a.bundle,a.output),indent=2))
