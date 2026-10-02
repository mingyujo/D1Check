# 스모크 1002→03 밤 — GPU(CompiledModel) · 상한 · 연쇄 (+ 1단계 사전 등록 기록)

> 표기: [P] 실측 · [D] 문서·코드 인용 · [E] 추정 · `미확인`. 시각은 전부 KST 절대값 (2026-10-02 밤 → 10-03 새벽).
> 프롬프트 `프롬프트_밤측정_1002.md` 와 절차서 `측정절차_연쇄모드_0928.md` §2·§3·§5 의 사전 판정 표를 글자 그대로 쓴다.
> 이 문서는 칸이 끝날 때마다 덧붙인다 — 작성 중 (각 절 머리에 기록 시각).

## 0. 세션 공변량 (0단계) [P]

| 항목 | 값 |
|---|---|
| 무선 adb | `<IP:PORT>` (영훈, 23:5x). `adb devices` 에 mDNS 자동연결 항목(`adb-<SERIAL>…_adb-tls-connect`)이 같이 보여 `adb disconnect` 로 끊음 → 기기 1대 |
| 클론 | HEAD = `origin/s26-measure` = `9e81997eee21061c36ddd62f70f6d1f452208950` (`push_1002\step1_state.txt` `head=` 와 일치). 작업트리 비깨끗: `.idea/*` 3개 수정 + 미추적 `.idea/.name`·`CLAUDE.md`·`D1_ondevice/`·`_audit_tools/` (낮 세션 잔재 — 손대지 않음) |
| 바이너리 5개 | `GIT_REWRITE_MAP_20261002.md` 표와 크기·SHA 전부 일치 (dispatch `.so` `f08656a6…` 559,960 B · FP32 AOT `1415b2c8…` 8,901,712 B · INT8 AOT `36c75e6a…` 4,605,104 B · 원본 2개 동일) |
| **설치본** | `gradlew :npu-runner:installDebug` 23:56:32 → **23:56:58 설치** (BUILD SUCCESSFUL 25 s, dex 재빌드 없음 — UP-TO-DATE). APK `npu-runner-debug.apk` **55,055,326 B · SHA-256 `5ac485e382ebc82e380e6161ca6301ff89e9ab3d8be49b5d5388ab28b42c1033`** (= 낮 빌드 `5ac485e3…`, 파일 mtime 09-28 11:57:44). 기기 `lastUpdateTime=2026-10-02 23:56:58` · versionCode 1 · targetSdk 37. 이전 설치본 `2026-09-27 02:09:34` |
| benchmark-runner | 재설치 안 함. `lastUpdateTime=2026-09-13 20:46:45` |
| EfficientNet 기기 파일 | `/data/local/tmp/efficientnet_lite0.tflite` SHA `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0` · 18,582,189 B (일치) |
| 배터리 (23:55) | plugged 0 (AC/USB/Wireless/Dock 전부 false) · SOC 89 · BAT 28.6 ℃ · 케이블 분리 23:44:29 (dumpsys EventLog) |
| 실내 온도 (시작) | **23 ℃** (영훈 채팅, 1회) |
| 폰 상태 | 비행기 모드 1 · 밝기 수동 0 · `screen_off_timeout` 600000 → **86400000 (00:09:33, 2단계 직전)** |
| PC 절전 방지 | 숨은 PowerShell `SetThreadExecutionState` 프로세스 pid 20024, **23:58:21 시작** (powercfg 변경 없음). 첫 시도는 샌드박스가 `powercfg /requests` 줄을 막아 통째로 거부 → 그 줄 빼고 재시도 |
| 디스크 | 호스트 C: 여유 24.2 GB (> 5 GB → NPU 1300 s 그대로) · 폰 `/data` 여유 61.7 GB |
| 폰 회수 | ~10:00 KST (영훈: "배터리 가능한 대로 최대한") |
| 호스트 기록 폴더 | `results\S26_night_1002_host\` (git 무시 경로): `gradle_install_1002.log` 사본 없음(스크래치) · `phone_settings_log.txt` · `keepawake_log.txt` · `dryrun_1002.ps1/.log` · `gate_log_1002.csv` · `skin_watch_1002.csv` · `session_log.txt` |

## 1. 1단계 — 사전 등록·확인 (00:00~00:10, 폰 불필요) [P]

### 1-1. M1·M2 판정 스크립트 `sim\m1m2_judge_1002.py`

- **SHA-256 `ea282d4a48630c4af3cce301c13216f691389fa9f2c8e69a652de645be055b28` · 46,060 B · 2026-10-03 00:09:33 KST** (M2 자료를 열기 전)
- 입력: 연쇄 런 폴더 (`gpu\*.jsonl` + `raw\thermalservice.jsonl` [+ `merged\events.jsonl` d1check 표본]). 구간 창 = `segment_start.detail.start_ns` ~ `segment_end.detail.end_ns`, 전환 창 제외
- 출력: `segments`(구간별 전수 중앙·10 s 칸·시작 SKIN/AP/BAT·전환 창 `model_init_ns`) · `m2`(초안 §4 식 그대로, 하한 NPU·GPU 0.03 / CPU 0.05, CPU 는 `--metric first20`) · `m1`(초안 §2: `ref_d10`·A3 ±5 %·회복 k·중도절단·계단/점진) · `engine`(초안 §3 세 범위) · `extract`(구간 하나를 `throttle_curve_0928.py analyze` 용 가짜 결과 폴더로)
- 결정적: `sort_keys` + 소수 6자리. SOC 는 d1check 표본에 없어 호스트 감시 CSV(`--watch`)의 `battery_level` 로 (없으면 `미확인`), 런 시작 SOC 는 `pilot_battery_pct`
- **양방향 시험 (합성 JSONL) 21/21 PASS** (`py -X utf8 m1m2_judge_1002.py selftest`):

| 시험 | 결과 | 값 |
|---|---|---|
| M2 H=C×1.05, s_C 0.5 % → 있음 | PASS | s_C 0.4988 % · gain_low 4.478 % |
| M2 H=C (동일) → 없음 | PASS | s_C 0 |
| M2 H 가 대조 폭 안 (s_C 0.5 %) → 없음 | PASS | gain_high 0.400 % |
| M2 H=C×1.02, s_C 0.5 % → 보류 | PASS | gain_low 1.493 % < 3 % |
| M2 H=C×1.05 인데 s_C 3 % → 보류 | PASS | 2·s_C 6.008 % > 5 % |
| M2 CPU 피해자 first20 ×1.06 (하한 5 %) → 있음 · 하한 3 % 로 바꿔도 같음 | PASS | — |
| M1 선형 감소 k=8 부터 4칸 ≤ ×1.10 → 80 s · 점진형 | PASS | max step 12.5 % |
| M1 끝까지 ×1.2 → 중도절단 | PASS | "270 s 안 미회복" |
| M1 한 칸 ×1.5 → ×1.05 → 계단형 (50 s) | PASS | step 100 % |
| M1 4칸 유지 안 되는 일시 하강은 회복 아님 → 70 s | PASS | — |
| M1 A3 평탄 → 기준 안정 / 칸 ±5 % 밖 → 기준 불안정 | PASS | — |
| M1 가열 구간 1-1 진입 (합성 계단 60 s) | PASS | 60 |
| 엔진 대조 같은 모양 / 다른 모양(진입 120) / 전력 없음 → 보류 | PASS | — |
| 구조: 구간 하나 뺀 JSONL → 오류로 멈춤 · 추론 한 건 뺀 JSONL → 오류로 멈춤 | PASS | `JudgeError` |
| 결정성: 같은 입력 두 번 = 같은 바이트 | PASS | 3,101 B |
| extract: 구간 0 추론만 · load 창 = 구간 창 | PASS | — |

- 관찰 (규칙 변경 아님, 영훈 참고): 초안 §4 의 "없음" 식은 `max(vH)/min(vC) − 1 ≤ s_C` 인데 s_C 는 평균으로 정규화돼 있어 **H 가 C 와 완전히 같은 두 값이어도 (C1 ≠ C2 면) 0.5 % 대 0.4988 % 로 '보류'** 가 된다. 식은 글자 그대로 구현했고, 합성 시험의 "H = C" 는 네 값이 같은 경우로 넣었다. 실제 자료에서 H 가 대조 폭 **안쪽**이면 "없음" 이 나온다 (시험 3)
- 생성기 버그 1건 (구간 끝을 넘는 합성 추론 1건)은 selftest 첫 실행에서 `JudgeError` 로 잡혀 생성기만 고침 — 판정 코드는 그대로

### 1-2. 명령 dry-run — **21/21 exit 0** (00:07:18~00:07:24, `results\S26_night_1002_host\dryrun_1002.log`)

2단계 GPU 스모크 · 3단계 상한 · 4단계 N1300·N600 · 5단계 연쇄 스모크(+upfront) · 6단계 M2 C1/H1/H2/C2 · 6b M2r C1/H1/H2/C2 (1.5 M) + C1/H1 (1 M 대체) · 7단계 M1 · 9단계 EffNet×CPU · EffNet×GPU · M2 CPU C1/H1 — 전부 `<IP:PORT>` 실제 값으로 `validate_cli` 통과 (`performs_adb_calls false`, `writes_manifest false`). 절차서 원형과 다른 곳 없음.

### 1-3. 예상 추론 수·상한 (프롬프트 표 그대로 [E]) — NPU 1300 ≤ 1.77 M / 2 M (여유 13 %) · NPU 600 ≤ 0.82 M / 1 M · M2 NPU 피해자 H ≈ 179k / 400k · 6b H ≈ 831k / 1.5 M (2 M 통과 시) · M1 ≈ 173k / 400k

### 1-4. 고정 스크립트 확인 — `sim\throttle_curve_0928.py` SHA `3182267894b23813802f0e3f3c3146fbbe2d52581bb494339f1dc623cb6d0b4e` (사전등록 §0 의 `31822678…` 일치) [P]

### 1-5. 스킬 — `anti-hallucinate`(0단계 전) · `falsifiable-experiments`(1단계 전) 읽음. 양방향 검증기·보존 검사·제안/판정 분리 원칙을 1-1 에 적용

## 2. GPU 스모크 (60 s × 1) → GPU 증거 규칙 동결 — **통과 · 갈림길 "통과" (3 → 4 → 5 → 6 → 6b → 7)** (기록 00:38)

- 게이트 **00:09:53 통과, 대기 0 s** — HAL SKIN 28.0 · AP 26.1 · BAT 25.5 ℃ · status 0 · SOC 88 · plugged False [P `gate_log_1002.csv`]. `MemAvailable` 3,322,024 kB
- orchestrator 00:11:26 → 00:25:27 (763 s, 독립 프로세스 pid 30080). preflight(benchmark-runner CPU↔GPU 합성 + npu-runner GPU 품질 게이트) 00:11:44~46 완료 → 슬롯 → stable 냉각 → analyze. 폴더 `results\S26_GPUcm_smoke_1002`, 런 `9f40b682-a955-4982-8657-5ad561077dec`

### 사전 판정 (절차서 §2 표 1~4) [P]

| # | 항목 | 결과 |
|---|---|---|
| 1 | 실행 | **통과** — slot `npu-d100-r001` completed · validation **valid (33 검사 0 실패)** · `termination_reason duration_complete` · 추론 23,425 건 / 60.002 s · achieved duty 100 |
| 2 | 라벨·옵션 | **통과** — `npu_accelerator_requested GPU` · `npu_timed_resource_label gpu_compiled_model` · `compiled_model_options.accelerators_passed_to_native ["GPU"]` · `gpu_options.precision FP32` · `model_sha256 d95b3c5e…` · `npu_compile_mode "not_aot (original model, compiled on device by the GPU accelerator)"` · `npu_model_partition null` |
| 3 | 품질 게이트 | **PASS** (`npu_quality_preflight.status passed`, 게이트 run `npuq-85ab46bb…`) — `bit_identical_to_cpu false` (32 중 0) · argmax 32/32 (전부 112) · `cosine_min 1.0` · `candidate_accelerator GPU` · `candidate_gpu_precision FP32`. **`bit_identical` 은 관찰값으로만 기록** (조민규 DECISIONS 규칙) |
| 4 | 증거 후보 | 러너 PID **9079** 의 litert 23줄 + tflite 3줄: `tflite: Replacing 31 out of 31 node(s) with delegate (LITERT_CL) node, yielding 1 partitions for subgraph 0 ().` (X = Y = 31 → **전 그래프 GPU**) · `litert: [gpu_environment.h:155] Created LiteRT GpuEnvironment.` · `tflite: Loaded OpenCL library with dlopen.` · `[gpu_environment.cc:220] Created OpenCL device …` · 실패·폴백 줄 **0** (캡처 필터 `litert:V tflite:V TfLite:V` 범위 안). 후보 규칙 `candidate-0` 판정 `CANDIDATE_PASS` |

- 지연: 중앙 **2.517 ms** · p95 2.830 · min 2.201 · max 7.001 (write+run+read, CompiledModel GPU FP32 요청) — Interpreter GPU strict(C1-probe 처음 30 s 3.66 ms [D C1a_결과])와 **절대값 비교 금지** (엔진 다름). 관찰로만
- `formal_npu_valid False` (pilot · GPU 런 — 정상). logger 의 기존 `delegate_evidence` 는 `TfLiteGpuDelegateV2` 를 찾는 Interpreter 규칙이라 `unverified` (31/31 은 읽음) — CompiledModel GPU 의 ② 증거는 아래 v1 규칙으로만 판정한다
- 같은 PID 에 `Attempting to load GPU accelerator(libLiteRtGpuAccelerator.so)` → 이어서 `libLiteRtClGlAccelerator.so` 가 `LiteRT GPU` 로 등록 — **이 기기에서 실제로 쓴 것은 OpenCL 가속기(LITERT_CL)**. ML Drift 경로(`ops are delegated to ML Drift`)는 **나타나지 않았다** → 후보 규칙의 바이너리 문자열 가정 중 그 줄은 기기 문구가 아니었다 (후보가 통과한 것은 "Created LiteRT GpuEnvironment" 쪽이 맞아서)
- 정밀도 4항목 (`precision_record` schema precision-4-v1): ① 저장 — 러너 `unknown_in_runner`, 호스트 파일 읽기 = 원본 MobileNet FLOAT32×88 + INT32×1 [D 0928 §3.4] · ② I/O FLOAT32 write/read · ③ `CompiledModel.Options(Accelerator.GPU)` + `GpuOptions(precision=FP32)` + env `DispatchLibraryDir/CompilerPluginLibraryDir=nativeLibraryDir`, compiler_cache true — **요청이지 실행 증거 아님** · ④ `unknown` ("LiteRT 2.2.0 exposes no executed or accumulation precision")

### GPU 증거 규칙 v1 동결 (유일한 코드 변경) [P]

- `tools\compiled_model_evidence.py` — `gpu-compiled-model-evidence-candidate-0` → **`gpu-compiled-model-evidence-v1`**. 조건 6개 전부 AND: ① 러너 프로세스 하나 ② 그 PID 의 `Replacing X out of Y … (LITERT_CL)` 가 있고 X = Y > 0 (**delegate 이름을 기기 문구 `LITERT_CL` 로 고정** — 후보의 "XNNPACK/Dispatch/NNAPI 가 아닌 이름" 대신) ③ 그 PID 의 `[gpu_environment.h:<n>] Created LiteRT GpuEnvironment.` (줄 번호만 와일드카드) ④ 다른 delegate 교체 줄 없음 ⑤ 실패·폴백 줄 없음 (`FAILURE_RE` + 바이너리 유래 `GPU_FAILURE_RE` — 기기에서 관측된 실패 문구는 없으므로 추가 음성 조건으로만 유지) ⑥ `npu_accelerator_requested == GPU`. 후보의 `GPU_SUPPORT_RE`(ML Drift 문구 포함)·`NON_GPU_DELEGATES` 는 삭제. **CPU 규칙·NPU 규칙은 한 줄도 안 건드림** — 공유 함수(`parse_log`·`runner_pids`·`_verdict`)·공유 상수 불변
- **지문** (`py tools\compiled_model_evidence.py fingerprint`, **2026-10-03 00:36:28 KST**): `cpu` **`cef076049ea750289c3406f707f58f70c872f2f7392d4644a3688f6005e7c7bb`** (= 0928 동결값, 불변 확인) · **`gpu` `36615b9e1377c02b13629adf9fe950f90d6614155b2876cdbadcf785aeac0618`** · `npu` `2305a46c93769157fd0baeab2342d5dd5d9be192c28e1a38403b0e2e423289e8`
- 양방향: 스모크 런 `evaluate --rule gpu` **PASS** (6/6 조건) · 기존 픽스처 42개(C5 CPU 20 · NPU formal 20 · 9/24 진단 2) → GPU 규칙 **전부 FAIL 유지** (`litert_cl_full_replacement_in_runner_pid` 등 로그 조건에서) · 스모크 발췌를 `make_fixtures.py` 로 추가 (`gpu_smoke_1002_npu-d100-r001.log`, 32줄, 민감어 필터 적용, 원본 11,9xx 줄 → 발췌·원본 판정 일치 확인) · MANIFEST 43개 · 기존 42개 `.log` 바이트 불변 · `py -3 -m pytest tools	est_compiled_model_evidence.py` **22 passed** (새 시험: 스모크 PASS + 같은 로그가 CPU·NPU 규칙엔 FAIL · 30/31 부분 교체 FAIL · 교체 줄을 다른 PID 로 옮기면 FAIL · GpuEnvironment 줄 제거 FAIL · XNNPACK 교체 줄 추가 FAIL · `falling back to CPU` 추가 FAIL · 요청 NPU 면 FAIL · 등록·OpenCL dlopen 줄만으론 FAIL)
- 규칙은 **스모크 1런**으로 만든 것 → M1·M2·EfficientNet×GPU 의 첫 런들이 사실상 첫 시험. ML Drift 경로가 나타나는 런은 이 규칙에서 FAIL(= "② 증거 부족", 실패 런 아님) — 그때는 v2 를 그 로그로 새로 동결하지 v1 을 풀지 않는다
- 커밋: **`9ad3844`** (`9ad384480fa6111f3615d5362ed178c1482bedf2`) `tools: GPU 자원 증거 규칙 v1 동결 (1002 스모크)` — 파일 5개만 (`compiled_model_evidence.py` · `test_compiled_model_evidence.py` · `make_fixtures.py` · `MANIFEST.json` · 새 픽스처). push 안 함

## 3. 상한 스모크 (NPU d100 30 s, 상한 2,000,000) — **통과 → 4단계 1300 s · 2 M, 6b 상한 1.5 M** (기록 00:41)

- 게이트 **00:26:12 통과, 대기 0 s** — SKIN 28.9 · AP 27.1 · BAT 26.4 ℃ · status 0 · SOC 87 [P `gate_log_1002.csv`]. `MemAvailable` 3,254,680 kB
- orchestrator 00:28:19 → 00:37:23 (442 s, pid 22236). 폴더 `results\S26_capsmoke_npu_1002`, 런 `6917ff5c-e994-4622-9f90-473c53f8d48b`

| 사전 판정 (절차서 §3) | 결과 [P] |
|---|---|
| run_metadata `max_inference_spans` | **2000000** |
| `max_inference_spans_buffer_bytes` | **56000000** (= 2,000,000 × 28 B) |
| `jvm_max_memory_bytes` | **268,435,456** (256 MiB — S26 앱 힙 한도, 지금까지 `미확인` 이던 값). 40 % = 107.4 MB ≥ 56 MB → 러너가 거부하지 않음 |
| slot valid | completed · validation **valid** · `duration_complete` · 러너 거부 로그(`Invalid automation request`) 0 |

- 관찰: 추론 37,761 건 / 30.001 s = **1,259 /s** · 중앙 0.7526 ms (write+run+read, NPU AOT FP16[E]) · load_start SKIN 28.5 ℃ · SOC 87. 9/25 formal d100 중앙 0.743~0.749 [D CLAUDE.md]·0928 N165 처음과 같은 자릿수 (새 설치본 — 조건)
- 1.5 M 상한(6b) = 42 MB ≤ 107 MB → 같은 힙 조건 안 [E, 계산]. 3 M(도구 상한) = 84 MB 도 들어간다 [E] — 쓰지 않음

## 5. 연쇄 스모크 (40 s 2구간, GPU d100 20 → NPU d100 20, per_segment) — **구조 통과 → 6 → 6b → 7. 시간 보존 표시 1개** (기록 01:40)

- 게이트 **01:22:36 통과, 대기 0 s** — SKIN 30.2 · AP 28.9 · BAT 27.9 ℃ · SOC 75 [P `gate_log_1002.csv`]. `MemAvailable` 3,653,540 kB
- orchestrator 01:23:45 → 01:34:01 (595 s, pid 2448). 폴더 `results\S26_chainsmoke_1002`, 런 `a1e3445e-71ca-489d-a700-f665bbbf73e3`. 체인 canonical SHA `0a73a377…` (왕복 일치 — `spec_roundtrip`·`sha_roundtrip` 통과)

| # | 사전 판정 (절차서 §5) | 결과 [P] |
|---|---|---|
| 1 | 구조 (`chain_structure`) | **통과** — validation **valid (실패 0)**, `chain_check.structure_passed true` (체인·SHA 왕복 · segment 짝 2/2 · 순서 · 겹침 0 · 추론 7,770 + 25,309 = 33,079 = 전체 · 번호 연속 · 구간별 duty 등식) |
| 1b | 시간 보존 (표시만) | **`chain_conservation_flags = ["transitions_explained"]`** — 전환 창 150.76 ms 중 기록된 스팬(model_close·model_init·warmup)이 90.47 ms, **60.3 ms 미설명 (> 허용 50 ms)**. Σ구간 40.0013 s + Σ전환 0.1508 s + 잔차 1.36 ms = load 창 40.1534 s (허용 200 ms 안 — `time_conservation` OK) · `boundary_gaps` OK · 표본 공백 OK. **허용오차는 바꾸지 않는다** — M1·M2 결과마다 이 표시를 같이 쓴다 |
| 2 | 전환 | `chain_transitions[0]`: `backend_switch true` · `model_initialized true` · **`model_init_ns 26,340,234` (26.3 ms)** · env_init 1.66 ms · buffer_init 0.21 ms · warmup 20 · 전환 창 **150.8 ms** — **GPU→NPU 전환비용 첫 실측** (순서의존 준비시간) |
| 3 | 구간 | seg 0 `smoke_gpu` GPU d100 20.001 s **duration_complete** 7,770 건 (중앙 2.527 ms, FP32 요청) · seg 1 `smoke_npu` NPU d100 20.001 s **duration_complete** 25,309 건 (중앙 0.750 ms) |
| 4 | 공식 판정에 안 섞임 | `formal_npu_valid false` · `formal_npu_conditions.not_chain_run false` ✓ |
| 5 | 자원 증거 | `--rule npu` **FAIL** (기대 PASS 와 다름) — `existing_npu_delegate_evidence_verified false`: `aot_partition null` → `partition_matches_aot_manifest false`. 원인: 런 단위 규칙이 `run_metadata.model_sha256`(= **구간 0 의 원본 MobileNet** `d95b3c5e…`)으로 AOT 매니페스트를 찾는다. dispatch 1/1 · ENN · 실패 줄 0 은 러너 PID(20006)에 있다 (`dispatch_and_enn_lines_in_runner_pid true`). `--rule gpu` 도 FAIL (`no_other_delegate_replacement` — Dispatch 줄, `requested_accelerator_gpu`). → **체인 런의 ② 증거는 런 단위 규칙으로 판단 불가 (구간별 귀속 없음, 절차서가 미리 적은 한계).** 발췌(판정 아님): PID 20006 — 구간 0 쪽 `Replacing 31 out of 31 … (LITERT_CL)` + `Created LiteRT GpuEnvironment.` → 전환 뒤 `Replacing 1 out of 1 … (DispatchDelegate)` · `Header verification failed - using old format`(기지) · `Buffer info - inputs: 1, outputs: 1` · `Created TensorFlow Lite XNNPACK delegate for CPU.` (교체 줄은 없음 — 9/25 NPU formal 로그와 같은 모양 [P 픽스처]) · 실패·폴백 줄 0 |

- 전환 창 첫 값: **150.8 ms** (GPU→NPU, 모델 교체 포함). 같은 전환이 M2 두 팔에 다 있다
- 캡처: raw logcat 33,615 줄 · D1GPU 33,113 (러너 이벤트 33,124 → 거의 전부). 깨진 JSONL 줄 0
- 온도: 구간 0 시작 SKIN 29.4 · AP 28.9 → 구간 1 시작 SKIN 32.7 · AP 36.9 (GPU 20 s 로 AP +8 ℃) → load_end SKIN 33.1 · AP 35.7. SOC 75
- (선택 upfront 판 `chain_smoke_gpu_npu_upfront_v1`) — **하지 않음** (예산 우선순위, 프롬프트 기본)
- 갈림길: 1 통과 → **6 → 6b → 7 진행**. P3 로 넘길 것: 체인 런용 구간별 증거 귀속(교체 줄을 segment 경계 시각으로 구간에 붙이기) · `transitions_explained` 의 60 ms 미설명(전환 창 안의 D1Check 재확인 지연 [E]이 스팬으로 기록되지 않는다)

## 6. M1·M2 사전 등록 v1 동결

- `sim\M1M2_사전등록_v1.md` — 초안 본문 무변경 복사 + v1-A(영훈 결정 5개 초안값) + v1-B(스모크 후 변경: 6b 상한 1.5 M · GPU 규칙 v1 · 연쇄 스모크 뒤 표기 규칙 3개) + v1-C(공변량). **동결 2026-10-03 01:36:19 KST · 파일 SHA-256 `002a47a7e5d64284c18c33180a3dc1a5825d06a800a1a72523f78a8d9d26da67` (25,456 B)** — M2 C1 orchestrator 시작(01:3x) 전. 기록 `sim\out_1002\M1M2_v1_freeze.txt`
