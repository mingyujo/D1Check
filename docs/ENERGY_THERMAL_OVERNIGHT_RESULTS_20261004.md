# 지속 입력 CPU/PAR 실측·동결 예측 완료

2026-10-04 KST. [승인된6시간 계획](ENERGY_THERMAL_OVERNIGHT_PLAN_20261004.md), [PC 준비](results/online_policy_study_01/overnight_sustained_pc_v1/README.md), [결과 화면](results/online_policy_study_01/overnight_sustained_run01/index.html), [공유 재현](results/online_policy_study_01/overnight_sustained_run01/README.md).

**8/8세션·4쌍·1536본 요청을 재시도 없이 완료했다.** 192요청/400ms CPU·PAR의 일정/응답/J/AP 예측, 실측 대조, 지원 제한, 공유 번들을 연결했다. 두 정책 모두 기한을 지켰고 PAR 긴급 응답은 빨랐다. 그러나 에너지 차이 부호가 일관되지 않아 에너지·열의 작은 차이에 의한 정책 우월성은 미판정이다. 이것은 제한된 시뮬레이터 산출물 완료이며 범용 열 모형·절감 입증 완료가 아니다.

## 준비·동결·실행

- 착수 HEAD `81a6ad6df94a5f149a809051f60e0dee8ab004e0`, 당시 clean. 현재 소스 변경 상태에서 테스트·빌드·해시 동결했다. 다른 worktree/master·기존 사용자 변경·옛 원본/FAIL/종료/미소비 계획은 보존했다.
- 별도 opt-in `sustained-confirmation-v1`: 분류urgent96/탐지normal96, common35~111.4초 예정 도착·400ms. 도착은 이전 완료와 독립. 기존96입력 및 generic128cap은 보존하며 새 whitelisted CPU/PAR 확인 입력만192 허용한다. 인위적 감속·추가 sleep·추가 추론·모형 적합0.
- APK 변경은 입력 검증과 버전 기록. resident4·warmup8·900ms sampler·기존 host polling·numeric-ap-observe-v2·Activity lifecycle·cleanup을 유지한다. 새로운 입력/긴 지속 이력/새 APK를 기존 strict 확인으로 합치지 않는다.
- 최초 PC 빌드가 잘못된 user-home 키를 선택해 인증서 불일치를 발견했다. 배포하지 않고 기존 프로젝트 `.android-user`/기존 격리 빌드 경로로 다시 빌드해 프로젝트 서명을 확인했다. 기기 실패나 재시도 소비로 집계하지 않는다.
- APK `sustained_confirmation_build_v2/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, SHA `5fb72bf2bfda7370abe6b7c50224dfea9fabce28626488897ec424f3f94de833`. 패키지 `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1, signer `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 설치 전후 APK/서명 일치, push1·업데이트 설치1·설치본pull1.
- 계획 `sustained_confirmation_plan_v1/collection_plan.json`, ID `SUSTAINED-CPU-PAR-CONFIRM-01`, SHA `62f4fa62fdd764453317f5d4c0e90fb328999462e8b4f6cacc7e9806832192ee`. 원본 계획/manifest/소스/입력/APK/계수 해시 동결 후 실제PowerShell Check 기기0→Run1회. 마지막에 registry completed를 보존하며 재실행 금지.
- 사용 모형은 분리 개발3으로 동결한 `separated-power-model-v1`, SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`; 원 freeze `19637bf11814e473922c482e752942fb486e4cc74fd74694e6ecf15ee322b825`. 과거870건 모형과 혼동하지 않음. byte 불변·재적합0. 새 자료를 개발로 재사용하지 않음.

## 승인·동결 상한과 실제 소비

|항목|동결 주 실행 / 추가 복구 포함 캠페인 상한|실제|
|---|---:|---:|
|세션/실행계획|8 / 최대10·3계획|8 / 1계획|
|본 요청|1536 / 1920|1536 시작·반환·output_ready·저장·lane해제|
|warmup / 명시적 추론|64/1600 / 최대80/2000|64/1600|
|runtime|32 / 40|32 시작·반환|
|staging·파일|8·56 / 10·70|8·56|
|설치본pull·APKpush·설치|각1 / 각최대3|각1|
|고정 관측|8×210=1680초|8세션 모두 baseline/common/cooling 기록|
|기기/preflight/간격/회수/cleanup|6830초 예약 / 단계180분|2588.054초(43분8초)|
|ADB|25800 / 32600|6647명령·6647 client 결과|
|추가 시도·대체·자동재연결|재현 코드 결함 보완만 최대2 / 대체0|전부0|

예약 식은 `600+8×(120 stage/gate+485 poll+50 recovery+45 cleanup)+7×90=6830초`. ADB 상한 `8×3200+200=25800`, 세션485초 poll에서250ms 파일조회≤1940,2초 thermal3명령≤729,10초 화면≈49에 gate/staging/승인/회수/cleanup을 포함한다. 조회 대기·단계 timeout의 최악 예약이며 정상 소요시간이 아니다. 최초 기기 작업부터 모든 회수/cleanup까지 실제시간에 포함했다.

