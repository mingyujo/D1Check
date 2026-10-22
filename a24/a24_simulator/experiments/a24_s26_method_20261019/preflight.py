"""Pure operators only. No simulated environment, START, or model fitting."""
import sys,json,math,importlib.util
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1]
sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
from common_transfer import B,np
sys.path.insert(0,str(A/'experiments/a24_parallel_20261018'));sys.path.insert(0,str(A/'experiments/a24_candidate_repair_20261018'));sys.path.insert(0,str(H))
def mod(name,file):
    sp=importlib.util.spec_from_file_location(name,H/file);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
Physics=mod('port_physics_preflight','physics.py').Physics;Policy=mod('port_policy_preflight','policy.py').Policy
parent=json.loads((A/'experiments/a24_parallel_20261018/OPERATION.json').read_text(encoding='utf-8'));model=json.loads((A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json').read_text(encoding='utf-8'));shape=json.loads((H/'SHAPE.json').read_text(encoding='utf-8'));checks=0;maxerr=0
def near(a,b,tol=1e-8):
    global checks,maxerr
    maxerr=max(maxerr,abs(a-b));assert abs(a-b)<tol,(a,b);checks+=1
active=[dict(request_id='q',task='C',route='CPU',stage=1)]
for profile in ('ORIGINAL','UNION','S26_STYLE'):
    p=Physics(model,B.Config(**parent['physics']),profile,shape);s=p.initial(26.)
    # Constant-activity analytical composition is exact for filtered profiles;
    # original heat-dependent power is frozen over each engine integration step.
    if profile!='ORIGINAL':
        one,t=p.transition(s,active,3.);state=s;E=Q=0
        for _ in range(30):state,u=p.transition(state,active,.1);E+=u['increment'];Q+=u['temperature_area']
        near(one['temperature_c'],state['temperature_c']);near(t['increment'],E);near(t['temperature_area'],Q)
        # CPU-union, not task count; adding identical CPU activity costs once.
        two,u=p.transition(s,active+[dict(active[0],request_id='q2')],3.);near(t['increment'],u['increment'])
        end,v=p.transition(one,[],2000.);near(end['temperature_c'],26.,.05);assert v['increment']>=0;checks+=1
    # Pure features and one visible-job forecast; no environment engine.
    class Nominal:
        def vector(self,j,r,s):return [.001,.1 if r=='CPU' else .2,.001,.001,.001]
    q=dict(request_id='q',ordinal=0,task='C',priority='U',scheduled_arrival_ns=35_000_000_000,queue_entry_ns=35_000_000_000,deadline_ns=37_000_000_000)
    snapshot=dict(now_ns=35_000_000_000,queue=[q],owners=[],sensor={**s,'peak_c':26.,'increment_so_far':0.},wait_used_ns=0)
    actor=Policy(Nominal(),p,dict(n=1,supply_stop_s=95,service_stop_s=695),'TEACHER');bank,actions=actor.encode(snapshot)
    assert bank['x'].shape==(36,48) and np.isfinite(bank['x']).all() and sum(bank['mask'])==4;checks+=1
    assert {a.get('wait_ns') for a in actions if a['kind']=='WAIT'}=={20_000_000,50_000_000};checks+=1
    assert all(f['visible_ids']==['q'] and f['no_future_arrivals'] and not f['capped'] for f in bank['forecasts']);checks+=1
    a=actor(snapshot);assert a==actions[int(np.argmin(bank['scores'][:len(actions)]))];checks+=1
output=dict(status='PASS',pure_operator_checks=checks,max_absolute_error=maxerr,environment_START=0,training=0,fit=0)
with (H/'PREFLIGHT.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2)
print(output)
