import copy
import json
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools import d1_history_control_plan as p
from tools import d1_history_control_analysis as a


def case(gap=30,policy='CPU_URGENT_ONLINE_V1',role='development'):
    frozen=a.m.read(a.m.MODEL);offset=120+gap+30
    pre=[dict(t=t,lo=t-.1,hi=t+.1,ap=30.) for t in range(-30,35,2)]
    local=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=70.,state='classification:CPU'),dict(start_s=70.,end_s=180.,state='idle')]
    if policy=='C0':local=[dict(start_s=0.,end_s=180.,state='idle')]
    seg=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=70.,state='classification:CPU'),dict(start_s=70.,end_s=float(offset),state='idle')]
    seg.extend(dict(s,start_s=s['start_s']+offset,end_s=s['end_s']+offset) for s in local)
    q=list(range(offset+36,offset+180,2))
    c=dict(id=f'{role}_{gap}_{policy}',role=role,gap=gap,target_policy=policy,
        inputs=dict(preload=pre,query_s=q,segments=seg),local_inputs=dict(preload=pre,query_s=[x-offset for x in q],segments=local),
        pre_w=1.,power_t=list(range(-30,182)),power_w=[1.]*212,observed_j=120.,last_lane_s=70. if policy!='C0' else 35.)
    base,x,_=a.basis(c,frozen);c['observed_ap_c']=(base+.4*x).tolist()
    return c


