import copy,unittest
from common import B,ROOT,np,torch,selector,read
from learner import Learner
from public_controller import PublicController
class Tests(unittest.TestCase):
    def make(self):return Learner(B.Learner(3701).snapshot())
    def bank(self):
        x=np.random.default_rng(6).normal(0,.2,(19,32)).astype(np.float32);mask=np.zeros(19,bool);mask[:4]=True;return dict(x=x,mask=mask,scores=np.arange(19,dtype=np.float32))
    def test_value_gradient_does_not_touch_actor_or_encoder(self):
        l=self.make();b=self.bank();_,v=l.forward(torch.from_numpy(b['x'])[None],torch.from_numpy(b['mask'])[None]);v.square().sum().backward();self.assertTrue(all(p.grad is None for p in l.actor_parameters));self.assertTrue(any(p.grad is not None for p in l.net.critic.parameters()))
    def test_split_forward_preserves_logits_and_values(self):
        l=self.make();b=self.bank();x=torch.from_numpy(b['x'])[None];m=torch.from_numpy(b['mask'])[None];a=l.forward(x,m);c=l.net(x,m);self.assertTrue(all(torch.equal(u,v) for u,v in zip(a,c)))
    def test_restore_rng_and_optimizer_storage(self):
        l=self.make();a=l.snapshot();r=Learner(a);b=self.bank();i,f=l.choose(b,True);j,g=r.choose(b,True);self.assertEqual(i,j);self.assertEqual(f['old_logp'],g['old_logp']);self.assertTrue(torch.equal(l.action_rng.get_state(),r.action_rng.get_state()))
        for p,q in zip(l.net.parameters(),r.net.parameters()):self.assertNotEqual(p.data_ptr(),q.data_ptr())
    def test_actual_split_update_and_exact_replay(self):
        l=self.make();initial=l.snapshot();r=Learner(initial)
        for ep in range(2):
            for actor in (l,r):
                fs=[]
                for i in range(4):
                    _,f=actor.choose(self.bank(),True);f['time_ns']=int((35+i*.1)*1e9);fs.append(f)
                actor.add(fs,np.full((4,5),.01))
        self.assertEqual(l.updates,1);self.assertNotEqual(initial['network_sha256'],l.snapshot()['network_sha256']);self.assertEqual(l.snapshot()['network_sha256'],r.snapshot()['network_sha256'])
    def test_temperature_probability_uses_same_behavior_likelihood(self):
        l=self.make();b=self.bank();i,f=l.choose(b,False)
        with torch.no_grad():lp=(l.net(torch.from_numpy(b['x'])[None],torch.from_numpy(b['mask'])[None])[0]/.15).log_softmax(-1)
        self.assertEqual(f['old_logp'],float(lp[0,i]));self.assertTrue(np.isfinite(f['old_logp']))
    def test_distillation_preserves_value_weights_and_action_rng(self):
        l=self.make();before=copy.deepcopy(l.net.critic.state_dict());rng=l.action_rng.get_state().clone();b=self.bank();x=np.stack([b['x']]*10);m=np.stack([b['mask']]*10);l.distill(x,m,np.zeros(10,dtype=np.int64),epochs=2)
        self.assertTrue(torch.equal(rng,l.action_rng.get_state()));self.assertTrue(all(torch.equal(before[k],v) for k,v in l.net.critic.state_dict().items()));self.assertEqual(l.episodes,0)
    def test_bank_only_selectors_obey_masks(self):
        b=self.bank();b['x'][:4,4]=0;b['x'][:4,10]=[0,3,2,1]
        self.assertEqual(selector(b,'BANK_ATC'),1);self.assertEqual(selector(b,'WEIGHTED'),0)
        for kind in ('LEX_EDF','LEX_ATC'):self.assertTrue(b['mask'][selector(b,kind)])
    def test_public_continuation_does_not_read_future_metadata(self):
        physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'))
        q=dict(request_id='visible',task='C',priority='N',scheduled_arrival_ns=35000000000,deadline_ns=38000000000,ordinal=0)
        state=dict(now_ns=35000000000,sensor=dict(temperature_c=26.,shared_z=0.,peak_c=26.),owners=[])
        vectors={('visible',r):[.01,.05,.005,.005,.005] for r in ('CPU','GPU')};first=dict(kind='WAIT',wait_ns=50000000)
        for continuation in ('EDF','ATC'):
            a=PublicController(None,physics,dict(n=1,service_stop_s=1000),'RL',continuation=continuation)
            x=a.preview(state,[q],[],vectors,first);other=copy.deepcopy(state);other['future_arrivals']=[dict(secret_actual_time=999)];y=a.preview(other,[q],[],vectors,first)
            self.assertEqual(x,y);self.assertEqual(x['nominal_unfinished'],0);self.assertFalse(x['future_arrivals_used'])
if __name__=='__main__':unittest.main()
