# 세션 내 대조 전력 추정 — 실행 모형·계측 AI 검토

2026-10-10. 사람 전문가 검증이 아닌 저장소 코드·자료 기반 AI 검토이다.
착수 HEAD `29af09df041ae413aa547aa1df22d755b9b39a3f`, branch `feature/arrival-scheduling-20260923`.
다른 RL 작업의 STATUS/PLAN/DECISIONS·소스·출력을 보존한다. 이 노트 외 수정 없음. 신규 fit/기기/ADB/실측/정책 배치0.

## 독립 round1 판정

**세션 내 중심화는 다음 한 family로 검토할 근거가 있다.** 배경오차의 세션별 상수분을 상태계수에 흡수시키지 않는 점에서 기존 δ=0/p4 재추정과 다르다. 그러나 세션 내 시간변동·상태와 동반되는 관측부하를 분리하지 못하며, 예측에 pre50만 쓰는 한 무부하/장기회복 오차와 AP의 기존 악화를 해결하지 못한다. 개선은 미검증이다.

### 현재 완료본에서 확인한 근거

`docs/ENERGY_AP_ZERO_OFFSET_RESULTS_20261010.md`와 `tools/d1_energy_ap_zero_offset.py:36`의 실제 완료본은 개발4의5초bin에서 `observed_J−5·pre50`을 target으로 삼고 상태노출초4열만 적합했다. 최종p4는 .807621/.720310/.397905/1.099416W다. LOAD 같은창J−23.060→−6.187J, AP .437→.173°C지만 archive29 J악화10, C0/유휴·정책부호2/4는 남는다.

저장된 `development_residual_preflight.csv`와 완료p4로 계산한 기존후보 잔차평균은 다음과 같다. 새 nuisance계수를 적합하거나 예측에 쓴 값이 아니라 이미완료한모형의 잔차 기술통계다.

| 개발세션 | 전체등록bin 평균 잔차 W | 순수유휴bin 수 | 순수유휴 평균잔차 W |
|---|---:|---:|---:|
| 00 | +.009415 | 69 | +.012806 |
| 01 | +.046019 | 68 | +.041866 |
| 02 | +.080467 | 69 | +.107879 |
| 03 | −.078246 | 69 | −.072847 |

세션별 잔차수준의 부호와크기가다르고, 유휴에서도 유사한수준차이가 남는다. 현재계수에세션배경수준오차가섞일가능성을검토할직접근거다. 이표가배경의원인이나상수성을증명하지는않는다.

### 정확한 식과 식별 경계

각세션j,동일5초bin k에 대해 `f_jks=exposure_jks/5`, `y_jk=observed_J_jk/5−pre50_j`라두면훈련가설은

`y_jk = b_j + Σ p_s f_jks + ε_jk`, `p_s≥0`이다.

`ỹ_jk=y_jk−mean_k(y_jk)`, `f̃_jks=f_jks−mean_k(f_jks)`로둘다중심화하면b_j가소거된다. pre50_j도상수이므로target에서정확히소거된다. 예측식은여전히 `E=P_pre50·duration+Σp_s·actual_exposure_s`이며훈련에서얻은b_j는미래입력에넣지않는다.

이는세션별signed intercept를훈련에허용한fixed-effect추정과동일하다. 모델예측계수는4개라도훈련의nuisance 자유도를숨겨서는안된다. 중심화된특징과target은음수가될수있으며0으로clipping하면위동등성이깨진다. nonnegative제약은p_s에만적용한다.

상수배경편향에는강하지만실제배경이`b_j(t)`로변하고상태노출과상관되면편향이남는다. macro의순차block,열이력,request/cadence와관측부하의차이는시간상수나ambient를만들지않고도교란이될수있다. 숫자rank는이인과분리를증명하지않는다.

### 기존 개발13의 역할과 정보량 — fit 없이 확인

두공유archive번들의role=development9(기존3+이력6)와macro4를ID로분리해읽었다. 기존확인6+이력확인6+지속8+긴2는개발로승격하지않는다. 지속8은두번들에중복되지만개발13에는들어가지않는다.

