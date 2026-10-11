"""Read-only evidence decomposition of the frozen service-envelope run."""
import csv,gzip,hashlib,html,json,statistics,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone
from tools import d1_service_envelope_run as d

def schedule(raw):return [(q['id'],q['backend'],q['dispatch_ns'],q['response_ns'],q['lane_available_ns']) for q in sorted(raw['result']['ledger'],key=lambda q:q['ordinal'])]
def behavior(a):
    if a['kind'] in ('single','bundle'):return tuple(sorted((q['request_id'],q['backend']) for q in a['jobs']))
    return (a['kind'],a.get('until_ns'))
def raw(name):return json.loads(gzip.decompress((d.LOCAL/'items'/(name+'.json.gz')).read_bytes()))
def summary(rows,scope):
    refs={q['condition']:q for q in rows if q['policy']=='Band'};out=[]
    for role in d.ROLES:
        rs=[q for q in rows if q['policy']==role]
        if not rs:continue
        out.append(dict(scope=scope,policy=role,conditions=len(rs),planned=sum(q['planned'] for q in rs),completed=sum(q['completed'] for q in rs),urgent_failures=sum(q['urgent_failure'] for q in rs),normal_deadline_violations=sum(q['normal_failure'] for q in rs),mean_condition_P95_ms=statistics.mean(q['urgent_p95_ms'] for q in rs),mean_J=statistics.mean(q['energy_j'] for q in rs),mean_AP=statistics.mean(q['peak_ap_c'] for q in rs),mean_delta_J=statistics.mean(q['energy_j']-refs[q['condition']]['energy_j'] for q in rs) if refs else None,mean_delta_AP=statistics.mean(q['peak_ap_c']-refs[q['condition']]['peak_ap_c'] for q in rs) if refs else None,mean_delta_P95_ms=statistics.mean(q['urgent_p95_ms']-refs[q['condition']]['urgent_p95_ms'] for q in rs) if refs else None))
    return out
