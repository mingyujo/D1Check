# D1Check 현재 상태

## 2026-09-25 지정 v1 실행 재요청 — 중복 실행 gate로 미진입

- 실제 시작 HEAD `6f8d950`/로컬·원격일치/clean. 요청의 `bceec84` 이후 변경은 이전 배터리 gate 종료 문서 commit이다. 새101.5분 예산 승인 요청은 확인했으나 지정된 `collection_recovery_plan_v1/RUN_AFTER_APPROVAL.ps1`은 이미 소비된 복구/workflow를 가리킨다.
- 원 workflow claim과 `stopped_no_resume`, recovery `failed/preflight/battery level gate failed`를 직접 확인했다. 수집registry 부재/0세션은 통합 계획 재실행 허가가 아니다. `d1_collection_recovery.run`의 `bundle already used` 조건 및 사용자 지시의 종료 계획 재개 금지를 그대로 적용했다.
- **이번 호출은 스크립트/ADB/기기조회/전송/설치/세션/추론 모두0**, 새 소비 기록 없음. 현재 배터리·연결·화면 상태는 조회하지 않아 미확인이다. 이전 원본/소비량/계획 hash와 experiment_ready=false 유지. 테스트/빌드 반복 없음.
- 근거: 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/collection_recovery_reentry_check_20260925/REPORT.json`. 기존 종료 보고서는 바로 아래 경로를 따른다.
- 다음은 승인된 범위와 기존 종료 기록을 분리하는 **새 식별자·출력·소비 경로의 실행 계획 재발행**이다. 이번에는 지정 계획 충돌 시 실행하지 말라는 조건에 따라 실행을 보류했으며, 과거 소비 상태를 초기화하거나 새 계획으로 임의 전환하지 않았다.

## 2026-09-24 INSTALL-RECOVERY-01 / COLLECT-02 — 승인 실행·배터리 gate 종료

- 시작 `bceec84`/clean. [종료 결과](ARRIVAL_INSTALL_RECOVERY_20260924.md). 계획/소스/APK/manifest·미소비 확인 후 스크립트1회. **배터리50%<시작55%로복구preflight중단. 후보전송0·설치0·세션0/12·진단0/48·warmup0/96·명시적추론0/144**, retry/대체/추가0. 개발/확인각6미시도, 실패세션0/복구실패1.
- 기기/fingerprint/서명확인·기존설치APK회수1회86.390초. 후보push와구분. 명령12개정상반환, 출력/시점/exit보존. hostcleanup/프로세스부재·thermal0확인, 앱cleanup N/A. 기존APK9019b85d…2c0유지. 설정변경없음, awake/앱memorygate는미진입.
- 복구91.156초·workflow92.297초, 최초조회tool wall상한포함92.792초. 냉각/수집0. 복구와workflow소비·종료/재개금지. 수집registry는미생성이지만통합계획재실행불가.
- 새표본/동결/확인/PC연결없음. experiment_ready=false·병행차단·40값/20null/FAIL/부분결과/과거원인미확정보존. 완료된PC검증·빌드반복없음.
- 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/collection_recovery_execution_v1`의FINAL_REPORT/FINAL_RECEIPT/REPRODUCE.py/GIT_FINAL, `install_recovery_run_v1`의원본/receipt와`collection_recovery_workflow_v1`의claim/stopped를보존. 문서만commit/push.
- 다음: (1) 배터리시작55%이상여유충전후비충전상태준비, (2) 새실행계획PC준비, (3) 별도승인/gate후복구·수집. 기존종료계획은초기화/재개하지않는다. 아래는준비당시이력이다.

## 2026-09-24 ARRIVAL-INSTALL-RECOVERY-01 / COLLECT-02 — PC 준비 완료

- 시작 `b4c6e23`/clean, 기존 COLLECT-01의 install120초 timeout·세션0·종료 기록 보존. [복구 원인 분석·새 실행 계약](ARRIVAL_INSTALL_RECOVERY_20260924.md). 이전 성공/실패 APK 차이16,384bytes, 같은install-r/120초이며 크기·GPU·전송 원인 확정 근거 없음. timeout 부분 stdout/stderr 미보존을 확인했다.
- 새 host 명령 기록: 부분 bytes·시작/종료/timeout/exit·client tree 종료·조회 실패 보존. staged push→원격hash→pm install-r→설치본hash로 명령 단계를 분리. 설치timeout120초 유지. exact APK이면 설치생략, 새 수집에서는 재설치 금지·동일설치본 필수gate.
- PC28건(복구15+collection13) 통과, 실제 PC 자식트리 timeout 포함. APK/서명/Android source 대응·새manifest12·dry-run 확인. APK 재빌드/ADB/설치/실측 없음. experiment_ready=false 및40값/20null/FAIL/부분결과 불변.
- **미승인 제안**: 복구설치최대1/전송1·600초 + 새수집개발6→동결→확인6/48진단/96warmup·5490초, 합6090초=101.5분. 예상35~50분·냉각24분 포함, retry/대체/추가0. 기존 승인/미시도분 재사용 아님.
- 외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `collection_recovery_plan_v1`(recovery_plan/collection_plan/manifests/RUN_AFTER_APPROVAL.ps1), `install_recovery_pc_v1`(FINAL_REPORT/VERIFICATION/tests/재현명령/GIT_FINAL). 후보APK는기존integrated_collection_apk_v1그대로. 새출력/registry미생성.
- 다음: (1) 새 통합예산 승인, (2) 당일gate→복구verified/cleanup→새수집동결/확인, (3) 적격자료에한해PC연결/정책비교요건검토. 이번에는 PC 준비만 수행했다. 원격에는 관련host소스/테스트/문서만 반영한다.

## 2026-09-24 ARRIVAL-COLLECT-01 — 승인 실행 중단·설치 timeout

- 시작 `0338433`/clean. [실행 결과·중단 근거](ARRIVAL_INTEGRATED_COLLECTION_20260924.md). planv2 동일성·미소비·A24/서명/설치 전 환경gate 확인 후 승인 스크립트1회 실행. **설치1회가120초 timeout, 세션0/12·진단0/48·warmup0/96·총명시적추론0/144.** 개발6·확인6 모두 미시도, 세션 전 기술적 실패1. retry·대체·추가0.
- host cleanup·프로세스 부재 확인, 앱 cleanup은 미시작N/A. 설치 후 읽기 전용 조회에서 이전 APK9019b85d…2c0 유지, 후보d8db6963…34bc 설치 성공 없음. signer 일치이며 전송/무선/패키지 처리 원인 미확정. 화면/시스템 설정 변경 없음.
- claim→cleanup195.893초, 마지막 추가조회까지283.200초(PC대기 포함); 최초 기기조회 tool wall0.699초를 합해도283.899초. 냉각·세션0, 승인5490초 이내. 원본 stopped의 일반 unknown은 보존하고 launch0 근거를 별도 receipt에 명시했다.
- 개발 claim+전체 stopped로 **종료·재개 금지**. 새 표본/동결/확인/PC연결 없음, experiment_ready=false·40값/20null/FAIL/부분결과/과거 원인 미확정 유지. 관련 코드 변경/재빌드/테스트 반복 없음.
- 외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `integrated_collection_run_v1/development`(원본), `collection_execution_registry/ARRIVAL-COLLECT-01`(소비/중단), `integrated_collection_execution_v1`(FINAL_REPORT/FINAL_RECEIPT/REPRODUCE.py/GIT_FINAL). Git에는 문서만 반영한다.
- 다음: (1) 부분 설치 출력·단계 시간을 보존하는 새 설치 진단 PC 준비, (2) 별도 승인 후 기기 진단, (3) 설치 문제와 수집 gate 해결 뒤 새 수집/독립 평가 준비. 현 계획/미시도분 자동 재개 금지. 아래 준비 상태는 이전 이력이다.

## 2026-09-24 ARRIVAL-COLLECT-01 — 통합 수집 PC 준비 완료·새 실측 미승인

- 시작 `0eae7c0`, 작업 브랜치 유지. 사용자 일시 중단 후 같은 변경에서 재개했다. [수집 계약·코드·예산·명령](ARRIVAL_INTEGRATED_COLLECTION_20260924.md). 기존40값/20null/FAIL/부분결과/종료계획 불변.
- 새 Android `COLLECTION_DISPATCH_DEV_1`: 엄격 PC 정책 active(CPU fallback·전체직렬)와 고정 배정+shadow 분리. 판단/기록/D→A·priority별후보/선택없음·실제lane해제 기록. 별도 namespace, 기존 정책 의미 유지. 이것은 완전한 B3/P가 아니다.
- Kotlin28·기존 Python timing9 통과본 유지, 최종 Python collection13/13(skip0)·Kotlin-PC snapshot12 일치. APK 빌드·PC 서명·입력/manifest·실행 스크립트 check 통과. 재개 후 host 동결 전 회수 hash 검사만 보완해 후보plan v2. Android 빌드 반복 없음.
- **실기기/ADB/설치/추론/본simulation 미실행, experiment_ready=false**. 새 예산 제안: 개발6→기술통계동결→확인6,12세션/48진단/96warmup/설치2, retry·대체·추가0, 예상32~45분·상한91.5분. 이전 승인 예산 재사용 금지.
- 외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `integrated_collection_plan_v2`(계획SHA914a43ce…0566·manifest12·RUN_AFTER_APPROVAL.ps1), `integrated_collection_apk_v1`, `integrated_collection_pc_v1`(FINAL_REPORT/VERIFICATION/재현명령). 출력/registry 미생성 확인, v1후보 보존. 원격 공유에는 코드/문서만 포함한다.
- 다음: (1) 새 예산 승인, (2) 당일identity·서명·환경gate 후 계획대로 개발/동결/확인, (3) 지원범위/B2/B3/P 차별성과 독립평가 요건 검토. 추가 실측 자동 실행 없음. 최종 commit·원격일치·worktree는 외부 GIT_FINAL.json에 기록한다.

