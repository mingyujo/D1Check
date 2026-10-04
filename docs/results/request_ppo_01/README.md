# 요청별 PPO-Lagrange: 신경망 학습과 분리 평가

2026-10-05, REQUEST-PPO-PC-01. 사용자 지적을 반영한 별도 실험이다. 이전 표 기반96회는 구현 연결 초기 시험으로 남기며 강화학습의 효과·불가능성을 판정할 충분한 학습으로 취급하지 않는다. 기존 결과/계약/표는 덮어쓰지 않는다.

## 완료 결과 — 신경망 학습·동결 평가 완료, 정책 채택은 보류

[학습·평가 대시보드](run_v2/index.html), [완료 receipt](run_v2/summary.json), [최종 비교768행](run_v2/test.csv), [seed별 결과](run_v2/seed_results.json), [증거 검증](run_v2/verification.json).

- **3개 학습 seed × 2,048 = 6,144 episode, 실제 행동 결정649,184회, optimizer minibatch 갱신11,628회**를 수행했다. 연속 관측85개를 사용하는64×64 신경망 PPO-Lagrange다. 이전96회 표 기반 시험과 별개다.
- 검증720회(untrained 포함), 최종시험96조건 × 8정책 =768회. EFT 대응 참조2,096회까지 포함하면 본 run_v2는 **9,728 PC 시뮬레이션, 1,467.918초(24분27.918초)**다. 단위테스트/앞선 중단 run_v1은 이 합계 밖이다. 학습6144회는2,048개 학습 조건을3seed로 학습한 횟수이며 독립 실측 세션 수가 아니다.
- 세 정책을 검증에서 선택하고 [최종 시험 전에 동결](run_v2/freeze_before_test.json)했다. seed11/23/37의 선택 update는64/256/64다. 평가 결과로 seed·학습량·보상·입력을 다시 고르거나 재학습하지 않았다.
- 최종768계산에서 전 요청은 완료됐다. 다만 **완료와 기한 충족은 다르다.** queue·burst에는 기준정책과 PPO 모두 기한 위반이 남는다. 세 PPO는 각각 모든96조건에서 EFT보다 등급별 기한/미완료 비율을 악화시키지는 않았다.
- **열 제약과 에너지 개선은 함께 달성하지 못했다.** seed11은 작은 에너지 감소와 열 증가, seed23/37은 평균 열 감소와 에너지 증가를 보였다. 따라서 어느 한 seed를 우승으로 택하지 않고 기본 정책·기기 실행으로 승격하지 않는다.

아래 차이는 동일 입력·서비스 문맥의 `PPO − EFT`다. 96조건은4입력 × 8도착seed × 3문맥이며, 최고AP/긴급P95 열은 조건별 지표의 평균 차이다.

| 학습 seed | 선택 update | 학습 결정 수 | J 차이 | AP 부담 차이 °C·s | 최고 AP 차이 °C | 긴급 P95 차이 ms | 서비스 악화 조건 | 열 부담 악화 조건 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|11|64|210,688|−0.070094|+2.847128|+0.045682|+22.949|0/96|67/96|
|23|256|209,427|+0.138339|−2.171351|−0.006701|+133.123|0/96|43/96|
|37|64|229,069|+0.159345|−2.290245|−0.059925|+110.246|0/96|43/96|

평균 열 부담이 감소한 seed도 개별 조건의 위반은 남는다. 학습의 기대 제약과 모든 조건의 보장을 구분한다.

| 입력 | EFT 기한 충족 / 전체 | 각 PPO 기한 충족 / 전체 | 3seed 평균 J 차이 | AP 부담 차이 °C·s | 최고 AP 차이 °C | 긴급 P95 차이 ms |
|---|---:|---:|---:|---:|---:|---:|
|low|576/576|576/576|0|0|0|0|
|queue|483/576|504/576|−0.068515|+1.101736|+0.029458|+26.414|
|burst|514/576|534/576|−0.065691|+1.118568|+0.035439|+77.700|
|sustained|4,608/4,608|4,608/4,608|+0.437661|−4.372930|−0.092822|+250.977|

