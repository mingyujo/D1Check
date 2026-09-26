# S26 NPU 정식 측정 결과 — `S26_NPU_formal_0925b`

Galaxy S26 (SM-S942N, Exynos 2600 `s5e9965`) · `--mode formal --resources NPU` · 2026-09-25 01:19 ~ 05:01 (KST)

**20슬롯 전부 완주. `validation.valid` 20/20 (35개 검사), `formal_npu_valid` 20/20, dispatch 증거 verified 20/20, exports-v2 제외 0.**
재시도 1건 (호스트 파일 잠금 — §2).

근거 라벨: [P] 이번 실측 · [D] 기존 문서 값 · [E] 추정·해석. **모든 숫자는 §1 조건에서만 유효하다.**

---

## 1. 실험 설계와 조건

| 항목 | 값 |
|---|---|
| 자원 | NPU (npu-runner, LiteRT **CompiledModel 2.2.0**, `Accelerator.NPU` 단독 — 폴백 나열 없음) |
| 모델 | MobileNet V1 FP32 → AOT `mobilenet_v1_1.0_224_Samsung_E9965.tflite` (`1415b2c8…`, 컴파일러 `2.3.0.dev20260917`, 31/31 op → 1 partition, 가중치 FP16) |
| dispatch | `libLiteRtDispatch_Samsung.so` `f08656a6…` (LiteRT main@9380426b 소스 빌드) |
| 입력 | 합성 LCG `lcg-unit` (`input_sha256 5dc1cb09…`. benchmark-runner 와 비트 동일한 생성기 — [D] `NpuDeterministicInput.kt`, 이 실험 데이터로는 검증 안 됨) |
| 듀티사이클 | 25, 50, 75, 100 % (주기 10 s) |
| 조건 수 · 반복 | 4 조건 × 5 = **20 런**, 블록 내 무작위 (seed **20260910**, CPU/GPU formal 과 같은 seed) |
| 런 구조 | baseline 60 s → warmup 20회 → load 60 s → cooling (`--cooling-policy stable`): 기기 시계 load_end→run_stop **중앙 314.9 s** (184.5~588.3 s) · 호스트 타이머 `actual_duration_s` 중앙 307 s (150~579 s). `FORMAL_RESULTS.md` 의 "142~604 s" 는 기기 시계 기준이므로 비교는 앞의 값으로 |
| 시작 정책 | `--start-policy stable` (AP/BAT/PA/SKIN 60 s 창, 범위 ≤ 0.5 ℃ · 기울기 ≤ 0.2 ℃/분) |
| 정확도 정책 | `required` / scope `backend-performance-formal` / 대표 텐서셋 `d1-imagenette-val40.d1tset` / GPU 프로파일 `gpu-fp32-strict-v1` |
| 연결 · 전원 | **비충전** [P] — 20런 전부 러너 시작 시 `plugged 0`, battery status 3, 모든 텔레메트리 샘플 `plugged 0` · **무선 adb** [관찰] (serial 이 ip:port, USB 미연결 — 데이터로는 간접) |
| 배터리 구간 [P] | 러너 시작 시 **78 % → 60 %** (formal 게이트 30~90 % 안) · 배터리 온도 28.5~31.7 ℃ |
| 시작 온도 [P] | load 시작 시 SKIN **30.3~32.4 ℃**, BAT 28.3~30.9 ℃ · Android thermal status 전 구간 **0** |
| 화면·무선 [관찰 — manifest·메타데이터·logcat 에 없음] | 측정 세션이 00:04 에 읽은 값: 밝기 수동 0(`screen_brightness 0`, mode 0), 비행기 모드 ON + Wi-Fi. `screen_off_timeout 86400000`(23:58 에 600000 에서 변경, 05:05 원복). 러너 Activity 는 `FLAG_KEEP_SCREEN_ON` [D] |
| 총 표본 | thermal 8,532 행 (≈ 2.38 시간) |

명령줄 (`D1Check_v4` 루트에서):

```
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --mode formal --resources NPU --duty-cycles 25 50 75 100 --duration 60 --warmup 20 --repeat 5 --seed 20260910 --accuracy-preflight required --accuracy-validation-scope backend-performance-formal --representative-tensor-set C:\datasets\d1-imagenette-val40.d1tset --gpu-profile gpu-fp32-strict-v1 --accuracy-input-count 32 --accuracy-seed 305419896 --accuracy-atol 0.0001 --accuracy-rtol 0.001 --start-policy stable --cooling-policy stable --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_NPU_formal_0925b
```

`s26\tools\s26_formal.bat`(CPU/GPU 80런)과 비교해 `--resources NPU`, 출력 폴더, 그리고 `--cpu-thread-levels 1 2 4` 가 빠진 것(NPU 에 무의미)만 다르다.

---

## 2. 완주·검증 상태 [P]

```
slot_status                              completed 20
validation_status                        valid     20   (35개 검사 = 33 기본 + formal_energy_eligible + formal_npu_valid)
formal_npu_valid                         True      20 / 20   (9조건 전부 True)
npu_delegate_evidence.verification       verified  20 / 20   (DispatchDelegate 1/1 · 1 partition · ENN SOC=s5e9965 · 실패 문구 0)
model_eligible                           True      20
exclusion_reasons                        []        20
termination_reason                       duration_complete 20
cooling_status                           completed 20 (stable_condition_met)
attempts                                 1회 19 · 2회 1
npu_quality_preflight                    passed  (bit_identical 0/32 · argmax 32/32 · cosine_min 0.99971543 · cosine_mean 0.99994283)
accuracy_preflight (benchmark-runner)    passed
  synthetic_numerical_check              passed  (mismatch 0, non-finite 0)
  representative_input_equivalence       passed  (mismatch 0)
  task_accuracy_check                    passed  (Top-1 0.75 / Top-5 0.95, 델타 0.0 / 0.0)
energy_measurement_status                raw_unverified 20
```

