# 전체 요청 방법론 비교와 동결식의 에너지·AP 상충

## 최고 AP와 부담 면적을 함께 제한한 offline 참고값 — 2026-10-06

[새 4사례 판독](joint_calendar_readout_v2/index.html), [같은 입력·응답·부호 있는 면적 CSV](joint_calendar_readout_v2/comparisons.csv). 앞선 최고 AP만 제한한 8회 최적화와 별도 실행이다. 기존 두 queue 입력/seed223001·223002/48요청/mean 처리시간/초기값을 유지하고, **EFT의 최고 AP와 양의 AP 부담 면적을 동시에 넘지 않으면서 J를 최소화**하도록 기존 격자 문제에 면적 epigraph만 더했다. 원래 planner·이벤트 엔진·물리 계수를 수정하지 않았다. 시작 HEAD `fe70b1f6abd188bba65a2eff9fee4196935c3c1f`, 미커밋 구현의 byte를 실행 전에 등록했다.

| 입력·seed | 원 5단계 재생의 기한 | ΔJ, 0–120초 | Δ최고 AP | Δ양의 AP 면적, 35–180초 | Δ긴급 P95 | Δ일반 평균 |
|---|---:|---:|---:|---:|---:|---:|
| queue50·223001 | null | null | null | null | null | null |
| queue50·223002 | null | null | null | null | null | null |
| queue75·223001 | 48/48 | −0.052468J | −0.049803°C | −0.886985°C·s | +686.803ms | +2398.596ms |
| queue75·223002 | 48/48 | −0.013042J | −0.045679°C | −1.164743°C·s | +776.264ms | +2981.247ms |

**현재식에서 공동 비악화하는 미래 일정은 2개 존재한다. 온라인 정책으로 확보한 것은 아니다.** 미래 도착과 mean 처리시간을 알고 계획한 참고 일정이며, 긴급 1.5초/일반 6초 기한 안에서 응답을 늦춰 얻은 작은 J 이득이다. 새 독립 입력이나 실기기 확인이 아니고, 모든 온도 지표 또는 모든 시점이 개선된다는 뜻도 아니다. queue75·223001의 부호 있는 AP 차이 적분은 **+0.617532°C·s**, 추가 가열입력 적분은 **+0.033200°C**다. queue75·223002는 각각 −0.140978°C·s와 +0.002494°C다. 유효 유휴 기준 아래의 초기 AP 구간 및 열 입력의 시점 때문에 양의 면적과 부호 있는 면적은 다르다. 이 산술을 임의 물리적 냉각량으로 해석하지 않는다.

두 queue50의 null은 120초 solver 제한 안에서 정수해를 확보하지 못했다는 뜻이다. **제약 불가능이라는 증명이 아니다.** 별도 결정적 CPU-only/도착한 요청의 절대 기한 우선/동일20ms 격자 일정이 네 입력 모두의 기한·최고 AP·면적 제약을 만족함을 구성적으로 확인했다. 이 확인은 solver 재시작/입력 선정/새 계수 fitting이 아니다. CPU witness의 ΔJ는 각각 +0.086494/+0.242688/+0.161923/+0.416662J로, 에너지 개선 정책이 아니다. [전체 증거와 ledger](joint_calendar_witness_v1/result.json), [판독 전 규칙](joint_calendar_witness_v1/registered_before_analysis.json).

native solve는 등록대로 **4회·각120초·20ms**이며 전체 기록 시간은 **543.515초**다. 120초는 native solver의 제한으로 모델 행렬 생성·회수·판독 시간을 포함한 전체 시간 제한이 아니다. 성공한 두 해의 gap은 0.003051/0.005617, 둘 다 시간제한 상태로 최적성 미입증이다. 추가/finer-grid/변경 제약 재시도0. 새 원 엔진 재생은 최적화해2×48=96요청과 CPU witness4×48=192요청, 합계 **288 PC 요청**이다. 이전 전체 배치는 재실행하지 않았다. [실행 전 등록·해시](joint_calendar_v1/registered_before_run.json), [종료 요약](joint_calendar_v1/summary.json).

