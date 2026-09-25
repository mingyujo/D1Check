import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools import d1_energy_operational as op
from tools import d1_energy_collection as c
from tools import d1_energy_collection_device as d
from tools import d1_energy_trace_account as ledger


def sample(t,ap='32.4'):
    return dict(mono_ns=int(t*1e9),AP=ap,thermal_status='0',sampling_uncertainty_ns=100000000)


class OperationalTests(unittest.TestCase):
    def test_no_single_sample_or_early_release(self):
        self.assertFalse(op.assess([sample(120)],0)['ready'])
        self.assertFalse(op.assess([sample(t) for t in range(0,120,3)],0)['ready'])
        self.assertTrue(op.assess([sample(t) for t in range(0,121,3)],0)['ready'])

    def test_no_anchor_or_equilibrium_claim(self):
        rows=[sample(t,str(31+t/120)) for t in range(0,121,3)]
        r=op.assess(rows,0)
        self.assertTrue(r['ready']);self.assertFalse(r['thermal_equilibrium_claim'])

    def test_invalid_missing_nan_and_gap_stop(self):
        base=[sample(t) for t in range(0,121,3)]
        for key,value in [('AP',''),('AP','NaN'),('thermal_status','1'),('sampling_uncertainty_ns',3e9)]:
            rows=copy.deepcopy(base);rows[5][key]=value
            self.assertEqual(op.assess(rows,0)['reason'],'invalid_sensor_or_thermal')
        self.assertEqual(op.assess(base[:4]+base[10:],0)['reason'],'invalid_sensor_or_thermal')
        self.assertFalse(op.assess([sample(t) for t in range(352)],0)['ready'])

    def test_recovery_missing_cleanup_does_not_erase_other_artifacts(self):
        import io,tarfile,subprocess
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w') as tar:
            entry=tarfile.TarInfo('progress.jsonl');entry.size=3
            tar.addfile(entry,io.BytesIO(b'{}\n'))
        class Device:
            def call(self,*args,**kw):
                if 'tar' in args:return subprocess.CompletedProcess(args,0,data.getvalue(),b'')
                if args[-1].endswith('cleanup.json'):
                    return subprocess.CompletedProcess(args,0,b'cat: cleanup.json: No such file',b'')
                return subprocess.CompletedProcess(args,0,b'{}\n',b'')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            r=d.recover(Device(),'remote',root/'artifacts',True)
            self.assertEqual(r['status'],'recovered_with_prefix_errors')
            self.assertTrue((root/'artifacts/progress.jsonl').exists())
            self.assertTrue((root/'recovery_prefix/cleanup.json.invalid.bin').exists())
            self.assertFalse((root/'artifacts/cleanup.json').exists())

    def test_probe_preparation_same_and_old_unchanged(self):
        self.assertEqual(op.probe_specs(True,'serial'),op.probe_specs(True,'parallel'))
        self.assertEqual(op.probe_specs(False,'parallel'),[('eligibility_probe','parallel')])
        self.assertEqual(c.plan_profile()[1]['sessions'],8)
        self.assertEqual(c.plan_profile(conditioned=True)[1]['total_seconds'],16080)

    def test_budget_and_order_not_oracle(self):
        _,b,order,_=c.plan_profile(operational=True)
        self.assertEqual(b['work_requests']+b['eligibility_requests']+b['warmup'],3528)
        self.assertEqual([r[2] for r in order],['serial','parallel','parallel','serial'])
        r=op.reserve_summary(b)
        self.assertEqual(r['fixed_observation_seconds'],3600)
        self.assertEqual(r['nested_timeout_reservation_seconds'],8500)
        self.assertEqual(r['hard_seconds'],8640)
        with self.assertRaises(AssertionError):op.reserve_summary(dict(b,total_seconds=8641))

    def test_partial_probe_consumption_and_legacy(self):
        rows=[dict(kind='request_start',phase=label,id=label+'-'+str(n))
              for label,_ in op.probe_specs(True,'serial') for n in range(2)]
        raw=('\n'.join(json.dumps(x) for x in rows)+'\n').encode()
        r=c.progress_consumption(raw,True,True)['counts']['eligibility']
        self.assertEqual(r['confirmed_started_at_least'],4);self.assertEqual(r['confirmed_returned'],0)
        self.assertEqual(r['actual_started_upper'],4)
        self.assertEqual(c.progress_consumption(b'',True)['counts']['eligibility']['actual_started_upper'],2)

    def test_actual_runner_freezes_before_reverse_order_confirmation(self):
        class Device:
            def __init__(self,*a):self.deadline=None
            def call(self,*a,**kw):pass
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);entries=[]
            for i,(phase,pair,mode) in enumerate(op.ORDER):
                m=root/f'{i}.json';m.write_text('{}')
                entries.append(dict(index=i,phase=phase,pair=pair,mode=mode,session_id=str(i),manifest=m.name))
            plan=dict(output_root=str(root/'run'),registry=str(root/'registry'),budget=op.budget(c.CONDITIONED_BUDGET),
                operational_only=True,apk_preflight={'candidate':{}},apk_sha256='hash',source_files={},entries=entries)
            f=root/'plan.json';f.write_text(json.dumps(plan))
            n=0;frozen_bytes=[]
            def summarize(*args):
                nonlocal n
                e=entries[n]
                if n>=2:
                    data=(root/'run/development_freeze.json').read_bytes();frozen_bytes.append(data)
                    frozen=json.loads(data)
                    self.assertEqual(len(frozen['conditions']),2)
                    self.assertTrue(all(x['phase']=='development' for x in frozen['conditions'].values()))
                n+=1
                return dict(status='eligible_descriptive_only',condition=e['pair']+'_'+e['mode'],
                    phases={'resident_baseline':dict(energy={'mean_power_w':1},ap_end_c=32)})
            with (patch.object(c,'check'),patch.object(d,'ObservedDevice',Device),
                  patch.object(d,'installation',return_value={'status':'verified'}),patch.object(d,'gates'),
                  patch.object(d.install,'installed_hash',return_value='hash'),
                  patch.object(d.shared,'stage_inputs',return_value='remote'),patch.object(d,'poll') as poll,
                  patch.object(d,'recover',return_value={'status':'recovered'}),
                  patch.object(d.shared,'cleanup',return_value={'status':'completed'}),
                  patch.object(c,'summarize_session',side_effect=summarize)):
                result=d.run(f,'NOT_ADB','fixture',c.p.digest(f),True)
            self.assertEqual(result['sessions'],4);self.assertEqual(result['explicit_inference'],3528)
            self.assertEqual(frozen_bytes[0],frozen_bytes[1])
            self.assertEqual(poll.call_count,4)
            self.assertTrue(all(call.args[-1] is None for call in poll.call_args_list))

    def test_serial_technical_gate_cannot_be_bypassed(self):
        # Execute the real host state machine with a premature probe marker.
        class Device:
            deadline=10**20
            def call(self,*args,**kwargs):
                import subprocess
                return subprocess.CompletedProcess(args,0,b'probe.ready.json\n',b'')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'input_manifest.json').write_text('{}')
            marker=root/'marker.json';marker.write_text(json.dumps({'manifest_sha256':c.p.digest(root/'input_manifest.json'),'mono_ns':0}))
            with (patch.object(d,'thermal',return_value=sample(0)),patch.object(d.screen,'snapshot'),
                  patch.object(d,'pull_file',return_value=marker),patch.object(d,'arm') as arm):
                with self.assertRaisesRegex(ValueError,'probe before warmup gate'):
                    d.poll(Device(),'remote',root,{'session_id':'s'},dict(operational_only=True,
                        temperature_preparation=op.PREPARATION,budget={'host_poll_seconds':1580},screen_contract={}))
                arm.assert_not_called()


