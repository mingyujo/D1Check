# 리스트 + RL v4.1 구현·검증 결과

2026-10-10 · `LIST-CANDIDATE-RL-IMPLEMENT-04` · **구현·PC 검증 완료, 학습·기기 실행 0회, 최종 방법론 미선정**

공개 이벤트, 제한된 대기, 최대 8개 후보, 기본 리스트 L0, 같은 후보를 쓰는 고정 선택기 risk5, 관측 encoder, Maskable PPO의 행동 선택·목표·손실 계산과 controller/RNG 저장을 구현했다. 등록된 시뮬레이터 실행 32회를 사용했고 실행 실패는 0회, 예정 1,748건 모두 완료했다. **요청 완료와 기한 준수는 다르므로 기한 위반은 별도로 남겼다.** 새 학습·optimizer 갱신·기기 명령은 모두 0회이며, 기존 누적은 6,549환경/641학습이다.

이 단계의 결론은 **실제 구현이 실행되며 누락 정보를 보완했다**는 것이다. 성능 개선이나 최종 정책 선정을 완료한 것은 아니다. 대조군의 서비스 실패, 전체 일정 표현성과 실제 학습 재개의 미검증 항목 때문에 본학습은 보류한다.

[오프라인 결과 화면](results/list_candidate_rl_implementation_01/index.html) · [CSV](results/list_candidate_rl_implementation_01/native_results.csv) · [검증·소비·남은 범위](results/list_candidate_rl_implementation_01/summary.json) · [소스 버전·검증 기록](results/list_candidate_rl_implementation_01/verification.json)

## 구현과 기존 경로 보존

- `tools/d1_list_candidate_rl_engine.py`는 원실행기의 별도 opt-in 복사본에 arrival/actualdispatch/phase 공개훅만 추가한다. 기존 `tools/d1_arrival_explore.py` SHA55eaff8b…7b9는 불변이다. EDD/Band/Triton/원List4정책의 원장·전이·지표·결정이 old/fork에서 모두 정확히 같았다(8native).
- `tools/d1_list_candidate_rl.py`는 실제dispatch credit·양의시간1회debit·phase-only hold유지·arrival/AVAILABLE/timer 재판단·PAIR 첫영수증/둘째 재검사·zero-time 순서를 연결한다. 연속event/phase계보가 누락되면 실패처리하며 응답을평균으로채우지 않는다.
- 기본56/28 schema `head2`는보존한다. 실제별칭근거뒤에만 opt-in `head2+C_next`를추가했다. 물리action·credit.25·모형·목적은변경하지않았다. 기존actor/Adam은새schema에로드하지않는다.
- forecast불명→L0는고정선택기의규칙이다. PPO는물리mask와knownflag를받아불명후보도선택할수있다. 공개journal/초기화자체불명은실행실패와구분하며모든불명을공통L0로처리했다고보고하지않는다.

순수 검사 12개(기능10＋소비 기록 재호출 보호2)가 통과했다. 완료된 추가 검사/표현성 단계를 재호출하면 기존 등록 기록을 덮어쓰기 전에 거부하고, 실패한 CLI 결과는 exit1로 반환한다. 이 마지막 보호 변경은 native32 이후 순수 검사로 검증했으며 시뮬레이터/정책 동작은 변경하지 않았다.

실행시간을 0으로 만든 2회는 공개 응답 누락·시간 정지·요청 보존을 확인하는 인위적 fixture이며 성능 비교에 사용하지 않는다. 모델 SHA5682082a…bd2/초기 SHA42f60312…8d와 기본/strict/experiment_ready=false는 유지했다. 별도 C0/LOAD 실측 2조건의 완료와 이번 RL 작업의 신규 실측 0회를 구분한다.

## C2를 실제로 재현했다

네등록fixture는각25요청(C10/D15)을합법prefix부터고정risk5후속까지완주했다. 실제cut은41.00000000031248초,마지막hold 실제차감0.01207794439585초다. A/B의state56/candidate8×28/physicalmask·순서/L0index·credit/timestamp/eventseq/pending/hold가비트단위로같았다. rawpublicqueue에는의도한C2도착차이를별도남겼다. 공통suffix9로최근8gap도같아졌다.

| C2 기한 상태·첫 선택 | C2 실제 응답 ms | 긴급 위반 | 전체 J120 | 최고 모형 AP |
|---|---:|---:|---:|---:|
| 빠른 A / CPU 먼저 |1459.271|2|140.991348|30.296208|
| 빠른 A / PAIR |1598.884|3|140.920447|30.306606|
| 늦은 B / CPU 먼저 |1209.271|1|140.963694|30.280157|
| 늦은 B / PAIR |1348.884|2|140.991348|30.295468|

응답은 요청 도착부터의 실제 지연이다. 정적 계산의 cut 이후 0.459/0.599초와 혼합하지 않는다. A의 PAIR는 C2 기한을 놓쳐 전체 긴급 위반이 2→3으로 늘었다. 나머지 큐에도 위반이 있어 어느 경로도 전체 서비스 조건을 통과하지 못했다. B에서는 CPU-first가 서비스와 AP/J에서도 더 좋았다. 따라서 **A/B의 최적 첫 행동이 반대로 바뀐다는 증거는 아니다.** 기존 세 요청의 증분 J−0.04325를 전체 결과에 전용하지 않는다.

