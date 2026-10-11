"""Journal/cap/cache tests use no simulator, controller or optimizer."""
import tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime,timezone
from tools import d1_joint_amount_cli as x

class DesktopLedger(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        reg=dict(registered_utc=datetime.now(timezone.utc).isoformat(),active_seconds=100,reserve_seconds=10,canonical_source_sha256={},inputs_sha256=x.x.r.c.digest({}),model_export_sha256=x.x.sha(x.x.h.MODEL),parent_checkpoints={},native_cap=2,learning_cap=1,phase_caps=dict(train=1,reference=1))
        # Standalone copies have no .git; the test registration needs the same
        # exported seed-registry lock as a real prepared desktop task.
        reg['arrival_seed_registry_sha256']=x.registry()[1]
        x.x.write(self.path/'registration.json',reg);x.x.write(self.path/'inputs.json',{})
    def start(self):
        b=x.Budget(self.path);q=dict(number=1,identity='train_11_0000',phase='train',case={},learning=True,status='started');b.rows.append(q);b.append(q);return b,q
    def test_consume_survives_reload_and_counts_parent(self):
        b,q=self.start();again=x.Budget(self.path)
        self.assertEqual(again.used()['native_starts'],1);self.assertEqual(again.used()['learning_starts'],1);self.assertEqual(again.used()['cumulative_V1_lineage_learning'],193)
    def test_learning_cap_blocks_before_any_environment(self):
        b,q=self.start()
        with self.assertRaises(TimeoutError):b.call('new','train',{},None,True)
    def test_cached_learning_is_not_reexecuted_or_replayed(self):
        b,q=self.start();q.update(status='completed',sha256='unused');b.append(dict(event='completed',**q));again=x.Budget(self.path)
        with self.assertRaises(ValueError):again.call('train_11_0000','train',{},None,True)
    def test_paused_active_time_is_charged_once_on_resume(self):
        x.x.write(self.path/'clock.json',dict(consumed_active_seconds=10.,running_since=None))
        with patch.object(x.time,'time',return_value=1000.):b=x.Budget(self.path,activate=True)
        self.assertEqual(b.deadline,1080.)
        with patch.object(x.time,'time',return_value=1050.):b.close_clock()
        with patch.object(x.time,'time',return_value=2000.):again=x.Budget(self.path,activate=True)
        self.assertEqual(again.deadline,2030.)
        with patch.object(x.time,'time',return_value=2000.):again.close_clock()
    def test_unclear_running_clock_fails_closed(self):
        x.x.write(self.path/'clock.json',dict(consumed_active_seconds=0.,running_since=12.))
        with self.assertRaises(ValueError):x.Budget(self.path,activate=True)
    def test_stop_covers_final_baselines_and_actor_before_start(self):
        b=x.Budget(self.path);(self.path/'REQUEST_STOP').write_text('')
        for identity in ('confirmation_Band_00','confirmation_11_00'):
            with self.assertRaises(x.PauseRequested):b.call(identity,'confirmation',{},None)
        self.assertEqual(b.used()['native_starts'],0)
    def test_published_original_checkpoint_hash_rejects_changed_archive(self):
        original=x.x.sha
        with patch.object(x.x,'sha',side_effect=lambda p:'changed' if str(p).endswith('.pt') else original(p)):
            with self.assertRaises(ValueError):x.verify()
    def test_reserved_seed_and_closed_range_both_rejected(self):
        q=dict(version='arrival_seed_registry_v1',seeds=[827020101],ranges=[[834010001,834010016]],source_receipts=[])
        for seed in (827020101,834010001,834010002,834010016):
            with self.assertRaises(ValueError):x.reject_reserved_seeds([seed],q)
        x.reject_reserved_seeds([860010001],q)
    def test_bad_registry_range_or_noninteger_rejected(self):
        for q in (dict(version='arrival_seed_registry_v1',seeds=[True],ranges=[]),dict(version='arrival_seed_registry_v1',seeds=[],ranges=[[9,2]])):
            with self.assertRaises(ValueError):x.validate_registry(q)

if __name__=='__main__':unittest.main()
