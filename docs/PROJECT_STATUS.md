# D1Check 현재 상태

## 2026-10-03 장구간 점유 전력 추정 완료·프로토콜 전이 실패

- [계약·계수·오차·재현](results/online_policy_study_01/legacy_transfer_v1/README.md), [화면](results/online_policy_study_01/legacy_transfer_v1/index.html). 옛개발3의272창으로 고정구조1회 적합, 온라인13은 사후평가만. 평균11.877/최대31.704J로 기존7.118/17.871보다 악화하여 미채택. 독립확인0·기준완화0.
- 부하전후 유휴가 평균차이7.206J/60.7%; 산술분해이며 원인확정/보정 아님. 자료 재사용 경로는 완성했지만 현재 배경·점유 전력의 전이 예측은 미해결. 기존 AP/서비스·동결·기본/strict/experiment_ready=false 불변.
- 다음 행동: 현재 계측 조건의 유휴·분리부하 개발과 혼합 독립확인을 묶어 배경 변화/상태 항을 구분하는 경로 준비. 옛3세션 또는 동일96요청 단순반복은 하지 않는다. 원본9해시/PC2검사/13구간합 검증, 이번 기기·새계획·claim0. 아래는 과거 단계.


## 2026-10-03 상태 점유 식별력: 기존 장구간 원본 재사용으로 전환

- [수치·근거·재현](results/online_policy_study_01/identifiability_v1/README.md). 온라인13의 조건수119.5, 분류CPU 총11.79초. 옛 개발3 원본의 지원272개5초창은 조건수6.37로 더 분리된다. 미지원 탐지GPU 포함88창은 제외표 보존; 부분을 전체창으로 표시하지 않음.
- 옛 W는250ms 반복 regimen 평균이며 순간 lane 점유 W와 다름. 원본9해시 확인, 새 계수 적합0. 추가 장구간 측정 필요를 지금 선언하지 않는다. 실패 pooled 후보 판정 불변, 기본/strict/experiment_ready=false 유지.
- 다음 행동: 기존272창 실제 점유와 동일창 J를 연결해 전력 추정 및 이미 본 온라인자료의 프로토콜 전이 평가. 새 독립 확인으로 표현하지 않는다. PC2검사·실제 원본 분석 완료, 기기/새계획/claim0. 아래는 과거 단계.


## 2026-10-03 배경 전력 후보1개 평가: 미채택

- [판독·재현](results/online_policy_study_01/pooled_candidate_v1/README.md), [화면](results/online_policy_study_01/pooled_candidate_v1/index.html). 이미 본13세션의 사후 개발/세션제외 평가이며 독립 확인0. 평균 절대J7.118→5.307이나 최대17.871→19.447로 사전 진행 조건 실패. 기준 완화·최악 세션 삭제·추가 후보 탐색·확인 실측0.
- 기존 AP/처리시간·동결557fbe·strict/default/experiment_ready=false 보존. 일정/응답·조건부 AP와 관측 비교는 가능하지만 작은 J 차이의 정책 우열은 미판정. 원래 목표 진행 중이며 완료/불가능으로 선언하지 않는다.
- 다음 행동: 고정24분류/72탐지의 상태 점유 식별 기여를 계산해 단순 반복 대신 최소 입력 변경의 필요를 특정한다. 후보2+기존8검사 통과. 이번 PC 단계 기기0; 직전 적격4/실패1/520추론은 보존. 아래 기록은 과거 단계다.


## 2026-10-03 전력 계측 대조4 확보·짧은 배경입력의 민감도 확인

- [최종화면/CSV/재현](results/online_policy_study_01/sampling_run01_complete/index.html), [보고서](ONLINE_POLICY_MODEL_STUDY_20261002.md), [검증](results/online_policy_study_01/sampling_run01_complete/verification.json). 앞2완료→냉각thermal조회2초timeout→새남은2완료. 원래4세션 연속완주가 아니며 실패/부분96요청을 보존한다.
- 실제합계5시도/적격4/부분종료1,본480＋warmup40=520추론/runtime20/staging5·35/pull2/APK push·설치각1/ADB4144/작업1560.662초(PC공백별도). 앱cleanup4완료/중단1미회수,host세션정리5＋설치정리1/각마지막ps부재/parent·child exited. 원본두receipt/inventory21947파일 보존.
- 900ms는133표본/8위상,1000ms는120표본/2위상으로 분산 개선. 그러나900−1000 J차이는−4.200/+0.300으로 불일치. 기존557fbe동결식을 그대로 적용한 J오차−17.871…+5.803/AP MAE0.192–0.756°C. 조회주기만으로 모형오차 해결/정확도PASS 아님.
- 관측120초J 범위4.200J에 비해, 부하전20초W 차이를120초고정배경으로 전용한 변동22.398J. **다음 행동:** 기존13적격에서 세션별짧은 배경입력을 pooled resident 항으로 대체하는 최소후보 하나의 식별성/사후평가를 수행한다. 기존계수/default/strict/experiment_ready=false 유지; 새후보 독립확인은 별도로 필요하다. 원래목표는 아직진행중이며 추가동일실측을 기계적으로 반복하지 않는다.
- Python12/Android7/서명APK·Check·Run·수치/그림 검증. source104/기존3freeze 불변. UTF8 SVG 후처리 오류만 PC수정, 기기재실행으로 해결하지 않았다. 아래진행중/미승인 설명은 당시 이력이다.

## 2026-10-03 전력 계측 대조: 앞2완료·냉각조회 중단 후 남은2 실행 중

- plan_v1은 `thermalservice`2초 timeout으로 stopped_no_resume. 첫2 적격, 세 번째 본96/common120기록은 회수했으나 cooling/appcleanup미확인, 네 번째 미시도. 실제312추론/ADB2473/962.877초, 계획상 force-stop·ps부재 확인. 출력0bytes를 기기단절/전송0으로 해석하지 않는다.
- 완료2개412근거 해시 보존 후 새 plan_v2에서900/1000ms 두세션만 진행. SHA `af6ff98a…1a689b`, 상한208추론/runtime8/stage2·14/pull1/APK0/ADB6600/2090초. 동일APK·gate·timeout 유지, 내부retry0. 서로 다른block·기존실패 소비를 합쳐 원래4세션 완주로 표시하지 않는다. [근거/판독](ONLINE_POLICY_MODEL_STUDY_20261002.md).
- 기존 모형 적합/strict/default 변경0, experiment_ready=false. 다음 행동은 남은실측 종료와 계측 민감도 판독·증거/Git 보존이다.

## 2026-10-02 전력 잔차의 표본 위상 집중 확인·새 대조 실행 착수

- 기존9세션의 반복 주기 대비 전력 표본 시각을 분석했다. 개발500ms 도착은 2초 반복에서8위상 중2구간만 관측, 확인550ms는8구간에 분산됐다. aliasing 크기/오차 원인으로 확정하지 않는다. 계수 leave-session-out 불안정과 약4mAh charge counter 단계도 확인했다. [CSV·그림](results/online_policy_study_01/power_diagnosis_v1/sample_phases.svg).
- 사용자 자율 실측 승인으로 동일 병행96요청/500ms 부하의1,000→900→900→1,000ms 조회 대조4만 실행한다. APK는 별도opt-in900ms를 추가하며 기존기본1초/onDestroy/부하/환경 gate 불변. 900ms 추가조회 약11.1% 자체 비용과 세션변동은 구분 불가 한계다. 새 모형 적합/확인 재보정0.
- plan SHA `d7e962eea85ed50d491630ff1f3162e458f3fd53d1b304ace8c75a7d58be3c6b`, 외부 `online_power_sampling_plan_v1`, 출력 `online_power_sampling_run_v1`. 상한4세션/본384+warmup32=416추론/runtime16/staging4·28/pull1/push·설치각1/고정840초/상한3670초/ADB13000/재시도0. 현재설치본과환경은 기존 실행기 안에서 확인한다.
- 관련Python11/Android7·서명APK 빌드·실제PS Check/ADB차단Check 통과. 실측 전 단계이며 예상 정상시간이나 완주보장이 아니다. 다음 행동은 Run1회와 실제 소비/회수/계측 민감도 판독. 기존 freeze/default/strict/experiment_ready=false 보존.

## 2026-10-02 원래 목표 연결: 온라인 정책 개발3·동결·독립 확인6 완료

- [실행·오차·정책 판정](ONLINE_POLICY_MODEL_STUDY_20261002.md), [그림/CSV/재현](results/online_policy_study_01/run02/index.html), [검증](results/online_policy_study_01/run02/verification.json). 실제 예정도착96개/CPU직렬·CG_DC병행·CG_DC직렬을 실행하고 일정/응답/J/AP를 독립 비교했다. AP 조건부 재생만으로 전체 연구 완료라고 부르던 경계를 바로잡았다.
- 02 prelaunch ADB 실패(추론0),03 개발2완료 후 냉각 configuration-destroy 실패(본288/warmup24)는 stopped_no_resume 보존. 새 온라인 전용 Activity의 구성 callback만 보완, 기존 onDestroy 취소/worker/계측은 유지. 구체적 외부 구성 변경 원인은 미확정. 새04 개발1＋확인6 정상 완료, 이전 적격2 재사용; 과학적 구조/입력/판정·동결 후 계수 변경0.
- 04 실제7세션/본672＋warmup56=728추론/runtime28/staging7·49/pull2/APK push·설치각1/ADB5836,2235.496초. 전체02/03/04 합계1040추론/ADB7762로 실패 소비 포함. 앱cleanup7·회수7·세션host정리7＋설치정리1·최종대상ps 부재·parent/child exited. 기존 원본과 별도 registry 보존.
- 모형freeze `557fbe5b…7bcf2`(2026-10-02T13:33:27Z), 완료receipt `online_policy_study_run_v4/FINAL_RECEIPT.json`. 확인 전원96/96마감, 예정도착 dispatch MAE11.047–31.375ms/AP MAE0.152–0.605°C. 전체120초 J오차 −0.291…−15.941(−0.162…−9.275%); 실제 일정 조건부에도 비용오차 잔존. 초기화 이후35–120초와 상쇄를 별도표시.
- 병행의 urgent P95는 CPU보다136–146ms 짧았지만 관측 에너지 차이는 −11.112/−0.820J로 달랐다. AP최고 차이도0.1–0.2°C 수준으로 모형 오차보다 작다. **등록 정책의 실측 비교·예측 평가/도구 연결은 완료, 정밀 에너지·열 정책 선택/안정 절감 우월성은 미입증.** 실측을 더 했다는 이유로 완성/정확도 PASS를 선언하지 않는다.
- `python -B -m tools.d1_simulator online-policy --case-id confirmation_0_CPU_URGENT_ONLINE_V1 --policy B2_PARALLEL_ONLINE_V1 --output output/online_parallel_fresh`로 부하 전 초기조건과 예정 도착 기반 재현 가능. 기존 AP/arrival/episode/default·strict·experiment_ready=false 유지, 임의 도착/열→처리시간/S26은 자동 지원하지 않는다.
- 관련Python33/Android13·프로젝트 서명 빌드·실제Check/Run·전체/부분 적분/CLI/CSV/SVG 검증 완료. **다음 PC 작업 하나:** 기존9세션의 상태·이력별 전력 잔차에서 고정 증가분＋부하 전 배경 전력 가정의 실패 경계를 특정한다. 동일6세션 추가/후보 재보정/기기 작업 자동 실행 없음. 아래는 과거 완료·권고의 이력이며 최신 범위는 이 절을 따른다.

## 2026-10-02 남은 확인4 완료·제한 시뮬레이터 최종 연결

- 사용자 연결·재개 승인으로 새 plan_v3의 SPLIT/SPLIT/L50/C 확인4가 모두 적격 완료됐다. 개발6(과거C1＋새5)→변경 없는M0 동결→확인2＋휴지 후 새4의 판독을 완료했다. [최종 보고서](AP_MODEL_COMPLETION_STUDY_20261002.md), [확인6 곡선/CSV·등록 입력](results/ap_completion_study_01/final/index.html), [통합 시뮬레이터](results/simulator_workbench_01/index.html). 기존01/02 실패·사용자 중지는 stopped_no_resume로 보존하고 연속12세션 완주라고 하지 않는다.
- 새03 실제 본72/warmup32/runtime16=104추론, staging4·28파일/pull1/APK push·설치0, ADB2812/13000, root1293.024/3670초, timeout·재시도0. 앱 cleanup4·회수4·host 종료4·마지막 대상ps 부재, parent/child 생성시각·명령 식별 기준 exited, receipt/registry completed. 원본 `ap_completion_study_run_v3/FINAL_RECEIPT.json`, PC `ap_completion_remaining_readout_v3`. 현재 시각의 재조회가 아니라 계획 종료 시 관측이다.
- M1은 개발 LOSO 일부 악화로 미채택, M0 freeze `b5bbfa51…b83e` 불변·확인 재보정0. 확인6 AP MAE0.061661–0.371789°C/최대0.173043–0.901555°C. 분할2의90–115초 냉각 방향 재현,18창 중16 방향미식별. 기존 W식 전체120초 차이+5.438741–+20.446578J, 원래 시작AP 범위밖/외삽. 정확도 PASS·정책 순위 없음.
- `tools.d1_simulator ap-conditioned --case-id v3_confirmation_2_SPLIT_DELAY30 --output output/ap_split_fresh`로 실제 일정·부하 전AP 조건부 재생이 가능하다. 기존 일정/응답·서비스/관측 참조/고정870 경로 보존, 임의 도착J/AP·열→처리시간 미지원/null, default/strict/experiment_ready=false 유지. 연구 결과·제한 시뮬레이터는 이 범위에서 완료이며 범용 열 정책 완성은 아니다.
- PC 현재 경계10검사(잔여3＋AP4＋대표기존3), 실제 Check 기기0, 여섯 CSV/CLI 수치·누적J 끝점/상태coverage·SVG·동결 불변 확인. Android/APK 변경0. **다음 행동 하나:** 최종 대시보드와 지원·미판정 결론을 팀 연구 결과로 공유한다. 추가 실측/후보적합/계획 자동 생성 없음. 아래는 과거 준비·실행 이력이다.

## 2026-10-02 남은 확인4 새 계획 PC 검증·실행

- 개발6(기존 적격C1＋신규5) 판독·모형 선택을 완료했다. M1은 LOSO의 C/L65 일부 오차 악화로 미채택, 변경 없는 M0를 확인 전에 동결했다. 확인 C/L50 2개 완료 후 사용자 이동 요청으로 세 번째 staging 중 중지했으며 앱 launch는 없었다. 이전01/02는 stopped_no_resume/원자료·소비 보존이다. [정확한 경계·표·근거](AP_MODEL_COMPLETION_STUDY_20261002.md), [후속02 결과](results/ap_completion_study_01/followup02/index.html).
- 사용자 연결 복구·남은 실측 승인으로 **새 plan_v3 확인4만** 진행한다: SPLIT_DELAY30/SPLIT_DELAY30/L50/C. 개발 재수집·재적합0, M0 freeze SHA `b5bbfa51…b83e` 불변. 현재 기기/설치본/환경 gate는 기존 실행기 안에서 재확인한다. 계획 SHA `72fe75f7f7730a181331f3fceb15bec5567908446f5615e1ee461c94f54a55ca`, 원본 출력 `ap_completion_study_run_v3`, 상한104추론/runtime16/staging4·28/pull1/APK0/ADB13000/3670초/재시도0.
- 잔여 subset/실제 root 진입/확인 재적합 금지·동결 불변/소비 계획 차단 관련 PC3검사와 실제 PS Check 통과. Check 기기0. 원래 scientific·measurement 소스/계약/APK unchanged, host orchestration만 보완했고 구 실행 소스를 외부 보존했다. PC 검증은 실기기 안정성 증명이 아니다.
- **다음 행동:** 승인된 새 Run1회→원본·확인 판독→제한 시뮬레이터/본문·대시보드 반영. 실제 중단이면 그 계획을 종료하고 자동 재실행하지 않는다. 일반 동적 J/AP·열→처리시간·정책 순위는 미검증이며 default/strict/experiment_ready=false 유지. 아래는 역사적 상태다.

## 2026-10-02 AP 종료형 연구 Run1회·조회 timeout 종료

- 사용자 계획 후 실측 진행 승인에 따라 개발6→한 후보군 추정/선택/동결→새 확인6의 실제 host 진입을 구현/PC검증/Run1회 수행했다. [설계·최종 판독](AP_MODEL_COMPLETION_STUDY_20261002.md), [화면/CSV](results/ap_completion_study_01/index.html). 개발 C1 완료·L35 준비 중 uptime2초timeout으로 **stopped_no_resume**, 나머지개발4/확인6 미시도,추정·동결·확인0. AP 예측 실패/미식별 판정 아님. Android/APK·계측 주기 변경0.
- plan SHA `09b70105…b14b86`·소비/종료 보존. 실제warmup16/runtime8/본시작기록0/staging2·14파일/pull1/배포0/ADB963/375.400초. 중단 세션 terminal 미회수로 본 호출 미확인범위0–24(발생 주장 아님). 첫C cleanup 정상, 둘째부분회수/host정리각1·최종ps 대상부재; 앱cleanup 미확인. 원본 `ap_completion_study_run_v1/FINAL_RECEIPT.json`, inventory4,960파일/110,483,976bytes. 기존6 plan은 미소비/원문 보존.
- 새 관련7테스트 PASS: 실제 root 동결 전후 순서/과학적 중단·실패/receipt 실패, 기존6세션 진입의 회수·cleanup 오류8조건/설치 금지/동결 연결, 합성 계수 식별·확인 적합 차단·지원/시간 경계. 실제 PS Check 기기0, 기존 원문6 fixture의 M0 전파 차이<1e-10°C 및 ADB 실행 차단 Check 확인. PC 검증은 기기/장시간/실용 식별 증거가 아니다. 외부 `ap_completion_study_pc_v2/verification.json`에 소스 hash 기록.
- 부분C 공통120초132.482716J/원래식147.052011J; M0 AP35.344549–179.784549초 MAE0.067274/최대0.385750°C, 새모형확인/방향PASS 없음. uptime190정상 중앙0.091480초/단발timeout1·내부원인미확정, 이후계획내회수/종료성공. 추가기기0. 다음 PC 행동은 동일 시각괄호/thermal 관측을 단일 원격 명령으로 얻는 최소 경계 검증이며 새실측 자동생성 없음. 기존 freeze/default/strict/experiment_ready=false 보존. 아래 미승인·미구현은 당시이력.

## 2026-10-02 AP 개발→동결→독립 확인의 종료형 실측 설계

- 사용자 ‘오래 걸려도 확실한 계획’ 요청에 [최대12세션 연구 계획](AP_MODEL_COMPLETION_STUDY_20261002.md)을 작성했다. 개발 C/L35/L65 역순6 → 한 후보군 PC 추정·동결 → 새 C/L50/분할 역순6. 같은 자료 보정/독립 확인 혼용 금지, 미식별·실패 시 종료·13번째 세션 없음. 제한 A24 CG_DC AP 모형이며 일반 정책/열 피드백 완성을 보장하지 않는다.
- **DESIGN_FIXED_EXECUTION_NOT_APPROVED**. 본192/warmup96=288추론, runtime48, staging12/84, pull2, push/설치0, 관측42분, 기기상한2시간55분＋PC동결관리60분=누적3시간55분 제안. 현재 새 수집 승인 아님. 입력 변환·예산·원래계획/소스/APK/후보 보존 PC검사 통과, 기기0.
- 기존6세션 plan_v1은 미승인·미소비 그대로 보존. **전체 경로 완성 전 실행 보류 권고**이며 실패/stopped로 변경하지 않음. 다음 행동은 한 후보군 적합·미식별 처리·동결·확인6 진입을 PC에서 함께 완성하는 것. 현재 실행기에는 12세션 연결이 없으며 새 Run/claim 없음. 기존 계수/default/strict/experiment_ready=false 유지. 아래는 당시 이력이다.

## 2026-10-02 AP 배경·부하 시점 통합 대조 PC 준비 완료

- [설계·판독·예산·명령](results/ap_background_contrast_01/README.md), [준비 화면](results/ap_background_contrast_01/index.html), [검증](results/ap_background_contrast_01/verification.json). C→L35→L65→L65→L35→C, 같은74e APK/resident/warmup/계측으로6세션을 고정했다. 조건별 평균 순번3.5의 균형이며 임의 환경/잔열 제거 보장은 아니다. 모든 조건은+35초 이전 AP만 초기화에 사용한다.
- `ENERGY-AP-BACKGROUND-CONTRAST-01`/`energy_ap_background_contrast_plan_v1`, SHA `acfa2510…4be0`. **PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED**, 생산 출력/registry 없음. 구조 판별6·본96/warmup48=144추론·runtime24·staging6/42·pull1·APK push/설치0·고정1,260초·전체5,250초(87분30초)/19,400ADB·재시도0. 새 계수 적합/새 모형 독립 확인0.
- 관련13테스트·실제PS Check·ADB 실행 차단 Check·원문 fixture 정상/결측/부분 실패·실제 판독CLI 통과. 공용 실행기 opt-in 분기와 C0 요청 소비 분모만 보완; Android/APK 변경0. 원래 오류/회수·cleanup 오류 보존·정리 중복/실패 후 추가 실행 차단. 현재 기기·장시간 안정성은 미검증. 기기 명령/추론/실측/생산claim0.
- **다음 행동 하나:** 이 미승인 묶음의 실행 시 현재 A24·설치본·환경 gate와 새 예산을 적용한다. 자료가 적격해도 정확도 PASS/열 정책 완성을 보장하지 않으며 미식별이면 자동 추가 없이 종료한다. 동결본·기각 후보·원본·소비 계획·default/strict/experiment_ready=false 보존. 아래는 당시 이력이다.

## 2026-10-02 AP 냉각률·부하 반응 식별 PC 판독 완료

- [결과·재현·최소 해결 조건](results/ap_rate_identification_01/README.md), [화면/CSV](results/ap_rate_identification_01/index.html), [검증](results/ap_rate_identification_01/verification.json). 기존 부하7세션+C/L 대조를 재사용; 개발1만으로 구조1개 적합, 이미 본 나머지는 사후 평가. β 최적 격자점은 기존0.0459325203/s, 공통 부하배율0.720002. 평균 일부 개선이나 **부하7세션 전부 최고오차 악화**로 미채택. 최근+65초 MAE0.189876→0.216500°C.
- 무부하 C의 일부 구간 +0.1°C와 후보 MAE0.346076°C를 확인. 작업 잔열 하나로 원인 확정 불가; 다른 APK/초기 이력/순서 자료를 인과적으로 빼지 않음. β/k 수치 추정 가능성과 물리적 유일성은 구분. L은 부하 전 기록 부족으로 모델 점수 제외/관측 보존.
- 관련8검사·실제 분석CLI·기존7점수/동결본 보존·공유 수치 검증 완료. 기존 후보의 독립 확인2/기본/strict/experiment_ready=false 보존; 새 후보는 사후 진단 파일에만 존재. 기기/실측/APK/새 계획/claim0.
- **다음 행동 하나:** 열 정책까지 확장할 경우 같은 조건의 무부하 배경과 부하 시점 반응을 분리하는 통합 대조를 고정한다. 동일 B2 단순 반복은 하지 않는다. 제한된 일정/서비스 시뮬레이터·실측 비용 대조와 결과 본문은 지금 사용할 수 있다. 아래는 당시 이력이다.

## 2026-10-02 준비 이력 AP 두 독립 확인 완료

- [실행·판독 보고서](AP_MEMORY_CONFIRM_RUN01_20261002.md), [그림/CSV](results/ap_memory_confirmation_01/run01/index.html), [검증](results/ap_memory_confirmation_01/run01/verification.json). 사용자 실측 승인으로 plan_v1 1회 실행, **completed_descriptive_only·소비·완료**. 본48/warmup16=64추론·runtime8·staging2/14·pull1·APK push/설치0·ADB1,698/6,600·581.797/2,090초·재시도0.
- 고정 τ30/γ0 후보의 새 확인 MAE **0.178596/0.189876°C**(기존 preload0.544909/0.370485), 최대0.737337/0.700567·최고 부호오차−0.121397/−0.303239°C. 실제 일정/부하 전 AP 조건부이며 조건당1세션. +35 조건 후기 관측+0.100°C 대 후보+0.001121°C로 후기 크기 미재현; 계수 재적합0, 정확도 PASS/기본 채택/strict 확대 없음.
- 공통120초 관측144.098982/140.797012J, 원래 W식 차이+11.535933/+14.879580J. 초기 AP27.4/27.9°C 범위 밖, 실제 lane병행1.334590/1.391242초. 앱cleanup2·회수각58파일·host정리각1·최종ps 부재·host exit0. timeout/관측 연결 소실/lifecycle_cancelled0. 원본8,778파일 inventory·소스103/동결4파일 보존, 분석 기기0.
- 원본 `D1Check_Arrival_Extension/energy_ap_memory_confirm_run_v1/FINAL_RECEIPT.json`, 판독 `ap_memory_confirm_run01_pc`. 실제 Check/Run/판독/공유수치 검증 완료. experiment_ready=false 유지. **다음 PC 행동 하나:** 두 독립 확인과 후기/전력 오차 한계를 제한 시뮬레이터 본문에 통합한다. 추가 실측 자동 실행 없음. 아래 준비·미승인 문구는 당시 이력이다.

