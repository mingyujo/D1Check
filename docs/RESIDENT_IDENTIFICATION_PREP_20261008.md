# 에너지·AP 모형 식별과 독립 확인: 실측 전 PC 준비

**2026-10-09 후속:** 승인Run1회/개발4정상/AP식별gate실패/확인4미시도·계획종료. [실제결과와소비](RESIDENT_IDENTIFICATION_RESULTS_20261009.md). 아래는실행전준비기록이며현재미소비라는뜻이아니다.

2026-10-08 · ENERGY-AP-RESIDENT-IDENTIFICATION-02 · **PC 준비·Check 완료, 미승인·미소비**

기존 자료에서 불안정했던 GPU 단독 전력과 유휴/잔열 반응을 분리하기 위해, 같은 네 resident runtime의 긴 상태 구간 개발4회와 모형 동결 후 확인4회를 준비했다. 마지막 확인2회는 기존 Arrival 실행기의96/192 혼합 요청이다. 새 측정이나 오차 감소 결과는 아직 없다. 원모형·기본 시뮬레이터·RL·strict·experiment_ready=false를 유지한다.

[공유 계획·예산·재현](results/resident_identification_prep_01/README.md) · [분석 계약](results/resident_identification_prep_01/analysis_contract_v2.json) · [8개 입력 요약](results/resident_identification_prep_01/roster.csv) · [검증](results/resident_identification_prep_01/verification.json).

## 무엇을 해결하려는가

현재 최근14 조건부 J MAE4.319J/AP MAE0.329°C, AP 초기화 후보의 일부 개선과 조건별 악화를 출발점으로 삼는다. 기존9개 개발에서 새이력6의 GPU단독 총1.018초만으로는 상태 비용이 안정되지 않았다. 과거 부하후 소비 상승·유휴 냉각 방향 오류를 단순 시간 정렬 결함으로 재분류하지 않는다. [현재 근거](PRELOAD_DYNAMICS_REFINEMENT_RESULTS_20261008.md)·[계수 식별 한계](JOINT_MODEL_REFINEMENT_RESULTS_20261008.md)를 재사용하고 완료한 포괄 감사/정책 배치를 반복하지 않았다.

|질문|모형 항|이번 자료|완료/중단|
|---|---|---|---|
|네 실행 상태 비용을 구분할 수 있는가|상태별 추가W4개와 유효 유휴 bias1개|CPU분류·CPU탐지·GPU분류 단독과 CG_DC, 긴 유휴 포함. 모든 세션에서 네 runtime 유지|전력 설계 rank5·양의 baseline·실제 GPU단독≥10초/개발세션, 부족하면 추가호출 없이 중단|
|가열·냉각·잔열을 같은 식으로 예측하는가|기존 두 상태 AP의 beta/k/g, 잠재30초 고정|개발 순서A/B/B/A,60초 상태·90초 유휴. 실제 lane과 AP 경로|수치 rank3/내부 beta·개발 제외 예측 비악화; 불충족 시 확인 미시도|
|짧은 다른 순서에도 적용되는가|동결한 같은 계수|CONF_A/B의30초 상태 구간|계수·구간을 재맞추지 않고 오차·방향·악화 보고|
|실제 요청 실행 경로에도 적용되는가|같은 모형의 프로토콜 전이|새96 CPU우선·192 분류GPU/탐지CPU 혼합 도착|실제 일정 조건부 비용오차 확인. 정책 우열·예정도착부터의B검증으로 확대하지 않음|

네 상태는 `classification_CPU`, `detection_CPU`, `classification_GPU`, `classification_GPU+detection_CPU`다. CPU두작업 병행·탐지GPU 부하·NPU·정밀도 변경·온도→처리율 곡선은 추가하지 않는다. 탐지GPU runtime은 기존 resident 구성과 warmup 품질 확인을 위해 유지하나 본 부하로 사용하지 않는다.

## 입력과 실행 경로

기존 Arrival 앱은 common120초/분류GPU·탐지CPU 재생 등 계약이 고정돼 있어 긴 네 상태 구간을 그대로 표현하지 못했다. 기존 `EnergyCollectionActivity`에 `resident-identification-regimen-v1` opt-in을 추가하고, 이미 초기화되는 네 runtime·worker·sampler·lifecycle·회수·cleanup 경로를 재사용했다. 이전 state-regimen/short-transition/Arrival 계약은 별도 분기로 남겼다.

|순서|역할·입력|부하 상한|baseline/common/cooling|고정 관측|
|---|---|---:|---|---:|
|0|개발 DEV_A|1,200|120/600/180초|900초|
|1|개발 DEV_B|1,200|동일|900초|
|2|개발 DEV_B|1,200|동일|900초|
|3|개발 DEV_A|1,200|동일|900초|
|—|개발자료 적격성·제외예측·최종계수 동결|추론0|PC 예약600초|관측0|
|4|확인 CONF_A|600|120/480/180초|780초|
|5|확인 CONF_B|600|동일|780초|
|6|확인 ARRIVAL_SEPARATED96|예정96|30/120/60초|210초|
|7|확인 ARRIVAL_SUSTAINED192|예정192|동일|210초|

