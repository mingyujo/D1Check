# S26 NPU 포함 서비스 비교 실행 계약 — 2026-10-11

상태: S26-NPU-SERVICE-COMPARE-01 구현·학습·비교 완료. 아래 계약은 첫 환경 실행 전에 등록했으며 [완료 결과](results/s26_npu_service_20261011/README.md)에 실제 소비와 판정을 기록했다. 사용자 최신 지시는 현재 자료로 NPU 포함 시뮬레이터와 FIFO/EFT/EDD/ATC/PPO 서비스 비교를 실행하는 것이다. 기존 설계 단계의 실행0회는 당시 이력이며 이번 실행으로 소급 덮어쓰지 않는다. 에너지·발열은 이번 보상/정책/평가에서 null, 물리 적합/APK/기기 실행0이다. 기본 정책과 experiment_ready=false, 기존 strict/FAIL을 유지한다.

## 지원과 자료

분류 CPU/GPU/NPU, 탐지 CPU, 분류GPU+탐지CPU 또는 분류NPU+탐지CPU 최대2건이다. 비선점·중복 dispatch 거부·실제AVAILABLE까지 점유·긴급output_ready/일반persist_complete 응답 계약을 유지한다. 탐지GPU/NPU·두 가속기 분류·분류CPU+가속기·3건 병행은 거부한다. 기존 NPU 품질 미확인을 서비스 탐색 실행의 PASS로 바꾸지 않는다.

upstream s26-parsim994ca614의 a24fmt_v1 S0 6셀과 R3 3072요청을 단계 이름/단위ns/개수/평균으로 검산한다. CPU1 EfficientNet/EfficientDet, NPU/병행 서비스 자료만 가져오고 power/theta를 가져오지 않는다. 원5단계 intact vector를 키(environment seed,request ID,context)로 뽑아 순서/정책/RNG에 무관한 잠재 처리시간을 공유한다. 세션 문맥을 순간 dispatch에 적용하는 가정, 단독가속기/부분겹침 검증 부족, 고정 CPU 서비스와 약120초 이내 제한을 명시한다.

R3 학습 session index0/1/2/3/8/9/10/11, 개발4/5/12/13, 확인6/7/14/15다. 공개 경로 평균은학습8세션만 사용한다. 확인은 새 가상 요청열/난수에 대한 확인이며 이미본R3를 새 blind 실기기 확인으로 주장하지 않는다. intact 요청 내부 상관은 유지하고 세션 내부 시계열 상관은 복원하지 않는다.

## 정책 계약

전체 현재 도착·미시작 큐를 검토한다. FIFO 주군은 실행 가능한 가장 오래된 요청(FIFO_READY), EFT는 현재 feasible 요청/자원의 예상응답 최솟값, EDD는 absolute deadline, ATC는 아래 점수에 현재 EFT 배정을 붙인다. 선두고정 FIFO_HOL을 별도 보조군으로 둔다. 모두 같은work-conserving 운영조건/지원/품질 연구 범위다.

ATC 앱식은 `log(w_i)-log(p_i/1s)-max(d_i-t-r_i,0)/(k*pbar)`: w긴급2/일반1은 연구 중요도, k2, p는대표경로점유시간, r는대표경로응답시간, 대표경로는현재 공개평균응답이 최소인 지원경로다. 자원 대기는mask에서판단하고 future queue rollout 없이 현재 요청의 경로만 계산한다. 원형 `w/p*exp(-max(d-t-p,0)/(k*pbar))`의 응답/점유 구분 수정이다. EDD/ATC 동일 순위·top4비율을보고하고 확인결과로k를재튜닝하지 않는다.

PPO 후보는 ATC top4+oldest C/D+EDD 복귀 요청+fastest feasible 요청의중복제거합집합≤8이다. 모든 현재실행가능요청을누락하는경우를방지한다. 단일3C+D, 병행2CD, 자원wait1이므로 C+D≤8일때≤49행동, pad64다. 물리mask는점유/미지원/중복/병행위반, 운영mask는실행행동이있으면WAIT억제를별도로적용한다. padding은mask0다.

state=8request×20+3resource×8+8global=192, action feature32, 단일service critic1이다. 요청은task/priority/age/기한/3경로응답·점유/지원/ATC/arrival/ordinal/present, resource는owner task·priority/phase/elapsed/공개평균remaining, global은now/queue·urgent·classification비율/후보수/점유/관측응답수/capability다. ms/ns→6초/120초 기준정규화, signed값clip±10이며차원을검사한다. 정확실현잔여시간·미래도착·J/온도·전체큐일정은입력에없다. 모델오류는현재EDD로복귀하고학습오류가생기면실패로원장기록후중단한다.

## 학습·확인과 유한 예산

새weights seed501/503/509 각256episode, batch8·native weighted clipped loss/Adam3e-4·clip.2·최대4epoch·KL.03·gamma1/MC다. 에너지/온도 critic이나A24weights를사용하지 않는다. incomplete50/n, 긴급원/요청실패각20/nu, 일반각5/nn, 긴급응답.2/(nu*1.5s), 일반.1/(nn*6s), weighted normalized tardiness를음의보상으로쓴다. 모든단위는무차원이며실제경제지연비용이아니다. label은완료후관측결과로만만든다.

개발32조건에서64/128/256checkpoint를 lex incomplete→원U→요청U→원N→요청N→servicecost→긴급P95로선택한다. 동점은이른checkpoint/seed다. 보상가중합과서비스보호우선선정의차이를공개한다. 대표를확인전에동결하고최종deterministic argmax·canonical tie, 확인후재선정/학습자동확대0이다. 59episode/7update+pending3를저장·복원해optimizer/RNG/pending exact SHA를검사한다.

4부하(low20s/steady10s/burst4×16/overload2s)에64요청(C32/D32), 원기한1.5/6초와가변긴급.5/1/1.5·일반2/4/6초를준다. 부하와기한은공학적시험입력이며측정도착분포라고주장하지않는다. 학습256/개발32/확인64는arrival·service난수영역분리, original/varied pair는같은도착·servicekeys다. 환경/action/shuffle RNG도분리한다.

본환경예정1952=학습768+개발416+확인512(4규칙+3PPO+FIFO_HOL)＋규칙NPU-off256. cap2200환경/768학습/활성1800초·저장120초이며기존A24예산자동승계0이다. 소스/입력/모형SHA를첫환경전에등록하고모든시작·완료·실패를보존한다. 예산/계약실패시중단·부분결과저장, 실패무시/대체/확인뒤튜닝없다. 사전합성계약검사는기기환경과별도다.

전체도착분모의미완료·원/요청실패·P95·평균·weighted miss/tardiness를조건별/부하별/seed별보고한다. 서비스guard는epsilon0 casewise각규칙대비비악화와low/steady 원서비스실패0/전완료다. 기존전체strict는J/AP/품질gate가미확인이라UNAVAILABLE, 자동채택0이다. 평균이득으로악화조건을숨기지않는다. 규칙NPU on/off와PPO학습효과를분리하고이번off에는PPO재학습이없으므로순수PPO NPU효과는주장하지않는다.

ATC/후보·마스크·인코딩/PPO/전체판단의PC 평균·P95·max를저장하고queue1/8/32/128/512에서현재상태계산만벤치마크한다. 이를휴대폰판단시간이나소비에너지로해석하지않는다. 최종산출은outputs/S26-NPU-SERVICE-COMPARE-01/README.md·comparison/summary/paired_deltas/npu_ablation/decision_timing/verification이다. 원자료/rollout/models/실행원장은work/S26-NPU-SERVICE-COMPARE-01에보존한다.
