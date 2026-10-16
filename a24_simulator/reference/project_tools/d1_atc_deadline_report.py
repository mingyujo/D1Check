"""Read-only saved-trajectory comparisons, complete-work means and old strict diagnostics."""
import gzip
import json
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np

from tools import d1_atc_waitlink_report as helpers
from tools import d1_atc_deadline_study as s


COSTS=("energy_j","mean_ap_120_c","mean_ap_180_c","peak_ap_c")
METRICS=(*s.SERVICE,*COSTS)


def finite(v):return v is not None and bool(np.isfinite(float(v)))


def service_failure(row):
    required=('planned','completed','planned_work_units','completed_work_units',*(key for key in s.SERVICE if key!='urgent_p95_ms'))
    missing=[key for key in required if not finite(row.get(key))]
    if missing:return True,missing
    failed=(row['completed']!=row['planned'] or row['completed_work_units']!=row['planned_work_units'] or any(row[key] for key in s.SERVICE if key!='urgent_p95_ms'))
    return failed,[]


def aggregate(values):
    """Whole-scope mean stays unavailable if any paired/equal-work metric is missing."""
    good=[v for v in values if finite(v)]
    return dict(valid=len(good),missing=len(values)-len(good),
                mean=float(np.mean(good)) if len(good)==len(values) and good else None,
                complete_conditional_mean=float(np.mean(good)) if good else None)


def summary(rows):
    by=defaultdict(list)
    for row in rows:by[row['policy']].append(row)
    out=[]
    for role,q in by.items():
        def total(key):return sum(r[key] for r in q) if all(finite(r.get(key)) for r in q) else None
        item=dict(role=role,conditions=len(q),planned=total('planned'),completed=total('completed'),
            planned_work_units=total('planned_work_units'),completed_work_units=total('completed_work_units'),
            urgent_planned=total('urgent_planned'),normal_planned=total('normal_planned'),
            incomplete=total('incomplete'),U=total('urgent_failure'),N=total('normal_failure'),
            Ucap=total('urgent_original_cap_failure'),Ncap=total('normal_original_cap_failure'),
            service_unknown_conditions=sum(bool(service_failure(r)[1]) for r in q))
        for alias,key in (('P95','urgent_p95_ms'),('J','energy_j'),('AP','peak_ap_c'),('meanAP120','mean_ap_120_c'),('meanAP180','mean_ap_180_c')):
            result=aggregate([r.get(key) for r in q])
            item[alias]=result.pop('mean');item.update({alias+'_'+k:v for k,v in result.items()})
        item['cost_valid']=item['J_valid'];out.append(item)
    return out


def scope_rows(rows,scope):
    if scope=='full':return rows
    return [r for r in rows if r['primary' if scope=='primary' else 'release_domain']]


def paired_row(row,reference,**meta):
    item=dict(condition=row['condition'],family=row['family'],factor=row['factor'],primary=row['primary'],release_domain=row['release_domain'],**meta)
    for key in METRICS:item['delta_'+key]=row[key]-reference[key] if finite(row.get(key)) and finite(reference.get(key)) else None
    return item


def paired_summary(rows):
    groups=defaultdict(list)
    for row in rows:
        for scope in ('full','primary','release'):
            if scope!='full' and not row['primary' if scope=='primary' else 'release_domain']:continue
            groups[row['seed'],row['reward_arm'],row['comparison'],scope].append(row)
    out=[]
    for (seed,arm,comparison,scope),q in groups.items():
        item=dict(seed=seed,reward_arm=arm,comparison=comparison,scope=scope,conditions=len(q))
        for key in METRICS:
            raw=[row['delta_'+key] for row in q];valid=[v for v in raw if finite(v)];agg=aggregate(raw)
            item.update({key+'_wins':sum(v<0 for v in valid),key+'_ties':sum(v==0 for v in valid),key+'_losses':sum(v>0 for v in valid),
                key+'_mean_delta':agg['mean'],key+'_complete_conditional_mean_delta':agg['complete_conditional_mean'],
                key+'_missing':agg['missing'],key+'_valid':agg['valid'],key+'_worst_delta':max(valid) if valid else None})
        out.append(item)
    return out


