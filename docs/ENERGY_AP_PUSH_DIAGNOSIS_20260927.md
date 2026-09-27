# ENERGY-AP-PUSH-DIAGNOSIS-01 — 두 120초 push timeout의 증거 경계

**판정:** 후보 APK의 두 과거 push는 모두 *client가 120초에 반환하지 않아 중단*됐다. 당시 원격 바이트 증가, 정지 시점, 원격 완료 여부를 기록하지 않아 세 경우를 구분할 수 없다. 2026-09-27 새 읽기 전용 조회에서는 **두 정확한 원격 경로 모두 파일 부재**였다. 이는 현재 재전송 없는 원격 파일 설치 경로가 없다는 뜻이지, 과거 전송량 0바이트의 증거는 아니다. 이전 COLLECT-03 및 배포 복구는 모두 `stopped_no_resume`로 유지한다.

## 확인한 명령과 host 경계

| 항목 | COLLECT-03 | DEPLOY-RECOVERY-01 |
|---|---|---|
| 원본 | 외부 `energy_ap_state_run_v3/host_commands/0020/client/result.json` | 외부 `energy_ap_deploy_recovery_run_v1/commands/015/result.json` |
| 시작 UTC | 2026-09-27 12:46:38.554528 | 2026-09-27 13:24:06.282719 |
| 실행 | 동일 pinned `C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe -s <당시 A24 무선 transport> push <동일 후보 APK> <아래 원격 경로>` | 동일 |
| 원격 경로 | `/data/local/tmp/d1check-energy-ap-state-collect-03.apk` | `/data/local/tmp/d1check-energy-ap-deploy-recovery-01/candidate.apk` |
| 결과 | timeout 120.000초, stdout/stderr 각 0 byte, client root reaped | timeout 120.032초, stdout/stderr 각 0 byte, client root reaped |

- 후보 APK는 **106,092,116 byte**, SHA-256 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`; 현재 로컬 파일 읽기와 해시 검사를 통과했다. pinned ADB는 1.0.41 / platform-tools **37.0.1-15733141**이다. 같은 무선 transport를 사용했지만 원격 경로는 달랐다.
- 복구 시 기존 설치본 host pull은 **106,059,328 byte / 85.032초**에 반환됐다. 전송 방향·경로·APK가 달라 이 속도를 후보 push의 속도로 치환하지 않는다.
- `tools/d1_recorded_process.py`는 stdout/stderr를 실행 중 파일로 직접 넘긴다. 파이프를 읽지 못해 가득 차는 host 교착 경로는 해당 호출에 없다. timeout에는 시작한 client root만 종료하며 공유 ADB daemon은 종료하지 않는다. 출력이 비어 있어도 원격 전송 0바이트나 무선 단절을 증명하지 않는다. [AOSP adb push 옵션](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/client/commandline.cpp)에 `-q`는 진행 출력 억제용이고 별도 `-p` 진행 강제 옵션은 없다. [AOSP line printer](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/android15-qpr2-s8-release/client/line_printer.cpp)는 smart terminal이 아닌 stderr에서 진행 줄을 끝까지 보류할 수 있다. 이는 설치 바이너리 내부를 직접 계측한 결과가 아니라 0-byte 출력의 한 설명이다.
- 보존 로그에 명시적 host 보안 프로그램/파일 접근 오류 또는 같은 시간의 별도 전송은 없다. 기록 부재로 다른 host 부하나 무선 품질 문제를 배제할 수 없다. 현재 관련 `adb.exe` client 잔존 증거도 확인되지 않았다. GPU·앱 추론은 시작되지 않았으므로 이 timeout을 그 결함으로 귀속하지 않는다.

## 새 읽기 전용 원격 조회

실행 전 `energy_ap_push_readonly_plan_v1/diagnosis_plan.json`에 최대 **9 ADB 명령/300초**를 고정했다. `devices -l`, A24 model/fingerprint/hardware serial, 두 정확한 경로의 `stat -c %s:%Y`, `df -k /data/local/tmp`, 크기가 후보와 같을 때만 각 경로의 `sha256sum`이다. 일반 조회는 명령당 5초, 조건부 101MiB 원격 SHA는 각 120초, 행정 예약 25초이다. 원격 SHA는 큰 파일 전체를 읽기 때문에 짧은 일반 조회 timeout을 전용하지 않았다.

한 번의 승인된 읽기 전용 실행에서 현재 단일 무선 A24와 고정 model/fingerprint/hardware serial을 확인했고, **7/9 명령, 0.891초**를 소비했다. 두 `stat`은 모두 `No such file or directory`를 반환했고 SHA 호출은 0회였다. `/data/local/tmp`가 속한 파일시스템의 가용량은 조회 출력상 **86,623,744 1K-blocks**였다. 원본: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_readonly_run_v1\receipt.json` 및 `commands/00`–`06`; 계획 SHA-256 `a351724e9b9ed94f7b8b6a802fe3c0aa1b5ad3158e3b9ea5be224d1add55bf74`. 현재 파일 부재와 여유 공간은 과거 timeout 순간의 원격 상태·속도·정지 원인을 확정하지 못한다. 다른 작업에 의한 파일 변화도 배제하지 못한다.

