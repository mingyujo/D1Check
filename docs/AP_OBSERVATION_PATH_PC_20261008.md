# AP 관측 입력과 전달 경계의 PC 적용 판정

2026-10-08 · AP-OBSERVATION-PATH-01 · **host 진단용 입력·예측 연결은 PC 검증 완료, 현재 APK의 자율 AP 피드백은 적용 불가**

현재benchmark 앱은numeric AP를직접읽지않으며실행중AP를받는consumer도없다. host가이미읽은AP를소유권/시각/단위검사후10초예측에연결하는별도PC API를구현했다. 새기기명령·관측주기·원실행기·Android/APK를변경하지않았다. APK에적용됐다거나실시간폰정책이완성됐다는판정은하지않는다.

단말에현재설치된APK/권한상태는이번에조회하지않았다. 판정대상은현재저장소코드·기존서명APK계열·과거원기록이다. 앞선40~45%의AP평균오차감소도기록상가용proxy를이용한PC재생결과이며, 실제consumer/앱전달지연까지검증한개선으로승격하지않는다.

[지원표·재현](results/ap_observation_path_01/README.md) · [명령/조회시간1630행](results/ap_observation_path_01/query_timings.csv) · [원manifest소유권재판독](results/ap_observation_path_01/owner_gate_replay.csv) · [20개예측진입](results/ap_observation_path_01/forecast_integration.csv).

## 현재 코드의 실제 경로

|주체/코드|읽거나보내는값|진행중AP 갱신에대한판정|
|---|---|---|
|[ArrivalEnergyActivity.snapshot](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalEnergyActivity.kt)|BatteryManager전류/charge counter, 배터리broadcast전압/BAT온도, PowerManagerthermal status, memory/screen/actualstate|numeric AP필드없음. status/BAT를AP로대체할수없음|
|[ArrivalBackgroundObservation/PastPowerWindow](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalBackgroundObservation.kt)|과거전력10초창·ready시점·128표본buffer, background opt-in때만causal_power_input기록|전력입력구성요소는존재하지만backend배정에사용하지않음. PC창`issue−10..latest`와앱창`latest−10..latest`가달라자동동일처리하지않음|
|[host thermal()](../tools/d1_energy_collection_device.py)|uptime→dumpsys thermalservice→uptime의3명령, Current HAL AP·전후device시각·host기록시각|원host만숫자AP확보. 원계측이연결중반복하는경로이며새query추가없음|
|[ArrivalStartApGate](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalStartApGate.kt)|start_ap.arm의hash/ready/before/after/AP/status6필드, 시작신선도3초·대기30초|시작전승인1회. 스트리밍경로가아니며반복전송용으로재사용하면실행의미변경|
|[EnergyProgress](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/EnergyCollectionCore.kt)|비동기32768queue, 1초fsync, gate/종료flush|event의mono_ns는기록생성시점이며host가받은시점/디스크내구화완료를보장하지않음|
|[메인앱TelemetryForegroundService](../app/src/main/java/com/example/d1check/TelemetryForegroundService.kt)|thermal headroom0/60초·BAT/전류·전압|별도메인앱의공개thermal API 경로이며probe AP°C 경로/observer가아님|

Activity→worker→sampler의기존소유권·onDestroy취소·정상/실패cleanup을수정하지않았다. 기존policy choose경로에AP입력이나추가대기를끼워넣지않았다. `modelProbe`의INTERNET제거·원project서명·기기권한/설정도그대로다.

## 일반 앱 API의 제한

