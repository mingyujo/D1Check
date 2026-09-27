"""Frozen small PC comparison: baseline policies versus one energy/AP-aware candidate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_thermal_feedback as feedback

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'docs/results/arrival_thermal_feedback_01/CONFIG.json'
INPUT=ROOT/'docs/results/arrival_explore_20260925/input_bundle'
FREEZE=ROOT/'docs/results/arrival_explore_20260925/freeze_before_evaluation.json'
OUTPUT=ROOT/'docs/results/arrival_thermal_feedback_01/run_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def write_csv(path, rows):
    if not rows:
        raise ValueError('empty CSV')
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def expand(compact):
    """One absolute whole-device coefficient per joint state, never lane additive."""
    power={};equilibrium={}
    for state in feedback.STATES:
        kind='idle' if state=='idle' else 'pair' if '+' in state else 'cpu_single' if state.endswith(':CPU') else 'gpu_single'
        power[state]=compact[f'{kind}_w']
        equilibrium[state]=compact[f'{"idle" if kind=="idle" else "pair" if kind=="pair" else "cpu" if kind=="cpu_single" else "gpu"}_equilibrium_c']
    return dict(power_w=power,ap_equilibrium_c=equilibrium)


def model(profile,config):
    predicted=expand(profile['predicted'])
    realized=predicted if profile['realized']=='same_as_predicted' else expand(profile['realized'])
    result=dict(version=feedback.VERSION,id=profile['id'],device='A24',
                model='efficientnet_lite0+efficientdet_lite0',evidence='explicit_assumptions',
                initial_ap_c=profile['initial_ap_c'],ap_limit_c=profile['ap_limit_c_research'],
                tau_s=profile['tau_s_assumed'],max_wait_ns=config['max_voluntary_wait_ns'],
                wait_step_ns=config['wait_step_ns'],predicted=predicted,realized=realized)
    return feedback.validate(result)


def settings(policy, config, freeze):
    s=batch.defaults('explore')
    s.update({k:freeze['B2']['explore']['settings'][k] for k in ('static_map','static_parallel')})
    s.update(interference=config['realized_interference'],
             predicted_interference=config['predicted_interference'],
             decision_ns=config['candidate_decision_ns_assumed'] if policy==feedback.POLICY else config['baseline_decision_ns'],
             record_ns=config['record_ns_assumed'],dispatch_ns=config['dispatch_ns_assumed'])
    return s


def verify(config):
    required={'low','queue','burst'}
    if (set(config['scenario'])!=required or set(config['compared_policies'])!=
            {'CPU_URGENT','B2_PC','B3_SOLO_EFT_PC',feedback.POLICY}):
        raise ValueError('comparison matrix changed')
    if set(config['development_seeds_seen_before']) & set(config['pc_confirmation_seeds_not_used_for_policy_design']):
        raise ValueError('development/confirmation seed overlap')
    if config['common_window_s']!=120 or config['research_request_deadline_ms']!={'urgent':1500,'normal':6000}:
        raise ValueError('research clock contract')
    receipt=read(INPUT/'receipt.json')
    for name in ('estimates.json','realizations.json'):
        if sha(INPUT/name)!=receipt['files'][name]:
            raise ValueError(f'frozen input hash mismatch: {name}')
    frozen=read(FREEZE)
    if frozen['B2']['explore']['candidate']!='GPU_CPU_parallel' or frozen['evaluation_data_seen'] is not False:
        raise ValueError('B2 development freeze mismatch')
    for p in config['profiles']:
        model(p,config)
    return frozen


def metric_row(phase,profile,scenario,seed,policy,result):
    m=result['metrics'];t=result['thermal']
    urgent_miss=round(m['urgent_deadline_violation']*6)
    normal_miss=round((1-m['normal_timely'])*18)
    return dict(phase=phase,profile=profile,scenario=scenario,seed=seed,policy=policy,
        realized_interference=result['settings']['interference'],
        decision_ns_assumed=result['settings']['decision_ns'],
        planned=m['planned'],urgent_planned=m['urgent_n'],normal_planned=m['normal_n'],
        completed=round(m['completion']*m['planned']),unfinished=m['unfinished'],
        not_arrived=m['not_arrived'],modeled_failures=0,
        urgent_response_count=sum('response_ns' in r for r in result['ledger'] if r['priority']=='urgent'),
        normal_response_count=sum('response_ns' in r for r in result['ledger'] if r['priority']=='normal'),
        urgent_p95_ms=m['urgent_p95_ms'],normal_mean_ms=m['normal_mean_ms'],
        urgent_miss_count=urgent_miss,normal_miss_count=normal_miss,
        makespan_s=m['makespan_s'],throughput_per_s=m['throughput'],
        energy_120s_j_assumed=t['energy_j'],ap_peak_c_assumed=t['ap_peak_c'],
        ap_over_limit_s_assumed=t['ap_exceed_s'],
        ap_limit_c_research=result['thermal_model_limit_c'],
        actions=len(result['decisions']),
        voluntary_wait_decisions=sum(d['reason'].startswith('wait_for_') for d in result['decisions']),
        fallback_decisions=sum(d['reason'].startswith('fallback_') for d in result['decisions']),
        evidence='PC model + unmeasured absolute whole-device power/AP assumptions; no device confirmation')


def decision_rows(phase,profile,scenario,seed,result):
    rows=[]
    for i,d in enumerate(result['decisions']):
        if d['selected'] is None and d.get('wait_until_ns') is None:
            continue
        prediction=d.get('chosen_prediction') or {}
        rows.append(dict(phase=phase,profile=profile,scenario=scenario,seed=seed,ordinal=i,
            now_ms=d['now_ns']/1e6,head_request=d['queue'][0]['id'] if d['queue'] else '',
            selected_request=d['selected']['request_id'] if d['selected'] else '',
            backend=d['selected']['backend'] if d['selected'] else '',
            wait_until_ms=d.get('wait_until_ns',0)/1e6 if d.get('wait_until_ns') is not None else '',
            reason=d['reason'],current_ap_c=d['current_ap_c'],
            predicted_energy_j=prediction.get('predicted_energy_j',''),
            predicted_ap_peak_c=prediction.get('predicted_ap_peak_c',''),
            predicted_deadline_miss=prediction.get('deadline_miss',''),
            predicted_ap_violation=prediction.get('ap_violation','')))
    return rows


def assignment_rows(phase,profile,scenario,seed,results):
    candidates={p:{r['id']:r for r in result['ledger']} for p,result in results.items()}
    new=candidates[feedback.POLICY]
    reasons={d['selected']['request_id']:d['reason'] for d in results[feedback.POLICY]['decisions']
             if d['selected'] is not None}
    rows=[]
    for rid,row in sorted(new.items(),key=lambda item:item[1]['ordinal']):
        backends={p:cells[rid].get('backend','') for p,cells in candidates.items()}
        dispatch={p:cells[rid].get('dispatch_ns') for p,cells in candidates.items()}
        if all(backends[p]==backends[feedback.POLICY] and dispatch[p]==dispatch[feedback.POLICY]
               for p in candidates if p!=feedback.POLICY):
            continue
        rows.append(dict(phase=phase,profile=profile,scenario=scenario,seed=seed,
            request_id=rid,priority=row['priority'],task=row['task'],arrival_ms=row['arrival_ns']/1e6,
            new_backend=backends[feedback.POLICY],b2_backend=backends['B2_PC'],
            b3_backend=backends['B3_SOLO_EFT_PC'],cpu_backend=backends['CPU_URGENT'],
            new_dispatch_ms=dispatch[feedback.POLICY]/1e6 if dispatch[feedback.POLICY] is not None else '',
            b2_dispatch_ms=dispatch['B2_PC']/1e6 if dispatch['B2_PC'] is not None else '',
            b3_dispatch_ms=dispatch['B3_SOLO_EFT_PC']/1e6 if dispatch['B3_SOLO_EFT_PC'] is not None else '',
            cpu_dispatch_ms=dispatch['CPU_URGENT']/1e6 if dispatch['CPU_URGENT'] is not None else '',
            new_reason=reasons.get(rid,'unconfirmed'),
            new_status=row['status']))
    return rows


def svg_chart(rows, config, output):
    spec=config['representative_svg_before_results']
    selected=[r for r in rows if r['phase']=='pc_confirmation' and r['scenario']==spec['scenario']
              and r['profile']==spec['profile'] and r['seed']==spec['seed']]
    if len(selected)!=4:
        raise ValueError('prespecified SVG coverage')
    energies=[r['energy_120s_j_assumed'] for r in selected]
    urgencies=[r['urgent_p95_ms'] for r in selected]
    xmin,xmax=min(energies)-.5,max(energies)+.5
    ymin,ymax=min(urgencies)-50,max(urgencies)+50
    x=lambda value:85+540*(value-xmin)/(xmax-xmin)
    y=lambda value:355-270*(value-ymin)/(ymax-ymin)
    points=''.join(f'<circle cx="{x(r["energy_120s_j_assumed"]):.1f}" cy="{y(r["urgent_p95_ms"]):.1f}" r="7" fill="{color}"/><text x="{x(r["energy_120s_j_assumed"])+10:.1f}" y="{y(r["urgent_p95_ms"])+4:.1f}" font-size="12">{r["policy"]} · AP {r["ap_peak_c_assumed"]:.2f}°C · 초과 {r["ap_over_limit_s_assumed"]:.2f}s</text>'
                   for r,color in zip(selected,('#355f9b','#bc8231','#668d49','#b44e64')))
    image=f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="430" viewBox="0 0 900 430"><rect width="900" height="430" fill="white"/><text x="45" y="32" font-family="Malgun Gothic" font-size="19">queue · thermal_cap · 새 PC seed 301 (사전 고정)</text><text x="45" y="52" font-size="12">기기 전체 W/AP 계수는 미측정 탐색 가정; 동일 120초·24요청, 실기기 성능 아님</text><line x1="85" y1="355" x2="650" y2="355" stroke="#445"/><line x1="85" y1="70" x2="85" y2="355" stroke="#445"/><text x="250" y="402" font-size="14">공통 120초 에너지 J (가정)</text><text x="10" y="80" font-size="13">긴급 P95 ms</text>{points}</svg>'''
    output.write_text(image,encoding='utf-8')


def run(output=OUTPUT, config_path=CONFIG, dry_run=False):
    config=read(config_path);frozen=verify(config)
    expected=3*len(config['profiles'])*(len(config['development_seeds_seen_before'])+
             len(config['pc_confirmation_seeds_not_used_for_policy_design']))*4
    if dry_run:
        return dict(runs=expected,profiles=[p['id'] for p in config['profiles']],
                    source_head='1c55c239eb0d56d050f9b1dd0c9fcb038e43b45e',
                    config_sha256=sha(config_path),device_runs=0)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    estimate=read(INPUT/'estimates.json');vectors=read(INPUT/'realizations.json')
    manifest=dict(config_sha256=sha(config_path),frozen_b2_sha256=sha(FREEZE),
                  input_sha256={name:sha(INPUT/name) for name in ('estimates.json','realizations.json','receipt.json')},
                  engine_sha256=sha(Path(engine.__file__)),policy_sha256=sha(Path(feedback.__file__)),
                  runner_sha256=sha(Path(__file__)),planned_pc_runs=expected,
                  development_seeds=config['development_seeds_seen_before'],
                  confirmation_seeds=config['pc_confirmation_seeds_not_used_for_policy_design'],
                  source_head='1c55c239eb0d56d050f9b1dd0c9fcb038e43b45e',
                  experiment_ready=False,device_sessions=0)
    write_json(output/'SOURCE_MANIFEST.json',manifest)
    all_rows=[];all_decisions=[];all_assignments=[]
    def phase_run(label,seeds):
        rows=[]
        for profile_spec in config['profiles']:
            cost_model=model(profile_spec,config)
            for scenario in config['scenario']:
                requests=batch.workload(scenario,'evaluation')
                for seed in seeds:
                    results={}
                    for policy in config['compared_policies']:
                        result=engine.simulate(estimate,vectors,requests,policy=policy,
                                               settings=settings(policy,config,frozen),seed=seed,
                                               thermal_model=cost_model)
                        result['thermal_model_limit_c']=cost_model['ap_limit_c']
                        results[policy]=result
                        rows.append(metric_row(label,profile_spec['id'],scenario,seed,policy,result))
                        if policy==feedback.POLICY:
                            all_decisions.extend(decision_rows(label,profile_spec['id'],scenario,seed,result))
                    all_assignments.extend(assignment_rows(label,profile_spec['id'],scenario,seed,results))
        return rows
    dev=phase_run('retrospective_development',config['development_seeds_seen_before'])
    write_csv(output/'development_metrics.csv',dev)
    write_json(output/'freeze_before_confirmation.json',dict(
        config_sha256=manifest['config_sha256'],development_metrics_sha256=sha(output/'development_metrics.csv'),
        policy_version=feedback.VERSION,b2_sha256=manifest['frozen_b2_sha256'],
        policy_changed_after_development=False,confirmation_data_seen=False,
        confidence_or_pass_threshold=None,device_validation=False))
    confirmation=phase_run('pc_confirmation',config['pc_confirmation_seeds_not_used_for_policy_design'])
    all_rows=dev+confirmation
    write_csv(output/'metrics.csv',all_rows)
    write_csv(output/'decision_trace.csv',all_decisions)
    write_csv(output/'assignment_differences.csv',all_assignments)
    svg_chart(all_rows,config,output/'comparison.svg')
    write_json(output/'FINAL_RECEIPT.json',dict(status='pc_completed',runs=len(all_rows),
        development_runs=len(dev),confirmation_runs=len(confirmation),
        config_sha256=manifest['config_sha256'],freeze_sha256=sha(output/'freeze_before_confirmation.json'),
        confirmation_recalibration=False,device_runs=0,experiment_ready=False))
    return dict(runs=len(all_rows),development=len(dev),confirmation=len(confirmation),output=str(output))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(args.output,args.config,args.dry_run),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
