# D1Check 프로젝트 실행계획

- 개정: 4.4 / 2026-09-18 / A24 주평가와 추가 Android 기기 고정정책 재현평가 분리
- 기준 코드: `df8192aa61eebacf83df7a7815f0c60c8bbf4004`의 `master`. 이 개정은 문서 변경이며 새 모델·스케줄러 구현 또는 실기기 PASS가 아니다.
- 현재 작업: `ARRIVAL-EXT-01` — 기존 support-constrained 계획 동결을 보존하고, 별도 [비동시 도착 앱 내부 스케줄링 계약](ARRIVAL_SCHEDULING_EXTENSION_20260923.md)의 개발용 실측 경로를 평가한다. 이전 `SIM-PLAN-02-SUPPORT`는 [동결 계약](SUPPORT_SIMULATION_PROTOCOL.md)과 receipt `SUPPORT_SIMULATION_FREEZE_20260922.json`에서 `SIMULATION_PLAN_READY` 상태를 유지한다. 새 확장의 A24 smoke·개발 pilot 19세션은 완료됐고 독립 평가·새 본 simulation은 미실행이다.
- 현재 bounded simulation의 deadline은 사전 quantile/multiplier 규칙으로 계산한 공통 복수 engineering scenario다. 사용자 절대 SLA나 정책 우월성 기준을 승인한 것은 아니다. 이전 calibration_pending 기록은 역사적 근거로 보존한다.
- 유지: A24 개발·주평가, 기존 80슬롯과 diagnostic v1/v2 원본, CALIB-01B PASS, 실패를 포함한 전체 도착 분모. 추가: 정책 동결 후 최소 한 대의 다른 Android 기기에서 축소 재현평가.
- 전환: 단일 분류 모델은 기존 기준선으로 보존하고, 서로 다른 두 AI 작업의 요청 배정 문제를 새 주평가로 준비한다. 구체 모델과 마감시간은 아직 미확정이다.
- 문서 역할: 이 문서는 목표·우선순위, [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)는 혼합 요청·후보·선행 연구의 근거와 한계, [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)는 exact model/label/hash/tensor·host 판정, [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md)는 기기 이식 가능한 외부 모델 probe 계약, [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)는 새 다기기 실험 계약, [CALIBRATION_PROTOCOL.md](CALIBRATION_PROTOCOL.md)는 구현된 legacy 단일 모델 계약, [PROJECT_STATUS.md](PROJECT_STATUS.md)는 현재 진행 상태다.

## 현재 PC 단계의 명시적 축소 범위

2026-09-23 추가 작업은 위 2026-09-22 support-constrained PC 계약의 결과·가정을 바꾸지 않는다. 새 protocol `arrival-scheduler-v1`은 A24에서 독립 도착·실제 두 모델·resident runtime·비선점 queue 배정의 실측 확장이다. 개발 pilot 19세션을 완료했고 paired 분산과 순서 균형으로 독립 평가 27세션 제안 plan을 만들었다. 평가·새 본 시뮬레이션은 별도 승인받는다. pilot만으로 정책 우월성을 주장하지 않는다.

2026-09-22 사용자 지시를 채택했다. 아래 장기 개정4.4의 다중 도착률·등급 반전·추가 기기 목표는 현재 PC 계약의 완료 조건이 아니다. 현재 모델은 구현·gate를 통과한 exact 분류/탐지이며 A24 thermal0/resident/non-preemptive, warm 교환가능성 가정과 측정된 전체 co-run만 허용한다. 12개 offset0·분류 urgent6/탐지 normal6 배치와 54개 복수 deadline budget, 5paired atom 전수 평가로 제한한다. CPU FIFO/urgent/정적/항상 허용 co-run/시작 전 adaptive를 비교하며 STATIC=CPU FIFO alias를 숨기지 않는다.

주 결과는 Pareto frontier, epsilon=0/0.5/1은 예측 trade-off 구간의 sensitivity다. 임의 실질효과·허용손실 단일값을 만들지 않는다. exact bootstrap3125·low/central/high·5LOSO로 제한 모형 민감도를 보고한다. 반사실적 순서 효과·staggered overlap·장기 thermal·새 transition·다른 기기는 OUT_OF_SUPPORT다. 가정은 실측 검증 사실이 아니다. 사용자 절대 SLA는 calibration_pending, 복수 engineering deadline은 동결되어 있다.

다음 `SIM-RUN-01-SUPPORT`는 별도 승인 후 본 실행, 그 후 `SIM-DEVICE-CONFIRM-01`은 선택 정책의 A24 소규모 paired 확인 계획이다. 이 순서로 장기 목표와 현재 증거를 구분한다.

## 1. 한 문장으로 설명하는 프로젝트

**D1Check는 한 Android 앱에 겹쳐 들어오는 서로 다른 AI 요청에 대해, 무엇을 먼저 실행하고 CPU/GPU 중 어느 실행 경로를 쓰며 언제 병행할지를 결정하여 대화형 요청의 기한 준수와 응답속도를 높이고 백그라운드 작업의 서비스를 보장하는 앱 수준 스케줄러다.**

대회 가제는 **「스마트폰 다중 AI 작업의 마감시간·실행 간섭을 고려한 자원 배정」**이다. 긴급은 사용자가 결과를 기다리는 대화형 요청을 뜻하며 재난·의료 판단이 아니다. 연구 질문은 “기기·작업별로 미리 고른 좋은 고정 배정과 단순 우선순위보다, 현재 큐와 실행 간섭을 고려한 배정이 언제 얼마나 유리한가?”다.

수상 가능성은 보장할 수 없다. 측정 도구의 규모보다 실제 사용 문제, 강한 기준정책 대비 효과, 효과의 원인과 적용 한계를 명확히 보이는 데 개발 시간을 쓴다. 동적 정책이 이기지 못한 조건도 결과다.

## 2. 연구 범위·혼합 요청 조건·대표 시연

