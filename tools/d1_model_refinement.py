"""Read-only existing-data study. Candidate outputs never enter simulator/RL defaults."""
import argparse
import copy
import csv
import hashlib
import gzip
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_online_policy_model as base
from tools import d1_ap_completion_model as thermal
from tools import d1_ap_preparation_memory as memory
from tools.d1_ap_idle_response import preload_reference
from tools import d1_arrival_policy_screen as screen

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/model_refinement_01'
MODEL = ROOT / 'docs/results/online_policy_study_01/overnight_sustained_run01/model.json'
MODEL_SHA = '5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'
NAMES = ('FROZEN', 'AP_SIMPLE', 'AP_DELAY', 'E_TREND')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    return json.loads(gzip.decompress(path.read_bytes()).decode('utf8') if path.suffix=='.gz' else path.read_text(encoding='utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def table(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w', encoding='utf8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)


def condition_summary(rows):
    result=[]
    for block in ('confirmation','sustained'):
        for mode in ('A_conditional','B_arrival'):
            for policy in sorted({r['policy'] for r in rows if r['block']==block}):
                for name in NAMES:
                    use=[r for r in rows if r['block']==block and r['mode']==mode and r['policy']==policy and r['candidate']==name]
                    valid=[r for r in use if r.get('abs_j') not in ('',None)]
                    result.append(dict(block=block,mode=mode,policy=policy,candidate=name,n=len(valid),
                        unavailable=len(use)-len(valid),
                        energy_mae_j=float(np.mean([float(r['abs_j']) for r in valid])) if valid else None,
                        ap_mae_c=float(np.mean([float(r['mae_c']) for r in valid])) if valid else None))
    return result


def integral(c, a, b):
    """Independent clipped trapezoid, no extrapolation or missing-value zero fill."""
    t = np.array(c['power_t']); y = np.array(c['power_w'], dtype=float)
    if b < a or a < t[0] or b > t[-1]:
        raise ValueError('power coverage')
    use = (t[:-1] < b) & (t[1:] > a)
    if np.any(np.diff(t)[use] > 2.5) or np.any(np.diff(t) <= 0):
        raise ValueError('power gap/order')
    indices = np.flatnonzero(use)
    if any(not np.isfinite(y[i:i+2]).all() for i in indices):
        raise ValueError('missing power')
    grid = np.r_[a, t[(t > a) & (t < b)], b]
    values = np.interp(grid, t, y)
    return float(np.trapezoid(values, grid))


def case_input(c, segments):
    # Evaluation targets are deliberately absent at the prediction boundary.
    return dict(inputs=dict(preload=c['pre'], query_s=c['q'], segments=segments))


def simple_basis(c, segments, frozen):
    beta = frozen['ap']['beta']; slopes = frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
    inp = case_input(c, segments)
    # Reuse complete frozen schedule/preload validity gates.
    thermal.basis(inp, frozen['ap']['parameters'], beta)
    reference = preload_reference([(p['t'], p['ap']) for p in c['pre']], beta)
    init = dict(reference_c=reference['effective_idle_reference_c'], h_last_c_per_s=0.,
                anchor_s=c['pre'][-1]['t'], anchor_ap_c=c['pre'][-1]['ap'])
    zero = {k: slopes['resident_idle'] for k in slopes}
    a = np.array(memory._propagate(segments, c['q'], zero, beta, 30., 0., init))
    b = np.array(memory._propagate(segments, c['q'], slopes, beta, 30., 0., init))
    d = np.array(memory._propagate(segments, c['q'], slopes, beta, 30., 1., init))
    return a, np.column_stack((b-a, d-b)), init


def trend(c, t):
    delta = integral(c, 10, 30)/20 - integral(c, -20, 0)/20
    return delta*30*(-math.expm1(-max(0., t-35)/30))


def energy_prediction(c, segments, frozen, candidate, t):
    value = c['pre_w']*t + float(base.exposure(segments, 0, t) @ np.array([
        frozen['energy_increment_w'][k] for k in base.STATES]))
    if candidate['name'] == 'E_TREND':
        delta = integral(c, 10, 30)/20 - integral(c, -20, 0)/20
        if min(c['pre_w'], c['pre_w'] + candidate['alpha']*delta) <= 0:
            raise ValueError('candidate nonpositive power; not clipped')
        value += candidate['alpha']*trend(c, t)
    return value


def predict(c, segments, frozen, candidate):
    if candidate['name'] in ('FROZEN', 'E_TREND'):
        ap, init = thermal.predict(case_input(c, segments), frozen['ap'])
    else:
        a, x, init = simple_basis(c, segments, frozen)
        ap = (a+x@np.array([candidate['k'], candidate['g']])).tolist()
    return ap, init


def fit(cases, frozen, name):
    if not cases or any(c['role'] != 'development' for c in cases):
        raise ValueError('only designated development sessions may fit')
    result = dict(name=name, development_ids=[c['id'] for c in cases], default=False,
                  experiment_ready=False, strict_support=False, accuracy_pass=None)
    if name == 'FROZEN':
        return result
    xs, ys = [], []
    for c in cases:
        if name.startswith('AP_'):
            a, x, _ = simple_basis(c, c['actual'], frozen)
            if name == 'AP_SIMPLE':
                x = x[:, :1]
            y = np.array(c['ap'])-a
        else:
            x = np.array([[trend(c, t+5)-trend(c, t)] for t in range(35, 120, 5)])
            baseline = dict(name='FROZEN')
            y = np.array([integral(c, t, t+5) - (
                energy_prediction(c, c['actual'], frozen, baseline, t+5) -
                energy_prediction(c, c['actual'], frozen, baseline, t)) for t in range(35, 120, 5)])
        weight = 1/math.sqrt(len(y)*len(cases))
        xs.append(x*weight); ys.append(y*weight)
    x = np.vstack(xs); y = np.concatenate(ys)
    norms = np.linalg.norm(x, axis=0)
    singular = np.linalg.svd(x/np.maximum(norms, 1e-30), compute_uv=False)
    if min(norms) < 1e-12 or np.linalg.matrix_rank(x) != x.shape[1]:
        raise ValueError('unidentified candidate coefficient')
    if name == 'AP_DELAY':
        coefficients = thermal.nnls2(x, y)
    elif name == 'AP_SIMPLE':
        coefficients = np.array([max(0., float(x[:, 0]@y/(x[:, 0]@x[:, 0])))])
    else:
        coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
    result.update(scaled_singular_values=singular.tolist(), numerical_rank=x.shape[1],
                  training_session_equal_rmse=float(np.sqrt(np.sum((x@coefficients-y)**2))),
                  practical_identification='not established by rank; three confounded sessions')
    if name.startswith('AP_'):
        result.update(k=float(coefficients[0]), g=float(coefficients[1]) if len(coefficients)>1 else 0.)
    else:
        result['alpha'] = float(coefficients[0])
    return result


def extract(external, output):
    """Only reads recorded artifacts; shared export contains no device/session UUID."""
    external = Path(external); output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    if sha(MODEL) != MODEL_SHA:
        raise ValueError('frozen model changed')
    frozen = read(MODEL); source_files = {}; cases = []; audits = []
    def source(path):
        source_files[str(Path(path).relative_to(external))] = sha(path)
        return read(path)
    for role in ('development', 'confirmation'):
        raw = source(external/'separated_power_run_v4'/f'{role}_cases.json')
        old = source(external/'separated_power_run_v4'/f'{role}_evaluation.json')
        for i, c in enumerate(raw):
            cases.append((f'{role}_{i}', role, c, old[i], role, i))
    plan_file = external/'sustained_confirmation_plan_v1/collection_plan.json'
    plan = source(plan_file)
    # No preflight, commands, launch or collection entry point is invoked.
    for e in plan['entries']:
        folder = Path(plan['output_root'])/f"{e['index']:02d}_{e['session_id']}"
        for f in ['validated.json', 'thermal.jsonl', 'artifacts/progress.jsonl',
                  'artifacts/requests.json', 'artifacts/manifest.json',
                  'artifacts/common_boundary.json', 'artifacts/cleanup.json',
                  'artifacts/start_ap.accepted.json']:
            source_files[str((folder/f).relative_to(external))] = sha(folder/f)
        c = base.load_case(plan_file, plan, e)
        c['preload_power_w'] = base.energy_at(c, -20, 30)/50
        cases.append((f"sustained_{e['index']}", 'evaluation', c, None, 'sustained', e['index']))
    portable = []; old_metrics = list(csv.DictReader((MODEL.parent/'metrics.csv').open(encoding='utf8')))
    for label, role, c, old, block, index in cases:
        initial = dict(preload=c['inputs']['preload'], preload_power_w=c['preload_power_w'])
        planning = 'sustained-confirmation-v1' if block == 'sustained' else c['study_phase']
        _, forecast = base.forecast(initial, c['manifest_requests'], c['policy'], frozen, planning_input_role=planning)
        end = c['inputs']['segments'][-1]['end_s']
        if forecast[-1]['end_s'] <= 120:
            forecast.append(dict(start_s=120., end_s=end, state='idle'))
        power = sorted(c['power_samples'], key=lambda s:s['mono_ns'])
        t = [(s['mono_ns']-c['origin_ns'])/1e9 for s in power]
        watts = [base.energy.discharge_w(s, 1000) for s in power]
        item = dict(id=label, role='development' if role=='development' else 'evaluation',
                    block=block, index=index, policy=c['policy'], pre=c['inputs']['preload'],
                    pre_w=c['preload_power_w'], q=c['inputs']['query_s'], ap=c['observed_ap_c'],
                    actual=c['inputs']['segments'], forecast=forecast, power_t=t, power_w=watts,
                    last_lane_s=c['last_lane_s'], common_start_ap_c=c['common_start_ap_c'])
        diff = integral(item, 0, 120)-c['observed_120s_j']
        if abs(diff) > 1e-6 or abs(integral(item, -20, 30)/50-item['pre_w']) > 1e-9:
            raise ValueError('raw energy/preload mismatch')
        gaps = np.diff(t); inside = [(a,b) for a,b in zip(t,t[1:]) if a<120 and b>0]
        pgaps = [b-a for a,b in inside]
        q = item['q']; frozen_outputs = {}
        for mode, seg in [('actual_schedule_conditional', item['actual']), ('arrival_forecast', forecast)]:
            pred, init = predict(item, seg, frozen, dict(name='FROZEN'))
            j = energy_prediction(item, seg, frozen, dict(name='FROZEN'), 120)
            if old:
                expected = old['outputs'][mode]
                mismatch = max(abs(j-expected['whole_120s_j']), float(np.max(np.abs(np.array(pred)-expected['ap_path']))))
            else:
                expected = next(r for r in old_metrics if int(r['index'])==index and r['prediction']==mode)
                score = base.common.score(item['ap'], pred)
                mismatch = max(abs(j-float(expected['predicted_120s_j'])),abs(score['mae_c']-float(expected['mae_c'])))
            if mismatch > 1e-6:
                raise ValueError('old prediction mismatch '+label)
            frozen_outputs[mode] = dict(whole_j=j, ap=pred)
        item['frozen_reference'] = frozen_outputs
        common_power = [(s,w) for s,w in zip(power,watts) if c['origin_ns']<=s['mono_ns']<=c['origin_ns']+120e9]
        audit = dict(id=label, power_samples=len(common_power), power_median_s=float(np.median(pgaps)),
            power_max_gap_s=max(pgaps), ap_samples=len(q), ap_median_s=float(np.median(np.diff(q))),
            ap_max_gap_s=max(np.diff(q)), ap_bracket_max_s=max(p['hi']-p['lo'] for p in item['pre']),
            ap_window_start_s=q[0], ap_window_end_s=q[-1], integral_reproduction_delta_j=diff,
            repeated_power_pairs=sum(a[1]==b[1] for a,b in zip(common_power,common_power[1:])),
            repeated_ap_pairs=sum(a==b for a,b in zip(item['ap'],item['ap'][1:])),
            actual_overlap_s=float(base.exposure(item['actual'],0,120)[3]),
            input_power_missing=sum(w is None for s,w in common_power), frozen_reproduced=True)
        for r in c['rows']:
            times=[r[k] for k in base.FIELDS]
            if times != sorted(times):
                raise ValueError('request boundary ordering')
        audits.append(audit); portable.append(item)
    write(output/'inputs.json', portable); table(output/'data_audit.csv', audits)
    write(output/'source_inventory.json',dict(external_root_alias='D1Check_Arrival_Extension',files=source_files,
        frozen_model_sha256=MODEL_SHA, observations='raw mA conditional; no absolute accuracy certification',device_commands=0))
    if any(sha(external/f)!=h for f,h in source_files.items()):
        raise ValueError('source mutated')
    return dict(cases=len(portable), frozen_reproduced=len(portable)*2, device_commands=0)


def audit_cached_raw(external, output):
    """Cross-check the nine cached cases against their original recovered records."""
    root=Path(external);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    folders=[]
    for run in ('separated_power_run_v1','separated_power_run_v2','separated_power_run_v4'):
        for phase in ('development','confirmation'):
            if (root/run/phase).is_dir():folders.extend((root/run/phase).glob('*_*'))
    rows=[];files={}
    for role in ('development','confirmation'):
        for index,c in enumerate(read(root/'separated_power_run_v4'/f'{role}_cases.json')):
            session=c['power_samples'][0]['session_id']
            matches=[f for f in folders if f.name.endswith(session)]
            if len(matches)!=1:raise ValueError('raw folder unavailable or ambiguous')
            folder=matches[0]
            for name in ('artifacts/progress.jsonl','artifacts/requests.json','artifacts/common_boundary.json','thermal.jsonl'):
                path=folder/name;files[str(path.relative_to(root))]=sha(path)
            origin=read(folder/'artifacts/common_boundary.json')['start_ns']
            if origin!=c['origin_ns']:raise ValueError('origin mismatch')
            events=[json.loads(line) for line in (folder/'artifacts/progress.jsonl').read_text(encoding='utf8').splitlines() if line]
            samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2) for e in events if e.get('kind')=='power_sample']
            if samples!=c['power_samples']:raise ValueError('cached power mismatch')
            requests=read(folder/'artifacts/requests.json')
            if len(requests)!=len(c['rows']):raise ValueError('raw denominator mismatch')
            for a,b in zip(requests,c['rows']):
                for key in base.FIELDS+('scheduled_arrival_ns','actual_arrival_ns'):
                    if a[key]-origin!=b[key]:raise ValueError('raw request clock mismatch')
            th=[json.loads(line) for line in (folder/'thermal.jsonl').read_text(encoding='utf8').splitlines() if line]
            known={(r['mono_ns']-origin)/1e9:r for r in th if r.get('AP') not in ('',None)}
            brackets=[]
            for t,y in zip(c['inputs']['query_s'],c['observed_ap_c']):
                r=known[t]
                if float(r['AP'])!=y or not r['before_ns']<=r['mono_ns']<=r['after_ns']:raise ValueError('raw AP mismatch')
                brackets.append((r['after_ns']-r['before_ns'])/1e9)
            rows.append(dict(id=f'{role}_{index}',requests=len(requests),power_samples=len(samples),
                ap_samples=len(brackets),max_ap_query_bracket_s=max(brackets),raw_cache_equal=True))
    if any(sha(root/f)!=h for f,h in files.items()):raise ValueError('raw mutation')
    write(out/'raw_cache_audit.json',dict(sessions=rows,files=files,device_commands=0))
    return dict(raw_cache_equal_sessions=len(rows),device_commands=0)


