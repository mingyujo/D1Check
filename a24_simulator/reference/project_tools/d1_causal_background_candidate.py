"""One registered, retrospective background/AP candidate. PC only, no device I/O.

Power already observed before issuance is an input, never the forecast target.
The six old confirmation sessions are post-hoc evaluation, not a new holdout.
"""
import argparse
import copy
import csv
import hashlib
import html
import json
import math
from pathlib import Path

import numpy as np
from tools import d1_online_policy_model as old
from tools import d1_energy_thermal as energy
from tools import d1_ap_completion_model as ap
from tools import d1_ap_model_completion as scoring
from tools import d1_arrival_policy_screen as screen

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT/'docs/results/online_policy_study_01/causal_background_pc_v1/analysis_contract.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write(path, value):
    # Explicit newline matches the registered Windows bundle on every platform.
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                          encoding='utf8', newline='\r\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_write(path, rows):
    with Path(path).open('w', encoding='utf8', newline='') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def task_j(segments, model, a, b):
    return float(old.exposure(segments, a, b) @ np.array([model['energy_increment_w'][k] for k in old.STATES]))


def integral(samples, a, b, *, available_at=None, max_gap=2.5):
    """Exact clipped trapezoids. Filtering uses record availability, not midpoint."""
    if not math.isfinite(a+b) or b <= a:
        raise ValueError('invalid integration boundary')
    rows = [s for s in samples if available_at is None or s['ready_s'] <= available_at]
    total = covered = 0.
    for x, y in zip(rows, rows[1:]):
        if y['t_s'] <= x['t_s']:
            raise ValueError('unordered or duplicate power sample')
        lo, hi = max(a, x['t_s']), min(b, y['t_s'])
        if hi <= lo:
            continue
        dt = y['t_s']-x['t_s']
        if (dt > max_gap or x['w'] is None or y['w'] is None
                or not math.isfinite(x['w']) or not math.isfinite(y['w'])):
            continue
        p0 = x['w']+(y['w']-x['w'])*(lo-x['t_s'])/dt
        p1 = x['w']+(y['w']-x['w'])*(hi-x['t_s'])/dt
        total += (p0+p1)*(hi-lo)/2; covered += hi-lo
    return total if abs(covered-(b-a)) < 1e-6 else None


def residual_at(case, model, issue, cfg):
    """Read only the already-published sample and lane prefix."""
    rows = [s for s in case['power'] if s['ready_s'] <= issue]
    if not rows or issue-rows[-1]['ready_s'] > cfg['latest_sample_max_age_s']:
        return dict(issue_s=issue, r_w=None, reason='missing_or_stale_power')
    last = rows[-1]; b = last['t_s']; a = b-cfg['lookback_s']
    if not a <= b <= last['ready_s'] <= issue:
        raise ValueError('power clock or future endpoint')
    value = integral(rows, a, b, max_gap=cfg['power_gap_limit_s'])
    if value is None:
        return dict(issue_s=issue, r_w=None, reason='incomplete_power_window')
    increment = task_j(case['actual_segments'], model, a, b)/(b-a)
    residual = value/(b-a)-increment-case['preload_w']
    return dict(issue_s=issue, r_w=residual, reason=None, window_start_s=a, window_end_s=b,
                latest_record_s=last['ready_s'], read_age_s=issue-last['ready_s'],
                mean_observed_w=value/(b-a), mean_task_increment_w=increment)


def updates(case, model, cfg, end=180):
    return [residual_at(case, model, float(t), cfg)
            for t in range(cfg['start_s'], math.ceil(end), cfg['update_period_s'])]


def advance(z, r, beta, dt):
    if not all(math.isfinite(x) for x in (z, r, beta, dt)) or beta <= 0 or dt < 0:
        raise ValueError('invalid correction state')
    decay = math.exp(-beta*dt)
    return z*decay+r*(-math.expm1(-beta*dt))/beta


def correction_at(rows, query, beta, start=35):
    if query < start:
        raise ValueError('query precedes correction initialization')
    z = 0.
    for i, row in enumerate(rows):
        a = row['issue_s']
        if a >= query:
            break
        b = min(query, rows[i+1]['issue_s'] if i+1 < len(rows) else query)
        if row['r_w'] is None:
            return None
        z = advance(z, row['r_w'], beta, b-a)
    if query > start and (not rows or rows[0]['issue_s'] != start):
        raise ValueError('missing initial correction interval')
    return z


