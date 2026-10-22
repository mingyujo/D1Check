"""Explain missed deadlines from saved traces only; no model or engine calls."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_ATC_BC600_20261019_01'
Q = R / 'a24_simulator/results/A24_BC_600_20261019_01'


def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes())


def pin(p):
    return dict(path=p.relative_to(R).as_posix(), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    reviews = []
    oldrows = read(Q / 'RESULT.json')['rows']
    for row in read(O / 'RESULT.json')['rows']:
        rawfile = R / row['raw']['path']
        assert pin(rawfile)['sha256'] == row['raw']['sha256']
        data = read(rawfile)
        for q in data['result']['requests']:
            if q['response_ns'] is None or q['response_ns'] <= q['deadline_ns']:
                continue
            decisions = []
            for i, dec in enumerate(data['result']['decisions']):
                if not q['queue_entry_ns'] <= dec['time_ns'] <= q['dispatch_ns']:
                    continue
                call = data['calls'][i]
                assert dec['time_ns'] == call['time_ns']
                actions = call['actions']
                scores = call['forecast_scores'][:len(actions)]
                best = min(range(len(actions)), key=lambda k:(scores[k], k))
                decisions.append(dict(index=i, time_ns=dec['time_ns'],
                    chosen_action=call['action'], owners=[j['request_id'] for j in dec['public_state']['owners']],
                    saved_forecast_min_action=actions[best], saved_chosen_score=scores[call['chosen']],
                    saved_min_score=scores[best], chosen_agrees_with_saved_min=call['chosen'] == best))
            oldrow = next(x for x in oldrows if x['case'] == row['case'])
            oldfile = R / oldrow['raw']['path']
            assert pin(oldfile)['sha256'] == oldrow['raw']['sha256']
            oldq = next(x for x in read(oldfile)['result']['requests'] if x['request_id'] == q['request_id'])
            fields = ('request_id', 'task', 'priority', 'route', 'scheduled_arrival_ns',
                      'queue_entry_ns', 'dispatch_ns', 'deadline_ns', 'response_ns')
            assert all(q[k] == oldq[k] for k in ('scheduled_arrival_ns', 'queue_entry_ns', 'deadline_ns'))
            empty_waits = [d for d in decisions if not d['owners'] and d['chosen_action']['kind'] == 'WAIT']
            idle_wait_ns = sum(d['chosen_action']['wait_ns'] for d in empty_waits)
            reviews.append(dict(case=row['case'], request={k:q[k] for k in fields},
                lateness_ns=q['response_ns'] - q['deadline_ns'],
                queue_wait_ns=q['dispatch_ns'] - q['queue_entry_ns'],
                response_latency_ns=q['response_ns'] - q['scheduled_arrival_ns'],
                empty_system_WAIT_count=len(empty_waits), empty_system_WAIT_ns=idle_wait_ns,
                empty_system_waits_disagreeing_with_saved_teacher_min=sum(not d['chosen_agrees_with_saved_min'] for d in empty_waits),
                old_BC_same_request={k:oldq[k] for k in fields},
                old_BC_margin_ns=oldq['deadline_ns'] - oldq['response_ns'],
                sources=[pin(rawfile), pin(oldfile)], saved_decisions=decisions))
    assert len(reviews) == 1
    assert reviews[0]['empty_system_WAIT_count'] == 9
    assert reviews[0]['empty_system_WAIT_ns'] == 420000000
    record = dict(status='PASS', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source=pin(Path(__file__).resolve()), saved_only=True, new_environment=0, new_fit=0,
        reviews=reviews,
        observation='Recorded NN repeatedly waits despite the stored nominal rolling cost preferring CPU dispatch.',
        inference='BC imitation error on visited evaluation states is a plausible contributor. A higher TRAIN accuracy does not establish better scheduling.',
        not_established=['ATC-only causal effect', 'Outcome of any alternate action trajectory', 'Generalization to other seeds or loads'])
    with (O / 'LATE_CASE_REVIEW.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('SAVED_LATE_CASE_REVIEW_PASS', len(reviews), 'lateness_ns', reviews[0]['lateness_ns'])


if __name__ == '__main__':
    main()
