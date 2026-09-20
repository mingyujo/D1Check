import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import d1_empirical_plan as e
from tools import d1_telemetry_v4 as v


class EmpiricalPlanTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {'variability': {'cold': {'cv': .45648826656937674}}, 'dropout_upper95': .2492487498202596}
        self.registry = dict(sessions=[], requests=[], traces=[])
        self.pins = {'apk': 'a' * 64}
        self.plan = e.build_plan(self.evidence, self.registry, self.pins)

    def validate(self, p):
        return e.validate_plan(p, self.evidence, self.registry, self.pins)

    def test_valid(self): self.assertTrue(self.validate(self.plan))

    def test_deterministic_seed(self):
        self.assertEqual(self.plan, e.build_plan(self.evidence, self.registry, self.pins))
        self.assertNotEqual(self.plan['entries'], e.build_plan(self.evidence, self.registry, self.pins, 7)['entries'])

    def test_counts_from_cv(self):
        s=self.plan['sizes']
        self.assertEqual(s['minimum_per_family_phase'], 8)
        self.assertEqual(s['recommended_per_family_phase'], 14)
        self.assertEqual(s['p95_one_sided_rank_minimum'], 59)

    def test_consumed_rejected(self):
        self.registry['sessions']=[self.plan['entries'][0]['session_id']]
        p=e.build_plan(self.evidence,self.registry,self.pins)
        with self.assertRaises(ValueError):self.validate(p)

    def test_leakage_rejected(self):
        p=copy.deepcopy(self.plan);p['entries'][-1]['session_id']=p['entries'][0]['session_id']
        with self.assertRaises(ValueError):self.validate(p)

    def test_missing_family(self):
        p=copy.deepcopy(self.plan);p['entries']=[x for x in p['entries'] if x['family']!=e.FAMILIES[0]]
        with self.assertRaises(ValueError):self.validate(p)

    def test_state_missing(self):
        p=copy.deepcopy(self.plan);p['entries'][0]['states'].pop()
        with self.assertRaises(Exception):self.validate(p)

    def test_partial_pair(self):
        p=copy.deepcopy(self.plan);p['entries']=[x for x in p['entries'] if x['family']!='resident_corun']
        with self.assertRaises(ValueError):self.validate(p)

    def test_pair_matched_balanced(self):
        for phase in ('calibration','validation'):
            pairs={}
            for x in self.plan['entries']:
                if x['phase']==phase and x['pair_id'] and not x['reserve']:pairs.setdefault(x['pair_id'],[]).append(x)
            orders=[]
            for arms in pairs.values():
                self.assertEqual(len(arms),2)
                for key in ('seed','task_mix','arrivals_ms','input_schedule','warmup_per_runtime','thermal_gate','pair_order'):
                    self.assertEqual(arms[0][key],arms[1][key])
                orders.append(arms[0]['pair_order'])
            self.assertEqual(orders.count('AB'),orders.count('BA'))

    def test_memory_contract(self):
        p=copy.deepcopy(self.plan);p['entries'][0]['memory_contract']='invented_headroom'
        with self.assertRaises(Exception):self.validate(p)

    def test_thermal_scope(self):
        p=copy.deepcopy(self.plan);p['entries'][0]['thermal_gate']=1
        with self.assertRaises(Exception):self.validate(p)

    def test_threshold_change(self):
        p=copy.deepcopy(self.plan);p['criteria']['p95_relative_drift_max']=.99
        with self.assertRaises(ValueError):self.validate(p)

    def test_no_op(self):
        r=e.dry_run(self.plan)
        self.assertEqual((r['device_commands'],r['dispatches'],r['simulated_completions']),([],0,0))
        self.assertFalse(r['execution_allowed'])

    def test_transition_fail_closed(self):
        self.assertTrue(all(not x['execution_supported'] for x in self.plan['entries'] if x['family'].startswith('transition/')))

    def test_native_resident_pair_contract(self):
        from tools.test_d1_telemetry_v4 import fixture
        templates=[fixture()[0],fixture('resident_corun',base=10000)[0]]
        arms=[x for x in self.plan['entries'] if x['phase']=='calibration' and x['replicate']==0 and x['pair_id']]
        a=e.native_manifest(next(x for x in arms if x['family']=='resident_cpu_serial'),templates)
        b=e.native_manifest(next(x for x in arms if x['family']=='resident_corun'),templates)
        self.assertEqual(v.paired(a,b)['status'],'matched_plan')
        self.assertEqual(len(a['warmup_requests'])+len(a['requests']),24)

    def test_native_transition_cannot_compile(self):
        entry=next(x for x in self.plan['entries'] if not x['execution_supported'])
        with self.assertRaisesRegex(ValueError,'transition'):e.native_manifest(entry,[])

    def test_joint_draw_whole_block(self):
        blocks=[dict(session_id=str(i),setup=i,active=i,memory=i,thermal=0) for i in range(5)]
        for index in range(20):
            r=e.draw_block(blocks,1,index)
            self.assertIn(r,blocks)
            self.assertEqual(r,e.draw_block(blocks,1,index))
            r['setup']=999
            self.assertNotIn(r,blocks)

    def test_joint_recombination_rejected(self):
        original=dict(protocol=e.BLOCK,session_id='one',source_provenance_sha256='a'*64,
                      manifest_sha256='b'*64,manifest={},events=[{}],receipt={'setup':1,'active':2},
                      terminal_outcome='succeeded',interpretation='whole session; setup referenced once per runtime; no independent field sampling')
        with patch.object(e,'make_block',return_value=original):
            self.assertTrue(e.validate_block(original,None,None,None,None))
            for key in original:
                b=copy.deepcopy(original);b[key]='mixed'
                with self.assertRaises(Exception):e.validate_block(b,None,None,None,None)

    def test_empty_dataset_cannot_approve(self):
        with self.assertRaises(ValueError):e.validate_dataset([],self.plan,'calibration',self.registry)

    def test_dataset_leakage(self):
        b={'session_id':self.plan['entries'][0]['session_id']}
        with self.assertRaisesRegex(ValueError,'leaked'):e.validate_dataset([b],self.plan,'validation',self.registry,[b['session_id']])

    def test_smoke_import_rejected(self):
        with patch.object(v,'validate',return_value={}),patch.object(v,'read',return_value={'purpose':'telemetry_smoke'}):
            with self.assertRaises(ValueError):e.make_block(Path('.'),'a','',self.registry)

    def test_cluster_bootstrap_deterministic(self):
        a=e.bootstrap_session_quantiles([[1,2,3],[4,5,6]],repetitions=100)
        self.assertEqual(a,e.bootstrap_session_quantiles([[1,2,3],[4,5,6]],repetitions=100))
        self.assertEqual(a['sessions'],2)

    def test_single_session_not_many_independent_requests(self):
        with self.assertRaises(ValueError):e.bootstrap_session_quantiles([[1]*100])

    def test_freeze_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'freeze.json').write_text('{}')
            expected=v.digest(p/'freeze.json');(p/'freeze.json').write_text('{"changed":true}')
            with self.assertRaises(ValueError):e.verify(p,expected)

    def test_distribution_gate_matching_blocks(self):
        x=[[10,11,12,13,14,15]]*8
        self.assertTrue(e.distribution_gate(x,x,[11,13,15])['passed'])

    def test_distribution_gate_drift_rejected(self):
        a=[[10,11,12]]*8;b=[[20,21,22]]*8
        self.assertFalse(e.distribution_gate(a,b,[11,15,21])['passed'])

    def test_cold_tail_not_identified_by_n8(self):
        x=[[10]]*8
        r=e.distribution_gate(x,x,[10])
        self.assertFalse(r['passed']);self.assertTrue(r['sparse_cold_tail'])


if __name__=='__main__':unittest.main()
