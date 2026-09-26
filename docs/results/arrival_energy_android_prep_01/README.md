# ARRIVAL-ENERGY-SYNTHETIC-COLLECT-01 PC 준비·검증 기록

2026-09-26 KST, 검증 출발 HEAD `36632fadf67f52791d8681e18027927ba05f0011`, 이번 관련 파일 미커밋 상태. [실행·해석 계약](../../ARRIVAL_ENERGY_ANDROID_PREP_20260926.md). ADB·설치·앱 실행·추론 0, 새 output/소비 registry 미생성. 기존 실측·960 PC 배치·전체 빌드 재실행 없음.

## 로컬 전용 후보

| 항목 | 경로·식별자 |
|---|---|
| 프로젝트 서명 APK/build receipt | `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_synthetic_build_v2/build_receipt.json` |
| APK SHA-256 | `1f2bec87adc9bfcb2824e58aa49f20dbae68bd7ce185b22411f96facbe25b659` |
| 프로젝트 signer 인증서 SHA-256 | `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` (키·비밀번호 미공유) |
| 실행 후보 계획 | `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_collection_plan_v4/collection_plan.json` |
| 계획 SHA-256 | `64b2a9a8461f4815aedcc0599ad38766c2fde698bdb8e23c52500195897f2dc0` |
| manifest/스크립트 | 같은 폴더 `manifests/` 12개, `RUN_AFTER_APPROVAL.ps1` |
| 계획 전용 output/registry | `arrival_energy_synthetic_run_v1` / `arrival_energy_synthetic_registry/ARRIVAL-ENERGY-SYNTHETIC-COLLECT-01`, **둘 다 아직 없음** |

초기 v1~v3 계획 초안은 host 정체성 검사·요약 출력 보완 전에 생성되어 현재 `Check`를 통과하지 않는다. 덮어쓰지 않았고 **v4만 실행 후보**다. 새 APK는 프로젝트 서명으로 PC 검증했으나 현재 A24 설치본·runtime/native/센서 적격성은 조회하지 않았다.

## PC 재현 명령

저장소 루트에서 PowerShell:

```powershell
python -B -m unittest tools.tests.test_arrival_energy_collection -v
$env:ANDROID_HOME='C:/Users/LG/AppData/Local/Android/Sdk'
$env:ANDROID_USER_HOME='C:/Users/LG/AndroidStudioProjects/D1Check-model02b/.android-user'
$env:D1_TIMING_BUILD_ROOT='C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_synthetic_build_v1/build'
./gradlew.bat --no-configuration-cache --init-script tools/arrival_timing_isolated_build.gradle :benchmark-runner:testModelProbeUnitTest --tests '*ArrivalEnergyContractTest' --tests '*EnergyObservedStateTest' -PenableModelProbe=true --console=plain
python -B -m tools.d1_arrival_energy_collection check --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_collection_plan_v4/collection_plan.json'
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_collection_plan_v4/RUN_AFTER_APPROVAL.ps1' -Action Check
```

APK 재생성은 이번에 완료했으며 재생성 명령은 `python -B -m tools.d1_arrival_timing_calibration package --output <새 빈 build 폴더>`다. 현재 후보와 같다고 자동 간주하지 않는다. PC 결과: 관련 Kotlin unit 통과, Python 단위/경계/overlap 3건 통과, package/서명 검사·12 manifest/입력 해시·정확한 예산·`Check`/PowerShell dry-run 통과, `device_commands=0`. 기존 스냅샷 경로에 waiting count를 설정하지 않으면 기존 필드가 그대로인 것도 확인했다. 테스트는 정책 의미와 회계 경계 검증이며 실기기 안정성·전력 단위·발열 예측 검증은 아니다.

별도 실행 승인이 생겨 **그 시점의 A24 serial·환경/설치본 gate가 충족될 때만** 아래 명령을 단일 사용한다. 이번 작업에서 이 명령은 실행하지 않았다. 승인 예산은 계약의 12세션·384 명시적 추론·177분 hard 상한과 같아야 한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_collection_plan_v4/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 확인한 A24 transport serial>' -ExpectedPlanSha256 '64b2a9a8461f4815aedcc0599ad38766c2fde698bdb8e23c52500195897f2dc0'
```

완료/부분 원본을 회수한 뒤에만 `python -B -m tools.d1_arrival_energy_analysis --run C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_energy_synthetic_run_v1 --output <새 분석 폴더>`를 사용할 수 있다. 이 도구는 `session_metrics.json`, `session_windows.csv`, `pair_differences.csv`를 write-once로 만든다. 기기 전체 전류 `mA` 해석은 조건부이고 불완전 coverage는 `null`; request별 에너지·CPU/GPU 직접 전력·병행 인과효과·우월성 PASS는 만들지 않는다. 원본·APK·모델·키는 Git에 포함하지 않는다.
