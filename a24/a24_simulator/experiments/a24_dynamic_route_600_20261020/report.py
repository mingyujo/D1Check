"""Read saved audited results; no policy/environment execution."""
import json
from pathlib import Path
import study
from study import H,O,R,read,new,stamp,MODES

def f(v,n=3):return '미정' if v is None else f'{v:.{n}f}'
def main():
    assert not any((O/n).exists() for n in ('INTERPRETATION_KO.md','REPORT_KO.md','CONTINUE_RUNNING.md','ROUTE_DIAGNOSIS.json'))
    summary=read(O/'SUMMARY.json');derived=read(O/'DERIVED.json');groups={g['policy']:g for g in summary['groups']}
    assert read(O/'AUDIT.json')['status']=='PASS'
    diagnosis=[]
    for mode in MODES:
        fixed=mode.replace('_DYN','_CPU')
        for case in study.old.cases():
            curr=next(r for r in derived if r['case']==case['id'] and r['policy']==mode)
            base=next(r for r in derived if r['case']==case['id'] and r['policy']==fixed)
            if curr.get('failed'):diagnosis.append(dict(policy=mode,case=case['id'],failed=True));continue
            a=read(R/curr['raw']['path']);b=read(R/base['raw']['path'])
            qs={q['request_id']:q for q in b['result']['requests']}
            changed={k:sum(q[k]!=qs[q['request_id']][k] for q in a['result']['requests']) for k in ('route','dispatch_ns','response_ns','available_ns')}
            both=[c for c in a['calls'] if len(c['free_routes'])==2]
            diagnosis.append(dict(policy=mode,case=case['id'],pattern=curr['pattern'],changed_vs_CPU_first=changed,both_routes_free=len(both),GPU_chosen_with_both_free=sum(c['action']['route']=='GPU' for c in both),actual_routes=curr['route_counts'],saved_J_vs_CPU=base['common']['J']-curr['common']['J'],AP_delta_vs_CPU=curr['common']['AP']-base['common']['AP'],comparison_end_ns=curr['common_end_ns']))
    new(O/'ROUTE_DIAGNOSIS.json',dict(status='PASS',utc=stamp(),cases=diagnosis,new_environment=0))
    names={'FIFO_CPU':'FIFO·CPU우선','EDF_CPU':'EDF·CPU우선','RR_CPU':'RR·CPU우선','FIFO_DYN':'FIFO·동적배정','EDF_DYN':'EDF·동적배정','RR_DYN':'RR·동적배정','IDLE_BC':'우리정책·롤링+ATC+BC+대기보완','BC':'기존48특징BC','OLD_PPO':'기존PPO','ATC_BC':'대기보완 전 ATC+BC'}
    columns='|정책|소비 J*|평균AP ℃|전체정시|긴급정시|전체P95 초|긴급P95 초|미완료|\n|---|---:|---:|---|---|---:|---:|---:|\n'
    def table(ids):
        out=columns
        for key in ids:
            g=groups[key]
            if g['failed']:out+=f"|{names[key]}|미정|미정|미정|미정|미정|미정|FAIL {g['failed']}|\n";continue
            sv=g['service'];out+=f"|{names[key]}|{f(g['common_J'])}|{f(g['AP'])}|{sv['ALL']['on']}/{sv['ALL']['n']}|{sv['U']['on']}/{sv['U']['n']}|{f(sv['ALL']['mean_session_P95_s'])}|{f(sv['U']['mean_session_P95_s'])}|{g['incomplete']}|\n"
        return out
    intro='# A24 FIFO·EDF·RR 공통 동적 장치 배정 비교\n\n2026-10-20, 부하0.4·600초·두패턴·CPU3/GPU1·ORIGINAL 모형이다. 새 동적기준선6환경만 실행했고 기존14세션과 현재 우리정책은 저장 원자료를 재사용했다. 명목 응답시간이 짧은 현재 가용 장치에 즉시 배정하며, 요청 순서는 FIFO/EDF/C·D군RR 각각 유지한다. 기준선에는 롤링·학습·자발적WAIT를 추가하지 않았다. 새fit/NN/실기기0이다.\n\n소비·AP·P95는 두 패턴의 세션평균, 정시/미완료는 합계다. 소비·온도는 패턴별 전체10정책의 동일 공통 완료창으로 재적분했다. J*는 미교정 모형의 예측 소비다. 두패턴은 기존주기의 반복이며 독립표본/실기기절감 증거가 아니다.\n\n'
    md=intro+table([*MODES,'IDLE_BC'])
    md+='\n## 우리 정책과 동적 기준선의 차이\n\n절감이 양수이면 우리정책이 덜 소비한다. AP차와 P95차는 우리정책−기준선이며 양수이면 더 높거나 느리다.\n\n|동적 기준선|우리정책 소비 절감 J*|절감 %|평균AP 차 ℃|긴급P95 차 초|전체P95 차 초|\n|---|---:|---:|---:|---:|---:|\n'
    for c in summary['IDLE_BC_comparisons']:
        if c['baseline'] in MODES:md+=f"|{names[c['baseline']]}|{f(c['saved_common_J'])}|{f(c['saving_pct'])}|{f(c['AP_delta'])}|{f(c['U_P95_delta_s'])}|{f(c['ALL_P95_delta_s'])}|\n"
    md+='\n## CPU 우선과 실제 행동 차이\n\n|정책|패턴|CPU우선과 경로 다른 요청 수|배정시각 다른 요청 수|두장치 가용 결정 수|그중GPU선택 수|CPU우선 대비 소비 절감 J*|\n|---|---:|---:|---:|---:|---:|---:|\n'
    for d in diagnosis:
        if not d.get('failed'):md+=f"|{names[d['policy']]}|{d['pattern']}|{d['changed_vs_CPU_first']['route']}|{d['changed_vs_CPU_first']['dispatch_ns']}|{d['both_routes_free']}|{d['GPU_chosen_with_both_free']}|{f(d['saved_J_vs_CPU'])}|\n"
    md+='\n## 해석 범위와 검증\n\n동적기준선의 목표는 선택한 한 요청의 명목 응답시간이다. 우리정책은 소비·열·납기 비용의 롤링+ATC+BC 결합이며, 이 비교만으로 ATC/롤링/BC 각각의 효과를 분리하지 않는다. 현재온도와 현재 CPU실행단계 경합을 유지한 단순 예측이라 실제 미래 응답의 정확한 예언은 아니다. CPU/GPU 고정 우선은 없으며, 정확한 동점만 공개ID/경로 SHA256으로 결정한다. 가능한 장치가 하나면 그 장치에 즉시 배정한다.\n\n[전체10정책/20행](REPORT_KO.md) · [계산 원자료](DERIVED.json) · [비교 수치](SUMMARY.json) · [장치 변화](ROUTE_DIAGNOSIS.json) · [독립 감사](AUDIT.json) · [저장 상태 재생](REPLAY.json) · [사전 설계](../../experiments/a24_dynamic_route_600_20261020/PROTOCOL.md). 독립감사는 물리 적합성/실기기 정확도 인증과 구분한다.\n'
    (O/'INTERPRETATION_KO.md').write_text(md,encoding='utf-8')
    full=intro+table(list(names))+'\n## 패턴별20행\n\n|패턴|정책|공통창 초|소비 J*|평균AP ℃|전체정시|긴급정시|긴급P95 초|공급창 J*|자체완료+활동꼬리 J*|미완료|자료|\n|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|---|\n'
    for d in derived:
        if d.get('failed'):full+=f"|—|{d['policy']}|미정|미정|미정|미정|미정|미정|미정|미정|FAIL|원행보존|\n";continue
        sv=d['service'];full+=f"|{d['pattern']}|{d['policy']}|{f(d['common_end_ns']/1e9-35)}|{f(d['common']['J'])}|{f(d['common']['AP'])}|{sv['ALL']['on']}/{sv['ALL']['n']}|{sv['U']['on']}/{sv['U']['n']}|{f(sv['U']['P95'])}|{f(d['supply']['J'])}|{f(d['own_tail_J'])}|{d['incomplete']}|{'저장재사용' if d['reused'] else '새평가'}|\n"
    full+='\n[해석·장치변화·우리정책 대비 차이](INTERPRETATION_KO.md) · [독립 물리/서비스/정책선택 검사](AUDIT.json) · [모든 응답·평균/pooled P95](DERIVED.json) · [현재우리정책의 기존 NN 감사](../A24_IDLE_WAIT600_20261019_01/NN_AUDIT.json). 최고온도는 비교대상 모두 동일한 trace 끝점 기준이며 연속구간 peak는 저장 원자료에 있다. 과거CPU우선 결과의 보고서 자체는 변경하지 않고 이번 공통창만 새로 계산했다. 기존BC/우리정책 차이와 기존ATC_BC의 긴급1건 지각도 전량 보존한다.\n'
    (O/'REPORT_KO.md').write_text(full,encoding='utf-8')
    (O/'CONTINUE_RUNNING.md').write_text('# 재개 안내\n\n이번6개 동적기준선 평가와 저장14세션의 비교를 완료했다. 완료실험을 재시작하지 않는다. 먼저 INTERPRETATION_KO.md, REPORT_KO.md, SUMMARY.json, ROUTE_DIAGNOSIS.json, AUDIT.json, FINAL_HANDOFF_PROOF.json을 읽는다. 현재HEAD/미커밋 상태는 최종증명을 따른다. 새학습/NN/실기기/물리fit0, 현재6단위·도출누적137725·추가자동실험/재시도0이다. GitHub게시/커밋은 미수행이다.\n',encoding='utf-8')
    print('DYNAMIC600_REPORT',json.dumps(diagnosis,ensure_ascii=False))
if __name__=='__main__':main()