- `experiment_manifest.json` sha256 `ac9729f768eb461dfe4438376cec0b3e488f1765ec2283237365c10325d22cd2`
- **재시도 1건**: `npu-d075-r003` 1차 시도가 **냉각 단계**에서 `PermissionError [WinError 5]` (manifest 원자 교체 실패)로 멈췄다.
  러너는 이미 정상 종료. 원인은 호스트 쪽 파일 잠금 — 측정 세션의 감시 스크립트가 manifest 를 주기적으로 열어 읽은 것과 겹친 것으로 보인다 [E].
  `--resume` 으로 같은 폴더에서 재개, 2차 시도 완주. 1차 시도 run 폴더 `runs\2fb5adc4-…` 는 20개 런에 들지 않는다 (분석 제외 —
  manifest 에는 그 슬롯의 `failures[0].run_id` 로만 남아 있다)
- `FORMAL_RESULTS.md` §2 는 CPU/GPU 가 "33개 검사" 라고 적었지만 그 manifest 의 실제 검사 수는 CPU 34 · GPU 35 다 (그 문서의 표기 문제, 이번 판정과 무관)
- ⚠ `accuracy_preflight` 는 **benchmark-runner 의 CPU↔GPU** 검사다. NPU 품질은 `npu_quality_preflight` 가 따로 본다.
  exports-v2 `run_summary.csv` 의 `accuracy_preflight_status` 열은 앞의 것이다 (NPU 게이트 아님)

---

## 3. 지연 — 조건별 중앙값 (ms, 5반복의 중앙값) [P]

npu-runner 지연 span = **write + run + read** (입력 복사·출력 읽기 포함). 러너당 전체 inference 이벤트.

| duty | median | 5런 median | p95 (5런 중앙) | CV (5런) | 60 s 당 추론 수 |
|---|---|---|---|---|---|
| 25 | **0.749** | 0.746 · 0.749 · 0.755 · 0.750 · 0.747 | 1.083 | 0.41 % | 17,359~18,142 |
| 50 | **0.746** | 0.746 · 0.747 · 0.742 · 0.743 · 0.748 | 1.023 | 0.34 % | 36,193~37,564 |
| 75 | **0.746** | 0.746 · 0.747 · 0.745 · 0.744 · 0.749 | 1.009 | 0.25 % | 55,632~56,075 |
| 100 | **0.743** | 0.745 · 0.746 · 0.740 · 0.743 · 0.742 | 0.989 | 0.26 % | 75,507~76,170 |

**NPU 지연은 duty 에 둔감하다** (0.743~0.749 ms, 차이 < 1 %). 60 s·duty 100 에서도 **지연이 늘지 않았다** (d100 처음 10 s ≈ 0.743~0.750, 마지막 10 s ≈ 0.730~0.742 ms).
Android thermal status 는 전 구간 0 이지만 거친 지표이고 NPU devfreq 는 읽기 권한이 없어, "스로틀 없음" 이 아니라 **"성능 저하 없음"** 까지만 말할 수 있다.

### 3.1 CPU/GPU 와 나란히 (조건 다름 — 각주 필수)

| 자원 | 엔진 | duty 25 | duty 50 | duty 75 | duty 100 | 출처 |
|---|---|---|---|---|---|---|
| CPU 4 스레드 | Interpreter 1.4.2 | 3.897 | 3.904 | 4.096 | 4.370 | [D] `FORMAL_RESULTS.md` §3 (2026-09-13~14) |
| GPU | Interpreter 1.4.2, `gpu-fp32-strict-v1` | 3.669 | 3.660 | 3.641 | 3.636 | [D] 같은 곳 |
| **NPU** | **CompiledModel 2.2.0** | **0.749** | **0.746** | **0.746** | **0.743** | [P] 이 문서 |

> **표기 규칙 (2026-09-26 사후 증거 감사)**: 판정·기준·수치를 바꾼 곳은 `~~이전 판: 원문~~` → `[2026-09-26 사후 증거 감사] 새 판 (근거)` 형식이다.
> 표를 통째로 바꾼 곳은 이전 표 원문을 **취소 표시된 코드 블록**으로 남겼다 (표 안 취소선은 렌더가 깨지므로). 이 감사는 수집 당시의 사전 기준이 아니며 기존 판정을 대체하지 않는다.

~~이전 판 (e27f907, 2026-09-26 1차): 정밀도 2열 표 (저장 / 연산)~~ — 원문 그대로:

```text
**정밀도 — 모델 저장 정밀도와 실제 연산 정밀도를 따로 적는다** (2026-09-26 추가. 조민규 지적: 저장 형식이 연산 형식을 보증하지 않는다)

| 자원 | 모델 파일 | 크기 · SHA | 저장 정밀도 | 연산 정밀도 |
|---|---|---|---|---|
| CPU 4 스레드 | `mobilenet_v1_1.0_224.tflite` | 16,901,128 B · `d95b3c5e…` | FP32 [P 파일] | **미확인** (Interpreter 1.4.2 + XNNPACK. FP16 강제 옵션은 코드에 없음 [D] — 실제 커널 정밀도는 API 가 노출하지 않음) |
| GPU | 같은 파일 | 같음 | FP32 [P 파일] | **미확인** — 설정은 `precision_loss_allowed=false` [D `GpuDelegateProfile.kt`], 러너 스스로 `actual_fp16_execution = unknown_not_exposed_by_litert_api` 로 기록. 간접 근거: CPU 대비 최대 총변동 3.8e-6 (A24, `A24_S26_COMPARISON.md`:202) |
| NPU | AOT `mobilenet_v1_1.0_224_Samsung_E9965.tflite` | 8,901,712 B · `1415b2c8…` (원본 `d95b3c5e…` 에서 컴파일) | **FP16 [E]** — 원본 대비 정확히 1/1.90 크기, 9/24 G4 top5 점수가 전부 FP16 표현값 [D]. 벤더 blob 내부 형식은 직접 확인 안 함 | **미확인** — `npu_precision = fp16(compiler-default)` 는 러너가 적는 **가정값**이다 (`NPU_ACCESS_PLAN_0916.md`:115-117 이 사전에 FP16 으로 못 박음). 컴파일 로그·ENN 로그에 연산 정밀도 명시 없음 |

→ **CPU·GPU 는 FP32 모델, NPU 는 FP16 가중치 모델이다. 같은 모델의 자원 비교가 아니다.**
A24 에서 GPU fp16 허용만으로 25 % 빨라진 실측이 있다 (`A24_S26_COMPARISON.md`:200-205) — 정밀도 하나만으로도 배율에 들어갈 크기다.
```

