import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_background_activity_result as r


class ResultTests(unittest.TestCase):
    def test_missing_bracket_and_gap_are_null_without_extrapolation(self):
        self.assertEqual(r.interpolate([(10,2.),(20,4.)],[0,15,25],10),[None,3.,None])
        self.assertEqual(r.interpolate([(10,2.),(20,4.)],[15],9),[None])
        with self.assertRaises(ValueError):r.interpolate([(10,2.),(10,3.)],[10],10)

    def test_real_c0_reader_preserves_trace_failure_and_prediction_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'run/00_test';art=folder/'artifacts';art.mkdir(parents=True)
            origin=100_000_000_000
            def save(path,value):path.write_text(json.dumps(value),encoding='utf8')
            save(root/'manifest.json',{});save(art/'manifest.json',{})
            save(folder/'validated.json',{'status':'eligible_descriptive_only'})
            save(art/'requests.json',[]);save(art/'cleanup.json',{'status':'completed'})
            save(art/'common_boundary.json',{'start_ns':origin})
            save(art/'start_ap.accepted.json',{'ap_c':28.,'initial_ap_in_frozen_development_range':False})
            events=[dict(kind='phase_start',phase='resident_baseline',mono_ns=origin-30_000_000_000),
                    dict(kind='phase_end',phase='resident_cooling',mono_ns=origin+180_000_000_000)]
            for kind,n in [('runtime_start',4),('runtime_return',4),('warmup_start',8),('warmup_return',8)]:
                events.extend(dict(kind=kind,mono_ns=origin-31_000_000_000) for _ in range(n))
            for second in range(-31,182):
                t=origin+second*1_000_000_000
                events.append(dict(kind='power_sample',snapshot_start_ns=t,sensor_read_end_ns=t,
                    current_raw=-250,current_valid=True,voltage_mV=4000,plugged=0,self_cpu_ms=(second+40)*100))
            (art/'progress.jsonl').write_text('\n'.join(json.dumps(x) for x in events)+'\n',encoding='utf8')
            thermal=[dict(mono_ns=origin+s*1_000_000_000,before_ns=origin+s*1_000_000_000-1,
                after_ns=origin+s*1_000_000_000+1,AP=str(28.-max(0,s-35)*.001),thermal_status='0') for s in range(-30,182,2)]
            (folder/'thermal.jsonl').write_text('\n'.join(json.dumps(x) for x in thermal)+'\n',encoding='utf8')
            plan=dict(output_root=str(root/'run'));entry=dict(index=0,session_id='test',manifest='manifest.json',requests=0,condition='C0')
            model=r.p.read(r.plan_code.MODEL)
            real=r.online.costs;observed=[]
            def checked(segments,initial,query,frozen,end):
                self.assertTrue(all(e['hi']<35 for e in initial['preload']))
                self.assertNotIn('observed_ap_c',initial)
                self.assertNotIn('postload_power',initial)
                observed.append(initial)
                return real(segments,initial,query,frozen,end)
            with patch.object(r.trace,'summarize',side_effect=ValueError('trace loss/error')),patch.object(r.online,'costs',side_effect=checked):
                summary,curves,aps,_=r.session(root/'plan.json',plan,entry,model,root/'unused')
            self.assertEqual(summary['trace_status'],'contract_ineligible')
            self.assertIsNone(summary['system_cpu_activity'])
            self.assertAlmostEqual(summary['observed_energy_j'],120)
            self.assertAlmostEqual(curves[-1]['observed_j'],120)
            self.assertAlmostEqual(summary['self_cpu_seconds'],12)
            self.assertEqual(summary['completed'],0);self.assertEqual(summary['warmup'],8)
            self.assertEqual(len(observed),1);self.assertTrue(aps)
            # Changing pre-zero power must affect the model-declared -20..30 window,
            # while explicit legacy reproduction remains 10..30. AP must not change.
            for e in events:
                if e['kind']=='power_sample' and e['snapshot_start_ns'] < origin:
                    e['current_raw']=-500
            (art/'progress.jsonl').write_text('\n'.join(json.dumps(x) for x in events)+'\n',encoding='utf8')
            with patch.object(r.trace,'summarize',side_effect=ValueError('trace loss/error')):
                fixed,_,fixed_ap,_=r.session(root/'plan.json',plan,entry,model,root/'unused')
                legacy,_,legacy_ap,_=r.session(root/'plan.json',plan,entry,model,root/'unused',True)
            self.assertAlmostEqual(fixed['predicted_energy_j'],166.8)
            self.assertAlmostEqual(legacy['predicted_energy_j'],120.)
            self.assertEqual(fixed_ap,legacy_ap)
            self.assertEqual(fixed['preload_power_window_s'],[-20,30])
            self.assertEqual(legacy['preload_power_window_s'],[10,30])
            invalid=dict(model);invalid.pop('preload_power_window_s')
            with self.assertRaisesRegex(ValueError,'frozen preload'):
                r.load_inputs(root/'plan.json',plan,entry,invalid)
            events=[e for e in events if e['kind']!='warmup_return']
            (art/'progress.jsonl').write_text('\n'.join(json.dumps(x) for x in events)+'\n',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'consumption unconfirmed'):
                r.session(root/'plan.json',plan,entry,model,root/'unused')

    def test_partial_block_requires_opt_in_and_preserves_missing_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';(run/'00_a').mkdir(parents=True)
            (run/'00_a/validated.json').write_text('{}')
            model=root/'model.json';model.write_text('{}')
            plan=dict(output_root=str(run),activity_model=dict(path=str(model),sha256=r.p.digest(model)),
                entries=[dict(index=0,session_id='a'),dict(index=1,session_id='b')])
            file=root/'plan.json';file.write_text(json.dumps(plan))
            (run/'FINAL_RECEIPT.json').write_text(json.dumps(dict(status='stopped_no_resume',completed_sessions=1)))
            with self.assertRaisesRegex(ValueError,'partial opt-in'):r.run(file,root/'exports',root/'blocked')
            row=dict(condition='C0',trace_error=None)
            with patch.object(r,'session',return_value=(row,[dict(condition='C0',common_s=1)],
                    [dict(condition='C0',common_s=1)],[])) as call:
                result=r.run(file,root/'exports',root/'partial',allow_partial=True)
                call.assert_called_once()
            self.assertFalse(result['full_planned_block_completed'])
            self.assertEqual((result['completed_sessions'],result['planned_sessions']),(1,2))
            self.assertEqual(result['acquisition_status'],'stopped_no_resume')


if __name__=='__main__':unittest.main()
