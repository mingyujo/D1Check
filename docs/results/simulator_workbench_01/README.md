# D1Check 통합 시뮬레이터

## 2026-10-06 공동 절감의 필요조건 추가

[현재 동결식의 J 이득 상한](../method_followup_01/joint_bound_v2/index.html), [식·검증](../method_followup_01/README.md). 전기한/EFT최고AP·양의AP면적을동시에유지하는queue50의낙관적이득상한은각저장사례0.120–0.178J다. 완화된순간입력LP이며실현가능정책/실기기성능/정확도기준이아니다. 큰공동절감이나모든방법의불가능을증명하지않는다. 기본정책/계수/strict미변경,새시뮬레이션·기기0.

## 2026-10-06 방법론 판독의 통합 진입 완료

```powershell
python -B -m tools.d1_simulator method-readout --output output/method_readout
```

[실행 예시 화면](../method_followup_01/workbench_v3/index.html), [범위·검증·해시](../method_followup_01/README.md). 저장28묶음/168사례를 기한→계수 매핑→독립 예측 확인→정책 차이 식별로 나눠 읽는다. 새 일정/계수/기기 실행이 아니며 새 seed·정책·온도·제약을 이 경로에 전달할 수 없다. 실제lane 반환까지의 상태 창과 자원 중복을 확인하되 새 일정의 전용·제어비용0은 탐색 가정, strict/독립 확인/배포추천은 미완료다. 신규8검증·기존 대표3회귀 통과. 기존 네 실행 경로의 의미를 바꾸지 않았다.

## 2026-10-06 모형 절감과 실제 제어 비용의 경계

[상충·손익분기 화면](../method_followup_01/tradeoff_budget_v2/index.html), [판독·실제계측부재·재현](../method_followup_01/README.md). 기존28묶음/168사례에서전기한충족과같은사례비용을먼저검사했다. queue50 CPU병목의최소모형J이득0.430421J는미모형화차등비용으로없어질수있고최대AP+0.291083°C상충이남는다. EFT callback의원0은계측부재/null이며휴대폰무비용이아니다. 새실측·새가정·정책효과PASS를표시하지않는다.

## 2026-10-06 호환 자원 backfill의 시간 평가 완료

[분류CPU고정/탐지CPU·GPU 비교](../detector_gpu_bridge_01/compatible_backfill_v2/index.html), [근거·검증](../detector_gpu_bridge_01/README.md). 새16PC사례 중12전기한충족이나큐응답상충/버스트실패·현재J/AP null로새기본정책미채택. 실제lane해제/중복점유차단을검증하고옛이벤트본문을보존했다. 실측/독립확인/절감그림이아니다. [전체입력 방법론 판정](../industrial_scheduling_01/README.md)은기한우선·EFT대조·Pareto상충평가를권고한다.

## 방법론 결과를 사용하는 경로 — 2026-10-06

[기한→Pareto 상충 판독](../method_followup_01/decision_readout_v2/index.html), [명시한 J/AP 비악화 질문](../method_followup_01/decision_nonworsening_v2/index.html), [CLI/해석](../method_followup_01/README.md). 저장된 전체48요청결과만읽고추가시뮬레이션은하지않는다. 다른seed의block을같은대조로합치지않으며,EFT동일과새개선·기한실패·미확인비용을구분한다. 제약/상충판독은완료했지만실제정책승자·미래오차한도·배포추천은null/false다.

## 탐지 GPU 과거 시간 근거의 연결 판정 — 2026-10-06

[과거 CAL03 원본·미식별 항](../detector_gpu_bridge_01/README.md), [시간 참고 일정](../detector_gpu_bridge_01/index.html). 5단계/worker release/lane 해제·delegate 근거는 존재한다. 64개 새 시간전이 PC 계산에서 모든 탐지GPU의 일반기한손해와4-cellEFT의미측정분류CPU+GPU병행을분리했다. 현재DG/CC_DG J/AP는null이며새실측/예측PASS/정책절감으로표시하지않는다. 이번확인은추가GPU측정이반드시이득이라는주장이아니다.

## 전체 요청 방법론 비교 — 2026-10-06