→ [2026-09-26 사후 증거 감사] 정밀도를 **4항목**으로 나눈다 (조민규 지적: FP16 가중치나 출력 dtype 만으로 내부 연산·누산 정밀도를 확정하지 않는다).
(근거: 텐서 dtype 은 flatbuffer 를 직접 읽은 스크래치 계산 [P], 설정은 코드 [D], 로그는 NPU 20런 캡처 `litert`/`tflite` 줄 [P])

| 자원 | ① 모델 저장 정밀도 | ② 입출력 dtype | ③ 설정한 실행 옵션 | ④ 확인된 내부 연산·누산 정밀도 + 근거 |
|---|---|---|---|---|
| CPU 4 스레드 | FP32 [P] — `mobilenet_v1_1.0_224.tflite` 16,901,128 B `d95b3c5e…`, 텐서 89개 중 FLOAT32 88 · INT32 1 (flatbuffer 직접 읽음) | 입력 FLOAT32 `[1,224,224,3]` / 출력 FLOAT32 `[1,1001]` [P 파일] · 러너가 실행 전 `DataType.FLOAT32` 검사 [D `GpuBenchmarkEngine.kt`:318-324] | LiteRT Interpreter 1.4.2, 스레드 4 (`cpu_threads=4`), XNNPACK delegate (캡처 로그 `Replacing N out of N … (TfLiteXNNPackDelegate)` [P]). FP16 허용 옵션 설정 코드 없음 [D] | **unknown** — XNNPACK 은 커널 정밀도를 로그·API 로 내놓지 않는다. 캡처 `tflite` 3줄에 정밀도 정보 없음 |
| GPU | CPU 와 같은 파일 — FP32 [P] | CPU 와 같음 [P 파일, D 검사] | TfLiteGpuDelegateV2, `gpu-fp32-strict-v1`: `precision_loss_allowed=false`, `FAST_SINGLE_ANSWER`, backend UNSET [D `GpuDelegateProfile.kt`] | **unknown** — 러너 스스로 `actual_fp16_execution = unknown_not_exposed_by_litert_api` 를 기록한다 [D]. 캡처 `tflite` 6줄(OpenCL 로드·커널 1개 생성)에 정밀도 정보 없음. 간접: A24 에서 CPU 대비 최대 총변동 3.8e-6 (`A24_S26_COMPARISON.md`:202 — **S26 아님**) |
| NPU | **FP16 [E] 추정** — AOT `mobilenet_v1_1.0_224_Samsung_E9965.tflite` 8,901,712 B `1415b2c8…` 의 flatbuffer 텐서는 입출력 2개뿐이고 가중치는 벤더 bytecode(8,900,608 B, `litert` 로그)에 들어 있어 **형식을 읽을 수 없다**. 근거는 원본 대비 1/1.90 크기뿐 | 입력 FLOAT32 `[1,224,224,3]` / 출력 FLOAT32 `[1,1001]` [P, AOT flatbuffer 직접 읽음] · 러너는 `writeFloat`/`readFloat` [D] | LiteRT CompiledModel 2.2.0 `Accelerator.NPU` 단독 [D]. AOT 컴파일러 `ai_edge_litert 2.3.0.dev20260917` + `sdk_samsung` 같은 버전, 컴파일 옵션 기록 없음 [D `aot_manifest.json`]. ENN `SetGenAiPerfConfigFromSoc: mode=7, configId=0` [P 로그 — 성능 모드 값이며 정밀도 표기 아님] | **unknown** — AOT 매니페스트·컴파일 보고·ENN `litert` 24줄 어디에도 연산·누산 정밀도 필드가 없다. 단서만 있다: 9/24 G4 스모크에서 NPU top5 점수 5개가 전부 FP16 으로 정확히 표현되는 값 [D `G4_VERDICT_0924.md`:42] → **출력 경로 어딘가에 FP16 반올림이 있다**는 흔적이지 내부 누산 정밀도의 증거는 아니다 |

- **`npu_precision = fp16(compiler-default)` 는 러너가 적는 가정값이다** (`NpuRunMetadata.kt`:135 상수. `NPU_ACCESS_PLAN_0916.md`:115-117 이 사전에 FP16 으로 정했다). 측정된 값이 아니다
- 같은 방식으로 EfficientNet AOT (`311e4aac…`) 도 입출력 FLOAT32 `[1,224,224,3]`/`[1,1000]`, 텐서 2개 [P]

~~이전 판: → **CPU·GPU 는 FP32 모델, NPU 는 FP16 가중치 모델이다. 같은 모델의 자원 비교가 아니다.**~~
→ [2026-09-26 사후 증거 감사] **CPU·GPU 는 FP32 저장 모델, NPU 는 저장 정밀도가 FP16 으로 추정되는 AOT 산출물이다. 연산 정밀도는 세 자원 모두 확인되지 않았다. 같은 모델 바이트의 자원 비교가 아니다.** (근거: 위 4항목 표)
A24 에서 GPU fp16 허용만으로 25 % 빨라진 실측이 있다 (`A24_S26_COMPARISON.md`:200-205) — 정밀도 설정 하나만으로도 배율에 들어갈 크기다.