def metrics(c, seg, frozen, candidate):
    pred, init = predict(c, seg, frozen, candidate)
    score = base.common.score(c['ap'], pred)
    ej = energy_prediction(c, seg, frozen, candidate, 120)-integral(c,0,120)
    row = dict(observed_j=integral(c,0,120), predicted_j=ej+integral(c,0,120), signed_j=ej,
               abs_j=abs(ej), relative_error=ej/integral(c,0,120), **score)
    residual=[]
    for a in range(0,120,5):
        residual.append(energy_prediction(c,seg,frozen,candidate,a+5)-energy_prediction(c,seg,frozen,candidate,a)-integral(c,a,a+5))
    row.update(positive_bins_j=sum(max(0,x) for x in residual), negative_bins_j=sum(min(0,x) for x in residual),
               sum_abs_bins_j=sum(abs(x) for x in residual))
    for key,a,b in [('pre',0,35),('load',35,c['last_lane_s']),('post',c['last_lane_s'],120)]:
        row[key+'_signed_j']=energy_prediction(c,seg,frozen,candidate,b)-energy_prediction(c,seg,frozen,candidate,a)-integral(c,a,b)
        ix=[i for i,t in enumerate(c['q']) if a<=t<=b]
        row[key+'_ap_mae_c']=float(np.mean([abs(pred[i]-c['ap'][i]) for i in ix])) if ix else None
    ix=[i for i,t in enumerate(c['q']) if t>=c['last_lane_s']]
    row['whole_cooling_ap_mae_c']=float(np.mean([abs(pred[i]-c['ap'][i]) for i in ix])) if ix else None
    if abs(sum(row[k+'_signed_j'] for k in ('pre','load','post'))-ej)>1e-7:
        raise ValueError('energy partition')
    for label,a,b in [('load',35,c['last_lane_s']),('cooling',c['last_lane_s'],c['q'][-1])]:
        ix=[i for i,t in enumerate(c['q']) if a<=t<=b]
        if len(ix)<2:
            row[label+'_observed_change_c']=row[label+'_predicted_change_c']=row[label+'_opposite']=None
        else:
            dy=c['ap'][ix[-1]]-c['ap'][ix[0]]; dp=pred[ix[-1]]-pred[ix[0]]
            row.update({label+'_observed_change_c':dy,label+'_predicted_change_c':dp,
                        label+'_opposite':bool(abs(dy)>.100000001 and dy*dp < -1e-12)})
    return row,pred,init


