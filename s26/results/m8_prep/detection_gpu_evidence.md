# detection_gpu_evidence — R2 의 `detection_GPU` 실행이 warmup/probe 인지 등록 요청인지 (조민규 §9 · 프롬프트 B-5 · 폰 0 · 기록만)

> 근거 [P] = `s26/results/mixreq_1008/R2_smoke/S26_MIXREQ_SMOKE_1009_r2/S26_MIXREQ_SMOKE_S1_warmup_only_blockN_a1/` · `…_r4/S26_MIXREQ_SMOKE_S2_B2_PARALLEL_ONLINE_V1_a1/` (device/warmup.json · manifest.json · summary.json · requests.json · progress.jsonl · validated.json rule 7) · `R2_LEDGER.md` · `작업결과_1008_R2_혼합요청.md`. **"S26 탐지 GPU 본요청 검증 완료" 라 쓰지 않는다.**

## 1. 사실 (R2 · APK `fb240791…` · 커밋 `0ad7fac` · 2026-10-09)

| 항목 | 값 [P] |
|---|---|
| 세션 | S1 `962ea966-9ff6-5069-a6ce-baf936171b84` (`S26-MIXREQ-01-SMOKE` · warmup_only · 블록 N · 00:45:31) · S2 PAR `5667edd6-69c4-5c4f-beef-5688cc963ffc` (블록 A · 24 요청 · 03:18:26) |
| `detection_GPU` 실행의 role | **warmup 만** (`warmup.json` key `detection_GPU` index 0 · 1 — 세션마다 2회 · `runtime_setup` 뒤 warmup 단계) · **등록 요청 0건** (`requests.json` 에 `task_id detection · selected_backend GPU` 행 0 / 24 · 정책 `laneFor` 는 탐지를 항상 CPU) · `summary.used_keys` = `[classification_GPU, detection_CPU]` · rule 7 `detection_GPU.used_by_policy = false` |
| runtime 생성 | `runtime_return detection_GPU` · `CompiledModel.Options(Accelerator.GPU)` · `gpu_options.precision FP32` · `available_accelerators [CPU, GPU, NPU]` · `model_init_ns ≈ 456 ~ 459 ms` · `detection_gpu_created true` |
| delegate 실제 적용 | logcat GPU 규칙 v1 (`gpu-compiled-model-evidence-v1` · 생성 + warmup 창 안): `gpu_environment_created true` · **`263/263 LITERT_CL` 교체 줄 1개** (`replacement_lines [1617]`) · `no_failure_or_fallback_line true` · `no_other_delegate_replacement true` → verdict PASS (warmup 창 기준) |
| fallback / partition | 실패 · fallback 줄 0 · partition 줄 0 (전부 교체 263/263) |
| 품질 판정 | warmup 0 · 1 결과 = person 0.69621003 [372.136, 24.473, 576.728, 321.459] · bicycle 0.55899948 [−11.355, 12.291, 495.527, 470.614] — **A24 탐지 CPU 참조 (`a24_reference/detection_cpu_warmup.json`) 및 S26 detection_CPU warmup 과 같은 값** (|Δscore| 0 · 라벨 · 개수 같음) · 입력 텐서 `e1ce665b…` 같음 · raw SHA `9e2f38c7…/ffc8c537…` (2회 같음) · `actual_backend` 필드 = `unverified_requires_host_delegate_log` (앱은 실제 백엔드를 모름 · 호스트 logcat 규칙이 근거) |
| 추론 시간 (warmup · 기록만) | index 0 346.6 ms (첫 호출 · 컴파일 포함) · index 1 2.69 ms (S1) / 6.46 · 2.23 ms (S2) — 요청 단계 시각 아님 |
| source / APK | APK `fb2407911a5ee036b52e9bdb259d5e1bb1e8b16082ed9afad92eb576dd8fb230` (R1 · 커밋 `0ad7fac` · `local_inputs/apk/request-runner-debug_fb240791.apk`) · 매니페스트 S1 `2645dc40…` · S2 `d90a88be…` |
| M6/M7 에서도 | 블록 M 5 상주에 `detection_GPU` 포함 (생성 실패만 허용) · warmup 2회 · **요청 0** (정책 3 전부 탐지 → CPU) — M7-A `summary.detection_gpu_created true` 46/46 |

## 2. 결론 (기록)

- R2 의 탐지 GPU 실행 = **runtime 생성 + warmup 2회 (role warmup · session 안 index 0/1)** 이지 **등록된 실제 요청이 아니다** (`used_by_policy false` · 요청 행 0). delegate 교체 (`LITERT_CL 263/263`) · fallback 0 · warmup 출력 = CPU 참조와 같은 값 (품질 지표만 · Q20 꼴 20장 품질 판정 없음).
- 따라서 "S26 탐지 GPU 본요청 검증 완료" 아님 · 기존 탐지 CPU 비교에 새 경로가 들어간 것 아님. P4-1 (실제 요청 · delegate 적용 · fallback/partition · 출력 품질 · 실패 · 5단계/응답/AVAILABLE) 는 M8 핵심안 밖 **별도 새 계보** (정책 1 `…_DG_…` + 품질 게이트 Q20 꼴 + 단독 D_CPU/D_GPU · idle→DG→idle → 그 뒤 pair 별도) — 질문 #7.
- 탐지 NPU: 러너 미통합 (AOT 263/263 · 1 partition · raw 2 텐서 · 후처리 없음 · `NPU_DETECTOR_GATE_NOTE.md`) · 서류 실측과 분리 · 영구 제외 아님 (하드웨어 불가능 단정 안 함).
- CPU threads: 매니페스트 `cpu_threads` (지금 1) = **설정값** (`CompiledModel.CpuOptions(numThreads)`) · 실제 worker 수 = 호스트 `top -H` 관측 (M7 `host/top_h.txt` · 파서가 행을 못 셈 → "설정 1 / 관측 미확인") — 설정값과 관측을 열을 나눠 기록 (`m8_probe.ps1 top_threads_runner`).