현재 모형의 controller 차등비용0 가정에서 얻은 0.013–0.052J는 실기기 제어·기록·지연 영향이나 예측 오차로 사라질 수 있다. 같은 일정이라는 조건에서 미모형화된 차등비용이 각 이득에 도달하면 J 이득이0이 된다. **이 숫자는 실기기 허용오차·비열등성 기준·미래 보장값이 아니다.** mean 외 처리시간, 인과적 온라인 구현, 독립 예측 및 정책 차이 식별은 별도 미확인이다. 기본 정책/동결/strict/`experiment_ready=false` 유지. 현재 추천은 강한 EFT 대조와 기한 우선·목적별 Pareto 판독이며, 이 offline 계획을 배포 정책으로 채택하지 않는다.

```powershell
# 저장 결과 판독만: 최적화/추가 이벤트 재생/기기 명령 없음
python -B -m tools.d1_joint_calendar_report --output output/joint_calendar_readout
python -B -m unittest tools.test_d1_joint_calendar_readout -v
# 재현 가능한 신규 PC 탐색 명령. 이미 종료한 폴더에는 실행하지 않는다.
python -B -m tools.d1_joint_calendar_study --output output/joint_calendar_reference
python -B -m tools.d1_joint_calendar_witness --output output/joint_calendar_cpu_witness
```

새 경계 검증은 adapter6/실행 분모·예외3/증거 판독·실제 CLI8, 총17건이다. 처음 adapter 검증의 함수 identity assertion은 class attribute를 instance에서 읽어 bound method로 만든 테스트 코드 오류였으며 class에서 읽도록 정정했다. assertion을 삭제하지 않았고 source/global 불변 검사가 통과했다. 판독v1은 local 보존하고 v2에 witness의 실제 ledger/격자 면적 재계산 및 공동 개선 표지/분모 검증을 보강했다. 수치와 그림은 동일하다. CSV·모형 경로 그림을 검수했으며 새 실측 그림이 아니다. [대상·명령·검증](joint_calendar_verification.json). 기기 명령/ADB/설치/실측/APK/새 기기 계획/claim **0**.


## 새로운 후보 대신 공동 절감의 필요조건 계산 — 2026-10-06

[동결식의 낙관적 상한](joint_bound_v2/index.html), [24개 기준 사례](joint_bound_v2/bounds.csv). 앞선 무한시간 부호 있는 온도 적분 항등식만으로는 유한창의 최고AP·양의 AP면적을 판단할 수 없었다. 이번에는 기존 전체48요청·같은시간문맥·EFT 대조를 유지한 채, **기한을 모두 지키고 최고AP와 AP면적을 EFT보다 늘리지 않는 경우의 에너지 이득 상한**을 추가 계산했다. 후보 생성/튜닝/새 시뮬레이션/실측은0이며 새 전력·열 계수가 없다.

| 저장 입력 | 적격 EFT 사례 | 각 사례의 낙관적 J 이득 상한 범위 |
|---|---:|---:|
| low | 6 | 0.225153–0.356781J |
| queue50 | 6 | 0.120068–0.178390J |
| queue75 | 6 | 0.225632–0.258417J |
| burst50 | 0/6 | null — 기준부터 전기한 미충족 |

2seed×3문맥은 독립 기기 세션이 아니다. 표는 **이 현재식/입력/초기값/고정 처리문맥**에서의 숫자이며 임의 부하나 기기 성능의 한계가 아니다. 양의 상한은 그 이득을 달성할 일정이 있다는 증명이 아니다. 도착·lane packing·순간 전력 상한을 완화했으므로 실현 가능한 이득은 이보다 작을 수 있다. 이번 상한으로 공동 절감이 불가능하다고 증명하지도 않았다. 따라서 “큰 실제 공동 절감이 확인됐다”거나 “모든 방법이 불가능하다” 둘 다 결론으로 쓰지 않는다.

### 사용한 식과 완화

분류CPU/GPU lane 길이를 C/G, 탐지CPU를 D, 분류GPU 수를 n, CG_DC 겹침을 x라 둔다. 현재 동결식에서 `J=J_CPU+n(wG·G−wC·C)−x(wG+wD−wGD)`이고, 적분 열입력은 `H=H_CPU+n(uG·G−uC·C)+x(uGD−uG−uD)`다. u는 AP기울기에서 resident_idle 기울기를 뺀 값이다. 두 겹침 계수의 부호는 현재파일에서검사하며 다른계수/구조를대입하지않는다.

