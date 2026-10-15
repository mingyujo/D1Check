# 2026-10-15 최신 — 응답·AP 새 확인40 동결

- DEV8 실제1,144요청·출력PASS·정상회수 완료,누적41/81. 사용자가 J미판정 상태의 응답·AP 확인과 진단 병행을 명시 승인했다. [새 확인40 계약](team/a24-measurement-revision02-20261015/confirm40_after_dev8_20261015/README.md).
- 새40/5블록/5,720요청 전체순서·입력·분석·예산을 동결했다. 오늘 첫M128 ORDER→WAIT200→PAIR_G→BASE 최대4군, 기기16:33:25/저장16:38:25KST 종료를 유지한다. 신규APP21분·MAIN5분 여유가 없으면 미시작으로 보존한다.
- 원179소스/APK/MAIN gate 불변. 별도 SHA결합 coordinator의 전40승인 검산과 정확40 manifest의 앱parser PC검증PASS 후 최초 방문만 실행한다. DEV GPU177/후속179 실제 버전과 추가호환PC증거를 구분한다. 기존결과 합산/실패재실행0.
- 다음최대3: 등록첫4군 실행·회수; API원값·전하계단·동일구간 적분 진단; 결과·원장·재개문서/Git저장. J미판정·표면온도미검증·experiment_ready=false. 아래는 이전 이력.

# 2026-10-15 현재 작업 — DEV8 완료·CONFIRM 전 에너지 계측 원인 추적

- 사용자 총상한81회(기존33+DEV8+새확인40)를 명시 승인. 오늘 기기16:33:25/전체16:38:25 KST 종료는 유지한다. [연속 실행 v2](team/a24-measurement-revision02-20261015/dev_window01_continuation_20261015/README.md).
- C252 두군 회수: 각각252기한 내·출력504PASS·실패/미완료0. P95 GPU272.371/CPU116.471ms. MAIN 직전AP GPU26.3/CPU25.9℃로 달라 AP효과 미확정. CPU 앱 전 냉각 하한 오류는14:28:50 호스트만 중지/당시CPU소비0으로 보존했고 v2에서같은미시작ID를 처음실행했다.
- 별도179소스로 준비 전 냉각만 `안정60초·AP≤같은Tref`로 수정. 워밍업 후 MAIN의 ±0.5℃/60초/기울기/600초와 APK·과업·판정 불변. 순수4+기존40/전7군 승인결합/실제8manifest parser 검증 후 미시작7군만 진행한다. 확인40은 동결 전 미시작이다.
- DEV8全군정상회수·원장close·빈소유프로세스종료,15:24경실측종료. [로컬분석]은output/a24_suite_dev_window01_continuation_20261015/final_report. 예정1,144건전량완료·출력PASS·실패/미완료0. 이번8시도포함누적41/81,새확인40미시작/40잔여.
- 혼합BASE/WAIT/EDD는기한위반을보존한다. 병행은C96/D32전부기한내·긴급P95 1.426초,통로동시점유14.222초/앱추론호출겹침2.542초이다. 최고AP28.5℃(BASE28.1℃)로열절감·검증J절감은확인되지않았다.
- 최신사용자가CONFIRM전에에너지사용범위확정을우선지시한뒤실측계속/문제해결을요청했다. 다음CONFIRM범위질문은비동기확인중이며그동안기존원자료·코드추적/읽기전용진단을계속한다. 새CONFIRM실행기초안은output의미완성초안으로보존·실행0,동결미완료이다.
- 다음최대3: API→JSON→CSV→동일구간적분/전하변화검산; 여러유휴/CPU/GPU구간의계단·지연·누락/부호·단위분석; 검증범위/남은계측·DEV결과문서/Git저장. 원179/앱불변·추가진단APP/NN/세션0. J미판정·표면온도미검증·experiment_ready=false. 아래는 이전 이력이다.

# 2026-10-15 이전 작업 — 새시간창 실제 DEV8 기능검증

