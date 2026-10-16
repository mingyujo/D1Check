# ATC＋PPO 2차: 단일 이미지 범위·대조 피드백·P95 보호

작업 `ATC-DELTA-REFINE-09`, 2026-10-12 KST. 사용자 ‘여러방면으로실험하면서발전’의후속이며 EFT금지·Greedy비교군전용을유지한다. 08의5연결×3seed 학습3840/환경6836/확인1344는완료됐고소스/가중치/원자료/선정을바꾸지않는다. 08에서는행동을바꾸어도일부서비스손실과학습seed불안정이남았다. 이번에는실제지원범위n1에서학습목적과credit를추가비교한다.

## 세 군과 비교 의미

| 군 | 연결 | 학습 피드백 |
|---|---|---|
| JP05_CAUSAL | ATC 후보＋기준행동prior0.5＋PPO | 08과같은절대CAUSAL10목적(E100J/AP1°C/Uholding) |
| JP05_DELTA | 같은연결/prior | 동일입력의ATC사후대조＋E1J/AP0.1°C/P95초과비용 |
| ATC_SCORE_DELTA | ATC현재score−gap＋NNresidual,beta1 | JP05_DELTA와같음 |

JP05_CAUSAL 대 JP05_DELTA는대조baseline·단위·P95목적을묶은효과이다. 순수분산감소만의대조가아니다. 두DELTA군은목적이같아연결효과를분리한다. 08vs09는학습범위·입력seed·목적도달라연결단독효과라고하지않는다. 모든군은물리mask·현재후보와state218/action57/pad32를공유하며fresh weights다. 다른schema/목적의08weights를그대로재사용하지않는다.

제안은ATC와PPO뿐이다. Greedy/RR/FIFO/EDD는대조군이고제안내부출력호출0, EFT새비교/행동/재생0이다. CPU는ATC p/r기준경로와canonical teacher순서이며현재평균/EMA와현재합법성만쓴다. finish최소화·미래큐rollout/place/전체큐J/AP추정/legacycallback은runtime trap으로금지한다. SLOT32 single/pair/필요자원WAIT·비선점·실제AVAILABLE·응답분리·CG_DC≤2·NPU0·냉각대기0은그대로다.

## ATC 대조를 어떻게 쓰는가

새학습256입력마다RuleATC를**실제독립환경**에서한번실행해저장한다. 이256환경은control예산에포함하고9모델이같이참조한다. 같은case/request/backend-keyed exogenousdraw와초기상태를사용하며정책/RNG호출순서가환경draw를바꾸지않는다.

대조의완료궤적은**student episode가끝난뒤학습label**에서만읽는다. 운영state·후보·mask·추론·dispatch는그궤적/미래응답/에너지/온도를받지않는다. 이것은현재상태에서teacher미래를재계획하는것이아니라독립완료궤적의사후slice다. 같은현재물리시각t에서대조futurebaseline을계산하며teacher의결정index와맞추지않는다. exogenousdraw·현재t에정해진baseline은현재a_t에독립이라는가정아래controlvariate로쓴다.

`Rδ(t)=Ractual_future(t)−RATC_future(t)`이며unitAVAILABLEcredit는`t < AVAILABLE ≤120초`인완료만넣는다. 경계완료가이미앞행동에귀속됐다는원credit계약과맞춘다. 미응답unitarea는[t,response]∩[arrival,120]을적분해/units/85초로정규화한다.

`Eδ(t)=Eactual_increment(t..120)−EATC_increment(t..120)`, 단위1J다. AP는각궤적의35초이후runningpeak에서과거peak(t)를빼서남은growth120을각자구하고,그차이를0.1°C로나눈다. signed차이를유지하며음수는기준보다낮은비용이다. shared initial/preload와공통120창을맞춘다. 공통float64helper로두궤적을계산한후float32로변환해같은궤적의R/E/AP차이는정확0이된다.

cost3~8의요청/원cap U/N실패rate·terminalIunits/Irequest는**절대값**그대로다. 마지막cost9는holding대신`max(0,(student조건P95−같은조건ATCP95)/1500ms)`이며weight10이다. 1500ms는정규화단위이고원1.5초cap초과와는다르다. P95는완료응답분모라절대U/I·전체분모/최종guard와항상함께본다. 응답누락으로P95가낮아지는결과를안전이라고부르지않는다. P95None/대조미완료는0으로대체하지않고중단한다.

DELTA비용가중치는E/AP각1·Ureq/Ucap/Nreq/Ncap/Iunits/Irequest/P95초과각10이다. CAUSAL군은원E100/AP1/holding1목적을그대로써대조한다. E스케일100배/AP스케일10배와P95목적교체를단일baseline효과로귀속하지않는다. R/E/AP/P95의같은궤적δ0은절대서비스비용전체0이나gradient전체0을뜻하지않는다.

## 새 자료·선정·최종 확인

