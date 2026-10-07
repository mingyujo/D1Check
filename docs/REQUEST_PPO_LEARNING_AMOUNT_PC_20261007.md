# PPO 학습량 진단과 정확한 연장 상태

2026-10-07. 이전 분석 계약·CSV·receipt·checkpoint inventory에서 확인할 수 있는 내용으로 UTF-8 한국어를 재작성했다. 실제 `?`로 손상된 원문을 추측해 복원하지 않았다. 손상 원문은commit9e1975b 및 로컬 `output/rules_rl_amount_20261007_v1/encoding_originals/`에 보존한다.

최신 별도 재학습은 [새 연구](results/request_ppo_01/rules_rl_amount_v1/README.md)를 따른다. 아래는 기존 v2의 진단이며 새 재학습 결과가 아니다.

**기존6개 실행의 정확한 이어 학습은 최종 Adam·RNG 누락으로 차단됐다.** 이후 상태 보존 코드는 과거 상태를 복구하지 않는다. 수렴 완료나 강화학습 일반의 실패를 입증하지 않는다.

## 실제 완료와 분모

- 원 `output/queue_ppo_feasible_v2`:각1,024episode/128update, 총6,144학습·720검증. 원 실행은budget_stopped, 활성5,319.094초다.
- 후속 `output/queue_ppo_v2_evaluation_v1`:남은88조건 평가만 완료(completed/205.984초). 원104조건과 합친192조건×11정책=2,112행이다.
- 논리적 합계는학습6,144+검증720+비참조시험1,920+SHARED_EFT참조1,240=10,024환경 실행이다. 원 시간 종료를 정상 완주로 바꾸지 않는다.

## 실행별 기록

[seed_accounting.csv](results/request_ppo_01/queue_learning_amount_v1/seed_accounting.csv). rollout transition은 저장된 정책 결정 표본이며 환경 전체 transition과 다르다. optimizer 반복 표본은epoch 재사용을 포함한다.

| 실행 | episode/update | rollout transition | optimizer 반복 표본 | WAIT 비율 | 선택update | 검증 적격 |
|---|---:|---:|---:|---:|---:|---|
| HEAD/11 |1,024/128|154,645|618,580|28.49%|128|예|
| HEAD/23 |1,024/128|147,669|590,676|25.11%|32|예|
| HEAD/37 |1,024/128|200,666|802,664|44.89%|0|아니오|
| QUEUE/11 |1,024/128|145,710|582,840|24.10%|64|예|
| QUEUE/23 |1,024/128|186,950|747,800|40.84%|32|아니오|
| QUEUE/37 |1,024/128|255,571|1,022,284|56.73%|128|아니오|

합계rollout1,091,211·optimizer 반복 표본4,364,844. 전체 환경transition·검증/시험 결정 총수는 기존 자료에서 미기록이다. 빈 값을0으로 채우지 않는다.

## 추세와 최종 정책

[검증곡선](results/request_ppo_01/queue_learning_amount_v1/validation_curve.csv)은 실행별0/32/64/96/128update의 주24조건이다. 일부 후반 서비스 개선과 일부 서비스/열 회귀가 있었다. 가장 이른 정책을 선택한 실행도 있어1,024episode가 부족하거나 충분하다고 단정하지 않는다.

주96조건·과부하96조건을 구분한다. [전체 결과](results/request_ppo_01/queue_learning_amount_v1/policy_results.csv)에서 검증 적격PPO는3개, PPO의 에너지·최고AP·AP면적 공동 비악화 및 엄격 공동 감소는0건이다. EFT_REFERENCE의 개선 사례는 PPO 성과가 아니다. 성공 조건만 골라 전체 정책 순위를 만들지 않는다.

## 누락 상태와 보완

[inventory](results/request_ppo_01/queue_learning_amount_v1/checkpoint_inventory.json):두ring checkpoint 모두시험 단계·learner6, network/optimizer=None이다. 6개 최종 Adam·learner별 학습 종료 RNG가 없다. 선택actor4개는 마지막 학습 가중치도 아니다. HEAD/11·QUEUE/37의 선택 가중치가 최종update라도 Adam·RNG까지 복구되는 것은 아니다.

`tools/d1_queue_ppo_learning_amount.py`의 TerminalArchiveSession은 향후 실행의 최종 actor+critic·Adam moments/step·Python/NumPy/Torch RNG·승수·선택 상태를 별도archive로 보존한다. 기존 CLI가 이 세션을 자동 학습하지 않는다. Adam lr0.0003은 일정하며 advantage 정규화는 optimizer batch 내부에만 있다. running 통계나 총 학습 길이에 종속된 스케줄은 없다.

기존4검증은 누락 차단·정상 중지/재개 후 추가 학습 가중치/optimizer/RNG 일치·공유 CSV 결측 보존·그림 재현을 확인했다. 당시fixture 환경114/학습12episode, 분석49.562초다. [원 검증](results/request_ppo_01/queue_learning_amount_v1/verification.json). fixture를 정책 효과로 사용하지 않는다.

## 당시 승인과 조건부 산식

[원 계약](results/request_ppo_01/queue_learning_amount_v1/analysis_contract.json)은 추가18,432학습/환경30,000/활성4시간·마지막5분 저장, 전체재학습0이었다. terminal 상태가 있다면1,024→2,048→4,096은 학습18,432+검증1,728+참조3,288+최종비참조4,224=27,672환경 실행이다. 상태가 없어 이 경로의 본학습·새시험·claim은0이었다.

처음부터 새6개를 학습하는 당시 선택정책만의 비교 산식은24,576본학습/35,560환경 실행으로 기존 승인 밖이었다. 이 값은 마지막 정책까지 평가하는 최신 새 연구의 실행량이 아니다. 당시fixture12학습도 별도 실제 소비로 남겨 예산을 자동 초기화하지 않았다.

새16시간/재조합4,000/RL80,000/실행별8,192 재학습 승인은 별도 계약이다. [최신 연구](results/request_ppo_01/rules_rl_amount_v1/README.md)에서 처리한다. 모형 계산을 실기기 절감·정확도·정책 우월성으로 확대하지 않으며 원자료/기본/strict/experiment_ready=false를 유지한다.
