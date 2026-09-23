# G4 판정 — 2026-09-24 새벽 (S26, 무선 adb, AC 충전 중)

> ## ⚠ 이 문서는 타이밍·에너지 수치를 기록하지 않는다
> 오늘 밤 실행은 **무선 adb + AC 충전 중**(`dumpsys battery`: `AC powered: true`, `plugged != 0`)이라
> 측정 안전 게이트 밖이다. 요약 JSON에 `latency_ms`·`model_init_ms`가 찍혀 있지만 **판정 근거로 쓰지 않고
> 여기에도 옮기지 않는다.** 이 문서가 판정하는 것은 "NPU에서 돌았는가"와 "출력 품질이 CPU와 동등한가" 둘뿐이다.
> 결과 파일명에는 전부 `_WIRELESS_ACPLUGGED_`를 넣었다(밤샘 지시문의 `_NOCHARGE_`는 실제 상태와 달라서 쓰지 않았다).
>
> 근거 라벨: `[P]` 실측 / `[D]` 문서 근거 / `[E]` 추정

원본 (전부 `results\`):
`G4_DIAG_NPU_2026-09-24455_1519_WIRELESS_ACPLUGGED.txt`(수정 전 네이티브 로그) ·
`G4_GO_2026-09-24452_5268_WIRELESS_ACPLUGGED_CPU.txt`(CPU 대조군) ·
`G4_GO_2026-09-24456_4289_WIRELESS_ACPLUGGED_NPU.txt`(첫 NPU 성공) ·
`G4_GO_2026-09-24500_0638_WIRELESS_ACPLUGGED_NPU_GATE.txt` / `…506_1569_…_NPU_GATE_FINAL.txt`(품질 게이트 2회) ·
`G4_GO_2026-09-24502_2852_WIRELESS_ACPLUGGED_NPU_U8.txt`(INT8) · 같은 타임스탬프의 `G4_summary_*.json`
(`…501_3075_…_NPU_U8.*`은 INT8 출력 해석 버그 수정 **전** 실행 — 출력값 무효, 기록 보존용.
`…452_1246_…_ENVFAIL.txt`는 이 세션 셸이 cwd의 `gradlew.bat`을 못 찾아 빌드 전에 끝난 실행)

기기: `SM-S942N` / `s5e9965` / Android 16 · SDK 36 · One UI 8.5 · 빌드 `BP4A.251205.006.S942NKSS4AZHA` (밤새 변동 없음 [P])

## 한 줄

**G4 PASS [P].** S26 NPU에서 AOT MobileNet V1(FP32 입력, FP16 가중치)이 `DispatchDelegate` 1/1 노드로 실행됐고
품질 게이트(결과 보기 전 고정: 비트 비동일 · argmax 32/32 · `cosine_min ≥ 0.99`)를 **PASS**했다
(0/32 · 32/32 · 0.99972). 막혀 있던 원인은 dispatch ABI가 아니라 **매니페스트의 `<uses-native-library>` 누락**이었고,
한 줄로 풀렸다. **Colab dispatch 재빌드는 필요 없다.**

## 항목별

| # | 확인 | 결과 | 라벨 | 뜻 |
|---|---|---|---|---|
| 1 | 04:14 `No dispatch library found`의 정체 | 같은 로그 머리에 `ls: lib/arm64: No such file or directory`. `useLegacyPackaging=true` **수정 전** 실행 | [P] | 파일이 "있는데 거부"가 아니라 **디렉터리가 없었다.** ABI 근거가 아님 |
| 2 | 수정 후 dispatch 탐색 | `litert_dispatch.cc:159 Loading shared library: …/lib/arm64/libLiteRtDispatch_Samsung.so` | [P] | 04:22 이후 빌드는 dispatch를 찾아 로드한다 |
| 3 | ABI 핸드셰이크 | `LiteRtDispatchGetApi` 후 `dispatch_api.cc:84`의 Initialize까지 진입. `Found Dispatch API with an unsupported version` **0건** | [P] | 2.2.0 런타임에 이 거부 문자열이 실재함을 `llvm-strings`로 확인 [P]. 버전 거부였다면 이 줄이 찍혔다 → **ABI 가설 기각** |
| 4 | 수정 전 실패 지점 | `enn_manager.cc:79 Loading from: libenn_public_api_cpp.so` → `:81 Failed to load enn runtime` → `No usable Dispatch runtime found` → `Node number 1 (DELEGATE) failed to prepare` → `Failed to allocate tensors` | [P] | 인과 사슬 전체가 로그에 있다 |
| 5 | 원인 | `targetSdk = 37`, `libenn_public_api_cpp.so`는 `/vendor/etc/public.libraries.txt` 등재 [P], 매니페스트에 `<uses-native-library>` 없음 [P]. Android 12부터 targetSdk 31+ 앱은 선언한 벤더 공개 라이브러리만 볼 수 있다 [D] | [P]+[D] | G0 문서의 "public.libraries.txt 등재 → 앱에서 접근 가능"은 **선언 조건이 빠진 반쪽 사실**이었다 |
| 6 | 권한(SELinux) 가설 | 수정 전 전체 logcat에서 `avc:` **0건** | [P] | 기각 |
| 7 | 버퍼 타입 가설 | 호스트 메모리 버퍼(`createInputBuffers()` 기본값) 그대로 성공 | [P] | 기각 |
| 8 | 수정 | `npu-runner/src/main/AndroidManifest.xml`에 `<uses-native-library android:name="libenn_public_api_cpp.so" android:required="false"/>` 한 줄. 버전·dispatch·폴백 **무변경** | [P] | 한 번에 한 가설, 1회 시도로 통과 |
| 9 | 수정 후 ENN | `SetGenAiPerfConfigFromSoc: SOC=s5e9965` · `Replacing 1 out of 1 node(s) with delegate (DispatchDelegate)` · 바이트코드 8,900,608 B 메모리 적재 · `Buffer info - inputs: 1, outputs: 1` | [P] | **전 그래프가 NPU dispatch로 실행** |
| 10 | 출력 | NPU `output_sha256 95cec3f7…` (3회 실행 동일) ≠ CPU `0ef50910…`. top5 인덱스 순서 동일(112, 611, 79, 814, 550). NPU top5 점수 5개는 전부 FP16로 정확히 표현되는 값, CPU는 0/5 | [P] | 결정적이고, CPU와 비트는 다르고, 순위는 같다. FP16 연산 경로의 흔적 |
| 11 | 품질 게이트 | n=32, `bit_identical_count 0`, `argmax_agreement 32/32`, `cosine_min 0.99971543`, `cosine_mean 0.99994283` → **PASS**. 최종 APK로 재실행 시 `cosine_min` 비트까지 동일 | [P] | 기준은 `NPU_RUNNER_SPEC`·CLAUDE.md에 사전 고정된 그대로 |
| 12 | 기준값이 정말 CPU인가 | 기준 엔진 로그 `Replacing 31 out of 31 node(s) with delegate (TfLiteXNNPackDelegate)` | [P] | 기준 = XNNPACK CPU, 후보 = DispatchDelegate. 섞이지 않았다 |
| 13 | INT8 AOT | `DispatchDelegate` 1/1, `status OK`, argmax 742 (uint8 점수 79/67/67/11/3) | [P] | NPU에서 돈다. **품질은 미판정** — 짝이 맞는 CPU INT8 기준 모델이 assets에 없다 |
| 14 | 설치본 무결성 | 기기 `…/lib/arm64/libLiteRtDispatch_Samsung.so` SHA `f08656a6…` = 소스 = G2 README | [P] | 헌 파일 문제 아님 |

## 가설 판정

| 가설 | 판정 | 근거 |
|---|---|---|
| dispatch ABI 불일치 (main@9380426b ↔ AAR 2.2.0) | **기각** | #1, #3. 04:14 로그는 수정 전 실행, 수정 후엔 Initialize까지 진입 |
| 텐서 버퍼 타입 불일치 | **기각** | #7 |
| 앱 uid 권한 차단 | **기각** | #6 |
| 벤더 라이브러리 네임스페이스 (`<uses-native-library>` 누락) | **채택** | #4, #5, #8, #9 — 선언 한 줄 추가 전후로 실패/성공이 갈렸다 |

## 한계 (결과를 과장하지 않기 위해)

- **argmax 32/32는 변별력이 약하다.** 합성 LCG 입력 32개는 CPU·NPU 모두 argmax가 전부 112다 [P].
  실질 근거는 `cosine_min`과 비트 비동일이다. 대표 이미지셋으로 재확인해야 한다
- CPU 기준은 `npu-runner` 안의 CompiledModel CPU(XNNPACK)다. benchmark-runner의 Interpreter CPU(LiteRT 1.4.2)와의
  엔진 대조는 별도 항목(CLAUDE.md §7-2)
- INT8 품질 미판정. Geekbench AI의 ENN INT8 정확도 0.014 붕괴 기록(`EXTERNAL_REF_GEEKBENCH_0919.md`)과 대조할 재료가 아직 없다
- 모델이 MobileNet V1이다. 팀 계약(PLAN 4.4)은 EfficientNet-Lite0 / EfficientDet-Lite0 → AOT 재컴파일 필요

## 판정과 분기

| 관문 | 판정 | 근거 |
|---|---|---|
| G4 앱 추론 | **PASS** | 위 #9~#12 |
| G5 프로토콜 정합 | 착수 가능 | 무선 + **비충전** 조건에서 CPU 대조 → 엔진 대조 → pilot → formal |
| Colab dispatch 재빌드 (v2.2.0 태그) | **불필요 — 보류** | #3. 재빌드하면 오히려 오늘 검증한 조합이 바뀐다 |

## 다음 행동

1. 충전 케이블을 뽑은 무선 상태에서 `s26_npu_go.bat <ip:port> NPU float 50` 1회 → 게이트 재확인 후 CLAUDE.md §7 순서대로 G5
2. EfficientNet-Lite0 / EfficientDet-Lite0 AOT 파티션 판정 (`tools\COLAB_G1B_NEWMODELS.py`)
3. 대표 이미지셋으로 품질 게이트 재실행 (argmax 변별력 확보)
4. `mobilenet_v1_1.0_224_quant.tflite`를 CPU 기준으로 확보 → INT8 품질 게이트
5. `조민규_요청_0925.md` 근거 3줄의 "남은 건 G4 앱 실행 하나"를 "G4 통과"로 고쳐서 보낼 것

## 도구·코드 수정

| 파일 | 수정 | 이유 |
|---|---|---|
| `npu-runner/src/main/AndroidManifest.xml` | `<uses-native-library>` 추가 | #8 — G4 해결 |
| `npu-runner/src/main/java/NpuQualityGate.kt` (신규) | 품질 게이트 구현 | 세 판정이 코드에 없었다 |
| `NpuRunnerActivity.kt` / `NpuDeterministicInput.kt` | `quality_n`·`ref_model_asset` extra, 32개 연속 입력 생성 | 위 게이트 연결 |
| `NpuBenchmarkEngine.kt` `runInt8()` | `readInt8()`을 먼저 읽도록 순서 교체 | `readFloat()`가 uint8 텐서에서 예외 없이 쓰레기(9.4e-38)를 반환 [P] |
| `tools\s26_npu_go.bat` | logcat 필터에 `litert:V tflite:V` 추가 · `gradlew` 절대경로 · `timeout`→`ping` · 빈 줄 `echo(` · NPU float에 `quality_n 32` | `LiteRt:V`만으로는 0줄(04:22 로그에 네이티브 줄이 없던 이유) · 비대화형 셸에서 cwd 실행 차단/`timeout` 즉시 실패 |
| `tools\s26_npu_diag.bat` | `timeout`→`ping` | 비대화형 실행에서 25초 대기가 0초가 되어 추론 전에 로그를 떠버림 |
