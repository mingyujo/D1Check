"""First-action counterfactuals with an identical observable past.

This is diagnostic replay, not an online policy.  Only the first dispatch is
forced; every subsequent decision is the frozen THERMAL_ENERGY_PC_V1 rule.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import json
import math
import time
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_offline_search as offline
from tools import d1_arrival_thermal_feedback as feedback
from tools import d1_arrival_thermal_feedback_batch as frozen
from tools import d1_cal03_connection as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'docs/results/arrival_information_check_01/CONFIG.json'
OUTPUT = ROOT/'docs/results/arrival_information_check_01/run_v2'
PRIOR = ROOT/'docs/results/arrival_offline_search_01/run_v1/witnesses.csv'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')


def write_csv(path, rows):
    base.require(bool(rows), 'empty diagnostic CSV')
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def branch_inputs(case, branch, vectors):
    original=batch.workload(case['scenario'], 'evaluation')[:case['first_request_count']]
    requests=[copy.deepcopy(original[i]) for i in branch['request_indices']]
    if branch.get('move_second_to_original_index_1_time'):
        requests[1]['arrival_ns']=original[1]['arrival_ns']
        requests[1]['ordinal']=1
    actual=vectors
    if branch['realization'] != 'frozen':
        task,backend,factor=branch['realization'].split('_')
        base.require(task=='detection' and backend in ('CPU','GPU') and factor=='x1.25',
                     'unfrozen stress realization')
        actual=copy.deepcopy(vectors)
        for priority in ('normal','urgent'):
            for cell in actual['cells'][f'{task}_{backend}_{priority}']:
                cell['durations_ns']=[int(round(d*1.25)) for d in cell['durations_ns']]
    return requests,actual


def visible_snapshot(decision, config, settings, model):
    head=decision['queue'][0]
    costs={}
    for backend in ('CPU','GPU'):
        cell=config['cells'][f"{head['task']}_{backend}_{head['priority']}"]
        costs[backend]={
            'response_median_ns':cell['joint']['dispatch_to_response_ns']['median_ns'],
            'lane_median_ns':cell['joint']['dispatch_to_lane_ns']['median_ns'],
            'predicted_single_power_w':model['predicted']['power_w'][f"{head['task']}:{backend}"],
            'predicted_single_ap_equilibrium_c':model['predicted']['ap_equilibrium_c'][f"{head['task']}:{backend}"],
        }
    return dict(now_ns=decision['now_ns'],arrived_queue=decision['queue'],lanes=decision['lanes'],
                remaining_deadline_ns={q['id']:q['arrival_ns']+q['deadline_offset_ns']-decision['now_ns']
                                       for q in decision['queue']},
                current_modeled_ap_c=decision['current_ap_c'],estimated_costs=costs,
                assumed_tau_s=model['tau_s'],assumed_ap_limit_c=model['ap_limit_c'],
                prediction_horizon_ns=decision['candidates'][0]['prediction_horizon_ns'],
                candidates=decision['candidates'],online_selected=decision['selected'],
                online_reason=decision['reason'],decision_ns=settings['decision_ns'],
                record_ns=settings['record_ns'],dispatch_ns=settings['dispatch_ns'])


class FirstAction:
    def __init__(self, backend):
        self.backend=backend
        self.calls=0
        self.snapshot=None

    def __call__(self, config, queue, lanes, now, settings, model, ap):
        decision=feedback.choose(config,queue,lanes,now,settings,model,ap)
        self.calls+=1
        if self.calls==1:
            base.require(now==0 and len(queue)==1 and queue[0]['arrival_ns']==0,
                         'first-action observation boundary changed')
            self.snapshot=visible_snapshot(decision,config,settings,model)
            head=decision['queue'][0]
            candidate=next((c for c in decision['candidates']
                            if c['backend']==self.backend and c['wait_ns']==0),None)
            base.require(candidate is not None, 'forced backend not a legal immediate action')
            decision['chosen_prediction']=candidate
            decision['selected']=dict(request_id=head['id'],backend=self.backend)
            decision.pop('wait_until_ns',None)
            decision['reason']='diagnostic_first_dispatch_'+self.backend
        return decision


def replay(config,vectors,requests,settings,model,seed,backend):
    provider=FirstAction(backend)
    result=engine.simulate(config,vectors,requests,policy=feedback.POLICY,
                           settings=settings,seed=seed,thermal_model=model,
                           decision_provider=provider)
    base.require(provider.calls>=1 and result['ledger'][0]['backend']==backend,
                 'first dispatch not applied')
    return result,provider.snapshot


def metrics(result):
    value=offline.summary(result)
    return dict(planned=value['planned'],complete=value['complete'],unfinished=value['unfinished'],
                urgent_n=value['urgent_n'],normal_n=value['normal_n'],
                urgent_miss=value['urgent_miss'],normal_miss=value['normal_miss'],
                responses_ms=value['response_by_id'],energy_j=value['energy_j'],
                ap_peak_c=value['ap_peak_c'],ap_exceed_s=value['ap_exceed_s'])


def delta(cpu,gpu):
    base.require(cpu['planned']==gpu['planned'] and cpu['responses_ms'].keys()==gpu['responses_ms'].keys(),
                 'different request denominator')
    return dict(energy_j=cpu['energy_j']-gpu['energy_j'],
                ap_peak_c=cpu['ap_peak_c']-gpu['ap_peak_c'],
                ap_exceed_s=cpu['ap_exceed_s']-gpu['ap_exceed_s'],
                urgent_miss=cpu['urgent_miss']-gpu['urgent_miss'],
                normal_miss=cpu['normal_miss']-gpu['normal_miss'],
                unfinished=cpu['unfinished']-gpu['unfinished'],
                response_ms={k:cpu['responses_ms'][k]-gpu['responses_ms'][k]
                             for k in cpu['responses_ms']})


def no_worse(cpu,gpu,tol):
    d=delta(cpu,gpu)
    return (d['urgent_miss']<=0 and d['normal_miss']<=0 and d['unfinished']<=0
            and d['energy_j']<=tol['energy_j'] and d['ap_peak_c']<=tol['ap_c']
            and d['ap_exceed_s']<=tol['ap_exceed_s']
            and all(x<=tol['response_ms'] for x in d['response_ms'].values()))


def svg(path, rows):
    width=1000;height=140+len(rows)*28
    bits=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
          '<rect width="100%" height="100%" fill="white"/>',
          '<text x="20" y="32" font-size="20">첫 행동 CPU−GPU: 같은 관측 과거, 다른 미래</text>',
          '<text x="20" y="56" font-size="13">음수는 CPU 첫 배정의 감소. 120초 기기 전체 에너지와 AP 최고온도; 가정 기반 PC 재생</text>',
          '<line x1="760" y1="70" x2="760" y2="{height-15}" stroke="#555"/>']
    for i,r in enumerate(rows):
        y=84+i*28
        x=760+80*float(r['delta_energy_j'])
        x=max(570,min(965,x))
        color='#097969' if float(r['delta_energy_j'])<0 else '#bd4b37'
        bits.extend([f'<text x="20" y="{y}" font-size="12">{html.escape(r["case"])} / {html.escape(r["branch"])}</text>',
                     f'<line x1="760" y1="{y-4}" x2="{x:.1f}" y2="{y-4}" stroke="{color}" stroke-width="5"/>',
                     f'<text x="790" y="{y+12}" font-size="11">ΔE {float(r["delta_energy_j"]):+.3f} J, ΔAP {float(r["delta_ap_peak_c"]):+.3f} °C</text>'])
    bits.append('</svg>')
    Path(path).write_text('\n'.join(bits),encoding='utf-8')


def evaluate(contract=CONFIG, output=OUTPUT):
    contract=Path(contract);output=Path(output)
    base.require(not output.exists(), 'preserve prior diagnostic output')
    spec=read(contract);source=read(frozen.CONFIG);freeze=frozen.verify(source)
    config=read(frozen.INPUT/'estimates.json');vectors=read(frozen.INPUT/'realizations.json')
    base.require(spec['common_window_ns']==120_000_000_000 and spec['max_simulations']==24,
                 'frozen common-window/budget contract')
    base.require(len(spec['cases'])*len(spec['branches'])*2<=spec['max_simulations'],
                 'simulation budget exceeded')
    output.mkdir(parents=True)
    manifest=dict(contract_sha256=sha(contract),source_config_sha256=sha(frozen.CONFIG),
                  estimates_sha256=sha(frozen.INPUT/'estimates.json'),
                  realizations_sha256=sha(frozen.INPUT/'realizations.json'),
                  prior_witnesses_sha256=sha(PRIOR),engine_sha256=sha(engine.__file__),
                  tool_sha256=sha(__file__),source_commit='b6312857e8ef8d0ba52b748e60c231ff96110a17')
    write_json(output/'SOURCE_MANIFEST.json',manifest)
    started=time.monotonic();comparisons=[];deltas=[];snapshots={};decision_rows=[];realized_rows=[]
    for case in spec['cases']:
        settings=frozen.settings(feedback.POLICY,source,freeze)
        model=frozen.model(next(p for p in source['profiles'] if p['id']==case['profile']),source)
        case_id=f"{case['scenario']}_{case['profile']}_{case['seed']}"
        first_request=batch.workload(case['scenario'],'evaluation')[0]
        for backend in ('CPU','GPU'):
            key=f"{first_request['task']}_{backend}_{first_request['priority']}"
            cell=vectors['cells'][key][engine.keyed_index(case['seed'],first_request['id'],backend)]
            realized_rows.append(dict(case=case_id,backend=backend,
                dispatch_to_lane_no_overlap_ms=sum(cell['durations_ns'])/1e6,
                stage_durations_ms=json.dumps([d/1e6 for d in cell['durations_ns']]),
                scope='posthoc keyed sample, not visible to online decision; concurrent execution can alter actual duration'))
        first_snapshot=None
        for branch in spec['branches']:
            base.require(time.monotonic()-started < spec['wall_seconds'],'diagnostic wall budget exhausted')
            requests,actual=branch_inputs(case,branch,vectors)
            results={};values={}
            for backend in ('GPU','CPU'):
                result,snapshot=replay(config,actual,requests,settings,model,case['seed'],backend)
                base.require(snapshot['online_selected']['backend']==case['online_first_action'],
                             'original online first action changed')
                if first_snapshot is None:first_snapshot=snapshot
                base.require(snapshot==first_snapshot,'future input leaked into first observable snapshot')
                results[backend]=result;values[backend]=metrics(result)
                comparisons.append(dict(case=case_id,branch=branch['id'],first_action=backend,
                    request_count=len(requests),profile=case['profile'],seed=case['seed'],
                    planned=values[backend]['planned'],complete=values[backend]['complete'],
                    unfinished=values[backend]['unfinished'],urgent_n=values[backend]['urgent_n'],
                    normal_n=values[backend]['normal_n'],urgent_miss=values[backend]['urgent_miss'],
                    normal_miss=values[backend]['normal_miss'],
                    responses_ms=json.dumps(values[backend]['responses_ms'],sort_keys=True),
                    energy_j=values[backend]['energy_j'],ap_peak_c=values[backend]['ap_peak_c'],
                    ap_exceed_s=values[backend]['ap_exceed_s']))
                for d in result['decisions']:
                    decision_rows.append(dict(case=case_id,branch=branch['id'],first_action=backend,
                        now_ms=d['now_ns']/1e6,action=d['selected']['backend'] if d['selected'] else 'WAIT',
                        request_id=d['selected']['request_id'] if d['selected'] else '',reason=d['reason']))
            if branch['id']=='original_three':
                baseline=engine.simulate(config,actual,requests,policy=feedback.POLICY,
                    settings=settings,seed=case['seed'],thermal_model=model)
                base.require(metrics(baseline)==values['GPU'], 'forced GPU differs from original online metrics')
                base.require(baseline['ledger']==results['GPU']['ledger'] and
                             baseline['thermal']==results['GPU']['thermal'],
                             'forced GPU differs from original online replay')
            diff=delta(values['CPU'],values['GPU'])
            tol=spec['numeric_tolerance']
            deltas.append(dict(case=case_id,branch=branch['id'],request_count=len(requests),
                cpu_no_worse_all=no_worse(values['CPU'],values['GPU'],tol),
                delta_energy_j=diff['energy_j'],delta_ap_peak_c=diff['ap_peak_c'],
                delta_ap_exceed_s=diff['ap_exceed_s'],delta_urgent_miss=diff['urgent_miss'],
                delta_normal_miss=diff['normal_miss'],delta_unfinished=diff['unfinished'],
                delta_responses_ms=json.dumps(diff['response_ms'],sort_keys=True)))
        snapshots[case_id]=first_snapshot
    base.require(len(comparisons)==spec['max_simulations'],'incomplete branch matrix')
    write_json(output/'first_snapshots.json',snapshots)
    write_csv(output/'branch_metrics.csv',comparisons)
    write_csv(output/'branch_deltas.csv',deltas)
    write_csv(output/'decisions.csv',decision_rows)
    write_csv(output/'posthoc_first_realization.csv',realized_rows)
    with PRIOR.open(encoding='utf-8',newline='') as stream:
        prior=[r for r in csv.DictReader(stream)
               if r['case'].startswith(('queue_','burst_'))
               and r['baseline']==feedback.POLICY and r['delta_ms']=='500'
               and r['objective']=='energy']
    base.require(len(prior)==len(spec['cases']),'prior offline witness missing')
    write_csv(output/'prior_offline_reference.csv',prior)
    svg(output/'branch_deltas.svg',deltas)
    gate=all(r['cpu_no_worse_all'] for r in deltas) and any(
        r['delta_energy_j'] < -spec['numeric_tolerance']['energy_j'] or
        r['delta_ap_peak_c'] < -spec['numeric_tolerance']['ap_c'] for r in deltas)
    write_json(output/'RUN_SUMMARY.json',dict(simulations=len(comparisons),elapsed_s=time.monotonic()-started,
        branch_count=len(deltas),all_first_snapshots_equal_within_case=True,
        first_action_cpu_rule_gate_passed=gate,experiment_ready=False,
        interpretation='diagnostic counterfactual, no probabilities or physical validation'))
    return deltas,gate


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    _,gate=evaluate(args.config,args.output)
    print(json.dumps(dict(output=str(args.output),rule_gate_passed=gate),ensure_ascii=False))
