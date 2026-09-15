# A24 → S26 이식 가이드

근거: `mingyujo/D1Check` master `15950e5` 전체 소스 정독 (2026-09-12) + **S26 실측 (2026-09-13)**
전제: [`S26_DEVICE_PROFILE.md`](S26_DEVICE_PROFILE.md) 수집 완료 ✅

> **2026-09-13 갱신.** 실측으로 항목 2·3(센서 일반화)과 12(안전 게이트)가 **불필요**로 판정됐고, NPU 항목은 규모가 커졌다. 아래는 갱신본이다.

---

## 0. 순서

```
0. pilot 스모크 (코드 수정 없음)  ← 지금 여기. 전체 체인이 S26에서 도는지 확인
1. 기기 판별 일반화                ← formal 모드와 exports-v2 적격성에 필요
2. S26 CPU/GPU 기준선 재측정
3. NPU 실행 엔진 추가 (별도 설계)
4. 3자원 비교표
```

**0번은 코드를 안 고쳐도 된다.** `formal_gpu_valid`는 `resource == GPU` **and** `mode == formal`일 때만 판정에 쓰이고, pilot `validate_result`는 이를 확인하지 않는다. 그래서 APK만 빌드·설치하면 CPU/GPU pilot 60초 스모크가 바로 돈다.

---

## 1. 기기 판별 하드코딩 — 필요 ⚠️

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
device_model = SM-S942N (≠ SM-A245)
  → formal_gpu_valid = False
    → d1_thermal_dataset: GPU 슬롯에 "gpu_delegate_not_formally_valid" 제외 사유
      → model_eligible = False → exports-v2에서 모델 학습 제외
    → orchestrator validate_result: formal 모드 GPU에서 체크 실패
      → 슬롯 failed → 실험 전체 halt
```

**영향 범위 (실측 확인 후 정정)**
- pilot 모드 CPU 스모크: 영향 **없음** (`formal_gpu_valid`가 CPU면 `null`)
- pilot 모드 GPU 스모크: `validate_result`는 통과. 단 exports-v2를 돌리면 그 슬롯은 `model_eligible=false`
- formal 모드 GPU: **첫 슬롯에서 halt**

### 해결 방향

기기 목록을 코드에서 빼고 **기기 프로파일 테이블**로. 시뮬레이터 설계의 `device_profile_<기기>.yaml` 원칙과 같다 — 식별자는 한 곳에, 코드는 모른다.

```python
# 예시 — 하드코딩 대신
FORMAL_VALIDATED_DEVICES = {
    "SM-A245": {"litert": "1.4.2", "model_sha256": "D95B3C5E…"},
    "SM-S942": {"litert": "1.4.2", "model_sha256": "D95B3C5E…"},   # S26, 2026-09-13 프로파일 확보
}
def device_formally_validated(model: str) -> bool:
    return any(model.upper().startswith(p) for p in FORMAL_VALIDATED_DEVICES)