읽기 전용 실행 후 공유 코드의 **계획 생성부만** 바꿔 고유 기기 확인값을 공개 소스에 두지 않고 기존 외부 계획에서 읽게 했다. 실행된 원본 계획·receipt와 조회 함수·원격 결과는 그대로 보존했다. 후속 계획에는 읽기 전용 계획·receipt 및 관련 코드 해시를 묶었다.

## 별도 후속 후보 하나 — 실행 미승인

현재 두 원격 파일이 없으므로 해시 재확인→설치만으로 복구하는 경로는 성립하지 않는다. 후속 후보 `ENERGY-AP-PUSH-OBSERVE-01`은 **새 원격 경로**에 후보 APK를 한 번만 push하고, 같은 경로의 크기를 push 시작 후 20초 간격으로 최대 8회 조회한다. client 종료 후 마지막 크기와, 완전한 후보 크기일 때만 SHA-256을 검사한다. 크기가 증가하면 그 시점의 원격 크기 증가가 확인된다. 크기 정체는 그 구간에서 관측된 plateau일 뿐 내부 전송 정지의 확증은 아니다. SHA가 일치하면 *현재* 원격 전체 파일을 확인한 것이며, 과거 두 실패의 완료 시점을 소급 판정하지 않는다.

| 미래 계획 상한 | 값 |
|---|---:|
| A24 식별·원격 대상 부재·공간 preflight | 최대 6명령, 각 5초 |
| APK push | **1회**, client timeout 180초 |
| push 중 동일 경로 크기 조회 | 최대 8회, 20초 간격, 각 3초 |
| 마지막 크기 / 조건부 SHA | 각각 최대 1회, 5초 / 120초 |
| ADB 전체 | **최대 17명령**(push 포함), pull 0, install 0, 추론 0 |
| 전체 벽시계 / 재시도·대체 | **420초 / 0회** |

180초는 앞선 120초 실패를 성공으로 만들기 위한 timeout 변경이 아니다. 120초 뒤 3개의 20초 관측점을 더 확보하는 *새 진단 상한*이다. 6개 preflight의 timeout·client 정리 예약, push client 180초와 정리, push 후 stat 및 원격 SHA 120초와 정리, 25초 회수 예약을 분리해 전체 420초 안에 둔다. 원격 `stat`도 ADB daemon과 기기 I/O를 공유해 push를 교란할 수 있고, 파일 갱신이 지연·임시 경로를 거치면 진행 중에도 크기 변화를 못 볼 수 있다. 따라서 이 진단 자료는 전송 원인과 속도를 완전히 식별하는 시험이 아니다. 전송 성공은 최종 SHA 일치 전까지 인정하지 않는다. 새 출력에는 단계별 result·부분 stdout/stderr·크기/시각·client 종료 및 root 회수 상태를 남긴다. 공유 daemon, 원격 파일을 삭제·변경하는 cleanup은 하지 않는다.

외부 준비 계획: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_plan_v1\diagnosis_plan.json`, SHA-256 `423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a`, 상태 **`PC_READY_NOT_APPROVED_DEVICE_UNVERIFIED`**. 예상 출력은 형제 폴더 `energy_ap_push_observed_run_v1`이며 현재 존재하지 않는다. 미래 실행 직전에는 현재 A24·후보 APK·ADB·원본 receipt·소스 해시·새 원격 경로 부재·공간을 다시 검사한다. 이전 조회가 현재 상태를 대신하지 않는다. 배포 뒤 수집은 별도 계획·승인 사항이다.

PC만 하는 검사:

```powershell
$env:D1_APK_PUSH_READONLY_PLAN='C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_readonly_plan_v1\diagnosis_plan.json'
python -m unittest tools.test_d1_apk_push_readonly tools.test_d1_apk_push_observed -v
python -m tools.d1_apk_push_observed check --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_plan_v1\diagnosis_plan.json'
```

**별도 승인 뒤에만** 실행할 명령(이번에는 실행하지 않음):

```powershell
python -m tools.d1_apk_push_observed run --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_plan_v1\diagnosis_plan.json' --expected-sha256 423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a --approved
```

PC 관련 테스트 8건 통과, 별도 미래 계획 `check` 통과. 이 검증은 future push 경로의 코드·예산 경계를 확인한 것이지 기기 전송 성공 증거가 아니다. 이번 작업의 새 push/pull/install/추론은 모두 **0회**이며 기존 `experiment_ready=false`, FAIL·부분 원자료·동결값·종료 계획을 변경하지 않았다.
