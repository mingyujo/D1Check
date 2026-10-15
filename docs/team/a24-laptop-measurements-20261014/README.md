# 2026-10-15 현재 상태: 기존 실측 중지 / REV02 설계 전용

최신 사용자 지시로 기존 자동 실행·감독·수집을 중지했다. 기존 확인은2정상/1온도사전거절/1사용자중지전준비/36미시도로 보존한다. [개정 폴더](../a24-measurement-revision02-20261015/README.md)에서 설계와 PC 검산만 수행한다. 현재 실제 측정은 승인되지 않았으며 아래 과거 명령·job·자동 감독기를 재실행하지 않는다. 기존 PC 준비 단계의 기기0회 숫자는 그 시점의 이력이다.

# 2026-10-15 실제 A24 작업 진행

PC 준비 종료 뒤 별도 사용자 승인을 받아 실제 작업을 진행하고 있다. [실제 진행·오류·계측 제한](MEASUREMENT_PROGRESS.md)을 먼저 읽는다. [측정 source v7](MEASUREMENT_SOURCE_V7.json)과 [통신 복구 v8](MEASUREMENT_SOURCE_V8.json)은 버전별 실제 코드 바이트다. 아래의 준비 완료·기기 명령0 표기는 당시 PC 준비 경계의 이력이다. 모델·APK·개인 기기 원로그는 공개하지 않는다.

# 2026-10-15 노트북 PC 준비 완료 / DEVICE_UNVERIFIED

새 opt-in 실행기·host 검산/회수/미래 제어기·미소비64세션 계획과 새 APK의 PC 준비를 완료했다. 최종 Python103개·새 JVM18개 PASS, 데스크톱 참고73파일 SHA 검산 완료. 실제 기기 작업·실측 START/claim·세션 소비0. [최종 준비 보고서](PREPARATION_REPORT.md), [PC·미래 명령](COMMANDS.md), [실기기 체크리스트](DEVICE_CHECKLIST.md), [데스크톱 인수 기록](DESKTOP_REFERENCE_INTAKE.md), [미동결 분석 초안](ANALYSIS_CONTRACT_DRAFT.md), [남은 자료](DESKTOP_REQUIRED.md), [정확 원물 SHA](MATERIALS_AUDIT.md)를 먼저 본다. 아래는 최초 계획 전달 상태이며 새 APK 미완성이라는 표기는 당시 상태다.

# A24 실측 — 사용자 노트북에서 진행

최종 PC 준비 소스는 별도 `codex/a24-laptop-prep-20261014` 브랜치에 저장한다. 새 공간에서 받는 명령은 다음과 같다. APK·승인 원물·개인 설정·미소비 로컬 계획은 공개 Git에 포함하지 않으며 [명령/결합 절차](COMMANDS.md)를 따른다.

```powershell
git clone --branch codex/a24-laptop-prep-20261014 --single-branch https://github.com/mingyujo/D1Check.git D1Check-a24-preparation
```

이 아래 최초 전달 안내의 clone 명령은 과거 문서 브랜치이며 최신 준비 소스와 구분한다.

2026-10-14 사용자 지시를 반영했습니다. **실측은 사용자 노트북과 A24에서 진행하며, 이 데스크톱의 GEN002 학습·CAUSAL·NODGPU는 계속 유지합니다.** 현재는 노트북 준비 안내와 측정 계획이며 즉시 실행할 수 있는 APK/수집 패키지는 아닙니다.

- [A24 상세 계획: 최대64세션](PLAN.md)
- [준비 상태와 필요한 패키지](PACKAGE_STATUS.json)
- [S26 담당자 요청](../s26-scheduling-measurements-20261014/README.md)

## 역할과 호스트 차이

노트북은 실행 제어·ADB 통신·시각/원장·로그 회수와 검산을 맡고 추론은 A24에서 합니다. 노트북에서 RL을 학습하거나 데스크톱의 대규모 시뮬레이션 결과 전체를 복사할 필요는 없습니다. 호스트 전송/수집 지연과 실제 요청 도착 시각은 여전히 기록합니다.

현재 로컬 수집 host는 PowerShell/CIM·ADB port 조회에 Windows 의존성이 있습니다. 노트북 OS는 아직 확인하지 않았습니다. Windows 노트북 기준의 경로 이식을 준비하며 macOS/Linux에서 검증됐다고 주장하지 않습니다. 다른 OS는 host 계층 이식·검증이 먼저입니다.

## 지금 받을 수 있는 것

새 폴더에 문서 브랜치만 내려받아 확인할 수 있습니다. 기존 작업 폴더에 덮어쓰지 않습니다.

```powershell
git clone --branch codex/s26-measurement-request-20261014 --single-branch https://github.com/mingyujo/D1Check.git D1Check-measurements
Set-Location -LiteralPath .\D1Check-measurements
```

