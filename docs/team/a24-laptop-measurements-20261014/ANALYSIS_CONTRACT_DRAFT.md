# A24 분석 계약 초안과 GEN002 적용 경계

2026-10-15. **분석 방법을 정리한 PC 초안이며 최종 동결 계약이나 실행 분석 코드가 아니다.** [기계 판독 초안](ANALYSIS_CONTRACT_DRAFT.json)의 `frozen=false`를 유지한다. 새 예측·시뮬레이션·학습·기기 명령·추론·계측·START/claim·실측 세션 소비는 모두 0이다. 기존 데스크톱 실행과 EP814를 재시작하지 않았다.

## 받은 자료가 의미하는 것

원격 전달 commit은 `ec8a1424f9326bae80486e9182fc81e88ae318a1`이다. [전달 README](desktop-reference/README.md), [가용성](desktop-reference/AVAILABILITY.json), [GEN002 등록](desktop-reference/GEN002.json), [분석 상태](desktop-reference/ANALYSIS_CONTRACT_STATUS.json)를 읽고 원 소스·프로필을 텍스트/JSON으로 확인했다. 원 코드를 import하거나 실행하지 않았다.

GEN002는 기존 동결 소스 59개와 프로필 8개를 식별한다. 그중 A24의 4층은 보존된 참고 자료이며 새 8군의 완성 예측 모형, 수치 예측표, 최종 선정 PPO, 독립 실기기 확인의 완료를 뜻하지 않는다. A24 계획 참조인 `M1_coupled`의 SHA는 `ee36899cc7c5ea17a689bbd746e8906866e846ceb0e68685d8faa17b20009df3`이다. `hardware_validated=false`, `strict_eligible=false`, `experiment_ready=false`를 그대로 해석한다.

이번 노트북의 실측 준비 버전은 `plan_v3`의 64 미소비 슬롯, 26 bank, 총 8,832 예정 요청과 `bound_v2`다. 계획 SHA는 `82d5108db8d44fc6785cbdc99f71baee01361e21abdd4c59df9544826cb93855`, APK SHA는 `32c42c32fb4ada08a811c82ee867875bd848fa6989f4cba13339c40d9568e9ef`다. 승인된 한 장의 이미지를 반복하는 범위를 유지하며 도착식·납기·작업량·bank SHA를 유리한 결과에 맞춰 바꾸지 않는다. 기존 원 PLAN의 SHA `29bbbdc882d273ddec769f748f86907866bb186423643d6f2546bbac55720225`를 근거로 한다.

64세션의 시각0 이후 관측은 `64×210초=224분`이다. 사이63구간에90초를 단순 예약하면 총318.5분(약5시간19분)이지만 매번 post-ready AP 최소60초 이력, 설치·워밍업·회수·초기 gate 대기는 별도다. 실제 작업이5시간19분에 끝난다고 보장하지 않는다. I4/F4/DEV16/CONFIRM40과 재시도0을 유지하며 추가 PC 예측 예산도 새로 소비하지 않는다.

## 그대로 예측기로 사용할 수 없는 이유

| 비교 항목 | GEN002에 있는 것 | 이번 계약에 필요한 연결 |
| --- | --- | --- |
| 실행 조합 | 분류 CPU·분류 GPU·탐지 CPU의 5단계 시간 anchor와 CG_DC 비용 항 | 새 APK·입력·runtime·위임·품질과 원 anchor의 동일성 검증. 3개 cell이 있다는 사실만으로 새 실행 경로가 검증되지는 않음 |
| 요청 선택 | 기존 ATC/EDD 후보·학습용 controller | strict FIFO head 차단/EDD 동점·전역직렬·동일순서 PAIR를 직접 실행·검산하는 별도 adapter |
| WAIT | `plant.py`에서 도착·상태 변화가 선택된 WAIT를 중단할 수 있음 | 새 도착이 취소/연장하지 않는 묶음별 WAIT200, 실제 idle owner, 16회·명목3.2초와 실제 timer 초과 기록 |
| 완료와 해제 | 기존 5phase의 persist·worker release·AVAILABLE | D의 write→flush→fsync→rename→readback 성공 시각과 추가 비용 연결. 미측정 readback 비용을 0으로 넣지 않음 |
| 미완료 비용 | 완주와 cooling 조건에 따라 J180·AP가 null이 되는 경로 | 완주 여부와 별개로 실제 공통창의 관측 소비·열을 보존하고 서비스 손해를 병기하는 경로 |
| 초기 상태 | 과거 AP pre 이력에서 가져온 background, 기존 baseline/초기 열 상태 | 새 runtime 상주·워밍업 뒤의 AP 이력·시각 원점·충전/화면·전력 baseline·느린 잔열 조건 |
| 열·속도 회복 | M1 실현 속도 feedback과 정책의 예상 비용 파라미터가 구분됨 | 가정층을 실측 효과로 승격하지 않음. 새 기기에서 냉각에 따른 처리율 회복을 검증했다고 말할 근거 없음 |
| 관측 | 합성 2초 온도·0.9초 전력 관측, SKIN placeholder | 실제 HAL 센서명/종류/단위/읽기 시각/cache와 측정 부하 확인. AP를 표면·배터리 온도로 대체하지 않음 |