| 묶음 | 세션 | 훈련가능등록창 | 특징/전이 경계 |
|---|---:|---|---|
| 기존3 | 3 | 35..120,5초17bin | CPU/PAR/SER96도착; APK5c284190…; conditioning이력동일아님 |
| 이력30 | 3 | 35..120,5초17bin | conditioning96후회복30; C0/CPU/PAR; APK3840bfb1… |
| 이력180 | 3 | 35..120,5초17bin | conditioning96후회복180; C0/CPU/PAR; 동일이력variant |
| macro4 | 4 | 35..635,5초120bin | DEV_A/B/B/A,상태60초block·idle대조; APK57d2320c… |

이전9개manifest호환성기록은기기·모델/텐서/정규화·runtime/CPU1/GPU구성·sampler900ms·resident조건이같고APK/준비이력이달랐다고명시한다. macro4도같은핵심모델/입력/CPU1·resident4를쓰지만긴등록macro와전이관측이다. **공통계수의프로토콜간전이가설로는사용가능하나13개를동일조건반복이라고묶을수없다.**

훈련계수계산없이5초상태노출비율을세션별중심화해rank/SVD만확인했다. 세션당bin수의역제곱근으로가중해긴macro가표본수만으로지배하지않게했다.

| 묶음 | 중심화설계rank | 정규화조건수 | GPU단독 점유 합 초 |
|---|---:|---:|---:|
| 기존3 | 4 | 1.3294 | 25.0016 |
| 이력6 | 4 | 5.6194 | 1.0183 |
| macro4 | 4 | 1.2947 | 240.3976 |
| 전체13 | 4 | 1.1983 | 266.4175 |

이력GPU열의세션균등중심화정보대각합은 .000505,macro는 .358693으로약710배차이다. 이력만의GPU단독W는rank4여도불안정하다는기존반례와일치한다. 두이력C0의설계는rank0이므로p4식별에는기여하지않지만nuisance의시간변동/음성대조에중요하다.13센서세션이독립반복의균질표본13개가되는것도아니다.

### 다음 한 family를 검토할 조건

하나의centered-p4 family만사전등록한다. 독립적으로검토가능한정보는13개개발의동일5초빈·실제점유·전력target이며평가자료를들여다보고window/τ/seed/후보를늘리지않는다. 세션균등가중,4source block(기존3/이력30/이력180/macro4)제외와전체최종의유한추정절차가필요하다. macro전체제외시GPU정보가작아지는상태를성능실패와별도로식별한계로보고한다.

현재한프로토콜범위를최우선으로삼는다면macro4에서중심화만달리한후보가더직접적인대조다.13개풀링은기존29전이개선까지목표로삼는가설이며,분모증가만으로정당화하지않는다. **이훈련범위선택은성과를본뒤고르는hyperparameter가아니라root가다음등록전에정해야할목표선택이다.** 이번에는어느쪽도fit하지않았다.

`docs/JOINT_MODEL_REFINEMENT_RESULTS_20261008.md`의이전개발9pooled-p4+AP재fit은구개발제외J4.169→17.377/정책차이6.322→8.730으로실패했다. 새centered추정은상수배경nuisance를빼는새가설이므로그실패를자동전용하지않지만,단순자료13개추가만으로성공할것이라고도하지않는다.

예측에서는nuisance사용0/AP새전력proxy주입0/기본·RL교체0을유지한다. 동일창J/AP,energy5·10초국소잔차/상쇄·registered600/covered회복·정책차이·저장B를함께보고한다. C0와회복은state exposure0이라여전히개선불가이며AP는고정LOAD_SLOW의기존성과/악화를그대로재사용한다. 새로운energy추정성과를새AP학습성과로쓰지않는다.

### 대안과 반론

더작은대안은**macro동일세션의등록active block 대 인접idle block 전력대조**로state별유효increment를검토하는것이다.4상태가각각충분한점유/idle대조를갖는다는식별근거는있다. 하지만GPU60초/CPU낮은duty처럼노출비율차이를정확히분모로쓰고원phase경계/전후idle을미리정해야하며,인접idle의잔열·상태후관측비용을baseline에흡수할위험이있다. 창선택자유도를추가하므로**현재root제안의전체동일bin중심화보다우선추천하지않는다.**두family를동시에fit하자는뜻이아니다.