## 2026-09-24 ARRIVAL-CAL03-CONNECT-01 — PC 추정 연결·실행 모델 완료

- 시작46b6c20/로컬·원격일치/clean. [새 계약·검증·재현 명령](ARRIVAL_CAL03_CONNECTION_20260924.md). 기존 CAL-03을 반복하지 않고 개발8세션32요청에서 priority별 공동 구간 통계를 별도 산출했다. 동결40값·확인 자료·기존20null 불변, 확인 자료 재튜닝 없음.
- 새 PC 정책 `CAL03_SOLO_CONDITIONAL_PC_DEV_1`에 후보 응답/점유·phase 잔여 예측 연결. adaptive D→A 미측정은null, 엄격CPU fallback/명시적 가정 모드 분리. UNKNOWN_OVERRUN·실제AVAILABLE까지busy 유지. Android Activity/기존 정책/APK는 변경하지 않음.
- 새 단독 이벤트 엔진: 완료와 독립된 도착, 응답O/P·worker_release·lane해제 구분, 예상/실현 분리, 전체 planned/arrived/미완료 분모. concurrency>1 차단. 8요청 PC 점검(판단1ms/도착지연0 가정) 완료이며 실측·본simulation·정책성능 검증 아님.
- PC21테스트 및 개발자료32요청 경계 호환 재생 통과. 초기 fixture 오류3건 수정 후 통과. Kotlin/전체build/기존감사/실기기 반복 없음. 외부 `cal03_connection_pc_v1`에 새 설정·벡터·재생·엔진점검·VERIFICATION/보고서/명령 보존.
- **experiment_ready=false**: adaptive D→A·부하 의존 준비/저장/callback·간섭·정확도 허용폭·새 앱 정책 검증 미충족. 완전한B3/P·정책 우월성 주장 없음. 기존FAIL/부분결과/종료계획/과거원인미확정 유지.
- 다음: (1) 새 정책 D→A/큐 부하 전이의 최소 개발 수집 설계, (2) 병행이 필요할 때만 별도 overlap 대조 설계, (3) B2/B3 차별성·독립 평가 요건 검토. 추가 실측 자동 실행 없음. 관련 새 소스/문서만commit·현재브랜치 정상push; 최종Git은 외부 GIT_FINAL.json.

## 2026-09-24 CAL-03 — 개발·동결·확인 완료

- 시작8fdb90d/clean/원격일치. 승인 예산 내 **개발8·확인8 완료, 설치2, 진단64·warmup128·명시적추론192**. 실패·미시도·retry·대체·추가0. [실행 계약·40슬롯 결과 근거](ARRIVAL_CAL03_EXECUTION_20260924.md).
- 화면 관측·회수10초 예약을 반영한 v3만 실행(plan9f7224e…8400). v1/v2 미실행 보존, APK·모델·요청 순서·추정 규칙·총예산 불변. 실행/cleanup은 host UTC 기준 약43.43분/상한121.5분. 앱/host cleanup 및 프로세스 부재16/16 확인, registry 소비 완료·재실행 금지.
- 개발 적격성 확인 후40개 구간값을 확인 전에 동결(fitf4f55b65…4106fb), 확인 claim/종료 hash 불변. 조건당 개발1·확인1 독립세션, 각4상관요청. 확인 자료로 재보정하지 않았다. 자료 적격성 PASS, 정확도/정책성능 PASS는 없음(performance_pass=null).
- S→O 최대 절대오차32.270ms. 탐지/GPU/긴급은 확인4/4가 개발중앙값 초과: 중앙값을 상한으로 사용 불가. 전체40슬롯의 값·오차는 외부 timing_cal03_analysis_v1/FINAL_REPORT.md 및 fit/confirmation JSON에 보존.
- 후속 lane 재사용48쌍·화면96표본 통과. 밝기81/수동/5시간 유지 조회, 설정·화면조작0. host snapshot 누적43.310초는 관측 비용이며 서비스시간에서 빼지 않음. 표본 사이 상태·병행 부하·다른 입력/기기·tail·과거 정지 원인은 미검증.
- PC20건+예약보완 후6건 회귀 PASS, 빌드/이전 진단 반복 없음. 원자료 등571파일 hash 확인·동기 journal16/16 없음. source/규칙/PC기록은 외부 timing_cal03_execution_preflight_v1, 원본/receipt는 timing_cal03_run_v1. 기존20null/UNKNOWN_OVERRUN/experiment_ready=false 및 기존FAIL·부분결과·종료계획·과거 미확인 소비량 보존.
- 다음: PC에서priority별 관측의 적용 범위와 적응형 D→A 미측정·초과 잔여시간 요건 정리. 추가 실측/정책 평가 자동 실행 없음. 관련 소스·문서만 commit·현재 브랜치 정상 push하며 최종 Git 상태는 외부 GIT_FINAL.json.

## 2026-09-24 ARRIVAL-STALL-OBS-DIAG-01 — 승인 진단 완료·CAL-03 PC 후보 준비

- 시작29b8543/원격일치/clean. [진단 계약·결과](ARRIVAL_STALL_OBSERVATION_DIAGNOSTIC_20260924.md). 앱수정/빌드없이 host독립관측·phase clock만추가해승인1회실행. **설치1성공·세션1완료/실패0·runtime4반환·warmup8·정규1·총추론9, 평가/retry/대체/추가0,209.390/600초**. 종료registry/no_resume.
- journal191/256·회수10파일hash/단계/trace검증, 앱cleanup/hostcleanup·프로세스부재확인. 마지막seq190 cleanup/succeeded Java99. 요청1개이므로실제후속lane재사용미검증. sync시간은보정에사용금지.
- 새host5초관측: Dozing/top-sleeping/isFrozen=false, kernel stack권한거부. 전체호출은완료됐으므로과거정지원인으로단정불가. CAL-02/이전통합실패원인미확정, 기존미확인호출수보존. 35/105초관측은정상완료로생략.
- PC: host20건·후속calibration15건 PASS, signature/manifest/dry-run·문서검사완료. 기존Kotlin/전체build반복없음. 실행source snapshot과후속PC수정source를별도보존. 외부root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`의`stall_observation_run_v1`(FINAL_REPORT/RECEIPT/POST_RUN_VERIFICATION), `stall_observation_pc_v1`(실행host), `timing_cal03_pc_v1`(후속host).
- [CAL-03 후보](ARRIVAL_TIMING_CAL03_PREPARATION_20260924.md): 새16세션/64진단/128warmup, 개발8→동결→확인8, retry/대체/추가0,45~60분/상한121.5분. 같은APK·sync journal없음·awake/interactive시작gate 추가. **미승인·미실행**, `timing_cal03_plan_v1/calibration_plan.json`, hash b184dea…d635. 이번진단승인으로실행하지않음.
- 기존198요청FAIL/fixed-split부분결과/종료계획/20null/experiment_ready=false/과거RawAdapter대응미확인유지. 다음: (1) CAL-03새예산·화면켜짐조건검토/승인, (2) 승인후identity/미소비/환경gate, (3) 개발품질검토·동결후확인. 추가진단자동실행없음. 관련소스·문서commit/정상push, 최종Git상태는외부GIT_FINAL.json.

## 2026-09-24 ARRIVAL-WARMUP-REQUEST-DIAG-01 — 승인 실행 중단·재시도 금지

- 시작 `adb7c01ca9ee34156952223b2dbfa1ec79d54274` / `feature/arrival-scheduling-20260923` / clean. 미소비·계획/APK/source·동일A24/서명·환경gate 후 script1회 실행. [실패 판독·다음 행동](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md). 아래 준비/미승인 상태는 당시 이력이다.
- **업데이트설치1성공·세션1시도/완료0/기술적실패1/미시도0.** host poll125초 소진, 전체311.344/600초. runtime시작의도2/반환1(실제범위1~4); warmup0~8·정규0~1·총추론0~9 미확인. 기록0을실제0으로대체하지 않는다. 평가0/retry/대체/추가0. no_resume/closed 유지.
- 마지막seq25: classification_GPU interpreter_construction/start, GPU Java106. CPU분류반환확인, 이후생성/모든warmup/정규요청/앱cleanup미관측. 앱Future30·watchdog120종료기록도없고회수시PID25426생존. native/VM/lifecycle/기록정지 구분에필요한stack은없으며 GPU/CAL-02동일원인확정불가.
- journal유효26/256·잘린suffix/overflow증거없음; 회수2파일크기/hash일치·OS증거5명령확보. 앱산출물불완전이며회수오류는없음. host cleanup·프로세스부재/thermal0확인, 앱정상close와구분. 정상계측/보정준비완료아님.
- 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/warmup_request_run_v1/`: 원본receipt/journal/OS증거, FINAL_REPORT·POST_RUN_VERIFICATION·Git최종상태. 이번소스변경/빌드/기존PC시험반복없음. 기존FAIL/부분결과/종료계획/20null/experiment_ready=false/과거RawAdapter대응미확인보존.
- 다음: (1) PC에서lifecycle·Future30·watchdog120무기록조건검토, (2) 구체적위험과수집가능성이확인될때만별도최소진단계획검토. 같은진단/보정실측자동재개금지. 관련문서만commit·현재브랜치정상push.


## 2026-09-24 ARRIVAL-WARMUP-REQUEST-DIAG-01 — 통합 진단 PC 준비 완료

