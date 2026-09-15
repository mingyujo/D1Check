# s26/patches — 본체 코드에 가한 변경 기록

S26 측정을 위해 `benchmark-runner`에 가한 변경을 여기에 전부 적는다.
**적용·복구는 손으로 하지 않는다.** 반드시 스크립트를 쓴다.

```
cd s26\tools
s26_patch_gpu_gate.bat --check     :: 현재 상태만 확인
s26_patch_gpu_gate.bat             :: 적용
s26_patch_gpu_gate.bat --revert    :: 원복 (바이트 단위로 원본 복귀)
```

스크립트는 바꿀 문자열이 **정확히 1회** 존재할 때만 쓴다. 하나라도 어긋나면
아무 파일도 건드리지 않고 멈춘다. 두 번 실행해도 안전하다.

---

## 패치 1 — `s26-compat-list-advisory-v1` (2026-09-13)

### 증상

S26에서 GPU 런이 **항상** setup 단계에서 죽었다. 추론은 한 번도 실행되지 않았다.

```
delegate_init  status=error  latency=33.16 ms
detail: java.lang.IllegalStateException:
        GPU delegate is not supported; GPU experiment cannot start
```

`accuracy preflight`도 같은 이유로 실패해서 오케스트레이터가 CPU 런까지
진행하지 못하고 중단했다.

```
OrchestratorError: runner accuracy preflight failed:
  IllegalStateException: GPU delegate is not supported;
  output equivalence preflight cannot run
```

근거 로그: [`../device/12_gpu_failure.txt`](../device/12_gpu_failure.txt)

### 원인

LiteRT 1.4.2에 **바이너리로 내장된 기기 허용목록**(`CompatibilityList`)이
Exynos 2600을 모른다. LiteRT 1.4.2가 이 SoC보다 먼저 빌드됐기 때문이다.
목록에 없으면 `isDelegateSupportedOnThisDevice`가 false를 돌려준다.

기존 코드는 이 값을 **치명적 오류로 취급**했다.

```kotlin
val compatibility = CompatibilityList()
check(compatibility.isDelegateSupportedOnThisDevice) {
    "GPU delegate is not supported; GPU experiment cannot start"
}
GpuDelegate(config.gpuDelegateProfile.options())   // 도달하지 못함
```

`delegate_init`이 33 ms 만에 끝난 것이 증거다. 목록을 조회하고 곧바로 거부했고
`GpuDelegate()` 생성자는 호출조차 되지 않았다.

### 반증

기기에 OpenCL이 **있다**. TFLite GPU 델리게이트가 쓰는 바로 그 백엔드다.

```
/vendor/lib64/libOpenCL.so
/vendor/lib64/libOpenCL_samsung.so
/system/lib64/libOpenCL.so
```

즉 "S26이 GPU 추론을 못 한다"가 아니라 "LiteRT 1.4.2가 S26을 모른다"이다.
허용목록은 앱 개발자를 위한 **휴리스틱**이지 하드웨어 능력 선언이 아니다.

### 변경 내용

허용목록의 판정을 **기록하고 진행**한다. 실제 판정은 `GpuDelegate()` 생성자가 한다.

| 파일 | 성격 | 변경 |
|---|---|---|
| `.../benchmarkrunner/s26/GpuCompatibilityPolicy.kt` | **신규 (S26 소유)** | 목록 판정을 읽고 기록. 중단하지 않음 |
| `.../benchmarkrunner/GpuBenchmarkEngine.kt` | 기존 | import 1줄, 변수 1줄, `check` 블록 → 호출 1줄, 메타데이터 병합 1블록 |
| `.../benchmarkrunner/AccuracyPreflightEngine.kt` | 기존 | import 1줄, `check` 블록 → 호출 1줄 |

기존 파일에서 실제로 지운 로직은 **`check()` 두 곳**뿐이다.

### 왜 측정 신뢰도가 떨어지지 않는가

허용목록을 **더 강한 검증으로 대체**하는 것이지 검증을 없애는 게 아니다.
GPU에서 실제로 돌았는지는 기존 장치들이 그대로 판정한다.

1. **`delegate_evidence`** — logcat에서 직접 확인
   - `Created TensorFlow Lite delegate for GPU`
   - `TfLiteGpuDelegateV2`
   - `Created N GPU delegate kernels`
   - `Replacing N out of M nodes` → 전 노드 대체 시에만 `full_delegate: true`
2. **출력 동등성 preflight** — CPU 결과와 GPU 결과를 atol/rtol로 수치 비교
3. **`gpu_compatibility_list_supported`** — 목록이 뭐라고 했는지가 모든 런 기록에 남는다

허용목록은 "돌려보기 전의 추측"이고, 위 셋은 "돌린 뒤의 증거"다.

### 다른 기기에 미치는 영향

**없다.** Galaxy A24(Mali-G57)는 허용목록에 있어서 판정이 `true`다.
분기가 사라졌을 뿐 실행 경로가 같고, 메타데이터 필드 4개만 추가된다.
조민규 측 A24 결과는 재측정 없이 그대로 유효하다.

### 런 기록에 새로 남는 필드

`merged/summary.json`과 러너 메타데이터에 다음이 추가된다.

| 필드 | 값 | 뜻 |
|---|---|---|
| `gpu_compatibility_policy_id` | `s26-compat-list-advisory-v1` | 이 정책의 버전 |
| `gpu_compatibility_list_supported` | `true` / `false` / `null` | 허용목록의 판정. S26은 `false` 예상 |
| `gpu_compatibility_list_query_error` | 문자열 또는 `null` | 목록 조회 자체가 실패한 경우 |
| `gpu_compatibility_list_enforced` | 항상 `false` | 판정을 강제하지 않았음을 명시 |

