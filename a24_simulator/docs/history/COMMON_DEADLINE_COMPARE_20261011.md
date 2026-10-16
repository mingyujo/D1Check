# 공통 납기·전체 큐 비교 — COMMON-DEADLINE-COMPARE-04

2026-10-11 KST. 사용자 “적어도 비교는 되게” 지시를 구현하는 새 별도 과제다. 비교 가능성과 정책 채택을 분리하고 기존 결과/strict/기본/experiment_ready=false는 유지한다. 원 사용자 WIP와 동시 QUEUE-HETERO-PPO-03/S26 과제에 쓰지 않도록 `work/common-compare-repo`의 detached HEAD12d64923에서 소스·입력을 고정한다.

## 동일한 비교 문제

모든 주 비교군은 같은 도착 요청·실제 시간 표본·물리 지원·전체 현재 큐·운영 계약·요청별 납기를 사용한다. 학습·개발 선정·최종 주순위는 **같은 요청별 declared deadline 한 개**를 평가한다. 긴급0.5/1/1.5초, 일반2/4/6초는 원 긴급1.5/일반6초보다 크지 않으므로 이전의 확대 납기와 원기준 상충을 제거한다. 납기는 모바일 표준 또는 실측 이용자 요구분포가 아닌 사전 고정 연구 요청 조건이다.

원1.5/6초 실패는 보조/기존 guard로 따로 기록한다. 주순위에 혼합하거나 별도 학습 목표로 넣지 않는다. strict 미통과는 배포 미채택을 뜻하며, 같은 목적의 순위·동률·조건별 승패 비교를 무효화하지 않는다.

주지표는 조건별 중요도 가중 응답 납기 실패율 `M=Σ w·1[미응답 또는 R>D]/Σw`, 중요도 urgent2/normal1이다. 이는 정책 중요도이며 실제 금전적 지연비용이 아니다. 보조지표는 무차원 `T=Σ w·max(R/D−1,0)/Σw`, 긴급 P95 ms, 완료·자원 미완료, 원기준 실패, J/AP다. 응답이 납기내 완료되고 AVAILABLE만 창밖이면 응답실패로 바꾸지 않는다. 미응답은 실패에 포함하고 T는 종료창까지의 지연 하한임을 표시한다.

주평균은 각 조건 M/T의 **macro 평균**으로 학습/개발/확인 선정 정의를 맞춘다. 전체 요청 가중분모의 pooled 실패율도 별도 제공한다. 일부 조건의 손해는 paired delta/win·tie·loss/최악손해와 family별 표로 남긴다. 새로운 그림이나 주순위를 만들 때 좋은 지표만 선택하지 않는다.

## 선택 공간과 물리·운영 계약

전체 arrived/unstarted 큐를 모두 입력하고 top-K/oldest 보충으로 자르지 않는다. 요청 슬롯 상한24, 초과는 오류로 중단하고 조용히 잘라내지 않는다. 단일 요청을 commit한 뒤 같은 시각 재판단하여 합법적 CG_DC 병행을 채운다. 묶음 actor action은 없지만 실제 최대2건 병행은 모든 군에 동일하게 허용한다.

물리 mask는 C_CPU/C_GPU/D_CPU/CG_DC·실제 owner·AVAILABLE·중복을 검사한다. 비선점/이동 금지, 응답과 AVAILABLE 분리, NPU/냉각 없음은 유지한다. 추가 운영 계약은 “실행 가능한 행동이 있으면 WAIT를 선택하지 않음”이다. 이는 WAIT의 물리 불가능을 뜻하지 않으므로 물리 mask와 별도 저장한다.

