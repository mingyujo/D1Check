# ATC-ENERGY-GUARD-13 — 서비스 보호와 비용 보상 대조

상태: 사용자 승인에 따른 구현·등록 전 준비. 신규 환경/학습/기기 실행은 현재0이다. 실행 이후 실제 수치는13의 원장에 기록한다. 현재12 장기학습의 source92·등록·입력·모델·원장·PID·우선순위·15:59:47KST 종료시각은 변경하지 않는다.

## 문제와 대조

현재 WAIT1 연결에서 평균 응답 개선은 확인했지만 모형 J/AP 이득은 작고 조건별 서비스/응답/비용 손해가 남았다. 같은 실행 구조에서 비용 보상 비중과 서비스 악화 시 비용 혜택의 처리, 발열 학습 label의 시간창을 따로 대조한다. 보상 변경만으로 응답·납기를 보장한다고 주장하지 않는다.

| 목적 | 에너지/AP 비용 가중치 | 서비스/P95 악화 시 비용 혜택 | 사후 AP label 종료 |
|---|---:|---|---:|
| CONTROL | 1/1 | 기존 signed cost | 120초 |
| ECO5 | 5/5 | 기존 signed cost | 120초 |
| GATED_ECO5 | 5/5 | 음수 비용의 혜택만0 | 120초 |
| GATED_ECO5_AP180 | 5/5 | 음수 비용의 혜택만0 | 180초 |

CONTROL→ECO5는 비용 가중치, ECO5→GATED_ECO5는 gating, GATED_ECO5→AP180은 학습 시간창 변경을 분리한다. 가중치5는 PPO advantage 정규화 이후 gradient가5배라는 뜻이 아니다. 초기3목적 안은 등록/실행0에서4목적으로 확장했다.

원 URGENT_HOLD 응답 reward·서비스6비용의100 가중치·P95 비용20·E10J/AP0.1°C/P95100ms 단위를 유지한다. 즉각 reward와 원 KPI의 단위를 혼동하지 않는다. GATE가 실패한 episode의 frame E/AP cost만 `max(c,0)`으로 바꾸어 비용 절감에 대한 음수 cost 혜택을 제거한다. 양의 비용 손해와 응답/서비스/P95 비용은 유지하고 frame target·episode costs를 일치시킨다. GATE는 같은 실현의 RuleATC 대비 완료/units·선언/원 U/N·완료 긴급P95가 모두 비악화일 때 통과한다. 누락/미완료를0으로 넣지 않는다. 원 raw KPI와 실패 판정은 변경하지 않는다.

기존 AP label은120초까지의 사후 suffix proxy다. 원 평가 AP는35~180초 peak이므로 두 창을 같다고 설명하지 않는다. AP180 arm만 기존 before-peak anchor 규칙을 유지하면서 사후 curve의 suffix 끝을180까지 늘린다. 평가 J120/AP35~180·strict는 모든 목적에 동일하다. 어느 label도 온라인 입력·후보·마스크에 넣지 않는다.

## 공통 운영과 초기화

현재 WAIT1의 ATC top4＋coverage/fallback 최대8요청, 물리 mask, 상태226/행동57/패딩32/최대29행동, NN teacher52 숨김·ATC rank/gap·WAIT prior를 유지한다. 새도착/실제AVAILABLE/자원타이머마다 미시작 요청을 재판단한다. 비선점·응답과점유종료 분리·C_CPU/C_GPU/D_CPU/CG_DC≤2·필요자원WAIT만 허용한다. mask는 물리 실행 가능성 검사이며 납기 보장 장치가 아니다. 다른 즉시 합법 시작이 있어도 막힌 지원자원을 기다릴 수 있다.

4목적×3seed1013/1019/1021의12 fresh 모델이다. 각seed의 목적별 초기 network·Adam·action/shuffle RNG 조건을 같게 하고, 목적·critic 의미가 바뀌므로 과거 학습 가중치를 신규학습에 계승하지 않는다. native PPO loss/update와 기존 ActorCritic 구조를 재사용하되 별도 constructor/objective/version/복원 검사를 둔다. 기존 파일이나 기존 모듈의 OBJECTIVES 전역을 바꾸지 않는다. CONTROL의 target/loss 입력은 원 목적과 exact 비교한다.

EFT0·Greedy/RR/FIFO 독립 비교군, 미래 전체큐 rollout/place/J/AP·실제 미래도착/duration 입력0, 냉각/NPU/APK/기기/S26/물리fit/외부전송0이다. 현재 기본 정책/experiment_ready=false를 유지한다.

## 자료와 비교

12의 이미 완료된 TRAIN2816/DEV176, RuleATC teacher2816＋규칙DEV1056＋원4096 DEV528의4400참조를 source/input/receipt/raw SHA로 결합해 재사용한다. 이 복사·참조는13 신규 환경0이다. 같은 model/initial/arrival_seed/realization에 맞는 교사인지 검사한다. 현재12 latest·개발 선정·최종 결과는13의 선정에 사용하지 않는다.

