# D1Check 처리시간·납기 이질성 비교 — HETERO-DIRECT-PPO-03

2026-10-11 KST. 사용자 승인: 모바일에서 나올 법한 처리시간·납기 다양화로 EDD/ATC/PPO 재비교, 새 S26 P1l 참고. 단계: 등록·A24 PC 학습·고정 확인·전문가 최종 감사 완료, PPO 채택0. 이번 실제 증분 환경1824/새학습768/실패0·활성482.954초다. 원 QUEUE-DIRECT-PPO-02와 과거 결과·가중치·실행 소비는 변경하지 않는다. 기존 앱 기본/experiment_ready=false 유지, APK/ADB/기기/NPU/새 물리 적합0.

## 범위와 현실성의 지위

현재 A24의 frozen service는 요청별 raw 분포가 아니라 문맥별 5단계 평균이다. 점유 추정은 C_CPU165.216ms, C_GPU297.106~312.553ms, D_CPU621.014~622.422ms로 좁고 동일 task/priority의 요청은 같은 추정치를 썼다. 단순히 반복 횟수를 늘려도 요청 간 ATC 차이가 생기기 어렵다.

이번은 **실측 모형에 공개 입력 I/O 이질성을 더한 합성 민감도 비교**다. 25/75ms를 A24의 새 측정값·모바일 모집단 분포로 주장하지 않는다. 실제 사용자 사진의 원 크기/인코딩/저장 위치 등으로 입력 처리 비용이 다를 수 있다는 운영 가정이며, 정확한 예상 I/O를 앱에서 사전에 구분할 수 있다는 추가 가정이 있다. 모델/tensor/품질/추론 kernel 자체는 교체하지 않는다.

- 공개 입력 클래스: 추가 입력 처리 기대시간0/25/75ms. CPU/GPU 모두 같은 요청 클래스 예산을 갖는다.
- A24 실행기 코드를 확인한 위치: `ArrivalEnergyActivity.kt`는 execution_start 뒤 `runtime.execute(image)`를 호출하고 adapter가 내부에서 파일/hash/read/decode/resize/tensor를 수행한다. 따라서 합성 추가시간은 **execution_start→output_ready(S→O) 단계**에 넣는다. dispatch→execution_start를 decode 단계로 잘못 부르지 않는다.
- 실제 입력 I/O 잔차는 요청ID 기반으로 `[0.8,0.9,1.1,1.2]` 중 하나를 뽑는다(평균1). 같은 요청의 CPU/GPU 잠재 경로에 같은 I/O 잔차를 적용한다. frozen kernel/나머지 phase는 short/mean/long 문맥 벡터를 유지한다. 이는 새 실측 분포가 아니라 기존 문맥 평균의 요청별 전이 가정이다.
- 정책은 공개 클래스별 사전 평균과 실행 완료 후 같은 class/backend EMA만 사용한다. 엔진의 실제 잔차·벡터·미래 도착·미래 응답/온도/J를 보지 않는다.
- 요청별 납기: 긴급0.75/1.5/3초, 일반3/6/9초를 처리 클래스와 독립적으로 부여한다. 실제 사용자 납기 분포가 아니라 사전 고정한 요구조건 시나리오다. 원 긴급1.5/일반6초 실패도 별도로 모든 행에서 평가한다. 납기 확대가 원 SLA 실패를 지우지 않는다.

원 frozen 상태별 에너지/AP 계수를 일정의 실제 점유 구간에 적용하되, 입력 I/O 이질성에 그 계수가 전이된다는 가정이다. 이 비교로 휴대폰의 실제 전력·발열 절감을 검증하지 않는다.

## 2×2 대조와 비교군

| factor | 공개 처리시간 클래스 | 요청별 납기 |
|---|---|---|
| fixed | 추가0 | 원1.5/6초 |
| time | 추가0/25/75ms | 원1.5/6초 |
| deadline | 추가0 | 긴급0.75/1.5/3·일반3/6/9초 |
| both | 추가0/25/75ms | 위 변동 납기 |

같은 arrival seed/family의 도착·요청ID와 같은 phase residual seed를 네 factor에 짝 제공한다. 클래스와 납기의 hash label은 서로 다르며 독립적으로 생성한다. low/queue/burst/sustained를 전부 유지한다. ATC가 유리하도록 클래스와 납기를 상관시키거나 실패한 조건을 제거하지 않는다.

새 비교군: FIFO_FIXED, FIFO_EFT, FIFO_READY, EDD_EFT, ATC_EFT, RuleEDD, RuleATC와 후보 bank별 새 PPO101/113/127이다. FIFO+EFT는 선택된 global FIFO 선두의 자원 배정만 바꾸며 HOL을 유지한다. READY는 HOL 해소 효과를 분리한다. EDD/ATC 실행 가능 규칙은 요청 순위에서 현재 legal 행동을 선택한다. 새 기준에 Band/Triton을 넣지 않는다.

학습 전 RuleATC 개발32의 같은 스냅샷에서 raw rank/top4/bank/legal/규칙선택을 분리해 비교한다. bank/action 차이가0이면 EDD만 학습하고 ATC의 중복 learner를 추가하지 않는다. 순위가 달라도 candidate/actor가 같을 수 있으므로 순위 차이만으로 ATC 우위를 선언하지 않는다.