## 2026-10-02 준비 이력 AP 독립 확인 계획 PC 완료

- [설계·명령·종료 기준](results/ap_memory_confirmation_01/README.md), [상태 화면](results/ap_memory_confirmation_01/index.html), [검증](results/ap_memory_confirmation_01/verification.json). 후보 τ30/γ0를 재적합 없이 확인하도록 부하 시작 +35/+65초 두 조건을 고정했다. 추가 가열 대신 준비 후 수동 유휴30초 차이를 사용하며 처음 자료 부적격이면 다음 세션을 막는다.
- `ENERGY-AP-MEMORY-CONFIRM-01`/`energy_ap_memory_confirm_plan_v1`, SHA `7013bcfe…8cfbd`. **PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED**, 실제 Run/output/registry 없음. 기존74e APK 재사용, 개발0/확인2·본48/warmup16=64추론·runtime8·staging2/14·pull1·push/설치0·고정420초·상한2,090초/ADB6,600·재시도0.
- 관련14검사·실제 PS Check/ADB차단 Check·원문 두 세션 판독 재현/결측 fixture 통과. 기존38근거/모형3개 hash 보존, APK/기기/새 실측/실행 claim0. 실제 일정과 부하 전 AP 조건부 확인이며 후기 재상승/스로틀/정책 비용/strict/default/experiment_ready=false는 미해결·불변이다.
- **다음 행동 하나:** 두 확인 세션 실행 시 이 계획의 예산과 현재 A24·설치본·환경 gate를 적용한다. 이번에는 PC 준비만 완료했다. 아래는 당시 이력이다.

## 2026-10-02 준비 이력 AP 후보·온도/처리시간 PC 분석 완료

- [보고서·재현](results/ap_preparation_memory_01/README.md), [화면](results/ap_preparation_memory_01/index.html), [검증](results/ap_preparation_memory_01/verification.json). 구조1개를 적합 전 고정하고 기존 개발1/사후 평가4로 구현·분해했다. τ30초/γ0, 기존 preload 대비 네 평가 MAE0.418/0.463/0.450/0.405→0.257/0.241/0.248/0.146°C. 최고오차도 개선하나 개발 최대오차0.849→1.132°C로 악화, 후기 재상승은 미해결이다.
- 개선의 주된 항은 유효 유휴 기준 E이며 지연 가열/물리 잔열 식별이 아니다. 새 독립 확인0, candidate는 별도 사후 진단용·정책 비용 차단. 기존 완료 COLLECT05 4세션/3,174요청의 23조건층 AP–시간 조정 연관은 양13/음10으로 스로틀 곡선 미식별. 온도 독립성도 입증하지 않는다.
- 관련22검사·실제 분석 CLI 재현·38근거/두freeze 해시 불변·CSV/그림/화면 검증. 기기/추론/설치/빌드/새계획/claim0; 기본·strict·experiment_ready=false 유지. 제한 시뮬레이터는 사용 가능하고 범용 동적 비용/열 피드백은 미검증이다.
- **다음 행동 하나:** 이번 고정 후보의 독립 AP 확인 여부를 결정한다. 필요 시 준비 이력이 다른 실행에서 충분한 부하 전 AP와 등록 부하·후기 유휴를 관측하며 기존 B2 단순 반복은 하지 않는다. 이번에는 실행안을 생성하거나 실측하지 않았다. 아래는 당시 이력이다.

## 2026-10-02 통합 시뮬레이터 실행·공유 경로 완료

- [시작 화면](results/simulator_workbench_01/index.html), [CLI·지원 범위·추가 실측 판정](results/simulator_workbench_01/README.md), [검증](results/simulator_workbench_01/verification.json). `tools.d1_simulator`로 입력→CPU/B2/B3 일정·응답→서비스 규칙→지원 차단→별도 실측 참조를 연결했다. 고정870건 모형은 별도 episode 경로로 연결. 기존 엔진/계수/strict/default는 불변이다.
- queue201 세 일정의 모든 실행 경계가 저장 결과와 일치; B2 서비스 적격/B3 urgent P95 부적격. 정확한 입력·seed·모드·일정이 일치할 때만 CPU/B2 네 실측 J/AP를 연결한다. 관측은 예측 입력이 아니며 동적 J/AP/열 피드백/순위는 unsupported/null, experiment_ready=false다.
- 관련18검사 PASS·두 실제 CLI/재실행 덮어쓰기 차단·HTML/SVG/CSV 일치·Edge 화면 확인. 작은 공유 번들만 필요해 기기/대용량 원본 없이 재현 가능. 이번 기기명령/추론/실측/빌드/새 계획/claim0. 원래 동결본·기각 후보·원자료·소비 계획 보존.
- **완료/남은 범위:** 제한된 일정/서비스 시뮬레이터와 실측 대조 도구는 완료. 일반 동적 에너지·AP, 후기 최고/열→처리시간의 정확도는 미완료이며 반복 실측만으로 해결됐다고 하지 않는다. 새 계수 식별 목적이 없는 동일 진단은 반복하지 않았다. **다음 행동 하나:** 통합 화면으로 queue201의 서비스 상충과 별도 관측 비용을 결과 시연한다. 아래는 당시 이력이다.

## 2026-10-02 기록 CPU/B2 네 세션 완료·제한 시뮬레이션 본문 반영

- [실행·소비·판정](RECORDED_POLICY_COMPARE_20261002.md), [관측 화면/CSV](results/recorded_policy_comparison_01/run01/index.html), [본문](ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md). 새 opt-in CPU 배정/같은 서명 APK·CPU→B2→B2→CPU4세션 모두 completed_descriptive_only. 본96/warmup32=128추론·runtime16·staging4/28·pull/push/설치 각1, 1,279.649/3,670초·ADB3,386/13,000·재시도0. 사전 연결7 포함 총3,393명령.
- 같은120초의 B2−CPU J는−9.198/−1.611(평균−5.405), urgent P95−282.761/−327.330ms·마감 충족18/24→20/24가 두 쌍에서 관측됐다. B2 두 관측 자체 차이8.845J·초기 AP30.1–30.6°C/이력 차이 때문에 안정적 절감률/정책 우월성은 미판정. AP 최고 차이0/−0.5°C·공통창 마지막 유효 표본−승인 초기 변화 차이−1/+0.1°C. 온라인 정책/일반 동적 모형 검증 아님.
- 요청 전체 시작/반환/저장/worker/lane 해제96·미완료0, 앱 정상cleanup4·회수각58파일·세션별 host 정리1 및 프로세스 부재. 설치 정리1은 별도, parent/child exited·정상 receipt/registry completed. timeout/관측된 연결 소실/lifecycle_cancelled0. plan_v1 소비·완료로 재실행 금지.
- Python13/Android10·실제 PS Check/Run·분석CLI/CSV/그림·원문 J 재현 완료. 기존 freeze/기각 후보/default/strict/experiment_ready=false 유지. 제한 본문·직접 비용 비교까지 완료, 남은 일반 AP 후기/최고/열 피드백·임의 일정 예측은 미지원으로 명시했다. 다음 행동 하나: 팀과 제한된 최종 결론 검토. 추가 실측 자동 실행 없음. 아래는 당시 이력이다.

## 2026-10-02 사용자 지정 무선 주소 연결 실패 — 실측 미착수

- 사용자의 연결·실측 요청에 따라 지정 endpoint에 `adb connect`1회(15초 상한), `devices -l`1회(8초 상한)를 실행했다. 전자는 exit0이지만 본문 `failed to connect`, 후자는 exit0·기기0개다. timeout 없음, 연결 실패 내부 원인/페어링 소실 원인은 미확정이다. 자동 재연결·서버 재시작·설정 변경 없음.
- 외부 증거 `D1Check_Arrival_Extension/connection_check_20261002_025522/connection.json`. 설치/앱 실행/추론/실측/새 plan/claim0. 기존 bundle02·resident대조03은 실제 receipt completed_descriptive_only·registry/출력 존재를 확인해 재실행하지 않았다. 이번 연결 실패를 기존 실측 계획의 stopped 상태로 기록하지 않는다.
- 페어링 목록이 비었다는 사용자 관측에 따라 현재 페어링 화면의 IP:포트·코드를 요청했다. **다음 행동:** 현재 페어링 정보로 연결을 복구하고, 완료 진단 반복 대신 CPU_URGENT/B2 비용 비교의 별도 경로·예산을 준비한다. 기존 B2 재생 검사는 입력/backend가 B2로 고정되어 있으므로 CPU_URGENT manifest로 바꾸기만 해 실행할 수 없다. 현재 A24 동일성/환경 gate는 미도달, experiment_ready=false 유지.

## 2026-10-02 PC 모형 보완·제한 시뮬레이션 본문 완료

- [완성 본문](ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md), [PC 결과·재현·검증](results/ap_model_completion_pc_01/README.md), [화면](results/ap_model_completion_pc_01/index.html). 사용자 요청에 따라 기존 자료만 재사용했다. 등록 부하 지연1항 후보를 적합 전 계약 후 구현; 기존 개발1세션 τ4초/나머지4세션 사후 평가. MAE는5개 모두 소폭 감소하지만 최고오차5개 모두 악화·후기 상승 미재현으로 **미채택**. 구조/계수 추가 탐색0·새 독립 확인0, 원래freeze/preload/default/strict 불변.
- 저장 queue/201/실현1.5 일정3개만으로 비용 민감도를 구현했다. CPU_URGENT−B2 진단 산술−0.884J, 대칭 유휴 잔차 부호 전환0.00410W. 관측 protocol별 유한 스트레스 두 범위 모두0 포함; 보편 오차/신뢰구간/정책 순위 아님. 서비스 B2 통과/B3 부적격 보존. 후보를 엔진 정책 J/AP 비용으로 전달해도 null/unsupported 유지.
- PC18검사·실제 분석CLI/별도 경로 재현·기존5개 MAE 재현·두freeze/참조 source 보존·그림/CSV 확인. 새 기기/실측/설치/빌드/계획/claim0, experiment_ready=false 유지. PC 가능 범위의 본문과 대시보드는 완료했으며 ‘무부하 대조 없음’ 등 낡은 현재 설명을 최신 완료 결과로 정정했다.
- **실측만 남은 주장:** 서비스 적격 CPU_URGENT/B2의 비교 가능한 J/AP 차이·실행 간 변동성, 후기 AP/최고를 위한 이력 반응 식별과 별도 고정 모형 확인. 지연 후보 자체의 추가 확인 실측은 권고하지 않는다. 한 쌍 직접 비교와 동적 모형 검증은 별개다. **다음 행동 하나:** 완성 본문의 제한된 결론으로 연구를 마감할지, 정책 비용 비교 주장까지 확장할지 결정한다. 자동 실측 없음. 아래 ‘다음’은 당시 이력이다.

## 2026-10-02 AP 두 이력 확인02 — 두 실측·고정 판독 완료

- [새 실행02·정확한 소비·한계](AP_BUNDLE_CONFIRM_RUN02_20261002.md), [공유 화면/CSV/그림](results/ap_bundle_confirmation_01/run02/index.html), [검증](results/ap_bundle_confirmation_01/run02/verification.json). 사용자 승인 plan_v2 SHA `f11992ad…3f89` Run1회, **completed_descriptive_only·소비·완료**. 본48/warmup16/runtime8=64추론, staging2/14·pull1·APK push/설치0, ADB1,343/6,600·616.410/2,090초·재시도0. 이전01 재개 없음.
- 한 묶음→두 반묶음 모두24요청 terminal/반환/저장/worker/lane 해제 확인·관측 적격. 초기 AP28.1/28.7°C 범위 밖·실제 CG_DC1.609444/0.822579초. 공통120초 J145.621340/142.351264; 원래 W식 차이+10.205170/+13.483338J(+7.008/+9.472%). 짧은 병행 전력 계수 식별 아님.
- 변경 없는 preload AP 후보 MAE0.449945/0.404970°C(원래식5.911910/5.350159), 최대1.015364/0.691399°C. 150–175초 관측+0.2/+0.1°C에 후보는−0.007028/−0.014669°C: 평균 개선과 후기 재상승 미재현을 함께 보존. 각 이력1세션·실제 일정/부하 전 AP 조건부·3d8 APK 전이이며 계수 재보정/정확도 PASS/strict/default 승격 없음, experiment_ready=false.
- 앱 정상 cleanup2·회수2·소유자 host force-stop 각1회·기존 ps 대상 부재 확인, parent/child exited·최종 receipt/registry completed. timeout/관측된 연결 소실/lifecycle_cancelled 없음. PC10검사·실제 Check/Run/분석CLI·CSV/그림/구간합 확인. 원본6,993파일·old01/모형/APK18개 핵심파일·실행 소스/manifest/plan 해시 불변; 새 빌드/Android 수정0. 분석 기기0(실측ADB는 위1,343회).
- **다음 PC 작업 하나:** 이 두 이력 확인 결과를 제한 시뮬레이터 결과 본문에 반영해, 후기 열 방향·최고·동적 J/AP 순위 미판정과 함께 평가를 마무리한다. 새 실측/후보 재적합 자동 추가 없음. 아래 ‘다음’은 당시 이력이다.

## 2026-10-01 AP 일괄 판독 경로 PC 검증 완료

