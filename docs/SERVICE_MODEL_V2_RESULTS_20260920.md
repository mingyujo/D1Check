# SERVICE-MODEL-V2-DESIGN 결과

**BLOCKED_MISSING_TELEMETRY**, SIM-01_INCOMPLETE. 2026-09-20 시작2faeb8e/clean, 구현 checkpoint1cbdd1e. 새 ADB/실기기 측정/scheduling simulation/formal 없음. 최종 commit/clean은 외부git_final.json에 기록한다.

상세 보고서: `C:/Users/LG/Documents/D1Check_Service_Model_V2_Design/run_20260920T140424Z/FINAL_REPORT.md`. 같은root/artifacts에 consumed registry,559요청 trace, 별도host실패9요청,후보LOSO,상태전이/BIC,분포/F구간,표본수,개발모델,설계계약/no-op을 보존했다. 이전 raw2세션·시작전실패계획·74.57%오차/cold774.244ms·기존독립평가 실패도 보존한다.

## 모델 및 trace 결과

| 개발 후보 | MAE ms | WAPE | 지원율 |
| --- | ---: | ---: | ---: |
| A task/backend mean | 354.019 | 51.831% | 100% |
| B origin first/early/warm 후보 | 41.738 | 6.111% | 100% |
| C setup/active+context | 30.363 | 4.445% | 100% |
| D 전체 source-cell matrix | 30.455 | 4.459% | 100% |
| E session joint empirical | 29.447 | 4.311% | 100% |
| G pooled relative multiplier | 172.248 | 25.218% | 100% |

51세션/559요청 전체개발 LOSO이며 독립승인 아님. 최소선택은 C+E: 같은관측의 setup/active를 함께 보존하고 cell/origin/co-run 구성/priority 완료경계를 분리한다. D의추가복잡도 이득없음. B는co-run/완료경계 pooling을 남긴다. 현재context는 manifest구성이며 실제overlap/causal interference와 같지 않다. 새simulation에 연결할 완성된 multiworker sampler는 아니다.

분류CPU solo normal 호출1/2/3/4의 total 중앙은787.516/407.404/104.298/97.524ms, inference 중앙은35.050/34.599/34.693/35.306ms다. 호출별표본이달라 paired causal차이를 주장하지 않는다. 초기비용은 inference 외 active에도 있어 runtime setup만 분리해 해결되지 않는다. BIC tail-start가cell/trace별2~6호출에분산되고 전환3호출만으로tail 검증불가: ≥3은warm_candidate이며 warm자동승인금지.

F session-max split-conformal 개발평균session coverage99.183%지만 radius중앙4.005×point로매우넓다. 교환가능성/미지원score제외문제가있어 통계보장없고 높은coverage를성공으로승격하지않는다. Scheduler PI사용시90%/finite rank유지. Empirical simulator는mean/median/P95/Wasserstein/tail을주평가하되 목적연결margin은pending이다. 기존MAE/WAPE완화없음.

## 설계와 blocker

- task-profile-v3의prepare는close+create혼합. model preloading은request밖. process/activity·constructor/delegate/allocation/close·pre/post·worker-release span은없거나TaskProfile경로에서비활성이다. 최소v4 span연결설계와setup/span validator를작성했다.
- CPU-only도두runtime상주/동일warmup,globalpermit1; CPU/GPU는두상주/permit2. 동일arrival/mix/count/seed/deadline/thermal/background/output/회수와balancedAB/BA. 현재v3는runtime slot과동시성이결합돼공정대조불가. 기존n2 GPU효과는runtime재생성혼입,양쪽완료율100%.
- MemoryInfo/Javaheap/PSS동기화와추가runtime/pressure upper가필요. gate는fresh/thermal0/!lowMemory/available여유/Java여유/resident envelope 모두요구,미검증이면거부. sampled318364kB를절대최대라고하지않는다.
- 네cell PASS_EQ/A24 CPU-solo-dominant 유지. quality동등성≠accuracyGT,thermal0범위만,같은backend contention미승인,fallback금지. Deadline calibration_pending.
- 새holdout 표본계획:8family의정확binomial p0=.9,p1=.95,power.8,FWE.05는322/family(303성공),분포무관session coverage±5%동시bound는1154/family. 기존sessionCV기반mean5%근사최대624. 합동보수bound9232완료세션은최소요구/실행승인이아니다. Host2/23실패상한24.925%를proxy로쓰면기대완수1538시도/family. 연구일정에과도하며목적precision/동일프로토콜변동성/공정paired variance를새calibration에서확정한뒤새holdout전재산출·동결한다.

## 검증·hash·다음 행동

- 새unit30/관련targeted83 PASS. 전체unittest341(339 PASS·기존skip2), compileall/diff-check PASS. leak/consumed/stale/replay/immutability/seed/span/paired/memory/no-op포함.
- 두새root 생성의계약hash동일. no-op/dry-run device명령[],dispatch0,가상완료0. 전체검증은1cbdd1e clean에서수행했고validation.json에명령/시각/HEAD기록.
- Android source2faeb8e대비불변,debug/modelProbe/release APKhash기존값일치. JVM/build/lint재실행없음.
- 설계계약SHA `635087906dde3ff3c50fc034b350689207109d54970c721bf21a24bb432f0719`. 승인된simulation input hash는없다. 기존frozen transition_mean artifact/코드/기준은수정하지않았다.
- **다음 실기기 명령 발급불가:** v4 최소계측/residentCPU직렬gate를구현하고Android검증·새APKhash를고정하는것이먼저다. 기존runner로조건을충족한다고꾸미지않는다. 지금실행가능한명령은보고서의host dry-run이다. 새측정/simulation/formal은이번범위밖이다.