연구 범위는 **한 앱에서 제한된 CPU/GPU를 공유하는 여러 AI 요청의 배정 문제**다. 특정 사진 정리 기능에 한정하지 않는다. 실제 구현할 작업은 우선 분류와 객체탐지 두 종류로 제한하되, 여러 요청 조건에서 같은 정책의 적용 범위와 한계를 검증한다.

| 구분 | 이 계획의 역할 | 확정/검증 상태 |
| --- | --- | --- |
| 연구 문제 | 실행 순서·실행 경로·병행 여부 결정 | 주제 유지 |
| 실제 작업 | 분류·객체탐지의 독립 모델과 전·후처리 | 후보, MODEL-02/TASK-02에서 승인·구현 |
| 주평가 조건 | 일반 backlog 중 긴급 burst, 지속 혼합 요청 | 부하·작업 비율·도착 기록을 개발 뒤 동결 |
| 보조 조건 | 낮은 부하, 동일 등급 요청의 동시 도착 | overhead·일반성·공정성 확인; primary 실패를 대체하지 않음 |
| 대표 시연 | 사진 자동 태그·색인 중 선택 사진의 객체탐지 | 이해를 돕는 후보이며 연구 범위의 필수 제약이 아님 |

`task_id`와 긴급/일반 등급은 독립 필드다. 분류도 대화형 요청이 될 수 있고 객체탐지도 일반 요청이 될 수 있다. 기본 시연에서 분류=일반/탐지=긴급을 쓰더라도 평가 계약에서는 이를 하드코딩하지 않는다. 최소 한 사전 지정 보조 조건에서 등급 배치를 바꿔 특정 모델의 속도와 우선순위 효과를 구분한다.

사진 정리 시연을 채택한다면 누적 사진의 태그·색인은 일반 결과의 durable persistence/readback, 선택 사진의 box/label은 긴급 output-ready로 연결한다. 다른 시연을 골라도 task별 입력·출력·완료 경계를 먼저 고정하고 정책마다 같은 실제 작업을 수행한다. 시연을 늘리는 것이 연구의 필수 목표는 아니다.

SCOPE-02 조사 결과는 [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)에 기록했다. 모바일 multi-DNN·이종 프로세서 scheduling 문제와 관련 연구는 확인했지만 한 앱에서의 실제 도착 빈도·burst 분포를 입증한 사용자 로그는 확보하지 못했다. 따라서 W-burst/W-sustain의 arrival trace는 합성 실험 조건으로 공시한다. 사용 관찰·기록 또는 3~5명의 짧은 과업 인터뷰는 가능한 보조 근거지만 특정 사진 기능의 수요 인터뷰를 모든 개발의 선행 조건으로 만들지 않는다. 작은 인터뷰 표본으로 시장 수요·채택률·실사용 도착 분포를 추정하지 않는다.

통역·OCR·게임·LLM은 향후 작업 유형의 예시다. 현재 두 시각 모델을 검증한 결과로 그 작업들의 성능을 주장하지 않는다. 다른 앱이나 OS 스케줄러를 제어하는 구현도 아니다. 실측 없는 작업을 `sleep()`이나 분류 반복 횟수 변경으로 흉내 내고 실제 다중 AI 검증으로 표시하지 않는다.

## 3. 산업공학적 기여와 검증 가설

| 산업공학 관점 | 이 프로젝트의 구체 내용 | 제출 증거 |
| --- | --- | --- |
| 대기행렬·서비스 수준 | 우선순위, burst 도착, 대기와 과부하, 일반 작업 starvation | 전체 도착 로그, 긴급 P95·기한 내 완료율, 일반 backlog |
| 이종 자원 배정 | 작업별 CPU/GPU 적합성, 준비·전환 비용, 비선점 실행 | 작업×실행 경로 프로파일, 배정 결정 로그 |
| 제약하의 의사결정 | 메모리·열 안전·일반 최소 서비스 하에서 긴급 지연 최소화 | 제약 준수표, 강한 기준정책 대비 대응 비교 |
| 실험계획·통계 | 같은 arrival trace, 순서 무작위화, 개발/평가 분리 | 독립 세션 효과 크기·신뢰구간, 실패·제외 기록 |
| 이산사건 시뮬레이션 | 실측 서비스시간·간섭으로 실험 범위 확장 | 별도 실기기 holdout으로 보정 오차 검증 |
| 외적 타당성 | A24에서 정책을 고정한 뒤 다른 Android 기기에서 무재튜닝 축소 재현 | 기기별 결과와 `device × policy` 차이, 실패·미지원 cell |

가설 H1: 누적 작업 중 대화형 요청이 도착하면 단독 실행보다 지연·기한 위반이 증가한다. H2: 기한·현재 자원 점유·간섭을 고려한 정책 P가 개발 자료로 선정한 고정 정책 및 단순 동적 정책보다 서비스 제약 아래 유리한 조건이 있다. H3: 무조건 병렬 실행보다 선택적 직렬/병렬 허용이 낫다. H4: A24에서 고정한 정책 논리와 사전 calibration 규칙이 추가 기기에서도 코드·임계값 사후 조정 없이 안전하게 동작하며, 우세 backend가 달라도 기준정책 대비 방향 또는 적용 한계를 재현한다. H1부터 실측하며 H2~H4의 성립을 전제하지 않는다.

열 스로틀링 발생은 성공의 필수조건이 아니다. 관측 가능한 열 상태가 안정적인 조건에서도 H2가 성립하면 의미가 있다. 시스템 thermal status가 0이라는 사실만으로 하드웨어 스로틀링 부재를 확정하지 않으며, 미검증 온도를 에너지 절감률로 바꾸지 않는다.

## 4. 범위와 모델 선택

