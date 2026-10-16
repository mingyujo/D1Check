"""Fixed mean calendar transfer to existing short/long PC contexts.

No replanning/fitting: releases and backends are fixed; the unchanged event
engine owns completion and lane release. A late lane delays dispatch instead
of forcing a fabricated service duration. This is not a causal online policy.
"""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import html
import json
from pathlib import Path
import subprocess
import time
from tools import d1_joint_calendar_report as readout

P = readout.P
x = readout.study.followup.x
ROOT = readout.ROOT


def specification():
    return dict(version='fixed-joint-calendar-transfer-v1', cases=['g0.45_c0.75_b4'],
        seeds=[223001, 223002], source_scenario='mean', contexts=['short_context', 'long_context'],
        maximum_PC_replays=4, maximum_wall_s=120., optimizer_runs=0,
        rule='all two prior integer incumbents; fixed request ID/backend/not-before release; arrived queue only; actual lane ownership; no new delays or replanning',
        timing='existing whole five-phase development contexts, not randomized or independent device sessions',
        windows=dict(energy_s=[0, 120], AP_s=[35, 180]),
        comparison='same-arrival EFT already stored for each context; no source plan selection by transfer outcome',
        physical_validation=False, strict_supported=False, experiment_ready=False, device_commands=0)


class NotBeforeReplay(x.Replay):
    """Recorded future calendar with release times, not forced exact starts."""
    def __call__(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        if any(q['arrival_ns'] > now_ns for q in queue): raise ValueError('future queue ticket')
        if any(q['id'] not in self.plan for q in queue): raise ValueError('unregistered calendar request')
        ready = sorted((self.plan[q['id']] for q in queue), key=lambda j: (j['start'], j['id']))
        for job in ready:
            # Integer ns lower bound: never dispatch before the recorded release.
            release_ns = round(job['start']*1e9)
            if release_ns <= now_ns and lanes[job['backend']]['request'] is None:
                members = [job['state']]+[lane['request']['task']+'_'+b for b, lane in lanes.items() if lane['request']]
                if '+'.join(sorted(members)) not in P.STATES: continue
                return dict(now_ns=now_ns, selected=dict(request_id=job['id'], backend=job['backend']),
                    reason='fixed_offline_not_before_release', recorded_release_ns=release_ns,
                    dispatch_lateness_ns=now_ns-release_ns)
        future = [round(j['start']*1e9) for j in ready if round(j['start']*1e9) > now_ns]
        result = dict(now_ns=now_ns, selected=None, reason='fixed_calendar_wait_for_release_or_actual_lane')
        if future: result['wait_until_ns'] = min(future)
        return result


def replay(frozen, initial, tickets, context, jobs):
    if context not in specification()['contexts']: raise ValueError('registered contexts only')
    controller = NotBeforeReplay(frozen, initial, jobs)
    vectors = dict(cells={k: [dict(source_request_id='development_context_'+context, durations_ns=v) for _ in range(4)]
        for k, v in P.profile(frozen, context).items()})
    result = x.old.engine.simulate(dict(protocol=P.VERSION, cells=P.profile(frozen)), vectors, tickets,
        policy=x.REPLAY, settings=x.settings(), seed=201, decision_provider=controller)
    metric, segments, cost = x.outcome(result, initial, frozen)
    by_id = {j['id']: j for j in jobs}
    for q in result['ledger']:
        job = by_id[q['id']]
        if q['backend'] != job['backend'] or q['dispatch_ns'] < round(job['start']*1e9):
            raise ValueError('fixed calendar backend/release changed')
        d = P.profile(frozen, context)[P.key(q, q['backend'])]
        # Profile means are fractional ns; the unchanged engine independently
        # rounds dispatch and each boundary to integer ns (difference <1 ns).
        fields = ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')
        if any(abs(q[field]-q['dispatch_ns']-sum(d[:i+1])) > 1.01 for i, field in enumerate(fields)):
            raise ValueError('actual five-phase service was forced to calendar duration')
    readout.study.work.audit_record(dict(meta=metric, ledger=result['ledger'], segments=segments), frozen)
    lateness = [(q['dispatch_ns']-round(by_id[q['id']]['start']*1e9))/1e6 for q in result['ledger']]
    return dict(metrics=metric, ledger=result['ledger'], segments=segments,
        decisions=result['decisions'], AP_path=cost['ap_path'],
        delayed_dispatches=sum(v > 1e-6 for v in lateness), maximum_dispatch_lateness_ms=max(lateness))


def run(output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    prior = readout.load(ROOT/'joint_calendar_v1', ROOT/'joint_calendar_witness_v1')
    rule = specification()
    if [(d['key']['envelope'], d['key']['seed']) for d in prior['details']] != [(rule['cases'][0], s) for s in rule['seeds']]:
        raise ValueError('all fixed two incumbents required')
    frozen, case = P.inputs(P.BUNDLE)
    code_files = [Path(__file__), Path(readout.__file__), Path(x.__file__), Path(x.old.engine.__file__)]
    code = {p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in code_files}
    resources = readout.study.work.verify_resources()
    P.write(out/'registered_before_run.json', dict(spec=rule, code=code, resources=resources,
        source_plans_sha256=P.digest(ROOT/'joint_calendar_v1/records.jsonl.gz'),
        base_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), source_dirty=True,
        utc=datetime.now(timezone.utc).isoformat()))
    (out/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    refs = readout.study.work.budget.readout.source.records(ROOT/'run_v1/records.jsonl.gz')
    rows = []; records = []; began = time.monotonic()
    try:
        for detail in prior['details']:
            key = detail['key']; tickets = readout.study.followup.tickets(detail['reference'])
            jobs = copy.deepcopy(detail['result']['jobs'])
            for context in rule['contexts']:
                if time.monotonic()-began >= rule['maximum_wall_s']: raise TimeoutError('bounded fixed-calendar transfer')
                reference = next(r for r in refs if r['meta']['stage'] == readout.study.work.budget.STAGE and
                    r['meta']['envelope'] == key['envelope'] and r['meta']['seed'] == key['seed'] and
                    r['meta']['policy'] == 'EFT_REFERENCE' and r['meta']['scenario'] == context)
                result = replay(frozen, case['initial'], tickets, context, jobs)
                readout.study.work.budget.same_input(result, reference)
                metric = result['metrics']; ref = reference['meta']
                row = dict(**key, context=context, planned=48, completed=metric['completed'],
                    deadline_met=metric['deadline_met'], reference_deadline_met=ref['deadline_met'],
                    delayed_dispatches=result['delayed_dispatches'], maximum_dispatch_lateness_ms=result['maximum_dispatch_lateness_ms'],
                    **{'delta_'+k: metric[k]-ref[k] for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds', 'urgent_p95_ms', 'normal_mean_ms')},
                    fixed_plan_joint_nonworsening=metric['deadline_met'] == ref['deadline_met'] == 48 and
                    all(metric[k] <= ref[k]+1e-8 for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds')) and
                    any(metric[k] < ref[k]-1e-8 for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds')),
                    actual_device_validation=False, online_policy=False, experiment_ready=False)
                rows.append(row); records.append(dict(meta=row, result=result, reference=ref,
                    fixed_jobs=jobs, tickets=tickets))
                x.old.csv_write(out/'results.csv', rows)
                (out/'records.jsonl.gz').write_bytes(gzip.compress((''.join(json.dumps(r, allow_nan=False)+'\n' for r in records)).encode(), mtime=0))
                P.write(out/'progress.json', dict(completed_replays=len(rows), elapsed_s=time.monotonic()-began))
                print(context, key['seed'], row['deadline_met'], row['delta_energy_j'], row['delta_peak_ap_c'], flush=True)
    except BaseException as error:
        import traceback
        P.write(out/'PC_FAILURE.json', dict(error_type=type(error).__name__, message=str(error),
            stack=traceback.format_exc(), completed_replays=len(rows), original_error_preserved=True))
        raise
    if code != {p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in code_files} or resources != readout.study.work.verify_resources():
        raise ValueError('registered fixed-calendar transfer evidence changed')
    summary = dict(PC_replays=len(rows), PC_requests=48*len(rows), optimizer_runs=0,
        fixed_plan_joint_nonworsening=sum(r['fixed_plan_joint_nonworsening'] for r in rows), elapsed_s=time.monotonic()-began,
        independent_device_sessions=0, device_commands=0, experiment_ready=False)
    P.write(out/'summary.json', summary)
    fields = ('seed', 'context', 'deadline_met', 'reference_deadline_met', 'delayed_dispatches',
        'maximum_dispatch_lateness_ms', 'delta_energy_j', 'delta_peak_ap_c', 'delta_thermal_degree_seconds',
        'delta_urgent_p95_ms', 'delta_normal_mean_ms', 'fixed_plan_joint_nonworsening')
    table = '<tr>'+''.join('<th>'+k+'</th>' for k in fields)+'</tr>'
    table += ''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in fields)+'</tr>' for r in rows)
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>고정 일정의 처리문맥 전이</title>'+
        '<style>body{font:16px/1.7 system-ui;margin:24px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #aaa;padding:6px}.note{background:#fff2ca;padding:15px}.scroll{overflow:auto}</style>'+
        '<h1>평균 문맥에서 찾은 미래 일정의 고정 재생</h1><p class="note">같은 두 계획의 backend와 not-before 시각을 고정하고 기존 short/long 5단계 문맥만 적용했습니다. 실제 lane 반환을 기다리며 강제 감속·처리시간 맞춤·재최적화는 없습니다. 독립 실기기 확인이나 인과적 온라인 정책이 아닙니다.</p>'+
        '<p>기한 충족과 에너지·AP 상충을 별도 표시합니다. 이 네 PC 문맥을 독립 세션·통계적 안정성·미래 지연 상한으로 쓰지 않습니다. 기본/strict/experiment_ready=false 유지.</p><div class="scroll"><table>'+table+'</table></div>'+
        '<p><a href="results.csv">전체4사례</a> · <a href="summary.json">소비·범위</a> · <a href="../README.md">근거·검증·한계</a></p>', encoding='utf8')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
