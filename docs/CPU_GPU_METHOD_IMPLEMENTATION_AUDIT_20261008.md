# CPU GPU 방법론 선정의 구현과 근거 감사

2026-10-08 · `CPU-GPU-METHOD-PILOT-01`

이번 작업은 A24 CPU/GPU의 기존 동결 모형에서 후보를 같은 조건으로 비교한다. NPU·새 모델·새 앱 기능·선점·주파수/전력 제어·실기기 측정을 추가하지 않는다. 평가 결과와 선정은 [파일럿 보고서](results/cpu_gpu_method_01/README.md)에 기록한다. 원 실측과 과거 결과는 보존한다.

## 확인한 현재 상태

착수 HEAD `2ace32f801f1dbcfb5bc916ae10cc88732e00b63`, `feature/arrival-scheduling-20260923`. STATUS에는 이전 설계 완료 이력이 있으며, 실제 작업 트리에는 새 controller·PPO·실행기 코드와 미공유 prototype 결과가 있다. 사용자 STATUS14행·HTML/PDF·개인 설정·다른 worktree는 이번 변경에서 제외한다.

현재109/68 구조로 학습한 기존 checkpoint는 없다. `output/edd_ect_residual_learning_20261008_v1`에는 입력·예산 등록만 있고 환경 시작/learner owner/학습 archive가 없다. 이전85관측/17행동 PPO 결과는 다른 알고리즘/목적 계약의 근거이며 새109/68 network에 읽어 넣을 수 없다. 다른 연구 단계의49,152episode 결과와 이번 별도6,144episode 상한을 혼합하지 않는다.

기존 prototype는12조건5정책60행·분기12쌍, 실제환경91회(실패1 포함)·학습0으로 완료했다. 원 BASE 일정/예측을 확인했으며 저부하의 작은 AP 감소와 지속부하 손실을 함께 보고했다. 이번 비교 전 누적은2,916/20,000환경·학습0/6,144다. 준비했던3×2,032 학습을 자동 실행하지 않고 작은 맞춤 파일럿으로 진행한다.

## 현재 EDD+ECT 기반 RL의 실제 구조

| 항목 | 코드에서 확인한 동작 |
|---|---|
| 기본 규칙 | `tools/d1_ie_dispatch.py`: 절대 응답 기한 EDD, 자원은 mean5단계 전체 lane 완료 ECT |
| EDD의 후보 제한 | 현재 도착 Q를 EDD로 정렬하고 앞8요청을 RL 후보에 넣음. 예측은 후보 밖을 포함한 현재 Q 전체 |
| RL 제어 | 요청/backend 단건, 분류GPU+탐지CPU 묶음, 추가 냉각 대기. 규칙 이름만 선택하는 방식 아님 |
| 행동32slot | 최대30원 후보를 중복 제거하고 빈 slot mask. 원 BASE와 동일 행동에는 prior를 한 번 부여 |
| 판단 시점 | 도착·공개 phase·lane 가용·선택한 timer. 동일 공개 상태/시각 재호출은 재추첨하지 않음 |
| 실행 ABI | 단건 selected 반환. 묶음 둘째는 같은시각에서 실제 점유·큐·lane을 재검사하여 확정 |
| C 알고리즘 | native PyTorch masked Categorical + clipped PPO. actor에 mask를 적용하고 저장한 mask/후보로 optimizer를 재평가. SB3 패키지 구현은 아님 |
| C mask | 실제lane/지원 조합/slot/냉각 credit + 세문맥 현재Q의 예상 실제기한/120초 반환. 예측 검사이며 미래도착/실현오차 보장 아님 |
| C 목적 | AP 격자 최고 증가의 음 보상,180초tail 포함·γ1. 종료 후 EDD/Shared/Band 대비 J/완료/서비스/P95 악화5cost |
| 신경망 | 상태109·후보68·각64→64Tanh·결합128→64→1. critic6head, 처음BASE확률0.9 |
| 관측 | 도착 Q·공개lane의request/phase/since/dispatch·관측한 응답 통계·과거 도착 간격·모형 비용·후보 예측 |
| 열 특징 | MODEL_AP와30초 h는 보정된 수식과 공개된 과거 점유로 계산한 **추정 상태**. 엔진 실제 미래 잔여/숨은 열 상태를 읽지 않음 |
| 금지 입력 | 미래 도착, 실제 future duration/context, seed/family label, 미래 기준선 총량, NN 입력의 요청ID |
| 완료 경계 | 긴급 OUTPUT_READY 앞2단계/일반 PERSISTED 앞3단계. worker release는lane 가용과 다름. lane은전체5단계 소유 |
| 자원 | 분류CPU/GPU, 탐지CPU, 지원CG_DC만 최대2건. 탐지GPU/NPU·이동·중단 행동 없음 |

