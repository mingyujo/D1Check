# ATC＋PPO 연결 대조 확대 — 2026-10-12

작업 `ATC-WAITLINK-EXPAND-11`. 사용자의 밤사이 충분한학습/여러연결시험 승인에따라10회차의512 **개발** 관측(일부목적이ATC와같은행동)을근거로teacher 표시 shortcut과WAIT 점수불이익을대조한다. 10의확인결과는이설계·선정에쓰지않는다. 10을수정하거나중단하지않고별도소스/신규weights/원장으로병렬실행한다. 새확인자료는10과다른923410101..108이며모든모델선정후한번열어본다. 유리한결론을미리정하지않고모든seed·불리한조건도보존한다.

## 대조군과 공통 조건

| 군 | NN에teacher행동표시52 | resourceWAIT logitgap | 목적 |
|---|---|---|---|
|10 URGENT_HOLD(기존개발대조)|있음|현재legalstart gap최대+1|urgent AREA＋pairedP95potential |
|11 KEEP_FLAG_WAIT0|있음|0|위와동일 |
|11 DROP_FLAG_WAIT1|NNembedding에서만52=0|현재legalstart gap최대+1|위와동일 |
|11 DROP_FLAG_WAIT0|NNembedding에서만52=0|0|위와동일 |

single/pair 현재ATCgap β1,물리mask/후보/공개state226·행동57·패딩32는같다. DROP에도ATC점수/순위/후보와현재Rule복귀·안정동점이남아있으므로ATC정보전체를없앴다고주장하지않는다. raw52·unique legal validation·argmax tie·fallback 메타는모두보존하고NNcandidate clone에서만표시52를숨긴다. WAIT0은실제필요resourceWAIT의확률불이익을제거하는학습연결변경이며물리mask·임의냉각/idle를확대하지않는다.

세군은같은목적 `Rdelta−absoluteurgent suffixarea/(NU1.5s)`,Edelta/10J/APdelta/.1°C,요구/원U/N/Icost100,pairedrunningP95potentialsuffix/100ms weight20이다. nativeepisode-sum/clippedPPO·actor/valueencoder분리·critic0·동일paired초기1013/1019/1021,action/shuffle분리·maskedargmax 확인을유지한다.10가중치를재사용하지않고v8freshschema/newweights다. 데이터/모형과상태정의가같은개발checkpoint끼리비교할수있지만다른확인자료의한평균을연결단독효과로합치지않는다.

## 자료 재사용과 새 확인

10의train1408/dev88·실제ATC teacher1408＋규칙dev528＝1936원환경자료를변조없는SHA binding으로복사한다. 이1936은10에서이미계수됐으므로11신규환경0으로정확히구분한다. finite학습자료순환재사용이며새실측/완전히독립학습자료가아니다. 신규확인은923410101..108×11family×2납기＝176조건,전체6규칙＋9학습모델＝2640행이다. 이후확인튜닝·seed선별·재선정0이다.

같은n1·4/188/192의384intact5phase donor·동결J/AP·D3초와Coffset.15/.35/.5/.58/.65·burst2/4·별혼잡mix4·boundary6·idle/steady·원/선언기한·120초창을유지한다. 도착을실제미래Dduration에맞추지않는다. 미래teacher결과는post-episode label만이고policy/state/mask/NN입력에없다. 전현재Qscan＋top4/coverage8/action29 boundedpool은전Q모든행동선택과구분한다.

## 실행·범위·판정

EFT0·Greedy/RR/FIFO독립군·비선점/실제AVAILABLE/응답분리/지원C_CPU/C_GPU/D_CPU/CG_DC≤2·필요resourceWAIT만·NPU/냉각0. 기기/APK/새모형fit/S26실행0·원기본과experiment_ready=false유지. 이전10의WinError IO복구보충만동일SHA로써atomic os.replace transientretry를재사용하고정책/자료/모델/optimizer를바꾸지않는다.

숫자episode/환경상한=None,512→1024→2048→4096→8192→…·10과같은밤사이종료시각/최종reserve·저장8GiB를공유한다. 세새seedworker를추가해총6process를6core/12threadPC에서돌린다. PC병렬경합시간을폰시간/J로환산하지않는다. 실제59학습부분정확resume/native12teacher동형은새회차에서도검산한다.

개발primary는사전지정boundary6제외10family,조건별RuleATC 서비스/기한/원cap/I/units/P95 비악화guard후평균J/AP/P95/earlier로실제trainedcheckpoint만선정한다. 없음이면besttrained도FAIL로평가하고CP0로숨기지않는다. originalstrict full/primary epsilon0·참조FIFO/RR/Greedy/ATC·전량완료/서비스/P95/J/AP비악화/strictgain은바꾸지않는다. 추가제안release400ms SLO 조건부효율은별도이며보편우위나원strict PASS로승격하지않는다. 모든9seed모델·조건별win/tie/loss/worst·미완료와낮은Q/largeQ진단을공개한다.

## 구현/검증

tools/d1_atc_waitlink_{policy,ppo,targets}와test는RL전문가가별도구현했고engine/controls/budget/study/orchestrator/report는주담당이새파일로작성했다. 소스4파일순수9검사PASS:teacher52 NNdrop/가중치gradient0·rawflag/물리mask/복귀보존·Wait0/Wait1/sample logprob·maskedgap/pairmin·초기argmaxteacher·동일URGENT_HOLDtargets/수치/valid/reward·seed파라미터/RNG/newoldschema거절이다. 순수검사는환경/학습/기기0이며등록→native실제학습→새확인은별도기록한다.

10계약의물리/ETA/credit/열모형자료한계를그대로따른다. CPU분류4표본/기존모형PC탐색이므로phone개선실증아니다. 원08/09/10 SOURCE·등록·raw·weights·닫힌이력·다른WIP를보존한다. 초기등록단계의11새환경/학습0은이후실제원장누적이우선한다. HEAD12d64923+새미커밋source·등록SHA와parentreferenceSHA가근거다.