def base_ap(case, model, query, schedule):
    # Whitelist: pre-load AP only. No observed post-load AP/power is passed.
    return ap.predict(dict(inputs=dict(preload=case['preload'], query_s=query,
                                      segments=case[schedule])), model['ap'])[0]


def fit(cases, model, cfg):
    if not cases or any(c['role'] != 'development' for c in cases):
        raise ValueError('development-only coefficient fit')
    rows = []
    for c in cases:
        rs = updates(c, model, cfg)
        z = [correction_at(rs, t, model['ap']['beta'], cfg['start_s']) for t in c['query_s']]
        if any(x is None for x in z):
            raise ValueError('incomplete development inputs; no selected target subset')
        x = np.array(z); y = np.array(c['observed_ap'])-base_ap(c, model, c['query_s'], 'actual_segments')
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError('nonfinite development inputs/targets; no selected subset')
        information = float(np.mean(x*x)); cross = float(np.mean(x*y))
        rows.append(dict(id=c['id'], samples=len(x), information=information, cross=cross,
                         unconstrained_gamma=cross/information if information > 1e-12 else None,
                         r_min_w=min(r['r_w'] for r in rs), r_max_w=max(r['r_w'] for r in rs),
                         unit_gain_basis_rms=float(np.sqrt(information))))
    info = sum(r['information'] for r in rows); cross = sum(r['cross'] for r in rows)
    g = cross/info if info > 1e-12 else None
    return dict(gamma=None if g is None else max(0., g), unconstrained_gamma=g,
                numerical_rank=int(info > 1e-12), total_equal_session_information=info,
                sessions=rows, inference='session sensitivity, not an IID sample confidence interval')


def issued_forecast(case, model, gamma, cfg, issue, horizon):
    """Fixed future planned schedule, causal correction, frozen entire horizon."""
    if gamma is None or not math.isfinite(gamma) or gamma < 0:
        raise ValueError('unidentified/invalid gamma')
    if horizon not in cfg['horizons_s'] or (issue-cfg['start_s']) % cfg['update_period_s']:
        raise ValueError('unregistered forecast issuance')
    past = updates(case, model, cfg, end=issue+1)
    z = correction_at(past, issue, model['ap']['beta'], cfg['start_s'])
    r = past[-1]
    if z is None or r['r_w'] is None:
        return dict(issue_s=issue, horizon_s=horizon, status='missing_inputs', reason=r['reason'],
                    predicted_ap_c=None, predicted_j=None)
    end = issue+horizon
    baseline = base_ap(case, model, [end], 'forecast_segments')[0]
    corrected = baseline+gamma*advance(z, r['r_w'], model['ap']['beta'], horizon)
    background = case['preload_w']+r['r_w']
    fixed_j = case['preload_w']*horizon+task_j(case['forecast_segments'], model, issue, end)
    candidate_j = None if background < 0 else fixed_j+r['r_w']*horizon
    return dict(issue_s=issue, horizon_s=horizon, status='predicted', input_cutoff_s=issue,
                latest_power_record_s=r['latest_record_s'], power_window_end_s=r['window_end_s'],
                r_w=r['r_w'], correction_at_issue_per_gamma=z,
                predicted_ap_c=corrected, frozen_ap_c=baseline,
                predicted_j=candidate_j, frozen_j=fixed_j,
                energy_status='negative_inferred_background' if background < 0 else 'computed',
                future_r_assumption='hold last available', post_start_ap_feedback=False,
                future_schedule='stored forecast, not realized future or re-scheduled queue')