- 기기 역할: Galaxy A24는 개발·주평가 기기다. A24에서 정책과 분석법을 동결한 뒤 최소 한 대의 다른 Android 기기를 외부검증 기기로 사용한다. 가능하면 SoC·성능 등급이 다른 두 번째 기기를 고르고, 세 번째 기기는 일정이 허용할 때만 추가한다.
- 기존 S26 formal은 보조 사례일 뿐 새 두 작업의 외부검증을 대체하지 않는다. S26을 다시 사용할 수 있다면 다른 기기와 동일한 새 probe/profile/evaluation 계약을 통과한 결과만 재현평가로 인정한다.
- 주평가: 두 실제 task adapter, CPU와 검증된 GPU 실행 경로, 일반/긴급 요청. 먼저 전체 한 건 실행을 완성한 후 PROFILE-02의 간섭 측정을 통과한 조합만 최대 두 건 병행한다.
- 비선점 단위: 모델 내부 추론을 중단하지 않는다. 최초 구현은 이미지 한 건의 전·후처리와 완료 경계를 포함한 service 단위를 끝낸다. 레이어 분할·OS 주파수 제어는 제외한다.
- 모델 품질·입력 해상도·정밀도·전처리·후처리 임계값은 정책 간 동일하게 고정한다. 모델 크기나 정확도를 낮춰 얻은 이득을 스케줄링 이득에 포함하지 않는다.
- NPU·강화학습은 필수 범위 밖이다. 추가 기기는 CPU/GPU 중 실제 검증된 cell만 사용하며, 기기별 지원 차이를 숨기기 위한 compatibility override나 silent fallback을 도입하지 않는다. 신규 런타임으로의 전면 이전도 필요성이 입증될 때만 한다.

| 역할 | 먼저 검증할 후보 | 선택 이유와 상태 |
| --- | --- | --- |
| 과거 비교 기준 | 기존 MobileNet V1 | 80슬롯과 CALIB-01B 재현용. 원 모델·파일·해시 보존. 1001행 라벨 출처 미확인 문제는 해결된 것으로 처리하지 않음 |
| 새 분류 작업 | EfficientNet-Lite0 FLOAT32 v1 | host source/hash/tensor/내장 1000 labels·Apache-2.0 metadata 확인. A24 CPU/GPU canonical 계약 동등성 및 bounded profile 확인; 품질 수용·추가 기기 검증은 pending |
| 새 객체탐지 작업 | EfficientDet-Lite0 FLOAT32 v1 | source/hash/tensor/내장 labels·raw/decoded CPU output 확인. exact binary license 귀속은 미입증이므로 승인 기기 내부의 비배포 연구 probe만 조건부 허용; 저장소·APK·공유 bundle 포함 금지 |

이는 최신 모델 경연이 아니다. 공개된 [분류 모델 안내](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier)와 [탐지 모델 안내](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector)는 후보의 근거이며, 표의 다른 기기 성능을 A24 성능으로 사용하지 않는다. 파일을 확보한 뒤 실제 출력 tensor/metadata·label index를 검사해야 한다. 공식 문서가 있다는 이유만으로 특정 파일의 라이선스·1000/1001행 대응·GPU full delegation이 검증된 것은 아니다.

MODEL-02A 결과는 [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)에 기록한다. EfficientNet 분류는 host 계약을 통과했다. EfficientDet는 exact binary license 귀속이 확인되지 않았지만 Google 공식 안내와 Apache-2.0 sample이 고정 v1 URL을 직접 내려받아 쓰는 사실, raw/decoded host golden을 확인했다. 이는 법적·재배포 승인이 아니다. URL·byte count·SHA-256을 고정하고 binary를 저장소·PR·APK·팀 공유물에 넣지 않으며 각 실행자가 원 URL에서 직접 확보하는 **승인 기기 내부 비배포 연구 평가만 조건부 허용**한다. 배포가 필요해지면 exact license/NOTICE를 확보하거나 명시적으로 라이선스된 artifact로 교체한다. MODEL-02B는 동일 외부 manifest와 probe 코드로 각 기기의 CPU/GPU 실행 가능성, 실제 delegation/fallback, 품질, 메모리, 초기화 비용을 확인한다. 첫 pilot과 full profile은 A24에서 수행하고, 추가 기기는 정책 동결 뒤 같은 계약의 축소 profile을 수행한다. TASK-02에서만 사용자 경로와 공통 runner에 연결한다. GPU가 항상 불리하거나 미지원이면 그 사실을 받아들이고 큐 순서·동시성 제한의 효과를 검토한다.

## 5. 기존 구현과 새 구현의 경계

기준 commit의 calibration은 MobileNet FLOAT32 `[1,224,224,3] -> [1,1001]`와 image-v3 전처리에 고정돼 있다. 새 모델을 asset 교체만으로 넣을 수 없다. CALIB-01B의 119개 JVM 테스트 통과는 두 작업 지원이나 새 모델의 정확도·성능 통과가 아니다.

재사용할 것은 입력 read/decode·EXIF, monotonic event, queue/terminal 계약, 결과 영구 저장, exact artifact set/provenance 검증, CPU/GPU 준비·정리 경계다. TASK-02에서 모델별 전처리·출력 tensor·후처리와 label mapping을 명시하는 adapter, `task_id`/`model_id`, 독립 도착 발생기, 정책 공통 runner를 추가한다. 기존 core inference 타이머는 보존한다. 새 모델 API 내부를 계측할 수 없으면 API 호출 시간으로 따로 이름 붙이고 `Interpreter.run()`이라고 부르지 않는다.

formal v1, diagnostic v2, `calibration-v1`/schema 2, `android-mobilenet-v1-image-v3`는 그대로 보존한다. 새 task/arrival/result 계약은 별도 `multitask-v1`(예약 ID, 미구현)로 버전 관리하며 기존 CLI·manifest에 없는 옵션이 이미 작동한다고 문서화하지 않는다.

기존 `CALIB-01C-INPUT`은 legacy 단일 모델 입력 준비로 보류·재계획한다. 검증된 1001행 라벨을 꾸며서 통과시키지 않고 기존 blocker를 기록한다. 새 모델의 자체 검증된 labels를 쓰는 경로와 과거 라벨의 출처 해결은 별개다. 기존 8장 이미지는 연결 확인용이며 새 두 작업의 정확도 평가 데이터로 자동 승격하지 않는다.

## 6. 스케줄러 의사결정

