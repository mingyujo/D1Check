# burst8 실패 경계와 도착 대기열 기한 보호

2026-10-05, 기준 HEAD `e884882b88d6146b78c740437e0b002a27b09377`. [대시보드](run_v1/index.html), [원 실패 요청별 분해](run_v1/original_request_decomposition.csv), [비교표](run_v1/comparison.csv), [검증](run_v1/verification.json).

**원 실패16건은 전부 긴급 분류였다. 병행을 우선 만드는 결정에 남은 대기열의 기한 검사가 빠져 있었다. 별도 보호 계층을 연결하자 이 조건의 기존/새 seed에서 총576/576요청 기한을 충족했다.** 다만 EFT 대비 에너지는 줄고 최고 AP는 높아져 에너지·열 공동 우월성은 아니다. 기존 ML 재학습·물리 계수 변경·실측은 하지 않았다.

## 확인한 실패 원인

대상은 평균도착1.2초/분류75%/burst8의48요청이다. 이전 [지도학습](../supervised_selector_01/README.md)이 이 미학습 조합에서 PAIR_COALESCE를 선택한6사례 중5사례에서16건이 늦었다. 저장원장12개(EFT/PAIR×2seed×3문맥)를 이번 PC 실행에서 **원장 전체 일치**로 재현했다.

- PAIR_COALESCE는200ms 안에 이미 도착한 탐지와 분류를 묶기 위해 탐지CPU를 우선 시작하고 분류GPU를 배정한다. 이때 선택된 요청뿐 아니라 뒤에 기다리는 긴급 요청 전체의 deadline을 점검하지 않는다.
- seed123001/mean 첫군집에서 요청0–5는긴급분류,6은일반탐지,7은긴급분류다. EFT는분류CPU 응답을먼저진행한다. PAIR는0.182747초에탐지6과분류0GPU를시작하고분류1·2까지GPU로연결한다.
- 탐지CPU는0.804484초에lane을놓지만분류2GPU가1.097236초까지점유한다. 현재지원mask에서분류CPU＋분류GPU는허용하지않으므로CPU분류도기다린다. 요청7의응답은1,536.989ms로1,500ms를넘는다. 단순200ms대기만의문제가아니며배정·비선점lane점유·후속대기가결합한다.
-16실패요청의EFT대비평균응답증가678.760ms = 대기증가602.602ms＋자체dispatch→응답증가76.158ms. 이것은원장의산술분해이며기기물리인과분해가아니다. 대기에는앞선다른요청의정책결정이포함된다. [분해요약](run_v1/decomposition.json).
- output_ready(긴급응답),persist_complete(일반응답),worker_release,lane_available을구분했다. lane을응답시점에조기해제해문제를감추지않았다.

## 별도 보호 계층

`PAIR_QUEUED_SERVICE_GUARD_V1`은 기존 PAIR제안을 받은 뒤 현재 도착한 요청만으로검사한다. 기존 controller/입력/정책을덮어쓰지않고옵트인decision_provider로만연결했다. 엔진의합법action namespace는기존PAIR를재사용하되결과에는별도guardID를기록한다.

1. 기존개발자료의long_context 처리시간벡터로현재lane잔여시간을계산한다. 실제미래완료시각이나현재문맥정답은입력하지않는다.
2. PAIR의첫제안(자원·요청·유예) 뒤 나머지 현재대기열을EFT로배정하는예측과, 처음부터현재EFT결정을따르는예측을비교한다.
3. 어느미응답요청이든예측지각시간 `max(0,응답−기한)`을EFT보다늘리면현재제안을거부하고EFT로돌린다. 위반건수가같아도지각량을늘리는결정은거부한다.1ns비교여유는수치오차용이지서비스허용오차가아니다.
4. 이미응답한요청을미래실패로세지않고실제lane해제까지소유권을유지한다. 예상실행시간을넘긴활성작업은기존의실제이벤트대기로처리한다.

