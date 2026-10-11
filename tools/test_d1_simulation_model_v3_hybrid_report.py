import copy
from pathlib import Path
import tempfile
import unittest

from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v3_hybrid_report as report


class HybridReportTests(unittest.TestCase):
    def fixture(self,valid=2):
        rows=[]
        for mode in report.base.MODES:
            for index in range(valid):
                for name in report.MODELS:
                    value=.2 if name=='hybrid' else .4
                    rows.append(dict(session=str(index),policy=report.POLICIES[index],mode=mode,model=name,
                        mae_c=value,max_absolute_error_c=value+.1,J120_abs_j=3.,J120_signed_j=3.))
        identities=[dict(session=str(i),policy=report.POLICIES[i],J120_prediction_identity=True,
            ledger_identity=True,service_metrics_identity=True,P95_identity=True) for i in range(valid)]
        roster=[dict(status='validated' if i<valid else 'not_validated') for i in range(2)]
        return rows,roster,identities

    def test_active_and_partial_reports_do_not_claim_hybrid_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run=root/'run';run.mkdir()
            with self.assertRaisesRegex(ValueError,'FINAL_RECEIPT'):
                report.report(run,root/'output')
            self.assertFalse((root/'output').exists())
        rows,roster,ids=self.fixture(1);summary=report.aggregate_scores(rows,roster,ids)
        self.assertEqual(summary['planned_sessions'],2)
        self.assertEqual(summary['validated_sessions'],1)
        self.assertIsNone(summary['hybrid_comparison_pass'])
        self.assertEqual(summary['modes'][report.base.MODES[1]]['overall']['hybrid']['mean_AP_MAE_c'],.2)

    def test_new_gate_requires_identity_and_never_changes_parent_joint_FAIL(self):
        rows,roster,ids=self.fixture()
        summary=report.aggregate_scores(rows,roster,ids)
        self.assertTrue(summary['hybrid_comparison_pass'])
        self.assertFalse(summary['original_V3_joint_pass'])
        self.assertFalse(summary['energy_decrease_claim'])
        changed=copy.deepcopy(ids);changed[0]['ledger_identity']=False
        self.assertFalse(report.aggregate_scores(rows,roster,changed)['hybrid_comparison_pass'])
        for row in rows:
            if row['mode']==report.base.MODES[1] and row['model']=='hybrid' and row['policy']==report.POLICIES[1]:row['mae_c']=.5
        summary=report.aggregate_scores(rows,roster,ids)
        self.assertTrue(summary['hybrid_comparison_pass'])
        self.assertEqual(summary['policies_with_AP_worsening'],[report.POLICIES[1]])

    def test_future_target_mutation_changes_scores_not_blind_forecast_or_identity(self):
        original=p.read(report.base.v2.prior.MODEL);previous=p.read(report.base.V2_FILE)
        plan=p.read('output/model_v3_expert_20261010_v1/hybrid/plan/collection_plan.json')
        candidate=p.read(plan['prior_freeze']['path'])['model']
        run=report.model.ROOT/'output/model_v2_20261010_v1/user_resume/run'
        path=next(x for x in run.glob('*/validated.json') if p.read(x)['analysis_case']['policy']=='ARRIVAL_CPU96')
        c=p.read(path)['analysis_case'];manifest=p.read(path.parent/'input_manifest.json')
        first=report.evaluate_case(c,manifest,candidate,original,previous)
        changed=copy.deepcopy(c);changed['ap']=[999.]*len(changed['ap'])
        changed['power_w']=[w if t<35 else w+.7 for t,w in zip(changed['power_t'],changed['power_w'])]
        second=report.evaluate_case(changed,manifest,candidate,original,previous)
        self.assertEqual(first['forecast'],second['forecast'])
        self.assertEqual(first['identity'],second['identity'])
        self.assertNotEqual(first['scores'],second['scores'])
        self.assertTrue(first['identity']['J120_prediction_identity'])
        self.assertTrue(first['identity']['ledger_identity'])


if __name__=='__main__':unittest.main()
