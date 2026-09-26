# S26 정식 측정 결과 — `S26_formal_strict`

Galaxy S26 (SM-S942N, Exynos 2600) · `--mode formal` · 2026-09-13 ~ 09-14

**80슬롯 전부 완주. 실패 0, 제외 0, 검증 무효 0.**

---

## 1. 실험 설계

| 항목 | 값 |
|---|---|
| 자원 | CPU, GPU |
| CPU 스레드 | 1, 2, 4 |
| 듀티사이클 | 25, 50, 75, 100 % |
| 조건 수 | (3 스레드 × 4 듀티) + (GPU × 4 듀티) = **16 조건** |
| 반복 | 조건당 5 → **80 런** |
| 런 구조 | baseline 60 s → load 60 s → cooling **중앙 350 s** (142~604 s, `--cooling-policy stable`이 온도 안정까지 대기) |
| 총 실측 | 37,613 표본 ≈ **10.4 시간** |
| warmup | 20 s |
| seed | 20260910 |
| GPU 프로파일 | `gpu-fp32-strict-v1` (`precisionLossAllowed=false`) |
| 정확도 정책 | `required` / scope `backend-performance-formal` |
| 대표 텐서셋 | `d1-imagenette-val40.d1tset` (40장, Imagenette 계층 추출) |

### 1.1 실행 조건 — 2026-09-26 사후 재추출 [P]

이전 판에는 충전·화면·시작온도·비행기모드 기록이 0건이었다. 원시 `results\S26_formal_strict\runs\<run>\merged\events.jsonl` 에서 다시 뽑았다
(방법은 `npu\results\NPU_FORMAL_RESULTS.md` 의 CPU4 d100 사후 재계산과 같음. 스크립트는 읽기 전용, 원시 폴더에 쓰지 않음).

**부적격 규칙 (재추출 전부터 있던 규칙을 그대로 씀)**: 러너의 안전 게이트 `pilot_require_unplugged = true` (모든 런의 `run_metadata` 에 기록됨).
→ 러너 시작 시 `pilot_plugged != 0` 이거나, 런 중 d1check 텔레메트리 샘플 중 하나라도 `plugged != 0` 이면 **부적격**.
부적격 런은 **원본을 지우지 않고** 이 표에 부적격으로 표시한 뒤 분석에서만 제외한다.

| 항목 | CPU 60런 | GPU 20런 |
|---|---|---|
| 러너 시작 `plugged` | **0** (60/60) | **0** (20/20) |
| 런 중 샘플 `plugged != 0` | **0 샘플** | **0 샘플** |
| battery status (시작) | 3 (방전) | 3 |
| **→ 부적격 런** | **0** | **0** |
| 러너 시작 배터리 | 30~90 % (중앙 68.5) | 32~88 % (중앙 63) |
| load 시작 SKIN | 29.1~31.6 ℃ (중앙 30.35) | 29.6~31.6 ℃ (중앙 30.3) |
| load 시작 AP | 27.6~30.9 ℃ (중앙 29.25) | 28.3~31.0 ℃ (중앙 29.15) |
| load 시작 BAT | 26.8~29.8 ℃ (중앙 28.3) | 27.4~29.7 ℃ (중앙 28.2) |
| Android thermal status (런 전체 최대) | 0 | 0 |
| 화면 밝기 | **런별 기록 없음** — `s26\device\13_display_state.txt` 원시값 91 을 9/14 00:26 KST 에 한 번 읽은 것뿐 | 같음 |
| 비행기 모드 · Wi-Fi | **기록 없음 (미확인)** | 같음 |

**충전 브레이크**: 시간순 53번째 런(9/14 10:34 KST, 시작 30 %) 뒤 30 % 게이트로 멈췄고, 충전 후 9/15 01:58 KST 에 85 % 에서 재개했다 (약 15.4 시간 공백).
재개 후 27런도 전부 `plugged 0` — 충전 케이블을 뽑고 재개했다. 다만 반복 블록 r004 가 공백을 가로질러 나뉜다.
load 시작 중앙값은 공백 전 53런 BAT 28.1 · SKIN 30.2 ℃, 공백 후 27런 BAT 28.7 · SKIN 30.7 ℃ (+0.5~0.6 ℃) → **세션 효과를 공변량으로 볼 것** [E].
### 1.2 GPU delegate 증거 재점검 — 2026-09-26 [P]

