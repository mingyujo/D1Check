import json
import unittest
from pathlib import Path

from tools import d1_arrival_energy_research as research
from tools import d1_energy_thermal as thermal
from tools import test_d1_arrival_explore as explore_test


def request(rid='a', priority='urgent', arrival_ns=0, deadline_offset_ns=1_000_000_000):
    return dict(id=rid, task='classification', priority=priority, ordinal=0,
                arrival_ns=arrival_ns, deadline_offset_ns=deadline_offset_ns)


def result(rows):
    return dict(policy='CPU_URGENT', ledger=rows)


def profile():
    def state(power):
        return dict(power_w=power, thermal={'AP': dict(equilibrium_c=40., tau_s=10.)})
    return dict(version=thermal.VERSION, evidence='explicit_assumptions',
        device='synthetic-only', model='synthetic-only', unit_status='assumed W',
        source='hand-calculated unit case, not A24 measurement', sensors=['AP'],
        states={'classification:CPU:urgent:execute': state(2.), 'idle': state(1.)})


class ArrivalEnergyResearchTest(unittest.TestCase):
    def test_existing_scenarios_and_deadlines(self):
        scenarios = research.scenarios()
        self.assertEqual(set(scenarios), {'low', 'queue', 'burst'})
        for rows in scenarios.values():
            self.assertEqual((len(rows), sum(r['priority'] == 'urgent' for r in rows)), (24, 6))
            self.assertEqual({r['deadline_offset_ns'] for r in rows}, {1_500_000_000, 6_000_000_000})
        self.assertEqual(research.scenario_manifest()['horizon_ns'], 120_000_000_000)
        saved = Path(__file__).resolve().parents[1] / 'docs/results/arrival_energy_research_01/scenario_manifest.json'
        self.assertEqual(research.scenario_manifest(), json.loads(saved.read_text(encoding='utf-8')))

    def test_boundaries_full_denominator_and_unsupported_energy(self):
        urgent = dict(request(), status='succeeded', output_ready_ns=900_000_000,
                      persist_complete_ns=1_100_000_000, lane_available_ns=1_200_000_000)
        normal = dict(request('b', 'normal'), status='unfinished')
        out = research.aggregate([request(), request('b', 'normal')], result([urgent, normal]), horizon_ns=2_000_000_000)
        self.assertEqual((out['service']['urgent']['timely'], out['service']['normal']['missing_response']), (1, 1))
        self.assertEqual((out['service']['planned'], out['service']['unfinished']), (2, 1))
        self.assertIsNone(out['energy_ap']['whole_device_energy_j'])
        self.assertEqual(out['energy_ap']['status'], 'UNSUPPORTED_MISSING_ARRIVAL_STATE_PROFILE')

    def test_common_window_assumption_energy_and_ap_not_measured(self):
        row = dict(request(), status='succeeded', backend='CPU', dispatch_ns=0,
                   execution_start_ns=0, output_ready_ns=1_000_000_000,
                   persist_complete_ns=1_000_000_000, worker_release_ns=1_000_000_000,
                   lane_available_ns=1_000_000_000)
        out = research.aggregate([request()], result([row]), horizon_ns=2_000_000_000,
                                 profile=profile(), initial_ap_c=25.)
        self.assertEqual(out['energy_ap']['status'], 'ASSUMPTION_EXPLORATION_ONLY')
        self.assertAlmostEqual(out['energy_ap']['whole_device_energy_j'], 3.)
        self.assertGreater(out['energy_ap']['ap_peak_c'], 25.)
        self.assertEqual(out['energy_ap']['common_window_s'], 2.)
        incomplete = dict(row, status='unfinished')
        self.assertEqual(research.aggregate([request()], result([incomplete]), horizon_ns=2_000_000_000,
            profile=profile(), initial_ap_c=25.)['energy_ap']['status'], 'UNSUPPORTED_INCOMPLETE_LEDGER')

    def test_no_silent_profile_transfer_or_changed_denominator(self):
        row = dict(request(), status='unfinished')
        with self.assertRaises(ValueError):
            research.aggregate([request()], result([dict(row, id='other')]))
        bad = profile(); bad['evidence'] = 'legacy_mobilenet_conditional'
        with self.assertRaises(ValueError):
            research.aggregate([request()], result([row]), profile=bad, initial_ap_c=25.)
        bad = profile(); bad.pop('source')
        with self.assertRaises(ValueError):
            research.aggregate([request()], result([row]), profile=bad, initial_ap_c=25.)
        with self.assertRaises(ValueError):
            research.aggregate([request(arrival_ns=3)], result([row]), horizon_ns=2)

    def test_existing_engine_ledger_adapter(self):
        # Actual event engine boundary, not a hand-built ledger.
        from tools.test_d1_cal03_connection import request as engine_request
        source = engine_request()
        engine_result = explore_test.ExploreTest().run_case([source], horizon=100)
        out = research.aggregate([source], engine_result, horizon_ns=100)
        self.assertEqual((out['service']['urgent']['timely'], out['service']['lane_released']), (1, 1))
        self.assertEqual(out['energy_ap']['status'], 'UNSUPPORTED_MISSING_ARRIVAL_STATE_PROFILE')

    def test_waiting_state_requires_its_own_assumption(self):
        row = dict(request(), status='succeeded', backend='CPU', dispatch_ns=1_000_000_000,
                   execution_start_ns=1_000_000_000, output_ready_ns=2_000_000_000,
                   persist_complete_ns=2_000_000_000, worker_release_ns=2_000_000_000,
                   lane_available_ns=2_000_000_000)
        with self.assertRaisesRegex(ValueError, 'unsupported state'):
            research.aggregate([request()], result([row]), horizon_ns=3_000_000_000,
                               profile=profile(), initial_ap_c=25.)


if __name__ == '__main__':
    unittest.main()