요청 i는 예정 도착 a_i, enqueue e_i, 작업 k_i, 등급 u_i, 마감 d_i, 입력 hash, 허용 실행 경로 집합 E_i를 갖는다. 상태는 대기열, 현재 실행 요청·잔여시간 추정, warm 인스턴스, 메모리, 열 관측이다. 결정은 다음 요청, 실행 경로, 지금 시작/대기 및 허용된 병행 조합이다. CPU/GPU는 독립된 공장이 아니라 CPU 전·후처리와 메모리 등을 공유하므로 완전 독립 자원으로 모델링하지 않는다.

사전적 목적은 (1) 안전·품질·메모리·일반 최소 서비스 제약, (2) 긴급 기한 위반 최소화, (3) 긴급 완료 응답 P95 최소화다. 일반 서비스 하한과 허용 감소폭은 개발 단계에서 고정하고 최종 평가 후 완화하지 않는다. 가중치 최적화나 전역 최적해를 주장하지 않는다.

첫 P는 설명 가능한 규칙으로 구현한다. 새 요청·완료·열 상태 변경 시 현재까지 관측한 정보만 사용해 후보를 평가한다. 예상 완료에는 기다림, 읽기·전처리, 준비·전환, 추론, 후처리·필요한 저장 및 현재 co-run 간섭을 포함한다. 긴급은 등급 내 EDF, 일반은 공통 aging/최대 대기 규칙을 사용하며, 검증되지 않은 병행 후보는 제외한다. 예측 오차가 큰 상태에는 보수적인 프로파일 또는 직렬 실행을 사용한다. 사용하지 않는 GPU로 일부러 보내거나 평가 trace의 미래 도착을 미리 읽지 않는다.

구현은 각 실행 경로의 후보 요청과 허용 병행 조합만 열거하는 작은 dispatch 규칙에서 시작한다. 공통 aging으로 보호할 일반 요청과 서비스 제약을 먼저 적용하고, 남은 후보의 현재 대기 긴급 요청에 대한 예상 기한 위반 수·예상 지각량·예상 완료 순으로 비교한다. 동률은 예정 도착과 request ID로 해소한다. 대기를 선택할 때 다음 완료/기한/aging 경계에 재평가하도록 하며 무기한 대기하지 않는다. 이 국소 규칙은 전체 기간의 P95 최적화를 보장하지 않으므로 실제 전체 지표로 평가한다.

결정마다 선택·배제 사유, 예상 완료와 실제 완료, 정책 계산 시간을 기록한다. “열-aware AI” 같은 이름보다 어떤 관측 때문에 무엇을 바꿨는지 설명할 수 있어야 한다.

## 7. 반드시 넘어야 할 기준정책

| ID | 정책 | 비교 목적 |
| --- | --- | --- |
| B0 | calibration에서 고른 task별 고정 경로 + FIFO, 직렬 | 단순 기준 |
| B1 | 같은 고정 경로 + 긴급 우선/등급 내 EDF + 공통 aging, 직렬 | 순서 효과 |
| B2 | 개발 자료에서 고른 최선의 정적 정책: CPU-only 포함 task별 CPU/GPU 고정 배정, 직렬 또는 검증된 고정 병행, 단순 thermal pacing | 강한 정적 기준 |
| B3 | B1의 순서·aging + 단독 프로파일로 earliest-finish 경로 선택, 검증된 병행 허용 | 단순 동적 기준 |
| P | 같은 공통 규칙 + co-run 간섭·준비 비용을 고려한 예상 완료 및 시작/대기 결정 | 제안정책 |

B2는 같은 장치의 모든 합법적 task별 배정 후보(두 task·두 경로면 최대 4개), CPU-only, 고정 병행 허용/금지를 개발 자료에서 비교해 하나를 사전 고정한다. 단독 최속 경로를 그대로 B2로 가정하지 않는다. B3도 준비 비용은 고려하되 pairwise 간섭 보정은 하지 않아 P의 추가 요소를 식별한다. 평가 때마다 B2를 바꾸는 oracle을 사용하지 않는다.

정확도·열 안전·큐 상한·admission/expiry/drain 규칙·일반 서비스 목표·가용 모델 인스턴스 예산은 공통이다. 주비교 B2/B3/P의 지원 경로와 합법적 병행 조합은 동일하며 B2만 개발 단계에서 선택을 고정한다. B0/B1의 직렬 제한은 순서 효과를 보기 위한 명시적 기준 조건이다. CPU thread 수와 CPU 전·후처리 worker 예산도 고정한다. 다른 thread 수나 메모리 상한을 P에게만 주지 않는다. B2/B3/P에 동일 개발 데이터와 사전 제한된 튜닝 예산을 적용한다.

개발 결과가 유망하면 P의 (a) backend 고정, (b) 병행 금지, (c) 간섭 보정 제거를 필요한 조건에서 각각 비교한다. 열 변화가 작으면 thermal 제거 비교는 생략하고 이유를 남긴다. 단순히 B0만 이겼다는 이유로 동적 배정의 기여를 주장하지 않는다.

## 8. 측정과 공정한 평가

측정·deadline·arrival·통계 계약은 [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)를 따른다. **주평가는 A24에서 두 실제 모델을 실행하고, 요청의 도착 시각·등급·작업 비율만 합성·재생하는 실측 실험이다. 정책 동결 뒤 최소 한 대의 추가 Android 기기에서 같은 코드와 계약으로 축소 재현평가를 한다.** 모델 실행을 계산 모형으로 대체한 시뮬레이션과 구분한다.

| 방법 | 실제로 실행/계산하는 것 | 용도 |
| --- | --- | --- |
| 실기기 혼합 요청 재생 | 고정 도착 기록 + 실제 read/전처리/CPU·GPU 추론/후처리·저장 | 정책 효과의 주증거 |
| 실측 기반 이산사건 시뮬레이션 | 서비스시간·준비 비용·간섭 분포로 가상 큐와 자원 상태 계산 | 검증된 범위의 부하·burst·비율 민감도 탐색 |
| 대표 사용자 시연 | 사용자가 버튼/입력으로 실제 요청 생성 | 이해·사용 흐름 확인; 정량 반복 실험을 대체하지 않음 |

