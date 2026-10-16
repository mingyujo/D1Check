# EDD·ATC·직접 PPO의 처리시간·납기 다양화 비교

2026-10-11. 새 작업 `QUEUE-HETERO-PPO-03`. 상태: **구현·6모델 학습·13군×48조건 비교·세 전문가 최종 감사 완료, 새 PPO 미채택**. 실제 환경2,768/학습1,536/실패환경0·보고 저장실패1, 활성1,133.609초다. [완료 보고서](results/queue_hetero_20261011/README.md)가 최종 수치 근거다. 닫힌 `QUEUE-DIRECT-PPO-02`를 수정하거나 다시 학습하지 않았다. 현재 detached HEAD `12d64923be824ce4c88fca074fbe38820f5a7d25`의 사용자 문서·신규 소스·원장·원자료 및 동시 별도 작업을 보존했다. 적용 지침은 루트 AGENTS.md다.

## 현실성의 근거와 한계

현재 A24 앱은 같은 이미지와 고정 224/320 tensor를 사용한다. 이미지 내용이 다르면 CNN 처리량이 크게 달라진다는 근거는 없다. 따라서 사전에 미래 실제 처리시간을 알려주는 실험은 하지 않는다.

실제 자료는 `docs/results/overnight_device_20261011/requests.csv`의 ABBA4·384 요청, 분류CPU4/분류GPU188/탐지CPU192의 온전한5phase다. dispatch→execution_start→output_ready→persist_complete→worker_release→lane_available 경계를 유지한다. 이미 본 자료의 bootstrap은 시뮬레이터 개발·감도 자료이며 새로운 기기 독립 검증이 아니다. 분류CPU4표본은 매우 작아 일반적인 분포를 입증하지 못한다.

변동은 각 요청·backend의 전체5phase 벡터를 숨겨서 뽑는다. 공개 ticket에는 task/priority/arrival/deadline/ordinal/id와 사전에 선언한 `work_units`만 있다. 고정 입력에서 단순히 선택된 quantile을 알려주는 oracle 힌트를 만들지 않는다. 미래 도착·실현 벡터·미래 결과는 환경 전용이다.

## 네 조건과 비교군

| 조건 | 공개 작업량 | 납기 | 용도 |
| --- | --- | --- | --- |
| single_fixed | 한 이미지 요청 n=1 | 긴급1.5초·일반6초 | 새 실측 bootstrap과 기존 납기 기준의 대조 |
| single_deadlines | n=1 | 긴급0.5/1/1.5초, 일반2/4/6초 | 납기 다양화 효과 |
| batch_uniform2 | 모든 요청 n=2 | 같은 가변 납기 | 묶음 평균 작업량 증가의 대조 |
| batch_variable | 요청별 n=1/2/3 | 같은 가변 납기 | 공개 처리 작업량 다양화 감도 |

두 batch 조건은 작업별 총 work_units를 정확히 같게 하고 같은 도착·납기·기저 잔차를 사용한다. single과 batch 사이에는 부하량 증가가 있으므로 그 차이를 순수 이질성 효과로 부르지 않는다.

batch는 현재 Android 앱에 구현·측정된 기능이 아닌 모바일에서 가능한 새 요청 형태의 **합성 가정**이다. 5phase 중 `execution_start→output_ready` 구간 전체만 n배 하고 다른4구간은 고정한다. 순수 invoke 시간 n배라고 부르지 않는다. 같은 잔차를 n배하는 상관구조·추가 aggregation 비용0도 가정이다. 완료는 묶음 전체 응답이 준비된 경계이며 요청수와 작업단위 완료를 모두 보고한다. batch 열/J는 동결 점유 상태 모형의 전이 가정이며 실제 측정 비용이 아니다.

납기는 앱의 기존 긴급1.5/일반6초 상한보다 강화하거나 같다. 위 세부 값은 새 요청 조건을 위한 연구 가정이며 실제 모바일 산업 표준 기한이라고 주장하지 않는다. 작업을 제거하거나 기한을 늘려 실패를 숨기지 않는다. 요청별 강화 납기 실패와 기존 상한 실패를 각각 기록한다.

FIFO_FIXED/FIFO_EFT/FIFO_READY/EDD_EFT/ATC_EFT/RuleEDD/RuleATC 및 EDD 후보 PPO·ATC 후보 PPO를 비교한다. 같은-bank Rule과 PPO로 학습 효과를, 두 bank로 후보 효과를 구분한다. Band/Triton은 이번 비교에서 제외하며 과거 결과를 보존한다.

## 추정·ATC·물리 계약

대표 경로는 현재 지원 경로 중 예상 점유 최소다. 각 backend 기저5phase 추정에 공개 n을 적용하되 실제 bootstrap 선택은 읽지 않는다. 관측 AVAILABLE 뒤 실행구간을 n으로 나눈 기저 관측으로 EMA0.1을 갱신하여 이중 배수를 막는다. CPU/GPU의 p/r과 실제 owner 잔여도 같은 n을 적용한다.