동료에게묻는반론은(1)13프로토콜의level차이만뺐는데state×protocol차이가없다고가정할근거가있는가,(2)C0/time-variable idle에는p4가작용하지않으므로전체두출력목표의어떤부분이여전히미해결인가,(3)유한4block-exclusion중macro제외GPU실용식별과전이실패를어떻게구분할것인가다.

round1은여기까지독립판정이다. 후속직접토론으로바뀐권고는아래에기록한다.

## Round2 — root의 동일자료 대조 반론과 동료 토론

root의추가반론을수용했다. **centered13을현재macro4계수와만대조하면자료확대와중심화효과가혼동된다.** 따라서round1의macro4만중심화하는최소대조안보다,목표가기존다중조건전이라면동일13개발의두추정법을고정비교하는설계가더적절하다. 이것은이번실행승인이아니며지금fit은0이다.

### 제한된 다음 비교 설계

- 신규목표추정법: session-centered p4 하나. 필수대조: 같은13개발의uncentered δ0/p4. 같은pre50/실제state노출/5초energytarget/세션균등가중/비음수p4/기존AP고정이다. 자료추가효과는기존macro4완료모형→uncentered13,중심화효과는uncentered13→centered13으로분리한다.
- 4sourceblock는old3/history30x3/history180x3/macro4다. 각추정법의4block제외+최종1로**추정법2×5=최대10fit**인유한등록을권고한다. thirteen-LOSO나추가grid/후보/결과후window수정은포함하지않는다. '한family'라는이름으로대조의실제5fit을숨기지않는다.
- energy단위는기존과같은J/노출초로통일해 `Y=observed_J−5·pre50`, `X=exposure_s`의세션평균을뺀다. round1의meanpower/fraction 표현은정확히5로스케일한동일식이지만훈련MSE단위/로그가달라지지않게등록식은하나로고정한다.
- 원 `d1_energy_ap_zero_offset.design()`는macro DEV_A/B만허용한다.13개발을쓰는새경로는별도registration/roster/권한있는개발역할검사로구현해야하며기존API의허용scope를조용히넓히지않는다.

### 자료 역할과 비교층위

원archive29의old3+history개발6은이새family의개발9로명시적으로사용한다. 따라서원29평가를그대로독립평가라고쓰기불가하며**추정미사용평가20+긴2=22**로표시해야한다. 전부이미열람한사후평가이고미사용이fresh blind확인을뜻하지않는다. 같은분모20에기존완료모형/원모형점수를다시배열해대조해야한다.29mean을20mean과단순대조하지않는다.

에너지의신규4block제외와이전macro4의4session-LOSO는heldout학습조건이다르므로절대수치만나란히두어같은CV라고하지않는다. 원FROZEN전력계수는old3로이미개발됐고현재δ0후보는macro4로이미개발됐다. 해당source제외fold에서이두참조모형은새훈련법과같은independent out-of-fold모형이아니다. centered/uncentered두새추정법의같은fold대조가핵심이다.

고정LOAD_SLOW도macro4로학습했다. macro제외energy평가에서그AP값은고정최종모형의in-sample재생이므로energyblock-exclusion의AP독립확인으로해석하지않는다. 신규APfit0/AP전력proxy교체0을유지한다. 비용식의두head를분리한상태로모든같은창결과를보고한다.

정책검토자가지적한storedB17에서도old개발3은새energy훈련에들어간다. B비용평가는추정미사용14와old3의개발/해당fold기록을분리한다. B는이미저장된forecast일정의비용투영이고service모형자체의과거학습/응답오차를새로검증한것이아니다.

### 두 AI에게 직접 제기하고 받은 반론

identification 검토자는중심화가상수nuisance를제거한다는수학과전체design rank4/cond1.198에독립적으로동의했다. '공통p4'가정은protocol×state전력차이를제거하지않으며GPUsolo희박성때문에rank만으로전체13풀링을인증할수없다는반론도일치했다. 저는historyGPU정보 .000505 대macro .358693의차이와훈련role변경/AP고정in-sample경계를전달했다.

