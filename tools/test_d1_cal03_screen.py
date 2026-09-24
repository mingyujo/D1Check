import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import d1_arrival_timing_calibration_device as d


class ScreenTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.contract=dict(poll_interval_seconds=10,screen_brightness=81,screen_brightness_mode=0,screen_off_timeout=18000000)

    def test_pass_records_settings_and_command_cost_without_setting_writes(self):
        dev=Mock()
        values=[b'mWakefulness=Awake\nmHalInteractiveModeEnabled=true\n',b'81',b'0',b'18000000']
        dev.call.side_effect=[SimpleNamespace(stdout=x) for x in values]
        result=d.screen_snapshot(dev,self.root,'before_launch',self.contract,settings=True)
        self.assertEqual(result['status'],'sample_pass')
        self.assertEqual(result['screen_brightness'],'81')
        self.assertGreaterEqual(result['host_end'],result['host_start'])
        self.assertTrue(all(c.kwargs['timeout']==2 and 'put' not in c.args for c in dev.call.call_args_list))

    def test_screen_deviation_and_query_failure_are_preserved_and_stop(self):
        for label,effect in [('sleep',SimpleNamespace(stdout=b'mWakefulness=Dozing\nmHalInteractiveModeEnabled=false')),
                             ('lost',OSError('ADB lost'))]:
            dev=Mock()
            if isinstance(effect,Exception):dev.call.side_effect=effect
            else:dev.call.return_value=effect
            with self.assertRaises((OSError,ValueError)):d.screen_snapshot(dev,self.root,label,self.contract)
            result=json.loads((self.root/'screen_observations'/f'{label}.json').read_text())
            self.assertEqual(result['status'],'sample_failed')

    def test_poll_observation_failure_does_not_continue_to_next_app_probe(self):
        dev=Mock(deadline=125)
        with patch.object(d,'screen_snapshot',side_effect=ValueError('sleep')) as screen:
            with patch.object(d.time,'monotonic',return_value=0):
                with self.assertRaisesRegex(ValueError,'sleep'):
                    d.wait_for_cleanup(dev,'remote',screen_contract=self.contract,folder=self.root)
        dev.call.assert_not_called();screen.assert_called_once()

    def test_poll_shares_deadline_and_records_final_sample(self):
        dev=Mock(deadline=125);dev.call.return_value=SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
        with patch.object(d.time,'monotonic',return_value=0),patch.object(d,'screen_snapshot') as screen:
            d.wait_for_cleanup(dev,'remote',screen_contract=self.contract,folder=self.root)
        self.assertEqual([c.args[2] for c in screen.call_args_list],['poll_00','poll_complete'])
        self.assertEqual(dev.deadline,125)

    def test_expired_poll_never_starts_an_observation(self):
        dev=Mock(deadline=5)
        with patch.object(d.time,'monotonic',return_value=5),patch.object(d,'screen_snapshot') as screen:
            with self.assertRaises(TimeoutError):d.wait_for_cleanup(dev,'remote',screen_contract=self.contract,folder=self.root)
        screen.assert_not_called();dev.call.assert_not_called()


if __name__=='__main__':unittest.main()