889 namespace, train32arrival×4family×2factor=256, dev2×4×2=16, final4×4×2=32다. private889000201/publichint889000301, fresh초기701/709/719·행동+10000/셔플+20000을분리한다. 모든요청work_units1로n2/n3 합성은없다. 동일384donor의5phasebootstrap/CPU분류4표본약점과현재모형의PC탐색한계는유지한다. fixed기한U1.5/N6 또는single_due U.75/1/1.5·N3/4.5/6,원cap1.5/6도보호한다.

balancedC/D의low24/gap1.8,variable48/gap.65~1.05,paired48/group2.6(Cfirst/Dfirst교대),sustained96/gap.85와35..120창이다. 동결기기모형·서비스·에너지120/모형AP35..180의최종기준을유지한다. 대조label의APprefix120과최종180은같다고보장하지않는다. 운영은동결masked argmax·사건마다미시작재판단이며formalrollinghorizon없다.

각군/seed64→128→256후개발의**조건별**I/units/Ureq/Ucap/Nreq/Ncap/P95가RuleATC보다나쁘지않은checkpoint만먼저선별한다. eligible이면meanJ→AP→P95/earlier로고정선정한다. 모두실패면besttrained서비스lex를평가하며실패를숨기거나CP0를학습이득으로돌리지않는다. 모든9모델과대표를개발만으로부모freeze에고정하고나서새32×15군=480행을평가한다. 확인후학습/선정/설정변경0이다.

09strict는08의EFT제외개정참조(FIFO_FIXED/RR/Greedy/RuleATC)를유지하고전량완료/요청·원서비스/P95/J/AP/epsilon0/모든조건비악화와strict비용개선을검사한다. 과거EFT참조포함닫힌FAIL을소급변경하지않고새strict후보도자동기기채택하지않는다. 응답P95·선언/원기한 실패·AVAILABLE완료·energy/AP조건별승동패를함께보고한다.

## 예산·검증·실행 경계

예정3580환경=teacher학습대조256＋student학습2304＋student개발432＋규칙개발96＋최종480＋초기native증명12다. 학습2304는환경에포함하고teacher256은학습0이다. 3modelworker각1150환경/768학습＋control600/0=합cap4050/2304,예정첫worker1020(증명12),나머지1008각/control544이다. ownerlock/시계/원장/seed/model별가중치·optimizer·RNG를분리한다. active3600초/model·reserve300,control1200·reserve120로과거예산초기화0이다.

세새학습seed를병렬로돌리며처음실제59학습부분중지·3Adam/partial/RNG 정확복원과12 native 초기Rule동형을검사한다. parentfreeze후확인만병렬로돌리고실제시작/실패도세어합산한다. PC공유호스트시간을휴대폰시간/전력으로해석하지않는다.

새policy/engine/controls/budget/ppo/targets/study 및test_d1_atc_delta.py는08소스를바꾸지않고작성했다. 순수6검사PASS: 동일궤적performanceδ정확0·동일t경계, signed E/AP/teacherP95단위,missing대조/P95거부,CAUSAL목적보존/newschema,teacher/Greedy/EFT온라인접근금지와n2입력거부,입력/예산/조건별guard다. 순수검사는환경/학습0이며실제우위는최종확인에서만판정한다.

근거는docs/results/atc_delta_20261012 검토,work/ATC-DELTA-REFINE-09 원장·입력·source/model SHA,산출물outputs/ATC-DELTA-REFINE-09다. 이번fit/APK/기기/S26/NPU 실행0·기존모든실행/실패/WIP/default/experiment_ready=false 유지다. 08원결과를보고09의목적가설을세웠으나08확인자료를09개발/학습에전용하지않는다.

## 최종 완료 기록 — 2026-10-12

실제3,580환경/2,304학습/실패0·9모델각256/32update·최종480행을완료했다. 256 ATC teacher 환경은control예산에포함하며9모델공유·운영미래입력0이다. 개발조건별서비스/P95보호선정후부모freeze·새32확인·확인후재선정0이다. 대표 ATC_SCORE_DELTA_701@256은요청/원U/N/I0·실제teacher변경10병행이지만평균ΔJ-0.017488049214J/ΔAP-0.000199857567°C와ΔP95+11.943035969ms다. paired/single_due ID5/13/21/29의P95손해4/32,그외28동률. 모든9학습모델개정strictFAIL·채택0이며확인에맞춘추가튜닝0이다. Greedy별도비교군의선언U실패16/864는숨기지않는다. 6pure/partial59 exact/native proof12/전체raw/실제AVAILABLE/mask/SHA·IE/RL독립감사를완료했다. 원메타의seed복사/n1설명은별도ERRATA로정정하고등록/schema/SHA불변이다. 기기/APK/fit/S26/NPU0·원기본/experiment_ready=false 유지. 근거: results/atc_delta_20261012/RESULTS.md·ERRATA.md 및 ATC_PPO_ITERATIVE_RESULTS_20261012.md.
