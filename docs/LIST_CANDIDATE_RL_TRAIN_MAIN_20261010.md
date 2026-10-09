# 리스트 + RL 파일럿과 본학습 연장

2026-10-10 · `LIST-CANDIDATE-RL-TRAIN-MAIN-05` · **본학습·확인 평가 완료, RL 미채택**

**학습량을64→128회로 늘리자 세 seed 모두 긴급 응답과 기한 성적이 좋아졌다. 그러나 Band/Triton/L0 대비 전체 서비스·AP·에너지 비악화를 만족하지 못했다.** 이번 예산 안에서는 RL128을 최종 정책으로 채택하지 않는다. 수렴 완료나 RL 일반의 실패라는 결론은 아니다.

[오프라인 화면·CSV·그림](results/list_candidate_rl_train_main_01/README.md) · [검증/원장/재개](results/list_candidate_rl_train_main_01/verification.json) · [세 AI 회의](results/list_candidate_rl_train_main_01/expert_main_decision.json)

최신 사용자 승인에 따라 유효성 검증 → 3seed 작은 학습 → 미개선이면 기존 모바일·산업공학·RL AI 회의 → 본학습까지 진행한다. 성과 판정은 유지하며, 개발 미적격 뒤에도 회의 후 제한된 본학습을 수행하는 지시만 별도로 적용한다.

## 결과 전 고정한 계약

- 누적6,549환경/641학습을 계승한다. 설계 전체상한1,536환경에는 이미 실행한 구현32가 포함되며 이번 후속 최대1,504환경이다. 학습상한416도 유지한다.
- seed11/23/37 각각64episode 파일럿 뒤 같은 actor·critic·Adam·승수·RNG에서64episode 추가, 총384학습이다. 기존 조건부 이력제거192학습 몫을 본학습192연장으로 배분하며 둘을 함께 실행하지 않는다.
- 실제 재개 fixture는8L0참조＋원본16학습＋재개4학습=28환경/20학습. 실제update 후 partial4를 저장하고 다음4episode/update를 exact 대조한다. host timing과 두 분기의 외부 실제소비는 분리하며 budget을 복원·초기화하지 않는다. episode/update 경계 재개만 지원하고 다음 engine은 새 Controller다.
- 새 단계 clock은 등록부터2시간/마지막5분 저장이며 이전 구현clock·소비는 보존한다. 환경 진입과 optimizer update 전에 시간·소스·모형을 검사한다. 완료 환경은 입력/역할/학습 전 network/hash가 같을 때만 재사용하며 다른가중치 warmstart 재사용을 금지한다.
- 훈련64조건=16도착seed×4부하/3실현문맥 사전순환. 개발24=별도2seed×4부하×3문맥, 확인48=별도4seed×4부하×3문맥이다. seed·요청열 해시를 결과 전 등록한다. 실현 문맥/미래 도착/실제 잔여시간은 actor 입력이 아니다.
- 원 hyperparameter 유지:8episode/update·4epoch·minibatch256·Adam lr.0003/eps1e-5·clip.2·entropy.01·value.5·gradclip.5·KL.03·gamma1. episode-sum actor/episode-mean critic·entropy, 공통 advantage 정규화와 N/m frame 보정. AP 주보상·J signed·서비스 positive-part와 기존 승수 갱신을 유지한다. 튜닝0이다.
- 기본/학습참조L0, 같은bank 고정선택기, 원 EDD·ListV2·Band·Triton, PPO3seed를 비교한다. Band/Triton은 평가 전용이다. terminal64/128과 seed전부를 보존하며 최고seed·개발최우수actor를 고르지 않는다.
- 원 model/initial/kernel·CPU/GPU 지원·CG_DC 최대2건·비선점·1.5/6초 기한·응답/저장/lane 경계는 유지한다. NPU/기기/ADB/설치/새실측0·기본/strict/experiment_ready=false이며 별도 모형정확도 작업을 RL에 적용하지 않는다.

## 표현성은 제외 근거로 닫았다

원3성공 일정의 arrival/실제dispatch/lane 반환을 순수 연산으로 대조했다. 실제 물리 대안이 있는데 배정하지 않은 시간만 합산하고 ns반올림을 보수적으로 줄인다. 필요한 credit 하한 mean0.3369242495/short0.3863225635/long0.2920395625초가 .25를 초과한다. **현재 후보로 그3일정을 정확히 재현할 수 없다는 한계**이며 후보/대기 한도를 자동 확대하지 않는다. 이 제한을 명시한 현재 후보 안의 학습 성과를 따로 평가한다.

## 고정 예산

| 항목 | 환경 | 학습 |
|---|---:|---:|
| 완료된 구현 gate |32|0|
| 재개 fixture·L0참조 |28|20|
| 훈련 L0공통참조 |64|0|
| 3seed 파일럿 |192|192|
| 개발24×9역할 |216|0|
| 3seed 본학습 연장 |192|192|
| 본학습 개발 평가 |72|0|
| 확인48×9역할 |432|0|
| 유망할 때만 대기제거 추론 평가 |144|0|
| 최대 예상 합계 |1372|404|