고정 `g=0`, 양의 beta/k에서 AP의 부하 기여는 `k∫exp(−beta(t−s))u(s)ds`다. 동일한 준비이력으로 계산한 무부하 경로는 보존한다. 35–180초 1초질의 사이의 양의 입력을 그 구간 시작 직후의 순간 입력으로 옮기면 모든 미래질의의 기여가 작아진다. 이 자유로운 입력을 허용한 LP에서 **같은EFT 최고AP 및 `Σw·max(AP−유효유휴기준,0)` 한도** 아래 가능한 H의 상한을 구했다. 순간 입력은 실행 가능한 작업도 실제 열 측정도 아니다.

응답 마감은 긴급O/일반P이므로 마지막lane상한은 각 요청의 `도착+기한+O/P→L 잔여`로 산정했다. 모든 요청이 마지막도착부터같은6초를 갖는다고 복사하지 않는다. GPU 수를0..분류전체의 정수로 두고, x≤GPU 점유·탐지CPU 점유·열입력여유를 함께 적용해 J의 하한/이득상한을 산출했다. lane배치·도착별자원가용성을풀었기때문에 이것은 필요조건이고 충분조건이아니다.

LP success만 믿지 않고 dual의 비음수·표본별커버리지 제약을 보수적으로 복원했다. 1ns endpoint 반올림과 `1e−6`의 수치 여유를 포함하며 이는 **측정오차 허용폭/정확도 기준이 아니다**. 현재 `g≠0` 또는 시간벡터가바뀌면 거절한다. 기존출력·동결계수·strict·`experiment_ready=false`불변. [분석 전 규칙·해시](joint_bound_v2/registered_before_analysis.json), [신규9검증](joint_bound_verification.json).

```powershell
python -B -m tools.d1_method_joint_bound --output output/method_joint_bound
python -B -m unittest tools.test_d1_method_joint_bound -v
```

기한실패6건의 분모/null을 보존하고, 실제EFT의 적분입력이 완화상한 안에 들어가는지·dual/가상 양의입력·상한추가의 단조성·시간벡터변경·solver미완료·원해시보존을 검증했다. 이번계산으로 새 정확도 기준을 만들지 않는다. 큐에서모형상최대0.12–0.18J의 공동이득이 있어도실제controller차등비용/예측오차/독립변동보다큰지는미확인이다. 다른등록기기확인의오차를이표의보편오차한도로복사하지않는다.

**현재 권고는 강한EFT 대조·기한 우선·목적별상충 판독을 사용하는 것**이다. 에너지와 AP를 함께 줄인 새정책으로 ATC/병목/beam을 채택하지 않는다. 작은양의상한을찾았다는이유로실측/후보를자동추가하지않으며, 현재DG/CC_DG 비용과실기기controller·독립정확도공백은그대로남는다.

## 시뮬레이터 한 진입점에서 판독 — 2026-10-06

[통합 화면](workbench_v3/index.html)에서 기한·모형 계수 매핑·독립 예측 확인·정책 차이 식별을 따로 표시한다. 세 등록block/28묶음/168사례의 저장 ledger만 읽었다. 원래48요청과 같은 seed 대조를 유지하고 dispatch→실제 lane_available 구간, 같은 lane 중복 점유, 전체0–180초 상태 경계를 검사했다. 현재3cell/CG_DC의 계수 존재는 새 일정의 전용 가능성이나 strict 정확도 검증이 아니다. 미측정 DG 비용을 대신 채우지 않았다.

```powershell
python -B -m tools.d1_simulator method-readout --output output/method_readout
python -B -m unittest tools.test_d1_method_workbench -v
```

이 경로는 출력 위치만 받는다. 새로운 seed·정책·초기 AP·제약값을 넘기면 시작 전에 거절하며 기존 출력도 덮어쓰지 않는다. `method_readout_resources.json`은 원 비교6파일과 동결 모형·초기값2파일의 byte 해시를 고정한다. 저장 일정의 제어 비용0 가정과 현재 열→처리시간 미지원을 표시하고, 계측 부재/예측 오차한도/실제 승자는 null로 유지한다. 단순 Pareto 표시는 온라인 제어기나 채택한 정책이 아니다.