**각주 (반드시)**
1. **엔진이 다르다.** 같은 CompiledModel 로 CPU 를 돌리면 Interpreter CPU4 보다 **21.4 % 느리다** (npu-runner CPU `run()` span 3런 중앙 5.303 ms vs 4.370 ms,
   사전 기준 "≤ 5 % 면 무시" 초과 → 이 각주). 조건: 스모크 경로 56.5~58.7 s 연속, 배터리 82~83 %, 각 런 전 온도 안정 대기
   (세션 로그 기준 98~264 s — 스모크 로그에는 시작 직전 스냅샷 하나만 있다). 스레드 수는 LiteRT 기본값(미확인).
   근거 `SMOKE_cpu_engine60_r{1,2,3}_20260925_*.json`
2. **span 이 다르다.** Interpreter = `interpreter.run()` 만 (`MEASUREMENT_DEFINITION.md`:57-62), NPU = write+run+read. NPU 쪽이 불리하게 잰 것
3. ~~이전 판 (e27f907): **정밀도가 다르다** (위 정밀도 표). CPU·GPU = FP32 모델, NPU = FP16 가중치 AOT 산출물~~
   → [2026-09-26 사후 증거 감사] **저장 정밀도가 다르고, 연산 정밀도는 확인되지 않았다.** CPU·GPU = FP32 저장, NPU = FP16 저장 [E 추정] (근거: 4항목 표)
4. ~~이전 판 (3521b9b, 9/25 원문): 3. 배율 [E]: Interpreter CPU4 대비 duty 100 에서 **5.9×** (4.370/0.743), GPU 대비 **4.9×**.
   **같은 엔진·같은 span** 비교: CompiledModel CPU write+run+read 3런 중앙 **5.339 ms** (5.525 · 5.339 · 5.276) vs NPU 0.743 ms → **7.2×**
   (단 CPU 쪽은 스모크 경로 연속 실행, NPU 는 timed run duty 100 — 프로토콜이 다르다)~~
   ~~이전 판 (e27f907, 1차 감사): 섞인 요소 "자원 + 엔진 + span + 정밀도" / 7.2× "자원 + 정밀도(… NPU 는 FP16 AOT) + 프로토콜"~~
   → [2026-09-26 사후 증거 감사] 배율 [E] — **전부 "해당 구성에서 관측된 복합 성능 차이"이다. 어느 한 요소(자원)의 효과도, 다른 효과의 상한도 아니다.** (근거: 엔진 대조 CPU 스모크 3런 `model_sha256 = d95b3c5e…` [P], 4항목 표)
   - Interpreter CPU4 대비 duty 100 에서 **5.9×** (4.370/0.743), GPU 대비 **4.9×** — 섞인 요소: **자원 + 엔진 + span + 저장 정밀도** (+ 날짜·배터리·밝기, 각주 5)
   - CompiledModel CPU write+run+read 3런 중앙 **5.339 ms** (5.525 · 5.339 · 5.276) vs NPU 0.743 ms → **7.2×** — 엔진·span 은 같지만
     섞인 요소: **자원 + 저장 정밀도(CPU 쪽은 원본 FP32 `d95b3c5e…`, NPU 는 FP16 추정 AOT) + 프로토콜**(CPU 는 스모크 경로 연속 실행, NPU 는 timed run duty 100). 연산 정밀도 차이 여부는 unknown
5. 날짜·배터리 구간·화면 밝기가 다르다 — CPU/GPU 는 **KST 9/14 00:38 → 9/15 07:44** (UTC 9/13~14), 시작 90 % 부근 → 30 % 게이트 중단 → 85 % 에서 재개.
   밝기는 `s26\device\13_display_state.txt` 의 원시값 91 (0~255, 9/14 00:26 KST 한 번 기록 — 80런 전체 기록 아님) [D]

---

## 4. 열 — load 구간 온도 상승분 (조건별 중앙값, ℃) [P]

| 자원 | duty | AP | BAT | SKIN | 냉각 후 AP 잔열 | 출처 |
|---|---|---|---|---|---|---|
| NPU | 25 | +2.40 | +0.90 | +1.30 | +0.40 | [P] |
| NPU | 50 | +4.30 | +1.70 | +2.10 | +0.60 | [P] |
| NPU | 75 | +5.60 | +2.20 | +2.90 | +0.80 | [P] |
| NPU | 100 | **+8.00** | **+3.30** | **+4.00** | +0.90 | [P] |
| CPU 4 스레드 | 100 | +13.70 | +4.40 | +5.60 | +1.20 | 9/13~14 `S26_formal_strict\exports-v2\run_summary.csv` 에서 **이번에 재계산** (cpu-t04-d100, 5런, load 시작 SKIN 29.7~30.9 ℃) |
| CPU 1·2·4 통합 | 100 | +14.10 | +4.60 | +5.90 | +1.50 | [D] `FORMAL_RESULTS.md` §7 (그 표의 CPU 행은 스레드 통합 15런 — 재계산으로 확인) |
| GPU | 100 | +11.70 | +4.10 | +5.50 | +1.30 | [D] 같은 곳 (재계산 값 동일) |

- 60 s 동안 NPU 는 CPU4 의 **약 5.5 배** 추론(≈ 76k vs ≈ 13.7k = 60 s / 4.37 ms)을 하면서도 AP 상승은 CPU4 의 **58 %**, SKIN 은 **71 %** [E 해석]
- NPU 런의 load 시작 SKIN(30.7~32.3 ℃, duty 100)이 CPU4 런(29.7~30.9 ℃)보다 약 1 ℃ 높았다 — 시작 온도를 공변량으로 볼 것 (`MEASUREMENT_DEFINITION.md`:284)
- 듀티는 **시간 기준**이다. "같은 작업량" 비교가 아니라 "같은 점유 시간" 비교임을 명시할 것

