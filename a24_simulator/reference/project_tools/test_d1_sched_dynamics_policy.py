"""Pure fixtures only: no device plant, fitting, rollout or PPO training."""
import copy
import math
import unittest
import numpy as np
from tools import d1_sched_dynamics_policy as p
from tools import d1_sched_dynamics_cases as c


def request(rid,task='classification',priority='urgent',arrival=35e9,deadline=None,units=1,ordinal=0):
    return dict(id=rid,ordinal=ordinal,task=task,priority=priority,arrival_ns=int(arrival),
        deadline_offset_ns=int(deadline or (1.5e9 if priority=='urgent' else 6e9)),work_units=units)


MEANS=dict(classification_CPU=[1e6,35e6,2e6,1e6,1e6],
    classification_GPU=[1e6,75e6,2e6,1e6,1e6],
    classification_NPU=[1e6,55e6,2e6,1e6,1e6],detection_CPU=[1e6,245e6,2e6,1e6,1e6])


class Fixture:
    """No environment evolution; exposes only fixed public observed state."""
    def __init__(self,npu=True):
        self.now=35_000_000_000;self.npu=npu
        self.lanes={b:None for b in p.BACKENDS}

    def routes(self,q):
        return ('CPU',) if q['task']=='detection' else p.BACKENDS if self.npu else p.BACKENDS[:2]

    def estimate(self,q,b,jobs=()):
        ds=list(MEANS[q['task']+'_'+b]);ds[1]*=q.get('work_units',1)
        return ds

    def feasible(self,jobs):
        labels=[(lane['request']['task'],b) for b,lane in self.lanes.items() if lane]
        for q,b in jobs:
            if b not in self.routes(q) or self.lanes[b] or q['arrival_ns']>self.now:
                return False
            labels.append((q['task'],b))
        return len(labels)==1 or len(labels)==2 and set(labels) in (
            {('classification','GPU'),('detection','CPU')},
            {('classification','NPU'),('detection','CPU')})

    def public(self):
        return dict(now_ns=self.now,lanes=copy.deepcopy(self.lanes),npu_enabled=self.npu,
            observed_responses=0,ap_c=35.,skin_c=32.,reference_ap_c=30.,
            recent_activity=dict(CPU=.2,GPU=.1,NPU=0.))

    def occupy(self,q,b,phase='EXECUTING'):
        self.lanes[b]=dict(request=q,phase=phase,dispatch=self.now-1_000_000,
            estimate_ns=self.estimate(q,b))