NPU 에서 `Replacing … (DispatchDelegate)` 줄이 **dispatch 실패 때도 찍힌** 반례(9/24 04:55 진단 로그 766행)가 있어, 같은 함정이 GPU 20런에 있는지 봤다.
- 20/20 런의 캡처 logcat `tflite` 줄이 모두 같은 6줄: `Initialized TensorFlow Lite runtime` → `Loaded OpenCL library` → `Initialized OpenCL-based API` → `Created TensorFlow Lite delegate for GPU` → **`Replacing 31 out of 31 node(s) with delegate (TfLiteGpuDelegateV2) node, yielding 1 partitions`** → **`Created 1 GPU delegate kernels`**
- D1GPU JSON 을 뺀 모든 캡처 줄에서 fail/error/unable/cannot/fallback/not supported/abort 패턴 **0건**. `delegate_evidence.json` 20/20 `verified`, 31/31, `failure_or_fallback_evidence = []`
- → **GPU 20런에는 NPU 식 함정의 흔적이 없다.** 교체 줄 뒤에 커널 생성 성공 줄이 오며, NPU 실패 사례에서는 그 자리에 실패 줄이 왔다
- 한계: 캡처 필터가 `D1CHECK_EVENT:I D1GPU:I tflite:I TfLite:I *:S` 라 벤더 OpenCL/드라이버 태그와 `tflite` V/D 레벨은 없다. 이 범위 밖의 실패는 이 점검으로 못 본다
- ⚠️ 별개 사항: 이 GPU 런들은 `s26-compat-list-advisory-v1`(CompatibilityList 부정 판정을 기록만 하고 진행)로 돌았다. 조민규 새 protocol(MULTITASK §2)은 이 override 를 금지한다 → 합의 필요

재현 (`D1Check_v4` 루트에서): `py s26\tools\s26_run_conditions.py results\S26_formal_strict <출력.json>` (런별 JSON 은 커밋하지 않음).

명령줄은 [`../tools/s26_formal.bat`](../tools/s26_formal.bat)에 그대로 들어 있다.

---

## 2. 완주·검증 상태

```
slot_status                              completed 80
validation_status                        valid     80
formal_gate_result_status                passed    80
formal_gpu_valid                         True      20 / 20   (GPU 런 전부)
model_eligible                           True      80
accuracy_preflight_status                passed    80
  synthetic_numerical_check              passed    (argmax 32/32, mismatch 0)
  representative_input_equivalence       passed    (argmax 40/40, mismatch 0)
  task_accuracy_check                    passed    (Top-1 델타 0.0, Top-5 델타 0.0)
termination_reason                       duration_complete 80
cooling_status                           completed 80
exclusion_reasons                        []        80
attempts                                 1회 78 · 2회 2
energy_measurement_status                raw_unverified 80
```

- 열 표본 **37,652건 수집 / 37,613건 구간 배정** (미배정 39건 = 0.10 %)
- GPU 프로파일 단일성: `gpu-fp32-strict-v1` 20런, `mixed_gpu_profiles=false`
- `experiment_manifest.json` sha256 `5d49488529d30cdcf2d1f9244a761229d9106b872e058fef9efe3c1374dcd43b`

재시도 2회가 발생한 런이 2건 있다. 배터리 게이트(SOC 30 %)로 중단됐다가 `--resume`으로
이어받은 구간이며, 완주 후 `validate_result()` 33개 검사를 모두 통과했다.

---

## 3. 지연 — 조건별 중앙값 (ms, 5반복의 중앙값)

| 자원 | 스레드 | duty 25 | duty 50 | duty 75 | duty 100 |
|---|---|---|---|---|---|
| CPU | 1 | 3.895 | 3.911 | 4.079 | 4.342 |
| CPU | 2 | 3.907 | 3.913 | 4.043 | 4.421 |
| CPU | 4 | 3.897 | 3.904 | 4.096 | 4.370 |
| **GPU** | — | **3.669** | **3.660** | **3.641** | **3.636** |

재현성: 16개 조건의 5반복 변동계수(CV)가 **최소 0.187 % / 중앙 0.740 % / 최대 2.208 %**.

---

## 4. 결과 1 — 스레드 축은 평평하다 (오히려 미세하게 악화)

CPU 런 60건을 스레드별로 묶은 중앙값:

