import copy,unittest
from tools import d1_rolling_prefix_selection as x
def forecast(**changes):
    f=dict(valid=True,state_key='state0',global_peak_ap_c=31.,peak_ap_c=31.,remaining_increment_j=2.,
        urgent_misses=0,normal_misses=0,urgent_p95_ms=200.,lane_end_s=50.)
    f.update(changes);return f
def values(f):return {c:dict(f) for c in x.CONTEXTS}
def action(rid='C',backend='CPU'):return dict(kind='single',jobs=[dict(request_id=rid,backend=backend)])
def candidate(rid='C',backend='GPU',**changes):
    f=forecast();f.update(changes)
    return dict(action=action(rid,backend),state_key='state0',semantics=x.DISPATCH,forecasts=values(f))
def choose(candidates,references,band_action,past=30.):
    return x.select(candidates,references,band_action,past_peak_c=past,state_key='state0',now_ns=35e9)
class Selection(unittest.TestCase):
    def test_rejected_plan_winner_does_not_hide_safe_alternative_prefix(self):
        bad=candidate(global_peak_ap_c=31.1,peak_ap_c=31.1);good=candidate('D','CPU',remaining_increment_j=1.9)
        out=choose([bad,good],values(forecast()),action())
        self.assertEqual(out['chosen'],good);self.assertEqual(out['admissible'],1)
    def test_future_peak_only_is_not_global_KPI_gain(self):
        out=choose([candidate(peak_ap_c=30.)],values(forecast(peak_ap_c=30.5)),action(),past=31.)
        self.assertIsNone(out['chosen']);self.assertEqual(out['future_only'],1)
    def test_energy_only_gain_is_admissible(self):
        self.assertIsNotNone(choose([candidate(remaining_increment_j=1.9)],values(forecast()),action())['chosen'])
    def test_thermal_only_gain_is_admissible(self):
        self.assertIsNotNone(choose([candidate(global_peak_ap_c=30.8,peak_ap_c=30.8)],values(forecast()),action())['chosen'])
    def test_any_context_service_loss_rejects(self):
        c=candidate(remaining_increment_j=1.9);c['forecasts']['long_context']['normal_misses']=1
        self.assertIsNone(choose([c],values(forecast()),action())['chosen'])
    def test_same_action_with_different_forecasts_is_ambiguous(self):
        a=candidate(remaining_increment_j=1.9);b=candidate(remaining_increment_j=1.8)
        out=choose([a,b],values(forecast()),action());self.assertIsNone(out['chosen'])
        self.assertEqual(out['rejected'][0][1],'ambiguous_same_prefix_forecast')
    def test_exact_duplicate_is_scored_once_and_input_preserved(self):
        a=candidate(remaining_increment_j=1.9);snapshot=copy.deepcopy(a)
        out=choose([a,copy.deepcopy(a)],values(forecast()),action())
        self.assertEqual(out['admissible'],1);self.assertEqual(a,snapshot)
    def test_nan_missing_reference_and_same_Band_are_not_improvement(self):
        self.assertIsNone(choose([candidate(remaining_increment_j=float('nan'))],values(forecast()),action())['chosen'])
        self.assertIsNone(choose([candidate()],{},action())['chosen'])
        self.assertIsNone(choose([candidate(backend='CPU',remaining_increment_j=1.9)],values(forecast()),action())['chosen'])
    def test_legacy_wait_forced_dispatch_projection_is_rejected(self):
        a=dict(kind='cool_wait',until_ns=40e9,hold_signature=[['D'],[['CPU',None],['GPU',None]]])
        c=dict(action=a,state_key='state0',semantics='legacy_wait_then_force_D_CPU',forecasts=values(forecast()))
        out=choose([c],values(forecast()),action());self.assertIsNone(out['chosen'])
        self.assertEqual(out['rejected'][0][1],'unverified_execution_semantics')
    def test_wait_must_not_commit_future_request(self):
        with self.assertRaises(ValueError):x.signature(dict(kind='resource_wait',hold_signature=[],jobs=[dict(request_id='future',backend='CPU')]))
    def test_physical_future_and_busy_capacity(self):
        queue=[dict(id='C',task='classification',arrival_ns=35e9),dict(id='D',task='detection',arrival_ns=35e9)]
        lanes={b:dict(request=None) for b in ('CPU','GPU')}
        plan=[dict(request_id='C',backend='GPU'),dict(request_id='D',backend='CPU')]
        self.assertEqual(x.immediate_action(plan,queue,lanes,35e9)['kind'],'bundle')
        lanes['GPU']['request']=queue[0];self.assertIsNone(x.immediate_action(plan,queue,lanes,35e9))
        with self.assertRaises(ValueError):x.immediate_action(plan,queue,lanes,34e9)
        with self.assertRaises(ValueError):x.immediate_action([dict(request_id='D',backend='GPU')],queue,{b:dict(request=None) for b in lanes},35e9)
    def test_cpu_classifier_does_not_create_unsupported_parallel_pair(self):
        queue=[dict(id='C',task='classification',arrival_ns=35e9),dict(id='D',task='detection',arrival_ns=35e9)]
        lanes={b:dict(request=None) for b in ('CPU','GPU')}
        plan=[dict(request_id='C',backend='CPU'),dict(request_id='D',backend='CPU')]
        self.assertEqual(x.immediate_action(plan,queue,lanes,35e9)['kind'],'single')
    def test_global_peak_cannot_drop_below_shared_past_peak(self):
        bad=candidate(global_peak_ap_c=30.8,peak_ap_c=30.5)
        out=choose([bad],values(forecast(peak_ap_c=30.5)),action(),past=31.)
        self.assertIsNone(out['chosen'])
    def test_symbolic_Band_alias_and_unresolved_reference_reject(self):
        c=candidate(remaining_increment_j=1.9);c['action']=dict(kind='band');c['semantics']=x.WAIT
        self.assertIsNone(choose([c],values(forecast()),action())['chosen'])
        self.assertEqual(choose([candidate()],values(forecast()),dict(kind='band'))['reason'],'unresolved_band_action')
    def test_mismatched_state_keys_reject(self):
        c=candidate(remaining_increment_j=1.9);c['forecasts']['mean']['state_key']='other'
        self.assertIsNone(choose([c],values(forecast()),action())['chosen'])
        c=candidate(remaining_increment_j=1.9);c['state_key']='other'
        self.assertIsNone(choose([c],values(forecast()),action())['chosen'])
    def test_bundle_and_wait_signature_contract(self):
        with self.assertRaises(ValueError):x.signature(dict(kind='bundle',jobs=[dict(request_id='a',backend='CPU'),dict(request_id='b',backend='CPU')]))
        with self.assertRaises(ValueError):x.signature(dict(kind='cool_wait',hold_signature=[]))
        with self.assertRaises(ValueError):x.signature(dict(kind='resource_wait',hold_signature=[],until_ns=40e9))
        c=candidate(remaining_increment_j=1.9);c['action']=dict(kind='cool_wait',hold_signature=[],until_ns=34e9);c['semantics']=x.WAIT
        self.assertIsNone(choose([c],values(forecast()),action())['chosen'])
if __name__=='__main__':unittest.main()
