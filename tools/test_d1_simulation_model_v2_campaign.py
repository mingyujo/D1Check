import unittest
import tempfile
from pathlib import Path
from tools import d1_simulation_model_v2_campaign as c
from tools import d1_simulation_model_v2 as m


class CampaignTests(unittest.TestCase):
    def test_budget_matches_every_roster_entry_not_only_global_total(self):
        b=c.budget();self.assertEqual(sum(r['work_requests'] for r in b['profiles']),7680)
        self.assertEqual(b['explicit_inference'],7768);self.assertEqual(b['total_seconds'],600+8*1780+630+600+600)
        self.assertEqual(b['adb_command_slots'],29448);self.assertEqual(b['pre_cleanup_command_slots'],29048)
        self.assertEqual(b['fixed_observation_seconds'],6*(120+498+180)+2*(30+120+60))
    def test_same_probe_train_and_recovery_anchor_in_both_orders(self):
        for profile in c.PROFILES[:6]:
            blocks=c.resident.blocks(profile);offsets={};now=0
            for b in blocks:offsets[b['id']]=now;now+=b['seconds']
            key=0 if profile.endswith('_A') else 1
            self.assertEqual(offsets['conditioning_pair'],24)
            self.assertEqual(offsets['after90_solo'+str(key)]-144,90)
            self.assertEqual(offsets['after240_solo'+str(key)]-144,240)
            self.assertEqual(now+90,498)
    def test_occupancy_uses_lane_release_and_rejects_unmeasured_pairs(self):
        rows=[dict(key='classification_GPU',dispatch_ns=0,lane_available_ns=4_000_000_000),dict(key='detection_CPU',dispatch_ns=2_000_000_000,lane_available_ns=5_000_000_000)]
        ss=m.occupancy(rows,0,6_000_000_000);self.assertEqual(ss[1]['state'],'classification_GPU+detection_CPU');self.assertEqual(ss[-1]['state'],'idle')
        rows[1]['key']='classification_CPU'
        with self.assertRaises(ValueError):m.occupancy(rows,0,6_000_000_000)
    def test_repair_does_not_add_physical_sessions_or_inference_slots(self):
        b=c.repair_budget();self.assertEqual(b['sessions']+b['reused_measured_windows'],8)
        self.assertEqual(b['work_requests']+1248,7680);self.assertEqual(b['explicit_inference']+1260,7768)
    def test_arrival_budget_exposes_poll_alias_and_stays_within_original_clock_and_commands(self):
        b=c.arrival_repair_budget()
        self.assertEqual(b['adb_commands'],b['pre_cleanup_command_slots'])
        self.assertEqual(b['sessions'],2);self.assertEqual(b['reused_measured_windows'],6)
        self.assertEqual(b['explicit_inference'],208)
        self.assertEqual(b['total_seconds'],600+2*765+90+600)
        self.assertLessEqual(9652+b['adb_command_slots'],c.budget()['adb_command_slots'])
    def test_user_resume_adds_only_one_par_session_and_no_new_fit_or_clock(self):
        b=c.resume_budget();self.assertEqual(b['sessions'],1);self.assertEqual(b['reused_measured_windows'],7)
        self.assertEqual(b['work_requests'],96);self.assertEqual(b['explicit_inference'],104)
        self.assertEqual(b['total_seconds'],600+90+765+600)
        self.assertEqual(b['adb_commands'],b['pre_cleanup_command_slots'])
        self.assertEqual(b['installs'],0);self.assertEqual(b['freeze_seconds'],0)
    def test_completed_reuse_preserves_validation_bytes_bound_to_frozen_model(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'source';source.mkdir();target=root/'out';target.mkdir()
            payload=b'{"work_calls": 12, "original_failure_preserved": true}\n'
            (source/'validated.json').write_bytes(payload)
            plan=dict(model_v2_arrival_host_repair=True,model_v2_prior_completed=[dict(session_id='s',source_folder=str(source),files={'validated.json':c.p.digest(source/'validated.json')})])
            result=c.reuse_session(dict(index=0,session_id='s'),plan,target)
            self.assertEqual((target/'00_s/validated.json').read_bytes(),payload)
            self.assertEqual(result['work_calls'],12)
    def test_arrival_post_cleanup_sampler_failure_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);manifest=root/'manifest.json'
            c.write(manifest,dict(protocol='arrival-energy-synthetic-v1'))
            (root/'sampler_failure.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'application failure preserved'):
                c.summarize_session(root,manifest,{})
    def test_only_a_failed_sample_after_completed_cleanup_can_be_classified(self):
        from tools import d1_resident_identification_analysis as a
        cleanup=dict(status='completed',error=None,sampler_failure=None,mono_ns=100)
        failure=dict(exception_class='java.lang.IllegalStateException',message='journal closed/failed',phase='cleanup',stage='sampler_snapshot_or_event',mono_ns=121)
        self.assertTrue(a.post_cleanup_sampler_race(cleanup,failure))
        for changed in (dict(failure,mono_ns=99),dict(failure,phase='load'),dict(failure,message='inference failed')):
            self.assertFalse(a.post_cleanup_sampler_race(cleanup,changed))
        self.assertFalse(a.post_cleanup_sampler_race(dict(cleanup,status='failed'),failure))

if __name__=='__main__':unittest.main()
