# ATC＋PPO 필요한 자원 대기 확대 연구 — 2026-10-12

작업 `ATC-WAIT-EXPAND-10`. 사용자 밤사이 추가학습/방법확대 승인에 따라 이전256episode 상한을 없앴다. 결과는 데이터에 따라 판정한다. 유리한 가설조건을 사전에 선언하고 부정 조건·모든 비교군·실패·모든seed를 함께 공개한다. 원08/09의확인·FAIL·source·weights·닫힌예산은보존한다. 기기/APK/fit/S26/NPU실행0·기본과experiment_ready=false를유지한다.

## 현재 원인과 가설

09의실제maxQ2에서는ATC/EDD22,217판단이같았고,10GPU병행선택은tiny J/AP 이득과4조건P95손해를냈다. 이번주가설은D_CPU AVAILABLE근처의C도착에서PPO가**CPU자원WAIT**를선택해GPU보다빠르고비용이낮은CPU를활용할수있는가다. EFT식완료시간argmin을정책에넣지않는다. 후보에는현재합법GPU와막힌CPU를이유로하는자원WAIT를둘다남기고NN이현재관측에서배운다. 원ATC_ROUTE는start가능일때WAIT를빼므로사용하지않는다.

D실측점유범위0.605~0.656초/C_CPU중앙0.170초(n4)/C_GPU중앙0.274초(n188)가근거다. 처리시간·열·전력계수를조작하지않고동일intact5phase384donor와기존frozen모형을쓴다. 가설arrival은실측도착분포라는주장없다. CPU분류4표본및모형오차한계는유지한다.

## 부하와 자료 분리

| family | 사전 고정 도착 | 역할 |
|---|---|---|
| idle | C/D교대24·1.8초gap | 과거형낮은부하anchor |
| steady | 교대96·0.6초gap | 일반음성/혼합대조 |
| release_015/035/050/058/065 | D3초주기18회＋C offset .15/.35/.50/.58/.65초±.01초 | earlyWAIT손해·transition/late가설·해제후anchor 모두포함 |
| burst2/4 | D3초주기18회＋C2/4건offset.55＋.06j초±.008초 | 해제경쟁과연속분류대기 |
| mix4 | D1.5초주기24회＋C4 offset.15＋.06j초 | 별도CPU혼잡/배정 |
| boundary6 | D1.3초주기24회＋C6,168요청 | capacity경계stress;삭제하지않고full판정 |

전체n1,기존192requestcap안이다. 두기한factor는원U1.5/N6고정또는U.75/1/1.5,N3/4.5/6 balanced triplets다. 원cap도같이보호한다. arrivals35~120/실행horizon120/에너지120/AP35~180을유지한다. 미래실현Dduration으로Carrival을맞추지않는다.

새namespace923: train64seed×11family×2=1,408개별입력,dev4×11×2=88,final8×11×2=176. 사후ATC teacher1,408환경은control에실제계수하고9모델이공유한다. 모든군의arrival/workload/backend-keyed private draw/물리모형은동일하다. fresh초기1013/1019/1021,action+10000/shuffle+20000은환경난수와분리한다. traincase순환은공개된finite학습자료재사용이며새실측을늘리는것이아니다. final도새arrival/keyeddraw지만같은동결기기모형이라독립기기검증아니다.

## 연결·새ABI·물리 마스크

전체현재arrived/unstartedQ ATC scan→top4＋작업별oldest＋현재복귀coverage,max8요청→single/CG_DC/resourceWAIT→물리mask→PPO. 후보제한을없앤전Qactor라고부르지않는다. 기존공동지원이면현재legalpattern이coverage되고후보slot상한8·실제29행동/패딩32이다. 현재Q의점수/총량집계는가능,전체미래큐실행/응답/J/AP예측은금지한다. teacher는고정CPUreference/CPUcanonical이며Greedy출력이나EFT를호출하지않는다. β1현재ATCgap logitprior＋NNresidual 공통이다.

기존218state＋CPU/GPU각4추가＝**226/행동별57/패딩32**,freshschema/weights다. 추가4는공개현재phase/since/EMA로계산한남은점유/150ms,phase elapsed/phase예상길이,known,overrun이다. 실제hiddenwork-left/AVAILABLE미래시각은받지않는다. phaseoverrun은ETA0＋unknownflag이며조기owner삭제없다. actor encoder와value encoder를분리하고critichead0초기화·critic-only시actorstate/candidate/actorgradNone을공통적용한다. 원episode-sum PPO loss/8episodeupdate/clip/독립RNG와정확resume은유지한다. 과거weights는새226에전용하지않는다.

지원C_CPU/C_GPU/D_CPU/CG_DC≤2,비선점·이동금지,긴급OUTPUT_READY/일반PERSISTED응답과actualAVAILABLE자원반환을분리한다. WAIT는지원필요자원이owner/병행지원때문에막힌경우만이며임의냉각대기0이다. arrival/actualAVAILABLE/자원timer에미시작재판단하는사건기반온라인이고formal rolling horizon없다. 마스크는물리실행가능성이고서비스/P95보장이아니다.

## 세 목적과 단위