EDD+ECT는 특징·보상에만 들어가지 않는다. 정확한 BASE 제안·fallback·후속 예측에 쓰이고 앞8개의 순서도 정한다. RL이 EDD/ECT에서 벗어나는 선택을 직접 할 수 있다. 기존 `p.rollout()`의 응답 최소 suffix와 다른 새 순수 event projection을 사용한다.

모형 T/h는 측정 센서값이나 실제 plant 내부 상태가 아니다. PC 조건에서 초기 preload 관측을 공통 입력으로 주고 그뒤 공개 점유 이력만으로 계산한다. 현재 APK에는 numeric AP의 지속 수신 경로가 없어, 이 연구용 초기화/추정 계약을 검증하지 않고 휴대폰 자체 운영 정책으로 배포할 수 없다. 공개 thermal status/headroom을 섭씨 AP로 바꾸지 않는다.

## 비교 후보

| 역할/ID | 연결과 차이 |
|---|---|
| A Band | `BAND_HEFT_WHOLE_REQUEST_ADAPT_V1`: 공개HEFT 원 코드의 FIFO대표/worker배정/yield/EMA 규칙을 보존한 whole-request 제한적 B. FIFO 대체 없음 |
| A Triton | `TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1`: 검증된 고정CPU/GPU요청 instance 배정·rate-off 동작. 서버 제품 전체 비교 아님 |
| 강한 자체 기준 | `SHARED_EFT`: 실제 공용예상응답·기한 동점·aging. EDD와 다르고 독립 비교군 |
| B EDD+ECT | `IE_EDD_ECT_LANE_PC_V1`: 원 adapter 그대로. lane 점유·호환성+mean5단계 비용으로 ECT 계산 |
| C 현재 RL | `EDD_ECT_SLACK_RESIDUAL_PPO_V1`: 같은설계·native mask PPO를3seed 공통예산으로 새로 학습. 입력형식 연결 오류만 wrapper로 수정 |
| D 휴리스틱 | `EDD_ECT_ENERGY_AP_GUARD_PC_V1`: 물리후보 중 세문맥 기한·AP 비악화가 예측되는 대안에서 예상J 최소, 동점AP/BASE/정규순서. 임의 가중치·튜닝0 |
| E 보완 RL | `EDD_ECT_PHYSICAL_MASK_ENERGY_PPO_PC_V1`: 같은109/68 network/PPO/optimizer에서 물리 mask와 별도 energy 목적 버전. ECT 비교 비용 결측은valid bit/−1표식이며 물리비용0으로 계산하지 않음 |

C는 현재 AP 우선 계약을 유지한다. E는 **ENERGY_AP_NONWORSE_V1**로 별도 등록한다: 전체 J 감소 보상, 같은 세 기준 대비 AP/완료/서비스/P955cost. 새로운 온도 한계가 아닌 같은채널 최고AP 비악화다. 선택은 원래단위 KPI와 전체작업/서비스/AP 조건 뒤 J로 수행하며 보상값으로 순위를 정하지 않는다. 원 정책/모형/기본값은 바꾸지 않는다.

C와E는 알고리즘이 동일하며 mask/목적 패키지가 다르다. 그 차이를 PPO 알고리즘 우열로 부르지 않는다. 새HEFT/GNN/RecurrentPPO/SAC/ALNS/NSGA-II/DoubleDQN은 추가하지 않는다. 이미 공개 HEFT의Band 비교가 있고 현재 이산·비선점 문제에서 복잡한 알고리즘을 추가할 근거가 확보되지 않았다.

## 시간과 보상

