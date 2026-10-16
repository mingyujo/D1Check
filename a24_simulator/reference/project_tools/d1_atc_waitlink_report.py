"""Saved-data only reporting. No simulated environment or learner update."""
import csv,gzip,json,shutil,zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
from tools import d1_atc_waitlink_study as s

def csvwrite(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def summary(rows):
    by=defaultdict(list)
    for r in rows:by[r['policy']].append(r)
    def mean(q,k):
        v=[r[k] for r in q if r[k] is not None];return float(np.mean(v)) if v else None
    return [dict(role=role,conditions=len(q),planned=sum(r['planned'] for r in q),completed=sum(r['completed'] for r in q),
        urgent_planned=sum(r['urgent_planned'] for r in q),normal_planned=sum(r['normal_planned'] for r in q),
        incomplete=sum(r['incomplete'] for r in q),U=sum(r['urgent_failure'] for r in q),N=sum(r['normal_failure'] for r in q),
        Ucap=sum(r['urgent_original_cap_failure'] for r in q),Ncap=sum(r['normal_original_cap_failure'] for r in q),
        P95=mean(q,'urgent_p95_ms'),J=mean(q,'energy_j'),AP=mean(q,'peak_ap_c'),cost_valid=sum(r['energy_j'] is not None for r in q)) for role,q in by.items()]
def table(q):
    lines=['| 정책 | 완료/요청 | U/N 기한 실패 | 원 U/N 상한 실패 | 긴급P95 평균 ms | J 평균 | AP 평균 °C |','|---|---:|---:|---:|---:|---:|---:|']
    fmt=lambda v:'미확인' if v is None else f'{v:.6f}'
    for r in q:lines.append(f"| {r['role']} | {r['completed']}/{r['planned']} | {r['U']}/{r['N']} | {r['Ucap']}/{r['Ncap']} | {fmt(r['P95'])} | {fmt(r['J'])} | {fmt(r['AP'])} |")
    return '\n'.join(lines)
def strict(rows,role):
    by={(r['condition'],r['policy']):r for r in rows};q=[r for r in rows if r['policy']==role];failures=[];improve=False
    for r in q:
        if r['completed']!=r['planned'] or r['completed_work_units']!=r['planned_work_units']:failures.append(dict(condition=r['condition'],reason='incomplete'))
        if r['family'] in ('idle','steady') and any(r[k] for k in ('incomplete','urgent_failure','normal_failure','urgent_original_cap_failure','normal_original_cap_failure')):failures.append(dict(condition=r['condition'],reason='absolute_anchor_service'))
        for refrole in ('FIFO_FIXED','RR_READY','GREEDY_RESOURCE_FIFO','RuleATC'):
            ref=by[r['condition'],refrole]
            for key in ('incomplete','urgent_failure','normal_failure','urgent_original_cap_failure','normal_original_cap_failure','urgent_p95_ms','energy_j','peak_ap_c'):
                if r[key] is None or ref[key] is None or r[key]>ref[key]:failures.append(dict(condition=r['condition'],reference=refrole,metric=key))
            for key in ('energy_j','peak_ap_c'):
                if r[key] is not None and ref[key] is not None and r[key]<ref[key]:improve=True
    return dict(promising=not failures and improve,nondegrading=not failures,strict_cost_gain=improve,failures=failures,epsilon=0)
def pairdiff(rows):
    by={(r['condition'],r['policy']):r for r in rows};out=[]
    for role in dict.fromkeys(r['policy'] for r in rows):
        for ref in s.BASES:
            for metric in ('incomplete','urgent_failure','normal_failure','urgent_original_cap_failure','normal_original_cap_failure','urgent_p95_ms','energy_j','peak_ap_c'):
                vals=[r[metric]-by[r['condition'],ref][metric] for r in rows if r['policy']==role and r[metric] is not None and by[r['condition'],ref][metric] is not None]
                out.append(dict(role=role,reference=ref,metric=metric,valid=len(vals),win=sum(v<0 for v in vals),tie=sum(v==0 for v in vals),loss=sum(v>0 for v in vals),mean_delta=float(np.mean(vals)) if vals else None,worst=max(vals) if vals else None))
    return out
def report(root):
    s.check(root);out=s.ROOT.parent.parent/'outputs'/s.budget.TASK;out.mkdir(parents=True,exist_ok=True)
    rows=s.budget.read(root/'final_rows.json');cons=s.budget.read(root/'consumption.json');freeze=s.budget.read(root/'freeze.json')
    full=summary(rows);primary=summary(s.primary(rows));release=[r for r in rows if r['release_domain']]
    csvwrite(out/'final_rows.csv',rows);csvwrite(out/'summary_full.csv',full);csvwrite(out/'summary_primary.csv',primary);csvwrite(out/'summary_release.csv',summary(release));csvwrite(out/'paired_win_tie_loss.csv',pairdiff(rows))
    verdict={role:dict(full=strict(rows,role),primary=strict(s.primary(rows),role)) for role in freeze['selections']};s.write(out/'strict_verdict.json',verdict)
    # Added SLO is proposed and preregistered, separate from original strict.
    feasible={}
    for role in dict.fromkeys(r['policy'] for r in rows):
        q=[r for r in release if r['policy']==role]
        bad=[r['condition'] for r in q if r['completed']!=r['planned'] or any(r[k] for k in ('urgent_failure','normal_failure','urgent_original_cap_failure','normal_original_cap_failure')) or r['urgent_p95_ms'] is None or r['urgent_p95_ms']>400]
        feasible[role]=dict(feasible=not bad,proposed_urgent_P95_budget_ms=400,conditions=len(q),failed_conditions=bad,
            mean_J=float(np.mean([r['energy_j'] for r in q])) if all(r['energy_j'] is not None for r in q) else None,mean_AP=float(np.mean([r['peak_ap_c'] for r in q])) if all(r['peak_ap_c'] is not None for r in q) else None)
    s.write(out/'conditional_release_400ms.json',feasible)
    behavior=defaultdict(lambda:defaultdict(int));timing=defaultdict(list);queues=defaultdict(list);rawchecks=[]
    for child in ('controls',*(f'seed{seed}' for seed in s.SEEDS)):
        c=root/child
        for path in (c/'rows').glob('*.json'):
            receipt=s.budget.read(path);rawpath=c/'items'/(path.stem+'.json.gz')
            if s.budget.digest(rawpath)!=receipt['raw_sha256']:raise ValueError('raw hash changed '+str(path))
            rawchecks.append(dict(worker=child,identity=path.stem,raw_sha256=receipt['raw_sha256']))
        for path in (c/'items').glob('confirmation_*.json.gz'):
            raw=json.loads(gzip.decompress(path.read_bytes()));s.audit_ledger(raw['result']);role=raw['row']['policy']
            for snap in raw['snapshots']:
                if np.asarray(snap['state']).shape!=(226,) or np.asarray(snap['candidates']).shape!=(32,57):raise ValueError('saved ABI')
                if not snap['physical_mask'][snap['chosen']] or snap['online_forecast_calls']!=0:raise ValueError('saved mask/forecast')
                action=snap['actions'][snap['chosen']];behavior[role]['decisions']+=1;behavior[role][action['kind']]+=1
                behavior[role]['teacher_overrides']+=snap['chosen']!=snap['base'];behavior[role]['max_queue']=max(behavior[role]['max_queue'],snap['queue_size'])
                behavior[role]['nonhead']+=snap['nonhead_selected']
                if action['kind']=='resource_wait':behavior[role]['wait_with_legal_start']+=any(v and a and a['kind']!='resource_wait' for v,a in zip(snap['physical_mask'],snap['actions']))
            for frame in raw['stage_times']:
                for key in ('atc_seconds','candidates_seconds','mask_seconds','encode_seconds','inference_seconds','total_seconds','actual_total_seconds'):
                    if key in frame:timing[role,key].append(frame[key]*1000)
            for callback in raw['callbacks']:queues[role,callback['queue']].append(callback['event_to_dispatch_seconds']*1000)
    csvwrite(out/'actual_behavior.csv',[dict(role=role,**v) for role,v in behavior.items()]);csvwrite(out/'raw_sha_receipts.csv',rawchecks)
    csvwrite(out/'PC_timing.csv',[dict(role=role,stage=stage,count=len(v),mean_ms=float(np.mean(v)),P95_ms=float(np.quantile(v,.95)),max_ms=max(v)) for (role,stage),v in timing.items()])
    csvwrite(out/'PC_queue_timing.csv',[dict(role=role,queue=q,count=len(v),mean_ms=float(np.mean(v)),P95_ms=float(np.quantile(v,.95)),max_ms=max(v)) for (role,q),v in queues.items()])
    import torch
    mechanics=[];weightout=out/'weights';weightout.mkdir(exist_ok=True)
    for seed in s.SEEDS:
        for arm in s.ARMS:
            role=f'{arm}_{seed}';data=torch.load(s.learner_path(root/f'seed{seed}',arm,seed),map_location='cpu',weights_only=False);selected=freeze['selections'][role]
            if data['pending']:raise ValueError('unclosed training batch')
            path=s.learner_path(root/f'seed{seed}',arm,seed,selected['episodes'])
            if s.budget.digest(path)!=selected['sha256']:raise ValueError('selected model changed')
            shutil.copy2(path,weightout/path.name)
            mechanics.append(dict(role=role,episodes=data['episodes'],updates=len(data['logs']),Adam_steps=data['steps'],selected_episode=selected['episodes'],selected_sha=selected['sha256'],development_guard=selected['development_guard_pass'],actor_updates=sum(not l['critic_only'] for l in data['logs']),critic_only_updates=sum(l['critic_only'] for l in data['logs'])))
    csvwrite(out/'native_learning.csv',mechanics)
    for fname in ('registration.json','inputs.json','consumption.json','freeze.json','partial59_audit.json','development_continuation.json','orchestration.json'):
        if (root/fname).exists():shutil.copy2(root/fname,out/fname)
    source=out/'source';source.mkdir(exist_ok=True)
    for path in (s.ROOT/'tools').glob('d1_atc_waitlink_*.py'):shutil.copy2(path,source/path.name)
    shutil.copy2(s.ROOT/'tools/test_d1_atc_wait.py',source/'test_d1_atc_wait.py')
    reviews=s.ROOT/'docs/results/atc_waitlink_20261012'
    for path in reviews.glob('*_review.md'):shutil.copy2(path,out/path.name)
    shutil.copy2(s.ROOT/'docs/ATC_WAITLINK_STUDY_20261012.md',out/'DESIGN.md')
    # Final/dev traces and selected checkpoints are exported; all train raw remains preserved.
    with zipfile.ZipFile(out/'confirmation_and_dev_evidence.zip','w',zipfile.ZIP_STORED) as z:
        for path in root.rglob('*'):
            if not path.is_file():continue
            if (path.suffix in ('.json','.jsonl') and path.parent.name not in ('rows',)) or path.name.startswith(('confirmation_','development_','dev','initialproof_')):z.write(path,path.relative_to(root).as_posix())
    chosen=freeze['selected'];r=next(r for r in full if r['role']==chosen);ref=next(r for r in full if r['role']=='RuleATC')
    selected_pass=verdict[chosen]['primary']['promising'];slo=feasible[chosen]['feasible']
    text=f'''# ATC＋PPO 밤사이 확대 실험 — 완료

신규 환경 {cons['environments']:,}회, 학습 {cons['learning']:,}에피소드, 환경 실패 {cons['failed']}회. 모델9개의 실제 업데이트/선정값은 native_learning.csv에 있다. 학습은 환경 수에 포함한다. 기존08/09와FAIL·입력·source·weights는 보존했다. 기기/APK/fit/S26/NPU0, EFT0, Greedy는 독립 비교군이다.

대표 `{chosen}`는 개발 자료로만 선정하고 모든9모델을 확인 전에 동결했다. 확인 뒤 재학습·재선정은0이다. 대표의 primary original strict는 **{'PASS 후보' if selected_pass else 'FAIL'}**, release 도메인에서 추가 제안한400ms P95 budget의 서비스 적격성은 **{'충족' if slo else '미충족'}**이다. 두 판정은 다르며 조건부 결과를 전체 정책 우위·앱 채택·실기기 개선으로 승격하지 않는다.

## 전체176조건·모든 seed

{table(full)}

P95/J/AP는 조건별 평균이다. P95는 완료 응답 분모이므로 전체 도착 기준 실패/완료/원 상한을 함께 보고한다. J는 공통120초, AP는35~180초 모형 peak이며 불완료 equal-work J/AP는null이다. 비용 유효조건 수는 summary CSV에 있다. 평균 개선으로 악화조건을 숨기지 않으며 모든 비교군과 조건별 승/동/패를 공개한다.

## 사전 정의 primary (boundary6 제외) 및 부정 대조

{table(primary)}

release offset .15/.35는 대기가 손해일 수 있는 부정 대조, .5/.58은 해제 경쟁 가설, .65는 해제 뒤 anchor다. 모두 보존했다. idle/steady/burst2/4/mix4와 boundary6도 전체 표·원행에 있다. arrivals는미래 실현D처리시간에 맞추지 않았다. 이 조건은 실측 도착 분포가 아닌 사전 명시 가설 부하다.

## 조건부 효율 분석과 전체 strict

release_domain의5offset×8새도착seed×2납기=80조건에서 모든 정책에 동일한 추가P95≤400ms·원/요청납기·전량완료 기준을 적용했다. 이는 새 제안 운영 목표이고 기존1.5/6초/strict를 완화하거나 과거FAIL를 바꾸는 기준이 아니다. conditional_release_400ms.json의 실패조건과 원행을 함께 읽는다. 적격성/에너지/P95/열의상충을분리하고 특정seed·조건의우위를보편적결론으로바꾸지않는다.

대표 전체 평균 ATC 차이: ΔP95={r['P95']-ref['P95']:+.9f}ms, ΔJ={(r['J']-ref['J']) if r['J'] is not None and ref['J'] is not None else 'UNAVAILABLE'}J, ΔAP={(r['AP']-ref['AP']) if r['AP'] is not None and ref['AP'] is not None else 'UNAVAILABLE'}°C. 각 seed·condition·metric의 worst와fail은 paired_win_tie_loss.csv/strict_verdict.json에 있다. 기존strict는epsilon0와동일참조(FIFO/RR/Greedy/ATC)를유지했다. 자동채택0·experiment_ready=false다.

## 학습·물리·계산 경계

현재관측state226/후보32×57, top4＋coverage최대8요청·실제행동29상한·phase-awareETA150ms/known-overrun을사용했다. 전체현재Qscan은후보선정이고actor가전Q모든행동을본다는뜻이아니다. actor/valueencoder분리와critichead0초기화를공통적용하고freshweights를학습했다. 원episode-sumPPO손실을유지했다. train1408/dev88·teacher1408/control개발528은10의확인전자료·SHAbinding으로재사용하고이1936개를신규환경으로중복계수하지않았다. 최종은별도923410101..108이다. 세군은같은URGENT_HOLD·pairedrunningP95potential목적이다. KEEP_FLAG_WAIT0/DROP_FLAG_WAIT1/DROP_FLAG_WAIT0은teacherflag52의NN노출과WAITlogitgap0/1을대조한다. DROP에도현재ATC rank/gap과후보/복귀메타는남아있다. 사후teacher/future상태는학습label만쓰고운영후보/mask/NN에는없다.

모든환경원시SHA/실제원장·지원/응답/AVAILABLE·최종선택물리mask/shape와현재forecast0을확인했다. partial59정확복원·nativeproof12·실제Adam/count는원장과가중치에보존한다. 마스크는서비스/P95보장이아니다. 실행중선점/이동·조기owner재사용·냉각·NPU·EFT/Greedy내부중재0이다. 롤링은사건기반온라인재판단이며formal rolling horizon없다.

PC stage/queue판단시간은병렬호스트자료이며폰시간/정책에너지로환산하지않는다. CPU분류4/GPU188/탐지CPU192 donor와같은동결열/에너지모형을사용한PC 탐색이므로실기기검증이아니다. confirmation_and_dev_evidence.zip은확인/개발trace·원장·입력·증명이고, 모든학습raw는원work/ATC-WAITLINK-EXPAND-11에보존하며그SHA는raw_sha_receipts.csv다. 이자료를원시실측혹은독립기기홀드아웃으로이름붙이지않는다.

학습횟수수치상한은없었다. 반복확대의실제종료이유와stage별walltime·개발guard는development_continuation/orchestration.json에있다. 결론을미리정하거나승리할때까지최종자료를다시쓰지않았다.
'''
    (out/'RESULTS.md').write_text(text,encoding='utf8',newline='\n')
    reviews.mkdir(parents=True,exist_ok=True);(reviews/'RESULTS.md').write_text(text,encoding='utf8',newline='\n')
    s.write(out/'manifest.json',{p.relative_to(out).as_posix():s.budget.digest(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'})
    entry=f'''## 2026-10-12 ATC-WAITLINK-EXPAND-11 — 밤사이 확대 학습·확인 완료

- [새계약](ATC_WAITLINK_STUDY_20261012.md)·[완료결과](results/atc_waitlink_20261012/RESULTS.md): 이번환경{cons['environments']}/학습{cons['learning']}/환경실패{cons['failed']},9fresh모델·실제nativeupdate·512→powers2확대·개발만으로선정·새176×15=2640확인행이다. 과거08/09닫힌입력/모델/source/FAIL/이력과다른동시과제를보존했다.
- 대표{chosen} primarystrict={'PASS후보' if selected_pass else 'FAIL'},추가제안400ms releaseSLO={'충족' if slo else '미충족'}는별도판정이며보편우위/앱채택/기기개선으로전용0. 모든seed/negative offset/anchor/boundary와조건손해를공개한다. EFT0·Greedy독립비교군·비선점/실제AVAILABLE/응답분리/CG_DC≤2·기기/APK/fit/S26/NPU0·기본/experiment_ready=false유지.
- 학습수치상한은없고개발안정성/밤사이시간·저장reserve의실제종료이유를기록했다. 다음최대2: 완료결과공유,조건부효과/미해결서비스·모형적격성범위검토. 최종자료재튜닝/자동채택0. HEAD12d64923+신규미커밋PCsource/등록SHA·실측donor384/CPU분류4약점유지.

'''
    for name in ('PROJECT_STATUS.md','PROJECT_PLAN.md','DECISIONS.md'):
        p=s.ROOT/'docs'/name;old=p.read_bytes();marker=b'## 2026-10-12 ATC-WAITLINK-EXPAND-11'
        i=old.find(marker)
        if i>=0:
            end=old.find(b'\n## ',i+len(marker));end=len(old) if end<0 else end+1
            new=old[:i]+entry.encode('utf8')+old[end:]
        else:
            i=old.find(b'\n')+1;new=old[:i]+b'\n'+entry.encode('utf8')+old[i:]
        if p.read_bytes()!=old:raise RuntimeError('concurrent documentation revision, preserve and retry report')
        p.write_bytes(new)
    return dict(reported=True,selected=chosen,primary_strict=selected_pass,conditional_release_feasible=slo,consumption=cons)
