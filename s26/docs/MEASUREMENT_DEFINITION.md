# D1Check 측정 정의 — 우리가 정확히 무엇을 재고, 무엇이 결과로 나오는가

작성: 2026-09-12 · 근거: `mingyujo/D1Check` master `15950e5` 전체 소스 (101개 파일) 정독
대상 독자: S26 측정 코드를 새로 짜는 사람, 시뮬레이터를 만드는 사람

이 문서는 **현재 코드가 실제로 하는 일**만 적는다. 계획·제안·희망은 §7에 따로 모았다.
수치와 컬럼명은 전부 코드에서 직접 확인한 값이다.

---

## 0. 한 문단 요약

D1Check는 **"같은 스마트폰에서 MobileNetV1 추론 1회를 반복 실행했을 때, 추론 1건이 얼마나 걸리고 / 기기가 얼마나 뜨거워지고 / 배터리 원시 전류값이 어떻게 변하는지"** 를 재는 장치다.
정확도(품질)는 timed 구간에서 재지 않고, 실행 전 별도의 preflight에서 CPU와 GPU가 같은 답을 내는지만 검증한다.
에너지(J·mWh)는 **아직 한 번도 계산하지 않는다** — 전류 단위가 미검증이라 코드가 의도적으로 막아놨다.

---

## 1. 측정을 만드는 3개 프로세스

| 프로세스 | 어디서 도는가 | 무엇을 만드는가 | 샘플 주기 |
|---|---|---|---|
| **D1Check 앱** `com.example.d1check` | 폰 (foreground service) | 열 헤드룸·전류·전압·배터리 원시값 | **1초 고정** (`SAMPLE_PERIOD_NS = 1_000_000_000L`) |
| **Benchmark Runner 앱** `…d1check.benchmarkrunner` | 폰 (전용 스레드 `d1-benchmark-runner`) | 추론 1회당 지연 span, 라이프사이클 구간 | 추론마다 1건 |
| **호스트 PC (Python)** | 노트북 | `dumpsys thermalservice` HAL 온도, logcat 수집·병합·검증·CSV export | **1초** (`--interval`, 최소 0.5) |

두 앱은 **같은 키로 서명**되어야 한다 (`com.example.d1check.permission.READ_RUN_CONTEXT`, `protectionLevel="signature"`).
Runner는 ContentProvider `content://com.example.d1check.run/current`로 현재 run 컨텍스트(run_id, active, boot_id)를 읽고, **5개 체크포인트**(before_baseline / before_warmup / before_gpu_load / after_gpu_load / before_file_flush)에서 재검증한다. 하나라도 어긋나면 `run_context_mismatch`로 실험 무효.

호스트 도구 3종:
- `tools/d1_logger_v4.py` (1,249줄) — `clear` / `capture` / `analyze` / `self-test`
- `tools/d1_experiment_orchestrator.py` (4,665줄) — 반복 실험 자동화, 블록 설계, 안전 감시, resume
- `tools/d1_thermal_dataset.py` (1,008줄) — 최종 `exports-v2/` CSV 생성

---

## 2. "AI 항목" — 무엇을 추론하는가

### 2.1 모델 (단 하나, 고정)

| 항목 | 값 | 근거 |
|---|---|---|
| 모델 | MobileNet V1 1.0 224 **float(FP32)** | `ModelLoader.kt` |
| asset 경로 | `models/mobilenet_v1_1.0_224.tflite` | `ModelLoader.ASSET_PATH` |
| model_id | `mobilenet_v1_1.0_224_float` | `ModelLoader.MODEL_ID` |
| SHA-256 | `D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB` | `ModelLoader.MODEL_SHA256` |
| 파일 크기 | 16,901,128 bytes | `benchmark-runner/build.gradle.kts` |
| 입력 | `[1,224,224,3]` FLOAT32 | `GpuBenchmarkEngine.INPUT_SHAPE` |
| 출력 | `[1,1001]` FLOAT32 Softmax 확률 | `GpuBenchmarkEngine.OUTPUT_SHAPE` |
| 출력 인덱스 규약 | 0 = TF-Slim background, **1~1000 = ImageNet WNID** | `V4_INTEGRATION.md`, `taskAccuracy()` require |
| 런타임 | LiteRT (TFLite) **1.4.2** | `libs.versions.toml`, `LITERT_VERSION` |

빌드 시 `verifyBenchmarkModel` Gradle task가 **파일 크기와 SHA-256을 강제 검증**한다. 모델을 바꾸려면 이 task도 같이 고쳐야 빌드가 된다.

### 2.2 "추론 1회"의 정확한 정의 — 타이밍 경계

```kotlin
resetTensorBuffers(input, output)          // ← 타이밍 밖
val startNs = SystemClock.elapsedRealtimeNanos()
interpreter.run(input, output)             // ← 이것만 잼
val endNs = SystemClock.elapsedRealtimeNanos()
```

타이밍 구간 안에는 **Logcat·JSON·파일 I/O·입력 생성·메모리 할당·UI 갱신이 전혀 없다.** 전부 `load_end` 이후에 몰아서 한다.
배치 크기는 1. 추론 1회 = span 1개 (start/end 분리 이벤트 아님).

### 2.3 입력 텐서 — 2가지가 전혀 다르다

| | timed run (본 측정) | accuracy preflight |
|---|---|---|
| 생성 | `DeterministicInputSet.legacyTimedInput()` | 합성 32개 또는 대표입력 40개 |
| 내용 | LCG(seed `0x12345678`) `[0,1]` float32 난수 | 합성 동일 방식 / 실사진 호스트 전처리 |
| 개수 | **단 1개 버퍼를 끝까지 재사용** | 32~256개 |
| 정규화 | 없음 (`synthetic_[0,1]_float32_no_additional_normalization`) | 대표입력은 RGB→EXIF→central crop 0.875→bilinear 224→`(p/255-0.5)*2` |

> **본 측정은 "똑같은 합성 입력 1장을 계속 반복 추론"한다.** 입력 다양성이 지연·발열에 주는 영향은 측정 대상이 아니다. 시뮬레이터 모델링 시 이 가정을 반드시 명시해야 한다.