- 사용자14:08부터150~160분실측진행지시. [DEV8사전계약](team/a24-measurement-revision02-20261015/dev_window01_20261015/README.md): 최대8시도/1,144요청,기기16:33:25/저장포함16:38:25 KST종료. 원33시도보존·잔여31중8예약,확인40미시작·예산증액없음.
- 등록A24·SOC100%/비충전확인. C252 GPU→CPU,M128 BASE→WAIT200→PAIR_G→ORDER,L64 PAIR_G→BASE순서를결과전고정. 부하별3기준을첫준비후봉인/공유,후속군은앱밖냉각. 요청/기한/공통8warmup/관측창/응답·실제반환/APK동일.
- 실제설정결합PC검사에서새suite의source검사에옛controller경로가남은문제발견. 앱/START0에서새adapter만수정·PC-v1보존,원실측171불변. 새177소스/Python40/정확8manifest앱parser1/전8군전체승인결합검산PASS뒤실행한다.
- 활성원물Documents/A24R02S1,메타output/a24_suite_dev_window01_20261015. job/OWNER_WINDOW/실제원장을읽고중복실행금지. 다음최대3: DEV8순차실행; 각군품질/전체분모/반환회수; 기한내보고·안전종료/Git저장. J불가/표면온도미검증/experiment_ready=false. 아래는이력이다.

# 2026-10-15 이전 작업 — 8군·확인40 경로 PC 준비 완료

- 최신 지시: 저부하/혼합/확인40 경로를미리PC에서준비한다. [구현·검증](team/a24-measurement-revision02-20261015/suite_pc_20261015/README.md) · [재개필독](team/a24-measurement-revision02-20261015/MEASUREMENT_RUNBOOK.md).
- 별도suite host2파일/계획생성/공유기준·앱밖냉각/이미시도ID차단/정상회수후입증된빈자기프로세스정리/확인동결·예산·시간창차단을연결했다. Python39+새실제앱parser1 PASS,실행불가확인40·5,720요청·160binding·15기준그룹검산. 원171소스/APK불변,이번대상175파일SHA보존.
- 이번작업추가기기명령/설치/워밍업/추론/실측/START/claim/세션소비0. 원33시도/31미사용불변. 새40에최소9추가슬롯필요,실제개발추가분별도·증액/실행미승인. 확인40축소없음.
- 실제새경로기능검증/충전분리·시작조건/새시간창·예산/독립확인동결은아직필요. PCmock는기기증거로대체불가. J불가/표면온도미검증/experiment_ready=false.
- 다음최대3: 코드·문서/Git저장; 향후실측범위/예산/시간창을정한뒤새기능검증; 그증거로확인계약동결후에만새40승인결합. 현재는기기실행금지. 아래는이전이력이다.

# 2026-10-15 이전 작업 — 나머지 실측 사전 오류 점검만

- 최신 지시: 실측 없이 연결폰과나머지실측의사전오류만확인. [읽기전용기기/PC보고](team/a24-measurement-revision02-20261015/readiness_20261015/README.md) · [재개필독](team/a24-measurement-revision02-20261015/MEASUREMENT_RUNBOOK.md).
- 등록A24/설치APK/기존입력SHA/run-as/활성owner없음 확인. 단발배터리/온도조회,현재충전중. 기기조회30명령,설치/전송/앱시작/warmup/추론/START/claim/세션소비0,원장91파일불변.
- PC전용실행불가64복사본·256runtime·8,832요청의앱parser와scheduler/WAIT/worker반환18검사PASS. 옛미결합템플릿의SOC20/과거APK불일치를첫검사에서차단했고그실패도보존.원161/현재171실행소스불변.
- 장애: 새REV02 adapter는C252 DEV전용이므로L64/M128/CONFIRM은차단. 새host연결/동결/확인40계약이필요. 원64중33시도/31미사용이며이예산에맞춘확인축소승인없음. 새40은최소9추가슬롯필요·실행미승인. J불가/표면온도미검증/experiment_ready=false.
- 다음최대3: 점검문서/Git저장; PC에서새경로/확인계약을구체화; 별도실측지시전에는기기실행금지. 아래는이전이력이다.

