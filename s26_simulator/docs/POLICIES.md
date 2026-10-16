# 정책·행동 공간

[동률 원인 진단](../SAME_CHOICE_DIAGNOSIS_KO.md): 세 정책이같은배정기와WAIT규칙을공유하므로직전실험은순서정책대조다. 전역FIFO·EDF선두349회차이가가용mask후0회가됐다. 실행가능복수1,551회전부동일task/priority/기한과route별ATC동점이었다. FIFO_FREE_ROUTE는실행가능ready중FIFO로, 막힌전역head를기다리는strictFIFO와구분한다.

2026-10-16: FIFO/EDF의 `FIFO_FREE_ROUTE_V1`/`EDF_FREE_ROUTE_V1` 동일 자원 비교를 `../experiments/fair_resource_v1/source/`에 별도 등록했다. 원 SIM002 물리와 우리정책을 유지하며, 원 명목 후보·납기/열/에너지 자원 배정기·WAIT를 공유하고 시작 가능한 ready 요청을 도착순/절대기한순으로 고른다. [결과](../FAIR_RESOURCE_COMPARISON_KO.md)는48조건 전부 실제 궤적까지 동률이다. 아래 GPU 고정 참고군과 이 새 비교를 구분한다.

## 현재 주정책: ROLLING_ATC_ROUTE_V2

새 RL 전의 결정론적 규칙이다. 도착/자원반납/센서 전달/WAIT 종료 등 공개 상태 변화에서 현재 ready 요청을 다시 본다.

1. 각 분류 요청마다 CPU/GPU/NPU 후보를 만들고 탐지는 CPU 후보만 만든다.
2. 실제 owner 점유와 검증된 두 병행 조합으로 후보를 mask한다. 실행 중 선점/가상 반납은 없다.
3. 동결 모델의 명목 응답/점유시간으로 해당 요청과 다른 도착 요청의 예상 납기 손해를 검사한다.
4. 예상 납기 손해를 먼저 줄이고 ATC로 요청 우선도를 정한다. 같은 요청의 가능한 경로는 정규화한 명목 에너지·열 대리값으로 비교한다. 이 값은 실제 절감J/℃가 아니다.
5. 짧은 WAIT는 owner가 없고, 이미 관측된 냉각이 있고, 모든 도착 요청에 명목 납기 여유가 있을 때만 허용한다. 현재 50ms씩/누적2초 상한이며 실제 사용량을 기록한다. 미완료/지연을 감추지 않는다.

현재 48조건에서는 분류4,608건 전부 NPU, 탐지1,536건은 CPU였다. 각 분류 후보 CPU/GPU/NPU가 각각9,824회 기록되었다(요청 재검토 포함). 최종 선택이 같아도 후보가 고정된 것은 아니다. CPU/GPU/NPU 각각의 선택 가능성은 별도 순수 시험과 P0 실제 실행으로 검증했다.

## 지원되는 실행 조합

| 상태 | 허용 |
|---|---|
| 아무 owner 없음 | 분류 CPU/GPU/NPU 또는 탐지 CPU 단일 |
| 분류 GPU owner 있음 | 탐지 CPU 추가 가능 |
| 분류 NPU owner 있음 | 탐지 CPU 추가 가능 |
| 탐지 CPU owner 있음 | 분류 GPU/NPU 추가 가능 |
| 분류 CPU owner 있음 | 다른 요청 추가 불가 |
| owner2개 | 추가 불가 |

여기서 CPU는 해당 런타임 경로/점유 자원이다. CPU 코어별 배정·주파수·DVFS 조절이나 작업 분할이 아니다. 탐지 GPU/NPU는 이 엔진의 지원 대상이 아니다.

## 기존 참고 규칙

`FIFO_SERIAL_CG_V1`, `EDD_SERIAL_CG_V1`, `FIFO_PAIR_CG_V1`, `EDF_PAIR_CG_V1`은 분류GPU/탐지CPU 고정의 과거 저장 결과다. ready strict head를 선택하고 불가능하면 backfill하지 않는다. EDF/EDD는 절대기한순이다. 이 화면에서 새 동적 자원 정책과는 선택 공간이 다름을 명시한다. FIFO는 FCFS와 같은 뜻이며 중복 정책으로 세지 않는다.

## 과거 RL/IE와 다음 RL

RARL001_G002의 JOINT_ATC_RL/ATC_ROUTE_RL/ATC_RESIDUAL_RL/NO_ATC_RL×3seed×64경험과 IE depth2/beam4/branch8 비교는 `policy_history` 아카이브에 경험·RNG·체크포인트·선정·raw·감사를 보존했다. 기존 입력/물리/행동 ABI가 달라 최신 엔진의 학습본으로 이식 완료했다고 하지 않는다. 자세한 결과와 작은 차이/모형 반전은 `docs/history/S26_RARL_IE_TRANSITION_20261016.md`를 읽는다.

주정책의 다음 후보는 같은 공개 정보/지원 마스크에서 롤링+ATC joint constrained PPO 및 ATC residual PPO다. 충분하지 않으면 사용자 승인 IE/MPC/강건 제한탐색을 새 등록에서 검증한다. 현재 새 RL은 선행 환경 보완 이후다.
