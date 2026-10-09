# 긴 C0·부하 회복 Run01 — C0 종료 경계 결함으로 중단

2026-10-09 · ENERGY-AP-TAIL-OBSERVATION-01 · **stopped_no_resume, 정상 완료0/2**

재페어링과 동일 A24·설치본·환경 gate를 통과해 plan_v2를1회 실행했지만, 첫 C0의600초 무부하 블록 뒤에 기존 부하 경로의 tail 검사를 적용하는 구현 결함으로 중단됐다. 제가 준비한 경로에서 이 종료 경계 검증을 빠뜨린 것이 원인이다. 연결 소실·lifecycle_cancelled·모형 예측 실패 사례가 아니다. C0의1920초 회복과 LOAD_A는 미진행이며 새 예측 오차는 없다.

[실제 종료 화면](results/ap_tail_observation_run_01/run_v2/index.html) · [소비·정리](results/ap_tail_observation_run_01/run_v2/consumption.json) · [Android 사건표](results/ap_tail_observation_run_01/run_v2/app_timeline.csv) · [실패 경계·부분 관측](results/ap_tail_observation_run_01/run_v2/failure_boundary.json) · [PC 수정 검증](results/ap_tail_observation_run_01/verification.json).

## 실행과 실제 소비

착수HEAD2bd9970, 기존 9816886 연결 실패 후 사용자가 현재 페어링 정보를 제공했다. pairing1회가 성공했고 목록 확인1회에서 A24 한 transport를 확인해 고정했다. 기기 식별·fingerprint·프로젝트 인증서·패키지/버전·배터리/비충전/BAT/thermal/화면/메모리·GPU/출력품질 gate를 실행기에서 확인했다. 과거 주소·환경을 현재값으로 사용하지 않았다.

설치본57d2320c…와 후보dd55b04d…가 달라 같은 프로젝트 서명의 데이터보존 업데이트를1회 수행했다. Run은1회이며 종료된 계획·초안은 실행하지 않았다. 구체적인 기기 식별정보·페어링 코드·키·APK·모델·대용량 원본은 Git에 넣지 않는다.

|항목|승인 상한|실제|
|---|---:|---:|
|정상 세션 / 시도|2|정상0, C0시도1, LOAD_A미시도|
|본작업|1200|0|
|적격성 / warmup / 명시적추론|8 / 16 / 1224|4 / 8 / **12**|
|runtime|8|4|
|staging / 파일|2 / 14|1 / 7|
|설치본hostpull / APKpush / install|각1|각1|
|ADB|16752|내부1584＋연결 준비4＝**1588**|
|실행·회수·cleanup|9050초|**927.703초=15분27.703초**|
|재시도 / 대체 / 추가|0|0|

연결 준비4는 이전 실패 connect/listing2와 이번 pairing/listing2다. 최초 접속 실패에서 재페어링까지 약65분의 사용자 응답 대기는 실측 실행시간과 분리한다. 이전 실패 명령도 소비 분모에서 지우지 않았다. 준비 추론12는 원본 journal/receipt의 시작·반환·상한이 일치하는 범위로 확인했다. 일반적인 미기록 호출을0으로 간주한 것이 아니다.

고정 관측 목표는 세션당2640초였지만 실제 공식 baseline약120초와 C0 무부하약600초까지만 도달했다. 전체 고정88분을 완료한 것으로 표현하지 않는다.

## 정확한 실패 경계

원본 APK의 calibrationWorkload는 블록 뒤에 다음 검사를 공통 적용했다.

```kotlin
check(now()-commonStart < commonNs) { "no common-window tail reserve" }
```

LOAD_A는 등록 블록510초＋예약 tail90초여서 이 검사가 맞는다. C0는 등록 무부하 블록 자체가600초라 정상적으로 끝내도 elapsed≥600초가 되어 검사가 실패한다. 원인에는 외부 조작 추정이 필요하지 않다.

Android elapsedRealtimeNanos 기준 common 시작을0으로 두면 block_end는600.025575728초, 원 session_failure는600.028086189초다. 정상 identification_common_end와 resident_cooling 시작 기록은 없다. session_failed→app_cleanup→finish_requested가 뒤따랐다. onDestroy/lifecycle_cancelled로 종료 원인을 설명하지 않는다.

host 회수는 원 manifest/progress/cleanup prefix와 archive를 보존해18파일을 확보했다. 원 app stack은 EnergyCollectionActivity.calibrationWorkload의 이 검사 위치를 가리킨다. PC validator의 app failure 오류는 원 앱 실패를 거부한 결과이고, 후속 sampler_failure.json 누락 회수 오류는 별도다. 이를 원래 원인으로 바꾸지 않았다.