# 2026-10-15 이전 작업 — 묶음04 측정 종료·실측 재개 문서

- **실측 재개 시 필독:** [현재 실측 원장·계획·중단 경계](team/a24-measurement-revision02-20261015/MEASUREMENT_RUNBOOK.md). 대화 기억 대신 이 문서와 실제 원장·Git을 대조하며, 단계 종료 때 갱신한다.
- [묶음04 결과](results/a24_revision02_20261015/prepared_block04/README.md): GPU/CPU 각252기한 내·출력504 PASS·실패/미완료0.12:55:25 KST에 실제 반환·저널 close·회수·실행 종료. 사용자 상한13:20 전에 종료했고 추가조건0이다.
- 묶음03 GPU는본요청0·워밍업8·AP28.2~29.5℃/마지막28.5℃로27.6±0.5℃ 사전거절,CPU미시도. DRAINED/close/빈 소유프로세스 종료 확인. 준비 전 기준의 실행 가능성 문제로 기록하고 이전 결과와 합산하지 않는다.
- 원28+W1두+묶음03한+현재두 시도=33,미사용31. 원161소스/APK/controller 불변,새171파일이 실제 실행 커밋94337e6과 일치. J불가·표면온도미검증·experiment_ready=false 유지. PC순수/사건21PASS,새 실제 두manifest parser 강제재실행 PASS.
- CPU P95=116.581ms/GPU273.369ms. AP평균GPU29.4666/CPU29.8679℃지만 시작도GPU28.6/CPU29.0℃로 달라 열효과는미확정이다. 다음최대3: 결과/재개문서/Git저장; 다음시간창에서잔여31의DEV/동결/확인배분고정; 새ID·사전조건검증후에만실측. 아래는이력이다.

# 2026-10-15 현재 작업 — REV02 현재값 기준 묶음03

- 최신 지시: 현재 온도 기준으로 GPU부터 다시 수행,12:50보다 늦어도 허용. [새 묶음03](team/a24-measurement-revision02-20261015/current_block03/README.md)의27.6℃를 새 본요청 전에 봉인했다. GPU→CPU 최대2조건, 상한13:20 KST. 새 앱은21분/START는5분 여유가 필요하다.
- 기존 W1은 GPU252/252 기한 내·출력252 PASS·P95=271.841ms. CPU는26.1±0.5℃ 불일치로600초 사전거절,본요청0·워밍업8·예정252미완료. 실제 DRAINED/close/빈 소유프로세스 종료를 확인했다. 이전 결과와 새 반복을 합산하지 않는다.
- 앱 없이 추가 대기 관측 후 GPU 우선 지시로 대기 중 CPU 후속을 앱0/START0에서 취소했다. 원28+W1두 시도 보존, 새 최대2는 미사용34에서 배정한다. 원161소스/APK 불변, 새170파일SHA 고정. J계산불가·표면온도미검증·experiment_ready=false.
- 새 실제 두 설정의 앱 parser/승인 PASS,12:24 GPU 준비/SOC86%·비충전 확인. 다음최대3: 두 조건 실행·회수; 미완료 포함 별도 분석; 종료 확인·Git 저장. 아래는 이전 이력이다.

# 2026-10-15 현재 작업 — A24-INITIAL-STATE-REV02 (설계 전용)

