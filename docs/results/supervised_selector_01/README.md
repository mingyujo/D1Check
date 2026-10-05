# 이전 요청 이력 기반 지도학습 정책 선택기 — PC 평가

2026-10-05. 기준 HEAD `f4f6049826807ed5f7e4471ef6ae7f7cd82724bb` + 이번 미커밋 소스에서 검증했다. [대시보드](run_v1/index.html), [모든 결과](run_v1/metrics.csv), [조건별 결정](run_v1/decisions.csv), [검증](run_v1/verification.json).

**구현·학습·분리 평가 완료. 에너지 선택기는 미채택, 열 선택기는 상충 분석용 PC 후보로만 보존한다.** 강화학습 없이 이전 요청의 도착·작업 통계로 다음48요청에 적용할 기존 스케줄러를 선택한다. 기본 정책·strict 지원·물리 계수·experiment_ready=false는 변경하지 않았다. 폰 절감·정책 우월성 확인이 아니다.

## 무엇을 학습했는가

- 작은 결정나무와 histogram gradient boosting을 비교했다. CatBoost는 현재 환경에 없어 새 의존성을 설치하지 않고 scikit-learn 1.7.2의 `HistGradientBoostingRegressor`를 사용했다. CatBoost 평가 결과로 부르지 않는다.
- 입력5개: **이미 도착한 이전48요청**의 분류 비율, 평균·중앙 도착간격, 간격 CV, 50ms 미만 간격 비율. 정책8개는 one-hot으로 표현한다. envelope ID·seed·미래 도착·미래 완료·실현 처리문맥·미래 AP/J는 입력하지 않는다.
- 출력4개: 세 고정 처리문맥 중 최대 기한위반 비율, 평균 기기전체 J, 평균 최고 AP, 평균 AP 초과면적. 서로 다른 단위가 트리 분할을 지배하지 않도록 출력별 회귀모형을 따로 학습했다. 이는 기기 물리모형의 재적합이 아니라 **기존 시뮬레이터 결과의 대리 예측**이다.
- 예상 위반 수가0.5건/48건 이하인 후보 중 에너지 목적은 J→최고AP→AP면적, 열 목적은 최고AP→AP면적→J 순으로 선택한다. 0.5는 사전에 고정한 결정 규칙이며 정확도 합격선·안전 보장이 아니다. 음수 위반 회귀값도 가능한 원시 예측이며 확률로 해석하지 않는다.
- 입력이 학습 feature box 밖이거나 예측상 적격 후보가 없으면 EFT로 돌아간다. feature box는 결합분포/OOD 판정의 충분조건이 아니다. EFT도 과부하에서 기한을 보장하지 않는다.48요청 이력이 없는 cold start는 현재 API에서 거절한다.
- 트리 `max_depth=5,min_samples_leaf=4`; 부스팅 `max_iter=100,max_depth=3,min_samples_leaf=5,learning_rate=.05,early_stopping=False`. seed20261005. 결과를 본 뒤 구조/하이퍼파라미터/결정 기준을 다시 맞추지 않았다.

## 실험 경계와 자료 분리

1. 기존 [조건별 연구](../scheduler_conditions_01/README.md)의27조합 중 `(간격 index + 작업비율 index + burst index) % 3 == 0`인9조합을 **이번 학습과 모델 선정에서 통째 제외**했다. 이9조합도 과거 연구에서 이미 본 조건이다. 새로운 연구 영역이나 독립 실기기 자료라고 부르지 않는다.
2. 나머지18조합의 개발seed81001/81002만 fitting: **36합성 이력×8정책=288학습 행**. 각 target은3처리문맥을 집계했다.288행/센서표본/시뮬레이션 수를 독립 기기 세션 수로 세지 않는다.
3. 같은18조합의 저장seed91001×3문맥54조건으로 두 학습기 중 모델을 선택했다. 위반건수 우선, 그 다음 목적 비용 차이. 에너지 tree(362위반, EFT대비−0.120760J), thermal boosting(360위반, −0.019923°C). tree thermal은366위반, boosting energy는362위반/−0.088686J였다. 전체 과부하도 포함하므로 개발적격17조건 연구와 분모가 다르다.
4. [동결된 모형 SHA·선정·새 입력별 결정](run_v1/freeze_before_final.json)을 **최종 시뮬레이션 전에** 저장했다. seed123001/123002×27조합×3처리문맥=162평가 조건. 두 모형/두 목적 및 CPU·split·EFT의 중복 정책을 공유해 **594시뮬레이션/50.803초**를 실행했다. 선정하지 않은 모형의 최종 성적도 모두 보존했다.