앱 ATC는 `w/p_occ × exp[-max(d−t−r,0)/(k×mean_p_occ)]`, urgent w2/normal w1·k2다. EDD는 절대 d 순서다. top4∪oldestC/D∪현재 EDD 복귀≤8을 canonical arrival/ordinal/id 슬롯으로 묶는다. 동점은 같은 순서다. 지원single/CG_DC pair/필요한 resource wait≤29, padding32를 유지한다.

지원 C_CPU/C_GPU/D_CPU/CG_DC·최대2요청·비선점/이동금지·실제AVAILABLE·긴급OUTPUT_READY/일반PERSISTED 응답을 유지한다. 물리 mask는 서비스 보장이 아니다. 냉각/NPU/미지원 조합·전체큐 미래 rollout/응답/J/AP 계산은 추가하지 않는다.

새 ABI는 state214 = global24 + request8×20 + lane2×15, action53 = present/kind4 + job2×24 + fallback1, pad32다. 각 요청·job의 공개 n/3와 valid를 추가하며 예상 p/r은 요청별 n을 사용한다. 이전198/49 가중치를 재사용하지 않는다.

## 학습·개발·확인과 예산

초기화101/113/127, action seed+10000, shuffle seed+20000. 환경 도착873110101..116/개발873210101..102/확인873310101..103, 처리실현873000201, 공개 힌트/납기873000301을 분리한다. keyed realization은 정책의 dispatch 순서에 좌우되지 않는다.

학습16도착×4부하×4조건=256/learner, 개발2×4×4=32, 새 최종3×4×4=48이다. 개발 RuleATC 방문 상태에서 raw rank, 실제bank/legal/입력 동일성을 분리한다. bank 차이가 없으면 EDD만3seed 학습하고 ATC Rule은 비교한다. 차이가 있으면 각각3seed를 학습한다. 현재 범위를 모든 가능한 상태의 동일성 증명으로 부르지 않는다.

128에서 finite/positive actor gradient·actor 변경·fallback0와 actual physical ledger를 확인하고 최대256까지 수행한다. stage마다 개발32를 평가한다. 각 seed의 개발 I→U→N→P95→J→AP lexicographic와 earliest tie로 checkpoint를 고르고 대표 bank/seed를 최종 자료 전에 SHA freeze한다. 최종은 masked argmax·추론만, 전seed를 보고한다. stage256 뒤 확대/holdout 사후튜닝은 없다. 오류/등록 mismatch는 중단하며 실패 환경을 소비에 남긴다.

목적 V3는 AP interval/1°C, J minus known resident baseline/100J, I/U/N 실패율·초기승수10/dual, urgentP95/1500ms다. E가중치1이라 이전 J/1J 대비 에너지 상대 중요도를 낮춘 **새 목적**이다. critic만 바꿨다고 설명하거나 원 PPO 결과와 합치지 않는다. 최종 평가는 J/°C/ms/전체 도착 건수의 원단위이며 정상 완료 표본만으로 성공을 만들지 않는다.

주과제 cap3,200환경/1,536학습/A24학습1,536/S26학습0, 활성3,600초와 저장reserve300초다. 양bank이면 controls224+train1536+dev384+confirm624=**2,768환경**이 예상된다. raw-free unit8은 환경0이다. stop/restart는 actor/critic/Adam/승수/partial/action·shuffle RNG/cursor/consumption/active clock을 보존한다. 등록driver SHA를 처음부터 포함한다.

등록한 strict V3는 FIFO_FIXED/FIFO_EFT/same-bank Rule 각각과 모든조건 completion·요구 U/N·P95/J/AP 비악화 ε0, low/sustained 절대실패0, low 또는 sustained 전짝에서 J/AP 한축 엄격 개선을 요구한다. 납기 상한은 넓히지 않았지만 강화 납기의 실패 합 비악화는 기존상한 실패 합 비악화와 동치가 아니다. 실제 선정 PPO는 RuleATC 대비 강화긴급 실패189vs190으로1건 적고 기존1.5초 실패18vs14로4건 많았다. 원등록을 소급 변경하지 않고 전6 FAIL을 유지하며 기존상한의 조건별 guard를 별도 사후 보수감사로 추가했다. 다음 등록은 기존cap와 요청due 비교를 모두 채택 조건에 명시해야 한다. 그룹별 결과·불리 조건을 공개하며 평균만 좋아 채택하지 않는다. experiment_ready=false·자동채택0·앱 기본을 유지한다.

## S26 인계의 반영

격리 checkout `work/s26-parsim`의 보고된 연결 커밋5bdc13c1에 고정했다. 등록2f31deac→결과전부품/예측c4eae394→판정83d86332→연결5bdc13c1의 조상관계를 확인했다. 현재 branch tip1cf46069와 이 인계 기준을 구분한다.

