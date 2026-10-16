"""Read the four capped offline references and deterministic grid witnesses."""
import argparse
import gzip
import html
import json
from pathlib import Path
import numpy as np
from tools import d1_joint_calendar_study as study

P = study.P
ROOT = P.ROOT/'docs/results/method_followup_01'


def load(source, witness):
    source = Path(source); witness = Path(witness)
    registration = json.loads((source/'registered_before_run.json').read_text(encoding='utf8'))
    if registration['spec'] != study.spec(): raise ValueError('joint reference rule changed')
    for name, sha in {**registration['resources'], **registration['code']}.items():
        if P.digest(P.ROOT/name) != sha: raise ValueError('joint source hash mismatch '+name)
    summary = json.loads((source/'summary.json').read_text(encoding='utf8'))
    records = [json.loads(z) for z in gzip.decompress((source/'records.jsonl.gz').read_bytes()).decode().splitlines()]
    expected = {(e, s) for e in study.spec()['cases'] for s in study.spec()['seeds']}
    if len(records) != 4 or {(z['meta']['envelope'], z['meta']['seed']) for z in records} != expected or summary['solves'] != 4:
        raise ValueError('complete reference denominator required')
    wr = json.loads((witness/'registered_before_analysis.json').read_text(encoding='utf8'))
    from tools import d1_joint_calendar_witness as construct
    if P.digest(construct.__file__) != wr['source_sha256'] or wr['resources'] != registration['resources']:
        raise ValueError('witness source/resources changed')
    witnesses = json.loads((witness/'result.json').read_text(encoding='utf8'))['records']
    if len(witnesses) != 4 or {(z['proof']['envelope'], z['proof']['seed']) for z in witnesses} != expected:
        raise ValueError('complete witness denominator required')
    witnesses = {(z['proof']['envelope'], z['proof']['seed']): z for z in witnesses}
    frozen, case = P.inputs(P.BUNDLE); initial = case['initial']
    controls = study.work.budget.readout.source.records(ROOT/'run_v1/records.jsonl.gz')
    refs = {(z['meta']['envelope'], z['meta']['seed']): z for z in controls
        if z['meta']['stage'] == study.work.budget.STAGE and z['meta']['scenario'] == 'mean' and
        z['meta']['policy'] == 'EFT_REFERENCE' and (z['meta']['envelope'], z['meta']['seed']) in expected}
    rows = []; details = []
    for record in records:
        m = record['meta']; key = m['envelope'], m['seed']; ref = refs[key]; result = record['result']
        metric = result.get('metrics')
        if m['status'] != result['status']: raise ValueError('solver status mismatch')
        proof = witnesses[key]['proof']
        # A stored feasibility label is not a proof without its full ledger/jobs.
        wr = witnesses[key]
        tickets = study.followup.tickets(ref)
        profile = P.profile(frozen, 'mean')
        study.followup.x.validate_schedule(wr['jobs'], tickets, profile)
        witness_metric = dict(planned=48, completed=len(wr['ledger']),
            deadline_met=proof['actual_deadline_met'])
        study.work.audit_record(dict(meta=witness_metric, ledger=wr['ledger'], segments=wr['segments']), frozen)
        study.work.budget.same_input(wr, ref)
        witness_cost = P.model.costs(wr['segments'], initial, list(range(35, 181)), frozen, 180.)
        ref_cost = P.model.costs(ref['segments'], initial, list(range(35, 181)), frozen, 180.)
        weights = np.ones(146); weights[[0, -1]] = .5
        idle = witness_cost['initial']['reference_c']
        witness_area = float(weights@np.maximum(np.array(witness_cost['ap_path'])-idle, 0.))
        for field, value in dict(delta_energy_j=witness_cost['whole_120s_j']-ref['meta']['energy_j'],
            delta_peak_ap_c=max(witness_cost['ap_path'])-ref['meta']['peak_ap_c'],
            delta_AP_area_c_s=witness_area-ref['meta']['thermal_degree_seconds']).items():
            if abs(proof[field]-value) > 1e-7: raise ValueError('witness metric mismatch')
        import copy
        import math
        rounded = copy.deepcopy(wr['jobs'])
        for job in rounded:
            q = next(q for q in tickets if q['id'] == job['id'])
            if job['backend'] != 'CPU' or abs((job['start']-35.)/.02-round((job['start']-35.)/.02)) > 1e-6:
                raise ValueError('witness differs from CPU grid contract')
            job['end'] = job['start']+math.ceil(sum(profile[P.key(q, 'CPU')])/1e9/.02-1e-8)*.02
        grid_cost = P.model.costs(P.segments(rounded, 0., 180.), initial, list(range(35, 181)), frozen, 180.)
        grid_peak = max(grid_cost['ap_path'])
        grid_area = float(weights@np.maximum(np.array(grid_cost['ap_path'])-idle, 0.))
        feasible = (all(j['response'] <= j['deadline']+1e-9 for j in rounded)
            and grid_peak <= ref['meta']['peak_ap_c']+1e-8 and grid_area <= ref['meta']['thermal_degree_seconds']+1e-8)
        if proof['same_grid_feasible_witness'] != feasible or abs(proof['planning_peak_c']-grid_peak) > 1e-7 or abs(proof['planning_area_c_s']-grid_area) > 1e-7:
            raise ValueError('witness grid proof mismatch')
        row = dict(m, same_grid_feasible_witness=proof['same_grid_feasible_witness'],
            witness_delta_energy_j=proof['delta_energy_j'], witness_delta_peak_ap_c=proof['delta_peak_ap_c'],
            witness_delta_AP_area_c_s=proof['delta_AP_area_c_s'],
            optimization_unresolved=result['status'] == 'no_incumbent',
            integrated_model_drive_delta_c=None, signed_AP_area_delta_c_s=None,
            device_energy_gain=None, online_policy_validated=False)
        if metric is None:
            if m['deadline_met'] is not None or m['delta_energy_j'] is not None:
                raise ValueError('no incumbent cannot become zero/complete')
        else:
            study.work.audit_record(dict(meta=metric, ledger=result['ledger'], segments=result['segments']), frozen)
            study.work.budget.same_input(result, ref)
            calculated = P.model.costs(result['segments'], initial, list(range(35, 181)), frozen, 180.)
            ref_cost = P.model.costs(ref['segments'], initial, list(range(35, 181)), frozen, 180.)
            idle = calculated['initial']['reference_c']
            path = np.array(calculated['ap_path']); reference_path = np.array(ref_cost['ap_path'])
            weights = np.ones(len(path)); weights[[0, -1]] = .5
            area = float(weights@np.maximum(path-idle, 0.))
            checks = dict(energy_j=calculated['whole_120s_j'], peak_ap_c=float(max(path)), thermal_degree_seconds=area)
            for name, value in checks.items():
                if abs(value-metric[name]) > 1e-7 or abs(m['delta_'+name]-(value-ref['meta'][name])) > 1e-7:
                    raise ValueError('replay metric does not match full model window')
            joint = (metric['deadline_met'] == 48 and all(value <= ref['meta'][name]+1e-8 for name, value in checks.items())
                and any(value < ref['meta'][name]-1e-8 for name, value in checks.items()))
            if m['exact_replay_joint_nonworsening'] != joint:
                raise ValueError('joint improvement label mismatch')
            slopes = frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
            def drive(segments):
                return sum((s['end_s']-s['start_s'])*(slopes[s['state']]-slopes['resident_idle'])
                           for s in segments if s['state'] != 'idle')
            row['integrated_model_drive_delta_c'] = drive(result['segments'])-drive(ref['segments'])
            row['signed_AP_area_delta_c_s'] = float(weights@(path-reference_path))
            row['unknown_incremental_controller_cost_to_erase_J_gain_j'] = max(0., -m['delta_energy_j'])
            details.append(dict(key=dict(envelope=key[0], seed=key[1]), reference=ref, result=result,
                                reference_path=ref_cost, result_path=calculated))
        rows.append(row)
    if summary['new_offline_replays'] != len(details) or summary['joint_nonworsening'] != sum(r['exact_replay_joint_nonworsening'] for r in rows):
        raise ValueError('summary denominator mismatch')
    return dict(version='joint-calendar-readout-v1', rows=rows, details=details, summary=summary,
        device_commands=0, experiment_ready=False, independent_prediction_validation=False,
        physical_advantage_proven=False, accuracy_pass=None,
        interpretation='offline modeled J/peak/rectified-area tradeoff; not online policy or uniformly colder path',
        sources={str(p.relative_to(P.ROOT)).replace('\\', '/'): P.digest(p) for p in
            (source/'registered_before_run.json', source/'records.jsonl.gz', source/'summary.json',
             witness/'registered_before_analysis.json', witness/'result.json')})