- 시작 `3130f0199f99c319ee80e30e5b2307f477302d42` / `feature/arrival-scheduling-20260923` / clean. [통합 warmup→정규요청 계약](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md). CAL-02 원인 미확정, 과거 ProbeRawAdapter hash 대응 미확인 유지. 아래 진단 완료/승인 이력과 새 후보를 구분한다.
- 원 CAL-02는 C_CPU2→C_GPU2→D_CPU2→D_GPU2, warmup8 뒤 C/urgent/GPU4요청이었다. 새 후보는 runtime4·전체warmup8·동일 첫 정규요청1(평가0), 총 명시적추론9. 설치/세션1, retry/대체/추가0, 600초(545/10/45), 기존timeout/gate 유지. **기기 실행 미승인·미실행**.
- 새scope만 제출/worker/input/API/output/persist/event저장/lane callback durable 기록을 연결하고 journal256 상한을 적용했다. 기존scope128/정책/공식 inference 경계 보존. worker_release는 event저장전 표식, lane_available는 scheduler busy해제이며 물리적 thread idle과 구분한다. 부분회수는 manifest/journal 우선.
- PC Kotlin19/Python24·관련compile/격리assemble·프로젝트서명·manifest/dry-run·script구문 PASS. 초기SDK환경/overload/tuple 오류와 최종결과 보존. 기존 두 진단 판독 호환 확인. 새 실행/registry 없음, ADB/설치/앱/추론0. mock 성공을 native/GPU 실기기 검증으로 해석하지 않는다.
- 외부 PC root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `warmup_request_plan_v1`(plan/manifest/명령), `warmup_request_apk_v1`(APK/source snapshot), `warmup_request_pc_v1`(보고서/receipt/검증로그/Git상태). plan0100c50…853d, APK9019b85…f2c0. 기존FAIL·부분결과·종료계획·20null/experiment_ready=false 불변, 소스/문서만commit·작업브랜치 정상push.
- 다음: (1) 새1세션/9추론 진단 예산 별도 승인, (2) 승인 시 최신 identity/기기/환경/미소비gate, (3) 성공하면 동기 기록 없는 보정 계획을 준비하고 남은8조건/개발-동결-확인 요건 검토. 실패면 마지막단계·확인된반환/미확인범위를 판독. 자동 재실행/보정 실측 없음.


## 2026-09-24 ARRIVAL-WARMUP-DIAG-01 — 승인 실행 완료

- 시작 `38556fe53aa315b002af309885ceabe46ccaf2a9` / `feature/arrival-scheduling-20260923` / clean. 사용자 승인과 미소비·source/APK/plan/manifest·동일 A24/서명·환경 gate 확인 후 준비된 script를 1회 실행했다. [결과와 한계](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md). 아래 PC 준비/승인 대기는 당시 이력이다.
- **업데이트 설치1 성공·세션1 완료/실패0/미시도0·runtime4 시작/4반환·첫 classification_CPU warmup1 반환·명시적 inference1(그 warmup에 포함)·평가요청0·retry/대체/추가0. 총181.0/600초.** 입력 준비→host API→출력 처리→반환 및 앱/host cleanup 완료. 종료 registry/no_resume 유지, 재실행 금지.
- journal80개·회수5파일 크기/hash·단계/시각/identity 검증, OS증거5명령 회수 완료. 마지막 seq79는 setup Java thread98의 cleanup succeeded. 이번 PID23909의 crash/timeout 증거 없음; crash 버퍼의9월19일 다른PID 오류와 구분했다. CAL-02 원인은 여전히 미확정이며 나머지7warmup/정규요청은 이번에 미관측이다.
- 외부 PC 전용 `C:/Users/LG/Documents/D1Check_Arrival_Extension/first_warmup_run_v1/`: 원본 `FINAL_RECEIPT.json`, `partial/`, OS증거와 새 `FINAL_REPORT.md`, `POST_RUN_VERIFICATION.json`. 현재 후보 source103개 일치와 과거 ProbeRawAdapter hash 대응 미확인을 구분했다. 동기 진단시간은 보정에 쓰지 않는다.
- 기존 FAIL·fixed-split 부분결과/분모·종료 CAL 계획·20null/experiment_ready=false 보존. 이번 검증(2026-09-24, 시작 HEAD+문서4개 변경): diff check·상대 링크77개/추적 대상·원본26파일 불변 확인 PASS. 소스 변경/빌드/기존 PC 테스트 반복 없음. 문서만 commit/push하며 최종 Git 상태는 종료 보고와 외부 `GIT_FINAL.json`에 기록한다.
- 다음: (1) PC에서 두 번째 CPU warmup/이후 GPU warmup 등 미관측 경계를 정리, (2) 필요할 때만 별도 최소 진단 계획·승인. 후속 실측과 중단 계획 재개는 자동 실행하지 않는다.

## 2026-09-24 ARRIVAL-WARMUP-DIAG-01 — PC 비교·후속 준비

- 시작 `67e6b10d4a8ae7f2b67ec54012311b42dac2a131` / feature/arrival-scheduling-20260923 / clean. [실행 경로 비교·후속 계약](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md). CAL-02 정지 원인은 미확정이며 추측성 runtime 수정 없음.
- 생성 순서/worker/Future30초 유지 확인. setup_only 성공은 첫warmup 이전return이므로 CAL-02 첫classification_CPU warmup 이후를 검증하지 않았다. host209.047초와 앱 네runtime wait span17.409608초를 분리했다. RawAdapter의 과거Git blob과원working-tree hash의exact byte 대응은 미확인으로 기록; Activity/TaskAdapter와보존APK identity는 대조했다.
- 새first_warmup scope: 네runtime후CPU첫warmup1회만, 평가요청0, 앱명시적inference총1(warmup에포함), 단계별durable mark와Future30초, 즉시return. 기존calibration/setup_only 의미 보존·20null/experiment_ready=false·보정제외. 원인치료/품질/성능PASS 아님.
- 제안: claim/설치/session각1·runtime≤4·warmup≤1·retry/대체/추가0·총600초(545/10/45), 동일기기/환경gate·cooling120·앱120/host125 유지. **새 실행 승인 전 금지**, 이번ADB/설치/실기기0. 과거 소비계획 재개 없음.
- PC Kotlin16·Python10·관련컴파일/격리assemble·서명·dry-run PASS. 초기테스트fixture/runner 오류후최종통과, 로그보존. APK8c6d41…3b75/plan e6f996…ad61, 새run/registry부재. 후보/근거는 관련문서와외부 `warmup_transition_pc_v1/FINAL_RECEIPT.json`. 관련소스·문서만commit/push, 원본/키/APK/모델제외.
- 다음: (1) 새1세션 후보의 별도 실행 승인, (2) 승인 시에만 최신서명/기기/미소비gate후실행, (3) 원인과장없이prefix/실제호출수·종료판독. 기존FAIL/부분결과/CAL-02불확실소비량/NPU경계 유지.

## 2026-09-24 ARRIVAL-INIT-DIAG-01 — 승인 실행 완료·원인 미확정

