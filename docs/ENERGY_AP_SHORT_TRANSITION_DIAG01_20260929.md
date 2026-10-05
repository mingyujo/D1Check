# A24 짧은 상태 전환 진단 1세션과 시뮬레이터 적용 경계 (2026-09-29)

**판정:** 별도 opt-in `ENERGY-AP-SHORT-TRANSITION-DIAG-01`을 PC 검증 뒤 A24에서 한 번 실행했고 앱 정상 종료·원본 회수·host 정리를 확인했다. 10~20초의 단독·유휴·CC_DG 병행 전환을 관측하는 기술 목표는 충족했다. 그러나 공통창 시작 AP가 **32.3°C**로 기존 개발 동결 모형의 관측 지원 범위 **32.5~39.5°C 밖**이다. 이 세션에 대한 동결 모형의 **지원 판정은 계산 불가**이며, 아래 수치 대입은 외삽 진단일 뿐 예측 오차 검증으로 승격하지 않는다. [오프라인 대시보드](results/energy_ap_short_transition_01/dashboard.html)와 [CSV·그림·재현 안내](results/energy_ap_short_transition_01/README.md)를 제공한다.

## 고정된 질문과 실행 계보

기존 queue/seed201/strict 24요청 PC 일정의 단독 점유 최대가 1.145초이고 FIXED_SPLIT의 CC_DG 공동 점유가 0초라, 1초 전류·약2.65초 AP 표본으로 해당 일정의 상태별 계수를 식별할 수 없었다. 이번에는 그 정책을 바꾸거나 기존 12세션 도착 계획을 재개하지 않고, A24 동일 두 모델·입력·4 resident runtime의 **CC_DG 한 조건**에서 상태 전환의 관측 가능성을 물었다. 결과를 보기 전에 6주기×(pair20초, idle10초, 탐지 GPU 단독15초, idle10초, 분류 CPU 단독15초, idle10초)를 고정했다. 목표 부하480초와 완료 후 유휴120초가 공통창600초다. 준비120초·baseline120초·냉각180초는 공통창 에너지 밖이다. 제출 간격250ms는 실제 추론 동시성을 뜻하지 않는다.

계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_plan_v1/collection_plan.json` SHA-256 `16fd8b08dd0f8ec3b5ea8909ddf84434c5406f7f69cbf215cafb1f3d2e50913d`. 프로젝트 서명 APK SHA-256 `7ce5d11ebe9ae67036f434d3150b52ca6178b388d3919057ee4eaee431402caa`, 기존 COLLECT-05 개발3 동결 파일 SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`. 여기의 APK는 새 블록 프로토콜을 위한 것이며 기존 정식 확인 APK/계측과 동일 조건으로 취급하지 않는다. frozen byte는 실행 전후 일치했다. 개발·확인 자료로 재적합하지 않았다.

## 실제 수행·계측 결과

| 항목 | 관측 / 계획 상한 |
|---|---:|
| 세션 | 1 / 1, 진단만 |
| runtime·warmup·적격성·본 작업 | 4/4 · 8/8 · 4/4 · 1,039/1,680회 |
| 총 명시적 추론 | 1,051/1,692회 |
| staging·입력 파일 | 1/1 · 7/7 |
| APK push·설치·설치본 확인 pull | 각 1/1 |
| ADB 명령 slot | 3,634/11,000 |
| 실행 시간 | 1,129.172/2,700초 |
| 재시도·대체·추가 | 0 |