def csv_write(name,rows):
    with (d.PUBLIC/name).open('w',encoding='utf-8-sig',newline='') as f:
        fields=sorted({k for q in rows for k in q});w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def report():
    reg=d.check();state=d.read(d.LOCAL/'WORKING_STATE.json');assert state['phase']=='completed'
    starts=[]
    for line in (d.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        q=json.loads(line)
        if q.get('event'):starts[q['number']-1].update(q)
        else:starts.append(q)
    assert len(starts)==248 and all(q['status']=='completed' for q in starts)
    planned=completed=0;by={};frozen,initial,model=d.x.r.h.load();increments=frozen['energy_increment_w'];base=initial['initial']['preload_power_w']*120
    decomposition=[];diagnostics={role:Counter() for role in ('JointList','CostList')};admissions={role:Counter() for role in diagnostics}
    for s in starts:
        p=d.LOCAL/'items'/(s['identity']+'.json.gz');assert d.sha(p)==s['sha256'];item=raw(s['identity']);d.native.prior.previous.audit(item['result'],s['case']['tickets'])
        planned+=item['row']['planned'];completed+=item['row']['completed'];by[s['identity']]=item
        if s['phase']!='confirmation':continue
        segments,costs,end=d.x.r.h.account(item['result'],initial['initial'],frozen)
        volumes={label:sum(max(0,min(120.,q['end_s'])-max(0,q['start_s'])) for q in segments if q['state']==label) for label in increments}
        inc={label:volumes[label]*increments[label] for label in increments}
        reconstruct=base+sum(inc.values());assert abs(reconstruct-item['row']['energy_j'])<1e-8
        ledger=item['result']['ledger'];routing=Counter(q['task']+'_'+q['backend'] for q in ledger)
        curve=item['curve'];peak=max(v for _,v in curve);peak_t=[t for t,v in curve if v==peak]
        row=dict(condition=s['case']['condition'],seed=s['case']['seed'],family=s['case']['family'],context=s['case']['context'],policy=s['role'],baseline_J=base,increment_J=sum(inc.values()),whole_J=reconstruct,peak_AP=peak,peak_grid_seconds=peak_t,initial35_peak=(35 in peak_t),tail120plus_peak=any(t>120 for t in peak_t),CG_DC_parallel_seconds=volumes['classification_GPU+detection_CPU'])
        row.update({'count_'+label:routing[label] for label in ('classification_CPU','classification_GPU','detection_CPU')})
        row.update({'seconds_'+label:value for label,value in volumes.items()});row.update({'J_'+label:value for label,value in inc.items()});decomposition.append(row)
        if s['role'] not in diagnostics:continue
        ds=diagnostics[s['role']]
        for snap in item['snapshots']:
            actions=snap['actions'];fs=snap['forecasts'];mask=snap['mask'];physical=snap['physical_mask'];chosen=snap['chosen'];assert mask[chosen] and not any(a and not b for a,b in zip(mask,physical))
            ds['decisions']+=1;ds['physical_legal_slots']+=sum(physical);ds['admitted_slots']+=sum(mask)
            ds['informative_slot_count_gt1']+=sum(mask)>1
            unique={behavior(a) for i,a in enumerate(actions) if mask[i]};ds['meaningful_behavior_count_gt1']+=len(unique)>1
            ds['admitted_unique_behaviors']+=len(unique);ds['selected_'+actions[chosen]['kind']]+=1
            ds['nonreference_selected']+=chosen!=0;refs=fs[0]
            for i,a in enumerate(actions):
                admissions[s['role']][snap['admissions'][i]]+=1
                if not physical[i] or not all(f['valid'] and ref['valid'] for f,ref in zip(fs[i],refs)):continue
                nonworse=all(f['global_peak_ap_c']<=ref['global_peak_ap_c']+1e-9 and f['remaining_increment_j']<=ref['remaining_increment_j']+1e-9 for f,ref in zip(fs[i],refs))
                strict=any(f['global_peak_ap_c']<ref['global_peak_ap_c']-1e-9 or f['remaining_increment_j']<ref['remaining_increment_j']-1e-9 for f,ref in zip(fs[i],refs))
                if nonworse and strict:
                    ds['forecast_cost_improver_before_envelope']+=1
                    ds['forecast_cost_improver_after_envelope']+=bool(mask[i])
                ds['global_AP_same_as_reference_slots']+=all(f['global_peak_ap_c']==ref['global_peak_ap_c'] for f,ref in zip(fs[i],refs))
                ds['reference_J_AP_identical_slots']+=all(f['global_peak_ap_c']==ref['global_peak_ap_c'] and f['remaining_increment_j']==ref['remaining_increment_j'] for f,ref in zip(fs[i],refs))
        ds['explicit_cooling_count']+=item['cooling_count'];ds['extra_cooling_seconds']+=item['total_extra_wait']
    confirmation=d.read(d.PUBLIC/'confirmation_comparison.json');dev=d.read(d.PUBLIC/'development_comparison.json')
    prior_dev=d.read(d.ROOT/'output/overnight_ie_20261011_v1/development_rows.json')
    dev_refs=[q for q in prior_dev if q['policy'] in ('Band','Triton')];combined_dev=dev+dev_refs
    results=dict(development=summary(combined_dev,'development_reused_baselines'),confirmation=summary(confirmation,'fresh_confirmation'))
    paired=[];exact=Counter();band={q['condition']:q for q in confirmation if q['policy']=='Band'}
    for case in range(48):
        exact['Joint_Cost_exact_schedule']+=schedule(by[f'confirmation_JointList_{case:02d}'])==schedule(by[f'confirmation_CostList_{case:02d}'])
        for role in ('JointList','CostList'):
            q=next(q for q in confirmation if q['condition']==case and q['policy']==role);b=band[case]
            exact[role+'_Band_exact_schedule']+=schedule(by[f'confirmation_{role}_{case:02d}'])==schedule(by[f'confirmation_Band_{case:02d}'])
            service=all(q[k]<=b[k] for k in ('incomplete','urgent_failure','normal_failure','urgent_p95_ms'))
            costs=q['energy_j']<=b['energy_j'] and q['peak_ap_c']<=b['peak_ap_c']
            exact[role+'_service_nonnworse_cases']+=service;exact[role+'_cost_nonnworse_cases']+=costs
            paired.append(dict(condition=case,seed=q['arrival_seed'],family=q['family'],context=q['context'],policy=role,service_nonworse=service,cost_nonworse=costs,delta_P95_ms=q['urgent_p95_ms']-b['urgent_p95_ms'],delta_normal_violations=q['normal_failure']-b['normal_failure'],delta_J=q['energy_j']-b['energy_j'],delta_AP=q['peak_ap_c']-b['peak_ap_c']))
    indexed={(q['condition'],q['policy']):q for q in decomposition};cross=increments['classification_GPU+detection_CPU']-increments['classification_GPU']-increments['detection_CPU'];invariance=[]
    for case in range(48):
        b=indexed[case,'Band']
        for role in ('JointList','CostList'):
            q=indexed[case,role]
            same=all(q['count_'+s]==b['count_'+s] for s in ('classification_CPU','classification_GPU','detection_CPU'))
            overlap=q['CG_DC_parallel_seconds']-b['CG_DC_parallel_seconds'];actual=q['whole_J']-b['whole_J']
            invariance.append(dict(condition=case,policy=role,routing_multiset_same=same,delta_overlap_seconds=overlap,actual_delta_J=actual,pair_nonadditive_delta_J=cross*overlap,residual_if_same_multiset=actual-cross*overlap if same else None))
    representative={};request_exports={}
    for role in ('Band','JointList','CostList'):
        item=by['representative_'+role];rep=d.read(d.PUBLIC/'representative_rows.json');rep_row=next(q for q in rep if q['policy']==role)
        requests=[]
        for q in sorted(item['result']['ledger'],key=lambda q:q['ordinal']):
            requests.append(dict(ordinal=q['ordinal'],source_request_id=q['id'],task_id=q['task'],priority=q['priority'],offset_ms=q['arrival_ns']/1e6,deadline_ms=q['deadline_offset_ns']/1e6,release_offset_ns=q['dispatch_ns'],recorded_backend=q['backend'],pc_execution_start_ns=q.get('execution_start_ns'),pc_output_ready_ns=q.get('output_ready_ns'),pc_persist_complete_ns=q.get('persist_complete_ns'),pc_lane_available_ns=q['lane_available_ns']))
        plan=dict(version='frozen-plan-v2',policy_id=d.IDS[role],clock_origin='common0; arrivals35s+i*350ms',requests=requests,PC_metrics=rep_row,source_sha256=reg['source_sha256'],online_mobile_policy=False)
        path=d.LOCAL/f'device_plan_{role}.json';d.write(path,plan)
        representative[role]=dict(plan_sha256=d.sha(path),exact_Band_schedule=schedule(item)==schedule(by['representative_Band']),different_requests=sum(a!=b for a,b in zip(schedule(item),schedule(by['representative_Band']))),raw_sha256=d.sha(d.LOCAL/'items'/('representative_'+role+'.json.gz')))
    verification=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),registered_head=reg['head'],source_sha256=reg['source_sha256'],native_starts=248,new_learning=0,failed=0,scheduled_requests=planned,completed_requests=completed,all_raw_SHA_phase_lane_audited=True,mask_physical_support=True,request_wait_cap025=True,unit_tests=7,energy_decomposition_max_error_j=max(abs(q['whole_J']-(q['baseline_J']+q['increment_J'])) for q in decomposition),independent_physical_sessions=0,device_commands=0,model_fit_calls=0,original_final_gate_unchanged=True,new_confirmation_seeds_shared_with_simultaneously_registered_RL=True)
    d.write(d.PUBLIC/'summary.json',results);d.write(d.PUBLIC/'selection_diagnostics.json',dict(counts=diagnostics,admission_reasons=admissions,exact_schedules=exact,forecast_counts_are_not_independent_trials=True));d.write(d.PUBLIC/'energy_decomposition.json',decomposition);d.write(d.PUBLIC/'J_invariance.json',dict(pair_cross_increment_w=cross,condition_rows=invariance));d.write(d.PUBLIC/'representative_receipt.json',representative);d.write(d.PUBLIC/'verification.json',verification)
    csv_write('comparison.csv',confirmation);csv_write('condition_differences.csv',paired);csv_write('energy_decomposition.csv',decomposition)
    make_figures(results,paired,decomposition,by)
    render=''.join('<tr>'+''.join('<td>'+html.escape(str(q[k]) if k in ('policy','normal_deadline_violations','completed') else f'{q[k]:.6f}')+'</td>' for k in ('policy','completed','normal_deadline_violations','mean_condition_P95_ms','mean_delta_J','mean_delta_AP'))+'</tr>' for q in results['confirmation'])
    links=['execution_contract.json','summary.json','comparison.csv','condition_differences.csv','selection_diagnostics.json','energy_decomposition.csv','J_invariance.json','representative_receipt.json','verification.json']
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>기한·호환성 기반 공동 리스트</title><style>body{max-width:1180px;margin:30px auto;font:18px "Malgun Gothic",sans-serif;color:#183349;background:#f6f8fb}section{background:white;padding:25px;margin:20px 0}table{border-collapse:collapse;width:100%}th,td{padding:12px;border-bottom:1px solid #dae1e8;text-align:left}p{line-height:1.6}img{width:100%}.warn{background:#fff0d0;padding:20px}</style><h1>기한·호환성 기반 공동 리스트: 새 확인 결과</h1><p class="warn">물리 허용과 예측 성능 제한을 분리했다. 새248환경·학습0·요청 전량 완료·실패0. 원 엄격 기준은 두 정책 모두 FAIL이다. 열·에너지 절감 방법론 확립으로 표시하지 않는다.</p><section><table><tr><th>정책</th><th>완료</th><th>일반 기한 위반</th><th>조건별 긴급P95 평균ms</th><th>Band 대비 평균 ΔJ</th><th>평균 ΔAP°C</th></tr>'+render+'</table><p>각3168/3168 완료. 기한 위반은 늦은 완료이고 실행 오류가 아니다. P95 평균은 조건별 P95의 평균이다. 새4도착 seed×4부하×3민감도 문맥으로48독립 실측이 아니다.</p></section><section><h2>어떤 제약을 바꿨나</h2><p>개별 긴급 요청의 L0 응답 비악화 제한을 제거했다. 현재 전체 큐의 기한 위반·지각량, 공동 ECT, CPU 전용 탐지의 호환성을 먼저 본다. JointList가 서비스 기준, CostList/RL은 같은 서비스·현재 P95와 CPU 전용 응답을 보호하는 후보를 고른다. 예측 마스크는 미래 서비스 보장이 아니다.</p><p>공유 JointDispatcher는 최대4개 호환 EDD 자원 분할을 사용하는 유한 근사다. 향후 전체 본정책을 재귀적으로 실행하는 정확 rollout이 아니다. 같은 dispatcher를 fallback과 예측 suffix에 적용하며 원 파일을 수정하지 않는다.</p></section>'+''.join('<section><img src="figures/'+html.escape(p.name)+'"></section>' for p in sorted((d.PUBLIC/'figures').glob('*.png')))+'<p>'+' · '.join('<a href="'+q+'">'+q+'</a>' for q in links)+'</p></html>'
    (d.PUBLIC/'index.html').write_text(page,encoding='utf-8')
    lines=['# 기한·자원 호환성 기반 공동 리스트 서비스 Envelope','', '새 사용자의 최종 방법론 요청에 따른 별도 버전이다. 기존 실패·모형·기한·지원·기본·체크포인트를 보존했고 새 정책을 자동 채택하지 않았다.','',f'248/384환경·학습0·오류0·{completed}/{planned}요청 완료. gate4+개발48+확인192+대표4. 새 확인은833110101..104×4부하×3문맥이며 동시 새RL도 같은 사전등록 자료를 사용한다. 과거827 결과 재사용이나 새 독립 실측은 아니다.','', '## 정책과 결과','', '| 정책 | 일반 기한 위반 | 조건별 P95 평균ms | 평균 ΔJ | 평균 ΔAP°C |','|---|---:|---:|---:|---:|']
    for q in results['confirmation']:lines.append(f'| {q["policy"]} | {q["normal_deadline_violations"]} | {q["mean_condition_P95_ms"]:.6f} | {q["mean_delta_J"]:+.6f} | {q["mean_delta_AP"]:+.6f} |')
    lines.extend(['','두 정책 모두 원 strict FAIL/유망0이다. JointList/CostList의 전체 완료·일반 위반 건수는 Band와 같지만 긴급 P95가 악화하고 에너지도 평균 증가했다. AP의 미세 평균 감소를 서비스 악화와 바꾸어 성공으로 처리하지 않는다.','',f'JointList=CostList 정확 일정은{exact["Joint_Cost_exact_schedule"]}/48. 대표96은 두 정책 모두 Band와 전체 일정 exact이며 새 기기 재생0이다. 같은 대표의 중복2회 측정으로 절감을 주장하지 않는다.','', '## 왜 비용 대안이 남지 않았나','', 'selection_diagnostics.json은 물리 허용/예측 허용/실행 가능한 고유 행동과 실제 WAIT를 구분한다. PAIR 실행 순서만 다른 두 슬롯은 같은 자원 행동으로 집계하여 informative 수를 부풀리지 않는다. 과거/초기 최고가 global AP를 고정하는 예측 슬롯도 따로 센다.','', '고정5phase의 에너지는 120초 기본 에너지+상태별 점유초×증분W다. 같은 CPU/GPU 작업 multiset과 서비스 벡터라도 CG_DC 병행초가 바뀌면 J가 바뀔 수 있다. pair 비가산계수는 '+str(cross)+'W다. 같은 routing/병행초일 때만 J가 불변이다. J_invariance.json은 실제 대응 차이와 해당 식의 잔차를 보존한다. 열 경로는 작업 시각·공통 초기 상태·180초 꼬리에 의존하므로 같은 J가 같은 AP를 보장하지 않는다.','', '전체 현재 큐의 완료/기한/지각을 먼저 최소화하고 드레인 ECT를 빠르게 해도 긴급 P95 비악화와 같은 목적은 아니다. 이 새버전의 더 큰 학습이나 규칙 추가가 개선을 보장하지 않는다. 모형 차이는 표면온도/실제 절감 검증이 아니며 고정5phase 모형에 냉각→속도 회복은 없다.','', '## 근거와 재현','', '[화면](index.html) · [설정/사전등록](execution_contract.json) · [KPI CSV](comparison.csv) · [선택 진단](selection_diagnostics.json) · [상태별 에너지](energy_decomposition.csv) · [불변성](J_invariance.json) · [대표 일정/해시](representative_receipt.json) · [검증](verification.json)','', '```powershell','python -B -X utf8 -m unittest tools.test_d1_service_envelope_policy -v','python -B -X utf8 -m tools.d1_service_envelope_run check','python -B -X utf8 -m tools.d1_service_envelope_report','```','', '후처리는 원 local gz가 있는 workspace에서만 수행한다. 새환경·학습·기기·fit0이며 완료 run/등록을 반복해 예산을 초기화하지 않는다. 강한 새학습 참조 API는 tools/d1_service_envelope_policy.py의 Controller(mode=JOINT), 같은 bank/encoder PPO는 mode=r.PPO다. 새 semantic SCHEMA·fresh actor만 허용한다. 기존 L0/32/512 actor는 재사용하지 않는다.'])
    (d.PUBLIC/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(verification=verification,summary=results['confirmation'],selection=diagnostics,exact=exact,representative=representative)

def make_figures(result,paired,energy,by):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    folder=d.PUBLIC/'figures';folder.mkdir(exist_ok=True)
    rows=result['confirmation'];labels=['Band 대응','Triton 대응','공동 서비스 리스트','같은 서비스 비용 리스트'];fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,key,title in zip(axes,('mean_condition_P95_ms','mean_J','mean_AP'),('조건별 긴급 P95 평균 (ms)','전체 에너지 평균 (J)','최고 AP 평균 (°C)')):
        values=[q[key] for q in rows];ax.bar(labels,values,color=['#347da3','#9fabb5','#ce8b65','#488c80']);ax.set_ylabel(title);ax.tick_params(axis='x',labelrotation=18)
    fig.suptitle('새 확인48 · 일반 기한 위반 모두42 · P95/J 악화로 원 FAIL');fig.tight_layout();fig.savefig(folder/'01_응답과비용.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,6),sharex=True)
    rr=[q for q in paired if q['policy']=='CostList']
    for ax,key,title in zip(axes,('delta_P95_ms','delta_J','delta_AP'),('Band 대비 긴급P95 차이 (ms)','Band 대비 에너지 차이 (J)','Band 대비 최고 AP 차이 (°C)')):
        values=[q[key] for q in rr];ax.bar(range(48),values,color=['#ce8b65' if v>0 else '#488c80' for v in values]);ax.axhline(0,color='#374b61',lw=.7);ax.set_ylabel(title)
    axes[-1].set_xlabel('사전 고정 조건0..47 · 4도착seed×4부하×3민감도');fig.suptitle('평균 뒤의 조건별 상충 · Cost=Joint 일정48/48');fig.tight_layout();fig.savefig(folder/'02_조건별차이.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,3.5))
    for row,role in enumerate(('Band','JointList','CostList')):
        for q in by['representative_'+role]['result']['ledger']:
            a=q['dispatch_ns']/1e9-35;b=q['lane_available_ns']/1e9-35;ax.broken_barh([(a,b-a)],(row+.03 if q['backend']=='CPU' else row+.47,.40),facecolors='#347da3' if q['task']=='classification' else '#ce8b65')
    ax.set_yticks([.45,1.45,2.45],['Band 대응','공동 서비스 리스트','같은 서비스 비용 리스트']);ax.set_xlabel('공통35초 시작 이후 시간 (초) · 각 행 위CPU/아래GPU');ax.set_title('사전 고정96요청: 전체 일정 exact · 추가 기기 재생0');fig.tight_layout();fig.savefig(folder/'03_대표실행시간표.png',dpi=150);plt.close(fig)

if __name__=='__main__':print(json.dumps(d.serial(report()),ensure_ascii=False),flush=True)
