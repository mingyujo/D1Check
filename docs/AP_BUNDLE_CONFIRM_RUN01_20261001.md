# AP 후보의 두 부하 이력 일괄 확인 — 계획·실행·판독

2026-10-01, 착수 HEAD `d6747ab`. 사용자의 “묶어서 실측하는 쪽으로 가자”와 중단 후 “재개해” 승인으로 새 `ENERGY-AP-BUNDLE-CONFIRM-01`을 실행한다. 기존 소비 계획은 재개하지 않는다. 기존 후보를 고정한 **확인2/개발0**이며 새로운 열·전력 계수 적합은 없다. 이 작업의 완료는 두 등록 이력의 자료 적격성·오차·형태 판독 또는 최초 실패의 종료 기록이다. 이번 실행은 기기 연결 부재로 종료했다. 열모형 전체 완성이나 정책 선택 PASS가 아니다.

## 사전 고정한 입력과 판독

같은 최신 서명 APK `3d8ea871…4e94c2`, 네 resident/CPU thread1/각 runtime warmup2·센서·lifecycle·정상 cleanup을 재사용한다. 기존 burst/seed201/B2 기록의 24요청 도착 격자·모델·CG_DC 배정을 유지한다. 첫 확인은 release+35초 한 묶음, 두 번째는 앞12개+35/뒤12개+60초의 두 묶음이다. 예정 도착은 이전 완료와 독립이다. 실제 lane 시간·병행을 PC 값에 맞추거나 간섭1.5를 실제 감속으로 넣지 않는다. [등록 입력](results/ap_bundle_confirmation_01/planned_input.json).

원래 개발3 freeze SHA `35ed6987…034c54`, 기존 preload 후보 절차 SHA `8507adc1…bc7ec5`를 실행 전에 고정하고 원본을 그대로 보존한다. 후보는 frozen β/상태별 유휴 대비 기울기와 부하 전 AP로 산출한 세션별 유효 유휴 기준을 사용한다. **부하 후 AP/current를 예측 입력이나 재적합에 사용하지 않는다.** 예측은 회수 후 생성하는 실제 lane 일정 조건부 계산이며 온라인 정책/종단간 예측이 아니다.

AP 초기값은 실제 공통창 시작 승인값이다. 부하 전 표본의 전체 HAL 조회 bracket이 실제 baseline 시작 이후/첫 dispatch 이전이어야 하며 ≥15표본·span≥55초·gap≤10초다. AP는 첫 dispatch 이후~냉각 종료의 유효 표본에서 절대/변화량 MAE·최대오차·진단 최고값 오차와 구간 잔차를 산출한다. 후기 변화는 사전 고정 `[90,115]`, `[120,145]`, `[150,175]`초의 endpoint bracket으로 판독하며 결측이면 null이고 창을 옮기지 않는다. 120초 J는 원래 동결 W의 진단 계산으로만 함께 기록한다. 전류 raw=mA 조건부·절대 정확도 미인증이다.

공통 환경 gate(배터리≥20%, 비충전, BAT≤35°C, thermal0, 고정 화면 조건, memory/8 warmup 품질·GPU delegate)는 유지한다. numeric AP의 유효성·신선도만 실행 gate이고 개발32.5–34.0°C 범위는 적용 범위 표시다. 범위 밖/짧은 전환은 외삽·전이 진단이다. 현재 APK는 후보 개발749계열과 다르므로 프로토콜 전이를 별도 표시한다. start AP의 범위 통과와 짧은 전환의 strict 지원은 별개다. `accuracy_pass`, `policy_rank`는 null, `experiment_ready=false`/strict/default 불변.

## 정확한 실행 상한

| 항목 | 상한 |
|---|---:|
| 확인/개발 | 2/0, 이력별 새 세션1개 |
| 본 요청/warmup/적격성/총 추론 | 48/16/0/64 |
| runtime/staging/파일 | 8/2/14 |
| 설치본 host pull/APK push/설치 | 1/0/0; 설치본 불일치 시 중단 |
| 고정 관측 | baseline30+common120+cooling60=210초씩, 합계420초 |
| 세션 예약 | stage/gate120+poll485+회수50+cleanup45=700초씩 |
| 최초 기기 preflight/세션 간 자연 대기 | 최대600초/90초 |
| 전체/ADB | **2,090초(34분50초)/6,600명령** |
| 재시도/대체/추가 | 0/0/0 |

600초는 설치 없는 동일성·기기/environment preflight 예약이며 정상 예상시간이 아니다. 앱 watchdog480초/개별 timeout은 poll485에 중첩돼 중복 합산하지 않는다. 등록 release35/60은 common120 안에 포함된다. ADB는 기존 listing0.25초(485초에 최대1,940), HAL AP2초(최대243회×uptime/thermal/uptime3=729), 화면10초(최대49), session gates/staging/승인/회수/cleanup을 더한 **3,200/세션＋전체200** 상한이다. 각 session 관찰 ceiling에서100회수·cleanup slots를 먼저 예약한다. 정상 횟수는 client 지연 때문에 낮으며 과거 C/L 쌍1,543명령·679.531초는 참고 관측일 뿐 이번 완주 보장이 아니다. 세션 간90초는 자연 대기이며 내부 열 상태 동일화 보장이 아니다.

한 최초 목록 조회에서 현재 온라인 A24 한 transport를 선택하고 이후 해당 transport로 고정한다. 내부 gate의 재확인 외에 외부 중복 ADB 조회는 추가하지 않는다. 자동 재연결/전환/설정 변경·새 설치는 없다. 원 실행 소유자만 기존 회수·정리를 수행한다. 앱 정상 cleanup, host force-stop, process absence는 각각 기록한다. 정상 종료를 force-stop으로 대체하지 않는다. 첫 실패면 다음 세션/자동 재실행을 차단한다. parent/child PID·생성시각·명령·실행 ID 및30초 PC checkpoint는 기기 명령 없이 기록한다. 강제 종료/PC 전원 상실까지 최종 receipt를 보장하지 않는다.