각 입력은8도착열 × 3문맥의24계산이다. 분모576/4608은 요청 합계이며 독립 세션 수가 아니다. queue·burst의 기한 개선은 실측 모형과 처리시간 전이 가정 아래의 **합성 입력 결과**다. 전체 모형 정확도/실기기 절감의 독립 확인이 아니다. 나머지CPU·고정split·이전규칙·MC 비교도 [전체 집계](run_v2/aggregate.csv)와 [대응 차이](run_v2/paired_differences.csv)에 누락 없이 있다.

### 학습이 무엇을 했는가

seed11의 최종시험 대기 행동은0회, seed23은3,243회, seed37은3,484회다. 동일 구조가 배정 위주와 배정+대기 방식을 각각 학습했다. 다만 이 행동 횟수와 지표 차이만으로 대기의 순수 인과 효과를 분리했다고 할 수 없다. 저부하에서는 세 정책 모두 EFT와 같은 결과였다.

학습 곡선은 단조롭게 좋아지지 않았다. 검증 서비스 손해가 중간에 커졌으며2개 seed는 마지막이 아닌64update 정책이 선택됐다. 후반64update 평균 entropy는0.493–0.576, KL은0.000208–0.000499다. 이 수치나6144episode만으로 **수렴/최적성/충분한 모든 상태 탐색을 인증하지 않는다.** 현재의 완료는 본격적인 신경망 학습과 분리 평가 절차의 완료다. 기대 제약을 다루는 Lagrange 방법은 입력별 강제 제약을 보장하지 않으며, 최종 시험에서 그 한계가 드러났다.

현재 결과는 “강화학습이 불가능하다”도 “모형이 쓸모없다”도 아니다. 현 상태·행동·가드·모형에서 학습 가능한 정책과 서비스/J/AP 상충을 실제로 비교했다. 아직 관측되지 않은 자원이나 열→처리시간 법칙을 넣어 이득을 만들지 않았다. 기기에서 확인된 오차와 무관하게0.07J 차이를 절감 효과로 선언하지 않는다. 다음 PC 행동 하나는 **저장된 일정에서 배정과 대기가 만든 서비스·J·AP 상충을 분해하는 것**이며, 같은 설정의 맹목적 장시간 재학습이나 기기 실측 자동 추가가 아니다.

### 실행·검증과 보존

1. 실제 엔진 phase 이름을 잘못 참조하던 연결1건을 본학습 전 fixture에서 수정했다. run_v1은 검증키의NumPy 정수 JSON 직렬화 결함 발견으로 최종시험 전에 소유 프로세스를 중단했다. [중단 기록](run_v1/ABORTED_PC.json)에 확인된32update/256episode/21,376결정을 보존한다. 체크포인트 이후 미기록 진행량은 확정하지 않는다. 목적·입력·학습법은 바꾸지 않고 Python 기본형 직렬화만 수정한 뒤 새 run_v2에서 실행했다.
2. [관련 테스트56건](pc_tests.json) 모두 실제 실행·통과, skip0. 보상/비용 방향을 known-bandit에서 확인했고 미래정보 차단·mask·GAE·기한분모·원가합산·기존엔진 회귀를 검사했다. PC fixture이며 실기기 검증이 아니다.
3. 최종768 ledger,50,688 요청의 경계순서·lane 소유권·분모·P95·J/AP를 재계산했다. J를별도구간합산한 최대차이는9.67e−13J, AP면적 재계산차이0이다. 기존 물리모형/초기조건/실행소스 해시 불변, 세 정책 시험 전 동결,768회 승수 갱신도 확인했다. 재학습/시뮬레이션 재실행 없이 저장 결과만 읽었다.
4. [분석·시각화 계약](report_contract.json)은 최종시험 전에 고정했다. 2,000회 crossed bootstrap은 학습seed3개와 도착trace8개를 각각 재표집하고3개서비스문맥을 묶는다. 탐색적2.5/97.5백분위이며 실측오차·모집단 보장으로 해석하지 않는다. PNG/SVG3종을 렌더링해 판독했고 CSV와같은값을쓴다.
5. 학습종료·계산완료와 별도로 기기 명령/추론/설치/실측/새기기계획은 모두0이다. 기존 계수·원자료·FAIL·종료계획·strict·`experiment_ready=false` 불변. 사용자 HTML/다른 worktree도 보존한다.

