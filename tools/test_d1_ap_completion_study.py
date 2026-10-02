import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools import d1_ap_completion_model as m
from tools import d1_ap_completion_study as s
from tools import d1_ap_preparation_memory as memory
from tools import d1_energy_host_lifecycle as lifecycle
from tools import d1_arrival_energy_collection_device as runner


PARAMS=s.p.read(s.contrast.memory.CANDIDATE)['fixed_parameters']


def cases(k=.8,g=.4):
    result=[];beta=PARAMS['ap_cooling_rate_per_s']
    for i,c in enumerate(('C','L35','L65','L65','L35','C')):
        pre=[]
        for t in range(-30,35,3):
            value,_=memory.advance(30+i*.1,.02,0,28+i*.1,beta,30,0,t+30)
            pre.append(dict(t=float(t),ap=value,lo=t-.05,hi=t+.05))
        start=65 if c=='L65' else 35
        segments=[dict(start_s=0,end_s=180,state='idle')] if c=='C' else [
            dict(start_s=0,end_s=start,state='idle'),dict(start_s=start,end_s=start+12,state='detection:CPU'),
            dict(start_s=start+12,end_s=180,state='idle')]
        case=dict(id='dev_'+str(i),condition=c,study_phase='development',requests=0 if c=='C' else 24,
            first_dispatch_s=None if c=='C' else start,last_lane_s=None if c=='C' else start+12,
            common_start_ap_c=29.,inputs=dict(preload=pre,query_s=list(range(36,180,3)),segments=segments))
        case['observed_ap_c']=m.predict(case,dict(beta=beta,k=k,g=g,parameters=PARAMS))[0]
        result.append(case)
    return result


