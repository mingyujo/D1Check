# 후속 AI 검토 — 세션 중심화·자료 전이·검증 설계

AI 식별/검증 검토자이며 사람 전문가의 인증이 아니다. 현재대상은HEAD `29af09df041ae413aa547aa1df22d755b9b39a3f`와완료된 `energy_ap_zero_offset_01/run_v1`이다. 이노트만작성했다. 미커밋STATUS/PLAN/DECISIONS·RL소스/설정/출력/프로세스를수정·stage·재해석하지않았다. 이번작업은독립문서/코드/manifest읽기와state노출설계의작은rank/SVD산술이며새fit/모델평가배치/기기/ADB/빌드/테스트0회다.

## 1. 독립 1차 의견

**세션내상수baseline오차를제거하는중심화는추가한family로검토할가치가있다. 하지만새계수의예측에원pre50를쓰면C0와미래유휴baseline오차는그대로다.** 더많은자료와새추정법의효과도분리해야한다. centered13을개발4의기존p4와만비교하면무엇때문에달라졌는지알수없다.

완료된δ0후보의에너지개선은실제5fit결과이며앞선계수고정ablation과다르다. longLOAD공통J/AP구간의−23.060→−6.187J/AP .437→.173°C는유지한다. AP는동결LOAD_SLOW재사용이라신규AP학습/개선성과가아니다. 과거29 J5.522→5.144/10악화와C0불변/정책부호오판2/4를전체완료로바꾸지않는다.

### 중심화가 무엇을 식별하는가

고정5초창의관측J를 `y_sj`,네state노출초를 `x_sj`라하면가설은다음이다.

`y_sj = 5*B_s + x_sj·p + ε_sj`

같은세션에서각열/목표평균을빼면:

`y_sj−mean_j(y_sj) = [x_sj−mean_j(x_sj)]·p + [ε_sj−mean_j(ε_sj)]`

5초창이모두같은길이이면원pre50의상수오차도소거된다. training에서세션별자유intercept를흡수하는fixed-effects 추정과동등한구조이다. 배포/예측전역계수는p4만남지만통계적으로세션별level을소거했으므로'배경정보를공짜로식별했다/매개변수4라과적합이없다'고말하면안된다.

예측식은기존처럼 `E(lo,hi)=P50_s*(hi−lo)+exposure(lo,hi)·p`이고δ=0이다. 학습세션의post평균/B_s/nuisance추정치는예측입력으로쓰지않는다. heldout세션의target평균을빼서그림/contrast오차를보이는것은진단이지만실제forecast를그평균에맞춰보정하면누수다. 주요평가는원관측J와정규화하지않은미래/전체창잔차다.

중심화는시간에따라변하는drift나부하/순서와연동된잔열·OS·기록비용을제거하지않는다. macro의각state가다른시각에배치되면느린drift가centeredX와상관되어p에흡수될수있다. 공통p가상대부하효과를설명한다는제한가설이지GPU/CPU의인과W분해가아니다.

## 2. 개발13의 분모·가용 정보·사후 역할

| 원천·역할 | 세션 | fitting창 | 서로다른조건 |
|---|---:|---|---|
| 기존분리개발CPU/PAR/SER | 3 |35..120,세션별17개의5초창 |96개요청의분류32→탐지32→혼합32;기존순차수집/초기AP/준비 |
| history개발gap30 | 3 |35..120,17창 |conditioning96→고정회복30→C0/CPU/PARtarget |
| history개발gap180 | 3 |35..120,17창 |같은conditioning→회복180→C0/CPU/PARtarget |
| macro개발DEV_A/B/B/A | 4 |35..635,120창 |4state각60초·사이90초idle·긴baseline과다른기록경로 |

총개발13/633창이다. history C0두개는targetstate노출0이라centeredX=0이고p에대한정보가없다. conditioning을한historyC0는전체실행무부하대조가아니다. 전체분모/잔차진단에는포함하되부하정보를주는독립13개의완전반복으로세지않는다. 전력창633개도13독립세션의대체가아니다.

