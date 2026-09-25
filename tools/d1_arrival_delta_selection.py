"""Exact post-hoc deadline-margin selection from preserved aggregate CSV only.

No simulator, device tool, policy tuning, or B2 development selection is invoked.
"""
import argparse
import csv
from decimal import Decimal
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

POLICIES=('CPU_URGENT','FIXED_SPLIT','B2_PC','B3_SOLO_EFT_PC','P_PAIR_COST_PC')
NAMES=dict(zip(POLICIES,('CPU urgent','Fixed split','B2','B3','P')))
BASE=POLICIES[0]


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def non_timely_pp(timely,planned):
    """Unfinished/failed requests cannot disappear from the planned denominator."""
    if planned<=0 or not 0<=timely<=planned:raise ValueError('invalid planned/timely count')
    return 100*F(planned-timely,planned)


def gap(row,ref):
    return non_timely_pp(int(row['normal_n'])-int(row['normal_misses']),int(row['normal_n']))-non_timely_pp(int(ref['normal_n'])-int(ref['normal_misses']),int(ref['normal_n']))


def comparable(row):
    # The preserved aggregate has no per-priority failure ledger. Fail closed if
    # it is no longer the fully completed success-vector dataset it describes.
    return (Decimal(row['completion'])==1 and Decimal(row['normal_completion'])==1
        and int(row['planned'])==int(row['arrived']) and int(row['unfinished'])==0
        and int(row['not_arrived'])==0 and row['urgent_p95_ms']!=''
        and all(int(row[k])==0 for k in ('simulated_failures','simulated_rejections','simulated_expirations')))


def choose(rows,ref,delta):
    if delta<0:raise ValueError('delta must be nonnegative')
    eligible=[r for r in rows if comparable(r) and gap(r,ref)<=delta]
    if not eligible:return [],[]
    best=min(Decimal(r['urgent_p95_ms']) for r in eligible)
    return eligible,[r for r in eligible if Decimal(r['urgent_p95_ms'])==best]


def fields(r):
    return {k:r[k] for k in ('urgent_p95_ms','normal_mean_ms','completion','normal_completion',
        'urgent_misses','urgent_n','normal_misses','normal_n','planned','arrived','unfinished','not_arrived',
        'makespan_s','throughput','failure_model')} | dict(
        urgent_miss_pct_exact=str(100*F(int(r['urgent_misses']),int(r['urgent_n']))),
        normal_miss_pct_exact=str(100*F(int(r['normal_misses']),int(r['normal_n']))))


