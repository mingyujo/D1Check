"""PC fixture checks only; never invokes ADB or treats PC times as device measurements."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_recorded_replay_analysis as analysis
from tools import d1_arrival_energy_collection_device as runner


class RecordedReplayTest(unittest.TestCase):
    def test_inrange_followup_has_new_identity_but_same_recorded_work(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            template=dict(models={key:dict(identity={},target={}) for key in
                                  ('classification','detection')},images={})
            (folder/'template.json').write_text(json.dumps(template),encoding='utf-8')
            (folder/'source.json').write_text(json.dumps({'entries':[{'manifest':'template.json'}]}),
                                              encoding='utf-8')
            source=dict(source_plan={'path':str(folder/'source.json')},device_fingerprint='fixture')
            old=replay.expected_manifest(source,'apk')
            new=replay.expected_manifest(dict(source,experiment_id=replay.CONFIRM_EXPERIMENT),'apk')
            self.assertNotEqual(old['session_id'],new['session_id'])
            self.assertEqual(old['start_ap_gate'],'numeric-ap-observe-v2')
            self.assertEqual(new['start_ap_gate'],'numeric-ap-once-v1')
            for field in ('requests','common_window_seconds','resident_baseline_seconds',
                          'cooling_seconds','maximum_duration_ms','cpu_threads','thermal_gate'):
                self.assertEqual(old[field],new[field])
            self.assertEqual(new['models']['classification']['identity']['session_id'],new['session_id'])
            with self.assertRaisesRegex(ValueError,'unknown replay'):
                replay.configuration('unregistered-auto-retry')

    def test_exact_saved_schedule_and_support_states(self):
        source=replay.source_check()
        self.assertEqual(len(source['requests']),24)
        self.assertAlmostEqual(sum(source['occupancy_seconds'].values()),120)
        self.assertGreater(source['occupancy_seconds']['classification:GPU+detection:CPU'],2)
        self.assertTrue(all(q['release_offset_ns']>=q['offset_ms']*1_000_000
                            for q in source['requests']))

    def test_continuity_common_window_and_no_idle_double_count(self):
        frozen={'initial_ap_development_range_c':[32.5,34.0],
                'ap_cooling_rate_per_s':.1,'ap_reference_c':30.,
                'whole_device_power_w':{'resident_idle':1.,'detection_CPU':3.},
                'ap_slope_at_30_c_per_s':{'resident_idle':.2,'detection_CPU':.4}}
        segments=[{'start_s':0.,'end_s':1.,'state':'idle'},
                  {'start_s':1.,'end_s':2.,'state':'detection:CPU'},
                  {'start_s':2.,'end_s':120.,'state':'idle'}]
        path=analysis.forecast(segments,frozen,33.,[1.,2.])
        self.assertAlmostEqual(path[-1]['predicted_energy_j'],122.)
        self.assertAlmostEqual(path[1]['predicted_ap_c'],
            32.+(33.-32.)*__import__('math').exp(-.1))
        self.assertAlmostEqual(path[2]['predicted_ap_c'],
            34.+(path[1]['predicted_ap_c']-34.)*__import__('math').exp(-.1))
        with self.assertRaisesRegex(ValueError,'noncontiguous'):
            analysis.forecast([dict(segments[0],end_s=.9),*segments[1:]],frozen,33.,[])
        with self.assertRaisesRegex(ValueError,'initial AP'):
            analysis.forecast(segments,frozen,32.3,[])
        extrapolated=analysis.forecast(segments,frozen,28.8,[],diagnostic_extrapolation=True)
        self.assertAlmostEqual(extrapolated[-1]['predicted_energy_j'],122.)
        with self.assertRaisesRegex(ValueError,'unsupported frozen state'):
            analysis.forecast([dict(segments[0],state='classification:CPU+classification:GPU'),
                               *segments[1:]],frozen,33.,[])

    def test_run_denies_unapproved_before_claim_or_device(self):
        with patch.object(runner,'ObservedDevice',side_effect=AssertionError('device opened')):
            with self.assertRaisesRegex(ValueError,'approval'):
                runner.run('not-a-plan','fake','serial','0'*64,False)

    def test_partial_unrecovered_session_is_not_filled_with_zero(self):
        from tools import d1_arrival_plan as p
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            model=folder/'model.json';model.write_text('{"version":"energy-ap-state-regimen-fit-v1"}',encoding='utf-8')
            output=folder/'analysis'
            with patch.object(analysis.replay,'FROZEN_SHA',p.digest(model)):
                result=analysis.analyze_or_mark(folder/'missing-session',model,output)
            self.assertEqual(result['status'],'not_evaluable')
            self.assertIsNone(result['predicted_energy_120s_j'])
            self.assertIsNone(p.read(output/'summary.json')['observed_energy_120s_j'])

    def test_replay_single_entry_failure_preserves_stopped_receipt(self):
        from tools import d1_arrival_plan as p
        import json
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);file=folder/'plan.json'
            file.write_text(json.dumps({'recorded_replay_confirmation':True,'budget':replay.BUDGET,
                'output_root':str(folder/'run'),'registry':str(folder/'registry')}),encoding='utf-8')
            fake=type('FakeDevice',(),{'sequence':0,'deadline':None})()
            with patch.object(replay,'check'),patch.object(runner,'ObservedDevice',return_value=fake),\
                 patch.object(runner.energy_device,'installation',side_effect=RuntimeError('preflight failure')):
                with self.assertRaisesRegex(RuntimeError,'preflight failure'):
                    runner.run(file,'fake','serial',p.digest(file),True)
            self.assertEqual(fake.command_limit,replay.ADB_CAP)
            self.assertEqual(p.read(folder/'run'/'FINAL_RECEIPT.json')['status'],'stopped_no_resume')

    def test_validation_failure_does_not_repeat_completed_host_cleanup(self):
        from tools import d1_arrival_plan as p
        import json
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);file=folder/'plan.json';manifest=folder/'manifest.json'
            manifest.write_text(json.dumps({'session_id':'a'*36}),encoding='utf-8')
            file.write_text(json.dumps({'recorded_replay_confirmation':True,'budget':replay.BUDGET,
                'output_root':str(folder/'run'),'registry':str(folder/'registry'),
                'apk_preflight':{'candidate':{}},'apk_sha256':'x',
                'source_files':{},'entries':[{'index':0,'session_id':'a'*36,'manifest':'manifest.json'}]}),encoding='utf-8')
            fake=type('FakeDevice',(),{'sequence':0,'deadline':None,
                'call':lambda self,*args,**kwargs:None})()
            with patch.object(replay,'check'),patch.object(runner,'ObservedDevice',return_value=fake),\
                 patch.object(runner.energy_device,'installation',return_value={'status':'verified'}),\
                 patch.object(runner.energy_device,'gates'),\
                 patch.object(runner.install,'installed_hash',return_value='x'),\
                 patch.object(runner.shared,'stage_inputs',return_value='remote') ,\
                 patch.object(runner,'poll'),\
                 patch.object(runner.energy_device,'recover',return_value={'status':'recovered'}),\
                 patch.object(runner.shared,'cleanup',return_value={'status':'completed'}) as cleanup,\
                 patch.object(runner,'validate',side_effect=ValueError('original validation failure')),\
                 patch.object(runner.energy_device,'pull_file',side_effect=RuntimeError('partial pull')):
                with self.assertRaisesRegex(ValueError,'original validation failure'):
                    runner.run(file,'fake','serial',p.digest(file),True)
            cleanup.assert_called_once()
            receipt=p.read(folder/'run'/'FINAL_RECEIPT.json')
            self.assertIn('original validation failure',receipt['error'])
            self.assertEqual(receipt['host_cleanup']['status'],'completed')

    def test_app_failure_is_reported_before_absent_success_summary(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);artifacts=folder/'artifacts';artifacts.mkdir()
            manifest={'session_id':'recorded-test'}
            (folder/'input_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            (artifacts/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            (artifacts/'cleanup.json').write_text(json.dumps({'status':'failed'}),encoding='utf-8')
            (artifacts/'session_failure.json').write_text(json.dumps({
                'message':'stopped: lifecycle_cancelled/null'}),encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'lifecycle_cancelled'):
                runner.validate(folder,manifest,{})

    def test_actual_recovery_parser_accepts_recorded_gate_and_rejects_early_dispatch(self):
        from tools import d1_arrival_plan as p
        import json
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);artifact=folder/'artifacts';artifact.mkdir()
            origin=100_000_000_000;end=origin+120_000_000_000
            source=replay.source_check()['requests'];manifest={'policy':replay.POLICY,'phase':'diagnostic',
                'scenario':'queue','requests':source}
            (artifact/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            (folder/'input_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            rows=[]
            for q in source:
                dispatch=origin+q['release_offset_ns']+q['ordinal']*10_000_000
                r=dict(request_id=q['request_id'],source_request_id=q['source_request_id'],
                       task_id=q['task_id'],priority=q['priority'],selected_backend=q['recorded_backend'],
                       scheduled_arrival_ns=origin+q['offset_ms']*1_000_000,
                       actual_arrival_ns=origin+q['offset_ms']*1_000_000,
                       recorded_release_ns=origin+q['release_offset_ns'],
                       dispatch_ns=dispatch,execution_start_ns=dispatch+1000,
                       host_inference_start_ns=dispatch+2000,host_inference_return_ns=dispatch+3000,
                       output_ready_ns=dispatch+4000,persist_complete_ns=dispatch+5000,
                       worker_release_ns=dispatch+6000,lane_available_ns=dispatch+7000,
                       terminal_status='succeeded')
                rows.append(r)
                (artifact/(q['request_id']+'.result.json')).write_text('{}',encoding='utf-8')
            for name,value in [('requests.json',rows),('common_boundary.json',{'start_ns':origin,
                'planned_end_ns':end,'end_ns':end,'rows':rows}),
                ('summary.json',{'status':'completed','planned':24}),
                ('cleanup.json',{'status':'completed'}),
                ('start_ap.accepted.json',{'common_start_ns':origin,'ap_c':33,
                    'read_before_ns':origin-1_000_000,'read_after_ns':origin-500_000})]:
                (artifact/name).write_text(json.dumps(value),encoding='utf-8')
            events=[{'kind':kind} for kind,count in [('warmup_return',8),('runtime_return',4),
                                                      ('lane_available',24)] for _ in range(count)]
            (artifact/'progress.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in events),encoding='utf-8')
            (folder/'thermal.jsonl').write_text(''.join(json.dumps({'mono_ns':origin+i*4_000_000_000,
                    'thermal_status':'0','AP':'33'})+'\n' for i in range(31)),encoding='utf-8')
            ref=folder/'ref.json';ref.write_text('{}',encoding='utf-8')
            plan={'recorded_replay_confirmation':True,
                  'references':{key:{'path':str(ref)} for key in ('detection_CPU','classification_GPU')}}
            with patch.object(runner.c.old,'quality'),\
                 patch.object(runner.energy,'integrate',return_value={'full_energy_j':1}):
                self.assertEqual(runner.validate(folder,manifest,plan)['terminal_completed'],24)
                manifest['start_ap_gate']='numeric-ap-observe-v2'
                for target in (artifact/'manifest.json',folder/'input_manifest.json'):
                    target.write_text(json.dumps(manifest),encoding='utf-8')
                accepted={'common_start_ns':origin,'ap_c':28.8,'gate_mode':'numeric-ap-observe-v2',
                          'read_before_ns':origin-1_000_000,'read_after_ns':origin-500_000}
                (artifact/'start_ap.accepted.json').write_text(json.dumps(accepted),encoding='utf-8')
                self.assertEqual(runner.validate(folder,manifest,plan)['terminal_completed'],24)
                manifest['start_ap_gate']='numeric-ap-once-v1'
                for target in (artifact/'manifest.json',folder/'input_manifest.json'):
                    target.write_text(json.dumps(manifest),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'AP approval'):
                    runner.validate(folder,manifest,plan)
                manifest['start_ap_gate']='numeric-ap-observe-v2'
                for target in (artifact/'manifest.json',folder/'input_manifest.json'):
                    target.write_text(json.dumps(manifest),encoding='utf-8')
                source[0]['release_offset_ns']+=1_000_000_000
                with self.assertRaisesRegex(ValueError,'recorded replay allocation/release'):
                    runner.validate(folder,manifest,plan)


if __name__=='__main__':unittest.main()
