import json
from pathlib import Path
import tempfile
import unittest
from tools import d1_execution_manifest as a


class AtomicTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.j=a.Journal(self.root)
        self.plan=dict(entries=[dict(session_id=str(i)) for i in range(30)],
                       manifests={str(i):dict(requests=[{}]* (24 if i>=20 else 12),warmup_requests=[]) for i in range(30)})
        self.j.create(self.plan,{'plan':'frozen'})
        self.ok={k:True for k in ('terminal','schema','identity','equivalence','provenance','timing','memory','thermal')}
    def tearDown(self):self.tmp.cleanup()
    def test_initial_counts(self):self.assertEqual(self.j.load()['next_pending_session'],'0')
    def test_running_blocks_next(self):
        self.j.start('0',{'pid':1})
        with self.assertRaises(ValueError):self.j.start('1',{'pid':2})
    def test_no_duplicate_running(self):
        self.j.start('0',{})
        with self.assertRaises(ValueError):self.j.start('0',{})
    def test_completed_no_replay(self):
        self.j.start('0',{});self.j.complete('0',self.ok,{'process_absent':True})
        with self.assertRaises(ValueError):self.j.start('0',{})
        self.assertEqual(self.j.load()['next_pending_session'],'1')
    def test_complete_requires_all_checks(self):
        self.j.start('0',{});self.ok['terminal']=False
        with self.assertRaises(ValueError):self.j.complete('0',self.ok,{'process_absent':True})
    def test_cleanup_required(self):
        self.j.start('0',{})
        with self.assertRaises(ValueError):self.j.complete('0',self.ok,{})
    def test_failed_halts(self):
        self.j.start('0',{});self.j.fail('0','partial artifact')
        with self.assertRaises(ValueError):self.j.start('1',{})
        self.assertEqual(self.j.load()['sessions'][0]['state'],'failed')
    def test_recover_no_new_start(self):
        self.j.start('0',{});self.j.complete('0',self.ok,{'process_absent':True},True)
        self.assertEqual(sum(s['started_utc'] is not None for s in self.j.load()['sessions']),1)
    def test_corrupt_rejected(self):
        self.j.path.write_text('{')
        with self.assertRaises(json.JSONDecodeError):self.j.load()
    def test_tamper_rejected(self):
        d=self.j.load();d['sessions'][0]['state']='completed';self.j.path.write_text(json.dumps(d))
        with self.assertRaises(ValueError):self.j.load()
    def test_partial_tmp_ignored(self):
        (self.root/'execution_manifest.json.partial.tmp').write_text('{')
        self.assertEqual(self.j.load()['sessions'][0]['state'],'pending')
    def test_revision_history(self):
        self.j.start('0',{});self.assertEqual(len(list((self.root/'manifest_history').glob('*.json'))),2)
    def test_lock_live_owner(self):
        with a.HostLock(self.root):
            with self.assertRaises(RuntimeError):
                with a.HostLock(self.root):pass
        with a.HostLock(self.root):pass


if __name__=='__main__':unittest.main()
