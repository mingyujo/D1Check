"""Summarize frozen PC matrix; optional prespecified decision-cost stress on seen seeds."""
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as arrival
from tools import d1_arrival_thermal_feedback as feedback
from tools import d1_arrival_thermal_feedback_batch as study

OUT=study.OUTPUT
NUMERIC=('urgent_p95_ms','normal_mean_ms','energy_120s_j_assumed',
         'ap_peak_c_assumed','ap_over_limit_s_assumed','makespan_s')
COUNTS=('urgent_miss_count','normal_miss_count','unfinished','completed',
        'planned','urgent_planned','normal_planned','voluntary_wait_decisions','fallback_decisions')


def summarize(source=OUT):
    source=Path(source)
    rows=list(csv.DictReader((source/'metrics.csv').open(encoding='utf-8',newline='')))
    grouped=defaultdict(list);matched=defaultdict(dict)
    for row in rows:
        key=(row['phase'],row['profile'],row['scenario'])
        grouped[key,row['policy']].append(row)
        matched[key,row['seed']][row['policy']]=row
    summaries=[];pairs=[]
    for (key,policy),data in sorted(grouped.items()):
        if len(data)!=2 or any((int(r['planned']),int(r['urgent_planned']),int(r['normal_planned']))!=(24,6,18)
                            for r in data):raise ValueError('unbalanced denominators')
        item=dict(phase=key[0],profile=key[1],scenario=key[2],policy=policy,
                  pc_seeds=2,independent_device_sessions=0)
        item.update({f'mean_{name}':sum(float(r[name]) for r in data)/2 for name in NUMERIC})
        item.update({f'total_{name}':sum(int(r[name]) for r in data) for name in COUNTS})
        summaries.append(item)
    for (key,seed),policies in sorted(matched.items()):
        if set(policies)!=set(study.read(study.CONFIG)['compared_policies']):
            raise ValueError('missing policy under matched seed/profile/scenario')
        new=policies[feedback.POLICY]
        for baseline in ('CPU_URGENT','B2_PC','B3_SOLO_EFT_PC'):
            old=policies[baseline]
            d={name:float(new[name])-float(old[name]) for name in NUMERIC}
            count_d={name:int(new[name])-int(old[name]) for name in COUNTS}
            response_worse=any(d[name]>1e-9 for name in ('urgent_p95_ms','normal_mean_ms')) or any(
                count_d[name]>0 for name in ('urgent_miss_count','normal_miss_count','unfinished'))
            pairs.append(dict(phase=key[0],profile=key[1],scenario=key[2],seed=seed,
                candidate=feedback.POLICY,baseline=baseline,
                **{f'delta_{name}':value for name,value in d.items()},
                **{f'delta_{name}':value for name,value in count_d.items()},
                energy_better=d['energy_120s_j_assumed'] < -1e-9,
                ap_peak_better=d['ap_peak_c_assumed'] < -1e-9,
                no_response_or_completion_loss=not response_worse,
                evidence='matched PC seed, unmeasured stress coefficients'))
    study.write_csv(source/'summary.csv',summaries)
    study.write_csv(source/'paired_differences.csv',pairs)
    return summaries,pairs


def decision_cost_stress(source=OUT):
    """Already specified 5-ms cost, retrospectively applied to seen development seeds only."""
    config=study.read(study.CONFIG);frozen=study.read(study.FREEZE)
    estimates=study.read(study.INPUT/'estimates.json');vectors=study.read(study.INPUT/'realizations.json')
    rows=[]
    for scenario in config['scenario']:
        for seed in config['development_seeds_seen_before']:
            profile=config['profiles'][2]  # predeclared energy_shift stress assumption
            settings=study.settings(feedback.POLICY,config,frozen)
            settings['decision_ns']=config['candidate_decision_ns_stress']
            result=engine.simulate(estimates,vectors,arrival.workload(scenario,'evaluation'),
                policy=feedback.POLICY,settings=settings,seed=seed,thermal_model=study.model(profile,config))
            result['thermal_model_limit_c']=profile['ap_limit_c_research']
            rows.append(study.metric_row('posthoc_seen_seed_cost_stress',profile['id'],scenario,seed,
                                         feedback.POLICY,result))
    study.write_csv(Path(source)/'decision_cost_stress.csv',rows)
    return rows


if __name__=='__main__':
    summary,pairs=summarize()
    stressed=decision_cost_stress()
    print(f'{len(summary)} summaries, {len(pairs)} paired comparisons, {len(stressed)} seen-seed cost stresses')
