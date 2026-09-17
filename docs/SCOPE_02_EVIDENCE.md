# SCOPE-02 혼합 요청 범위·근거 조사

- 조사일: 2026-09-17
- 상태: **completed_with_open_gates**
- 적용 계획: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.1
- 다음 작업: `MODEL-02A` — 정확한 모델 artifact·label·license·tensor 계약을 확보하고 승인 여부를 판정한다.
- 이번 단계에서 하지 않은 일: 모델 binary 다운로드, production 구현, APK 빌드, A24 설치·실행, 성능 측정.

## 1. 결론

한 앱에서 서로 다른 온디바이스 AI 요청의 순서·CPU/GPU 경로·허용 병행 여부를 정하는 문제는 연구 가치가 있다. 모바일 multi-DNN scheduling, heterogeneous processor coordination, GPU preemption 연구가 이미 존재하므로 “모바일에서 처음”이라는 주장은 할 수 없다. D1Check의 제출 가능한 차이는 **Galaxy A24 한 대에서 실제 두 작업을 끝까지 실행하고, 강한 정적·단순 동적 기준정책과 비교하여 서비스 수준·간섭·적용 한계를 재현 가능하게 밝히는 것**이다.

분류와 객체탐지는 첫 구현 대상으로 유지한다. 입력 형식은 비슷하지만 출력·후처리·service time이 달라 작업 이질성을 만들 수 있고, Google의 공개 Android 안내와 label 자료가 있어 계약을 조사할 수 있다. 다만 공식 안내가 있다는 사실만으로 정확한 model artifact의 라이선스, 현재 raw LiteRT 경로 호환성, A24 GPU delegation, 품질을 승인하지 않는다. 이 항목은 `MODEL-02A/B` gate로 넘긴다.

실사용 도착 빈도와 burst 분포를 입증한 사용자 로그는 없다. 따라서 주평가의 arrival trace는 **합성 실험 조건**으로 명시한다. 실기기에서는 실제 모델·전처리·후처리·I/O를 수행하고 도착 시각·task·등급만 생성·재생한다. 작은 인터뷰나 시연으로 시장 수요 또는 실제 분포를 주장하지 않는다.

기존 80슬롯·diagnostic v2·CALIB-01B는 폐기하지 않는다. 각각 자원 우열의 기기 의존성, 측정·산출물 신뢰성, production 측정 경계를 제공한다. 기존 MobileNet V1의 8장 입력·1001행 표시 라벨 확보는 legacy 재현 과제로 보류하며 새 두 작업의 선행조건으로 사용하지 않는다.

## 2. 사실·추론·가정의 구분

| 구분 | 이 단계에서 확인한 내용 | 주장 한계 |
| --- | --- | --- |
| 사실 | 모바일에서 여러 DNN을 이종 프로세서에 배정·조정하는 선행 시스템 연구가 존재한다. | D1Check의 정책이 더 우수하다는 뜻이 아니다. |
| 사실 | 공식 분류 안내는 EfficientNet-Lite0를 권장하고 224×224 입력·ImageNet 1000 class·FLOAT32/INT8 변형을 제시한다. | 안내 페이지의 다른 기기 benchmark를 A24 수치로 사용할 수 없다. |
| 사실 | 공식 분류 label 자료는 조회 시 1001행이며 0행이 `background`다. | 정확한 model binary와 이 label 파일의 결합은 hash·metadata로 다시 검증해야 한다. |
| 사실 | 공식 탐지 안내는 EfficientDet-Lite0를 권장하고 320×320·COCO 80 object class·여러 정밀도 변형을 제시한다. | exact output tensor·postprocess와 current runtime 지원은 아직 미확인이다. |
| 사실 | 공식 탐지 label map은 조회 시 90행이며 10개의 `???` placeholder를 포함해 80개 object label을 sparse index로 표현한다. | validator가 단순히 80개 연속행을 기대하면 안 된다. model과의 index 결합은 아직 미검증이다. |
| 추론 | 분류와 탐지는 입력을 공유하기 쉽지만 출력·후처리·실행시간이 달라 첫 두 작업으로 구현 가능성이 높다. | A24 profile 전에는 scheduling 이득이나 CPU/GPU 우열을 알 수 없다. |
| 가정 | 일반 backlog 중 긴급 burst와 지속 혼합 요청이 서비스 수준 차이를 드러낼 것이다. | 실제 사용자 빈도 추정이 아니라 사전 고정할 합성 실험 조건이다. |
| 가정 | task와 priority를 독립시키면 특정 모델 속도와 우선순위 효과를 분리할 수 있다. | 실제 session 결과로 확인해야 한다. |

## 3. 주평가 workload 계약

수치 도착률·deadline·task 비율은 `PROFILE-02` 뒤 평가 전에 동결한다. 현재 단계에서는 조건의 의미와 비교 질문만 고정한다.

