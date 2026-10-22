"""Pure RR semantics/capacity regressions. No simulator or NN is executed."""
import copy
import unittest
from rr_policy import RoundRobin, legacy


def q(i, task='C', arrival=1, due=100, priority='N'):
    return dict(request_id=str(i), task=task, scheduled_arrival_ns=arrival,
                queue_entry_ns=arrival, ordinal=i, deadline_ns=due, priority=priority)


def s(queue, owners=()):
    return dict(now_ns=10, queue=queue, owners=[dict(route=r) for r in owners])


class RRChecks(unittest.TestCase):
    def test_initial_C_then_D(self):
        rr = RoundRobin();state = s([q(1, 'D'), q(2)])
        self.assertEqual(rr(state)['request_id'], '2')
        self.assertEqual(rr(state)['request_id'], '1')

    def test_skip_empty_class_and_advance_from_actual_class(self):
        rr = RoundRobin()
        self.assertEqual(rr(s([q(1, 'D')]))['request_id'], '1')
        self.assertEqual(rr.turn, 'C')
        self.assertTrue(rr.calls[-1]['empty_class_skipped'])

    def test_within_class_FIFO_and_ordinal(self):
        self.assertEqual(RoundRobin()(s([q(9, arrival=2), q(3)]))['request_id'], '3')
        self.assertEqual(RoundRobin()(s([q(9), q(3)]))['request_id'], '3')

    def test_ID_breaks_equal_arrival_and_ordinal(self):
        a, b = q(1), q(1);a['request_id'] = 'b';b['request_id'] = 'a'
        self.assertEqual(RoundRobin()(s([a, b]))['request_id'], 'a')

    def test_deadline_and_priority_do_not_override_RR(self):
        self.assertEqual(RoundRobin()(s([q(1, 'D', due=11, priority='U'), q(2, due=100)]))['request_id'], '2')

    def test_CPU_first_when_both_free(self):
        self.assertEqual(RoundRobin()(s([q(1)]))['route'], 'CPU')

    def test_partial_CPU_occupancy_keeps_CPU_available(self):
        for count in (1, 2):
            self.assertEqual(RoundRobin()(s([q(1)], ['CPU']*count))['route'], 'CPU')

    def test_three_CPUs_busy_uses_GPU(self):
        self.assertEqual(RoundRobin()(s([q(1)], ['CPU']*3))['route'], 'GPU')

    def test_GPU_busy_keeps_CPU_available(self):
        self.assertEqual(RoundRobin()(s([q(1)], ['GPU']))['route'], 'CPU')

    def test_all_busy_preserves_turn(self):
        rr = RoundRobin()
        self.assertEqual(rr(s([q(1)], ['CPU']*3+['GPU'])), dict(kind='RESOURCE_WAIT'))
        self.assertEqual(rr.turn, 'C')

    def test_empty_queue_preserves_turn(self):
        rr = RoundRobin();rr(s([q(1)]))
        self.assertEqual(rr(s([])), dict(kind='RESOURCE_WAIT'))
        self.assertEqual(rr.turn, 'D')

    def test_public_input_not_mutated(self):
        state = s([q(1), q(2, 'D')], ['CPU']);before = copy.deepcopy(state)
        RoundRobin()(state)
        self.assertEqual(state, before)

    def test_invalid_resource_counts_rejected(self):
        for owners in (['CPU']*4, ['GPU']*2, ['NPU']):
            with self.assertRaises(ValueError):RoundRobin()(s([q(1)], owners))

    def test_future_duplicate_and_unknown_requests_rejected(self):
        for queue in ([q(1, arrival=11)], [q(1), q(1)], [q(1, task='X')]):
            with self.assertRaises(ValueError):RoundRobin()(s(queue))

    def test_legacy_CPU1_actions_and_turns_exact(self):
        old, new = legacy.RoundRobin(), RoundRobin(cpu_slots=1)
        for state in (s([q(1), q(2, 'D')]), s([q(1), q(2, 'D')], ['CPU']),
                      s([q(7, 'D')]), s([], ['CPU', 'GPU']), s([q(1)], ['GPU'])):
            self.assertEqual(old(state), new(state));self.assertEqual(old.turn, new.turn)

    def test_new_session_resets_turn_and_logs_semantics(self):
        rr = RoundRobin();rr(s([q(1)]))
        self.assertEqual(RoundRobin().turn, 'C')
        self.assertFalse(rr.calls[-1]['NN_execution'])
        self.assertFalse(rr.calls[-1]['future_information'])
        self.assertFalse(rr.calls[-1]['post_NN_override'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
