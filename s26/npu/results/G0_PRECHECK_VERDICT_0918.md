# G0 사전점검 판정 — 2026-09-18 (S26, 무선 adb)

> ## ⚠ 2026-09-19 00:40 정정 — 최종 판정 **PASS** (경로 A 가능)
> 어제 판정은 `libenn_public_api_cpp.so` **한 파일만** 보고 내린 것이라 틀렸다. 그 파일이 NEEDED 로 의존하는
> **`libenn_user.samsung_slsi.so`(436,344 B, 같은 ENN_VERSION_2.4.20)** 를 추가로 가져와 검사하니
> **평문 C 심볼 111개**가 있고, LiteRT 필수 15개(어제 "없음"이라던 `EnnCreateBufferFromFdWithOffset`,
> `EnnCreateBufferCache` 포함)와 선택 5개가 **전부** 들어 있다. Android(bionic) `dlsym(handle, name)` 은 열린
> 라이브러리의 DT_NEEDED 의존 트리까지 탐색하므로, LiteRT 가 `dlopen("libenn_public_api_cpp.so")` 후
> `dlsym("EnnInitialize")` 하면 `libenn_user.samsung_slsi.so` 의 심볼에 결합된다. 두 라이브러리 모두
> `/vendor/etc/public.libraries.txt` 에 등재돼 있어 앱에서 접근 가능하다.
>
> - 경로 A (LiteRT CompiledModel): **현재 펌웨어(One UI 8.5)에서 가능 → 주력 복귀.** G1(AOT 컴파일)부터 진행
> - 경로 B (ENNDelegate): 헤더 확보, 구현 가능. Geekbench AI ENN 완주로 동작 실증(`EXTERNAL_REF_GEEKBENCH_0919.md`). A 의 예비
> - One UI 9 업데이트: **당장은 보류** — A 가 8.5 에서 되므로 S26 데이터를 한 펌웨어에 유지하는 편이 낫다. NPU Manager 확인은 NPU 측정이 끝난 뒤
> - 도구: `s26_npu_precheck.bat` 가 두 라이브러리를 모두 가져와 의존 트리로 판정하도록 수정됨. 재생성된 `12_enn_symbols.txt/.json` 이 정본
>
> 아래는 어제 원문(기록 보존). §"12번이 왜 결정적인가" 와 §"판정과 분기" 의 A 불가 결론은 **철회**.


원본: `../device/11_npu_precheck.txt`, `12_enn_symbols.txt`(+`.json`), `13_nnapi_probe_logcat.txt`
기기: `SM-S942N` / `s5e9965` / Android 16 · SDK 36 · **One UI 8.5 (`ro.build.version.oneui=80500`)** · 빌드 `BP4A.251205.006.S942NKSS4AZHA` (펌웨어 코드 ZHA = 2026-08)

## 한 줄

**NPU 하드웨어·ENN 런타임은 앱에서 접근 가능하지만, 현재 펌웨어의 ENN 공개 API(2.4.20)는 LiteRT Samsung dispatch 가 요구하는 것보다 구버전이라 경로 A(LiteRT)는 이 펌웨어에서 막힌다. 경로 B(ENNDelegate)는 영향 없음 → B 를 주력으로 승격, A 는 OS 업데이트 후 재검사.**

## 항목별

| # | 확인 | 결과 | 뜻 |
|---|---|---|---|
| 2 | `android.hardware.npu` | 없음 | 예상대로 (Android 17 기능). 프레이밍용 |
| 3 | `service list` 의 enn/neural | **0건** | ENN HAL 이 framework servicemanager 에 등록돼 있지 않거나 shell 에서 안 보임. 결정적이지 않음(Galaxy AI 가 NPU 를 쓰고 있으므로 런타임은 살아 있음). 원인은 B 스모크에서 드러남 |
| 4 | ENN public libs | `libenn_public_api_cpp.so` 등 4개, `/vendor/etc/public.libraries.txt` 등재 | **앱이 dlopen 가능** ✅ |
| 5 | vendor ENN 스택 | engine/model/user_driver(cpu/gpu/unified)/wrapper/AIDL-V1 전부 존재 + `libtflitecore.so` | 스택 완비 ✅ |
| 6 | 플랫폼 LiteRT 라이브러리 | 없음 | 예상대로 — 앱이 dispatch 를 번들해야 함 |
| 7 | AICore | Google aicore `…samsungslsi.prod_aicore_20260723…`, Samsung aicore 2.1.09.55 | Google AICore 의 삼성 S.LSI 전용 빌드가 있음 = Google↔Samsung NPU 협업 흔적 |
| 11 | NNAPI 프로브 (D1NPU 로그 2회) | `nnapi-reference`, `type_name=CPU`, `reference_cpu=true`, `npu_verification=UNVERIFIED` | **NNAPI 배제 확정** (경로 F 종결) |
| 12 | `libenn_public_api_cpp.so` 심볼 | **`ENN_VERSION_2.4.20`**. 동적 심볼 85개 중 Enn* 79개가 **전부 C++ `enn::api::` 맹글링**, 평문 C 심볼 0개. LiteRT 필수 15개 중 13개는 C++ 형태로만 존재, **2개(`EnnCreateBufferFromFdWithOffset`, `EnnCreateBufferCache`)는 어떤 형태로도 없음** | 아래 |

