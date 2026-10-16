"""Independent scalar exhaustive reference, no new environment starts."""
import itertools,unittest
import numpy as np
from tools import d1_micro_schedule_oracle as x
from tools.test_d1_ie_dispatch import ticket,lanes,controller as hand


class Certificate(unittest.TestCase):
    def test_worker_release_phase_does_not_make_lane_available(self):
        frozen,case=x.p.inputs(x.p.BUNDLE);c=x.SlackController(frozen,case['initial']);c.estimates=hand().estimates
        ls=lanes();ls['CPU']=dict(request=ticket('running',1),phase='WORKER_RELEASED',since=35.8e9,dispatch=35e9)
        out=c.decide(None,[ticket('queued',0)],ls,35.9e9,{},None,None)
        self.assertIsNone(out['selected']);self.assertGreater(out['wait_until_ns'],35.9e9)

    def test_vector_minima_and_safe_pruning_equal_scalar_all_calendars(self):
        frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial'];profile=x.p.profile(frozen);model=x.PulseModel(frozen,initial)
        qs=[ticket('c',0),ticket('d',1,'detection',35.,6.)]
        end_c=35e9+sum(profile[x.p.key(qs[0],'CPU')]);band=[dict(request_id='c',backend='CPU',start_ns=35e9),dict(request_id='d',backend='CPU',start_ns=end_c)]
        starts=np.array([[35e9,end_c]]);ends,response=x.plan_arrays(qs,('CPU','CPU'),profile,starts);j,ap,_=model.costs(starts,ends,['classification_CPU','detection_CPU'])
        ref=dict(energy_j=float(j[0]),peak_ap_c=float(ap[0]),urgent_p95_ms=float(response[0,0]/1e6),normal_mean_ms=float(response[0,1]/1e6),urgent_service_failure=0,normal_service_failure=0)
        answer=x.enumerate_calendars(qs,profile,model,[ref,ref],band,delay_ns=200000000)
        domains=[sorted(set([q['arrival_ns']+k*100000000 for k in range(3)]+[b['start_ns']])) for q,b in zip(qs,band)]
        candidates=[];raw=0
        for assignment in itertools.product(*(x.p.backends(q) for q in qs)):
            for times in itertools.product(*domains):
                raw+=1;jobs=[];responses=[]
                for q,backend,start in zip(qs,assignment,times):
                    now=float(start);point=None
                    for phase,d in enumerate(profile[x.p.key(q,backend)]):
                        now+=d
                        if phase==(1 if q['priority']=='urgent' else 2):point=round(now-q['arrival_ns'])
                    jobs.append(dict(state=q['task']+'_'+backend,start=round(start)/1e9,end=round(now)/1e9));responses.append(point)
                overlap=min(a['end'] for a in jobs)>max(a['start'] for a in jobs)
                pair='+'.join(sorted(a['state'] for a in jobs))
                if overlap and (assignment[0]==assignment[1] or pair not in x.p.STATES):continue
                if responses[0]/1e6>ref['urgent_p95_ms']+1e-9 or any(r>q['deadline_offset_ns'] for q,r in zip(qs,responses)):continue
                cost=x.p.model.costs(x.p.segments(jobs,0.,180.),initial,list(range(35,181)),frozen,180.)
                candidates.append((cost['whole_120s_j'],max(cost['ap_path'])))
        scalar_j=min(j for j,t in candidates if t<=ref['peak_ap_c']+1e-9)
        scalar_ap=min(t for j,t in candidates if j<=ref['energy_j']+1e-9)
        self.assertEqual(raw,answer['counts']['raw'])
        self.assertAlmostEqual(scalar_j,answer['energy_min_ap_cap']['energy_j'],places=10)
        self.assertAlmostEqual(scalar_ap,answer['ap_min_energy_cap']['peak_ap_c'],places=10)


if __name__=='__main__':unittest.main()
