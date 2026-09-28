# DEVICE-SEGMENT-DIAG-04 실행 (2026-09-29)

사용자의 “알아서 실측까지 계속 진행해” 지시에 따라 새 lifecycle 기록 APK로 기존 한 세션 진단을 준비했다. DIAG-03을 재개하지 않으며 이번 ID는 `ENERGY-AP-DEVICE-SEGMENT-DIAG-04`다. [기존 진단 계약](ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md)과 [수정·PC 검증](ENERGY_AP_DEVICE_SEGMENT_LIFECYCLE_PC_20260929.md)을 적용한다. Android·측정 부하·gate는 추가 변경하지 않았다. 기존 정식 CG_DC/CC_DG 확인 block과 합치지 않는다.

- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v4/collection_plan.json`, SHA-256 `187dd4af1f552117cc38a021e40f3fc922471cdf2f22c9a87dbbe68d58e771dd`.
- APK: `energy_ap_lifecycle_build_v1/benchmark-runner-modelProbe.apk`, SHA-256 `933d202e5c6e2244ea1216a0935daa03088d550552e88be8f009be68f4d831f7`, 기존 프로젝트 signer. 새 빌드 없이 직전 검증본을 복사했다.
- 상한: CG_DC 진단1, runtime4·warmup8·적격성4·작업1,680·총추론1,692, staging1/7파일, 설치본 pull1, APK push/install 각각1, 재시도/대체/추가0. 고정 관측1,020초·준비최대360초·세션2,100초·preflight600초·전체2,700초, ADB11,000/cleanup 전10,900. 조건부 동일 세션 읽기 전용 회수1은 최대90초/12명령으로 제한하며 앱 terminal·원 host 종료가 선행해야 한다. 누적 작업 상한2,790초, 연결 복구 대기시간은 별도다.
- numeric AP는 host의 준비 적격성과 분석용 경로 관측이며 앱 thermal status로 대체하지 않는다. 진행 중 AP 결측은 에너지/AP 분석 적격성과 앱 lifecycle 완료를 별도로 판정한다.
- 원본 출력: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v4`; registry는 `energy_collection_registry/ENERGY-AP-DEVICE-SEGMENT-DIAG-04`. Check 시 둘 다 미소비였다. 계획 JSON의 `not_approved`는 생성 시 고정값이고 이번 사용자 승인과 `Run -Approved`를 별도로 기록한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v4/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v4/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved
```

Check는 기기 명령0. 새 ID 외 실행 의미 변경 없음, 관련 host 진입7건을 확인했다. 시작 HEAD `8c274fbe666ae65d3ef76e6fdbe4d087186ae4e4`, 진단 ID 갱신이 미커밋인 상태에서 계획의 소스 해시를 동결했다. 실행 결과는 아래에 기록한다. 기존 원본·FAIL·개발3·동결 모형·DC_DG 확인 및 `experiment_ready=false` 유지.

## 실제 결과: 정상 완료, 정식 확인과 분리

`completed_regimen_diagnostic_only`, CG_DC 1세션 정상 완료. 현재 동일 A24·설치본·환경·앱 적격성을 실행기에서 확인한 뒤 진행했다. 새 APK의 전송·데이터 보존 설치·해시/프로젝트 서명 검증 완료. 추가 조회·재연결·재실행은 하지 않았다.

| 항목 | 실제 / 상한 |
|---|---:|
| 세션 | 1 / 1 |
| runtime / warmup / 적격성 | 4/4 · 8/8 · 4/4 |
| 본 작업 / 총 명시적 추론 | 1,073/1,680 · 1,085/1,692 |
| staging / 입력 파일 | 1/1 · 7/7 |
| 설치본 pull / APK push / 설치 | 각 1/1 |
| ADB 명령 | 3,345/11,000 |
| 전체 시간 | 1,148.453/2,700초 (19분 8.453초) |
| 조건부 사후 회수 / 재시도·대체·추가 | 모두 0 |

시간 제한 반복 부하에서 미사용 작업 상한607회는 실패·누락이 아니다. 작업1,073회 및 적격성4회의 시작·성공 반환·lane 해제를 확인했다. warmup8·runtime4 반환도 기록됐다. ADB timeout0, nonzero exit4는 시작 전 지정 경로의 `test -e` 부재 결과이며 전송/연결 오류가 아니다. APK push1과 입력 staging의 push7은 별도 소비다.

## 종료·회수와 시간축

host UTC 기록: 실행 claim 09-28 16:24:54.185 → 설치 검증16:25:54.276 → Activity launch 반환16:26:08.058 → probe.arm16:28:24.198 → baseline 완료 관측16:30:26.160 → 세션 host cleanup16:43:37.544 → 최종 checkpoint16:44:01.084. 한국시각은 각각 +9시간이다. baseline 완료 관측은 **사후 관측이며 host baseline.arm이 아니다**.

앱 monotonic 기록에서 준비123.086초 → baseline120.103초 → 지정 부하/상태 전환 → post-work 대기 → 냉각180.099초 → `app_cleanup(error=null)` → `finish_requested(stop_reason=null)` 순서를 확인했다. lifecycle_cancelled·session_failure·sampler failure 없음. 현재 소스는 journal 종료 뒤의 onDestroy를 기록하지 않으므로 해당 callback을 직접 관측한 것으로 표현하지 않는다. host wall clock과 앱 monotonic을 직접 빼지 않았고, 위 절대시각은 host 관측 시각이다.

force-stop은 전체2회: **설치 후 앱 시작 전 정리1회 + 세션 정상 완료/회수 후 정리1회**다. 세션 후 중복 cleanup은 없었다. 앱 cleanup 성공, host force-stop 성공, 마지막 `ps -A`에서 대상 패키지 프로세스 부재를 각각 확인했다. 회수1,089파일·오류0, archive SHA-256 `d41cd14bd9f54876db83803a3800d3feaeaca93424ae1e8bef1519f28da7316e`. PowerShell/Python 정상 exit0. 별도 사후 회수 불필요.

이번에는 ADB 연결 소실이 관측되지 않았다. 따라서 연결 소실 뒤 자율 진행이나 과거 onDestroy 원인 해결을 검증하지 않았다. 사용자 무선 디버깅 스위치 OFF→ON 관측은 별도 사실이며 이번 로그로 스위치의 연속 ON을 추정하지 않는다.

## 계측 결과와 적용 한계

- 공통 부하 관측창 **600.098초**, 기기 전체 에너지 **953.069J**, 평균 **1.588W**. 기존 적분기로 재현, 유효 에너지 coverage600.098초·결측0. 준비/baseline/냉각/설치 비용은 이 숫자에 포함하지 않는다. 미계측 host 준비 비용을 소비0으로 간주하지 않는다.
- AP `mName=AP,mType=0`, °C. 공통창 시작32.6°C·최고37.6°C. 전체 앱 전력1,038표본·host AP390표본. 앱 배터리 표시는62→60%, 비충전·thermal status0이며, 이 변화로 배터리 수명이나 절대 에너지를 검증하지 않는다.
- pair lane 공동 점유 **120.037초**, host invocation 교집합 **9.062초**. 전자는 dispatch부터 실제 lane_available까지, 후자는 invocation_start/end까지다. 어느 것도 GPU hardware 실행의 직접 측정이 아니다. pair 구간 평균2.258W는 이 반복 부하 전체의 관측값이며 지속적인 두 모델 동시 추론 상태의 식별 계수로 승격하지 않는다.
- raw 전류=mA 조건부 해석·절대 정확도 미인증 유지. 새 APK와 관측 방식의 **프로토콜 전이 진단**이다. 기존 동결 모형 재보정/정확도 PASS 없음, 기존 CG_DC·CC_DG 동일 조건 확인은 여전히 미완료. 개발3·DC_DG 확인을 합쳐 새 독립 반복으로 세지 않는다.

[작은 요약](results/energy_ap_device_segment_01/diag04/summary.json), [상태 구간 CSV](results/energy_ap_device_segment_01/diag04/blocks.csv), [에너지 CSV](results/energy_ap_device_segment_01/diag04/energy.csv), [AP CSV](results/energy_ap_device_segment_01/diag04/ap.csv), [관측 곡선](results/energy_ap_device_segment_01/diag04/observed.svg).

PC 재현(기기 명령 없음; 원본은 공유 제외):

```powershell
python tools/d1_energy_device_segment_report.py --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v4 --output docs/results/energy_ap_device_segment_01/diag04
```

원본 `FINAL_RECEIPT.json`, 세션 `validated.json`, `artifacts/progress.jsonl`, `artifacts/summary.json`, `artifacts/cleanup.json`, `thermal.jsonl`, `host_cleanup.json`, `recovery.json`, host 명령·checkpoint는 위 외부 실행 폴더에 보존한다. 재현 스크립트는 원본 progress/thermal 해시·성공 lane 수·기존 적분 일치를 검증하며 계수를 적합하지 않는다. 생성물에 기기 식별정보는 포함하지 않는다.

**다음 행동 하나:** 추가 실측 없이 이 새 프로토콜의 적격 구간에 기존 동결 모형을 변경 없이 적용할 수 있는지 지원 범위를 검사하고, 가능할 때만 별도 전이 예측 오차를 PC에서 산출한다. 정식 확인 완료나 새 모형 적합으로 처리하지 않는다.
