# AP 배경 변화와 부하 시점의 통합 대조 — 실행 전 고정

2026-10-02 · [준비 화면](index.html) · [계획 요약·해시](plan_summary.json) · [분석 계약](analysis_contract.json) · [PC 검증](verification.json)

**PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED.** 기존 자료만으로 구분되지 않은 ‘준비 후 배경 변화인가, 등록 부하에 따라 이동하는 반응인가’를 한 묶음에서 확인하도록 준비했다. 이번에는 Run·ADB·설치·추론·실측·소비 claim이 없다. 기존 완료/중단 계획을 재개하지 않는다. 기존 β/k 사후 후보는 미채택이며 동결 모형·준비 이력 후보·strict/default/experiment_ready=false를 유지한다.

## 선택한 한 가지 설계

| 순서 | 조건 | 본 요청 | 목적 |
|---:|---|---:|---|
| 1 | C: 무부하 | 0 | 앞쪽 준비·resident 배경 |
| 2 | L35: +35초 허용 | 24 | 이른 등록 부하 반응 |
| 3 | L65: +65초 허용 | 24 | 같은 부하의 30초 시점 이동 |
| 4 | L65: +65초 허용 | 24 | 역순 위치의 같은 조건 |
| 5 | L35: +35초 허용 | 24 | 역순 위치의 같은 조건 |
| 6 | C: 무부하 | 0 | 뒤쪽 준비·resident 배경 |

세 조건×앞뒤 두 위치의 6세션이다. 각 조건의 평균 실행 순번은3.5로 같아서 **순번에 선형인 변화항**은 조건 평균 차이에서 산술적으로 상쇄된다. 이 목적을 세 조건1회씩의3세션으로 달성할 수 없어서6세션을 선택했다. 모든 가능한 설계의 절대 최소·통계적 검정력 보장은 아니다. 실제 경과시간의 비선형 변화·carryover·주변 조건을 제거하거나 순서를 무작위화한 인과 실험이라고 하지 않는다. 세션 사이90초 자연 대기는 열 상태 초기화의 증명이 아니다.

같은74e 서명 APK·네 runtime·각2warmup·resident·입력·화면·계측을 사용한다. C도 준비8warmup은 수행하며 ‘추론을 전혀 하지 않은 폰’이 아니다. L은 기존 burst·seed201 CG_DC 24요청의 도착0–4.840초/backend를 보존한다. +35 실행 허용은35.000300–46.260403초, +65는65.000300–76.260403초다. 실제 처리시간/lane 점유는 기기 결과이며 간섭계수1.5·추가 sleep·가열로 맞추지 않는다.

세션마다 baseline30＋common120＋cooling60=210초로, 공통 원점150–175초의 기존 후기 질문을 포함한다. 기존 AP 간격 약2–3초에 비해 시점 차이30초는 판독할 수 있는 규모다. 짧은 병행의 별도 전력 계수·개별 요청 전력까지 식별하는 입력은 아니다. 완료·실패·누락 분모와 실제 dispatch→lane_available를 모두 보존한다.

## 자료 역할과 무엇이 끝나는가

**신규 계수 개발0/신규 모형 독립 확인0/구조 판별6세션**이다. 변경 없는 준비 이력 후보의 새 조건부 평가도 함께 수행한다. 기존 후보가 τ30/γ0으로 두 새 세션에서 확인됐다는 근거는 보존하되, 이번 자료가 새로운 수정 모형의 독립 확인인 것처럼 쓰지 않는다. 이후 이 자료로 구조·계수를 정하면 개발 자료로 표시하고 별도 미관측 확인이 남는다. 지금 식별되지 않은 새 수식을 임의로 정해 실행 중 적합하는 단계는 넣지 않았다.

모든 조건은 **baseline 시작 이후부터 공통창+35초 전까지 전체 조회 괄호가 들어오는 AP만**으로 E/H를 초기화한다. ≥55초/≥15표본/공백≤10초와 기존 수치 식별 검사를 유지한다. L65의 추가 대기 중 온도를 예측 입력으로 주지 않는다. 마지막 초기화 구간(+35초 전) 표본을 T로 쓰고 이후 실제 일정으로 연속 전파한다. E는 주변 온도가 아니며 H는 내부 온도 관측이 아니다. 무부하에도 가짜 작업 시작이나 lane 해제를 만들지 않는다.

