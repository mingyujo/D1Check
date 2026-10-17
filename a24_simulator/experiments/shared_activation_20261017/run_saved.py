"""One registered saved-only revaluation; never invokes a simulator or learner."""
from pathlib import Path
import gzip
import hashlib
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
from shared_cost import SharedActivationCost, SPEC
G.OWN_TOKENS+=('shared_activation_20261017','choice_opportunities_20261017','rl_cost_20261017','state_recovery_owner')


def read(path):
    b=path.read_bytes()
    return json.loads(gzip.decompress(b) if path.suffix=='.gz' else b)


def verify(pin):
    path=ROOT/pin['path']
    G.require(path.stat().st_size==pin['bytes'] and G.sha(path)==pin['sha256'],'Pin drift: '+pin['path'])
    return path


def mean(xs):return sum(xs)/len(xs)


def group_rows(rows, scenario):
    out=[]
    for collection in sorted({r['collection'] for r in rows}):
        for policy in sorted({r['policy'] for r in rows if r['collection']==collection}):
            rr=[r for r in rows if r['collection']==collection and r['policy']==policy]
            out.append(dict(collection=collection,policy=policy,conditions=len(rr),
                requests=sum(r['n'] for r in rr),on_time=sum(r['on_time'] for r in rr),
                urgent_on_time=sum(r['urgent_on_time'] for r in rr),mean_AP_c=mean([r['mean_AP_c'] for r in rr]),
                legacy_total_J_proxy=mean([r['legacy_total_J_proxy'] for r in rr]),
                legacy_increment_J_proxy=mean([r['legacy_increment_J_proxy'] for r in rr]),
                **{k:mean([r['scenario_costs'][scenario][k] for r in rr]) for k in (
                    'total_J_proxy','increment_J_proxy','full_episode_increment_J_proxy',
                    'additive_route_J_proxy','identified_pair_credit_J_proxy',
                    'hypothesized_pair_credit_J_proxy','hypothesized_idle_tail_J_proxy',
                    'known_pair_overlap_s','transferred_pair_overlap_s','remaining_tail_J_proxy')}))
    return out


def contrast(rows, a, b, scenario):
    aa={r['case']:r for r in rows if r['policy']==a}
    bb={r['case']:r for r in rows if r['policy']==b}
    G.require(set(aa)==set(bb),'Unpaired policy comparison')
    pairs=[]
    keys=('total_J_proxy','increment_J_proxy','full_episode_increment_J_proxy',
          'additive_route_J_proxy','identified_pair_credit_J_proxy',
          'hypothesized_pair_credit_J_proxy','hypothesized_idle_tail_J_proxy')
    for c in sorted(aa):
        x,y=aa[c],bb[c]
        pairs.append(dict(case=c,**{k:x['scenario_costs'][scenario][k]-y['scenario_costs'][scenario][k] for k in keys},
            on_time=x['on_time']-y['on_time'],urgent_on_time=x['urgent_on_time']-y['urgent_on_time'],
            AP_c=x['mean_AP_c']-y['mean_AP_c']))
    return dict(a=a,b=b,conditions=len(pairs),per_condition=pairs,
                mean_delta={k:mean([r[k] for r in pairs]) for k in keys},
                scenario_parameters_shared_between_policies=True)


def examples(model):
    def o(a,b,task,route):return dict(start_s=a,end_s=b,task=task,route=route)
    # Analytic fixtures only: identical8 jobs, routes, durations, all ready0/due20.
    schedules={
        'SPREAD_SERIAL':[x for i in range(4) for x in (o(3*i,3*i+.3,'C','GPU'),o(3*i+.8,3*i+1.5,'D','CPU'))],
        'CONTIGUOUS_SERIAL':[x for i in range(4) for x in (o(i,i+.3,'C','GPU'),o(i+.3,i+1.,'D','CPU'))],
        'PAIRED':[x for i in range(4) for x in (o(.7*i,.7*i+.3,'C','GPU'),o(.7*i,.7*(i+1),'D','CPU'))]}
    m=SharedActivationCost(model)
    return dict(kind='ANALYTIC_MECHANISM_FIXTURES_NOT_DEVICE_OR_ENGINE_RUNS',
        all_arrivals_s=0,all_deadlines_s=20,job_count=8,unfitted_example_durations_s={'C_GPU':.3,'D_CPU':.7},
        schedules={name:dict(owners=owners,window_cost=m.observe(owners,0,20),episode=m.episode(owners)) for name,owners in schedules.items()})