근거는 [plant.py](desktop-reference/model/code/plant.py)의 WAIT 종료 및 completed-only 비용 경로, [grounded36 물리 경로](desktop-reference/model/vendor/tools/d1_grounded36.py)의 초기 background·비용·속도 구분, [A24 M1 프로필](desktop-reference/model/vendor/profiles/A24_G36_M1_coupled.json)의 evidence/observation 항목이다. 원 프로필의 과거 오차를 이번 8군의 독립 검증 오차나 허용치로 전용하지 않는다. 평균 시간의 단순 합이나 다른 workload 결과를 새 J/AP/납기 예측표로 채우지 않았다.

## 관측창·분모·완료 경계

공통 시각 0은 runtime·워밍업 뒤 실제 post-ready 초기 gate를 통과한 `common_start.origin_ns`다. 본 요청은 기존 bank대로 35초부터 도착한다. 서비스는 0~120초, 총 기기 소비는 J0~120/J0~180, 평균 AP는 35~180초이며 센서는 최소 210초까지 기록한다. 120초부터 새 dispatch를 금지하고 이미 시작한 작업은 비선점으로 실제 AVAILABLE까지 기록한다.

긴급 C의 응답은 표시 가능한 결과 객체가 준비된 `output_ready`, 일반 D는 저장·동기화·원자 rename 뒤 `persist_readback.completed_ns`다. 이 시각과 worker release/AVAILABLE을 바꾸어 쓰지 않는다. 예정 도착부터 응답까지를 계산하며 actual arrival/enqueue 지연은 별도 열로 보고한다.

각 과업의 **전체 예정 요청을 분모로 유지**한다. 실패·거절·미배정·미완료를 삭제하지 않는다. 120초에 기한이 이미 지난 미완료와 아직 기한이 남은 pending을 나누며 pending을 실패나 성공으로 단정하지 않는다. 120초 이후 drain에서 완료했으면 원래 기한에 대한 on-time/late도 따로 보존하지만 주 서비스창 성공으로 바꾸지 않는다. 요청이 없는 과업의 비율은 null/해당 없음이다.

초안의 주 긴급 P95는 120초 안에 성공 응답한 요청의 예정 도착 기준 nearest-rank P95이며, 전체 분모의 성공·실패·pending을 함께 보여준다. drain 포함 P95는 보조 열이다. 기존 host의 `completed_only` 집계에는 drain이 포함되므로 그 필드를 그대로 주 서비스창 P95라고 재명명하지 않는다. 실패 중 응답 준비 시각이 남았으면 경계 증거와 실패 사유를 함께 보존하며 자료/품질 적격성을 별도로 판단한다.

70·80·90·95·100% 서비스 단계와 전량 완료 여부를 모두 보고한다. 새 사용자 SLA나 채택할 서비스 단계를 임의로 만들지 않는다. 최종 주 채택 기준은 아직 null이며 CONFIRM 전에 정할 사항이다.

## 같은 블록의 다섯 짝 비교

| 비교 | 처치 − 기준 | 바꾸는 요소 |
| --- | --- | --- |
| 저부하 병행 | L64 PAIR_G − BASE | 병행 허용 |
| 분류 자원 | C252 GPU − CPU | CPU/GPU 경로 |
| 혼합 순서 | M128 ORDER − BASE | FIFO/EDD |
| 혼합 병행 | M128 PAIR_G − BASE | 병행 허용 |
| 혼합 대기 | M128 WAIT200 − BASE | 고정 대기 dose |

각 비교는 CONFIRM의 독립 5블록에서 5개 대응 차이를 낸다. DEV2블록은 점검·동결 준비 자료이며 CONFIRM에 합쳐 반복 수를 늘리지 않는다. 요청 수·센서 표본 수·학습 seed를 독립 반복으로 세지 않는다. L64에서 실제 겹침이 없으면 zero treatment로 표시한다. 경로·순서·WAIT 처방이 달라졌으면 전체 서비스 결과는 남기되 순수 요인 효과로 해석하지 않는다.

