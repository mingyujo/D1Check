import itertools,math,unittest
import numpy as np
from tools import d1_micro_schedule_oracle as x
from tools.test_d1_ie_dispatch import ticket,lanes,controller as hand


def inputs():
    frozen,case=x.p.inputs(x.p.BUNDLE)
    return frozen,case['initial']


class MicroOracle(unittest.TestCase):
    def test_pulse_matches_original_thermal_and_energy_accounting(self):
        frozen,initial=inputs();m=x.PulseModel(frozen,initial)
        starts=np.array([[35e9,35.1e9,35.8e9,36e9]]);ends=np.array([[35.3e9,35.7e9,36.05e9,36.6e9]])
        labels=['classification_GPU','detection_CPU','classification_GPU','detection_CPU']
        energy,peak,path=m.costs(starts,ends,labels)
        jobs=[dict(state=l,start=a/1e9,end=b/1e9) for l,a,b in zip(labels,starts[0],ends[0])]
        cost=x.p.model.costs(x.p.segments(jobs,0.,180.),initial,list(range(35,181)),frozen,180.)
        self.assertAlmostEqual(float(energy[0]),cost['whole_120s_j'],places=9)
        self.assertLess(np.max(np.abs(path[0]-np.array(cost['ap_path']))),1e-10)

    def test_capacity_blocks_unmeasured_overlap_and_reuse(self):
        s=np.array([[35e9,35e9],[35e9,36e9]]);e=np.array([[36e9,36e9],[36e9,37e9]])
        self.assertEqual(x.capacity(s,e,['classification_CPU','classification_GPU']).tolist(),[False,True])
        self.assertTrue(x.capacity(s[:1],e[:1],['classification_GPU','detection_CPU'])[0])
        self.assertFalse(x.capacity(s[:1],e[:1],['classification_GPU','classification_GPU'])[0])

    def test_enumeration_conservation_and_bounded_delay(self):
        frozen,initial=inputs();m=x.PulseModel(frozen,initial);profile=x.p.profile(frozen)
        qs=[ticket('c',0),ticket('d',1,'detection',35.,6.)]
        c=x.external.Timed(frozen,initial);a=c.place(qs[0],'CPU',35.,[]);b=c.place(qs[1],'CPU',35.,[a])
        starts=np.array([[a['start']*1e9,b['start']*1e9]])
        ends,response=x.plan_arrays(qs,('CPU','CPU'),profile,starts);energy,peak,_=m.costs(starts,ends,['classification_CPU','detection_CPU'])
        ref=dict(urgent_p95_ms=float(response[0,0]/1e6),energy_j=float(energy[0]),peak_ap_c=float(peak[0]),urgent_service_failure=0,normal_service_failure=0,normal_mean_ms=float(response[0,1]/1e6))
        calendar=[dict(request_id=q['id'],backend='CPU',start_ns=s) for q,s in zip(qs,starts[0])]
        answer=x.enumerate_calendars(qs,profile,m,[ref,ref],calendar,delay_ns=200000000)
        self.assertEqual(answer['counts']['raw'],answer['counts']['visited']+answer['counts']['pruned'])
        self.assertIsNotNone(answer['energy_min_ap_cap']);self.assertLessEqual(answer['energy_min_ap_cap']['energy_j'],ref['energy_j']+1e-9)

    def test_lower_bound_does_not_exceed_a_legal_calendar(self):
        frozen,initial=inputs();m=x.PulseModel(frozen,initial);profile=x.p.profile(frozen)
        qs=[ticket('c',0),ticket('d',1,'detection',35.,6.)]
        s=np.array([[35e9,35.7e9]]);ends,_=x.plan_arrays(qs,('GPU','CPU'),profile,s);energy,_,_=m.costs(s,ends,['classification_GPU','detection_CPU'])
        self.assertLessEqual(x.lower_bound(qs,profile,m),float(energy[0]))

    def test_response_slack_can_reverse_plain_edd(self):
        frozen,initial=inputs();c=x.SlackController(frozen,initial);c.estimates=hand().estimates
        qs=[ticket('c',0,arrival=39.45),ticket('d',1,'detection',35.,6.)]
        r=c.decide(None,qs,lanes(),39.5e9,{},None,None)
        self.assertLess(qs[0]['arrival_ns']+qs[0]['deadline_offset_ns'],qs[1]['arrival_ns']+qs[1]['deadline_offset_ns'])
        self.assertEqual(r['selected']['request_id'],'d')

    def test_explicit_cpu_flex_protects_arrived_cpu_only_job(self):
        frozen,initial=inputs();c=x.SlackController(frozen,initial,True);c.estimates=hand().estimates
        c.estimates['classification_GPU_urgent']=[.2e9,.2e9,0.,0.,1.1e9] # synthetic pure function fixture, not a device coefficient
        qs=[ticket('c',0,arrival=39.6),ticket('d',1,'detection',35.55,6.)]
        r=c.decide(None,qs,lanes(),40.5e9,{},None,None)
        self.assertEqual(r['selected'],dict(request_id='c',backend='GPU'))
        self.assertEqual(r['reason'],'protect_arrived_cpu_only_deadline')

    def test_future_ticket_rejected_and_worker_release_still_owned(self):
        frozen,initial=inputs();c=x.SlackController(frozen,initial)
        with self.assertRaisesRegex(ValueError,'future'):c.decide(None,[ticket('q',0,arrival=36.)],lanes(),35e9,{},None,None)


if __name__=='__main__':unittest.main()