신규8검증과 기존 arrival/episode·실제 CLI 대표 회귀3건 통과. 가짜ADB trap 및 새 event simulation을 금지한 검증으로 기기 호출·새 시뮬레이션이 없음을 확인했다. 실제 CLI 산출물과 CSV/그림을 검수했다. [대상·명령·원본 보존](method_workbench_verification.json). 기존 기본/strict/동결값·`experiment_ready=false`·사용자 자료/다른worktree를 유지한다.

지금 바로 가능한 실험은 **동결식과 시간 전용 가정을 명시한, 기한 우선의 목적별 상충 평가**다. ATC/CPU병목/호환 backfill이 실제 기기의 열·에너지를 함께 줄이는 방법으로 확인됐다는 뜻은 아니다. 새 정책을 계속 추가하기보다 강한EFT 대조에서 어느 목적이 개선되고 무엇을 손해 보는지 먼저 읽는다.

## 절감을 지워 버릴 수 있는 비용까지 판독 — 2026-10-06

[손익분기·상충 화면](tradeoff_budget_v2/index.html), [28개 묶음](tradeoff_budget_v2/groups.csv), [168개 동일입력 사례](tradeoff_budget_v2/cases.csv). 새 시뮬레이션이나 모형 fitting 없이 세 등록block의 새seed 결과만 재사용했다. 각block/입력의2seed×3전체5단계문맥을 유지하고, 다른block의seed를 같은 대조로 합치지 않았다.

동일한 모형 일정/공통창이라는 조건에서 `실제 차등J = 모형 차등J + 미모형화된 차등비용`이다. 따라서 모형상 절감을 남기는 조건은 `미모형화된 차등비용 < −모형 차등J`다. 등호에서는 이득이0이므로 엄격한 절감이 아니다. 이 식은 새로운 물리 계수나 실기기 오차모형을 추가한 것이 아니라, 계산에서 빠진 비용에 대한 **조건부 산술 질문**이다. 제어 때문에 일정·간섭·AP가 바뀌거나 센서 단위/계측이 달라지는 경우는 별도 미확인으로 남긴다.

| 전체48요청 조건·후보 | 저장6사례 모두의 모형상 J 이득을 남길 차등비용 | EFT 대비 최대 AP 증가 | 최대 AP면적 증가 | 최소 당시 응답 기한잔여 |
|---|---:|---:|---:|---:|
| queue50·ATC | 0.177365J 미만 | 0.283401°C | 7.473288°C·s | 632.055ms |
| queue50·CPU병목 | 0.430421J 미만 | 0.291083°C | 9.852405°C·s | 663.191ms |
| queue75·CPU병목 | 0.414962J 미만 | 0.261954°C | 8.158515°C·s | 775.951ms |

이것은 앞으로의 입력에 대한 절감 보장·신뢰구간·안전상한·허용오차가 아니다. 최대 AP/면적 증가는 사용자가 받아들여야 한다는 결정도 아니다. **J의 이득과 열 부담 증가를 같이 남기는 사후 모형 결과**이며 실제 정책 우열은 미판정이다. 표의 최소 기한잔여도 “그만큼 제어 지연을 추가해도 된다”는 보장이 아니다. 대기·lane 경합·다음 요청의 연쇄 지연이 달라질 수 있어 `safe_global_extra_delay_ms=null`이다.

CPU병목의queue50은 저장된각사례에서252–282번 판단했고, PC callback 합계는0.071–0.105초다. 이 값을 휴대폰 실행시간/J로 환산하지 않는다. 새판독에서 발견한 **EFT callback 계측 부재**도 명시했다. 원 runner는 EFT controller에 callback timer를 붙이지 않아 저장 `decision_host_total_s=0`이 나왔다. 원본0은 보존하고 새CSV의 EFT 계측값은null로 표시한다. EFT가 실제로 무비용이라는 근거나, 두 정책의 실기기 제어 비용 차이는 없다. 정책 일정/동결 계수를 바꾼 수정이 아니다.