Android 사건표는 동일 기기의 단조시각으로 정렬한다. host UTC는 ADB client 시작/끝과 checkpoint에만 사용하고 직접 두 시계를 빼지 않는다. host force-stop은06:50:58.997 UTC에 회수 이후 실행됐으며, 원 app 오류/cleanup가 앞서 기록돼 있었음을 회수 순서로 확인했다.

## 자료 경계와 종료

시작 AP29.1°C, 조회 후 실제 common 시작 지연0.197962423초이며 조회 시작부터0.427962423초로3초 신선도를 통과했다. 해당 무부하 구간의 host AP233표본은 common 시작 후2.912..598.472초를 덮었고 관측범위29.0..29.6°C, 첫/끝29.1→29.3°C였다. 이는 부분 관측이며 긴 회복 확인 결과가 아니다.

전력954표본 중 등록600초 coverage는599.743861304초, 끝 누락0.256138696초다. covered J549.731714는 원 current raw=mA 조건부 적분이다. **전체600초J는null**, 모형 오차도null이다. 끝을 외삽하거나 부분J를 전체 창으로 표현하지 않았다. 비교AP곡선·정확도PASS·정책효과를 만들지 않고 실제 실행 경계 그림만 남겼다.

앱은 정리 경로/app_cleanup/finish 요청까지 도달했으나 cleanup.json 상태는 원 실패를 포함한failed다. 정상 수집 완료와 구분한다. 세션 host cleanup1회가 force-stop/프로세스부재/thermal0 확인까지 완료됐다. 설치 단계 정리1회와 세션 정리1회는 별개이며 같은 종료처리의 중복force-stop은 없다. host parent/child 실제 부재를 PC에서 확인했고 wrapper는 Python exit1/normal_wrapper_return=true를 기록했다. 새 기기 종료 조회는 추가하지 않았다.

원본 receipt: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_run_v2/FINAL_RECEIPT.json`.
원 manifest·journal·FAIL/부분회수·archive·checkpoints·host 명령·APK·모형·registry는 그대로 보존한다. 원모형5682082a…와 후보aa28410d…/기본/RL/strict/experiment_ready=false는 불변이다. 소비된plan_v2를 재개하거나 claim을 초기화하지 않는다.

## PC 최소 수정과 검증

새 tail 프로토콜의 **정확한 등록 C0만** elapsed≥common600초의 종료를 허용했다. 조기 C0·미등록idle·다른창은 거부한다. LOAD_A와 모든 legacy 경로는 기존 elapsed<commonNs 검사/오류를 유지한다. watchdog·건강감시·센서 주기·호출수·1920초 냉각·onDestroy 취소·모형 계수는 바꾸지 않았다.

실제 Activity의 종료 분기 메서드를 Robolectric에서 실행하는 회귀2건과 조기/미등록 경계1건을 추가했다. 기존 tail4·resident4·lifecycle callback2와 함께 **Android13건 통과**, 본문·테스트 컴파일·격리 APK assembly를 완료했다. 최초 경계 테스트2실패는 Activity 호출부가 아직 교체되기 전 컴파일된 구버전에 메서드가 없었던 PC 빌드였다. 완성된 소스에서 동일 assertion으로 재컴파일해 통과했으며 실패 로그도 보존했다.

PC publisher5건은 clipping/끝·공백null/원본 시작·반환 범위/미래AP·전력 누출 차단/활성 실행 publication 차단을 통과했다. 실패 데이터를 실패 화면으로 재현하고 계수 적합0을 유지한다. Robolectric는 실제600초+1920초 장시간 성공이나 native·환경·연결 안정성 증거가 아니다.

수정 후보 APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/ap_tail_boundary_fix_signed_v1/benchmark-runner-modelProbe.apk`.
SHA `00b2b926d8505e149e6ec3315dc2156031fde290a9327fb751e07e016d651cdb`, 기존인증서b253dbb9…fcc7565, 동일package/versionCode1/versionName1.0, 비서명860payload 서명전후동일. 출처·소스SHA·build receipt를 외부에 보존했다. **수정 후보의 전송/설치/추론은0회**이며 현재 설치본dd55b04d…에는 이 경계 수정이 없다.

## 재현과 다음 행동

```powershell
python -B -m unittest tools.test_d1_ap_tail_observation_results.ResultTests -v

# PC 판독만, 새 출력 경로를 사용:
python -B -m tools.d1_ap_tail_observation_results --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v2/collection_plan.json --output output/ap_tail_failed_reproduction --external-adb-commands 4
```

다음 행동 하나는 **수정 APK를 별도 ID의 새 실행 계획에 동결하는 PC 준비**다. 기존 2조건 질문/소비 분모와 실패를 유지하며, 이번에는 새 계획·추가 claim·재실측을 만들지 않았다. 이미 끝난 포괄 감사나 다른 모형 후보 탐색을 반복하지 않는다.
