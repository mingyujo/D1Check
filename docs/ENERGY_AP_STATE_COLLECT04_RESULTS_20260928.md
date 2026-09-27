# ENERGY-AP-STATE-COLLECT-04 결과 — 첫 개발 세션 중단

**판정: `stopped_no_resume`.** 설치가 검증된 APK를 재사용하는 새 계획을 PC에서 검증·동결하고 한 번 실행했다. 현재 A24와 설치본 SHA-256, 환경 gate는 통과했다. 첫 개발 `CC_DG` 세션은 runtime·warmup·직렬/병행 적격성을 통과해 resident 온도 준비에 들어갔으나, host 실행기가 정상 종료 receipt 없이 끝났다. 공식 baseline과 부하는 시작되지 않았다. 완료 세션은 0/6이며 개발 계수 동결·확인·예측 오차 산출은 **없다**. 기존 `COLLECT-03` 및 배포·설치 계획은 재개하지 않았다.

## 계획과 승인 상한

- 새 ID `ENERGY-AP-STATE-COLLECT-04`, [외부 계획](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v4/collection_plan.json>) SHA-256 `cc8f8cfd3f98f986c6417e939d1f65000f4d988cf1c135208308d445007054f7`. [외부 manifest·Check/Run](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v4/RUN_AFTER_APPROVAL.ps1>). 원래 [수집 계약](ENERGY_AP_STATE_COLLECTION_PREP_20260927.md)의 세 모델 조합, 250ms 반복, 구간·적격성·분석 의미를 유지하고 설치 전용 단계만 제외했다. Android protocol 및 APK는 기존과 동일하다.
- 개발3→동결→확인3, 작업 최대10,080·적격성24·warmup48·명시적 추론10,152, runtime24, staging6회/42파일. APK push/설치0, 동일성 확인 host pull 최대1, 재시도·대체·추가0.
- 고정 관측102분. 설치본 preflight 최대300초＋6×세션 최대2,100초＋동결 최대600초 = **13,500초/225분**의 새 계획 hard cap. 이는 사용자 승인 전체 230분 이내이며 정상 예상시간은 아니다. 기존 설치 단계 600초를 없애고 설치본 preflight 300초로 대체했다.
- 새 registry `energy_collection_registry/ENERGY-AP-STATE-COLLECT-04`. 기존 종료·원자료와 분리했다. 계획의 `Check`는 기기 명령 0회였고, 승인된 `Run`은 한 번만 호출했다.

## 확인된 소비와 중단 경계

