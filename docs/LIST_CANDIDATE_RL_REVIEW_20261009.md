# 리스트 후보 + RL 설계: 세 관점 토론과 보완안

2026-10-09 · `LIST-CANDIDATE-RL-REVIEW-01` · **코드 확인·토론·설계 보완, 새 정책 구현/학습/환경/기기 실행0**

모바일 실행, 산업공학 스케줄링, 강화학습 관점의 AI 검토자를 하나씩 두어 독립 검토→서로 직접 질문/반박→중재자의 반론과 수정안 재검토를 진행했다. 모델을 자동 변경하지 않았다. 역할을 분리한 AI 검토이며 독립 인간 전문가의 검증이나 성능 입증은 아니다.

결론은 **과업별 리스트가 실제 후보를 만들고 native Maskable PPO가 선택하는 구조를 유지하되, 실행·보상·평가 계약을 먼저 보완한다**는 것이다. 새 알고리즘 추가보다 지금 설계의 시간·관측·서비스 정의를 닫는 것이 우선이다. [원v3](LIST_CANDIDATE_RL_DESIGN_20261009.md)는 그대로 보존하고 아래를 미구현 **v4 제안**으로 분리했다.

[토론 요약](results/list_candidate_rl_review_01/debate_record.json) · [v4 개정 계약](results/list_candidate_rl_review_01/design_amendment_v4.json) · [정적 검증 기록](results/list_candidate_rl_review_01/verification.json)

## 1. 각 관점에서 찾은 문제와 합의

| 관점 | 코드와 설계의 차이 | 합의한 최소 보완 |
|---|---|---|
| 모바일 | 기존 projection은 phase 사건에서 대기를 취소하지만 원안은 phase만 바뀌면0.25초 timer를 유지한다. 약1.3ms ASSIGNED 종료로 대기가 사라질 수 있다. | 새 hold/credit/pending 상태를 분리하고 phase-only는 관측만 갱신. 실제 대기시간을 한 번만 차감 |
| 모바일 | snapshot은0시간 OUTPUT_READY/PERSISTED를 건너뛰어 정확한 응답 시각을 잃는다. | 공개 과거 이벤트 observer와 유효성 필요. 불명확하면L0 복귀, 평균비용으로 응답 시각 생성 금지 |
| 산업공학 | 원 EDD+ECT는 점유 자원의 반환을 기다릴 수 있다. 새 L0는 현재 빈 자원과 backfill을 쓰므로 다른 정책이다. | 기존 EDD+ECT를 별도 기준군으로 보존. 새 L0의 범위·변경을 표시하고 후보 표현 가능성을 먼저 진단 |
| 산업공학 | L0 대비 상대 비악화만으로 기존 low/sustained의 절대 전기한 충족 조건을 대체할 수 없다. | 기존1.5/6초 engineering target과 primary의 `F=U=N=0`을 명시적으로 복원 |
| RL | signed 서비스 차이를 평균하면 한 조건의−1이 다른 조건의+1을 상쇄할 수 있다. | 서비스는 양의 악화 잔차로 학습하고 signed J는 유지. 조건별 원 KPI와 절대 조건은 별도 판정 |
| RL | 기존 코드의 과거grid 증분은 현재 행동에 붙고 mean observer에서 나온다. 총합이 맞아도 행동 이후 비용과 다르다. | 실현곡선은 학습 경로에서만 사용하고 행동 이후 구간에 배분. 마지막180초 꼬리까지 합 검증 |
| 세 관점 | proxy J/AP의 구간 길이가 없고, 원 리스트는 다른 후보/suffix를 써서 RL 기여의 단독 대조가 아니다. | 중복 특징2개를 구간 길이/유효성으로 교체. 같은 후보·관측·proxy의 비학습 대조를 개발 자료에 추가 |

근거 위치: `tools/d1_edd_ect_residual_controller.py:117,195,208`, `tools/d1_ie_dispatch.py:35`, `tools/d1_edd_ect_residual_ppo.py:101,120,134`, `tools/d1_arrival_explore.py:163,183,209`, `tools/d1_empirical_request_policy.py:50,80,100,110` 및 `docs/results/ie_candidates_v2/README.md:100`. 검토 소스의 정확한hash는 v4 계약에 고정했다.

## 2. 실행과 관측: 학습 이전의 필수 조건

공개 이벤트 hook은 **향후 PC opt-in 경로의 최소 수정 제안**이다. 현재 `observe(now, lanes)` snapshot만으로 zero-duration 응답을 복원하는 것은 불가능하다. 공개 arrival/actual dispatch와 phase journal의 `at_ns/request_id/backend/event`에 순번을 더해 받는다. 알려진 과거 `output_ready_ns`, `persist_complete_ns`, `worker_release_ns`, `lane_available_ns`만 전달한다. 미래 도착목록·실현 비용벡터·private 잔여시간·실현 열곡선은 actor에게 주지 않는다. 기존 정책에 hook을 적용하지 않았을 때 원장·시계·예산이 정확히 같아야 한다. 이번 엔진/앱 코드는 수정하지 않았다.

