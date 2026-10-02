# S26 결과 — 9/25 이후 실험 (요약 자료)

9/15 의 80런(`../formal_strict/`) 뒤에 돌린 실험의 **목록과 요약 CSV** 다. 원시 런 파일(`runs/…`: 러너 JSONL, logcat, thermalservice)은 크기 때문에 넣지 않았고 영훈 PC 의 `<클론>/results/` 에 있다.

표기: `[P]` 실측·직접 산출 / `[D]` 문서 인용 / `[E]` 추정.

## 들어 있는 것

| 경로 | 내용 |
|---|---|
| `inventory/S26_EXPERIMENTS_20261001.tsv` | `<클론>/results/` 의 실험 폴더 24개 (9/13~9/28). 설정·시각(KST)·완료/시도 수·종료 경로·품질 게이트·에너지 상태·`experiment_manifest.json` 과 `exports-v2` 파일의 SHA-256 |
| `inventory/S26_RUNS_20261001.tsv` | 시작된 런(슬롯) 168개. 완료 162 · 중단 3 · 실패 3. 슬롯·런 ID·시도 수·종료 경로·추론 수·지연 중앙값 |
| `exports_v2/<실험>/` | 실험 14개의 `dataset_manifest.json` + `run_summary.csv` · `phase_temperature_summary.csv` · `thermal_timeseries.csv` |

- 목록 두 개는 각 실험의 `experiment_manifest.json` · `exports-v2/dataset_manifest.json` · `run_summary.csv` 에서 기계적으로 뽑았다 (2026-10-01). 손으로 고친 값은 없다
- `exports_v2/` 의 파일은 원본과 바이트 동일하다. CSV 3개의 SHA-256 이 같은 폴더 `dataset_manifest.json` 의 `outputs` 값과 같은 것을 커밋 전에 대조했다. `.gitattributes` 가 `* -text` 라 줄바꿈 변환 없이 저장된다
- `experiment_manifest.json` 원본은 넣지 않았다 (무선 adb 주소·PC 경로 포함). 그 SHA-256 은 목록 TSV 에 있다
- 9/13~14 의 pilot·시험 폴더 5개와 80런은 목록에만 있다 (80런 요약은 `../formal_strict/`)

## 읽을 때 주의

- **`energy_measurement.status` 는 전부 `raw_unverified`** 다. J 로 쓰지 않는다
- `S26_C5_cpu_compiled_0927` 은 슬롯 이름이 `npu-d…` 이지만 **`CompiledModel` CPU 가속기 런**이다 (`config.npu.timed_accelerator = CPU`). 같은 런 메타데이터의 `npu_compile_mode aot` · `npu_precision fp16(compiler-default)` 는 틀린 표기다
- `exports-v2` 의 `model_eligible = False` (사유 `npu_dispatch_not_formally_valid`)는 **실행 실패가 아니다.** 품질 게이트를 돌리지 않은 pilot 이거나 CPU 가속기 런이라 `formal_npu_valid` 가 False 인 것이다 (C5 20런 · N165 · C6 진단 · EfficientNet 경로 스모크)
- exports 의 NPU 행: `accuracy_preflight_status` 는 MobileNet CPU↔GPU 검사 결과이고 NPU 품질 게이트가 아니다. `execution_profile_type` 은 `cpu_not_applicable` 로 찍힌다
- GPU 런(`S26_C1probe_gpu600_0927` · `S26_C1a_gpu1300_0928` · `S26_M3_gpud50_0928`)은 LiteRT 1.4.2 CompatibilityList 의 미지원 판정을 기록만 하고 진행한 자료다
- 결과 해석은 `../C2_RESULTS_0928.md` (EfficientNet NPU formal) · `../THROTTLE_CURVE_0928.md` · `../C1A_RESULTS_0928.md` · `../NIGHT_0927_RESULTS.md` · `../NIGHT_0928_RESULTS.md` · `../../npu/results/NPU_FORMAL_RESULTS.md`