정책검토자는동일13비중심화대조가필수라는root반론을수용했다. C0/유휴와순차짝의baseline차이는centered p4로해결되지않으며,동일source-exclusion에서정책차이/5·10초/긴matchedAP창/B14를함께보고해야한다고답했다. 저는시간변동과state의공분산이남으면δ(t)/새τ로즉석확장하지말고한family의실패로종료해야한다고반박·동의했다.

### 풀링 전 필수 gate와 현재 확인 수준

원9의 `compatibility.json`과macro6의이전직접manifest대조는각범위내core동일성을보인다. **그둘을서로연결해13개전체core계약의값동일성을자동인증해서는안된다.** 다음등록전에기존13manifest의model/input/CPUthreads/runtime/GPUprofile/resident/cadence/전류단위·사전clock조건을필드로연결해비교해야한다. APK/준비이력/등록도착·macro차이는별도variant이며동일계측claim으로승격하지않는다. 단위raw=mA는동일조건부가설이지절대J인증이아니다.

제가이번에13manifest를모두새로감사하지는않았다. identification 검토자에게이cross-source핵심값확인담당여부/근거를직접질문했다. 답이오기전에는이gate를**풀링전필수·현재추가확인미완료**로표시한다. 과거감사PASS를이번새훈련계약의PASS로전용하지않는다.

후속직접응답에서identification 검토자가13개실행native manifest를새로대조했다고보고했다. old9는이전compatibility의9manifest SHA에일치하는separated_power_run_v1/v2/v4 및history primary manifest,macro4는plan_v3실행input_manifest다. model/runtime/tensor/input/execution/comparator 객체는13개가동일하고CPU1/기기/resident4도같다. 이문장은그검토자의새직접조사근거이며제가13원본을중복감사했다는뜻은아니다.

동시에차이도확인됐다. old/history는baseline30/common120/cooling60, `online-power-phase-audit-v1` sampler900ms이고macro는baseline120/common600/cooling180, `resident-identification-power-v1` sampler900ms/cadence250이다. APK도5c284190/3840bfb1/57d2320c의세variant다. **동일baseline+동일sampling-version을hardgate로삼으면13풀링은차단된다.** 핵심실행객체를공통으로두되프로토콜별배경·점유대비가전이될수있는가라는가설로시험한다면차이를명시한soft variant 등록이필요하다. 단위는동일raw=mA조건부loader의가설이며실기기13전체의절대단위가인증된것은아니다.

### 성과 판정·종료 조건

입력/roster/단위/소스불일치,중심화오류,rank붕괴면fit전에중단한다. 노출이희박한source제외fold가나쁘다고그fold를빼지않는다. center가동일자료uncentered의개발block대조를개선하지못하면이미본평가20/긴2의좋은subset로선택을뒤집지않는다. 개발에등록한선택규칙을평가후바꾸지않는다.

비교결과는같은창J/AP의signed/absolute/max,5·10초국소잔차·양/음상쇄,등록600/작업후유휴/덮인전체회복,모든source평가층,CPU/PAR짝차이오차·부호와B14를포함한다. 신규candidate효과는기존기준대비개선뿐아니라동일13대조대비효과도표시한다. 수치rank/낮은평균J가정책순위나실제에너지절감인증이되는것은아니다.

새추정이성공해도**p4-only라는구조상C0와작업후순수유휴에너지오차는개선할수없고AP는이전고정값이다.** 따라서한family의세션수준편향완화여부를검토할수는있지만두출력의전기간문제가완전히해결된다고합의하지않았다. 차라리결과를정직하게분리하고새정보가필요한부분을남기는것이현재자료의한계에맞다.

더작은인접idle대조대안은등록창자유도와잔열혼입이늘어이번추정법과함께추가fit하지않는것을추천한다. 지금까지신규fit/환경배치/기기/원자료수정/RL변경은모두0이다.

## Round3 — 같은 LOAD_SLOW basis의 AP 계수 재추정 질문

