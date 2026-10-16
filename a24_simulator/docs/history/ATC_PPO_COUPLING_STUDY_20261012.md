# ATC와 PPO 연결 방식의 유한 비교 — 08

작업 `ATC-COUPLING-EXPLORE-08`, 2026-10-12 KST. 사용자가 여러 연결 방식을 실험하도록 요청했고, 이어 EFT 사용 금지와 Greedy의 독립 비교군 역할을 명확히 했다. 이에 맞춰 제안 내부의 EFT/Greedy 중재안을 **등록·환경·학습0회에서 폐기**했다. 과거05~07의 원자료·판정·소스·예산은 보존한다. 기준 checkout은 `work/repo`, detached HEAD `12d64923be824ce4c88fca074fbe38820f5a7d25`의 미커밋 작업이다. 앱 기본과 experiment_ready=false는 유지한다.

## 질문과 확정한 다섯 연결 방식

이전05는 강한 초기 ATC 행동 확률0.9 때문에 개발의18,432개 복수가능 선택에서 학습된 greedy가 ATC를 벗어나지 않았다. 다음 비교는 같은 상태·ATC 후보·물리 지원·목적·새 자료에서 연결만 바꾸어 그 영향을 분리한다.

| 군 | ATC와 PPO 연결 | 명시적 prior | 실행 선택 범위 |
|---|---|---|---|
| JP09 | 실제 ATC 기준행동에 강한 logit bias＋PPO | 초기 기준행동 확률0.9 | 후보의 모든 물리적 행동 |
| JP05 | 약한 기준행동 bias＋PPO | 초기 기준행동 확률0.5 | 위와 같음 |
| JNONE | ATC 후보/점수특징을 주고 PPO 직접 선택 | 없음 | 위와 같음 |
| ATC_ROUTE | 현재 후보 안에서 ATC가 논리적 primary 요청을 고르고 PPO가 자원·pair를 선택 | 없음 | primary를 포함하는 single/CG_DC; 진전불가일 때 자원WAIT |
| ATC_SCORE_RESIDUAL | 현재 ATC 요청점수를 action prior로 넣고 PPO residual이 보정 | beta1×clipped ATC logscore gap | 모든 물리적 행동 |

JNONE에도 ATC 후보·rank/gap·teacher feature가 남아 있으므로 ‘ATC 없는 PPO’가 아니다. Greedy·RR·FIFO는 독립 비교군이며 제안 정책이 그 출력을 호출/선택하지 않는다. EFT 비교군·선택지·구모델 callback 재생은 이번에0이다.

초기 기준행동은 ATC 순위에서 현재 후보에 표현된 합법 요청을 고른 뒤 **CPU→GPU의 고정 canonical 순서**로 배정한다. 이는 초기 동점/오류 복귀/teacher를 정의하는 규칙이며 최소 처리시간·최소 예상완료시간 배정이 아니다. 학습된 PPO는 각 연결의 허용 범위 안에서 다른 자원·병행·요청을 선택할 수 있다. ATC_ROUTE가 전체 task FIFO를 다시 요구하는 것도 아니다.

## 상태·행동·ATC 점수

공통 새 ABI는 state218=global28＋8request×20＋2owner×15, action57=기존53＋두 job별(rank,score-gap)4, padding32다. 새5군 모두 fresh weights를 사용하고 이전214/218×53 가중치는 전용하지 않는다. coupling ID와 source/input/schema를 checkpoint dependency에 고정한다.

후보는 현재 도착한 미시작 큐의 ATC top4＋task별 oldest coverage＋현재 EDD 복귀 행동의 요청, 최대8개다. single C_CPU/C_GPU/D_CPU와 CG_DC pair, 필요한 자원WAIT만 구성한다. 실질 행동 최대29·padding32이며 동점 arrival/ordinal/id와 지원 밖 조합 배제를 유지한다.

현재 ATC lower-is-better logscore는 다음과 같다.

