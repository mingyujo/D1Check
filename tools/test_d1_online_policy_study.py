import copy
import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
import numpy as np
from tools import d1_online_policy_model as m
from tools import d1_online_policy_study as s
from tools import d1_arrival_energy_collection_device as runner
from tools import d1_energy_host_lifecycle as lifecycle
from tools.test_d1_ap_completion_study import cases as old_cases


def synthetic():
    params=m.p.read(m.PARAMETERS)['fixed_parameters'];out=[]
    paths=[[(35,45,'classification:CPU'),(45,75,'detection:CPU')],
           [(35,45,'classification:GPU'),(45,65,'classification:GPU+detection:CPU'),(65,75,'detection:CPU')],
           [(35,50,'classification:GPU'),(50,75,'detection:CPU')]]
    increments=np.array([.5,.8,.3,1.1])
    for i,policy in enumerate(m.POLICIES):
        seg=[dict(start_s=0,end_s=35,state='idle')]+[dict(start_s=a,end_s=b,state=x) for a,b,x in paths[i]]+[dict(start_s=75,end_s=180,state='idle')]
        c=old_cases()[1];c.update(id=str(i),policy=policy,inputs=dict(preload=c['inputs']['preload'],query_s=list(range(36,178,3)),segments=seg),preload_power_w=1.,origin_ns=0,power_samples=[],rows=[])
        c['observed_ap_c']=m.ap.predict(c,dict(beta=params['ap_cooling_rate_per_s'],k=.7,g=0.,parameters=params))[0]
        for j,q in enumerate(m.requests('development')):
            backend='CPU' if policy==m.POLICIES[0] or q['task_id']=='detection' else 'GPU'
            c['rows'].append(dict(q,selected_backend=backend,**dict(zip(m.FIELDS,[1,2,102,104,105,106]))))
        out.append(c)
    return out,increments