| 스레드 | n | 중앙값 (ms) | 1스레드 대비 |
|---|---|---|---|
| 1 | 20 | 3.9731 | — |
| 2 | 20 | 3.9906 | +0.441 % |
| 4 | 20 | 4.0285 | +1.394 % |

**스레드를 늘려도 빨라지지 않는다.** 4스레드가 1스레드보다 1.4 % *느리다* —
조건별 CV 중앙값 0.74 %를 감안하면 유의미하다고 주장할 수 있는 크기는 아니지만,
적어도 "이득 없음"은 확실하다.

A24에서 조민규가 관측한 값(1/2/4 = 41.178 / 41.210 / 41.224 ms, 총 편차 0.11 % — 감사본 `A24_S26_COMPARISON.md`:58-60 기준.
2026-09-26 정정: 이전 판의 41.190 / 41.252 / 41.303 ms · 0.114 % 는 출처 불명 값이라 교체)과
**같은 현상이 서로 다른 SoC에서 재현됐다.** 모델이 작아 XNNPACK이 스레드 분할로
얻는 이득보다 동기화 비용이 크기 때문으로 보인다.

> 스케줄링 정책 관점: **스레드 수는 제어 변수로 쓸 가치가 없다.**
> 8·10스레드를 추가해도 같은 평면 위를 움직일 가능성이 높다.
> 제어 레버는 `자원(CPU/GPU)`과 `듀티사이클`이다.

---

## 5. 결과 2 — S26에서는 GPU가 CPU보다 빠르다 (A24와 부호가 반대)

| duty | CPU 중앙값 | GPU 중앙값 | GPU 배속 |
|---|---|---|---|
| 25 | 3.897 | 3.669 | **1.062×** |
| 50 | 3.911 | 3.660 | **1.069×** |
| 75 | 4.085 | 3.641 | **1.122×** |
| 100 | 4.367 | 3.636 | **1.201×** |

A24: GPU가 CPU보다 **3.196배 느림** (131.63 ms vs 41.19 ms).
S26: GPU가 CPU보다 **1.06~1.20배 빠름**.

**같은 모델·같은 fp32 strict 프로파일인데 자원 선택의 정답이 기기마다 뒤집힌다.**
이게 이 프로젝트의 핵심 논거가 된다 — "온디바이스 AI 자원 배정은 기기별로
측정해서 정해야 한다"는 주장의 실측 근거다.

---

## 6. 결과 3 — GPU는 부하율에 둔감하다

- CPU: duty 25 → 100에서 3.897 → 4.367 ms (**+12.1 % 악화**)
- GPU: duty 25 → 100에서 3.669 → 3.636 ms (**-0.9 %, 사실상 평평**)

부하가 올라갈수록 GPU의 상대 이득이 커진다(1.062× → 1.201×).
CPU는 지속 부하에서 열·주파수 제약을 받지만 GPU는 이 부하 수준에서 아직 여유가 있다는 뜻이다.

> 스케줄링 정책 관점: **요청이 몰릴수록 GPU로 보내는 정책이 유리하다.**
> 단일 요청 기준의 벤치마크만 보고 자원을 고정하면 이 이득을 놓친다.

---

## 7. 결과 4 — GPU가 더 시원하다

load 구간 온도 상승분의 조건별 중앙값 (℃):

| 자원 | duty | AP | BAT | SKIN | 냉각 후 AP 잔열 |
|---|---|---|---|---|---|
| CPU | 25 | +5.30 | +1.80 | +2.80 | +0.50 |
| CPU | 50 | +9.50 | +3.60 | +4.90 | +0.80 |
| CPU | 75 | +14.00 | +4.30 | +5.70 | +1.20 |
| CPU | 100 | +14.10 | +4.60 | +5.90 | +1.50 |
| GPU | 25 | +2.60 | +1.00 | +1.50 | +0.50 |
| GPU | 50 | +6.70 | +1.90 | +2.80 | +0.70 |
| GPU | 75 | +9.10 | +3.00 | +4.20 | +0.90 |
| GPU | 100 | +11.70 | +4.10 | +5.50 | +1.30 |

**모든 듀티에서 GPU의 AP 상승이 CPU보다 낮다.** duty 75에서 차이가 가장 크다
(+14.00 vs +9.10, 4.9 ℃ 차이).