`HardwarePropertiesManager.getDeviceTemperatures`는CPU/GPU/BAT/SKIN°C를반환하지만device owner/current VR service외의호출자에는SecurityException이명시돼있다. 현재프로젝트에는그역할설정이나이API를호출하는경로가없다. 또CPU온도배열을기존A24 HAL이름AP/type0와같다고자동인정할수없다. [Android 공식 API](https://developer.android.com/reference/android/os/HardwarePropertiesManager#getDeviceTemperatures(int,%20int)).

`PowerManager.getThermalHeadroom`은열envelope의사용/예상사용정도를반환하며특정AP온도°C와동등하지않다. 미지원기기는NaN을반환할수있고1.0을초과할수도있다. 기존AP모형에headroom×임의비율을온도로대입하지않았다. [Android 공식 API](https://developer.android.com/reference/android/os/PowerManager#getThermalHeadroom(int)).

PC에서는vendor sysfs의현재접근권한이나기기특정센서지원여부를확인할수없다. root/device-owner/서명교체/DUMP권한추가·OS열보호변경을준비하거나실행하지않았다. 현재코드에없는직접AP경로를앱자체실행지원으로선언하지않는다.

## 원본으로 판독한 시간

새이력개발6/확인6＋기존지속8의20세션에서사용한AP기록 **1630개**를앞뒤uptime/thermal의원client결과와모두대조했다. 전체원client19,473개를PC에서읽었으며새ADB조회가아니다. 실패client를성공조회로채우지않고그외query를추가하지않았다.

|구간|중앙값|P95|최대|뜻|
|---|---:|---:|---:|---|
|Android before..after bracket|0.220초|0.270초|1.320초|기기쪽조회시각불확실성, hardware갱신주기아님|
|thermalservice client단독대기|0.079초|0.109초|0.673초|PC client벽시계, 기기CPU/에너지비용아님|
|3개client대기합|0.281초|0.375초|1.616초|세client예약/대기측정, 앱전달지연아님|
|첫client시작→마지막client종료|0.328초|0.437초|1.650초|기존AP 관측cycle의host span|
|마지막client종료→host기록timestamp|0.0146초|0.0200초|0.0630초|parse/read후timestamp간격, receiver나앱수신시간아님|

`thermal()`은values를파싱한뒤`host_monotonic`을찍고그다음파일write/flush후반환한다. 따라서기존timestamp를**consumer실제수신시점**으로취급할수없다. 앱AP수신/적용ack 자체가없으므로앱전달지연은 **null**이다. clockdomain이서로다른host秒와Androidns를직접빼지않았다.

## 최소 PC 구현

[d1_ap_observation_bridge.py](../tools/d1_ap_observation_bridge.py)는기존thermal결과를입력하는독립API다. 기존collector/runner에는hook하지않아새기기명령이나source/계측프로토콜변경이없다.

- **정확한센서/원본문검사:** Current HAL구간의유일한AP/type0·degC만수락. 캐시fallback·중복AP·BAT·status·headroom·metadata/본문불일치·nonfinite거부. 공용legacyparser동작은보존한다.
- **소유권:** session ID·manifest SHA·host clock namespace를수신자와비교한다. 실제20manifest byte/hash를확인해1630개전체를그소유권으로재판독했다. 공유fixture는동일값/시각을익명별칭으로재현하며실제메시지라고하지않는다.
- **신선도:** Android결정시각≥조회after, 결정시각−before≤10초와host now−receipt≤10초를각domain에서확인한다. 현재Android결정시각없음/clock범위불일치/future/stale/thermal환경변경은unavailable이다. 추가uptime조회나clock추정은자동수행하지않는다.
- **실제수신과proxy:** caller가consumer callback완료후의동일hostclock 시각을`received_host_mono`로명시할수있다. 생략하면원timestamp를proxy로표시한다. proxy를실수신/내구화/앱전달인증으로승격하지않는다.
- **유한buffer:** immutable32표본/deque·짧은Lock로저장/복사만한다. 중복/늦게온이전표본은최신값을대체하지않고sensor/file/inference를lock안에서수행하지않는다.
- **예측연결:** 검증된host관측을기존10초AP관측보정함수에연결한다. 초기관측준비미완료·기존anchor보다이전관측·10초밖/무순서요청을거절한다. energy보정/새전력식은붙이지않았다. app_status/app_ready는현재APK에대해unavailable/false다.

받아온관측의AP사용불가와실제기기환경위반은동일한사실이아니다. 이API는정리/force-stop/재연결/재실행을호출하지않고원환경/중단/회수계약을우회하지않는다. 온도값/공통환경/timeout/조회주기를수정하지않았다.

## 적용가능 범위와 종료

**완료:** 같은A24 원센서의host 진단용관측→입력검사→조건부10초예측연결, clock/소유권/결측의PC경계검증·과거조회시간판독. 실제20진입과공유20fixture의공식을기존rolling API와대조했다.

**현재불가:** 일반권한의현APK에서직접numericAP관측/실행중받기/스케줄러적용. 이미연결된host collector가값을읽는다는사실은앱stream소유권·수신ack·지연·추가계측비용을충족하지않는다. 현재APK에반복start_ap.arm·새AP파일polling을붙여실시간ADB의존성을되살리지않았다.

연구용AP보정은host보조진단/PC사후예측도구로사용가능하다. 기기독립실행에연결하려면ordinaryapp에서확인된수치APsource또는**공개thermal signal용별도모형/목적**이필요하다. 후자는AP모형의동일검증완료가아니다. 이번에는공개신호를임의온도로바꾸거나새기기실행계획·APK를만들지않았다. 이불일치해결없이폰AP피드백실행을권고하지않는다.

다음행동하나는 **현재AP보정은host연구도구로범위를고정하고, 앱자체경로에는기존공개thermal signal을사용하는별도입력계약의필요성을결정**하는것이다. 현재자료에서관측신호가정책레버를제공하는지도따로판정해야하며단순공개API존재만으로절감효과를주장하지않는다. 같은온도gate/긴진단을반복해해결할문제로다루지않는다.

## 검증·Git

관련8검증PASS:원parser CurrentHAL/캐시·type/중복·owner/단위/nonfinite·dualclock/future/stale·producer/consumer시점분리·duplicate/order/buffer·thermal·10초예측/초기조건/원hash. Git공유값만으로1630조회통계·20예측fixture·앱미지원표시를추가실행0으로재현했다. [검증/입력/코드hash](results/ap_observation_path_01/verification.json).

기기/ADB/설치/앱실행/추론/실측/설정/Android변경/compile/APKbuild/새claim0. 원모형/strict/RL/experiment_ready=false·계측주기·원FAIL/소비/자료와사용자14행/SLACK별도작업/다른worktree보존. 관련소스·작은요약/fixture/문서만Git반영하고실원격HEAD는push후대조한다.
