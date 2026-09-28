# COLLECT-05 timeout PC 감사와 별도 확인 2조건 준비

**결론:** COLLECT-05 중단을 직접 일으킨 것은 확인 `CG_DC` 앱 준비 중 `run-as … ls` ADB client의 **3.000초 timeout**이다. client 지연의 내부 원인은 미확정이다. 동일 조회의 구조적 중복이나 동시 실행은 확인되지 않아 조회 주기·timeout·센서·APK는 바꾸지 않았다. 기존 개발3세션의 동결 파일 SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`를 읽기 전용 원본으로 묶고 `CG_DC → CC_DG`만 수행하는 **별도 미승인·미소비 확인 block**을 PC에서 준비했다. 원래 6세션 계획은 `stopped_no_resume`이며, 새 자료로 그 계획을 완주했다고 소급 기록하지 않는다.

## 실패 조회와 진행 경계

| 증거 | 직전 동일 조회 slot 14384 | 실패 slot 14385 |
|---|---:|---:|
| 명령 | 현재 선택 transport의 `shell run-as <패키지> ls files/energy-ap-state-collection-v1/<세션>` | 동일 명령·경로 |
| 시작 UTC | 2026-09-27 19:33:43.112737 | 19:33:43.509846 |
| client 경과 | 0.109초 | 제한값 **3.000초**(실제 완료 지연은 우측 검열) |
| exit / 출력 | 0 / stdout 31 byte, stderr 0 | 1 / stdout·stderr 0 byte |
| host 처리 | 정상 반환 | `TimeoutExpired`, 시작 client PID만 회수, 공유 ADB daemon 종료는 시도하지 않음 |

두 조회 모두 localhost ADB server protocol `0029` 사전 검사를 통과했다. 실패 직후 Windows host snapshot 조회 자체가 2초 timeout되어 그 순간의 daemon 상태는 미확인이다. host `failure_detected` checkpoint는 19:33:48.565 UTC이고 Python/PowerShell exit1, stack, `FINAL_RECEIPT.json`과 registry `stopped.json`이 남았다. 이후 기록된 manifest/progress 회수와 host force-stop·`ps -A`·thermal 조회는 반환했으므로 지속 연결 단절이나 앱/GPU 결함을 이 단일 timeout에서 확정하지 않는다. 앱 journal prefix는 runtime4·warmup8 반환까지이며 적격성·공식 baseline·부하는 시작 확인이 없다. prefix 이후 미확인 호출 범위는 [COLLECT-05 원 결과](ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md)대로 유지한다. 앱 cleanup JSON은 회수되지 않았고 host force-stop 반환·사후 앱 프로세스 부재만 확인했다.

## 14,394 host ADB 명령 감사

[재현 가능한 집계](results/energy_ap_state_collect05/adb_audit.json)는 `host_commands/*/client/result.json`과 host checkpoint를 읽으며 serial·개별 원격 경로를 공유 결과에 싣지 않는다. 전체 **14,394/14,394 slot**가 결과 파일을 남겼다. 인접 client의 시간 겹침 **0건**, timeout **1건**이다. 그 외 code0 이외 15건은 staging 파일 존재 검사 5건과 앱 artifact 조회 10건의 범주에 들어간다. 집계만으로 이를 다른 장치 장애로 해석하지 않는다. client 대기시간 합 **1,771.285초**는 host가 client를 기다린 합으로 기기 CPU 시간이나 계측 에너지로 환산할 수 없다.

| 용도 | 횟수 | client 대기 합 | 의미·주기 |
|---|---:|---:|---|
| 준비/완료 파일 `run-as ls` | **8,528** | 960.5초 | 앱 gate·종료 파일 확인, 목표 약 0.25초 polling. 연속 시작 간격 중앙값 0.391초 |
| `/proc/uptime` 전후 bracket | 3,194 | 306.5초 | 약 2초 AP 조회의 monotonic 정렬용 전·후 2회 |
| thermalservice | 1,602 | 135.5초 | 약 2초 AP/thermal 표본 |
| 화면 interactive/power | 395 | 198.4초 | 약 10초 화면 gate |
| 기타 `exec-out` | 394 | 67.5초 | 화면 축소 조회·회수 등 |
| 앱 artifact `run-as cat` | 136 | 13.4초 | gate 파일과 회수 prefix |
| 입력 staging push | 35 | 44.1초 | 시도 5세션×7파일, APK 전송 아님 |

완료된 세션별 동일 listing의 정상 반환 지연 중앙값은 **0.094–0.109초**, P95 **0.172–0.203초**, 최대 **0.688초**였다. 마지막 시도에서는 정상 4회 뒤 1회가 timeout됐다. timeout을 3초의 정상 지연 표본으로 넣어 분위수를 낮추지 않았다. 화면·thermal·uptime·listing은 목적과 자료가 서로 달라 이름이 비슷하다고 중복으로 제거할 수 없다. `ls`가 많은 것은 사실이나, 이 기록만으로 높은 빈도가 실패를 유발했다고 단정할 수 없다. 주기를 늦추면 gate 판독 시점·host/기기 부하가 달라져 기존 동결 모형의 관측 프로토콜과 직접 비교가 약해진다. 이번에는 **poll/timeout 변경 0**이다.
완료 세션의 listing 정상 stdout 크기 중앙값은 세션별 **7.6–14.8KB**, P95 **15.3–30.9KB**, 최대 **30,925 byte**였다. 실패 직전은 31 byte, 실패 client는 0 byte였다. 실제 실행기는 파일 리다이렉션으로 stdout/stderr를 증분 보존한 뒤 종료 시 파일을 읽으므로 Python `PIPE` 미배출 정체는 코드상 재현 경로가 아니다. 0 byte는 client가 원격 작업을 전혀 하지 않았다는 증거가 아니다. 큰 listing 출력의 비용 가능성은 남지만 해당 실패 순간의 출력량이나 내부 정지 지점은 식별되지 않는다.

## 보존한 모형과 완료 확인 1세션

동결 전 `CC_DG → CG_DC → DC_DG` 개발3세션 적격성, 확인 전 `development_freeze.json`·`freeze_receipt.json`, 확인 `DC_DG` 적격성을 원본에서 재확인했다. 동결 모형의 구조·계수·입력 변환·분석 코드 SHA와 기존 결과를 수정하지 않았다. 이미 `DC_DG` 확인 결과를 본 뒤의 이번 작업이며 새 독립 사전등록 검증으로 부르지 않는다.

`DC_DG`의 공통창은 유효 계측 **600.100초**, 전력 표본 605개, AP 경로 표본 229개, 시작 AP **34.1°C**다. 조건부 기기 전체 에너지는 관측 **960.954 J**, 동결 예측 **965.504 J**, 부호 있는 오차 **+4.550 J**(**+0.474%**, 관측 대비)다. AP 경로 MAE **0.645°C**, 최대 절대오차 **1.531°C**다. 이는 **독립 세션 1개**의 사후 판독이고, 절대 J 정확도·다른 배정·임의 도착·정책 선택 적격성을 증명하지 않는다. 개발 시작 AP 범위 32.5–34.0°C보다 해당 확인 시작이 0.1°C 높다는 제한도 유지한다.

## 새 별도 확인 block

PC 계획 ID `ENERGY-AP-STATE-CONFIRM-06`: [동결 계획](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_plan_v1/collection_plan.json>) SHA-256 **`d13e16124570dbe54770fd58b4b94d777ab22d20867cd415c39b603b28089301`**, 같은 폴더의 `RUN_AFTER_APPROVAL.ps1`과 새 manifest 2개. 원래 확인 manifest의 `CG_DC`(기존 index4), `CC_DG`(index5)를 복제해 새 experiment/session ID만 바꿨다. 동일 APK 기대 SHA `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`, 프로젝트 signer SHA `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`, resident 4 runtime·모델/입력·CPU thread1·구간·품질·환경 gate·250ms 제출·AP/전력 계측을 유지한다. Android/APK 소스는 바꾸지 않았다.

새 runner는 COLLECT-05 동결 파일·receipt·원 계획·완료 4세션 신원을 Check에서 검증한다. 실행 시 그 **동일 byte의 동결 파일을 새 출력에 복사**해 해시를 기록하고, 개발 fit 분기를 건너뛰며 두 세션 각각에 기존 `summarize_session`/`evaluate`만 적용한다. 확인 결과를 보고 계수·구조·threshold를 갱신하는 경로가 없다. 별도 output/registry는 **아직 존재하지 않고**, 새 계획의 approval은 `not_approved`다. `Check`는 기기 명령 **0회**로 통과했다.

| 예산 항목 | 후보 최대 |
|---|---:|
| 세션·순서 | 확인 CG_DC → CC_DG, **2세션**; 개발·기존 확인 DC_DG 반복0 |
| 작업 / 적격성 / warmup / 명시적 추론 | **3,360 / 8 / 16 / 3,384** |
| runtime / staging | **8회 / 2회·14파일** |
| APK push·설치 / 설치본 host pull | **0·0 / 최대1**. 설치본 불일치·미확인이면 중단 |
| 재시도·대체·추가 | 모두 **0** |
| 고정 관측 | 2×(resident 준비120＋공식 baseline120＋공통창600＋냉각180)=**2,040초/34분** |
| 각 세션 예약 | **2,100초**: gate120＋host poll1,800＋회수60＋cleanup45＋검증35＋launch20=2,080초, 여유20초. 앱 watchdog과 개별 ADB timeout은 중첩이며 재합산하지 않음 |
| 전체 hard cap | 설치본 preflight300＋2×2,100=**4,500초/75분**. ADB 계산상 정상 최악 20,701 slot, cleanup 전20,900·전체21,000 cap |

정상 평균은 미확정이다. COLLECT-05의 완료 4세션은 각 1,062–1,082초였지만 다른 날짜·초기 온도·배터리/주변·무선 상태에 같은 시간을 보장하지 않는다. 75분은 timeout 합산 **상한 예약**이지 예상 소요시간이 아니다. 반복 부하의 짧은 단독/병행 regimen은 지원 범위 내 확인 목적이며, 2세션이 완료돼도 센서 표본을 독립 세션 수로 세지 않는다. 새 자료는 날짜·프로토콜 lineage를 나눠 기존 확인 DC_DG와 병기할 수 있지만, 최초 6세션 계획의 누락분을 지운 완료 처리로 합치지 않는다. 동일한 host 관측 주기를 유지했어도 날짜/초기 열 상태 차이의 교란은 남는다.

실행 직전 동일 A24 현재 transport/fingerprint, 설치본 hash·서명, 배터리≥20%·비충전·BAT≤35°C·thermal0, 화면/밝기/timeout, host·앱 memory, GPU delegate·직렬/병행 품질 적격성을 새로 확인해야 한다. 과거 gate 결과는 재사용하지 않는다. `Check`는 기기 상태 검증이 아니다. 다음 명령은 **별도 실기기 승인 후에만** 사용한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
# 별도 승인 후 현재 기기 gate를 실행기에서 통과할 때만 1회:
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved
```

관련 PC 검증은 착수 HEAD `ab9e027`＋이번 관련 미커밋 변경을 대상으로 변경 경계 **5건 통과**와 실제 PowerShell `Check` 성공이다. fake device 성공/첫 세션 timeout에서 동결 byte 보존·fit 미호출·두 조건 순서·원래 오류/후속 cleanup 오류 분리·중복 실행 차단을 확인했다. 실제 기록 14,394개로 명령 분포를 재생성했고 출처 없는 가상 fixture만으로 timeout 원인을 판정하지 않았다. 이는 실기기 연결 안정성·새 날짜 계측 비교 가능성·에너지/AP 예측 정확도의 증거가 아니다. 이번 ADB·설치·앱 실행·추론·실측은 **0회**다.

```powershell
python -B -m unittest tools.test_d1_energy_ap_followup tools.test_d1_energy_state_collection.StateCollectionTest.test_current_transport_selection_and_apk_deploy_block tools.test_d1_energy_state_collection.StateCollectionTest.test_recorded_a24_parser_and_energy_boundary tools.test_d1_energy_host_failure.HostFailureTest.test_temperature_failure_keeps_original_stack_and_stop_receipt -q
python -B -m tools.d1_energy_ap_adb_audit --run-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5' --output docs/results/energy_ap_state_collect05/adb_audit.json
```
