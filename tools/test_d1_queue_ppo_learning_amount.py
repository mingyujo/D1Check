from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_queue_ppo_learning_amount as a


class LearningAmountTests(unittest.TestCase):
    def test_missing_state_cannot_fall_back_to_selected_actor(self):
        with self.assertRaisesRegex(ValueError,'EXACT_EXTENSION_BLOCKED'):
            a.require_exact_states({},[('HEAD',11),('QUEUE',11)],128)
        state=dict(identity=['HEAD',11],update=128,network={'actor.weight':0},optimizer=None,
            multipliers=[10]*4,python_rng=1,numpy_rng=1,torch_rng=1)
        with self.assertRaisesRegex(ValueError,'optimizer'):
            a.require_exact_states({('HEAD',11):state},[('HEAD',11)],128)
        with self.assertRaisesRegex(ValueError,'terminal_update_identity'):
            a.require_exact_states({('HEAD',11):dict(state,update=32)},[('HEAD',11)],128)

    def test_optimizer_presentations_are_not_independent_transitions(self):
        self.assertEqual(a.optimizer_presentations(257,8),1028)
        self.assertEqual(a.optimizer_presentations(257,3),513)
        self.assertEqual(a.optimizer_presentations(257,0),0)
        with self.assertRaises(ValueError):a.optimizer_presentations(257,9)

    def test_shared_reader_keeps_missing_measurement_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv';p.write_text('variant,seed,environment_transitions,episodes,validation_eligible\nHEAD,11,,1024,False\n',encoding='utf8')
            row=a.typed_csv(p)[0]
            self.assertIsNone(row['environment_transitions'])
            self.assertEqual(row['episodes'],1024);self.assertEqual(row['seed'],11)
            self.assertFalse(row['validation_eligible'])

    def test_future_terminal_archive_preserves_actual_pause_resume_training(self):
        cfg=a.v.fixture_config();cfg.update(train=cfg['train']*2,updates=2,validation_updates=[1,2],
            expected=dict(training=2,validation=3,test=10,reference=4,smoke=0))
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()),patch.object(a.v,'fixture_config',return_value=cfg):
            lock=Path(tmp)/'lock'
            full=a.TerminalArchiveSession(Path(tmp)/'full',fixture=True,lock=lock)
            self.assertEqual(full.execute(),'completed')
            part=a.TerminalArchiveSession(Path(tmp)/'part',fixture=True,lock=lock)
            self.assertEqual(part.execute(pause_after=3),'paused')
            resumed=a.TerminalArchiveSession(part.folder,a.v.durable.read_state(part.folder),lock=lock)
            self.assertEqual(resumed.execute(),'completed')
            name='terminal_QUEUE_seed101_update2.pt'
            payload=a.v.torch.load(full.folder/name,map_location='cpu',weights_only=False)
            other=a.v.torch.load(part.folder/name,map_location='cpu',weights_only=False)
            a.require_exact_states({('QUEUE',101):payload},[('QUEUE',101)],2)
            self.assertEqual(payload['episodes'],2);self.assertEqual(payload['selected']['seed'],101)
            self.assertEqual((full.folder/'QUEUE_seed101.json').read_bytes(),(part.folder/'QUEUE_seed101.json').read_bytes())
            for key,value in payload['network'].items():a.v.torch.testing.assert_close(value,other['network'][key],rtol=0,atol=0)
            for key,values in payload['optimizer']['state'].items():
                for field,value in values.items():a.v.torch.testing.assert_close(value,other['optimizer']['state'][key][field],rtol=0,atol=0)
            self.assertEqual(payload['python_rng'],other['python_rng'])
            a.v.np.testing.assert_equal(payload['numpy_rng'],other['numpy_rng'])
            a.v.torch.testing.assert_close(payload['torch_rng'],other['torch_rng'],rtol=0,atol=0)
            self.assertEqual((full.folder/'test.csv').read_bytes(),(part.folder/'test.csv').read_bytes())
            self.assertEqual(sum(full.s['counts'].values())+sum(resumed.s['counts'].values()),38)


if __name__=='__main__':unittest.main()