새 분석은 +35초 이후→실제 냉각 종료의 유효 AP 표본을 공통 원점으로 비교한다(≥20개, 처음/끝 미관측≤10초·중간 공백≤10초). 이전 +65 확인은 첫 부하 이후의 별도 창/더 긴 초기화 입력을 썼으므로 그 결과와 같은 오차 분모로 합치지 않는다. 실제 lane 일정 조건부이며 온라인·도착부터의 종단간 예측이 아니다.

| 판독 층위 | 고정 처리·종료 기준 |
|---|---|
| 실행·자료 적격성 | 기존 기기/앱/품질/시간 gate 및 AP 초기화·전체 관측 적격성. 첫 실패에 전 계획 중단, 완료 부분과 원래/후속 오류 보존 |
| AP 오차 | 절대 AP/초기 anchor 대비 변화·부호 잔차·MAE·최대·최고 차이. work span/부하 전 대기/부하 후 유휴를 분리하고 정확한 창/표본 수 기록 |
| 배경 대 부하 반응 | 고정90–115/120–145/150–175초 변화, 실제 last_lane 이후0–25/25–50/50–75초 변화, 관측 표본 최고 시각. 최고점을 맞춰 시간을 이동하지 않음 |
| 조건 대조 | C/L35/L65 각각 두 원값과 평균 차이. 필수 arm/endpoint가 없으면 전체 대비null. 측정 C를 L 예측에 넣거나 인과 효과로 차감하지 않음 |
| 전력 | 원래 common120초 J와 상태를 함께 보존. raw=mA 조건부, 절대 인증·짧은 병행 전력 검증 아님 |
| 정확도·정책 | 허용오차 근거가 없어 accuracy_pass=null. 오차가 불리해도 적격한 다음 arm을 생략하지 않음. 열 정책 우월성·strict 확대 없음 |

**완료점은6조건 기록과 사전 판독 산출 또는 첫 실패의 부분 종료다.** 전·후 C의 변화, 시점 이동에 따른 반응, 같은 조건 두 관측이 서로 일치하지 않아 구분할 수 없으면 ‘미식별’로 종료한다. AP0.1°C 양자화나 표본 최고시각 차이를 통계적 유의성으로 바꾸지 않는다. 결과를 보고 후보·창·기준을 바꾸거나7번째 세션을 추가하지 않는다. 이 계획만으로 일반 열 모형 완성을 보장하지 않는다.

## 실제 실행 경로와 정확한 예산

기존 `d1_arrival_energy_collection_device.run`에 새 opt-in 계획 검증/AP 자료 검증 분기만 연결했다. 기존 resident0/24 manifest와 bundle의 설치 없는 실행·선택 transport 고정·소유권/checkpoint·회수·정리 경로를 재사용한다. Android·lifecycle·센서·APK 변경0이다. 공유 소비 판독의 본 요청 분모를 entry.requests로 읽게 해 C0이24로 표시되지 않도록 수정했다. 기존24요청 경로는 동일하다.

| 항목 | 상한 |
|---|---:|
| 세션 | 6 (C2/L35×2/L65×2) |
| runtime / warmup / 별도 적격성 | 24 / 48 / 0 (warmup 출력 품질 검사) |
| 본 요청 / 총 명시적 추론 | 96 / **144** |
| staging | 6회·42파일 |
| 설치본 host pull / APK push / 설치 | 1 / 0 / 0 |
| 고정 관측 | 6×210=1,260초(21분) |
| 세션 사이 수동 유휴 | 5×90=450초 |
| preflight | 600초; installation_seconds와 installed_preflight_seconds는 같은 예약, 중복 합산 아님 |
| 각 세션 | stage/gate120＋poll485＋회수50＋cleanup45=700초 |
| 전체 상한 | **600＋6×700＋5×90=5,250초(87분30초)** |
| ADB | **6×3,200＋200=19,400명령** |
| 재시도 / 대체 / 추가 | 0 / 0 / 0 |

poll485초 안에서 listing0.25초 간격≤1,940명령(각3초timeout), HAL AP2초 간격의uptime/thermal/uptime≤729명령(각2초), 화면10초 간격≤49명령(각2초)으로 관측 상한2,718/세션이다. 3,200과의 차이는 staging/품질/승인/회수·cleanup 여유이며, 기존 누적 단계 ceiling과 마지막100명령 예약 검사를 유지한다. 총 상한은 preflight 여유200을 더한 보수적 한도다. 조회 자체의 시간 때문에 통상 이 수에 도달하지 않는다. 새 polling·timeout 연장·자동 reconnect는 없다.

