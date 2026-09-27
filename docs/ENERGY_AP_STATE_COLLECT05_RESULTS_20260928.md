# ENERGY-AP-STATE-COLLECT-05 결과 — 확인 단계에서 중단

**판정: `stopped_no_resume`.** 이번 새 계획은 현재 A24·설치본·환경 gate를 통과해 한 번 실행됐다. 개발 `CC_DG → CG_DC → DC_DG` 세션 3개가 적격으로 끝났고, 개발 자료만으로 상태별 기기 전체 전력·AP 1차 모형을 동결했다. 확인 첫 `DC_DG`도 완료했으나 다음 `CG_DC`의 앱 준비 중 `run-as ... ls` ADB client가 3초 timeout되어 전체 계획을 중단했다. 완료 **4/6**, 시도 **5/6**이며 마지막 `CC_DG` 확인은 미시도다. 동결 모형은 부분 진단 자료로 보존하되 임의 도착 시뮬레이터의 검증된 상태 모형으로 등록하지 않는다. `experiment_ready=false`를 유지한다.

## 실행 동일성·예산

- 계획: 외부 `energy_ap_state_plan_v5/collection_plan.json`, SHA-256 `4616c2ea358ec7db3f2e3ce1242df1cf485e01fd8f1186cb142815396c9dcd1d`; 실행 `RUN_AFTER_APPROVAL.ps1 -Action Check` 후 `-Action Run -Approved` **1회**. 새 ID `ENERGY-AP-STATE-COLLECT-05`와 별도 output/registry를 사용했다. `Check`의 기기 명령은 0회다.
- Android·APK·250ms 반복 부하·구간·품질·중단 기준은 [기존 수집 계약](ENERGY_AP_STATE_COLLECTION_PREP_20260927.md)을 유지했다. 설치본 SHA-256 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`를 확인했다. 새 host 경로는 [진단 결과](ENERGY_AP_HOST_DIAG_RESULTS_20260928.md)의 실행 신원/checkpoint/실패 회수 개선을 정식 완료 경로에 연결했고, 진단의 baseline 전 강제 종료를 포함하지 않았다.
- 사용자 상한 230분에 대해 계획 hard cap은 설치본 preflight 300초＋6×세션 2,100초＋동결 600초 = **13,500초/225분**이다. 고정 관측은 6×(120초 baseline＋600초 공통창＋300초 냉각)=**102분**. 정상 예상시간이나 배터리 완주 보장은 정하지 않았다. ADB 정상 최악 산식 62,061 slot, hard cap 62,500, cleanup 전 62,400으로 동결했다. 진단 3,000명령 상한을 복사하지 않았다.

| 항목 | 승인 상한 | 기록으로 확인된 소비 | 미시도·불확실성 |
|---|---:|---:|---|
| 세션 | 개발3＋확인3 | 개발3 완료, 확인1 완료＋1 시도/중단 | 확인 `CC_DG` 1 미시도 |
| 작업 호출 | 10,080 | 완료4세션 시작·lane 해제 **3,174** | 중단 세션의 회수 prefix는 작업 시작0, 실제 상한은 그 세션 계획 cap 1,680으로 보수 유지 |
| 적격성 / warmup | 24 / 48 | 완료 세션 16/32＋중단 세션 warmup8 반환 | 중단 세션 적격성 prefix 0, 미회수 구간은 확정0으로 취급하지 않음 |
| 명시적 추론 | 10,152 | 완료·반환 확인 **3,230**(작업3,174＋적격성16＋warmup40) | 중단 세션의 적격성≤4·작업≤1,680은 미확인 범위 |
| runtime / staging | 24 / 6회·42파일 | runtime20 반환, staging5회·35파일 | 6번째 미시도 |
| APK push·설치 / 설치본 pull | 0 / 0 / 1 | **0 / 0 / 1** | 재시도·대체·추가 실행0 |
| ADB / 전체 시간 | 62,500 / 승인230분 | **14,394 slot / 4,342.422초(72분22.422초)** | 계획 hard cap225분 이내 |

호출 수는 영속적인 시작·반환/lane 해제 쌍의 확인치다. timeout 직전과 강제 종료 사이를 누락 없이 관측했다고 단정하지 않으며, 분모와 계획 cap을 유지한다. 종료 계획·소비 registry와 기존 COLLECT-03/04, host 진단 원본은 서로 합치거나 재개하지 않는다.

## 동결 모형과 한 개 확인 세션

세 개발 세션의 시작 AP는 각각 **32.5, 33.8, 34.0°C**였고, 실제 공동 lane 점유는 **78.48, 119.88, 119.95초**다. 공통창 기기 전체 에너지는 조건부 A24 raw=mA 해석에서 각각 **931.147, 964.961, 959.527 J**였다. `development_freeze.json`의 `energy-ap-state-regimen-fit-v1`은 resident idle과 4종 단독·3종 병행 상태의 전체 평균전력(W), 각 상태의 AP 기울기, 공통 냉각률을 개발 자료만으로 추정했다. 병행 전력을 단독 전력의 합으로 만든 값이 아니다. 설계 rank 9/9, 최소/최대 특이값 비 0.00921, 개발 AP 기울기 RMSE 0.0942°C/s다. **상태 점유 regimen의 계수**이며 짧은 임의 요청별 비용이나 물리적으로 독립 검증된 열전달 계수가 아니다.

동결 전력은 resident idle **1.225 W**, 분류 CPU/GPU **1.741/1.611 W**, 탐지 CPU/GPU **1.932/1.613 W**, CC_DG **2.110 W**, CG_DC **2.327 W**, DC_DG **2.313 W**다. 이는 idle 포함 기기 전체 전력의 조건부 추정값이며 CPU/GPU 칩 직접 전력이나 절대 정확도 인증값이 아니다. AP 초기 개발 범위는 32.5–34.0°C, 개발 경로 관측 범위는 32.5–39.5°C다.

완료한 확인 `DC_DG` 1세션은 시작 AP **34.1°C**(개발 *시작* 범위보다 0.1°C 높음), 작업535건, 실제 공동 lane 점유120.40초였다. 동결된 지원 검사는 이 초기값을 개발 *경로* 관측 범위 안으로 받아들였지만, 다른 초기 열 상태의 정확성까지 검증한 것은 아니다.

| 확인 `DC_DG`, 공통 600초 창 | 관측 | 동결 예측 | 예측−관측 |
|---|---:|---:|---:|
| 조건부 기기 전체 에너지 | 960.954 J | 965.504 J | **+4.550 J** |
| 누적 에너지 경로 | — | — | MAE **3.233 J**, 최대 절대오차 **11.124 J** |
| AP 경로 | — | — | MAE **0.645°C**, 최대 절대오차 **1.531°C** |
| AP 최고값 | 39.3°C | 39.265°C | **−0.035°C** |
| 연구용 30°C 초과 시간 | 596.88초 | 596.88초 | 0초 |

에너지 표는 양쪽 모두 유효 표본이 덮는 동일 공통창 600.100초의 결과다. 전류 단위는 A24 raw=mA **가장 유력한 조건부 해석**이며 절대 J 정확도는 미인증이다. AP는 `mType=0` 센서로 BAT·SKIN·잔량%·사용시간·열 안전성 대신 쓰지 않는다. 30°C는 연구용 계산 기준이며 안전 한도가 아니다. AP 최고값이 가까워도 경로 최대오차 1.531°C가 있어 경로 정확성을 최고값 하나로 대체하지 않는다. 확인 조건당 1세션조차 채우지 못했고 CG_DC/CC_DG의 확인 오차 및 조건 간 차이 방향은 **미산출**이다. 이 한 개의 사후 확인 결과로 정확도 PASS·시뮬레이터 적격성·정책 절감을 선언하지 않는다.

## 중단·회수 경계

첫 확인 세션은 앱 `cleanup.json.status=completed`, 자료 적격성 및 host cleanup을 통과했다. 다섯 번째 시도는 runtime4·warmup8이 앱 journal에서 반환됐고 공식 baseline/부하 시작 전, host `host_commands/14385/client/result.json`의 `run-as ... ls`가 **3.000초**, stdout/stderr 각각 0 byte, `TimeoutExpired`, exit1로 끝났다. 직전 동일 조회는 정상 반환했다. 단일 client timeout으로 기기 연결 단절·앱 오류·GPU 결함을 확정할 수 없다.

원 실행기는 원래 stack과 `FINAL_RECEIPT.json`, checkpoint, `stopped.json`, PowerShell/Python exit1을 보존했다. 실패 회수에서 manifest와 progress prefix는 회수했지만 `cleanup.json`·두 failure JSON은 정상 JSON으로 회수되지 않았다. 이는 앱 cleanup 부재/실패 여부까지 확정하지 않는다. host `am force-stop`은 정상 반환했고 직후 `ps -A`에는 해당 앱 프로세스가 없으며 thermal status 0을 확인했다. **host 강제 종료와 앱 정상 cleanup은 다른 사실**이다. 종료 후 배터리 잔량·장시간 지속 상태는 새로 확인하지 않았다.

원본 [FINAL_RECEIPT.json](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/FINAL_RECEIPT.json>) SHA-256 `fd0e8d888314b95beec772e39d559630e72ba7ca54810d334ab422dc79147b66`, 동결 [development_freeze.json](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json>) SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`, command 기록·원본 session artifacts·host entry/registry는 외부 폴더에 그대로 있다. [작은 요약·CSV·그림](results/energy_ap_state_collect05/README.md)은 원본을 수정하지 않는 별도 산출물이다.

