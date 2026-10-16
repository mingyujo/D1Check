"""Causal controller unit tests. No simulate calls, training or device commands."""
import copy
import unittest
import tempfile
from pathlib import Path
import numpy as np
import torch
from tools import d1_list_candidate_rl as x


def tickets():
    return [dict(id='C', task='classification', priority='urgent', ordinal=0, arrival_ns=35_000_000_000, deadline_offset_ns=1_500_000_000),
            dict(id='D', task='detection', priority='normal', ordinal=1, arrival_ns=35_000_000_000, deadline_offset_ns=6_000_000_000)]


def empty():
    return {b: dict(request=None, phase='AVAILABLE', since=35e9, dispatch=None) for b in ('CPU','GPU')}


def controller(policy=x.GREEDY, selector=None, network=None, deterministic=True):
    frozen, case=x.p.inputs(x.p.BUNDLE)
    c=x.Controller(frozen, case['initial'], policy, selector=selector, network=network, deterministic=deterministic)
    for q in tickets():event(c,'arrived',q['id'],35e9,ticket=q)
    c.observe(35e9, empty())
    return c


def event(c, kind, rid, now, backend=None, ticket=None):
    payload=dict(event_seq=c.event_seq+1,event=kind,request_id=rid,at_ns=now,backend=backend)
    if ticket is not None:payload['ticket']=ticket
    c.on_public_event(payload)


