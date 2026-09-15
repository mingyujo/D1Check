# S26 기기 프로파일 — 수집 완료

수집일: **2026-09-13** · 수집자: 영훈 · 방법: `s26_collect.bat` + `s26_probe_npu.bat` (USB, 읽기 전용)
원본 로그: `measure/s26/device/00~10_*.txt`

A24 열은 비교 기준이며 코드/문서에서 확인된 값이다.

---

## 1. 기기 식별 ✅

| 항목 | A24 (기준) | **S26 (실측)** |
|---|---|---|
| `ro.product.model` | `SM-A245N` | **`SM-S942N`** |
| `ro.product.device` | — | `m1s` |
| `ro.product.name` | — | `m1sksx` |
| `ro.product.manufacturer` | samsung | samsung |
| `ro.build.version.release` | 16 | **16** |
| `ro.build.version.sdk` | — | **36** |
| `ro.build.fingerprint` | — | `samsung/m1sksx/m1s:16/BP4A.251205.006/S942NKSS4AZHA_OKR4AZHA:user/release-keys` |
| `ro.board.platform` | — | `erd9965` |
| `ro.hardware` | — | `s5e9965` |
| `ro.soc.manufacturer` / `ro.soc.model` | — | Samsung / **`s5e9965` = Exynos 2600** |
| `ro.product.cpu.abi` | — | `arm64-v8a` |
| adb serial | — | `R3KL3039J1V` |
| NPU 하드웨어 | **없음** | **있음** (§4) |

> `SM-S942N` 문자열이 `d1_logger_v4.py` 기기 판별 어댑터에 들어갈 값이다.
> `fingerprint`는 accuracy preflight 캐시 키에도 쓰인다. OS 업데이트로 바뀌면 preflight가 재실행된다.

### CPU — 10코어 (A24는 8코어)

| 코어 | 클럭 |
|---|---|
| cpu0–5 | 2,764 MHz |
| cpu6–8 | 3,264 MHz |
| cpu9 | 3,801 MHz |

`CPU part 0xd8b`, ARMv9 (SVE2 / SME2 / i8mm / bf16).
→ CPU 스레드 축을 A24의 1·2·4로 그대로 쓸지, 8을 추가할지 **단계0에서 결정 필요**.

---

## 2. 열 센서 ✅ — 코드 수정 불필요

`dumpsys thermalservice`의 `Current temperatures from HAL:` 섹션 (idle 상태):

```
AP 29.1 / BAT 28.0 / CP 28.8 / PA 28.9 / SKIN 30.2 / SUBBAT 0.0 / USB 27.6
```

| 코드가 요구하는 이름 | S26 실측 | 판정 |
|---|---|---|
| `AP` | `AP` (mType=0) | ✅ 그대로 |
| `BAT` | `BAT` (mType=2) | ✅ 그대로 |
| `PA` | `PA` (mType=5) | ✅ 별칭 불필요 (A24는 PATHM/PA1THM 필요했음) |
| `SKIN` | `SKIN` (mType=3) | ✅ 그대로 |

**추가로 나오는 3종**: `CP`(mType=12, 모뎀), `USB`(mType=4), `SUBBAT`(mType=2, 값 0.0)
→ `THERMAL_SENSOR_ALIASES`에 없으므로 `parse_hal_temperature_vector`가 `continue`로 무시한다. `SUBBAT`이 `BAT`과 같은 mType=2지만 매칭은 **이름 기준**이라 중복 에러가 나지 않는다.

**결론: 센서 이름 일반화 작업(이식 항목 2·3)은 S26에서 필요 없다.** 3곳 모두 그대로 통과한다.

### 임계값

```
SKIN mHotThrottlingThresholds = [38.0, 40.0, 42.0, 45.0, 47.0, 60.0, 90.0]
BAT  mHotThrottlingThresholds = [NaN, NaN, NaN, NaN, NaN, 55.0, 85.0]
Temperature headroom thresholds = [NaN, 0.8333333, 0.9, 1.0, 1.0666667, 1.5, 2.5]
```