| ID | 역할 | 고정할 구조 | 해석 |
| --- | --- | --- | --- |
| W-burst | primary | 정상 작업 backlog를 먼저 만든 뒤 사전 시각에 대화형 burst 도착 | 누적 작업 중 긴급 요청 보호 능력 |
| W-sustain | primary | 두 task·두 priority가 지속적으로 도착 | 서비스 하한·backlog·starvation 관리 |
| W-low | supporting | 낮은 명목 부하, burst 없음 | scheduler overhead와 불필요한 제어 확인 |
| W-peer | supporting | 같은 priority의 서로 다른 task가 동시·근접 도착 | task 이질성·공정성·전체 완료량 확인 |
| W-swap | supporting | task와 urgent/normal 배치를 사전 지정해 교환 | 모델 자체 속도와 priority 효과 분리 |

각 trace는 실행 전에 `request_id`, `task_id`, `priority`, 입력, 예정 도착, deadline을 생성해 hash로 고정한다. 정책마다 같은 trace를 재생한다. 발생기가 늦게 enqueue해도 예정 도착 기준 KPI를 유지하며 발생기 지연을 별도로 기록한다.

실기기 workload의 실제 실행 범위는 이미지 byte 읽기, decode, task별 전처리, 실제 CPU/GPU inference, 후처리, output-ready 또는 durable persistence다. `sleep()`이나 한 모델의 반복 횟수만 바꾼 요청은 두 작업의 성능 증거가 아니다. 이산사건 시뮬레이션은 실측 profile을 보정하고 별도 A24 holdout에서 정책 순위와 핵심 지표 오차를 검증한 뒤 보조 민감도 분석에만 쓴다.

## 4. 첫 두 작업 후보 조사

### 4.1 분류 후보