추가 대기 credit은 **실제 dispatch 이벤트로만** 갱신한다. 같은시각 콜백 반복이나 phase 전이로 충전하지 않는다. hold 중 phase-only는 잔여 timer를 유지하고, 새 도착·실제 소유 변경·timer에서 재판단한다. 양의 경과시간은 중복 차감하지 않는다. 실제 이벤트 순번이 바뀐 같은시각과 같은 snapshot의 반복 호출을 구분해야 한다.

PAIR는 한 actor 표본에서 나온 논리적 묶음이다. 둘째 commit 직전 요청·실제 lane 소유·CG_DC 지원을 재검사한다. 둘째가 실패하면 첫 실행은 유지하고 둘째 요청은 큐에 보존하며 사유를 기록한다. 같은 commit에서 재추첨하지 않고 다음 실제 공개 사건에서 재판단한다. 실제 AVAILABLE 이전에는 lane을 다시 쓰지 않는다. Android의 응답→저장→WORKER_RELEASED→이벤트 기록/dispatch callback→AVAILABLE을 합치지 않는다. 물리적으로 정확히 동시 시작한다는 보장은 없다.

## 3. 후보 특징은 크기를 유지하고 의미를 보완

2FIFO head·8슬롯·0.125/0.25초·최대2건·기존 CPU/GPU/CG_DC를 유지한다. `C_head.included_now`와 `D_head.included_now`는 현재 미예약2head 구조에서 `dispatches_classification/detection`와 같다. 이를 `proxy_span_duration_over_6s`와 `proxy_span_duration_known`으로 교체한다. **56/28특징·16,455파라미터는 유지하되 새schema/hash로 구분**하고 과거 weights/Adam을 로드하지 않는다.

proxy는 현재 owned 작업과 이번 atom만 다룬다. 즉시 실행은 이 작업들의 예상 마지막 lane_available까지, 혼합 지연은 그 끝과 hold timer 중 늦은 시각까지, 순수 지연은 선언한 timer까지만 적분한다. 순수 지연 끝에 owned 작업은 미완료일 수 있다. 미배정 큐 후속 순서를 짜거나 완료한 것처럼 계산하지 않는다. 구간을 계산할 수 없으면 raw 비용/시간은null, tensor0에는 known=false를 붙인다.

구간 길이를 알려줘도 서로 다른 처리량/기간의 proxy가 전체episode J/AP 순위를 뜻하지 않는다. 전체0…120초 J와35…180초1초grid AP, 전체 예정 요청 KPI를 최종 판정에 사용한다. 온라인 rolling/Band suffix는 추가하지 않는다.

## 4. 보상·제약과 학습 집계

동일trace의 L0를0, 정책을π로 표기한다. `A`는 모형AP최고, `J`는 공통창 전체J, `F`는 예정−완료, `U/N`은 긴급/일반 실패, `P`는 긴급P95다.

```text
R = (A0 - Aπ) / 1°C
c_J = (Jπ - J0) / 1J
c_service = [(Fπ-F0)+, (Uπ-U0)+, (Nπ-N0)+, (Pπ-P0)+/1500ms]
x+ = max(0, x)
objective = E[R - lambda_J*c_J - sum(lambda_service*c_service)]
```

서비스의 조건 간 개선/악화 상쇄를 막는 학습 신호다. 이것이 조건별 보장이나 CPO 구현은 아니다. 양의 서비스 비용에 따른 λ의 단조 증가·cap/선택 동결 위험은 λ·선택분포·최악 위반으로 감시한다. 원단위 signed 차이도 보고한다. AP 주목적은 CMDP 설계 의도이며 유한 Lagrangian 학습의 사전식 우선순위 보장은 아니다. 단위척도를 새 SLA/온도 한계로 쓰지 않는다.

실현AP곡선은 episode 완료 후 학습용 경로에서만 읽는다. actor는 계속 공개 이력과 동결 평균모형만 쓴다. 실제 선택시각 `t_i`까지의 과거 in-window 최고를 `M_i`로 두면 다음처럼 행동 이후 구간에 배분한다.

```text
r_i = -(M_(i+1) - M_i) / 1°C
r_last = [-(Aπ - M_last) + (A0 - M_first)] / 1°C
sum(r) = (A0 - Aπ) / 1°C
```

첫grid/선택 전 초기 potential·empty-grid 유효성과 마지막 선택 뒤180초 꼬리를 명시해 검사한다. 기존 current-step에 이전 증분을 붙이는 코드를 그대로 이식하지 않는다. AP/J가 무효인 정상 종료episode는 해당 **전체 trajectory 채널**을 차단하고 알려진 실패비용만 유지한다. 인프라 예외로 원장/완료량이 불명확한 시도는 학습 업데이트 없이 실패·소비 기록을 보존하며 완료량을0으로 지어내지 않는다.

