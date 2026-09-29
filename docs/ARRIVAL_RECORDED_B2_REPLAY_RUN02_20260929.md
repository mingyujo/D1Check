# 새 lifecycle APK의 B2 기록 일정 재생: 시작 AP gate 중단

**결과: 새 계획 `ENERGY-AP-RECORDED-B2-02`를 1회 실행했고 `stopped_no_resume`로 종료했다.** 시작 AP 승인 직전의 HAL AP는 **28.8°C**로 사전 고정한 32.5–34.0°C 밖이었다. host가 `start_ap.arm`을 보내지 않았고 공식 120초 창과 24개 본 요청은 시작되지 않았다. 따라서 실제 병행, 공통창 에너지·AP, 동결 모형의 예측 오차는 **미산출**이다. 이는 모형 예측 실패가 아니라 입력 적격성 중단이다.

## 계획·계측 계보

- 착수 Git HEAD `fa0ad285a6b926714708917bc7d76cfca11bb23a`, 작업 트리 clean, 실제 원격 HEAD 동일. [원본 B2 재생 계약](ARRIVAL_RECORDED_B2_REPLAY_PC_20260929.md)의 queue/seed201/실현 간섭1.5, 24요청, 배정·release gate, 동결 모형 SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`, numeric AP 32.5–34.0°C와 3초 신선도 규칙을 유지했다. PC 간섭계수 1.5를 기기 감속으로 구현하지 않았다.
- 기존 빌드 산출물의 프로젝트 서명 APK SHA `120ee894a0d91bdb93c57b634bce1f7bd8f1c2cb7d65cf6b14cf1158101d50f5`를 재빌드하지 않았다. 기존 설치본과 달라 계획상 허용된 APK push·데이터 보존 설치 각 1회를 수행한 뒤 패키지·서명·설치본 SHA를 검증했다. 새 APK에는 [lifecycle 관측 보완](ARRIVAL_RECORDED_B2_LIFECYCLE_PC_20260929.md)이 있어 과거 중단 자료와 동일 계측 프로토콜의 완료 세션으로 합치지 않는다. 기록 비용은 미측정이다.
- 별도 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_plan_v4/collection_plan.json` SHA `19ef883a902587182da343c8b0e3cba4be9c574e9744e1fb184d6f2c1c99a507`, manifest SHA `63fbb75c8eb96471357e9c2379139170b5caf8c96adb23f6c2932f4d78d124f8`. 이전 plan_v3·registry·원자료를 재사용하거나 초기화하지 않았다. 계획의 `Check`는 입력·APK·서명·동결 모형·코드·상한을 확인했고 기기 명령 0회다. 관련 PC 테스트 `python -B -m unittest tools.test_d1_arrival_recorded_replay tools.test_d1_arrival_ap_confirmation -v` 12건 PASS. 새 계획을 위한 변경은 ID/출력 경로와 계측 변경 선언뿐이다.

## gate·소비·종료

`start_ap.ready.json`의 앱 단조시각에서 조회 bracket 시작까지 **0.734초**, bracket 길이 **0.190초**였다. 조회의 thermal status는 0, AP는 28.8°C이므로 신선도 문제와 분리해 **범위 하한 미달**로 거절했다. host 조회 기준이며 센서 내부 갱신 시각을 증명하지는 않는다. `start_ap_gate/host_approval.json`과 앱 `start_ap.accepted.json`은 없고 host가 arm을 보내지 않았다. 마지막 회수 progress는 `session_start`, `activity_lifecycle:onCreate`, runtime start/return 각4, warmup start/return 각8, resident baseline 종료, gate 단계의 sampler까지 확인한다. `onPause`·`onStop`·`onDestroy`, `lifecycle_cancelled`, 앱 자체 `cleanup.json`은 기록되지 않았다. 대상 앱은 host의 실패 정리 force-stop으로 종료됐으므로 앱의 정상 cleanup으로 표시하지 않는다.

이전 기기 값을 재사용하지 않았다. 실행 중 마지막 앱 snapshot은 배터리 26%, 비충전, BAT 28.3°C, thermal status 0, 화면 interactive, memory admission `admit`을 기록한다. 이는 시작 AP 28.8°C의 동결 모형 지원 판정을 대신하지 않는다.

