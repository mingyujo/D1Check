"""Read saved outcomes; compare all conditions without new simulations."""
import argparse
import csv
import html
import json
from pathlib import Path
import statistics
from tools import d1_scheduler_conditions as s
p=s.p
COSTS=('energy_j','peak_ap_c','thermal_degree_seconds')


def read(path):
    rows=list(csv.DictReader(path.open(encoding='utf8')))
    for r in rows:
        for k,v in r.items():
            if k not in ('stage','envelope','scenario','policy'):
                try:r[k]=float(v) if v else None
                except ValueError:pass
    return rows


def group_result(xs,bs):
    full=all(x['deadline_met']==x['planned']==x['completed'] for x in xs)
    valid=all(x[k] is not None and b[k] is not None for x,b in zip(xs,bs) for k in COSTS)
    nonworse=valid and all(x[k]<=b[k]+1e-8 for x,b in zip(xs,bs) for k in COSTS)
    both=valid and all(x['energy_j']<b['energy_j']-1e-8 and x['peak_ap_c']<b['peak_ap_c']-1e-8
                      and x['thermal_degree_seconds']<b['thermal_degree_seconds']-1e-8 for x,b in zip(xs,bs))
    improvement=valid and any(x[k]<b[k]-1e-8 for x,b in zip(xs,bs) for k in COSTS)
    out=dict(cases=len(xs),all_deadlines=full,joint_nonworse_gain=full and nonworse and improvement,
        all_cases_J_and_heat_lower=full and both,
        deadline_met=int(sum(x['deadline_met'] for x in xs)),planned=int(sum(x['planned'] for x in xs)),
        reference_deadline_met=int(sum(x['deadline_met'] for x in bs)))
    for k in (*COSTS,'urgent_p95_ms','normal_mean_ms'):
        diffs=[x[k]-b[k] for x,b in zip(xs,bs) if x[k] is not None and b[k] is not None]
        out['mean_delta_'+k]=statistics.mean(diffs) if len(diffs)==len(xs) else None
        out['min_delta_'+k]=min(diffs) if len(diffs)==len(xs) else None
        out['max_delta_'+k]=max(diffs) if len(diffs)==len(xs) else None
    out['classification']=('deadline_failure' if not full else 'joint_model_gain' if out['joint_nonworse_gain'] else
        'unchanged' if valid and all(abs(out['min_delta_'+k])<1e-8 and abs(out['max_delta_'+k])<1e-8 for k in COSTS) else 'tradeoff_or_worse')
    return out


