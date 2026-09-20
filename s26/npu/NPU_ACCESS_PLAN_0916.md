# S26 NPU 접근 — 다각도 계획 (Gate G0~G5)

> **2026-09-19 정정 — G0 최종 PASS**: `libenn_public_api_cpp.so` 가 의존하는 `libenn_user.samsung_slsi.so` 가 LiteRT 필수 C 심볼 15+5 를 전부 내보낸다(dlsym 은 의존 트리까지 탐색). **경로 A(LiteRT) 는 현재 펌웨어(One UI 8.5)에서 가능 → 주력 유지, G1 진행.** 경로 B 는 헤더 확보·Geekbench 로 동작 실증, 예비. NNAPI 배제 확정. One UI 9 업데이트는 NPU 측정 완료까지 보류(데이터를 한 펌웨어에 유지). 상세: `results/G0_PRECHECK_VERDICT_0918.md`(정정 포함), `results/EXTERNAL_REF_GEEKBENCH_0919.md`.

작성: 2026-09-16, 영훈. **D-36** (1차 서류 10/22 17:00)
대상 기기: Galaxy S26 `SM-S942N`, Exynos 2600 (`s5e9965` = **E9965**), Android 16 / SDK 36
근거: `measure/s26/device/10_npu_runtime.txt`(9/13 프로브), `S26_DEVICE_PROFILE.md` §4, `NEXT_3WEEKS.md`, 그리고 오늘 조사한 외부 출처(§8)

> **한 줄**: 9/13 에 "최대 리스크"로 적었던 *LiteRT NPU 사이드로드 가능 여부*는 오늘 조사로 **가능**으로 바뀌었다.
> 필요한 부품 3개 중 **2개(AOT 컴파일러, 기기 쪽 ENN 런타임)는 지금 바로 있고**, 1개(`libLiteRtDispatch_Samsung.so`)만 소스 빌드가 필요하다.
> NPU 는 "자원 하나 추가"가 아니라 **두 번째 실행 엔진**이므로, 기존 CPU/GPU 측정기(LiteRT 1.4.2)를 건드리지 않는 **별도 APK 모듈**로 붙인다.

---

## 0. 지난 실패는 무엇이었나

| 9/13 시점 | 사실 | 오늘 판정 |
|---|---|---|
| NNAPI 로만 접근 시도 (`nnapi_probe.cpp`) | S26 에 NNAPI 벤더 HAL 없음 (`lshal`/`service list` 에 neural 0건) → `nnapi-reference`(CPU) 만 나올 것 | **NNAPI 는 배제 확정.** 프로브 실제 로그(`09_nnapi_probe.txt`)만 남기면 끝 (G0 에 포함) |
| Samsung ENN 라이브러리 존재 확인만 함 | `libenn_public_api_cpp.so` 등 4개가 `public.libraries.txt` 에 등재 = 일반 앱이 dlopen 가능 | **이게 열쇠.** LiteRT 의 Samsung dispatch 가 바로 이 라이브러리를 dlopen 한다 (§1) |
| "LiteRT NPU = CompiledModel, PODAI 배포, 사이드로드 미확인" | Google·Samsung 공식 문서 모두 **개발 빌드에서 라이브러리를 직접 번들**하는 절차를 제공. Play 는 배포 편의일 뿐 | 리스크 해소. 단 Samsung 용 prebuilt 가 8월 릴리스 zip 에 **아직 없음** → 빌드 필요 |

즉 실패한 것은 "NPU 접근"이 아니라 "**NNAPI 라는 죽은 문**"이었다. 살아 있는 문은 ENN 이고, LiteRT 가 그 문을 여는 공식 열쇠다.

---

## 1. 확인된 사실 (출처 있는 것만)

