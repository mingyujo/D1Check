import copy
from pathlib import Path
import tempfile
import unittest

from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v3 as model
from tools import d1_simulation_model_v3_report as report


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = p.read(v2.prior.MODEL)
        cls.previous = p.read(report.V2_FILE)
        cls.candidate = dict(version=model.VERSION, thermal=model.baseline_head(cls.original,'thermal'),
                             energy=model.baseline_head(cls.original,'energy'),
                             original_model=dict(sha256=v2.prior.MODEL_SHA))
        run = model.ROOT/'output/model_v2_20261010_v1/user_resume/run'
        cls.path = next(path for path in run.glob('*/validated.json')
                        if p.read(path)['analysis_case']['policy'] == 'ARRIVAL_CPU96')
        cls.case = p.read(cls.path)['analysis_case']
        cls.manifest = p.read(cls.path.parent/'input_manifest.json')

    def test_future_targets_change_scores_but_not_blind_forecast(self):
        first = report.evaluate_case(self.case, self.manifest, self.candidate, self.original, self.previous)
        changed = copy.deepcopy(self.case)
        changed['ap'] = [999.]*len(changed['ap'])
        changed['power_w'] = [w if t<35 else w+.5 for t,w in zip(changed['power_t'], changed['power_w'])]
        second = report.evaluate_case(changed, self.manifest, self.candidate, self.original, self.previous)
        self.assertEqual(first['forecast'],second['forecast'])
        self.assertEqual(first['forecast_service'],second['forecast_service'])
        self.assertNotEqual(first['scores'],second['scores'])
        self.assertEqual(len(first['scores']),6)
        self.assertTrue(all(r['mode'] in report.MODES for r in first['scores']))

    def test_partial_missing_sessions_keep_planned_denominator_and_cannot_pass(self):
        roster=[dict(status='validated' if i<3 else 'not_validated') for i in range(4)]
        scores=[]
        for mode in report.MODES:
            for i in range(3):
                for name in report.MODELS:
                    value=1. if name=='v3' else 2.
                    scores.append(dict(session=str(i),policy=report.POLICIES[i],mode=mode,model=name,
                        mae_c=value,max_absolute_error_c=value+1,J120_abs_j=value*10,J120_signed_j=value*10))
        result=report.aggregate_scores(scores,roster)
        self.assertEqual(result['planned_sessions'],4)
        self.assertEqual(result['validated_sessions'],3)
        self.assertEqual(result['missing_sessions'],1)
        self.assertIsNone(result['joint_cost_error_decrease_pass'])
        row=result['modes'][report.MODES[1]]['overall']['v3']
        self.assertEqual(row['evaluated_sessions'],3)
        self.assertEqual(row['mean_AP_MAE_c'],1.)
        self.assertEqual(row['mean_J120_abs_j'],10.)

    def test_all_four_require_both_cost_means_to_decrease_and_A_does_not_override_B(self):
        roster=[dict(status='validated') for _ in range(4)]
        rows=[]
        for mode in report.MODES:
            for i in range(4):
                for name in report.MODELS:
                    value=.5 if name=='v3' and mode==report.MODES[0] else 2. if name=='v3' else 1.
                    rows.append(dict(session=str(i),policy=report.POLICIES[i],mode=mode,model=name,
                        mae_c=value,max_absolute_error_c=value,J120_abs_j=value,J120_signed_j=value))
        result=report.aggregate_scores(rows,roster)
        self.assertFalse(result['joint_cost_error_decrease_pass'])
        self.assertFalse(result['AP_mean_improved'])

    def test_active_run_is_rejected_without_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run=root/'run';run.mkdir();out=root/'report'
            with self.assertRaisesRegex(ValueError,'FINAL_RECEIPT'):
                report.report(run,out)
            self.assertFalse(out.exists())

    def test_forecast_service_p95_excludes_failed_and_retains_all_arrivals(self):
        ledger=[dict(priority='urgent',status=s,response_ns=t,deadline_offset_ns=1_500_000_000)
                for s,t in [('succeeded',1_000_000_000),('succeeded',2_000_000_000),('failed',9_000_000_000)]]
        ledger.append(dict(priority='normal',status='unfinished',deadline_offset_ns=6_000_000_000))
        out=report.forecast_service(dict(ledger=ledger))
        self.assertEqual(out['urgent']['planned'],3)
        self.assertEqual(out['urgent']['response_P95_ms'],2000)
        self.assertEqual(out['urgent']['service_success_rate'],1/3)
        self.assertEqual(out['urgent']['completion_success_rate'],2/3)
        self.assertIsNone(out['normal']['response_P95_ms'])


if __name__=='__main__':
    unittest.main()