- 최신 지시: 개정 실험으로 분리하고 실측은 진행하지 않는다. 기존 controller/감독/logcat 중지, 앱 DRAINED·journal close/본요청0 확인·회수 후 빈 프로세스 종료. 재연결돼도 자동 재개하지 않는다.
- [개정 설계](team/a24-measurement-revision02-20261015/README.md): 부하별 비교 묶음의 첫 본요청 전 최초 유효 AP 이력으로 기준을 정하고, 묶음 내 모든 군에 같은 기준 적용. 정책별 재기준·결과에 따른 기준 선택·기존 결과 합산 금지. 실행권한0/실행기미구현/experiment_ready=false.
- 기존 확인40은 정상2/AP사전거절1/사용자중지전준비1/미시도36. 기존 총64 중28시도·36미시도, 실패·중지 재실행0. 원 계획/동결161소스/APK·원물·기존 정책/학습/다른기기 보존. 새32세션은 제안이며 승인·예산 이관·새UUID발급0.
- PC 기준선택/고정기준·시계/gap·예산/버전분리·순서균형 fixture14개 및 계약 검사 PASS. [검증/SHA](team/a24-measurement-revision02-20261015/PC_VERIFICATION.json). PC 검산은 새 host/APK/실기기 검증이 아니다.
- 개정의 기기명령/워밍업/추론/계측/START/claim/세션소비0. 중지 후에는 이전 준비앱 종료 확인·읽기전용 회수만 했다. 검증J=null·실제표면온도/수치예측미검증 유지.
- 다음최대3(PC만): 묶음기준 봉인/승인SHA를 연결할 별도 host 설계; 새 원장/파서·APK 호환검사 계획; 향후 명시적 실측 지시가 있을 때만 미사용 예산 이관·실행동결 검토. 아래는 이전 작업 이력이다.

# 2026-10-15 현재 작업 — A24-MEASURE-01

- 사용자 실제 측정 승인: SOC10% 이상·같은 기기 단절 최대20분 대기. 원64슬롯/모델/입력/기한/작업량 보존. 실패 슬롯 재실행·대체0. [원인·범위](team/a24-laptop-measurements-20261014/MEASUREMENT_PROGRESS.md).
- I4/F4/DEV16 전체24시도 보존. I4는 준비환경 결함으로 START 전 실패, F1은 AP gate 거절. F2 원장FAIL 뒤 동일 실행의252완료를 읽기전용 회수/검산. F3/F4 정상 회수, DEV15정상+1통신 PRESTART 거절. DEV 예정2288요청 전부 표에 보존, 정상15세션 실패/미완료0.
- 초깃값은 common prepared runtime의 고정 준비 마지막60초 median AP28.5℃를 사용; 최초idle27.6℃와거절을 보존. ±0.5℃/slope0.1℃/분/최대600초 유지. API 전류·전하 scale불일치로 검증J=null, 임의1000배보정0. HAL readout/cache age·실제 표면온도 미검증, 정확도 PASS 주장0.
- 확인 v10: 앱단위 KEEP_SCREEN_ON만 추가, 유휴는 runtime0×2warmup=실제0이라는 원 선언 유지. 관련JVM30/host50/연결6/조립2/분석3 PASS. 새APK`6fbe5c08…0bfd8b` 실제 설치SHA일치. 기존실측APK`eab8e449…5b883e`/자료/실패 보존.
- CONFIRM40: 2정상/1PRESTART 거절/37미시도. 06:48 온도 gate(AP29.1>상한29.0) 중단, 08:20 연결복구20분 종료. 10:03 재연결 후 준비, 10:12 사용자 설계전용/실측중지 지시로 종료. 해당 M128 ORDER는 START0·본요청0·중지 전warmup8·UNFINISHED128을 보존. [중단시점 부분 회수](results/a24_laptop_measurement_20261015_v1/README.md). 사전 봉인: [분석](team/a24-laptop-measurements-20261014/CONFIRM_ANALYSIS_CONTRACT_V10.json), [동결](team/a24-laptop-measurements-20261014/CONFIRM_FREEZE_V10.json), [원장SHA](team/a24-laptop-measurements-20261014/PRIOR_STAGE_ATTEMPTS_SHA_V1.json). 새8군 수치예측은명시적없음/모형정확도주장없음. 확인중 코드/설정/계수/선정 변경 없음.
- 다음최대3: 동일 동결계약으로 미시도37등록슬롯; 거절/실패 보존·종료증거 확인 후 후속슬롯만 진행; 실제 시도 종료 뒤 전체분모 분석/작은 결과 공유. 부분회수 CSV·그림·오프라인참조 무결성 검산PASS. 데스크톱학습/EP814/원WIP12개/다른기기변경0; strict·기본정책·experiment_ready=false 유지. 아래PC준비는과거이력.

