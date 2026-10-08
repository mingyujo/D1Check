# D1Check 결정 기록

## 2026-10-09 RESIDENT-AP-STRUCTURE-01 — 사후 장구간 후보 보존·일반 적용 미채택

- 확정: 사용자PC후속승인에따라β/τ30/부하전초기화·J고정,상태별가열4+기존비율지연gain1 후보하나/제약대조2를결과전에등록했다. 개발4LOSO는모두MAE/최대개선이나최고온도오차평균과과거29전이가악화했다. [근거](RESIDENT_AP_STRUCTURE_RESULTS_20261009.md). 가장좋은대조로주후보를바꾸지않고기본/RL/strict/experiment_ready=false유지.
- 별도후보는장구간사후계산컨텍스트에만명시opt-in,동일APK/입력·상태/시간/초기범위이외null이다. 이것은기기실행gate/정확도PASS/독립확인/물리계수인증이아니다. reader 표기수정은계수재학습과분리,기학습/실패출력을보존했다.
- 기존고정R/30초항은늦은유휴편차를설명못하지만물리원인이나새τ는미확정이다. 현자료의꼬리/C0 식별성부터판독하며같은B2 반복/새실측자동실행/원종료계획재개0.

## 2026-10-09 IE-THERMAL-LOAD-GATE-01 — 산업공학 작업량 검사를 대기 행동에 적용

- 확정: V3 개발이저부하AP를낮췄으나혼잡에서서비스/열이악화하여, 별도후속후보에 가용예상시간 대비 현재CPU전용작업량과 현재큐절대기한가능 검사를대기에만추가한다. 최근8관측간격/최소3요청은고정설계며SLA나미래도착보장이아니다. [설계/선정/예산](results/thermal_load_gate_01/README.md).
- 원V3/0.25·1초/대기0/실패/clock보존, 개발만재사용·새확인2seed동결·후행재선정0이다. 추가192환경/학습0·V3완료누적5,636/641 계승, 계수/기본/strict/experiment_ready=false·기기0 유지. 물리절감이나산업공학이론신규성으로승격0.
- 최종: 개발선택을새확인전에동결했으나새확인양기준비악화17/24·두seedAP부호차로미채택. Band대비서비스/J/P9524/24유지·열감소3/24·J/AP공동0, 낮은부하AP−0.0051vs+0.00253를모형오차보다확실한개선으로표현0. 고정5모형에서도첫seed부호민감/둘째감소방향유지·실제비용/기기효과미확정. 새168/누적5,804/641·원기준유지,후속예측/판단비용근거를정리하며추가학습/실측0이다.

## 2026-10-09 IE-THERMAL-SLACK-03 — 산업공학 기본 요소의 실제 선택 연결

- 확정: 최신 사용자 발전 지시를 EDD 후보·응답여유·CPU전용호환성·receding계획으로구현하고, 새열우선/AP감소·서비스/J비악화계약을분리한다. 이전공동J/AP목적·기본/원모형은바꾸지않는다. [대응/예산/선정](results/thermal_slack_v3/README.md).
- 누적0.25/1초대기두버전과동일후보대기0ablation만비교한다. 실제dispatch외credit회복0·새긴급도착재판단·모든실제lane점유와전체요청보존. 후보예측을실제서비스보장으로승격0. 개발선정은확인전동결·확인후재선정0, 새384환경/학습0·기존5,298/641차감·기기/계수적합0이다.
- 결과: 실제338·학습0·선택none확인전동결/확인미채택,0.25s J감소와AP증가/기한상충·1s서비스악화·대기0Band동일을보존한다. 개발근거로후속대기허용검사를별도코드/경로/새확인에추가했으며원실행재시작/criterion완화/계수변경0이다.

## 2026-10-09 RESIDENT-IDENTIFICATION-RUN-01 — AP 식별 실패로 확인 진행 차단 유지

- 확정: 사용자실측승인으로plan_v3 개발4 정상완료. 첫개발제외 AP fit의beta_boundary=true로사전계약에따라확인4 미시도/소비계획종료. power rank5/AP rank3은안정적물리식별/정확도PASS의대체가아니다. [실행·근거·한계](RESIDENT_IDENTIFICATION_RESULTS_20261009.md).
- 상한확대나결과후후보선택으로 gate를우회하지않는다. 첫heldout의J개선/AP악화를함께보존하고기본/RL/strict/experiment_ready=false유지. 새개발자료의AP 상태가열입력비율/고정30초잔열구조를PC에서판독하는것이후속이며자동새실측0.
- 종료후host소비요약은현재세션entry의cap에결합하는최소수정만수행했다. 원receipt의AP 원오류/후속회수·요약오류를지우지않고별도corrected 요약을제공한다. APK/기기 설정/센서/실측중코드변경0.

## 2026-10-09 IE-BUSY-ORACLE-01 — 빈 초기 상태와 busy 상태의 진단 분리

- 사용자 자율 진행 승인으로 기존 원장의 첫 실행 중/분류2·탐지2대기 시점을 선택한다. 결과 전 [계약](results/busy_oracle_01/README.md)과 입력·소스 hash를 동결한다. 전체 prefix를 원 엔진에서 재생하고 열 이력·lane 해제 경계를 보존한다.
- 나머지 대기·미래 요청은 제외되는 조건부 네 요청 문제이므로 전체 서비스량·제품 우위·독립 확인·온라인 최적성으로 확대하지 않는다. 원정책7개와 유한100ms/3s 오프라인 참고의 개선 여지를 비교하며 현재RL credit·원계수는 바꾸지 않는다. 추가80환경/학습0·기기0·기존소비5,255/641 보존이다.
- 판정: 공동J/AP개선0·BandJ는조건부낙관적하한과ns회계여유~4.13e−7J, 본진단으로학습량을추가하지않는다. J동률/AP감소4개선정일정의일반지연·credit밖대기·short문맥P95악화를공개한다. 온라인열분산/J비악화계약은후속후보이며목적/대기범위를몰래바꾸거나기본채택0. 실제43환경·성공42/630전량·실패1·누적5,298/641·학습/기기0이다.

## 2026-10-09 IE-MICRO-ORACLE-01 — 작은 문제부터 제약과 개선 여지 확인

- 사용자 진행 승인에 따라 기존 후보의 목적/예산을 바꾸지 않고 별도 [유한 최적 일정 비교](results/micro_oracle_01/README.md)를 먼저 수행한다. Band 일정을 포함한 사전 시작시각집합·모든CPU/GPU배정을 전수 확인하며 서비스/AP조건의J최소와J조건의AP최소를 분리한다. 일반평균 비악화는 추가진단 조건으로만표시한다.
- 현재RL의0.25s credit와 오프라인3s 격자대기는 별도공간이다. 미래를 아는 최적일정과 온라인 규칙의 우열을 합치지 않는다. 기존에소비한2trace의부분요청을독립평가로표시하지않으며 새학습/NPU/기기/계수적합/기본교체0이다. 새320환경·1h/저장5min, 기존5,055환경/641학습과모든실패/종료clock보존.
- 최종: 선언공간24조건의서비스/AP제약 최소J·J제약 최소AP가Band와동률·공동감소0이고원엔진24재생도비악화다. 전체trace/연속시간/온라인/폰최적성은미판정. CPU보호는함수동작확인/실제발동0으로압박조건부효과를미입증으로남긴다. 저장소이력의LLF·CPU병목·MPC존재를기록하며최근EDD/RL경로부재를전체저장소부재로표현하지않는다. 새200환경·누적5,255/641·기기/학습0, 다음busy/backlog 조건부작업은별도계약전미실행이다.

## 2026-10-08 IE-FOUR-CANDIDATES-02 — 추가 후보 범위와 공통 판정 고정

- 확정: 사용자 시작 승인에 따라 리스트·Rolling Horizon CP-SAT·masked PPO·Double DQN만 별도 PC 파일럿으로 추가한다. 산업공학 연구 사용과 우리 휴대폰 적용을 구분하며 제품 전체의 우월성을 주장하지 않는다. [근거·계약](results/ie_candidates_v2/README.md).
- 원 PPO의 BASE logit 가산점이 유지되는 구조는 보존하고 새 PPO에서만 제거한다. PPO/DDQN 목적은 Band/Triton 양쪽 대비 에너지 이득과 AP/완료/서비스/P95 비악화이며 공통 상태·후보·물리mask·64에피소드×3seed를 사용한다. 학습은 같아도 replay/target/계산량 차이를 공개한다.
- CP-SAT은1ms 계획과 측정 병행 에너지, 기존 정확한 열모형의 첫 행동 필터를 사용한다. 열모형을 정확히 CP-SAT에 넣었다거나 제한시간 FEASIBLE이 최적이라는 주장은 하지 않는다. 검증 선택 후 확인 고정·기존예산 차감·기기/NPU0·원모형/기본/strict/experiment_ready=false 유지.
- 최종판정: validation24 새적격0을확인전에동결했고final48도새정책미채택이다. 리스트공동감소3조건은독립1trace/3문맥이며정상기한·긴급P95를지켰지만일반평균약3.1초지연·전체서비스악화를동반한다. CP-SAT의응답/열 감소는J증가와상충하고RL은3seed서비스안정성을통과하지못했다. 수렴/일반RL실패/물리절감/제품전체우월성·자동기본교체로승격0. 실제1,422/학습416은기존예산에차감, 원자료/체크포인트보존.

## 2026-10-08 RESIDENT-IDENTIFICATION-PREP-02 — 모형 식별과 Arrival 전이 확인 경계 고정

- 확정: 현재범위는실측전PC 구현/서명APK/미승인계획준비다. 개발4회로유휴bias+4상태W/AP beta,k,g를식별하고제외예측·자료hash를동결한후확인4로진행한다. Arrival2회는실제요청경로의조건부비용전이만판독하며정책우열/B성공으로승격하지않는다. [근거·실행조건](RESIDENT_IDENTIFICATION_PREP_20261008.md).
- 실현가능성에맞춰종료tail90초와기존Arrival구간을사용했다. 초기91분구상/중간6800추론PC초안을최종93분/6376추론명세로대체했으며소비실패가아니다. 최종plan_v3 하나만실행후보다. 소스변경이APK/계측비용에미치는차이와원모형/프로토콜구분을유지한다.
- 새실측승인·자동재연결·timeout완화·기준변경·원계수재보정·기본/RL/strict 교체없음. experiment_ready=false/원자료/FAIL/종료계획·사용자/다른작업을보존한다. 모형개선효과는새실측전미판정이다.

## 2026-10-08 CPU-GPU-METHOD-PILOT-01 — 검토 범위의 Band 요청 적용 기준 선정

- 확정범위: 검증12조건에서고정한`BAND_HEFT_WHOLE_REQUEST_ADAPT_V1`이확인24조건에서공용EFT/Band대비서비스·J/AP비악화를유지해이번PC후보중선정한다. 실제Band제품전체·전역최적·폰물리절감은미확정이며앱기본/strict는교체하지않는다. [선정근거](results/cpu_gpu_method_01/README.md).
- 현재C의AP우선계약은보존, E는같은maskedPPO에서물리mask와`ENERGY_AP_NONWORSE_V1` 목적을별도등록했다. 알고리즘비교로해석0. C/E각3seed×32·동일예산의모든확인원장이EDD와동일하여새RL/D미채택, 수렴/일반RL실패판정0. 미유망RL에추가구성제거/대규모학습을자동추가하지않는다.
- 실패C schema KeyError는원기본행동을그대로기록하는wrapper로수정하고원소스/partial batch/RNG/실패/clock을보존했다. 성공fixture32+실패1 포함225학습을기존6144에차감,717환경을누적3633/20000에차감했다. 기기/NPU0·원모형/기본/experiment_ready=false 유지. 별도2032등록은미실행준비로보존한다.


## 2026-10-08 PRELOAD-DYNAMICS-REFINEMENT-01 — AP 초기화 후보 별도 보존·일반 채택 보류

- 확정: 목표는정책판독이아닌에너지/AP 예측오차보완이다. 원beta/k/g0/상태계수/잠재30초를유지한AP 첫표본고정해제와사전전력추세의두구조를사전에제한하고개발/평가를분리했다. [근거](PRELOAD_DYNAMICS_REFINEMENT_RESULTS_20261008.md).
- AP 지속8/최근14 평균개선은사후평가근거이며새확인악화와개발기준실패를이유로기본채택하지않는다. 선택적API만별도보존한다. 전력후보는평균악화로제외하며전력개선·정책효과로포장하지않는다.
- 원모형/기본/RL/strict/experiment_ready=false·원자료/FAIL/소비계획을보존한다. 추가강도/범위/합격선변경·새실측/claim·다른EDD작업수정0. 단순첫값고정이유휴/잔열오차전체원인이라는판정도하지않는다.

## 2026-10-08 POLICY-COEFFICIENT-SENSITIVITY-01 — 설정 내 방향과 실제 절감 구분

- 확정: 원모형＋이미적합된개발변형4의짝지은계수민감도를기한/서비스guard뒤선택적으로표시한다. 변형4는미채택stress probe이며범위를확률구간/보편오차한도로쓰지않고기본/RL에자동적용하지않는다. [근거](POLICY_COEFFICIENT_SENSITIVITY_RESULTS_20261008.md).
- 첫seed주6조건의R2/EDD 대Triton J/최고AP방향유지는제한적모형결과이며강한공용EFT/Band대비공동개선이아니다. 원기본/RL/strict/experiment_ready=false유지. AP면적구현수정은기존KPI정의복구이며결과후목적함수/합격선변경없음.
- 후속권고는별도EDD/RL 시험일정의같은판독이며신규학습/정책선정/기기승인/소비claim을만들지않는다. 진행중작업·사용자/원자료/실패/소비계획보존.

## 2026-10-08 JOINT-REFIT-01 — 공동 개발자료 후보 일반 채택 보류

- 확정: 기존3+이력6 개발자료로한구조의계수를추정하고세묶음제외선택과이미본평가20을구분한다. APK·준비이력차이로전이후보이며strict확대로처리하지않는다. [근거](JOINT_MODEL_REFINEMENT_RESULTS_20261008.md).
- 판정: 개발에너지/AP 기준실패,최근14 J평균의약1.06%감소에도AP/지속정책차이악화로기본채택0. 원모형/기본/RL/experiment_ready=false유지. 순차관측80초짝차이개선은미실행정책120초비용예측의개선으로승격하지않는다.
- 신규실측승인·후보재튜닝·정확도PASS·정책우월성·다른EDD방향변경없음. 다음선택적PC판독권고와미식별정보를구분해보고하며원본/FAIL/소비계획보존.

## 2026-10-08 ENERGY-MEMORY30-01 — 30초 잔차 후보를 기본으로 채택하지 않음

- 상태: 개발/평가 분리와 기본 보존 확정. 고정 30초 평균 후보 하나를 개발 전용 alpha 0.518654로 동결해 확인 6·지속 8세션에 사후 평가했다. 확인 개별 MAE 0.870→0.848J 개선과 지속 0.844→0.854J 악화를 함께 보존한다. [근거·교차 기준](POWER_RESIDUAL_STRUCTURE_RESULTS_20261008.md).
- 회복 이력 교차평가에서 개별 오차 비악화 조건을 충족하지 못했으므로 selected_alpha=0으로 원모형을 유지한다. 합산 80초 순오차 감소만으로 후보를 채택하거나 전체 120초/정책 우월성/센서 정확도/독립 확인을 완료 처리하지 않는다. 30초를 물리적 센서 갱신 주기나 시간상수로 해석하지 않는다.
- AP·기본 시뮬레이터·RL 환경·strict·experiment_ready=false 불변. 이번 결과로 후보 기간/계수를 자동 재탐색하거나 새 실측·claim을 생성하지 않는다. 다른 EDD/SLACK 방향과 이번 에너지 판정을 별도로 유지한다.


## 2026-10-08 EDD-ECT-RESIDUAL-DESIGN-01 — EDD+ECT 중심 설계 방향 채택

- 최신 사용자 지시로 후속 RL의 기본 제안·fallback·예측 후속규칙을 `IE_EDD_ECT_LANE_PC_V1`로 변경한다. 원 EDD/ECT는 제한적 B이며, 보정 정책은 별도 `EDD_ECT_SLACK_RESIDUAL_PPO_V1`이다. SHARED의 aging을 섞거나 ECT lane 완료를 응답으로 바꾸지 않는다. [현행 설계·핵심식](EDD_ECT_RESIDUAL_RL_DESIGN_20261008.md).
- 기존 EDD의 주96 AP 감소/J 증가와 전체 일반실패292를 근거로 열·J·서비스 상충을 검증한다. 종료 후 EDD/Shared/Band 세 참조와 검증의 강한Triton을 유지한다. 산업공학 규칙+RL 자체의 최초성, 기본 정책 개선만으로 외부 제품 우월성은 주장하지 않는다.
- 설계 방향/불변조건은 채택, NN·optimizer·후속16,488환경 배분은 구현 전 등록 제안이다. 기존소비2,825·학습0/6,144와 원모형/기본/strict/experiment_ready=false 보존. A/B/C/D/새 controller/PPO 미완료, 이번 환경/학습/기기0. 이전 SLACK 봉인과 결과는 소급 수정하지 않는다.


## 2026-10-08 ROLLING-ENERGY-SHRINK-01 — 개발 전용 강도 추정·평가 완료, 후보 미채택

- 이 대화의 시뮬레이션 에너지 오차 보완으로 단일alpha0..1을 개발6/48창 MAE최소로추정해0.262688로봉인. 확인6+지속8을재적합없이평가했다. [결과·상충·범위](ROLLING_ENERGY_SHRINK_RESULTS_20261008.md) · [480행/재현](results/rolling_energy_shrink_01/README.md).
- 개발회복제외alpha.171..526·30초개별오차악화로gate실패/선택0(원유지). 확인10초MAE 원.870→후보.922J·지속.844→.856J 악화, 확인합산80초3.891→2.960J/지속4.615→3.433J 감소는상쇄/순차관측포함·120초전체개선아님. 전량보정대비악화완화와원모형개선을구분·확인후튜닝0.
- 8검증·실제API160창/480점수재현·원4입력hash/모형불변·표/그림통과. 단일후보적합3회(전체+history2fold), fixture/재현별도. AP/기한/원모형/RL/strict/experiment_ready=false 유지, 정책환경/학습/기기/ADB/실측/Android/APK/claim0·다른IE/SLACK과사용자14행/개인/다른worktree보존.
- 종료/다음에너지PC질문하나: 기존전류의반복/갱신양상과최근잔차지속성으로변동과지속편향을분리할근거가있는지판독. 앱AP배포/RL로목표를대체하거나보정기간/강도를결과후자동탐색하지않는다.

## 2026-10-08 IE-DISPATCH-PC-01 — 산업공학 ECT·SPT·EDD 동일조건 검증 완료

- 사용자 ‘한번 검증해보자’에 따라 FIFO/SPT/EDD 순서+동일 ECT(5단계 lane 완료)의 제한적 B를 별도 adapter로 비교했다. 결과 전 대응·소스·설정 고정, 튜닝0. 기존192조건9정책1,728행(신규576/재사용1,152). [결과·범위·재현](results/ie_dispatch_01/README.md) · [오프라인 화면](results/ie_dispatch_01/index.html).
- 주96 SPT/EDD는 전기한·전량·긴급P95 유지, SHARED_EFT 대비 AP−0.065317°C/J+0.080970·공동감소4. Band 대비 AP−0.053022°C/J+0.169820·공동감소0. SPT/EDD 실제 원장192/192동일. 전체 일반 실패292 vs Shared204/Band193, FIFO 긴급560. Band 대비 상대 공동감소1은 기한 위반 잔존, 절대 전기한 공동감소0으로 구분한다.
- 함수13·엔진 fixture6·기존 EFT 원장2동일, 신규576 원장·인과·점유·ECT·J적분 감사, 5그림·오프라인 검색 PASS. 이번584환경/실패0·학습/기기/ADB0. 기존2,241+584=2,825/20,000·잔여17,175. 옛 장부/종료 clock/단계2 129/학습0/6,144 보존. 후속 RL 제안은 새 소비를 합쳐 등록해야 한다.
- 원모형·기본정책·strict·experiment_ready=false, 사용자9파일·STATUS 인계14행·별도 AP 작업·다른 worktree 보존. 원문 직접403, 동점·SPT축약·응답과 기계 완료 대응 한계 명시. 제품/폰/표면온도 우월성·새 RL gate 통과로 승격0. 버전/해시는 [검증](results/ie_dispatch_01/verification.json).
- 기록 보완: PowerShell→Python 입력 인코딩으로 이 요약 세 절의 한글이 물음표로 저장된 오류를 UTF-8 원문으로 바로잡았다. 다른 절/사용자 변경·코드·설정·결과·예산은 그대로이며 새 환경/학습/기기0.
- 다음: 연구기여는 단순 ECT/SPT/EDD가 아닌 실제 기한 내 열·에너지 보정으로 한정한다. 기존 SLACK prototype A/B/C/D 검증은 미실시다. 별도 진행 지시 없이 추가 학습/실측/배치0.

## 2026-10-08 AP-OBSERVATION-PATH-01 — host 진단 입력 연결·현재APK 자율AP 미지원 확정

- 현재코드에서numericAP는host CurrentHAL에서만읽고start_ap.arm은시작승인1회. 앱은전력/status/BAT와별도메인앱headroom만읽으며지속APconsumer없음. 공식온도API호출자제한·headroom/AP단위차이확인. [코드/판정](AP_OBSERVATION_PATH_PC_20261008.md) · [지원표/재현](results/ap_observation_path_01/README.md).
- 기존20세션1630AP관측을19473원client기록에대조. 3명령host span중앙값.328초/P95.437초·producer기록지연중앙값14.6ms, 앱전달지연null. 기록timestamp는write/flush전이라consumer수신과다름. 실제callback시각명시/proxy표시·소유권/단위/dualclock/future/stale/buffer의독립PC API와10초예측연결 구현.
- 8검증·actualmanifest20/owner1630/예측20·공유Git20fixture/조회통계PASS. 원collector미부착·Android/컴파일/APK/설치/ADB/실측/설정/claim0·원모형/strict/RL/experiment_ready=false유지. 별도SLACKcommit d6074da/사용자14행·개인파일·다른worktree보존.
- 종료/다음행동하나: AP보정은host연구도구로범위를고정하고앱자체경로에는기존공개thermal signal용별도입력계약필요성을결정. 현APK에APstream/반복startarm을붙여소유권/지연/계측비용을우회하지않는다.

## 2026-10-08 — SLACK-RESIDUAL-DESIGN-01 재설계 방향 채택

- 사용자 재설계 지시로 정확한 SHARED_EFT fallback + 실제 기한 내 단건/허용2건/제한 대기 보정을 선택한다. 원기한/완료/P95/J기준·물리계수/기본/strict/experiment_ready=false는 유지하고 R2의 최초EFT cap/signed J veto만 새정책에서 제외한다. [설계·식·구현 경계](SLACK_RESIDUAL_RL_REDESIGN_20261008.md).
- 기록분석192조건: 이른cap12,403/12,672·cap-only탈락579,528·라벨제외추가즉시배정6,776. 실제SLA재검증/새성능은미완료, old192는소비된설계자료로명시한다. 미래일정의작은공동이득은P95증가로teacher불가. 함수7/schema/망원합/prior/예산검증만완료, 환경/학습/기기0.
- 관측107/후보61/32slot·6headcritic·두종료후참조의5제약을 제안한다. MODELED_AP만사용, 최신관측prefix는앱입력/지연/동등입력을확인할별도v2로분리한다. PPOLagrange/예측mask가실제제약보장을준다는주장은하지않는다.
- 기존누적2,241/20,000·잔여17,759·학습0/6,144를유지한다. 제안후속13,912환경/본6,096+학습fixture48·참조cache4,160필수·학습시간null이며 실행계약은미동결이다. 다음은학습없는prototype의A/B/C/D gate, 미통과면학습0. 신규숫자/설계파일을실행승인/정책채택으로승격하지않는다. 다른작업/사용자자료보존.

## 2026-10-08 ROLLING-FORECAST-01 — 관측 가용prefix·10초 갱신 구현/평가 완료

- 기존20세션/280발행·840창을고정10초식으로평가. [판독·평균/최악/합산경계](ROLLING_FORECAST_RESULTS_20261008.md) · [화면/재현](results/rolling_forecast_01/README.md). AP after_ns/전력기록완료이전만입력, future관측누출차단·계수재적합0. 원/갱신은실제미래일정이주어진A조건부, 온라인정책/B검증아님.
- 같은10초AP평균확인0.258→0.156°C·지속0.383→0.209°C개선(평균악화0/6·0/8), 확인최대1.077→1.380°C악화. 개별10초J확인0.870→1.268J악화, 35..115초8회갱신합순오차3.891→0.632J감소는상쇄/지속관측포함·120초전체예측아님. AP별도프로토타입보존/J단기보정채택보류.
- 8관련검증/840행재현·원40파일/모형SHA·그림/표확인. 초기시각 조인 key조인/정확anchor 예외수정·원PC실패보존/v1-v3수치 불변. 새계수/학습/정책환경/기기/ADB/빌드/claim0, 원자료/기본/RL/strict/experiment_ready=false·사용자14행/개인/SLACK별도작업과다른worktree보존.
- 다음PC행동하나: AP관측입력/전달지연을현재앱·host코드에서확인해이모듈의적용가능성판정. 현재 앱numericAP직접읽기/host실시간전달·계측비용미검증, 새실측/주기변경자동시작0.

## 2026-10-08 HISTORY-MODEL-REFINEMENT-01 — 두 후보 구현·사후 평가 완료

- 새이력개발6으로유휴/부하전력분리·AP초기화정규화 두구조를고정하고확인6+기존지속8에서100행평가/100행재현. [결과·악화·범위](HISTORY_MODEL_REFINEMENT_RESULTS_20261008.md) · [화면/입력/재현](results/history_model_refinement_01/README.md). 새정렬/단위/적분결함없음.
- 특정조건개선: AP확인MAE0.260→0.233°C이나개발선택실패·지속최대오차1.277→1.385°C, 에너지지속MAE4.624→4.140J이나확인3.913→4.694J·4쌍J차이오차6.322→6.788J. 두후보일반적용보류·원모형유지. 이미본자료의사후평가, 정확도PASS/정책우월성아님.
- 8관련검증·全100행/계수/봉인/경로재현·原60필수파일/모형SHA불변·그림/화면수치확인. 기기/ADB/빌드/학습/정책환경/새claim0, 기본/RL/strict/experiment_ready=false유지·원FAIL/소비/후보/사용자14행과개인파일/타worktree보존.
- 종료/다음PC행동하나: 기존저장공동개선상한·고정일정에서현재행동공간의개선여지와응답상충을판독. 후보재튜닝/같은실측반복을자동시작하지않는다.

## 2026-10-08 HISTORY-POLICY-READOUT-01 — 저장 정책 차이·새 확인 잔차 연결 완료

- 저장192조건/2,112행·1,920쌍을 재사용해 서비스/전체기한/비용/모형공동감소를 구분했다. 주96 R2−Triton −0.790J/−0.130°C, Band +0.167J/−0.052°C·공동감소0; 후보미채택 유지. [판독·범위](HISTORY_POLICY_ERROR_READOUT_20261008.md) · [화면/CSV/재현](results/history_policy_readout_01/README.md).
- 새확인6 JMAE3.913J·APMAE0.260°C, 명목CPU/PAR 대조잔차J +2.306/−13.877·최고AP +0.619/+0.742°C를 동일지표로병기. 다른부하/초기이력/프로토콜의잔차를 보편한도/신뢰구간으로전용0; 큰물리이득판별숫자·정책승자null. 기존지속192요청 CPU/PAR 서비스전량·긴급P95 127.912–131.381ms개선은그입력의관측근거로유지.
- 관련6검증/실제2,112행 차분/잔차/모형SHA/공유그림·화면확인. 새환경/학습/기기/빌드/fit0; 원모형/기본/RL/strict/experiment_ready=false 유지. 사용자STATUS 인계14행/개인파일/다른worktree는commit제외·보존.
- 다음PC행동하나: 기존공동개선상한·고정일정 저장결과에서 현재행동공간의개선여지 판독. 새배치/실측/학습 자동시작0.

## 2026-10-08 HISTORY-FINAL-01 — 실측12자료・원모형별도확인 완료

- 실제개발6・새확인6총12자료적격확보/회수/판독완료, 마지막app/host정리・PC프로세스부재확인. 원g후보0.162는dev gate실패미채택, 원모형유지·고정된미채택보조비교만수행했다. 원모형확인APMAE0.260°C/최대1.077°C・JMAE3.913J/최대9.682J, 30초C0냉각방향오류1/6남음. [최종보고](ENERGY_AP_HISTORY_FINAL_RESULTS_20261008.md) · [화면/CSV/재현](results/history_control_plan_01/run_v7/README.md).
- 독립physical15시도/12완료・durable2236시작/2235반환/미확인실패PAR최대92추가가능성・전체상한2328유지. runtime60/warmup120/staging105파일/ADB12827 intent/12826 client, APKpush/설치각1・pull2. 원v3clock부터11784.782초/21600초, 이후추가기기0. v7는과거7자료재사용＋새5로12cohort를구성했고최초종료계획들의실패를완주로바꾸지않았다.
- 세부예산결함공개: v7 budget808 대manifest/실제904(+96), 전체상한이내이나세부상한불일치. sourcegenerator를원roster합으로수정하고새Check invariant/실제bad-plan거부25관련회귀통과(총51경계). 잘못된중간조건설명은최종manifest표로정정. original/raw/modelhash불변/재현/그림확인, default/RL/strict/experiment_ready=false유지.
- 다음PC행동하나: 이번잔차를기존정책 차이에병기해분별가능한큰효과범위를산출. 새실측/후보재보정/전체정책배치자동시작0. 다른작업/사용자파일과다른worktree변경보존.

## 2026-10-08 HISTORY-LOCAL-SERVER-PROBE-01 — 7자료再사용·남은확인5 동결

- v6 첫원모형확인PAR180적격(개발6+확인1). 다음준비의localhost5037 host:version1초timeout은서버동일PID8648존재/이후정상응답이며원client미실행. warmup8반환・AP시작승인없어조건부하0(코드gate/arm명령부재확인), 앱host정리완료/원FAIL보존. [구체원인·PC수정](ENERGY_AP_HISTORY_BOUNDARY_REPAIR_20261008.md#v7-로컬-server-probe의-한정된-재확인).
- opt-inPC서버TimeoutError만전체2gap・.25초뒤같은1초probe1회추가, 통과뒤원기기client단1회. serverrestart/daemon생성/프로토콜불일치/기기명령재시도0, 원오류/컨텍스트보존. 실제wrapper/원client1회·legacy/거절/횟수cap검증포함50PASS. APK변경0・모형/g비교값불변.
- v7 `e3d9e199…aa7ae2`/child `76e45a64…bab2cc9`, 적격개발6+확인1read-only 재사용, 원모형/보조비교재동결fit0・새확인5만실행. 808추론/runtime20/staging35파일/ADB38200/9015초예약・APK/pull/install0. 추가준비실패warmup8만누적상한+8=2328・15시도/runtime60/staging105파일, 원v3clock6시간/마무리600초초기화0.
- v5새잔열후보gate실패/미채택과모든원FAIL/소비・동결/기본/RL/strict/experiment_ready=false보존. 나머지확인은추가조건/모형탐색이아니며이미예정된원모형전이확인이다. 다른작업/사용자변경보존. 다음: 현재동일기기gate→남은확인5→전체자료판독・그림・보고/Git.

## 2026-10-08 HISTORY-ORIGINAL-CONFIRM-01 — 원동결모형 별도전이확인6 동결

- v5개발6모두적격. 새g0.162291은두회복block교차기준미충족(원APMAE평균0.169°C/후보0.267°C), 기존원모형냉각방향오류0. v5gate실패/FAIL보존·g후보미채택. 최신자율진행승인아래남은예정6세션을 **원동결모형의별도전이확인**으로고정하며새모형탐색/재적합/허용폭변경0. [목적·기준·예산](ENERGY_AP_HISTORY_BOUNDARY_REPAIR_20261008.md#v6-원동결-모형의-별도-전이-확인).
- v6 `ac518af1…ca6a18`/child `db14ac7d…95505a`, 개발6read-only재사용·새확인6만실행. 모델5682082a/β・k・g0불변, 실패g0.162는동결된보조비교만. 동결분기fit0검사/관련24회귀PASS(나머지기존경계46PASS), Check/캐시/자료hash통과·APK변경0.
- 새1008추론/runtime24/staging6·42파일/tracepull6/ADB45800/10461초예약. 누적상한2320·14시도・6시간/마무리600초/기존계획소비는그대로, v3원시clock승계초기화0・추가후보/추가세션0. 향후결과는원모형conditional전이오차와미채택후보사전고정보조결과, strict/PASS/정책우열아님.
- 다른작업/사용자파일/원모형/기본/RL/experiment_ready=false보존. 다음: 현재동일A24 gate후원모형/보조비교동결→예정확인6→원자료분석/그림/보고서/Git.

## 2026-10-08 HISTORY-ENVIRONMENT-LEASE-01 — 2자료재사용·남은10 실행 동결

- 최신사용자자율수정/재실측승인아래v4의화면2초무출력timeout을PC판독했다. 마지막정상host화면/앱interactive/thermal표본은정상이었으며조회응답소실과실제상태위반을구분한다. opt-in환경미확인1회/session, 마지막유효AP부터10초안에fresh thermal/화면복구필수; 실제위반/두번째실패/미복구/증거실패는중단. [계약개정](ENERGY_AP_HISTORY_BOUNDARY_REPAIR_20261008.md#v5-환경-미확인-lease와-완료-2자료-재사용).
- 실제poll/fresh복구·lease만료·원stack·state위반·legacy·재사용/캐시 포함46검증PASS. v5 SHA `a5a9e425…fa4ba4`, child `5f5c3bf3…735a74f`; C0/CPU적격2는원hash복사, 실패PAR은개발/확인에서제외. 새개발4+확인6/10세션·1712추론/runtime40/staging70파일/ADB76200/16245초예약, APK설치/push/pull0.
- 실패PAR durable108시작/107반환·그뒤미확인(등록상한200)을별도보존한다. 최신계속수정/실행승인으로전체누적상한2320추론/14시도/runtime56/staging98파일로등록(+실패PAR최대200); ADB99240·설치본pull2·6시간/마무리600초는유지. 시간은v3원claimclock승계해수정/대기포함초기화0.
- 원v2/v3/v4receipt·FAIL·원모형/기본/RL/strict/experiment_ready=false보존. helperlease는환경PASS가아니며후속기록의APcoverage/앱환경/최종적격성검사를통과해야한다. 다른RESERVED/S26/사용자변경보존. 다음은남은10세션→등록개발gate/g동결→조건부확인6→부분/완료분석이다.

## 2026-10-08 HISTORY-BOUNDARY-REPAIR-01 — 완료C0 재사용·남은11 실행 동결

- v3첫앱은정상종료/회수됐으나PC가냉각마지막0.393초전류까지요구해power gap으로종료했다. 공식conditioning→target120초는결측0이어서해당구간필수검사와냉각full J의null을분리했다. 원v3FAIL/receipt/원자료불변, 수정판독으로C0적격1을확인. [수정·재사용·정확예산](ENERGY_AP_HISTORY_BOUNDARY_REPAIR_20261008.md).
- 42관련PC검증/원본실제재판독/바인딩Check통과. APK변경0. 새v4 `d2b9687a…da2e`, child `ede6b9e2…f59d`: 첫C0원자료read-only복사/출처hash·현재검사, **개발5+확인6=11새세션만실행**. 총cohort12와새실행소비를분리하며원v3중단을완주로고치지않는다.
- 새1912추론/runtime44/staging11·77파일/ADB83800/17691초예약. 설치본fresh원격hash와이전검증APKcache동일성으로pull0·push0·install0, 불일치면중단. v3원claimclock을승계해수정시간포함6시간/마무리600초·연결대기20분상한을초기화하지않는다. 새보완실측0, 상한소진은중단·부분분석.
- 이전v2의104와v3의104＋남은1912=총상한2120추론/runtime52/staging13, hostAPKpull총2. user/RESERVED/S26변경과동결모형/기본/RL/strict/experiment_ready=false유지. 다음은최신자율승인아래동결v4의남은수집→g동결→확인→분석이다.

## 2026-10-08 POSTAPPROVAL-OBSERVATION-01 — PC 검증·새 v3 동결, 자율 실행 승인

- 사용자 “알아서 수정해가면서 계속 진행…계획한거 다 마무리”로 PC 수정 뒤 새 실행을 승인했다. 단순 진행 listing을 opt-in2초 주기로 분리하고, 출력없는3초 timeout/client-reaped/증거완전일 때만 세션당1gap을 기록한다. 다음 정규관측의 fresh thermal/화면 확인은 필수, 두번째실패/연결오류/환경실패/저장실패는중단. [계약·검증](ENERGY_AP_POSTAPPROVAL_OBSERVATION_PC_20261008.md).
- 실제 poll 진입·원0605비식별fixture·legacy·회수/cleanup 포함39검증/기기차단Check통과. APK재빌드0, 기존원모형/기본/RL/strict/experiment_ready=false보존. 새 v3 SHA `2a4f3443…96213`, child `e64cda96…63a65`/동일APK `3840bfb1…c8768be`; v2소비·원자료는불변.
- v3는별도6시간 캠페인(최대2120추론/13시도/ADB99240, 마무리600초/연결대기1200초/읽기회수120초); 이전v2의104추론/623명령은별도공개한다. 최신승인아래새v3만단1회실행하며수정/대기중시간증액없다. 첫앱결함/적격개발0/전체블록잔여예약일때만보완1회, 무한재시도·미확정원인우회없다.
- 다음행동: v3로현재A24·설치본·환경gate를확인해개발6→g동결→확인6을수행하고부분/완료결과를판독한다. 다른RESERVED/S26인계/사용자파일변경보존.

## 2026-10-08 HISTORY-RECOVERY-RUN-02 — 첫 개발 세션 host timeout 중단

- 사용자 최신 “진행하자” 승인으로 v2 SHA `7daa7326…13ace`를 단1회 실행했다. 첫 conditioning96/120초와 runtime4/warmup8을 회수했으나 회복30초 도중 listing3초 무출력 timeout. 적격개발0/6·확인0/6, candidate 동결0, target/J/AP 평가null. [결과·소비·원인 경계](ENERGY_AP_HISTORY_RECOVERY_RUN02_20261008.md) · [작은 결과/재현](results/history_control_plan_01/run_v2/README.md).
- 총 durable 추론104/상한2,120·ADB623/99,240·251.720초/21,600초. 설치본pull/APKpush/설치각1, staging1/7파일, tracepull1. 앱결함/명시연결소실증거없어 보완/20분대기0. 첫계획소비·stopped_no_resume, 새claim/재실측0.
- 대상 세션 host force-stop1/프로세스부재 확인, 앱 cleanup 미회수. child/parent실제PC프로세스부재·원모형2hash·원본불변/공유판독 재현 확인. 원인내부미확정, 기기 설정/연결전환/추가조회0. 원기본/RL/strict/experiment_ready=false·사용자/RESERVED/팀회신 변경 보존.
- 다음PC작업하나: 승인 후 반복 listing의 단순 진행 관찰 실패와 필수 환경 감시 실패를 실제 poll 진입fixture에서 분리 검증한다. 같은 계획·앱결함 추측 재실행으로 이어가지 않는다.

## 2026-10-08 HISTORY-RECOVERY-PC-02 — 6시간·연결대기·보완 실행 경계 준비 완료

- 실측 전 PC 작업만 수행. 원 수집 child 종료 확인 뒤 동일 transport를 최대20분/20회 조회하고, 동일 기기·manifest·앱 종료 증거를 확인한 경우 읽기 전용 회수1회(120초/20명령)를 수행하는 별도 parent 경로를 구현했다. 자동 연결/서버재시작/설정변경/endpoint전환0. [최종 계약](ENERGY_AP_HISTORY_RECOVERY_PC_20261008.md).
- 새 `energy_ap_history_recovery_plan_v2` 캠페인 SHA `7daa7326…13ace`, 기본 child SHA `2e25aa64…62620`, Check 통과·미승인·미소비. 기존 v1 계획 byte/미소비 보존하되 실행 대상은 새 wrapper뿐이다. APK `3840bfb1…c8768be` 재사용, Android 변경/재빌드0.
- 최대6시간(대기·수정 포함), 마지막600초 예약. 정상12세션/2,016추론, 보완 포함 최대13세션/2,120추론·runtime52·staging91파일·설치/push/pull각2·ADB99,240. 모든 상한을 함께 소진할 수 있다는 뜻은 아니다. 보완은 **첫 앱 실패·적격 개발0·원인 재현/검증·남은 전체 블록 시간**일 때만 새12세션 block1회 허용. 이후 실패·모형 gate 실패·원인 미확정은 재실측하지 않는다.
- Python36검사/기기차단 Check 통과. 기기/ADB/실측/Run/claim0, 기존 기본/RL/strict/experiment_ready=false 보존. 다른 작업의 문서·.gitattributes·사용자 파일은 이번 commit에서 제외한다. 다음 행동 하나: 새 캠페인 예산의 실측 승인 후 현재 A24 환경 gate를 확인한다.

## 2026-10-08 — RESERVED-THERMAL-01 단계 진행과 모델 역할 채택

- 최종 자율 실행 완료/판정: 수치R2·동일48조건576행·새192조건11정책2,112행을 완료했다. 주96Triton공동감소96/Band0·전체일반실패292 vsBand193이므로 현후보미채택·RL0. 내부EFT 대조추가/원후보R2교체·계획11정책 개정을 명시하며 기존판정/기본/strict/experiment_ready=false를 유지한다. 누적2,241/전체20,000·단계2 129/512·학습0/6,144·이작업기기0, 사용자/다른작업 보존. [최종요약/원본/재현](results/reserved_thermal_01/FINAL_SUMMARY.md). 이번파일만Git공유하고 남은예산으로 새설계/학습/실측을 자동시작하지 않는다. 아래는 이전 단계 이력이다.

- 단계3 수정본48/576행 완료·누적129환경(추가58, 실패추가0). 9직접검증/10회귀·최대이동0.458ns·원 pilot 주요지표 동일. 유효행동 다양성319/12,623이나 배정차이0·Band/EFT 주24공동개선0이므로 RL0/보류. `PROCEED_RULE_ONLY`로 새16seed×4부하×3문맥=192조건/11정책2,112행을 사전등록해 최종 비교 중이다. 내부EFT 대조 추가/원후보 대신R2 사용을 명시했고 기기0·계수불변. 최종블록 최대2,128환경/60분·저장5분, 같은 전체20,000 장부. [검토/범위](results/reserved_thermal_01/numeric_r2/RULE_ONLY_REVIEW.md).

- 최신 사용자 지시로 단계별 모델 전환 대기와 반복 확인을 해제한다. 기존 예산 안에서 전체 계획·조건부 RL 판정·문서/시각화/Git까지 자율 진행하며 모델 자동 위임은 하지 않는다. 단계3 `REVISE_BEFORE_RUN`에 따라 원48행 보존, 이동량≤1ns 수치R2·내부EFT 대조·행동 다양성·같은48조건을 최대64추가환경/60분으로 수행한다. 학습/새 최종시험은 이 보완 결과 판정 전0. [검토 계약](results/reserved_thermal_01/ASTRA_STAGE3_REVIEW.md).

- Sol 승인pilot 완료: 고정48신규/432재사용=480행을 보존했다. `PROCEED_PILOT`의 코드/식/물리계수는 바꾸지 않고 저장 일정≤1ns 겹침만 별도 수치adapter로 보완, 첫4원실행/44보완실행 binding과 실패2회 추가를 명시했다. 누적71환경/학습·기기0. [실행 결과와 한계](results/reserved_thermal_01/PILOT_REPORT.md). 강한Triton 대비 주24공동개선24이나 Band/EFT0·전체 기한손실이 있어 정책 채택/RL 허가로 승격하지 않는다. 다음 판정은 Astra 단계3이다.

- 최종 코드/pilot 검토 `PROCEED_PILOT` 확정: 구현5·설계2·pilot등록2에 바인딩한 48신규/432재사용 개발 pilot만 허용한다. 이전 차단 사유 해소와43검증 소스 일치, 전체/단계 예산 소비21 보존을 확인했다. 경미한 fallback 집계 누락은 원본 decisions 후처리로 분리 보고하며 동결 정책은 변경하지 않는다. [최종 판정과 구체 범위](results/reserved_thermal_01/ASTRA_FINAL_REVIEW.md). 이번 환경/학습/기기 추가0, Sol 실행 후 Astra 단계3에서 성능/RL 판정. 아래 수정 판정 이력과 초기 검토 원본은 보존한다.

- Sol이 Astra 수정 계약을 반영했다. 완료 cap/signed J 식은 유지하며 저장 일정 각 시작 하한·최종 장부/원인 분리·pending·설계revision/원 상태 소실과 owner 보호·gate 검증·pilot 실행/재개를 보완했다. 43검증과 이번10fixture를 완료했고 누적21환경이다. 48신규/432재사용 설정을 고정했다. [보완·해시·다음 Astra](results/reserved_thermal_01/SOL_REPAIR.md). 최종 소스 확인 전 `REVISE_BEFORE_RUN` 유지, 성능 pilot/RL/기기 허가로 승격하지 않는다.

- Astra 사전 검토 판정은 `REVISE_BEFORE_RUN`이다. 최초 완료 cap과 signed J credit을 보수적 1차 pilot 가설로 유지하며 일반 cap 완화·새 계수·그림자 기준정책은 이번 수정에 추가하지 않는다. 누적 예산 충족은 별도 EFT/Band 실행 대비 J 비악화 보장이 아니다. 저장 일정의 절대 시각 보존·최종 예산/원인 분리·불변 설계 revision과 gate 검증 보완 후 최종 소스를 다시 확인한다. [검토·직접 반례·Sol 범위](results/reserved_thermal_01/ASTRA_REVIEW.md). 성능 정책 채택/RL 허가0, 이번 환경/학습/기기 추가0, 누적11환경 유지.

- 단계2 구현안을검토가능하게완성했다. 최초long-context EFT응답cap과현재상태새요청signed J credit은**제안식**이며성능정책채택아니다. 원16+회귀5검증·fixture11환경(실패1포함), pilot/학습/기기0. [명시식·인계](results/reserved_thermal_01/README.md). 사용자가정한Astra핵심식검토를거쳐Sol이pilot을이어가며, 판정완화/모형변경/소비초기화없음.

- 사용자 지시에 따라 [단계별 PC 진행](RESERVED_THERMAL_STAGE_PLAN_20261008.md)을 채택한다. Astra=계획/검토, Sol=구현/실행, 사용자가 직접 모델 전환. 다른 모델 하위 에이전트로 자동 위임하지 않는다.
- 전량·기한·긴급 응답 유지 아래 AP 최고값을 주목적으로, J 비증가를 조건으로 연구한다. Band/Triton 요청adapter·강한EFT·학습 없는 새 규칙을 대조한다. 과거 판정 변경/외부제품·실기기 우월성 채택이 아니다.
- 새20,000환경·본학습6,144 상한, Sol 구현/최대512환경 pilot 뒤 Astra 검토. RL은 필요할 때만 새 알고리즘으로 수행한다. 입력/소스 manifest·RL 세부 설정 미동결을 남긴다.
- 기기/ADB/실측0, 사용자파일/다른worktree/별도 수집 작업/동결/기본/strict/experiment_ready=false 보존. 최초 계획 작성과 이번 Astra 검토의 추가 소비는0이며, 사이에 수행한 Sol fixture11환경은 누적 장부에 유지한다.

## 2026-10-08 HISTORY-CONTROL-PC-01 — 통합 경로·서명 APK·실행 계획 준비 완료

- 사용자 `진행해`에 따라 실측 전 PC 구현을 완료했다. 같은 resident에서 conditioning96→고정 회복30/180초→C0/CPU96/PAR96을 수행하는 opt-in 경로와 개발6→후보동결→확인6 진입을 연결했다. 기존 경로·동결 모형·RL·strict·experiment_ready=false 보존. [상세/정확 예산](ENERGY_AP_HISTORY_CONTROL_DESIGN_20261007.md) · [검증/바인딩](results/history_control_plan_01/implementation_check.json).
- APK `3840bfb1…c8768be`, 계획 `da212cf9…79954f`. 외부 `energy_ap_history_control_plan_v1`은 **미승인·미소비**이며 Check 통과. 최대12세션/2,016추론/runtime48/staging84파일, ADB91,400명령·19,557초(5시간25분57초) 예약. 고정103.5분과 정상 예상시간을 구분한다.
- Android12·Python26 관련 검사, 기존 프로젝트 서명 격리빌드·패키지·해시·계획 Check 완료. 새 모드의 실기기 동작·trace 연속성·계수 식별 가능성은 미확인이다. 개발 부적격/후보 gate 실패이면 확인에 진입하지 않는다. 기기/ADB/설치/실측/Run/claim0.
- 다음 행동 하나: 준비된 한 캠페인의 실측 승인을 받은 뒤 현재 기기·설치본·환경 gate를 통과할 때만 실행한다. 이번 PC 작업에서 실행 승인이나 자동 재시도는 만들지 않았다. 과거 종료 계획·사용자 파일·다른 worktree 보존.

## 2026-10-07 HISTORY-CONTROL-DESIGN-01 — 수집 설계 제안, 실행 미준비

- 사용자 계획작성 요청. 기존배경대조4가이미있으므로단순반복제외. 동일conditioning96→고정회복30/180초→C0/CPU96/PAR96의개발6·동결·확인6을권고. 채택/실행승인이아닌제안이다. [계획](ENERGY_AP_HISTORY_CONTROL_DESIGN_20261007.md).
- 최대2,016명시추론/runtime48, 고정관측+pause103.5분. 총6시간은제안예약이며실제ADB/전체강제상한은구현전null. 같은resident의2단계origin/trace/watchdog/후보동결gate/APK바인딩이필요해실행준비완료라고하지않는다.
- PC조합·산술Check통과, 기기/ADB/설치/빌드/실측/claim0. 원동결/기본/RL/strict/experiment_ready=false유지. 다음행동하나: 등록이력연속실행과분석gate를PC구현해정확상한·APK·manifest를최종동결한다. 기존실패/종료계획재개없음.

## 2026-10-07 MODEL-REFINEMENT-02 — 후보 미채택

- 사용자 추가 검토 승인으로 기존개발3+확인6을 사후개발9로 사용하고 지속8 적합제외. 부하구간 세션중앙값 공통전력gain/AP k 한후보 구현, 개발LOSO9·A/B68행·사전특징최근접 진단 완료. [보고서](MODEL_ROBUST_GAIN_20261007.md)·[화면/재현](results/model_refinement_02/README.md).
- 지속8 J MAE4.624→5.207J/AP0.381→0.395°C, 악화6/8·5/8로 미채택. 준비4특징 잔차진단12.058J, 해당최근접진단은후반오차예측실패. 정책쌍J6.322→6.297J의작은감소도 전체개선/정책우월성 아님. 기존자료로모든개선불가능이라고확대하지않음.
- 원동결/원자료/기본/RL/strict/experiment_ready=false 유지. 기기/ADB/실측/빌드/추가학습0, 새계획/claim0. 다음PC행동하나: 정책차이에세션/쌍별잔차병기. 사용자파일/다른worktree 보존.

## 2026-10-07 — MODEL-REFINEMENT-01: 기존 실측 후보를 기본 경로에 채택하지 않음

- [사전 후보계약](results/model_refinement_01/contract.json)·[사후 결과](MODEL_REFINEMENT_EXISTING_DATA_20261007.md). 부하전초기단순화/작업잔열/전력추세3후보는 개발일부개선이 확인14의일반개선으로 이어지지 않았다. 개발세션제외선택은 기존동결 유지, 평가후후보추가·계수재조정0.
- AP_DELAY는 확인/지속 평균AP오차0.389→0.429/0.381→0.411°C, E_TREND는J MAE9.424→11.975/4.624→6.750J. 일부좋은세션만지원으로선택하지않는다. 원모형/기본정책/RL/strict/experiment_ready=false유지.
- 확인자료를적합에쓰지않았으나이미열람한사후평가다. 센서표본≠독립세션, 순서/정책/열이력교란과후반배경변화는미식별. 소수후보실패를기존자료의모든개선불가능으로확대하지않는다. 추가실측계획/실행승인아님.

## 2026-10-07 — EXTERNAL-RULES-12: 제어 방식보다 동등 서비스와 J/AP 평가

- 최종 판정: Triton5설정×48조건240신규환경 완료, 기존384행 재사용. 2건은제한해제일정동률·1건은상충/서비스손실, 전량·기한 유지한J/AP공동개선0. StarPU는이번C보류, 우리2규칙도지속기한손실. 원제품우월성/기기절감으로확대하지않는다. [결과](REQUEST_TRITON_THERMAL_ENERGY_PC_20261007.md). 이번fixture포함246환경/16검증·기기/학습0, 기본/strict/experiment_ready 승격0.

- 사용자 지시를 반영하여 공개 규칙이 CPU/GPU 배정과 다른 제어를 하더라도 같은 기한·예정 전량을 유지한 열/에너지 비교를 허용한다. 미완료/지각을 에너지 성공으로 바꾸지 않는다.
- Triton Rate Limiter 실제 core control flow를 request 단위 B로 적용,5설정/48조건은 [결과전 대응](results/external_rules_02/mapping.md)에 고정한다. 원 서버/기기 성능으로 확대하지 않는다.
- StarPU의 작업별 에너지 귀속·전송/prefetch·허용병행과 독립worker 큐 대응은 미확정이다. 이번은 보류하며 미측정 값을0으로 채우거나 원 규칙에 자체 제한을 조용히 붙이지 않는다.
- 과거384행은 입력·원 소스·모형SHA 일치 후 재사용. 이미 공개된48조건이므로 새독립확인아님·결과후튜닝0. 이번400환경/3시간(마지막20분 저장)·기기/학습0,기본/strict/experiment_ready=false 보존.

## 2026-10-07 — EXTERNAL-RULES-11: 외부 규칙의 제어 대상·근거 경계

- 최종 판정: 원출처2개/제한적B adapter·48조건/1,056행 완주. Band 적용의지속12조건은강한EFT 대비기한유지·J/AP소폭동시감소이나외부제품/실기기우열미판정. 우리열에너지2규칙은같은지속조건기한위반,Ente합성상태일부지각/미완료를보존한다. 판정완화/원모형변경/튜닝/기기/학습0. 기본/strict/experiment_ready 승격과LSF/MediaPipe/LiteRT/NPU의미재현범위를자동완료하지않는다. [근거](REQUEST_EXTERNAL_RULES_PC_20261007.md).

- 사용자 지시를 채택하여 공식 출처에서 확인한 Ente 건강/활동 시작 허용과 Band 기본 HEFT를 별도 PC adapter로 비교한다. [결과 전 대응표](results/external_rules_01/mapping.md)에 변경·생략·동점·상태·단위를 고정한다.
- Ente BAT·OS thermal·활동은 미보유 입력이므로 합성 상태 민감도만 허용하고 AP를 BAT로 대신 쓰지 않는다. 양쪽 하위 EFT를 동일하게 고정한다. Band subgraph를 whole-request로 축약하는 변경은 핵심 구조 차이이므로 B·제한적 재현이며 동일 Band 알고리즘/제품 비교로 쓰지 않는다.
- LSF/MediaPipe의 drop을 제거해 원 이름으로 비교하지 않는다. LiteRT priority 전달과 NPU Manager load/선점의 기능 존재를 현재3cell 스케줄러·전력 모형 지원으로 승격하지 않는다. 기존 기본·strict·experiment_ready=false·사용자 자료·활성 실행 보존, 기기0.

## 2026-10-07 — RULES-RL-AMOUNT-10: 규칙 재조합·별도 재학습의 새 승인

- 최종 상태: 본학습49,152/공통4지점/최종192조건·10,560행 완료, 실제RL68,754/재조합458·기기0. 후보/시험입력은결과전에동결했고시험후다시선택하지않았다. 적격best3→3→4→4·강한SHARED_EFT 공동개선0, 부적격조건별이득과B−A 열상충을보존한다. 8,192상한·수렴미확인이다. 현재자료로기본정책/strict/experiment_ready를변경하거나추가학습·실측을자동승인하지않는다. [근거·한계](REQUEST_RULES_RL_AMOUNT_20261007.md).

- 사용자 붙여넣기 지시의 순서·자율 PC 복구·분석/commit/push를 채택한다. 단계별 재승인은 요구하지 않는다. 이번16시간/4,000재조합/80,000RL환경·실행별8,192학습·기기0 상한은 새 승인이고 이전6실행의 Adam/RNG 복구나 정확한 이어학습을 뜻하지 않는다.
- 기존 즉시 행동 안에서 최대3도착요청의 prefix 가지치기와 완성 조합 판정을 비교한다. 새 WAIT·미지원 계수·미래 입력을 추가하지 않는다. 이미 완료된 동일 비교를 찾으면 재사용하며, 다른 범위인 과거 offline/WAIT beam은 별도 근거로 남긴다.
- RL은 기존6구성으로 새 연속 학습을 수행하며 common milestone별 latest/terminal과 best-validation을 분리한다. 재조합 결과로 RL 행동/보상을 바꾸지 않는다. 연장 판단은 최종시험 개방 전에 개발 검증만 사용한다. 구현 보존 검증 뒤 장시간 실행한다.
- 모든 fixture·오류복구 환경을 새 장부에 포함한다. 같은 원인 수정 후 재개 최대2회, 학습수치/정책결함은 이전 이후를 합치지 않고 영향을 받는 새학습 중단. 기존자료·사용자변경·다른worktree·strict/default/experiment_ready=false 보존.


## 2026-10-07 — REQUEST-PPO-LEARNING-AMOUNT-09: 정확한 연장 조건과 상태 보존

- 사용자 승인: 학습량만 연장(추가18,432episode/환경30,000/활성4시간·종료5분예약), 상태부재시초기화/전체재학습없이가능한분석을완료한다. [실제자료·판정](REQUEST_PPO_LEARNING_AMOUNT_PC_20261007.md).
- 원 v2 ring checkpoint는 학습후 network/optimizer를지우고시험까지덮어써6개최종Adam/RNG가없다. 선택actor대체·Adam재초기화는순수학습량비교가아니므로정식연장차단. 기존소비계획의재실행차단을해제하지않는다.
- 확정된 구현 보완: 별도 producer에서 상태를 지우기 전 최종 network/optimizer 참조를 확보하고, 마지막 검증 직후 다음 learner로 넘어가기 전에 actor+critic/Adam/승수/RNG/선택상태를 불변archive에 보존한다. 기존 실행자료를 복구하지 않는다. 두update fixture에서 정상재개 후 추가학습·archive의 optimizer/RNG 동일성을 검증했다.
- 기존데이터의후반개선/회귀·seed차이를기록하고1,024/2,048/4,096 효과는미판정으로남긴다. 정식본학습/시험/claim0·기기0, 기본/strict/experiment_ready=false/모형/원자료는보존한다. 별도재학습은현재전체재학습0 승인범위밖이며자동실행하지않는다.

## 2026-10-07 — REQUEST-PPO-EVALUATION-08: 시간 종료 뒤 동결 정책 평가만 준비

- 상태: 사용자의 이어가는 방법 요청에 따른 PC 후속 경로 구현·검증. 정식 후속Run은 사용자터미널 명시 호출까지 미실행이다. 기존 학습Run의 budget_stopped·90분예산·원본·동결actor를 보존한다.
- 완료104조건과 남은88조건을 원 checkpoint/receipt/순서/해시로 고정했다. 남은평가880+참조88, 추가학습/선택/재보정0, 별도활성2700초(종료120초포함)·retry0. 종료 계획 Resume 제한을 풀지 않고 별도 소비claim/출력을 사용한다. [명령·근거](results/request_ppo_01/queue_design_v2/README.md).
- 조건별 원자료와 작은 재개 위치를 저장한다. 정상 Ctrl+C 뒤의 동일 후속 실행만 Resume를 지원한다. 완료·예산종료·비정상중단은 재실행하지 않는다. 일부최종결과를본후운영보완이며 조건/정책/판독은 고정, 독립실기기확인/절감효과/strict/PASS/experiment_ready를 승격하지 않는다.

## 2026-10-06 — REQUEST-PPO-FEASIBILITY-07: 처리 가능한 주 실험과 과부하 판독

- 상태:사용자의 '위 작업 진행' 요청에 따른 **PC 설계/구현 채택**,새학습/실측/정책효과채택 아님. [계약과근거](results/request_ppo_01/queue_design_v2/README.md). v1을본사후설계로여섯actor부적격·공동개선0·기존계획/모형을보존한다.
- 이미기록된필수CPU초과를절대실패0 학습과선택에연결하지않은누락을수정한다. 기한1.5/6초유지,low/sustained 주학습/선택,queue/burst 과부하최종평가만. 필요조건위반과가능일정witness를구분하며unknown은주조건편입차단.
- 양의열초과cost로상쇄를막고조건별선택과일치시킨다. 기대0을유한학습의전입력보장으로쓰지않는다. v2 공유mask는같은요청에즉시제시간대안이있을때이미늦는backend만제외,모두늦으면진행한다. 과거v1/가드결과를재판정하지않는다.
- 새seed/기준/공동비악화와엄격감소/6144학습·10024계산·90분활성상한을새계약에고정했다. 관련검증·Check 뒤사용자정식Run 준비,이번Run/Resume/claim0·기기0. 개선없음도종료,추가실측/기본정책/strict승격없음,experiment_ready=false.

## 2026-10-06 — REQUEST-PPO-RESUME-06: 사용자 요청의 명시적 상태 복원

- 최신사용자요청에따라별도정상정지/Resume를추가한다. [§12](REQUEST_PPO_QUEUE_RULES_20261006.md). 현재실행중인원래코드와기한/물리식/학습선정은변경하지않고전체state·RNG·캐시·검증/시험cursor·소비·잔여활성시간을복원한다. source/runtime변경·강제중단·완료·활성/미확인owner는재개거절이다.
- 첫버전의부족한캐시는고정참조만재구축하고checkpoint뒤계산반복을따로기록한다. 논리적원배치는같으며최대2399추가PC복구계산과실제소비/미기록범위를별도로보고한다. 이최신명시적복원요청은과거재시도0의정상checkpoint이어가기만변경하며결과후튜닝/추가seed/실측을승인하지않는다.7200초는기존사용시간과복구를합산하고정지공백은따로기록한다.
- 9관련시험·실제PowerShell Resume 및연속/재개/첫버전이관의actor/CSV일치확인. 독립정책효과/실기기/장시간완료는미판정이다. 현재사용자폴더는조사만했으며자동중단/이관을수행하지않았다. 동결/기본/strict/experiment_ready=false·기기명령0유지.

## 2026-10-06 — REQUEST-PPO-TERMINAL-05: 사용자 실행 코드와 진행 관측

- 사용자직접터미널실행요청에따라기존이벤트엔진/모형을재사용한별도 `d1_queue_ppo` 경로를구현했다.17출력/5value/85관측·공유진행가드와Check/Smoke/Run/Status·journal/원자적progress/checkpoint/owner lock/receipt를연결했다. 주기한1.5/6초와정식예산은변경하지않았다.
- 관련13시험및실제PowerShell→Python축소14+10=24실행통과. 최고APcost를양의유휴초과량에서복원하던새연결오류를절대AP경로사용으로수정했다. 기존모형/과거PPO/결과byte는보존한다. fixture최적화·단일축소동결/시험은정식학습/독립예측/정책효과증거가아니다.
- 다음은사용자Check→정식Run이며이번에자동시작하지않았다. 정상취소/실패는원래stack과부분진행을보존한다. 강제종료/전원상실의finally보장/자동재개/실기기절감은주장하지않는다. 기기명령0,기본/strict/experiment_ready=false유지.

## 2026-10-06 — REQUEST-PPO-FINAL-PLAN-04: 유한한 HEAD/QUEUE 비교 계획

- 사용자 최종계획 요청에 따라 [§10](REQUEST_PPO_QUEUE_RULES_20261006.md)과 [예산 JSON](results/request_ppo_01/queue_training_plan_v1.json)을 설계로 고정한다.1.5/6초·동결모형·17슬롯·5value의masked PPO-Lagrange를 사용하고 HEAD/QUEUE와5기준정책을비교한다. PPO최적성검증이나기기실행승인이아니다.
- 같은순서2048학습사례×2변형×3seed=12,288episode. 참조/검증/시험포함17,936PC시뮬레이션·정식전체7200초·기록120초예약, 구현smoke별도최대24. 기존hyperparameter를재사용하며최고AP비용승수초기1을추가한다. 서비스비용은기준실패율차이가아닌절대실패율0이다. 수렴·성공·검정력보장으로해석하지않는다.
- 검증48사례에서각actor를고르고6actor모두최종192사례전에동결한다. 시험최선seed선택·결과후재튜닝·예산증액·DQN/SAC자동탐색0. 원래EFT와공유guard기준을구분하고조건별전체분모·기한/J/AP상충을보고한다. 절감없음/제약실패도정상연구종료다.
- 현재는계획의정적검증만완료,새학습/시뮬레이션/실측0. 정확한관측schema/소스/입력hash·seed사용검사·callback검증을다음구현에서연결한후에만학습가능하다. 기존원자료/결과/동결/기본/strict/experiment_ready=false보존;실기기절감과정책기본채택은미확인이다.

## 2026-10-06 — REQUEST-DEADLINE-FIX-03: 동일 서비스 요구의 주 기한 확정

- 사용자 요청에 따라 주 평가 기한은 **분류 예정 도착→output_ready1.5초, 탐지 예정 도착→persist_complete6초**로 유지한다. [PPO 규칙 §9](REQUEST_PPO_QUEUE_RULES_20261006.md). 현실 앱의 유일한 정답/SLA가 아니라 비교 가능한 등록 연구 조건이다. 개발 CPU 평균 응답 대비 두 작업 약9.6배라는 산술은 일관성 점검이며 원래 선정/사용자 연구 근거로 소급 주장하지 않는다.
- REQUEST-TASK-DEADLINE-02의1초/공통120초 주조건 채택을 철회한다. 기존 제안 JSON/기록은 보존하며 활성 학습에 사용하지 않는다. 에너지 회계창은 서비스 기한의 근거가 아니다. 정규화3조건은 보조 민감도로 유지하고 성적이 좋은 값으로 주 기준을 교체하지 않는다.
- HEAD/QUEUE/EFT에 같은 기한·입력을 적용한다. 다음은17슬롯과 해당 기한의 공유 진행 가드 구현이며 혼합 기한 구현은 제외한다. 기한 변경에는 구체적 과업 요구 근거 또는 명시적 별도 연구 질문이 필요하다. 정책 실패/절감 부족/구현 편의는 변경 근거가 아니다. 전 요청 lane해제≤120초의 전체 비용 적격성은 별도 유지한다. 기존 결과/동결/strict/experiment_ready=false 불변, 이번 새 학습/시뮬레이션/기기0회.

## 2026-10-06 — REQUEST-TASK-DEADLINE-02: 과업 요구와 완료 예산 분리

- 사용자 과업별 기한 설계 요청에 따라 [PPO 규칙 §8](REQUEST_PPO_QUEUE_RULES_20261006.md)을 후속 PC 설계로 채택한다. 분류는 대화형 결과 준비 대리로 도착→output_ready1초, 탐지는 유예 가능한 저장 대리로 공통 원점+120초까지 전량 persist_complete다. 첫 도착35초부터85초이며 각 요청에120초를 주지 않는다. 역할 매핑과1초 채택은 연구 설계,120초는 기존 J창의 동일 작업량 완료 예산이다. 실제 사용자 SLA는 미확보다.
- 정규화 중간값0.628/4.968초의 주 조건 추천을 대체한다. 기존3조건은 공학 민감도,1.5/6초 실측/학습은 과거 계약 그대로 보존한다. 현재 결과를 다시 합격 처리하지 않는다. 모든 lane 해제≤120초와 전체 실패/미완료 분모를 확인해야 하며, 이후 AP는180초까지 판독한다.
- 기존 고정2초 배경 aging은 새 묶음 기한에 자동 적용하지 않는다. 현재 도착한 CPU 필수 수요/남은 묶음 시간/긴급 응답을 함께 보는 공유 진행 가드를 다음 구현에서 검증한다. 미래 수요 미확인하에 완료를 무조건 보장하지 않는다. HEAD/QUEUE/EFT 같은 조건, 새 기한 실행/학습 미진행, 기본/strict/동결/experiment_ready=false 보존.

## 2026-10-06 — REQUEST-DEADLINE-DESIGN-01: 제품 SLA와 연구용 여유 분리

- 사용자 기한 재설계 요청에 따라 [PPO 규칙 §7](REQUEST_PPO_QUEUE_RULES_20261006.md#7-후속-기한-설계--요구사항과-처리-가능성을-구분)을 후속 PC 설계로 채택한다. 제품 SLA는 null, 기존 1.5/6초 대조는 보존한다. 현재 개발 CPU 응답 기준 157/621ms와 배수 2/4·4/8·8/16을 사용한 유한 민감도 조건은 인간 허용시간·P95·WCET가 아니다.
- 입력은 정책/backend/미래 결과에 무관하게 같은 기한을 받고 예정 도착을 변경하지 않는다. 2초 고정 aging만으로 작은 기한을 보호하지 못하므로 `min(2s,max(0,D-C_ref))`를 공통 자발적 추월 가드의 설계값으로 정한다. 이 가드와 필요 CPU 수요 판정은 새 실행 경로 구현 때 검증할 항목이다.
- 생성기/실제 CLI 6검증만 완료, 기존 엔진에 새 기한을 이미 연결했다거나 정책 효과를 검증했다고 하지 않는다. 전체 120초 비용 창 밖으로 부하를 밀어 절감으로 인정하지 않는다. 새 학습/실측/claim 0, 동결/기본/strict/experiment_ready=false 보존.

## 2026-10-06 — REQUEST-PPO-QUEUE-RULES-02: 요청 선택 포함 설계

- 상태: 사용자 재설계 요청에 따른 **다음 구현 명세 채택**, 학습 후보나 기기 정책의 효과 채택 아님. [규칙](REQUEST_PPO_QUEUE_RULES_20261006.md). 상위 8개 요청의 CPU/GPU 배정과 WAIT를 합법 mask로 선택하고 현재 3cell/지원 병행/비선점 소유권을 유지한다.
- 전체 도착 기한과 J/AP 면적·최고값을 분리한다. 같은 새 목적·가드로 HEAD와 QUEUE를 비교하고 과거 PPO와의 수치 차이를 행동 확장만의 효과로 해석하지 않는다. 새 모델 가정·물리 계수 조정·미래 정보 사용 없음.
- 실행량·seed·학습 manifest는 구현 검증 후 고정할 미완료 항목이다. 이번 학습/기기 실행/새 기기계획/claim 0, 기존 결과/strict/experiment_ready=false 유지. 행동 공간 확대가 과거 실패를 해결한다고 미리 결론 내리지 않는다.

## 2026-10-06 — METHOD-DIRECT-PAIR-READOUT-PC-01

- 채택한판독:세션별requestID를제외한의미입력은같아야하며실제요청기록/전체분모/기한·공통창을대조한다. 모든실패/미완료/미확인을남긴다. J/AP적격성은독립검사,없는값은null,제어비용이포함된전체기기J에이중합산0. 실제CLI/7검증으로기존1536응답·4쌍의의미입력을확인했다. [결과·소스·검증](results/method_followup_01/README.md).
- 기존4쌍의같은120초J점차이는보존하되완전동일AP창/초기조건/불확실성근거부족으로공동순위는미판정이다. 과거공유계획동일성과미래기기/APK/센서/runtime/resident동일성을혼동하지않는다. 새측정/계획/claim/정확도PASS/기본후보채택0,연구목표미완료,기본/strict/동결/experiment_ready=false유지.

## 2026-10-06 — METHOD-JOINT-EVIDENCE-REQUIREMENTS-PC-01

- 채택한판독:기존192요청8세션의A/B두층을같은4쌍으로검증하고새48요청의오차인증으로사용하지않는다. 원pairCSV의B값·조건부A·실제AP표본창을구분한다. 부하전background차이항/개발RMSE를관측보정·보편적오차한도·계수W불확실성으로승격하지않는다. [수치·4검증·최소조건](results/method_followup_01/README.md).
- 최소해결경로는직접같은입력전체J/AP비교또는계수오차/제어비용/AP차이근거를갖춘모형판정이다. 직접전체기기J의제어비용을별도차감/이중합산하지않는다. 고정미래일정의효과는온라인정책검증과분리한다. 현재연구목표미완료,반복수/전체기기예산/실행계획/소비claim추가0. EFT대조·기한·목적별Pareto/기본/strict/동결/experiment_ready=false유지.
- 권고와채택을구분:실제공동절감의확인에는전체기기비용을포함하는직접동일입력비교가우선이다. 작은현재이득에대한실측예산/반복수/새계획을채택하거나자동승인한것은아니다.

## 2026-10-06 — METHOD-JOINT-GAIN-PRECISION-PC-01

- 채택한 판독: 전체 mean 4결과/short·long 4결과를 재계산 없이 읽고 같은 고정 일정·공통 background의 `ΔJ=ΣΔt·W`를 검증한다. 6계산의 조건부 이득 소거 계수오차는 0.060–0.099W, 실제 계수 오차와 차등 제어비용은 null이다. 두 solver null은 계산 불가능/계수0으로 바꾸지 않는다. [전체 상태시간·5검증·재현](results/method_followup_01/README.md).
- 미채택: 역산을 신뢰구간/새 정확도 기준/실제 공동 절감으로 표현하기, 작은 J만으로 mW 정밀도 필요를 단정하기, 미래 입력 일정의 온라인 정책 승격, 새 후보 기본 채택. 현재 연구 목표는 미완료이며 EFT 대조·기한·목적별 Pareto 평가를 사용한다. 이번 PC 분석 후 manifest는 사전 등록이 아니다. 새 실측 계획/기기 작업/claim0, 기존 동결/기본/strict/experiment_ready=false 보존.

## 2026-10-06 — METHOD-JOINT-QUEUE-AREA-PC-01

- 이번규칙:현재도착큐beam의기존J/peak/기한guard에양의AP면적 비악화만추가한후보한개를별도ID로분리했다. queue75와새2seed/3전체문맥·12실행만등록,결과뒤재튜닝/새후보/seed추가0. 내부콜백ABI를재사용하되공개결과를옛beam과합치지않는다. 물리계수/parent/engine/기본불변.
- 확인:6대조모두48/48기한이나 J +0.055–+0.176J/최고AP −0.108–−0.020°C 상충으로공동비악화0/6. 현재큐의local비용비악화가미래요청포함전체창보장은아니다. GPU/겹침 항과실제도착ID·localguard·원오류/부분결과를검증했다. [수치·13검증·재현](results/method_followup_01/README.md).
- 미채택:새기본정책,실제기기절감/정확도PASS/독립확인,사후열목표/허용오차,PCcallback의휴대폰비용환산. 현재권고는강한EFT 대조와기한우선·목적별Pareto 평가다. strict/experiment_ready=false/기존FAIL/원자료/미소비기기계획보존,기기/실측/claim0.

## 2026-10-06 — METHOD-FIXED-CALENDAR-TRANSFER-PC-01

- 채택한검증규칙: 평균문맥의두기존incumbent backend/허용시각을고정해기존short/long전문맥만4회재생한다. 기존Replay의정확시각assertion은보존,별도not-before PC실행에서실제lane반환을기다리며강제처리시간/인위감속을넣지않는다. 이경로는미래일정이주어지며온라인정책이아니다.
- 확인:4/4기한48/48과J/최고AP/양의면적감소·원소스해시불변. 실제허용시각지연0이나일반/긴급응답손해가남는다. mean포함최소J이득0.002644J는미모형화실기기비용으로지워질수있다. 신규6검증/실제CLI통과; 독립세션/실제절감/미래서비스보장은미완료.
- 미채택:기본/strict/experiment_ready 변경,사후안전/정확도PASS,solver재시도/계수보정/새기기계획. [원소스·분모·시간양자화·재현](results/method_followup_01/README.md). 기기/실측/APK/claim0.

## 2026-10-06 — METHOD-JOINT-CALENDAR-PC-01

- 이번 분석 규칙: 기존 두queue/두seed/mean/48요청·20ms·사례당native120초를 유지하고 EFT 최고AP와 양의AP면적을 함께 제한한 J 최소화 참고값을4회만 계산했다. 물리계수/원planner/이벤트본문은 보존했다. 후보/정확도/안전기준 채택 결정이 아니다.
- 확인: queue75 두 사후 offline 일정은 원5단계재생에서48/48기한·ΔJ −0.052468/−0.013042J와 최고AP/양의면적 감소를 보였다. 응답 증가/다른열지표 증가·제어비용 미확인을 같이 기록한다. queue50 null은 동일격자CPU witness의4/4제약충족 근거로 불가능증명이 아님을 확인했다. 최적성/실기기절감/인과적정책/독립확인은 미입증.
- 미채택: 작은J이득의 실제정책 승격, 사후허용오차, 새로운AP/스로틀/제어비용 계수, 변경caps/finergrid/solver재시도, 기본/strict/experiment_ready 변경. 다음은 같은계획의 기존처리문맥 민감도만 제한확인한다. [소스·분모·등록·검증](results/method_followup_01/README.md). 기기/실측/기기계획/claim0.

## 2026-10-06 — METHOD-JOINT-BOUND-PC-01

- 채택한추가판독은 [현재동결식의필요조건](results/method_followup_01/README.md)이다. 동일48요청/고정시간문맥/초기이력에서전기한/EFT최고AP·양의AP면적을유지할J이득의낙관적상한을순간열입력완화/dual검사로산출했다. 후보정책/전력·열계수/정확도기준을추가하지않는다.
- 양의상한은실현가능성이나실기기효과가아니다. 새정책공동절감채택/모든방법불가능판정없음. 18적격/6기한실패분모·null보존,신규9검증/CLI통과. 기존기본/strict/동결값/experiment_ready=false/기기계획미소비유지;기기명령/실측/새claim0.

## 2026-10-06 — METHOD-WORKBENCH-READONLY-01

- 채택한 PC 연결: [저장방법론 판독](results/method_followup_01/README.md)을 `d1_simulator method-readout`으로 제공한다. 새계수/정책채택이 아닌 기한 우선·같은seed대조·전체분모·목적별상충 판독이다. 원등록6파일/모형·초기값2파일의해시와실제D→L 상태를검사한다.
- 수치반환/계수매핑/독립예측확인/정책차이식별을분리한다. 현재전용·제어비용0은가정이고,실제우월성/배포/strict승격은아니다. 새시뮬레이션/기기/계획/claim0,기존기본·동결·experiment_ready=false보존. 신규8/기존대표3검증통과.

## 2026-10-06 — METHOD-UNMODELED-COST-READOUT-PC-01

- 채택한판독경계: 기존3등록block의같은seed/처리문맥·전48요청에서서비스를먼저검사하고J/AP상충과미모형화차등비용의손익분기조건을산출한다. [원자료대응·식·해석](results/method_followup_01/README.md). 추가시뮬레이션/계수/기기실측없음.
- EFT의원callback시간0은timer부재였으므로새표에서는null,원본/기존일정은보존한다. PC시간을휴대폰J로환산하거나최소응답잔여를허용추가지연으로채택하지않는다. 비용여유/AP증가필요량은사후산술질문이며새허용폭/정확도/실제우월성승인이아니다.
- 신규8검증·실제CLI/그림통과,실제공동절감/정책우월성미완료·기본/strict/experiment_ready=false유지. 기기명령/실측/APK/새기기계획/claim0. 재현경로연결외추가후보/실측자동승인없음.

## 2026-10-06 — COMPATIBLE-TIMING-BACKFILL-PC-01

- 채택한구현경계: 분류CPU고정·탐지CPU/GPU의호환즉시배정,실제lane해제까지같은종류병행차단을과거시간전용opt-in으로연결. 실제도착큐·원기한/시간벡터유지,미래실현값/가짜전력모형없음. 기존이벤트본문/기본/strict/동결파일보존. [근거·검증](results/detector_gpu_bridge_01/README.md).
- 결과/채택보류: 새16PC사례/768요청 중12전기한충족,탐지GPU94배정. queue응답상충과burst기한실패,현재DG/CC_DG J/AP null 때문에새우월정책으로채택하지않는다. 입력은이미본자료이며사후개발·소프트웨어평가,독립실기기확인아님.
- 원래EASY/보수적backfill의앞작업예약보장을구현했다고부르지않는다. CLI모듈타입결함수정·첫실패보존,새13/관련23검증통과. 이번PC구현완료와연구목표달성을분리,experiment_ready=false/기존FAIL/미소비계획유지. 기기/실측/APK/새기기계획/claim0·자동추가실측승인없음.

## 2026-10-06 — METHOD-CONSTRAINT-READOUT-PC-01

- 채택한연결경계: 기존전체48요청결과의기한우선/5지표Pareto/명시적상대제약판독CLI. 각등록block의같은seed·모형·6사례를유지하고다른seed를paired비교로합치지않는다. [실행·근거](results/method_followup_01/README.md).
- 실제선택정책이아닌사후결과판독이며새시뮬레이션·기기명령0. 상대제약0의예시는동시비악화질문이지정확도/안전기준/사용자배포승인이아니다. 모델수치반환/지원/독립오차확인/실제정책차이를분리한다.
- 현재강한EFT기준/목적별상충평가를사용하고새공동절감우승자를선언하지않는다. 기한실패/부분비용/null/EFT동일을성공으로승격하지않는다. 기본·strict·계수·experiment_ready=false/기존원본·FAIL유지,후속실측자동승인없음.

## 2026-10-06 — DETECTOR-GPU-TIMING-REUSE-PC-01

- 확인/재사용: CAL03 exact32요청의D/A/S/O/P/W/L·입력해시·개발동결/별도확인·GPU delegate 검증을연결했다. 모델/runtime/resident기록은일치하나APK/프로토콜은달라현재요청의서비스/J/AP적격으로자동승격하지않는다. [보고/재현](results/detector_gpu_bridge_01/README.md).
- 채택한계산경계: 기존시간벡터의48정적+16기존EFT참고만수행,64새PC계산/3,072요청. 간섭1.0/1.5가정분리·전체도착분모·미측정분류CPU+GPU병행표시·J/AP모두null. 신규물리계수/가정/새기기실측은없다.
- 미채택: 모든탐지GPU배정, 현재4-cellEFT새정책, 옛전체W−새배경W로만든증가분, S26계수혼합. queue기한실패와현재지원공백을보존한다. 최소확장경계는분류CPU고정+탐지CPU/GPU선택에필요한DG/CC_DG항이며전backend표채우기는필수가아니다.
- 최소해결명세는권고·자료역할/완료조건고정이며새실행계획/자동승인은아니다. 원래실제공동절감목표/미확인오차한도는남고기본/strict/experiment_ready=false/기존동결/FAIL/미소비계획보존,기기명령0.

## 2026-10-06 — FULL-REQUEST-METHOD-PC-01

- 채택한 평가 경계: 전체48요청의 도착·기한·5단계/lane·동결 계수를 유지해 ATC/CPU 병목과 현재 큐 Pareto beam을 평가하고, 모든 미래를 아는20ms 혼합정수 참고 일정은 별도로 표시한다. 입력/후보/시간 상한/소스 해시는 각 실행 전에 등록했다. [결과·재현](results/method_followup_01/README.md).
- 종료 결과: 새PC264계산+offline8재생에서 EFT 대비 전체기한·J·최고AP·AP부담면적 공동비악화 후보0. 유예v1실패를 본 뒤 즉시배정v2를 별도 사후 개발했으나 채택하지 않는다. 결과를 본 후보변경과 새seed소프트웨어확인을 독립 실측으로 부르지 않는다.
- 확정한 사용 경계: EFT를 강한PC기준으로 유지하고 목적별 J/AP 상충과 기존split 대비 조건별 탐색을 분리한다. 동결식의 겹침J감소/AP입력증가 및 완화하한은 현재모형의 성질이지 실제열량/기기최적성/모든정책불가능 판정이 아니다. 원래 열·에너지 절감 목표는 미완료로 남긴다.
- 신규기기명령/실측/APK/기기계획/claim0. 기존모형/FAIL/strict/experiment_ready=false/사용자파일/다른worktree를 보존한다. 다음은 기존 탐지GPU 자료의 정확한 요청·resident·계측 대응 판정이며 자동실측 승인이 아니다.

## 2026-10-06 — INDUSTRIAL-SCHEDULING-PC-01

- 사용자 진행 승인에 따라 채택한 PC 경계: 현재 도착 큐만 보는 ATC/CPU 병목 적용을 기존 물리모형의 별도 opt-in으로 구현하고, 미래 도착/해당 처리시간을 아는 offline beam 참고값과 분리한다. 도착·기한·응답/lane·모형·초기자료 불변. 원 ATC/DBR 전체 재현이나 현업 폰 정책으로 부르지 않는다.
- [최종 45계산](results/industrial_scheduling_01/README.md): 각각 8/8 기한 충족. mean의 burst −0.135488J/긴급 P95 +417.101ms; queue 병목 −0.043247J/일반 평균 −110.144ms/긴급 동일. AP 부담 0·최고값이 180초 끝이어서 열 절감은 미판정이다. 작은 부분 입력의 사후 탐색이며 독립 확인·전체 48요청·폰 효과는 미완료다.
- 후보 기본 채택·strict 지원 확대·추가 실측은 채택하지 않는다. 공유 재현의 출처 확인 보완을 포함한 총 90본계산, 모형 수치 불변. 기존 모형/FAIL/종료계획/experiment_ready=false 유지. 다음 queue 전체 48요청 제한 회귀는 권고이며 이번에는 미실행이다.

## 2026-10-06 — S26-CONTRACT-MODEL-03

- 사용자 승인된 팀 회신 반영: S26 정책 비교·폰 확인의 주대상은 EfficientNet-Lite0 FLOAT32 원본 SHA `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0`. MobileNet V1은 열모형 개발·민감도 자료로분리. NPU AOT의변환출처/실행정밀도/품질과MobileNet→EffNet열전이는별도적격성이다.
- 범위채택이지모형전이·정책효과PASS또는기기실행승인이아니다. [회신·원격근거·v1수정요청](team/S26_REPLY_AND_INPUT_HANDOFF_20261006.md). S26 v1가드/oracle/FG없는재생의한계는v2수정**권고**이며담당자채택·구현은미확인. 원v1/FAIL보존, A24계수전용없음.

## 2026-10-05 — PAIR-QUEUED-SERVICE-GUARD-PC-01

- 채택한구현경계:학습기가고른PAIR의병행우선제안에현재도착대기열의상대지각검사를별도옵트인으로추가한다. 원정책/학습/동결모형을덮어쓰지않고예측상해로운결정만EFT로돌린다. long_context는WCET가아니며미래도착기한을보장하지않는다.
- [36PC비교](results/pair_service_guard_01/README.md)에서원/새seed총576/576기한충족. 새seed에너지−0.560587J/최고AP+0.225968°C상충과응답지연을보존한다. 기본정책·strict승격·실기기절감/우월성은채택하지않는다. 다른부하검증은남았고기기명령0이다.

## 2026-10-05 — UNSUPERVISED-SELECTOR-PC-01: 군집 탐색 종료

- 채택한절차: 요청이력5특징의K-means/GMM fitting과내재점수선정,개발성과를사용한별도정책연결,저장결과의사후판독. 군집자체를절감label이나새물리상태로보지않는다. [근거](results/unsupervised_selector_01/README.md).
- 주스케줄러채택은보류한다. 기한수는EFT와같고대부분fallback이며J/AP공동개선미확보. 부하유형설명보조로만보존,strict/기존계수/experiment_ready=false 유지. 이번결과는모든비지도기법불가능판정아님. 새실측/기기계획/시뮬레이션0.

## 2026-10-05 — SUPERVISED-SELECTOR-PC-01: 이력 기반 지도학습 선택 경로

- 채택한 연구 절차: 이전48도착 이력에서5특징을 추출해8기존정책의 비용/위험을 회귀한다.18조건 개발fitting/저장검증→선정동결→새seed전27조건평가.9조합은학습/선정에서제외, 독립기기자료로표현하지않는다. CatBoost미설치로기존sklearn의트리/HistGradientBoosting사용. 물리계수·정책 기본값·strict 불변.
- [결과](results/supervised_selector_01/README.md): 에너지tree는미학습군집8의16추가위반으로미채택. thermalboosting은EFT와기한수동일하나J증가/AP감소상충이므로PC분석후보만보존. 실기기 채택·공동절감·기한보장·experiment_ready승격은없다. 관측범위밖/위험fallback도기한보장아님.
- 완료594PC재생/26관련테스트, 결과후재학습0. 이전/다음 구간의 동일분포와 고정초기조건 가정을 명시하고 연속열이력·온라인 요청별전환으로 확대하지 않는다. 다음은저장실패ledger의서비스제약분해한건이며추가실측자동승인이아니다.

## 2026-10-05 — SCHEDULER-CONDITIONS-PC-01: 조건 탐색 범위 확장

- 최신 사용자 지시에 따라 이전 비교의 네 입력에 한정한 결론을 일반화하지 않고, [사전 고정한 27개 입력 조건](results/scheduler_conditions_01/README.md)과 다른 분야의 네 제어 원리를 PC에서 평가한다. 이전 알고리즘·물리 계수·기기 결과는 덮어쓰지 않는다.
- 채택한 평가 절차: 개발2seed에서 조건별 선택 동결 후 새3seed 및 3처리 문맥을 모두 보고한다. 전 요청의 기한 충족을 필수로 하고 기한 안의 P95 손해는 별도 표시한다. 에너지·최고 AP·AP 면적의 공동 개선과 서로 간 상충을 나눈다. 특정 기준과의 차이를 EFT/모든 정책 대비 우월성으로 확대하지 않는다.
- 이는 연구 절차 채택이며 새 스케줄러의 성능 채택 결정이 아니다. 미측정 상태/주파수/전력 차단/스로틀/S26 계수는 추가하지 않고, strict/experiment_ready=false 및 기기 실행0을 유지한다.
- 종료 판정: 27조건 본탐색 후 목적별 선택기를 사후 설계했음을 표시하며 개발자료만으로 고정, 새 seed112001–112003의738계산으로 확인했다. 17조건 전 기한 충족·고정병행대비 공동절감10/9조건, EFT대비 상충이다. PC 목적별 선택 경로만 채택하고 기본 스케줄러/실기기 우월성으로 승격하지 않는다. 반올림에 따른 선택 결함·CSV/export 결함을 보완하고 원 결과/소스를 보존했다.

## 2026-10-05 — SCHEDULER-ALTERNATIVES-PC-01: 비RL 비교 완료, 새 우월정책 채택 없음

- 사용자요청에따라 [5종 대안과3기준·PPO3](results/scheduler_alternatives_01/README.md)을PC에서구현·분리평가했다. 개발384→LLF선정동결→최종1056. 개발선정과최종시험을나눴으며결과후재튜닝없음. 기존물리계수·지원cell·작업/입력분포불변.
- 결정: LLF는EFT와동일하고다른후보는서비스/J/AP상충이남아새기본/기기정책으로채택하지않는다. 기존EFT를PC기준으로유지하는것을권고한다. 현재3cell모형에서queue/burst의탐지CPU수요필요조건위반과작은에너지개선상한을구체적인범위한계로기록한다. 알고리즘전체불가능/실기기용량인증/실제절감완료를뜻하지않는다.
- 완료:69검사·1440저장ledger/95040요청검증·대시보드. 다음권고는기존탐지GPU자료의정확한요청/비용/프로토콜연결판정이며자동실측승인이아니다. 기존FAIL/원자료/동결/미소비계획/strict/experiment_ready=false보존.

## 2026-10-05 — REQUEST-PPO-PC-01: 신경망 강화학습과 분리 평가, 기본정책 채택 보류

- 사용자 요구에 따라96회 표 기반 결과를 초기시험으로 한정하고3개 seed의 PPO-Lagrange 후보를 한 구조·설정으로 학습했다. [사전 계약·구현·실제 결과](results/request_ppo_01/README.md). 기존실측모형/서비스문맥가정/지원mask를 유지하고 미래정보를 차단한다. 학습6144episode, 검증720, 동결후최종768시험 완료; 결과후재학습/최고testseed선택 없음.
- 채택된 절차: 서비스와 열 기대제약을 실제등급별분모/°C·s로 학습·판독, 검증에서checkpoint선정, 세seed전부보고. 이번결과의정책채택은 보류: queue/burst서비스 개선에도 열악화조건과 seed별J/AP상충이 남는다. 수렴/최적성/실기기절감이나 strict지원승격은 아니다.
- 완료56테스트,768저장ledger/50688요청회계 및 frozenhash 확인. 다음권고는 저장배정·대기상충분해1건이며 새실측/반복학습자동승인이 아니다. 기존원자료/FAIL/종료계획/동결계수/experiment_ready=false 보존.

## 2026-10-05 REQUEST-RL-PC-01 — 제한 학습 경로 완료, 정책 미채택

- 사용자 강화학습 제안·진행 승인을 반영해 [단일 Monte Carlo 후보](results/request_rl_01/README.md)를 별도PC모드로 수행했다. 사전벡터목적·seed·입력·예산고정, 마지막표동결후평가. 새로운 전력/열가정·기존계수재적합·실기기 실행은 없다.
- 기한위반→EFT대비AP증가→J→P95의 기대비용 우선순위는 후보설계이며 개별조건의제약보장/합격기준이 아니다. 학습방문이적고압축상태이며 신규PC입력평가를독립기기확인으로취급하지않는다.
- 채택한 것은 재현가능한 제한RL비교 경로다. 후보는queue서비스악화와sustained에너지/열/응답손해로 기본/실기기정책 채택보류. 평가후재학습0·새실측승인0, 원본/FAIL/동결/strict/experiment_ready=false 유지. 다음은저장된결정에서누락상태·제약국소화; 평가자료를새후보개발에쓰면더이상독립평가가아니다.

## 2026-10-05 EMPIRICAL-REQUEST-POLICY-PC-01 — 요청별 비교 경로 채택, 후보 성능 채택 보류

- 근거: [계약·코드·60개 제한 PC 비교·44검사](results/empirical_request_policy_01/README.md). 실측 상태비용으로 새 일정을 계산하는 PC 전이 탐색을 기존 독립확인/strict 출력과 분리한다. 개발 정책별 처리시간의 공통프로필 전이는 가정으로 명시하고 미래 완료/AP/전류를 결정에 전달하지 않는다.
- 이번 완료는 기존 엔진의 요청별 자원 배정·250ms 단위 제한 유예와 다섯 방식 비교이다. 새 열/전력 계수·스로틀·정책별 맞춤서비스·독립확인·기기실행은 없다. 세션 단위 선택기를 원래 동적스케줄러 목표의 완료로 부르지 않는다.
- 후보ENERGY_AP_REQUEST_V1은 평균 지속입력에서만 제한된 상충개선이 보였고burst·긴문맥 서비스조건이 악화해 **기본정책/배포정책으로 채택하지 않음**. 해당 부정결과를 보존하며 결과를 보고 이번 후보를 다시 맞추지 않는다. 다음 권고는 저장결정의 기한여유 소모 판독으로 한정하며 새실측 승인이 아니다.
- 기존 모형/FAIL/원자료/strict/experiment_ready=false 및 S26 별도범위 유지.

## 2026-10-05 — ENERGY-AP-SESSION-SELECTOR-PC-01

- 채택 범위: 사용자 지시에 따라 [ENERGY_AP_SESSION_SELECTOR_PC_V1](results/energy_ap_session_selector_01/README.md)을 별도 PC 참고 설계로 구현한다. 기한을 지키는 등록CPU/PAR 전체 일정에서 AP 제약 아래 공통120초J 최소화를 사용한다. 계약은 대표 계산 전에 고정했고 새계수/후보 탐색/기기 실행은 없다.
- 한 번의 세션 선택으로 제한한다. 예정 도착을 미리 알지만 미래 실현 AP/전력/완료시각은 사용하지 않는다. 기존B2_PC/B3/P와 최신온라인CPU/PAR namespace를 합치지 않는다. 임의 재배정·지연의 효과를 기존 정책문맥 서비스값으로 만들지 않는다.
- 미채택: 실제AP 안전/허용 상한, 실기기 배포, 후보 우월성. 기존 energy-ap-policy-selection 차단·strict·모형byte·experiment_ready=false 불변. 참고model_only_action과 deployable_action=null을 분리한다. 한 입력에서 두 고정방식 중 하나를 고르는 규칙을 둘 모두보다 나은 새 스케줄러로 주장하지 않는다.

## 2026-10-04 — REAL-APP-BASELINE-BUILD-PC-01: 관측 연결과 검증 한계

- [원본 기반 구현·검증 기록](results/real_app_baseline_pc_01/build_pc.md). Ente 고정 소스에 시작/반환/최초 중단/compute 반환의 opt-in 로그만 연결했다. 함수 반환과 전체 사진 처리 완료를 구분하며 실사용 앱보다 나은 정책을 구현·입증한 것으로 해석하지 않는다.
- 기존 모델·계수·배정·기한·Ente timer/health/retry는 유지. Windows symlink 권한 부족 및 코드 생성 중 디스크 여유 급감은 PC 환경 차단이며 앱/정책 실패 증거가 아니다. OS 설정 변경·추가 실측·새 정책 채택은 수행하지 않았다.

<a id="real-app-baseline-pc-01"></a>
## 2026-10-04 — REAL-APP-BASELINE-PC-01: 실제 앱 후보와 직접 비교의 경계

- 상태: 사용자 지시에 따른 실제 앱 **비교 후보 선정 완료 / 원앱 실행 비교 미완료**. Ente Photos Android 전경 배경 ML 제어를 선정한다. [고정 소스·PC 결과·최소 연결 명세](results/real_app_baseline_pc_01/README.md). Band는 연구 기준선이며 현업 앱이라고 부르지 않는다.
- 기존 D1 이식 gate는 원앱 재현이 아니다. 15초 시작 유예에 6초 D1 연구 기한을 적용한 승패는 공정하지 않다. 실제 앱 개선 주장은 같은 Ente 작업/품질/전경 반응 보호 조건 안의 비교를 필요로 한다. 기존 B2/B3 연구 결과와 별도로 유지한다.
- 채택하지 않은 것: 새 admission 정책, 원앱 SLA/허용오차, 실측 계획/예산, 실제 앱 대비 우월성. 다음 원본 PC 빌드/계측은 권고 단계이며 완료 사실이 아니다. 기존 동결 모형/strict/experiment_ready=false 불변.

<a id="s26-thermal-scope-02"></a>
## 2026-10-04 — S26-THERMAL-SCOPE-02: 기기별 범위와 공통 평가 정의

- 상태: 사용자 협업 요청에 따라 **범위 변경 채택 / S26 정책 효과 검증 미완료**. [실제 근거·회신·품질 입력·ledger 인계](team/S26_SCOPE_AND_INTERFACE_20261004.md). A24 기준71a2f2b, S26 실제 읽은 원격b4f7634. 이후10/4 측정/v2 완료는 팀원 보고와 파일 확인을 구분한다.
- 9/24 S26-NPU-COLLAB-01의 XDEV-02 두 모델 CPU/GPU 축소 재현을10/11 동결·10/22 제출 필수 범위에서 보류한다. 기존 결정/결과는 보존하며 재현 완료로 표시하지 않는다. S26은 검증된 분류·순차 CPU/GPU/NPU, 열 이력→처리율·회복, 열 인지 유예/부하 상한/자원 선택의 별도 절로 구성한다. 3backend는3건 병행 지원이 아니다.
- 공통 목표는 응답·완료 요구 아래 기기 전체 에너지·열 부담의 개선 가능 조건 판정이다. 기기별 모델/엔진/프로필·확인을 분리하며 A24 CPU/GPU+S26 NPU 혼합을 금지한다. 현재 두 엔진을 단일 구현이라고 표현하지 않는다. 코드 통합은 후속 후보, 납기 보장 없음.
- S26 CompiledModel2.2.0/OpenCL/무override 근거와 Interpreter1.4.2 GPU 미지원 경로를 구분한다.9/15 override80런은 보조 이력. A24 APK의 S26 arrival 실행은 미검증이다. 기존 런타임·계수·strict·experiment_ready=false 불변.
- RL은 이번 제출 필수 범위에서 제외한다. 강한 기준선·규칙·대조군·명시적 oracle과 결과 전 등록을 우선한다. 제안 P 우월성·작은 J/AP 효과는 아직 미입증이며 A24의 CPU/PAR 비교와 혼동하지 않는다.
- A24는 열→처리시간 연결 미식별이지 스로틀 부재 인증이 아니다. S26 C2 일관성 FAIL은 같은 폰 상대 J 우열에도 제한이다. CV screening·oracle 회수율은 조건부 기술값이며 섭씨 온도 퍼센트·보편 오차 한도로 사용하지 않는다. S26 결과가 A24 미검증을 대신 채우지 않는다.
- 인계 일정/분량은10/12 초안·10/13 대조, 본문2쪽+부록1쪽/발표2장 **제안**이며 담당자 합의·측정 완료와 구분한다. 새 기기 실행·새 예산·정책 PASS를 승인하지 않는다.

## 2026-10-04 결과 전달 형식 확정

- 상태: 적용 완료. 사용자 지시에 따라 기존192요청8세션의 [발표 자료](results/final_presentation_01/README.md)를 생성했다. 그림은 모든8세션·4쌍을 포함하고 경로 예시는 시간순 첫 CPU/PAR 쌍으로 고정했다. 최소오차 사례 선별·새 적합·정확도 PASS는 없다.
- 정책 비교의 결론은 응답 개선 관측, 작은 에너지·열 차이 우열 미판정이다. 모형의 동일초기조건 AP 증가를 실제 관측 증가로 바꾸지 않는다. 기존 연구 범위·계수·strict·experiment_ready=false 유지.

## 2026-10-04 연구 본문·시뮬레이터 시연 안내 최신화 완료

- [본문](ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md)에 등록192요청 온라인8세션의 방법·관측·A/B 예측·오차·한계와 PC 시연 순서를 반영했다. PAR 응답 개선은 관측 결과, 최고AP 증가 +0.728~+0.748°C는 동일 초기조건의 모형 예측임을 구분했다. 실제 최고AP 차이 −0.4~+0.4°C를 열 우월성으로 해석하지 않는다.
- 루트 README·[통합 화면](results/simulator_workbench_01/index.html)·사용법의 오래된 ‘최신/미완료’ 안내를 현재 근거와 역사적 기록으로 정리했다. 원본·계수·기존 결과/검증 파일·strict·experiment_ready=false 불변. 새 실측/배치/적합/빌드/기기 명령0.
- 기존 CSV·공유물 해시·본문 수치·로컬 링크·HTML 구조를 대조했다. 검증 대상은 e4fd9a88 기반 문서 수정이며 기존 모델 정확도 검증을 재수행한 것이 아니다. 다음 행동 하나: 완성된 본문과 통합 화면으로 팀 결과 시연·보고에 사용한다. 추가 감사나 동일 실측 자동 반복은 없다.

## 2026-10-04 지속192 CPU/PAR 확인8 완료·제한 시뮬레이터 연결

- [보고서](ENERGY_THERMAL_OVERNIGHT_RESULTS_20261004.md), [대시보드·재현](results/online_policy_study_01/overnight_sustained_run01/README.md). 별도opt-in192/400ms·CPU/PAR4쌍8세션전부완료. 본1536+warmup64=1600/runtime32/staging8·56/pull·push·설치각1/ADB6647/2588.054초. 재시도·추가계획0. 앱cleanup8·회수8·host정리8·설치정리1·최종ps대상부재·parent/child exit0. 옛FAIL/원본/미소비계획/기본/strict불변.
- 모두기한192/192. PAR실제CG_DC병행21.924~22.581초·긴급P95쌍별127.912~131.381ms단축. 도착B J오차−5.541~+8.210J/AP MAE0.186~0.559°C. PAR−CPU관측J−5.304~+11.682·평균+1.195·SD8.069(4쌍,기술통계). 동일초기동결예측−2.091J/최고AP+0.728~+0.748°C와구분;작은J/AP정책우열은미판정.
- 관련Android10/Python22·실제Check기기0·8세션독립적분/CSV/hash·portableCLI2검증. 서명APK5fb72bf2…·계획62f4fa62…·원모형5682082a…byte불변. 등록입력조건부A/도착B 전이평가·공유번들완료,임의도착/열처리율/미래오차한도는미지원. accuracy_pass/policy_winner=null, experiment_ready=false. 다음PC행동하나:제한된결과를연구본문/시연의응답개선·열상충·에너지우열미판정에사용. 같은실측확대/추가보정자동실행없음.

## 2026-10-04 최대6시간 자율 작업 제안 — 실패 복구 포함

- [시간·입력·예산·중단·마무리](ENERGY_THERMAL_OVERNIGHT_PLAN_20261004.md). PC90분→기기 최대180분→분석75분→Git15분. 단일192요청/400ms CPU–PAR 후보를 검토하고 적격일 때만4쌍8세션 제안. 현재Android/host96고정이므로 opt-in구현·PC검증·서명빌드·새계획동결 전에는 실행 불가. DESIGN_PROPOSED_NOT_RUN_READY.
- 사용자 추가 요청의 실패 수정은 최대2개 추가세션/총10시도/실행계획최대3 안에서 재현된 코드 오류만 PC수정 후 새ID로 진행하도록 제안. 기존계획재개·환경완화·모형오차 때문에 재측정 금지. 총2000추론/runtime40/staging10·70, push·설치·설치본pull각최대3. 기존식 참고예약9610초/ADB32600은192경로 재검증 전 확정 실행예산 아님.
- 이번에는 계획 작성·산술 대조만, 기기/빌드/실행계획/claim0. 기존원본/FAIL/모형/strict/experiment_ready=false 보존. 다음 행동: 실행 지시 후90분 PC gate부터 수행; 안 되면 기기 단계 없이 가능한 분석·문서·Git까지 완료. 시뮬레이터 산출물 마무리와 정책 절감 입증은 구분한다.


## 2026-10-04 CPU–PAR 판별 가능성 PC 완료 — 동일 배치 확대 보류

- [판정·가정·재현](results/online_policy_study_01/policy_feasibility_pc_v1/README.md), [민감도 화면](results/online_policy_study_01/policy_feasibility_pc_v1/evaluation/index.html). 기존96요청 CPU/PAR만 선정, 새입력검색/적합/예측/실측0. 관측 차이 +1.657/−42.939J의 기술적SD31.534J는 두 비교뿐이며 미래분산이 아님. 동결 차이1.712761J에 알려진분산 정규근사를 가정하면2661쌍; 실제 필요횟수·권고가 아니다. 8쌍 예시에는SD1.729J 이하가 필요하지만 달성근거 없음.
- **현재1.713J 입증용 확대 반복은 권고하지 않음.** actual_required_pairs/AP표본수/최소실용J/허용AP증가=null, run_ready=false. α.05·power.8은 민감도 가정이며 PASS 기준 아님. 새 실측계획/claim0; 원래 에너지·열 최적화 목표를 완료했다고 하지 않음. 기존모형/FAIL/default/strict/experiment_ready=false 보존.
- 관련PC4·CLI·결측/편향 비소거·원본hash·그림 검증. 다음 행동 하나: 이 종료 판정을 포함한 제한된 시뮬레이터 결과를 연구 본문에 반영. 향후 실측은 의미 있는 효과·열 허용치와 차분변동/편향 관리 근거가 있을 때 재검토하며 같은 감사/배치 자동 반복 없음.


## 2026-10-03 확인6 오차와 정책 차이 PC 대조 완료

- [판정·재현](results/online_policy_study_01/policy_resolution_pc_v1/README.md), [결과 화면](results/online_policy_study_01/policy_resolution_pc_v1/evaluation/index.html). 기존 확인6 전부 보존·새 적합/실측0. 동일 초기6×정책3의 제한된 예측에서 PAR−CPU J −1.712761, 최고AP +0.793~0.816°C; SER +2.481829J/+0.194~0.223°C. 기존 관측 비교4개와 원 예측 J6개 재현.
- 이 96요청에서 CPU/PAR 기한96/96, SER61/96; PAR 긴급P95 −469/−456ms. 그러나 잔차2×2 대입 J 차이는 PAR −40.968~+7.378, SER −39.019~+5.083으로 부호 비보존. 사후 산술이며 미래 bound/신뢰구간 아님. 관측 서비스 결과·제한 예측 허용, 작은 J/AP 정책 우열 보류/기존 선택 차단 유지. 기본/strict/experiment_ready=false·동결/FAIL 불변.
- 관련 PC7 통과·실제CLI/그림/CSV/hash 확인. 기기/APK/계획/claim0. **다음 행동 하나: 이 결과를 연구 본문의 CPU/PAR 응답–발열 상충과 에너지 우열 보류에 반영.** 동일 실측 반복·새 후보 자동 탐색 없음.


## 2026-10-03 GitHub 공유·S26 최신 계측 인계

- [팀 안내](team/README.md), [S26 전달문](team/S26_HANDOFF_20261003.md). A24 PC 완료5b3de27은 실제 원격 반영 확인. S26 원격cea8eae를 fetch/읽기 전용 대조하여 EfficientNet NPU20런과 MobileNet N1300/M2양방향/M1의 완료 사실을 반영했다. 오래된 “NPU 전부 미검증” 안내를 최신으로 쓰지 않는다. S26원본 전체 재분석/브랜치merge/기기 실행0.
- 기존 export·에너지 적격성·두 작업 대표 품질/요청 경계를 우선 연결한다. 추가 N1300/M1/M2 CPU 피해자 등은 실제 사용할 연구 범위별 **권고·미승인**, 새 계획/claim 없음. 기기별 계수/엔진/모델·개발/독립확인 분리, 기본/strict/experiment_ready=false 유지. 다음 협업 행동은 담당자의 기존 증거/미보유 항목 회신; A24 다음 PC 분석은 기존 확인6의 오차와 정책 차이 대조로 유지한다.


## 2026-10-03 배경4 PC 식별 완료 — 전력 초기화 수정·gamma 미채택

- [보고서·재현·한계](results/online_policy_study_01/background_identification_pc_v1/README.md), [대시보드](results/online_policy_study_01/background_identification_pc_v1/index.html). 적격 v4 C0/CPU + v6 PAR/C0 두 block 재사용. frozen model의 preload −20~30초를 background 판독기10~30초와 대조해 구현 오류 수정; 기존 수치·원자료 보존/legacy 재현 제공. 120초 J 오차 +4.041/−2.162/−3.252/+3.585, 평균절대8.363→3.260J. AP 초기화·계수·MAE 불변(평균0.184408°C).
- 등록된 단일 gamma 공통최적0(무제약−0.020551), 세션별 부호 불일치. 세션제외MAE0.184408→0.199300, block제외0.203042°C로 악화해 **미채택**. 수치적 rank와 물리적 유효성 구분. 과거10초 잔차 유지도 미래10/30초J 악화. CPU 활동은 동시성 기술통계만, GPU/무선 에너지 귀속·독립PASS 아님. 기본/strict/experiment_ready=false 유지.
- PC 관련 검사·56개 앱 입력 재현·실제 CLI/원본 수치/동결hash/공유그림 검증 완료. APK/기기/실측/새계획/claim0. 기존 후보/FAIL/종료 계획 보존. **다음 행동 하나: 기존 독립 확인6의 정책별 J/AP 오차를 동결 정책 차이와 대조해 판정 가능/보류 경계를 결과 화면에 연결.** 미채택 후보를 위한 개발4 반복·확인12 자동 실행 없음.


## 2026-10-03 재개 — v5 host 연결 오류 보존 / v6 남은 개발2 완료

- [결과·소비·원본·재현](results/online_policy_study_01/background_activity_run04/README.md), [대시보드](results/online_policy_study_01/background_activity_run04/index.html). v5 staging에서 host127.0.0.1:5037 client 연결 rc1(21.125초) 중단, launch/추론0·ADB68/142.983초. 같은 daemon 식별과 후속 cleanup 성공; 내부원인 미확정·stopped 보존. 사용자 추가 실행 승인으로 별도 campaign retry1회 v6 준비·Check·실행, gate/timeout/APK 수정0.
- v6 PAR96→C0_POST 개발2/2 적격, 본96+warmup16=112/runtime8/staging2·14/설치본pull1/tracepull2/APK0/ADB1669/735.433초. 앱cleanup2·host force-stop2·최종ps 대상부재, parent/child exit0·이후PC 부재. trace2 BOOTTIME/8CPU/24bin/loss 통과. 시작AP28.9/29.5°C 범위밖. PAR 실제병행13.051초, J153.440→150.563(−2.877), AP MAE0.225°C; C0 J129.789→143.740(+13.951), MAE0.157°C. 조건부·개발/전이 자료이며 정확도PASS 아님.
- 기존 v4 C0·CPU와 이번 v6는 별도 block이며 v4 완주로 합치지 않는다. 원본/FAIL/registry/계수/기본/strict/experiment_ready=false 유지, 새fit/채택/독립확인0. Check 기기0·실제경계/CSV/hash/공유그림 재현 통과, Android/빌드0. **다음 행동 하나: 적격 네 개발 자료의 과거 시스템 활동과 잔차에서 gamma 분리 식별 가능성 PC 검사.** 추가 실측 자동 실행 없음.

## 2026-10-03 v4 두 세션 적격·조회 timeout 종료 / v5 이동 전 미소비 보류

- [결과·소비·수정·재개 명령](results/online_policy_study_01/background_activity_run03/README.md). v4 C0/CPU2적격, PAR 준비 ls3초 timeout; 원인미확정·최종 대상 ps 부재/trace 회수. 확인추론120/runtime12/ADB1803/817.657초. trace 설정 수정 실제 성공, CPU 집계 동일성 최적화·부분 분석/분모 보존 PC15통과. APK/계수 불변.
- 사용자 추가 실행 승인에 따른 새 v5 PAR→C0 개발2 계획(112추론/2402초/ADB6618/설치0) Check 통과. 사용자 5분 뒤 이동 안내로 **claim 전 보류**; Run/추가 기기 조회/소비0, 실패/stopped 상태 아님. 다음 행동: 연결과 충분한 시간이 있을 때 v5만 현재 gate로 실행. 완료 두 세션 반복/종료 v4 재개/모형 자동채택 없음. 기본/strict/experiment_ready=false·원본/FAIL 보존.


## 2026-10-03 trace 설정·내용 검사 최소 수정 채택

- 기존 DISCARD와 producer flush 누락의 공식 parser 플래그를 실제 원본에서 확인. RING_BUFFER/flush5초와 loss 전체 SQL, 회수 후 CPU/clock/coverage 검사로 수정한다. 계측 프로토콜 변경 개발 자료이며 기존 원본의 오류 판정을 덮어쓰지 않는다. [근거·정확한 예산](results/online_policy_study_01/background_activity_pc_v1/README.md), [검증](results/online_policy_study_01/background_activity_pc_v1/plan_v4/verification.json). 다음 행동: 현재 A24/설치본/환경을 실행기 gate로 확인하고 v4 1회 실행·판독.


## 2026-10-03 배경 활동 개발4 v3 Run02 — 수집 완료·trace 계약 부적격

- [보고서·소비·재현](results/online_policy_study_01/background_activity_run02/README.md), [대시보드](results/online_policy_study_01/background_activity_run02/index.html). 새 승인 v3 단1회, C0→CPU96→PAR96→C0 4/4 완료. 본192+warmup32=224/runtime16/staging4·28/설치본pull1/tracepull4/APKpush·설치0/ADB3260(실행기3259+선택1)/기기작업1243.243초, 원본 FINAL_RECEIPT 완료·계획 소비/종료. 연결소실/timeout/추가실행 없음.
- PAR 실제병행13.154초. 120초 관측→기존 동결 조건부J: CPU171.210→161.438(−9.772), PAR157.006→152.319(−4.688). AP MAE0.207/0.278°C(common35초→냉각말); C0전후138.729/141.342J. 시작AP27.6–28.2°C 원래 범위 밖/계측변경 개발 자료이며 strict·정확도·정책 우월 PASS 아님. 계수 적합/후보채택/독립확인0, 기본/strict/experiment_ready=false 유지.
- 앱 정상cleanup4 +host정리4/최종 저장ps 대상부재; parent/child 종료exit0/뒤PC에서PID부재. 원본17051파일205776672byte inventory·4trace 보존. 공식TP v58.2 hash확인/SQL16회 exit0; 네 trace 모두 config_write_into_file_no_flush=1로 사전 내용검사 거부. 메모리 설정 경고이지 실제 손실·무선 원인 확정 아님. file_write와flush 주기가 다른 점 확인. system CPU귀속null; selfCPU·과거입력56개 별도판독. 새 readout PC2검사 통과, Android/빌드0.
- 다음 PC 행동 하나: 확보된 네 trace의 flush 설정 경고와 실제 loss/clock/CPU coverage를 분리해 판독 보완. 원래 부적격 판정 보존; 새 기기계획/실측 자동추가 없음. 아래는 과거 기록.


## 2026-10-03 결정 — 새 개발4는 설치 없는 v3로 분리 (PC 구현 채택·실기기 미승인)

- [계획·예산·명령](results/online_policy_study_01/background_activity_pc_v1/README.md), [검증](results/online_policy_study_01/background_activity_pc_v1/plan_v3/verification.json). 도움말 수정 소스를 새 ID BACKGROUND-ACTIVITY-DEVELOPMENT-03에 동결. plan_v3 SHA dbec1de3…ff501. PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED; 출력/registry/claim 없음. stopped v2·원본 보존.
- 설치된 동일 APK9d8d55c2…e73fd932 재사용, installed_only=True·불일치 중단·배포 fallback 없음. 개발 C0→CPU96→PAR96→C0, 본192+warmup32=224/runtime16/staging4·28/설치본pull1/tracepull4/APKpush·설치0/고정840초/총4454초/ADB13036/retry0. 기존 부하·900ms sampler·조회 주기·gate 유지.
- 관련 Python9 및 실제 PowerShell Check/Device·server probe 금지 Check 통과. 실제 공유 runner 설치 없는 호출 연결/설치본 불일치 오류 보존 검증. Android·APK 재빌드0, 기기명령·Run0. 도움말 옵션 외 실제 trace 시작·내용·clock/loss·TraceProcessor·추가 계측 비용·장시간은 미검증. 기존 모형/기본/strict/experiment_ready=false, gamma 미채택 유지.
- 다음 행동 하나: 새 개발4 계획의 기기 실행 승인 후 현재 A24/설치본/환경·trace gate로 1회 수행. 이번 진행은 PC 준비까지이며 이전 종료 계획을 재개하지 않음. 아래는 과거 기록.


## 2026-10-03 배경 활동 개발4 Run01 — trace help 판독으로 앱 시작 전 중단

- [실행·소비·수정·근거](results/online_policy_study_01/background_activity_run01/README.md), [종료 화면](results/online_policy_study_01/background_activity_run01/index.html). 승인된 plan_v2 1회 실행: A24/설치본·host 환경 통과, 첫 C0 trace 준비의 `perfetto --help` stderr3804byte/exit1을 host가 실패로 판독. timeout/연결소실·AP 예측실패 아님. 필요한 옵션은 도움말에 있으나 실제 trace 지원·내용은 아직 미검증. stopped_no_resume로 보존.
- APK9d8d55c2…e73fd932 설치·해시 검증. 실제 앱시작0/본·warmup·runtime0, 준비1/staging1·7/설치본pull1/APKpush·설치각1/trace0/ADB89(실행기88+선택1)/실행누적63.753초·wall92.049초. CPU/PAR/마지막C0 미시도, 공식창·새J/AP·후보식별 없음. 앱cleanup해당없음, 설치·실패단계 host정리 각1/종료ps대상부재 확인.
- 원본484파일 inventory·원래 오류/후속 non-JSON 회수오류·checkpoint·receipt 외부 `background_activity_run_v2`와 분리 `background_activity_run_v2_pc_analysis` 보존. 상세host_identity=null·PID만 완전소유권으로 간주하지 않음. 뒤의PC조회에서parent/child부재.
- help 조회만 exit0/1+Usage+필수옵션 모두 확인하도록 최소수정, 원본stderr fixture로 Python8 통과. 다른조회/gate/timeout/재시도불변, Android/추가빌드0. 수정후기기실행0·새계획/claim0·종료planCheck기기전차단/원래plan·APK·모형hash불변. 기본/strict/experiment_ready=false 유지.
- 다음 행동 하나: 도움말 판독 수정본을 별도 미소비 계획의 소스해시에 연결. 종료plan_v2 재개·기존4세션자동추가 없음. 아래는 과거 기록.


## 2026-10-03 시스템 활동·과거 sampler 입력 및 개발 대조4 PC 준비 완료

- [계약·APK·예산·명령](results/online_policy_study_01/background_activity_pc_v1/README.md), [준비 화면](results/online_policy_study_01/background_activity_pc_v1/index.html). opt-in APK에 process CPU·과거10초 전력 입력을 추가하고 기존 수집기에 UUID 소유 trace 시작/단일 회수를 연결. GPU/무선 전력 식별·새 controller 아님. 이전 gamma 후보 미채택·기본/strict/experiment_ready=false 유지.
- C0→CPU96→PAR96→C0 개발4만 동결. plan_v2 SHA a214b53e…ad78d97e, APK9d8d55c2…e73fd932. 본192+warmup32=224/runtime16/staging4·28/설치본pull1/tracepull4/APKpush·설치각최대1/고정840초/예약4454초(74분14초)/ADB13036/retry0. v1은 미소비 PC 초안으로 보존. 최종 계획은 PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED, 새출력·claim 없음.
- Python 신규7+관련9 통과, 기존cleanup3도 통과. Android12 callback/계약/회귀·서명빌드·실제PowerShell Check 및 device금지 Check 통과. trace 실제 SQL/플랫폼/내용/손실·새APK 계측비용/장시간 미검증. 이번 기기명령·실측·Run0.
- 채택한 결정은 PC 구현·개발4 준비에 한정된다. 기기 실행은 미승인이다. 다음 행동: 별도 승인 후 개발4 대조를 현재 A24/설치본/환경·trace gate로 실행하고, 회수 자료의 clock/손실/CPU 활동 및 계수 식별을 먼저 판독. 독립확인12/후보채택은 자동 진행하지 않는다. 아래는 과거 기록.


## 2026-10-03 기존 자료 기반 배경·AP 후보 판정 완료 — 미채택

- [분석·필요 실측 판정](results/online_policy_study_01/causal_background_pc_v1/README.md), [화면](results/online_policy_study_01/causal_background_pc_v1/evaluation/index.html). 기존 개발3만으로 gamma1개=0.126287 추정, 이미 본 확인6 사후평가. 새 독립확인0. AP 조건부 평균MAE0.38915→0.29882°C(4개개선/2개악화), 마지막CPU 최대4.2196→3.0403°C; 원인해결·정확도PASS 아님.
- 개발 세션 제외 gamma0.01950–0.19914, 평균MAE0.45832→0.47809°C 악화. 30초 미래J MAE3.91198→4.16008J 악화. 계수 실용 안정성/정책사용 근거 부족으로 후보미채택, 둘째후보탐색0. 기존동결/default/strict/experiment_ready=false 불변.
- 최대18세션을 바로 실행하지 않음. 기존4상태전력·서비스는재사용; 시스템활동 동시관측을 추가한 C0→CPU96→PAR96→C0 개발4 대조를 우선PC구현할 것을 권고. 산술224추론/runtime16/고정840초, 정확한 총시간·ADB·반복정밀도 미확정/실행계획·claim0. 확인12는후보식별전보류이며사용자실행승인아님.
- 관련PC13검사/실제CLI·미래정보변조·원본9세션J/AP일치·해시불변/그림검사 완료. 이번기기/실측/빌드0. 다음 행동: 대조4에 필요한 시스템 관측과 기존 sampler의 과거입력 경로를 PC 구현·검증. 아래는이전기록.

## 2026-10-03 에너지·열 최적화 목표 유지 — 해결 설계 제안

- [새 해결 계획](ENERGY_THERMAL_COMPLETION_RECOVERY_PLAN_20261003.md). 응답 비교/우열 차단만으로 완료하지 않는다는 사용자 목표를 재확인했다. 기존 자료의 단일 후보 식별 검사→필요한 시스템 활동 관측·개발 최대6→모형·정책 동결→대응 확인12를 한 캠페인으로 구현할 것을 권고한다. 현재는 DESIGN_PROPOSED_NOT_RUN_READY이며 실행승인·새Run계획·claim은 아니다.
- 부하/배경/계측 활동을 분리하고, 개방루프 예측과 과거관측까지만 쓰는 온라인 갱신 예측을 별도평가. 후보1개·확인재보정0·추가세션자동생성0. 18세션/본1536+warmup144=1680/runtime72/staging18·126은 제안. trace기능·비용·ADB추가명령/최종시간은PC구현과기기지원확인전미동결. 기존모형/FAIL/기본/strict/experiment_ready=false유지.
- 다음 행동: 단일후보의기존자료식별과앱과거표본온라인예측을PC구현·검증하고필요한관측/예산/판독을동결. numericAP는host관측이고실시간앱입력으로가정하지않음. 이전 '본문정리만 다음행동' 권고는완성경로로승계하지않음. 이번기기/빌드/추론/실측0. 아래는기존이력.

## 2026-10-03 작업 후 유휴 오차 국소화·정책 사용 경계 구현

- [판독·한계·재현](results/online_policy_study_01/post_idle_pc_v1/README.md), [그림](results/online_policy_study_01/post_idle_pc_v1/index.html). 마지막CPU75–120초82.138J vs 첫CPU46.551J, 활성/대기0; AP최고36°C 첫관측약99.197초. host명령120 vs119/실패0, 화면·비충전·thermal 조건 관측상유지. 추가요청/명령급증으로 설명되지 않지만 외부앱/OS/통신/숨은열 원인은미확정. 동시활동 계측이 없어 같은기록으로원인확정불가.
- 수치재생은 유지하고 `decision_support`와 `--purpose` 검사추가. 에너지/AP정책선택은 미래오차한도미검증으로차단, 미래bound=null/동등성미입증. 사후최대오차를보편한도로쓰지않음. 큰예측실패자체해결/모형완성아님. 기존모형/strict/기본·experiment_ready=false 보존, 재적합/제외/기기/계획/claim0.
- 관련PC6검사·원본6세션/144창·실CLI수치불변/정책선택출력차단·freeze해시불변 확인. 다음 행동: 확보한 정책 비교를 서비스 제약 충족·응답 차이와 에너지/열 우열 유보로 구분해 연구 본문에 연결한다. 새변수없는동일실측반복은 하지않는다. 아래는이전이력.

## 2026-10-03 분리 부하 개발3·동결·독립 확인6 완료

- [결과·소비·재현](results/online_policy_study_01/separated_power_final/README.md), [대시보드](results/online_policy_study_01/separated_power_final/index.html). 준비 중 silent/reaped 조회 누락을 공식창 승인 전 최대1회로 분리하고 새 관측 성공 후에만 진행하도록 보완했다. 기존 timeout/안전 gate/APK 불변. 실제 원인 미확정; 성공 run04의 누락허용 사용0회.
- 앞선 CPU/PAR 개발2를 보존하고 SER개발1→freeze19637bf1→독립확인6 완료. v1/v2 stopped_no_resume, v3 미소비 초안, v4 완료. v4 본672+warmup56=728/runtime28/staging7·49/pull2/APK0/ADB4681/2262.958초. 이번 턴 실패 포함840 확인 추론; 이전v1까지952와 미회수2세션의 보수적 본0–192 별도. 앱cleanup7·회수7·host정리7·종료시ps부재, parent/child exited.
- CPU/PAR 모두96/96 마감, SER 두 번61/96. PAR 긴급P95는CPU보다456–469ms 단축. 예정 도착 J오차 −35.497~+6.004J, AP MAE0.151~0.927°C/최대4.213°C. 마지막CPU의 부하후유휴 전력·AP상승은 미예측이므로 작은 에너지/열 정책 순위와 원래 목표 전체 완료는 미판정. 제외/재적합0; 기존 AP557fbe·기본·strict·experiment_ready=false 유지.
- PC12검사/소스110/5초창144 합/CLI/오차재계산 통과. 다음 행동: 기존 마지막CPU 유휴 상승의 기록 경계를 국소화하고 배경 변동 미예측 조건을 명시한다. 추가 실측 자동반복 없음. 아래는 과거 이력이다.

## 2026-10-03 분리 부하 Run01 중단·첫 개발 자료 보존

- [결과/소비/재현](results/online_policy_study_01/separated_power_run01/README.md), [관측 화면](results/online_policy_study_01/separated_power_run01/index.html). 공간 확보 후 새계획1회 실행: CPU개발1 적격, 병행개발 준비 listing3초 timeout으로 stopped_no_resume. 개발잔여1/확인6 미시도, 추정·동결0. 원인미확정, 직후회수성공을 보존.
- 확인소비 본96+warmup16=112/runtime8/staging2·14/pull1/push·설치각1/ADB877/428.988초. 두 번째 terminal미회수로 미확인본0–96 별도. 첫앱cleanup완료/두 번째미확인; host세션정리2+설치정리1/최종ps부재. 기존계수·FAIL·strict·experiment_ready=false 불변.
- 첫120초165.373J, 초기AP32.6, CPU단독만관측,96완료/54마감. 새예측/정확도PASS없음. 다음PC행동: 성공개발1 보존하에 반복된 준비조회 timeout의 관측/중단 경계 검증. 기존계획재실행0. 아래는과거기록.


## 2026-10-03 분리 부하 개발3·혼합 확인6 PC 준비 / 저장공간 보류

- [계약·APK·예산·명령](results/online_policy_study_01/separated_power_v1/README.md). 개발 분류32/탐지32/혼합32 분리, 확인48:48 교대96. 같은정책3, 새정책0. AP557fbe 유지,50초부하전전력+4상태증가분 및서비스평균만개발자료로고정. 사후후보2개미채택보존.
- 새계획 separated_power_plan_v1 SHA0340473b…eac7f, APK5c284190…ba4c. 9세션/본864+warmup72=936/runtime36/staging9·63/pull2/APKpush·설치각1/고정1890초/예약8310초/ADB29200/retry0. PC준비완료·기기미검증·미소비,출력/claim없음.
- Python15/Android8/서명·소스/실제Check 통과. 기존mode/기본/strict/experiment_ready=false 불변. 초기SDK누락·서명환경오류는PC에서수정,최종프로젝트인증서일치.
- 현재C:약128MB로host2GiB운영예약부족. 기존빌드중간폴더삭제는자동검토 blocked by policy로거절되어삭제0. 사용자에게공간확보요청;이번기기명령0. 다음행동:공간확보후동일계획/현재기기gate를확인해승인된묶음실행. 아래는과거단계.


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


## 2026-10-03 계측 대조 완료·전력 보완 대상 특정

적격4를 두block에서 확보하고 냉각 중단1의 실제소비/부분자료를 보존했다. 조회900ms는표본위상을 넓혔지만J차이방향이 두대비에서 불일치하고 기존모형 오차도 남았다. 새정확도PASS/기본채택은 하지 않는다. 관측J 범위보다 세션별20초배경W를 전체창에 전용한 예측변동이 커, 다음후보는 pooled resident 항이라는 단일최소구조만 검토한다. 기존13적격을 쓰면 새후보에 대해서는 사후개발/평가이고 원래동결 확인은 그대로 유지한다. 연구 전체목표는미완료이며 기존모형/strict/default/experiment_ready=false를 보존한다. [근거](results/online_policy_study_01/sampling_run01_complete/README.md).

## 2026-10-02 전력 표본 위상 민감도만 별도 대조 — 채택

관측 사실은 개발1초 조회가2초 부하 반복의8구간 중2구간에 집중됐다는 것이다. 센서 내부 갱신/aliasing 편향 크기는 미확정이다. 기존 승인에 따라 같은APK에서1000/900/900/1000ms,96요청 병행4를 수행하며 원래계수 적합이나 새로운 정확도 PASS는 하지 않는다. sampler만 명시적opt-in으로 분리하고 나머지 정책/상태/환경/cleanup은 유지한다. 900ms 추가 계측 비용을 포함한 프로토콜 비교이며 절대 기준 계측이나 순수aliasing 인과실험으로 표현하지 않는다.

## 2026-10-02 온라인 정책 독립 평가 완료·정밀 비용 모형 미승격 — 채택

사용자 자율 실측/실패 복구 승인으로 온라인 CPU/CG_DC병행/CG_DC직렬의 개발3→동결→확인6을 완료했다. 구성 변경으로 Activity가 파괴된 새 증거에 한해 별도 온라인 Activity의 common configuration callback을 같은 소유자에서 처리했고, 기존 Activity/실제 onDestroy 취소는 보존했다. 실제 구성 변경 callback은 새실측에서 발생0이므로 그 내성은 PC검증 범위다.

기존 적격 개발2와 신규1의 APK 차이는 기록하고 실패·소비·구 프로토콜을 보존했다. 후보군/추정법/입력/마감/gate는 실행 중 바꾸지 않았다. 확인자료 재적합0이다. 새6 확인의 서비스100%/AP오차와 에너지 과소예측을 모두 채택 결과에 반영하며, 작은 정책차이를 구분할 정확도가 부족하므로 새 후보를 default/strict에 승격하지 않는다. experiment_ready=false 유지. 원래 목표의 정책/입력→일정/J/AP→새 관측 연결은 실제 구현·검증됐으나 안정 절감/열 우월성은 미입증이다. [수치·소비·판정](ONLINE_POLICY_MODEL_STUDY_20261002.md).

## 2026-10-02 원래 목표를 제한 도구 완료로 대체하지 않음 — 채택

사용자가 원래 목표 달성을 다시 명시했다. ‘제한 시뮬레이터 완료 후 팀 공유’는 하위 작업의 종료 설명으로만 남기며 전체 프로젝트 종료 결정으로 사용하지 않는다. 완료 기준은 자원 배정·시작 대기의 서비스/J/AP 예측과 독립 정책 차이 판독이다. 이번에는 기존 계수를 바꾸지 않고 예정 입력→일정→W/M0 계산을 연결했다. 계산 가능·계측 지원·독립 오차 확인·정책 차이 식별을 분리하며 PC 결과를 실측 검증으로 승격하지 않는다. [코드/검증/구체적 다음 작업](results/policy_prediction_bridge_01/README.md). 기기 작업0, 실행 계획/claim0.

## 2026-10-02 등록된 조건부 AP 확인6·제한 시뮬레이터로 연구 종료 (완료)

새 확인4의 적격 완료를 기존2와 별도 block으로 보존해 사전 지정6개를 판독했다. 동결M0 유지·M1 미채택·재적합0이다. AP 평균/최대/최고 및 냉각 방향/미식별을 공개하되 근거 없는 정확도 PASS나 정책 우월성을 만들지 않는다. 등록된 실제 일정＋common+35초 전AP에 한해 한정 시뮬레이터에 연결하고 원래 strict/default는 유지한다. 기존 W식의+5.44–+20.45J 오차와 작은 병행/유휴 이력 한계 때문에 임의 도착J/AP·열 피드백의 지원을 확대하지 않는다. 연구 결과와 소프트웨어의 제한 완료를 전체 물리 모형 완성과 구분하고 experiment_ready=false를 유지한다. 추가 실측·새 후보·새 계획 자동 실행 대신 완성된 범위의 결과 공유로 종료한다.

## 2026-10-02 사용자 중지 보존·동결 M0 재사용·확인4 신규 실행 (승인)

후속02는 개발5＋기존C의 개발6과 M0 동결, 확인2 완료 뒤 사용자 이동 요청으로 staging 중 중지됐다. 모형/연결 실패로 변경하지 않는다. M1은 사전 LOSO 선택 규칙을 충족하지 못해 미채택이며 확인 자료로 다시 맞추지 않는다. 새 승인으로 잔여4만 별도 plan_v3 ID/registry에서 실행한다. 원래2개 확인을 반복하지 않고 APK·수식·초기화·계측·timeout·gate·계수 변경0, host subset만 보완한다. 휴지 공백과 환경 차이는 별도 block 한계로 유지한다. 사용자 목표의 제한 시뮬레이터 완료와 일반 열 피드백 정책 검증을 구분하며 default/strict/experiment_ready=false를 유지한다.

## 2026-10-02 — 미완료 실측의 신규 후속 block과 적격 C 재사용 (사용자 승인)

- 사용자의 “미진행된 실측 마저 진행” 지시로 새 follow-up 02를 한 번 실행한다. 종료된01의 소비 기록은 유지하며 재개하지 않는다. 적격 첫 C만 원자료·manifest·판독 입력 해시로 고정해 개발 자료로 가져오고 나머지 개발5 이후 동일 사전 계약으로 추정/동결·확인6을 수행한다. 실패 L35는 적합 표본이 아니며 소비·실패 분모에서는 지우지 않는다.
- APK·앱/센서·조회 주기·timeout·부하·추정 격자·선별·중단 기준은 그대로다. 과거 timeout 내부 원인은 미확정이고 이번 후속 경로 구현은 그 원인의 해결이 아니다. 개발 중 공백/실패 준비 이력/환경 차이는 사전에 기록하며 순번의 산술 균형을 실제 환경 균형으로 해석하지 않는다. 재사용 C는 신규 독립 확인으로 집계하지 않는다.
- 새 실행 예산과 이전 소비를 구분한다. 최대11세션/280추론·기기9710초＋PC3600초/35600ADB·배포0, 실패/미식별이면 다음 단계 없이 종료한다. 확인 후 재적합·새 후보·추가 실행은 없다. 기존 원본/동결/default/strict/experiment_ready=false 보존. 근거: [실행 전 후속 계약](AP_MODEL_COMPLETION_STUDY_20261002.md).

## 2026-10-02 — 개발·동결·확인 종료형 연구 실행 연결 (사용자 승인)

- 실제 실행은 첫C 적격 완료 뒤 다음 L35 준비의 단발 uptime client timeout으로 종료됐다. 원인 미확정이고 재현 가능한 실행 코드 결함은 확인되지 않아 조건/timeout을 바꾼 자동 재실측은 하지 않는다. 개발/확인 모형 적합 실패와 자료 획득 실패를 구분한다. 일부C의 작은AP오차를 새 후보 독립 확인으로 승격하지 않는다. 계획/소비/실패·부분 회수/정리 결과를 최종 기록한다.

- 사용자 ‘계획 마무리 후 연결된 기기에서 실측까지 진행’ 승인으로 [사전12세션 설계](AP_MODEL_COMPLETION_STUDY_20261002.md)를 실제 host 경로에 연결했다. 신규 입력/모형 후보 추가/식별 기준 완화는 하지 않는다. 실행 장애의 수정 가능성과 과학적 식별·예측 실패를 구분하며, 후자는 자동 재실측 없이 최종 결과로 남긴다.
- 개발6만 적합/LOSO/선택에 사용하고 확인6은 생성된 모형 freeze를 바인딩한 후에만 진입한다. 기존 계수/사후 후보/두 독립 확인/모든 종료 계획은 보존한다. 기본·strict 지원 확대/experiment_ready 변경 없음. 기존 미소비6세션 plan은 새 host 코드와 다르므로 실행하지 않는다.

## 2026-10-02 — 열 모형의 끝없는 진단 확대를 막는 종료형 설계 (권고, 실행 미승인)

- 사용자 요청에 따라 [개발6→동결→독립 확인6](AP_MODEL_COMPLETION_STUDY_20261002.md)의 입력·한 후보군·선별·중단·종료와 예산을 실행 전에 명세했다. 12세션은 성공 보장·검정력 계산 결과가 아니라 조건/순서 대비와 새로운 입력 확인을 포함한 상한이다. 모든 내부 열 기제나 임의 정책까지 이번 완료 조건으로 확대하지 않는다.
- 기존6 plan/동결원본을 변경하지 않고 별도 오프라인 개발 분석 역할을 선언한다. 확인 자료 재적합·새 수식 자동 추가·13번째 세션 금지. 한정 지원 또는 미식별도 최종 결과다. 한 후보군 추정/동결과 확인 실행 연결은 아직 PC 구현 대상이므로 기존6부터 먼저 실행하지 않는 것을 권고한다. 실행예산 승인·소비0, 기기0, default/strict/experiment_ready=false 불변.

## 2026-10-02 — AP 배경 대 부하 시점 통합 대조 채택 (PC 설계, 실행 미승인)

- [고정 계약](results/ap_background_contrast_01/analysis_contract.json): C/L35/L65/L65/L35/C로 세 조건 평균 순번을 맞춘다. 선형 순번항의 산술 균형과 실제 환경/잔열 통제는 구분한다. 한 묶음에서 부족하면 미식별 종료하며 같은 B2·추가 후보/세션을 자동 반복하지 않는다.
- 모든 조건은 baseline→common+35 전 AP만 E/H 초기화에 쓰고 후기값은 목표로만 사용한다. 무부하를 실제0요청으로 취급하며 가짜 작업/센서값을 넣지 않는다. 기존 τ30/γ0 후보·원래 계수는 고정, 새 β/k 미채택 보존. 이번 자료를 나중에 모형 개발에 쓰면 그 모형의 독립 확인이 아니다.
- 기존 APK/자율 실행/소유권/회수 경로 재사용, 설치 불일치 fallback 금지. PC13검사/Check/원문 판독 완료, 새 계획144추론/5,250초/19,400ADB를 미승인·미소비로 준비했다. 기기·설치·실측·claim0. 정확도/정책 PASS·strict/default 승격 없음. 실행 승인과 환경 적격성은 아직 충족한 것으로 기록하지 않는다.

## 2026-10-02 — β/k 사후 후보 미채택, 배경과 부하 반응의 식별 한계 보존 (채택)

- 사용자 ‘어떻게 알아내는가/진행’에 따라 [단일 구조 PC 판독](results/ap_rate_identification_01/README.md)을 수행했다. 분석 계약을 적합 전에 기록하되 자료 결과는 모두 이미 본 사후 분석으로 명시했다. 기존 개발1만 적합해 β=기존값/k0.720002를 얻었으나 부하7세션 모두 최고 절대오차가 증가하므로 후보를 기본/strict로 채택하지 않는다.
- 무부하의 일부 +0.1°C 상승과 초기 기준 오차를 부하 잔열의 증명으로 해석하지 않는다. 수치 rank와 물리적 식별은 다르며 두 자유 감쇠율의 무부하 항 교환도 구분한다. 주변온도/센서지연/내부열 원인은 미확정이다. 기존 독립 확인·계수·원본·소비 계획은 보존한다.
- 현재 제한 시뮬레이터 사용과 결과 본문 완성에는 추가 실측을 강제하지 않는다. 열 정책 확장의 다음 권고는 동일 조건의 무부하 대 부하 시점 통합 대조이며 **아직 실행 설계 채택·승인·예산 확정이 아니다**. 이번 새 실측/계획/claim0, experiment_ready=false.

## 2026-10-02 — 준비 이력 후보의 독립 오차 확인과 채택 판정 분리 (채택)

- 사용자 명시적 실측 승인으로 기존 plan_v1을 한 번 실행해 두 조건 모두 정상 회수했다. [사전 고정 후보 결과](AP_MEMORY_CONFIRM_RUN01_20261002.md): τ30/γ0·계수 불변, 부하 전 AP 초기화/실제 일정 조건부 MAE0.178596/0.189876°C. 새 결과를 후보 개발에 사용하지 않는다.
- 기존 preload 대비 평균·최고오차 개선은 새 확인 근거로 보존한다. 후기 작은 상승의 크기와 순간 최대오차는 남으며 조건당1세션으로 보편 오차한도·물리 잔열·정책 판별을 승인하지 않는다. 원래 W식 오차+8.006/+10.568%도 별개로 남긴다.
- 소비 계획/원본/freeze/default/strict/experiment_ready=false를 유지한다. 완료 결과만 공유하고 추가 실측·후보 재보정·확인 추가는 자동 수행하지 않는다. 다음은 제한 시뮬레이터 본문 반영이다.

## 2026-10-02 — 준비 이력 후보의 확인 목적과 종료점 고정 (PC 설계 채택)

- [새 확인 계약](results/ap_memory_confirmation_01/analysis_contract.json): τ30/γ0 후보를 그대로 두고, 같은 runtime4/warmup8 후 등록 부하를+35/+65초에 허용하는 두 새 세션을 권고한다. 순서/시간은 결과 전에 고정하며 임의 가열·온도 맞춤·재적합은 하지 않는다. 부하 전 E/H 초기화는 관측 입력 처리이며 미래 AP를 사용하지 않는다.
- 후기 재상승 해결을 이 후보의 성공 조건처럼 전제하지 않는다. 자료 적격성/오차 산출/정확도/정책 판별을 분리하고 조건별1세션으로 반복 안정성을 주장하지 않는다. 74e APK는 후보 개발의747/3d8과 프로토콜 전이로 표시한다. 설치본이 다르면 자동 배포 없이 중단한다.
- PC 계획·동결·검증만 완료했다. 전체2,090초·64추론·6,600ADB, push/설치/재시도0. 실행 상태는 미승인·미소비이고 Run/claim0; 실행 준비와 실제 독립 확인 완료는 별개다. 기존 freeze/default/strict/experiment_ready=false 유지.

## 2026-10-02 — 준비 반응 후보는 사후 진단 전용, 스로틀 계수 미도입 (채택)

- [사전 구조·사후 평가](results/ap_preparation_memory_01/README.md): 기존 냉각률/상태 기울기를 고정한 추가 H상태1개를 구현했다. 부하 전 AP만으로 E/H를 추정하고 개발1세션만으로 τ30초/γ0을 얻었다. 네 적합 제외 세션의 평균·최고오차 개선은 보존하지만 새 독립 확인으로 부르지 않는다.
- 후기 개선은 주로 E 변경이며 후기 재상승을 재현하지 못했다. 개발 최대오차 악화·γ0경계·초기값 민감도를 숨기지 않는다. 기본/strict/정책 비용으로 승격하지 않고 별도 후보만 보존한다. 기존 기각 지연 후보도 변경하지 않는다.
- COLLECT05 완료4세션의 AP/시간 연관은 조건층에 따라 부호가 달라 인과 스로틀 곡선을 추가하지 않는다. 온도 무관 가정으로 승격하지도 않는다. 준비 이력에 대한 새 확인 필요 여부는 다음 결정이며 이번 새계획/실측0. 기존 freeze/FAIL/원본/experiment_ready=false 불변.

## 2026-10-02 — 실행 도구 완성과 물리 예측 검증 분리 (채택)

- `tools.d1_simulator`는 기존 엔진·동결 B2 선택·서비스 비교 규칙·모형 지원 검사를 호출한다. 새 전력/열 가정이나 계수는 추가하지 않는다. 지원되지 않는 도착 비용은 null로 차단하고 고정870건 모형과 분리한다.
- 실측 참조는 queue/explore/201 및 저장 일정의 backend·도착·dispatch·실행·응답·저장·worker/lane 전체 경계 일치를 요구한다. 정확한 기록 일정과의 대응이지 현재 PC 예측의 독립 실기기 검증이 아니다. 관측 전류·AP·실현 미래 시간을 예측 입력으로 전달하지 않는다.
- 사용자 추가 실측 허용은 존중하되, 제한 도구 완료에 동일 ABBA/열 진단 반복은 필요하지 않다. 기존 관측의 기술적 상충을 결과로 사용하며 미식별 후기/최고·열 피드백을 ‘완성’으로 승격하지 않는다. 기기0·새계획0·claim0, 원래 freeze/default/strict/experiment_ready=false 유지. 근거: [사용법·판정·검증](results/simulator_workbench_01/README.md).

## 2026-10-02 — 두 기록 일정 직접 비교와 모형 예측을 분리 (채택)

사용자의 실측·시뮬레이션 마무리 요청에 따라 서비스 적격 후보 CPU_URGENT/B2만 ABBA4세션으로 직접 관측한다. 저장 일정·입력·동결 계수 불변, 새 opt-in CPU replay로 동일 APK의 두 배정을 지원한다. 각2세션은 순서 역전 기술 비교이며 정밀도/정책 우월성/동적 에너지·AP 지원 확대의 증거가 아니다. 기존 AP 지연 후보 미채택 유지, 추가 후보 탐색·기존 종료 계획 재개 없음. 실행4세션을 완료했고 두 비교쌍 B2−CPU J−9.198/−1.611·마감+2/24를 제한된 관측 결과로 채택한다. 효과 크기·초기조건 변동 때문에 일반 우월성/엄격 모형 지원은 확대하지 않는다. 근거: [사전 예산·판독](RECORDED_POLICY_COMPARE_20261002.md).


## 2026-10-02 — 사후 지연 후보 미채택·PC 시뮬레이션 본문 완료

- **승인/수행:** 사용자 최신 요청에 따라 기존 실측만으로 가능한 후보 보완·민감도·본문을 완료했다. 이전 확인02의 무적합 판독은 그대로 보존하고 새 사후 후보를 분리했다. [적합 전 계약](results/ap_model_completion_pc_01/contract.json)의 구조1개/τ만 추정, 기존 개발1세션 τ4초·다른4세션 적합 제외. 모든 자료를 이미 봤으므로 새 독립 확인으로 부르지 않는다.
- **판정:** 평균 MAE 감소만으로 채택하지 않는다. 최고온도 차이5개 모두 악화·CG_DC 최대오차 악화·후기 재상승 미재현이다. 미채택 candidate JSON/API는 진단 전용, 원래 계수/절차/default/strict 불변이다. 엔진 비용 사용은 unsupported/null로 명시한다. τ3.5–4.5초의 전체세션 제외 안정성을 물리 지연 식별이나 신뢰구간으로 쓰지 않는다.
- **에너지:** 기존 상태W·저장 일정3개·protocol별 관측 잔차만 사용하는 민감도다. CPU_URGENT/B2의0.884J 진단 차이를 구분하려면 유휴 잔차에 매우 민감함을 확인했으나 보편 오차범위/새 W 보정/정책 우열을 만들지 않았다. 공통 배경의 산술 상쇄와 실제 배경 동일성 증거를 구분한다.
- **완료/권고 구분:** [결과·논의 본문](ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md)은 현재 증거 범위에서 완성했다. 서비스 적격 정책쌍의 실제 비용/변동성과 AP 이력 반응은 주장 확장에 필요한 미확인이다. 미채택 후보를 같은 B2 실측으로 확인하는 반복은 권고하지 않는다. 새 기기 계획·claim·기기 명령0, experiment_ready=false 유지.

## 2026-10-02 — 두 이력 확인 결과와 후보 적용 경계

- **실행 사실:** 사용자 실측/문제 해결 승인으로 별도 edition2를 준비·PC10검사·Check·동결 후 Run1회 실행했다. [두 세션/원본/종료](AP_BUNDLE_CONFIRM_RUN02_20261002.md) 모두 완료·회수,64추론·616.410초·ADB1,343·push/설치/재시도0. 새 edition은 ID·경로를 명시적으로 분리한 것이며 자동 재시도 선택기는 아니다. 과거01의 소비/중단 기록은 불변이다.
- **판독 사실:** 사전 동결한 후보·고정 방향창을 변경 없이 적용했다. 부하 후 AP 재적합0, 각 이력1개의 새로운3d8 전이 확인. 후보 평균 오차는 감소했지만 후기+0.2/+0.1°C 상승을 냉각으로 예측했다. 작은 양자화/시간 불확실성·독립 변동성 미확인과 함께 기록하고 물리 원인을 확정하지 않는다.
- **현재 적용 결정:** 후보는 실현 일정·부하 전 AP 조건부 진단으로 유지한다. 평균 개선만으로 최고/한도·온도 피드백 처리시간·동적 정책 J/AP 순위를 지원하지 않는다. 원래 W식의 새+7.01/+9.47% 차이를 보편 오차 한도로 채택하지 않는다. 기본/strict/계수·기존 FAIL·experiment_ready=false 불변이며, 확인 결과에 맞춘 후보/실측 추가는 하지 않는다.

## 2026-10-01 — 판독 완료와 실측 완료·그림 실패를 분리

- **구현 결정:** 정상 JSONL prefix만 소비 하한으로 사용하고 미회수는 null로 남긴다. 실제 반환 event는 host_inference_return이며 부재한 request_return 종류를 추론 반환0으로 해석하지 않는다. 최초 session attempt receipt가 미시도를 입증할 때만0을 표시한다. 그림 실패는 수치/자료 적격성과 별도 상태이고 원래 receipt·stack을 보존한다.
- **PC 사실:** 원래625e5a8 코드에서 부분 JSONL은 summary를 막고 렌더링 실패는 analysis_ineligible+깨진 링크를 만든 결함을 재현했다. 수정 경계10검사·기존 원문 두 세션의 실제CLI4경우를 통과했다. [검증/수치/자료 역할](results/ap_bundle_confirmation_01/readout_pc/verification.json). 기존 개발/확인 자료의 사후 PC 재생이며 새 독립 확인이 아니다.
- **보존 결정:** 기존 consumed plan_v1·원자료·당시 소스/결과는 불변이다. 새 분석 코드 해시를 옛 계획에 대입하거나 동일성 검사를 우회하지 않는다. 후보 재적합/strict/default 승격/새 계획·실측0, experiment_ready=false 유지. 다음 실측 목적은 이미 정한 두 이력의 고정 후보 확인이며 추가 포괄적 감사가 아니다.

## 2026-10-01 — AP 확인을 한 실행 묶음으로 통합, 최초 gate 실패면 종료

**구현/실행 결정:** 사용자 “묶어서 실측하는 쪽으로 가자”, 중단 뒤 “재개해”를 반영해 기존 AP 후보를 재적합하지 않는 확인2(한 pulse/두 half-pulse) 묶음을 채택했다. 총64추론/2,090초/ADB6,600·push/설치0·재시도0, 동일 설치본 실패 시 중단. 진단/개발/승인을 반복해 세션마다 끊는 방식으로 이어가지 않는다. **실행 사실:** 첫 devices -l에0대여서 plan claim 후 중단·두 세션 미시도. [receipt·소비·원래 오류·host 종료](AP_BUNDLE_CONFIRM_RUN01_20261001.md). 이번 결과는 AP/W 검증이나 과거 원인 해결이 아니다. 새 실측/계수/strict/default/experiment_ready 승격 없음; 기존 후보와 미확인 범위 유지.

## 2026-10-01 — 기존 가산 후보 미채택 유지·유휴 법칙 미식별

- **사후 사실:** 완료 C/L＋기존4세션의 [고정창/10초 bin 판독](RESIDENT_IDLE_HISTORY_PC_20261001.md)으로 무부하 시간 변화·loaded 전후 변화의 방향 불일치를 기록했다. APK/초기조건·이력이 다르며 bin을 독립 세션이나 보편 예측오차 한도로 쓰지 않는다.
- **판정 채택:** 기존 후보 식/창을 새 L에 그대로 적용한 첫 dispatch→120초 차이는+18.139→+27.929J. 이전4점수 불변·총2개선/3악화, 가산 후보 미채택 유지. 새 time/thermal/hidden-history 법칙을 추가 적합하지 않는다. 원래 W/AP·AP후보·strict/default/experiment_ready=false 보존.
- **출력 경계:** 적격 고정창 관측 재생과 동결식 외삽은 제공하되 미래 유휴 비용의 전용 법칙/동적 정책 J/AP 순위는 미판정이다. 후속 독립 예측 질문을 특정했으나 새 기기 계획/예산/승인을 만들지 않았다. PC6검사·출처/동결 해시 재검증, 기기 명령0.

## 2026-10-01 — resident 대조03 완료 자료의 판독 경계

- **확인 사실:** [실행03](RESIDENT_CONTROL_RUN03_20261001.md) C/L 두 세션 정상 완료·회수,40추론/1543명령/679.531초. 동일 설치본 push/설치0. 원본·두freeze·APK·실행95소스 불변.
- **판독 결정:** 공통120초 J와 pre/late 변화는 고정창으로 산출했다. L 냉각후기0.176161초 결측/AP 끝 bracket 부재는 null로 보존한다. 창 이동·0채움·부분창을 전체창으로 표현하지 않는다.
- **연구 경계:** 초기 AP/사전 전력·고정순서가 다른 조건당1세션의 구조 판별용 개발 쌍이다. −0.202361W를 부하 인과효과/전역 보정계수로 쓰지 않는다. 동결식은 외삽 진단, 새 후보 적합/독립 정확도 PASS/default 변경 없음. experiment_ready=false 유지. 다음 유휴 이력 PC 분석은 계획이며 아직 보완 모형을 채택하지 않았다.

## 2026-10-01 — 공간 검사 수정본의 새 계획03 동결

- **계획 채택:** 사용자 “계획 ㄱㄱ”에 따라 동일 C0/L24·같은APK·입력·센서·판독 기준을 새 ID03에 고정했다. 2세션/40추론/2,090초/6,600명령/재시도0, [해시·실행 경계](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#새-실행-계획03-준비-완료--2026-10-01). 기존 consumed v1/v2를 재개하지 않는다.
- **PC 사실:** claim 전 최소 공간 검사와 새 edition 경계7테스트·실제PS Check 완료,95소스/두manifest/기존APK·서명·입력·freeze 동일성 확인. 사용자 정리 영수증은 보존해시 확인 완료다. 설치본·현재 환경·연결 안정성은 기기 미검증.
- **권한·연구 경계:** 이번 요청은 준비이며 새 계획은 미승인·미소비, Run/기기/claim0. 구조 판별용 개발 쌍이고 독립 확인/인과/정확도 PASS/자동 후보적합 아님. 원래 모형/AP후보/strict/default/experiment_ready=false 유지.

## 2026-10-01 — 로컬 저장 공간 실패와 실행 전 최소 admission

- **확인 사실:** [대조02](RESIDENT_CONTROL_RUN02_20261001.md)는 설치본 pull에서 exit1/로컬 쓰기 I/O 오류, 직후 C: free0으로 종료됐다. 기존 화면 timeout 내부 원인과 별개다. 5명령/8.360초·앱 launch0·추론0, plan_v2 소비·stopped_no_resume. 부분 APK/원본·소비 registry를 보존한다.
- **구현 채택:** resident-control Run에서 후보 APK 바이트 수의 최소 여유 공간을 claim/기기 명령 전에 확인한다. 전체 저장량/장시간 안정성 보장은 아니며 소비 후 추가된 PC 수정이다. 초기 실패 판독의 미시도·cleanup 해당 없음·관측 null을 보존한다. 14개 관련 PC검증 통과, 실기기 재실행 없음.
- **범위:** 사용자 공간 확보 후 재개는 PC 검증·문서·Git만 수행한다. 기존 두freeze/APK/strict/default/experiment_ready=false 불변. 종료 계획 재개/새 계획 자동 생성/새 정확도 PASS 없음. 향후 실측은 별도 새 ID와 승인이 필요하다.

## 2026-10-01 — resident 대조 부분 종료와 판독 범위 확정

- **실행 사실:** 사용자 “실측 ㄱㄱ” 승인으로 plan_v1만1회 실행, C완료/L부분, stopped_no_resume. [원본·소비·정리](RESIDENT_CONTROL_RUN01_20261001.md). 종료 계획을 재개하거나 자료를 대체하지 않는다.
- **판독 채택:** C무부하 W1.295715→1.114261은 부하 이외 시간 변화의 관측이며 원인·새 계수·인과 비교는 미확정. L전체창/C–L 차이 null, C냉각 끝 결측도 고정창 유지/null. 화면 timeout은 확정, 내부/무선 원인은 미확정. 앱 cleanup과 host force-stop/프로세스 부재를 분리한다.
- **보존:** 두 freeze/strict/default/experiment_ready=false 불변. 후보 채택/독립 정확도 PASS/정책 우월성/추가 실측 승인 없음. 다음 PC 작업은 화면 조회 실패 경계 진단 하나다. 아래 준비 결정은 당시 이력이다.

## 2026-10-01 — resident 대조 opt-in 구현 채택, 실측은 미승인

- **구현 채택:** 기존 Activity/worker/sampler/cleanup을 사용하며 `resident-control-pair-v1`의 C만0요청을 허용한다. L 및 기존 실행은24요청이다. host가 각 분모/합계를 검증하고 실패 후 다음 세션/중복 정리를 차단한다. 기기 선택은 실행기의 최초 조회로 한 transport에 고정한다.
- **PC 사실:** Python18/Android9·서명 패키징·실제PS Check 완료, [계획/해시](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#실행-준비-완료-2026-10-01) 미소비. 원래 설계 JSON은 당시 blocked 증거로 보존했다. 현 예산은2세션·40추론·2,090초·6,600명령·재시도0.
- **범위:** 동일 새 APK끼리의 시간 변화 기술용 자료다. 조건당1세션/고정순서의 원인 귀속·독립 확인 한계 유지, 계수/strict/기본 경로/experiment_ready=false 불변. 이번 작업은 실행 승인이나 실기기 검증이 아니다.

## 2026-10-01 — 무부하 대조 목적과 실행 차단 구분

- **설계 권고:** [C무부하1＋L등록부하1](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md)로 같은 준비 이후의 시간 변화와 부하 후 변화를 기술한다. 조건당1세션·고정순서이므로 인과 귀속/변동성/독립 모형 확인은 하지 않는다. 고정 일정 설명은 추가 실측 없이 가능하고, 동적 에너지 보완에는 누락 대조가 필요하다.
- **구현 판정:** 현 APK와 host는24건 전제다. 요청0 JSON/강제 종료/setup-only로 대체하지 않는다. 설계 산술·입력 해시 Check를 실행준비 PASS로 표현하지 않는다. 수집기/Android 수정·새 APK는 이번 설계에서 수행하지 않았고 Run/후보APK hash=null이다.
- **보존:** 두 세션/40추론/2,090초/6,600명령은 미승인 제안 예산. 기존 모형/미채택 후보/원자료/소비 기록/strict/experiment_ready=false 유지. 후속 구현 후 실행 동일성/예산 검증이 필요하며 자동 측정 승인을 만들지 않는다.

## 2026-10-01 — 부하 전 유휴 가산 전력 후보 미채택

- **판정 채택:** [RESIDENT-PRELOAD-OFFSET-01](RESIDENT_POWER_CANDIDATE_PC_20261001.md)은 네 세션을 이미 본 뒤 정한 후보1개다. 부하 전20초 평균＋원래 상태 차이의 고정식은2개선/2악화로 미채택; 창/배율 추가 탐색·AP 변경·기본/strict 승격 없음. prefix만 입력하는 정보 경계를 PC에서 구현했고 이후 전류 변경이 예측을 바꾸지 않음을 확인했다.
- **다음 권고, 실행 승인 아님:** 같은 준비·resident의 무부하 대조로 시간 변화와 부하 후 효과를 구분할 최소 설계를 확정한다. 반복 수/정확도 허용폭/실행 예산은 현재 미확정이며 기기 계획·claim을 만들지 않는다. 후보 확인을 위한 즉시 재측정은 권고하지 않는다.

## 2026-10-01 — CG_DC 전이 확인 종료, 후보의 진단 범위 유지

- **실행 사실:** 사용자 “실측 진행하자” 승인으로 기존 ENERGY-AP-CGDC-TRANSFER-02를1회 완료. [소비/자료/오차](AP_CGDC_TRANSFER_RUN01_20261001.md). plan_v2는 소비·완료이며 기존 미소비/종료 계획과 구분한다.
- **판정:** 고정 preload 후보가 다른 기록 일정에서 AP MAE0.463463°C를 보였으나 후반 재상승을 표현하지 못한다. 원래 W는120초 +20.583851J이며 이번 세 구간의 잔차는 모두 양수. 4세션 원문 유휴 대조도 완료했고 경계 혼합 제외 후 W1.046593–1.227498의 조건 차이가 남았다. 부하 후 재적합·기본 모형 채택·strict/최고/한도/정책 순위/experiment_ready 승격은 하지 않는다. 수집 조건/열 이력/주변 원인과 정책 판별력을 이 사후 분석으로 확정하지 않는다. 다음 PC 작업은 결과·논의 본문 반영이며 새 실측 승인이 아니다.

## 2026-09-30 — 최신 팀 안내와 과거 실행 이력의 읽기 순서 고정

- **공유 안내 채택:** 루트 README→[팀 안내](team/README.md)→결과/현재 STATUS/현재 준비 계약 순으로 읽는다. 기존 팀 안내는 당시 이력으로 접어 보존하고 현재 “최신”으로 읽지 않는다. GitHub 계약/코드와 외부 실행 묶음·APK·모형/원자료의 확보 경계를 명시한다.
- **연구/실행 결정 불변:** 팀원 전달용 갱신이며 새 측정 승인·새 예산·모형 채택이 아니다. S26/NPU는 보유 근거를 먼저 제출하고 기기별로 판단한다. 미승인/미소비plan_v2·strict·FAIL·`experiment_ready=false` 유지.

## 2026-09-30 — 기존 제한 결과를 연구 본문으로 정리

- **본문에 채택한 표현:** [결과·논의 초안](ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md)의 고정 CC_DG 상충, 저장 PC 서비스 선별, 조건부 에너지 잔차와 AP 후보의 제한적 확인. 기존 판정의 통합 서술이며 새로운 정책 채택/계수/지원 범위 결정이 아니다.
- **미완료 유지:** 온라인 정책의 에너지·열 우월성, AP 최고/한도 보장, 새 일정 전이 및 정책 차이 판별력. 실측 가능 전에는 준비된 계획을 미승인·미소비로 보존하고 이번 글을 실행 승인으로 해석하지 않는다. 새 기기 명령0, `experiment_ready=false`.

## 2026-09-30 — 동결 실행 경로와 분리한 PC 판독 어댑터 채택

- **구현 채택:** [고정 transfer readout→CSV 검사→그림·HTML](AP_CGDC_TRANSFER_PREP_20260930.md#실측-후-pc-판독과-그림-자동화-2026-09-30). 실제 일정 조건부 진단만 출력하며 post-load AP는 점수 대상이다. 원래 120초 예측 요약값은 이미 정확한 끝까지 적분한다. 센서 타임스탬프만 있는 누적 경로에는 유효한 창 끝 적분과 요약·상태 적분이 일치할 때120초 점을 추가하고 원래 CSV를 보존한다. 계수/창/요약 오차 변경은 없다.
- **승격하지 않는 것:** fixture PASS는 실기기/새 예측 확인이 아니다. 미실행 계획의 not_evaluable은 실행 실패/소비가 아니다. 새 승인/Run/claim0, 기존 미승인plan_v2·동결본·strict·FAIL·`experiment_ready=false` 유지.

## 2026-09-30 — APK를 유지한 다른 CG_DC 일정의 전이 확인만 준비

- **채택한 PC 준비 범위:** [고정 절차 확인1의 목적과 종료 기준](AP_CGDC_TRANSFER_PREP_20260930.md). 원래 개발3 freeze와 이미 고정한 preload 후보를 변경하지 않고, 저장 burst/201/B2의 release만35초 이동해 전이 오차를 확인할 실행 전 자료·plan_v2·Check·readout을 구현했다. Android의 도착 격자 검사를 실제 JVM 경계에서 확인해 원래 도착을 유지하며, 서비스 guard 적격 원본이라는 이유로 새35초 대기 입력의 서비스 적격성을 주장하지 않는다. APK/관측 주기 변경은 없다.
- **권고이지 기기 승인/검증이 아닌 것:** 확인1·명시적추론≤32·전체≤1300초/ADB≤3200 계획. 현재 미승인·미소비, Run/claim0. 원본/후보·strict/기본 simulator·`experiment_ready=false` 유지. AP/전력식 수치 산출을 정책 순위나 최고온도 제약 검증으로 승격하지 않는다. DC_DG까지 넣기 위한 새 APK/다중 세션 개발은 이번 준비에 추가하지 않는다. v1 초안은 실제 contract 불일치를 발견해 실행불가 초안으로 보존했다.

## 2026-09-30 — 저온 AP 후보의 조건부 진단 인터페이스만 채택

- **PC 구현 채택:** [실현 lane 일정·부하 전 AP 조건부 경로](AP_SIMULATION_CLOSURE_PC_20260930.md#6-저온-ap-출력의-pc-연결-2026-09-30)만 opt-in 계산한다. 정보 cutoff 이전 구간 출력, 부족한 pre-load·다른 APK/구성·미지원 상태를 차단한다. 기존 두 세션의 수치 재현은 사후 scope readout이고 기존 확인 역할을 새 독립 검증으로 늘리지 않는다.
- **채택하지 않은 범위:** AP 최고/한도 초과/기기 J/정책 순위/미래 일정 비용의 후보 지원. 실제 arrival 집계는 후보 profile을 명시적 unsupported/null로 반환한다. 작은 MAE를 정책 판별력으로 승격하지 않고 기존 β/기울기/동결/후보절차/strict·`experiment_ready=false`를 유지한다. 이번 PC 작업은 완료; ADB·새 실측·APK·실행계획/claim0.

## 2026-09-30 — 승인 B2 범위 내 확인 중단 보존, 온도 gate 반복 금지

- 사용자의 계획준비·실측·기술오류 수리 후 진행 승인으로 [새 계획1회](ARRIVAL_B2_INRANGE_RUN01_20260930.md)를 실행했다. 기존 APK의 v1 gate를 선택한 별도 ID이며 과거 v2 진단을 수정하지 않는다. 동일 설치본/환경이 확인되고 warmup8 반환 뒤 AP30.0°C로 arm을 거절했다. 공통창·본 요청0, host 종료/프로세스 부재 확인, `stopped_no_resume`다.
- 초기조건 부적합은 기술 오류나 모형 예측 실패가 아니다. 수정할 코드 결함이 확인되지 않아 같은 계획/동일 gate를 성공할 때까지 반복하지 않고 개발 하한 삭제·가열·계수 변경도 하지 않는다. 정상 저온에 대한 별도 모형 질문은 기존 저온 자료를 먼저 사용해야 하며, 이번 중단을 독립 확인 성공으로 승격하지 않는다. 동결/FAIL/원자료/`experiment_ready=false` 유지.
## 2026-09-30 — 동적 정책 비용 비교 전 연구용 서비스 선별 규칙

- **채택한 PC 비교 규칙:** [계약과 사후 판독](results/arrival_service_guard_01/README.md)에 따라 동일 trace·seed·실현 간섭의 `CPU_URGENT` 대비 24예정 요청 전부 완료, 긴급·일반 기한 미준수 건수 비증가, 긴급 완료 응답 P95 비증가를 요구한다. 일반 평균은 보고값이다. 기존 δ=0 허용폭 탐색 결과를 소급 변경하지 않는다. 이 규칙은 보수적 연구용 선별이며 실제 UX SLA·에너지/AP 허용오차가 아니다.
- **증거 경계:** 이미 본 저장135사례에 적용한 B2 적격21/45·B3 적격22/45·동시 적격7/45는 사후 PC 판독이다. 대표 queue/201/1.5의 B2는 남고 B3는 긴급 P95 +373.652ms로 제외된다. 동시 적격 사례도 J/AP 전체창 지원·독립 예측 검증이 없어 비용 순위는 null이다. 향후 다른 허용폭은 독립 자료를 보기 전에 별도 결정해야 한다. 새 정책·계수·실측·SLA PASS는 채택하지 않고 동결 모형·FAIL·원자료·`experiment_ready=false`를 유지한다.

## 2026-09-30 — AP 후보와 에너지 전이 판정, 제한 계산과 동적 완성 분리

- **확정한 PC 판정:** [기존8세션 판독](AP_SIMULATION_CLOSURE_PC_20260930.md)에서 single-state idle 식은 관측 상승→하강을 재현할 수 없지만 HAL 내부 timestamp 부재로 센서 지연/열 이력을 따로 식별하지 못한다. 새 계수를 임의 생성하지 않고 부하 전 유효 기준 후보를 조건부 진단에만 남긴다. 새 유휴2세션의120초 W 외삽 오차 +20.090/+11.305J를 보존하며 B2의 작은 전체오차를 보편 정확도로 전용하지 않는다.
- **재사용 범위 확정:** 기존 고정CC_DG870건/480초 회고 선택 인터페이스의 `TRADEOFF`는 지금 재현할 수 있는 제한 계산이다. 이것으로 원래 동적 목표를 완료 처리하지 않는다. 저장135개 일정의 완전한 J/AP 지원0과 대표3개의 null을 유지한다. 후보/지원 마스크/동결계수/원자료/FAIL/`experiment_ready=false`는 변경하지 않는다.
- **후속 권고, 기기 계획·승인 아님:** 동적 정책 비교의 남은 질문은 같은 프로토콜에서 B2/B3 짧은 상태 전환의 전체창 비용과 AP 관측 반응·일정 전이 오차다. 같은 B2 반복이나 모든 조합 추가 계측을 자동 권고하지 않는다. 당장 다음은 완료된 고정 비교의 상충과 순위 실패를 연구 결과로 반영하는 PC 작업이다.

## 2026-09-30 — 저온 AP 후보는 확인 오차 개선에도 기본 채택 보류

- [승인 계획 실행과 별도 확인](ENERGY_AP_IDLE_RESPONSE_RUN01_20260929.md): 부하 전 AP로만 세션별 유효 기준을 넣는 고정 절차는 개발 후 동결했고, 다른 두 묶음의 확인 세션에서 후보 AP MAE0.418°C 대 원래 동결식의 저온 외삽5.461°C를 관측했다. 그러나 확인의 마지막 부하 후 AP는 관측 시작→끝 0.000°C이며 중간 상승 표본이 있고 후보는 −0.719°C 냉각을 예측했다. 후보의 이력·지연 한계가 남으므로 기본 시뮬레이터/strict 지원/정확도 PASS로 **채택하지 않는다**. 이미 본 확인을 재보정에 사용하지 않는다.
- 원래 동결본·기존 사후 후보·원자료·실패·종료 계획은 보존하고 `experiment_ready=false` 유지. 같은 승인 실행은 소비·종료했으며 새 기기 계획/추가 실측을 자동 시작하지 않는다. 기존 기록에서 AP 최고 표본 지연과 실제 lane 경계를 분리 판독하는 PC 작업만 다음 행동으로 둔다. 아래 2026-09-29 권고는 **당시 실행 전 결정**이다.

## 2026-09-29 — AP 유휴 방향 오류의 후속 수집 권고(실측 채택/승인 아님)

- [근거·계획](ENERGY_AP_IDLE_RESPONSE_PLAN_PC_20260929.md): 동결식의 공통 idle 평형34.380°C가 저온 B2 관측의 냉각과 반대로 가열 방향을 만든다. 같은 B2 한 세션 반복 또는 그 세션만 맞는 시작값 평행 이동 후보의 기본 채택은 하지 않는다. 기존 개발 β·상태별 차이를 고정하고 **부하 전** resident AP로 세션별 *유효* 유휴 기준을 구하는 별도 진단 후보를 채택해 PC 준비한다. 이는 주변온도·숨은 잔열을 식별하는 물리 모형이 아니다.
- 개발1(한 묶음)→구조/코드 동결→확인1(두 묶음)의 미승인 `ENERGY-AP-IDLE-RESPONSE-01`을 권고한다. AP<32.5°C는 이 저온 층의 일회성 자료 적격성이지 안전 하한 변경이 아니다. 기존 BAT/비충전/thermal/화면/메모리/품질 gate·동결/strict/기본 profile·원본/FAIL/`experiment_ready=false`를 보존한다. PC Check·실행 준비는 실기기 완주, 독립 정확도 PASS, 정책 우월성을 뜻하지 않는다. 새 plan 실행 승인·claim 없음.

## 2026-09-29 — 저온 AP 후보 기본 채택 보류, 상쇄 구간 명시

- **PC 결과·채택하지 않은 변경:** [잔차·후보 판독](ARRIVAL_RECORDED_B2_RESIDUAL_MODEL_PC_20260929.md)에서 원래 +1.062J는 부하+1.687J와 긴 유휴−0.625J의 상쇄로 분해됐다. 시계/적분/상태 매핑 결함은 발견하지 못했다. 동결 초기 AP는 29.9°C로 정확히 초기화됐으나 idle 평형34.380°C 예측과 실제 냉각이 반대였다.
- 별도 AP 후보 `energy-ap-start-referenced-idle-diagnostic-v1`은 **사후 감도 구현**으로만 보존한다. B2에서 MAE가 감소해도 기존 개발3·확인 DC_DG·DIAG-04에서 모두 악화하고 시작 AP를 주변온도로 동일시할 수 없으므로 simulator 기본 profile·strict 범위로 **채택하지 않는다**. 기존 동결 계수·원본·FAIL·`experiment_ready=false` 불변. 새 실측 계획/승인은 만들지 않았으며, 저온 독립 확인의 필요성은 후속 결정으로 남긴다.

## 2026-09-29 — B2 관측 1회 완료의 해석 경계

- **실행 사실과 채택하지 않은 주장:** [plan_v6 결과](ARRIVAL_RECORDED_B2_AP_OBSERVE_RUN01_20260929.md)는 24요청·공통120초·실제 CG_DC 병행을 회수했다. 개발 범위 밖 시작 AP29.9°C에서 동결식의 J 오차+1.062J, AP MAE3.555°C는 외삽 진단이다. strict 지원 확대, 정확도 PASS, 온라인 B2 우월성, 동결 계수 재보정은 채택하지 않는다.
- plan_v6는 소비·완료됐으며 재실행하지 않는다. 기존 미소비 plan_v5 초안·queue24, 종료된 plan_v3/v4, 원본·FAIL과 `experiment_ready=false`를 보존한다. 다음 PC 판독은 상태구간의 에너지 오차 상쇄와 AP 초기조건 차이 분석 하나로 제한한다. 새 실측은 승인하거나 자동 시작하지 않는다.

## 2026-09-29 — 개발 시작 AP 범위와 실행 적격성 분리

- **채택한 PC 프로토콜 변경, 실측 승인 아님:** [근거·계약](ARRIVAL_RECORDED_B2_AP_OBSERVE_PC_20260929.md)에 따라 32.5–34.0°C는 개발 세션에서 본 시작 AP 범위로 취급한다. 독립적인 실행 안전 하한은 확인되지 않았다. 새 `numeric-ap-observe-v2`는 기존 안전·환경·품질 gate와 numeric AP 유효성·신선도는 유지하면서 이 범위 밖의 관측을 허용한다. 과거 v1 gate 중단은 소급 변경하지 않는다.
- 범위 밖 동결식 계산은 별도 외삽 진단이며 에너지/AP 경험적 지원·short-transition strict·정책 우월성을 확장하지 않는다. 새 plan_v6는 미승인·미소비, 실행 출력/claim 없음. v5 PC 초안은 현재 코드 Check 불일치로 실행 대상이 아니다. 기존 동결 계수·FAIL·원본·queue24 미소비 계획과 `experiment_ready=false` 유지.

## 2026-09-29 — 새 B2 재생의 AP gate 중단 판정

- [승인된 plan_v4 1회](ARRIVAL_RECORDED_B2_REPLAY_RUN02_20260929.md)에서 시작 직전 HAL AP 28.8°C가 사전 범위 32.5–34.0°C 미달이므로 host가 arm을 보내지 않았다. 이는 자료 적격성 중단이지 동결 J/AP 예측 실패나 lifecycle 수정의 성공/실패 판정이 아니다. 공식창·실제 병행이 없어 정확도·정책 우월성은 계속 미판정이다.
- 소비 계획 재실행, 즉석 가열·시작 범위 완화·동결 계수 변경·새 실측 자동 생성은 채택하지 않는다. 이전 plan_v3·원본/FAIL, 미소비 queue24 계획, strict 지원과 `experiment_ready=false`를 보존한다. 다음 PC 판독은 이미 있는 초기 AP 관측으로 gate의 적용 가능성을 판단하는 범위다.

## 2026-09-29 — B2 재생의 Activity 소유권은 유지, 종료 증거만 보강

- [PC 시간축·코드 판독](ARRIVAL_RECORDED_B2_LIFECYCLE_PC_20260929.md)에서 `onDestroy` 취소 뒤 앱 실패 기록, 이후 host force-stop을 확인했다. 최초 `onDestroy` trigger는 구 APK에 callback/instance 로그가 없어 미확정이다. Activity의 작업 소유권·미완료 취소를 삭제하거나 Service로 전환하지 않는다. 별도 journal 기록은 다음 사건의 구분을 위한 변경이며 원인 해결·기기 검증 결정이 아니다.
- 중단 plan_v3 재실행과 새 실측 자동 시작은 채택하지 않았다. 새 APK의 추가 계측 비용은 미확인이고 기존 동결 모델·FAIL·미소비 queue24·`experiment_ready=false`는 그대로 둔다. 다음 실행은 새 계획과 별도 승인/현재 gate를 필요로 한다.

## 2026-09-29 — 짧은 전환 확인용 기록 일정 선택과 1회 결과

- **PC 확인 범위 확정:** [B2 원본·49구간 교차검사](ARRIVAL_RECORDED_B2_REPLAY_PC_20260929.md)에 따라 queue/seed201/실현 간섭1.5의 B2_PC 24요청을 첫 조건부 모형 전이 질문으로 고정했다. 이는 유휴·탐지 CPU·분류 GPU·CG_DC를 포함하는 최소 상태 묶음이고 반대 병행 방향은 포함하지 않는다. 저장 dispatch는 실행 허용 *하한*일 뿐 기기 완료시간이나 실제 병행을 강제하지 않는다. 별도 기록 재생 모드와 기존 정책/strict 지원은 구분한다.
- **승인 실행의 한계:** 서명 APK와 plan_v3을 별도 승인으로 [한 번 실행](ARRIVAL_RECORDED_B2_REPLAY_RUN01_20260929.md)했으나 resident baseline에서 앱 lifecycle 취소로 `stopped_no_resume`가 됐다. 공식창이 없어 동결 모형 조건부 J/AP 오차는 산출할 수 없으며, 정확도·정책 우월성 PASS는 미정이다. 소비 계획 재실행·기존 queue24 계획 소비·동결 계수 보정·`experiment_ready=true`를 결정하지 않았다. 오류의 최초 기록을 다음 판독에서 먼저 보존하도록 host 검증 경로만 보완했다.

## 2026-09-29 — 실측 기반 정책 우열의 현 지원 판정

- **확정된 지원 판정:** [저장 일정 135개 지원 검사](ARRIVAL_MEASURED_SUPPORT_BOUNDARY_20260929.md)에서 동결 A24 모형으로 전체120초 J/AP를 계산할 정책·입력 사례가 없다. 지원 마스크가 0인 상태에서 가정 비용 순위를 실측 기반 우열로 승격하지 않는다. PC 일정·응답 비교는 유지한다. 온도→처리시간 식 부재는 고정 처리시간 *탐색*을 자동 차단하지 않지만 실제 고온 응답의 증거도 아니다.
- **후속 권고, 실측 승인 아님:** 상태 이름이 모두 있는 queue/seed201/실현1.5의 CPU/B2/B3를 최소 *PC* 비교 묶음으로 둔다. 기존 Android FIXED_SPLIT 도착 경로가 세 정책의 직접 실기기 재생을 지원한다고 가정하지 않는다. 먼저 유효한 관측 시작 AP와 유휴/단독/세 종류 병행의 짧은 실제 전환·전체 J/AP를 동결식과 조건부로 대조해야 상태 비용 지원을 재판정할 수 있다. 실제 정책 우열은 별도 정책 실행·종단간 확인이다. burst/B3의 미계측 분류 CPU＋분류 GPU는 현재 범위에서 제외한다. 기존 queue24/FIXED_SPLIT 미승인·미소비 계획, 동결 계수·FAIL·원본·`experiment_ready=false`를 유지한다.

## 2026-09-29 — 기존 근거로 시작할 정책 탐색과 측정 보류의 구분

- **이번 감사의 권고, 새 목표 채택/실측 승인 아님:** [근거표·종료 기준](ENERGY_AP_POLICY_MEASUREMENT_AUDIT_20260929.md)에 따라 기존 CPU_URGENT·B2·B3의 제한 PC 서비스/가정 비용 비교는 진행 가능하다. 실측 기반 정책 우열은 동결 모형의 임의 도착 전환 오차와 정책 차이를 구분하는 독립 근거가 필요하다. 온도→처리시간 계수는 미검증이므로 넣지 않고 OS 열 보호의 존재를 부정하지 않는다.
- 준비된 queue24/FIXED_SPLIT 계획은 A/B의 좁은 예측 진단에 유용하지만 병행 계수·정책 순위 확인의 필수조건으로 채택하지 않는다. 계획 SHA·미승인·미소비 상태를 유지하며 이번 보류를 실패·`stopped_no_resume`로 바꾸지 않는다. A24·S26 모형은 분리하고 기존 FAIL/원본/동결값/`experiment_ready=false`를 보존한다.

## 2026-09-29 — 짧은 전환 진단의 계측 적격성과 모형 지원을 분리

- [별도 DIAG-01 실행](ENERGY_AP_SHORT_TRANSITION_DIAG01_20260929.md)은 36개 블록과 공동 lane 점유·전류/AP coverage를 충족했다. 이것은 상태 전환의 관측 가능성이지 임의 도착 시뮬레이터의 예측 검증이 아니다. 기존 개발3 동결 파일의 byte·계수, 기존 정식 확인 분모, 실패/종료 계획을 보존한다.
- AP 시작32.3°C가 개발 관측 범위32.5~39.5°C 밖이므로 동결 모형 `evaluate`의 unsupported 판정을 유지한다. 동결식 대입값을 정확도 PASS나 지원 범위 확대에 사용하지 않는다. 새 APK/제어 프로토콜은 동일 조건 확인으로 합치지 않고, `energy_ap_state_regimen_fit_v1`의 임의 도착 strict 계산 불가와 `experiment_ready=false`를 유지한다.
- 다음 정책·모형 실측은 결과에 맞춰 냉각/재시도하지 않는다. 상태 시간 척도·센서 분해능·초기 AP gate를 PC에서 사전 고정한 최소 입력만 후속 후보로 다룬다. 현재 수집 설계를 반복하는 결정을 채택하지 않는다.

## 2026-09-29 — 기존 queue 단일 도착 경로를 상태별 계수 확인 계획으로 전용하지 않음

- [저장된 일정의 센서 해상도 감사](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md): queue/seed201/strict의 24요청에서 Android 지원 `FIXED_SPLIT`의 CC_DG 공동 lane 점유가 없고, 단독 연속 구간은 1초 전류·약2.65초 AP 표본보다 짧다. 이 **PC 일정의 실패**를 다른 seed·실기기에서도 병행이 없다는 결론으로 일반화하지 않는다.
- 실제 단독↔병행↔유휴 전환의 별도 opt-in 단일 세션 재생·적격성 경로를 PC에서 먼저 준비한다. 기존 12세션 계획의 값·APK·승인을 승계하지 않으며 정확한 예산/해시/Check 없이 수집하지 않는다. 동결 모형·도착 unsupported·`experiment_ready=false`는 유지한다.

## 2026-09-29 — 상태 동결 모형은 실제 블록 일정 전이 진단까지만 연결

- [전이 평가](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md)의 **확정 경계:** DIAG-04 CG_DC는 개발 시작 AP 범위·exact 모델/입력/runtime을 충족하지만 새 APK·host 계측 방식의 별도 프로토콜이다. 동결 파일은 유지하고 실제 상태 일정 조건부 오차만 표시한다. 전체창과 상태 매핑 구간의 0.008초 차이는 분리한다.
- [도착 엔진](../tools/d1_arrival_energy_research.py)에 이 동결 profile을 지정해도 임의 도착·짧은 전환은 unsupported/null이다. 한 프로토콜 전이 세션의 잔차로 새 계수를 적합하거나 정책 절감·AP 한도 준수를 인증하지 않는다. 독립 짧은 전환 확인 목적은 남아 있지만 현재 실행기·예산 근거가 없어 새 계획은 미승인·미소비다. `experiment_ready=false` 유지.

## 2026-09-29 — DIAG-04 완료의 주장 범위

- 사용자 “알아서 실측까지 계속 진행해” 승인으로 새 ID의 기존 CG_DC 단일 진단을 1회 수행했다. [정상 완료·소비](ENERGY_AP_DEVICE_SEGMENT_DIAG04_RESULTS_20260929.md). 앱 cleanup·finish 요청과 host 사후 cleanup1회가 확인됐지만, 연결 소실이 없었으므로 단절 내성이나 과거 onDestroy 원인 해결은 미입증이다.
- 새 APK/프로토콜 자료를 기존 동일 조건 확인에 합치지 않는다. lane 공동 점유120.037초와 host invocation 겹침9.062초를 구분하며 지속 병행 상태의 전력 계수로 자동 전용하지 않는다. 동결 모형·기존 FAIL·정식 미완료 상태·`experiment_ready=false`를 유지한다.

## 2026-09-29 — host cleanup은 같은 종료 처리에서 한 번만 시도

- **확정된 코드 경계:** [DIAG-03 PC 조사](ENERGY_AP_DEVICE_SEGMENT_LIFECYCLE_PC_20260929.md)에서 앱 실패·회수·첫 host cleanup 뒤 요약 거절로 예외 cleanup이 반복되는 결함을 확인했다. 향후 실행기는 첫 cleanup의 성공/부분 실패/미확인을 보존하고 동일 종료 처리에서 두 번째 force-stop을 자동 시도하지 않는다. 원래 앱 stack과 host 요약 오류는 별도로 보존한다.
- **미확정:** DIAG-03의 실제 `onDestroy` trigger와 사용자가 본 무선 디버깅 OFF→ON의 전환 시각·주체·인과 관계. 새 Android 기록은 종료 의미를 바꾸지 않는 관측 보완이며 기존 APK·동결 모형의 동일 조건 검증이 아니다. 기기 진단·설치·수집 승인 또는 새 실측 계획은 이번 결정에 포함하지 않는다. `experiment_ready=false` 유지.

## 2026-09-28 — host arm 제거 범위를 진단 세션 내부로 제한

- **결정:** [ADB 의존성·계측 비교](ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md)에 따라 `baseline.arm` 생략은 별도 opt-in 진단에서만 허용한다. host의 warmup/GPU·품질, probe/AP 준비 승인은 보존한다. 앱이 읽지 못하는 AP numeric 적격성은 새 모드의 결측으로 남긴다. 기존 정식 모드·개발 동결 모형과 CONFIRM-06 실패 결과는 변경하지 않는다.
- **회수/전이:** host가 관측을 잃으면 앱 실패와 분리해 미확인으로 기록하고, 원 host 종료·동일 session ID·앱 terminal 근거 뒤 읽기 전용 회수한다. 새 APK와 host 조회/앱 screen 관측 변경은 기존 계수의 **동일 조건 확인**이 아닌 전이 진단이다. `experiment_ready=false`, DIAG-03 미승인·미소비다.

## 2026-09-28 — CONFIRM-06 중단 자료의 모형 확인 판정

- **판정:** [별도 확인 실행 결과](ENERGY_AP_CONFIRM06_RESULTS_20260928.md)는 첫 `CG_DC`에서 host transport 소실과 후속 앱 `baseline_gate` 실패로 끝났다. 전체 앱 journal에서 본 작업 호출0·완료 세션0을 확인했으므로 CG_DC/CC_DG 예측 오차나 모형 지원 범위를 추가하지 않는다.
- **보존:** 개발3 동결 byte·기존 DC_DG 단일 확인 결과, 기존 COLLECT-05/CONFIRM-06 종료 상태와 원본을 유지한다. CONFIRM-06·소비된 단일 회수 claim을 재실행하지 않으며 `experiment_ready=false`다. 다음 PC 작업은 원본 ADB transport 소실 경계 진단이며 새 실측/정책 개발을 자동 채택하지 않는다.

## 2026-09-28 — 동결 계수 유지, 별도 2조건 확인 후보만 PC 준비

- **근거:** [COLLECT-05 PC 감사](ENERGY_AP_CONFIRM_FOLLOWUP_PC_20260928.md)의 단일 `run-as ls` timeout은 중단 원인이나 내부 지연 원인은 미확정이다. 조회 중복·동시 client 증거가 없어 계측 주기/timeout을 사후 변경하지 않는다.
- **범위:** 기존 개발3·완료 확인 DC_DG1·중단 prefix와 동결 계수를 보존하고 CG_DC/CC_DG만 별도 미승인 계획으로 준비했다. 기존 6세션 분모를 완료로 고치거나 확인 결과로 재보정하지 않는다. 다른 날짜/환경의 후속 확인은 별도 lineage로 판독한다.
- **상태:** PC Check/fixture 검증만 완료, 실기기 명령0·실행 claim0. 새 2세션 후보의 별도 실행 승인과 현재 A24 gate가 남으며 기존 FAIL·종료 계획·`experiment_ready=false`는 유지한다.

## 2026-09-28 — COLLECT-05 부분 동결 모형의 지원 범위 승격 보류

- **실행 상태:** 별도 승인된 새 정식 계획을 한 번 실행했으며 개발3→동결→확인1 뒤 다음 확인 준비의 ADB `run-as ls` timeout으로 `stopped_no_resume`다. [원본 경계·오차](ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md)를 따른다.
- **판정:** 동결 계수와 유일한 확인 오차는 보존하되, 누락된 CG_DC/CC_DG 확인과 조건 간 방향·짧은 임의 도착 예측을 완료한 검증으로 취급하지 않는다. 기존 동결값/FAIL·원자료를 변경하지 않고 `experiment_ready=false`를 유지한다. 재시도·동일 계획 재개·확인 자료 재보정은 채택하지 않았다.
- **다음 근거:** timeout 발생 client와 직전 정상 조회의 PC 기록 비교가 후속 실행 신뢰성 판단에 필요하다. 새 실측 예산이나 timeout 변경은 이번에 확정하지 않는다.

## 2026-09-28 — host 복구는 종료 확인 후 단일 owner, 기기 진단은 별도 승인

- **확정:** 사용자 승인 범위의 PC 설계로 향후 수집의 `host_run_id`·parent/child 생성시각/명령 신원을 보존하고, active/unknown 상태의 회수·force-stop을 금지한다. receipt 누락은 성공이 아니며 stale heartbeat나 PID 단독으로 강제 종료하지 않는다. 복구는 별도 output의 1회 claim, 원 계획의 남은 시간 안에서 원자료 회수·cleanup만 수행하고 추론/세션 재개를 하지 않는다. [근거·검증](ENERGY_AP_HOST_LIFECYCLE_PC_20260928.md).
- **준비만 완료:** 동일 APK의 `ENERGY-AP-HOST-DIAG-01`은 1세션·12명시 추론·25분 상한의 PC 후보이며 아직 미승인·미소비다. 앱 준비 중 정상 완료를 지원하지 않아 host 요청 stop은 앱 cleanup 성공 증거가 아니다. Android 변경/APK 재설치나 진단 실행은 이번 결정에 포함되지 않는다.
- **보존:** COLLECT-04 원인 미확정·`stopped_no_resume`, 기존 FAIL·부분 자료·동결값 및 `experiment_ready=false`. 에너지·AP 모형 지원 확대·6세션 재수집·정책 개발은 채택하지 않는다.

## 2026-09-28 — 설치 검증 APK 재사용 수집 승인분의 중단 판정

- **승인·실행:** 사용자가 기존 측정 설계의 새 설치 없는 수집을 개발3→동결→확인3, 추론 최대10,152·전체 최대230분·재시도0으로 승인했다. plan_v4는 설치본 확인 host pull 최대1, APK push/설치0, 계획 전체225분 상한으로 고정했다. [결과](ENERGY_AP_STATE_COLLECT04_RESULTS_20260928.md)의 `Run` 1회에서 첫 개발 세션만 시도했다.
- **판정:** 온도 준비 중 host 실행기 종료, 정상 종료 receipt 부재, 완료0/6. 기록으로 runtime4·warmup8·적격성4·작업0 시작/완료를 확인했지만 기록 공백의 호출을 무조건 0으로 단정하지 않는다. 앱 cleanup 미확인, 별도 host force-stop/프로세스 부재 확인. 이 ID는 `stopped_no_resume`이며 개발 동결/확인/모형 적격성/정책 절감 증거가 아니다.
- **보존·다음:** 기존 종료 계획·원본·FAIL·동결값·`experiment_ready=false`를 유지한다. 후속 PC 진단은 host 종료/receipt/cleanup 경계에 한정하며 이 승인으로 기존 또는 새 실측 계획을 자동 실행하지 않는다.

## 2026-09-27 — COLLECT-03 전송 중단과 배포 복구를 분리

- **채택된 범위:** 기존 `stopped_no_resume` 수집을 보존하고, [별도 배포 복구](ENERGY_AP_DEPLOY_RECOVERY_PC_20260927.md)를 PC에서 준비한다. 기존 단계형 push/원격 SHA-256/설치/설치본 SHA-256을 재사용하며 Android·APK·수집 설계를 변경하지 않는다. 이 준비는 배포 실기기 실행이나 후속 수집 승인이 아니다.
- **근거·한계:** 101.18MiB 후보의 `adb push` client가 120초 timeout; 원격 byte 수와 전송 지연 원인은 미확정. 새 배포 ID의 상한은 600초·전송/설치 각1·재시도0·수집0이다. 정확한 APK 설치 검증 후에도 새로운 수집 ID·계획·환경 gate·별도 승인 없이는 세션을 시작하지 않는다. 기존 FAIL·동결값·`experiment_ready=false` 유지.
- **후속 실행:** 사용자가 무선 ADB 단일 복구를 별도 승인했다. [결과](ENERGY_AP_DEPLOY_RECOVERY_RESULTS_20260927.md)는 기존 설치본 pull 1회 완료·후보 push 1회 120초 timeout·설치/수집0, `stopped_no_resume`다. 동일 계획의 재실행은 금지한다. 무선 자체 원인·원격 전송량은 미확정이며, 실패 결과를 원래 수집의 설치/개발 표본에 합치지 않는다.

## 2026-09-27 — 모형 지원 범위와 독립 확인을 정책 개발보다 우선

- **채택:** 사용자의 최신 목표에 따라 실측 보정 에너지·AP 모형의 상태·전환 지원과 별도 자료 예측 오차 확인을 우선한다. 새 정책·강화학습 구현/튜닝은 보류한다. 소비 에너지 J를 배터리 잔량/사용시간으로 환산하지 않는다.
- **근거·판정:** [ENERGY-AP-MODEL-BRIDGE-PC-02](ENERGY_AP_MODEL_BRIDGE_PC_20260927.md)의 고정 CC_DG 개발 상태 전력은 기존 확인 실제 점유 일정에 조건부 대입 가능하지만, 고정 480초 병행−직렬 에너지 차이 방향조차 확인에서 재현하지 못했다. AP 상태 동역학·다른 joint 비용은 미식별. 확인 요약 열람 뒤 만든 v2 지표는 사후 진단이지 새 독립 확인이 아니다.
- **범위:** 기존 profile/FAIL/부분 결과/원자료/종료 계획과 합성 가정 탐색을 보존한다. 임의 도착은 `UNSUPPORTED_STATE_COSTS`로 차단하며, 실측 기반 정책 우월성이나 `experiment_ready=true`로 승격하지 않는다. 최소 추가 수집 후보는 미승인·실행 미준비다. S26 계수를 A24에 전용하지 않는다.

## 2026-09-27 비교 기준선 검토 완료 — 경로 C 권고, 새 비교 채택 아님

- **확인 사실:** [기준선 검토](ARRIVAL_BASELINE_REVIEW_20260927.md)에 따라 현재 앱 본체와 정책 도입 전 benchmark에는 혼합 두 과업 scheduler가 없었다. CPU_FIFO·CPU_URGENT는 후속 격리 실험의 자체 기준이고, B2_PC·B3_SOLO_EFT_PC는 연구용 고정/축소 구현이다. 공개 Ente·MediaPipe·Band의 분류와 의미 차이를 출처로 확인했다.
- **권고 상태:** 외부 전체 앱 성능을 스케줄링 효과로 혼동하지 않고 동일 엔진의 합성 비교군과 개발 고정 강한 B2/B3를 유지하는 경로 C를 권고한다. 외부 adapter 구현·기기 실행·프로젝트 목표 변경은 채택하지 않았다. 기존 합성 연구 선택과 P 불리 결과, FAIL·원자료·동결값·종료 계획·`experiment_ready=false`는 불변이다.

## 2026-09-27 첫 offline 행동을 온라인 규칙으로 승격하지 않음

- 상태: 이번 PC 진단의 구현 판단. 프로젝트 목표나 서비스 기준 변경 아님.
- 근거: [ARRIVAL-INFORMATION-CHECK-PC-01](ARRIVAL_INFORMATION_CHECK_PC_20260927.md)의 사전 고정 2사례×6미래 분기에서 동일 첫 관측 snapshot임에도 CPU/GPU 첫 배정의 에너지·AP·요청별 응답 손익이 뒤집혔다. 수치 허용오차 이내 전 분기 비악화 gate 실패.
- 결정: 기존 `THERMAL_ENERGY_PC_V1`과 완전 offline 결과를 보존하고 이번에는 새 온라인 후보를 구현하지 않는다. 미래·실현비용을 아는 offline 개선을 배포 가능 성능으로 승격하지 않는다. 조건부 별도 확인은 실행하지 않았고 `experiment_ready=false`를 유지한다.

## 2026-09-27 — 작은 합성 사례의 제한된 offline 일정 기준

- **채택한 PC 범위:** [탐색 계약·결과](ARRIVAL_OFFLINE_SCHEDULE_PC_20260927.md)의 사전 고정 2/3요청·3사례·seed301·전력/AP 스트레스 profile·0/250/500ms 연구용 응답 손실만 기존 이벤트 엔진의 opt-in 일정 provider로 열거한다. 미래 도착/실현 비용을 이용하는 offline 참고값이며 현재 Android/온라인 정책, B2 개발 선정, CAL-03 동결 계수, 기존 192회 결과는 변경하지 않는다.
- **판정:** 제한 행동 공간의 완전 탐색에서 열·에너지 후보 대비 손실0의 개선 일정은 없고, 손실 허용 시 일부 에너지/AP 개선 일정이 나타났다. 수치 tolerance는 실질 절감 기준이 아니며, AP 연구 한도 초과·작은 요청 수·미측정 W/AP·판단비용 차이를 보존한다. 이는 온라인 정책 수정·실기기 최적성·서비스 합격 결론이 아니다. 다음은 발견한 선택의 현재 정보 구별 가능성만 검토한다. 새 실측/정책 튜닝·`experiment_ready=true` 결정은 아니다.

## 2026-09-27 온라인 에너지·AP 피드백 후보의 PC 탐색

- **채택 범위:** 별도 `THERMAL_ENERGY_PC_V1` 탐색 후보를 기존 arrival 엔진에 선택적으로 연결한다. 현재 도착·lane·모형상 AP·동결 시간 추정과 명시적 예상 전력/AP만 판단에 사용한다. 기존 P·기본 실행·CAL-03 동결·Android 정책은 바꾸지 않는다. 미측정 상태는 strict에서 지원하지 않는다.
- **비교와 판정:** [계약·결과](ARRIVAL_THERMAL_FEEDBACK_PC_20260927.md)의 사전 설정으로 CPU_URGENT·개발 고정 B2·B3와 같은 PC trace/seed/실현 비용·공통120초를 비교했다. 미측정 W/AP/연구용 한도는 스트레스 가정이다. PC 확인에서도 일부 에너지/AP 개선은 응답 또는 일반 서비스 손실과 상충한다. 확인 결과로 정책·계수·기준을 재튜닝하지 않았고 실기기 절감·열 안전·우월성을 채택하지 않는다.
- **보존:** 기존 FAIL·부분 결과·원자료·종료 계획과 `experiment_ready=false`, S26/NPU 별도 범위는 그대로다. 추가 실측·Android 연결은 이번 결정에 포함되지 않는다.

## 2026-09-26 — 합성 도착 Android 수집의 제한된 두 arm 후보

- **채택 범위:** 기존 채택된 합성 연구 질문의 첫 Android 기술 관측 후보를 `CPU_URGENT`와 `FIXED_SPLIT`으로 제한한다. 두 arm의 큐 우선순위는 같고 배정·병행 허용이 다르다. [후보 계약](ARRIVAL_ENERGY_ANDROID_PREP_20260926.md)은 고정 trace의 기기 전체 에너지/AP·긴급/일반 응답을 같은 120초 창에서 기술한다. 강한 B2(분류 GPU＋탐지 CPU)를 이번 고정 분리와 동일시하거나 기준 정책을 재선정하지 않는다. 목적 B의 새 도착 상태별 보정은 이 후보의 자동 성과로 간주하지 않는다.
- **검증 상태:** PC 구현·관련 테스트·서명 APK/계획 dry-run까지이며 **기기 실행/에너지 절감/열 모형·정책 우월성 검증은 0**이다. 12세션은 조건별 단계당 1독립 세션의 coverage 후보이지 충분한 통계 표본 수가 아니다. 새 실행 승인·현재 gate 이전에 계획을 소비하지 않는다. 과거 FAIL·원본·동결값·`experiment_ready=false`와 S26/NPU 별도 개발 유지.

## 2026-09-26 — 출처를 밝힌 합성 도착 연구 범위 채택

- **사용자 채택:** [합성 도착 PC 계약](ARRIVAL_ENERGY_SYNTHETIC_RESEARCH_20260926.md)에 따라 실측 보정 모형과 출처가 명시된 합성 조건에서 긴급 응답·일반 완료·기기 전체 에너지·AP 경로의 상충을 연구한다. 발열·배터리·응답을 함께 다루는 원래 목표와 고정 CC_DG 중간 질문은 유지한다. 실제 서비스 SLA·실사용 배터리 절감·AP 안전 한도·정책 우월성을 채택하지 않는다. 이미 사용한 low/queue/burst와 연구용 1.5/6초 기한을 성능 확인에 재사용해도 새 독립 평가로 부르지 않는다.
- **구현/검증 상태:** 별도 PC v1은 scenario ID·분모를 고정하고 응답/저장/lane 해제·120초 공통창을 집계한다. 고정870건 profile에서 임의 도착의 전력·열을 보간하지 않는다. 명시적 가정 profile이 없는 에너지/AP는 `null`이다. 관련 unit 검증만 완료했고 Android active 정책·새 상태별 에너지/AP 보정·독립 평가는 미실시다. 기존 FAIL·부분 결과·40값/20null·종료 계획·`experiment_ready=false`·S26/NPU 별도 범위 유지.

## 2026-09-26 — 고정 CC_DG를 발열·배터리 연구의 중간 질문으로 채택

- **사용자 채택 범위:** [원래 목표까지의 실행안](ENERGY_THERMAL_TO_ORIGINAL_GOAL_PLAN_20260926.md)에 따라 동일870건 CC_DG 직렬/병행의 완료시간·공통480초 조건부 기기 에너지·AP 경로 상충을 **중간 연구 질문**으로 사용한다. 최종 목표는 혼합 도착 요청의 대화형 응답·일반 완료 제약 아래 에너지/열 부담을 줄이는 자원·시작/대기·병행 결정으로 유지한다. 고정 묶음의 요청별 SLA나 사용자 서비스 기한, 최소 의미 절감량·AP 안전 한도를 채택한 것은 아니다.
- **검증 상태:** 두 block의 병행 완료시간 단축은 관측됐으나 공통창 에너지 차이 방향은 뒤집혔다. 에너지 절감·열 안전·동적 정책 우월성/일반화는 미입증이다. `decision-preview-v2`는 확인 두 arm의 29.1°C 회고 예시를 출력에 표시하고 모형 후보를 배포 후보로 부르지 않는다. Android/동결 profile/원자료/종료 계획·기존 FAIL·`experiment_ready=false`는 불변이다. 새 실측 승인이나 최종 목표 축소가 아니다.

## 2026-09-26 — 29.1°C 회고적 적용 조건의 의미 명확화

- **기존 결정의 해석:** [연구 설계 검토](ENERGY_THERMAL_RESEARCH_SCOPE_20260926.md)에 따라 고정 CC_DG 선택기의 29.1°C 검사는 두 **확인** arm의 단일 오차 시나리오를 같은 관측 시작 AP에서 기술하기 위한 회고적 제한이다. 개발 시작 AP는 직렬 29.4°C·병행 29.2°C다. 29.1°C를 사용자 요구·물리적 안전/일반 적용 한도나 개발 동결 기준으로 채택하지 않는다. AP 변화량의 시작값 평행 이동은 미검증 가정이다.
- **상태:** 고정 묶음의 완료기한·공통창 에너지 질문은 후속 **권고**일 뿐 최종 목표 변경이 아니다. 서비스 기한·AP 한도·최소 의미 절감량은 미합의이고, 동결 모형/코드/기존 결과와 `experiment_ready=false`는 유지한다.

## 2026-09-26 — 운영 비교의 PC 제약 탐색만 허용

- **채택 범위:** [판단·분해 보고서](ENERGY_OPERATIONAL_DECISION_PC_20260926.md)에 따라 기존 동결 CC_DG profile의 사용 범위를 A24·동일870건/입력/resident·명목480초 기기 전체 조건부 에너지와 부하 완료시간·AP 최고온도로 제한한다. 사용자가 서비스 기한·AP 기술 한도를 제공할 때만 모형상 제약 충족을 계산한다. 기준 미정은 `null`로 두고 단일 최적 정책/안전 기준을 확정하지 않는다. 지원 외 요청·전체 운영 에너지·BAT·임의 도착은 차단한다.
- **검증 상태:** PC 분해 항등식과 조건부 분기만 확인했다. 확인 arm당1세션의 오차는 사후 민감도이며 신뢰구간/상한이 아니다. 공통창 에너지 예측의 직렬/병행 방향 불일치를 수정값으로 숨기지 않는다. 기존 Android 배정·CAL-03 동적 정책·동결 모형·FAIL·`experiment_ready=false`는 불변이다. 새 실기기 실행이나 발열·배터리 최적화 PASS 결론이 아니다.

## 2026-09-26 — CC_DG 운영 4세션의 격리된 PC 모형 사용 범위

- **채택 범위:** [연결 결과](ENERGY_OPERATIONAL_SIM_CONNECTION_20260926.md)의 A24·동일 모델/입력·4-runtime resident·CC_DG 동일 870건 묶음에서 개발 직렬/병행 각1세션의 단계별 시간·기기 전체 평균전력·AP 경험 경로만 별도 템플릿으로 사용한다. 원본 trace 재생, 개발 템플릿의 조건부 예측, 미측정 조건의 탐색 가정을 구분한다. 기본 정책·과거 시뮬레이터 지원 조합은 변경하지 않는다.
- **검증 상태와 제한:** 확인 각1세션의 완료시간/완료시점 에너지 방향은 일치했지만 공통480초 에너지 차이 방향은 불일치한다. 확인 요약을 이미 본 뒤 작성한 PC 연결로 사전등록 독립 검증이 아니며 PASS 기준이 없다. 미계측 전환·냉각 에너지는 0이나 전체 운영 에너지로 승격하지 않는다. AP를 BAT 모형으로 전용하지 않고 전류 단위·인과/반복성 한계를 유지한다. 정책 우월성·`experiment_ready` 판정과 기존 FAIL·동결값은 불변이다.

## 2026-09-26 — 준비 상태 비대칭 확인과 운영 비교의 별도 PC 경로

- **PC 구현 결정:** [종합 검토](ENERGY_DESIGN_REVIEW_20260926.md)의 운영 전용 namespace를 추가한다. 같은 초기 상태 비교와 준비/대기 포함 운영 비교를 혼동하지 않는다. 운영 후보만 동일 직렬2→host확인→병행2 기술 probe, 고정120초 resident 노출, 공식 baseline1회로 준비한다. 기술적 적격성과 긴 비교 표본 순서를 분리한다. 기존 COLLECT-05의±0.5/±0.25°C 기준·실패는 소급 변경하지 않는다.
- **검증 상태:** 원문 parser/회계 재생·관련 PC 테스트·후보 APK/서명/manifest 준비만 완료. 평형 도달시간·내부 열 동등성·병행 에너지/발열 효과는 미확인이다. 한 조합4세션 AB/BA는 권고안이며 실행·프로젝트 전체 목표 변경 승인이 아니다. 절감/정밀도/정책 PASS 기준을 임의 도입하지 않는다.
- **보존:** 옛 원자료·진단·완료 직렬은 새 표본에 합치지 않는다. setup/gate 비용과 미완료·cleanup 에너지 누락을 드러내고 준비비용을 절감으로 숨기지 않는다. 기존 FAIL·40값/20null·experiment_ready=false·S26/NPU 별도 개발 유지.

## 2026-09-26 — COLLECT-05 사전 AP 준비의 PC 후보, 실기기 미승인

- **채택 범위:** 종료된 COLLECT-04의 +0.8°C paired AP gate 실패에 대해 공식 baseline 이전 resident 상태에서 제한된 온도 관측을 하는 **별도 개발 후보**를 준비한다. 60초/20표본/범위0.3°C, paired anchor ±0.25°C, 대기 최대360초는 prospective 설계값이며 기기 검증 전 안정성 기준 PASS가 아니다. 확인 병행 anchor는 같은 단계·같은 pair의 직렬 세션에서만 취한다. 최종 ±0.5°C paired gate, 원래 비교군·순서·분모·개발 동결/확인 분리, retry0은 유지한다. [근거·한계·예산](ENERGY_THERMAL_TEMPERATURE_PREP_20260926.md).
- 준비 대기 시간·에너지를 따로 기록하고 전체 비용에서 숨기지 않는다. PC 테스트·서명·계획 Check만 통과했으며 실기기 gate/병행/장기 안전성·에너지 절감은 미검증이다. COLLECT-04 완료 직렬 및 중단 표본을 새 개발/확인에 합치지 않는다. 새 계획 실행 승인이나 `experiment_ready=true` 결정이 아니다.

## 2026-09-25 — 수정 sampler 정식 수집의 별도 계보·PC 준비

채택/PC 준비: [COLLECT-04 계약](ENERGY_THERMAL_COLLECTION_REPREP_04_20260925.md)에 따라 새 ID·run/registry를 사용하고 종료된 COLLECT-03와 성공한 직렬 진단을 입력 해시로 **연결하되 표본으로 합치지 않는다**. 수정 APK/프로젝트 서명과 동일 화면 필터를 개발·확인 전체에 쓰며 기존 두 직렬 대조·두 병행 배정, 개발4→동결→확인4, 220분 hard 상한·재시도0·환경/품질/병행 gate를 유지한다. PC 관련3건과 plan_v7 Check 통과; 실기기 병행/반복 안정성·에너지 절감·정책 우월성은 미검증이다. 이번 결정은 새 수집 **실행 승인이나 experiment_ready PASS가 아니다**. 기존 판정과 원자료를 보존한다.

## 2026-09-25 — 공유 상태 snapshot 일관성과 실패 증거 보존

[ENERGY-SAMPLER-PC-01](ENERGY_SAMPLER_PC_20260925.md)에서 toMap size/순회 경쟁을 PC 재현했다. phase/active/resident metadata의 동일 lock 복사와 예외 detached 증거 게시→stop→sidecar 저장을 채택한다. 센서 전체의 동시성이나 과거 발생 행을 확정하지 않는다. 계측 비용이 바뀌므로 새 APK 계보를 사용하고 기존 부분 표본과 합치지 않는다. 정식8세션 전에 원래 실패 구간을 포함하는1세션 부하 진단 후보만 준비하며, 실행은 미승인이다. 실기기 안정성/에너지 절감/experiment_ready PASS를 부여하지 않는다.


## 2026-09-25 — COLLECT-03 계약상 중단과 부분 자료 보존

사용자가 plan_v5 8세션/6976진단/64warmup/7040추론/220분을 승인했다. 실제 설치 생략·첫 개발 세션 sampler 예외로 stopped_no_resume 종료. [결과](ENERGY_THERMAL_COLLECT03_RESULTS_20260925.md). 개발 적격0이므로 동결/확인 및 병행 비교를 수행하지 않았다. 원 receipt·미확인 범위·기존 증거와 experiment_ready=false를 유지하며, 추가 실측 대신 PC 예외 경로 확인을 권고한다.


## 2026-09-25 — 에너지 수집 재준비의 관측 일관성

사용자 승인 범위는 PC 재준비·Git 공유다. [COLLECT-03 후보](ENERGY_THERMAL_COLLECTION_REPREP_20260925.md)에 새 식별자/출력/registry와 모든 새 개발·확인의 동일 필터 관측을 고정했다. 기존 APK·비교 설계·동결/판독 기준·timeout/중단 규칙은 유지한다. 옛 중단자료는 새 표본에서 제외한다. 무추론32조회 이후 관행적인 추가 진단을 만들지 않되 부하 중 안정성을 선언하지 않는다. 새 수집은 별도 실행 승인과 현재 gate가 필요하며 experiment_ready=false다.


## 2026-09-25 — ENERGY-SCREEN-OBSERVE-02 제한된 기기 동작 확인

새 승인으로 실제저장ADB원문 parser 재생 후 무추론32조회 완료했다. [보고서](ENERGY_SCREEN_OBSERVE_02_20260925.md). 각76bytes로 전송량은 줄었으나 중앙0.578초로 이전부하31회0.422초보다 짧지 않았다. 조건불일치이므로 인과속도/에너지효과를 주장하지 않는다. 부하중안정성·과거원인해결·전체수집적격성은 미확인, 기존 stopped계획과 experiment_ready=false 보존. 추가실측은 실행하지 않는다.


## 2026-09-25 — ENERGY-SCREEN-OBSERVE-01 조회 전 host gate 오류

32조회/480초 사용자 승인으로 새진단1회를 시작했으나 battery bytes/str 경계결함으로 화면조회0에서 중단했다. [결과](ENERGY_SCREEN_OBSERVE_20260925.md). decode를 PC에서 수정하고 실제parser 테스트를 추가했으며 재실행하지 않았다. 종료계획·원소스hash·기존 미확인값 보존, 필터 기기PASS나 timeout원인해결로 해석하지 않는다.


## 2026-09-25 — ENERGY-SCREEN-DIAG-PC-01 관측량 축소·중단 의미 보존

기존32화면조회 중 timeout1의 내부 원인은 미확정이다. [PC 진단](ENERGY_SCREEN_DIAGNOSIS_PC_20260925.md)에 따라 에너지 host 경로만 필수상태+producer종료 marker를 전송한다.2초/cadence/재시도0/조회불가중단은 유지하며 기기 생성비용 감소나 재발 해결을 주장하지 않는다. PC24건·보존로그31건 재생 완료, 기기확인은 미실행이다. 새 관측 방식의 에너지를 옛 부분값과 동일 조건으로 합치지 않는다. 종료 plan_v4는 원소스/원hash 그대로 보존하고 자동 재개하지 않는다.


## 2026-09-25 — ENERGY-THERMAL-COLLECT-02 승인 실행·계약상 중단

사용자는8세션/진단6976/warmup64/총추론7040·상한220분을 승인했다. 시간 문구만206분40초 timeout 합산 예약으로 정정하고 코드/계획 hash/기준은 유지했다. 설치1 성공 후 첫 개발 세션 화면 조회2초timeout에서 중단 규칙을 적용했다. 회수 prefix와 host cleanup을 보존하고 재실행하지 않는다. 상세 [결과](ENERGY_THERMAL_COLLECTION_EXECUTION_20260925.md). 부분 자료는 모형 동결·절감/병행/정책 우월성 PASS 근거가 아니며 기존 보존 조건 불변이다.


## 2026-09-25 — ENERGY-THERMAL-COLLECTION-PREP-02: 실제 직렬 대조와 두 병행 조건

- **채택 범위:** 사용자 지시에 따른 PC 실행 준비. [계약](ENERGY_THERMAL_COLLECTION_PREP_02_20260925.md)의 두 배정×직렬/병행4조건을 개발/확인 각1세션으로 구성한다. 실제 동일 작업 묶음678분류+192탐지를 사용하고, 단독합을 직렬 실측으로 대체하지 않는다. 단독4경로는 직렬 구간에서 관측하되 잔열/순서 한계를 공개한다.
- **구현 결정:** 기존 정책/timeout과 분리한 신규 Activity·protocol, runtime4 resident, 실소유 worker/lane 해제, 연속 raw telemetry와 bounded 비동기 journal. short probe·출력 회귀·GPU 위임/실제 overlap·baseline AP matching 후 긴 부하를 허용한다. 공통480초 및 resident cooling180초로 대기 에너지 누락을 막는다. 새 임의 offset/duty는 추가하지 않는다.
- **검증 상태:** Python17/Kotlin6·관련 compile/서명/dry-run 완료, 실기기0. 요청6976/warmup64/총추론7040·상한220분은 권고 예산이며 실행 승인 미포함. 설치본·두 병행 적격성은 실제 단계 gate가 필요하다. 조건당 독립세션1/단계라 정확도·절감·정책 우월성 PASS를 약속하지 않는다.
- **보존:** 옛 후보/빌드/계획도 덮어쓰지 않는다. 기존 FAIL·부분 결과·40값·20null·종료 계획·experiment_ready=false 유지. S26/NPU 별도 협업 및 기기간 계수 전용 금지 유지.

## 2026-09-25 — ENERGY-THERMAL-PC-01: 필수 에너지·발열 목표와 제한된 PC 보정

- **채택:** 사용자 명시 요구에 따라 발열·배터리 최적화를 필수 목표로 기록한다. 동일 작업량/품질/서비스 제약 아래 평가하며 단순 안전 gate로 축소하지 않는다. 일시정지 중심 Android 작업은 현재 보류한다. 과거 FAIL이나 목적을 소급 대체하지 않는다.
- **구현 결정:** [별도 계약](ENERGY_THERMAL_PC_01_20260925.md). 기기별 raw 단위 후보와 counter 일관성을 분리하고 임의 배율 fit을 하지 않는다. 기기 전체 전력 적분과 상태 기반 센서별 열모형을 독립 보정한다. baseline은 주변온도가 아니며 old idle은 resident idle이 아니다. 기기·모델·condition·센서·지속시간/온도 범위를 검사한다. 미측정 병행 전력을 자동 합산하지 않는다.
- **검증 상태:** 기존160세션 추출/사후 내부 확인·PC18테스트·작은 재생 완료. 절대 전력 정확도, 현재 두 모델 절감, 고온 성능 관계, 새 정책 우월성은 미검증이다. 현재 두 모델은 명시적 가정 모드 외 실측 기반 연결을 차단한다. 실측0, 추가 수집은 [8세션 후보](ENERGY_THERMAL_COLLECTION_PROPOSAL_20260925.md)로만 제시한다.
- **보존:** 기존 FAIL·부분 결과·40동결값·20null·종료 계획·experiment_ready=false 유지. S26/NPU 채택·별도 개발 유지, S26 계수를 A24에 전용하지 않는다. 이번 완료를 정확도/성능 PASS나 실기기 승인으로 해석하지 않는다.

## 2026-09-25 — REPLAN-PC-01: 조작 기반 시작 제한의 별도 후속 개발

- **채택 범위:** 사용자 승인에 따라 공개 앱의 조작 후 배경 제한을 참고한 요청 단위 시작 허용과 우선순위·정적 배정을 분리 비교하는 후속 개발에 착수한다. 기존 긴급 성능 목적/독립 평가 FAIL은 그대로이며 이 기록은 새 정책 우월성·실기기 예산 승인이 아니다. [별도 계약](REPLAN_PC_01_20260925.md).
- **확정한 PC 의미:** 조작과 AI 도착은 별도 입력, 기본 유휴15초는 고정 공개 코드의 참고값이다. normal의 새 dispatch만 제한하고 urgent는 자원/비선점 제약 아래 처리한다. 같은 시각에 조작을 만료/dispatch보다 먼저 적용한다. 진행 중 판단의 배경 선택은 dispatch 직전 재검사하고 취소 시 큐 순서·소모 비용을 유지한다. 실제 lane 해제 전 재사용하지 않는다. stale 만료와 no-selection 무한 호출을 막는다.
- **비교 공정성:** CPU 고정과 정적 배정에 같은 EDF/aging kernel을 사용하며 과거 CPU_URGENT FIFO의 의미를 바꾸지 않는다. 제한 on/off에 같은 사건 관측을 적용한다. 두 규칙의 개발 승자가 다르면 교차 적용하며 후보·개발 예산을 동등하게 둔다. 이번에 후보 선정·새 P·timeout 튜닝을 하지 않는다.
- **검증 상태:** 새 PC 기능/작은 합성 trace와 직접 영향받는 기존 엔진 검증 완료. 실제 기기 timer/dispatch·새 병행 조합·응답 품질/성능은 미검증. gate 관측 처리비용0은 미측정 PC 가정이다. Ente의 stage/전체 앱, UI 끊김, 현실 수요를 재현·입증한 것으로 쓰지 않는다.
- **보존/미확정:** 40동결값/20null/FAIL/부분 결과/종료 계획/experiment_ready=false·S26/NPU 별도 개발을 유지한다. margin·최소효과·독립 block 수·측정 예산은 아직 미정이다. 특정 과업 인터뷰는 보조 근거이며 필수 진행/전환 gate로 채택하지 않는다. 다음 기기 실행에는 별도 승인과 새 계획이 필요하다.

## 2026-09-25 — 후속 확인 완료와 가정 기반 PC 정책 비교

- 채택/실행: 사용자 승인 1계획/최대3세션·진단12/warmup24/설치0/45분 안에서 준비된30분 수집 계약을 실행했다. 추가 지시에 따라 배터리 시작/실행 하한20%만 실행 전 계획v4에 고정했다. 다른 gate는 불변이며 원계획의 배터리 조건을 소급 변경하지 않는다. 실제3/3 완료·cleanup 확인, 개발동결 불변·기존 부분 계획 분모 보존. 확인 후 수치 재튜닝 없음.
- PC 수정/검증: 후속3조건 집계를 기존6조건과 구분한다. 실측 연결은 정확한 recorded trace/조건별 비용 조회로 제한한다. 기록된 병행을 임의 도착의 병행 모형 검증으로 승격하지 않는다.
- 채택/탐색 범위: 사용자가 시뮬레이터 구현·배치 비교를 추가 승인했다. CAL-03 개발 숫자 파생 입력으로 새 PC namespace의 엄격 직렬/명시적 병행 가정 모드를 구현했다. B2를 개발에서 고정하고 B3/P/제거군을 별도 scenario/seed로 비교한다. 숫자 가정과 B2 개발 손실0은 탐색 관례이며 프로젝트 성공 기준·비열등성 margin이 아니다. 실측 세션과 시뮬레이션 반복을 구분한다.
- 결과/축소 판단: 최종 P는 기본 큐 B3 대비 긴급−4.11%/일반+3.14%이나 B2 대비 긴급+138.03%이고 다른 조건에서는 더 큰 손해다. 추가 P 기여·우월성의 근거로 삼지 않는다. strict B3/P 동일성, explore B2 반대 조합의 실측 미지원도 공개한다. 다음은 일반 서비스 제약·정적 기준의 검토이며 추가 실측 자동 실행은 없다.
- 미충족: Android 새 active B3/P, 새 병행 조합·예측 허용 기준, 일반 서비스 목적/손실·세션 표본 설계, 실제 기존 시스템 비교. PC 실행 가능과 독립 기기 평가 준비를 구분하고 `experiment_ready=false`, 기존FAIL/40값/20null/원본을 유지한다. [구현·결과·정정 이력](ARRIVAL_FOLLOWUP_AND_EXPLORATION_20260925.md).

이 문서는 방향 변경을 날짜순으로 기록한다. 각 항목에 제안 / 채택 / 대체됨 상태를 표시한다. 아래 초기 항목은 이전 계획에서 이관한 작업 방향이며, 개별 수치·실험 조건 확정을 의미하지 않는다. 이번 개정은 사용자 요청에 따른 문서 보강이다.

> 현재 계획은 개정4.4에 날짜별 후속 결정을 적용한다. S26·NPU 범위는 [2026-09-24 협업 결정](#s26-npu-20260924)을 우선한다. 과거 결정은 이력으로 보존한다. 새 시나리오·모델 후보·효과 수치는 아래에 명시한 검증/미확정 상태를 유지한다.

## 2026-09-15 — 프로젝트 목표 재정의

- 단일 Android 앱의 긴급·일반 AI 요청 스케줄링 문제로 범위를 고정한다.
- 운영체제 전체의 자원 스케줄러는 범위에 포함하지 않는다.
- 초기 주목적은 긴급 요청 P95 응답시간 감소로 두었다. DEFINE-01에서 안전·정확도와 긴급 마감 위반을 P95보다 앞선 사전적 우선순위로 구체화했다.
- 근거: 기기별 CPU/GPU 성능 차이는 확인했지만 동적 정책의 추가 효과는 아직 확인되지 않았다.

## 2026-09-15 — 초기 구현 범위

- 현재 모델, CPU/GPU, 긴급·일반 두 요청 종류, 비선점 실행을 초기 범위로 한다.
- CPU와 GPU의 동시 실행은 간섭을 별도로 확인하기 전에는 사용하지 않는다.
- NPU와 강화학습은 초기 완성의 필수 조건에서 제외한다.

## 2026-09-15 — 비교정책과 평가 원칙

- B0: 기기별 최속 고정 backend + FIFO.
- B1: 기기별 최속 고정 backend + 긴급 우선.
- B2: CPU/GPU 고정 후보에 긴급 우선·단순 열 대응을 적용하고 개발 자료로 선정. 짧은 단독 추론 최속값만으로 고정하지 않는다.
- P: 큐·마감·열 상태를 함께 사용하는 제안정책.
- 같은 요청 도착 기록, 입력, 마감시간, 만료·거절 규칙과 종료 규칙으로 비교한다.
- 전체 도착 요청을 분모로 사용하며 실패와 미완료를 제외해 P95를 유리하게 만들지 않는다.

## 2026-09-15 — 증거 분리

- A24/S26 formal, diagnostic v2 trace-off/on, 새 혼합 요청 실험을 서로 합치지 않는다.
- 원시 자료는 불변으로 보존하고 파생 분석은 새 경로와 입력 해시를 갖는다.
- 온도 차이를 에너지 차이로 표현하지 않는다.

## 2026-09-15 — 문서 개정 2

- 상태: 채택 — 사용자가 검토사항을 반영한 수정을 요청함.
- 내용: 선택적 읽기, 단계별 체크포인트, 읽기 전용 예외, 증거 버전 연결, 조건부 P95와 전체 서비스율 분리, B2 후보 선정 보강.
- 미확정: 36세션, 개선 10%, 허용 감소 2%p, 실제 마감·열 기준. 개발 결과와 사용 요구를 근거로 평가 전에 고정한다.
- 영향: AGENTS, STATUS, PLAN, 설치 안내. 구현·실기기 실행을 수행했다는 뜻은 아니다.

## 2026-09-15 — DEFINE-01 공식 사용·평가 계약

- 상태: 채택 — 사용자가 프로젝트의 공식 정의로 명시함.
- 범위: D1Check는 Android 운영체제 전체가 아니라 하나의 온디바이스 AI 앱 내부에서 CPU/GPU/NPU 후보를 선택하고 긴급·일반 요청 큐를 관리하는 애플리케이션 수준 스케줄러다.
- 사용자 시나리오: 긴급 요청은 사용자가 갤러리 사진 한 장의 즉시 분류 결과를 요구하는 대화형 작업이고, 일반 요청은 여러 갤러리 사진을 백그라운드에서 분류·색인하는 일괄 작업이다.
- 완료 시점: 긴급 응답은 앱 큐 진입부터 결과가 사용자에게 제공 가능한 시점까지, 일반 요청은 큐 진입부터 해당 이미지 결과 저장까지다. 순수 `Interpreter.run()` 지연과 종단간 지연을 분리한다.
- 일반 작업 처리 후보: 현재 일반 이미지 완료 후 긴급 실행, 다음 이미지 경계에서 일반 batch 중단, 다른 가용 자원 동시 실행을 비교한다. `Interpreter.run()` 중간 강제 중단은 가정하지 않는다.
- 자원: 1차 구현은 CPU/GPU다. NPU는 capability detection과 실제 실행 검증을 통과한 기기에서만 활성화하며, 미지원·접근 실패 시 CPU/GPU로 정상 동작한다. S26의 현재 NNAPI 노출은 `nnapi-reference` CPU뿐이며 NPU 지원은 성공 필수조건이 아니다.
- KPI: 긴급 output-ready 응답시간 P95, 긴급 마감 위반율, 일반 기한 내 완료율, 전체 도착 대비 완료율, 처리량, 최고 온도 또는 Android thermal status, CPU/GPU 실제 사용 비율, 정확도 검증 통과 여부를 각각 보고한다. 실패·거절·만료는 전체 도착 분모에서 제외하지 않는다.
- 목적함수: 안전·정확도 제약, 긴급 마감 위반 최소화, 긴급 P95 최소화, 일반 기한 내 완료율 최대화, 처리량 최대화, 온도·전환 비용 최소화의 사전적 순서를 사용한다. 가중합은 아직 채택하지 않는다.
- 마감시간: 상태는 `calibration_pending`이다. 기존 80슬롯은 순수 추론 중심이므로 CALIB-01의 실제 이미지 종단간 측정 후 평가 전에 절대값을 사전 고정한다.
- 연구 근거: A24에서는 CPU 중앙 약 41.2 ms 대 GPU 약 131.6 ms(GPU/CPU 약 3.196), S26에서는 GPU가 pooled CPU보다 duty별 약 1.062~1.201배 빨랐다. 자원 우열이 기기마다 달라 기기별 calibration이 필요하다.
- S26 공시: 20개 block-duty 대응 비교 모두 GPU가 더 빠르고 AP 온도 상승도 더 낮았으며, 모든 GPU run은 31/31 노드 full delegation과 fallback 없음이 확인됐다. `gpu_compatibility_list_supported=false`, `formal_gpu_compat_list_override=true`를 결과에 반드시 공시한다.
- 남은 제한: A24 위치 변경, 실제 FP32/FP16 하드웨어 실행 여부 unknown, 미검증 에너지 단위, GPU 내부 H2D/GPU/D2H·fence timing 부재, S26 dataset manifest 문구 수정 필요, 설치 APK와 Git 소스의 완전한 cryptographic binding 부족, S26 재시도 raw run 하나의 불완전한 failure 기록.
- 영향: PROJECT_PLAN 개정 3, PROJECT_STATUS의 DEFINE-01 완료 및 CALIB-01 전환. production 코드·테스트·실험 데이터는 변경하지 않는다.

## 2026-09-15 — CALIB-01A 종단간 calibration 설계

- 상태: 채택 — 측정 실행 전 구현·검증해야 할 calibration protocol로 사용한다. 절대 마감시간 값은 여전히 `calibration_pending`이다.
- 코드 감사: 현재 production에는 run 단위 CPU/GPU 선택과 tensor-only Interpreter 초기화·run, telemetry/provenance는 있지만 photo picker, 실제 이미지 I/O·전처리, 긴급·일반 큐, 사용자 후처리/output-ready와 분류 결과 영구 저장 경로는 없다.
- 결정: 기존 tensor benchmark를 종단간 calibration으로 사용하지 않고 CALIB-01B에서 누락 경로를 실제 production 흐름에 연결한 뒤 측정한다.
- 시계·상태: 모든 device timestamp는 `SystemClock.elapsedRealtimeNanos()`를 사용하고 성공·실패·거절·만료를 전체 도착 분모에 남긴다.
- pilot: 기기·backend별 독립 session 5개로 시작하고 사전 변동성 기준을 만족하지 못하면 2개씩 최대 9개까지 확장한다. 9개에서도 불안정하면 deadline을 고정하지 않는다.
- deadline: 기기별 fastest validated warm backend를 reference로 삼고 일반 이미지 한 건의 비선점 완료와 긴급 처리 비용에서 urgent deadline을, 긴급 3건 burst 허용에서 normal deadline을 사전 공식으로 계산한다. 정책 평가 후 변경하지 않는다.
- workload: reference warm 일반 처리능력에 대한 0.4/0.9 utilization과 0.6 일반 + 3건 urgent burst 조건을 기기별로 생성하며 동일 기기 정책 간 arrival trace를 고정한다. 실제 사용자 로그가 없는 synthetic 조건임을 공시한다.
- 영향: `docs/CALIBRATION_PROTOCOL.md`, PROJECT_PLAN의 CALIB-01A/01B 연결, PROJECT_STATUS의 다음 작업 CALIB-01B. production 코드·테스트·실기기와 기존 자료는 이 단계에서 변경하지 않는다.

## 2026-09-16 — CALIB-01B 모듈 경계와 영구 저장 완료 의미

- 상태: 채택 — CALIB-01A의 후보를 현재 production 소유권에 맞춰 최소 구현함.
- 결정: 실제 이미지 calibration production 경로는 모델 asset, LiteRT, GPU delegate를 소유한 `benchmark-runner`에 둔다. telemetry-only app의 기존 사용자 `MainActivity`와 formal/diagnostic v1/v2 경로는 변경하지 않는다.
- 영구 저장 완료: app-private external-files session의 임시 파일에 write/flush하고 `FileDescriptor.sync()`한 뒤 동일 디렉터리 최종 파일로 atomic rename하고 byte-for-byte readback에 성공한 시점이다. 저장장치 controller의 물리 flush 완료는 주장하지 않는다.
- backend: CPU/GPU는 요청 전에 고정한다. backend별 Interpreter를 한 worker에서 재사용하며 GPU 실패를 CPU로 조용히 대체하지 않는다. Java API로 GPU full delegation을 증명할 수 없으면 `unverified_requires_host_delegate_log`를 기록하고 host 증거 전에는 해당 GPU cell을 정식 결과로 승인하지 않는다.
- artifact: `calibration-v1`/schema 1을 기존 v1/v2와 분리하고 canonical session/request UUID, 고정 경로, exact artifact set, byte count와 SHA-256을 production/host 양쪽에서 fail-closed 검증한다.
- 영향: benchmark-runner calibration production/test, 별도 host CLI/test, CALIBRATION_PROTOCOL/PLAN/STATUS. 동적 scheduler, mixed arrival generator, ADB 실행은 포함하지 않는다.
- 마감시간: 전체 검증과 A24 pilot 전까지 `calibration_pending`을 유지한다.

## 2026-09-16 — CALIB-01B-FIX2-A24 범위·deadline·thermal·EXIF 계약

- 상태: 채택.
- 직접 실기기 범위: CALIB-01C와 최종 스케줄러의 새 실기기 검증은 Galaxy A24만 수행한다. S26 formal 80슬롯은 기기별 CPU/GPU 특성 차이의 보조 자료로 유지하며 S26 end-to-end calibration·스케줄러 검증을 주장하지 않는다.
- GPU: strict `CompatibilityList` gate와 silent CPU fallback 금지를 유지한다. S26 compatibility override나 기기 모델 우회는 구현하지 않는다. A24 GPU 진입 가능 여부는 후속 smoke에서 확인한다.
- 완료와 deadline: output-ready 또는 durable persistence가 완료되면 늦었더라도 `terminal_status=succeeded`다. `deadline_outcome`은 `not_set`, `on_time`, `late`, `not_completed`로 분리한다. `expired`는 deadline 때문에 실제 완료되지 못한 요청에만 사용하며 failed/rejected/expired에는 결과 artifact가 없어야 한다.
- 집계: 늦은 성공은 전체 완료율에는 포함하고 기한 내 완료율에는 포함하지 않는다. 실패·거절·만료를 전체 도착 분모에서 제외하지 않는다.
- thermal: `baseline_pilot`, `baseline_formal`, `thermal_stress`를 분리한다. baseline 시작 thermal status는 0/1만 허용하고 formal은 사전 고정 temperature/stability policy와 hash를 요구한다. stress는 baseline에 합치지 않는다.
- 관측 경계: 앱은 battery temperature와 Android thermal status의 monotonic 원시 시계열을 기록한다. AP/PA/SKIN은 앱에서 측정했다고 주장하지 않으며 A24 baseline 전에 host logger의 시계열·cooling/stability gate와 calibration session 자동 연결이 필요하다.
- 입력: minSdk 24의 Android framework `ExifInterface`로 orientation 1~8을 적용한 뒤 versioned Android preprocessing 계약을 실행한다. 자체 EXIF parser는 만들지 않는다. Pillow host 검증과 Android preprocessing이 byte-identical하다고 주장하지 않는다. input bundle은 실제 파일 크기·SHA-256·magic MIME·크기·EXIF·label/APK 및 exact file set을 fail-closed 검증한다.

## 2026-09-17 — CALIB-01B-FIX3 EXIF/decode/Matrix 수정

- 상태: 채택. FIX2의 framework EXIF/preprocessing-v2 선택을 대체한다.
- 근거: EXIF 없는 정상 PNG의 합성 orientation 0, Robolectric decode RuntimeException, transformed bitmap backing 부재가 재현됐다는 사용자 확인.
- 결정: AndroidX ExifInterface 1.4.2를 사용한다. 원본 byte offset이 있는 명시 orientation은 1~8만 허용하고 태그 부재는 normal(1)로 처리한다. 명시 0/9 등은 거부한다. 자체 EXIF parser를 추가하지 않는다.
- 전처리 계약: `android-mobilenet-v1-image-v3`, canonical SHA-256 `03e507dea1d4111681b6c1120fab7729967a19e49712ccc05d2e72e4f7762cf5`. host CLI와 Android를 함께 갱신하며 Pillow byte-identical 주장은 하지 않는다.
- decode: RuntimeException만 cause 보존 IllegalArgumentException으로 변환한다. Error/OOM은 잡지 않는다.
- 검증: production Matrix 좌표로 1~8/미러 의미를 검사하고 실제 EXIF JPEG reader→decoder를 유지한다. Shadow bitmap의 getPixels에 의존하지 않는다. 테스트 수 3개·기존 inference timer·v1/v2·artifact/provenance·A24-only 범위는 유지한다.

## 2026-09-17 — 대회 목표에 맞춘 두 작업·강한 비교 중심 계획 개정

- 상태: 채택 — 사용자의 “우리의 계획을 수상 가능성을 높여서 더 나은 방향으로 발전” 요청에 따른 계획 개정. 코드/실기기 완료 또는 수상 가능성의 정량 입증이 아니다.
- 유지: A24-only, 단일 앱 수준 제어, 비선점, 전체 도착 분모, 품질·일반 서비스·열/메모리 제약, 기존 80슬롯/v1/v2/calibration-v1 보존. NPU·강화학습은 선택적 확장이다.
- 변경: 단일 분류 모델의 긴급/일반 시나리오에서 서로 다른 두 실제 AI 작업으로 주평가를 확장한다. 초기 직렬 경로 이후 실측으로 검증된 조합만 최대 두 건 병행한다. 09-15 초기 범위/DEFINE-01의 단일 모델 한정은 새 주평가에 대해 대체하며 기존 구현 계약에는 소급하지 않는다.
- 우선 검증할 사용 가설: 오프라인 사진 정리 중 백그라운드 분류·색인과 선택 사진의 대화형 객체탐지. 현장 수요·최종 모델 선정은 SCOPE-02/MODEL-02에서 검증한다. 통역/OCR/게임은 구현 사실이나 필수 범위가 아니다.
- 모델 후보: 분류 EfficientNet-Lite0 FLOAT32, 탐지 EfficientDet-Lite0 FLOAT32(부적합 시 SSD MobileNetV2 FLOAT32 검토). 최신성 대신 출처/labels/license·A24 호환성·품질·메모리·측정 가능성으로 선택한다. 후보는 배포 파일을 검증하기 전 승인 모델이 아니다.
- 기존 MobileNet V1과 1001행 라벨 미확인 문제를 보존한다. CALIB-01B PASS는 유지, CALIB-01C-INPUT은 legacy 입력 준비로 보류/재계획한다. 라벨을 임의 생성하거나 새 모델 라벨을 기존 출력에 붙이지 않는다. 새 모델도 독립적인 label provenance gate를 통과해야 한다.
- 비교: 개정 4의 B2는 task별 고정 배정·직렬/허용 병행·단순 열 대응 중 개발자료로 고른 강한 정책이다. B3(단독 프로파일 기반 EDF/earliest-finish)를 추가한다. P는 실측 간섭과 준비 비용으로 시작/대기·경로를 결정한다. 구 B2 결과는 개정 없이 재사용하지 않는다.
- 지표: 새 주평가는 예정 도착→완료, enqueue→완료도 병기한다. 긴급 기한 내 서비스율과 조건부 P95, 일반 기한 내 완료율/aging·backlog를 함께 보고한다. 일반 하한·허용차·실질 개선 수치는 evaluation 전에 freeze한다.
- 열: 스로틀링 유도는 필수조건이 아니다. 새 실험의 기본 안전/비교 조건은 검증 가능한 system thermal/battery·cooling policy로 집행하고 AP/PA/SKIN은 가능한 진단 자료로 결합한다. 구 calibration-v1의 AP/PA/SKIN 외부 gate를 완료 처리하거나 삭제하지 않는다. 센서 부재는 기록하며 열 인과·에너지 절감 주장을 제한한다.
- 프로토콜: 기존 image-v3와 schema 2 유지. `multitask-v1`은 새 계획용 예약 ID이며 별도 구현·validator가 필요하다. 기존 CLI에서 새 manifest가 실행된다고 주장하지 않는다.
- 미확정: 구체 모델 파일/hash·runtime, 실제 사용자 deadline, 일반 서비스 하한, 안전 온도/stability 값, 튜닝 예산·최종 반복 수. 상태는 `calibration_pending`/`thresholds_pending`이다.
- 영향: AGENTS, PROJECT_PLAN/STATUS/DECISIONS, CALIBRATION_PROTOCOL의 적용 범위 표시, 신규 MULTITASK_EXPERIMENT_PROTOCOL. production·입력·APK·기존 데이터는 변경하지 않는다.

## 2026-09-17 — 개정 4.1: 사용 사례와 혼합 요청 주평가 분리

- 상태: 채택 — 사용자가 한 사용 상황으로 연구를 한정하지 않는 방향의 수정을 요청했다.
- 연구 범위는 한 앱의 제한된 CPU/GPU를 공유하는 여러 AI 요청의 순서·경로·병행 결정이다. 사진 정리는 대표 시연 후보이며 필수 사용 상황이나 앱 기능으로 고정하지 않는다.
- 두 실제 작업의 초기 후보와 A24-only, 비선점·최대 두 건 병행·기존 데이터/계약 보존은 유지한다. task ID와 요청 등급을 독립시키고 task별 등급 배치 변경을 사전 지정 보조 조건으로 검증한다.
- 주평가는 일반 backlog 중 긴급 burst와 지속 혼합 요청이다. 저부하·동일 등급 경합은 overhead·공정성·적용 범위를 확인하는 보조 조건이며 primary 판정을 대체하지 않는다.
- 실기기 실험은 요청 도착만 합성·재생하고 모델·전후처리·I/O는 실제로 실행한다. 별도 이산사건 시뮬레이션은 실측 서비스·준비·간섭으로 보정하고 독립 실기기 자료에서 검증한 뒤 조건을 탐색한다. 두 방법의 표본·결과·provenance를 분리한다.
- 수동 시연·합성 도착 재생·가상 시뮬레이션을 구분한다. 모델 실행을 sleep으로 대체하거나 미측정 통역/OCR/게임의 성능을 검증했다고 주장하지 않는다. 가상 온도·에너지 효과도 검증된 모형 없이 만들지 않는다.
- 사용 패턴의 현실 근거는 조사하되 특정 사진 앱의 수요 인터뷰를 모든 개발의 선행 조건으로 만들지 않는다. 미확인 패턴은 합성 가정으로 공시한다.
- 현재 작업 SCOPE-02, deadline/thresholds 미확정 상태와 개발→동결→독립 평가 원칙을 유지한다. 이 결정은 새 구현·실측 PASS가 아니다.

## 2026-09-17 — SCOPE-02 근거 경계와 MODEL-02 분리

- 상태: 채택 — [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)에 확인 사실·추론·합성 가정을 분리해 기록하고 다음 작업을 `MODEL-02A`로 전환한다.
- 기존 작업: A24/S26 80슬롯, diagnostic v2, CALIB-01B는 폐기하지 않는다. 자원 우열의 기기 의존성, 측정·provenance, production 측정 경계의 근거로 유지한다. legacy MobileNet 8장/1001행 라벨은 새 두 작업의 필수 입력에서 제외하고 재현 과제로 보류한다.
- workload: W-burst와 W-sustain을 primary, W-low·W-peer·task/priority swap을 supporting으로 유지한다. 실제 사용자 도착 로그가 없으므로 arrival trace는 합성 조건이라고 명시하고 모델·전후처리·I/O는 A24에서 실제 실행한다.
- 작업 후보: EfficientNet-Lite0 FLOAT32와 EfficientDet-Lite0 FLOAT32를 유지한다. 공식 안내와 label 후보 구조만 확인했으며 exact artifact/license/hash·metadata/tensor 결합·A24 지원은 승인하지 않았다. 탐지의 공식 label map은 90 index row 중 10 placeholder로 80 object class를 표현하므로 dense 80행으로 가정하지 않는다.
- 차별성: Band·Sung et al.·Pantheon·CoDL 등 모바일 multi-DNN/이종 실행 연구가 이미 있으므로 최초성을 주장하지 않는다. A24 한 앱의 whole-request 비선점 배정, 서비스 제약, co-run 간섭, 강한 정적·단순 동적 기준정책 대비 재현 실증으로 범위를 좁힌다.
- 중복 조사: 공개 공식 대회 목록과 접근 가능한 프로그램에서 동일 제목은 확인하지 못했으나 최근 3개년 전체 출품작 감사가 아니므로 중복 없음은 미확정이다. 제출 전 `RELATED-02`에서 다시 확인한다.
- MODEL-02 분리: `MODEL-02A`는 host artifact/source/license/tensor/label/golden output, `MODEL-02B`는 승인 bundle의 A24 CPU/GPU·delegation·품질·메모리 smoke다. SCOPE-02 완료는 모델 승인·앱 구현·실기기 PASS나 정책 효과를 뜻하지 않는다.

## 2026-09-17 — MODEL-02A host 판정과 탐지 license gate

- 상태: 부분 대체됨 — host 판정은 유지하고, 무조건 A24 반입 보류는 2026-09-18 조건부 결정으로 대체한다.
- EfficientNet-Lite0 FLOAT32 v1은 공식 version URL, byte count/SHA-256, 내장 1000 labels, `[1,224,224,3] -> [1,1000]`, metadata의 Apache-2.0, deterministic raw CPU output을 확인해 MODEL-02B 후보로 승인한다. 이 승인은 A24/GPU/품질/성능 PASS가 아니다.
- EfficientDet-Lite0 FLOAT32 v1은 공식 source, 90행 sparse labels, raw tensor와 host CPU 실행을 확인했으나 exact binary metadata의 license가 null이다. 안내 문서 footer나 sample source license를 binary license로 대신하지 않는다.
- 사전 지정 대안 SSD MobileNetV2 FLOAT32 v1도 한 번 검사했다. 91행 background 포함 label과 tensor·raw CPU 실행은 확인했지만 license가 동일하게 비어 있어 대안 승인하지 않는다. 후보를 계속 바꾸지 않는다.
- 당시 다음 작업은 `MODEL-02A-LICENSE`였다. exact license 연결은 확보하지 못했지만 decoded golden을 완료했고, 2026-09-18 결정에서 비배포 연구 probe만 조건부 허용했다.
- 모델 binary·golden 산출물은 이번 문서 PR에 넣지 않는다. deadline과 threshold는 계속 pending이며 host latency를 A24 수치로 사용하지 않는다.

## 2026-09-18 — EfficientDet 비배포 연구 평가 조건부 승인

- 상태: 채택 — `MODEL-02A_CONDITIONAL_PASS`. 이전의 무조건 A24 반입 보류를 비배포 연구 probe에 한해 완화한다.
- 확인 사실: Google 공식 Object Detector 안내는 EfficientDet-Lite0 FLOAT32를 권장하고 모델을 내려받아 프로젝트에 저장하도록 안내한다. 공식 Apache-2.0 sample은 exact v1 GCS URL을 직접 사용한다. 동일 exact binary는 source/hash/tensor/label/raw output과 MediaPipe Tasks decoded output이 host에서 결정적으로 확인됐다.
- 미확인: exact GCS binary metadata와 bucket에는 license/NOTICE가 없으며, Apache-2.0인 TensorFlow/Kaggle EfficientDet TFLite variants는 byte·dtype·출력 계약이 달라 exact binary의 라이선스 증거가 아니다. 이 결정은 법률 자문이나 재배포 승인으로 해석하지 않는다.
- 결정: version URL, byte count, SHA-256을 고정한 A24 내부 연구 평가만 허용한다. binary를 Git 저장소·PR·APK·팀 공유 ZIP·제출물에 포함하지 않는다. A24 probe는 외부 다운로드 검증 후 app-private storage로 전달하고 실험 종료 후 cleanup·provenance를 기록한다.
- 배포 gate: 시연 APK나 재현 bundle에 모델을 넣기 전 exact license/NOTICE를 확보한다. 확보하지 못하면 명시적으로 라이선스된 artifact로 교체하고 MODEL-02A/B를 다시 통과한다.
- 다음 작업: `MODEL-02B-PREP`. 외부 manifest와 비번들 A24 CPU/GPU 최소 probe 계약을 먼저 확정한다. host latency는 deadline·simulation service time·A24 성능으로 사용하지 않는다.

## 2026-09-18 — MODEL-02B debug-only 외부 probe 구조

- 상태: 채택 — [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md)의 manifest·staging·비교·cleanup·판정 계약을 구현 기준으로 사용한다.
- 코드 감사: 현재 `ModelLoader`와 calibration runtime은 APK MobileNet asset 및 고정 tensor에 묶여 있어 새 model 파일 복사만으로 재사용할 수 없다. 기존 계약을 일반화한 것처럼 바꾸지 않는다.
- 구현 경계: 새 loader·component·Tasks dependency는 debug source/dependency에 격리하고 release·formal v1·diagnostic v2·calibration-v1에 연결하지 않는다. model/sample bytes는 어느 variant에도 bundle하지 않는다.
- 실행 계층: 두 모델의 raw LiteRT CPU/GPU tensor·수치 검증과 EfficientDet Tasks decoded 검증을 분리한다. Tasks API 전체 시간은 `tasks_detect_ns`이며 내부 inference 시간으로 부르지 않는다.
- GPU 판정: delegate 생성만으로 PASS하지 않는다. full-delegation host evidence, 수치 gate, no-fallback가 모두 있어야 verified GPU cell이다.
- 범위 판정: 두 task CPU와 두 GPU가 모두 통과하면 FULL, 두 CPU와 최소 한 GPU만 통과하면 REDUCED, 그보다 좁거나 dependency/배포 gate를 충족하지 못하면 SCOPE-03로 보낸다.
- 현재 작업: `MODEL-02B-SEAM`. host tests와 dry-run을 통과하기 전 A24 설치·실행을 시작하지 않는다.

## 2026-09-18 — A24 주평가와 추가 Android 기기 무재튜닝 재현

- 상태: 채택 — 사용자의 “다른 핸드폰에도 실측해야 하는 것까지 고려” 지시를 반영한다.
- 기기 역할: A24는 개발·full profile·정책 튜닝·주평가 기기다. A24에서 모델·입력·정책·분석을 동결한 뒤 최소 한 대의 다른 Android 기기에서 같은 runner의 축소 profile과 재현평가를 수행한다. 세 번째 기기는 일정과 접근성이 허용할 때만 추가한다.
- 구현: MODEL-02B seam과 host 도구는 model name/serial별 코드 분기 없이 device manifest와 runtime capability로 동작해야 한다. 추가 기기의 GPU unsupported/unverified는 실패를 숨기지 않고 CPU/queue-only 축소 범위로 남긴다. compatibility override와 silent CPU fallback은 허용하지 않는다.
- 비교: `absolute-SLA`는 같은 millisecond deadline과 byte-identical arrival trace로 실제 사용자 경험 차이를 보고, `capacity-normalized`는 기기별 사전 solo capacity로 부하를 스케일해 정책 구조의 재현성을 본다. 원시 latency를 기기 사이에서 pooling하지 않는다.
- 무재튜닝: P/B3의 알고리즘·hyperparameter·quality/tolerance는 A24에서 고정한다. B2는 사전 정의된 기기별 profile 선택 규칙만 적용한다. 추가 기기 결과를 본 뒤 정책이나 임계값을 바꾸면 외부검증이 아니라 새 개발 버전으로 되돌린다.
- 증거 한계: A24와 추가 기기 한 대의 일치만으로 Android 전체 모집단 일반화를 주장하지 않는다. `device × policy` 차이와 미지원 cell도 결과다. 기존 S26 80슬롯은 동기 자료이며 새 두 작업 재현평가를 대체하지 않는다. S26을 쓰려면 새 계약으로 다시 실행한다.
- 라이선스: EfficientDet exact binary는 각 승인 기기 실행자가 고정 원 URL에서 직접 확보하고 hash 검증하는 비배포 연구 사용으로만 확장한다. binary를 기기 간 전달하거나 Git·PR·APK·팀 ZIP·제출물에 넣지 않는다.
- 이전 결정 관계: 2026-09-16 CALIB-01B-FIX2의 A24-only는 legacy `calibration-v1`에 그대로 적용한다. 2026-09-17 개정 4/4.1의 새 주평가 A24-only 부분은 `multitask-v1`에 한해 이 결정으로 대체한다.
- 영향: PLAN 개정 4.4, STATUS, MODEL-02 inventory/probe, SCOPE evidence, MULTITASK protocol. 현재 production 구현·실기기 PASS를 뜻하지 않는다.

## 2026-09-19 — 비정상 종료 복구와 probe APK 격리

- 상태: 채택 — 사용자가 feature/pre-simulation-ready-20260919의 미커밋 작업 보존·복구 및 최소 A24 smoke를 명시적으로 요청했다. push/PR/merge는 하지 않는다.
- 결정: 09-18 debug 전용 seam을 opt-in modelProbe variant와 별도 applicationId로 좁힌다. 일반 debug/release와 legacy production 경로를 보존한다. 전용 테스트만 testModelProbe에 둔다.
- 결과 저장 완료와 모델/기기 PASS를 분리한다. manifest schema 1과 legacy v1/v2/calibration은 유지하고, 결과 binding 강화는 artifact_contract_version=2로 명시한다. 과거 artifact는 보존하고 새 계약을 소급 적용해 수정하지 않는다.
- 미커밋 sample 교체는 bytes/source 확인만 완료했다. 새 sample에 기존 golden·정확도 판정을 전용하지 않는다. 새 decoded golden과 raw CPU/GPU 수치 gate는 미완료다.
- SIM-01 준비는 MODEL-02B 및 TASK-02/PROFILE-02의 실제 완료 경계를 충족해야 한다. probe 호출시간을 사용자 요청 service distribution으로 승격하지 않는다. deadline/threshold/repetition pending은 그대로 유지한다.

## 2026-09-20 — GPU 진행 증거·raw 수치와 실제 task 승인 분리

- 상태: 채택 — 사용자의 GPU 진단부터 SIM-01 준비까지 자율 진행 지시를 반영했다. 본 simulation·formal·push/merge는 실행하지 않았다.
- 결정: 기존 8-file probe와 공식 timer를 유지하고 UUID/manifest/monotonic 순서에 묶인 별도 durable progress와 raw f32 sidecar를 사용한다. cleanup 실패는 진단 저장 오류와 구분한다. 세부 실패를 성공으로 바꾸지 않는다.
- 증거: 첫 GPU 진단과 raw 12세션이 120초 이내 완료됐고 두 task×CPU/GPU는 seed 0/1/2의 raw 수치 gate를 통과했다. 이전 timeout의 exact phase는 미확정이다. 새 성공으로 과거 원인이 수정됐다고 선언하지 않는다.
- 제한: Tasks decoded GPU는 완료했지만 Android CPU와 고정 label/box/score gate가 실패했고 actual delegate 이름은 unknown이다. host 새 golden과 Android CPU도 한 score 기준이 실패했다. raw full GPU 증거를 Tasks wrapper에 전용하지 않는다.
- 다음 판단: 탐지 GPU를 현재의 실제 task/profile 후보에서 제외한다. 탐지 CPU와 분류 GPU 조합은 과학적으로 가능한 축소 후보이나 탐지 CPU golden/품질·adapter 검증 전에는 REDUCED_PASS로 채택하지 않는다. tolerance 완화·CPU fallback·모델 교체는 결정하지 않았다.
- 준비 범위: 별도 draft simulation schema·validator·seed·no-op·정책 인터페이스·host KPI 계약을 구현하되 TASK-02 production 완성이나 PROFILE-02 실측으로 표시하지 않는다. 실제 service/transition/co-run·품질 입력·holdout·deadline/반복은 열린 gate다.
- 근거: `C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/device_evidence_summary.json`, `decoded_comparison.json`, [SIM_01_PREPARATION.md](SIM_01_PREPARATION.md).

## 2026-09-20 — 명시적 image task 계약과 증거 경계

- 상태: 채택 — 사용자의 decoded 원인 조사·adapter 구현·bounded 실측 승인 범위.
- 결정: 같은 원본의 RGB PNG와 Q16 resize를 입력 계약으로 고정하고 `explicit-image-task-v1`에서 LiteRT raw 출력과 metadata 기반 decoder를 직접 연결한다. 기존 모델 ID와 기존 Tasks artifact는 유지하며 새 task-profile-v1 결과를 별도 root에 저장한다.
- 근거: host/A24 CPU JPEG decode 차이를 같은 RGB ablation으로 확인했다. 같은 tensor에서는 CPU/GPU raw 및 decoded가 기존 tolerance를 통과했다. Tasks GPU는 추가 2회 timeout으로 실제 task/profile 후보에서 제외한다. [상세 근거](DECODE_RESOLUTION_20260920.md).
- 모델: exact float32 license/NOTICE는 아직 미확인이다. 기존 실행자 직접 확보·비배포 연구 probe 한정으로 유지한다. 확보한 공식 uint8 대안은 다른 모델이며 결과를 섞거나 교체 완료로 기록하지 않는다. 배포 전 라이선스 입증/교체 gate를 유지한다.
- 품질: Open Images 공식 주석 20장으로 실제 탐지 품질을 관측하되 host equivalence와 분리한다. 낮은/불확실한 품질 관측을 감추거나 gate 통과를 위해 threshold/tolerance를 바꾸지 않는다.
- 준비: B0/B1 순수 결정 함수를 추가한다. 고정 mapping·aging 값은 caller가 명시해야 하며 아직 평가용 동결값은 없다. 호출 테스트는 simulation·정책 비교가 아니다. 절대 deadline과 holdout 오차 허용값은 pending을 유지한다.

## 2026-09-20 — 색상 canonical 계약과 외부 연결 장애

- 상태: 채택(구현/host 검증), 기기 최종 검증 보류.
- 근거: 실제 10-image 실행의 한 PNG에서 iCCP에 따른 input tensor 차이가 확인됐다. host ICC→sRGB 변환 후 metadata 없는 RGB PNG를 고정한다. 모델/resize/decoder threshold/tolerance는 유지한다.
- 최종 버전: canonical-srgb-q16-stretch-v2, explicit-image-task-v2, task-profile-v3. 기존 입력과 v1/v2 결과는 보존한다. 요청 journal과 bounded Activity 가시성을 보강했다.
- 제한: 최종 APK 전송 중 A24 offline. 네 cell은 최종 계약에서 unverified이며 기존 raw 성공을 task 승인으로 전용하지 않는다. 본 simulation·formal은 미실행.
- 판정: BLOCKED_EXTERNAL_INPUT. STATUS와 외부 FINAL_REPORT에 재연결·정리 대상 UUID·최종 APK hash를 기록한다. 임의 deadline·품질 하한·holdout 오차를 채우지 않는다.

## 2026-09-20 — A24 최종 색상 계약 네 cell 검증

- 상태: 채택 — 사용자 재연결·bounded 최종 검증 지시. 최신 APK 원격 hash 확인 후 새 UUID 8 session을 실행했다.
- 결정: explicit-image-task-v2의 classification/detection CPU/GPU 네 cell을 20-image backend equivalence 범위에서 PASS_EQ로 인정한다. 기존 Tasks 실패에 따른 GPU 제외를 새 명시적 adapter에 적용하지 않는다. 품질 승인 또는 formal 안정성으로 확대하지 않는다.
- 근거: [재개 검증](A24_RESUME_20260920.md). host와 같은 tensor, decoded 및 CPU↔GPU 직접 비교 40쌍 통과. session/PID full GPU 확인. tolerance/fallback 변경 없음.
- 추가 수정: 이전 외부 분류 golden의 manifest/파일 경로 혼용을 검출했다. 실제 bytes/hash 결합 generator와 회귀 테스트를 추가하고 잘못된 golden/실패 판정을 보존했다.
- 다음: 통과 cell의 bounded solo/transition/co-run/holdout을 관측한다. deadline·품질·안정성·오차 수용값은 근거 없이 동결하지 않는다.

## 2026-09-20 — bounded profile 관측과 SIM-01 동결 보류

- 상태: 채택 — 사용자의 본 simulation/formal 제외 및 시뮬레이션 직전 준비 지시.
- 결정: 네 cell을 실제 지원하는 것으로 유지하되, 현재 두 작업 모두 solo CPU가 빠르다는 관측을 받아들인다. heterogeneous 배정 이득을 전제하거나 GPU를 유리하게 보이도록 기준을 바꾸지 않는다.
- 근거: 새31개 실기기 session, bounded solo/전환/두 co-run/별도 holdout, thermal/PSS·모든 requested/actual backend 검증. [상세 결과](A24_RESUME_20260920.md).
- 제한: 분류 CPU의 첫 non-cold 요청381ms와 warm 예측 오차74.57%를 보존한다. 추가 warmup 진단은 초기 호출 상태 영향의 근거지만 기존 holdout을 대체하는 confirmatory 결과가 아니다. cold boolean만으로 안정적인 warm service를 가정하지 않는다.
- 판정: SIM-01_INCOMPLETE. 측정값과 준비 입력을 provenance로 연결하고 no-op만 실행한다. 품질 수용·초기 호출 서비스 모델·안정성·holdout 오차·공통 제약/반복/평가 freeze 없이 READY나 절대 deadline을 만들지 않는다.
- 연결 복구 시 완료 artifact 회수는 재실행과 구분한다. host 명령 실패를 보존하고 device monotonic 실행 bound·hash·decoded·delegate를 검증한 경우에만 완료로 인정한다.

## 2026-09-20 — SERVICE-MODEL-FREEZE의 독립성·품질 보존 계약

- 상태: 채택 — 사용자의 기존233요청/31 session 분석·6후보 비교·누수 방지·no-op 지시.
- 결정: 이미 결과를 확인한4개 holdout과 사후1개 진단은 retrospective로만 유지한다. calibration24개 LOSO로 선택한 초기 상태 분리 모델은 임시 후보이며, 포함률82.52%<90% 및 untouched holdout 부재로 동결하지 않는다. 과거74.57% 오차를 제거하거나 새로운 진단으로 덮어쓰지 않는다.
- 근거: [SERVICE-MODEL-FREEZE](SERVICE_MODEL_FREEZE_20260920.md), 외부 최종 bundle의 split/acceptance/model comparison/source hash closure. 새 기준은 calibration 변동성으로 산출한 prospective engineering 기준이며 과거 holdout을 사전 승인으로 소급하지 않는다.
- 품질: numerical/decoded 동등성과 실제 task accuracy를 분리한다. 정확도를 임의 생성하지 않고 검증 cell·동일 모델/입력/전처리/decoder·기존 허용오차를 정책 공통 quality-preservation 제약으로 사용한다. 이는 모델 배포 라이선스 승인이나 실제 정확도 개선 주장이 아니다.
- 공통 경계: fallback 금지·thermal0·serial만 준비 승인, co-run/메모리 limit·deadline은 독립 검증 전 pending. GPU는 solo에서 느리지만 CPU-only 직렬 대조가 없으므로 모든 조건에서 지배당한다고 단정하거나 제외하지 않는다.
- 상태: SIM-01_INCOMPLETE 유지. 작은 추가 calibration과 새 holdout/control 설계를 명시했으며 본 simulation/formal을 실행하지 않았다. 기존 정책 ID·증거 의미는 변경하지 않는다.

## 2026-09-20 — FINAL-CALIB 사전 동결

- 상태: 채택 — 사용자 승인 A4 calibration/B16 독립 holdout/C2 CPU-only bounded 대조. 본 simulation/formal 금지 유지.
- calibration24+신규4만으로 전환을 cold와 분리한 `transition_mean`을 독립 평가 후보로 고정했다. 기존 PI Q05..Q95, coverage90%, MAE432.808616ms/WAPE43.191436% 기준을 완화하지 않았다. calibration coverage80.65% 미달도 보존한다. 후보 고정은 SIM-01 승인과 다르다.
- 2026-09-20T13:11:32.713690Z 고정 hash는 [receipt](SERVICE_MODEL_FINAL_FREEZE_20260920.json), 원자료/상세는 `C:/Users/LG/Documents/D1Check_Service_Model_Final/run_20260920T130139Z`. B16은 이 시각/commit 이후 새 UUID로 실행하고 모델을 read-only 평가한다.
- 첫 host 종료기록 변수 오류 시도는 진단 원자료로 보존하고 새 UUID로 대체했다. CPU-only 직렬 대조는 기존 단일-worker runtime 교체 비용이 포함돼 warm 두 모델 상주 대조가 아니다. sampled memory/미확정 deadline을 임의 승인하지 않는다.

## 2026-09-20 — FINAL-CALIB 독립 holdout 실패 보존

- 상태: 확정 — A4/B16/C2 실행과 동결 모델 read-only 평가 완료. Holdout coverage80.384615%<90%, 상태/분포 기준 실패로 SIM-01_INCOMPLETE다. 전체 MAE39.07ms/WAPE6.10%만으로 승인하지 않는다.
- 근거: [최종 calibration](SERVICE_MODEL_FINAL_CALIB_20260920.md), 외부 frozen contract/260개 request 예측/16개 session 평가/두 CPU 대조 및 memory·thermal 원자료.
- 모델·PI·기준을 holdout 이후 변경하지 않는다. Cold직후와 전환직후 pooling 실패는 새 버전의 calibration 설계 근거로만 사용하며 이번16개를 독립 holdout으로 재사용하지 않는다.
- CPU/GPU co-run의 긴급 응답 개선 관측은 CPU직렬 runtime 재생성과2개 warm runtime 유지의 비대칭을 포함한 n2 진단이다. GPU 자체의 우월성·전체 완료율 개선을 주장하지 않는다. Memory admission 미검증·deadline pending도 유지한다.
- Host 실패2건을 보존했다. 첫 시도는 새UUID로 대체, 다른 한 건은 이미 완료된 기기 artifact 전송만 복구했으며 Activity 재실행·실패상태 수정 없음. 본 simulation/formal·push/merge/rebase 없음.

### 2026-09-20 — SERVICE-MODEL-V2 개발 재설계와 telemetry blocker

- 상태: 채택(개발 설계); 서비스 모델 승인/실기기 실행은 아님.
- 사용자 SERVICE-MODEL-V2-DESIGN 지시에 따라 기존 calibration 및 consumed holdout 모두 개발 근거로 전환한다. 기존 실패·74.57%오차·cold774.244ms를 보존하며 새 독립 holdout으로 재사용하지 않는다.
- C setup/active 분리+E joint session empirical를 최소 구조로 선택하고, origin/cell/co-run/완료경계를 유지한다. D full sequence matrix·G pooled multiplier는 추가 복잡도/오차 근거상 선택하지 않는다. F session-conformal은90%를 유지하되 exchangeability/유한표본 한계와 분포 목적을 분리한다.
- warm3회차 자동 승인 금지. lifecycle/worker-release·MemoryInfo·두 resident CPU runtime 직렬 대조가 없어 BLOCKED_MISSING_TELEMETRY다. Android 변경/새 ADB/본 simulation/formal은 이번에 수행하지 않는다.
- [V2 설계](SERVICE_MODEL_V2_DESIGN.md)의 sample-size 계산은 계획 bound이며 수천세션 실행 승인이 아니다. 목표 precision/분포margin·공정한 paired variance가 미확정이므로 새 calibration 이후, 새 holdout 이전에 정확 프로토콜을 동결한다.
- 이전 transition_mean frozen artifact/hash/평가기 코드는 수정하지 않는다. V2 host 도구는 새 파일로 분리한다.

### 2026-09-21 — Telemetry v4와 resident control의 별도 실행경로

- 상태: 구현·host 검증 완료, **BLOCKED_DEVICE_CONNECTION**. 사용자는 새 calibration/holdout/formal/simulation을 금지하고 최소4개 lifecycle/resident smoke만 승인했다. ADB devices와mDNS 모두비어 설치/Activity/smoke는0회이며 READY_FOR_CALIBRATION을선언하지않는다.
- task-profile-v4/schema1을 modelProbe 전용 Activity/adapter로 분리해 기존 v3/공식 timer/decoder/legacy artifact를 보존한다. 캡처한 invocation timestamp를 호출 종료 후 기록하고 내부 logger 시간을 inference에 넣지 않는다.
- 두 CPU runtime을 같은 lane에 상주시켜 serial control의 runtime 재생성 혼입을 제거한다. Co-run도 같은 사전생성/warmup 원칙을 사용한다. Paired 비교는 같은 workload hash와 두 성공 receipt가 필요하다.
- 고정 headroom 대신 android-low-memory-resident-v1의 system threshold+관측 PSS reserve를 적용한다. sampled peak나 baseline guard를 실제 최대/안전보장으로 주장하지 않는다. [세부 계약](TELEMETRY_V4_GATE.md).
- v4 warm label은 ordinal이고 qualified=false다. 이번 smoke는 서비스모델 calibration/holdout으로 승격하지 않는다. 기존 consumed registry와 PI 실패를 유지한다.

### 2026-09-21 — Telemetry v4 실기기 smoke gate 통과

- 상태: 채택. 사용자의 연결 복구 후 smoke 재개 지시 범위에서만 실행했다.
- 근거: `C:/Users/LG/Documents/D1Check_Telemetry_V4/resume_20260920T160724Z/FINAL_REPORT.md`, smoke_ledger/post_validation/paired_smoke_contract. 새4세션18요청, schema/semantic validator·출력 동등성·memory admission·runtime/worker release 모두 PASS. 기존 소스/APK/원자료 불변.
- 결정: TELEMETRY_V4_READY_FOR_CALIBRATION. 서비스모델 승인이나 GPU 우월성 증거로 승격하지 않는다. Ordinal warm은 qualified=false, deadline pending, 기존 holdout consumed 유지.
- 다음: 별도 승인된 calibration 계획 동결. 이번 단계에서는 추가 calibration/holdout/simulation/formal 없음. 이전 BLOCKED_DEVICE_CONNECTION은 이번 gate에 한해 해소됐다.

### 2026-09-21 — Prediction gate에서 joint empirical 입력 검증으로 protocol amendment

- 상태: 새 방법 채택, 실행 계획은 INCOMPLETE. 사용자 EMPIRICAL-CALIBRATION-PLAN 지시를 따른다.
- PI를 scheduler가 사용하지 않으므로 새 protocol의 request PI90% 필수 gate를 제거한다. 이는 운영 성과 비교 목적과 입력 모델의 정렬이며 기존 threshold 사후 완화가 아니다. transition_mean80.38% 실패와 이전 hash/원자료는 불변이다.
- 기존52 profile 및 smoke4는 consumed development, 승인 입력은 신규 v4 자료에 한정한다. setup/active/memory/thermal/interference는 session block으로 결합하고 임의 field 재조합을 거부한다.
- [계약](EMPIRICAL_CALIBRATION_PROTOCOL.md)에 최소160/권장280 탐색세션·사전 criteria·deadline 계산 규칙을 고정했다. n8로 cold P95 정밀도를 보장하지 않으며 fair paired variance도 없다. 같은-session 전환경로가 현재 APK에 없으므로 전체 계획의 A24 실행 명령을 발행하지 않는다.
- 이번 ADB·실측·calibration·holdout·simulation/formal 없음. Android/APK 불변. 최신 외부 증거는 C:/Users/LG/Documents/D1Check_Empirical_Calibration_Plan/plan_20260921_v1/FINAL_REPORT.md.

### 2026-09-21 — 최대30세션 descriptive resident-only protocol 채택

- 상태: 계획채택, 측정미실행. 사용자 BOUNDED-EMPIRICAL-PLAN의고정수량·제한된주장을우선한다. 160/280계획은실행하지않고이전동결artifact/실패결과를보존한다.
- A24/현분류탐지/thermal0/v4의관측경험분포로정책상대비교한다. dynamic unload/reload transition과cold populationP95 precision은simulation v1필수gate에서제외한다. Setup/queue/dispatch는남긴다.
- 정확30=solo4×5+resident5pair×2. device retry0/대체0/총시작≤30; 실패시자료보존·중단·incomplete. 독립holdout없이completeness/quality/safety·sessionbootstrap/LOSO·wholeblock sensitivity/CRN을사용한다. 통계적보편우월성주장금지.
- [계약](BOUNDED_EMPIRICAL_PROTOCOL.md), 외부 `C:/Users/LG/Documents/D1Check_Bounded_Empirical_Plan/plan_20260921_v1/FINAL_REPORT.md`. 다음실행명령을제공하되이번에는ADB/측정/simulation/formal을호출하지않았다. Deadline pending·SIM-01_INCOMPLETE유지.

### 2026-09-21 — 30세션 descriptive empirical 입력 동결

- 상태: SIM-01_READY(현재사용자기준의resident-only/A24/thermal0/관측입력범위). 본simulation/formal은실행하지않음.
- 정확30/480 completed, 추가/retry/대체/실패0. Nativemanifest·순서·seed·480호출·criterion·memory/thermal·deadline공식은동결계획과동일하다. Atomic fsync/rename journal·exclusivehostlock·completed 재실행금지·완전artifact만복구하는별도관리계층을추가했다.
- Joint input SHA `4eeae6f6f8e9954d153b010767ba5a84307e5b8d0a971e7a478b0255413c0fc5`, `C:/Users/LG/Documents/D1Check_Bounded_Empirical_Run/run_20260921_atomic_v1/FINAL_REPORT.md`.
- 5pair의GPUcorun은urgentP95 개선과makespan/throughput 악화가동시에관측됐다. 5쌍bootstrap·wholeblock sensitivity로방향과불확실성만보고하고보편우월성/인과일반화는주장하지않는다.
- 기존coverage80.38%예측실패/consumedholdout/51session559요청/v4smoke/formal80원본은보존한다. 새READY는이전prediction모델의PASS전환이아니며coldP95/요청90%예측/다기기·다른thermal보장이아니다.
- 다음은동일input/CRN/복수deadline을쓰는별도승인simulation단계이며새실기기재실행은없다.

### 2026-09-22 — PC 계획의 입력 READY와 정책 READY 분리

- 상태: 채택 — 사용자의 동결 A24 입력만 사용하는 PC 계획 확정 요청. 본 simulation·추가 실기기 금지.
- 결정: 연구 질문·calibration 역할·선행연구와 비신규성을 [PC 계약](SIMULATION_PROTOCOL.md)과 [문헌 비교](RELATED_WORK_GAP.md)에 명시한다. 새 SP1 policy namespace, epsilon-constraint/lexicographic 구조, seed2026092201 및 부분 계약 hash를 사용한다. 기존 정책/telemetry/원본 의미를 바꾸지 않는다.
- 확인: 고정 offset0·분류 urgent6/탐지 normal6 co-run과 CPU 교대 serial만 측정돼 있다. 요청 순서와 overlap을 바꾸는 서비스 모형이 없는데 전체block resampling만으로 동적 정책 성능을 계산할 수 있다고 가정하지 않는다.
- 판정: SIMULATION_PLAN_INCOMPLETE. adaptive estimator·합법 action, 서비스 모형 지원, 실질효과/일반 허용 손실, workload·replication/drain, simulator version/hash는 null로 보존한다. 과거10%/2%p를 승인값으로 승격하지 않는다. 기존 SIM-01_READY는 입력 준비 판정으로 유효하다.
- 동결: 계획/schema/validator·원본 hash/consumed registry·no-op과 문서. validator PASS는 연구 READY가 아니다. 새 원자료·새 simulation 결과 생성 없이 별도 외부 root에 저장한다.
- 다음: SIM-PLAN-02-SUPPORT-DECISION에서 반사실적 모형의 가정과 기존 외삽 금지의 관계를 결정한다. 가정 미합의 시 고정 trace 기술 분석으로 연구 질문을 명시적으로 축소하는 대안을 제시하며 임의 변경하지 않는다.

### 2026-09-22 — 사용자 승인 support-constrained 모델 채택

- 상태: 채택. 최신 사용자 지시의 warm 교환가능성·허용 action·Pareto·epsilon 제한을 반영한다. 새 실측과 본 simulation은 금지한다.
- 결정: A24 thermal0/resident/non-preemptive, 같은 task/backend/state joint tuple의 제한 가정으로 CPU urgent 재배열을 허용한다. 전체 paired co-run 외의 overlap/transition은 OUT_OF_SUPPORT. 기존 empirical/v4 계약을 수정하지 않고 새 simulator namespace에서 가정과 관측을 분리한다.
- 최소 설계: 고정12요청/54budget/5pair 전수/seed2026092202. conditional MC 오차0이므로 임의 복제 수를 도입하지 않는다. 모집단 오차는 남으며 exact bootstrap3125·wholepair rank sensitivity·5LOSO deletion으로 기술한다.
- 정책·평가: FIFO/urgent/static/always-corun/adaptive, STATIC은 FIFO alias. adaptive는 시작 전 기대값의 epsilon 제약 후 miss/P95/makespan 사전식 선택, epsilon0 primary와0.5/1 sensitivity. 주 결과 Pareto, 보편승자·실질가치 threshold 없음. 상세 알고리즘과 적용 한계는 SUPPORT_SIMULATION_PROTOCOL.md에 고정한다.
- 대체: 이전 SIM-PLAN-01의 필수 null은 이 축소 계약에서 해결한다. 과거 부분 계획·hash·실패 모델은 보존한다. absolute user SLA calibration_pending은 복수 budget과 구분한다. 현재 교환가능성은 검증된 사실이 아니다.
- 다음: 검증 후 checkpoint, 별도 실행 승인 전에는 본 simulation/기기 작업0. 실행 후 선택 정책의 소규모 A24 확인은 후속 단계다.

### 2026-09-23 — 동결 시뮬레이션과 분리된 비동시 도착 확장

- 상태: 채택. 2026-09-23 사용자가 정확19세션·평가130·warmup152·총시도≤19·retry0 개발 pilot 예산을 승인했다. 실행 전 A24 연결 부재로 설치·실측0에서 중단했으며 연결 복구 시 같은 frozen plan으로 재개한다.
- 사용자 지시: A24의 검증된 분류/탐지·resident·non-preemptive를 재사용하고 완료 독립 도착, CPU FIFO/긴급 우선/조건부 CPU-GPU를 같은 workload로 비교한다. 기존 동결·원본·실패 기록을 보존한다.
- 결정: `ARRIVAL-EXT-01`/`arrival-scheduler-v1` 별도 Activity·manifest·출력 root. 네 runtime을 전 정책에 상주시켜 시작 조건을 맞추고 CPU thread1·동시2로 제한한다. 19세션/130평가요청·retry0 개발 계획과 100ms 도착 지연·120초 drain·thermal0/paired 시작온도 1°C 조건은 [확장 계약](ARRIVAL_SCHEDULING_EXTENSION_20260923.md)에 기록한다.
- 이유·근거: 기존 offset0 12요청 제한 시뮬레이션에는 staggered arrival의 실제 정책 순위/paired 효과 검증이 없다. 새 결과를 기존 동결 결과로 소급 해석하지 않는다. 네 runtime memory admission·실제 GPU delegation과 성능 이득은 아직 실기기 미검증이다.
- 미확정: UX SLA, 최소 의미 효과·일반 허용손실·독립 평가 최대 예산. 개발 결과를 본 뒤 과거 10%/2%p 참고값을 자동 승인값으로 만들지 않는다.
- 영향을 받는 범위: 새 modelProbe Activity·host 계획/실행/분석 도구와 PLAN/STATUS. formal v1/v2, task-profile-v3/v4, support-constrained freeze, 과거 APK/원본은 변경하지 않는다.

### 2026-09-23 — ARRIVAL-EXT-01 개발 pilot 완료와 독립 평가 제안

- 상태: **pilot 증거 채택 / 독립 평가 제안 미승인**.
- 실행: 고정 SHA plan/APK로 A24 19/19세션·평가130·warmup152, 총시도19/retry0. 오류·실패·거절·만료·미완료·늦은 성공0, arrival/thermal/paired온도/memory/GPU delegation/cleanup gate 통과.
- 관측: 주 3 paired block에서 `CPU_URGENT−CPU_FIFO` urgent P95 `-1217.5±15.8ms`, normal 평균응답 `+104.1±5.4ms`; `CONDITIONAL−CPU_URGENT` urgent P95 `-11.2±6.7ms`, normal 평균응답 `-630.4±27.9ms`, makespan `-1.245±0.024s`. 개발용 소표본으로 우수성을 선언하지 않는다.
- 제안: 순서 균형 주6블록+보조3블록, 27세션/198평가/216warmup/retry0, 예상65분·예약120분. 종전 참고값인 urgent P95 10% 최소효과, normal 평균응답 10% 손실 및 on-time·완료율 2%p 손실을 결과 전 동결하는 안이다. 2초/8초 deadline은 UX SLA가 아닌 설명 지표로 유지한다.
- 근거: `C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_analysis_v3/FINAL_REPORT.md`; 제안 plan SHA `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`.
- 영향: 기존 formal v1/v2, support-constrained simulation freeze와 과거 원본·APK를 변경하지 않는다. 독립 평가·새 본 시뮬레이션은 별도 승인 전 실행하지 않는다.

### 2026-09-23 — ARRIVAL-EXT-01 독립 평가 완료와 동결 판정 유지

- 상태: 채택. 사용자가 정확27세션·평가198·warmup216·retry/대체/추가0 예산과 사전 gate를 승인했다.
- 실행: plan SHA `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`, 고정 APK SHA `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`, 동일 A24 fingerprint로 27/27세션을 완료했다. 성공198, 실패·거절·만료·미완료·늦은 성공0, retry·대체·추가0이다.
- 결정: `CPU_URGENT−CPU_FIFO`는 urgent 10% 최소효과와 normal 10% 손실 기준을 통과했다. `CONDITIONAL−CPU_URGENT`는 normal 기준을 통과했지만 urgent 상대개선 `-3.48%`, 95% CI `[-5.02%,-1.95%]`로 10% 최소효과를 실패했다. 결과를 본 뒤 threshold를 완화하지 않으며 조건부 정책의 주 결합 판정은 `FAIL`로 유지한다.
- 해석: CPU 긴급 우선 대비 FIFO 차이는 우선순위 효과다. 조건부 정책의 normal 응답·makespan·throughput 개선은 주로 GPU 보조 병행 효과이며 긴급 추가 개선은 작다. deadline 2초/8초는 포화된 설명 지표이며 UX SLA 또는 2%p 비열등성 입증으로 승격하지 않는다.
- 증거: `C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_run_v1`, `C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_analysis_v2/FINAL_REPORT.md`. 독립 block n=6, 세션당 urgent2, A24 thermal0·단일 canonical 입력 범위다.
- 미완료: 새 staggered workload의 simulation 예측을 평가 전에 동결하지 않았으므로 simulation 정책 순위·paired 개선량 일치 검증은 하지 못했다. 이번 평가로 simulator를 보정한 뒤 같은 평가로 검증하지 않는다. 추가 simulation·holdout·다기기는 별도 계획과 승인 대상이다.
- 영향: 기존 formal v1/v2, support-constrained simulation freeze, pilot·과거 APK·원본을 변경하지 않는다.

### 2026-09-23 — 독립 평가 PC 재현과 확장 시뮬레이션 plan-only 경계

- 상태: 채택. 사용자 지시에 따라 추가 실측 없이 기존 원본·판정의 재현 검증, 시각화와 탐색적 simulation 적합성만 수행한다.
- 재현 결정: 세션당 urgent2건 nearest-rank P95의 평균과 모든 요청 pooled P95를 별도 추정량으로 유지한다. paired t CI 단위는 6개 workload block이며 요청 수를 독립 표본 수로 쓰지 않는다. 기존 JSON과 semantic equality, 원본694 hash를 통과했고 joint primary `FAIL`은 변하지 않았다.
- 시각화 결정: 첫 primary paired block `replicate=0`의 세 정책 전부를 대표 간트로 사용한다. metric 기반 선택을 금지하고 PNG+SVG와 그래프 CSV를 함께 보존한다.
- simulation 결정: `arrival-extension-exploratory-simulation-plan-v1`은 기존 support-constrained freeze와 별도다. 응답시간을 서비스시간으로 쓰지 않고 execution-start→worker-release 점유, completion 경계, queue wait, residual, overlap, policy cost를 분리한다. 이번에는 plan 생성과 dry-run만 허용하고 성공 기준·본 실행은 없다.
- 한계: classification/GPU arrival cell0, detection/GPU15 전부 overlap·조건부 선택 표본이다. fixed split 우월성, overlap 인과 penalty, 임의 부하·순서, 독립 simulator 검증은 현재 자료로 지지하지 않는다. 평가 공개 후 fit은 적합도 확인이다.
- 근거: [PC 후처리 계약](ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md), 외부 `independent_evaluation_post_analysis_v2`, `arrival_extension_simulation_plan_v2`.
- 영향: formal v1/v2, support-constrained simulation freeze, pilot·독립 평가 원본·기존 분석은 변경하지 않는다.

## 새 결정 작성 형식

### YYYY-MM-DD — 결정 제목

- 상태: 제안 / 채택 / 대체됨
- 사용자 지시 또는 합의 근거:
- 결정:
- 이유와 근거:
- 영향을 받는 계획·코드·실험:
- 폐기하거나 대체한 이전 결정:


## 2026-09-23 — ARRIVAL-FIXED-01 고정 분리 대조군 준비

- 확정(사용자 작업 범위): 기존27세션 주 결합 FAIL과 모든 동결 계약/결과를 보존한다. 새 같은 기간 paired 측정 후보는 CPU_URGENT/FIXED_SPLIT/CONDITIONAL, 기존 burst·low·queue와 모델/입력/앱 정책/APK를 재사용한다. 과거 conditional과 새 fixed만을 주 비교하지 않는다.
- 구현 감사: fixed는 priority 기준 urgent CPU/normal GPU, 해당 lane busy이면 대체 배정 없음. 조건부는 기존 개발 추정97/250/558/1063ms와 도착한 큐만 사용한다. 네 runtime resident 및 각2warmup은 세 정책에서 동일하다.
- PC 준비 완료: 새 plan protocol과 기존 runner 확장, 품질 gate/cleanup 중단 결함 수정, 새 고유 manifest와16 Python/7 JVM 관련 테스트·두 안 dry-run. 기존 앱 inference 경계/정책/공식 v1/v2 변경 없음.
- 제안/승인 대기: 최소27 또는 정밀54세션 중 하나, 추가/retry/대체0. 주 비교 burst C−F urgent 세션 max·normal 평균의 상대차 Bonferroni CI. 동등성/비열등성 margin 없는 추정안 권장; 새 PASS 기준이나 실측 예산 승인으로 승격하지 않는다.
- 근거·실제 명령: [별도 계약](ARRIVAL_FIXED_SPLIT_COMPARISON_20260923.md), 외부 `fixed_split_preparation_v1/FINAL_REPORT.md`. 본 simulation/추가 모델·기기·역할반전·열부하 실행은 이번 범위 밖이다.

## 2026-09-23 — ARRIVAL-FIXED-01 최소안 실행 승인 및 시작 전 gate

- 확정: 사용자가 권장 최소안을 “승인할게”로 승인했다. 27세션/162평가요청/216warmup, retry·대체·추가0, host150분+cleanup45초 상한. plan SHA `9812ce6ec8d04c43e9a072bf15d712a222304ca96e2a0033d564748decaa213f`; 정밀54세션안은 미승인이다. 승인 receipt는 외부 `minimum_approval.json`에 보존한다.
- gate: 동일 A24 serial/fingerprint, thermal0·28.8°C·충전 없음·프로세스 부재를 확인했으나 배터리39%로 동결 시작55% 기준에 미달했다. 기준을 완화하지 않고 설치·측정 시작 전 중단했다. session attempt0/27, 평가0, warmup0이며 예산 재승인은 필요 없다.
- 동일 기기의 IP/mDNS 중복 연결은 serial/fingerprint를 먼저 대조한 후 IP 연결만 해제했다. 앱/기기 설정·원본 변경 없음. 충전 후 분리·cooling 및 gate 재확인으로 같은 승인된 명령을 시작한다. 원래 실제 실행 중 실패의 retry0 규칙은 그대로 유지한다.


## 2026-09-23 — ARRIVAL-FIXED-01 기술적 중단 및 부분 결과 보존

- 사실: 동일 기기와 승인 gate 확인 후 한 번 실행해23세션 완료. 24번째 시도의 실행 전 thermal 확인에서 ADB 연결 단절, cleanup도 첫 시도 실패. 24/27시도·142/162평가요청·184/216warmup; retry/대체/추가0. 재연결 후 원본 확인·cleanup만 수행했다.
- 확정된 규칙 적용: 사용자 재연결은 retry0·첫 기술 실패 종료 규칙을 변경하지 않는다. 남은3세션을 이어 실행하거나 실패 FIXED_SPLIT을 대체하지 않는다. 별도 복구 receipt를 남기며 원래 오류를 보존한다.
- 해석: burst 완전2pair와 low2pair는 계획n3 미달로 주/해당 CI 미산출. queue3pair의 사전 보조95% CI는 탐색으로만 표시한다. C−F는 관측된 모든 완전pair에서 urgent 비용과 normal 이득이 함께 나타났다. 전체 평가 완료·전면 우월성·동등성·비열등성을 주장하지 않고 기존 FAIL 유지.
- 산출물: [결과·재현 명령](ARRIVAL_FIXED_SPLIT_RESULTS_20260923.md), 외부 analysis_v3/FINAL_REPORT.md와 recovery_v1/recovery_receipt.json. 새 raw566파일·기존758파일 보존. 추가 측정은 별도 전향적 계획/예산 판단 대상이며 이번 작업에서 실행하지 않는다.

## 2026-09-24 — ARRIVAL-TIMING-DEV-01 시간 계약 보완

- 상태: 채택(사용자 승인 설계·코드·PC 범위). 기존 CONDITIONAL의 dispatch 기준 잔여 소진·누락 snapshot 문제를 시간 경계/재현 보완으로 다룬다. 간섭 보정 P의 우수성 근거로 확대하지 않는다.
- 새 protocol `arrival-timing-dev-v1` / ID `CONDITIONAL_TIMING_DEV_1`에만 phase 추정·판단 기록을 적용한다. 기존 ArrivalPolicy/old protocol/원자료·분석·198요청 FAIL·fixed-split 부분 결과·동결 simulation은 의미와 재현 경로를 유지한다.
- 판단→dispatch, dispatch→execution, execution→output, output→persist, persist→실제 scheduler callback의 5구간을 분리한다. worker_release는 기존 event 저장 전 경계를 유지하고 lane_available을 별도로 기록한다. host inference는 API 호출 구간이며 kernel 계측으로 부르지 않는다.
- 추정 소진/필수값 미정은 UNKNOWN으로 기록하고 busy를 가용으로 전환하지 않는다. 미확정 비교는 CPU idle 진단 fallback/CPU busy 대기다. 20값 모두 null인 출처 포함 설정을 제공하며 과거 단독 수치를 새 경계에 전용하지 않는다. 실험 READY 승격·새 성공 기준·실측 예산 확정 없음.
- 모든 선택/대기 호출·phase를512개 bounded RAM snapshot으로 저장하고 종료 때 flush한다. overflow는 이후 배정 중지·trace 무효이며 강제 종료의 기록 소실은 성공으로 취급하지 않는다. 새 PC 검증은 당시 입력 재생·경계/분모/누락 검사이고 전체 GPU/품질 gate가 아니다.
- 근거·검증·한계·후속 질문: [별도 계약](ARRIVAL_TIMING_DEV_20260924.md). 구현/관련 PC 통과와 실기기 미검증을 구분한다. 폐기한 기존 결정 없음; 완료·중단 실측을 재개하지 않는다.

## 2026-09-24 — ARRIVAL-TIMING-CAL-01 단독 진단 준비

- 상태: 설계·코드·PC 준비 채택 / **16세션 실기기 예산은 제안·미승인**. 직전12개 변경은 사용자 지시대로2904165에 선택적으로 checkpoint했다.
- 채택: 기존 실행기를 재사용하는 별도 `arrival-timing-calibration-v1`/`CALIBRATION_FIXED_BACKEND_1`, 지정 backend·global concurrency1·독립0/5/10/15초 도착. 모든 추정값 null이며 일반 experiment_ready gate의 예외를 만들지 않는다. 도착 시 아직 busy인 경우와 환경/계측 실패에 새 배정을 중단한다.
- 계약: 기존20 budget/조건부 ID 의미 유지. 새 `arrival-phase-observations-v2`는 task/backend/priority8조건×5구간을 구분한다. urgent도 저장하므로 저장이 응답 예측에 N/A인 것과 lane 점유 및 실제 관측은 다르다. 미측정을0/N/A로 대체하지 않는다. 단독 고정 정책 판단 비용은 적응형 비용으로 전용하지 않는다.
- 보존: worker event가 미완료일 때도 calibration의 실제 도착/queue 사실을 immutable snapshot으로 남기되 status는 unfinished다. warmup start/end를 별도 기록한다. 기존 arrival-v1·timing-dev-v1의 실패 해석/출력은 조용히 바꾸지 않는다.
- 제안 근거: 조건당 개발1+확인1의16세션·64요청·128warmup은 최소 수집 가능성/초기 중앙값 확인용이다. 동결 뒤 확인 자료로 재적합하지 않는다. 정밀도·검정력·안정된 tail 보장 없음. 예상45~60분·host/cleanup 상한121.5분, retry/대체/추가0. 과거27세션 잔여 예산과 독립이다.
- 구현: 별도 build root에 APK를 보존하고 APK Android/Gradle 입력 및 host plan/tool hash를 분리해 결합한다. phase 소비 registry는 출력 경로를 바꾼 재실행도 막고, 중단 뒤 회수/cleanup만 허용한다. 모델/원본/APK/동결 계약 덮어쓰기·ADB·실측·simulation·push/merge 없음.
- 근거·실제 명령·판정 경계: [진단 준비 계약](ARRIVAL_TIMING_CALIBRATION_20260924.md). 기존 FAIL과 부분 결과를 대체하는 결정은 없다.

## 2026-09-24 — APK 서명 복구 및 CAL-02 후보

후속 승인/종료: 사용자가16/64/128·retry/대체/추가0·121.5분을 승인했다. 동일성/기기 gate·서명 preflight 후 설치1회 성공, 실제 package/version/APK hash·서명을 확인했다. 첫 세션(index0)의 필수 trace/ledger/warmup/environment가 없어서 동결 중단 규칙을 적용했다. 세션시도1·완료0·실패1·미시도15, 확인 phase 미소비, fit 없음. 실제 진단/warmup 호출 수는 누락 기록 때문에 미확인(해당 세션 상한4/8)으로 남기며0이나성공으로 대체하지 않는다. cleanup 완료. 이는 서명 문제 해결과 별개의 계측/초기화 실패이며 GPU hang 등 원인은 미확정이다. [CAL-02 종료 보고](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md). 남은 세션 자동 재개·재시도·새 측정 없음.

- 채택: 현재 설치본/성공 보관본은 프로젝트 기존 debug 키b253…7565, 실패 APK는 전역 debug 키35ce…18f3임을 apksigner로 확인했다. 격리 출력 경로 자체가 키를 생성한 것으로 단정하지 않는다. 패키징 경로가 기존 ANDROID_USER_HOME 조건을 보장하지 않았고 설치 전 signer gate도 없었다.
- 기존 APK 정확한 바이너리를 기존 프로젝트 키로 새 경로에 재서명했다. ZIP909개 중 서명3개 외 동일, Android source/의존성/variant/manifest 불변. 키/비밀번호/개인 설정은 저장소에 추가하지 않는다. 앱 삭제·데이터 초기화·applicationId 변경·설치 재시도 없음.
- 새 CAL-02에만 parent 중단/hash 연결·새 UUID/registry·서명 preflight를 결합한다. 설치본 읽기 검사 실패는 phase/install/session0인 별도 receipt, 설치 실패는 claim 이후이므로 소비·중단이다. CAL-01 소비 상태를 소급 변경하지 않는다.
- PC10 및 실제 읽기 전용 A24 서명 비교 통과는 설치/추론 성공과 다르다. 후보16/64/128·retry/대체/추가0·개발8→동결→확인8·121.5분은 **승인 대기**이며 이번에 실행하지 않는다. [전체 근거·명령](APK_SIGNING_RECOVERY_20260924.md).

## 2026-09-24 — ARRIVAL-FAILURE-DIAG-PC-01 기록 보존 보완

- 채택: runtime 정지 원인과 기록 누락을 분리한다. CAL-02 마지막 GPU 로그/과거 crash를 원인으로 확정하지 않는다.125초 host poll 소진·finally/RAM 의존 기록 구조는 코드와 원본으로 확인했다. 진단0~4/warmup0~8 미확인 및 세션1/16 중단을 유지한다.
- 명시적 `arrival-failure-journal-v1`/performance_excluded 진단에만 session·runtime·호출 의도/반환·timeout/cancel/부분 cleanup을 append+fsync로 보존한다. 비용이 계측을 바꾸므로 calibration fit 입력을 차단한다. setup_only는 동일4runtime 생성·warmup/추론0이며 기존 정책/manifest 의미를 바꾸지 않는다. 저장 오류/128record 한도 초과 시 후속 호출 차단, native crash/강제 종료의 finally나 마지막 저장은 보장하지 않는다.
- host 실패 단계·회수 실패를 앱 실패와 분리하고 기존 phase 예산 안에서 pre-cleanup 증거5초+partial5초 후 기존 bounded cleanup을 수행한다. 기존 계획 hash/consumed를 갱신하지 않는다. PC 검증 완료는 실기기 GPU 초기화 복구 증명이 아니다.
- 제안(미승인): 새로운 setup_only 최대1시도·생성4·warmup/추론0·retry/대체/추가0·총600초. 기존30/120/125초 timeout 및 환경 gate는 유지한다. 새 실행 준비/승인이 필요하며 이번에 APK/실행 plan을 생성하거나 실측하지 않았다.16세션 보정·간섭·정책 비교로 확대하지 않는다. [근거·검증·한계](ARRIVAL_FAILURE_DIAGNOSIS_20260924.md).

## 2026-09-24 — ARRIVAL-TIMING-CAL-01 bound_v2 실행 승인

- 사용자 명시 승인 채택: 개발8→기록 검토·추정값/규칙/지원 범위 동결→확인8, 총16시도·64진단요청·128warmup, retry/대체/추가0, 실행+cleanup 합상한7290초. 별도 smoke/과거 fixed-split 잔여 실행 없음.
- 승인 대상은 plan SHA `a340a6c61e4eb4a85591ce226965495627ebd6751c3db4075b7b558a9d0553a2`, APK SHA `7bf84ce9997ed1fc0866ed89c38c84a78f37d5589a04eedef28ff65f16ae11e5`, HEAD `660532f`. 동결 plan의 역사적 proposed 상태를 고치지 않고 별도 승인 receipt에 결합했다.
- 최초 preflight의 동일 기기/연결·배터리·thermal·초기 상태 확인 후 승인된 개발 명령을 한 번 시작했다. 원자료/receipt: 외부 `timing_calibration_execution_20260924T105336` 및 `timing_calibration_development_run_v1`.
- 필수 기록 불완전·추정 근거 부족이면 확인 예산을 소모하지 않는다. 확인 자료 재적합·tail/간섭/정책 우수성 주장·일반 experiment_ready 승격은 승인에 포함하지 않는다.

- 실행 결과/동결 중단 규칙 적용: 개발 phase의 `install -r`에서 기존 설치본과 새 APK의 서명 불일치로 실패했다. session attempt0이어도 phase 소비/실패이므로 같은 실험 ID의 재실행과 확인 단계는 금지한다. 설치 시도1, Activity0, 세션0/16, 진단0/64, warmup0/128; 자동 uninstall/clear/재서명/재설치 없음. cleanup 완료·해당 앱 전체 프로세스 부재·thermal0. 상세: 외부 `timing_calibration_execution_20260924T105336/FINAL_REPORT.md`.

<a id="s26-npu-20260924"></a>

## 2026-09-24 — S26-NPU-COLLAB-01: 추가 기기와 NPU 개발 채택

**상태: 사용자 지시로 개발 방향 채택. 기기 identity·NPU 실행 장치·품질·성능은 검증 대기.** 문서화 시작은 `744cd75`, 작업 브랜치 `feature/arrival-scheduling-20260923`, clean이었다. 이번 변경은 문서/협업 정리이며 모듈 구현·기기 실행·평가 기준 수치 확정을 하지 않는다. 이전 NPU 제외/추가 기기 기능 제한은 아래 범위에서 대체하며 과거 기록은 보존한다.

### 채택 범위

- **S26을 XDEV-02 추가 검증 기기로 선정**한다. 정확한 모델명·SoC·fingerprint는 새 기기 manifest로 확인한다. 확인 전 S26 identity는 팀원 보고 정보이며 모델번호/SoC를 추정해 채우지 않는다.
- 팀원이 별도 **`npu-runner` 모듈·CompiledModel 엔진으로 NPU 확장 개발**을 진행한다. A24 작업과 병행하되 A24의 기존 `benchmark-runner` 런타임을 이 작업 때문에 교체하지 않는다. 이 로컬 체크포인트의 settings에는 npu-runner가 없고 팀원 측 최신 소스는 아직 검토하지 않았다. 채택은 현재 저장소 구현 완료 선언이 아니다.
- **S26 CPU/GPU 재현**은 검증된 두 모델과 동결 정책의 축소 재현평가이며, **NPU 확장**은 별도 엔진/모델 경로의 개발·동결·평가다. model-probe-v1 계열 실행 확인은 전자의 필요 자료일 뿐 XDEV-02 완료가 아니다. 기존 S26 80런은 보조 자료로 유지하고 새 두 모델·엔진·정책 검증을 대체하지 않는다.
- 모델별 지원·실제 실행 증거·출력 품질을 모두 통과한 NPU 경로만 배정 후보에 넣는다. 한 모델만 지원하면 해당 모델만 허용한다. 기기별 지원 경로/합법적 병행 조합을 정책 입력으로 다루는 구조는 개발 후 고정하고 새 자료로 평가한다. 현재 CONDITIONAL/시간 경계 개발 버전이3자원을 지원하거나 완전한 B3/P라고 기록하지 않는다.
- CPU/GPU/NPU 각각의 지원과3건 동시 실행 지원은 별개다. 검증되지 않은 병행 조합은 허용하지 않는다. 과거 기기의 열 상수·전환비용을 새 모델·엔진에 그대로 적용하지 않는다.

### 실행·품질 판정 원칙

| 항목 | 채택한 원칙 | 확보할 증거/미확정 사항 |
|---|---|---|
| 경로 이름 | `npu_full`/`npu_partial`은 후보 이름이며 자동 PASS가 아니다. 모델별 위임·실행 근거로 구분하며 근거 부족 시 미확정 | 원 모델 연산/partition→변환/AOT graph→컴파일 매핑, CPU 잔여 연산과 실패 시 fallback(거절/명시적 CPU 재시도/엔진 내부 대체)의 실제 의미·로그. silent fallback을 NPU 성공으로 세지 않음 |
| 식별 | engine, runtime와 compiler 버전, 원본 모델 SHA-256과 AOT 모델 SHA-256을 별도 기록 | 정밀도·변환 옵션·컴파일 target·device manifest·입출력 dtype/shape/layout·전후처리/labels/threshold. 같은 이름의 모델을 동일 artifact로 가정하지 않음 |
| DispatchDelegate | `1/1`이 변환 후 graph의 노드 집계인지 먼저 확인 | 원 모델 partition/compile mapping과 실제 실행 근거 없이 원 모델 전체 NPU 실행으로 확정하지 않음 |
| 장치와 품질 | 실행 장치 검증과 출력 품질 검증을 독립 gate로 둠 | `bit_identical_to_cpu`는 관찰값. true/false 어느 쪽도 NPU 실행 또는 품질의 PASS/FAIL 조건이 아님. 비트 비동일은 NPU 실행 증명이 아니며 비트 동일도 실패 조건이 아님 |
| FP16 등 변환 | 기존 FP32 경로와 동일 산출물 비교라고 부르지 않음 | 엔진·정밀도 변경 효과 공개, 공통 task 품질 요구를 사전에 고정. 속도 차이를 전부 배정 정책 효과로 해석하지 않음 |
| 분류 품질 | 대표 이미지와 적절한 출력/품질 기준으로 확인 | 입력 출처/hash·전처리·label 대응·출력 허용오차 및 task 품질 기준/표본을 결과 열람 전에 고정. 숫자는 이번 문서에서 임의 확정하지 않음 |
| 탐지 품질 | box/class/score와 필요한 task 품질 기준을 분리해 확인 | 좌표계·NMS/score threshold·매칭 규칙·적절한 task 품질 지표/하한을 결과 전에 고정. tensor 유사성만으로 정확도 PASS를 선언하지 않음 |

새 모델의 품질 기준은 해당 검증 결과를 보기 전에 고정한다. 이미 공개한 결과로 기준을 만들면 개발 자료 사용임을 밝히고 별도 확인 자료를 확보한다. 기존 합성 입력 결과를 대표 이미지 품질 검증으로 승격하지 않는다. 온도 관측을 에너지 절감으로 해석하지 않는다.

### 현재 근거와 보존

- **계약 모델 미검증:** EfficientNet-Lite0 / EfficientDet-Lite0의 NPU 지원·품질·성능은 확인 전까지 미검증이다. 아래 MobileNet 보고로 대체하지 않는다. 이 명시는 2026-09-24 팀 공유 동기화에서 기존 채택/검증 구분을 명확히 한 것이며 새 검증 결과가 아니다.
- **팀원 보고/미검토:** MobileNet V1 NPU 성공, 합성 입력32개 결과, manifest 수정 원인. 현재 전달 내용만 기록한다. 원본·해당 commit·변경 diff·사전 기준을 확인하지 않아 프로젝트의 독립 검증 완료로 표시하지 않는다. 특히 manifest 수정의 구체 원인·타당성을 여기서 추정하지 않는다.
- A24 두 모델 실측·198요청 독립 평가의 `conditional_joint_primary_pass=false`, fixed-split24시도/23완료 부분 종료, CAL-02 실패/미확인 소비량, 원본·동결 APK/계획·중단 registry는 그대로다. NPU 채택으로 기존 FAIL을 대체하지 않는다.
- EfficientDet exact binary의 비배포 경계는 유지한다. 원본뿐 아니라 이를 포함/파생한 AOT artifact도 배포 권한을 별도 확인하기 전 저장소·PR·APK·팀 공유 bundle에 넣지 않는다. 승인된 실행자가 고정 원 URL에서 직접 확보하는 기존 절차를 따른다.
- 이 결정은 **NPU 개발 채택**이다. NPU 품질·속도·에너지 절감·정책 이식성 검증 완료가 아니다. 새 기기 실행 예산/명령, 모델별 품질 수치, 지원 경로/병행 조합 freeze는 별도 근거가 필요하다.
- 팀 전달 최소 자료와 읽는 순서는 [팀 안내](team/README.md)에 있다. 이번 작업은 문서 diff/상대 링크/추적 파일·push 대상 점검만 하고 기존 테스트·빌드·실측을 반복하지 않는다. 작업 브랜치만 origin에 정상 push하며 master/타인 브랜치를 변경하지 않는다.

## 2026-09-24 — ARRIVAL-INIT-DIAG-01 단일 초기화 후보

- 채택/PC 준비: 사용자 요청에 따라 별도1세션·생성≤4·warmup/명시적추론0·retry/대체/추가0·전체600초의 실행 후보를 준비한다. 실행은 아직 미승인이다. 기존 CAL-02의source/입력/순서/CPU·GPU worker 소유권/대기 구조를 유지하고, 단계 기록과0호출 차단/검증만 보완했다. 생성자의 앱 추론 호출은 없으나 library prepare 내부 연산까지0이라고 주장하지 않는다.
- 단일 host monotonic T0+600 deadline에서 work cutoff545·회수10·cleanup45초를 예약한다. runtime30초/앱120초/host125초·cooling120초·환경 gate 유지. close는 같은worker에 제출하되5초까지만 기다린다. signature subprocess·host cleanup도 절대 deadline을 넘겨 새 예산을 시작하지 않는다. gate/여유 미달이면 Activity를 시작하지 않는다.
- 새로운 execution claim은 preflight 전에 소비하고 재진입을 막는다. install/session attempt는 각각 명령 직전에 별도 기록한다. runtime start 의도와 반환 증거/미확인 범위를 구분한다. preflight/설치 실패는 session0일 수 있으나 claim 이후 같은 계획 재실행은 금지한다. 기존 소비/중단 상태는 불변이다.
- 프로젝트 기존 인증서로 격리 APK를 빌드하고 PC 검증했다. 새plan/source/manifest/APK identity를 묶고 runtime_initialization 전용 root/registry를 쓴다. 동기 기록이 포함되어 성능 보정/평가에 사용하지 않는다. 결과가 완전해도 `complete_not_cause_resolved`; 불완전하면 마지막 확인 단계/회수 오류와 앱 실패를 구분하고 원인을 추측하지 않는다.
- 검증: 관련Kotlin5/Python15·compile/assemble·dry-run PASS, 실제ADB/설치/기기생성0. 새1회 실행 승인과 실제 설치본·기기/환경 gate가 남았다. 기존FAIL·부분 결과·20null/experiment_ready=false 및 S26 협업 결정은 유지한다. [후보 경로·실제 명령·한계](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md).

## 2026-09-24 — ARRIVAL-WARMUP-DIAG-01 준비 범위

- 채택은 PC 준비 범위다. 네 생성 성공 뒤 아직 관측하지 않은 첫 classification_CPU warmup 전이를1회만 확인하는 새 scope를 추가한다. 원래 CAL-02 순서/worker를 유지하고 나머지7warmup/4요청은 시작하지 않는다. setup_only 단순 반복·16세션 보정 재개 대신 미관측구간을최소확장한다. 과거원인을고친다는추측성수정은하지않는다.
- 앱명시적inference 상한1은warmup1에포함되며추가호출이아니다. 입력준비/host API/출력단계와Future대기를기록하되성능보정에는쓰지않는다. 공식inference timer 내부경계는유지한다. 새실행예산은1세션/600초제안·미승인, timeout/gate는기존값유지.
- 과거RawAdapter의Git blob과원working-tree byte hash 대응미확인은별도공시한다. 새후보source/build/APK/plan mandatory검사에는예외를두지않는다. 기존FAIL·부분결과·두종료계획·20null/experiment_ready=false 불변. [비교와판독기준](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md).

## 2026-09-24 — ARRIVAL-WARMUP-REQUEST-DIAG-01 통합 준비 채택

- 첫 warmup 성공 후 두 번째 호출만 확인하는 진단을 반복하는 대신, 원 순서8warmup과 첫 정규 classification/urgent/GPU1건의 전이를 한 세션에 관측하는 PC 준비를 채택했다. 정규1건은 dispatcher·저장·lane callback 경계 확인용이며 평가가 아니다. 설치/세션1·생성4·warmup8+요청1=명시적추론9·600초·retry/대체/추가0은 **제안 예산/미승인**이다.
- 구체적 공백인 전체 warmup의 제출/내부 단계, 정규 요청의 durable 저장/callback 기록을 새scope에서 보완한다. journal 정상 예상약191개에 근거해 새scope만256, 기존scope128 유지. 기존 worker_release 의미를 물리적 lane 해제로 바꾸지 않고 event저장과 scheduler AVAILABLE을 별도 기록한다. 환경/timeout 완화나 간섭 정책은 추가하지 않는다.
- 동기 기록의 성능자료 제외,20null/experiment_ready=false,과거FAIL/부분결과/소비registry와RawAdapter 대응미확인 유지. 성공은 보정 준비로 넘어갈 조건이며 과거원인치료·8조건 보정·반복안정성의 검증이 아니다. 후속 조건은 새 보정 개발/확인 계획에서 함께 다루고 구체적 장애 없이 작은 진단을 계속 증설하지 않는다.
- PC Kotlin19/Python24·컴파일/서명/계획검사 통과와 실기기미검증을 구분한다. [근거·파일·판독·남은검증](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md).

### 2026-09-24 실행 결과 반영

위 제안은 이후 사용자가 같은예산으로 승인했고1회실행후중단됐다. 설치1성공/세션1실패·311.344초, CPU분류runtime1반환과GPU분류Interpreter시작만확인, 이후호출수미확인이다. 회수·host cleanup완료, 앱정상close미확인. 같은계획재시도는하지않는다. 이번결과로보정준비/과거원인해결을선언하지않고PC에서Future30/main watchdog120의무기록조건을검토한다. 상세는 [실행결과](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md)와외부원본을따른다. 새실측예산이나timeout완화결정은없다.


## 2026-09-24 ARRIVAL-STALL-OBS-DIAG-01: host 독립 관측 채택

- 확정: GPU worker/setup Future/main watchdog 구조는 유지한다. 원인이 확인되지 않은 앱/런타임 수정 대신 기존 통합 APK 재사용과 host125초 안5/35/105초 read-only snapshot을 추가한다. 앱/API source identity 동일성을 PC검사하고 새 host source·계획·session·registry를 고정한다. [근거·계약](ARRIVAL_STALL_OBSERVATION_DIAGNOSTIC_20260924.md).
- 증거: 통합 실패는 CPU반환/GPU interpreter 시작 이후 무기록, Future30/watchdog120도 무기록이다. journal fd.sync 지연과 OS/VM/scheduling 정지는 가능한 가설이나 현재 확정 원인은 아니다. invisible은 성공setup에도 있었으므로 단독 인과근거가 아니다. Handler uptime과host125초를 같은clock으로 취급하지 않는다.
- 범위: 사용자 승인1계획/1설치/1세션/runtime4/warmup8/정규1/추론9, 평가0/retry0,600초(545/10/45). 신규observer는 각8초·명령2초, signal/debugger/root 없음. 접근불가stack은미확인. PC검증20건은 native복구 입증이 아니다. 종료계획/기존FAIL/미확인소비량/20null/experiment_ready=false 유지.


### 2026-09-24 실행 판독 및 CAL-03 제안 분리

- 진단1회성공: runtime4/warmup8/정규1,209.390초, 앱/hostcleanup. Dozing/top-sleeping과isFrozen=false를한시점관측했으나전체실행은성공했다. 원인해결·반복안정성·성능보정을선언하지않는다. stack권한거부와native_gpu_verified=false보존.
- 확정개발변경: 새CAL-03 provenance/unique ID·registry·sync journal없음·awake/interactive read-only 시작gate·host poll125절대deadline 지원. 이는sleep환경을보정지원조건에서분리하는새수집조건이며과거gate를소급변경하지않는다. 화면조작없음.
- 제안/미승인: [CAL-03](ARRIVAL_TIMING_CAL03_PREPARATION_20260924.md)의16세션·64진단·128warmup/121.5분. 기존규칙으로개발8→동결→확인8, 관련PC15건과dry-run통과. 실행승인과측정품질PASS는아니다. 기존20null과experiment_ready=false유지.


## 2026-09-24 CAL-03 실행·동결·확인 판정

- 사용자 승인16세션/64진단/128warmup·retry/대체/추가0·합121.5분 범위를 유지했다. 결과 열람 전에 화면상태10초 host 관측, settings 전후 확인, 작업deadline의 회수10초 예약을 보완해 v3 source/계획을 고정했다. v1/v2는 미실행 보존, APK/모델/순서/통계량 변경 없음. [사전 규칙과 결과](ARRIVAL_CAL03_EXECUTION_20260924.md).
- 개발8개 모두 적격한 뒤40슬롯 median/min/max·원자료/환경 hash를 동결하고 확인8을 수집했다. 설치2·진단64·warmup128, 실패·미시도·대체·retry0, 앱/host cleanup16/16. 화면96표본/후속lane재사용48쌍 확인. 약43.43분의 이번 자료로 과거 정지 원인을 확정하지 않는다.
- 자료 적격성은 통과했으나 수치 정확도 허용폭은 원 계약에 없으며 performance_pass=null을 유지한다. 확인 자료로 재보정하지 않았다. S→O 최대 절대오차32.270ms, 탐지/GPU/긴급의 중앙값 초과4/4를 포함한 모든 오차를 보존한다. median은 상한/초과 잔여시간 분포가 아니다.
- 확정 범위: A24·고정 입력·resident4·CPUthread1·단독·관측된 awake/thermal 조건의 초기 구간 관측. 40슬롯을 기존20개 설정에 자동 복사하지 않는다. adaptive D→A·priority별 적용·UNKNOWN_OVERRUN·병행 부하 미검증을 유지하고 experiment_ready=false다. 다음은 해당 경계를 정리하는 PC 작업이며 새 정책 실측이나 추가 기기 진단 승인이 아니다.


## 2026-09-24 — ARRIVAL-CAL03-CONNECT-01: priority·공동 구간 PC 연결

- 채택/PC 검증 완료: 동결40값을 task×backend×priority로 보존하는 새 설정과 PC 개발 정책을 사용한다. 기존20필드/정책ID/Android 경로에 대입하지 않는다. 개발자료에서 각 요청의 A→응답/A·S·O·P→L 차를 먼저 계산한 중앙값을 파생 설정에 두며, phase 중앙값의 합을 전체 구간 중앙값이라고 해석하지 않는다. 확인 자료는 변환/튜닝에 사용하지 않는다.
- 고정 경로 D→A는 적응형 비용이 아니므로 missing/null 유지. 엄격 모드는 CPU fallback/단독busy 대기, 공통 비용을 명시한 PC 가정 모드에서만 후보 최소 응답 선택. 이는 보수적 개발 제한이며 성능 보장·새 P 기여가 아니다. UNKNOWN_OVERRUN 유지·실제L callback 전busy, W에서 P→L 시계 재시작 금지.
- 새 이벤트 엔진은 기존 동결 simulator/옛 탐색 계획과 분리한다. CPU/GPU overlap은 미지원으로 차단하고, 다른 도착/순서에 단독 벡터를 쓰는 전이는 미검증 가정으로 표시한다. policy 예상과 engine 실현을 분리하며 예정도착·전체분모·미완료를 보존한다. PC21시험/8요청 엔진 점검은 기기 검증·독립 예측 검증이 아니다.
- experiment_ready=false: adaptive 비용/부하 의존 지연/병행 간섭/정확도 기준/새 앱 연결·독립평가가 미충족이다. 기존10% 판정·FAIL/부분결과·CAL-03 performance_pass=null·동결값·종료계획 불변. 상한/허용폭/실측 예산을 새로 확정하지 않는다. [범위·구현·검증·다음 조건](ARRIVAL_CAL03_CONNECTION_20260924.md).

## 2026-09-24 — ARRIVAL-COLLECT-01: 통합 개발 수집 경로 준비

- 채택/PC 구현: 기존 정책을 바꾸지 않고 새 collection namespace에서 PC 엄격 정책의 실제 배정과 고정 배정+shadow를 분리한다. strict는 현재 CPU fallback·전체직렬이고, fixed는 urgentCPU/normalGPU이며 global1과per-lane2를 구분한다. snapshot/후보/초과잔여/선택없음·계산/메모리기록/dispatch 시간 경계를 보존한다. 동기 journal 없이 버퍼를 종료 시 저장하며 유실을0호출로 바꾸지 않는다.
- 근거: 공통 판단비용은 backend 순위에서 상쇄된다. 이번 목적은 완전한P 개발이 아니라 실제 목표 경로의 절대시간과큐/병행 지원 범위를 식별할 최소 자료다. 한정 병행은 탐지normalGPU+분류urgentCPU만, 단계별앞5조건검증/cleanup 뒤 허용한다. F를마지막에두는 안전조건의순서교란, overlap과큐전이혼재, 조건당독립세션1개의한계를명시한다.
- 제안/실측 미승인: 개발6→회수hash재검사/조건별기술통계동결→확인6,12세션/48진단/96warmup/설치2·retry/대체/추가0·상한91.5분. 새로운 실측 승인 전에는 실행하지 않는다. 단계claim/preflight/설치/세션/Activity소비를 분리하고 어떤실패든전체계획종료·재개금지. 확인자료재보정·CI/tail/정확도/우월성PASS없음.
- 검증: Kotlin28/기존timing Python9·최종collection Python13/실제Kotlin-PC snapshot12, APK빌드/PC서명/dry-run통과. 실기기병행·환경·성능 미검증. host동결검사보완으로planv2, 기존v1/APK보존. [상세 계약·실제 명령](ARRIVAL_INTEGRATED_COLLECTION_20260924.md).
- 유지: 기존40값/20null/FAIL/부분결과/종료계획·experiment_ready=false. 강한B2/B3/P·기존시스템 비교와 축소 기준은불변. 이수집성공만으로최종비교완료/새성공기준을부여하지않는다.

### 2026-09-24 ARRIVAL-COLLECT-01 승인 실행 중단 판정

- 승인12세션/48진단/96warmup·2설치·retry/대체/추가0·91.5분 범위에서planv2를변경없이1회호출했다. 설치전identity/서명/환경gate통과 뒤 install-r가120초timeout. 설치1·세션0·명시적추론0, 미시도12다. 원래중단규칙대로전체종료, 미소비세션을재개/대체하지않는다.
- hostcleanup/프로세스부재확인, 이후비파괴조회에서이전설치APK해시유지. 서명불일치가아니며전송/패키지처리원인은미확정. 앱실행전실패이므로GPU/CAL-02원인에새결론을부여하지않는다. 화면설정변경없음.
- 새적격자료가없어동결/확인/PC연결은수행하지않는다. 기존설정과experiment_ready=false유지. 다음은설치timeout부분출력·단계시간보존을갖춘새진단의PC준비이며지금추가기기작업을승인하거나실행하지않는다. [원본·소비량·판독](ARRIVAL_INTEGRATED_COLLECTION_20260924.md).

## 2026-09-24 — 설치 복구와 COLLECT-02 분리 준비

- 채택/PC구현: 새 복구 전용 host 기록으로 명령 시작/종료·부분 stdout/stderr·timeout·client tree 종료·설치 후 조회 실패를 남긴다. 기존install-r 스트리밍 추정 대신 명시적 push/hash→pm install-r로 분리한다. 방식·추가 staging 비용이 달라지며 이전 방법과 동일 실험이라고 하지 않는다. 설치timeout120초 유지, 기존증거의전송/패키지처리원인은미확정.
- 복구와 수집의 namespace/소비/출력을 분리한다. exact APK/package/version/signer 확인 시 재설치생략 가능, 아니면 복구단계만 설치최대1. 성공receipt·증거hash·cleanup 확인 후 새 수집, 각 단계 설치본 재검사, 수집내설치0. 기존중단계획·미시도분재사용금지.
- 미승인예산: 복구600초+기존설계수집5490초=6090초, 개발6→동결→확인6/48진단/96warmup/명시적144, retry·대체·추가0. 한 번의 향후 승인으로 gate 충족 시 자동 진행하는 스크립트 준비. 이번에는 기기 작업0.
- PC28건·서명/해시/manifest/dry-run 확인. Android/APK변경없어재빌드없음. 기존40값/20null/FAIL/부분결과/experiment_ready=false 보존. [상세 근거·예산·명령](ARRIVAL_INSTALL_RECOVERY_20260924.md).

### 2026-09-24 승인 실행의 배터리 gate 중단

- bceec84에서동결된복구/수집계획을승인실행했다. 서명/기기조회후배터리50%가시작55%를충족하지못해원래규칙대로종료. 후보push/install0, 수집phase/세션/명시적추론0, retry/대체/추가0. 단순로그부재가아니라기록된명령과설치전제어흐름을근거로0을판정한다.
- hostcleanup/프로세스부재·기존설치본유지확인. 복구91.156초/workflow92.297초, 새비용표본없음. 현복구/workflow소비기록보존·재개금지, PC연결/병행허용확대없음. 다음은충전/비충전조건준비후새식별자의계획준비이며추가기기실행을자동승인하지않는다. [원본·소비량](ARRIVAL_INSTALL_RECOVERY_20260924.md).

## 2026-09-25 새 승인 RECOVERY-02 / COLLECT-03 및 부분 종료 판정

- 채택/실행: 사용자가 v1과 별개의 예산을 명시적으로 승인해 새ID/UUID/출력/registry를 발행했다. v1의실패·소비를보존하고4개선행증거hash를연결했다. APK/수집설계/기준/timeout불변, hostnamespace변경PC14건확인. 개발자옵션재활성화는사용자보고와현재관측을구분하며과거원인으로단정하지않는다.
- 실기기결과: 설치1성공·개발6완료동결·확인3완료후4번째앱실행전staging의PC5037daemon접속실패로전체종료. 10시도/9완료/실행전실패1/미시도2, 진단36/warmup72, retry/대체/추가0. 기존계획재개·실패세션대체·자동새계획발행없음. 원본·미실행분·cleanup을모두보존한다.
- 판정: 개발동결값은확인자료로재튜닝하지않는다. 확인3/6의기술통계만보고하며전조건확인/정확도/정책우월성PASS를부여하지않는다. active/병행확인미실행과사전정확도기준부재때문에PC정책·시뮬레이터연결및병행허용확대를보류한다. 조건별중앙값·관측오차는상한/인과간섭계수가아니다.
- 다음최소작업은PC의ADBdaemon/staging증거점검이다. 기존40값/20null/FAIL/부분결과/experiment_ready=false와B2사전선정·B3/P실제차이·독립평가계약을유지한다. [종료결과·근거](ARRIVAL_INSTALL_RECOVERY_20260924.md).

## 2026-09-25 확인 전용 후속 설계·host 관측 보완

- 채택/PC구현: 완료개발6·동결값은재사용하고누락확인조건B/A/F를별도ID/registry/UUID로준비한다. 기존확인E/D/C의3세션과원계획실패·미시도분모를보존한다. 날짜/순서/host기록변경및선택적후속확인을명시하며원계획완주로합치지않는다. 기존동결의오차확인과새정책튜닝을분리한다.
- 원인판정: PC5037접속실패확인, daemon내부원인미확정. 새host의server사전조회/생성의도·실제clientPID/부분bytes/OSsnapshot과client-only종료를채택한다. 명시적server재시작/재연결/retry는없다. 체크와client실행사이race·host계측영향은남으며PCmock을실기기복구성공으로해석하지않는다.
- 제안/미승인: 3세션/진단12/warmup24/명시적36/설치0/30분, retry·대체·추가0. 새병행gate는불변과거6개발+3확인과당일2직렬세션검증/cleanup 및당일runtime/admission이다. 원계획같은phase5선행조건과다른후속계약임을명시한다. 당일GPU직렬대조없으므로인과간섭평가가아니다.
- PC13신규+7관련회귀와dry-run통과. 기기명령/ADBserver변경/설치/추론은실행하지않았다. 다음은별도예산승인후에만현재gate·후속확인이다. 완료해도정책우월성/임의병행/정밀tail/P기여/experiment_ready=true를자동부여하지않는다. [계약·명령·근거](ARRIVAL_CONFIRMATION_FOLLOWUP_20260925.md).

## 2026-09-25 ARRIVAL-SERVICE-REVIEW-01 — 계산 확인과 방향 권고

- 확인/보존: B2는 개발 후보8개(explore)에서 한 번 선정해 평가에 고정했다. 평가별 oracle·P 전용 비용을 추가한 오류는 확인되지 않았다. 지연2지표와 기한 위반까지 포함한 서비스 관계를 분리한다. 기본 큐 B2/P 일반 위반20/90·17/90 때문에 두 지연 평균의 B2 우세를 전체 서비스 우세로 확대하지 않는다.
- 채택/분석 원칙: 기존960행·동결값을 유지하고 동일seed 상대차를 먼저 계산한다. 새 후처리의 제거군 이름 오류만 정정하고 원 수치/정책을 바꾸지 않는다. 가정 기반 민감도 경계를 새 성공 기준·비열등성 margin으로 채택하지 않는다. 기존198요청 FAIL과 experiment_ready=false를 유지한다.
- 권고/미채택: 현재 P 튜닝을 보류하고 강한 정적 기준 중심의 제한적 서비스 선택 문제로 정리한다. 최종 목표를 바꾸는 합의는 아직 없으며, CPU 긴급우선 대비 일반 기한 위반 증가 허용 여부가 다음 사용자 판단이다. 단순 정책으로 충족되지 않는 실제 요구가 확인될 때만 적응형 개발을 다시 검토한다.
- 승인 범위 정정 설명: 대화 원문은 시작 배터리20%를 명시했다. 실행 중30→20 변경은 당시 구현 해석이고 별도 명시적 승인 근거는 미확인이다. 시작52%는 옛55% 미달, 세션 관측51%는 옛 실행 중30% 이상이다. 원본·계획·과거 기록을 소급 변경하지 않는다.
- PC5테스트·대표3재생 일치 확인. 추가 실측·ADB·전체 배치·정책 튜닝 없음. [보고서·수치·근거](ARRIVAL_SERVICE_COMPARISON_20260925.md).

## 2026-09-25 ARRIVAL-DELTA-SELECTION-01 — 허용폭 경계 분석

- 채택/이번 분석 규칙: 사용자 지정대로 CPU 긴급우선 대비 일반 위반율 증가δ(%p) 제약 아래 긴급P95만 최소화한다. 이전 후처리의 일반평균 제약·긴급위반 우선 정렬은 적용하지 않는다. 정수 planned/위반 건수의 정확한 분수로 경계를 계산하고 동률을 모두 보존한다.
- 확인: δ0에서B2단독9조건·CPU단독2조건·low동률4정책. P단독최선구간없음. 전조건고정적용의적격경계는CPU0/B2 40/9/B3 140/9/P 220/9/고정분리50%p다. 최악값비교는기술통계이며미합의minimax목적으로최종승자를선언하지않는다.
- 미채택: δ0포함허용폭수치·시나리오가중치·서비스목적변경. 이번결과는공개된평가자료의사후선택이고새평가/배포가능oracle가아니다. 현재P추가튜닝보류와재현용보존을권고하며간섭인지정책일반의불가능성을주장하지않는다.
- 신규4PC테스트통과, 추가실측/시뮬레이션/P튜닝/B2재선정없음. 기존FAIL·부분결과·동결40값·20null·종료계획·experiment_ready=false보존. [보고서·CSV·명령](ARRIVAL_DELTA_SELECTION_20260925.md).

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 — PC 수집 설계 판정(실행 미승인)

- **채택한 준비 방식:** 세 실제 정책 관련 병행 상태(CC_DG, B2의 CG_DC, B3의 탐지 CPU＋GPU)를 대칭 복사하지 않고 별도 관측한다. 개발3/확인3에서 블록 순서를 바꾸고 계수·코드·계획을 확인 전에 동결한다. 전력은 250ms 반복 구간의 **기기 전체 평균**이며 순간 joint·요청별 계수가 아니다. AP는 식별 rank/양의 시정수 gate를 통과하지 못하면 null/중단한다.
- **미채택:** 기존 개발2＋확인2/144분 후보를 확정 예산으로 전용, 온도 anchor 부활, 확인 자료 재보정, 임의 정책 PASS. 새 후보 상한 6세션·추론 10,152회·230분은 **실측 미승인**이다. 이전 중단 자료와 4세션 결과·원본·FAIL·동결값은 불변이며 `experiment_ready=false`다.
- 근거·PC 검증·실행 gate: [수집 준비 계약](ENERGY_AP_STATE_COLLECTION_PREP_20260927.md). APK/기기 서명·현재 환경·memory·병행 적격성은 실행 직전에 다시 확인한다.

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 — 승인 후 실행 전 gate 보류

- 사용자가 plan_v3의 6세션·추론 최대 10,152회·230분 실행을 승인했다. 계획 해시와 `Check`는 일치했으나 `adb devices -l`에 기기가 0대여서 A24 동일성과 환경을 검증하지 못했다. 따라서 `Run` 미호출, 계획·출력·소비 registry 미생성, 세션·설치·추론 0이다. [착수 기록](ENERGY_AP_STATE_COLLECTION_PREFLIGHT_20260927.md).
- 미채택: 연결·서명·환경 gate 생략, daemon 재시작/강제 재연결, 이전 값 전용, 이번 실패 뒤 자동 재실행. 기존 수집 종료 계획·FAIL·원본·동결값과 `experiment_ready=false` 유지. 새 모형 계수·확인 오차 및 정책 개선 주장은 아직 없다.

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 — 전송 중단 후 종료

- 동일 A24와 현재 gate가 확인되어 승인 plan_v3를 한 번 호출했다. 이전 설치본이 정확한 후보 APK와 달라 전송 1회가 시작됐으나, 120초 timeout으로 원격 해시 전 경계에서 실패했다. 설치·앱·세션·추론 0, 개발/동결/확인 미실시. `stopped_no_resume`와 소비 registry를 보존한다. [원본 경계·cleanup 보고](ENERGY_AP_STATE_COLLECT03_RESULTS_20260927.md).
- 재시도·대체·추가와 기존 계획 재개는 채택하지 않는다. 전송 원인과 원격 부분 파일 상태는 미확정이고 이번 결과는 전력/AP 계수나 정책 효과의 증거가 아니다. `experiment_ready=false` 유지.
## 2026-09-29 — 최소 도착 입력은 고정, 시작 AP gate 미충족으로 실행 차단

- 결정: 기존 queue 24요청/FIXED_SPLIT/120초를 첫 확인 입력으로 고정하고, 32.5–34.0°C 개발 **시작** AP 범위를 사전 gate 계약으로 사용한다. 32.5–39.5°C 세션 경로 범위나 32.3°C의 범위 밖 결과로 하한을 바꾸지 않는다. 1초 전류·약2.63초 AP 대비 짧은 요청과 병행 점유0초 때문에 이 입력은 공통창/전환 확인 질문에만 쓴다.
- 실행 판정: 현 앱/host는 실제 load 시작의 numeric AP를 집행하지 못한다. 새 실시간 handshake를 즉석에 넣거나 thermal status로 대신하지 않고 `PC_INPUT_FIXED_RUN_BLOCKED`로 둔다. [`근거·입력·Check`](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md). 동결 계수·과거 결과·strict unsupported·`experiment_ready=false` 유지; 실행 계획이나 실측 승인을 만든 결정이 아니다.
## 2026-09-29 — 시작 AP는 baseline 뒤 1회 조회와 앱 최종 검사로 집행

- 사용자 후속 구현 지시에 따라 `numeric-ap-once-v1`을 별도 opt-in으로 구현했다. host 준비 온도를 재사용하지 않고 baseline 뒤 새 HAL AP를1회 조회해 앱이 origin 직전 범위/표본 나이를 확인한다. 사전 최대5명령/앱 대기30초, 실패 시 본 작업0·재시도0; 부하 중 새 handshake 없음. 이전 차단 판단과 동결값을 보존한다.
- 이 입력의 완료는24요청 조건부/종단간 오차 보고까지이며 병행 계수·짧은 요청 J·임의 부하 정확도 PASS로 확대하지 않는다. 계측 변경은 프로토콜 전이로 표시한다. [실제 코드·검증·한계](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md). 실측 승인/실행 계획 발행 아님.

## 2026-09-29 — 시작 AP 단일세션 계획은 미승인 PC 준비로 분리

- queue24/FIXED_SPLIT/공통120초의 [별도 실행 계약](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md)을 고정했다. 프로젝트 서명 APK·AP gate·새 session/output/registry·1,300초/ADB3,000/총 추론32 상한을 PC Check했으나 현재 기기 조건과 예측 정확도는 미검증이고 실측 승인은 없다. 처음 `PC_INPUT_FIXED_RUN_BLOCKED` 입력 기록은 이력으로 보존한다.
- 이번 확인의 종료 범위는 한 입력의 A(실제 일정 조건부 J/AP)·B(예정 도착 종단간 일정/응답/비용)의 자료 적격성 및 오차 보고다. 병행0인 PC 일정만으로 병행 계수, 열→시간 피드백, 동적 정책 우월성을 채택하지 않는다. 동결 계수와 `experiment_ready=false` 유지.
