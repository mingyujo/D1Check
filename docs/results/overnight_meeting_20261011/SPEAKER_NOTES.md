# 발표자 노트

권장: 핵심10장 약10분, 부록9장은 질문 때 사용. 기본 화면은 핵심만 이동하며 부록 포함 버튼으로 전체19장을 연다. 화살표/PageUp·PageDown 이동, N 노트 토글, 인쇄는 모든 슬라이드를 출력한다.

## 1. 온디바이스 AI의 CPU/GPU 자원 스케줄링

모델 정확도를 높이는 프로젝트가 아니라 앱 내부 요청의 순서·CPU/GPU 배정·실행 시점을 선택하는 연구입니다. 연구 자료 묶음의 완료와 새 정책 우월성 입증의 완료를 구분해 설명합니다.

근거: docs/OVERNIGHT_COMPLETION_20261011.md

## 2. 실제 문제: 같은 자원을 두 작업이 나눠 쓴다

분류·탐지는 자원 배정 문제를 검증하는 예시입니다. 실제 사용자 로그는 없으므로 이번 도착은 사전 고정한 합성 trace입니다. 시장 규모나 모든 휴대폰의 온디바이스 구조를 수치로 주장하지 않습니다.

근거: docs/MULTITASK_EXPERIMENT_PROTOCOL.md, docs/BOUNDED_EMPIRICAL_RESULTS_20260921.md

## 3. 범위와 KPI를 먼저 고정했다

사용자가 원래 제시한 표면 온도 목표와 현재 측정 가능한 AP 지표 사이의 공백을 숨기지 않습니다. 기기별 자료를 혼합하지 않았고 NPU 자료는 별도 범위로 보존합니다.

근거: docs/results/overnight_ie_20261011/execution_contract.json, docs/OVERNIGHT_COMPLETION_20261011.md

## 4. 실측 근거와 품질의 의미

30세션/480호출은 제한된 resident/thermal0 실측입니다. CAL-03 자료 적격 통과는 모든 예측 정확도 통과가 아닙니다. 과거 198요청의 조건부 정책 주 판정 FAIL도 유지합니다.

근거: docs/BOUNDED_EMPIRICAL_RESULTS_20260921.md, docs/ARRIVAL_CAL03_EXECUTION_20260924.md, docs/ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md

## 5. 응답 완료와 자원 반환을 분리한다

빠른 출력 준비를 lane 반환으로 착각하면 유령 병행과 성능 이득이 생깁니다. 처리 종료·저장·worker 해제·lane 반환을 각각 보존하는 것이 시뮬레이션의 핵심입니다.

근거: tools/d1_arrival_explore.py, docs/results/overnight_ie_20261011/verification.json

## 6. 새 열 모형: 평균 오차는 줄었고 한계는 남았다

같은 미래 예정 요청으로 예측한 B를 주로 비교합니다. 실제 미래 점유를 넣는 A는 조건부 진단입니다. 첫 v3의 AP/J 동시 감소 FAIL을 유지하고, 별도 hybrid 동결 뒤 새 2회로 확인했습니다.

근거: docs/ROLLING_HYBRID_PILOT_20261011.md, docs/results/overnight_meeting_20261011/supporting_evidence/model_validation.json

## 7. 산업공학 구조: EDD·ECT + 공동 롤링

예시: 현재 분류1건+탐지1건이 있다. 분류CPU→탐지CPU 순차와 분류GPU+탐지CPU 병행을 비교한다. 선택한 첫 배정(가능한 동시 쌍)만 실행한다. 새 요청이 도착하면 다시 계산한다. 잠깐 냉각을 기다리던 중 새 탐지가 몰리면 기한이 나빠질 수 있으므로 미관측 초기 대기를 보수적으로 제한한다. 산업공학 기여는 병렬 자원 배정·납기·호환성·반복 재계획의 대응과 정량 검증이며 전역 최적해를 주장하지 않는다.

근거: docs/ROLLING_EXPERT_REVIEW_20261010.md, tools/d1_rolling_joint_thermal.py

## 8. 강한 비교군도 출처의 판단 규칙을 옮겼다

