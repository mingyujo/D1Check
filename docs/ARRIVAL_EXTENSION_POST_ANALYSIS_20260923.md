# 비동시 도착 독립 평가 PC 후처리와 확장 시뮬레이션 적합성

- 작업 ID: `ARRIVAL-EXT-01-POST`
- 입력: 27세션 A24 독립 평가 원본과 plan SHA `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`
- 기준 판정: `CONDITIONAL−CPU_URGENT`의 동결 joint primary **FAIL 유지**
- 범위: PC read-only 재현·시각화·plan-only 시뮬레이션 설계. ADB·설치·추가 실측·본 시뮬레이션 없음.

## 재현 검증

기존 `tools.d1_arrival_analysis`를 새 출력 root에서 다시 실행해 27/27 completed와 27 paired comparison을 확인했다. 새 감사 도구는 원본694파일을 기존 hash inventory와 전수 대조하고 plan의 27 manifest hash, raw manifest, 198개 request ID·terminal·monotonic 순서와 warmup216을 다시 확인했다. `session_kpi.json`, `paired_kpi.json`, `evaluation_summary.json`은 기존 v2 분석과 semantic equality를 통과했다. 정책별66건(urgent17/normal49), 전체 urgent51/normal147이며 실패·거절·만료·미완료·late success·제외는 모두0이다.

조건 구성은 주 classification-urgent burst 6 paired block/18세션/144요청, 역할반전 burst·low·queue가 각각1 paired block/3세션이며 요청 수는 24/12/18이다. 정책 순서가 달라도 같은 `pair_id`를 유지한 완전한 세 정책 묶음으로 비교한다.

### 지표 계산 경계

- 동결 urgent P95: 세션당 urgent 완료2건에 nearest-rank P95를 적용한다. 두 건에서는 최댓값이다. 이 세션 KPI를 주 조건6개 block에서 평균한다.
- 주 조건 pooled urgent P95: 12개 urgent 요청을 정책별로 합쳐 nearest-rank P95를 별도로 계산한 탐색적 기술값이다. FIFO/긴급우선/조건부 `1641.5/417.1/397.2ms`이며 동결 주 판정에 사용하지 않는다.
- makespan: `workload_start_ns`부터 그 세션 마지막 `worker_release_ns`까지다. 도착 구간과 drain이 포함된다.
- throughput: 성공 요청 수를 위 makespan으로 나눈다.
- 불확실성: 요청을 독립 표본으로 재표집하지 않는다. 주 조건의 같은 workload를 유지한 6개 paired block 차이에 양측 paired t 95% CI를 적용한다. bootstrap은 사용하지 않았다.

분석 오류나 동결 판정 변화는 발견되지 않았다. 동결 `conditional_joint_primary_pass=false`를 유지한다.

## 결과의 세 층위

### 사전 동결 주 평가

`CPU_URGENT−CPU_FIFO`는 urgent P95 `-1228.1ms`, 상대 `-75.15%`이고 normal 평균응답은 `+88.2ms/+4.72%`다. 긴급10% 최소효과와 normal10% 손실 기준을 통과했다. `CONDITIONAL−CPU_URGENT`는 urgent P95 `-14.2ms/-3.48%`, normal 평균응답 `-605.5ms/-30.93%`다. normal 기준은 통과했지만 긴급10% 최소효과는 실패했으므로 joint primary는 **FAIL**이다.

### 사전 지정 보조 지표

조건부 정책은 CPU 긴급 우선 대비 makespan `-1.202s`, throughput `+0.886req/s`였다. urgent miss0%, normal on-time100%, completion100%는 모든 정책에서 같아 구분력이 없다. 2초/8초는 UX SLA가 아닌 engineering scenario이며 0건 관측으로 2%p 비열등성을 입증하지 않는다.

### 평가 공개 후 탐색적 해석

CPU만 쓰는 FIFO와 긴급 우선의 차이가 긴급 개선 대부분을 설명한다. 조건부 정책은 주 조건에서 normal 탐지14건을 GPU로 보조해 일반 대기·makespan·throughput을 개선했다. 긴급 추가 개선은 작다. low와 queue는 각1 block이고 조건부 urgent P95가 CPU 긴급 우선보다 각각9.7ms,6.8ms 느렸다. 이는 전체 조건의 긴급 비열등성이 아니라 조건 의존성 신호다. 고정 CPU/GPU 분리는 평가하지 않아 적응적 판단 자체의 우월성은 결론낼 수 없다.

## 그림과 대표 선정

대표 간트는 기존 분석 코드가 결과와 무관하게 사용한 규칙을 명문화했다: plan에서 첫 주 조건 paired block인 `replicate=0`의 세 정책을 전부 사용한다. 성능이 좋은 세션을 고르지 않는다. 검은 tick은 예정 도착, 회색은 queue entry부터 실행 시작까지, 파랑/빨강은 CPU/GPU의 실행 시작부터 worker release까지다. 그림은 PNG와 SVG, 모든 그래프 입력은 CSV로 별도 보존한다.