기기 간 실험은 두 묶음을 분리한다. `absolute-SLA`는 모든 기기에 같은 millisecond deadline과 같은 도착 trace를 적용해 실제 사용자 경험 차이를 본다. `capacity-normalized`는 각 기기의 동결된 단독 처리능력으로 부하를 스케일해 정책 구조의 재현성을 본다. 두 결과를 합치거나 유리한 묶음만 선택하지 않는다. 원시 latency를 기기 사이에서 단순 pooling하지 않고 기기별 효과를 먼저 보고한다.

시뮬레이션은 별도 실기기 holdout에서 오차를 검증한 뒤 사용한다. 데이터가 없을 때 임의 서비스시간으로 정책 동작을 확인하는 것은 개발용 toy 검증이며 성능 증거가 아니다. 자원이 부족하면 보조 시뮬레이션 범위를 줄이고 실기기 주비교를 우선한다. 핵심 측정 원칙은 다음과 같다.

- 주평가 시간은 예정 도착부터 output-ready/필요한 저장 완료까지다. enqueue 기준 시간도 별도 보고하여 발생기 지연을 드러낸다. 사용자 화면에 실제 표시된 시각은 UI 보조 지표로 구분한다.
- 완료 요청 P95와 전체 도착 기준 기한 내 완료율을 함께 보고한다. 오류·거절·만료·취소·종료 시 미완료를 숨기지 않는다.
- 단독/동시 실행의 서비스시간, cold/warm·전환, peak memory, scheduler overhead를 먼저 측정한다. 새 모델에서 측정한 CPU/GPU 우열을 사용한다.
- calibration/development/evaluation의 seed와 session을 분리한다. 입력 이미지도 가능하면 분리하고 재사용하면 해당 제한을 공시한다. 같은 도착 기록으로 정책을 대응 비교하고 순서는 block마다 무작위화한다.
- 저부하, 일반 작업 중 긴급 burst, 지속 혼합 부하를 포함한다. 열 스트레스는 선택적 별도 실험이다. 일부 조건만 골라 전체 상황에서 우수하다고 쓰지 않는다.
- deadline은 사용 요구와 실측 가능성을 함께 검토해 사전 고정한다. 사용 요구 근거가 없으면 engineering target이라고 표시한다. 성능을 본 뒤 낮은 위반율이 나오도록 deadline을 늘리지 않는다.
- 시뮬레이션은 실측으로 보정하고 별도 세션으로 검증한다. 실기기에서 측정하지 않은 OCR/통역/게임의 성능을 분류 지연에 임의 배수를 곱해 주장하지 않는다.

## 9. 단계·완료 조건·일정

일정은 안내문상 2026-10-22 17:00 KST 제출에 맞춘 내부 목표다. 공식 변경 공지는 제출 전에 다시 확인한다. 아래 단계는 실행계획이며 이번 문서 수정으로 완료되지 않는다.

| 작업 | 내부 목표 | 완료 조건 | 불충족 시 |
| --- | --- | --- | --- |
| SCOPE-02 | 09-17 완료 | `completed_with_open_gates`: 혼합 조건·합성 가정, 공식 안내/label 후보, 선행 연구·대회 적합성·선택적 시연을 근거 문서에 기록 | exact artifact/license·실기기 성능과 최근 대회 전체 중복 감사는 후속 gate; 특정 앱 수요를 입증한 것으로 쓰지 않음 |
| MODEL-02A/B | 09-18~09-23 | 분류 host PASS와 탐지 비배포 조건부 PASS; 기기 비종속 외부 manifest/seam을 고정한 뒤 A24 CPU·GPU 후보 smoke 및 품질·메모리 확인 | 배포 필요 시 exact license/NOTICE 또는 artifact 교체; GPU 미지원은 unsupported, 동적 자원 주장은 재검토 |
| TASK-02 | 09-24~09-28 | 두 실제 adapter, 독립 arrival, UI 결과·저장, 실패 포함 ledger와 validator 동작 테스트 | 단일 모델 pipeline을 다중 작업 완성으로 표시하지 않음 |
| PROFILE-02 | 09-29~10-03 | A24 단독/전환/허용 co-run full profile, thermal 연결, deadline·입력·주평가 규칙 고정 | 불안정 원인 수정; 병행은 이득 없으면 금지 |
| SCHED-02 | 10-04~10-08 | B0~B3/P 개발 비교, 구성요소 제거 비교, feasibility 판정, 평가 설정 freeze | B2/B3와 차이 없으면 복잡한 정책 확대 중단 |
| EVAL-02 | 10-09~10-13 | A24 실제 모델+합성 도착의 독립 세션 평가, 효과크기·불확실성·서비스 제약·실패 공시 | 판정 불충분 또는 고정 정책 우세로 기록 |
| XDEV-02 | 10-13~10-16 | 동결한 APK·모델·정책으로 추가 Android 기기 1대 이상 probe→축소 profile→`absolute-SLA`/`capacity-normalized` 재현평가 | 확보 기기·미지원 cell·실패를 그대로 보고하고 A24 결과를 모든 기기로 일반화하지 않음 |
| SUBMIT-02 | 10-16~10-20 | 15쪽 이내/10MB 이내 익명 PDF, 재현 자료, 학생별 기여·시연 | 미확인 효과를 기대효과 수치로 대체하지 않음 |

10월 8일까지 A24 기본 비교가 불가능하면 모델·NPU·강화학습을 추가하지 않는다. 추가 기기용 별도 기능을 만들지 않고 같은 runner와 host 도구의 이식성만 유지한다. A24 평가가 끝나기 전 추가 기기 결과로 정책을 튜닝하지 않는다. 남은 기간에는 동작하는 범위에서 결과와 제한을 정리한다. 역할은 사용근거·입력, Android·측정, 정책·분석, 통합·발표로 나누되 팀원 수에 맞춰 겸임하고 서로의 산출물을 교차 검토한다. AI가 제안한 설계·코드는 학생이 설명·검증할 수 있어야 한다.