### 4.1 RC 1차 지수 피팅 τ (조건별 5런 중앙값) — 방법 [E]

기존 표(`A24_S26_COMPARISON.md` §3.3)를 만든 스크립트를 찾지 못해 **재구현**했다 (τ 상한 3000 s, load 구간 가열 `T0+ΔT(1−e^(−t/τ))`, cooling 구간 냉각 `T∞+ΔT·e^(−t/τ)`).
재구현을 CPU/GPU 80런에 돌리면 SKIN 가열 13~40 s(문서 17~48), SKIN 냉각 60~118 s(문서 50~116), AP 가열 3~19 s(문서 4~20), AP 냉각 29~61 s(문서 31~80) —
~~이전 판 (3521b9b): 범위 끝에서 **17~24 % 낮게** 나오고, CPU 의 AP 가열 피팅은 조건별 R² 중앙이 0.21~0.81 로 나쁘다. **같은 방법이라고 볼 수 없다.**~~
→ [2026-09-26 사후 증거 감사] 범위 끝에서 **−25~+20 %** 어긋난다 (SKIN 냉각 하단은 60 vs 50 s 로 오히려 높다). CPU 의 AP 가열 피팅은 조건별 R² 중앙이 0.21~0.81 로 나쁘다. **같은 방법이라고 볼 수 없다.**
  (근거: 재구현 범위와 문서 범위의 끝값 비 — SKIN 가열 13/17·40/48, SKIN 냉각 60/50·118/116, AP 가열 3/4·19/20, AP 냉각 29/31·61/80. 재구현은 `s26\tools\s26_thermal_fit.py` 로 커밋되어 이 절의 NPU τ 를 그대로 재현함)
이 표의 NPU τ 는 기존 A24/S26 τ 표와 **직접 비교하지 말고**, 같은 재구현으로 CPU/GPU 를 다시 낸 값(위 범위)과만 비교할 것.

| 센서 | duty 25 | duty 50 | duty 75 | duty 100 | R² 범위 |
|---|---|---|---|---|---|
| SKIN 가열 τ | 46.9 s | 45.5 s | 47.6 s | 68.7 s | 0.96~0.97 |
| SKIN 냉각 τ | 77.7 s | 84.9 s | 90.4 s | 113.6 s | 0.95~0.97 |
| AP 가열 τ | 25.0 s | 26.4 s | 33.7 s | 35.1 s | 0.95~0.97 |
| AP 냉각 τ | 56.9 s | 55.3 s | 46.7 s | 63.2 s | 0.92~0.94 |
| BAT 가열 τ | 상한(3000) 4/5 | 455 s | 상한 4/5 | 2345 s | — — 60 s 안에 포화가 안 보임 → **식별 불가** |
| BAT 냉각 τ | 147 s | 139 s | 144 s | 165 s | 0.97~0.99 |

### 4.2 load 60 s 끝의 정상상태 점검 — 2026-09-26 (100런 = CPU/GPU 80 + NPU 20) [P]

> **이 절은 2026-09-26 사후 증거 감사다. 수집 당시의 사전 기준이 아니며, 기존 판정을 대체하지 않는다. 새 기준의 사전 동결은 이후 수집부터 적용한다.**

기준은 계산 전에 고정했다 (`D1_ondevice\작업결과_0926_대기중.md` 7단계, 18:41 KST): load_relative_s 40~60 s 의 OLS 기울기 조건 5런 중앙 |·| ≤ **0.2 ℃/min**
(orchestrator `stable` 의 기존 기울기 한도) **그리고** 가열 피팅 60 s 도달률 1−e^(−60/τ) ≥ 0.95. 스크립트 `s26\tools\s26_thermal_fit.py`.

| 자원 | duty | SKIN 상승 ℃ | SKIN 끝 기울기 ℃/min | SKIN 도달률 | AP 상승 ℃ | AP 끝 기울기 ℃/min | AP 가열 R² | 판정 |
|---|---|---|---|---|---|---|---|---|
| NPU | 25 / 50 / 75 / 100 | 1.3 / 2.1 / 2.9 / 4.0 | 0.95 / 1.05 / 1.88 / 3.09 | 0.72 / 0.73 / 0.72 / 0.58 | 2.4 / 4.3 / 5.6 / 8.0 | 1.3 / 1.7 / 2.4 / 5.1 | 0.95~0.97 | 미도달 |
| GPU | 25 / 50 / 75 / 100 | 1.5 / 2.8 / 4.2 / 5.5 | 0.95 / 1.67 / 2.83 / 3.47 | 0.88 / 0.81 / 0.81 / 0.82 | 2.6 / 6.7 / 9.1 / 11.7 | 1.1 / 2.4 / 6.1 / 4.8 | 0.89~0.98 | 미도달 |
| CPU4 | 25 / 50 / 75 / 100 | 2.8 / 4.8 / 5.4 / 5.6 | 1.83 / 2.90 / 1.97 / 1.40 | 0.79 / 0.88 / 0.97 / 0.99 | 5.5 / 9.5 / 13.6 / 13.7 | −1.1 / 5.0 / 6.4 / −1.3 | 0.23~0.78 | 미도달 |

(값은 조건별 5런 중앙. 피팅 MAE 는 SKIN 0.06~0.20 ℃, AP 0.11~3.0 ℃ — CPU AP 는 duty 사각파를 1차 지수가 못 따라가 MAE 가 크다)

- **SKIN: 20조건 전부 미도달** (끝 기울기 0.95~3.47 ℃/min, 개별 런 0/100 통과)
- **AP: 20조건 중 2개(CPU1 d25, CPU2 d25)만 두 기준 통과** — 그 둘의 AP 가열 R² 는 0.21·0.26 이라 도달률 자체가 약한 피팅에서 나온 값이다. 개별 런 3/100
- → **정상상태 미도달 — 시정수 기반 외삽 필요.** duty 4점 회귀로 `gain_c_per_w` 를 **산출하지 않는다**
  (60 s 끝의 온도 상승은 정상상태 상승이 아니라 "60 s 시점의 과도 응답"이다. 이를 전력으로 나누면 이득이 아니라 시간 의존 값이 된다)
