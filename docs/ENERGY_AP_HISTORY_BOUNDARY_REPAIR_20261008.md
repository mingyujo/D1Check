# 냉각 끝 적분 경계 수정·완료 C0 재사용 — 2026-10-08

v3 첫 `development_30_C0`는 앱cleanup completed, runtime4/warmup8/conditioning96 완료·target120초 완료·trace 회수 뒤 **PC `load_case`의 cooling tail 전체전류검사**에서중단됐다. 마지막표본은냉각phase_end보다0.392626577초전이다. 기존원receipt의stopped_no_resume·power gap과원자료는보존한다.

## 확정된 구현 문제·수정

PC수식의J보고구간은target 공통120초다. 기존검사는 conditioning 시작부터 냉각phase_end까지full current를필수로요구했는데, 마지막센서tick은phase종료보다앞일수있다. 이를conditioning 시작→target+120초의필수coverage와냉각coverage(계산불가null 가능)로분리했다. 공통창end를옮기거나외삽/0채움하지않았다. AP냉각은별도의실제AP표본·gap gate로기존과같이검증한다.

실제검사: registered conditioning/history/common300.081567318초, coverage전부·energy320.839310145832J. 이는**conditioning+회복+target 공통의합계**이며 target120초에너지와구분한다. 냉각60.152639088초중59.760012511초전류coverage·missing0.392626577초, 냉각full J=null을보존한다. 앱/전류/gain계수를변경하지않는다. corrected validate가 eligible_descriptive_only를반환했고APinitial/state/quality/clock/호출gate는생략하지않았다.

## 자료재사용·추가측정범위

같은APK/입력/host progress2초/환경감시/sampler/trace인 v3 C0를재측정하지않는다. 신규v4의첫logical entry는v3원manifest/원artifacts/trace의read-only복사와file별SHA출처로채우며, 별도validated·provenance만신규경로에쓴다. 원FAIL/receipt를바꾸지않는다. 수정PC분석과planner/재사용/preflight5모듈외의원source hash는같아야한다. 기존모형·Android·계측/분석핵심계수는불변이다.

원cohort 12조건 분모를유지하고새기기실행은개발5+확인6=11이다. 개발완료6에는재사용C0 1이들어간다. 그6개로등록절차/g를동결한후확인6을진행한다. 새receipt의cohort소비와new_*소비를분리한다. 식별/개발gate를결과에맞춰완화하지않고, 불충족이면확인0·부분분석으로종료한다. 확인자료로재보정/새후보추가0.

현재설치본은동일APK라는v3검증cache를그대로믿는것이아니다. 신규preflight에서동일기기/현재pm path/현재원격APK SHA를읽고, 그값이로컬검증cache bytes SHA와일치할때만서명/패키지/버전을cache에서재확인한다. 다르면pull/재설치fallback없이중단. 이경로hostpull0·push0·install0.

## 정확한 v4 예산·시간

- plan `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v4/campaign_plan.json` SHA `d2b9687a355391fe07f2ca1635a5521feffc4ab9731a877ac82856812160da2e`
- child SHA `ede6b9e2f1ab20cbaabceb8f4dbfb928cb88efd6e27a95f66c088d31d22ff59d`. 11새세션/요청1824/warmup88/총1912/runtime44/staging11·77파일/tracepull11/ADB83800/installed-only180초,전체예약17691초.
- v2실패104+v3재사용104+v4신규1912=총2120추론, runtime4+4+44=52/staging1+1+11=13/총91파일/설치본hostpull1+1+0=2. 전체목표에기존상한보다추가된호출을숨기지않는다.
- v4claim은v3원시monotonic/wall 시작을승계한다. **수정·계획·대기시간을포함한6시간을reset하지않는다.** 남은시간이17691+600초미만이면진입하지않는다. 종료예약/누적commandcap/환경gate를그대로준수한다. child시간상한은남은11세션plan의예약이다.
- 원v3host/client종료를PC식별검사로확인. 원자료hash와원receiptSHA를Check로재확인. 새ID/output/claim을사용하되소비기록초기화/원v3재개는없다.
- 명시연결오류때만같은transport20분/20조회대기와읽기회수120초/20명령·1회를허용한다. 앱재시작/다른endpoint/daemon/settings변경0. 재사용개발자료가있으므로이cohort의새whole-block보완은0이다. 실시간필수gate/손상/상한을단순성공요청으로우회하지않는다.

