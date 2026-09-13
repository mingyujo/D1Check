# S26 기기 정보 수집 체크리스트

**코드를 고치기 전에 이 표를 전부 채운다.** 비어 있는 칸은 `미확인`으로 남기고, 추측값을 적지 않는다.
A24 열은 비교 기준이며 전부 코드/문서에서 확인된 값이다.

수집일: `____-__-__` · 수집자: `______`

---

## 1. 기기 식별

```powershell
adb shell getprop ro.product.model
adb shell getprop ro.product.device
adb shell getprop ro.product.manufacturer
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell getprop ro.build.fingerprint
adb shell getprop ro.board.platform
adb shell getprop ro.hardware
adb shell getprop ro.soc.manufacturer
adb shell getprop ro.soc.model
```

| 항목 | A24 (확인됨) | S26 |
|---|---|---|
| `ro.product.model` | `SM-A245N` | |
| `ro.product.device` | | |
| `ro.build.version.release` | Android 16 | |
| `ro.build.version.sdk` | | |
| `ro.build.fingerprint` | | |
| `ro.board.platform` | | |
| `ro.soc.manufacturer` / `ro.soc.model` | | |
| NPU 하드웨어 | **없음** | |

> ⚠️ `ro.product.model` 값이 §5의 기기 판별 어댑터에 들어간다. 정확히 받아적을 것.
> ⚠️ `adb shell getprop ro.build.fingerprint`는 정확도 preflight 캐시 키에도 쓰인다. 값이 바뀌면 preflight가 재실행된다.

---

## 2. 열 센서 — **가장 중요**

```powershell
adb shell dumpsys thermalservice
adb shell cat /sys/class/thermal/thermal_zone*/type
```

현재 코드는 `Current temperatures from HAL:` 섹션에서 **정확히 4종**을 요구한다.

| 코드가 요구하는 이름 | 허용 별칭 | S26에서 실제로 나오는 이름 |
|---|---|---|
| `AP` | — | |
| `BAT` | — | |
| `PA` | `PATHM`, `PA1THM` | |
| `SKIN` | — | |

**S26 `dumpsys thermalservice` 원문을 통째로 붙여넣을 것:**

```text
(여기에 dumpsys thermalservice 전체 출력 붙여넣기)
```

체크:
- [ ] AP/BAT/PA/SKIN 4종이 그대로 나오는가?
- [ ] 이름이 다르면 어떤 이름인가? → 별칭 테이블(`THERMAL_SENSOR_ALIASES`)에 추가 필요
- [ ] 4종에 대응하는 게 아예 없으면? → 센서 집합 자체를 기기별 설정으로 빼야 함 (`SENSORS` 상수 3곳)
- [ ] 중복 이름이 있는가? (`parse_hal_temperature_vector`는 중복을 에러로 처리)
- [ ] `Thermal Status:` 값이 파싱되는가?

| 항목 | A24 (확인됨) | Flip3 (참고) | S26 |
|---|---|---|---|
| SKIN SEVERE 임계 | | 42 ℃ (38/40/42/46/55/85) | |
| headroom 공식 | | `1 + (T_skin − 42)/30` | |
| PA 센서명 | `PA` / `PATHM` / `PA1THM` | `PATHM` / `PA1THM` | |

---

## 3. 배터리 / 전류

```powershell
adb shell dumpsys battery
```

| 항목 | A24 | S26 |
|---|---|---|
| `CURRENT_NOW` 단위 | **미검증** (mA 추정) | |
| `CHARGE_COUNTER` 단위·해상도 | 미검증 | |
| 방전 시 부호 | 음수(Android 규약) | |
| 전압 보고 여부 | `EXTRA_VOLTAGE` 있음 | |
| 갱신 주기 | | |

> Flip3는 **mA**, S22는 **µA**로 서로 달랐다. **S26도 반드시 직접 확인할 것.** 단위를 틀리면 에너지 예산 정책 전체가 왜곡된다.
> 단계 2(에너지 검증)가 끝나기 전에는 어차피 J/mWh를 계산하지 않지만, 원시값 단위는 지금 기록해둬야 한다.

---

## 4. NPU — NNAPI 디바이스 열거

**이미 코드가 있다.** Benchmark Runner를 S26에 설치하고 UI의 **"Probe NNAPI devices"** 버튼을 누른다.

```powershell
adb logcat -c
# 앱에서 "Probe NNAPI devices" 버튼 클릭
adb logcat -d -s D1NPU:I
```

출력 JSON 필드: `index`, `name`, `type_number`, `type_name`, `version`, `feature_level`, `reference_cpu`, `npu_verification`

`type_name` 값: `UNKNOWN`(0) / `OTHER`(1) / `CPU`(2) / `GPU`(3) / **`ACCELERATOR`(4)**

| index | name | type_name | version | feature_level | reference_cpu |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

체크:
- [ ] `type_name = ACCELERATOR`인 디바이스가 있는가? ← **이게 NPU 후보**
- [ ] `nnapi-reference`(CPU 폴백)만 있는 건 아닌가?
- [ ] `feature_level`이 몇인가?
- [ ] API 29 미만이면 프로브 자체가 `Unsupported` (S26은 해당 없을 것)