| # | 사실 | 출처 |
|---|---|---|
| 1 | Exynos 2600(E9965)은 LiteRT NPU **공식 지원 SoC** (E9955/E9965 두 개뿐). AOT·JIT 모두 지원. 요구 API 36 = S26 충족 | Google LiteRT Samsung 페이지(2026-06-16), Samsung LiteCore 문서 "Supported Devices" |
| 2 | LiteRT Samsung dispatch(`libLiteRtDispatch_Samsung.so`)는 기기의 **`libenn_public_api_cpp.so` 를 dlopen** 하고 `EnnInitialize`·`EnnExecuteModel` 등 15개 필수 + 5개 선택 심볼을 dlsym 한다. S26 은 이 .so 가 `public.libraries.txt` 에 있음 | LiteRT `vendors/samsung/dispatch/enn_manager.cc`, S26 프로브 §3 |
| 3 | AOT 컴파일러: `pip install ai-edge-litert-nightly ai-edge-litert-sdk-samsung-nightly` → `aot_compile(model, target=[samsung_target.Target(SocModel.E9965)])`. **Linux x86_64 전용**. 후자는 설치 시 Samsung 사이트의 공개 URL 에서 `ai-litecore-ubuntu2404-v1.2.0.tar.gz` 를 인증 없이 받도록 짜여 있다 (setup.py 는 `urllib` 단순 다운로드). 단 LiteRT 의 Bazel 규칙 주석에는 "아직 공개 리소스 아님" 문구가 남아 있어 **실제 다운로드 가능 여부는 G1 첫 단계에서 확인** — 막히면 Samsung 계정 로그인 후 LiteCore Release 페이지에서 수동 다운로드 | Samsung "LiteRT Guide", PyPI 2.3.0.dev20260913 setup.py 원문, LiteRT `third_party/exynos_ai_litecore/workspace.bzl` |
| 4 | nightly 의 Samsung target enum 에는 **E9965 만** 있다 (= 우리 기기). 컴파일 플러그인 `libLiteRtCompilerPlugin_Samsung.so`(x86_64) 는 nightly wheel 에 동봉 | wheel 내용 직접 확인 |
| 5 | LiteRT **v2.2.0(2026-08) 정식 릴리스의 NPU 런타임 zip 에는 Google Tensor·Qualcomm 만** 있고 Samsung 없음. Samsung dispatch/compiler-plugin 소스는 v2.1.6 태그부터 존재 → Bazel 로 빌드 가능 (제3자 빌드 사례: Bazel 7.7 + NDK 29, 478,144 B) | 릴리스 zip 목록 직접 확인, GitHub 코드검색 |
| 6 | 공식 샘플 `litert-samples/.../c++_segmentation` 에 `--phone=s26` 옵션이 있고, **S26 NPU E2E ≈ 11 ms** (selfie segmentation, AOT/JIT 동일) 을 보고. Samsung 은 "No extra SDK required" 로 빌드됨 | litert-samples README (2026) |
| 7 | Samsung LiteCore **v1.2.0 릴리스 노트: "Support JIT compilation"**. Ubuntu 20.04/22.04/24.04 용 3종 공개 다운로드. Exynos Lab 노트북(Colab 류)은 **로그인 필요** | Samsung Exynos Developer Society |
| 8 | Kotlin 런타임: `com.google.ai.edge.litert:litert:2.2.0` (Maven 최신). `Environment.create(context, mapOf(DispatchLibraryDir→nativeLibraryDir, CompilerPluginLibraryDir→nativeLibraryDir))` + `CompiledModel.create(assets, path, CompiledModel.Options(Accelerator.NPU), env)`. 번들 .so 는 `app/src/main/jniLibs/arm64-v8a/` | LiteRT `Environment.kt`, `AcceleratorProvider.kt`, litert-samples 마이그레이션 스킬 |
| 9 | 컴파일 산출물은 커스텀 연산자 **`DISPATCH_OP`** 로 NPU 바이트코드를 감싼 `.tflite` — 파일만 보고 "NPU 컴파일됨/부분 위임" 판정 가능 | LiteRT `build_stamp.h` |
| 10 | **ENNDelegate** (github.com/Samsung/ENNDelegate) v3.1.14, **2026-08-20** 갱신. 자가추출 아카이브(라이선스 "I ACCEPT" 필요) 안에 `libenn_wrapper.so`, `libcdi_2600.so`(=Exynos 2600), 온디바이스 컴파일러 libs, 헤더 2개. **문서 0, 2024년 이슈에 "3rd party 제공 중단" 답변.** 그러나 **Geekbench AI 1.7(2026-02)이 "Samsung ENN 3.1.13" 을 최신 Exynos 지원 백엔드로 탑재** → 같은 계열 라이브러리가 Exynos 2600 에서 실제로 돈다는 간접 증거 | 아카이브 zip 목록 직접 확인, Issue #1, Geekbench 블로그 2026-02-11 |
| 11 | Android 17 **NPU Manager**(`android.npumanager.NpuManager`, `android.hardware.npu`, NDK `ANpuManager_*`) 는 API 37. S26 은 Android 16 → 없음. One UI 9(Android 17) 정식은 삼성이 9/1 "soon" 공지, 베타 8차까지 진행 | AOSP npu-manager(2026-06-25), NDK 레퍼런스, SamMobile 9/1 |
| 12 | 외부 대조군: **Geekbench AI 1.7 은 Exynos 에서 프레임워크 "Samsung ENN"(3.1.13) 을 선택할 수 있다.** 삼성 공개 수치는 MLPerf Mobile-BERT 1199.57 QPS(2500 대비 2.1×). MLPerf Mobile 앱의 Samsung 백엔드 유무는 설치 후 확인 | Geekbench 블로그 2026-02-11, Samsung/SammyFans 2026-06-12 |
| 13 | NNAPI: 런타임(APEX)은 있으나 벤더 드라이버 없음. Android 15 부터 deprecated | 9/13 프로브 |