centered13로학습하면원archive29중olddev3+historydev6=9는새개발자료로이동한다. 새로운role분모는개발13+사후평가20(기존확인6+지속8+history확인6)+긴2=35다. 원zerooffset의archive29표는그당시모형의historical정의로보존하되새20평균과그29평균을직접비교하지않는다. 비교모형들을새20의동일ID/창에서짝지어다시보고한다.

평가20와긴2는추정에미사용해도이미봤으므로새blind확인이아니다. AP LOAD_SLOW도macro4에서개발했으므로에너지macroblock제외에서동결AP를재생했다고AP의blockholdout학습이성립하는것은아니다. source제외에너지와AP재생의evidence_stage를따로쓴다.

## 3. 실제 13 manifest의 실행 계약과 차이

기존 `joint_model_refinement_01/compatibility.json`은old9만의core같음/동일측정조건주장false를기록했다. 그bool을macro까지연결하지않고이번에원manifest13을독립직접읽었다.

- old3/history6는그compatibility의9개manifestSHA와일치하는외부 `separated_power_run_v1/v2/v4`의적격출처및 `energy_ap_history_recovery_run_v7/primary`의원manifest를선택했다. 중단prefix나중복artifact를추가세션으로세지않았다.
- macro4는소비된 `energy_ap_resident_identification_plan_v3/collection_plan.json`의실행root4개 `input_manifest.json`에서읽었다.
- 13전부 devicefingerprint동일(값은내보내지않음),CPUthread1,모델키4개동일이다. 모델별 `model`, `runtime`, `tensor`, `input`, `execution`, `comparator` 객체는13전부동일했다. LiteRT1.4.2/XNNPACK/기존GPU설정/정규화·tensor·deterministic입력등core가일치한다. 다른task/backend pair를합치지않는다.

| manifest조건 | old3/history6 | macro4 |
|---|---|---|
| APK |old `5c284190…`/history `3840bfb1…` |`57d2320c…` |
| baseline |30초 |120초 |
| common/cooling |120/60초 |600/180초 |
| power_sample_period_ms |900 |900 |
| power_sampling_version |`online-power-phase-audit-v1` |`resident-identification-power-v1` |
| 프로토콜 |`arrival-energy-synthetic-v1`,history추가opt-in |`energy-ap-resident-identification-v1` |
| 준비·이력 |history는conditioning/gap·trace추가 |native적격성·긴등록macro/250mscadence |

**모델실행core가같지만동일측정조건은아니다.** history의trace/host/log규칙도다른초기이력과기록비용을만든다.900ms가같다는이유로기록version/부하주기/전체전력의해석이완전같다고선언하면안된다. centeredintercept가이차이를모두상수로흡수한다는것도미확인이다.

원점·실제lane반환·전류조건부단위·midpoint/bracket·coverage/원자료검증의의미가같은지는pool전필수gate다. 실행core/tensor/backend/CPU/resident 또는관측target/시간의의미가깨지면13pool을차단한다. 반면baseline길이/로그version문자열이달라도같은조건이라고가장하지않고**여러프로토콜로전이하는공통유효p4라는실험가설**로사전명시해검사할수있다. 만약동일baseline·동일측정version을hard동등조건으로요구하는계획이면현재13은그조건을통과하지못한다.

## 4. 추정 없는 작은 설계행렬 산술

actualstate노출만읽어5초X를만들고세션열평균을제거했다. y/postpower계수fit/optimizer/예측은호출하지않았다. 각세션weight는 `1/sqrt(n_s*K)`로고정했다. column정규화조건수는규모를숨기므로실용적식별판정으로쓰지않는다.

| centeredX 묶음 | 세션/행 | rank | column정규화조건수 |
|---|---|---:|---:|
| 전체13 |13/633 |4 |1.1983 |
| old3만 |3/51 |4 |1.3294 |
| history6만 |6/102 |4 |5.6194 |
| macro4만 |4/480 |4 |1.2947 |
| old3제외 |10/582 |4 |1.2669 |
| history6제외 |7/531 |4 |1.3083 |
| macro4제외 |9/153 |4 |1.4569 |

13개의전체세션LOSO design도모두rank4였다. 개별historyC0는rank0,historyCPUrank2/PARrank3,macro각세션rank4다. 모든시간에4active상태의점유합이항상같으면중심화후공통수준방향이사라져rank3이될수있으나이번에는idle변동이있어그완전공선성은없다.

