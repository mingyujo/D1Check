"""Host-only V2 development analysis. No device runner or scheduling simulator."""
import argparse
import datetime as dt
import math
from pathlib import Path
import statistics as st

from tools import d1_service_model as old
from tools.d1_task_profile import read, digest
from tools.d1_sim_prepare import canonical

PROTOCOL = 'service-model-v2-design-v1'
STATUS = 'BLOCKED_MISSING_TELEMETRY'
SEED = 20260921
APK = '8b805d3acfcede25fe6e4bcd17075d172c5ef66b425ff40ff29e2317ffce2489'
FINAL_SHA = 'ca678f65b3ddd7d1e96aaf21e4ffdd39fcdcfaeb80f838404cf788458b30ee1e'
MODELS = ('A_cell_mean', 'B_origin_state', 'C_setup_service', 'D_sequence_setup',
          'E_joint_empirical', 'G_pooled_multiplier')
PAIR_FIELDS = ('runtime_precreated', 'resident_tasks', 'warmup_per_runtime', 'arrivals',
               'task_mix', 'seed', 'request_count', 'thermal_range', 'background',
               'output_validation', 'artifact_collection', 'deadline', 'cold_definition')


def save(path, value):
    with Path(path).open('xb') as f:
        f.write(canonical(value))


def boundary(service, setup, inference):
    if any(type(v) is not int or v < 0 for v in (service, setup, inference)):
        raise ValueError('invalid timing')
    if setup + inference > service:
        raise ValueError('setup/service boundary overlap')
    return dict(setup_ns=setup, active_service_ns=service-setup,
                inference_ns=inference, other_active_ns=service-setup-inference)


def validate_spans(spans):
    """Minimum proposed v4 span validator, independent of Android implementation."""
    by_id={s['span_id']:s for s in spans}
    if len(by_id)!=len(spans):raise ValueError('replayed span')
    for s in spans:
        if any(type(s[k]) is not int or s[k]<0 for k in ('start_ns','end_ns')) or s['end_ns']<s['start_ns']:
            raise ValueError('invalid span boundary')
        parent=s.get('parent_id')
        ancestors={s['span_id']}
        while parent is not None:
            if parent in ancestors or parent not in by_id:raise ValueError('span parent cycle/missing')
            ancestors.add(parent);p=by_id[parent]
            if (p['session_id']!=s['session_id'] or p['runtime_id']!=s['runtime_id'] or
                    not p['start_ns']<=s['start_ns']<=s['end_ns']<=p['end_ns']):
                raise ValueError('span outside parent')
            parent=p.get('parent_id')
    exclusive={}
    for s in spans:
        if s.get('exclusive',False):
            exclusive.setdefault((s['session_id'],s['runtime_id'],s.get('parent_id')),[]).append(s)
    for group in exclusive.values():
        ordered=sorted(group,key=lambda s:s['start_ns'])
        if any(a['end_ns']>b['start_ns'] for a,b in zip(ordered,ordered[1:])):
            raise ValueError('exclusive spans overlap')
    return True