- 시작 `72b3264a77325f1370048665cbfdde86823eebab` / feature/arrival-scheduling-20260923 / clean. 사용자 승인과 동결 계획·소스/APK/manifest 동일성, 미소비 확인 후 준비된 script1회 실행. [결과·근거·한계](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md). 아래 승인 대기 문구는 당시 이력이다.
- **설치1성공·세션1완료/실패0/미시도0·runtime4시작/4반환·warmup0·명시적추론0·retry/대체/추가0.** 전체209.047초/600초. 동일A24/fingerprint·서명·환경·네memory admission 통과, 앱cleanup과host 종료/프로세스부재/thermal0 확인. 삭제/초기화/timeout 연장 없음.
- journal68개·앱파일5개/hash·OS증거5명령 회수 확인. CPU thread107/GPU108, 마지막seq67 setup thread99 cleanup succeeded. 이번timeout/native·Java crash 증거 없음; CAL-02의125초 대기 소진은 미재현·원인 미확정. 라이브러리 준비 연산과 앱 추론0 구분, 동기 진단 자료는 성능 보정 제외.
- 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/runtime_initialization_run_v1/`: 원본 FINAL_RECEIPT/partial/OS증거, FINAL_REPORT·POST_RUN_VERIFICATION. registry closed·no_resume=true. 기존FAIL/부분결과/CAL 중단·20null/experiment_ready=false 유지. 관련 문서만commit·작업브랜치push; 기존PC시험/빌드 반복 없음.
- 다음: (1) PC에서 이전 실패와 이번 setup_only의 단계 경계·잔여 가설 정리, (2) 필요할 때 별도 진단 계획/승인. 이번 소비 계획과 CAL/fixed-split 재개·후속 실측 자동 실행 금지. S26/NPU 협업 경계 유지.

## 2026-09-24 TEAM-SYNC-02 — GitHub·팀 안내 동기화

- 시작 `feature/arrival-scheduling-20260923` / `d8dfec32215c7fa832595cdec83d145f9d25614b` / clean. 원격 동일 브랜치 `6a63e39`보다 1커밋 앞섬을 확인했다. 아래 초기화 후보는 **준비 완료·실제 실행 미실시·별도 실행 승인 대기**다. 이번 요청은 문서·commit·작업 브랜치 push만 승인하며 기기 실행 승인이 아니다.
- [팀 안내](team/README.md)의 과거 미준비 표기를 현재 상태로 갱신하고 최신 진단 계약 링크를 연결했다. S26 선정/NPU 개발 채택은 유지하며 계약 두 모델의 NPU 지원·품질·성능 미검증, 모델별 위임 근거와 비트 동일성의 판정 한계를 PLAN/DECISIONS와 명확히 맞췄다. 기존 FAIL·부분 결과·중단 계획 불변.
- 문서 검증(2026-09-24, `d8dfec3`+문서4개 변경): `git diff --check` PASS, PC 상대 링크95개(팀 안내14개) 모두 추적 파일, 채택 anchor 확인. `rev-list --objects`/`cat-file`로 원격 미반영14개 blob 확인: 소스/문서만, 최대78,859bytes, 신규 모델/APK/키/대용량 원자료 없음·개인키/토큰/비밀값 패턴 미검출. 이번 문서 변경도 같은 검사 통과. 완료된 테스트/빌드/감사 반복, ADB·설치·실기기 실행 없음. push 결과·최종 commit·원격 일치는 종료 보고로 확인한다.
- 다음: (1) 팀원 최신 commit·모델/AOT·위임/실행·사전 품질 기준과 원본 판정 자료 검토, (2) A24 단일 초기화 후보는 별도 실행 승인 후 gate 확인. GitHub에서는 master가 아닌 위 작업 브랜치를 읽는다.

## 2026-09-24 ARRIVAL-INIT-DIAG-01 — 실행 후보 준비 완료

- 시작 `6a63e39`/`feature/arrival-scheduling-20260923` clean.744cd75의 기록 보완과 이후 S26 협업 문서를 보존했다. **별도 초기화1세션의 APK·plan·manifest·실행 CLI·PC 검증 완료 / 실행 승인 대기 / 실기기 미검증.** [계약·명령·판독 기준](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md).
- 생성 순서와 CPU/GPU별 worker·Future.get30초·close5초 구조 유지. 생성자에서 명시적 추론 호출 없음 확인, 라이브러리 내부 준비 연산은 미검증. setup_only는 빈warmup/requests와 생성 후return으로 차단. 생성 내부 단계·thread/시각 기록을 추가했으며 sync 비용이 있어 성능 보정에서는 제외한다.
- 예산은 실행claim1·설치≤1·session≤1·생성≤4·warmup/추론0·retry/대체/추가0. 단일600초 wall에서 작업545초·회수10초·cleanup45초, 앱120초/host125초 timeout 및 기존 gate 유지. 실패/claim 후 재실행 금지, CAL-02 미시도15와 별개다.
- 후보 plan SHA `bbb2d6428056af88abc7f0a88fda461c01fea045f8ccb9db55a78919cdcbaf78`, APK SHA `9af4f9ba89236702330ea57763066827116112a73353b4bb7ff668bc7631431c`. PC apksigner: 기존 보존 설치본과 같은b253…7565/package/version1. 실제 현재 설치본은 실행 직전 재확인 대상이다. 원 APK/plan/원자료 불변.
- 관련 Kotlin5·Python15·컴파일/격리 APK assemble·plan dry-run PASS(`6a63e39`+이번 변경; 파일hash/명령/시점은 외부 receipt). 기존 조사/전체 테스트 반복 없음. 실행root/registry 없음, 실제 ADB/설치/앱 실행/추론0. 일반 experiment_ready=false·20null·기존FAIL/부분 결과/미확인 소비량 유지.
- 외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `runtime_initialization_plan_v1`(plan/manifest/PC_CHECK/RUN_AFTER_APPROVAL), `runtime_initialization_apk_v1`, `runtime_initialization_pc_v1`(FINAL_REPORT/FINAL_RECEIPT/GIT_FINAL). 소스·문서만 로컬commit; 이번 push/merge 없음.
- 다음: (1) 별도1세션 실행 승인, (2) 승인 후 실제 동일A24/서명·환경·미소비 gate 확인과 단일 진단, (3) prefix/OS증거·정상 해제와host 종료를 분리 판독. 생성 성공 한 번을 원인 해결로 선언하거나16세션 보정으로 확대하지 않는다. S26 NPU 개발은 이전 협업 경계대로 병행한다.

## 2026-09-24 S26-NPU-COLLAB-01 — 최신 협업 지침

- 시작 `feature/arrival-scheduling-20260923` / `744cd75183189c237ddac98611aa2906ae3389b2` / clean. [팀 안내](team/README.md)와 [S26·NPU 채택 범위](DECISIONS.md#s26-npu-20260924)를 현재 지침으로 추가했다. 아래 날짜별 기록은 당시 상태이며 현재 미구현/승인 대기 목록으로 읽지 않는다.
- **S26을 XDEV-02 기기로 선정하고 별도 npu-runner/CompiledModel NPU 개발을 채택**, A24와 병행한다. 정확한 모델명·SoC·fingerprint는 팀원 보고/manifest 확인 대기. 이 로컬 브랜치의 NPU 모듈·3자원 정책 구현은 미완료이며 A24 benchmark-runner를 교체하지 않는다.
- S26 CPU/GPU 동결 정책 재현과 NPU 확장을 분리한다. 모델별 실행 장치·품질을 모두 통과한 경로와 검증된 병행 조합만 허용한다. npu_full/partial·DispatchDelegate1/1·bit_identical 값만으로 NPU 전체 실행/품질 PASS를 부여하지 않는다. FP16/엔진 변경 공개·사전 품질 기준이 필요하다.
- 팀원 MobileNet V1 NPU 성공·합성32입력·manifest 수정 원인은 보고만 접수했으며 원본/최신 commit/사전 기준 미검토다. 기존 S26 80런은 보조 자료이고 probe 통과도 XDEV-02 완료가 아니다. NPU 속도·에너지·이식성 미검증, EfficientDet 비배포 경계 유지.
- A24는 두 모델 실측·27세션198요청 독립 평가 완료/주 FAIL, fixed-split24시도23완료 부분 종료, CAL-02 시도1/16 실패/호출 수 미확인 상태를 보존한다. `744cd75` 초기화 기록 보완은 PC 검증 완료·실기기 미검증,20 null/experiment_ready=false. 새 setup_only1회는 실행 준비/별도 승인 필요, 중단 run 재개 금지.
- 이번 범위는 문서/상대 링크·Git 공유 대상 확인과 관련 commit·작업 브랜치 정상 push다. 원격 origin에는 시작 시 이 브랜치가 없었고 master는 `df8192a`였다. 모델/키/원자료 추가, master merge·타인 브랜치 변경·실기기 실행·무관한 테스트/빌드 없음. 최종 push/원격 HEAD는 종료 보고에서 확인한다.
- 문서 검증(2026-09-24, `744cd75`+이번 문서5개 변경): `git diff --cached --check` PASS, PC 상대 링크 검사90개(팀 안내12개) 모두 실제 추적 파일/채택 anchor 확인. `git ls-tree`/`rev-list --objects`/`cat-file` 공유 대상 검사에서 신규 모델/APK/키·5MiB 초과 blob 없음, 개인키/토큰 패턴 미검출. 기존16.9MB MobileNet은 origin/master와 같은 blob이다. 이 검사는 소스/데이터 품질 재감사가 아니다.
- 다음: (1) 팀원 최신 commit·재현 명령·모델/컴파일 identity·사전 품질 기준·원본/판정 자료 검토, (2) A24 단일 초기화 진단의 새 APK/manifest/runner 준비와 별도 승인, (3) 검증된 기기별 지원 경로 구조 개발 후 freeze/평가 계획 수립. 추가 측정 예산은 이번에 확정하지 않는다.

## 2026-09-24 ARRIVAL-FAILURE-DIAG-PC-01 — 현재 작업

- 시작 `feature/arrival-scheduling-20260923` / `63f46581347eedf10d4e5f75b6df87e451486790` / clean. **PC 조사·실패 기록 보완·관련 검증 완료, 정지 원인 미확정, 실기기 미검증.** [진단·구현·검증·다음 최소 제안](ARRIVAL_FAILURE_DIAGNOSIS_20260924.md).
- CAL-02의125초 host poll 소진과 RAM/finally 의존 기록 구조를 확인했다. 마지막 GPU 로그는 원인 증명이 아니다. 실제 원격/회수본 모두 manifest만 있어 경로 오류만으로 설명되지 않는다. 현재 PID의 native/Java crash 증거와 정지 전 thread 상태는 부족하다.
- `arrival-failure-journal-v1` opt-in 진단에만 fsync prefix·runtime/warmup/요청 start/terminal·stop/부분 cleanup 기록을 추가했다. setup_only는4runtime·warmup0·추론0. 기록 오류/overflow는 후속 호출 차단; native crash/finally·마지막 이벤트 내구성 보장 없음. 동기 I/O 진단 자료는 calibration fit에서 거절한다. 기존 정책/manifest 경로는 opt-out으로 유지한다.
- host는 명시적 timeout/실행 단계와 회수 실패를 분리하고 cleanup 전 증거5초+partial5초를 기존 phase 예산 안에서 회수한다. cleanup은 finally에서 수행한다. PC Kotlin14·Python12 PASS 및 관련 컴파일 PASS; native GPU/실기기 복구 PASS가 아니다. 검증 대상은 시작 HEAD+이번 변경, hash/명령/결과는 외부 receipt에 기록한다.
- CAL-02 **시도1/16·완료0·기술적 실패1·미시도15**, 진단0~4/warmup0~8 미확인·완료 증거0, 나머지60/120 미실행 유지. 동결/확인 미실행·20 null/experiment_ready=false. 기존 FAIL·fixed-split 부분 결과·중단 registry·원본·APK·plan 불변.
- 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_failure_diagnosis_pc_v1/`: starting_evidence, old_session_consumption, Kotlin/Python 로그, FINAL_REPORT/FINAL_RECEIPT/GIT_FINAL. 소스/문서만 로컬 commit; ADB·설치·앱 실행·실측·APK assemble·simulation·push/merge0.
- 다음: (1) 제안된 setup_only1회·runtime생성≤4·warmup/진단0·총600초 상한의 단일시도 실행 준비, (2) 새 APK/manifest/runner 및 별도 승인 후에만 기기 진단. 새16세션 계획 준비나 CAL-02/과거 중단 run 재개는 하지 않는다.

## 2026-09-24 CAL-02 승인 실행 — 첫 세션 기록 불완전으로 종료

