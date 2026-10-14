# M7 개발 묶음 3 — S26 같은 APK 확대 반복 (M7-apk) · 측정 · readout 까지 (계산 · 판정 = 조민규 / Cowork)

- 만든 시각: 2026-10-14T12:07:08 · 등록 v2 `c3da26cc05c496ed4ebaf718f9c7d3293204e5223e0830a1fb0c378968a226bb` (v1 `899d63c6…`) · APK M7 `878b10b7bc05300ddddc60fac0b2fb40eb020870841e473a8775827ef92bf092` (커밋 `7ad2b18f`) · M6 12세션은 APK `6a4da1ac…` (`cycle = m6` 행만)
- 계획 SHA: plan_m7p `bf1e3c258367f4cdbcf37eb85478f2b9a7bc5d2941db129111c9551fb39e5454` · plan_m7prep `8f0e748b0d2e9a2cdd22291e862906e02512a501c63236c76bf406784003070a` · plan_m7k `571d4a1e58442f54789721c04c3235f20b68d24682dcebaf604873aeddf83a96` · plan_m7s `e08a6adb859f8a36778311f6c9a0ee021957cfe32fe81dbdcbcd37635cf67b2e`
- 세션 표 행: 44 (m7 44 · m6 0) · 유효 (m7): {"K": 9, "P": 18, "PREP": 6, "S": 5} · kind 별: {"K": 9, "M6REPRO": 1, "P": 18, "PREP": 6, "S": 6, "S7": 1, "SMOKE": 3}
- fingerprint: `samsung/m1sksx/m1s:17/CP2A.260605.016/S942NKSS4BZIG_OKR4BZIG:user/release-keys` · 케이스/거치/바람: 케이스 없음 · 책상 위 눕힘 · 바람 없음 · 실내 온도: 미기록

## 단위 · 부호
- 전류 µA (current_raw · 방전 음수 · API 값 · 기기 스케일 미검증 — 등록 M6 v3 §3-7 가설 그대로) · charge_counter µAh · 전압 mV · 배터리 온도 deci-℃ · HAL 온도 ℃ (0.1 단위) · 시각 mono_ns (기기 단조 시계) / host_ms (PC epoch ms) · 같은 gauge 라 독립 전력 기준 아님 (M6 v3 §7-2)

## 완화 3개 (등록 v2 · 대조 문서)
- 완화 1 (항목 1 · 등록 §1-4): 준비 P ~ K 사이 끊김 없는 관측 = 호스트 연속 HAL + dumpsys battery (hal_cont · 2.3 s) · 앱 power_sample 은 세션 밖 (cooling 끝 ~ K 준비) 없음 → power_gap = {reason: app not running between sessions (APK: power_sample only inside a session)} · 추정 채움 0
- 완화 2 (항목 2 · 등록 §2-6): 마지막 AVAILABLE 뒤 180 s 냉각 — 온도는 호스트 HAL 을 원점 + 300 s 까지 (hal_coverage_after_last_available_s ≥ 180 실측) · 전력은 앱 cooling 60 s 까지 (power_coverage_after_last_available_s ≈ 105 s 실측)
- 완화 3 (항목 4 · 등록 §4-3): 지속 S 냉각 600 s — 온도는 호스트 HAL 을 창 끝 + 600 s 까지 · 전력은 cooling 60 s · 준비는 블록 A/N (R4 와 같음 · 블록 M 아님)

## 공백 사유 (null)
- `power_gap`: 세션 사이 (준비 P cooling 끝 → K 준비 · 세션 cooling 60 s 뒤) 앱 power_sample 없음 — APK 가 세션 안에서만 표본을 쓴다 (field_map.json power_gap)
- `응답 시각`: 앱에 요청자 응답 이벤트 없음 (field_map.json) · `실내 온도`: 온도계 없음 → 미기록 · K 의 `power_coverage_after_last_available_s`: 요청 0 → null
- 조건 B · C 의 K 는 시작 띠 · 게이트 대기를 건너뛴다 (등록 §1-2 90 s 간격 우선 · plan_m7k.k_after_prep_gate) → band_result = skipped · 시작 SKIN 등은 세션 표 start_* 열
- index 자리: M6 · R4 가 쓴 자리 뒤 (P 12 ~ 51 · K 4 ~ 18 · S 16 ~ 27 · 등록 v2 머리 단락) · session_id = uuid5(실험 ID/index) 그대로

## 실측 사용량 (run log · 기술만)
- 세션 44 · 순수 실행 합 20460.9 s · 재시도 (attempt 2) 실행 478.8 s · 세션 사이 대기 합 27461.0 s (유휴 · 안정 · 게이트 · 띠 포함) · 충전 구간 (드라이버 기록) 0 · 첫 세션 2026-10-13T21:46:30 · 마지막 끝 2026-10-14T11:05:09
- 세션별 run_s 는 `usage.json`

## 폴더
- `docs/` 등록 v1 · v2 · 대조 · REQUEST · APK_COMMIT_MAP.md · APK_M7_AREA_DIFF.json · area_rules.json · freeze_m7.txt (원장 사본)
- `plans/` plan_m7p · plan_m7prep · plan_m7k · plan_m7s (plan.json · manifests · smoke · projection.json · device_inputs.json)
- `results/` S26_M7_S7 (회귀) · S26_M7_M6REPRO (M6 재현 스모크) · S26_M7_SMOKE · S26_M7_K · S26_M7_PREP · S26_M7_P · S26_M7_S · S26_M7_HAL (연속 HAL csv) · S26_M7_runs.jsonl · S26_M7_driver_events.jsonl · 드라이버 콘솔 · keepawake 로그
- `tables/` session_table_m7.csv · apk_manifest_session_map.csv · field_map.json · fingerprint.txt · table_index.json · readout_<root>/ (m6_readout: 세션 JSON · inventory.csv · readout_index.json)
- logcat 은 정리본 (`logcat_threadtime.sanitized.txt`) 만 · *.apk 없음 · 주소 · 시리얼 0 (PAT 검사)
