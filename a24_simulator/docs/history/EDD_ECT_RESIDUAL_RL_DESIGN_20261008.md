# EDD+ECT 기반 열 에너지 보정 강화학습 설계

2026-10-08 · `EDD-ECT-RESIDUAL-DESIGN-01` · 설계 수정 완료, 새 controller·학습 미구현

**EDD로 처리할 요청을 고르고 ECT로 자원을 고르는 기존 규칙을 기본 판단으로 삼는다. RL은 같은 기한·작업량 안에서 요청 순서, CPU/GPU 배정, 허용 병행, 짧은 대기를 보정한다.** EDD+ECT 대비 개선과 SHARED_EFT·Band·Triton의 제한적 재현 대비 경쟁력을 각각 평가한다. 산업공학 규칙을 사용한다는 사실만으로 기여나 성능 우위를 주장하지 않는다.

이 문서와 [기계 계약](results/edd_ect_residual_design_01/design_contract.json)이 후속 구현의 현행 설계다. [이전 SHARED_EFT 보정 설계](SLACK_RESIDUAL_RL_REDESIGN_20261008.md)와 봉인된 분석·검증은 당시 이력으로 보존한다. 이전 안과 이 안을 모두 학습하는 계획이 아니다. 이번 요청의 범위는 설계 수정이며, 아래 신경망·실행 배분은 구현 전 등록할 제안이다. 새 성능 실험·학습·기기 실행은 0회다.

## 근거와 문제 정의

[산업공학 규칙 비교](results/ie_dispatch_01/README.md)는 이미 본 합성 192조건에서 EDD+ECT를 실행했다. 주96조건에서 전량·기한·긴급P95는 유지했지만, SHARED_EFT 대비 AP 최고값 −0.065317°C / 에너지 +0.080970J, Band 대비 −0.053022°C / +0.169820J였다. 전체192 일반 기한 실패는 EDD+ECT 292, SHARED_EFT 204, Band 193건이다. 따라서 **낮은 모형 AP를 유지하면서 에너지 증가와 과부하 서비스 손실을 줄일 수 있는가**가 검증할 질문이다. 개선 가능성이 이미 입증된 것은 아니다.

SPT+ECT와 EDD+ECT의 실제 일정은 기존192조건 모두 같았다. EDD의 기한 우선 의미를 연구의 출발점으로 선택하며, 그 자료에서 SPT보다 좋았다고 쓰지 않는다. EDD와 SPT가 다른 순서를 만드는 수작업 사례는 기능 검증으로 별도 요구한다.

산업공학적으로는 도착시각·납기·자원 적합성이 있는 이종 병렬자원 배정 문제에, 공유 점유의 에너지·열 이력을 추가한 제한 모형이다. CPU/GPU를 독립 기계로 가정하지 않는다. 다공정 공장·AGV·job-shop 전체를 구현한 연구가 아니다.

## 이전 설계에서 유지하거나 수정한 것

| 항목 | 현행 설계 |
|---|---|
| 기본 제안·fallback·예측 후속정책 | 정확한 `IE_EDD_ECT_LANE_PC_V1`로 일치 |
| SHARED_EFT의 강제 aging·긴급 우선·8후보 구성 | 상속하지 않음. EDD 정렬의 앞8개가 후보 |
| ECT 선택 | 예상 응답이 아닌 5단계 전체 lane 반환시각 최소 |
| 기본 자원 대기 | ECT 원래 동작으로 보존. 다른 즉시 실행이 있으면 RL의 비교 대상 |
| 추가 냉각 대기 | 별도 행동·별도 누적 한도. ECT 자원 대기와 구분 |
| 실제 기한·전량·P95·J 비악화 | 유지. EDD+ECT만 이기면 성공으로 처리하지 않음 |
| 최초 EFT 완료 cap·signed J veto | 새 정책에는 사용하지 않음. 옛 정책과 판정은 보존 |
| 학습 참조 | EDD+ECT·SHARED_EFT·Band 세 독립 종료 실행 |
| 상태와 후보 특징 | EDD 순위·ECT 자원 차이·냉각 대기 잔량을 표현하는 새 schema |
| 온도·에너지 | 동결 모형, MODEL_AP. 관측 보정 후보를 자동 채택하지 않음 |
| 실행 상태 보존 | 최종 actor·critic·Adam·RNG·승수·미완료 batch·참조 cache 보존 |

