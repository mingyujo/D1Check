"""Opt-in archived low-temperature AP diagnosis, never a policy cost profile.

Reuses the frozen pre-load-reference procedure. Observations after first
dispatch are targets only. Peak, threshold, energy and online schedule outputs
remain unsupported even when the conditional diagnostic path is calculable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from tools import d1_ap_idle_response as candidate

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'docs/results/energy_ap_idle_response_01/low_temperature_scope_v1'
VERSION = 'ap-low-temperature-conditional-scope-v1'
MODE = 'observed_schedule_preload_diagnostic'
FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'
CANDIDATE_FREEZE_SHA = '8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5'
STATES = {'idle', 'classification:GPU', 'detection:CPU',
          'classification:GPU+detection:CPU'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                   allow_nan=False).encode()).hexdigest()


def blocked(reason):
    return dict(status='UNSUPPORTED_LOW_TEMPERATURE_OUTPUT', reason=reason,
                ap_path=None, ap_peak_c=None, threshold_exceedance_s=None,
                whole_device_energy_j=None, policy_rank=None,
                strict_support=False, accuracy_pass=None, experiment_ready=False)


def conditional_path(inputs, parameters, contract, *, output='ap_path', mode=MODE):
    """Calculate only a labelled path after pre-load information is available.

    This is an admissible diagnostic calculation, not empirical validation of
    every new sequence or a prediction made before observing the pre-load trace.
    The context is fixed to the original two sessions' APK/resident/input setup.
    """
    if mode != MODE or output != 'ap_path':
        return blocked('only actual-schedule, pre-load-conditioned AP path diagnosis')
    if (contract['version'] != VERSION or contract['evidence'] != candidate.VERSION or
            contract['frozen_sha256'] != FROZEN_SHA or
            contract['candidate_freeze_sha256'] != CANDIDATE_FREEZE_SHA or
            contract['candidate_code_sha256'] != digest(candidate.__file__) or
            content_hash(parameters) != contract['parameters_sha256']):
        return blocked('frozen procedure or parameters differ')
    if content_hash(inputs['context']) != contract['context_sha256']:
        return blocked('APK, device identity, models, input, resident or protocol differ')
    if inputs['schedule_source'] != 'observed_dispatch_to_lane_available':
        return blocked('future PC schedule is not the archived conditional input')
    if inputs['common_window_s'] != 120 or any(inputs[k] != 24 for k in
            ('planned', 'completed', 'lane_released')):
        return blocked('missing common-window or full-request denominator')
    start = inputs['initial_ap_c']
    if not math.isfinite(start) or not start < 32.5:
        return blocked('not the original low-start diagnostic stratum; not a safety gate')
    segments = inputs['segments']
    cursor = 0.
    first = None
    for segment in segments:
        a, b = segment['start_s'], segment['end_s']
        if (not all(math.isfinite(v) for v in (a, b)) or a != cursor or b <= a or
                segment['state'] not in STATES):
            return blocked('missing, overlapping or unsupported lane-state interval')
        if segment['state'] != 'idle':
            if b > inputs['common_window_s']:
                return blocked('work escapes the original common window')
            if first is None:
                first = a
        cursor = b
    if first is None or first != inputs['prediction_information_cutoff_s']:
        return blocked('first dispatch and information cutoff differ')
    preload = inputs['preload_ap']
    if any(not all(math.isfinite(p[k]) for k in ('t', 'ap', 'lo', 'hi')) or
           not inputs['resident_baseline_start_s'] <= p['lo'] <= p['t'] <= p['hi'] < first
           for p in preload):
        return blocked('pre-load query bracket crosses baseline or first dispatch')
    try:
        fit = candidate.preload_reference([(p['t'], p['ap']) for p in preload],
                                         parameters['ap_cooling_rate_per_s'])
    except ValueError as error:
        return blocked(str(error))
    times = inputs['query_s']
    if not times or any(not math.isfinite(t) or not first <= t <= cursor for t in times):
        return blocked('reported path would precede available pre-load information')
    try:
        path = candidate.predict(segments, parameters, start,
                                 fit['effective_idle_reference_c'], times)
    except ValueError as error:
        return blocked(str(error))
    return dict(blocked('not validated for peak, threshold, energy or policy ranking'),
        status='CONDITIONAL_DIAGNOSTIC_ONLY', reason='fixed procedure, actual lane schedule and pre-load AP',
        ap_path=[dict(elapsed_s=t, predicted_ap_c=path[round(t, 9)]) for t in times],
        prediction_information_cutoff_s=first, preload_fit=fit,
        actual_schedule_supplied=True, post_load_ap_used_as_input=False,
        independent_accuracy_pass=None)


def evaluate(bundle, output):
    """Reproduce only the two archived paths; no new fit structure or batch."""
    bundle, output = Path(bundle), Path(output)
    if output.exists():
        raise FileExistsError(output)
    data, contract = read(bundle/'inputs.json'), read(bundle/'contract.json')
    if digest(bundle/'inputs.json') != contract['inputs_sha256']:
        raise ValueError('shared source bundle changed')
    results, paths = [], []
    for case in data['cases']:
        result = conditional_path(case['prediction_inputs'], data['parameters'], contract)
        if result['ap_path'] is None:
            raise ValueError(case['role']+': '+result['reason'])
        if abs(result['preload_fit']['effective_idle_reference_c']-
               case['saved_reference_c']) > 1e-7:
            raise ValueError('archived pre-load reference reproduction differs')
        if len(result['ap_path']) != len(case['observed_ap_c']):
            raise ValueError('target sample denominator differs')
        errors = []
        for point, actual in zip(result['ap_path'], case['observed_ap_c']):
            error = point['predicted_ap_c']-actual
            errors.append(error)
            paths.append(dict(role=case['role'], **point, observed_ap_c=actual,
                              signed_error_c=error))
        if len(errors) != len(result['ap_path']):
            raise ValueError('target sample denominator differs')
        mae = sum(map(abs, errors))/len(errors)
        if abs(mae-case['saved_mae_c']) > 1e-7:
            raise ValueError('archived AP score reproduction differs')
        results.append(dict(role=case['role'], analysis_role='posthoc_scope_readout',
            original_data_role=case['original_data_role'],
            status=result['status'], information_cutoff_s=result['prediction_information_cutoff_s'],
            initial_ap_c=case['prediction_inputs']['initial_ap_c'], samples=len(errors),
            mae_c=mae, max_absolute_error_c=max(map(abs, errors)),
            maximum_error_is_not_a_universal_bound=True, independent_sessions=1))
    report = dict(version=VERSION, results=results, strict_support=False,
        ap_peak_c=None, threshold_exceedance_s=None, whole_device_energy_j=None,
        policy_rank=None, accuracy_pass=None, experiment_ready=False,
        frozen_sha256=FROZEN_SHA, candidate_freeze_sha256=CANDIDATE_FREEZE_SHA,
        inputs_sha256=digest(bundle/'inputs.json'), contract_sha256=digest(bundle/'contract.json'))
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    with (output/'ap_paths.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(paths[0]));writer.writeheader();writer.writerows(paths)
    with (output/'output_scope.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=('output','status','meaning'))
        writer.writeheader()
        writer.writerow(dict(output='ap_path',status='CONDITIONAL_DIAGNOSTIC_ONLY',
            meaning='actual schedule and >=55 s pre-load AP; first dispatch onward; no independent accuracy PASS'))
        for name in ('ap_peak_c','threshold_exceedance_s','whole_device_energy_j','policy_rank'):
            writer.writerow(dict(output=name,status='UNSUPPORTED',
                meaning='candidate does not identify delayed peak, threshold, power or policy distinguishability'))
    return report


def extract(external, output):
    """Read two completed source sessions into a small, identity-free PC bundle."""
    from tools.d1_arrival_recorded_replay_analysis import observed_segments
    external, output = Path(external), Path(output)
    if output.exists():
        raise FileExistsError(output)
    frozen_file=external/'energy_ap_state_run_v5/development_freeze.json'
    run=external/'energy_ap_idle_response_run_v1'
    freeze=read(run/'ap_model_freeze.json')
    if (digest(frozen_file) != FROZEN_SHA or
            digest(run/'ap_model_freeze.json') != CANDIDATE_FREEZE_SHA or
            freeze['analysis_code_sha256'] != digest(candidate.__file__) or
            read(run/'FINAL_RECEIPT.json')['status'] != 'completed_descriptive_only'):
        raise ValueError('source freeze, procedure or receipt differs')
    frozen=read(frozen_file)
    parameters={k:frozen[k] for k in ('ap_cooling_rate_per_s','ap_slope_at_30_c_per_s')}
    cases=[];context=None
    for vf in sorted(run.glob('0*/validated.json')):
        folder=vf.parent;v=read(vf);artifacts=folder/'artifacts'
        manifest=read(artifacts/'manifest.json')
        normalized=dict(device='A24',device_identity_hash=content_hash(manifest['device_fingerprint']),
            **{k:manifest[k] for k in ('apk_sha256','cpu_threads','images','protocol',
                'start_ap_gate','ap_idle_response_version','maximum_concurrency','thermal_gate')},
            models={k:{name:spec[name] for name in ('model','runtime')}
                    for k,spec in manifest['models'].items()},runtime_creations=4,warmup=8)
        if context is not None and normalized != context:
            raise ValueError('source contexts differ')
        context=normalized
        if (v['status'] != 'eligible_descriptive_only' or v['requests'] != 24 or v['warmup'] != 8 or
                v['runtimes'] != 4 or v['terminal_completed'] != 24 or v['common_unfinished'] != 0 or
                read(artifacts/'cleanup.json')['status'] != 'completed' or
                read(folder/'host_cleanup.json')['status'] != 'completed'):
            raise ValueError('source completion, denominator or cleanup differs')
        requests=read(artifacts/'requests.json')
        if len(requests)!=24 or any(r['terminal_status']!='succeeded' for r in requests):
            raise ValueError('source request denominator')
        boundary=read(artifacts/'common_boundary.json');origin=boundary['start_ns']
        if boundary['planned_end_ns']-origin != 120_000_000_000:
            raise ValueError('source common window')
        first=min(r['dispatch_ns'] for r in requests)
        baseline=v['preload_ap']['baseline_start_ns']
        thermal=[json.loads(s) for s in (folder/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
        preload=[dict(t=(s['mono_ns']-origin)/1e9,ap=float(s['AP']),
            lo=(s['before_ns']-origin)/1e9,hi=(s['after_ns']-origin)/1e9)
            for s in thermal if baseline<=s['mono_ns']<first and s.get('AP') not in ('',None)
            and s.get('thermal_status')=='0']
        summary=read(folder/'ap_analysis/summary.json')
        with (folder/'ap_analysis/ap_path.csv').open(encoding='utf-8',newline='') as stream:
            saved=list(csv.DictReader(stream))
        segments=observed_segments(requests,origin)
        segments.append(dict(start_s=120.,end_s=summary['cooling_end_s'],state='idle'))
        inputs=dict(context=context,schedule_source='observed_dispatch_to_lane_available',
            common_window_s=120,planned=24,completed=24,lane_released=24,
            initial_ap_c=summary['initial_ap_c'],resident_baseline_start_s=(baseline-origin)/1e9,
            prediction_information_cutoff_s=(first-origin)/1e9,preload_ap=preload,segments=segments,
            query_s=[float(r['elapsed_s']) for r in saved])
        provenance={name:digest(folder/name) for name in ('validated.json','thermal.jsonl',
            'artifacts/requests.json','artifacts/manifest.json','ap_analysis/ap_path.csv')}
        cases.append(dict(role=summary['role'],original_data_role=summary['data_role'],
            prediction_inputs=inputs,observed_ap_c=[float(r['observed_ap_c']) for r in saved],
            saved_reference_c=summary['preload_effective_reference_c'],
            saved_mae_c=summary['ap_path_mae_c'],source_sha256=provenance))
    if [c['role'] for c in cases] != ['development','confirmation']:
        raise ValueError('not the two original sessions')
    output.mkdir(parents=True)
    def write(name,value):
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write('inputs.json',dict(version=VERSION,parameters=parameters,cases=cases))
    write('contract.json',dict(version=VERSION,evidence=candidate.VERSION,
        frozen_sha256=FROZEN_SHA,candidate_freeze_sha256=CANDIDATE_FREEZE_SHA,
        candidate_code_sha256=freeze['analysis_code_sha256'],parameters_sha256=content_hash(parameters),
        context_sha256=content_hash(context),inputs_sha256=digest(output/'inputs.json'),
        allowed_calculation=MODE,empirical_generalization=False,
        forbidden_outputs=['ap_peak_c','threshold_exceedance_s','whole_device_energy_j','policy_rank'],
        observed_initial_ap_c=[c['prediction_inputs']['initial_ap_c'] for c in cases],
        observation_range_is_not_new_support_range=True,accuracy_pass=None,experiment_ready=False))
    return dict(cases=len(cases),device_commands=0,inputs_sha256=digest(output/'inputs.json'))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract-external',type=Path)
    parser.add_argument('--bundle',type=Path,default=BUNDLE)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=extract(args.extract_external,args.output) if args.extract_external else evaluate(args.bundle,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))