수집 중에는 대상 Activity를 유지하는 계약이며 host는 launch 이후 다른 Activity를 여는 명령, 화면·자동 꺼짐·무선 디버깅 설정 변경을 추가하지 않았다. host 화면 snapshot의 interactive 값은 실제 전경 Activity나 사용자 조작 부재의 증거가 아니다. 이번 중단은 lifecycle 사건보다 먼저 AP gate에서 발생했으므로 새 callback 기록의 원인 식별력까지 기기에서 검증한 결과로 보지 않는다.

| 소비 | 실제 | 승인 상한·판독 |
|---|---:|---|
| 세션 | 시도1·완료0 | 최대1, 재시도0 |
| runtime·warmup·본 요청 | 반환4·반환8·시작 기록0 | 최대4·8·24. arm 미발행으로 작업 진입 불가; 미기록 일반 호출을 무조건 0으로 치환하지 않음 |
| 명시적 추론 | 확인 반환8 | 최대32. 적격성 추가0 |
| staging | 1회·7파일 | 최대1회·7파일 |
| APK 확인·전송·설치 | host pull1·APK push1·설치1 | 각각 최대1. staging push7은 APK push와 별도 |
| ADB | 실행기234 + transport 선택1 = **235** | 최대3,200. timeout0; 비정상 exit4는 부재를 기대한 `test -e` 결과 |
| 전체 시간 | **95.906초** | 최대1,300초, 설치 경로42.235초 포함 |
| 실패 정리 | host force-stop·`ps -A` 부재 확인·thermal status0 | host cleanup `completed`; 앱 cleanup 증거 없음 |

원본 `FINAL_RECEIPT.json`은 오류를 `start AP invalid; no arm, no retry`로 보존했고, 실패 prefix의 `progress.jsonl` 94개 유효 record와 무부분행을 보고한다. 원본은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v4`에 그대로 있고 receipt SHA는 `13c26903d4856eefbd05f16e50dedaa0334e06e33b051dd543f635ddb56a2104`다. 기기 transport는 현재 목록에서 1개를 선택해 이후 실행기 명령에 고정했으며 주소·기기 식별값은 공유 결과에서 제외했다. 연결 소실이나 Activity 자체 취소는 이번 기록에 없다. 이로써 이전 `lifecycle_cancelled`의 원인이 해결됐다고 판정할 수 없다.

## 판독 한계와 종료

`tools.d1_arrival_recorded_replay_analysis`를 별도 `analysis_readout` 출력에 적용한 결과 `not_evaluable`, 관측·예측 공통창 J 및 AP 오차 `null`이다. 회수된 `manifest.json`과 일부 prewindow progress만으로 120초 비교를 만들거나 부분 전류를 공통창 J로 표시하지 않았다. 본 요청·병행이 없어 온라인 B2, 종단간 일정, 짧은 상태 전환 지원, 정책 우월성은 미판정이다. 동결 계수·strict 지원 범위·`experiment_ready=false`를 유지한다.

이번 계획·registry는 소비·종료됐으며 다시 실행하지 않는다. **다음 PC 행동 하나:** 기존 개발·확인 및 이번 사전 AP 기록으로 고정 시작 범위 32.5–34.0°C가 현재 비충전 환경에서 도달 가능한 조건인지 판독한다. 결과에 맞춘 즉석 가열·하한 완화나 새 실측 자동 실행은 하지 않는다.

재현(원자료 읽기만, 새 출력 경로 필요):

```powershell
python -B -m tools.d1_arrival_recorded_replay_analysis --session 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v4/00_b7401080-e75a-5db5-b3ba-1f69041f5224' --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' --output '<새 PC 판독 폴더>'
```

[공유 소형 요약](results/energy_ap_recorded_b2_01/run02_summary.json)과 [통합 대시보드](results/arrival_policy_screen_01/dashboard.html)는 구 계획 결과와 이번 gate 중단을 분리한다. 실제 비교 곡선은 만들지 않았다.