저부하와queue75 ATC의EFT동일은 양의절감예산으로 승격하지 않는다. burst는본후보와기준의전기한충족을못하므로 낮은J가있어도 적격절감예산은null이다. beam의불완전/동일결과도 그대로 유지한다. 센서오차·독립세션변동·실기기controllerJ의미확인값을0으로채우지않았다.

```powershell
# 기존압축ledger 판독만 수행; 새 실행/기기명령 없음
python -m tools.d1_method_tradeoff_budget --output output/method_tradeoff_readout
python -m unittest tools.test_d1_method_tradeoff_budget -v
```

신규8검증: 같은입력/전체분모/우선순위별response·실제lane반환,평균이아닌최소같은사례J여유,기한실패/결측/null/EFT동일차단,기존동결hash불변. event simulate를금지한상태에서도실제저장자료판독·CSV/그림생성이통과했다. 첫그림v1의동일원점label겹침은local보존하고v2에서묶음표시만고쳤으며수치는바꾸지않았다. 기기명령·실측·APK·새계획·claim0,기본·strict·`experiment_ready=false`불변. [대상해시·명령·시점](tradeoff_budget_verification.json).

2026-10-06 PC 작업. 시작 HEAD `42890f417871c262685bce0e6bb6a85d908d1372`, 미커밋 구현에서 각 실행 전에 입력·소스·계수 해시를 등록했다. [화면](index.html), [대표 일정·모형 경로](comparison.png).

## 지금 사용할 판독 방법

**기한 제약을 먼저 검사하고, J·최고AP·AP면적·응답의 상충을 Pareto 집합으로 남기는 방법을 권고한다.** 여러 비용을 임의 가중치로 합쳐 새 승자를 만들지 않는다. [저장 결과 판독 화면](decision_readout_v2/index.html)과 [J/AP 동시 비악화 질문의 예시](decision_nonworsening_v2/index.html)를 구현했다. 새로운 정책이나 새 계산 결과가 아니라, 앞서 완료한 전체48요청 결과를 그대로 읽는 CLI다. 현재 사용할 강한 PC 기준은 EFT이고, ATC/CPU 병목은 목적별 상충을 드러내는 비교 후보다.

각 block/입력에서2seed×3전체5단계 문맥,288도착을 모두 검사한다. 지표별 Δ는 **각 사례의 동일 seed EFT 대비 차이의 최댓값**이다. 이는 미래 오차한도·WCET가 아니다. 부모3block은 서로 다른seed이므로 섞어서정책을순위매기지않는다. `equivalent_to_reference=true`는 계산이EFT와같다는뜻이며개선이아니다. J/AP를낮추면서응답을늘리는후보와응답기한을어기는후보를구분한다. 소수점 `1e-8`은 산술 판독오차이며 연구 허용오차가 아니다.

상대 제약은 사용자가 직접 지정한 PC 질문으로만 사용한다. `relative_nonworsening_example.json`의0은 “각 저장 사례에서EFT보다J/최고AP/AP면적이커지지않는가”를 읽는 **예시 질문**이지새안전기준·정확도합격선·배포정책이아니다. ATC/병목block의queue50에서는EFT만통과하고, 즉시beam은일부조건에서EFT와동일하다. 전체기한을지키지못하는burst는낮은J값이있어도적격후보가없다. 실제승자/배포허용/미래오차한도는계속null/false다.

```powershell
# 아래는 새 출력 폴더의 사후 재집계이며 추가 시뮬레이션/기기 명령은 없다.
python -m tools.d1_method_decision_readout --output output/method_frontiers
python -m tools.d1_method_decision_readout --relative-caps-file docs/results/method_followup_01/relative_nonworsening_example.json --output output/method_nonworsening
python -m unittest tools.test_d1_method_decision_readout -v
```

본 실험을 더 반복하지 않고 같은seed대조·전체분모·부분/결측null·기한실패차단·모형해시를검증했다. 새로운초기온도/사용사례/열피드백을승인하는경로가아니다. [검증 대상과명령](decision_readout_verification.json). 기기 계측이 필요한 구체적 경계는 [탐지 GPU 근거 연결](../detector_gpu_bridge_01/README.md)에 별도로 남겼다.

