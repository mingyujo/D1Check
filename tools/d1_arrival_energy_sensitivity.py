"""Post-hoc, assumption-only energy/AP accounting of the published seed-201 ledgers.

Never transfers fixed 870-job or legacy MobileNet coefficients to arrivals. The
arrival event engine is not rerun, and the thermal state never feeds scheduling.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from tools import d1_arrival_energy_research as research
from tools import d1_arrival_explore_batch as batch
from tools import d1_energy_thermal as thermal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/results/arrival_visualization_01/timeline.csv'
OUTPUT = ROOT / 'docs/results/arrival_visualization_01'
POLICIES = ('CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC')
SCENARIOS = ('low', 'queue', 'burst')
MODES = ('strict', 'explore')
HORIZON = 120_000_000_000
GRID = ((2.0, 30.0), (2.0, 42.0), (3.0, 30.0), (3.0, 42.0))
TIME_FIELDS = ('arrival_ns', 'deadline_offset_ns', 'dispatch_ns', 'execution_start_ns',
               'output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')


def load_timelines(path=SOURCE):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    groups = defaultdict(list)
    for row in rows:
        if row['scenario'] not in SCENARIOS or row['mode'] not in MODES or row['policy'] not in POLICIES:
            continue
        item = {k: row[k] for k in ('id', 'task', 'priority', 'backend', 'status')}
        item.update({k: int(row[k]) for k in TIME_FIELDS if row[k] != ''})
        groups[(row['mode'], row['scenario'], row['policy'])].append(item)
    if len(groups) != len(MODES)*len(SCENARIOS)*len(POLICIES):
        raise ValueError('representative policy/scenario coverage incomplete')
    for key, ledger in groups.items():
        if len(ledger) != 24 or any(r['status'] != 'succeeded' for r in ledger):
            raise ValueError(f'incomplete schedule: {key}')
        requests = {r['id']: r for r in batch.workload(key[1], 'evaluation')}
        if set(requests) != {r['id'] for r in ledger}:
            raise ValueError(f'request mismatch: {key}')
        for row in ledger:
            if any(row[k] != requests[row['id']][k] for k in ('task','priority','arrival_ns','deadline_offset_ns')):
                raise ValueError(f'scheduled input mismatch: {key}')
    return groups


def state_key(segment):
    return segment['state'] + ('|queued' if segment['waiting'] else '')


def profile(pair_power_w, pair_equilibrium_c, state_names):
    """Illustrative stress axes, not an empirical power/thermal interval."""
    states = {}
    for key in sorted(state_names):
        base = key.split('|')[0]
        pair = '+' in base
        idle = base == 'idle'
        power = 1.0 if idle else pair_power_w if pair else 2.0
        equilibrium = 29.0 if idle else pair_equilibrium_c if pair else 34.0
        states[key] = dict(power_w=power,
                           thermal={'AP': dict(equilibrium_c=equilibrium, tau_s=60.0)})
    return dict(version=thermal.VERSION, evidence='explicit_assumptions',
        device='hypothetical-A24-like', model='two-model hypothetical arrival states',
        source='researcher stress grid; no arrival power/AP calibration',
        unit_status='assumed whole-device W and AP degrees C; not measured A24 units',
        sensors=['AP'], reference_temperature={'AP':29.0}, states=states)


def sample_path(trace, prof, seconds):
    if seconds == 0:
        return 0., 29.
    previous_energy = 0.
    for segment in trace:
        if segment['start_s'] <= seconds <= segment['end_s']:
            elapsed = seconds-segment['start_s']
            duration = segment['end_s']-segment['start_s']
            power = (segment['cumulative_energy_j']-previous_energy)/duration
            law = prof['states'][segment['state']]['thermal']['AP']
            return (previous_energy + power*elapsed,
                    thermal.transition(segment['temperature_start']['AP'], law['equilibrium_c'],
                                       law['tau_s'], elapsed))
        previous_energy = segment['cumulative_energy_j']
    raise ValueError('common-window sample outside trace')


def add_dominance(rows):
    keys = ('urgent_p95_ms','normal_mean_ms','urgent_not_timely_rate',
            'normal_not_timely_rate','energy_j_assumed','ap_peak_c_assumed')
    groups = defaultdict(list)
    for row in rows:
        groups[(row['scenario'], row['mode'], row['profile'])].append(row)
    for group in groups.values():
        for row in group:
            row['nondominated_in_stress_grid'] = not any(
                other is not row and all(other[k] <= row[k]+1e-10 for k in keys)
                and any(other[k] < row[k]-1e-10 for k in keys)
                for other in group)


def build(source=SOURCE, output=OUTPUT):
    output = Path(output)
    schedules = load_timelines(source)
    segments = {key: thermal.ledger_segments({'ledger': ledger}, HORIZON)
                for key, ledger in schedules.items()}
    state_names = {state_key(s) for schedule in segments.values() for s in schedule}
    rows, paths, profiles = [], [], {}
    for pair_power, pair_heat in GRID:
        ident = f'P{pair_power:g}_T{pair_heat:g}'
        prof = profile(pair_power, pair_heat, state_names)
        profiles[ident] = prof
        for (mode, scenario, policy), ledger in schedules.items():
            result = research.aggregate(batch.workload(scenario,'evaluation'),
                {'ledger':ledger,'policy':policy}, horizon_ns=HORIZON,
                profile=prof, initial_ap_c=29.)
            energy = result['energy_ap']
            if energy['status'] != 'ASSUMPTION_EXPLORATION_ONLY':
                raise ValueError(f'unsupported accounting: {mode}/{scenario}/{policy}')
            service = result['service']
            rows.append(dict(profile=ident, mode=mode, scenario=scenario, policy=policy,
                seed=201, evidence='assumption_exploration_only',
                planned=service['planned'], completed=service['succeeded'], unfinished=service['unfinished'],
                urgent_p95_ms=service['urgent']['response_p95_ms'],
                normal_mean_ms=service['normal']['response_mean_ms'],
                urgent_not_timely_rate=service['urgent']['not_confirmed_timely_rate'],
                normal_not_timely_rate=service['normal']['not_confirmed_timely_rate'],
                work_completion_s=max(r['lane_available_ns'] for r in ledger)/1e9,
                energy_j_assumed=energy['whole_device_energy_j'],
                ap_peak_c_assumed=energy['ap_peak_c'],
                initial_ap_c_assumed=29., common_window_s=120.,
                pair_power_w_assumed=pair_power, pair_equilibrium_c_assumed=pair_heat))
            for sec in range(0,121,5):
                e,t = sample_path(energy['state_trace'],prof,sec)
                paths.append(dict(profile=ident, mode=mode, scenario=scenario, policy=policy,
                    seed=201, time_s=sec, cumulative_energy_j_assumed=e, ap_c_assumed=t,
                    evidence='assumption_exploration_only'))
    add_dominance(rows)
    contrasts=[]
    for mode in MODES:
        for scenario in SCENARIOS:
            for ident in profiles:
                group={r['policy']:r for r in rows if (r['mode'],r['scenario'],r['profile'])==(mode,scenario,ident)}
                p,b=group['P_PAIR_COST_PC'],group['B3_SOLO_EFT_PC']
                contrasts.append(dict(mode=mode,scenario=scenario,profile=ident,seed=201,
                    p_minus_b3_energy_j_assumed=p['energy_j_assumed']-b['energy_j_assumed'],
                    p_minus_b3_ap_peak_c_assumed=p['ap_peak_c_assumed']-b['ap_peak_c_assumed'],
                    p_minus_b3_urgent_p95_ms=p['urgent_p95_ms']-b['urgent_p95_ms'],
                    p_minus_b3_normal_mean_ms=p['normal_mean_ms']-b['normal_mean_ms']))
    break_even=[]
    for mode in MODES:
        for scenario in SCENARIOS:
            durations={}
            for policy in ('P_PAIR_COST_PC','B3_SOLO_EFT_PC'):
                acc=defaultdict(float)
                for segment in segments[(mode,scenario,policy)]:
                    state=segment['state']; kind='pair' if '+' in state else 'idle' if state=='idle' else 'single'
                    acc[kind]+=segment['end_s']-segment['start_s']
                durations[policy]=acc
            p,b=durations['P_PAIR_COST_PC'],durations['B3_SOLO_EFT_PC']
            delta={kind:p[kind]-b[kind] for kind in ('idle','single','pair')}
            threshold=-(delta['idle']+2*delta['single'])/delta['pair'] if abs(delta['pair'])>1e-9 else None
            break_even.append(dict(mode=mode,scenario=scenario,seed=201,
                delta_idle_s=delta['idle'],delta_single_s=delta['single'],delta_pair_s=delta['pair'],
                pair_power_break_even_w_assumed=threshold,
                meaning='post-hoc threshold for P-B3 energy equality; not empirical feasible range'))
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'arrival_energy_stress.csv',rows)
    write_csv(output/'arrival_energy_stress_path.csv',paths)
    write_csv(output/'arrival_energy_stress_contrasts.csv',contrasts)
    write_csv(output/'arrival_energy_stress_break_even.csv',break_even)
    manifest=dict(version='arrival-energy-stress-pc-v1', source_timeline=str(Path(source).name),
        evidence='explicit_assumptions_only', device_sessions=0, simulation_seed=201,
        horizon_s=120, initial_ap_c_assumed=29.,
        power_w_assumed=dict(idle=1.,single_active=2.,pair=[2.,3.]),
        thermal_assumed=dict(idle_equilibrium_c=29.,single_equilibrium_c=34.,
            pair_equilibrium_c=[30.,42.],tau_s=60.),
        rationale='stress axes bracket a post-hoc queue P-B3 energy break-even; no measured physical range or calibration',
        queue_power_assumption='queued state uses same whole-device power as corresponding unqueued state, not zero or additive',
        scope='current two models, frozen synthetic 24-request seed-201 schedules only',
        no_feedback='energy/AP accounted after simulation; policy and execution durations unchanged',
        unsupported=['BAT model','arrival state power/AP calibration','temperature-to-runtime feedback',
                     'energy-based policy selection','device accuracy or absolute battery saving'],
        states_by_profile=profiles)
    (output/'arrival_energy_stress_profiles.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    plot_figures(output,rows,paths,contrasts)
    return rows,paths,contrasts,break_even


def write_csv(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def plot_figures(output, rows, paths, contrasts):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.is_file():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family']='Malgun Gothic'
    plt.rcParams['axes.unicode_minus']=False
    plt.rcParams['svg.hashsalt']='arrival-energy-stress-pc-v1'
    names={'CPU_URGENT':'CPU','FIXED_SPLIT':'분리','B2_PC':'B2','B3_SOLO_EFT_PC':'B3','P_PAIR_COST_PC':'P'}
    fig,axes=plt.subplots(2,2,figsize=(13,10))
    for ax,profile_id in zip(axes.flat,profiles_ids()):
        group=[r for r in rows if r['scenario']=='queue' and r['mode']=='explore' and r['profile']==profile_id]
        xs=[r['urgent_p95_ms'] for r in group];ys=[r['energy_j_assumed'] for r in group]
        sc=ax.scatter(xs,ys,c=[r['ap_peak_c_assumed'] for r in group],vmin=29,vmax=32,
            cmap='inferno',s=95,edgecolors='black')
        for r in group:
            ax.annotate(names[r['policy']],(r['urgent_p95_ms'],r['energy_j_assumed']),
                xytext=(5,5),textcoords='offset points',fontsize=9)
        ax.set_title(profile_id+' · AP 색');ax.set_xlabel('긴급 응답 P95 (ms, seed201 n=6)')
        ax.set_ylabel('공통 120초 기기 전체 에너지 (가정 J)');ax.grid(alpha=.2)
    fig.colorbar(sc,ax=axes.ravel().tolist(),label='AP 최고온도 (가정 °C)',shrink=.8)
    fig.suptitle('queue / explore · 24요청 seed201 · 사후 스트레스 가정, 실측 아님')
    fig.subplots_adjust(top=.91,right=.88,hspace=.32,wspace=.28)
    save_pair(fig,output,'arrival_energy_stress_tradeoff')
    fig,axes=plt.subplots(2,3,figsize=(14,7),sharex=True)
    for col,scenario in enumerate(SCENARIOS):
        group=[r for r in contrasts if r['mode']=='explore' and r['scenario']==scenario]
        for row,key,label in ((0,'p_minus_b3_energy_j_assumed','P-B3 에너지 (가정 J)'),
                              (1,'p_minus_b3_ap_peak_c_assumed','P-B3 AP 최고 (가정 °C)')):
            ax=axes[row,col]
            ax.axhline(0,color='#586675',lw=.8)
            for i,item in enumerate(group):
                ax.scatter(i,item[key],color='#376fa2' if item['profile'].startswith('P2_') else '#b7553c',s=60)
            ax.set_xticks(range(4),[r['profile'] for r in group],rotation=45,ha='right')
            ax.set_title(scenario);ax.grid(axis='y',alpha=.2)
            if col==0:ax.set_ylabel(label)
    fig.suptitle('전력·열 가정별 P-B3 쌍차 · 양수는 P 불리 · seed201만, 실측 범위 아님')
    fig.tight_layout()
    save_pair(fig,output,'arrival_energy_stress_reversal')
    fig,axes=plt.subplots(1,2,figsize=(13,4.5))
    for policy in POLICIES:
        group=[r for r in paths if r['scenario']=='queue' and r['mode']=='explore'
               and r['profile']=='P2_T30' and r['policy']==policy]
        axes[0].plot([r['time_s'] for r in group],[r['cumulative_energy_j_assumed'] for r in group],label=names[policy])
        axes[1].plot([r['time_s'] for r in group],[r['ap_c_assumed'] for r in group],label=names[policy])
    axes[0].set_ylabel('누적 기기 에너지 (가정 J)')
    axes[1].set_ylabel('AP 온도 (가정 °C)')
    for ax in axes:
        ax.set_xlabel('첫 예정 도착 후 시간 (s), 공통 0–120초')
        ax.grid(alpha=.2);ax.legend()
    fig.suptitle('사전 대표 queue / explore / seed201 · P2_T30 스트레스 가정 · 사후 회계')
    fig.tight_layout()
    save_pair(fig,output,'arrival_energy_stress_path')


def profiles_ids():
    return [f'P{p:g}_T{t:g}' for p,t in GRID]


def save_pair(fig,output,name):
    import matplotlib.pyplot as plt
    for suffix in ('png','svg'):
        fig.savefig(output/f'{name}.{suffix}',dpi=150,
                    metadata={'Date':None} if suffix=='svg' else None)
    plt.close(fig)
    svg=output/f'{name}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


if __name__=='__main__':
    build()