def pareto_by_scope(rows):
    """Mean-cost Pareto is descriptive and does not establish conditionwise dominance."""
    out=[]
    for scope in ('full','primary','release'):
        scoped=scope_rows(rows,scope);items=[]
        for item in summary(scoped):
            q=[r for r in scoped if r['policy']==item['role']]
            eligible=all(not service_failure(r)[0] for r in q)
            vector=[item['J'],item['meanAP180'],item['AP']]
            valid=all(finite(v) for v in vector)
            items.append(dict(scope=scope,role=item['role'],conditions=len(q),absolute_service_eligible=eligible,cost_finite=valid,
                mean_J=vector[0],mean_AP_time180=vector[1],mean_AP_peak180=vector[2],vector=vector))
        pool=[dict(v) for v in items if v['absolute_service_eligible'] and v['cost_finite']]
        for item in items:
            dominators=[p['role'] for p in pool if p['role']!=item['role'] and all(x<=y for x,y in zip(p['vector'],item['vector'])) and any(x<y for x,y in zip(p['vector'],item['vector']))] if item in pool else []
            item.pop('vector');item.update(mean_pareto=not dominators if item['absolute_service_eligible'] and item['cost_finite'] else None,dominated_by=dominators,conditionwise_dominance_claim=False);out.append(item)
    return out


def validate_means(raw,row):
    complete=row['completed']==row['planned'] and row['completed_work_units']==row['planned_work_units']
    for end in (120,180):
        observed=s.objectives.ap_mean_suffix(raw,35e9,end)
        if row['observed_mean_ap_'+str(end)+'_c']!=observed:raise ValueError('mean AP stored curve/row mismatch')
        expected=observed if complete else None
        if row['mean_ap_'+str(end)+'_c']!=expected:raise ValueError('equal-work mean AP missing/incomplete mismatch')
    if row['mean_ap_equal_work_valid']!=complete:raise ValueError('mean AP equal-work marker')