- `ARRIVAL-TIMING-CAL-02`, 시작 `b4cc659`/feature/arrival-scheduling-20260923 clean. 사용자 승인: 개발8→검토·추정/규칙 동결→확인8,16세션/64진단/128warmup, retry/대체/추가0·cleanup 포함121.5분. 과거 CAL-01 중단과 별도다.
- 계획 SHA31558f…5a7a6, APK SHA85c5fd…7ff6와 코드·16manifest 동일성 확인. 변경 없는 PC 테스트/서명 원인 조사는 반복하지 않았다. 동일 A24/fingerprint·배터리76%/충전 분리/29.0°C/thermal0·프로세스 부재 확인, 앱 runtime memory admission은 실행 gate에서 확인한다.
- 근거 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal02_execution_v1`. 동결 runner를 그대로 호출하는 외부 approved_phase.py는 설치 성공 직후 기기 APK SHA/package/version을 확인하는 읽기 전용 gate만 추가한다. 후보의 apksigner 검증과 byte identity로 설치본 인증서를 확인하고 불일치 시 runner의 중단·cleanup으로 전파한다. 앱/정책/측정 코드 수정 없음.
- **종료:** preflight1 PASS·업데이트 설치1 성공·설치후 SHA/package/version/signer 확인. 세션1/16시도·완료0·기술실패1·미시도15, Activity1, retry/대체/추가0. 첫 classification/GPU/urgent 출력이manifest뿐이고 decision_trace 등 필수 기록이 없어 host125초 poll 뒤 중단했다. cleanup 완료·프로세스 부재·thermal0.
- 진단64 중 성공 증거0, 실패 세션4건의 실제 호출 미확인(0~4), 나머지60 미실행. warmup128 중 완료 증거0, 실패 세션8회 실제 호출 미확인(0~8), 나머지120 미실행. 호출0으로 단정하지 않는다. fit 미동결·확인8 미소비·조건별 오차 계산 불가, 기존20null/experiment_ready=false 유지.
- [종료 보고](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md). 마지막 runtime 생성 로그 이후 원인 미확정; 과거09-19 crash와 혼동 금지. phase claim→cleanup315.995초, 서명 preflight 포함약6분. 기기 기존 결과 directory69개 존재, 앱 삭제/초기화 없음. 원래 FAIL/부분결과·CAL-01 중단 보존.
- 다음: (1) PC에서 초기화/실패 종료 기록 유실 원인 진단, (2) 필요 시 별도 코드/계측 버전과 검증 준비. CAL-02/과거 중단 계획은 재실행하지 않으며 다음 실측은 별도 판단 대상이다.

## 2026-09-24 APK 서명 복구 준비 — 현재 작업

- 시작660532f/`feature/arrival-scheduling-20260923`, 직전 종료 문서3개 변경 보존. **ARRIVAL-TIMING-CAL-02 PC 준비 완료·새 실행 승인 대기**, 설치/추론/simulation0. [원인·인증서·계획·명령](APK_SIGNING_RECOVERY_20260924.md).
- 실패 APK는 전역 debug 인증서35ce…18f3, 설치본/성공 보관본은 프로젝트 기존 키b253…7565. 보관본과 설치본 APK SHA1a8448…3612 일치. 기존 키로 동일 APK 재서명; 코드·resource·AndroidManifest entry 불변(909중 서명3개만 변경).
- 새 APK SHA `85c5fd0ab578d48e8af3e2abdda4c836939c5a330631d39dc4df61bd6d3e7ff6`, plan SHA `31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6`. 외부 `timing_calibration_resigned_apk_v1`, `timing_calibration_recovery_plan_v1`. CAL-01 중단/소비 유지, 새 registry/세션UUID/출력 분리.
- preflight는 설치본 읽기/서명 검증을 설치·phase소비 전에 수행한다. unknown/mismatch/package/version 하향은0소비 차단, install_attempt와session_attempt 구분. 실제 A24 읽기 전용 preflight 호환 PASS(설치 성공 판정 아님), PC10 PASS·plan/16manifest dry-run PASS. Android 소스/의존성 변경·전체 빌드/테스트 반복 없음.
- 후보 예산 개발8→검토·동결→확인8,16세션/64진단/128warmup·retry/대체/추가0·121.5분, **미승인/미실행**. 기존20null·experiment_ready=false·198요청 FAIL·fixed-split 부분 결과 보존. 키/원자료/APK/캐시 Git 제외.
- 근거: 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_signature_recovery_v1/FINAL_REPORT.md` 및 FINAL_RECEIPT.json. 관련 코드/문서만 로컬 checkpoint, 정확한 commit/worktree는 같은 root GIT_FINAL.json.
- 다음: (1) 새 CAL-02 실행 승인, (2) 승인 후 동일기기/최신 환경 gate 재확인·개발8, (3) 품질·추정 가능성 검토/fit 동결 후 확인8. CAL-01/과거 fixed-split 재개 금지.

## 2026-09-24 ARRIVAL-TIMING-CAL-01 승인 실행 — 설치 실패로 종료

- 시작 HEAD `660532fc8a8634a2fffd3d142f11194d8f8db0c9`, branch `feature/arrival-scheduling-20260923`, 시작 clean. 사용자 승인: bound_v2 개발8→검토·동결→확인8, 총16시도/진단64/warmup128, retry·대체·추가0, 실행+cleanup 합상한121.5분. 아래 준비 단계의 미승인 표시는 과거 상태다.
- plan SHA `a340a6c61e4eb4a85591ce226965495627ebd6751c3db4075b7b558a9d0553a2`, APK SHA `7bf84ce9997ed1fc0866ed89c38c84a78f37d5589a04eedef28ff65f16ae11e5`, 현재 코드·manifest16·입력·build receipt 동일성 PASS. 변경 없는 PC 테스트/빌드 반복 없음.
- 실행 전 동일 SM-A245N/fingerprint, 단일 무선 ADB 연결, 배터리77%/충전 분리/30.0°C/thermal0, 시스템 RAM normal·메인 앱 PID 부재 확인. runtime memory admission은 설치 실패 때문에 미검증이다.
- 10:54 KST `install -r`가 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`(기존 패키지와 새 APK 서명 불일치)로 실패했다. 개발 phase 소비1/실패1, **세션 시도0·완료0·세션 실패0·미시도16**, 진단0/64·warmup0/128. Activity 실행0, retry/대체/추가0. phase 설치 시작부터 cleanup까지49.44초. 16세션이 남았다고 같은 run을 재실행할 수 없다.
- `development_stopped.json`으로 영구 중단, 확인 phase 미소비. bounded cleanup 완료·전체 해당 앱 프로세스 부재·thermal0 확인. 앱 삭제/데이터 초기화/재설치 없음. fit 동결·확인 결과 없음; 기존20 null/experiment_ready=false 유지.
- 승인·preflight·종료 보고: 외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_calibration_execution_20260924T105336/FINAL_REPORT.md`, `FINAL_RECEIPT.json`. 원래 오류·cleanup: `timing_calibration_development_run_v1`; 소비/중단: `timing_calibration_execution_registry/ARRIVAL-TIMING-CAL-01`. 코드/APK/plan 변경·테스트 반복 없음, 문서만 갱신. 기존 FAIL·fixed-split 종료 상태 보존.
- 다음: (1) 기존 설치본의 서명과 동일하게 빌드할 수 있는 키/빌드 출처를 PC에서 확인, (2) 해결 가능한 경우 새 APK·새 계획/실험 ID 및 별도 실행 승인을 준비. 기존 앱 삭제를 우회책으로 자동 진행하지 않으며 이번 중단 run/확인 phase는 재개하지 않는다.

## 2026-09-24 시간 경계 단독 진단 준비 — 현재 작업

- `ARRIVAL-TIMING-CAL-01`, branch `feature/arrival-scheduling-20260923`. 직전 d95a25f의12개 미커밋 변경·기록된8개 hash를 대조한 뒤 **2904165**로 먼저 보존했다. 이번 후속은 별도 [진단 계약·실행 명령](ARRIVAL_TIMING_CALIBRATION_20260924.md)이며 코드/PC 준비와 실기기 검증을 분리한다.
- 새 calibration 전용 protocol/ID는 null 추정값으로 고정 CPU/GPU를 지정하고 두 lane 중 하나라도 busy면 실행하지 않는다. 4요청의 독립 예정 도착에서 단독성이 깨지면 중단한다. warmup 시작/종료 및 실제 도착·큐 진입 사실을 실패 때도 보존한다. 일반 적응형 실험의 `experiment_ready=false`를 우회하지 않는다.
- 기존20 null은 그대로다. priority·persist_all·정책 범위를 구분한 새 관측 v2는8조건×5구간40슬롯. urgent 응답의 저장/해제는 N/A지만 실제 관측·lane에는 필요하며, missing과0을 구분한다. 고정 진단의 판단 비용을 CONDITIONAL의 비용으로 전용하지 않는다.
- **제안/미승인:** 개발8+동결 후 확인8=최대16세션·진단64요청·warmup128호출, retry/대체/추가0. 예상45~60분, 두 phase host+cleanup 합상한121.5분(중간 검토/충전 별도). n=1개발+1확인 session/조건의 초기 보정이며 tail/성능 우수성 검증이 아니다. 현재 소비0/16.
- PC 완료: Kotlin27/Python22·관련 컴파일·격리 APK v2 build·새 manifest16개 dry-run PASS. 현행 `timing_calibration_bound_v2/calibration_plan.json` SHA `a340a6c61e4eb4a85591ce226965495627ebd6751c3db4075b7b558a9d0553a2`, APK SHA `7bf84ce9997ed1fc0866ed89c38c84a78f37d5589a04eedef28ff65f16ae11e5`. write-once 소비 registry/fit 분리 구현. 상세·종료checkpoint는 위 계약과 외부 `timing_calibration_pc_verification_v1/GIT_FINAL.json`. ADB/설치/추론/본 simulation 미실행, 구형 전체 감사/분석 반복 없음.
- 기존198요청 FAIL·fixed-split 부분 결과·원자료·동결 APK/계획 보존. 중단 run 재개 금지. 이번 소스·문서만 checkpoint하며 데이터/APK/cache 제외, push/merge 없음.
- 다음 행동(최대3): (1) 제안16세션 예산 승인, (2) 승인 후에만 동일 A24/fingerprint·배터리/thermal/memory·연결·초기 상태 gate 및 개발8세션, (3) 개발 완전성 검증·fit 동결 후 별도 확인8세션. 하나라도 실패하면 회수만 하고 재실행하지 않는다.