# 2026-10-15 현재 작업 — A24-LAPTOP-PREP-01

- PC 구현·단위/mock 검증·APK 빌드 완료 / DEVICE_UNVERIFIED. 별도 branch `codex/a24-laptop-prep-20261014`에서 작업했고 원 worktree HEAD `0d4ddc6`와 사용자 추적 변경12개·다른 worktree를 보존했다. [준비 보고서](team/a24-laptop-measurements-20261014/PREPARATION_REPORT.md).
- 새 CPU/GPU opt-in·FIFO/EDD·직렬/CG_DC·WAIT200·120초 dispatch/실제 반환·210초 로그·host 원물 검산/회수를 구현했다. 최종 APK `32c42c32…568e9ef`, 새 JVM18·기존 modelProbe264·계약13 PASS. 최종 host 수와 검증 코드 바이트는 [PC_VERIFICATION.json](team/a24-laptop-measurements-20261014/PC_VERIFICATION.json)/[SOURCE_SHA256.json](team/a24-laptop-measurements-20261014/SOURCE_SHA256.json)를 따른다.
- 데스크톱 `ec8a1424` 참고73파일·GEN002 소스59개·프로필8개 인수/SHA 완료. [인수 기록](team/a24-laptop-measurements-20261014/DESKTOP_REFERENCE_INTAKE.md), [분석 계약 초안](team/a24-laptop-measurements-20261014/ANALYSIS_CONTRACT_DRAFT.md). 새8군 예측/최종 분석은 미동결이며 기존 가정층을 실기기 검증으로 승격하지 않는다.
- 미소비 계획 `A24-LAPTOP-PC-PREP-20261014-03`: I4→F4→DEV16→동결→CONFIRM40, 총64세션·26bank·8832예정요청. plan SHA `82d5108d…93855`; 모든64manifest 허가false/DEVICE_UNVERIFIED, 활성 registry/device_runs 없음.
- 실제 기기 연결/조회/명령/설치/warmup/NN/계측/Run/START/claim/세션 소비0. 데스크톱 EP813 보존·EP814 정확 복구 불가/자동 재수집 금지는 사용자 인계로 유지하며 학습/시뮬레이션을 재시작하지 않았다. 기본·strict·experiment_ready=false 유지.
- 다음 최대3: 별도 실측 지시 후 기기identity/위임/품질/AP·gauge/USB·회수 내구성 확인; I4/F4/DEV16의 모든 시도 보존; 초기·계측 gate와 분석/예측 또는 명시적 없음 동결 후에만 CONFIRM40.
- 장애/미검증: AP 센서·Tref·gap·정확도 기준·예측 adapter/최종 분석 코드 미확인/미동결. C드라이브 약1.3GB로 원물 수집 공간 확보 필요. journal 최종fd.sync/close는 host 별도 미관측. [실기기 목록](team/a24-laptop-measurements-20261014/DEVICE_CHECKLIST.md).
- 검증 대상은 source base`38d34c6`+당시 미커밋152파일 SHA, runtime 이식`7475b183`, 고정 APK 바이트다. 아래는 요청 branch의 과거 STATUS이며 현재 완료 범위와 구분한다. 이번 작업은 여기서 종료하며 실제 측정을 시작하지 않는다.

# D1Check 현재 상태

