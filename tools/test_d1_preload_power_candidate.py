import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.d1_preload_power_candidate import prepare, evaluate_case, FROZEN_SHA


class PreloadPowerCandidateTest(unittest.TestCase):
    def setUp(self):
        self.contract=json.loads((Path(__file__).parents[1]/'docs/results/resident_power_candidate_01/contract.json').read_text())
        self.powers={'resident_idle':1.2,'detection_CPU':2.0}
        samples=[dict(relative_ns=i*10**9,read_start_ns=i*10**9-10**8,read_end_ns=i*10**9+10**8,
            current_raw=-250,voltage_mV=4000,current_valid=True,plugged=0,active_count=0,
            resident_keys=self.contract['required_resident_keys'],phase='common_window') for i in range(-30,122)]
        self.case=dict(case='fixture',baseline_start_ns=-30*10**9,samples=samples,states=[
            dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=40.,state='detection:CPU'),
            dict(start_s=40.,end_s=120.,state='idle')])

    def test_prefix_information_boundary_and_increment_preserved(self):
        original=copy.deepcopy(self.case)
        info,power,_=prepare(self.case,self.contract,self.powers)
        self.assertEqual((info['prefix_start_s'],info['prefix_end_s']),(13.,32.))
        self.assertLess(info['latest_read_end_s'],32.5)
        self.assertAlmostEqual(info['mean_preload_w'],1.)
        self.assertAlmostEqual(power['detection_CPU']-power['resident_idle'],.8)
        self.assertEqual(original,self.case)

    def test_future_power_cannot_change_prediction(self):
        a,rows,_=evaluate_case(self.case,self.contract,self.powers)
        for x in self.case['samples']:
            if x['relative_ns']>=35*10**9:x['current_raw']=-500
        b,changed,_=evaluate_case(self.case,self.contract,self.powers)
        self.assertEqual(a,b)
        self.assertEqual([x['candidate_j'] for x in rows],[x['candidate_j'] for x in changed])
        self.assertNotEqual(rows[0]['observed_j'],changed[0]['observed_j'])
        self.assertIsNone(a['full_120s_candidate_j'])

    def test_bad_prefix_rejected_without_fallback(self):
        for field,value in [('active_count',1),('resident_keys',[]),('plugged',1),('current_valid',False),('read_start_ns',40*10**9)]:
            c=copy.deepcopy(self.case);next(x for x in c['samples'] if x['relative_ns']==20*10**9)[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):prepare(c,self.contract,self.powers)
        self.case['samples']=[x for x in self.case['samples'] if not 20*10**9<=x['relative_ns']<=25*10**9]
        with self.assertRaisesRegex(ValueError,'prefix missing'):prepare(self.case,self.contract,self.powers)

    def test_future_missing_is_null_and_phase_conservation(self):
        _,rows,_=evaluate_case(self.case,self.contract,self.powers)
        self.assertAlmostEqual(rows[0]['candidate_j'],sum(x['candidate_j'] for x in rows[1:]))
        self.assertAlmostEqual(rows[0]['observed_j'],85.)
        self.case['samples']=[x for x in self.case['samples'] if not 50*10**9<=x['relative_ns']<=60*10**9]
        info,rows,_=evaluate_case(self.case,self.contract,self.powers)
        self.assertEqual(info['status'],'partial_score_missing')
        self.assertIsNone(rows[0]['observed_j']);self.assertIsNone(rows[0]['candidate_error_j'])

    def test_prefix_endpoint_loss_is_not_shifted_to_older_data(self):
        self.case['samples']=[x for x in self.case['samples'] if not 30*10**9<=x['relative_ns']<=34*10**9]
        with self.assertRaisesRegex(ValueError,'edge missing or stale'):prepare(self.case,self.contract,self.powers)

    def test_unsupported_map_negative_power_and_contract_change_rejected(self):
        c=copy.deepcopy(self.case);c['states'][1]['state']='unsupported'
        with self.assertRaisesRegex(ValueError,'unsupported'):prepare(c,self.contract,self.powers)
        c=copy.deepcopy(self.case);c['states'][1]['start_s']=36.
        with self.assertRaisesRegex(ValueError,'gap'):prepare(c,self.contract,self.powers)
        powers=dict(self.powers,detection_CPU=.1)
        with self.assertRaisesRegex(ValueError,'nonpositive'):prepare(self.case,self.contract,powers)
        self.contract['prefix_end_before_first_dispatch_seconds']=-5
        with self.assertRaisesRegex(ValueError,'contract changed'):prepare(self.case,self.contract,self.powers)

    def test_actual_cli_output_and_occupied_output_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bundle=root/'input.json';contract=root/'contract.json';out=root/'result'
            bundle.write_text(json.dumps(dict(frozen_sha256=FROZEN_SHA,original_power_w=self.powers,cases=[self.case])))
            contract.write_text(json.dumps(self.contract))
            cmd=[sys.executable,'-X','utf8','-B','-m','tools.d1_preload_power_candidate','evaluate',
                 '--bundle',str(bundle),'--contract',str(contract),'--output',str(out)]
            first=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            self.assertEqual(first.returncode,0,first.stderr)
            receipt=(out/'summary.json').read_bytes()
            self.assertEqual(json.loads(receipt)['device_commands'],0)
            self.assertTrue((out/'comparison.svg').exists())
            second=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(second.returncode,0)
            self.assertIn('fresh candidate output only',second.stderr)
            self.assertEqual(receipt,(out/'summary.json').read_bytes())


if __name__=='__main__':unittest.main()
