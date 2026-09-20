# G1 AOT 컴파일 결과 — 2026-09-19 (Colab, Ubuntu 24.04 x86_64) — **PASS**

도구: `tools/s26_npu_aot_compile.py` · `ai-edge-litert-nightly 2.3.0.dev20260917` + `ai-edge-litert-sdk-samsung-nightly 2.3.0.dev20260917` (LiteCore SDK 16 .so, `libcdi_9965.so` 포함) · 타깃 `Samsung_E9965`

| 입력 | 입력 SHA-256 (앞 16) | 산출물 | 크기 | 파티션 | 판정 |
|---|---|---|---|---|---|
| `mobilenet_v1_1.0_224.tflite` (16,901,128 B) | `d95b3c5ea86750ce` | `mobilenet_v1_1.0_224_Samsung_E9965.tflite` | **8,901,712 B** | **31 / 31 ops → 1 partition** (전 그래프 NPU) | PASS |
| `mobilenet_v1_1.0_224_quant.tflite` (4,276,352 B) | `ecc3a67c47c5a609` | `mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite` | **4,605,104 B** | **31 / 31 ops → 1 partition** | PASS |

컴파일 시간 각 ≈3 s. `DISPATCH_OP` 1개, 비-dispatch 연산자 0개 (`--inspect`).

## 읽는 법

- FP32 산출물이 원본의 **0.53배** → 가중치가 FP16 으로 저장됨 = NPU 에서 **FP16 실행** (Geekbench 의 "FP32 는 NPU 자원이 아니다" 와 일치). 프로파일 표기: `npu_precision = fp16(compiler-default)`
- uint8 QAT 모델(NEXT_3WEEKS §3.4 의 그 파일)도 **거부되지 않고 전 그래프 컴파일**됨 — Geekbench 의 INT8 분류 정확도 붕괴(0.014)는 컴파일 실패가 아니라 **실행 결과의 문제**일 수 있으므로 G3 에서 argmax 일치율로 반드시 확인
- 두 산출물 모두 CPU Interpreter 로는 열리지 않는다(`DISPATCH_OP` 커스텀 op). "동작 확인" 을 CPU 로 하려 하지 말 것

## 겪은 문제 (기록)

1. nightly wheel 패키징 버그: `libLiteRtCompilerPlugin_Samsung.so` 가 `flatbuffers::ClassicLocale::instance_` 를 참조하나 정의가 없음 → `undefined symbol: _ZN11flatbuffers13ClassicLocale9instance_E` 로 플러그인 로드 실패(dev20260913·dev20260917 동일). 스크립트가 같은 정의를 가진 shim `.so` 를 g++ 로 빌드해 `LD_PRELOAD` 하도록 수정 → 해결. LiteRT GitHub 이슈 등록 예정 (재현 로그: 첫 시도의 `/tmp/*.error` 전문 보관 — 대화 기록)
2. Samsung SDK tarball 은 Colab 에서 인증 없이 받아짐 (계획서 §1 사실 3 의 우려 해소)

## 산출물 위치

`artifacts/compiled_e9965/` — **주의: 9/19 01:00 시점 로컬 폴더에는 첫 실패 실행의 0 바이트 파일과 옛 manifest 가 있음. 성공 실행의 폴더를 Colab 에서 다시 내려받아 덮어쓸 것** (`*_Samsung_E9965.tflite` 8.9 MB / 4.6 MB, `aot_manifest.json` 에 `"failed_backends": []`, `fb_classic_locale_shim.cpp`, `libfb_classic_locale_shim.so`).

## 다음: G2 (dispatch 빌드) → G3 (첫 추론)

`tools/build_litert_samsung.sh` 를 Colab 에서 실행 → `litert_samsung_arm64/` (dispatch .so + `run_model` CLI) → `artifacts/` 저장 → `tools/s26_npu_run_model.bat` 로 폰에서 NPU fp32·int8 + CPU 대조 실행.
