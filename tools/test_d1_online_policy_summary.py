import json
import tempfile
import unittest
from pathlib import Path
from tools.d1_online_policy_summary import summarize

class SummaryTests(unittest.TestCase):
    def test_whole_and_prospective_windows_conserve_signed_error(self):
        output=dict(energy_path=[dict(common_s=t,predicted_j=2*t) for t in range(121)],energy_signed_error_j=120.,whole_120s_j=240.,ap_scores={'mae_c':.1})
        service={k:dict(p95_ms=1.,deadline_met=96) for k in ('actual_urgent','predicted_urgent','actual_all','predicted_all')}
        c=dict(id='fixture',phase='confirmation',policy='CPU',common_start_ap_c=30.,observed_120s_j=120.,
            outputs={'arrival_forecast':output},observed_energy_path=[dict(common_s=t,observed_j=float(t)) for t in range(1,121)],
            actual_segments=[dict(start_s=0,end_s=120,state='idle')],timing=[dict(dispatch_error_ms=2,lane_error_ms=-3)],service=service)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'evaluation.json').write_text(json.dumps([c]))
            r=summarize(root,root/'out')[0]
            self.assertEqual(r['signed_120_j'],120.);self.assertEqual(r['signed_future_35_120_j'],85.)
            self.assertEqual(r['positive_5s_residual_j']+r['negative_5s_residual_j'],120.)
            self.assertEqual(r['parallel_s'],0.);self.assertEqual(r['lane_mae_ms'],3.)
            output['energy_signed_error_j']=0
            (root/'evaluation.json').write_text(json.dumps([c]))
            with self.assertRaisesRegex(ValueError,'accounting'):summarize(root,root/'bad')

    def test_same_initial_comparison_uses_response_duration_not_absolute_time(self):
        from unittest.mock import patch
        from tools.d1_online_policy_summary import compare_same_initial
        from tools import d1_online_policy_model as model
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'initial_inputs.json').write_text(json.dumps([dict(id=str(i),phase='confirmation',policy=model.POLICIES[0],initial={},manifest_requests=[]) for i in range(2)]))
            (root/'model.json').write_text('{}')
            ledger=[dict(priority='urgent',arrival_ns=35000000000,response_ns=1000000000,deadline_offset_ns=1500000000) for _ in range(96)]
            with patch.object(model,'forecast',return_value=({'ledger':ledger},[])),patch.object(model,'costs',return_value=dict(whole_120s_j=120,prospective_35_120s_j=85,ap_path=[30,31])):
                rows=compare_same_initial(root,root)
            self.assertEqual(len(rows),3)
            self.assertTrue(all(r['urgent_p95_ms']==1000 and r['deadline_met']==96 for r in rows))

if __name__=='__main__':unittest.main()
