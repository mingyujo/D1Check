"""Saved-only RR/FIFO trajectory equality and competition diagnosis."""
from pathlib import Path
from study import H, O, R, old, read, pin, new, stamp


def main():
    fifo = [r for r in read(old.P / 'RESULT.json')['rows']
            if r['condition']['supply_s'] == 600 and r['policy'] == 'FIFO_CPU']
    previous = read(R / 'a24_simulator/results/A24_IDLE_WAIT600_20261019_01/DERIVED.json')
    current = read(O / 'DERIVED.json')
    cases = []
    for rr in read(O / 'RESULT.json')['rows']:
        f = next(r for r in fifo if r['case'] == rr['case'])
        fp = old.P / (f['label']+'.raw.json.gz')
        assert pin(fp)['sha256'] == f['raw_sha256']
        assert pin(R / rr['raw']['path']) == rr['raw']
        a, b = read(R / rr['raw']['path']), read(fp)
        rd, fd = a['result']['decisions'], b['result']['decisions']
        assert len(rd) == len(fd)
        actions_equal = all(x['time_ns'] == y['time_ns'] and x['action'] == y['action'] for x, y in zip(rd, fd))
        before = {q['request_id']:q for q in b['result']['requests']}
        request_differences = [q['request_id'] for q in a['result']['requests'] if
            any(q[k] != before[q['request_id']][k] for k in ('route', 'dispatch_ns', 'response_ns', 'available_ns'))]
        multi_ready = both_classes = differs_fifo = 0
        for d in rd:
            queue = d['public_state']['queue']
            multi_ready += int(len(queue) > 1)
            both_classes += int({q['task'] for q in queue} == {'C', 'D'})
            head = min(queue, key=lambda q:(q['scheduled_arrival_ns'], q['ordinal'], q['request_id']))
            differs_fifo += int(d['action']['request_id'] != head['request_id'])
        cr = next(x for x in current if x['label'] == rr['label'])
        pf = next(x for x in previous if x['label'] == f['label'])
        assert cr['common_end_ns'] == pf['common_end_ns']
        assert actions_equal and not request_differences and differs_fifo == 0
        cases.append(dict(case=rr['case'], decisions=len(rd), multi_ready=multi_ready,
            both_classes_ready=both_classes, selected_request_differs_FIFO=differs_fifo,
            action_and_time_exactly_equal_FIFO=actions_equal, request_time_or_route_differences=request_differences,
            comparison_window_unchanged=True, common_end_ns=cr['common_end_ns'], sources=[rr['raw'], pin(fp)]))
    record = dict(status='PASS', utc=stamp(), new_environment=0, new_fit=0, new_NN_execution=0,
        cases=cases, source=pin(Path(__file__).resolve()),
        interpretation='RR obeys the preserved class-turn rule, but its actual choices equal FIFO for these two inputs. This is conditional equality, not equality of the algorithms.')
    new(O / 'RR_FIFO_DIAGNOSIS.json', record)
    print('RR_FIFO_SAVED_DIAGNOSIS_PASS', cases)


if __name__ == '__main__':
    main()