`L_i = log(p_occ,i) - log(w_i) + max(0, (d_i-t)-p_response,i)/(k*mean(p_occ))`

- t는 현재시각, d는 도착＋요청이 선언한 기한이다. w는 긴급2/일반1의 정책 가중치이며 실측 지연 비용이 아니다. k2, 처리시간 단위초를 고정한다.
- 대표 p/r는 **고정 CPU 기준 경로**의 측정 평균과 완료 후 현재까지 관측된EMA0.1이다. CPU/GPU별 특징은 NN에 주지만 ATC 대표경로나 teacher를 현재 예상finish 최소화로 고르지 않는다. 응답은 urgent OUTPUT_READY, normal PERSISTED이고 점유는 실제 AVAILABLE까지다.
- rank는 전체 현재Q에서의 index/(Q−1), singleton은0이다. gap은 L_i−현재Q의최소known L이며 encoder에서0~10으로clip한다. unknown gap10·duration-valid bit0, padding0이다. 이 값은 실측 비용이 아니라 순위 prior용 특징이다.
- single의g는 해당요청gap, pair는 두요청gap의min이다. pair의둘째요청 납기/비용을 보장하지 않는다. 현재 legal start가 있으면 WAIT g는그start들의최대g＋1, 진전없으면0이다. 모두 현재 public 후보/물리mask에서 계산하며 미래큐 실행이 없다.

JP09/JP05는 legal 선택수M에 대해 `log[(p0/(1-p0))*(M-1)]*teacher_flag`를 logit에 더한다. SCORE는 `NN_logit - g_action`이다. sampler와 PPO old logprob/update는 같은 bias와 **실제 effective mask**의Categorical을 사용한다. 외부 epsilon-greedy·비교군 정책 혼합은 없다. 초기raw actor0의argmax 동점은실제teacher를택한다.

## 물리 계약과 사건 기반 롤링

physical_mask와 coupling의effective selection mask를 모두 저장한다. ROUTE의선택제한은운영 envelope이며 물리적 불가능과 구분한다. 실제 샘플링은둘의교집합에서만 하고 teacher를 항상유지한다. 나머지4군의effective mask는physical mask와같다. 물리mask는 납기·서비스·온도를보장하지 않는다.

기존C_CPU/C_GPU/D_CPU/CG_DC≤2, 비선점, 실행 중 자원이동0, 응답과AVAILABLE 분리, 자원WAIT 계약을 유지한다. 출력/응답만준비돼도소유권을풀지않는다. 임의냉각·NPU·3건병행·unsupportedGPU 추가0이다. 새도착/실제AVAILABLE는HOLD를취소하고 자원타이머에서미시작요청을재판단한다. 같은시각 단계완료CPU/GPU→ordinal도착→dispatch완료→새판단,revision 중복방지와같은시각 pairsecond의actualreceipt/owner/physicalguard를유지한다. 별도미래계획구간을최적화하는rolling horizon은없다.

운영이벤트→bank→mask→encode→NN→dispatch에전체큐 future simulation이들어오면runtime trap으로실패하게한다. 엔진의private현실화벡터/미래도착/실제미래응답/J/AP는관측에전달하지않는다. legacy engine.choose/p.Controller callback/rollout/place/전체큐 AP·J forecast/EFT helper를트랩한다. 학습용future suffix label은episode완료후에만계산한다.

## 새 자료와 가정의 경계

888 namespace의학습16도착seed×4family×4factor=256입력/모델,개발2×4×4=32,확인4×4×4=64다. private residual888000201, 공개hint888000301과초기601/607/613, 행동+10000/셔플+20000을분리한다. 같은초기seed를5군에짝지어초기화하지만가중치/optimizer를공유하지않는다. 같은환경 request/backend-keyed draw가 모든군에 적용된다.