## 결론

앞선 온라인 후보 비교에서는 현재 지원되는 세 요청 cell과 CG_DC 병행에서 **EFT를 기준으로 전 요청의 기한을 지키면서 J·최고 AP·AP 부담 면적을 함께 비악화시키는 새 온라인 후보는 확보하지 못했다.** ATC/CPU 병목은 에너지와 일부 일반 응답을 줄이지만 AP와 긴급 응답의 손해가 있다. 현재 큐 다단계 유예는 미래 요청의 여유를 소모했고, 첫 행동을 즉시 배정으로 제한한 별도 후보도 기본 채택 근거가 없다. 실패와 동일 결과를 모두 보존한다.

이는 방법론 전체의 불가능 판정이나 프로젝트 주제 변경이 아니다. 기존 [조건별 목적 선택](../scheduler_conditions_01/README.md)의 고정 split 대비 제한된 개선은 그대로 유효한 **PC 탐색 결과**다. 강한 EFT 대비 공동 절감·실기기 효과는 별도 미완료다. 기본 스케줄러·동결 모형·strict·`experiment_ready=false`를 바꾸지 않았다.

## 무엇을 실행했는가

모든 본 입력은 기존 생성 규칙의 48요청이다. low(`g1.2_c0.5_b1`), queue 50%(`g0.45_c0.5_b4`), burst 50%(`g0.15_c0.5_b8`), queue 75%(`g0.45_c0.75_b4`)를 사용했다. 모델/기한/도착을 결과에 맞춰 바꾸지 않았다. mean/short_context/long_context의 **전체 5단계** 벡터를 유지했다. 이 세 문맥은 독립 기기 세션이나 WCET가 아니다.

| 단계 | 실행 전 고정 | 새 PC 계산 | 저장 EFT 재사용 | 별도 새 seed | 결과 |
|---|---|---:|---:|---|---|
| ATC·CPU 병목 | [등록](run_v1/registered_before_run.json) | 120 | 24 | 223001/223002 | 공동 비악화 0/96 후보 사례 |
| 큐 Pareto beam v1 | [등록](beam_v1/registered_before_run.json) | 72 | 24 | 323001/323002 | 공동 비악화 0/48; 유예의 기한 실패 |
| 즉시 배정 beam v2 | [등록](beam_v2/registered_before_run.json) | 72 | 24 | 423001/423002 | 공동 비악화 0/48; 서비스 36/48 사례 완전 충족 |
| offline 격자 참고 일정 | [등록](calendar_v1/registered_before_run.json) | solver 8·재생 8 | 별도 같은 입력 EFT | 223001/223002 mean | 공동 비악화 0/8; 최적성 미입증 incumbent 포함 |

264개 새 온라인 후보/대조 PC 계산과 8개 offline 재생이다. 세 단계의 저장 EFT 24건은 같은 기존 24건의 재사용이며 72개의 독립 표본이 아니다. 본 PC 요청 처리 총수는 `264×48+8×48=13,056`이다. 단위 테스트/작은 solver fixture는 본 비교 수에 넣지 않는다. 세 단계는 seed가 다르므로 후보끼리 다른 seed의 원 J/AP를 직접 비교하지 않고 **각자 같은 seed의 EFT와 대조**한다. seed 확인은 소프트웨어 확인이며 새 실측 독립 확인이 아니다.

## 전체 48요청에서 확인한 수치

새 seed 2개×3문맥의 평균 차이, `후보−EFT`. J는 0–120초 기기 전체 회계, AP는 같은 초기조건에서 35–180초 1초 질의. 일반 응답은 persist_complete, 긴급 응답은 output_ready, 자원 점유는 lane_available까지다.

