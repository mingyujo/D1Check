import inspect,unittest
from tools import d1_rolling_list_rl_run as x

class Contract(unittest.TestCase):
    def test_case_split_and_bounded_budget_arithmetic(self):
        train=x.cases(range(826010001,826010009),True);dev=x.cases((826020101,826020102))
        self.assertEqual(len(train),32);self.assertEqual(len(dev),24)
        self.assertFalse({r['seed'] for r in train}&{r['seed'] for r in dev})
        self.assertEqual(4+32+3*32+4+24*5+24*3*2+24*3,472)
        self.assertLessEqual(472+72,572);self.assertEqual(3*32+4,100)
    def test_resume_writes_separate_checkpoint_not_expected_original(self):
        source=inspect.getsource(x.train_episode);self.assertIn("phase=='train' else phase+'_'",source)
    def test_no_best_seed_or_automatic_main(self):
        source=inspect.getsource(x.run);self.assertIn('for seed in SEEDS:',source);self.assertIn('automatic_adoption=False',source)
        self.assertNotIn('range(32,64)',source)
    def test_cache_cannot_advance_consumed_training_episode(self):
        self.assertIn('matching saved learner cursor',inspect.getsource(x.train_episode))
        with self.assertRaises(ValueError):x.restore_frames({})

if __name__=='__main__':unittest.main()
