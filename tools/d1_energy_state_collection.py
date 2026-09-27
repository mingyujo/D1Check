"""Single-use, PC-prepared A24 AP/whole-device-power state-regimen collection.

Check/prepare never issue device commands. Run is explicitly approved and delegated
to the existing observed, bounded device runner. No old plan is resumed.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import statistics
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_energy_collection as old
from tools import d1_energy_operational as operational
from tools import d1_energy_thermal as energy
from tools.d1_energy_thermal import require

PROTOCOL = 'energy-ap-state-collection-v1'
EXPERIMENT = 'ENERGY-AP-STATE-COLLECT-03'
PAIRS = ('CC_DG', 'CG_DC', 'DC_DG')
PAIR_KEYS = dict(old.PAIRS, DC_DG=('detection_CPU','detection_GPU'))
ORDER = [(phase, pair) for phase in ('development', 'confirmation')
         for pair in (PAIRS if phase == 'development' else tuple(reversed(PAIRS)))]
BLOCKS = {
    'development': [('solo_a', (0,), 90), ('idle_1', (), 30), ('solo_b', (1,), 90),
                    ('idle_2', (), 30), ('pair', (0, 1), 120), ('idle_tail', (), 120)],
    'confirmation': [('pair', (0, 1), 120), ('idle_1', (), 30), ('solo_b', (1,), 90),
                     ('idle_2', (), 30), ('solo_a', (0,), 90), ('idle_tail', (), 120)],
}
WORK_CAP = 1680
BUDGET = dict(sessions=6, development=3, confirmation=3, work_requests=10080,
              eligibility_requests=24, diagnostic_requests=10104, warmup=48,
              explicit_inference=10152, runtime_creations=24, staging=6, staged_files=42,
              apk_transfers=1, installs=1, retry=0, replacement=0, additional=0,
              fixed_observation_seconds=6120, preparation_max_wait_seconds=360,
              baseline_seconds=120, common_work_seconds=600, cooling_seconds=180,
              stage_gate_seconds=120, host_poll_seconds=1800, recovery_seconds=60,
              cleanup_seconds=45, validation_slack_seconds=35, launch_seconds=20,
              session_seconds=2100, installation_seconds=600, freeze_seconds=600,
              total_seconds=13800)
HOST_FILES = old.HOST_FILES + ['tools/d1_energy_state_collection.py']


def identity():
    return cal.code_identity() | {name: p.digest(cal.ROOT / name) for name in HOST_FILES}


def block_state(pair, block):
    keys = PAIR_KEYS[pair]
    indices = next(lanes for name, lanes, _ in BLOCKS['development'] if name == block)
    return '+'.join(sorted(keys[i] for i in indices)) if indices else 'resident_idle'


def probe_counts(pair):
    tasks=[key.rsplit('_',1)[0] for key in PAIR_KEYS[pair]]
    return {task:2*tasks.count(task) for task in ('classification','detection')}


def budget_check(b=BUDGET):
    require(b == BUDGET, 'budget changed')
    require(sum(s * len(lanes) * 4 for _, lanes, s in BLOCKS['development']) == WORK_CAP,
            'bounded cadence call cap')
    require(all(sum(s for _, _, s in blocks) == 480 for blocks in BLOCKS.values()), 'block time')
    require(b['diagnostic_requests'] == b['work_requests'] + b['eligibility_requests'] and
            b['explicit_inference'] == b['diagnostic_requests'] + b['warmup'], 'inference denominator')
    require(b['total_seconds'] == b['installation_seconds'] + b['sessions'] * b['session_seconds'] +
            b['freeze_seconds'], 'hard time')
    require(b['fixed_observation_seconds'] == b['sessions'] * (120 + 120 + 600 + 180), 'fixed time')
    require(b['session_seconds'] >= b['stage_gate_seconds'] + b['host_poll_seconds'] +
            b['recovery_seconds'] + b['cleanup_seconds'] + b['validation_slack_seconds'] +
            b['launch_seconds'], 'nested reservation')


def prepare(source, build, output):
    from tools import d1_apk_identity as apk
    source, build, output = map(Path, (source, build, output))
    require(not output.exists(), 'write-once new plan path')
    old_plan, receipt = p.read(source), p.read(build)
    require(old_plan['experiment_id'] == operational.EXPERIMENT and
            old_plan['protocol'] == old.PROTOCOL, 'source plan identity')
    require(p.digest(receipt['apk_path']) == receipt['apk_sha256'] and
            cal.apk_sources(receipt['source_code']) == cal.apk_sources(identity()), 'APK/source mismatch')
    candidate = apk.inspect(receipt['apk_path'], old_plan['apk_preflight']['toolchain'])
    require(candidate['signer_sha256'] == old_plan['apk_preflight']['candidate']['signer_sha256'],
            'project signer changed')
    template = p.read(source.parent / old_plan['entries'][0]['manifest'])
    budget_check()
    output.mkdir(parents=True); (output / 'manifests').mkdir()
    root = output.parent
    plan = dict(protocol=PROTOCOL, experiment_id=EXPERIMENT, status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
        state_model_calibration=True, experiment_ready=False, budget=BUDGET, source_code=identity(),
        build_receipt=str(build.resolve()), build_receipt_sha256=p.digest(build),
        apk_path=receipt['apk_path'], apk_sha256=receipt['apk_sha256'],
        apk_preflight=dict(old_plan['apk_preflight'], candidate=candidate),
        device_fingerprint=old_plan['device_fingerprint'], device_hardware_serial=old_plan['device_hardware_serial'],
        source_plan=dict(path=str(source.resolve()), sha256=p.digest(source)),
        output_root=str(root / 'energy_ap_state_run_v3'),
        registry=str(root / 'energy_collection_registry' / EXPERIMENT),
        battery_start_percent=20, battery_min_percent=20, battery_max_temperature_tenths_c=350,
        require_unplugged=True, screen_observation=old.OBSERVATION,
        screen_contract=old_plan['screen_contract'], temperature_preparation=operational.PREPARATION,
        operational_only=True, source_files=old_plan['source_files'], references=old_plan['references'],
        analysis=dict(current_ua_per_raw=1000, current_unit='A24 raw mA hypothesis; absolute J not certified',
            target='whole-device regimen mean W and AP first-order transitions, not per-request coefficients',
            thermal_sensor='AP mType=0 degC', power_sample_nominal_seconds=1,
            ap_sample_nominal_seconds=2, common_seconds=600, unsupported=['BAT', 'SKIN', 'battery percent',
                'arbitrary arrivals', 'sub-second direct request energy', 'GPU kernel overlap']),
        acceptance=dict(power_coverage_min=.95, power_max_gap_seconds=2.5,
            thermal_max_gap_seconds=10, thermal_min_samples_90s=20,
            joint_lane_occupancy_min_seconds=5, official_baseline_repeated=False,
            confirmation_error_pass_threshold=None, meaning='eligibility, not accuracy PASS'), entries=[])
    for index, (phase, pair) in enumerate(ORDER):
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{EXPERIMENT}/{phase}/{pair}'))
        manifest = dict(protocol=PROTOCOL, experiment_id=EXPERIMENT, session_id=sid,
            phase=phase, pair=pair, mode='calibration', state_model_calibration=True,
            calibration_version='state-regimen-v1', work_call_cap=WORK_CAP, cadence_ms=250,
            blocks=[dict(id=name, lane_indices=list(lanes), seconds=seconds)
                    for name, lanes, seconds in BLOCKS[phase]],
            models=copy.deepcopy(template['models']), images=template['images'], cpu_threads=1,
            experiment_ready=False, apk_sha256=plan['apk_sha256'],
            device_fingerprint=plan['device_fingerprint'], maximum_duration_ms=1800000,
            baseline_seconds=120, common_work_seconds=600, cooling_seconds=180,
            counts={'classification': 0, 'detection': 0},
            probe_counts=probe_counts(pair), warmup_count=8,
            operational_only=True, temperature_preparation=operational.PREPARATION,
            memory_contract='android-low-memory-resident-v1', thermal_gate=0)
        for spec in manifest['models'].values():
            spec['identity']['session_id'] = sid
            spec['target']['apk_sha256'] = plan['apk_sha256']
        file = output / 'manifests' / f'{sid}.json'; cal.write_new(file, manifest)
        plan['entries'].append(dict(index=index, phase=phase, pair=pair, mode='calibration',
            session_id=sid, manifest='manifests/' + file.name, manifest_sha256=p.digest(file)))
    file = output / 'collection_plan.json'; cal.write_new(file, plan)
    script = f'''param([ValidateSet("Check","Run")][string]$Action="Check",[switch]$Approved,[string]$Serial)
$ErrorActionPreference="Stop"
Set-Location '{cal.ROOT.as_posix()}'
$plan=Join-Path $PSScriptRoot 'collection_plan.json'
if ($Action -eq 'Check') {{ python -B -m tools.d1_energy_state_collection check --plan $plan }}
else {{
  if (!$Approved -or !$Serial) {{ throw 'Explicit new plan approval and confirmed A24 serial required' }}
  python -B -m tools.d1_energy_state_collection run --plan $plan --expected-sha {p.digest(file)} --approved --serial $Serial --adb 'C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe'
}}
if ($LASTEXITCODE -ne 0) {{ throw 'Failed; no automatic retry/resume' }}
'''
    (output / 'RUN_AFTER_APPROVAL.ps1').write_text(script, encoding='utf-8-sig')
    return check(file)


def check(file):
    from tools import d1_apk_identity as apk
    file = Path(file); plan = p.read(file); budget_check(plan['budget'])
    require(plan['protocol'] == PROTOCOL and plan['experiment_id'] == EXPERIMENT and
            plan['status'] == 'PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
            plan['state_model_calibration'] and plan['experiment_ready'] is False, 'plan status/identity')
    require(Path(plan['output_root']) == file.parent.parent/'energy_ap_state_run_v3' and
            Path(plan['registry']) == file.parent.parent/'energy_collection_registry'/EXPERIMENT,
            'output/registry namespace')
    require(p.read(plan['build_receipt'])['status'] == 'built_not_device_verified', 'build receipt status')
    require(plan['source_code'] == identity() and p.digest(plan['build_receipt']) == plan['build_receipt_sha256'],
            'source/build receipt changed')
    require(cal.apk_sources(p.read(plan['build_receipt'])['source_code']) == cal.apk_sources(identity()) and
            p.digest(plan['apk_path']) == plan['apk_sha256'], 'APK/source hash')
    for name, digest in plan['apk_preflight']['tool_sha256'].items():
        require(p.digest(plan['apk_preflight']['toolchain'][name]) == digest, 'tool changed')
    require(apk.inspect(plan['apk_path'], plan['apk_preflight']['toolchain']) ==
            plan['apk_preflight']['candidate'], 'signed APK identity')
    for entry in list(plan['source_files'].values()) + list(plan['references'].values()) + [plan['source_plan']]:
        require(p.digest(entry['path']) == entry['sha256'], 'frozen external input/reference changed')
    require(plan['temperature_preparation'] == operational.PREPARATION and
            plan['screen_observation'] == old.OBSERVATION and plan['operational_only'], 'gate contract')
    require(set(plan['references']) == set(old.KEYS) and len(plan['source_files']) == 6,
            'four references and six external staging files')
    require(len(plan['entries']) == 6 and len({e['session_id'] for e in plan['entries']}) == 6,
            'entry count/uniqueness')
    for i, entry in enumerate(plan['entries']):
        phase, pair = ORDER[i]; manifest = file.parent / entry['manifest']; m = p.read(manifest)
        require(entry['index'] == i and entry['phase'] == phase and entry['pair'] == pair and
                entry['mode'] == 'calibration' and entry['session_id'] == m['session_id'] and
                p.digest(manifest) == entry['manifest_sha256'], 'entry/manifest binding')
        require(m['protocol'] == PROTOCOL and m['experiment_id'] == EXPERIMENT and
                m['phase'] == phase and m['pair'] == pair and m['mode'] == 'calibration' and
                m['state_model_calibration'] and m['calibration_version'] == 'state-regimen-v1' and
                m['blocks'] == [dict(id=n, lane_indices=list(l), seconds=s) for n, l, s in BLOCKS[phase]] and
                m['work_call_cap'] == WORK_CAP and m['cadence_ms'] == 250 and
                m['maximum_duration_ms'] == 1800000 and m['common_work_seconds'] == 600 and
                m['baseline_seconds'] == 120 and m['cooling_seconds'] == 180 and
                m['warmup_count'] == 8 and m['probe_counts'] == probe_counts(pair) and
                m['cpu_threads'] == 1 and
                m['temperature_preparation'] == operational.PREPARATION and
                m['apk_sha256'] == plan['apk_sha256'] and m['device_fingerprint'] == plan['device_fingerprint'] and
                m['operational_only'] and not m['experiment_ready'], 'manifest semantics')
        require(set(m['models']) == set(old.KEYS) and len(m['images']) == 1, 'resident/input')
        for key, spec in m['models'].items():
            require(spec['identity']['session_id'] == m['session_id'] and
                    spec['target']['apk_sha256'] == plan['apk_sha256'] and
                    spec['runtime']['cpu_threads'] == 1 and
                    key == spec['model']['task_id'] + '_' + spec['execution']['backend'], 'model binding')
    require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),
            'consumed output/registry; never resume')
    return dict(status=plan['status'], plan_sha256=p.digest(file), budget=BUDGET, device_commands=0)


def progress_consumption(raw, launched):
    rows, partial = old.progress_prefix(raw); counts = {}
    for name, cap, phases in [('runtime', 4, None), ('warmup', 8, None),
                              ('eligibility', 4, {'eligibility_serial_probe','eligibility_parallel_probe'}),
                              ('load', WORK_CAP, {'load'})]:
        if phases is None:
            label = name; starts = [r for r in rows if r.get('kind') == label+'_start']
            ends = [r for r in rows if r.get('kind') == label+'_return']
        else:
            starts = [r for r in rows if r.get('kind') == 'request_start' and r.get('phase') in phases]
            ends = [r for r in rows if r.get('kind') == 'lane_available' and r.get('phase') in phases]
        key = lambda r: r.get('id', r.get('key'))
        started, returned = len({key(r) for r in starts} | {key(r) for r in ends}), len({key(r) for r in ends})
        require(started <= cap and returned <= cap, 'progress exceeds cap')
        counts[name] = dict(confirmed_started_at_least=started, confirmed_returned=returned,
                            actual_started_upper=cap if launched else 0,
                            missing_completion_is_not_success=True)
    return dict(records=len(rows), partial_lines=partial, counts=counts)


def _bounds(events, start_kind, end_kind, name):
    a = [r['mono_ns'] for r in events if r['kind'] == start_kind and r.get('block') == name]
    b = [r['mono_ns'] for r in events if r['kind'] == end_kind and r.get('block') == name]
    require(len(a) == len(b) == 1 and a[0] < b[0], 'block bounds ' + name)
    return a[0], b[0]


def summarize_session(folder, manifest, plan):
    folder = Path(folder); m = p.read(manifest)
    require(p.digest(folder/'manifest.json') == p.digest(manifest) and
            p.read(folder/'cleanup.json')['status'] == 'completed' and
            p.read(folder/'summary.json')['status'] == 'completed', 'app completion/identity')
    require(not any((folder/name).exists() for name in ('sampler_failure.json','session_failure.json')),
            'recorded app failure')
    events = [json.loads(x) for x in (folder/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
    require([r['sequence'] for r in events] == list(range(len(events))) and
            all(r['session_id'] == m['session_id'] for r in events) and
            all(a['mono_ns'] <= b['mono_ns'] for a,b in zip(events,events[1:])), 'journal loss/clock')
    consumed = progress_consumption((folder/'progress.jsonl').read_bytes(), True)
    require(all(consumed['counts'][k]['confirmed_returned'] == n for k,n in
                [('runtime',4),('warmup',8),('eligibility',4)]) and
            consumed['counts']['load']['confirmed_started_at_least'] ==
            consumed['counts']['load']['confirmed_returned'], 'unfinished invocation')
    require(all(r['observation_version'] == 'energy-state-snapshot-v1' and
                r['snapshot_start_ns'] <= r['sensor_read_end_ns'] <= r['state_snapshot_ns'] <= r['mono_ns']
                for r in events if r['kind'] in ('power_sample','admission')), 'snapshot coherence')
    samples = [r for r in events if r['kind'] == 'power_sample']
    require(all(r['plugged'] == 0 and r['thermal_status'] == 0 and r['interactive'] and
                r['admission_reason'] == 'admit' for r in samples), 'environment violation')
    thermal = [json.loads(x) for x in (folder.parent/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
    prep = p.read(folder.parent/'gate_probe/temperature_preparation.json')
    require(prep['assessment']['ready'] and prep['status'] == 'ready_before_one_official_baseline',
            'fixed resident preparation')
    for label, mode in operational.probe_specs(True, 'calibration'):
        probe = p.read(folder/(label+'.requests.json'))
        old.validate_rows(probe,m['pair'],mode,[1,1])
        for row in probe:old.quality(p.read(plan['references'][row['key']]['path']),
                                      p.read(folder/(row['id']+'.result.json')))
    load = [r for r in events if r['kind'] == 'lane_available' and r['phase'] == 'load']
    require(len({r['id'] for r in load}) == len(load) <= WORK_CAP and len(load) > 0,
            'work denominator/cap')
    for r in load:old.quality(p.read(plan['references'][r['key']]['path']),
                              p.read(folder/(r['id']+'.result.json')))
    starts = [r['mono_ns'] for r in events if r['kind'] == 'phase_start' and r['phase'] == 'load']
    ends = [r['mono_ns'] for r in events if r['kind'] == 'phase_end' and r['phase'] == 'post_work_wait']
    require(len(starts) == len(ends) == 1 and 599 <= (ends[0]-starts[0])/1e9 <= 601,
            'common window')
    blocks = []; pair = PAIR_KEYS[m['pair']]
    for name, lanes, target in BLOCKS[m['phase']]:
        a,b = _bounds(events,'block_start','block_end',name)
        require(starts[0] <= a < b <= ends[0] and
                target-1 <= (b-a)/1e9 <= target+15, 'block duration')
        rows = [r for r in load if r['block'] == name]
        require((not rows) == (not lanes) and
                all(r['key'] in {pair[i] for i in lanes} and a <= r['dispatch_ns'] < b and
                    r['persist_complete_ns'] <= r['worker_release_ns'] <= r['lane_available_ns'] <= b
                    for r in rows), 'block occupancy/boundary')
        for i in lanes:
            key = pair[i]; count = sum(r['key'] == key for r in rows)
            require(0 < count <= min(512,target*4), 'per-lane call cap')
        power = energy.integrate(samples,a,b,1000)
        require(power['covered_s'] >= plan['acceptance']['power_coverage_min']*power['duration_s'],
                'power coverage')
        tt = [t for t in thermal if a <= t['mono_ns'] <= b]
        ap = [float(t['AP']) for t in tt if t.get('AP') not in ('',None)]
        require(len(ap) >= (20 if target >= 90 else 6) and len(ap) >= .95*len(tt) and
                all(t['sampling_uncertainty_ns'] <= 2e9 for t in tt), 'AP coverage/clock')
        require(max([tt[0]['mono_ns']-a,b-tt[-1]['mono_ns']]+[y['mono_ns']-x['mono_ns']
                    for x,y in zip(tt,tt[1:])]) <= 10e9, 'AP gap')
        occupancy = old.state_intervals(rows,a,b)
        joint_ns = sum(x['end_ns']-x['start_ns'] for x in occupancy if x['state'] ==
                       '+'.join(sorted(pair)))
        if name == 'pair':require(joint_ns >= plan['acceptance']['joint_lane_occupancy_min_seconds']*1e9,
                                  'pair had insufficient real lane overlap')
        blocks.append(dict(name=name,state=block_state(m['pair'],name),start_ns=a,end_ns=b,
            calls=len(rows),joint_lane_occupancy_s=joint_ns/1e9, power=power,
            ap_path=[dict(mono_ns=t['mono_ns'],ap_c=float(t['AP'])) for t in tt],
            ap_start_c=ap[0], ap_end_c=ap[-1], ap_peak_c=max(ap)))
    wait_start = [r['mono_ns'] for r in events if r['kind'] == 'phase_start' and r['phase'] == 'post_work_wait']
    require(len(wait_start) == 1 and wait_start[0] >= blocks[-1]['end_ns'] and
            60 <= (ends[0]-wait_start[0])/1e9 <= 120.5, 'post-work common tail')
    wait_power = energy.integrate(samples,wait_start[0],ends[0],1000)
    require(wait_power['covered_s'] >= .95*wait_power['duration_s'], 'post-work power coverage')
    wait_ap = [dict(mono_ns=t['mono_ns'],ap_c=float(t['AP'])) for t in thermal
               if wait_start[0] <= t['mono_ns'] <= ends[0] and t.get('AP') not in ('',None)]
    require(len(wait_ap) >= 20 and max(b['mono_ns']-a['mono_ns'] for a,b in zip(wait_ap,wait_ap[1:])) <= 10e9,
            'post-work AP coverage')
    blocks.append(dict(name='post_work_wait',state='resident_idle',start_ns=wait_start[0],end_ns=ends[0],
        calls=0,joint_lane_occupancy_s=0,power=wait_power,ap_path=wait_ap,
        ap_start_c=wait_ap[0]['ap_c'],ap_end_c=wait_ap[-1]['ap_c'],
        ap_peak_c=max(x['ap_c'] for x in wait_ap)))
    common = energy.integrate(samples,starts[0],ends[0],1000)
    require(common['covered_s'] >= .95*common['duration_s'], 'common power coverage')
    return dict(status='eligible_regimen_only', condition=m['pair'], phase=m['phase'],
        independent_sessions=1, work_calls=len(load), eligibility_calls=4, warmup_calls=8,
        blocks=blocks, common_window=common, common_start_ns=starts[0],common_end_ns=ends[0],
        power_path=[{k:r[k] for k in ('mono_ns','current_raw','current_valid','voltage_mV','plugged')}
                    for r in samples if starts[0]-2_500_000_000 <= r['mono_ns'] <= ends[0]+2_500_000_000],
        start_ap_c=blocks[0]['ap_start_c'],
        actual_joint_lane_occupancy_s=sum(x['joint_lane_occupancy_s'] for x in blocks),
        sensor='AP mType=0 degC', power_unit='J conditional raw mA',
        request_energy_identified=False, thermal_accuracy_pass=None, experiment_ready=False,
        input_hashes={'manifest':p.digest(manifest),'progress':p.digest(folder/'progress.jsonl'),
                      'thermal':p.digest(folder.parent/'thermal.jsonl')})


def freeze(results, plan, root):
    import numpy as np
    require(len(results) == 3 and [r['condition'] for r in results] == list(PAIRS) and
            all(r['phase'] == 'development' and r['status'] == 'eligible_regimen_only' for r in results),
            'complete development only')
    states = sorted({b['state'] for r in results for b in r['blocks']})
    totals = {s: [0.,0.] for s in states}; rows=[]; targets=[]
    for r in results:
        for block in r['blocks']:
            s = block['state']; totals[s][0] += block['power']['covered_energy_j']
            totals[s][1] += block['power']['covered_s']
            for a,b in zip(block['ap_path'],block['ap_path'][1:]):
                dt = (b['mono_ns']-a['mono_ns'])/1e9
                if not 0 < dt <= 10:continue
                row = [float(s == k) for k in states] + [-(a['ap_c']-30.)]
                rows.append(row); targets.append((b['ap_c']-a['ap_c'])/dt)
    require(all(v[1] >= 60 for v in totals.values()), 'not enough state-regimen duration')
    x = np.asarray(rows,dtype=float); y=np.asarray(targets,dtype=float)
    coef,_,rank,singular = np.linalg.lstsq(x,y,rcond=None)
    require(rank == len(states)+1 and singular[-1]/singular[0] >= 1e-5 and
            1/1000 <= coef[-1] <= 1/10, 'AP first-order coefficient not identified')
    power = {s:totals[s][0]/totals[s][1] for s in states}
    require(all(math.isfinite(v) and v>0 for v in power.values()), 'power coefficient invalid')
    return dict(version='energy-ap-state-regimen-fit-v1',source='development_only_post_prior_results',
        plan_sha256=p.digest(Path(root).parent/'energy_ap_state_plan_v3/collection_plan.json'),
        analysis_code_sha256=p.digest(__file__), source_code=plan['source_code'],
        input_conversion=plan['analysis']['current_unit'],
        input_hashes={r['condition']:r.get('input_hashes') for r in results},
        states=states, whole_device_power_w=power, ap_slope_at_30_c_per_s={s:float(coef[i]) for i,s in enumerate(states)},
        ap_cooling_rate_per_s=float(coef[-1]), ap_reference_c=30.,
        ap_fit_rank=int(rank),ap_design_singular_ratio=float(singular[-1]/singular[0]),
        ap_development_rmse_c_per_s=float(np.sqrt(np.mean((x@coef-y)**2))),
        initial_ap_development_range_c=[min(r['start_ap_c'] for r in results),max(r['start_ap_c'] for r in results)],
        ap_development_observed_range_c=[min(q['ap_c'] for r in results for b in r['blocks'] for q in b['ap_path']),
                                         max(q['ap_c'] for r in results for b in r['blocks'] for q in b['ap_path'])],
        accuracy_pass=None, absolute_energy_accuracy_certified=False,experiment_ready=False)


def evaluate(stats, frozen, plan):
    require(stats['condition'] in PAIRS and stats['phase'] == 'confirmation' and
            frozen['version'] == 'energy-ap-state-regimen-fit-v1', 'confirmation/freeze identity')
    power = frozen['whole_device_power_w']; slope=frozen['ap_slope_at_30_c_per_s']; beta=frozen['ap_cooling_rate_per_s']
    require(all(b['state'] in power and b['state'] in slope for b in stats['blocks']), 'unsupported state')
    start_ap=stats['start_ap_c']; low, high=frozen['ap_development_observed_range_c']
    if not low <= start_ap <= high:
        return dict(status='unsupported_initial_ap_outside_development_observed_range',
                    initial_ap_c=start_ap,development_observed_range_c=[low,high],
                    accuracy_pass=None)
    cumulative=0.; t=stats['start_ap_c']; ap_errors=[]; predicted_peak=t
    predicted_path=[]; observed_path=[]
    for b in stats['blocks']:
        duration=(b['end_ns']-b['start_ns'])/1e9; s=b['state']
        cumulative += power[s]*duration
        equilibrium = 30. + slope[s]/beta
        for point in b['ap_path']:
            dt=(point['mono_ns']-b['start_ns'])/1e9
            predicted=equilibrium+(t-equilibrium)*math.exp(-beta*dt)
            ap_errors.append(predicted-point['ap_c']);predicted_peak=max(predicted_peak,predicted)
            predicted_path.append((point['mono_ns'],predicted))
            observed_path.append((point['mono_ns'],point['ap_c']))
        t=equilibrium+(t-equilibrium)*math.exp(-beta*duration)
    common=stats['common_window']['covered_energy_j']
    require(stats['common_window']['covered_s'] >= .95*stats['common_window']['duration_s'],
            'confirmation power coverage')
    start=stats['common_start_ns']; end=stats['common_end_ns'];samples=stats['power_path']
    def predicted_on_covered(a,b):
        total=0.
        ordered,_=energy.canonical_samples(samples)
        for left,right in zip(ordered,ordered[1:]):
            lo=max(a,left['mono_ns']);hi=min(b,right['mono_ns'])
            if hi<=lo or right['mono_ns']-left['mono_ns']>2_500_000_000:continue
            if energy.discharge_w(left,1000) is None or energy.discharge_w(right,1000) is None:continue
            total+=sum(power[block['state']]*max(0,min(hi,block['end_ns'])-max(lo,block['start_ns']))/1e9
                       for block in stats['blocks'])
        return total
    common_predicted_covered=predicted_on_covered(start,end)
    path_errors=[]
    for point in range(start+10_000_000_000,end+1,10_000_000_000):
        actual=energy.integrate(samples,start,point,1000)
        if actual['covered_s'] < .95*actual['duration_s']:continue
        predicted=predicted_on_covered(start,point)
        path_errors.append(predicted-actual['covered_energy_j'])
    def exceedance(path,threshold=30.):
        seconds=0.
        for (a,ta),(b,tb) in zip(path,path[1:]):
            dt=(b-a)/1e9
            if not 0 < dt <= 10:continue
            if ta>=threshold and tb>=threshold:seconds+=dt
            elif (ta-threshold)*(tb-threshold)<0:
                frac=abs((ta-threshold)/(tb-ta))
                seconds+=dt*(frac if ta>=threshold else 1-frac)
        return seconds
    predicted_peak=max(predicted_peak,t)
    return dict(common_energy_predicted_full_window_j=cumulative,
        common_energy_predicted_on_observed_coverage_j=common_predicted_covered,
        common_energy_observed_covered_j=common,
        common_energy_coverage_s=stats['common_window']['covered_s'],
        signed_energy_error_on_covered_time_j=common_predicted_covered-common,
        absolute_energy_error_on_covered_time_j=abs(common_predicted_covered-common),
        cumulative_energy_path_mae_j=statistics.mean(map(abs,path_errors)) if path_errors else None,
        cumulative_energy_path_max_absolute_error_j=max(map(abs,path_errors)) if path_errors else None,
        ap_path_mae_c=statistics.mean(map(abs,ap_errors)),
        ap_path_max_absolute_error_c=max(map(abs,ap_errors)),
        ap_peak_predicted_c=predicted_peak,
        ap_peak_observed_c=max(b['ap_peak_c'] for b in stats['blocks']),
        ap_peak_signed_error_c=predicted_peak-max(b['ap_peak_c'] for b in stats['blocks']),
        ap_research_threshold_c=30., ap_threshold_predicted_exceedance_s=exceedance(predicted_path),
        ap_threshold_observed_exceedance_s=exceedance(observed_path),
        ap_threshold_exceedance_error_s=exceedance(predicted_path)-exceedance(observed_path),
        accuracy_pass=None,meaning='one held-out regimen/session per pair; prior summary already inspected')


def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for x in ('source','build','output'):q.add_argument('--'+x,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for x in ('plan','adb','serial','expected-sha'):q.add_argument('--'+x,required=True)
    q.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare': result=prepare(args.source,args.build,args.output)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
