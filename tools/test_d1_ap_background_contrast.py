import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from tools import d1_ap_background_contrast as m
from tools import d1_ap_background_contrast_readout as r
from tools import d1_arrival_energy_collection_device as runner
from tools import d1_energy_host_lifecycle as lifecycle
from tools.test_d1_ap_preparation_memory import synthetic


class ContrastTests(unittest.TestCase):
    def test_manifest_order_arrivals_counts_and_time_reserve(self):
        template=dict(models={'x':{'identity':{}}},scenario='burst',policy=m.memory.base.replay.POLICY,
            start_ap_gate='numeric-ap-observe-v2',requests=m.p.read(m.memory.base.control.BUNDLE/'load_input.json')['requests'])
        with patch.object(m.memory,'specification',return_value=({'ap_memory_confirmation':True,'approval':'not_approved'},[template,template])),patch.object(m,'identity',return_value={}):
            plan,mm=m.specification('source','build',Path('parent')/m.FOLDER)
        m.budget_check(plan['budget']);self.assertNotIn('ap_memory_confirmation',plan)
        self.assertEqual([len(x['requests']) for x in mm],[0,24,24,24,24,0])
        self.assertEqual(sum(e['requests'] for e in plan['entries'])+48,144)
        self.assertEqual(plan['budget']['total_seconds'],5250)
        for i in [1,2,3,4]:
            for row,original in zip(mm[i]['requests'],template['requests']):
                self.assertEqual((row['offset_ms'],row['recorded_backend']),(original['offset_ms'],original['recorded_backend']))
                self.assertEqual(row['release_offset_ns']-original['release_offset_ns'],30_000_000_000 if i in (2,3) else 0)
        for condition in set(m.CONDITIONS):
            indices=[i+1 for i,c in enumerate(m.CONDITIONS) if c==condition]
            self.assertEqual(sum(indices)/2,3.5)

    def test_consumed_plan_stops_before_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/m.FOLDER;folder.mkdir();run=Path(tmp)/'run';run.mkdir()
            f=folder/'collection_plan.json';m.cal.write_new(f,dict(output_root=str(run),registry=str(Path(tmp)/'registry')))
            with patch.object(m,'specification',side_effect=AssertionError('must not inspect APK')):
                with self.assertRaisesRegex(ValueError,'occupied/consumed'):m.check(f)

    def test_common_cutoff_allows_control_and_wait_but_no_later_initialization(self):
        binding=dict(memory_candidate={'path':str(m.memory.CANDIDATE)})
        c=synthetic();c['inputs']['segments']=[dict(start_s=0,end_s=180,state='idle')]
        values,init=r.predict_fixed(c,binding)
        self.assertEqual(len(values),len(c['inputs']['query_s']))
        self.assertLess(init['input_end_s'],35)
        c=synthetic();c['inputs']['segments'][0]['end_s']=65
        c['inputs']['segments'][1].update(start_s=65,end_s=77);c['inputs']['segments'][2]['start_s']=77
        a=r.predict_fixed(c,binding)
        c['observed_ap_c']=[999]*len(c['inputs']['query_s'])
        self.assertEqual(a,r.predict_fixed(c,binding))
        c['inputs']['preload'].append(dict(t=40,ap=30,lo=39.9,hi=40.1))
        with self.assertRaisesRegex(ValueError,'cutoff'):r.predict_fixed(c,binding)

    def test_prediction_continuity_and_supported_only(self):
        c=synthetic();binding=dict(memory_candidate={'path':str(m.memory.CANDIDATE)})
        old=m.memory.model.predict(c,m.p.read(m.memory.CANDIDATE)['fixed_parameters'],30,0)
        self.assertEqual(old,r.predict_fixed(c,binding))
        c['inputs']['segments'][1]['state']='unknown'
        with self.assertRaisesRegex(ValueError,'unsupported'):r.predict_fixed(c,binding)
        c=synthetic();c['inputs']['query_s']=[36,60]
        with self.assertRaisesRegex(ValueError,'boundary'):r.predict_fixed(c,binding)

    def test_partial_contrasts_null_and_linear_order_balancing(self):
        contract=m.p.read(m.BUNDLE/'analysis_contract.json');items=[]
        means={'C':1,'L35':3,'L65':4}
        for i,(role,condition) in enumerate(zip(m.ROLES,m.CONDITIONS)):
            items.append(dict(role=role,condition=condition,status='evaluated_fixed_candidate',windows=[
                dict(axis='common_origin',start_s=a,end_s=b,observed_change_c=means[condition]+.2*(i+1))
                for a,b in contract['fixed_direction_windows_s']]))
        result=r.contrasts(items,contract)
        self.assertAlmostEqual(result[0]['L35_minus_C'],2)
        self.assertAlmostEqual(result[0]['L65_minus_L35'],1)
        self.assertIsNone(r.contrasts(items[:-1],contract)[0]['L35_minus_C'])
        items[0]['windows'][0]['observed_change_c']=None
        self.assertIsNone(r.contrasts(items,contract)[0]['L65_minus_C'])

    def test_control_has_no_fake_work_axis(self):
        c=synthetic();c.update(id='control_first',condition='C',requests=0,first_dispatch_s=None,last_lane_s=None,common_start_ap_c=29.)
        c['inputs']['segments']=[dict(start_s=0,end_s=180,state='idle')]
        values,init=r.predict_fixed(c,dict(memory_candidate={'path':str(m.memory.CANDIDATE)}))
        c['observed_ap_c']=values
        result=r.describe(c,values,init,m.p.read(m.BUNDLE/'analysis_contract.json'))
        self.assertEqual(len(result['windows']),3)
        self.assertEqual(result['phase_scores'][0]['phase'],'no_work')

    def test_real_runner_six_arms_and_failure_boundaries(self):
        for fail in (None,'coverage','poll','recover','cleanup','recover_and_cleanup','reserve','installation'):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);freeze=root/'freeze.json';m.cal.write_new(freeze,{'fixed':True})
                binding=dict(path=str(freeze),sha256=m.p.digest(freeze))
                plan=dict(ap_background_contrast=True,ap_bundled_confirmation=True,resident_control_pair=True,recorded_replay_confirmation=True,
                    budget=m.BUDGET,output_root=str(root/'run'),registry=str(root/'registry'),apk_path='fixture.apk',
                    apk_sha256='fixture',apk_preflight={'candidate':{}},source_files={},memory_candidate=binding,
                    candidate_freeze=binding,analysis_contract=binding,entries=[])
                for i,(role,condition) in enumerate(zip(m.ROLES,m.CONDITIONS)):
                    mf=root/f'{i}.json';m.cal.write_new(mf,dict(session_id=str(i),phase=role,condition=condition))
                    plan['entries'].append(dict(index=i,session_id=str(i),manifest=mf.name,phase=role,condition=condition,requests=0 if condition=='C' else 24))
                file=root/'plan.json';m.cal.write_new(file,plan);clock=[0.]
                def now():clock[0]+=.1;return clock[0]
                def sleep(seconds):clock[0]+=seconds
                fake=type('Fake',(),{'sequence':0,'deadline':None,'call':lambda *a,**k:None})()
                def validate(folder,manifest,plan):
                    if fail=='reserve':clock[0]+=701
                    return dict(status='eligible_descriptive_only',requests=0 if manifest['condition']=='C' else 24)
                for obj,name,kwargs in [(m,'check',{}),(runner,'require_host_pull_space',{}),
                    (runner,'ObservedDevice',{'return_value':fake}),
                    (lifecycle,'host_identity',{'return_value':{'parent':{'status':'present'},'child':{'status':'present'}}}),
                    (runner.time,'monotonic',{'side_effect':now}),(runner.time,'sleep',{'side_effect':sleep}),
                    (runner.energy_device,'gates',{}),(runner.install,'installed_hash',{'return_value':'fixture'}),
                    (runner.shared,'stage_inputs',{'return_value':'remote'}),
                    (runner.energy_device,'recover',{'side_effect':ValueError('recover original') if fail in ('recover','recover_and_cleanup') else None,'return_value':{'status':'recovered'}}),
                    (runner.energy_device,'pull_file',{'side_effect':ValueError('partial recovery')}),
                    (runner,'validate',{'side_effect':validate}),
                    (r,'case_from_session',{'side_effect':ValueError('AP coverage original') if fail=='coverage' else None}),
                    (r,'predict_fixed',{'return_value':([],{'fixed':True})})]:
                    stack.enter_context(patch.object(obj,name,**kwargs))
                stack.enter_context(patch.object(runner.energy_device,'installed_preflight',side_effect=ValueError('installation mismatch') if fail=='installation' else None,return_value={}))
                deploy=stack.enter_context(patch.object(runner.energy_device,'installation',side_effect=AssertionError('no deployment')))
                poll=stack.enter_context(patch.object(runner,'poll',side_effect=TimeoutError('poll original') if fail=='poll' else None))
                cleanup=stack.enter_context(patch.object(runner.shared,'cleanup',side_effect=ValueError('cleanup original') if fail in ('cleanup','recover_and_cleanup') else None,return_value={'status':'completed'}))
                if fail:
                    with self.assertRaisesRegex((ValueError,TimeoutError),'original|installation mismatch|session exceeded'):runner.run(file,'FAKE_ONLY','',m.p.digest(file),True)
                    self.assertEqual(poll.call_count,0 if fail=='installation' else 1)
                    self.assertEqual(cleanup.call_count,0 if fail=='installation' else 1)
                    receipt=m.p.read(root/'run/FINAL_RECEIPT.json')
                    self.assertEqual(receipt['status'],'stopped_no_resume');self.assertIn('original_stack',receipt)
                    if fail=='recover_and_cleanup':
                        self.assertIn('recover original',receipt['error']);self.assertIn('cleanup original',receipt['host_cleanup_error'])
                else:
                    result=runner.run(file,'FAKE_ONLY','',m.p.digest(file),True)
                    self.assertEqual((result['sessions'],result['requests'],result['warmup']),(6,96,48))
                    self.assertEqual((poll.call_count,cleanup.call_count),(6,6))
                    self.assertEqual((root/'run/memory_candidate_freeze.json').read_bytes(),freeze.read_bytes())
                deploy.assert_not_called()
                self.assertTrue(runner.ObservedDevice.call_args.kwargs['forbid_apk_deploy'])


if __name__=='__main__':unittest.main()
