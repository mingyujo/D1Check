# A24 노트북 사전 준비 완료 — 실기기 미검증

2026-10-15 최종 갱신. **구현·PC 검증·APK 빌드까지만 완료했다. 실제 기기 연결/조회·설치·워밍업·추론·계측·Run·실측 원장 START/claim·세션 소비는 모두0이다.** 모의 fixture의 가상 원장은 임시 폴더에만 만들었고 실제 계획/원장을 소비하지 않았다.

## 작업 공간과 버전

별도 worktree `D1Check-a24-prep-20261014`, 브랜치 `codex/a24-laptop-prep-20261014`를 준비했다. 요청 문서의 원격 commit은 `38d34c62111d8ea2b71b7a808db5bdf172e56b1d`이다. 해당 브랜치의 기본 코드가 새 계획을 지원하지 않음을 확인하고 A24 benchmark/modelProbe·계약 소스를 고정 `7475b1838d538c2a163d4aeefa02327eeed6f407`에서 별도 공간에 이식했다. 원 worktree HEAD `0d4ddc6…`와 사용자 추적 변경12개 SHA, 다른 worktree HEAD는 그대로다. 데스크톱 학습·시뮬레이션·출력·원본/체크포인트를 수정하거나 재실행하지 않았다.

PC는 Windows11 Home/build26200, 물리 RAM 약8GB, Python3.11.9, Temurin17.0.20.1, Gradle9.5.0, AGP9.3.2, Android SDK37/build-tools36.0.0, NDK28.2.13676358/CMake3.22.1이다. 플랫폼 도구37.0.1은 파일/버전/SHA만 읽었으며 adb를 실행하지 않았다. host는 `.venv-a24`의 표준 라이브러리만 사용하고 pip/torch/RL 환경을 설치하지 않았다. 도구·환경 SHA는 [PC_ENVIRONMENT.json](PC_ENVIRONMENT.json), source152개 SHA는 [SOURCE_SHA256.json](SOURCE_SHA256.json), JVM 해석/Android 라이브러리 고정은 각 모듈 `gradle.lockfile`과 catalog/wrapper에 있다.

## 구현

| 영역 | 구현한 범위 |
| --- | --- |
| 새 Android opt-in | `A24PreparationActivity` / `A24PreparationScheduler`, 정확 protocol·명시 허가·새 UUID·실제 target/모델/입력 결합 없으면 실행 거절 |
| 요청/행동 | L64/C252/M128, FIFO head blocking·절대기한 EDD/FIFO 동점, 분류 CPU/GPU·탐지CPU, 전역직렬 또는 CG_DC 최대2병행 |
| WAIT/시간 | M128 각 묶음 첫 ready·전체 owner 해제 뒤 WAIT200 최대16회; timer 재판단·실제 dose; 120초 未submit 선택 rollback/dispatch stop; 210초 로그·비선점 drain |
| 완료/오류 | 긴급 output·일반 write/flush/fsync/rename/readback 완료, worker 반환 marker 뒤 AVAILABLE; 실패/미배정/미완료 전량 보존; drain 실패와 자동 재시작 차단 |
| host | 사전점검·모델/runtime4 새 identity 바인딩·요청/event/시간/owner/WAIT/완료/분모 검산·원장 template·SHA 안전 회수 |
| 미래 제어기 | 기본 오프라인 검토만; 별도 실측 허가·모든 exact SHA·실기기 등록·동결 gate 후에만 NativeClient 분기. 설치 전 base/:model_probe/:a24_preparation PID와 owner 확인, 조회 오류도 거절. 새 namespace 원장·READY 이후60초 AP·계측·회수 처리 |
| Perfetto | OFF/ON 계측을 위한 고정210초/64MiB 상한·고유 detached 세션·회수. 주파수는 관측만 하며 제어하지 않음. CLI 지원/자료손실/카운터는 DEVICE_UNVERIFIED |