def report(root):
    root=Path(root);reg=s.check(root)
    rows=s.budget.read(root/'final_rows.json');cons=s.budget.read(root/'consumption.json');freeze=s.budget.read(root/'freeze.json')
    roles=(*s.BASES,*freeze['selections'],*freeze['origin_selections'])
    expected={(case['condition'],role) for case in s.budget.read(root/'inputs.json')['confirmation'] for role in roles}
    if len(rows)!=3696 or {(r['condition'],r['policy']) for r in rows}!=expected:raise ValueError('report exact176x21 matrix')
    out=s.ROOT.parent.parent/'outputs'/s.budget.TASK;out.mkdir(parents=True,exist_ok=True)
    helpers.csvwrite(out/'final_rows.csv',rows)
    for scope in ('full','primary','release'):helpers.csvwrite(out/('summary_'+scope+'.csv'),summary(scope_rows(rows,scope)))
    helpers.csvwrite(out/'mean_cost_Pareto_by_scope.csv',pareto_by_scope(rows))
    verdict={role:dict(full=helpers.strict(rows,role),primary=helpers.strict(s.parent.primary(rows),role),diagnostic_only=True) for role in (*freeze['selections'],*freeze['origin_selections'])}
    s.write(out/'strict_verdict_diagnostic.json',verdict)
    helpers.csvwrite(out/'paired_win_tie_loss_old_metrics.csv',helpers.pairdiff(rows))
    service={}
    for scope in ('full','primary','release'):
        for role in roles:
            q=[r for r in scope_rows(rows,scope) if r['policy']==role]
            bad=[r['condition'] for r in q if service_failure(r)[0]]
            unknown=[dict(condition=r['condition'],missing=service_failure(r)[1]) for r in q if service_failure(r)[1]]
            service[scope+':'+role]=dict(absolute_service_complete_and_zero=not bad,failed_conditions=bad,unknown_conditions=unknown,conditions=len(q),p95_guard=False)
    s.write(out/'absolute_service_by_scope.json',service)
    # Original 400ms proposal remains diagnostic only; never a 14 DEV guard/key/stop.
    release400={}
    for role in roles:
        q=[r for r in scope_rows(rows,'release') if r['policy']==role]
        bad=[r['condition'] for r in q if service_failure(r)[0] or not finite(r.get('urgent_p95_ms')) or r['urgent_p95_ms']>400]
        release400[role]=dict(feasible=not bad,diagnostic_only=True,proposed_urgent_P95_budget_ms=400,conditions=len(q),failed_conditions=bad,
            mean_J=aggregate([r.get('energy_j') for r in q])['mean'],mean_AP=aggregate([r.get('peak_ap_c') for r in q])['mean'],
            mean_AP_time180=aggregate([r.get('mean_ap_180_c') for r in q])['mean'])
    s.write(out/'conditional_release_400ms.json',release400)
    behavior=defaultdict(lambda:defaultdict(int));timing=defaultdict(list);queues=defaultdict(list);rawchecks=[];io=[];resources=[]
    by={(r['condition'],r['policy']):r for r in rows}
    for child in ('controls','models'):
        folder=root/child
        for path in (folder/'rows').glob('*.json'):
            receipt=s.budget.read(path);rawpath=folder/'items'/(path.stem+'.json.gz')
            if s.budget.digest(rawpath)!=receipt['raw_sha256']:raise ValueError('raw SHA changed '+str(path))
            rawchecks.append(dict(worker=child,identity=path.stem,raw_sha256=receipt['raw_sha256']))
        for path in (folder/'items').glob('confirmation_*.json.gz'):
            raw=json.loads(gzip.decompress(path.read_bytes()));s.parent.audit_ledger(raw['result']);role=raw['row']['policy']
            row=by[raw['row']['condition'],role]
            if raw['row']!=row:raise ValueError('final row/raw differs')
            validate_means(raw,row)
            for snap in raw['snapshots']:
                if np.asarray(snap['state']).shape!=(226,) or np.asarray(snap['candidates']).shape!=(32,57):raise ValueError('saved ABI')
                if not snap['physical_mask'][snap['chosen']] or snap['online_forecast_calls']!=0:raise ValueError('physical mask/forecast')
                action=snap['actions'][snap['chosen']];behavior[role]['decisions']+=1;behavior[role][action['kind']]+=1
                behavior[role]['teacher_overrides']+=snap['chosen']!=snap['base'];behavior[role]['nonhead']+=snap['nonhead_selected']
                behavior[role]['max_queue']=max(behavior[role]['max_queue'],snap['queue_size'])
            for frame in raw['stage_times']:
                for key in ('atc_seconds','candidates_seconds','mask_seconds','encode_seconds','inference_seconds','total_seconds','actual_total_seconds'):
                    if key in frame:timing[role,key].append(frame[key]*1000)
            for callback in raw['callbacks']:queues[role,callback['queue']].append(callback['event_to_dispatch_seconds']*1000)
        if (folder/'checkpoint_io.jsonl').exists():io.extend(dict(worker=child,**json.loads(line)) for line in (folder/'checkpoint_io.jsonl').read_text('utf8').splitlines())
        for line in (folder/'executions.jsonl').read_text('utf8').splitlines():
            item=json.loads(line)
            if item['event']=='start':resources.append(dict(worker=child,identity=item['identity'],at_utc=item['at_utc'],**item['resources']))
        if (folder/'boundary_stop.json').exists():
            item=s.budget.read(folder/'boundary_stop.json');resources.append(dict(worker=child,identity='boundary_stop',reason=item['reason'],**item.get('resources',{})))
    for oldseed in s.ORIGIN_MAP.values():
        child='origin'+str(oldseed);folder=root/child
        for path in (folder/'rows').glob('*.json'):
            receipt=s.budget.read(path);rawpath=folder/'items'/(path.stem+'.json.gz')
            if s.budget.digest(rawpath)!=receipt['raw_sha256']:raise ValueError('origin DEV copied raw changed')
            rawchecks.append(dict(worker=child,identity=path.stem,raw_sha256=receipt['raw_sha256']))
    helpers.csvwrite(out/'actual_behavior.csv',[dict(role=role,**v) for role,v in behavior.items()])
    helpers.csvwrite(out/'raw_sha_receipts.csv',rawchecks);helpers.csvwrite(out/'PC_resource_observations.csv',resources)
    helpers.csvwrite(out/'PC_timing.csv',[dict(role=role,stage=stage,count=len(v),mean_ms=float(np.mean(v)),P95_ms=float(np.quantile(v,.95)),max_ms=max(v)) for (role,stage),v in timing.items()])
    helpers.csvwrite(out/'PC_queue_timing.csv',[dict(role=role,queue=q,count=len(v),mean_ms=float(np.mean(v)),P95_ms=float(np.quantile(v,.95)),max_ms=max(v)) for (role,q),v in queues.items()])
    helpers.csvwrite(out/'checkpoint_io.csv',io)
    helpers.csvwrite(out/'checkpoint_io_summary.csv',[dict(worker=worker,count=len(q),mean_seconds=float(np.mean([x['seconds'] for x in q])),P95_seconds=float(np.quantile([x['seconds'] for x in q],.95)),max_seconds=max(x['seconds'] for x in q),max_checkpoint_bytes=max(x['bytes'] for x in q)) for worker in {x['worker'] for x in io} for q in [[x for x in io if x['worker']==worker]]])
    paired=[]
    for seed in s.SEEDS:
        for arm in s.ARMS:
            for row in [r for r in rows if r['policy']==f'{arm}_{seed}']:
                refs=[(refarm,f'{refarm}_{seed}') for refarm in s.ARMS]+[('origin4096',s.origin_role(seed))]+[(base,base) for base in s.BASES]
                for comparison,refrole in refs:paired.append(paired_row(row,by[row['condition'],refrole],seed=seed,reward_arm=arm,comparison=comparison))
    helpers.csvwrite(out/'reward_arm_paired.csv',paired);paired_sum=paired_summary(paired);helpers.csvwrite(out/'reward_arm_paired_summary.csv',paired_sum)
    weights=out/'weights';weights.mkdir(exist_ok=True);mechanics=[];labelaudit=[];maskrates=[]
    for seed in s.SEEDS:
        for arm in s.ARMS:
            role=f'{arm}_{seed}';item=freeze['selections'][role];path=s.learner_path(root/'models',seed,item['episodes'],arm)
            if s.budget.digest(path)!=item['sha256']:raise ValueError('selected model changed')
            shutil.copy2(path,weights/path.name)
            latest=s.learning.Learner.load(s.learner_path(root/'models',seed,None,arm),s.deps(reg,arm))
            for log in latest.episode_logs:labelaudit.append(dict(seed=seed,reward_arm=arm,episode=log['episode'],family=log['row']['family'],factor=log['row']['factor'],costs=json.dumps(log['costs']),valid=json.dumps(log['valid']),**log['deadline_objective']))
            mechanics.append(dict(seed=seed,reward_arm=arm,episodes=latest.episodes,native_updates=len(latest.logs),Adam_steps=latest.steps,pending=len(latest.pending),selected_episode=item['episodes'],selected_sha=item['sha256']))
            incomplete=sum(log['row']['completed']!=log['row']['planned'] or log['row']['completed_work_units']!=log['row']['planned_work_units'] for log in latest.episode_logs)
            invalid=sum(not(log['valid'][1] and log['valid'][2]) for log in latest.episode_logs)
            maskrates.append(dict(seed=seed,reward_arm=arm,episodes=len(latest.episode_logs),actual_incomplete_training_episodes=incomplete,invalid_EAP_episodes=invalid,
                invalid_EAP_rate=invalid/len(latest.episode_logs) if latest.episode_logs else None,deadline_equal_work_mask_inactive=(arm!='CURRENT_COST5' and invalid==0)))
        original=root/'origin_weights'/Path(reg['origin_checkpoints'][str(seed)]['path']).name;shutil.copy2(original,weights/original.name)
    helpers.csvwrite(out/'native_learning.csv',mechanics);helpers.csvwrite(out/'episode_objective_audit.csv',labelaudit);helpers.csvwrite(out/'incomplete_cost_mask_by_arm_seed.csv',maskrates)
    matched=[];stages=[]
    for episode in s.completed_stages(root):
        stage=s.budget.read(root/'models'/f'stage{episode}.json')
        stages.extend(dict(role=role,**item) for role,item in stage['models'].items())
        rr=s.rows(root/'models',f'dev{episode}_');lookup={(r['condition'],r['policy']):r for r in rr}
        for row in rr:
            arm,ss=row['policy'].rsplit('_',1)
            for refarm in s.ARMS:matched.append(paired_row(row,lookup[row['condition'],refarm+'_'+ss],episode=episode,seed=int(ss),reward_arm=arm,comparison=refarm))
    helpers.csvwrite(out/'development_stages.csv',stages);helpers.csvwrite(out/'matched_stage_DEV_paired.csv',matched)
    for name in ('registration.json','inputs.json','namespace_receipt.json','freeze.json','consumption.json','development_continuation.json','PROTOCOL_REGISTERED.md','partial59_audit.json','reused_reference_bindings.json'):
        if (root/name).exists():shutil.copy2(root/name,out/name)
    shutil.copytree(root/'REGISTERED_SOURCE_TREE',out/'REGISTERED_SOURCE_TREE',dirs_exist_ok=True)
    text=['# 기한 중심 보상과 고정 구간 평균 AP 대조', '',f"새 환경 {cons['environments']}회 안에 학습 {cons['learning']}회가 포함됩니다. 환경 실패 {cons['failed']}회, 기존 참조 복사 4400개는 신규 환경 0회입니다.",
          f"모델 대표 {freeze['selected']}는 새 DEV에서만 선정했습니다. 12개 trained 모델과 3개 origin4096 모두 고정한 뒤 176×21=3696개의 새 확인 행을 보존했습니다.", '',helpers.table(summary(rows)), '',
          'CURRENT_COST5→DEADLINE_PEAK120은 시간 보상 제거와 미완료 equal-work 비용 마스크 보완을 함께 바꿉니다. incomplete_cost_mask_by_arm_seed.csv에서 해당 마스크가 실제로 발동했는지 공개합니다. PEAK120→MEAN120은 목표의 peak/mean 차이, MEAN120→MEAN180은 구간과 냉각 꼬리 차이를 분리합니다. 전군 간 대응 결과는 reward_arm_paired.csv와 scope별 summary에 있습니다.',
          'deadline 3군은 기한 이내 응답시간·P95·holding·완료 보너스를 모두 제거했습니다. 기한/원 상한 U/N과 요청/units 미완료 6개 절대 비용100만 서비스 벌점으로 남습니다. 선언 기한과 원 상한이 같으면 두 채널 벌점이 겹치는 기존 설계를 공개합니다.',
          '새 DEV 선택·확대 중단에는 P95를 사용하지 않습니다. J→meanAP35..180→peakAP35..180 순서의 선택은 두 비용 동시 절감을 보장하지 않습니다. P95와 원 strict4참조 ε0 및 release80의400ms 적격성은 별도 진단으로 모두 보존합니다.',
          '전6개 비교군의 J/meanAP120/meanAP180/peak/P95/서비스 조건별 차이를 모두 출력합니다. scope별 평균 Pareto는 절대서비스 적격과 비용 전량 유효인 군에만 표시하며 조건별 우위나 원 strict PASS를 뜻하지 않습니다.',
          'mean AP는 35..120의85초 또는35..180의145초 고정 분모와 1초 격자의 선형 보간·사다리꼴 적분입니다. 완료시각에 따라 구간을 줄이거나 추가 냉각하지 않습니다.',
          '미완료 equal-work J/AP/mean AP는 결측이며 0이나120초 평균으로 대체하지 않습니다. 전체 scope 평균은 결측이 하나라도 있으면 미확인입니다. complete_conditional_mean과 valid/missing 분모는 별도이며 실패 행을 버리지 않습니다.',
          'deadline 비용 타깃은 actual/reference 어느 쪽이든 전량/units 미완료일 때 E/AP를 invalid 처리하고 6개 서비스 비용을 유지합니다. CURRENT_COST5는 원13 대조 계약을 그대로 유지합니다.',
          '고정 모델로 argmax 추론하며 actual AVAILABLE·비선점·CG_DC≤2·필요자원WAIT와226/57/32 ABI를 유지합니다. EFT0, Greedy 독립 비교군 전용, NPU/APK/기기/S26/fit/외부전송0입니다.',
          '8시간 예산은 새 롤아웃/DEV/최종을 포함합니다. PC 자원 관측과 판단/저장시간은 공유 호스트 부하를 포함하며 폰 판단시간이나 소비 J로 해석하지 않습니다.',
          'CPU 분류4표본·고정 열plant·n1 범위·2816개 유한 TRAIN 재사용 한계가 남습니다. 학습 횟수나 비용 가중치5만으로 서비스 유지·실기기 개선·자동 채택을 주장하지 않습니다.', '', '모든 seed의 원 strict 진단:']
    for role in freeze['selections']:text.append(f"- {role}: episode={freeze['selections'][role]['episodes']}, full={verdict[role]['full']['promising']}, primary={verdict[role]['primary']['promising']}, DEV절대서비스={freeze['selections'][role]['development_guard_pass']}.")
    text+=['', '원 source/input/registration/freeze/weights SHA는 manifest와 REGISTERED_SOURCE_TREE, 모든 raw SHA는 raw_sha_receipts.csv에 있습니다. 최종 뒤 튜닝·재선정은 0입니다.']
    (out/'RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf8')
    manifest={p.relative_to(out).as_posix():s.budget.digest(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    s.write(out/'manifest.json',manifest)
    return dict(reported=True,output=str(out),automatic_adoption=False)