## PC 검증·실행

42관련검증통과: 공식창coverage는허용·공통창내결측은여전히차단, 냉각끝null보존, 원자료재사용hash/소비0/원파일불변/변경자료차단, cachedAPKfreshremotehash일치·불일치/no-pull, 실제poll단순진행gap/thermal/screen/원오류/legacy, 기존동결/확인/cleanup회귀. 실제완료v3원본을corrected validate/coverage로재판독했다. Android변경/재빌드0. 소프트웨어test를실제연결안정성으로확대하지않는다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v4/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v4/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<동일현재A24 transport>' -ExpectedPlanSha256 'd2b9687a355391fe07f2ca1635a5521feffc4ab9731a877ac82856812160da2e'
```

최신사용자자율수정/실행승인에따라별도질문없이현재gate후진행한다. 중간stop/완료/후보fit·독립확인·오차·실소비는종료후별도최종보고로남긴다.

## v5 환경 미확인 lease와 완료 2자료 재사용

v4 CPU는정상완료/자료적격, 다음PAR은화면poll1373의2초무출력/root-reaped timeout으로중단됐다. 화면꺼짐이나연결소실을확정할근거는없다. 직전정상host화면은awake/interactive=true, 마지막앱power표본도interactive=true/thermal0/plugged0/low_memory=false. 원FAIL/receipt/부분PAR을그대로남기고학습/확인에서제외한다. PAR durable시작100작업+warmup8=108, 반환99+8=107, 원prefix뒤호출은미확인·등록상한200을보수적으로예약한다.

새 opt-in `postapproval-environment-lease-v1`은무출력2초timeout·정확한screen/thermal명령·client-reaped·완전증거·최근정상thermal10초미만/화면20초미만일때만1회환경unknown을기록한다. ValueError실제위반·부분출력·closed/offline·명령불일치·증거저장실패는여전히중단. 원오류/stack/clock/제한을먼저기록하고다음정규loop에서freshthermal/화면을확인한다. 마지막유효thermal부터10초가최대복구기한이며그동안환경이통과했다고표시하지않는다. 제시간복구파일없음·두번째환경실패·늦은응답은중단한다. 환경공백중작업이진행할수있으며, 앱의기존battery/thermal/interactive/memory감시와watchdog는그대로다. nativehang/프로세스정지까지항상종료한다고보장하지않는다.

후속자료검사는APgap≤10초·원숫자AP·전체필수power창·호출/품질을그대로확인한다. lease를사용했다면추가로앱power표본의interactive/plugged/thermal/low_memory가전부적격이고복구가lease기한이전이어야한다. 관측손실을실제환경위반과분리한새계약이다. 필수센서를삭제/thermal을numericAP로대체하지않는다. query/추가fresh환경관측의에너지영향은보정해빼지않고프로토콜전이로분리한다. 기존지원범위/계수/strict/기본모형은불변.

검증46PASS: 실제poll에서무출력환경timeout→제시간fresh복구, 두번째실패/lease만료/state위반/최근정상값부재차단, 기존경로fail-fast, listing간격/원오류·재사용·현재APKfreshhash/no-pull·원공통창/냉각null·개발/확인분리. 실제ADB0의PC검증이며실기기안정성PASS가아니다. fixture의명시index누락1을보완했고최종46PASS.

v5는C0+CPU 2개만read-only로재사용하며새개발4/확인6=10세션이다. 1632작업+80warmup=1712추론/runtime40/staging10·70파일/tracepull10/ADB76200/설치・APKpush・hostAPKpull0/전체예약16245초. 최종cohort12의2016추론과실제새소비는분리한다. v2실패104+cohort2016+실패PAR최대200=**전체누적상한2320추론/14시도/runtime56/staging98파일**이다. 최신사용자의“알아서수정하며계속…다마무리”승인에따른추가실패1회분예약이며무한증액이아니다. ADB99240/hostAPKpull2/6시간상한은유지한다. 실패PAR후단순재실행이아니라관측계약/구현/PC검증을고친새ID로진행하며완료2자료는재측정하지않는다.

계획 `energy_ap_history_recovery_plan_v5/campaign_plan.json` SHA `a5a9e4257a44648230b86f567641749f8c46b2bfffaceeac2b2ae3e636fa4ba4`, child `5f5c3bf39b527162d53a6fd8ca888146af881278c3bd9c3c79bf02fe4735a74f`. v4claim의시작clock은v3원clock이므로v5도이를승계해PC수정시간포함6시간을초기화하지않는다. 남은시간≥16245+600초일때만Run진입한다. 최신승인으로새v5만단1회실행한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<동일현재A24 transport>' -ExpectedPlanSha256 'a5a9e4257a44648230b86f567641749f8c46b2bfffaceeac2b2ae3e636fa4ba4'
```