누락 정보를 보완하기 위해 중복된 `remaining_over_120s` 슬롯1만 **이미 도착한 분류 FIFO 두 번째 요청의 `(절대기한−현재시각)/1.5초`**로 교체했다. 분류 queuecount≥2로 존재를 구분하고 없으면 padding0을 사용한다. 입력 차원56/28과 파라미터16,455개를 유지하면서 schema/hash를 분리했다. 미래 도착이나 실제 잔여 실행시간을 추가한 것이 아니다.

추가 4회에서 A/B는 state index1(.33333334/.6666667)만 달랐고 candidate/mask는 같았다. 고정 선택기의 원장·전이·지표·결정도 원 4회와 정확히 같았다. **고정 rule은 새 C_next를 사용하지 않는다.** 이것은 관측 보완 검증이며 서비스 개선이나 순수 PPO 효과의 입증이 아니다.

## 고정선택기의 대기 편향은 남는다

결과무관으로사전고정한개발seed812010001/mean의4부하를검사했다.

| 부하 | 완료/예정 | 긴급/일반 위반 | 자발대기 실제초 | hold선택 |
|---|---:|---:|---:|---:|
| 낮음 |24/24|0/0|4.500|23|
| 큐 몰림 |24/24|0/12|2.313|26|
| 순간 몰림 |24/24|0/10|2.474|22|
| 지속 |192/192|0/31|18.280|148|

새 risk5는 기한 위험과 공개 긴급 proxy를 계산하지만, 짧은 구간의 비용이나 대기를 선호하는 한계를 해결했다고 볼 수 없다. 지속 부하의 일반 기한 위반 31건을 무시하고 에너지 절감 우위로 판정하지 않는다. 순수/혼합 hold, 실제 차감 시간, 강제 대기, fallback 원인과 전체 분모를 원자료에 보존했다. 이번 결과를 보고 임계값·목적·추가 대기 설정을 튜닝하지 않았다.

## 기존 성공 일정의 표현성 범위

이전좋은한trace의mean/short/long3조건은192전량·원지표를정확히재현했다. 추가3native의passive공개event tap도원장·전이·지표·결정을바꾸지않았다. 원공개시점의점별물리primitive 대조3617행에서즉시배정primitive576개,같은선언timer137개,강제wait2689개,불명215개를기록했다.

credit.25상한의낙관적점별대조이며구원정책의실제hold/debit를새규칙으로순차재현한검사는아니다. 혼합/PAIR의첫primitive포함을전체원자행동동등으로읽지않고timer/phase중단·credit도달성은불명으로남긴다. **새후보로기존성공일정전체를재현했다는PASS는없다.** 학습량부터늘려해결됐다고하지않는다.

## RL 경로와 체크포인트 검증

미학습PPO의기능진단1native에서sampled32선택의logprob/critic/마스크를저장했다. 실제완료곡선의행동이후AP증분·180초꼬리보상합은참조AP차이0.03920177234906319와일치했다. episode-sum actor/episode-mean critic·entropy와채널유효성손실을역전파했으며optimizerstep0·가중치불변이다. 이진단은AP가낮아져도J+0.155248/일반위반+3/P95악화가있어방법개선이아니다.

λJ=0의직접actor J항은정확히0이었다. 공유encoder J critic gradient는2.06733으로비영이었으므로전체optimizer가에너지와무관하다고해석하지않는다. 별도비교/학습수렴증거로승격하지않는다.

controller 전체 tree·RNG·weights·partial batch·승수/소비 payload·Adam 구조 복원과 다른 schema의 거부를 확인했다. **Adam은 아직 비어 있으며 실제 추가 학습 동일성과 live engine 중간 재개는 미검증**이다. 향후 resume에는 controller뿐 아니라 formula/plant/engine 소스 manifest도 묶어야 한다.

## 현재 판정과 재현

후보/encoder/event/hold/초기 PPO/loss/API의 제한된 구현과 실행 검사는 완료했다. epoch/minibatch/dual 학습 runner, 실제 optimizer 갱신 후 resume 동일성, 기존 성공 일정의 전체 시간순 표현성과 새 3seed 성능 검증은 남았다. **현재 본학습 NO-GO, 최종 방법 미선정**이다. 고정 선택기의 서비스 실패나 미학습 PPO 진단을 RL 일반의 실패 또는 수렴으로 해석하지 않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_list_candidate_rl -v
python -B -X utf8 -m tools.d1_list_candidate_rl_verify --output output/NEW_REGISTERED_GATE
python -B -X utf8 -m tools.d1_list_candidate_rl_verify --additional --output output/NEW_REGISTERED_GATE
python -B -X utf8 -m tools.d1_list_candidate_rl_verify --representation --output output/NEW_REGISTERED_GATE
python -B -X utf8 -m tools.d1_list_candidate_rl_report --run output/NEW_REGISTERED_GATE --output docs/results/NEW_GATE --check-browser
```

환경호출은예산/owner/소스등록과함께실행되고소비ID재호출은차단된다. 새root재현도기존누적원장/남은전체예산을확인하고별도로등록해야하며위명령이예산초기화권한은아니다. 원시NP/전체이벤트/체크포인트는local output에두고작은코드·CSV·검증요약만공유한다.

결과 파일만 다시 만들려면 마지막 report 명령만 기존 run 경로에 실행한다. report는 native 환경·학습을 호출하지 않고 32개 원자료 해시와 전체 분모를 검사한다. `--check-browser`는 별도 headless Chrome 프로필로 한국어 화면을 렌더링하며 사용자의 기존 브라우저를 변경하지 않는다.