def export_bundle(source, output, cfg):
    """Strip IDs/large logs, preserve exact sample publication timing and model."""
    source, output = Path(source), Path(output)
    if digest(source/'model_freeze.json') != cfg['source_freeze_sha256']:
        raise ValueError('wrong frozen model')
    frozen = read(source/'model_freeze.json')['model']; plan = read(source/'frozen_study_plan.json')
    folders = list((source/'development').glob('??_*'))+list((source/'confirmation').glob('??_*'))
    for imported in plan['imported_development']:
        prior = read(imported['plan']); i = imported.get('index', 0); e = prior['entries'][i]
        folders.append(Path(prior['output_root'])/f"{i:02d}_{e['session_id']}")
    by_phase = {read(f/'artifacts/manifest.json')['phase']:f for f in folders}
    evidence = {str((source/f).relative_to(source.parent)):digest(source/f)
                for f in ('model_freeze.json','development_cases.json','confirmation_cases.json',
                          'development_evaluation.json','confirmation_evaluation.json')}
    cases = []
    for role in ('development','confirmation'):
        evaluation = {r['id']:r for r in read(source/(role+'_evaluation.json'))}
        for c in read(source/(role+'_cases.json')):
            folder = by_phase[c['id']]; f = folder/'artifacts/progress.jsonl'
            events = [json.loads(x) for x in f.read_text(encoding='utf8').splitlines() if x]
            raw = [e for e in events if e['kind']=='power_sample']; origin = c['origin_ns']
            midpoint = [dict(e, mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2) for e in raw]
            if midpoint != c['power_samples']:
                raise ValueError('raw power/cached case mismatch')
            evidence[str(f.relative_to(source.parent)).replace('\\','/')] = digest(f)
            e = evaluation[c['id']]
            future = screen.occupancy(dict(ledger=e['forecast_ledger']), 'stored', 1, 201, c['policy'])
            future = [{k:s[k] for k in ('start_s','end_s','state')} for s in future]
            end = c['inputs']['segments'][-1]['end_s']; future.append(dict(start_s=120.,end_s=end,state='idle'))
            power = [dict(t_s=(v['mono_ns']-origin)/1e9, ready_s=(r['mono_ns']-origin)/1e9,
                          w=energy.discharge_w(v, cfg['power_unit_hypothesis_uA_per_raw'])) for r,v in zip(raw,midpoint)]
            if any(s['ready_s'] < s['t_s'] for s in power):
                raise ValueError('publication before sensor midpoint')
            row = dict(id=c['id'],role=role,policy=c['policy'],preload=c['inputs']['preload'],
                       preload_w=c['preload_power_w'],power=power,actual_segments=c['inputs']['segments'],
                       forecast_segments=future,query_s=c['inputs']['query_s'],observed_ap=c['observed_ap_c'],
                       observed_120s_j=c['observed_120s_j'],last_lane_s=c['last_lane_s'],
                       frozen_conditional_ap=e['outputs']['actual_schedule_conditional']['ap_path'],
                       frozen_forecast_ap=e['outputs']['arrival_forecast']['ap_path'])
            if abs(integral(power, 0, 120)-c['observed_120s_j']) > 1e-6:
                raise ValueError('common energy mismatch')
            if not np.allclose(base_ap(row,frozen,row['query_s'],'actual_segments'),row['frozen_conditional_ap'],atol=1e-10,rtol=0):
                raise ValueError('frozen conditional AP changed')
            if not np.allclose(base_ap(row,frozen,row['query_s'],'forecast_segments'),row['frozen_forecast_ap'],atol=1e-10,rtol=0):
                raise ValueError('stored forecast AP mismatch')
            cases.append(row)
    output.mkdir(parents=True,exist_ok=False)
    write(output/'inputs.json',cases)
    write(output/'model.json',frozen)
    write(output/'source_hashes.json',evidence)
    write(output/'resources.json',dict(files={n:digest(output/n) for n in ('inputs.json','model.json','source_hashes.json')},
                                      source_freeze_sha256=cfg['source_freeze_sha256']))
    return dict(cases=len(cases), device_commands=0)