- [기존 보고서의 판독 검증](AP_BUNDLE_CONFIRM_RUN01_20261001.md#pc-판독-경로-검증--2026-10-01), [작은 검증/CSV 화면](results/ap_bundle_confirmation_01/readout_pc/index.html). 기존 queue 개발·확인 원문으로 실제 Python CLI4경우(완료2·둘째 부분기록·전류 결측·AP 결측)를 검증했다. J135.617969/144.565095·후보 MAE0.487518/0.417521°C가 재현됐다. **새 실측/독립 확인0**, 현재 burst/3d8 두 이력 검증으로 전용하지 않는다.
- 이전 판독의 잘린 JSONL→최종요약 누락/그림 실패→부적격+깨진 링크를 PC 재현하고 수정했다. 소비는 정상 prefix 하한·미회수 null·실제 host_inference_return을 구분하고, 첫 적격 세션/원래 receipt·후속 오류를 보존한다. 관련10검사 PASS·4CLI exit0·원자료 핵심25파일/두freeze 불변·빌드/기기/계획/claim0.
- 소비된 bundle plan_v1/receipt/registry·당시 소스 해시는 그대로다. 수정본의 해시가 달라 기존 계획을 최신 코드로 재분석/실행하지 않는다; 기존 결과를 보존하고 PC 복사본만 현재 분석 소스에 결합했다. strict/default/experiment_ready=false 유지. **다음 행동 하나:** 기기 사용이 가능할 때 이미 정한 두 AP 이력 확인을 새 ID로 한 번 실행한다. 이번에는 새 계획/실측을 추가하지 않았다. 아래 ‘다음’은 당시 이력이다.

## 2026-10-01 AP 일괄 확인01 — 연결 부재로 preflight 중단

- [계획·실행·종료](AP_BUNDLE_CONFIRM_RUN01_20261001.md), [작은 결과/화면](results/ap_bundle_confirmation_01/run01/index.html). 사용자 묶음 실측/재개 승인으로 Run1회, **claim 후 stopped_no_resume**. 첫 devices -l 반환 exit0지만 transport0개; 두 확인 모두 미시도. ADB1/6,600·실행기3.362482/2,090초, runtime/warmup/추론/staging/pull/push/설치0·재시도0.
- 기존 후보 고정·개발0/확인2의 실행 경로/PC26검사/실제PS Check 완료. parent/child 식별·원래stack/4 checkpoint·최종receipt 보존·두 host 소유자 exited 확인. 앱 미실행이므로 app cleanup/force-stop 해당 없음; 현재 앱 프로세스 부재는 미조회. 새 J/AP/병행/그림0, 모형 실패나 열모형 완성 판정 아님.
- 원본14파일/두freeze/APK/소스/동결 계획 해시 불변, PC 판독 완료·소비 후 Check 거절. strict/default/experiment_ready=false 유지. **다음 행동 하나:** 사용자 측 A24 무선 ADB 연결 복구. 이 plan_v1 재개·새 계획/실측 자동 추가 없음. 아래 ‘다음’은 당시 이력이다.

## 2026-10-01 유휴 시간·이력6세션 PC 판독 완료

- [판정·재현·남은 한 공백](RESIDENT_IDLE_HISTORY_PC_20261001.md), [화면/CSV/출력 범위](results/resident_history_01/index.html), [검증](results/resident_history_01/verification.json). 완료 C/L대조03＋기존4세션을 재사용했다. 고정 pre→late 적격5개 중 증가3/감소2, B2 pre는 활성 혼합/null. C10초 bin18개는0.869466–1.297921W로 비단조; 상관된 기술적 관측이며 인과/오차 상한 아님.
- 변경 없는 기존 가산 후보를 새 L의35.008415–120초에 적용하면 기존 차이+18.139070→후보+27.928944J(부하 후 유휴+16.355960→+24.776531J)로 악화. 기존4점수 보존·총2개선/3악화, 미채택 유지. 새로운 time/AP/이력 계수·후보적합0, 동적 J/AP 순위null. 원래freeze/AP후보/strict/default/experiment_ready=false 불변.
- 실제CLI 포함6검사 통과, 기존4원문/새pair source해시·동결2파일·120초/고정창 수치·CSV 재현 확인. APK749계열4세션과3d8계열C/L 프로토콜은 분리한다. L 냉각후기 결측과 B2 혼합창을 채우지 않음. 기기 명령/실측/설치/빌드/새 계획/claim0.
- 다음 PC 작업 하나: 제한 시뮬레이터의 서비스 결과와 동적 J/AP 미판정을 함께 제시하도록 기존 결과 본문을 정리한다. 기록된 고정 일정 재생은 가능하며 동적 정책 우월성은 미입증. 아래 ‘다음’과 준비/실측 문구는 당시 이력이다.

## 2026-10-01 resident 대조03 두 세션 완료·PC 판독 완료

- [실행 결과·예산·원본·재현](RESIDENT_CONTROL_RUN03_20261001.md), [공유 화면/CSV](results/resident_control_design_01/run03/index.html), [보존·판독 검증](results/resident_control_design_01/run03/verification.json). 사용자 승인 plan_v3 1회 실행, **completed_descriptive_only·소비·종료**. C0/L24 모두 정상 완료, runtime8/warmup16/본24=40추론, staging2/14·pull1·APK push/설치0, ADB1,543/6,600·679.531/2,090초·재시도0.
- C/L 공통120초 J124.545817/137.005431; 원래 동결식 진단 차이+22.506194/+18.679647J. pre→late W는 C0.971881→0.989955/L1.195793→1.011505, 변화 차이−0.202361W. 실제 CG_DC1.455957초. 초기 AP27.3/27.7°C 범위 밖·외삽이며 인과/독립 확인/정확도 PASS 아님. L 냉각후기 전력0.176161초 결측·AP bracket 부재로 전체창 null, 창 대체 없음.
- 앱 정상 cleanup 두 건/소유자 host 정리/기존 ps 대상 부재 확인, Run exit0·회수 완료. timeout/관측된 연결 소실/lifecycle_cancelled 없음. 원본7,923파일·실행95소스/APK/두freeze 불변; 판독4테스트·고정 수치/CSV/그림 일치. 새 계수/후보적합/추가 기기 실행0, strict/default/experiment_ready=false 유지.
- 다음 PC 작업 하나: 이 완전 C/L 쌍과 기존4세션으로 유휴 전력의 시간·이력 의존성과 식별 가능한 보완 범위를 판정한다. 과거 종료 계획 재개와 자동 재실측 없음. 아래 준비/중단 문구는 당시 이력이다.

## 2026-10-01 resident 대조03 실행 계획 준비 완료

- [새 계획·정확한 예산·Check/승인 후 Run](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#새-실행-계획03-준비-완료--2026-10-01), [대상해시·검증](results/resident_control_design_01/plan03/verification.json). `ENERGY-AP-RESIDENT-CONTROL-03`/plan_v3 SHA `2e9b3fcd…7bf6d8`, **PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED**, output/registry 미생성. 기존 plan_v1/v2는 stopped_no_resume.
- 같은 APK/부하/판독 기준으로 C0→L24, runtime8/warmup16/본24/총40추론·staging2/14·pull/push/설치 각각≤1·고정420초·전체2,090초·ADB6,600·재시도/대체/추가0. 공간 검사 수정본과 새 ID를 소스95개에 동결. PC7테스트·실제PS Check·보호된 Python Check 통과, 기기0/Run0/APK재빌드0. 현재 환경·설치본은 실행 직전 재확인한다.
- 사용자 정리 receipt `finished_preservation_verified`: 971폴더 삭제·실패0·보존해시 확인. PC계획 검사 당시 여유약11.48GiB; 지속 여유 보장은 아니다. 두freeze/과거 자료/strict/default/experiment_ready=false 유지.
- 다음 행동 하나: 위 새 계획03의 예산 내 실측 실행 여부 결정. 아래 정리 도구 차단과 계획01/02 준비 문구는 당시 이력이다.

## 2026-10-01 재생성 가능한 빌드 중간 파일 정리 — 도구 삭제 차단

- [정리 후보·검증·차단 요약](results/resident_control_design_01/storage_cleanup_20261001.json): 완료 빌드의 중간971폴더/20,351파일/4,426,671,652바이트만 선정. 서명APK·로그·영수증62파일 해시 확인, 실측 원본/계획/registry/freeze/소스/다른worktree/다운로드캐시 보존. 실제 원격421786e와 로컬의 기존 소스·문서 백업 일치 확인.
- 삭제 명령은 자동 승인 검토의 `blocked by policy`로 프로세스 생성 전에 거부됨. **삭제0·확보0**, 우회 실행 없음. `tools/Clear-D1BuildIntermediates.ps1 -Action Check -Manifest <로컬 candidates.json>`은 실제 경로/파일수·바이트/해시/활성build/reparse 검사 통과, 기기명령0. 로컬 상세 목록은 `D1Check_Arrival_Extension/storage_cleanup_pc_20261001_v1/candidates.json`, GitHub에는 스크립트와 작은 요약만 저장.
- 다음 행동 하나: 사용자 로컬 PowerShell에서 같은 manifest로 정리 스크립트의 `-Action Run`을 실행한다. 기존 receipt가 있으면 중복 실행을 차단하고, 삭제/부분실패·보존 해시·free를 별도 receipt로 기록한다. 실제 삭제 완료와 Check 통과를 구분한다. 아래 실측 상태·experiment_ready=false는 불변이다.

## 2026-10-01 resident 대조02 preflight 중단·PC 마무리 완료

- [실행·진단·검증](RESIDENT_CONTROL_RUN02_20261001.md), [작은 결과](results/resident_control_design_01/run02/index.html). plan_v2/SHA5073b2b9…52fde7은 1회 소비·**stopped_no_resume**. 설치본 pull 로컬 쓰기 I/O 오류·직후 C: free0 확인. 8.360초/ADB5/pull1부분, 세션·launch·runtime·warmup·본 요청·추론·staging·APK push·설치0. 환경/설치본 전체 검증 미도달, 새 J/AP 없음. 앱/host 종료 해당 없음(미실행), 현재 프로세스 부재 미조회.
- 기존 화면34조회(33정상 중앙0.531/최대0.610초,1timeout)의 내부 원인은 미확정. timeout·marker·주기 유지. claim 전 최소 APK 저장 공간 검사·실패/미시도 판독 보완, **PC14통과**·원본30파일/부분APK/두freeze 해시 보존·APK재빌드0. 사용자 공간 확보 후 재개는 PC 기록·Git만, 기기명령0. strict/default/experiment_ready=false 불변.
- 다음 행동 하나: 향후 실측을 진행할 경우 최소 공간 검사를 반영한 별도 새 ID·승인을 사용한다. plan_v1/v2 재개·새 계획 자동 생성·재실측 없음. 아래 준비 문구는 당시 이력이다.

## 2026-10-01 resident 대조 종료 — C 완료/L 부분 중단

- [실행·소비·판독](RESIDENT_CONTROL_RUN01_20261001.md), [공유 화면/CSV](results/resident_control_design_01/run01/index.html). 승인 plan_v1 1회 실행, **stopped_no_resume**. 시도2/정상완료1, runtime8/warmup16/본24=추론40, staging14/pull1/APK push·설치각1, ADB1240/6600, 477.671/2090초. 재시도0.
- C 무부하120초145.578J; pre→late W1.295715→1.114261(−0.181454W). 부하 없는 시간 변화의 근거이며 원인/새 계수 미식별. 시작AP29.6°C 범위 밖, 동결식+1.474J는 진단/strict PASS 아님. 냉각 끝 전력0.826초 결측/null.
- L24개 시작/output/persist/worker/lane event 확보, 경로60.168초까지만 회수. 화면 명령1229의2초 timeout/부분stdout, 연결 소실 증거 없음. L전체창/C–L 차이 null, 세션 완료/최종 품질 미확인. C app cleanup 완료/L app cleanup 미확인; owner host 정리·대상 프로세스 부재 확인. freeze/default/strict/experiment_ready=false 유지.
- 다음 PC 작업 하나: 화면 조회 partial stdout/marker·인접 지연·subprocess 종료 경계 진단. 종료 계획 재개/새 실측 자동 실행 없음. 아래 준비 문구는 당시 이력이다.

## 2026-10-01 무부하 대조 구현·서명 APK·실행 계획 준비 완료

- [최종 해시·예산·Check/승인 후 명령](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#실행-준비-완료-2026-10-01): 새 opt-in C0/L24를 동일4runtime/8warmup·baseline30/common120/cooling60·정상 cleanup으로 연결했다. host0/24 분모·합계·실패시 다음 세션 차단·실제 transport 자동 선택(온라인1개)을 검증했다. 기존24건 경로 보존.
- `ENERGY-AP-RESIDENT-CONTROL-01`/plan_v1 SHA `7c200ab7…58e135`, 프로젝트 서명 APK `3d8ea871…4e94c2`. **PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED**, output/registry 없음. 두 세션/40추론/runtime8/staging14·pull/push/설치 각≤1·고정420초/전체2,090초·ADB6,600·재시도0.
- Python18＋Android9(실제callback3 포함) 통과·서명 빌드/실제PS Check 완료. native/장시간/환경은 기기 미검증. ADB·Run·설치·추론0, strict/default/동결/experiment_ready=false 유지. 다음 행동 하나: 이 단일 계획의 별도 실측 승인 여부 결정. 아래 실행 차단은 구현 전 이력이다.

## 2026-10-01 무부하 대조 설계 확정 — 실행 경로 차단

- [필요성·두 세션 설계·차단 조건](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md), [계획/입력/PC Check](results/resident_control_design_01/README.md). 동적 에너지 보완에는 같은 준비 후 C무부하1→L짧은 CG_DC1 대조가 필요하다. 기존 고정 일정 설명에는 추가 실측이 필수 아님. 구조 판별용 개발이며 독립 확인/인과/정책 PASS가 아니다.
- 제안: 본24＋warmup16＝40추론/runtime8·staging2/14파일·pull/push/설치 각≤1·고정420초·총2,090초·ADB6,600·재시도0. **DESIGN_CHECKED_EXECUTION_BLOCKED**: 현 APK/host는 정확히24요청을 요구하므로0요청 대조 불가. 후보APK/Run=null, 실행준비 완료 아님. 기존 APK/동결/strict/experiment_ready=false 보존, 기기/claim0.
- 다음 행동 하나: 기존 수집기의0요청 대조 opt-in과0/24 분모·정상 종료 경계를 구현/검증하고 같은 새 서명 APK로 실행 묶음을 완성한다. 현재 설계는 미승인·미소비이며 아래 “다음”은 당시 이력이다.

## 2026-10-01 부하 전 전력 후보 PC 평가 완료 — 채택하지 않음

- [후보1개·4세션 결과·최소 해결 조건](RESIDENT_POWER_CANDIDATE_PC_20261001.md), [휴대 입력/CSV/그림/재현](results/resident_power_candidate_01/README.md). 부하 전20초의 평균 W로 원래 상태 전력을 가산 이동했다. 첫 dispatch→120초 잔차는 B2 +1.072→−17.385J, 유휴 개발 +16.087→+4.280J, 확인 +10.453→+17.702J, 전이 +16.364→+12.957J. 2개선/2악화로 기본 경로 채택 없음. 전체120초 예측·독립 확인으로 표현하지 않는다.
- 현재4세션만으로 일정한 유휴 보정의 전용을 지지하지 못했다. 전후 전력 변화가 부하 없이도 발생하는지 구분할 대조가 없다. 기존 AP 후보/동결 W·원자료·strict·experiment_ready=false 유지. PC7테스트/실제4세션 판독·구간합·정보 비누설 통과, 기기/계획/claim/추가 후보0.
- 다음 행동 하나: 같은 준비·resident에서 무부하 대조와 짧은 CG_DC 부하를 비교할 최소 원인 분리 수집 설계를 확정한다. 이번에는 실행 계획·예산을 만들거나 실측하지 않았다. 아래 “다음”은 당시 이력이다.

## 2026-10-01 CG_DC 전이 확인1 완료 — 계수/strict 불변

- [실측·소비·해석](AP_CGDC_TRANSFER_RUN01_20261001.md), [공유 HTML/CSV/그림](results/energy_ap_cgdc_transfer_01/run01/index.html). 승인된 plan_v2를1회 실행: 본24/warmup8/runtime4·전부 반환/lane 해제, staging7·pull1·APK push/설치0, ADB737(실행736＋선택1)/3200·실행293.138초/1300. 앱 정상 cleanup·58파일 회수·세션 host 정리·프로세스 부재 확인. 연결 소실/lifecycle_cancelled 미관측.
- 시작 AP28.3°C·실제 lane CG_DC1.466752초. 정확한120초 J 관측135.146493 대 원래식155.730344＝+20.583851J(+15.230770%). AP35.008859–180.062298초의 기존/고정 후보 MAE5.831406/0.463463°C. 부하 전25표본/span65.36초만 후보 입력, 부하 후 재적합0; 후반 재상승 형태는 미재현. 정확도/정책 PASS 없음·strict/기본 모형/experiment_ready=false 유지.
- Check/98소스·APK/두 freeze 해시·분모/구간합·24요청 경계·cleanup·소비 후 Check 거절·그림3개 검토 완료. plan_v2는 **소비·완료/재실행 불가**, 원본 `energy_ap_cgdc_transfer_run_v2/FINAL_RECEIPT.json`·registry 보존. 추가 실측 자동 실행 없음. 아래 미승인/미실행은 당시 이력이다.
- [기존4세션 유휴 PC 대조](results/energy_ap_cgdc_transfer_01/run01/idle_comparison/summary.json) 완료: 경계 혼합 제외 부하 후 관측 W는 B2 1.227498·유휴 개발1.046593·확인1.058204·전이1.055108, 동결계수1.225433W. 원문120초 J 재현·관련3테스트 PASS, 신규 계수/기기 명령0. 원인 귀속/정책 차이 허용폭은 미판정. 다음 PC 작업 하나: 전이 확인과 유휴 조건 전용 한계를 기존 연구 결과·논의 본문에 반영한다.

## 2026-09-30 팀 공유 입구 갱신 완료

- [팀 안내](team/README.md)를 최신 결과·근거·A24 전이 확인1·S26/NPU 자료 요청·GitHub/로컬 파일 경계로 갱신했다. 기존9월26일 본문은 접힌 이력으로 보존했고 저장소 루트에 README를 추가했다. 팀원에게 전달할 요약도 안내에 포함했다.
- 착수 `9bbfe6d` clean, 활성 링크32개/고유 대상26개 모두 추적 파일 확인, 기존 안내 본문 보존·계획/APK/원래·후보 freeze 해시 일치·diff-check PASS. 문서 검증이며 코드/기기 검증 추가 아님. 기기 명령·Run·claim0, 계획v2 미승인·미소비/`experiment_ready=false` 유지.
- 다음 행동 하나: 작업 브랜치의 팀 README 링크를 팀원에게 전달하고 S26/NPU 담당자의 보유 근거를 위 제출 목록으로 받는다. 본 안내는 실측 실행 승인이 아니다.

## 2026-09-30 연구 결과·논의 초안 완료 — 기존 증거만 사용

- [본문 초안](ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md): 고정870건 실측의 상충, 저장135개 PC 일정의 서비스 선별, B2 에너지 상쇄, AP 후보 확인과 형태 한계를 한 결과·논의로 연결했다. 기존 그림만 참조하며 실측·PC 일정·외삽·독립 확인1세션의 역할을 명시했다. 동적 에너지/열 정책 우월성은 미입증이다.
- 저장 JSON/CSV7개에서 수치53항목·근거 링크16개 대조 완료. 새 모형/분석 배치/기기 명령0; 원래/후보 freeze·계획v2 해시 불변, 미승인·미소비 유지. 검증 대상은 `6b99141`+이번 문서 변경이며 [기록](results/energy_ap_results_discussion_01/verification.json)에 보존했다. `experiment_ready=false`.
- 실측 대기 중 PC 본문 작성은 완료. 다음 행동 하나: 기기 사용이 가능할 때 기존 별도 CG_DC 전이 확인1의 실행 승인 여부 결정. 추가 준비/감사 단계를 만들지 않는다.

## 2026-09-30 실측 후 판독·그림 자동화 완료 — 실행 계획 불변

- [PC 판독 명령·성공/실패 출력](AP_CGDC_TRANSFER_PREP_20260930.md#실측-후-pc-판독과-그림-자동화-2026-09-30): 별도 `d1_ap_transfer_report`가 고정 readout을 연결해 예정/실제 lane·120초 누적 J/잔차·부하후 AP/잔차·CSV·단일 HTML을 만든다. 실패/부분 회수/센서 누락은 null·사유·inventory, 완성 비교 그림0; 렌더링 실패는 적격성 실패와 분리한다. 부하후 AP 재적합/새 후보0, 원자료/strict/기본 simulator 불변.
- 관련 PC7검사 통과, fixture 그림은 외부 `ap_transfer_report_pc_v1/fixture/preview`에 **NOT MEASURED**로만 보존. 미실행 실제계획 판독은 예상한 not_evaluable이며 계획 실행 실패가 아님. 계획v2 SHA `e1826853…9f3234`/Check·원본/후보 freeze 불변, output/registry 없음·미승인/미소비 유지. ADB/Run/APK/설치/추론0, `experiment_ready=false`.
- 현재 PC 자동화 완료. 다음 행동 하나: 기기 사용이 가능할 때 기존 별도 CG_DC 전이 확인1의 실행 승인 여부 결정. 이번 도구가 새 실측/정책 정확도 근거를 만들지는 않는다.

## 2026-09-30 실측 전 준비 완료 — 다른 CG_DC 일정의 고정 절차 전이 확인

- [단일 확인 계획·실행 전 조건·판독 종료점](AP_CGDC_TRANSFER_PREP_20260930.md), [입력·분석 계약·검증 요약](results/energy_ap_cgdc_transfer_01/README.md). 저장 burst/201/B2 일정에서 도착0–4.840초는 APK contract 그대로, release만+35초로 부하 전 유휴 약65초 확보. 새 개발/계수 재적합0; 기존 동결 W와 기존 유휴 후보의 전이 진단이며 B2 서비스·정책 순위 확인 아님. CG_DC만 관측하며 DC_DG 공백은 남는다.
- 유일 권고 `ENERGY-AP-CGDC-TRANSFER-02`/`energy_ap_cgdc_transfer_plan_v2`, SHA `e1826853…9f3234`: 확인1·runtime4·warmup8·본작업24·명시적추론32·staging7·pull/선택적 APK push/설치 각≤1·1,300초·ADB≤3,200·재시도0. **미승인·미소비**, output/registry 미생성. 이번 PC v1 초안은 도착 이동이 실제 앱 contract에 어긋나 발견 후 실행불가 초안으로 보존; 기기 실패/소비로 처리하지 않음. 기존 queue24와 종료 계획은 보존.
- Python9＋실제 Android contract/선택 경계 JVM1 및 PowerShell Check PASS, APK 본문/계수/strict 불변·재빌드0. **기기명령·Run·설치·추론0**, `experiment_ready=false`. 준비 작업 완료; **다음 행동 하나:** 이 별도 한 세션의 실측 예산 승인 여부 결정. 실행 전 동일A24·유일 transport·설치본/서명·기존 환경/품질 gate는 현재 미검증. 장시간/연결 안정성·정책 비용 지원을 PC PASS로 승격하지 않음.

## 2026-09-30 저온 AP 조건부 진단 연결 완료 — 최고/한도/J/정책 순위 차단

- [이번 출력 경계와 구현](AP_SIMULATION_CLOSURE_PC_20260930.md#6-저온-ap-출력의-pc-연결-2026-09-30), [휴대용 입력·CSV·재현](results/energy_ap_idle_response_01/low_temperature_scope_v1/README.md). 기존 두 세션의 실제 일정/부하 전 AP로만 후보 경로를 재현(개발 MAE0.487518°C·확인0.417521°C). 정보 시점은 첫 dispatch 직전35.007초이며 그 이전을 사전 예측으로 출력하지 않는다. 같은 APK·resident·입력·프로토콜/충분한 pre-load만 진단 계산 허용, 경험적 일반화/PASS 아님.
- 실제 arrival 집계기에 후보가 들어오면 전체 J·AP 최고·한도 초과·순위를 null로 차단한다. 관련12검사 PASS, 원래 동결·후보 절차 SHA 불변; 재적합/새 실측/ADB/APK/계획/claim0. **PC 연결은 이 범위에서 완료**, `experiment_ready=false` 유지. 다음 결정은 동적 J/AP 순위를 현재 미검증으로 보고하고 지원된 고정 CC_DG 상충 결과를 활용하는 것이다. 아래 AP30.0°C 중단은 그대로 보존한다.

## 2026-09-30 B2 범위 내 확인 — AP30.0°C로 본 작업 전 중단

- [원본 receipt·작은 요약·실제 소비](ARRIVAL_B2_INRANGE_RUN01_20260930.md). 새 `ENERGY-AP-RECORDED-B2-INRANGE-01`을 승인으로1회 실행했고 `stopped_no_resume`. 현재 동일A24·설치본·환경 확인, 배터리68%·비충전·thermal0. runtime4/warmup8 이후 시작 AP30.0°C(조회 bracket0.210초)가 연구 범위32.5–34.0°C 밖이라 arm을 보내지 않았다. 본 작업0·공식창0, J/AP 새 오차 없음. 설치본pull1·staging7·APK push/설치0, ADB232/3,201, 활성시간76.207/1,315초. 세션 host정리 completed·프로세스 부재, 앱 자체 cleanup은 미회수로 미확인.
- 관련PC9테스트·기기없는Check 통과, 실행 후 소비Check 거절 확인. 기술 결함이 확인되지 않았으므로 같은 온도 gate를 통과할 때까지 반복하거나 기준/가열을 바꾸지 않는다. **다음 행동 하나:** 정상 저온 자료에서 필요한 AP 예측 출력과 별도 모형 적용 계약을 확정한다. 기존 동결/strict/원자료/FAIL/`experiment_ready=false` 보존.

## 2026-09-30 대표 B2 짧은 전환의 기존 계측 재사용 경계 확정

- [저장 PC 일정·동결 모형·기존 8세션의 한정 대조](ARRIVAL_SERVICE_CHOICE_PC_20260930.md#대표-b2의-기존-계측으로-독립-확인-가능한가-2026-09-30). 대표 B2 저장 일정은 CG_DC 2.531초·시작 AP29°C 미측정 가정. 실제 B2 재생1은 24/24·120초를 회수했으나 CG_DC1.683초·시작29.9°C로 동결 시작32.5–34.0°C 밖이다. 조건부 외삽 J +1.062J에는 구간 오차 상쇄가 있고 AP MAE3.555°C다. 다른 두 저온120초의 W 오차 +20.090/+11.305J도 별도 조건이다. **지원 범위 안 독립 짧은 B2 전체창 예측 확인은 0세션**이며 온라인 B2·정책 J/AP 순위는 미지원.
- 동결 SHA와 공유 결과·strict 차단을 읽기 전용으로 대조했다. 새 모형·정책 배치·기기명령·계획/claim 0, 동결/원자료/FAIL/`experiment_ready=false` 보존. **다음 행동 하나:** 필요한 경우 실제 관측 시작 AP와 전체120초 단독↔CG_DC↔유휴를 갖는 독립 B2 확인 한 조건만 별도 실행 계약으로 구체화한다. 같은 저온 B2 진단 반복은 권고하지 않는다.

## 2026-09-30 보수적 서비스 비교 규칙 고정 — 저장 PC 판독은 사후, J/AP 순위 미지원

- [응답·완료 판독과 새 규칙](ARRIVAL_SERVICE_CHOICE_PC_20260930.md), [계약·135사례 CSV·재현](results/arrival_service_guard_01/README.md). 같은 입력의 `CPU_URGENT` 대비 예정24건 전부 완료, 긴급·일반 기한 미준수 비증가, 긴급 완료 응답 P95 비증가를 **연구용 선별 규칙**으로 고정했다. 기존 δ=0은 탐색점이었고 실제 UX SLA는 아직 없다. 이미 본 저장 결과의 판독은 독립 확인이 아니다.
- 대표 queue/201/실현1.5에서는 B2 적격, B3는 긴급 P95 +373.652ms로 부적격. 45개 저장 입력에서는 B2 21개·B3 22개 적격, 둘 다 적격인 입력7개. 모든 실측 기반 전체창 J/AP·정책 비용 순위는 null이며 동결 모형·원자료·FAIL·`experiment_ready=false` 유지. 관련 PC 테스트2건 통과, 시뮬레이션 배치·기기 명령0. **다음 행동 하나:** 실제 서비스 허용폭을 정하기 전에는 대표 B2의 짧은 전환·전체창 J/AP 독립 예측 근거가 기존 자료로 해제되는지 특정된 경계만 다룬다.

## 2026-09-30 저장 도착 정책의 응답·완료 판독 완료 — 실측 J/AP 순위 미지원

- [135개 저장 PC 일정의 서비스 판독](ARRIVAL_SERVICE_CHOICE_PC_20260930.md), [재현 CSV·대표 지원 경계](results/arrival_service_choice_01/README.md). 사전 선정 queue/seed201/실현 간섭1.5에서 세 정책 모두 24/24 완료, 연구용 1.5초 긴급·6초 일반 기한 내 완료는 CPU_URGENT18/24, B2 20/24, B3 20/24. B2 긴급 P95 424.755ms 대 B3 1014.998ms, 일반 평균은 B2 4188.833ms 대 B3 4044.433ms. 채택 SLA나 독립 실기기 성과 아님.
- 동결 A24 모형은 세 일정 모두 t=0부터 짧은 도착 전환을 지원하지 않으며 초기 AP 29°C도 미관측 PC 가정이다. J/AP와 정책 에너지 순위는 null. 저장 135사례 재집계·관련 PC 테스트2건 PASS, 시뮬레이터 배치/기기명령0; 동결/원자료/FAIL/`experiment_ready=false` 유지. **다음 행동 하나:** 대표 B2/B3 비교에서 허용할 긴급 응답·일반 기한 손실 기준을 연구 목적에 맞게 사전 고정한다.

## 2026-09-30 고정 CC_DG 연구 결과 본문·대시보드 반영 완료

- [제한 결과 본문과 오차 분해](ENERGY_OPERATIONAL_DECISION_PC_20260926.md), [4세션 관측/모형 대비 대시보드](results/ap_simulation_closure_01/readout/index.html). A24 고정870건 직렬/병행 각 개발1·확인1: 병행 완료시간 이득은 각각122.456초/126.319초, 부하 AP 최고는 각각+1.2°C/+1.9°C. 같은480초 기기 전체 에너지 차이(병행−직렬)는 개발−36.255J, 확인+4.559J로 방향이 바뀌었다. 개발 템플릿의 확인 에너지 차이 예측−36.216J는 관측 방향을 재현하지 못한다. J는 raw=mA 조건부이며 절대 정확도 미인증; 방식당 독립 확인1세션으로 변동성·정책 우월성 미판정.
- 저장 CSV에서 네 관측행을 읽어 화면에 연결하고 확인 차이를 대조하는 PC 테스트7건 통과. 동적 정책135사례 전체창 실측 J/AP 지원0, 기존 동결/원본/FAIL/`experiment_ready=false` 유지. 기기 명령0. **다음 행동 하나:** 저장된 동적 정책 일정의 응답·완료 요구 충족 여부를 제한 PC 비교로 판독한다(J/AP는 지원 밖으로 명시).

## 2026-09-30 AP·에너지 연결 판정 완료 — 고정 비교 가능, 동적 J/AP 순위 미지원

- [판정·구현·최소 완료 조건](AP_SIMULATION_CLOSURE_PC_20260930.md), [작은 입력/CSV/그림/재현](results/ap_simulation_closure_01/README.md). 기존8세션의 lane-free 19구간 중 저온 확인1세션의 두 구간에서 상승→하강을 확인했다. AP 조회 중앙2.522–2.680초, 값 변화 관측 간격 중앙10.352–15.053초; HAL 내부 측정시각이 없어 센서 지연/열 이력은 분리 미식별. 후보는 조건부 진단에 한정하고 기본/strict에 채택하지 않는다.
- 새 유휴 개발/확인의120초 동결 W 외삽 오차는 +20.090J(+14.814%)/+11.305J(+7.820%). B2 +1.062J를 보편 오차로 쓰지 않는다. 기존 고정CC_DG870건/480초 decision 인터페이스는 `TRADEOFF` 재현(회고 비교1개, 순위/정확도 PASS 아님). 저장135개 동적 일정의 전체창 실측 J/AP 지원은0, 대표3개 J/AP/rank=null. 새 fit/정책배치/기기명령/계획/claim0; 원본·동결·FAIL·`experiment_ready=false` 유지.
- **다음 행동 하나:** 실행 가능한 고정CC_DG 직렬/병행의 완료시간–J–AP 상충 및 에너지 순위 실패를 연구 결과 본문에 반영한다. 동적 목표의 필수 공백은 동일 프로토콜 B2/B3 짧은 전환의 전체창 에너지·AP 전이와 정책 차이 판별력으로 특정했으며 자동 재실측하지 않는다. 아래는 각 시점 기록이다.

## 2026-09-30 저온 resident AP 반응 — 승인 2세션 완료, 후보 기본 미채택

- [개발→동결→확인 결과와 소비·한계](ENERGY_AP_IDLE_RESPONSE_RUN01_20260929.md), [관측/예측 AP 그림·CSV](results/energy_ap_idle_response_01/run01/README.md). `ENERGY-AP-IDLE-RESPONSE-01` 개발·확인 각 1세션 완료, 각 작업24·warmup8·runtime4, 공통120초와 냉각 회수. 개발 전 부하 AP26표본·64.425초로 절차를 식별하고 확인 전 freeze SHA `8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5` 기록. 확인은 자기 부하 전 AP26표본·64.305초만 조건부 입력으로 사용했다.
- 확인의 별도 후보 AP MAE0.418°C 대 기존 동결식 저온 외삽5.461°C이나, 마지막 부하 후 관측 AP 변화0.000°C·후보−0.719°C로 지연된 상승 형태는 미재현. strict·정확도 PASS·정책 선택 적격성은 미판정; 후보를 기본 simulator에 넣지 않는다. 실제 명시추론64/상한64, ADB **총1,627**(실행기1,626＋선택1)/6,600, 628.032/2,120초, 설치본 pull1·APK push/설치0, 앱 cleanup/host 종료/프로세스 부재 확인. 소비·종료 계획 재실행 금지, 기존 동결·원본·FAIL·`experiment_ready=false` 유지. **다음 PC 작업 하나:** 기존 자료로 lane 해제 뒤 AP 최고 표본 지연과 갱신 간격을 대조해 단일 AP 상태의 한계를 판정한다.

## 2026-09-29 저온 resident AP 반응 — 별도 2세션 계획 PC 준비·미승인

- [유휴 AP 방향 오류의 식별 설계·계획·예산](ENERGY_AP_IDLE_RESPONSE_PLAN_PC_20260929.md), [분석 계약/재현](results/energy_ap_idle_response_01/README.md). 동결 idle 평형34.380°C 항이 B2 저온29.9°C에서 가열 방향을 만들었다. 기존 B2 부하 전 유휴는32.072초·AP13표본으로 부하 전 유효 기준을 식별하기 부족하다. 기존 β/상태별 유휴 대비 기울기를 고정하고 **부하 전 AP로만** 세션별 유효 기준을 산출하는 별도 진단 구조를 구현했다. 주변온도·숨은 잔열은 미식별, 기존 단순 시작값 기준 후보는 미채택 유지.
- 같은 서명 APK/모델/관측 경로의 새 `ENERGY-AP-IDLE-RESPONSE-01`: 저온 시작·한 묶음 개발1 → 구조/코드 동결 → 두 묶음 확인1, 총 작업48·warmup16·명시추론64·runtime8·staging2/14파일·APK push/설치 각≤1·ADB≤6,600·전체≤2,120초, 재시도0. 외부 별도 plan/manifest/Check 준비, **Run·ADB·claim 0**. PC 관련 테스트/Check 결과는 보고서를 따른다. `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`; 동결/strict/기본 simulator/원본/FAIL/`experiment_ready=false` 불변. **다음 행동 하나:** 별도 예산 승인과 현재 A24 환경 gate를 결정한다.

## 2026-09-29 B2 잔차·AP 전이 PC 판독 완료 — 후보는 사후 진단, 기본 미채택

- [120초 센서 구간·AP 형태·후보 비교](ARRIVAL_RECORDED_B2_RESIDUAL_MODEL_PC_20260929.md), [작은 CSV/SVG](results/energy_ap_recorded_b2_01/residual_pc_v1/README.md). 원본/동결 SHA와 재현 수치 일치, 적분·시계·상태 매핑 결함 없음. 원래 에너지 +1.062J는 마지막 lane 해제까지 **+1.687J**, 이후 resident idle **−0.625J**가 상쇄. 실제 표본 구간 13개·12.285초가 혼합 상태라 1.683초 병행 W 독립 재추정 불가. 이전 그림의 120초 관측 끝점 누락은 새 누적 CSV/그림에서 표시하되 원본 분석은 보존했다.
- 시작 AP29.9°C는 동결식 초기 상태로 입력됐다. frozen idle 평형34.380°C로 올라가는 예측과 31.6→29.9°C로 내려가는 관측은 형태가 다르다. 사후 AP 후보 `energy-ap-start-referenced-idle-diagnostic-v1`은 B2 MAE3.555→0.182°C이나 개발3·이미 본 DC_DG·DIAG-04 모두 악화해 simulator 기본/strict에 등록하지 않았다. 저온 AP 독립 예측·정책 차이 판정 미완료, 동결·FAIL·원본·`experiment_ready=false` 보존. **다음 행동 하나:** 별도 승인 전 실행하지 않는 같은 프로토콜 저온 시작의 긴 유휴→짧은 CG_DC→유휴 독립 확인 한 조건을 검토한다.

## 2026-09-29 B2 numeric AP 관측 진단 v2 — 승인 1회 완료, 외삽 판독

- [plan_v6 단일세션 원본·소비·120초 판독](ARRIVAL_RECORDED_B2_AP_OBSERVE_RUN01_20260929.md)과 [공유 CSV/SVG](results/energy_ap_recorded_b2_01/diag_v6/README.md). 현재 A24·설치본·환경/품질 gate를 통과해 runtime4·warmup8·본 요청24/24를 마쳤다. 실제 CG_DC 병행 1.683초, 시작 AP **29.9°C**는 동결 개발 시작 범위 32.5–34.0°C 밖. 관측 154.696J, 동결식 외삽 계산 155.758J(+1.062J), AP MAE3.555°C·최고값 차이+2.770°C다. **자료 전체창 적격과 수치 계산은 완료했으나 strict 지원·독립 정확도 PASS·정책 우열은 미완료**다.
- plan_v6 SHA `38c9eb2f…00ced`는 소비·완료, 재실행하지 않는다. APK push/설치 각1, 설치본 pull1, 실행기 ADB812+사전 선택1, 경과285.594초, 회수58파일·앱 자체 cleanup·host force-stop/프로세스 부재 확인. 이전 종료 계획, 미소비 plan_v5 초안·queue24, 동결 모형·FAIL·원본·`experiment_ready=false` 보존. **다음 PC 작업 하나:** AP 외삽 잔차와 짧은 구간의 J 오차 상쇄를 기존 개발·확인 자료의 초기조건/상태별 잔차와 대조한다.

## 2026-09-29 B2 시작 AP 관측 진단 v2 — PC 준비 완료·실행 미승인

- [실행 gate와 모형 지원 분리·검증·계획](ARRIVAL_RECORDED_B2_AP_OBSERVE_PC_20260929.md). 32.5–34.0°C는 동결 개발 **시작 AP 관측 범위**이며 별도 안전 하한 근거가 없다. 기존 `numeric-ap-once-v1`은 유지하고 `numeric-ap-observe-v2`에서 기존 환경·품질 gate와 신선한 HAL AP를 요구하되 개발 범위 밖 값을 원자료로 관측할 수 있게 했다. 밖의 계산은 외삽 진단, 짧은 전환 strict 미지원·정확도 PASS 없음. plan_v4 AP28.8°C 중단은 당시 계약 결과 그대로다.
- 프로젝트 서명 APK SHA `747ce77e…43f6180`와 별도 plan_v6 SHA `38c9eb2f…00ced`를 외부 경로에 보존. 1세션·runtime4·warmup8·작업24·총32·staging7·APK push/설치 각≤1·ADB≤3,200·전체≤1,300초, 재시도0. Python13건/JVM 대상 테스트·서명 검사·PowerShell Check PASS/기기명령0. 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`; run/registry 미생성. plan_v5는 AP 경로 판독 보완 전의 미소비 초안이며 실행 대상이 아니다. 기존 동결·FAIL·원자료·queue24 미소비 계획·`experiment_ready=false` 유지. **다음 행동 하나:** 이 별도 단일세션 진단의 실행 여부를 현재 기기·환경 및 승인 예산으로 결정한다.

## 2026-09-29 새 lifecycle APK의 B2 기록 재생 — 시작 AP gate 중단

- [별도 plan_v4 실행·원본·gate 판독](ARRIVAL_RECORDED_B2_REPLAY_RUN02_20260929.md), [소형 소비 요약](results/energy_ap_recorded_b2_01/run02_summary.json), [통합 화면](results/arrival_policy_screen_01/dashboard.html). 새 계획 SHA `19ef883a…99a507` 1회 claim·실행, `stopped_no_resume`. 설치본 SHA `120ee894…1d50f5` 확인(이번 APK push·설치 각1). runtime4·warmup8 반환 뒤 시작 직전 HAL AP **28.8°C**가 고정 32.5–34.0°C 밖이라 arm 미발행; 본 요청 시작 기록0·120초 공식창 미진입·완료0/시도1. 실행기 ADB234+transport 선택1/3,200, 95.906/1,300초; host force-stop·프로세스 부재 확인, 앱 자체 cleanup 기록 없음. lifecycle은 `onCreate`만 있고 이번에는 `lifecycle_cancelled`가 아니다. J/AP 오차·실제 병행·정책 성능은 미산출. plan_v3·v4 모두 소비·종료, 동결 모형·strict 범위·기존 FAIL·queue24 미소비 계획·`experiment_ready=false` 유지. **다음 행동 하나:** 기존 사전 AP 기록으로 고정 시작 범위의 현재 비충전 환경 적용 가능성을 PC에서 판독한다(실측 자동 실행 아님).

## 2026-09-29 저장 B2 재생의 lifecycle·소유권 PC 판독 완료

- [시간축·소유권·수정·검증](ARRIVAL_RECORDED_B2_LIFECYCLE_PC_20260929.md). 앱 baseline 중 `onDestroy` 취소와 그 뒤의 host force-stop은 구분했다. 구 APK에 callback/instance 기록이 없어 `onDestroy` trigger(사용자 조작·재생성·시스템 처리 등)는 **미확정**이다. Activity가 worker/runtime/journal을 소유하고 `onDestroy`에서 안전 취소하는 현 계약은 유지한다. 두 번째 Activity의 기존 출력 덮어쓰기는 이미 root guard가 차단한다. 부족했던 lifecycle·finish 의도만 bounded journal에 추가했고 Robolectric callback 3건 및 관련 4건 PASS, 별도 프로젝트 서명 APK SHA `120ee894…1d50f5` 생성·검증(미설치)했다. 새 journal 비용은 미계측이므로 구 APK 자료와 동일 프로토콜로 합치지 않는다. 기기 명령0; plan_v3 `stopped_no_resume`, 동결 모형·FAIL·queue24 미소비 계획·`experiment_ready=false` 유지. **다음 행동 하나:** 별도 새 실행을 논의할 때 먼저 lifecycle 계측 APK와 계획 동일성·현재 기기 gate를 확인한다. 이번 PC 작업에서는 실측하지 않는다.

## 2026-09-29 저장 B2 짧은 전환 재생 — 1회 중단·재실행 금지

- [원본·구현·판독·예산](ARRIVAL_RECORDED_B2_REPLAY_PC_20260929.md), [공유 입력](results/energy_ap_recorded_b2_01/README.md), [통합 화면](results/arrival_policy_screen_01/dashboard.html). queue/seed201/B2_PC/실현 간섭1.5의 원본 24요청과 49개 점유 구간을 교차검사했다. 별도 `RECORDED_B2_REPLAY_V1`은 원본 backend/dispatch 허용 하한을 따르되 실제 추론·lane 해제를 연장하지 않는다. 동결식 적용은 실제 일정·시작 AP를 받는 **조건부 진단**이고 strict 임의 도착 지원·온라인 B2·정책 절감 판정이 아니다.
- [승인 1회 결과·원본·소비](ARRIVAL_RECORDED_B2_REPLAY_RUN01_20260929.md): plan_v3 SHA `52b0a21b…30d5c`는 `stopped_no_resume`. APK push/설치 각1·staging7·runtime4·warmup8 뒤 resident baseline 중 앱 `lifecycle_cancelled`; 본 요청 시작 기록0, 시작 AP gate·120초 공식창 미도달, 완료0/시도1. 실행기 ADB207+transport 선택1/3,200, 전체93.547/1,300초. 앱 실패 파일 회수 뒤 대상 host force-stop·프로세스 부재 확인. `summary.json` 누락이 원본 host receipt의 최상위 오류로 올라온 판독 경로를 PC에서 보완·8테스트 통과했으며 소모 계획을 다시 실행하지 않는다. J/AP 오차·실제 병행·정책 성능 미판정. 기존 queue24 미승인 계획·원본·동결 모형·FAIL·`experiment_ready=false` 유지. 뒤이은 PC 시간축 판독은 위 최신 항목을 따른다.

## 2026-09-29 저장된 정책 일정의 실측 모형 지원 경계 — PC 판정 완료

- [135개 일정의 지원·차단 구간과 최소 해결 명세](ARRIVAL_MEASURED_SUPPORT_BOUNDARY_20260929.md), [CSV/SVG와 통합 화면](results/arrival_policy_screen_01/dashboard.html). low/queue/burst × 실현 간섭1/1.5/2 × seed201–205 × CPU_URGENT/B2/B3의 저장 120초 일정 중 **실측 기반 J/AP 전체창 지원 0개**. 임의 짧은 전환이 동결 regimen 지원 밖이고 저장 초기 AP29°C는 미측정·개발 시작 범위 밖이다. burst/B3의 9사례는 분류 CPU＋분류 GPU 계수도 없다. 저장 PC 일정·응답과 가정 비용은 그대로, 미지원 J/AP는 계산하지 않았다.
- A24 동결 byte SHA `35ed6987…34c54`를 확인하고 기존 개발3·DC_DG 확인1·CG_DC 새 프로토콜 사후 진단을 보존했다. queue/seed201/실현1.5의 B2/B3/CPU는 상태 이름이 모두 있는 최소 결손 비교이나 짧은 전환·관측 시작 AP·독립 오차가 없어 정책 우열은 미판정. 현재 Android 도착 계획은 FIXED_SPLIT만 고정하므로 세 정책 직접 기기 재생은 아직 지원 확인이 없다. queue24/FIXED_SPLIT 계획은 **미승인·미소비 실행 보류**이고 FAIL·원본·종료 계획·`experiment_ready=false` 유지. **다음 행동 하나:** 대표 queue/201/1.5의 상태·전환을 실제 앱에서 고정 재생할 최소 PC 실행 경로와 예산을 검증한다(실측 자동 실행 아님). 이번 기기 명령0.

## 2026-09-29 에너지·AP 정책 실험 측정 필요성 감사 — PC 범위 확정

- [원본·모형·정책 지원 근거표와 종료 기준](ENERGY_AP_POLICY_MEASUREMENT_AUDIT_20260929.md). A24 개발3 동결 SHA `35ed6987…34c54`·DC_DG 확인1(+4.550J, AP MAE0.645°C)·새 프로토콜 CG_DC 사후 전이(+13.121J/매핑600.090초, AP 최고+1.612°C)·시작32.3°C의 짧은 CC_DG 범위 밖 결과를 구분했다. 고정 CC_DG 4세션은 에너지 차이 방향 실패. S26 공유 MobileNet 자료는 두 모델의 계수가 아니다.
- **판정:** 제한된 PC 응답/상충·명시적 가정 민감도 탐색은 지금 가능. 실측 기반 임의 도착 정책 우열은 최소 독립 확인이 필요하지만 세션/예산은 아직 근거 부족. queue24/FIXED_SPLIT은 좁은 A/B 진단용 **B**로서 핵심 병행 비용의 필수 선행은 아니며 이번 실행 **보류**. `energy_ap_arrival_confirm_plan_v1`은 기존 SHA·미승인·미소비 그대로, 실행 실패/`stopped_no_resume` 아님. 새 계획·claim·기기 명령0, 동결 계수·FAIL·원자료·`experiment_ready=false` 유지. **다음 행동 하나:** 기존 B2/B3/CPU 결과의 지원 마스크와 가정 경계를 사용한 제한 PC 정책 비교를 시작한다.

## 2026-09-29 시작 AP 단일세션 PC 준비 완료 — 미승인·기기 미검증

- [실행/판독 경계·정확한 예산](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md), [24요청·분석 계약](results/energy_ap_arrival_confirmation_01/README.md). `numeric-ap-once-v1` 프로젝트 서명 APK SHA `d2af6d0a…ea771`, 별도 계획 `ENERGY-AP-ARRIVAL-CONFIRM-01` SHA `5dfc940d…a641c`, 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`; Check 기기명령0·출력/registry 미생성. 1세션·runtime4·warmup8·작업24·총 추론32, stage7파일, push/설치 최대 각1, ADB3,000, 총1,300초, 재시도0. 실제 설치본·환경·센서 내부 AP 갱신·실행은 아직 미확인이다.
- 이 입력은 queue24/FIXED_SPLIT/120초의 A(관측 일정 조건부 에너지/AP)와 B(예정 도착 종단간 일정/응답/비용)를 **별도** 판독하기 위한 것이다. PC 예상 병행0초, frozen strict 임의 전환 unsupported라 병행 비용·동적 열 피드백·정책 우열 검증 완료가 아니다. 개발 동결 SHA `35ed6987…34c54`, 과거32.3°C 범위 밖/FAIL/원본과 `experiment_ready=false` 유지. **다음 행동:** 별도 승인 전제의 현재 A24·설치본·환경 확인 후 이 한 세션을 실행할지 판단; 이번 턴 기기명령0.

## 2026-09-29 시작 직전 numeric AP opt-in 구현·PC 검증

- [후속 구현·계측 경계·완료 정의](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md): `numeric-ap-once-v1`은 baseline 뒤 AP를 한 번 확인하고 앱이 실제 common origin에서32.5–34.0°C·읽기 시작부터3초 이내를 재검사한다.30초 대기 만료/결측/범위 밖/전달 지연이면 본 작업0, 자동 대기 반복·재시도 없음. host 조회 최대5명령이 시작 전에 추가되며 부하 중 새 handshake는 없다.
- host 실제 poll 포함3테스트·Android gate/기존24요청 계약4테스트 및 Kotlin 컴파일 통과. 기기명령0; APK 패키징·설치·새 실행계획/claim 없음. 확인 목적은 이번24요청의 A조건부/B종단간 오차이며 병행 계수·개별요청 J·임의 부하 전체 검증이 아니다. 기존 동결값·FAIL·`experiment_ready=false` 유지. 다음은 수정 소스의 서명 APK와 단일세션 계획 준비다.

## 2026-09-29 최소 도착 확인 입력·시작 AP gate PC 판정

- [고정 입력·센서 해상도·차단 근거](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md), [공유 입력/Check](results/energy_ap_arrival_confirmation_01/README.md). queue 24요청/FIXED_SPLIT/공통120초를 결과 선택 없이 고정했다. 단기 전환 공통창 전류 중앙 간격1.000초·AP2.630초, 요청 lane 점유 중앙0.163초; 기존 PC 일정의 병행 점유0초이므로 개별/병행 비용 검증 입력으로 확대하지 않는다.
- 동결 시작 AP 개발 범위는 **32.5–34.0°C**(전체 경로 범위32.5–39.5°C와 별개). 직전 32.3°C는 unsupported, +23.280J는 매핑 구간의 범위 밖 탐색 외삽이다. 사후 AP 판독 코드를 검증했으나 기존 앱은 실제 load 시작 numeric AP를 읽거나 차단하지 못한다. `Check`는 `PC_INPUT_FIXED_RUN_BLOCKED`/기기명령0을 반환, Run/registry/실측 예산 없음. 다음은 **실제 시작 경계의 AP 차단 가능성을 PC에서 해결하고 계측·APK 영향 검증 후 별도 계획 발행**. 동결값·원본·FAIL·`experiment_ready=false` 유지.

## 2026-09-29 CC_DG 짧은 전환 진단 1회 완료 — 동결 예측은 범위 밖

- [실행·지원 판정](ENERGY_AP_SHORT_TRANSITION_DIAG01_20260929.md), [별도 오프라인 대시보드](results/energy_ap_short_transition_01/dashboard.html). 새 opt-in 36블록 단일 세션을 PC 검증 후 한 번 실행했다. 앱 정상 완료·회수·host 정리 확인; 작업1,039·적격성4·warmup8, 총1,051/1,692명시 추론, ADB3,634/11,000, 전체1,129.172/2,700초. 6개 병행 블록의 실제 공동 lane 점유는 각각12.908~13.352초였다. 기존 계획·원본·동결값은 보존한다.
- 관측 공통창600.094초·903.842J, AP 시작32.3/최고36.6°C. **시작 AP가 개발 동결 모형의 관측 하한32.5°C 밖**이라 확인 예측 오차는 미산출/unsupported다. 동결식에 실제 블록을 대입한 +23.280J와 AP 경로 차이는 범위 밖 탐색 외삽으로만 표시했다. 동결 모형 SHA `35ed6987…34c54` 불변, 후보 재적합 없음. 임의 도착 strict는 계속 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`; CG_DC·CC_DG 정식 동일 프로토콜 확인 미완료, `experiment_ready=false`.
- **다음 행동 하나:** 이번 자료의 상태 시간 척도와 센서 분해능을 바탕으로 정책 선택에 필요한 최소 도착/전환 확인 입력을 PC에서 고정한다. 이번 0.2°C 범위 이탈을 이유로 즉석 재측정하거나 기존 6/12세션을 반복하지 않는다.

## 2026-09-29 짧은 도착 입력의 계측 가능성 PC 감사

- [전이 보고서의 후속 감사](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md)와 [대시보드·CSV/SVG](results/energy_ap_transition_01/README.md). 기존 queue/seed201/strict 24요청 PC 일정에서 CPU_URGENT·FIXED_SPLIT의 lane/inference 구간을 추출했다. FIXED_SPLIT의 분류 CPU＋탐지 GPU 동시 점유는 **이 일정에서 0초**이며 각 단독 연속 구간 최대 1.145초다. 1초 전류·약2.65초 AP로 병행 계수/짧은 잔열을 식별할 수 있는 입력이 아니다. Android 실측 결과가 아닌 PC 상태 길이 감사다.
- 옛 12세션 arrival 계획의 `Check`는 현재 소스 해시 변경으로 실패하며, host `warmup.arm`·AP 조회를 요구하는 기존 경로를 새 lifecycle APK 확인에 곧바로 사용할 수 없다. 따라서 새 수집 계획은 **미준비·미승인·미소비**, 정확한 예산/Check 없음. 동결 모형·기존 오차·도착 unsupported·CG_DC/CC_DG 정식 미완료·`experiment_ready=false` 유지. 이번에는 단일 입력 감사 테스트3건 통과·기기 명령0.
- **다음 행동 하나:** opt-in 단일 세션의 짧은 단독↔실제 병행↔유휴 전환을 재생·기록하고 실제 센서 coverage로 적격성을 가르는 PC 실행 경로를 구현·검증한 뒤에만 새 예산을 산정한다. 기존 6/12세션을 자동 재사용하지 않는다.

## 2026-09-29 A24 상태 모형의 새 APK 전이 오차 PC 판독

- [동결 계보·오차·지원 판정](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md), [오프라인 대시보드](results/energy_ap_transition_01/dashboard.html). 개발3세션 동결 SHA `35ed6987…34c54`를 변경 없이 DIAG-04 CG_DC 실제600초 블록 일정에 적용했다. 매핑600.090초의 관측953.055J·예측966.176J, **+13.121J (+1.377%)**. AP 경로 MAE0.834°C·최대2.278°C, 최고 예측39.212/관측37.600°C. pair 구간 +8.320J·AP MAE1.777°C 등 잔차 부호가 섞인다. 전체 공통창600.098초 가운데 상태 미매핑0.008초를 0으로 채우지 않았다.
- 실제 상태·전환 시각과 관측 초기 AP를 입력한 **사후 프로토콜 전이 1세션 진단**이다. 별도 후보 적합 없음, 기존 동일 조건 확인·임의 도착 종단간 예측·정책 선택 PASS 아님. 도착 엔진에 동결 profile을 전달하면 unsupported/null을 반환한다. 기존 개발3·DC_DG 확인, CG_DC/CC_DG 정식 미완료, 원본·FAIL·동결값·`experiment_ready=false` 유지. 그때 남긴 단일 도착 입력 감사는 위 후속 절에서 완료했다. 기기 명령0.

## 2026-09-29 DEVICE-SEGMENT-DIAG-04 새 lifecycle APK 승인 실행

- [실행 결과·원본·재현](ENERGY_AP_DEVICE_SEGMENT_DIAG04_RESULTS_20260929.md): CG_DC 진단1세션 정상 완료. 새 프로젝트 서명 APK 설치1, runtime4·warmup8·적격성4·작업1,073·총추론1,085, ADB3,345, 전체1,148.453초. 앱 cleanup·finish 요청·자료 회수·세션 host cleanup1회 및 프로세스 부재 확인. 연결 소실/timeout0, 과거 종료 원인 해결·단절 내성 증명 아님.
- 공통600.098초 기기 전체953.069J, AP 시작32.6/최고37.6°C. lane 공동 점유120.037초와 host invocation 겹침9.062초를 구분. raw=mA 조건부·절대 정확도 미인증. 기존 개발3·동결 모형·DC_DG 유지, CG_DC/CC_DG 정식 확인 미완료, `experiment_ready=false`. 다음은 추가 실측 없이 기존 동결 모형의 새 프로토콜 적용 범위와 전이 오차를 PC에서 확인하는 일이다.

## 2026-09-29 DEVICE-SEGMENT-DIAG-03 lifecycle·중복 host cleanup PC 조사

- [시간축·원인 경계·수정·검증](ENERGY_AP_DEVICE_SEGMENT_LIFECYCLE_PC_20260929.md). 원본의 앱 `lifecycle_cancelled`는 `onDestroy()` 경로이나 파괴 trigger는 미확정이다. 앱 terminal/회수/첫 host force-stop 뒤 PC 요약 거절이 예외 처리에서 두 번째 cleanup을 호출한 것은 코드 결함으로 확인해 단일 시도로 수정했다. 앱 Activity lifecycle·finish 사유 기록을 새 소스에 추가했지만 기존 설치 APK에는 없다. 사용자 관측 “무선 디버깅” 스위치 OFF→ON은 시각·주체 미확정의 별도 사실이며 ADB 명령 실패0과 동일시하거나 `onDestroy` 원인으로 확정하지 않는다. 실행 경로에서 무선 디버깅 설정 변경 코드는 발견되지 않았다.
- PC host 진입 7건·Android Kotlin 컴파일에 이어, 권한 조정 후 Robolectric lifecycle callback **2건 실행·PASS** 및 동일 프로젝트 인증서의 modelProbe APK 빌드·서명 검증 완료. 새 APK SHA-256 `933d202e…d831f7`, 기존 APK와 signer·패키지·버전 일치; 기기 전송·설치·실행 0. 이전 Git index/NDK/네트워크 제한은 해소됐고 실제 원격 브랜치 HEAD를 확인했다. 기존 DIAG-03 `stopped_no_resume`, 개발3·동결 모형·DC_DG 확인, CG_DC/CC_DG 미완료, 원본·FAIL·`experiment_ready=false` 유지. **다음 행동:** 별도 기기 승인과 현재 gate가 있을 때 새 APK로 제한된 lifecycle 관찰 필요성을 결정한다. 기존 진단이나 6세션 수집을 자동 재실행하지 않는다.

## 2026-09-28 DEVICE-SEGMENT-DIAG-03 중단 — 준비 중 앱 lifecycle 취소

- [진단 결과·소비·원본 경계](ENERGY_AP_DEVICE_SEGMENT_DIAG03_RESULTS_20260928.md), [작은 요약](results/energy_ap_device_segment_01/diag03_summary.json). plan SHA `5ec12e31…ca09068`을 `Check` 후 1회 실행. 새 APK 전송·설치 각1 및 현재 A24/환경 gate 통과. CG_DC 1시도·0완료; runtime4·warmup8·적격성4, **본 작업0/1,680**, 공식 baseline·냉각 없음. resident AP 준비 중 앱 `onDestroy` 경로의 `lifecycle_cancelled` 실패; 외부 trigger 미확정. ADB 연결 소실·timeout 0, host AP46표본, 앱 표본119개. host 회수14파일·force-stop 후 프로세스 부재 확인, 실패 후 cleanup 중복 호출 기록. ADB513/11,000, 전체193.094/2,700초, 조건부 사후 회수0. registry `stopped_no_resume`, 재실행 금지.
- 기존 개발3·동결 모형·DC_DG 확인, CG_DC/CC_DG 미완료·FAIL·원본·`experiment_ready=false` 유지. numeric AP의 진행 중 별도 온도 중단 한도는 없지만 AP 경로 결측은 분석 부적격이며 이번에는 baseline/부하가 없어 전이 예측 오차도 없다. **다음 행동:** 추가 실측 없이 `onDestroy` 발생 경계와 host 후속 cleanup 중복 호출을 PC에서 조사한다.

## 2026-09-28 세션 내부 ADB 의존성 축소 — 진단 전용 PC 준비

- [구현·계측 차이·후속 한도](ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md), [계획·재현 안내](results/energy_ap_device_segment_01/README.md). 기존 CONFIRM-06의 `baseline.arm` 미전달과 앱 gate 종료를 구분했다. 연결 소실의 내부 원인은 미확정이다. 별도 `device-after-probe-diagnostic-v1`은 host가 runtime/warmup/품질·AP 준비를 승인한 뒤 앱이 baseline→부하→냉각을 한 세션 안에서 진행한다. 기존 정식 모드·동결 계수·원본은 그대로다.
- 새 APK SHA `7589b96f…2e9c00d`, 별도 DIAG-03 plan SHA `5ec12e31…ca09068`은 프로젝트 서명 빌드·PC 경계 테스트·`Check` 통과. **미승인·미소비, 기기 명령/설치/추론 0회**. 앱 자체 종료와 host 상태 미확인을 분리하고, 원 host 종료 확인 뒤 같은 session ID terminal 자료만 읽는 제한 회수 경로를 준비했다. host AP 결측/계측 부하 변경 때문에 기존 동결 모형의 동일 조건 확인으로 취급하지 않는다. `experiment_ready=false`.
- **다음 행동:** 별도 승인 전에는 실기기 실행 없음. 준비된 한 세션 진단의 기기 gate와 앱 정상 종료·관측 범위를 확인할지 결정한다. 종료된 CONFIRM-06과 미완료 CG_DC/CC_DG를 재개하지 않는다.

## 2026-09-28 CONFIRM-06 재연결 뒤 잔류 프로세스·transport 경계 확인

- [읽기 전용 확인과 PC 진단](ENERGY_AP_CONFIRM06_TRANSPORT_PC_20260928.md): 현재 동일 A24는 재연결된 IP endpoint 한 건으로 확인. 앱 PID는 있으나 Android 분류 `cached=true, empty=true`, 해당 수집 Activity 없음, 세션 journal 500행/마지막 `app_cleanup`은 회수본과 동일. 이전 실험이 계속 작업 중이라는 증거는 없지만 다른 작업 부재는 보장할 수 없어 force-stop하지 않았다. 이번 추가 ADB 읽기 전용 9명령, 새 추론·실측 0.
- 원 실행은 mDNS `transport_id:89`에 고정됐고 slot0608 `error: closed` 뒤 선택 경로가 `device not found`; 복구 뒤 `transport_id:91`은 같은 A24의 다른 endpoint다. 실패 순간 두 번째 경로 상태와 `closed`의 내부 원인은 미확인. host의 실시간 AP/poll/gate arm 의존 때문에 `baseline.arm` 부재 후 앱 gate가 종료됐다. 개발3·동결값·DC_DG는 유지, CG_DC/CC_DG 미완료, `stopped_no_resume`, `experiment_ready=false`.
- 같은 시각 host 원본에는 ADB server PID 일부만 남고 server 진단 로그/Windows 앱 오류 기록은 발견되지 않아 `closed` 내부 위치와 두 번째 경로의 당시 상태는 미확인이다. **03:34 UTC 사용자 승인 종료:** 현재 동일 A24·정확한 패키지를 재확인한 뒤 대상 앱만 force-stop 1회, 패키지 본체와 `:model_probe` 프로세스 부재 확인. 별도 읽기/종료/확인 ADB 9명령, 재측정0. [receipt와 구분](ENERGY_AP_CONFIRM06_TRANSPORT_PC_20260928.md). 다음 행동은 새 실측이 아닌 연결 소실 시 host arm/관측 의존의 설계 검토다.

## 2026-09-28 CONFIRM-06 중단 — ADB transport 소실, 새 확인 결과 없음

- [실행·회수·미확인 범위](ENERGY_AP_CONFIRM06_RESULTS_20260928.md), [작은 요약](results/energy_ap_state_confirm06/summary.json). 별도 계획 SHA `d13e1612…89301` Check 후 현재 온라인 동일 A24/설치본·환경 gate를 통과해 `Run` 1회. 첫 `CG_DC`에서 resident 준비·baseline 일부 후 slot0608 `exec-out cat /proc/uptime`가 `error: closed`/exit -1; 후속 transport `device not found`. **1시도·0완료/2**, `CC_DG` 미시도, `stopped_no_resume`, 재시도0.
- 원 실행 ADB615/21,000·308.484/4,500초, staging1/7파일·host pull1, APK push/설치0. 최초 단일 회수는 온라인 기기0대로 1명령 후 종료. 사용자 연결 복구 후 동일 A24에서 목록1＋기록형17=18개 읽기 전용 명령으로 원본14파일 회수(전체 기기 명령634): runtime4·warmup8·적격성4 반환, **본 작업0**. 앱은 `baseline_gate` 시간 상한 실패와 실패 cleanup을 기록했다. host parent/child 종료, host force-stop 실패·앱 프로세스 존재; 다른 세션 소유권 미확인으로 재강제종료하지 않았다. 동결 SHA·기존 DC_DG 결과 보존, 새 에너지/AP 오차 계산 불가, `experiment_ready=false`.
- **다음 행동:** 원본 ADB client·server/transport 기록으로 연결 소실 경계를 PC에서 진단한다. 앱 `baseline_gate`는 host가 arm하지 못한 뒤 60초 상한에 도달한 것으로 확인. 종료된 수집·단일 회수 claim을 재호출하지 않는다.

## 2026-09-28 CONFIRM-06 승인 후 착수 보류 — 우선 A24 transport offline

- [계획 Check·현재 연결·소비 경계](ENERGY_AP_CONFIRM_FOLLOWUP_PREFLIGHT_20260928.md). 승인 계획 SHA 일치·Check 통과, 실행 출력/registry 없음. `adb devices -l` 1회에서 지정된 `10.80.3.177:45677`이 offline, 온라인 0대여서 fingerprint·설치본·환경 gate 미확인. `Run`·세션·추론·설치/전송 0회, cleanup 해당 없음. 동결 모형·기존 DC_DG·COLLECT-05 `stopped_no_resume`·`experiment_ready=false` 유지.
- **다음 행동:** 우선 transport가 온라인인 시점에 현재 동일 A24를 확인한다. 두 transport가 온라인이면 현재 실행기의 단일 온라인 기기 선택 계약과 사용자 우선 지정의 차이를 해소하기 전에는 소비 claim을 만들지 않는다.

## 2026-09-28 COLLECT-05 ADB timeout PC 감사·별도 확인2 준비 — 기기 미실행

- [원인 경계·ADB 용도/지연·동결 확인 계약](ENERGY_AP_CONFIRM_FOLLOWUP_PC_20260928.md). slot14385 `run-as ls`는 server 사전검사 통과 뒤 client 3.000초 timeout; 직전 동일 조회0.109초·이후 회수 명령 반환. 14,394명령 중 listing8,528·timeout1·인접 client overlap0. 내부 지연 원인 미확정. poll/timeout·센서·APK 변경0, 기존 동결 계수/원본·COLLECT-05 `stopped_no_resume` 보존.
- `ENERGY-AP-STATE-CONFIRM-06`은 확인 `CG_DC→CC_DG` **2세션만** 별도 미승인·미소비 PC 준비. 동결 SHA `35ed6987...034c54`를 재보정 없이 로드하는 경로/manifest/Check 통과, 기기 명령0. 외부 plan SHA `d13e1612...89301`, 추론 최대3,384·전체75분·ADB21,000/cleanup 전20,900, APK push/설치0. 새 output/registry claim 없음. 기존 확인 DC_DG +4.550J/+0.474%·AP MAE0.645°C는 독립1세션 한계 유지. `experiment_ready=false`.
- **다음 행동:** 별도 실기기 승인 전 현재 A24/설치본/환경 gate를 적용할 수 있는 날 이 신규 2조건 계획의 실행 여부를 판단한다. 이번에는 실행하지 않는다.

## 2026-09-28 ENERGY-AP-STATE-COLLECT-05 종료 — 개발3 동결·확인1 후 ADB 조회 timeout

- [정식 실행 결과·원본/부분 그림](ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md), [공유 요약](results/energy_ap_state_collect05/README.md). 새 plan_v5 SHA `4616c2ea...cd1d`를 Check한 뒤 동일 A24·설치본/환경 gate를 통과해 한 번 실행했다. 개발3 적격 완료→계수 동결→확인 DC_DG 1 적격 완료. 다음 CG_DC 준비 중 `run-as ls` 3초 timeout으로 **5시도·4완료/6**, 마지막 확인 미시도; `stopped_no_resume`, 재시도0.
- 작업 lane 해제 확인3,174, 적격성16·warmup40 반환, runtime20·staging5/35파일, ADB14,394/62,500, 설치본 pull1, push/설치0, 전체4,342.422/13,500초. 중단 세션의 회수 prefix 이후 호출은 확정0으로 두지 않는다. host force-stop과 프로세스 부재 확인; 앱 cleanup은 중단 세션에서 미확인이다.
- 동결 상태별 기기 전체 전력/AP 모형은 부분 자료로 보존한다. 유일한 확인 DC_DG는 조건부 공통창 에너지 오차 +4.550J, AP 경로 MAE 0.645°C·최대 1.531°C. CG_DC/CC_DG 확인과 조건 간 방향·임의 도착 적용은 미검증. 전류 절대 정확도 미인증, 기존 FAIL/동결값/원자료/종료 계획 및 `experiment_ready=false` 유지. **다음 행동:** 이번 `run-as ls` timeout의 host client 기록과 앞선 정상 조회를 PC에서 대조해 반복 위험을 좁힌다. 이 계획은 재개하지 않는다.

## 2026-09-28 ENERGY-AP-HOST-DIAG-01 완료 — 통제된 host 종료·회수 확인

- [실행 결과·증거 경계](ENERGY_AP_HOST_DIAG_RESULTS_20260928.md), [작은 요약](results/energy_ap_host_diag_01/summary.json). 승인 plan_v7 SHA `a6c65b0d...b20decf`를 현재 동일 A24/설치본/환경 gate 확인 후 한 번 실행했다. runtime4·warmup8·적격성4 전부 반환, resident 관측120.275초·AP 43표본 후 `probe` arm 없이 host 통제 종료. 공식 baseline/load0, 추가 실행0.
- ADB359/3,000, host pull1, staging1/7파일, APK push/설치0, Python254.843/1,500초(전체 진입 약256.243초). parent/child 시작·종료 기록, `poll_alive` 4회, host force-stop·앱 프로세스 부재, archive12파일/완전한 progress311기록 확인. 앱 `cleanup.json`은 없어 **앱 자체 cleanup 미확인**. COLLECT-04 우발 종료 원인·장시간 안정성·에너지/AP 예측은 미검증. 출력/registry는 소비되어 `stopped_no_resume`; 기존 종료 계획·FAIL·원자료·동결값 및 `experiment_ready=false` 유지.
- **다음 행동:** 이번 host 경로를 유지하는 새 정식 수집 계획을 별도 PC 준비·검증한다. 실측 자동 실행은 하지 않는다.

## 2026-09-28 HOST-DIAG-01 실행 전 3,000명령·동일 APK 범위 재검토 — 미실행

- [실행 코드 산식·소유권·판독 범위](ENERGY_AP_HOST_LIFECYCLE_PC_20260928.md): plan_v7 정상 예시는 과거 준비 전 약 84초와 resident 120초를 조건부 합쳐 **약 650 ADB명령**이며 정상 평균은 미측정. 900초 poll 최악 보수 상계는 **2,530/3,000명령**, cleanup 전 **2,523/2,900명령**이다. 기존 0.25초 `ls` 대기는 진단에서 1초이며 필수 상태 조회의 중복은 발견되지 않아 코드·계획 해시는 그대로다.
- 동일 APK로 준비 중 host 지속·기록, 소유자 요청 force-stop, 부분/전체 회수와 앱 프로세스 부재를 판독할 수 있다. 앱 자체 정상 종료·cleanup과 COLLECT-04 우발 종료 원인은 확인할 수 없다. 원 실행기의 통제 종료는 활성 host를 막는 **외부 orphan 복구기**와 별개다. 관련 PC 3건과 plan_v7 `Check` 통과, 기기 명령·추론 0. 계획/registry 미소비, 기기 gate 미검증, `experiment_ready=false` 유지.
- **다음 행동:** 별도 실행 승인 시 현재 A24·설치본·환경 gate 확인 후 이 한정된 진단 1회만 실행한다. 이번 검토에서는 실행하지 않는다.

## 2026-09-28 host 종료 소유권·단일 복구 PC 연결 — 최소 진단 미승인

- [구현·PC 장애 주입·진단 계약](ENERGY_AP_HOST_LIFECYCLE_PC_20260928.md): 향후 PowerShell/Python 실행 ID와 parent/child 생성시각·명령 신원을 묶고, 활성/미확인 host에는 기기 복구를 차단한다. 별도 단일 claim 복구는 작은 증거→host cleanup 예약→archive 순서이며 원래 오류와 후속 오류를 분리한다. COLLECT-04 실제 종료 원인은 미확정, 기존 `stopped_no_resume`·원본·FAIL·동결값 보존.
- 동일 APK의 준비 단계 1세션 진단 plan_v7 SHA `a6c65b0d...b20decf`, runtime4/warmup8/적격성4·추론 최대12·전체25분/ADB3,000 상한을 PC Check했다. **미승인·미소비·기기 미검증**이며 공식 baseline/부하 0. 현재 APK는 준비 전 앱 정상 종료가 불가해 host 요청 stop/회수까지만 확인 가능하다. PC 관련 27건 중 26 통과·1 옛 fixture 건너뜀, ADB/설치/추론0. `experiment_ready=false`.
- **다음 행동:** 별도 승인 시 현재 A24/설치본/환경 gate를 확인하고 이 진단 1회만 실행하여 host 종료·회수·cleanup을 판독한다. 앱 자체 정상 완료를 요구하면 진단 전용 APK/설치가 별도 필요하다.

## 2026-09-28 COLLECT-04 host 종료 PC 진단·기록 경로 수정

- [계층별 사실·재현 결함·PC 검증](ENERGY_AP_HOST_TERMINATION_PC_20260928.md). 마지막 원본 ADB client는 정상 반환했으나 Python/PowerShell 종료 이유는 원본 PID·exit/stderr 부재로 미확정. 별도 PC 주입에서 실패 처리의 2차 progress 파싱 오류가 원래 예외와 종료 receipt를 잃게 하는 결함을 재현했다. 향후 host checkpoint·원래 stack·독립 회수/cleanup 오류·receipt fallback 및 PowerShell child exit/stdout/stderr 기록을 보완했다. Android/APK·gate·호출 상한 변경 없음.
- `COLLECT-04`와 원본·소비 registry는 그대로 `stopped_no_resume`, 완료0/6·동결/확인 없음. 기기 없는 140.516초 child 정상 종료와 parent 단독 종료 뒤 bounded child 생존을 PC에서 관측했으나 과거 종료 원인은 미확정. 이번 기기 명령0, `experiment_ready=false` 유지. **다음 행동 1개:** 새 기기 실행 전에 host 소유권 종료·orphan 감지·수동 회수 절차의 PC 계약을 확정한다. 자동 재수집 없음.

## 2026-09-28 ENERGY-AP-STATE-COLLECT-04 중단 — 첫 개발 세션 온도 준비 단계

- [결과·소비·증거 경계](ENERGY_AP_STATE_COLLECT04_RESULTS_20260928.md), [작은 요약](results/energy_ap_state_collect04/summary.json). 설치 검증 APK를 재사용하는 별도 plan_v4 SHA `cc8f8cfd...7054f7`를 PC 검증·Check 후 1회 실행했다. 현재 A24/설치본 SHA/환경 gate 통과, APK push·설치0, host pull1. 첫 개발 `CC_DG` 세션은 runtime4·warmup8·적격성4까지 확인됐으나 공식 baseline/부하 이전 온도 준비에서 host가 정상 종료 receipt 없이 끝났다. 세션 1시도·0완료, 개발 동결/확인/예측 오차 없음. 나머지5 미시도; 새 계획 `stopped_no_resume`.
- 앱 journal·부분 원본은 별도 회수했고 host force-stop/프로세스 부재 확인. 앱 내부 cleanup은 미확인. 원인 미확정이며 기존 원본·FAIL·동결값·종료 계획과 `experiment_ready=false` 유지. **다음 행동 1개:** host 정상 종료 receipt 부재와 실패 시 회수/cleanup 경계를 PC에서 진단한다. 동일 계획 재개·새 실측 자동 실행 금지.

## 2026-09-28 ENERGY-AP-INSTALL-ONLY-02 완료 — 원격 APK 재사용 설치

- [새 계획·PC 검증·실기기 설치 결과](ENERGY_AP_INSTALL_ONLY_02_RESULTS_20260928.md). 새 ID/plan SHA `1176c4d94aa263feddcf9e4690a1ead79cd3c30e34cd3c61327a5840704e761b`를 Check 후 1회 실행. 현재 동일 A24·환경 gate, 원격 APK와 설치 후 base APK의 SHA `b273f74…114cf` 일치. 기존 설치본 해시가 달라 `pm install -r` 1회 성공. 실제 ADB19/22·pull1/1·push0·설치1/1·앱/추론/실측0, 전체45.687/600초. host·종료 확인 완료; 원본 외부 `energy_ap_install_only_run_v2/receipt.json` 및 별도 complete registry 보존.
- 수정 최초 조회 경로의 실제 `run→preflight→identify` PC fixture 포함 테스트 6건 통과. 설치는 GPU·센서·병행·모형 검증이 아니다. 다음 행동: 종료된 COLLECT-03은 재개하지 않고, 별도 수집 계획과 승인·현재 기기/앱 적격성 gate를 준비한다. 기존 FAIL·원자료·동결값과 `experiment_ready=false` 유지.

## 2026-09-27 ENERGY-AP-INSTALL-ONLY-01 중단 — 기기 명령 전 host 오류

- [설치 전용 계획·실제 소비·수정 범위](ENERGY_AP_INSTALL_ONLY_RESULTS_20260927.md). 관측된 원격 APK를 재전송 없이 설치하는 별도 plan SHA `f76c4ef3e44bc256944650330ca0e8f4297071a6dac1d99a923de4a838139fba`를 PC 준비·Check 후 한 번 실행했다. 0.016초에 첫 `devices -l` 기록 래퍼가 미선택 serial `None`으로 `TypeError`를 내고 프로세스 생성 전 종료. claim/registry 소비, 실제 ADB client·기기 조회·pull·원격 SHA·설치·앱·추론 0. 앱 cleanup은 기기 미식별로 해당 없음. 원본 외부 `energy_ap_install_only_run_v1/receipt.json`, 상태 `stopped_no_resume`.
- 원인 코드 수정 후 현재 transport 최초 조회의 `-s` 생략과 이후 선택된 serial 사용을 PC fixture로 검증했다(관련 5건 통과). 소비 계획의 소스 동일성이 달라져 재실행하지 않았다. 다음 행동: **새 ID의 설치 전용 계획만** 별도 PC 동결·승인 후 현재 A24·원격 SHA를 확인한다. 기존 COLLECT-03·복구 종료 계획과 FAIL·원자료·동결값·`experiment_ready=false` 유지.

## 2026-09-27 ENERGY-AP-PUSH-OBSERVE-01 완료 — 이번 원격 파일 SHA 일치

- [관측용 push 결과·소비·원본 경계](ENERGY_AP_PUSH_OBSERVE_RESULTS_20260927.md). 사용자가 설치본·추가 환경 gate 요구를 이번 전송 진단에서 철회하여 기존 plan SHA `423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a`를 수정 없이 실행했다. 현재 동일 A24·새 원격 대상 부재·공간 gate 통과. 9/17 ADB명령, push 1/1 정상 반환 13.469초, 전체 14.422/420초. 첫 20초 전에 완료돼 중간 크기 조회 0/8; 최종 106,092,116 byte·SHA `b273f74...a114cf` 일치. 설치·앱·warmup·추론·재시도 0. 외부 `energy_ap_push_observed_run_v1/receipt.json`과 claim 보존.
- 이번 원격 파일은 재전송 없이 별도 설치 단계의 후보로 사용할 수 있다. 과거 두 timeout 원인은 미확정이며 전송 안정성·기기 정책/모형 적격성을 주장하지 않는다. 다음 행동: 별도 설치 전용 계획에서 현재 원격 SHA·설치본 동일성을 확인한다. 기존 stopped 계획·FAIL·원자료·동결값·`experiment_ready=false` 유지.

## 2026-09-27 ENERGY-AP-PUSH-OBSERVE-01 승인 후 실행 전 보류

- [PC preflight와 차단 근거](ENERGY_AP_PUSH_OBSERVE_PREFLIGHT_20260927.md). 승인된 관측 계획 SHA `423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a`의 `Check`는 통과했고 출력·소비 claim은 없다. 그러나 이번 지시의 현재 설치본 확인·환경 gate와 생략 규칙이 동결된 6명령 preflight/코드에 없다. 별도 조회 뒤 실행하면 최대 17명령 상한을 넘을 수 있어 기기 명령 전 중단했다. 이번 ADB·push·pull·설치·추론 0, 현재 기기 상태 미확인. 외부 `energy_ap_push_observed_preflight_v1/PREFLIGHT_RECEIPT.json` 보존.
- 다음 행동: 설치본·환경 gate와 생략을 포함한 별도 계획을 PC에서 동결·예산 검증한 뒤 승인 범위를 다시 정한다. 기존 계획은 미소비·미실행이며 COLLECT-03 등 종료 계획, FAIL·원자료·`experiment_ready=false`를 유지한다.

## 2026-09-27 ENERGY-AP-PUSH-DIAGNOSIS-01 완료 — 재전송 없이 원격 상태 확인

- [두 timeout·읽기 전용 조회·후속 후보](ENERGY_AP_PUSH_DIAGNOSIS_20260927.md). 착수 HEAD `d99ad84` clean/upstream 동일. 두 120초 push의 동시 진행 기록은 없어 원인 미확정이다. 현재 동일 A24에서 두 정확한 원격 경로는 모두 파일 부재였다(읽기 전용 7/9명령·0.891초). 이 사실은 과거 0바이트 전송이나 무선 결함의 증거가 아니다. 새 push/pull/install/앱/추론 0회.
- 별도 `ENERGY-AP-PUSH-OBSERVE-01`은 크기 관측+최종 SHA 경계의 PC 후보로 준비했다. 외부 계획 SHA `423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a`, 최대 17 ADB명령·push 1/180초·전체 420초, 설치/재시도 0. **미승인·기기 미검증·미소비**이며 기존 stopped 계획을 재개하지 않는다. 관련 PC 테스트 8건과 새 계획 `check` 통과. 기존 FAIL·원자료·동결값·`experiment_ready=false` 유지.
- 다음 행동: 별도 승인 시에만 현재 A24/파일/환경을 새로 확인하고 관측용 전송 진단 1회를 실행한다. 그 결과 전에는 수집을 재개하지 않는다.

## 2026-09-27 ENERGY-AP-DEPLOY-RECOVERY-01 종료 — 무선 push timeout

- [단일 실행 결과·원본 경계](ENERGY_AP_DEPLOY_RECOVERY_RESULTS_20260927.md). 승인된 별도 600초 계획을 현재 동일 A24·비충전/배터리 94%/29.9°C/thermal 0/화면 gate 확인 후 한 번 실행했다. 기존 설치본 pull 1회 완료(85.032초), 후보 push 1회가 120.032초 timeout; 원격 hash·설치0, 수집·warmup·추론0. 전체 213.563초. 실패 후 설치본은 여전히 이전 APK 해시, 원격 전송량·무선 내부 원인 미확정.
- 전용 출력/registry는 `stopped_no_resume`로 보존. host force-stop 정상 반환·앱 프로세스 부재·thermal 0 확인, 앱 내부 cleanup 해당 없음. 재시도·재연결·새 계획 자동 실행 없음. 기존 COLLECT-03·FAIL·동결값·원자료와 `experiment_ready=false` 유지.
- 다음 행동: 동일 무선 push timeout에서 원격 진행량이 없는 공백을 대상으로 **별도 배포 진단 계약을 PC에서 설계**한다. 이번 소비 ID를 재사용하거나 후속 수집을 시작하지 않는다.

## 2026-09-27 ENERGY-AP-DEPLOY-RECOVERY-01 PC 준비 — 기기 미실행

- [전송 실패 진단·분리 배포안](ENERGY_AP_DEPLOY_RECOVERY_PC_20260927.md). COLLECT-03 push 120초 timeout은 확인됐으나 원격 전송량·실패 당시 transport 상태·지연 원인은 미확정이다. 기존 106,092,116-byte APK/서명·원본·`stopped_no_resume`·소비 registry를 보존한다.
- 기존 단계형 복구기의 push→원격 해시→설치→설치본 해시와 부분 출력/cleanup을 재사용하는 새 전용 ID·계획을 PC에서 준비했다. 외부 `energy_ap_deploy_recovery_plan_v1/recovery_plan.json` SHA `8b9fb528ea75139d208b3b458072a6f8787bcd10564f12bd62cd1daf718c17c8`; 전송/설치 각 최대1·재시도0·세션/추론0·전체600초. `Check`·관련 PC 테스트 통과, ADB/설치/기기 조회0. 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`, `experiment_ready=false`.
- 다음 행동: 별도 배포 승인 시 현재 동일 A24 transport와 환경 gate를 새로 확인하고 배포 복구만 1회 실행한다. 성공해도 COLLECT-03을 재개하지 않으며, 수집에는 새 계획·소비 기록·별도 승인이 필요하다.

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 종료 — APK 전송 timeout

- [실행 결과·소비·cleanup](ENERGY_AP_STATE_COLLECT03_RESULTS_20260927.md). 승인 plan_v3 SHA 일치, 연결된 A24·실행 직전 환경 gate 통과 후 `Run` 1회. 이전 APK와 후보 APK의 signer는 같으나 해시가 달라 전송 1회 시도했고 `adb push` 120초 timeout. 원격 해시·설치·앱 시작 전 중단, `stopped_no_resume`, 전체 235.125초. 개발/확인 0/6·추론 0/10,152·전송 1/1 시도(완료 미확인)·설치 0/1. 출력/소비 registry 보존, 자동 재개 금지.
- 앱 cleanup 해당 없음(앱 미시작). host force-stop 성공·`ps -A` 프로세스 부재 확인·종료 thermal 0, host cleanup `completed`. 원격 부분 APK 여부·전송 지연 원인 미확정, 앱 내부 memory/GPU/병행·계수 동결/오차 미확인. 기존 FAIL·원자료·동결값·종료 계획과 `experiment_ready=false` 유지.
- 다음 행동: 보존된 전송 command·ADB host 기록에서 timeout 범위를 PC에서 진단한다. 추가 기기 명령·새 계획·재실측은 자동 실행하지 않는다.

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 승인 후 착수 보류 — A24 미연결

- [실행 전 gate 결과](ENERGY_AP_STATE_COLLECTION_PREFLIGHT_20260927.md), 외부 `energy_ap_state_preflight_20260927/PREFLIGHT_RECEIPT.json`. 승인된 plan_v3 해시·예산·`Check` 통과, 브랜치 HEAD `8a7a4d0` clean/원격 일치. `adb devices -l` 기기 0대여서 serial·fingerprint와 현재 환경을 확인할 수 없었다. `Run` 미호출, 세션 0/6·추론/전송/설치/설정 변경 0, 동결·확인 미실시. 새 출력·소비 registry 없음.
- 현재 장애: 승인 대상 A24가 ADB에 표시되지 않음. 배터리·비충전·BAT/thermal·화면·memory·설치본·GPU/병행 적격성은 미확인. 이 착수 시도는 재연결·daemon 재시작·자동 재실행 없이 종료한다. 기존 계획/원본/FAIL/동결값과 `experiment_ready=false` 유지.
- 다음 행동: A24를 연결하고 필요한 USB 디버깅 승인을 완료한 뒤, 현재 serial과 모든 실행 gate를 새로 확인한다. 별도 실행 지시 없이 이 실패 직후 자동 재개하지 않는다.

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 PC 준비 완료 — 실기기 미승인

- [수집·분석 계약](ENERGY_AP_STATE_COLLECTION_PREP_20260927.md), [공유 요약](results/energy_ap_state_collection_03/README.md). 기존 4세션/144분 후보는 세 병행 상태와 다른 전환 순서의 확인을 모두 제공하지 못한다. 새 개발3→동결→확인3, 고정 관측 102분·전체 예약 상한 230분, 명시적 추론 최대 10,152회로 별도 plan_v3를 PC에서 준비했다.
- Android 반복 구간·host 단일 사용/부분 회수/동결/확인 분석, 프로젝트 서명 APK와 manifest·계획 해시·`Check`를 확인했다. 관련 Python 46건·JVM 관련 1건·APK 빌드 통과. ADB·설치·추론 0, 새 출력/소비 registry 없음. 요청 순간 W·동적 AP 계수 식별과 기기 완주는 미확인이다. 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`, `experiment_ready=false`.
- 다음 행동: 별도 230분·10,152회 상한의 실행 여부를 결정하고, 승인 시 현재 A24·서명·환경·병행 적격성 gate를 새로 확인한다. 기존 FAIL·부분 원본·동결값·종료 계획과 S26/NPU 별도 범위는 보존한다.

## 2026-09-27 ENERGY-AP-MODEL-BRIDGE-PC-02 — 실측 보정·예측 오차 우선

- [한국어 범위·오차·최소 수집 후보](ENERGY_AP_MODEL_BRIDGE_PC_20260927.md), [실측/예측 경로와 지원 상태](results/energy_model_bridge_02/dashboard.html). 기존 A24 고정 CC_DG 개발2/확인2와 동결 v1을 보존한 채 개발 점유 상태의 기기 전체 평균전력 네 값과 확인 실제 일정 조건부 J를 사후 진단했다. 합성 도착 엔진은 이 profile로 미지원 전력/AP를 계산하지 않고 joint 상태와 `UNSUPPORTED_STATE_COSTS`를 반환한다. 기존 가정 탐색은 별도 유지한다.
- 확인 고정480초 J 오차(예측−관측) 병행 −8.468J·직렬 +32.306J, 병행−직렬 차이 방향 실패. AP 공통창 MAE 병행 0.425°C·직렬 0.245°C; 상태별 AP 동역학/임의 도착 예측은 미식별. 확인 요약을 본 뒤의 사후 지표이므로 독립 검증 아님. 전류 절대 단위 미인증, BAT/다른 배정 미지원. `experiment_ready=false`, 기존 FAIL·부분 결과·동결값·원자료·종료 계획 보존. ADB/실측 0.
- **현재 우선순위:** 실측에 근거한 에너지·AP 모형의 상태/전환 지원과 별도 자료 예측 오차 확인. 새 정책·강화학습 개발 보류. 다음 행동은 (1) 보고서의 4세션 *미승인* 식별/전환 확인 후보에서 PC 실행 경로와 상태별 장구간 성립·시간 상한을 계산한 뒤 실행 여부 판단, (2) 독립 자료 없이는 합성 도착 에너지/AP를 가정 탐색으로만 표시. 배터리 잔량/사용시간은 소비 J와 다른 목표다.

## 2026-09-27 ARRIVAL-BASELINE-REVIEW-01 완료 — 비교군의 실제 출처 분리

- [기준선 검토 보고서](ARRIVAL_BASELINE_REVIEW_20260927.md)와 [작은 비교표](results/arrival_baseline_review_01/baseline_matrix.csv). HEAD `4368032`의 앱 본체는 계측 UI이고, 정책 도입 전 benchmark는 반복 추론 도구였다. `CPU_FIFO`·`CPU_URGENT`는 격리된 arrival 실험의 자체 기준이며 실사용 기본 정책이 아니다. Ente는 공개 앱의 조작 기반 시작 제한, MediaPipe는 task 예제, Band는 연구 프레임워크로 구분했다. 권고는 **기존 합성 동일 엔진 비교(C)를 유지**하고 CPU_FIFO를 단순 대리 anchor, 개발 고정 B2와 B3를 강한 연구 기준으로 명시하는 것이다. 외부 앱/프레임워크 직접 실행·A24 포팅·새 정책·기기 실측 0회. 기존 P의 불리한 결과·FAIL·동결값·원자료·종료 계획과 `experiment_ready=false`는 불변.
- 현재 작업 완료. 다음 행동은 (1) 연구 보고서의 기준군 명칭을 위 근거대로 한 번 정리하고, (2) 외부 정책 재구현을 별도 채택할 경우에만 Band 원 코드와 작은 결정 trace의 의미 일치를 먼저 검증하는 것이다. 이번 검토는 외부 구현 비교 채택이나 새 실측 승인으로 기록하지 않는다.

## 2026-09-27 ARRIVAL-INFORMATION-CHECK-PC-01 완료 — 새 온라인 규칙 보류

- [첫 선택 정보 경계 보고서](ARRIVAL_INFORMATION_CHECK_PC_20260927.md), [동결 분기·CSV·재현](results/arrival_information_check_01/README.md), [통합 대시보드](results/arrival_policy_screen_01/dashboard.html). queue/burst offline 발견 일정의 첫 CPU와 기존 V1 첫 GPU를 같은 시각0 snapshot에서 비교했다. 2사례×6미래 분기×2행동=24 PC 재생, 관련 테스트 5건 통과, 기기 실행 0. 사전 비악화 gate 실패: queue 에너지 차이는 +0.655~−0.057J, burst는 −1.943~+0.278J로 미래에 따라 방향이 바뀌며 요청별 응답/AP 상충이 있다. 기존 완전 offline 개선은 첫 선택만의 효과가 아니다.
- 현재 작업 종료. 다음 행동은 **현재 정보만으로 정당화되는 새 규칙 개발을 보류하고 이 한계를 연구 결과에 명시**하는 것이다. 기존 P/V1·동결값·FAIL·부분 자료·종료 계획 보존, `experiment_ready=false`. 새 seed/24요청 조건부 확인은 규칙 미구현으로 실시하지 않았다.

## 2026-09-27 ARRIVAL-OFFLINE-SCHEDULE-PC-01 — 작은 사례 제한 탐색 완료

- [질문·결과·한계](ARRIVAL_OFFLINE_SCHEDULE_PC_20260927.md), [설정·CSV·재현](results/arrival_offline_search_01/README.md), [통합 대시보드](results/arrival_policy_screen_01/dashboard.html). 기존 low/queue/burst의 시간순 첫 2/3요청과 seed301·미측정 전력/AP profile을 탐색 전 고정했다. 68/258/301노드, 완료 일정 41/114/127개를 제한된 큐 선두·CPU/GPU·250ms/최대500ms 대기 공간에서 완전 열거했다. 기존 열·에너지 후보 대비 요청별 응답 손실0에는 에너지/AP 개선 일정이 없고, 연구용 손실500ms에는 queue −0.127J, burst −2.004J/−0.080°C가 있으나 응답 손실과 offline 미래 정보가 따른다. 각 일정은 기존 이벤트 엔진으로 재생·회계 일치 확인; 기기 실행0.
- 현재 작업 종료. 다음 행동 1개: 발견 일정의 첫 배정·대기를 당시 관측 정보만으로 구별할 수 있는지 trace에서 판정한다. 기존 192실행/72 확인 짝 비교·P·동결 계수·FAIL·부분 결과·종료 계획은 보존했다. 실기기 절감·열 안전·온라인 달성 가능성은 미입증이며 `experiment_ready=false` 유지.

## 2026-09-27 ARRIVAL-THERMAL-FEEDBACK-PC-01 — 온라인 에너지·AP 후보 PC 탐색 완료

- [정책·한계·비교 보고서](ARRIVAL_THERMAL_FEEDBACK_PC_20260927.md), [단일 대시보드](results/arrival_policy_screen_01/dashboard.html), [설정·CSV·재현](results/arrival_thermal_feedback_01/README.md). 별도 `THERMAL_ENERGY_PC_V1`을 기존 이벤트 엔진에 opt-in으로 연결했다. 미측정 기기 전체 전력/AP 가정 아래 개발 96·새 seed PC 확인 96 실행, 실기기 0. 확인 24 matched 비교 중 응답·완료 손실 없이 에너지까지 개선한 정책 쌍은 0; 일부 energy/AP 이득은 응답·일반 위반 또는 다른 지표 악화를 동반한다. 엄격 모드 미지원, Android 정책 미구현, BAT/실제 절감·열 안전 미검증이다.
- 현재 작업 종료. 다음 행동: (1) 대시보드에서 조건별 상충을 검토해 이 후보의 연구 가치 판단, (2) 실제 선택/절감 주장으로 진행할 때에만 joint 상태 전력·AP 경로·판단 비용의 별도 측정 목적 확정. 기존 P·동결값·FAIL·부분 결과·종료 계획·`experiment_ready=false` 보존.

## 2026-09-27 ARRIVAL-INTEGRATED-EXPLORER-PC-01 — 통합 PC 탐색 완료

- [단일 오프라인 대시보드](results/arrival_policy_screen_01/dashboard.html)와 [사용·상대 경로 재현 안내](results/arrival_policy_screen_01/README.md), [한국어 판독](ARRIVAL_INTEGRATED_EXPLORER_20260927.md). 착수 HEAD `b15526a`, 선택 135일정의 저장 응답 지표 검증 재생으로 task×backend 점유를 얻었다. B2 CG_DC·B3 탐지 CPU＋GPU 등 기기 전체 전력을 독립 탐색 입력으로 분리하고 δ(%p)·seed·간섭·AP 가정을 한 화면에 연결했다. 기존 공통 병행 전력 결과·원본 유지. PC 관련 6테스트와 로컬 Chrome 기본 화면 렌더 통과; Android 계측·정책 튜닝·실측 0.
- 시간은 CAL-03 기반 조건부 PC 결과, 전력·열은 미계측 사후 가정이다. 열 피드백/실기기 정책 우위·BAT·절대 에너지 정확도는 미검증. 다음 행동≤3: (1) 팀은 대시보드에서 응답 제약·독립 병행 전력 가정에 따른 상충을 탐색, (2) 실제 에너지 절감 주장은 별도 근거가 생길 때만 판단. 기존 FAIL·동결값·20 null·원본·종료 계획·`experiment_ready=false` 유지.

## 2026-09-27 ARRIVAL-COST-BOUNDARIES-PC-01 — B2·B3·CPU 미측정 비용 경계

- [한국어 판독·상태 근거·역전 경계](ARRIVAL_COST_BOUNDARIES_PC_20260927.md), [오프라인 대시보드·재현 CSV](results/arrival_cost_boundaries_01/README.md). 기존 45개 같은 trace/seed/실현 간섭에서 idle·단독·병행 시간을 복원하고 seed201 저장 timeline과 대조했다. queue/간섭1.5 B2−B3의 가정 전력 역전점은 idle1W/단독2W에서 2.070–2.100W/5 seed이나 실기기 가능 범위는 미확인이다. B2는 CG_DC, B3는 탐지 CPU＋GPU 점유가 커서 기존 반대 방향 CC_DG 값을 전용할 수 없다. 대표 AP 부호도 미보정 병행 열 가정에 따라 바뀐다. PC 관련 테스트 2건 통과, 이벤트 배치·ADB·실측 0.
- 다음≤3: (1) B2−B3 queue/burst의 공통창 기기 전체 전력·AP를 식별할 단일 측정 목적과 Android active 지원·센서 dwell 적격성을 별도로 확정. 서비스 선호 미정이므로 측정만으로 단일 정책을 채택하지 않는다. 기존 FAIL·원본·동결값·종료 계획·`experiment_ready=false` 유지.

## 2026-09-27 ARRIVAL-POLICY-SCREEN-PC-01 — 기존 결과의 후보 선별

- [한국어 판독·지원 범위·다음 행동](ARRIVAL_POLICY_CANDIDATE_SCREEN_20260927.md), [오프라인 정책 비교표·45행 CSV](results/arrival_policy_screen_01/README.md). 기존 low/queue/burst × 평가 seed 5 × 실현 간섭 3의 동일 입력만 재집계했다. 핵심 후속 비교는 B2·B3·CPU 긴급우선, 고정 분리는 긴급 응답 극단 대조로 유지한다. 현재 P는 queue/1.5의 평균 비지배가 seed 2/5에만 유지되어 재현용으로 보존하고 튜닝·확대를 우선하지 않는다. 미보정 에너지/AP는 별도 가정 층이며 실기기 우열은 미판정이다. `python -m unittest tools.test_d1_arrival_policy_screen -v` 3건 통과; ADB·실측·기존 전체 배치 0.
- 다음≤3: (1) B2·B3·CPU의 실제 선택을 바꿀 idle·단독·B2 방향 병행의 기기 전체 전력/AP 관측 필요성을 공통창·지원 조합 기준으로 좁히기, (2) Android active 배정/독립 확인은 별도 승인된 계획에서만 검증. 기존 FAIL·원자료·동결값·종료 계획·`experiment_ready=false` 유지.

## 2026-09-27 ARRIVAL-INTERFERENCE-ENERGY-DIAG-PC-02 — 예상/실현 간섭·에너지/AP 경계

- [한국어 판독·가정·다음 조건](ARRIVAL_INTERFERENCE_ENERGY_DIAGNOSTIC_20260927.md), [오프라인 진단 탭·CSV/PNG/SVG·재현](results/arrival_diagnostic_02/README.md). 기존 동결 엔진/seed·B2를 유지하고 low/queue/burst의 explore PC 315조합만 별도 실행했다. 실현 간섭2.0에 P 예상도2.0으로 맞춰도 queue 긴급 P95 평균 +150.36ms/일반 +443.00ms, burst +2213.56/+661.57ms(B3 대비) 손실이 남는다. queue 대표 trace에서 비어 있는 GPU 대신 바쁜 CPU를 우선해 기다린다. 간섭1.0 일치에서는 P/B3 동일; 완벽 정보는 진단 가정이다.
- 사후 공통120초 에너지는 상태별 전력의 선형식이며 queue/실현1.5의 P−B3 병행 전력 동률점은 seed별2.151–3.479W(임의 스트레스 값; 물리 범위 아님). AP 최고 차이도 가정 pair 평형30/42°C에 따라 방향이 바뀐다. 일부 차이는 1% 미만이고 seed 방향도 달라 절감·열 제약·정책 PASS 없음. 기존 고정870건·MobileNet 계수 미전용, 열 피드백/실기기 표본0. 관련 PC/Chrome 검증 통과.
- 다음≤3: (1) 연구용 응답/기한 제약과 공통창 에너지의 선택 규칙을 명시하여 P/B3가 실제 경쟁 후보인지 판단, (2) 그때 에너지 부호가 선택을 바꾸면 idle·단독·병행 기기 전체 전력의 최소 계측 여부 결정, (3) AP 한도를 선택에 쓰는 경우에만 AP 시간 응답 근거 추가. 기존 FAIL·동결값·원자료·종료 계획·`experiment_ready=false` 유지.

## 2026-09-27 ARRIVAL-ENERGY-SENSITIVITY-PC-01 — strict 경로 확인·에너지/AP 사후 탐색

- [계수/실행 경로·가정 한계 판독](ARRIVAL_ENERGY_SENSITIVITY_PC_20260927.md), [오프라인 대시보드·CSV/그림·재현](results/arrival_visualization_01/README.md). strict 대표 low/queue/burst seed201에서 P와 B3의 24요청별 backend·dispatch·응답·lane 해제가 동일함을 대조했다. `global_serial`과 적응형 CPU fallback으로 pair 비용이 작동하지 않으며 원 strict 쌍차 0을 설명한다. 탐색 간섭의 예상 1.5와 실현 1.0은 별개다.
- 기존 도착 일정에 5정책·4개의 **미보정 스트레스 가정**을 사후 회계했다. queue/explore seed201 P−B3 공통창 에너지 방향은 병행 전력 가정 2W/3W에 따라 +0.301/−1.693J, AP 최고 방향은 병행 평형30/42°C에 따라 +0.137/−0.212°C로 바뀐다. 열 피드백·도착별 실측 보정 없음. 기존 고정870건·MobileNet 계수 미전용, BAT·절대 절감·정책 PASS 미지원. 관련 PC/browser 7건 통과, ADB/실측 0.
- 다음≤3: (1) 실제 절감 판단이 필요하면 도착 idle·단독·CC_DG 겹침의 기기 전체 전력/대응 AP를 별도 승인된 계측으로 식별, (2) 그 전에는 스트레스 민감도만 탐색으로 인용, (3) 기존 합성 도착 수집 후보는 현재 승인 없이 실행하지 않음. FAIL·동결값·종료 계획·`experiment_ready=false` 유지.

## 2026-09-26 ARRIVAL-VISUALIZATION-PC-01 — 기존 PC 결과의 오프라인 시각화

- [로컬 한국어 대시보드·PNG/SVG/CSV·재현 안내](results/arrival_visualization_01/README.md). 기존 960평가/126개발 배치는 반복하지 않았다. 저장된 queue/explore 대표 trace 8개와 나머지 seed201 대표 trace 40개 최소 재생을 합쳐 low/queue/burst×strict/explore×8정책 타임라인을 만들고, 저장된 평가 지표 7개와 대조했다. Chrome 로컬 파일 렌더·low/strict/B2 및 burst/explore/P 필터 전환, 관련 PC 테스트 3건 통과.
- 합성 도착의 응답은 **PC 모형 탐색**이고 에너지/AP는 상태별 계수 부재로 `계산 불가`다. 대시보드의 에너지·AP 경로와 상충 산점도는 **별도 고정 870건 CC_DG**의 실측 재생/사후 동결 모형 예시이며 합성 도착 정책 결과가 아니다. 절대 J 단위 조건부, BAT 미지원, 실기기 합성 도착 수집0/`experiment_ready=false` 유지.
- 다음≤3: (1) 별도 승인 시 Android 합성 도착 수집 후보의 현재 기기 gate 재확인, (2) 실제 원본이 생기면 동일 회계 경계로 시각화 입력 확장, (3) 임의 도착 에너지/AP 계수 적격성 전에는 정책 절감 판정 금지. 기존 FAIL·동결 설정·종료 계획 불변.

## 2026-09-26 ARRIVAL-ENERGY-SYNTHETIC-COLLECT-01 — Android 재생·계측 PC 준비

- [Android 재생·에너지/AP 후보 계약](ARRIVAL_ENERGY_ANDROID_PREP_20260926.md), [검증·로컬 산출물·명령](results/arrival_energy_android_prep_01/README.md). 기존 low/queue/burst 각24예정 도착을 별도 Activity에서 `CPU_URGENT`와 `FIXED_SPLIT`으로 재생하고, 1초 앱 전류/전압·2초 host AP를 동일 120초 공통창에 연결하도록 구현했다. 4-runtime owner thread·warmup8·큐/응답/저장/lane 해제·snapshot 예외/부분 회수 경계를 보존한다. 기존 Android arrival·고정 에너지 경로와 P/B2는 변경하지 않았다.
- 프로젝트 서명 APK SHA `1f2bec87…b659`, 새 계획 v4 SHA `64b2a9a8…2dc0`, 12 manifest/스크립트 `Check`·관련 Kotlin/Python 테스트 통과. **ADB·설치·앱 실행·추론/실측 0, output/registry 없음; 실행 미승인·기기 적격성 미확인.** 목적 A(고정 trace별 전체 결과)는 향후 관측 가능하나, 목적 B(다른 trace용 상태별 전력/열 보정)는 짧은 요청·느린 센서 갱신으로 이번 표본만으로 보장되지 않는다. 공통창 관측 시간24분, hard 상한177분은 정상 예상이 아니다.
- 다음≤3: (1) 별도 승인 후에만 현재 A24·설치본·환경/품질 gate로 새 계획 단일 실행 여부 결정, (2) 실행된다면 개발6 적격→고정 규칙 동결→확인6/부분 결과 판독, (3) 상태별 모형 B는 실제 dwell/coverage가 식별될 때만 별도 설계. 기존 FAIL·부분 결과·40값/20null·원자료·종료 계획·`experiment_ready=false`와 S26/NPU 별도 범위 유지. 아래는 이력이다.

## 2026-09-26 ARRIVAL-ENERGY-SYNTHETIC-PC-01 — 합성 연구 범위 채택·최소 PC 계약

- 사용자 결정은 **실측 보정 모형+출처 명시 합성 조건**이며 실제 서비스 SLA/실사용 배터리 절감 주장 아님. 발열·배터리·응답 원래 목표와 고정870건 중간 질문은 유지. [3조건·공통창·근거/가정 경계](ARRIVAL_ENERGY_SYNTHETIC_RESEARCH_20260926.md), [재현·manifest](results/arrival_energy_research_01/README.md). 기존 low/queue/burst 각24건·연구용 1.5/6초, 예정 전체 분모·긴급 O/일반 P·lane L·120초 공통창을 별도 PC adapter로 검증했다. 임의 도착의 전력/AP는 profile 부재로 `null`, 명시적 가정만 탐색; 새 정책 성능 순위·Android/ADB·실측 없음.
- 다음≤3: (1) Android active 재생·상태별 전력/AP 계측의 PC 계약 및 실제 샘플링/세션시간 타당성 점검, (2) 지원 정책·상태를 제한한 개발 보정/독립 확인 예산·중단 기준 동결, (3) 별도 승인 전 실측·독립 정책 평가 금지. 기존 FAIL·부분 결과·40값/20null·원자료·종료 계획·`experiment_ready=false`·S26/NPU 별도 범위 유지. 아래는 이력이다.

## 2026-09-26 ENERGY-THERMAL-BRIDGE-PC-01 — 중간 질문 채택·원래 목표 실행안

- 사용자 채택: 고정870건 CC_DG 직렬/병행은 **중간 질문**, 원래 혼합 도착·발열/배터리 최적화 목표는 유지. [근거·최소 부족 항목·단계/중단 기준](ENERGY_THERMAL_TO_ORIGINAL_GOAL_PLAN_20260926.md). 기존 요청별 2/8초 및 PC 1.5/6초는 engineering 시나리오이며 묶음 완료기한/실사용 SLA가 아니다. 480초는 고정 기술 경계, AP는 관측 지표다. 공통창 에너지 방향 역전과 조건당 한 세션 때문에 절감/정책 PASS 없음.
- PC `decision-preview-v2`는 29.1°C가 사후 확인 두 arm의 일치값임을 결과에 표시하고 단일 후보를 `RETROSPECTIVE_MODEL_CANDIDATE`로 반환한다. 다른 시작값은 회고적 오차 적용 근거가 없어 차단하며 온도 물리 지원 범위로 표현하지 않는다. 동결 모형·기존 v1 공유 결과 보존, 관련 unit 4건 통과. ADB/설치/실측/전체 배치 0.
- 다음≤3: (1) 실제 서비스/배터리 요구 근거 또는 engineering 민감도 주장 범위를 동결, (2) 그 결과 안정적 절감/동적 정책 판정이 필요한 경우에만 최소 상태·변동성 계측 범위와 예산 산정, (3) 새 독립 평가 전 모형/정책·기준 동결. 기존 FAIL·부분 결과·40값/20null·원자료·종료 계획·`experiment_ready=false`·S26/NPU 별도 범위 유지. 아래는 이력이다.

## 2026-09-26 ENERGY-THERMAL-RESEARCH-SCOPE-01 — 고정 묶음 연구 질문 검토

- [짧은 설계·근거·다음 판정 경계](ENERGY_THERMAL_RESEARCH_SCOPE_20260926.md). 출발 `1c1b449`/clean. 원래 혼합 도착·동적 배정과 별개로, 동일 870건 CC_DG의 완료기한 아래 **공통 480초 조건부 기기 에너지와 AP 경로**를 비교하는 중간 질문을 권고한다. 최종 목표 변경이나 에너지 절감 PASS는 아니다. 개발 공통창 에너지 차이 −36.255J와 확인 +4.559J의 방향 역전, arm당 block별 1세션, 전류 단위 한계를 유지한다.
- 29.1°C는 개발 기준/사용자 한도가 아니라 확인 두 세션에서 관측된 시작 AP다. 기존 PC 선택기의 동일값 제한은 확인 오차를 붙이는 회고적 예시에만 해당한다. 개발 AP 29.4/29.2°C에서 확인 29.1°C로 AP 변화 템플릿을 평행 이동하는 가정은 미검증이다. 동결 모형·기존 코드·결과 불변, ADB/실측/배치 0.
- 다음≤3: (1) 이 좁은 질문을 중간 질문으로 쓸지 결정, (2) 채택한다면 서비스/배터리 근거로 완료기한·공통창 적합성·최소 의미 절감량을 새 결과 전에 동결, (3) 그때만 필요한 독립 block 변동성/추가 계측을 산정. 기존 FAIL·부분 결과·40값/20null·종료 계획·`experiment_ready=false`·S26/NPU 별도 개발 유지. 아래는 이력이다.

## 2026-09-26 ENERGY-OPERATIONAL-DECISION-PC-01 — 제한된 의사결정 탐색 완료

- [한국어 판단·오차 분해·지원 범위](ENERGY_OPERATIONAL_DECISION_PC_20260926.md), [작은 CSV/입출력·재현 명령](results/energy_operational_decision_01/README.md). 출발 `3106425`/clean. 기존 profile/확인 자료를 보존하고 확인 2세션의 공통480초 에너지 예측−관측 차이를 단계별 산술로 분해했다. 병행−직렬 오차 −40.774J 중 부하 평균전력항 −43.448J가 가장 크나 원인·인과효과 식별은 불가. 계측/경계 결함은 발견되지 않아 동결 모형 재보정 없음.
- 별도 PC 탐색 입력에서 고정870건 CC_DG의 사용자 지정 작업 완료기한·AP 최고 제한·공통창 조건부 기기 에너지 경계를 검사한다. 출력은 모형상 단일 후보/상충/판단 불가/지원 밖이며 기본 정책·Android 실행·임의 도착 엔진은 불변. 기준 미설정 예시는 `TRADEOFF`, 확인1세션 오차는 사후 민감도일 뿐 보장/CI 아님. 새 unit 4건·분해 항등식과 원본 지표 대조 통과, ADB·추론 0.
- 다음≤3: (1) 고정 기술 비교와 실제 서비스 최적화 중 보고서 주장 범위를 결정, (2) 후자를 원할 때만 완료기한/AP 기술 제한 및 에너지 경계를 사용자 요구로 정한 뒤 필요한 독립 근거를 계약, (3) 추가 실측·P 튜닝·동적 지원 확대는 별도 결정 전 중단. 기존 FAIL·부분 결과·40값/20null·동결 profile·종료 계획·`experiment_ready=false`·S26/NPU 별도 개발 유지. 아래는 이력이다.

## 2026-09-26 ENERGY-OPERATIONAL-SIM-PC-01 — 4세션의 제한된 시간·에너지·AP 연결 완료

- [한국어 결과·오차·한계](ENERGY_OPERATIONAL_SIM_CONNECTION_20260926.md), [profile/CSV/그림·재현 명령](results/energy_operational_sim_01/README.md). 출발 `cf7aa263`/clean, 기존 4/4 raw 재생 일치. 개발 직렬1·병행1만 고정 episode 템플릿에 넣고 profile SHA `b58c2ca3…0772`와 평가 명세 SHA `383a50c5…d763`를 별도 동결했다. 확인 직렬1·병행1은 재보정 없이 오차만 계산했다. 확인 요약을 이미 본 뒤의 연결이므로 완전한 사전등록 독립 검증은 아니다.
- 확인 병행−직렬은 완료 −126.319초·완료시점 조건부 에너지 −143.341J·공통480초 에너지 +4.559J·부하 AP 최고 +1.9°C. 동결 템플릿은 앞 두 방향과 AP 최고 방향은 재현하나 공통창 에너지 방향은 **−36.216J로 실패**. 조건별 1세션, 열 상태·순서·유휴 소비 교란, 전류 raw=mA 조건부 해석, 미계측 단계 공백으로 인과/전체 운영 에너지/정책 PASS는 불가. BAT·다른 병행/도착/작업량은 미지원. PC unit 6건 통과, 원본/기존 정책 불변, ADB·추론 0.
- 다음≤3: (1) 이 고정 CC_DG 기술 비교의 시간·에너지·발열 상충을 조건부 결과로 사용, (2) 다른 배정/도착·실서비스 최적화를 주장할 경우에만 해당 조건과 평가 기준을 사전 계약, (3) 추가 실측·정책 튜닝은 별도 결정 전 수행하지 않음. 기존 FAIL·부분 결과·40값/20null·종료 계획·`experiment_ready=false`·S26/NPU 별도 개발 유지. 아래는 이력이다.

## 2026-09-26 ENERGY-OPERATIONAL-PAIR-01 — 4세션 운영 비교 완료

- 출발 `9e9668b`/clean, 승인된 plan_v3 SHA `4d0bd250…0ed5` 1회 실행. [결과·한계·재현 명령](ENERGY_OPERATIONAL_PAIR_01_RESULTS_20260926.md), 공유 [세션 CSV](results/energy_operational_pair_01/sessions.csv), 외부 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1/FINAL_RECEIPT.json`. 동일 A24·서명/환경 gate 통과, APK 전송·설치 각1. registry `completed`, 재실행 금지.
- 개발 직렬→병행2/2 완료, 개발 설정 SHA `1dc5766a…2881` 동결 후 확인 병행→직렬2/2 완료. 작업3,480·적격성16=진단3,496, warmup32, 총 명시적 추론3,528, runtime16, staging4·28파일. 실패/미완료0, 재시도0, 앱·host cleanup/프로세스 부재 확인. 전체3,847.922/8,640초.
- 두 block에서 병행은 같은870건 완료가 약122~126초 빠르고 완료시점까지의 조건부 기기 전체 에너지는 낮았다. AP 최고온도는 +1.2/+1.9°C, 480초 공통창 에너지 방향은 개발 -36.255J/확인 +4.559J로 다르다. 조건당 개발1·확인1세션, 시작 열 상태·순서 교란, 전류 단위/절대 정확도와 전체 운영 에너지 공백 때문에 에너지 절감·정책 우월성·시뮬레이터 PASS는 아님. 확인값으로 재보정하지 않음.
- 다음≤3: (1) 이 제한된 상충을 보고서에 반영하고 CC_DG 관측 trace만 조건부 PC 입력으로 사용, (2) 실제 서비스 제약·다른 병행/부하까지 주장하려면 별도 사전 계약과 독립 근거 판단, (3) 추가 실측/정책 튜닝은 새 승인 전 중단. 기존 FAIL·부분 결과·40값/20null·종료 계획·`experiment_ready=false`·S26/NPU 별도 협업 유지. 아래는 당시 이력이다.

## 2026-09-26 ENERGY-DESIGN-REVIEW-PC-01 — 중단 분석·별도 운영 후보 PC 준비

- 시작3773f26/clean. [종합 보고서·선택지·예산·명령](ENERGY_DESIGN_REVIEW_20260926.md). COLLECT-04/05와 sampler5시도·온도 원문1064개를 제한 재생했다. 온도31.5/32.3°C 재현, COLLECT-05의98개 off-anchor 창·준비의 비대칭 확인. 주변/잔열 원인·평형·병행 본 부하 효과는 미확정. 구 계획은 모두 보존·재개 금지.
- 완료: 새 운영 전용 경로(동일 직렬+병행 기술 probe→고정 resident120초→baseline1회), 초기화/gate를 포함하는 비중복 관측에너지 ledger, 부분 회수 오류 보존. 기존 에너지값 재생 일치, Python40·Kotlin core7·새 서명APK/plan Check 검증. 기기 실행0. [검증 대상·산출물](results/energy_design_review_01/README.md).
- **권고 후보, 실행 미승인:** ENERGY-OPERATIONAL-PAIR-01 / `energy_operational_plan_v3`. CC_DG 개발 직렬→병행, 확인 병행→직렬의4세션. 진단3496/warmup32/추론3528/runtime16/staging4·28파일/전송·설치≤1/retry0. 고정60분·timeout 예약141분40초·hard144분. 동일 초기 열 상태의 인과효과가 아닌 제한된 운영 비교이며 AP matching은 새 estimand에서 N/A다. 안전 gate는 유지한다.
- 다음≤3: (1) 이 제한된 운영 질문의 새4세션 실행 여부 결정, (2) 승인 후에만 현재 기기/설치본/환경·기술 probe gate 확인, (3) 완료/실패 후 사전 분석·무재보정 종료. 기존 FAIL·부분 결과·40값/20null·`experiment_ready=false`·S26/NPU 별도 협업 불변. 아래는 당시 이력이다.

## 2026-09-26 ENERGY-THERMAL-COLLECT-05 — 준비 온도 gate 중단·재개 금지

- 승인된 plan_v9 SHA `3f794c9a…5bfc2` 1회 실행. [종료 판독](ENERGY_THERMAL_COLLECT05_RESULTS_20260926.md), 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v5/FINAL_RECEIPT.json`·`FINAL_REPORT.md`. 동일 A24·서명/환경 gate 통과, APK 전송·설치 각1. 전체1,389.359/16,080초, retry0, registry `stopped_no_resume`.
- 개발2시도: CC_DG 직렬1적격 완료, 병행1은 runtime4/warmup8/적격성2 뒤 AP 준비351.176초에서 중단. AP 126표본32.3~33.5°C, 직렬 anchor31.5°C의 사전 허용31.25~31.75°C 미도달. 공식 병행 baseline/load 없음; 개발2·확인4 미시도, 동결 없음. 완료 근거 runtime8·warmup16·진단874·추론890. 둘째 앱 cleanup 미확인, host 종료·프로세스 부재·thermal0 확인.
- 직렬 단일세션 조건부 에너지·발열 수치만 가능하고 paired 비교/절감 판정 불가. 다음: (1) 현재 AP 경로와 준비 비용으로 동일 anchor의 실현 가능성 PC 검토, (2) 그 결과 전까지 새 전체 수집·gate 완화·정책 PASS 보류. 기존 FAIL·부분 결과·40값/20null·종료 계획·`experiment_ready=false` 유지. 아래는 과거 이력이다.

## 2026-09-26 ENERGY-THERMAL-COLLECT-05 — 온도 준비 PC 설계·기기 미실행

- [COLLECT-04 온도 분석·새 후보 계약](ENERGY_THERMAL_TEMPERATURE_PREP_20260926.md): 공식 AP baseline 31.5°C/32.3°C 차이 +0.8°C 재현. 첫 직렬 냉각 마지막32.3°C→다음 세션 전31.4°C, 이후 runtime/warmup/적격성 경과 후 baseline 첫 표본33.8°C. 준비 단계 재가열은 관측되지만 잔열·주변 원인은 미식별이며 고정 180초 냉각 부족이라고 단정하지 않는다.
- 별도 COLLECT-05/plan_v9에 resident AP 준비 창 최대360초를 모든 8세션에 동일 적용하고 공식 baseline은 한 번만 수집한다. 확인 병행 anchor가 같은 단계 직렬 세션을 쓰도록 host 결함도 수정했다. 기존 ±0.5°C paired gate·비교군·작업량·동결 규칙 불변. 새 hard 상한268분, 진단6976/warmup64/추론7040, retry0. 관련 Python26건·Kotlin 핵심 테스트·격리 APK/프로젝트 서명·plan Check 통과. **실기기 미검증·실행 미승인**; 새 run/registry 미생성.
- 다음: (1) 새 계획 별도 승인 여부 판단, (2) 승인 시 현재 A24/설치본/환경·병행 gate 확인 후 한 번만 실행, (3) 실패 또는 완료 후 대기 비용과 본 비교 결과를 구분해 판독. 기존 COLLECT-04 `stopped_no_resume`·부분 에너지/불확실성·FAIL·40값/20null·`experiment_ready=false` 유지. 아래는 과거 이력이다.

## 2026-09-25 ENERGY-THERMAL-COLLECT-04 — paired AP baseline gate 중단·재개 금지

- 시작 `16ce73e`/clean, 승인된 plan_v7 SHA `a1399e2f…96719` 단일 실행. [종료 판독](ENERGY_THERMAL_COLLECT04_RESULTS_20260925.md), 외부 `energy_collection_run_v4/FINAL_RECEIPT.json`·`energy_collection_analysis_v4/FINAL_REPORT.md`. 동일 A24와 설치본·서명·환경 gate 통과, 전송/설치0. 실행·cleanup 1,024.188초/220분, 재시도0, registry `stopped_no_resume`.
- 개발2시도: CC_DG 직렬1완료, 병행1은 시작 AP baseline 32.3°C 대 직렬31.5°C(+0.8°C, 허용 ±0.5°C)로 부하 전 중단. 개발2·확인4 미시도. runtime8/8, warmup16/16, 진단874건 lane 해제 확인, 명시적 추론890건 완료 근거. 둘째 앱 cleanup 미확인, host 강제종료·프로세스 부재 확인. 동결/확인 없음, 병행·에너지 절감 비교 불가.
- 첫 직렬870건의 완료까지 327.208초·기기 전체 540.675J는 A24 전류 mA 가설의 조건부 단일세션 값이며 절대 정확도/우월성 PASS가 아니다. 기존 FAIL·부분 결과·40값·20null·종료 계획·`experiment_ready=false` 보존. 다음: (1) PC에서 고정 냉각과 paired AP gate의 양립성 검토, (2) 별도 결정 전 새 실측·기준 변경 없음. 아래는 과거 이력이다.

## 2026-09-25 ENERGY-THERMAL-COLLECT-04 — 수정본 정식8세션 PC 준비 완료·기기 미실행

- 시작 `919f908`/clean. [새 계약·예산·명령](ENERGY_THERMAL_COLLECTION_REPREP_04_20260925.md), 외부 `energy_collection_plan_v7`/`energy_collection_reprep_pc_v2`. 종료된 COLLECT-03와 완료 진단의 plan/receipt/registry hash를 계보로 묶고 표본은 제외한다. 수정 APK SHA `2874a97f…0931`/같은 signer 재사용, Android 변경·재빌드 없음. 새 run_v4/registry COLLECT-04 미생성.
- 동일 축소 화면 조회/두 pair의 직렬→병행 gate·비교 순서·작업량·timeout·개발 동결/확인 비재보정 유지. 신규 관련 Python3건 및 최종 plan/manifest/서명/입력 Check 통과(`PC_READY_DEVICE_UNVERIFIED`, 기기 명령0). 직렬 진단1회는 병행/반복 안정성 증거가 아니다. 고정104분·timeout 예약206분40초·hard220분, 진단6976/warmup64/추론7040/runtime32, 전송/설치≤1·retry0. 정상 평균시간/배터리 완주 미확인.
- 다음: (1) 새 계획의 별도 실행 승인 판단, (2) 승인 시 현재 A24·설치본·환경/병행 gate 확인 후 계약대로 단일 사용. 이번에는 ADB/실측0. 기존 FAIL·부분 결과·40값·20null·종료 계획·`experiment_ready=false` 유지. 아래는 과거 이력이다.

## 2026-09-25 ENERGY-SAMPLER-LOAD-DIAG-01 — 수정 sampler 직렬 부하 1세션 완료

- 시작 `55a143b`/clean. [종료 판독](ENERGY_SAMPLER_LOAD_DIAG_RESULTS_20260925.md), 외부 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_sampler_load_run_v1/FINAL_REPORT.md`. 계획 v2 단일 실행 완료·registry consumed. 동일 A24·환경 gate 통과, APK 전송/설치 각1, staging1/7파일, runtime4, warmup8, 적격성2·작업870의 명시적 추론880 모두 확인. retry·대체·추가0, 전체902.5/2100초.
- 872요청의 dispatch/start/output_ready/release/lane_available 각872, sampler snapshot1678개 시간·상태 정합, 화면조회71/71, 앱/host cleanup·프로세스 부재 확인. 실패 sidecar 없음. **진단 1세션의 직렬 경로 확인**만 가능; 과거 COLLECT-03 원인·병행/반복 안정성·에너지 절감/정식 보정 PASS 미확인. 기존 FAIL·부분 에너지/결과·40값·20null·종료계획·`experiment_ready=false` 유지.
- 다음: (1) 별도 정식 수집 재준비 시 동일 수정 APK/관측 경로를 개발·확인에 적용하는 계약 차이 검토, (2) 직렬·병행 적격성과 독립 확인 예산을 새 승인 전에 고정. 이번 계획 재실행·추가 실측 없음. 아래는 과거 이력이다.

## 2026-09-25 ENERGY-SAMPLER-PC-01 — snapshot 결함 PC 재현·수정, 기기 미실행

- 시작bb38b1d/clean. [원인 수준·수정·후속 후보](ENERGY_SAMPLER_PC_20260925.md). 실제 옛 toMap 표현의 size1→마지막 항목 삭제 경쟁으로 NoSuchElementException을 PC 재현했다. 과거 COLLECT-03 stack 부재로 동일 원인 확정은 하지 않는다.
- active/resident/phase를 짧은 lock 아래 detached 복사, 센서·추론·I/O/close는 밖에 둠. 실패 stack/thread/phase/시간을 독립 sidecar와 cleanup에 보존하고 증거 게시→stop 순서를 검증. 단위/작업량/timeout/환경 gate/retry0 불변. 기존 원본·소비량/불확실성·FAIL/부분에너지/40값/20null/experiment_ready=false 유지.
- 새 프로젝트 서명 APK와 진단 전용1세션 후보를 별도 계보로 준비. CC_DG 직렬870작업+2적격성·8warmup=880추론, runtime4·staging1/7파일·전송/설치≤1·35분 상한. 정식 개발/확인 표본 전용 금지, 전체8세션 자동재수집 없음. ADB/설치/실측0.
- 다음: (1) PC 검증·plan_v2 결과 검토, (2) 별도 승인 후 현재기기 gate/단1세션 진단, (3) 결과에 따라 정식 수집 준비 여부 판단. 상세 검증 대상/결과는 보고서·verification.json. 아래는 과거 이력이다.


## 2026-09-25 ENERGY-THERMAL-COLLECT-03 — sampler 예외로 중단·재개 금지

- 시작ffe2d32/clean, 승인된 plan_v5 실행1회. [결과·재현](ENERGY_THERMAL_COLLECT03_RESULTS_20260925.md). 동일설치본 확인으로 전송/설치0. 개발1시도/0완료/1실패/3미시도, 확인4미시도. runtime4/warmup8/적격성2·작업645시작644해제, host inference654시작/성공 기록. 원 receipt 보수적 불확실성 상한 보존.
- 앱 sampler `NoSuchElementException`→stop. 화면23/23성공(최대0.719초), 화면timeout 아님. ConcurrentHashMap snapshot 변환 경쟁은 코드상 후보이며 stack 부재로 정확한 행 미확정. app_cleanup 기록은 있으나 failed, hostcleanup/프로세스부재 확인. claim→마지막cleanup279.631초, retry0/stopped_no_resume.
- 부분 baseline139.089J/부하prefix191.764J(추가74.340J)는 조건부mA·미완료 관측. 동일작업량/480초/냉각/병행 비교 불가, 동결/확인 없음. 기존 FAIL/원본/40값/20null/experiment_ready=false 유지.
- 다음: (1) PC snapshot 경쟁 재현·stack 보존 검토, (2) 근거 있는 최소 수정·관련 검증. 추가 실측/새 계획 자동실행 없음. 근거 외부 run_v3·analysis_v3·registry stopped. 아래는 이전 이력이다.

## 2026-09-25 ENERGY-THERMAL-COLLECTION-REPREP-03 — PC 준비 완료·실행 승인 대기

- 시작bfd8594/clean. [새 계약·명령](ENERGY_THERMAL_COLLECTION_REPREP_20260925.md). 실제 수집기와 진단의 공통 화면필터 연결/bytes 경계 확인. 실제 원문 fixture6사례와 관련24테스트·서명APK 재사용·새 plan_v5/Check 통과. Android/빌드/ADB/실측/설정변경0.
- 새 COLLECT-03/run_v3/registry·UUID 분리, 구 계획과 비교군/작업량/순서/기준/timeout 동일. 개발4→동결→확인4, 진단6976·warmup64·추론7040·runtime32, staging8/56파일, 전송/설치≤1·retry0. 고정104분/timeout 합산예약206분40초/hard220분. 정상시간·배터리완주 미확인.
- 새 개발/확인 모두 필터 관측, 옛547KB 부분세션과 결합 금지. 무추론76B/32회 성공은 부하안정성/과거원인해결/내부생성비용감소 근거 아님. 기존 stopped/FAIL/부분에너지 한계/40값/20null/experiment_ready=false 유지.
- 다음: (1) 새 후보 실행 승인, (2) 실행 직전 동일기기·설치본·환경 gate, (3) 통과 시 계약대로1계획 수행·실패 시 회수/cleanup 후 중단. 현재 run/claim 없음. 아래는 과거 이력이다.


## 2026-09-25 ENERGY-SCREEN-OBSERVE-02 — 무추론32조회 완료

- 시작4c08a79/clean. 사용자 새승인·새ID/plan_v2, 실제기록 bytes→실제환경parser PC 재생 후 실행. [결과](ENERGY_SCREEN_OBSERVE_02_20260925.md).32/32성공·335.297초/480초, 중앙0.578초/최대0.828초·각76bytes·exit0/marker0/두상태확인. 설치/앱/추론/설정변경/재시도0, client정리 확인.
- 동일A24·비충전88~89%·29.1~29.2°C/thermal0·첫마지막화면설정일치. 기존10테스트 재실행 없이 실기록parser경계·새plan/source/Check 검증. 무추론필터동작만 확인, 부하안정성·과거원인해결·내부dumpsys비용감소/에너지보정 아님. 기존종료계획/FAIL/부분에너지/40값/20null/experiment_ready=false 보존.
- 다음: (1) 에너지 수집 재준비의 PC 검토, (2) 관측방식 변경/부하중미검증/자료결합 제한과 새 예산 검토. 추가 실측·전체8세션 자동실행 없음. 아래는 이전 기록이다.


## 2026-09-25 ENERGY-SCREEN-OBSERVE-01 — gate 코드 오류로 조회 전 종료

- 시작603db8e/clean. [계획·결과·수정](ENERGY_SCREEN_OBSERVE_20260925.md). 사용자 승인 별도1진단 claim, 동일A24/앱부재 확인 후 배터리 bytes→문자열 parser 형식오류로 중단. 화면조회0/32, 설치/앱/추론/설정변경/재시도0,3.141초/480초. 배터리원문90%/비충전29.2°C, thermal/화면gate 미확인. client 정리 확인, 계획stopped_no_resume.
- 원실행 runner/hash 보존, decode 한 줄 수정·실제parser 경계 회귀 포함PC10건 통과. 수정후 기기 재실행0. 초기PC9건의 환경mock이 오류를 놓쳤음을 기록. 필터 기기검증·지연통계·과거원인해결 근거는 확보하지 못했다.
- 다음: (1) 결과/수정본 검토, (2) 별도 승인 시 같은 무추론 진단의 새ID 고정. 이번/기존 종료계획 재개금지. 기존FAIL/부분에너지/동결값/experiment_ready=false 유지. 아래는 과거 이력이다.


## 2026-09-25 ENERGY-SCREEN-DIAG-PC-01 — PC 진단·최소 수정 완료

- 시작eed0852/clean. [원인·수정·후속 후보](ENERGY_SCREEN_DIAGNOSIS_PC_20260925.md). 화면조회32회 중31완료(중앙0.422초/최대0.687초),1timeout2.016초. 전체덤프 중앙547581bytes, 자체client overlap0. 기기/통신/디스크 지연 중 원인은 미구분, 화면꺼짐/GPU결함으로 단정하지 않는다.
- 새 에너지 전용 필터는 상태2행+producer종료표시만 전송, timeout2초/cadence/미확인중단 유지. spawn/wait 단계기록·JSON회수 오류 구분 보완. 관련PC24건/기존31완료 덤프 재생 통과. ADB·기기조회·실측·빌드0, 실기기 검증 아님. 기존 run_v2/registry stopped_no_resume, 호출범위/조건부125.4J·314.2J/40값/20null/FAIL·experiment_ready=false 보존.
- 다음 최대3개: (1) 무추론32조회·8분상한 후보 검토/별도 승인, (2) 승인 시 별도 스크립트/새 식별자 고정, (3) 한 번의 동작 확인 후 남은 부하 위험 판단. 전체8세션 재수집은 자동 제안/실행하지 않는다. 아래는 이전 이력이다.


## 2026-09-25 ENERGY-THERMAL-COLLECT-02 — 승인 실행 후 첫 개발 세션 중단, 재개 금지

- 시작6b1a743/clean. 시간 표현을 **timeout 합산 예약206분40초**로 정정(고정104/상한220분 불변). 사용자 승인 후 plan_v4 hash/서명/환경 gate 확인, 전송1·설치1 성공. [실행 보고서](ENERGY_THERMAL_COLLECTION_EXECUTION_20260925.md), [작은 공유 요약](results/energy_thermal_collection_execution_02/README.md).
- 개발1시도/0완료/실패1/미시도3, 확인4미시도. runtime4·warmup8·적격성2 반환, 작업745 lane해제/최소746시작. 진단 시작748~872/6976·총추론 시작756~880/7040, 미확인 구간 보존. 화면 dumpsys power2초timeout으로 중단, 재시도0. claim→cleanup463.109초. 앱cleanup 미확인/host 종료·프로세스부재 확인. 계획·registry stopped_no_resume.
- baseline125.427J/부분부하314.168J(조건부 mA 가설), 동일작업량 완료·공통480초·냉각·병행 비교 불가. 동결/확인/PC연결 없음. 기존 FAIL·부분 결과·40값/20null·experiment_ready=false 보존. 원본 energy_collection_run_v2, 분석 energy_collection_analysis_v1.
- 다음 최대3개: (1) 기존 host 화면 조회 시간/출력량 PC 분석, (2) 관측 경로 최소 보완 필요성 판단, (3) 필요시 별도 실행 계획/승인. 종료된 이번 계획은 자동 재개하지 않는다. 아래는 당시 준비 이력이다.


## 2026-09-25 ENERGY-THERMAL-COLLECTION-PREP-02 — 병행 포함 PC 준비 완료, 미실행

- 시작 `ff03641`/clean. [새 계약](ENERGY_THERMAL_COLLECTION_PREP_02_20260925.md), [계획·APK·명령·검증](results/energy_thermal_collection_prep_02/README.md). 두 배정(CC_DG/CG_DC)의 실제 동일 작업량 직렬/병행4조건, 개발4→동결→확인4로 재설계했다. 기존 단독8세션 후보는 미실행 이력으로 보존한다.
- 신규 긴 세션 Activity·연속 raw 전력/온도·실제 lane 해제·단계 arm/quality/memory/GPU gate·bounded 회수/cleanup·단일소비 registry 구현. Python17/Kotlin6·관련 compile/APK 서명·최종 plan_v4 dry-run 통과. 최종 build_v5, 상세 외부 `energy_collection_pc_v2/FINAL_REPORT.md`. ADB/설치/실측0. 현재 설치본·새 병행 지원은 기기 gate 미확인이다.
- **새 미승인 예산:** 8세션/진단6976(작업6960+적격성16)/warmup64/총추론7040/runtime32, APK전송·설치 각≤1, retry/대체/추가0. 고정관측104분, timeout 합산 예약시간206분40초, 회수·cleanup 포함 상한220분. 실행 root/registry 미생성. 기존20null·40값·FAIL·부분 결과·종료 계획·experiment_ready=false 보존, S26/NPU 별도 유지.
- 다음 최대3개: (1) 새220분 예산 실행 승인, (2) 현재 A24/설치본/환경과 단계별 병행 적격성 gate, (3) 승인 범위 개발→동결→확인 후 적격성과 오차 판독. 임의 offset/duty·정책 우월성·절대 에너지 정확도는 이 준비로 검증되지 않는다. 아래는 과거 시점 기록이다.

## 2026-09-25 ENERGY-THERMAL-PC-01 — 기존 자료 보정·PC 구현 완료

- 시작 `38d5959`/clean, 원격 일치. **발열·배터리 최적화는 필수 목표**이며 동일 작업량·품질·응답/완료 제약을 함께 평가한다. 일시정지 Android 연결은 현재 우선순위에서 보류한다. [결과·계약](ENERGY_THERMAL_PC_01_20260925.md), [공유 CSV/그림/검증](results/energy_thermal_pc_01/README.md).
- A24/S26 MobileNet 각80세션을 비파괴 추출했다. A24 raw mA, S26 raw μA가 유력하지만 절대 에너지 정확도는 미인증이다. 상태별 에너지·완료량당 에너지·센서별1차 열모형과 사후 내부 확인을 구현했다. A2450/128·S26118/128 모형만 식별성 점검 충족; 정확도 PASS가 아니다.
- 새 `energy-thermal-pc-v1`: 기존 엔진 불변 ledger 연결, 에너지/연속 온도/잔열/미완료 분모·지원 범위 검사. 관련18테스트·실제 대표2세션 적분 보존·legacy2재생·합성1연결 완료. ADB/설치/실측/정책 최적화/전체 기존 배치0. 상세 원본·모형은 외부 `energy_thermal_pc_v2`, 실패한 v1도 보존.
- 현재 두 모델의 resident 전력·열·병행은 실측 기반 모드에서 미지원이다. 가정 모드는 명시적 입력만 허용한다. 기존 FAIL·부분 결과·40동결값·20null·종료 계획·`experiment_ready=false` 불변. S26/NPU 협업 유지, 기기 간 계수 전용 금지.
- 다음 최대3개: (1) [4단독 경로 수집 후보](ENERGY_THERMAL_COLLECTION_PROPOSAL_20260925.md)의 logger/긴 세션 별도 경로 PC 준비, (2) 품질·시간/단위 적격성 및 새 manifest 동결, (3) 별도 승인 후 개발4→동결→확인4. 후보8세션/3,480요청/64warmup, 예상102분·상한127분은 **미승인·기기 실행 준비 미완료**다. 아래는 과거 시점 이력이다.

## 2026-09-25 REPLAN-PC-01 — 별도 후속 PC 구현 완료, 실기기 미실행

- 시작 `c0524cb`/clean. [후속 계약·재현 명령](REPLAN_PC_01_20260925.md). 사용자 승인으로 조작 기반 배경 시작 제한과 요청 우선순위·정적 배정의 비교를 **별도 후속 개발**로 착수했다. 기존 목적/FAIL을 소급 변경하지 않는다. 인터뷰는 필수 gate가 아니다.
- 새 `arrival-interaction-pc-v1`: 독립 조작 입력·15초 기본 유휴 타이머·세대별 만료·normal dispatch 직전 재검사·배정 취소/큐 보존·공통 drain/배경 persist 완료 지표 구현. 양 비교군에 같은 관측/정렬을 적용하고 정적 개발 승자를 교차 구성할 수 있다. 기존 P·Android 정책은 변경하지 않았다.
- 관련 PC38건(새23+기존 엔진15) 통과, 실제 CLI의 합성3trace 수작업 시각 일치. [검증 기록](results/replan_pc_01_20260925/README.md)에 소스 hash·대상 HEAD·실행 명령과 한계. 성능 순위·실기기 PASS가 아니며 기존960배치/전체 빌드/ADB/설치/추론은 실행하지 않았다.
- 다음 최대3개: (1) Android dispatch 소유권에 새 gate를 연결하는 별도 개발, (2) 동일 개발 예산의 정적 후보·지원 조합/입력·trace/drain과 새 실측 예산 산정, (3) 승인과 필수 gate 후 한 번의 개발→동결→평가. 이번에 새 실측 예산·margin·표본수·새 P는 확정하지 않았다.
- 미완료: Android 조작 timer/실제 배정, 선정B2 분류GPU+탐지CPU 병행, 새 역할·부하 전이/정확도·UI 계측. S26/NPU 별도 채택 유지. 기존 FAIL·부분 결과·40동결값·20null·종료 계획·`experiment_ready=false` 보존. 아래는 당시 이력이다.

## 2026-09-25 DIRECTION-REVIEW-01 완료 — B 제한적 재정의 권고, 미채택

- 시작 `c8b4e30`/clean. [프로젝트 방향 근거 검토](PROJECT_DIRECTION_REVIEW_20260925.md)에 PLAN–구현–증거 대응, P 손실의 원인 분류, Band 등 공식 자료와 세 방향 비교를 정리했다. 기존 보고서·설정·trace를 재사용했으며 코드/설정 변경·테스트·재생·배치·ADB·실측은 하지 않았다.
- **권고 B:** 현재 P 개발을 보류하고 서비스 제약 아래 단순/적응형 정책의 적용 조건으로 좁혀 정리한다. 현재 P의 추가 이득은 미확보이며, 이 결과가 원래 PLAN P 전체를 기각하지도 않는다. 예측 간섭계수1.5는 개발 전 탐색 가정으로 실측 보정값이 아니다. 실제 서비스 필요성과 현실 예측 검증은 여전히 부족하다.
- 다음 한 가지: 기존 사진 정리 과업의 실제 담당자와 최대30분 근거 검토를 제안한다. 두 작업의 겹침과 단순 처리로 남는 구체적 불편을 확인하지 못하면 추가 정책 개발을 종료하고 전환을 권고한다. 이번에 면담·실측을 실행한 것은 아니다. **δ 확정은 요구하지 않으며 전체 민감도 결과를 유지한다.**
- 목표/채택 결정은 사용자 선택 전 변경하지 않는다. 기존 FAIL·부분 결과·40동결값·20null·종료 계획·`experiment_ready=false` 보존. 문서 링크·diff·문서만 변경됐는지 확인한 뒤 관련 문서만 commit/push한다. 아래의 다음 행동은 각 당시 이력이다.

## 2026-09-25 ARRIVAL-DELTA-SELECTION-01 완료 — 기존 CSV만 사용

- 시작 `b7a4695`/clean. [일반 서비스 허용폭에 따른 정책 선택](ARRIVAL_DELTA_SELECTION_20260925.md), [정확 경계·CSV·계단형 그림](results/arrival_delta_selection_20260925/README.md). CPU 긴급우선 대비 일반 위반 증가δ 제약 아래 긴급P95만 최소화했다. 이전 일반평균 제약/긴급위반 우선순위는 적용하지 않는다. 사후 oracle 참고이며 배포 정책/새 평가가 아니다.
- δ0에서 B2 단독9조건·CPU 단독2조건·low 4자 동률. P는 어느δ에서도 단독 선택되지 않는다. 전체조건 고정 적용은 δ<40/9%p에서CPU만 적격; 이후B2, 140/9부터B3, 220/9부터P, 50부터고정분리 진입. 최악 긴급값은CPU830.361ms가 최저이나 minimax 목적/시나리오 가중치를 채택하지 않았다.
- 신규PC4테스트(정확경계·동률·미완료분모·δ0) 통과, PNG/링크/diff 확인. 입력·설정·코드hash와시점은결과폴더VERIFICATION/receipt. 기존원본·동결값·FAIL·부분결과·종료계획·experiment_ready=false 유지. ADB/실측/P튜닝/B2재선정/시뮬레이션 재생/전체 배치 모두0.
- 다음: (1) 실제 일반 위반 증가 허용폭과 모든 조건 동일 적용 여부 결정, (2) 그 목적 아래 강한 정적 기준/CPU 중심으로 정리. 현재 P는 재현·제거 비교용 보존을 권고하며 추가개발 근거는 부족하다. δ0도 최종 서비스 기준으로 채택하지 않는다. 아래는 당시 이력이다.

## 2026-09-25 ARRIVAL-SERVICE-REVIEW-01 완료 — 추가 실측 없음

- 시작 `7402a0a`/clean·원격 일치. [한국어 서비스 비교·권고](ARRIVAL_SERVICE_COMPARISON_20260925.md), [조건별 표·CSV·그림](results/arrival_service_review_20260925/README.md). 기존960행 재집계와 누락된 대표 trace3개만 PC 재생했고 원 지표와 일치했다. B2 평가별 재선정·P 튜닝·전체 배치·ADB·추가 실측 없음.
- 기본 큐 B2 긴급425.89ms/일반4138.67ms, P1014.02/4150.55ms. 그러나 일반 위반 B2 20/90·P17/90으로 상충한다. 12조건의 긴급/일반 지연+위반율에서는 B2 표본 우세5·P1·상충6이다. P의 간섭 가정에 따른 대기·일반 요청 배정이 손실을 설명하며 보편적 지배/실기기 우월성 증거는 아니다.
- 후처리 신규5테스트·대표3재생 일치·PNG/링크/diff 확인. 새 후처리 v1 제거군 이름만 v2에서 수정; 수치·시뮬레이터·기존 결과 불변. 원본은 외부 `arrival_explore_batch_v3`, 새 분석은 `arrival_service_review_v2`(v1 보존). 검증 버전/hash는 결과 묶음 VERIFICATION 참조.
- 배터리 **시작20%**는 사용자 원문으로 승인 확인. 실행 중30→20 변경의 별도 명시적 승인은 미확인(당시 구현 해석). 실제 시작52%는 종전55% 미달, 세션별 관측51%는 종전 실행 중30% 이상. 연속 준수·원래 계획 완주로 확대하지 않는다.
- 다음 최대3개: (1) CPU 긴급우선 대비 일반 기한 위반 증가 허용 여부를 먼저 합의, (2) 강한 정적 기준 중심의 제한적 서비스 선택 문제로 정리할지 결정, (3) 고정 규칙의 부족이 입증될 때만 적응형 개발을 재검토. 권고이며 목표/margin 채택 아님. 현재 P 튜닝·추가 실측은 보류한다.
- 기존 FAIL·부분 결과·동결40값·20null·종료계획·과거 원인 미확정·`experiment_ready=false` 유지. Android B3/P·선정 B2 역방향 병행·정확도/평가 예산/기존 시스템 비교 미충족. 아래 항목은 당시 이력이다.

## 2026-09-25 CONFIRM-FOLLOWUP-01 완료·PC 탐색 비교 완료

- 시작 `983d3b2`/clean. [결과·재현 명령](ARRIVAL_FOLLOWUP_AND_EXPLORATION_20260925.md). 승인된 새 확인1계획을 1회 실행했다. 사용자 후속 지시로 배터리 하한20%만 실행 전 v4에 고정; 나머지 조건 불변. 현재 동일 A24/정확한 설치 APK·서명, 시작52%/32.5°C/비충전·thermal0·화면·memory gate 통과. 설치/서버 재시작/재연결/설정 변경0.
- **3시도/3완료/실패0·미시도0, 진단12/warmup24/명시적36, retry·대체·추가0.** runner492.687초/사전 연결 확인→cleanup561.360초(냉각360초 포함). 앱·host cleanup3/3, 프로세스 부재 확인. 원래 부분 계획은 계속 종료 상태이며 이번 자료로 완주 처리하지 않는다. 조건당 독립1세션; F host API overlap2쌍·후속 lane 재사용8쌍 확인.
- 완료 후 PC 요약의 기존6조건 검사 오류를 발견해 후속3조건만 분리 수정했다. 원 완료 receipt/로그 보존·실측 재실행 없음. 새 관측 bridge는 정확한 기록 재생/조건별 비용 조회만 연결하며 임의 병행·새 adaptive GPU는 차단한다.
- PC 엔진/8정책·개발B2선정/별도 평가 시나리오/미래정보 분리/UNKNOWN_OVERRUN/실제 lane 해제 구현. 관련21테스트 통과. 최종 탐색은 개발126+평가960실행(23,040가상요청), 실기기 세션과 별개. [공유 숫자 입력·CSV·PNG/SVG](results/arrival_explore_20260925/README.md). v1/v2 결함·결과 보존 후 v3 정정; 새 독립 기기 검증 아님.
- 기본 큐 가정에서 P−B3 paired 긴급−4.11%/일반+3.14%; P−B2 긴급+138.03%. 간섭없음/urgent비중증가에서는 긴급+45.85/+40.58% 손해. P 우월성 근거 없음. strict B3/P는 동일 CPU fallback이고 explore B2의 분류GPU+탐지CPU 병행은 실측 미지원이다. 기존FAIL·40값/20null·experiment_ready=false 유지.
- 외부 root: `confirmation_followup_execution_v1`(receipt/분석/검증), `confirmation_followup_run_v1`(원본), `confirmation_followup_bridge_v1`, `arrival_explore_batch_v3`, `policy_evaluation_pc_preparation_v1`. 마지막 것은 PC gate 준비이며 기기 실행 명령/승인 예산이 아니다.
- 다음 최대3개: (1) 일반 서비스 목적·허용손실을 정하고 강한 정적 기준 검토, (2) 필요성이 확인될 때만 Android B3/P와 미측정 병행 조합 개발 gate 해소, (3) 그 이후 별도 독립 평가 설계·예산 승인. 추가 실측/소비 계획 재개 없음. 아래 기록은 당시 이력이다.

## 2026-09-25 CONFIRM-FOLLOWUP-01 PC 준비 완료 — 실행 미승인

- 시작 `fefe913`/clean. [ADB 분석·확인 전용 계약](ARRIVAL_CONFIRMATION_FOLLOWUP_20260925.md). 실패는PC127.0.0.1:5037 접속오류이며daemon내부원인미확정. 과거수집경로에는server종료/taskkill없고복구경로timeout도없었다. 현재PATH의ADB1경로/SDK37.0.1·PID2388/listener를OS조회했으나과거상태로전용하지않는다. adb.log는실패시각을포함하지않는다.
- 새host는기존server smart socket 준비조회·raw stdout/stderr/명령intent/clientPID/종료대상·OS실패snapshot을기록한다. timeout은해당client만종료, explicitserver재시작/retry없음. client내부race가능성과계측부담을명시했다. 공용수집runner에별도후속branch만추가하고기존Android/APK는보존·재빌드없음.
- **제안3세션(B 고정CPU단독→A activeCPU단독→F 병행), 진단12/warmup24/runtime12/총추론36/설치0/retry·대체·추가0, 예상9~15분·상한30분(작업1755+cleanup45초, 냉각6분포함).** 기존개발6/동결e4cb73aa…83023과이전확인E/D/C의3세션을그대로보존한다. 새계획은별도선택적후속확인, 원계획완주·동일날짜paired비교로합치지않는다.
- 신규13건+직접관련기존7건PC통과/최종script Check·APK서명·manifest·불변동결검사통과. ADB명령/서버접속/기기실행/설치/추론0, 원본변경0. 외부 `confirmation_followup_plan_v3`(plan SHA3de26b4e…e4bb3/manifest3/실행script), `confirmation_followup_pc_v1`(원인증거/최종source/VERIFICATION_FINAL/tests_v3/regression/보고서). v1/v2는미실행초안이다. 새출력/registry미생성.
- 다음: (1) 새확인전용예산승인, (2) 승인후정확한설치본·현재server/device/environment gate, (3) 통과시누락3조건만실행·동결대비오차기술. 기존계획/실패분모재개·삭제없음. 성공해도임의병행허용·정책PASS·experiment_ready=true로자동전환하지않는다. 기존FAIL/부분결과/40값/20null유지.

## 2026-09-25 RECOVERY-02 / COLLECT-03 종료 — 설치 성공·확인 중 ADB daemon 오류

- 시작 `3a88ca8`/clean. 별도 승인 v2 준비·PC14건/dry-run 후1회 실행. [새 계약·종료 결과](ARRIVAL_INSTALL_RECOVERY_20260924.md). APK/설계/기준/timeout 불변, host namespace·v1 종료 증거 hash 연결만 변경. 재빌드 없음. 전송1/설치1 성공·정확한 후보설치본 확인·복구cleanup 완료(79.453초). 이 설치 계보 누적2시도(COLLECT-01 timeout1+RECOVERY-01 0+이번1).
- **개발6/6 완료→동결, 확인4시도/3완료/앱실행전실패1/미시도2. 전체10시도·9완료, 진단36/48·warmup72/96·명시적108/144, retry/대체/추가0.** 실패는 확인index9 labels staging push의 PC ADB daemon `127.0.0.1:5037` 접속 실패/Windows10060. Activity 미진입이므로 해당 호출0; 과거 불명 호출수는 변경하지 않는다. 원인·개발자옵션과의 관계는 미확정.
- 정상9세션 앱/hostcleanup 확인, 실패시도 부분회수 output_missing·host증거 회수·cleanup/프로세스부재 확인. workflow1675.625초, 실행직전 marker→cleanup1677.534초(27.959분), 냉각20분 포함/상한101.5분 이내. 설정변경0, 종료후ADB0, `stopped_no_resume` 유지·재개금지.
- 개발동결SHA `e4cb73aa…83023`을 확인claim에 고정, 재보정 없음. 확인3/6만 확보; 탐지GPU S→O 중앙값 오차는 완료2조건에서+38.632/+79.972ms. 개발병행의 탐지GPU S→O 차이+76.520ms는 인과간섭 계수가 아니다. active/병행 확인 미실행·수치정확도 기준없음 때문에 PC설정 연결/병행해제 없음. 기존40값/20null/FAIL/부분결과·experiment_ready=false 유지.
- 외부 `collection_recovery_execution_v2/FINAL_REPORT.md`, FINAL_RECEIPT/ANALYSIS/REPRODUCE_ANALYSIS.py에 전체분모·부분통계·명령/시간·한계, `install_recovery_pc_v2`에14검증/source snapshot을 보존. 원본은 `install_recovery_run_v2`, `integrated_collection_run_v3`, `collection_recovery_workflow_v2`. 원본/동결/선행hash 및PC분석 재현 일치.
- 다음: PC에서5037 daemon 실패와 staging 증거 보존을 점검한다. 새 기기 실행/종료계획 재개 없음. B2 사전선정 목적·제약, B3/P 실제결정차이와 독립평가 요건은 여전히 남는다. 관련 소스/문서만commit·정상push하며 최종Git은 외부GIT_FINAL.json을 따른다.

## 2026-09-25 개발자 옵션 재활성화 후 읽기 전용 gate 확인

- 시작 `3e57107`/clean. 개발자 옵션 재활성화는 사용자 보고이며 정확한 변경 시각은 미확인이다. 현재 `development_settings_enabled=1`, `adb_wifi_enabled=1`과 단일 온라인 A24(`R59W802RW5F`, SM-A245N), 계약 fingerprint 일치를 직접 확인했다. 과거 timeout 원인 해결로 해석하지 않는다.
- 01:52~01:54 KST 조회: 배터리58%/33.9°C/비충전, thermal0, Awake/interactive, 밝기81/수동/timeout18,000,000ms 일치. 앱 프로세스 없음. host 메모리 normal/Free RAM1,217,575KiB이며 **앱 내부 low_memory/runtime admission은 앱 미실행으로 미검증**이다. 시점 관측이므로 지속 유지 또는 실행 직전 gate를 대체하지 않는다.
- 설치본 SHA `9019b85d…2c0`는 이전 apksigner 검증 APK bytes와 같고 후보 `d8db6963…34bc`와 다르다. 현재 해시를 보존된 서명 근거에 연결했으며 새 APK 회수/서명 검사를 반복하지 않았다.
- COLLECT-01의 plan v1/v2는 같은 소비 registry로 종료 상태다. INSTALL-RECOVERY-01/workflow도 `stopped_no_resume`; COLLECT-02는 12세션 미시도지만 필수 recovery receipt가 failed이므로 실행 불가다. 별도 미시작 실행 가능 bundle은 없다. **ADB 읽기 전용16명령, 새 claim/전송/설치/세션/warmup/추론0**, 설정 변경/force-stop/계획 재개 없음. 기존 원본·소비량·experiment_ready=false 보존.
- 근거: 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/developer_options_gate_check_20260925_015243/`의 context/plan_inventory/identity/query_index/commands/FINAL_RECEIPT. 다음은 종료 계획과 분리된 새 실행 계획 준비이며, 실행 전 환경·서명·미소비 gate를 다시 적용한다.

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