| severity | SKIN ℃ | headroom |
|---|---|---|
| LIGHT | 38.0 | 0.833 |
| MODERATE | 40.0 | 0.900 |
| **SEVERE** | **42.0** | **1.000** |
| CRITICAL | 45.0 | 1.067 |
| EMERGENCY | 47.0 | 1.500 |
| SHUTDOWN | 60.0 / 90.0 | 2.500 |

**headroom 1.0 = SKIN 42.0℃** — Flip3와 같은 앵커점이다. 다만 구간별 기울기가 달라 Flip3의 `1+(T−42)/30` 같은 단일 선형식은 성립하지 않는다. 위 임계표를 그대로 룩업으로 쓰는 편이 정확하다.

`Current cooling devices from HAL:` 은 **비어 있다** (A24는 `thermal-cpufreq-0` 있었음).

> ⚠️ 파서 주의: `Current temperatures from HAL:` **앞에** `Cached temperatures:` 블록이 있고 같은 센서 이름에 다른(오래된) 값이 들어 있다. 예: 캐시 AP=38.6 vs 실시간 AP=29.1. 현재 정규식은 `Current temperatures from HAL` 이후만 잡으므로 정상이지만, 파서를 건드릴 때 이 함정을 기억할 것.

---

## 3. 배터리 / 전류 ✅ — 단위 사실상 확정

`dumpsys battery` 및 `ACTION_BATTERY_CHANGED` 이력에서 확인.

| 항목 | A24 | **S26** |
|---|---|---|
| `current_now` 단위 | 미검증 (mA 추정) | **µA (마이크로암페어)** |
| 방전 시 부호 | — | **음수** (Android 규약과 일치) |
| 충전 시 부호 | — | 양수 |
| `charge_counter` 단위 | 미검증 | **µAh** |
| 전압 | — | `voltage` mV (예: 4163) |
| 배터리 용량 추정 | — | **≈ 4,315 mAh** (cc 3,236,175 µAh @ 75%) |
| 관측 최대 충전 전류 | — | 5,315,625 µA = **5.32 A** |

### 교차검증 (60분 방전 구간)

| 방법 | 값 |
|---|---|
| `charge_counter` 감소량 192,375 µAh ÷ 0.9995 h | **192.5 mA** |
| `current_avg` 시간가중 평균 | **237.9 mA** |
| 비율 | **1.24×** |

두 독립 경로가 같은 자릿수(수백 mA)로 수렴 → **µA 단위 확정**. mA였다면 192,000 mA가 되어 불가능하다.

1.24× 차이는 `current_avg`가 (a) 평활화된 레지스터이고 (b) 이벤트 발생 시점에만 기록돼 변화가 큰 순간에 편향되기 때문으로 보인다. **단계 2 정식 검증**(1초 균일 샘플링 + `BATTERY_PROPERTY_CURRENT_NOW` 적분 vs charge_counter 차분)은 여전히 필요하다. 다만 단위·부호 규약은 이제 확정으로 봐도 된다.

코드의 `current_now_discharge_magnitude_ua()`가 가정하는 규약(양수면 충전으로 간주해 예외)과 **일치한다.**

### 접근 불가

`/sys/class/power_supply/`, `/sys/class/thermal/thermal_zone*/temp` 는 SELinux로 shell에서 읽히지 않는다. **HAL(`dumpsys`) 경로만 사용 가능**하며, 코드가 이미 그렇게 되어 있으므로 문제없다.

---

## 4. NPU ✅ 하드웨어 있음 — 단 실행 경로는 재설계 필요

### 4.1 하드웨어 증거

