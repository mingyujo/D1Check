"""Separate PC diagnosis: prediction-vs-realization and post-hoc energy/AP sensitivity.

The frozen engine, policies and source vectors are reused unchanged. No device I/O.
All power and temperature coefficients come from the explicit stress CONFIG.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_plan as io
from tools import d1_arrival_energy_sensitivity as prior
from tools import d1_energy_thermal as thermal

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'docs/results/arrival_diagnostic_02/CONFIG.json'
OUTPUT = CONFIG.parent
BUNDLE = ROOT / 'docs/results/arrival_explore_20260925/input_bundle'
FREEZE = ROOT / 'docs/results/arrival_explore_20260925/freeze_before_evaluation.json'
POLICIES = ('CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC')
P = 'P_PAIR_COST_PC'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def state_durations(result, horizon_ns):
    if any(r['status'] != 'succeeded' or r.get('lane_available_ns', math.inf) > horizon_ns
           for r in result['ledger']):
        raise ValueError('incomplete 120s ledger: no zero-energy imputation')
    segments = thermal.ledger_segments(result, horizon_ns)
    durations = defaultdict(float)
    for s in segments:
        key = 'pair' if '+' in s['state'] else 'idle' if s['state'] == 'idle' else 'single'
        durations[key] += s['end_s'] - s['start_s']
        if s['waiting']:
            s['state'] += '|queued'
    if not math.isclose(sum(durations.values()), horizon_ns/1e9, abs_tol=1e-7):
        raise ValueError('state interval coverage')
    return dict(durations), segments


def energy(durations, idle, single, pair):
    return durations.get('idle', 0)*idle + durations.get('single', 0)*single + durations.get('pair', 0)*pair


def threshold(delta, idle, single):
    a = delta.get('pair', 0)
    b = delta.get('idle', 0)*idle + delta.get('single', 0)*single
    if abs(a) <= 1e-9:
        return None, 'identical_all_pair_powers' if abs(b) <= 1e-9 else 'no_pair_time_difference'
    return -b/a, 'finite_algebraic_boundary_not_physical_range'


def ap_account(segments, initial, pair_eq, config):
    names = {s['state'] for s in segments}
    profile = prior.profile(2., pair_eq, names)
    # These five values are declared in CONFIG, not fitted to confirmation data.
    for key, state in profile['states'].items():
        base = key.split('|')[0]
        state['thermal']['AP']['equilibrium_c'] = (
            config['ap_stress']['idle_equilibrium_c'] if base == 'idle'
            else pair_eq if '+' in base else config['ap_stress']['single_equilibrium_c'])
        state['thermal']['AP']['tau_s'] = config['ap_stress']['tau_s']
    account = thermal.account(segments, profile, device=profile['device'], model=profile['model'],
        mode='assumption_exploration', initial_temperature={'AP': initial},
        planned=24, completed=24)
    return account


def ap_at(trace, initial, second, tau_s):
    if second == 0:
        return initial
    for segment in trace:
        if segment['start_s'] <= second <= segment['end_s']:
            dt = second - segment['start_s']
            start = segment['temperature_start']['AP']
            end = segment['temperature_end']['AP']
            duration = segment['end_s'] - segment['start_s']
            if not duration:
                return end
            # The trace profile uses one first-order law per segment; recover its
            # equilibrium from start/end for interpolation, without refitting.
            decay = math.exp(-duration/tau_s)
            eq = (end-start*decay)/(1-decay) if decay != 1 else start
            return thermal.transition(start, eq, tau_s, dt)
    raise ValueError('AP sample outside 120s trace')


def build(config_path=CONFIG, output=OUTPUT):
    config_path, output = Path(config_path), Path(output)
    contract = json.loads(config_path.read_text(encoding='utf-8'))
    assert contract['baseline_policies'] == list(POLICIES)
    assert contract['scenarios'] == ['low', 'queue', 'burst']
    assert contract['seeds'] == [201, 202, 203, 204, 205]
    assert contract['realized_interference'] == [1., 1.5, 2.]
    assert contract['p_predicted_interference'] == [1., 1.5, 2.]
    assert contract['common_window_s'] == 120
    receipt = io.read(BUNDLE / 'receipt.json')
    for name in ('estimates.json', 'realizations.json'):
        if io.digest(BUNDLE/name) != receipt['files'][name]:
            raise ValueError('source bundle hash')
    estimate = io.read(BUNDLE/'estimates.json')
    vectors = io.read(BUNDLE/'realizations.json')
    freeze = io.read(FREEZE)
    settings_base = batch.defaults('explore')
    settings_base.update({k: freeze['B2']['explore']['settings'][k]
                          for k in ('static_map', 'static_parallel')})
    horizon = contract['common_window_s']*1_000_000_000
    metrics, main, representative = [], {}, {}
    for scenario in contract['scenarios']:
        requests = batch.workload(scenario, 'evaluation')
        for seed in contract['seeds']:
            for realized in contract['realized_interference']:
                for policy in (*POLICIES, P):
                    predictions = contract['p_predicted_interference'] if policy == P else [1.5]
                    for predicted in predictions:
                        settings = dict(settings_base, interference=realized,
                                        predicted_interference=predicted)
                        result = engine.simulate(estimate, vectors, requests, policy=policy,
                                                 settings=settings, seed=seed, horizon_ns=horizon)
                        m = result['metrics']
                        metrics.append(dict(scenario=scenario, seed=seed, realized=realized,
                            predicted=predicted if policy == P else '', policy=policy,
                            urgent_p95_ms=m['urgent_p95_ms'], normal_mean_ms=m['normal_mean_ms'],
                            urgent_not_timely_rate=m['urgent_deadline_violation'],
                            normal_not_timely_rate=1-m['normal_timely'],
                            unfinished=m['unfinished'], planned=m['planned'],
                            urgent_planned=m['urgent_n'], normal_planned=m['normal_n'],
                            evidence='frozen-PC-engine-diagnostic; no device validation'))
                        if policy != P or predicted == 1.5:
                            main[scenario,seed,realized,policy] = result
                        if scenario == 'queue' and seed == 201 and realized in (1.,1.5,2.) and policy in (P,'B3_SOLO_EFT_PC'):
                            representative[policy,realized,predicted] = result
    write_csv(output/'interference_metrics.csv', metrics)
    index = {(r['scenario'],r['seed'],r['realized'],r['policy'],r['predicted']):r for r in metrics}
    paired = []
    for scenario in contract['scenarios']:
        for seed in contract['seeds']:
            for realized in contract['realized_interference']:
                baseline = index[scenario,seed,realized,'B3_SOLO_EFT_PC','']
                for predicted in contract['p_predicted_interference']:
                    p = index[scenario,seed,realized,P,predicted]
                    paired.append(dict(scenario=scenario,seed=seed,realized=realized,predicted=predicted,
                        prediction_relation='matched_diagnostic' if predicted == realized else 'over' if predicted>realized else 'under',
                        p_minus_b3_urgent_p95_ms=p['urgent_p95_ms']-baseline['urgent_p95_ms'],
                        p_minus_b3_normal_mean_ms=p['normal_mean_ms']-baseline['normal_mean_ms'],
                        p_minus_b3_urgent_not_timely_pp=100*(p['urgent_not_timely_rate']-baseline['urgent_not_timely_rate']),
                        p_minus_b3_normal_not_timely_pp=100*(p['normal_not_timely_rate']-baseline['normal_not_timely_rate']),
                        p_unfinished=p['unfinished'],b3_unfinished=baseline['unfinished'],planned=p['planned']))
    write_csv(output/'interference_paired.csv', paired)
    summary=[]
    for scenario in contract['scenarios']:
        for realized in contract['realized_interference']:
            for predicted in contract['p_predicted_interference']:
                group=[r for r in paired if (r['scenario'],r['realized'],r['predicted'])==(scenario,realized,predicted)]
                summary.append(dict(scenario=scenario,realized=realized,predicted=predicted,seeds=len(group),
                    p_minus_b3_urgent_p95_ms_mean=statistics.mean(r['p_minus_b3_urgent_p95_ms'] for r in group),
                    p_minus_b3_urgent_p95_ms_min=min(r['p_minus_b3_urgent_p95_ms'] for r in group),
                    p_minus_b3_urgent_p95_ms_max=max(r['p_minus_b3_urgent_p95_ms'] for r in group),
                    p_minus_b3_normal_mean_ms_mean=statistics.mean(r['p_minus_b3_normal_mean_ms'] for r in group),
                    p_minus_b3_urgent_not_timely_pp_mean=statistics.mean(r['p_minus_b3_urgent_not_timely_pp'] for r in group),
                    p_minus_b3_normal_not_timely_pp_mean=statistics.mean(r['p_minus_b3_normal_not_timely_pp'] for r in group),
                    total_p_unfinished=sum(r['p_unfinished'] for r in group),
                    total_b3_unfinished=sum(r['b3_unfinished'] for r in group),
                    total_planned=sum(r['planned'] for r in group)))
    write_csv(output/'interference_summary.csv',summary)
    # A compact, deterministic comparison at the decision boundary; no policy edit.
    sample={}
    for (policy,realized,predicted),result in representative.items():
        decisions=[d for d in result['decisions'] if 190_000_000 <= d['now_ns'] <= 650_000_000]
        request=next(r for r in result['ledger'] if r['id']=='evaluation/queue/1')
        sample[f'{policy}/real{realized}/pred{predicted}']=dict(decisions=decisions[:8],request=request,
                                                  metrics=result['metrics'])
    (output/'representative_queue_decisions.json').write_text(json.dumps(sample,ensure_ascii=False,indent=2),encoding='utf-8')
    # Energy/AP use the default P predictor 1.5 versus each unchanged baseline.
    durations,segments={},{}
    for key,result in main.items():
        durations[key],segments[key]=state_durations(result,horizon)
    power_rows=[]
    power_pairs=list(zip(contract['energy_stress_w']['idle'],
                         contract['energy_stress_w']['single_active']))
    if len(power_pairs) != 3:
        raise ValueError('declared paired idle/single stress grid changed')
    for scenario in contract['scenarios']:
        for seed in contract['seeds']:
            for realized in contract['realized_interference']:
                p=durations[scenario,seed,realized,P]
                for comparator in POLICIES:
                    b=durations[scenario,seed,realized,comparator]
                    delta={k:p.get(k,0)-b.get(k,0) for k in ('idle','single','pair')}
                    for idle,single in power_pairs:
                        cross,status=threshold(delta,idle,single)
                        for pair in contract['energy_stress_w']['pair']:
                            ep,eb=energy(p,idle,single,pair),energy(b,idle,single,pair)
                            power_rows.append(dict(scenario=scenario,seed=seed,realized=realized,
                                p_predicted=1.5,comparator=comparator,idle_w_assumed=idle,
                                single_w_assumed=single,pair_w_assumed=pair,
                                p_energy_j_assumed=ep,comparator_energy_j_assumed=eb,
                                p_minus_comparator_j=ep-eb,
                                p_minus_comparator_relative_pct=100*(ep-eb)/eb,
                                delta_idle_s=delta['idle'],delta_single_s=delta['single'],
                                delta_pair_s=delta['pair'],pair_power_cross_w_algebraic=cross,
                                cross_status=status,planned=24,completed=24,common_window_s=120))
    write_csv(output/'energy_boundaries.csv',power_rows)
    ap_rows=[]
    ap_paths=[]
    for scenario in contract['scenarios']:
        for seed in contract['seeds']:
            for realized in contract['realized_interference']:
                for initial in contract['ap_stress']['initial_c']:
                    for pair_eq in contract['ap_stress']['pair_equilibrium_c']:
                        a=ap_account(segments[scenario,seed,realized,P],initial,pair_eq,contract)
                        b=ap_account(segments[scenario,seed,realized,'B3_SOLO_EFT_PC'],initial,pair_eq,contract)
                        difference=[ap_at(a['trace'],initial,t,contract['ap_stress']['tau_s'])
                                    -ap_at(b['trace'],initial,t,contract['ap_stress']['tau_s'])
                                    for t in range(0,121,5)]
                        if seed == 201 and realized == 1.5 and initial == 29.:
                            ap_paths.extend(dict(scenario=scenario,seed=seed,realized=realized,
                                initial_ap_c_assumed=initial,pair_ap_equilibrium_c_assumed=pair_eq,
                                time_s=t,p_minus_b3_ap_c_assumed=difference[t//5],
                                evidence='post-hoc thermal stress, no feedback')
                                for t in range(0,121,5))
                        ap_rows.append(dict(scenario=scenario,seed=seed,realized=realized,
                            p_predicted=1.5,initial_ap_c_assumed=initial,
                            pair_ap_equilibrium_c_assumed=pair_eq,tau_s_assumed=contract['ap_stress']['tau_s'],
                            p_ap_peak_c_assumed=a['peak_temperature']['AP'],
                            b3_ap_peak_c_assumed=b['peak_temperature']['AP'],
                            p_minus_b3_peak_c_assumed=a['peak_temperature']['AP']-b['peak_temperature']['AP'],
                            p_minus_b3_end_c_assumed=difference[-1],
                            max_abs_path_difference_c_assumed=max(map(abs,difference)),
                            common_window_s=120,evidence='post-hoc state-thermal stress, no feedback'))
    write_csv(output/'ap_sensitivity.csv',ap_rows)
    write_csv(output/'ap_path_representative.csv',ap_paths)
    provenance={str(x.relative_to(ROOT)):sha(x) for x in
                (config_path,BUNDLE/'estimates.json',BUNDLE/'realizations.json',FREEZE,
                 ROOT/'tools/d1_arrival_explore.py',ROOT/'tools/d1_arrival_explore_batch.py',
                 ROOT/'tools/d1_energy_thermal.py',ROOT/'tools/d1_arrival_energy_sensitivity.py',
                 ROOT/'tools/d1_arrival_diagnostic.py',
                 ROOT/'tools/assets/d1_arrival_diagnostic.html')}
    (output/'SOURCE_HASHES.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    figures(output,summary,paired,power_rows,ap_rows,ap_paths)
    dashboard(output,contract,metrics,paired,power_rows,ap_rows)
    return metrics,paired,power_rows,ap_rows


def save_figure(fig, output, name):
    import matplotlib.pyplot as plt
    for ext in ('png','svg'):
        fig.savefig(output/f'{name}.{ext}',dpi=140,
                    metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig)
    svg=output/f'{name}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


def figures(output,summary,paired,power,ap,ap_paths):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.is_file():
        font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']='Malgun Gothic'
    plt.rcParams['axes.unicode_minus']=False
    plt.rcParams['svg.hashsalt']='arrival-diagnostic-02'
    scenarios=('low','queue','burst'); factors=(1.,1.5,2.)
    for scenario in scenarios:
        fig,axes=plt.subplots(2,2,figsize=(11,8))
        specs=[('p_minus_b3_urgent_p95_ms','긴급 P95 차이 (ms)'),
               ('p_minus_b3_normal_mean_ms','일반 평균응답 차이 (ms)'),
               ('p_minus_b3_urgent_not_timely_pp','긴급 기한 미충족 차이 (%p)'),
               ('p_minus_b3_normal_not_timely_pp','일반 기한 미충족 차이 (%p)')]
        for ax,(key,title) in zip(axes.flat,specs):
            scale=max(1e-9,max(abs(r[key]) for r in paired if r['scenario']==scenario))
            for yi,r in enumerate(factors):
                for xi,p in enumerate(factors):
                    cells=[x[key] for x in paired if (x['scenario'],x['realized'],x['predicted'])==(scenario,r,p)]
                    mean=statistics.mean(cells)
                    ax.add_patch(plt.Rectangle((xi-.5,yi-.5),1,1,facecolor=plt.cm.RdBu_r(.5+mean/(2*scale))))
                    ax.text(xi,yi,f'{mean:+.1f}\n[{min(cells):+.1f},{max(cells):+.1f}]',ha='center',va='center',fontsize=8)
            ax.set(xlim=(-.5,2.5),ylim=(2.5,-.5),xticks=range(3),xticklabels=factors,
                   yticks=range(3),yticklabels=factors,xlabel='예상 간섭',ylabel='실현 간섭',title=title)
        fig.suptitle(f'{scenario} · P-B3, 5 seed 평균 [최소,최대] · PC 진단, 실측 아님')
        fig.tight_layout();save_figure(fig,output,f'interference_heatmap_{scenario}')
    fig,axes=plt.subplots(1,3,figsize=(13,4),sharey=True)
    for ax,scenario in zip(axes,scenarios):
        group=[x for x in power if x['scenario']==scenario and x['realized']==1.5 and
               x['comparator']=='B3_SOLO_EFT_PC' and x['idle_w_assumed']==1 and x['single_w_assumed']==2]
        for seed in range(201,206):
            pair=sorted((r for r in group if r['seed']==seed),key=lambda r:r['pair_w_assumed'])
            ax.plot([r['pair_w_assumed'] for r in pair],[r['p_minus_comparator_j'] for r in pair],
                    marker='o',label=f'seed{seed}')
            cross=pair[0]['pair_power_cross_w_algebraic']
            if cross is not None and 2<=cross<=3:ax.scatter(cross,0,marker='x',color='black')
        ax.axhline(0,color='black',lw=.8);ax.set(title=scenario,xlabel='병행 전력 가정 (W)')
    axes[0].set_ylabel('P-B3 공통창 에너지 차이 (가정 J)')
    axes[-1].legend(fontsize=8)
    fig.suptitle('idle=1W, 단일=2W 고정 · seed별 선형식 · 2~3W는 물리 범위 아님')
    fig.tight_layout();save_figure(fig,output,'energy_power_lines')
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,scenario in zip(axes,scenarios):
        group=[x for x in power if x['scenario']==scenario and x['comparator']=='B3_SOLO_EFT_PC'
               and x['idle_w_assumed']==1 and x['single_w_assumed']==2 and x['pair_w_assumed']==2]
        for r in (1.,1.5,2.):
            point=[x for x in group if x['realized']==r]
            for j,x in enumerate(point):
                boundary=x['pair_power_cross_w_algebraic']
                if boundary is not None:
                    ax.scatter(r+(j-2)*.04,boundary,color=plt.cm.tab10(j),s=32,
                               label=f"seed{x['seed']}" if scenario=='queue' and r==1. else None)
        if scenario=='low':
            ax.text(.5,.5,'5 seed 모두 동일 일정\n경계 없음',ha='center',va='center',
                    transform=ax.transAxes,fontsize=11)
        ax.axhline(0,color='gray',lw=.8);ax.set(title=scenario,xlabel='실현 간섭 가정',xticks=(1.,1.5,2.))
    axes[0].set_ylabel('대수적 병행 전력 동률점 (W)')
    axes[1].legend(fontsize=8,loc='upper left')
    fig.suptitle('5 seed별 동률점 · 표시값은 실측 가능한 전력 범위가 아님')
    fig.tight_layout();save_figure(fig,output,'energy_crossings')
    fig,axes=plt.subplots(1,3,figsize=(13,4),sharey=True)
    for ax,scenario in zip(axes,scenarios):
        group=[x for x in ap if x['scenario']==scenario and x['realized']==1.5]
        for init in (29.,31.):
            for eq in (30.,42.):
                points=[x['p_minus_b3_peak_c_assumed'] for x in group if x['initial_ap_c_assumed']==init and x['pair_ap_equilibrium_c_assumed']==eq]
                ax.scatter([eq+(init-30)*.15]*len(points),points,label=f'시작{init:g}°C' if eq==30 else None,alpha=.65)
        ax.axhline(0,color='gray',lw=.8);ax.set(title=scenario,xlabel='병행 AP 평형 가정 (°C)',xticks=(30,42))
    axes[0].set_ylabel('P-B3 AP 최고 차이 (가정 °C)')
    axes[-1].legend(fontsize=8)
    fig.suptitle('seed별 점 · τ=60초 · 열 피드백 없음 · 물리 범위 아님')
    fig.tight_layout();save_figure(fig,output,'ap_stress')
    fig,axes=plt.subplots(1,3,figsize=(13,4),sharey=True)
    for ax,scenario in zip(axes,scenarios):
        for eq in (30.,42.):
            group=[x for x in ap_paths if x['scenario']==scenario and x['pair_ap_equilibrium_c_assumed']==eq]
            ax.plot([x['time_s'] for x in group],[x['p_minus_b3_ap_c_assumed'] for x in group],
                    label=f'병행 평형{eq:g}°C')
        ax.axhline(0,color='gray',lw=.8);ax.set(title=scenario,xlabel='첫 도착 후 시간 (s)')
    axes[0].set_ylabel('P-B3 AP 경로 차이 (가정 °C)')
    axes[-1].legend(fontsize=8)
    fig.suptitle('대표 seed201 · 실현1.5 · 초기29°C · 5초 간격 · 사후 열 가정')
    fig.tight_layout();save_figure(fig,output,'ap_path_representative')


def dashboard(output,contract,metrics,paired,power,ap):
    template=(ROOT/'tools/assets/d1_arrival_diagnostic.html').read_text(encoding='utf-8')
    payload=dict(config=contract,metrics=metrics,paired=paired,power=power,ap=ap)
    html=template.replace('/*__DATA__*/','const DATA='+json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';')
    (output/'diagnostic.html').write_text(html,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    build(args.config,args.output)