def paired_order(blocks, seed):
    if type(blocks) is not int or blocks<2 or blocks%2:
        raise ValueError('balanced paired blocks must be positive and even')
    return dict(zip(old.ordered([str(i) for i in range(blocks)],seed),['AB','BA']*(blocks//2)))


def trace_rows(session):
    event_path = next(Path(f['path']) for f in session['files'] if Path(f['path']).name == 'events.jsonl')
    events = [__import__('json').loads(line) for line in event_path.read_text().splitlines() if line]
    originals = {r['request_id']: r for r in session['rows']}
    previous = {}
    rows = []
    for e in sorted(events, key=lambda x: (x['execution_start_ns'], x['request_id'])):
        r = dict(originals[e['request_id']])
        w = e['worker']; p = previous.get(w)
        changed = p is None or p['cell'] != r['cell']
        r.update(worker=w, episode=(0 if p is None else p['episode']+int(changed)),
                 origin=('process_first' if p is None else 'recreated') if changed else p['origin'],
                 source_cell=('NONE' if p is None else p['cell']) if changed else p['source_cell'],
                 invocation=1 if changed else p['invocation']+1,
                 requested_backend=e['requested_backend'], actual_backend_evidence=e['actual_backend'],
                 execution_start_ns=e['execution_start_ns'], completion_ns=e['completion_ns'])
        r.update(boundary(e['service_ns'], e['prepare_ns'], e['inference_ns']))
        r['phase'] = phase(r['origin'], r['invocation'])
        # Request priority selects a different completion boundary; never pool silently.
        r['context'] = r['pair']+'|'+r['priority']
        rows.append(r); previous[w] = r
    return rows


def phase(origin, invocation):
    if origin not in ('process_first', 'recreated') or type(invocation) is not int or invocation < 1:
        raise ValueError('unknown runtime history')
    return origin+'_'+('first' if invocation == 1 else 'early' if invocation == 2 else 'warm_candidate')


def finite_interval(scores, alpha=.1):
    """Scores must be one maximum normalized residual per independent session."""
    if not 0 < alpha < 1 or any(not math.isfinite(s) or s < 0 for s in scores):
        raise ValueError('invalid conformal score')
    rank = math.ceil((len(scores)+1)*(1-alpha)-1e-12)
    return dict(n_sessions=len(scores), rank=rank,
                radius=sorted(scores)[rank-1] if 0 < rank <= len(scores) else None,
                finite=0 < rank <= len(scores))


def partition(development, calibration, holdout, consumed):
    groups = [list(x) for x in (development, calibration, holdout)]
    flat = sum(groups, [])
    if len(flat) != len(set(flat)):
        raise ValueError('session leakage/replay')
    if set(calibration+holdout) & set(consumed):
        raise ValueError('consumed holdout/development cannot be fresh calibration or holdout')
    return True


def fresh_receipts(receipts, consumed_ids, consumed_requests, consumed_traces, frozen_utc):
    ids, requests, traces = set(consumed_ids), set(consumed_requests), set(consumed_traces)
    frozen = dt.datetime.fromisoformat(frozen_utc)
    if frozen.tzinfo is None:
        raise ValueError('timezone required')
    for r in receipts:
        if (r['session_id'] in ids or r['fingerprint'] in traces or
                dt.datetime.fromisoformat(r['started_utc']) <= frozen):
            raise ValueError('stale/replayed session')
        if len(r['request_ids']) != len(set(r['request_ids'])) or requests & set(r['request_ids']):
            raise ValueError('replayed request')
        ids.add(r['session_id']); traces.add(r['fingerprint']); requests.update(r['request_ids'])
    return True


def paired(a, b):
    if a['session_id'] == b['session_id']:
        raise ValueError('paired sessions must be distinct')
    for key in PAIR_FIELDS:
        if key not in a or key not in b or a[key] != b[key]:
            raise ValueError('paired-control mismatch: '+key)
    if (a['runtime_precreated'] is not True or a['resident_tasks'] != ['classification', 'detection']
            or a['warmup_per_runtime'] < 2 or a['thermal_range'] != [0]):
        raise ValueError('unfair residency/warmup/thermal')
    if a['configuration'] != 'CPU_serial_two_resident' or b['configuration'] != 'CPU_GPU_two_resident':
        raise ValueError('invalid control arms')
    if (a.get('backend_mapping') != {'classification':'CPU','detection':'CPU'} or
            b.get('backend_mapping') not in ({'classification':'CPU','detection':'GPU'},
                                            {'classification':'GPU','detection':'CPU'}) or
            a.get('max_in_flight') != 1 or b.get('max_in_flight') != 2):
        raise ValueError('paired backend/concurrency mismatch')
    return True


def memory_admit(snapshot, estimate, now_ns):
    """Proposed gate; unknown evidence rejects. PSS is NOT the Java heap limit."""
    required = ('mono_ns', 'avail_bytes', 'threshold_bytes', 'low_memory', 'pss_bytes',
                'memory_class_mib', 'large_memory_class_mib', 'java_used_bytes', 'java_max_bytes', 'thermal_status')
    if any(k not in snapshot for k in required) or estimate.get('validated') is not True or type(now_ns) is not int:
        return False
    numeric = [snapshot[k] for k in required if k != 'low_memory']
    if (any(type(v) is not int or v < 0 for v in numeric) or type(snapshot['low_memory']) is not bool or
            snapshot['memory_class_mib']<=0 or snapshot['large_memory_class_mib']<=0 or snapshot['java_max_bytes']<=0):
        return False
    keys = ('max_age_ns', 'incremental_pss_upper_bytes', 'pressure_reserve_bytes',
            'java_increment_upper_bytes', 'java_reserve_bytes', 'resident_pss_upper_bytes')
    if any(type(estimate.get(k)) is not int or estimate[k] < 0 for k in keys):
        return False
    age = now_ns-snapshot['mono_ns']
    return (0 <= age <= estimate['max_age_ns'] and not snapshot['low_memory'] and
            snapshot['thermal_status'] == 0 and
            snapshot['pss_bytes'] <= estimate['resident_pss_upper_bytes'] and
            snapshot['avail_bytes']-snapshot['threshold_bytes'] >
            estimate['incremental_pss_upper_bytes']+estimate['pressure_reserve_bytes'] and
            snapshot['java_max_bytes']-snapshot['java_used_bytes'] >
            estimate['java_increment_upper_bytes']+estimate['java_reserve_bytes'])


def group_key(r, model):
    if model == 'A_cell_mean': return r['cell']
    base = r['cell']+'|'+r['phase']
    if model in ('C_setup_service', 'D_sequence_setup', 'E_joint_empirical'):
        base += '|'+r['context']
    if model == 'D_sequence_setup':
        base += '|from='+r['source_cell']
    return base


def fit(rows, model):
    groups = {}
    for r in rows:
        groups.setdefault(group_key(r, model), {}).setdefault(r['session_id'], []).append(r)
    return groups


def predict(train, row, model, fitted):
    if model == 'G_pooled_multiplier':
        same = [r for r in train if r['cell'] == row['cell'] and r['invocation'] >= 3]
        if not same: return None
        bases = {c: st.mean(r['service_ns'] for r in train if r['cell']==c and r['invocation']>=3)
                 for c in {r['cell'] for r in train if r['invocation']>=3}}
        ratios = [r['service_ns']/bases[r['cell']] for r in train
                  if r['phase']==row['phase'] and r['cell'] in bases]
        if not ratios: return None
        return st.mean(r['service_ns'] for r in same)*st.mean(ratios)
    block = fitted.get(group_key(row, model))
    if not block: return None
    if model == 'E_joint_empirical':
        return st.mean(st.mean(r['setup_ns']+r['active_service_ns'] for r in rs) for rs in block.values())
    # C/D explicitly paired decomposition: never add setup to inclusive service again.
    return st.mean(r['service_ns'] for rs in block.values() for r in rs)


def comparisons(rows):
    results = {}
    for model in MODELS:
        folds=[]
        for sid in sorted({r['session_id'] for r in rows}):
            train=[r for r in rows if r['session_id']!=sid]; test=[r for r in rows if r['session_id']==sid]
            fitted=fit(train, model); good=[]
            for r in test:
                p=predict(train,r,model,fitted)
                if p is not None: good.append((r['service_ns'],p))
            folds.append(dict(session_id=sid,n=len(test),supported=len(good),
                              absolute_error_sum=sum(abs(y-p) for y,p in good),observed_sum=sum(y for y,p in good)))
        n=sum(f['supported'] for f in folds); error=sum(f['absolute_error_sum'] for f in folds)
        results[model]=dict(support=n/len(rows),mae_ms=error/n/1e6 if n else None,
                           wape=error/sum(f['observed_sum'] for f in folds), folds=folds,
                           approval=False, groups=len(fit(rows,model)))
    return results


def empirical_draw(model, key, seed, block_number, invocation):
    """A paired observation lookup only; never advances simulated time."""
    if key not in model or any(type(x) is not int or x < 0 for x in (seed,block_number,invocation)):
        raise ValueError('unsupported empirical state/seed')
    blocks=model[key]; names=old.ordered(blocks,seed)
    number=int(old.sha(['v2-block',seed,block_number,key]),16)
    block=blocks[names[number % len(names)]]
    r=block[invocation % len(block)]
    return {k:r[k] for k in ('session_id','request_id','setup_ns','active_service_ns','inference_ns')}


def uncertainty_analysis(rows):
    """Development-only nested session split. No request independence assumption."""
    from scipy.stats import wasserstein_distance, ks_2samp
    ids=old.ordered({r['session_id'] for r in rows},SEED)
    folds=[]
    for sid in ids:
        others=[s for s in ids if s!=sid]; calibration=others[::3]; train_ids=[s for s in others if s not in calibration]
        train=[r for r in rows if r['session_id'] in train_ids]
        model=fit(train,'E_joint_empirical'); scores=[]; scored_ids=[]; unsupported_ids=[]
        for cal in calibration:
            residuals=[]
            for r in (r for r in rows if r['session_id']==cal):
                point=predict(train,r,'E_joint_empirical',model)
                if point is None:
                    unsupported_ids.append(cal);break
                residuals.append(abs(r['service_ns']-point)/point)
            else:
                scores.append(max(residuals));scored_ids.append(cal);continue
        interval=finite_interval(scores)
        test=[r for r in rows if r['session_id']==sid]; covered=[]; distributions=[]
        for key in sorted({group_key(r,'E_joint_empirical') for r in test}):
            block=model.get(key)
            if not block:continue
            ys=[r['service_ns'] for r in test if group_key(r,'E_joint_empirical')==key]
            values=[r['service_ns'] for rs in block.values() for r in rs]
            weights=[1/(len(block)*len(rs)) for rs in block.values() for r in rs]
            mean=sum(y*w for y,w in zip(values,weights))
            def q(p):
                total=0
                for y,w in sorted(zip(values,weights)):
                    total+=w
                    if total>=p-1e-12:return y
                return max(values)
            distributions.append(dict(key=key,n=len(ys),source_sessions=len(block),
                observed=old.describe(ys),predicted_distribution=dict(mean=mean,median=q(.5),p95=q(.95)),
                normalized_wasserstein=float(wasserstein_distance(ys,values,v_weights=weights))/mean,
                ks_request_weighted_descriptive=float(ks_2samp(ys,values).statistic),
                tail_above_training_p95=sum(y>q(.95) for y in ys)/len(ys),
                warning='KS effect size only, no iid-request p value; sparse-state P95 not reliable'))
        if interval['finite']:
            for r in test:
                point=predict(train,r,'E_joint_empirical',model)
                covered.append(point is not None and abs(r['service_ns']-point)<=interval['radius']*point)
        folds.append(dict(session_id=sid,fit_sessions=train_ids,score_sessions=calibration,
                          effective_score_sessions=scored_ids,unsupported_score_sessions=unsupported_ids,
                          interval=interval,coverage=st.mean(covered) if covered else None,
                          distributions=distributions))
    return dict(candidate='F_session_max_split_conformal',nominal_coverage=.9,folds=folds,
                approval=False,scope='development sensitivity; heterogeneous protocols are NOT exchangeable new validation sessions',
                unsupported_calibration_sessions='cannot score missing cells; effective score count reported; no finite-sample validity claim for this diagnostic selection')


def stabilization(rows):
    groups={}; episodes={}
    for r in rows:
        key=r['cell']+'|'+r['origin']+'|'+r['context']
        group=groups.setdefault(key, {})
        group.setdefault(str(r['invocation']),[]).append(r)
        episodes.setdefault((r['session_id'],r['worker'],r['episode']),[]).append(r)
    summary={}
    for key, indices in groups.items():
        summary[key]={i:dict(sessions=sorted({r['session_id'] for r in rs}),
                            service_ms=old.describe([r['service_ns']/1e6 for r in rs]),
                            setup_ms=old.describe([r['setup_ns']/1e6 for r in rs]),
                            active_ms=old.describe([r['active_service_ns']/1e6 for r in rs]),
                            inference_ms=old.describe([r['inference_ns']/1e6 for r in rs])) for i,rs in indices.items()}
    change=[]
    for key,rs in episodes.items():
        rs.sort(key=lambda r:r['invocation'])
        if len(rs)<6: continue
        # Descriptive log-active BIC: k free initial calls, constant remaining tail.
        ys=[math.log(r['active_service_ns']) for r in rs]; n=len(ys); scores=[]
        for k in range(min(5,n-3)+1):
            tail=ys[k:]; mean=st.mean(tail); sse=sum((y-mean)**2 for y in tail)
            scores.append(n*math.log(max(sse/n,1e-12))+(k+2)*math.log(n))
        k=min(range(len(scores)),key=scores.__getitem__)
        change.append(dict(session_id=key[0],worker=key[1],episode=key[2],cell=rs[0]['cell'],
                           context=rs[0]['context'], n=n,tail_start_invocation=k+1,bic=scores,
                           gaps_ns=[r['gap_ns'] for r in rs],request_ids=[r['request_id'] for r in rs]))
    return dict(by_invocation=summary,change_points=change,
                limitation='Descriptive development BIC, no causal JIT/GC claim; input/idle/priority confounding remains. No latency-based state assignment on validation.')


def sample_size(rows):
    from scipy.stats import binom, beta, norm
    families=8; alpha=.05/families
    # Exact prospective power, not fitting the failed 80.38% coverage.
    for n in range(1,10001):
        k=next((k for k in range(math.ceil(.9*n),n+1) if binom.sf(k-1,n,.9)<=alpha),n+1)
        power=float(binom.sf(k-1,n,.95))
        if power>=.8: break
    variations={}
    for cell in sorted({r['cell'] for r in rows}):
        for phase_name in sorted({r['phase'] for r in rows if r['cell']==cell}):
            subset=[r for r in rows if r['cell']==cell and r['phase']==phase_name]
            means=[st.mean(r['service_ns'] for r in subset if r['session_id']==sid)
                   for sid in sorted({r['session_id'] for r in subset})]
            cv=st.stdev(means)/st.mean(means) if len(means)>1 else None
            needed=math.ceil((float(norm.ppf(1-alpha/2))*cv/.05)**2) if cv is not None else None
            variations[cell+'|'+phase_name]=dict(sessions=len(means),cv=cv,normal_approx_n_mean_5pct=needed)
    dropout_upper=float(beta.ppf(.95,2+1,23-2))
    # Hoeffding applies to session-mean coverage in [0,1], not correlated requests.
    bounded_n=math.ceil(math.log(2*families/.05)/(2*.05**2))
    max_mean=max(v['normal_approx_n_mean_5pct'] or 0 for v in variations.values())
    per_family=max(n,bounded_n,max_mean)
    return dict(families=families,coverage_target=.9,alternative_for_power=.95,power_target=.8,
                familywise_alpha=.05,exact_binomial_n=n,exact_min_successes=k,exact_power=power,
                unit='independent session; binomial success means all planned requests covered',
                variability=variations,mean_relative_precision=.05,coverage_precision=.05,
                bounded_session_coverage_n=bounded_n,complete_sessions_per_family=per_family,
                complete_total=per_family*families,dropout_basis='2 host failures / 23 attempts; transfer recovery retained; conservative planning proxy, not device failure probability',
                dropout_upper95=dropout_upper,attempt_budget_per_family=math.ceil(per_family/(1-dropout_upper)),
                conformal_min_finite_sessions=9,conformal_rank_resolution_sessions=99,
                status='planning_bound_not_execution_authorization; heterogeneous old CV not a new-protocol guarantee')


def collect(bundle, final):
    old.validate_bundle(bundle)
    from tools.d1_final_service import validate_frozen
    validate_frozen(final, FINAL_SHA)
    sessions=read(bundle/'observations.json')['sessions']
    seen={s['session_id'] for s in sessions}
    for name in ('calibration_sessions.json','holdout_sessions.json','control_sessions.json'):
        for s in read(final/name):
            if s['session_id'] not in seen: sessions.append(s);seen.add(s['session_id'])
    sources={}
    for f in read(final/'final_artifact_provenance.json')['files']:
        path=final/f['path']
        if digest(path)!=f['sha256']:raise ValueError('stale final evidence: '+str(path))
        sources[str(path)]=f['sha256']
    for s in sessions:
        for f in s['files']:
            path=Path(f['path'])
            if digest(path)!=f['sha256']: raise ValueError('stale profile source: '+str(path))
            sources[str(path)]=f['sha256']
    rows=[r for s in sessions for r in trace_rows(s)]
    failed=read(final/'failed_host_attempt_diagnostic.json')
    failed_root=final/'A'/'profiles'/failed['session_id']
    diagnostic=[]
    for p in sorted(failed_root.rglob('*')):
        if p.is_file(): sources[str(p)]=digest(p)
    events=failed_root/'artifacts'/'events.jsonl'
    for line in events.read_text().splitlines():
        e=__import__('json').loads(line)
        diagnostic.append(e)
    for p in (final/'FINAL_REPORT.md',final/'frozen_contract.json',final/'attempt_ledger.json',
              final/'matched_control_comparison.json',bundle/'observations.json'):
        sources[str(p)]=digest(p)
    return sessions,rows,sources,dict(record=failed,events=diagnostic,
        use='consumed development diagnostic, preserved; absent validated host equivalence/context prevents primary parameter fitting')


def validate(root, expected):
    root=Path(root); path=root/'design_contract.json'
    if digest(path)!=expected: raise ValueError('frozen-contract immutability failure')
    c=read(path)
    import jsonschema
    jsonschema.validate(c,read(Path(__file__).with_name('schemas')/'service-model-v2-design-v1.schema.json'))
    required={'development_rows.json','diagnostic_attempt.json','candidate_comparison.json','stabilization.json',
              'sample_size.json','uncertainty_analysis.json','development_model.json','development_registry.json'}
    if set(c['artifacts'])!=required:raise ValueError('missing artifact inventory')
    for name,h in c['artifacts'].items():
        if Path(name).name!=name or digest(root/name)!=h: raise ValueError('artifact mutation')
    for name,h in c['sources'].items():
        if digest(Path(name))!=h: raise ValueError('stale source')
    for name,h in c['analysis_sources'].items():
        if digest(Path(name))!=h: raise ValueError('analysis changed')
    partition(c['consumed_sessions'],[],[],c['consumed_sessions'])
    if c['status']!=STATUS or c['simulation_approved'] or c['device_execution_allowed']:
        raise ValueError('unapproved execution')
    result=dict(status=STATUS,dispatch_count=0,simulated_completion_count=0,device_commands=[],
                independent_holdout_count=0,design_contract_sha256=expected)
    if (root/'no_op.json').exists() and read(root/'no_op.json')!=result:
        raise ValueError('fabricated no-op')
    return result


def generate(bundle, final, output):
    analysis_paths=[Path(__file__),Path(__file__).with_name('schemas')/'service-model-v2-design-v1.schema.json',
                    Path('docs/SERVICE_MODEL_V2_DESIGN.md'),Path('tools/d1_service_model.py'),
                    Path('tools/d1_sim_prepare.py'),Path('tools/d1_task_profile.py')]
    analysis_hashes={str(p.resolve()):digest(p) for p in analysis_paths}
    sessions,rows,sources,diagnostic=collect(Path(bundle),Path(final))
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    for name,value in [('development_rows.json',rows),('diagnostic_attempt.json',diagnostic),
                       ('candidate_comparison.json',comparisons(rows)),('stabilization.json',stabilization(rows)),
                       ('sample_size.json',sample_size(rows)),('uncertainty_analysis.json',uncertainty_analysis(rows)),
                       ('development_model.json',fit(rows,'E_joint_empirical'))]: save(output/name,value)
    consumed=sorted([s['session_id'] for s in sessions]+[diagnostic['record']['session_id']])
    save(output/'development_registry.json',dict(sessions=sessions,consumed_sessions=consumed,
        requests=[r['request_id'] for r in rows]+[e['request_id'] for e in diagnostic['events']],
        fingerprints=[s['measurement_fingerprint'] for s in sessions],
        diagnostic_fingerprint=old.sha([{k:e[k] for k in ('scheduled_arrival_ns','execution_start_ns','completion_ns',
            'task_id','requested_backend','input_tensor_sha256')} for e in sorted(diagnostic['events'],key=lambda e:(e['execution_start_ns'],e['request_id']))]),
        previous_holdout_status='all_consumed_development; never approval holdout',
        validated_sessions=len(sessions),validated_requests=len(rows),diagnostic_requests=len(diagnostic['events'])))
    c=dict(protocol=PROTOCOL,status=STATUS,seed=SEED,simulation_approved=False,device_execution_allowed=False,
           consumed_sessions=consumed,selected_structure='C paired setup/active service + E session-block empirical; F optional session conformal; D source-cell audit',
           parameter_status='development only; new telemetry calibration required',coverage_required=.9,
           deadline='calibration_pending',thermal_status_allowed=[0],fallback='forbidden',
           required_missing=['runtime lifecycle monotonic spans','two resident CPU runtimes under one global serial gate',
                             'synchronized MemoryInfo and calibrated admission bounds','new protocol calibration and untouched validation',
                             'deadline/service objective and distribution equivalence margins'],
           artifacts={p.name:digest(p) for p in sorted(output.glob('*.json'))},sources=sources,
           analysis_sources=analysis_hashes)
    save(output/'design_contract.json',c)
    result=validate(output,digest(output/'design_contract.json'))
    save(output/'no_op.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['analyze','validate','no-op','dry-run'])
    p.add_argument('--bundle',type=Path);p.add_argument('--final',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-sha256')
    a=p.parse_args()
    result=generate(a.bundle,a.final,a.output) if a.command=='analyze' else validate(a.output,a.expected_sha256)
    print(__import__('json').dumps(result,indent=2))


if __name__=='__main__': main()
