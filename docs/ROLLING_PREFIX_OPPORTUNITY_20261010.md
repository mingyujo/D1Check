# 8개 공개 상태에서 공동 롤링의 새로운 첫 행동 기회 확인

작업 `ROLLING-PREFIX-OPPORTUNITY-05`, 사용자 “진행해봐” 승인에 따른 [세 AI 합의](ROLLING_EXPERT_REVIEW_20261010.md)의 다음 진단이다. **8개 상태를 복원했고, 기존 실제 행동과 다른 국소 개선 후보1개를 확인했다. 전체 정책 성능이나 실기기 절감은 아직 미확인이다.**

## 결과 전에 고정한 범위

기존 개발 mean의2seed×4부하에서 상태를 하나씩 선정했다. 해당 그룹의 최초 첫 행동 검사 차단 상태, 없으면 최초 비Band 행동으로 표시된 선정 상태다. 선택 시점·raw SHA를 새 예측 전에 [등록](results/rolling_prefix_opportunity_05/registration.json)했다. 좋은 결과를 찾기 위해 다른 상태로 바꾸지 않았다. 사용한 개발은 이미 평가한 자료이며 확인자료/새 독립평가가 아니다.

창4·과업 내 EDD·CPU전용 최소여유·원후보≤72·원선별8·0.25초 credit·3실행문맥·원CPU/GPU 지원·기한·계수는 유지했다. 최대792예측/45분·마지막5분저장, **새 native 환경/학습/기기 cap0**이다. 기존 정책 누적9749환경/1449학습과 닫힌IE480/480을 계승하며 초기화하지 않았다.

## 구현과 공개 상태 복원

`tools/d1_rolling_prefix_opportunity.py`는 기존 결정·도착·phase 전이 기록을 현재 시각까지 읽고 요청큐/실제lane소유/phase·since·dispatch, 모형 추정T/h·AP격자, 관측응답·credit/hold와 Band EMA를 복원한다. native simulator를 실행하지 않고 저장된 과거 선택만 적용한다. 미래 도착·실제 남은 실행시간·실현 비용벡터는 정책 관측에 넣지 않는다.

저장 전이의 ns가 정수화되어 콜백 시각과 정밀도가 다르다. 같은 전이에 대응하는 정확한 저장 콜백 시각이 있으면 그것을 쓰고, 없으면 기록된 정수를 유지한다. 저장기준 AP/J는 원1e−9 수치검사, P95는 로그 정수화1ns에 대응하는1e−6ms로 복원 정합을 확인했다. **이 정밀도 검사는 서비스 판정/SLA 허용폭이 아니다.** 후보 선정EPS1e−9와 최종 KPI 여유0은 바꾸지 않았다.

8개 모두 원 참조 예측과 선별 개수·기존우승 계획 포함을 복원했다. AP 최대복원차이는 약1.22e−10°C, J차이는0, P95최대차이는 약3.33e−7ms다. 완전한 모든원후보 순위가 별도로 저장돼 있지 않으므로 원순위를 전바이트로 대조했다고 주장하지 않는다. 선택공간과 결정적 선별식/개수/원우승 포함을 확인한 제한적 복원이다.

## 실제 대기 동작을 맞춘 예측

기존 `plan[:1]`은 대기 후 특정 요청을 강제로 배정할 수 있어 실제 hold와 달랐다. 새 경로는 실행prefix의 단건/지원병행 쌍만 확정한다. 냉각 대기는 timer가 끝난 뒤 Band가 현재큐를 선택하며, 자원 대기는 **최초 lane AVAILABLE**에서 끝난 뒤 Band로 이어간다. OUTPUT_READY/PERSISTED/WORKER_RELEASED만으로 lane이 반환됐다고 처리하거나 대기를 끝내지 않는다.

미래 새 도착은 예측에 없다. “대기 구간에 새 도착이 없다”는 조건부 투영이며 실제 새 도착은 hold를 취소·재판단하게 한다. 따라서 이 예측이 미래 서비스나 전체 실행경로를 보장하지 않는다. native Band의 `selected=None` 사건 대기는 resolved reference로 별도 표현하고 후보 대기로 추가하지 않았다.

정의검사5개: 실제 반환 전 resourcehold 유지, 냉각 뒤 버린 계획의 대상이 아닌 Band 선택, 응답과5단계반환 구분, 미래 도착 제외/worker소유 유지, 대기 descriptor의 미래배정 약속 없음. 원형 선택기17검사까지 통과했다. 모델fixture3예측은 아래170에 포함하고 native 환경은0이다.

## 8개 상태의 대조 결과

|상태|개발seed 끝자리·부하|시각 s|Band 대비 국소 이득|기존 실제 행동과 다른 이득|
|---|---|---:|---|---|
|0|101·낮은 부하|48.236185|있음|없음:기존과 같은0.25초 대기|
|1|101·큐 몰림|36.865211|없음|없음|
|2|101·순간 몰림|36.865211|없음|없음|
|3|101·지속 부하|61.150702|없음|없음:차단 뒤의 추가 안전 대안 없음|
|4|102·낮은 부하|49.297672|있음|없음:기존과 같은0.25초 대기|
|5|102·큐 몰림|36.784235|없음|없음|
|6|102·순간 몰림|37.486948|있음|**있음:즉시 탐지→0.25초 대기**|
|7|102·지속 부하|42.234523|있음|없음:기존과 같은0.25초 대기|