대표입력 컨테이너 `d1-representative-tensor-set-v1` (`.d1tset`):
`D1TSET01`(8B) + header 길이 uint32 LE + canonical UTF-8 JSON header + FLOAT32 LE 페이로드.
헤더에 데이터셋·선택 seed·원본 이미지 해시·WNID·전처리 설정 해시·텐서별 해시가 전부 들어간다. Android가 컨테이너 해시·전처리 해시·텐서별 해시·구조 경계를 **인터프리터 만들기 전에** 전부 검증한다.

### 2.4 자원(resource) — 현재 실제로 실행 가능한 것

| enum | 실행 가능? | 근거 |
|---|---|---|
| `CPU` (스레드 1~16) | ✅ | `options.setNumThreads(cpuThreads)` |
| `CPU4` | ✅ (CPU+4스레드의 레거시 별칭) | `normalizedResource` |
| `GPU` | ✅ (`GpuDelegate`) | `CompatibilityList().isDelegateSupportedOnThisDevice` 확인 후 생성 |
| `NPU` | ❌ **`error("NPU is reserved for a future version")`** | `GpuBenchmarkEngine.kt` |

- CPU4는 "4코어 고정(affinity)"이 **아니다**. 메타데이터에 `cpu_affinity = "NONE"`을 명시 기록한다.
- timed CPU 실행은 XNNPACK을 명시적으로 켜지 **않는다**. preflight의 CPU reference만 `setUseXNNPACK(true)`를 켜고 그 사실을 기록한다.
- GPU 프로필 2종 (`GpuDelegateProfile.kt`), 둘 다 `quantized_models_allowed=true`, `FAST_SINGLE_ANSWER`, backend `UNSET`:

| profile_id | precision_loss_allowed | 의미 |
|---|---|---|
| `gpu-compat-default-v1` (기본) | `true` | FP16 **허용**(허가일 뿐, 실행 증거 아님) |
| `gpu-fp32-strict-v1` | `false` | FP32 강제 |

두 프로필 모두 `actual_fp16_execution = "unknown_not_exposed_by_litert_api"`. **LiteRT가 실제 FP16 커널 실행 여부를 알려주지 않으므로 아무도 그렇게 주장하지 않는다.**

### 2.5 정밀도(precision) — INT8은 아직 막혀 있음

`ModelPrecision` enum에 `FLOAT32`/`INT8`이 있지만 `RunConfig`의 `init`이 **`require(precision == ModelPrecision.FLOAT32)`** 로 INT8을 차단한다. 즉 현재 품질 티어는 FP32 한 가지뿐이다.

---

## 3. 1회 run의 시간 구조

```
D1Check run_start
  │  ← baseline 60초 고정 (BASELINE_MS = 60_000, 하드코딩)
  │     그 사이 delegate_init / interpreter_init / warmup 수행
load_start ─────────── 부하 구간 (duty cycle 적용) ───────────  load_end
  │                                                              │
  │                                              ← cooling (fixed/stable/matched)
run_stop
```

phase는 **반개구간**으로 겹치지 않게 자른다 (`d1_thermal_dataset.classify_phase`):

| phase | 구간 |
|---|---|
| `baseline` | `[run_start_mono_ns, load_start_mono_ns)` |
| `load` | `[load_start_mono_ns, load_end_mono_ns)` |
| `cooling` | `[load_end_mono_ns, run_stop_mono_ns)` |

**시계는 Android `SystemClock.elapsedRealtimeNanos()` (= `mono_ns`) 하나뿐이다.** UTC·호스트 monotonic은 provenance(출처 기록)용이며 **정렬에 절대 쓰지 않는다.** 호스트 시간과 Android mono_ns를 빼는 것은 금지.

### 3.1 종료 조건 (`TerminationReason`)

`count_complete` · `duration_complete` · `buffer_limit` · `run_context_mismatch` · `pilot_safety_rejected` · `run_error` · `shutdown_error`

DURATION 모드에서 추론 횟수는 **입력이 아니라 출력**이다. `Interpreter.run()`은 중단 불가라 마지막 1회가 마감을 넘길 수 있고, 그 초과분을 `duration_overrun_ns`로 기록한다.

### 3.2 duty cycle (부하율)

`load_start` 시점의 mono 시계에 앵커링. 주기마다 active 창 → idle 창. 추론은 active 창에서만 **시작**하지만 진행 중인 추론은 경계를 넘을 수 있다.

- `actual_active_duration_ns + actual_idle_duration_ns = actual_load_duration_ns` (항상 성립, 검증됨)
- `achieved_duty_cycle_percent = actual_active / actual_load × 100` (요청값이 아니라 **실측값**)
- `duty_cycle_active_overrun_ns` = 의도한 idle 창을 침범한 누적 시간

### 3.3 상한값 (하드코딩)

| 항목 | 상한 |
|---|---|
| warmup | 10,000회 |
| 추론 span | **250,000개** (초과 시 `buffer_limit`으로 실험 종료) |
| 라이프사이클 이벤트 | 20,000개 |
| duration | 3,600초 |
| CPU 스레드 | 1~16 |
| duty | 1~100% |

---

## 4. 측정 항목 — 6개 계층

### A. 지연 (Runner)

추론 span 1개당: `start_mono_ns`, `mono_ns`(=end), `latency_ns`, `latency_ms`, `inference_index`, `batch_size`, `sequence`, `wall_ms`
라이프사이클 구간도 같은 방식으로 측정: `delegate_init`, `interpreter_init`, `warmup`(회차별), `shutdown`, `baseline_start/end`, `load_start/end`
→ **자원 전환·모델 로드 비용이 여기 이미 잡혀 있다.** `delegate_init`이 GPU 초기화 비용이다.

집계(`latency_stats`): `count`, `mean_ms`, `median_ms`, **`p95_ms`**, `min_ms`, `max_ms`
p95는 선형보간 방식 (`percentile()`, position = (n-1)×0.95).

