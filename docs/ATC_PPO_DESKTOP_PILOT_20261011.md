# ATC-PPO-DESKTOP-PILOT-01 구현·실행 계약과 결과

2026-10-11 KST. 기준 HEAD 3b54a74b80f7c61ae140eb71b4985c38c2abbb27. [전체 결과·CSV·그림](results/atc_ppo_desktop_pilot_01/README.md)과 [사전등록](results/atc_ppo_desktop_pilot_01/registration.json)을 함께 따른다.

**A24의 새 사건 기반 온라인 선택기를 구현하고3seed 각64 학습·개발·새48조건 확인을 완료했지만 세 PPO 모두 원 strict FAIL이다.** 신규 채택0, 기본/strict/experiment_ready=false 유지다. S26은 세 고정 tree·추가4문서의 읽기 감사와7구간 adapter 검증을 완료했으며, 현재 혼합 품질·정밀도·시각·비용프로필 gate가 부족해 학습/성능 평가를 보류했다.

## 범위·보존·실제 소비

- 기존 dirty checkout의 설계 문서4개와13434b4 HEAD를 보존했다. 최신 원격3b54a74를 별도 detached worktree로 확보했고 실행 중인 기존 보고 서버를 중단하지 않았다. reset/clean/dirty pull/강제push/세S26브랜치merge는 하지 않았다.
- 실제 호스트는 Windows11 Home26200/Ryzen5 5600/15.94GiB/RTX3050이다. 프롬프트의RTX3060과 달랐으며 호스트GPU를 휴대폰GPU로 취급하지 않고 CPU부터 실행했다.
- 별도 Python3.11.9 venv의 NumPy2.4.6/Torch2.11.0+cpu/Matplotlib3.10.9를 사용했다. 기존 패키지·원64→512 상태는 보존했다.
- 새 과제 소비는 환경791/1536, 실제학습192/384(A24만192, S26 0), 실행 활성343.312초/240분이다. 마지막10분 저장 경계와 원자 저장을 적용했다. 설치/ADB/기기 실행·새물리계수 재적합0이다.
- 환경791에는 원자료 없는 단위시험의 환경호출11, 동결demo3, 새 실행gate8, 학습192, 개발32의168, 개발64의PPO72, 새 확인336, 호스트 결과기록 오류1이 포함된다. 오류1은 실패로 남기고 별도retry1로 정상행을 회수했다. 과거 종료 소비/시계는 초기화하지 않았다.

## 기존 구조와 새 구조

기존 rolling/service-envelope PPO는 창4의 계획 열거·선별8 및 각 후보의 전체 현재 큐 소진·응답·J/AP 예측을 bank/encoder/서비스mask에 사용했다. 최신 JointList 복귀도 전체큐 분할 배정안을 예측하므로 직접 구조에 그대로 호출하지 않았다.

새 경로는 task별FIFO 선두, ATC top1, 현재 실행 가능 선두와 선두L0 보충,7행동 템플릿, 물리mask, 새nativePPO 또는 같은bank의 비학습Rule이다. 아직 시작하지 않은 요청만 사건에서 재판단한다. 미래 구간 최적화를 하지 않아 사건 기반 온라인 스케줄링이며 롤링은 반복 재판단의 의미다.

~~~mermaid
flowchart LR
 E["도착·실제 AVAILABLE·자원timer"] --> O["공개관측 갱신"]
 O --> C["FIFO 선두·ATC·가능후보 보충"]
 C --> M["현재행동·물리mask"]
 M --> P["고정PPO/같은bank Rule"]
 P --> D["dispatch 또는 자원wait"]
 D --> E
~~~

분류urgent CPU/GPU, 탐지normal CPU, CG_DC 최대2병행만 유지한다. output/persist 응답과 실제AVAILABLE 소유 종료를 분리한다. 선점·이동·NPU·탐지GPU·세건병행·냉각유예·새주파수/전력제한을 추가하지 않았다.

## ATC·추정·후보

