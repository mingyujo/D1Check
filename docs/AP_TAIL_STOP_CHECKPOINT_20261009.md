# AP 수집 중단·재개 체크포인트 — 2026-10-09

**사용자의 명시적 요청으로 현재 C0를 중단했다. 추가 측정은 시작하지 않는다. 나중에 새 계획에서 C0부터 처음 시작한다.**

## 현재 종료

plan_v5/ENERGY-AP-TAIL-OBSERVATION-04, SHA dfc034918d0cca805af3623406e74cd2616d8aedd7ac5b5ed2535c4901aa1028.
소유권을 현재기기/PID/manifest/freshjournal로 확인한 대상만 force-stop1회를 수행했고 ps에서 프로세스부재와thermal0을 확인했다. 중단보조11ADB명령, 앱 재실행/추론0. host는 heartbeat stale을 통해 정상 실패 처리 후 stopped_no_resume를 기록했으며 parent/child 실부재를 PC에서 확인했다. **이번 종료의 사용자 원인과 host 메커니즘 오류는 별도 기록**한다. 원 receipt를 수정하지 않는다.

- 정상 완료0/2, C0 중간 종료/LOAD_A미시도.
- 현재 실행에서 runtime4/warmup8/적격4/명시추론12/본작업0. 시작·반환·상한이 일치하는 범위다.
- host 내부3298ADB＋실행전선택1＋중단보조11=현재시도3310ADB.
- host 실행1921.609초. 고정2640초 관측은 미완료다.
- APK703d09d5…b200e/기존프로젝트서명/저SOC별도프로토콜,20%미만 사용자승인·≤5%중단. 비충전/BAT≤35/thermal0/화면/메모리/품질 유지, 절전설정 자동변경0.
- 화면은 같은AOSP Awake/HAL-interactive 상태를완료protobuf로판독하는별도host관측.2초/10초·설정/producer exit검증·실패중단 유지. APK재빌드 없이기존703…재사용.
- C0의600초 종료는 수정후통과했지만 후반1920초는 미완료. 전체block오차/정확도PASS/독립확인완료 없음.

원본: C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_run_v5/FINAL_RECEIPT.json.
사용자 중단: 같은 root의user_stop_request.json, ap_tail_user_stop_run_v5/receipt.json.
로컬 소스 백업: ap_tail_pause_checkpoint_20261009/checkpoint.json. 기존원본/실패/receipt/소비registry와모형5682082a…·후보aa28410d… 불변, 기본/RL/strict/experiment_ready=false 유지.

## 앞선 시도와 PC 변경

plan_v2는C0종료tail검사결함, plan_v3는21→19%배터리gate, plan_v4는text화면조회2초timeout으로각각독립중단됐다. 이것을지우거나합쳐최초계획완주로쓰지않는다. plan_v4의자율앱은소유권확인후첫force-stop/ps부재를보충기록했고최종thermal은12명령예산으로미확인이다.

기존3후보는사전고정/추가fit0다. plan_v3의20%위반전C0 prefix를사후진단으로별도보존했다: AP MAE 원식/LOAD_SLOW0.083°C·CLOCK_SHIFT0.687°C; 실제AP첫/끝29.2→29.2°C. 공통600초J는관측560.486/예측552.650/차이−7.836J(−1.398%)다. 약824초prefix이지2640초완료나LOAD확인이아니다. τ/물리원인/정책차이의확정으로확대하지않는다.

PC 검증: C0종료/기존경로/lifecycle/저잔량Android15, host계획/lowbattery14, proto원문필드/bytes/완료표지/기존화면6＋관련host9 PASS. 새서명703…은프로젝트키·package/version/860payload동일 검증. 키·APK·모델·대용량원본·기기 식별정보는Git제외.

[AOSP 같은상태proto변수](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android15-release/services/core/java/com/android/server/power/PowerManagerService.java) · [필드3/15schema](https://android.googlesource.com/platform/frameworks/base/+/7567b9b595c7/core/proto/android/server/powermanagerservice.proto).
원문선택predicate는같고producer/전송경로와저SOC/APK가변경됐다. 그계측비용을임의추정해J에서빼지않는다.

## 재개할 때

1. 사용자가 재개하면새ID·session·출력의계획을만들고최신Source/APK/계수·contract·미소비를Check한다. 기존v2/v3/v4/v5는소비돼재실행하지않는다.
2. C0부터새세션으로수행한다. 현재기기/transport/잔량·비충전/환경·품질gate를다시확인하며과거값을재사용하지않는다.
3. 같은C0→LOAD_A 질문과코드산출예산을유지한다. 이번에는추가계획/claim/실측을자동생성하지않는다.
