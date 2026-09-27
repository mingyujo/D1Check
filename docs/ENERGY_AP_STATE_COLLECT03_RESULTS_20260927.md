# ENERGY-AP-STATE-COLLECT-03 실행 결과 — APK 전송 timeout 중단

**판정: `stopped_no_resume`, 개발·확인 세션 0/6.** 2026-09-27 승인된 plan_v3(SHA-256 `b717df5c51c27f1f8a0f4d08604203b0c89b9d61fd054c96e794bc9537a59f02`)를 한 번 실행했다. `Check`는 통과했고, 기존 기기 0대 착수는 Run·소비가 없었던 별도 [preflight](ENERGY_AP_STATE_COLLECTION_PREFLIGHT_20260927.md)로 보존한다. 이번에는 연결된 A24를 확인했지만 **APK 전송 client의 120초 timeout**으로 원격 해시·설치·세션에 도달하지 못했다. 실패 후 재시도·새 계획 실행은 하지 않았다.

## 실행 전 사실과 경계

- 착수 HEAD `41c243e3c6a145e209056afebf5cd44ecdd917b4`, 작업 브랜치 clean, 원격 일치. plan/manifest/source/APK/프로젝트 서명은 `Check`와 설치 preflight에서 일치했다. 동일 실행 ID의 출력과 소비 registry는 착수 전 없었고, Run이 이를 단일 사용으로 점유했다.
- ADB의 한 transport는 `SM-A245N`, fingerprint `samsung/a24ks/a24:16/BP2A.250605.031.A3/A245NKSS9EZB5:user/release-keys`, 하드웨어 serial은 계획의 A24와 일치했다. 연결 방식은 기존 무선 transport 그대로였고 전환하지 않았다.
- 실행 직전 host gate는 배터리 98%·비충전·29.0°C, thermal 0, 화면 Awake/interactive, 수동 밝기 81·화면 timeout 18,000,000ms를 확인했다. 앱 내부 memory admission·GPU 위임·품질·병행 적격성은 **앱 시작 전 중단**되어 확인되지 않았다.
- 후보 APK SHA-256 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`, 이전 설치본 `86d3fac6504104214fbd4d6b43533a0ec420a051920c2d29ae74ed90c8373e3f`. 패키지·versionCode 1·signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`는 같지만 APK가 달라 계획된 전송·설치가 필요했다. 실패 후 설치본을 다시 조회하지 않았으므로 현재 설치 상태를 새로 확인한 것으로 쓰지 않는다.

## 소비와 시간

| 단계 | 승인 상한 | 실제 시도/완료 | 판정 |
|---|---:|---:|---|
| APK 전송 | 1 | 1/0 | `adb push` 120.000초 timeout; 원격 바이트 수·해시 미확인 |
| 원격 해시·APK 설치·설치본 확인 | 설치 1 | 0/0 | 미시도 |
| 개발·동결·확인 | 3→동결→3 | 0→미실시→0 | 미시도 |
| runtime·staging | 24·6회/42파일 | 0·0 | 미시도 |
| 작업·적격성·warmup·총 추론 | 10,080·24·48·10,152 | 모두 0 | 앱 미시작으로 확인 가능 |
| 전체 실행 | 13,800초 | **235.125초** | 설치 preflight·gate·전송 실패·cleanup 포함, 예산 이내 중단 |

전송 명령은 21:46:38 KST 시작해 21:48:38에 timeout됐다. 부분 stdout/stderr는 각각 0 byte, exit code 기록 1, 시작 client PID 15460, `root_reaped=true`다. 도구가 **시작한 ADB client만** 종료했고 공유 daemon의 process tree는 종료하지 않았다. 5037 server probe는 client 시작 직전 통과했다. 전송이 원격에 일부 남았는지·왜 완료되지 않았는지는 이 기록만으로 확정할 수 없다. 앱을 시작하지 않았으므로 호출 수 0은 session progress 추정이 아니라 launch attempt 0과 세션 미착수에 근거한다.

원본: 외부 [FINAL_RECEIPT.json](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v3/FINAL_RECEIPT.json>), [전송 command result](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v3/host_commands/0020/client/result.json>), [설치 단계 receipt](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v3/installation/installation_receipt.json>), [소비 registry](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_registry/ENERGY-AP-STATE-COLLECT-03/stopped.json>). 위 파일과 stdout/stderr·호스트 snapshot을 수정하지 않았다.

## 회수·cleanup 및 분석 한계

앱 Activity·runtime·추론은 시작하지 않아 앱 자체 cleanup receipt는 없다. 실패 경로는 `am force-stop` 성공, `ps -A`를 통한 앱 프로세스 부재 확인, 종료 thermal status 0을 각각 기록했고 host cleanup은 `completed`다. 원격 APK의 부분 전송 여부와 해시는 **미확인**이며, 실패한 전송을 완료로 세지 않는다. 개발 자료·동결 계수·확인 자료가 없으므로 상태별 전력·AP 계수·예측 오차·그림은 산출할 수 없다. 기존 동결 모형과 `experiment_ready=false`를 유지한다.

읽기 전용 재현:

```powershell
python -c "import json,pathlib; r=pathlib.Path(r'C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_state_run_v3'); print(json.load(open(r/'FINAL_RECEIPT.json'))); print(json.load(open(r/'host_commands/0020/client/result.json')))"
```

**다음 행동 하나:** 이번 `stopped_no_resume`의 전송 실패 원인을 보존된 PC command 기록으로 진단한다. 같은 plan_v3의 재전송·재설치·재실측이나 새 계획 자동 실행은 하지 않는다. 원격 잔여물과 현재 설치본은 향후 별도 실행 전에 확인해야 한다.
