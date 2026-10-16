"""Pure fixtures and registered source/input checks; environment START=0."""
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('thermal_fixture',ROOT/'src/thermal_four_route.py')
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
from fast_thermal import FastThermal

def main(opfile,outfile):
    op=json.loads(Path(opfile).read_text(encoding='utf-8-sig'));checks=[]
    for p in op['pins']:
        b=Path(p['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==p['sha256'];assert len(b)==p['bytes']
    checks.append('exact source/input/checkpoint/model pins')
    for p in HERE.glob('*.py'):compile(p.read_bytes(),str(p),'exec');ast.parse(p.read_bytes())
    checks.append('all Python AST/compile without execution')
    parent=(ROOT/'src/interactive_kernel.py').read_text(encoding='utf-8')
    expected=parent.replace('frozen_policy(copy.deepcopy(public))','frozen_policy(public)')
    expected=expected.replace('decisions.append({"time_ns": now, "public_state": public, "public_state_sha256": digest(public), "action": copy.deepcopy(action)})',
        'decisions.append({"time_ns": now, "public_state": {k:v for k,v in public.items() if k != "past_activity"}, "public_state_sha256": digest({k:v for k,v in public.items() if k != "past_activity"}), "public_state_hash_scope": "public fields excluding cumulative past_activity; exact NN inputs separately saved", "action": copy.deepcopy(action)})')
    assert expected==(HERE/'kernel_long.py').read_text(encoding='utf-8');checks.append('exact two kernel logging/copy changes; physics unchanged')
    before=(ROOT/'experiments/protected48_v2_20261016/protected_policy.py').read_text(encoding='utf-8')
    assert before.replace('public_state=copy.deepcopy(state),','public_state=copy.deepcopy({k:v for k,v in state.items() if k != "past_activity"}),')==(HERE/'protected_policy_long.py').read_text(encoding='utf-8');checks.append('policy logging-only derivative')
    before=(ROOT/'src/policy_bridge_four_route.py').read_text(encoding='utf-8')
    after=(HERE/'bridge_long.py').read_text(encoding='utf-8')
    assert before.replace('512','16384')==after;checks.append('queue validation only; shortlist/NN unchanged')
    data=json.loads((HERE/'INPUTS_V2.json').read_text(encoding='utf-8-sig'));base=data['cases'][0]['input']['requests'];prefix=[]
    for c in data['cases']:
        rows=c['input']['requests'];assert len(rows)==c['n'] and c['n']%48==0
        assert rows[:len(prefix)]==prefix;prefix=rows
        assert sum(r['profile'].startswith('C_') for r in rows)==c['n']//2
        assert sum(r['priority']=='U' for r in rows)==c['n']//4
        assert all(r['deadline_s']>r['arrival_s'] and r['ordinal']==i for i,r in enumerate(rows))
        assert c['work_window'][1]==c['service_stop_s'] and c['observation_end_s']==c['service_stop_s']+180
        checks.append('prefix/composition/clock/window N='+str(c['n']))
    model=dict(status='EXPERIMENTAL_FIT',config=dict(cooling_tau_s=600.,activity_tau_s=30.,pre_slope_tau_s=30.,ridge=.1),domains=['D'],
               domain_activity_support={'D':list(T.STATES)},coefficients=[29.,.2,.4]+[.1*(i+1) for i in range(8)])
    owners=[dict(start_s=2.,end_s=5.,request_id='a',task='C',route='GPU'),dict(start_s=3.,end_s=6.,request_id='b',task='D',route='CPU'),
            dict(start_s=30.,end_s=40.,request_id='c',task='C',route='CPU'),dict(start_s=35.,end_s=39.,request_id='d',task='D',route='GPU')]
    for ambient in (None,24.):
        for slope in (False,True):
            public=dict(session_id='fixture',device='A24',compatibility={'ap_activity_domain':'D'},initial_ap_c=28.,initial_ap_time_s=0.,forecast_origin_s=0.,ambient_c=ambient)
            if slope:public['observations']=[dict(channel='AP',initial_eligible=True,hi_s=-10.,t_s=-10.,ap_c=27.),dict(channel='AP',initial_eligible=True,hi_s=0.,t_s=0.,ap_c=28.)]
            fast=FastThermal(T,T.predict,public,model);maximum=0.
            for t in (1.,2.,3.,3.5,5.,6.,10.,30.,35.,36.,39.,40.,100.,1000.,10000.):
                past=[{**r,'end_s':min(t,r['end_s'])} for r in owners if r['start_s']<t]
                s={**public,'owner_intervals':past,'activity_coverage_s':[0.,t]}
                a=T.predict(model,s,[t],include_features=True);b=fast.predict(model,s,[t]);maximum=max(maximum,abs(a['ap_c'][0]-b['ap_c'][0]))
                assert maximum<1e-10 and a['local_coefficients']==b['local_coefficients']
            checks.append(dict(test='streaming AP exact through10000s',ambient=ambient,past_slope=slope,max_error=maximum))
    result=dict(status='PASS',checks=checks,check_groups=len(checks),operation_sha256=hashlib.sha256(Path(opfile).read_bytes()).hexdigest(),environment_START=0,NN_training=0)
    with Path(outfile).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main(*sys.argv[1:])