```

체크:
- [ ] `formal_gpu_valid` 판정에서 기기 목록 분리
- [ ] `test_d1_logger_v4.py`에 S26 케이스 추가 (기존 A24 테스트는 그대로 통과해야 함)
- [ ] 기기별 검증 상태(`validated` / `unvalidated`)를 요약에 명시 — 미검증 기기 데이터를 검증된 것처럼 쓰지 않게

> ⚠️ 조건을 그냥 지우면 안 된다. "이 기기에서 검증했다"는 의미가 사라진다. **기기별로 무엇이 검증됐는지 기록하는 구조로** 바꾼다.

---

## 2·3. 열 센서 이름 — **불필요** ✅ (실측으로 해소)

S26 HAL이 내놓는 이름:

```
AP 29.1 / BAT 28.0 / CP 28.8 / PA 28.9 / SKIN 30.2 / SUBBAT 0.0 / USB 27.6
```

코드가 요구하는 `AP` `BAT` `PA` `SKIN`이 **정확히 그 이름으로** 다 있다. A24에서 필요했던 `PATHM`/`PA1THM` 별칭도 불필요.
추가로 나오는 `CP`·`USB`·`SUBBAT`은 `THERMAL_SENSOR_ALIASES`에 없어서 자동으로 무시된다. `SUBBAT`이 `BAT`과 같은 mType=2지만 매칭은 이름 기준이라 중복 에러도 안 난다.

**3곳(`parse_thermalservice`, `parse_hal_temperature_vector`, `SENSORS`) 모두 무수정 통과.**

남은 주의 하나 — 파서를 건드릴 때만:
`Current temperatures from HAL:` **앞에** `Cached temperatures:` 블록이 있고 같은 이름에 오래된 값이 들어 있다(캐시 AP=38.6 vs 실시간 29.1). 현재 정규식은 올바른 섹션만 잡지만, 수정 시 이 함정을 깨지 말 것.

---

## 4. NPU 실행 경로 — 필요, **재설계 규모** ⚠️⚠️

### 4.1 실측으로 드러난 상황

| 확인 항목 | 결과 |
|---|---|
| NPU 하드웨어 | ✅ `/dev/npu0_throughput`, `npu1_`, `unpu_`, `dsp_` |
| NNAPI 런타임 | ✅ `/apex/com.android.neuralnetworks/lib64/libneuralnetworks.so`, `public.libraries.txt` 등재, feature level 7 |
| NNAPI 벤더 HAL | ❌ `lshal`에 neural 서비스 없음 → `nnapi-reference`(CPU)만 나올 가능성 높음 |
| Samsung ENN | ✅ `libenn_public_api_cpp.so` 등 **public 등재**, `vendor.samsung_slsi.hardware.enn_aidl-V1` |
| LiteRT 공식 지원 | ✅ Exynos 2600(E9965)은 지원 SoC, API 36 요구조건 충족 |

**결론: NNAPI는 실행 경로로 못 쓴다.** 프로브는 돌지만 NPU에 안 닿는다. 실제 경로는 LiteRT NPU(`CompiledModel` + Exynos AI LiteCore) 또는 ENN 직접 호출이다.

### 4.2 왜 "자원 하나 추가"가 아닌가

| | 현재 (CPU/GPU) | NPU |
|---|---|---|
| API | `org.tensorflow.lite.Interpreter` | **`CompiledModel`** (LiteRT Next) |
| 의존성 | `litert 1.4.2` + `litert-gpu` | `com.google.ai.edge.litert:litert` (Next) |
| 실행 | `interpreter.run(input, output)` | 다른 호출 형태 |
| 측정 경계 | `run()` 전후 `elapsedRealtimeNanos()` | **다시 정의 필요** |
| 런타임 배포 | APK에 포함 | **Google Play for On-device AI (PODAI)** — 사이드로드 가능 여부 미확인 |

`GpuBenchmarkEngine`에 `when(resource)` 분기 하나 추가하는 걸로 안 된다. **두 번째 실행 엔진**이 필요하고, 지연 측정 경계와 위임 증거 판정을 새로 설계해야 한다.

체크:
- [ ] 사이드로드 debug APK에서 LiteRT NPU 런타임이 로드되는지 먼저 확인 (**최대 리스크**)
- [ ] `CompiledModel` 기준 타이밍 경계 정의 — 현재와 동등하게 비교 가능한 지점으로
- [ ] AOT 컴파일 여부 결정 (선택이지만 초기화 시간에 영향 → 전환비용 측정에 관계)
- [ ] ENN 직접 호출을 대안으로 평가 (public API가 열려 있음)

### 4.3 그래도 손대야 할 6곳

`RunConfig.init`(resource/precision require) → `GpuBenchmarkEngine`(`error("NPU is reserved…")`) → `AutomationIntentParser`(`"NPU"` 매핑 없음) → Runner `MainActivity` Spinner → orchestrator(`--resources` choices, `build_conditions`, `runner_intent_arguments`, `validate_result`) → `execution_profile_columns`(GPU 외 전부 `cpu_not_applicable`)

### 4.4 delegate 증거 — 새로 설계

`delegate_evidence()`는 GPU 전용 정규식이고, `test_d1_logger_v4.py`가 **NNAPI 로그를 의도적으로 `unverified` 처리**한다.

```python
def test_non_gpu_delegate_is_unverified(self):
    log = self.A24_GPU_LOG.replace("GPU", "NNAPI").replace(
        "TfLiteGpuDelegateV2", "TfLiteNnapiDelegate")
    self.assertFalse(LOGGER.delegate_evidence(log)["full_delegate"])