def analyze(source,out):
    source,out=Path(source),Path(out)
    with source.open(encoding='utf-8-sig',newline='') as f:allrows=list(csv.DictReader(f))
    rows=[r for r in allrows if r['mode']=='explore' and r['policy'] in POLICIES]
    scenarios=list(dict.fromkeys(r['scenario'] for r in rows))
    assert len(rows)==60 and len(scenarios)==12
    assert len({(r['scenario'],r['policy']) for r in rows})==60
    groups={s:[r for r in rows if r['scenario']==s] for s in scenarios}
    thresholds=[];intervals=[];pcomparison=[];zero=[]
    for s,rs in groups.items():
        ref=next(r for r in rs if r['policy']==BASE)
        for r in rs:
            assert int(r['replicates'])==5
            assert (r['planned'],r['normal_n'],r['urgent_n'])==(ref['planned'],ref['normal_n'],ref['urgent_n'])
            assert int(r['normal_n'])+int(r['urgent_n'])==int(r['planned'])
            assert 0<=int(r['normal_misses'])<=int(r['normal_n'])
            g=gap(r,ref);minimum=max(F(0),g)
            thresholds.append(dict(scenario=s,policy=r['policy'],reference=BASE,
                reference_normal_misses=ref['normal_misses'],reference_normal_n=ref['normal_n'],
                reference_miss_pct_exact=str(100*F(int(ref['normal_misses']),int(ref['normal_n']))),
                gap_pp_exact=str(g),gap_pp=float(g),minimum_delta_pp_exact=str(minimum),minimum_delta_pp=float(minimum),
                comparable=comparable(r),incomparable_reason='' if comparable(r) else 'incomplete_or_missing_ledger',**fields(r)))
        edges=sorted({F(0)}|{max(F(0),gap(r,ref)) for r in rs if comparable(r)})
        for i,lower in enumerate(edges):
            upper=edges[i+1] if i+1<len(edges) else None
            eligible,winners=choose(rs,ref,lower)
            for winner in winners:
                intervals.append(dict(scenario=s,lower_pp_exact=str(lower),lower_pp=float(lower),
                    upper_pp_exact=str(upper) if upper is not None else '',upper_pp=float(upper) if upper is not None else '',
                    boundary='lower inclusive, upper exclusive; blank upper = infinity',
                    feasible=';'.join(r['policy'] for r in eligible),winners=';'.join(r['policy'] for r in winners),
                    winner=winner['policy'],tie=len(winners)>1,role='posthoc scenario oracle; not deployable policy',**fields(winner)))
        _,winners=choose(rs,ref,F(0));p=next(r for r in rs if r['policy']=='P_PAIR_COST_PC')
        zero.append(dict(scenario=s,winners=';'.join(r['policy'] for r in winners),urgent_p95_ms=winners[0]['urgent_p95_ms'],
            reference_normal_misses=ref['normal_misses'],normal_n=ref['normal_n'],reference_miss_pct_exact=str(100*F(int(ref['normal_misses']),int(ref['normal_n'])))))
        for other in [ref]+[r for r in winners if r['policy']!=BASE]:
            pcomparison.append(dict(scenario=s,comparator=other['policy'],
                P_urgent_ms=p['urgent_p95_ms'],comparator_urgent_ms=other['urgent_p95_ms'],
                P_urgent_loss_ms=str(Decimal(p['urgent_p95_ms'])-Decimal(other['urgent_p95_ms'])),
                P_normal_misses=p['normal_misses'],comparator_normal_misses=other['normal_misses'],normal_n=p['normal_n'],
                P_miss_difference_count=int(p['normal_misses'])-int(other['normal_misses']),
                P_miss_difference_pp_exact=str(gap(p,other)),P_normal_mean_ms=p['normal_mean_ms'],
                comparator_normal_mean_ms=other['normal_mean_ms'],P_feasible_delta0=gap(p,ref)<=0 and comparable(p),
                predicted_interference=1.5,realized_interference=1.0 if s=='queue_interference_1.0' else 2.0 if s=='queue_interference_2.0' else 1.5,
                interference_evidence='unvalidated assumption, not measured causal coefficient'))
    globalrows=[]
    for policy in POLICIES:
        prs=[r for r in rows if r['policy']==policy]
        ts=[t for t in thresholds if t['policy']==policy]
        minimum=max(F(t['minimum_delta_pp_exact']) for t in ts)
        worst=max(Decimal(r['urgent_p95_ms']) for r in prs)
        globalrows.append(dict(policy=policy,minimum_delta_all_conditions_pp_exact=str(minimum),minimum_delta_all_conditions_pp=float(minimum),
            limiting_conditions=';'.join(t['scenario'] for t in ts if F(t['minimum_delta_pp_exact'])==minimum),
            worst_urgent_p95_ms=str(worst),worst_conditions=';'.join(r['scenario'] for r in prs if Decimal(r['urgent_p95_ms'])==worst),
            comparable_all=all(comparable(r) for r in prs),scenario_weighting='none',
            **{s+'_urgent_p95_ms':next(r['urgent_p95_ms'] for r in prs if r['scenario']==s) for s in scenarios}))
    gedges=sorted({F(0)}|{F(r['minimum_delta_all_conditions_pp_exact']) for r in globalrows})
    gintervals=[]
    for i,edge in enumerate(gedges):
        feasible=[r for r in globalrows if r['comparable_all'] and F(r['minimum_delta_all_conditions_pp_exact'])<=edge]
        worst=min(Decimal(r['worst_urgent_p95_ms']) for r in feasible)
        gintervals.append(dict(lower_pp_exact=str(edge),upper_pp_exact=str(gedges[i+1]) if i+1<len(gedges) else '',
            feasible=';'.join(r['policy'] for r in feasible),
            descriptive_minimax=';'.join(r['policy'] for r in feasible if Decimal(r['worst_urgent_p95_ms'])==worst),
            worst_urgent_p95_ms=str(worst),role='descriptive worst-case only; no adopted minimax objective or probabilities'))
    out.mkdir(parents=True,exist_ok=False)
    for name,rs in [('thresholds',thresholds),('intervals',intervals),('delta_zero',zero),('P_comparisons',pcomparison),('global_policies',globalrows),('global_intervals',gintervals)]:write_csv(out/(name+'.csv'),rs)
    # Compact table with every admission boundary, including boundaries that do
    # not change the urgent-optimal winner. Exact fractions, not rounded gates.
    lines=['# 12조건의 정확한 허용폭 구간', '', 'δ 단위 %p. 구간은 [왼쪽, 오른쪽), ∞는 이후 동일. 이름은 동결된 PC 정책이다. 사후 oracle 참고이며 배포 정책이 아니다.', '',
           '| 조건 | δ 구간 | 제약 충족 정책 | 긴급 P95 최저 정책(동률 모두) | 긴급 ms |', '|---|---|---|---|---:|']
    seen=set()
    for r in intervals:
        key=(r['scenario'],r['lower_pp_exact'])
        if key in seen:continue
        seen.add(key)
        names=lambda v:', '.join(NAMES[p] for p in v.split(';'))
        lines.append(f"| {r['scenario']} | [{r['lower_pp_exact']}, {r['upper_pp_exact'] or '∞'}) | {names(r['feasible'])} | {names(r['winners'])} | {float(r['urgent_p95_ms']):.3f} |")
    (out/'interval_table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    plot(out,scenarios,intervals)
    receipt=dict(version='arrival-delta-selection-v1',input=str(source.as_posix()),input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_checkpoint='b7a4695d3f1241e8a184290ad9a95ff49e314cd7',
        policies=POLICIES,mode='explore',objective='minimum mean of per-replicate urgent nearest-rank P95',
        constraint='planned normal non-timely rate <= CPU_URGENT rate + delta pp',
        exact_thresholds='Fraction integer miss/planned counts',ties='all equal exported Decimal urgent means; no secondary objective',
        additional_requirement='fully completed preserved dataset; incomparable if completion/ledger missing',
        old_mean_loss_constraint=False,old_urgent_miss_first_ordering=False,scenario_weights=None,
        posthoc=True,simulations=0,device_calls=0,B2_reselection=False,P_tuning=False,experiment_ready=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def plot(out,scenarios,intervals):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=dict(zip(POLICIES,['C0','C1','C2','C3','C4']))
    fig,axes=plt.subplots(3,4,figsize=(17,11))
    for ax,s in zip(axes.flat,scenarios):
        rs=[r for r in intervals if r['scenario']==s]
        byedge={r['lower_pp']:r for r in rs}
        for lower,r in byedge.items():
            right=r['upper_pp'] if r['upper_pp']!='' else 55
            y=float(r['urgent_p95_ms']);color='black' if r['tie'] else colors[r['winner']]
            ax.plot([lower,right],[y,y],color=color,lw=2)
            ax.scatter([lower],[y],color=color,s=20)
            if right<55:
                next_y=float(byedge[right]['urgent_p95_ms'])
                ax.plot([right,right],[y,next_y],color='gray',lw=.8)
        ax.set_title(s,fontsize=10);ax.set_xlim(-1,55);ax.set_ylim(bottom=0)
        ax.set_xlabel('Allowed normal miss increase (pp)');ax.set_ylabel('Urgent P95 (ms)');ax.grid(alpha=.2)
    handles=[plt.Line2D([0],[0],color=colors[p],lw=2,label=NAMES[p]) for p in POLICIES]
    handles.append(plt.Line2D([0],[0],color='black',lw=2,label='Tie (all winners retained)'))
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.94),ncol=6)
    fig.suptitle('Post-hoc scenario oracle: deadline constraint only, then minimum urgent P95\n5 model replicates x24 requests/condition; P95=mean of replicate maxima; no device CI; >55 pp unchanged')
    fig.tight_layout(rect=(0,0,1,.91))
    for ext in ('png','svg'):fig.savefig(out/f'delta_steps.{ext}',dpi=150)
    plt.close(fig)
    for p in out.glob('*.svg'):p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='docs/results/arrival_service_review_20260925/absolute.csv')
    p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(analyze(a.source,a.output),indent=2))
