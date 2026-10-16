"""Saved-row/raw audit, PC calculation timings and static comparison deliverables."""
import argparse,collections,csv,gzip,json,math,shutil,time
from pathlib import Path
import numpy as np
import torch
from tools import d1_queue_direct_study as s
from tools import d1_queue_direct_cli as guarded

METRICS=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
ROLE_ORDER=('FIFO_FIXED','FIFO_EFT','FIFO_READY','EDD_EFT','ATC_EFT','RuleEDD','RuleATC','EDD_41','EDD_53','EDD_67','Future64_11','Future64_23','Future64_37','HeadDirect_11','HeadDirect_23','HeadDirect_37')

def saved_audit(main,aux):
    """Hash-check all saved successful episodes and frozen inputs; no environment calls."""
    guarded.guard(main)
    counts={};receipts={};models={}
    for folder in (main,aux) if aux else (main,):
        rows=sorted((folder/'rows').glob('*.json')); items=list((folder/'items').glob('*.json.gz'))
        if len(rows)!=len(items):raise ValueError('unpaired saved result/receipt')
        for path in rows:
            receipt=s.budget.read(path)
            item=folder/'items'/(path.stem+'.json.gz')
            if s.budget.digest(item)!=receipt['raw_sha256']:raise ValueError('saved item SHA changed '+path.name)
        counts[folder.name]=len(rows)
        receipts[folder.name]=s.a.native.digest({p.name:s.budget.digest(p) for p in rows})
    freeze=s.budget.read(main/'freeze.json')
    for role,selection in freeze['selections'].items():
        bank,seed=role.split('_');path=s.learner_path(main,bank,int(seed),selection['episodes'])
        if s.budget.digest(path)!=selection['sha256']:raise ValueError('selected weights changed')
        models[role]=selection['sha256']
    repair=None
    if aux:
        reg=s.budget.read(aux/'registration.json');repair=s.budget.read(aux/'source_repairs.json')
        if repair['registration_sha256']!=s.budget.digest(aux/'registration.json'):raise ValueError('repair lineage changed')
        for path,sha in reg['sources'].items():
            if path in repair['effective_sources']:
                item=repair['effective_sources'][path]
                if item['original_sha256']!=sha or repair['scope']!='legacy_event_hook_adapter_only':raise ValueError('repair scope changed')
                sha=item['effective_sha256']
            if s.budget.digest(s.ROOT/path)!=sha:raise ValueError('legacy source changed '+path)
        for role,model in reg['models'].items():
            if s.budget.digest(model['path'])!=model['sha256']:raise ValueError('legacy weights changed')
            models[role]=model['sha256']
    return dict(status='PASS_all_saved_SHA_and_frozen_models',successful_items=sum(counts.values()),counts=counts,receipt_set_digests=receipts,frozen_model_sha256=models,legacy_transport_repair=repair,new_environments=0,new_learning=0)