원본은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_run_v1/FINAL_RECEIPT.json`와 동일 폴더 세션 artifacts·host 명령·checkpoint다. 앱 `summary.json`·`cleanup.json`은 각각 `completed`, 회수는 `recovered`(1,055파일, prefix 오류0), host cleanup은 `completed`다. host가 앱 정상 종료 **후** 대상 패키지 force-stop과 프로세스 부재 확인을 수행했으며 이를 앱 자체 cleanup으로 합치지 않는다. 이번 세션에서 transport 소실은 관측되지 않았지만 연결 소실 내성을 입증하지 않는다.

공통창 **600.094초**의 기기 전체 관측 에너지는 **903.842J**, AP 시작 **32.3°C**, 최고 **36.6°C**다. 36개 예정 블록은 모두 실제 적격성을 통과했고 6개 pair 블록의 공동 lane 점유는 각각 **12.908~13.352초**, 합계 **78.565초**다. 이는 실제 lane 점유이며 GPU kernel 또는 host invocation의 지속 겹침 증거가 아니다. 각 10초 idle 블록의 AP 표본 최솟값은 3개, pair 블록은 7~8개였다. 전류 표본은 600.094초 공통창을 gap/중복 없이 적분했다. 이는 A24 raw 전류=mA의 **조건부** 에너지이며 절대 정확도는 인증되지 않았다.

## 동결식 범위 밖 대입: 정확도 아님

기존 `whole_device_power_w`와 AP 1차식을 실제 블록 경계에 대입하면 상태 매핑 **600.056초**에 관측 **903.793J**, 수치 대입 **927.073J**, 대입−관측 **+23.280J**다. 미매핑 **0.0376초**와 그 관측 약0.049J는 0으로 채우거나 예측 총량에 몰래 합치지 않았다. AP 경로 229표본의 수치 대입 MAE **0.739°C**, 최대 절대차 **1.877°C**이고 표본 기준 예측 최고 **36.234°C** 대 관측 최고 **36.6°C**다. 시작 AP가 지원 밖이므로 이 수치들을 새로운 확인 오차, PASS, 통계적 성능으로 인용하면 안 된다.

| 실제 상태 | 시간(초) | 관측(J) | 동결식 대입−관측(J) |
|---|---:|---:|---:|
| 분류 CPU＋탐지 GPU | 123.239 | 250.492 | +9.595 |
| 탐지 GPU 단독 | 93.573 | 153.077 | −2.188 |
| 분류 CPU 단독 | 90.038 | 149.866 | +6.928 |
| resident idle·완료 후 유휴 | 293.206 | 350.359 | +8.945 |

합계 오차만 볼 경우 탐지 GPU의 음수 잔차가 다른 양수 잔차를 일부 상쇄한다. 블록별 차이는 전력과 일정의 사후 회계 비교이지 원인 분해나 요청별 에너지 배분이 아니다. AP 센서 `mName=AP,mType=0`은 BAT·표면·공식 안전온도가 아니다. 초기 온도 평행 이동, 미계측 전력 0 대입, 확인 자료 재보정은 하지 않았다.

## 시뮬레이터에 실제 연결한 범위와 남은 필수 조건

기존 상태별 기기 전체 전력·AP 연속 열식을 재사용하여 **기록된 짧은 일정의 조건부 경로를 재생·외삽 계산**하는 별도 결과 화면과 CSV를 연결했다. 이는 원본 trace를 그대로 표시하는 기능과 동결식의 수치 대입을 구분한다. 시뮬레이터의 `energy_ap_state_regimen_fit_v1`은 임의 도착 입력에 계속 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`를 반환하며, 기존 명시적 전력/열 가정 profile의 탐색 결과와 섞지 않는다. 이번 데이터의 10~20초 블록은 기존 1초 안팎 요청이나 큐 대기·callback·임의 병행 상태를 식별하지 못한다. 따라서 실측 기반 **동적 정책 에너지·AP 예측 시뮬레이터의 검증 완료는 불가능**하며 `experiment_ready=false`다.

다음 한 작업은 **현재 기록에서 실제 짧은 작업의 상태 분해능과 모형 선택에 필요한 시간 척도를 PC에서 고정하고, 그 척도에 맞는 단일 도착/전환 확인 입력을 설계**하는 것이다. 이때 기존 AP 약2.65초 cadence보다 짧은 상태를 개별 계수로 주장하지 않아야 한다. 새 실측은 계획·분모·센서 coverage·시작 AP 지원 gate를 먼저 동결한 뒤에만 의미가 있다. 지금 세션이 하한에서 0.2°C 벗어났다는 이유로 즉석 냉각/가열·재측정을 반복하지 않는다. 완료되지 않은 CG_DC·CC_DG 정식 동일 프로토콜 확인과 독립 세션 변동성도 그대로 남는다.

## 재현·검증

```powershell
python -B -m tools.d1_energy_short_transition_report --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_run_v1 --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_plan_v1/collection_plan.json --frozen C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_reproduce_NEW
python -B -m unittest tools.test_d1_energy_ap_short_transition tools.test_d1_energy_ap_autonomous_diag tools.test_d1_energy_state_collection -q
```

기존 결과·원본·FAIL·동결 계수는 덮어쓰지 않는다. 공유 결과는 작은 JSON/CSV/PNG/SVG/HTML이며 APK·모델·키·원시 journal은 Git 밖에 둔다.

검증 대상은 착수 HEAD `597d3bff08dfb42fc3f13e7acd395911d99ee537`와 이번 미커밋 변경이다. `EnergyStateCalibrationTest` 대상 Android 테스트, host 관련 19건(1건은 현 환경 비적용 건너뜀) 통과. 새 보고기는 원본 manifest/progress/thermal 및 동결 파일 해시, 공통창 적분과 CSV/그림 입력 일치를 검사한 뒤 생성했다. Edge headless로 로컬 HTML을 실제 렌더해 한글·경고·범례·곡선과 표 배치를 확인했다. 이는 플랫폼의 에너지 절대 정확도나 장시간 임의 도착 예측 검증이 아니다.
