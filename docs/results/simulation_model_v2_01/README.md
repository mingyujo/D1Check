# 새 시뮬레이션 모형 v2 — 구현·실측 비교 결과

2026-10-10. **별도 v2 구현과 예정8자료 확보는 완료했다. 기본 모형 교체는 보류한다.** 회복 탐침 확인2에서는 AP/J 오차가 줄었지만 예정 도착부터의 CPU/PAR 확인에서는 비용 예측이 악화했다. 개발동결 후 확인에 맞춰 다시 보정하지 않았다.

[표·그림](run_v1/index.html) · [동결 모형](run_v1/model.json) · [전체 근거/잔차](run_v1/summary.json) · [전체8자료](run_v1/sessions.csv) · [조건부 비용](run_v1/conditional_scores.csv) · [종단간 예측](run_v1/arrival_scores.csv) · [회복 탐침](run_v1/recovery.csv)

## 모형과 데이터 역할

- 실제5구간 dispatch→execution→output→persist→worker release→lane available를 하나의 순서 벡터로 재생한다. CPU/GPU 소유권은 lane available까지 유지하며 최대2건, 분류GPU＋탐지CPU 조합을 지원한다. CPU/PAR/EFT의 mean 또는 개발세션 순서 재생이다. 실패 확률/미측정 조합/동적 thermal→service는 미지원이다.
- 서비스 시간은 기존 개발 요청 벡터와 기존 CPU/PAR 판단 D→A 중앙값1.563ms다. 신규 PPO의 기기 비용으로 쓰지 않는다. AP/증분 전력은 새 회복 개발4자료로만 추정했다. 초기 AP/전력은 해당 세션의 도착 전 관측이고, 미래 AP/전력은 평가 정답에만 썼다.
- AP 빠른 감쇠β0.0459325203와 느린τ1920초는 고정·상속값이다. 시간상수의 물리적 유일 식별이나 잔열의 완전 관측은 아니다. 과거 점유 가열을 초기 관측에서 먼저 빼며 기록 이전 slow 상태0을 가정한다.
- 개발4의 4LOSO＋최종동결1 뒤 회복A/B2와 CPU/PAR96 각1을 확인했다. 동결 SHA `df6fc49a4f6b203f551534044cd630e47784979f8e7884452ce93881b5a5cd52`를 모든 확인에서 유지했다. 새 확인으로 재적합0, 기본/RL/strict 전환0, `experiment_ready=false`다.

## A — 실제 일정에 조건부인 비용

회복 확인2의 세션별 오차 평균이다. AP는 작업/냉각 관측 경로, J120은 공통0..120초, J등록은0..533초다. 관측 창과 분모가 다른 값은 같은 성능 지표로 합치지 않는다.

| 지표 | 기존 | 동결 v2 |
|---|---:|---:|
| AP MAE | 0.675653°C | 0.204184°C |
| 120초 에너지 절대오차 | 18.199165J | 5.317617J |
| 등록533초 에너지 절대오차 | 54.842244J | 29.819465J |

잔차는 남아 있다. 회복A의 v2 최대 AP 오차1.038614°C, J등록−27.959932J; 회복B는0.686817°C/−31.678999J다. 감소를 정확도 PASS/물리 법칙 인증으로 해석하지 않는다. 개발4LOSO 평균은 AP0.678573→0.185029°C/J120절대12.774303→0.908769J로 독립 확인 수치와 구분한다.

혼합 요청의 실제 일정 조건부 A도 악화했다. CPU AP MAE0.231821→0.286843°C/J120절대12.335317→14.531619J, PAR0.374422→0.384757°C/3.317897→6.703504J다.

## B — 예정 도착부터 일정·응답·비용 예측

각 정책96개(분류 긴급48/탐지 일반48), 교대350ms 도착, 기한1.5/6초다. 관측은 CPU/PAR 모두 완료96/96, 기한 내96/96이며 실패/거절/만료/미완료0이다. 성공률 분모는 전체 예정 도착, P95는 성공 완료 요청만이다. 미완료 요청을 P95에 포함하지 않는 horizon 경계 검사를 추가했다.

| 조건/우선순위 | 실측 P95 | 기존 예측 | v2 예측 |
|---|---:|---:|---:|
| CPU 긴급 | 764.478ms | 750.254ms | 754.779ms |
| CPU 일반 | 5041.548ms | 5090.436ms | 5119.652ms |
| PAR 긴급 | 296.842ms | 286.608ms | 268.350ms |
| PAR 일반 | 645.870ms | 618.791ms | 618.705ms |

| 예정 도착 비용 오차 | 기존 | v2 |
|---|---:|---:|
| CPU AP MAE | 0.230723°C | 0.289081°C |
| CPU J120 절대오차 | 12.545895J | 14.666241J |
| PAR AP MAE | 0.385875°C | 0.390690°C |
| PAR J120 절대오차 | 3.844724J | 6.831658J |

