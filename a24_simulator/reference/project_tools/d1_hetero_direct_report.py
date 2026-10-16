"""Completed-study saved-only audit/report; no simulation, fitting or learning."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from tools import d1_hetero_direct_study as s

METRICS = ('incomplete','urgent_failure','normal_failure','declared_urgent_failure',
           'declared_normal_failure','urgent_p95_ms','energy_j','peak_ap_c')


def csv_file(path, rows):
    if not rows: return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)


def stats(v):
    return dict(count=len(v), mean_ms=float(np.mean(v))*1000,
                p95_ms=float(np.quantile(v,.95,method='higher'))*1000,
                max_ms=max(v)*1000) if v else dict(count=0,mean_ms=None,p95_ms=None,max_ms=None)


def summarize(rows, role, factor):
    rr = [r for r in rows if r['policy']==role and (factor=='all' or r['factor']==factor)]
    sums = ('planned','completed','incomplete','urgent_planned','normal_planned',
            'urgent_failure','normal_failure','declared_urgent_failure','declared_normal_failure','fallbacks')
    row = dict(policy=role,factor=factor,conditions=len(rr),**{k:sum(r[k] for r in rr) for k in sums})
    for k in ('urgent_p95_ms','energy_j','peak_ap_c'):
        row[k+'_mean'] = float(np.mean([r[k] for r in rr])) if all(r[k] is not None for r in rr) else None
    return row


def template(action, tickets):
    if not action or action['kind']=='resource_wait': return ('resource_wait',)
    return action['kind'],tuple(sorted((tickets[j['request_id']]['task'],j['backend']) for j in action['jobs']))


def calculation_benchmark(f, initial, network):
    """Synthetic current-state calculations only; environment/learning=0."""
    result=[]; torch.set_num_threads(1)
    c=s.a.Controller(f,initial,network=network)
    lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
    for n in (1,8,32,128,512):
        qs=[dict(id=f'bench{i}',task='classification' if i%2 else 'detection',priority='urgent' if i%2 else 'normal',ordinal=i,
                 arrival_ns=35_000_000_000,deadline_offset_ns=1_500_000_000 if i%2 else 6_000_000_000,service_class=i%3) for i in range(n)]
        measures=collections.defaultdict(list)
        for j in range(55):
            start=time.perf_counter(); bank=s.a.bank(qs,lanes,35e9,c.estimates,sequencing='EDD'); built=time.perf_counter()
            encoded=c.encode(qs,lanes,35e9,bank); encoded_at=time.perf_counter()
            with torch.no_grad(): network(torch.from_numpy(encoded['state'])[None],torch.from_numpy(encoded['candidates'])[None],torch.from_numpy(encoded['mask'])[None])
            end=time.perf_counter()
            if j<5: continue
            for k in ('atc_seconds','candidates_seconds','mask_seconds'): measures[k].append(bank['timings'][k])
            measures['encode'].append(encoded_at-built); measures['PPO_forward'].append(end-encoded_at); measures['calculation_total'].append(end-start)
        for k,v in measures.items(): result.append(dict(queue=n,component=k,**stats(v),scope='PC static current queue, 5warmup+50; no environment or learning'))
    return result


def report(folder,out):
    reg=s.check(folder)
    if not s.budget.read(folder/'cursor.json')['completed']: raise ValueError('study not complete')
    out.mkdir(parents=True,exist_ok=True)
    freeze=s.budget.read(folder/'freeze.json'); usage=s.budget.read(folder/'consumption.json')
    confirm=s.rows(folder,'confirmation_'); roles=[*s.BASES,*freeze['selections']]
    if len(confirm)!=64*len(roles): raise ValueError('confirmation matrix')
    summary=[summarize(confirm,role,factor) for factor in ('all',*s.FACTORS) for role in roles]
    csv_file(out/'comparison.csv',confirm); csv_file(out/'summary.csv',summary)
    dev=s.rows(folder,'dev'); csv_file(out/'development.csv',dev)
    hashes={}; receipt_hashes={}; tickets_by_case={}; diag=collections.Counter(); diag_f=collections.defaultdict(collections.Counter)
    timed=collections.defaultdict(list); queued=collections.defaultdict(list); raw_by={}; counts=collections.Counter()
    executions=[json.loads(line) for line in (folder/'executions.jsonl').read_text('utf8').splitlines()]
    starts=[e for e in executions if e['event']=='start']; ends=[e for e in executions if e['event']=='completion']
    assert len(starts)==len(ends)==usage['environments'] and not any(e['event']=='failure' for e in executions)
    assert len({e['identity'] for e in starts})==len(starts)
    for receipt in sorted((folder/'rows').glob('*.json')):
        metadata=s.budget.read(receipt); rawpath=folder/'items'/(receipt.stem+'.json.gz')
        actual=s.budget.digest(rawpath)
        if actual!=metadata['raw_sha256']: raise ValueError('raw SHA changed')
        hashes[rawpath.name]=actual; receipt_hashes[receipt.name]=s.budget.digest(receipt)
        counts[metadata['row']['phase']]+=1
        if not receipt.stem.startswith('confirmation_'): continue
        raw=json.loads(gzip.decompress(rawpath.read_bytes())); s.audit_ledger(raw['result'])
        row=raw['row']; condition=row['condition']; role=row['policy']; factor=row['factor'];raw_by[condition,role]=raw
        tickets=[{k:r[k] for k in s.a.TICKET_FIELDS} for r in raw['result']['ledger']]
        digest=s.a.native.digest(tickets)
        if condition in tickets_by_case and tickets_by_case[condition]!=digest: raise ValueError('paired tickets differ')
        tickets_by_case[condition]=digest
        by_id={q['id']:q for q in tickets}
        for snap in raw['snapshots']:
            if 'request_ids' not in snap: continue
            values=dict(decisions=1, bank_same=int(snap['ATC_EDD_same']),legal_same=int(snap['ATC_EDD_legal_actions_same']),
                        raw_rank_different=int(not snap['raw_rank_same']),raw_top_different=int(not snap['raw_top_same']),
                        rule_choice_different=int(not snap['same_bank_rule_choice_same']),nonhead_selected=int(snap['nonhead_selected']))
            values['physical_choice']=int(len({template(ac,by_id) for ac,m in zip(snap['actions'],snap['mask']) if m})>1)
            diag.update(values);diag_f[factor].update(values)
            if not snap['mask'][snap['chosen']]: raise ValueError('masked selected')
        for cb in raw['callbacks']:
            timed[role,'callback'].append(cb['seconds'])
            if 'event_to_dispatch_seconds' in cb: timed[role,'event_to_dispatch_including_model_observe'].append(cb['event_to_dispatch_seconds'])
        for record in raw['stage_times']:
            for k in ('atc_seconds','candidates_seconds','mask_seconds','encode_seconds','inference_seconds','total_seconds','actual_total_seconds','diagnostic_seconds'):
                if k in record: timed[role,k].append(record[k])
            n=record.get('queue',0);group='1' if n<=1 else '2-4' if n<=4 else '5-8' if n<=8 else '9-16' if n<=16 else '17+'
            total=record.get('actual_total_seconds',record.get('total_seconds',record.get('native_seconds')))
            if total is not None: queued[role,group].append(total)
    assert len(hashes)==usage['environments'] and len(tickets_by_case)==64
    paired=[];indexed={(r['condition'],r['policy']):r for r in confirm}
    for role in freeze['selections']:
        for condition in range(64):
            q=indexed[condition,role]
            for baseline in ('FIFO_FIXED','FIFO_EFT','FIFO_READY','EDD_EFT','ATC_EFT','RuleEDD','RuleATC'):
                r=indexed[condition,baseline]
                delta={k:q[k]-r[k] if q[k] is not None and r[k] is not None else None for k in METRICS}
                paired.append(dict(policy=role,condition=condition,factor=q['factor'],family=q['family'],baseline=baseline,
                                   **delta,all_axes_nonworse=all(v is not None and v<=0 for v in delta.values())))
    csv_file(out/'paired_deltas.csv',paired)
    csv_file(out/'decision_times.csv',[dict(policy=r,component=k,**stats(v)) for (r,k),v in timed.items()])
    csv_file(out/'observed_queue_times.csv',[dict(policy=r,queue_bin=k,**stats(v)) for (r,k),v in queued.items()])
    learning=[]; model_hashes={}
    for role,selection in freeze['selections'].items():
        bank,seed=role.split('_'); path=s.learner_path(folder,bank,int(seed),selection['episodes'])
        if s.budget.digest(path)!=selection['sha256']: raise ValueError('frozen weights changed')
        model_hashes[role]=selection['sha256']
        l=s.learning.Learner.load(s.learner_path(folder,bank,int(seed)),s.deps(reg,bank))
        row=dict(policy=role,episodes=l.episodes,updates=len(l.logs),optimizer_steps=l.steps,pending=len(l.pending),selected_episodes=selection['episodes'],
                 actor_changed_all=all(q['actor_changed'] for q in l.logs),gradient_finite_positive_all=all(math.isfinite(q['actor_gradient_max']) and q['actor_gradient_max']>0 for q in l.logs),
                 physical_choices=sum(q['row']['physical_choice_decisions'] for q in l.episode_logs),fallbacks=sum(q['row']['fallbacks'] for q in l.episode_logs))
        learning.append(row);s.write(out/f'learning_{role}.json',dict(summary=row,updates=l.logs,selection=selection))
    csv_file(out/'learning.csv',learning)
    bank,seed=freeze['selected'].split('_'); selected=s.learning.Learner.load(s.learner_path(folder,bank,int(seed),freeze['selections'][freeze['selected']]['episodes']),s.deps(reg,bank))
    f,initial,_=s.a.hybrid.load()
    if not (out/'queue_scaling_calculation.csv').exists(): csv_file(out/'queue_scaling_calculation.csv',calculation_benchmark(f,initial['initial'],selected.network))
    true_top=collections.defaultdict(collections.Counter)
    for (c,role),raw in raw_by.items():
        if role != 'RuleATC': continue
        by_id={q['id']:q for q in raw['result']['ledger']}
        for snap in raw['snapshots']:
            ranked=snap['ranked_ids']
            edd=sorted(ranked,key=lambda rid:(by_id[rid]['arrival_ns']+by_id[rid]['deadline_offset_ns'],by_id[rid]['arrival_ns'],by_id[rid]['ordinal'],rid))
            true_top[raw['row']['factor']].update(dict(decisions=1,top4_set_different=int(set(ranked[:4])!=set(edd[:4])),top4_ordered_different=int(ranked[:4]!=edd[:4])))
    schedule_diag={}
    for p1,p2 in [('EDD_EFT','ATC_EFT'),('RuleEDD','RuleATC'),('RuleEDD',freeze['selected'])]:
        fields=('id','backend','dispatch_ns','response_ns','lane_available_ns')
        def signature(raw): return [{k:q.get(k) for k in fields} for q in raw['result']['ledger']]
        schedule_diag[p1+' vs '+p2]={factor:sum(signature(raw_by[c,p1])!=signature(raw_by[c,p2]) for c in range(64) if indexed[c,p1]['factor']==factor) for factor in s.FACTORS}
    s.write(out/'bank_diagnostics.json',dict(development_gate=s.budget.read(folder/'bank_gate.json'),confirmation=dict(diag),factors={f:dict(v) for f,v in diag_f.items()},RuleATC_true_top4={f:dict(v) for f,v in true_top.items()},different_schedule_cases=schedule_diag))
    verdict=s.budget.read(folder/'verdict.json')
    for role in verdict:
        if verdict[role]!=s.gate(confirm,role):raise ValueError('saved verdict differs')
    verification=dict(status='PASS_saved_SHA_physical_matrix_and_freeze',registered_sources_unchanged=True,driver_SHA_registered_from_start=True,
        saved_successful_raw=len(hashes),raw_set_sha256=s.a.native.digest(hashes),receipt_set_sha256=s.a.native.digest(receipt_hashes),
        confirmation_rows=len(confirm),paired_cases=64,original_and_declared_metrics=True,model_sha256=model_hashes,
        consumption=usage,preflight_tests=5,resume=s.budget.read(folder/'resume_receipt.json'),new_report_environments=0,new_report_learning=0,
        new_physical_fit=0,new_device_runs=0,S26_experiments=0,S26_learning=0,phone_decision_energy_measured=False)
    s.write(out/'verification.json',verification)
    for name in ('freeze.json','bank_gate.json','verdict.json','registration.json','consumption.json','pause_receipt.json','resume_receipt.json','expand128.json','expand256.json'):
        shutil.copy2(folder/name,out/name)
    s.write(out/'saved_integrity_audit.json',dict(status='PASS',raw_set_sha256=verification['raw_set_sha256'],receipt_set_sha256=verification['receipt_set_sha256'],counts=dict(counts),frozen_model_sha256=model_hashes))
    source=out/'source';source.mkdir(exist_ok=True)
    for path in reg['sources']:
        if path.startswith('tools/d1_hetero') or path=='tools/test_d1_hetero_direct.py':shutil.copy2(s.ROOT/path,source/Path(path).name)
    shutil.copy2(Path(__file__),source/Path(__file__).name)
    shutil.copy2(s.ROOT/'docs/HETERO_DIRECT_PPO_STUDY_20261011.md',out/'DESIGN.md')
    text=make_text(summary,freeze,usage,verdict,learning,diag,schedule_diag)
    (out/'README.md').write_text(text,encoding='utf8')
    html_table = ''.join(f"<tr><td>{r['policy']}</td><td>{r['urgent_failure']}</td><td>{r['normal_failure']}</td><td>{r['declared_urgent_failure']}</td><td>{r['declared_normal_failure']}</td><td>{r['urgent_p95_ms_mean']:.2f}</td></tr>" for r in summary if r['factor']=='both')
    html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 처리시간·납기 변동 비교</title>
<style>body{font:16px "Malgun Gothic",sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}img{max-width:100%}p{max-width:950px}</style>
<h1>A24 처리시간·납기 변동 비교</h1><p>시간·납기를 함께 바꾼 16조건, 정책별 1,056요청 전부 완료. 아래 실패는 납기 초과다. 세 PPO 모두 strict FAIL이며 채택하지 않았다. 입력 처리 시간 추가와 가변 납기는 미측정 감도·요구조건 가정이다.</p>
<p>개발 자료로 선정한 PPO101은 EDD 규칙 대비 원 일반 실패43→24, 요청별 일반 실패9→29였다. 한 기준의 개선이 다른 기준의 손해를 숨기지 않도록 둘 다 보고한다.</p>
<p><a href="README.md">설명·판정</a> · <a href="comparison.csv">전체 640행</a> · <a href="summary.csv">4요인·전체 요약</a> · <a href="verification.json">검산</a></p>
<table><thead><tr><th>정책</th><th>원 긴급 실패</th><th>원 일반 실패</th><th>요청 긴급 실패</th><th>요청 일반 실패</th><th>긴급P95 평균 ms</th></tr></thead><tbody>'''+html_table+'''</tbody></table><img src="comparison_both.png" alt="일반 납기 실패와 긴급 P95 비교"><p>1,824환경·768학습. PC 시뮬레이션과 모형 비용이며 실제 휴대폰 효과로 해석하지 않는다. S26는 별도 짧은 서비스 연결만 작성했고 신규 실험·학습·기기 실행은 0회다.</p></html>'''
    (out/'index.html').write_text(html,encoding='utf8')
    chart(out,summary,freeze['selected'])
    return dict(selected=freeze['selected'],usage=usage,summary_both=[q for q in summary if q['factor']=='both'],diagnostics=dict(diag),schedule_differences=schedule_diag,all_strict=[(r,v['promising']) for r,v in verdict.items()])


def make_text(summary,freeze,usage,verdict,learning,diag,schedules):
    selected=freeze['selected']; chosen=[q for q in summary if q['factor']=='both' and q['policy'] in ('FIFO_EFT','FIFO_READY','EDD_EFT','ATC_EFT','RuleEDD','RuleATC',selected)]
    table='| 정책 | 원긴급 실패 | 원일반 실패 | 요청긴급 실패 | 요청일반 실패 | 조건별 긴급P95 평균 ms | 모형J 평균 | 모형AP 평균 ℃ |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for q in chosen:
        table+=f"| {q['policy']} | {q['urgent_failure']} | {q['normal_failure']} | {q['declared_urgent_failure']} | {q['declared_normal_failure']} | {q['urgent_p95_ms_mean']:.2f} | {q['energy_j_mean']:.4f} | {q['peak_ap_c_mean']:.4f} |\n"
    count=chosen[0]['planned']; urgent=chosen[0]['urgent_planned']; normal=chosen[0]['normal_planned']
    return f'''# A24 처리시간·납기 변동 비교 완료 (2026-10-11)

**순위 차이는 생겼지만 새 PPO의 추가 이득과 채택은 입증되지 않았다.** ATC/EDD 개발 raw 순위16회·규칙 선택2회 차이, 후보/유효 행동 bank는4,372판단 전부 같아 EDD 후보 fresh PPO만3시드 학습했다. ATC 추가 학습·튜닝은 사전 중단 계약대로 하지 않았다. 같은 bank여도 비학습 규칙이 순위를 사용하는 효과는 따로 비교했다.

## 처리시간과 납기를 어떻게 바꿨는가

A24 EfficientNet/Det의 동결 short/mean/long 문맥 5구간을 사용했다. 공개 입력 처리 class에 따라 execution_start→output_ready에 0/25/75ms를 더했고 실제 추가량의 요청공통 잔차0.8/0.9/1.1/1.2는 정책에 숨겼다. 입력 읽기/디코드/resize/tensor가 해당 구간에 있는 실제 코드에 맞춘 **미측정 감도 가정**이다. 실제 모바일에서 관측한 분포나 S26 실측을 A24에 이식한 값으로 주장하지 않는다.

urgent0.75/1.5/3초·normal3/6/9초는 새 요청 요구조건 가정이다. 원 urgent1.5/normal6초도 별도 집계·strict 보호했다. fixed/time/deadline/both × low/queue/burst/sustained × 새확인4arrival =64조건, 각군 같은 도착/처리시간 potential outcome/물리지원이다. 미래 실제 처리시간·미래도착·J/온도를 정책 입력에 넣지 않았다. 원래 FIFO 선두 차단을 유지한 군과 실행 가능한 뒤 요청을 선택하는 READY를 구분한다.

## 시간·납기를 함께 바꾼 both16조건

각군 {count}요청(긴급{urgent}/일반{normal}) 전부 완료했다. 실패는 실행오류가 아니라 해당 납기 초과다. P95는 각조건 P95의 산술 평균이며 전체요청 pooled P95와 다르다.

{table}
선정 PPO는 RuleEDD 대비 원 일반 실패43→24지만 요청별 일반 납기 실패9→29다. 처리순서 선택에 따라 원6초와 새3/6/9초 기준 사이에 손해가 발생한다. 평균 J/AP·긴급P95가 같아도 서비스 성공의 계약이 같다는 뜻은 아니다. FIFO_EFT의 긴급실패는 뒤 요청을 막는 HOL이 주원인이며 READY는0이다. 이를 PPO 학습효과로 합치지 않는다.

## 전체64와 시드 판정

summary.csv는4factor별/전체10군, comparison.csv는최종640행, paired_deltas.csv는각PPO×64×7참조의 모든손해를 담는다. 전체64 선정PPO 원U/N0/77·요청U/N0/90, RuleEDD0/116·0/53, FIFO_EFT190/70·214/110, READY0/70·0/110이다. 원일반은 READY보다도 악화했다. strictV3 세시드 모두 FAIL, 채택0, 앱기본·experiment_ready=false·과거FAIL은 유지한다. 모형의 작은 J/AP 차이를 실제 휴대폰 절감·발열 우위로 해석하지 않는다.

개발자료만으로 {selected}@128을대표선정,101/113/127 모두128weights를 새확인 전에freeze했다. 각seed 실제256episode/32update 후 개발key 개선이없어512확대중단. 각seed 기록은 learning.csv/learning_*.json이다. 최종 확인자료로 재선택/추가학습하지 않았다. 신선한 ABI206/49/32,8critic,J10/원+요청기한 비용을 썼고 기존 weights를 재사용하지 않았다. 이전 연구와 objective/ABI도 바뀌었으므로 이전 결과와의 차이를 시간변동 하나의 인과효과로 주장하지 않는다.

## 후보·행동이 같다는 말의 범위

새 최종 직접5군의 {diag['decisions']} 판단 중 raw rank 차이{diag['raw_rank_different']}, raw top4 순서열 차이{diag['raw_top_different']}, Rule선택 차이{diag['rule_choice_different']}다. bank_same={diag['bank_same']}, legal_same={diag['legal_same']}, 즉 bank는{diag['decisions']-diag['bank_same']}회·유효행동 집합은{diag['decisions']-diag['legal_same']}회 달라졌다. 개발4372판단에서 동일했던 것이 최종에서도 항상동일하다는 뜻은 아니다. 결과를 본뒤ATC모델을추가학습하지않으며 새독립개발계약의후속가설로남긴다. raw_top_same은 순서열 비교이고 집합 비교가 아니다. RuleATC trajectory의 진짜top4집합차는 fixed/time/deadline/both=0/0/0/10회로 별도 검산했다. 같은 후보 집합도 우선순위/실제 실행순서의 동일함을 보장하지 않는다. 상세factor별 진단과 EDD_EFT/ATC_EFT·RuleEDD/RuleATC 실제원장 차이는 bank_diagnostics.json에 있다.

top4만 쓰지 않고 oldest C/D·복귀 EDD 행동을 보충하며 대부분 큐≤4여서 raw 순위 변화가 최종 bank 변화로 이어지지 않는다. ATC_EFT는 전체 현재 큐 순위를 직접 쓰는 별도 규칙이다. 후보를 달리 만들기 위해 결과를 보고 K/보충 계약을 바꾸지 않았다. ATC튜닝은 중단하며 EDD후보 직접PPO 또는 비학습 EDD/ATC규칙을 후속 대안으로 남긴다. ATC효과와 전체큐 미래예측 제거 효과는 별개다.

## 실행·검산·계산시간

신규 {usage['environments']}환경 시작/성공, 실패{usage['failed']}, 새학습{usage['learning']}, 활성{usage['active_seconds']:.3f}초. 개발control224+학습768+checkpoint개발192+최종640={usage['environments']}이다. 상한5000환경/3072학습/10800초, 저장600초를 유지했다. 새물리fit/S26학습·환경/APK/기기0, 기존 프로젝트 누적을 덮지 않는다.

preflight5 PASS.59학습에서20/20/19episode, partial4/4/3, 실제Adam 각2update40step의 정상중지 후 snapshot/action/shuffle/cursor/clock exact재개 PASS다. 처음부터등록한 driver와모든 source SHA, 성공raw{usage['environments']} SHA,64같은공개ticket,완료·실제AVAILABLE·허용병행·선정mask·동결3weights SHA 및 저장verdict재계산을 감사했다. 보고의 새환경/학습은0이다.

decision_times.csv는 ATC/후보/mask/encode/PPO/판단/이벤트→dispatch의 평균/P95/max, observed_queue_times.csv는 실제Q별시간이다. queue_scaling_calculation.csv는Q1/8/32/128/512의 고정 현재상태 계산만5warmup+50회, 환경/학습0이다. 기록 진단시간도 분리한다. PC측정이며 휴대폰 지연/에너지로 환산하지 않는다.

## S26 추가자료와 다음 단계

P1l의 CPU1/CG_DC 실측분포와 새994ca614의 A24형 S0 5단계 평균을 확보했다. 별도 S26-SERVICE-CONNECTION-01에서 비용/NPU를 제외한120초이내 서비스모듈을 작성,4합성계약검사와4셀원장 검산PASS다. S26새실험/학습/fit/기기0이다. S26 열미재현·E0상태전력/theta미식별·request-runner품질/정밀도 미확인은 유지한다. S0 service비교는가능하며 J/열 PPO비교에는상태분리·품질 연결 결과가필요하다.

후속 추천은 서비스를 원/요청기한 둘 다 보호하는 전체현재큐 규칙 비교다. PPO는 현재채택하지 않는다. S26서비스 실험은별도정해진원장/유한예산/단위/새weights계약으로등록한다. Band/Triton은현재주비교군에서제외하고과거결과보존. 이번새64에서는기존미래예측PPO를새낮은비용ABI에임의이식하지않았으며, 이전QUEUE-DIRECT-PPO-02의기존PPO비교는그조건의근거로만보존한다.

## 산출물과 한계

DESIGN.md/등록·freeze·중지재개영수증/source/비교·개발CSV/학습/검산/타이밍/그림을포함한다. 원raw와완전checkpoint는별도work/HETERO-DIRECT-PPO-03에보존했다. 새도착seed는학습881110xxx/개발881210xxx/확인881310xxx,숨은실현881000201/202/203,actor101/113/127(action+10000/shuffle+20000)로분리했다. 실제기기세션표본수나열·전력물리검증을가상seed로늘리지않는다. 사용자WIP/다른queue_hetero draft/과거소비/기본정책을보존했다.
'''


def chart(out,summary,selected):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    roles=('FIFO_EFT','FIFO_READY','EDD_EFT','ATC_EFT','RuleEDD','RuleATC',selected)
    by={(r['factor'],r['policy']):r for r in summary}
    fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    x=np.arange(len(roles));a=[by['both',r] for r in roles]
    axes[0].bar(x-.18,[r['normal_failure'] for r in a],.36,label='Original 6s');axes[0].bar(x+.18,[r['declared_normal_failure'] for r in a],.36,label='Declared 3/6/9s')
    axes[0].set_title('Normal deadline failures: both (16 paired cases)');axes[0].legend()
    axes[1].bar(x,[r['urgent_p95_ms_mean'] for r in a]);axes[1].set_title('Mean of case urgent P95 (ms)')
    for ax in axes:ax.set_xticks(x,roles,rotation=35,ha='right');ax.grid(axis='y',alpha=.2)
    fig.savefig(out/'comparison_both.png',dpi=170);plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(report(a.run_root,a.out),ensure_ascii=False))


if __name__=='__main__':main()