root의반론을수용한다. 사용자의목표는J뿐아니라AP오차를더줄이는것이며고정AP의이전성과재사용만으로는새AP개선이없다. **기존정확basis를고정한5계수의개발13재추정은검토가능하다.** 현재에너지계수를APproxy에주입하거나새τ격자/ambient/물리상수를만드는안과는다르다. 성능과일반채택은미검증이며무조건이개정을추천하는것은아니다.

### 그대로 고정해야 하는 식

기존 `tools/d1_ap_tail_identification.py:20`의 `bases()`를읽고그함수로design만계산했다. predictor입력은pre/q/실제state일정만화이트리스트로넘겼고postAP/관측전력target은계산에넣지않았다. 기존pre-only R/H초기화계산을그대로재사용했지만새head계수나nuisance를적합하지않았다.

`T_j(q) = I_j(q;pre) + Σ a_s D_js(q;beta) + c K_j(q;tau,oldpowerproxy)`다.

- `I_j`는기존pre-only 초기경로다. beta=.045932520308001434/s, preparation tau30초가고정된다.
- D의4fast basis와K의slow basis를그대로사용한다. slowtau1920초가고정된다.
- K의구동은원SHA5682082a…의전력4계수proxy다. 신규에너지p4는주입하지않는다.
- 새추정미지수는a_s4개+c1개,모두비음수다. τgrid0/βgrid0다.1920을물리적으로식별된τ라고부르지않는다.

uncentered학습target은 `r_j=T_observed,j−I_j(pre)`, X_j는D4/K1이다. centered는**r_j와X_j를각세션평균으로같이중심화**한다. rawAP만중심화하고I_j가상수라고빼면같은식이아니다. I_j는시간경로이므로정확한차이target을먼저만들어야한다.

centered가제거하는것은세션별상수AP잔차nuisance다. 예측은계속I_j+원rawX_j·θ이며훈련nuisance/실측postAP평균을예측에넣지않는다. centered loss는경로의평균수준을버린다. 따라서형태변화는잘맞아도그수준이pre초기화에서틀리면**절대APMAE/피크가더나빠질수있다**. 목표가절대온도경로이므로delta-MAE나centeredtrainingMSE만낮아지는것을성공으로삼을수없다.

### fit0 design-only 확인

개발13의실제post35query 1,676개에동일basis를만들고세션당query수의역제곱근가중을적용했다. 그후matrixrank/SVD만계산했고계수최적화는호출하지않았다.

| 훈련대상 | uncentered rank/정규화조건수 | centered rank/정규화조건수 |
|---|---|---|
| 전체13 | 5 / 1.815927 | 5 / 1.396883 |
| old3 제외 | 5 / 1.809102 | 5 / 1.400554 |
| history30 제외 | 5 / 1.804099 | 5 / 1.418712 |
| history180 제외 | 5 / 1.804129 | 5 / 1.419816 |
| macro4 제외 | 5 / 3.626674 | 5 / 2.730459 |

각macro세션은rank5이고old/history단독세션은해당노출상태에따라rank3/4다. 두historyC0는D/K가전부0/rank0이다. C0에서는어떤5계수를추정해도AP경로가I_j와같으므로그오차를줄일수없다.

중심화후slow column의세션균등가중L2 norm은전체75.356706,macro제외old9는19.565672이다. 따라서그열의제곱norm약93.3%는macro4에서온다. 이것은정규화전열크기의기술통계이며Fisher정보·fast열에대해조건부인slow실용식별값은아니다. **좋은정규화조건수가다자료slow전이를인증하지않는다.** old/history의AP관측끝은약178–180초,macro는약813–815초라지평도다르다. 장시간긴2를학습에추가하거나1920상수를다시선택하지않는다.

pre-only기존초기화의정규화조건수는5.7576..6.3096이다. rank극단붕괴의증거는없지만,pre초기열이력·유휴기준이모든미래조건에맞는다는증명도아니다. 중심화는초기화의시간경로편향이나프로토콜별state반응차이를자동제거하지않는다.

### 유한 비교와 증거역할

동일13의uncentered/centered두방법에에너지head4계수와APhead5계수를각각연결할수있다. source4group제외+최종1을동일하게적용하면**2방법×2head×5=정식최대20fit**이다. basis/τ확인은headfit이아니며이번은정식fit0이다. 이횟수에원5energyfit이나과거APfit을섞지않는다.