### 2026-09-22 PC 계획 감사 amendment (현재 적용)

연구 질문은 A24 joint empirical 분포 아래 상태 기반 앱 요청 배정이 CPU-only·정적 정책보다 긴급 응답/deadline을 개선하면서 일반 완료율·makespan·throughput·메모리/열 손실을 사전 범위에 유지할 수 있는가다. 상충관계 자체는 비신규이며 현재 실측은 calibration이다. 기존 4.4 B0~B3/P는 보존하고 PC 계약은 별도 SP1 namespace를 사용한다.

목적은 epsilon-constraint 후 사전적 urgent miss/P95 순위다. 현재 offset0·분류 urgent6/탐지 normal6·고정 순서 trace는 재정렬·staggered overlap·선택적 co-run의 반사실적 서비스 모형을 제공하지 않는다. 미측정 overlap/4runtime/dynamic reload 금지를 유지하며 FIFO/urgent CPU/정적/항상 co-run/적응형을 비교할 지원 모형, adaptive estimator, 실질효과·허용 손실, workload/반복/drain, simulator hash는 미해결이다. 임의 null 해제나 과거 10%/2%p 자동 채택은 금지한다.

이번 master seed2026092201·정책과 계획의 부분 명세·원본 hash·consumed registry·host validator/no-op을 동결한다. 사용자 절대 SLA는 calibration_pending이고 기존 복수 engineering deadline의 전 후보를 보존한다. 현재 작업 완료는 audit/부분 계약 동결이며 사용자가 요청한 SIMULATION_PLAN_READY 달성은 아니다. 다음 ID는 SIM-PLAN-02-SUPPORT-DECISION: 새 측정 없이 반사실적 모형의 허용 가정/범위를 먼저 결정한다. 이후 정책 효과 실기기 확인·최소 추가 Android 한 대 재현이라는 전체 연구 계획은 남긴다.

### 2026-09-21 bounded descriptive amendment (입력 범위 유지)

사용자지시에따라 정확30세션계획을채택한다. 아래이전160/280설계는역사적기록이며실행하지않는다. Simulation v1은workload전setup·admit된resident runtime·관측dispatch/queue만허용하고dynamic unload/reload transition필수gate를제거한다. 정확cold populationP95·request90%PI·독립holdout80을요구하지않고, 실측cold/early/warm jointblock·complete5session/cell/5pair·quality/memory/thermal·관측요약/bootstrap/LOSO/sensitivity로제한한다. 성능보증을낮춰기존실패를통과시킨것이아니라주장범위를제한한새descriptive protocol이다. 이전holdout80.38%실패및원자료불변. 현재단계의추가기기일반화는주장하지않고기존연구전체의후속외부재현계획과구분한다.

### 2026-09-21 empirical protocol amendment

새 protocol의 scheduler는 PI를 사용하지 않으므로 request-level PI coverage90%를 새 SIM-01 필수 gate에서 제거한다. 기존 prediction model의 독립 holdout80.38% 실패를 취소하거나 재평가하지 않는다. 기존 holdout 및 v4 smoke는 consumed development다. 신규 v4 session joint block의 provenance·cell/state·독립 분포 drift/정밀도·paired completeness·품질·memory/thermal·deterministic replay로 대체하며 승인 기준은 신규 자료 전에 hash로 고정한다. [정확한 수치·표본수·한계](EMPIRICAL_CALIBRATION_PROTOCOL.md). 본 정책 운영성과 검증·deadline·미지원 전환 범위는 계속 gate이며 현재 SIM-01_INCOMPLETE다.

### SIM-01 준비 gate (2026-09-19 사용자 요청)

이번 실행에서 시뮬레이션 본 실험은 금지한다. `SIM_01_READY`는 MODEL-02B 기기/품질/artifact gate와 TASK-02 실제 완료 경계, PROFILE-02의 기기별 service·transition·thermal·capability 근거를 확보한 뒤 선언한다. 추가로 독립 device profile schema, workload/request class, arrival/service/deadline/thermal 입력, B0~B3/P 결정·목적·제약, seed/반복/KPI, manifest/schema/validator, no-op 검증, 저장/provenance·실행 명령이 있어야 한다. 어느 하나라도 없으면 INCOMPLETE 또는 구체 장애로 BLOCKED다. 기존 smoke 시간을 service profile로 바꾸거나 pending deadline을 임의 숫자로 채우지 않는다. 보조 simulation은 위 8절과 MULTITASK 9절의 실측 보정·holdout 조건을 유지한다.

2026-09-20 초기 준비 기록: draft simulation schema/semantic validator/no-op, seed namespace, B0~B3/P 의미·인터페이스와 host KPI 계약 테스트를 구현했다. 당시에는 decoded gate 실패로 draft를 INCOMPLETE로만 반환했다. 이후 네 cell의 decoded gate는 통과했지만, 독립 holdout·서비스 모델·deadline/메모리 계약이 미동결이므로 현재도 INCOMPLETE다. 실제 scheduler나 frozen service-profile 구현 완료를 뜻하지 않는다. 초기 절차는 [SIM_01_PREPARATION.md](SIM_01_PREPARATION.md), 현재 근거와 최소 다음 행동은 [SERVICE_MODEL_FREEZE_20260920.md](SERVICE_MODEL_FREEZE_20260920.md)를 따른다.

## 10. 성공·축소·중단 판정

성공 수치는 아직 `thresholds_pending`이다. 기존 제안인 긴급 P95 10% 이상 감소, 일반 기한 내 완료율 감소 2%p 이내는 개발 참고값으로만 보존한다. 일반 서비스의 절대 하한, 긴급 위반율의 허용 차이, 효과크기·신뢰구간 기준은 평가 전에 동결하며 결과를 보고 유리한 지표로 갈아타지 않는다.

