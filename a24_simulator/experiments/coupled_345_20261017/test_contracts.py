from pathlib import Path
import copy
import json
import math
import unittest
import numpy as np
import torch
from dynamics import Physics,Config,NS,advance_jobs
from controller import Controller,WIDTH,ACTIONS
from engine import run,metrics
from nn_train import Learner,digest
from rewards import labels
ROOT=Path(__file__).resolve().parents[2]
MODEL=json.loads((ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json').read_text())


class ToyTiming:
    def request_context(self,public,q):return {},[]
    def admission(self,*args,**kwargs):return dict(scheduled_to_actual_ns=0,actual_to_queue_ns=0)
    def draw_latent_serial(self,action,state,key):return dict(stages_ns=[10_000_000,500_000_000,10_000_000,5_000_000,5_000_000])


class ToyNominal:
    def vector(self,q,r,state):return [.01,.5,.01,.005,.005]


def case(T=26.):return dict(n=1,service_stop_s=38.,drain_stop_s=40.,temperature_c=T)


def public(T=26.):
    return dict(initial_ap_c=T,service_stop_ns=38*NS,drain_stop_ns=40*NS,observation_end_ns=42*NS,
        requests=[dict(request_id='a',ordinal=0,task='C',priority='U',scheduled_arrival_ns=35*NS,deadline_ns=37*NS)])


def fixed(state):return dict(kind='DISPATCH',request_id=state['queue'][0]['request_id'],route='CPU')


class DynamicsTests(unittest.TestCase):
    def test_no_negative_power_and_hot_execution_slower(self):
        p=Physics(MODEL)
        self.assertLess(p.speed(39,'CPU',1),p.speed(26,'CPU',1))
        self.assertEqual(p.speed(39,'CPU',2),1)
        for T in (26,32,39,60):
            for route in ('CPU','GPU'):
                s,t=p.transition(dict(temperature_c=T,shared_z=1),[dict(task='D',route=route,stage=1)],.1)
                self.assertGreater(t['increment'],0);self.assertTrue(math.isfinite(s['temperature_c']))

    def test_zero_feedback_preserves_steady_power(self):
        p=Physics(MODEL,Config(strength=0))
        s,t=p.transition(dict(temperature_c=40,shared_z=0),[dict(task='C',route='GPU',stage=1)],2.)
        self.assertAlmostEqual(t['increment'],2*p.solo['classification_GPU'])

    def test_measured_cg_dc_pair_preserved_at_zero_feedback(self):
        p=Physics(MODEL,Config(strength=0));_,t=p.transition(dict(temperature_c=26,shared_z=0),[dict(task='C',route='GPU',stage=1),dict(task='D',route='CPU',stage=1)],1)
        self.assertAlmostEqual(t['increment'],MODEL['coefficients_W_proxy'][3])

    def test_idle_tail_and_cooling_exact(self):
        p=Physics(MODEL);state=dict(temperature_c=39,shared_z=1)
        whole,t=p.transition(state,[],2)
        half,a=p.transition(state,[],1);split,b=p.transition(half,[],1)
        self.assertAlmostEqual(whole['temperature_c'],split['temperature_c'])
        self.assertAlmostEqual(t['increment'],a['increment']+b['increment'])
        self.assertAlmostEqual(t['temperature_area'],a['temperature_area']+b['temperature_area'])

    def test_reject_resource_conflict(self):
        with self.assertRaises(ValueError):Physics(MODEL).transition(dict(temperature_c=26,shared_z=0),[dict(task='C',route='CPU',stage=1),dict(task='D',route='CPU',stage=1)],1)

    def test_hot_job_uses_more_wall_time(self):
        p=Physics(MODEL)
        a=run(public(26),ToyTiming(),fixed,p,['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        b=run(public(39),ToyTiming(),fixed,p,['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        self.assertGreater(b['requests'][0]['response_ns'],a['requests'][0]['response_ns'])

    def test_current_phase_progress_conserves_work(self):
        p=Physics(MODEL);r=run(public(39),ToyTiming(),fixed,p,['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        sums=[0.]*5
        for t in r['trace']:
            if t['active']:sums[t['active'][0]['stage']]+=t['dt']*t['speeds']['CPU']
        expected=[.01,.5,.01,.005,.005]
        for a,b in zip(sums,expected):self.assertLess(abs(a-b),5e-9)

    def test_timestep_refinement_is_small(self):
        a=run(public(39),ToyTiming(),fixed,Physics(MODEL,Config(tick_s=.1)),['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        b=run(public(39),ToyTiming(),fixed,Physics(MODEL,Config(tick_s=.05)),['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        self.assertLess(abs(a['requests'][0]['response_ns']-b['requests'][0]['response_ns'])/NS,.02)

    def test_no_latent_remaining_or_future_arrivals_in_public_state(self):
        seen=[]
        def observer(s):
            seen.append(s)
            self.assertNotIn('timing',json.dumps(s));self.assertNotIn('remaining',json.dumps(s));self.assertNotIn('potential',json.dumps(s))
            return fixed(s)
        run(public(),ToyTiming(),observer,Physics(MODEL),['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        self.assertEqual(len(seen[0]['queue']),1)

    def test_nominal_and_actual_use_same_transition_and_objective(self):
        p=Physics(MODEL);c=case(39);actor=Controller(ToyNominal(),p,c,'EXACT')
        q=public(39)['requests'][0];q['queue_entry_ns']=35*NS
        state=dict(now_ns=35*NS,queue=[q],owners=[],sensor=dict(temperature_c=39,shared_z=0,peak_c=39,increment_so_far=0),wait_used_ns=0)
        vectors={('a',r):ToyNominal().vector(q,r,state) for r in ('CPU','GPU')}
        prediction=actor.preview(state,[q],[],vectors,dict(kind='DISPATCH',request_id='a',route='CPU'))
        actual=run(public(39),ToyTiming(),fixed,p,['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        m=metrics(actual,c,p)
        self.assertLess(abs(prediction['energy']-m['increment_J_proxy']),1e-8)
        self.assertLess(np.max(abs(np.array(prediction['costs'])-np.array(m['cost_vector']))),1e-7)

    def test_durable_guard_required(self):
        with self.assertRaises(ValueError):run(public(),ToyTiming(),fixed,Physics(MODEL),['toy'],{})


class NeuralTests(unittest.TestCase):
    def bank(self):
        rng=np.random.default_rng(100);x=rng.normal(size=(ACTIONS,WIDTH)).astype(np.float32);mask=np.zeros(ACTIONS,bool);mask[:2]=True
        return dict(x=x,mask=mask,scores=np.zeros(ACTIONS,np.float32))

    def test_mask_and_evaluation_rng(self):
        l=Learner(100);before=l.action_rng.get_state().clone()
        i,_=l.choose(self.bank(),False)
        self.assertIn(i,(0,1));self.assertTrue(torch.equal(before,l.action_rng.get_state()))

    def test_initial_zero_logits_are_canonical_first_action(self):
        i,_=Learner(101).choose(self.bank(),False);self.assertEqual(i,0)

    def test_optimizer_and_rng_checkpoint_roundtrip(self):
        l=Learner(102);snap=l.snapshot();x=Learner(999);x.restore(snap)
        self.assertEqual(digest(l.net),digest(x.net))
        self.assertEqual(l.choose(self.bank(),True)[0],x.choose(self.bank(),True)[0])

    def test_ppo_learns_a_toy_bandit_and_changes_logits(self):
        l=Learner(103);bank=self.bank();before=digest(l.net)
        for episode in range(20):
            frames=[];cost=[]
            for i in range(12):
                chosen,f=l.choose(bank,True);f['time_ns']=i*NS;frames.append(f);cost.append([float(chosen==1),0,0,0,0])
            l.add(frames,np.array(cost))
        self.assertNotEqual(before,digest(l.net));self.assertGreater(l.steps,0)
        self.assertEqual(l.choose(bank,False)[0],0)

    def test_reward_telescope(self):
        p=Physics(MODEL);c=case(39)
        r=run(public(39),ToyTiming(),fixed,p,['toy'],dict(durable_START_consumed=True,start_id='UNIT_TOY_ONLY'))
        m=metrics(r,c,p);frames=[dict(time_ns=35*NS)]
        _,audit=labels(r,frames,c,p,m);self.assertLess(audit['max_telescope_error'],1e-7)


class BankTests(unittest.TestCase):
    def state(self):
        q=public(39)['requests'][0];q['queue_entry_ns']=35*NS
        return dict(now_ns=35*NS,queue=[q],owners=[],sensor=dict(temperature_c=39,shared_z=.7,peak_c=39,increment_so_far=0),wait_used_ns=0)

    def test_nn_receives_actual_thermal_and_cost_memory_without_fixed_prior(self):
        actor=Controller(ToyNominal(),Physics(MODEL),case(39),'RL',Learner(200),False);actor.waited.add('a')
        action=actor(self.state());call=actor.calls[-1]
        self.assertEqual(np.asarray(call['x']).shape,(ACTIONS,WIDTH))
        self.assertAlmostEqual(call['x'][0][15],1.3,places=6);self.assertAlmostEqual(call['x'][0][16],.7,places=6)
        self.assertEqual(call['fixed_ATC_prior_logit'],0);self.assertEqual(action['kind'],'DISPATCH')

    def test_common_coalescing_is_same_for_every_policy(self):
        for mode in ('EDF','FIFO','RR','ATC','EXACT','RL'):
            actor=Controller(ToyNominal(),Physics(MODEL),case(39),mode)
            self.assertEqual(actor(self.state()),dict(kind='WAIT',wait_ns=50_000_000))

    def test_urgent_infeasible_wait_is_masked(self):
        actor=Controller(ToyNominal(),Physics(MODEL),case(39),'EXACT');actor.waited.add('a')
        state=self.state();state['queue'][0]['deadline_ns']=round(35.1*NS)
        actor(state)
        self.assertFalse(any(a['kind']=='WAIT' for a in actor.calls[-1]['actions']))

    def test_approximation_ablation_changes_only_the_energy_head(self):
        actor=Controller(ToyNominal(),Physics(MODEL),case(39),'APPROX');actor.waited.add('a')
        actor(self.state());call=actor.calls[-1]
        for action,prediction in zip(call['actions'],call['forecasts']):
            if action['kind']=='DISPATCH':
                cell='classification_'+action['route']
                self.assertAlmostEqual(prediction['nominal_additive_energy'],.53*actor.physics.solo[cell])
            self.assertEqual(len(prediction['costs']),5)


if __name__=='__main__':unittest.main()
