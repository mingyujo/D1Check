import tempfile
import unittest
from pathlib import Path
from tools import d1_sustained_readout as r
from tools import d1_arrival_plan as p
from unittest.mock import patch


class ReadoutTests(unittest.TestCase):
    def test_missing_progress_is_unknown_after_launch_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'host_commands').mkdir();session=root/'00_s';session.mkdir()
            (session/'launch_attempt.json').write_text('{}')
            (session/'attempt.json').write_text('{}')
            plan=dict(entries=[dict(index=0,session_id='s',policy='CPU')])
            x=r.consumption(root,plan)
            self.assertIsNone(x['sessions'][0]['counts']['request_start'])
            self.assertEqual(200,x['sessions'][0]['unrecorded_explicit_upper_bound'])
            self.assertEqual(1,x['unknown_progress_sessions'])

    def test_durable_partial_consumption_and_no_identifier_sharing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);command=root/'host_commands/0000/client';command.mkdir(parents=True)
            (command/'result.json').write_bytes(p.canonical(dict(command=['FAKE_ADB','-s','PRIVATE_TARGET','push','file.apk','remote'],status='returned')))
            session=root/'00_s';(session/'failure_prefix').mkdir(parents=True)
            for name in ('launch_attempt.json','attempt.json'):(session/name).write_text('{}')
            (session/'failure_prefix/progress.jsonl').write_bytes(b'{"kind":"warmup_start"}\n{"kind":"warmup_return"}\n{"kind":')
            x=r.consumption(root,dict(entries=[dict(index=0,session_id='s',policy='CPU')]))
            self.assertEqual(1,x['confirmed_counts']['warmup_start'])
            self.assertEqual(1,x['sessions'][0]['partial_lines'])
            self.assertEqual(1,x['apk_push_attempts'])
            self.assertNotIn('PRIVATE_TARGET',str(x))

    def test_unattempted_session_not_silently_completed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'host_commands').mkdir()
            x=r.consumption(root,dict(entries=[dict(index=0,session_id='s',policy='CPU')]))
            self.assertEqual((0,1),(x['completed_sessions'],x['unattempted_sessions']))
            self.assertEqual(0,x['sessions'][0]['counts']['request_start'])

    def test_no_policy_selection_or_future_data_input(self):
        with self.assertRaisesRegex(ValueError,'selection unavailable'):
            r.predict('not_read',0,'CPU','not_written',purpose='energy-ap-policy-selection')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bundle=root/'bundle';bundle.mkdir()
            from tools import d1_sustained_plan as plan_source,d1_sustained_protocol as protocol
            (bundle/'model.json').write_bytes(plan_source.MODEL.read_bytes())
            initial=dict(preload=[dict(t=-20,ap=29,lo=-20.1,hi=-19.9)],preload_power_w=1.1,
                         forbidden_future_ap_c=99,forbidden_future_current_ma=99999)
            r.write(bundle/'initial_inputs.json',[dict(index=0,initial=initial,manifest_requests=protocol.requests())])
            r.write(bundle/'resources.json',dict(files={f.name:p.digest(f) for f in bundle.iterdir()}))
            with patch.object(r.model,'forecast',return_value=(dict(ledger=[]),[])) as f, patch.object(r.model,'costs',return_value=dict(whole_120s_j=132)):
                r.predict(bundle,0,protocol.POLICIES[0],root/'out')
                self.assertEqual({'preload','preload_power_w'},set(f.call_args.args[0]))
                self.assertFalse(p.read(root/'out/result.json')['uses_future_measurements'])
            (bundle/'model.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'bundle hash'):
                r.predict(bundle,0,protocol.POLICIES[0],root/'bad')


if __name__=='__main__':unittest.main()