### B. 열 — 두 개의 독립 소스

**(1) D1Check 앱, 1초** — `getThermalHeadroom()` 기반
| 필드 | 의미 | 주의 |
|---|---|---|
| `headroom_now` | `getThermalHeadroom(0)` | **짝수 tick에만 갱신** |
| `headroom_60s` | `getThermalHeadroom(60)` | **홀수 tick에만 갱신** |
| `thermal_status` | `PowerManager.currentThermalStatus` (0~6) | API 29+ |
| `battery_temp_C` | `EXTRA_TEMPERATURE / 10.0` | |
| `verdict` | `HEADROOM_OK` / `HEADROOM_WARMUP` / `HEADROOM_UNSUPPORTED_OR_ERROR` / `HEADROOM_API_UNAVAILABLE` | tick 15까지는 WARMUP |

> 두 헤드룸은 **매 초가 아니라 2초마다 번갈아** 갱신된다. 시계열로 쓸 때 이 점을 반드시 반영할 것.

**(2) 호스트 `dumpsys thermalservice`, 1초** — HAL 실제 온도
- 센서 **정확히 4종 강제**: `AP`, `BAT`, `PA`, `SKIN` (PA는 `PA`/`PATHM`/`PA1THM` 별칭 허용)
- `Current temperatures from HAL:` 섹션만 파싱
- **샘플마다 `/proc/uptime`을 앞뒤로 읽어 시각을 bracketing**:
  `sample_before_mono_ns`, `sample_after_mono_ns`, `mono_ns = (before+after)//2`, `sampling_uncertainty_ns = (after-before)//2`
- 4종 중 하나라도 없으면 `parse_status = "missing_sensor"` → 그 샘플은 무효

**열 커버리지 게이트** (`thermal_coverage`): 유효 샘플 비율 **≥ 95%** 이고 load 구간 안에 유효 샘플이 **최소 1개** → `passes_formal_requirement = true`

### C. 전력 / 에너지 — **원시값만, 계산 없음**

D1Check 1초 샘플에 들어가는 원시 필드:
`current_raw` (`BATTERY_PROPERTY_CURRENT_NOW`), `current_valid`, `voltage_mV` (`EXTRA_VOLTAGE`), `charge_counter_raw` (`BATTERY_PROPERTY_CHARGE_COUNTER`), `charge_valid`, `plugged`

모든 산출물이 아래를 명시한다:
```json
"energy_measurement": {
  "status": "raw_unverified",
  "current_raw_policy": "raw_unscaled_unit_unverified",
  "current_unit_verified": false,
  "charge_counter_unit_verified": false,
  "calculation_performed": false,
  "note": "no J or mWh result is produced before unit calibration"
}
```

> **J도 mWh도 mA도 존재하지 않는다.** `current_raw`는 스케일 변환·부호 변환 없이 보고된 값 그대로다. 단위 검증(단계 2)이 끝나기 전에는 배터리 예산 정책을 "검증했다"고 말할 수 없다.

부호 규약 함수만 미리 준비돼 있다 (양의 방전 크기로 통일):
- `current_now_discharge_magnitude_ua(raw)` — Android 음수 방전값을 부호 반전
- `charge_counter_discharge_magnitude_ua(start, end, s)` — `(start-end)*3600/elapsed`
스케일 불일치는 **절대 조용히 보정하지 않는다.**

### D. 품질 / 정확도 — timed run과 완전 분리

**timed run은 정확도를 재지 않는다.** 메타데이터에 그 사실을 박아둔다:
`accuracy_preflight.status = "not_run"`, `validation_scope = "timed_run_does_not_execute_preflight"`

preflight는 `START_RUN`과 열 컨디셔닝 **이전에** 별도 인터프리터 생애주기로 돌고, 끝나면 runner를 force-stop한 뒤 컨디셔닝을 새로 한다. timed 작업과 버퍼·인터프리터를 절대 공유하지 않는다.

**3개 스코프 (스키마 v2, 서로 다른 질문에 답한다)**

| 스코프 | 무엇을 보는가 | 차단 게이트 |
|---|---|---|
| `synthetic_numerical_check` | 합성 32개+ 로 런타임·텐서·delegate·파국적 수치 오류 smoke | formal에서 필수 |
| `representative_input_equivalence` | 실사진 40장 호스트 전처리 텐서로 CPU↔GPU 동등성 | **`backend-performance-formal`의 차단 게이트** |
| `task_accuracy_check` | 정답 WNID 대비 top-1/top-5 정확도와 GPU−CPU 델타 | `accuracy-preserving-formal`에서만 |

**비교기 `output-equivalence-v3`**
- 원소 허용식: `|GPU − CPU| ≤ atol + rtol × |CPU|` (기본 `atol=1e-4`, `rtol=1e-3`, 상대오차 eps `1e-6`)
- 순위 tie-break: **점수 내림차순 → 인덱스 오름차순**
- 5위/6위가 **정확히 동점**이면 top-5 집합이 유일하지 않음 → `top5_overlap_applicable=false`로 기록하고 최소 overlap 계산에서만 제외 (다른 게이트는 그대로 적용)

**수락 정책 `representative-equivalence-v2`** (사전 등록값, 관측치에 맞춰 조정 금지)
| 기준 | 값 |
|---|---|
| 최소 샘플 수 | 40 |
| top-1 불일치 허용 | **0** |
| 입력별 top-5 overlap 최소 | 4 |
| 최대 total variation distance | 0.02 |
| 최소 cosine similarity | 0.999 |

**정책 `task-accuracy-no-regression-v1`**: 라벨 샘플 ≥40, top-1/top-5 정확도 하락 허용 0.0

입력 1건당 기록되는 지표 (JSONL `accuracy_preflight_input`):
`max_absolute_error`(+인덱스/값/임계), `mean_absolute_error`, `rmse`, `max_relative_error`, `elementwise_mismatch_count`, `non_finite_count`, `reference/candidate_{minimum,maximum,probability_sum}`, `cosine_similarity`, `total_variation_distance`, `reference/candidate_argmax`, `argmax_agreement`, `reference/candidate_top5`, `top5_overlap_count`, `top5_overlap_applicable`(+사유), `top5_set_agreement`, `ordered_top5_agreement`, `reference/candidate_top1_margin`, `reference/candidate_top5_boundary_margin`

