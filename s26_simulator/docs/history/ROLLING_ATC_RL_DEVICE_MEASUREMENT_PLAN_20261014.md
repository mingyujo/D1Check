# A24와 S26의 스케줄링 차이 확인 실측 설계

사용자가 요청한 A24 실측 계획과 S26 전달문을 탐색34·36·V2 P1에서 확인한 분류 비중·밀집/버스트·병행·순서·대기 조건에 맞춰 작성했다. **계획·템플릿 작성 완료이며 기기 실행, APK 빌드·설치, 외부 전송은0이다.** 기존 GEN002 학습·CAUSAL·NODGPU 동결 소스와 원장·예약은 보존한다.

| 산출물 | 경로 |
| --- | --- |
| A24 상세 계획 | [A24_MEASUREMENT_PLAN.md](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/A24_MEASUREMENT_PLAN.md) |
| S26 전달용 요청문 | [S26_REQUEST.txt](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/S26_REQUEST.txt) |
| 기계 판독 설계·용량 산술 | [PLAN_ONLY.json](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/PLAN_ONLY.json) |
| 기기별 실행 순서표 | [SESSION_ROSTER.csv](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/SESSION_ROSTER.csv) |
| 요청 템플릿50개 색인 | [TRACE_INDEX.json](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/TRACE_INDEX.json) |
| 처방 정의·창·응답 계약 | [PRESCRIPTIONS.json](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/PRESCRIPTIONS.json) |
| 독립 검토·해시·범위 검산 | [PLAN_QA.json](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/PLAN_QA.json) |
| 문서·순서표·미결합 템플릿 묶음 | [HANDOFF.zip](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_PLAN_20261014/HANDOFF.zip) |

## 설계와 예산

입력은 L64 저부하 혼합, C252 분류 반복, M128 분류96/탐지32의 균형8건 버스트다. C252는333.2ms 정확격자·jitter0인 새 통제 recipe이며 V2의 누적위치 jitter 입력과 구별한다. S26에서는 이 간격이 포화가 아니므로 기기별 명목 용량을 사용한 M128을 별도로 둔다. 모든 대조에서 같은 요청·입력·도착·납기·작업량을 유지하고 한 요소만 바꾼다.

| 단계 | A24 | S26 |
| --- | ---: | ---: |
| 계측 확인 I | 4 | 4 |
| 기능·용량 확인 F | 4 | 6 |
| 개발2블록 | 16 | 22 |
| 동결 후 새 확인5블록 | 40 | 55 |
| 핵심 계획 최대 | **64** | **87** |

A24 블록당8군, S26 블록당11군이다. 경로는 분류 CPU/GPU(/NPU), 탐지CPU만이다. 전역직렬 FIFO를 공통 기준으로 EDD 순서, 지원되는 CG_DC/CN_DC 병행, 고정200ms WAIT를 분리한다. 분류단독에는 의미 없는 탐지 병행을 추가하지 않는다. S26 NPU pair는 NPU serial과 비교한다. 저부하 pair의 실제 겹침0도 음성 결과로 남긴다.

한 세션210초 관측과 세션 사이90초 단순 예약은 A24 약5시간19분, S26 약7시간13분이며 준비·초기화·냉각 gate·회수는 추가다. 먼저 A2424/S2632세션의 I/F/DEV를 검토한 뒤 확인 단계에 들어간다. 최근CPU부하·긴WAIT·묶음을 푼 동일작업량 입력은 별도 후속 모듈이며 위 예산에 포함하지 않는다.

## 실제 실행 전 필요한 작업

A24 현재 주 연구 실행기는 고정96/192건이다. 새64/128/252건·FIFO/EDD 고정처방·의도WAIT·strict head와 serialgate를 위한 새 opt-in 실행기/host validator·APK가 먼저 필요하다. S26 최신 M6 APK의 처방/WAIT 지원은 미확인이므로 담당자에게 기능 확인을 요청한다. 요청 템플릿은 승인 입력 슬롯만 있으며 실제 이미지·tensor SHA가 미결합 상태다. PLAN_ONLY 산출물을 기존 실행기에 넣지 않는다.

기존 소비된 A24 측정 계획을 재실행하지 않는다. 기존 M6의600요청·6경로 시간 자료를 다시 요청하지 않으며, 원자료가 있는 내용은 재사용한다. 새 계측·입력·처방·품질·환경과 분석 수치 허용치를 DEV에서 고정하고 확인 결과로 바꾸지 않는다. 새 센서값을 얻는 것은 또 하나의 기기 실험이며 이번 계획 작성이 실행이나 전송을 뜻하지 않는다.

## 판정

서비스0~120초·에너지0~180초·평균AP35~180초와180초 뒤 실제 센서 표본을 공통으로 확보한다. 전체 도착 분모의 긴급·일반 서비스수준, 전량완료·미완료·납기손해·관측최고/잔열을 함께 기록한다. 불완전 관측창은null이며 단일 저속 gauge 표본을 개별 짧은 요청의 에너지로 해석하지 않는다. S26의 기존180초 끝 표본 부족과 전류 갱신/도착 위상 문제를 특히 확인한다.

모형 예측은 확인 전에 동결해 각 대응 블록의 ΔJ·ΔAP·Δ납기와 대조한다. 새 입력/단독·병행/순서/WAIT dose와 실제 개입을 따로 검산한다. 작거나 반전된 효과도 보존하며 총J 오차 감소를 정책차이 재현으로 바꾸지 않는다.5블록은 정밀한 신뢰구간이나 실제폰 공동목표 달성의 보장이 아니다. 실제 기기 자료가 들어오면 원 V2와 별도 모형·개발/확인 계보에서 보완한다.

검증 대상 HEAD는12d64923be824ce4c88fca074fbe38820f5a7d25이며 기존 미커밋 WIP를 보존했다. 계획 생성기는 별도 work/ROLLING-ATC-RL-37-V2-MEASUREMENT-PLAN-20261014/build_plan.py이며 finalize_plan.py가 정적 산출물·보호 SHA·프로젝트 문서의 한정 삽입과 전달 ZIP을 검산한다. 공개 프로필 평균의 합산·템플릿/세션 구조 검산만 수행했고 Device·시뮬레이션·NN·기기 실행은0이다. 전체 시뮬레이션137712 상한과 기존 예약111334는 변경하지 않았다.