| 항목 | 승인 최대 | 기록으로 확인한 값 | 남은/미확인 범위 |
|---|---:|---:|---|
| 세션 | 6 | 개발 첫 세션 1시도·0완료 | 나머지 5 미시도 |
| 작업 호출 | 10,080 | 시작·완료 0 | 회수 앱 journal의 마지막 단계는 온도 준비. 기록 공백의 호출 여부를 일반적으로 0으로 증명할 수는 없음 |
| 적격성 / warmup / 명시적 추론 | 24 / 48 / 10,152 | 4 / 8 / 12 시작·반환 확인 | 이후 명령 없음; 누락된 앱 기록 가능성은 별도 보존 |
| runtime / staging | 24 / 6회·42파일 | 4 / 1회·7파일 | 나머지 미시도 |
| APK push·설치 / 설치본 pull | 0 / 0 / 1 | 0 / 0 / 1 | 설치본 SHA가 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`와 일치 |
| 공식 baseline·부하·냉각 | 각 계획값 | 시작 증거 없음 | 따라서 상태별 점유/전력/AP 계수·예측 오차 산출 불가 |

시작 claim `2026-09-27 16:15:37.953 UTC`; 원 실행기의 마지막 기록된 host 명령 `16:17:46.163 UTC`로 claim 이후 **128.210초**다. host 명령 377개 중 마지막 반환도 정상이며, 3개의 파일 부재 조회 exit은 계획상 예상된 `test -e` 결과다. 원 실행기는 `FINAL_RECEIPT.json`이나 `stopped.json`을 남기지 않았다. Python traceback·확정된 기기 gate 위반·timeout 기록이 없으므로 갑작스러운 host 종료의 원인은 **미확정**이다. 이를 GPU·sampler·온도 실패로 단정하지 않는다. 원 실행기 종료와 뒤따른 회수 완료 사이 공백이 있어 `128.210초`를 전체 현장 소요시간으로 부르지 않는다.

별도 1회 증거 회수는 `16:20:41.402 UTC`에 끝났고 3.156초, ADB 11 command slot을 썼다. claim부터 회수 종료까지 벽시계 약 **303.449초**(중간 공백 포함). 회수한 app journal은 435행(전력 표본 260), `temperature_preparation` 표본 246개, `request_start`·`lane_available` 각 4개, load 단계 0개다. host thermal 표본은 34개다. 이는 세션 전체의 적격 전력·AP 경로가 아니다. 일반적 호출 상한 계산은 중간 누락 가능성을 남기므로, 확인된 12건을 전체 실제 소비의 무조건적인 정확한 상한으로 간주하지 않는다.

## 회수·cleanup 및 모형 판정

[회수 원본 receipt](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_rescue_v4/RESCUE_RECEIPT.json>) SHA-256 `fc7c14837f0738e8f08a8701a73f50c63d3ed7346e0a4bc33404a39aa7edbc28`; [별도 원본 inventory](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_rescue_v4/INVENTORY.json>)는 2,023파일의 경로·바이트·SHA-256을 기록하며 자체 SHA-256은 `0b4443ee25893d2e0ac9714cde48a6eb4a31a995418b3f83841d7a94d6e8c936`이다. 앱 progress·적격성 결과·센서와 host command 기록은 외부 폴더에 원본 그대로 보존했다. 앱 `cleanup.json`은 회수되지 않아 **앱 내부 cleanup 미확인**이다. 별도 host force-stop은 정상 반환했고 사후 프로세스 부재와 thermal status 0은 확인했다. 이것을 앱 cleanup 성공으로 대체하지 않는다. 새 registry의 `postmortem_stopped.json`은 원 실행기의 누락된 receipt를 대신 꾸민 것이 아닌 **사후 종료 주석**이다. 이 계획은 재개·재실행하지 않는다.

개발3세션 중 첫 세션이 공식 baseline 이전에 중단됐으므로 개발 상태 전력/AP 계수, `development_freeze.json`, 확인3세션 및 에너지/AP 예측 오차는 모두 **미산출**이다. 대시보드에 그릴 적격 실측–예측 곡선이 없으며 기존 그림을 새 검증처럼 갱신하지 않는다. A24 current raw=mA의 조건부 해석과 절대 J 정확도 미인증, 임의 도착·BAT·배터리 잔량 미지원, 기존 FAIL·동결값·`experiment_ready=false`를 유지한다.

## 재현과 다음 한 행동

검증 대상은 착수 HEAD `735b21d014f96016e075e1ed16c1c7488cb94829`의 이 작업 미커밋 변경이다. 실행 전 frozen plan `Check`는 기기 명령 0회로 통과했고 관련 PC 49건이 통과했다. 중단 후 `python -B -m unittest tools.test_d1_energy_state_collection tools.test_d1_energy_state_rescue -q`는 11건 통과했으며 소비 계획의 재실행 차단도 확인했다. 회수 journal과 공유 요약의 runtime4·warmup8·적격성4·baseline/load 부재를 PC에서 대조했다. PC 테스트 통과는 실기기 안정성이나 적격 모형 검증이 아니다.

PC 기록·보호 검사(소비된 계획의 `check`는 의도적으로 `consumed output/registry; never resume`를 반환한다):

```powershell
$plan='C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v4/collection_plan.json'
(Get-FileHash $plan -Algorithm SHA256).Hash
python -B -m unittest tools.test_d1_energy_state_collection tools.test_d1_energy_state_rescue -q
```

원본 `energy_ap_state_run_v4/host_commands`, `energy_ap_state_rescue_v4/artifacts`와 회수 receipt를 함께 대조한다. 다음 행동은 **host 실행기의 정상 receipt 부재 원인과 그 실패 시 회수·cleanup 경로를 PC에서 좁히는 것**이다. 미확정 원인 상태에서 6세션 새 수집을 자동 제안하거나 실행하지 않는다.