교차 검증: 폰이 만든 요약을 그대로 믿지 않고, 호스트가 바이너리 아티팩트(`D1EQV001` + input_count + output_count + CPU/GPU FLOAT32 교차 배열)를 **전부 다시 계산**해서 일치하는지 확인한다.

> **중요한 구분**: `execution_integrity_status`(구조적으로 제대로 실행됐나)와 `equivalence_acceptance_status`(허용 오차 안에 들어왔나)는 **별개**다. 대표입력 수락 실패가 실행 무결성 실패를 뜻하지 않는다. A24 compat 프로필 파일럿이 정확히 이 경우였다(무결성 통과, 동등성 실패 → timed 측정 자체를 못 씀).

### E. 실행 증거 (delegate evidence) — 호스트가 logcat에서 파싱

`full_delegate = true` 가 되려면 **5개 전부** 충족:
1. `Created TensorFlow Lite delegate for GPU`
2. `TfLiteGpuDelegateV2` 문자열 존재
3. `Replacing X out of Y node(s)` 에서 **X = Y > 0**
4. `Created N GPU delegate kernels` 에서 **N > 0**
5. fallback 증거 **없음** (`failed to apply` / `restored original execution plan` / `unsupported op` / `remaining nodes run on CPU` / `falling back to CPU` / `CPU fallback`)

하나라도 없으면 `verification = "unverified"`. 코드가 명시한다: **"증거 없음은 CPU fallback의 증거가 아니다."**
delegate 생성 성공만으로는 전체 위임을 주장하지 않는다.

### F. 안전·통제 상태

**pilot 안전 게이트** (앱 `PilotSafetyPolicy` + 호스트 `evaluate_safety`, 값이 동일)
| 조건 | 값 |
|---|---|
| Android thermal status | ≤ 1 (LIGHT) |
| 충전 | unplugged 필수 |
| battery status | 3 (DISCHARGING) |
| 배터리 잔량 | 30~100% (formal 에너지 적격은 30~90%) |
| 배터리 온도 | ≤ 35.0 ℃ |

메타데이터에 `safety_policy_scope = "PILOT_START_ONLY"`, `formal_safety_limits_applied = false`, `matched_start_limits_applied = false`를 명시한다. **시작 시점만 보고, 실행 중 하드 세이프티는 아직 없다.**

**시작 열 조건 `--start-policy`**
| 정책 | 동작 |
|---|---|
| `safety` (기본) | 위 preflight만 |
| `stable` | 롤링 윈도우에서 4개 센서 **전부** range ≤ `--stability-max-range-c`(0.5) **and** \|최소제곱 기울기\| ≤ `--stability-max-slope-c-per-minute`(0.2) |
| `matched` | stable + 실험 전체에 저장된 **단 하나의 기준 벡터**와 `--matched-tolerance-c`(0.5) 이내 |

> `stable`은 "같은 온도"라는 뜻이 **아니다.** 실제 `load_start` 온도를 모델의 상태변수/공변량으로 써야 한다.
> `matched`는 조건 3개 이상 행렬에서 `matched_global_reference_long_matrix` 경고를 남긴다 (비차단). A24 파일럿에서 실제로 300초 안에 기준 복귀 실패 사례가 있었다 (AP +0.8℃, PA +0.9℃, SKIN +0.6℃).

**냉각 `--cooling-policy`**: `fixed`(기본, 고정 시간) / `stable` / `matched`
stable·matched는 runner를 force-stop한 뒤 D1Check 텔레메트리는 계속 켠 채로 대기 → `load_end`~`run_stop`이 냉각 곡선 데이터가 된다.
matched 냉각 마감 시 `status=timeout`, `completion_reason=cooling_timeout`, `failure_classification=thermal_conditioning_timeout` (비상 중단이나 runner 실패로 분류하지 않음).

**런타임 비상 감시**: 기본 **OFF** (`--emergency-check-interval-seconds 0`). 켜면 logcat 텔레메트리를 먼저 보고, 빈틈만 희소 `dumpsys`로 채운다.

### 실험 설계 (반복)

무작위 완전 블록(randomized complete block). 블록 = 반복 회차. `--seed`는 **블록 내부만** 섞고 블록 경계를 넘는 전역 셔플은 없다.
조건 ID: CPU는 `cpu-t{스레드:02d}-d{duty:03d}`, GPU는 `gpu-d{duty:03d}`. 슬롯 ID는 `{condition_id}-r{반복:03d}`.
슬롯마다 **새 D1Check run UUID + 새 runner command UUID**. 실패한 슬롯은 실험 전체를 멈추고, `--resume`으로 이어가되 완료 슬롯은 절대 재실행하지 않는다.

---

## 5. 결과물 — 실제로 나오는 파일과 값

### 5.1 run 1개당 (`results/<run_id>/`)

```
metadata.json                       ← logger 버전, device_model, device_fingerprint, capture_error, capture_warnings
raw/logcat.jsonl                    ← D1CHECK_EVENT + D1GPU JSON 이벤트
raw/logcat.txt                      ← D1CHECK_EVENT, D1GPU, tflite, TfLite 원문 (delegate 증거 소스)
raw/thermalservice.jsonl            ← 1초 HAL 온도 샘플
raw/thermalservice-probe.txt        ← dumpsys 원문 1회 스냅샷
gpu/gpu-events-<run_id>-<session_id>.jsonl   ← ★ 권위 있는 원본 (adb pull)
merged/events.jsonl                 ← 전부 시간순 병합 + analysis_phase(BASELINE/LOAD/COOLDOWN)
merged/latency_timeline.csv         ← ★ 추론 1건 = 1행
merged/summary.json                 ← ★ run 판정 요약
merged/delegate_evidence.json
diagnostics/d1check.perfetto-trace  ← 진단 모드에서만
```

