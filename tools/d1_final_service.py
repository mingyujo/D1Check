"""Pre-holdout service model freeze and read-only independent validation."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import statistics as st
import subprocess
import tempfile

from tools import d1_service_model as sm
from tools.d1_task_profile import read, digest
from tools.d1_final_calib import save_new, check_entry


def selected_sessions(root, entries):
    """Use strict legacy validation; retain original paths in the evidence closure."""
    result = []
    for entry in entries:
        original = Path(root)/entry['phase']/'profiles'/entry['session_id']
        context = read(original/'context.json')
        if context['recipe'] != entry['recipe'] or context['phase'] != entry['phase']:
            raise ValueError('measured workload differs from preregistration')
        with tempfile.TemporaryDirectory(prefix='d1-final-read-') as name:
            catalog = Path(name)
            target = catalog/'profiles'/entry['session_id']
            shutil.copytree(original, target)
            sessions, excluded = sm.load_sessions(catalog)
            if excluded or len(sessions) != 1:
                raise ValueError('missing session')
            session = sessions[0]
            for item in session['files']:
                item['path'] = str(original/Path(item['path']).relative_to(target))
            result.append(session)
    return result


def select_model(sessions, criteria):
    rows = [r for s in sessions for r in s['rows']]
    comparisons = {}
    models = {}
    for candidate in sm.CANDIDATES:
        models[candidate] = sm.fit(rows, candidate)
        predictions, validation_rows = [], []
        for session in sessions:
            train = [r for r in rows if r['session_id'] != session['session_id']]
            fitted = sm.fit(train, candidate)
            validation_rows.extend(session['rows'])
            predictions.extend(sm.predict(fitted, r) for r in session['rows'])
        evaluation = sm.evaluate(models[candidate], validation_rows, predictions)
        comparisons[candidate] = evaluation
    # First three candidates collapse required cold/early/transition distinctions.
    eligible = list(sm.CANDIDATES[3:])
    # Never trade missing support for lower WAPE. Complexity ordering is fixed.
    support = max(comparisons[c]['overall']['support_rate'] for c in eligible)
    supported = [c for c in eligible if comparisons[c]['overall']['support_rate'] == support]
    best = min(comparisons[c]['overall']['wape'] for c in supported)
    selected = next(c for c in supported if comparisons[c]['overall']['wape'] <= best + criteria['wape_max']/2)
    return models[selected], dict(selected=selected, candidates=comparisons,
                                 selection_scope='calibration LOSO only; required state separation, maximal support, simplest within original calibration variability',
                                 final_approval=False)


def freeze(root):
    root = Path(root)
    plan = read(root/'measurement_plan_v2.json')
    for e in plan['sessions']:
        check_entry(plan, e)
    if any((root/'B'/'profiles'/e['session_id']).exists() for e in plan['sessions'] if e['phase']=='B'):
        raise ValueError('cannot freeze after holdout starts')
    bundle = Path(read(root/'installed.json')['source_bundle'])
    sm.validate_bundle(bundle)
    observed = read(bundle/'observations.json')['sessions']
    old_ids = read(bundle/'split.json')['calibration']
    previous = [s for s in observed if s['session_id'] in old_ids]
    additions = selected_sessions(root, [e for e in plan['sessions'] if e['phase']=='A'])
    if len(previous)!=24 or len(additions)!=4:
        raise ValueError('expected 24 old and 4 new calibration sessions')
    criteria = read(bundle/'acceptance_criteria.json')
    # Preserve published thresholds and interval rule, without retrospective relaxation.
    model, comparison = select_model(previous+additions, criteria)
    contract = copy.deepcopy(read(bundle/'simulation_input.json'))
    contract['protocol']='service-final-candidate-v1'
    contract['model_sha256']=sm.sha(model)
    contract['measurement_plan_sha256']=sm.sha(plan)
    contract['memory_blocker']='sampled PSS and host MemAvailable cannot establish independent peak/admission guarantee; no approved memory constraint'
    contract['constraints']['memory']['calibration_peak_pss_kb']=max(s['peak_pss_kb'] for s in previous+additions)
    contract['constraints']['memory']['rule_frozen']='retain previous proposed guard/headroom; exceeding it fails, never raise after holdout'
    allseen = observed+additions
    envelope = dict(protocol='service-final-freeze-v1', frozen_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    status='frozen_for_independent_evaluation_not_approved', model=model,
                    model_sha256=sm.sha(model), criteria=criteria, criteria_sha256=sm.sha(criteria),
                    simulation_input=contract, simulation_input_sha256=sm.sha(contract),
                    plan=plan, plan_sha256=sm.sha(plan), calibration_sessions=model['calibration_sessions'],
                    old_excluded_from_fit=read(bundle/'split.json')['retrospective_holdout']+read(bundle/'split.json')['post_discovery'],
                    previously_seen=[s['session_id'] for s in allseen]+[e['session_id'] for e in plan.get('superseded_attempts',[])],
                    seen_measurements=[s['measurement_fingerprint'] for s in allseen],
                    seen_requests=[r['request_id'] for s in allseen for r in s['rows']],
                    apk_sha256=allseen[0]['apk_sha256'],device_fingerprint=allseen[0]['device_fingerprint'],
                    state_definition='per-worker first=cold_first; changed task/backend=transition_FROM_to_TO; ordinal2 with dispatch gap<=frozen boundary=initial_followup; remaining=warm_steady; pair records co-run context',
                    interval_method='original empirical nearest-rank calibration Q05..Q95; no post-holdout expansion',
                    source_files=[item for s in previous+additions for item in s['files']],
                    generator_sources={str(Path(n).resolve()):digest(Path(n)) for n in
                        ['tools/d1_service_model.py','tools/d1_final_service.py','tools/d1_final_calib.py','tools/d1_task_profile.py','tools/schemas/service-final-freeze-v1.schema.json']},
                    runner_sha256=digest(root/'profile_device.py'),
                    baselines=['FIFO_CPU_only','feasible_fixed_GPU','static_task_mapping','EDF','proposed_adaptive_interface'],
                    no_scheduling_simulation=True)
    save_new(root/'calibration_comparison.json', comparison)
    save_new(root/'calibration_sessions.json',previous+additions)
    save_new(root/'frozen_contract.json',envelope)
    return dict(frozen_contract_path=str((root/'frozen_contract.json').resolve()),
                frozen_contract_sha256=digest(root/'frozen_contract.json'),
                frozen_utc=envelope['frozen_utc'],model_sha256=envelope['model_sha256'],
                simulation_input_sha256=envelope['simulation_input_sha256'])


def validate_frozen(root, expected):
    root=Path(root)
    if digest(root/'frozen_contract.json') != expected:
        raise ValueError('frozen contract mutated')
    f=read(root/'frozen_contract.json')
    import jsonschema
    jsonschema.validate(f,read(Path('tools/schemas/service-final-freeze-v1.schema.json')))
    for name in ('model','criteria','simulation_input','plan'):
        if sm.sha(f[name]) != f[name+'_sha256']:
            raise ValueError('frozen component binding drift')
    validate_partition(f)
    if sm.sha(read(root/'measurement_plan_v2.json')) != f['plan_sha256']:
        raise ValueError('live measurement plan drift')
    if f['calibration_sessions'] != f['model']['calibration_sessions']:
        raise ValueError('calibration identity drift')
    if digest(root/'profile_device.py') != f['runner_sha256']:
        raise ValueError('runner changed since freeze')
    for name,h in f['generator_sources'].items():
        if digest(Path(name))!=h:
            raise ValueError('stale generator source')
    for item in f['source_files']:
        if digest(Path(item['path']))!=item['sha256']:
            raise ValueError('stale calibration evidence')
    if f['criteria']['required_empirical_coverage']!=.9 or not f['no_scheduling_simulation']:
        raise ValueError('acceptance/scope drift')
    return f


def validate_partition(f):
    plan = f['plan']
    entries=plan['sessions']
    if len({e['session_id'] for e in entries}) != len(entries):
        raise ValueError('session replay in plan')
    if [sum(e['phase']==p for e in entries) for p in 'ABC'] != [4,16,2]:
        raise ValueError('phase count drift')
    calibration=set(f['calibration_sessions'])
    holdout={e['session_id'] for e in entries if e['phase']=='B'}
    if calibration & holdout or holdout & set(f['previously_seen']):
        raise ValueError('calibration/holdout leakage')
    if not {e['session_id'] for e in entries if e['phase']=='A'} <= calibration:
        raise ValueError('new calibration omitted')
    for cell in f['model']['cells'].values():
        if not set(cell['blocks']) <= calibration:
            raise ValueError('model fitted on holdout')
    for entry in entries:check_entry(plan,entry)
    return True


def evaluate_sessions(f, sessions):
    sm.check_prospective(f,f['model'],sessions)
    ids=[e['session_id'] for e in f['plan']['sessions'] if e['phase']=='B']
    if set(ids)!=set(s['session_id'] for s in sessions) or len(sessions)!=16:
        raise ValueError('not the exact 16 preregistered holdout sessions')
    rows=[r for s in sessions for r in s['rows']]
    result=sm.evaluate(f['model'],rows)
    criteria=f['criteria']
    gates=dict(overall=sm.metric_gate(result['overall'],criteria),
               every_session=all(sm.metric_gate(x['metrics'],criteria) for x in result['sessions']),
               every_stratum=all(sm.metric_gate(m,criteria) for m in result['strata'].values()),
               distributions=all(all(v<=criteria['distribution_relative_error_max'] for v in x['relative_error'].values()) for x in result['distribution_metrics']),
               thermal_scope=all(s['thermal_statuses']==[0] for s in sessions),
               calibration_repetition=all(c['session_count']>=2 for c in f['model']['cells'].values()),
               holdout_repetition=all(len({r['session_id'] for r in rows if r['cell']==cell})>=2 for cell in {r['cell'] for r in rows}),
               warm_count=all(sum(r['cell']==cell and sm.state(r,f['model']['gap']['boundary_ns'])=='warm_steady' for r in rows)>=20 for cell in {r['cell'] for r in rows}),
               candidate_memory_guard=all(s['peak_pss_kb']<=f['simulation_input']['constraints']['memory']['proposed_limit_kb'] for s in sessions),
               memory_constraint_approved=False,
               deadline_frozen=False)
    result.update(gates=gates,status='SIM-01_READY' if all(gates.values()) else 'SIM-01_INCOMPLETE',
                  session_count=len(sessions),request_count=len(rows),
                  session_weighted=dict(mean_session_wape=st.mean(x['metrics']['wape'] for x in result['sessions']),
                                        mean_session_coverage=st.mean(x['metrics']['coverage'] for x in result['sessions'])),
                  independence_note='16 sessions are the experimental units; request counts are not independent replications')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['freeze','validate','evaluate','no-op']);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--expected-sha256');a=p.parse_args()
    if a.command=='freeze':result=freeze(a.root)
    else:
        f=validate_frozen(a.root,a.expected_sha256)
        result=dict(status='frozen_for_independent_evaluation_not_approved',model_sha256=f['model_sha256'],simulation_input_sha256=f['simulation_input_sha256'],dispatch_count=0,simulated_completion_count=0,comparative_results=None)
        if a.command=='evaluate':
            sessions=selected_sessions(a.root,[e for e in f['plan']['sessions'] if e['phase']=='B'])
            result=evaluate_sessions(f,sessions)
            save_new(a.root/'holdout_evaluation.json',result)
            save_new(a.root/'holdout_sessions.json',sessions)
        elif a.command=='no-op':save_new(a.root/'no_op_result.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
