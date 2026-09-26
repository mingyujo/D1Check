# EfficientDet-Lite0 NPU 검출 품질 게이트 — 계약 초안 v2 (2026-09-26, 코드 미구현)

> 상태: **계약 설계 문서만. 코드 없음.** 조민규와 합의할 사안이라 **선택지를 열어 둔다** — 항목마다 선택지·장단점·우리 제안을 적었고, 제안은 확정이 아니다.
> 합의된 값은 **첫 EfficientDet NPU 검출 결과를 보기 전에** 이 문서에 고정하고 커밋 해시를 남긴다. 결과를 본 뒤에는 바꾸지 않는다.
>
> 9/24 초안(top-100 겹침 ≥ 0.90 · IoU ≥ 0.90 · score 차 ≤ 1e-2)은 조민규 지적대로 **계약이 아니었다** — 비교 대상, 매칭 방식, 빈 검출·동점 처리,
> 집계 방식, 기준 출력 생성법이 빠져 있어 두 사람이 같은 데이터로 다른 판정을 낼 수 있었다. 그 값들은 아래 선택지 중 하나로만 남긴다.
>
> 근거 라벨: `[P]` 실측 / `[D]` 문서·코드 근거 / `[E]` 추정

---

## 0. 전제 (확정된 사실)

- 팀 고정 원본: MediaPipe EfficientDet-Lite0 FLOAT32 v1, 13,836,895 B, `40338edf…` [D `MODEL_02_INVENTORY.md` §2]. 입력 `[1,320,320,3]` `(RGB−127.5)/127.5`
- 우리 NPU 실행 파일: AOT `efficientdet_lite0_Samsung_E9965.tflite` 8,799,008 B `f51d082d…` (원본 `40338edf…` 에서 컴파일, 263/263 op → 1 partition, 가중치 FP16 [E]) [P 9/24 G1-B]
- 컴파일본 출력은 **raw 2개**: score `[1,19206,90]`, location `[1,19206,4]`. `TFLite_Detection_PostProcess` 없음 [P]
  → **anchor decode·NMS 는 NPU 그래프 밖, CPU 에서 돈다.** "EfficientDet 전부 NPU" 라고 쓰지 않는다. 종단간 시간 = NPU `run()` + CPU decode/NMS 를 따로 잰다
- 조민규 GPU probe 의 decode [D `ProbeTaskAdapter.kt` `ExplicitDetectionDecoder`]: anchor 별 argmax 클래스 → score ≥ 0.5 → box decode (anchors `e095e869…`)
  → score 내림차순(동점은 anchor index 오름차순) **그리디·클래스 무관 NMS, IoU > 0.3 제거** → (score↓, label, x, y, w, h) 정렬. 개수 상한 없음
- 조민규 decoded 비교 `combined-tolerance-v1` [D `MODEL_02B_PROBE.md`:102, `ModelProbeContract.kt`:366-368]: canonical 정렬 뒤 **개수·label 순서 동일**, 짝지은 box 좌표 절대차 ≤ **2 px**, score 절대차 ≤ **1e-3**, non-finite 0. raw 는 atol 1e-4 · rtol 1e-3 · eps 1e-6

### ⚠️ CPU 출력과의 일치성 ≠ 실제 탐지 정확도

이 게이트는 "NPU 경로가 CPU 기준 경로와 **같은 답**을 내는가"만 본다. **두 경로가 함께 틀려도 서로 잘 일치할 수 있다**
(같은 원본 가중치, 같은 decode, 같은 전처리를 공유하므로 공통 오류는 상쇄된다). 탐지 정확도(GT 대비)는 별도 지표로 CPU·NPU 각각 보고하며,
이 게이트의 PASS 를 "NPU 탐지가 정확하다"로 쓰지 않는다 (§C8).

---

## 계약 항목 C1~C8

### C1. 무엇을 비교하나 — raw anchor vs decode·NMS 이후 검출

| 선택지 | 장점 | 단점 |
|---|---|---|
| **(a) raw 만** (score·location 텐서) | decode 코드 차이가 끼어들지 않는다. NPU 가 실제로 계산한 값 그 자체 | 1.7M 값 대부분이 배경 anchor → 전체 cosine 은 변별력 없음 [E]. 사용자가 보는 결과와 거리가 멀다. FP16 이라 조민규 raw atol/rtol 은 구조적으로 못 넘는다 |
| **(b) decoded 만** | 사용자가 보는 결과. 조민규 GPU decoded 비교와 같은 층 | threshold·NMS 경계에서 작은 raw 차이가 검출 유무로 증폭된다 (C4). decode 가 양쪽 동일해야만 의미 |
| **(c) 둘 다 — decoded 로 판정, raw 는 진단** | 실패 원인을 raw 에서 찾을 수 있다. 판정 층은 하나라 모호하지 않다 | 기록할 것이 늘어난다 |