---

## 2. 접근 경로 비교 — 7갈래

| 경로 | 엔진 | 우리 측정기와의 관계 | 지금 없는 것 | 리스크 | 시간상자 | 우선순위 |
|---|---|---|---|---|---|---|
| **A. LiteRT CompiledModel + Samsung NPU (AOT)** | LiteRT 2.2.0 `CompiledModel` | **별도 모듈** `npu-runner` (기존 runner 무변경) | `libLiteRtDispatch_Samsung.so` (빌드) | 런타임 2.2.0 ↔ nightly AOT 산출물 버전 불일치 가능 | G1 1일, G2 반나절, G3 1일 | **1 (주력)** |
| **A′. 같은 경로, JIT** | + `libLiteRtCompilerPlugin_Samsung.so`(arm64) + LiteCore `lib/arm64-v8a/*.so` 번들 | A 와 동일 모듈, 옵션 하나 | 위 두 가지 arm64 빌드/추출 | APK 커짐, 첫 실행 컴파일 수초 | A 성공 후 반나절 | 2 — **전환비용 연구엔 오히려 재료**(JIT 컴파일 시간 = 준비시간 항목) |
| **B. ENNDelegate** | 기존 LiteRT 1.4.2 `Interpreter` + 델리게이트 | **기존 runner 안**에 GPU 처럼 추가 (가장 이상적 형태) | API 문서 (헤더 2개뿐), JNI 래퍼 (`TfLiteDelegate*` 를 만들어 `Interpreter.Options.addDelegate`) | 무문서·비공식. 라이선스 "I ACCEPT". 단 Geekbench AI 가 같은 계열(ENN 3.1.13)을 Exynos 2600 에서 쓰므로 "돌긴 돈다" 는 알려짐 | **1.5일** | 3 — A 가 G2 에서 막히면 승격. 헤더를 열어 `TfLiteDelegate` 생성 함수가 보이면 시도 가치 큼 |
| **C. LiteRT C++ 샘플/CLI 바이너리 (adb shell)** | LiteRT C++ (`--phone=s26`) | 측정기 밖. 텔레메트리 앱만 병행 | Bazel 빌드 환경 (A 의 G2 와 같은 환경) | 앱 컨텍스트가 아니라 `/data/local/tmp` 실행 = 정식 데이터 아님 | G2 와 동시에 1시간 | 4 — **G3 대체 증거** ("S26 에서 NPU 가 돈다") |
| **D. 외부 벤치 앱 + 우리 텔레메트리** | Geekbench AI 1.7 (프레임워크 = **Samsung ENN**) / MLPerf Mobile | 측정기 밖. `app` 텔레메트리 서비스 병행 → 열·전류 | 앱 설치만 | 모델·전처리 다름 → **참고치**로만 | 30분 | 5 — 오늘 해도 됨 (서사·검증용). 결과는 "Exynos 2600 NPU 가 이 폰에서 실제로 동작한다"는 가장 빠른 증거 |
| **E. ExecuTorch Exynos backend** | 세 번째 엔진(.pte) | 별도 | 전부 | 엔진 3개 = 비교 불능 | — | 보류 |
| **F. NNAPI** | — | — | — | 벤더 HAL 없음 | 0 | **배제 확정** (로그만 보관) |
| **G. Android 17 NPU Manager** | 측정 아님 | 프레이밍(승인통제 메커니즘) | One UI 9 정식 | 일상폰에 베타 설치 비권장 | 정식 배포 후 30분 | 서류용 — `android.hardware.npu` 선언 여부·`NpuManager` 존재 확인 |

