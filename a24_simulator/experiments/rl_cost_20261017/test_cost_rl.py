"""Pure new-policy/reward contracts; no environment or optimizer update."""
import os,sys,json,copy,ast
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
sys.path[:0]=[str(HERE),str(ROOT/'src'),str(ROOT/'experiments/competition_cost_20261017')]
import lab_backend as L
L.runtime_guard.OWN_TOKENS+=('s26-multiresource-','rl_cost_20261017','rr_20261017')
import numpy as np
from rl_policy import protected_bank,cost_powers,CONFIG,NS
from rewards import interval_energy,make_costs,SPEC
import state_cost as C
from relative_drain import exclusive

def run():
    reg=L.read(ROOT/'models/registration.json')
    L.runtime_guard.process_guard(Path(__file__).resolve(),reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
    checks=[]
    def ok(value,name):
        if not value:raise AssertionError(name)
        checks.append(name)
    for file in HERE.glob('*.py'):ast.parse(file.read_text(encoding='utf-8'));checks.append('AST '+file.name)
    queue=[dict(request_id='c0',task='C',priority='U',ordinal=0,scheduled_arrival_ns=0,queue_entry_ns=0,deadline_ns=2*NS),
           dict(request_id='d1',task='D',priority='N',ordinal=1,scheduled_arrival_ns=0,queue_entry_ns=0,deadline_ns=5*NS)]
    estimates={q['request_id']:{r:dict(occupancy_ns=int(o*NS),response_ns=int(.9*o*NS),energy_proxy_j=.5)
                              for r,o in (('CPU',.2 if q['task']=='C' else .6),('GPU',.25 if q['task']=='C' else .8))} for q in queue}
    obs=dict(now_ns=100_000_000,queue=queue,owners={},estimates=estimates,last_release_ns={},
             history={'planned_U':1,'planned_N':1},wait_used_ns=0,waited_request_ids=[],horizon_ns=180*NS,alpha=.95,heat_weight=.5,
             sensor=dict(AP_c=27.,power_w=1.2,age_s=0.,recent_activity={'CPU':0.,'GPU':0.,'NPU':0.},ap_slope_c_s=0.,power_slope_w_s=0.))
    powers=cost_powers();gains={k:.1*v for k,v in powers.items()};saved=copy.deepcopy(obs)
    bank=protected_bank(obs,powers,gains)
    ok(obs==saved,'no public mutation')
    ok(not np.any(bank['mask']&~bank['physical_mask']),'physical mask never expanded')
    for task in ('C','D'):
        routes={bank['actions'][i]['route'] for i in np.flatnonzero(bank['mask'][:72]) if queue[int(bank['actions'][i]['request_id'][-1])]['task']==task}
        ok(routes=={'CPU','GPU'},'loose '+task+' both CPU/GPU')
    ok(not any(bank['mask'][i] and bank['actions'][i].get('route')=='NPU' for i in range(72)),'no NPU')
    imminent=copy.deepcopy(obs);imminent['now_ns']=int(1.7*NS)
    protected=protected_bank(imminent,powers,gains)
    ok(not protected['mask'][72:75].any(),'urgent excludes voluntary WAIT')
    ok(all(protected['actions'][i].get('request_id')=='c0' for i in np.flatnonzero(protected['mask'])),'urgent focus')
    fake=copy.deepcopy(obs);fake['future_sampled_duration_ns']=10**15
    other=protected_bank(fake,powers,gains)
    ok(np.array_equal(bank['features'],other['features']) and np.array_equal(bank['mask'],other['mask']),'future extras cannot influence action bank')
    ok(CONFIG['goal_service_alpha']==.95,'explicit non-100-percent learning target')
    model=L.read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
    for owners,name in [([], 'idle'),([dict(task='C',route='GPU',start_s=.2,end_s=1.1)],'solo'),
         ([dict(task='C',route='GPU',start_s=.2,end_s=1.1),dict(task='D',route='CPU',start_s=.6,end_s=1.5)],'measured overlap'),
         ([dict(task='D',route='GPU',start_s=.2,end_s=1.1)],'unmeasured transfer')]:
        windows=[(0.,.2),(.2,.2),(.2,.7),(.7,1.3),(1.3,3.)]
        pieces=interval_energy(owners,windows,model,3.)
        expected=C.observe(exclusive(owners,0.,3.),0.,3.,model)['increment_J_proxy']
        ok(abs(pieces.sum()-expected)<1e-10,'causal energy telescope '+name)
        ok(pieces[1]==0.,'zero duration '+name)
    owners=[dict(task='C',route='GPU',start_s=.2,end_s=1.1)]
    tail=interval_energy(owners,[(1.1,2.)],model,3.)[0]
    ok(tail>0,'causal tail not reset at action')
    row={**queue[0],'deadline_ns':NS,'response_ns':int(1.3*NS)}
    summary=dict(requests=[row],gantt=owners,AP=dict(t_s=[0.,1.,3.],ap_c=[26.,26.2,26.]))
    case=dict(n=1,work_window=[0.,3.],observation_end_s=3.)
    frames=[dict(time_ns=0),dict(time_ns=0),dict(time_ns=NS)]
    costs,counts,proof=make_costs(summary,frames,case,model,26.)
    ok(costs.shape==(3,5) and np.isfinite(costs).all(),'five dense costs incl duplicate actor time')
    ok(abs(costs[:,2].sum()-1.3)<1e-8,'deadline event and normalized tardiness')
    ok(proof['energy_telescope_error_J_proxy']<1e-10,'dense cost exact observer')
    ok('torch' not in sys.modules,'tests do not execute/import NN')
    return dict(status='PASS',groups=len(checks),tests=checks,environment_START=0,NN_updates=0,
                policy_config=CONFIG,reward_spec=SPEC)

if __name__=='__main__':
    with Path(sys.argv[1]).open('x',encoding='utf-8') as f:json.dump(run(),f,ensure_ascii=False,indent=2)
