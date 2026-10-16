from pathlib import Path
import json,sys,unittest
from cost_adapter import CostObserver,ROOT
import state_cost as C
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G

class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=CostObserver()
    def test_all_eight_saved_observations(self):
        witness=json.loads((ROOT/'results/COMPETITION_WITNESS_V2_20261017_01/RESULT.json').read_text(encoding='utf-8'))
        expected=json.loads((ROOT/'results/COMPETITION_COST_COMPARISON_20261017_01/RESULT.json').read_text(encoding='utf-8'))
        for a,b in zip(witness['cases'],expected['cases']):
            for row,metric in zip(a['rows'],b['metrics']):
                cost=self.model.observe(row,*a['common_work_window_s'])
                self.assertEqual(cost['conditional_state_cost'],metric['new_state_cost'])
                self.assertEqual(cost['native_current_index'],metric['native_current_index'])
    def test_novel_schedule_not_a_lookup(self):
        summary={'gantt':[dict(task='C',route='CPU',start_s=40.,end_s=41.)]}
        r=self.model.observe(summary,35.,50.)
        self.assertGreater(r['conditional_state_cost']['increment_J_proxy'],0.)
        self.assertEqual(r['native_current_index']['status'],'CONDITIONAL_NATIVE_SENSOR_INDEX')
        self.assertEqual(r['simulations_started'],0)
    def test_future_activity_is_not_charged(self):
        r=self.model.observe({'gantt':[dict(task='C',route='CPU',start_s=60.,end_s=61.)]},35.,50.)
        self.assertEqual(r['conditional_state_cost']['increment_J_proxy'],0.)
    def test_annotation_preserves_original(self):
        s={'gantt':[],'policy':'TEST','legacy_energy':123.};before=json.dumps(s,sort_keys=True)
        result=self.model.annotate(s,35.,50.)
        self.assertEqual(json.dumps(s,sort_keys=True),before);self.assertEqual(result['legacy_energy'],123.)
        self.assertNotIn('cost_model_v2',s)
    def test_portable_relative_pin_paths(self):
        self.assertTrue(all(not Path(p['path']).is_absolute() and ':' not in p['path'] for p in self.model.bundle['pins']))
    def test_no_energy_promotion(self):
        r=self.model.observe({'gantt':[dict(task='D',route='GPU',start_s=40.,end_s=41.)]},35.,50.)
        self.assertIsNone(r['measured_J']);self.assertIsNone(r['energy_CI']);self.assertIsNone(r['energy_error_J'])
        self.assertEqual(r['native_current_index']['status'],'UNQUALIFIED_ROUTE_SUPPORT')

if __name__=='__main__':
    op=G.read(sys.argv[1]);G.OWN_TOKENS+=('competition_cost_20261017','s26-state-aware-atc-','state_recovery_owner')
    reg=G.read(ROOT/'models/registration.json');G.process_guard(Path(__file__).resolve(),reg['known_PS_producer_paths']);G.free_guard([ROOT,'D:/'])
    for p in op['pins']:G.pin(p)
    out=ROOT/op['output_dir'];G.require(not out.exists(),'Consumed test output');out.mkdir(parents=True)
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdapterTests))
        G.require(result.wasSuccessful(),'Adapter fixtures failed')
        G.write_new(out/'RESULT.json',dict(status='PASS_PORTABLE_COST_ADAPTER',tests=result.testsRun,
                     operation_sha256=G.sha(sys.argv[1]),source_sha256=G.sha(__file__),saved_schedule_comparisons=8,
                     new_environment=0,new_fit=0,NN_training=0,utc=G.now()))
    except BaseException as e:
        G.write_new(out/'FAILURE.json',dict(error=str(e),retry=False));raise
