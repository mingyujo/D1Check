"""Isolated PC fixtures, never ADB. Short tests are not device stability proof."""
import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_ap_transfer_confirmation as t
from tools import d1_arrival_energy_collection_device as runner


class TransferTest(unittest.TestCase):
    def test_saved_burst_preserves_android_arrival_grid_and_delays_release_only(self):
        s=t.schedule();self.assertEqual(s,t.p.read(t.BUNDLE/'schedule.json'))
        old=t.replay.source_check()
        self.assertNotEqual([r['source_request_id'] for r in s['requests']],
                            [r['source_request_id'] for r in old['requests']])
        self.assertEqual(len(s['requests']),24)
        self.assertAlmostEqual(sum(s['pc_occupancy_seconds'].values()),120.)
        self.assertGreater(s['pc_occupancy_seconds']['classification:GPU+detection:CPU'],0.)
        self.assertEqual(min(q['offset_ms'] for q in s['requests']),0)
        self.assertEqual(max(q['offset_ms'] for q in s['requests']),4840)
        self.assertEqual([q['offset_ms'] for q in s['requests']],
                         [i*80+(i//6)*1000 for i in range(24)])
        self.assertTrue(all(q['release_offset_ns']>=q['offset_ms']*1_000_000 for q in s['requests']))

    def test_preload_query_bracket_and_information_cutoff(self):
        frozen=dict(ap_cooling_rate_per_s=.1,
                    ap_slope_at_30_c_per_s={'resident_idle':0,'detection_CPU':.2})
        pre=[dict(t=i,lo=i-.05,hi=i+.05,ap=28.+math.exp(-.1*(i+29)))
             for i in range(-29,35,2)]
        seg=[dict(start_s=0.,end_s=35.,state='idle'),
             dict(start_s=35.,end_s=40.,state='detection:CPU'),
             dict(start_s=40.,end_s=180.,state='idle')]
        fit,path=t.condition(pre,seg,frozen,28.5,[35.,40.,120.,180.])
        self.assertAlmostEqual(fit['effective_idle_reference_c'],28.)
        self.assertEqual(len(path),4)
        with self.assertRaisesRegex(ValueError,'bracket'):
            t.condition(pre+[dict(t=34.9,lo=34.8,hi=35.1,ap=28)],seg,frozen,28.5,[40.])
        with self.assertRaisesRegex(ValueError,'precedes'):
            t.condition(pre,seg,frozen,28.5,[34.99])
        with self.assertRaisesRegex(ValueError,'short|insufficient'):
            t.condition(pre[-10:],seg,frozen,28.5,[40.])
        with self.assertRaisesRegex(ValueError,'unsupported'):
            t.condition(pre,[seg[0],dict(seg[1],state='classification:CPU+classification:GPU'),seg[2]],
                        frozen,28.5,[40.])

    def test_consumed_plan_blocks_before_any_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan_dir=root/t.FOLDER;plan_dir.mkdir()
            registry=root/'ap_transfer_registry'/t.EXPERIMENT;registry.mkdir(parents=True)
            file=plan_dir/'collection_plan.json'
            file.write_text(json.dumps(dict(experiment_id=t.EXPERIMENT,
                status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',approval='not_approved',
                ap_transfer_confirmation=True,recorded_replay_confirmation=True,
                experiment_ready=False,budget=t.BUDGET,entries=[{}],
                registry=str(registry),output_root=str(root/t.RUN_FOLDER))),encoding='utf-8')
            with patch.object(runner,'ObservedDevice',side_effect=AssertionError('real device')):
                with self.assertRaisesRegex(ValueError,'consumed'):
                    runner.run(file,'forbidden-adb','fixture',t.p.digest(file),True)

    def test_actual_runner_entry_has_no_development_or_diagnostic_early_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);file=folder/'plan.json';mf=folder/'manifest.json'
            mf.write_text(json.dumps(dict(session_id='fixture',phase='heldout_protocol_transfer')))
            file.write_text(json.dumps(dict(ap_transfer_confirmation=True,
                recorded_replay_confirmation=True,budget=t.BUDGET,
                output_root=str(folder/'run'),registry=str(folder/'registry'),
                apk_preflight={'candidate':{}},apk_sha256='fixture',source_files={},
                entries=[dict(index=0,session_id='fixture',manifest='manifest.json')])))
            device=type('Fake',(),{'sequence':0,'deadline':None,'call':lambda *a,**kw:None})()
            with (patch.object(t,'check') as check,patch.object(t.replay,'check',side_effect=AssertionError('old plan checker')),
                patch.object(runner,'ObservedDevice',return_value=device),
                patch.object(runner.energy_device,'installation',return_value={'status':'verified'}),
                patch.object(runner.energy_device,'gates'),
                patch.object(runner.install,'installed_hash',return_value='fixture'),
                patch.object(runner.shared,'stage_inputs',return_value='fixture'),
                patch.object(runner,'poll') as poll,
                patch.object(runner.energy_device,'recover',return_value={'status':'recovered'}) as recover,
                patch.object(runner.shared,'cleanup',return_value={'status':'completed'}) as cleanup,
                patch.object(runner,'validate',return_value={'status':'eligible_descriptive_only','requests':24})):
                result=runner.run(file,'forbidden-adb','fixture',t.p.digest(file),True)
            check.assert_called_once();poll.assert_called_once();recover.assert_called_once();cleanup.assert_called_once()
            self.assertEqual(result['sessions'],1)
            self.assertEqual(result['requests'],24)
            self.assertEqual(device.command_limit,3200)
            self.assertFalse((folder/'run/ap_model_freeze.json').exists())
            self.assertFalse((folder/'run/development_freeze.json').exists())

    def _fixture(self, root):
        def save(path,data):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(data),encoding='utf-8')
        origin=100_000_000_000
        model=dict(ap_cooling_rate_per_s=.1,ap_reference_c=30.,
            initial_ap_development_range_c=[32.5,34.],ap_development_observed_range_c=[32.5,40.],
            ap_slope_at_30_c_per_s={'resident_idle':.1,'classification_GPU':.2,'detection_CPU':.3},
            whole_device_power_w={'resident_idle':1.,'classification_GPU':2.,'detection_CPU':3.})
        frozen=root/'frozen.json';freeze=root/'candidate.json';save(frozen,model);save(freeze,{})
        m=dict(phase='heldout_protocol_transfer');manifest=root/'manifest.json';save(manifest,m)
        folder=root/'run/00_fixture';artifact=folder/'artifacts'
        save(root/'run/FINAL_RECEIPT.json',dict(status='completed_descriptive_only'))
        save(folder/'validated.json',dict(status='eligible_descriptive_only'))
        save(artifact/'manifest.json',m)
        save(artifact/'common_boundary.json',dict(start_ns=origin,planned_end_ns=origin+120_000_000_000))
        save(artifact/'start_ap.accepted.json',dict(common_start_ns=origin,gate_mode='numeric-ap-observe-v2',ap_c=29.))
        rows=[]
        for i in range(24):
            start=origin+35_100_000_000+i*200_000_000
            row=dict(scheduled_arrival_ns=origin+35_000_000_000,task_id='classification' if i%2 else 'detection',
                     priority='normal',selected_backend='GPU' if i%2 else 'CPU',terminal_status='succeeded')
            for k,offset in [('dispatch_ns',0),('execution_start_ns',1000),('output_ready_ns',100000000),
                ('persist_complete_ns',110000000),('worker_release_ns',120000000),('lane_available_ns',190000000)]:
                row[k]=start+offset
            rows.append(row)
        save(artifact/'requests.json',rows)
        events=[dict(kind='phase_start',phase='resident_baseline',mono_ns=origin-30_000_000_000),
                dict(kind='phase_end',phase='resident_cooling',mono_ns=origin+180_000_000_000)]
        for i in range(121):
            events.append(dict(kind='power_sample',snapshot_start_ns=origin+i*1_000_000_000,
                sensor_read_end_ns=origin+i*1_000_000_000,current_raw=-250,current_valid=True,
                voltage_mV=4000,plugged=0))
        (artifact/'progress.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in events),encoding='utf-8')
        thermal=[]
        for i in range(-29,180,2):
            n=origin+i*1_000_000_000
            thermal.append(dict(mono_ns=n,before_ns=n-50_000_000,after_ns=n+50_000_000,
                                AP=str(28.+math.exp(-.1*(i+29))),thermal_status='0'))
        (folder/'thermal.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in thermal),encoding='utf-8')
        plan=root/'plan.json'
        save(plan,dict(experiment_id=t.EXPERIMENT,source_code={'fixture':'isolated'},output_root=str(root/'run'),
            frozen_model={'path':str(frozen)},candidate_freeze={'path':str(freeze)},
            entries=[dict(session_id='fixture',manifest='manifest.json',manifest_sha256=t.p.digest(manifest))]))
        return plan,folder,frozen,freeze

    def test_readout_full120s_conservation_and_future_ap_no_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,folder,frozen,freeze=self._fixture(root)
            with (patch.object(t,'identity',return_value={'fixture':'isolated'}),
                 patch.object(t.replay,'FROZEN_SHA',t.p.digest(frozen)),
                 patch.object(t,'FREEZE_SHA',t.p.digest(freeze))):
                result=t.readout(plan,root/'analysis1')
                path=folder/'thermal.jsonl'
                records=[json.loads(x) for x in path.read_text().splitlines()]
                for r in records:
                    if r['before_ns']>=135_100_000_000:r['AP']='40'
                path.write_text(''.join(json.dumps(r)+'\n' for r in records))
                changed=t.readout(plan,root/'analysis2')
            self.assertEqual(result['preload'],changed['preload'])
            self.assertNotEqual(result['ap_scores']['candidate']['mae_c'],changed['ap_scores']['candidate']['mae_c'])
            self.assertAlmostEqual(result['observed_energy_120s_j'],120.)
            with (root/'analysis1/phase_energy_residuals.csv').open() as f:
                residual=list(csv.DictReader(f))
            self.assertAlmostEqual(sum(float(x['observed_j']) for x in residual),120.)
            self.assertAlmostEqual(sum(float(x['predicted_j']) for x in residual),result['predicted_energy_120s_j'])
            with (root/'analysis1/ap_paths.csv').open() as f,(root/'analysis2/ap_paths.csv').open() as g:
                self.assertEqual([r['candidate_ap_c'] for r in csv.DictReader(f)],
                                 [r['candidate_ap_c'] for r in csv.DictReader(g)])
            self.assertFalse(result['strict_support']);self.assertIsNone(result['policy_rank'])
            self.assertEqual(result['actual_parallel_seconds'],0.)

    def test_partial_current_is_not_zero_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,folder,frozen,freeze=self._fixture(root)
            path=folder/'artifacts/progress.jsonl'
            records=[json.loads(x) for x in path.read_text().splitlines()]
            for r in records:
                if r.get('kind')=='power_sample' and r['snapshot_start_ns']==160_000_000_000:
                    r['current_valid']=False
            path.write_text(''.join(json.dumps(r)+'\n' for r in records))
            with (patch.object(t,'identity',return_value={'fixture':'isolated'}),
                 patch.object(t.replay,'FROZEN_SHA',t.p.digest(frozen)),
                 patch.object(t,'FREEZE_SHA',t.p.digest(freeze))):
                with self.assertRaisesRegex(ValueError,'incomplete power'):
                    t.readout(plan,root/'analysis')
            self.assertFalse((root/'analysis').exists())


if __name__=='__main__':unittest.main()