class PolicyTests(unittest.TestCase):
    def test_derived_bound_all_64_no_truncation(self):
        dev=Fixture();qs=[request(str(i),ordinal=i) for i in range(64)]
        bank=p.build(dev,qs)
        self.assertEqual(len(bank['actions']),193)
        self.assertEqual(bank['state'].shape,(p.STATE_DIM,))
        self.assertEqual(bank['candidates'].shape,(193,32))
        self.assertEqual(bank['diagnostics']['candidates'],64)
        self.assertEqual(int(bank['mask'].sum()),192)
        self.assertFalse(bank['mask'][-1])

    def test_padding_and_unsupported_routes(self):
        bank=p.build(Fixture(False),[request('d','detection','normal')])
        self.assertEqual(bank['actions'][0][0][1],'CPU')
        self.assertEqual(len(bank['actions']),2)
        self.assertFalse(bank['mask'][1:].any())
        np.testing.assert_array_equal(bank['candidates'][2:],0.)

    def test_output_ready_does_not_release(self):
        dev=Fixture();dev.occupy(request('running'), 'GPU','OUTPUT_READY')
        bank=p.build(dev,[request('other')])
        self.assertFalse(bank['mask'][:3].any())
        self.assertTrue(bank['mask'][3])
        self.assertEqual(p.rule_choice(dev,[request('other')],'ATC'),None)

    def test_same_time_rebuild_can_add_only_measured_pair(self):
        dev=Fixture();q=request('d','detection','normal')
        dev.occupy(request('running'),'GPU')
        bank=p.build(dev,[q])
        self.assertTrue(bank['mask'][0])
        self.assertFalse(bank['mask'][1])
        self.assertEqual(p.rule_choice(dev,[q],'EDD')[0][1],'CPU')

    def test_empty_bank_never_infers(self):
        dev=Fixture();bank=p.build(dev,[])
        self.assertFalse(bank['mask'].any())
        self.assertIsNone(p.Controller().choose(dev,[]))

    def test_future_private_duplicate_and_overflow_rejected(self):
        dev=Fixture()
        for qs in ([request('f',arrival=36e9)],
            [dict(request('p'),actual_duration_ns=123)],
            [request('a'),request('a')],
            [request(str(i),ordinal=i) for i in range(65)]):
            with self.assertRaises(ValueError):p.build(dev,qs)

    def test_past_observation_slopes_and_future_history_rejected(self):
        public=dict(observed_history=[dict(time_ns=30_000_000_000,ap_c=31.,power_w=2.),
            dict(time_ns=35_000_000_000,ap_c=33.,power_w=3.)])
        self.assertEqual(p.observed_slopes(public,35_000_000_000),(.4,.2))
        public['observed_history'].append(dict(time_ns=36_000_000_000,ap_c=34.,power_w=4.))
        with self.assertRaises(ValueError):p.observed_slopes(public,35_000_000_000)

    def test_atc_formula_and_nonidentical_order(self):
        dev=Fixture();qs=[request('c',deadline=.9e9),
            request('d','detection','normal',deadline=.8e9,ordinal=1)]
        bank=p.build(dev,qs)
        mean=(40e6+250e6)/2
        expected=math.log(2)-math.log(.04)-(.9e9-36e6)/(2*mean)
        self.assertAlmostEqual(bank['scores']['c'],expected)
        self.assertEqual(bank['diagnostics']['edd_order'][0],'d')
        self.assertEqual(bank['diagnostics']['atc_order'][0],'c')

    def test_rules_share_exact_physical_bank(self):
        dev=Fixture();qs=[request('c'),request('d','detection','normal',ordinal=1)]
        bank=p.build(dev,qs)
        for rule in p.RULES:
            i=p.rule_index(dev,bank,rule)
            self.assertTrue(bank['mask'][i]);self.assertTrue(dev.feasible(bank['actions'][i]))

    def test_greedy_v17_ready_fallback_is_no_cooling_wait(self):
        dev=Fixture();dev.occupy(request('d','detection','normal'),'CPU')
        jobs=p.rule_choice(dev,[request('c')],'GREEDY_READY_V17',affinity={'classification':'CPU'})
        self.assertTrue(jobs)
        self.assertIn(jobs[0][1],('GPU','NPU'))


class CaseTests(unittest.TestCase):
    def test_deterministic_split_and_window(self):
        for family in c.FAMILIES:
            a=c.make_case('S26','dev',917200101,family,'original',MEANS)
            b=c.make_case('S26','dev',917200101,family,'original',MEANS)
            self.assertEqual(a,b);self.assertLessEqual(len(a['requests']),64)
            self.assertGreaterEqual(min(q['arrival_ns'] for q in a['requests']),35e9)
            self.assertLessEqual(max(q['arrival_ns'] for q in a['requests']),105e9)
        with self.assertRaises(ValueError):c.make_case('S26','dev',917300101,'mixed','original',MEANS)

    def test_declared_changes_only_deadline(self):
        a=c.make_case('S26','dev',917200101,'mixed','original',MEANS)
        b=c.make_case('S26','dev',917200101,'mixed','declared',MEANS)
        for qa,qb in zip(a['requests'],b['requests']):
            self.assertEqual({k:v for k,v in qa.items() if k!='deadline_offset_ns'},
                {k:v for k,v in qb.items() if k!='deadline_offset_ns'})
        self.assertNotEqual(a['request_sha256'],b['request_sha256'])

    def test_device_capacity_normalization_and_execution_only_units(self):
        slow={k:[v*4 for v in ds] for k,ds in MEANS.items()}
        fast=c.make_case('S26','dev',917200101,'mixed','original',MEANS)
        other=c.make_case('A24','dev',917200101,'mixed','original',slow)
        self.assertGreater(other['activity_span_s'],fast['activity_span_s'])
        self.assertEqual(c.scaled_mean([1,2,3,4,5],3),19)
        self.assertEqual({q['work_units'] for q in fast['requests']},{1,2,3})


if __name__=='__main__':unittest.main()
