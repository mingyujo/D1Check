"""Read-only original-model confirmation readout; never refit or select on test."""
import argparse
import collections
import csv
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
import numpy as np
from tools import d1_history_control_analysis as analysis


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def physical_ledger(raw,output):
    distinct={};runs=[];missing=[]
    for version in range(2,8):
        root=raw.parent/f'energy_ap_history_recovery_run_v{version}'/'primary'
        file=root/'FINAL_RECEIPT.json'
        if not file.exists():missing.append(version);continue
        r=read(file);cmds=list((root/'host_commands').glob('*/context.json'))
        runs.append(dict(version=version,status=r['status'],adb_intents=r['adb_commands'],
            recorded_clients=len(list((root/'host_commands').glob('*/client/start.json'))),
            local_reprobes=len(list((root/'host_commands').glob('*/server_precheck_gap.json'))),receipt_sha256=sha(file)))
        for folder in sorted(root.glob('[0-9][0-9]_*')):
            manifest=read(folder/'input_manifest.json')
            event_file=next((folder/p for p in ['artifacts/progress.jsonl','failure_prefix/progress.jsonl'] if (folder/p).exists()),None)
            if event_file is None:continue
            events=[]
            for line in event_file.read_text(encoding='utf8').splitlines():
                try:events.append(json.loads(line))
                except json.JSONDecodeError:break
            sid=manifest['session_id']
            if sid in distinct and distinct[sid]['valid_records']>=len(events):continue
            counts=collections.Counter(e['kind'] for e in events)
            origin=distinct[sid]['origin_version'] if sid in distinct else version
            terminal=read(folder/'artifacts/cleanup.json')['status'] if (folder/'artifacts/cleanup.json').exists() else 'unknown_after_prefix'
            distinct[sid]=dict(origin_version=origin,condition=manifest['phase'],role=manifest['history_role'],valid_records=len(events),
                runtime_start=counts['runtime_start'],runtime_return=counts['runtime_return'],warmup_start=counts['warmup_start'],warmup_return=counts['warmup_return'],
                request_start=counts['request_start'],inference_return=counts['host_inference_return'],output_ready=counts['output_ready'],persist_complete=counts['persist_complete'],
                worker_release=counts['worker_release'],lane_available=counts['lane_available'],terminal_evidence=terminal)
    rows=list(distinct.values());table(output/'physical_sessions.csv',rows);table(output/'physical_runs.csv',runs)
    return dict(distinct_recorded_sessions=len(rows),known_inference_starts=sum(r['warmup_start']+r['request_start'] for r in rows),
        known_inference_returns=sum(r['warmup_return']+r['inference_return'] for r in rows),runtime_starts=sum(r['runtime_start'] for r in rows),
        warmup_starts=sum(r['warmup_start'] for r in rows),request_starts=sum(r['request_start'] for r in rows),
        adb_intents=sum(r['adb_intents'] for r in runs),recorded_adb_clients=sum(r['recorded_clients'] for r in runs),
        local_server_reprobe_events=sum(r['local_reprobes'] for r in runs),missing_original_run_versions=missing,
        counting='deduplicated immutable session IDs across reused folders; unrecorded failure tails remain unknown')