- 보고는 ℃ 상승량·MAE(℃)로 한다. 섭씨 MAPE 는 영점 의존이라 쓰지 않는다

---

## 5. 에너지 — 잠정치 (논문에 쓰지 말 것) [E]

> **이 절의 2026-09-26 추가분(판정 인용·idle 정정·⁽ⁱ⁾·분모 대조)은 2026-09-26 사후 증거 감사다. 수집 당시의 사전 기준이 아니며, 기존 판정을 대체하지 않는다. 새 기준의 사전 동결은 이후 수집부터 적용한다.**

`s26\tools\s26_energy.py` (추적 안 됨, `_if_uA` 가정) — **단위 검증 허용오차가 사전에 문서화돼 있지 않아 잠정**이다.

> **2026-09-26 판정 (사후 등록 — 사전 등록 아님, `docs\MEASUREMENT_DEFINITION.md` §10)**:
> ① 단위 µA·방전 음수 **PASS** · ② 내부 일관성 NPU **PASS**(−2.3 % ≤ ±5.4 %) / CPU·GPU **FAIL**(−7.2 % > ±2.6 %) · **절대 정확도는 두 세션 모두 미인증** ·
> ③ NPU↔CPU4/GPU d100 차이(−88 %/−84 %)는 세션 간 기준 20 % 를 넘어 **구분됨**, NPU duty 간 차이는 **구분 안 됨**. 아래 표는 이 조건으로만 인용한다

| 항목 | NPU 20런 (이번) | CPU/GPU 80런 (같은 스크립트, 참고) |
|---|---|---|
| 전류 적분 / charge counter 비율 (전체) | **0.977** (−2.3 %) · 런별 0.80~1.13, 중앙 0.991 | 0.928 (−7.2 %) · 런별 0.70~1.18 |

| 자원 | duty | load W | idle W | net mJ/추론 ⁽ⁱ⁾ |
|---|---|---|---|---|
| NPU | 25 | 1.648 | 0.627 | 3.18 |
| NPU | 50 | 2.843 | 0.533 | 3.98 |
| NPU | 75 | 4.119 | 0.561 | 3.73 |
| NPU | 100 | 5.120 | 0.563 | **3.53** |
| CPU 4 | 100 | 7.259 | 0.537 | 28.58 |
| GPU | 100 | 6.457 | 0.436 | 21.88 |

- [E] 잠정치 기준 NPU 는 추론당 CPU4 의 약 1/8, GPU 의 약 1/6. **허용오차를 먼저 정하고** 이 표를 판정할 것.
  ~~이전 판 (e27f907): 이 배율도 §3.1 과 같이 **자원 + 엔진 + 정밀도(FP16 vs FP32) + 세션 복합**이다~~
  → [2026-09-26 사후 증거 감사] 이 배율도 §3.1 과 같이 **자원 + 엔진 + 저장 정밀도(FP16 추정 vs FP32) + 세션 복합**이다. 연산 정밀도는 확인되지 않았다 (근거: §3.1 4항목 표)
- load W 는 전체 기기 전력(화면 포함)이다. NPU 단독 전력이 아니다
- ~~이전 판 (3521b9b): load W 는 전체 기기 전력(화면 포함)이다. NPU 단독 전력이 아니다. idle W 비교는 화면 밝기 차이(NPU 세션 0 [관찰] vs CPU/GPU 91 [D])로 오염돼 있다~~
  → [2026-09-26 사후 증거 감사] 이 설명은 데이터와 맞지 않는다.
  d100 idle W 는 NPU 0.563 > CPU4 0.537 > GPU 0.436 으로 **밝기 0 인 NPU 세션이 오히려 높고**, 같은 세션 안 CPU4↔GPU 도 0.10 W 다르다.
  런별 idle W 는 세션마다 0.38~0.89 W 로 흩어지고 세션 중앙은 NPU 0.562 · CPU 0.593 · GPU 0.587 W 로 거의 같다 [P, 이번 재계산].
  → **idle 기준선은 세션 간 비교 불가 — 원인 미확인.** (런 사이 변동이 세션 차이보다 크다. 밝기 가설은 방향이 반대라 근거로 쓰지 않는다)
- ⁽ⁱ⁾ **net mJ/추론 = (load W − idle W) × load 시간 / 추론 수** 라서 위 idle 기준선에 의존한다 — 같은 각주: **기준선 세션 간 비교 불가 — 원인 미확인.**
  민감도 [P, 이번 재계산, d100 5런 중앙]: idle 을 100런 합동 중앙 0.581 W 로 바꾸면 NPU 3.52 · CPU4 29.10 · GPU 21.14 mJ,
  idle 을 빼지 않은 gross 는 NPU 3.97 · CPU4 31.63 · GPU 23.23 mJ → 헤드라인 1/8 은 **1/8.0~1/8.3** 범위로 유지 (load W 가 idle 의 9~13 배라서).
  단 이것은 기준선 선택에 대한 민감도일 뿐, 절대 에너지 정확도(`docs\MEASUREMENT_DEFINITION.md` §10)와는 별개다
- **분모 대조 (2026-09-26) [P]**: `s26_energy.py` 의 `inferences` = `merged/events.jsonl` 의 inference 줄 수. 20런 전부
  **merged = 러너 JSONL(`gpu/*.jsonl`) = `run_summary.completed_inference_count`** 로 정확히 일치 (결손 0).
  merged 는 logcat 이 아니라 러너 JSONL 에서 만들어지므로 §8 의 logcat D1GPU 사본 결손(77.9~99.9 %)은 mJ/추론 분모에 영향 없다. 재계산 불필요
