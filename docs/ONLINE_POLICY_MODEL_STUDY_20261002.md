# 실제 도착 정책의 일정·에너지·AP 개발/독립 확인

## 연구 완료 경계

원래 목표는 도착·배정·시점 정책에서 일정/응답/J/AP를 예측하고 새로운 실행에서 정책 간 차이를 판단하는 것이다. 기존 AP 조건부 재생의 완료를 전체 완료로 바꿔 부르지 않는다. 기존 M0 확인6·CPU/B2 기록 재생4를 그대로 보존하며 이번 새 자료에 합치지 않는다. 강한 단순 정책으로 충분하거나 차이가 불확실한 결과도 유효하다. RL과 임의 스로틀 법칙은 필요하지 않다.

## 사전 고정한 한 묶음

[기계 판독 계약](results/online_policy_study_01/analysis_contract.json). CPU 우선 직렬, 분류 GPU/탐지 CPU 병행, 같은 배정의 직렬의 세 정책을 비교한다. 앱은 도착한 요청과 실제 lane 해제만 사용한다. 직렬 대기는 전 작업의 실제 해제를 기다리는 정책이며 인위적 추론 감속이 아니다. 기존 저장된 dispatch 시각 재생, PC 간섭1.5 강제 적용은 없다.

96요청 중 분류 urgent24/탐지 normal72. 도착은 공통+35초부터 개발500ms/확인550ms 간격이며 이전 완료와 독립이다. 마감 urgent1.5초/normal6초 유지. 개발 CPU/병행/직렬 각1 → 모형 동결 → 확인 CPU/병행/직렬/직렬/병행/CPU 각2. 확인의 도착 간격은 개발과 다르다. 사후 가장 잘 맞는 입력 선택을 하지 않는다.

기존 기록4의 탐지 CPU lane 평균622–628ms, 분류 CPU160–164ms/GPU285–293ms를 근거로 500/550ms 입력을 정했다. 약50초의 부하와 별도 CPU/GPU/병행 상태를 관측하기 위한 입력이며, 실제 병행시간이나 계수 식별을 보장하지 않는다. 기존24요청 뒤 대부분 유휴였던 전체 에너지 상쇄 문제를 줄이되 짧은 개별 요청 전력 정밀 식별이라고 하지 않는다.

## 모형과 자료 사용

- 처리시간: 정책별 개발 실행의 다섯 단계 산술평균. 기존 이벤트 엔진에서 실제 도착과 동일 온라인 정책으로 예정 일정을 생성한다. 관측된 병행 영향이 포함된 정책 맥락 모형이므로 추가 간섭계수는1, 별도 가정 지연은0이다. 처리시간이 온도와 무관하다는 주장이 아니며 다른 온도/부하로 확대하지 않는다.
- 에너지: 공통10–30초의 부하 전 기기 전력 + 4상태의 비음수 증가분. 개발35–120초 고정5초 구간의 실제 점유로 추정하며 행렬rank4가 아니면 확인 중단. 수치 rank는 정밀 식별 증명이 아니다. 전체120초와 예측 생성 이후35–120초를 구분한다. 부하 전 기준도 주변 온도/상수 물리 배경이라고 하지 않는다.
- AP: 기존 M0의 beta/tau/g, 부하 전 AP 초기화를 유지하고 개발3으로 부하 gain k 하나만 비음수 추정. 추가 후보군 탐색0. 기존 M0와 옛8상태W는 보존한다.
- 확인 전 계수·개발원본 해시·분석코드·입력·APK를 동결한다. 이후 관측 AP/전류/완료시간은 종단간 예측 입력에 넣지 않는다. 실제 일정 조건부 A와 예정 도착 종단간 B를 따로 계산한다. 부하 전 초기조건을 사용하는 조건부 세션 예측임을 밝힌다.
- 오차: 모든96요청 분모, nearest-rank P95와 마감완료율, dispatch/lane 오차, 전체 및 예측 이후 J 차이, 누적J, AP MAE/최대/최고오차. 두 확인의 정책차이와 세션 변동 폭을 나란히 표시한다. 임의 정확도 PASS/보편 오차한도/통계적 안정성 보장은 없다.

## 예약과 중단

개발3 + 확인6 = 9세션, runtime36, warmup72, 본864, 총936추론. staging9/63파일, 설치본pull 최대2(블록별1), APK push/설치 최대각1(개발만, 확인은 설치 불일치 중단). 재시도/대체/추가0.

고정관측 9×(baseline30+common120+cool60)=1890초. 블록 내 대기7×90=630초. 각 세션 stage/gate120 + poll485 + 회수50 + cleanup45=700초. 개발블록600+3×700+2×90=2880초; 확인블록600+6×700+5×90=5250초; PC추정/동결600초. 전체 예약8730초(2시간25분30초), 정상 소요 예상과 구분한다. 이전 실제 세션의 약230초/90초 간격 기준 대략45–55분이지만 환경/전송/실패에 따라 달라진다.