이름을 붙인 임의 FIFO가 아니라 출처 기반 판단 흐름을 옮겼습니다. 실행 단위와 자원 범위가 달라 외부 제품보다 우월하다는 주장은 하지 않습니다. 기준이 강하면 새 정책이 이를 못 넘는 것도 유효한 연구 결과입니다.

근거: docs/results/external_rules_01/README.md, docs/REQUEST_TRITON_THERMAL_ENERGY_PC_20261007.md

## 9. 리스트 보완: 무조건 기다리는 문제를 줄였다

R1/R2는 새로운 계수나 기한을 넣은 방식이 아니라 기존 선택기의 위험을 분리한 작은 보완입니다. 알고리즘 숫자를 늘리는 대신 실제 반례를 고쳤습니다.

근거: docs/results/overnight_ie_20261011/execution_contract.json, tools/d1_overnight_ie_policy.py

## 10. 확인①: R1은 서비스 손실을 막았지만 교체 기준은 미달

새 확인48의 seed828110101..104입니다. R1은 Band와 같은 일반 실패40건이고 기존 Rule42건의 추가 실패를 막았습니다. 13조건의 비용 악화를 평균으로 상쇄하지 않았습니다. 온도 차이는 아주 작고 실제 절감이 아닙니다.

근거: docs/results/overnight_ie_20261011/summary.json, docs/results/overnight_ie_20261011/confirmation_verdict.json, docs/results/overnight_ie_20261011/confirmation_comparison.csv

## 11. 확인②: P95 유연성을 열어도 공동 개선은 자동으로 생기지 않았다

확인①과 다른 새 seed828120201..204입니다. 실패40/42를 전후 개선으로 비교하지 않습니다. 과거+현재 도착/소유 미응답의 P95를 쓰며 개별 lateness는 보호했습니다. 실제 누락 후보는 CPU가 바쁠 때 GPU 즉시 실행 대신 CPU 반환을 기다리는 자원 대기였습니다.

근거: docs/results/overnight_ie_flex_20261011/summary.json, docs/results/overnight_ie_flex_20261011/execution_contract.json, docs/results/overnight_ie_flex_20261011/expert_review.md

## 12. RL은 실제로 학습했다: 짧은 3seed 파일럿

기본·복귀·학습 참조는 L0이고 Band는 비교군입니다. 자체 PyTorch masked PPO가 실제 후보 슬롯을 선택했습니다. EDD/ECT를 이름만 보상에 붙인 구조가 아닙니다. 행동 마스킹은 물리 불가능과 예측 위험의 구분이며 미래 기한 보장이 아닙니다. 이번 새설계3learner는 과거PPOv2와 별도이며 소실된 과거 학습 상태의 연장 또는 프로젝트 전체학습수로 표시하지 않습니다.

근거: docs/results/rolling_list_rl_pilot_08/summary.json, docs/results/rolling_list_rl_pilot_08/verification.json, tools/d1_rolling_list_rl.py

## 13. 같은 설정으로 더 학습하면 개선되는가?

전체 actor·Adam·RNG와 원 알고리즘·보상을 유지한 학습량 비교입니다. 최고 seed 하나를 골라 대표하지 않고 세 terminal512를 모두 평가했습니다. 실제 Adam 각768step/gradient가 발생했습니다. 개발24에서 seed11/23은 Band KPI와 같았지만 새 확인48에서는 세 PPO 모두 일반45건 vs Band42건입니다. 이는 비단조 학습과 일반화 제약이지 학습 미실행·수렴 완료·RL 일반의 실패를 뜻하지 않습니다. L0 자체도45건이며 서비스 학습참조 L0와 강한 최종 비교군 사이의 격차를 구분합니다. NoWait는 냉각 대기와 자원 대기를 함께 제거하므로 비용 변화를 냉각만의 효과로 분리하지 않습니다. 기본/복귀는 L0이며 외부 Band로 복귀한 것이 아닙니다. NoWait가 제거하는 것은 명시적 냉각·자원 대기 후보이며, 실제 AVAILABLE까지 기다리는 불가피한 대기는 유지한다.

근거: docs/results/overnight_rl_20261011/result.json, docs/results/overnight_rl_20261011/verification.json, docs/results/overnight_rl_20261011/checkpoint_inventory.json