def csv_file(path,rr):
    if not rr:return
    keys=list(dict.fromkeys(k for r in rr for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rr)

def stats(v):
    return dict(count=len(v),mean_ms=float(np.mean(v))*1000,p95_ms=float(np.quantile(v,.95,method='higher'))*1000,max_ms=max(v)*1000) if v else dict(count=0,mean_ms=None,p95_ms=None,max_ms=None)

def strip(action, by_id):
    if not action:return None
    if action['kind']=='resource_wait':return ('resource_wait',)
    return (action['kind'],tuple(sorted((by_id[j['request_id']]['task'],j['backend']) for j in action.get('jobs',[]))))

def benchmark(f,initial,network):
    rr=[];torch.set_num_threads(1)
    c=s.a.Controller(f,initial,network=network)
    lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
    for n in (1,8,32,128,512):
        qs=[dict(id=f'bench{i}',task='classification' if i%2 else 'detection',priority='urgent' if i%2 else 'normal',ordinal=i,arrival_ns=35_000_000_000,deadline_offset_ns=1_500_000_000 if i%2 else 6_000_000_000) for i in range(n)]
        measured=collections.defaultdict(list)
        for i in range(55):
            t=time.perf_counter();e=s.a.bank(qs,lanes,35e9,c.estimates,sequencing='EDD');after=time.perf_counter()
            enc=c.encode(qs,lanes,35e9,e);encoded=time.perf_counter()
            with torch.no_grad():network(torch.from_numpy(enc['state'])[None],torch.from_numpy(enc['candidates'])[None],torch.from_numpy(enc['mask'])[None])
            end=time.perf_counter()
            if i<5:continue
            for k in ('atc_seconds','candidates_seconds','mask_seconds'):measured[k].append(e['timings'][k])
            measured['encode'].append(encoded-after);measured['PPO_forward'].append(end-encoded);measured['calculation_total'].append(end-t)
        for k,v in measured.items():rr.append(dict(queue=n,component=k,**stats(v),scope='PC synthetic current queue; 5warmup+50samples; environment0/learning0'))
    return rr

def report(main,aux,out):
    out.mkdir(parents=True,exist_ok=True);reg=s.check(main);cursor=s.budget.read(main/'cursor.json')
    if not cursor['completed']:raise ValueError('wait for complete paired confirmation')
    supplement=s.budget.read(main/'driver_freeze_receipt.json')
    if s.budget.digest(s.ROOT/supplement['path'])!=supplement['sha256']:raise ValueError('driver supplemental hash changed')
    freeze=s.budget.read(main/'freeze.json');rr=s.rows(main,'confirmation_')
    if aux:
        if s.budget.read(aux/'completion.json')['status']!='completed':raise ValueError('legacy incomplete')
        rr+=s.rows(aux,'confirmation_')
    saved=saved_audit(main,aux);s.write(out/'saved_integrity_audit.json',saved)
    if saved['legacy_transport_repair']:s.write(out/'legacy_transport_repair.json',saved['legacy_transport_repair'])
    csv_file(out/'comparison.csv',rr)
    roles=[role for role in ROLE_ORDER if any(q['policy']==role for q in rr)];summary=[]
    for role in roles:
        q=[r for r in rr if r['policy']==role]
        if len(q)!=48:raise ValueError('all roles need48paired cases')
        summary.append(dict(policy=role,conditions=len(q),planned=sum(r['planned'] for r in q),completed=sum(r['completed'] for r in q),incomplete=sum(r['incomplete'] for r in q),urgent_failure=sum(r['urgent_failure'] for r in q),normal_failure=sum(r['normal_failure'] for r in q),urgent_p95_mean_ms=float(np.mean([r['urgent_p95_ms'] for r in q])),energy_mean_j=float(np.mean([r['energy_j'] for r in q])) if all(r['energy_j'] is not None for r in q) else None,peak_ap_mean_c=float(np.mean([r['peak_ap_c'] for r in q])) if all(r['peak_ap_c'] is not None for r in q) else None,nonhead_decisions=sum(r.get('nonhead_decisions',0) for r in q),fallbacks=sum(r.get('fallbacks',0) for r in q)))
    csv_file(out/'summary.csv',summary)
    by={(r['condition'],r['policy']):r for r in rr};deltas=[]
    for role in roles:
        if role in s.BASES:continue
        for case in range(48):
            q=by[case,role]
            for baseline in ('FIFO_FIXED','FIFO_EFT','FIFO_READY','RuleEDD'):
                r=by[case,baseline]
                row=dict(condition=case,arrival_seed=q['arrival_seed'],family=q['family'],context=q['context'],policy=role,baseline=baseline)
                row.update({k:q[k]-r[k] if q[k] is not None and r[k] is not None else None for k in METRICS})
                row['all_axes_nonworse']=all(row[k] is not None and row[k]<=0 for k in METRICS);deltas.append(row)
    csv_file(out/'paired_deltas.csv',deltas)
    verdict=s.budget.read(main/'verdict.json');s.write(out/'verdict.json',verdict)
    timed=collections.defaultdict(list);qgroup=collections.defaultdict(list);diag=collections.Counter();ticket_hash={};raw_count=0;planned=0
    for folder in (main,aux) if aux else (main,):
        for receipt in sorted((folder/'rows').glob('confirmation_*.json')):
            d=s.budget.read(receipt);rawpath=folder/'items'/(receipt.stem+'.json.gz')
            if s.budget.digest(rawpath)!=d['raw_sha256']:raise ValueError('raw mutated')
            raw=json.loads(gzip.decompress(rawpath.read_bytes()));role=raw['row']['policy'];raw_count+=1
            s.audit_ledger(raw['result']);planned+=len(raw['result']['ledger'])
            tickets=[{k:r[k] for k in ('id','task','priority','ordinal','arrival_ns','deadline_offset_ns')} for r in raw['result']['ledger']]
            digest=s.a.native.digest(tickets);condition=raw['row']['condition']
            if condition in ticket_hash and ticket_hash[condition]!=digest:raise ValueError('paired arrivals differ')
            ticket_hash[condition]=digest
            for cb in raw['callbacks']:
                timed[role,'all_callback'].append(cb['seconds'])
                if 'event_to_dispatch_seconds' in cb:timed[role,'event_to_dispatch_with_modeled_observe'].append(cb['event_to_dispatch_seconds'])
            for t in raw['stage_times']:
                if role.startswith('EDD_') or role.startswith('Rule') or role in s.mobile.ROLES:
                    for k in ('atc_seconds','candidates_seconds','mask_seconds','encode_seconds','inference_seconds','total_seconds','actual_total_seconds','diagnostic_seconds'):
                        if k in t:timed[role,k].append(t[k])
                n=t.get('queue',0);group='1' if n<=1 else '2-4' if n<=4 else '5-8' if n<=8 else '9-16' if n<=16 else '17+'
                total=t.get('actual_total_seconds',t.get('total_seconds',t.get('native_seconds')))
                if total is not None:qgroup[role,group].append(total)
            for snap in raw['snapshots']:
                if 'request_ids' not in snap:continue
                diag['decisions']+=1;diag['bank_same']+=bool(snap['ATC_EDD_same']);diag['legal_same']+=bool(snap['ATC_EDD_legal_actions_same'])
                diag['rank_same']+=bool(snap['raw_rank_same']);diag['rule_same']+=bool(snap['same_bank_rule_choice_same'])
                diag['nonhead_selected']+=bool(snap['nonhead_selected']);diag['one_request']+=sum(x is not None for x in snap['request_ids'])==1
                diag['candidate_count_'+str(sum(x is not None for x in snap['request_ids']))]+=1
                diag['multiple_id_actions']+=sum(snap['mask'])>1
                templates={strip(x,{q['id']:q for q in tickets}) for x,m in zip(snap['actions'],snap['mask']) if m}
                diag['multiple_physical_templates']+=len(templates)>1
                if not snap['mask'][snap['chosen']]:raise ValueError('selectedmasked')
    timing=[dict(policy=r,component=k,**stats(v)) for (r,k),v in timed.items()];csv_file(out/'decision_times.csv',timing)
    csv_file(out/'observed_queue_times.csv',[dict(policy=r,queue_bin=k,**stats(v)) for (r,k),v in qgroup.items()])
    selected=freeze['selected'];bank,seed=selected.split('_');model=s.learner_path(main,bank,int(seed),freeze['selections'][selected]['episodes'])
    l=s.learning.Learner.load(model,s.deps(reg,bank));f,i,_=s.a.hybrid.load()
    # Rebuilding a report reuses the completed PC calculation benchmark.
    if not (out/'queue_scaling_calculation.csv').exists():
        csv_file(out/'queue_scaling_calculation.csv',benchmark(f,i['initial'],l.network))
    development=s.rows(main,'dev')
    for row in development:
        row['episodes']=int(row['phase'][3:]) if row['phase'][3:].isdigit() else 0
    csv_file(out/'development.csv',development)
    dev_summary=[]
    for role in sorted({r['policy'] for r in development}):
        for stage in sorted({r.get('episodes',0) for r in development if r['policy']==role}):
            q=[r for r in development if r['policy']==role and r.get('episodes',0)==stage]
            dev_summary.append(dict(policy=role,episodes=stage,conditions=len(q),incomplete=sum(r['incomplete'] for r in q),urgent_failure=sum(r['urgent_failure'] for r in q),normal_failure=sum(r['normal_failure'] for r in q),urgent_p95_mean_ms=float(np.mean([r['urgent_p95_ms'] for r in q])),energy_mean_j=float(np.mean([r['energy_j'] for r in q])),peak_ap_mean_c=float(np.mean([r['peak_ap_c'] for r in q]))))
    csv_file(out/'development_summary.csv',dev_summary)
    learning=[]
    for role in freeze['selections']:
        bank,seed=role.split('_');terminal=s.learning.Learner.load(s.learner_path(main,bank,int(seed)),s.deps(reg,bank))
        learning.append(dict(policy=role,episodes=terminal.episodes,updates=len(terminal.logs),optimizer_steps=terminal.steps,selected_episodes=freeze['selections'][role]['episodes'],pending=len(terminal.pending),actor_changed_all=all(x['actor_changed'] for x in terminal.logs),gradient_finite_positive_all=all(math.isfinite(x['actor_gradient_max']) and x['actor_gradient_max']>0 for x in terminal.logs),fallbacks=sum(x['row']['fallbacks'] for x in terminal.episode_logs)))
        s.write(out/f'learning_{role}.json',dict(summary=learning[-1],updates=terminal.logs,development_only_selection=freeze['selections'][role]))
    csv_file(out/'learning.csv',learning)
    # Separate actual role outcomes; means are descriptive, epsilon0 gate uses each condition.
    s.write(out/'bank_diagnostics.json',dict(diag));s.write(out/'freeze.json',freeze)
    usage=s.budget.read(main/'consumption.json');auxusage=s.budget.read(aux/'consumption.json') if aux else None
    verification=dict(status='PASS_saved_result_integrity',registered_sources_unchanged=True,supplemental_driver_sha_verified=True,driver_registration_omission_preserved=True,driver_supplement=s.budget.read(main/'driver_freeze_receipt.json'),postcompletion_guard_added=True,guard_used_for_historical_training=False,all_successful_item_hashes_verified=saved['successful_items'],raw_confirmation_items=raw_count,planned_confirm_requests=planned,all48_arrival_tickets_exact_across_roles=True,selected_masks_and_physical_ledger_audited=True,main_consumption=usage,aux_consumption=auxusage,tests=dict(pretraining_contract=9,postcompletion_transport_and_hash_guard=3,total=12),resume=s.budget.read(main/'resume_receipt.json'),model_fit=0,device_runs=0,phone_decision_energy_measured=False)
    s.write(out/'verification.json',verification)
    s.write(out/'execution_contract.json',{k:v for k,v in reg.items() if k!='sources'})
    if aux:
        ar=s.budget.read(aux/'registration.json');s.write(out/'legacy_contract.json',{k:v for k,v in ar.items() if k not in ('models','sources','inputs')})
        s.write(out/'legacy_models.json',{k:{kk:vv for kk,vv in v.items() if kk!='path'} for k,v in ar['models'].items()})
    chart(out,summary,selected)
    selected_row=next(x for x in summary if x['policy']==selected)
    baseline=next(x for x in summary if x['policy']=='FIFO_EFT')
    ready=next(x for x in summary if x['policy']=='FIFO_READY');rule=next(x for x in summary if x['policy']=='RuleEDD')
    if not all(by[case,selected][key]==by[case,'FIFO_READY'][key] for case in range(48) for key in ('completed','incomplete','urgent_failure','normal_failure','energy_j','peak_ap_c')):
        raise ValueError('READY equality conclusion needs revision')
    losses=[x for x in deltas if x['policy']==selected and x['baseline']=='FIFO_EFT' and not x['all_axes_nonworse']]
    rows_md='\n'.join(f"|{x['policy']}|{x['completed']}/{x['planned']}|{x['urgent_failure']}|{x['normal_failure']}|{x['urgent_p95_mean_ms']:.3f}|{x['energy_mean_j']:.6f}|{x['peak_ap_mean_c']:.6f}|" for x in summary)
    learned_md='\n'.join(f"|{x['policy']}|{x['episodes']}|{x['updates']}|{x['optimizer_steps']}|{x['selected_episodes']}|{'PASS' if verdict[x['policy']]['promising'] else 'FAIL'}|" for x in learning)
    text=f'''# 전체 큐 직접 PPO·FIFO·모바일 EFT 비교 — 2026-10-11

3전문가 검토 후 전체 미시작 큐의 후보 생성·행동 선택·실제 dispatch를 구현하고 PC 학습과 고정 비교를 완료했다. 개발에서 미리 선택한 모델은 **{selected}, {freeze['selections'][selected]['episodes']}회 checkpoint**다. 새 strictV2 판정은 **{', '.join(k+': '+('PASS' if v['promising'] else 'FAIL') for k,v in verdict.items())}**이며 기본 정책과 experiment_ready=false를 유지한다. PC 실측 기반 모형 결과이며 휴대폰 실험 결과가 아니다.

**이번 학습 PPO의 추가 이득은 입증되지 않았다.** 단순 FIFO_READY에서도 긴급 실패가122→0이고, 선정 PPO와 완료·기한 실패·J·AP가48조건 각각 같았다. PPO의 조건별 긴급P95 평균은 READY보다 {selected_row['urgent_p95_mean_ms']-ready['urgent_p95_mean_ms']:.3f}ms 높다. 전체 큐 EDD 물리 규칙은 PPO와 긴급0/일반51 실패가 같으면서 평균 P95·J·AP가 더 낮다. ATC 튜닝과 확인 자료를 이용한 추가 학습을 중단한다. 전체 큐 EDD 규칙을 후속 후보로 남기며 채택 PASS로 올리지 않는다.

## 구현과 선정

- 전체 arrived/unstarted 큐 top4 ∪ oldest 분류/탐지 ∪ 현재 EDD 복귀 행동: max8. 물리 mask에서 task FIFO 선두 조건 제거. 입력198·행동49·padding32, 새 가중치와 Adam/RNG로 학습했다.
- 모바일 기본 비교는 **FIFO 순서 + EFT 자원 배정**이다. FIFO_FIXED는 분류GPU/탐지CPU 고정, FIFO_EFT는 같은 global FIFO 선두의 현재 owner와 한 요청만으로 AVAILABLE 종료 추정, FIFO_READY는 선두 차단 해소를 따로 보는 보조군이다. Android 표준이나 전체 HEFT 구현을 주장하지 않는다.
- 개발24의 3,075 판단에서 ATC/EDD rank/top4/bank/legal/Rule선택 동일. 사전 gate에 따라 ATC 튜닝·동일 PPO 중복 학습 중단, EDD PPO 3seed 학습. 확인에서 bank 동일 {diag['bank_same']}/{diag['decisions']}, 유효 행동 동일 {diag['legal_same']}/{diag['decisions']}. 이 자료에서 같은 encoder/mask 입력이므로 ATC 후보+동일 actor는 EDD 후보+actor와 같은 선택을 낸다. 다른 도착·이질 처리시간의 보편적 동일성은 입증하지 않았다.
- 확인에서 뒤 요청을 선택한 판단 {diag['nonhead_selected']}회. ID가 다른 다중 행동 {diag['multiple_id_actions']}회와 자원/병행/대기 템플릿이 다른 다중 행동 {diag['multiple_physical_templates']}회를 구분했다. 제약 제거·후보 확대가 성능 개선을 보장하지 않는다.

## 학습·개발·확인

128→256→512/seed, 단계당8episode/update. 256 개발에서 한 seed가 128보다 사전 lexicographic 서비스 지표를 개선하여512로 확대했다. 모델마다 개발24에서 checkpoint 선택 후 hash를 동결했으며 새 도착4seed×4부하×3실측문맥=48조건을 확인했다. 48은 같은 물리모형/초기AP를 사용하는 조건 수이며 독립 새 기기 측정48회가 아니다. 확인 argmax 고정·추론만, 미래 도착/실제 처리시간/에너지/AP 입력0이다.

|모델|새 학습회|update|Adam step|개발 선택회|strictV2|
|---|---:|---:|---:|---:|---|
{learned_md}

원 HeadDirect는 닫힌 이전 task의 개발 선택32/64 고정 모델이다. Future64는 기존 미래예측 PPO의 원64 checkpoint다. 최신512 weights는 이번 checkout에서 확보하지 못했으므로 Future64 결과를 그 모델의 결과로 해석하지 않는다. 두 보조군은 확인 자료를 보기 전에 각3개를 동결했으며 추가학습0, 같은48 요청·문맥·물리모형으로 평가했다. 새 strict 참조 집합에 사후 추가하지 않았다. Band/Triton은 이번 비교군에서 제외했으며 과거 결과·FAIL은 보존했다.

## 고정 48조건 결과

실패는 전체 도착 분모에서 미응답 또는 납기 초과다. 긴급1,500ms·일반6,000ms를 유지했다. P95/J/AP 열은 각 조건 KPI의 단순 평균이며 pooled P95가 아니다. 미완료 요청을 제외해 성공으로 바꾸지 않는다. 조건별 손해는 paired_deltas.csv와 verdict.json에서 확인할 수 있다.

|정책|완료/도착|긴급 실패|일반 실패|조건별 긴급P95 평균 ms|120s J 평균|35..180s AP peak 평균 °C|
|---|---:|---:|---:|---:|---:|---:|
{rows_md}

개발 선정 {selected}의 FIFO_EFT 대비: 긴급 실패 {selected_row['urgent_failure']-baseline['urgent_failure']:+d}, 일반 실패 {selected_row['normal_failure']-baseline['normal_failure']:+d}, 조건별 P95 평균 {selected_row['urgent_p95_mean_ms']-baseline['urgent_p95_mean_ms']:+.3f}ms, J {selected_row['energy_mean_j']-baseline['energy_mean_j']:+.6f}, AP {selected_row['peak_ap_mean_c']-baseline['peak_ap_mean_c']:+.6f}°C. 전체 지표를 유지하지 못한 조건은 **{len(losses)}/48**이다. 평균 개선만으로 이를 통과 처리하지 않는다.

선정 PPO의 READY 대비 서비스 실패·J·AP 동률과 P95 악화는 선두 차단 해소와 PPO 효과를 분리한다. RuleEDD 대비 PPO의 조건별 P95 평균은 +{selected_row['urgent_p95_mean_ms']-rule['urgent_p95_mean_ms']:.3f}ms, J +{selected_row['energy_mean_j']-rule['energy_mean_j']:.6f}, AP +{selected_row['peak_ap_mean_c']-rule['peak_ap_mean_c']:.6f}°C다. 에너지·AP의 작은 차이는 동결 모형 수치이며 기기 절감으로 해석하지 않는다.

![서비스 비교](service_comparison.png)
![에너지·AP 비교](cost_comparison.png)

## 판정·계산 비용·한계

새 FIFO_EFT_QUEUE_STRICT_V2는 FIFO_FIXED/FIFO_EFT/같은-bankRule 각각과 모든 조건에서 완료·미완료·긴급/일반 실패·긴급P95·J·AP 비악화(ε=0), low/sustained 절대 실패0, primary low 또는 sustained의 모든 짝에서 J/AP 한 축 엄격 개선을 요구한다. 기존 서비스 기준을 완화하지 않았고 과거 Band/Triton strict FAIL을 재판정하지 않았다. 채택은 자동으로 이루어지지 않는다.

decision_times.csv는 ATC 계산·후보·mask·encoder·순수 network forward·새 판단의 실제 전체 시간과 shadow ATC/EDD 비교 제외 시간, 전체 callback 및 public event/모형 관측 포함 시간을 구분한다. early return도 전체 callback 분모에 포함한다. 각 평균/P95/최댓값·관측 큐 구간은 observed_queue_times.csv, 별도 Q=1/8/32/128/512 현재 상태 계산50표본은 queue_scaling_calculation.csv다. 후자는 시뮬레이션/학습0인 PC 계산 벤치이며 휴대폰 판단시간·소비전력으로 환산하지 않는다. synthetic 큐 입력의 처리량을 실제 앱 자료로 주장하지 않는다.

원 frozen 에너지·서비스·v3 AP 모형, 최대2건 C_GPU+D_CPU, nonpreemptive, 실제AVAILABLE 점유/응답경계 분리, 자원대기만 유지했다. AP는 모형 AP 관측이며 표면온도/실기기 발열과 다르다. 온도→service feedback/새잔차모형/냉각/NPU/기기 실행은 없다. 요청 내 p/w/상대납기의 동질성, 개발3seed 작은 선택자료, critic 채널 scale 차이, 모형 오차 및 S26 품질·시각·혼합비용 gate가 한계다.

등록 sources()의 __main__ driver hash 누락을 실행 중 발견했다. 소스와 원등록을 변경하지 않고 **491환경/323학습 진행 시점, ep128 개발선택·새확인 전** supplemental driver SHA를 잠갔다. 원 run의 resume 자동검사는 이 보충 SHA를 포함하지 않았다. 실행 종료 후 guarded CLI와 회귀검사3개를 추가하여 보충 SHA 변조를 거부하고 최종 source/input/model SHA를 검산했다. 처음부터 모든 학습을 이 guard로 보호했다고 주장하지 않는다. expand128 코드 gate는 유한양의 actor gradient·actor 변경·fallback0이며 ID 제외 물리 템플릿 다양성은 별도 사후 감사한다. 원계약 문구와 자동 gate의 차이를 보존한다.

보조 Future64 첫 환경은 과거 Controller에 없는 public-event hook을 adapter가 노출하여 dispatch 전 실패했다. 실패1을 소비에 남기고 hook이 없는 경우 원 observe 경로를 쓰는 **전송 adapter만** 수정했다. 정책·weights·mask·입력·plant는 유지하며 원/수정SHA와 이유는 legacy_transport_repair.json에 있다. 줄바꿈/hash 사전검사 수정은 환경을 시작하지 않아 추가환경0이다. 288 성공행과 원 실패를 모두 보존했다.

## 실행 증분과 파일

본 task: 환경 {usage['environments']} / 새학습 {usage['learning']} / 실패 {usage['failed']} / 누적 활성 {usage['active_seconds']:.3f}s. 보조 기존모델 비교: 환경 {auxusage['environments'] if auxusage else 0} / 학습0 / 실패 {auxusage['failed'] if auxusage else 0} / 활성 {auxusage['active_seconds'] if auxusage else 0:.3f}s. 이번 전체 새 환경 {(usage['environments']+(auxusage['environments'] if auxusage else 0))}·새학습 {usage['learning']}이며 이전791/192 등 프로젝트 이력을 덮어쓰지 않는다. 새물리fit/APK/ADB/기기/S26학습 각0. 계산벤치와 raw-free unittest12(학습 전9·종료 후 guard/adapter3)은 환경실행 수에 합산하지 않는다.

raw/완전checkpoint/원장은 work의 별도task에서 보존했다. 전체 성공 raw2,688개의 SHA, 확인768 원장의 물리·동일도착·mask, 선정3모델과 과거6모델 SHA를 검산했다. 보고서는 comparison.csv(전체768행), summary.csv, paired_deltas.csv, verdict.json, development.csv/development_summary.csv, learning_*.json, freeze.json, execution_contract.json, legacy_contract.json, legacy_models.json, legacy_transport_repair.json, saved_integrity_audit.json, bank_diagnostics.json, verification.json, timing CSV와 세 전문가 검토를 포함한다. 설계는 ATC_DIRECT_PPO_DESIGN_20261011.md다.
'''
    (out/'README.md').write_text(text,encoding='utf-8')
    # Standalone review page with exact CSV-style summary; no browser claim.
    import html
    body=''.join('<tr>'+''.join('<td>'+html.escape(str(x[k]))+'</td>' for k in ('policy','completed','urgent_failure','normal_failure','urgent_p95_mean_ms','energy_mean_j','peak_ap_mean_c'))+'</tr>' for x in summary)
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>전체 큐 PPO 비교</title><style>body{font:16px Malgun Gothic,sans-serif;max-width:1200px;margin:40px auto;color:#14213d}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}th{background:#edf4fa}img{max-width:100%}</style><h1>전체 큐 직접 PPO 비교</h1><p>개발 선정 '+html.escape(selected)+' · 새 strict 판정은 README와 verdict.json 참고 · PC 모형 결과</p><p><a href="README.md">한국어 보고서</a> · <a href="comparison.csv">48조건 전체 표</a> · <a href="paired_deltas.csv">조건별 손해</a></p><table><tr><th>정책</th><th>완료</th><th>긴급 실패</th><th>일반 실패</th><th>P95 평균 ms</th><th>J 평균</th><th>AP peak 평균 °C</th></tr>'+body+'</table><img src="service_comparison.png"><img src="cost_comparison.png"></html>',encoding='utf-8')
    return dict(summary=summary,learning=learning,verification=verification,selected=selected)

def chart(out,rr,selected):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=[r['policy'] for r in rr];x=np.arange(len(rr));colors=['#bf4938' if r['policy']==selected else '#3b7597' for r in rr]
    fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
    for ax,k,title in zip(axes,('urgent_failure','normal_failure','urgent_p95_mean_ms'),('Urgent deadline failures (all arrivals)','Normal deadline failures (all arrivals)','Mean of per-condition urgent P95 (ms)')):
        ax.bar(x,[r[k] for r in rr],color=colors);ax.set_title(title);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[-1].set_xticks(x,labels,rotation=50,ha='right');fig.suptitle('A24 frozen model / 48 paired conditions / selected in red');fig.tight_layout();fig.savefig(out/'service_comparison.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for ax,k,title in zip(axes,('energy_mean_j','peak_ap_mean_c'),('Mean whole 120s energy (J)','Mean per-condition AP peak 35..180s (C)')):
        values=[r[k] for r in rr];ax.bar(x,values,color=colors);ax.set_title(title)
        margin=.004 if k=='peak_ap_mean_c' else .09
        ax.set_ylim(min(values)-margin,max(values)+margin);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        for pos,value in enumerate(values):ax.text(pos,value+margin*.1,f'{value:.3f}',ha='center',va='bottom',fontsize=8)
    axes[-1].set_xticks(x,labels,rotation=50,ha='right');fig.suptitle('Model estimates: truncated cost axes / service gate required');fig.tight_layout();fig.savefig(out/'cost_comparison.png',dpi=140);plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('--main',type=Path,required=True);p.add_argument('--aux',type=Path);p.add_argument('--output',type=Path,required=True);x=p.parse_args()
    print(json.dumps(s.serial(report(x.main,x.aux,x.output)),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
