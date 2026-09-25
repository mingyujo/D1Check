# ENERGY-DESIGN-REVIEW-PC-01 검증 기록

[종합 보고서](../../ENERGY_DESIGN_REVIEW_20260926.md), [작은 식별·결과 요약](summary.json). 시작 HEAD3773f26, 검증 시 관련 수정 미커밋. 최종 commit은 Git 이력을 따른다. 다른 worktree/원본 변경·ADB·설치·실측0.

- Python40건(운영/회계14 + 관련 기존collection26) 통과. 고정 노출 경계·invalid/gap·기술 gate 순서·개발2 뒤 동결·역순 확인·실패회수·분모·비중복 적분/미측정 끝점 검사.
- Kotlin `EnergyCollectionCoreTest`7건 통과(실제 Activity가 사용하는 동일 probe 순서와 구버전 호환 포함). 새 APK compile/build 통과. GPU/native/부하 안정성의 기기검증은 아님.
- 실제 원본5시도 HAL1064샘플을 기존 parser로 재생. 완료3세션의 원래 equal_work/common_window 에너지와 재생 일치. 나머지2시도는 prefix로 보존, 완료 처리하지 않음.
- 새 project-signed APK SHA `86d3fac6504104214fbd4d6b43533a0ec420a051920c2d29ae74ed90c8373e3f`; signer `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`.
- `energy_operational_plan_v3/collection_plan.json` SHA `4d0bd250029f8fb46c7f989775f63cf75714c4e681522a6c056e58ef0f900ed5`. 실행 스크립트 `-Action Check`는 `PC_READY_DEVICE_UNVERIFIED` 반환, 기기 명령0. run/registry 미생성·미승인, source/manifest/input/APK/서명 hash 연결.

외부 자료는 모두 `C:/Users/LG/Documents/D1Check_Arrival_Extension` 아래에 있으며 GitHub에는 없다:

- `energy_design_review_pc_v1/review.json`, `VERIFICATION_final.json`, `kotlin_test.log`: 이번 집중 분석/검증
- `energy_operational_build_v1/build_receipt.json`, `build.log`: 격리 새빌드
- `energy_operational_plan_v3/collection_plan.json`, `manifests/`, `RUN_AFTER_APPROVAL.ps1`: 미실행 후보
- `energy_collection_run_v4`, `energy_collection_run_v5`, `energy_sampler_load_run_v1`: 보존 원본/receipt

재현:

```powershell
python -B -m unittest tools.test_d1_energy_operational tools.test_d1_energy_collection
python -B -m tools.d1_energy_replan_review --root C:/Users/LG/Documents/D1Check_Arrival_Extension --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_design_review_REPRO_NEW
$env:ANDROID_HOME='C:/Users/LG/AppData/Local/Android/Sdk'
$env:ANDROID_USER_HOME='C:/Users/LG/AndroidStudioProjects/D1Check-model02b/.android-user'
$env:D1_TIMING_BUILD_ROOT='C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_build_v1/build'
./gradlew.bat --no-configuration-cache --init-script tools/arrival_timing_isolated_build.gradle :benchmark-runner:testModelProbeUnitTest --tests '*EnergyCollectionCoreTest' -PenableModelProbe=true --console=plain
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
```

새 폴더 재패키징은 `python -B -m tools.d1_arrival_timing_calibration package --output <새build폴더>`이며 실제 준비 명령은 아래다. **소비된 옛 계획 실행 명령이 아니다.** source는 계보/입력 템플릿으로만 읽고 `--operational`이 새4세션을 생성한다. 출력 폴더는 새 경로여야 한다.

```powershell
python -B -m tools.d1_energy_collection prepare --operational --source C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v9/collection_plan.json --build C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_build_v1/build_receipt.json --references C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v5 --output <새plan폴더>
```

조건부 mA 해석, 새 운영 질문의 AP matching N/A, 시작 상태/순서와 개발·확인 block의 교란은 보고서에 명시했다. PC 준비가 같은 초기 열 상태/에너지 절감/실험 READY를 뜻하지 않는다.

미실행 PC 중간 산출물 plan_v1은 서비스 P95 회계 추가 전, plan_v2는 앱 시작20초 예약 명시 전이다. 모두 보존하되 현 source Check 불일치로 실행할 수 없다. 최종 후보는 **plan_v3만**이다. APK 코드는 변하지 않아 재빌드하지 않았다. 전체 상한144분은 같고, 중간 설명의 timeout 합산 예약140분20초를 앱 시작4×20초를 포함한141분40초로 바로잡았다.