def report(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    folder=Path(folder);rows=read(folder/'results.csv');test=[r for r in rows if r['stage']=='test']
    ref={(r['envelope'],r['seed'],r['scenario'],r['policy']):r for r in test}
    groups=[]
    for e in s.envelopes():
        for policy in s.POLICIES:
            xs=[r for r in test if r['envelope']==e['id'] and r['policy']==policy]
            for baseline in s.a.BASELINES:
                bs=[ref[x['envelope'],x['seed'],x['scenario'],baseline] for x in xs]
                groups.append(dict(envelope=e['id'],gap_s=e['gap_s'],class_share=e['class_share'],burst=e['burst'],
                    policy=policy,reference=baseline,**group_result(xs,bs)))
    s.save_rows(folder/'condition_support.csv',groups)
    selected=json.loads((folder/'freeze_before_test.json').read_text(encoding='utf8'))['selected']
    chosen=[g for g in groups if g['reference']=='EFT_REFERENCE' and g['policy']==selected[g['envelope']]]
    s.save_rows(folder/'frozen_selector_test.csv',chosen)
    # Descriptive frontier: retain conflicting objectives, do not invent an
    # AP safety cap or claim an averaged Pareto point passes every context.
    frontiers=[]
    for e in s.envelopes():
        candidates=[]
        for pol in s.POLICIES:
            xs=[r for r in test if r['envelope']==e['id'] and r['policy']==pol]
            if all(x['completed']==x['planned']==x['deadline_met'] for x in xs):
                candidates.append(dict(envelope=e['id'],policy=pol,**{k:statistics.mean(x[k] for x in xs) for k in COSTS},
                    urgent_p95_ms=statistics.mean(x['urgent_p95_ms'] for x in xs),
                    normal_mean_ms=statistics.mean(x['normal_mean_ms'] for x in xs)))
        for x in candidates:
            x['nondominated_mean_costs']=not any(all(y[k]<=x[k]+1e-8 for k in COSTS) and any(y[k]<x[k]-1e-8 for k in COSTS)
                for y in candidates)
            frontiers.append(x)
    s.save_rows(folder/'feasible_frontiers.csv',frontiers)
    summary=dict(test_cases_per_policy=243,conditions=27,selection=selected,
        frozen_selector_joint_regions=sum(g['joint_nonworse_gain'] for g in chosen),
        frozen_selector_deadline_failure_regions=sum(not g['all_deadlines'] for g in chosen),
        robust_joint_regions={b:{pol:sum(g['joint_nonworse_gain'] for g in groups if g['reference']==b and g['policy']==pol)
                                 for pol in s.POLICIES} for b in s.a.BASELINES},
        all_cases_both_lower_regions={b:{pol:sum(g['all_cases_J_and_heat_lower'] for g in groups if g['reference']==b and g['policy']==pol)
                                 for pol in s.POLICIES} for b in s.a.BASELINES},
        independent_device_validation=False,experiment_ready=False)
    p.write(folder/'condition_summary.json',summary)
    labels=[e['id'] for e in s.envelopes()]
    fig,axes=plt.subplots(3,1,figsize=(15,11),layout='constrained')
    codes=dict(deadline_failure=0,tradeoff_or_worse=1,unchanged=2,joint_model_gain=3)
    from matplotlib.colors import ListedColormap
    cmap=ListedColormap(['#db7872','#edc879','#c4ced5','#64b496'])
    for ax,b in zip(axes,s.a.BASELINES):
        arr=np.array([[codes[next(g['classification'] for g in groups if g['envelope']==e and g['policy']==pol and g['reference']==b)] for e in labels] for pol in s.POLICIES])
        ax.imshow(arr,vmin=-.5,vmax=3.5,cmap=cmap,aspect='auto')
        ax.set_yticks(range(len(s.POLICIES)),s.POLICIES,fontsize=8)
        ax.set_xticks(range(len(labels)),labels,rotation=60,ha='right',fontsize=7)
        ax.set_title('Reference: '+b+' | all 9 fresh-seed/context cases per cell')
    fig.suptitle('Model-condition map: red=deadline failure; amber=tradeoff/worse; grey=equal; green=joint non-worsening gain\nSynthetic inputs + frozen measured costs; not physical-device validation',fontsize=11)
    for ext in ('png','svg'):fig.savefig(folder/f'condition_map.{ext}',dpi=160)
    plt.close(fig)
    # Entire distribution, never only favorable test cases.
    fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
    for ax,b in zip(axes,s.a.BASELINES):
        for pol in s.POLICIES:
            gs=[g for g in groups if g['reference']==b and g['policy']==pol]
            ax.scatter([g['mean_delta_energy_j'] for g in gs],[g['mean_delta_peak_ap_c'] for g in gs],s=22,alpha=.65,label=pol)
        ax.axhline(0,color='grey',lw=.5);ax.axvline(0,color='grey',lw=.5)
        ax.set(xlabel='Mean candidate - reference J / 120s',ylabel='Mean peak AP difference C',title=b)
    axes[-1].legend(fontsize=6,loc='best')
    fig.suptitle('All 27 envelopes, including missed deadlines. Lower-left alone is NOT feasibility.')
    for ext in ('png','svg'):fig.savefig(folder/f'condition_tradeoffs.{ext}',dpi=160)
    plt.close(fig)
    table=''.join('<tr><td>'+html.escape(b)+'</td><td>'+html.escape(pol)+'</td><td>'+str(n)+'</td></tr>'
                  for b,x in summary['robust_joint_regions'].items() for pol,n in x.items())
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>조건별 스케줄링 탐색</title>
<style>body{font-family:system-ui;max-width:1300px;margin:30px auto;line-height:1.6}img{width:100%}td,th{padding:6px;border-bottom:1px solid #ccc} .warn{background:#fff2d0;padding:16px}</style>
<h1>어떤 조건에서 에너지·AP를 줄일 수 있는가</h1>
<p class="warn">실측 계수에 합성 도착과 공통 처리시간 전이 가정을 적용한 PC 탐색입니다. 새 실측·정확도 PASS·실제 절감률이 아닙니다. 기한 전체 충족과 J·최고 AP·AP 면적을 별도로 판독합니다. 응답 P95 손해도 CSV에 보존합니다.</p>
<p><a href="../README.md">설계·결과·한계</a> | <a href="condition_support.csv">모든 조건·기준별 결과</a> | <a href="frozen_selector_test.csv">개발에서 동결한 선택기의 새 seed 결과</a></p>
<img src="condition_map.png" alt="조건별 서비스 및 에너지 열 상충"><img src="condition_tradeoffs.png" alt="모든 조건의 에너지 열 차이">
<h2>9개 시험 문맥 모두 기한 충족·비용 비악화, 적어도 하나 개선한 조건 수 / 27</h2><p>기준별 비교이며 가장 약한 기준만 골라 EFT보다 낫다고 주장하지 않습니다. 표시상 수치 허용값 1e-8은 부동소수 비교용이며 정확도 합격선이 아닙니다.</p><table><tr><th>기준</th><th>정책</th><th>조건 수</th></tr>'''+table+'</table></html>'
    (folder/'index.html').write_text(page,encoding='utf8')
    for svg in folder.glob('condition_*.svg'):
        svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True)
    report(parser.parse_args().folder)
