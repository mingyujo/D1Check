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

**각주 (반드시)**
1. **엔진이 다르다.** 같은 CompiledModel 로 CPU 를 돌리면 Interpreter CPU4 보다 **21.4 % 느리다** (npu-runner CPU `run()` span 3런 중앙 5.303 ms vs 4.370 ms,
   사전 기준 "≤ 5 % 면 무시" 초과 → 이 각주). 조건: 스모크 경로 56.5~58.7 s 연속, 배터리 82~83 %, 각 런 전 온도 안정 대기
   (세션 로그 기준 98~264 s — 스모크 로그에는 시작 직전 스냅샷 하나만 있다). 스레드 수는 LiteRT 기본값(미확인).
   근거 `SMOKE_cpu_engine60_r{1,2,3}_20260925_*.json`
2. **span 이 다르다.** Interpreter = `interpreter.run()` 만 (`MEASUREMENT_DEFINITION.md`:57-62), NPU = write+run+read. NPU 쪽이 불리하게 잰 것
3. 배율 [E]: Interpreter CPU4 대비 duty 100 에서 **5.9×** (4.370/0.743), GPU 대비 **4.9×**.
   **같은 엔진·같은 span** 비교: CompiledModel CPU write+run+read 3런 중앙 **5.339 ms** (5.525 · 5.339 · 5.276) vs NPU 0.743 ms → **7.2×**
   (단 CPU 쪽은 스모크 경로 연속 실행, NPU 는 timed run duty 100 — 프로토콜이 다르다)
4. 날짜·배터리 구간·화면 밝기가 다르다 — CPU/GPU 는 **KST 9/14 00:38 → 9/15 07:44** (UTC 9/13~14), 시작 90 % 부근 → 30 % 게이트 중단 → 85 % 에서 재개.
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
범위 끝에서 **17~24 % 낮게** 나오고, CPU 의 AP 가열 피팅은 조건별 R² 중앙이 0.21~0.81 로 나쁘다. **같은 방법이라고 볼 수 없다.**
이 표의 NPU τ 는 기존 A24/S26 τ 표와 **직접 비교하지 말고**, 같은 재구현으로 CPU/GPU 를 다시 낸 값(위 범위)과만 비교할 것.

| 센서 | duty 25 | duty 50 | duty 75 | duty 100 | R² 범위 |
|---|---|---|---|---|---|
| SKIN 가열 τ | 46.9 s | 45.5 s | 47.6 s | 68.7 s | 0.96~0.97 |
| SKIN 냉각 τ | 77.7 s | 84.9 s | 90.4 s | 113.6 s | 0.95~0.97 |
| AP 가열 τ | 25.0 s | 26.4 s | 33.7 s | 35.1 s | 0.95~0.97 |
| AP 냉각 τ | 56.9 s | 55.3 s | 46.7 s | 63.2 s | 0.92~0.94 |
| BAT 가열 τ | 상한(3000) 4/5 | 455 s | 상한 4/5 | 2345 s | — — 60 s 안에 포화가 안 보임 → **식별 불가** |
| BAT 냉각 τ | 147 s | 139 s | 144 s | 165 s | 0.97~0.99 |

---

## 5. 에너지 — 잠정치 (논문에 쓰지 말 것) [E]

`s26\tools\s26_energy.py` (추적 안 됨, `_if_uA` 가정) — **단위 검증 허용오차가 사전에 문서화돼 있지 않아 잠정**이다.

| 항목 | NPU 20런 (이번) | CPU/GPU 80런 (같은 스크립트, 참고) |
|---|---|---|
| 전류 적분 / charge counter 비율 (전체) | **0.977** (−2.3 %) · 런별 0.80~1.13, 중앙 0.991 | 0.928 (−7.2 %) · 런별 0.70~1.18 |

| 자원 | duty | load W | idle W | net mJ/추론 |
|---|---|---|---|---|
| NPU | 25 | 1.648 | 0.627 | 3.18 |
| NPU | 50 | 2.843 | 0.533 | 3.98 |
| NPU | 75 | 4.119 | 0.561 | 3.73 |
| NPU | 100 | 5.120 | 0.563 | **3.53** |
| CPU 4 | 100 | 7.259 | 0.537 | 28.58 |
| GPU | 100 | 6.457 | 0.436 | 21.88 |

