# 블록 1 정정 3판 (delta · 조민규 10/15 22:xx 답) — 부모 v1 ZIP `3d7818a7a415215870bb97c10e0d3228b28afe938df5741c9747864dc7f764f6` · v2 ZIP `61d2e922c697304f4a11d9c5352b5a873da3dfdd8bde10927fd6aeec6bbb16d2` · 새 측정 0 · 원 HAL · 결과 파일 보존

## 온도 파생열 시간 원점 (session_table_m8_v2.csv 의 *_target_* · *_sample_* · *_delta_s · *_method · hal_path · hal_sha256)
- 시계: common / first_request / device_session_start = **기기 CLOCK_BOOTTIME** (HAL `device_uptime_s` = progress `mono_ns`/1e9 · 같은 시계 · host 변환 0) · app_start = **host 시계** (HAL `host_ms` vs session_log `start_time`) · gate_last = 게이트 마지막 판정의 60 s 창 중앙값 (표본 1개 아님).
- `common_*`: target = `common_boundary.start_ns` (= scheduled_origin_ns · common 0) · 표본 = nearest (양쪽 · |delta| ≤ 6 s). RECENT 는 common_start 로그 발행 시각 (mono_ns · prep_end) 이 아니라 이 값. B1-03: target 494372145200198 → AP 30.3 (delta −1.095 s).
- `first_request_pre_*`: **target = min(common_boundary.rows.scheduled_arrival_ns) (= common0 + 35 s)** · 표본 = **target 이전 (≤) 가장 늦은 HAL 표본 · ≤ 10 s** (직전 실측 · 이후 표본 사용 0 · "5초 전" 아님). B1-03: 494407145200198 → AP 30.3 (delta −1.705 s). v2 의 `first_request_pre_AP` (common 로그 발행 시각 + 35 − 2.5 s nearest · RECENT 7행은 첫 요청 뒤 19~37 s 표본) 은 `v2_*_deprecated` 열로만 보존 · 시작 조건으로 쓰지 않음.
- `app_start_*`: 정의 = **host 호출시각 (session_log start_time) 근접 HAL (nearest · ≤ 6 s)** · gate_last · 기기 session_start (`device_session_start_*` · 기기 시계 nearest) · 앱 직접 센서 (power_sample · 온도 없음) 와 다른 값.
- 표본/시계 정렬 없음 → null (`*_note` 에 사유) · 보간 0.
- 재파생 수: common 20/21 · first_request_pre 20/21 (B1-06 a1 stall = common_boundary 없음 → null) · app_start 21/21.

## 코드 증거 (`code_evidence/`)
- `slope_fix_8bc310915.diff` = 집계 source `fe14bd886` (v1 · `abs(x or 9)` 버그) → `8bc310915` 수정 diff · `rev3_time_origin_uncommitted_vs_8bc310915.diff` = 이 판의 시간 원점 변경 (커밋 SHA 는 원장) · `m8_b1_corrections.py` · `test_m8_b1_corrections.py` 원본 · `SOURCE_SHA.txt`.
- 실제 분기: `slope_ok()` = `if a is None or b is None: return None` (결측 → **None · False/0 아님**) · 아니면 `abs(float(a)) <= max and abs(float(b)) <= max` (0.0 · −0.0 = 숫자 통과). `slope_check_evidence.json` 의 "boolean 수식" 설명은 이 분기로 정정.
- 경계 시험 `pytest_boundaries.txt` 14 passed: (0.0, −0.0) 통과 · ±0.1 통과 · ±0.1000001 실패 · None → None (is not False) · `pick()` before/nearest/null 3경우.

## 집계 (다른 셈 · 섞지 않음)
- 당시 host 완료 **20 세션 / 3,300 요청** (회수실패 1 소비 = EDD a1 · 대표 19군 3,048 · a2 대표) — 보존.
- 회수 후 현재 가용 **3,428 요청 (+128 = EDD a1 기기 완료 128 · 읽기 전용 회수)** — 별도 집계 · 새 성공 시도로 세지 않음 · 대표/동결 모형 변경 0.
- 휴식 원점별 501.181 (events) / 501 (driver_log) / 526 (session_log) / 482.336 (기기 mono) s · manifest.split = confirmation · analysis_split/stage = dev 그대로.
