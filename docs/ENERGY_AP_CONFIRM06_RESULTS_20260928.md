# ENERGY-AP-STATE-CONFIRM-06 실행 중단

**판정:** 승인된 SHA `d13e16124570dbe54770fd58b4b94d777ab22d20867cd415c39b603b28089301` 계획을 2026-09-28 UTC에 한 번 실행했다. 현재 온라인 A24와 계약 fingerprint·하드웨어 serial, 설치본 SHA `b273f74…114cf`, 비충전·배터리 40%·thermal 0 등 실행기 gate를 통과하고 기존 개발 동결 파일 SHA `35ed6987…034c54`를 byte 동일하게 로드했다. 첫 확인 `CG_DC`는 resident 준비와 공식 baseline 일부까지 진행했지만 ADB transport가 실행 중 사라져 **0/2세션 완료**, `CC_DG`는 미시도다. 원 계획과 이 별도 계획 모두 재개하지 않는다. `experiment_ready=false` 유지.

## 실패 시각과 확인 가능한 진행

| 경계 | 원본 증거 |
|---|---|
| 시작·소유권 | `host_entry_20260928T024921471Z_*/start.json`, host checkpoint 0000, 단일 소비 claim |
| preflight | 66.703초, APK 설치본 SHA 일치, push·설치 0, 설치본 확인 host pull 1 |
| 첫 세션 | gate 통과→입력 7파일 staging→앱 launch→runtime/warmup·적격성 gate 파일 회수→120.592초 resident 온도 준비 완료→공식 baseline 시작 |
| 마지막 정상 명령 | slot 0607, 02:54:15.260 UTC `run-as … ls`, exit 0, 1.094초, stdout 360 byte. 당시 목록에 serial/parallel 적격성 result·warmup·progress 파일이 있었다 |
| 직접 실패 | slot 0608, 02:54:16.631 UTC `exec-out cat /proc/uptime`, **0.328초**, exit `4294967295`(-1), stdout 0, stderr `error: closed`. 2초 timeout에 도달한 사례가 아니다 |
| 이후 | slots 0609–0614의 회수 5개와 host `am force-stop`은 선택된 transport를 찾지 못해 실패. 원래 오류와 각 후속 오류가 별도로 `FINAL_RECEIPT.json`에 남았다 |
| host 종료 | Python exit 1·PowerShell wrapper exit 1, checkpoint `stopped`, parent/child 종료 확인. 당시 앱 cleanup·앱 프로세스 부재는 미확인 |

`error: closed`와 이어진 `device not found`는 **선택 transport가 ADB에서 없어졌다는 관측**이다. 무선 링크·mDNS·ADB daemon·기기 상태 중 어느 내부 원인이었는지는 현재 로그로 구분할 수 없다. 이 실패를 앱·GPU·추론 결함이나 앞선 COLLECT-05의 `run-as ls` timeout과 동일 원인으로 확정하지 않는다. 원본 host stdout/stderr·명령별 exit·부분 출력·checkpoint는 수정하지 않았다.

처음에는 연결 소실 뒤 앱 호출 여부가 미확인이었다. 사용자가 연결을 복구한 뒤 새 transport의 model·fingerprint·하드웨어 serial이 모두 승인 A24와 일치함을 확인하고 세션 원본 15파일을 읽기 전용으로 회수했다. 전체 `progress.jsonl`은 sequence 0–499가 빠짐없이 있고 마지막이 `app_cleanup`인 500기록이다. runtime 4회·warmup 8회·적격성 4회의 시작/반환과 lane 해제, 120.592초 온도 준비, 공식 baseline 약120.055초 시작/종료, 이어진 `baseline_gate`를 보여준다. `request_start` 4건은 모두 적격성이며 **본 작업 호출 시작·완료 0회**다. 앱은 `baseline_gate`에서 `IllegalStateException: bounded phase/call timeout`을 기록하고 `cleanup.json`에 `status:failed`를 남겼다. sampler failure 파일은 없었다. host가 끊긴 동안 앱은 계획의 다음 부하를 시작하지 않았다는 점이 이제 원본으로 확인됐다. host가 연결된 동안의 AP 65표본(29.5–31.2°C)과 앱 power sample 318개는 모두 부하 이전의 부분 자료이며 완성된 공통창 자료가 아니다.

코드상 `resident_baseline` 종료 뒤 앱은 `baseline.ready.json`을 쓰고 **host의 `baseline.arm`을 최대60초 기다린다**(`EnergyCollectionActivity.gate`, 기본 `waitNs`). 이번 원본에서 baseline 종료부터 `session_failed`까지 약61.13초이며 host checkpoint에는 baseline arm이 없다. host가 baseline 중 연결을 잃어 arm할 수 없었고, 앱은 예정된 gate 시간 상한에서 종료한 순서가 코드·원본과 일치한다. 앱의 `baseline_gate` 예외는 별도의 독립 추론 실패 증거가 아니다. 다만 ADB transport가 왜 소실됐는지는 이 순서로도 알 수 없다.

## 예산·회수 판독

