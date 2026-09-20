import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_service_v2 as v


class ServiceV2Tests(unittest.TestCase):
    def test_cold_early_warm_candidate_distinct(self):
        self.assertEqual([v.phase('process_first',n) for n in (1,2,3)],
                         ['process_first_first','process_first_early','process_first_warm_candidate'])

    def test_transition_origin_never_merged(self):
        for n in (1,2,3):self.assertNotEqual(v.phase('process_first',n),v.phase('recreated',n))

    def test_invalid_runtime_history(self):
        for origin,n in [('unknown',1),('process_first',0),('recreated',True)]:
            with self.assertRaises(ValueError):v.phase(origin,n)

    def test_setup_service_no_double_count(self):
        result=v.boundary(100,30,20)
        self.assertEqual(result['active_service_ns'],70)
        self.assertEqual(result['other_active_ns'],50)

    def test_overlapping_or_invalid_duration_rejected(self):
        for args in [(10,9,2),(-1,0,0),(True,0,0),(10,1.5,2)]:
            with self.assertRaises(ValueError):v.boundary(*args)

    def test_finite_sample_rank(self):
        self.assertFalse(v.finite_interval(list(range(8)))['finite'])
        self.assertEqual(v.finite_interval(list(range(9)))['radius'],8)
        self.assertEqual(v.finite_interval(list(range(99)))['rank'],90)

    def test_bad_scores_rejected(self):
        for scores in [[float('nan')],[-1],[float('inf')]]:
            with self.assertRaises(ValueError):v.finite_interval(scores)

    def test_session_leakage(self):
        with self.assertRaisesRegex(ValueError,'leakage'):v.partition(['d'],['c'],['c'],['d'])

    def test_consumed_holdout_rejected(self):
        with self.assertRaisesRegex(ValueError,'consumed'):v.partition(['d'],[],['old'],['d','old'])

    def test_consumed_conformal_calibration_rejected(self):
        with self.assertRaisesRegex(ValueError,'consumed'):v.partition(['d'],['old'],[],['d','old'])

    def test_new_partition(self):
        self.assertTrue(v.partition(['d'],['c'],['h'],['d','old']))

    def receipt(self):
        return dict(session_id='new',fingerprint='newtrace',started_utc='2026-09-21T00:00:01+00:00',request_ids=['newrequest'])

    def test_stale_replayed_id_trace_request(self):
        for change in [dict(session_id='old'),dict(fingerprint='oldtrace'),dict(request_ids=['oldrequest']),
                       dict(started_utc='2026-09-20T00:00:00+00:00'),dict(request_ids=['x','x'])]:
            r=self.receipt();r.update(change)
            with self.assertRaises(ValueError):v.fresh_receipts([r],['old'],['oldrequest'],['oldtrace'],'2026-09-21T00:00:00+00:00')

    def test_replay_across_new_receipts(self):
        r=self.receipt()
        with self.assertRaises(ValueError):v.fresh_receipts([r,r],[],[],[],'2026-09-21T00:00:00+00:00')

    def test_fresh_receipt(self):
        self.assertTrue(v.fresh_receipts([self.receipt()],[],[],[],'2026-09-21T00:00:00+00:00'))

    def arms(self):
        a={k:'same' for k in v.PAIR_FIELDS}
        a.update(session_id='a',runtime_precreated=True,resident_tasks=['classification','detection'],
                 warmup_per_runtime=3,thermal_range=[0],configuration='CPU_serial_two_resident',
                 backend_mapping={'classification':'CPU','detection':'CPU'},max_in_flight=1)
        b=copy.deepcopy(a);b.update(session_id='b',configuration='CPU_GPU_two_resident',
                                   backend_mapping={'classification':'CPU','detection':'GPU'},max_in_flight=2)
        return a,b

    def test_fair_paired_control(self):self.assertTrue(v.paired(*self.arms()))

    def test_asymmetric_control_rejected(self):
        for key in v.PAIR_FIELDS:
            a,b=self.arms();b[key]='changed'
            with self.assertRaises(ValueError):v.paired(a,b)

    def test_both_arms_unfair_rejected(self):
        a,b=self.arms();a['runtime_precreated']=b['runtime_precreated']=False
        with self.assertRaises(ValueError):v.paired(a,b)

    def test_ab_ba_reproducible_balanced(self):
        a=v.paired_order(10,v.SEED)
        self.assertEqual(a,v.paired_order(10,v.SEED))
        self.assertEqual(list(a.values()).count('AB'),5)
        self.assertNotEqual(a,v.paired_order(10,v.SEED+1))

    def memory(self):
        return (dict(mono_ns=100,avail_bytes=1000,threshold_bytes=200,low_memory=False,pss_bytes=100,
                     memory_class_mib=256,large_memory_class_mib=512,java_used_bytes=50,java_max_bytes=200,thermal_status=0),
                dict(validated=True,max_age_ns=10,incremental_pss_upper_bytes=300,pressure_reserve_bytes=100,
                     java_increment_upper_bytes=20,java_reserve_bytes=30,resident_pss_upper_bytes=500))

    def test_memory_gate(self):self.assertTrue(v.memory_admit(*self.memory(),105))

    def test_memory_fail_closed(self):
        for change in [dict(low_memory=True),dict(thermal_status=1),dict(avail_bytes=500),
                       dict(mono_ns=200),dict(pss_bytes=501),dict(java_used_bytes=151),dict(avail_bytes=float('nan'))]:
            s,e=self.memory();s.update(change);self.assertFalse(v.memory_admit(s,e,105))
        s,e=self.memory();e['validated']=False;self.assertFalse(v.memory_admit(s,e,105))
        s,e=self.memory();del s['threshold_bytes'];self.assertFalse(v.memory_admit(s,e,105))
        self.assertFalse(v.memory_admit(*self.memory(),111))

    def test_memory_class_is_not_pss_limit(self):
        s,e=self.memory();s['memory_class_mib']=1;s['pss_bytes']=2000000;e['resident_pss_upper_bytes']=3000000
        self.assertTrue(v.memory_admit(s,e,105))

    def spans(self):
        p=dict(span_id='p',session_id='s',runtime_id='r',start_ns=0,end_ns=100,parent_id=None)
        a=dict(span_id='a',session_id='s',runtime_id='r',start_ns=10,end_ns=30,parent_id='p',exclusive=True)
        b=dict(a,span_id='b',start_ns=30,end_ns=40)
        return [p,a,b]

    def test_nested_setup_boundary(self):self.assertTrue(v.validate_spans(self.spans()))

    def test_bad_spans_rejected(self):
        for change in [dict(end_ns=101),dict(start_ns=31,end_ns=30),dict(parent_id='missing'),dict(parent_id='a'),dict(runtime_id='other')]:
            spans=self.spans();spans[1].update(change)
            with self.assertRaises(ValueError):v.validate_spans(spans)
        spans=self.spans();spans[2]['start_ns']=29
        with self.assertRaises(ValueError):v.validate_spans(spans)

    def test_empirical_joint_pair_seed(self):
        rows=[dict(session_id='s',request_id=str(i),setup_ns=i,active_service_ns=100-i,inference_ns=1) for i in range(5)]
        model={'k':{'s':rows}}
        a=v.empirical_draw(model,'k',v.SEED,0,2)
        self.assertEqual(a,v.empirical_draw(model,'k',v.SEED,0,2))
        self.assertEqual(a['setup_ns']+a['active_service_ns'],100)
        with self.assertRaises(ValueError):v.empirical_draw(model,'unknown',v.SEED,0,0)

    def test_schema_valid_and_rejects_approval(self):
        import jsonschema
        schema=v.read(Path('tools/schemas/service-model-v2-design-v1.schema.json'))
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertEqual(schema['properties']['coverage_required']['const'],.9)
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate({'simulation_approved':True},schema)

    def test_frozen_bytes_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'design_contract.json';path.write_text('{}')
            h=v.digest(path);path.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'immutability'):v.validate(tmp,h)

    def design_fixture(self, root):
        names=['development_rows.json','diagnostic_attempt.json','candidate_comparison.json','stabilization.json',
               'sample_size.json','uncertainty_analysis.json','development_model.json','development_registry.json']
        for name in names:v.save(root/name,{})
        source=root/'source.txt';source.write_text('original')
        c=dict(protocol=v.PROTOCOL,status=v.STATUS,seed=v.SEED,simulation_approved=False,device_execution_allowed=False,
               consumed_sessions=['old'],selected_structure='C+E',parameter_status='development only; new telemetry calibration required',
               coverage_required=.9,deadline='calibration_pending',thermal_status_allowed=[0],fallback='forbidden',required_missing=['spans'],
               artifacts={name:v.digest(root/name) for name in names},sources={str(source):v.digest(source)},
               analysis_sources={str(source):v.digest(source)})
        v.save(root/'design_contract.json',c)
        return v.digest(root/'design_contract.json')

    def test_noop_and_dry_run_have_no_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);h=self.design_fixture(root);result=v.validate(root,h)
            self.assertEqual(result['device_commands'],[])
            self.assertEqual(result['dispatch_count'],0)
            self.assertEqual(result['simulated_completion_count'],0)
            v.save(root/'no_op.json',result);self.assertEqual(v.validate(root,h),result)

    def test_stale_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);h=self.design_fixture(root);(root/'source.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError,'stale'):v.validate(root,h)

    def test_fabricated_noop_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);h=self.design_fixture(root);v.save(root/'no_op.json',dict(dispatch_count=1))
            with self.assertRaisesRegex(ValueError,'no-op'):v.validate(root,h)

    def test_artifact_replay_mutation_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);h=self.design_fixture(root);(root/'development_rows.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'artifact'):v.validate(root,h)


if __name__=='__main__':unittest.main()