기존 두 확인의 실제581.797초(preflight22.072초, 사이 대기90초)를 같은 단계 길이로 환산하면 약1,881초(31분21초)다. **새 6세션 예상 보장값이 아니라 참고 계산**이다. 상한87분30초를 정상 예상시간이나 완주 보장으로 사용하지 않는다. 다음 세션700초+필요한90초 예약이 없으면 시작하지 않는다. 앱 watchdog480초·drain30초·시작 AP 승인대기30초는 기존 poll 예산 내부의 한도이며 더하지 않는다.

Run 때 현재 A24/단일 online transport·fingerprint·설치본 SHA/서명/패키지를 내부 절차로 확인한다. 후보 불일치면 설치 fallback 없이 중단한다. 배터리≥20%·비충전·BAT≤35°C·thermal0·메모리·8warmup 품질/GPU 증거·화면밝기81/자동밝기0/timeout18,000,000ms/Awake/interactive는 기존 계약 그대로다. numeric AP의 유효성/조회 신선도는 필수이며 개발 하한32.5°C를 실행 gate로 되살리지 않는다. 초기 AP의 개발 범위 안/밖과 짧은 전환의 strict 미지원은 별개로 표시한다. 주변 온도는 실제 기록하지 않으면 unknown이다.

연결·lifecycle·기기 실패 시 원 소유자의 기존 회수/cleanup만 수행하고 새 실행·무한 대기·재연결·다른 앱 종료를 하지 않는다. 앱 cleanup/host force-stop/프로세스 부재는 구분한다. 강제 host/PC 종료까지 finally가 보장하지 않으며 기존 checkpoint·원문과 미확인 상태를 남긴다.

## 동결 계획과 명령

- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_background_contrast_plan_v1/collection_plan.json`
- SHA-256: `acfa2510316700e04d02312fa98c72ab43fd844ab03d8851b6de212a0af44be0`
- 재사용 APK: 외부 `recorded_policy_compare_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, SHA `74e8065d10bdfac01c4fbda77afeac196986501b9534bf02d1dd5b0ad541ee6e`.
- 패키지 `com.example.d1check.benchmarkrunner.modelprobe`/versionCode1/프로젝트 인증서 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`를 PC 도구로 확인. 현재 설치본은 조회하지 않았다.
- 동결 후보 `d885b87c…c1466`, 정확한 후보/계약/소스/manifest 해시는 plan_summary.json과 frozen_source_hashes.json. 실제 출력 `energy_ap_background_contrast_run_v1`, registry `ap_background_registry/ENERGY-AP-BACKGROUND-CONTRAST-01`은 **둘 다 존재하지 않는다**.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_background_contrast_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
# 위 새 계획의 실행 승인 이후에만 한 번:
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_background_contrast_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 'acfa2510316700e04d02312fa98c72ab43fd844ab03d8851b6de212a0af44be0'
# 실행 종료 후, 새로운 PC 출력 폴더에 판독:
python -B -m tools.d1_ap_background_contrast_readout --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_background_contrast_plan_v1/collection_plan.json' --output output/ap_background_contrast
```

## PC 검증과 남은 범위

관련13테스트(새7/기존 memory6) 통과. 실제 공용 Run 함수에 가짜 Device를 주입해 정상6세션, AP 부적격·poll timeout·회수/cleanup 단독·연속 실패·시간 예약 부족·설치본 부적격을 검사했다. 원래 오류/receipt를 보존하고 최초 정리 이후 중복 force-stop이나 추가 세션이 없음을 확인했다. 소비된 계획은 검사 전 차단한다. 실제 기기 안정성 검증은 아니다.

실제 PowerShell→Python Check 통과, 별도 Popen 감시 Check에서 실행된 PC 도구는 java/aapt2뿐이며 ADB 실행을 차단했다. 기존 C·+35·+65 원문3세션을 **복사·명시적으로 fixture 처리**해6개 판독 슬롯을 검사했다. 정상·AP 결측·부분 실패 및 실제 판독 CLI 통과, 원본24파일 hash 불변. 복제 자료는6독립 세션이 아니며 결과 그림을 새 실측 화면에 공유하지 않는다. 초기 AP 범위 표시 추가 후 최종 정상 fixture/CLI도 다시 확인했다.

```powershell
python -B -m unittest tools.test_d1_ap_background_contrast tools.test_d1_ap_memory_confirmation -v
python -B docs/results/ap_background_contrast_01/pc_fixture.py --archive '<외부 원자료 루트>' --output output/background_fixture --mode complete
```

**다음 행동 하나:** 이 미승인 통합 계획을 실행할 때 현재 기기 gate와 위 예산을 적용한다. 이번 PC 준비는 완료했지만 아직 어떤 새로운 실측 결과나 모형 정확도도 추가되지 않았다.