[전체48요청·다단계큐·offline 참고값](../method_followup_01/index.html), [계약·재현·상충식](../method_followup_01/README.md). 새264PC계산과8일정재생을 연결했다. ATC/병목의J감소와AP증가, 유예후보의기한실패, 즉시배정후보의EFT동일/과부하손해를 보존한다. 미래입력을아는참고일정은온라인정책이아니다. 새실측/정확도PASS/실제절감그림이아니며기본·strict·experiment_ready=false를유지한다.

## 최신 시연 경로 — 2026-10-04

[192요청 CPU/PAR 실측·동결 예측](../online_policy_study_01/overnight_sustained_run01/index.html)과 [연구 본문](../../ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md)을 먼저 읽는다. 실제 온라인8세션 모두192/192 기한을 충족했다. 병행 긴급P95는127.912–131.381ms 짧았지만, 관측 에너지 차이는−5.304–+11.682J로 부호가 바뀌었다. 관측 최고AP 차이와 모형의 예상 최고AP 차이를 구분하며 작은J/AP 정책 선택은 차단한다.

기존 `tools.d1_simulator arrival`은 과거queue/seed201 일정 경로다. **새192 입력은 별도 등록 경로**로 아래 명령을 사용한다. Python·NumPy·Matplotlib 환경에서 새 출력 폴더를 지정한다. ADB/기기/외부 대용량 원본은 필요 없다.

```powershell
python -B -m tools.d1_sustained_readout predict --bundle docs/results/online_policy_study_01/overnight_sustained_run01 --index 0 --policy CPU_URGENT_ONLINE_V1 --output output/sustained_cpu
python -B -m tools.d1_sustained_readout predict --bundle docs/results/online_policy_study_01/overnight_sustained_run01 --index 0 --policy B2_PARALLEL_ONLINE_V1 --output output/sustained_par
```

초기조건0의120초 모형값 CPU185.389926J/PAR183.299134J를 재현한다. 초기값은 저장된 부하 전 AP 이력과 전력이며 이후 실제 미래 관측은 사용하지 않는다. 전체 실측 재분석과 파일 의존성은 [해당 README](../online_policy_study_01/overnight_sustained_run01/README.md)를 따른다. 입력·계수·공유물 해시가 다르면 차단하며 새 도착/정책을 임의로 허용하지 않는다. strict=false, accuracy_pass/policy_winner=null, experiment_ready=false.

아래는 2026-10-02에 제공한 기존 경로의 사용법과 당시 확장 과제다. 완료된192요청 확인을 다시 준비·실행하라는 지시가 아니다. 기존 verification.json은 당시 검증이며 최신 근거는 새 번들의 verification.json/resources.json에 분리했다.

[통합 시작 화면](index.html) · [도착 일정/실측 참조](arrival/index.html) · [고정 870건 모형](episode/index.html) · [검증](verification.json)

2026-10-02: 여러 개의 분석 스크립트를 찾아 조립하던 경로를 `tools.d1_simulator` 한 진입점으로 연결했다. 새 정책·새 계수·새 실측 없이 기존 엔진과 지원 판정을 재사용한다. 소프트웨어 실행 경로는 완료했으며 **임의 도착의 에너지·AP 예측 또는 열 피드백 모형이 검증 완료됐다는 의미는 아니다.** `experiment_ready=false`와 기존 기본/strict 규칙은 유지한다.

## 실행

저장소 루트에서 Python 표준 라이브러리만 필요하다. 출력 폴더는 새 경로여야 하며 기존 결과를 덮어쓰지 않는다. ADB·Android SDK·외부 원자료·기기 연결이 필요 없다. 현재 검증 환경은 Windows checkout(`core.autocrlf=true`)이다. 기존 동결 파일의 byte SHA 계약을 유지하므로 다른 줄끝으로 변환한 checkout은 해시 검사에서 차단될 수 있다. 다른 OS의 byte 재현까지 검증했다고 하지 않는다.

```powershell
python -B -m tools.d1_simulator arrival --scenario queue --mode explore --seed 201 --output output/sim_queue201
python -B -m tools.d1_simulator episode --output output/sim_fixed870
python -B -m unittest tools.test_d1_simulator tools.test_d1_energy_operational_decision tools.test_d1_arrival_service_guard -v
```