`false`인 런은 보고서에서 **"허용목록 미등재 기기에서 측정함"**으로 표기하고,
`delegate_evidence.full_delegate`를 근거로 GPU 실행을 주장한다.

### 남은 위험

`GpuDelegate()` 생성자가 터질 가능성은 그대로 있다. 그 경우 예외 메시지가
`delegate_init`에 기록되며, 그것은 **"Exynos 2600에서 LiteRT 1.4.2 GPU
델리게이트는 실제로 동작 불가"**라는 별개의 측정 결과가 된다.
어느 쪽이든 기록이 남는다.

### 적용 후 해야 할 것

1. Android Studio에서 **`benchmark-runner` 재빌드 후 폰에 설치**
2. `s26_pilot.bat dry` → `s26_pilot.bat`
3. 결과에서 확인할 것
   - `gpu_compatibility_list_supported` — 예상 `false`
   - `delegate_evidence.gpu_delegate_created` — `true`여야 GPU가 실제로 붙은 것
   - `delegate_evidence.full_delegate` — `true`여야 전 노드가 GPU로 갔다는 뜻
   - `delegate_evidence.failure_or_fallback_evidence` — 비어 있어야 함

---

## 패치 2 — `s26-formal-gpu-device-list-v1` (2026-09-13)

### 증상

`--mode formal`로 돌리면 **GPU 런이 예외 없이 실패**한다.

```
validate_result() -> checks["formal_gpu_valid"] = False
  -> OrchestratorError: result validation failed: formal_gpu_valid
  -> 슬롯 failed -> 실험 halt
```

파일럿 GPU 런에서도 이미 `formal_gpu_valid: false`가 확인됐다.

### 원인

`tools/d1_logger_v4.py`의 `formal_gpu_valid`는 아홉 조건의 곱이다. 여덟은 그 런에
대한 증거이고, 아홉째가 기기 모델 하드코딩이다.

```python
galaxy_a24 = str(capture_metadata.get("device_model","")).upper().startswith("SM-A245")
formal_gpu_valid = (is_gpu and mode == "basic" and galaxy_a24 and ...)
```

**이건 버그가 아니다.** "내가 GPU 경로를 검증한 기기의 결과만 인증하겠다"는 의도적
범위 표시다. 검증하지 않은 하드웨어를 인증하지 않는 것은 옳은 태도다.

### 왜 바꾸는가

S26이 A24와 **같은 증거**를 냈다. (근거: [`../results/PILOT_RESULTS.md`](../results/PILOT_RESULTS.md) §5, §6)

| 증거 | S26 값 |
|---|---|
| `gpu_delegate_created` | `true` |
| `gpu_delegate_type` | `TfLiteGpuDelegateV2` |
| `gpu_delegate_kernel_count` | 1 |
| `replaced_nodes / total_nodes` | 31 / 31 |
| `full_delegate` | `true` |
| `verification` | **`verified`** |
| `failure_or_fallback_evidence` | `[]` |
| CPU↔GPU 출력 동등성 | `passed`, argmax **32/32**, cosine 0.99993 |

그래서 범위 표시를 **이름 붙인 검증 기기 목록**으로 넓힌다.

```python
FORMAL_GPU_VALIDATED_DEVICE_PREFIXES = ("SM-A245", "SM-S942")
```

**나머지 여덟 조건은 하나도 건드리지 않는다.** 이 패치는 무엇도 통과하기 쉽게 만들지
않는다. 기기 하나를 이 목록에 추가하는 것은 "그 기기에 위 증거가 존재한다"는 주장이며,
근거 없이 추가해서는 안 된다.

### ⚠ 솔직한 비대칭 — 반드시 공시할 것

A24에서는 LiteRT 호환목록이 **`true`**를 돌려줬다. S26에서는 **`false`**이고 우리가
패치 1로 넘어갔다. **두 기기의 GPU 경로는 출처가 동일하지 않다.**

이 차이를 숨기지 않기 위해 패치 2는 런마다 다음을 기록한다.

| 필드 | 뜻 |
|---|---|
| `gpu_compatibility_list_supported` | LiteRT 호환목록의 판정 (S26은 `false`) |
| `formal_gpu_compat_list_override` | 목록이 거부했는데도 통과한 런이면 `true` |

**S26 GPU 숫자를 쓰는 보고서는 이 플래그를 반드시 공시해야 한다.** A24 결과와 한
표에 놓을 때 각주 없이 섞으면 안 된다.

남은 위험: 호환목록이 어떤 기기를 제외하는 이유가 *간헐적* 문제(지속 부하에서의
드라이버 결함, 특정 연산의 정밀도 이상)일 수 있고, 60초 런으로는 드러나지 않을 수
있다. **이 가능성은 배제되지 않았다.** 다만 300초 × 3반복 측정에서도
`full_delegate`와 출력 동등성이 유지된다면 그 자체가 추가 검증이 된다.

### 변경 내용

| 파일 | 변경 |
|---|---|
| `tools/d1_logger_v4.py` | 상수 1개 추가, 기기 조건 1곳 일반화, 요약에 공시 필드 2개 추가 |

Kotlin이 아니라 호스트 파이썬 도구라 **앱 재빌드가 필요 없다.**

### 다른 기기에 미치는 영향

**없다.** A24는 `SM-A245`로 목록에 있어 판정이 동일하고, 호환목록이 `true`였으므로
`formal_gpu_compat_list_override`는 `false`로 기록된다. 기존 A24 결과는 재측정 없이
유효하다.

### 검증

- 적용 → 재실행 무해 → 원복 시 원본과 **바이트 단위 동일** 확인
- 패치 적용 상태에서 `tools/test_d1_logger_v4.py` **30개 전부 통과**
- `python tools/d1_logger_v4.py self-test` PASS