class OnlineTests(unittest.TestCase):
    def test_fit_identifiable_single_family_and_confirmation_forbidden(self):
        cc,z=synthetic()
        with patch.object(m,'energy_at',side_effect=lambda c,a,b:(b-a)+float(m.exposure(c['inputs']['segments'],a,b)@z)):
            fit=m.develop(cc)
            np.testing.assert_allclose(list(fit['energy_increment_w'].values()),z,atol=1e-10)
            self.assertAlmostEqual(fit['ap']['k'],.7,places=10)
            cc[0]['study_phase']='confirmation'
            with self.assertRaisesRegex(ValueError,'development'):m.develop(cc)
        with self.assertRaisesRegex(ValueError,'unsupported'):m.exposure([dict(start_s=0,end_s=1,state='detection:GPU')],0,1)
        with self.assertRaisesRegex(ValueError,'incomplete'):m.exposure([],0,1)

    def test_causal_forecast_and_policy_ownership(self):
        cc,z=synthetic()
        with patch.object(m,'energy_at',side_effect=lambda c,a,b:(b-a)+float(m.exposure(c['inputs']['segments'],a,b)@z)):fit=m.develop(cc)
        for policy in m.POLICIES:
            a=m.requests('confirmation');initial=dict(preload=cc[0]['inputs']['preload'],preload_power_w=1.)
            r,seg=m.forecast(initial,a,policy,fit)
            self.assertEqual(len(r['ledger']),96);self.assertTrue(all(x['status']=='succeeded' for x in r['ledger']))
            self.assertEqual([r['arrival_ns'] for r in r['ledger']],[q['offset_ms']*1000000 for q in a])
            initial.update(observed_ap_c=[999],rows=[{'future':'forbidden'}],power_samples=[999])
            self.assertEqual(r,m.forecast(initial,a,policy,fit)[0])
            costs=m.costs(seg,initial,list(range(35,181)),fit,180)
            self.assertTrue(np.isfinite(costs['whole_120s_j']))
            self.assertAlmostEqual(costs['whole_120s_j']-costs['prospective_35_120s_j'],35.)
            if policy!=m.POLICIES[1]:self.assertTrue(all('+' not in x['state'] for x in seg))
            initial['preload']=copy.deepcopy(initial['preload']);initial['preload'][-1]['hi']=36
            with self.assertRaises(ValueError):m.costs(seg,initial,list(range(35,181)),fit,180)

    def test_real_root_freezes_before_confirmation_and_preserves_failure(self):
        for failure in (None,'fit','confirmation'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);(root/'development').mkdir();(root/'confirmation').mkdir()
                file=root/'study_plan.json';s.cal.write_new(root/'old.json',{'whole_device_power_w':{}});s.cal.write_new(root/'development/collection_plan.json',{'frozen_model':{'path':str(root/'old.json')}})
                study=dict(output_root=str(root/'run'),registry=str(root/'registry'),contract={'sha256':'contract'},budget=s.p.read(s.CONTRACT)['budget'])
                s.cal.write_new(file,study);seen=[]
                def fake_run(f,*args):
                    phase=Path(f).parent.name;seen.append(phase)
                    if phase=='confirmation':
                        self.assertTrue((root/'run/model_freeze.json').exists())
                        if failure=='confirmation':raise TimeoutError('original confirmation')
                    return {'status':'completed_descriptive_only'}
                for obj,name,kw in [(s,'check',{}),(s,'check_block',{}),(s,'identity',{'return_value':{}}),
                    (s,'imported_cases',{'return_value':[]}),(s,'load_cases',{'return_value':[]}),(m,'develop',{'return_value':{'fixed':True},'side_effect':ValueError('unidentified') if failure=='fit' else None}),
                    (m,'evaluate',{'return_value':[]}),(runner,'run',{'side_effect':fake_run}),
                    (s,'block_spec',{'side_effect':lambda f,phase,b:({'study_freeze':b,'budget':{'total_seconds':5250}},[])}),
                    (lifecycle,'host_identity',{'return_value':{}})]:stack.enter_context(patch.object(obj,name,**kw))
                stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('real process forbidden')))
                if failure:
                    with self.assertRaises((ValueError,TimeoutError)):s.run(file,'FAKE',s.p.digest(file),True)
                    receipt=s.p.read(root/'run/FINAL_RECEIPT.json');self.assertEqual(receipt['status'],'stopped_no_resume');self.assertIn('original_stack',receipt)
                else:self.assertEqual(s.run(file,'FAKE',s.p.digest(file),True)['status'],'completed_development_and_confirmation')
                self.assertEqual(seen,['development'] if failure=='fit' else ['development','confirmation'])
                with self.assertRaises(FileExistsError):s.run(file,'FAKE',s.p.digest(file),True)

    def test_manifest_wire_and_budget(self):
        archive=Path('C:/Users/LG/Documents/D1Check_Arrival_Extension')
        source=archive/'energy_recorded_policy_compare_plan_v1/collection_plan.json'
        if not source.exists():self.skipTest('external immutable template unavailable')
        build=archive/'recorded_policy_compare_build_v1/build_receipt.json'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'study_plan.json'
            s.cal.write_new(file,dict(source_plan={'path':str(source)},build_receipt={'path':str(build),'sha256':s.p.digest(build)},
                candidate=s.p.read(source)['apk_preflight']['candidate'],contract={'path':str(s.CONTRACT),'sha256':s.p.digest(s.CONTRACT)},
                output_root=str(root/'run'),block_registry_root=str(root/'registry'),remaining_development_order=[m.POLICIES[2]]))
            for role,count in [('development',1),('confirmation',6)]:
                plan,ms=s.block_spec(file,role)
                self.assertTrue(plan['online_configuration_owner_v1']);self.assertEqual(plan['installed_only'],role=='confirmation');self.assertEqual(len(ms),count);self.assertEqual(plan['budget']['requests'],96*count)
                self.assertEqual(plan['budget']['total_seconds'],600+count*700+(count-1)*90)
                for mf in ms:
                    self.assertEqual(mf['policy_study_role'],role);self.assertNotIn('replay_version',mf)
                    self.assertEqual(len(mf['requests']),96)
                    self.assertNotIn('recorded_backend',mf['requests'][0])
            src=(s.ROOT/'benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalEnergyActivity.kt').read_text(encoding='utf8')
            self.assertIn('m.getString("policy_study_role")',src)

    def test_actual_device_entry_new_modes_and_cleanup_once(self):
        for phase,failure in [('development',None),('confirmation',None),('development','poll'),('confirmation','cleanup')]:
            with self.subTest(phase=phase,failure=failure),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);freeze=root/'freeze.json';s.cal.write_new(freeze,{'fixed':True})
                budget=dict(s.replay.BUDGET,per_session_adb_commands=3200,intersession_cooling_seconds=90)
                plan=dict(online_policy_study=True,study_phase=phase,study_freeze={'path':str(freeze),'sha256':s.p.digest(freeze)},
                    installed_only=phase=='confirmation',budget=budget,output_root=str(root/'run'),registry=str(root/'registry'),
                    apk_path='fixture.apk',apk_sha256='fixture',apk_preflight={'candidate':{}},
                    frozen_model=dict(path=str(freeze),sha256=s.p.digest(freeze)),source_files={},entries=[])
                mf=root/'manifest.json';s.cal.write_new(mf,{'session_id':'fixture','phase':phase})
                plan['entries']=[dict(index=0,session_id='fixture',manifest=mf.name)]
                file=root/'plan.json';s.cal.write_new(file,plan)
                fake=type('Fake',(),{'sequence':0,'deadline':None,'call':lambda *a,**k:None})()
                for obj,name,kw in [(s,'check_block',{}),(runner,'require_host_pull_space',{}),(runner,'ObservedDevice',{'return_value':fake}),
                    (lifecycle,'host_identity',{'return_value':{}}),(runner.energy_device,'gates',{}),
                    (runner.install,'installed_hash',{'return_value':'fixture'}),(runner.shared,'stage_inputs',{'return_value':'remote'}),
                    (runner.energy_device,'recover',{'return_value':{}}),(runner.energy_device,'pull_file',{'side_effect':ValueError('secondary recovery')}),
                    (runner,'validate',{'return_value':dict(status='eligible_descriptive_only',requests=96)})]:stack.enter_context(patch.object(obj,name,**kw))
                installed=stack.enter_context(patch.object(runner.energy_device,'installed_preflight',return_value={}))
                deploy=stack.enter_context(patch.object(runner.energy_device,'installation',return_value={}))
                poll=stack.enter_context(patch.object(runner,'poll',side_effect=TimeoutError('original poll') if failure=='poll' else None))
                cleanup=stack.enter_context(patch.object(runner.shared,'cleanup',side_effect=ValueError('cleanup failed') if failure=='cleanup' else None,return_value={}))
                stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('actual adb forbidden')))
                if failure:
                    with self.assertRaises((ValueError,TimeoutError)):runner.run(file,'FAKE','',s.p.digest(file),True)
                    r=s.p.read(root/'run/FINAL_RECEIPT.json');self.assertEqual(r['status'],'stopped_no_resume');self.assertIn('original_stack',r)
                else:self.assertEqual(runner.run(file,'FAKE','',s.p.digest(file),True)['requests'],96)
                self.assertEqual(cleanup.call_count,1)
                self.assertEqual(installed.call_count,int(phase=='confirmation'));self.assertEqual(deploy.call_count,int(phase=='development'))
                self.assertEqual(runner.ObservedDevice.call_args.kwargs['forbid_apk_deploy'],phase=='confirmation')

    def test_install_gate_cannot_stop_preexisting_app(self):
        from tools import d1_energy_collection_device as d
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp,patch.object(d.apk,'preflight',return_value={'candidate':{},'installed':{}}),patch.object(d,'gates',side_effect=ValueError('existing app active')),patch.object(d.shared,'cleanup',side_effect=AssertionError('not owned')) as cleanup:
            with self.assertRaisesRegex(ValueError,'existing app active'):
                d.installation(SimpleNamespace(deadline=None),{'online_policy_study':True},'fake',Path(tmp),d.time.monotonic()+600)
            cleanup.assert_not_called()

    def test_evaluation_export_and_portable_cli_have_no_device_or_refit(self):
        from tools import d1_online_policy_readout as readout
        cc,z=synthetic()
        with patch.object(m,'energy_at',side_effect=lambda c,a,b:(b-a)+float(m.exposure(c['inputs']['segments'],a,b)@z)):
            fitted=m.develop(cc)
            cases=[]
            for phase,order in [('development',m.POLICIES),('confirmation',list(m.POLICIES)+list(reversed(m.POLICIES)))]:
                for i,policy in enumerate(order):
                    c=copy.deepcopy(cc[m.POLICIES.index(policy)])
                    c.update(id=phase+str(i),study_phase=phase,manifest_requests=m.requests(phase),common_start_ap_c=30.,observed_120s_j=120.)
                    ledger,seg=m.forecast({},c['manifest_requests'],policy,fitted)
                    c['rows']=[dict(r,request_id=r['id'],scheduled_arrival_ns=r['arrival_ns']) for r in ledger['ledger']]
                    cases.append(c)
            evaluated=m.evaluate(cases,fitted)
            self.assertEqual(len(evaluated),9)
            with tempfile.TemporaryDirectory() as tmp,patch('subprocess.Popen',side_effect=AssertionError('device forbidden')),patch.object(m,'develop',side_effect=AssertionError('no refit')):
                root=Path(tmp);s.cal.write_new(root/'model_freeze.json',{'model':fitted})
                for phase in ('development','confirmation'):
                    s.cal.write_new(root/(phase+'_cases.json'),[c for c in cases if c['study_phase']==phase])
                    s.cal.write_new(root/(phase+'_evaluation.json'),[c for c in evaluated if c['phase']==phase])
                self.assertEqual(readout.export(root,root/'bundle')['cases'],9)
                self.assertEqual(readout.predict(root/'bundle','confirmation0',m.POLICIES[0],root/'prediction')['device_commands'],0)
                with self.assertRaises(FileExistsError):readout.predict(root/'bundle','confirmation0',m.POLICIES[0],root/'prediction')

    def test_power_negative_pre_origin_and_missing_not_zero(self):
        samples=[dict(mono_ns=i*1000000000,current_raw=-250,voltage_mV=4000,current_valid=True,plugged=0) for i in range(10,160)]
        c=dict(origin_ns=30000000000,power_samples=samples)
        self.assertAlmostEqual(m.energy_at(c,0,120),120.)
        c['power_samples']=samples[30:]
        with self.assertRaisesRegex(ValueError,'missing'):m.energy_at(c,0,120)

if __name__=='__main__':unittest.main()
