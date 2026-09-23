# G4 — `npu-runner` 앱 실행 결과 (2026-09-24 새벽)

기기 `SM-S942N` / Exynos 2600 / Android 16 SDK 36 / One UI 8.5 (`S942NKSS4AZHA`)
무선 adb `<IP:PORT>` · 모듈 `npu-runner` (LiteRT Next `CompiledModel`)

> **한 줄**: 9/19에 셸 바이너리로 막혔던 구간을 앱이 **전부 통과**했다.
> `CompiledModel.run()` 한 칸만 남았고, 실패 메시지는 `Failed to allocate tensors`다.

---

## 1. G3(셸)와 G4(앱)의 차이

| 단계 | G3 셸 `run_model` (9/19) | G4 앱 `npu-runner` (9/24) |
|---|---|---|
| dispatch `.so` 로드 | ✅ | ✅ |
| ENN 2.4.20 로드 | ✅ | ✅ |
| ENN AIDL HAL lazy 기동 | ✅ | ✅ |
| binder 스레드 풀 | ❌ `MediumInterface initialization failed` | **✅ 통과** |
| 시스템 lib 링크 | ❌ `CANNOT LINK EXECUTABLE … libandroidfw.so` | **✅ 통과** |
| LiteRT 런타임 초기화 | 도달 못 함 | **✅ NPU accelerator registered** |
| AOT 모델 인식 | 도달 못 함 | **✅ pre-compiled 인식** |
| dispatch 라이브러리 탐색 | 도달 못 함 | **✅ 통과** |
| 텐서 할당 · 추론 | 도달 못 함 | ❌ `Failed to allocate tensors` |

**셸의 binder 제약은 앱에서 재현되지 않는다**는 가설이 실측으로 확인됐다.
`NPU_ACCESS_PLAN_0916.md`의 G4 분기 선택이 옳았다.

---

## 2. 통과까지 넘은 실패 3개 (기록)

### 2.1 배치 파일이 cmd에서 깨짐 (04:00)

`.bat`을 LF 줄바꿈 + UTF-8 한글로 썼더니 cmd가 줄 단위 파싱에 실패하고 mojibake가 났다.

> **규칙: `.bat`은 CRLF + ASCII 전용.** 콘솔 코드페이지가 cp949라 UTF-8 한글이 깨진다.
> 앱의 logcat 출력 문구도 ASCII로 통일했다 (`=== OK ===`, `first inference OK`) —
> 캡처한 로그 파일이 깨지면 판독이 불가능해지기 때문.

### 2.2 manifest merger 실패 (04:07)

```
Namespace 'com.google.ai.edge.litert' is used in multiple modules and/or libraries:
  com.google.ai.edge.litert:litert:2.2.0
  com.google.ai.edge.litert:litert-api:2.2.0
```

LiteRT Next가 AAR을 둘로 쪼개 배포하는데 **둘 다 같은 AAR namespace를 선언**한다.
AGP 9가 이 검사를 경고 → 에러로 승격시키면서 터졌다.

`litert/kotlin/BUILD`를 읽어 확인한 분담:

- `litert-api` = Kotlin API 클래스(`CompiledModel`/`Environment`/`TensorBuffer`) + `liblitert_jni.so`
- `litert` = 런타임 구현 `libLiteRt.so`

**둘 중 하나를 exclude할 수 없다.** → `gradle.properties`에 `android.uniquePackageNames=false`.
같은 문제를 TFLite 계열·Agora 분할 AAR에서 같은 방법으로 해결한 사례 확인.

한편 이 PC에서 받은 Maven 목록으로 **`litert` 최신 정식판 = 2.2.0** 확인
(`litert_maven_metadata_*.xml`). 우리가 고른 버전이 맞았다.

### 2.3 `No dispatch library found` (04:22)

```
E litert : [litert_dispatch.cc:122] No dispatch library found in
           /data/app/…/com.example.d1check.npurunner-…/lib/arm64
E litert : [dispatch_delegate.cc:131] Failed to create a dispatch delegate kernel:
           No usable Dispatch runtime found
```

`packaging { jniLibs { useLegacyPackaging = false } }` 때문이었다.
`false`면 `.so`가 APK 안에 무압축으로 남아 `base.apk!/lib/arm64-v8a` 경로로 dlopen된다.
`liblitert_jni.so`는 그래도 로드되지만 **dispatch 로더만은 디렉터리를 스캔**하는 방식이라
`lib/arm64` 디렉터리 자체가 없어서 못 찾았다. (`run-as ls lib/arm64` → `No such file or directory`)

→ `useLegacyPackaging = true`. 설치 시 실제 파일로 풀린다.