즉 S26의 GPU는 **더 빠르면서 동시에 더 시원하다.** 지연/열 사이의 교환이 아니라
한쪽이 다른 쪽을 지배하는(dominate) 구조다. 냉각(중앙 350 s, §1 — 2026-09-26 정정: 이전 판 "115초" 는 A24 값 오기) 후에도 AP 잔열이
+0.5~1.5 ℃ 남아 있어, 연속 실험 설계에서 냉각 시간은 계속 필요하다.

---

## 8. 정확도 검증

| 검사 | 결과 |
|---|---|
| `synthetic_numerical_check` | passed · argmax 32/32 · mismatch 0 · non-finite 0 |
| `representative_input_equivalence` | passed · argmax **40/40** · mismatch 0 · tolerance `within` |
| `task_accuracy_check` | passed · Top-1 **75 %** · Top-5 **95 %** · 델타 **0.0 / 0.0** |

Top-1 75 % / Top-5 95 %는 조민규가 A24에서 얻은 값과 **정확히 일치한다.**
같은 텐서셋·같은 모델이므로 당연한 결과이며, 우리 텐서셋 재구축이
옳았다는 교차 확인이 된다.

기록된 한계 3가지:

- 합성 입력의 수치 허용오차는 진단용이며 과제 정확도가 아니다
- `precision_loss_allowed`는 드라이버의 실제 FP16 실행 여부를 드러내지 않는다
  (`actual_fp16_execution: unknown_not_exposed_by_litert_api`)
- Imagenette는 10클래스 부분집합이므로 전체 ImageNet 정확도가 아니다

---

## 9. ⚠ 반드시 공시할 것

S26 GPU 런 20건 전부에 다음이 기록되어 있다.

| 필드 | 값 |
|---|---|
| `gpu_compatibility_list_supported` | **`false`** |
| `formal_gpu_compat_list_override` | **`true`** |
| `gpu_compatibility_policy_id` | `s26-compat-list-advisory-v1` |

LiteRT 1.4.2의 내장 허용목록이 Exynos 2600을 모르기 때문이며, 우리는 패치 1로
이를 "치명적 오류"에서 "기록 후 진행"으로 바꿨다. GPU 실행 자체는
`delegate_evidence.full_delegate = true` (31/31 노드 대체)와 출력 동등성으로 입증된다.

**A24 결과와 한 표에 놓을 때 이 각주 없이 섞으면 안 된다.**
A24는 허용목록이 `true`였으므로 두 기기의 GPU 경로는 출처가 동일하지 않다.
자세한 근거와 남은 위험은 [`../patches/README.md`](../patches/README.md) 패치 1·2 참조.

---

## 10. 에너지

`energy_measurement_status = raw_unverified` (80런 전부).
전류 단위 검증이 끝나지 않아 **J·mWh 값을 산출하지 않았다.**
배터리 소모는 런당 약 1.17 %p로 관측됐으나 이는 참고치이며 에너지 주장에 쓸 수 없다.
단계 2의 전류 단위 검증이 선행되어야 한다.

---

## 11. 산출물

`results/S26_formal_strict/exports-v2/` (스키마 v2, `d1_thermal_dataset.py` 자동 생성)

| 파일 | 크기 | 행수 |
|---|---|---|
| `run_summary.csv` | 58,705 B | 80 |
| `phase_temperature_summary.csv` | 184,831 B | 320 |
| `thermal_timeseries.csv` | 10,834,995 B | 37,613 |
| `dataset_manifest.json` | 254,108 B | — |

---

## 12. 남은 일

- [ ] **A24 원본 CSV 확보** — 깃헙·로컬 어디에도 없다. 조민규에게 위 4개 파일 + `experiment_manifest.json` 요청 필요
- [ ] 대표 텐서셋 `container_sha256` 차이 해소 (우리 `89190c28…` vs 조민규 `cf1b9232…`, 헤더 메타데이터만 다름)
- [ ] 전류 단위 검증 (단계 2) — 에너지 주장의 전제
- [ ] NPU 경로 — NNAPI는 `nnapi-reference`(CPU)만 노출되어 불가. Samsung ENN / LiteRT Next `CompiledModel` 미검증
- [ ] 8·10스레드 추가 여부 — 스레드 축이 평평하므로 우선순위 낮음, 팀 논의 후 결정
