# D1Check 현재 상태

## 2026-09-23 비동시 도착 확장 — 현재 작업

- `ARRIVAL-EXT-01`, 시작 HEAD `f2f559c03cd4146818dda232bf548d26afbe2af2` clean, 별도 브랜치 `feature/arrival-scheduling-20260923`. 기존 `SIMULATION_PLAN_READY`/freeze·30세션 원본·formal v1/v2는 보존. 이전 support 보고서는 본 simulation 실행 0을 기록하며 새 본 실행 결과는 확인되지 않았다.
- [새 계약·pilot](ARRIVAL_SCHEDULING_EXTENSION_20260923.md): 실제 분류/탐지 비동시 도착, CPU FIFO/긴급 우선/조건부 CPU-GPU(고정 분리 코드는 보조), 동일 4 resident runtime·CPU thread1·최대 동시2. 기존 v3/v4와 공식 inference timer는 변경하지 않음. 네 runtime 동시 상주의 A24 admission은 **미검증**.
- pilot manifest `C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_v2/pilot_plan.json` SHA `a3ba8ca0cf33c695d089b9ae548c851c8eea1adc6c9b8ca20900496f5746664e`: smoke1+paired18=19세션/130평가요청/152warmup, 전체 시도≤19·retry0. 원본 모델/이미지는 이전 검증 입력 경로에서 SHA 확인만 하고 재배포·커밋 안 함. 최종 새 APK SHA `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`, 첫 개발 draft v1 SHA `ace10ad4abb3f1f91a05e3639f39d005b3c615873e30555ba788f6b8399473d4` 미실행 보존, 기존 APK SHA `68e55aefdceb91e569e0d55ff0a18af0658163106589852325cb9ad5626fa62e` 별도 보관.
- PC 검증(2026-09-23 KST, 시작 HEAD `f2f559c` + 이 단계 미커밋 소스): `:benchmark-runner:compileModelProbeKotlin` PASS, `:benchmark-runner:testModelProbeUnitTest` PASS, 최종 v2 `:benchmark-runner:assembleModelProbe` PASS, 신규 Python unit3 PASS, compileall PASS, 실제 v2 19 manifest 생성/dry-run PASS(ADB0·모델호출0), A24 read-only preflight 지문 일치. 빌드 첫 시도는 SDK 경로 미설정으로 실패했고 환경변수 설정 후 통과했다. 종료 전 최종 diff-check·v2 dry-run 재확인 대상.
- **판정:** 설계·PC 구현/빌드 완료, 실기기 smoke·pilot 미실행, 독립 평가·새 본 시뮬레이션 미실행. blocker는 신규 확장 pilot **19세션 예산 승인**과 A24 네 runtime admission/실제 GPU 로그 확인이다. 이전 실측 예산은 신규 확장에 전용하지 않는다.
- 다음 행동(최대 3): (1) 최종 회귀·선택적 소스/문서 checkpoint commit, (2) 19세션 pilot 예산 승인 후 첫 smoke gate와 최대18 paired session, (3) pilot paired 변동성으로 평가값·세션 수 동결안을 만들고 별도 평가 승인을 요청.

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