## 결과 전에 고정한 설계

[계약](contract.json), 구현 `tools/d1_request_ppo.py`. 설치된PyTorch2.11.0+cpu/NumPy2.3.5 사용. 기존 conda의 OpenMP 중복 초기화는 **해당 PC 명령의 `MKL_THREADING_LAYER=SEQUENTIAL`**로 MKL 순차 실행을 선택해 해결했다. `KMP_DUPLICATE_LIB_OK` 강행·전역 설정·패키지 교체·기기 변경은 하지 않는다. PyTorch thread1, 결정론적 연산을 사용한다.

- 알고리즘: invalid-action mask를 샘플링/손실 양쪽에 적용한 PPO clipped surrogate, 네 value head, 투영 Lagrange multiplier 갱신. 기존 도착·단계·lane 실행 엔진을 그대로 사용한다. 별도 표본평균 정책을 딥RL로 이름만 바꾼 것이 아니다.
- 관측85차원: 상위8개 도착 요청의 개별 기한/작업/나이/서비스 추정, 전체 큐 작업량·등급별 수·기한여유, 실제 관측된 최근 도착 간격, CPU/GPU 단계·추정 잔여시간·overrun, 연속적인 모형 AP/유휴기준/이력·시간. 이전의4개에서 포화되는 backlog를 제거했다. 미래 도착·미래 완료·실현 서비스벡터·scenario/seed/총 미래 요청 수는 입력하지 않는다. 완전한 Markov 상태라고 보장하지 않는다.
- 행동: 합법적인 즉시CPU/GPU 배정, 최대250ms 대기. 자발적대기는 요청도착 기준2초 이내·추정head기한guard, 자원점유로 인한 대기는 별도. EDF/aging·실제lane해제·허용3cell/병행쌍을 유지한다. mask는 물리 실행 적합성과 국소 기한만 검사하며 전체서비스/열을 보장하지 않는다.
- 목적: 공통120초 J 최소화. 제약비용은 긴급·일반별 `기한위반 또는 최종미완료` 비율과35–180초 AP부담 각각을 동일입력EFT의 기대값 이하로. AP부담은 **부하 전 유효유휴기준 위 AP의 degree-seconds**이며 주변온도·BAT·안전상한이 아니다. 최고AP와P95는 별도로 전부 보고한다. 결과를본뒤유리한열지표로바꾸지않는다.
- 상태전환 사이 구간의J/10, 긴급/일반실패비율, AP면적/100을 각각 학습채널로 기록. 종료후실현결과는 학습표적으로만 사용한다. 시간할인gamma1, GAE0.95. 단위scale은수치학습용이며실제평가는J/°C/초/전체분모로수행한다. 승수초기10/10/1, 학습률5,0–100투영을 사전고정했다. 가중치/승수나보상점수로 실제기한손해를가리지않는다.
- actor/critic 공유tanh64×2, 출력행동3/value4. Adam3e-4/eps1e-5,4epochs,minibatch256,clip0.2,entropy0.01,value0.5,gradclip0.5,targetKL0.03. 계산된열/전력계수는재학습하지않는다.

## 규모·분리·종료