이 브랜치의 A24 폴더와 S26 폴더는 전달 문서입니다. 브랜치 기본 코드는 오래된 calibration 경로이고, 현재 데스크톱의 최신 modelProbe/host와 동일하지 않습니다. clone 성공을 새 측정 실행기 설치 완료로 해석하지 않습니다.

## 노트북용 실행 패키지에 반드시 들어갈 것

| 항목 | 준비 조건 | 현재 상태 |
| --- | --- | --- |
| 새 opt-in 실행기·host validator | 64/128/252건, strict FIFO/EDD, serial/pair, WAIT·실제AVAILABLE·분모/복구 검산 | 미구현/미게시 |
| 수집 전용 host 의존성 lock | Python/라이브러리·host source·Android platform-tools 버전과 SHA | 새 실행기와 함께 고정 필요 |
| 설치할 APK | 새 source/build/runtime SHA·정밀도·스레드·서명·품질/회귀 확인 | 새 APK 미빌드/미검증 |
| 승인 모델·이미지·tensor | EfficientNet-Lite0/EfficientDet-Lite0 원본·각 labels·anchors.json·승인 이미지·품질 기준·원 URL/bytes/SHA | GitHub에 포함하지 않음 |
| 노트북 local config | repo/input/APK/output/registry/adb의 노트북 절대경로 | 노트북에서 새로 생성 |
| 새 실행 계획·원장 | 세션/요청 UUID·DEV/확인 입력·예산·모든 드라이브 여유·재시도 규칙 | 기기 실행 전 새 등록 필요 |
| 사전점검/수집/회수 명령 | exact 계획 SHA와 하나의 대상 A24에 결합, 원자료 전수 검산 | 실행기 완성 후 제공 |

데스크톱의 atcenv·사용자 절대경로·기존 registry/lock·종료된 session ID를 복사해 재개하지 않습니다. 모델 binary·기기 serial·개인 이미지·원자료는 공개 저장소에 올리지 않습니다. 승인 exact 모델은 실행자가 출처에서 직접 확보하고 SHA를 확인합니다.

## 노트북 준비 순서

1. 노트북 OS와 Git·Python·Android platform-tools/드라이버 사용 가능 여부, 저장공간·전원 설정을 기록합니다. 새 수집 패키지의 의존성 lock을 기준으로 전용 가상환경을 만들고 데스크톱 RL 환경을 통째로 설치하지 않습니다.
2. APK를 직접 빌드하는 경우에만 해당 실행기의 Gradle wrapper·JDK·Android SDK/NDK/CMake 버전을 사용합니다. 현재 로컬 개발판의 버전이 원격 기본 코드에 그대로 맞는다고 가정하지 않습니다. 검증된 APK를 받으면 노트북에 Android 빌드 전체 환경은 필요하지 않지만 기존 host의 APK 검사를 위해 Java·aapt2·apksigner가 필요할 수 있으므로 수집 도구 lock에 포함합니다.
3. 노트북의 전용 input/output/registry 폴더와 새 run ID를 정하고 repo/입력/APK/도구/출력 경로를 local config에 바인딩합니다. 데스크톱 C:/Users 경로가 노트북에도 같다고 가정하지 않습니다.
4. USB 또는 무선ADB 연결 방식을 한 가지로 고정하고 충전 여부·케이블/허브/포트·화면/밝기·통신·SOC·주변온도를 기록합니다. 연결 방식·읽기 부하가 정책별로 달라지지 않게 합니다.
5. 실제 기기 접속 전 순수 fixture/host 검산을 통과시킵니다. 이후 새 기기 등록과 APK/입력 SHA를 고정하고 I4→F4→DEV16→동결→새확인40의64세션 계획을 수행합니다.
6. 시작·실패·사전거절·미완료와 raw를 노트북에 보존하고 블록 완료 후 manifest/SHA와 함께 회수합니다. 끝난 세션을 반복해 성공행으로 바꾸거나 데스크톱과 노트북에서 같은 identity를 동시에 실행하지 않습니다.

## 계측 조건

추론시간과 전체J·AP는 A24에서 수집하며 host 시각과 연결합니다. 노트북 USB의 충전 상태나 포트 조건을 데스크톱과 같다고 가정하지 않습니다. 전류/전압·온도 원표본·읽기 시각·cache 갱신을 기록하고 J0/120/180·AP35/180 경계를 확보합니다. 불완전 창은null이며 저속 gauge 한 점으로 짧은 요청별 에너지를 식별하지 않습니다.

모형 예측·입력·초기 gate·계측/분석은 확인 전에 동결합니다. 노트북으로 옮긴 뒤 새 계측 조건에서 검산하고, 과거 데스크톱/다른 USB 조건의 PASS를 자동 전용하지 않습니다.

현재 이 폴더를 받은 것만으로 폰을 연결·설치·실측하라는 뜻은 아닙니다. 남은 실행기/APK/입력 패키지를 이 체크리스트에 맞춰 완성해야 합니다.
