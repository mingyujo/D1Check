# M8 계약 질문 v2 — 조민규 10/15 01:5x 답 (8항목) 반영 상태 (2026-10-15 · v1 `contract_questions.md` 12 질문 · v1 파일 무변경)

> 정본 = `D1_ondevice/조민규_답_1015_계약값_8항목.txt`. 반영 = 등록 `M8_사전등록_v2.md` · 계약표 `M8_계약표_v2.md` · `contract_v2/*.json` · 코드 (앱 · 호스트). 첫 DEV 정책 실행 전 → v2 가 전 블록에 적용 (한 블록 안 계약 섞지 않음 · START 한 스모크/회귀 원자료 소급 0).

| v1 # | 질문 | 조민규 답 (01:5x) | 반영 |
|---|---|---|---|
| 1 | WAIT 정책 ID | **ID 하나 `FIFO_WAIT_CG_V1` + 인자** (`wait_ms` · `first_n_bursts` · `nominal_total_ms`) · 200×16 명목 3.2 s / 200×12 명목 2.4 s / 1000×12 명목 12 s · 묶음별 최초 eligible head 한 번 · 이후 WAIT 0 · 타이머 중 도착 enqueue 만 · 실제 dose/잘림/초과/개입 0 기록 · 명목으로 실제 대신 안 함 | `cap_ms` → `nominal_total_ms` (앱 `M8Plan.WaitArgs` · 엔진 wait 이벤트 `nominal_total_ms` · `overrun_ms` · 호스트 `wait_args` · A7 · readout 열 nominal/planned/dose/overrun/cut) · 단위 시험 3 config |
| 2 | 537.155 재계산 | **확인** · C_GPU 73.54419138 · D_CPU 241.71965499333334 · raw 537.154788874… · 1 µs 올림 537,155,000 ns · 프로필 SHA `bd8d55c1…` · 합성 입력용 평균 · 실측/이용률 90 % 보장 아님 | 상수 · `burstIntervalRawMs` · 시험 (raw 1e-9 · µs · ns) · `burst_interval_recalc_v2.json` · 등록/bank 표에 SHA |
| 3 | task × priority 응답 경계 | **priority 기준** (task 무관): urgent = output_ready · normal = 실제 readback 성공 · C/D × urgent/normal 네 조합 코드 시험 · 교차 실측 = P3 | `M8RoundTripTest.responseBoundaryAllFourTaskPriorityCombos` (validate 없이 엔진 경계 · bank 는 fail closed) · 교차 효과 검증 주장 0 |
| 4 | Tref 산출 | **측정일 시작 · 같은 준비·유휴 조건에서 처음 확보한 안정 60 s AP 중앙값** · 기울기 = 실제 표본 시각 · ≤ 0.1 ℃/min · ± 0.5 · 10 min 거절 · 첫 DEV 정책 실행 전 고정 · 센서/결측/gap 명시 · 블록 안 재산출 0 · RECENT_CPU gate 준비 전 | `m8_gate.py` v2 (`TREF_DAY_FIRST_STABLE_AP60_V2` · 판정 불가 ≠ REJECT) · `m8_driver` tref_day/gate · gate_m8.json v2 · 등록 v2 §3 |
| 5 | M7-B | (답 없음 — 유지) | 결정 대기 (M8 일정에 넣지 않음) |
| 6 | SMOOTH128 식 | **`arrival_ns = 35000000000 + floor(i × 15 × 537155000 / 127)`** · i = 0..127 · 첫 35 s · 마지막 43.057325 s · task/입력/ordinal/상대기한 유지 · 절대기한 = 새 도착 + C 0.8 / D 2 s | `M8Plan.slotsNs` · `Request.offsetNs` · 엔진 ns 예정 도착 · 호스트 `slots_ns` · 시험 i=0/127/단조/기한 |
| 7 | 탐지 GPU R2 | (답 없음 — 유지) | 별도 계보 (M8 밖) |
| 8 | 입력 순열 seed | (답 없음 — 유지) | 단일 입력 |
| 9 | NO_RUNTIME 자리 | (답 없음 — 유지) | DEV 각 1 + CONFIRM 각 1 |
| 10 | RECENT J0~180 | (답 없음 — 유지) | 네 문장대로 |
| 11 | Perfetto on/off · C32 | (답 없음 — 유지) | L64 BASE 2세션 (off/on) |
| 12 | baseline 60 | (답 없음 — 유지) | 60 |
| 새 (#1) | S 시도 수 | **8** (S1~S5 5 + S6-C 3) · "7시도" 정정 · 완료 5/6 · 실패 2 · 상한 밖 추가 DEV 1 구분 유지 | `m7_derive_1014.py` 문구 정정 (파생표 8행은 그대로) · 등록 v2 §0 |
| 새 (#7) | SOC · M7-A 재사용 | SOC ≥ 20 · 상한 없음 = 원래 40~80 과 다른 조건 명시 · 블록별 시작/변화폭/충전/40~80 열 · 삭제 0 · '원래 조건 준수' 표기 0 · L-C3/L-G3 = DEV 재사용 후보 (식별표·APK/입력/응답·계측창 검산 연결) · 87/38 대체 아님 | `m8_table` 열 (end_SOC · soc_delta · in_block_charge_yes_no · soc_40_80_satisfied · soc_condition) · 등록 v2 §3 · 보고 |
| 새 (#8) | 조민규 쪽 자료 | 동결 예측 모델 · 정책별 수치 예측 · 최종 ATC/PPO 인계물 **없음** → 해당 항목 "미완료 — 인계물 없음" · 고정 처방 구현·실측은 계속 · 사후 비교를 "예측 검증" 으로 부르지 않음 · 준비/등록/실측 착수/완료 상태 분리 | 등록 v2 §5 (d) · 보고 상태표 |

남은 질문 (조민규 답 없음 · v1 기본값 유지): #5 M7-B · #7 탐지 GPU · #8 입력 seed · #9 NO_RUNTIME 반복 · #10 J0~180 · #11 C32 · #12 baseline 60 · 새: Tref 유휴 1,200 s 상수 (v1 유지 · 조민규 #5 는 창 정의만 바꿈) · Tref 탐색 상한 1,200 s · 판정 불가 상수 (표본 20 · gap 5 s).
