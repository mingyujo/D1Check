import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from tools import d1_ap_bundle_confirmation as bundle
from tools import d1_arrival_energy_collection_device as runner
from tools import d1_ap_bundle_readout as readout
from tools import d1_arrival_start_ap as gate
from tools import d1_energy_host_lifecycle as lifecycle


class BundleTests(unittest.TestCase):
    def test_budget_and_registered_schedule_preserve_arrivals(self):
        bundle.budget_check(bundle.BUDGET)
        source=bundle.p.read(bundle.control.BUNDLE/'load_input.json')['requests']
        self.assertEqual(len(source),24)
        self.assertEqual(bundle.BUDGET['explicit_inference'],64)
        self.assertEqual(bundle.BUDGET['total_seconds'],2090)
        self.assertEqual((bundle.BUDGET['apk_transfers'],bundle.BUDGET['installs']),(0,0))
        changed=copy.deepcopy(bundle.BUDGET);changed['retry']=1
        with self.assertRaises(ValueError):bundle.budget_check(changed)

    def test_new_observe_mode_does_not_reintroduce_study_temperature_gate(self):
        self.assertTrue(gate.study_start_ap_eligible({'ap_bundle_role':bundle.ROLES[0]},28.8))
        self.assertTrue(gate.study_start_ap_eligible({'ap_bundle_role':bundle.ROLES[0]},33.0))
        self.assertFalse(gate.study_start_ap_eligible({'ap_idle_response_version':bundle.transfer.candidate.VERSION},33.0))

    def test_fixed_direction_endpoints_and_missing_not_shifted(self):
        rows=[dict(elapsed_s=t,observed_ap_c=y,frozen_ap_c=35.,candidate_ap_c=30.)
              for t,y in [(148.,30.),(152.,31.),(173.,29.),(178.,30.)]]
        got=readout.direction(rows,150,175)
        self.assertAlmostEqual(got['observed_change_c'],-1.1)
        self.assertEqual(got['candidate_change_c'],0.)
        self.assertEqual(readout.direction(rows,150,180)['status'],'missing_bracket')

    def test_consumed_check_stops_before_signature_and_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/bundle.FOLDER;folder.mkdir();run=Path(tmp)/'run';run.mkdir()
            file=folder/'collection_plan.json'
            bundle.cal.write_new(file,dict(output_root=str(run),registry=str(Path(tmp)/'registry')))
            with patch.object(bundle,'specification',side_effect=AssertionError('signature forbidden')):
                with self.assertRaisesRegex(ValueError,'consumed'):bundle.check(file)

    def test_real_runner_installed_only_two_confirmations_and_first_failure_stops(self):
        for failure in (None,'poll','installation'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);freeze=root/'freeze.json';bundle.cal.write_new(freeze,{'fixed':True})
                plan=dict(ap_bundled_confirmation=True,recorded_replay_confirmation=True,
                    budget=bundle.BUDGET,output_root=str(root/'run'),registry=str(root/'registry'),
                    apk_path='fixture.apk',apk_sha256='fixture',apk_preflight={'candidate':{}},
                    candidate_freeze=dict(path=str(freeze),sha256=bundle.p.digest(freeze)),source_files={},entries=[])
                for i,role in enumerate(bundle.ROLES):
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
                installed=stack.enter_context(patch.object(runner.energy_device,'installed_preflight',
                    side_effect=ValueError('installed mismatch') if failure=='installation' else None,
                    return_value={'status':'verified'}))
                deploy=stack.enter_context(patch.object(runner.energy_device,'installation',side_effect=AssertionError('deploy forbidden')))
                poll=stack.enter_context(patch.object(runner,'poll',side_effect=TimeoutError('original poll') if failure=='poll' else None))
                cleanup=stack.enter_context(patch.object(runner.shared,'cleanup',return_value={'status':'completed'}))
                if failure:
                    with self.assertRaisesRegex((ValueError,TimeoutError),'mismatch|original poll'):
                        runner.run(file,'FAKE','',bundle.p.digest(file),True)
                    self.assertEqual(poll.call_count,1 if failure=='poll' else 0)
                    self.assertEqual(cleanup.call_count,1 if failure=='poll' else 0)
                    receipt=bundle.p.read(root/'run/FINAL_RECEIPT.json')
                    self.assertEqual(receipt['status'],'stopped_no_resume')
                    self.assertIn('original_stack',receipt)
                else:
                    result=runner.run(file,'FAKE','',bundle.p.digest(file),True)
                    self.assertEqual((result['sessions'],result['requests'],result['warmup']),(2,48,16))
                    self.assertEqual(poll.call_count,2);self.assertEqual(cleanup.call_count,2)
                    self.assertEqual((root/'run/candidate_procedure_freeze.json').read_bytes(),freeze.read_bytes())
                installed.assert_called_once();deploy.assert_not_called()
                self.assertTrue((root/'registry/claimed.json').is_file())
                self.assertTrue(list((root/'run/host_checkpoints').glob('*.json')))
                self.assertTrue(runner.ObservedDevice.call_args.kwargs['forbid_apk_deploy'])

    def test_first_session_observation_cap_reserves_cleanup(self):
        plan=dict(ap_bundled_confirmation=True,recorded_replay_confirmation=True,
                  budget=bundle.BUDGET,entries=[{'index':0,'session_id':'first'}])
        d=type('Fake',(),{'deadline':999999999.,'sequence':3100})()
        with self.assertRaisesRegex(RuntimeError,'reserve'):
            runner.poll(d,'fake',Path('.'),{'session_id':'first'},plan)


if __name__=='__main__':unittest.main()
