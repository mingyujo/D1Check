# 이력 통제 캠페인 v2 실행 결과 — 2026-10-08

**첫 개발 세션의 host listing timeout으로 중단. 적격 개발0/6·확인0/6, 후보 동결0, 보완 실행0.** 재생·모형 실패로 판정하지 않는다. 지정 v2 캠페인은 소비·종료됐으며 `stopped_no_resume`로 보존한다. [작은 요약](results/history_control_plan_01/run_v2/summary.json) · [원본 판독/그림](results/history_control_plan_01/run_v2/README.md).

## 승인·동일성·현재 기기

사용자 “그럼 이제 준비 완료됐어 진행하자”로 [v2 계약](ENERGY_AP_HISTORY_RECOVERY_PC_20261008.md)의 실측·분석·문서·Git 범위를 승인했다. 기준 HEAD `a081d55e9cc9d1a732bee9bed9e1ca8535244b29`에서 PC Check·미소비·source/APK/model 바인딩을 확인하고 Run을 단1회 호출했다. 이번 실행 소스는 수정하지 않았다. 현재 A24 하드웨어·fingerprint·설치 전 배터리/비충전/BAT/thermal/화면/메모리 확인은 실행기 원본 preflight/환경 기록에 있다. 지정 IP transport만 사용하고 다른 연결은 해제하지 않았다. 식별 원문은 외부 원본에만 보존한다.

- 캠페인 SHA `7daa7326c419a8bc9c851c9ac3d701c48ede8a08735876f6dea7607d8a313ace`, child `2e25aa64d908cde413fc0b5f8b989458551ff501806b5f62188f7d436b662620`.
- APK SHA `3840bfb161b038ae61f34cd4215f8fe88bc511ec4e5f87cccc3b58e02c8768be`. 현재 설치본이 달라 전송1·데이터 보존 설치1, 설치 후 exact hash 확인. APK 재빌드0.
- 실제 AP 모형/activity model SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2` 불변. 별도 원 collection model snapshot SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`도 plan의 기대 hash와 일치한다. 두 파일을 혼동하지 않는다.

## 진행·중단 경계

|원본 사건|clock/시각 또는 경계|판독|
|---|---|---|
|부모 캠페인 claim|host monotonic 기준0초|새 계획 단1회, 부모31444/child14436 식별·소유권 기록|
|설치본 검증|설치 단계65.719초|전송/설치 각각1, hash 검증 완료|
|Activity 시작·runtime/warmup|Android monotonic 별도 clock|onCreate1, runtime4·warmup8 start/return 확인|
|resident baseline|Android monotonic conditioning origin 약−31.31→−1.26초|baseline30.049초|
|host numeric AP 승인|원 host bracket에서 AP28.3°C|numeric-ap-observe-v2로 승인, 개발32.5–34.0°C 밖|
|conditioning common|Android start519255047243087ns, 계획 끝519375047243087ns|등록120초, 실제 boundary120.070231392초, 요청96의 terminal/해제 기록|
|회복 시작|Android519375158000018ns|회복30초 중 가장 마지막 durable event|
|직전 listing0603/0604|host UTC17:44:33.333/33.716|0.125/0.156초 정상 반환|
|listing0605 timeout|host UTC17:44:34.147482→17:44:37.142686|3초 제한, stdout/stderr0, client exit1/root_reaped=true|
|부분 증거 회수0606–0615|host UTC17:44:39.193 이후|동일 transport 정상 반환, 원 manifest/progress/conditioning 경계 회수|
|세션 host force-stop0616|host UTC17:44:42.325727→42.485365|실패 뒤 대상 패키지만1회|
|프로세스 부재0617|host UTC17:44:42.509443→42.669078|원 ps 출력에서 대상 프로세스 부재 확인|
|trace 종료·회수|원 host 명령0619–0622|소유 trace stop/pull1, 약14.25MB 부분 trace|
|child/parent 종료|child248.625초, campaign251.720초|실제 process 부재 PC 확인, 도구 wait 완료와 구분|

UTC는 2026-10-07, KST는2026-10-08이다. Android ns와 host monotonic/UTC는 다른 clock이다. 동시 관측 AP bracket은 원 `thermal.jsonl`의 before/after Android uptime와 host 기록으로 연결되며 약0.1초 단위 uptime 및 명령 왕복 불확실성이 있다. 표/그림의 두 origin을 임의로 합쳐 정확한 사건 인과를 주장하지 않는다.

## 원인·회수·cleanup 판정

직접 중단 원인은 `run-as <대상 package> ls files/<protocol>/<session>`의 **3초 제한 도달**이다. 내부 지연 원인은 미확정이다. client는 종료·reap됐고 공유 ADB daemon은 건드리지 않았다. stdout/stderr가 비었고 직후 같은 endpoint의 회수·cleanup 명령이 정상 반환했다. `error: closed`/device-not-found는 이번 timeout에 없다. 따라서 연결 소실·mDNS 결함·두 transport 충돌·기기 과부하·GPU/app 결함을 확정하지 않는다.

20분 대기 경로는 사전 계약상 명시적인 연결 실패 증거가 있을 때만 적용한다. 이번 무출력 timeout은 해당 증거가 아니므로 대기0회다. 앱 `session_failure.json`이 존재하지 않아 원인 재현 앱 결함 요건도 충족하지 못했으며 보완 실행0회다. 무출력 timeout의 재시도나 즉석 gate/timeout 변경을 하지 않았다.