- 갱신: 2026-09-17 / CALIB-01B 종료 문서 정리
- 현재 작업 ID: `CALIB-01C-INPUT` — A24 실제 이미지 calibration 입력 준비
- CALIB-01B: completed / `CALIB_01B_PASS`. FIX4까지 production 구현·host 검증·최종 읽기 전용 감사를 완료했다. A24 이미지 종단간 실측이나 최종 스케줄러 효과 검증의 완료를 뜻하지 않는다.
- 기준 저장소: branch `master`, HEAD `38386b94a5a4aaf3d9b9da077e40af71e342dadf` (`Define end-to-end calibration protocol`). 로컬 `origin/master`도 동일하다.
- Git 상태: index 0개, CALIB production/test/문서는 unstaged/untracked이며 아직 커밋되지 않았다. 기존 사용자 변경 4개와 diagnostic 결과 보고서 9개를 보존한다.
- 직접 실기기 범위: Galaxy A24만 해당. S26 새 calibration·설치·앱 실행·스케줄러 검증은 `OUT_OF_SCOPE_NON_BLOCKING`; 기존 formal 80슬롯 보조 사례만 유지한다.
- 긴급·일반 절대 마감시간 상태: `calibration_pending`. 입력·환경 준비와 A24 pilot 안정성/정확도 gate 전에는 고정하지 않는다.

## Git 및 완료된 작업

- `SETUP-01`: completed. 문서 설치 커밋 `1c9d759589e06b48a30e8f2311e3141af8ad4da6` 및 완료 당시 tracking ref/reflog의 일반 push 기록 확인. live 원격 재조회는 별도 미확인이다.
- diagnostic v2는 기존 커밋에 포함돼 있다. CALIB-01B 미커밋 변경과 구분하며 기존 v1/v2 schema·경로·latency 의미는 보존한다.
- `AUDIT-A24-01`, `DIAGNOSTIC-V2-01`, `AUDIT-S26-01`, `DEFINE-01`, `CALIB-01A`, `CALIB-01B`: completed.
- 기존 변경·커밋 제외: `.idea/deploymentTargetSelector.xml`, `.idea/gradle.xml`, `.idea/misc.xml`, app `MainActivity.kt`의 EOF 빈 줄, 모든 `DIAGNOSTIC_V2_*_RESULT.txt`.
- build/cache/APK·기존 A24/S26 데이터·분석·사용자 개인 변경도 제외한다. 소스·테스트·보고서·기존 데이터는 이번 종료 문서 작업에서 수정하지 않는다.
- 공식 시나리오·KPI·사전적 목적함수는 [PROJECT_PLAN.md](PROJECT_PLAN.md)와 [DECISIONS.md](DECISIONS.md)를 따른다. 실패·거절·만료는 도착 분모에 남기고, 완료 P95와 전체 도착 기준 성공률을 함께 보고한다.

## CALIB-01B 최종 검증 증거

검증 대상은 위 HEAD + 미커밋 CALIB-01B FIX4 production/test다. 2026-09-17 사용자 로컬 Temurin 17.0.20.1+1에서 `gradlew.bat --no-daemon testDebugUnitTest lintDebug assembleDebug --rerun-tasks`가 BUILD SUCCESSFUL / exit 0, 161 actionable tasks: 161 executed였다. 최종 감사에서 최신 XML/SARIF·APK·코드 관계를 직접 확인했다. 이번 문서 정리에서는 테스트·빌드를 재실행하지 않았다.

| 모듈 | Suite/Test | Failure/Error/Skip | lint Error/Warning | XML 생성 시각 |
| --- | --- | --- | --- | --- |
| app | 3/9 | 0/0/0 | 0/20 | 2026-09-17 11:45:45 |
| benchmark-runner | 18/97 | 0/0/0 | 0/54 | 2026-09-17 11:48:13 |
| telemetry-contract | 5/13 | 0/0/0 | 0/2 | 2026-09-17 11:46:06 |
| 합계 | 26/119 | 0/0/0 | 0/76 | 최신 로컬 전체 실행 |

