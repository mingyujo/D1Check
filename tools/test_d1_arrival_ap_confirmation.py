"""PC-only checks of the exact one-session contract; never opens ADB."""
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_ap_confirmation as c
from tools import d1_arrival_plan as p


class ArrivalApConfirmationTest(unittest.TestCase):
    def test_budget_and_request_lineage(self):
        c.budget_check(c.BUDGET)
        design=p.read(c.BUNDLE)
        source={'source_plan':{'path':'source-plan.json'},'device_fingerprint':'A24'}
        prior={'entries':[{'manifest':'old.json'}]}
        template={'models':{'classification_CPU':{'identity':{},'target':{}}},'images':[{'filename':'input.jpg'}]}
        with patch.object(c.p,'read',side_effect=lambda path: design if path==c.BUNDLE else
                          prior if str(path)=='source-plan.json' else template):
            m=c.expected_manifest(source,'a'*64)
        self.assertEqual(m['requests'],design['requests'])
        self.assertEqual(m['start_ap_gate'],'numeric-ap-once-v1')
        self.assertEqual((m['scenario'],m['policy'],m['common_window_seconds']),('queue','FIXED_SPLIT',120))
        self.assertEqual((len(m['requests']),sum(r['priority']=='urgent' for r in m['requests'])),(24,6))

    def test_no_budget_expansion(self):
        for change in ({'sessions':2},{'explicit_inference':33},{'adb_commands':3001},
                       {'retry':1},{'total_seconds':1301}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                c.budget_check(dict(c.BUDGET,**change))

    def test_run_requires_explicit_approval_before_device(self):
        from tools.d1_arrival_energy_collection_device import run
        with self.assertRaisesRegex(ValueError,'approval'):
            run('no-plan.json','no-adb','no-serial','0'*64,False)

    def test_single_entry_routes_to_preflight_and_preserves_original_failure(self):
        from tools import d1_arrival_energy_collection_device as runner
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            plan_file=root/'plan.json'
            plan_file.write_text(json.dumps(dict(single_arrival_confirmation=True,budget=c.BUDGET,
                output_root=str(root/'run'),registry=str(root/'registry'))),encoding='utf-8')
            fake=type('FakeDevice',(),{'sequence':0,'deadline':None})()
            with patch.object(c,'check'),patch.object(runner,'ObservedDevice',return_value=fake),\
                 patch.object(runner.energy_device,'installation',side_effect=RuntimeError('preflight failure')) as install:
                with self.assertRaisesRegex(RuntimeError,'preflight failure'):
                    runner.run(plan_file,'fake-adb','fake-serial',p.digest(plan_file),True)
            install.assert_called_once()
            self.assertEqual(fake.command_limit,c.BUDGET['adb_commands'])
            receipt=p.read(root/'run'/'FINAL_RECEIPT.json')
            self.assertEqual(receipt['status'],'stopped_no_resume')
            self.assertIn('preflight failure',receipt['error'])
            self.assertTrue((root/'registry'/'stopped.json').is_file())


if __name__=='__main__':unittest.main()