- 후보: EfficientNet-Lite0 FLOAT32.
- 공식 안내: [MediaPipe Image Classifier](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier).
- label 후보: [공식 labels.txt](https://storage.googleapis.com/mediapipe-tasks/image_classifier/labels.txt).
- 문서상 계약: 224×224 이미지, ImageNet 기반 1000 class, FLOAT32와 INT8 변형.
- 관찰한 label 구조: 1001행, index 0 `background` + 1000 label.
- task output 후보: top-k `(index, label, score)`와 전체 output hash. top-k·score tolerance·non-finite 처리 규칙은 품질 gate 전에 고정한다.

### 4.2 객체탐지 후보

- 우선 후보: EfficientDet-Lite0 FLOAT32.
- 대안 1회: 우선 후보가 출처·호환성·품질·메모리 gate를 통과하지 못하면 SSD MobileNetV2 FLOAT32.
- 공식 안내: [MediaPipe Object Detector](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector).
- label 후보: [공식 labelmap.txt](https://storage.googleapis.com/mediapipe-tasks/object_detector/labelmap.txt).
- 문서상 계약: EfficientDet-Lite0 320×320, COCO 80 object class, bounding box·class·score·box count 출력.
- 관찰한 label 구조: 90행 중 10행이 `???` placeholder인 sparse index table. 표시 class 수와 tensor index row 수를 구분한다.
- task output 후보: threshold를 통과한 box/label/score의 canonical 배열과 output hash. NMS 포함 여부·box 좌표계·정렬·tolerance는 exact model을 본 뒤 고정한다.

### 4.3 아직 승인되지 않은 항목

아래를 통과하기 전에는 표의 후보를 “사용 모델”로 부르지 않는다.

1. exact download URL·원 byte·파일명·byte count·SHA-256.
2. model artifact의 배포 주체·license·재배포 조건. 안내 페이지의 문서 라이선스를 model binary 라이선스로 대신하지 않는다.
3. TFLite metadata와 associated file, input/output tensor 이름·shape·dtype·quantization·index 의미.
4. raw LiteRT `Interpreter` 또는 Tasks API 중 측정 가능한 실행 방식. wrapper 시간을 `Interpreter.run()`으로 잘못 부르지 않는다.
5. host golden input의 CPU output과 label/postprocess 검증.
6. A24 CPU 실행, strict GPU 진입·실제 delegation/fallback, cold/warm·메모리 smoke.
7. 모델별 실제 결과 품질. 정책별로 모델·정밀도·입력 해상도·threshold를 바꾸지 않는다.

## 5. 선행 연구와 D1Check의 경계

| 선행 연구 | 확인한 범위 | D1Check가 좁혀 검증할 범위 |
| --- | --- | --- |
| [Band, MobiSys 2022](https://doi.org/10.1145/3498361.3538948) | 모바일 이종 프로세서에서 multi-DNN을 조정하는 시스템 | subgraph/framework 수준 일반 해법이 아니라 A24 한 앱의 request 단위 순서·backend·허용 병행 결정과 서비스 지표 |
| [Sung et al., USENIX ATC 2023](https://www.usenix.org/conference/atc23/presentation/sung) | open mobile device의 multi-instance DNN을 앱 수준에서 적응형으로 schedule | 분산 앱·DRL 일반화를 주장하지 않고, 설명 가능한 규칙과 강한 정적/단순 동적 기준의 재현 실험 |
| [Pantheon, MobiSys 2024](https://lixianghan.github.io/) | mobile edge GPU에서 multi-DNN preemption으로 real-time task를 보호 | inference 내부 preemption 없이 CPU/GPU whole-request 배정과 start/hold, end-to-end 완료 경계 |
| [CoDL, MobiSys 2022](https://doi.org/10.1145/3498361.3538932) | 한 DNN의 operator를 CPU/GPU에 나눠 co-execute | operator 분할 없이 서로 다른 요청을 비선점 단위로 배정하고 일반 서비스 제약을 평가 |

따라서 독창성 문구는 “첫 모바일 multi-DNN scheduler”가 아니다. 제출 시에는 **기기별 profile, 실제 두 작업의 end-to-end 완료, 전체 도착 분모, 강한 기준정책, co-run 간섭을 포함한 설명 가능한 의사결정의 A24 실증**으로 한정한다. 선행 시스템과 직접 구현 비교를 하지 않으면 성능 우위를 주장하지 않는다.

## 6. 대회 적합성·중복 조사

[2026년 대회 공식 페이지](https://kiie.org/Conference/ConferenceView.asp?AC=2&CODE=CI20260701&CpPage=)는 실무적 결과, 산업공학 교육의 응용, 창의성, 활용·확장 가능성을 요구하고 아이디어 창의성·전공지식 응용·결과 활용성을 심사 기준으로 제시한다. 이 계획은 다음처럼 대응한다.

| 심사 관점 | 제출할 증거 |
| --- | --- |
| 산업공학 응용 | 대기행렬·우선순위·이종 자원 배정·서비스 제약·대응 실험 |
| 실무 결과 | 실제 A24에서 두 모델·I/O를 실행한 요청별 ledger와 정책 비교 |
| 창의성 | 단독 최속 backend 선택을 넘어 실제 co-run 간섭과 start/hold를 고려한 설명 가능한 규칙 |
| 활용성 | task adapter·profile·freeze·재calibration 절차와 실패/축소 조건 |

[공식 대회 목록](https://kiie.org/conference/conference01_1.asp?AC=2)과 공개 검색, 접근 가능한 [2021 프로그램](https://kiie.org/wp/2021b/online.asp)에서 동일 제목의 프로젝트를 확인하지 못했다. 그러나 2023~2025 전체 출품작 제목·내용을 완전하게 열람한 감사가 아니므로 중복 없음이나 최초성을 확정하지 않는다. 제출 전 `RELATED-02`에서 최근 3개년 수상/본선 자료, 논문·오픈소스와 키워드·핵심 기여 비교표를 다시 갱신한다.

## 7. 기존 작업의 보존과 역할 변경

| 기존 작업 | 유지하는 역할 | 새 주평가에서 사용하지 않는 방식 |
| --- | --- | --- |
| A24/S26 80슬롯 | 같은 모델에서도 기기별 CPU/GPU 우열이 다를 수 있다는 동기와 측정 경험 | 새 모델의 backend 우열·deadline·혼합 부하 결과로 전용하지 않음 |
| diagnostic v2/Perfetto | trace lifecycle·identity·provenance와 sched/gpu_frequency 관찰 경험 | GPU 내부 실행·fence·energy 증거로 과장하지 않음 |
| CALIB-01B | 이미지 read/decode/EXIF, timestamp, queue/terminal, durable result, exact artifact 검증 재사용 | 단일 MobileNet PASS를 두 task·A24 policy PASS로 부르지 않음 |
| CALIB-01C-INPUT | legacy MobileNet 재현 과제로 기록 | 기존 8장/미확인 1001행 label을 새 모델 품질 입력으로 승격하지 않음 |

## 8. MODEL-02 인계 조건

`MODEL-02A`는 host에서 exact artifact를 확보하고 source/license/hash/tensor/metadata/label index 표를 완성한다. 이 단계는 A24 없이 진행할 수 있다. 두 후보 중 하나라도 출처·license·tensor·label 계약이 불명확하면 다운로드 횟수를 늘려 추측하지 않고 후보를 제외하거나 사전 지정 대안을 한 번 검토한다.

`MODEL-02B`는 승인된 host bundle로 A24 CPU/GPU smoke, 품질·메모리·cold/warm을 확인한다. GPU 미지원 또는 fallback은 그대로 기록한다. 두 task의 합법적 실행 cell이 없으면 동적 CPU/GPU 배정 주장을 축소하고 queue/order 문제만 남길지 `SCOPE-03`에서 재판정한다.

SCOPE-02 완료는 모델 승인, 앱 구현, 실기기 성능 또는 정책 개선을 의미하지 않는다. 현재 deadline은 `calibration_pending`, 서비스·효과·안전 수치는 `thresholds_pending`이다.