- [E] 잠정치 기준 NPU 는 추론당 CPU4 의 약 1/8, GPU 의 약 1/6. **허용오차를 먼저 정하고** 이 표를 판정할 것
- load W 는 전체 기기 전력(화면 포함)이다. NPU 단독 전력이 아니다. idle W 비교는 화면 밝기 차이(NPU 세션 0 [관찰] vs CPU/GPU 91 [D])로 오염돼 있다
- 에너지 출력은 스크래치패드 CSV — 원시 실험 폴더에는 쓰지 않았다 (`-o` 지정)

---

## 6. NPU 실행 증거 — 무엇이 직접이고 무엇이 간접인가

| 증거 | 종류 | 결과 |
|---|---|---|
| `Replacing 1 out of 1 … (DispatchDelegate) … 1 partitions` | 간접 (실패해도 찍힘) | 20/20 |
| ENN `SetGenAiPerfConfigFromSoc: SOC=s5e9965` + 실패 문구 0 | 간접 (런타임 로드) | 20/20 |
| dispatch·ENN 줄과 D1GPU 이벤트가 같은 PID (= timed run 프로세스) | 간접 | **formal 20/20** (캡처된 logcat 줄 기준) |
| 비트 비동일 + cosine 0.9997 | 간접 (CPU 가 아님) | preflight PASS [P]. "top5 가 FP16 표현값" 은 9/24 G4 스모크 관찰 [D] — 이번 preflight 기록엔 top5 가 없다 |
| 지연 0.743 ms vs 같은 엔진·같은 span CPU 5.339 ms, GPU 3.636 ms | 간접 (성능 격차) | [P]/[D] |
| 앱 프로세스의 `/dev/npu*` fd | 직접 | **없음** — 00:01 스모크(40,000회) 중 조사, formal 중에는 조사 안 함. 앱에 `vendor.samsung_slsi.hardware.enn_aidl-V1-ndk.so` 가 로드돼 있고 HAL 서비스가 존재하므로 ENN 이 AIDL HAL 을 거친다고 **추정** [E]. HAL 프로세스 fd 는 루트 필요 → **미확인** (`NPU_DEVICE_FD_PROBE_0925_NOT_FOUND.txt`) |

---

## 7. 한계 (과장 금지)

- 입력은 합성 LCG 하나를 반복 (argmax 32/32 는 전부 112 — 변별력 약함). 대표 이미지 NPU 품질은 미확인
- MobileNet V1 만. 계약 모델(EfficientNet-Lite0 / EfficientDet-Lite0)은 **스모크(실행)만** 확인 — timed run 경로 미연결
- S26 은 일상 사용 폰 — 백그라운드 경합은 통제하지 않았다 (비행기 모드로 줄였을 뿐)
- 화면 밝기 0 — CPU/GPU 80런의 밝기(9/14 기록 91)와 다르다 → **idle W 비교에 주의** (지연·열 상승 비교에는 영향 작음 [E])
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
- 캡처된 logcat 의 D1GPU 사본은 11/20 런에서 일부 빠졌다 (77.9~99.9 %, 전체 98.8 %). 지연·추론 수는 **러너 JSONL(완전)** 에서 나오므로 영향 없음

exports-v2 의 알려진 표기 문제: `formal_npu_valid` 열 없음(`model_eligible` 로만 반영), NPU 행 `execution_profile_type cpu_not_applicable`.

## 9. 남은 일

- [ ] 에너지 단위 허용오차 사전 등록 → §5 판정
- [ ] 대표 이미지셋으로 NPU 품질 재확인 (조민규 답장 대기)
- [ ] EfficientNet/EfficientDet timed run (orchestrator `d1_npu_input_spec`·`d1_npu_model_path` 전달 필요)
- [ ] 엔진 대조 개선 — npu-runner timed run 에 CPU 허용 여부 결정
