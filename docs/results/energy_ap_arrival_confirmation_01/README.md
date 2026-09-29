# 최소 도착 확인 입력: PC 고정, 실행 차단

[`input_manifest.json`](input_manifest.json) · [24요청 CSV](requests.csv) · [센서 해상도 요약](sensor_screen.json) · [판정 보고서](../../ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md)

기존 Android `queue` 생성 규칙으로 예정 도착 0–4.6초(200ms 간격), 긴급 분류6·일반 탐지18, 연구용 요청별 기한1.5/6초를 고정했다. 정책은 `FIXED_SPLIT`, 공통창은120초, 분모는 예정24요청 전체다. 도착은 앞 요청의 완료와 독립적이다. seed201은 기존 PC 상태 길이 화면에만 적용되고 Android 도착 난수는 없다. 이 하나의 입력은 짧은 단독/대기/유휴 전환의 전체창 예측 질문을 위한 것이며, 기존 PC 일정의 병행 점유가 0초라 병행 계수는 확인하지 못한다.

별도 A24 단기 전환 원본의 공통창 전류 표본600개(간격 중앙1.000초·최대1.093초), AP229개(중앙2.630초·최대3.525초), 작업 lane 점유 중앙0.163초·최대1.209초다. 6개 병행 블록의 실제 공동 lane 점유는 각각12.908–13.352초였지만 블록 비용/경로만 점검 가능하다. 표본 조회 주기는 센서 내부 갱신 주기의 증명이 아니며 요청별 전력은 식별되지 않는다. 원본 SHA는 센서 요약에 있다.

동결 파일 SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`의 **시작 AP 개발 범위는 32.5–34.0°C**이고 32.5–39.5°C는 세션 전체 관측 범위다. HAL numeric AP `mName=AP,mType=0`의 마지막 3초 이내 표본을 검사하는 코드는 사후 증거 화면이다. 기존 앱은 부하 시작에서 AP를 읽거나 중단하지 않으므로 실행 gate가 아니다. 과거 32.3°C는 범위 밖이며 동결식 외삽을 검증 오차로 바꾸지 않는다. 현재 `Check`는 `PC_INPUT_FIXED_RUN_BLOCKED`; Run/registry/승인 예산은 없다.

A는 실제 실행 일정·초기 AP를 입력으로 공통창 J와 AP 경로를 예측하는 **조건부** 질문이다. B는 예정 도착·사전 동결 처리시간으로 일정/응답/비용을 예측하는 **종단간** 질문이다. 이후 실측 전류/AP나 실제 완료시각을 예측 입력으로 넣지 않는다. 두 질문 모두 이번 번들에서는 수치 검증 결과가 아니다. frozen strict는 임의 도착 전환을 지원하지 않는다. 누락 구간은 0으로 채우지 않고 unsupported로 표시한다. A24 raw 전류=mA는 조건부 해석이며 절대 J 정확도는 미인증이다.

저장소 루트에서 기기 명령 없는 공유 번들 확인:

```powershell
python -B -m tools.d1_energy_ap_arrival_confirmation check --manifest docs/results/energy_ap_arrival_confirmation_01/input_manifest.json
python -B -m unittest tools.test_d1_energy_ap_arrival_confirmation -v
```

원본 감사 재생성은 **새 디렉터리**로 한다:

```powershell
python -B -m tools.d1_energy_ap_arrival_confirmation prepare --frozen C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_run_v1 --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_arrival_confirmation_reproduce_NEW
```

원본 감사에는 외부 `00_*/artifacts/progress.jsonl`·`00_*/thermal.jsonl`이 필요하다. 공유 번들 Check에는 필요 없다. APK·모델·원자료·키는 포함하지 않는다.