def run():
    op_path=ENTRY.parent/'OPERATION.json';op=read(op_path);op_sha=G.sha(op_path)
    G.require(op['schema']=='A24-shared-activation-saved-operation-v1' and len(op['schedules'])==72,'Scope')
    for p in [*op['source_pins'],*op['input_pins']]:verify(p)
    for row in op['schedules']:
        verify(row['raw']);verify(row['summary'])
    reg=read(ROOT/'models/registration.json')
    guard=G.process_guard(ENTRY,reg['known_PS_producer_paths'])
    free=G.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];G.require(not out.exists(),'Consumed analysis output; no retry')
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        out.mkdir()
        G.write_new(out/'START.json',dict(utc=G.now(),operation_sha256=op_sha,guard=guard,free=free,
            analysis_operation_START=1,new_environment_START=0))
        try:
            suite=unittest.defaultTestLoader.discover(str(ENTRY.parent),pattern='test_shared_cost.py')
            result=unittest.TextTestRunner(verbosity=1).run(suite)
            G.write_new(out/'PURE_TESTS.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                status='PASS' if result.wasSuccessful() else 'FAIL',operation_sha256=op_sha))
            G.require(result.wasSuccessful(),'Pure contracts failed')
            model=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
            sys.path.insert(0,str(ROOT/'experiments/competition_cost_20261017'))
            import state_cost as C
            from relative_drain import exclusive
            rows=[];checks=0
            for source in op['schedules']:
                raw=read(ROOT/source['raw']['path']);saved=read(ROOT/source['summary']['path']);owners=raw['summary']['gantt']
                G.require(G.sha(ROOT/source['raw']['path'])==saved['raw_sha256'],'Raw/summary binding')
                G.require(len(raw['summary']['requests'])==source['n'],'Request denominator')
                G.require(not any(r.get('end_is_censored_forecast_window') for r in owners),'Censored owner cannot count as full episode')
                old=C.observe(exclusive(owners,0.,max(source['window'][1],max(r['end_s'] for r in owners))),*source['window'],model)
                G.require(abs(old['total_J_proxy']-saved['metrics']['total_J_proxy'])<1e-7,'Legacy compatibility')
                values=[]
                for params in op['scenarios']:
                    engine=SharedActivationCost(model,**params)
                    cost=engine.observe(owners,*source['window']);cost.update(engine.episode(owners))
                    parts=sum(cost[k] for k in ('additive_route_J_proxy','identified_pair_credit_J_proxy',
                        'hypothesized_pair_credit_J_proxy','hypothesized_idle_tail_J_proxy'))
                    G.require(abs(parts-cost['increment_J_proxy'])<1e-8,'Cost decomposition')
                    G.require(abs(cost['baseline_J_proxy']-old['baseline_J_proxy'])<1e-8,'Baseline unchanged')
                    values.append(cost);checks+=2
                metrics=saved['metrics']
                rows.append({k:source[k] for k in ('collection','case','policy','id','window','n')}|dict(
                    raw_sha256=source['raw']['sha256'],on_time=metrics['on_time'],urgent_on_time=metrics['urgent_on_time'],
                    mean_AP_c=metrics['mean_AP_c'],legacy_total_J_proxy=old['total_J_proxy'],
                    legacy_increment_J_proxy=old['increment_J_proxy'],scenario_costs=values))
                checks+=3
            nominal=op['scenarios'].index(op['nominal_parameters'])
            groups=group_rows(rows,nominal);contrasts=[]
            fresh=[r for r in rows if r['collection']=='FRESH12']
            for i,params in enumerate(op['scenarios']):
                comparisons=[contrast(fresh,p,'EDF_CPU_FIRST',i) for p in ('ROLLING_ATC','ROLLING_ATC_RL_COST','FIFO_CPU_FIRST','RR_CPU_FIRST')]
                choice=[r for r in rows if r['collection']=='CHOICE_V2']
                comparisons.append(contrast(choice,'COALESCED_COST','COST_PRIOR',i))
                contrasts.append(dict(parameters=params,comparisons=comparisons,policy_means=group_rows(rows,i)))
            fg=[g for g in groups if g['collection']=='FRESH12']
            spread={}
            for key in ('legacy_total_J_proxy','total_J_proxy','legacy_increment_J_proxy','increment_J_proxy','full_episode_increment_J_proxy'):
                vals=[g[key] for g in fg];spread[key]=dict(min=min(vals),max=max(vals),range=max(vals)-min(vals),range_percent_of_min=100*(max(vals)-min(vals))/min(vals))
            G.write_new(out/'SCHEDULES.json',dict(schema=SPEC['schema'],rows=rows,scenarios=op['scenarios']))
            G.write_new(out/'MECHANISM_EXAMPLES.json',examples(model))
            G.write_new(out/'COMPARISON.json',dict(nominal_parameters=op['nominal_parameters'],policy_means=groups,
                fresh_policy_spread=spread,sensitivity=contrasts,scenario_range_is_not_CI=True,
                no_largest_gap_parameter_selection=True,all_existing_AP_and_service_results_reused=True))
            for p in [*op['source_pins'],*op['input_pins']]:verify(p)
            G.require(G.sha(op_path)==op_sha,'Operation drift')
            G.write_new(out/'COMPLETE.json',dict(status='SAVED_HYPOTHESIS_COST_REVALUATION_COMPLETE',utc=G.now(),
                operation_sha256=op_sha,saved_schedules=len(rows),scenario_settings=len(op['scenarios']),
                decomposition_and_binding_checks=checks,tests=result.testsRun,new_environment_START=0,new_fit=0,NN_updates=0,
                calibrated_energy_validated=False,measured_J=None,physical_policy_superiority_proven=False,
                result_pins=[dict(path=p.name,sha256=G.sha(p),bytes=p.stat().st_size) for p in sorted(out.iterdir())]))
            print(json.dumps(dict(status='COMPLETE',checks=checks,policy_means=groups,spread=spread)),flush=True)
        except BaseException as error:
            G.write_new(out/'FAILURE.json',dict(error=str(error),utc=G.now(),automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':run()