- 제안: **(c)**. raw 진단 지표(판정 아님): 비유한 0, `bit_identical_to_cpu`(score·location 각각 — true 면 CPU 로 돈 것 = 실행 실패), CPU score 상위 K (anchor, class) 쌍의 NPU 상위 K 겹침률, 그 anchor 들의 location 최대 절대차
- raw 비트 동일 = FAIL 은 분류 게이트와 같은 반전 논리이고 **판정 층과 무관하게** 적용한다 (실행 경로 검증)

### C2. decode·NMS 구현 — 누구의 코드로

| 선택지 | 장점 | 단점 |
|---|---|---|
| **(a) 조민규 `ExplicitDetectionDecoder` 를 그대로 옮김** (같은 anchors `e095e869…`, 같은 상수) | 그의 GPU probe 와 **같은 함수** → CPU/GPU/NPU 결과가 같은 기준에 선다. 순수 함수라 호스트 재현 가능 | MediaPipe Tasks 결과와 바이트 동일하다는 보장은 없다 (golden 과 대조 필요) |
| (b) MediaPipe Tasks `ObjectDetector` | 공식 canonical, golden `83de431d…` 이 이것 | NPU raw 출력을 넣을 수 없다 (모델 실행까지 Tasks 가 한다). 내부 설정이 블랙박스 |
| (c) 앱은 raw 덤프, 호스트(Python)에서 decode | 기기 코드 변경 최소, 재현 쉬움 | 1.7M float × 이미지 수 전송. 기기 종단간 시간에 decode 가 안 들어간다 |

- 제안: **(a)**, 구현 위치는 앱·호스트 중 합의. decode 코드의 해시를 결과에 기록 (`detector_decoder_sha256`)
- 배선 점검(판정 아님): CPU 기준 경로 + (a) decode 로 `cat_and_dog.jpg` 를 돌려 golden(cat 0.7803 `(72,162,252,191)`, dog 0.7626 `(303,27,249,345)`)과 대조. 어긋나면 게이트를 돌리기 전에 멈춘다

### C3. 박스 매칭 방식과 클래스 조건

| 선택지 | 장점 | 단점 |
|---|---|---|
| **(a) 위치 매칭** — canonical 정렬 뒤 i 번째끼리 짝 (조민규 `combined-tolerance-v1`) | 그의 CPU↔GPU 규칙 그대로. 구현 한 줄 | **score 가 비슷한 두 검출의 순서가 FP16 오차로 뒤바뀌면 전부 틀린 짝**이 된다. NPU 에선 드물지 않을 것 [E] |
| **(b) 같은 클래스 안 그리디 IoU 매칭** — CPU 검출을 score 내림차순으로 돌며, 아직 안 짝지은 NPU 검출 중 IoU 최대(≥ 임계) 와 짝 | 순서 뒤바뀜에 강하다. 결정적(동점 규칙 C5). 구현 쉬움 | 붐비는 장면에서 전역 최적이 아닐 수 있다 |
| (c) 같은 클래스 안 헝가리안 (IoU 최대화) | 전역 최적 | 구현·설명 부담. 결과가 (b) 와 다른 건 겹친 박스가 많은 이미지뿐 [E] |

클래스 조건:
- (i) **엄격** — 같은 label 끼리만 매칭 (label 이 다르면 미매칭 2건)
- (ii) 클래스 무관 매칭 후 label 일치율을 별도 지표로 — 원인 진단엔 좋지만 판정이 두 갈래가 된다

- 제안: **(b) + (i)**, 매칭 IoU 임계 선택지 **0.5 / 0.75 / 0.9** — 합의. 짝지은 쌍마다 IoU·좌표 절대차(px)·score 절대차를 **전부 기록**
- (a) 를 쓰면 조민규 GPU 결과와 직접 비교되는 이점이 있으니, (b) 를 판정으로 쓰더라도 (a) 결과를 **보조로 함께 기록**하는 안도 가능

### C4. score threshold · NMS 설정 · top-k

- score threshold: **0.5** (조민규 decoder·golden 과 같음) — 바꿀 이유 없음
- NMS: 클래스 무관 그리디, IoU > **0.3** 제거 (조민규 decoder 와 같음)
- top-k: 조민규 decoder 는 **상한 없음**. 선택지 (a) 상한 없음 — 그와 동일 / (b) 상위 25 또는 100 — 이미지당 비교 비용 제한, 하지만 그와 달라짐. 제안 (a)
- **threshold 경계 문제**: CPU score 0.501 · NPU 0.499 같은 검출은 raw 차이는 미미한데 decoded 에선 "미매칭"이 된다. 선택지
  - (a) 경계 무시 — 엄격. FP16 에서 거짓 FAIL 가능
  - (b) **경계 대역 δ**: 한쪽이라도 score ∈ [0.5−δ, 0.5+δ] 인 미매칭 검출은 "경계"로 따로 세고 판정에서 뺀다. δ 선택지 1e-3 / 1e-2 / 0.05
  - (c) 두 경로에 threshold 를 낮춰(예 0.3) 후보를 넓게 뽑고 매칭한 뒤 CPU score ≥ 0.5 인 것만 판정
  - 제안: **(b), δ = 1e-2** 를 첫 후보로 — 합의 필요. 경계 건수는 항상 보고