class HistoryTests(unittest.TestCase):
    def test_readonly_reuse_preserves_source_and_starts_no_runtime(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/'source';source.mkdir();p.cal.write_new(source/'input_manifest.json',dict(session_id='fixture'))
            (source/'progress.jsonl').write_text('original')
            hashes={str(f.relative_to(source)):p.p.digest(f) for f in source.iterdir()}
            plan=dict(history_reuse=dict(source_folder=str(source),file_sha256=hashes),entries=[dict(index=0,session_id='fixture',manifest_sha256=hashes['input_manifest.json'])])
            root=Path(t)/'new';root.mkdir()
            with patch.object(a,'validate',return_value=dict(status='eligible_descriptive_only')):
                result=p.reuse_first(plan,root)
            self.assertEqual(result['new_device_calls'],0);self.assertTrue((root/'00_fixture/validated.json').exists())
            self.assertFalse((source/'validated.json').exists());self.assertEqual({str(f.relative_to(source)):p.p.digest(f) for f in source.iterdir()},hashes)
            (source/'progress.jsonl').write_text('drift')
            with self.assertRaisesRegex(ValueError,'raw drift'):p.reuse_first(plan,root)

    def test_common_energy_coverage_not_cooling_tail_extrapolation(self):
        power=[dict(mono_ns=i*1_000_000_000,current_raw=-100,voltage_mV=4000,plugged=0,current_valid=True) for i in range(360)]
        result=a.power_coverage(power,0,180_000_000_000,360_000_000_000)
        self.assertIsNotNone(result['registered_history_common']['full_energy_j'])
        self.assertIsNone(result['cooling']['full_energy_j']);self.assertAlmostEqual(result['cooling']['missing_s'],1)
        missing=[x for x in power if not 150_000_000_000<x['mono_ns']<160_000_000_000]
        with self.assertRaisesRegex(ValueError,'registered common'):a.power_coverage(missing,0,180_000_000_000,360_000_000_000)

    def test_budget_and_registered_denominators(self):
        b=p.budget();self.assertEqual(b['total_seconds'],19557)
        self.assertEqual(b['session_seconds'],1446);self.assertEqual(b['explicit_inference'],2016)
        self.assertEqual(b['adb_commands'],91400)
        d=p.p.read(p.DESIGN);self.assertEqual(len(d['entries']),12)
        self.assertEqual(sum(e['conditioning_requests']+e['target_requests']+e['warmup'] for e in d['entries']),2016)

    def test_continuous_basis_recovers_one_coefficient_without_target_assimilation(self):
        c=case();f=a.m.read(a.m.MODEL);fit=a.fit([c],f)
        self.assertAlmostEqual(fit['g'],.4,places=10)
        original=a.basis(c,f)[0];changed=copy.deepcopy(c);changed['observed_ap_c']=[900.]*len(original)
        np.testing.assert_array_equal(a.basis(changed,f)[0],original)
        r=a.evaluate(c,f,fit);self.assertLess(r['candidate']['mae_c'],1e-10)
        self.assertAlmostEqual(sum(r[k+'_signed_j'] for k in ('pre','load','post')),r['signed_j'],places=10)

    def test_confirmation_cannot_fit_and_future_initial_input_rejected(self):
        f=a.m.read(a.m.MODEL)
        with self.assertRaisesRegex(ValueError,'development only'):a.fit([case(role='confirmation')],f)
        c=case();c['inputs']['preload'][-1]['hi']=35
        with self.assertRaisesRegex(ValueError,'future AP'):a.basis(c,f)
        c=case();c['inputs']['segments'][1]['state']='detection:GPU'
        with self.assertRaisesRegex(ValueError,'unsupported state'):a.basis(c,f)

    def test_complete_development_cells_and_unidentified_coefficient(self):
        f=a.m.read(a.m.MODEL);cases=[case(gap,policy) for gap in (30,180) for policy in ('C0','CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1')]
        r=a.develop(cases,f);self.assertEqual(len(r['folds']),2)
        with self.assertRaisesRegex(ValueError,'six development'):a.develop(cases[:-1],f)
        with patch.object(a,'basis',return_value=(np.ones(5),np.zeros(5),{})):
            bad=case();bad['observed_ap_c']=[1.]*5
            with self.assertRaisesRegex(ValueError,'unidentified'):a.fit([bad],f)

    def test_reservation_and_failed_freeze_never_enters_confirmation(self):
        plan=dict(budget=p.budget(),entries=[dict(index=i) for i in range(12)])
        with patch.object(p,'pc_stage',side_effect=RuntimeError('development gate failed')) as stage,patch.object(p,'freeze_verify') as verify:
            with self.assertRaisesRegex(ValueError,'reservation'):p.before_entry(plan,'unused',dict(index=6),[],time.monotonic())
            stage.assert_not_called()
            with self.assertRaisesRegex(RuntimeError,'development gate'):p.before_entry(plan,'unused',dict(index=6),[dict(status='eligible_descriptive_only')]*6,10**15)
            verify.assert_not_called();stage.assert_called_once()

    def test_frozen_bytes_and_no_silent_overwrite(self):
        self.assertEqual(p.p.digest(a.m.MODEL),a.m.MODEL_SHA)
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'freeze.json';p.cal.write_new(f,dict(g=.4));original=f.read_bytes()
            with self.assertRaises(FileExistsError):p.cal.write_new(f,dict(g=.5))
            self.assertEqual(f.read_bytes(),original)

    def test_existing_cleanup_failure_precedes_missing_history_summary(self):
        with tempfile.TemporaryDirectory() as t:
            art=Path(t)/'artifacts';art.mkdir()
            p.cal.write_new(art/'cleanup.json',dict(status='failed'))
            p.cal.write_new(art/'session_failure.json',dict(error='original_stack'))
            with self.assertRaisesRegex(RuntimeError,'original_stack'):a.validate(t,{}, {})

    def test_pc_child_timeout_preserves_log(self):
        import subprocess
        with tempfile.TemporaryDirectory() as t,patch.object(p.subprocess,'run',side_effect=subprocess.TimeoutExpired('fixture',1)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):p.pc_stage({},t,'freeze',1)
            self.assertEqual(run.call_args.kwargs['timeout'],1)
            self.assertTrue((Path(t)/'freeze.log').exists())

    def exercise_entry(self,fail_freeze):
        from tools import d1_arrival_energy_collection_device as runner
        from tools import d1_energy_host_lifecycle as life
        from tools.test_d1_background_activity_plan import FakeDevice
        with tempfile.TemporaryDirectory() as t,ExitStack() as stack:
            root=Path(t);model=root/'model.json';model.write_text('{}')
            b=p.budget();b['intersession_cooling_seconds']=0
            entries=[]
            for i in range(12):
                import uuid
                sid=str(uuid.uuid4());file=root/f'{i}.json';p.cal.write_new(file,dict(session_id=sid))
                entries.append(dict(index=i,session_id=sid,manifest=file.name,requests=0))
            plan=dict(history_control=True,history_trace={},background_activity_contrast=True,
                online_policy_study=True,online_configuration_owner_v1=True,installed_only=False,
                study_phase='development',budget=b,apk_sha256='fixture',apk_preflight={'candidate':{}},
                frozen_model={'path':str(model)},source_files={},output_root=str(root/'run'),registry=str(root/'registry'),entries=entries)
            file=root/'collection_plan.json';p.cal.write_new(file,plan)
            d=FakeDevice();order=[]
            def stage(*args):
                order.append('freeze')
                if fail_freeze:raise ValueError('development gate fixture')
            def cleanup(*args):order.append('cleanup');return dict(status='completed')
            for obj,name,options in [(p,'check',{}),(p,'pc_stage',{'side_effect':stage}),
                (p,'freeze_verify',{}),(p,'finish_analysis',{}),
                (runner,'ObservedDevice',{'return_value':d}),(runner,'require_host_pull_space',{}),
                (life,'host_identity',{'return_value':{}}),(runner.energy_device,'installation',{'return_value':{}}),
                (runner.energy_device,'gates',{}),(runner.install,'installed_hash',{'return_value':'fixture'}),
                (runner.shared,'stage_inputs',{'return_value':'owned'}),(runner,'poll',{}),
                (runner.energy_device,'recover',{'return_value':{}}),(runner.energy_device,'pull_file',{}),
                (runner.shared,'cleanup',{'side_effect':cleanup}),
                (p.bg,'trace_start',{}),(p.bg,'trace_recover',{'return_value':{'errors':[]}}),
                (runner,'validate',{'return_value':dict(status='eligible_descriptive_only',requests=0,conditioning_requests=96)})]:
                stack.enter_context(patch.object(obj,name,**options))
            stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('device/process forbidden')))
            if fail_freeze:
                with self.assertRaisesRegex(ValueError,'development gate fixture'):runner.run(file,'FAKE','FAKE',p.p.digest(file),True)
                receipt=p.p.read(root/'run/FINAL_RECEIPT.json')
                self.assertEqual(receipt['completed_sessions'],6)
                self.assertEqual(order,['cleanup']*6+['freeze'])
                p.finish_analysis.assert_not_called()
            else:
                receipt=runner.run(file,'FAKE','FAKE',p.p.digest(file),True)
                self.assertEqual(receipt['sessions'],12)
                self.assertEqual(order,['cleanup']*6+['freeze']+['cleanup']*6)
                self.assertEqual(receipt['explicit_inference'],12*104)
                p.finish_analysis.assert_called_once()
            with self.assertRaises(FileExistsError):runner.run(file,'FAKE','FAKE',p.p.digest(file),True)

    def test_actual_host_entry_twelve_sessions_freeze_once_cleanup_once_each(self):self.exercise_entry(False)

    def test_actual_host_entry_failed_freeze_stops_before_seventh_and_no_repeat_cleanup(self):self.exercise_entry(True)

    def test_artifact_loader_two_origins_power_integral_and_actual_lane_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);art=root/'artifacts';art.mkdir();origin=10**12
            def ns(s):return origin+int(s*1e9)
            p.cal.write_new(art/'history_boundary.json',dict(conditioning_start_ns=origin,target_start_ns=ns(180),target_baseline_start_ns=ns(150)))
            row=dict(request_id='one',scheduled_arrival_ns=ns(35),task_id='classification',selected_backend='CPU',priority='urgent',
                dispatch_ns=ns(35),execution_start_ns=ns(35),output_ready_ns=ns(35.8),persist_complete_ns=ns(35.9),worker_release_ns=ns(36),lane_available_ns=ns(36.2))
            p.cal.write_new(art/'conditioning_requests.json',[row]);p.cal.write_new(art/'requests.json',[])
            ev=[dict(kind='phase_start',phase='resident_baseline',mono_ns=ns(-30)),dict(kind='phase_end',phase='resident_cooling',mono_ns=ns(360))]
            ev.extend(dict(kind='power_sample',mono_ns=ns(s)+3,snapshot_start_ns=ns(s)-1,sensor_read_end_ns=ns(s)+1,
                state_snapshot_ns=ns(s)+2,resident_keys=list(a.c.old.KEYS),current_raw=-250,voltage_mV=4000,plugged=0,current_valid=True) for s in range(-31,362))
            (art/'progress.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in ev),encoding='utf8')
            thermal=[dict(mono_ns=ns(s),before_ns=ns(s-.05),after_ns=ns(s+.05),AP='30.0',thermal_status='0') for s in range(-30,360,2)]
            (root/'thermal.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in thermal),encoding='utf8')
            c=a.load_case(root,dict(session_id='fixture',history_role='development',history_recovery_seconds=30,history_target_policy='C0'))
            self.assertEqual(c['target_offset_s'],180);self.assertAlmostEqual(c['observed_j'],120)
            occupied=[s for s in c['inputs']['segments'] if s['state']!='idle']
            self.assertAlmostEqual(occupied[0]['end_s'],36.2)
            self.assertGreater(len(c['fit_observed_ap_c']),len(c['observed_ap_c']))
            a.basis(c,a.m.read(a.m.MODEL))
            thermal=[e for e in thermal if not ns(60)<e['mono_ns']<ns(100)]
            (root/'thermal.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in thermal),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'history AP coverage'):a.load_case(root,dict(session_id='fixture'))


if __name__=='__main__':unittest.main()