| 입력·후보 | 기한 충족/전체 도착 | ΔJ | Δ최고 AP | ΔAP 부담 면적 | Δ긴급 P95 | Δ일반 평균 |
|---|---:|---:|---:|---:|---:|---:|
| queue 50%·ATC | 288/288 | −0.279385 J | +0.208772°C | +5.6963°C·s | +169.413ms | −118.478ms |
| queue 50%·CPU 병목 | 288/288 | −0.524165 J | +0.276163°C | +8.3862°C·s | +233.818ms | −170.225ms |
| queue 75%·CPU 병목 | 288/288 | −0.517496 J | +0.215088°C | +6.8408°C·s | 동일 | −178.984ms |
| queue 50%·beam v1 | 257/288 | −0.160387 J | +0.059640°C | +2.6864°C·s | +1,237.150ms | +2,878.156ms |
| queue 50%·beam v2 | 288/288 | 동일 | 동일 | 동일 | 동일 | 동일 |

burst 50%는 탐지 CPU의 필수 수요부터 일부 기한창을 넘는다. 새 seed에서 EFT 168/288, ATC 207/288, 병목 217/288로 개선되지만 완전 서비스는 아니다. [필수 CPU 수요·완화 J 하한](run_v1/bounds.csv)은 현재 고정 시간 모형의 필요조건이며 기기 용량 인증·충분조건이 아니다. beam v1/v2의 다른 seed 분모와 손해는 [전체 표](beam_groups.csv)를 따른다.

공동 비악화의 사전 정의는 전체 기한 충족, J·최고 AP·부담 면적 모두 EFT 이하이고 하나 이상 감소다. 응답 P95 비악화를 뜻하지 않으며, `1e-8`은 부동소수점 판독 오차일 뿐 연구 정확도 허용폭이 아니다. 작은 모형 차이를 실측으로 식별할 수 있다는 주장도 아니다.

## 왜 상충하는가: 식에서 확인한 범위

[항과 수치](energy_heat_identity.json), [조건별 완화 경계](energy_heat_bounds.csv). 평균 처리시간에서 분류 CPU lane 점유 `C=0.165216276s`, GPU `G=0.304829475s`, 탐지 CPU `D=0.621736895s`다. 추가 전력은 `wC=.584429435`, `wG=.472884373`, `wD=.712925902`, `wGD=.887811893W`다.

동일 작업 수에서 GPU 분류 수를 n, 탐지 CPU와의 겹침을 x초라 하면:

`J = J_CPU + n×0.047591841 − x×0.297998382`

AP 상태식의 resident 대비 가열 입력 적분 U는:

`U = U_CPU + n×0.014069107 + x×0.056976116`

따라서 분류 1건을 GPU로 바꿔 전부 탐지와 겹치면 **−0.043246850J / +0.031437107°C의 입력 적분**이다. U는 물리적 열량·주변 온도·AP 최고값이 아니다. 같은 초기조건과 등록된 `g=0`에서 무한 시간의 **부호 있는 AP 차이 적분**은 `k/β×ΔU`이며 위 1건은 +0.736232°C·s다. 실제 유한창의 양의 부담 면적·최고온도 또는 모든 실제 정책의 불가능 증명으로 확대하지 않는다.

queue 대표 EFT는 같은 J 이하를 허용한 U 완화 하한에 수치적으로 가깝다. 이 하한은 도착·기한·배치를 완화한 모형 내부 값이다. 그래서 알고리즘 이름만 바꿔 같은 지원 상태를 더 병행하는 것은 J 감소와 AP 입력 증가를 함께 만든다. 가열 입력을 낮추는 지연은 최고 AP를 낮출 수 있지만 응답·기한을 별도 검사해야 한다.

## offline 참고값과 온라인 후보의 경계

`calendar_v1`은 모든 미래 도착과 해당 처리시간 문맥을 알고 20ms 격자에 first start를 배치한다. CPU/GPU lane와 금지된 분류 CPU+분류 GPU 동시 실행을 제약하고, 계획 점유를 위로 반올림한다. 반환 일정은 원래 비반올림 5단계 엔진으로 다시 재생한다. min J 및 EFT 최고 AP cap 두 목적×4입력, solver당45초 상한이다. 모델 최적성과 실기기 효과를 보장하지 않는다.

queue 75%/seed223001의 AP cap incumbent는 재생 ΔJ −0.309185J·Δ최고 AP −0.029244°C였지만 **AP 부담 면적 +2.971444°C·s·긴급 P95 +790.627ms**다. queue 50%/seed223001은 최고 AP −0.080476°C·면적 −0.084837°C·s 대신 J +0.229269J·긴급 P95 +984.658ms다. 모든 solver 상태·gap·실제 재생 차이는 [결과](calendar_v1/results.csv)에 남긴다. offline 해를 미래를 모르는 폰 정책으로 부르지 않는다.

