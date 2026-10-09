# D1Check 통합 시뮬레이터

## 2026-10-10 추가 AP 후보와 전체 교체 보류

[세AI4차토론·20fit·35판독](../../SESSION_CONTRAST_COST_RESULTS_20261010.md) · [추가개선과반례](../session_contrast_cost_01/index.html). LOAD600 J/AP와긴AP가더개선됐지만추정미사용과거20 AP/긴J/정책차가악화했다. 새API는명시적전이진단용으로만두고기존zero+고정LOAD 주진단/기본/RL/strict를유지한다. 이미본자료의사후평가·새실측/기기0이다.

## 2026-10-10 에너지·AP 개선 비용 API 구현 완료

[실제추정·35평가·API](../../ENERGY_AP_ZERO_OFFSET_RESULTS_20261010.md) · [그림·악화·명령](../energy_ap_zero_offset_01/index.html). δ0/p4를개발4로5fit,고정AP와별도opt-in으로연결했다. LOAD공통관측J절대23.060→6.187/AP MAE0.437→0.173°C,과거29의참고120초J5.522→5.144이나10악화/C0·정책차부호문제는남는다. 기본/RL/strict는유지·새실측/기기0. 계산경로구현과새독립확인·전체정책정확도를구분한다.

## 2026-10-09 긴 C0·부하 회복: 미승인 실행 준비

[최종2조건 계약·예산](../../AP_TAIL_OBSERVATION_PREP_20261009.md) · [준비 화면/Check](../ap_tail_observation_prep_01/index.html). 별도opt-in으로 C0와1920초냉각을 지원했다. 고정88분/전체2h30m50s/최대1224추론·16752ADB, 새실측/오차감소결과아님·기기0·기본/RL/strict 유지. 기존33판독과 현재미승인계획을 구분한다.

## 2026-10-08 모형 식별/확인: PC 준비·미승인

[8세션·계약·상한](../../RESIDENT_IDENTIFICATION_PREP_20261008.md) · [준비/검증/입력](../resident_identification_prep_01/README.md). 개발4 긴상태/유휴→자료/계수동결→다른순서2+실제Arrival96/192 요청2의전이확인이다. 새실측/오차감소그림없음·Check기기0/미소비. 최대6376추론/5h17m50s/34728ADB는별도실행승인대상이며기본/RL/strict는유지한다.

## 2026-10-08 AP 초기화 변경: 지속 부하 일부 오차 감소

[20평가·관측/예측/잔차](../preload_dynamics_refinement_01/run/index.html) · [초기화후보/API·재현](../../PRELOAD_DYNAMICS_REFINEMENT_RESULTS_20261008.md). AP지속8 MAE0.381→0.335°C/최대1.277→1.165°C,최근14 평균0.329→0.307°C 감소. 새확인6/지속4개악화·개발기준실패로기본미교체,전력추세후보악화로제외. 별도opt-in AP API29경로일치,물리계수/원기본/RL/strict/기기불변.

## 2026-10-08 정책 계수 민감도: 설정 안의 방향 판독

[첫seed72저장일정·96guard·그림](../policy_coefficient_sensitivity_01/run_v2/index.html) · [판정·재현·면적수정](../../POLICY_COEFFICIENT_SENSITIVITY_RESULTS_20261008.md). R2/EDD는주6조건Triton대응대비J/최고AP방향5설정모두유지,공용EFT/Band대비공동감소0·지속J부호변화. 미채택계수변형의고정일정민감도이며새B재실행/실제절감/신뢰구간아님. 기본/RL/strict불변·환경/적합/기기0.

## 2026-10-08 공동 계수 후보: 일반 적용 보류

[20세션·68행·그림](../joint_model_refinement_01/run/index.html) · [개발/평가·정책 차이·재현](../../JOINT_MODEL_REFINEMENT_RESULTS_20261008.md). 최근14 조건부J MAE4.319→4.273J이나AP0.329→0.369°C·정책차이6.322→8.730J 악화. 개발묶음제외기준실패. 과거고오차도보존하며원모형/RL/strict유지. MEMORY30의80초실행중관측보정은사전정책예측과구분한다. 기기명령0.

## 2026-10-08 전력 잔차 지속성과 30초 후보: 특정 조건만 개선

[20세션·640행 비교](../energy_memory30_01/index.html) · [판독·재현·악화 조건](../../POWER_RESIDUAL_STRUCTURE_RESULTS_20261008.md). 전류 반복 10/2,644쌍, 기록 간격 약 0.9초이며 센서 내부 갱신 주기는 미확인이다. 개발 전용 alpha 0.519 후보는 확인 개별 10초 MAE 0.870→0.848J로 줄였지만 지속은 0.844→0.854J로 악화했다. 개발 교차 기준 실패로 기본 적용은 보류한다. 합산 80초 순오차 개선은 순차 관측·상쇄를 포함하며 전체 120초 예측 개선이 아니다. AP·원모형·RL·strict 불변, 정책 환경·기기 0회.

## 2026-10-08 에너지 보정 강도 추정: 원모형보다 평균오차 감소 미확보

[비교/480행](../rolling_energy_shrink_01/index.html) · [추정·교차평가·범위](../../ROLLING_ENERGY_SHRINK_RESULTS_20261008.md). 개발6에서 alpha0.263 고정·회복교차gate실패. 확인10초MAE 원0.870→후보0.922J/지속0.844→0.856J 악화, 합산80초 확인3.891→2.960J 감소는상쇄/순차관측포함·120초전체예측개선아님. 원모형/RL/strict 유지·이창의에너지오차보완작업이며정책/앱AP/기기0.

