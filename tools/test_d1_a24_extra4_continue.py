import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from d1_a24_extra4_continue import stable_enough_to_prepare,passive_before_APP,control
from d1_a24_laptop_validator import NS,sha256
from d1_a24_suite_dev_continue import cold_enough_to_prepare


class PreparationCases(unittest.TestCase):
    def simplified(self,t):return [{'before_ns':i*5*NS,'after_ns':i*5*NS+1000,'AP_c':t} for i in range(13)]

    def gate(self,folder):
        p=folder/'reference.json';p.write_text(json.dumps({'block_id':'b','Tref_c':27.6}))
        return {'schema':'a24-revision02-blocked-gate-v1','frozen':True,'reference_role':'MATCH_FIXED','block_id':'b',
            'block_reference_path':str(p),'block_reference_sha256':sha256(p),'Tref_c':27.6,'sensor_name':'AP','sensor_type':0,
            'tref_tolerance_c':.5,'maximum_abs_slope_c_per_min':.1,'history_ns':60*NS,'maximum_gate_wait_ns':600*NS,
            'soc_contract':'USER_SOC_GE10_20261015','minimum_SOC_percent':10,'maximum_SOC_percent':100,'require_unplugged':True,
            'hal_poll_period_ns':5*NS,'maximum_observation_gap_ns':10*NS,'status_poll_period_ns':NS,'ready_timeout_ns':180*NS,
            'session_timeout_ns':240*NS,'maximum_raw_bytes':67108864,'environment_reviewed':True,'screen_contract':'test'}

    def full(self,rows):return [{'device_elapsed_before_ns':x['before_ns'],'device_elapsed_after_ns':x['after_ns'],
                                'sensors':[{'sensor_name':'AP','sensor_type':0,'value_c':x['AP_c']}]} for x in rows]

    def test_counterexample_old_preparation_rejected_legal_MAIN_state(self):
        with tempfile.TemporaryDirectory() as t:
            g=self.gate(Path(t));samples=self.simplified(27.9);before=copy.deepcopy(g)
            self.assertFalse(cold_enough_to_prepare(samples,g['Tref_c']))
            self.assertTrue(stable_enough_to_prepare(samples,g))
            verdict=control.admission(self.full(samples),g,ready_ns=0,battery={'SOC_percent':70,'plugged':False})
            self.assertTrue(verdict['admitted']);self.assertEqual(g,before)

    def test_MAIN_still_rejects_hot_unstable_or_missing_full_history(self):
        with tempfile.TemporaryDirectory() as t:
            g=self.gate(Path(t))
            for kind in ['hot','slope','short','gap']:
                rows=self.simplified(28.2 if kind=='hot' else 27.8)
                if kind=='slope':
                    for i,x in enumerate(rows):x['AP_c']+=i*.2/12
                if kind=='short':rows=rows[:-1]
                if kind=='gap':rows=rows[:6]+rows[9:]
                with self.subTest(kind=kind):
                    self.assertFalse(stable_enough_to_prepare(rows,g))
                    self.assertFalse(control.admission(self.full(rows),g,ready_ns=0,battery={'SOC_percent':70,'plugged':False})['admitted'])

    def test_preparation_receipt_never_claims_MAIN_or_calls_APP(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);g=self.gate(base);rows=iter(self.full(self.simplified(27.9)))
            class Fake:
                def check_window(self,phase):assert phase=='NEW_SESSION'
                def sleep_ns(self,ns):pass
                def command(self,*args,**kwargs):raise AssertionError('no APP/device call from mocked predicate')
            p=base/'preparation'/'s.jsonl'
            with patch.object(control,'read_hal',side_effect=lambda c:next(rows)),patch.object(control,'run_one') as run:
                passive_before_APP(Fake(),g,p);run.assert_not_called()
            receipt=json.loads(p.with_suffix('.ready.json').read_text())
            self.assertFalse(receipt['MAIN_admitted']);self.assertTrue(receipt['post_warmup_MAIN_rules_unchanged'])
            self.assertEqual(receipt['reference_sha256'],g['block_reference_sha256'])
            self.assertEqual(receipt['Tref_c'],27.6)


if __name__=='__main__':unittest.main()
