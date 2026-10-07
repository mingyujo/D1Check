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
