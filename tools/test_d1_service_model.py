import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_service_model as sm
from tools.d1_service_model_generate import generate
from tools.d1_task_profile import read, digest
from tools.d1_sim_prepare import canonical


def row(sid='s1', ordinal=1, cell='classification/CPU', value=100, gap=10):
    return dict(session_id=sid, request_id=sid+'-'+str(ordinal), cell=cell, priority='urgent',
                role='calibration', purpose='solo', pair='solo', ordinal=ordinal,
                first=ordinal==1, transition=False, from_backend=None, gap_ns=gap,
                service_ns=value, prepare_ns=10, inference_ns=20, response_ns=value+10,
                sample_id='sample',terminal_ns=1000+ordinal)


def fixtures():
    sessions=[]
    for task in ('classification','detection'):
        for backend in ('CPU','GPU'):
            for repeat in range(3):
                sid=task+backend+str(repeat)
                count=10 if repeat<2 else 5
                rows=[row(sid,i+1,task+'/'+backend, (100 if i>1 else 500)+repeat) for i in range(count)]
                sessions.append(dict(session_id=sid, purpose='solo' if repeat<2 else 'holdout',
                    started_utc='2026-09-01T00:00:00+00:00',measurement_fingerprint=sm.sha([sid]),
                    apk_sha256='a'*64,device_fingerprint='test-device',rows=rows,files=[],
                    peak_pss_kb=1000+repeat,thermal_statuses=[0],battery_temperature_deci_c=[300,310]))
    return sessions


class ServiceModelTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def bundle(self, name='bundle'):
        source=self.root/'source'
        source.mkdir(exist_ok=True)
        (source/'device').mkdir(exist_ok=True)
        for f in ('FINAL_REPORT.md','capability_matrix.json','raw_comparison.json','hash_audit.json'):
            (source/f).write_text('{}')
        output=self.root/name
        with patch('tools.d1_service_model_generate.load_sessions',return_value=(fixtures(),[])):
            generate(source,output,123)
        return output

    def rehash(self, root, name, value):
        (root/name).write_bytes(canonical(value))
        receipt=read(root/'provenance.json')
        receipt['files'][name]=digest(root/name)
        (root/'provenance.json').write_bytes(canonical(receipt))

    def prospective(self):
        sessions=fixtures()
        model=sm.fit([r for s in sessions[:2] for r in s['rows']],'initial_state_mean')
        criteria={'wape_max':.1}
        plan=dict(frozen_utc='2026-09-20T00:00:00+00:00',model_sha256=sm.sha(model),criteria=criteria,
                  criteria_sha256=sm.sha(criteria),previously_seen=[s['session_id'] for s in sessions],
                  seen_measurements=[s['measurement_fingerprint'] for s in sessions],
                  seen_requests=[r['request_id'] for s in sessions for r in s['rows']],
                  apk_sha256='a'*64,device_fingerprint='test-device')
        session=copy.deepcopy(sessions[0]);session.update(session_id='new',
            started_utc='2026-09-21T00:00:00+00:00',measurement_fingerprint='new-trace')
        session['rows']=[row('new',i+1) for i in range(10)]
        return plan,model,session

    def test_state_keeps_first_and_followup(self):
        self.assertEqual(sm.state(row(),20),'cold_first')
        self.assertEqual(sm.state(row(ordinal=2),20),'initial_followup')
        self.assertEqual(sm.state(row(ordinal=2,gap=30),20),'warm_steady')
        self.assertEqual(sm.state(row(ordinal=3),20),'warm_steady')

    def test_transition_precedes_cold(self):
        r=row(cell='detection/GPU');r.update(transition=True,from_backend='CPU')
        self.assertEqual(sm.state(r,20),'transition_CPU_to_GPU')

    def test_gap_uses_dispatch_history_only(self):
        rows=[row('s1',2,gap=10),row('s2',2,gap=100000)]
        a=sm.gap_boundary(rows)
        rows[0]['service_ns']=99999999
        self.assertEqual(a,sm.gap_boundary(rows))
        self.assertEqual(a['boundary_ns'],1000)

    def test_partition_sessions_not_requests(self):
        split=sm.make_split(fixtures(),123)
        self.assertEqual(len(split['calibration']),8)
        self.assertEqual(len(split['retrospective_holdout']),4)
        self.assertEqual(split['prospective_holdout'],[])

    def test_split_rejects_leakage(self):
        split=sm.make_split(fixtures(),123)
        split['retrospective_holdout'].append(split['calibration'][0])
        with self.assertRaisesRegex(ValueError,'leakage'):sm.validate_split(split)

    def test_split_rejects_omitted_session(self):
        split=sm.make_split(fixtures(),123);split['calibration'].pop()
        with self.assertRaises(ValueError):sm.validate_split(split)

    def test_split_rejects_old_data_as_fresh(self):
        split=sm.make_split(fixtures(),123)
        split['prospective_holdout'].append(split['retrospective_holdout'].pop())
        with self.assertRaisesRegex(ValueError,'previously'):sm.validate_split(split)

    def test_seed_is_stable_and_bounded(self):
        self.assertEqual(sm.ordered(['b','a','c'],123),sm.ordered(['c','b','a'],123))
        for seed in (True,-1,2**64,1.5):
            with self.assertRaises(ValueError):sm.ordered(['a'],seed)

    def test_no_backend_or_state_fallback(self):
        model=sm.fit([row()],'corun_state_mean')
        self.assertIsNone(sm.predict(model,row(cell='classification/GPU')))
        self.assertIsNone(sm.predict(model,row(ordinal=3)))

    def test_empirical_session_balance_and_reproducibility(self):
        rows=[row('short',3,value=100)]+[row('long',i+3,value=300) for i in range(9)]
        model=sm.fit(rows,'empirical_session_blocks')
        p=sm.predict(model,rows[0]);self.assertEqual(p['point_ns'],200)
        self.assertEqual(p['median_ns'],100)
        draws=[sm.resample(model,rows[0],3,i) for i in range(20)]
        self.assertEqual(draws,[sm.resample(model,rows[0],3,i) for i in range(20)])
        self.assertTrue(set(draws)<={100,300})

    def test_invalid_empirical_draw_rejected(self):
        model=sm.fit([row()],'task_backend_mean')
        with self.assertRaises(ValueError):sm.resample(model,row(),3,0)

    def test_absolute_relative_and_interval_metrics(self):
        rows=[row(value=100),row(ordinal=2,value=200)]
        model=sm.fit([row(value=120)],'global_mean')
        m=sm.evaluate(model,rows)['overall']
        self.assertEqual(m['mae_ns'],50)
        self.assertAlmostEqual(m['wape'],1/3)
        self.assertEqual(m['coverage'],0)

    def test_distribution_p95_not_point_mean(self):
        rows=[row('s1',i+3,value=i+1) for i in range(20)]
        model=sm.fit(rows,'task_backend_mean')
        metric=sm.evaluate(model,rows)['distribution_metrics'][0]
        self.assertEqual(metric['predicted']['p95'],19)
        self.assertEqual(metric['relative_error']['p95'],0)
        self.assertFalse(metric['p95_sample_warning'])

    def test_criteria_need_between_session_variability(self):
        with self.assertRaises(ValueError):sm.calibration_criteria([row()])

    def test_wape_alone_cannot_pass(self):
        criteria=sm.calibration_criteria([row('a',value=100),row('b',value=101)])
        metrics=dict(support_rate=1.,mae_ns=1,wape=.01,coverage=.89)
        self.assertFalse(sm.metric_gate(metrics,criteria))
        metrics['coverage']=.9
        self.assertTrue(sm.metric_gate(metrics,criteria))

    def test_prospective_accepts_only_unseen_later_identity(self):
        plan,model,s= self.prospective()
        self.assertTrue(sm.check_prospective(plan,model,[s]))

    def test_prospective_rejects_seen_session(self):
        plan,model,s=self.prospective();s['session_id']=plan['previously_seen'][0]
        with self.assertRaisesRegex(ValueError,'leakage'):sm.check_prospective(plan,model,[s])

    def test_prospective_rejects_relabelled_replay(self):
        plan,model,s=self.prospective();s['measurement_fingerprint']=plan['seen_measurements'][0]
        with self.assertRaisesRegex(ValueError,'replayed measurement'):sm.check_prospective(plan,model,[s])

    def test_prospective_rejects_stale(self):
        plan,model,s=self.prospective();s['started_utc']='2026-09-19T00:00:00+00:00'
        with self.assertRaisesRegex(ValueError,'stale'):sm.check_prospective(plan,model,[s])

    def test_prospective_rejects_replayed_request(self):
        plan,model,s=self.prospective();s['rows'][0]['request_id']=plan['seen_requests'][0]
        with self.assertRaisesRegex(ValueError,'replayed request'):sm.check_prospective(plan,model,[s])

    def test_prospective_rejects_criteria_change(self):
        plan,model,s=self.prospective();plan['criteria']['wape_max']=.99
        with self.assertRaisesRegex(ValueError,'changed'):sm.check_prospective(plan,model,[s])

    def test_prospective_rejects_runtime_change(self):
        plan,model,s=self.prospective();s['apk_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'identity'):sm.check_prospective(plan,model,[s])

    def test_empty_holdout_not_pass(self):
        plan,model,s=self.prospective()
        with self.assertRaisesRegex(ValueError,'no independent'):sm.check_prospective(plan,model,[])

    def test_generator_noop_and_model_hash_reproducible(self):
        a=self.bundle('a');b=self.bundle('b')
        result=sm.validate_bundle(a)
        self.assertEqual(result,sm.validate_bundle(b))
        self.assertEqual(result['dispatch_count'],0)
        self.assertEqual(result['simulated_completion_count'],0)
        self.assertEqual(result['status'],'SIM-01_INCOMPLETE')

    def test_holdout_values_cannot_change_fit_or_criteria(self):
        a=self.bundle('a');sessions=fixtures()
        for s in sessions:
            if s['purpose']=='holdout':
                for r in s['rows']:r['service_ns']*=100
        with patch('tools.d1_service_model_generate.load_sessions',return_value=(sessions,[])):
            generate(self.root/'source',self.root/'b',123)
        for name in ('candidate_model.json','selection.json','acceptance_criteria.json'):
            self.assertEqual(read(a/name),read(self.root/'b'/name))

    def test_bundle_hash_tamper_rejected(self):
        root=self.bundle();(root/'candidate_model.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'hash'):sm.validate_bundle(root)

    def test_bundle_source_stale_rejected(self):
        root=self.bundle();(self.root/'source/FINAL_REPORT.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'stale'):sm.validate_bundle(root)

    def test_bundle_missing_inventory_rejected(self):
        root=self.bundle();v=read(root/'provenance.json');v['files'].pop('split.json')
        (root/'provenance.json').write_bytes(canonical(v))
        with self.assertRaisesRegex(ValueError,'inventory'):sm.validate_bundle(root)

    def test_bundle_cannot_promote_ready(self):
        root=self.bundle();v=read(root/'simulation_input.json');v['status']='SIM-01_READY'
        self.rehash(root,'simulation_input.json',v)
        with self.assertRaisesRegex(ValueError,'promoted'):sm.validate_bundle(root)

    def test_bundle_baseline_input_drift_rejected(self):
        root=self.bundle();v=read(root/'baseline_bindings.json');v['policies'][0]['input_sha256']='b'*64
        self.rehash(root,'baseline_bindings.json',v)
        with self.assertRaisesRegex(ValueError,'baseline'):sm.validate_bundle(root)

    def test_bundle_cannot_omit_baseline(self):
        root=self.bundle();v=read(root/'baseline_bindings.json');v['policies'].pop()
        self.rehash(root,'baseline_bindings.json',v)
        with self.assertRaisesRegex(ValueError,'baseline inventory'):sm.validate_bundle(root)

    def test_bundle_rejects_fabricated_noop(self):
        root=self.bundle();v=read(root/'no_op_result.json');v['simulated_completion_count']=5
        self.rehash(root,'no_op_result.json',v)
        with self.assertRaisesRegex(ValueError,'fabricated'):sm.validate_bundle(root)

    def test_bundle_rejects_stale_generator(self):
        root=self.bundle();v=read(root/'generation.json')
        path=next(iter(v['generator_sources']));v['generator_sources'][path]='0'*64
        self.rehash(root,'generation.json',v)
        with self.assertRaisesRegex(ValueError,'stale generator'):sm.validate_bundle(root)

    def test_contract_rejects_fallback_unmeasured_thermal_deadline(self):
        root=self.bundle();original=read(root/'simulation_input.json')
        for change in (lambda v:v['constraints'].update(fallback='CPU'),
                       lambda v:v['constraints'].update(thermal_status_allowed=[0,1]),
                       lambda v:v['deadline'].update(values_ns=1000000)):
            v=copy.deepcopy(original);change(v)
            with self.assertRaises(ValueError):sm.validate_contract(v)

    def test_published_schema(self):
        import jsonschema
        root=self.bundle()
        schema=read(Path(__file__).parent/'schemas/service-model-preparation-v1.schema.json')
        jsonschema.Draft202012Validator.check_schema(schema)
        value=read(root/'simulation_input.json');jsonschema.validate(value,schema)
        value['status']='SIM-01_READY'
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(value,schema)


if __name__=='__main__':
    unittest.main()