## 2026-09-24 시간 경계·판단 재현 — 이전 PC checkpoint

- `ARRIVAL-TIMING-DEV-01`, branch `feature/arrival-scheduling-20260923`, 시작/현재 HEAD `d95a25f9095d4470a612128d7b79890b0d4732a8`. 시작 clean, 현재 이번 소스·문서 변경 미커밋. **설계·최소 코드·PC 검증 완료 / 실기기 미검증 / 실험 준비 미완료**. [시간·추정 계약과 검증 기록](ARRIVAL_TIMING_DEV_20260924.md).
- 새 `arrival-timing-dev-v1` / `CONDITIONAL_TIMING_DEV_1`은 기존 정책 ID/동작을 보존하는 별도 개발 버전이다. 판단→배정→실행→host inference→output→persist→worker release→scheduler lane available을 구분한다. snapshot·null 결정·후보 예측/이유와 버전·출처를 bounded RAM trace로 기록한다.
- 잔여 소진은 `UNKNOWN_OVERRUN`, 미확정은 `UNKNOWN_MISSING_BUDGET`; busy를 0/가용으로 바꾸지 않는다. 불확실 시 CPU idle에서만 긴급 우선 진단 fallback, busy면 대기. callback에서만 실제 lane 재사용. 완전한 B3/P·간섭 보정·개선 증거로 부르지 않는다.
- 2026-09-24 KST, `d95a25f`+미커밋 변경 대상: 관련 modelProbe 소스 컴파일 및 Kotlin20(신규13/기존7), Python9 PASS. 설정 dry-run은 네 cell×5구간 **20 null / experiment_ready=false**. 실기기·ADB·APK assemble/설치·본 simulation 미실행. 기존 감사/전체 분석/전체 테스트 반복 없음.
- 기존 198요청 FAIL 및 아래 fixed-split 중단/분모/재시도0·재개 금지 보존. 원본·모델·APK·frozen 계약 수정 없음. commit/push/merge 없음.
- 미확정: 새 경계에 맞는 추정값, 초과 잔여 근거, 계측 비용·callback 실기기 확인, 고정 backend 진단 수집 경로/새 예산. 기존 device CLI는 새 protocol을 실행하지 않는다.
- 다음 행동(최대3): (1) 별도 시간 경계 보정 계획에 질문·입출력·고정 backend 수집 경로 정의, (2) 그 근거로 필요한 최소 실측 예산 제안·승인, (3) 승인 뒤에만 새 버전 기기 검증. 간섭 인과 식별/독립 평가와 분리한다.

## 2026-09-23 고정 CPU/GPU 비교 — 종료 기록

- `ARRIVAL-FIXED-01`, branch `feature/arrival-scheduling-20260923`, 시작 HEAD `97225b1` clean. **STOPPED_TECHNICAL_CONNECTION_NO_RETRY / 전체 평가 미완료 / 부분 실측·복구·분석 완료**. [결과 보고서](ARRIVAL_FIXED_SPLIT_RESULTS_20260923.md), [동결 설계](ARRIVAL_FIXED_SPLIT_COMPARISON_20260923.md).
- 사용자 승인 최소안27세션·162평가요청·216warmup, retry/대체/추가0. plan SHA `9812ce6ec8d04c43e9a072bf15d712a222304ca96e2a0033d564748decaa213f`, 앱/APK/정책/threshold/순서 변경 없음. 기존27세션 `conditional_joint_primary_pass=false`와 원본은 그대로다.
- 충전 후 동일 A24/serial/fingerprint, 배터리56%·충전 없음·32°C·thermal0·hash gate를 확인해13:19 KST에 한 번 시작했다. 14:28에24번째 시도(index23 FIXED_SPLIT burst replicate2)의 첫 thermal 확인에서 ADB가 끊겼다. Activity/warmup 전 실패이며 최초 cleanup도 실패 기록 보존.
- **24/27시도 소비, 완료23, 기술적 실패1, 미시도3; retry/대체/추가0**. 실행142/162요청 모두 성공(urgent37/45, normal105/117), 미실행20을 계획 분모에 유지. warmup184/216(완료 세션 코드 경로 근거). 실제 도착 실패·거절·만료·미완료·late success0. 총 실행68.82분.
- 사용자 재연결 후14:31에 동일 기기를 확인하고 원본 확인·force-stop·프로세스 부재 확인 완료. 기기 output은 완료23개뿐이며 failed/미시도 UUID 출력 없음. 현재 thermal0, 복구 시 배터리51%. 남은 세션 자동 재개 금지; 같은 RUN script 재실행 금지.
- 부분 결과 C−F: burst 완전2/3pair urgent 세션max +72.27%, normal 평균−61.69%, 주 CI 미산출. low2/3pair +7.39%/−47.84%; queue3/3pair +21.19%/−63.15%(보조 pointwise95% CI만). 7개 완전pair 모두 urgent는 C가 느리고 normal은 C가 빠름. 단순 비유의/부분자료로 동등성·비열등성·전면 우월성 주장 없음.
- 완료 세션 gate: 최대lag2.591ms, thermal전부0, memory admission257/257 admit, sampled peak PSS432.31MiB. 새 원본566파일·기존 근거758파일 hash 불변. 실제142요청 identity/event/ledger/payload/cleanup 재검증. 분석 Python5/synthetic plot PASS, PNG/SVG3종·CSV 생성. v1/v2/v3 핵심 JSON 동등, 최종v3는 그림 표기/공통 시간축 보완.
- 근거 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `fixed_split_comparison_minimum_run_v1`, `fixed_split_comparison_recovery_v1/recovery_receipt.json`, `fixed_split_comparison_minimum_analysis_v3/FINAL_REPORT.md`·`FINAL_RECEIPT.json`. 신규 분석 코드만 추가했으며 측정용 frozen code는 불변.
- 다음 행동(최대3): (1) 부분 결과의 긴급/일반 비용 상충을 팀 검토, (2) 필요하면 보고서의 PC 재현 명령을 새 출력에서 실행, (3) 추가 실측은 별도 전향적 계획·예산 승인 후에만 검토. 이번 중단 run의 retry·대체·이어 측정은 하지 않는다.

## 2026-09-23 비동시 도착 확장 — 현재 작업

- `ARRIVAL-EXT-01`, 브랜치 `feature/arrival-scheduling-20260923`. 기존 `SIMULATION_PLAN_READY`/freeze·30세션 원본·formal v1/v2·과거 APK는 변경하지 않았다. 설계·최소 구현·PC 검증·A24 개발 pilot과 **독립 평가를 완료**했다.
- 독립 평가 plan SHA `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`, APK SHA `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`. `SM-A245N`, fingerprint `samsung/a24ks/a24:16/BP2A.250605.031.A3/A245NKSS9EZB5:user/release-keys`와 모든 실행 전 gate를 확인한 뒤 KST 07:19~08:23에 27/27세션·평가198/198·warmup216을 실행했다. 총 시도27, retry·대체·추가0, 성공198, 실패·거절·만료·미완료·늦은 성공0이다.
- 평가 품질: 최대 arrival lag 9.799ms(<100ms), thermal status 전 구간0, paired 시작온도 최대 차0.2°C, memory admission333/333 admit, sampled PSS 평균419.6MiB/최대437.8MiB, 전 세션 GPU 2 instance `verified_full`, 종료 cleanup·앱 프로세스 부재 확인. 원본694파일은 hash inventory와 전수 일치했다.
- 주 6 paired block 평균: urgent P95는 FIFO 1634.2ms, CPU 긴급 우선 406.1ms, 조건부 391.9ms다. normal 평균응답은 각각 1869.4/1957.5/1352.0ms, makespan은 3.961/3.949/2.747s, throughput은 2.020/2.026/2.912req/s다. 모든 완료율·normal on-time은100%, urgent miss는0%이며 2초/8초 deadline은 설명용 engineering scenario라 정책 구분력이 없었다.
- 동결 판정: `CPU_URGENT−CPU_FIFO` urgent 상대차의 95% CI `[-75.67%,-74.63%]`, normal 상대손실 상한 `5.53%`로 우선순위 대비는 10% 최소효과와 10% normal 손실 기준을 모두 통과했다. `CONDITIONAL−CPU_URGENT` urgent 상대차 `-3.48%`, 95% CI `[-5.02%,-1.95%]`로 10% 최소효과를 실패했고 normal 상대차는 `-30.93%`로 손실 기준을 통과했다. 따라서 조건부 정책의 주 결합 기준은 **FAIL**이다.
- 해석: 큰 urgent 개선은 CPU 내 우선순위 효과다. 조건부 정책은 주 조건에서 normal 탐지를 GPU로 보조 실행해 normal 응답·makespan·throughput을 개선했지만 CPU 긴급 우선보다 긴급 P95를 최소10% 더 줄이지 못했다. 주 urgent·normal 순위는 6/6 block에서 안정적이나 독립 block n=6, 긴급2건/세션이라 tail 일반화는 제한된다.
- PC 후처리 `ARRIVAL-EXT-01-POST` 완료: 새 root에서 기존 분석을 재현했고 session/paired/evaluation JSON이 v2와 semantic-equal, 원본694 hash와 27세션·198평가·216warmup·urgent51/normal147·정책별66을 재확인했다. 세션 urgent2건의 nearest-rank P95와 pooled P95를 분리했으며 동결 FAIL은 변하지 않았다.
- 새 그림5종 PNG+SVG, 그래프 CSV·팀 요약·재현 보고서: `C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_post_analysis_v2`. 대표 간트는 결과 무관 규칙인 첫 primary block replicate0의 세 정책 전부다.
- 확장 시뮬레이션은 별도 `arrival-extension-exploratory-simulation-plan-v1`의 plan-only/dry-run PASS, 실행0이다. classification/GPU 관측0, detection/GPU15건 전부 overlap·정책선택 표본이라 fixed split/간섭 인과 모델은 미지원이다. [적합성 계약](ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md)을 따른다.
- 다음 행동(최대 3): (1) PC 후처리 결과를 팀 공유 근거로 채택, (2) 본 시뮬레이션이 필요하면 post-unblinding 탐색임을 유지한 별도 실행·성공기준 승인, (3) 독립 검증 주장을 원하면 fixed split·matched overlap·untouched holdout의 최소 추가 측정 예산 결정.