actor는 `(1/B) Σepisode Σ실제 선택 clipped surrogate`로 집계하고 episode별 선택 수T로 다시 나누지 않는다. 강제 단일선택·중복 callback·PAIR 둘째 commit은 actor/entropy에서 제외한다. entropy는 episode별 실제선택 평균, critic는 episode별 고유 유효상태/유효채널 평균으로 분리한다. λ를 합친 원단위 advantage를 만든 뒤 공유 정규화하고, 채널을 개별 표준화해 λ 의미를 바꾸지 않는다. 각 분모·minibatch 가중과 preclip gradient를 검증한다.

zero actor 마지막층은 결함이라는 1차 지적을 **반론 후 철회**했다. 균등 초기화는 유지하고 이후 gradient·coverage를 기록한다. 실패192건처럼 critic MSE가 큰 사례에서 actor가 global clip에 묻히는지도 본다. 근거 없는 critic 정규화/Huber 전환은 자동 추가하지 않는다. 3seed×64episode는 작은 개발 탐색이며 수렴 판정이 아니다.

## 5. 비교와 예산: 개선을 전제하지 않는다

기존 EDD+ECT는 점유 CPU의 예상 반환+서비스가 GPU즉시보다 빠르면 기다린다. 새 L0는 빈 자원 선택/backfill이다. 예를 들어 분류CPU 약0.165초, GPU 약0.305초의 동결 평균과 가상 CPU 잔여0.05초에서는 CPU대기 ECT약0.215초와 GPU즉시약0.305초가 다르다. **실제 실행 결과가 아닌 차이 설명용 가상 상태**다. 두 정책을 합치거나 기존 EDD를 FIFO로 대체하지 않는다.

같은bank/state/proxy의 `LIST_SAME_BANK_GREEDY_V4_PROPOSAL`을 개발24조건에서만 비교하는 안을 추가한다. 순위는 현재 head의 예측 서비스 위험→단원AP→단원J→L0 동률→고정 signature다. 정확한 서비스 위험 식과 unknown→L0는 **구현 gate에서 실행 전에 고정할 미완료 항목**이다. AP/J부터 순위를 매겨 짧은 대기만 선호하는 약한 대조를 만들지 않는다. 이 예측 순위로 RL 물리 마스크를 좁히지는 않는다.

이 대조만 이겼다고 채택하지 않는다. L0·원List·EDD+ECT·Band·Triton을 보존한다. 기존 low/sustained의 절대 `F=U=N=0`과 모든조건 상대비악화를 함께 요구하며, 원v3의 엄격 열감소 gate도 이번에 완화하지 않는다. 같은bank 대조의 RL 기여 판정은 **개발 자료 범위**에 한정한다. 그 대조의 확인48 추가는 이번에 자동 계상/실행하지 않는다.

기존 first512환경은 유지하고 그 뒤 별도 개발대조24를 제안한다. 조건부 예상총량1448→1472, 전체cap1536/학습416은 그대로다. 현재누적6,517환경/641학습을 계승하며 이번 신규 소비는0이다. 개발2개/확인4개 도착trace, 서비스3문맥, 학습3seed를 서로 같은 독립 반복으로 세지 않는다.

## 6. 합의하지 못한 것과 다음 구현 gate

0.25초 밖 CPU 반환 대기가 필요한지, 56특징이 공개 후속 기한 밀도를 충분히 구분하는지는 아직 답할 증거가 없다. 기존 성공3원장에는 판단 의도가 없다. 긴 resource wait가 구현 가능하더라도 GPU 즉시 실행 대안이 있으면 자발적 선택이며 무료 credit 우회가 아니다. 표현성/배제율과 동일 관측 반례를 먼저 보고 필요할 때 별도 개정한다. GNN/RecurrentPPO/DQN/CP-SAT 등을 일괄 추가하지 않는다.

구현 gate는 공개 이벤트의 zero-phase/dispatch 보존, hold 차감·실제 AVAILABLE·PAIR 실패 시 요청 보존, 같은 공개 이력/다른 private 문맥의 actor tensor 동일성, 후보 중복·일정 표현성, AP 보상 시점/180초 합, 학습 분모·gradient·checkpoint 재개 동일성 및 기존 엔진 원장/clock/예산 보존이다. **gate 전에는 학습하지 않는다.**

동결 모형은 새 열 slowdown이나 추가 간섭을 지원하지 않는다. g=0은 열 관성 자체가 없다는 뜻은 아니지만 h를 부하별 독립 잔열 특징으로 쓰지 않는다. 표면온도·휴대폰 제어J·실제 스로틀링 회피 효과는 미지원이다. lane 소유 병행과 inference 실행 병행, host 판단시간과 phone 제어J를 구분한다. 다른 프로토콜의 AP/J 오차를 새 허용 margin으로 전용하지 않는다. 별도 Run05 실측·미완성자료·계수/경로/프로세스·사용자 변경은 이번에 건드리지 않았다.

외부 근거는 [PPO 원논문](https://arxiv.org/abs/1707.06347v2), [invalid action masking](https://arxiv.org/abs/2006.14171v3), [CPO](https://proceedings.mlr.press/v70/achiam17a.html), 원설계의 [job-shop 휴리스틱 선택 연구](https://arxiv.org/html/2601.11189v1)다. 원논문의 성능·공장 자원·CPO 보장을 D1Check에 전용하지 않는다.