**왜 A 가 주력인가**: (1) Google·Samsung 양쪽 공식 문서가 같은 경로를 가리킨다, (2) S26 이 지원 기기 표에 이름으로 올라 있다, (3) 증거 체인이 코드로 확인된다(dispatch → `libenn_public_api_cpp.so` → ENN AIDL HAL), (4) 컴파일 산출물이 파일 단위로 검증 가능하다(`DISPATCH_OP`).
**왜 B 를 버리지 않나**: B 만이 CPU/GPU 와 **같은 Interpreter 경로**에 붙는다. 성공하면 "엔진 차이" 변수가 사라진다. 그러나 무문서라 하루 이상 쓰지 않는다.

---

## 3. 관문 (결과 보기 전에 판정식 고정)

| 관문 | 내용 | 통과 판정 | 소요 | 누구 | 실패 시 |
|---|---|---|---|---|---|
| **G0 사전점검** | `tools/s26_npu_precheck.bat` (읽기 전용, 40초). ENN AIDL 서비스·public libs·**`libenn_public_api_cpp.so` 심볼 15+5 검사**·플랫폼 LiteRT 라이브러리 유무·NNAPI 프로브 로그 수집 | `12_enn_symbols.txt` = **PASS** (필수 15개 전부 + 선택 1개 이상) | 오늘 40분 | 영훈 | 심볼 누락 → dispatch 가 못 붙음. B 로 전환, A 는 LiteRT 이슈 등록 |
| **G1 AOT 컴파일** | Colab(또는 WSL2 Ubuntu 24.04)에서 `tools/s26_npu_aot_compile.py` 로 MobileNetV1 FP32 + INT8(quant) 을 E9965 타깃 컴파일 | `aot_manifest.json` 의 verdict **PASS**(전 연산자 NPU) 또는 **PART**(잔여 CPU 연산자 기록) — 둘 중 하나. INT8 quant 모델(uint8 QAT)이 거부되면 FP32 결과만으로 통과 | 오늘~내일 1~2h | 영훈 | ① SDK tarball 다운로드 실패 → Samsung 계정 로그인 후 LiteCore Release 페이지에서 수동 다운로드, `site-packages/ai_edge_litert_sdk_samsung/data/` 에 풀기 ② Colab glibc 문제(Ubuntu 22.04 vs SDK 24.04 빌드) → WSL2 24.04 ③ 그래도 실패 → LiteCore 22.04 tarball 로 교체 |
| **G2 런타임 부품** | `libLiteRtDispatch_Samsung.so`(arm64) 확보. 1순위: LiteRT 다음 릴리스 zip 에 `samsung_runtime/` 생겼는지 확인 → 있으면 끝. 2순위: Bazel 빌드 `//litert/vendors/samsung/dispatch:dispatch_api_so --config=android_arm64` (v2.2.0 태그 권장, JIT 용 `compiler:compiler_plugin_so` 도 함께) | .so 생성 + `LiteRtDispatchGetApi` 심볼 존재(`s26_npu_symbols.py` 로 확인 가능) | 반나절 (첫 Bazel 의존성 다운로드 포함) | 영훈(WSL2/Colab) 또는 조민규 | 빌드 환경 실패 → **경로 C 와 함께 포기**하고 B 승격. 동시에 LiteRT 이슈에 Samsung prebuilt 요청 |
| **G3 첫 NPU 추론** | 최소 Kotlin 스모크(`npu-runner` 골격 또는 별도 1화면 앱): CompiledModel(NPU) 1회 추론 | ① 예외 없음 ② CPU FP32 출력과 argmax 일치·**비트동일 아님** ③ logcat `LiteRt`/`Dispatch`/`ENN` 로그 ④ 지연이 CPU 4.4 ms·GPU 3.6 ms 와 통계적으로 구분 | 1일 | 조민규(코드)+영훈(실기기) | 로드 실패 메시지 종류별 분기: "dispatch not found" → 경로/파일명, "ENN" 오류 → G0 재검토, "model" 오류 → 버전 불일치(§5.7) |
| **G4 측정기 통합** | `runner/NPU_RUNNER_SPEC.md` 대로 `npu-runner` 모듈 + orchestrator `--resources NPU` + logger `formal_npu_valid`. pilot 60 s → **formal 20런** (NPU × duty 25/50/75/100 × 5회) | 20/20 완료, 검증 체크 통과, exports-v2 에 NPU 행 | 2일 코드 + 반나절 측정 | 조민규+영훈 | — |
| **G5 NPU 티어(선택)** | NPU 에서 FP16(FP32 입력) vs INT8 — KS-D1 을 NPU 축으로 확장 | NEXT_3WEEKS §3.2 판정식 그대로 | 반나절 | 영훈 | KS-D1 CPU/GPU 결과가 먼저 |

