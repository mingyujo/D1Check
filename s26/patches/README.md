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