## 기본 규칙과 RL의 역할

기본 구현은 [d1_ie_dispatch.py](../tools/d1_ie_dispatch.py)의 `Controller(..., policy='IE_EDD_ECT_LANE_PC_V1')`다. 출처와 제한적 재현 B의 범위는 [대응표](results/ie_dispatch_01/mapping.md)를 따른다. 기존 adapter를 수정하지 않는다.

도착한 대기 요청 Q에서 `Dq = arrival_ns + deadline_offset_ns`로 놓는다.

```text
q0 = argmin_q (Dq, arrival_ns, ordinal, id)
b0 = argmin_b (predicted_lane_end(q0,b), b != CPU)
predicted_lane_end = earliest_supported_start + sum(mean five-phase durations)
```

`earliest_supported_start`는 기존 `place()`의 점유·호환성 검사로 구한다. 단순히 두 독립 기계의 가용시각만 비교하는 식으로 대체하지 않는다. 동점은 CPU, 요청 동점은 도착/ordinal/ID다. 선두 q0의 최선 자원이 아직 바쁘면 예상 시작까지 기다리되, 먼저 도착한 공개 사건에서 다시 판단한다. 과거의 장래 배정 예약은 유지하지 않는다. 비용 갱신·강제 aging·기한 초과 삭제·자발 냉각은 기본 규칙에 없다.

긴급 응답 경계는 OUTPUT_READY(앞2단계), 일반은 PERSISTED(앞3단계), lane 재사용은 전체5단계 종료다. **ECT가 최소화하는 완료와 KPI가 검사하는 응답을 구분한다.** 실제 WORKER_RELEASED만으로 lane을 비웠다고 처리하지 않는다.

기본 규칙은 전체 도착 큐를 사용한다. RL 후보는 EDD 정렬 앞8개로 제한하지만, 기한 예측에는 후보 밖을 포함한 현재 Q 전체와 실행 중 요청을 넣는다. 우선순위는 기한과 상태 특징에 반영하되 별도의 긴급 가중치나 SHARED_EFT aging을 기본에 끼워 넣지 않는다.

새 정책 ID는 `EDD_ECT_SLACK_RESIDUAL_PPO_V1`이다. 학습 없는 대조는 `EDD_ECT_FEASIBILITY_PRIOR_V1`, `EDD_ECT_THERMAL_GREEDY_V1`이다. 셋 다 새 설계 ID이며 현재 실행 가능한 CLI가 아니다. 원 EDD+ECT를 그대로 실행한 비교 정책과 새 필터가 붙은 prior를 별개로 공개한다.

## 행동과 대기

| 행동 | 허용 조건과 의미 |
|---|---|
| BASE | 현재 공개 상태에서 원 EDD+ECT가 제안하는 배정 또는 자원 대기 |
| SINGLE(q,b) | 앞8개 중 도착한 q와 현재 실제로 빈 지원 b. EDD 순서·ECT 자원을 변경할 수 있음 |
| BUNDLE(qc,qd) | 서로 다른 분류GPU+탐지CPU, 두 lane 실제 가용. 같은 시각의 두 단건 배정 |
| COOL_WAIT | 즉시 지원 배정이 존재하고 기한 필터가 통과할 때만 추가 대기 |
| 필수 사건 대기 | 비용 overrun/공개 정보 부족 또는 실행 가능한 행동 부재. 강제 BASE이며 학습 선택 아님 |