**전체 시간상자: 9/25(W2 끝)까지 G3 미달이면 NPU 는 프로파일에 `null`(마스킹) 로 확정**하고, 서류에는 경로 D 참고치 + NPU Manager 서사만 쓴다. 이 규칙을 9/18 회의에서 합의한다.

---

## 4. 이번 주 순서 (9/16 ~ 9/18 회의 전)

- [ ] **오늘** G0: `s26_npu_precheck.bat` 실행 → `device/11~13_*.txt` 확인. runner 의 "Probe NNAPI devices" 를 먼저 한 번 눌러 둘 것
- [ ] **오늘** 경로 D: Geekbench AI 1.7 설치 → 프레임워크 **Samsung ENN**, 백엔드 NPU 선택 → 1회 실행 + `app` 텔레메트리 ON. Image Classification 항목의 시간·점수와 실행 중 AP/SKIN·전류 캡처 → `npu/results/external_ref.md`. (같은 폰에서 TensorFlow Lite/CPU·GPU 로도 한 번씩 돌리면 3자원 참고표가 된다)
- [ ] **내일** G1: Colab 새 노트북에서 `s26_npu_aot_compile.py` (스크립트 머리말 절차). 산출물 `compiled_e9965/` 를 `npu/artifacts/` 에 저장 (SHA 기록)
- [ ] **내일** G2 1순위 확인: github.com/google-ai-edge/LiteRT/releases 최신 zip 안에 `samsung_runtime` 폴더 유무
- [ ] **9/18 회의 안건**: ① NPU 시간상자(9/25) 합의 ② `npu-runner` 별도 모듈 방식 합의(§5.7) ③ 엔진 대조 3런(§5.6) 포함 여부 ④ INT8 모델 출처(uint8 QAT vs AI Edge Quantizer 재생성) — G1 결과 보고 결정 ⑤ NEXT_3WEEKS §5 의 11번 항목(STAGE_GATE "NPU 필수" vs 0911 "CPU/GPU 고정")은 **"NPU 는 S26 한정 조건부 자원"** 으로 답한다 (프로파일에 칸은 만들고, A24 는 `null`)

