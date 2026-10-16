# FIFO·EFT와 ATC＋PPO의 동일 SLA 준수 비교

2026-10-12 KST. `SERVICE-EQUAL-COMPARE-06`은 사용자의 FIFO/EFT 추가 비교·실패 문제 점검·롤링 확인·병렬 시뮬레이션 요청에 따른 후속 작업이다. 원 `ATC-RESIDUAL-REPAIR-05`의 등록과 완료 결과를 보존하고 별도 입력·원장·예산을 사용한다. HEAD `12d64923`의 미커밋 작업이며 앱 기본과 `experiment_ready=false`는 유지한다.

## 질문과 비교군

같은 요청을 전부 끝내고 기존 납기를 지키는 조건에서 에너지와 AP 발열을 비교한다. 납기를 지켜도 응답 P95가 같다는 뜻은 아니다. 기존 strict의 조건별 P95·완료·원 납기·J/AP 보호는 그대로 적용한다. 혼잡 부하의 실패를 새 낮은 부하 결과로 덮어쓰지 않는다.

| 군 | 정의 | 분리하는 효과 |
|---|---|---|
| FIFO_FIXED | 전역 도착순 선두, 분류GPU/탐지CPU 고정 | 기존 고정 배정과 선두 차단 |
| FIFO_EFT | 전역 선두, 현재 소유자의 AVAILABLE 추정＋해당 요청 점유시간 최소 | 단일 요청 EFT 배정과 busy 경로 대기 |
| FIFO_READY | 고정 경로가 현재 가능한 가장 오래된 요청 | 고정 경로에서 선두 차단 제거 |
| FIFO_READY_EFT | 하나라도 현재 legal 경로가 있는 가장 오래된 요청, legal 경로 중 점유시간 최소 | 실행 가능 요청 선택＋ready 경로 EFT |
| RuleEDD / RuleATC | 기존 full-queue 후보·지원·물리 마스크의 비학습 규칙 | 순위 규칙 차이 |
| ANCHOR_211 / CAUSAL_211 | 05 개발 검증에서 고정한 CP0 | ATC를 보존하는 현재 PPO 경로, 학습 우위 아님 |
| LEGACY_101 | 873에서 고정한 ATC_101@128 모델, 기존214 스키마 그대로 | 이전에 학습한 직접 PPO와 비교 |

새 `FIFO_READY_EFT`는 기존 FIFO/EFT를 바꾸지 않는 별도 정책이다. 모든 ready 경로의 시작시각은 현재 `t`여서 `EFT=t+p_occ`이며 MET와 동치이다. 기존 FIFO_EFT는 busy 경로의 예상 finish까지 비교하고 그 경로가 이기면 대기한다. Android 표준 스케줄러라고 부르지 않는다.

## 사전 등록한 입력과 범위

- 원 긴급1.5초/일반6초, 단일 이미지 `work_units=1`, 같은120초 평가·35~180초 AP 창이다. 4 입력/residual 시드×4 family×4 level=64조건, 9군×64=576환경이다. variable만 시드에 따라 도착열이 달라지고 다른 family는 level별 고정 도착열에 4개 hidden residual을 짝짓는다. 64개의 독립 도착열이나 새 기기 실험이 아니다.
- low24건은1.50/1.35/1.20/1.05초 간격, variable48건은시드 고정0.75~1.05초 간격, paired48건은 Dfirst 동시/0.50초뒤C와group1.15/1.20초, sustained96건은0.70/0.75/0.80/0.85초 간격이다. 모두35초부터119초 전 도착한다. paired Dfirst는 선두 차단 진단이며 Cfirst 전체 순서 민감도는 미검증이다.
- A24 ABBA4 원384개 intact 5phase 실측 donor를 사용한다. CPU분류4/GPU분류188/탐지CPU192 표본이고 CPU분류의 약한 근거를 유지한다. 숨겨진 요청별 처리시간 draw를 도착 설계나 정책 입력에 조건부 사용하지 않는다. 공개 분포 상한으로 부하를 고른 사실과 납기 보장은 다르다.
- 동결된 기기 모형·실제AVAILABLE·응답/점유 분리·비선점·C_CPU/C_GPU/D_CPU/CG_DC≤2를 그대로 유지한다. 냉각대기·납기 연장·지원 외 병행·NPU·거절/미완료 삭제는 없다.
- 05와 과거873의 tighter·batch·과부하 결과는 그대로 남긴다. 이 새 부하에서 모두 완료했다는 결과를 기존 과부하 해결로 전용하지 않는다. 등록은 새 환경 실행 전에 source/driver/test/input/model SHA와 시드887을 고정했다.

## 병렬 실행 및 검증

