# 데스크톱 전달 — S26 시뮬레이터와 A24 비교 검토

> 배포 추가(2026-10-11): 아래는 작성 당시 **검토 전용 역사적 프롬프트**다. 새 이관에서 S26 계획·리뷰와 A24 v2/v3 원본을 게시한다. 최신 실행은 [ATC→PPO 프롬프트](DESKTOP_ATC_PPO_PROMPT_20261011.md)를 따른다. 아래의 로컬·미게시 표현과 원격13434b4 확인은 당시 상태다.

2026-10-11. 아래 프롬프트는 **검토·자료 감사·개선 계획 작성용**이다. 별도 A24 PPO 학습 연장 프롬프트와 구분한다. S26 계획과 리뷰는 현재 로컬 문서이며 GitHub 게시를 전제로 하지 않는다. 그래서 아래에 핵심 범위와 고정 근거를 직접 포함했다.

## 복사할 프롬프트

```text
D1Check의 기존 S26 시뮬레이터를 이 데스크톱에서 검토하고, 현재 A24 시뮬레이터와의 차이 및 개선 계획을 근거와 함께 작성하라. 한국어로 보고하라. 계획만 반복하지 말고 실제 GitHub 코드·실측 로그·실행 계약을 확인하고, 가능한 관련 단위시험과 동결 결과 재현까지 수행하라.

이번 과제 ID: S26-DESKTOP-REVIEW-01
범위: 조사·자료 감사·검토·보고서. 새 모형 적합, 계수 튜닝, RL 학습, 새 정책 비교 배치, ADB·휴대폰 실행·설치는 이번 범위에 포함하지 않는다. 기존 A24 학습량 연장 작업을 이 과제 때문에 시작하거나 재개하지 않는다.

저장소: https://github.com/mingyujo/D1Check
아래 고정 커밋을 실제 GitHub에서 확인하고 각 자료의 버전을 기록하라.
- S26 기존 엔진: s26-measure / 0a0749890fba2452c5907433c6bea476a2da7e24
- S26 혼합 요청: s26-mixreq / 21cba44faa5fff1fb9703b590aa536a6207f8de5
- S26 품질20장: s26-quality20 / 5857152ad8244c41975843ded77dd33024f38f2d
- A24 공개 비교 기준: feature/arrival-scheduling-20260923 / 8175aac95c82fa70860e07e2e7566797b92b7736
브랜치 HEAD가 이후 바뀌었으면 고정 버전과 최신 버전을 구분하고, 조용히 교체하지 않는다.

먼저 AGENTS.md, docs/PROJECT_STATUS.md, 관련 PROJECT_PLAN/DECISIONS를 읽고 실제 Git 상태를 대조하라. 기존 저장소·사용자 변경·다른 worktree와 실행 중인 데스크톱 학습을 보존한다. 별도 검토 폴더/checkout을 사용하고 reset·clean·강제 merge·push는 하지 않는다. 토큰·키·민감 logcat을 출력하지 않는다.

처음에는 tree/inventory로 필요한 파일을 식별하고 코드·manifest·requests.json·progress.jsonl·hal.csv·validated.json·분석표를 선별 확보하라. 107,032개 요청별 출력 파일을 처음부터 전량 내려받을 필요는 없다. GitHub recursive tree가 truncated이면 하위 트리로 확인하고, 잘린 목록을 데이터 누락으로 오판하지 않는다. APK·TFLite·NPU AOT가 없다는 이유로 순수 Python 코드 검토를 중단하지 않는다. 실제 재현에 없는 파일이 필요하면 그 경로·SHA·영향 범위를 명시하고 독립적인 검토는 계속한다.

검토할 S26 경로:
- d1sim/: env.py, env_v2.py, profiles/, throttle_v2.py·v21·v22, policy_eval_v2/sim.py·run_eval.py, v3/predict_v3.py·predict_v3_v2.py, tests/
- s26/results/mixreq_1008/: R3_blocks/R3_readout, R4C_blocks/R4C_readout, R4S_blocks/R4S_readout, R3_LEDGER.md/R4_LEDGER.md, plan_v2/plan_v3c/plan_v3s
- s26/results/quality20_1008/: Q20_LEDGER.md와 q20_1009a/
- s26/exports/20261005/README.md, s26/results/energy_1008/, modelerr_1009/, gpuerr_1011/, gpuho_1011/
- request-runner/와 s26/tools/mixreq/: 실제 서비스·완료·센서·검증 경계

검토할 A24 공개 경로:
- tools/d1_online_policy_model.py, tools/d1_simulator.py, tools/d1_rolling_hybrid_model.py
- docs/results/rolling_hybrid_pilot_07/model.json·README.md, docs/results/online_policy_study_01/overnight_sustained_run01/model.json
- docs/results/service_goal_20261011/README.md와 연결된 실행 계약
새 S26 통합 계획이나 tools/d1_simulation_model_v3* 원본이 GitHub에 없을 수 있다. 아래 핵심 범위를 기준으로 검토하고, 공개된 streaming adapter/모형과 비공개 원 API를 같다고 가정하지 않는다. 실제로 확보한 코드와 문서만 재현했다고 보고하라.

열·서비스, 에너지 계측, 실험 검증의 3개 AI 전문 역할을 분리하여 1차 의견→상호 반박→2차 합의를 진행하라. 서로 다른 담당 파일로 작업하고 원 모델/자료를 수정하지 않는다. 에이전트 기능이 없으면 세 관점으로 직접 검토하고 독립 에이전트를 썼다고 주장하지 않는다.

반드시 확인할 내용:
1. A24는 분류＋탐지/CPU·GPU/실제 요청과 lane_available 경계/검증 조합 최대2병행이다. 현재 온도 보정 모형은 원 서비스·에너지를 유지하며 온도→처리속도 피드백이 없다. S26 주 policy_eval_v2는 같은 EffNet의 FG1회/BG128회 chunk, GPU 또는 NPU 한 자원에서 순차 처리하며 열·부하 controller가 처리율에 연결된다. 최신 S26 두 모델 mixed 실측과 기존 d1sim의 연결 여부를 코드로 검증하라. 어느 쪽이 더 정확하다고 미리 결론 내리지 않는다.
2. MobileNet/CPU4/Interpreter 개발 자료와 최신 EffNet·EffDet/CPU1/CompiledModel 자료의 모델 SHA·엔진·정밀도·resident 집합·입력·완료 단위를 대조하라. 구조 재사용과 계수 전이를 구분하고 A24/S26 계수를 혼합하지 않는다.
3. R3/R4C는 각각16세션×192요청이다. R4S는16슬롯·18실제시도(유효14/실패4)＋준비/중지2, 유효짝 A4/N2다. 전체 예정 도착·실패·미완료·관측 prefix를 보존하라. 같은 run의 요청이나 부하/회복 창을 독립 표본으로 나누지 않는다.
4. 대표 R4C에는 power_sample239행과 admission204행 모두 센서 필드가 있다. 전력 적분 대상 이벤트를 명시하고 중복 포함을 검사하라. S26 baseline30/common120/cooling60은 실제 manifest/anchors로 연결하고 A24 −20..30초 창을 복사하지 않는다. 전류·전압·잔량계의 부호/단위/갱신·snapshot/갭/경계와 full120/full720 coverage를 점검하라. 없는 표본을0으로 채우지 않는다.
5. HAL의 pc_ms와 device_boottime_s를 요청 단조시계에 어떻게 연결하는지 확인하라. 전후 bracket 부재·센서 지연·실제 온도 관측 주기를 남기고, 미래 온도 보간을 과거 예측 입력에 넣지 않는다. 유효 R4S peak SKIN38.1°C 집중을 raw/창/선별과 대조하되 전체 clip이라고 단정하지 않는다.
6. Q20 실행 장치 증거와 품질 합격을 분리하라. GPU 정밀도 미확인/NPU FP16 합격선 미등록, 별도 quality-runner APK 귀속을 보존한다. 연구 관측 재생과 승인된 정책 후보 mask를 구분하고 미검증 조합/3건 동시 실행을 허용하지 않는다.
7. 에너지 E_int와 E_cc 내부 일관성·눈금·정책 짝차 부호를 검토하라. energy_1008의 약4% 내부 차이와 전류/잔량계 방향 역전을 절대 교정 완료로 해석하지 않는다. 작은 절감 효과와 총소비량 예측 정확도를 구분한다.
8. service/AP/SKIN/J의 절대 오차와 같은 요청 정책 짝차·순위 재현을 별도 평가하라. 완료 응답 P95와 전체 도착 성공률을 함께 보고하고 °C/J/ms를 임의 점수로 합치지 않는다. 이미 본 R4C의 후행 평가를 새 blind 독립 확인으로 바꾸지 않는다.

검토할 개선 방향은 기존 엔진·추출·판독 재사용＋새 mixed profile/adapter다. 우선 서비스 S0(고정 phase/세션 블록)·S1(누적 실행/점유 한 변수), 온도 T0(사전 값 유지)·T1(점유 기반1pole), 에너지 E0(사전 전력＋식별 가능한 상태별 증분)까지의 계획을 비판적으로 평가하라. A24 prelate·τ30 에너지 보정과 온도→service/복잡 ML은 S26 근거 없이 추가하지 않는다. 이번에는 후보를 실제 적합하지 않는다.

Python/라이브러리는 코드 import와 requirements를 확인해 격리 환경으로 준비하고 버전을 기록하라. 관련 순수 단위시험과 기존 동결 결과의 재현은 가능하지만, run_compare/run_eval/fit 스크립트의 기본 전체 실행을 검토라는 이름으로 시작하지 않는다. 명령·시간·결과·HEAD·미커밋 변경·소스/자료 SHA와 재현 범위를 기록한다. 누락 fixture나 과거 FAIL을 숨기거나 기준을 완화하지 않는다.

산출물은 새 검토 폴더에 작성하라:
- README.md: 결론과 우선순위
- comparison.md: A24/S26 차이표와 코드 근거
- data_audit.csv: 데이터·세션·프로토콜·품질·coverage·가용성
- issues.md: 확인된 오류/미확인/가정, 위치와 영향
- improvement_plan.md: 재사용/수정 범위, 유한 후보·분할·평가지표·추가자료 발동조건
- verification.json: 버전·SHA·명령·시험/재현 결과·미실행 범위
3역할의 1·2차 의견과 반박도 보존하라. 원 모델·FAIL·기본·strict·experiment_ready=false를 유지한다. Git commit/push는 이 검토의 완료 조건이 아니다.

최종 보고는 ①그대로 재사용할 것 ②우선 수정할 것 ③현재 자료로 가능한 것 ④별도 원본/추가 실측이 필요한 것 ⑤우리 A24와 비교한 장단점 순으로 작성하라. 시뮬레이터 존재·코드 검증·모형 정확도·실기기 정책 효과를 서로 구분하라.
```

## 확인한 배포 경계

원격 feature는 확인 시 `13434b4e6577149a1d00a8159d1111b6c972278f`이며 비교 기준 `8175aac…`보다1커밋 앞이다. `docs/S26_SIMULATION_PLAN_20261011.md`와 `docs/results/simulation_model_v3_expert_01`는 해당 원격에서404였으므로 필수 다운로드 문서로 지정하지 않았다. 공개 A24 경로는 기준 커밋의 Git tree와 대조했다. 검토 프롬프트의 실제 데스크톱 수행 결과는 아직 없다.