---

## 5. 측정 설계 — NPU 도 CPU/GPU 와 같은 프로토콜로

### 5.1 타이밍 경계 (MEASUREMENT_DEFINITION 의 6계층에 대응)

| 항목 | CPU/GPU (Interpreter, 현행) | NPU (CompiledModel) | 대응 |
|---|---|---|---|
| 준비(전환비용) | `interpreter_init` + `delegate_init` span | `npu_env_init`(Environment.create) + `npu_model_init`(CompiledModel.create = 모델 로드 + ENN 세션 오픈, JIT 면 컴파일 포함) | `switch_cost_s.idle->NPU` 로 프로파일에 들어감. **JIT 컴파일 시간은 별도 필드** `npu_jit_compile_ms` |
| 추론 1회 | `Interpreter.run(input, output)` 전후 (입력 복사 포함) | `inputBuffers[0].writeFloat()` → `run()` → `outputBuffers[0].readFloat()` **세 호출을 하나의 span** 으로 잰다 (사용자 체감 = CPU/GPU 의 run 과 같은 범위). `run()` 만의 시간은 보조 필드 `npu_run_only_ms` | `latency_ms` |
| 반복 입력 | 동일 합성 텐서 1장 반복 | **동일** (같은 LCG seed 텐서) | 입력 다양성은 측정 대상 아님 (기존 가정 유지) |
| duty | 25/50/75/100 | 동일 | — |
| 스레드 | CPU 1/2/4 | 해당 없음 (`threads=null`) | — |

### 5.2 위임 증거 (`delegate_evidence` 의 NPU 판)

GPU 의 "Replacing N out of M nodes" 에 해당하는 것이 NPU 에는 **두 층**으로 있다.

| 층 | 증거 | 어디서 |
|---|---|---|
| 컴파일 시점 | 컴파일된 `.tflite` 의 `DISPATCH_OP` 개수 / 비-dispatch 연산자 개수 (`aot_manifest.json`) | 호스트, 파일 단위 → `npu_model_partition = {dispatch_ops, non_dispatch_ops}` |
| 실행 시점 | ① logcat 태그 `LiteRt`·`LiteRtDispatch`·`ENN`/`enn` 라인 ② 예외/폴백 문자열 없음 ③ 출력이 CPU FP32 와 **비트동일이 아니면서** argmax 32/32 일치 ④ 지연 분포가 CPU/GPU 와 겹치지 않음 | 기기 → `npu_evidence.{dispatch_log_lines, enn_log_lines, fallback_evidence[], bit_identical_to_cpu, argmax_agreement}` |

`full_delegate` 의 NPU 대응 = `non_dispatch_ops == 0`. 부분 위임이면 GPU 와 같은 원칙: **"미검증"이 아니라 "부분 위임"으로 기록하고 제외하지 않는다**, 단 표에 각주.

### 5.3 정밀도

NPU 는 FP32 를 그대로 돌리지 않는다 (Exynos NPU: FP16 / A8W8 / A16W16). 따라서
- FP32 입력 모델 → NPU 는 **FP16 실행**으로 기록 (`npu_precision = "fp16(assumed by compiler)"`). 컴파일 로그에 명시되면 그 값으로.
- CPU↔NPU 출력 동등성 게이트는 GPU strict 의 atol/rtol 을 그대로 쓰면 **실패한다**. NPU 전용 게이트: argmax 32/32 + cosine ≥ 0.99 (GPU compat(fp16) 수준). 값은 pilot 에서 실측 후 9/18 이후 고정.
- INT8 은 KS-D1 의 티어 축. NPU 에서 INT8 이 FP16 보다 빠르고 싼지가 **G5**.