def analyze(inputs, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    cases=read(inputs);frozen=read(MODEL)
    if sha(MODEL)!=MODEL_SHA:raise ValueError('model hash')
    development=[c for c in cases if c['role']=='development']
    if len(development)!=3 or len(cases)!=17 or len({c['id'] for c in cases})!=17:raise ValueError('session denominator')
    candidates={n:fit(development,frozen,n) for n in NAMES}
    folds=[]
    for c in development:
        train=[d for d in development if d['id']!=c['id']]
        for name in NAMES:
            candidate=fit(train,frozen,name)
            score,_,_=metrics(c,c['actual'],frozen,candidate)
            folds.append(dict(id=c['id'],candidate=name,ap_mae_c=score['mae_c'],energy_abs_j=score['abs_j'],
                              fit_coefficients=json.dumps(candidate,sort_keys=True)))
    selected={}
    for field,names in [('ap_mae_c',['FROZEN','AP_SIMPLE','AP_DELAY']),('energy_abs_j',['FROZEN','E_TREND'])]:
        refs={r['id']:r[field] for r in folds if r['candidate']=='FROZEN'}
        eligible=[n for n in names if all(r[field]<=refs[r['id']]+1e-12 for r in folds if r['candidate']==n)]
        selected[field]=min(eligible,key=lambda n:(sum(r[field] for r in folds if r['candidate']==n),names.index(n)))
    write(output/'candidates.json',dict(models=candidates,development_only_selection=selected,
        frozen_model_sha256=MODEL_SHA,contract_sha256=sha(BUNDLE/'contract.json'),selection_before_evaluation=True))
    rows=[];paths=[];windows=[];failures=[];initial=[]
    for c in cases:
        for mode,key in [('A_conditional','actual'),('B_arrival','forecast')]:
            seg=c[key]
            for name,candidate in candidates.items():
                common=dict(id=c['id'],role=c['role'],block=c['block'],policy=c['policy'],mode=mode,candidate=name,last_lane_s=c['last_lane_s'])
                try:score,pred,init=metrics(c,seg,frozen,candidate)
                except ValueError as e:
                    failures.append(dict(**common,error=str(e)));rows.append(dict(**common,status='unavailable'));continue
                rows.append(dict(**common,status='calculated_posthoc',**score))
                if mode=='A_conditional':initial.append(dict(id=c['id'],candidate=name,**init))
                for t,y,v in zip(c['q'],c['ap'],pred):
                    paths.append(dict(**common,kind='AP',t=t,observed=y,predicted=v,residual=v-y))
                for t in range(121):
                    y=integral(c,0,t);v=energy_prediction(c,seg,frozen,candidate,t)
                    paths.append(dict(**common,kind='J',t=t,observed=y,predicted=v,residual=v-y))
                for a in range(0,120,5):
                    states=sorted({s['state'] for s in c['actual'] if min(a+5,s['end_s'])>max(a,s['start_s'])})
                    obs=integral(c,a,a+5);pr=energy_prediction(c,seg,frozen,candidate,a+5)-energy_prediction(c,seg,frozen,candidate,a)
                    windows.append(dict(**common,start_s=a,end_s=a+5,states='|'.join(states),mixed=len(states)>1,observed_j=obs,predicted_j=pr,signed_j=pr-obs))
    table(output/'session_errors.csv',rows);table(output/'paths.csv',paths);table(output/'windows.csv',windows)
    table(output/'development_loso.csv',folds);write(output/'initial_states.json',initial);write(output/'unavailable.json',failures)
    aggregates=[]
    for block in ('development','confirmation','sustained'):
        for mode in ('A_conditional','B_arrival'):
            refs={r['id']:r for r in rows if r['block']==block and r['mode']==mode and r['candidate']=='FROZEN' and 'abs_j' in r}
            for name in NAMES:
                use=[r for r in rows if r['block']==block and r['mode']==mode and r['candidate']==name and 'abs_j' in r]
                aggregates.append(dict(block=block,mode=mode,candidate=name,n=len(use),
                    energy_mae_j=float(np.mean([r['abs_j'] for r in use])) if use else None,
                    ap_mae_c=float(np.mean([r['mae_c'] for r in use])) if use else None,
                    worst_ap_error_c=max((r['max_absolute_error_c'] for r in use),default=None),
                    energy_worse_sessions=sum(r['abs_j']>refs[r['id']]['abs_j']+1e-10 for r in use),
                    ap_worse_sessions=sum(r['mae_c']>refs[r['id']]['mae_c']+1e-10 for r in use),
                    cooling_opposite_sessions=sum(r['cooling_opposite'] is True for r in use)))
    table(output/'comparison.csv',aggregates)
    table(output/'condition_comparison.csv',condition_summary(rows))
    pairs=[]
    for pair in range(4):
        ids={c['policy']:c['id'] for c in cases if c['block']=='sustained' and c['index']//2==pair}
        for mode in ('A_conditional','B_arrival'):
            for name in NAMES:
                use={r['id']:r for r in rows if r['mode']==mode and r['candidate']==name and 'abs_j' in r}
                a,b=[use.get(ids[k]) for k in ('CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1')]
                if a is None or b is None:continue
                pairs.append(dict(pair=pair,mode=mode,candidate=name,observed_delta_j=b['observed_j']-a['observed_j'],
                    predicted_delta_j=b['predicted_j']-a['predicted_j'],difference_error_j=b['signed_j']-a['signed_j'],
                    peak_difference_error_c=b['peak_signed_error_c']-a['peak_signed_error_c'],
                    causal_policy_effect=False))
    table(output/'paired_errors.csv',pairs)
    write(output/'summary.json',dict(selection=selected,development_sessions=3,evaluation_sessions=14,
        evaluation_blocks=['confirmation6','sustained8_four_pairs'],candidate_structures=3,
        device_commands=0,rl_training=0,posthoc=True,accuracy_pass=None,experiment_ready=False,
        input_sha256=sha(inputs),model_sha256=sha(MODEL),failures=len(failures)))
    plot(output)
    return read(output/'summary.json')


def plot(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=Path(output)
    path=output/'paths.csv'
    with (path.open(encoding='utf8') if path.exists() else gzip.open(output/'paths.csv.gz','rt',encoding='utf8')) as f:
        rows=list(csv.DictReader(f))
    colors=dict(FROZEN='#c44735',AP_SIMPLE='#1775b5',AP_DELAY='#369346',E_TREND='#8556a6')
    links=[]
    for block in ('confirmation','sustained'):
        ids=list(dict.fromkeys(r['id'] for r in rows if r['block']==block))
        fig,axes=plt.subplots(len(ids),4,figsize=(16,2.5*len(ids)),squeeze=False,constrained_layout=True)
        for i,identity in enumerate(ids):
            for j,(kind,names) in enumerate([('J',['FROZEN','E_TREND']),('AP',['FROZEN','AP_SIMPLE','AP_DELAY']),('J',['FROZEN','E_TREND']),('AP',['FROZEN','AP_SIMPLE','AP_DELAY'])]):
                ax=axes[i,j]
                for n in names:
                    values=[r for r in rows if r['id']==identity and r['mode']=='A_conditional' and r['kind']==kind and r['candidate']==n]
                    if not values:continue
                    x=[float(r['t']) for r in values]
                    if n=='FROZEN' and j<2:ax.plot(x,[float(r['observed']) for r in values],color='black',label='Observed')
                    ax.plot(x,[float(r['residual' if j>=2 else 'predicted']) for r in values],color=colors[n],label=n)
                    if n=='FROZEN':ax.axvspan(35,float(values[0]['last_lane_s']),color='grey',alpha=.1)
                ax.set(title=identity+' / '+(('residual '+kind) if j>=2 else kind),xlabel='Common seconds')
                if j>=2:ax.axhline(0,color='black',lw=.5)
                ax.axvline(35,color='grey',ls=':',lw=.8);ax.grid(alpha=.2);ax.legend(fontsize=6)
        name=block+'_conditional.png';fig.savefig(output/name,dpi=115);plt.close(fig);links.append(name)
    errors=list(csv.DictReader((output/'session_errors.csv').open(encoding='utf8')))
    fig,axes=plt.subplots(2,1,figsize=(13,7),constrained_layout=True)
    ids=list(dict.fromkeys(r['id'] for r in errors if r['role']=='evaluation'))
    for ax,field,names in [(axes[0],'abs_j',['FROZEN','E_TREND']),(axes[1],'mae_c',['FROZEN','AP_SIMPLE','AP_DELAY'])]:
        for j,n in enumerate(names):
            use={r['id']:r for r in errors if r['mode']=='A_conditional' and r['candidate']==n}
            ax.plot(range(len(ids)),[float(use[i][field]) if use[i].get(field) else np.nan for i in ids],'.-',color=colors[n],label=n)
        ax.set_xticks(range(len(ids)),ids,rotation=30,ha='right');ax.set_ylabel(field);ax.legend();ax.grid(alpha=.2)
    fig.savefig(output/'session_comparison.png',dpi=130);plt.close(fig);links.append('session_comparison.png')
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>기존 실측 모형 후보</title><style>body{font:16px system-ui;margin:30px;max-width:1400px}img{width:100%}</style><h1>기존 실측의 사후 모형 후보 평가</h1><p>개발3 / 평가6+8. 그림은 실제 일정 조건부 A. B 도착예측은 CSV에서 별도 판독. 기존 동결본·RL 기본값 불변. 절대 에너지 미인증·정확도 PASS 없음.</p><p><a href="../../MODEL_REFINEMENT_EXISTING_DATA_20261007.md">한국어 판정</a> · <a href="session_errors.csv">세션별 A/B</a> · <a href="comparison.csv">후보 비교</a> · <a href="paired_errors.csv">짝 차이 오차</a> · <a href="development_loso.csv">개발 세션 제외</a> · <a href="windows.csv">5초 혼합 구간·상쇄</a></p>'+''.join('<img src="'+x+'">' for x in links),encoding='utf8')


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['extract','analyze','plot','audit-raw'])
    p.add_argument('--external');p.add_argument('--inputs');p.add_argument('--output',required=True)
    args=p.parse_args()
    result=(extract(args.external,args.output) if args.action=='extract' else
            audit_cached_raw(args.external,args.output) if args.action=='audit-raw' else
            analyze(args.inputs,args.output) if args.action=='analyze' else plot(args.output))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
