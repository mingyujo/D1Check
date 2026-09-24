# EfficientDet-Lite0 NPU 품질 게이트 — 설계 메모 (2026-09-24, 코드 미구현)

> 상태: **설계만.** 코드는 아직 없다. 이 문서의 임계값은 **제안값**이며, 영훈이 확정한 뒤
> **첫 EfficientDet NPU 결과를 보기 전에** `NpuQualityGate` 옆에 상수로 고정한다 (CLAUDE.md §2-6).
>
> 근거 라벨: `[P]` 실측 / `[D]` 문서 근거 / `[E]` 추정

## 0. 먼저 바로잡을 전제 — "출력 텐서 4개"가 아니다

팀이 고정한 바이너리(MediaPipe GCS FLOAT32, 13,836,895 B, SHA `40338edf…`)의 raw 출력은 **2개**다 [D]
(`MODEL_02_INVENTORY.md` §4, 조민규 `feature/model-02b-seam-20260918`):

| 텐서 | shape | 뜻 |
|---|---|---|
| 입력 `serving_default_images:0` | FLOAT32 `[1,320,320,3]` | `(RGB-127.5)/127.5` |
| score | FLOAT32 `[1,19206,90]` | anchor × class 점수, **디코드 전** |
| location | FLOAT32 `[1,19206,4]` | anchor box encoding, **디코드 전** |

출력 4개(`boxes/classes/scores/num`)는 `TFLite_Detection_PostProcess`가 들어간 **공식 UINT8 decoded 변형**
(4,563,519 B)의 모양이다. 그 파일은 byte·계약·라이선스가 달라 팀이 쓰지 않는다 [D].
anchor 디코드와 NMS는 MediaPipe Tasks `ObjectDetector`가 모델 **밖에서** 한다.

**12:30 G1-B 결과로 확정 [P]** (`results/G1B_NEWMODELS_VERDICT_0924.md`):
- EfficientDet-Lite0 AOT = **263/263 ops → 1 partition, PASS → `npu_full` cell 후보** (PART 아님)
- 컴파일 산출물을 직접 읽으면 출력은 **2개**: [0] `StatefulPartitionedCall:1` `[1,19206,90]` score,
  [1] `StatefulPartitionedCall:0` `[1,19206,4]` location. `TFLite_Detection_PostProcess` 문자열 없음
- 원본 `.tflite` 는 미확보라 원본 자체는 검사하지 못했다

→ 그래서 게이트는 여전히 필요하고, 모양은 이렇다: **모델은 raw 2개를 내고, 사람이 보는 4개
(`boxes / classes / scores / num_detections`)는 CPU 후처리(anchor 디코드 + NMS)가 만든다.**
아래 층 A 가 raw 2개, 층 B 가 디코드된 4개를 판정한다. 층 B 의 후처리는 NPU 그래프 밖(CPU)이므로
검출 task 의 종단간 시간 = NPU `run()` + CPU 후처리로 따로 잰다.

## 1. 검출 모델의 "품질 동등성" 정의

분류 게이트(`npu-quality-gate-v1`)를 그대로 쓸 수 없는 이유가 셋이다.

1. 출력이 2개다 — 지금 `runFloat()`은 `outputs[0]`만 읽는다
2. 합성 입력(LCG·coordinate-rgb)은 **검출이 0개**일 가능성이 높다 [E]. "CPU 0개 = NPU 0개"로 PASS가 나면
   MobileNet의 "argmax 전부 112"보다 더 나쁜 거짓 통과다
3. 사용자가 보는 결과는 raw 텐서가 아니라 디코드된 박스다

그래서 **두 층**으로 판정한다. 둘 다 통과해야 PASS.

### 층 A — raw 텐서 (디코드 없이 앱 안에서 계산 가능)

| # | 조건 | 제안값 | 이유 |
|---|---|---|---|
| A1 | `bit_identical_to_cpu == false` (score·location **각각**, 하나라도 전체 비트 동일이면 true) | — | 분류 게이트와 같은 반전 논리. true = CPU로 돈 것 = FAIL |
| A2 | 비유한 값 0개 (두 텐서 모두) | 0 | 팀 계약과 동일 |
| A3 | CPU score 상위 K개 (anchor, class) 쌍과 NPU 상위 K개의 겹침 | K=100, 겹침 ≥ 0.90 | 1.7M 값 전체 cosine은 배경 anchor에 지배돼 변별력이 없다 [E] |
| A4 | 위 CPU 상위 K개 anchor의 location 4값 cosine | ≥ 0.99 | 분류 게이트 cosine과 같은 수준 |

### 층 B — 디코드된 검출 (사용자가 보는 결과)

- 입력: 팀 golden 이미지 `cat_and_dog.jpg` (69,041 B, SHA `cfa90c34…`) [D]. 합성 입력은 층 B에 쓰지 않는다
- 디코드: CPU·NPU raw 출력에 **같은** anchor 디코드 + NMS 적용, score threshold 0.5 (팀 golden과 동일)
- **전제 조건**: CPU 기준에 threshold 이상 검출이 **1개 이상**. 0개면 `NOT_APPLICABLE(inconclusive)` — 절대 PASS 아님

| # | 조건 | 팀 decoded 규칙 (CPU↔GPU) | NPU 제안값 | 차이 이유 |
|---|---|---|---|---|
| B1 | 검출 개수 동일 | 같아야 함 | 같아야 함 | — |
| B2 | label 순서 동일 (score 내림차순 정렬 후) | 같아야 함 | 같아야 함 | — |
| B3 | 짝지은 box 차이 | 좌표 절대차 ≤ 2 px | IoU ≥ 0.90 **그리고** 좌표 절대차 기록 | FP16이라 2 px를 넘을 수 있다 [E]. 넘으면 그대로 보고 |
| B4 | 짝지은 score 차이 | 절대차 ≤ 1e-3 | 절대차 ≤ 1e-2 | FP16 유효자리 ~3자리 → 1e-3은 구조적으로 경계선 [E] |
| B5 | 비유한 값 | 0 | 0 | — |

