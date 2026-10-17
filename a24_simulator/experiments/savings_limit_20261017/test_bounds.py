from pathlib import Path
import math
import sys
import unittest
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from dynamics import Physics,Config
sys.path.insert(0,str(HERE))
from math_bounds import coefficients,work_energy,relaxation,feasibility,observed_vector,solve
from actors import list_plans

MODEL=dict(supported_states=['classification_CPU','classification_GPU','detection_CPU','classification_GPU+detection_CPU'],
    coefficients_W_proxy=[1.,.8,1.2,1.6])


def job(i,task='C',due=37.):
    return dict(request_id=str(i),task=task,priority='U' if i==0 else 'N',queue_entry_ns=35_000_000_000,
        deadline_ns=round(due*1e9),routes={r:dict(stages_ns=[0,int(t*1e9),0,0,0]) for r,t in [('CPU',.5),('GPU',1.)]})


class Contracts(unittest.TestCase):
    def test_shared_allocation(self):
        p=Physics(MODEL);H=p.shared
        for T in [26,32,39,55,80]:
            for stage in range(5):
                for active in [[dict(task='C',route='CPU',stage=stage)],
                               [dict(task='C',route='CPU',stage=stage),dict(task='D',route='GPU',stage=stage)]]:
                    _,x=p.transition(dict(temperature_c=T,shared_z=1.),active,.01)
                    allocated=0.
                    for a in active:
                        f=p.speed(T,a['route'],stage);cell=('classification' if a['task']=='C' else 'detection')+'_'+a['route'];A=p.solo[cell]-H
                        leak=math.exp(min(math.log(3.),.025*(T-26)))
                        allocated+=(A*(.8*f**3+.2*leak)+H/2)*.01
                    self.assertLessEqual(allocated,x['increment']+1e-12)
    def test_coefficients_cover_temperature_and_phases(self):
        p=Physics(MODEL);b=coefficients(p,80)
        for cell,values in b['cells'].items():
            route=cell.rsplit('_',1)[1];A=p.solo[cell]-p.shared
            for T in np.linspace(26,b['temperature_upper'],2001):
                f=p.speed(float(T),route,1);leak=math.exp(min(math.log(3.),.025*(T-26)))
                actual=A*.8*f*f+(A*.2*leak+p.shared/2)/f
                self.assertLessEqual(values['execution'],actual+1e-12)
                self.assertLessEqual(values['execution_free'],actual+1e-12)
                self.assertLessEqual(values['nonexecution'],A*(.8+.2*leak)+p.shared/2+1e-12)
    def test_temperature_upper_invariant(self):
        p=Physics(MODEL);b=coefficients(p,39)
        for T in [26,39,b['temperature_upper']]:
            for stage in range(5):
                n,_=p.transition(dict(temperature_c=T,shared_z=1.),[dict(task='D',route='CPU',stage=stage),dict(task='D',route='GPU',stage=stage)],1.)
                self.assertLessEqual(n['temperature_c'],b['temperature_upper']+1e-12)
    def test_full_prefix_consistency(self):
        p=Physics(MODEL);b=coefficients(p,39);j=job(0)
        for r in ('CPU','GPU'):
            self.assertLessEqual(work_energy(j,r,b,prefix=True),work_energy(j,r,b)+1e-12)
            self.assertLessEqual(work_energy(j,r,b,free=True),work_energy(j,r,b)+1e-12)
    def test_list_enumeration_complete(self):
        for n in range(1,5):
            a=list(list_plans(list(map(str,range(n)))))
            self.assertEqual(len(a),(n+1)*math.factorial(n))
            self.assertEqual(len({(tuple(p['CPU']),tuple(p['GPU'])) for p in a}),len(a))
            for p in a:self.assertEqual(sorted(p['CPU']+p['GPU']),list(map(str,range(n))))
    def test_necessary_demand_accepts_known_schedule(self):
        p=Physics(MODEL);b=coefficients(p,26);jobs=[job(0),job(1,'D')]
        case=dict(drain_stop_s=40.,service_stop_s=38.,temperature_c=26.)
        problem=relaxation(jobs,case,dict(on_time=2,urgent_on_time=1),p,b)
        actual=[dict(request_id=str(i),route='CPU',deadline_ns=37_000_000_000,response_ns=round((35+.5*(i+1))*1e9)) for i in range(2)]
        v=observed_vector(jobs,actual,40)
        self.assertLessEqual(feasibility(problem,v),1e-12)
        answer=solve(problem,'energy',2)
        self.assertIsNotNone(answer['reported_dual_bound'])
        simple=sum(min(work_energy(j,r,b) for r in ('CPU','GPU')) for j in jobs)
        self.assertLessEqual(answer['conservative_lower_bound'],simple+1e-8)
        self.assertGreaterEqual(answer['primal'],simple-1e-8)
    def test_impossible_prefix_is_not_certified_feasible(self):
        p=Physics(MODEL);b=coefficients(p,26)
        problem=relaxation([job(0,due=35.1)],dict(drain_stop_s=40.,service_stop_s=38.,temperature_c=26.),dict(on_time=1,urgent_on_time=1),p,b)
        with self.assertRaises(RuntimeError):solve(problem,'energy',2)
    def test_heat_kernel_latest_deadline_is_optimistic(self):
        for end in (1.,10.,30.):
            for deadline in (.1,.5):
                k=lambda t:12*(1-math.exp(-(end-t)/25))
                for t in np.linspace(0,deadline,101):self.assertGreaterEqual(k(float(t)),k(deadline)-1e-12)


if __name__=='__main__':
    import io
    import hashlib
    import json
    import subprocess
    import scipy
    sys.path.insert(0,str(ROOT/'reference/model_integration'))
    import runtime_guard as G
    G.OWN_TOKENS+=('savings_limit_20261017','coupled_345_20261017')
    guard=G.process_guard(Path(__file__).resolve());volumes=G.free_guard([ROOT,'D:/'])
    stream=io.StringIO();answer=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    attempt=len(list(HERE.glob('TEST_ATTEMPT_*.json')))+1
    value=dict(utc=G.now(),command=sys.argv,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        uncommitted_changes=True,tests=answer.testsRun,successful=answer.wasSuccessful(),output=stream.getvalue(),
        numpy=np.__version__,scipy=scipy.__version__,guard=guard,volumes=volumes,
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'math_bounds.py',HERE/'actors.py']},
        new_environment_START=0,new_model_build=0,new_fit=0)
    G.write_new(HERE/('TEST_ATTEMPT_%02d.json'%attempt),value)
    if answer.wasSuccessful():G.write_new(HERE/'PURE_TEST_RESULT.json',value)
    print(stream.getvalue());sys.exit(0 if answer.wasSuccessful() else 1)
