"""Separate A24/S26 measured anchors and explicitly hypothetical dynamics.

No fitting, device execution or default-policy replacement happens here.
"""
from __future__ import annotations
import copy
import csv
import hashlib
import json
import math
from pathlib import Path

ABI = 'd1-sched-dynamics-profile-v1'
PRIMARY = ('neutral', 'mild', 'full')
ABLATIONS = ('thermal_only', 'parallel_only', 'activation_only')
ROOT = Path(__file__).resolve().parents[1]
A24_MODEL = ROOT/'docs/results/online_policy_study_01/overnight_sustained_run01/model.json'
A24_RAW = ROOT/'docs/results/overnight_device_20261011/requests.csv'
A24_RAW_SHA = '08421e953cd3ee606ff1d9e6cbc53e649a86a62548791a1494b3279e9953bce9'
PHASES = ('dispatch_to_execution_start', 'execution_start_to_output_ready',
          'output_ready_to_persist_complete', 'persist_complete_to_worker_release',
          'worker_release_to_lane_available')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def normalize_service(device, source):
    """Keep immutable five-phase vectors; policies only call estimate()."""
    if device == 'S26':
        service = source.get('service', source)
        if service.get('schema') != 's26-short-npu-service-v1' or tuple(service['phases']) != PHASES:
            raise ValueError('S26 measured service ABI')
        return copy.deepcopy(service)
    if device != 'A24': raise ValueError('separate supported device required')
    if sha(A24_RAW) != A24_RAW_SHA: raise ValueError('A24 raw anchor identity changed')
    pools = {f'{task}|{b}': [] for task,b in [('classification','CPU'),('classification','GPU'),('detection','CPU')]}
    with A24_RAW.open(encoding='utf-8-sig', newline='') as handle:
        for i,row in enumerate(csv.DictReader(handle)):
            if row['terminal_status'] != 'succeeded': raise ValueError('A24 intact raw denominator')
            ts = [float(row[k])*1e6 for k in ('dispatch_ms','execution_start_ms','output_ready_ms','persist_complete_ms','worker_release_ms','lane_available_ms')]
            ds = [round(y-x) for x,y in zip(ts,ts[1:])]
            key=f"{row['task_id']}|{row['backend']}"
            if key not in pools or min(ds)<0: raise ValueError('unsupported A24 vector')
            pools[key].append(dict(source_request_id=f'ABBA{row["index"]}/row{i}',durations_ns=ds))
    if [len(v) for v in pools.values()] != [4,188,192]: raise ValueError('A24 384 raw roster')
    means = {}
    frozen_service=source.get('service',source)
    for key in pools:
        task,b = key.split('|'); priority = 'urgent' if task=='classification' else 'normal'
        rows = [v['phase_means_ns'][f'{task}_{b}_{priority}'] for v in frozen_service.values() if f'{task}_{b}_{priority}' in v['phase_means_ns']]
        if not rows: raise ValueError('A24 measured mean unavailable')
        means[key] = [sum(col)/len(col) for col in zip(*rows)]
    return dict(schema='a24-dynamics-service-anchor-v1', phases=list(PHASES), means=means,
                pools={s:copy.deepcopy(pools) for s in ('train','dev','confirm')},
                split_note='existing 384 vectors reused; fresh arrival split is not new hardware confirmation',
                sources={str(A24_RAW):A24_RAW_SHA}, priority_transfer='same task/backend work across public priority labels; hypothesis')

