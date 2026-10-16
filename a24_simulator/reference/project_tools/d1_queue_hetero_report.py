"""Saved episodes only: integrity audit, paired results and static deliverables."""
import argparse,collections,csv,gzip,json,math,shutil,subprocess
from pathlib import Path
import numpy as np
import time,torch
from tools import d1_queue_hetero_study as s

METRICS=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
def csv_file(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def stat(values):
    return dict(n=len(values),mean_ms=float(np.mean(values))*1000,p95_ms=float(np.quantile(values,.95,method='higher'))*1000,max_ms=max(values)*1000) if values else dict(n=0,mean_ms=None,p95_ms=None,max_ms=None)
def summary(rr,policy,factor):
    q=[r for r in rr if r['policy']==policy and (factor=='all' or r['factor']==factor)]
    eligible=[r for r in q if r['energy_j'] is not None and r['peak_ap_c'] is not None]
    p95=[r['urgent_p95_ms'] for r in q if r['urgent_p95_ms'] is not None]
    result=dict(policy=policy,factor=factor,conditions=len(q),planned=sum(r['planned'] for r in q),completed=sum(r['completed'] for r in q),incomplete=sum(r['incomplete'] for r in q),planned_work_units=sum(r['planned_work_units'] for r in q),completed_work_units=sum(r['completed_work_units'] for r in q),urgent_failure=sum(r['urgent_failure'] for r in q),normal_failure=sum(r['normal_failure'] for r in q),urgent_original_cap_failure=sum(r['urgent_original_cap_failure'] for r in q),normal_original_cap_failure=sum(r['normal_original_cap_failure'] for r in q),urgent_p95_mean_ms=float(np.mean(p95)) if p95 else None,eligible_cost_cases=len(eligible),energy_mean_j=float(np.mean([r['energy_j'] for r in eligible])) if eligible else None,peak_ap_mean_c=float(np.mean([r['peak_ap_c'] for r in eligible])) if eligible else None)
    return result

def report(folder,out,s26):
    reg=s.check(folder);cursor=s.budget.read(folder/'cursor.json')
    if not cursor['completed']:raise ValueError('confirmation not complete; no interim final report')
    freeze=s.budget.read(folder/'freeze.json');verdict=s.budget.read(folder/'verdict.json')
    roles=[*s.BASES,*freeze['selections']];rr=s.rows(folder,'confirmation_')
    expected={(i,role) for i in range(48) for role in roles}
    if len(rr)!=len(expected) or {(r['condition'],r['policy']) for r in rr}!=expected:raise ValueError('incomplete/duplicate final matrix')
    out.mkdir(parents=True,exist_ok=True);csv_file(out/'comparison.csv',rr)
    summaries=[summary(rr,role,factor) for factor in s.FACTORS for role in roles]
    csv_file(out/'summary_by_factor.csv',summaries);csv_file(out/'summary_all.csv',[summary(rr,role,'all') for role in roles])
    by={(r['condition'],r['policy']):r for r in rr};deltas=[]
    for role in roles:
        if role in s.BASES:continue
        for condition in range(48):
            q=by[condition,role]
            for baseline in ('FIFO_FIXED','FIFO_EFT','FIFO_READY','RuleEDD','RuleATC'):
                b=by[condition,baseline];d={k:q[k]-b[k] if q[k] is not None and b[k] is not None else None for k in METRICS}
                deltas.append(dict(condition=condition,factor=q['factor'],family=q['family'],policy=role,baseline=baseline,**d,all_axes_nonworse=all(v is not None and v<=0 for v in d.values())))
    csv_file(out/'paired_deltas.csv',deltas)
    original_caps={}
    for role in freeze['selections']:
        bank=role.split('_')[0];items=[]
        for condition in range(48):
            q=by[condition,role]
            for ref in ('FIFO_FIXED','FIFO_EFT','Rule'+bank):
                b=by[condition,ref]
                delta={name:q[name]-b[name] for name in ('urgent_original_cap_failure','normal_original_cap_failure')}
                items.append(dict(condition=condition,factor=q['factor'],reference=ref,delta=delta,nonworse=all(v<=0 for v in delta.values())))
        original_caps[role]=dict(original_cap_nonworse_all=all(x['nonworse'] for x in items),differences=items)
    s.write(out/'original_cap_guard_auxiliary.json',dict(scope='posthoc additional conservative audit; registered tighter-deadline strict verdict unchanged',registered_before_final=False,roles=original_caps))
    for name in ('registration.json','freeze.json','verdict.json','consumption.json','bank_gate.json','pause_receipt.json','resume_receipt.json','stage128.json','stage256.json','source_repair.json'):
        if (folder/name).exists():shutil.copyfile(folder/name,out/name)
    dev=s.rows(folder,'controls_')+s.rows(folder,'dev');csv_file(out/'development.csv',dev)
    csv_file(out/'development_summary.csv',[dict(stage=stage,**summary([q for q in dev if q['phase']==stage],role,'all')) for stage in ('controls','dev128','dev256') for role in sorted({q['policy'] for q in dev if q['phase']==stage})])
    learning=[]
    for role in freeze['selections']:
        bank,seed=role.split('_');l=s.learning.Learner.load(s.learner_path(folder,bank,int(seed)),s.deps(reg,bank));selected=freeze['selections'][role]
        if s.budget.digest(s.learner_path(folder,bank,int(seed),selected['episodes']))!=selected['sha256']:raise ValueError('selected weights changed')
        row=dict(policy=role,episodes=l.episodes,updates=len(l.logs),Adam_steps=l.steps,pending=len(l.pending),selected_episodes=selected['episodes'],all_actor_changed=all(x['actor_changed'] for x in l.logs),all_gradients_finite_positive=all(math.isfinite(x['actor_gradient_max']) and x['actor_gradient_max']>0 for x in l.logs),strict='PASS' if verdict[role]['promising'] else 'FAIL')
        learning.append(row);s.write(out/f'learning_{role}.json',dict(summary=row,updates=l.logs,selection=selected))
    csv_file(out/'learning.csv',learning)
    if not (out/'queue_scaling_calculation.csv').exists():
        bank,seed=freeze['selected'].split('_')
        l=s.learning.Learner.load(s.learner_path(folder,bank,int(seed),freeze['selections'][freeze['selected']]['episodes']),s.deps(reg,bank))
        csv_file(out/'queue_scaling_calculation.csv',calculation_benchmark(l.network,bank))
    timings=collections.defaultdict(list);qtime=collections.defaultdict(list);diagnostics=collections.defaultdict(collections.Counter);ticket_hash={};audits=0;totalitems=0;maxq=0;physical_templates=collections.Counter()
    for receipt in sorted((folder/'rows').glob('*.json')):
        row=s.budget.read(receipt);rawpath=folder/'items'/(receipt.stem+'.json.gz')
        if s.budget.digest(rawpath)!=row['raw_sha256']:raise ValueError('raw SHA changed')
        totalitems+=1
        if not receipt.name.startswith('confirmation_'):continue
        raw=json.loads(gzip.decompress(rawpath.read_bytes()));q=raw['row'];role=q['policy'];factor=q['factor']
        s.audit_ledger(raw['result']);audits+=1
        if q['planned_work_units']!=sum(r['work_units'] for r in raw['result']['ledger']):raise ValueError('work-unit denominator changed')
        if q['completed']==q['planned'] and q['completed_work_units']!=q['planned_work_units']:raise ValueError('work completion mismatch')
        tickets=[{k:r[k] for k in sorted(s.a.PUBLIC_FIELDS)} for r in raw['result']['ledger']]
        digest=s.a.native.digest(tickets);case=q['condition']
        if case in ticket_hash and ticket_hash[case]!=digest:raise ValueError('paired public requests differ')
        ticket_hash[case]=digest
        public_by={r['id']:r for r in tickets}
        for event in raw['events']:
            if 'ticket' in event and set(event['ticket'])!=s.a.PUBLIC_FIELDS:raise ValueError('private ticket event')
        for cb in raw['callbacks']:
            timings[role,'all_callback'].append(cb['seconds']);timings[role,'event_to_dispatch_with_modeled_observe'].append(cb['event_to_dispatch_seconds'])
        for snap in raw['snapshots']:
            d=diagnostics[factor];d['decisions']+=1;d['rank_different']+=not snap['raw_rank_same'];d['bank_different']+=not snap['ATC_EDD_same'];d['legal_different']+=not snap['ATC_EDD_legal_actions_same'];d['rule_choice_different']+=not snap['same_bank_rule_choice_same'];d['nonhead_selected']+=snap['nonhead_selected'];maxq=max(maxq,snap['queue_size'])
            actions=snap['actions'];mask=snap['mask'];chosen=snap['chosen']
            if not mask[chosen]:raise ValueError('selected masked')
            if len(snap['state'])!=214 or len(snap['candidates'])!=32 or any(len(v)!=53 for v in snap['candidates']):raise ValueError('raw ABI changed')
            if snap['online_forecast_calls']!=0:raise ValueError('forecast input')
            templates=set()
            for action,legal in zip(actions,mask):
                if not action or not legal:continue
                template=('resource_wait',) if action['kind']=='resource_wait' else (action['kind'],tuple(sorted((public_by[j['request_id']]['task'],j['backend']) for j in action['jobs'])))
                templates.add(template)
            physical_templates[role]+=len(templates)>1
        for times in raw['stage_times']:
            for name,value in times.items():
                if name.endswith('_seconds'):timings[role,name].append(value)
                if name=='inference_seconds' and value>0:timings[role,'pure_forward_calls_only'].append(value)
            n=times['queue'];key='1' if n<=1 else '2-4' if n<=4 else '5-8' if n<=8 else '9-16' if n<=16 else '17+'
            qtime[role,key].append(times.get('actual_total_seconds',times['total_seconds']))
    csv_file(out/'decision_times.csv',[dict(policy=role,component=k,**stat(v)) for (role,k),v in sorted(timings.items())])
    csv_file(out/'observed_queue_times.csv',[dict(policy=role,queue_bin=k,**stat(v)) for (role,k),v in sorted(qtime.items())])
    s.write(out/'bank_diagnostics.json',{factor:dict(v) for factor,v in diagnostics.items()})
    s.write(out/'physical_template_diagnostics.json',dict(physical_templates))
    # Matched units do not guarantee matched realized seconds: calculate private demands post hoc.
    cases=s.budget.read(folder/'inputs.json')['confirmation'];demands=[]
    for case in cases:
        vs=s.realizations(case['requests'],case['arrival_seed']);cpu=split=0.;cpu_exec=split_exec=0.
        for q in case['requests']:
            def vector(b):return vs['requests'][q['id']][b][s.engine.keyed_index(s.REALIZATION,q['id'],b)]['durations_ns']
            c=vector('CPU');b='GPU' if q['task']=='classification' else 'CPU';v=vector(b)
            cpu+=sum(c)/1e9;split+=sum(v)/1e9;cpu_exec+=c[1]/1e9;split_exec+=v[1]/1e9
        demands.append(dict(condition=case['condition'],family=case['family'],factor=case['factor'],arrival_seed=case['arrival_seed'],planned_work_units=sum(q['work_units'] for q in case['requests']),all_CPU_private_demand_s=cpu,fixed_split_private_demand_s=split,all_CPU_executing_block_s=cpu_exec,fixed_split_executing_block_s=split_exec,scope='posthoc workload sums; not online policy input or queued future execution'))
    csv_file(out/'realized_workload_demands.csv',demands)
    s26receipt=s26_audit(s26);s.write(out/'S26_P1L_AUDIT.json',s26receipt)
    # Audit all old sources captured before this task; never modify prior study artifacts.
    protected=s.ROOT.parent/'QUEUE-HETERO-PPO-03-protected.json'
    for path,sha in s.budget.read(protected).items():
        if s.budget.digest(s.ROOT/path)!=sha:raise ValueError('prior source changed '+path)
    usage=s.budget.read(folder/'consumption.json')
    verification=dict(status='PASS_saved_integrity_matrix_physics',successful_raw_items=totalitems,confirmation_items=audits,expected_matrix=len(expected),all48_public_tickets_exact_across_roles=True,registered_policy_learning_sources_unchanged=True,driver_output_repair=s.budget.read(folder/'source_repair.json'),driver_in_initial_source_registration=True,selected_weight_hashes_unchanged=True,phase_response_actual_AVAILABLE_supported_pairs_audited=True,work_unit_denominators_checked=True,max_observed_waiting_queue=maxq,physical_template_multiple_decisions=dict(physical_templates),unit_tests=dict(preflight=8,output_and_source_guard=2,total=10),prior_sources_unchanged=True,counts=usage,model_fit=0,S26_environments=0,S26_learning=0,device=0,decision_time_scope='PC running alongside independent sibling workload; no inference about phone or energy',bank_equivalence='action signature and legal mask comparison; encoder structural inference, not direct bitwise comparison of shadow tensors',new_environments_in_report=0,new_learning_in_report=0)
    s.write(out/'verification.json',verification)
    chart(out,summaries,freeze['selected'])
    readme(out,summaries,learning,freeze,verdict,usage,diagnostics)
    return dict(status='complete_report',selected=freeze['selected'],roles=len(roles),rows=len(rr),usage=usage,strict={k:'PASS' if v['promising'] else 'FAIL' for k,v in verdict.items()})

def calculation_benchmark(network,bank):
    torch.set_num_threads(1);network.eval();f,i,_=s.a.hybrid.load();c=s.a.Controller(f,i['initial'])
    lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')};rows=[]
    for n in (1,8,32,128,512):
        qs=[dict(id=f'bench{i}',ordinal=i,task='classification' if i%2 else 'detection',priority='urgent' if i%2 else 'normal',arrival_ns=35_000_000_000,deadline_offset_ns=1_500_000_000 if i%2 else 6_000_000_000,work_units=1+i%3) for i in range(n)]
        times=collections.defaultdict(list)
        for attempt in range(55):
            start=time.perf_counter();e=s.a.bank(qs,lanes,35e9,c.estimates,sequencing=bank);built=time.perf_counter();x=c.encode(qs,lanes,35e9,e);encoded=time.perf_counter()
            with torch.no_grad():network(torch.from_numpy(x['state'])[None],torch.from_numpy(x['candidates'])[None],torch.from_numpy(x['mask'])[None])
            end=time.perf_counter()
            if attempt<5:continue
            for key,value in e['timings'].items():times[key].append(value)
            times['encode_seconds'].append(encoded-built);times['pure_forward_seconds'].append(end-encoded);times['calculation_total_seconds'].append(end-start)
        rows += [dict(queue=n,component=key,**stat(values),scope='PC synthetic current queue calculation 5warmup+50; no simulation/learning, shared-host concurrency') for key,values in times.items()]
    return rows

def s26_audit(root):
    pinned=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if not pinned.startswith('5bdc13c1'):raise ValueError('S26 handoff commit changed')
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD','d1sim/parsim_v1'],cwd=root,text=True).splitlines()
    hashes={}
    for path in tracked:
        data=subprocess.check_output(['git','show','HEAD:'+path],cwd=root)
        hashes[path]=dict(bytes=len(data),sha256=s.hashlib.sha256(data).hexdigest())
    commits={}
    for prefix in ('2f31deac','c4eae394','83d86332','5bdc13c1'):
        full=subprocess.check_output(['git','rev-parse',prefix],cwd=root,text=True).strip()
        if subprocess.run(['git','merge-base','--is-ancestor',full,pinned],cwd=root).returncode:raise ValueError('handoff ancestor chain')
        commits[prefix]=full
    judge=json.loads(subprocess.check_output(['git','show','HEAD:d1sim/parsim_v1/out/parsim_judge.json'],cwd=root))
    profile=json.loads(subprocess.check_output(['git','show','HEAD:d1sim/profiles/parsim_v1_thermal_sum.json'],cwd=root))
    return dict(status='PASS_source_and_reported_judgement_audit_only',pinned_commit=pinned,reported_commits=commits,canonical_git_blob_hashes=hashes,judge=judge,profile=profile,service='exploration_only_short_mixed',thermal='not_reproduced_C_and_S',energy_eligible=False,CPU_throttle='assumed_none',three_resources='extrapolation_excluded',adapter_future_times='private environment only; never policy observation',A24_S26_stage_boundary_direct_mapping=False,CPU1_CG_DC_distribution_exists=True,new_environments=0,new_learning=0,new_fit=0,device_runs=0)

def fmt(value,digits=3):return '미산출' if value is None else f'{value:.{digits}f}'
def readme(out,summary_rows,learning,freeze,verdict,usage,diag):
    selected=freeze['selected'];parts=[]
    names=dict(single_fixed='단일 이미지·기존 납기',single_deadlines='단일 이미지·가변 납기',batch_uniform2='2장 고정 묶음·가변 납기 — 합성',batch_variable='1~3장 가변 묶음·가변 납기 — 합성')
    for factor in s.FACTORS:
        q=[x for x in summary_rows if x['factor']==factor]
        lines='\n'.join(f"|{r['policy']}|{r['completed']}/{r['planned']}|{r['completed_work_units']}/{r['planned_work_units']}|{r['urgent_failure']}|{r['normal_failure']}|{fmt(r['urgent_p95_mean_ms'],1)}|{fmt(r['energy_mean_j'])}|{fmt(r['peak_ap_mean_c'],4)}|{r['eligible_cost_cases']}/{r['conditions']}|" for r in q)
        parts.append(f"### {names[factor]}\n\n|정책|요청 완료/도착|작업단위 완료/계획|요구 긴급 실패|요구 일반 실패|긴급P95 평균 ms|J120 평균|AP peak 평균 °C|비용 유효 조건|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n{lines}\n")
    lp='\n'.join(f"|{x['policy']}|{x['episodes']}|{x['updates']}|{x['Adam_steps']}|{x['selected_episodes']}|{x['strict']}|" for x in learning)
    text=f'''# 처리시간·납기 다양화 EDD / ATC / PPO 비교

2026-10-11. 작업 **QUEUE-HETERO-PPO-03**. A24 실측 기반 PC 시뮬레이션과 명시한 합성 작업량 감도이며 새 휴대폰 실험은 아니다. 세 전문가 검토·새 ABI·fresh learner·개발선택·동결·새48 확인을 완료했다. 개발에서 선정한 모델은 **{selected}@{freeze['selections'][selected]['episodes']}**다. 새 strict 결과는 **{', '.join(k+':'+('PASS' if v['promising'] else 'FAIL') for k,v in verdict.items())}**다. 기본 정책/experiment_ready=false를 유지하며 자동채택하지 않는다.

**이번에는 ATC와 EDD의 실제 후보와 결과가 달랐지만, PPO의 전조건 우위는 확보하지 못했다.** 전체 RuleATC 완료는3027/3168로 RuleEDD3001보다26건 많으나 완료 작업단위는4413/4752로 RuleEDD4415보다2단위 적었다. 선정 PPO는3019건·4397단위 완료로 RuleATC보다 미완료가8건 많고 긴급P95 평균도56.958ms 높다. 작은 요청 우선과 총 작업량·긴급서비스 사이의 상충을 구분한다.

## 이번 변경과 현실성

실측자료는 ABBA4 requests.csv의384개5phase(C_CPU4/C_GPU188/D_CPU192)다. 요청별 전체 구간을 숨긴 bootstrap으로 실제 처리시간을 다양화했다. 정책은 선택된 실현처리시간을 읽지 않고 task/backend/사전에 선언한 작업단위와 이미 완료한 관측으로 추정한다. CPU4표본은 작고 기존자료를 재사용하므로 실제 모바일 모집단/새기기 독립 확인을 입증하지 않는다.

원자료 점유시간 범위는 분류CPU169.571~186.262ms(4표본), 분류GPU230.886~391.504ms(188), 탐지CPU605.110~656.022ms(192)다. 이 범위를 단일입력의 숨은 변동에 사용했다. 2·3장 구간은 이 원자료의 EXECUTING 블록을 배수한 합성 값이며 그 처리시간을 기기에서 측정했다고 주장하지 않는다.

원 기한 U1.5/N6초에 더해 공개 요청 납기를 U0.5/1/1.5·N2/4/6초로 다양화했다. 이 값은 기존상한보다 강화한 연구가정이며 산업표준 실측 SLA가 아니다. 강화 요구 실패와 기존상한 실패를 comparison.csv에 따로 보고한다.

단일이미지 고정/가변 납기는 실측변동 주분석이다. 공개 n2와 n1/2/3 묶음은 현재앱 미구현/미측정 **합성 감도**다. `execution_start→output_ready` 구간 전체만 n배, 나머지4구간·추가aggregation 비용은 고정가정이다. 순수invoke n배 또는 batch측정으로 부르지 않는다. 두 batch군은 task별 총units가정확히같지만 숨은잔차의가중합때문에 실제총처리초는같지않다. realized_workload_demands.csv에 사후 처리량을 기록했다. 단일→묶음에는부하량증가도있고 전체변화를순수이질성효과로해석하지않는다.

## 개발·학습·최종 선택

개발32의5,227판단에서 ATC/EDD raw rank차2,519·bank차1,973·legal차302를관측해각bank3seed를학습했다. 같은작업이라도공개작업량과납기가달라질때후보차이가생겼다. bank비교는action signature/mask를직접비교하며shadow encoder전체배열bitwise검사는하지않았다. 후보/slot와입력특징의구조적연결을단위검사한다.

state214/action53/pad32, request/각job에work_units 힌트를바인딩했다. 관측phase2/n으로기저EMA를갱신해이중배수를막았다. 실제AVAILABLE/비선점/CG_DC/max2/응답완료분리·자원대기만유지하고NPU/냉각/전체큐미래예측을추가하지않았다. 모든policy선택에old rollout/place/futureAPJ trap을적용했다.

train256(16arrival×4부하×4factor)/learner, dev32/최종새48(3arrival×4×4). 원데이터분포는공유하지만새도착/실현seed와학습·확인자료를분리했다.128/256의개발서비스lexicographic로각seed checkpoint를선정하고대표bank/seed를최종자료전SHAfreeze,확인은masked argmax다. 운영에서도가중치고정/추론만이다. 전seed결과를공개하고holdout후재튜닝하지않았다.

모든 모델의 개발32에는 미완료 조건이 있어 E/AP 평균 선정 key는 infinity(출력 UNAVAILABLE)였다. 실제 모델 선정은 I/U/N/P95가 결정했고 비용 key는 모델 구분에 기여하지 못했다. AP/J 학습 label은 모델마다224/256 episode에서 유효했으므로 비용 학습을 전혀 하지 않았다는 뜻은 아니다.

|모델|학습episode|update|Adam step|개발 선택episode|strict|
|---|---:|---:|---:|---:|---|
{lp}

새목적은 APinterval/1°C, (J−상주baseline)/100J·가중치1, I/U/N실패율승수초기10, urgentP95/1500ms다. 이전J/1J보다에너지상대가중치도낮아진새목적이며critic만조정했다고부르지않는다. 새목적·상태·학습량도다르므로이전512결과와의차이를부하이질성한요인에귀속하지않는다.

## 새48조건 결과

각factor는12조건이며P95/J/AP열은조건별KPI평균이다(pooled P95아님). 실패는전체도착기준응답누락/요구기한초과다. 완료와기한내응답은별개이며미완료를제외해성공으로바꾸지않는다. J/AP는전량완료조건만유효하여분모를함께표시한다. 다른비용유효조건집합의평균을직접우위로쓰지않고전조건paired strict를따른다.

{chr(10).join(parts)}

![서비스 비교](service_by_factor.png)
![비용 비교](cost_by_factor.png)

## 판정·계산 비용·한계

strict는모든48조건에서FIFO_FIXED/FIFO_EFT/같은bankRule 각각과완료/U/N/P95/J/AP 비악화ε0,low/sustained의절대서비스실패0,low또는sustained의전짝J/AP한축엄격개선이다. 요구납기를강화하고원cap실패도따로표시했으며원V2 FAIL을재판정하지않는다. 평균개선만으로불리조건을숨기지않는다. 조건별차이·strict사유는paired_deltas.csv/verdict.json이다.

강화 기한의 실패 합 비교는 기존1.5/6초 실패 합의 비악화와 수학적으로 동치가 아니다. 예를 들어 선정 PPO는 RuleATC보다 강화 긴급 실패가189 vs190으로1건 적지만 기존1.5초 실패는18 vs14로4건 많다. 원등록 strict를 사후 바꾸지 않고 전6 FAIL을 유지하며, original_cap_guard_auxiliary.json으로 기존 상한의 조건별 비악화를 별도 보수 감사했다. 이 보조 guard는 최종자료 뒤 추가한 점검이지 사전 등록된 별도 성공 판정이 아니다. 다음 실행 계약에서는 두 기한의 비교를 모두 채택 조건에 명시해야 한다.

decision_times.csv는ATC계산·후보·mask·encode·network forward·판단실제전체·shadow진단제외/포함·earlyreturn포함callback·관측과공개사건포함event→dispatch의평균/P95/최댓값이다. observed_queue_times.csv는실제Q구간별이다. EDD bank도ATC진단을계산해해당계측비용을구분한다. PC에서는동시에별도연구작업이돌아공유호스트시간변동이있었으며phone추론시간·소비전력/기기에너지로환산하지않는다. 해당타이밍은이번PC환경기술이며통제된성능벤치라고부르지않는다.

inference_seconds는모델을호출하지않은강제행동의0을포함한판단당비용이고,pure_forward_calls_only는실제로network를호출한양수표본만의평균/P95/최댓값이다. 각각표본수를함께보고한다.

queue_scaling_calculation.csv는Q1/8/32/128/512의현재인공큐에대한5warmup+50계산표본이다. 시뮬레이션환경/학습0이며큰Q를실제앱에서관측했다는뜻이아니다. 후보·마스크·순수forward등과실제eventcallback의모집단을구분한다.

원frozen J/AP의batch점유전이·CPU4표본·현재fixedtensor·일반화되지않은공개n예측·가상aggregation·기기오차가한계다. 물리mask는납기보장이아니며finitegradient는수렴/학습이득의증거가아니다. 별도기존 HETERO-DIRECT-PPO-03는공개I/O가정/다른seed/다른납기를쓰는동시작업이며소스/원장을보존했지만이번결과와합치지않았다.

## S26 P1l 참고 결과

보고한4commit과연결5bdc13c1에분리checkout을고정하고모델카드/adapter/CSV/Gitblob/expectedSHA/원판정을정적으로확인했다. **mixedCPU1 EffNet/Det와분류GPU+탐지CPU의R3처리시간분포·연결코드가있음은확인됐다.** 서비스는짧은혼합부하탐색용,열(C/S)은미재현,CPU지속조임/DVFS는없고CPU4전력근사여서에너지적격이아니다. 자료부재와모형적격문제를구분하며새S26학습/환경/fit/기기는0이다.

adapter의state lane_available와dispatch의6미래실현시각은정책입력으로사용하면oracle누수다. 환경private로보관하고현재발생한단계만공개해야한다. 현재라이브러리는NPU/3자원도포함해우리지원/중복ID/max2 wrapper가필요하다. A24의5phase와S26의host-inference/return5tuple경계가달라durations=를단순전달하지않는다. 실제APK/source·품질/정밀도·시계남은증거와열/J적격은별도다. 근거는 S26_P1L_AUDIT.json과모바일전문가보고서다.

## 실행 증분과 산출물

이번 작업 환경시작 **{usage['environments']}**, 새학습 **{usage['learning']}**, 실패 환경 **{usage['failed']}**, 누적활성 **{usage['active_seconds']:.3f}초**다. 상한3200/1536/3600초·저장300초를유지했다. 단위10PASS(초기8+저장/guard2)와실제59학습뒤6모델Adam/partial/RNG/clock exact재개는원장과receipt에있다.128단계 개발메타데이터의미산출비용Infinity를JSON에쓰려는저장작업1회가실패했다. 원등록/sourcearchive를보존하고 UNAVAILABLE출력표현·effectiveSHA검사만수정,policy/학습식/weights/Adam/RNG/기한/선정계산/소비변경0으로재개했다. 환경실패로계산하거나기존경험을재실행하지않았다. source_repair.json에원/수정SHA와시점을남겼다. 과거2400/1536+289/0 및동시다른연구의소비를덮거나합산하지않았다. 이번새물리fit/S26환경/학습/APK/ADB/기기각0이다.

- [전체 비교](comparison.csv), [factor별 요약](summary_by_factor.csv), [기존 기한 상한 포함 요약](summary_all.csv), [조건별 차이](paired_deltas.csv)
- [개발 자료](development.csv), [개발 요약](development_summary.csv), [학습/선택](learning.csv), [동결](freeze.json), [판정](verdict.json)
- [실행 검증](verification.json), [등록](registration.json), [원장 소비](consumption.json), [중지/재개](resume_receipt.json), [S26 감사](S26_P1L_AUDIT.json)
- [설계](QUEUE_HETERO_PPO_DESIGN_20261011.md), [모바일](experts/mobile_review.md), [산업공학](experts/ie_review.md), [RL AI](experts/rl_review.md)

원raw/완전checkpoint/원장은 work/QUEUE-HETERO-PPO-03에보존했다. 산출물은저장결과만재집계했고추가학습/환경0이다. Android기본교체나GitHub게시를실행하지않았다.
'''
    (out/'README.md').write_text(text,encoding='utf-8',newline='\n')

def chart(out,rows,selected):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    roles=[*s.BASES,*[r for r in dict.fromkeys(q['policy'] for q in rows) if r not in s.BASES]]
    fig,axs=plt.subplots(4,3,figsize=(19,15))
    for i,factor in enumerate(s.FACTORS):
        q=[next(r for r in rows if r['factor']==factor and r['policy']==role) for role in roles]
        for j,key in enumerate(('urgent_failure','normal_failure','urgent_p95_mean_ms')):
            ax=axs[i,j];ax.bar(range(len(q)),[r[key] if r[key] is not None else 0 for r in q],color=['#bf4938' if r['policy']==selected else '#377697' for r in q]);ax.set_title(factor+' / '+key);ax.set_xticks(range(len(q)),roles,rotation=65,ha='right',fontsize=7);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('A24 empirical residual + declared synthetic work / 12 paired conditions per factor / selected red');fig.tight_layout();fig.savefig(out/'service_by_factor.png',dpi=130);plt.close(fig)
    fig,axs=plt.subplots(4,2,figsize=(16,14))
    for i,factor in enumerate(s.FACTORS):
        q=[next(r for r in rows if r['factor']==factor and r['policy']==role) for role in roles]
        for j,key in enumerate(('energy_mean_j','peak_ap_mean_c')):
            ax=axs[i,j];vals=[r[key] if r[key] is not None else np.nan for r in q];ax.bar(range(len(q)),vals,color=['#bf4938' if r['policy']==selected else '#377697' for r in q]);ax.set_title(factor+' / '+key+' (complete cases only)');ax.set_xticks(range(len(q)),[r['policy']+f" [{r['eligible_cost_cases']}/12]" for r in q],rotation=65,ha='right',fontsize=7);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
            finite=[v for v in vals if math.isfinite(v)]
            if finite:margin=max((max(finite)-min(finite))*.2,.02 if j else .1);ax.set_ylim(min(finite)-margin,max(finite)+margin)
    fig.suptitle('Frozen-model costs / truncated axes / eligible completion denominator in brackets; strict gate required');fig.tight_layout();fig.savefig(out/'cost_by_factor.png',dpi=130);plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--s26',type=Path,required=True);x=p.parse_args()
    print(json.dumps(s.serial(report(x.run_root,x.out,x.s26)),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
