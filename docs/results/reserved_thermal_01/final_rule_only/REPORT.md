# 기한 예약·열 분산 스케줄링 최종 비교

2026-10-08 KST · RESERVED-THERMAL-01 · **검토 완료, 현 후보 미채택·RL 보류**

**Triton의 강한 요청 대응 기준보다 유리한 모형 조건은 확인했지만, Band·강한EFT보다 열과 에너지를 함께 줄인다는 목표는 달성하지 못했다.** 구현·검증·새 합성192조건 비교를 완료했다. 모형의 작은 AP 차이는 실기기나 실제 제품 우월성을 입증하지 않는다. 원래 연구 목표 전체와 이 PC 캠페인의 완료를 구분한다.

## 가져온 판단 규칙과 재현 수준

| 원 시스템/버전 | 실제 실행한 판단 | 그대로 유지한 핵심 | 변경/생략 | 수준 |
|---|---|---|---|---|
| Band `8600d4960ccb6f121221f6d252da8dbef2db160b` | 기본 HEFT, reserve=false·SLO미지정 | FIFO window, worker 대기+예상 비용의 최솟값이 가장 큰 요청 우선, 바쁜 최선worker yield, 완료 후 EMA .1 | subgraph→전체5단계 요청, CPU/GPU 두worker·허용CG_DC, 전송/연결/DSP/NPU/LSF early-drop 생략 | B: 실행 단위·자원을 바꾼 제한적 재현 |
| Triton core `3af839d613da6995051f9bcfab00efe2eac87d4c` | rate_limiter의 submit/stage/allocation/release | 작업별 FIFO, 완료횟수×priority, 최소 scaled priority, 실제 자원 반환 | 서버 instance→분류GPU/탐지CPU 고정instance, global token1/2, batching/cache/선점/네트워크 생략 | 조건식 A, 실행 대응 B |
| 우리 R2 | 완료 cap·signed J credit·현재 큐 전체 후속계획, AP 우선 | 기존 기한/예측/WAIT·지원·계수, 실패 시 내부EFT, 실제lane반환 | 수치 이동량≤1ns, 초과 후보만 탈락; 진단 추가 | 동일 모형의 새 연구 후보 |

Triton은 제한해제와 capacity1/2×equal/class-weight의5설정을 모두 공개했다. class-weight는 분류1/탐지2의 실험 설정이고 기본값은둘다1이다. 좋은 설정만 골라 비교하지 않는다. 동시2/제한해제 결과가 같은 경우도 별도행에 남겼다. Band는 deadline early-drop을 제거한 LSF가 아니라 원 HEFT 무SLO 경로를 쓴다. 원시 API만으로 새 외부 스케줄러를 만들어 넣지 않았다.

원 코드 위치·원 URL·임계값/동점/재판단·비선점·비용갱신의 상세는 [Band/Ente 사전 대응](../../external_rules_01/mapping.md)·[Band 출처](../../external_rules_01/sources.json)·[Triton 대응](../../external_rules_02/mapping.md)·[Triton 출처](../../external_rules_02/sources.json)에서 확인할 수 있다. Band HEFT 코드는 `band/scheduler/heterogeneous_earliest_finish_time_scheduler.cc`, Triton은 `src/rate_limiter.cc/.h`다. 외부 앱/서버 전체를 실행한 비교가 아니다. Ente의 배경 시작 허가는 같은 하위EFT를 고정한 기존 별도결과를 유지하며 이번 자원 배정 성적표에는 넣지 않았다.

## 입력·실행 규모와 사전 동결

- 새 trace seed610880001–610880016 × 기존low/queue/burst/sustained × mean/short/long=192조건, 11정책×192=2,112신규환경. 정책/입력/실현비용/CRN201/초기상태/관측창/기한/완료 요구가 같다.
- low/sustained96조건이 주평가, queue/burst96은 미리 지정한 과부하 진단이다. 정책별예정12,672요청, 전체139,392논리요청을 모두 분모에 포함했다. seed는 같은 합성 생성기의 새로운 표본이고 실기기 독립 확인이 아니다.
- Band·SHARED_EFT·내부EFT·자체 기존2규칙·Triton5·수정본R2를 포함한다. 원 mixed pilot 후보는 역사비교48행에 보존했다. 내부EFT 대조 누락을 보완해 당초RL없는10정책/1,920행에서11정책/2,112행으로 명시적으로 늘렸으며 전체20,000환경 상한은 유지했다.
- 생성 전 등록자료 충돌0으로 seed를 고정했다. 실행 중 압축 이력18,770개까지 읽기 전용 확장검사해 충돌0을 확인했다. 압축 범위는 초기검사 한계를 보완한 후속검사이며 seed 변경/성능기반 선별0이다.
- 설정 조정·보상 튜닝·물리계수 fitting·기기/ADB/설치/실측0. 기존 PPO·재조합·원 checkpoint·기본/strict/experiment_ready=false를 유지한다.