historyPAR의GPUsolo노출은각0.470975/0.547286초로900ms기록주기보다짧다. norm으로열을확대하면rank4가나와도실제전력식별정보가충분하다는뜻은아니다. old3GPUsolo는PAR9.999043/SER15.002537초,macro는각약60초로정보공간이다르다. macro제외계수와legacy점수가크게변하면그상태의전이를미식별/불안정으로남긴다. rank가있다는이유로추가계수/τ/정확도PASS를만들지않는다.

## 5. 두 동료와 실제 교차토론

독립1차핵심을root/에너지·열AI/시뮬레이터·정책AI에먼저보냈다. 이후직접교환한반론과교정:

1. **에너지·열AI:** 상수level편향의근거는있지만drift/state상관은남는다. historyGPU정보가macro보다매우작고rank만으로공통p4를정당화할수없다. AP는macro개발자료에서최종고정본재생인점을별도표시해야한다.
   - 수용했다. nuisance소거는C0예측baseline개선이아니며AP새fit/새proxy주입을제안하지않는다. 원FROZEN도old3로개발된모형이므로old3제외대조를FROZEN의새blindCV로부르지않는다.
2. **시뮬레이터·정책AI:** old3/history30/history180/macro의4group제외+최종1이최소의유한source전이검사이며C0X0도평가분모에유지해야한다. group4는3프로토콜과history2gap이고4독립day가아니다.
   - 동의했다. 전체13LOSO를추가13fit로독립검증처럼붙일필요는없다. source별상호전이가우선질문이고5초rowrandomsplit은금지한다.
3. **root의반론:** centered13만개발4의기존δ0p4와비교하면자료확대효과와중심화효과를분리못하므로동일13의uncenteredδ0p4통제가필요하다.
   - 세AI모두수용했다. 처음의centered단일5fit안은**동일13자료의추정법2×(4group제외+최종1)=합계10fit상한**이라는후속사전안으로교정했다. 이번실제fit은0이다.
4. **내계약반론:** actual13에서baseline30vs120/samplingversion차가확인됐는데동일측정계약이라고pooling할수있는가?
   - 정책AI는900ms동일=동일조건주장을철회하고core/target의미를hardgate,prep/log차이는명시한source전이가설로분리한다고답했다. version이target정의/공개시각을바꾸면pool을중단한다. 그차이를intercept가흡수했다는인증은하지않고실패후fold/weight를다시고르지않는것에합의했다.

## 6. 가장 작은 후속 후보와 사전판독

추천은새에너지예측family를여럿만드는것이아니라**같은원pre50+δ0+p4 식을같은개발13에서일반LS와세션중심화LS로추정하는한대조연구**다. 계수비음수,세션균등weight,동일5초창·원단위/실제점유·모델출처를고정한다. centering에는partial꼬리/냉각끝/조건에맞춘cutoff를추가하지않는다. 비음수p라도centeredX/target자체는양음가능하며이를clipping하지않는다.

사전gate:

1. hard실행/target계약확인·중복/role/원hash·13roster고정. sourcevariant차이를숨기지않는다. 관측의미가정렬되지않으면fit없이차단한다.
2. 네sourcegroup `old3/history30x3/history180x3/macro4`를고정한다. history둘은초기회복이력stressgroup이고동일protocol의서로다른독립일자라는의미가아니다. 각제외fit에서trainingsession만의mean으로X/y를중심화한다.
3. uncentered/centered두경로각4group제외와최종1만실행하도록등록한다. 같은13/같은weight/같은제약이므로centered−uncentered가추정법차이,uncentered13−기존macro4후보가자료확대차이다. 과거zerooffsetfold와centered13fold의서로다른train분모를숨기지않는다.
4. heldout13은그룹제외모형으로원pre50와actual일정만예측한다. centeredtarget오차는보조진단이며principalJ오차를유휴mean에맞춰보정하지않는다. 최종13계수는개발in-sample값과명확히구분한뒤hash동결한다.
5. 사후평가20+long2에동결후2경로/원식/완료zerooffset를동일ID·동일창에서계산한다. 그자료로추정법/weight/fold/계수를재선택하지않는다.

