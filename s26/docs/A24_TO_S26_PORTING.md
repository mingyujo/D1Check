# A24 → S26 이식 가이드

근거: `mingyujo/D1Check` master `15950e5` 전체 소스 정독 (2026-09-12)
전제: [`S26_DEVICE_PROFILE.md`](S26_DEVICE_PROFILE.md)를 먼저 채웠을 것

---

## 0. 순서를 지켜야 하는 이유

```
1. 기기 판별 일반화   ← 안 하면 S26 데이터가 exports에서 전부 제외됨
2. 센서 이름 일반화   ← 안 하면 stable 정책이 슬롯을 즉시 중단시킴
3. S26 CPU/GPU 기준선 재측정
4. NPU 실행 경로 추가
5. 3자원 비교표
```

4번부터 시작하면 NPU가 돌긴 하는데 `model_eligible=false`로 걸러져 데이터가 안 남는다.

---

## 1. 기기 판별 하드코딩 — 최우선

### 문제

`tools/d1_logger_v4.py` `analyze()`:

```python
galaxy_a24 = str(capture_metadata.get("device_model", "")).upper().startswith("SM-A245")
formal_gpu_valid = (
    is_gpu and mode == "basic" and galaxy_a24
    and metadata_event.get("model_sha256") == "D95B3C5E…CFBB"
    and metadata_event.get("litert_version") == "1.4.2"
    and evidence["full_delegate"] is True
    and profile_validation["valid"] is True
    and metadata_event.get("experiment_valid") is True
    and coverage["passes_formal_requirement"] is True
)
```

### 연쇄 영향

```
device_model이 SM-A245가 아님
  → formal_gpu_valid = False
    → d1_thermal_dataset: GPU 슬롯에 "gpu_delegate_not_formally_valid" 제외 사유 추가
      → model_eligible = False
        → run_summary.csv에 행은 남지만 모델 학습에서 제외
    → orchestrator validate_result: formal 모드에서 "formal_gpu_valid" 체크 실패
      → 슬롯 status = failed → 실험 전체 halt
```

즉 **S26 GPU formal 실험은 첫 슬롯에서 멈춘다.**

### 해결 방향

기기 목록을 코드에서 빼서 **기기 프로파일 테이블**로 만든다. 시뮬레이터 설계초안의 `device_profile_<기기>.yaml` 원칙과 같다 — 숫자·식별자는 한 곳에, 코드는 모른다.

```python
# 예시 — 하드코딩 대신
FORMAL_VALIDATED_DEVICES = {
    "SM-A245": {"litert": "1.4.2", "model_sha256": "D95B3C5E…"},
    "SM-S9xx": {...},   # ← S26 실제 모델 번호로 교체
}
def device_formally_validated(model: str) -> bool:
    return any(model.upper().startswith(prefix) for prefix in FORMAL_VALIDATED_DEVICES)
```

체크:
- [ ] `formal_gpu_valid` 판정에서 기기 목록 분리
- [ ] `test_d1_logger_v4.py`에 S26 케이스 추가 (기존 A24 테스트는 그대로 통과해야 함)
- [ ] 기기별 검증 상태(`validated` / `unvalidated`)를 **요약에 명시**해서, 미검증 기기 데이터를 검증된 것처럼 쓰지 않게 한다

> ⚠️ 단순히 조건을 지우면 안 된다. 그러면 "이 기기에서 검증했다"는 의미가 사라진다. **기기별로 무엇이 검증됐는지 기록하는 구조로 바꾼다.**

---

## 2. 열 센서 이름 — 3곳이 4종을 강제

| 위치 | 코드 | 실패 시 |
|---|---|---|
| `d1_logger_v4.py` `parse_thermalservice()` | `AP`/`SKIN`/`BAT`/`PA`(+`PATHM`,`PA1THM`) | `parse_status = "missing_sensor"` → 샘플 무효 |
| `d1_experiment_orchestrator.py` `parse_hal_temperature_vector()` | `THERMAL_SENSOR_NAMES` + `THERMAL_SENSOR_ALIASES` | `ValueError` → **슬롯 즉시 중단** |
| `d1_thermal_dataset.py` `SENSORS` | 4종 튜플 | export 컬럼 구조 자체 (74/61/30 컬럼이 여기서 나옴) |

체크:
- [ ] S26 센서 이름이 4종과 그대로 맞으면 → 별칭만 추가하고 끝
- [ ] 이름만 다르면 → `THERMAL_SENSOR_ALIASES`에 매핑 추가
- [ ] 센서 개수·종류가 다르면 → **컬럼 구조가 바뀐다.** 기기별 센서 집합을 설정으로 빼고 export 스키마를 v3로 올릴지 결정 필요 (팀 합의 사항)
- [ ] 중복 이름 주의: `parse_hal_temperature_vector`는 같은 canonical 이름이 두 번 나오면 에러