- 학습 seed11/23/37 각각256update×8episode=2048, 합계6144episode. 별도 학습 안정성 비교이며 가장 좋은seed만발표하지않는다. 최소탐색량을등록했지만 이숫자가수렴을보장하지는않는다. 학습곡선·KL·entropy·제약위반·승수·행동수를남긴다.
- 학습 입력seed30000–30511, low/queue/burst24와sustained192, 기존 생성규칙의 작업순서셔플·도착간격±5% jitter. 세모사서비스문맥을사전순환한다. mean추정은고정하고실현벡터만바뀐다. 기존과같은동결모형/초기관측1개를쓴다. 새로운물리분포/잡음/스로틀모형을발명하지않는다.
- 검증seed40001–40004×4입력×3문맥48조건. untrained0과64/128/192/256update마다평가. 학습된4checkpoint중, 미완료조건수→서비스악화조건수/크기→열부담악화조건수/크기→평균J→P95 순서로선정. 불가능하면최소위반checkpoint를진단후보로남기며통과로표시하지않는다. untrained는선정후보에서제외한다.
- 세선정정책을모두해시동결한뒤에만최종testseed50001–50008×4×3=96조건을연다. PPO3개+CPU/고정split/EFT/기존에너지AP규칙/이전MC의8정책=768계산. 최종test결과로hyperparameter·epoch·seed·입력을선택하거나다시학습하지않는다.
- PC 전체실행상한7200초,16update마다checkpoint. 한구조·한설정이며 무한학습/실측/새기기계획없음. 완료·수렴징후부족·제약불충족·단순정책대비개선없음을구분한다. 사용자요청의제대로된학습은 성공보장이아니다.

## 해석 경계

세학습seed는알고리즘변동,8최종도착seed는같은합성분포의입력변동,3서비스문맥은민감도다. 서로독립실측세션이아니다. 문맥3개를표본수3배로부풀린신뢰구간을만들지않는다. policy seed와arrival trace별결과를보존한다. 동일초기온도·개발문맥전이·열→처리율미지원·추가정책연산비용0은기존모형한계다. 실제휴대폰절감·정책우월성·strict/experiment_ready승격은없다.

기대제약을 학습하는Lagrange방법은 각입력의하드제약을보장하지않는다. 평가에서전분모서비스,미완료,에너지,AP면적/최고값,P95를각각판독한다. 에너지·열원모형과현재배포경로는불변이다.

알고리즘 근거: [PPO 원 논문](https://arxiv.org/abs/1707.06347), [action masking 연구](https://arxiv.org/abs/2006.14171), [Lagrange 방법 공식 설명](https://omnisafe.readthedocs.io/en/latest/saferlapi/lagrange.html). 이번 구현은 해당 알고리즘 원리를 적용한 프로젝트용 구현이며 논문의 벤치마크 성능이나 이론 보장을 승계하지 않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_request_ppo tools.test_d1_request_rl tools.test_d1_empirical_request_policy -v
python -u -B -m tools.d1_request_ppo --output output/request_ppo_reproduction
```

## 재현과 파일 경계

저장된 결과의 대시보드 재생성은 학습을 다시 하지 않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_request_ppo tools.test_d1_request_ppo_report tools.test_d1_request_rl tools.test_d1_empirical_request_policy tools.test_d1_arrival_explore -v
python -B -m tools.d1_request_ppo_report --folder docs/results/request_ppo_01/run_v2
# 다음 검증은 로컬 원시 ledger 파일이 있을 때만 실행한다.
python -B -m tools.d1_request_ppo_verify --folder docs/results/request_ppo_01/run_v2
```

학습 재현 명령은 위 설계 절의 별도 새 출력 경로를 사용한다. 기존 run 폴더를 덮어쓰지 않는다. 학습 입력은 생성 규칙/seed로 고정되고 외부 기기 원자료를 새로 읽거나 요청하지 않는다. 필요 공유 의존 파일은 이전 MC의 `docs/results/request_rl_01/run_v1/learned_table.json`, 기존 `overnight_sustained_run01/model.json` 및 `initial_inputs.json`이다. 정확한 해시는 [preregistered.json](run_v2/preregistered.json)에 있다.

공유: 계약·코드·테스트·훈련/검증/시험CSV·선택된3정책의 소규모JSON 파라미터·해시·그림·대시보드. 제외: 약32MB `run_v2/local_test_ledgers.jsonl`, 중간 actor/checkpoint.pt, console 로그. 원시 ledger는 로컬에 보존하며 [verification.json](run_v2/verification.json)에 경로/해시가 있다. 이 작은JSON은 스케줄링 정책 파라미터이며 Android 추론 모델/APK/키가 아니다.