> `npu_verification`은 현재 `"UNVERIFIED"` 하드코딩이다. 디바이스 **열거**는 실행 **증거**가 아니다.

### 4.1 실행 경로 결정

| 후보 | 확인 방법 | S26 지원? |
|---|---|---|
| LiteRT 공식 NPU delegate | LiteRT 1.4.2 문서 + SoC 지원 목록 | |
| NNAPI delegate (`ACCELERATOR` 지정) | `NnApiDelegate` + device name 지정 | |
| Vendor delegate (Qualcomm QNN / Samsung ENN) | SDK 확보 가능 여부 | |

> 기존 조사 결론: LiteRT 공식 NPU 지원은 Snapdragon 8 Gen1+ / Exynos 2500·2600. 최소 기종 Galaxy S23.
> **S26의 실제 SoC를 §1에서 확인한 뒤 이 표를 채운다.** 지원 여부가 확정되기 전까지 실행 경로는 `미확정`으로 기록한다.

### 4.2 INT8

NPU는 보통 INT8을 요구한다. 현재 코드는 `require(precision == FLOAT32)`로 INT8을 막아둔다.

- [ ] MobileNetV1 1.0 224 **quant(INT8)** `.tflite` 확보 (SHA-256 기록)
- [ ] 같은 계열인지 확인 (서류까지 MobileNet 한 계열 유지)
- [ ] NPU가 FP16만 지원하는지 INT8만 지원하는지 확인

---

## 5. 안전 게이트 재확인

현재 코드 값이 S26에 적절한지 확인한다 (`PilotSafetyPolicy` + 호스트 `evaluate_safety`).

| 항목 | 현재 값 | S26 적절? | 근거 |
|---|---|---|---|
| Android thermal status 상한 | ≤ 1 (LIGHT) | | |
| 배터리 온도 상한 | ≤ 35.0 ℃ | | |
| 배터리 잔량 (pilot) | 30~100% | | |
| 배터리 잔량 (formal 에너지) | 30~90% | | |
| unplugged + DISCHARGING | 필수 | | |

---

## 6. 측정 환경 통제

| 항목 | 설정 |
|---|---|
| 비행기 모드 | ON |
| 와이파이 | ON (무선 adb용, 비행기 모드 켠 뒤 다시 켬) |
| 무선 디버깅 | 켜고 mDNS 항목으로 연결 |
| 화면 밝기 | 고정 (값: ____) |
| 케이스 | 제거 / 착용 (____) |
| 거치 | 평평한 면에 화면 위로 |
| 충전 | 분리 |
| 주변 온도 | ____ ℃ |

> 두 기기를 동시에 연결하면 `adb disconnect` 후 하나씩. 세션 순서: 비행기모드 → 와이파이 → 무선디버깅 → `adb connect` → 로거.

---

## 7. 설치·서명

- [ ] D1Check와 Benchmark Runner가 **같은 키로 서명**되어 있는가?
      (`com.example.d1check.permission.READ_RUN_CONTEXT`가 `protectionLevel="signature"`)
- [ ] `minSdk 24` / `targetSdk 37` / `compileSdk 37`이 S26 Android 버전과 맞는가?
- [ ] `/sdcard/Android/data/com.example.d1check.benchmarkrunner/files/runs/` 에 `adb shell ls`로 접근되는가?
      (안 되면 `run-as` 폴백 경로 확인 — debuggable 빌드 필요)
- [ ] `adb shell dumpsys thermalservice`가 권한 없이 실행되는가?

---

## 8. 최소 동작 확인 (smoke)

기기 정보를 다 채웠으면, **코드를 고치기 전에** 기존 스택 그대로 한 번 돌려서 어디서 깨지는지 본다.

```powershell
python tools/d1_logger_v4.py --serial <S26-IP:PORT> clear
python tools/d1_logger_v4.py --serial <S26-IP:PORT> capture results/S26_smoke
# D1Check 새 run 시작 → Benchmark Runner CPU4, DURATION 60s, warmup 20 → Start
# 완료 후 D1Check 종료
python tools/d1_logger_v4.py analyze results/S26_smoke/<run_id>
```

예상되는 결과와 확인할 것:

| 확인 | 예상 | 실제 |
|---|---|---|
| `raw/thermalservice.jsonl` `parse_status` | `ok`여야 정상. `missing_sensor`면 §2 문제 | |
| `merged/summary.json` `formal_gpu_valid` | CPU run이면 `null` (정상) | |
| GPU run에서 `formal_gpu_valid` | **`false`** (기기 하드코딩 때문) | |
| `delegate_evidence.full_delegate` | GPU run에서 `true`여야 함 | |
| `inference_latency.mean_ms` / `p95_ms` | 값이 나오는가 | |
| `thermal_coverage.passes_formal_requirement` | `true`여야 함 | |

---

## 9. 채운 뒤 할 일

1. 이 문서를 커밋한다 (원본 로그 포함)
2. `A24_TO_S26_PORTING.md`의 각 항목에 S26 실제값을 채운다
3. **9/18 단계0 회의**에 올릴 것:
   - S26 NPU 실행 경로 확정 여부
   - 자원·티어 정의역 (3자원 × 3티어 중 실제 지원되는 칸)
   - 조민규님과의 분담