## 새로운 ABI·보상·인과성 계약

공개 ticket에 service_class만 추가한다. engine-only 실현은 별도 per_request 벡터 테이블이다. state206는 기존198 필드에 각 후보의 실제 declared deadline/6초8개를 더한다. action49/pad32는 기존 전체큐의2C+D+C×D+resource-wait≤29 상한을 그대로 충족한다. 각 후보·lane estimate/EMA/workload/owner 예상 반환을 task/backend/priority/**class**별로 연결한다. shape의 숫자 일부가 같아도 의미/schema가 달라 구weights·Adam을 재사용하지 않는다.

8개 critic 채널: AP interval reward/1°C, residual J120/10J, incomplete/planned, 원 urgent/normal 실패율, urgent P95/1500ms, declared urgent/normal 실패율. 비용7개 초기 가중치 `[1,10,10,10,1,10,10]`, 서비스 비용5개만 eta0.01/cap100 dual, E/Q는1 고정. 원학습의 큰 J critic scale 관측을 반영한 새 목적함수이며, 과거 PPO와의 차이를 이질성 단독 효과로 해석하지 않는다. AP label은 실제 행동 구간의 peak 증가를 episode 종료 후 작성한다. policy에서는 온도 미래 경로를 계산하지 않는다.

학습은 sample, 개발·확인은 argmax, 운영은 고정 가중치로 추론만 한다. update는 episode8, max4epoch/minibatch256/lr0.0003/clip0.2/gradient0.5/KL0.03의 기존 native 수학을 재사용한다. actor/environment/shuffle RNG 상태는 서로 분리한다. native 고정 ABI validator는 사용하지 않고 새206/49/32/8 validator를 쓴다.

실제 AVAILABLE까지 점유, 실행 중 비선점/이동 금지, C_CPU/C_GPU/D_CPU/CG_DC만 허용, 최대2건, 자원대기만 허용한다. 미래 큐 rollout/place/AP-J costs는 모든 새 controller 실행 중 trap한다. 평가 engine의 전체 사건 진행과 온라인의 미래 일정 계획은 다른 것이다.

## 학습·개발·확인·예산

- fresh base init seeds101/113/127. 두 bank는 같은 base 초기화의 짝 비교지만 각 learner/action/shuffle 상태는 독립 객체로 관리한다. 행동seed+10000, shuffle+20000.
- train arrival881110101..881110228,512episode(128×4family, 각arrival의factor를고정순환). dev881210101/102×4family×4factor=32. confirm881310101..104×4×4=64.
- 실제 시간 잔차 seed는 train881000201/dev881000202/confirm881000203으로 분리한다. 같은 조건·요청ID/backend의 잠재 실현은 정책 순서와 무관하다. 같은 frozen 물리자료를 쓰므로 독립 새 기기 측정이라고 부르지 않는다.
- 128→256은 finite positive gradient/actor변경/fallback0/실제 서로 다른 ID제외 물리 template 경험/전량 물리원장 계약 통과.256→512는 적어도 한 learner의 개발 key가128보다 개선됐을 때만.512 절대상한.
- 개발 선택key: 미완료→원긴급→declared긴급→원일반→declared일반→P95→J→AP, exact tie는 이른checkpoint. bank/seed 대표도 같은 개발key로 선택한다. 모든 선정weights SHA를 최종64 전에동결하고 모든 seed를 보고한다.
- 새 cap **환경5000/학습3072/A24학습3072/S26학습0/활성10800초/저장600초**.6모델 최대학습3072+개발control224+stage개발576+확인832=4704, 남은296은gate/실패예비이며 추가탐색 권한이 아니다. 원 종료 예산을 초기화/재개하지 않는다. 실패 시작도 소비에 남긴다.
- 등록 직전 새 raw-free unittest5 PASS: 요청class/순위 반례·206/49/32, private realization 독립/sharedIO, 실제AVAILABLE/HOL/미래trap,8critic loss parity/실제Adam1update+partial2+action/shuffle exactrestore, 데이터/factor 분리. 테스트의 합성frame optimizer 검사와 실제환경 episode학습 수를구분한다.
- 원자checkpoint/활성clock/원장/partial/action/shuffle는 보존하고 실제 Adam이생긴57학습 이후에 중지·정확재개를검산한다. source는 **driver자체 `__file__` SHA를등록부터포함**한다. 등록 후 동작수정은 자동거부한다.

새 strictV3는 원 SLA/declared SLA 모두 모든조건·모든참조에서 완료/I/U/N/declaredU/N/P95/J/AP 비악화ε0, low/sustained 절대서비스실패0, 그후 primary low 또는sustained 모든짝의엄격J/AP개선이다.원strict를완화하거나과거FAIL을소급PASS로바꾸지않는다. PC유망도자동앱채택이아니다.

## S26 P1l 인계 감사 반영

읽기전용 별도 clone `work/s26-parsim-p1l`. 사용자 마지막 묶음 `5bdc13c1b59cdb9c231fa88c736ca7c2064d58dc`, 현재branch HEAD `1cf460694daa06f95fecd0ef3c600a7f1ed1bdb0`. 차이는 부록세션/원장사본이며 parsim_v1 부품·계수·결과는 같다. upstream 등록→동결부품→결과판정→연결묶음 순서를 보존한다.

R3 `data/r3_requests.csv`의 CPU1 EfficientNet/Det 및 CG_DC 전체단계분포가 실제 제공됐다. 이전에부족했던 혼합CPU1 서비스 부품의존재는확인됐다. 다만 MODEL_CARD/기존판정은 짧은서비스 **탐색용**, 열 **미재현**이며CPU조임=1가정,CPU전력은CPU4MobileNet계수×g_CPU가정이다. 지속서비스·열크기·J우위·3자원/NPU를이번비교에추가하지않는다.

adapter의dispatch6시각과state.lanes의정확한미래lane_available은엔진예약전용정보다.새scheduler정책에넘기면미래실현누수이므로직접입력으로쓸수없다.원부품공유RNG는같은seed만으로정책간요청별동일실현을보장하지않는다.실제연결시요청ID/resource별draw고정과공개owner/과거phase/관측추정만노출하는경계를구현해야한다.

이번실행은A24이질성비교로한정한다.S26는인계부품/분포/원판정의정적감사이며새S26학습/환경/열재적합/기기0이다.첨부답변에재현명령이있다는이유로fit/기기명령을자동실행하지않는다.상세전문가근거는results/hetero_direct_ppo_20261011/{mobile,ie,rl}_review.md다.

## 구현과 검증 대상

새 `tools/d1_hetero_direct_{policy,ppo,engine,study,budget}.py`, `d1_hetero_mobile_rules.py`, `test_d1_hetero_direct.py`. 원 `d1_queue_direct_*` source·기존모델·보고서·미커밋문서와동일경로에발견된외부 `d1_queue_hetero_*` draft는변경하지않는다.기준checkout detached HEAD12d64923be824ce4c88fca074fbe38820f5a7d25+이번source/document WIP이다. 실제실행수·선정·strict·조건별손해·판단평균/P95/max는완료원장과별도결과로갱신한다.

## 완료 결과와 해석

개발 RuleATC32의4372판단에서순위/top4차이16·규칙선택차이2,bank/legal차이0으로EDD만fresh3seed학습했다.128→256개발비개선이라256에서중단·3모두128checkpoint를선택했고대표EDD101을최종64전에동결했다.실제각256/32update·Adam648/648/644·partial0이다. pause59는20/20/19 episode·partial4/4/3·각2update/Adam40step을정확복원했고46.047초/283환경/59학습소비를계승했다.

최종10군×64=640행,각군4224/4224완료·미완료0.이번1824환경은224control+768학습+192stage개발+640확인이며실패0·누적활성482.954초다.이전task2689/1536·원791/192및프로젝트누적이력은변경하지않았다.S26이번새환경/학습/fit/기기0,설치/ADB/NPU0이다.

both16조건:EDD_EFT urgentP95598.541ms/원긴급실패1 vsATC_EFT404.184ms/0으로차이가발생,J는153.492679→153.506442로악화했고원/declared일반실패는둘49/13이다.RuleEDD와RuleATC는원/declared일반43/9·J/AP동률,긴급P95는426.425vs431.595로ATC가높다.정책의순위차이와실제성과차이를구분한다.

선정PPO의전체64원일반실패77은Rule116보다적으나declared일반90은Rule53보다많다.both에서는24/29vsRule43/9다.urgentP95와J는Rule과64조건exact동일,AP차이는약10^-14°C수치오차라실질열효과로주장하지않는다.원+declared보호strictV3세모델모두FAIL·채택0이다.부동소수점차이의epsilon0문턱은등록대로유지했고원일반/새납기상충만으로도채택실패다.

직접5군×64의46702판단에서raw순위1265/top4순서1227/bank31/legal8/규칙선택227차이가있었다.개발중복gate는관측된개발상태만의사실이며최종에드문bank차이가발견되어보편동형성을주장할수없다.이64를보고새ATClearner를학습하거나모델을재선택하지않았다.결과가모든자료에서ATC/EDD완전동일하다고설명하지않는다.

원장/raw1824SHA·전snapshot201109의shape/chosenmask/futurecalls·640strict·원+declared분모·phase/AVAILABLE·source/3latest/3선정SHA를root와RL전문가가독립감사했다.5개새raw-free단위검사도PASS다.PC판단평균/P95/max·Q증가는결과CSV에있고현재큐Q512전용계산평균5.097/P955.947/max6.286ms를폰시간·정책에너지로환산하지않는다.보고서재생성/계산bench/정적감사는환경·학습0이다.

현재앱기본/experiment_ready=false유지,본과제추가학습·확인재튜닝없음이다.S26 P1l의서비스부품은확보됐으나열/J/지속서비스·품질/시계gate가해결된것은아니다.기존자료로제한을숨기거나S26모형을A24에혼합하지않는다.완료근거는results/hetero_direct_ppo_20261011/README.md와각CSV/JSON/전문가3검토다.