beam v1은 현재 큐만 보고 4요청·폭8·callback 확장 최대64개, 현재 요청별 long_context 지각 보호와 mean J/peak 보호를 적용했다. 이런 국소 보호는 미래 도착 전체를 보장하지 않는다. 반복 250ms 유예의 실패를 본 뒤 개발한 v2는 즉시 가능한 첫 배정만 허용했으며 사후 개발이라고 표시했다. 부모 v1·실패 결과는 그대로 보존한다. controller 처리 비용은 PC 기록에 별도 있고 기기 비용은 0 가정이다.

## 지금 쓸 방법과 남은 구체적 공백

- 현재 지원 범위의 기한 중심 비교에는 **EFT를 강한 PC 기준**으로 유지한다. J 우선 또는 AP 우선 목적별 조건 지도는 상충을 보이는 결과로 사용할 수 있다. 새 후보를 실제 절감 정책으로 자동 채택하지 않는다.
- 엄격한 기한이 불가능한 burst는 알고리즘 변경만으로 완주한다고 만들지 않는다. 요청을 버리지 않고 용량 밖 분모를 남긴다.
- 탐지 GPU는 과거 고정 상태/시간 자료가 **존재**하지만, 현재 요청 프로필의 exact 5단계·resident·관측 프로토콜 연결이 자동 성립하지 않는다. 기존 자료의 필드 대응을 먼저 확인해야 하며, S26 계수·다른 APK의 평균 W를 붙여 현 모형의 빈 cell을 채우지 않는다.
- 열→처리시간 피드백, 전력 차단, 미측정 배정은 이 연구 경로의 지원 밖이다. 열을 사후 계산하는 기능과 열 때문에 서비스가 달라지는 모형을 구분한다. 이번 PC 작업으로 프로젝트의 실제 열·에너지 공동 절감을 완료했다고 쓰지 않는다.

## 재현과 보존

공유 압축 ledger·입력·고정 소스 해시만으로 **재집계·화면 생성·경계 검증**이 가능하다. 부모 18.59MB ledger가 필요한 새 본실행은 별도 의존이며 기존 결과를 소비하거나 재생성할 필요가 없다.

```powershell
python -m tools.d1_energy_heat_frontier --root docs/results/method_followup_01
python -m tools.d1_method_followup_report --root docs/results/method_followup_01
python -m unittest tools.test_d1_method_followup_report tools.test_d1_method_followup tools.test_d1_deadline_calendar tools.test_d1_pareto_beam tools.test_d1_pareto_immediate tools.test_d1_energy_heat_frontier -v
```

`source_snapshots/`는 실행 전에 등록한 observer/search의 정확한 byte를 보존한다. 현재 observer는 두 후보 namespace만 추가했으며 회계/controller 본문이 바뀌면 보고서 해시 검사가 중단한다. 관련 회귀에서 Windows 시계가 동일 tick인 `timeout=0`에 탐색 깊이1까지 진행하는 경계 결함을 재현해 `>`를 `>=`로 수정했다. 고정 시계 테스트로 확장0·원 incumbent 보존을 확인했다. 이 beam search는 이번 전체 입력 비교/혼합정수/큐 후보 실행에는 호출되지 않아 본 결과를 재계산하지 않았다. 옛 등록 해시를 새 해시로 덮어쓰지 않으며 두 최소 차이 이외의 코드 변경은 재집계에서 차단한다. 과거 industrial 보고서의 본실행 재현은 commit `42890f4`의 소스를 사용한다.

검증23건은 본 입력의 분모·120초 J 보존·상태/시간 경계·미래 정보 차단·미확인 null·등록 소스·기존 동결 해시를 검사한다. 관련 기존 회귀 결과와 현재 Git 기준은 `verification.json`을 따른다. 새 기기 명령·실측·APK·설치·기기 계획·소비 claim **모두 0**이다. 원본/FAIL/strict/미소비 계획/사용자 별도 파일/다른 worktree를 보존한다.
