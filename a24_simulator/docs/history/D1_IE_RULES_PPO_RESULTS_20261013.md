# 산업공학 공통 배정 비교·PPO 후속 결과 (2026-10-13)

상태: **AUDITED_COMPLETE**. 24회차의 정적 소스·등록 SHA와 실행을 보존하고 별도26에서 수행했다. Git HEAD `12d64923be824ce4c88fca074fbe38820f5a7d25`/detached이며 사용자와 다른 작업의 미커밋 변경은 유지했다.

SPT·WSPT·EDD·LST·ATC에 동일 자원 배정기를 적용했고 DEV에서 ATC·EDD를 고정해 DIRECT/ATC 후보+PPO/EDD 후보+PPO 각3seed의 48→96회 학습까지 수행했다. 최종4도착seed·192조건×14정책=2688행을 모델 동결 뒤 고정 argmax로 확인했다. 확인 자료로 규칙·모델·seed를 재선정하지 않았다.

에너지는0~120초 총J, 평균AP는35~180초 시간적분/145초다. **기존20의 추가8/1/.4W·열/감속·탐지.35배는 탐색 가정**이다. 이번 결과는 PC 모형의 차이이며 실측 모바일 절감·절대J 인증·원strict PASS가 아니다. 다른M6 새fit을 혼합하지 않았다.

## 핵심 판정

**이번 비교에서 ATC의 추가 비용 효과는 입증되지 않았다.** 전체 96조건 중 모든 방법이 서비스 기준을 지킨 교집합은 A24 28조건, S26 62조건이다. 이 조건부 범위에서 ATC 후보+PPO의 3시드 평균은 ATC 대비 A24 −0.017594J·+0.001416℃로 상충했고, S26 −0.252692J(−0.1118%)·−0.003513℃로 작게 개선됐다. S26에서도 3시드 평균 기준 두 비용 중 하나가 악화된 조건이 13/62개여서 공동 비악화로 채택하지 않는다. 전체 조건의 서비스 탈락과 미완료는 원표에 남겼다.

S26의 직접 PPO도 −0.252252J·−0.003513℃로 거의 같았다. 따라서 이 감소를 ATC 후보 선정의 효과로 귀속할 수 없다. EDD 후보+PPO는 −0.253737J·−0.003531℃이며, 두 후보 방식의 작은 차이도 실측 우위로 주장하지 않는다. 기본 교체와 추가 ATC 파라미터 튜닝은 보류한다.

ATC/EDD 결합 모델의 학습 실행 원장과 사건열은 각 시드 96/96회, 합계 288/288회 동일했다. 신경망 가중치는 서로 달랐으므로 입력·후보·가중치가 모두 동일했다고 해석하지 않는다. 서로 다른 특징을 줬어도 학습 중 실제 실행이 구별되지 않은 결과다. [학습 동형 검산](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/HYBRID_TRAIN_EQUIVALENCE.json>).

사전 주평가 범위는 light32·steady다. 이 범위에서 모든 규칙과 PPO의 비용 차이는 정확히0이었다.
주범위에서 공통 배정 후 복수 요청 행동이 없으면 순위를 선택할 여지가 없다. 물리적으로 다른 CPU/GPU/NPU 경로가 없다는 뜻은 아니다. 이번 공통 배정기는 요청마다 경로를 하나로 제한하므로 자원까지 선택하는24PPO의 잠재 효과를 제거한 순서 대조다. 이 구간은 서비스 회귀 확인에는 유효하지만 순서 규칙의 비용 우열을 식별하는 주평가로는 부적합하다. 사후에 주범위를 바꾸어 우위를 주장하지 않는다.
ATC/EDD는 주범위 비용이 동률인 상태에서 서비스와 서로 다른 DEV 원장을 포함한 사전 기준으로 선택됐다. 에너지/온도 우승 규칙으로 선정된 것이 아니다. 산업공학 규칙에는 에너지 최적성 보장이 없고, 비용 차이는 순서가 가용 자원/경로/병행/열 이력을 바꿀 때 발생한다.

## 공통 서비스 조건의 비용

아래 all_policy_common_sla는5규칙과9PPO가 전량완료·원/선언 납기 무위반인 동일조건 교집합이다. PPO 숫자는3학습seed 평균이다. 조건 교집합은 결과로 정해진 조건부 범위이므로 전체192조건/주범위·제외분모와 같이 읽는다.

