"""Synthetic contract tests only. No measured TRAIN fit or policy adoption."""
import unittest
import torch
import bc

torch.set_num_threads(1)
class Checks(unittest.TestCase):
    def bank(self):
        x=torch.zeros(bc.ACTIONS,bc.WIDTH);x[0,1]=1;x[1,2]=1
        return dict(version=bc.VERSION,split='TRAIN',source_kind='SYNTHETIC',x=x.tolist(),mask=[True,True]+[False]*25,
                    teacher_mask=[True]+[False]*26,group='C_CPU')
    def test_shared_network_contract(self):
        n=bc.Net();x=torch.zeros(2,27,50);mask=torch.ones(2,27,dtype=torch.bool)
        logits,critic=n(x,mask);self.assertEqual(tuple(logits.shape),(2,27));self.assertEqual(tuple(critic.shape),(2,5))
    def test_legacy_checkpoint_rejected(self):
        for name in ('A24_ROLLING_ATC_BC50_V1','S26_ROUTE_GROUP_V1'):
            with self.assertRaises(ValueError):bc.restore(dict(version=name))
    def test_actual_fit_requires_registration(self):
        with self.assertRaises(ValueError):bc.distill([self.bank()],seed=123,epochs=1)
    def test_eval_labels_rejected(self):
        f=self.bank();f['split']='EVAL'
        with self.assertRaises(ValueError):bc.distill([f],seed=1,synthetic=True,epochs=1)
    def test_invalid_teacher_mask_rejected(self):
        f=self.bank();f['teacher_mask']=[False]*26+[True]
        with self.assertRaises(ValueError):bc.distill([f],seed=1,synthetic=True,epochs=1)
    def test_synthetic_fit_restore_replay_rng_and_frozen_inference(self):
        before=torch.random.get_rng_state().clone()
        state=bc.distill([self.bank() for _ in range(4)],seed=22,synthetic=True,epochs=2)
        self.assertTrue(torch.equal(before,torch.random.get_rng_state()))
        with self.assertRaises(ValueError):bc.restore(state)
        net=bc.restore(state,allow_synthetic=True);digest=bc.network_hash(net);a=bc.choose(net,self.bank());b=bc.choose(net,self.bank())
        self.assertEqual(a,b);self.assertEqual(digest,bc.network_hash(net));self.assertEqual(a,0)
    def test_permutation_equivariance(self):
        with torch.random.fork_rng():
            torch.manual_seed(4);net=bc.Net();nn_last=net.actor[-1]
            with torch.no_grad():nn_last.weight.normal_(0,.1)
            x=torch.randn(1,27,50);mask=torch.ones(1,27,dtype=torch.bool);perm=torch.arange(26,-1,-1)
            a=net(x,mask)[0];b=net(x[:,perm],mask[:,perm])[0]
            self.assertTrue(torch.allclose(a[:,perm],b,atol=1e-6))
if __name__=='__main__':unittest.main(verbosity=2)