def save(result, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    compact = {k: v for k, v in result.items() if k != 'details'}
    compact['analysis_code_sha256'] = P.digest(Path(__file__))
    P.write(out/'result.json', compact)
    fields = sorted(set().union(*(z.keys() for z in result['rows'])))
    study.followup.x.old.csv_write(out/'comparisons.csv', [{k: r.get(k) for k in fields} for r in result['rows']])
    curves = []
    if result['details']:
        # First registered replayed case, not best/most favorable outcome.
        d = result['details'][0]; ref = d['reference']; replay = d['result']; paths = []
        for label, data in [('saved EFT', d['reference_path']), ('offline incumbent', d['result_path'])]:
            for row in data['energy_path']:
                curves.append(dict(series=label, time_s=row['common_s'], modeled_J=row['predicted_j'], modeled_AP_c=None))
            for t, ap in zip(range(35, 181), data['ap_path']):
                curves.append(dict(series=label, time_s=t, modeled_J=None, modeled_AP_c=ap))
            paths.append((label, data))
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
        colors = ('#566377', '#ba4f24')
        for (label, data), color in zip(paths, colors):
            axes[0].plot([v['common_s'] for v in data['energy_path']], [v['predicted_j'] for v in data['energy_path']], label=label, color=color)
            axes[1].plot(range(35, 181), data['ap_path'], label=label, color=color)
        for label, record, shift, color in [('EFT', ref, 0., colors[0]), ('offline', replay, .45, colors[1])]:
            for q in record['ledger']:
                lane = (0 if q['backend'] == 'CPU' else 1)+shift
                axes[2].plot([q['dispatch_ns']/1e9, q['lane_available_ns']/1e9], [lane, lane], lw=5, color=color)
        axes[0].set_ylabel('Modeled whole-device J'); axes[1].set_ylabel('Modeled AP (C)')
        axes[2].set_yticks([0, .45, 1, 1.45], ['CPU EFT', 'CPU offline', 'GPU EFT', 'GPU offline'])
        axes[2].set_xlim(35, 65); axes[2].set_xlabel('Common seconds; dispatch to actual lane release')
        for ax in axes[:2]: ax.legend(); ax.grid(alpha=.2)
        fig.suptitle('Offline future-known incumbent vs saved EFT / not device measurements\n'+
            d['key']['envelope']+' / seed '+str(d['key']['seed']))
        for suffix in ('png', 'svg'): fig.savefig(out/f'modeled_paths.{suffix}', dpi=140)
        plt.close(fig)
        svg = out/'modeled_paths.svg'; svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf8').splitlines())+'\n', encoding='utf8')
        study.followup.x.old.csv_write(out/'modeled_paths.csv', curves)
    columns = ('envelope', 'seed', 'status', 'deadline_met', 'planned', 'delta_energy_j',
               'delta_peak_ap_c', 'delta_thermal_degree_seconds', 'delta_urgent_p95_ms',
               'delta_normal_mean_ms', 'integrated_model_drive_delta_c', 'signed_AP_area_delta_c_s',
               'same_grid_feasible_witness', 'exact_replay_joint_nonworsening')
    headers = ''.join('<th>'+html.escape(k)+'</th>' for k in columns)
    body = ''.join('<tr>'+''.join('<td>'+html.escape('미확인 / null' if r[k] is None else
        str(round(r[k], 6) if type(r[k]) is float else r[k]))+'</td>' for k in columns)+'</tr>' for r in result['rows'])
    (out/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>공동 비용 한도 아래 offline 참고 일정</title>
<style>body{font:16px/1.6 system-ui;max-width:1400px;margin:24px auto;padding:20px}.warning{padding:16px;background:#fff2cf}.scroll{overflow:auto}img{max-width:100%}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:6px}</style>
<h1>같은 기한·AP 최고/면적 아래의 offline 참고 일정</h1>
<p class="warning">저장된 같은4입력/48요청,mean 처리문맥의 제한된 미래입력 최적화입니다. 실제 기기 관측·온라인 정책·독립 확인이 아닙니다. grid20ms,사례당120초를 바꾸지 않았습니다. solver 시간제한을 완료/불가능 증명으로 바꾸지 않습니다.</p>
<p>queue75 두사례는 실제 원PC실행기로 재생해 선택한 J/최고AP/양의AP면적이 함께 낮아졌지만 응답은 길어졌습니다. 전체열입력과 부호있는AP적분은 별도 표시합니다. 이 지표들의 동시 감소는 모든 시점에서 더 차갑다는 뜻이 아닙니다. 제어 비용이 포함되지 않아 작은J이득의 실기기 의미는 미확인입니다.</p>
<p>queue50의 정수해 미확보는 제약불가능이 아닙니다. 같은grid의 결정적CPU일정이 네사례 모두 기한/열 제약을 만족했으나 J는 증가했습니다. 최적성/현재정책우월성/정확도PASS/strict승격은 없습니다.</p>
<p><a href="comparisons.csv">전체4사례·응답상충</a> · <a href="result.json">출처·수치·미판정</a> · <a href="../README.md">계약·검증·한계</a></p>
<div class="scroll"><table><tr>'''+headers+'</tr>'+body+'</table></div>'+('<img src="modeled_paths.png" alt="기기 관측이 아닌 미래입력 참고일정의 모델 계산">' if result['details'] else ''), encoding='utf8')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source', default=str(ROOT/'joint_calendar_v1'))
    parser.add_argument('--witness', default=str(ROOT/'joint_calendar_witness_v1'))
    parser.add_argument('--output', required=True); args = parser.parse_args()
    save(load(args.source, args.witness), args.output)
