import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from tools import d1_ap_memory_confirmation as m
from tools import d1_ap_memory_confirmation_readout as readout
from tools import d1_arrival_energy_collection_device as runner
from tools import d1_energy_host_lifecycle as lifecycle
from tools.test_d1_ap_preparation_memory import synthetic


class ConfirmationTests(unittest.TestCase):
    def test_registered_two_waits_preserve_arrival_backend_and_calls(self):
        template=dict(models={'x':{'identity':{}}},requests=m.p.read(m.base.control.BUNDLE/'load_input.json')['requests'])
        with patch.object(m.base,'specification',return_value=({},[template,template])),patch.object(m,'identity',return_value={}):
            plan,mm=m.specification('source','build',Path('parent')/m.FOLDER)
        m.base.budget_check(plan['budget'])
        self.assertEqual(plan['approval'],'not_approved')
        self.assertEqual((plan['budget']['explicit_inference'],plan['budget']['total_seconds']),(64,2090))
        for a,b,source in zip(mm[0]['requests'],mm[1]['requests'],template['requests']):
            self.assertEqual(b['release_offset_ns']-a['release_offset_ns'],30_000_000_000)
            self.assertEqual((a['offset_ms'],a['recorded_backend']),(b['offset_ms'],b['recorded_backend']))
            self.assertEqual(a['release_offset_ns'],source['release_offset_ns'])
            self.assertNotEqual(a['request_id'],b['request_id'])
        self.assertEqual(len(mm[0]['requests'])+len(mm[1]['requests']),48)

    def test_consumed_stops_before_apk_or_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/m.FOLDER;folder.mkdir();run=Path(tmp)/'occupied';run.mkdir()
            file=folder/'collection_plan.json';m.cal.write_new(file,dict(output_root=str(run),registry=str(Path(tmp)/'registry')))
            with patch.object(m,'specification',side_effect=AssertionError('no after-consumption operation')):
                with self.assertRaisesRegex(ValueError,'consumed'):m.check(file)

    def test_fixed_predict_never_fits_or_uses_target(self):
        plan=dict(memory_candidate=dict(path=str(m.CANDIDATE),sha256=m.CANDIDATE_SHA))
        # Synthetic schedule uses a supported key, complete pre-load observation.
        case=synthetic();case['observed_ap_c']=[-10000]*len(case['inputs']['query_s'])
        with patch.object(readout.model,'fit',side_effect=AssertionError('refit forbidden')):
            first=readout.predict_fixed(case,plan)
            case['observed_ap_c']=[10000]*len(case['inputs']['query_s'])
            self.assertEqual(first,readout.predict_fixed(case,plan))

    def test_changed_candidate_blocked(self):
        with patch.object(readout.p,'digest',return_value='changed'):
            with self.assertRaisesRegex(ValueError,'candidate changed'):
                readout.predict_fixed({},dict(memory_candidate={'path':'fake'}))

    def test_longer_passive_preload_is_supported_without_new_coefficient(self):
        case=synthetic();case['inputs']['segments'][0]['end_s']=65.
        case['inputs']['segments'][1].update(start_s=65.,end_s=77.)
        case['inputs']['segments'][2]['start_s']=77.
        case['inputs']['query_s']=list(range(66,179,3))
        case['inputs']['preload']=[]
        for t in range(-30,65,3):
            temperature,_=readout.model.advance(31,.04,0,29,.05,60,1.2,t+30)
            case['inputs']['preload'].append(dict(t=float(t),ap=temperature,lo=t-.05,hi=t+.05))
        values,init=readout.predict_fixed(case,dict(memory_candidate=dict(path=str(m.CANDIDATE))))
        self.assertEqual(len(values),len(case['inputs']['query_s']))
        self.assertGreater(init['duration_s'],90)
        self.assertLess(init['input_end_s'],65)

    def test_real_runner_routes_memory_eligibility_and_stops_without_duplicate_cleanup(self):
        for fail in (None,'memory','poll','installation'):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);freeze=root/'freeze.json';m.cal.write_new(freeze,{'fixed':True})
                binding=dict(path=str(freeze),sha256=m.p.digest(freeze))
                plan=dict(ap_memory_confirmation=True,ap_bundled_confirmation=True,recorded_replay_confirmation=True,
                    budget=m.BUDGET,output_root=str(root/'run'),registry=str(root/'registry'),
                    apk_path='fixture.apk',apk_sha256='fixture',apk_preflight={'candidate':{}},source_files={},
                    memory_candidate=binding,candidate_freeze=binding,analysis_contract=binding,entries=[])
                for i,role in enumerate(m.ROLES):
                    mf=root/f'{i}.json';m.cal.write_new(mf,dict(session_id=str(i),phase=role))
                    plan['entries'].append(dict(index=i,session_id=str(i),manifest=mf.name))
                file=root/'plan.json';m.cal.write_new(file,plan);clock=[0.]
                def now():clock[0]+=.1;return clock[0]
                def sleep(seconds):clock[0]+=seconds
                fake=type('Fake',(),{'sequence':0,'deadline':None,'call':lambda *a,**k:None})()
                for obj,name,kwargs in [(m,'check',{}),(runner,'require_host_pull_space',{}),
                    (runner,'ObservedDevice',{'return_value':fake}),
                    (lifecycle,'host_identity',{'return_value':{'parent':{'status':'present'},'child':{'status':'present'}}}),
                    (runner.time,'monotonic',{'side_effect':now}),(runner.time,'sleep',{'side_effect':sleep}),
                    (runner.energy_device,'gates',{}),(runner.install,'installed_hash',{'return_value':'fixture'}),
                    (runner.shared,'stage_inputs',{'return_value':'remote'}),
                    (runner.energy_device,'recover',{'return_value':{'status':'recovered'}}),
                    (runner.energy_device,'pull_file',{'side_effect':ValueError('partial recovery')}),
                    (runner,'validate',{'return_value':dict(status='eligible_descriptive_only',requests=24)}),
                    (readout,'case_from_session',{'side_effect':ValueError('memory coverage') if fail=='memory' else None}),
                    (readout,'predict_fixed',{'return_value':([],{'fixed':True})})]:
                    stack.enter_context(patch.object(obj,name,**kwargs))
                installed=stack.enter_context(patch.object(runner.energy_device,'installed_preflight',
                    side_effect=ValueError('installation mismatch') if fail=='installation' else None,return_value={}))
                deploy=stack.enter_context(patch.object(runner.energy_device,'installation',side_effect=AssertionError('no deployment')))
                poll=stack.enter_context(patch.object(runner,'poll',side_effect=TimeoutError('poll original') if fail=='poll' else None))
                cleanup=stack.enter_context(patch.object(runner.shared,'cleanup',return_value={'status':'completed'}))
                if fail:
                    with self.assertRaisesRegex((ValueError,TimeoutError),'memory coverage|poll original|installation mismatch'):
                        runner.run(file,'FAKE_ONLY','',m.p.digest(file),True)
                    self.assertEqual(poll.call_count,0 if fail=='installation' else 1)
                    self.assertEqual(cleanup.call_count,0 if fail=='installation' else 1)
                    receipt=m.p.read(root/'run/FINAL_RECEIPT.json')
                    self.assertEqual(receipt['status'],'stopped_no_resume');self.assertIn('original_stack',receipt)
                else:
                    out=runner.run(file,'FAKE_ONLY','',m.p.digest(file),True)
                    self.assertEqual((out['sessions'],out['requests']),(2,48))
                    self.assertEqual((poll.call_count,cleanup.call_count),(2,2))
                    self.assertEqual((root/'run/memory_candidate_freeze.json').read_bytes(),freeze.read_bytes())
                installed.assert_called_once();deploy.assert_not_called()
                self.assertTrue(runner.ObservedDevice.call_args.kwargs['forbid_apk_deploy'])
                self.assertTrue((root/'registry/claimed.json').exists())


if __name__=='__main__':unittest.main()