- 실제 실행·통과: artifact validator 8/8, 이미지 integration 3/3, production pipeline 6/6, Activity entry 1/1. 중첩 provenance 미등재/실제 hash 등재 및 production finalizer 거부, 루트-only self-hash 제외가 검증됐다.
- Python 전체: 195건·failure/error 0·기존 skip 1, exit 0. skip은 `test_completed_trace_on_resume_rejects_symlinked_trace`의 Windows symlink 생성 권한 부재로 CALIB 핵심 검증이 아니다. calibration CLI targeted 7/7도 통과했다.
- `python -m compileall -q tools`, logger self-test, assembleDebug: PASS. CALIB 관련 lint 24건은 UseKtx 2·SetTextI18n 22로 중대한 보안·정확성 경고는 발견되지 않았다.
- 증거 위치: 각 모듈 `build/test-results/testDebugUnitTest/TEST-*.xml`, `build/reports/lint-results-debug.sarif`; 성공 로그 `.gradle-user/daemon/9.5.0/daemon-24276.out.log`.
- image-v3 configuration SHA-256: `03e507dea1d4111681b6c1120fab7729967a19e49712ccc05d2e72e4f7762cf5`. Kotlin/host CLI/docs 일치. EXIF 부재=1, 명시 1~8만 허용, mirror/회전 후 crop/resize, decode cause 보존 계약 유지.
- runner APK: `benchmark-runner/build/outputs/apk/debug/benchmark-runner-debug.apk`, 55,735,474 bytes, 2026-09-17 11:46:41. SHA-256 `9C5F0C8C939371311ABE2CECDC9198F5935697D5E178B01A232940079EE5A04B`.
- app APK: `app/build/outputs/apk/debug/app-debug.apk`, 5,652,356 bytes, 2026-09-17 11:45:20. SHA-256 `9796C828E9720E28E88A788D1DC3C0DFB4F591FE425F8BA78D4E7BEDE33DC8A6`.
- scoped diff check 통과, index 비어 있음. 전체 diff check의 기존 app EOF 빈 줄은 보존·제외한다. 구현 검증, 실기기 calibration, 스케줄러 효과 입증은 별도 상태다.

## Resolved history

- 2026-09-16~17 sandbox의 Google Maven/AndroidX resolve, Robolectric jar 접근·`C:\.robolectric-download-lock`, debug signing lock 실패는 과거 환경 이력이다. FIX2 전체의 28건·FIX4 targeted 8건/전체 30건 실패는 테스트 본문 전 환경 실패였고, 위 최신 사용자 로컬 전체 119/119 및 assembleDebug 성공으로 완료 대기가 해제됐다. sandbox 권한 제한 자체가 변경됐다고 주장하지 않는다.
- FIX1은 이미지 fixture 리소스와 production writer/validator 계약, FIX2는 terminal/deadline·thermal·A24-only·입력 검증을 정리했다. FIX3 EXIF/decode/Matrix 및 FIX4 중첩 provenance 우회 수정은 최신 동작 테스트와 최종 감사로 완료됐다.
- 과거 FIX3의 이미지 테스트 실패 3건과 이전 미확인·INCOMPLETE 기록은 종료 판정이 아니다. 이전 PASS를 새 버전에 전용하지 않고 최신 FIX4 증거로 `CALIB_01B_PASS`를 확정했다.

## 현재 작업·완료 조건과 실측 사전조건

`CALIB-01C-INPUT`의 완료 조건은 라이선스·ground-truth를 확인한 실제 이미지 8개(최소 4 class, class당 2개), verified 1001-line label mapping 및 image-v3 manifest/provenance를 고정하는 것이다. 각 이미지 bytes/size/MIME/크기/EXIF·라벨·APK hash를 production 계약에 맞춰 확인해야 한다. 임의 이미지 생성·다운로드나 1×1 fixture의 대표/정확도 데이터 승격은 하지 않는다.