ADB: 세션별상한3200(기존 .25초 listing,2초 thermal,10초 screen와 gate/회수 예약 그대로) + 블록고정200; 개발9800+확인19400=29200. 총수와 각 세션 회수/정리100명령 예약을 함께 적용. APKpush120초/설치120초/설치본pull180초; 회수는 단일tar35초를 포함한50초이며 파일별 반복pull을 만들지 않는다. 설치/기기 gate 실패 시 본 작업 없음. 연결/품질/sampler/메모리/환경/시간 실패는 원래 오류와 후속 정리 오류를 별도 기록하고 해당 계획 종료. 원래 소유자의 앱 정리는1회, 외부 중복 복구 없음.

현재 기기 transport/fingerprint/하드웨어/설치본은 기존 실행기 안에서 확인한다. 비충전/BAT/thermal/화면/메모리/품질 gate를 바꾸지 않는다. numeric AP의 유효성과3초 신선도는 유지하며 개발 시작32.5°C 하한을 안전 gate로 재도입하지 않는다. 사용자 설정을 변경하지 않는다.

## 실행 중 확인된 결함과 후속04 경계

plan02는 설치 검증 후 첫 fingerprint client 실패(34명령,85.501초,앱 시작0), plan03은 CPU/병행 개발2 완료 후 직렬의 본96/공통120초 완료·냉각6.6초에서 중단했다. 세 번째 Activity는 `isChangingConfigurations=true`인 onPause→onStop→onDestroy 후 lifecycle_cancelled였고, host force-stop은 그 뒤다. 구체적 구성 변경/사용자 조작은 미확정이며 과거 같은 이름의 실패까지 원인 규명됐다고 하지 않는다.