| 관측 | 해석과 행동 |
| --- | --- |
| P가 B2와 B3 대비 긴급 서비스를 개선하고 일반·품질·안전 제약도 만족 | 적용 가능한 조건을 한정해 정책 기여 보고 |
| 긴급만 빨라지지만 일반이 사전 서비스 제약을 만족 | 유효한 서비스 우선순위 개선. 전체 효율 향상으로 과장하지 않음 |
| 일반 요청 포기·오류 증가 때문에 완료 P95만 감소 | 성공 아님 |
| B0 대비만 개선, B2/B3 대비 추가 효과 없음 | 우선순위 또는 고정 정책을 채택; 동적 자원 선택의 우수성 주장 중단 |
| 열 스로틀링은 관측되지 않았지만 대기·간섭 감소 | 스케줄링 결과로 유효; 열 개선 주장은 제외 |
| CPU-only가 모든 허용 부하에서 최선 | A24의 정적 선택·동시성 제한 결과로 축소. GPU 사용률을 목표로 하지 않음 |
| 추가 기기에서 P의 우위가 재현되지 않음 | 기기×정책 상호작용과 적용 조건을 결과로 보고하고 범용 우수성 주장 중단 |
| 추가 기기의 GPU가 unsupported/unverified | 해당 기기는 CPU/queue 정책 축소 재현만 수행하고 GPU 결과를 추정하지 않음 |
| 혼합 요청 문제의 근거·강한 기준 대비 개선·재현성 모두 부족 | 주제의 추가 개발 투입을 재검토 |

## 11. 대회에 보여줄 결과와 차별성

대회 안내문의 창의성·전공지식 활용·결과물 활용가능성에 맞춰 다음 증거를 만든다. “처음으로 CPU/GPU를 선택했다”는 주장은 하지 않는다.

| 평가 관점 | 제출물에서 보여줄 것 |
| --- | --- |
| 실제 문제·실무 적용 | 혼합 요청에서 대기·경합이 생기는 근거, 합성 패턴의 가정과 범위, 대표 시연 |
| 전공지식 | 자원 배정·기한·서비스 제약, 강한 기준정책, 대응 실험·불확실성 |
| 창의성 | 자원 단독 속도만이 아니라 동시 실행 간섭을 보고 병행 여부까지 결정한 효과 |
| 직접 구현·검증 | 동일 도착 기록의 B2/B3/P A24 실측, 실제 두 모델 결과, request ledger, 동결 정책의 추가 기기 재현 |
| 활용·확장 | task adapter 계약과 기기별 capability probe/recalibration 절차; 검증하지 않은 모델·기기 일반화 금지 |

보고서 15쪽 배분안: 1 제목·핵심 결과, 2 사용 문제, 3 실제 문제 근거, 4 기존 연구·범위, 5 의사결정 모형, 6 구현·완료 경계, 7 모델·입력·품질, 8 단독/간섭 실측, 9 정책·기준정책, 10 공정한 실험 설계, 11 긴급 결과, 12 일반 서비스·안전, 13 구성요소 제거·민감도, 14 활용·한계·학생 기여, 15 결론·참고문헌. 결과 페이지는 실제 측정값이 생긴 뒤 채운다. 소속 대학·지도교수 등 식별 표시는 제출본에서 제외한다.

주요 그림은 긴급 P95와 일반 기한 내 완료율을 함께 보여주는 정책 비교, 부하/간섭에 따른 유리한 정책 영역, 요청별 Gantt·선택 사유다. APK·raw·manifest·분석 코드는 해시와 버전으로 연결해 재현 패키지를 만든다. 원자료와 새 결과는 합치지 않는다.

## 12. 관련 근거와 주장 범위

2026-09-17 확인. 상세 조사와 주장 경계는 [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)에 있다. 아래 자료는 기능·기존 연구의 근거이며 실제 앱의 보급률이나 D1Check의 성능 우수성을 증명하지 않는다.

