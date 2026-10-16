import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from pathlib import Path
from tools import d1_simulation_model_v3_campaign as c


class V3CampaignTests(unittest.TestCase):
    def test_four_new_confirmations_have_complete_fixed_budgets(self):
        b=c.budget()
        self.assertEqual(b['explicit_inference'],4*(96+8))
        self.assertEqual(b['runtime_creations'],16)
        self.assertEqual(b['total_seconds'],600+4*765+3*90+600)
        self.assertEqual(b['fixed_observation_seconds'],4*(30+120+60))
        self.assertEqual(b['adb_commands'],b['pre_cleanup_command_slots'])
        self.assertEqual(b['installs'],0);self.assertEqual(b['apk_transfers'],0)
        self.assertEqual(c.POLICIES,(c.POLICIES[0],c.POLICIES[1],c.POLICIES[1],c.POLICIES[0]))
    def test_explicit_user_lower_gate_adds_only_required_install_reservation(self):
        b=c.budget(True)
        self.assertEqual(b['total_seconds'],5130);self.assertEqual(b['explicit_inference'],416)
        self.assertEqual(b['installs'],1);self.assertEqual(b['apk_transfers'],1)
        self.assertEqual(b['adb_commands'],5704);self.assertEqual(b['adb_command_slots'],5904)
    def test_observation_repair_preserves_global_command_cap_and_inference_roster(self):
        b=c.observation_repair_budget()
        self.assertEqual(b['adb_command_slots']+119,5904)
        self.assertEqual(b['explicit_inference'],416);self.assertEqual(b['installs'],0)
    def test_hybrid_is_two_new_confirmations_and_no_install_or_extra_training(self):
        b=c.hybrid_budget();self.assertEqual(b['sessions'],2);self.assertEqual(b['explicit_inference'],208)
        self.assertEqual(b['total_seconds'],600+2*765+90+600);self.assertEqual(b['installs'],0)
    def test_longer_response_timeout_keeps_same_sensor_clock_uncertainty_guard(self):
        from tools import d1_energy_collection_device as device
        d=SimpleNamespace(thermal_timeout_seconds=3,call=MagicMock(return_value=SimpleNamespace(stdout=b'x')))
        with tempfile.TemporaryDirectory() as t,patch.object(device.logger,'parse_uptime',side_effect=[100000000000,104100000000]):
            with self.assertRaises(ValueError):device.thermal(d,Path(t),0)
            self.assertTrue(all(call.kwargs['timeout']==3 for call in d.call.call_args_list))
            self.assertFalse((Path(t)/'thermal.jsonl').exists())


if __name__=='__main__':unittest.main()