## 서비스와 비용 결과

수정본 12,672/12,672완료, 긴급기한 실패0·일반기한 실패292이다. 주96조건은 10,368/10,368기한 내 완료했다. 전체 일반실패는 Band 193, SHARED_EFT 204, 강한Triton 192과 각각 비교한다. 긴급 완료 응답P95만 보고 일반 서비스 손실을 숨기지 않는다.

아래는 **수정본−기준**, 주96의 전량·서비스·비용 적격 쌍 평균이다. EPS1e−9는 부동소수점 동률 처리이며 모형오차/실용개선 한도가 아니다. AP와 J가 모두 감소해야 공동 감소로 센다.

| 기준 | 주96 서비스 유지 | AP 최고값 차이(°C) | 공통120초 J 차이 | 주96 공동 감소 |
|---|---:|---:|---:|---:|
| Triton 제한 해제 |96/96|-0.129776202|-0.790013531|96/96|
| Band 요청 대응 |96/96|-0.052367237|+0.167123232|0/96|
| 예상 완료 우선 |96/96|-0.064662216|+0.078273774|4/96|
| 내부 EFT |96/96|-0.000913120|-0.000940765|5/96|


모든 조건별 차이와 각Triton 설정은 [전체 결과](results.csv)·[짝비교1,920행](pairs.csv)·[정책성적표](policy_summary.csv)에 남겼다. 미완료 정책의 J는 공통창 부분처리 비용이며 절감 이득으로 인정하지 않는다. AP180은 전량 완료에서만 유효하며 미지원 안전한도·초과시간은null이다. 완료된 응답의P95와 전체기한 성공/실패 분모를 함께 보고했다.

## 차이가 발생한 지점

Triton 대응은 분류GPU·탐지CPU 고정instance와 자원허가/작업별FIFO를 제어한다. Band 대응은 worker대기·예상비용과largest-min 규칙으로 요청/배정을 고른다. 우리 규칙은 urgent/aging·예약·J예산·AP 점수를 함께 사용하고, 실패복귀 내부EFT는 곧 비는CPU를 기다릴 수 있다. SHARED_EFT와 동일 규칙이 아니다. 그러므로 전체 차이를 열 최적화나 rate-limit 하나에만 귀속할 수 없다.

대표 seed610880001/mean/queue·sustained는 결과 확인 전에 등록했다. [실제lane반환까지의 시간표](figures/03_대표요청_실행시간표.png)와 [전체 ledger](representative_ledger.csv)로 순서·배정·대기를 확인할 수 있다. 아래는 같은대표 trace에서 수정본−SHARED_EFT 에너지를 점유상태별로 분해한 모형회계다. 공통기저항은 같다. GPU 사용량을 줄였다고 J가 자동으로 줄어드는 것은 아니다.

| 대표조건 | 점유 상태 | 수정본−SHARED_EFT J |
|---|---|---:|
|queue|classification_CPU|+0.193114509|
|queue|classification_GPU|+0.000000000|
|queue|classification_GPU+detection_CPU|-0.541262467|
|queue|detection_CPU|+0.434641657|
|sustained|classification_CPU|+1.641473325|
|sustained|classification_GPU|-1.008807108|
|sustained|classification_GPU+detection_CPU|-2.706756456|
|sustained|detection_CPU|+2.173564921|


## 수치 수정과 RL 판정

수치R2는 겹침 길이만 보는 첫보완의1.62초 반례를 거절한다. 최초 미보정 proposal→최종 시작 이동량의합을1ns로 제한하고, 초과/미지원점유가 남으면 그후보만 탈락시키며 원fallback으로 계속한다. 원18소스·첫보완2소스·원48항목은 보존했다. 직접9검증·10엔진 회귀·수정48조건에서 전량ledger/주요지표가 원48행과 일치했다.

최종192조건에서도 중복lane/미래요청/요청누락·완료 경계·raw receipt/binding을 감사했다. 수치보정456회(계획 함수호출), 최대 0.458385ns, 수치 후보 거절0회다. 실제로 거절된 경우가 없더라도 직접 경계 검증은 유지한다.

scoring callback 53,209 중 서로 다른 실제 반환행동이 있는 경우1,112, 첫 요청/backend가 다른 경우0다. 계획 수와 행동 수를 구분했다. 관측cap초과1739요청·최종J예산초과94/192조건을 숨기지 않는다. 원 cap/J식이 미래 도착/문맥 오차까지 전역 보장하지 않는다.

