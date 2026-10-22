"""Registered all-seen measurement-only calibration. No policy simulation."""
import gzip
import hashlib
import json
import os
import time
from pathlib import Path
import numpy as np
from rc_model import features, fit, predict


def read(p):
    p = Path(p)
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_text(encoding='utf-8-sig'))


def save(p, value):
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')
    if str(p).endswith('.gz'):
        raw = gzip.compress(raw, mtime=0)
    with Path(p).open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(op):
    for entry in [*op['source'].values(), *op['inputs'].values()]:
        assert sha(entry['path']) == entry['sha256'], 'Changed pin '+entry['path']


def prepare(op):
    sessions = read(op['inputs']['sessions']['path'])
    rows = read(op['inputs']['old_OOF']['path'])
    by = {s.get('session_uid', s['id']): s for s in sessions}
    power = {r['id']: r for r in rows if r['target'] == 'POWER_API'}
    included, usage = [], []
    for row in rows:
        if row['target'] != 'AP':
            continue
        sid = row['id']
        try:
            assert sid in power, 'Not in original eligible POWER_API OOF'
            s = by[sid]
            anchor = s['targets']['AP']['anchor']
            at = anchor.get('time_s', anchor.get('t_s'))
            AP = anchor.get('AP_c', anchor.get('AP'))
            skin = anchor.get('SKIN_c', anchor.get('SKIN'))
            assert all(v is not None and np.isfinite(v) for v in (at, AP, skin)), 'Missing measured anchor'
            pp = power[sid]
            # Retain measured pre-anchor samples; post-anchor samples are exactly eligible old rows.
            past = [(r['t_s'], r['value_api_w']) for r in s['targets']['POWER_API']['observations']
                    if r['t_s'] < pp['times'][0] and r['value_api_w'] > 0]
            pv = sorted(past + list(zip(pp['times'], pp['observed'])))
            pt, values = map(np.asarray, zip(*pv))
            assert np.all(np.diff(pt) > 0) and pt[0] <= at, 'No measured power bracket for anchor'
            ts = np.asarray(row['times'])
            pw_window = s['targets']['POWER_API'].get('fit_window_s', [0, pt[-1]])
            keep = (ts >= max(at, pw_window[0], pt[0])) & (ts <= min(pt[-1], pw_window[1]))
            assert sum(keep) >= 3, 'Less than three common observed AP/power points'
            ep = dict(id=sid, group=row['group'], pool=row['pool'], cohort=s.get('cohort', row['group']),
                      anchor_s=float(at), anchor_AP=float(AP), skin=float(skin),
                      baseline=float(s['targets']['POWER_API']['baseline']['median_api_w']),
                      times=ts[keep], observed=np.asarray(row['observed'])[keep],
                      parent_OOF=np.asarray(row['predicted'])[keep], power_times=pt, power_values=values)
            assert ep['baseline'] > 0 and np.isfinite(values).all(), 'Invalid baseline or power'
            included.append(ep)
            usage.append(dict(id=sid, status='INCLUDED', points=int(sum(keep)), original_AP_points=len(ts),
                              common_window_s=[float(ts[keep][0]), float(ts[keep][-1])],
                              max_power_gap_s=float(max(np.diff(pt)))))
        except AssertionError as error:
            usage.append(dict(id=sid, status='EXCLUDED', reason=str(error)))
    # Explicitly preserve AP ineligibility too, without promoting old exclusions.
    selected = {u['id'] for u in usage}
    for s in sessions:
        sid = s.get('session_uid', s['id'])
        if sid not in selected:
            usage.append(dict(id=sid, status='EXCLUDED', reason='Not in original AP OOF eligibility'))
    assert len(usage) == len(sessions) and len(selected) == 210
    return included, usage


def serial(ep):
    return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in ep.items() if k != 'features'}


def summary(rows, category, lo=0, hi=float('inf')):
    picked = [r for r in rows if category == 'ALL' or r['pool'] == category or category == 'R21' and r['group'].startswith('M8_R21_')]
    metrics = []
    for r in picked:
        t, obs = np.asarray(r['times']), np.asarray(r['observed'])
        keep = (t >= lo) & (t < hi)
        if not np.any(keep):
            continue
        metrics.append([float(np.mean(abs(np.asarray(r[k])[keep]-obs[keep])))
                        for k in ('predicted', 'parent_OOF', 'anchor_prediction')])
    return dict(category=category, time_bin_s=[lo, hi if np.isfinite(hi) else None], sessions=len(metrics),
                RC_MAE_C=float(np.mean([m[0] for m in metrics])) if metrics else None,
                parent_MAE_C=float(np.mean([m[1] for m in metrics])) if metrics else None,
                anchor_MAE_C=float(np.mean([m[2] for m in metrics])) if metrics else None)


