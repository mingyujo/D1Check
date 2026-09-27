"""Bounded offline enumeration over the existing arrival engine (not an online policy).

Every leaf is an ordinary engine simulation with an explicit decision provider. The
oracle may inspect future *outcomes* while searching; the provider itself receives
only the engine's arrived queue, current lanes, time and current modeled AP.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import time
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_thermal_feedback as feedback
from tools import d1_arrival_thermal_feedback_batch as frozen
from tools import d1_cal03_connection as base
from tools import d1_energy_thermal as thermal

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'docs/results/arrival_offline_search_01/CONFIG.json'
OUTPUT = ROOT/'docs/results/arrival_offline_search_01/run_v1'


class BranchPoint(Exception):
    def __init__(self, actions):
        self.actions = actions


def ordered(queue, now, aging_ns):
    return sorted(queue, key=lambda q: (
        0 if now-q['arrival_ns'] >= aging_ns else 1 if q['priority']=='urgent' else 2,
        q['arrival_ns'] if now-q['arrival_ns'] >= aging_ns else q['arrival_ns']+q['deadline_offset_ns'],
        q['ordinal'], q['id']))


class Script:
    def __init__(self, prefix, step_ns, max_wait_ns):
        self.prefix=prefix
        self.step_ns=step_ns
        self.max_wait_ns=max_wait_ns
        self.index=0

    def __call__(self, config, queue, lanes, now, settings, model, ap):
        base.require(model is not None and ap is not None, 'offline model required')
        head=ordered(queue,now,settings['aging_ns'])[0]
        free=[b for b in ('CPU','GPU') if lanes[b]['request'] is None]
        row=dict(now_ns=now, queue=ordered(queue,now,settings['aging_ns']), lanes=lanes,
                 current_ap_c=ap, candidates=[], selected=None, reason='busy_lanes')
        if not free:
            return row
        actions=list(free)
        if (now-head['arrival_ns'] < self.max_wait_ns and
                now < head['arrival_ns']+head['deadline_offset_ns'] and
                now+self.step_ns < 120_000_000_000):
            actions.append('WAIT')
        if self.index==len(self.prefix):
            raise BranchPoint(actions)
        action=self.prefix[self.index]
        base.require(action in actions, 'scripted action not legal at this decision')
        self.index+=1
        if action=='WAIT':
            row.update(reason='offline_discrete_wait', wait_until_ns=now+self.step_ns)
        else:
            row.update(reason='offline_oracle_assignment',
                       selected=dict(request_id=head['id'],backend=action))
        row['offline_action_index']=self.index-1
        return row


def replay(config, vectors, requests, settings, model, seed, prefix, step_ns, max_wait_ns):
    script=Script(prefix,step_ns,max_wait_ns)
    result=engine.simulate(config,vectors,requests,policy=feedback.POLICY,
                           settings=settings,seed=seed,thermal_model=model,
                           decision_provider=script)
    base.require(script.index==len(prefix), 'unused offline action')
    result['offline_actions']=list(prefix)
    return result


def summary(result):
    rows=result['ledger']
    by_id={r['id']:r for r in rows}
    urgent=[r for r in rows if r['priority']=='urgent']
    normal=[r for r in rows if r['priority']=='normal']
    def misses(group):
        return sum('response_ns' not in r or r.get('late_success',False) for r in group)
    return dict(planned=len(rows), complete=sum(r['status']=='succeeded' for r in rows),
                unfinished=sum(r['status']!='succeeded' for r in rows),
                urgent_n=len(urgent), normal_n=len(normal),urgent_miss=misses(urgent),
                normal_miss=misses(normal),
                urgent_responses_ms=[r.get('response_ns',math.inf)/1e6 for r in urgent],
                normal_responses_ms=[r.get('response_ns',math.inf)/1e6 for r in normal],
                response_by_id={rid:r.get('response_ns',math.inf)/1e6 for rid,r in by_id.items()},
                energy_j=result['thermal']['energy_j'],ap_peak_c=result['thermal']['ap_peak_c'],
                ap_exceed_s=result['thermal']['ap_exceed_s'])


def feasible(candidate, comparator, delta_ms, tol):
    if candidate['unfinished']>comparator['unfinished'] or candidate['urgent_miss']>comparator['urgent_miss'] or candidate['normal_miss']>comparator['normal_miss']:
        return False
    return all(candidate['response_by_id'][rid] <= value+delta_ms+tol['response_ms']
               for rid,value in comparator['response_by_id'].items())


def improvements(candidate, comparator, tol):
    return dict(energy=candidate['energy_j'] < comparator['energy_j']-tol['energy_j'],
                ap=candidate['ap_peak_c'] < comparator['ap_peak_c']-tol['ap_c'])


def dominates(a,b,tol):
    av=[a['unfinished'],a['urgent_miss'],a['normal_miss'],a['energy_j'],a['ap_peak_c'],a['ap_exceed_s'],
        *(a['response_by_id'][k] for k in sorted(a['response_by_id']))]
    bv=[b['unfinished'],b['urgent_miss'],b['normal_miss'],b['energy_j'],b['ap_peak_c'],b['ap_exceed_s'],
        *(b['response_by_id'][k] for k in sorted(b['response_by_id']))]
    ts=[0,0,0,tol['energy_j'],tol['ap_c'],1e-6,*([tol['response_ms']]*(len(av)-6))]
    return all(x<=y+t for x,y,t in zip(av,bv,ts)) and any(x<y-t for x,y,t in zip(av,bv,ts))


def pareto(leaves,tol):
    summaries=[(prefix,summary(result)) for prefix,result in leaves]
    frontier=[]
    def near(x,y,t):
        return x==y or abs(x-y)<=t
    for prefix,value in summaries:
        if any(dominates(other,value,tol) for _,other in summaries):continue
        if any(not dominates(value,other,tol) and not dominates(other,value,tol)
               and near(value['energy_j'],other['energy_j'],tol['energy_j'])
               and near(value['ap_peak_c'],other['ap_peak_c'],tol['ap_c'])
               and near(value['ap_exceed_s'],other['ap_exceed_s'],1e-6)
               and all(near(value['response_by_id'][k],other['response_by_id'][k],tol['response_ms'])
                       for k in value['response_by_id']) for _,other in frontier):continue
        frontier.append((prefix,value))
    return frontier


def search_case(config, vectors, requests, settings, model, seed, *, step_ns, max_wait_ns,
                max_nodes, wall_seconds):
    """Depth-first enumeration, with no pruning or heuristic optimality claims."""
    started=time.monotonic();stack=[()];leaves=[];nodes=0
    while stack and nodes<max_nodes and time.monotonic()-started<wall_seconds:
        prefix=stack.pop();nodes+=1
        try:
            result=replay(config,vectors,requests,settings,model,seed,prefix,step_ns,max_wait_ns)
        except BranchPoint as branch:
            stack.extend(prefix+(a,) for a in reversed(branch.actions))
        else:
            leaves.append((prefix,result))
    return dict(status='complete' if not stack else 'budget_exhausted',nodes=nodes,
                elapsed_s=time.monotonic()-started,unexplored_prefixes=len(stack),leaves=leaves)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_csv(path, rows):
    if not rows:return
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


def thermal_path(case_id, label, result, model):
    """Common-window path from the established occupancy ledger, including idle."""
    energy=0.;ap=model['initial_ap_c'];rows=[]
    for segment in thermal.ledger_segments(result,120_000_000_000):
        state=feedback.state_from_ledger(segment['state'])
        start,end=segment['start_s'],segment['end_s']
        rows.append(dict(case=case_id,name=label,time_s=start,state=state,
                         cumulative_energy_j=energy,ap_c=ap))
        dt=end-start
        energy+=model['realized']['power_w'][state]*dt
        ap=thermal.transition(ap,model['realized']['ap_equilibrium_c'][state],model['tau_s'],dt)
        rows.append(dict(case=case_id,name=label,time_s=end,state=state,
                         cumulative_energy_j=energy,ap_c=ap))
    base.require(math.isclose(energy,result['thermal']['energy_j'],abs_tol=1e-6)
                 and math.isclose(ap,result['thermal']['ap_final_c'],abs_tol=1e-6),
                 'path/accounting mismatch')
    return rows


def request_path(case_id,label,result):
    rows=[]
    for r in result['ledger']:
        rows.append(dict(case=case_id,name=label,request_id=r['id'],priority=r['priority'],
            arrival_ms=r['arrival_ns']/1e6,
            dispatch_ms=r['dispatch_ns']/1e6 if 'dispatch_ns' in r else '',
            output_ready_ms=r['output_ready_ns']/1e6 if 'output_ready_ns' in r else '',
            persist_complete_ms=r['persist_complete_ns']/1e6 if 'persist_complete_ns' in r else '',
            worker_release_ms=r['worker_release_ns']/1e6 if 'worker_release_ns' in r else '',
            lane_available_ms=r['lane_available_ns']/1e6 if 'lane_available_ns' in r else '',
            response_ms=r.get('response_ns',0)/1e6 if 'response_ns' in r else '',
            late=r.get('late_success',''),backend=r.get('backend',''),status=r['status']))
    return rows


def write_svg(path, rows):
    """Static overview; each small case gets its own axis to avoid mixed baselines."""
    cases=list(dict.fromkeys(r['case'] for r in rows))
    width=1100;height=120+len(cases)*210
    bits=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
          '<rect width="100%" height="100%" fill="#fff"/>',
          '<text x="24" y="34" font-size="23" font-family="sans-serif">작은 합성 사례: 공통 120초 에너지와 AP 최고온도</text>',
          '<text x="24" y="60" font-size="13" font-family="sans-serif">미측정 기기 전체 W/AP 가정 · offline 최저 에너지 일정은 응답 제약 미적용 · 사례 간 직접 수치 비교 금지</text>']
    colors={'CPU_URGENT':'#46515b','B2_PC':'#2563eb','B3_SOLO_EFT_PC':'#8b5cf6',
            'THERMAL_ENERGY_PC_V1':'#d97706','OFFLINE_ORACLE':'#059669'}
    for i,case in enumerate(cases):
        group=[r for r in rows if r['case']==case]
        y=95+i*210
        energies=[r['energy_j'] for r in group];temps=[r['ap_peak_c'] for r in group]
        emin=min(energies);emax=max(energies);tmin=min(temps);tmax=max(temps)
        bits.append(f'<text x="24" y="{y}" font-size="17" font-family="sans-serif">{html.escape(case)}</text>')
        for j,r in enumerate(group):
            yy=y+27+j*31;col=colors[r['name']]
            ex=360+400*(r['energy_j']-emin)/(emax-emin or 1)
            tx=850+190*(r['ap_peak_c']-tmin)/(tmax-tmin or 1)
            bits.extend((f'<text x="30" y="{yy+4}" font-size="12" font-family="sans-serif">{html.escape(r["name"])}</text>',
                         f'<line x1="360" y1="{yy}" x2="760" y2="{yy}" stroke="#ddd"/>',
                         f'<circle cx="{ex:.1f}" cy="{yy}" r="5" fill="{col}"/>',
                         f'<text x="770" y="{yy+4}" font-size="12" font-family="sans-serif">{r["energy_j"]:.3f} J</text>',
                         f'<circle cx="{tx:.1f}" cy="{yy}" r="5" fill="{col}"/>',
                         f'<text x="1042" y="{yy+4}" font-size="11" font-family="sans-serif">{r["ap_peak_c"]:.2f}°</text>'))
    bits.append('</svg>')
    Path(path).write_text('\n'.join(bits),encoding='utf-8')


def evaluate(contract=CONFIG, output=OUTPUT):
    contract=Path(contract);output=Path(output)
    base.require(not output.exists(), 'preserve prior output')
    spec=read(contract);original=read(frozen.CONFIG);freeze=frozen.verify(original)
    estimates=read(frozen.INPUT/'estimates.json');vectors=read(frozen.INPUT/'realizations.json')
    base.require(spec['common_window_ns']==120_000_000_000 and
                 spec['online_comparators']==original['compared_policies'], 'frozen comparison contract')
    base.require(spec['wait_step_ns']==250_000_000 and spec['max_offline_wait_ns']==500_000_000,
                 'discrete action contract')
    base.require(spec['question_b_max_per_request_response_loss_ms']==[0,250,500], 'research deltas')
    output.mkdir(parents=True)
    source=dict(contract_sha256=sha(contract),source_config_sha256=sha(frozen.CONFIG),
                estimates_sha256=sha(frozen.INPUT/'estimates.json'),
                realizations_sha256=sha(frozen.INPUT/'realizations.json'),
                b2_freeze_sha256=sha(frozen.FREEZE),engine_sha256=sha(engine.__file__),
                search_sha256=sha(__file__),created_before_result='CONFIG.json frozen before evaluation',
                assumption='whole-device W and AP profile are unmeasured stress assumptions')
    (output/'SOURCE_MANIFEST.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    comparisons=[];witnesses=[];actions=[];paths=[];thermal_paths=[]
    selected_paths=[];selected_thermal_paths=[];selected_actions=[];frontier_rows=[]
    for case in spec['cases']:
        name=case['scenario'];seed=case['seed'];profile=case['profile']
        requests=batch.workload(name,'evaluation')[:case['request_count']]
        m=frozen.model(next(p for p in original['profiles'] if p['id']==profile),original)
        baselines={}
        for policy in spec['online_comparators']:
            s=frozen.settings(policy,original,freeze)
            baselines[policy]=engine.simulate(estimates,vectors,requests,policy=policy,
                settings=s,seed=seed,thermal_model=m)
        offline_settings=frozen.settings(feedback.POLICY,original,freeze)
        found=search_case(estimates,vectors,requests,offline_settings,m,seed,
            step_ns=spec['wait_step_ns'],max_wait_ns=spec['max_offline_wait_ns'],
            max_nodes=case['max_nodes'],wall_seconds=case['wall_seconds'])
        case_id=f'{name}_{profile}_{seed}_n{len(requests)}'
        tolerance=spec['numeric_tolerance']
        for prefix,value in pareto(found['leaves'],tolerance):
            frontier_rows.append(dict(case=case_id,search_status=found['status'],
                actions=json.dumps(prefix),energy_j=value['energy_j'],ap_peak_c=value['ap_peak_c'],
                ap_exceed_s=value['ap_exceed_s'],complete=value['complete'],planned=value['planned'],
                urgent_miss=value['urgent_miss'],normal_miss=value['normal_miss'],
                responses_ms=json.dumps(value['response_by_id'],sort_keys=True)))
        for policy,result in baselines.items():
            value=summary(result)
            thermal_paths.extend(thermal_path(case_id,policy,result,m))
            paths.extend(request_path(case_id,policy,result))
            comparisons.append(dict(case=case_id,request_count=len(requests),profile=profile,
                seed=seed,row_type='online_policy',name=policy,search_status='',nodes='',leaves='',
                **{k:v for k,v in value.items() if not isinstance(v,(dict,list))},
                urgent_responses_ms=json.dumps(value['urgent_responses_ms']),
                normal_responses_ms=json.dumps(value['normal_responses_ms'])))
        for policy,result in baselines.items():
            benchmark=summary(result)
            for delta in spec['question_b_max_per_request_response_loss_ms']:
                eligible=[]
                for prefix,leaf in found['leaves']:
                    value=summary(leaf)
                    if feasible(value,benchmark,delta,tolerance):eligible.append((prefix,leaf,value))
                for objective in ('energy','ap'):
                    key='energy_j' if objective=='energy' else 'ap_peak_c'
                    best=min(eligible,key=lambda item:(item[2][key],item[0])) if eligible else None
                    row=dict(case=case_id,baseline=policy,delta_ms=delta,objective=objective,
                        search_status=found['status'],optimality_proven=bool(best and found['status']=='complete'),
                        nodes=found['nodes'],leaves=len(found['leaves']),unexplored=found['unexplored_prefixes'],
                        elapsed_s=round(found['elapsed_s'],3),feasible_leaves=len(eligible),
                        baseline_energy_j=benchmark['energy_j'],baseline_ap_peak_c=benchmark['ap_peak_c'],
                        baseline_ap_exceed_s=benchmark['ap_exceed_s'],
                        baseline_urgent_miss=benchmark['urgent_miss'],baseline_normal_miss=benchmark['normal_miss'],
                        witness_energy_j=best[2]['energy_j'] if best else None,
                        witness_ap_peak_c=best[2]['ap_peak_c'] if best else None,
                        witness_ap_exceed_s=best[2]['ap_exceed_s'] if best else None,
                        witness_urgent_miss=best[2]['urgent_miss'] if best else None,
                        witness_normal_miss=best[2]['normal_miss'] if best else None,
                        witness_urgent_responses_ms=json.dumps(best[2]['urgent_responses_ms']) if best else None,
                        witness_normal_responses_ms=json.dumps(best[2]['normal_responses_ms']) if best else None,
                        max_request_response_loss_ms=max(best[2]['response_by_id'][rid]-value
                            for rid,value in benchmark['response_by_id'].items()) if best else None,
                        energy_improved=improvements(best[2],benchmark,tolerance)['energy'] if best else None,
                        ap_improved=improvements(best[2],benchmark,tolerance)['ap'] if best else None,
                        witness_actions=json.dumps(best[0]) if best else None)
                    witnesses.append(row)
                    if best:
                        checked=replay(estimates,vectors,requests,offline_settings,m,seed,best[0],
                                       spec['wait_step_ns'],spec['max_offline_wait_ns'])
                        base.require(checked['ledger']==best[1]['ledger'] and
                                     checked['thermal']==best[1]['thermal'], 'selected schedule replay differs')
                        selected_id=f'{case_id}|{policy}|{delta}|{objective}'
                        selected_paths.extend(request_path(case_id,selected_id,best[1]))
                        selected_thermal_paths.extend(thermal_path(case_id,selected_id,best[1],m))
                        for d in best[1]['decisions']:
                            selected_actions.append(dict(case=case_id,name=selected_id,
                                at_ms=d['now_ns']/1e6,
                                queue_head=d['queue'][0]['id'] if d['queue'] else '',
                                action=d['selected']['backend'] if d['selected'] else ('WAIT' if 'wait_until_ns' in d else 'BUSY'),
                                request_id=d['selected']['request_id'] if d['selected'] else '',
                                reason=d['reason'],current_ap_c=d.get('current_ap_c')))
        # One reproducible energy witness per case, including the unbounded-loss frontier point.
        if found['leaves']:
            prefix,leaf=min(found['leaves'],key=lambda x:(x[1]['thermal']['energy_j'],x[0]))
            again=replay(estimates,vectors,requests,offline_settings,m,seed,prefix,
                         spec['wait_step_ns'],spec['max_offline_wait_ns'])
            base.require(leaf['ledger']==again['ledger'] and leaf['thermal']==again['thermal']
                         and leaf['decisions']==again['decisions'], 'offline schedule replay differs')
            value=summary(leaf)
            thermal_paths.extend(thermal_path(case_id,'OFFLINE_ORACLE',leaf,m))
            paths.extend(request_path(case_id,'OFFLINE_ORACLE',leaf))
            comparisons.append(dict(case=case_id,request_count=len(requests),profile=profile,
                seed=seed,row_type='offline_energy_witness',name='OFFLINE_ORACLE',
                search_status=found['status'],nodes=found['nodes'],leaves=len(found['leaves']),
                **{k:v for k,v in value.items() if not isinstance(v,(dict,list))},
                urgent_responses_ms=json.dumps(value['urgent_responses_ms']),
                normal_responses_ms=json.dumps(value['normal_responses_ms'])))
            for d in leaf['decisions']:
                actions.append(dict(case=case_id,at_ms=d['now_ns']/1e6,
                    queue_head=d['queue'][0]['id'] if d['queue'] else '',
                    action=d['selected']['backend'] if d['selected'] else ('WAIT' if 'wait_until_ns' in d else 'BUSY'),
                    request_id=d['selected']['request_id'] if d['selected'] else '',reason=d['reason'],
                    current_ap_c=d.get('current_ap_c')))
    write_csv(output/'comparisons.csv',comparisons)
    write_csv(output/'witnesses.csv',witnesses)
    write_csv(output/'actions.csv',actions)
    write_csv(output/'requests.csv',paths)
    write_csv(output/'thermal_paths.csv',thermal_paths)
    write_csv(output/'selected_requests.csv',selected_paths)
    write_csv(output/'selected_thermal_paths.csv',selected_thermal_paths)
    write_csv(output/'selected_actions.csv',selected_actions)
    write_csv(output/'pareto.csv',frontier_rows)
    write_svg(output/'comparison.svg',comparisons)
    (output/'RUN_SUMMARY.json').write_text(json.dumps(dict(cases=[dict(c,case_id=f"{c['scenario']}_{c['profile']}_{c['seed']}_n{c['request_count']}") for c in spec['cases']],
        comparisons=len(comparisons),witness_rows=len(witnesses),experiment_ready=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return comparisons,witnesses


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--contract',type=Path,default=CONFIG)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    evaluate(args.contract,args.output)