원 prefix에는 onCreate1만 있고 lifecycle_cancelled/onDestroy/app failure가 없다. 이후 callback의 미회수와 “발생하지 않음”은 다르다. 앱 cleanup·target requests/history boundary 등은 당시 아직 생성되지 않아 non-JSON 반환 원문과 별도 회수 오류 파일을 보존했다. host 실패를 앱 자체 실패로 바꾸지 않는다.

원 session host cleanup은 completed·force-stop1·프로세스 부재 확인이다. 설치 단계 cleanup과 세션 실패 cleanup은 다른 목적이며 각각 수행했다. 앱 자체 정상 cleanup은 미회수/미확인이다. trace는 원 host가 종료해 회수했으나 완료 target common window가 없어 full-window content audit은 부적격이다. 마지막 원 host AP28.5/BAT28.2°C/thermal0. 이후 기기 조회를 추가하지 않았다.

## 실제 소비

|항목|승인 캠페인 상한|기록된 실제|
|---|---:|---:|
|세션 시도|13|1, 적격0|
|runtime|52|시작4/반환4|
|warmup|104|시작8/반환8|
|본 요청(conditioning 포함)|2,016|conditioning96 시작/반환/output_ready/persist/worker_release/lane_available 각96|
|명시적 추론|2,120|durable 시작104·반환104|
|staging|13회·91파일|1회·7파일|
|설치본 pull/APK push/설치|각2|각1|
|trace host pull|13|1|
|ADB|99,240|623명령, 외부 중복 조회0|
|전체|21,600초|campaign251.720초(약4분12초),child248.625초|
|연결 대기/사후 회수|20조회/20명령·각1경로|0/0|
|보완 실행|1|0|

첫 조건은C0여서 예정 target 요청 자체가0이다. 목표 target 관측창은 미진입이며 conditioning 창과 구분한다. 후속 개발5·확인6은 모두 미시도, 정상 원12세션 분모와 중단을 유지한다. 마지막 durable prefix 밖의 호출/상태는 무조건0으로 확정하지 않는다. 원 소비 receipt는 추가 summary로 덮지 않았다.

## 조회 구조·자료 적격성·모형 판독

총623 중 session listing324(52.0%)·thermal63·clock bracket122. listing 정상 반환323의 중앙값0.094초/P950.188초/최대0.421초, timeout1은 지연3초 확정값이 아니라 제한에 걸린 censored 관측이다. listing 누적 client 대기39.621초(그중 timeout3초). 모든 명령의 반환 대기137.086초+timeout 제한3초=140.086초이며 기기 CPU/에너지 비용으로 해석하지 않는다. 원 명령 시간상 실행 중첩0쌍. [용도별 CSV](results/history_control_plan_01/run_v2/command_delays.csv). 정상 nonzero 반환(존재 여부 probe 등)은 timeout/앱 실패와 분리한다.

반복 listing은 현재 code의 약0.25초 sleep과 command 대기 기반 상태 감시다. 이번 하나의 timeout만으로 조회 수가 내부 원인이라고 단정할 수 없다. 승인 이후에도 listing 한 번의 실패가 앱 세션을 host 정리로 끝내는 구조가 실제 발동했다. 이를 해결하려면 “진행 관찰 미확인”과 “필수 numeric 환경 감시 실패”를 구분한 PC 변경 검증이 먼저 필요하다. 이번 소비 계획의 규칙을 사후 바꿔 재실행하지 않는다.

179개 power 표본과 conditioning 요청96·120초 boundary는 부분 원자료로 재사용 가능하다. 다만 마지막 power sample은 conditioning 계획끝보다0.429156초 전이고 target/window/cooling/앱 종료 자료가 없어 전체 target120초J/AP 평가·candidate g 추정·독립 확인은 **null/미완료**다. 누락을0으로 채우거나 창끝을 임의 외삽하지 않았다. runtime/품질 gate 통과는 입력 준비 근거이고 전체 요청 결과 artifact를 모두 회수한 품질 확인과 구분한다. 단독 CPU conditioning을 진행했으며 PAR 병행·target 유휴반응은 확인하지 못했다.

실제 일정 조건부 예측 A와 도착부터의 종단간 예측 B 어느 쪽도 이번 자료로 새로운 정확도 결과를 만들지 않는다. 시뮬레이터 기본·동결모형·strict·experiment_ready=false를 유지한다. 완성된 실측–예측 비교 그림 대신 실행 경계만 그렸다.

## 재현·검증

외부 원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_run_v2`의 claim·primary_campaign_receipt·primary/FINAL_RECEIPT·frozen plan·registry·host command 원문·session failure_prefix·thermal·trace. 원본은 변경하지 않는다. 상세 의존 파일/재현은 [README](results/history_control_plan_01/run_v2/README.md).

- 판독기 검증: 원623명령/receipt 일치, 96요청 terminal·6경계 count 일치, 원모형2개 hash 확인, host ps/cleanup 근거 확인, timeout을 censored로 분리, host/app clock을 별도 축에 유지.
- 원본 필수파일 hash 불변·공유 summary/CSV 재현 일치·PNG/SVG 렌더 확인. Run 단계 소스/timeout/gate 변경0, 추가 Android 빌드0, 완료한 전체 테스트 반복0. PC 프로세스 부재 확인 후 추가 기기 명령0.
- 결과 화면에 stopped/partial/null을 표시한다. 전송·설치·conditioning 성공을 적격 개발 완료나 모형 개선으로 표현하지 않는다.

**다음 PC 작업 하나:** 승인 이후의 반복 listing을 필수 환경 감시와 분리할 수 있는지 실제 `poll()` 진입 fixture에서 검증한다. 원인을 모르는 앱 수정·재실측으로 대체하지 않는다. 새 실행 계획/claim은 이번에 만들지 않는다.
