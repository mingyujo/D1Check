# ATC-COST-GUARD-13: 응답·납기 보호와 에너지·AP 보상 대조

상태: 구현·등록 준비. 2026-10-12 사용자 승인으로 현재12 장기학습을 그대로 진행하며 별도 보상 실험을 추가한다. 등록 전13의 신규 환경/학습/기기 실행은0이다. 실제 실행 수치는13의 별도 원장에 기록한다. 12의 source92·등록·입력·가중치·PID·목표·deadline과 과거 결과는 변경하지 않는다.

## 고정 구조와 변경 요인

전체 현재 미시작 큐의 ATC top4＋coverage 최대8요청 → 지원된 단일/CG_DC 병행/필요 자원 대기 → 물리 마스크 → DROP_FLAG_WAIT1 직접 PPO → 실제 사건마다 미시작 요청 재판단을 유지한다. 상태226/행동57/패딩32/최대29행동, 원teacher표식52의NN비노출, ATC rank/gap·WAIT1 prior·모든정규화는 동일하다. 시간표 전체의 미래 최적화나 미래 큐 rollout은 추가하지 않는다.

비교는3보상×3새 초기 seed의9모델이다. 연결·물리·입력·PPO 손실/학습률/entropy/clip/8episode 업데이트는 고정하고 아래 비용 강조와 보너스 처리만 바꾼다.

| 군 | E/AP 비용 가중치 | 서비스6비용 / P95 비용 | 추가 변경 |
|---|---|---|---|
| CONTROL | 1 / 1 | 각100 / 20 | 현 URGENT_HOLD 목표와 동일 |
| COST5 | 5 / 5 | 각100 / 20 | 에너지·AP 비용 강조만5배 |
| GATED_COST5 | 5 / 5 | 각100 / 20 | 서비스 적격 실패 에피소드의 음수 비용 보너스 제거 |

가중치5는 개발용 정책 설계값이며 실제 지연·에너지·온도의 환산 비용으로 주장하지 않는다. CONTROL 대 COST5는 강조 효과, COST5 대 GATED_COST5는 보너스 gate의 효과를 비교한다. 같은 episode 수의 DEV 대조를 남긴다. 최종 선정 episode가 달라지면 최종 비교는 보상＋개발 선정 절차의 효과이며 순수 보상 변화 하나의 효과로 과장하지 않는다.

## 보상과 gate의 정확한 정의

현재 reward return은 ATC 사후 대조 보상 차이에서 절대 긴급 미응답 면적을 뺀 URGENT_HOLD다. 에너지 비용은 동일 case의 ATC 대비120초까지 남은 모형 에너지 차이를10J로 나눈 signed return이다. AP는35~120초의 final peak−현재까지 running peak의 성장 차이를0.1°C로 나눈 signed return이다. 서비스6채널은 긴급/일반의 선언·원기한 실패율, 미완료 unit/요청 비율이고, 마지막 채널은 paired P95 초과를100ms로 정규화한 기존 비용이다. 학습 AP proxy의35~120초와 최종 평가 AP peak의35~180초를 구분한다. 모든 실측/모형 원 지표는 그대로 기록한다.

GATED_COST5의 에피소드 보너스 적격은 **전 요청/units 완료 AND 선언/원기한 긴급·일반 실패 모두0 AND 긴급 P95≤동일case RuleATC**다. 필요한 값이 없거나 nonfinite이면 적격으로0임퓨트하지 않고 invalid를 기록·보존하며 해당 학습을 성공으로 처리하지 않는다. 비교 원장의 case/arrival_seed/실현키/모형/초기조건도 일치해야 한다.

PASS에서는 CONTROL/COST5의 원 signed suffix target을 그대로 유지한다. FAIL에서는 판단 frame의 수에 의존하지 않는 공통 시간 구간으로 양의 비용만 구성한다. 에너지는 학생·교사 physical segment 경계의 합집합에서 양의 paired power-rate 차이를 적분한다.

$$C'_E(t)=\frac1{10\mathrm J}\int_t^{120\mathrm s}\max(0,P_\pi(u)-P_{ATC}(u))\,du.$$

두 궤적의 동일 상주전력은 차이에서 소거된다. segment/state/120초 coverage·finite를 검사하고 고정 모델의 power를 사용한다. AP는 기존35~120초 고정1초 grid $\tau_k$와 running peak $M(\tau_k)$를 사용한다.