Logcat은 **권위 있는 소스가 아니다.** Android가 늦은 `D1GPU` 리플레이를 버릴 수 있어서, 폰에서 `adb pull`한 runner JSONL이 정본이고 Logcat은 상태·복구용 사본이다. pull 실패 시 debuggable 빌드에서 `run-as cat` 폴백.

**`latency_timeline.csv` — 23개 컬럼 (추론 1건 = 1행)**
```
run_id, sequence, inference_index, start_mono_ns, end_mono_ns, load_elapsed_s, latency_ms,
d1_sample_delta_ms, thermal_sample_delta_ms,
headroom_now, headroom_60s, thermal_status, current_raw, current_valid, voltage_mV,
battery_temp_C, charge_counter_raw, plugged,
AP, SKIN, BAT, PA, thermalservice_status
```
열·전류 값은 그 추론의 **종료 시각에 가장 가까운 샘플**을 붙인 것이고, 얼마나 떨어져 있었는지를 `d1_sample_delta_ms` / `thermal_sample_delta_ms`로 같이 남긴다. (보간 아님)

**`merged/summary.json` 주요 키**
`resource`, `model_id`, `model_sha256`, `statistics_group`(basic/diagnostic), `runner_session_id`, `runner_session_count`, `telemetry_sample_count`, `thermalservice_sample_count`, `thermal_coverage{…}`, `run_start/load_start/load_end/run_stop_mono_ns`, `run_envelope_validation`, `delegate_evidence{…}`, `gpu_delegate_profile`, `profile_consistency_validation`, **`formal_gpu_valid`**, `inference_latency{count, mean_ms, median_ms, p95_ms, min_ms, max_ms}`, `duty_cycle{10개}`, `accuracy_preflight`, `energy_measurement`, `analysis_warnings`

**`formal_gpu_valid = true` 조건 (9개 전부)** — `d1_logger_v4.py`
GPU 자원 · BASIC 모드 · **기기 모델이 `SM-A245`로 시작** · 모델 SHA 일치 · LiteRT 1.4.2 · `full_delegate=true` · 프로필 검증 통과 · `experiment_valid=true` · 열 커버리지 통과
> ⚠️ **S26에서는 기기 하드코딩 때문에 무조건 `false`가 된다.** §7 이식 항목 1 참고.

### 5.2 실험 전체 (`experiment_manifest.json` + `exports-v2/`)

`experiment_manifest.json` — 모든 전이·실패를 원자적으로 체크포인트. 블록 설계, 슬롯별 steps, 안전 스냅샷, 열 컨디셔닝 원시 샘플, 냉각 판정, 비상 감시 관측, 실패 아티팩트 경로, resume 상태.

**`exports-v2/` (schema v2, 스테이징 후 원자적 교체, 재실행 시 append 아니라 replace)**

| 파일 | 행 단위 | 컬럼 수 |
|---|---|---|
| `run_summary.csv` | 슬롯 1개 = 1행 (**실패·대기 슬롯도 전부 포함**) | **74** |
| `phase_temperature_summary.csv` | 슬롯 × 센서 4종 = 4행 | **61** |
| `thermal_timeseries.csv` | phase 배정된 유효 샘플 1개 = 1행 | **30** |
| `dataset_manifest.json` | — | 원본 매니페스트 SHA, 행 수, 제외 사유 집계, 시계 정의, CSV별 SHA |

**공통 BASE 17컬럼** (3개 CSV 전부)
`experiment_id, run_id, slot_id, condition_id, block, repetition, order, resource, cpu_threads, requested_duty_cycle_percent, execution_profile_type, gpu_delegate_profile_id, gpu_delegate_configuration_sha256, gpu_precision_loss_allowed, gpu_inference_preference, gpu_force_backend, actual_fp16_execution`

`execution_profile_type` 값: `cpu_not_applicable` / `gpu_delegate` / `gpu_legacy_missing` / `gpu_delegate_invalid`

**`run_summary.csv` 추가 25컬럼**
`slot_status, attempts, slot_error, achieved_duty_cycle_percent, requested_duration_s, actual_load_duration_s, completed_inference_count, latency_mean_ms, latency_median_ms, latency_p95_ms, validation_status, termination_reason, cooling_status, accuracy_preflight_status, synthetic_numerical_check_status, representative_input_equivalence_status, task_accuracy_check_status, formal_gate_result_status, energy_measurement_status, formal_gpu_valid, model_eligible, exclusion_reasons, thermal_raw_record_count, thermal_valid_sample_count, thermal_source_issues`
**+ 센서 4종 × 8개 = 32컬럼**: `{ap,bat,pa,skin}_` × `{run_start, load_start, load_end, cooling_end}_temperature_c`, `baseline_change_c`, `load_change_c`, `cooling_change_c`, `residual_vs_load_start_c`

**`phase_temperature_summary.csv` 추가 44컬럼**
센서별 온도 16개 (4 endpoint 온도 + 3 변화량 + 잔차 + load min/max/peak/peak_mono_ns/peak_elapsed_s + cooling min/max)
\+ endpoint 4종 × 7개 선택 품질: `selection_method`, `quality`, `quality_reason`, `sample_mono_ns`, `signed_offset_ms`, `absolute_offset_ms`, `sampling_uncertainty_ms`

**`thermal_timeseries.csv` 추가 13컬럼**
`achieved_duty_cycle_percent, mono_ns, run_elapsed_s, load_relative_s, phase, phase_elapsed_s, AP, BAT, PA, SKIN, thermal_status, sampling_uncertainty_ns, parse_status`

**엔드포인트 온도 선택 규칙**
- 대상 시각 **이하**의 가장 최근 유효 샘플을 고른다
- `run_start`만 예외적으로, 앞선 샘플이 하나도 없을 때 뒤쪽 첫 샘플로 폴백
- 절대 오프셋 **2,000 ms** 초과 시 `too_far`로 표시하고 **온도를 null로 둔다**