새 `OnlinePolicyStudyActivity`만 orientation/screenSize/screenLayout/smallestScreenSize/uiMode callback을 같은 소유자에서 처리한다. 기존 Activity, 실제 onDestroy 취소, 명시적 종료, worker/runtime/sampler와 watchdog은 보존한다. [Android 구성 변경 계약](https://developer.android.com/guide/topics/resources/runtime-changes)에 따른 opt-in 처리이며 모든 구성 변경/프로세스 죽음을 견디는 구조가 아니다. 정적 계측 UI에는 방향별 가변 자원이 없고 callback은 식별·시각·구성을 기록한다. PC Robolectric 실제 configurationChange는 같은 인스턴스/단일 setup/미취소, 마지막 destroy는 취소를 확인했다. 실기기 안정성 보장은 아니다.

04는 **개발 첫2 원본 hash 고정 재사용 + 남은 직렬 개발1 + 확인6**이다. 실패 직렬은 계수 추정에서 제외하되 전체 시도 분모와 본96 소비는 보존한다. 성공2의 기존 APK와 새 callback APK 차이는 기록하고 계측 비용을 임의 보정하지 않는다. 과학적 계약/후보군/입력/판정은 유지한다. 재사용은 유리한 결과 선택이 아니라 사전 순서의 적격 완료 자료를 보존하는 것이다.

04 상한: 세션7,본672,warmup56,명시적728,runtime28,staging7/49파일,pull2,push·설치각1. 고정1470초,세션간450초,개발600+700=1300초,확인5250초,PC동결600초,합7150초. ADB3400+19400=22800. 종료된02/03을 재개하지 않고 새 ID/registry를 쓴다. 내부 재시도0이나 이번 작업의 이전 중단2는 별도 보고한다. 04 확인6을 마치면 개발3 기반 계수의 새 도착·정책 예측 오차와 실제 정책 상충을 판단하며, 부적격 자료/정확도 부족을 추가 후보 탐색으로 덮지 않는다.

기존 기록·모형·FAIL·strict·experiment_ready=false 보존. 04는 실제 Check 후 Run1회 실행했다. 새 직렬 개발이 정상 완료되어 기존 적격2와 지정 개발3을 구성했고, 2026-10-02T13:33:27.920464Z에 모형을 동결한 뒤 확인6에 진입했다. 현재 확인 진행 중이며 아직 완료 판정이 아니다.

### 04 동결 식별

- plan SHA `bd39f8e57bd23d738867dbe22c9c624e463ec2317c6341065c27a2069f3aa630`
- APK SHA `a9e2c3072f75f053b6d3f3edd6675442b0d061bd0f17005f7d789d44cc45e92b`, 기존 프로젝트 인증서 유지. 외부 `online_policy_study_build_v2/build_receipt.json`.
- 모형 SHA `557fbe5be8a9c9ba5f5911d44d1c19611710cbe5b80e015d1b965b777357bcf2`; 외부 `online_policy_study_run_v4/model_freeze.json`.
- 실행 소스102파일은 `online_policy_execution_source_v4`에 byte 보존. 이전02/03도 별도 보존.

### 예측 발행 시점과 정보 경계

확인 전 고정하는 것은 계수와 알고리즘이다. 현재 host는 세션 원자료 회수 뒤 지정된 부하 전 AP/전력만 추출하여 예정 도착 예측을 재생한다. 따라서 **실시간으로 부하 전에 발행한 예측**이 아니라, 미래 관측을 입력에서 제외한 동결 절차의 사후 계산이다. 예측 초기화 구간0–35초를 포함한 전체120초 J와, 초기 입력이 모두 끝난35–120초 J를 따로 보고한다. AP 점수는35초 이후 냉각 종료까지이며 센서 timestamp의 실제 첫·마지막을 표시한다. 실제 일정 조건부 A는 스케줄 예측 검증이 아니며 B의 dispatch/응답/lane 오차와 분리한다.

## 최종 결과 — 실측·독립 예측 평가 완료, 정밀 에너지 정책 선택은 미판정

새04의 개발1＋확인6은 모두 적격 완료했다. 기존03 적격 개발2를 연결해 지정 개발3→동결→확인6을 완성했지만, **한 번의 연속9세션 완주가 아니다.** 02 인프라 실패와03 냉각 취소는 계속 stopped_no_resume이며, 실패 직렬의 본96 소비도 지우지 않는다. 최종 `online_policy_study_run_v4/FINAL_RECEIPT.json`은 completed_development_and_confirmation, 정상 PS/Python exit0이다.

[실측·예측 대시보드](results/online_policy_study_01/run02/index.html), [정밀 지표](results/online_policy_study_01/run02/details/detailed_metrics.csv), [lane 그림](results/online_policy_study_01/run02/details/schedules.svg), [원래 고정 분석](results/online_policy_study_01/analysis_contract.json).

| 확인 | 정책 | 관측120초 J | 예정도착 예측−관측 J | AP MAE / 최대오차 °C | urgent P95 관측/예측 ms |
|---|---|---:|---:|---:|---:|
| 1 | CPU 직렬 | 179.930 | -0.291 | 0.152 / 0.813 | 436.6 / 365.5 |
| 2 | CG_DC 병행 | 168.817 | -13.158 | 0.302 / 0.760 | 291.1 / 271.0 |
| 3 | CG_DC 직렬 | 171.482 | -8.263 | 0.242 / 0.688 | 593.8 / 521.7 |
| 4 | CG_DC 직렬 | 171.859 | -15.941 | 0.605 / 1.236 | 606.1 / 521.7 |
| 5 | CG_DC 병행 | 171.567 | -10.385 | 0.160 / 0.733 | 315.5 / 271.0 |
| 6 | CPU 직렬 | 172.387 | -2.686 | 0.242 / 1.031 | 451.4 / 365.5 |

- 모든 확인에서 전체96/96가 완료·품질·urgent1.5초/normal6초 마감 기준을 충족했다. 독립 세션은 정책당2개이며 요청576개/AP335표본을 독립 반복576/335개로 세지 않는다. 예정도착 예측 dispatch MAE11.047–31.375ms, lane MAE15.029–38.533ms. 병행은 실제5.640791/5.508086초, 두 직렬 정책의 병행0이다.
- 예정도착 전력 오차는 −0.291…−15.941J(−0.162…−9.275%). 초기화 이후35–120초만 보면 −3.093…−14.813J이다. 실제 일정 조건부 계산에서도 −13.394/−8.279/−15.884/−10.469J 등의 비용 오차가 남으며, 두 예측의 J 차이는 최대0.674J다. 따라서 이 자료의 큰 J 오차를 일정 예측 실패 하나로 설명할 수 없다. 배경 전력의 조건 변화/정책 맥락 전용 한계를 가설로 남기고 외부 원인으로 확정하지 않는다.
- AP 예정도착 MAE0.152–0.605°C, 최대오차0.688–1.236°C; 실제 일정 조건부 MAE0.145–0.607°C. 점수는 각 세션의 실제35초 이후 첫 AP(35.870–36.577초)부터 마지막(177.945–179.861초)까지다. 모든 AP 결측을0으로 채우지 않았고 최대 관측 간격은 확인 중3.255초, 전류/전압 표본 최대간격1.052초다. 폴링 주기가 센서 내부 갱신 주기라는 주장은 아니다. 최고오차는 같은 AP 표본 시각에서 비교한 값이다.
- 개발 초기 AP29.6–30.0°C, 확인30.2–30.7°C, 확인 배터리51–55%, thermal0·비충전 조건이다. 이는 기존 시작32.5–34°C strict 범위를 바꾼 것이 아니며 새 후보/프로토콜의 독립 결과다. 첫 개발2 APK3aed…와 이후a9e…의 구성 처리 차이, 실행 공백·준비 이력·잔량 차이를 보존한다.

새 AP gain의 확인6 평균 MAE는0.283831°C, 이전 M0는0.291946°C다. 3세션은 좋아지고3세션은 나빠져 일관된 개선이라고 하지 않는다. 개발로 고른 gain을 확인 후 바꾸지 않았고 이전 M0도 기본/기존 지원 경로에서 보존했다.

### 정책 판단과 원래 목표의 완료 수준

1. 예정 도착→온라인 자원/직렬 대기→일정/응답→J/AP 계산과 새로운 실행의 비교를 실제로 연결했다. 기존 기록 일정 재생만 수행한 결과와 다르다. [동일 초기조건 세 정책 계산](results/online_policy_study_01/run02/details/same_initial_policy_predictions.csv)은 첫 CPU 확인의 부하 전 입력을 공통 사용한 **모형상 반사실 비교**이며 같은 초기조건의 실측쌍은 아니다. 모델 값을 정책의 검증된 절감으로 표시하지 않는다.
2. 병행 urgent P95는 두 순서에서 CPU보다145.538/135.951ms 짧았고, 직렬 CG_DC는157.226/154.636ms 길었다. 다만 세 정책 모두 이미 등록 마감을 충족했으므로 더 빠른 응답이 마감 달성에 필수였다고 하지는 않는다.
3. 병행−CPU 관측J 차이는 −11.112/−0.820J, CG_DC직렬−CPU는 −8.447/−0.528J였다. 두 순서에서 관측 순서는 같지만 CPU 두 세션 자체 차이는7.543J이고 초기 AP/배경 이력이 다르다. 에너지 예측 오차가 일부 정책 차이보다 크므로 **안정된 절감률·정밀 순위·정책 우월성은 미입증**이다. AP 최고 차이도 병행−CPU −0.2/−0.1°C, 직렬−CPU −0.2/+0.1°C로 모형 경로 오차보다 작아 열 우월성은 미판정이다.
4. 따라서 등록된 A24 혼합96요청·세 온라인 정책의 **실측 비교와 모형 오차 평가, 제한 시뮬레이션 구현은 완료**다. 정확한 에너지·열 비용을 근거로 작은 정책 차이를 자동 선택하는 목표까지 완료됐다고 하지 않는다. 일반 도착/미계측 backend/S26/열→처리시간/열 피드백 정책/SOC·BAT 온도·절대J 인증은 지원하지 않는다. 기존 default/strict/experiment_ready=false 유지, 새 후보는 explicit explore에만 연결했다.

### 오차 상쇄와 미완료 항목의 구체적 경계

첫 CPU 전체 J 오차 −0.291J는 고정5초 양의 잔차+8.373J와 음의 잔차−8.663J의 합이다. 전체값만으로 정밀성을 주장하지 않는다. 다른 확인의 에너지 오차에는 부하 구간의 지속적 과소예측도 있다. 사후 기술 분해35–90초 오차는 −2.673…−12.000J, 모든 작업이 끝난90–120초는 +0.432…−5.203J였다. 분해는 산술적 설명이며 원인 식별/새 모델 선택이 아니다. [고정5초 전체 표](results/online_policy_study_01/run02/details/energy_windows.csv)의 혼합 상태를 독립 병행 전력으로 해석하지 않는다.

에너지 계수 행렬은 수치rank4이고 singular values23.2601/2.2511/1.7498/0.4146이나, 이것은 조건 간 전용 정확도/물리 계수의 정밀 식별 보장이 아니다. 확인의 비용 오차는 그대로 실패 근거로 남겼고 계수 재적합·후보군 추가·유리한 확인 제외0이다. 이번 뒤에 같은6세션을 자동 반복하지 않는다. 남은 구체적 PC 질문은 **고정 부하 증가분과 부하 전 배경 전력의 합으로 충분한지, 기존9세션에서 전력 잔차가 어떤 상태/이력에 묶이는지**이며, 추가 실측부터 요구하는 포괄 감사로 되돌리지 않는다.

### 소비·종료·증거

| 구분 | 실제 | 새04 상한 |
|---|---:|---:|
| 새 세션 | 개발1＋확인6=7 | 7 |
| 본 시작/반환/저장/lane 해제 | 각각672 | 672 |
| warmup 시작/반환 | 각각56 | 56 |
| 총 명시적 추론 | 728 | 728 |
| runtime 생성/반환 | 각각28 | 28 |
| staging | 7회·49파일 | 7회·49파일 |
| 설치본 pull | 2 | 2 |
| APK push/설치 | 각각1 | 각각1 |
| ADB | 5,836 | 22,800 |
| 전체 실행·동결·회수·종료 | 2,235.496초 | 7,150초 |

고정관측1470초와 실제전체2235.496초를 구분한다. 앱 cleanup7 정상·세션별 host 정리7·설치 정리1, 마지막 계획내 ps에서 대상 부재, 원 parent/child 생성시각·명령 기준 exited. 22건의 ADB exit1은 모두 `test -e`에서 신규 경로 부재를 확인하는 예정 응답이며 timeout/연결 실패가 아니다. 구성 callback 실제 발생0: 이번 정상 완료가 실제 구성 변경 내성까지 실기기 검증한 것은 아니다.

이번 작업 전체02/03/04를 합치면 **ADB7,762·본960＋warmup80=1,040추론·runtime40·staging10/70·설치본pull4·APK push/설치각2**다. 이 중 냉각 실패1세션의104추론도 포함된다. 종료된 계획을 재개한 것은 아니며 실패 복구 후 새 ID 두 번의 이력이 있다. 이전 실패0으로 꾸미지 않는다. 전체 계획 실행시간 합계3198.508초는 PC 수정·빌드·대기 공백을 제외한 값이다.

원본: 외부 `online_policy_study_run_v2`, `online_policy_study_run_v3`, `online_policy_study_run_v4` 각각 FINAL_RECEIPT/host_commands/artifacts/host_checkpoints. 완료04 receipt SHA `df1929c5520d4bd73573aa89041ab59b8e68f205e2ae6eeb06adf721d2d6be50`. PC 회수 inventory·소비 판독·재현 출력은 `online_policy_finish_pc_v4`. 04 원본 inventory는31,179파일/284,211,948bytes, SHA `3d2ca47f616f571cf04f4f046ed08d6b3e868fa62897dfe1fae7df64697338e8`이다. 모든 원본/기존M0·옛W freeze는 보존한다.

### 재현·검증

```powershell
python -B -m tools.d1_simulator online-policy --case-id confirmation_0_CPU_URGENT_ONLINE_V1 --policy B2_PARALLEL_ONLINE_V1 --output output/online_parallel_fresh
python -B -m tools.d1_online_policy_readout export --root C:/Users/LG/Documents/D1Check_Arrival_Extension/online_policy_study_run_v4 --output output/online_readout_fresh
python -B -m tools.d1_online_policy_summary --bundle output/online_readout_fresh --output output/online_details_fresh
python -B -m unittest tools.test_d1_online_policy_study tools.test_d1_policy_prediction_bridge tools.test_d1_simulator tools.test_d1_recorded_policy_comparison tools.test_d1_online_policy_summary -q
```

첫 명령은 저장소 작은 공유 입력만 사용한다. export는 정확한 원본04의 model_freeze, development/confirmation_cases와 development/confirmation_evaluation JSON이 필요하다. 실제 실행 소스의 byte 재현은 외부 `online_policy_execution_source_v4`의102파일을 사용한다. 종료된 Run을 재호출하지 않는다.

최종 관련 Python33검사/Android13 callback·정책·기존 계약 검사, 프로젝트 서명 빌드, 실제PS Check(기기0), 실제Run, 공유CLI 수치 재현 및 strict 차단, 전체/부분 적분합·9개곡선/CSV·lane 그림 확인을 완료했다. 소스 검증 대상은 HEAD87122dd의 이번 미커밋 변경이며 code/build/plan/freeze hash로 고정했다. 최종 Git commit은 이 변경과 작은 결과만 포함하며 APK·키·모델 바이너리·원자료는 제외한다. 후처리 기기 명령0, 새 실측 추가0.

Git 줄끝 변환으로 동결 소스 해시가 달라지지 않도록 실행 의존102파일의 checkout bytes를 대조했다. 혼합 줄끝8파일은 작업 파일을 다시 쓰지 않고 원래 bytes를 Git에 보존했으며, 정규화 후 기존 HEAD와 같은 내용임을 확인했다. 실행 의미나 추가 빌드는 바꾸지 않았다. SVG 생성기의 줄끝 공백만 제거했고 수치와 좌표는 유지했다.


## 전력 오차 후속: 동기화된 표본 시점의 영향 분리

기존9세션의 수치 판독을 다시 수행했다. 개발35–80초 전력45표본은2초 반복 부하의8등분 중2구간에 집중됐다. 확인은2.2초 반복과1초 계측이 어긋나8구간을 모두 관측했다. 이는 **조회 시점 집중의 확정 관측**이며 센서 내부 갱신 주기, aliasing 오차 크기, 전력 과소예측 원인의 확정은 아니다. 기존 snapshot은1초 고정 주기로 읽고 원래 시각으로 적분했다. 적분창 이동이나 실제 전류를 예측 입력에 넣는 수정은 하지 않았다.

네 증가분의 개발행렬 rank4/condition 약56.1은 수치 식별만 뜻한다. CPU 또는 병행 세션을 하나 제외하면 rank3이며, 직렬 제외 시 rank4라도 분류CPU 증가분2.701→5.014W, 병행0.392→1.555W로 바뀐다. 이 값은 사후 민감도이며 새 후보로 채택하지 않는다. 세션 전 배경W가 부하 뒤 같다는 가정도 관측으로 보장되지 않는다. charge counter의 최소 관측 변화4,000raw를 명목uAh로 해석하면 약55.4–56.2J 단계다. 해당 gauge 역시 절대교정되지 않았고, 작은 정책 차이를 확인할 독립 기준으로 사용할 수 없다.

[위상 그림](results/online_policy_study_01/power_diagnosis_v1/sample_phases.svg), [세션 표](results/online_policy_study_01/power_diagnosis_v1/cases.csv), [구간 전력](results/online_policy_study_01/power_diagnosis_v1/windows.csv), [민감도·원본 해시](results/online_policy_study_01/power_diagnosis_v1/diagnosis.json).

### 실행 전에 고정한 계측 대조

같은 APK/resident/병행정책/96요청·500ms 간격·기본환경을 유지하고 전력조회만1,000→900→900→1,000ms로 설정한다. 세션당 baseline30＋common120＋cooling60초, 사이90초 유휴다. 새 opt-in 버전 `online-power-phase-audit-v1`; 기존 모드는1초 그대로다. 두 AB/BA 대비와 같은주기 반복 차이를 함께 보고한다. 결과를 보고 후보를 추가하거나 원래 동결값을 수정하지 않는다. 900ms 자체 추가조회/쓰기 비용과 세션 배경·이력을 완전히 분리하는 설계는 아니므로, 에너지 차이를 모두 aliasing 보정값으로 간주하지 않는다. 이 네 세션은 모형 독립 정확도 확인이 아니다.

APK SHA `7e91b4a3126f0f31328ebfd67ce21e11796a92669d3df7bab20e3aa5ca1c55a7`, 기존 프로젝트 서명/패키지 유지. 외부 `online_sampling_build_v1/build_receipt.json`과 `online_power_sampling_source_v1/identity.json`104파일로 출처를 보존했다. 계획 SHA `d7e962eea85ed50d491630ff1f3162e458f3fd53d1b304ace8c75a7d58be3c6b`. 상한4세션/본384/warmup32/합416/runtime16/staging4·28/pull1/push·설치각1/ADB13000. 총3670초는 preflight600＋4×세션예약700＋3×유휴90이며, 고정관측840초와 구분한다. 실패 후 해당 계획 재시도0. 기존 하드타임아웃·회수50·cleanup45초/명령100예약을 유지한다.

Python11검사, Android7(정책3/lifecycle4), 실제PS Check/실제ADB 호출 차단Check를 통과했다. 첫 Android 명령은 `-PenableModelProbe=true` 누락으로 task-not-found였고 테스트 본문 미실행이었다. 기존 옵션을 바로잡은 두 번째 명령으로 실제7건을 실행했다. 프로젝트 서명 빌드 성공, 설정/환경 기준 변경0. 이는 장시간 기기 안정성 보장이 아니다.

```powershell
python -B -m tools.d1_online_power_diagnosis --root C:/Users/LG/Documents/D1Check_Arrival_Extension/online_policy_study_run_v4 --output output/power_diagnosis_fresh
python -B -m unittest tools.test_d1_online_sampling_study tools.test_d1_online_policy_study -q
```


### 2026-10-03 냉각 관측 timeout과 남은 두 세션

첫 묶음은2세션 적격 완료 뒤3번째 냉각의 `dumpsys thermalservice`2초 client timeout으로 중단됐다. 명령2462는2.009917초/출력0bytes/exit1이며, 연결 단절·기기 정지·GPU 오류의 증거가 아니다. 다음 manifest 회수는5.127초에 성공했고 계획상 부분 회수와 force-stop1회, 대상ps 부재·thermal0 확인이 이어졌다. 앱 cleanup은 회수되지 않아 미확인이다. 본 요청96개의 시작/반환/output/persist/worker/lane와 common120초 경계는 해당 부분 기록에 존재하지만 cooling 종료/정상cleanup까지 완료한 적격 세션으로 승격하지 않는다.

원래 plan_v1은 `stopped_no_resume`다. 실제962.876757초/ADB2473/launch3/runtime12/warmup24/본288=총312추론,staging3·21/pull1/push·설치각1. 첫2세션의 정상 앱cleanup/회수/host정리, 실패3번째의 host종료는 분리한다. 네 번째는 미시도다. 원본 `online_power_sampling_run_v1/FINAL_RECEIPT.json`과 failure_prefix를 유지한다.

사용자의 자율적인 실패 복구·후속 실측 승인에 따라 완료2개는412파일 해시로 재사용하고, 미완료900ms와 미시도1000ms만 별도 plan_v2에 고정했다. 계측·timeout·환경 gate·APK 변경0, 기존 실패 계획 재실행0이다. 새 두 세션의 최대192본＋16warmup=208추론/runtime8/staging2·14/pull1/push·설치0/고정420초/ADB6600/상한2090초(600＋2×700＋90)이며 내부재시도0. APK를 다시 빌드하지 않았다.

계획 SHA `af6ff98a41fa746457ba3dc7eeaa2ce5d806717a54b2340b377eeca1941a689b`, `online_power_sampling_plan_v2/collection_plan.json`, 원본 `online_power_sampling_run_v2`. 실제PS Check 통과 후 Run1회. 예산/설치금지/두주기순서/원래 적격자료 해시를 확인했고 새소스104파일을 `online_power_sampling_source_v2`에 보존했다. 이는 원래4세션 계획의 연속 완주가 아니며, 두 실행 사이의 준비시간·환경·이력 차이가 추가된 별도block이다. 실패의96요청도 전체 소비와 실패 분모에 남긴다.


### 후속 완료·전력 입력 가정의 남은 문제

후속02는2/2세션 정상 완료(597.785269초/ADB1671/본192/warmup16/runtime8/staging2·14/pull1/배포0)했다. 앱cleanup2·회수2·host정리2·마지막대상ps 부재다. 두 실행 합계 실제5시도/적격4/냉각중단1, 본480＋warmup40=520추론/ADB4144/작업1560.662초(PC 공백 제외). 시작/반환/output/persist/worker/lane는480개 모두 확인됐다. 앱cleanup은4정상/중단1미회수이며 미회수와 실패를 같은 의미로 쓰지 않는다. 첫실행 명령2462 단일timeout 외의 exit1은6개 경로 부재 확인이다.

|순서·계측|관측120초 J|기존식−관측 J|AP MAE °C|최대 AP 오차 °C|시작 AP °C|
|---|---:|---:|---:|---:|---:|
|첫block1000ms|173.814325|+0.007760|0.337516|1.009786|29.4|
|첫block900ms|169.614304|+5.802522|0.240457|0.995047|29.6|
|후속block900ms|170.846155|−17.871248|0.191953|0.924580|30.0|
|후속block1000ms|170.545659|−12.714599|0.756355|1.183990|30.1|

900ms는각133표본/8위상,1000ms는각120표본/2위상이었다. 실제병행6.292–6.567초. 두 대비900−1000은−4.200020/+0.300496J로 불일치하며, 같은주기 반복 차이는1000ms−3.268666J/900ms+1.231851J다. 배경을뺀35–120초 차이도−4.909517/+1.580628J로 바뀐다. 단일 원인이나 일정한 보정값을 뒷받침하지 않는다.900ms의 센서읽기 경과8.326/8.438초 대1000ms7.309/7.565초는 추가측정시간 기록이며 CPU사용/에너지 비용으로 바꾸지 않는다.

관측총J의 범위4.200J보다, 부하전20초의 W범위1.053847–1.240496을120초에 고정 적용한 변동22.398J가 크다. 따라서 위상집중을 완화해도 세션마다 짧게 관측한 배경W를 전체창에 전용하는 가정이 남는다. **전체 목표 미완료**이며 원래 독립확인 오류와 이번 전이 오류를 모두 보존한다. 다음PC 보완은 pooled resident 항 하나로 세션별20초입력을 대체하는 최소후보의 식별성/사후 평가다. 기존13적격을 이용하면 그 자료는 새후보의 개발/사후평가이며 독립확인이 아니다. 이번에는 새계수 채택0/원래동결불변이다.

[최종그림/CSV/재현](results/online_policy_study_01/sampling_run01_complete/index.html). 후속receipt SHA `a341cc286c798b9e7f408322556f8e082f1fa26cd45c48296c6320c3bab3f956`, 첫실패receipt `d9a715b2ddc2bf4ec7b5d94480bbf1932555e95f79d27ff85c2c811ab511ca28`. PC 후처리 cp949 읽기오류를 UTF-8명시로 수정하고 새출력에서 재현했다. 수치·적분창·계수 수정은 없고 Python12/Android7검사, 실제 APK/두Check/두Run 경계를 구분한다. 시각자료는새 적격4만 표시하고 중단1을 정상으로 채우지 않았다.

## 2026-10-03 최소 배경 전력 후보 판독 완료

기존 적격13세션(개발3·이미 본 확인6·계측대조4)으로 사전등록한 pooled resident 후보 하나를 평가했다. 새 독립 확인이 아니다. AP·처리시간 항과 기존 동결본은 변경하지 않았다. 5초 창·정책별 동일 가중·세션 전체 제외 평가를 사용했으며 모든 식별 행렬은 rank5였다.

- 120초 에너지 평균 절대차: 기존7.117586J → 후보 세션제외5.307220J.
- 최대 절대차: 기존17.871248J → 후보19.447192J. 사전 조건인 최대오차 비악화를 위반했으므로 **미채택·추가 확인 실측으로 진행하지 않음**이다. 기준을 결과에 맞춰 바꾸지 않는다.
- 가장 큰 후보 오차는 기존 개발 병행 세션이다. 관측150.175774J 대비 후보169.622966J이며 기존식150.426768J였다. 이 세션을 제거하거나 잘못된 자료로 단정하지 않는다. 세션 간 배경·계측 프로토콜·이력 차이를 일정한 배경항 하나로 설명할 수 있다는 근거가 부족하다. 행렬 rank는 물리 계수의 안정성이나 원인 식별을 뜻하지 않는다.
- 후보의 전체자료 적합 resident는1.116311837W다. 이 값은 주변조건과 무관한 물리 유휴 전력으로 인증된 것이 아니다. 후보JSON의 확인 pending 범위 표시는 가능 범위 메타데이터이며 실제 실행 결정은 summary의 advance=false가 우선한다.

**지금 사용 가능한 범위:** 기존 등록96요청·세 정책의 일정/응답 예측과 조건부 AP 경로 및 관측 정책 비교는 재현 가능하다. 작은 에너지 차이나 AP 최고값 차이의 우열은 미판정이다. 후보 실패를 열 모형 전체 부재나 원래 목표 불가능으로 확대하지 않는다. 기존 strict/default/experiment_ready=false 유지.

**다음 작업 하나:** 고정된24분류/72탐지 혼합에서 각 상태 점유의 식별 기여를 산출하여, 동일 세션 단순 반복 대신 CPU 분류·GPU 분류·실제 병행을 구분할 최소 입력의 필요 여부를 결정한다. 추가 모형 가족 탐색이나 이 후보의 즉시 재확인은 하지 않는다.

재현(외부 원본 필요, 출력은 새 경로):
```powershell
python -B -m tools.d1_pooled_energy_candidate --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/pooled_candidate_fresh
python -B -m tools.d1_pooled_energy_candidate --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/pooled_candidate_fresh --render-existing --share output/pooled_candidate_share
python -B -m unittest tools.test_d1_pooled_energy_candidate tools.test_d1_online_policy_study -q
```

외부 의존: online_policy_study_run_v4의 model_freeze/development_cases/confirmation_cases, online_power_sampling_plan_v2 및 해시 결속된 첫2·후속2 세션의 validated/thermal/artifacts. 원본 경로·해시 상세는 외부 pooled_energy_candidate_pc_v1/source_inventory.json에 보존한다. 개발·확인 모두 이미 본 자료라는 사실을 CSV에 기록했다. 세션제외 평가는 새로운 독립 확인이 아니다.

검증: 후보2+기존 경계8=10건 통과(실제9.486초), 분석13세션/39행, 동결557fbe 불변, 기존 AP/처리시간 항 불변. 본 PC 후보 단계 기기 명령·추론·APK·새 계획·claim0. 직전 실측의520추론/4144명령은 삭제하거나0으로 바꾸지 않는다.

[후보 화면/CSV](results/online_policy_study_01/pooled_candidate_v1/index.html)

## 2026-10-03 실제 점유 식별력: 기존 장구간 원본을 먼저 재사용

새 계수 적합이나 기기 명령 없이 기존 온라인13세션(312개5초창)과 COLLECT-05 개발3세션의 원본을 대조했다. 옛 manifest/progress/thermal은 동결본에 결속된9해시와 일치했다. 원본/동결본 변경0.

|계산|온라인13|기존 장구간3 중 현재 지원 상태 창|
|---|---:|---:|
|5초 창 수|312|272 (미지원 탐지GPU 포함88창 별도 제외표)|
|배경+4상태 rank|5|5|
|비정규화 설계 조건수|119.523|6.371|
|분류CPU 계수의 단위 L2 에너지 교란 민감도|1.078707/s|0.075044/s|
|탐지CPU|0.090477/s|0.036702/s|
|분류GPU|0.551768/s|0.049577/s|
|분류GPU+탐지CPU|0.526540/s|0.043793/s|

이는 동일 단위/5초 창의 선형 설계 기하이며 실제 잡음 분포·정확도·신뢰구간을 추정한 표가 아니다. 창 수가 다른 효과도 포함한다. 온라인 분류CPU는 탐지CPU보다 약11.9배 민감하고, 세션별 배경을 제거한 설계에서도1.141425/0.090618≈12.6배다. 배경만 제거하면 해결되는 문제가 아니다.

온라인13의 실제 총점유는 분류CPU11.789867초, 분류GPU25.199561초, 병행43.294553초, 탐지CPU543.256042초다. 각 연속상태 최대는0.185/0.340/0.399/0.673초이며1초 이상 구간0이다. 원래 occupancy 구현은 인접 동일 상태를 합친다. 짧은 개별 전력을 직접 식별했다고 할 수 없지만, 이 사실이120초 전체 적분 또는 구간 노출 회귀를 자동 금지하지는 않는다.

기존 `d1_energy_state_collection.freeze`는 block의 J/covered_s를 상태 이름별로 합산했다. 이는250ms 반복 제출·빈틈·실제 병행 비율을 포함한 **regimen 평균전력**이다. 순간 dispatch→lane_available 점유의 계수로 그대로 쓰면 의미가 달라진다. 이번에는 옛 요청 lane 경계로5초별 실제 점유를 재구성했으며 탐지GPU가 포함된 창은 제외표에 남겼다. 부분272창을 전체600초 에너지로 표시하지 않았다. AP·전력 계수·지원 범위는 수정하지 않았다.

**결정:** 상태 계수를 구분하기 위한 장구간 실측을 지금 추가할 필요는 입증되지 않았다. 기존 원본에 해당 정보가 존재한다. 다음 작업은 이272창의 실제 점유와 동일창 전류·전압 적분을 연결한 장구간 개발자료 기반 전력 추정/프로토콜 전이 평가다. 기존 온라인13개는 이미 본 사후 평가로 고정하고 이 결과를 새로운 독립 확인이라 부르지 않는다. 다른 초기온도/APK/센서·host조회 차이 때문에 전이 성공은 아직 미확인이다. 데이터 처리 경계를 먼저 고정하고 계수나 입력을 여러 번 바꾸어 가장 좋은 결과를 고르지 않는다.

기존5계수 pooled 후보의 advance=false를 번복하지 않는다. 새 실제점유 추정은 자료 의미가 다른 장구간 원본을 재사용하는 별도 근거 작업이며 아직 후보 채택·추가 실측·새 실행계획0이다. AP와 서비스/정책 비교 구현, 기본/strict/experiment_ready=false는 그대로다.

```powershell
python -B -m tools.d1_energy_identifiability --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/online_geometry_fresh
python -B -m tools.d1_energy_identifiability --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/legacy_geometry_fresh --legacy
python -B -m unittest tools.test_d1_energy_identifiability -q
```

단위·공선·결측상태 검사2건 통과. 실제13+3 원본 경계 실행 및 해시 확인을 별도로 수행했다. 기기 명령·APK·새 계획·claim0. 실제 정확도 검증과 PC 기하 계산은 다르다.

[식별력 화면](results/online_policy_study_01/identifiability_v1/index.html)