**ECT가 CPU를 기다리더라도 GPU 즉시 실행이 가능하면 무조건 강제 대기로 처리하지 않는다.** 그 BASE 자원 대기와 즉시 대안을 같은 mask에서 비교한다. 반면 잔여 비용을 알 수 없는 overrun은 임의 잔여0이나 실제 미래 비용을 넣지 않고 원 BASE로 복귀한다.

냉각 대기 한도는 새 보정 정책의 설정이다. EDD/ECT의 원 임계값으로 표시하지 않는다. `cool_credit=0.25초`로 시작하고 실제 DISPATCH가 일어날 때만 재충전한다. COOL_WAIT 지속시간은 `min(credit, 가장 이른 현재 기한-now, 120-now)`이며 1ns보다 커야 한다. 중간 공개 사건에서 깨어나면 실제 경과한 냉각 대기시간만 차감한다. 요청 도착·phase 변경·반복 callback은 credit을 초기화하지 않는다. 대기 도중 실제 lane 해제/도착을 정상 관측하고 매 사건에서 재판단한다.

BASE의 원 자원 대기에는 이 추가 냉각 한도를 적용하지 않는다. 이로써 원 규칙의 정확한 복귀와 추가 냉각 제한을 구분한다. 자원 대기·냉각 대기·필수 사건 대기의 실제 경과시간을 별도 기록한다. 유한 입력의 완료 및 일반 기한 검사가 기아를 검출하며, 미래의 무한 도착에 대한 무기아 보장은 주장하지 않는다.

8후보 중 분류 c개이면 single은 8+c, bundle은 c(8−c)개다. BASE와 COOL_WAIT를 더해 최대30개, 32slot padding이다. 같은 행동에 BASE 태그만 붙은 중복은 합치고 prior 질량을 한 번만 준다. BASE 대기와 COOL_WAIT도 같은 timer·재판단 효과이면 합친다.

묶음은 EDD key가 이른 요청을 먼저, 다음 같은 시각 callback에서 둘째를 배정한다. 첫 요청의 실제 점유·now 불변·둘째 큐 존재·실제 빈 lane·지원 조합을 재검사한다. 실패하면 pending을 취소하고 새로 판단한다. 둘째 실행은 같은 행동의 확정이므로 별도 actor 표본/로그확률/RNG 소비가 아니다. 예측은 동일한 순서·재검사를 따라야 한다.

반환한 이름이나 timer의 차이를 선택 폭으로 세지 않는다. 최초 양의 시간진행 전 실제 dispatch 집합과 다음 공개 사건의 점유가 달라야 별도 물리 선택으로 센다. 공개 상태 변화 없는 같은시각 재호출은 재추첨하지 않는다.

## 도착한 작업의 예측 검사

후보 a 뒤에 **원 EDD+ECT**를 적용하는 순수 event 예측을 mean/short_context/long_context에서 계산한다. BASE와 후보의 ΔJ/ΔAP도 동일 EDD 후속계획끼리 비교한다. 기존 `p.rollout()`은 응답 최소 자원을 택하므로 EDD+ECT suffix로 그대로 재사용할 수 없다. 기존 `p.score()`의 전이경계 포함 최고값도 AP KPI와 달라 그대로 reward로 쓰지 않는다.

예측 plant에서 앞으로 시작하는 작업만 κ의 5단계 비용을 사용하고, BASE의 판단용 추정값은 항상 원 mean이다. 이미 실행한 과거는 고정한다. 실행 중 작업은 mean/short 경로에 mean 잔여, long 경로에 long 잔여를 사용하며 필요한 잔여가 unknown이면 강제 BASE다. 예측 상태를 복제하고 실제 provider의 관측·heap·RNG를 소모하지 않는다. 실제 엔진 simulate를 후보 예측에 호출하지 않는다.

필터는 모든 κ에 대해 다음을 요구한다.

1. 현재 실제 lane·지원 조합·요청 ID·냉각 credit 조건 충족.
2. 현재 Q 전체와 미응답 실행 요청이 원 응답 기한 이내. 이미 공개된 응답은 미래 실패로 다시 세지 않음.
3. 현재 작업들의 lane 반환이 120초 이내이며 필요한 비용이 모두 유한·지원됨.