기존 기본 경로와 opt-in을 구분한다. 새 모델 없는 APK에는 기존 MobileNet bundled calibration 경로의 asset 계약이 없으므로 그 회귀는 기존 modelProbe variant에서 검사했다. 기존 테스트를 삭제하거나 허용 기준을 완화하지 않았다. 새 학습/RL 정책을 구현하거나 실행한 작업이 아니다.

## PC 검증 결과

| 검사 | 실제 결과와 한계 |
| --- | --- |
| 새 전용 Python 환경 | 최종103개 PASS(제어기41 포함), 외부 Python 패키지 없이 실행 |
| Python 기존 전체 회귀 | 241개 실행, 실패0·기존 Windows symlink 권한 skip1; 당시 소스 범위. 이후 새 host 변경은 위103개로 검증 |
| Android 최종 새 variant | 신규18개 PASS: 순서/대기/용량/반환·120초 rollback·미허가 entry·모의 실행 |
| 기존 modelProbe 회귀 | 264개 PASS(이 중 당시 새17개 포함); 최종 경계 보완은 새18개 실행으로 따로 검증 |
| 계약 모듈 | 13개 PASS |
| 언어 간 검산 | Kotlin 코어 생성 PAIR_G/WAIT200 두 원시 fixture를 host가 독립 검산 PASS, 각128요청; 임의 소프트웨어 duration이며 실측/예측이 아님 |
| 등록 구조 | 64세션·26bank·예정8832요청, 각4runtime 총256spec, ID/순서/input/tensor/source SHA 보존 PASS; 과거 target/UUID 재사용0 |
| APK 정적 검사 | 최종 assemble PASS, signature v2 PASS, 정확 package 및 새 entry/rollback 구현 DEX 확인, assets0/모델 binary0 |
| 로컬 사전점검 | 19개 역할의 파일 SHA·APK/서명 결합 PASS; 상태 PC_ARTIFACTS_CHECKED_DEVICE_UNVERIFIED, 실제 측정 준비 판정 false |