pilot의 적격 대안은 대체로 같은배정의대기차이였고 Band/EFT 대비 공동개선 근거가 부족해 **RL 본학습0·학습 세부 계약 미동결·현 후보 미채택**으로 판정했다. 학습량 부족, 수렴 완료, RL 일반의 실패 또는 개선 불가능을 입증한 결과가 아니다. 최종시험을 본 뒤 재선택하거나 추가학습으로 성공결과를 찾지 않는다. 남은 예산이 있다는 이유로 새 설계/seed/학습을 자동 시작하지 않는다.

## 실측 근거와 가정·미완료 범위

지원은A24 분류CPU/GPU·탐지CPU·허용CG_DC 병행이다. 기기별계수를 혼합하지 않는다. 과거 실측에서 얻은서비스/전력/상태/AP계수를 쓰지만, 합성도착·평균/짧은/긴문맥 전이·임의 일정 적용은 가정 기반 탐색이다. 문맥3개는 신뢰구간/WCET가 아니다. J0–120초, AP35–180초·1초격자+경계의동일모형값이며 연속물리최고 보장도 아니다.

**최고 표면온도는 이번 모형에서 계산 불가다.** AP를 표면온도·기기 열안전·배터리수명·스로틀링 개선으로 바꾸지 않는다. S26/NPU/탐지GPU·DVFS·선점·미측정전송/메모리·폰에서의판단비용·독립폰정책효과는미검증이다. 미측정 항목을0으로 채우거나 다른기기 값으로 대체하지 않았다.

기존PC모형의 차등판단/기록/dispatch overhead0 가정은 유지한다. 실제host callback 총 513.768초·최대 198.871ms는PC벽시계이며 폰의에너지/응답추가비용을 대신하지 않는다. 추가판단비용이 실기기에서는 이득을 없앨 수 있다. 과거 모형확인에서 정책 차이보다 큰 J/AP오차가 남았다는 [근거](../../online_policy_study_01/policy_resolution_pc_v1/README.md)·[후속오차 판독](../../../MODEL_ROBUST_GAIN_20261007.md)을 유지한다. 이번 차이에 통계적/실용적 확실성을 부여하지 않는다.

현재 목표의 ‘Band와Triton보다기한/전량을 유지하며 열·에너지 동시감소’ 및 실제폰확인은 미충족/미검증이다. 이는숨은미완료구현이 아니라 공개한실험판정/근거한계다. PC 구현·검증·비교·시각화·문서화는완료했고, 이후 새구조/실측은 이실패증거를 유지한 별도설계가 필요하다. 현기본정책을 교체하지 않는다.

## 소비·검증·공유

이번 재개 추가2,170환경(수치회귀10+수정pilot48+최종2,112), 누적2,241/20,000환경(성공2,238/이전실패3). 단계2실제129/512·최종evaluation2,112, 본학습0/상한6,144·이작업기기0. 잔여전체17,759/단계2 383이며 예산초기화0이다. 각환경시작은같은장부에서실행전에차감했고 각완료item을입력/정책/소스와receiptSHA에결합했다. 완료캐시3경계 확인은추가환경0이다.

[오프라인 화면](index.html) · [최종 검증](verification.json) · [실행 동결](registration.json) · [전체 입력](inputs.json) · [진단](diagnostics.csv) · [48조건 보완 보고서](../numeric_r2/REPORT.md). 최종검증시HEAD/미커밋·명령/시점/소스SHA는verification에 기록했다. 원본대용량·모델binary·키·개인경로는새공유물에포함하지 않는다. Git에는이번소스/계약/CSV/그림/문서만반영하고실제원격HEAD는마지막보고에서확인한다. 사용자HTML/PDF/다른worktree/다른작업 변경은보존했다.

PPT용그림: [완료·응답](figures/01_전체요청_완료와응답.png), [열·에너지차이](figures/02_기준별_열에너지차이.png), [시간표](figures/03_대표요청_실행시간표.png), [AP경로](figures/04_대표조건_AP경로.png), [192조건지도](figures/05_전체192조건_결과지도.png). SVG도같은폴더에있다.

## 재현 명령

공유Git만있는경우 읽기전용 검증은원실행폴더없이가능하며 엔진0이다.

```powershell
python -B -m tools.d1_reserved_thermal_artifact_check
```

원로컬장부/완료item이있는경우의바인딩검사/분석명령이다. `run`은완료item이면추가환경0으로receipt를확인하고, 없으면원남은예산/시간/owner검사를통과할때만실행한다. 원상태가없으면예산을조용히새로만들지않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_reserved_thermal_numeric_r2 -v
python -B -m tools.d1_reserved_thermal_final_study prepare
python -B -m tools.d1_reserved_thermal_final_study run
python -B -m tools.d1_reserved_thermal_final_analysis
python -B -m tools.d1_reserved_dashboard_check docs/results/reserved_thermal_01/final_rule_only/index.html 2138 195
```

일반수치/파서/화면문제를해결한이력은수정보고서에보존했다. 최종후설정선정/재학습/기기검증은수행하지않았다.