## 2026-09-22 지원 범위 한정 계획 — 현재 작업

- `SIM-PLAN-02-SUPPORT`, 시작 `11d1e89`, 브랜치 `feature/pre-simulation-ready-20260919`. 사용자가 warm 교환가능성 가정·support-constrained 범위를 명시적으로 채택했다. 아래 SIM-PLAN-01의 INCOMPLETE는 이전 상태다.
- 구현·[계약](SUPPORT_SIMULATION_PROTOCOL.md): 12개 offset0/6+6, thermal0/resident/non-preemptive, 측정된 전체 paired co-run과 warm CPU 재배열만 허용. 미지원 action/scenario는 OUT_OF_SUPPORT. STATIC=CPU FIFO alias, adaptive는 배치 시작 전 선택으로 제한한다.
- 54deadline budget, 5pair 전수, seed2026092202, exact bootstrap3125·low/central/high·5LOSO. Pareto 주 결과와 epsilon0/0.5/1 sensitivity, 임의 허용손실 없음. 절대 SLA calibration_pending은 유지한다.
- **SIMULATION_PLAN_READY**. 신규 synthetic17 PASS, 전체Python468=466 PASS+기존symlink권한skip2. compileall/diff-check·실제 raw validator·두root byte-identical·잘못된hash/schema/seed/path/replay/consumed거절·엔진/RNG/외부process/write 차단 dry-run PASS. 검증 명령·시각·HEAD+source hash는 외부 로그에 기록했다.
- 원본1250파일+APK3 SHA 불변, Android production diff 없음. Gradle 반복 없음. 본 simulation/formal·ADB·실기기·push/PR/merge0. 절대 SLA·다기기·새 overlap은 READY 범위가 아니며 Band 원문 상세 external_verification_pending은 유지한다.
- 근거: `C:/Users/LG/Documents/D1Check_Simulation_Plan/run_20260922_support_v1/FINAL_REPORT.md`, [동결 receipt](SUPPORT_SIMULATION_FREEZE_20260922.json). Freeze SHA `32968a7f66f58f4d1b74087d2dcfafd21c729ba20b8f6705bc9d3521f8b6d9bc`. 종료 HEAD·commit·clean은 외부 git_final.json에 기록한다.
- 다음: 별도 승인·실행 프롬프트로 `SIM-RUN-01-SUPPORT`. 선택 정책의 A24 소규모 확인은 후속 `SIM-DEVICE-CONFIRM-01`이다.

## 이전 2026-09-22 PC 계획 동결 감사

- 현재 `SIM-PLAN-01` 감사·부분 계약 동결 완료. **SIMULATION_PLAN_INCOMPLETE**, 목표 READY는 미달성. 시작 `6654cb7`, 예상 브랜치·HEAD 일치 및 clean/index empty 확인. 기존 실측 입력의 SIM-01_READY는 유지한다.
- 원본 재검증: 30세션/480호출/11,155event/550 admission/480 출력 동등성/cleanup/5pair PASS. 실패·retry·대체·추가0. 평균 co-run−CPU urgentP95 −2,838.110815ms, makespan +2,178.003769ms, throughput −0.879968req/s로 기존값 일치.
- 핵심 제약: 고정 offset0/교대6+6 joint trace에는 urgent-first 순서·staggered overlap·상태 적응의 반사실적 서비스 모형이 없다. 미측정 overlap 외삽 금지 유지. adaptive 예상값/합법 action, 실질효과·일반 허용 손실, workload/replication/drain, simulator hash도 미해결이다.
- 산출물: [PC 계약](SIMULATION_PROTOCOL.md), [문헌 비교](RELATED_WORK_GAP.md), [동결 receipt](SIMULATION_PLAN_FREEZE_20260922.json), `tools/d1_simulation_plan.py`·schema·targeted tests. SP1 정책 namespace, seed2026092201, 기존 복수 deadline과 전체도착 분모·epsilon/사전적 목적 구조를 기록했다. 필수 null을 READY로 승격하지 않는다.
- 검증: 신규15 PASS; 전체Python451=449 PASS+기존symlink권한skip2, compileall/diff-check PASS. 두root byte-identical, 전체 raw validator/consumed/replay/hash/schema/seed/path 거절, dry-run 실제 RNG/외부process/결과파일0·입력 불변 확인. 검증 대상은 6654cb7+이번 미커밋 코드이며 최종 source hash는 외부 frozen_final/freeze.json의 code에 결합한다.
- 보존: 기존 실험root1250파일+APK3 SHA 불변, Android production/modelProbe Git diff 없음. Gradle 반복 없음. 본simulation/formal·ADB·실기기·push/PR/merge 없음.
- 외부 최종 보고서: `C:/Users/LG/Documents/D1Check_Simulation_Plan/run_20260922_v1/FINAL_REPORT.md`. 정확한 종료 HEAD/commit/clean은 같은 root의 git_final.json 참조.
- freeze SHA `0f9f6bebe11d09f8b4ed1116c5a701ba960794ebc39b73463240219299c0142a` (부분계획 동결, 실행 승인 아님).
- 다음 한 가지: `SIM-PLAN-02-SUPPORT-DECISION`에서 **새 실측 없이 사용할 반사실적 서비스 모형의 허용 가정과 범위**를 결정한다. 불가하면 고정 trace 기술분석으로 연구 질문을 명시적으로 축소하는 대안을 검토한다.

## 이전 체크포인트 — 실측 입력 준비

- 갱신: 2026-09-21 KST. **SIM-01_READY (bounded descriptive/resident-only/A24/thermal0)**. 시작 `3b4472b` clean, atomic journal checkpoint `86040fd`. 정확30session/480호출 completed, failed/retry/대체/추가0. 본simulation/formal 실행0.
- 새 [bounded 결과](BOUNDED_EMPIRICAL_RESULTS_20260921.md): solo4cell×5, resident5pair 완전. 실제11,155event·output equivalence480·memory admission550 통과, setup/active/worker-release/close·cleanup 검증. Warm은ordinal관측이며 populationP95/PI보장 아님.
- Paired 관측: corun−CPU urgentP95 평균−2,838.11ms, makespan+2,178.00ms, throughput−0.880req/s. 5쌍의 제한된 방향·bootstrap 근거이며 GPU보편우월성/인과일반화 없음. Low/central/high/cold-stress도같은상충방향.
- Sampled peak PSS311,353KiB(기존326,254KiB보존), true maximum/headroom보장 아님. Thermal0만승인. Deadline은사전공식의공통복수engineering scenario로계산·동결했고 사용자SLA는미확정이다.
- Joint input SHA `4eeae6f6f8e9954d153b010767ba5a84307e5b8d0a971e7a478b0255413c0fc5`. 두root동일재생성/원본재검증/field mixing거절/no-op PASS. 전체Python436(434 PASS·skip2)+복구overlay4 PASS, compileall/diff-check PASS. Android/APK·기존근거2213파일·이전보고서hash불변.
- 보고서·atomic manifest·raw·분포/LOSO/bootstrap/paired/deadline/provenance: `C:/Users/LG/Documents/D1Check_Bounded_Empirical_Run/run_20260921_atomic_v1/`. 최초실행흔적없음을확인후새root에서시작했고실제context중단복구는불필요했다. 복구경로는host mock검증, 30완료후실행기재호출금지.

## 이전 단계 기록 — 아래 판정과 pending은 당시 상태이며 현재 판정을 대체하지 않음