이전 관측 이력은 별도 RNG(seed+700000)로 만들고 모두 평가 시작 이전의 timestamp로 옮겼다. 다음 구간과 **같은 정상 부하 분포**를 공유한다는 가정이다. 미래 trace의 앞부분을 엿본 것이 아니지만 급격한 부하 변화에 대한 검증은 아니다. 이전 구간의 소비/잔열을 이어 시뮬레이션하지 않고 평가 구간은 기존 동일 initial0에서 시작한다. 따라서 연속 운용·변하는 초기 AP·세션 중 재선택으로 확대하지 않는다. 대기열·slack·현재 AP를 활용한 요청별 학습 제어는 이번 구현 범위가 아니다.

기존 상태/계수, classification CPU/GPU·detection CPU와 CG_DC만 사용한다. 처리시간 mean/short/long 벡터의 새 도착형태 전용은 기존 탐색 가정이다. J창0–120초, AP35–180초,48요청·긴급1.5초/일반6초는 그대로다. 센서 기반 절대 J 정확도 미인증, A24 열→처리시간 미검증도 그대로다.

## 결과 — 선정 모형, 전체162조건 평균

| 선택기 | 기준 | 기한 충족/7776 | 기준 기한 충족 | ΔJ/120초 | Δ최고AP | 전체48요청 기한 충족 사례/162 |
|---|---|---:|---:|---:|---:|---:|
| 에너지/tree | EFT |6772|6788|−0.105158|+0.053325°C|100|
| 열/boosting | EFT |6788|6788|+0.086789|−0.040130°C|105|
| 에너지/tree | 고정split |6772|6163|−0.657564|−0.101093°C|100|
| 열/boosting | 고정split |6788|6163|−0.465616|−0.194548°C|105|

실패도 포함한 평균으로, 모든 조건의 절감이나 서비스 적격성을 뜻하지 않는다. 6개새seed/처리문맥에서 모두 기한을 충족하고 J/최고AP/AP면적을 모두 낮춘 **조건 수**는 split대비 에너지8/27·열10/27, EFT대비0/27이다. 각각 전 요청 기한을 충족한 조건은16/27·17/27이다. 비교 기준별 모든 수치와 P95/일반 응답 손해는 [metrics](run_v1/metrics.csv), [조건별 결과](run_v1/comparison.csv)에 있다.

### 미학습 조합과 오류

- 미학습9조합54조건: 에너지2224/2592기한 충족(EFT2240), 평균−0.130791J/+0.068866°C. 열2240/2592로EFT와같고 +0.071584J/−0.040647°C.
- 에너지 선택기의 **추가16건 위반은 전부** 평균1.2초·분류75%·burst8 조합에서 발생했다. PAIR_COALESCE를 고른6사례 중5사례의 기한충족은44/44/45/45/46개로 EFT48개보다 나빴다. 결합 조건 일반화 및 서비스 위험 예측 실패다. 이 결과 뒤 선택기를 다시 맞추지 않았다.
- 열 선택기는162사례 모두 EFT보다 기한충족 수가 나쁘지 않았다. 그러나 에너지 평균+0.086789J, 긴급P95 평균+92.584ms의 대가가 있다. 이 증가를 숨기고 에너지·열 공동 최적화 성공으로 표현하지 않는다.
- 54개 평가 이력 중 에너지/tree는26회 학습 선택,16회 위험 fallback,12회 feature-box fallback. 열/boosting은18회 학습 선택,24회 위험 fallback,12회 feature-box fallback이다. 열 선택기의 상당 부분은 EFT와 같다. [fallback 분모](run_v1/fallback.csv).
- [회귀 예측 오차](run_v1/prediction_errors.csv)는 이번에 실제 평가한 정책 부분집합에서 산출했다. 모든8행동의 불편 정확도 추정은 아니며, 부하 변화·보정된 불확실성 보장은 없다.