def main(raw,output):
    raw,output=Path(raw),Path(output);root=raw/'primary'
    receipt=read(root/'FINAL_RECEIPT.json');plan=read(root/'frozen_collection_plan.json')
    frozen=read(plan['activity_model']['path'])
    assert sha(plan['activity_model']['path'])==plan['activity_model']['sha256']
    assert sha(root/'original_model_freeze.json')==plan['frozen_model']['sha256']
    candidate=None;candidate_role=None;freeze_sha=None
    if (root/'history_candidate_freeze.json').exists() and (root/'history_freeze_receipt.json').exists():
        freeze=read(root/'history_candidate_freeze.json');freeze_sha=sha(root/'history_candidate_freeze.json')
        assert freeze_sha==read(root/'history_freeze_receipt.json')['sha256']
        candidate=freeze['candidate'];candidate_role='rejected memory diagnostic; fixed before confirmation, not selected'
    elif (root/'history_development_result.json').exists():
        candidate=read(root/'history_development_result.json')['candidate'];candidate_role='development only; failed gate, no independent confirmation'
    totals=collections.Counter();sessions=[];scores=[];ap_paths=[];energy_paths=[];parts=[]
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        if not folder.exists():continue
        event_file=next((folder/p for p in ['artifacts/progress.jsonl','failure_prefix/progress.jsonl'] if (folder/p).exists()),None)
        events=[]
        if event_file:
            for line in event_file.read_text(encoding='utf8').splitlines():
                try:events.append(json.loads(line))
                except json.JSONDecodeError:break
        count=collections.Counter(e.get('kind') for e in events);totals.update(count)
        cleanup=read(folder/'artifacts/cleanup.json') if (folder/'artifacts/cleanup.json').exists() else {}
        eligible=(folder/'validated.json').exists() and read(folder/'validated.json')['status']=='eligible_descriptive_only'
        sessions.append(dict(condition=entry['phase'],role=entry['role'],eligible=eligible,
            runtime_start=count['runtime_start'],runtime_return=count['runtime_return'],warmup_start=count['warmup_start'],warmup_return=count['warmup_return'],
            request_start=count['request_start'],inference_return=count['host_inference_return'],output_ready=count['output_ready'],persist_complete=count['persist_complete'],
            worker_release=count['worker_release'],lane_available=count['lane_available'],app_cleanup=cleanup.get('status','unknown'),
            progress_gap=(folder/'postapproval_observation_gap.json').exists(),last_event=events[-1]['kind'] if events else 'unknown'))
        if not eligible:continue
        case=analysis.load_case(folder,read(folder/'input_manifest.json'))
        occupancy=collections.defaultdict(float)
        for segment in case['local_inputs']['segments']:
            dt=max(0.,min(120.,segment['end_s'])-max(0.,segment['start_s']))
            occupancy[analysis.states.state_key(segment['state'])]+=dt
        sessions[-1].update(target_parallel_s=sum(v for k,v in occupancy.items() if '+' in k),target_idle_s=occupancy.get('resident_idle',0),
            target_observed_j=case['observed_j'],cooling_current_missing_s=case['power_coverage']['cooling']['missing_s'],cooling_full_j=case['power_coverage']['cooling']['full_energy_j'])
        # g=0 is never published as a new candidate; this evaluates the original even before fitting.
        result=analysis.evaluate(case,frozen,candidate if candidate is not None else {'g':0})
        for name in ['frozen']+(['candidate'] if candidate is not None else []):
            score={k:v for k,v in result[name].items() if not isinstance(v,(dict,list))}
            scores.append(dict(condition=entry['phase'],role=entry['role'],gap=case['gap'],policy=case['target_policy'],model=name,
                candidate_role=candidate_role if name=='candidate' else 'original frozen model',**score,
                observed_j=result['observed_j'],predicted_j=result['predicted_j'],signed_j=result['signed_j'],absolute_j=result['absolute_j'],relative_j=result['relative_j'],
                ap_samples=len(case['observed_ap_c']),power_samples=len(case['power_t']),ap_window_start_s=case['local_inputs']['query_s'][0],ap_window_end_s=case['local_inputs']['query_s'][-1],
                observed_peak_ap_c=max(case['observed_ap_c']),
                prediction='actual schedule conditional; preload AP and initial resident power permitted; no future target measurements',strict_support=False,accuracy_pass=None))
        for i,t in enumerate(result['paths']['q']):
            ap_paths.append(dict(condition=entry['phase'],role=entry['role'],t_s=t,observed_c=result['paths']['observed'][i],
                frozen_c=result['paths']['frozen'][i],candidate_c=result['paths']['candidate'][i] if candidate is not None else None))
        for name in ['pre','load','post']:
            parts.append(dict(condition=entry['phase'],role=entry['role'],segment=name,signed_j=result[name+'_signed_j']))
        for t in np.linspace(0,120,121):
            energy_paths.append(dict(condition=entry['phase'],role=entry['role'],t_s=float(t),
                observed_j=analysis.m.integral(case,0,float(t)),
                predicted_j=analysis.m.energy_prediction(case,case['local_inputs']['segments'],frozen,{'name':'FROZEN'},float(t))))
        assert abs(sum(result[n+'_signed_j'] for n in ['pre','load','post'])-result['signed_j'])<1e-8
    commands=[read(p) for p in sorted((root/'host_commands').glob('*/client/result.json'))]
    assert len(commands)==receipt['adb_commands']
    assert len([s for s in sessions if s['eligible']])==receipt.get('completed_sessions',receipt.get('sessions'))
    installation=receipt.get('installation',{})
    dev=read(root/'history_development_result.json') if (root/'history_development_result.json').exists() else None
    reused=plan.get('history_reuse',{}).get('count',0)
    reused_starts=sum(s['request_start']+s['warmup_start'] for s in sessions[:reused])
    summary=dict(status=receipt['status'],source_head='099e35d',plan_sha256=read(raw/'claim.json')['plan_sha256'],
        child_receipt_sha256=sha(root/'FINAL_RECEIPT.json'),campaign_receipt_sha256=sha(raw/'primary_campaign_receipt.json'),
        activity_model_sha256=plan['activity_model']['sha256'],collection_model_sha256=plan['frozen_model']['sha256'],
        sessions_attempted=receipt.get('session_attempts'),eligible_development=sum(s['eligible'] and s['role']=='development' for s in sessions),
        eligible_confirmation=sum(s['eligible'] and s['role']=='confirmation' for s in sessions),
        durable_counts={k:totals[k] for k in ['runtime_start','runtime_return','warmup_start','warmup_return','request_start','host_inference_return','output_ready','persist_complete','worker_release','lane_available']},
        known_inference_starts=totals['request_start']+totals['warmup_start'],missing_calls='unrecorded prefix tails are unknown, not zero',
        reused_sessions=reused,new_inference_starts=totals['request_start']+totals['warmup_start']-reused_starts,
        total_physical_durable_start_lower_bound=104+108+8+totals['request_start']+totals['warmup_start'],
        total_physical_registered_upper_bound=104+200+8+sum(e['requests']+e['conditioning_requests']+e['warmup'] for e in plan['entries']),
        declared_new_inference_budget=plan['budget']['explicit_inference'],
        manifest_new_inference_budget=sum(e['requests']+e['conditioning_requests']+e['warmup'] for e in plan['entries'][reused:]),
        remaining_budget_discrepancy='808 declared vs 904 manifest/actual; +96; overall 2328 cap retained; future roster check corrected',
        adb_attempts=len(commands),timeouts=sum(x['status']=='timeout' for x in commands),progress_gaps=sum(s['progress_gap'] for s in sessions),
        apk_pushes=installation.get('apk_transfer_attempts'),installs=installation.get('install_attempts'),
        installed_host_pulls=sum(x['command'][3]=='pull' and x['command'][4].endswith('.apk') for x in commands),
        trace_host_pulls=sum(x['command'][3]=='pull' and x['command'][4].endswith('.pftrace') for x in commands),
        staged_files=sum(x['command'][3]=='push' and x['command'][5].endswith('.part') for x in commands),
        child_elapsed_s=receipt.get('elapsed_seconds'),candidate=candidate,candidate_role=candidate_role,freeze_sha256=freeze_sha,
        development_gate=dev['status'] if dev else None,original_error=receipt.get('error'),
        prior_v2=dict(status='stopped_no_resume',known_inference_starts=104,adb_commands=623,elapsed_s=251.72004508972168),
        prior_v3=dict(status='stopped_no_resume',known_inference_starts=104,adb_commands=857,elapsed_s=470.469,reused_in_cohort=True),
        prior_failed_PAR=dict(known_inference_starts=108,known_returns=107,registered_upper_bound=200,unknown_after_prefix=True,excluded_from_candidate_fit=True),
        prior_local_probe_preparation=dict(warmup_starts=8,warmup_returns=8,work_approval=False,work_starts=0,excluded_from_cohort=True),
        selected_model='ORIGINAL_FROZEN',new_fit_calls=0,prior_memory_development_gate='development_gate_stop',
        interpretation='original fixed model protocol-transition confirmation; rejected memory comparator secondary, no post-test selection',
        policy_effect=None,accuracy_pass=None,strict_support=False,experiment_ready=False)
    output.mkdir(parents=True,exist_ok=True)
    summary['physical_ledger']=physical_ledger(raw,output)
    for name,rows in [('sessions.csv',sessions),('metrics.csv',scores),('ap_paths.csv',ap_paths),('energy_paths.csv',energy_paths),('energy_parts.csv',parts)]:table(output/name,rows)
    contrasts=[]
    for role in ('development','confirmation'):
        for gap in (30,180):
            group=[s for s in scores if s['role']==role and s['gap']==gap and s['model']=='frozen']
            cpu=next((s for s in group if s['policy']=='CPU_URGENT_ONLINE_V1'),None)
            par=next((s for s in group if s['policy']=='B2_PARALLEL_ONLINE_V1'),None)
            if cpu and par:
                observed=par['observed_j']-cpu['observed_j'];predicted=par['predicted_j']-cpu['predicted_j']
                contrasts.append(dict(role=role,gap_s=gap,observed_par_minus_cpu_j=observed,predicted_par_minus_cpu_j=predicted,
                    signed_contrast_error_j=predicted-observed,sign_agrees=observed*predicted>0,
                    evidence='nominal condition-matched sequential diagnostic, different observed initials; not randomized paired policy effect'))
    table(output/'contrast_diagnostic.csv',contrasts)
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    keys=['condition','role','model','mae_c','max_absolute_error_c','peak_signed_error_c','signed_j','observed_j','predicted_j']
    table_html='<table><thead><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr></thead><tbody>'
    for row in scores:
        table_html+='<tr>'+''.join('<td>'+html.escape(str(round(row[k],6) if isinstance(row.get(k),float) else row.get(k,'미기록')))+'</td>' for k in keys)+'</tr>'
    table_html+='</tbody></table>'
    images=''.join('<h2>'+role+'</h2><img src="paths_'+role+'.png"><img src="residual_'+role+'.png"><img src="delta_ap_'+role+'.png">' for role in ('development','confirmation') if any(s['eligible'] and s['role']==role for s in sessions))
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>등록 이력 원모형 전이 확인</title><style>body{font:15px sans-serif;max-width:1200px;margin:2rem auto;padding:1rem}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.4rem}img{max-width:100%}p{line-height:1.6}</style><h1>원동결 모형 전이 확인 — 실제 수집 결과</h1><p>원모형 선택·계수 불변. 잔열 후보는 개발 gate 실패·미채택이며 고정된 보조 비교입니다. 실제 일정 조건부 예측 A, 부하 전 AP/유휴전력 입력. 종단간 예측 B·정책 효과·정확도 PASS·strict 지원 확대는 확인하지 않았습니다.</p><p>원자료·실패·부분 결과와 실측 전후 프로토콜 구분을 유지합니다. current raw=mA 해석은 조건부이고 절대 에너지 정확도는 미인증입니다.</p>'+table_html+images+'<p><a href="README.md">조건·오차·입력·재현 안내</a> · <a href="summary.json">소비·종료 요약</a></p></html>'
    (output/'index.html').write_text(page,encoding='utf8')
    if ap_paths:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for role in ('development','confirmation'):
            cells=[s for s in sessions if s['eligible'] and s['role']==role]
            if not cells:continue
            for residual in (False,True):
                fig,axes=plt.subplots(len(cells),2,figsize=(12,max(4,2.5*len(cells))),squeeze=False,layout='constrained')
                for i,session in enumerate(cells):
                    name=session['condition'];ap=[p for p in ap_paths if p['condition']==name];en=[p for p in energy_paths if p['condition']==name]
                    series=[('frozen_c','Original frozen')]+([('candidate_c','Rejected memory diagnostic')] if candidate is not None else [])
                    if not residual:series=[('observed_c','Observed')]+series
                    for key,label in series:
                        axes[i,0].plot([p['t_s'] for p in ap],[p[key]-p['observed_c'] if residual else p[key] for p in ap],label=label)
                    axes[i,0].set(title=name+' AP '+('residual' if residual else '(conditional)'),ylabel='Pred-obs C' if residual else 'AP C',xlabel='Target seconds');axes[i,0].legend(fontsize=7)
                    eseries=[('predicted_j','Original energy model')] if residual else [('observed_j','Observed'),('predicted_j','Original energy model')]
                    for key,label in eseries:
                        axes[i,1].plot([p['t_s'] for p in en],[p[key]-p['observed_j'] if residual else p[key] for p in en],label=label)
                    axes[i,1].set(title=name+' energy '+('residual' if residual else '(common 120s)'),ylabel='Pred-obs J' if residual else 'J',xlabel='Target seconds');axes[i,1].legend(fontsize=7)
                    if residual:axes[i,0].axhline(0,color='gray',linewidth=.5);axes[i,1].axhline(0,color='gray',linewidth=.5)
                fig.savefig(output/(('residual_' if residual else 'paths_')+role+'.png'),dpi=130);plt.close(fig)
            fig,axes=plt.subplots(len(cells),1,figsize=(10,max(3,2.1*len(cells))),squeeze=False,layout='constrained')
            for i,session in enumerate(cells):
                ap=[p for p in ap_paths if p['condition']==session['condition']]
                for key,label in [('observed_c','Observed delta'),('frozen_c','Original delta')]+([('candidate_c','Rejected memory delta')] if candidate is not None else []):
                    axes[i,0].plot([p['t_s'] for p in ap],[p[key]-ap[0][key] for p in ap],label=label)
                axes[i,0].set(title=session['condition']+' relative to first scored AP sample',ylabel='Delta C',xlabel='Target seconds');axes[i,0].legend(fontsize=7)
            fig.savefig(output/('delta_ap_'+role+'.png'),dpi=130);plt.close(fig)
    return summary


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--raw',required=True);cli.add_argument('--output',required=True);args=cli.parse_args()
    print(json.dumps(main(args.raw,args.output),ensure_ascii=False,indent=2))
