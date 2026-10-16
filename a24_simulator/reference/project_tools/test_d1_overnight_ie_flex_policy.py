import copy,gzip,json,unittest
from unittest.mock import patch
import numpy as np
from tools import d1_overnight_ie_flex_policy as x


class Flex(unittest.TestCase):
    def setUp(self):
        f,i,_=x.r.h.load();self.c=x.Controller(f,i['initial']);self.old=x.r.Controller(f,i['initial'])
        self.q=[x.r.h.prior.ticket('C','classification')];self.now=35_000_000_000;self.lanes=x.r.old.core.empty_lanes(self.now)
        self.c.observe(self.now,self.lanes);self.old.observe(self.now,self.lanes)
        history={f'completed_{j}':dict(priority='urgent',response_ms=250.) for j in range(20)}
        self.c.observed_responses=copy.deepcopy(history);self.old.observed_responses=copy.deepcopy(history)
        self.base=dict(kind='single',jobs=[dict(request_id='C',backend='CPU')]);self.alt=dict(kind='single',jobs=[dict(request_id='C',backend='GPU')])
        self.ref=dict(valid=True,responses={'C':35.18},lane_end_s=36.,urgent_p95_ms=250.,urgent_misses=0,normal_misses=0,remaining_increment_j=2.,peak_ap_c=30.,global_peak_ap_c=30.)
        self.new=dict(self.ref,responses={'C':35.20},remaining_increment_j=1.9,peak_ap_c=29.9,global_peak_ap_c=29.9)
        self.risk=dict(known=False,rho=0.,gap=0.,gap_known=False,queued=0.)
    def admit(self,f=None,ref=None,action=None):return self.c.admission(action or self.alt,[f or self.new]*3,[ref or self.ref]*3,self.q,self.now,self.risk)
    def test_per_request_delay_with_same_full_P95_is_newly_admitted(self):
        self.assertEqual(self.old.admission(self.alt,[self.new]*3,[self.ref]*3,self.q,self.now,self.risk),(False,'urgent_response'))
        self.assertTrue(self.admit()[0])
    def test_P95_increase_rejected(self):self.assertEqual(self.admit(dict(self.new,urgent_p95_ms=251.)),(False,'current_observed_urgent_P95'))
    def test_current_urgent_deadline_violation_rejected(self):self.assertFalse(self.admit(dict(self.new,urgent_misses=1,responses={'C':36.6}))[0])
    def test_existing_late_request_cannot_be_made_later_even_if_count_ties(self):
        self.assertEqual(self.admit(dict(self.new,responses={'C':36.8},urgent_misses=1),dict(self.ref,responses={'C':36.7},urgent_misses=1)),(False,'individual_lateness'))
    def test_unknown_forecast_blocks_alternative(self):self.assertEqual(self.admit(dict(valid=False)),(False,'unknown_forecast'))
    def test_unknown_cooling_still_blocked(self):self.assertEqual(self.admit(action=dict(kind='cool_wait',until_ns=35_250_000_000)),(False,'unknown_observed_CPU_load_no_cooling'))
    def test_J_increase_rejected_even_when_thermal_reduces(self):self.assertEqual(self.admit(dict(self.new,remaining_increment_j=2.1)),(False,'drain_or_J'))
    def test_feature_and_candidate_ABI_equal_only_admission_mask_changes(self):
        def predict(queue,lanes,now,action,context):return copy.deepcopy(self.ref if action['jobs'][0]['backend']=='CPU' else self.new)
        with patch.object(self.old,'predict',side_effect=predict),patch.object(self.c,'predict',side_effect=predict):
            a=self.old.encode(self.q,self.lanes,self.now,[self.base,self.alt],self.q);b=self.c.encode(self.q,self.lanes,self.now,[self.base,self.alt],self.q)
        for k in ('state','candidates','physical_mask'):np.testing.assert_array_equal(a[k],b[k])
        self.assertEqual(tuple(a['mask'][:2]),(True,False));self.assertEqual(tuple(b['mask'][:2]),(True,True));self.assertNotEqual(a['schema_id'],b['schema_id'])
    def test_archived_reachable_counterexample_is_one_seed_not_three(self):
        root=x.r.h.ROOT;path=root/'output/overnight_ie_20261011_v1/items/development_Rule_09.json.gz'
        if not path.exists():self.skipTest('archived development witness unavailable in shared clean checkout')
        raw=json.loads(gzip.decompress(path.read_bytes()));found=[]
        for s in raw['snapshots']:
            if s['now_ns']!=63_072_586_416:continue
            for j,reason in enumerate(s['admissions']):
                if reason!='urgent_response':continue
                fs=s['forecasts'][j];refs=s['forecasts'][0]
                if all(f['valid'] and ref['valid'] and f['urgent_p95_ms']<=ref['urgent_p95_ms'] and f['urgent_misses']<=ref['urgent_misses'] and f['normal_misses']<=ref['normal_misses'] and f['remaining_increment_j']<=ref['remaining_increment_j'] and f['global_peak_ap_c']<=ref['global_peak_ap_c'] for f,ref in zip(fs,refs)):
                    found.append(s['actions'][j])
        self.assertTrue(found);self.assertTrue(all(q['kind']=='resource_wait' for q in found))

if __name__=='__main__':unittest.main()