## PC 검증·동결 파일

[검증·소스/manifest/APK 해시](results/ap_bundle_confirmation_01/pre_execution_verification.json). 관련26검사 통과/실패·skip0, 실제 PowerShell Check exit0·기기0. 새 분기에서 최초 serial 미선택·설치 없는 실행·2확인 연결/고정 후보 보존·첫 실패 중단·cleanup 중복 방지·소비 차단·고정 endpoint 결측과 기존 단일 전이의 적분/정보 비누설/그림 경계를 확인했다. 기존 test fixture에 빠져 있던 실제 validator의 request count를 보완했다. Android 변경/빌드0, PC fake 검증을 실기기 안정성으로 표현하지 않는다.

계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v1/collection_plan.json`, SHA **`c8382c21c8d9a26dce8523532e2c7ef0aa3f72b1799417c16398c0ef3513691f`**. 새 출력 `energy_ap_bundle_confirm_run_v1`, registry `ap_bundle_registry/ENERGY-AP-BUNDLE-CONFIRM-01`. 실행 직전 출력/registry 없음과 소스·원본 입력·APK·서명·두 freeze 일치를 Check했다. 기존 종료·FAIL·원자료는 보존한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 'c8382c21c8d9a26dce8523532e2c7ef0aa3f72b1799417c16398c0ef3513691f'
# 종료 후 PC 판독, 기존 output과 다른 새 경로만 사용
python -X utf8 -B -m tools.d1_ap_bundle_readout --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v1/collection_plan.json' --output '<새 PC 판독 폴더>'
```

## 실제 결과 — 2026-10-01 18:30 KST 중단

**claim 후 preflight 중단·stopped_no_resume**, 두 확인 모두 미시도다. 첫 `adb devices -l`은 exit0/0.056340초·stdout28bytes/stderr0으로 반환했지만 online/offline/기타 transport가 모두0개였다. 설치본 확인·fingerprint·환경 gate·앱 launch에 도달하지 않았다. 연결 부재의 내부 원인을 단정하지 않으며 무선 설정·ADB server/reconnect를 조작하지 않았다. 이 결과는 에너지/AP 예측 실패가 아니다.

| 실제 소비 | 결과 |
|---|---:|
| 실행 호출/plan claim | 1/1, 소비·종료 |
| 시도·완료 세션 | 0/0, 두 조건 모두 미시도 |
| runtime/warmup/적격성/본 요청/총 추론 | 0/0/0/0/0 |
| staging/파일/pull/push/설치 | 0/0/0/0/0 |
| ADB/실행기 시간/entrypoint tool 시간 | 1/6,600 · 3.362482/2,090초 · 5.797175초 |
| 재시도/대체/추가 | 0/0/0 |

호출0은 progress 부재로 추정한 값이 아니라 **모든 기록이 devices -l 한 명령뿐이고 session attempt/launch attempt가 없다는 실행 경계**로 확인한 값이다. 설치본·현재 앱 상태는 미확인이다. plan claim은 소비됐지만 내부 preflight의 session phase_consumed=false는 모순이 아니다. 이번에는 claim 전 보류가 아니며 Check/Run은 소비 경로로 거절한다. consumed Check 실제 거절을 PC에서 확인했고 기기 명령은 늘지 않았다.

원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_run_v1/FINAL_RECEIPT.json`, `host_checkpoints/0000–0003.json`, `host_commands/0000/client/start.json/result.json/stdout.bin/stderr.bin`, `installation/preflight/preflight.json`, registry `ap_bundle_registry/ENERGY-AP-BUNDLE-CONFIRM-01/claimed.json/stopped.json`를 보존했다. Python child와 PowerShell parent의 PID·생성시각·경로·명령을 별도 PC 조회해 모두 exited로 확인했다. 원래 stack은 receipt/checkpoint에 먼저 남았다. PowerShell의 후속 NativeCommandError는 Python 실패 표면이며 기기 선택 실패 원인이 아니다. redirect stdout/stderr 파일0bytes도 ADB 전송량의 의미가 없다. PC 외부 기록 `ap_bundle_pc_20261001_v1/entrypoint_result.json`.

앱을 시작하지 않아 앱 cleanup은 해당 없음, host force-stop도 미시도다. ADB client는 정상 반환했다. 기기 앱 프로세스 부재는 조회하지 않았으므로 현재 기기 종료 상태를 보장하지 않는다. 별도 회수·기기 조회·재연결·새 계획·재실행은 하지 않았다.

새 공식창/J/AP/실제 병행/예측오차는 모두 null, 비교 그림0. 기존 AP 후보의 냉각·후반 재상승 미확인, 기존 W 유휴 이력 미식별 판정은 그대로다. [결과 화면](results/ap_bundle_confirmation_01/run01/index.html), [소비·보존 요약](results/ap_bundle_confirmation_01/run01/summary.json). 원본 inventory14파일·두freeze/APK/동결 계획·실행소스와 모든 원본 해시 불변을 확인했다. PC 판독 exit0, 부적격 두 조건을 값0으로 채우지 않았다.

**다음 행동 하나:** 사용자 측에서 A24의 무선 ADB 연결을 복구한다. 이 소비 계획은 재개하지 않으며, 이후 동일 두 이력 묶음의 실행은 별도 ID로 구분한다. 이번 턴에는 그 새 계획/실측을 자동 추가하지 않는다.
