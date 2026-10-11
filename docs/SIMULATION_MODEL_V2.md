# 새 시뮬레이션 모형 v2

새 모형은 기존 기본/RL 모형과 분리되어 있다. [실측 사전 계획](SIMULATION_MODEL_V2_PLAN_20261010.md), [종료 경합 수정·남은 측정](SIMULATION_MODEL_V2_REPAIR_20261010.md), [현재 상태](PROJECT_STATUS.md)를 함께 따른다.

구현·개발동결·8자료 확보와 새 확인4의 판독을 완료했다. [최종 비교와 재현](results/simulation_model_v2_01/README.md), [동결 모형](results/simulation_model_v2_01/run_v1/model.json)을 사용한다. 회복 확인의 AP/J는 개선됐지만 CPU/PAR 혼합 요청 비용은 악화해 기본 교체를 보류한다.

## 구성

1. **서비스:** dispatch→execution→output→persist→worker release→lane available의 실제5구간을 함께 보존한다. `mean`은 세션 균등 평균, `session_replay`는 해당 cell/context의 한 개발세션 순서 벡터를 재생한다. 독립 요청 분포나 미래 P95 보장은 아니다. 서로 다른 cell의 경합 중 속도 변화는 추가 전이 가정이다.
2. **제어:** 기존 CPU/PAR 규칙의 판단 시작→배정 중앙1.563ms를 별도로 더한다. 새 PPO의 실기기 비용으로 전용하지 않는다.
3. **에너지:** `E(0,t)=P_pre·t＋Σ 추가전력_s·실제 lane 점유시간_s`. 세션별 시작 전 전력이 baseline이고, 상태 전력은 개발 자료만의 비음수 추정이다. 미래 배경부하와 센서 절대 정확도는 해결되지 않았다.
4. **AP:** 고정 fast β와 slow τ1920초의 실제 점유 입력 convolution을 사용한다. β/τ의 물리적 유일 식별을 주장하지 않는다. 상태별 fast 계수4와 부하 연동 slow 계수1을 개발 자료만으로 추정한다.
5. **초기화:** 과거 일정이 주어진 경우 가열 입력 `F(pre)`를 초기AP에서 먼저 빼고 유효기준R/잔열H를 추정한다. 미래는 `AP(t)=R＋(AP_anchor−F(anchor)−R)e^(−βΔt)＋H_anchor·K(β,30,Δt)＋F(t)`다. 마지막 관측을 anchor로 유지하므로 과거 이력과 초기AP를 이중 가산하지 않는다. R은 주변온도 실측이 아니며, 기록 이력 이전 slow 상태0도 명시적 가정이다.

CPU와 GPU의 소유권은 실제 lane release까지 유지한다. 최대2건/CG_DC 조합만 허용하고 미측정 조합은 거절한다. 현재 요청 범위는 분류urgent의CPU/GPU와 탐지normal의CPU다. 전체 도착 분모/미완료/기한 실패와 완료 응답P95를 함께 제공한다.

## 확인 경계

- A: 실제 실행 일정에 조건부인 J/AP 예측.
- B: 예정 도착→고정CPU/PAR/EFT 일정→응답/J/AP 예측. 새로운 실제 정책을 실행한 결과가 아니다.
- 기존35 자료의 재평가는 이미 본 자료의 사후 비교다. 새 개발4자료로 동결한 뒤 별도 확인4를 판독한다. 원 종료실패 계측1을 포함하면 APK와 lifecycle 차이를 별도로 표시한다.
- 온도→처리시간 함수, 실행 실패 확률, BAT/SOC/사용시간/NPU/S26은 미지원이다. 숫자를 계산한다는 사실은 물리 정확도나 정책 우월성 PASS가 아니다.

## 실행 예

```powershell
python -B -m unittest tools.test_d1_simulation_model_v2 tools.test_d1_simulation_model_v2_campaign tools.test_d1_simulation_model_v2_report -v
# 측정/fit 없이 저장 모형으로 입력 재생. 기존 출력은 덮어쓰지 않는다.
python -B -m tools.d1_simulation_model_v2_demo --model docs/results/simulation_model_v2_01/run_v1/model.json --output output/model_v2_demo_new --mode mean
python -B -m tools.d1_simulation_model_v2_demo --model docs/results/simulation_model_v2_01/run_v1/model.json --output output/model_v2_replay_new --mode session_replay --seed 13
```

최종 모형은 개발4 동결 계수와 동일하며 새 확인으로 재적합하지 않았다. 사후 기존자료 후보는 `output/model_v2_20261010_v1/archive_preview_v2/candidate.json`이며 새 동결 모형과 역할을 구분한다. 실제 기기 실행은 소스/계획/모형/입력/hash·미소비·환경·서명·품질 gate를 거치는 단일사용 campaign 명령만 사용한다. 종료 계획의 재실행/registry 초기화는 하지 않는다.

코드: [모형](../tools/d1_simulation_model_v2.py), [실측 실행기](../tools/d1_simulation_model_v2_campaign.py), [판독](../tools/d1_simulation_model_v2_report.py), [재생](../tools/d1_simulation_model_v2_demo.py). 기본/strict/experiment_ready=false는 유지한다.