```
/dev/npu0_throughput      /dev/npu0_throughput_max
/dev/npu1_throughput      /dev/npu1_throughput_max
/dev/npu_throughput       /dev/npu_throughput_max
/dev/npucon_throughput    /dev/unpu_throughput
/dev/dsp_throughput       /dev/memlog-4-npu-fil
```
NPU 2코어 + micro-NPU + DSP. 전부 root/system 소유라 앱에서 직접 접근 불가(정상).

### 4.2 NNAPI — 런타임은 살아있음, 그러나 벤더 드라이버 없음

```
/apex/com.android.neuralnetworks/lib64/libneuralnetworks.so   4,823,528 bytes
public.libraries.txt:  libneuralnetworks.so nopreload
[persist.device_config.nnapi_native.current_feature_level]: [7]
```

- 라이브러리가 **APEX 모듈**에 있고 `public.libraries.txt`에 등재 → 앱에서 `dlopen("libneuralnetworks.so")` **가능**
- → 레포의 `nnapi_probe.cpp` / "Probe NNAPI devices" 버튼은 **그대로 동작할 것**
- 그러나 `lshal | grep neural` 결과 **NNAPI HAL 서비스가 등록돼 있지 않다**
- → NNAPI 디바이스 열거 시 `nnapi-reference`(CPU 폴백)만 나올 가능성이 높다. 코드의 `reference_cpu` 플래그가 이걸 잡는다.
- NNAPI는 Android 15에서 deprecated. **NPU 실행 경로로 쓸 수 없다고 보는 게 안전하다.**

> 프로브를 실제로 눌러 `type_name=ACCELERATOR`가 나오는지 확인해 결론을 확정할 것. 결과는 `device/09_nnapi_probe.txt`에 남긴다.

### 4.3 Samsung ENN — 앱에서 접근 가능한 실제 NPU 스택

`public.libraries.txt`에 **등재됨** (= 앱이 직접 dlopen 가능):
```
libenn_public_api_cpp.so
libenn_public_api_cpp_lib.so
libenn_user.samsung_slsi.so
libenn_user_lib.so
```

`/vendor/lib64/` 구현체:
```
libenn_engine.so          libenn_model.so         libenn_wrapper.so
libenn_user_driver_cpu.so libenn_user_driver_gpu.so
libenn_user_driver_unified.so
libenn_common_utils.so    libenn_cpu_operators.so
vendor.samsung_slsi.hardware.enn_aidl-V1-ndk.so    ← ENN AIDL HAL
vendor.samsung_slsi.hardware.enn_aux@1.0.so
```
그 외: `/system/lib64/libneural.snap.samsung.so`

### 4.4 LiteRT 공식 경로

Exynos 2600(E9965)은 LiteRT NPU **공식 지원 SoC**이고 요구 조건 Android API 36을 이 기기가 정확히 충족한다.

| 항목 | 값 | 현재 코드와의 차이 |
|---|---|---|
| API | **`CompiledModel`** (LiteRT Next) | 현재는 `Interpreter.run()` — **엔진 자체가 다름** |
| 의존성 | `com.google.ai.edge.litert:litert` (LiteRT Next) | 현재 `litert 1.4.2` + gpu-api/gpu |
| 가속기 | Samsung Exynos AI LiteCore | GPU delegate와 다른 계층 |
| AOT 컴파일 | 선택(권장) | — |
| 런타임 배포 | **Google Play for On-device AI (PODAI)** | 사이드로드 APK 가능 여부 **미확인 — 리스크** |

관련 패키지 설치돼 있음: `com.google.android.aicore`, `com.samsung.android.aicore`, `com.google.android.ondevicepersonalization.services`

**결론: NPU는 "runner에 자원 하나 추가"가 아니라 별도 실행 엔진 추가다.** 측정 경계(`interpreter.run()` 전후 타이밍)도 `CompiledModel` 기준으로 다시 정의해야 한다. 조민규님과 분담 조율 시 이 점을 반드시 공유할 것.

### 4.5 INT8