평가지표는원계약창으로등록한다. 공통비교는0..120 및future35..120;macro/long은35..635·actualwork·residentidle·회복coveredprefix·AP/power공통관측범위를별도보고한다. 에너지signed/absolute/상대·phase별국소절대잔차합/상쇄와세션별최대악화를함께낸다. 둘센서coverage밖전체값은null이며동일prefix비교만허용한다. 600초/85초/전체냉각을한분모로합치지않는다.

개발group별평균이원모형보다어떤방향인지,centered가동일자료uncentered보다실제로나아졌는지,특정source/case만희생해평균이줄었는지우선본다. 모델차이가나더라도원raw=mA조건부/절대J미인증·같은block의숨은상태차를유지하며수치EPS를현실정확도허용폭으로쓰지않는다.

## 7. 실패·종료 조건과 AP의 경계

- rank부족/비양수초기전력/원점·coverage·role·hardcontract불일치면unavailable/차단으로끝낸다. 특정source/fold를제거해rank나점수를통과시키지않는다.
- 네group제외에서전이계수가흔들리거나같은group의absoluteJ/phase/최악세션이악화하면불안정/적용제한을보고한다. centered를uncentered보다우선채택하는개발규칙은결과전에고정하고,실패후그룹weight·bin길이·nuisance함수·부호/τ를조정하지않는다.
- p4예측은C0/무부하회복에효과0임을항등성으로확인한다. 이오차가남으면'중심화실패'와'예측baseline정보부족'을분리하되전체오차목표완료로처리하지않는다.
- AP는추가개선근거가없다. 기존LOAD_SLOW/원proxy/pre-onlyR/H/β/τ를고정하고APfit0으로유지한다. AP13/20/long에서새동일창짝표를만들수있지만똑같은AP곡선을계산한것은새AP오차감소가아니다. newp4를APproxy에넣거나session상수APoffset를post로맞추는새family를붙이지않는다.
- Aactual비용/저장B일정비용을분리한다. B미기록case는actual미래일정으로채우지않는다. 저장B17에는새개발old3가들어있으므로evalB14와개발B3역할을분리한다.
- 같은sustainedCPU/PAR4짝의J차이/부호와AP차이오차는전체J평균개선과별도로보고한다. 2/4부호문제가남으면정책판별미완료이고,줄어도작은순차4쌍으로인과정책우월성을확정하지않는다.
- 기존AP/비용API의macro6guard를개발13이증가했다는이유로넓히지않는다. 분석상diagnostic계산과실제허용API범위는구분한다. 신규개발자료를지원사례로추가하려면사전자료계약/예측검증이별도다.
- 위유한2경로판독을끝내면이후추가후보/fit/실측을자동연쇄하지않는다. centered의제한적효과가없으면미채택으로종료하며동일계수의더많은반복을성공보장해법으로제안하지않는다.

## 근거·현재 판정

주근거: `docs/ENERGY_AP_ZERO_OFFSET_RESULTS_20261010.md`, `tools/d1_energy_ap_zero_offset.py` design/train/evaluate/windows, `docs/results/energy_ap_zero_offset_01/registration.json`, `run_v1/development_residual_preflight.csv`, `run_v1/paired_errors.csv`, `run_v1/fit_receipt.json`.

개발/이력근거: `docs/MODEL_REFINEMENT_EXISTING_DATA_20261007.md`, `docs/HISTORY_MODEL_REFINEMENT_RESULTS_20261008.md`, `docs/ENERGY_AP_HISTORY_CONTROL_DESIGN_20261007.md`, `docs/RESIDENT_IDENTIFICATION_PREP_20261008.md`, `docs/results/online_policy_study_01/separated_power_final/README.md`, `history_control_plan_01/run_v7/{sessions,physical_sessions,physical_runs}.csv`, `joint_model_refinement_01/compatibility.json`.