13 최종은 registry/local 충돌을 확인한 별도8seed×22조건=176조건이다. 6규칙＋12학습＋3원11 terminal4096 평가군=21군·3696행을 동일환경에서 비교한다. 원4096은 평가 기준이며 신규학습계승이 아니다. 같은epoch·seed의 목적 대조와 DEV로 선정한 서로 다른epoch의 최종 정책 대조를 구분한다. 선정epoch가 다르면 순수 동일학습량 reward 효과라고 부르지 않는다.

모든 부하/낙관·부정 offset/납기factor/boundary를 보존한다. full176/사전primary160/사전release80을 모두 보고한다. 원 strict ε0·완료/units·서비스·P95/J/AP 조건별 비악화/비용이득을 유지하고, 별도release400ms SLO를 앱 채택 기준 완화로 쓰지 않는다. 평균 개선으로 나쁜 조건·seed를 삭제하지 않는다.

## 학습·선정·중단

새회차6시간 wall·episode/env 수치상한None·8GiB 저장·최종1800초 reserve를 둔다. 모델worker는1개로 고정해 각 공통stage의seed3을 순차·seed내4목적을 round-robin으로 진행한다. 현재12의 자원을 강제로 변경하지 않는다. 공유 PC 부하가 학습 wall/PC 판단시간에 영향을 주며 모형 서비스시간이나 기기 에너지로 환산하지 않는다.

최초512학습stage 이후1024/2048/4096 등의powers2로 확대한다. 모든12모델이 완료한 공통stage만 DEV선정에 사용한다. ep0는 초기동형 검사만 하며 학습모델선정으로 대체하지 않는다. 실제59개 수집 후 native update·pending·Adam·두RNG·원장을 정확복원하는 검사를 등록 후 예산에 포함한다. 순수 검사는 신규 환경/학습0으로 분리한다.

DEV 각조건 RuleATC와 같은seed 원4096 양쪽의 완료/units·원/선언U/N·P95 비악화를 만족한 실제학습checkpoint를 우선하고 meanJ→AP→P95→이른epoch로 선정한다. 적격이 없으면 위험key의 실패모델을 보고하며 guard 통과로 표시하지 않는다. 최종 전에12선정＋3원4096의SHA와코드/입력/설정/UTC를 동결하고 확인 뒤 재학습·재선정0이다.

cost3목적 모두에서 각≥2seed의 unique service/P95 손해조건수가2연속 공통stage전환 동안 증가하면 확대를 중단한다. 3추가stage에서 모든cost목적/seed의 besteligible/risk 개선이 없고 의미 비용이득도 없으면 정체로 중단한다. 의미 reward 이득은 같은seed CONTROL@동일공통stage 대비 meanJ≥0.005J 또는 meanAP≥0.005°C이며, cost arm이 RuleATC·원4096·CONTROL 모두에 각조건 완료/units·서비스/P95/J/AP 비악화를 만족할 때만 인정한다. 최초512 기준은 추가stage에 세지 않는다. 원4096 대비 적용 이득도 별도로 보고하고, CONTROL 자체의 fresh학습 이득을 reward 효과로 세지 않는다. 위험key가 개선되면 정체 조건이 성립하지 않는다. 확대용 문턱은 모형 정밀도·실기기 최소효과·strict ε0의 대체값이 아니다. 구현자/IE가 등록 전에 코드와 본 문서의 일치를 확인한다.

NaN/불법/소스·입력·복원 불일치는 실패와소비를 보존하고 확대중단한다. 환경 진입 전 시간/저장 중단은 ControlledStop으로 처리해 새환경 실패로 오계수하지 않는다. 동일 os.replace 재시도 helper만 SHA로 별도 결합하며 정책 개선으로 세지 않는다. 등록 후 policy/physics/input/seed/selection 변경은 하지 않는다.

## 산출·미확인

새 `d1_atc_energy_{ppo,targets,budget,study,orchestrator,report}.py`와 순수 test를 최초 source 등록에 포함한다. source tree·프로토콜·입력·재사용 binding·원PT와선정PT·원장·native/Adam/부분pending·모든seed/조건손해·공통stage/선정결과·PC mean/P95/max/큐 증가·저장비용·전체raw SHA/실제AVAILABLE/마스크를 감사한다. 실행루트 work/ATC-ENERGY-GUARD-13, 사용자 산출 outputs/ATC-ENERGY-GUARD-13이다.

CPU분류4표본과동결AP/J모형, 합성n1 Curgent/Dnormal, 유한자료반복의 한계는 그대로다. 많은학습/새seed가 신규실측표본을 뜻하지 않는다. 새보상이 서비스보호 아래 비용을 더 줄일 수 있다는 가설은 아직 결과가 아니다. IE/모바일 사전검토와 구현자의 RL 검사를 구분한다. 현재12의 완료보고/후속자동화는 그대로 유지하고13은 별도후속에서 코드검토·등록·실행·감사·보고까지 진행한다.