예측계수는head별4/5이고centered훈련에서는세션별nuisance자유도가묵시적으로소거된다. 그훈련자유도를예측계수4/5뿐이라고숨겨서는안된다. 비음수제약은head계수에만적용하고중심화된target/features의음수는보존한다.

원전체35의표는학습자료재생13과추정미사용22(archive20+긴2)를분리한다. 모든자료가seenposthoc이다. 동일13비중심화대조가없으면자료추가효과와AP중심화효과를구분할수없다. 기존LOAD_SLOW는macro4로이미fit했으므로macro제외fold의참조AP점수는독립OOF모형이아니다. 신규두추정법의같은source-exclusion대조를기준으로판정해야한다.

개발group별동일창의절대APpathMAE·max/peak·냉각방향과같은창J/phase오차를보고선택규칙을평가전에정한다. head별잘맞는fold나평가subset을서로바꿔조합하면추정법2를넘는조합탐색이므로사전등록없는혼합은허용하지않는다. 평가22/긴2의성적을본뒤head·τ·창·손실·지원scope를바꾸지않는다.

예측API에서는고정AP후보의이전독립긴확인성과와새AP재추정의사후전이성과를별도버전/hash로표시한다. 새계수로나빠질가능성이있는원개발/과거13악화조건·긴LOAD도모두보존해야한다. 좋은등록LOAD만남겨AP전면개선이라고하지않는다.

### 동료에게 직접 보낸 질문

identification 검토자에게동일rank/SVD를전달하고,평균수준을버리는AP중심화가절대AP오차를더키울수있는반론과macro slow지배93.3%를어떻게판정할지질문했다. 정책검토자에게20fit유한비교의타당성과head별선택/조합이평가후탐색으로확장되지않게할규칙을직접질문했다. 회신/수렴내용은다음문단에추가한다.

두동료모두기존basis의다자료계수재추정이라는목적에조건부동의했다. identification 검토자는**beta/preptau/slowtau/원전력proxy가이미old3/macro4를써서결정된prior**라는추가반론을보냈다. 이를수용한다. macro제외나old3제외의새AP계수예측도이번θ5의고정basis조건부OOF이지,τ선택/전체family의완전독립OOF가아니다.13공동학습이물리τ를새로식별했다고하지않는다.

두historyC0의design이정확히0이므로두head의어떤계수도C0경로를바꾸지않는항등검사를다음구현gate에넣는다. 이를scope를줄여문제완료로바꾸지않고이번family가개선할수없는부분으로명시한다. 본디자인검토에서도C0의fast4/slow1은0으로확인했다.

정책검토자는head별독립개발선택을권고했다. 에너지와AP가별도fixed-basis head이므로,각head에대해**전역uncentered/centered방법하나를동일source-excluded rawmetric으로선택하는규칙을사전에등록**하면새조합최적화/추가fit없이각목표의효과를판정할수있다. 저는이를조건부수용한다. 두방법의matched두출력표는그대로보존하고,fold별잘맞는방법을혼합하지않으며평가22를본뒤head조합을고르지않아야한다. 명시적독립head선택규칙이없으면등록된두방법bundle만비교한다.

J와°C를섞는새가중치α나jointscore를발명하면추가자유도가생긴다. 대신단위별raw gate/모든sourcegroup악화·max/peak/방향·정책차이를독립적으로보존한다. centeredshape오차가작다는이유로absolutelevel손실을감추지않는다. source제외시희박노출/shortmemory문제가드러나면새τ나window를탐색하지않고한family의실패/전이한계로닫는다.

**Round3 결론:** 고정정확basis의AP5계수를추가해최대20fit의사전등록대조연구를검토하는것은타당하다. 이것은두출력의추가오차감소가능성을실제로검증할수있는유한가설이며성과보장이아니다. 다음실행에서새AP계수의절대경로가더악화할수있다. 이번검토는design-only/새headfit0/기기0/RL변경0이며기존개발이력·고정후보·결과를수정하지않았다.