## 재현과 다음 행동

```powershell
$plan='C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v5/collection_plan.json'
(Get-FileHash $plan -Algorithm SHA256).Hash
python -B -m tools.d1_energy_ap_collect05_partial --run-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5' --output docs/results/energy_ap_state_collect05
```

소비된 `Run`은 재호출하지 않는다. 부분 그림/CSV는 이 외부 원본이 있어야 재생성할 수 있다. 다음 행동은 **ADB `run-as ls` 3초 조회의 이번 timeout과 앞선 정상 조회를 PC 명령 기록으로 대조해, 후속 새 수집에서 같은 조기 중단이 반복될 위험을 좁히는 것**이다. 새 실측·timeout 연장·동결 모형 재보정은 자동 실행하지 않는다.

검증 기록(2026-09-28 KST, 착수 HEAD `0c04cc1`＋이번 관련 미커밋 변경): 계획 `Check` 통과/기기 명령0, 정식 `Run` 1회; 변경 경계의 PC unittest 7건 `OK`. 부분 산출 스크립트는 저장된 확인 오차와 재계산값의 완전 일치를 검사하고 SVG/PNG를 열어 한글·단위·범례와 경로를 확인했다. PC 검증은 이번 실기기 실패의 재발 방지나 물리 모형 정확성 보장이 아니다.