같은 실수가 반복되지 않도록 앱이 시작할 때 `nativeLibDir`와 그 내용을 기록하도록 추가했다
(`native_lib_files`, `dispatch_so_present`).

---

## 3. 현재 상태 (`G4_summary_2026-09-24422_2909.json`)

```
engine                 : litert-compiled-model
accelerator_requested  : NPU
model                  : mobilenet_v1_1.0_224_Samsung_E9965.tflite
available_accelerators : NPU,GPU,CPU
env_init_ms            : 4.806
model_init_ms          : 10.93          <- idle->NPU 전환비용 후보
buffer_init_ms         : 0.27
input_buffers          : 1
output_buffers         : 1
native_lib_files       : libLiteRt.so, libLiteRtClGlAccelerator.so,
                         libLiteRtDispatch_Samsung.so, liblitert_jni.so
dispatch_so_present    : true
input_sha256           : 5dc1cb09d712429fa580bdb7976c01d3933956d77002a8c8ab3c82c40f3899f3
status                 : FAILED
error                  : Failed to invoke the compiled model
```

`available_accelerators`에 **NPU가 포함**된다는 것은 런타임 AAR(2.2.0)과 우리가 빌드한
dispatch(`main@9380426b`)의 **ABI가 맞았다**는 뜻이다. 계획 단계에서 가장 걱정했던 항목이 해소됐다.

네이티브 로그(`G4_DIAG_NPU_2026-09-24414_3202.txt`):

```
litert : Loaded runtime library and found kLiteRtRuntimeBuiltin.
litert : Creating LiteRT environment with options
litert : NPU accelerator registered.
litert : XNNPACK CPU accelerator registered.
litert : Compiler plugin path is provided, but the model is pre-compiled.   (정상 — AOT)
litert : Flatbuffer model initialized directly from incoming litert model.
litert : [litert_compiled_model.cc:164] Failed to allocate tensors          <- 마지막 지점
```

---

## 4. 남은 가설

| # | 가설 | 확인 방법 |
|---|---|---|
| 1 | **텐서 버퍼 타입 불일치.** ENN이 `AHardwareBuffer`/dmabuf를 요구하는데 호스트 메모리로 할당됨 | `CompiledModel.getInputBufferRequirements()`의 `supportedTypes`/`bufferSize`/`strides`를 기록하고 그 타입으로 재할당 |
| 2 | **버전 skew.** AOT 컴파일러 `2.3.0.dev20260917` ↔ 폰 ENN `2.4.20` ↔ dispatch `main@9380426b` ↔ 런타임 AAR `2.2.0` | 로그의 ENN 버전 문자열. 필요 시 dispatch를 2.2.0 태그로 재빌드 |
| 3 | **권한.** 앱 uid의 ENN AIDL 호출 차단 | logcat `avc: denied` 검색 |

가장 유력한 것은 1번이다. `buffer_init_ms = 0.27`로 버퍼 생성 자체는 성공했지만,
그 버퍼가 dispatch가 요구하는 종류가 아닐 수 있다.

---

## 5. 판독 함정

- **logcat 태그는 소문자 `litert`.** `LiteRt:V`로 필터하면 0줄이 나온다. 이것 때문에 한 라운드를 버렸다.
- 앱 태그는 `D1NPU`. JSON 전문이 `SUMMARY[i/n]` 청크로 나뉘어 찍힌다(`run-as` 불필요).
- USB와 무선이 동시에 잡히면 gradle이 엉뚱한 기기에 설치한다 → `ANDROID_SERIAL` 고정.

---

## 6. 산출물

| 파일 | 내용 |
|---|---|
| `G4_GO_2026-09-24400_5217.txt` | manifest merger 실패 |
| `G4_GO_2026-09-24407_4530.txt` | 빌드 성공, `No dispatch library found` |
| `G4_DIAG_NPU_2026-09-24414_3202.txt` | 전체 logcat 520 KB — 네이티브 원인 확정 |
| `G4_GO_2026-09-24422_2909.txt` | dispatch 탐색 통과, `Failed to allocate tensors` |
| `G4_summary_2026-09-24422_2909.json` | 위 §3 |
| `litert_maven_metadata_*.xml` | `litert` 배포 버전 목록 (최신 2.2.0) |

코드: `D1Check_v4\npu-runner\` (브랜치 `s26-measure`, 미커밋)
도구: `npu\tools\s26_npu_go.bat`, `s26_npu_diag.bat`

---

## 7. 시간상자

**9/25.** 미달 시 NPU는 `null`로 두고 CPU/GPU 2자원으로 진행
(`NPU_ACCESS_PLAN_0916.md` §3). 현재 진척으로 볼 때 남은 것은 텐서 버퍼 계약 하나이므로
시간상자 안에 결론이 난다고 본다 — 통과든 미달이든.