A는분류CPU→탐지CPU→분류GPU→CG_DC, B는역순이다. 개발의각부하60초/사이유휴90초이며마지막90초는호출종료 여유를포함한유휴tail이다. 확인A/B는다른순서의각30초부하를쓴다. 호출은기존250ms cadence의시간제한 부하이며세션별수는상한이다. 실제 추론이느리면횟수/점유가달라진다. phase 예정시각을놓치면다음일정을뒤로밀어맞추지않고중단한다. 호출의실제종료·lane해제와idle단축/한쪽만남은구간을보존한다.

마지막2회는기존지원원칙의새요청ID를고정했다. 96회는분류/탐지48:48·350ms 도착/CPU우선,192회는96:96·400ms 도착/분류GPU+탐지CPU 허용이다. 최초도착35초,긴급1.5초/일반6초는기존정의다. 예정도착은이전완료와독립이며미래완료시각/감속계수/인위적추가sleep을넣지않는다. 서로다른입력/정책의J총량을자원우열로비교하지않고각실행의관측−예측만검사한다.

이수정으로최초대화의91분/8상태구간제안을그대로실행하지않는다. 호출종료tail과현재지원Arrival구간을코드로산출한최종관측은 **93분**이다. 상태6회는필수준비관측120초씩,세션간대기는90초씩별도다. 이전PC설계v1/v2·중간v3소스바이트초안은미소비로보존했으며FAIL/stopped_no_resume로기록하지않았다. 최종실행대상은아래해시의 **plan_v3 하나**다.

## 실행 적격성·계측·연결 정책

- 같은A24/fingerprint/하드웨어값·현재transport·설치본/프로젝트서명·모델/입력/hash를실행기가확인한다. 이전endpoint를현재값으로대체하지않으며전체명령을사용자에게승인받은한transport로고정한다. 다른연결해제·daemon재시작·재연결·설정변경없음.
- 기존비충전·배터리≥20%·BAT≤35°C·thermal0·화면/설정·메모리·GPU/출력품질gate유지. 모델개발하한32.5°C는실행gate가아니다. 온도맞춤가열·추가warmup·무제한대기는없다.
- 각실제부하직전HAL numeric AP를한번신선하게승인한다. Android조회before/after·실제start의3초조건을앱에서검사한다. state경로의기존baseline.arm은기기자체연속으로남기고새numeric start승인만한번추가했다. 부하내부상태전환은host arm없이앱이진행한다.
- sampler900ms/host AP 최소2초/화면 최소10초를두경로에적용한다. listing도이신규계획에서는이전iteration후최소2초로한정했다. 준비·프로토콜·기록비용차이를숨기거나추정해빼지않는다. 실제센서내부갱신/정확도인증아님.
- Activity는유지하며앱을떠나게하는명령을추가하지않는다. onDestroy취소/기존최초오류/정리중복방지는그대로다. 앱환경감시와watchdog은있지만nativehang/프로세스전체정지를항상끝낸다는보장은없다.
- 연결소실/조회실패면기존중단규칙을따르고새실행을시작하지않는다. 앱이이미자율실행중일가능성이있으면소유권/종료를임의확정하지않고미확인으로보존한다. 이번계획에자동재연결·20분대기·추가회수계획을승계하지않았다.

## 추정·동결·확인

한 후보군은 `P=세션부하전W + 유효유휴bias(부하후) + 4상태별증가W`와기존AP 두상태계열의beta/k/g다. bias는기기전체잔차의경험항이며특정프로세스전력/주변온도/숨은내부온도라고하지않는다. 잠재30초/기존상태열입력/기기·모델·정밀도는고정한다. beta는기존61격자다. 원모형과기존AP초기화후보를보존하며확인후새구조를선택하지않는다.

개발4회만으로상태전력rank5와AP rank3/경계값을검사하고,실행1회전체를빼는4fold+최종적합을수행한다. 각A/B묶음의120초J/긴등록창J/AP MAE/최대오차가원모형보다악화하면확인으로넘어가지않는다. 이규칙은정확도PASS나통계적안정성인증이아니다. 동결에는개발4개validated SHA·분석계약SHA·원모형SHA·계수와선택근거를기록하고,각확인진입전다시대조한다.

확인은자기부하전W/AP와실제상태일정만입력으로쓴다. 부하후온도/전력을계수·초기기준·구간선택에사용하지않는다. 원120초와긴구간에너지를분리하고AP는실제post35 표본창으로오차/최고값/방향을산출한다. 전체/등급별완료분모·부분/미완료·실제겹침·센서coverage를보존한다. Arrival요청이common120초를넘기면전체작업비용으로합격처리하지않는다.

개발부적격/미식별/예측gate실패면확인4회미시도다. 확인실패면고정모형을고쳐재확인하는경로가없다. n4 확인으로변동성·정책의작은차이·모든도착/온도/기기를검증하지않는다. 현재원모형/기본/RL/strict/experiment_ready=false자동교체0.

## 코드에서 산출한 최종 예산

