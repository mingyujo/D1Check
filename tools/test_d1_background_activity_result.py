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
            events=[e for e in events if e['kind']!='warmup_return']
            (art/'progress.jsonl').write_text('\n'.join(json.dumps(x) for x in events)+'\n',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'consumption unconfirmed'):
                r.session(root/'plan.json',plan,entry,model,root/'unused')


if __name__=='__main__':unittest.main()
