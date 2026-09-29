"""Focused PC checks of the AP candidate and unconsumed two-session plan."""
from __future__ import annotations

import math
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_ap_idle_response as ap
from tools import d1_ap_idle_response_plan as plan
from tools import d1_arrival_energy_collection_device as device
from tools import d1_arrival_start_ap
from tools import d1_arrival_plan as fileplan
from tools import d1_arrival_recorded_replay as saved_replay


class ApIdleResponseTests(unittest.TestCase):
    def test_preload_reference_uses_only_earlier_ap(self):
        beta=.0459325; first=31.; reference=29.8
        samples=[(float(t),reference+(first-reference)*math.exp(-beta*t))
                 for t in (0,3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63)]
        result=ap.preload_reference(samples,beta)
        self.assertAlmostEqual(result['effective_idle_reference_c'],reference,places=9)
        self.assertAlmostEqual(result['prefit_mae_c'],0.,places=9)
        self.assertEqual(result['samples'],17)

    def test_unidentified_and_missing_are_not_zero(self):
        points=[(float(t),30.) for t in range(0,64,3)]
        with self.assertRaises(ValueError):ap.preload_reference(points[:10],.0459)
        with self.assertRaises(ValueError):ap.preload_reference(points[:5]+[(18.,float('nan'))]+points[6:],.0459)
        with self.assertRaises(ValueError):ap.preload_reference(points[:5]+points[8:],.0459,
                                                                maximum_gap_seconds=8.)

    def test_continuity_and_support(self):
        frozen=dict(ap_cooling_rate_per_s=.05,
            ap_slope_at_30_c_per_s={'resident_idle':.2,
                'classification_GPU':.35,'detection_CPU':.3,
                'classification_GPU+detection_CPU':.48})
        segments=[dict(start_s=0.,end_s=60.,state='idle'),
            dict(start_s=60.,end_s=64.,state='classification:GPU+detection:CPU'),
            dict(start_s=64.,end_s=120.,state='idle')]
        curve=ap.predict(segments,frozen,30.,29.8,[0.,59.999,60.,60.001,64.,64.001,120.])
        self.assertEqual(curve[0.],30.)
        self.assertLess(abs(curve[60.001]-curve[60.]),.01)
        self.assertLess(abs(curve[64.001]-curve[64.]),.01)
        self.assertLess(curve[120.],curve[64.])
        with self.assertRaises(ValueError):
            ap.predict([dict(start_s=0.,end_s=1.,state='classification:CPU')],frozen,30.,29.8,[.5])

    def test_schedule_roles_and_budget_are_fixed(self):
        plan.budget_check(plan.BUDGET)
        dev_id,dev=plan.transformed_requests('development')
        confirm_id,confirm=plan.transformed_requests('confirmation')
        self.assertNotEqual(dev_id,confirm_id)
        self.assertEqual(len(dev),len(confirm))
        self.assertEqual(len(dev),24)
        self.assertEqual([x['offset_ms'] for x in dev],[x['offset_ms'] for x in confirm])
        self.assertEqual([x['recorded_backend'] for x in dev],
                         [x['recorded_backend'] for x in confirm])
        for index,(a,b) in enumerate(zip(dev,confirm)):
            self.assertEqual(a['release_offset_ns']-b['release_offset_ns'],
                             0 if index<12 else -25_000_000_000)
            self.assertLess(a['release_offset_ns'],120_000_000_000)
        self.assertEqual(plan.BUDGET['explicit_inference'],64)
        self.assertEqual(plan.BUDGET['total_seconds'],2120)

    def test_runner_command_reserve_and_unapproved_run(self):
        class FakeDevice:
            deadline=10**20
            sequence=3100
        fake=FakeDevice()
        with self.assertRaisesRegex(RuntimeError,'ADB observation cap reserve'):
            device.poll(fake,'unused',Path('unused'),{'phase':'development'},
                {'ap_idle_pulse_followup':True,'recorded_replay_confirmation':True,
                 'budget':plan.BUDGET})
        fake.sequence=6500
        with self.assertRaisesRegex(RuntimeError,'ADB observation cap reserve'):
            device.poll(fake,'unused',Path('unused'),{'phase':'confirmation'},
                {'ap_idle_pulse_followup':True,'recorded_replay_confirmation':True,
                 'budget':plan.BUDGET})
        with self.assertRaises(ValueError):
            device.run('nonexistent','unused','unused','unused',False)

    def test_one_shot_low_start_study_gate_does_not_change_old_mode(self):
        new={'ap_idle_response_version':ap.VERSION}
        old={}
        self.assertTrue(d1_arrival_start_ap.study_start_ap_eligible(new,29.9))
        self.assertFalse(d1_arrival_start_ap.study_start_ap_eligible(new,32.5))
        self.assertFalse(d1_arrival_start_ap.study_start_ap_eligible(new,float('nan')))
        self.assertTrue(d1_arrival_start_ap.study_start_ap_eligible(old,33.))

    def test_actual_runner_route_freezes_between_two_sessions_and_cleans_once_each(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); entries=[]
            for index,phase in enumerate(('development','confirmation')):
                manifest=base/f'{phase}.json'
                manifest.write_text(json.dumps({'phase':phase,'session_id':phase}),encoding='utf-8')
                entries.append(dict(index=index,phase=phase,session_id=phase,manifest=manifest.name))
            budget=dict(plan.BUDGET)
            data=dict(ap_idle_pulse_followup=True,recorded_replay_confirmation=True,
                budget=budget,output_root=str(base/'run'),registry=str(base/'registry'),
                entries=entries,frozen_model={'path':'unused','sha256':'f'*64},
                analysis_contract={'sha256':'a'*64},source_files={},
                apk_preflight={'candidate':{}},apk_sha256='b'*64)
            plan_file=base/'collection_plan.json'
            plan_file.write_text(json.dumps(data),encoding='utf-8')
            clock=[1000.]
            calls=[]
            class FakeDevice:
                def __init__(self,*args):self.sequence=0;self.deadline=0
                def call(self,*args,**kwargs):
                    calls.append(('launch',args))
                    if len([x for x in calls if x[0]=='launch'])==2:
                        self_outer.assertTrue((base/'run'/'ap_model_freeze.json').is_file())
                    self.sequence+=1
                    return object()
            self_outer=self
            def snapshot(*args,**kwargs):calls.append(('gate',args[-1]))
            def cleanup(*args,**kwargs):calls.append(('cleanup',None));return {'status':'done'}
            def validate(*args,**kwargs):return {'status':'eligible_descriptive_only'}
            def analysis(folder,frozen,output):
                output.mkdir()
                (output/'summary.json').write_text('{}',encoding='utf-8')
                return {'ap_samples':40}
            with patch.object(plan,'check'),patch.object(device,'ObservedDevice',FakeDevice),\
                 patch.object(device.energy_device,'installation',return_value={'status':'verified'}),\
                 patch.object(device.energy_device,'gates',side_effect=snapshot),\
                 patch.object(device.install,'installed_hash',return_value='b'*64),\
                 patch.object(device.shared,'stage_inputs',return_value='remote'),\
                 patch.object(device,'poll'),\
                 patch.object(device.energy_device,'recover',return_value={'status':'recovered'}),\
                 patch.object(device.shared,'cleanup',side_effect=cleanup),\
                 patch.object(device,'validate',side_effect=validate),\
                 patch.object(plan,'development_evidence',return_value={'version':ap.VERSION}),\
                 patch.object(ap,'analyze_session',side_effect=analysis),\
                 patch.object(device.time,'monotonic',side_effect=lambda:clock[0]),\
                 patch.object(device.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)):
                result=device.run(plan_file,'fake-adb','fake-serial',fileplan.digest(plan_file),True)
            self.assertEqual(result['sessions'],2)
            self.assertEqual([x[0] for x in calls].count('launch'),2)
            self.assertEqual([x[0] for x in calls].count('cleanup'),2)
            self.assertEqual([x[0] for x in calls].count('gate'),2)
            self.assertTrue((base/'run'/'ap_model_freeze_receipt.json').is_file())
            self.assertEqual(fileplan.read(base/'registry'/'completed.json')['sessions'],2)

    def test_analysis_reads_actual_lane_boundaries_and_keeps_future_ap_as_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);artifact=root/'session'/'artifacts';artifact.mkdir(parents=True)
            frozen=root/'frozen.json'
            frozen.write_text(json.dumps({'ap_cooling_rate_per_s':.05,
                'ap_slope_at_30_c_per_s':{'resident_idle':.2,
                    'classification_GPU':.3,'detection_CPU':.25,
                    'classification_GPU+detection_CPU':.4}}),encoding='utf-8')
            origin=10**15
            rows=[]
            for i in range(24):
                dispatch=origin+int((35+i*.2)*1e9)
                task='classification' if i%4==1 else 'detection'
                rows.append(dict(request_id=str(i),task_id=task,
                    selected_backend='GPU' if task=='classification' else 'CPU',
                    priority='urgent' if task=='classification' else 'normal',
                    scheduled_arrival_ns=origin+i*200_000_000,
                    dispatch_ns=dispatch,execution_start_ns=dispatch+1_000_000,
                    output_ready_ns=dispatch+20_000_000,persist_complete_ns=dispatch+30_000_000,
                    worker_release_ns=dispatch+40_000_000,lane_available_ns=dispatch+50_000_000,
                    terminal_status='succeeded'))
            data={'validated.json':{'status':'eligible_descriptive_only',
                    'preload_ap':{'version':ap.VERSION,'effective_idle_reference_c':29.8}},
                  'artifacts/manifest.json':{'ap_idle_response_version':ap.VERSION,
                      'ap_schedule_role':'confirmation'},
                  'artifacts/common_boundary.json':{'start_ns':origin,
                      'planned_end_ns':origin+120_000_000_000},
                  'artifacts/requests.json':rows,
                  'artifacts/start_ap.accepted.json':{'common_start_ns':origin,
                      'gate_mode':'numeric-ap-observe-v2','ap_c':30.}}
            for relative,value in data.items():
                (root/'session'/relative).write_text(json.dumps(value),encoding='utf-8')
            (artifact/'progress.jsonl').write_text(json.dumps({'kind':'phase_end',
                'phase':'resident_cooling','mono_ns':origin+180_000_000_000})+'\n',encoding='utf-8')
            thermal=[{'mono_ns':origin+t*1_000_000_000,'AP':'29.9','thermal_status':'0'}
                     for t in range(36,181,3)]
            (root/'session'/'thermal.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in thermal),encoding='utf-8')
            with patch.object(fileplan,'digest',return_value=saved_replay.FROZEN_SHA):
                first=ap.analyze_session(root/'session',frozen,root/'analysis_one')
            path1=(root/'analysis_one'/'ap_path.csv').read_text()
            thermal[10]['AP']='31.9'
            (root/'session'/'thermal.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in thermal),encoding='utf-8')
            with patch.object(fileplan,'digest',return_value=saved_replay.FROZEN_SHA):
                second=ap.analyze_session(root/'session',frozen,root/'analysis_two')
            self.assertEqual(first['data_role'],'independent_confirmation')
            self.assertEqual(first['ap_samples'],len(thermal))
            self.assertNotEqual(first['ap_path_mae_c'],second['ap_path_mae_c'])
            self.assertEqual(first['ap_peak_predicted_c'],second['ap_peak_predicted_c'])
            self.assertIn('predicted_ap_c',path1)
            for i,row in enumerate(rows):
                dispatch=origin+int((35+i*.1)*1e9)
                offset=dispatch-row['dispatch_ns']
                for key in ('dispatch_ns','execution_start_ns','output_ready_ns',
                            'persist_complete_ns','worker_release_ns','lane_available_ns'):
                    row[key]+=offset
            (artifact/'requests.json').write_text(json.dumps(rows),encoding='utf-8')
            with patch.object(fileplan,'digest',return_value=saved_replay.FROZEN_SHA):
                with self.assertRaisesRegex(ValueError,'insufficient work AP samples'):
                    ap.analyze_session(root/'session',frozen,root/'analysis_too_short')


if __name__=='__main__':unittest.main()
