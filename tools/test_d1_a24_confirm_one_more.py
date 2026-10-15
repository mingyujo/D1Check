import json
from pathlib import Path
import tempfile
import unittest
from d1_a24_confirm_one_more import check_history
from d1_a24_laptop_validator import PROTOCOL,sha256,ValidationError


class OneMoreHistoryTests(unittest.TestCase):
    def fixture(self,base):
        root=base/'visit';root.mkdir();global_root=base/'global';global_root.mkdir()
        (root/'WINDOW_STOPPED.json').write_text('{}')
        plan=base/'plan.json';plan.write_text(json.dumps({'plan_id':'p'}))
        raw=root/'raw'/'s';raw.mkdir(parents=True);(raw/'host_hal_partial.jsonl').write_bytes(b'')
        registry=root/'registry'/PROTOCOL/'p'/'s';registry.mkdir(parents=True)
        (registry/'host_hal_partial.jsonl').write_bytes(b'')
        reject={'START':False,'session_run_consumed':False,'reason':'bounded window does not admit APP_CREATE'}
        (registry/'PRESTART_REJECT.json').write_text(json.dumps(reject))
        out=root/'s.outcome.json';out.write_text(json.dumps({'APP_launch_intent':False,'reason':reject['reason']}))
        files={str(p.relative_to(root)).replace('\\','/'):sha256(p) for entry in [raw,registry,out] for p in ([entry] if entry.is_file() else entry.rglob('*')) if p.is_file()}
        binding={'previous_visits':[{'root':str(root),'stop_sha256':sha256(root/'WINDOW_STOPPED.json')}],
                 'previous_global_reservation_roots':[str(global_root)],'preserved_preAPP_artifacts':{'visit/s':{'files':files}}}
        return {'plan':str(plan)},binding,{'records':[{'session_id':'s','APP_launches':0}]},root,global_root

    def test_exact_empty_preAPP_time_refusal_is_not_APP_replay(self):
        with tempfile.TemporaryDirectory() as t:
            job,binding,ledger,_,_=self.fixture(Path(t));check_history(job,binding,ledger)

    def test_APP_intent_blocks_resumption(self):
        with tempfile.TemporaryDirectory() as t:
            job,binding,ledger,_,g=self.fixture(Path(t));p=g/'reservations'/'s';p.mkdir(parents=True);(p/'APP_LAUNCH_INTENT.json').write_text('{}')
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)

    def test_actual_sample_or_START_cannot_be_relabelled_unlaunched(self):
        with tempfile.TemporaryDirectory() as t:
            job,binding,ledger,r,_=self.fixture(Path(t));(r/'raw'/'s'/'events.jsonl').write_text('{}')
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)

    def test_changed_preAPP_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            job,binding,ledger,r,_=self.fixture(Path(t));(r/'s.outcome.json').write_text('{}')
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)

    def test_prior_active_owner_blocks_new_visit(self):
        with tempfile.TemporaryDirectory() as t:
            job,binding,ledger,_,g=self.fixture(Path(t));(g/'ACTIVE_OWNER.json').write_text('{}')
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)


if __name__=='__main__':unittest.main()