$$D_k=\frac{M_\pi(\tau_k)-M_{ATC}(\tau_k)}{0.1{}^\circ\mathrm C},\quad d_k=D_k-D_{k-1},\qquad C'_{AP}(t)=\sum_{\tau_k>t}\max(0,d_k).$$

35초의 initial peak 차이는0이며 grid 시각·초기조건·finite·coverage를 검증한다. 이미 관측한 grid-end emission은 후속 decision의 suffix에 다시 넣지 않는다. 현재 decision 시각을 추가·삭제해도 같은 물리 궤적의 전체 gated 비용은 같아야 한다. 예를 들어 canonical 구간 비용[-2,+1]의 net은-1이지만 FAIL에서는 양수+1만 유지한다. 서로 다른 부호 구간을 판단 frame 하나로 합쳐 max0하는 안은 사용하지 않는다. reward/서비스/P95 target은 변경하지 않고 episode E/AP 벡터를 새 첫 suffix와 결합한다.

AP increment는 running peak 차이의 potential 증분이며 가산 물리 열량이나 실제 순간 온도 비용이 아니다. gate FAIL에서 음수 proxy 증분을 제거한 대리 비용과 실제 AP peak/J 평가를 구분한다. gate는 에피소드가 끝난 뒤 label을 만드는 방법이며 후보·상태·마스크·NN 입력에는 넣지 않는다. 비용 절감 보너스 제한은 실제 운영의 서비스 보장을 뜻하지 않는다. 판단 frame별 clip안과 학습 AP180초 확장안은 등록·환경0에서 폐기했다.

고부하에서 ATC도 납기 실패를 내더라도 GATED 보너스는 절대 실패0 조건을 만족해야 한다. 그런 에피소드를 제거하지 않고 gate-off 비율과 실제 서비스 실패를 보고한다. 원 strict의 상대 비악화 계약은 이 보너스 gate와 별도로 보존한다.

## 새 가중치·자료·대조

보상/critic target의 의미가 바뀌므로9모델은 fresh 초기화한다. 새 seed1103/1109/1117마다 세 보상군의 초기 network/Adam 설정과 action/shuffle RNG를 같게 하며 실제 forward/초기 state hash를 확인한다. 기존 모델의 learned weight·Adam·critic을 새 목표에 그대로 재사용하거나 기존 loader의 objective 검사를 우회하지 않는다. actor/encoder/물리 마스크 구현은 동결11 코드로 재사용한다. reward_arm/objective ID/고정 multipliers는13의 별도 learner에 결합한다.

12에서 이미 완료한 TRAIN2816/DEV176과 ATC teacher2816＋규칙DEV1056＋학습전4096 DEV528의 총4400개 참조 환경을 SHA로 결합해 복사한다. 13 신규 환경으로 중복 계수하지 않는다. 원본은 읽기 전용이고 source/초기모형/마스크/arrival_seed/실현키/요청 signature를 확인한다. idle/steady 시각이 같다는 이유만으로 다른 hidden draw의 교사를 쓰지 않는다. 12의 최종 결과·궤적·선정은 사용하지 않는다.

11family×2납기factor의 모든 계열을 유지한다. 새13 FINAL8seed×22=176조건은 별도923810xxx namespace를 충돌 확인 후 등록한다. source/입력/보상/gate/선정 계약을 처음부터 고정한다. 최종은6규칙＋9학습 모델＋3고정 origin4096의18군=3168행이며 모든 가중치를 최종 전에 동결한다. origin1013/1019/1021은 새 seed1103/1109/1117과 순서대로 사전 대응한다. 이 대응은 선택 기준과 참고 성능이며 같은 초기 가중치 비교라고 부르지 않는다.

CONTROL/COST5/GATED의 같은 fresh seed·같은 case paired 차이와 RuleATC/origin 차이를 full176/primary160/release80별로 분리한다. 기존12와13은 다른 최종 실현이므로 condition ID끼리 직접 차감하지 않는다. 신규 episode/native/Adam 업데이트와 원본·복사 참조를 별도 계수한다.

## 실행 예산·보호·선정

현재12의3학습 worker를 그대로 유지한다. 13은 초기부터 training concurrency1로 등록해 seed/보상군을 순환 실행한다. CPU6코어/12스레드, RAM약16GiB에서 기존 작업의 CPU/RAM/디스크 여유를 보호하며 공유 호스트의 간섭을 기록한다. 현재12를 중단하거나 priority/affinity/deadline을 바꾸지 않는다.

