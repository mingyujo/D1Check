# 전체 요청 방법론 비교와 동결식의 에너지·AP 상충

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

현재 지원되는 세 요청 cell과 CG_DC 병행에서 **EFT를 기준으로 전 요청의 기한을 지키면서 J·최고 AP·AP 부담 면적을 함께 비악화시키는 새 후보는 확보하지 못했다.** ATC/CPU 병목은 에너지와 일부 일반 응답을 줄이지만 AP와 긴급 응답의 손해가 있다. 현재 큐 다단계 유예는 미래 요청의 여유를 소모했고, 첫 행동을 즉시 배정으로 제한한 별도 후보도 기본 채택 근거가 없다. 실패와 동일 결과를 모두 보존한다.

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
