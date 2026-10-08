import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools import d1_resident_identification_plan as p
from tools import d1_resident_identification_analysis as a
from tools import d1_logger_v4 as logger


class PlanTests(unittest.TestCase):
    def test_budget_roster_exact_not_old_budget_fraction(self):
        b=p.budget()
        self.assertEqual(b['work_requests'],6288);self.assertEqual(b['explicit_inference'],6376)
        self.assertEqual(b['fixed_observation_seconds'],5580);self.assertEqual(b['total_seconds'],19070)
        self.assertEqual(b['runtime_creations'],32);self.assertEqual(b['staged_files'],56)
        self.assertEqual(sum(x['work_requests'] for x in b['profiles']),b['work_requests'])
        self.assertGreater(b['adb_command_slots'],b['pre_cleanup_command_slots'])

    def test_fixed_profiles_keep_solo_gpu_and_supported_parallel(self):
        for profile in p.PROFILES:
            if profile.startswith('ARRIVAL_'):continue
            for b in p.blocks(profile):self.assertIn(b['lane_indices'],[[],[0],[1],[2],[1,2]])
        self.assertEqual(p.profile_budget('DEV_A')['common_work_seconds'],600)
        self.assertEqual(p.profile_budget('CONF_MIX_A')['common_work_seconds'],210)
        with self.assertRaises(ValueError):p.blocks('CONF_MIX_UNKNOWN')

    def test_script_preserves_verified_foreground_owner_wrapper(self):
        text=p.script_text()
        for term in ['host_entry_','powershell_pid=$PID','D1_ENERGY_HOST_RUN_ID','stdout.txt','stderr.txt','normal_wrapper_return','--serial $Serial','--expected-sha $ExpectedPlanSha256']:
            self.assertIn(term,text)
        self.assertNotIn('Start-Process',text)

    def test_recorded_original_parser_fixture_reused(self):
        fixture=p.old.p.read(Path('tools/fixtures/energy_state_recorded_parser.json'))
        actual=logger.parse_thermalservice(fixture['thermal_raw'])
        self.assertEqual({k:actual[k] for k in fixture['thermal_parsed']},fixture['thermal_parsed'])
        raw=b'{"kind":"request_start","phase":"load","id":"a"}\n{"kind":'
        r=p.progress_consumption(raw,True,600)
        self.assertEqual(r['counts']['load']['confirmed_started_at_least'],1)
        self.assertEqual(r['counts']['load']['actual_started_upper'],600)
        self.assertTrue(r['counts']['load']['missing_completion_is_not_success'])

    def test_confirmation_cannot_fit_or_freeze(self):
        with self.assertRaises(ValueError):a.energy_fit([dict(role='confirmation')]*4,{})
        with self.assertRaises(ValueError):a.freeze([dict(role='confirmation',id=str(i)) for i in range(4)],{})

    def test_power_coefficients_identified_with_idle_and_all_states(self):
        truth=np.array([.04,.5,.7,.4,.8]);cases=[]
        for i in range(3):
            seg=[dict(start_s=0.,end_s=35.,state='idle')]
            for n,state in enumerate(['classification_CPU','detection_CPU','classification_GPU','classification_GPU+detection_CPU','idle']):
                seg.append(dict(start_s=35.+n*20,end_s=55.+n*20,state=state))
            cases.append(dict(id=str(i),role='development',pre_w=1.,actual=seg,common_end_s=135))
        def integral(c,start,end):return (end-start)*c['pre_w']+np.r_[end-start,p.j.m.base.exposure(c['actual'],start,end)]@truth
        with patch.object(a.j.m,'integral',side_effect=integral):result=a.energy_fit(cases,{})
        self.assertAlmostEqual(result['idle_bias_w'],truth[0],places=10)
        for k,v in zip(p.j.m.base.STATES,truth[1:]):self.assertAlmostEqual(result['increments'][k],v,places=10)
        for c in cases:c['actual']=[dict(start_s=0.,end_s=135.,state='idle')]
        with patch.object(a.j.m,'integral',side_effect=integral),self.assertRaises(ValueError):a.energy_fit(cases,{})

    def test_actual_assessment_never_refits_confirmation(self):
        c=copy.deepcopy(p.j.panel()[0][0]);c.update(role='confirmation',common_end_s=120)
        original=p.old.p.read(p.j.m.MODEL)
        model=dict(energy=dict(idle_bias_w=0.,increments=original['energy_increment_w']),ap=copy.deepcopy(original['ap']))
        before=copy.deepcopy(model)
        with patch.object(a,'fitting',side_effect=AssertionError('no confirmation fit')):
            result=a.assess(c,model,original)
        self.assertEqual(model,before)
        self.assertAlmostEqual(result['original']['mae_c'],result['candidate']['mae_c'],places=12)
        self.assertAlmostEqual(result['candidate']['common120_signed_j'],result['original']['common120_signed_j'],places=12)

    def test_original_frozen_model_hash_preserved(self):
        self.assertEqual(p.old.p.digest(p.j.m.MODEL),p.j.m.MODEL_SHA)

    def test_development_freeze_and_confirmation_full_pc_path(self):
        # Deterministic synthetic model fixture, not fitted device evidence.
        original=p.old.p.read(p.j.m.MODEL);cases=[]
        for i,profile in enumerate(p.PROFILES[:4]):
            cursor=35.;segments=[dict(start_s=0.,end_s=35.,state='idle')]
            for b in p.blocks(profile):
                state='+'.join(sorted(p.old.KEYS[n] for n in b['lane_indices'])) or 'idle'
                segments.append(dict(start_s=cursor,end_s=cursor+b['seconds'],state=state));cursor+=b['seconds']
            end=35+p.profile_budget(profile)['common_work_seconds'];segments.append(dict(start_s=cursor,end_s=end+180,state='idle'))
            pre=[dict(t=float(t),ap=29.,lo=t-.1,hi=t+.1) for t in range(-30,35,2)];q=list(range(35,int(end+180),4))
            c=dict(id='fixture_'+str(i),role='development',policy=profile,pre=pre,q=q,actual=segments,pre_w=1.,common_end_s=end,last_lane_s=cursor)
            c['ap']=p.j.m.thermal.predict(p.j.m.case_input(c,segments),original['ap'])[0];cases.append(c)
        def integral(c,start,end):
            def e(t):return t+max(0,t-35)*.1+float(p.j.m.base.exposure(c['actual'],0,t)@np.array([original['energy_increment_w'][k] for k in p.j.m.base.STATES]))
            return e(end)-e(start)
        with patch.object(a.j.m,'integral',side_effect=integral):
            frozen=a.freeze(cases,original)
            confirmation=copy.deepcopy(cases[0]);confirmation.update(id='confirmation_fixture',role='confirmation')
            before=copy.deepcopy(frozen)
            with patch.object(a,'fitting',side_effect=AssertionError('confirmation must not fit')):result=a.assess(confirmation,frozen['model'],original)
            self.assertEqual(before,frozen)
            self.assertTrue(frozen['confirmation_fit_forbidden'])
            self.assertLess(result['candidate']['registered_absolute_j'],1e-7)
            self.assertLess(result['candidate']['mae_c'],1e-7)

    def test_actual_read_case_entry_with_registered_blocks_and_missing_block(self):
        # Software fixture, not a phone execution. Real parser schema is reused above.
        sid='00000000-0000-0000-0000-000000000001';begin=120*10**9;end=720*10**9;cool=900*10**9
        m=dict(session_id=sid,phase='development_fixture',identification_role='development',identification_profile='DEV_A',
               work_call_cap=1200,common_work_seconds=600,blocks=p.blocks('DEV_A'))
        events=[]
        def event(kind,t,phase='load',**fields):events.append(dict(kind=kind,mono_ns=t,phase=phase,session_id=sid,**fields))
        for i in range(4):event('runtime_return',i+1,phase='setup')
        for i in range(8):event('warmup_return',i+10,phase='warmup')
        for i in range(4):event('lane_available',20+i,phase='eligibility_serial_probe',id=f'probe{i}',key=p.old.KEYS[i],
                               dispatch_ns=1,execution_start_ns=2,output_ready_ns=3,persist_complete_ns=4,worker_release_ns=5,lane_available_ns=6)
        event('identification_common_start',begin,start_ns=begin,window_ns=600*10**9)
        offset=0
        for b in m['blocks']:
            start=begin+offset*10**9;finish=start+b['seconds']*10**9
            event('block_start',start,block=b['id'],keys=[p.old.KEYS[i] for i in b['lane_indices']],target_seconds=b['seconds'],nominal_offset_ns=offset*10**9)
            for key_index in b['lane_indices']:
                for n in range(2):
                    lo=start+n*30*10**9;hi=lo+30*10**9;id=f'{b["id"]}-{key_index}-{n}'
                    event('request_start',lo+1,id=id,key=p.old.KEYS[key_index])
                    event('lane_available',hi,block=b['id'],id=id,key=p.old.KEYS[key_index],dispatch_ns=lo,execution_start_ns=lo+1,
                          output_ready_ns=hi-3,persist_complete_ns=hi-2,worker_release_ns=hi-1,lane_available_ns=hi)
            event('block_end',finish,block=b['id']);offset+=b['seconds']
        event('identification_common_end',end,start_ns=begin,planned_end_ns=end,end_ns=end)
        event('phase_end',cool,phase='resident_cooling')
        for t in range(0,900_000,900):
            ns=t*10**6;event('power_sample',ns+300,sample_period_ms=900,plugged=0,thermal_status=0,interactive=True,admission_reason='admit',
                            snapshot_start_ns=ns,sensor_read_end_ns=ns+100,state_snapshot_ns=ns+200,resident_keys=list(p.old.KEYS),current_raw=-250,voltage_mV=4000,current_valid=True)
        events.sort(key=lambda r:r['mono_ns'])
        for i,r in enumerate(events):r['sequence']=i
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'artifacts';folder.mkdir();manifest=root/'input_manifest.json'
            def write(path,value):path.write_text(json.dumps(value),encoding='utf8')
            write(manifest,m);write(folder/'manifest.json',m);write(folder/'cleanup.json',dict(status='completed'))
            write(folder/'start_ap.accepted.json',dict(ap_c=28.2,read_before_ns=begin-10**9,read_after_ns=begin-5*10**8))
            dummy=root/'reference.json';write(dummy,{})
            for r in events:
                if r['kind']=='lane_available':write(folder/(r['id']+'.result.json'),{})
            text=''.join(json.dumps(r)+'\n' for r in events);(folder/'progress.jsonl').write_text(text,encoding='utf8')
            thermal=[dict(mono_ns=t*10**9,before_ns=t*10**9-10**8,after_ns=t*10**9+10**8,AP='28.2',thermal_status='0',sampling_uncertainty_ns=10**8) for t in range(0,901,2)]
            (root/'thermal.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in thermal),encoding='utf8')
            plan=dict(references={k:dict(path=str(dummy)) for k in p.old.KEYS})
            with patch.object(a.old,'quality',return_value=None):
                c,stats=a.read_case(folder,manifest,plan)
                self.assertEqual(stats['work_calls'],10);self.assertEqual(c['common_end_s'],635)
                self.assertTrue(c['pre'][-1]['hi']<35)
                broken=[r for r in events if not (r['kind']=='block_end' and r.get('block')=='state_0')]
                for i,r in enumerate(broken):r['sequence']=i
                (folder/'progress.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in broken),encoding='utf8')
                with self.assertRaisesRegex(ValueError,'missing registered block'):a.read_case(folder,manifest,plan)


if __name__=='__main__':unittest.main()
