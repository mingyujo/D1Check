"""Pure equal-work/service/bounded wait checks; no simulator."""
import copy,unittest
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_service_list as s

class Contract(unittest.TestCase):
    def setup_controller(self):
        frozen,case=c.p.inputs(c.p.BUNDLE);x=s.ServiceList(frozen,case['initial'],feature_variant='head2+C_next')
        q=[dict(id='C',task='classification',priority='urgent',ordinal=0,arrival_ns=35e9,deadline_offset_ns=1.5e9),dict(id='D',task='detection',priority='normal',ordinal=1,arrival_ns=35e9,deadline_offset_ns=6e9)]
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        for i,ticket in enumerate(q):x.on_public_event(dict(at_ns=35e9,event_seq=i+1,request_id=ticket['id'],backend=None,event='arrived',ticket=ticket))
        x.observe(35e9,lanes);return x,q,lanes
    def test_full_work_and_common_horizon_include_unassigned_head(self):
        x,q,l=self.setup_controller();actions=x.bank(q,l,35e9);e=x.encode(q,l,35e9,actions)
        for f in e['raw']:
            if f['known']:self.assertEqual(len(x.work_intervals(f,q)),2)
        idx=x.choose(e,actions,q);self.assertEqual(idx,e['base'])
        record=x.fair_work_records[-1]
        self.assertEqual(len({v['horizon_end'] for v in record['costs'].values()}),1)
        self.assertEqual(len({v['work_count'] for v in record['costs'].values()}),1)
    def test_urgent_delay_and_normal_lateness_not_admitted(self):
        x,q,l=self.setup_controller();a=x.bank(q,l,35e9);e=x.encode(q,l,35e9,a)
        for i,item in enumerate(a):
            if q[0]['id'] in item['held']:self.assertFalse(x.admitted(i,e,a,q))
        modified=copy.deepcopy(e);i=e['base'];modified['raw'][i]['prediction']['D']['response']=42.
        j=next(k for k in range(len(a)) if k!=i)
        modified['raw'][j]=copy.deepcopy(modified['raw'][i]);modified['raw'][j]['prediction']['D']['response']=43.
        self.assertFalse(x.admitted(j,modified,a,q))
    def test_actual_request_debit_not_reset_by_other_dispatch_credit(self):
        x,q,l=self.setup_controller();x._arm(35e9,.25,['D']);x._debit(35.125e9)
        self.assertAlmostEqual(x.request_wait['D'],.125)
        x._end_hold(35.125e9,'test');x.credit=.25
        x._arm(35.125e9,.125,['D']);x._end_hold(35.25e9,'test')
        self.assertAlmostEqual(x.request_wait['D'],.25)
    def test_unknown_forecast_returns_physical_L0(self):
        x,q,l=self.setup_controller();a=x.bank(q,l,35e9);e=x.encode(q,l,35e9,a)
        e['raw'][e['base']]['known']=False
        self.assertEqual(x.choose(e,a,q),e['base']);self.assertEqual(x.fallbacks,1)

if __name__=='__main__':unittest.main()
