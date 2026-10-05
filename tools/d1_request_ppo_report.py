"""Report a completed frozen PPO study without training or device access."""
import argparse
import csv
import html
import json
import statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tools import d1_request_rl as old

FAMILIES=old.FAMILIES


def read_csv(path):
    with Path(path).open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        for k,v in list(r.items()):
            if v=='':r[k]=None;continue
            try:r[k]=json.loads(v)
            except (ValueError,TypeError):pass
    return rows


def paired(rows):
    index={(r['trace_seed'],r['family'],r['scenario'],r['policy']):r for r in rows}
    differences=[]
    for r in rows:
        if not r['policy'].startswith('PPO_seed'):continue
        for baseline in ('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE','ENERGY_AP_REQUEST_V1','MC_RL_01'):
            b=index[(r['trace_seed'],r['family'],r['scenario'],baseline)]
            differences.append(dict(trace_seed=r['trace_seed'],family=r['family'],scenario=r['scenario'],
                learn_seed=int(r['policy'].split('seed')[1]),baseline=baseline,
                delta_deadline_met=r['deadline_met']-b['deadline_met'],
                delta_urgent_failure=r['urgent_service_failure']/r['urgent_n']-b['urgent_service_failure']/b['urgent_n'],
                delta_normal_failure=r['normal_service_failure']/r['normal_n']-b['normal_service_failure']/b['normal_n'],
                delta_j=r['energy_j']-b['energy_j'],
                delta_thermal=(r['thermal_degree_seconds']-b['thermal_degree_seconds']
                    if r['thermal_degree_seconds'] is not None and b['thermal_degree_seconds'] is not None else None),
                delta_peak=(r['peak_ap_c']-b['peak_ap_c'] if r['peak_ap_c'] is not None and b['peak_ap_c'] is not None else None),
                delta_p95=(r['urgent_p95_ms']-b['urgent_p95_ms'] if r['urgent_p95_ms'] is not None and b['urgent_p95_ms'] is not None else None),
                both_complete=r['completed']==r['planned'] and b['completed']==b['planned']))
    return differences


def cluster_intervals(differences):
    """Exploratory crossed seed x trace bootstrap, contexts kept together.

Not device error bars. Three training seeds and eight arrival traces do not
establish universal population coverage. Never resample requests as sessions.
"""
    rng=np.random.default_rng(20261005);rows=[]
    for family in FAMILIES:
        group=[r for r in differences if r['family']==family and r['baseline']=='EFT_REFERENCE']
        seeds=sorted({r['learn_seed'] for r in group});traces=sorted({r['trace_seed'] for r in group})
        for metric in ('delta_j','delta_thermal','delta_peak','delta_urgent_failure','delta_normal_failure','delta_p95'):
            if any(r[metric] is None for r in group):
                rows.append(dict(family=family,metric=metric,mean=None,low=None,high=None));continue
            array=np.array([[statistics.mean(r[metric] for r in group if r['learn_seed']==s and r['trace_seed']==t)
                             for t in traces] for s in seeds])
            samples=[]
            for _ in range(2000):
                ss=rng.integers(0,len(seeds),len(seeds));tt=rng.integers(0,len(traces),len(traces))
                samples.append(array[np.ix_(ss,tt)].mean())
            rows.append(dict(family=family,metric=metric,mean=float(array.mean()),
                             low=float(np.quantile(samples,.025)),high=float(np.quantile(samples,.975))))
    return rows


def aggregate(rows):
    out=[]
    for family in FAMILIES:
        for policy in dict.fromkeys(r['policy'] for r in rows):
            group=[r for r in rows if r['family']==family and r['policy']==policy]
            def avg(field):
                vals=[r[field] for r in group]
                return statistics.mean(vals) if all(v is not None for v in vals) else None
            out.append(dict(family=family,policy=policy,synthetic_conditions=len(group),
                arrival_traces=len({r['trace_seed'] for r in group}),
                planned=sum(r['planned'] for r in group),completed=sum(r['completed'] for r in group),
                deadline_met=sum(r['deadline_met'] for r in group),
                mean_energy_j=avg('energy_j'),mean_peak_ap_c=avg('peak_ap_c'),
                mean_thermal_degree_seconds=avg('thermal_degree_seconds'),mean_urgent_p95_ms=avg('urgent_p95_ms')))
    return out


