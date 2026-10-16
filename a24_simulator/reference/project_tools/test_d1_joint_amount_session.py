import copy,tempfile,unittest
from pathlib import Path
from tools import d1_joint_amount_session as s
from tools import d1_service_joint_rl_run as x

class SharedSession(unittest.TestCase):
    def setUp(self):
        paths={seed:x.LOCAL/'checkpoints'/f'seed{seed}_ep64.pt' for seed in x.SEEDS}
        if not all(p.exists() for p in paths.values()):self.skipTest('original local3 archives not included in ordinary shared checkout')
        self.learners=s.initial(paths)
    def test_full_three_model_and_global_rng_restore(self):
        p=s.snapshot(self.learners,dict(case=2,next_seed=1),dict(native=8,learning=5));expected=x.r.torch.rand(12)
        restored,cursor,usage=s.restore(p);actual=x.r.torch.rand(12)
        x.r.torch.testing.assert_close(expected,actual,rtol=0,atol=0);self.assertEqual(cursor,dict(case=2,next_seed=1));self.assertEqual(usage['learning'],5)
        x.r.training.restore_rng(p['session_rng'])
        for seed in x.SEEDS:self.assertEqual(s.digest(p['learners'][str(seed)]),s.digest(restored[seed].snapshot()))
    def test_atomic_session_checkpoint_without_new_learning(self):
        p=s.snapshot(self.learners,dict(case=0,next_seed=0),dict(native=0,learning=0))
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'session.pt';s.save(path,p);q=x.r.torch.load(path,map_location='cpu',weights_only=False)
            self.assertEqual(s.digest(p),s.digest(q));self.assertFalse(path.with_suffix('.tmp').exists())
    def test_other_objective_session_rejected(self):
        p=s.snapshot(self.learners,dict(case=0,next_seed=0),{});p['objective']='V2_unrelated'
        with self.assertRaises(ValueError):s.restore(p)
    def test_original_dependency_manifest_cannot_be_replaced(self):
        paths={seed:x.LOCAL/'checkpoints'/f'seed{seed}_ep64.pt' for seed in x.SEEDS}
        with self.assertRaises(ValueError):s.initial(paths,expected_dependencies={'different':'contract'})

if __name__=='__main__':unittest.main()
