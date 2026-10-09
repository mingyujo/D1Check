# v4.1 추가 토론: 구현과 학습 시작을 분리

2026-10-09 · `LIST-CANDIDATE-RL-IMPLEMENTATION-GATE-03` · **AI 추가 토론 완료, 실제 구현·native 검사·학습 미실행**

모바일·산업공학·RL 검토 AI가 사용자의 후속 검토를 다시 읽고 직접 반론을 교환했다. 결론은 **v4.1을 더 확장하지 않고 제한된 구현·검증으로 넘어갈 준비는 됐지만, 본학습은 아직 시작할 수 없다**는 것이다. 현재 새 encoder/event adapter/learner의 실제 PASS가 없다. 기존109/68 encoder의 검증을 새56/28에 전용하지 않는다.

현재 확인 HEAD는 `90782a2ec36e8ce702c211b84b9da12565eb7ec3`이다. 별도 C0·LOAD 실측2조건/본857·총추론881은 완료됐으며, 이번 RL 토론의 신규실측0과 구분한다. 원 모형SHA5682082a…bd2·초기입력·기본/strict/experiment_ready=false는 불변이다. LOAD_SLOW의 장시간 오차 개선으로 RL 모형/계수를 자동 교체하지 않는다.

[고정 v4.1](LIST_CANDIDATE_RL_PREPILOT_20261009.md) · [토론·근거·문서 검증](results/list_candidate_rl_gate_03/review_record.json)

## 1. C2는 세 증거를 분리해 확인한다

| 검사 | 실제 통과에 필요한 증거 | 미통과/불명 해석 |
|---|---|---|
| 합법 도달성 | 원점부터 등록arrival·newbank의합법index·실제dispatch/phase/AVAILABLE·credit으로 절단점에 도달 | 수동state나시간/소유주입은 산술fixture뿐. 도달 실패는 가설미재현 |
| 입력 동일성 | 실제 저장dtype/shape/bytes의state·candidate전체·slot순서·physicalmask·L0index와행동효과를결정하는pending/hold/credit/currentt/model/schema일치 | 차이경로를보고. epsilon으로지워별칭PASS를만들지않음 |
| 전체 후속 영향 | 같은등록후속선택으로나머지큐까지완주해C2개별응답과전체U/N/F/P95·J120·AP180를각각보고 | 세작업계산/첫입력동일만으로전체서비스/학습불가능을증명하지않음 |

전체 public signature에는 의도적으로 다른C2도착이 포함되므로 그해시를동일성 조건에넣지 않는다. public차이의계보와candidate캐시의재계산을별도로기록한다. 같은공개소유이력이라도arrival마다열observer를적분하는순서가달라실제tensor에차이가나면 그대로보고한다. actor에저장된dtype/bytes가판정대상이며tolerance로동일하게만들지않는다.

**최근8간격에는9개arrival가 필요하다.** C2뒤에공통arrival8개만두면C2→첫suffix의간격이입력에남을수있다. 다음9개공통suffix를검사전에고정한다.

```text
task: D,C,D,C,D,C,D,C,D       # C4/D5
arrival_j = t_nominal - 0.300 + 0.025*j, j=0..8
C2_A arrival = t_nominal - 1.0
C2_B arrival = t_nominal - 0.5
deadline offset: C1.5초 / D6초 그대로
```

초기합법prefix13요청(C4/D9)+core3(C2/D1)+suffix9(C4/D5)=**예정25요청(C10/D15)**인 작은기능fixture다. 본평가192요청의의미를바꾸지않는다. t_nominal≈41초와mean벡터로미리계획을등록하고실제event에서cut이도달했는지확인한다. CPU9개이전D/GPU4개이전C·PAIR/AVAILABLE·약0.01208초hold중소유반환은도달가설이며 아직실행증거가없다.

allD9의CPU과부하나allC9의긴급과부하로반례를왜곡하지않도록혼합을고정했지만, 이mix도서비스PASS를보장하지않는다. 결과를본뒤좋은mix/arrival/후속정책을다시찾지않는다.

## 2. 네 번의 완주에 증거를 같이 담는다

| 등록검사ID | C2도착 상태 | cut 첫선택 |
|---|---|---|
| c2_A_first_CPU | 빠른기한 | C_CPU_NOW |
| c2_A_first_PAIR | 빠른기한 | PAIR_NOW |
| c2_B_first_CPU | 늦은기한 | C_CPU_NOW |
| c2_B_first_PAIR | 늦은기한 | PAIR_NOW |