- single_fixed: n1·원U1.5/N6초.
- single_due: n1·새선언U.75/1/1.5·N3/4.5/6초.
- uniform2: 같은가변선언기한·n2합성.
- variable123: 같은가변선언기한·task별n1/2/3균형합성, uniform2와총units일치(실제realized초동등주장X).

새선언tier와arrival은05의U.5/1/1.5·N2/4/6보다일부덜엄격하므로‘기존모든요청SLA 완화0/과거실패해결’이라고말하지않는다. 원앱cap1.5/6은유지하고같은08입력에서5연결효과를분리한다. 이전873/05/07와달라진데이터·상태·목적의효과를연결한가지로귀속하지않는다.

측정 donor는동일ABBA4의384개intact5phase(C_CPU4/C_GPU188/D_CPU192)다. CPU분류4표본의약한근거를유지한다. n2/n123은execution_start→OUTPUT_READY 복합구간선형배율가정이며실측appbatch지원이아니다. 입력은공개units만,미리뽑은실제잔차는숨긴다.

부하는balancedC/D low24건/1.8초간격,variable48건/.65~1.05초,paired48건/2.6초group(Cfirst/Dfirst교대),sustained96건/.85초다. 모두35초부터120초전도착이다. n2탐지48건의CPU최소57.86초<85초로과거n2 D96건의용량불가능을재사용하지않지만,다른CPU경쟁·도착·n3·기한때문에완료/납기실패는여전히가능하다. 이것은새기기 독립확인이 아니다.

## 학습·개발선정·최종확인

동일CAUSAL10채널: AVAILABLEunit 완료credit−미응답unitseconds/(units×85초),prefix120증분J/100J·AP runningpeak35~120증가/1°C,원/선언U/N각실패rate·terminal미완료units/requests·긴급미응답시간/(NU×1.5초)다. 네실패/I각10·J/AP/Uholding각1의고정가중치이고이실험에서보상튜닝은없다. final J120/AP35~180과학습prefix는구분한다. final미완료 비용은null,학습prefix는실제소유자/관측경로를끝까지적분한다.

모델당64→128→256의8episode 경험묶음/native PPO update를사용한다. pure고정마스크뿐인묶음도수집학습수에포함하고critic-only update로기록한다. actor/candidate grad=None이라actor직접Adam모멘텀은업데이트하지않지만sharedstate encoder는critic으로변해정책에간접영향이가능하다. 가짜중복행동을만들어학습기회를부풀리지않는다. 실제actorchoice/update·gradient·변경·fallback을따로검사해64단계mechanics실패면자동확대하지않는다.

각군/seed는**실제학습한64/128/256 중**개발n1범위의I/units/Ucap/Urequest/Ncap/Nrequest/P95→J/AP합계lex,동률이면이른checkpoint를선정한다. 이선정은조건별서비스guard나채택통과를뜻하지않는다. CP0로되돌아간결과를학습성공으로숨기지않는다. RuleATC는독립대조/안전복귀기준이고,훈련모델의악화도실제확인표에남긴다.

15모델의weights/SHA와전체대표선정은개발만으로부모freeze에고정하고나서확인64×21=1344행을평가한다. 확인동안weight고정·masked argmax만,확인후재학습/재선정0이다. 새서비스실패·불완료·조건별손해/기준규칙과의teacher override를전부보고한다. source/형식/NaN 오류는ATC복귀로그를남기고반복모델오류3회면해당모델을비활성화한다. 실험검증과운영채택은별개다.

## 예산·병렬·재개

예정환경6836=학습3840＋trained개발1440＋규칙개발192＋확인1344＋초기native증명20. 학습3840은환경에포함한다. 3개seedworker는각2300환경/1280학습/active3600초·reserve300,규칙worker600환경/학습0/active1200·reserve120이다. 합cap7500환경/3840학습,예정seed6012100환경(초기증명20포함),607/613각2080,규칙576이다. 시작/실패도소비에포함·원상한재개0이다.

