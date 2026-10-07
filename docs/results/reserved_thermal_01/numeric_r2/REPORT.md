# 단계3 수치 보완·대조 검증 결과

2026-10-08 KST · 48조건 개발/회귀 · 12정책/576논리행

**수치 구현의 문제를 수정했지만 Band·강한EFT보다 낫다는 목표는 미충족이다.** 수정본과 원 pilot의 주요 성능 지표는 동일했다. 원48행은 첫4원소스/44첫보완소스라는 이력을 유지하며, 이번48행은 이동량을 제한한 한 버전으로 별도 실행했다.

## 실행과 검증

- 직접 함수9검증 PASS(엔진0): 앞 경계의 미세 겹침, 미래 예약의1.62초 반례, 여러 충돌의 누적 이동,0.25초 의도적 간격, 지원 병행/같은 lane, 후보 탈락·원 fallback, 실제 WAIT 중복 제거, cap/J/선택 보존, 무등록 엔진 차단.
- 기존5수작업 사례를 원본/수정본 각각 실행해10환경을 소비했다. 전체 ledger·완료·기한·응답·J/AP가 일치했다.
- 수정본48환경·3,168/3,168완료, 긴급 실패0, 일반 기한 실패53. 주 low/sustained24조건2,592/2,592 기한 내 완료. 기존432행+원 pilot48+완료된 내부EFT48을 재사용해 전체576행.
- 추가58환경·실패추가0, 누적129(성공126/실패3). 단계2잔여383/전체잔여19,871. 본학습/이 작업의 기기·ADB·실측0.
- 계획 함수에서 실제 보정108회, 최대 이동0.458357ns. 이동량 초과/수치 후보 거절0. 원 반례가 실제48조건에서 발생했다는 증거는 없고, 이번 보정 전후 기록에서는 모두1ns 이내였다.

## 동일 조건 결과

주평가24조건 평균, 수정본−기준. 전체 기한·완료 요구를 함께 읽는다.

| 기준 | AP 최고값 차이(°C) | 공통120초 J 차이 | 주24 공동 감소 |
|---|---:|---:|---:|
| Triton 제한해제/2건허용 |−0.119788|−0.770236|24|
| Band 요청 대응 |−0.048470|+0.154012|0|
| SHARED_EFT |−0.059351|+0.088176|0|
| 내부 EFT_REFERENCE |−0.002364|+0.003087|2|
| 원 pilot 후보 |0|0|0|

전체48조건의 일반 실패는 수정본/내부EFT53, Band/SHARED_EFT/강한Triton36이다. 추가 실패17을 새 예약 규칙만의 영향으로 귀속할 수 없다. 내부EFT와 SHARED_EFT의 곧 비는 자원 대기/즉시 배정 차이를 별도 대조했다. 내부EFT 대비 비용 차이도 작으며 실측 개선 근거로 승격하지 않는다.

## RL 판정과 다음 단계

scoring callback12,623 중 서로 다른 실제 DISPATCH/WAIT 반환이 있는 경우319, 첫 요청/backend가 다른 경우0. 같은 상태의 내부 기준계획 대비 AP감소·J비증가 대안162번, J감소·AP비증가 대안0이다. 계획 수가 많다는 이유만으로 의미 있는 학습 행동이 많다고 하지 않는다.

현재 cap/J 검사로도 최종예산 초과23조건·관측 cap초과319요청이 발생했다. 미래 도착과 처리문맥 오차에 대한 전역 서비스/J 보장이 아니다. 현 후보군을 대상으로 본학습6,144회를 자동 시작할 근거는 부족하므로 RL0으로 보류했다. 강화학습 일반의 실패나 개선 불가능 증명은 아니다. [규칙만 최종확인 결정](RULE_ONLY_REVIEW.md)에 따라 새로운 합성192조건을 별도 동결해 평가한다.

## 근거와 한계

A24 분류 CPU/GPU·탐지CPU·측정된 허용 병행만 사용한다. 모형 계수와 기본 정책은 유지했다. 요청 완료/저장/worker release와 실제lane반환을 구분하고 미래요청/실현비용은 온라인 controller에 주지 않았다. J는 공통0–120초, AP는35–180초·1초 격자와 경계의 모형값이다. 미완료면 AP180을null로 두며 부분J를 전량 비교의 이득으로 인정하지 않는다. 임의 표면 온도/NPU/DVFS/열한도/0미측정비용을 추가하지 않는다. host 판단시간은PC계산이며 기기 overhead는 미측정이다.

Band는 subgraph HEFT를 전체 요청으로 대응한 제한적 재현, Triton은 rate-limit과priority/FIFO를 두 고정 요청 instance로 대응한 제한적 재현이다. [Band 출처/대응](../../external_rules_01/mapping.md), [Triton 출처/설정](../../external_rules_02/mapping.md). 외부 시스템 전체를 실행한 비교가 아니며 실제 제품보다 우월하다고 말할 수 없다. Ente는 시작허가를 제어하므로 같은자원배정과 함께 비교한 기존별도결과를 유지하며 이번 자원 배정 성적표에는 포함하지 않는다.

[오프라인 화면](index.html) · [전체CSV](results.csv) · [짝비교](pairs.csv) · [진단](diagnostics.csv) · [원본·소스검증](verification.json) · [브라우저 확인](browser_verification.json) · [그림](figures/) · [실행동결](registration.json).

## 재현

기존 로컬 장부/원 item이 있는 경우 완료 receipt를 확인하며 추가환경0으로 재개할 수 있다. 상태가 없으면 승인 장부를 조용히 새로 만들지 않는다. 새 연구 재실행은 보존된 계약을 새출력/누적예산에 연결해야 한다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_reserved_thermal_numeric_r2 -v
python -B -m tools.d1_reserved_thermal_numeric_study check
python -B -m tools.d1_reserved_thermal_numeric_study pilot
python -B -m tools.d1_reserved_thermal_numeric_analysis
python -B -m tools.d1_reserved_dashboard_check docs/results/reserved_thermal_01/numeric_r2/index.html 592 50
```

소스/HEAD/명령·시각·미커밋 여부는registration/implementation_verification/verification/browser_verification에 분리한다. 표 생성 중 대표자료의family/policy 중복keyword 오류를 수정하고 엔진 추가 없이 재분석했다. 브라우저 검사는module 실행으로 고쳐592행/검색50행/5그림을 확인했다. 원 동결18소스·첫보완2소스·48gzip·기본·strict·experiment_ready=false·사용자자료·다른worktree는 보존한다.