각 출력의 `index.html`을 브라우저에서 연다. HTML은 오프라인 동작하며 `result.json`에 입력·설정·원자료 파생물/소스 해시가 있고, `summary.csv`와 정책별 `*_schedule.csv`에 전체 예정 분모와 각 실행 경계가 있다. Python 명령은 UI를 자동으로 띄우지 않는다.

도착 경로는 기존 low/queue/burst, strict/explore와 정수 seed를 지원한다. 세 정책 CPU_URGENT/B2_PC/B3_SOLO_EFT_PC만 계산하며 B2 배정은 기존 동결 선택값이다. P 재튜닝·전체 배치·RL은 없다. `strict`는 스케줄러의 기존 실행 제한 이름이며 모형 정확도 판정이 아니다. 간섭 1.5와 큐 전용 가정, 연구용 urgent 1.5초/normal 6초 기한을 그대로 기록한다. 응답은 urgent output_ready/normal persist_complete이고 lane 해제와 구분한다.

고정 경로는 **기존 CC_DG 분류 CPU678＋탐지 GPU192, 480초**만 다룬다. 기본 AP29.1°C는 보관된 두 확인 세션의 시작값이며 새 기기의 현재값이나 지원 온도 범위가 아니다. 예를 들어 `--completion-cap-s 250 --ap-cap-c 35`로 기존 모형의 제약 민감도를 볼 수 있으나 안전 기준·배포 추천이 아니다. 다른 시작 AP는 기존 상위 지원 검사에서 차단한다. AP 곡선 정렬의 미검증 가정과 조건별 확인1개의 오차 민감도를 유지한다.

## 계산과 실측을 섞지 않는 규칙

| 경로 | 계산/재사용 | 완료한 것 | 남은 한계 |
|---|---|---|---|
| 도착 입력→일정→응답 | 기존 CAL03 시간 벡터·엔진·정책 | 세 정책 일정·분모·서비스 비교·지원 차단·CSV/화면 | 간섭/큐 전용은 가정, 새 온라인 정책의 독립 예측 확인 아님 |
| 같은 기록 일정의 J/AP | CPU/B2 ABBA4세션을 별도 관측 참조 | exact queue/explore/201 및 모든 저장 실행 경계가 일치할 때만 표시 | 기록 재생은 온라인 실행 아님. 초기조건/이력 차이·두 관측의 변동성 |
| 동적 에너지·AP | 기존 상태 모형 지원 검사 | 미지원 전환이면 J/AP/null·순위 null | 유휴 이력·짧은 전환의 비용 전용, 후기 AP/최고, 열→처리시간 미검증 |
| 고정870건 | 기존 동결 episode 모형/확인 결과 | 제한된 수치·제약 민감도 | 임의 도착·온도 sweep·동적 열법칙 아님 |

queue/201 PC urgent P95는 CPU641.346/B2 424.755/B3 1014.998ms, 마감 충족18/20/20개다. 기존 서비스 규칙에서 B2는 적격, B3는 urgent P95 악화로 부적격이다. 이 적격성은 정확도 PASS가 아니다. 실제 두 B2 관측 J136.955/145.800과 CPU146.153/147.412는 예측 비용에 입력하지 않는다. B2−CPU 두 쌍−9.198/−1.611J는 기술적 실측 결과이며 보편 절감률이 아니다.

`resources.json`은 이미 공유된 시간 번들·정책 동결·저장 일정·서비스 규칙·고정 모형·관측 CSV/JSON의 정확한 해시를 검사한다. 파일이 바뀌면 실패하며 자동 재적합/해시 갱신을 하지 않는다. seed·입력·모드·backend·전체 일정 중 하나라도 바뀌면 실측 참조를 대입하지 않는다. 미지원/결측은 CSV 공란과 JSON null이며 0J가 아니다. 그림도 없는 표본을 0으로 만들지 않는다.

## 추가 실측 판정과 종료점

**이 제한 시뮬레이터의 실행·공유·연구 본문 완료에는 새 실측이 필요하지 않다.** 이미 끝난 ABBA 네 세션과 AP 이력 진단을 다시 실행해도 미식별 열 반응이 저절로 식별되지는 않는다. 이번 기기 명령·설치·추론·실측·새 계획·소비 claim은 0이다.

