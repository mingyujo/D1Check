"""Synthetic snapshots/integrals only, no scheduling environment or fitting."""
from pathlib import Path
import copy,json,sys,unittest
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'experiments/coupled_345_20261017')]
from dynamics import Physics,Config
from repair_controller import RepairController
from repair_rewards import labels
from engine import metrics

class Nominal:
    def vector(self,q,r,state):return [.005,.025 if r=='CPU' else .02,.005,.005,.005]

class Fake:
    def choose(self,bank,collect):
        i=int(np.flatnonzero(bank['mask'])[0]);return i,dict(x=bank['x'],mask=bank['mask'],scores=bank['scores'],index=i)

class Tests(unittest.TestCase):
    def physics(self):return Physics(json.loads((ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json').read_text()),Config())
    def case(self,drain=785,n=32):return dict(n=n,service_stop_s=755,drain_stop_s=drain,temperature_c=26.)
    def state(self,n=10):return dict(now_ns=40_000_000_000,queue=[dict(request_id=str(i),ordinal=i,task='C' if i%2 else 'D',priority='U' if i%3==0 else 'N',scheduled_arrival_ns=35_000_000_000+i,queue_entry_ns=35_000_000_000+i,deadline_ns=39_000_000_000+i) for i in range(n)],owners=[],sensor=dict(temperature_c=34.,shared_z=1.,peak_c=34.,increment_so_far=.05),wait_used_ns=0)
    def call(self,n=10,drain=785):
        actor=RepairController(Nominal(),self.physics(),self.case(drain,n),'RL',Fake(),False,deadline_guard=False);actor(self.state(n));return actor.calls[-1]
    def test_eight_head_physical_abi_and_no_urgent_guard(self):
        a=self.call(50);self.assertLessEqual(len({x['request_id'] for x in a['actions'] if x['kind']=='DISPATCH'}),8)
        self.assertEqual(sum(x['kind']=='WAIT' for x in a['actions']),3);self.assertEqual(np.asarray(a['x']).shape,(19,32))
    def test_forecast_independent_of_actual_drain_endpoint(self):
        a,b=self.call(drain=785),self.call(drain=5000);self.assertEqual(a['forecasts'],b['forecasts'])
        self.assertTrue(all(x['forecast_end_s']<45 for x in a['forecasts']))
    def test_long_queue_values_remain_distinguishable(self):
        a,b=self.call(240),self.call(480);self.assertNotEqual(a['x'][0][11],b['x'][0][11]);self.assertLess(a['x'][0][11],b['x'][0][11])
    def test_low_queue_encoding_unchanged(self):self.assertAlmostEqual(self.call(96)['x'][0][11],4.)
    def test_public_forecast_local_normalizer_and_completion_energy(self):
        a=self.call(80)
        for x in a['forecasts']:
            self.assertLessEqual(x['local_normalizer'],8);self.assertIsNotNone(x['completion_time']);self.assertGreater(x['completion_total_energy'],0.)
            self.assertAlmostEqual(x['costs'][0],x['completion_total_energy']/(x['local_normalizer']*.35))
            self.assertFalse(x['future_arrivals_used'])
    def test_reward_partial_boundaries_and_original_sla_terms(self):
        p=self.physics();s=dict(temperature_c=26.,shared_z=1.);trace=[]
        for a,b,active in [(35,36,[dict(task='C',route='CPU',stage=1)]),(36,37,[]),(37,40,[])]:
            nxt,t=p.transition(s,active,b-a);trace.append(dict(start_ns=round(a*1e9),end_ns=round(b*1e9),state=s,next_state=nxt,active=active,**t));s=nxt
        q=dict(request_id='a',ordinal=0,task='C',priority='U',scheduled_arrival_ns=35_000_000_000,deadline_ns=35_500_000_000,response_ns=36_000_000_000,available_ns=37_000_000_000,route='CPU')
        result=dict(trace=trace,requests=[q],wait_used_ns=0);case=dict(n=1,temperature_c=26.,service_stop_s=37.,drain_stop_s=40.)
        m=metrics(result,case,p);frames=[dict(time_ns=35_000_000_000),dict(time_ns=36_000_000_000)]
        c,audit=labels(result,frames,case,p,m,36_500_000_000)
        self.assertTrue(np.allclose(c.sum(0)[2:4],m['cost_vector'][2:4]));self.assertEqual(audit['unfinished_at_reference'],1)
        self.assertAlmostEqual(c[:,0].sum()*.35,sum(t['increment']+t['baseline'] for t in trace[:2]));self.assertEqual(c[:,4].sum(),1.)
        self.assertLess(audit['max_telescope_error'],1e-9)

    def test_paired_optimizer_and_rng_storage_are_independent(self):
        import gzip,io,torch
        from paired_initialization import independently_restored
        checkpoint=ROOT/'results/COUPLED_345_20261017_01/SEED_3701_EP064.pt.gz'
        snapshot=torch.load(io.BytesIO(gzip.decompress(checkpoint.read_bytes())),map_location='cpu',weights_only=False)
        a=independently_restored(snapshot,3701);b=independently_restored(snapshot,3701)
        state_a=a.optimizer.state_dict()['state'];state_b=b.optimizer.state_dict()['state'];count=0;first=None
        self.assertEqual(state_a.keys(),state_b.keys())
        for key in state_a:
            for name,value in state_a[key].items():
                other=state_b[key][name]
                if torch.is_tensor(value):
                    self.assertTrue(torch.equal(value,other));self.assertNotEqual(value.data_ptr(),other.data_ptr());count+=1
                    if first is None:first=(value,other.clone(),other)
        self.assertGreater(count,0)
        first[0].add_(1);self.assertTrue(torch.equal(first[1],first[2]))
        self.assertTrue(torch.equal(a.action_rng.get_state(),b.action_rng.get_state()))
        before=b.action_rng.get_state().clone();torch.rand(1,generator=a.action_rng)
        self.assertTrue(torch.equal(before,b.action_rng.get_state()))
        self.assertTrue(torch.equal(a.shuffle_rng.get_state(),b.shuffle_rng.get_state()))

if __name__=='__main__':unittest.main()