전체cap1536/416, 실패도 차감한다. 대기제거는 같은 가중치의 추론 행동 제한이며 재학습과 구분한다. 전량/서비스/AP/J 비악화·같은 부하군 반복 개선의 성과 기준은 그대로다. 본학습 수행과 최종 채택을 구분한다.

## 실제 학습·평가 규모

- 3seed 각각64파일럿＋64추가=128episode/16update/256Adam step. 본학습 총384episode이며 실제 재개 fixture20을 별도 포함한 이번 학습은404회다. optimizer step 총816(본학습768＋재개48)이다.
- 이번1196환경/실행 실패0·예정78,936/완료78,936, 기존구현32포함설계1228/1536·학습404/416. 누적7,745환경/1,045학습. 모델/기기 계수를 새로 fit하거나 기기·ADB를 실행하지 않았다.
- 개발24조건×9역할216회,128개발actor72회, 새확인48조건×9역할432회. 비교 CSV864행에는128개발에서 재사용한 기준선144행이 포함되며 이를 새 환경 실행으로 세지 않는다.
- CSV에는 CPU/GPU lane 점유·점유 병행·모형 EXECUTING 단계 병행 시간과 측정 가능한 PC 판단 P50/P95/max를 기록했다. lane 점유를 하드웨어 실행 병행으로 바꾸어 부르지 않으며 기준선에서 따로 기록하지 않은 판단시간과 실제 폰 제어비용은 계산 불가로 남겼다.
- 학습 seed별128episode의 실제 native＋optimizer 계산 합은41.38/42.34/43.38초다. 참조·평가·직렬화·회의·파일처리 시간은 이 합에서 제외된다. 원 episode/update별 시간을 보존했다.

## 같은 개발 자료에서64→128의 변화

각행은24조건·1,584예정/완료를 합친다. P95는 전체 요청을 pool한 P95가 아니라 **조건별 P95 평균**이다.

| 학습 seed | 긴급 위반64→128 | 일반 위반64→128 | 긴급 P95 평균 ms64→128 | 평균 J64→128 | 최고 모형 AP 평균64→128 |
|---|---:|---:|---:|---:|---:|
|11|171→0|153→24|1368.42→705.31|152.036→152.323|30.9051→30.8690|
|23|8→0|24→24|1108.13→397.52|152.547→152.761|30.9313→30.9196|
|37|4→0|436→396|946.49→652.09|152.747→152.504|30.8886→30.8872|

L0/Band의 같은자료 긴급P95 평균349.24ms·일반위반24와 비교하면128도 전체 조건에서 동등 서비스를 지키지 못한다. 216개 대응(3seed×24조건×L0/Band/Triton)의 개별 cell 통과는0→54,서비스악화는216→147로 줄었지만 전조건 M/G는 모두 미적격이다. 평균이나 좋은 seed만 골라 결과를 바꾸지 않는다.

## 새 확인48조건의 성적

전정책각3,168예정/완료·미완료0·긴급위반0이다. 원단위와 조건별 결과를 모두 CSV로 보존한다.

| 정책 | 일반 기한 위반 합 | 긴급 P95 조건평균 ms | 기기 J120 조건평균 | 최고 모형 AP 조건평균 °C |
|---|---:|---:|---:|---:|
|서비스 우선 L0|39|356.41|152.323|30.8687|
|같은 후보 고정 선택기|678|284.99|152.377|30.8469|
|EDD+ECT|66|305.85|152.383|30.8208|
|Band 요청 단위 적용|39|356.41|152.278|30.8596|
|Triton 요청 단위 적용|39|390.88|152.757|30.9033|
|이전 열·에너지 리스트|69|306.59|152.242|30.8431|
|RL128 seed11|39|649.80|152.272|30.8687|
|RL128 seed23|39|390.88|152.757|30.9033|
|RL128 seed37|798|621.71|152.486|30.8684|

확인432개 대응 중 cell통과117/서비스악화273, 전조건 M/G 적격0이다. seed11의 작은 평균 J감소는 P95와 AP 악화를 동반하며 우위가 아니다. seed23은 확인 KPI가 Triton과 같은 수준이고 Band를 이긴 증거가 없다. seed37은 일반기한이 크게 악화했다. 완료량을 줄여 비용을 낮춘 경우는 없었지만 **완료했다는 사실만으로 서비스 유지에 성공한 것도 아니다.**

추천은 현 연구용 기준선과 L0를 보존하고 RL128을 미채택하는 것이다. 비교조건 안에서도 Band가 모든 요청 기한을 완벽히 지킨다는 뜻은 아니며 제품 기본 정책을 자동 변경하지 않는다. 작은 AP/J 차이를 모형 오차보다 확실한 실물 절감으로 주장하지 않는다. 실현문맥3개는 독립 도착 반복이 아니며 확인 도착seed4개의 결과를 일반적 통계 우월성으로 확대하지 않는다.

