"""Single predeclared causal area-veto candidate; bounded PC comparison only."""
import argparse
from datetime import datetime, timezone
import gzip
import html
import json
from pathlib import Path
import subprocess
import time
from tools import d1_joint_queue_area as candidate
from tools import d1_method_followup as followup
from tools import d1_method_workbench as work

P = candidate.P
ROOT = followup.ROOT


def specification():
    return dict(version='joint-queue-area-study-v1', envelope='g0.45_c0.75_b4', seeds=[523001, 523002],
        scenarios=list(candidate.x.old.SCENARIOS), requests=48, policies=['EFT_REFERENCE', candidate.LABEL],
        maximum_PC_runs=12, maximum_wall_s=900., parameter_candidates=1,
        selection='prior offline queue75 witness motivates this posthoc structure; only two new synthetic seeds; not new independent device evidence',
        modification='add clipped AP area veto vs current-queue EFT continuation to unchanged J/peak/long-context per-request guard',
        preserved='parent first four queue, depth4/width8/64 candidates, firstwait0 or0.25s, maxfirststart2s, original aging and every arrival independent of completion',
        relative_caps='current-queue model comparison only; neither global future-service proof nor safety/accuracy threshold',
        engine_callback_ABI=candidate.parent.POLICY, public_candidate_ID=candidate.LABEL,
        no_new_physical_terms=True, controller_zero_incremental_cost_assumption=True,
        freeze='publish all six paired contexts; no re-tuning/extra seeds/extra candidates after outcomes',
        independent_device_validation=False, strict_supported=False, experiment_ready=False, device_commands=0)


def run(output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    rule = specification(); frozen, case = P.inputs(P.BUNDLE)
    files = [Path(__file__), Path(candidate.__file__), Path(candidate.parent.__file__), Path(P.__file__),
        Path(candidate.x.__file__), Path(candidate.x.old.engine.__file__), Path(followup.conditions.__file__)]
    code = {p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in files}
    resources = work.verify_resources()
    env = next(e for e in followup.conditions.envelopes() if e['id'] == rule['envelope'])
    inputs = [dict(seed=seed, tickets=followup.conditions.workload(env, seed)) for seed in rule['seeds']]
    P.write(out/'inputs.json', inputs)
    P.write(out/'registered_before_run.json', dict(spec=rule, code=code, resources=resources,
        input_sha256=P.digest(out/'inputs.json'), utc=datetime.now(timezone.utc).isoformat(),
        base_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), source_dirty=True))
    for path in (Path(__file__), Path(candidate.__file__)): (out/path.name).write_bytes(path.read_bytes())
    rows = []; records = []; began = time.monotonic()
    try:
        for block in inputs:
            for context in rule['scenarios']:
                for policy in rule['policies']:
                    if time.monotonic()-began >= rule['maximum_wall_s']: raise TimeoutError('bounded single-candidate queue study')
                    tickets = block['tickets']
                    if policy == 'EFT_REFERENCE':
                        metric, result, controller, segments, cost = candidate.x.simulate(frozen, case['initial'], tickets, context, policy)
                        # Existing constructor has no callback timer; zero is not a measurement.
                        metric['decision_host_total_s'] = metric['decision_host_max_ms'] = None
                    else:
                        metric, result, controller, segments, cost = candidate.simulate(frozen, case['initial'], tickets, context)
                    if len(result['ledger']) != 48: raise ValueError('complete scheduled denominator required')
                    if followup.tickets(dict(ledger=result['ledger'])) != tickets: raise ValueError('arrival/task/deadline moved')
                    row = dict(metric, envelope=rule['envelope'], seed=block['seed'], scenario=context, policy=policy,
                        stage='fresh_synthetic_after_structure_selection', actual_device_validation=False)
                    if metric['completed'] == 48:
                        work.audit_record(dict(meta=metric, ledger=result['ledger'], segments=segments), frozen)
                    rows.append(row); records.append(dict(meta=row, ledger=result['ledger'], segments=segments,
                        decisions=result['decisions'], guards=getattr(controller, 'records', []),
                        predicted_ap_path=cost['ap_path']))
                    fields = sorted(set().union(*(r.keys() for r in rows)))
                    candidate.x.old.csv_write(out/'results.csv', [{k: r.get(k) for k in fields} for r in rows])
                    (out/'records.jsonl.gz').write_bytes(gzip.compress((''.join(json.dumps(r, allow_nan=False)+'\n' for r in records)).encode(), mtime=0))
                    P.write(out/'progress.json', dict(PC_runs=len(rows), elapsed_s=time.monotonic()-began))
                    print(block['seed'], context, policy, row['deadline_met'], row['energy_j'], flush=True)
    except BaseException as error:
        import traceback
        P.write(out/'PC_FAILURE.json', dict(error_type=type(error).__name__, message=str(error),
            stack=traceback.format_exc(), completed_runs=len(rows), original_error_preserved=True))
        raise
    if code != {p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in files} or resources != work.verify_resources():
        raise ValueError('registered candidate/source/model changed')
    if P.digest(out/'inputs.json') != json.loads((out/'registered_before_run.json').read_text(encoding='utf8'))['input_sha256']:
        raise ValueError('registered arrivals changed')
    pairs = followup.compare(rows)
    candidate.x.old.csv_write(out/'comparisons.csv', pairs)
    summary = dict(PC_runs=len(rows), PC_requests=48*len(rows), eligible_pairs=sum(p['full_service'] for p in pairs),
        joint_nonworsening=sum(p['joint_nonworsening'] for p in pairs), elapsed_s=time.monotonic()-began,
        candidate_ID=candidate.LABEL, candidate_count=1, re_tuning_runs=0, independent_device_sessions=0,
        accuracy_pass=None, physical_advantage_proven=False, device_commands=0, experiment_ready=False)
    P.write(out/'summary.json', summary)
    keys = ('seed', 'scenario', 'deadline_met', 'planned', 'delta_energy_j', 'delta_peak_ap_c',
        'delta_thermal_degree_seconds', 'delta_urgent_p95_ms', 'delta_normal_mean_ms', 'joint_nonworsening')
    table = '<tr>'+''.join('<th>'+k+'</th>' for k in keys)+'</tr>'
    table += ''.join('<tr>'+''.join('<td>'+html.escape('null' if p[k] is None else str(p[k]))+'</td>' for k in keys)+'</tr>' for p in pairs)
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>도착한 큐의 공동 비용 후보</title>'+
        '<style>body{font:16px/1.7 system-ui;margin:24px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #aaa;padding:6px}.note{background:#fff2ca;padding:15px}.scroll{overflow:auto}</style>'+
        '<h1>도착한 큐의 J·최고 AP·면적 후보 한 개</h1><p class="note">앞선 미래일정 결과를 본 뒤 구조를 선택했습니다. 이 결과는 새 합성 seed 두 개/기존 개발 처리문맥의 PC 평가이며 독립 실기기 확인이 아닙니다. 현재 큐의 상대 제약은 미래 요청의 서비스 보장이 아닙니다.</p>'+
        '<p>기존 탐색 폭/대기 상한/계수/원 엔진은 유지했습니다. 전 도착 분모와 응답 상충을 보존하며, 실제 제어 비용과 미측정 상태를0으로 채우지 않습니다. 새 기본 정책/정확도 PASS/strict 승격은 없습니다.</p><div class="scroll"><table>'+table+'</table></div>'+
        '<p><a href="summary.json">소비·분모</a> · <a href="comparisons.csv">같은 입력 EFT 대조</a> · <a href="../README.md">근거·검증·한계</a></p>', encoding='utf8')
    return pairs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