각1회의zero-origin native호출이 **합법prefix→cut 입력캡처→첫선택→같은고정risk5후속→전량원장/J120/AP180**를포함한다. 첫선택script도실제bank의허용index만고르며timestamp/소유/벡터를주입하지않는다. script도달성은bank가능성의증거이며실제온라인정책성능이아니다.

별도prefix2회나재생4회를자동추가하지않는다. 네번은기존구현gate32 native상한안에서차감하고학습은0이다. 실패도1시작차감·원실패보존·미확보wholeKPI는null이다. 추가진단/복구가필요하면남은32안의새ID/수정근거를먼저등록하고예비16을자동전용하지않는다. 순수tensor재계산·원장검산은native호출과구분한다. 총예상1520/상한1536/학습416·누적6517/641은변경하지않는다.

cut 입력이같아도C2가head로옮겨오면이후관측은달라질수있다. 고정risk5후속에서손실이회복되거나전체서비스차이가없어지면추가관측의필요성은미확정이다. 차이가남아도 **등록된후속선택안의첫선택기회비용**이며모든가능후속정책의최적성증명은아니다.

정확한도달성+입력별칭+전체서비스손실이확인될때만C2공개age/slack같은최소정보를보완한다. 상태시간의중복slot교체가능성은실제encoder/known/presence관계를검증한뒤결정한다. 행동공간·0.25초·GNN/Recurrent·보상·계수확대의근거로사용하지않는다. 별칭미재현은정보누락없음이나RL실패의증명이아니며해당가설의미재현이다.

## 3. 대기 편향은 실제시간으로 검사

과거P95=.25초, L0=.18초, 후보=.20초면risk5 긴급proxy항은둘다0이다. 의도한동률영역이므로그자체가버그는아니지만짧은단원AP/J가대기를선호하는지는실제원장으로확인해야한다.

연속대기는두실제dispatch사이에이뤄진distinct hold선택수다. phase/arrival callback수와분리한다. 누적자발대기는활성hold의**실제양의시간구간합집합**이며선언한.125/.25초를단순합산하지않는다. hold_id/decision_seq·시작/중단/만료·종료사유·last_debit_at·credit전후·credited_dispatch_ids를남긴다. 같은시간중복차감/콜백충전은금지한다.

mixed첫dispatch는credit을갱신하므로구간내.25초가전체요청의누적대기한도는아니다. 요청별도착→응답·보류head·자발hold·점유에의한forcedwait·실행가능자원유휴·CPU/GPU점유/실제실행병행을분리한다. fallback횟수와분모도기록하고observer-only/중복callback을선택횟수로세지않는다. 임의연속wait횟수나fallback비율기준을새로만들지않고기존서비스·전량·비용KPI와후보coverage로판정한다.

고정selector만이긴결과는그등록대조대비성공이다. L0/Band/Triton·같은서비스의전체KPI·전3seed·새확인을함께충족해야RL추가가치를말할수있다. 고정selector도최종통과하고동률이면더단순한비학습방법을추천한다.

## 4. λJ 로그와 학습 시작 조건

λJ=0에서검사할것은 **명시적actor에너지항−λJ·A_J=0**이다. 공유critic의J value-loss는stateencoder를바꿀수있고Adam과거momentum·entropy·AP/서비스항·다음dual갱신도남으므로weights/logits전체불변을기대하지않는다. target·channelvalid·AP증분/180초합·signedJ·원advantage·결합/정규화항·actor/critic/encoder별gradient·λ경로를구분한다. 에너지형발견유무만으로현재보상을바꾸지않는다.

공개event누락/미래누출·lane조기해제/중복배정·요청누락·credit오류/시간정지·기존원장/clock/예산회귀·source/model/지원불일치·불명을안전0으로채움·32상한초과가있으면학습하지않는다. 실제encoder별칭때문에서비스손실이남으면정보보완재검증전학습보류다.

C2가정상적으로미재현됐다는이유만으로계획을무한확장하지않는다. 다른필수기능·재개동일성·coverage/표현성·보상/학습집계gate가통과하고유의미한실행대안이남으면등록된작은파일럿으로진행할수있다. 모든선택이강제/L0복귀이거나개선가능선택의근거가없으면본학습을늘리지않는다. **현재는그실제PASS가없어학습NO-GO**이며이번요청은토론만수행했다.
