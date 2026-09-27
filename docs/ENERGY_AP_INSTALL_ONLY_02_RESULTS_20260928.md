# ENERGY-AP-INSTALL-ONLY-02 — 원격 APK 재사용 설치 결과

**설치 완료·검증됨.** 새 설치 전용 계획을 한 번 실행했다. 이전 `ENERGY-AP-INSTALL-ONLY-01`의 실패·소비 기록과 [중단 보고서](ENERGY_AP_INSTALL_ONLY_RESULTS_20260927.md)는 보존했다. 에너지·AP 상태 수집, 앱 실행, warmup, 추론은 하지 않았다.

## 동결·PC 검증

- 외부 계획 `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_install_only_plan_v2\install_plan.json`, ID `ENERGY-AP-INSTALL-ONLY-02`, SHA-256 `1176c4d94aa263feddcf9e4690a1ead79cd3c30e34cd3c61327a5840704e761b`. 수정된 `tools/d1_energy_ap_install_only.py` SHA-256 `d4948929438ad4e86085ce9a8c06655c670106f9e2fb22e0e7171418c7733000`와 후보 APK·기존 관측 receipt·실행 보조 코드·서명 검사 도구 해시를 고정했다. 기존 `apk.preflight`·`installed_hash`·기록형 host 명령을 재사용했다.
- 2026-09-28 00:40~00:41 KST, 시작 HEAD `b0bc5b8ba79bbc21d6a3a8face74d0edd8b3f7c1`, 이번 도구·테스트 미커밋 변경에서 `RUN_AFTER_APPROVAL.ps1 -Action Check` 통과(기기 명령 0). `D1_INSTALL_ONLY_PLAN`을 새 계획으로 둔 `python -m unittest tools.test_d1_energy_ap_install_only -v`는 6/6 통과. 실제 `run → preflight → identify → 명령 생성`을 지나는 PC fixture에서 첫 `adb devices -l`은 serial 없이, 이후 명령은 선택 transport의 `-s`로 고정되는 것을 확인했다. 이 PC fixture는 실기기 안정성의 증거가 아니다.
- 계획 상한: 전체 600초, ADB 최대22명령, 기존 설치본 host pull 최대1회, 설치 최대1회/120초, push·재시도·대체·추가 설치·앱 실행·warmup·추론 0회. 새 출력 `energy_ap_install_only_run_v2`, 별도 registry `energy_ap_install_only_registry/ENERGY-AP-INSTALL-ONLY-02`.

## 실제 실행과 동일성

| 경계 | 확인 결과 |
|---|---|
| 현재 기기·환경 | `devices -l`로 유일한 온라인 transport를 선택한 뒤 모델 `SM-A245N`, 동결 fingerprint와 hardware serial 일치. 앱 프로세스 부재, 비충전, 배터리 86%, 배터리 온도 28.2°C, thermal 0, Awake/interactive, 밝기 81·수동 모드 0·화면 timeout 18,000,000ms 통과 |
| 프로젝트 서명·기존 설치본 | 후보 package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1, signer SHA-256 `b253dbb9…cc7565`. 기존 base APK를 host pull 1회(18.578초)하여 같은 package/version/signer를 확인. 기존 APK SHA `86d3fac6…37e3f`로 후보와 달라 설치 생략 대상이 아님 |
| 원격 APK | 설치 직전 `/data/local/tmp/d1check-energy-ap-push-observe-01.apk`의 SHA-256을 새로 조회해 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf` 일치 |
| 설치 | `pm install -r` 1회, 23.078초, exit 0 및 `Success`. 앱 삭제·데이터 초기화·재전송 없음 |
| 설치 후 | `pm path`의 단일 base APK SHA-256이 위 후보·원격과 일치. 후보의 package/version/signer는 로컬 APK 검사로 고정됨 |
| 종료 | 앱 미실행이므로 앱 cleanup은 `not_applicable_no_app_launch`. 종료 시 앱 프로세스 부재·thermal 0 확인, host 명령은 각각 반환·정리됨. registry `complete.json` |

실제 ADB 명령 **19/22회**, host pull **1/1**, push **0**, 설치 **1/1**, 앱 실행·warmup·추론·실측 **0회**. 전체 **45.687/600초**. 모든 기록형 명령이 exit 0으로 반환했다. APK 전송량은 이번에 0이며 기존 검증된 원격 파일을 읽었다. 설치 완료는 GPU·센서·병행 안정성이나 에너지·AP 모형의 적격성 검증이 아니다.

원본: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_install_only_run_v2\receipt.json` (SHA-256 `cc09e2fa7542ee4e933c7eaaf977e54018b0654ac7556c7443f2700f13e2c34f`), `commands/000`~`018`, `preflight/preflight.json`, `screen_observations`, 외부 registry의 `claim.json`·`complete.json`. 원본에는 기기 식별 정보와 기존 설치본 APK가 있어 Git에 넣지 않는다. 이번 문서와 도구·테스트만 공유한다.

**다음 경계:** 설치 성공으로 종료된 `ENERGY-AP-STATE-COLLECT-03`을 재개할 수 없다. 에너지·AP 상태 수집에는 별도 새 계획·승인과 실행 직전 배터리·비충전·온도·thermal·화면·앱 memory·GPU/병행 적격성 확인이 필요하다. 현재 `experiment_ready=false`, 기존 FAIL·부분 자료·동결값·종료 계획은 그대로다.