- 에너지 출력은 스크래치패드 CSV — 원시 실험 폴더에는 쓰지 않았다 (`-o` 지정)

---

## 6. NPU 실행 증거 — 무엇이 직접이고 무엇이 간접인가

| 증거 | 종류 | 결과 |
|---|---|---|
| `Replacing 1 out of 1 … (DispatchDelegate) … 1 partitions` | 간접 (실패해도 찍힘) | ~~이전 판: 20/20~~ → [2026-09-26 사후 증거 감사] **수집된 캡처 범위 안에서** 20/20. 캡처 필터(`D1CHECK_EVENT:I D1GPU:I tflite:I TfLite:I litert:I *:S`) 밖과 사본 결손 구간은 판단 불가 (§6.1) |
| ENN `SetGenAiPerfConfigFromSoc: SOC=s5e9965` + 실패 문구 0 | 간접 (런타임 로드) | ~~이전 판: 20/20~~ → [2026-09-26 사후 증거 감사] 로드 줄 20/20, 실패 문구는 **수집된 캡처 범위 안에서 0** — "실패 문구" = 로거 목록 `NPU_DISPATCH_FAILURE_RE` 8종 기준. 일반 grep(fail/error 등)으로는 런마다 `Header verification failed - using old format` 1줄이 있다 (G4 성공 런에도 있던 줄, 영향 미확인 [E]). 캡처 필터 밖·`litert` V/D 레벨·사본 결손 구간은 판단 불가 (§6.1) |
| dispatch·ENN 줄과 D1GPU 이벤트가 같은 PID (= timed run 프로세스) | 간접 | **formal 20/20** (캡처된 logcat 줄 기준) |
| 비트 비동일 + cosine 0.9997 | 간접 (CPU 가 아님) | preflight PASS [P]. "top5 가 FP16 표현값" 은 9/24 G4 스모크 관찰 [D] — 이번 preflight 기록엔 top5 가 없다 |
| 지연 0.743 ms vs 같은 엔진·같은 span CPU 5.339 ms, GPU 3.636 ms | 간접 (성능 격차) | [P]/[D] |
| 앱 프로세스의 `/dev/npu*` fd | 직접 | **없음** — 00:01 스모크(40,000회) 중 조사, formal 중에는 조사 안 함. 앱에 `vendor.samsung_slsi.hardware.enn_aidl-V1-ndk.so` 가 로드돼 있고 HAL 서비스가 존재하므로 ENN 이 AIDL HAL 을 거친다고 **추정** [E]. HAL 프로세스 fd 는 루트 필요 → **미확인** (`NPU_DEVICE_FD_PROBE_0925_NOT_FOUND.txt`) |

### 6.1 실행 증거 3분법 — 런별 (NPU 20런)

> **이 절은 2026-09-26 사후 증거 감사다. 수집 당시의 사전 기준이 아니며, 기존 판정을 대체하지 않는다. 새 기준의 사전 동결은 이후 수집부터 적용한다.**

판정 기준은 계산 전에 고정했다 (`D1_ondevice\작업결과_0926_2차.md` 첫 절, 20:56 KST). 요지:
- **① 실행 성공·유효 출력** — logcat 과 무관. `slot_status completed` · `validation valid` · `termination duration_complete` · 추론 수 > 0 이고 러너 JSONL 과 같음 · 세션 `npu_quality_preflight passed`
- **② 자원·fallback 증거 충분** — `npu_delegate_evidence.verification = verified`(DispatchDelegate 1/1 = AOT manifest, ENN 로드 줄, `NPU_DISPATCH_FAILURE_RE` 0) **그리고** 증거 줄 PID = D1GPU PID
- ① PASS + ② 불충분 이면 "실행은 성공, 자원 판정은 증거 부족" (실패·부적격 아님)

**D1GPU 보존율의 정의** [P, 1-1 재계산]: 분자 = 캡처 `raw\logcat.txt` 의 D1GPU 태그 줄 수, 분모 = 러너 `gpu\*.jsonl` 줄 수(모든 이벤트).
이 정의로 `§8` 의 77.9~99.9 % · 전체 98.8 % 가 재현된다 (inference 이벤트만 세도 같은 값). 100 % 미만 런 수는 13 (문서의 11 은 재현 안 됨).
**`tflite`·`litert` 태그에는 분모가 없다** — "몇 줄이 나왔어야 하는지"의 기준 기록이 없다. 런마다 `tflite` 3줄·`litert` 24줄로 일정하지만 이것은 완전성의 정황일 뿐이다 [E].
**따라서 이 두 태그에 대한 "실패 문구 0" 은 캡처된 줄 안의 주장이지 전체 구간 주장이 아니다.**

| 런 | ① 실행·출력 | ② 자원 증거 | D1GPU 보존율 |
|---|---|---|---|
| npu-d025-r001 | PASS | 충분 | 98.5 % |
| npu-d025-r002 | PASS | 충분 | 93.7 % |
| npu-d025-r003 | PASS | 충분 | 100.0 % |
| npu-d025-r004 | PASS | 충분 | 97.8 % |
| npu-d025-r005 | PASS | 충분 | 77.9 % |
| npu-d050-r001 | PASS | 충분 | 94.8 % |
| npu-d050-r002 | PASS | 충분 | 99.7 % |
| npu-d050-r003 | PASS | 충분 | 96.3 % |
| npu-d050-r004 | PASS | 충분 | 99.9 % |
| npu-d050-r005 | PASS | 충분 | 99.9 % |
| npu-d075-r001 | PASS | 충분 | 100.0 % |
| npu-d075-r002 | PASS | 충분 | 100.0 % |
| npu-d075-r003 | PASS | 충분 | 99.5 % |
| npu-d075-r004 | PASS | 충분 | 99.9 % |
| npu-d075-r005 | PASS | 충분 | 98.0 % |
| npu-d100-r001 | PASS | 충분 | 100.0 % |
| npu-d100-r002 | PASS | 충분 | 100.0 % |
| npu-d100-r003 | PASS | 충분 | 100.0 % |
| npu-d100-r004 | PASS | 충분 | 99.2 % |
| npu-d100-r005 | PASS | 충분 | 100.0 % |