**모델 적격성 `model_eligible`** — 아래를 전부 만족해야 true:
슬롯 `status=completed` · `validation.valid=true` · 열 커버리지 통과 · run envelope 통과 · phase 타임스탬프 유효 · 4개 엔드포인트 선택 전부 `ok` · 자원/설정 메타데이터 일치 · (GPU면) `formal_gpu_valid=true` **and** 실행 프로필 유효 · 중복 mono_ns 없음

> **실패 슬롯을 조용히 버리지 않는다.** `model_eligible=false` + `exclusion_reasons` JSON으로 남긴다.
> **null을 0으로 대체하지 않는다.** 미지원 조합·검증 실패를 0으로 채우는 것은 금지.

---

## 6. 시뮬레이터가 실제로 가져다 쓸 수 있는 값 (계약 A)

| 시뮬레이터 필요 값 | 출처 | 현재 상태 |
|---|---|---|
| 조건별 지연 L | `run_summary.csv` `latency_mean_ms` / `latency_p95_ms` | ✅ 사용 가능 |
| 지연 분포 | `latency_timeline.csv` `latency_ms` | ✅ 추론 단위 원본 |
| 온도 궤적 T | `thermal_timeseries.csv` AP/BAT/PA/SKIN + `phase` + `phase_elapsed_s` | ✅ RC 모델 피팅 가능 |
| 가열·냉각 시정수 | `phase_temperature_summary.csv` `load_change_c`, `cooling_change_c`, `load_peak_elapsed_s` | ✅ |
| 시작 열 상태 | `{sensor}_load_start_temperature_c` | ✅ 공변량으로 써야 함 |
| 자원 전환 비용 | runner JSONL `delegate_init` / `interpreter_init` span | ⚠️ CSV에 없음, JSONL에서 직접 뽑아야 함 |
| 에너지 E | — | ❌ **없음** (단계 2 미완) |
| 품질 손실 ΔQ | preflight `task_accuracy_check` | ⚠️ 티어가 FP32 하나뿐이라 티어 간 비교 불가 |
| 요청 도착·납기 | — | ❌ **개념 자체가 코드에 없음** (단계 4에서 신설) |
| NPU 어떤 값이든 | — | ❌ **없음** |

---

## 7. S26 이식 시 반드시 고쳐야 하는 지점 (A24 하드코딩)

| # | 위치 | 문제 | 영향 |
|---|---|---|---|
| 1 | `d1_logger_v4.py` `galaxy_a24 = device_model.startswith("SM-A245")` | 기기 모델 하드코딩 | **S26은 `formal_gpu_valid`가 항상 false** → `model_eligible`도 false → exports에서 전부 제외 |
| 2 | `parse_thermalservice` / `parse_hal_temperature_vector` | AP·BAT·PA·SKIN **4종 강제**, PA 별칭은 A24 기준 | S26 센서 이름이 다르면 전 샘플 `missing_sensor`, `stable` 정책은 슬롯 즉시 중단 |
| 3 | `d1_thermal_dataset.py` `SENSORS = ("AP","BAT","PA","SKIN")` | 동일 | export 컬럼 구조 자체가 4종 고정 |
| 4 | `RunConfig.init` | `require(resource in {CPU, CPU4, GPU})`, `require(precision == FLOAT32)` | NPU·INT8 진입 자체가 막힘 |
| 5 | `GpuBenchmarkEngine` | `ResourceTarget.NPU -> error(...)` | NPU 실행 경로 없음 |
| 6 | `AutomationIntentParser.parse` | `"NPU"` 문자열 매핑 없음 | `Unsupported d1_resource: NPU` |
| 7 | `orchestrator` `--resources choices=("CPU","GPU")`, `build_conditions` | CPU/GPU만 | 자동화에서 NPU 조건 생성 불가 |
| 8 | `delegate_evidence()` | GPU 전용 정규식 (`TfLiteGpuDelegateV2` 등) | NPU 위임 증거 판정 없음. 테스트가 NNAPI 로그를 명시적으로 `unverified` 처리 |
| 9 | `execution_profile_columns` | `resource != GPU` → `cpu_not_applicable` | NPU 프로필 provenance를 담을 칸 없음 |
| 10 | `GpuDelegateProfile` | GPU에만 profile 개념 | NPU delegate 설정 해시·증거 스키마 신설 필요 |
| 11 | `ModelLoader` + `verifyBenchmarkModel` | FP32 모델 1개, 크기·SHA 강제 | INT8/FP16 모델 추가 시 빌드가 막힘 |
| 12 | `PilotSafetyPolicy` | 배터리 35℃, thermal status ≤1 | S26 헤드룸 공식·임계가 다름. 측정 전 재확인 필요 |
| 13 | `BASELINE_MS = 60_000` | 고정 60초 | 변경하려면 orchestrator의 `BASELINE_SECONDS`도 같이 |
| 14 | `REMOTE_RUNNER_DIRECTORY = /sdcard/Android/data/…` | scoped storage | S26 Android 버전에서 접근 가능한지 확인 |
| 15 | `compileSdk/targetSdk 37`, `minSdk 24`, AGP 9.3.2 | | S26 Android 버전과 맞는지 확인 |