## 전문가 회의와 진단

파일럿 미개선 뒤 같은 모바일·산업공학·RL AI가 독립 검토→직접 반론→교차 합의를 수행했다. 현재 실행 P1 증거는 없고, 동일 learner에서 추가64회로 학습량 반응을 확인하는 데 합의했다. 사람 전문가 인증은 아니다.

64→128에서 정보가 있는 선택의 대기 비율은 seed11 97.93→51.42%, seed23 53.34→0%, seed37 96.29→79.79%였다. 저장된 `exp(logprob)`로 본 argmax 최대확률의 균등확률 대비 초과는 평균0.0048~0.0202로 작았다. 작은 점수 차이가 반복대기를 만드는 원인 후보이며 sampling/argmax만의 인과효과는 아니다. 훈련/개발 입력·문맥·weights도 다르다.

실제 actor gradient는 critic보다 컸고 λJ는양수였다. critic압도·J신호0이라는 설명은 기각했다. gradient clipping 비율을 Adam의 parameterstep 감소율로 해석하지 않고 raw advantage/frame평균을 실제 온도 절감으로 대체하지 않는다. 보상/entropy/λ설정/평가/seed/tie 기준을 튜닝하지 않았다.

## 오류 처리·검증·남은 범위

- 기존 ListV2의 `RuleNetwork`에 `state_dict`를 호출한 비교 초기화 오류1회는 native 진입 전에 발생했다. Torch 모듈만 해시하도록 최소 수정했다. 원 등록/driver/7checkpoint backup을 보존하고 dependency metadata만 이관했으며 나머지 θ/Adam/λ/RNG/partial/cursor payload가 exact임을 확인했다. clock·cap·입력은 변경0이다.
- offline browser checker 메타데이터 이식 오류2회(ROOT/sha helper 누락)는 실제 화면·filter 검사 뒤 발견해 고쳤다. 학습·환경 호출0이며 최종864행·seed11필터96행·reset864·6그림 로드가 통과했다.
- 순수기능12＋학습6＋표현성10＋실행 guard5=33검사 PASS, 실제 재개 gate PASS. 전1196원자료·controller SHA, 요청ID/전체 분모, 기한위반, 응답2/3phase, 실제5phase lane반환·자원 용량·CG_DC 지원을 재검증했다. 1ns는 분리 반올림의 경계 검사이며 KPI epsilon은0이다.
- 주어진 예산의 본학습과 고정 확인은 완료했다. 조건부 대기제거144회는 유망성 미달로 실행0,도착이력제거 학습은192연장에 예산을 배분했으므로0이다. 부족한 수렴 증거나 새 최적 일정 존재 여부를 예산 여유로 자동 추가 탐색하지 않는다.
- AP는 동결모형 채널이며 surface 온도·phone 제어J·임의 온도한도 초과시간은 미지원이다. 새로운 물리 정책 효과는 추가 실기기 확인 없이 확정할 수 없다. 중간 engine/minibatch 재개와 NPU 학습은 이번 범위 밖이다.

## 재현 명령

실제 수행한순서는 register→gate→pilot→회의 후 main→confirmation이다. 등록된 clock/cap과 완료 ID는 이미 소비했으며 새폴더/대화로 예산을 초기화해 재학습하지 않는다. 다음은 **완료 원자료의 읽기 전용 검증·산출물 재생성** 명령이다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_list_candidate_rl tools.test_d1_list_candidate_rl_training tools.test_d1_list_candidate_rl_representation tools.test_d1_list_candidate_rl_run -v
python -B -X utf8 -m tools.d1_list_candidate_rl_main_check --run output/list_candidate_rl_train_main_20261010_v1
python -B -X utf8 -m tools.d1_list_candidate_rl_diagnostics --run output/list_candidate_rl_train_main_20261010_v1
python -B -X utf8 -m tools.d1_list_candidate_rl_main_report --run output/list_candidate_rl_train_main_20261010_v1 --output docs/results/list_candidate_rl_train_main_01 --plots
python -B -X utf8 -m tools.d1_list_candidate_rl_main_browser_check docs/results/list_candidate_rl_train_main_01/index.html 864 96
```

학습 실행형식은 `python -B -X utf8 -m tools.d1_list_candidate_rl_run --phase PHASE --output RUN`이며 PHASE는 register/gate/pilot/main/confirmation이다. 새실험은 현재누적/남은cap·fresh입력·clock을 먼저 등록해야하고 이예시가 재시작 승인이나 새예산은 아니다. 대용량 episode·weights/Adam·checkpoint는local output에 보존하고 코드·작은CSV·그림·hash검증만 공유한다.