## 12번이 왜 결정적인가

LiteRT `enn_manager.cc` 는 `dlopen("libenn_public_api_cpp.so")` 후 **평문 이름으로 `dlsym("EnnInitialize")`** 한다(`#SYM` 매크로, 대안 이름 없음). 이 펌웨어의 라이브러리는 `_ZN3enn3api13EnnInitializeEv` 만 내보내므로 첫 심볼에서 `kLiteRtStatusErrorDynamicLoading` 으로 끝난다. 게다가 필수 2개는 심볼 자체가 없어 **맹글링 우회로도 해결이 안 된다** — LiteRT 가 겨냥한 ENN API 는 이 펌웨어(2.4.20)보다 새 버전이다.

→ Google 샘플의 "S26 ≈ 11 ms" 는 다른 펌웨어(개발용 또는 One UI 9 계열)일 가능성이 높다. 9/16 계획서 §1 사실 2 의 "핵심 근거" 는 **"라이브러리 접근 가능" 까지만 참**이고 "심볼 결합 가능" 은 거짓으로 정정한다.

## 판정과 분기 (계획서 §3 G0 실패 분기 그대로)

| 경로 | 판정 | 근거 |
|---|---|---|
| A. LiteRT CompiledModel (AOT/JIT) | **현재 펌웨어에서 불가 → 보류** | 12번. One UI 9(Android 17) 정식 배포 후 `s26_npu_precheck.bat` 재실행 → `VERDICT: PASS` 나오면 재개. 소프트웨어 업데이트 대기 중이면 먼저 확인 |
| B. ENNDelegate (Interpreter 델리게이트) | **주력으로 승격** | Samsung 이 배포하는 wrapper(3.1.14, 2026-08, `libcdi_2600.so` 포함)는 이 C++ API 위에서 동작하도록 만들어진 것. Geekbench AI 1.7 이 같은 계열(ENN 3.1.13)로 최신 Exynos 를 지원 |
| D. Geekbench AI (Samsung ENN) | 오늘 실행 | "이 펌웨어에서 NPU 가 돈다" 는 가장 빠른 증거 + B 의 동작 가능성 확인 |
| F. NNAPI | 종결 | 11번 |

## 다음 행동

1. **Geekbench AI 1.7** 설치 → 프레임워크 Samsung ENN → 실행 → 완료 여부·점수·항목별 시간 캡처 (`external_ref.md`). 실패하면 B 도 위험 신호
2. **ENNDelegate 아카이브 열기** — 아카이브는 리눅스 셸 스크립트라 WSL2 또는 Colab 에서 `bash ENNDelegate_v3.1.14_archive` → `I ACCEPT` → `ENNDelegate_v3.1.14/include/enn_wrapper_sq.h`, `enn_wrapper_log.h`, `License.pdf` 를 확보해 공유. 헤더에 `TfLiteDelegate` 생성 함수가 있으면 benchmark-runner 에 JNI 래퍼로 붙이는 스펙을 작성한다 (Interpreter 경로 그대로 → 엔진 차이 변수 없음 = 오히려 A 보다 나은 결과)
3. 폰: 설정 → 소프트웨어 업데이트 → 대기 중 업데이트 유무 확인. One UI 9 가 오면 팀 결정(일상폰 업데이트 시점)
4. 계획서 §3 시간상자(9/25 G3)는 유지. B 로 9/25 까지 첫 NPU 추론이 안 나오면 NPU 는 `null`
5. 9/18 회의 보고 문구: "NPU 는 하드웨어·런타임·앱 접근성까지 확인됐고, Google 경로는 펌웨어 API 버전 문제로 보류, 삼성 델리게이트 경로로 진행 중"

## 도구 수정

`s26_npu_symbols.py` 가 cp949 콘솔에서 죽던 문제(비ASCII 출력) 수정 + C/C++ 형태 구분·`ENN_VERSION` 추출 추가. `12_enn_symbols.txt/.json` 은 수정판으로 재생성(폰 재접속 불필요 — 가져온 .so 를 다시 검사한 것).
