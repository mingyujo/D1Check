import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from d1_a24_measurement_share_bundle import write_zip,public_manifest,snapshot,encode,read,PRIVATE,unlaunched_preAPP_evidence


class ShareBundleTests(unittest.TestCase):
    def test_identifier_filter_keeps_normal_runtime_field_names(self):
        self.assertIsNone(PRIVATE.search(b'cold_repetitions warm_repetitions'))
        self.assertIsNotNone(PRIVATE.search(b'R12A3456789'))
        self.assertIsNone(PRIVATE.search(b'1abc2adb-5ff2-1234-9876-000000000000'))
        self.assertIsNotNone(PRIVATE.search(b'adb-R12A3456789-example'))
    def test_exact_CRLF_raw_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.zip';write_zip(p,{'raw/sid/events.jsonl':b'{"a":1}\r\n'})
            with zipfile.ZipFile(p) as z:self.assertEqual(z.read('raw/sid/events.jsonl'),b'{"a":1}\r\n')
            with self.assertRaises(FileExistsError):write_zip(p,{})

    def test_private_bytes_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            for members in [{'../outside':b'x'},{'raw/x':b'C:\\Users\\sample-user\\private'}]:
                with self.assertRaises(ValueError):write_zip(Path(t)/'a.zip',members)

    def test_projection_excludes_device_target_and_keeps_input_SHA(self):
        x=public_manifest({'session_id':'s','device_fingerprint':'private','models':{'C_CPU':{'model':{'sha256':'a'*64},'target':{'adb_serial':'private'},'runtime':{'cpu_threads':1}}}})
        self.assertNotIn('device_fingerprint',x);self.assertNotIn('target',x['models']['C_CPU']);self.assertEqual(x['models']['C_CPU']['model']['sha256'],'a'*64)

    def test_preAPP_refusal_receipt_kept_but_executed_duplicate_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'visit';root.mkdir();sid='s';outcome={'APP_launch_intent':False}
            (root/(sid+'.outcome.json')).write_bytes(encode(outcome))
            registry=root/'registry'/'a24-laptop-measurement-v1'/'plan'/sid;registry.mkdir(parents=True)
            (registry/'PRESTART_REJECT.json').write_bytes(encode({'START':False,'session_run_consumed':False}))
            kept=unlaunched_preAPP_evidence(root,sid,'plan',outcome)
            self.assertEqual(len(kept),2)
            with self.assertRaises(ValueError):unlaunched_preAPP_evidence(root,sid,'plan',{'APP_launch_intent':True})
            (root/'adb_commands.jsonl').write_bytes(encode({'argv':['adb','shell','am','start','session_id',sid]}).replace(b'\n',b''))
            with self.assertRaises(ValueError):unlaunched_preAPP_evidence(root,sid,'plan',outcome)

    def test_later_active_attempt_never_copies_raw_after_unconsumed_refusal(self):
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);old=b/'old';active=b/'active';old.mkdir();active.mkdir();prepared=b/'prepared';prepared.mkdir()
            row=dict(session_id='s',stage='CONFIRM',block='B',recipe='L64',arm='BASE',request_count=1,plan_ordinal=0)
            (b/'plan.json').write_bytes(encode({'plan_id':'p','sessions':[row]}))
            (b/'job.json').write_bytes(encode({'plan':str(b/'plan.json'),'prepared_manifests':str(prepared)}))
            (old/'s.outcome.json').write_bytes(encode({'session_id':'s','status':'FAILED_PRESERVED','APP_launch_intent':False}))
            registry=old/'registry'/'a24-laptop-measurement-v1'/'p'/'s';registry.mkdir(parents=True)
            (registry/'PRESTART_REJECT.json').write_bytes(encode({'START':False,'session_run_consumed':False}))
            raw=active/'raw'/'s';raw.mkdir(parents=True);(raw/'events.jsonl').write_bytes(b'not closed')
            (active/'adb_commands.jsonl').write_bytes((json.dumps({'argv':['adb','shell','am','start','session_id','s'],'start_wall_ns':1})+'\n').encode())
            cfg={'source_catalog_directories':[],'families':[{'id':'PC_ONLY','job':str(b/'job.json'),'roots':[str(old),str(active)]}],'changes_notes':{}}
            snapshot(cfg,b/'public',b/'audit')
            self.assertEqual(read(b/'public'/'SNAPSHOT.json')['status_counts'],{'IN_PROGRESS_AT_SNAPSHOT':1})
            with zipfile.ZipFile(next((b/'public'/'blocks').glob('*.zip'))) as z:
                self.assertFalse(any(n.startswith('raw/') for n in z.namelist()))
                self.assertTrue(any(n.startswith('unlaunched_preAPP_refusals/') for n in z.namelist()))

    def test_failed_same_run_recovery_and_active_raw_are_not_normal_results(self):
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);root=b/'run';root.mkdir();prepared=b/'prepared';prepared.mkdir()
            rows=[dict(session_id=s,stage='DEV',block='B01',recipe='M128',arm=a,request_count=1,plan_ordinal=i) for i,(s,a) in enumerate([('failed','BASE'),('active','PAIR_G')])]
            (b/'plan.json').write_bytes(encode({'sessions':rows}));(b/'job.json').write_bytes(encode({'plan':str(b/'plan.json'),'prepared_manifests':str(prepared)}))
            (prepared/'failed.json').write_bytes(encode({'session_id':'failed','models':{}}))
            outcome={'session_id':'failed','status':'FAILED_OR_REJECTED_PRESERVED'};(root/'failed.outcome.json').write_bytes(encode(outcome))
            for p,raw in [(root/'raw'/'failed',b'original\r\n'),(root/'read_only_recovery'/'failed'/'recovered_app',b'recovered\r\n')]:
                p.mkdir(parents=True);(p/'events.jsonl').write_bytes(raw);(p/'requests.json').write_bytes(encode([{'terminal_status':'COMPLETED'}]))
            active=root/'raw'/'active';active.mkdir(parents=True);(active/'events.jsonl').write_bytes(b'C:\\Users\\sample-user\\not_closed')
            cooling=root/'pre_app_cooldown_v2';cooling.mkdir();(cooling/'failed.jsonl').write_bytes(b'{"AP":27.1}\r\n');(cooling/'active.jsonl').write_bytes(b'not closed')
            (root/'adb_commands.jsonl').write_bytes((json.dumps({'argv':['adb','shell','am','start','session_id','active'],'start_wall_ns':1,'exit':0})+'\n').encode())
            cfg={'source_catalog_directories':[],'families':[{'id':'PC_ONLY','job':str(b/'job.json'),'roots':[str(root)]}],'changes_notes':{'PC_ONLY':['MOCK ONLY']}}
            snapshot(cfg,b/'public',b/'audit')
            info=read(b/'public'/'SNAPSHOT.json');self.assertEqual(info['status_counts']['IN_PROGRESS_AT_SNAPSHOT'],1)
            with zipfile.ZipFile(next((b/'public'/'blocks').glob('*.zip'))) as z:
                self.assertEqual(z.read('raw/failed/events.jsonl'),b'original\r\n')
                self.assertEqual(z.read('supplemental_same_run_raw/failed/events.jsonl'),b'recovered\r\n')
                self.assertFalse(any(n.startswith('raw/active/') for n in z.namelist()))
                self.assertEqual(z.read('host_preAPP/failed/pre_app_cooldown_v2/failed.jsonl'),b'{"AP":27.1}\r\n')
                self.assertFalse(any(n.startswith('host_preAPP/active/') for n in z.namelist()))
                self.assertEqual(json.loads(z.read('BLOCK_STATUS.json'))['normal_completed'],0)


if __name__=='__main__':unittest.main()
