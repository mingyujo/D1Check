import json
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools import d1_background_activity_plan as b
from tools import d1_background_activity_readout as readout
from tools import d1_arrival_energy_collection_device as runner


class FakeDevice:
    def __init__(self,*args,**kw):self.calls=[];self.sequence=0;self.serial='FAKE';self.deadline=None
    def call(self,*args,**kw):
        self.calls.append((args,kw));self.sequence+=1
        stdout=b'';code=0
        if args[:3]==('shell','perfetto','--help'):stdout=b'--detach --attach --is_detached --txt'
        if args[:3]==('shell','perfetto','--query'):stdout=b'linux.ftrace linux.process_stats'
        if args[:3]==('shell','test','-e'):code=1
        if args[:3]==('shell','stat','-c'):stdout=b'3'
        if args[0]=='pull':Path(args[2]).write_bytes(b'raw')
        return SimpleNamespace(returncode=code,stdout=stdout,stderr=b'')


class BackgroundTests(unittest.TestCase):
    def test_budget_includes_trace_client_reserve_and_registered_work(self):
        x=b.budget()
        self.assertEqual(x['explicit_inference'],2*96+4*8)
        self.assertEqual(x['session_seconds'],120+90+26+485+50+45+80)
        self.assertEqual(x['total_seconds'],600+4*x['session_seconds']+3*90)
        self.assertEqual(x['adb_commands'],4*(3200+9)+200)
        self.assertEqual((x['retry'],x['replacement'],x['additional']),(0,0,0))
        self.assertEqual(x['fixed_observation_seconds'],840)

    def test_trace_owner_only_and_duplicate_recovery_reuses_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=FakeDevice();sid=str(uuid.uuid4());b.trace_start(d,sid,tmp)
            result=b.trace_recover(d,10**15);count=len(d.calls)
            self.assertEqual(result['errors'],[]);self.assertEqual(result['bytes'],3)
            self.assertEqual(b.trace_recover(d,10**15),result);self.assertEqual(len(d.calls),count)
            self.assertEqual(count,9)
            self.assertFalse(any('force-stop' in c[0] or 'kill' in c[0] or 'rm' in c[0] for c in d.calls))
            self.assertTrue(any('--attach=d1-bg-'+sid in c[0] for c in d.calls))
            with self.assertRaises(ValueError):b.trace_identity('bad; killall perfetto')

    def test_stop_failure_still_recovers_once_and_preserves_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=FakeDevice();b.trace_start(d,str(uuid.uuid4()),tmp);original=d.call
            def fault(*a,**kw):
                if any(str(x).startswith('--attach=') for x in a):raise TimeoutError('first trace stop')
                return original(*a,**kw)
            d.call=fault;r=b.trace_recover(d,10**15)
            self.assertEqual(r['errors'][0]['stage'],'trace_stop');self.assertEqual(r['bytes'],3)
            n=len(d.calls);self.assertEqual(b.trace_recover(d,10**15),r);self.assertEqual(len(d.calls),n)

    def test_unsupported_trace_does_not_launch_recording(self):
        d=FakeDevice();d.call=lambda *a,**kw:SimpleNamespace(stdout=b'old perfetto',stderr=b'',returncode=0)
        with self.assertRaisesRegex(ValueError,'CLI unsupported'):b.trace_start(d,str(uuid.uuid4()),'unused')
        self.assertFalse(hasattr(d,'background_trace'))

    def test_real_runner_boundary_trace_then_launch_cleanup_then_trace_stop(self):
        from tools import d1_energy_host_lifecycle as life
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);source=root/'model.json';source.write_text('{}')
            manifest=root/'manifest.json';sid=str(uuid.uuid4());b.cal.write_new(manifest,dict(session_id=sid))
            entry=dict(index=0,session_id=sid,manifest='manifest.json',requests=0)
            plan=dict(background_activity_contrast=True,online_policy_study=True,online_configuration_owner_v1=True,
                installed_only=False,study_phase='development',budget=b.budget(),apk_sha256='apk',
                apk_preflight={'candidate':{}},frozen_model={'path':str(source)},source_files={},
                output_root=str(root/'run'),registry=str(root/'registry'),entries=[entry])
            file=root/'collection_plan.json';b.cal.write_new(file,plan);d=FakeDevice();order=[]
            def start(dev,session,folder):order.append('trace_start');b.trace_start(dev,session,folder)
            # Retain real trace functions while instrumenting the actual collection entry.
            real_start=b.trace_start
            def start(dev,session,folder):order.append('trace_start');real_start(dev,session,folder)
            def poll(*args):order.append('poll')
            def cleanup(*args):order.append('app_force_stop');return {'status':'completed'}
            for obj,name,opts in [(b,'check',{}),(b,'trace_start',{'side_effect':start}),
                (runner,'ObservedDevice',{'return_value':d}),(runner,'require_host_pull_space',{}),
                (life,'host_identity',{'return_value':{}}),(runner.energy_device,'installation',{'return_value':{}}),
                (runner.energy_device,'gates',{}),(runner.install,'installed_hash',{'return_value':'apk'}),
                (runner.shared,'stage_inputs',{'return_value':'owned'}),(runner,'poll',{'side_effect':poll}),
                (runner.energy_device,'recover',{'return_value':{}}),(runner.shared,'cleanup',{'side_effect':cleanup}),
                (runner,'validate',{'return_value':dict(requests=0,status='eligible_descriptive_only')})]:
                stack.enter_context(patch.object(obj,name,**opts))
            stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('real process forbidden')))
            result=runner.run(file,'FAKE','FAKE',b.p.digest(file),True)
            self.assertEqual(result['status'],'completed_descriptive_only')
            self.assertEqual(order,['trace_start','poll','app_force_stop'])
            self.assertTrue((root/'run'/('00_'+sid)/'trace_recovery.json').exists())
            self.assertEqual(sum('force-stop' in c[0] for c in d.calls),0) # cleanup mock owns it exactly once
            self.assertEqual(sum('--stop' in c[0] for c in d.calls),1)
            with self.assertRaises(FileExistsError):runner.run(file,'FAKE','FAKE',b.p.digest(file),True)

    def test_trace_alignment_loss_and_missing_frequency(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)
            (f/'clock.csv').write_text('ts,clock_id,clock_value\n0,6,0\n10000000000,6,10000000000\n')
            (f/'loss.csv').write_text('name,value\n')
            (f/'frequency.csv').write_text('ts,value,cpu\n')
            (f/'sched.csv').write_text('ts,dur,cpu,activity_class\n0,5000000000,0,benchmark\n5000000000,5000000000,0,other\n')
            r=readout.summarize(f,0,10000000000)
            self.assertEqual(sum(x['benchmark_cpu_seconds'] for x in r['bins']),5)
            self.assertFalse(r['cpu_frequency_supported'])
            (f/'loss.csv').write_text('name,value\nftrace_cpu_overrun,1\n')
            with self.assertRaisesRegex(ValueError,'loss/error'):readout.summarize(f,0,10000000000)
            (f/'loss.csv').write_text('name,value\n');(f/'clock.csv').write_text('ts,clock_id,clock_value\n0,6,10\n')
            with self.assertRaisesRegex(ValueError,'alignment'):readout.summarize(f,0,10000000000)

    def test_partial_scheduler_coverage_is_null_and_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)
            (f/'clock.csv').write_text('ts,clock_id,clock_value\n0,6,0\n')
            (f/'loss.csv').write_text('name,value\n')
            (f/'frequency.csv').write_text('ts,value,cpu\n')
            (f/'sched.csv').write_text('ts,dur,cpu,activity_class\n0,4000000000,0,benchmark\n5000000000,5000000000,0,other\n')
            result=readout.summarize(f,0,10000000000)
            self.assertEqual(result['bins'][0]['sched_coverage_fraction'],.8)
            self.assertIsNone(result['bins'][0]['benchmark_cpu_seconds'])
            self.assertIsNone(result['bins'][0]['other_cpu_seconds'])
            (f/'sched.csv').write_text('ts,dur,cpu,activity_class\n0,6000000000,0,benchmark\n5000000000,5000000000,0,other\n')
            with self.assertRaisesRegex(ValueError,'overlapping'):readout.summarize(f,0,10000000000)

if __name__=='__main__':unittest.main()