범위를 확장하려면 (1) 선택한 새로운 도착 조건에서 CPU/B2의 실제 온라인 dispatch와 전체 분모를 함께 관측해 종단간 일정 예측을 확인하거나, (2) 초기 AP만으로 구분되지 않는 준비/이력에 대한 모형 구조를 먼저 고정하고 기존 C/L·두 이력 자료로 식별 가능성을 보인 뒤 별도 확인을 해야 한다. (2)의 후기/최고온도 문제를 해결할 후보는 현재 채택되지 않았으므로 실측 횟수·시간을 근거 없이 정하지 않는다. S26 계수, 임의 스로틀, 새로운 전력 가정으로 빈 부분을 채우지 않는다.

종료 기준은 재현 가능한 CLI/화면, 전체 분모 보존, 지원 밖 계산 차단, 정확한 실측 연결, 기존 동결본 보존이다. 모두 PC 검증했다. 다음 행동은 이 화면을 사용해 **queue201의 서비스 상충과 별도 관측 비용을 설명하는 결과 시연**이다. 포괄적 재감사나 동일 진단 반복이 아니다.

## 준비 이력 후보의 추가 PC 결과

[2026-10-02 후보·재현·한계](../ap_preparation_memory_01/README.md): 기존 개발1/사후 평가4에서 준비 반응 상태를 추가한 조건부 AP 후보를 구현했다. 평균·최고오차는 개선하지만 후기 재상승은 미해결이며 기본/strict로 채택하지 않는다. 이 후보를 arrival 비용으로 넘기면 J/AP/정책 순위는 명시적으로 null이다. 기존12건 시뮬레이터 회귀와 새 경계 검증을 완료했다. 위 verification.json은 최초 구현 시점의 기록이고 이번 소스/검증은 새 후보 번들에 분리했다.

## 등록된 조건부 AP 재생 연결 (2026-10-02)

기존 일정/서비스·직접 관측 참조와 별개인 `ap-conditioned` 경로를 연결한다. 개발6의 사전 선택 규칙으로 미채택된 M1은 쓰지 않고, 확인 전에 동결한 M0를 byte 대응하는 작은 공유 입력과 함께 재생한다. 두 확인은 사용자 휴지 전, 나머지 네 확인은 휴지 후 별도 block이므로 연속12세션 완주나 통제된 환경 반복으로 취급하지 않는다. 최신 상태·수치·재현 파일은 [AP 확인 결과](../ap_completion_study_01/final/index.html)와 [통합 보고서](../../AP_MODEL_COMPLETION_STUDY_20261002.md)를 따른다.

```powershell
python -B -m tools.d1_simulator ap-conditioned --case-id v2_confirmation_0_C --output output/ap_registered_C
python -B -m tools.d1_simulator ap-conditioned --case-id v3_confirmation_2_SPLIT_DELAY30 --output output/ap_registered_split
```

이 경로에는 NumPy가 필요하다. 기존 arrival/episode는 표준 라이브러리 경로를 유지한다. 실제 lane 일정과 common+35초 이전 AP를 알고 있는 **오프라인 조건부 예측**이다. 이후 AP·전류는 예측 입력으로 전달하지 않고 오차 계산에만 사용한다. 등록된 파일·모형·과학 코드 해시 또는 case ID가 다르면 계산을 막는다. AP 값을 바꾸는 `--initial-ap-c` 옵션이나 새로운 도착·정책 입력은 받지 않는다. 출력은 AP 경로·잔차·MAE·최대·최고오차이고 J/정책 순위/열→처리시간/accuracy PASS/strict는 null 또는 미지원이다. 표본 수는 독립 세션 수가 아니다.

기존 임의 도착의 에너지·AP 차단을 해제하지 않았다. 현재 한정 시뮬레이터는 일정/응답, exact 저장 일정의 별도 관측, 고정870건 episode, 등록된 실측 일정의 AP 조건부 재생을 제공한다. 보편적인 에너지 절감률·열 피드백 최적화 모형의 완성은 아니다. `experiment_ready=false`를 유지한다.
