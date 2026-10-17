"""Pure analytic/LP tests, no request environment or bank restoration."""
from pathlib import Path
import io,json,math,sys,unittest,warnings
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'experiments/coupled_345_20261017'),str(ROOT/'reference/model_integration')]
import runtime_guard as G
from dynamics import Physics,Config
from bounds import envelopes,coefficients,build,lift


class Contracts(unittest.TestCase):
    def setUp(self):
        self.physics=Physics(G.read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'))
        self.upper=G.read(ROOT/'experiments/load_density_20261017/THERMAL_PURE_TEST.json')['refined_invariant_upper_c']
        self.env=envelopes(self.physics,self.upper)

    def test_interval_work_coefficients(self):
        p=self.physics;c=p.c
        for task in ('C','D'):
            for r in ('CPU','GPU'):
                A=p.solo[('classification' if task=='C' else 'detection')+'_'+r]-p.shared
                non,ee=coefficients(p,self.env,task,r)
                for k,(lo,hi,_,_) in enumerate(self.env['modes'][r]):
                    for T in (lo,(lo+hi)/2,hi):
                        f=p.speed(T,r,1);leak=math.exp(c.leakage_per_c*(T-c.reference_c))
                        self.assertLessEqual(ee[k],A*.8*f*f+(A*.2*leak+p.shared/2)/f+1e-12)
                        self.assertLessEqual(non,A*(.8+.2*leak)+p.shared/2+1e-12)

    def test_dual_repair_is_lower_than_primal(self):
        jobs=[dict(request_id=str(i),task=t,priority='U',queue_entry_ns=35_000_000_000,deadline_ns=39_000_000_000,
                   routes={r:dict(stages_ns=[10_000_000,500_000_000,10_000_000,0,10_000_000]) for r in ('CPU','GPU')}) for i,t in enumerate(('C','D'))]
        for thermal in (None,40.):
            p,meta=build(jobs,self.physics,self.env,dict(on_time=2,urgent_on_time=2),40.,thermal)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore');s=p.certificate(5)
            self.assertEqual(s['status'],0)
            self.assertLessEqual(s['lower_bound'],s['primal_objective']+1e-8)
            self.assertLess(p.error(s['x']),1e-6)

    def test_RC_latest_deposition_kernel(self):
        for end in (40,155,430):
            for start in (35,(35+end)/2,end-.1):
                k=lambda t:12*(-math.expm1(-(end-t)/25))/(end-35)
                self.assertGreaterEqual(k(start),k(min(end,start+.05)))

    def test_known_two_lane_trace_lifts_into_relaxations(self):
        p=self.physics;state=dict(temperature_c=26.,shared_z=1.);trace=[];jobs=[];requests=[]
        for i,(task,route) in enumerate((('C','CPU'),('D','GPU'))):
            draw=dict(stages_ns=[0,500_000_000,0,0,0])
            jobs.append(dict(request_id=str(i),task=task,priority='U',queue_entry_ns=35_000_000_000,deadline_ns=39_000_000_000,routes={r:draw for r in ('CPU','GPU')}))
            requests.append(dict(request_id=str(i),task=task,route=route,response_ns=35_500_000_000,available_ns=35_500_000_000,deadline_ns=39_000_000_000,timing=draw))
        for k in range(5):
            active=[dict(task='C',route='CPU',stage=1),dict(task='D',route='GPU',stage=1)]
            nxt,terms=p.transition(state,active,.1)
            trace.append(dict(start_ns=35_000_000_000+k*100_000_000,end_ns=35_000_000_000+(k+1)*100_000_000,state=state,next_state=nxt,active=active,**terms));state=nxt
        nxt,terms=p.transition(state,[],4.5)
        trace.append(dict(start_ns=35_500_000_000,end_ns=40_000_000_000,state=state,next_state=nxt,active=[],**terms))
        result=dict(requests=requests,trace=trace)
        for end in (None,40.):
            problem,meta=build(jobs,p,self.env,dict(on_time=2,urgent_on_time=2),40,end)
            value=lift(jobs,result,p,self.env,problem,meta,40_000_000_000)
            self.assertLess(problem.error(value),1e-7)


if __name__=='__main__':
    G.OWN_TOKENS+=('density_headroom_20261018','load_density_20261017','coupled_345_20261017')
    guard=G.process_guard(Path(__file__).resolve());vol=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
        attempt=HERE/('PURE_TEST_RESULT_V2.json' if (HERE/'PURE_TEST_RESULT.json').exists() else 'PURE_TEST_RESULT.json')
        G.require(not attempt.exists(),'Preserve consumed pure test record')
        G.write_new(attempt,dict(successful=result.wasSuccessful(),tests=result.testsRun,log=log.getvalue(),guard=guard,volumes=vol,
                                new_environment_START=0,new_physical_fit=0,frozen_bank_restores=0,LP_solves=2))
        print(log.getvalue(),flush=True)
        if not result.wasSuccessful():raise SystemExit(1)
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