참고 golden (CPU XNNPACK, MediaPipe Tasks 1.0.1) [D]: cat 0.7803 `(72,162,252,191)`, dog 0.7626 `(303,27,249,345)`.

## 2. 조민규 `combined-tolerance-v1`과의 대응

| `combined-tolerance-v1` (CPU↔GPU) | NPU 검출 게이트 | 관계 |
|---|---|---|
| raw score·location 각각 `atol=1e-4`, `rtol=1e-3`, eps `1e-6` | 층 A (A1~A4) | **대체.** FP16 가중치라 구조적으로 못 넘는다 — 분류 NPU 게이트와 같은 논리 (조민규 PLAN의 "FP32↔INT8 수치 차이는 의도된 것, 티어 간 비교는 품질 지표로만"과 같은 규칙을 정밀도 축에 적용) |
| decoded: count·label 순서·box 2 px·score 1e-3 | 층 B (B1~B5) | **같은 구조, B3·B4만 완화 제안.** 완화 폭은 첫 결과 전에 고정 |
| non-finite 0 | A2, B5 | 동일 |
| comparator ID `combined-tolerance-v1` | **새 ID `npu-detector-quality-v1`** | 같은 이름을 재사용하지 않는다 — 기준이 다르다는 걸 ID로 드러낸다 |

## 3. PART(부분 파티션)일 때 `npu_partial` 증명

> 12:30 결과로 EfficientNet·EfficientDet 둘 다 PASS(1 partition)라 지금은 해당 없다. 다른 모델(SSD MobileNetV2 등)이나
> SDK 가 바뀌어 PART 가 나올 때를 위해 남긴다. `npu_full` 의 증명은 `X == Y` 한 줄이다.

`npu_partial`은 "NPU가 일부를 했다"와 "나머지를 누가 했는지"를 **둘 다** 증명해야 한다. 주장만으로는 `unverified`다.

| 증거 | 출처 | 조건 |
|---|---|---|
| 정적: 파티션 구성 | Colab `aot_manifest.json` `outputs[].operators` | `dispatch_ops ≥ 1` 그리고 `non_dispatch_ops > 0`. 남은 연산자 이름 목록을 결과에 복사 |
| 런타임: NPU가 맡은 노드 | logcat `tflite`: `Replacing X out of Y node(s) with delegate (DispatchDelegate) node, yielding P partitions` | `0 < X < Y` |
| 런타임: 나머지를 맡은 쪽 | logcat `tflite`: `Replacing N out of M node(s) with delegate (TfLiteXNNPackDelegate)` 또는 기본 CPU 커널 | 누가 맡았는지 기록 |
| 정합 | 위 둘 | `X == dispatch_ops` 이고 `Y == dispatch_ops + non_dispatch_ops`. 안 맞으면 `unverified` |
| 폴백 부재 | logcat `litert` | `Failed to create a dispatch delegate kernel` / `No usable Dispatch runtime` **0건**. 있으면 `failed` (전부 CPU로 돈 것) |

추가 규칙:
- 시간은 **전체 서비스 시간으로만** 보고한다. `run()` 한 번 안에서 NPU·CPU 몫을 나눌 수 없다 — "순수 NPU 속도"라 부르지 않는다 (조민규 `gpu_assisted`와 같은 취급)
- 요약 JSON에 `npu_partial_delegation = true`, `dispatch_nodes = "X/Y"`, `cpu_residual_ops = [...]`
- 품질 게이트 A1(비트 비동일)은 partial에서도 유효하다 — NPU 몫이 조금이라도 있으면 FP16 흔적이 남는다 [E]
- PASS(전 그래프)의 증명은 `X == Y` (MobileNet V1: `1 out of 1`, 9/24 실측 [P])

## 4. 구현할 때 필요한 것 (지금 코드와의 차이)

| 항목 | 지금 | 필요 |
|---|---|---|
| 출력 읽기 | `outputs[0]`만 | 전 출력. 타이밍 경계(`latency_ms`의 read)에도 전부 포함 |
| 게이트 입력 | 합성(LCG / coordinate-rgb) | 층 B는 실제 이미지. `cat_and_dog.jpg`를 실행자가 원 URL에서 직접 받아 push |
| 모델 적재 | 기준 모델은 asset만 (`ref_model_asset`) | **EfficientDet 바이너리는 레포·APK 금지** → 후보·기준 모두 `--es model_path` / `ref_model_path`(신규)로 기기 파일에서 연다 |
| 디코드 | 없음 | anchor 생성(19206개) + box decode + NMS. MediaPipe 설정값을 그대로 옮기거나, 앱은 raw 상위 K만 덤프하고 호스트에서 디코드 |
| 다중 출력 안전장치 | **있음 (9/24 오후 추가)** — 출력 ≠ 1이면 게이트 `NOT_APPLICABLE` | 검출 게이트 구현 후 교체 |
| 로그 증거 | 사람이 logcat을 읽음 | `formal_npu_valid`가 `Replacing X out of Y`를 파싱 (tools/d1_logger_v4.py) |

## 5. 영훈이 확정할 것

1. A3의 K와 겹침 비율, B3의 IoU, B4의 score 허용치 — 위 제안값 그대로 갈지
2. 층 B의 디코드를 앱에서 할지 호스트에서 할지
3. comparator ID `npu-detector-quality-v1`을 조민규 계약에 추가 요청할지
