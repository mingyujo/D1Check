"""Reproducible retrospective comparison and prospective acceptance plan generation."""
import datetime as dt
from pathlib import Path
import statistics as st
import sys

from tools.d1_service_model import (CANDIDATES, load_sessions, make_split, fit, predict,
    evaluate, score_predictions, calibration_criteria, state, describe, sha, validate_bundle, metric_gate)
from tools.d1_sim_prepare import canonical
from tools.d1_task_profile import read, digest


def generate(source, output, seed):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sessions, excluded = load_sessions(source)
    by_id = {s['session_id']:s for s in sessions}
    split = make_split(sessions, seed)
    calibration = [r for sid in split['calibration'] for r in by_id[sid]['rows']]
    holdout = [r for sid in split['retrospective_holdout'] for r in by_id[sid]['rows']]
    posthoc = [r for sid in split['post_discovery'] for r in by_id[sid]['rows']]
    def save(name, value):
        (output/name).write_bytes(canonical(value))
    save('split.json', split)
    save('observations.json', dict(sessions=sessions, excluded=excluded,
                                  row_count=sum(len(s['rows']) for s in sessions),
                                  non_service_raw_sessions=[f.name for f in sorted((source/'device').iterdir())]))
    # No retrospective holdout values enter fit, criteria or candidate selection.
    criteria = calibration_criteria(calibration)
    save('acceptance_criteria.json', criteria)
    comparisons, models = {}, {}
    for candidate in CANDIDATES:
        models[candidate] = fit(calibration, candidate)
        cv_rows, cv_predictions, folds = [], [], []
        for sid in split['calibration']:
            train = [r for r in calibration if r['session_id'] != sid]
            test = by_id[sid]['rows']
            model = fit(train,candidate)
            predictions = [predict(model,r) for r in test]
            cv_rows.extend(test);cv_predictions.extend(predictions)
            folds.append(dict(test_session=sid, training_sessions=model['calibration_sessions'],
                              metrics=score_predictions(test,predictions)))
        metrics = score_predictions(cv_rows,cv_predictions)
        comparisons[candidate] = dict(calibration_loso=metrics,folds=folds,
                                     calibration_stratified=evaluate(models[candidate],cv_rows,cv_predictions),
                                     calibration_overall_numeric_gate=metric_gate(metrics,criteria),
                                     parameter_groups=len(models[candidate]['cells']))
    # Choose only using calibration CV; retrospective data are evaluated afterwards.
    admissible = [c for c in CANDIDATES if comparisons[c]['calibration_loso']['support_rate']==1.]
    if not admissible:
        raise ValueError('no fully supported calibration candidate')
    best = min(comparisons[c]['calibration_loso']['wape'] for c in admissible)
    # Prefer simpler model within measured calibration variability of the best.
    tolerance = criteria['wape_max']/2
    selected = next(c for c in admissible if comparisons[c]['calibration_loso']['wape'] <= best+tolerance)
    selected_model = models[selected]
    save('candidate_models.json',models)
    save('selection.json',dict(selected_candidate=selected,final_frozen_model=None,
                              basis='calibration leave-one-session-out only; simplest full-support candidate within calibration variability of best WAPE',
                              allowed_excess_wape=tolerance,best_calibration_wape=best,
                              calibration_overall_numeric_gate=comparisons[selected]['calibration_overall_numeric_gate'],
                              sufficient_on_independent_holdout=False))
    frozen_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    plan = dict(protocol='service-prospective-plan-v1',frozen_utc=frozen_utc,
                model_sha256=sha(selected_model),criteria=criteria,criteria_sha256=sha(criteria),
                previously_seen=split['previously_seen'],
                seen_measurements=[s['measurement_fingerprint'] for s in sessions],
                seen_requests=[r['request_id'] for s in sessions for r in s['rows']],
                apk_sha256=sessions[0]['apk_sha256'],device_fingerprint=sessions[0]['device_fingerprint'],
                split_seed=seed,selection_sha256=digest(output/'selection.json'),
                independent_holdout='not_collected; all existing sessions were previously inspected',
                scope='prospective engineering acceptance only; calibration-derived criteria cannot retroactively validate old holdout')
    save('candidate_model.json',selected_model);save('prospective_plan.json',plan)
    for candidate in CANDIDATES:
        comparisons[candidate]['retrospective_holdout'] = evaluate(models[candidate],holdout)
        comparisons[candidate]['post_discovery_diagnostic'] = evaluate(models[candidate],posthoc)
    save('model_comparison.json',dict(results=comparisons,
         interpretation='retrospective sensitivity only; no independent pass or frozen model',
         interval='empirical calibration 5th..95th percentile; descriptive nominal 90%, not confidence guarantee',
         priority='fit pools priority within cell/state; evaluation stratifies urgent/normal; both completion boundaries preserved'))
    states = {}
    for s in sessions:
        for row in s['rows']:
            k = row['cell']+'|'+state(row,selected_model['gap']['boundary_ns'])+'|'+row['pair']
            group=states.setdefault(k,dict(sessions=set(),service=[],prepare=[],response=[],inference=[]))
            group['sessions'].add(s['session_id'])
            for name in ('service','prepare','response','inference'):group[name].append(row[name+'_ns'])
    for group in states.values():
        group['sessions']=sorted(group['sessions'])
        for name in ('service','prepare','response','inference'):group[name]=describe(group[name])
    save('state_analysis.json',dict(states=states,same_backend_contention='unmeasured',
         thermal_scope=sorted(set(v for s in sessions for v in s['thermal_statuses'])),
         sampled_peak_pss_kb=max(s['peak_pss_kb'] for s in sessions),
         gap=selected_model['gap'],gap_scope='largest observed dispatch-gap separation; behavior within empty gap range unvalidated'))
    # Actual same-input matched controls, no simulated serial requests or counterfactual completions.
    co = []
    for s in sessions:
        if s['purpose']!='corun':continue
        rows=[r for r in s['rows'] if r['role']=='calibration']
        for cell in sorted(set(r['cell'] for r in rows)):
            paired=[r for r in rows if r['cell']==cell]
            matched=[r for t in sessions if t['purpose']=='solo' and len(t['rows'])==5 for r in t['rows']
                     if r['cell']==cell and r['role']=='calibration' and r['priority']==paired[0]['priority']
                     and r['sample_id']==paired[0]['sample_id']]
            co.append(dict(session_id=s['session_id'],cell=cell,priority=paired[0]['priority'],
                           solo_service=describe([r['service_ns'] for r in matched]),
                           corun_service=describe([r['service_ns'] for r in paired]),
                           solo_response=describe([r['response_ns'] for r in matched]),
                           corun_response=describe([r['response_ns'] for r in paired]),
                           slowdown=st.mean(r['service_ns'] for r in paired)/st.mean(r['service_ns'] for r in matched),
                           peak_pss_kb=s['peak_pss_kb'],thermal_statuses=s['thermal_statuses']))
    save('gpu_tradeoff.json',dict(observations=co,classification='CPU-solo-dominant; GPU not excluded',
         cpu_urgent_benefit_vs_cpu_serial='unidentified: no matched CPU-only FIFO/EDF control',
         completion_rate_benefit='unidentified: both observed paired configurations completed; no matched serial or deadline window control',
         any_condition_dominance='not_established',same_backend_contention='unmeasured',
         memory_energy='co-run sampled PSS available; no causal peak attribution or energy measurement'))
    peaks = [by_id[sid]['peak_pss_kb'] for sid in split['calibration']]
    # Use only replicated solo cells for a measured variability-based *candidate* guard.
    peak_groups={}
    for sid in split['calibration']:
        s=by_id[sid]
        if s['purpose']=='solo' and len(s['rows'])==10:
            peak_groups.setdefault(s['rows'][0]['cell'],[]).append(s['peak_pss_kb'])
    headroom=max(max(v)-min(v) for v in peak_groups.values())
    memory=dict(status='candidate_guard_pending_independent_validation',sampled_peak_pss_kb=max(peaks),
                proposed_limit_kb=max(peaks)+2*headroom,proposed_headroom_kb=2*headroom,
                rule='calibration sampled maximum plus twice largest paired solo-session PSS difference',
                missing='independent stress/holdout and available-memory admission evidence; 500ms sampling is not true peak')
    contract=dict(protocol='service-model-preparation-v1',status='SIM-01_INCOMPLETE',
         model_sha256=sha(selected_model),criteria_sha256=sha(criteria),split_sha256=sha(split),
         source_apk_sha256=sessions[0]['apk_sha256'],device_fingerprint=sessions[0]['device_fingerprint'],
         capabilities=[dict(task=task,backend=backend,numerical_equivalence='passed_on_recorded_raw_scope',
                            decoded_equivalence='20_images_passed',enabled_for_validation=True)
                       for task in ('classification','detection') for backend in ('CPU','GPU')],
         service=dict(status='candidate_not_frozen',cold='first plus early followup separate from steady',
                      transitions='observed one session per task; prepare already included; do not add twice',
                      interference='two measured cross-backend pairs; no stable independent table'),
         constraints=dict(fallback='forbidden',thermal_status_allowed=[0],memory=memory,
                          max_in_flight=1,allowed_corun=[],observed_corun_pairs=sorted(set(r['pair'] for r in calibration if r['pair']!='solo'))),
         quality=dict(backend_numerical='fixed raw tolerance 1e-4+1e-3*abs(reference)',
                      decoded='score .001, box2px, labels/order exact',task_accuracy='observed partial detection GT 15/28; no generic accuracy approval',
                      scheduling_preservation='only verified cells, identical model/input/preprocessing and decoder; no synthetic accuracy; changed contracts invalidate approval'),
         terminal_states=['succeeded','failed','rejected','expired','cancelled','unfinished'],
         deadline=dict(state='calibration_pending',values_ns=None,
                       candidate_rule='per task/priority/state use calibration service Q50,Q95 and measured response Q50,Q95 as candidate relative-deadline grid; no numeric deadline selected',
                       missing='same-arrival CPU serial and feasible mixed-backend controls plus preregistered common miss-rate/quality/service objectives; verify grid has both feasible and missed requests, not universally loose'),
         readiness_blockers=['no untouched prospective holdout','state/transition/corun repeated validation missing',
                             'prediction intervals not independently calibrated','memory admission/headroom validation pending',
                             'deadline and evaluation objectives pending'],no_scheduling_simulation=True)
    save('simulation_input.json',contract)
    names=('FIFO_CPU_only','feasible_fixed_GPU','static_task_mapping','EDF','proposed_adaptive_interface')
    save('baseline_bindings.json',dict(status='common-input interface, no dispatch implementation invoked',
         policies=[dict(policy=name,input_sha256=sha(contract),quality_and_constraints='shared',
                        legal_cells_only=True,contract_version='4.4/service-model-preparation-v1') for name in names]))
    source_files=[]
    for s in sessions:source_files.extend(s['files'])
    for name in ('FINAL_REPORT.md','capability_matrix.json','raw_comparison.json','hash_audit.json'):
        source_files.append(dict(path=str((source/name).resolve()),sha256=digest(source/name)))
    audit=read(source/'hash_audit.json')
    for item in audit.get('checks',[]):
        path=Path(item['path'])
        if not path.is_file() or digest(path)!=item['sha256']:
            raise ValueError('previously verified source/APK/model/input artifact changed')
        source_files.append(dict(path=str(path.resolve()),sha256=item['sha256']))
    save('source_manifest.json',dict(source_root=str(source.resolve()),files=source_files,
         session_ids=[s['session_id'] for s in sessions],source_catalog_sha256=sha(sessions)))
    save('generation.json',dict(command=[sys.executable,'-m','tools.d1_service_model','analyze',
         '--source',str(source.resolve()),'--output',str(output.resolve()),'--seed',str(seed)],
         working_directory=str(Path(__file__).resolve().parents[1]),
         reproduction='use a fresh output directory; model/input hashes deterministic, freeze timestamp and path provenance differ',seed=seed,
         generator_sources={str(p):digest(p) for p in [Path(__file__),Path(__file__).with_name('d1_service_model.py')]},
         original_report_sha256=digest(source/'FINAL_REPORT.md'),input_rows=len(calibration),
         retrospective_rows=len(holdout),post_discovery_rows=len(posthoc)))
    save('provenance.json',dict(protocol='service-model-provenance-v1',
         files={p.name:digest(p) for p in sorted(output.glob('*.json')) if p.name!='provenance.json'}))
    result=validate_bundle(output)
    save('no_op_result.json',result)
    save('provenance.json',dict(protocol='service-model-provenance-v1',
         files={p.name:digest(p) for p in sorted(output.glob('*.json')) if p.name!='provenance.json'}))
    validate_bundle(output)
    return result