### 5.4 열·에너지

- 텔레메트리(1 Hz current/voltage/온도)는 `app` 서비스 그대로 → **코드 변경 없음**.
- 열 센서에 NPU 전용 항목이 없다(G0 §10 에서 재확인). NPU 발열은 AP 센서에 실린다고 가정하고, 이 가정을 서류에 명시.
- 전류 단위 µA (NEXT_3WEEKS §2 확정치) 그대로. `mJ/추론` 으로만 비교.

### 5.5 매트릭스

formal 80런(CPU 60 + GPU 20) 에 **NPU 20런**(duty 4 × 5회) 추가 = 100런. cooling 정책 `stable` 동일. 소요 ≈ 20 × 8분 ≈ 3시간.
비교표는 3열(CPU4 / GPU strict / NPU) 로 확장하고, S26 GPU 의 `formal_gpu_compat_list_override` 각주처럼 NPU 에는 **"엔진: CompiledModel 2.2.0, dispatch 소스빌드"** 각주를 반드시 단다.

### 5.6 엔진 대조 3런 (반드시)

NPU 만 다른 엔진으로 재면 "NPU 가 빨라서" 인지 "엔진이 달라서" 인지 구분이 안 된다. `npu-runner` 로 **CPU(Accelerator.CPU) duty100 60 s 를 3런** 돌려 Interpreter 경로의 CPU4 4.37 ms 와 비교한다. 차이 ≤ 5 % 면 엔진 효과 무시, 아니면 NPU 결과에 엔진 보정 각주.

### 5.7 왜 별도 APK 모듈인가

`benchmark-runner` 는 `com.google.ai.edge.litert:litert:1.4.2`(Interpreter) 이고 NPU 는 같은 좌표의 **2.2.0** 이 필요하다. 한 APK 에 두 버전은 못 넣는다. 전부 2.2.0 으로 올리면 A24·S26 의 CPU/GPU 80런이 **다른 엔진 버전으로 잰 것**이 되어 재측정(≈2일)이 필요하다. 그래서:
- `benchmark-runner`(1.4.2) **무변경** — 기존 결과 전부 유효
- 새 모듈 `npu-runner`(2.2.0) — 같은 telemetry-contract, 같은 intent 프로토콜, 같은 JSONL 스키마 + NPU 필드
- orchestrator 는 `resource == NPU` 일 때 패키지명만 바꿔 실행
상세는 `runner/NPU_RUNNER_SPEC.md`.

### 5.8 버전 고정 (provenance)

| 부품 | 버전/출처 | 기록 위치 |
|---|---|---|
| AOT 컴파일러 | `ai-edge-litert-nightly` + `ai-edge-litert-sdk-samsung-nightly` 날짜 버전, LiteCore v1.2.0 | `aot_manifest.json` |
| dispatch .so | LiteRT 태그/커밋 + Bazel/NDK 버전 + SHA-256 | `npu/artifacts/README.md` |
| 런타임 | `litert:2.2.0` | `npu-runner` build.gradle + 런 메타데이터 |
| 기기 | fingerprint `S942NKSS4AZHA_OKR4AZHA` (OS 업데이트 시 재기록) | 런 메타데이터 |

---

## 6. 알려진 함정