## 확장 시뮬레이션 적합성

기존 `support-constrained-simulation-v1`은 offset0 배치의 별도 동결 버전으로 그대로 둔다. 새 plan은 `arrival-extension-exploratory-simulation-plan-v1`이고 독립 평가 공개 후 만드는 적합도·민감도 계획이다. 현재 자료 재현은 독립 검증이 아니다.

### 직접 모델링 가능한 구성요소

- 예정·실제 도착, 도착 지연과 queue entry를 단일 monotonic clock에서 복원한다.
- 비선점 잔여시간은 urgent 예정 도착 때 실행 중인 요청의 `worker_release−arrival`로 관측 trace에서 계산한다.
- 서비스는 `execution_start→worker_release` lane 점유로 정의하고 urgent completion은 output-ready, normal completion은 persist-complete로 분리한다.
- 정책 계산비용은 dispatch 전 비용으로 응답 경계에 유지한다. worker는 release 뒤에만 가용해진다.
- 반대 lane의 실행 구간 교집합으로 관측 overlap을 계산한다.
- 종단간 `response_ns`는 queue wait를 포함하므로 서비스시간으로 사용하지 않는다.

현재 평가의 service cell은 classification/CPU 63건, detection/CPU 120건, detection/GPU 15건이다. classification/GPU는0건이며 detection/GPU 15건은 모두 overlap 상태이고 조건부 정책이 선택한 표본이다. 따라서 task/backend 중앙값 기술과 정확 trace replay는 가능하지만, overlap의 인과 penalty와 미관측 배정은 식별되지 않는다.

### 탐색 계획과 가정

관측된 primary/reversed/low/queue 네 arrival template만 core로 사용한다. CPU FIFO·CPU 긴급 우선·현재 조건부 정책을 비교한다. fixed split은 primary의 같은 조건 paired 측정 전에는 지원 정책으로 넣지 않는다. task/backend 점유시간의 동일 workload·thermal/resident 상태 내 교환가능성, whole-session/block dependency 보존, overlap bin 조건부 교환가능성이 필요하다. 미관측 overlap은 `no_extra_penalty / observed_overlap_conditioned / worst_observed_within_cell`, service는 `within-cell low/central/high` 민감도로만 제시한다.

통계 단위는 whole paired block/session이다. 실행이 별도 승인되면 주 조건에 한해 6개 block의 exact ordered bootstrap `6^6=46,656`을 상한으로 한다. 보조 조건 n=1에는 interval을 만들지 않는다. 계산 상한은 base cell108, contrast별 resample46,656, 10분·2GiB이며 source hash·clock order·terminal·지원 cell·finite KPI 위반 시 중단한다. 이 값은 계산 통제 예산이며 새 성공 기준이 아니다.

### 최소 추가 근거

1. primary workload의 고정 CPU/GPU 분리와 세 기존 정책을 같은 block으로 측정한다.
2. 같은 요청을 overlap 유무만 통제한 paired cell로 간섭을 식별한다.
3. 역할반전/fixed split을 계속 다루려면 classification/GPU arrival workload cell을 확보한다.
4. simulator 정책 순위·paired 효과 검증에는 이번 평가와 다른 untouched workload/session이 필요하다.
5. 다기기 일반화 주장을 유지할 때만 추가 Android 기기의 무재튜닝 축소 평가가 필요하다.

## 재생성 명령

```powershell
& 'C:\Users\LG\anaconda3\python.exe' -B -m tools.d1_arrival_analysis --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_plan_v1_proposal\evaluation_plan.json' --results 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_run_v1' --output 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_reproduction_new'
& 'C:\Users\LG\anaconda3\python.exe' -B -m tools.d1_arrival_post_analysis --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_plan_v1_proposal\evaluation_plan.json' --results 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_run_v1' --raw-inventory 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_analysis_v2\raw_inventory.json' --reference-analysis 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_analysis_v2' --output 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_post_analysis_new'
& 'C:\Users\LG\anaconda3\python.exe' -B -m tools.d1_arrival_simulation_plan generate --audit 'C:\Users\LG\Documents\D1Check_Arrival_Extension\independent_evaluation_post_analysis_new\audit.json' --output 'C:\Users\LG\Documents\D1Check_Arrival_Extension\arrival_extension_simulation_plan_new'
& 'C:\Users\LG\anaconda3\python.exe' -B -m tools.d1_arrival_simulation_plan dry-run --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\arrival_extension_simulation_plan_new\simulation_plan.json'
```

이 명령은 새 출력 root만 허용한다. 본 시뮬레이션 실행 명령은 구현하거나 제시하지 않는다.