원형은 I=w/p·exp(−max(d−t−p,0)/(k·평균p))다. 앱 수정식의 음의로그 S=log(p_occ)−log(w)+max(d−t−p_resp,0)/(k·평균p_occ)를 최소화한다. p_occ는5phase 전체 점유, p_resp는분류2/탐지3phase다. 대표 경로는 지원경로의 최소점추정 점유시간이며 동률CPU다. busy/후속queue 실행을 대표p에 넣지 않는다.

모집단은 현재FIFO 선두 최대2개 중 유효추정이다. w_U2/w_N1,k2,top1,완성된 공개5구간의EWMA.1을 결과 전에 고정했다. 가중치는 정책 입력이며 실제지연비용·문헌의 보편 기본값이 아니다. 미지원/비유한p를0의 유효추정으로 치환하지 않는다.

동점은 arrival_ns/ordinal/id로 해소한다. 후보는request_id로 중복 제거하고C/D 슬롯순서를 고정한다. task내 뒤요청을 선택하지 않되 두번째C/D의 공개 납기와 적체·과거 도착 이력을 모든 직접 비교군에 제공한다.

확인의 직접판단25,352상태에서 ATC/EDD 후보bank·유효행동은 모두 같았다. encoder도 ATC점수/순위를 입력하지 않으므로 후보선정의추가효과가 없었다. **ATC튜닝·중복PPO학습을 중단한다.** EDD후보+직접선택을 후속대안으로 남기며 미래계산제거 효과와ATC효과를 구분한다.

## 실제 ABI와 선택

|입력/행동|실제 명세|
|---|---|
|state float32[90]|global24 + C/D후보18×2 + CPU/GPU소유15×2|
|global24|시간/큐개수/최고대기/두번째C·D남은납기/점추정적체량/과거8도착간격·D부하율과known/현재관측AP·기울기·과거최고/관측긴급P95와수|
|후보18|present/task/priority/age/남은납기/w/CPU·GPU지원/점유·응답p와valid/대표추정관측수·경과|
|소유15|owned/task/response_done/6phase one-hot/dispatch·phase경과/잔여점유추정valid·overrun|
|action float32[7,23]|present1+kind3+jobbinding10+waitbinding4+선택경로p4+선두L0표식1|
|행동7|C_CPU/C_GPU/D_CPU/CG_DC/WAIT_C_CPU/WAIT_C_GPU/WAIT_D_CPU|
|마스크|현재미시작FIFO 후보·지원·실제lane소유·허용병행·중복요청/자원·패딩. 납기/P95/AP/J의미래성능조건없음|
|실제WAIT|현재owner가해당경로를막을때만. 새도착/AVAILABLE/등록자원반환점추정timer에서재판단. 동일첫반환을기다리는WAIT별칭은중복mask|
|정규화|고정초/1500ms/6초/log개수/중심AP단위, 연속clip±10. 결측valid·패딩을분리. 확인자료로재학습0|

현재AP는 기존동결모형의 과거·현재실행으로 생성하는 **시뮬환경 관측**이다. 실제HAL관측이나표면온도가아니며 숨은H/slow는neural입력에없다. 실기기센서경로의이식은별도미검증이다.

native masked categorical/MLP와 PPO clipping·기존episode-sum actor/episode-mean critic·minibatch loss를 재사용했다.90→64→64,23→32→32,결합96→64→1,critic6으로fresh weights/Adam을만들었고기존56/8×28actor는전용하지않았다. E/Q비용은고정가중치1,절대미완료·긴급·일반실패율만0목표dual이다. APpeak telescope·J증분·P95비용의단위와γ1/GAE없음을사전등록했다.

## 사건·오류·안전 경계

같은시각은실제CPU phase/반환→GPU phase/반환→ordinal도착→기존pending 완료→새판단의엔진순서다.0길이phase는다소진하고AVAILABLE전소유를유지한다. PAIR는GPU-C 뒤CPU-D의두번째commit을실제첫영수증·owner·동시간·FIFO/idle/지원으로재검사하며실패한두번째요청은queue에남긴다.

