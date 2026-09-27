import unittest

from tools import d1_energy_model_bridge_v2 as bridge
from tools import d1_arrival_energy_research as research


class BridgeTests(unittest.TestCase):
    def test_fixed_episode_energy_boundary(self):
        prediction = {'phase_trace': [
            {'phase': 'load', 'start_s': 0, 'end_s': 2,
             'whole_device_energy_j_conditional': 6},
            {'phase': 'post_work_wait', 'start_s': 2, 'end_s': 480,
             'whole_device_energy_j_conditional': 956}]}
        self.assertEqual(bridge.common_prediction(prediction, 0), 0)
        self.assertEqual(bridge.common_prediction(prediction, 2), 6)
        self.assertEqual(bridge.common_prediction(prediction, 480), 962)
        with self.assertRaisesRegex(ValueError, 'OUT_OF_SUPPORT'):
            bridge.common_prediction(prediction, 481)

    def test_missing_thermal_is_not_zero_or_forward_filled(self):
        samples = [{'mono_ns': 0, 'AP': '29'}, {'mono_ns': 11_000_000_000, 'AP': '31'}]
        self.assertIsNone(bridge._interpolate(samples, 5_000_000_000, 'AP'))

    def test_joint_state_whole_device_energy_once_and_support_gate(self):
        rows = [dict(start_ns=0, end_ns=2_000_000_000, state='resident_idle'),
                dict(start_ns=2_000_000_000, end_ns=5_000_000_000,
                     state='classification_CPU+detection_GPU')]
        self.assertEqual(bridge.schedule_conditioned_energy(rows,
            {'resident_idle': 1.0, 'classification_CPU+detection_GPU': 3.0},
            0, 5_000_000_000), 11.0)
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            bridge.schedule_conditioned_energy(rows,
                {'resident_idle': 1.0, 'classification_CPU': 2.0,
                 'detection_GPU': 2.0}, 0, 5_000_000_000)
        with self.assertRaisesRegex(ValueError, 'partition'):
            bridge.schedule_conditioned_energy(rows, {'resident_idle': 1.0},
                                               0, 6_000_000_000)

    def test_arrival_profile_is_rejected_with_joint_dwell(self):
        request = dict(id='x', task='classification', priority='normal',
                       arrival_ns=0, deadline_offset_ns=6_000_000_000)
        row = dict(request, status='succeeded', backend='CPU', dispatch_ns=0,
                   execution_start_ns=1, output_ready_ns=2,
                   persist_complete_ns=3, worker_release_ns=4,
                   lane_available_ns=5)
        output = research.aggregate([request], {'ledger': [row]}, horizon_ns=10,
                                    profile={'evidence': 'development_episode_template'})
        self.assertEqual(output['energy_ap']['status'], 'UNSUPPORTED_STATE_COSTS')
        self.assertIsNone(output['energy_ap']['whole_device_energy_j'])
        self.assertGreater(len(output['energy_ap']['required_joint_states_s']), 1)


if __name__ == '__main__':
    unittest.main()