25개 rc1은 새 staging/input/output 경로 `test -e`의 계획상 부재 확인이다. timeout·연결 소실·불시 lifecycle/추론 오류·중단은 관측되지 않았다. 미시도/실패/미회수/미확인 호출0이며 이는1536개 원본 start/return/lane 및64 warmup 증거로 확인했다. 별도 적격성 추론은 0회이며 warmup 품질 gate를 재사용했다. 실패를 성공으로 채우거나 표본을 제외하지 않았다. 추가 복구 예산은 사용하지 않았다.

## 관측·예측 오차

J는 동일common0~120초. AP 오차는 common35초 이후부터 cooling_end까지 실제 유효 host AP 표본(세션별 창은metrics.csv), 전체180초를 임의 보간한 MAE가 아니다. 예측−관측 부호를 유지한다.

|세션·정책|시작 AP °C|관측120초 J|조건부 A J차이|도착 B J차이|B AP MAE / 최대 °C|관측 최고 AP °C|긴급 P95 ms|병행초|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|0 CPU|29.1|190.930|-5.497|-5.541|0.186 / 0.751|31.9|429.286|0.000|
|1 PAR|29.6|185.627|+3.770|+4.668|0.352 / 1.032|32.3|298.837|21.924|
|2 PAR|29.9|186.741|-4.928|-4.035|0.533 / 1.193|32.7|291.134|22.581|
|3 CPU|30.3|191.732|-2.935|-2.931|0.367 / 1.172|33.1|422.514|0.000|
|4 PAR|30.6|187.884|-5.672|-4.683|0.341 / 0.975|33.1|298.918|22.218|
|5 CPU|30.7|184.491|+8.308|+8.210|0.559 / 1.281|33.4|429.688|0.000|
|6 CPU|30.7|187.533|-2.916|-3.065|0.267 / 0.904|33.4|430.232|0.000|
|7 PAR|30.9|199.216|-2.966|-2.148|0.443 / 1.174|33.4|302.319|22.056|

모든 세션 실제·예측 기한192/192. 마지막 실제lane112.014~112.073초, common120초 미완료0. PAR CG_DC 실제병행21.924~22.581초, CPU병행0. 개별 요청 전력이나 모든 병행 전력 계수의 정밀 식별로 해석하지 않는다.

- A: 실제dispatch~lane_available 일정이 주어진 조건부 비용 예측. 실제 일정 사용을 명시한다.
- B: 사전 예정 도착＋개발 당시 정책별5단계 평균으로 일정을 생성. 실제 미래 완료/전력/AP를 예측 입력으로 쓰지 않는다. 초기 입력은 부하 전 AP 이력과 동결된 −20~30초 평균W뿐이다. 관측 초기 AP를 사용하는 조건부 세션 예측이며 아무 관측 없는 시작 전 예측은 아니다.
- A J 차이 −5.672~+8.308J, 평균절대4.624J; B −5.541~+8.210J(−2.90~+4.45%), 평균절대4.410J. 전체 J가 작아 보이는 경우에도 누적 경로/시간별 잔차를 공개했다.
- B AP MAE0.186~0.559°C(평균0.381), 최대절대0.751~1.281°C, 최고값 차이 −0.816~+0.719°C. AP가 사후 계산 가능하다는 사실을 열에 따른 처리율 검증과 혼동하지 않는다.
- 전류/전압 표본 간격 중앙값0.899~0.900초·최대공백0.953초; AP 중앙값2.595~2.655초·최대공백4.435초. 센서 내부 갱신주기/양자화의 보장이 아니다. 시간축은 앱monotonic에서query before/after bracket로 정렬하며 host wallclock을 직접 차감하지 않는다.
- 공통창 시작 AP29.1~30.9°C, 실행 전 배터리56→51%, BAT29.0~30.6°C·비충전·thermal0 기록. 주변 온도/내부 열 상태는 측정하지 않았으며 시작 AP나 배터리로 대체하지 않는다. 미등록 초기 조건까지 strict를 넓히지 않는다.

## 정책 비교가 밝힌 것

|쌍·순서|PAR−CPU 관측 J|PAR−CPU 최고 AP °C|초기 AP 차이 °C|부하 전 전력 차이 W|긴급 P95 차이 ms|
|---|---:|---:|---:|---:|---:|
|0 CPU/PAR|-5.304|+0.4|+0.5|+0.058297|-130.450|
|1 PAR/CPU|-4.991|-0.4|-0.4|-0.033369|-131.381|
|2 PAR/CPU|+3.393|-0.3|-0.1|-0.061747|-130.770|
|3 CPU/PAR|+11.682|+0.0|+0.2|+0.122417|-127.912|