CPU 긴급 P95 오차는 감소했지만 일반 P95와 PAR P95는 개선되지 않았다. 비용도 두 조건 모두 악화했다. 따라서 이번 비교는 **전반적인 모형 우수성이나 정책 우월성을 입증하지 못했다.** PAR은 사용자 이동 후에 측정했고 초기 AP anchor CPU26.0/PAR27.3°C, 시작 전력0.977778/1.030535W였다. 큰 실측 응답 차이가 존재해도 시간·초기 상태가 다른 각1회를 동시 paired 정책 효과나 통계적 확증으로 쓰지 않는다.

## 감속·회복과 한계

새 회복 확인A/B에서 CPU 분류의 부하 전 대비 변화는 직후＋0.031/−0.383%, 약240초 뒤＋0.340/＋0.485%다. 분류GPU는 직후＋0.956/−9.201%, 약240초 뒤＋2.963/＋1.736%였다. 모든 모델이 부하 후 느려지고 냉각 뒤 빨라지는 공통 양상을 확인하지 못했다. 순서·캐시·탐침 부하와 실제 간격은 회복CSV에 공개했고 온도 인과식은 만들지 않았다.

J는 기기의 current 센서를 mA로 해석한 같은 관측 계약의 적분이다. 외부 전력계 절대 교정·배경부하의 정지성·S26/NPU/다른 초기 열 상태 일반화는 확인하지 않았다. 모델별 정확도/mAP 개선 실험이 아니라 고정 모델/입력 출력 동등성과 일정/비용의 검증이다.

## 원 실패·사용자 중단·한도

원 첫 개발자료는 계측 종료/cleanup 이후21.823ms에 journal-closed sampler 실패가 났다. 원 실패를 보존한 채 전량 검사를 통과한 계측 구간만 재사용했으며 전체 cohort의 앱 lifecycle PASS는 false다. 이후 앱 sampler 종료확인 수정은 별도 APK로 검증했다. 각 자료의 APK와 failure는 sessionsCSV에 기록했다.

별도 PC `adb_commands` 설정 오류1과 사용자 이동 시 PAR 준비 중단1도 원 receipt/prefix로 보존한다. 중단/실패를 완료 요청으로 쓰지 않는다. 새 ID로만 이어가서 물리시도는 원8→9→10, runtime 생성 한도는 원32→최대40, APK 설치는 원1→2로 명시 증가했다. 동일 APK 점검만의 최종 재개에서는 설치0이다.

완료8자료의 명시추론5464, 실패/중단 불명 상한을 더한5672≤원7768이다. 기록된 캠페인ADB10612＋이번 재연결 조사2≤원29448이며 최초16670초 clock을 유지해21:29 KST에 측정을 마쳤다. 이전 계획/registry를 재실행하거나 clock을 조용히 다시 시작하지 않았다. `summary.json`의 experiment_ledger와 실행 계획/원 터미널 hash를 따른다.

## 재현과 판정

[모형 설명](../../SIMULATION_MODEL_V2.md) · [사전 계획](../../SIMULATION_MODEL_V2_PLAN_20261010.md) · [재개 명세](../../SIMULATION_MODEL_V2_RESUME_20261010.md) · [코드](../../../tools/d1_simulation_model_v2.py)

```powershell
python -B -m unittest tools.test_d1_simulation_model_v2 tools.test_d1_simulation_model_v2_campaign tools.test_d1_simulation_model_v2_report
python -B -m tools.d1_simulation_model_v2_demo --model docs/results/simulation_model_v2_01/run_v1/model.json --output output/model_v2_demo_new --mode mean
python -B -m tools.d1_simulation_model_v2_demo --model docs/results/simulation_model_v2_01/run_v1/model.json --output output/model_v2_replay_new --mode session_replay --seed 13
```

19개 의미 경계 검사 PASS, 최종 두 예정 도착 forecast는 완료-P95 경계 수정 전후 원장/응답/AP/J가 exact 동일하다. 재생 mean은 [시연](run_v1/demo/index.html)이며 실제 기기 실행 결과와 구분한다. APK source/서명/출력 검증은 실행 receipt, 앞선 JVM/격리 빌드는 `output/model_v2_20261010_v1`의 원 검증 기록에 있으며 이번 호스트 변경으로 전체 빌드를 반복하지 않았다.

**권장:** v2를 회복 일정 분석·모형 민감도 확인용 별도 후보로 사용한다. 혼합 요청의 비용 오차와 처리시간의 열 의존성이 해결되지 않았으므로 기존 기본 모형을 보존한다. 필요한 후속은 현재 큐 정책·SLA·기한을 고정한 별도 반복 확인/잔차 원인 분석이며 이번에 추가 측정/보정/기본 채택을 자동 실행하지 않는다.