- [2026년 대회 공식 페이지](https://kiie.org/Conference/ConferenceView.asp?AC=2&CODE=CI20260701&CpPage=) 및 사용자 제공 `2026년_제22회_대학생프로젝트_경진대회_안내문_및_참가신청서_0727.pdf` 1~2쪽: 실무 결과·창의성·전공지식·활용성, 표지 포함 15쪽·10MB, 학생 주도와 중복 응모 제한. 공개 공식 목록과 접근 가능한 프로그램에서 동일 제목을 확인하지 못했지만 최근 3개년 전체 출품작 감사가 아니므로 독창성이 확정된 것은 아니다.
- [Google Acceleration Service](https://developers.google.com/edge/litert/android/acceleration_service): 모델과 기기에 맞는 가속 설정 평가가 이미 존재한다. 기기별 초기 calibration 자체를 독창성으로 주장하지 않는다.
- [Sung et al., USENIX ATC 2023](https://www.usenix.org/conference/atc23/presentation/sung): 모바일 multi-instance DNN의 앱 수준 적응형 스케줄링 연구가 존재한다. 본 계획은 한 앱·A24·설명 가능한 요청 단위 정책의 재현 가능한 검증으로 범위를 제한한다. 해당 논문 대비 성능 우위를 주장하려면 별도 직접 비교가 필요하다.
- [Band, MobiSys 2022](https://doi.org/10.1145/3498361.3538948), [Pantheon, MobiSys 2024](https://lixianghan.github.io/), [CoDL, MobiSys 2022](https://doi.org/10.1145/3498361.3538932): 이종 프로세서 multi-DNN 조정, GPU preemption, operator 단위 CPU/GPU co-execution이 이미 연구됐다. D1Check는 whole-request 비선점·service-level 제약·A24 실증으로 범위를 좁히며 최초성이나 직접 성능 우위를 주장하지 않는다.
- [Android Thermal API](https://developer.android.com/games/optimize/adpf/thermal): 열 관측·부하 조절 기능과 기기별 지원 한계. thermal status 0을 스로틀링 부재의 확증으로 사용하지 않는다.

## 13. 보존하는 기존 증거와 한계

아래는 기존 감사에 기록된 결과다. 이번 개정에서 원시자료를 재분석하지 않았으며 새 두 작업의 성능으로 전용하지 않는다.

| 증거 | 확인한 내용 | 아직 주장할 수 없는 내용 |
| --- | --- | --- |
| A24 formal 80슬롯 | CPU 중앙 지연 약 41.2 ms, GPU 약 131.6 ms, GPU/CPU 약 3.196. CPU 1/2/4 스레드 차이는 매우 작고 위치 변경 민감도 검사에서도 CPU 우세 방향 유지 | 모든 모델·부하에서 CPU가 우세하다는 일반화. 위치·주변온도 영향 제거 |
| S26 formal 80슬롯 | 원시자료 감사와 지연 재계산 통과. GPU가 pooled CPU보다 duty별 약 1.062~1.201배 빠르고 20개 block-duty 대응 비교 모두 GPU 우세. 모든 GPU run은 31/31 노드 full delegation, fallback 없음 | compatibility-list override 없는 결과로 일반화. 측정 APK와 Git 소스의 완전한 cryptographic binding |
| 기기 간 입력·설정 기록 | 모델, LiteRT 1.4.2, strict profile 설정, 대표 텐서 내용·전처리·라벨 해시 일치 | 두 기기의 전체 실험 계약과 소스가 완전히 동일하다는 주장 |
| 온도 | S26의 20개 block-duty 대응 비교에서 GPU AP 온도 상승이 모두 더 낮게 관측됨 | 동일 완료량에서 더 효율적임, 에너지 절감, 기기 간 AP 센서의 직접 동등성 |
| diagnostic v2 | trace-off/on 실기기 경로 확인. trace에서 sched 및 gpu_frequency 표본 확인 | GPU 내부 실행시간, fence, H2D/D2H 분해, 실제 FP32/FP16 확인 |
| CPU 설정 | CPU1/2/4 조건에서 뚜렷한 속도 이득이 관측되지 않음 | 실제 worker 수 또는 스레드 증가 효과에 대한 인과 결론 |

추가 주의사항:

- 대표 텐서셋은 정확도 preflight 입력이다. 실제 timed load 입력이 대표 이미지라고 가정하지 않는다. 새 요청 실험에서는 사용한 입력 바이트·생성 방식과 정확도 검사 입력을 구분하여 기록한다.
- A24 warm-up 설정은 5, S26 보고서 표기는 20 s이다. 원본 명령과 코드로 값의 단위·적용 위치를 확인하고 새 비교에서는 통일한다.
- S26은 `gpu_compatibility_list_supported=false`, `formal_gpu_compat_list_override=true`였다. compatibility-list override 사실을 모든 비교 결과에 공시한다.
- S26의 tensor container 해시는 A24와 다르다. 기록된 텐서 내용 해시는 같지만 컨테이너 차이를 직접 검증하지는 않았다.
- S26 `dataset_manifest`의 accuracy/pilot 문구는 수정이 필요하다. 원본은 보존하고 수정 설명 또는 새 export로 정정한다.
- A24의 약 22·72번째 장소 이동, 재시도와 실제 duty 차이는 기존 분석의 제한으로 유지한다.
- 실제 FP32/FP16 하드웨어 실행 여부는 unknown이다. GPU 내부 H2D/GPU/D2H 및 fence timing도 확보되지 않았다.
- 에너지 단위가 검증되지 않았으므로 J/mWh와 에너지 절감률을 사용하지 않는다.
- 측정 당시 설치 APK와 Git 소스의 완전한 cryptographic binding이 부족하다.
- S26 재시도 raw run 하나는 failure 기록이 불완전하다.
- 기존 formal 데이터, diagnostic v2 trace-off, trace-on, 새 스케줄러 실험을 서로 구분한다. 프로토콜 변경 자료를 동일 반복으로 합치지 않는다.

CALIB-01B는 FIX4까지 구현·host 검증·감사를 완료했다. 기록상 Kotlin/JVM 119건·실패/오류/skip 0, Python 195건·실패/오류 0·기존 skip 1, lint error 0/warning 76, compileall·logger self-test·assembleDebug PASS다. 기존 모델의 실기기 이미지 calibration, 새 두 모델 지원, 동적 정책 개선은 각각 미완료이며 별도로 검증한다.

2026-09-20 후속: [DECODE_RESOLUTION_20260920.md](DECODE_RESOLUTION_20260920.md)의 최초 종료는 연결 단절로 BLOCKED_EXTERNAL_INPUT이었다. 이후 [재개 결과](A24_RESUME_20260920.md)에서 최종 APK 설치·네 cell·bounded PROFILE-02를 실제 검증했다. 31개 실기기 session과 별도 host preflight 실패1건을 보존한다. 두 작업 모두 solo CPU가 빠르며, 분류 CPU 초기 호출의 큰 서비스 오차를 cold boolean만으로 설명할 수 없어 frozen profile로 승격하지 않았다. 개정4.4의 품질/profile/holdout/동결 완료 조건은 유지하고 SIM-01_INCOMPLETE다. 본 simulation·formal·정책 비교는 미실행이다.

2026-09-20 SERVICE-MODEL-FREEZE: [후속 분석](SERVICE_MODEL_FREEZE_20260920.md)에서 calibration24/과거 holdout4/사후 진단1 session을 분리하고 seed20260920, 새 prospective acceptance, 6후보와 공통 입력 준비 schema/validator/no-op을 기록했다. 이미 본 자료를 독립 holdout으로 재사용하지 않는다. backend equivalence와 절대 accuracy는 분리하며, 최신 사용자 지시대로 실제 정확도를 임의 생성하지 않고 검증된 cell의 출력 품질 보존을 scheduling 제약으로 사용한다. A24 solo CPU 우세를 반영하되 GPU 전체 지배는 미입증이다. 미검증 co-run/thermal/memory/deadline을 동결한 것으로 취급하지 않는다. 새 독립 검증이 없고 coverage도 미달이므로 frozen model은 발행하지 않았다.