복원/진단8·불명0·Band 대비 조건부 이득4, 그중3은 이미 기존 정책이 실행한 행동이다. **새 절차의 추가 기회는1개**이며, “기존1등이 차단됐을 때 항상 더 좋은 대안이 있다”는 주장은 확인되지 않았다. 실제 차단 시점인 상태3에서는 추가이득0이다. 상태6은 전체 계획이 고른 첫 행동과 prefix 자체의 최선이 달랐던 사례다.

### 새로운 기회:상태6

개발 `813010102/burst/mean`, 현재37.486947579초, 도착한 탐지4건·현재lane둘다빈 상태다. 기존 우승 계획은 요청7을 CPU로 즉시 실행했다. 새 선택기는 동일shortlist의0.25초 냉각 대기를 선택했다. 미래 다른요청을 입력하거나 새로운 대기 길이를 만들지 않았다.

|실행시간 문맥|새prefix−Band 전체최고AP 예측|증분J 차이|긴급/일반 기한실패 차이|긴급P95 차이|
|---|---:|---:|---:|---:|
|mean|−0.014212°C|0|0/0|0|
|short_context|−0.014200°C|0|0/0|0|
|long_context|−0.014224°C|0|0/0|0|

현재4건의 예상 일반응답은 각각 약250ms 늦지만 현재기한 안의 처리라는 예측은 유지된다. 남은 에너지가 같은 이유는 같은CPU작업량·단독점유를 단순히 옮긴 동결모형의 계산이다. 실제 폰의 대기/제어 에너지가0이라는 뜻이 아니다. 약0.0142°C는 작은 모형 차이이며 표면온도/실제폰 절감으로 확정하지 않는다.

사후 원기록의 다음실제도착은37.949537597초의탐지다. 이 값은 선택이나 예측 입력에 쓰지 않았고 현재prefix의 전체 trace 효과를 보장하는 근거도 아니다. 과거 경로에서만 알려진 정보와 새 정책의 인과적 운영정보를 분리한다.

## 해석과 다음 범위

실행prefix를 직접 고르는 방식이 원선택과 달라질 수 있다는 **조건부 모형 witness1개**는 확보했다. 기존전체계획의 이득을 firstaction에 전용하지 않는 것이 실제 선택 차이를 만들 수 있다. 다만 이미 도착한 요청만의 예측이며, 다음재계획/미도착요청·누적열·실제판단시간이 포함된 정책성능은 아직 검증하지 않았다.

다음은 기존Band/Triton/원V2/새선택기의 동일한 새도착24조건＋실행의미fixture4, 예상100환경/상한112의 작은 별도 개발pilot 제안이다. 새selector를 기존controller에 연결할 때 timer/ANY AVAILABLE/arrival 취소·credit·쌍commit·기본복귀를 먼저 확인해야 한다. 원관측창·일반완료·미완료·판단시간·J/AP와전조건판정을 유지한다. 이번진단native cap0이라 **이 정책pilot·학습은 아직 등록/실행하지 않았다.** 기존확인24를 새후보의독립확인으로 재사용하지 않는다.

## 소비·검증·재현

실제 **170/792 모형예측**＝원screen98＋reference/prefix/fixture72, 실패0이다. 각시작/완료/실패를 fsync 장부에 기록하고 artifactSHA를 확인했다. 8입력raw·모형·실행소스SHA·새행동전체예측·같은snapshot출처를 보존했다. 새native/학습/기기0·누적9749/1449·owner없음·기본/strict/experiment_ready=false 보존이다. 별도 진행 중 모형v2/실측/Android/사용자변경/다른worktree는 수정·종료하지 않았다.

아래는 완료 원본을 검사·시각화하는 명령이며 새예측/환경은0이다.

```powershell
python -B -X utf8 -m tools.d1_rolling_prefix_opportunity_report
python -B -X utf8 -m unittest tools.test_d1_rolling_prefix_selection -v
```

실제실행은 `d1_rolling_prefix_opportunity_study register`→`python -B -X utf8 -m unittest tools.test_d1_rolling_prefix_opportunity -v`→`d1_rolling_prefix_opportunity_study run`이었다. 완료 폴더/상태선정/장부를 새폴더로초기화하거나 자동재개하지 않는다. 원형의resolved Band no-dispatch 추가는 새source hash로구분하며 이전review04의16검사 소스는 `source_versions`에 보존한다.

[대시보드](results/rolling_prefix_opportunity_05/index.html) · [8상태 실제행동 대조](results/rolling_prefix_opportunity_05/action_comparison.csv) · [전체후보예측](results/rolling_prefix_opportunity_05/candidate_forecasts.csv) · [검증](results/rolling_prefix_opportunity_05/verification.json).
