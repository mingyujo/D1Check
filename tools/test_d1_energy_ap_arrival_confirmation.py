import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_energy_ap_arrival_confirmation as c


class ArrivalConfirmationTest(unittest.TestCase):
    def test_start_sample_is_retrospective_and_bounded(self):
        s = {'mono_ns': 9_000_000_000, 'before_ns': 8_900_000_000,
             'after_ns': 9_100_000_000, 'AP': '32.6', 'thermal_status': '0'}
        v = c.start_ap_evidence([s], 10_000_000_000, 32.5, 34.0)
        self.assertTrue(v['eligible'])
        self.assertFalse(v['proves_start_gate'])
        self.assertEqual(c.start_ap_evidence([s], 13_000_000_000, 32.5, 34.0)['reason'], 'stale_sample')
        self.assertEqual(c.start_ap_evidence([], 10_000_000_000, 32.5, 34.0)['reason'], 'missing_before_start')
        self.assertEqual(c.start_ap_evidence([{**s, 'AP':'32.3'}], 10_000_000_000, 32.5, 34.0)['reason'],
                         'outside_initial_support')
        self.assertEqual(c.start_ap_evidence([{**s, 'AP':''}], 10_000_000_000, 32.5, 34.0)['reason'],
                         'missing_numeric_ap')
        self.assertEqual(c.start_ap_evidence([{**s, 'after_ns':13_000_000_000}], 14_000_000_000, 32.5, 34.0)['reason'],
                         'uncertain_clock')

    def test_fixed_input_and_check_cannot_become_runnable(self):
        frozen = {'version':'energy-ap-state-regimen-fit-v1',
                  'initial_ap_development_range_c':[32.5,34.0],
                  'ap_development_observed_range_c':[32.5,39.5],
                  'states':['classification_CPU','detection_GPU','resident_idle']}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); fp=root/'frozen.json'; fp.write_text(json.dumps(frozen),encoding='utf-8')
            with patch.object(c,'FROZEN_SHA',c.sha(fp)), patch.object(c,'screen_raw',return_value={'source':'fixture'}):
                result=c.prepare(fp,root,root/'bundle')
                self.assertFalse(result['runnable'])
                m=json.loads((root/'bundle/input_manifest.json').read_text(encoding='utf-8'))
                self.assertEqual([r['offset_ms'] for r in m['requests']],list(range(0,4800,200)))
                self.assertEqual((m['planned_requests'],m['session_budget'],m['device_command_budget']),(24,0,0))
                m['session_budget']=1
                c.write(root/'bundle/input_manifest.json',m)
                with self.assertRaisesRegex(ValueError,'cannot consume'):
                    c.check(root/'bundle/input_manifest.json')


if __name__=='__main__': unittest.main()