- representative image set과 verified label mapping은 아직 준비되지 않았다. 현재 입력 준비는 A24만 대상이며 S26 end-to-end 결과를 주장하지 않는다.
- A24 baseline 실측 전 host AP/PA/SKIN 시계열, cooling/stability gate와 session/monotonic 시간 연결이 필요하다. 기존 logger 수집 기능은 있지만 calibration과 자동 연결돼 있지 않다. 앱의 battery temperature/Android thermal status로 AP/PA/SKIN을 대체했다고 주장하지 않는다.
- baseline pilot/formal/stress 분리, baseline 시작 status 0/1, formal 사전 policy/hash 계약 유지. THERMAL_STRESS는 baseline에 합산하지 않는다.
- A24 strict CompatibilityList GPU 진입 smoke와 full-delegation/fallback 외부 증거가 남아 있다. GPU 실패의 silent CPU fallback·S26 override·기기 모델 기반 우회는 금지한다.
- 긴급 output-ready/일반 durable persistence 완료는 늦어도 SUCCEEDED/LATE다. 미완료 만료만 EXPIRED이고 비성공에는 결과가 없어야 한다. 늦은 성공은 전체 완료율에는 포함하지만 기한 내 완료율에는 포함하지 않는다.
- 순수 Interpreter.run() 구간 밖에서 I/O·전처리·후처리·checksum·telemetry·저장을 수행한다. 기존 tensor-only 80슬롯은 이미지 종단간 지연의 대체 근거가 아니다.

## 기존 실기기 증거 위치와 해석 한계

아래는 기존에 확인한 자료로, 이번 종료 문서 작업에서 재측정·재처리하지 않았다.

| 자료 | 경로 및 기존 확인 범위 |
| --- | --- |
| A24 formal 80슬롯 | `C:\Users\LG\Documents\D1Check_Analysis\D1Check_A24_analysis_corrected_20260912_233544\CORRECTED_ANALYSIS_RESULT.txt`. CPU 중앙 약 41.2 ms, GPU 약 131.6 ms, 비율 약 3.196. CPU 1/2/4 차이 작음, 위치 민감도에서도 CPU 우세 방향 유지 |
| A24 diagnostic off | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_off_20260915_013906`. 기존 결과 루트 |
| A24 diagnostic on | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_on_retry3_20260915_123235`. 기존 manifest/runs |
| A24 trace | 위 on 루트의 `runs\a04ef424-1cac-4177-aa89-4cd7f35fb2c4\diagnostics\d1check-630699bd-98c0-4e8f-9c3e-b7273bad2005.perfetto-trace`, 3,381,748 bytes |
| S26 formal 보조자료 | `C:\Users\LG\Documents\카카오톡 받은 파일\S26_formal_strict_results.zip`. 원시자료 감사/지연 재계산 통과. GPU duty별 약 1.062~1.201배 빠름, 20개 대응 비교 모두 GPU 지연/AP 상승 낮음. 모든 GPU run 31/31 full delegation·fallback 없음 |

- A24 위치 변경·주변온도 제한은 유지한다. S26 compatibility-list false/override true를 기존 formal 비교에 공시하고 dataset manifest accuracy/pilot 문구와 재시도 failure 기록의 불완전성을 유지한다.
- 실제 FP32/FP16, GPU H2D/GPU/D2H·fence timing은 unknown이다. 미검증 에너지 단위로 J/mWh나 에너지 절감을 주장하지 않는다. 과거 측정 APK와 Git 소스의 완전한 cryptographic binding도 미확보다.
- trace content audit 보고서의 현재 경로·trace/binary hash는 미확인이다. `DIAGNOSTIC_V2_TRACE_CONTENT_AUDIT.txt`는 이전 `C:\Users\LG\Documents` 조사에서 찾지 못했으며 보고 기반 결론을 새 독립 증거로 승격하지 않는다.

## 다음 행동 (최대 3개)

1. 실제 이미지 8개의 출처·라이선스·ground-truth와 verified 1001-line label mapping을 확정한다.
2. image-v3·현재 runner APK hash에 맞는 입력 bundle/manifest/provenance를 준비하고 production 입력 계약으로 검증한다.
3. 입력 완료 후 host thermal/cooling 연결과 A24 strict GPU smoke의 별도 계획·승인을 확인한다. 모든 사전조건 전에는 설치·앱 실행·calibration을 시작하지 않는다.

이번 종료 작업: 위 세 문서만 정리했으며 테스트·빌드·ADB·설치·앱·실기기·Perfetto·stage·commit·push는 수행하지 않았다.