초기 실패를 보존했다. 01은 AGP9 built-in Kotlin의 소스 경로 등록 오류로 compile 실패였다. 공식 [이행 문서](https://developer.android.com/build/migrate-to-built-in-kotlin)에 따라 새 sourceSet을 Kotlin으로 연결했다. 02/03의 다섯 회귀 실패는 새 no-model APK에서 기존 MobileNet asset을 찾던 검사였고, 원 modelProbe 회귀264개를 별도로 실행해 모두 통과시켰다. 05는 최종 새18개와 APK 빌드가 통과했다. Python 첫 실패는 Windows checkout의 CRLF가 canonical bytes에 추가된 문제였고 원 Git blob bytes와 `.gitattributes`를 복원해 통과시켰다. 사진/모델/시간·열/에너지 계수·기한·판정 기준을 조정하지 않았다.

## 준비 파일과 정확 SHA

10월15일 제어기 검토에서 별도 프로세스를 놓치는 PID 검사와 summary만으로 조기 COMPLETE를 쓰는 오류를 수정했다. 정상 summary와 `DRAINED`/실제 worker 반환 확인을 기다리고 회수본을 재검산한다. 실패·timeout·회수본 불일치는 FAIL과 부분 원자료를 보존한다. 새23개 fake-client 검사를 포함한 제어기41개가 통과했다. APK 소스·바이트는 바꾸지 않았으며 재빌드하지 않았다. cleanup 기록 이후 수행되는 최종 journal `fd.sync/close`는 host가 별도로 관측하지 않는 한계가 남는다. PC PASS를 원장 최종 내구성의 실기기 증거로 해석하지 않는다.

- 최종 APK: `benchmark-runner/build/outputs/apk/a24Preparation/benchmark-runner-a24Preparation.apk`, **89,814,573bytes**.
- APK SHA-256: `32c42c32fb4ada08a811c82ee867875bd848fa6989f4cba13339c40d9568e9ef`.
- signer certificate SHA-256: `35ce1c7ca713d9c541df7381cfd7212f3bf79cc9b6bf55d08f7ed2716b0e18f3`(Android debug certificate; 서명 정적 검증이며 설치·기기 인증 아님).
- 최종 미소비 계획: `output/a24_laptop_prep_20261014/plan_v3/plan.json`, SHA-256 `82d5108db8d44fc6785cbdc99f71baee01361e21abdd4c59df9544826cb93855`.
- 최종64manifest: `output/a24_laptop_prep_20261014/bound_v2/session_manifests/`; `execution_authorized=false`, `mock=false`, `DEVICE_UNVERIFIED`.
- 원물 private copy6개는 `bound_v1/approved_inputs/` 한 곳을 재사용한다. 모델·labels·anchors·승인 PNG 및 tensor SHA는 [MATERIALS_AUDIT.md](MATERIALS_AUDIT.md)/[MATERIALS_BINDING.json](MATERIALS_BINDING.json)에 있다. 원 PNG는1개이며 이미지 순열 효과/held-out image 검증은 아니다.
- nominal 원 프로필 `5682082a…872db2`의 5phase 평균을 cell별 같은 표본수 context에서 평균·1µs 반올림하여 PLAN의165.216/304.829/621.737ms와 일치함을 검산했다. M128 Δ는2.032194초다. 최신 열·에너지 예측을 새로 동결한 것이 아니다.
- 개인 경로/기기 placeholder/현재 APK/input bindings는 `.local/a24-laptop.paths.json`, `.local/a24-laptop.preflight.json`, ignored output에 있다. source/환경/APK 공유 metadata만 공개 가능하다.

[PC 및 미래 명령](COMMANDS.md), [실기기 체크리스트](DEVICE_CHECKLIST.md)를 따른다. 과거 v1/v2 계획과 bound_v1을 덮어쓰지 않고 미소비 준비 초안으로 보존했다. 활성 실측 registry/device_runs 폴더는 생성하지 않았다.

## 아직 완료가 아닌 것

원물의 metadata/tensor를 검산한 기존 별도 환경과 수집용 표준 라이브러리 환경을 구분한다. [원물 감사 의존성/SHA](MATERIAL_AUDIT_DEPENDENCIES.json)를 기록했으며 수집 host에 외부 패키지를 추가 설치하지 않았다.

기기 접속/설치·실제 full delegation·품질·lane/병행/WAIT·센서 단위/부호/갱신·AP 채널·USB/방전·초기 Tref/AP gate·Perfetto 지원은 DEVICE_UNVERIFIED다. AP는 앱에서 null/host HAL required이며 배터리 온도로 대체하지 않는다. 동결되지 않은 Tref·센서 gap·polling·수치 정확도 허용치와 미래 허가 파일을 임의로 채우지 않았다.

데스크톱의 `ec8a1424` 참고 자료73개·GEN002 소스59개·프로필8개를 인수하고 바이트/SHA를 검산했다. [인수 기록](DESKTOP_REFERENCE_INTAKE.md)을 참조한다. 기존 참고 모형이 새 strict8군·고정 WAIT200·readback·초기 상태를 직접 지원하는 것은 아니다. [분석 계약 초안](ANALYSIS_CONTRACT_DRAFT.md)에 전체 분모·관측창·다섯 대응 비교를 정리했으며 `frozen=false`다. 동일8군 사전 수치 예측·최종 분석 코드/계약·계측/초기 gate는 아직 필요하다. [남은 자료](DESKTOP_REQUIRED.md)를 따른다. 이 자료와 실제 I/F/DEV를 동결하기 전 CONFIRM40은 제어기에서 거절한다.

사용자가 전달한 EP813 보존·EP814 정확 복구 불가·미저장 실행 자동 재수집 금지는 유지했다. 노트북이 데스크톱 checkpoint를 독립 검증하거나 학습을 재시작한 사실은 없다.

빌드 뒤 C 드라이브 여유는 약1.3GB로 줄었다. 원자료를 자동 삭제하지 않았다. 실제 수집 전에 세션/trace/원자료/회수의 공간 상한을 산정하고 출력 드라이브 확보 또는 보존 자료의 별도 관리로 여유를 마련해야 한다.

**PC 준비 완료 ≠ 실기기 검증 완료. 여기서 중지하며 실제 측정 시작은 별도 지시 이후다.**