## 2026-10-08 AP 관측 경로: host 진단 입력 검증·현재APK 미지원

[지원표](../ap_observation_path_01/index.html) · [적용판정/8검증/재현](../../AP_OBSERVATION_PATH_PC_20261008.md). host CurrentHAL AP→PC10초예측의별도API구현/20진입검증, 기존1630관측대조3명령span중앙값.328초/P95.437초. producer기록시각을consumer수신으로승격하지않고실수신시각은명시필수·없으면proxy. 현재APK직접AP/연속consumer없음·전달지연null·기기자율적용불가. Android/빌드/기기0·원기본/strict/RL불변.

## 2026-10-08 10초 관측 갱신: AP 평균 개선·개별J 악화

[화면/840창](../rolling_forecast_01/index.html) · [결과·가용시각·재현](../../ROLLING_FORECAST_RESULTS_20261008.md). 같은조건부A10초창에서AP확인0.258→0.156°C/지속0.383→0.209°C, 확인최대AP1.077→1.380°C. 개별J확인0.870→1.268J악화, 35..115초갱신합순오차3.891→0.632J감소는상쇄/지속관측을포함하며120초전체예측아님. 새계수fit/정책환경/기기0, 기본/strict/RL/experiment_ready=false유지·실시간numericAP전달경로미검증.

## 2026-10-08 새 이력 자료 모형 보완: 특정 조건만 개선

[후보 비교/100행](../history_model_refinement_01/index.html) · [결과·재현](../../HISTORY_MODEL_REFINEMENT_RESULTS_20261008.md). 두구조·개발6고정→확인6+지속8사후평가완료. AP확인MAE0.260→0.233°C이나개발선택실패/지속최대오차악화, 에너지지속MAE4.624→4.140J이나확인3.913→4.694J·4쌍차이오차악화. 후보일반적용보류·원모형/RL/strict/experiment_ready=false유지. 새로운처리결함없음, 새기기/학습/정책환경0.

## 2026-10-08 정책 차이와 새 이력 확인 오차

[판독 화면](../history_policy_readout_01/index.html) · [한국어 결과](../../HISTORY_POLICY_ERROR_READOUT_20261008.md). 저장192조건/2,112행을 재사용해1,920쌍의 서비스·J·최고AP와 새 확인6잔차를 연결했다. 주96 후보−Triton −0.790J/−0.130°C, Band +0.167J/−0.052°C. 작은 공동감소의실기기우월성은미확인, 보편오차한도/정책승자null. 기존지속CPU/PAR 응답127.912–131.381ms개선관측은별도사용가능. 새환경/학습/기기0·원모형/기본/strict불변.

## 2026-10-06 방법론 탐색의 최종 판독

[계수오차 역산 8행](../method_followup_01/joint_gain_sensitivity_v2/index.html), [전체 결과·41 관련 검증](../method_followup_01/README.md). 고정 미래일정의 작은 공동 모형 이득과 온라인 후보의 AP 감소/J 증가를 분리한다. 같은 고정 일정의 J 이득 소거 계수오차 조건은 약 0.060–0.099W이며 실제 불확실성·제어비용은 null이다. 실제 절감·독립 예측 확인·온라인 우월성은 미완료다. 현재 추천은 강한 EFT 대조·전체 도착 기한·목적별 Pareto이며, 새 후보/기본/strict/기기계획을 추가하지 않았다.

## 2026-10-06 현재 큐의 열 지향 후보: 에너지와 상충

[새2seed×3문맥·같은EFT 대조](../method_followup_01/joint_queue_readout_v1/index.html), [계약·13검증·재현](../method_followup_01/README.md). J/최고AP/면적을현재큐에서같이검사한후보는288/288기한을지켰지만전체창J +0.055–+0.176J/최고AP −0.108–−0.020°C상충이었다. local guard의통과를전체미래창/실기기절감보장으로바꾸지않는다. 새후보하나만평가·재튜닝0,기본/strict/experiment_ready=false유지. 그림은모형끼리의차이이고새실측확인그림이아니다.

## 2026-10-06 고정 미래일정의 처리문맥 전이

[short/long4재생](../method_followup_01/joint_calendar_transfer_v1/index.html). mean에서찾은두계획의backend/허용시각을유지하고기존개발전체5단계문맥만바꿨다. 4/4전기한·J/최고AP/양의AP면적감소가유지됐지만mean포함6계산최소J이득은0.002644J로작고응답이늘었다. 실제lane반환을기다리는별도PC경로이며새최적화/기기실측이아니다. 독립확인/온라인정책/정책효과PASS 미완료,기본/strict/experiment_ready=false유지. [소스·6검증·실제CLI·재현](../method_followup_01/README.md).

## 2026-10-06 공동 제약 offline 참고 일정 추가

[저장4사례 화면](../method_followup_01/joint_calendar_readout_v2/index.html), [계약·재현·검증](../method_followup_01/README.md). 같은 mean queue75 두 입력에서 모든48기한을지키며 J/최고AP/양의AP면적이 함께 감소하는 미래일정을 원PC엔진으로 확인했다. J 차이는 −0.052468/−0.013042J로작고 긴급P95/일반응답이늘었다. 모든시점/부호있는온도면적은개선이아니며실기기·온라인정책·독립확인이아니다. queue50 정수해미확보는제약불가능으로해석하지않는다. 현재기본/strict/experiment_ready=false불변. 기존온라인후보공동개선0 결과와분리한다.

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
