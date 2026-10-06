import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import torch
from tools import d1_queue_ppo_resume as r


class ResumeTests(unittest.TestCase):
    def quiet(self): return redirect_stdout(io.StringIO())

    def new(self,root,name):
        return r.Session(Path(root)/name,fixture=True,lock=Path(root)/'fixture.lock')

    def test_exact_uninterrupted_vs_two_resumes(self):
        with tempfile.TemporaryDirectory() as root, self.quiet():
            full=self.new(root,'full'); self.assertEqual(full.execute(),'completed')
            part=self.new(root,'part'); self.assertEqual(part.execute(pause_after=3),'paused')
            checkpoint=r.read_state(part.folder)
            self.assertEqual(checkpoint['update'],1)
            expected_rng=checkpoint['torch_rng'].clone()
            middle=r.Session(part.folder,checkpoint,lock=Path(root)/'fixture.lock')
            self.assertTrue(torch.equal(torch.get_rng_state(),expected_rng))
            self.assertEqual(middle.execute(pause_after=2),'paused')
            resumed=r.Session(part.folder,r.read_state(part.folder),lock=Path(root)/'fixture.lock')
            self.assertEqual(resumed.execute(),'completed')
            self.assertEqual(full.s['counts'],resumed.s['counts'])
            self.assertEqual(sum(full.s['counts'].values()),20)
            self.assertEqual(full.s['test_rows'],resumed.s['test_rows'])
            for filename in ('HEAD_seed101.json','QUEUE_seed101.json','test.csv'):
                self.assertEqual((full.folder/filename).read_bytes(),(part.folder/filename).read_bytes(),filename)
            self.assertEqual([x['update'] for x in full.s['selected']],[x['update'] for x in resumed.s['selected']])

    def test_resume_blocked_for_completed_corrupt_or_changed_source(self):
        with tempfile.TemporaryDirectory() as root,self.quiet():
            session=self.new(root,'part'); session.execute(pause_after=2)
            state=r.read_state(session.folder)
            wrong=copy.deepcopy(state); wrong['sources']['tools/d1_queue_ppo.py']='0'*64
            with self.assertRaises(ValueError): r.Session(session.folder,wrong,lock=Path(root)/'fixture.lock')
            meta=json.loads((session.folder/'checkpoint.json').read_text())
            path=session.folder/meta['file']; path.write_bytes(path.read_bytes()+b'corrupt')
            with self.assertRaises(ValueError): r.read_state(session.folder)

    def test_active_owner_not_killed_or_removed(self):
        with tempfile.TemporaryDirectory() as root:
            lock=Path(root)/'owner.json'
            lock.write_text(json.dumps(dict(pid=r.os.getpid(),run_id='foreign')))
            before=lock.read_bytes()
            with self.assertRaises(ValueError): r.owner_absent(lock)
            self.assertEqual(lock.read_bytes(),before)

    def test_remaining_budget_not_reset_by_resume(self):
        with tempfile.TemporaryDirectory() as root,self.quiet():
            session=self.new(root,'part'); session.execute(pause_after=1)
            state=r.read_state(session.folder); state['elapsed_s']=800.
            resumed=r.Session(session.folder,state,lock=Path(root)/'fixture.lock')
            self.assertEqual(resumed.execute(),'budget_stopped')
            self.assertEqual(resumed.s['counts']['training'],0)
            with self.assertRaises(ValueError): r.read_state(session.folder)

    def test_partial_exception_not_certified_as_pause(self):
        with tempfile.TemporaryDirectory() as root,self.quiet():
            session=self.new(root,'part')
            with patch.object(session,'step',side_effect=KeyboardInterrupt('forced second cancel')):
                with self.assertRaises(KeyboardInterrupt): session.execute()
            self.assertTrue((session.folder/'ORIGINAL_ERROR.json').exists())
            with self.assertRaises(ValueError): r.read_state(session.folder)

    def test_failed_receipt_preserves_original_exception(self):
        with tempfile.TemporaryDirectory() as root,self.quiet():
            session=self.new(root,'part'); real=r.q.atomic
            def fail(path,value):
                if Path(path).name.startswith('RECEIPT_') and Path(path).name!='RECEIPT_ERROR.json': raise OSError('disk fixture')
                return real(path,value)
            with patch.object(session,'step',side_effect=RuntimeError('original')),patch.object(r.q,'atomic',side_effect=fail):
                with self.assertRaisesRegex(RuntimeError,'original'): session.execute()
            evidence=json.loads((session.folder/'RECEIPT_ERROR.json').read_text())
            self.assertEqual(evidence['original_error']['message'],'original')
            self.assertFalse(session.lock.exists())

    def test_legacy_checkpoint_import_matches_continuous_fixture(self):
        with tempfile.TemporaryDirectory() as root,self.quiet(),patch.object(r.q,'LOCK',Path(root)/'owner.lock'):
            full=self.new(root,'full'); full.execute()
            donor=self.new(root,'legacy'); donor.execute(pause_after=4)
            state=r.read_state(donor.folder)
            pair=('HEAD',101); folder=donor.folder/'HEAD_seed101'; folder.mkdir()
            torch.save(dict(network=state['network'],optimizer=state['optimizer'],update=1,
                multipliers=state['multipliers'],torch_rng=state['torch_rng'],source_hashes=r.q.hashes()),folder/'checkpoint.pt')
            net=r.q.ActorCritic(); net.load_state_dict(state['best_actor']); r.q.save_actor(folder/'selected_actor.json',net)
            r.q.old.csv_write(donor.folder/'validation.csv',state['validation_rows'])
            r.q.atomic(donor.folder/'run_manifest.json',dict(source_hashes=r.q.hashes(),runtime=r.Session.runtime(),plan=r.q.load_plan()))
            r.q.atomic(donor.folder/'FINAL_RECEIPT.json',dict(status='stopped_no_automatic_restart',error={'type':'KeyboardInterrupt'},
                counts=state['counts'],elapsed_s=state['elapsed_s']))
            with (donor.folder/'journal.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(stage='training',variant='HEAD',seed=101,update=1))+'\n')
            with patch.object(r,'config',return_value=r.fixture_config()),patch.object(r.q,'input_manifest',return_value={}):
                resumed_folder=r.import_legacy(donor.folder)
            continued=r.Session(resumed_folder,r.read_state(resumed_folder),lock=Path(root)/'owner.lock')
            continued.execute()
            self.assertEqual(full.s['test_rows'],continued.s['test_rows'])
            self.assertEqual(continued.s['recovery']['reference_rebuild'],2)
            for filename in ('HEAD_seed101.json','QUEUE_seed101.json'):
                self.assertEqual((full.folder/filename).read_bytes(),(resumed_folder/filename).read_bytes())

    def test_legacy_before_first_checkpoint_reconstructs_seed_boundary(self):
        with tempfile.TemporaryDirectory() as root,self.quiet(),patch.object(r.q,'LOCK',Path(root)/'owner.lock'):
            full=self.new(root,'full'); full.execute()
            donor=self.new(root,'legacy'); donor.execute(pause_after=4)
            state=r.read_state(donor.folder)
            folder=donor.folder/'HEAD_seed101'; folder.mkdir()
            r.q.prev.seed_all(101); initial_net=r.q.ActorCritic()
            r.q.save_actor(folder/'selected_actor.json',initial_net)
            r.q.old.csv_write(donor.folder/'validation.csv',state['validation_rows'])
            r.q.atomic(donor.folder/'run_manifest.json',dict(source_hashes=r.q.hashes(),runtime=r.Session.runtime(),plan=r.q.load_plan()))
            r.q.atomic(donor.folder/'FINAL_RECEIPT.json',dict(status='stopped_no_automatic_restart',error={'type':'KeyboardInterrupt'},
                counts=state['counts'],elapsed_s=state['elapsed_s']))
            with (donor.folder/'journal.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(stage='training',variant='HEAD',seed=101,update=1))+'\n')
            with patch.object(r,'config',return_value=r.fixture_config()),patch.object(r.q,'input_manifest',return_value={}):
                resumed_folder=r.import_legacy(donor.folder)
            continued=r.Session(resumed_folder,r.read_state(resumed_folder),lock=Path(root)/'owner.lock')
            continued.execute()
            self.assertEqual(full.s['test_rows'],continued.s['test_rows'])
            self.assertTrue(json.loads((resumed_folder/'LEGACY_IMPORT.json').read_text())['initial_actor_bootstrap'])
            self.assertEqual(continued.s['recovery']['replayed_training_max'],1)

    def test_real_powershell_resume_entry_and_completed_block(self):
        with tempfile.TemporaryDirectory() as root,self.quiet():
            folder=Path(root)/'part'
            session=r.Session(folder,fixture=True,lock=Path(root)/'.resume_fixture_lock.json')
            session.execute(pause_after=3)
            command=['powershell.exe','-NoProfile','-File',str(r.q.p.ROOT/'tools/RUN_QUEUE_PPO_RESUMABLE.ps1'),
                '-Action','Resume','-Output',str(folder),'-Python',r.q.sys.executable]
            child=subprocess.run(command,capture_output=True,text=True,timeout=90)
            self.assertEqual(child.returncode,0,child.stderr)
            self.assertIn('"stage": "resumed"',child.stdout)
            self.assertIn('"stage": "completed"',child.stdout)
            again=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(again.returncode,0)


if __name__=='__main__': unittest.main()
