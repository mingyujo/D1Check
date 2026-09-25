import copy
import math
import unittest

import numpy as np

from tools import d1_energy_thermal as e
from tools import d1_energy_thermal_analysis as a
from tools import d1_arrival_explore as engine
from tools.test_d1_cal03_connection import fixture, request
from tools.test_d1_arrival_explore import settings


def sample(t,i=-1000,v=4000,**kw):
    return dict(mono_ns=int(t*1e9),current_raw=i,voltage_mV=v,current_valid=True,plugged=0,**kw)


def profile():
    return dict(version=e.VERSION,device='toy',model='two-model-explicit-toy',
        evidence='explicit_assumptions',unit_status='synthetic W',sensors=['SKIN'],source='hand calculation',
        states={k:dict(power_w=p,thermal={'SKIN':dict(equilibrium_c=t,tau_s=10)})
                for k,p,t in [('load',4,40),('idle',1,20)]})


class EnergyThermalTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(e.discharge_w(sample(0),1000),4)
        self.assertEqual(e.discharge_w(sample(0),1),.004)

    def test_charging_invalid_and_zero(self):
        for s in [sample(0,i=100),dict(sample(0),plugged=1),dict(sample(0),current_valid=False),sample(0,i=-2147483648),sample(0,v=-1)]:
            self.assertIsNone(e.discharge_w(s,1000))
        self.assertEqual(e.discharge_w(sample(0,i=0),1000),0)

    def test_irregular_integral(self):
        r=e.integrate([sample(0),sample(.5),sample(2)],0,2_000_000_000,1000)
        self.assertAlmostEqual(r['full_energy_j'],8)

    def test_boundary_interpolation_conservation(self):
        ss=[sample(0,i=0),sample(2,i=-1000)]
        a1=e.integrate(ss,0,1_000_000_000,1000)['full_energy_j']
        a2=e.integrate(ss,1_000_000_000,2_000_000_000,1000)['full_energy_j']
        self.assertEqual((a1,a2),(1,3))

    def test_duplicates_and_conflict(self):
        s=sample(0);r=e.integrate([s,s,sample(1)],0,1_000_000_000,1000)
        self.assertEqual((r['duplicates'],r['full_energy_j']),(1,4))
        with self.assertRaisesRegex(ValueError,'conflicting'):e.integrate([s,sample(0,i=-2)],0,1,1)

    def test_gap_and_extrapolation_not_zero_energy(self):
        r=e.integrate([sample(0),sample(4)],0,5_000_000_000,1000)
        self.assertIsNone(r['full_energy_j']);self.assertEqual(r['missing_s'],5)
        r=e.integrate([sample(0),sample(1,i=10)],0,1_000_000_000,1000)
        self.assertIsNone(r['covered_energy_j'])

    def test_sensor_and_device_mismatch(self):
        for kw in [dict(device='other',initial_temperature={'SKIN':20}),dict(device='toy',initial_temperature={'AP':20})]:
            with self.assertRaises(ValueError):e.account([],profile(),model='two-model-explicit-toy',mode='assumption_exploration',planned=0,completed=0,**kw)

    def test_current_models_cannot_claim_measured(self):
        p=profile();p['evidence']='legacy_mobilenet_conditional'
        with self.assertRaisesRegex(ValueError,'current models'):e.account([],p,device='toy',model=p['model'],mode='conditional_prediction',initial_temperature={'SKIN':20},planned=0,completed=0)

    def test_wait_energy_and_continuous_cooling(self):
        p=profile();segments=[dict(start_s=0,end_s=10,state='load'),dict(start_s=10,end_s=20,state='idle')]
        r=e.account(segments,p,device='toy',model=p['model'],mode='assumption_exploration',initial_temperature={'SKIN':20},planned=2,completed=2)
        self.assertEqual(r['energy_j'],50)
        self.assertAlmostEqual(r['trace'][0]['temperature_end']['SKIN'],40-20/math.e)
        self.assertEqual(r['trace'][1]['temperature_start'],r['trace'][0]['temperature_end'])
        self.assertFalse(r['eligible_for_equal_work_comparison']) # service conditions not supplied

    def test_incomplete_is_not_savings_success(self):
        p=profile();r=e.account([],p,device='toy',model=p['model'],mode='assumption_exploration',initial_temperature={'SKIN':20},planned=2,completed=1,service_constraints_met=True)
        self.assertEqual(r['unfinished'],1);self.assertFalse(r['eligible_for_equal_work_comparison']);self.assertFalse(r['optimization_pass'])

    def test_parallel_never_sum_default(self):
        p=profile()
        with self.assertRaisesRegex(ValueError,'unsupported state'):e.account([dict(start_s=0,end_s=1,state='CPU+GPU')],p,device='toy',model=p['model'],mode='assumption_exploration',initial_temperature={'SKIN':20},planned=0,completed=0)

    def test_no_thermal_divergence(self):
        self.assertEqual(e.transition(20,40,10,0),20)
        self.assertAlmostEqual(e.transition(20,40,10,3600),40)
        with self.assertRaises(ValueError):e.transition(20,40,0,1)

    def test_thermal_burden_exact(self):
        self.assertAlmostEqual(e.excess_degree_seconds(20,40,10,10,20),200/math.e)
        self.assertEqual(e.excess_degree_seconds(10,20,10,10,30),0)

    def test_extraction_preserves_run_identity_and_negative_increment(self):
        r=dict(device='A24',run_id='a',condition='cpu',block=1,backend='CPU',threads='1',duty=100,
               model='m',model_sha256='h',fingerprint='f',protocol='toy',runtime_version='v',precision='fp32',completed=1,
               samples=[dict(sample(0,i=-1000),run_id='a'),dict(sample(1,i=-1000),run_id='a'),
                        dict(sample(2,i=-500),run_id='a'),dict(sample(3,i=-500),run_id='a')],
               phases=dict(baseline=(0,1_000_000_000),load=(2_000_000_000,3_000_000_000)))
        p,energy=a.extract(r)
        self.assertEqual(p[0]['run_id'],'a')
        self.assertEqual(energy[1]['incremental_vs_pre_runtime_baseline_j'],-2)

    def test_conditional_support_limits(self):
        p=profile();p.update(evidence='legacy_mobilenet_conditional',model='mobilenet_v1_1.0_224_float',supported_state_sequence=['load'])
        p.update(fingerprint='toy-fp',model_sha256='toy-hash',condition='fixed')
        p['states']['load'].update(identified=True,max_observed_duration_s=10)
        p['states']['load']['thermal']['SKIN'].update(observed_min_c=20,observed_max_c=50)
        kw=dict(device='toy',model=p['model'],mode='conditional_prediction',initial_temperature={'SKIN':20},planned=1,completed=1,
                scope={k:p[k] for k in ('fingerprint','model_sha256','condition')})
        self.assertGreater(e.account([dict(start_s=0,end_s=10,state='load')],p,**kw)['energy_j'],0)
        with self.assertRaisesRegex(ValueError,'duration'):e.account([dict(start_s=0,end_s=11,state='load')],p,**kw)
        with self.assertRaisesRegex(ValueError,'duration'):e.account([dict(start_s=0,end_s=6,state='load'),dict(start_s=6,end_s=12,state='load')],p,**kw)
        with self.assertRaisesRegex(ValueError,'fingerprint'):e.account([],p,**dict(kw,scope={}))
        p['states']['load']['identified']=False
        with self.assertRaisesRegex(ValueError,'unidentified'):e.account([dict(start_s=0,end_s=10,state='load')],p,**kw)

    def test_fit_known_curve_session_unit(self):
        data=[]
        for start in (20,21,22):
            ts=np.linspace(0,60,61);data.append(dict(t=ts,y=30+(start-30)*np.exp(-ts/10),base=20))
        fit=a.fit_phase(data)
        self.assertLess(abs(fit['tau_s']-10),1);self.assertLess(fit['train_mse_c2'],.01)
        flat=[dict(t=d['t'],y=np.full(61,20.),base=20) for d in data]
        self.assertFalse(a.fit_phase(flat)['identified'])

    def test_engine_adapter_preserves_output_and_release(self):
        c,v=fixture();r=engine.simulate(c,v,[request(),request('b',arrival=31,ordinal=1)],policy='CPU_URGENT',settings=settings(),seed=7,horizon_ns=400)
        before=copy.deepcopy(r);ss=e.ledger_segments(r,400)
        self.assertEqual(before,r);self.assertEqual(ss[-1]['end_s'],400/1e9)
        cb=next(s for s in ss if s['start_s']==64/1e9)
        self.assertIn('callback',cb['state']);self.assertEqual(cb['waiting'],1)
        self.assertEqual(r['ledger'][1]['dispatch_ns'],70)

    def test_unfinished_adapter_keeps_busy(self):
        c,v=fixture();r=engine.simulate(c,v,[request()],policy='CPU_URGENT',settings=settings(),seed=7,horizon_ns=25)
        self.assertIn('execute',e.ledger_segments(r,25)[-1]['state'])


if __name__=='__main__':unittest.main()