|기기|정책|조건|J|평균AP ℃|ATC대비ΔJ|ΔAP ℃|
|---|---|---:|---:|---:|---:|---:|
|A24|SPT|28|197.573903|35.724740|0.000000|0.000000|
|A24|WSPT|28|197.573903|35.724740|0.000000|0.000000|
|A24|EDD|28|197.573903|35.724740|0.000000|0.000000|
|A24|LST|28|197.573903|35.724740|0.000000|0.000000|
|A24|ATC|28|197.573903|35.724740|0.000000|0.000000|
|A24|DIRECT|28|197.556164|35.726155|-0.017739|0.001415|
|A24|HYBRID_ATC|28|197.556309|35.726155|-0.017594|0.001416|
|A24|HYBRID_EDD|28|197.556309|35.726155|-0.017594|0.001416|
|S26|SPT|62|226.043558|33.763648|0.015022|0.000330|
|S26|WSPT|62|226.043558|33.763648|0.015022|0.000330|
|S26|EDD|62|226.027424|33.763298|-0.001113|-0.000020|
|S26|LST|62|226.023424|33.763226|-0.005112|-0.000091|
|S26|ATC|62|226.028536|33.763318|0.000000|0.000000|
|S26|DIRECT|62|225.776284|33.759805|-0.252252|-0.003513|
|S26|HYBRID_ATC|62|225.775844|33.759805|-0.252692|-0.003513|
|S26|HYBRID_EDD|62|225.774800|33.759787|-0.253737|-0.003531|

5규칙끼리의 공통SLA·전량완료 비용은 [COMPARISON.md](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/COMPARISON.md>) 및 [rule_pairwise.csv](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/rule_pairwise.csv>)에 남겼다. 전체정책 전량완료 범위(equal_work)는 납기 위반이 남으므로 진단이며 채택 표가 아니다. full에서 비용결측이 있으면 해당전체 평균은 미산출로 보존했다.

## PPO와 학습 신호

같은fresh 초기NN·빈Adam·행동/셔플난수1523/1529/1531에서 시작하고 같은96요청열을 교대로 학습했다. 기기별48경험이고 경험의 단위는 전체요청열이다. 환경난수와 행동난수는 분리했다. 이전24/21가중치를 초기값으로 쓰지 않았다.
PPO는 요청을 선택하고 공통배정기가 현재 합법경로 중 예상응답→점유시간→backend 순으로 자원을 정한다. 따라서 이번 결과는 자원까지학습하는24전체정책의 대체검증이 아니다. DIRECT는전체ready,HYBRID는rule top4+oldest C/D 보충(최대6)이다. 후보제한+rank특징을 묶은 대조이며 순수특징효과가 아니다.
완료학습864개 중 비용보너스가 비영이고 선택 여지도 있었던 경험은110개다. [training_cost_signal.csv](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/training_cost_signal.csv>)에 서비스적격/비용유효/비영보너스/선택프레임을모든seed별로공개했다. 전량·무위반gate 때문에 비용신호가희소하며 주범위동형은0보너스다.
보상과MC gamma1·PPO설정은기존21그대로이며 GAE0이다. 기한안응답/P95벌점·선정0, 비용항은총J와평균AP의softsign 합이라상쇄가능하다. 양의보상을두비용동시개선으로해석하지않는다.
체크포인트 선정은 서비스우선 및 사전 주범위비용key다. 주범위선택여지가0이면 비용key도구분력을잃는다. 이 선정식으로 burst비용의 최선체크포인트를 골랐다고주장하지않는다.

|군|seed|최종선정학습회수|동결SHA-256|
|---|---:|---:|---|
|DIRECT|1523|48|`5c59bbd33c16e11b9c57a11b922c598077cc93a186822507d00fe6d9a6b8dd57`|
|DIRECT|1529|96|`8ad1821be2135f21bc665035d11b9a582d7ad20645155579b3b8d3443eb3faac`|
|DIRECT|1531|48|`27c3fbd93b031e219515b2e884ae532dcfb5f0f5214bda996f1124061d551dae`|
|HYBRID_ATC|1523|48|`a4a6d0c914a6462703cd837fd7467ac3953d0110dbc78769043db17892ffffde`|
|HYBRID_ATC|1529|48|`03cadf55dc0889744bfef3855f53d3df2a1bf0f62369fab2a6fa28f86a0d2b98`|
|HYBRID_ATC|1531|48|`2eef291d02dda5d7977ae7a8ae35ba22d1cd2961a4362abac058a6a5167aae56`|
|HYBRID_EDD|1523|48|`de618ddc0f4c410f7d861ffb6be6c6a05d18f06a370fa23dc4467a222f21fbf6`|
|HYBRID_EDD|1529|48|`48365dc2a0d2ed6dff5d313314c36230ce16613e629885c8dc763e7f95b34909`|
|HYBRID_EDD|1531|48|`f86d33197096e4fdd9dc08a779f81b141218da3a5eda7000bf334421ef41f321`|