```

- [ ] S26에서 NPU 실행 시 실제 logcat 원문 수집 (`adb logcat -s tflite:I TfLite:I LiteRT:I ENN:I`)
- [ ] 전체 위임 / 부분 위임 / CPU 폴백 구분 패턴 확정
- [ ] `delegate_evidence()`를 자원별로 분기 — **GPU 경로는 바꾸지 말 것** (A24 기존 판정이 깨진다)

---

## 5. 안전 게이트 — **불필요** ✅ (실측으로 해소)

| 항목 | 코드 값 | S26 |
|---|---|---|
| thermal status 상한 | ≤ 1 (LIGHT) | LIGHT = SKIN 38.0℃ — 여유 있음 |
| 배터리 온도 상한 | ≤ 35.0 ℃ | 관측 24.4~30.8℃ |
| 잔량 pilot / formal | 30~100% / 30~90% | 그대로 적절 |

그대로 쓴다.

---

## 6. 모델 / 정밀도 (KS-D·NPU 공통)

| 위치 | 제약 |
|---|---|
| `ModelLoader.kt` | asset 경로·MODEL_ID·SHA-256 상수 1개 고정 |
| `benchmark-runner/build.gradle.kts` `verifyBenchmarkModel` | **파일 크기 16,901,128 + SHA-256 강제**, 불일치 시 빌드 실패 |
| `RunConfig` | `require(precision == FLOAT32)` |
| `GpuBenchmarkEngine.validateModel()` | 입출력 FLOAT32 `[1,224,224,3]`/`[1,1001]` 강제 |
| `AccuracyPreflightEngine.validateInput()` | 동일 |
| `RepresentativeTensorSet.load()` | `dtype == "FLOAT32"` 강제 |

**모델 해시 검증 자체를 없애지 말 것** — 모델 바꿔치기를 막는 장치다. 모델 레지스트리(id → 경로·크기·해시·dtype)로 확장하는 게 맞다.

---

## 7. 그 밖

| # | 위치 | 값 | S26 판정 |
|---|---|---|---|
| a | `BASELINE_MS` | 60,000 ms | 그대로. 바꾸면 orchestrator `BASELINE_SECONDS`도 같이 |
| b | `REMOTE_RUNNER_DIRECTORY` | `/sdcard/Android/data/…/files/runs` | **스모크에서 확인 필요** |
| c | `DEFAULT_MAX_INFERENCE_SPANS` | 250,000 | **NPU 지연 측정 후 재검토** — 2ms/추론이면 600초에 300,000회로 `buffer_limit` |
| d | `compileSdk/targetSdk 37`, `minSdk 24` | | ✅ SDK Platform 37 설치돼 있음, 기기는 SDK 36 |
| e | CPU 스레드 축 1·2·4 | A24 8코어 기준 | **S26은 10코어** (2.76×6 / 3.26×3 / 3.80×1) → 8 추가 여부 단계0 결정 |
| f | 냉각 중 화면 유지 | 없음 | **추가 권장** — runner force-stop 후 포그라운드 Activity가 없어 화면이 꺼지고 냉각 곡선이 바뀐다. orchestrator에서 D1Check를 다시 앞으로 (`am start -n com.example.d1check/.MainActivity`) 한 줄. wake lock은 전력을 바꾸므로 쓰지 말 것 |
| g | 전류 단위 | 미검증 | **µA·방전 음수 확정** (단계 2 정식 검증은 남음) |

---

## 8. 건드리면 안 되는 것

- **GPU delegate 증거 판정 로직** — A24 기존 판정이 깨진다. 자원별 분기만 추가
- **기존 exports-v1 디렉터리** — 코드가 의도적으로 건드리지 않는다
- **schema v1 결과의 재판정** — 과거 실패를 성공으로 바꾸지 않는다 (`legacy_semantics_preserved`)
- **`energy_measurement`의 `calculation_performed: false`** — 단계 2 정식 검증 전에 켜지 않는다. 단위를 알게 된 것과 검증된 것은 다르다
- **대표입력 수락 임계값** — 사전 등록값이다

---

## 9. 이식 후 검증

- [ ] 기존 Python 130개 / Kotlin 68개 테스트 전부 통과
- [ ] A24 기존 결과로 `analyze` 재실행 → 판정이 **바뀌지 않음** 확인
- [ ] S26 CPU 60초 스모크 → `parse_status=ok`, 지연 통계 산출
- [ ] S26 GPU 60초 스모크 → `full_delegate=true`, `formal_gpu_valid=true`
- [ ] S26 NPU 60초 스모크 → 위임 증거 확보, CPU 폴백 아님을 증명
- [ ] `exports-v2/` 생성 → `model_eligible=true` 행이 나오는가
- [ ] 같은 S26에서 CPU/GPU/NPU 최소 1조합씩 공정 비교 가능한가 (단계 3B 완료 기준)