def analyze(bundle, output, cfg):
    bundle, output = Path(bundle), Path(output)
    resources = read(bundle/'resources.json')
    if resources['source_freeze_sha256'] != cfg['source_freeze_sha256']:
        raise ValueError('freeze identity')
    for name, sha in resources['files'].items():
        if Path(name).name != name or digest(bundle/name) != sha:
            raise ValueError('bundle drift')
    cases = read(bundle/'inputs.json'); model = read(bundle/'model.json')
    dev = [c for c in cases if c['role']=='development']; confirm = [c for c in cases if c['role']=='confirmation']
    if len(dev)!=3 or len(confirm)!=6 or len({c['id'] for c in cases})!=9:
        raise ValueError('complete registered 3+6 required')
    fitted = fit(dev,model,cfg); gamma = fitted['gamma']
    loso = [dict(excluded=c['id'], **fit([x for x in dev if x['id']!=c['id']],model,cfg)) for c in dev]
    if gamma is None:
        output.mkdir(parents=True,exist_ok=False)
        write(output/'candidate.json',dict(status='unidentified_stop',fit=fitted,loso=loso,
                                          independent_validation_sessions=0,experiment_ready=False))
        return dict(status='unidentified_stop',output=str(output),device_commands=0)
    summaries=[]; curves=[]; rs=[]; forecasts=[]
    for c in cases:
        steps=updates(c,model,cfg); rs += [dict(id=c['id'],role=c['role'],**r) for r in steps]
        z=[correction_at(steps,t,model['ap']['beta'],cfg['start_s']) for t in c['query_s']]
        base=c['frozen_conditional_ap']; corrected=[None if x is None else a+gamma*x for a,x in zip(base,z)]
        complete=all(x is not None for x in corrected)
        old_score=scoring.score(c['observed_ap'],base)
        new_score=scoring.score(c['observed_ap'],corrected) if complete else None
        summaries.append(dict(id=c['id'],role=c['role'],gamma=gamma,complete_candidate_path=complete,
                              frozen_mae_c=old_score['mae_c'],candidate_mae_c=None if not complete else new_score['mae_c'],
                              frozen_max_c=old_score['max_absolute_error_c'],candidate_max_c=None if not complete else new_score['max_absolute_error_c'],
                              frozen_peak_error_c=old_score['peak_signed_error_c'],candidate_peak_error_c=None if not complete else new_score['peak_signed_error_c']))
        for t,y,a,b,x in zip(c['query_s'],c['observed_ap'],base,corrected,z):
            curves.append(dict(id=c['id'],role=c['role'],t_s=t,observed_ap_c=y,frozen_ap_c=a,candidate_ap_c=b,
                               frozen_error_c=a-y,candidate_error_c=None if b is None else b-y,unit_gamma_basis=x))
        for issue in range(cfg['start_s'],180,cfg['update_period_s']):
            for h in cfg['horizons_s']:
                end=issue+h
                if end>c['query_s'][-1]:
                    continue
                f=issued_forecast(c,model,gamma,cfg,issue,h)
                observed=scoring.interpolate(c['query_s'],c['observed_ap'],end)
                f.update(id=c['id'],role=c['role'],observed_ap_c=observed,
                         candidate_ap_error_c=None if f['predicted_ap_c'] is None else f['predicted_ap_c']-observed,
                         frozen_ap_error_c=None if f.get('frozen_ap_c') is None else f['frozen_ap_c']-observed,
                         observed_j=integral(c['power'],issue,end) if end<=120 else None)
                f['candidate_j_error']=None if f['observed_j'] is None or f['predicted_j'] is None else f['predicted_j']-f['observed_j']
                f['frozen_j_error']=None if f['observed_j'] is None or f.get('frozen_j') is None else f['frozen_j']-f['observed_j']
                forecasts.append(f)
    output.mkdir(parents=True,exist_ok=False)
    write(output/'candidate.json',dict(version=cfg['version'],formula=cfg['formula'],fit=fitted,loso=loso,
                                      source_freeze_sha256=cfg['source_freeze_sha256'],contract_sha256=digest(CONTRACT),
                                      independent_validation_sessions=0,default=False,strict_support=False,experiment_ready=False))
    write(output/'forecasts.json',forecasts)
    for name,rows in [('summary.csv',summaries),('ap_paths.csv',curves),('updates.csv',rs)]:
        csv_write(output/name,rows)
    metrics=[]
    for c in cases:
        for h in cfg['horizons_s']:
            rows=[r for r in forecasts if r['id']==c['id'] and r['horizon_s']==h]
            item=dict(id=c['id'],role=c['role'],horizon_s=h,issued_forecasts=len(rows),independent_sessions=1)
            for prefix in ('candidate','frozen'):
                for signal in ('ap','j'):
                    key=prefix+('_ap_error_c' if signal=='ap' else '_j_error')
                    vals=[r[key] for r in rows if r[key] is not None]
                    item[prefix+'_'+signal+'_valid']=len(vals)
                    item[prefix+'_'+signal+'_mae']=float(np.mean(np.abs(vals))) if vals else None
                    item[prefix+'_'+signal+'_max']=max(map(abs,vals)) if vals else None
            metrics.append(item)
    csv_write(output/'horizon_metrics.csv',metrics)
    write(output/'scope.json',dict(post_hoc=True,development_sessions=3,already_seen_evaluation_sessions=6,
                                   new_independent_validation=0,candidate_families=1,device_commands=0,
                                   whole_window_online_prediction=False,default_changed=False,experiment_ready=False))
    return dict(gamma=gamma,unconstrained_gamma=fitted['unconstrained_gamma'],loso_gammas=[x['gamma'] for x in loso],
                output=str(output),device_commands=0)