빈queue는모델호출없이idle,모델/ABI/비유한값오류는지원된선두L0로복귀한다. 반복3오류면모델을disable한다. owner추정overrun을실제빈lane으로바꾸지않는다. 중복event/dispatch는거절하고같은판단revision은재실행하지않는다. 정상전부busy에는강제자원wait가있으며무기한busy polling/냉각을추가하지않는다.

실제새정책콜백에서는원rollout/place/미래AP·J계산함수에trap을걸어재유입을차단했다. 후보·mask·복귀에서virtualqueue를끝까지실행하지않는다. 원장·지원·phase·응답·AVAILABLE·rawSHA전량검산을마쳤다.

## 학습·확인과 판정

각seed11/23/37의초기화/행동sample/shuffle generator를분리했다.환경arrival/realization과도분리했으며같은trace·실현5phase·기한·초기·모형·관측창으로7정책을대응했다. 개발32/64와새확인48을분리하고확인전seed/epoch선택을동결했다.

29학습의전체원자bundle에서부분2/2/1·nonempty Adam·각RNG·cursor·소비를별도프로세스가exact복원했다. 실제활성시간/실패도원장에누적했다.영수증dataclass와Band행label오류,미완료dev32단계재개처리만driver수정영수증으로보완했고정책/목표/학습식/Adam은리셋하지않았다.

각64/8update,Adam step156/152/160,actor변경8update씩이다. 새48의모든정책3168/3168완료·긴급실패0이다. 일반실패는Band48/Triton48/EDD74/Rule48/PPO각48이다. PPO11은Rule48일정exact,23/37은Triton48일정exact다. PPO11/Rule은Band대비평균J+.049064/AP+.002624°C로탈락한다. 다른두PPO는Band대비P95/J/AP가악화했다.

원조건별epsilon0·완료/서비스/P95/J/AP비악화·low/sustained절대서비스·주부하군엄격한축개선기준을유지했다. 세seed최종FAIL이다. 복잡한학습방법의추가이득이없으면단순Rule을우선하되그Rule도기존기본교체로채택하지않는다. 남은예산자동사용/NoWait/열제거/128·512확대0이다.

## S26 추가자료와 남은 gate

세고정tree를merge없이별도sparse확보했다. 사용자추가4자료는근거로읽고그안의재계산·재피팅·설치명령은실행하지않았다. 코드/계수22개LF/바이트일치,69manifest/관측48480요청7구간adapter PASS,18stress시도·원장없는실패4를분리했다.

Q20품질의APK/입력/runtime/thread/정밀도귀속을유지하고GPU실제정밀도·혼합품질승격보류를확인했다. 오래된MobileNet/CPU4/FG-BG chunk의정책홀드아웃과최신CPU1/exact mixed를합치지않았다. 구홀드아웃1200행cloud재현주장은첨부문서의주장이며이번에재실행/독립확인하지않았다.

대표R4C의정기power239와admission204,μA단위,AP/SKIN분리,HAL bracket미관측을재확인했다. 에너지교정/상태별식별·혼합원시프로필이검증되지않아S26환경학습0이다. 최소추가근거는exact mixed품질·정밀도연결,동기화·coverage·상태지원감사,서비스/열/전력모형의사전동결된독립확인이다. 이번기기예산0,호출/실측계획만후속문서로남긴다.

## 공유·검증 경계

공유는새source/설정/작은CSV/그림/HTML/체크포인트metadata다. 모델binary/APK/NPU AOT/키/원실측/큰raw/PT는추가하지않는다. 기존raw필수3suite는미실행으로남긴다.

PNG와HTML정적데이터/링크는검산했다. 보고서서버실행은자동실행정책에서거절됐고브라우저의file:프로토콜도차단되어 **브라우저UI의필터동작은미확인**이다. 정책차단을우회하지않았다. 이제약을대시보드전체browser PASS로표시하지않는다.
