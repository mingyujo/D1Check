# s26/npu — Galaxy S26 (Exynos 2600) NPU 측정 경로 확보

작성: 영훈, 2026-09-16 ~ 09-20. 상위 문서: `NPU_ACCESS_PLAN_0916.md` (계획·관문), `runner/NPU_RUNNER_SPEC.md` (구현 스펙, 조민규/Codex용).

## 현재 상태 (2026-09-24)

| 관문 | 상태 | 근거 |
|---|---|---|
| G0 기기 사전점검 | **PASS** | ENN 런타임 2.4.20이 앱에 공개(`public.libraries.txt`), LiteRT dispatch가 요구하는 C 심볼 15+5가 `libenn_user.samsung_slsi.so`에 전부 존재. NNAPI는 `nnapi-reference`(CPU)만 → 배제 확정. `results/G0_PRECHECK_VERDICT_0918.md` |
| 외부 대조군 | 완료 | Geekbench AI 1.7 + Samsung ENN 백엔드로 이 펌웨어에서 NPU 완주(fallback 0). FP16/INT8만 NPU 속도, FP32는 16~20× 느림, INT8 분류 정확도 붕괴(0.014). `results/EXTERNAL_REF_GEEKBENCH_0919.md` |
| G1 AOT 컴파일 | **PASS** | MobileNetV1 FP32·INT8 → E9965, **31/31 연산자 NPU** 1파티션. FP32 산출물이 원본의 0.53배 = FP16 실행. `results/G1_AOT_RESULT_0919.md`, `artifacts/compiled_e9965/` |
| G2 dispatch 빌드 | **PASS** | LiteRT `main`(9380426b) Bazel 7.7.0 + NDK r27c → `libLiteRtDispatch_Samsung.so`, `run_model`. `artifacts/litert_samsung_arm64/README.md`(SHA) — 바이너리는 레포 미포함 |
| G3 첫 NPU 추론 (adb shell) | **부분** | dispatch 로드 ✅ → ENN 2.4.20 로드 ✅ → ENN AIDL HAL 서비스 기동 ✅ → **binder 스레드 풀 부재로 `MediumInterface initialization failed`** (셸 바이너리 한계; 앱 프로세스엔 해당 없음). `results/G3_run_model_20260919_054241.txt` |
| G4 `npu-runner` 앱 통합 | **PASS** (9/24) | `DispatchDelegate` 1/1 노드로 NPU 추론 성공, 품질 게이트 PASS(비트 비동일 0/32 · argmax 32/32 · cosine_min 0.99972). 막혔던 원인은 ABI가 아니라 매니페스트 `<uses-native-library>` 누락. 무선·AC충전 실행이라 타이밍 무효. `results/G4_VERDICT_0924.md` |

## 다음 두 갈래 (둘 다 준비됨)

1. 셸에서 마지막 시도: `tools/binderpool_shim.c` 를 NDK로 빌드(`tools/build_binderpool_shim.sh`) → `libbinderpool_shim.so` 를 `artifacts/litert_samsung_arm64/` 에 두고 `tools/s26_npu_run_model.bat` 재실행 (자동 `LD_PRELOAD`)
2. 앱 경로 G4: `npu-runner` 모듈 — 스펙 §2~§5. 앱에서는 binder 스레드 풀·vendor 라이브러리 경로 문제가 모두 사라진다

## 폴더

```
NPU_ACCESS_PLAN_0916.md      계획·관문·측정 설계 (9/19 정정 포함)
runner/NPU_RUNNER_SPEC.md    npu-runner 구현 스펙 (dispatch 빌드 절차, Kotlin 스케치, JSONL 필드, formal_npu_valid)
tools/                       precheck(bat/py), AOT 컴파일(py), dispatch 빌드(sh), run_model 스모크(bat), binder shim(c/sh)
device/                      G0 원본 로그 (11_, 12_, 13_)   ※ 벤더 .so 사본은 커밋 제외
results/                     G0/G1/G4 판정, Geekbench 대조군(md+json), G3 run_model 로그, G4 실행 로그·요약 JSON
                             ※ G4_DIAG_NPU_*.txt(전체 logcat, SIM/eSIM 라인 포함)는 커밋 제외
artifacts/compiled_e9965/    E9965용 컴파일 모델 2개 + manifest + report + flatbuffers shim 소스
artifacts/litert_samsung_arm64/README.md   빌드 provenance·SHA (바이너리 제외)
```

## 겪은 함정 (재현 시 참고)

- LiteRT nightly(2.3.0.dev2026091x) Samsung 컴파일러 플러그인의 `flatbuffers::ClassicLocale::instance_` 미정의 → `s26_npu_aot_compile.py` 가 shim을 자동 빌드·`LD_PRELOAD`
- Android 빌드의 absl 플래그 이름 제거(`ABSL_FLAGS_STRIP_NAMES=1`) → `build_litert_samsung.sh` 에 `-DABSL_FLAGS_STRIP_NAMES=0`
- Windows adb: 로컬 경로에 `..\` 가 있으면 원격 파일명이 깨짐 → 절대경로 + 원격 파일명 명시
- 앱(targetSdk 31+)도 `/vendor/etc/public.libraries.txt` 의 ENN 라이브러리를 **매니페스트 `<uses-native-library>` 선언 없이는** 못 봄 → `Failed to load enn runtime` → `Failed to allocate tensors` (G4, 9/24)
- 셸 바이너리는 `/vendor/lib64` 를 못 봄. `/vendor/lib64` 전체를 `LD_LIBRARY_PATH` 에 넣으면 시스템 라이브러리가 벤더 사본으로 가려져 링크 실패 → ENN 체인 4개만 옆에 복사