| 군 | 요청 순서 | 자원 배정 |
|---|---|---|
| FIFO_READY | 현재 실행 가능한 요청 중 도착순 | 공통 현재 EFT-ready |
| SPT | 공통 선택 경로의 예상 점유시간이 짧은 순 | 공통 현재 EFT-ready |
| EDD | 요청별 절대 납기순 | 공통 현재 EFT-ready |
| ATC | ready 집합의 공통 경로 p_occ/r·w·d 기반 ATC | 공통 현재 EFT-ready |
| ORDER PPO ×3seed | 같은 ready 요청 중 학습 선택 | 위 네 군과 같은 공통 현재 EFT-ready |
| JOINT PPO ×3seed | 요청과 CPU/GPU를 학습 선택 | 모든 현재 legal 지원 경로, 배정 효과를 분리하는 부차 비교 |

공통 EFT-ready는 지금 실제 실행 가능한 지원 경로의 추정 AVAILABLE 종료가 빠른 경로 하나다. 미래 큐 소진·J/AP 예측 없음, busy 경로의 예측 반환이 실제 owner를 해제하지 않음. CPU/GPU 둘이 현재 legal이면 p_occ 최소·CPU 동점 우선이다. 원 글로벌 FIFO HOL은 이전 기록으로 보존하지만 주 비교는 FIFO_READY로 명확히 이름 붙인다. FIFO를 혼자 기다리게 하여 PPO의 요청 선택효과와 HOL 해소를 섞지 않는다.

ATC 식은 `log(p_occ)-log(w)+max(d−t−r,0)/(2 mean_ready_p_occ)` 최소이며 ready 요청의 공통 선택 경로를 쓴다. mean은 같은 ready 집합, 동점은arrival/ordinal/id다. 네 규칙과 ORDER PPO는 물리/운영/배정 mask가 정확히 같다. **같은 후보 집합은 공정한 통제다.** 알고리즘 차이는 실제 요청·자원 선택·납기 실패에서 판단하며 후보를 억지로 달리 만들지 않는다.

## 시간 변동의 근거와 가정

원 A24 ABBA4 `requests.csv`의 intact5phase384를 그대로 hidden keyed bootstrap한다. SHA `08421e953cd3ee606ff1d9e6cbc53e649a86a62548791a1494b3279e9953bce9`, C_CPU4/C_GPU188/D_CPU192다. 점유 관측 범위는 C_CPU169.6~186.3ms, C_GPU230.9~391.5ms, D_CPU605.1~656.0ms다. CPU 표본4는 분포 근거가 약하다. 같은 기존 실측의 독립 난수 재생은 새 독립 기기 검증이 아니다.

초기 추정은 위 표본의 평균이며 완료후 class/backend별 EMA0.1만 사용한다. 미래 실제 표본/남은 left/미래 도착/미래 온도/J를 policy에 주지 않는다. 요청ID·backend·arrival seed·별도 phase realization seed로 잠재 표본을 고정하여 policy dispatch 순서가 표본을 바꾸지 않게 한다.

| 조건 | 처리시간 | 납기 |
|---|---|---|
| measured_fixed | 실측 whole-phase bootstrap만 | 원1.5/6초 |
| measured_variable — 주 결과 | 같은 실측 bootstrap만 | 긴급0.5/1/1.5·일반2/4/6초 |
| io_fixed | 위 bootstrap＋공개 I/O 추가0/25/75ms 가정 | 원1.5/6초 |
| io_variable — 감도 | 위 bootstrap＋공개 I/O 추가 가정 | 위 변동 납기 |

추가 I/O는 A24 실제 실행기 경계에 맞춰 S→O 구간에 넣고 평균1 잔차0.8/0.9/1.1/1.2를 요청별 두 잠재 자원에 공유한다. 이 25/75ms와 예측 가능한 입력 클래스는 미측정 가정이며 주 실측 bootstrap 조건과 분리한다. batch_n1/2/3 확대는 이번에 사용하지 않는다. 상태별 J/AP 계수는 기존 동결 모형 전이 가정이며 온도/J 우위를 실기기 검증으로 해석하지 않는다.

## PPO·데이터·계산 계약

state510 = global24+request24×18+lane2×15+declared deadline24. 행동은single job38+present/kind3+fallback1=42. 현재 행동K≤2C+D+막힌WAIT≤49이며 K는 가변이다. batch에서만 최대K까지0벡터/false mask로 padding한다. 24×24 pair 열거는 없으므로 기존7/32/192행동 숫자를 근거없이 유지하지 않는다. shared action actor·state critic의 native PPO 수학을 재사용하되 새 ABI/가중치/Adam/RNG로 시작한다.