MODEL_CARD/adapter/data5CSV manifest/Git blob/expected events SHA/판정을 정적으로 확인한다. CPU1 EfficientNet/Det·CG_DC R3 실측분포·연결 코드의 **존재 문제는 해결**됐다. 서비스는 짧은 혼합 부하 탐색용이고 열은 미재현이다. 지속 CPU 조임/DVFS는 없으며 CPU4 전력지도 근사여서 에너지 검증으로 쓰지 않는다. S26 학습/fit/기기0, A24 계수와 결합0이다.

adapter의 `state()['lanes']`와 dispatch의6시각은 미래 실현값이므로 정책에 직접 공개하면 누수다. 미래에는 환경 private로 보관하고 실제 발생 단계만 journal로 공개해야 한다. NPU 제외/CG_DC/max2/중복ID wrapper도 필요하다. A24의 worker_release 포함5phase와 S26 host inference/start/return 포함5tuple은 경계가 달라 `durations=`를 그대로 넘기지 않는다. 실제 APK·품질/정밀도·시계의 남은 gate와 모델 열/J 판정을 구분하며 기존 실패는 보존한다.

## 구현·산출물

새 `tools/d1_queue_hetero_policy.py`, `_mobile.py`, `_engine.py`, `_ppo.py`, `_budget.py`, `_study.py`, `test_d1_queue_hetero.py`다. 기존 사건·PPO 수학·5phase/응답/실제ownership을 재사용하고 종료 V2 소스는 변경하지 않는다. 결과는 `docs/results/queue_hetero_20261011` 및 projectless `outputs/QUEUE-HETERO-PPO-03`에 원단위 CSV·그림·조건별 판정·학습/원장/SHA·세전문가 문서로 보고한다. PC 판단시간의 평균/P95/최댓값과 큐 크기 효과를 재계측하되 phone 시간·제어 에너지로 환산하지 않는다.

## 완료 결과와 설계에서 확인한 점

개발5,227판단의 raw rank차2,519·bank차1,973·legal차302로 EDD/ATC 각3seed를 학습했다. 각256episode·32update, Adam step은 EDD101/113/127=724/736/732, ATC101/113/127=744/748/744다. 선택은 EDD101@128/113@256/127@128, ATC101@128/113@256/127@256이고 대표ATC101@128을 최종 전에 동결했다. 전6 strict FAIL·채택0이다.

원 실측변동과 기존 기한의 single_fixed에서는 EDD/ATC raw rank차76/13,159이나 bank/legal/규칙 선택차는0이다. 가변 납기 single_deadlines는 rank차1,005/bank차26/legal차10/규칙선택차204이나 요구실패 합은 RuleEDD/ATC 모두U1/N50이었다. 기존6초 일반 실패는EDD25/ATC30으로달라 같은집계가같은서비스를뜻하지않는다.

공개 작업량이 달라지는 합성 batch_variable에서는 RuleEDD→RuleATC가 완료709→735, 미완료83→57, 강화U100→91/N387→237, P95평균1315.044→1293.849ms였다. 완료units는1415→1413으로2단위 줄어 작은요청 우선의 상충이 남았다. 같은군 대표PPO는완료730/units1403/I62/U92/N243/P951376.957ms로RuleATC보다나쁘다. 이질성에서ATC가유용할수있는조건과학습추가이득미입증을분리한다.

주분석 single_deadlines에서 대표PPO는일반실패50→35/기존cap30→21로RuleATC보다감소했지만 P95/J/AP가악화했다. 각조건의손해를보고해이일부이득을전조건우위로부르지않는다.

48×13=624행/예정41,184요청·63,903직접snapshot, 전성공raw2,768SHA/지원·원장·공개ticket/mask/선정6PT/source/입력digest/closedclock을감사했다. 비용은모든군같은batch×sustained6조건에서미산출이라42/48(각batch9/12)만유효했다. 미산출을0이득으로대체하거나strict분모에서제거하지않았다. 개발의E/AP key도모두Infinity여서실제선정은I/U/N/P95로결정됐다. AP/J 학습 label은각224/256episode에서유효했다.

실제59학습에서6Adam·partial2/2/2/2/2/1·소비후action/shuffle RNG·clock exact복원을검산했다.128개발완료 뒤메타데이터Infinity의JSON직렬화만실패하여원driver/archive/등록을보존하고출력UNAVAILABLE와effectiveSHAguard만수정했다. 정책·학습식·weights/Adam/난수/입력·선정계산 변경0, 실패환경0·보고작업실패1이다. source_repair.json이원/수정SHA를연결하고unit8+outputguard2=10PASS다. 당시pausedPT는latest에덮여최종제3자감사에서다시재검산하지못했으며부모의당시receipt와관측범위를구분했다.

독립동시연구의PC부하가있어계산시간은공유호스트의실측기술이다. Q1/8/32/128/512 현재합성큐50표본은학습/환경0으로수집했으며실제앱부하범위나phone시간/전력으로확장하지않는다. 원서비스/물리모형·기한상한·S26열/J실패·기본정책을보존했고후속자동학습/기기실행은없다.