서로다른lock/원장/시계/raw/rows로실행하고root에서합산한다. 첫worker는실제59학습뒤5모델partial/Adam/RNG/cursor/closedclock을보존·정확재개검산한다. 초기20환경은4조건×5군의raw0greedy=RuleATC 원장/전이증명이다. 세학습seed는독립프로세스에서병렬실행한다. 규칙의개발준비는초기증명참조를먼저확정하며,확인은모든freeze후4프로세스로실행한다. worker시간합은walltime이아니고공유PC경합/NN시간은폰시간·소비J가아니다.

## 비교·판정·중단

6기준은FIFO_FIXED(C_GPU/D_CPU globalhead),FIFO_READY_FIXED(현재고정경로ready의oldest),비선점자원RR,정적측정선호Greedy resourceFIFO,EDD,ATC다. Greedy의선호C_CPU/D_CPU는기존ABBA중앙값기준으로고정하며제안내부함수로호출하지않는다. EFT/Band/Triton은새비교0이다.

사용자EFT금지에따라**08 strict의참조군은FIFO_FIXED/RR/Greedy/RuleATC로개정**한다. 과거FIFO_FIXED/EFT/RuleATC의닫힌strict와같다고주장하지않는다. 원서비스cap·전량완료/units·요구/원기한·P95/J/AP·epsilon0·조건별비악화와strict J또는AP 개선요건은유지하고과거FAIL을소급승격하지않는다. n1지원범위와합성범위를분리하며평균손해로조건악화를숨기지않는다. 새strict 후보도자동모바일채택은아니다.

모든모델의actualactor/critic-only/teacher override·요청재정렬·route/pair/WAIT·실제병행·실패와효과를보고한다. ATC/후보/mask/encode/NN/전체PC판단시간평균/P95/max·큐규모를분리한다. 학습이규칙보다나쁘거나같으면그대로중단/보고하고결과가나올때까지확인자료로튜닝하지않는다. 데이터와물리계약은고정하고,후속개선은별도의새개발등록으로진행한다.

## 소스·현재검증과남은사항

새파일은tools/d1_atc_coupling_policy.py/ppo.py/engine.py/controls.py/budget.py/study.py 및test_d1_atc_coupling.py다. native PPO손실·5phaseevent/관측/회계엔진을재사용하고기존05~07소스를변경하지않았다. 새로운9개pure검사는5prior/물리마스크·routeprimary·score/WAIT/likelihood·최소finish비사용·비교군/EFT접근금지·57job바인딩/unknown·실제Adam과partial/RNG복원·critic-only·budget자료상한을PASS했다. 첫검사trap이없는메서드명을가리킨오류는등록전에실제상속callback으로바로잡았다. pure검사는환경/학습0이다.

초기기록의EFT/Greedy중재안은사용자의수정지시로등록전폐기했고새환경0이었다. 세전문가검토는docs/results/atc_coupling_20261012,신규작업원장은work/ATC-COUPLING-EXPLORE-08,사용자산출물은outputs/ATC-COUPLING-EXPLORE-08에둔다. 이번물리fit·APK·기기·S26·NPU 실행은0이며다른동시과제이력은손대지않는다. 학습·초기증명·재개·결과는실제완료후에만추가한다.

## 최종 완료 기록 — 2026-10-12

실제6,836환경/3,840학습/실패0·15모델각256/32update·최종1,344행을 완료했다. 모든선정은확인전개발동결이며CP0대체0이다. 연결5군을바꾸면teacher동일성과GPU편중/서비스손해의상충이남았다. 학습15모델full/지원n1모두개정strictFAIL·채택0이다. 09는별도새입력/목적이며08확인재튜닝0. 원source/input/raw/weights/closed원장 및부분optimizer/RNG exact, 전최종물리mask/AVAILABLE 감사를완료했다. Greedy독립대조/EFT새실행0/기기0·기본과experiment_ready=false 유지. 근거: results/atc_coupling_20261012/RESULTS.md 및 ATC_PPO_ITERATIVE_RESULTS_20261012.md.