**이미 준비돼 있는 것 — NPU의 출발점**
`benchmark-runner/src/main/cpp/nnapi_probe.cpp` + `NnapiDeviceProbe.kt`가 이미 있다.
`libneuralnetworks.so`를 dlopen해서 `ANeuralNetworks_getDeviceCount/getDevice/getName/getType/getVersion/getFeatureLevel`로 **NNAPI 디바이스를 열거**하고 `D1NPU` 태그로 JSON을 찍는다:
`index`, `name`, `type_number`, `type_name`(UNKNOWN/OTHER/CPU/GPU/**ACCELERATOR**), `version`, `feature_level`, `reference_cpu`(이름이 `nnapi-reference`인지), `npu_verification: "UNVERIFIED"`(하드코딩)
Benchmark Runner UI의 **"Probe NNAPI devices" 버튼**으로 지금 바로 실행 가능. **S26 첫 작업은 이 버튼을 눌러 `adb logcat -s D1NPU:I`를 받는 것.**

---

## 8. 이 측정이 말할 수 없는 것 (범위 한계)

1. **에너지** — J/mWh 값이 존재하지 않는다
2. **NPU** — 어떤 데이터도 없다
3. **품질 티어 간 비교** — FP32 하나뿐이라 INT8·FP16 트레이드오프를 아직 말할 수 없다
4. **요청 도착·납기·우선순위** — 개념이 코드에 없다. duty cycle은 "일정 비율로 켜고 끄기"일 뿐 **줄 서기가 아니다**
5. **동시 실행** — CPU/GPU/NPU 동시 실행 간섭은 측정한 적 없다. 순차 실행 데이터로 동시 실행을 추정하면 안 된다
6. **입력 다양성** — timed run은 같은 합성 텐서 1장을 반복한다
7. **실제 FP16 커널 실행** — LiteRT가 노출하지 않는다. `precision_loss_allowed=true`는 허가일 뿐 증거가 아니다
8. **기기 간 혼합** — 기기별 측정값을 하나의 자원 선택표로 직접 섞으면 안 된다. A24 CPU/GPU와 S26 NPU의 차이에는 SoC·센서·OS·배터리·열설계 차이가 전부 섞여 있다
9. **통계적 유의성** — 파일럿 export는 유의성을 확립하지 않는다
10. **Imagenette** — ImageNet 10개 클래스 부분집합이다. 전체 ImageNet 정확도가 아니다

---

## 9. 확인된 A24 실측값 (참고 기준선)

| 조건 | 값 | 출처 |
|---|---|---|
| GPU strict, timed 파일럿 | 76회, 평균 **131.60 ms**, P95 **137.18 ms** | `V4_INTEGRATION.md` |
| strict 대표입력 40장 | top-1 40/40, top-5 40/40, elementwise 불일치 **0**, min cosine 0.9999999999732401, max TV 0.0000038 | 동일 |
| compat 대표입력 40장 | top-1 39/40, top-5 set 34/40, 불일치 270/40,040, max TV **0.0230** (한계 0.02 초과 → **게이트 실패**) | 동일 |
| 두 프로필 task 정확도 | CPU/GPU top-1 모두 0.75 | 동일 |
| 전체 delegate | 31/31 노드 위임 확인 | 동일 |

> compat 프로필은 실행 무결성은 통과했지만 동등성 게이트에서 막혀 **timed 측정을 아예 수행하지 못했다.** 이 프로필의 지연값은 그 run에서 보고할 수 없다.

---

## 10. S26 에너지 허용오차 — **분해능 기반 사후 등록** (2026-09-26 작성, 커밋 시각은 git 기록)

> ⚠️ **사전 등록이 아니다.** 전류 적분 / charge counter 비율(CPU/GPU 80런 0.928, NPU 20런 0.977)은 **이미 관측된 뒤**에 이 절을 썼다.
> 그래서 허용오차는 그 두 값에서 거꾸로 정하지 않고, **분해능·산포 같은 성분**에서만 산정했다. 성분 계산은 평균 비율을 쓰지 않는다.
> 조민규 3분법(①단위 해석 일관성 / ②절대 에너지 측정 불확실성 / ③차이 구분 능력)을 섞지 않고 따로 적는다.
> 이 절이 `results\S26_THESIS_FIT.md` 의 "±10 % 기준 안"(철회 표시함)을 대체한다.

근거 자료 [P]: `results\S26_formal_strict` 80런, `results\S26_NPU_formal_0925b` 20런의 `merged\events.jsonl` d1check 1 Hz 샘플. 계산은 `s26\tools\s26_energy.py` + 2026-09-26 읽기 전용 재계산.

### 10.1 ① 전류 단위 해석 일관성

- 질문: `current_raw` 가 µA 인가 mA 인가, 부호는 어떤가. 두 가설은 1,000 배 차이라 **자릿수 판별**이면 충분하다
- 기준 (자릿수 논리에서 정함): 런별 비율(µA 가정 전류 적분 / charge counter 감소)이 **[0.5, 2]** 안이면 µA, 방전 샘플이 음수이면 "방전 음수"
- 판정: **PASS** — 100런 전부 [0.70, 1.18] 안 (mA 였다면 ~0.001 또는 ~1000). 모든 샘플 방전·유효. S26 = **µA · 방전 음수**

### 10.2 ② 절대 에너지 측정 불확실성

| 성분 | 크기 [P] | 종류 |
|---|---|---|
| charge counter 양자화 | 한 눈금 **4,275 µAh** (두 세션 모두 모든 Δ 가 배수). 런 전체 Δ 중앙 CPU/GPU 42,750 µAh(10눈금) · NPU 32,063(7.5눈금) → 단일 런 기준값 **±1눈금 = ±9.1 %(47,025 µAh 런)~±13 %** | 랜덤 (합산하면 √N 로 준다) |
| 1 Hz 전류 샘플링 (duty 10 s 주기의 켜짐/꺼짐을 1 Hz 로 봄) | 런별 비율 산포 σ 0.077(CPU/GPU)·0.080(NPU) 중 양자화로 설명되는 몫 0.041·0.055 를 빼면 **런당 ~6 %** 가 남는다 | 랜덤 (추정) |
| 전압 근사 (`s26_energy.py` 는 창 중앙 전압 × 전류 적분) | ∫V·I dt 대비 **−0.9~+1.8 %** (중앙 0.0~0.4 %) | 계통, 작음 |
| 연료게이지 자체의 계통 편향 | **측정 불가** — 전류와 charge counter 가 같은 연료게이지에서 나온다. 외부 전력계 기준이 없다 | 계통, **미확인** |

**② 내부 일관성 검정** (전류 적분 vs charge counter, 세션 합산). 허용오차 = 랜덤 성분의 3σ = 3 × (런별 비율 σ) / √N:

| 세션 | N | 허용오차 (3σ) | 관측 편차 | 판정 |
|---|---|---|---|---|
| NPU (9/25) | 20 | ±5.4 % | −2.3 % | **PASS** — 두 게이지 값이 분해능 안에서 일치 |
| CPU/GPU (9/14~15) | 80 | ±2.6 % | −7.2 % | **FAIL** — 랜덤으로 설명 안 되는 계통 차이 ≥ ~4.6 %. 원인 미확인 |

**절대 정확도: 두 세션 모두 "미인증".** ② 내부 일관성 PASS 는 "두 읽기가 서로 맞는다"는 뜻이지 기기 전력이 참값이라는 뜻이 아니다
(같은 게이지의 공통 편향은 이 검정으로 안 보인다). J·mWh 절대값을 논문에 쓸 때는 "연료게이지 기준, 절대 정확도 미인증"을 붙인다.
데이터는 버리지 않는다.

### 10.3 ③ 차이 구분 능력

- **같은 세션 안** (같은 게이지·블록 무작위 순서): 게이지의 곱셈형 계통 편향은 양쪽에 같이 걸려 비교에서 상쇄된다고 **가정** [E].
  구분 기준 = 조건 평균 차이 > 3 × √(s₁²/n₁ + s₂²/n₂) (5반복의 런 산포로 계산, 평균값 크기와 무관)
- **세션 사이** (NPU 9/25 vs CPU/GPU 9/14~15): 세션별 계통 차이가 상쇄되지 않고, ② 에서 CPU/GPU 세션만 계통 차이가 드러났다.
  그 크기를 독립적으로 잴 방법이 없으므로 **보수적으로 단일 런 분해능의 2배 = 20 %(±9.1 % × 2, 올림)를 넘는 상대 차이만** 구분 가능하다고 둔다
- 합산은 랜덤 성분만 줄이고 **계통 편향은 줄이지 않는다** — 런을 더 모아도 세션 간 20 % 기준은 그대로다

판정 (net mJ/추론, 5런 평균) [P]:

| 비교 | 차이 | 기준 | 판정 |
|---|---|---|---|
| NPU d100 vs CPU4 d100 (세션 간) | 3.53 vs 28.9 → **−88 %** | > 20 % | 구분됨 |
| NPU d100 vs GPU d100 (세션 간) | 3.53 vs 21.9 → **−84 %** | > 20 % | 구분됨 |
| GPU d100 vs CPU4 d100 (세션 내) | −7.00 mJ (−24 %) | 3SE 2.51 mJ | 구분됨 |
| NPU d25 vs d100 (세션 내) | −0.12 mJ (−4 %) | 3SE 0.65 | **구분 안 됨** |
| NPU d50 vs d100 (세션 내) | +0.39 mJ (+11 %) | 3SE 0.50 | **구분 안 됨** |
| CPU1 d50 vs CPU4 d50 (세션 내) | −1.74 mJ (−4 %) | 3SE 5.61 | **구분 안 됨** |
| GPU d25 vs d100 (세션 내) | +0.42 mJ (+2 %) | 3SE 7.43 | **구분 안 됨** |

- 구분됨 ≠ 원인 규명. NPU↔CPU/GPU 차이는 **자원 + 엔진 + 정밀도(FP16 vs FP32) + 세션**이 섞인 관측 차이다 (`npu\results\NPU_FORMAL_RESULTS.md` §3.1)
- duty 25 조건은 런 산포가 크다 (CV 14~35 %) — load 중 켜진 시간이 짧아 1 Hz 샘플링·양자화 몫이 커진다 [E]
- net mJ 는 idle 기준선에 의존한다. idle 기준선은 세션 간 비교 불가 — 원인 미확인 (`NPU_FORMAL_RESULTS.md` §5 각주 ⁽ⁱ⁾)

---

## 부록 A. 한 슬롯의 자동 실행 순서 (orchestrator)

1. runner force-stop → D1Check quiesce (Activity STOP + 직접 service STOP)
2. 안전 preflight (`dumpsys battery` + `dumpsys thermalservice`)
3. 열 컨디셔닝 (`--start-policy`)
4. 컨디셔닝 후 안전 재확인
5. `d1_logger_v4.py clear` → `capture` 시작 → `capture started` 마커 확인
6. orchestrator 전용 logcat 모니터 시작
7. `START_RUN` → 새 run UUID `run_start` 대기
8. runner Intent 발사 (resource, threads, duration, warmup, duty, run_id, command_id, gpu_profile)
9. terminal 이벤트 대기 — logcat 우선, **baseline 60 + duration + 30초** 지나면 15초 간격 원격 JSONL 폴백
10. (성공 + 냉각 필요 시) runner force-stop → 냉각 구간
11. `STOP_RUN` (실패 시 `run-as start-foreground-service` 복구) → `run_stop` 확인
12. logger 정상 종료 확인
13. `analyze <run_dir>` → merged 산출
14. 실험 레벨 preflight 결과를 summary에 부착
15. `validate_result` — **33개 체크**(formal 모드면 최대 35개) 전부 통과해야 `completed`
16. 전 슬롯 완료 시 `exports-v2/` 자동 재생성

## 부록 B. 수동 실행 순서 (`V4_INTEGRATION.md`)

```powershell
python tools/d1_logger_v4.py clear
python tools/d1_logger_v4.py capture results
# D1Check 열고 "새 run 시작"
# Benchmark Runner 열고 CPU4 또는 GPU 선택 후 Start
#   → 60초 baseline → init/warmup/추론 → load_end → flush
#   → logger가 file_summary 보고 runner JSONL 자동 pull
# 원하는 만큼 냉각 후 D1Check run 종료 → logger 자동 종료
python tools/d1_logger_v4.py analyze results/<run_id>
```

## 부록 C. 테스트 현황

| 대상 | 개수 |
|---|---|
| Python (`tools/test_*.py`) | 130 |
| Kotlin benchmark-runner | 52 |
| Kotlin app + telemetry-contract | 16 |

도구가 검증됐다는 뜻이지 **연구 가설이 통과했다는 뜻이 아니다.**
