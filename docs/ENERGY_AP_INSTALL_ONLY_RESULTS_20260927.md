# ENERGY-AP-INSTALL-ONLY-01 결과 — 설치 전 host 오류로 종료

**결과: 설치 미실시, `stopped_no_resume`.** [관측용 push](ENERGY_AP_PUSH_OBSERVE_RESULTS_20260927.md)에서 완전성이 확인된 원격 APK를 재전송 없이 설치하도록 새 ID의 설치 전용 계획을 만들었으나, 첫 기기 목록 조회의 host 프로세스 생성 전 오류로 중단됐다. 원격 파일의 *현재* SHA, 현재 설치본, 환경 gate는 이번 실행에서 확인되지 않았다. 이전 원격 SHA는 설치 직전의 확인값으로 대체하지 않는다.

## 준비한 설치 계약과 PC 확인

- 외부 계획 `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_install_only_plan_v1\install_plan.json`, SHA-256 `f76c4ef3e44bc256944650330ca0e8f4297071a6dac1d99a923de4a838139fba`; 새 출력/registry ID `ENERGY-AP-INSTALL-ONLY-01`. 기존 COLLECT-03·종료된 배포 복구 계획을 호출하지 않았다.
- 후보 SHA `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`, 원격 `/data/local/tmp/d1check-energy-ap-push-observe-01.apk`, 기존 `apk_preflight`의 package/versionCode/프로젝트 signer와 설치본 pull·비교, `pm install -r`, 최종 `pm path`·설치본 SHA 경계를 재사용했다. **설치본 SHA가 후보 APK와 같을 때에만** 패키지·버전·서명도 같은 후보 바이너리라고 판정한다.
- 계획 상한: 전체 **600초**; 기존 설치본 host pull 최대1/180초, push0, 원격 SHA 최대120초, 설치 최대1/120초, 재시도0, 앱 실행·warmup·추론0. 단계 예약은 preflight220·원격 SHA120·설치125·사후 확인60·cleanup45·예비20초(합590초, 전체600초 이내). A24 model/fingerprint/hardware serial, 앱 미실행, 비충전·배터리20% 이상·35°C 이하·thermal0, 기존 화면 계약을 gate로 연결했다. `Check`, PowerShell `-Action Check`, 관련 PC 테스트 4건은 **실행 전** 통과했다.

## 실제 중단 경계

| 항목 | 실제 |
|---|---|
| Run | 2026-09-27 14:33:11.134763~11.152212 UTC, **0.016초** |
| claim/registry | 새 설치 전용 claim 생성, `stopped.json` 기록. 같은 계획 재실행 금지 |
| 첫 조회 | 기록 래퍼의 `commands/000`에서 `adb devices -l` 시도. `host_command_error`, `TypeError`, `spawn_return_monotonic`/PID 없음 |
| 실제 ADB client/기기 명령 | **0회** — `subprocess.Popen` 인수에 아직 선택되지 않은 serial `None`이 들어가 프로세스 생성 전 실패. receipt의 `adb_commands_used=1`은 래퍼의 *시도 슬롯* 수이지 실제 기기 명령 수가 아님 |
| 기존 설치본 pull / 원격 SHA / 설치 / 사후 설치본 조회 | **모두 0회** |
| push / 앱 실행 / warmup / 추론 / 재시도 | **모두 0회** |
| cleanup | 기기 동일성 확인 전 중단돼 앱 cleanup `not_attempted_unidentified_device`; 시작한 ADB client가 없어 종료 대상 없음. 공유 daemon/기기 설정을 변경하지 않음 |

원본 `commands/000/result.json`에는 `stop_reason=TypeError`, `status=host_command_error`, stdout/stderr 각0바이트가 기록됐다. 이는 무선 연결 실패나 APK·설치 실패의 증거가 아니다. 새 실행기의 초기 `RecordedDevice.call`이 serial 미선택 상태에서도 `-s None`을 전달하는 코드 결함이 직접 확인된다. 이 결함은 기존 배포기의 *선택된 serial을 받는 경로*와 새 설치 전용 경로의 차이에서 생겼다.

실행 후 새 설치 전용 코드의 **첫 `devices -l`만 `-s` 없이 기록**하고, 선택된 transport 이후에는 기존 래퍼를 사용하도록 수정했다. 실제 그 경계를 통과하는 PC fixture, push/중복 설치 차단, 원격 SHA 경로 검증, 실패 보존을 포함한 **관련 테스트 5건 통과**. 이 수정은 소비된 계획의 소스 해시를 바꾸므로 이번 ID를 수정 후 재실행하지 않았다. PC 통과는 현재 무선 A24·설치 안정성의 검증이 아니다.

PC 검증 기록: 2026-09-27 23:37 KST, 시작 HEAD `e80e143225ee9854c3dc75a793e30127a7784ad0`에 이번 4개 파일의 미커밋 변경이 있는 상태. `D1_INSTALL_ONLY_PLAN`을 위 소비 계획으로 지정하고 `python -m unittest tools.test_d1_energy_ap_install_only -v` 실행: **5건 통과, 건너뜀 0**. `python -m py_compile tools/d1_energy_ap_install_only.py tools/test_d1_energy_ap_install_only.py` 통과. 소비 계획을 `Check`로 재승인하지 못하도록 막는 경계도 테스트했으며 기기 명령은 없었다.

외부 원본: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_install_only_run_v1\receipt.json` (SHA-256 `fe9b7708d184d7fcba67907e5eddbb3f37eb3f8a682e37d365588953ff2801e3`), `claim.json`, `commands/000/{start,result}.json`, 별도 `energy_ap_install_only_registry/ENERGY-AP-INSTALL-ONLY-01/{claim,stopped}.json`. 고유 transport·기기 자료와 APK/키/모델은 Git에 넣지 않았다.

**다음 행동 하나:** 수정된 초기 transport 경계를 묶은 **새 설치 전용 계획**을 별도 ID·출력으로 PC 검증하고 승인받아야 한다. 실행 시에는 현재 동일 A24·환경과 원격 SHA를 새로 확인하고, 동일 설치본이면 생략한다. 이번 승인의 재시도·대체·추가 설치0을 우회해 자동 실행하지 않는다. 기존 종료 계획·FAIL·원자료·동결값·`experiment_ready=false`는 유지한다.
