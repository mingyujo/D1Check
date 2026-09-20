# SERVICE-MODEL-FINAL-CALIB 결과

**SIM-01_INCOMPLETE.** 2026-09-20, 지정 feature 브랜치의4230160에서 시작해 신규 calibration4/holdout16/CPU-only control2세션을 실행했다. 계획22세션326요청 완료. 별도 host 실패 시도9요청을 포함해 실제23시도335개 기기요청을 보존한다. 본 simulation/formal은 실행하지 않았다.

외부 최종 보고서: `C:/Users/LG/Documents/D1Check_Service_Model_Final/run_20260920T130139Z/FINAL_REPORT.md`. 같은 root에 원시 session, 모든 명령/실패/회수 기록, frozen contract, 개별 model/input/criteria, split, request/session 평가, memory/thermal, schema 검증/no-op, 재현 script가 있다.

## 사전 동결과 결과

- 계획 `5544995`, 동결 `b5928e8`. 동결 시각2026-09-20T13:11:32.713690Z, [committed hash](SERVICE_MODEL_FINAL_FREEZE_20260920.json). 기존cal24+신규4만 사용했고 과거holdout·진단은 fitting에서 제외했다.
- 선택 `transition_mean`: cold/초기직후/warm/CPU↔GPU 전환을 구분한16개 cell-state 그룹. 기존6후보를 calibration LOSO로 비교하고 support·단순성을 우선했다. co-run 파라미터는 pooling하며 평가에서는 별도 층이다.
- 기존 기준 유지: MAE432.808616ms, WAPE/mean·median·P95 상대오차43.191436%, coverage90%, 지원율100%. PI는 calibration empirical Q05..Q95. 사후 변경 없음.
- calibration LOSO coverage80.65% 실패도 동결 전에 기록했다. 독립 holdout16세션/260요청: MAE39.070581ms, WAPE6.102956%, coverage80.384615%. 전체 MAE/WAPE는 기준 이내지만 coverage·세션/상태/분포 기준을 실패했다. 세션 평균 WAPE8.740222%, coverage77.383207%다.
- 분류CPU cold/early-after-cold coverage50%/50%, warm96.15%. early-after-transition은 중앙103.262ms인데 cold직후 중앙494.315ms와 같은 초기직후 모델로 묶여 WAPE250.07%다. origin 분리가 필요한지 새 개발 단계에서 검토할 사후 근거이며 이 결과로 이번 후보를 다시 fitting하지 않았다.
- 기존 두 번째381.316923ms/74.57% 오차와 cold774.244ms를 삭제하지 않았다. 신규cal 첫768.65/두 번째525.46/세 번째103.39ms도 보존했다.

## GPU·환경·품질의 경계

새 solo warm CPU/GPU 평균: 분류97.36/249.89ms, 탐지558.01/1063.06ms. 네 cell 모두 PASS_EQ와 requested/actual 검증을 유지한다. A24 CPU-solo-dominant이며 GPU가 모든 조건에서 지배당한다는 결론은 아니다.

CPU urgent+GPU normal과 CPU-only 직렬은 각각 두 session에서 같은12요청·task mix·arrival·sample·priority·seed·deadline 미설정·thermal0/29.2°C를 비교했다. urgent P95는 co-run1869/2096ms, CPU직렬2737/2919ms이고 둘 다 완료율100%다. 하지만 CPU직렬은 한 runtime을 작업마다 재생성하고 co-run은 두 runtime을 유지한다. 따라서 이 관측을 최적 warm CPU-only 대비 GPU 우월성으로 해석할 수 없다. 전체/30초 이후 burst의 P50/P95·normal완료·makespan·throughput·memory는 외부 비교 JSON에 있다.

신규 sampled peak PSS318,364kB, 기존314,184kB 모두500ms 표본이며 true peak가 아니다. 후보 guard340,066kB/headroom25,882kB를 사후 상향하지 않았다. 새 관측 peak와guard차21,702kB는 검증된 안전 headroom이 아니다. Host MemAvailable도 수집했지만 순간 peak·압력 조건·admission 강제는 미검증이므로 memory constraint는 blocker다. Thermal status0만 적용한다. Deadline은 calibration_pending/null, 위반수도null이다.

Raw numerical·decoded equivalence·실제 accuracy·scheduling quality preservation을 분리한다. 같은20개검증image를 사용했으며 정확도 GT를 생성하지 않았다. 기존 raw/decoded 허용오차·같은 모델/전처리/decoder·fallback 금지를 유지했다. 기존 EfficientDet exact license/NOTICE 미확인·비배포 연구 제한도 유지한다.

## 산출물·오류·검증

- 모델 SHA `c29691f6fac993cd97054667e861e19232277009243c1e41c199fa6d33e6bd30`, input 후보 SHA `dfe3fa15b0ff84165bb8570ea0d19d39b5cd6757d5b618453da6acfc30acad19`. 독립평가용 동결이며 최종 승인 input은 없다.
- 첫 host 종료기록 변수 오류 시도는 원시9요청과 원래 SHA가 일치하는 runner archive를 보존하고 새 UUID로 대체했다. 탐지CPU holdout1세션의 ADB daemon 오류는 재연결1회 후 이미 완료된 artifact만 회수했다. 원래 host failure/context를 고치거나 Activity를 재실행하지 않았다. 실패2건을 별도 ledger로 보존한다.
- targeted74/전체Python311(309 PASS·기존skip2)/compileall PASS. Schema/validator, committed hash, frozen mutation·holdout leakage·stale/replay 거부, seed 재현성, no-op, git diff check를 검증했다. Android source/APK 불변으로 JVM/build/lint 재실행 없음.
- 새 세션은 모두 최대48요청/120초 bounded recipe. Project force-stop과 원격 APK hash를 마지막에 확인했다. 기존 artifact·데이터 삭제·uninstall/pm clear/reboot/다른 앱 접근·push/merge/rebase 없음.

다음은 새 버전에서 초기화 origin/co-run·PI를 calibration으로 검토하고, 메모리 admission 및 두 warm runtime을 유지하는 CPU직렬 대조를 준비하는 것이다. 이 holdout16개를 새 독립 검증으로 재사용하지 않는다. 새 모델·규칙을 먼저 고정한 뒤 새 untouched holdout으로만 재판정한다. 본 simulation/formal은 계속 금지한다.