def report(bundle, output, cfg):
    """One deterministic report of saved candidate, without fitting alternatives."""
    bundle, output = Path(bundle), Path(output)
    if (output/'diagnostics.json').exists():
        raise ValueError('report already exists; use a new analysis directory')
    cases=read(bundle/'inputs.json');model=read(bundle/'model.json');candidate=read(output/'candidate.json')
    def csv_rows(name):
        with (output/name).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))
    summary=csv_rows('summary.csv');horizons=csv_rows('horizon_metrics.csv');curves=csv_rows('ap_paths.csv')
    dev=[c for c in cases if c['role']=='development'];loso=[]
    for c,sensitivity in zip(dev,candidate['loso']):
        if sensitivity['excluded']!=c['id']:raise ValueError('LOSO identity')
        rs=updates(c,model,cfg);g=sensitivity['gamma']
        values=[v+g*correction_at(rs,t,model['ap']['beta']) for v,t in zip(c['frozen_conditional_ap'],c['query_s'])]
        scores=scoring.score(c['observed_ap'],values)
        loso.append(dict(id=c['id'],gamma_excluding_this_session=g,
                         frozen_mae_c=scoring.score(c['observed_ap'],c['frozen_conditional_ap'])['mae_c'],
                         excluded_fit_mae_c=scores['mae_c'],excluded_fit_max_c=scores['max_absolute_error_c']))
    csv_write(output/'loso.csv',loso)
    information=candidate['fit']['sessions'];cross=sum(x['cross'] for x in information)
    dev_r=[r['r_w'] for c in dev for r in updates(c,model,cfg)]
    future_r=[r['r_w'] for c in cases if c['role']=='confirmation' for r in updates(c,model,cfg)]
    aggregates=[]
    for horizon in (10,30):
        rows=[r for r in horizons if r['role']=='confirmation' and int(r['horizon_s'])==horizon]
        aggregates.append(dict(horizon_s=horizon,sessions=len(rows),
            **{key:float(np.mean([float(r[key]) for r in rows])) for key in
               ('frozen_ap_mae','candidate_ap_mae','frozen_j_mae','candidate_j_mae')}))
    confirm=[r for r in summary if r['role']=='confirmation']
    diagnostics=dict(candidate_status='retrospective_candidate_not_adopted',
        gamma=candidate['fit']['gamma'],gamma_units='degC/(W*s)',
        numerical_rank=candidate['fit']['numerical_rank'],
        gamma_loso_range=[min(r['gamma'] for r in candidate['loso']),max(r['gamma'] for r in candidate['loso'])],
        cpu_cross_product_share=information[0]['cross']/cross,
        development_r_range_w=[min(dev_r),max(dev_r)],already_seen_evaluation_r_range_w=[min(future_r),max(future_r)],
        development_loso_mean_mae_c=float(np.mean([r['excluded_fit_mae_c'] for r in loso])),
        development_original_mean_mae_c=float(np.mean([r['frozen_mae_c'] for r in loso])),
        confirmation_frozen_mean_mae_c=float(np.mean([float(r['frozen_mae_c']) for r in confirm])),
        confirmation_candidate_mean_mae_c=float(np.mean([float(r['candidate_mae_c']) for r in confirm])),
        confirmation_mae_improved_sessions=sum(float(r['candidate_mae_c'])<float(r['frozen_mae_c']) for r in confirm),
        confirmation_sessions=len(confirm),horizons=aggregates,
        new_independent_validation_sessions=0,causal_source_identified=False,accuracy_pass=None,
        experiment_ready=False,device_commands=0,
        decision='numerical fit exists but session influence and mixed prospective error do not justify policy adoption; no second candidate fitted')
    write(output/'diagnostics.json',diagnostics)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,9),constrained_layout=True)
    for c,ax in zip([c for c in cases if c['role']=='confirmation'],axes.flat):
        rows=[r for r in curves if r['id']==c['id']]
        x=[float(r['t_s']) for r in rows]
        for key,label,color in [('observed_ap_c','Observed','#111111'),('frozen_ap_c','Original frozen','#bd5b2d'),
                                ('candidate_ap_c','Causal residual candidate','#2471a3')]:
            ax.plot(x,[float(r[key]) if r[key] else float('nan') for r in rows],label=label,color=color)
        ax.axvline(c['last_lane_s'],color='grey',ls=':',label='Last actual lane release')
        ax.axvline(120,color='grey',ls='--',alpha=.5)
        ax.set(title=c['id'].replace('confirmation_',''),xlabel='Common seconds',ylabel='AP (C)')
        ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.suptitle('Already-seen 6 sessions: post-hoc candidate evaluation, NOT independent validation')
    for ext in ('svg','png'):fig.savefig(output/('ap_comparison.'+ext),dpi=130)
    plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
    last=cases[-1];rs=updates(last,model,cfg)
    axes[0,0].step([r['issue_s'] for r in rs],[r['r_w'] for r in rs],where='post',label='Last CPU: available power residual')
    axes[0,0].axhspan(min(dev_r),max(dev_r),alpha=.15,label='Development signal range')
    axes[0,0].set(xlabel='Common seconds',ylabel='Residual W');axes[0,0].legend(fontsize=7)
    rows=[r for r in curves if r['id']==last['id']]
    for key,label in [('frozen_error_c','Original'),('candidate_error_c','Candidate')]:
        axes[0,1].plot([float(r['t_s']) for r in rows],[float(r[key]) for r in rows],label=label)
    axes[0,1].axhline(0,color='grey');axes[0,1].set(xlabel='Common seconds',ylabel='Last CPU signed AP error (C)');axes[0,1].legend()
    for ax,h in zip(axes[1],(10,30)):
        rows=[r for r in horizons if r['role']=='confirmation' and int(r['horizon_s'])==h]
        x=np.arange(len(rows))
        ax.bar(x-.18,[float(r['frozen_j_mae']) for r in rows],.36,label='Original')
        ax.bar(x+.18,[float(r['candidate_j_mae']) for r in rows],.36,label='Past power held constant')
        ax.set(xticks=x,xticklabels=['CPU1','PAR1','SER1','SER2','PAR2','CPU2'],ylabel=f'{h}s future interval MAE (J)')
        ax.legend(fontsize=8)
    fig.suptitle('No future AP feedback; horizon errors are not whole-120s errors')
    for ext in ('svg','png'):fig.savefig(output/('causal_limits.'+ext),dpi=130)
    plt.close(fig)
    for path in output.glob('*.svg'):
        path.write_text('\n'.join(s.rstrip() for s in path.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    table='<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in summary[0])+'</tr>'
    for row in summary:table+='<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row.values())+'</tr>'
    table+='</table>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>D1Check 과거 전력 기반 후보</title>'
        '<style>body{font:15px system-ui;margin:28px}td,th{border:1px solid #bbb;padding:5px}table{border-collapse:collapse;font-size:11px}</style>'
        '<h1>기존 자료 기반 단일 후보: 사후 평가·미채택</h1><p>개발3만 적합 / 이미 본 확인6 평가 / 새 독립 확인0. '
        'AP 평균 오차 감소와 계수 안정성·정책 선택 적격성을 구분합니다. 전류 raw=mA 조건부, 절대 정확도 미인증. '
        '실행 이후 AP 피드백 없음. 과거 전력만 사용한 10/30초 예측이며 전체120초의 사전 예측 개선으로 해석하지 않습니다. '
        '기존 동결본·strict·experiment_ready=false 유지.</p><p><a href="../README.md">판정·필요 실측·재현</a> · '
        '<a href="diagnostics.json">판독 수치</a> · <a href="horizon_metrics.csv">미래 구간 오차</a></p>'
        '<img width="100%" src="ap_comparison.svg"><img width="100%" src="causal_limits.svg">'+table,encoding='utf8')
    return diagnostics


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('bundle','analyze','report'))
    parser.add_argument('--source');parser.add_argument('--bundle');parser.add_argument('--output',required=True)
    args=parser.parse_args();cfg=read(CONTRACT)
    if args.action=='bundle':
        if not args.source:parser.error('--source required')
        result=export_bundle(args.source,args.output,cfg)
    else:
        if not args.bundle:parser.error('--bundle required')
        result=(analyze if args.action=='analyze' else report)(args.bundle,args.output,cfg)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