def figure_save(fig,folder,name):
    fig.savefig(folder/(name+'.png'),dpi=150);fig.savefig(folder/(name+'.svg'));plt.close(fig)
    path=folder/(name+'.svg')
    path.write_text('\n'.join(x.rstrip() for x in path.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')


def report(folder):
    folder=Path(folder)
    summary=json.loads((folder/'summary.json').read_text(encoding='utf8'))
    freeze=json.loads((folder/'freeze_before_test.json').read_text(encoding='utf8'))
    if summary['selected']!=freeze['selected']:raise ValueError('selection changed after test')
    rows=read_csv(folder/'test.csv');training=read_csv(folder/'training.csv');validation=read_csv(folder/'validation.csv')
    if len(rows)!=768 or len(training)!=768 or len(validation)!=720:raise ValueError('incomplete experiment')
    for s in summary['selected']:
        if old.p.digest(folder/f'seed{s["seed"]}'/'selected_actor.json')!=s['actor_sha256']:raise ValueError('frozen actor changed')
    differences=paired(rows);intervals=cluster_intervals(differences);groups=aggregate(rows)
    for name,data in [('paired_differences.csv',differences),('exploratory_intervals.csv',intervals),('aggregate.csv',groups)]:
        old.csv_write(folder/name,data)
    seed_results=[]
    for seed in (11,23,37):
        ds=[r for r in differences if r['baseline']=='EFT_REFERENCE' and r['learn_seed']==seed]
        tr=[r for r in training if r['learn_seed']==seed]
        candidate=[r for r in rows if r['policy']==f'PPO_seed{seed}']
        seed_results.append(dict(seed=seed,training_decisions=sum(r['batch_steps'] for r in tr),
            minibatch_updates=sum(r['minibatch_updates'] for r in tr),
            last64_mean_entropy=statistics.mean(r['entropy'] for r in tr[-64:] if r['entropy'] is not None),
            last64_mean_kl=statistics.mean(r['kl'] for r in tr[-64:] if r['kl'] is not None),
            service_worse_cases=sum(r['delta_urgent_failure']>1e-9 or r['delta_normal_failure']>1e-9 for r in ds),
            thermal_worse_cases=sum(r['delta_thermal'] is not None and r['delta_thermal']>1e-8 for r in ds),
            both_constraints_cases=sum(r['both_complete'] and r['delta_urgent_failure']<=1e-9 and
                r['delta_normal_failure']<=1e-9 and r['delta_thermal'] is not None and r['delta_thermal']<=1e-8 for r in ds),
            mean_delta_j=statistics.mean(r['delta_j'] for r in ds),
            test_wait_actions=sum(r['actions'][2] for r in candidate),
            test_choice_decisions=sum(r['controllable_decisions'] for r in candidate)))
    old.p.write(folder/'seed_results.json',seed_results)
    fig,axes=plt.subplots(2,2,figsize=(12,7.5))
    for seed in (11,23,37):
        tr=[r for r in training if r['learn_seed']==seed]
        x=[r['update']*8 for r in tr]
        for ax,key,label in zip(axes.flat,['mean_energy_j','mean_urgent_miss','mean_normal_miss','entropy'],
                              ['Training batch energy (J)','Training urgent misses','Training normal misses','Policy entropy']):
            vals=np.array([r[key] if r[key] is not None else np.nan for r in tr])
            # Fixed16-update moving average for readability; CSV retains all raw values.
            smoothed=np.convolve(vals,np.ones(16)/16,mode='valid')
            ax.plot(x[15:],smoothed,label=f'seed {seed}');ax.set_title(label);ax.set_xlabel('Training episodes / seed');ax.grid(alpha=.2)
    axes[0,0].legend();fig.suptitle('PPO training: 3 seeds, 2048 episodes each; 16-update rolling mean')
    fig.tight_layout(rect=(0,0,1,.95));figure_save(fig,folder,'learning_curves')
    fig,axes=plt.subplots(1,3,figsize=(12,4.4))
    for ax,metric,title in zip(axes,['delta_j','delta_thermal','delta_p95'],
                              ['120 s J: PPO - EFT','AP burden (C s): PPO - EFT','Urgent P95 (ms): PPO - EFT']):
        rr=[next(r for r in intervals if r['family']==family and r['metric']==metric) for family in FAMILIES]
        if all(r['mean'] is not None for r in rr):
            ax.errorbar(range(4),[r['mean'] for r in rr],
                yerr=[[max(0,r['mean']-r['low']) for r in rr],[max(0,r['high']-r['mean']) for r in rr]],fmt='o',capsize=4)
        ax.axhline(0,color='black',lw=.8);ax.set_xticks(range(4),FAMILIES,rotation=20);ax.set_title(title,fontsize=10);ax.grid(alpha=.2)
    fig.suptitle('Frozen policies on untouched synthetic test traces; NOT device savings',fontsize=12)
    fig.text(.5,.01,'Exploratory 95% bootstrap: 3 learning seeds x 8 arrival traces; service contexts kept together.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.94));figure_save(fig,folder,'test_differences')
    fig,axes=plt.subplots(1,2,figsize=(10,4.5))
    for seed in (11,23,37):
        vv=[]
        for update in (0,64,128,192,256):
            rr=[r for r in validation if r['learn_seed']==seed and r['update']==update]
            vv.append((update*8,statistics.mean(r['urgent_service_failure']/r['urgent_n']+r['normal_service_failure']/r['normal_n'] for r in rr),
                       statistics.mean(r['energy_j'] for r in rr)))
        axes[0].plot([v[0] for v in vv],[v[1] for v in vv],marker='o',label=f'seed {seed}')
        axes[1].plot([v[0] for v in vv],[v[2] for v in vv],marker='o',label=f'seed {seed}')
    axes[0].set_title('Validation: sum of priority failure fractions');axes[1].set_title('Validation: mean120s J')
    for ax in axes:ax.set_xlabel('Training episodes / seed');ax.grid(alpha=.2)
    axes[0].legend();fig.suptitle('Validation used for checkpoint selection; not final test')
    fig.tight_layout(rect=(0,0,1,.94));figure_save(fig,folder,'validation_curves')
    def table(records):
        return '<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in records[0])+'</tr>'+''.join(
            '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r.values())+'</tr>' for r in records)+'</table>'
    (folder/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>요청별 PPO 학습과 최종 평가</title>
<style>body{font:15px system-ui;margin:24px;color:#203040}img{max-width:100%}td,th{border:1px solid #bbb;padding:6px}table{border-collapse:collapse}.note{background:#fff0d0;padding:15px}</style>
<h1>요청별 PPO: 3 seed 학습·검증 선택·동결 후 최종 평가</h1>
<p class="note">실측 모형 위 합성입력 평가입니다. 새 실기기 절감·정확도 PASS가 아닙니다. 이전96회 초기 시험과 구분합니다. 서로 다른 seed의 좋은 결과만 선택하지 않습니다. 완료/서비스와 J/AP 상충을 함께 읽어야 합니다.</p>
<p><a href="../README.md">계약·결론·한계</a> · <a href="test.csv">최종768행</a> · <a href="paired_differences.csv">정책별 대응 차이</a> · <a href="training.csv">학습 원곡선</a></p>
<h2>학습과 검증</h2><img src="learning_curves.png" alt="학습seed별 곡선"><img src="validation_curves.png" alt="선정에 사용한 검증 곡선">
<h2>학습seed 전체 판독</h2>'''+table(seed_results)+'''<h2>최종 PC 평가</h2><img src="test_differences.png" alt="최종평가에서 PPO-EFT 대응차이">
<p>오차막대는 제한된 합성입력과학습seed의탐색적bootstrap입니다. 센서/실측오차범위가 아닙니다. 각family24조건은8도착열×3문맥, 정책별P95평균은pooled P95가 아닙니다.</p>'''+table(groups)+'</html>',encoding='utf8')
    return seed_results


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True)
    args=parser.parse_args();print(report(args.folder))
