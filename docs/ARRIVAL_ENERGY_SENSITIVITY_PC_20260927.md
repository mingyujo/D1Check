# 합성 도착의 시간·에너지·AP 민감도 판독 (PC, 2026-09-27)

이 문서는 기존 `arrival_explore_batch_v3` 결과와 대표 seed 201 실행 일정을 읽어 **사후 스트레스 가정**을 대입한 판독이다. 휴대폰 실행·도착 상태 전력/AP 보정·새 정책 튜닝은 없었다. [오프라인 대시보드와 CSV/그림](results/arrival_visualization_01/README.md)을 함께 본다.

## 시간 결과와 실행 경로

`sensitivity.csv`는 `tools/d1_arrival_explore_batch.py`의 `paired_effects.csv`를 복사한 P−B3 시간 지표이며 전력/열 계수가 없다. strict 12조건×5 seed에서 시간 차이가 모두 0인 까닭은 `tools/d1_arrival_explore.py::choose`의 `global_serial`과 strict 적응형 CPU fallback이다. 대표 low·queue·burst/seed201을 같은 입력으로 대조하면 P와 B3의 **24건 각각** backend, dispatch, execution_start, output_ready, persist_complete, lane_available이 같다. strict에서는 반대 lane이 실행 중인 pair 후보가 없어서 P의 pair 비용도 작동하지 않는다. 따라서 이 대표 trace에 한해 경로까지 동일하며, 별도 정책 구현/집계 오류의 증거는 없다. 기존 결과만으로 모든 가능한 입력의 두 정책이 동치라고 일반화하지 않는다.

| 설정 | 정책 예상시간 | 실현시간·이벤트 | 코드 위치/뜻 |
|---|---|---|---|
| `predicted_interference` | P의 겹침 `extra+harm`에만 | 직접 변경 없음 | `d1_arrival_explore.py::choose` 72–80행. 기본 1.5는 실측 계수가 아닌 탐색 가정 |
| `interference` | 직접 변경 없음 | 두 lane의 동시 `EXECUTING` 처리율 | 같은 파일 `simulate`의 `rate` 116행. `queue_interference_1.0`은 **이 값만** 1.0으로 변경 |
| `estimate_factor` | 예상 잔여·응답·service 비용 | 직접 변경 없음 | 같은 파일 52·68·77행 |
| `load_prepare_factor`, `load_callback_factor` | 직접 변경 없음 | 실현 vector의 준비·callback | 같은 파일 154–155행 |
| `decision_ns`, `record_ns`, `dispatch_ns` | `choose`의 점수에 직접 반영 없음 | host 판단·기록·dispatch 이벤트 비용 | 같은 파일 157–159·172행 |

실현 간섭 1.0 대표 queue/seed201에서도 P의 **예상** 간섭은 기본 1.5다. 200ms 긴급 요청 `.../1`에서 B3는 CPU 예상 582.435ms, GPU 295.764ms로 GPU를 약 200.300ms에 배정한다. P는 GPU에 예상 pair 손해 332.692ms를 더해 628.456ms로 보고 CPU 582.435ms를 우선하나 CPU가 바빠 기다린다. 약 629.848ms에 GPU 배정으로 넘어간다. 이 PC trace의 긴급 P95는 B3 725.314ms, P 867.945ms다. 대기 판단의 모형상 손해를 설명하지만 실기기 정지·성능 원인이 아니다.

## 에너지·열 연결과 범위

기존 `tools/d1_energy_thermal.py`에는 기기 전체 상태별 적분·AP 전이, `tools/d1_arrival_energy_research.py`에는 명시적 profile 회계와 미지원 반환이 이미 있다. 그러나 이전 `sensitivity.csv`/대시보드에는 이 회계가 **연결되지 않았고**, 현재 두 모델의 임의 도착 상태별 전력/AP 자료도 없다. 고정 870건 CC_DG 및 과거 MobileNet의 계수를 임의 도착으로 옮기지 않았다.

`tools/d1_arrival_energy_sensitivity.py`는 기존 대표 low·queue·burst, strict/explore, seed201의 예정24건·5정책 일정을 재사용한다. CPU_URGENT, FIXED_SPLIT, B2_PC, B3_SOLO_EFT_PC, P_PAIR_COST_PC의 공통 0–120초 전체 상태를 회계한다. CPU_FIFO와 두 P 제거 변종은 이 별도 회계에서 **미지원**이다. 미측정 queued 상태는 0W가 아니라 해당 전체 활성/유휴 상태 전력을 한 번만 청구한다. 병행 전력은 단독 합이 아니라 별도 가정값이다. 초기 AP 29°C, idle 1W/평형29°C, 단일 활성 2W/평형34°C, 시간상수60초, 병행 2 또는 3W/평형30 또는 42°C는 **연구자 스트레스 축**이다. 관측된 물리 범위나 A24 보정값이 아니다. 공통창 밖 준비·cleanup, BAT·표면온도, 도착별 실측 정확도는 미지원이다. 열은 사후 회계하며 배정·실현시간에 피드백되지 않는다.

queue/explore/seed201에서 P−B3 공통창 에너지는 병행 2W 가정이면 **+0.301J**, 3W면 **−1.693J**다. 두 일정의 상태 시간 차이로 계산한 사후 동률점은 약 **2.151W**이나, 이 값은 기기에서 가능한 전력 범위가 아니다. 병행 AP 평형 30→42°C에 따라 P−B3 AP 최고 차이도 **+0.137→−0.212°C**로 바뀐다. 같은 일정의 응답·기한 지표는 이 사후 profile 변경으로 바뀌지 않는다. burst에서는 에너지 P−B3 **+0.197~+0.293J**, AP 최고 **+0.008~+0.025°C**로 이 4개 가정에서 방향이 유지된다. low와 모든 strict 대표 일정에서는 P/B3 차이가 0이다. 정책별 긴급 P95·일반 평균/기한·완료 분모·가정 J/AP는 CSV와 대시보드에 함께 둔다. 비지배 표시는 **이 5정책/가정/seed에서만** 여섯 지표를 동시에 본 탐색 결과로, 종합 1위·현실 우월성이 아니다.

에너지 방향은 가정 전력에 따라 뒤집히므로, 실제 절감 여부를 바꿀 **한 가지 핵심 미측정 항목**은 현재 두 모델의 임의 도착 일정에서 idle·단독·실제 CC_DG 겹침을 구분한 **기기 전체 전력**이다. AP 경로 주장에는 대응 상태별 AP 시간 응답도 필요하다. 이 결과만으로 새 수집 예산을 승인하거나 열 제약 스케줄러를 검증하지 않는다. `experiment_ready=false`, 기존 FAIL·동결값·종료 기록은 그대로다.

재현: 저장소 루트에서 `python -m tools.d1_arrival_visualize` (기존 외부 `arrival_explore_batch_v3/metrics.csv` 필요), 또는 기존 대표 일정에 한정해 `python -m tools.d1_arrival_energy_sensitivity`. 검증: `python -m unittest tools.test_d1_arrival_energy_sensitivity tools.test_d1_arrival_visualize -v`. 대표 일정의 사후 회계는 5 seed 평균 시간 결과와 표본 단위가 다르다.