- [ ] MobileNetV1 1.0 224 **quant(INT8)** `.tflite` 확보 (SHA-256 기록)
- [ ] Exynos AI LiteCore가 요구하는 정밀도 확인 (INT8 전용인지, FP16도 되는지)
- 현재 코드는 `require(precision == FLOAT32)`로 INT8 차단 중

---

## 5. 안전 게이트 — 값 그대로 사용 가능

| 항목 | 코드 값 | S26 적절? |
|---|---|---|
| Android thermal status 상한 | ≤ 1 (LIGHT) | ✅ LIGHT = SKIN 38.0℃, 여유 있음 |
| 배터리 온도 상한 | ≤ 35.0 ℃ | ✅ 관측 24.4~30.8℃ |
| 배터리 잔량 (pilot) | 30~100% | ✅ |
| 배터리 잔량 (formal) | 30~90% | ✅ |
| unplugged + DISCHARGING | 필수 | ⚠️ **USB 연결 시 실측 불가 → 무선 adb 필수** |

---

## 6. 측정 환경 통제

| 항목 | 설정 |
|---|---|
| 비행기 모드 | ON (USB adb는 영향 없음) |
| 무선 adb | 실측 시 **필수** (USB = plugged = 안전 게이트 거부) |
| 화면 자동 꺼짐 | `adb shell settings put system screen_off_timeout 86400000` → 끝나고 원복 |
| 화면 밝기 | 고정 (값: ____) |
| 케이스 | ____ |
| 거치 | 평평한 면, 화면 위로 |
| 주변 온도 | ____ ℃ |
| ⚠️ 일상 사용 폰 | 백그라운드 앱 경합 — S22 사례에서 p95 14배. 범위 한계로 명시 필요 |

---

## 7. 빌드 환경

| 항목 | 상태 |
|---|---|
| adb | ✅ `C:\Users\rhoyo\AppData\Local\Android\Sdk\platform-tools\adb.exe` |
| Android SDK Platform 37 | ✅ `platforms\android-37.0` (compileSdk 37 충족) |
| **NDK** | ❌ **미설치** — `benchmark-runner`의 `nnapi_probe.cpp` 빌드에 필요 |
| **CMake** | ❌ **미설치** — 동일 |
| 소스 | ✅ `C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4` (master 클론) |
| 서명 | 두 APK 모두 같은 프로젝트의 debug 키 → signature permission 충족 |

→ SDK Manager → SDK Tools → **NDK (Side by side)** + **CMake** 설치 필요.

---

## 8. 코드 수정 판정

| 이식 항목 | S26 판정 |
|---|---|
| 1. 기기 판별 하드코딩 (`SM-A245`) | **필요** — formal 모드와 exports-v2 적격성에 영향. pilot CPU/GPU 스모크에는 불필요 |
| 2·3. 센서 이름 일반화 | **불필요** — AP/BAT/PA/SKIN 그대로 나옴 |
| 4~7. NPU 자원 추가 | **필요 + 재설계** — CompiledModel 엔진 별도 |
| 8. NPU delegate 증거 | **필요** — ENN 또는 LiteRT NPU 기준으로 새로 설계 |
| 9·10. NPU 프로필 provenance | **필요** |
| 11. 모델 레지스트리 (INT8) | 필요 (KS-D) |
| 12. 안전 게이트 임계 | **불필요** — 그대로 적절 |
| 13. baseline 60초 | 그대로 |
| 14. `/sdcard/...` 경로 | 스모크에서 확인 |
| a. 250,000 span 상한 | NPU 지연 측정 후 재검토 |
| 냉각 중 화면 유지 | 추가 권장 (orchestrator에서 D1Check 재포그라운드) |

**중요: pilot 모드 CPU/GPU 스모크 런은 코드 수정 없이 지금 바로 가능하다.**
`formal_gpu_valid`는 GPU + formal 모드에서만 판정에 쓰이고, pilot `validate_result`는 이를 확인하지 않는다.