| 항목 | 승인 상한 | 확인된 소비·상태 |
|---|---:|---|
| 세션 | 2 | `CG_DC` 1시도·0완료, `CC_DG` 0시도 |
| 작업 / 적격성 / warmup / 명시적 추론 | 3,360 / 8 / 16 / 3,384 | 회수된 전체 journal로 **작업 0·적격성 4·warmup 8 = 명시적 추론 12회** 확인. 두 번째 세션 미시도 |
| runtime / staging | 8 / 2회·14파일 | 첫 세션 resident runtime 4 활성 snapshot, staging 1회·7파일 |
| APK push·설치 / 설치본 pull | 0·0 / 최대1 | 0·0 / 1 |
| ADB slot / 시간 | 21,000 / 4,500초 | 원 실행 **615 / 308.484초**. 최초 단일 회수 시도 `adb devices -l` **1명령 / 1.797초**, 온라인 기기 0대. 사용자 연결 복구 뒤 별도 목록 조회1＋기록형 읽기 전용 확인·원본 회수17=**18명령**. 전체 기기 명령634. 첫 진입부터 마지막 상태 조회까지 약996.9초(사용자 연결 복구 대기 포함) |
| 재시도·대체·추가 세션 | 0 | 모두 0. 별도 회수는 추론·세션 재실행이 아님 |

원 실행의 host cleanup 명령은 `device not found`로 실패했다. 원 실행 parent/child가 종료된 것을 PC 소유권 검사로 확인하고, 승인된 실패 후 회수·cleanup 목적의 별도 단일 복구기를 150초 이내로 한 번만 호출했다. 이 복구기는 온라인 기기 0대로 fingerprint를 확인할 수 없어 첫 `devices -l` 뒤 종료했다. 별도 복구 claim/receipt는 보존하며 재호출하지 않는다. 이후 사용자가 연결을 복구해 동일 A24를 확인한 뒤 세션 원본을 읽었다. **앱 cleanup 기록은 존재하지만 실패 상태의 cleanup이며 정상 완료가 아니다.** 마지막 읽기 전용 확인에서 앱 프로세스는 남아 있었고 배터리 39%·비충전·BAT 29.7°C·thermal 0이었다. `dumpsys activity`에 이 세션 ID와 Activity가 함께 없어 외부 host force-stop 소유권을 확인할 수 없었고 **강제 종료하지 않았다**. 앱 프로세스 존재만으로 이번 세션이 계속 실행 중이라고 말할 수도 없다. 강제 재연결·ADB 서버 재시작·다른 transport 해제는 하지 않았다.

## 모형 확인 범위와 다음 조건

이번 별도 block의 `CG_DC`·`CC_DG`는 공통창 적격 완료가 없어 **관측/예측 에너지, 누적 경로, AP MAE·최고온도·한도 초과 시간 오차 모두 계산 불가**다. 기존 COLLECT-05의 확인 `DC_DG` 1세션(+4.550 J/+0.474%, AP MAE 0.645°C)은 [기존 결과](ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md)에 그대로 둔다. 이번 부분 준비 자료를 개발 fit이나 확인 표본으로 편입하지 않고, 기존 동결 계수·코드·기준을 변경하지 않았다. 새 비교 그림은 완성된 공통창이 없어 만들지 않았으며 [기존 DC_DG 그림](results/energy_ap_state_collect05/confirmation_path.svg)은 기존 결과로만 남긴다.

**다음 행동 하나:** 원본 ADB client·server/transport 기록을 대상으로 연결 소실 경계를 PC에서 진단한다. 앱 gate 시간 상한과의 순서는 위에서 확인했으며, 같은 계획의 실행/회수 claim을 재호출하거나 새 확인 실측을 자동 시작하지 않는다.

원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_run_v1/FINAL_RECEIPT.json`, 같은 폴더의 `host_commands/0608/client/result.json`, `host_checkpoints/`, 원본 `00_91172a82-*/`, `energy_ap_state_confirm_recovery_v1/RECOVERY_RECEIPT.json`, 복구 뒤 `energy_ap_state_confirm_postfailure_audit_v1/artifacts.tar`와 `artifacts/progress.jsonl`, 계획 폴더의 `host_entry_*/`. 회수 archive SHA-256 `3597fc88c52d0448c11dbf9eb5d7085055c536aa5c96284b0020a2590adabc76`. 공유 가능한 작은 수치 요약은 [summary.json](results/energy_ap_state_confirm06/summary.json). 재현은 기기 명령 없이 원본 receipt·명령 결과·회수 journal을 읽는다:

```powershell
Get-Content 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_run_v1/FINAL_RECEIPT.json' -Encoding utf8
Get-Content 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_run_v1/host_commands/0608/client/result.json' -Encoding utf8
Get-Content 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_recovery_v1/RECOVERY_RECEIPT.json' -Encoding utf8
Get-Content 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_postfailure_audit_v1/artifacts/progress.jsonl' -Encoding utf8 | Select-Object -Last 8
```

PC 무결성 확인(2026-09-28 03:11 UTC, 착수 HEAD `55588b1`＋이번 미커밋 문서)은 Python `json`·`hashlib.sha256`·`collections.Counter`로 원 receipt의 종료/615명령/0완료, 새 출력 동결 SHA, 회수 tar SHA, 전체 journal 500기록의 runtime 반환4·warmup 반환8·적격성 `request_start`/lane 해제 각4·본 작업 시작0, 공유 summary의 계산 불가 표기를 대조해 **PASS**였다. 이 PC 검사와 부분 회수는 에너지/AP 모형의 새 예측 정확도나 ADB 연결 안정성을 검증하지 않는다.