| arm | reward/비용 | 비교 의미 |
|---|---|---|
| BASE_DELTA |09같은Rfutureactual−teacher,E1J/AP.1°C,서비스cost10,P95positivegap/1500ms10 |새state/architecture/부하공통의목적대조 |
| URGENT_HOLD |Rδ−절대unrespondedurgent suffixarea/(NU1.5s),Eδ/10J/APδ/.1°C,원/요구U/N/Icost100,pairedrunningP95potential suffix/100ms20 |현재near-release의urgent지연credit강화 |
| TAIL_EXCESS |같은R/E/AP/서비스,age>teacher최종P95인미응답urgent의**t이후holdingarea**actual−teacher/(NU100ms),cost9weight5 |tail-excess 대리지표·CVaR그자체아님 |

URGHOLD ΦX(t)=max(0,(완료urgent runningQX(t)−teacher최종Q)/100ms),emptyΦ0. suffix cost9=(ΦA(H)−ΦA(t))−(ΦT(H)−ΦT(t))로첫frame총량은원terminalpositiveP95gap과같고이미발생한tail을후속target에서뺀다. 중간signedcost허용,γ1이다. TAIL_EXCESS는∫[max(t,arrival+qT),min(response,H)]미응답area라reply-time totalexcess와같은총량이지만과거지연은후속suffix에서제외한다. missingresponse는Hcensor＋절대I/원U 보호,teacher완료/P95None검증은중단하며0임퓨트없다. 사후teacher/실현결과는label에만있고정책입력/후보/mask/추론에는없다.

서비스절대채널은요청/원U/N기한실패rate와미완료unit/request이며분모·단위를원계약대로유지한다. E/AP는학습prefix120과평가180차이를공개한다. signedteacher차이/보상단위교체·state/architecture변경을한원인효과로과장하지않는다. 학습대리지표와최종observedP95/실패/전량/J/AP/strict는별개다.

## 확대·선정·확인

학습환경/episode 수치상한=None . 512→1024→2048→4096→8192→… checkpoints,각3seed×3arm을독립worker에서병렬실행한다. 개발조건별서비스/P95비악화guard후평균J/AP/P95·earlier로선정하며CP0를학습결과로대체하지않는다. primary는사전지정boundary6제외10family이고full은전11family다. guard실패시besttrained서비스lex모델도raw최종에내고FAIL를숨기지않는다.

원정책/입력/source모두처음부터등록sha . 모든9모델및대표를부모freeze에고정한뒤176×15＝2,640확인행에서maskedargmax를한번평가한다. 이후튜닝·재선정0 . 처음59실제부분학습의3optimizer/pending/RNG복원와12초기nativeRule동형을검사한다.

확대종료는미리고정한개발의3seed공통·조건별서비스/P95/J/AP비악화와평균J≥.005J개선2연속window(최소2048),또는밤사이시간/저장reserve이다. 승리할때까지최종자료를재사용하지않는다. wallhorizon6시간(초기9모델512완료여부를먼저확인)·최종1800초reserve,숫자학습cap0·workerclock/원장총량계속누적,8GiB저장reserve/atomiccheckpoint로사용자원자료보존 . 원닫힌상한을수정/초기화하지않는다. 유의한근거가없으면실패/조건부결론을그대로보고한다.

## 비교·판정

독립FIFO_FIXED/FIFO_READY_FIXED/자원RR/정적Greedy/RuleEDD/RuleATC＋학습9모델 . EFT 및옛EFTcallback/PPO재생0,Band/Triton0 . 같은요청·실현draw·owner계약·판정으로비교한다. percondition win/tie/loss/worst·미완료/기한/원cap·P95분모·모형J/AP와allseed을공개한다. PC판단단계/전체mean/P95/max와실제Q별분포를남기고폰판단시간이나소비J로환산하지않는다.

기존strict 참조FIFO_FIXED/RR/Greedy/RuleATC,epsilon0,전량완료/units·요구/원U/N·P95/J/AP 조건별비악화 및strict비용개선은그대로full/primary으로보고한다 . 자동채택0 . 

추가조건부질문은사전선언한5release family의**제안urgentP95≤400ms**·원/요구서비스·전량완료를모든군에똑같이적용했을때의모형비용/열Pareto다. 400ms는기존프로젝트판정이아니라이번에추가한운영목표다. early/after negative도포함하고비적격조건/전체표를숨기지않는다. 이별도분석으로기존strictFAIL를PASS로바꾸거나‘보편적으로우리정책이최고’라고주장하지않는다. 실제긍정결론은독립final에효과가나타난범위에한정한다.

## 구현·증거·현재 단계

새tools/d1_atc_wait_{policy,engine,controls,budget,ppo,targets,study,orchestrator,report}.py 및test . 원nativePPO loss/eventengine/동결모형을재사용하고구미래큐forecast/Greedy/EFT중재는runtime trap으로거절한다. IE/RL검토는docs/results/atc_extended_20261012 . 모바일agent후속은통신오류로미완료이며이를독립PASS로세지않는다. 주담당은실제owner/phase/마스크계약을새순수검사와원장감사로확인한다.

현재는설계·순수7검사PASS 단계,등록/새환경/학습0에서계약을작성했다. 이후실제누적은work/ATC-WAIT-EXPAND-10 원장/clock/status가우선한다. 파일SHA·명령/시각/HEAD12d64923+미커밋신규PCsource/기존WIP보존를기록한다. 구현완료·학습완료·최종효과·기기검증은별도로표시한다.