### C5. 빈 검출 · 미매칭 · 동점

| 경우 | 제안 처리 |
|---|---|
| CPU 검출 0 · NPU 검출 0 | 그 이미지는 **`inconclusive`** — PASS 로 세지 않는다 (합성 입력 "argmax 전부 112" 같은 거짓 통과 방지). 이미지셋 설계에서 CPU 검출 ≥ 1 인 이미지를 최소 수 이상 확보 |
| CPU 0 · NPU ≥ 1 | NPU 추가 검출(FP) — 경계 대역이 아니면 그 이미지 FAIL |
| CPU 검출 미매칭 | 누락(FN) — 경계 대역이 아니면 FAIL |
| NPU 검출 미매칭 | 추가(FP) — 같음 |
| decode 단계 동점 (같은 score) | anchor index 오름차순 (조민규 decoder 와 같음) |
| 매칭 단계 동점 (IoU 같음) | NPU 쪽 canonical 순위가 앞선 것 |
| 정렬 동점 | score↓ → label → x → y → w → h (조민규 canonical 과 같음) |
| 비유한 값 | 어느 단계든 1개라도 있으면 그 이미지 FAIL (조민규와 같음) |

### C6. 판정 — 이미지별 vs 전체 집계

| 선택지 | 장점 | 단점 |
|---|---|---|
| (a) **이미지별 전부 PASS** 여야 게이트 PASS | 가장 엄격, 조민규 CPU↔GPU 규칙과 같은 성격 | 이미지 하나의 경계 사례가 전체를 떨어뜨린다 |
| (b) **전체 집계 임계** — 모든 이미지를 합친 매칭 재현율·정밀도(CPU 기준) ≥ r, 짝지은 쌍 IoU 중앙 ≥ u, score 절대차 최대 ≤ s | 표본이 크면 안정적 | 특정 이미지의 큰 실패가 평균에 묻힌다 |
| (c) **둘 다**: 이미지 PASS 비율 ≥ p **그리고** 치명 실패(누락/추가가 경계 밖인 검출이 k 개 이상인 이미지) 0 | 균형 | 파라미터가 늘어난다 |

- 제안: **(c)** — p·k·r 은 합의. 항상 보고: 전체 이미지 수, `inconclusive` 수, PASS/FAIL 수, 경계 건수, 매칭 쌍의 IoU·좌표 px·score 차 분포(최대·중앙)
- 이미지별 판정 조건 (선택지 값은 C3·C4 에서): 모든 비경계 검출이 매칭됨, 짝마다 IoU ≥ 매칭 임계, score 절대차 ≤ s_img (선택지 **1e-3**(조민규와 같음) / **1e-2** / **2e-2**). FP16 유효자리 ~3자리라 1e-3 은 구조적으로 경계선 [E]
- 동일 이미지 반복 실행은 **독립 표본이 아니다** — 이미지 수만 표본으로 센다 (조민규 MX §2)

### C7. 대표 이미지셋과 CPU 기준 출력

이미지셋 (**조민규 답장 대기**):
- 라이선스·GT 가 확인된 공개 validation subset (그의 계약: task 별 ≥ 20장·여러 클래스, 개발/평가 분리, 인물·개인정보 기록)
- `cat_and_dog.jpg` (69,041 B `cfa90c34…`) 는 배선 점검용 golden — 평가 표본 수에 넣을지 합의
- 각 이미지 원본 bytes SHA-256 과 전처리 후 입력 텐서 SHA-256 을 기록. **CPU·NPU 에 같은 텐서 바이트**를 넣는다 (한 번 전처리해 두 경로가 공유)
- 이미지는 실행자가 원 출처에서 직접 받는다. EfficientDet 바이너리와 마찬가지로 레포·APK 에 넣지 않는다

CPU 기준 출력 생성 — 선택지:

| 선택지 | 장점 | 단점 |
|---|---|---|
| (a) 원본 FP32 `40338edf…` 를 **기기 CPU, LiteRT 1.4.2 Interpreter**(XNNPACK)로 — 조민규 probe 와 같은 런타임 | 그의 CPU 기준과 같다 | 원본 바이너리를 기기에 반입해야 한다 (외부 manifest 방식) |
| (b) 원본을 **npu-runner CompiledModel CPU** 로 | NPU 와 같은 엔진·같은 앱 | 엔진 대조 +21.4 % 처럼 엔진이 다르면 수치도 조금 다를 수 있다 — 그의 기준과 달라진다 |
| (c) 원본을 **호스트** `ai-edge-litert 2.2.0` CPU 로 | 기기 불필요, 결정적, 조민규 host smoke 와 같은 런타임 | 기기 CPU 결과와 비트 동일 보장 없음 |