작은설계산술입력: `model_refinement_01/inputs.json.gz`, `history_model_refinement_01/inputs.json.gz`의개발role9와중복sustained제거분모, `resident_identification_run_01/recorded_v3/inputs.json.gz`의개발4. actual5초노출633행/4열중심화후rank/SVD만계산했다. 계수/powertargetfit은호출하지않았다.

13manifest독립대조: 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_run_v1/v2/v4`, `energy_ap_history_recovery_run_v7/primary`, `energy_ap_resident_identification_run_v3`의적격원manifest. old9는기존compatibility의원hash9개로선택했고macro4는소비plan_v3의실행entry로선택했다. model/runtime/tensor/input/execution/comparator직접동일성·CPU1/4resident·관측variant차이를확인했다. fingerprint원값은기록하지않았다.

**판정: 한중심화가설과동일13자료의비중심화대조를고정한후속PC연구는조건부로타당하다. 실행core는일치하지만동일측정조건은아니며공통p4의프로토콜전이를검증해야한다. AP새개선·C0해결·범용도착지원·정책우월성을이후보로전제하지않는다. 이번새fit/배치/기기0이며후속등록10fit안은미실행이다.**

## 추가 root 반론 — AP를 고정만 하면 새 AP개선은 없는 문제

위1차의'AP새계수추가근거없음/동결유지'에root가정확한새가설을제시했다. **원LOAD_SLOW의동일linear5basis(고정preinit+fast4+oldproxy slow1)를쓰되β/preparationτ30/slowτ1920를모두고정하고개발13에서계수5만일반/중심화추정하는별도head**다. 새에너지계수를열proxy에주입하는안이아니다.

이구체화에따라**초기의APfit0유지만을최종권고로고집하지않고,새AP5계수head의단일가설검사를조건부허용하는쪽으로수정한다.** 준비초기화의level오차가부하반응계수에흡수되어다른프로토콜로전이되지않는가라는목적이있다. 원식과별도버전으로등록하고불확실성/실패종료를지키면목적없는열계수탐색이라고일괄기각할이유는없다. 아직오차감소의성과나실용적식별근거는없다.

### 정확한 target·예측·학습 자유도

`AP_sj=A_pre,s(t_j)+X_AP,sj·θ`, θ는fast4/slow1의비음수5계수다. 중심화해야할목표는 **`AP_observed−A_pre`의residual**이며X_AP도같은세션의열평균을뺀다. APobs만중심화하면서A_pre는원수준으로두면기존식과다른모형이된다. 각AP세션의동일원query/pointwise가중과같은pre-only초기화를사용한다.

예측은원pre-only R/H와마지막AP를그대로전파해 `A_pre+X_APθ`이며postν/target평균을더하지않는다. 학습에서소거한각세션의ν_s는freelevel변동을허용한training효과이므로13개ν에해당하는학습자유도를공개한다. 에너지도세션level13개를흡수하고AP도13개를흡수한다. inference의전역계수가4+5개라는것과trainingfixed-effects의level자유도는다르다. 이것을측정된주변온도/내부열/기기배경W의식별이라고말하지않는다.

β/slowτ/prepτ/기존전력proxy/사전초기화창을재탐색하지않고기존head/자료byte를보존한다. 새APhead는newversion으로선택적으로호출하며기존frozen이나RL/strict지원범위를변경하지않는다.

### fit없는 AP rank 정보와 실용성 한계

root와에너지·열AI가각자target-free exactbasis만으로rank를확인했다. 나는같은APbasis를다시생성해반복검사하지않고그들의수치를제공자근거로표시한다.

- root: 전체13/네source제외에서일반rank5(조건수약1.804–3.627),중심화rank5(약1.397–2.730).
- 에너지·열AI: 전체13 일반조건1.815927/중심화1.396883,macro제외old9 일반3.626674/중심화2.730459. centeredslow norm의전체75.3567 대비old9 19.5657로slow정보제곱량의약93.3%가macro4에기댄다.

rank5라선형coef가계산될수있다는조건은충족했지만short프로토콜에서τ1920의긴열memory가실용적으로식별/확인됐다는뜻은아니다. 그τ는원macro자료에서사후선택된기존상한값이다. macro를coef훈련에서제외해도τ/기존basis선택에macro가쓰였으므로**완전OOF 물리검증/새독립AP확인**이라는label을붙이면안된다. inheritedbasis가고정된상태의조건부coefficient전이검사로표시한다.

### 동료의 직접 반론·정정

- 에너지·열AI는centeredloss가경로level평균을버리므로shape점수는좋아도초기화의절대offset는남거나더나빠질수있다는반론을냈다. 이반론을수용하고절대AP경로MAE/최대/피크/가열·냉각방향을주판독으로둔다. centeredshapeRMSE만으로새APhead를채택하지않는다.
- 내가두동료에게levelconfound목적을명시하면APhead는조건부허용가능하다고질의했고,시뮬레이터·정책AI는기존'AP고정이니추가감소불가'라는견해가새θ별도등록으로해소됨을인정했다. 관측−init의중심화/negativeX,target를clipping하지않되θ비음수/heldoutν미입력/원basis고정에합의했다.
- 같은AI는J와°C를새가중α로합치는jointloss나평가22에서네head조합을탐색하지말고,개발source제외점수에서head별추정법을한번고정하는것을권했다. E와AP각각개발에서고정한규칙에따라일반/중심화/원유지를결정할수있지만fold마다우승방법을섞은최저점수모형은만들지않는다.

### 변경된 유한 후속 설계·실패종료

새계획은같은개발13/네group제외+최종1,동일시계/5초에너지창/AP원query/세션weight/coef제약하에서 **추정법2×head2×5=정식fit 최대20회**라는미실행제안이다. 이는head학습최대수이며이번실제E/APfit은0이다. active-set계산을최적계수나τ를더찾는여러family로연쇄확장하지않는다.

E/AP각head의raw절대오차·source별최악/평균/phase/방향개발규칙을결과전에동결한다. 개발제외에서방법을고정한뒤최종계수/선택hash를봉인하고이미본평가20+long2에서재fit/재선택하지않는다. raw절대J/AP가동시에좋아지는것은같은창의새공동표로판독하며한head만개선되면전체두head새오차감소개선완료라고하지않는다. 실패head는원동결/미지원으로남겨야한다.

historytargetC0의fast4/slow1 basis는0이며A_pre가고정이다. 따라서AP계수5로도C0경로는바뀌지않는다. E의C0항등과함께검사해nuisanceν를예측에몰래더해C0를'개선'하는누수를차단한다. C0/반복성/정책차이/실기기전체목표의잔존한계를완료조건에서삭제하지않는다.

## privacy-safe 13 계약 증거 산출

root의추가명시요청으로노트외에 `native13_contract_audit.json`을작성했다. 이미읽었던적격13manifest의작은계약객체를직렬화한증거이며다른raw센서/실측감사를반복하지않았다.

- SHA256: `19a95e24ccccb48f05e8242408cde9d4b686d5ad5afabd821a5275971bd6467d`.
- 내용:caseID/sourcegroup/inputmanifestSHA/expectedinventorymatch/core내용canonicalSHA/CPU1/4resident/model-field동일성/APK/baseline/common/cooling/samplingversion/cadence/참조inventory문서SHA.
- core는model/runtime/tensor/input/execution/comparator와CPUthread/residentkey만canonicalUTF8JSON으로hash했다. `device_identity_equal=true`만남겼고실제fingerprint/serial/IP/기기identity값은기록하지않았다.
- old9는기존compatibility의원manifestSHA목록과actualbytehash9개대조,macro4는recorded_v3 inventory의manifestSHA와대조했다. `core_execution_equal=true`, `same_measurement_conditions=false`를둘다명시한다. 동일core가곧동일계측프로토콜이라는주장은0이다.

**수정된최종의견: 실행/관측target의hard계약과명시적source차이를보존한뒤,같은13의일반/중심화 E4+AP5를최대20fit로유한하게판독하는제안은조건부타당하다.** θrank가능성과새AP목적은있지만coefficient전이/전체오차감소성공은미확인이다. τ/β선택의사후이력·C0불변·source별악화·사후22평가를보존하며새독립확인/범용도착/정책우월성으로승격하지않는다. 이노트와명시요청auditJSON외파일은수정하지않았고새E/APfit·기기·배치는0회다.