## 판정과 다음 행동

학습 기반 선택이 구현 가능함은 확인했다. **에너지 후보는 미학습 조합의 서비스 손해 때문에 미채택**이다. 열 후보는 열/응답/J 절충을 분석하는 PC 후보로만 남긴다. 강한 EFT 대비 공동개선/실기기 효과/기본 정책 채택은 미완료이며, 새 실측이나 후보 재튜닝은 하지 않았다.

다음 PC 행동 하나: 저장된 `g1.2_c0.75_b8`의5실패 ledger에서 coalescing 지연·GPU 배정·긴급응답 경계를 분해하여 **학습 선택과 별개로 필요한 서비스 제약**을 특정한다. 같은학습 반복이나 추가 실측을 자동 권고하지 않는다.

## 검증·재현

- 관련26테스트: 실제 두 estimator fit/예측, 미래 timestamp·미지원 task/policy·결측·이력부족·정렬·fallback·비학습조합/seed분리·평가 label 변화와 fitting 불변·기존 정책 경계. PC 테스트이며 물리 검증이 아니다.
-594ledger/28512요청의 도착·기한 분모·실제lane 해제·시간순서와 모든 비용을 재집계. 독립 J 합산 차이 최대2.8422e−14J. 기존 model/initial/source 해시 불변, 모든 동결 결정 재현. PNG 시각 확인 및 링크 점검. 실제 실행한 소스는 동결 hash로 특정한다.
- ADB·기기·설치·APK·새기기계획·claim0. 사용자HTML·다른worktree·기존FAIL·원자료 보존.

저장된 결과 화면·CSV·동결결정은 공유한다. 약18.6MB 요청 원장과 pickle 모델은 `run_v1/local_ledgers.jsonl`, `run_v1/local_models.pkl`에 로컬 보존하며 Git에는 넣지 않는다. 후자는 직접 생성한 신뢰할 수 있는 로컬 파일만 로드한다. pickle 해시와 원장 해시는 동결/검증 JSON에 있다. 모델은 저장된 학습 CSV 원본과 코드/버전으로 재학습 재현할 수 있다. 원장 재회계는 해당 로컬 원장이 필요하다. 새 출력 디렉터리의 재현은 **PC594회 재실행**이며 실측이 아니다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
$env:OMP_NUM_THREADS='1'
& C:/Users/LG/anaconda3/python.exe -B -m unittest tools.test_d1_supervised_selector tools.test_d1_scheduler_conditions tools.test_d1_scheduler_condition_selector
& C:/Users/LG/anaconda3/python.exe -B -m tools.d1_supervised_selector --output docs/results/supervised_selector_01/reproduction_v1
& C:/Users/LG/anaconda3/python.exe -B -m tools.d1_supervised_selector_report --folder docs/results/supervised_selector_01/reproduction_v1
```

Python 실행 경로는 동등한 로컬 Python으로 바꿀 수 있다. 데이터/소스 경로는 저장소 상대 경로다. scikit-learn1.7.2·numpy·matplotlib 및 기존 엔진 의존성이 필요하다. 기반 결과는 `docs/results/scheduler_conditions_01/run_v2/results.csv`, 물리 입력은 `docs/results/online_policy_study_01/overnight_sustained_run01/{model,initial_inputs}.json`이다. 기본 시뮬레이터/실기기 정책으로 자동 연결하지 않는다.