이는**현재대기열에대한상대예측검사**다. 미래도착·예측오차·임의과부하·최악실행시간을보장하지않는다. long_context는관측개발벡터중긴경우이며인증된WCET가아니다. continuation은EFT 가정이고실제다음시점에는다시PAIR제안을검사한다. 이조건에서의성공을모든정책·모든부하에확대하지않는다.

## 결과와 비용

[사전계약](run_v1/contract_before_run.json): 원실패2seed123001/123002와새2seed124001/124002,각3처리문맥×EFT/PAIR/guard=36PC계산. 소스/입력/원모형동일성을동결하고결과후규칙수정·추가seed선택없음.3.172초소요. 테스트의짧은fixture재생은이36회연구계산과별도다.

| 자료 | 기존 PAIR 기한충족 | 보호계층 | EFT | 보호계층−EFT J | 보호계층−EFT 최고AP |
|---|---:|---:|---:|---:|---:|
| 원 실패조건 재현 |272/288|288/288|288/288|−0.430954J|+0.188893°C|
| 새 seed 같은조건 |270/288|288/288|288/288|−0.560587J|+0.225968°C|

J는공통0–120초기기전체비용,AP는35–180초이다. 새seed의긴급P95는EFT보다평균419.675ms늦지만해당288요청의기한은모두지켰다. 일반평균응답은513.555ms빠르다. 평균J감소만으로모든응답/열지표를개선했다고하지않는다.

원PAIR대비새seed의guard는평균−0.033974J/−0.050268°C,긴급P95−141.385ms이지만일반평균+48.188ms다. J는일부사례에서+0.041096J라모든사례의동시우월성도아니다. 전체세부표를보존했다.

거부callback은원101회/새131회다. **232개추가요청/독립결정이아니며**,같은대기상태에대한이벤트별반복검사를포함한다. 제안종류별 bounded_pair142/overlap52/start_detection38. 추가추론·호출·가열없음. guard의실제폰계산시간·에너지오버헤드는미측정이며현재시뮬레이터의decision시간0가정을유지했다.

## 판정·다음 PC 행동

이번에해결한것은학습기가고른PAIR의**국소서비스보호누락**이다. 특정부하를식별해하드코딩하거나모형계수를조정하지않았다. 기존ML선택기를새로학습하거나guard를기본정책에자동적용하지않았다. 새seed는같은부하조합이므로독립기기확인/미지부하검증은아니다.

에너지목적의조건부후보로보존할가치는있으나, 열목적에서는EFT보다나쁘다. strict지원·experiment_ready=false는유지한다. 다음PC행동하나는 **다른부하조합에서이보호계층이새서비스손해를만들지않는지 제한된회귀비교**다. 새실측·자동기기계획은만들지않는다.

## 검증·재현

- 관련13테스트PASS(skip0):실제엔진/guardcallback/lane소유권/미래도착차단/지각량검사/요청분모일치/기존정책일치와기존조건정책회귀.
-36ledger·1728요청의시간순서/lane/분모/모든비용재회계,원장12개정확일치,원동결hash불변,J독립합산차이0. PNG시각확인. 기기명령/실측/APK/새기기계획0. 사용자HTML·다른worktree·기존결과보존.
- 원자료: `docs/results/supervised_selector_01/run_v1/local_ledgers.jsonl`; 이번상세기록: `run_v1/local_records.jsonl`. Git에는작은CSV/JSON/그림만포함하고상세원장·키·모델바이너리는제외한다. 원장SHA는계약/verification에보존한다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
$env:OMP_NUM_THREADS='1'
python -B -m unittest tools.test_d1_pair_service_guard tools.test_d1_scheduler_conditions
python -B -m tools.d1_pair_service_guard --output docs/results/pair_service_guard_01/reproduction_v1
python -B -m tools.d1_pair_service_guard_report --folder docs/results/pair_service_guard_01/reproduction_v1
```

새디렉터리재현은PC36회이며실측이아니다. 원실패로컬원장이없으면원장일치검사는불가하다. 공유CSV/그림은해당원장없이읽을수있다. 기본시뮬레이터나Android를변경하지않았다.
