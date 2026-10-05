# 비지도학습 탐색: 부하 군집과 정책 선택

2026-10-05, 기준 `323c8628caa35369c577fb74bfa9888f3529eabb`. [대시보드](run_v1/index.html), [전체 비교](run_v1/comparison.csv), [선택/fallback](run_v1/decisions.csv), [동결](run_v1/freeze_before_evaluation.json), [검증](run_v1/verification.json).

**K-means·Gaussian mixture를 실제 구현·검증했다. 현재 결과에서는 새 최적화 정책으로 채택하지 않고 부하 유형 설명용 보조로 남긴다.** 군집이 안정적으로 나뉘는 것과 서비스/J/AP 이득은 달랐다. 순수 비지도학습이 좋은 정책을 알아낸다고 주장하지 않는다.

## 방법과 자료 역할

- 기존 지도학습과 같은5특징: 이전48요청의 분류 비율·평균/중앙 도착간격·간격CV·50ms미만 간격 비율.18조합×2개발seed=36이력만 StandardScaler와 군집 fitting에 사용.9조합은이번학습에서통째제외한다. 결과·정책 이름·J/AP·기한은 **군집 fitting에 입력하지 않는다**.
- K-means는 k=3/6 중 개발 silhouette 최대, GMM은 diagonal covariance의 k=3/6 중 개발 BIC 최소로 선정. random_state20261005, 나머지 설정과 scaler/center/분산은 동결JSON과 코드에 있다. 평가 성적을 보고 k를 바꾸지 않았다. PCA2차원은 그림에만 사용한다.
- 각 군집에서 모든 개발 이력/처리문맥의 요청을 기한 안에 완료한 정책만 연결한다. 그중 에너지 목적은 평균J 우선, 열 목적은 평균최고AP 우선. **이 연결 단계는 개발 결과를 사용하므로 전체는 비지도군집＋성과 기반 선택의 혼합 방식**이다.
- 군집별 최대 개발표준화거리 밖이거나 적격 정책이 없으면 EFT. 이 거리 규칙은 보정된 이상확률/안전 보장이 아니다. 미래 이력·도착·실현시간·AP를 입력하지 않는다. 기존48요청 이력 부족/미지원 입력 거절도 유지한다.
- 이전 구간과 다음 구간은 같은 부하분포라는 가정이며, 열초기조건은 기존initial0로 고정한다. 연속 열이력·분포 변화·요청별 온라인 선택을 검증한 것이 아니다.

기존 저장seed91002/91003×27조합×3처리문맥=162조건의 모든 정책 성적을 재사용했다. 두방법×두목적=648정책-조건 판독이며 새 시뮬레이션은0이다. **이미 본 자료의 사후 평가**이며 새 독립 확인이 아니다. 기존 지도학습 두 선정모형도 원래 개발자료로만 재구성해 정확히 같은 입력에서 비교했다. 이전 fresh seed123001/123002의 숫자와 직접 섞지 않는다.

방법 참고: [KMeans 공식 API](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html), [GaussianMixture와 BIC 공식 API](https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html). 실행 환경은 기존 scikit-learn1.7.2이며 버전 업그레이드 없음. DBSCAN·오토인코더 등은 이번에 시험하지 않았다.36이력·5특징에서 복잡한 표현학습까지 늘리지 않았다.

## 결과

두 방법 모두6군집을 선택했다. K-means silhouette0.546254(3군집0.471274), GMM BIC−146.517680(3군집−40.169086). 동일18조건의 두개발이력 배정 ARI는 양쪽1.0이다. 이는 두합성이력에서의 일관성이고 물리상태/장기분포의 안정성 증거가 아니다. 군집의 절반은 모든 개발조건을 만족하는 정책이 없었다.

| 방식/목적 | 기한충족/7776 | EFT 대비 평균 J/120초 | EFT 대비 최고AP | EFT보다 서비스 악화 사례/162 |
|---|---:|---:|---:|---:|
| K-means 에너지 |6897|−0.000900|+0.000090°C|0|
| GMM 에너지 |6897|−0.000900|+0.000090°C|0|
| K-means 열 |6897|+0.040714|−0.015505°C|0|
| GMM 열 |6897|+0.040714|−0.015505°C|0|

EFT도6897/7776이며 모든요청기한충족118/162이다. 나머지과부하 실패를 삭제하지 않았다. 에너지와열 공동개선은확보하지못했다. 에너지쪽의0.0009J차이를 실제 절감으로 해석할 근거는없다. 열쪽은 에너지증가와 긴급P95평균+45.061ms/일반평균+63.586ms가동반됐다.

- K-means:54이력 중 군집정책8회,거리fallback23회,적격없음23회. GMM:10/22/22회. **대부분 EFT 유지**였고 군집/선택 차이에도 최종 성적은 같았다. 서비스가 유지된 것을 새로운 강한 제약보장으로 해석하지 않는다.
- 같은 입력의 지도학습 에너지tree:6882/7776,−0.113026J/+0.051499°C. 비지도연결은추가15기한손해를만들지않았지만에너지이득도거의없다. 지도학습thermalboosting:6897/7776,+0.069592J/−0.030342°C. 서로다른상충이며단일순위를만들지않는다. [동일입력표](run_v1/supervised_same_inputs.csv).
- 범위: 기기전체J0–120초/AP35–180초, 기존정밀도/입력/resident/초기조건/지원cell만. 실제AP/J측정·새열모형·스로틀·미지원backend근거를추가한것이아니다. strict/experiment_ready=false 불변.

## 결론과 다음 PC 행동 하나

비지도학습은 도착유형을 압축·표시하거나 모형 밖 입력을 경고하는 보조로는 사용할 수 있다. 그러나 **특징이 비슷한 군집이 정책 효과까지 비슷한 군집은 아니다**. 현재36이력과보수적인군집별기한조건에서는많은조건이EFT로돌아가므로 주스케줄러로채택하지않는다. 거리경계를느슨하게하거나군집수를결과에맞춰늘리는후속탐색은하지않았다.

다음은 앞서 특정한 지도학습의 `g1.2_c0.75_b8` 실패 ledger에서 **실제 slack 소모와 배정 순서를 분해해 학습과 별개로 필요한 서비스 제약을 특정하는 것**이다. 또다른학습기나실측을자동추가하지않는다.

## 구현·검증·재현

- 새8검사＋관련14검사=22PASS(skip0): 실제두군집fitting,재현성,전체조합분리,평가label변조와정책연결불변,범위밖/적격없음fallback,미래도착거절,결측0대입차단. 기존CSV읽기의ResourceWarning은남았으나본문검사통과.
-36비교행의전체요청분모·기한수·J/AP/AP면적평균차이를원저장CSV와재집계,source/physical hash불변확인. 새요청원장재생0,기기명령0. 그림시각확인. 사용자HTML·다른worktree·원본/FAIL/계획보존.
- `tools/d1_unsupervised_selector.py`와 동결JSON에 군집 파라미터를 공유한다. 모델바이너리·개인기기식별정보·대용량원장은 추가하지 않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
$env:OMP_NUM_THREADS='1'
python -B -m unittest tools.test_d1_unsupervised_selector tools.test_d1_supervised_selector
python -B -m tools.d1_unsupervised_selector --output docs/results/unsupervised_selector_01/reproduction_v1
```

저장소루트에서실행하며Python은기존conda환경또는동등한sklearn/numpy/matplotlib환경이다. 입력은 `docs/results/scheduler_conditions_01/run_v2/results.csv`, 물리동일성확인은 기존 `online_policy_study_01/overnight_sustained_run01/{model,initial_inputs}.json`. 새기기계획/소비claim 없음.