- [v4 계약](TELEMETRY_V4_GATE.md): 실제531 event의 setup/active/runtime/worker-release·memory·resident CPU serial/co-run·paired/joint 및 출력 동등성 모두 PASS. 각 session force-stop 성공, 최종 project process 부재 확인. 보고서: `C:/Users/LG/Documents/D1Check_Telemetry_V4/resume_20260920T160724Z/FINAL_REPORT.md`.
- 재개 targeted Python29 PASS, 실제 artifact4 schema/validator 및 consumed/replay 거절 PASS. 검증 소스/APK hash 불변으로 기존 debug JVM119/modelProbe JVM126/Python370(368 PASS·skip2)/lint/build는 반복하지 않았다. 기존 근거2213파일 및 이전 보고서101파일 불변.
- Memory admission28회 admit, lowMemory 거절 mock PASS; thermal0에 한정. sampled peak PSS326,254KiB는 절대 최대나 안전 상한이 아니다. APK SHA `68e55aefdceb91e569e0d55ff0a18af0658163106589852325cb9ad5626fa62e`. Warm 안정화·서비스모델 승인·deadline은 pending, SIM-01_INCOMPLETE 유지.
- 이전 V2: [V2 결과](SERVICE_MODEL_V2_RESULTS_20260920.md), [설계](SERVICE_MODEL_V2_DESIGN.md), `C:/Users/LG/Documents/D1Check_Service_Model_V2_Design/run_20260920T140424Z/FINAL_REPORT.md`. 구현 checkpoint `1cbdd1e`; 종료 commit/clean은 외부 git_final.json 참조.
- V2: 기존52 profile session 전부 consumed. 검증51세션559요청+host실패9요청 보존. C+E setup/active joint empirical 개발모델 WAPE4.311%/MAE29.447ms는 승인holdout 결과가 아니다. Warm K·worker-release·runtime span·MemoryInfo·공정resident CPU대조 부족으로 승인 동결 불가.
- V2검증: 새unit30/관련targeted83 PASS, 전체341(339 PASS·기존skip2), compileall/diff-check PASS. 두root 재생성hash 동일, no-op/dry-run device명령/dispatch/가상완료0. Android source/APK3종 불변. 계약 SHA `635087906dde3ff3c50fc034b350689207109d54970c721bf21a24bb432f0719`는 설계hash이고 승인simulation input은 없다.

## 이전 FINAL-CALIB 근거 보존
- 브랜치 `feature/pre-simulation-ready-20260919`, 시작 `4230160` clean. 계획 checkpoint `5544995`, holdout 전 후보 동결 `b5928e8`. 종료 문서 checkpoint/clean 여부는 외부 `git_final.json` 참조. push/merge/rebase/master 전환 없음.
- 최신 상세: `C:/Users/LG/Documents/D1Check_Service_Model_Final/run_20260920T130139Z/FINAL_REPORT.md`. 보고서·JSON·명령/시각/HEAD/실패 로그·모든 session 원자료를 같은 root에 보존했다.
- 저장소 요약: [FINAL-CALIB](SERVICE_MODEL_FINAL_CALIB_20260920.md), [사전 동결 hash](SERVICE_MODEL_FINAL_FREEZE_20260920.json). 이전 [FREEZE](SERVICE_MODEL_FREEZE_20260920.md)·[A24 재개](A24_RESUME_20260920.md)·[decoded 수정](DECODE_RESOLUTION_20260920.md)·기존233요청/31session 원자료 보존.

## 신규 실측과 실패 보존

- Phase A: 새 calibration4세션/42요청 PASS_EQ. 기존 calibration24세션/206요청과 합쳐28세션/248요청만 fitting. 과거 holdout4/사후진단1은 fitting 제외·원본 보존.
- Phase B: 동결 후 새 holdout16세션/260요청 완료·PASS_EQ. 같은20개 검증image 재사용이며 unseen-image accuracy 검증 아님. 독립 단위는 session이다.
- Phase C: CPU-only 직렬2세션/24요청 완료·PASS_EQ. 계획22세션326/326기기요청 완료. 별도 첫 host 실패 시도의9개 기기완료까지 실제23시도/335요청을 보존한다.
- Host 실패2건: 첫 calibration 종료기록 변수 오류는 원시9요청·오류·원래 SHA와 일치하는 코드 archive 보존 후 새 UUID 대체. B 탐지CPU1세션은 기기 완료 뒤 ADB 전송 실패, 재연결1회·force-stop 후 누락 파일만 native provenance SHA로 회수했다. Activity 재실행·실패 상태 덮어쓰기 없음. attempt_ledger/recovery_receipt 참조.
- 새 UUID·출력 root, 최대48요청/120초 bounded profile. 시작/종료 thermal·memory·시계열 회수, 마지막 project force-stop 확인. staging/과거 데이터 삭제·uninstall/pm clear/reboot/다른 앱 접근 없음.

## 사전 동결과 독립 평가

- 2026-09-20T13:11:32.713690Z, commit `b5928e8`에 `transition_mean`을 독립평가용 고정. cold_first/initial_followup/warm_steady/방향별전환16개 cell-state 그룹. co-run은 평가 층으로 분리하나 모델 파라미터는 solo와 pooling한다.
- 기존 acceptance 유지: MAE≤432.808616ms, WAPE/분포 상대오차≤43.191436%, coverage≥90%, 지원율100%, calibration상태≥2세션/holdout cell≥2세션/warm≥20관측. PI=calibration Q05..Q95. Holdout 이후 파라미터·상태·interval·threshold 변경 없음.
- calibration LOSO MAE36.97ms/WAPE5.07%/coverage80.65% 미달을 사전 기록. 기존6후보를 support·단순성 기준으로 비교했다.
- **독립 holdout:** MAE39.070581ms/WAPE6.102956%/coverage80.384615%. 전체 MAE/WAPE는 기준 이내지만 PI·session/상태별·분포 기준 실패. 세션 평균 WAPE8.740222%/coverage77.383207%.
- 분류CPU cold/early-after-cold coverage50%/50%, warm96.15%. early-after-transition 중앙103.262ms를 cold직후 중앙494.315ms와 같은 initial_followup으로 묶어 전환 직후 WAPE250.07%. 사후 원인 관찰이며 이번 모델은 재학습하지 않았다.
- 기존74.57% 오차의 두 번째381.316923ms와 cold774.244ms 보존. 신규cal 첫768.65/두 번째525.46/세 번째103.39ms도 삭제하지 않았다. JIT/GC 인과 미확정.
- UUID/seed20260920: measurement_plan_v2/split_manifest/frozen_contract. 요청별예측=request_predictions, 세션·분포평가=holdout_evaluation.json.

## Capability·품질·co-run

| Cell | Backend/decoded | 새 solo warm 평균 |
| --- | --- | ---: |
| classification CPU | PASS_EQ / actual CPU | 97.36ms |
| classification GPU | PASS_EQ / full GPU | 249.89ms |
| detection CPU | PASS_EQ / actual CPU | 558.01ms |
| detection GPU | PASS_EQ / full GPU | 1,063.06ms |

- A24 CPU-solo-dominant 유지. CPU urgent+GPU normal의 urgent P95는 두 관측1,869/2,096ms, CPU-only직렬2,737/2,919ms. 두 구성 모두 완료율100%. n2 진단이며 GPU 우월성 확정 아님.
- 대조 제한: CPU직렬 probe는 runtime1개를 작업 변경 때 재생성, co-run은2개 유지. arrival/sample/priority/seed/thermal0·29.2°C는 같지만 warm runtime 상주 조건이 다르다. GPU 자체 인과효과·강한 CPU-only 기준 대비 우월성을 주장하지 않는다.
- Numerical/decoded 동등성·실제 accuracy·scheduling quality preservation 분리. 기존20장/직접40쌍 및 별도 JPEG1장 raw 범위 유지. 부분GT15/28은 mAP 아님. 임의 accuracy 생성 없음. 같은 모델/input/preprocessing/decoder·기존 허용오차·fallback 금지 유지.
- EfficientDet exact license/NOTICE 미확인·직접 확보 비배포 연구 한정, 저장소/APK/공유물에 모델 추가 없음. formal v1/v2·calibration-v1/image-v3·공식 timer·A24 80슬롯·S26 자료 보존.

## 환경·입력·검증

- 신규 전체 sampled peak PSS318,364kB. 기존314,184kB 보존, true peak 아님. 후보 guard340,066kB/headroom25,882kB 사후 상향 없음. 새 peak와guard차21,702kB는 승인 headroom 아님. B/C host 최소 sampled MemAvailable1,198,500kB.
- Memory blocker: 순간 peak·압력 조건·실행 중 admission/stop 강제 미검증. Thermal status0만 검증, 다른 상태/장시간/에너지로 일반화 금지.
- Deadline=calibration_pending/null, 위반 개수도null. matched control runtime 비대칭·공통 목표 미고정으로 임의 deadline 동결 없음.
- 독립평가용 model SHA `c29691f6fac993cd97054667e861e19232277009243c1e41c199fa6d33e6bd30`; input 후보 SHA `dfe3fa15b0ff84165bb8570ea0d19d39b5cd6757d5b618453da6acfc30acad19`. 최종 승인 input 없음. 기존 split hash는 원자료24/4/1분할로 보존, 신규28/16은 frozen envelope에 명시한다.
- 다섯 baseline interface 동일 후보 input·품질/thermal/terminal/fallback 제약. no-op dispatch0/가상완료0/비교null. 정책 dispatch·본 simulation 미실행.
- targeted74 PASS, 전체 Python311(309 PASS·기존skip2), compileall PASS. 실제 schema/validator·committed hash·holdout 누수/stale/replay·seed·frozen bytes 변조 거부·no-op PASS. final_validation.json에 B16의 동결 commit 이후 시작·22세션 artifact·이전 source bundle 불변 확인.
- Android source는4230160 대비 diff 없음, debug/modelProbe/release APK SHA 불변·원격 APK 동일. JVM/build/lint 반복 없음. modelProbe APK SHA `8b805d3acfcede25fe6e4bcd17075d172c5ef66b425ff40ff29e2317ffce2489`.

## 정확한 다음 행동

1. 동결된 joint input과 동일CRN·deadline scenario를 사용하는 resident-only scheduling simulation 계획을 별도승인한다. 이번에는본simulation/formal을실행하지않았다.
2. 허용범위는현A24/모델/입력/thermal0/관측resident·overlap이다. 미측정4runtime·2GPUresident·dynamic reload·다른thermal/기기일반화금지.
3. 완료30session을재실행하지않는다. 결과재현은외부analyze_completed.py의host-only generation/validation으로수행한다. 기존prediction실패/consumed자료는계속보존한다.