def main(op):
    verify(op)
    out = Path(op['output'])
    entries, usage = prepare(op)
    save(out/'USE_LEDGER.json', usage)
    save(out/'PREPARED.json.gz', [serial(ep) for ep in entries])
    groups = sorted({e['group'] for e in entries})
    assert groups == op['groups'], 'Eligibility changed registered group plan'
    for ep in entries:
        ep['features'] = {tau: features(ep, tau) for tau in op['tau_grid_s']}
    fit_count, rows, profiles, begin = 0, [], [], time.monotonic()
    full = None
    with (out/'FIT_RECEIPTS.jsonl').open('x', encoding='utf-8') as receipt:
        def record(x):
            receipt.write(json.dumps(x)+'\n')
            receipt.flush()
            os.fsync(receipt.fileno())
        for group in groups+[None]:
            verify(op)
            train = [e for e in entries if e['group'] != group] if group else entries
            test = [e for e in entries if e['group'] == group] if group else []
            fitted = []
            for tau in op['tau_grid_s']:
                assert fit_count < op['fit_cap'] and time.monotonic()-begin < op['wall_cap_s'], 'Finite cap'
                identity = (group or 'FULL')+'_tau'+str(tau)
                record(dict(event='START', id=identity, sequence=fit_count+1))
                fit_count += 1
                m = fit(train, tau)
                m.update(id=identity, heldout_group=group, train_ids=[e['id'] for e in train],
                         train_groups=sorted({e['group'] for e in train}), role=op['fit_role'])
                save(out/'models'/(identity+'.json'), m)
                record(dict(event='COMPLETE', id=identity, model_sha256=sha(out/'models'/(identity+'.json'))))
                fitted.append(m)
            selected = min(fitted, key=lambda m: (m['train_MSE'], m['tau_s']))
            profiles.append(dict(heldout_group=group, selected=selected['id'],
                                 profiles=[{k: m[k] for k in ('id','tau_s','delta_C','gain_C_per_API_W','train_MSE','KKT_residual','condition_number')} for m in fitted]))
            for ep in test:
                y = predict(ep, selected)
                assert np.isfinite(y).all()
                rows.append(dict(id=ep['id'], group=ep['group'], pool=ep['pool'], model=selected['id'],
                                 times=ep['times'].tolist(), observed=ep['observed'].tolist(), predicted=y.tolist(),
                                 parent_OOF=ep['parent_OOF'].tolist(), anchor_prediction=[ep['anchor_AP']]*len(y),
                                 RC_MAE_C=float(np.mean(abs(y-ep['observed'])))))
            if group is None:
                full = dict(selected)
            print(json.dumps(dict(status='FOLD_COMPLETE', group=group, fits=fit_count, selected_tau_s=selected['tau_s'])), flush=True)
    assert fit_count == op['planned_fit_START']
    full.update(adopted=False, future_power_forecaster_validated=False, measured_thermal_mitigation_identified=False,
                equation='dT/dt=-(T-(SKIN_initial+delta+G*(P_API-baseline_API)))/tau', absolute_physical_W_verified=False)
    save(out/'MODEL.json', full)
    save(out/'TAU_PROFILES.json', profiles)
    save(out/'OOF_ROWS.json.gz', rows)
    summaries = [summary(rows, p) for p in ('ALL','OLD','M8','R21')]
    bins = [summary(rows, 'ALL', a, b) for a,b in [(0,35),(35,60),(60,180),(180,256),(256,float('inf'))]]
    supported = dict(AP_C=[float(min(min(e['observed']) for e in entries)), float(max(max(e['observed']) for e in entries))],
                     power_API_W=[float(min(min(e['power_values']) for e in entries)),float(max(max(e['power_values']) for e in entries))],
                     anchor_AP_C=[min(e['anchor_AP'] for e in entries),max(e['anchor_AP'] for e in entries)],
                     anchor_SKIN_C=[min(e['skin'] for e in entries),max(e['skin'] for e in entries)],
                     baseline_API_W=[min(e['baseline'] for e in entries),max(e['baseline'] for e in entries)])
    save(out/'MARGINAL_SUPPORT.json', dict(limits=supported, joint_validation=False,
          max_observed_elapsed_s=float(max(e['times'][-1]-e['anchor_s'] for e in entries)),
          meaning='Marginal measurements only; not a physical safety threshold or joint sustained-workload support'))
    accuracy = all(s['sessions'] and s['RC_MAE_C'] <= min(s['parent_MAE_C'],s['anchor_MAE_C']) for s in summaries)
    identified = full['gain_C_per_API_W'] > 0 and full['tau_s'] not in (op['tau_grid_s'][0],op['tau_grid_s'][-1])
    verify(op)
    result = dict(status='MEASUREMENT_REPLAY_COMPLETE_PENDING_AUDIT', inventory_sessions=len(usage), included_sessions=len(entries),
                  excluded_sessions=len(usage)-len(entries), fits=fit_count, summary=summaries, time_bins=bins,
                  accuracy_gate_pass=bool(accuracy), basic_identification_gate_pass=bool(identified),
                  deployment_gate_pass=False, adopted=False, new_policy_environments=0,new_RL=0,new_measurements=0,
                  observed_power_used_as_input=True, future_power_forecast_validated=False,
                  physical_policy_advantage_proven=False, elapsed_s=time.monotonic()-begin)
    save(out/'RESULT.json', result)
    return result