class StudyTests(unittest.TestCase):
    def test_linear_delayed_basis_and_continuity(self):
        c=cases()[1];beta=PARAMS['ap_cooling_rate_per_s'];init=memory.initialize(c['inputs']['preload'],beta,30)
        values,_=m.predict(c,dict(beta=beta,k=2.,g=1.,parameters=PARAMS))
        slopes=copy.deepcopy(PARAMS['ap_slope_at_30_c_per_s']);idle=slopes['resident_idle']
        slopes={k:idle+2*(v-idle) for k,v in slopes.items()}
        expected=memory._propagate(c['inputs']['segments'],c['inputs']['query_s'],slopes,beta,30,.5,init)
        np.testing.assert_allclose(values,expected,atol=1e-11)
        q=copy.deepcopy(c);q['observed_ap_c']=[999]*len(values)
        self.assertEqual(m.predict(c,dict(beta=beta,k=2.,g=1.,parameters=PARAMS)),m.predict(q,dict(beta=beta,k=2.,g=1.,parameters=PARAMS)))

    def test_known_parameters_equal_session_weight_and_no_confirmation_fit(self):
        cc=cases();best,rows=m.fit(cc,PARAMS)
        self.assertAlmostEqual(best['beta'],PARAMS['ap_cooling_rate_per_s'],places=10)
        self.assertAlmostEqual(best['k'],.8,places=8);self.assertAlmostEqual(best['g'],.4,places=8)
        self.assertEqual((best['load_rank'],best['numerical_rank'],len(rows)),(2,3,61))
        cc[0]['study_phase']='confirmation'
        with self.assertRaisesRegex(ValueError,'development-only'):m.fit(cc,PARAMS)

    def test_selection_control_missing_and_rank_boundaries(self):
        contract=s.p.read(s.CONTRACT);cc=cases();result=m.develop(cc,PARAMS,contract)
        self.assertEqual(result['status'],'ready_to_freeze');self.assertEqual(result['selected_name'],'M1')
        with self.assertRaisesRegex(ValueError,'complete'):m.develop(cc[:-1],PARAMS,contract)
        control=cc[0];control['observed_ap_c']=[25+t*.03 for t in control['inputs']['query_s']]
        ds=m.directions(control,m.predict(control,result['selected_model'])[0],contract['direction_windows_s'])
        self.assertTrue(any(d['opposite'] for d in ds))
        with patch.object(m,'fit',return_value=(dict(result['m1'],beta_boundary=True),[])):
            self.assertEqual(m.develop(cases(),PARAMS,contract)['status'],'unidentified_stop')
        values=[30.]*len(control['observed_ap_c']);control['observed_ap_c']=values
        self.assertTrue(all(d['observed_direction']=='unresolved' for d in m.directions(control,values,contract['direction_windows_s'])))

    def test_future_missing_and_unsupported_inputs(self):
        frozen=dict(beta=PARAMS['ap_cooling_rate_per_s'],k=1.,g=0.,parameters=PARAMS)
        for mutate in [lambda c:c['inputs']['preload'][-1].update(hi=35),
            lambda c:c['inputs'].update(query_s=[36,60]),lambda c:c['inputs']['segments'][1].update(state='unmeasured'),
            lambda c:c['inputs']['preload'][0].update(ap=float('nan'))]:
            c=cases()[1];mutate(c)
            with self.assertRaises(ValueError):m.predict(c,frozen)

    def test_actual_root_run_freezes_before_confirmation_and_stops_scientific_failure(self):
        for failure in (None,'scientific','development','confirmation','receipt_write','receipt_read'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);planfile=root/'study_plan.json';dev=root/'development';conf=root/'confirmation'
                dev.mkdir();conf.mkdir();s.contrast.cal.write_new(dev/'collection_plan.json',{'plan':'dev'})
                study=dict(output_root=str(root/'run'),registry=str(root/'registry'),contract={'sha256':'fixture'},
                    budget=s.p.read(s.CONTRACT)['budget']);s.contrast.cal.write_new(planfile,study)
                seen=[]
                def fake_run(file,*args):
                    phase=Path(file).parent.name;seen.append(phase)
                    if phase=='confirmation':
                        self.assertTrue((root/'run/model_freeze.json').exists())
                        self.assertEqual(s.p.read(file)['study_freeze']['sha256'],s.p.digest(root/'run/model_freeze.json'))
                    if failure=='receipt_read' and phase=='development':
                        (root/'run/development').mkdir()
                        (root/'run/development/FINAL_RECEIPT.json').write_text('{bad json',encoding='utf-8')
                        raise RuntimeError('development original')
                    if failure==phase:raise RuntimeError(phase+' original')
                    return dict(status='completed_descriptive_only',sessions=6,requests=96,warmup=48,adb_commands=10,elapsed_seconds=.1)
                result=dict(status='ready_to_freeze',selected_name='M0',selected_model={'fixed':True},m0={'fixed':True},reason='fixed')
                if failure=='scientific':result.update(status='unidentified_stop',selected_model=None)
                for obj,name,kwargs in [(s,'check',{}),(s,'check_block',{}),
                    (lifecycle,'host_identity',{'return_value':{'parent':{'status':'present'},'child':{'status':'present'}}}),
                    (runner,'run',{'side_effect':fake_run}),(s,'load_cases',{'return_value':[]}),
                    (s,'evaluate',{}),(m,'develop',{'return_value':result}),
                    (s,'block_spec',{'side_effect':lambda f,phase,binding:({'study_freeze':binding,'budget':s.contrast.BUDGET},[])})]:
                    stack.enter_context(patch.object(obj,name,**kwargs))
                stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('no real subprocess')))
                if failure=='receipt_write':
                    atomic=s.checkpoints.atomic_new
                    def failing_atomic(path,value):
                        if Path(path).name=='FINAL_RECEIPT.json':raise OSError('receipt fixture failure')
                        return atomic(path,value)
                    stack.enter_context(patch.object(s.checkpoints,'atomic_new',side_effect=failing_atomic))
                # A completed development directory is needed only for inventory enumeration.
                (root/'run').mkdir();(root/'run').rmdir()
                if failure in ('development','confirmation','receipt_read'):
                    with self.assertRaisesRegex(RuntimeError,'original'):s.run(planfile,'FAKE_ONLY',s.p.digest(planfile),True)
                elif failure=='receipt_write':
                    with self.assertRaisesRegex(RuntimeError,'persistence failed'):s.run(planfile,'FAKE_ONLY',s.p.digest(planfile),True)
                else:s.run(planfile,'FAKE_ONLY',s.p.digest(planfile),True)
                receipt=s.p.read(root/'run/TERMINAL_RECORDING_ERROR.json')['outcome'] if failure=='receipt_write' else s.p.read(root/'run/FINAL_RECEIPT.json')
                self.assertEqual(seen,['development'] if failure in ('development','scientific','receipt_read') else ['development','confirmation'])
                if failure in ('development','confirmation','receipt_read'):self.assertIn('original',receipt['error']);self.assertIn('original_stack',receipt)
                if failure=='receipt_read':self.assertEqual(receipt['secondary_recording_errors'][0]['stage'],'development_receipt_read')
                if failure=='scientific':self.assertEqual(receipt['status'],'completed_development_unidentified_no_confirmation')

    def test_common_collection_entry_study_branch_uses_existing_failure_cleanup(self):
        from tools.test_d1_ap_background_contrast import ContrastTests
        actual=runner.run
        def study_entry(file,*args,**kwargs):
            plan=s.p.read(file)
            plan.update(ap_completion_study=True,study_phase='confirmation',study_freeze=plan['memory_candidate'])
            Path(file).write_bytes(s.p.canonical(plan))
            args=list(args);args[2]=s.p.digest(file)
            return actual(file,*args,**kwargs)
        with patch.object(s,'check_block'),patch.object(runner,'run',side_effect=study_entry),patch('subprocess.Popen',side_effect=AssertionError('no real adb')):
            ContrastTests('test_real_runner_six_arms_and_failure_boundaries').test_real_runner_six_arms_and_failure_boundaries()

    def test_unbound_confirmation_stops_before_device_and_consumed_root_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'plan.json';s.contrast.cal.write_new(f,{'ap_completion_study':True,'study_phase':'confirmation','study_freeze':None})
            with patch.object(s,'check_block'),patch.object(runner,'ObservedDevice',side_effect=AssertionError('device must not start')):
                with self.assertRaisesRegex(ValueError,'frozen study model'):runner.run(f,'FAKE_ONLY','',s.p.digest(f),True)
            root=Path(tmp)/s.FOLDER;root.mkdir();output=Path(tmp)/'run';output.mkdir()
            pf=root/'study_plan.json';s.contrast.cal.write_new(pf,dict(registry=str(Path(tmp)/'registry'),output_root=str(output)))
            with patch.object(s,'verify_sources'),patch.object(s,'check_block',side_effect=AssertionError('no inspection')):
                with self.assertRaisesRegex(ValueError,'consumed'):s.check(pf)


if __name__=='__main__':unittest.main()