## 실행 계약·검산·소비

전체 도착·미시작큐(max64), 지원된C_CPU/C_GPU/S26C_NPU/D_CPU 및CG_DC/CN_DC 최대2, 비선점·실제AVAILABLE 점유·응답/점유종료분리·non-delay를유지했다. 미지원병행/임의냉각대기를추가하지않았다. 큐의미래rollout·미래도착/실현시간/J/온도를online입력하지않는다.
처음C용량경계와USB지연으로축소했던V7도보존했다. 사용자가C를확보한뒤FINAL0에서V8로원래48/96·전체확인범위를복원하고원시작부터6시간/최종reserve15분·시작cap6000/완료학습864를등록했다. 2509파일SHA검증복사·성공경험재수집0·D원본삭제0이다.
legal-only NN평가는같은확률/가치·gradient최대2.24e-8의수치검산을통과했다. 수학적동형이고Adam과정의비트동일성은주장하지않는다. 묶음forward argmax검산1회실패는확률2.98e-8의반올림동점이다. V9에서정책을바꾸지않고실제batch1 행동/likelihood/value exact검산을추가했다. 최종단계추가검산에서batch1 불일치0이며수치로그와모든실패를보존했다.
실제시작4999·완료4992·실패7; 학습시작865·완료864·실패1; native업데이트108·Adam1296; FINAL2688행. 신규fit/APK/기기0이며프로젝트기존누계를0으로덮어쓰지않았다.
순수5검사와scalar/candidate/snapshot수치검산, 전raw/frameSHA·물리owner/AVAILABLE·공통배정·mask부분집합·MC return·FINAL전체행렬·소비원장·모든9개partial59 직렬화NN/Adam/pending/RNG복원·동결모델SHA·원24정적소스/등록SHA를검사했다.
시간은 공유 PC 기준이다. Controller의 build/total 시간은 Audit이 먼저 계산한 pack을 memo 조회하며 전체 이벤트→dispatch 시간이 아니다. 평균/P95/최대·큐 구간을 부분 타이머 표로만 남겼고 폰 시간/에너지로 환산하지 않는다. 정책별 판단·PPO 추론의 추가 지연/소비도 폰 실측으로 분리 반영하지 않았으므로 모형의 작은 차이를 실제 순절감으로 해석하지 않는다. [DECISION_DIAGNOSTICS.md](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/DECISION_DIAGNOSTICS.md>)

## 다음 단계 제안과 채택 경계

이번결과만으로기본정책/원strict계약을변경하지않는다. 평균공동개선이있어도개별seed·조건손해와서비스탈락을확인해야한다. ATC필수우위/공통PPO범용우위를전제하지않는다.
후속주평가영역은별도의개발자료에서실제복수행동이있는동시대기·병행조건이면서전량/납기를만족하도록선정하고새등록·새확인을둔다. 이번FINAL을맞춰부하/납기를수정하지않는다. 비용체크포인트선정도서비스적격·선택가능영역의J/AP를반영하도록새실험에서명시해야한다.
원24의자원선택까지학습하는방법과결합하려면공통배정/학습배정의교차대조를추가한다. 본26은그효과를검증하지않았다. 휴대폰효과주장에는자료기반기기별전력/열모형의독립확인및같은APK·같은일량실측이별도로필요하다. 이번후속제안의추가환경/학습/기기실행0이다.

근거: [COMPLETION.md](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/COMPLETION.md>), [compact_policy_comparison.csv](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/compact_policy_comparison.csv>), [all_rows.csv](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/all_rows.csv>), [FINAL_AUDIT.json](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/FINAL_AUDIT.json>), [ACTUAL_CONSUMPTION.json](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/ACTUAL_CONSUMPTION.json>), [ACTUAL_BATCH_REPLAY_AUDIT.json](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/ACTUAL_BATCH_REPLAY_AUDIT.json>), [CHECKPOINT_RESTORE_AUDIT.json](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/CHECKPOINT_RESTORE_AUDIT.json>), [selected_models_before_final.json](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/selected_models_before_final.json>), [C_FAST_FULL_SCOPE_REGISTRATION_V8.json](<C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/ie26_fast/outputs/D1-IE-RULES-PPO-26/C_FAST_FULL_SCOPE_REGISTRATION_V8.json>).

원설계: [D1_IE_RULES_PPO_STUDY_20261013.md](D1_IE_RULES_PPO_STUDY_20261013.md).
