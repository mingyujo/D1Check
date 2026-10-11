# DECISIONS — S26 값을 A24 시뮬레이터 꼴로 (a24fmt_v1 · 2026-10-11 21:5x · 계산 전 커밋)

목적: 조민규 A24 시뮬레이터가 기기에서 받는 세 입력 (5단계 서비스 벡터 · 사전 전력 + 상태별 증분 전력 · AP 1차 응답) 을
S26 기존 자료로 같은 꼴로 만든다. 근거 = 조민규 `docs/S26_SIMULATION_PLAN_20261011.md` (S0 · T1 · E0) · A24 동결 모형
`docs/results/online_policy_study_01/overnight_sustained_run01/model.json` · `tools/d1_rolling_hybrid_model.py` (origin `feature/arrival-scheduling-20260923`).
A24 계수 · 숫자는 쓰지 않는다 (꼴만). 판정 · 합격선 없음 — 개발 적합 + 이미 본 자료의 회고 오차 기술.

D1 자료: R3 16세션 = 개발 (적합). R4 (C) 16 = 회고 평가 (이미 본 자료 · 독립 확인 아님). R4 (S) 유효 14 = 장시간 기술 (평가만, 적합 안 함).
D2 서비스 S0: (문맥 = 정책, 작업, 자원) 마다 5단계 = dispatch→execution_start · execution_start→output_ready · output_ready→persist_complete ·
    persist_complete→worker_release · worker_release→lane_available. 평균 (A24 와 같음) + 중앙 · p95 · n 같이. 요청 = 공통창 192 전부 (succeeded).
D3 전력: W = −current_raw × voltage_mV / 1e9 (S26 µA 가정 — A24 mA 해석 안 씀). 표본 시각 = (snapshot_start_ns + sensor_read_end_ns)/2.
    plugged ≠ 0 · current_valid false 는 버림. 적분 = 사다리꼴 · 창 경계는 선형 보간 · 표본 간격 > 2.5 s 이면 그 창 결측 (0 채움 · 외삽 없음).
D4 P_pre = phase `resident_baseline` (30 s) 의 시간 평균 전력 (세션마다). A24 [−20, 30] 창을 복사하지 않는다.
D5 상태 = 그 순간 바쁜 줄 조합 (줄 바쁨 = dispatch ~ lane_available): cls_CPU · det_CPU · cls_GPU · cls_NPU 단독 + det_CPU&cls_GPU · det_CPU&cls_NPU 겹침 (6상태).
    직렬 정책은 CPU 줄 하나라 cls_CPU 와 det_CPU 가 번갈아 온다.
D6 E0: 공통창 0 ~ 120 s 를 5 s 창 24개로 · 목표 = 창 J − P_pre × 5 s · 설명 = 상태별 점유 초 → R3 전체 창을 모아 NNLS 1회.
    식별 감사 (적합 전 고정): 설계 행렬 rank = 6 그리고 열 표준화 조건수 ≤ 30 이면 "식별" · 아니면 공선 상태 이름을 적고 "미식별" (측정 ① 대상).
    추가로 상태마다 "그 상태 점유가 창의 50 % 이상인 창 수" 를 노출로 보고.
D7 T1 (AP): dT/dt = −β (T − R) + Σ_s θ_s · x_s(t) (x_s = 상태 s 점유 비율 1 s 격자) · R = baseline 마지막 10 s AP 평균 · T(0) = 공통창 시작 직전 AP.
    적합 = R3 전체 AP 표본 (공통 120 s + 냉각 60 s) 의 제곱 오차 합 최소 · β ∈ [0.005, 0.5] · θ ≥ 0 · scipy least_squares 1회. 느린 항 · 잔열 h 없음 (A24 T1 = 1pole).
    θ 식별도 D6 과 같은 감사 (같은 노출).
D8 회고 평가 (R4C · R4S): 실측 점유를 넣은 조건 A (A24 계획의 A) 로 J (0 ~ 120 s) · AP 경로를 계산해 오차 기술. 계수 다시 맞추지 않음.
D9 R4 (S) 감속 기술: CPU 직렬 실행 시간 (execution_start→output_ready) 을 1분 칸별 중앙으로 · 공통창 첫 1분 대비 비율. S1 모형은 만들지 않는다 (기술만).
D10 출력: `out/s26_a24fmt_model.json` (A24 model.json 꼴 — service.*.phase_means_ns · power.pre_mode · power.state_increment_w · thermal.beta · theta) ·
    `out/audit.json` · CSV · README. 단위 ns · W · J · ℃.