class LedgerTests(unittest.TestCase):
    def test_service_quantile_and_failed_denominator(self):
        rows=[dict(priority='urgent',terminal_status='succeeded',output_ready_ns=t*10**9,scheduled_arrival_ns=0)
              for t in (1,3)] + [dict(priority='urgent',terminal_status='failed')]
        r=ledger.service_summary(rows,{'urgent':4})['urgent']
        self.assertAlmostEqual(r['completed_p95_s'],2.9)
        self.assertEqual(r['completion_rate'],.5)
        self.assertEqual(r['not_confirmed_complete'],2)
        self.assertIsNone(r['service_pass'])

    def trace(self):
        ev=[dict(kind='session_start',mono_ns=0,session_id='s')]
        for t in range(11):
            ev.append(dict(kind='power_sample',session_id='s',mono_ns=t*10**9,
                current_raw=-1000,voltage_mV=4000,current_valid=True,plugged=0))
        for a,b,phase in [(1,3,'temperature_preparation'),(4,8,'load'),(8,10,'post_work_wait')]:
            ev.extend([dict(kind=k,mono_ns=t*10**9,session_id='s',phase=phase)
                       for k,t in [('phase_start',a),('phase_end',b)]])
        return sorted(ev,key=lambda x:x['mono_ns'])

    def test_energy_includes_gaps_not_double_counted(self):
        ev=self.trace();r=ledger.replay(ev,[],planned_work=1)
        self.assertEqual(r['windows']['observed_session_prefix']['full_energy_j'],40)
        self.assertEqual(sum(p['energy']['covered_energy_j'] or 0 for p in r['partition']),40)
        self.assertFalse(r['equal_work_completion_observed'])
        self.assertIsNone(r['full_operation_energy_j'])

    def test_completion_vs_fixed_window_and_total(self):
        rr=[dict(id='r',terminal_status='succeeded',persist_complete_ns=7*10**9)]
        r=ledger.replay(self.trace(),rr,planned_work=1)
        self.assertEqual(r['windows']['work_to_persist_complete']['full_energy_j'],12)
        self.assertEqual(r['windows']['session_to_work_complete']['full_energy_j'],28)
        self.assertEqual(r['windows']['common_work_window']['full_energy_j'],24)

    def test_failed_and_missing_endpoint_never_savings_success(self):
        ev=[r for r in self.trace() if not(r['kind']=='power_sample' and r['mono_ns']==0)]
        r=ledger.replay(ev,[dict(id='r',terminal_status='failed')],planned_work=1)
        self.assertIsNone(r['windows']['observed_session_prefix']['full_energy_j'])
        self.assertEqual(r['work_not_confirmed_complete'],1)

    def test_mixed_session_and_overlapping_phase_rejected(self):
        ev=self.trace();ev[0]['session_id']='other'
        with self.assertRaises(ValueError):ledger.replay(ev,[])
        ev=self.trace();ev.append(dict(kind='phase_start',phase='bad',session_id='s',mono_ns=2*10**9));ev.sort(key=lambda x:x['mono_ns'])
        with self.assertRaises(ValueError):ledger.replay(ev,[])


if __name__=='__main__':unittest.main()
