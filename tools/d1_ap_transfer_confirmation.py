"""One held-out CG_DC schedule transfer, PC preparation and post-run readout.

Reuses the signed APK and single-use runner. No new physics, policy or device
commands are introduced by prepare/check/readout. Run needs later approval.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_timing_calibration as cal
from tools import d1_apk_identity as apk
from tools import d1_ap_idle_response as candidate

ROOT = replay.ROOT
EXPERIMENT = 'ENERGY-AP-CGDC-TRANSFER-02'
FOLDER = 'energy_ap_cgdc_transfer_plan_v2'
RUN_FOLDER = 'energy_ap_cgdc_transfer_run_v2'
BUNDLE = ROOT/'docs/results/energy_ap_cgdc_transfer_01'
GUARD = ROOT/'docs/results/arrival_service_guard_01/readout/guard_cases.csv'
FREEZE_SHA = '8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5'
BUDGET = dict(replay.BUDGET, adb_recovery_cleanup_reserve=100)
SHIFT_NS = 35_000_000_000


def schedule():
    """Prespecified burst/201/1.5 B2, no cost/accuracy-based input selection."""
    with GUARD.open(encoding='utf-8-sig', newline='') as f:
        selected = [r for r in csv.DictReader(f) if
            (r['scenario'], r['realized'], r['seed'], r['policy']) ==
            ('burst', '1.5', '201', 'B2_PC')]
    old.require(len(selected) == 1 and selected[0]['eligible'] == 'True',
                'saved service guard does not admit this B2 input')
    with replay.TIMELINE.open(encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if
            (r['mode'], r['scenario'], r['policy'], r['seed']) ==
            ('explore', 'burst', 'B2_PC', '201')]
    old.require(len(rows) == 24 and all(r['status'] == 'succeeded' for r in rows),
                'saved complete burst ledger required')
    ledger = []
    requests = []
    for i, row in enumerate(rows):
        backend = 'GPU' if row['task'] == 'classification' else 'CPU'
        urgent = i % 4 == 1
        old.require(row['backend'] == backend and
            int(row['arrival_ns']) == (i*80+(i//6)*1000)*1_000_000 and
            row['task'] == ('classification' if urgent else 'detection') and
            row['priority'] == ('urgent' if urgent else 'normal') and
            int(row['deadline_offset_ns']) == (1500 if urgent else 6000)*1_000_000,
            'actual APK arrival/task/priority/deadline/replay contract')
        q = dict(row)
        for field in ('arrival_ns', 'dispatch_ns', 'execution_start_ns',
                      'output_ready_ns', 'persist_complete_ns',
                      'worker_release_ns', 'lane_available_ns'):
            q[field] = int(q[field])
        ledger.append(q)
        requests.append(dict(request_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
            EXPERIMENT+'/'+row['id'])), source_request_id=row['id'], ordinal=i,
            task_id=row['task'], priority=row['priority'],
            offset_ms=q['arrival_ns']//1_000_000,
            deadline_ms=int(row['deadline_offset_ns'])//1_000_000,
            recorded_backend=backend, release_offset_ns=q['dispatch_ns']+SHIFT_NS,
            **{'pc_'+field:q[field]+SHIFT_NS for field in
               ('execution_start_ns','output_ready_ns','persist_complete_ns',
                'worker_release_ns','lane_available_ns')}))
    original = replay.screen.occupancy({'ledger':ledger},'burst',1.5,201,'B2_PC')
    with replay.OCCUPANCY.open(encoding='utf-8-sig', newline='') as f:
        stored = [r for r in csv.DictReader(f) if
            (r['scenario'],r['realized'],r['seed'],r['policy']) ==
            ('burst','1.5','201','B2_PC')]
    old.require(len(original) == len(stored) and all(
        a['state'] == b['state'] and abs(a['start_s']-float(b['start_s'])) < 1e-9 and
        abs(a['end_s']-float(b['end_s'])) < 1e-9 for a,b in zip(original,stored)),
        'saved timeline and occupancy differ')
    old.require(all(q['release_offset_ns'] >= q['offset_ms']*1_000_000 and
                    q['pc_lane_available_ns'] < 120_000_000_000 for q in requests),
                'planned arrival/release escapes common window')
    shifted = [dict(start_s=0.,end_s=35.,state='idle')]
    shifted += [dict(start_s=r['start_s']+35.,end_s=min(120.,r['end_s']+35.),
                     state=r['state']) for r in original if r['start_s']+35. < 120.]
    duration = defaultdict(float)
    for r in shifted: duration[r['state']] += r['end_s']-r['start_s']
    return dict(version='cgdc-heldout-recorded-transfer-v1', scenario='burst',
        source_mode='explore', source_policy='B2_PC',seed=201,
        predicted_interference=1.5,realized_interference=1.5,
        source_timeline_sha256=p.digest(replay.TIMELINE),
        source_occupancy_sha256=p.digest(replay.OCCUPANCY),
        source_service_guard_sha256=p.digest(GUARD),
        shift_seconds=35, shift_rule='original APK arrival grid unchanged; release gates +35s; deliberate queued AP test, not service replay',
        common_window_seconds=120, requests=requests,
        pc_occupancy_seconds=dict(duration), pc_segments=shifted,
        meaning='stored future schedule replay; not online B2 nor timing/temperature enforcement')


def identity():
    return old.identity() | {str(file.relative_to(ROOT)).replace('\\','/'):p.digest(file)
        for file in (Path(__file__),Path(candidate.__file__),Path(replay.__file__),
                     ROOT/'tools/d1_arrival_recorded_replay_analysis.py',
                     BUNDLE/'schedule.json',BUNDLE/'analysis_contract.json',
                     replay.TIMELINE,replay.OCCUPANCY,GUARD)}


def manifest(source, candidate_sha):
    m = replay.expected_manifest(source,candidate_sha)
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL,EXPERIMENT+'/burst/B2_PC'))
    design = p.read(BUNDLE/'schedule.json')
    m.update(experiment_id=EXPERIMENT,session_id=sid,scenario='burst',
        phase='heldout_protocol_transfer',replay_source_sha256=p.digest(BUNDLE/'schedule.json'),
        start_ap_gate='numeric-ap-observe-v2',requests=[{k:v for k,v in r.items()
            if not k.startswith('pc_')} for r in design['requests']])
    for spec in m['models'].values():
        spec['identity']['session_id']=sid
        spec['target']['apk_sha256']=candidate_sha
    # Do not set ap_idle_response_version: its old low-temperature stratum gate
    # is not a new execution safety requirement. This transfer records any
    # otherwise admissible AP and classifies its model range separately.
    return m


def script_text():
    script = replay.script_text().replace('d1_arrival_recorded_replay','d1_ap_transfer_confirmation')
    return script.replace('python -B', "& '"+sys.executable.replace('\\','/')+"' -X utf8 -B")


def prepare(source_file, output):
    source_file,output=Path(source_file),Path(output)
    old.require(output.name == FOLDER and not output.exists(), 'fresh dedicated plan only')
    source=p.read(source_file)
    old.require(p.read(BUNDLE/'schedule.json') == schedule(), 'fixed schedule differs')
    old.require(p.digest(source['frozen_model']['path']) == replay.FROZEN_SHA, 'old freeze changed')
    freeze_file=source_file.parent.parent/'energy_ap_idle_response_run_v1/ap_model_freeze.json'
    old.require(p.digest(freeze_file) == FREEZE_SHA, 'candidate procedure freeze changed')
    plan=copy.deepcopy(source)
    plan.update(experiment_id=EXPERIMENT,status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
        approval='not_approved',experiment_ready=False,ap_transfer_confirmation=True,
        budget=copy.deepcopy(BUDGET),source_code=identity(),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        input_bundle=dict(path=str((BUNDLE/'schedule.json').resolve()),sha256=p.digest(BUNDLE/'schedule.json')),
        analysis_contract=dict(path=str((BUNDLE/'analysis_contract.json').resolve()),
                               sha256=p.digest(BUNDLE/'analysis_contract.json')),
        candidate_freeze=dict(path=str(freeze_file.resolve()),sha256=FREEZE_SHA),
        output_root=str(output.parent/RUN_FOLDER),
        registry=str(output.parent/'ap_transfer_registry'/EXPERIMENT),
        selection='prespecified burst/seed201/B2_PC/realized1.5; original arrivals, release gates +35s',
        measurement_protocol_change='same APK, sensors, runtime and host polling; shifted burst input; prospective protocol transfer, not original queue replay',
        analysis_scope='frozen W/full-window diagnostic and fixed pre-load AP procedure; no refit/strict/ranking')
    output.mkdir();(output/'manifests').mkdir()
    m=manifest(source,source['apk_sha256'])
    rel=f"manifests/{m['session_id']}.json";cal.write_new(output/rel,m)
    plan['entries']=[dict(index=0,phase=m['phase'],scenario='burst',policy=replay.POLICY,
        session_id=m['session_id'],manifest=rel,manifest_sha256=p.digest(output/rel),
        requests=24,warmup=8,runtime_creations=4)]
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    old.require(file.name=='collection_plan.json' and file.parent.name==FOLDER and
        plan['experiment_id']==EXPERIMENT and plan['status']=='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
        plan['approval']=='not_approved' and plan['ap_transfer_confirmation'] and
        plan['recorded_replay_confirmation'] and not plan['experiment_ready'] and
        not plan.get('ap_idle_pulse_followup') and plan['budget']==BUDGET and len(plan['entries'])==1,
        'transfer plan identity/budget')
    old.require(Path(plan['output_root'])==file.parent.parent/RUN_FOLDER and
        Path(plan['registry'])==file.parent.parent/'ap_transfer_registry'/EXPERIMENT and
        not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),
        'consumed or occupied output; no resume')
    old.require(plan['source_code']==identity() and p.read(BUNDLE/'schedule.json')==schedule() and
        p.digest(file.parent/'RUN_AFTER_APPROVAL.ps1')==plan['run_script_sha256'], 'source/script/input changed')
    for key in ('source_plan','input_bundle','analysis_contract','frozen_model','candidate_freeze'):
        old.require(p.digest(plan[key]['path'])==plan[key]['sha256'],key+' hash changed')
    old.require(plan['frozen_model']['sha256']==replay.FROZEN_SHA and
        plan['candidate_freeze']['sha256']==FREEZE_SHA and
        Path(plan['input_bundle']['path'])==(BUNDLE/'schedule.json').resolve() and
        Path(plan['analysis_contract']['path'])==(BUNDLE/'analysis_contract.json').resolve(),
        'registered model/input identity')
    source=p.read(plan['source_plan']['path']);build=p.read(plan['build_receipt'])
    old.require(p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
        old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
        p.digest(plan['apk_path'])==plan['apk_sha256'] and
        apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'] and
        plan['apk_preflight']['candidate']==source['apk_preflight']['candidate'], 'signed APK/source changed')
    for name,sha in plan['apk_preflight']['tool_sha256'].items():
        old.require(p.digest(plan['apk_preflight']['toolchain'][name])==sha,'inspection tool changed')
    for key in ('source_files','references','screen_contract','battery_start_percent',
                'battery_min_percent','battery_max_temperature_tenths_c','require_unplugged',
                'device_fingerprint','device_hardware_serial','apk_sha256','apk_path'):
        old.require(plan[key]==source[key],key+' execution condition changed')
    for item in [*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'staging/reference changed')
    e=plan['entries'][0];m=manifest(source,plan['apk_sha256'])
    old.require(e==dict(index=0,phase=m['phase'],scenario='burst',policy=replay.POLICY,
        session_id=m['session_id'],manifest=f"manifests/{m['session_id']}.json",
        manifest_sha256=p.digest(file.parent/e['manifest']),requests=24,warmup=8,runtime_creations=4) and
        p.read(file.parent/e['manifest'])==m,'manifest/call budget differs')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def condition(preload, segments, frozen, initial, query_s, *, baseline_s=-30.):
    """Forecast inputs exclude comparison AP/current; times are observed schedule."""
    first=min(s['start_s'] for s in segments if s['state']!='idle')
    old.require(preload and all(x['lo']<=x['t']<=x['hi']<first and
        x['lo']>=baseline_s for x in preload), 'pre-load query bracket crosses work/baseline')
    old.require(query_s and all(first<=t<=segments[-1]['end_s'] for t in query_s),
                'candidate output precedes pre-load information')
    fit=candidate.preload_reference([(x['t'],x['ap']) for x in preload],
                                   frozen['ap_cooling_rate_per_s'])
    return fit,candidate.predict(segments,frozen,initial,fit['effective_idle_reference_c'],query_s)


def readout(plan_file, output):
    """Offline, pre-load-conditioned evaluation; no new fit to post-load AP."""
    plan_file,output=Path(plan_file),Path(output)
    old.require(not output.exists(),'fresh analysis output only')
    plan=p.read(plan_file)
    old.require(plan['experiment_id']==EXPERIMENT and plan['source_code']==identity() and
        p.digest(plan['frozen_model']['path'])==replay.FROZEN_SHA and
        p.digest(plan['candidate_freeze']['path'])==FREEZE_SHA, 'registered source/freeze differs')
    e=plan['entries'][0];root=Path(plan['output_root'])
    old.require(p.read(root/'FINAL_RECEIPT.json')['status']=='completed_descriptive_only',
        'not a completed eligible session; preserve partial evidence without whole-window scores')
    return readout_session(plan_file,plan,dict(e,index=0),output)


def readout_session(plan_file,plan,e,output):
    """Shared numerical path; caller verifies its own frozen plan/procedure.

    Permits a completed eligible session in a partially stopped multi-session
    run without representing the overall run as completed.
    """
    from tools import d1_arrival_recorded_replay_analysis as a
    from tools import d1_arrival_energy_analysis as descriptive
    from tools import d1_energy_thermal as energy
    plan_file,output=Path(plan_file),Path(output)
    old.require(not output.exists(),'fresh analysis output only')
    old.require(p.digest(plan['frozen_model']['path'])==replay.FROZEN_SHA and
        p.digest(plan['candidate_freeze']['path'])==FREEZE_SHA,'registered freeze differs')
    folder=Path(plan['output_root'])/f"{e['index']:02d}_{e['session_id']}"
    old.require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only',
                'not an eligible completed session')
    artifact=folder/'artifacts';m=p.read(artifact/'manifest.json')
    old.require(p.digest(plan_file.parent/e['manifest'])==e['manifest_sha256'] and
        m==p.read(plan_file.parent/e['manifest']), 'recovered manifest differs')
    boundary=p.read(artifact/'common_boundary.json');origin=boundary['start_ns']
    old.require(boundary['planned_end_ns']-origin==120_000_000_000,'changed common window')
    rows=p.read(artifact/'requests.json')
    old.require(len(rows)==24 and all(r['terminal_status']=='succeeded' and
        r['dispatch_ns']<r['lane_available_ns']<origin+120_000_000_000 for r in rows),
        'incomplete/unfinished request denominator')
    initial=p.read(artifact/'start_ap.accepted.json')
    old.require(initial['common_start_ns']==origin and initial['gate_mode']=='numeric-ap-observe-v2',
                'initial AP boundary/mode')
    frozen=p.read(plan['frozen_model']['path']);segments=a.observed_segments(rows,origin)
    events=descriptive.read_lines(artifact/'progress.jsonl')
    baseline=[x['mono_ns'] for x in events if x.get('phase')=='resident_baseline' and x.get('kind')=='phase_start']
    cooling=[x['mono_ns'] for x in events if x.get('phase')=='resident_cooling' and x.get('kind')=='phase_end']
    old.require(len(baseline)==len(cooling)==1 and baseline[0]<origin and cooling[0]>origin+120_000_000_000,
                'missing preparation/cooling boundaries')
    extended=[*segments,dict(start_s=120.,end_s=(cooling[0]-origin)/1e9,state='idle')]
    first=min(r['dispatch_ns'] for r in rows);last=max(r['lane_available_ns'] for r in rows)
    thermal=descriptive.read_lines(folder/'thermal.jsonl')
    # Whole query brackets, not just midpoints, must lie before the first dispatch.
    pre=[dict(t=(x['mono_ns']-origin)/1e9,ap=float(x['AP']),
              lo=(x['before_ns']-origin)/1e9,hi=(x['after_ns']-origin)/1e9)
         for x in thermal if x.get('AP') not in ('',None) and x['thermal_status']=='0' and
         baseline[0]<=x['before_ns']<=x['after_ns']<first]
    targets=[((x['mono_ns']-origin)/1e9,float(x['AP'])) for x in thermal
        if first<=x['before_ns']<=x['after_ns']<=cooling[0] and
        x.get('AP') not in ('',None) and x['thermal_status']=='0']
    old.require(len(targets)>=20 and targets[0][0]-(first-origin)/1e9<=10 and
        extended[-1]['end_s']-targets[-1][0]<=10 and
        all(0<b[0]-x[0]<=10 for x,b in zip(targets,targets[1:])), 'incomplete post-load AP coverage')
    # Actual baseline duration can differ slightly from the planned -30 s.
    offset=(baseline[0]-origin)/1e9
    old.require(all(x['lo']>=offset for x in pre),'pre-load before actual resident baseline')
    times=[t for t,_ in targets]
    fit,predicted=condition(pre,extended,frozen,float(initial['ap_c']),times,baseline_s=offset)
    old_e=frozen['ap_reference_c']+frozen['ap_slope_at_30_c_per_s']['resident_idle']/frozen['ap_cooling_rate_per_s']
    original=candidate.predict(extended,frozen,float(initial['ap_c']),old_e,times)
    table=[dict(elapsed_s=t,phase='load' if origin+t*1e9<=last else 'post_load_idle',
        observed_ap_c=actual,frozen_ap_c=original[round(t,9)],candidate_ap_c=predicted[round(t,9)],
        frozen_signed_error_c=original[round(t,9)]-actual,
        candidate_signed_error_c=predicted[round(t,9)]-actual) for t,actual in targets]
    samples=[dict(x,mono_ns=(x['snapshot_start_ns']+x['sensor_read_end_ns'])//2)
             for x in events if x['kind']=='power_sample']
    observed=energy.integrate(samples,origin,origin+120_000_000_000,1000)
    old.require(observed['full_energy_j'] is not None,'incomplete power; no full-window energy error')
    path=a.forecast(segments,frozen,float(initial['ap_c']),
                   [(x['mono_ns']-origin)/1e9 for x in samples if origin<=x['mono_ns']<=origin+120_000_000_000],
                   diagnostic_extrapolation=True)
    bytime={round(x['elapsed_s'],9):x for x in path}
    energy_table=[]
    for x in samples:
        if not origin<x['mono_ns']<=origin+120_000_000_000:continue
        t=(x['mono_ns']-origin)/1e9
        actual=energy.integrate(samples,origin,x['mono_ns'],1000)['full_energy_j']
        estimate=bytime[round(t,9)]['predicted_energy_j']
        energy_table.append(dict(elapsed_s=t,observed_j=actual,predicted_j=estimate,
                                 signed_error_j=None if actual is None else estimate-actual))
    residuals=[]
    for label,start,end in (('pre_load',origin,first),('load',first,last),
                            ('post_load_idle',last,origin+120_000_000_000)):
        actual=energy.integrate(samples,start,end,1000)['full_energy_j']
        estimate=sum(max(0,min(end,origin+round(s['end_s']*1e9))-
            max(start,origin+round(s['start_s']*1e9)))/1e9*frozen['whole_device_power_w'][a.state_key(s['state'])]
            for s in segments)
        residuals.append(dict(phase=label,duration_s=(end-start)/1e9,observed_j=actual,
            predicted_j=estimate,signed_error_j=None if actual is None else estimate-actual))
    scores={}
    for model in ('frozen','candidate'):
        err=[r[model+'_signed_error_c'] for r in table]
        idle=[r for r in table if r['phase']=='post_load_idle']
        old.require(len(idle)>=10,'insufficient idle targets')
        scores[model]=dict(mae_c=sum(map(abs,err))/len(err),max_absolute_error_c=max(map(abs,err)),
            observed_idle_change_c=idle[-1]['observed_ap_c']-idle[0]['observed_ap_c'],
            predicted_idle_change_c=idle[-1][model+'_ap_c']-idle[0][model+'_ap_c'],
            diagnostic_peak_signed_error_c=max(r[model+'_ap_c'] for r in table)-max(r['observed_ap_c'] for r in table))
    pred=path[-1]['predicted_energy_j'];actual=observed['full_energy_j']
    summary=dict(status='prospective_protocol_transfer_diagnostic',strict_support=False,
        accuracy_pass=None,policy_selection_pass=None,independent_sessions=1,
        observed_energy_120s_j=actual,predicted_energy_120s_j=pred,
        signed_energy_error_j=pred-actual,absolute_energy_error_j=abs(pred-actual),
        relative_energy_error=(pred-actual)/actual,initial_ap_c=initial['ap_c'],
        initial_ap_in_development_range=frozen['initial_ap_development_range_c'][0]<=initial['ap_c']<=frozen['initial_ap_development_range_c'][1],
        preload=fit,ap_scores=scores,ap_comparison_start_s=(first-origin)/1e9,
        ap_comparison_end_s=extended[-1]['end_s'],post_load_ap_used_as_input=False,
        prediction_generation='offline conditional reconstruction after retrieval; fixed procedure, pre-load AP only',
        supported_policy_energy_j=None,supported_ap_peak_c=None,policy_rank=None,
        actual_parallel_seconds=sum(s['end_s']-s['start_s'] for s in segments if '+' in s['state']),
        planned_requests=24,completed=24,experiment_ready=False,
        plan_sha256=p.digest(plan_file),frozen_sha256=replay.FROZEN_SHA,candidate_freeze_sha256=FREEZE_SHA)
    output.mkdir(parents=True)
    cal.write_new(output/'summary.json',summary)
    for name,items in (('ap_paths.csv',table),('energy_path.csv',energy_table),
                       ('phase_energy_residuals.csv',residuals),('actual_states.csv',segments)):
        old.require(items,'missing output rows')
        with (output/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
    return summary


def main():
    cli=argparse.ArgumentParser();sub=cli.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source-plan',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('readout');q.add_argument('--plan',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('run')
    for name in ('plan','adb','serial','expected-sha'):q.add_argument('--'+name,required=True)
    q.add_argument('--approved',action='store_true')
    a=cli.parse_args()
    if a.action=='prepare':r=prepare(a.source_plan,a.output)
    elif a.action=='check':r=check(a.plan)
    elif a.action=='readout':r=readout(a.plan,a.output)
    else:
        from tools.d1_arrival_energy_collection_device import run
        r=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(r,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
