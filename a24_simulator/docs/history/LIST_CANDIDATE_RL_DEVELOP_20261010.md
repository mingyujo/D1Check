# RL128 행동 진단과 서비스 중심 보완

2026-10-10 · `LIST-CANDIDATE-RL-DEVELOP-07` · **120회 개발 완료, V2는 서비스·에너지 개선/열 상충으로 미채택**

**탐지 요청이 쌓이면 추가 대기를 막는 산업공학 리스트 V2를 구현했다.** 동일 개발24조건에서 L0/Band/Triton 대비 모든 조건의 완료량·긴급P95·긴급/일반실패·에너지가 나빠지지 않았다. 다만 Band/L0보다 최고 모형AP가 높아진9조건이 남아 전체 채택 기준은 미달이다. 이 결과는 개발자료 안의 개선이며 실물이나 새 독립 확인의 성공이 아니다.

[화면·CSV·그림](results/list_candidate_rl_develop_01/README.md) · [검증·소스](results/list_candidate_rl_develop_01/verification.json)

사용자 `계속 발전시켜봐` 지시로 재회의의 원인 진단을 실제 실행한다. 새로운 학습 예산을 만들지 않고 원래 설계의 잔여308환경·12학습을 계승한다. 이번 학습/optimizer/기기/ADB/NPU 실행은0으로 고정한다. 원모형·지원·기한·품질·기본/strict/experiment_ready=false는 유지한다.

## 결과 전 고정한 첫 단계

- 고정 terminal128 actor/critic3개·seed11/23/37·기존 개발24조건을 사용한다. 기존 argmax72행과 L0/Band/Triton 등 개발 기준선은 원자료/hash로 재사용한다. 확인48은 이미 소비한 진단자료이며 새 정책 독립 확인으로 쓰지 않는다.
- 기존 bank/56상태/8×28후보/물리mask의 바이트와 slot순서를 그대로 보존한다. 원네트워크 계산 후 선택 단계에서 `wait>0` 후보만 제외한다. 기존 encode전 bank필터와 구분한다.
- 혼합 즉시배정＋반대head지연 후보도 제외하므로 이 진단은 기다리는 행동군의 제한이다. 시간 지연만의 단일 인과효과·학습알고리즘 우열·실제 서비스 안전보장을 주장하지 않는다. 같은 공개상태의 encoder를 유지하며 intervention 뒤 실제 상태 경로는 달라질 수 있다.
- 첫 배치는24조건×3seed=72환경 상한·학습0. 전체 후속cap308·학습0, 새 clock등록부터2h/저장5min, 이전누적7,745/1,045 및 설계1228/1536을 계승한다. 기존clock/원장/weights/Adam/RNG를 변경하지 않는다.
- completion·urgentP95/U/N·J120·모형AP·WAIT/자원 선택을 대응 비교한다. epsilon0·원단위 판정을 유지하고 실패도차감한다. 한seed나좋은조건을선별하지 않는다.

## 조건부 발전 범위

첫72결과가 대기·자원 선택 원인을 뒷받침하면 같은 bank의 서비스 중심 비학습 선택기를 단일 설정으로 개발24에서 비교하는 안을 검토한다. 짧고 작업량이 다른 atom proxy를 그대로 전체 비용 순위로 쓰지 않고 같은 현재head 작업량·공통 예측창 비교의 타당성을 먼저 검증한다. 예측불명은0비용이 아니며 물리적으로 실행 가능한L0로 복귀한다.

개발에서 실제 전조건 비악화·반복 개선이 없으면 독립 확인을 무조건 늘리지 않는다. 유망하다면 결과 전 동결한 새 도착seed로 L0/Band/Triton3기준＋단일후보48조건=192환경이 필요하다. 72진단＋24개발＋192확인은288/308이므로20예비를 남길 수 있다. 이 배분에서는 sampling216을 함께 실행하지 않는다. 동일 상태의 충분한 증거가 없으면 보상/특징/temperature-feedback을 임의로 바꾸지 않는다.

지금의 실행 승인은 최초72와 그 근거에 따른 최소 보완이다. 추가학습·측정·모형교체·무제한 tuning으로 확대하지 않는다. 결과·실제소비·변경과 검증은 완료 시 추가한다.

## 실제 발전 경로

1. **입력 보존 대기제거72:** 고정128 weights를 유지한 선택 제한만 실행했다. seed11은 긴급P95 평균705.31→349.24ms로L0 수준이 됐고, seed37 일반실패396→24가 됐다. seed23은24원장/전이가 원본과 exact동일하며 여전히Triton 수준이다. 자원 선택 문제가 함께 남는다.
2. **같은 작업량 비용 비교 V1,24:** 기존 atom proxy 대신 현재소유＋현재C/D 두head의 전체 평균 실행을 공통 예측창에 놓는다. 같은 작업량·같은 배경관측시간으로J/AP를 비교한다. 현재긴급head 예상응답은L0보다 늦지 않게 하고, 정상head 예상지각은L0보다 커지지 않게 선택한다. 미측정값을0으로 채우지 않고 예측불명은L0로 복귀한다. 실제 요청별 명시대기는 누적.25로 제한한다. 그러나 미래 도착/뒤 탐지 요청은 이 좁은 예측에 없어서 일반실패가24→76으로 늘었다. 평균J감소를 개선으로 채택하지 않았다.
3. **탐지 적체 보호 V2,24:** V1을 보존하고 `현재 도착한 탐지 요청이2건 이상이면 추가 대기 금지`만 더한 별도 정책이다. 숫자2는head외 대기요청이 있는지를 구분하는 구조적 조건이며 새SLA·측정계수·열한도가 아니다. 이 보완으로 일반실패76→24, 에너지 감소는 유지됐다. 임의 가중치 탐색이나 새RL학습은 하지 않았다.

