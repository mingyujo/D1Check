import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools import d1_recorded_policy_comparison as bundle
from tools import d1_recorded_policy_readout as readout
from tools import d1_arrival_energy_collection_device as runner
from tools import d1_energy_host_lifecycle as lifecycle
from tools.d1_adb_observed_client import ObservedDevice

class ComparisonTests(unittest.TestCase):
    def test_source_and_budget(self):
        rows=bundle.schedules();bundle.budget_check(bundle.BUDGET)
        self.assertEqual(len(rows['CPU_URGENT']),24)
        self.assertEqual({r['recorded_backend'] for r in rows['CPU_URGENT']},{'CPU'})
        self.assertEqual([r['offset_ms'] for r in rows['CPU_URGENT']],list(range(0,4800,200)))
        bad=copy.deepcopy(bundle.BUDGET);bad['retry']=1
        with self.assertRaises(ValueError):bundle.budget_check(bad)

    def test_pair_missing_is_null_not_zero(self):
        rows=[dict(energy_j=v) for v in (10.,12.,14.,11.)]
        result=[r for r in readout.pairs(rows) if r['metric']=='energy_j']
        self.assertEqual([r['b2_minus_cpu'] for r in result],[2.,3.])
        rows[3]={}
        self.assertIsNone([r for r in readout.pairs(rows) if r['metric']=='energy_j'][1]['b2_minus_cpu'])

    def test_explicit_transport_multiple_online_no_switch(self):
        d=ObservedDevice('NEVER_ADB','SELECTED','unused',allow_other_transports=True)
        listing=b'List of devices attached\nOTHER device\nSELECTED device\n'
        with patch.object(d,'call',side_effect=[SimpleNamespace(stdout=listing),SimpleNamespace(stdout=b'SM-A245N'),SimpleNamespace(stdout=b'FP')]) as call:
            self.assertEqual(d.identify('FP')['serial'],'SELECTED')
            self.assertEqual(call.call_count,3)
        with patch.object(d,'call',return_value=SimpleNamespace(stdout=b'List of devices attached\nOTHER device\n')) as call:
            with self.assertRaisesRegex(RuntimeError,'no fallback'):d.identify('FP')
            self.assertEqual(call.call_count,1)

    def test_consumed_check_stops_before_any_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/bundle.FOLDER;folder.mkdir();run=Path(tmp)/'run';run.mkdir()
            file=folder/'collection_plan.json'
            bundle.cal.write_new(file,dict(output_root=str(run),registry=str(Path(tmp)/'registry')))
            with patch.object(bundle,'specification',side_effect=AssertionError('forbidden')):
                with self.assertRaisesRegex(ValueError,'consumed'):bundle.check(file)

    def test_real_runner_four_sessions_and_first_failure_stops(self):
        for failure in (None,'poll','installation'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);freeze=root/'freeze.json';bundle.cal.write_new(freeze,{'fixed':True})
                plan=dict(recorded_policy_comparison=True,recorded_replay_confirmation=True,
                    budget=bundle.BUDGET,output_root=str(root/'run'),registry=str(root/'registry'),
                    apk_path='fixture.apk',apk_sha256='fixture',apk_preflight={'candidate':{}},
                    frozen_model=dict(path=str(freeze),sha256=bundle.p.digest(freeze)),source_files={},entries=[])
                for i,role in enumerate(bundle.ORDER):
                    mf=root/f'{i}.json';bundle.cal.write_new(mf,dict(session_id=str(i),phase=role))
                    plan['entries'].append(dict(index=i,session_id=str(i),manifest=mf.name))
                file=root/'plan.json';bundle.cal.write_new(file,plan)
                clock=[0.]
                def now():clock[0]+=.1;return clock[0]
                def sleep(seconds):clock[0]+=seconds
                fake=type('Fake',(),{'sequence':0,'deadline':None,'call':lambda *a,**k:None})()
                for obj,name,kwargs in [(bundle,'check',{}),(runner,'require_host_pull_space',{}),
                    (runner,'ObservedDevice',{'return_value':fake}),
                    (lifecycle,'host_identity',{'return_value':{'parent':{'status':'present'},'child':{'status':'present'}}}),
                    (runner.time,'monotonic',{'side_effect':now}),(runner.time,'sleep',{'side_effect':sleep}),
                    (runner.energy_device,'gates',{}),(runner.install,'installed_hash',{'return_value':'fixture'}),
                    (runner.shared,'stage_inputs',{'return_value':'remote'}),
                    (runner.energy_device,'recover',{'return_value':{'status':'recovered'}}),
                    (runner.energy_device,'pull_file',{'side_effect':ValueError('partial recovery')}),
                    (runner,'validate',{'return_value':dict(status='eligible_descriptive_only',requests=24)})]:
                    stack.enter_context(patch.object(obj,name,**kwargs))
                installed=stack.enter_context(patch.object(runner.energy_device,'installation',
                    side_effect=ValueError('installed mismatch') if failure=='installation' else None,
                    return_value={'status':'verified'}))
                deploy=stack.enter_context(patch.object(runner.energy_device,'installed_preflight',side_effect=AssertionError('wrong preflight path')))
                poll=stack.enter_context(patch.object(runner,'poll',side_effect=TimeoutError('original poll') if failure=='poll' else None))
                cleanup=stack.enter_context(patch.object(runner.shared,'cleanup',return_value={'status':'completed'}))
                if failure:
                    with self.assertRaisesRegex((ValueError,TimeoutError),'mismatch|original poll'):
                        runner.run(file,'FAKE','SELECTED',bundle.p.digest(file),True)
                    self.assertEqual(poll.call_count,1 if failure=='poll' else 0)
                    self.assertEqual(cleanup.call_count,1 if failure=='poll' else 0)
                    receipt=bundle.p.read(root/'run/FINAL_RECEIPT.json')
                    self.assertEqual(receipt['status'],'stopped_no_resume')
                    self.assertIn('original_stack',receipt)
                else:
                    result=runner.run(file,'FAKE','SELECTED',bundle.p.digest(file),True)
                    self.assertEqual((result['sessions'],result['requests'],result['warmup']),(4,96,32))
                    self.assertEqual(poll.call_count,4);self.assertEqual(cleanup.call_count,4)
                    self.assertEqual((root/'run/original_model_freeze.json').read_bytes(),freeze.read_bytes())
                installed.assert_called_once();deploy.assert_not_called()
                self.assertTrue((root/'registry/claimed.json').is_file())
                self.assertTrue(list((root/'run/host_checkpoints').glob('*.json')))
                self.assertFalse(runner.ObservedDevice.call_args.kwargs['forbid_apk_deploy'])
                self.assertTrue(runner.ObservedDevice.call_args.kwargs['allow_other_transports'])


if __name__=='__main__':unittest.main()
