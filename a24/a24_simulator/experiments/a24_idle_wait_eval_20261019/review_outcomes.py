"""Explain the two completed new trajectories from saved traces only."""
import json
import gzip
from pathlib import Path
from study import H, O, P, R, read, pin, new, stamp


def main():
    oldrows = read(P / 'RESULT.json')['rows']
    derived = read(O / 'DERIVED.json')
    details, targets = [], []
    for row in read(O / 'RESULT.json')['rows']:
        prior = next(r for r in oldrows if r['case'] == row['case'])
        after, before = read(R / row['raw']['path']), read(R / prior['raw']['path'])
        assert pin(R / row['raw']['path']) == row['raw']
        assert pin(R / prior['raw']['path']) == prior['raw']
        nq = {q['request_id']:q for q in after['result']['requests']}
        oq = {q['request_id']:q for q in before['result']['requests']}
        assert set(nq) == set(oq)
        changed = [dict(request_id=rid, old_route=oq[rid]['route'], new_route=nq[rid]['route'],
                        dispatch_delta_ns=nq[rid]['dispatch_ns']-oq[rid]['dispatch_ns'],
                        response_delta_ns=nq[rid]['response_ns']-oq[rid]['response_ns'])
                   for rid in nq if any(nq[rid][k] != oq[rid][k] for k in ('route', 'dispatch_ns', 'response_ns'))]
        dr = next(d for d in derived if d['label'] == row['label'])
        br = next(d for d in derived if d['label'] == prior['label'])
        filtered = [c for c in after['calls'] if c['idle_wait_guard']['applied']]
        details.append(dict(case=row['case'], before_calls=len(before['calls']), after_calls=len(after['calls']),
            filtered_states=len(filtered), removed_WAIT_actions=sum(len(c['idle_wait_guard']['removed']) for c in filtered),
            saved_common_J=br['common']['J']-dr['common']['J'], AP_delta=dr['common']['AP']-br['common']['AP'],
            changed_request_count=len(changed), changed_requests=changed,
            sources=[row['raw'], prior['raw']]))
        for rid, q in oq.items():
            if q['response_ns'] is None or q['response_ns'] <= q['deadline_ns']:
                continue
            n = nq[rid]
            fields = ('request_id', 'task', 'priority', 'route', 'scheduled_arrival_ns',
                      'queue_entry_ns', 'dispatch_ns', 'deadline_ns', 'response_ns')
            assert n['response_ns'] <= n['deadline_ns']
            idle_waits = [d for d in after['result']['decisions'] if
                n['queue_entry_ns'] <= d['time_ns'] < n['dispatch_ns']
                and not d['public_state']['owners'] and d['action']['kind'] == 'WAIT']
            assert not idle_waits
            targets.append(dict(case=row['case'], before={k:q[k] for k in fields},
                after={k:n[k] for k in fields}, response_improvement_ns=q['response_ns']-n['response_ns'],
                before_lateness_ns=q['response_ns']-q['deadline_ns'],
                after_margin_ns=n['deadline_ns']-n['response_ns'], after_idle_WAITs_while_queued=0))
    assert len(targets) == 1 and targets[0]['response_improvement_ns'] == 420000000
    new(O / 'OUTCOME_REVIEW.json', dict(status='PASS', utc=stamp(), new_environment=0, new_fit=0,
        actual_new_trajectory=True, targets=targets, per_pattern=details, source=pin(Path(__file__).resolve())))
    print('IDLE_WAIT600_OUTCOMES_PASS', len(targets), 'target fixed; response improvement 420ms')


if __name__ == '__main__':
    main()
