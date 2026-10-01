import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from tools import d1_resident_control_plan as c
from tools import d1_arrival_energy_collection_device as runner


def write(path,value):
    path.write_text(json.dumps(value),encoding='utf-8')


class ControlTests(unittest.TestCase):
    def test_real_parser_zero_with_complete_observation_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'artifacts';a.mkdir()
            m=dict(resident_control_version=c.VERSION,resident_control_role=c.ROLES[0],
                phase=c.ROLES[0],scenario='burst',policy=c.replay.POLICY,requests=[],start_ap_gate='numeric-ap-observe-v2')
            for f in (root/'input_manifest.json',a/'manifest.json'):write(f,m)
            begin=100_000_000_000;end=begin+120_000_000_000
            for name,value in [('cleanup.json',{'status':'completed'}),
                ('summary.json',{'status':'completed','planned':0,'terminal':0}),('requests.json',[]),
                ('common_boundary.json',dict(start_ns=begin,end_ns=end,planned_end_ns=end,planned=0,rows=[])),
                ('start_ap.accepted.json',dict(common_start_ns=begin,ap_c=28.8,gate_mode='numeric-ap-observe-v2',
                    read_before_ns=begin-1_000_000,read_after_ns=begin-500_000))]:write(a/name,value)
            events=[dict(kind=k) for k,n in [('warmup_return',8),('runtime_return',4)] for _ in range(n)]
            for i in range(122):
                t=begin+(i-1)*1_000_000_000
                events.append(dict(kind='power_sample',snapshot_start_ns=t,sensor_read_end_ns=t,
                    state_snapshot_ns=t,mono_ns=t,active={},current_raw=-300,current_valid=True,
                    voltage_mV=4000,plugged=0,resident_keys=list(runner.c.old.KEYS)))
            def save_events():
                (a/'progress.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
            save_events()
            (root/'thermal.jsonl').write_text(''.join(json.dumps(dict(mono_ns=begin+i*4_000_000_000,
                thermal_status='0',AP='28.8'))+'\n' for i in range(31)),encoding='utf-8')
            plan={'resident_control_pair':True,'recorded_replay_confirmation':True}
            result=runner.validate(root,m,plan)
            self.assertEqual(result['requests'],0)
            from tools import d1_resident_control_readout as readout
            read=readout.session(root,m,{'whole_device_power_w':{'resident_idle':1.2}})
            self.assertAlmostEqual(read['windows']['common']['observed_j'],144.)
            self.assertAlmostEqual(read['signed_diagnostic_error_j'],0.)
            self.assertIsNone(read['windows']['late_cooling']['mean_w'])
            self.assertEqual(read['windows']['pre']['ap']['change_c'],0.)
            events.append(dict(kind='dispatch'));save_events()
            with self.assertRaisesRegex(ValueError,'unexpectedly ran'):runner.validate(root,m,plan)
            write(a/'cleanup.json',{'status':'failed','error':'original cancellation'})
            (a/'summary.json').unlink()
            with self.assertRaisesRegex(RuntimeError,'original cancellation'):runner.validate(root,m,plan)

    def test_pair_run_counts_and_failure_no_second_session(self):
        for fail in (False,True):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);file=root/'plan.json'
                entries=[]
                for i,role in enumerate(c.ROLES):
                    write(root/f'{i}.json',{'phase':role})
                    entries.append(dict(index=i,session_id=str(i),manifest=f'{i}.json'))
                plan=dict(resident_control_pair=True,recorded_replay_confirmation=True,budget=c.BUDGET,
                    output_root=str(root/'run'),registry=str(root/'registry'),apk_preflight={'candidate':{}},
                    apk_sha256='x',source_files={},entries=entries)
                write(file,plan)
                clock=[0.]
                def now():clock[0]+=.001;return clock[0]
                def sleep(seconds):clock[0]+=seconds
                fake=type('Fake',(),{'sequence':0,'deadline':None,'call':lambda *a,**k:None})()
                for obj,name,kwargs in [
                    (c,'check',{}),(runner,'ObservedDevice',{'return_value':fake}),
                    (runner.time,'monotonic',{'side_effect':now}),(runner.time,'sleep',{'side_effect':sleep}),
                    (runner.energy_device,'installation',{'return_value':{'status':'verified'}}),
                    (runner.energy_device,'gates',{}),(runner.install,'installed_hash',{'return_value':'x'}),
                    (runner.shared,'stage_inputs',{'return_value':'remote'}),
                    (runner.energy_device,'recover',{'return_value':{'status':'recovered'}}),
                    (runner.energy_device,'pull_file',{'side_effect':RuntimeError('partial recovery')}),
                    (runner,'validate',{'side_effect':lambda folder,m,p:dict(status='eligible_descriptive_only',requests=0 if m['phase']==c.ROLES[0] else 24)})]:
                    stack.enter_context(patch.object(obj,name,**kwargs))
                poll=stack.enter_context(patch.object(runner,'poll',side_effect=TimeoutError('original poll') if fail else None))
                cleanup=stack.enter_context(patch.object(runner.shared,'cleanup',return_value={'status':'completed'}))
                if fail:
                    with self.assertRaisesRegex(TimeoutError,'original poll'):runner.run(file,'FAKE','',c.p.digest(file),True)
                    self.assertEqual(poll.call_count,1);self.assertEqual(cleanup.call_count,1)
                    receipt=c.p.read(root/'run/FINAL_RECEIPT.json')
                    self.assertIn('original poll',receipt['error'])
                    self.assertTrue((root/'registry/stopped.json').exists())
                else:
                    result=runner.run(file,'FAKE','',c.p.digest(file),True)
                    self.assertEqual((result['sessions'],result['requests'],result['warmup']),(2,24,16))
                    self.assertEqual(cleanup.call_count,2)
                # Check blocks a consumed plan before signature tools or any device access.
                stack.close()
                proper=root/c.FOLDER;proper.mkdir();proper_file=proper/'collection_plan.json'
                write(proper_file,plan)
                with self.assertRaisesRegex(ValueError,'consumed/occupied'):c.check(proper_file)

    def test_approval_denied_before_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'plan.json';write(file,{})
            with patch.object(runner,'ObservedDevice',side_effect=AssertionError('device forbidden')):
                with self.assertRaises(ValueError):runner.run(file,'FAKE','',c.p.digest(file),False)
            self.assertEqual(list(Path(tmp).iterdir()),[file])

    def test_request_roles_and_budget(self):
        self.assertEqual(c.BUDGET['total_seconds'],600+2*(120+485+50+45)+90)
        self.assertEqual(c.BUDGET['explicit_inference'],40)
        with self.assertRaises(ValueError):c.request_count({'requests':[]})


if __name__=='__main__':unittest.main()