BASE가 예측 기한을 실패하고 대안이 통과하면 BASE를 선택 mask에서 제외한다. 모두 실패하면 원 BASE 한 개로 복귀하고 `infeasible_fallback`을 기록한다. 이를 기한 보장/적격 행동이라고 부르지 않는다. BASE의 서비스 실패와 BASE 비용 예측 불가를 구분하며, 후자는 비교 비용을 만들 수 없어 보정을 중단한다.

이것은 현재까지 도착한 Q의 조건부 검사다. 미래 요청·미래 실현비용·전체 P95·전체 J를 보장하지 않는다. 기존보다 먼저 응답해야 한다는 요청별 cap이나 후보별 J 비증가를 core mask에 추가하지 않는다.

## 상태와 PPO

새 관측은 **109개**, 후보별 특징은 **68개**, 출력은32slot이다. 필드명·순서는 [계약](results/edd_ect_residual_design_01/design_contract.json)에 고정한다. 동일 차원의 옛 actor도 의미가 다르면 재사용할 수 없다.

- 이전107 상태의 요청별 `forced_aging`을 `is_edd_head`로 교체하고 냉각 credit과 AP 격자 표본 유무를 추가한다. lane·큐 요약·이미 공개된 응답 통계를 유지한다.
- 후보 종류는 single/bundle/cooling/ECT 자원 대기/필수 사건 대기와 BASE 태그로 구분한다. 각 요청에 전체 Q의 EDD rank, 원 ECT 선호 backend 여부, 단건 mean lane 완료의 ECT 대비 증가량을 추가한다. bundle 총효과는 별도 전체 예측 특징으로 표현한다.
- AP는 동결 계수와 지금까지의 공개 점유에서 계산한 MODEL_AP다. 실제 미래 실행 일정·실현 context·seed/family·미래 참조 최종값·NN 입력의 요청 ID는 금지한다. 없는 slot·미관측 통계의 padding은 valid bit와 함께 사용하며 미지원 물리 비용을0으로 채우지 않는다.

state109→64→64, candidate68→64→64 Tanh, 결합128→64→1 actor와 heat+5cost의6head critic을 제안한다. 초기 residual 마지막층은0, m개 적격 행동에서 BASE prior logit은 `log(9*(m−1))`로 초기 BASE 확률0.9다. BASE가 없으면 적격 행동 균등, 강제1개면 actor/entropy gradient와 RNG 소비0이다. 미래 순서를 직접 보는 teacher나 기존 P95가 악화된 offline 이득 일정은 사용하지 않는다.

Adam0.0003/eps1e−5, 8episode/update, 4epoch, minibatch256, clip0.2, entropy0.01, value0.5, gradient0.5, targetKL0.03, γ1·비할인 Monte Carlo는 이전 제안을 유지한다. 값 탐색이나 보상 튜닝을 추가한 실행 승인은 아니다.

## 목적과 세 참조의 제약

최고 모형 AP를 줄이되 전체 완료·기한·긴급P95·J를 지킨다. AP는 표면온도가 아니며 이 설계의 구현 가능한 열 KPI만 뜻한다. 일반 완료시간은 별도 보고하고 기한을 지켰다는 이유로 평균 지연 증가를 감추지 않는다.

공통 J는0..120초, AP는35..180초1초 격자다. 모델 점유시간에 따른 `J=P_idle*120+Σ_s W_inc(s)*duration(s)`를 유지한다. 같은 상태 점유시간을 단순히 뒤로 미룬 것만으로 J가 줄었다고 계산하지 않는다. grid와 전이경계 보조 최고값을 구분하고 grid 정렬에 민감한 이득을 표시한다.