새 등록부터 약6시간 wall, 최종1800초 reserve, 원자료/checkpoint 보존용8GiB를 적용한다. 숫자episode/environment 상한은 없다. fresh512→1024→2048→4096 이후 powers2로 확대한다. 원 모델0회 checkpoint를 새학습 성공으로 선정하지 않는다. 순수 계약 검사와 실제59episode 부분 저장/optimizer/RNG exact 복원을 구분하며 실제 proof 환경/학습은 원장에 계수한다.

같은 common stage를 모든9모델이 완료한 경우에만 DEV 평가·선정한다. 각 조건의 RuleATC와 사전 대응 origin4096에 대한 완료/units·선언/원U/N·긴급P95 비악화를 우선 guard로 두고 적격 모델 중 mean J→AP→P95→이른checkpoint로 선정한다. 적격이 없으면 위험 key로 실제 학습한 실패 후보를 보고하며 PASS로 표시하지 않는다. 비용 조건 손해는 평균으로 상쇄하지 않는다. 원 strict4참조 epsilon0·anchor 서비스·비용 이득 계약을 유지하며 별도 release400ms SLO도 동일 적용한다.

모든seed·보상군의 matched-stage mean/조건 손해수/최악 손해와 gate on/off·비정상지표·native actor/critic/RNG/부분 batch·저장 비용을 남긴다. 기술 오류·불법 실행·source/RNG 불일치는 실패를 보존해 중단한다. 사전 DEV 악화/정체 함수와 다음 stage 예상시간·메모리/디스크 여유를 등록 전에 코드로 고정한다. 자원 reserve는 새 환경 시작 전에 ControlledStop하며 accepted state를 저장한다. 모델을 최종 자료에서 다시 고르거나 확인 뒤 추가 학습하지 않는다.

## 운영·보고 경계

EFT0. Greedy/RR/FIFO/EDD/ATC는 독립 비교군이다. 실제 AVAILABLE 점유·긴급 OUTPUT_READY/일반 PERSISTED 응답 분리·비선점·지원 C_CPU/C_GPU/D_CPU/CG_DC 최대2건·필요 자원 WAIT·사건별 재판단을 유지한다. 마스크에 납기/보상 gate나 냉각 대기를 넣지 않는다. NPU/S26/새실측/물리fit/APK/기기/외부 전송은0이다.

source/입력/protocol/objective/weights/freezeUTC와 실제3168행·모든raw SHA/owner/응답/AVAILABLE/전체최종mask·원strict·gate 대리 비용 대 실제 지표·PC 판단/저장 mean/P95/max·큐 증가를 검산한다. 원4k와現12·이전08~11 등록/가중치/FAIL/다른WIP를 보존한다. source에는 새test도 최초부터 포함한다. IO는 동일 os.replace 재시도 helper를 별도SHA로 결합하며 정책 변경으로 세지 않는다.

이번에도 A24 C_CPU4/C_GPU188/D_CPU192 donor와 동결 AP·에너지 모형이다. 많은 학습은 CPU 분류4표본을 새실측으로 늘리지 않는다. 현재 n1 Curgent/Dnormal 합성 조건과 PC 판단시간을 모바일 전체 정책·실기기 에너지/발열 효능으로 일반화하지 않는다. gate/가중치5가 더 큰 절감과 서비스 유지로 이어지는지는 이번 새 확인에서 판단한다.

## 사실·가정·미확인

- 사실: 현재12는 별도 PID/source/deadline으로 실행 중이며 변경하지 않는다. 원11 정책/PPO/targets/엔진과12의 완료된 참조가 재사용 근거다.
- 설계 가정: 비용 강조와 실패 에피소드의 절감 보너스 억제가, 응답 보호를 유지하면서 더 나은 배정을 학습하도록 도울 수 있다. 아직 결과가 아니다.
- 미확인: 더 큰 실제 비용 개선·모든 조건 비악화·장기 안정성·실기기 판단비용이다. IE는 gate/단위/비가산성과 비교 계약을 검토하며 RL 구현자의 검사는 native 저장/목표 검증 범위로 구분한다. 새 독립 모바일 전문가 감사 완료로 표시하지 않는다.