4개 Python 프로세스에 각각 서로 겹치지 않는16조건×9=144환경을 예약했다. 각자의 owner lock·시계·시작/완료/실패 원장·raw/rows를 갖는다. 개별cap150 환경/학습0, 합cap600 환경/학습0이며 cap을 재설정하지 않는다. 매 환경 시작도 소비로 세고 원장을 여러 프로세스가 함께 append하지 않는다.

실제576환경/학습0/실패0, 각144환경이 완료됐다. 개별 활성16.188~16.266초, 활성 합64.845초다. 각 프로세스는 동시에 실행됐으므로 활성 합은 전체 wall time과 다르다. 다른 작업과 공유하는 PC의 시간이며 휴대폰 추론시간·에너지로 바꾸지 않는다. native 논리 판단/기록/dispatch overhead0 가정도 그대로다.

합성/순수 검사5개가 PASS했다. 초기 검사1건은 fixture 단계 이름 `PERSISTING`을 실제 enum `PERSISTED`로 바로잡은 뒤 재검사했고 환경·학습 소비는0이다. 과거EFT의busy경로선택과 새readyEFT의GPU dispatch 차이, 선두 건너뛰기/지원, 응답 후 소유권 유지, 도착/HOLD 취소·revision 중복, workload/cap/원기한을 검사했다. 이 PASS를 정책 우수성이나 기기 PASS로 쓰지 않는다.

원576행·공통 입력·동결source/model SHA·중복 없는 matrix·지원/단계/응답/AVAILABLE/소유자·전체 공개event·mask를 확인한다. 공통 SLA 준수조건은 모든9군이 같은조건에서 전량완료하고 U/N 원/선언 실패0인 교집합으로 사전 정의했다. 실제64/64 조건이다. 제외/실패행삭제0이다.

## 롤링 계약

`d1_atc_repair_engine.py`의 실제 이벤트 루프는 같은시각 CPU→GPU단계완료/해제→ordinal순 새도착→dispatch 완료→현재상태관측/선택 순이다. `d1_atc_repair_policy.py`는 새 arrival/실제AVAILABLE에서 HOLD를 취소하고 자원 ETA 타이머에서 재판단한다. `(now,event_seq,queue/owners revision)` 중복을 막고 CG_DC 두번째 dispatch는 첫번째 실제receipt·소유자·같은시각·현재물리합법성을 다시 검사한다.

현재 미시작 큐에 ATC top4＋coverage/복귀 후보를 만들고 행동·마스크·동결 PPO argmax를 다시 적용한다. 실행 중 요청의 중단·이동은 없으며 응답만 준비돼도 자원을 풀지 않는다. 미래 큐 rollout/place/전체큐 AP·J 예측은 runtime trap으로 금지했다. 이것은 **사건 기반 온라인 스케줄링의 반복 재판단**이고 별도의 미래 계획 구간을 최적화하는 rolling horizon은 아니다.

## 결과·채택·후속 경계

결과는 [전체 비교표](results/service_equal_compare_20261012/RESULTS.md), 사용자 산출물은 `outputs/SERVICE-EQUAL-COMPARE-06`이다. 모든 정책이 같은3456건을 완료하고 원 납기 실패0을 기록해 열/J 비교가 가능해졌다. 다만 P95와 에너지의 교환이 남아 기존 strict의 모든 조건·모든 비교 보호를 통과한 새 채택은0이다.

원 조건별 손해를 평균으로 가리지 않는다. common-SLA 비용표와 원 strict는 별개이고, 단독 PC 현재상태 kernel(q1/8/32/128/512)은 환경/학습0회 프로파일로 별도 보고한다. 05의 신규학습768회/환경2404회 및 다른 S26/Common 과제 이력을 합쳐 초기화하지 않는다. 이 후속 과제의 신규 fit·APK·기기·S26·NPU 실행은 각각0회다.


## 후속 사후 진단 완료와 현재 누적 (2026-10-12)

원576 공통확인을 유지한 뒤 이미 본05 single_fixed의low/sustained8조건에서 보완READY_EFT를8환경 추가했다. diagnostic_registration.json에 먼저source/oldinput/886realization/2환경씩분할을고정했고 원cap600/각150을 바꾸지 않았다. 현재누적584환경/학습0/실패0·각146환경이며활성합65.595초다. 이전64.845초는원576단계 기록이다. 원FIFO/EFT/FIFO_READY/ATC 32행은재실행하지않았다. 해당864건에서긴급실패FIFO4/EFT5→보완0, 일반실패/미완료0이다. 단일혼잡의선두차단진단이며batch 과부하/모든원조건의해결은아니다.

RR/Greedy는별도07의128확인＋16같은과거진단=144환경/학습0·cap160이다. 같은진단에서Greedy U185/408, RR0이라낮은공통부하SLA0을혼잡보장으로일반화하지않는다. 11군704행과기존부하진단은[MOBILE_BASIC_BASELINES_20261012.md](MOBILE_BASIC_BASELINES_20261012.md)에연결했다.