## 같은24조건·정책당1,584전량 결과

표의 P95/J/AP는 조건별 값의 평균이다. 전체 요청을 pool한P95와 혼합하지 않는다.

| 정책 | 일반기한 위반 합 | 긴급P95 평균ms | 공통J120 평균 | 최고 모형AP 평균°C |
|---|---:|---:|---:|---:|
|L0|24|349.241|152.308818|30.876957|
|Band 요청 단위 적용|24|349.241|152.272788|30.874566|
|Triton 요청 단위 적용|24|397.522|152.761036|30.919561|
|기존 같은bank GREEDY|306|259.586|152.378078|30.872964|
|V1 같은작업량 비교|76|336.166|152.134292|30.918032|
|V2 탐지 적체 보호|24|349.241|152.220692|30.883734|

V2는 **Triton 대비24조건 모두 서비스/J/AP 비악화**이고 J엄격감소15조건이다. 개발자료에서 재현한 판단규칙 대비의 결과이며 Triton 제품 전체에 대한 우위가 아니다.

Band와 비교하면 서비스/J 악화0·J엄격감소6조건이지만 AP악화9조건이며 차이범위−.017054…+.074257°C다. 평균J−.052096/평균AP+.009168°C의 에너지-열 상충이다. L0 대비도AP악화9조건이며 전체M/G는 미달이다. 작은값을 모형오차보다 확실한 물리효과로 확대하지 않는다.

V1의 현재head 서비스 제한만으로 뒤 정상요청까지 보호할 수 없었다. V2는 도착한 탐지 backlog를 반영해 이실험에서서비스를 회복했지만 미도착요청·모형오차의 기한 안전보장을 제공하지 않는다. 현재CPP/GPU 조합·lane5phase·.25dispatch credit는 그대로이고 요청별 명시대기.25와backlog 선택조건을 별도 정책 ID로 기록했다. 기존PPO/기준선 설정을 바꾸지 않았다.

## 완료·예산·제한

- 이번120환경/실행실패0·7,920예정/완료·새학습/optimizer/기기/ADB0. 고정weights/Adam 원본불변, 기존결과보존. 288 CSV행 중120만 신규이고168은이전개발행 재사용이다.
- 누적7,865환경/1,045학습·설계1348/1536환경·404/416학습, 잔여188환경/12학습이다. 첫clock02:29:50UTC/2h/저장5min을 후보보완에서도 초기화하지 않았다.
- 순수검사9개(NoWait3＋같은작업량4＋backlog/cap2)통과, 모든120raw/controller SHA·요청보존·응답/반환경계·lane용량·지원범위 확인. 후보별등록/실행/반례/소스버전을 보존했다.
- V1 실패를 근거로 V2를 별도등록했으며 평가한후가중치/열계수/성과epsilon을 바꾸지 않았다. V2 runner의 단계cap을24로 명시하는 마지막 보호는 실행후순수검사로 확인했고 실제24회와정책판단은불변이다. Browser의seed필터표시 오류1은환경/학습0으로 수정했다.
- 개발미적격이므로 새독립확인은0이다. 새48조건×3기준선＋후보=192환경은현재잔여188을넘고, 조건을줄여공식통과로승격하지 않았다. sampling216도188을넘으므로 자동실행0이다. 남은12학습으로3seed각8episode update(24학습)도 불가능하다.
- 가장 유망하게 남긴 구조는 **같은 작업량 비용 비교＋탐지 backlog 보호**다. 다만 열 악화원인·현재proxy와전체180초AP차이·CPU/GPU 열원 영향이남아 새정책으로채택하지 않는다. 기존L0/Band연구기준·기본/strict/experiment_ready=false 유지다.

## 재현

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_list_candidate_rl_develop tools.test_d1_list_candidate_service_list tools.test_d1_list_candidate_service_backlog -v
python -B -X utf8 -m tools.d1_list_candidate_rl_develop_check --run output/list_candidate_rl_develop_20261010_v1
python -B -X utf8 -m tools.d1_list_candidate_rl_develop_report --run output/list_candidate_rl_develop_20261010_v1 --output docs/results/list_candidate_rl_develop_01
python -B -X utf8 -m tools.d1_list_candidate_rl_develop_browser_check docs/results/list_candidate_rl_develop_01/index.html 288 48
```

실제 실행형식은 develop의 register/nowait, service_list_study의 register/development, service_backlog_study의register/development였다. 완료ID·구등록·clock을 재호출/새폴더로 초기화해예산을만들지않는다. 원시gz/PT·모델은local output에보존하고작은코드·CSV·그림·검증만공유한다.