---

## 3. NPU 실행 경로 추가 — 6곳

순서대로 고쳐야 컴파일이 통과한다.

### 3.1 `RunConfig.kt`

```kotlin
require(resource == CPU || resource == CPU4 || resource == GPU)   // ← NPU 추가
require(precision == ModelPrecision.FLOAT32)                      // ← INT8 허용 필요 시
require(cpuThreads == null) { "cpuThreads is only valid for CPU" } // ← NPU도 null이어야 함 (현재 else 분기가 이미 처리)
```

### 3.2 `GpuBenchmarkEngine.kt`

```kotlin
ResourceTarget.NPU -> error("NPU is reserved for a future version")  // ← 실제 delegate 생성으로 교체
```

`GPU` 분기를 그대로 참고한다: `telemetry.measured("delegate_init", "setup") { … }`로 감싸야 **초기화 비용이 span으로 기록**된다. 이게 시뮬레이터의 자원 전환 비용 입력이다.

또한 `validateModel()`이 입출력을 FLOAT32 `[1,224,224,3]` / `[1,1001]`로 강제한다. INT8 모델을 쓰면 여기도 같이 고쳐야 한다.

### 3.3 `AutomationIntent.kt`

```kotlin
val resource = when (resourceValue) {
    "CPU" -> ResourceTarget.CPU
    "CPU4" -> ResourceTarget.CPU4
    "GPU" -> ResourceTarget.GPU
    // "NPU" -> ResourceTarget.NPU     ← 없으면 Unsupported d1_resource
    else -> throw IllegalArgumentException(...)
}
val cpuThreads = when (resource) {
    …
    ResourceTarget.NPU -> error("unreachable")   // ← 실제 분기로 교체 (null 반환)
}
```

### 3.4 `MainActivity.kt` (benchmark-runner)

Spinner가 `listOf(ResourceTarget.CPU4.name, ResourceTarget.GPU.name)` 고정 → NPU 추가.

### 3.5 `d1_experiment_orchestrator.py`

| 위치 | 현재 | 필요 |
|---|---|---|
| `--resources` | `choices=("CPU","GPU")` | `"NPU"` 추가 |
| `build_conditions()` | `if resource not in {"CPU","GPU"}: raise` | NPU 분기 + `condition_id` 포맷 (`npu-d{duty:03d}` 등) |
| `runner_intent_arguments()` | CPU면 threads, 아니면 gpu_profile | NPU 분기 (profile 개념 신설 시 같이) |
| `validate_cli()` | | NPU 조건 검증 |
| `validate_result()` | `formal_gpu_valid` 체크가 GPU 전용 | NPU용 대응 체크 |

### 3.6 delegate 증거 — **가장 어려운 부분**

`delegate_evidence()`는 GPU 전용 정규식이다:
- `Created TensorFlow Lite delegate for GPU`
- `TfLiteGpuDelegateV2`
- `Replacing X out of Y node(s)` (X=Y>0)
- `Created N GPU delegate kernels` (N>0)

`test_d1_logger_v4.py`에 **NNAPI 로그는 의도적으로 `unverified` 처리**하는 테스트가 있다:

```python
def test_non_gpu_delegate_is_unverified(self):
    log = self.A24_GPU_LOG.replace("GPU", "NNAPI").replace(
        "TfLiteGpuDelegateV2", "TfLiteNnapiDelegate")
    self.assertFalse(LOGGER.delegate_evidence(log)["full_delegate"])
```

즉 **NPU 위임 판정 로직을 새로 설계해야 한다.** 필요한 것:
- [ ] S26에서 NPU delegate를 실제로 걸었을 때 어떤 logcat이 찍히는지 **원문 수집** (`adb logcat -s tflite:I TfLite:I`)
- [ ] 그 로그에서 "전체 위임 / 부분 위임 / CPU fallback"을 구분하는 패턴 확정
- [ ] `delegate_evidence()`를 자원별로 분기 (GPU 경로는 **바꾸지 말 것** — 기존 A24 판정이 깨진다)
- [ ] `NnapiDeviceProbe`의 `npu_verification: "UNVERIFIED"` 하드코딩을 실제 판정으로 교체

> **delegate 생성 성공 ≠ NPU 실행.** NNAPI는 조용히 `nnapi-reference`(CPU)로 떨어질 수 있다. 어느 디바이스에서 돌았는지까지 증거로 남겨야 한다.

### 3.7 실행 프로필 provenance

`d1_thermal_dataset.py` `execution_profile_columns()`:

```python
if str(resource).upper() != "GPU":
    return {"execution_profile_type": "cpu_not_applicable", …}   # ← NPU도 여기로 떨어짐
```

NPU 설정(어느 NNAPI 디바이스, 어떤 정밀도, allow-fp16 여부 등)을 담을 칸이 없다. `GpuDelegateProfile`과 같은 방식으로 **`NpuDelegateProfile` + canonical configuration SHA-256**을 만들어야 compat/strict처럼 서로 다른 설정이 하나로 뭉개지지 않는다.

---

## 4. 모델 / 정밀도

| 위치 | 제약 |
|---|---|
| `ModelLoader.kt` | asset 경로·MODEL_ID·SHA-256 상수 1개 고정 |
| `benchmark-runner/build.gradle.kts` `verifyBenchmarkModel` | **파일 크기 16,901,128 + SHA-256 강제**. 불일치 시 빌드 실패 |
| `RunConfig` | `require(precision == FLOAT32)` |
| `GpuBenchmarkEngine.validateModel()` | 입출력 FLOAT32 `[1,224,224,3]`/`[1,1001]` 강제 |
| `AccuracyPreflightEngine.validateInput()` | 동일 |
| `RepresentativeTensorSet.load()` | `dtype == "FLOAT32"` 강제 |

INT8 모델을 추가하려면 위 6곳 전부 다중 모델을 다루도록 바꿔야 한다. **모델 해시 검증 자체를 없애지 말 것** — 모델 바꿔치기를 막는 장치다. 모델 레지스트리(id → 경로·크기·해시·dtype) 형태로 확장하는 게 맞다.

---

## 5. 그 밖의 하드코딩

| # | 위치 | 값 | 비고 |
|---|---|---|---|
| a | `GpuBenchmarkEngine.BASELINE_MS` | 60,000 ms | 바꾸면 orchestrator `BASELINE_SECONDS = 60`도 같이. 원격 폴백 타이밍이 여기 물려 있음 |
| b | `PilotSafetyPolicy` | 배터리 35℃, status ≤1, 30~100% | S26 헤드룸 공식·임계 확인 후 결정 |
| c | `REMOTE_RUNNER_DIRECTORY` | `/sdcard/Android/data/…/files/runs` | scoped storage. `adb shell ls` 되는지 확인 |
| d | `GpuTelemetry.DEFAULT_MAX_INFERENCE_SPANS` | 250,000 | NPU가 빠르면 600초 안에 넘길 수 있음 → `buffer_limit` 주의 |
| e | `compileSdk/targetSdk 37`, `minSdk 24`, AGP 9.3.2 | | |
| f | `ACCURACY_MODEL_SHA256` 등 orchestrator 상수 | | 모델 추가 시 같이 |
| g | `REMOTE_FALLBACK_GRACE_SECONDS 30`, `REMOTE_POLL_INTERVAL_SECONDS 15` | | |

### 250,000 span 주의

A24 GPU strict는 추론당 ~132 ms → 600초에 약 4,500회. 여유가 크다.
**NPU가 추론당 2 ms라면 600초에 300,000회** → `buffer_limit`으로 실험이 무효 처리된다. S26 NPU 지연을 먼저 재고 duration·duty를 정하거나 상한을 올려야 한다.

---

## 6. 건드리면 안 되는 것

- **GPU delegate 증거 판정 로직** — A24 기존 판정이 깨진다. 자원별로 분기만 추가
- **기존 exports-v1 디렉터리** — 코드가 의도적으로 건드리지 않는다
- **schema v1 결과의 재판정** — 과거 실패를 성공으로 바꾸지 않는다 (`legacy_semantics_preserved`)
- **`energy_measurement`의 `calculation_performed: false`** — 단계 2 전에 켜지 않는다
- **대표입력 수락 임계값** — 사전 등록값이다. 관측치에 맞춰 조정 금지

---

## 7. 이식 후 검증

- [ ] 기존 Python 130개 / Kotlin 68개 테스트 전부 통과
- [ ] A24 기존 결과로 `analyze` 재실행 → 판정이 **바뀌지 않음** 확인
- [ ] S26 CPU 60초 smoke → `parse_status=ok`, 지연 통계 산출
- [ ] S26 GPU 60초 smoke → `full_delegate=true`, `formal_gpu_valid=true`
- [ ] S26 NPU 60초 smoke → 위임 증거 확보, CPU fallback 아님을 증명
- [ ] `exports-v2/` 생성 → `model_eligible=true` 행이 나오는가
- [ ] 같은 S26에서 CPU/GPU/NPU 최소 1조합씩 공정 비교 가능한가 (단계 3B 완료 기준)