- 제안: **(a)** 를 판정 기준으로, (c) 를 재현 점검용으로. 어느 쪽이든 기준 raw 출력 SHA 와 decoded canonical SHA 를 이미지별로 고정해 두고 NPU 실행 전에 커밋
- **NPU 쪽은 AOT FP16 컴파일본, CPU 기준은 원본 FP32** — 이 게이트가 재는 것은 "컴파일·FP16·NPU 실행 전체"의 차이다. 정밀도만의 효과로 쓰지 않는다

### C8. 정확도(GT 대비)는 별도 보고

- 게이트 PASS/FAIL 과 별개로, GT 가 있는 이미지에서 CPU·NPU **각각** 이미지별 검출 재현율·정밀도(IoU ≥ 0.5, 같은 클래스) 를 보고할지 — 합의
- 20장 수준에서 mAP 를 "탐지 정확도" 로 일반화하지 않는다

---

## 판정 결과 형식 (구현 시)

comparator ID: 조민규 `combined-tolerance-v1` 과 이름을 공유하지 않는다 — 제안 `npu-detector-quality-v2` (v1 = 9/24 초안, 폐기).
기록 필드 제안: `comparator_id`, `decoder_sha256`, `anchors_sha256`, `score_threshold`, `nms_iou`, `match_method`, `match_iou`, `class_rule`, `boundary_delta`,
`score_atol_img`, 이미지별 `{image_sha256, input_tensor_sha256, cpu_raw_sha256, npu_raw_sha256, cpu_count, npu_count, matched, fn, fp, boundary, iou_min, px_max, score_diff_max, verdict}`,
집계 `{n_images, n_inconclusive, n_pass, n_fail, n_boundary, pass_rate}`, `bit_identical_to_cpu{score,location}`.

---

## 부록 — PART(부분 파티션)일 때 `npu_partial` 증명 (9/24 초안에서 유지)

> EfficientNet·EfficientDet 은 1 partition(PASS)이라 지금은 해당 없다. SDK·모델이 바뀌어 PART 가 나올 때를 위해 남긴다. `npu_full` 의 증명은 `X == Y`.

| 증거 | 출처 | 조건 |
|---|---|---|
| 정적: 파티션 구성 | AOT `aot_manifest.json` `outputs[].operators` | `dispatch_ops ≥ 1` 그리고 `non_dispatch_ops > 0`. 남은 연산자 이름 목록을 결과에 복사 |
| 런타임: NPU가 맡은 노드 | logcat `tflite`: `Replacing X out of Y node(s) with delegate (DispatchDelegate) node, yielding P partitions` | `0 < X < Y` |
| 런타임: 나머지를 맡은 쪽 | logcat `tflite`: `Replacing N out of M node(s) with delegate (TfLiteXNNPackDelegate)` 또는 기본 CPU 커널 | 누가 맡았는지 기록 |
| 정합 | 위 둘 | `X == dispatch_ops` 이고 `Y == dispatch_ops + non_dispatch_ops`. 안 맞으면 `unverified` |
| 폴백 부재 | logcat `litert` | `Failed to create a dispatch delegate kernel` / `No usable Dispatch runtime` **0건**. 있으면 `failed` |

⚠️ `Replacing … (DispatchDelegate)` 줄은 **dispatch 가 실패해도 찍힌다** (9/24 04:55 진단 로그 766행 → 직후 `Failed to create a dispatch delegate kernel`). 이 줄 하나로 NPU 실행을 판정하지 않는다.
시간은 전체 서비스 시간으로만 보고 ("순수 NPU 속도" 라 부르지 않는다 — 조민규 `gpu_assisted` 와 같은 취급).

## 조민규와 합의할 것 (이 문서의 열린 칸)

1. C1 판정 층 (decoded 판정 + raw 진단 안에 동의하는지)
2. C2 decode 구현 위치 (앱 / 호스트)
3. C3 매칭 방식 (위치 / 그리디 IoU / 헝가리안), 클래스 조건, 매칭 IoU 임계
4. C4 경계 대역 δ, top-k 상한 여부
5. C6 집계 방식과 p · k · r · s_img
6. C7 대표 이미지 목록·SHA, CPU 기준 런타임 (기기 Interpreter 1.4.2 / CompiledModel CPU / 호스트)
7. C8 GT 정확도 별도 보고 여부
8. comparator ID 를 그의 계약(`DECISIONS.md`)에 등록할지