- **`grep -i npu` 는 `input` 을 오탐**한다 (i-**npu**-t). 9/13 프로브 §7 의 input 항목들이 그것. precheck 는 `grep -v input` 처리함.
- LiteRT 2.1.6 기준 "한 디렉터리에 dispatch 라이브러리가 여럿이면 선택이 불안정" → `jniLibs` 에는 **Samsung 것 하나만** 둔다.
- Colab 은 Ubuntu 22.04 (glibc 2.35). Samsung SDK pip 패키지는 **Ubuntu 24.04 빌드 tarball 을 고정**해서 받는다. `libgraphgen_api.so` 로드 실패(GLIBC_2.38 류)가 나면 WSL2 Ubuntu 24.04 로.
- WSL2 설치: PowerShell 관리자 → `wsl --install -d Ubuntu-24.04` → 재부팅 → Ubuntu 창에서 `sudo apt update && sudo apt install -y python3-venv python3-pip`.
- USB 연결 = plugged = 안전 게이트 거부 (기존 규칙). NPU formal 도 무선 adb.
- 일상 사용 폰 → NPU 는 Galaxy AI 기능(`com.samsung.android.aicore`)과 **경합할 수 있다**. 측정 중 카메라·번역·Bixby 사용 금지, 비행기 모드.
- Android 17(One UI 9) 로 올라가면 `android.hardware.npu` 미선언 앱은 **사이드로드는 되나** NPU Manager 중재 대상 밖일 수 있음 → `npu-runner` manifest 에 `<uses-feature android:name="android.hardware.npu" android:required="false"/>` 를 미리 넣는다. OS 업데이트 전후 결과는 섞지 않는다.

---

## 7. 산출물 위치

```
D1_ondevice/measure/s26/npu/
  NPU_ACCESS_PLAN_0916.md        ← 이 문서
  tools/s26_npu_precheck.bat     G0 (기기 읽기 전용)
  tools/s26_npu_symbols.py       ELF 심볼 검사 (precheck 가 호출, 단독 사용 가능)
  tools/s26_npu_aot_compile.py   G1 (Colab/WSL2) + --inspect
  tools/README.md
  runner/NPU_RUNNER_SPEC.md      G3~G4 구현 스펙 (조민규/Codex 전달용)
  device/                        precheck 출력 (11_, 12_, 13_) — libenn_*.so 사본은 커밋 금지
  artifacts/                     컴파일된 .tflite, dispatch .so, manifest (SHA 필수)
  results/                       external_ref.md, pilot/formal 결과
```

레포 `mingyujo/D1Check` 에는 `s26/npu/` 로 같은 구조로 올린다 (기존 절차: 로컬 클론에 쓰고 Android Studio 에서 commit+push).

---

## 8. 출처

- Google, "Samsung NPU (Exynos AI LiteCore) with LiteRT" — developers.google.com/edge/litert/next/samsung (2026-06-16)
- Google, "NPU acceleration with LiteRT" — developers.google.com/edge/litert/next/npu (2026-08-26)
- Samsung Exynos Developer Society, "Exynos AI LiteCore" 개요·릴리스(v1.2.0)·"LiteRT Guide"·"Supported Devices" — soc-developer.semiconductor.samsung.com/global/development/ai-litecore
- PyPI `ai-edge-litert-sdk-samsung-nightly` 2.3.0.dev20260913 (setup.py 의 다운로드 URL), `ai-edge-litert-nightly` 2.3.0.dev20260913 (wheel 내용)
- github.com/google-ai-edge/LiteRT — `litert/vendors/samsung/{dispatch,compiler}`, `enn_manager.cc`, `Environment.kt`, `AcceleratorProvider.kt`, `build_stamp.h`, Releases v2.2.0 자산 목록
- github.com/google-ai-edge/litert-samples — `samples/litert/image_segmentation/c++_segmentation/{use_prebuilt_litert,build_from_source}/README.md`, `skills/litert-compiled-model-migration/SKILL.md`
- github.com/Samsung/ENNDelegate — 커밋 이력(v3.1.14, 2026-08-20), 아카이브 내용, Issue #1
- AOSP, "NPU manager" — source.android.com/docs/core/perf/npu-manager (2026-06-25); Android NDK `android/npumanager/buffer.h` (API 37)
- SamMobile 2026-09-01 "Samsung confirms stable Galaxy S26 One UI 9 update is coming soon"; SammyFans 2026-06-12 (Exynos 2600 MLPerf)
- Geekbench 블로그 2026-02-11 "Geekbench AI 1.7" (Samsung ENN 3.1.13 탑재)
- ExecuTorch 1.3 docs, "Samsung Exynos Backend" (E9955/E9965, FP16/A8W8/A16W16)
