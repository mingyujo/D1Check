"""Pure LSF/adapter/source contracts; no scientific simulation or NN."""
import copy
import unittest
from pathlib import Path
from lsf_policy import Policy


class Nominal:
    def __init__(self, values=None):
        self.values = values or {}

    def vector(self, q, r, s):
        return list(self.values.get((q['request_id'], r), [.01, .1 if r == 'CPU' else .3, .02, .01, .01]))


class Physics:
    cpu_slots = 3
    beta = .25

    def speed(self, T, r, k, task):
        return 1.


def q(i, task='C', due=1.):
    return dict(request_id=f'q{i}', ordinal=i, task=task, priority='N', scheduled_arrival_ns=0,
                queue_entry_ns=0, deadline_ns=round(due * 1e9))


def state(queue, owners=()):
    return dict(now_ns=0, queue=queue, owners=list(owners), sensor=dict(temperature_c=26))


def owner(i, route='CPU', stage=1, progress=0.):
    return dict(request_id=f'o{i}', task='C', route=route, stage=stage, public_progress_s=progress)


def actor(mode='LSF_DYN', values=None):
    return Policy(Nominal(values), Physics(), mode)


class Checks(unittest.TestCase):
    def test_stage0_owner_does_not_subtract_itself_from_inference_count(self):
        p = actor('BAND_LSF_ALL')
        estimates = p.estimates(state([q(1)], [owner(0, stage=0), owner(1), owner(2)]))[2]
        self.assertAlmostEqual(estimates[0]['rate'], 1 / 1.5)

    def test_basic_LSF_differs_EDF(self):
        values = {('q1', 'CPU'): [0, .1, 0, 0, 0], ('q1', 'GPU'): [0, .1, 0, 0, 0],
                  ('q2', 'CPU'): [0, .8, 0, 0, 0], ('q2', 'GPU'): [0, .8, 0, 0, 0]}
        self.assertEqual(actor(values=values)(state([q(1, due=.5), q(2, due=.9)]))['request_id'], 'q2')

    def test_FIFO_tie(self):
        self.assertEqual(actor()(state([q(2), q(1)]))['request_id'], 'q1')

    def test_basic_no_drop_late(self):
        self.assertEqual(actor()(state([q(1, due=.01)]))['kind'], 'DISPATCH')

    def test_band_ALL_no_drop_late(self):
        self.assertEqual(actor('BAND_LSF_ALL')(state([q(1, due=.01)]))['kind'], 'DISPATCH')

    def test_band_DROP_late(self):
        self.assertEqual(actor('BAND_LSF_DROP')(state([q(1, due=.01)]))['kind'], 'DROP')

    def test_band_DROP_feasible(self):
        self.assertEqual(actor('BAND_LSF_DROP')(state([q(1)]))['kind'], 'DISPATCH')

    def test_C_D_response_boundary(self):
        p = actor(); p(state([q(1)]))
        self.assertAlmostEqual(p.calls[-1]['ranked_jobs'][0]['total_response_s'], .11)
        p = actor(); p(state([q(1, 'D')]))
        self.assertAlmostEqual(p.calls[-1]['ranked_jobs'][0]['total_response_s'], .13)

    def test_basic_GPU_when_CPU_full(self):
        self.assertEqual(actor()(state([q(1)], [owner(i) for i in range(3)]))['route'], 'GPU')

    def test_band_waits_busy_best_route(self):
        self.assertEqual(actor('BAND_LSF_ALL')(state([q(1)], [owner(i, stage=4) for i in range(3)]))['kind'], 'RESOURCE_WAIT')

    def test_band_skip_busy_head_dispatch_other(self):
        values = {('q2', 'CPU'): [.01, 2., 0, 0, 0], ('q2', 'GPU'): [.01, .1, 0, 0, 0]}
        st = state([q(1, due=.5), q(2, due=1)], [owner(i, stage=4) for i in range(3)])
        self.assertEqual(actor('BAND_LSF_ALL', values)(st)['request_id'], 'q2')

    def test_no_drop_if_all_workers_busy(self):
        st = state([q(1, due=.001)], [owner(i) for i in range(3)] + [owner(4, 'GPU')])
        self.assertEqual(actor('BAND_LSF_DROP')(st)['kind'], 'RESOURCE_WAIT')

    def test_busy_CPU_prediction_not_CPU4(self):
        p = actor('BAND_LSF_ALL'); st = state([q(1)], [owner(i) for i in range(3)])
        options = p.estimates(st)[3][0]['route_options']
        self.assertAlmostEqual(next(x for x in options if x['route'] == 'CPU')['rate'], 1 / 1.5)

    def test_public_remaining_clamped_zero(self):
        p = actor('BAND_LSF_ALL'); p(state([q(1)], [owner(i, stage=4, progress=5) for i in range(3)]))
        self.assertEqual(p.wait_calls[-1]['release_estimates_s']['CPU'], 0.)

    def test_empty_queue(self):
        self.assertEqual(actor()(state([]))['kind'], 'RESOURCE_WAIT')

    def test_input_immutable(self):
        st = state([q(1)], [owner(1)]); before = copy.deepcopy(st); actor()(st)
        self.assertEqual(st, before)

    def test_future_rejected(self):
        st = state([q(1)]); st['queue'][0]['queue_entry_ns'] = 1
        with self.assertRaises(ValueError): actor()(st)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError): actor()(state([q(1), q(1)]))

    def test_unknown_owner_rejected(self):
        with self.assertRaises(ValueError): actor()(state([q(1)], [owner(1, 'NPU')]))

    def test_overcapacity_rejected(self):
        with self.assertRaises(ValueError): actor()(state([q(1)], [owner(i) for i in range(4)]))

    def test_DROP_fork_only_added_branch(self):
        h = Path(__file__).resolve().parent
        original = (h.parent / 'a24_s26_method_20261019/engine.py').read_text(encoding='utf-8')
        fork = (h / 'drop_engine.py').read_text(encoding='utf-8')
        start = fork.index("            if action['kind']=='DROP':")
        end = fork.index("            if action['kind']=='WAIT_EVENT':", start)
        self.assertEqual(fork[:start] + fork[end:], original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