## 14. A24 확인: PC 계획과 실제 실행의 차이를 본다

기기에서는 사전 고정한 CPU/GPU와 실행 시점을 재생하며 busy lane는 실제 AVAILABLE까지 기다립니다. 원 정책의 온라인 판단 코드를 실행한 것은 아닙니다. PC AP35..180과 실측0..120의 관측 표본 최고는 다른 창입니다. 실제35..180초의 최초 경계와 마지막0.68..1.64초가 완전히 관측되지 않았으므로 정확한 연속180초 최고는 계산 불가입니다. 초기AP·순서반전·정책별2회와 전류 mA해석의 조건부J를 표시하며 절대 에너지 교정·실제 우월성은 미확정입니다.

근거: docs/results/overnight_device_20261011/summary.json, docs/results/overnight_device_20261011/requests.csv, docs/results/overnight_device_20261011/pairs.csv

## 15. 추천과 아직 확정하지 않은 것

Band 기본+롤링을 새 자체 방법론으로 채택하지 않았습니다. 연구 방향은 리스트 후보+RL이며 R1은 그 비학습 발전 후보입니다. RL 새 결과의 원 기준 통과 여부를 확인하고, 엄격한 최종 대체 기준 미달은 그대로 남깁니다. 실제 앱의 기존 기본은 바꾸지 않았고 공개 제품 전체와 승패를 말하지 않습니다.

근거: docs/results/overnight_ie_20261011/confirmation_verdict.json, docs/results/overnight_ie_flex_20261011/confirmation_verdict.json, docs/OVERNIGHT_COMPLETION_20261011.md

## 16. 한계와 다음 작업을 구체적으로 남긴다

마지막 제한은 연구 probe가 가능하다는 것과 재배포 승인이 다르다는 의미입니다. 추가 측정은 어떤 주장을 검증할지 목적을 먼저 고정해야 합니다. 지금 숫자 개선을 위해 계수·SLA·완료량·지원 범위를 바꾸지 않았습니다.

근거: docs/MODEL_02_INVENTORY.md, docs/RECOVERY_SERVICE_RESULTS_20261010.md, docs/ROLLING_HYBRID_PILOT_20261011.md

## 17. 사후 기전 진단: 학습과 별개로 검토할 제약

이미 본 확인자료를 재사용한 사후기전 진단이며 새 독립 확인이나 최종 채택 성공이 아닙니다. 첫 분기 전 배정과 관측 phase 콜백이 같은 것을 확인했고 실제 원 encoder 전체와 물리/예측 마스크를 검사했습니다. 긴급 예측 241.818→379.693ms는 1.5초 기한 안이지만 L0보다 느려 차단됩니다. 뒤 D22 응답은 L0계열6.303초 vs Band5.973초, 추가 CPU점유330.433ms는 사후회계이며 정책에 미래값을 주지 않았습니다. 이 상태의 원인을 모든 차이의 유일 원인으로 확대하지 않습니다. 다음 별도 설계에서는 L0참조와 최종 KPI의 대응, 긴급 P95 여유와 CPU전용 작업의 호환성을 검토해야 하며 이번 판정·목표·정책은 바꾸지 않았습니다. 해당 동일 상태·현재 허용 규칙에서의 차단이다. 이전 행동으로 다른 상태에 도달할 개선 가능성까지 부정하지 않으며, 예측 P95가 최종 전체 P95나 서비스 보장은 아니다. 마스크를 즉시 풀면 모든 KPI가 개선된다는 뜻이 아니다.

근거: docs/results/overnight_reference_gap_20261011/README.md, docs/results/overnight_reference_gap_20261011/matched_history_focus.json, docs/results/overnight_reference_gap_20261011/verification.json, docs/results/overnight_reference_gap_20261011/expert_review.md

## 18. 질의응답 ①

질문에 수치만 답하지 말고 같은 입력·원단위·증거의 범위를 함께 설명합니다.

근거: docs/OVERNIGHT_COMPLETION_20261011.md

## 19. 질의응답 ②

질문에 수치만 답하지 말고 같은 입력·원단위·증거의 범위를 함께 설명합니다.

근거: docs/OVERNIGHT_COMPLETION_20261011.md
