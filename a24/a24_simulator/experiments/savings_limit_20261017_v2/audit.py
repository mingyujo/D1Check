"""Saved-only independent power/RC/outcome and bound-scope audit."""
from pathlib import Path
import gzip
import json
import math
import subprocess
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'reference/model_integration'),str(ROOT/'experiments/coupled_345_20261017')]
import runtime_guard as G
from dynamics import Physics,Config
sys.path.insert(0,str(HERE))
from math_bounds import coefficients,work_energy,passive_mean,relaxation,observed_vector,feasibility
G.OWN_TOKENS+=('savings_limit_20261017','coupled_345_20261017')


def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];parent=ROOT/op['parent_output']
    G.require((out/'COMPLETE.json').exists() and not (out/'AUDIT.json').exists(),'Completed, unaudited namespace required')
    guard=G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
    checks=0;max_error=0.
    def need(test,reason):
        nonlocal checks
        checks+=1;G.require(test,reason)
    def close(a,b,reason,tol=2e-7):
        nonlocal max_error
        max_error=max(max_error,abs(a-b));need(abs(a-b)<=tol,reason)
    for p in [*op['sources'],*op['input_pins']]:need(G.sha(p['path'])==p['sha256'],'Source/input pin')
    result=read(out/'RESULT.json');terminal=read(out/'COMPLETE.json')
    need(G.sha(out/'RESULT.json')==terminal['result_sha256'],'Terminal result SHA')
    receipts=[json.loads(x) for x in (out/'receipts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts=[x for x in receipts if x['event']=='START'];complete=[x for x in receipts if x['event']=='COMPLETE']
    need(len(starts)==len(complete)==len(result['rows'])==280 and len({r['identity'] for r in starts})==280,'Unique280starts/completions')
    need(not any(x['event']=='FAIL' for x in receipts),'No native failure hidden')
    design=read(op['inputs']['path']);cases={c['id']:c for c in design['fresh']};banks={k:read(out/(k+'.BANK.json.gz'))['jobs'] for k in cases}
    source=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');physics=Physics(source,Config(**op['physics']));c=physics.c;H=physics.shared
    parent_result=read(parent/'RESULT.json');micro={}
    for bound in result['bound_cases']:
        case=cases[bound['case']];jobs=banks[case['id']];coef=coefficients(physics,case['temperature_c'],op['temperature_interval_step_c'])
        need(coef==bound['coefficients'],'Reproducible interval coefficients')
        simple=sum(min(work_energy(j,r,coef) for r in ('CPU','GPU')) for j in jobs)
        close(simple,bound['independent_thermal_linked_work_lower'],'Independent job lower sum')
        ref=bound['reference'];problem=relaxation(jobs,case,ref,physics,coef)
        need(problem['fingerprint']==bound['constraint_sha256'],'Capacity/SLA relaxation matrix bytes')
        old=next(r for r in parent_result['rows'] if r['kind']=='FRESH' and r['case']==case['id'] and r['policy']=='EDF')
        observed=read(parent/(old['label']+'.raw.json.gz'))['result']['requests'];v=observed_vector(jobs,observed,case['drain_stop_s'])
        need(feasibility(problem,v)<=2e-7,'Original EDF satisfies every relaxed constraint')
        close(c.baseline*(case['drain_stop_s']-35)+max(simple-1e-6,bound['energy_MILP']['conservative_lower_bound']),bound['total_energy_lower'],'Saved energy lower bound')
        close(passive_mean(case,physics)+bound['heat_MILP']['conservative_lower_bound'],bound['mean_temperature_lower'],'Saved mean heat lower bound')
        need(bound['total_energy_lower']<=ref['total_J_proxy']+1e-7,'Lower bound below known feasible EDF')
    for row in result['rows']:
        receipt=next(r for r in complete if r['label']==row['label']);raw=out/(row['label']+'.raw.json.gz')
        need(G.sha(raw)==row['raw_sha256']==receipt['raw_sha256'],'Native raw bytes')
        need(G.sha(out/(row['label']+'.json'))==receipt['result_sha256'],'Native summary bytes')
        r=read(raw)['result'];key=row['case'].removeprefix('MICRO_');case=cases[key];byid={j['request_id']:j for j in banks[key]};q=r['requests']
        need(len(q)==(4 if row['case'].startswith('MICRO_') else case['n']),'Planned denominator')
        inc=work_area=0.;peak=case['temperature_c'];rates={j['request_id']:[0.]*5 for j in q if j['dispatch_ns'] is not None}
        for tr in r['trace']:
            dt=(tr['end_ns']-tr['start_ns'])/1e9;T=tr['state']['temperature_c'];z=tr['state']['shared_z'];active=tr['active'];dynamic=0.
            need(len(active)<=2 and len({a['route'] for a in active})==len(active),'One CPU/GPU each')
            mid=(tr['end_ns']+tr['start_ns'])/2
            for a in active:
                j=next(j for j in q if j['route']==a['route'] and j['dispatch_ns'] is not None and j['dispatch_ns']<=mid and (j['available_ns'] is None or mid<j['available_ns']))
                stage=sum(j.get(k) is not None and j[k]<=mid for k in ('execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'))
                need(stage==a['stage'],'Phase reconstructed from outcomes')
                f=max(c.minimum_speed,1/(1+(c.cpu_slope if a['route']=='CPU' else c.gpu_slope)*max(0.,T-c.onset_c))) if stage==1 else 1.
                close(f,tr['speeds'][a['route']],'Actual thermal progress rate')
                rates[j['request_id']][stage]+=f*dt
                cell=('classification' if a['task']=='C' else 'detection')+'_'+a['route'];A=physics.solo[cell]-H
                leak=math.exp(min(math.log(3.),max(-math.log(3.),c.leakage_per_c*(T-c.reference_c))))
                dynamic+=A*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak)
            energy=dynamic*dt+(H*dt if active else H*z*c.idle_tail_s*(-math.expm1(-dt/c.idle_tail_s)))
            close(energy,tr['increment'],'Independent instantaneous power integral')
            close(tr['next_state']['temperature_c']-T,(c.thermal_resistance*energy-(tr['temperature_area']-c.idle_c*dt))/c.thermal_tau_s,'RC energy balance')
            if tr['end_ns']/1e9<=case['drain_stop_s']+1e-9:inc+=energy;peak=max(peak,tr['peak'])
            if tr['end_ns']/1e9<=case['service_stop_s']+1e-9:work_area+=tr['temperature_area']
        for j in q:
            if j['dispatch_ns'] is not None:
                need(j['timing']['stages_ns']==byid[j['request_id']]['routes'][j['route']]['stages_ns'],'Original latent work unchanged')
            if j['available_ns'] is not None:
                for got,w in zip(rates[j['request_id']],j['timing']['stages_ns']):close(got,w/1e9,'Work conservation',3e-8)
        m=row['metrics'];answered=[j for j in q if j['response_ns'] is not None and j['response_ns']/1e9<=case['drain_stop_s']]
        need(len(answered)==len(q)-m['response_missing'],'Missing responses retained')
        need(sum(j['response_ns']<=j['deadline_ns'] for j in answered)==m['on_time'],'On-time all arrivals')
        need(sum(j['priority']=='U' and j['response_ns']<=j['deadline_ns'] for j in answered)==m['urgent_on_time'],'Urgent SLA')
        need(sum(j['available_ns'] is None or j['available_ns']/1e9>case['drain_stop_s'] for j in q)==m['incomplete'],'AVAILABLE denominator')
        close(inc,m['increment_J_proxy'],'Independent total work energy')
        close(c.baseline*(case['drain_stop_s']-35)+inc,m['total_J_proxy'],'Fixed baseline retained')
        close(work_area/(case['service_stop_s']-35),m['mean_AP_c'],'Common-window mean temperature')
        if row['kind']=='MICRO_LIST':
            plan=row['extra']['plan'];need(sorted(plan['CPU']+plan['GPU'])==sorted(j['request_id'] for j in q),'Micro plan covers all4 once')
            micro.setdefault(row['case'],set()).add((tuple(plan['CPU']),tuple(plan['GPU'])))
        if row['kind']=='P0':need(m==next(x['metrics'] for x in parent_result['rows'] if x['kind']=='FRESH' and x['case']==key and x['policy']=='EDF'),'P0 exact metrics')
    need(len(micro)==2 and all(len(x)==120 for x in micro.values()),'Every distinct list plan enumerated')
    G.write_new(out/'AUDIT.json',dict(status='PASS_SAVED_HEADROOM_BOUND_AND_NATIVE_AUDIT',checks=checks,max_absolute_difference=max_error,
        command=sys.argv,utc=G.now(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),uncommitted_changes=True,
        result_sha256=G.sha(out/'RESULT.json'),guard=guard,new_environment_START=0,new_optimization=0,
        scope='analytic conservative inequalities + HiGHS reported dual bound with margin; micro optimality only over120 specified list plans, not continuous global optimum'))
    print(json.dumps(dict(status='PASS',checks=checks,max_error=max_error)))


if __name__=='__main__':main()
