import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_bounded_empirical as b
from tools import d1_telemetry_v4 as v
from tools.test_d1_telemetry_v4 import fixture


def templates():
    a=fixture()[0];c=fixture('resident_corun',10000)[0];g=fixture('lifecycle',20000)[0]
    model=g['models'].pop('classification_CPU');model['execution']['backend']='GPU';g['models']['classification_GPU']=model
    return [a,c,g]


class BoundedTests(unittest.TestCase):
    def setUp(self):
        self.t=templates();self.r=dict(sessions=[],requests=[],traces=[]);self.p=b.build_plan(self.t,self.r)

    def validate(self,p):return b.validate_plan(p,self.t,self.r)

    def test_exact_30(self):self.assertEqual(len(self.p['entries']),30);self.assertTrue(self.validate(self.p))
    def test_five_each(self):
        for f in b.FAMILIES:self.assertEqual(sum(e['family']==f for e in self.p['entries']),5)
    def test_five_complete_pairs(self):
        for i in range(5):self.assertEqual(v.paired(*b.pair_manifests(self.p,i))['status'],'matched_plan')
    def test_order_reproducible(self):
        self.assertEqual(self.p,b.build_plan(self.t,self.r))
        orders=[b.pair_manifests(self.p,i)[0]['paired']['order'] for i in range(5)]
        self.assertEqual(sorted([orders.count('AB'),orders.count('BA')]),[2,3])
    def test_changed_seed(self):self.assertNotEqual(self.p,b.build_plan(self.t,self.r,b.SEED+1))
    def test_partial_pair(self):
        p=copy.deepcopy(self.p);p['entries'].pop()
        with self.assertRaises(Exception):self.validate(p)
    def test_no_transition(self):
        p=copy.deepcopy(self.p);p['entries'][0]['family']='transition/classification/CPU_to_GPU'
        with self.assertRaises(Exception):self.validate(p)
    def test_cold_p95_not_gate(self):self.assertFalse(self.p['contract']['population_cold_p95_gate'])
    def test_no_holdout(self):self.assertEqual(self.p['contract']['independent_holdout'],0)
    def test_retry_zero(self):
        sid=self.p['entries'][0]['session_id'];self.assertTrue(b.admit_attempt(self.p,sid,[]))
        with self.assertRaises(ValueError):b.admit_attempt(self.p,sid,[sid])
    def test_global_cap(self):
        ids=[e['session_id'] for e in self.p['entries']]
        with self.assertRaises(ValueError):b.admit_attempt(self.p,ids[0],ids)
    def test_no_replacement(self):
        with self.assertRaises(ValueError):b.admit_attempt(self.p,'replacement',[])
    def test_consumed(self):
        self.r['sessions']=[self.p['entries'][0]['session_id']]
        with self.assertRaises(ValueError):b.build_plan(self.t,self.r)
    def test_memory(self):
        p=copy.deepcopy(self.p);p['contract']['memory']='fixed-headroom'
        with self.assertRaises(Exception):self.validate(p)
    def test_thermal(self):
        p=copy.deepcopy(self.p);next(iter(p['manifests'].values()))['thermal_gate']=1
        with self.assertRaises(ValueError):self.validate(p)
    def test_memory_decision_low_memory(self):
        _,events=fixture();d=next(e['data'] for e in events if e['event']=='memory_admission')
        self.assertEqual(v.memory_decision(d),'admit');d['low_memory']=True
        self.assertEqual(v.memory_decision(d),'android_low_memory')
    def test_no_op(self):
        r=b.dry_run(self.p);self.assertEqual((r['device_commands'],r['dispatches'],r['simulated_completions']),([],0,0))
        self.assertEqual(r['request_count'],480)
    def test_freeze_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'freeze.json').write_text('{}');h=v.digest(r/'freeze.json');(r/'freeze.json').write_text('{"x":1}')
            with self.assertRaises(ValueError):b.verify(r,h)
    def test_crn_no_policy_key(self):
        draws={policy:[b.ticket(1,i) for i in range(5)] for policy in b.contract()['baselines']}
        self.assertTrue(all(d==draws['FIFO_CPU'] for d in draws.values()))
    def test_joint_whole_block(self):
        blocks=[dict(session_id=str(i),receipt={'samples':[dict(active_service_ns=i+1,worker_occupancy_ns=i+2,runtime_state={'invocation':1})]},memory=i,setup=i) for i in range(5)]
        for scenario in ('resample','low','central','high','cold_stress'):
            draw=b.select_joint(blocks,1,0,scenario);self.assertIn(draw,blocks);self.assertEqual(draw['memory'],draw['setup'])
        self.assertEqual(b.select_joint(blocks,1,0,'high')['session_id'],'4')
    def test_joint_pair_crn(self):
        pairs=[dict(pair_id=str(i),A={'session_id':'a'+str(i),'receipt':{'samples':[]}},B={'session_id':'b'+str(i),'receipt':{'samples':[]}}) for i in range(5)]
        p=b.select_pair(pairs,1,0)
        self.assertEqual(p['A']['session_id'][1:],p['B']['session_id'][1:])
        self.assertEqual(p,b.select_pair(pairs,1,0))
        pairs[0].pop('B')
        with self.assertRaises(ValueError):b.select_pair(pairs,1,0)
    def test_paired_bootstrap_inconclusive(self):
        r=b.paired_diagnostics([1]*5,[.5,1,1.5,1,.9])
        self.assertEqual(r['interpretation'],'inconclusive')
    def test_ingest_cross_session_mixing(self):
        entry=self.p['entries'][0];m=self.p['manifests'][entry['session_id']]
        wrong=copy.deepcopy(m);wrong['session_id']='another'
        with patch.object(b.old,'make_block',return_value={'manifest':wrong}):
            with self.assertRaises(ValueError):b.ingest(None,'',entry,self.p,self.r)
    def test_partial_block_catalog(self):
        with self.assertRaises(ValueError):b.approve_blocks([],self.p)
    def test_descriptive_bootstrap_loso(self):
        r=b.descriptive([[i+1,i+2] for i in range(5)])
        self.assertEqual(r,b.descriptive([[i+1,i+2] for i in range(5)]));self.assertEqual(len(r['loso_session_medians']),5)
    def test_deadline_common_scenarios(self):
        d=b.deadline_scenarios([1,2,3],[5,6,7],[0,1],[3,4])
        self.assertEqual(len(d['urgent_warm']),6);self.assertEqual(len(d['normal']),3)
        self.assertLess(min(d['urgent_warm']),max([1,2,3]))


if __name__=='__main__':unittest.main()