3critic target은 서비스 reward `−M−0.2T`, J120 residual/10J cost, resource incomplete/planned cost다. energy 상대 가중치0.05·미완료100, 미완료 dual eta0.01/cap100, gamma1/noGAE. 서비스 희생 금지를 학습식만으로 보장하지 않고 최종 strict와 조건별 표로 검사한다. update8episode/최대4epoch/minibatch256/lr0.0003/clip0.2/grad0.5/KL0.03다. variable K reference PPO와 minibatch 합 손실의 동치를 검사한다.

fresh base seeds211/223/239를 ORDER/JOINT에 짝 초기화하되 learner/action/shuffle 객체 상태는 독립 관리한다. action seed+10000/shuffle+20000. train arrival891110101..891110164의256episode(64×4family, factor순환), dev891210101/102×4family×4factor=32, final891310101..104×4×4=64다. train/dev/final실현891000201/202/203을 분리한다. 스키마·source·driver자체·실측CSV·input SHA를 등록부터 잠근다.

128→256 확대는 기계검증(실제positive actor gradient/actor변경/fallback0/물리 template 경험/물리원장)으로 사전 정한 유한 예산을 연장하는 단계다. 개발 향상을 검사했다고 주장하지 않는다.256 절대상한, 개발은128/256 중 미완료→macroM→macroT→긴급P95→J→AP→이른checkpoint로 한번 선택한다. 모드별 대표와 모든seed SHA를 final64 전에 freeze한다. 최종 masked argmax·추론만, 확인 자료로 재선택/추가학습 없음.

상한 새환경3000/학습1536/A24학습1536/S26학습0/active3600초/reserve300초. 최대1536학습+128control+384stage개발+640확인=2688환경, 실패도 소비에 포함한다. 새raw-free6검사PASS이며 실제Adam1update/partial2/난수복원과 입력누수·same mask·overflow·의미있는ATC차이·응답≠점유끝·가변K loss를 확인했다. 실제59학습 이후 checkpoint partial/Adam/RNG/clock 중지재개도 별도 검산한다. 원 종료 예산·다른 실험 소비는 초기화/합산하지 않는다.

## 보고·채택·S26

주 표는 measured_variable 16조건의 중요도 가중 납기 실패율·조건별 M승/동/패·긴급/일반 실패·P95·완료를 동일 열로 낸다. 감도 io_variable과 고정조건은 별도 표다. ORDER/JOINT를 합쳐 한 PPO로 골라 좋은 값만 보고하지 않는다. 비교에서 PPO가 나쁘거나 모든 정책이 동률인 것도 그대로 보고한다.

strictV4의서비스/물리/원상한은 유지하고 모든 참조(FIFO_READY/SPT/EDD/ATC)에 대해 매조건 비악화ε0·원납기 guard·완료·low/sustained 절대실패0 뒤 J/AP엄격개선을 검사한다. 전 지표 채택FAIL도 비교 순위 표를 숨기는 이유가 아니다. 앱 기본/experiment_ready=false 유지·기기0이다.

S26 P1l/a24fmt 서비스 존재 및 별도 동시 연결 작업은 보존하며 본과제에서는 S26 모형/데이터/NPU/3자원을 사용하지 않는다. P1l 서비스탐색용/열미재현/J미검증·품질/시계 gate를 이 비교로 해결했다고 부르지 않는다. 새fit/APK/ADB/기기/S26학습0이다.

전문가 사전 검토와 최종 감사는 results/common_deadline_compare_20261011의 ie/mobile/rl_review.md. 실제 source는 tools/d1_common_compare_{data,policy,engine,ppo,budget,study}.py·test_d1_common_compare.py다. 코드 작성/단위검사/PC환경/정책효과/기기검증을 구분하고 actual source/input/model/raw SHA를 결과에 포함한다.