J는공통0..120초의기기전체 모형 에너지이며, 실제점유시간×실측증분W+공통유휴소비다. 대기 중의시간·유휴에너지를 포함한다. E의terminal J차이는γ1에서 사건 개수나zero-time dispatch 수를 늘려 얻는 보상이 없다. C의 AP 증가 보상도정확히180초최고차이로 망원합된다. 기존전량분모에서실패/미완료를유지하고부분J를전체작업절감target으로사용하지않는다.

추가 냉각은 실제 dispatch 사이 누적0.25초이고 도착/phase 사건으로 재충전되지 않는다. BASE 자원 대기와 구분한다. C의 추가 대기는 현재 최소기한도검사하고 E는물리운영창/credit만mask한다. E는예측실패행동도학습할수있으므로행동집합의효과가포함된다. 모든정책에서실행중작업의중단/이동과실제점유lane 재사용은금지한다.

Returns에 사건수 보너스는 없지만, PPO가 transition을모아학습하면사건/선택수의차이가 optimizer 표본비중에 영향을줄수있다. 동일episode예산과함께실제informative transition/판단/계산시간을보고한다. 요약관측을완전Markov 상태나전역안전인증이라고부르지않는다.

## 모형 근거와 지원 경계

원모형SHA5682082a·초기관측42f60312를유지한다. A24의효율분류/객체탐지CPU/GPU품질·resident·공개phase계측과지원된CG_DC·지속CPU/PAR 확인에기초한다. 공통 서비스3문맥은기존측정된5단계의평균/전체짧은/전체긴벡터를사용한**전이 가정**이다. 서비스시간의상태별간섭·열에따른감속을별도로동정한일반모형은아니며interference=1을원래대로유지한다. ECT가간섭정확도를새로확보했다고쓰지않는다.

상태별전력증분과AP 동역학은분리된실측에서보정한다. AP온도만으로전력계수를만들지않는다. 최근확인J MAE3.913J/AP MAE0.260°C와회복/잔열오차,개별악화를작은정책차이에함께병기한다. 다른부하의MAE를보편개선하한이나안전margin으로전용하지않는다. [기존근거](HISTORY_POLICY_ERROR_READOUT_20261008.md) · [최신계수민감도](POLICY_COEFFICIENT_SENSITIVITY_RESULTS_20261008.md).

최고표면온도·AP안전limit·한도초과시간·NPU·모바일solver 소비는계산불가/미측정으로남긴다. 계수민감도는기존원모형+개발자료묶음4설정을보존한고정일정후처리이며확률구간/새독립검증/변경모형정책재실행이아니다. [새초기화후보](PRELOAD_DYNAMICS_REFINEMENT_RESULTS_20261008.md)는평가악화/개발gate실패로기본에넣지않는다.

## 파일럿 계약과 보존

현재코드/입력/seed/정책/원단위선정기준을결과전에[등록](results/cpu_gpu_method_01/registration.json)했다. C/E각3seed11·23·37×32episode=192,동일순서32case·4update·탐색/보상튜닝0이다. 중지/재개fixture는별도32성공episode,실패/재개도소비로남긴다. 검증12/확인평가24는훈련과trace/seed hash가다르며동일한조건으로11정책역할을비교한다.3학습seed의안정성과trace반복을구분한다.

초기 C의기본복귀 응답에는backend placement `candidates`가있지만NN 특징은없었다. 실제fixture에서`state_features` KeyError를발견했다. `CurrentController` wrapper가원selected행동그대로단일강제critic transition을기록하고actor/entropy/RNG추가를제외한다. 원 C 소스·실패start·partial batch·clock을보존했고,현재튜닝이나mask완화로고치지않았다. [수정계보](results/cpu_gpu_method_01/repair.json).

최초2성공episode 후실패한fixture는완료분을재사용하고같은RNG/partial batch에서재개한다. 실패된episode의대체도새차감한다. 공통본학습192와성공fixture32는유지하며최대4학습오류여유를명시해파일럿학습상한228/기존전체6,144,환경상한1,024/전체20,000을지킨다. 시간은최초등록2시간·마지막5분저장예약이며재개로초기화하지않는다.

비교유망성/선정결과는파일럿확인자료안의판정이다. 상용제품전체·다른기기·모든도착조건·충분한학습후최적해로확대하지않는다. 추가실측은자동실행하지않으며유망한RL만후속학습/구성제거평가의대상으로검토한다.