AP 보상은 누적 grid 최고값의 증가에 음수를 주고, 마지막 정책 결정 이후180초까지의 증가도 terminal에 포함한다. 첫 grid 전에는 최고값이 없으므로 임의 관측을 만들지 않는다. 공개된 초기 모형 AP를 **보상 회계 anchor** A로 사용하고, 첫 표본에서 `−(M_first−A)`, 이후 `−(M_next−M_prev)`를 준다. terminal에 완료된 EDD 참조의 `M_EDD−A`를 더하면 합은 정확히 `M_EDD−M_policy`다. 첫 차분은 음/양 어느 쪽도 잘라내지 않는다. anchor는 실제 최고값 표본이 아니며 상태에는 표본 valid bit를 둔다.

세 참조 R={EDD+ECT, SHARED_EFT, Band}는 동일 입력·실현 비용으로 종료한 독립 실행이다. 미래 참조값은 target에만 쓴다. BASE는 EDD 하나이며, 세 기준 지표의 최솟값을 합친 가상 스케줄러를 실행한다고 주장하지 않는다.

```text
c_energy = max(0, max_r(J_policy - J_r - eps_J)) / 1J
c_incomplete = planned - successful_completion
c_urgent = max(0, max_r(urgent_fail_policy - urgent_fail_r))
c_normal = max(0, max_r(normal_fail_policy - normal_fail_r))
c_p95 = max(0, max_r(P95_policy - P95_r - eps_ms)) / 1500ms
```

각 cost 목표0, 초기 λ=[1,10,10,10,10], `λ=max(0, λ+0.01*valid_batch_mean(cost))`는 기존 제안이다. 기대 비용 벌점이며 조건별 무위반 보장이 아니다. 양의 악화만 쓰므로 목표0에서 λ가 줄지 않는다는 성질을 명시하고 λ/KL/entropy를 기록한다. 승수 폭증·유효 행동 붕괴가 발생하면 원 기준을 완화하거나 보상을 현장 튜닝해 통과시키지 않는다.

미완료도 전체 분모에 남긴다. 실제 공통창에서 적분 가능한 부분 J는 진단값으로 보존하되 전량 절감 target으로 사용하지 않는다. heat와 전량 J cost는 null/채널 mask, 완료·서비스 cost는 유효하게 유지한다. 참조 미완료·null이면 해당 참조의 대응 cost도 만들지 않고 부적격을 기록한다. 채널에 유효값이 없으면 λ 갱신0이다. 누락을 적격성으로 처리하지 않는다.

`EDD_ECT_FEASIBILITY_PRIOR_V1`은 같은 후보·mask에서 BASE 우선, BASE 제외 시 정규 행동 순서의 첫 적격을 택한다. `EDD_ECT_THERMAL_GREEDY_V1`은 현재 Q에서 세 문맥 모두 BASE 대비 J 비증가인 후보 중 worst-κ ΔAP→worst-κ ΔJ→BASE 선호→정규 순서로 고른다. BASE가 서비스 부적격이고 J 비증가 후보가 없으면 통과 후보 중 worst-κ ΔJ 최소로 복구하고 예외를 기록한다. 이 국소 J 제한은 greedy에만 적용하며 RL mask에는 넣지 않는다. 두 규칙도 전역 성능은 미검증이다.

## 검증 순서와 채택 기준

| 단계 | 완료 조건 |
|---|---|
| A 의미 검증 | 원 EDD BASE 실제 원장 일치, SPT/EDD가 다른 수작업 사례, lane 완료와 응답 구분, 대기 종류/credit, overrun, 묶음 취소, 미래정보 차단, 순수 suffix와 공개 상태 event 재생 일치, reward 망원합·채널 null |
| B 행동 검증 | 실제기한을 통과하고 BASE와 다른 물리 실행 prefix가 존재. 이름만 다른 중복은 제외 |
| C 개선 가능성 | 사전 지정 개발 조건에서 전체 실행의 전량·서비스·P95·J·AP가 EDD/Shared/Band 모두에 비악화이며, Shared/Band 대비 AP 감소와 EDD 대비 J 또는 AP 감소가 있는 사례. 미래를 본 분기/예상값만으로 통과 금지 |
| D 실행 등록 | 환경당/최악 callback·projection 시간, 입력/seed 충돌 검사, 장부·세 참조 cache·학습 시간 상한·archive 동등성 확인 |
| E 정책 판정 | 동결24검증의 각 조건에서 전량 및 실패/P95/J/AP가 EDD/Shared/Band/강한Triton 각각 비악화. 주조건은 절대 기한도 충족. 주조건에서 Shared/Band 대비 열 개선과 EDD 대비 J 또는 AP 개선을 확인 |