**요약 — NPU: ① 20/20 · ② 충분 20/20.** (D1GPU 결손 런 13개도 ①② 모두 통과 — ①은 러너 JSONL 경로, ②의 PID 대조는 남은 D1GPU 줄로 충분)

**③ 로그 범위가 불완전해 판단 불가한 것 (목록)**
- 캡처 필터 `D1CHECK_EVENT:I D1GPU:I tflite:I TfLite:I litert:I *:S` 밖의 태그 — ENN 벤더 태그, NPU 드라이버·커널 로그, ENN AIDL HAL 프로세스 로그
- `tflite`·`litert` 의 V/D 레벨 (I 이상만 캡처)
- `tflite`·`litert` 태그의 보존율 — 분모가 없어 산출 불가 → 이 태그의 "실패 문구 0" 은 캡처 범위 한정
- D1GPU 사본 결손 구간 (13/20 런, 최대 22.1 % 결손) — 그 구간에 다른 태그 줄도 빠졌는지 판단 불가
- load 루프 **도중**의 자원 전환 — dispatch·ENN 증거는 초기화 시점 줄뿐이고 추론별 backend 로그는 없다
- `Header verification failed - using old format` (런마다 1줄) 의 의미 — 실행 성공과 공존하지만 영향 미확인
- NPU 코어 실행의 직접 증거 (`/dev/npu*` fd) — 앱 프로세스엔 없음, HAL 프로세스는 루트 필요 (§6 마지막 행)

---

## 7. 한계 (과장 금지)

- 입력은 합성 LCG 하나를 반복 (argmax 32/32 는 전부 112 — 변별력 약함). 대표 이미지 NPU 품질은 미확인
- MobileNet V1 만. 계약 모델(EfficientNet-Lite0 / EfficientDet-Lite0)은 **스모크(실행)만** 확인 — timed run 경로 미연결
- S26 은 일상 사용 폰 — 백그라운드 경합은 통제하지 않았다 (비행기 모드로 줄였을 뿐)
- 화면 밝기 0 — CPU/GPU 80런의 밝기(9/14 기록 91)와 다르다 → **idle W 비교에 주의** (지연·열 상승 비교에는 영향 작음 [E])
  ([2026-09-26 사후 증거 감사] idle W 차이의 원인을 밝기로 볼 근거는 없다 — §5. 원문은 유지)
- [2026-09-26 사후 증거 감사 추가] 정밀도: CPU·GPU 는 FP32 저장, NPU 는 FP16 저장 추정. **연산 정밀도는 세 자원 모두 unknown** (§3.1)
- 에너지 잠정, τ 방법 재구현

---

## 8. 산출물

`D1Check_v4\results\S26_NPU_formal_0925b\exports-v2\` (스키마 v2, 자동 생성, git 무시 경로)

| 파일 | 크기 | 행수 |
|---|---|---|
| `run_summary.csv` | 15,331 B | 20 |
| `phase_temperature_summary.csv` | 44,708 B | 80 |
| `thermal_timeseries.csv` | 2,137,949 B | 8,532 |
| `dataset_manifest.json` | — | included 20 / excluded 0 |

exports-v2 점검 [P] — **무결성·복사 정합성 검사이지 독립 교차검증은 아니다**:
- `s26_verify_exports.py`: 3개 CSV 가 같은 내보내기 단계가 쓴 `dataset_manifest.json` 해시와 바이트 동일 (rc 0) → 파일 손상 없음
- `run_summary.csv` 20행 × 6필드(지연 median·p95, slot_id, duty, termination, resource) vs 각 런 `merged\summary.json`·manifest: 120 필드 불일치 0
  → 내보내기가 입력을 옮기는 과정에서 틀리지 않았다는 뜻 (summary.json 이 exporter 의 입력이므로)
- 독립 재계산 (읽기 전용 검토 에이전트, 05:0x): 이 문서의 모든 숫자를 원시 JSONL·summary·exports 에서 다시 계산 — **숫자 오류 0**, 표기 불일치 9건은 이 판에서 고침
- ~~이전 판 (3521b9b): 캡처된 logcat 의 D1GPU 사본은 11/20 런에서 일부 빠졌다 (77.9~99.9 %, 전체 98.8 %).~~
  → [2026-09-26 사후 증거 감사] 캡처 `raw\logcat.txt` 의 D1GPU 태그 줄 수 ÷ 러너 JSONL(`gpu\*.jsonl`) 줄 수 = 런별 77.9~100 %, 전체 **98.8 %** (재현됨), 100 % 미만은 **13/20 런** (11/20 은 재현 안 됨). 정의·세부는 §6.1 (근거: 원시 20런 재계산 [P]).
  원문 이어짐: 지연·추론 수는 **러너 JSONL(완전)** 에서 나오므로 영향 없음

exports-v2 의 알려진 표기 문제: `formal_npu_valid` 열 없음(`model_eligible` 로만 반영), NPU 행 `execution_profile_type cpu_not_applicable`.

## 9. 남은 일

- [ ] 에너지 단위 허용오차 사전 등록 → §5 판정
- [ ] 대표 이미지셋으로 NPU 품질 재확인 (조민규 답장 대기)
- [ ] EfficientNet/EfficientDet timed run (orchestrator `d1_npu_input_spec`·`d1_npu_model_path` 전달 필요)
- [ ] 엔진 대조 개선 — npu-runner timed run 에 CPU 허용 여부 결정