class Unit(unittest.TestCase):
    def test_bank_shapes_uniqueness_and_no_forecast_masks(self):
        c=controller();acts=c.bank(tickets(),empty(),35e9);encoded=c.encode(tickets(),empty(),35e9,acts)
        self.assertEqual(len(acts),8)
        self.assertEqual(len({a['signature'] for a in acts}),8)
        self.assertEqual(encoded['state'].shape,(56,));self.assertEqual(encoded['candidates'].shape,(8,28))
        self.assertEqual(encoded['state'].dtype,np.float32)
        self.assertEqual(encoded['mask'].dtype,bool);self.assertTrue(encoded['mask'].all())

    def test_mixed_phase_does_not_cancel_or_double_debit(self):
        pick=lambda c,e,a,q:next(i for i,item in enumerate(a) if item['kind']=='C_GPU_DEFER_D_FULL')
        c=controller(selector=pick);d=c(None,tickets(),empty(),35e9,{},None,None)
        self.assertEqual(d['selected']['backend'],'GPU');self.assertIsNone(c.hold)
        event(c,'dispatch_ns','C',35e9,'GPU')
        event(c,'execution_start_ns','C',35.001e9,'GPU')
        lanes=empty();lanes['GPU']=dict(request=tickets()[0],phase='EXECUTING',since=35.001e9,dispatch=35e9)
        c.observe(35.001e9,lanes);first=c.credit;c.observe(35.001e9,lanes)
        self.assertEqual(first,c.credit);self.assertAlmostEqual(c.credit,.249)
        out=c(None,[tickets()[1]],lanes,35.001e9,{},None,None)
        self.assertEqual(out['reason'],'hold_observer_only');self.assertEqual(out['wait_until_ns'],35.25e9)
        for kind in x.PUBLIC_PHASE_EVENTS[1:]:event(c,kind,'C',35.1e9,'GPU')
        self.assertIsNone(c.hold);self.assertAlmostEqual(c.deferred_seconds,.1)

    def test_journal_seq_and_phase_loss_are_not_silent(self):
        c=controller()
        with self.assertRaisesRegex(ValueError,'missing'):c.on_public_event(dict(event_seq=c.event_seq+2,event='dispatch_ns',request_id='C',backend='GPU',at_ns=35e9))
        c=controller();event(c,'dispatch_ns','C',35e9,'GPU')
        with self.assertRaisesRegex(ValueError,'phase'):event(c,'output_ready_ns','C',35e9,'GPU')

    def test_pair_first_receipt_and_failed_second_preserves_queue(self):
        pick=lambda c,e,a,q:next(i for i,item in enumerate(a) if item['kind']=='PAIR_NOW')
        c=controller(selector=pick);c(None,tickets(),empty(),35e9,{},None,None)
        out=c(None,tickets(),empty(),35e9,{},None,None)
        self.assertIsNone(out['selected']);self.assertEqual(c.pair_cancelled,1)
        c=controller(selector=pick);c(None,tickets(),empty(),35e9,{},None,None)
        event(c,'dispatch_ns','C',35e9,'GPU')
        for kind in x.PUBLIC_PHASE_EVENTS:event(c,kind,'C',35e9,'GPU')
        out=c(None,[tickets()[1]],empty(),35e9,{},None,None)
        self.assertEqual(out['reason'],'PAIR_second_commit');self.assertEqual(out['selected']['request_id'],'D')

    def test_unknown_busy_prediction_keeps_free_gpu_and_l0(self):
        c=controller();lanes=empty()
        lanes['CPU']=dict(request=tickets()[1],phase='EXECUTING',since=35e9,dispatch=35e9)
        c.observe(36e9,lanes);actions=c.bank([tickets()[0]],lanes,36e9)
        encoded=c.encode([tickets()[0]],lanes,36e9,actions)
        self.assertTrue(encoded['mask'][:len(actions)].all())
        self.assertTrue(all(not value['known'] for value in encoded['raw']))
        self.assertEqual(c.choose(encoded,actions,[tickets()[0]]),encoded['base'])
        self.assertEqual(actions[encoded['base']]['kind'],'C_GPU_NOW')

    def test_uniform_network_and_eval_l0_tie(self):
        torch.set_num_threads(1);torch.manual_seed(11)
        network=x.ActorCritic();self.assertEqual(sum(p.numel() for p in network.parameters()),16455)
        c=controller(x.PPO,network=network);a=c.bank(tickets(),empty(),35e9);e=c.encode(tickets(),empty(),35e9,a)
        dist,_=network(torch.from_numpy(e['state'])[None],torch.from_numpy(e['candidates'])[None],torch.from_numpy(e['mask'])[None])
        self.assertTrue(torch.equal(dist.probs,torch.full_like(dist.probs,1/8)))
        self.assertEqual(c.choose(e,a,tickets()),e['base'])

    def test_realized_reward_attribution_and_missing_F_key(self):
        c=controller();c(None,tickets(),empty(),35e9,{},None,None)
        c.snapshots.append(dict(c.snapshots[0],now_ns=36e9))
        row=dict(planned=2,completed=2,peak_ap_c=31.2,energy_j=3.,urgent_service_failure=0,normal_service_failure=0,urgent_p95_ms=300.)
        ref=dict(row,peak_ap_c=31.4,energy_j=4.)
        data,reward,cost,valid=x.episode_targets(c,row,[(35.,30.),(36.,30.2),(180.,31.2)],ref)
        self.assertAlmostEqual(reward.sum(),.2);self.assertAlmostEqual(reward[0],-.2)
        self.assertEqual(cost[0],-1.);self.assertTrue(valid.all())
        incomplete=dict(row,completed=1,peak_ap_c=None,energy_j=None)
        _,_,cost,valid=x.episode_targets(c,incomplete,[],ref)
        self.assertEqual(cost[1],1.);self.assertTrue(valid[2]);self.assertFalse(valid[0]);self.assertFalse(valid[1])

    def test_controller_state_restores_control_and_tensor_bytes(self):
        c=controller();actions=c.bank(tickets(),empty(),35e9)
        first=c.encode(tickets(),empty(),35e9,actions);saved=x.controller_state(c)
        other=controller();x.restore_controller(other,saved)
        second=other.encode(tickets(),empty(),35e9,other.bank(tickets(),empty(),35e9))
        for name in ('state','candidates','mask'):self.assertEqual(first[name].tobytes(),second[name].tobytes())

    def test_c_next_repairs_only_duplicate_slot_and_uses_arrived_FIFO(self):
        frozen,case=x.p.inputs(x.p.BUNDLE)
        c=x.Controller(frozen,case['initial'],feature_variant='head2+C_next')
        now=41e9
        q1=dict(tickets()[0],id='C1',arrival_ns=39.9e9)
        q2=dict(q1,id='C2',arrival_ns=40e9,ordinal=2)
        d=dict(tickets()[1],arrival_ns=35.85e9)
        for q in (q1,q2,d):event(c,'arrived',q['id'],max(now,q['arrival_ns']),ticket=q)
        c.observe(now,empty());q=[q1,q2,d];a=c.bank(q,empty(),now);e=c.encode(q,empty(),now,a)
        q2b=dict(q2,arrival_ns=40.5e9);qb=[q1,q2b,d];ab=c.bank(qb,empty(),now);eb=c.encode(qb,empty(),now,ab)
        self.assertEqual(np.flatnonzero(e['state']!=eb['state']).tolist(),[1])
        self.assertEqual(e['candidates'].tobytes(),eb['candidates'].tobytes())
        self.assertEqual(e['mask'].tobytes(),eb['mask'].tobytes())
        wrong=controller()
        with self.assertRaisesRegex(ValueError,'schema'):x.restore_controller(wrong,x.controller_state(c))

    def test_channel_finite_and_known_F_survives_bad_costs(self):
        c=controller();c(None,tickets(),empty(),35e9,{},None,None)
        row=dict(planned=2,completed=1,peak_ap_c=float('nan'),energy_j=float('inf'),urgent_failure=1,normal_failure=0,urgent_p95_ms=None)
        ref=dict(planned=2,completed=2,peak_ap_c=30.,energy_j=3.,urgent_failure=0,normal_failure=0,urgent_p95_ms=300.)
        data,reward,cost,valid=x.episode_targets(c,row,[],ref)
        self.assertEqual(cost[1],1.);self.assertTrue(valid[2])
        self.assertFalse(valid[0]);self.assertFalse(valid[1]);self.assertFalse(valid[-1])
        self.assertTrue(np.isfinite(data[0]['target']).all())


class PhaseEvidenceTests(unittest.TestCase):
    def test_new_phase_has_no_mutation(self):
        from tools.d1_list_candidate_rl_verify import assert_unconsumed_phase
        with tempfile.TemporaryDirectory(prefix='d1_list_phase_') as directory:
            path=Path(directory)
            self.assertEqual(path.resolve().parent, Path(tempfile.gettempdir()).resolve())
            assert_unconsumed_phase(path, 'representation_before_run.json')
            self.assertEqual(list(path.iterdir()), [])

    def test_consumed_phase_is_rejected_without_overwriting(self):
        from tools.d1_list_candidate_rl_verify import assert_unconsumed_phase
        with tempfile.TemporaryDirectory(prefix='d1_list_phase_') as directory:
            path=Path(directory)
            self.assertEqual(path.resolve().parent, Path(tempfile.gettempdir()).resolve())
            for name in ('observation_repair_before_run.json', 'representation_before_run.json'):
                evidence=path/name;evidence.write_bytes(b'{"consumed":true}\n')
                with self.assertRaises(FileExistsError):assert_unconsumed_phase(path, name)
                self.assertEqual(evidence.read_bytes(), b'{"consumed":true}\n')


if __name__=='__main__':unittest.main()