J는 J, AP는 ℃, 응답은 ms, 서비스는 건수와 %p로 비교한다. 음의 ΔJ/ΔAP는 비용 감소이며 서비스 성공 증가가 양수다. 모든 쌍의 서비스 손해·결측 사유를 먼저 보여주고, 같은 완료·서비스 조건과 해당 창의 계측 완전성을 충족한 공통쌍에서만 조건부 비용 차이를 해석한다. 미완료 작업의 작은 관측 J를 전량 작업의 절감이라고 부르지 않는다.

## 불확실성 방법의 제안

모든 블록 차이, 평균·중앙값·최소/최대와 적격 쌍 수를 공개한다. 구간은 **블록별 대응 차이의 양측 95% Student-t 구간**을 초안으로 제안한다: `mean(d) ± t(0.975,n−1) × sample_sd(d)/sqrt(n)`. 5쌍이 유효하면 자유도는 4다. 분산은 실제 블록 자료에서 계산하며 임의 값을 넣지 않는다. 고정 구현·의존성과 최종 방법은 아직 동결하지 않았다.

5블록으로 차이의 정규성·모집단 대표성을 입증할 수 없다. 따라서 탐색적 구간으로 표시하고 모든 원 차이를 함께 보여준다. 결측은 보간·추가 실측으로 메우지 않으며 endpoint별 n과 제외 이유를 남긴다. 구간이 0을 포함하면 방향 미확정이다. 다섯 비교와 여러 지표의 미보정 구간만으로 전체 스케줄러 우월성이나 사후 최상 군을 확정하지 않는다. 기존 GEN002의 case-cluster bootstrap을 새 휴대폰 5블록 구간으로 재사용하지 않는다.

## 비용·열의 아직 정하지 않은 부분

AP 센서명/종류, Tref 또는 날짜별 baseline 알고리즘, 전류 API·전압·전하 단위 확인, 샘플링 주기·시각 정렬·최대 gap·적분법·경계 보간 허용치·계측 정확도·모형 정확도 PASS 허용치는 아직 null이다. AP 기준 초과 온도도 임의로 만들지 않았다. 실제 표본이 J0/120/180·AP35/180 양쪽을 덮고 동결한 gap 안에 있을 때만 완전창 지표를 계산한다. 조건을 만족하지 못하면 해당 지표는 null이며 tail 외삽으로 채우지 않는다.

HAL timestamp/cache age가 없으면 null로 남긴다. polling 기록을 새로운 독립 갱신으로 세지 않는다. 같은 gauge의 전류와 charge counter도 독립 정답이 아니다. 과거 모형 MAE·가정층 변동이나 APK mock PASS를 새 실기기 오차 허용치로 승격하지 않는다.

## CONFIRM 전에 닫을 체크리스트

1. I4→F4→DEV16의 모든 시도·실패·미지원 기록을 보존한다. 슬롯 교체·자동 재시도·추가 후속 모듈을 64세션에 숨겨 넣지 않는다.
2. 새로운 기기 등록·APK/runtime 위임·입력/tensor·품질·초기 gate·상주4runtime/워밍업을 확인하고 정확 SHA로 묶는다. 현재는 DEVICE_UNVERIFIED다.
3. 계측·초기 조건·분모/응답 경계·분석 구현·의존성·불확실성 방법·서비스 단계·정확도 기준을 독립 확인 전에 동결한다.
4. 모형 검증을 할 경우에만 별도 adapter ID/초기 상태 대응/의존성/제한된 PC 예측 예산을 먼저 등록한다. 현 단계는 예측 실행 권한·예산을 소비하지 않는다.
5. 요청별 응답/AVAILABLE·실패/pending, J120/J180, AP 경로/평균/peak/AP180, 다섯 대응 Δ와 순서/배정/겹침/WAIT 예측을 계산했다면 결과를 CONFIRM 전에 코드·profile·bank SHA와 함께 봉인한다. 현재 이 수치 파일은 없다.
6. 예측을 만들지 못하면 `NOT_CREATED/NO_MODEL_ACCURACY_CLAIM` 상태 파일을 별도로 봉인하고 그 SHA로 없음을 기록한다. 수치 예측 성공의 SHA로 표시하지 않으며 실측 요인 비교와 모형 검증의 주장을 분리한다. 정확도 기준이 없으면 오차·결측·방향만 보고하며 numerical PASS를 선언하지 않는다.
7. I/F/DEV 원장, 최종 분석 계약, 예측 또는 명시적 없음, 모든 입력/기기/source SHA와 봉인 시각을 기록한 뒤 새 확인40슬롯만 수행한다. CONFIRM으로 재튜닝·재선정·유리한 반복 추가를 하지 않는다.

이 초안 작성으로 기존 GEN002·데스크톱 학습·FINAL·checkpoint·물리 계수가 바뀌지 않는다. 원 source·profile·APK와 준비된 미소비 계획은 보존한다.