C는 학습을 시도할 모형상 신호, E는 검증 후보 선택 기준이며 실기기 성능 인증이 아니다. C/E의 각 개선 횟수와 교집합도 공개해 서로 다른 조건의 이득을 하나의 공동 이득으로 합치지 않는다. AP/J의 실용적 최소효과와 표면온도 변환은 null이다. 단순 수치 차이를 모형 오차보다 확실한 개선으로 표현하지 않는다.

prototype 개발 입력은 이전48개 개발 조건에서 **가장 작은 seed의 4부하×3문맥=12조건**을 결과와 무관하게 고른다. 각 조건의 EDD/Shared/Band/prior/greedy 최대60실행, BASE와 비BASE가 모두 적격이며 물리적으로 다른 최초 시점의 분기 최대24실행, 엔진 fixture/오류 최대44로 총128 이내다. BASE 대 첫 정규 비BASE를 비교하고 분기 뒤에는 같은 prior를 사용한다. 두 arm의 prefix는 동일하게 재생한다. BASE가 부적격이거나 분기할 지점이 없으면 없는 결과로 남기고 다른 좋은 시점으로 바꾸지 않는다. 단순 함수 검증은 환경0, 엔진 호출 fixture는 모두 사전 차감한다.

정규 행동 순서는 BASE 중복을 합친 뒤 single→bundle→COOL_WAIT, 요청 EDD 순위·CPU/GPU 순이다. BASE가 mask에 없을 때의 prior 동점도 이 순서를 사용한다. 대표 사례와 분기 선택은 성능을 보기 전에 source/input 서명과 함께 고정한다.

학습 후에는 각 seed를 따로 검증하며 적격 checkpoint만 mean ΔAP(EDD 대비)→worst ΔAP→mean ΔJ→이른 checkpoint 순으로 선택한다. 적격0이면 정책 선택0·추가 학습0이다. 최종192는 새 미열람 seed를 충돌 검사 후 고정하며, 옛192는 회귀·진단용이다. 부하/기한을 결과 뒤 바꾸지 않는다. 모든 seed의 통과/실패를 보고하며 좋은 seed만 발표하지 않는다. 적격 actor가 없는 seed의 최종 성능은 null/미선정 사유로 남기고 다른 checkpoint로 대체하지 않는다. 아래17정책은 3seed가 모두 적격일 때의 최대 실행 수다.

## 비교군과 예산

현재 누적은 옛2,241+IE584=**2,825/20,000환경**, 잔여17,175다. 학습0/6,144, 옛 단계2 129/512는 보존한다. 새 설계 ID로 예산이나 종료된 wall clock을 초기화하지 않는다.

| 조건부 후속 배분 | 환경 최대 | 학습 episode |
|---|---:|---:|
| 학습 없는 prototype와 fixture |128|0|
| 학습·저장/재개 fixture |48|48|
| learner 11·23·37 각2,032 |6,096|6,096|
| 공통2,032학습+48fixture × 세 참조 |6,240|0|
| 3learner×4checkpoint×24검증 |288|0|
| 고정7정책×24검증 |168|0|
| 최종17정책×새192조건 |3,264|0|
| 비학습 오류·복구 여유 |256|0|
| 합계 |**16,488**|**6,144**|

