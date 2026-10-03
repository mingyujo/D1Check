"""One-family development identification and trace association. PC only, no device I/O."""
import argparse
import copy
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_causal_background_candidate as c
from tools import d1_background_activity_result as reader

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT/'docs/results/online_policy_study_01/background_identification_pc_v1/analysis_contract.json'
MODEL = ROOT/'docs/results/online_policy_study_01/separated_power_final/model.json'
SPECS = [('v4', 0, 'C0_PRE'), ('v4', 1, 'CPU96'), ('v6', 0, 'PAR96'), ('v6', 1, 'C0_POST')]


def geometry(matrix):
    x = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(x, axis=0)
    active = norms > 1e-12
    a = x[:, active]/norms[active] if active.any() else np.zeros((len(x), 0))
    sv = np.linalg.svd(a, compute_uv=False)
    rank = int(np.sum(sv > sv[0]*1e-12)) if len(sv) else 0
    return dict(columns=x.shape[1], active_columns=int(active.sum()), rank=rank,
                zero_columns=np.where(~active)[0].tolist(), scaled_singular_values=sv.tolist(),
                condition_number=float(sv[0]/sv[-1]) if len(sv) and rank == a.shape[1] else None)


def correlation(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    x, y = x-x.mean(), y-y.mean()
    den = np.linalg.norm(x)*np.linalg.norm(y)
    return None if den < 1e-12 else float(x@y/den)


def export_bundle(archive, output):
    archive, output = Path(archive), Path(output)
    if output.exists(): raise FileExistsError('fresh bundle required')
    cfg = c.read(CONTRACT)
    if c.digest(MODEL) != cfg['model_sha256']: raise ValueError('frozen model drift')
    model = c.read(MODEL); cases = []; bindings = {}
    def bind(file):
        bindings[Path(file).relative_to(archive).as_posix()] = c.digest(file)
    for block, index, label in SPECS:
        file = archive/f'background_activity_plan_{block}/collection_plan.json'; plan = c.read(file)
        e = plan['entries'][index]
        folder, rows, origin, end, events, counts, power, points, segments, data = reader.load_inputs(file, plan, e, model)
        art = folder/'artifacts'; audit = c.read(folder/'trace_export/audit.json')
        if audit['status'] != 'content_eligible_descriptive_only' or len(audit['bins']) != 24 or not all(b['full_sched_coverage'] for b in audit['bins']):
            raise ValueError('trace content not eligible')
        for f in [file, file.parent/e['manifest'], Path(plan['output_root'])/'FINAL_RECEIPT.json',
                  folder/'validated.json', folder/'thermal.jsonl', folder/'trace_export/audit.json',
                  *[art/n for n in ('progress.jsonl','requests.json','manifest.json','cleanup.json','common_boundary.json','start_ap.accepted.json')]]:
            bind(f)
        raw = [r for r in events if r['kind'] == 'power_sample']
        samples = [dict(t_s=((r['snapshot_start_ns']+r['sensor_read_end_ns'])//2-origin)/1e9,
                        ready_s=(r['mono_ns']-origin)/1e9,
                        app_ready_s=(r['past_input_ready_ns']-origin)/1e9,
                        w=c.energy.discharge_w(r, 1000)) for r in raw]
        if any(not s['t_s'] <= s['app_ready_s'] <= s['ready_s'] for s in samples):
            raise ValueError('sample availability clock ordering')
        legacy = reader.online.energy_at(data, 10, 30)/20
        manifest = c.read(art/'manifest.json')
        # Request identifiers are replaced; time/task/priority/deadline are preserved.
        requests = [dict(r, request_id=f'{block}_{label}_{i}') for i, r in enumerate(manifest['requests'])]
        end_s = data['inputs']['segments'][-1]['end_s']
        if rows:
            _, future = reader.online.forecast({}, requests, manifest['policy'], model, planning_input_role='confirmation')
            future = [{k:s[k] for k in ('start_s','end_s','state')} for s in future]
            future.append(dict(start_s=120., end_s=end_s, state='idle'))
        else: future = [dict(start_s=0., end_s=end_s, state='idle')]
        case = dict(id=f'{block}_{label}', block=block, role='development', condition=label,
                    preload=data['inputs']['preload'], preload_w=data['preload_power_w'], legacy_preload_w=legacy,
                    preload_window_s=data['preload_power_window_s'], power=samples,
                    actual_segments=data['inputs']['segments'], forecast_segments=future,
                    query_s=data['inputs']['query_s'], observed_ap=data['observed_ap_c'],
                    manifest_requests=requests, trace_bins=audit['bins'],
                    observed_120s_j=reader.online.energy_at(data,0,120),
                    initial_ap_c=c.read(art/'start_ap.accepted.json')['ap_c'],
                    initial_in_original_range=c.read(art/'start_ap.accepted.json')['initial_ap_in_frozen_development_range'],
                    actual_last_lane_s=max((r['lane_available_ns']-origin)/1e9 for r in rows) if rows else None)
        case['frozen_ap'] = c.base_ap(case, model, case['query_s'], 'actual_segments')
        audit_rows = []
        for r in (x for x in events if x['kind'] == 'causal_power_input'):
            issue, a, b = ((r[k]-origin)/1e9 for k in ('issue_ns','window_start_ns','window_end_ns'))
            if r['future_ap_used'] or not a < b <= (r['latest_ready_ns']-origin)/1e9 <= issue:
                raise ValueError('app future input')
            available = [dict(s, ready_s=s['app_ready_s']) for s in samples]
            j = c.integral(available, a, b, available_at=issue)
            value = None if j is None else j/(b-a)
            audit_rows.append(dict(issue_s=issue, window_start_s=a, window_end_s=b, status=r['status'],
                logged_w=r.get('mean_whole_device_w'), reconstructed_w=value,
                difference_w=None if value is None else value-r['mean_whole_device_w']))
        if len(audit_rows)!=14 or any(r['status']!='available' or r['difference_w'] is None or abs(r['difference_w'])>1e-8 for r in audit_rows):
            raise ValueError('logged past-input reproduction failed; no fit')
        case['app_input_audit'] = audit_rows
        saved = ROOT/f'docs/results/online_policy_study_01/background_activity_run{ "03" if block=="v4" else "04"}/summary.json'
        old = next(s for s in c.read(saved)['sessions'] if s['condition']==e['condition'])
        legacy_j = legacy*120+c.task_j(case['actual_segments'],model,0,120)
        if abs(legacy_j-old['predicted_energy_j'])>1e-8 or abs(case['observed_120s_j']-old['observed_energy_j'])>1e-8:
            raise ValueError('old result not reproduced')
        score = c.scoring.score(case['observed_ap'],case['frozen_ap'])
        if any(abs(score[k]-old['ap_scores'][k])>1e-10 for k in score):raise ValueError('AP changed during power-window fix')
        case['legacy_predicted_j'] = legacy_j
        case['corrected_predicted_j'] = case['preload_w']*120+c.task_j(case['actual_segments'],model,0,120)
        cases.append(case)
    output.mkdir(parents=True)
    c.write(output/'inputs.json', cases)
    (output/'model.json').write_bytes(MODEL.read_bytes())
    c.write(output/'source_hashes.json', bindings)
    c.write(output/'resources.json',dict(files={n:c.digest(output/n) for n in ('inputs.json','model.json','source_hashes.json')},
        contract_sha256=c.digest(CONTRACT), virtual_forecast_runs=2, device_commands=0))
    return dict(sessions=4, app_input_reproductions=56, device_commands=0)


def features(case, model, cfg):
    rows = c.updates(case, model, cfg)
    z = [c.correction_at(rows,t,model['ap']['beta'],cfg['start_s']) for t in case['query_s']]
    if any(x is None for x in z):raise ValueError('missing candidate inputs; no selected target subset')
    return rows, np.array(z)


def sensitivity(cases, model, cfg):
    design=[]; zs=[]
    for i, case in enumerate(cases):
        _, z=features(case,model,cfg); q=np.array(case['query_s']); n=len(q)
        base=np.array(case['frozen_ap']); columns=[]
        for name in ('beta','k'):
            changed=copy.deepcopy(model); step=1e-4*model['ap'][name]
            changed['ap'][name]+=step
            columns.append((np.array(c.base_ap(case,changed,q.tolist(),'actual_segments'))-base)/step)
        for j in range(len(cases)):
            decay=np.exp(-model['ap']['beta']*(q-35))
            columns.extend([decay if i==j else np.zeros(n),(1-decay) if i==j else np.zeros(n)])
        weight=1/math.sqrt(n*len(cases));design.append(np.array(columns).T*weight);zs.append(z*weight)
    x=np.vstack(design); z=np.concatenate(zs)
    projection=x@np.linalg.lstsq(x,z,rcond=None)[0]
    den=float(z@z)
    return dict(nuisance_columns=['beta','k']+[f'{s}_{kind}' for s in range(len(cases)) for kind in ('initial','effective_equilibrium')],
        joint_geometry=geometry(np.column_stack((x,z))),
        gamma_basis_energy=den, gamma_basis_remaining_fraction=None if den<=1e-12 else float((z-projection)@(z-projection)/den),
        interpretation='geometry only; no nuisance coefficient or target fitted; no physical equilibrium measurement')


def associations(cases, model):
    rows=[]; matrices=[]; correlations=[]
    for i,case in enumerate(cases):
        local=[]
        for b in case['trace_bins']:
            a,e=b['start_s'],b['end_s']; duration=e-a
            observed=c.integral(case['power'],a,e)
            if observed is None:raise ValueError('missing five-second energy; no row selection')
            exposure=reader.online.exposure(case['actual_segments'],a,e)/duration
            residual=observed/duration-case['preload_w']-c.task_j(case['actual_segments'],model,a,e)/duration
            row=dict(id=case['id'],block=case['block'],start_s=a,end_s=e,observed_j=observed,
                energy_residual_w=residual,state_mix=sum(v>1e-9 for v in exposure)+(sum(exposure)<1-1e-9)>1)
            for key in ('benchmark','tracer','other'):
                row[key+'_cpu_rate']=b[key+'_cpu_seconds']/duration
            for key,value in zip(reader.online.STATES,exposure):row[key+'_fraction']=float(value)
            observed_ap=c.scoring.interpolate(case['query_s'],case['observed_ap'],(a+e)/2)
            predicted_ap=c.scoring.interpolate(case['query_s'],case['frozen_ap'],(a+e)/2)
            row['ap_residual_observed_minus_frozen_c']=None if observed_ap is None or predicted_ap is None else observed_ap-predicted_ap
            local.append(row)
            matrices.append([*[float(i==j) for j in range(len(cases))],*exposure,*[row[k+'_cpu_rate'] for k in ('benchmark','tracer','other')]])
        for signal in ('benchmark','tracer','other'):
            correlations.append(dict(id=case['id'],signal=signal,windows=len(local),
                centered_correlation=correlation([r[signal+'_cpu_rate'] for r in local],[r['energy_residual_w'] for r in local]),
                inference='descriptive within-session; no IID significance/causality'))
        rows.extend(local)
    return rows,dict(energy_activity_geometry=geometry(matrices),correlations=correlations,
        column_names=[case['id']+'_intercept' for case in cases]+list(reader.online.STATES)+['benchmark_cpu_rate','tracer_cpu_rate','other_cpu_rate'],
        cpu_activity_is_power_input=False,gpu_radio_attributed=False)


def analyze(bundle, output):
    bundle, output=Path(bundle),Path(output)
    if output.exists():raise FileExistsError('fresh analysis output required')
    cfg=c.read(CONTRACT); bindings=c.read(bundle/'resources.json')
    if bindings['contract_sha256']!=c.digest(CONTRACT):raise ValueError('contract drift')
    for n,sha in bindings['files'].items():
        if Path(n).name!=n or c.digest(bundle/n)!=sha:raise ValueError('bundle drift')
    if c.digest(bundle/'model.json')!=cfg['model_sha256']:raise ValueError('model drift')
    cases=c.read(bundle/'inputs.json');model=c.read(bundle/'model.json')
    if [x['id'] for x in cases]!=cfg['cases'] or any(x['role']!='development' for x in cases):
        raise ValueError('exact four development cases required')
    fit=c.fit(cases,model,cfg);gamma=fit['gamma']
    if gamma is None:
        output.mkdir(parents=True)
        result=dict(status='unidentified',gamma=None,fit=fit,reason='zero excitation; no coefficient invented',
                    default=False,strict_support=False,experiment_ready=False,device_commands=0)
        c.write(output/'candidate.json',result)
        return result
    cross=[]
    for excluded in [[x['id']] for x in cases]+[[x['id'] for x in cases if x['block']==block] for block in ('v4','v6')]:
        f=c.fit([x for x in cases if x['id'] not in excluded],model,cfg)
        for case in [x for x in cases if x['id'] in excluded]:
            _,z=features(case,model,cfg);g=f['gamma']
            score=None if g is None else c.scoring.score(case['observed_ap'],np.array(case['frozen_ap'])+g*z)
            cross.append(dict(exclusion='session' if len(excluded)==1 else 'block',excluded=excluded,id=case['id'],
                gamma=g,unconstrained_gamma=f['unconstrained_gamma'],frozen=c.scoring.score(case['observed_ap'],case['frozen_ap']),candidate=score))
    rows=[];curves=[];updates=[];forecasts=[]
    for case in cases:
        rs,z=features(case,model,cfg);base=np.array(case['frozen_ap']);v=base+gamma*z
        updates.extend(dict(id=case['id'],**r) for r in rs)
        rows.append(dict(id=case['id'],block=case['block'],role=case['role'],initial_ap_c=case['initial_ap_c'],
            observed_120s_j=case['observed_120s_j'],legacy_predicted_j=case['legacy_predicted_j'],corrected_predicted_j=case['corrected_predicted_j'],
            legacy_error_j=case['legacy_predicted_j']-case['observed_120s_j'],corrected_error_j=case['corrected_predicted_j']-case['observed_120s_j'],
            legacy_preload_w=case['legacy_preload_w'],corrected_preload_w=case['preload_w'],
            frozen=c.scoring.score(case['observed_ap'],base),candidate=c.scoring.score(case['observed_ap'],v),
            app_input_max_difference_w=max(abs(x['difference_w']) for x in case['app_input_audit']),independent_validation=False))
        for t,y,a,b,x in zip(case['query_s'],case['observed_ap'],base,v,z):
            curves.append(dict(id=case['id'],t_s=t,observed_ap_c=y,frozen_ap_c=float(a),candidate_ap_c=float(b),unit_gamma_basis=float(x)))
        for issue in range(35,180,10):
            for h in (10,30):
                if issue+h>case['query_s'][-1]:continue
                f=c.issued_forecast(case,model,gamma,cfg,issue,h)
                obs=c.scoring.interpolate(case['query_s'],case['observed_ap'],issue+h)
                j=c.integral(case['power'],issue,issue+h) if issue+h<=120 else None
                forecasts.append(dict(id=case['id'],**f,observed_ap_c=obs,observed_j=j,
                    ap_error_c=None if f['predicted_ap_c'] is None else f['predicted_ap_c']-obs,
                    frozen_ap_error_c=None if f.get('frozen_ap_c') is None else f['frozen_ap_c']-obs,
                    j_error=None if j is None or f['predicted_j'] is None else f['predicted_j']-j,
                    frozen_j_error=None if j is None or f.get('frozen_j') is None else f['frozen_j']-j))
    bins,assoc=associations(cases,model);separation=sensitivity(cases,model,cfg)
    reasons=[]
    if gamma==0:reasons.append('nonnegative optimum at zero; no positive correction supported')
    signs=[s['unconstrained_gamma'] for s in fit['sessions'] if s['unconstrained_gamma'] is not None]
    if min(signs)<0<max(signs):reasons.append('per-session sign disagreement')
    for mode in ('session','block'):
        selected=[r for r in cross if r['exclusion']==mode]
        if any(r['candidate'] is None for r in selected) or np.mean([r['candidate']['mae_c'] for r in selected])>np.mean([r['frozen']['mae_c'] for r in selected]):
            reasons.append('worsened or unavailable '+mode+'-excluded mean AP MAE')
    candidate=dict(version=cfg['version'],formula=cfg['formula'],fit=fit,cross_validation=cross,
        status='not_adopted' if reasons else 'research_candidate_requires_independent_confirmation',reasons=reasons,
        separability=separation,source_model_sha256=c.digest(bundle/'model.json'),contract_sha256=c.digest(CONTRACT),
        independent_confirmation_sessions=0,default=False,strict_support=False,experiment_ready=False)
    output.mkdir(parents=True);c.write(output/'candidate.json',candidate);c.write(output/'summary.json',rows)
    c.write(output/'association.json',assoc);c.write(output/'forecasts.json',forecasts)
    for n,r in [('ap_paths.csv',curves),('causal_updates.csv',updates),('activity_bins.csv',bins)]:c.csv_write(output/n,r)
    c.write(output/'scope.json',dict(development_sessions=4,acquisition_blocks=2,post_hoc=True,
        new_independent_validation=0,candidate_families=1,coefficients_changed_in_original=0,
        baseline_bug_fixed=True,cpu_activity_is_predictor=False,device_commands=0,experiment_ready=False))
    return dict(status=candidate['status'],gamma=gamma,unconstrained_gamma=fit['unconstrained_gamma'],reasons=reasons)


def main():
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('action',choices=['bundle','analyze'])
    q.add_argument('--archive');q.add_argument('--bundle');q.add_argument('--output',required=True)
    a=q.parse_args(); result=export_bundle(a.archive,a.output) if a.action=='bundle' else analyze(a.bundle,a.output)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
