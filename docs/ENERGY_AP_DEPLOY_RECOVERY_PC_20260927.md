# ENERGY-AP-DEPLOY-RECOVERY-01 — APK 전송 중단의 PC 진단과 분리 배포안

**판정:** 2026-09-27 COLLECT-03의 직접 중단 원인은 APK `adb push` client의 120초 timeout이다. 그 안에서 무엇이 지연됐는지, 원격에 몇 byte가 남았는지, 실패 당시 기기 연결이 끊겼는지는 **미확정**이다. 기존 수집은 `stopped_no_resume`이며 배포 성공으로 소급하지 않는다. 이 문서의 새 복구안은 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`; 기기 명령은 실행하지 않았다. `experiment_ready=false`.

## 기록으로 확인한 경계

| 항목 | 확인된 값·의미 |
|---|---|
| 원본 | 외부 `energy_ap_state_run_v3/FINAL_RECEIPT.json`, `host_commands/0020/client/{result.json,stdout.bin,stderr.bin}`, `host_commands/0020/context.json`, `installation/installation_receipt.json` |
| 후보 APK | 106,092,116 byte(101.18 MiB), SHA-256 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`; package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1, signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` |
| 명령 | 고정 SDK `adb.exe -s adb-R59W802RW5F-yZ5QCN._adb-tls-connect._tcp push <후보 APK> /data/local/tmp/d1check-energy-ap-state-collect-03.apk` |
| 시각·종료 | 12:46:38.554528Z 시작, 120.000초 후 timeout; client PID 15460, exit 1, `root_reaped=true`; client만 종료, 공유 daemon tree는 종료하지 않음. descendant 부재는 별도 확인되지 않음 |
| 출력·server | stdout/stderr 각 0 byte. 이는 전송량 0 또는 연결 단절의 증거가 아니다. 직전 localhost:5037 protocol `0029` 확인 통과, 실패 시점 transport·원격 해시 미확인 |
| 소비 | 전송 1회 시도, 원격 해시·설치 0회, 앱·세션·추론 0회. 전체 235.125초. 앱 cleanup 해당 없음; host force-stop·프로세스 부재·thermal 0은 별도 확인됨 |

기존 [`d1_collection_recovery.py`](../tools/d1_collection_recovery.py)는 전송→원격 SHA-256→`pm install -r`→설치본 SHA-256을 단계별로 기록하고 실패 시 부분 출력·시간·PID·cleanup을 보존한다. [`d1_recorded_process.py`](../tools/d1_recorded_process.py)는 명령 stdout/stderr를 파일로 직접 수집한다. 과거 별도 `install_recovery_run_v2`에서는 다른 약 106MB APK의 push 17.094초·설치 23.234초가 관측됐다. 이는 당시 경로의 사례일 뿐 이번 연결의 예상시간이나 무선 원인 판별 근거가 아니다. 이번 복구기는 기존 단계를 재사용하며, timeout 시 **시작한 client만** 종료하고 공유 daemon은 건드리지 않도록 선택했다. APK나 Android 소스는 변경하지 않았다.

## 실행 가능한 별도 배포안 — 현재 미승인

계획: 외부 `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_deploy_recovery_plan_v1\recovery_plan.json`; SHA-256 `8b9fb528ea75139d208b3b458072a6f8787bcd10564f12bd62cd1daf718c17c8`. 새 ID `ENERGY-AP-DEPLOY-RECOVERY-01`, 전용 출력 `energy_ap_deploy_recovery_run_v1`, 전용 소비 registry `energy_ap_deploy_registry/ENERGY-AP-DEPLOY-RECOVERY-01`. 이전 registry와 remote path를 재사용하지 않는다. 이전 plan_v3는 APK·서명·기기 gate를 읽는 **불변 입력**일 뿐, 그 수집 실행기는 호출하지 않는다.

총 상한 **600초(10분)**: 사전 동일성/기기·환경 확인 200초, 후보 전송과 원격 해시 150초, package install과 client 종료 예약 125초, 설치본 재확인 60초, cleanup 45초, 관리 예약 20초. 단계별 예약 합계이며 정상 예상시간이 아니다. preflight에는 **기존 설치본 APK의 host pull 최대1회**가 포함된다. 이 pull도 약 106MB 전송일 수 있으므로 작은 메타데이터 조회로 세지 않는다. plan의 `transfer_cap=1`은 **후보 APK push** 상한이며 pull을 숨겨 합친 수치가 아니다. push timeout 120초와 `pm install` timeout 120초는 유지한다. 후보가 정확히 설치된 경우 후보 push·설치를 모두 생략한다. 후보 push 최대1·설치 최대1·재시도/대체/추가0, 세션·추론0. 조회 실패·timeout·해시/서명/화면/배터리/thermal 불일치 시 중단, 회수·cleanup 후 같은 ID 재실행 금지. 원격 파일이 부분적으로 남아도 기존 경로를 덮지 않는다. 원격 staging 파일은 증거·충돌 방지를 위해 자동 삭제하지 않으며, host cleanup은 앱 force-stop·프로세스 부재·thermal 확인을 별도 기록한다.

승인 후에는 현재 A24 transport serial을 실제로 확인해야 한다. 기존 무선 transport에서 실패했지만 무선 자체의 결함은 입증되지 않았다. 가능한 경우 기존 승인 A24를 USB로 준비하는 것은 **대안**이며, USB 디버깅 연결이 이미 승인됐는지 별도 확인이 필요하다. 어느 연결이든 현시점 fingerprint·hardware serial·설치본·서명·비충전·배터리 20% 이상·BAT 35°C 이하·thermal 0·계약상 화면 상태를 새로 확인한다. 현재 재사용 복구기는 기존 계약의 **비충전 gate를 배포에도 유지**하므로 USB가 충전 상태를 만들면 이 계획에서는 시작할 수 없다. 충전 중 배포만 별도 허용하려면 새 계약·예산·승인이 필요하며 측정 gate와 혼동하지 않는다. 이 배포안은 휴대폰 설정을 바꾸거나 자동 재연결·daemon 재시작을 하지 않는다.

PC 검증과 재현(ADB 호출 없음):

```powershell
python -m unittest tools.test_d1_energy_ap_deploy_recovery tools.test_d1_collection_recovery -v
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_deploy_recovery_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
```

**별도 배포 실행 승인 후에만**, 확인한 실제 transport serial로 다음을 한 번 수행한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_deploy_recovery_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<실제로 확인한 A24 transport serial>'
```

복구 성공 receipt가 후보 APK hash·signer·package/version 및 설치본 hash를 확인하면, **후속 수집은 새로운 ID·plan·manifest·출력·소비 registry와 별도 승인**이 필요하다. 그 계획은 정확히 동일한 설치본일 때 설치/전송 상한 0 경로를 우선하고, 실측 직전 비충전·온도·thermal·화면·memory·GPU/병행 gate를 다시 확인해야 한다. 이번 배포 receipt는 수집의 개발·확인 표본이나 에너지/AP 모형 적격성 자료가 아니다. 기존 FAIL·부분 결과·동결값·종료 계획을 보존한다.