## v6 원동결 모형의 별도 전이 확인

v5는개발6적격을확보했으나 g=0.16229091917947994의교차history gate가둘다실패했다. 회복30초: 원APMAE평균0.168262°C/후보0.216477°C, 180초: 원0.169161°C/후보0.316622°C. 원모형의cooling opposite는전부false이고candidate도냉각방향보다는절대AP/장기초기상태전용오차가문제다. 초기입력범위도다르다: 원모형은target부하전AP/유휴전력으로초기화, history후보는conditioning전AP와전체등록이력만으로propagate한다. 따라서차이를새g항물리메커니즘의실패하나로단정하지않는다.

최신사용자자율진행승인범위에서남은예정확인6을 **기존원동결모형의새프로토콜전이확인**으로사전고정한다. 원모형은이번개발6으로계수를적합하지않았고원SHA/β/k/g0은불변이다. v5의gate실패는완료로고치지않고새v6ID를쓴다. 다른후보/새구조/재적합/정확도허용폭변경/기존g기준완화는0. 기존원모형을유지할실제이유는6개개발자료의AP오차/냉각방향이더좋았기때문이며그선택은개발결과를본뒤이뤄졌다는사실을공개한다. 다음6확인은선택에사용하지않고사전에모두고정한뒤측정한다.

실패한g0.162후보는원계수그대로고정한 **보조비교**다. 독립자료에서그차이를관찰하되기존gate 실패・미채택을소급바꾸지않는다. 원모형과보조비교모두실제일정조건부A 예측이며예정도착→일정B/정책우월성/실기기절감검증아니다. 부하전AP와초기유휴전력은허용된입력이고부하후AP/전류를예측입력이나계수적합에사용하지않는다. 부하전입력시점(target −30~+35초AP/−20~+30초idlepower)과conditioning초기입력의차이를보고한다.

새freeze분기는6개개발자료의현재적격성/sourcehash를검증하고원모형SHA・선택ORIGINAL_FROZEN・보조g와이전개발gate실패를한파일로봉인한다. `new_fit_calls=0`이며테스트에서fit/develop호출을금지해검증했다. modelcode/raw/default/RL/strict/experiment_ready=false는불변이다. callback/host/protocol은v5와동일하고APK 재빌드0. 마지막clientreap은원격producer종료증거와다르며, readonly재관측의원격중첩/계측비용은임의차감하지않는다.

원개발6은hash/manifest/trace/유효성재검사후read-only로재사용한다. **새확인6/960요청+48warmup=1008추론/runtime24/staging42파일/tracepull6/ADB45800・설치/push/pull0/10461초예약**. 누적physical상한2320/runtime56/staging98파일/14시도와미확인PAR상한200은그대로다. 시간도v3원시claim부터6시간으로수정/대기포함초기화0. 새추가후보/추가조건/확인반복0.

계획 `energy_ap_history_recovery_plan_v6/campaign_plan.json` SHA `ac518af1056306b544dc7a7dc81d8eab32538c0776e2c898574aaec801ca6a18`, child `db14ac7d3ae90a9eed60813c0a5333852374f9a6c395a48dfba3515f7e95505a`. 기존47경계중동결관련신규1+기존23=24검사다시통과, 실제source/APK/원자료/캐시Check기기0. 새동결분기를한번검사한뒤최신승인아래단1회Run한다. 종료후확인자료는재보정/추가측정결정에사용하지않고등록지표를전체6조건에서산출한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v6/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v6/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<동일현재A24 transport>' -ExpectedPlanSha256 'ac518af1056306b544dc7a7dc81d8eab32538c0776e2c898574aaec801ca6a18'
```