누적 최대19,313/20,000, 미배분687이다. 옛 안의13,912를 별도로 더하지 않는다. validation 고정7은 EDD/Shared/Band/Triton-off/R2/prior/greedy다. 최종17은 기존 완료11정책(Triton5·Band·Shared·내부EFT·에너지규칙2·R2)+EDD+prior+greedy+RL3seed다. 정확한 ID는 계약 목록을 기준으로 한다. 옛 문서의 ‘15정책’과 역할 합계가 맞지 않던 부분도 목록 산술로 바로잡았다. SPT/FIFO는 완료 비교를 보존하며 새 학습 기준을 늘리기 위해 추가하지 않는다.

세 learner는 동일2032case(508seed×4부하, 사전 순환 문맥)를 사용한다. 3참조 cache는 입력·모형·초기값·source·실현 비용·완료 receipt가 모두 같은 경우만 공유한다. 캐시 유실/불일치는 상한 밖 자동 재계산이 아니라 중단 사유다. 참조·검증·실패·중단 episode도 실제 시작을 세며, 학습 fixture48은 전체학습6144에 포함한다. 절약된 cache와 미배분 예산으로 탐색/seed/episode를 자동 추가하지 않는다.

prototype 시간 제안60분/저장5분, 학습 wall 상한과 신규 seed는 비용 확인 전 null이다. 이 수량이 시간 내 실행 가능하다는 주장은 없다. 전체 예산을 만족하더라도 A/B/C/D 통과와 실행 계약 고정 전 학습은0이다.

learner별 archive는 actor·6critic·Adam·Python/NumPy/Torch CPU RNG·λ·109/68/32 schema·대기 credit/공개 응답 상태·data cursor·미완료8episode batch·참조 cache binding·소비장부·선택상태를 보존한다. 정상 중지는 현재 episode 종료 뒤에 하고, 재개 때 완료 episode 재학습·optimizer 초기화를 하지 않는다. 예기치 않은 중간 실패는 실제 소비로 남기며 자동 무상 재실행하지 않는다. 선택 actor와 최종 학습 weights는 별개로 보존한다.

## 구현 경계와 다음 작업

다음은 학습 없는 `tools/d1_edd_ect_residual_controller.py`와 별도 runner의 구현 및 A/B/C/D 검증이다. 파일명은 계획이며 현재 새 controller가 있다는 뜻이 아니다. 원 EDD/Shared/Band/Triton·모형·기본정책·strict 지원·`experiment_ready=false`는 수정하지 않는다.

최신 [AP 입력 확인](AP_OBSERVATION_PATH_PC_20261008.md)상 현재 APK에는 numeric AP의 지속 수신 경로가 없다. [에너지 보정](ROLLING_ENERGY_SHRINK_RESULTS_20261008.md)도 후보 미채택이다. 새 RL에 실측 AP stream이나 보정 계수를 있는 것처럼 넣지 않는다. 모바일 제어 계산의 시간/J도 미측정이며 PC callback 비용과 구분한다. S26/NPU·표면온도·새 실측은 이번 범위 밖이다.

기존 규칙+RL 조합 자체는 새로운 발상이 아니다. [2025 HA-DQN 연구](https://link.springer.com/article/10.1007/s40747-025-01828-6)는 작업 선택을 학습하고 기계/AGV 선택에 휴리스틱을 쓴다. 우리의 후보는 스마트폰의 기한·공유 점유·열 이력과 에너지 상충을 다루며 자원 선택도 보정한다. 그 논문의 구현이나 성능을 재현했다고 부르지 않는다. 학습 목적은 [PPO 원 논문](https://arxiv.org/abs/1707.06347)의 clipped objective를 사용하지만 서비스 보장은 별도 검증 사항이다.

실제 차별성은 **같은 실측 기반 모형·작업량·응답 조건에서 산업공학 기본 규칙의 어떤 선택을 바꿨고, 열·에너지·서비스가 어떻게 달라졌는지 검증하는 것**이다. 효과가 없으면 규칙 대비 개선 실패로 남긴다.