def profiles(device, source=None):
    """Return registered grid, never select a profile from evaluation results."""
    if source is None:
        if device != 'A24': raise ValueError('explicit frozen S26 source required')
        source = read(A24_MODEL)
    if isinstance(source,(str,Path)): source=read(source)
    service=normalize_service(device,source)
    if device == 'S26':
        if source.get('schema') != 's26-pair-observer-separated-heat-v2' or source['cost']['mode']!='START0':
            raise ValueError('explicit S26 START0 separated-heat anchor required')
        cost = copy.deepcopy(source['cost']); provenance = copy.deepcopy(source.get('provenance',{}))
    else:
        cost=copy.deepcopy({k:source[k] for k in ('ap','energy_increment_w')})
        provenance=dict(model_path=str(A24_MODEL), model_sha=sha(A24_MODEL), raw_path=str(A24_RAW), raw_sha=sha(A24_RAW))
    out={}
    for name in (*PRIMARY,*ABLATIONS):
        strength = 0. if name=='neutral' else .5 if name=='mild' else 1.
        thermal = name in ('mild','full','thermal_only')
        parallel = name in ('mild','full','parallel_only')
        activation = name in ('mild','full','activation_only')
        out[name] = dict(abi=ABI, name=name, device=device, evidence='hypothesis_only', hardware_validated=False,
            strict_eligible=False, experiment_ready=False, horizon_s=120., max_concurrent=2,
            service_anchor=copy.deepcopy(service), cost_anchor=copy.deepcopy(cost), provenance=provenance,
            reference_note='reference AP is a model boundary, not measured ambient air',
            observation_note='synthetic last-completed temperature2s and power0.9s observations; no device cache/noise calibration; A24 SKIN is a fixed boundary placeholder',
            thermal_observation_period_ns=2_000_000_000,power_observation_period_ns=900_000_000,
            work_units_note='public units1..3 multiply execution interval only; fixed callbacks; assumed declared work',
            step_s=.05, recent_tau_s=5., activation_tau_s=1.5,
            thermal_threshold_offset_c=4. if device=='A24' else 5.,
            thermal_slowdown_per_c={b:strength*v if thermal else 0. for b,v in zip(('CPU','GPU','NPU'),(.08,.06,.04))},
            recent_slowdown={b:strength*v if thermal else 0. for b,v in zip(('CPU','GPU','NPU'),(.12,.08,.06))},
            max_slowdown=2.,
            parallel_extra_slowdown={b:strength*v if parallel else 0. for b,v in zip(('CPU','GPU','NPU'),(.15,.12,.10))},
            parallel_extra_w=strength*(.15 if device=='A24' else .30) if parallel else 0.,
            startup_s={b:strength*v if activation else 0. for b,v in zip(('CPU','GPU','NPU'),(.001,.004,.006))},
            startup_j={b:strength*v if activation else 0. for b,v in zip(('CPU','GPU','NPU'),(.002,.010,.015))},
            idle_tail_w={b:strength*v if activation else 0. for b,v in zip(('CPU','GPU','NPU'),(.02,.05,.06))},
            switch_s=strength*.002 if activation else 0., switch_j=strength*.005 if activation else 0.,
            extra_heat_gain_c_per_w=.8, extra_heat_beta_per_s=.05,
            assumption_note='all new dynamics are sensitivity hypotheses above the measured anchor, including extra parallel cost; not fitted device behavior')
    for p in out.values(): validate(p)
    return out

def validate(p):
    if p.get('abi')!=ABI or p.get('device') not in ('A24','S26') or p.get('evidence')!='hypothesis_only' or p.get('hardware_validated') is not False:
        raise ValueError('research dynamics ABI/evidence')
    if any(p.get(k) is not False for k in ('strict_eligible','experiment_ready')) or p['max_concurrent']!=2 or p['horizon_s']!=120.:
        raise ValueError('unchanged scope')
    for k in ('step_s','recent_tau_s','activation_tau_s','thermal_threshold_offset_c','max_slowdown','extra_heat_beta_per_s'):
        if not math.isfinite(p[k]) or p[k]<=0: raise ValueError('finite positive dynamics')
    if p['step_s'] not in (.025,.05): raise ValueError('registered integration step')
    for k in ('thermal_slowdown_per_c','recent_slowdown','parallel_extra_slowdown','startup_s','startup_j','idle_tail_w'):
        if set(p[k])!={'CPU','GPU','NPU'} or any(not math.isfinite(v) or v<0 for v in p[k].values()): raise ValueError('nonnegative backend parameter')
    for k in ('parallel_extra_w','switch_s','switch_j','extra_heat_gain_c_per_w'):
        if not math.isfinite(p[k]) or p[k]<0: raise ValueError('nonnegative dynamics')
    return p
