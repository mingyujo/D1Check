"""PC-only registered entry and bounded host tests. No real device constructor."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from tools import d1_ap_tail_observation_plan as p
from tools import d1_energy_collection_device as host
from tools.test_d1_energy_host_failure import FakeDevice,HostFailureTest


def manifest(profile):
    return dict(protocol=p.PROTOCOL,tail_observation_version=p.VERSION,calibration_version=p.VERSION,
        identification_profile=profile,maximum_duration_ms=p.WATCHDOG_MS,baseline_seconds=120,
        common_work_seconds=600,cooling_seconds=1920,work_call_cap=p.budget()['profiles'][p.PROFILES.index(profile)]['work_requests'],
        cadence_ms=250,power_sample_period_ms=900,start_ap_gate='numeric-ap-observe-v2',blocks=p.blocks(profile),
        state_model_calibration=True,operational_only=True,autonomous_diagnostic_only=True,experiment_ready=False,
        session_control='device-after-probe-diagnostic-v1',mode='calibration')


class TailPlanTests(unittest.TestCase):
    def test_followup_is_a_new_registered_namespace_not_reset(self):
        new=p.registration('ENERGY-AP-TAIL-OBSERVATION-02')
        self.assertEqual(new['folder'],'energy_ap_tail_observation_plan_v3')
        self.assertNotEqual(new['run'],p.registration(p.NAME)['run'])
        self.assertNotEqual(new['contract'],p.CONTRACT)
        with self.assertRaises(ValueError):p.registration('unapproved_automatic_third_run')

    def test_low_battery_is_explicit_and_other_host_gates_survive(self):
        low=manifest('C0_LONG');low.update(protocol=p.LOW_BATTERY_PROTOCOL,tail_battery_gate_version=p.LOW_BATTERY_GATE,battery_min_percent=6,battery_stop_at_percent=5)
        p.validate_manifest(low)
        for bad in [dict(low,battery_min_percent=0),dict(low,protocol=p.PROTOCOL),dict(low,tail_battery_gate_version='unknown')]:
            with self.assertRaises(ValueError):p.validate_manifest(bad)
        from tools import d1_arrival_device as host_gate
        plan=dict(battery_start_percent=6,battery_min_percent=6,battery_max_temperature_tenths_c=350,require_unplugged=True)
        raw='level: 19\nscale: 100\ntemperature: 299\nAC powered: false\nUSB powered: false\nWireless powered: false\n'
        host_gate.battery_gate(plan,raw,True)
        for bad in [raw.replace('level: 19','level: 5'),raw.replace('temperature: 299','temperature: 351'),raw.replace('USB powered: false','USB powered: true')]:
            with self.assertRaises(RuntimeError):host_gate.battery_gate(plan,bad,True)

    def test_exact_budget_and_reservations(self):
        b=p.budget()
        self.assertEqual((b['sessions'],b['explicit_inference'],b['fixed_observation_seconds']), (2,1224,5280))
        self.assertEqual(b['total_seconds'],9050);self.assertEqual(b['adb_command_slots'],16752)
        self.assertEqual(sum(b['app_stage_timeout_seconds'].values()),3405)
        self.assertLess(3405,b['app_watchdog_seconds']);self.assertGreater(b['host_poll_seconds'],b['app_watchdog_seconds'])
        self.assertEqual(b['session_seconds'],3880)
        self.assertEqual((b['retry'],b['replacement'],b['additional']), (0,0,0))

    def test_c0_is_explicit_not_missing_work(self):
        p.validate_manifest(manifest('C0_LONG'));p.validate_manifest(manifest('LOAD_A_LONG'))
        for profile in p.PROFILES:
            bad=manifest(profile);bad['blocks']=[]
            with self.assertRaises(ValueError):p.validate_manifest(bad)
        with self.assertRaises(ValueError):p.blocks('C0')
        bad=manifest('LOAD_A_LONG');bad['work_call_cap']=0
        with self.assertRaises(ValueError):p.validate_manifest(bad)

    def test_no_implicit_version_or_watchdog_change(self):
        bad=manifest('C0_LONG');bad['resident_identification_version']=p.prior.VERSION
        with self.assertRaises(ValueError):p.validate_manifest(bad)
        for key in ('maximum_duration_ms','cooling_seconds','cadence_ms','power_sample_period_ms','start_ap_gate'):
            bad=manifest('C0_LONG');bad[key]='invalid'
            with self.assertRaises(ValueError):p.validate_manifest(bad)
        self.assertEqual(p.prior.budget()['host_poll_seconds'],1800)

    def test_wrapper_is_foreground_and_has_approval_hash_and_transport(self):
        text=p.script_text()
        for marker in ('tools.d1_ap_tail_observation_plan','powershell_pid=$PID','host_entry_', '--serial $Serial','--expected-sha $ExpectedPlanSha256'):
            self.assertIn(marker,text)
        self.assertNotIn('Start-Process',text)

    def test_prepare_writes_exact_script_bytes_without_windows_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/p.FOLDER
            plan=dict(entries=[],registry=str(root/'registry'),output_root=str(root/'run'))
            with patch.object(p,'expected',return_value=(plan,[])),patch.object(p,'check',return_value={'device_commands':0}):
                p.prepare('PC_FIXTURE','PC_FIXTURE',out)
            self.assertEqual((out/'RUN_AFTER_APPROVAL.ps1').read_bytes(),p.script_text().encode('utf8'))

    def test_c0_failure_progress_does_not_invent_load(self):
        result=p.progress_consumption(b'',True,load_cap=0,eligibility_cap=4)
        self.assertEqual(result['counts']['load']['actual_started_upper'],0)
        self.assertEqual(result['counts']['warmup']['actual_started_upper'],8)
        with self.assertRaises(ValueError):p.progress_consumption(b'{"kind":"request_start","phase":"load","id":"forbidden"}\n',True,0,4)

    def test_long_candidate_continuity_and_no_post_observation_leak(self):
        c=copy.deepcopy(p.tail.s.j.m.read(p.tail.s.INPUTS)[0]);original=p.old.p.read(p.j.m.MODEL)
        c['q']=list(map(float,range(35,2556,2)));c['actual'][-1]['end_s']=2555.
        models=p.old.p.read(p.CANDIDATES)
        for mode,m in models.items():
            before=copy.deepcopy(m);x=p.tail.predict(c,original,m)[0]
            changed=copy.deepcopy(c);changed['ap']=[999.]*len(c['q']);changed['power_w']=[999.]*len(c['power_w'])
            self.assertEqual(x,p.tail.predict(changed,original,m)[0]);self.assertEqual(before,m)
        idle=dict(c,actual=[dict(start_s=0.,end_s=2555.,state='idle')],last_lane_s=None)
        _,parts=p.tail.predict(idle,original,models['LOAD_SLOW'])
        self.assertEqual(parts['slow_path_c'],[0.]*len(c['q']))

    def test_real_host_entry_no_fit_single_cleanup_and_reexecution_block(self):
        self._host_run()

    def test_real_host_failure_keeps_error_and_does_not_start_load(self):
        self._host_run(fail=True)

    def test_preflight_does_not_cleanup_an_unowned_active_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fake=FakeDevice()
            plan=dict(tail_observation=True,apk_sha256='fixture')
            with patch.object(host.apk,'preflight',return_value={}),patch.object(host,'gates',side_effect=ValueError('active app ownership unknown')), \
                 patch.object(host.shared,'cleanup') as cleanup:
                with self.assertRaisesRegex(ValueError,'active app ownership unknown'):host.installation(fake,plan,'PC_ONLY',root,1e30)
            cleanup.assert_not_called()

    def test_check_rejects_consumed_plan_before_apk_or_device_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/p.FOLDER;root.mkdir();registry=root/'registry';registry.mkdir();file=root/'plan.json'
            file.write_text(json.dumps(dict(experiment_id=p.NAME,tail_observation=True,approval='not_approved',
                registry=str(registry),output_root=str(root/'run'))),encoding='utf8')
            with patch.object(host,'ObservedDevice',side_effect=AssertionError('Check must not create a device')):
                with self.assertRaisesRegex(ValueError,'consumed/occupied'):p.check(file)

    def test_actual_c0_artifact_reader_and_missing_block_or_load_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'artifacts';folder.mkdir();mf=root/'input_manifest.json'
            m=manifest('C0_LONG');m.update(session_id='fixture',phase='confirmation_C0',identification_role='confirmation')
            def write(path,value):path.write_text(json.dumps(value),encoding='utf8')
            write(mf,m);write(folder/'manifest.json',m);write(folder/'cleanup.json',dict(status='completed'))
            begin=120*10**9;end=720*10**9;cool=2640*10**9;events=[]
            def event(kind,t,phase='load',**fields):events.append(dict(kind=kind,mono_ns=t,phase=phase,session_id='fixture',**fields))
            for i in range(4):event('runtime_return',i+1,phase='setup')
            for i in range(8):event('warmup_return',i+10,phase='warmup')
            for i in range(4):
                event('lane_available',20+i,phase='eligibility_serial_probe',id=f'probe{i}',key=p.old.KEYS[i],
                    dispatch_ns=1,execution_start_ns=2,output_ready_ns=3,persist_complete_ns=4,worker_release_ns=5,lane_available_ns=6)
                write(folder/f'probe{i}.result.json',{})
            event('identification_common_start',begin,start_ns=begin,window_ns=600*10**9)
            event('block_start',begin,block='registered_no_work',keys=[],target_seconds=600,nominal_offset_ns=0)
            event('block_end',end,block='registered_no_work')
            event('identification_common_end',end,start_ns=begin,planned_end_ns=end,end_ns=end)
            event('phase_end',cool,phase='resident_cooling')
            for t in range(0,2640000,900):
                ns=t*10**6;event('power_sample',ns+300,sample_period_ms=900,plugged=0,thermal_status=0,interactive=True,
                    admission_reason='admit',snapshot_start_ns=ns,sensor_read_end_ns=ns+100,state_snapshot_ns=ns+200,
                    resident_keys=list(p.old.KEYS),current_raw=-250,voltage_mV=4000,current_valid=True)
            events.sort(key=lambda r:r['mono_ns'])
            def journal(rows):
                for i,r in enumerate(rows):r['sequence']=i
                (folder/'progress.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
            journal(events)
            write(folder/'start_ap.accepted.json',dict(ap_c=28.2,read_before_ns=begin-10**9,read_after_ns=begin-5*10**8))
            dummy=root/'reference.json';write(dummy,{})
            thermal=[dict(mono_ns=t*10**9,before_ns=t*10**9-10**8,after_ns=t*10**9+10**8,AP='28.2',
                thermal_status='0',sampling_uncertainty_ns=10**8) for t in range(0,2641,2)]
            (root/'thermal.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in thermal),encoding='utf8')
            plan=dict(tail_observation=True,references={k:dict(path=str(dummy)) for k in p.old.KEYS},
                original_model=dict(path=str(p.j.m.MODEL)),frozen_candidates=dict(sha256=p.old.p.digest(p.CANDIDATES)))
            with patch.object(p.analysis.old,'quality',return_value=None),patch.object(p,'verify_frozen',return_value=p.old.p.read(p.CANDIDATES)):
                stats=p.summarize_session(folder,mf,plan)
                self.assertEqual(stats['work_calls'],0);self.assertIsNone(stats['analysis_case']['last_lane_s'])
                self.assertEqual(set(stats['comparator_errors']),{'FROZEN','LOAD_SLOW','CLOCK_SHIFT'})
                self.assertTrue((root/'diagnostic_ap_curves.csv').is_file());self.assertEqual(stats['fit_calls'],0)
                self.assertIsNone(stats['energy_windows']['recovery1920']['observed_j'])
                self.assertIsNone(stats['energy_windows']['recovery1920']['signed_error_j'])
                self.assertIsNotNone(stats['energy_windows']['registered600']['observed_j'])
                low=copy.deepcopy(m);low.update(protocol=p.LOW_BATTERY_PROTOCOL,tail_battery_gate_version=p.LOW_BATTERY_GATE,battery_min_percent=6,battery_stop_at_percent=5)
                plan['tail_low_battery']=True;write(mf,low);write(folder/'manifest.json',low)
                for e in events:
                    if e['kind']=='power_sample':e.update(battery_level=19,battery_scale=100,battery_min_percent=6,power_save_mode=False)
                journal(events)
                self.assertEqual(p.summarize_session(folder,mf,plan)['work_calls'],0)
                sample=next(e for e in reversed(events) if e['kind']=='power_sample');sample['battery_level']=5;journal(events)
                with self.assertRaisesRegex(ValueError,'low battery protocol sample invalid'):p.summarize_session(folder,mf,plan)
                sample['battery_level']=19;plan.pop('tail_low_battery');write(mf,m);write(folder/'manifest.json',m)
                journal([e for e in events if e['kind']!='block_end'])
                with self.assertRaisesRegex(ValueError,'missing registered block'):p.summarize_session(folder,mf,plan)
                journal(events+[dict(kind='request_start',phase='load',mono_ns=begin+1,id='forbidden',session_id='fixture')])
                with self.assertRaisesRegex(ValueError,'unconfirmed request'):p.summarize_session(folder,mf,plan)

    def _host_run(self,fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=HostFailureTest().fixture(root);plan=json.loads(path.read_text())
            plan.update(tail_observation=True,resident_identification=True,autonomous_diagnostic_only=True,diagnostic_only=True,
                budget=dict(p.budget(),intersession_cooling_seconds=0),entries=[dict(index=i,phase='confirmation',pair='CG_DC',
                    mode='calibration',family='regimen',session_id=f'fixture{i}',manifest='manifest.json',
                    work_requests=0 if i==0 else 1200,eligibility_requests=4) for i in range(2)])
            path.write_text(json.dumps(plan),encoding='utf8')
            (root/'manifest.json').write_text(json.dumps(dict(protocol=p.PROTOCOL,session_control='device-after-probe-diagnostic-v1')),encoding='utf8')
            with ExitStack() as stack:
                for obj,name,value in [(p,'check',None),(p,'verify_frozen',{}),(host,'ObservedDevice',FakeDevice),
                    (host,'installation',{'status':'verified'}),(host,'gates',None),(host.install,'installed_hash','fixture'),
                    (host.shared,'stage_inputs','remote'),(host,'poll',None),(host,'recover',{'status':'recovered'}),
                    (host,'pull_file',None)]:
                    stack.enter_context(patch.object(obj,name,**({'side_effect':value} if name=='ObservedDevice' else {'return_value':value})))
                cleanup=stack.enter_context(patch.object(host.shared,'cleanup',return_value={'status':'completed'}))
                summary=stack.enter_context(patch.object(p,'summarize_session',side_effect=ValueError('original app failure') if fail else
                    [dict(work_calls=0,eligibility_calls=4,warmup_calls=8),dict(work_calls=853,eligibility_calls=4,warmup_calls=8)]))
                if fail:
                    with self.assertRaisesRegex(ValueError,'original app failure'):host.run(path,'NO_ADB','FAKE_ONLY',p.old.p.digest(path),True)
                    receipt=json.loads((root/'run/FINAL_RECEIPT.json').read_text(encoding='utf8'))
                    self.assertIn('original app failure',receipt['exception_stack']);self.assertEqual(cleanup.call_count,1)
                    self.assertEqual(summary.call_count,1);self.assertFalse((root/'run/01_fixture1').exists())
                    self.assertEqual(receipt['last_session_progress']['counts']['load']['actual_started_upper'],0)
                else:
                    result=host.run(path,'NO_ADB','FAKE_ONLY',p.old.p.digest(path),True)
                    self.assertEqual(result['explicit_inference'],877);self.assertEqual(cleanup.call_count,2)
                with self.assertRaises(FileExistsError):host.run(path,'NO_ADB','FAKE_ONLY',p.old.p.digest(path),True)


if __name__=='__main__':unittest.main()
