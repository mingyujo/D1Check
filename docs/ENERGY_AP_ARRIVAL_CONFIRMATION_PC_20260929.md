# 동결 에너지·AP 모형의 최소 도착 확인 설계와 실행 차단

**판정:** PC 입력·시작 AP 사후 판독·원본 센서 해상도 감사는 완료했다. **현재 APK와 host 경로로는 부하 시작 시 numeric AP 적격성을 집행할 수 없어 기기 실행 계획은 아직 만들 수 없다.** 기존 준비 gate를 통과한 뒤 resident baseline 동안 AP가 변하며, 앱은 baseline 뒤 host 승인 없이 load를 시작한다. 새 host 실시간 handshake를 넣어 과거 연결 의존을 다시 늘리거나, thermal status를 numeric AP 대신 쓰거나, 모형 범위를 넓히지 않았다. [입력·해시·PC 명령](results/energy_ap_arrival_confirmation_01/README.md) · [기존 진단과 범위 밖 +23.280J의 정확한 의미](ENERGY_AP_SHORT_TRANSITION_DIAG01_20260929.md).

| 근거 항목 | 고정 사실과 한계 |
|---|---|
| 동결 파일 | COLLECT-05 개발 3세션 `development_freeze.json`, SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`; `energy-ap-state-regimen-fit-v1`, 8개 상태의 기기 전체 W, AP 1차식. 변경 0. |
| 구성·지원 | A24, EfficientNet-Lite0 분류/EfficientDet-Lite0 탐지, 입력·CPU 1 thread·4 resident runtime의 기존 manifest 동일성 필요. 단독 분류/탐지 CPU/GPU, CC_DG·CG_DC·DC_DG, resident idle의 **계수 값은 존재**하지만 동결 검증 경로는 기록된 600초 상태 블록 일정으로 제한. 임의 도착 strict는 unsupported. 분류 CPU＋탐지 GPU를 반대 배정과 합치지 않음. |
| AP 범위 | `initial_ap_development_range_c=[32.5,34.0]`은 실제 개발 시작점; `ap_development_observed_range_c=[32.5,39.5]`는 전체 경로. 물리 한도 아님. 기존 `evaluate`의 범위 검사는 후자를 쓰므로 새 **사전 시작 gate 계약**에 전자를 사용. 32.3°C 진단은 양쪽 하한 밖이고 확인 표본 아님. |
| 센서/요청 | 단기 전환 원본 공통창 전류 600개, 1.000초 중앙·1.093초 최대 간격; numeric AP 229개, 2.630초 중앙·3.525초 최대; 단일 호출 lane 점유 중앙 0.163초·최대 1.209초. host AP 조회 간격은 하드웨어 내부 갱신 간격의 증명이 아님. 개별 호출 J는 식별 불가. 6개 pair 블록의 12.908–13.352초 공동 lane 점유는 블록 비용/경로 점검 수준. |
| 진단 산술 | 실제 전체 공통창 600.094초·903.842J. 상태 매핑 600.056초의 관측903.793J·동결식 대입927.073J의 **+23.280J는 범위 밖 탐색 외삽**. 제외 0.0376초·0.049J를 0으로 처리하지 않았고 전체창 검증 오차로 보고하지 않음. |
| 선택 입력 | 기존 queue 24요청, `FIXED_SPLIT`, 200ms 간격 0–4.6초, urgent6/normal18, 연구 기한 1.5/6초, 공통창120초. 기존 seed201 PC 화면은 정책 결과가 아닌 **상태 길이 화면**으로만 사용. 그 일정은 CC_DG 공동 점유 0초·단독 최대1.145초여서 병행 계수 또는 요청별 전력의 적격성 검사는 불가. |

## 예측과 판독 경계

A(조건부): 같은 세션에서 확인한 실제 도착/dispatch/worker release/lane_available로 상태 경계를 만들고, 관측 시작 AP **한 값**을 초기조건으로 둔다. 동결 상태별 전체 W를 공통 120초에 중복 없이 적분하고 AP 경로를 잔열 연속으로 예측한다. 실제 공통창 J/누적 경로, AP MAE·최대절대·최고·기존 연구용 한도 초과시간과 비교한다. 실제 출력/저장/worker/lane 경계가 없는 부분은 계산 불가로 남긴다. 1초·2.63초 표본보다 짧은 상태의 개별 오차를 주장하지 않는다.

B(종단간): 같은 24개 예정 도착·고정 배정과 **사전 동결된** 처리시간 추정만으로 일정을 만들고, 예정 24개 전체의 완료·실패·미완료 및 긴급 output_ready/일반 persist_complete 응답·기한 위반과 A의 에너지/AP 지표를 비교한다. 실제 미래 완료시각·전류·AP를 입력으로 사용하면 B가 아니다. 현재 PC 시뮬레이터는 이런 연구용 일정을 만들지만 설치된 새 APK의 시간/host callback 오차를 별도로 확인하지 못했고, 동결 에너지 strict는 임의 전환을 차단한다. 따라서 B는 **설계된 확인 질문**이지 아직 검증 가능한 수치 출력이 아니다. 24요청을 길게 만든 블록 진단과도 다르다.

자료 적격성은 시작 AP 범위·시각/센서 공백·상태 매핑·공통창 포함·예정 요청 전체 분모를 먼저 검사한다. 적격해도 예측 정확도 PASS가 자동으로 나오지 않는다. 오차의 부호·크기·구간별 상쇄와 정책 간 차이를 함께 보고하며 임의 허용오차는 만들지 않는다. 온도에 따른 처리시간 감속, BAT 온도, 잔량/사용시간, 절대 J 정확도는 범위 밖이다. 시작 뒤 AP가 개발 경로 범위를 벗어나면 이후 AP 예측은 그 시각부터 unsupported로 표기해야 한다. 에너지 상태가 별도 지원 가능해도 같은 구간이 완전 계측됐을 때만 J를 독립 보고한다. 과거 판정은 바꾸지 않는다.

## 시작 gate와 실행 준비 판정

기존 `ArrivalEnergyActivity.gate()`는 warmup 후에만 호출된다. `resident_baseline` 30초 후 `commonStart=now()`로 바로 load에 진입한다. host `d1_arrival_energy_collection_device.poll()`은 AP를 약 2초마다 기록하지만 baseline 뒤 시작을 보류시키지 않는다. 기기 자체 `EnergyCollectionActivity` 진단도 numeric AP를 앱에서 읽지 못해 host 준비 후 120초 baseline과 실제 load 시작 사이의 AP 하한을 보장하지 못했다. 직전 세션의 32.3°C가 실제 사례다. 새 자료 화면의 마지막 3초 이내 표본 검사는 **사후 판독**이며 실시간 차단이 아니다. 시작까지의 드리프트·0.1°C 양자화로 경계 근처를 보증할 수 없다.

따라서 `input_manifest.json`은 계획 ID를 가진 **PC 고정 입력**이나 `session_budget=0`, `device_command_budget=0`, `Run` 없음, `PC_INPUT_FIXED_RUN_BLOCKED`다. 단일 세션 후보라도 현재 지원 밖인 병행 상태 계수를 확인한다고 속일 수 없고, 설치 APK 소스도 옛 12세션 계획과 일치하지 않는다. 정확한 작업/ADB/설치/전체 시간 예산이나 승인 후 명령을 이 상태에서 확정하지 않았다. 실행 가능 계획으로 바꾸려면 먼저 **부하 시작 경계에서 numeric AP를 읽고 적격하지 않으면 작업 0회로 종료하는 기기/host 연결을 PC에서 검증**해야 한다. 한 번의 제한된 시작 판정과 실패 종료를 설계해야 하며 기존 실시간 반복 handshake를 무심코 재도입해서는 안 된다. 그 변경의 APK·관측 부하·동결 모형 전이 비교 영향과 호출/시간 상한을 확인한 뒤에만 별도 미승인 실행 계획을 발행한다. 이 단계는 이번에 임의 구현하지 않았다.

이번 검증은 `python -B -m unittest tools.test_d1_energy_ap_arrival_confirmation -v`, `python -B -m tools.d1_energy_ap_arrival_confirmation check --manifest docs/results/energy_ap_arrival_confirmation_01/input_manifest.json`, `git diff --check`다. Check는 ADB 0회, 외부 원본을 읽지 않는다. 코드/CSV/JSON 화면은 실측 결과가 아닌 실행 전 설계와 이전 원본의 해상도 감사다.
