"""Pairwise cost boundaries from stored arrival results; no event-model replay."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from tools import d1_energy_thermal as thermal

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / 'docs/results/arrival_diagnostic_02'
VIS = ROOT / 'docs/results/arrival_visualization_01'
SCREEN = ROOT / 'docs/results/arrival_policy_screen_01'
OUTPUT = ROOT / 'docs/results/arrival_cost_boundaries_01'
POLICIES = ('B2_PC', 'B3_SOLO_EFT_PC', 'CPU_URGENT')
PAIRS = (('B2_PC', 'B3_SOLO_EFT_PC'), ('B2_PC', 'CPU_URGENT'),
         ('B3_SOLO_EFT_PC', 'CPU_URGENT'))
FIELDS = ('arrival_ns', 'dispatch_ns', 'execution_start_ns', 'output_ready_ns',
          'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(path, rows):
    if not rows:
        raise ValueError('empty result')
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def recover_durations(energy_2w, energy_3w, horizon_s=120.):
    """Invert E=idle*1W+single*2W+pair*{2,3}W and total=120s."""
    pair = energy_3w - energy_2w
    single = energy_2w - horizon_s - pair
    idle = horizon_s - single - pair
    if min(idle, single, pair) < -1e-6 or not math.isclose(idle + single + pair, horizon_s, abs_tol=1e-6):
        raise ValueError('invalid state partition')
    return dict(idle=max(0., idle), single=max(0., single), pair=max(0., pair))


def boundary(a, b, idle_w, single_w):
    d = {key: a[key] - b[key] for key in ('idle', 'single', 'pair')}
    constant = idle_w*d['idle'] + single_w*d['single']
    if abs(d['pair']) < 1e-9:
        return None, 'identical' if abs(constant) < 1e-9 else 'no_pair_time_difference'
    return -constant/d['pair'], 'algebraic_unmeasured_power'


def build_state_rows(power):
    cells = defaultdict(dict)
    for raw in power:
        if (float(raw['idle_w_assumed']), float(raw['single_w_assumed']),
            float(raw['p_predicted'])) != (1., 2., 1.5):
            continue
        key = (raw['scenario'], int(raw['seed']), float(raw['realized']))
        pair = float(raw['pair_w_assumed'])
        if pair not in (2., 3.):
            continue
        for policy,field in (('P_PAIR_COST_PC','p_energy_j_assumed'),
                             (raw['comparator'],'comparator_energy_j_assumed')):
            value=float(raw[field]); bucket=cells[key].setdefault(policy,{})
            if pair in bucket and not math.isclose(bucket[pair],value,abs_tol=1e-8):
                raise ValueError(f'inconsistent stored energy: {key}/{policy}/{pair}')
            bucket[pair]=value
    if len(cells) != 45:
        raise ValueError('expected 45 aligned schedules')
    rows = []
    for key, group in sorted(cells.items()):
        for policy in POLICIES:
            if set(group.get(policy, {})) != {2., 3.}:
                raise ValueError(f'missing stress energies: {key}/{policy}')
            d = recover_durations(group[policy][2.], group[policy][3.])
            rows.append(dict(scenario=key[0], seed=key[1], realized=key[2], policy=policy,
                             idle_s=d['idle'], single_s=d['single'], pair_s=d['pair'],
                             horizon_s=120, evidence='PC schedule; power inversion of existing stress CSV'))
    return rows


def pair_rows(states, service):
    indexes = {(r['scenario'], int(r['seed']), float(r['realized']), r['policy']):r for r in states}
    metrics = {(r['scenario'], int(r['seed']), float(r['realized']), r['policy']):r
               for r in service if r['policy'] in POLICIES}
    rows = []
    for scenario in ('low', 'queue', 'burst'):
        for realized in (1., 1.5, 2.):
            for seed in range(201, 206):
                for first, second in PAIRS:
                    key=(scenario,seed,realized)
                    a=indexes[key+(first,)]; b=indexes[key+(second,)]
                    da={x:float(a[x+'_s']) for x in ('idle','single','pair')}
                    db={x:float(b[x+'_s']) for x in ('idle','single','pair')}
                    ma=metrics[key+(first,)]; mb=metrics[key+(second,)]
                    cross,status=boundary(da,db,1.,2.)
                    low,_=boundary(da,db,.8,1.8)
                    high,_=boundary(da,db,1.2,2.2)
                    def energy(d,pair_w):
                        return d['idle']+2*d['single']+pair_w*d['pair']
                    e2=energy(da,2.)-energy(db,2.)
                    e3=energy(da,3.)-energy(db,3.)
                    rows.append(dict(scenario=scenario,seed=seed,realized=realized,
                        first=first,second=second,planned_each=24,
                        first_unfinished=int(ma['unfinished']),second_unfinished=int(mb['unfinished']),
                        urgent_p95_delta_ms=float(ma['urgent_p95_ms'])-float(mb['urgent_p95_ms']),
                        urgent_miss_delta_count=round(float(ma['urgent_not_timely_rate'])*6)-round(float(mb['urgent_not_timely_rate'])*6),
                        normal_mean_delta_ms=float(ma['normal_mean_ms'])-float(mb['normal_mean_ms']),
                        normal_miss_delta_count=round(float(ma['normal_not_timely_rate'])*18)-round(float(mb['normal_not_timely_rate'])*18),
                        delta_idle_s=da['idle']-db['idle'],delta_single_s=da['single']-db['single'],
                        delta_pair_s=da['pair']-db['pair'],
                        energy_delta_j_pair_2w=e2,energy_delta_pct_pair_2w=100*e2/energy(db,2.),
                        energy_delta_j_pair_3w=e3,energy_delta_pct_pair_3w=100*e3/energy(db,3.),
                        pair_power_cross_w_idle1_single2=cross,
                        pair_power_cross_w_idle0p8_single1p8=low,
                        pair_power_cross_w_idle1p2_single2p2=high,
                        cross_status=status,
                        evidence='PC response + post-hoc unmeasured whole-device power; fixed schedule'))
    return rows


def representative_states(timeline):
    groups = defaultdict(list)
    for raw in timeline:
        if raw['mode'] != 'explore' or int(raw['seed']) != 201 or raw['policy'] not in POLICIES:
            continue
        row = {k:raw[k] for k in ('task','backend','priority','status')}
        row.update({k:int(raw[k]) for k in FIELDS})
        groups[raw['scenario'],raw['policy']].append(row)
    if len(groups) != 9 or any(len(v) != 24 for v in groups.values()):
        raise ValueError('seed201 representative trace coverage')
    result=[]
    for (scenario,policy),ledger in sorted(groups.items()):
        if any(r['status']!='succeeded' or r['lane_available_ns'] > 120_000_000_000 for r in ledger):
            raise ValueError('unfinished representative ledger')
        segments=thermal.ledger_segments({'ledger':ledger},120_000_000_000)
        dur=defaultdict(float)
        for s in segments:
            state=s['state']; dt=s['end_s']-s['start_s']
            if state=='idle': kind='idle'
            elif '+' not in state: kind='cpu_single' if ':CPU:' in state else 'gpu_single'
            else:
                members=state.split('+')
                paths={':'.join(v.split(':')[:2]) for v in members}
                kind=({frozenset(('classification:GPU','detection:CPU')):'pair_CG_DC',
                       frozenset(('classification:CPU','detection:GPU')):'pair_CC_DG',
                       frozenset(('detection:CPU','detection:GPU')):'pair_DCPU_DGPU',
                       frozenset(('classification:CPU','classification:GPU')):'pair_CCPU_CGPU'}
                      .get(frozenset(paths),'other_pair'))
                if all(':execute' in member for member in members): dur['both_execute_s']+=dt
            dur[kind]+=dt
            if s['waiting']: dur['any_queue_s']+=dt
            if s['waiting'] and state=='idle': dur['idle_with_queue_s']+=dt
        dur['request_wait_sum_s']=sum((r['dispatch_ns']-r['arrival_ns'])/1e9 for r in ledger)
        pair_kinds=('pair_CG_DC','pair_CC_DG','pair_DCPU_DGPU','pair_CCPU_CGPU','other_pair')
        if not math.isclose(sum(dur[k] for k in ('idle','cpu_single','gpu_single',*pair_kinds)),120.,abs_tol=1e-6):
            raise ValueError('representative time coverage')
        result.append(dict(scenario=scenario,seed=201,realized=1.5,policy=policy,
            **{k:dur[k] for k in ('idle','cpu_single','gpu_single',*pair_kinds,'both_execute_s','any_queue_s','idle_with_queue_s','request_wait_sum_s')},
            evidence='stored 24-request explore trace; stage occupancy, not GPU kernel overlap'))
    return result


def representative_ap(stress):
    cells={}
    for raw in stress:
        if raw['mode']=='explore' and int(raw['seed'])==201 and raw['policy'] in POLICIES and raw['profile'] in ('P2_T30','P2_T42'):
            cells[raw['scenario'],raw['policy'],raw['profile']] = raw
    if len(cells)!=18:
        raise ValueError('representative AP coverage')
    rows=[]
    for scenario in ('low','queue','burst'):
        for first,second in PAIRS:
            row=dict(scenario=scenario,seed=201,realized=1.5,first=first,second=second,
                     initial_ap_c_assumed=29.,tau_s_assumed=60.)
            for profile in ('P2_T30','P2_T42'):
                a=cells[scenario,first,profile]; b=cells[scenario,second,profile]
                for field in ('urgent_p95_ms','normal_mean_ms'):
                    if not math.isfinite(float(a[field])) or not math.isfinite(float(b[field])):
                        raise ValueError('invalid representative metric')
                row[f'peak_ap_delta_c_{profile}']=float(a['ap_peak_c_assumed'])-float(b['ap_peak_c_assumed'])
            row['sign_change_between_stress_endpoints']=(row['peak_ap_delta_c_P2_T30']*row['peak_ap_delta_c_P2_T42']<0)
            row['evidence']='existing seed201 post-hoc AP assumptions only; no thermal feedback'
            rows.append(row)
    return rows


def summarize(pairs):
    rows=[]
    for scenario in ('low','queue','burst'):
        for realized in (1.,1.5,2.):
            for first,second in PAIRS:
                group=[r for r in pairs if (r['scenario'],r['realized'],r['first'],r['second'])==
                       (scenario,realized,first,second)]
                if len(group)!=5 or {r['seed'] for r in group}!={201,202,203,204,205}:
                    raise ValueError('incomplete paired seed set')
                crosses=[r['pair_power_cross_w_idle1_single2'] for r in group
                         if r['pair_power_cross_w_idle1_single2'] is not None]
                rows.append(dict(scenario=scenario,realized=realized,first=first,second=second,
                    seeds=5,planned_each=120,
                    urgent_p95_delta_mean_ms=statistics.mean(r['urgent_p95_delta_ms'] for r in group),
                    normal_mean_delta_mean_ms=statistics.mean(r['normal_mean_delta_ms'] for r in group),
                    urgent_miss_delta_total=sum(r['urgent_miss_delta_count'] for r in group),
                    normal_miss_delta_total=sum(r['normal_miss_delta_count'] for r in group),
                    unfinished_first=sum(r['first_unfinished'] for r in group),
                    unfinished_second=sum(r['second_unfinished'] for r in group),
                    energy_delta_2w_min_j=min(r['energy_delta_j_pair_2w'] for r in group),
                    energy_delta_2w_max_j=max(r['energy_delta_j_pair_2w'] for r in group),
                    energy_delta_3w_min_j=min(r['energy_delta_j_pair_3w'] for r in group),
                    energy_delta_3w_max_j=max(r['energy_delta_j_pair_3w'] for r in group),
                    first_energy_lower_2w_seeds=sum(r['energy_delta_j_pair_2w'] < -1e-9 for r in group),
                    first_energy_lower_3w_seeds=sum(r['energy_delta_j_pair_3w'] < -1e-9 for r in group),
                    cross_count=len(crosses),cross_min_w=min(crosses) if crosses else None,
                    cross_max_w=max(crosses) if crosses else None,
                    evidence='fixed PC schedule; whole-device power and AP are uncalibrated stress assumptions'))
    return rows


def build(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    paths=[DIAG/'energy_boundaries.csv',DIAG/'interference_metrics.csv',
           VIS/'timeline.csv',VIS/'arrival_energy_stress.csv',SCREEN/'policy_screen.csv',
           DIAG/'CONFIG.json',
           ROOT/'docs/results/arrival_explore_20260925/freeze_before_evaluation.json',
           ROOT/'tools/d1_arrival_explore.py',ROOT/'tools/d1_energy_thermal.py']
    states=build_state_rows(read(paths[0]))
    pairs=pair_rows(states,read(paths[1]))
    reps=representative_states(read(paths[2]))
    ap=representative_ap(read(paths[3]))
    summary=summarize(pairs)
    # Cross-check independently stored seed-201 schedule against inverted all-seed accounting.
    lookup={(r['scenario'],r['seed'],r['realized'],r['policy']):r for r in states}
    for r in reps:
        s=lookup[r['scenario'],201,1.5,r['policy']]
        for key, actual in (('idle_s',r['idle']),('single_s',r['cpu_single']+r['gpu_single']),
                            ('pair_s',sum(r[k] for k in ('pair_CG_DC','pair_CC_DG','pair_DCPU_DGPU','pair_CCPU_CGPU','other_pair')))):
            if not math.isclose(float(s[key]),actual,abs_tol=1e-6):
                raise ValueError(f'stored trace/accounting mismatch: {r["scenario"]}/{r["policy"]}/{key}')
    for name,rows in [('state_durations.csv',states),('pair_boundaries.csv',pairs),
                      ('representative_states.csv',reps),('representative_ap.csv',ap),
                      ('boundary_summary.csv',summary)]:
        write(output/name,rows)
    (output/'SOURCE_HASHES.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in paths},indent=2)+'\n',encoding='utf-8')
    template=(ROOT/'tools/assets/d1_arrival_cost_boundaries.html').read_text(encoding='utf-8')
    payload=json.dumps(dict(summary=summary,states=states,representative=reps,ap=ap),
                       ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    (output/'dashboard.html').write_text(template.replace('/*__DATA__*/',f'const DATA={payload};'),encoding='utf-8')
    return states,pairs,reps,ap,summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args(); result=build(args.output)
    print('stored-state rows:',*[len(x) for x in result])
