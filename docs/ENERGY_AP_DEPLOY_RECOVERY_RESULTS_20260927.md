# ENERGY-AP-DEPLOY-RECOVERY-01 결과 — 무선 APK push timeout 중단

**결과: `stopped_no_resume`.** 2026-09-27 승인된 별도 배포 계획 SHA-256 `8b9fb528ea75139d208b3b458072a6f8787bcd10564f12bd62cd1daf718c17c8`을 한 번 실행했다. 후보 APK push가 120.032초 timeout되어 원격 SHA-256과 설치에 도달하지 않았다. 재시도·대체 실행은 없었다. 기존 종료된 `ENERGY-AP-STATE-COLLECT-03`은 재개하지 않았다. `experiment_ready=false`.

## 착수 및 동일성

- 작업 브랜치 착수 HEAD `1714533c74e0c9fc6324a1ecda622e06ecc696f4`, worktree clean, 원격 일치. 계획 `Check`는 원본 종료 receipt/registry, 후보 APK SHA-256 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`, package/versionCode/signer, host 코드 해시, 출력/소비 경로 미사용을 확인했다. 원본·계획·APK·코드를 수정하지 않았다.
- Windows PC 테스트의 조건부 건너뜀 2건은 별도의 `D1_RECOVERY_PLAN` arrival bundle이 없을 때 실행되지 않는 과거 번들 검증이다. 이번 배포 번들용 검사와 단일 실행/중단/공유 daemon 미소유 경로는 통과했고, `RUN_AFTER_APPROVAL.ps1 -Action Check`도 통과했다. 따라서 추가 전체 테스트를 반복하지 않았다.
- 현재 `adb devices -l`에 단일 무선 transport `adb-…._adb-tls-connect._tcp`가 `device`로 나타났다. `SM-A245N` fingerprint와 hardware serial은 승인 계획의 A24와 일치했다. 상세 transport 문자열은 외부 claim에만 둔다. 별도 사전 조회에서 배터리 94%·비충전·BAT 29.9°C·thermal 0, 화면 Awake/interactive, 밝기 81·수동 모드 0·꺼짐 18,000,000ms가 확인됐다. Run의 기기/설치본/환경 preflight도 통과했으며, 이 값은 이번 시작 시점의 관측이다.

## 소비·단계·종료

| 단계 | 승인 상한 | 실제 | 증거와 판정 |
|---|---:|---:|---|
| 기존 설치본 host pull | 1 | **1 완료** | `commands/004/result.json`: 85.032초, 정상 반환. preflight는 기존 설치 APK와 후보가 다름을 확인 |
| 후보 APK push | 1 | **1 시도, 완료 미확인** | `commands/015/result.json`: 13:24:06.282719Z 시작, 120.032초 timeout, exit 1, stdout/stderr 각 0 byte. 원격 byte 수·완전성 미확인 |
| 원격 SHA-256 | 조건부 | **0** | push 반환 성공 전 중단 |
| `pm install -r` | 1 | **0** | `install_attempt.json` 없음; 설치 명령 전 중단 |
| 설치본 사후 확인 | 조건부 | **1 조회** | 실패 후 `pm path`·`sha256sum`으로 기존 설치본 SHA-256 `86d3fac6504104214fbd4d6b43533a0ec420a051920c2d29ae74ed90c8373e3f` 확인. 후보와 다름 |
| 세션·warmup·추론 | 0 | **0** | 배포 전용 실행기이며 앱 Activity/수집 호출 없음 |
| 전체 | 600초 | **213.563초** | 사전 검사·pull·push 실패·사후 조회·cleanup 포함; 예약 상한 이내 |

Push client PID/시각·부분 출력은 `commands/015`에 보존됐다. timeout 처리에서 시작한 client만 종료되어 `root_reaped=true`; 공유 ADB daemon tree는 종료하지 않았다. 자식 프로세스 전체 부재는 입증하지 않았다. stdout/stderr 0 byte는 **전송량 0이나 무선 단절의 증거가 아니다**. 앞선 COLLECT-03과 같은 120초 timeout이 반복됐지만, 전송 지연의 내부 원인과 실패 시점 원격 staging 파일 상태는 여전히 미확정이다. 이번 실패 후 추가 원격 파일 조회·ADB 재연결·timeout 연장·재전송을 하지 않았다.

cleanup에서 host `am force-stop` 명령은 정상 반환했고 `ps -A`로 대상 앱 프로세스 부재, thermal 0을 별도로 확인했다. 앱 Activity가 시작되지 않아 앱 내부 cleanup receipt는 해당하지 않는다. receipt `cleanup.status=completed`; 배포 성공은 아니다.

## 원본과 다음 경계

- 외부 원본: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_deploy_recovery_run_v1\receipt.json`, `preflight/preflight.json`, `commands/015/{start.json,result.json,stdout.bin,stderr.bin}` 및 `commands/016`~`020`; 전용 소비 registry `energy_ap_deploy_registry/ENERGY-AP-DEPLOY-RECOVERY-01/{claim.json,stopped.json}`. 원본은 수정하지 않는다.
- PC 재현은 위 JSON을 읽는 것으로 제한한다. 현재 설치본·원격 staging 상태를 다시 조회한 것처럼 표현하지 않는다. 정확한 후보 APK 설치는 **미확인/미완료**이므로 후속 에너지·AP 수집 계획을 시작할 수 없다.
- **다음 행동 하나:** 두 번의 무선 push timeout에서 원격 진행량이 기록되지 않은 공백을 대상으로, 전송 진행/원격 상태를 안전하게 구분할 별도 배포 진단 계약을 PC에서 설계한다. 새 ID·예산·승인 없이 이번 소비 계획을 재사용하거나 자동 전송하지 않는다. 무선 자체가 원인이라는 결론이나 임의 timeout 연장은 보류한다.

읽기 전용 결과 확인:

```powershell
python -c "import json,pathlib; r=pathlib.Path(r'C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_deploy_recovery_run_v1'); print(json.loads((r/'receipt.json').read_text())['status']); print(json.loads((r/'commands/015/result.json').read_text())['status'])"
```