관측 PAR−CPU 평균 **+1.195J**, 범위−5.304~+11.682J, 기술적SD8.069J(4쌍). 미래분산·오차한도·신뢰구간·인과 효과의 인증이 아니다. 최고AP 차이−0.4~+0.4°C에는 초기AP 차이도 포함된다. 시작 AP만으로 잔열을 같게 만들거나 배경 전력 차이를 임의로 빼지 않았다.

동일 초기조건에 각각 두 정책을 넣은 모형 차이는8초기 모두 **−2.090792J / 최고AP +0.728~+0.748°C**. 실제 다른 세션의 관측 차이와 구분한다. 쌍별 B 예측에 서로 다른 부하 전 전력이 들어가 +4.905/−6.095/−9.500/+12.599J로 바뀌는 것도 공개했다. 이는 작은 정책 자체 차이보다 초기 배경 조건이 크게 작용할 수 있는 산술적 설명이며 배경의 물리적 원인 규명은 아니다.

PAR 긴급 P95는4쌍 모두127.912~131.381ms 짧았다. 이번 입력에서는 동등 기한서비스와 응답 차이를 관측했다. 그러나 에너지 부호가 바뀌며 최고AP도 초기조건에 얽히므로 **작은 에너지·열 차이로 최적 정책을 선택하지 않는다**. 사전 실용J/허용AP/정확도PASS 기준이null이라 새 PASS를 만들지 않았다.

## 시뮬레이터와 완료 경계

등록192요청/400ms·CPU/PAR·A24·동일model/input/resident/runtime의 조건부A/도착B 계산과 이번 독립 전이 block의 오차/관측비교를 실행 가능한 공유 번들로 마무리했다. 여기서 독립 확인은 개발에 사용하지 않은 세션이라는 뜻이며, 연속 실행의 숨은 열 이력이 통계적으로 독립이라고 인증한 것은 아니다. `predict`는exact입력과초기AP/전력만읽고2정책만허용, 출력파일해시/원계수byte검사, energy-ap-policy-selection 차단을 유지한다. CPU_URGENT와PAR의 서비스 충족·응답 차이와 모형의 예상 응답–발열 상충을 연구 결과로 사용할 수 있다.

범용 임의도착·새기기·다른온도/병행·열피드백 처리시간·정밀정책순위는 미검증. S26에A24계수를 적용하지 않는다. 에너지J조건부해석만이며 SOC/사용시간/BAT온도/열안전 인증이 아니다. 이번 변경을 기본모형에 자동 적용하거나 strict/experiment_ready를 승격하지 않았다. accuracy_pass/policy_winner/future_error_bound=null, experiment_ready=false.

이번 캠페인은 종료한다. 결과가 목표 이득을 보이지 않았다는 이유로 보정·새실측·정책튜닝·RL을 실행하지 않는다. **다음 PC 행동 하나: 이 제한된 결과를 연구 본문과 최종 시연에서 응답 개선·발열 상충·에너지 우열 미판정으로 사용한다.** 같은 반복의 추가확대는 권고하지 않는다.

## 종료·원본·검증

앱 정상cleanup8·회수8·host세션정리8, 설치정리1. host force-stop9는 설치정리1+각정상앱완료뒤8이며 앱cleanup과별도 사실이다. 마지막계약상ps조회 대상부재, 마지막thermal0/AP31.3°C(그시점한정),Python/PowerShellexit0·후속PC조회부재. PID와 생성시각·명령·실행 ID를 원 checkpoint와 entry_owner_observation에 보존했다. 이후기기추가조회0.

관련Android10(실제lifecyclecallback5+입력계약5),Python진입/legacy18+readout4통과. 실제PowerShell Check기기0, 정상8/오류/단일cleanup/소비재실행차단fake경계와본문기기실행은분리한다. 공유CLI2정책1초기재현,8세션독립numpy적분·CSV/J/AP점수·전체120초상태coverage·동결/실행소스해시불변검사,대표그림시각검사 통과. 완료한과거전체배치/빌드를반복하지않음.

외부원본root `C:/Users/LG/Documents/D1Check_Arrival_Extension/sustained_confirmation_run_v1`: `FINAL_RECEIPT.json`, `frozen_collection_plan.json`, `host_checkpoints`, `host_commands`,8세션`artifacts`/`recovery_prefix`/`host_cleanup.json`. registry `sustained_confirmation_registry/SUSTAINED-CPU-PAR-CONFIRM-01/completed.json`. entry stdout/stderr `sustained_confirmation_run_v1_entry.log`,PC분석`…/sustained_confirmation_run_v1_pc/evaluation`,inventory`…/sustained_confirmation_run_v1_pc/original_inventory.json`.

원본 inventory는 37,018파일·227,584,076바이트를 읽기 전용으로 해시 기록했다. 재현은 공유 README의 두 경로를 사용한다. 기존원본/모형/옛FAIL/소비계획불변. 키/APK/모델바이너리/대용량원본/기기식별정보는Git에서제외한다. 실제원격HEAD는정상push후직접대조한다.