|항목|상한/예약|
|---|---:|
|세션|개발4＋확인4=8|
|본작업|최대6,288회(상태6,000＋도착96＋192)|
|적격성 / warmup / 명시적추론|24 / 64 / **6,376회**|
|runtime / staging / 파일|32 / 8 / 56|
|설치본hostpull / APKpush / 데이터보존설치|각최대1회,동일설치본생략|
|고정baseline·부하·cooling|5,580초=93분|
|별도필수준비관측 / 세션간대기|720초=12분 / 630초=10분30초|
|세션예약|각2,080초(준비120＋launch20＋poll1800＋회수60＋cleanup45＋검증35)|
|설치확인·배포 / 개발동결 / 후처리예약|600 / 600 / 600초|
|전체누적상한|**19,070초=5시간17분50초**|
|ADB|**34,728명령**,pre-cleanup34,328＋후속종료예약400|
|재시도 / 대체 / 추가|0 / 0 / 0|

Arrival의poll은485초로더짧지만전체예약은각2,080초의보수적상한을사용한다. `normal_duration_seconds=null`이며고정93분이나timeout합을정상소요시간으로부르지않는다. OS/host정지에도벽시계종료가보장되는것은아니다. 최대명령은iteration2초·thermal3명령/2초·화면/heartbeat10초＋게이트/회수/배포예약으로산출하고ObservedDevice상한에연결했다. 개별조회3초(thermal/screen2초)·AP신선도3초·APKpush180초를임의늘리지않았다.

기기측cal watchdog1800초,Arrival480초와기존개별call30초를유지한다. 최대cal 내부예약은setup150＋warmup gate60＋serial gate60＋probe60＋probe gate360＋baseline120＋AP gate30＋common600＋cool180=1720초이며남은watchdog 여유를확인했다. 모든미시도최대호출을자동소비0으로확정하지않는다.

## APK·최종계획·승인 후 명령

서명APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/resident_identification_signed_v2/benchmark-runner-modelProbe.apk`,106,203,985B.

- SHA-256 `57d2320c35c3cfaf52a2a127460007809bed21e23b2c2b05a8efb30bd699cb20`
- 기존프로젝트인증서 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`
- package `com.example.d1check.benchmarkrunner.modelprobe`,versionCode1/versionName1.0
- 출처:격리build_v2와서명receipt. 서명전후860개비서명ZIP payload 항목byte동일. 키/비밀번호/모델/APK는Git제외,전송/설치0.

최종계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_identification_plan_v3/collection_plan.json`

SHA-256 **`2cb32c36c45345273a033f4c28f5f39c8daec540209e62e804349c07be17ac1f`**.

```powershell
# PC Check만 실행. 이번 작업에서 Run은 호출하지 않았다.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_identification_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check

# 위 전체예산의 별도 실행 승인과 현재transport 확보 후에만:
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_identification_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 확인한 A24 transport>' -ExpectedPlanSha256 '2cb32c36c45345273a033f4c28f5f39c8daec540209e62e804349c07be17ac1f'
```

검증된foreground PowerShell parent/child wrapper의host_entry start/end·stdout/stderr·runID와Python checkpoint를재사용했다. 새로운detached 구조가아니다. 도구출력대기와실제host종료를구분한다. 기기실행승인은아직없고registry/출력root는없다.

## PC 검증과 한계

새Kotlin4＋기존상태2＋기록재생4=10개테스트통과,Android본문/테스트컴파일·서명APK검증통과. Python새10＋관련host실패8=18개검증통과:실제파일parser fixture/누락블록·미지원·호출/시간상한·개발/확인분리·합성전체동결경로·확인재적합차단·원오류/checkpoint/정리보존이다. 실제기기2개보존Arrival원본의새reader를읽기전용으로검증했다. mock센서/합성경로는실기기분리계수/연결안정성의증거가아니다.

최초컴파일의ANDROID_HOME 누락은기존SDK 경로를설정해해결했다. 기본빌드서명이기존계열과달라기존프로젝트키로다시서명했고검증했다. 원문fixture는AP/status 두필드만기대한schema여서추가센서필드까지같다고가정한테스트를그원문필드기준으로정정했다. 원자료/판독결과를바꾸지않았다. 기존혼합줄바꿈의불필요한diff를복원한최종소스에APK 출처를맞췄다.

작업시작HEAD2ace32f,동시에완료된CPU/GPU/RL의01fa13f를보존했다. 사용자STATUS14행·다른worktree·기존자료/모형/실패/종료계획을보존한다. **이번기기/ADB/설치/앱실행/실측/claim은0회**다. 다음행동하나는최종8세션예산의실행승인과현재기기gate를확인하는것이며,이번계획이모형오차감소완료를뜻하지않는다.

추가회귀에서한글을포함한host parent명령이checkpoint에기록될때기존테스트가CP949 기본encoding으로읽어실패했다. JSON이UTF-8이라는실제계약대로테스트읽기encoding을명시했고최종18건을다시통과했다. 센서자료·오류사유·assertion조건은바꾸지않았다.
