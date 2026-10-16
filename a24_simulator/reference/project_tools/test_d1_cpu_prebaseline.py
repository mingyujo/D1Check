import csv
import tempfile
import unittest
from pathlib import Path
import numpy as np
from tools import d1_cpu_prebaseline as m


def rows(identity='dev', role='development', slope=.5):
    return [dict(session=identity, role=role, gap=30, lo_s=t, hi_s=t+5,
                 other_rate_core_s_per_s=.2+i*.01, mean_power_W=.8+slope*(.2+i*.01),
                 latest_power_event_s=t+5.1) for i,t in enumerate(range(-20,30,5))]


class Boundaries(unittest.TestCase):
    def test_development_only_fit_and_scalar_recovery(self):
        r = sum([rows(s) for s in ('a','b','c')], [])
        value=m.fit(r,['a','b','c'])
        self.assertAlmostEqual(value['slope_W_per_core_s_per_s'],.5, places=12)
        r[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'development'):m.fit(r,['a','b','c'])
        with self.assertRaises(ValueError):m.fit(rows('outside'),['a','b','c'])

    def test_future_power_not_used_and_no_constant_CPU_identification(self):
        r=rows(); f=m.feature(r)
        self.assertAlmostEqual(f['contrast_core_s_per_s'],.03)
        r[-1]['latest_power_event_s']=35
        with self.assertRaises(ValueError):m.feature(r)
        r=sum([rows(s) for s in ('a','b','c')],[])
        for p in r:p['other_rate_core_s_per_s']=.3
        with self.assertRaisesRegex(ValueError,'identified'):m.fit(r,['a','b','c'])
        c=dict(power_t=[-21,0,31,35,100],power_w=[1,1,1,999,999])
        with self.assertRaisesRegex(ValueError,'gap'):m.pre_power_bins(c,rows())

    def test_prediction_uses_only_public_pre_and_schedule_and_adds(self):
        r=rows(); public=dict(pre_w=1.,trace_complete=True,cpu_feature=m.feature(r),
                              actual=[dict(start_s=0.,end_s=120.,state='idle')])
        fixed=dict(idle_bias_w=0.,increments={k:0. for k in m.prior.prior.STATES})
        model=dict(slope_W_per_core_s_per_s=.5)
        with self.assertRaises(ValueError):m.predict(public,model,fixed,0,120)
        y=m.predict(public,model,fixed,0,120,opt_in=True)
        poisoned=dict(public,power_w=[9999],ap=[9999],future_CPU=[9999])
        self.assertEqual(y,m.predict(poisoned,model,fixed,0,120,opt_in=True))
        self.assertAlmostEqual(y, m.predict(public,model,fixed,0,35,opt_in=True)+m.predict(public,model,fixed,35,120,opt_in=True))
        self.assertEqual(m.predict(public,model,fixed,0,35,opt_in=True),35.)
        with self.assertRaises(ValueError):m.predict(public,model,fixed,0,121,opt_in=True)
        public['trace_complete']=False
        with self.assertRaises(ValueError):m.predict(public,model,fixed,0,120,opt_in=True)

    def test_complete_eight_cpu_slices_and_missing_overlap_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sched.csv'
            def save(values):
                with p.open('w',newline='',encoding='utf8') as f:
                    w=csv.DictWriter(f,fieldnames=('ts','dur','cpu','activity_class'));w.writeheader();w.writerows(values)
            records=[dict(ts=80*10**9,dur=50*10**9,cpu=k,activity_class='other' if k==0 else 'idle') for k in range(8)]
            save(records); b=m.cpu_bins(p,100*10**9)
            self.assertEqual(len(b),10);self.assertEqual(b[0]['other_rate_core_s_per_s'],1.)
            save(records[:-1])
            with self.assertRaisesRegex(ValueError,'coverage'):m.cpu_bins(p,100*10**9)
            save(records+[records[0]])
            with self.assertRaisesRegex(ValueError,'overlapping'):m.cpu_bins(p,100*10**9)
            records[0]['activity_class']='unknown';save(records)
            with self.assertRaisesRegex(ValueError,'unknown'):m.cpu_bins(p,100*10**9)

    def test_consumed_and_missing_outputs_not_restarted(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);m.write(out/'receipt.json',dict(status='done'))
            with self.assertRaisesRegex(ValueError,'consumed'):m.run(out)
            with self.assertRaises(FileExistsError):m.write(out/'receipt.json',{})

    def test_RMSE_restores_equal_session_weights_to_watts(self):
        r=sum([rows(s) for s in ('a','b','c')],[])
        for p in r:p['mean_power_W'] += .01*((int(p['lo_s'])+20)//5 % 2)
        model=m.fit(r,['a','b','c'])
        residual=[]
        for identity in ('a','b','c'):
            use=[p for p in r if p['session']==identity]
            x=np.array([p['other_rate_core_s_per_s'] for p in use]);y=np.array([p['mean_power_W'] for p in use])
            residual.extend(y-y.mean()-model['slope_W_per_core_s_per_s']*(x-x.mean()))
        self.assertAlmostEqual(model['within_session_pre_RMSE_W'],float(np.sqrt(np.mean(np.square(residual)))),places=14)

    def test_pre_power_is_unchanged_when_only_future_power_changes(self):
        t=np.arange(-21.,121.,.25);w=np.ones(len(t));c=dict(power_t=t,power_w=w)
        a=m.pre_power_bins(c,rows())
        w[t>=35]=99999.
        self.assertEqual(a,m.pre_power_bins(c,rows()))
        model=dict(slope_W_per_core_s_per_s=1.)
        fixed=dict(idle_bias_w=0.,increments={k:0. for k in m.prior.prior.STATES})
        public=dict(pre_w=.01,trace_complete=True,cpu_feature=dict(m.feature(rows()),contrast_core_s_per_s=-1.),
                    actual=[dict(start_s=0.,end_s=120.,state='idle')])
        with self.assertRaisesRegex(ValueError,'nonpositive'):m.predict(public,model,fixed,0,120,opt_in=True)


if __name__=='__main__':unittest.main()
