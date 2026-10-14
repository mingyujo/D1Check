# M7-A 정정 파생표 (derived_1014) — 조민규 10/14 답 §1 · §2 · §5 반영 · 원본 무변경 · 폰 0

> 2026-10-14 · 브랜치 `s26-m8` (`aaa7b87f` 에서) · 생성 도구 `s26/tools/mixreq/m7_derive_1014.py` (읽기만 · 새 파일만) · 원본 = `s26/results/m7_1013/dev/` (세션 표 · readout · 세션 폴더) **수정 0 · 삭제 0**.
> 전부 **파생** · 기술만 (J · 열 · 정책 비교 계산 0 · 보간 0 · 추정 채움 0). 시계: device = `progress.jsonl` `mono_ns` (elapsedRealtime = CLOCK_BOOTTIME) = 세션 `hal.csv` `device_boottime_s` = `hal_cont` `device_uptime_s` (`/proc/uptime`); host = PC epoch; 세션마다 host − device 오프셋 = 그 세션 `hal.csv` 의 (pc_ms ↔ device_boottime_s) 중앙값 (adb 읽기 지연 ≤ 1 s 포함). M7 드라이버의 "host start_time + mono 차" 방법은 둘째 열로 나란히.

## 파일

| 파일 | 행 | 내용 |
|---|---|---|
| `s_sessions_resolved.csv` | 8 | S 시도 전부 (S1 ~ S5 a1 · S6-C a1 · S6-C a2 13:22 `a2_screenoff_1322` · S6-C a2 13:38) 를 **`folder` + `command_id` + device 앱 시작 + host 시작** 으로 한 행씩 · `registered_status` (S1~S5 `valid` · S6-C a1 `invalid_1` · 13:22 `invalid_2 (invalid_twice)` · 13:38 **`extra_dev_outside_retry_limit`** · 민감도 자료) · 실패도 소비 보존 (실제 실행 시간 `runlog_run_s` · 앱 활동 `app_active_s` · SOC 차) |
| `mixed_columns.md` | — | 기존 `session_table_m7.csv` · `readout_S26_M7_S/sessions/21_C_a2.json` · `inventory.csv` 의 어느 열이 13:22 와 13:38 을 섞었는지 + 섞인 원인 (코드 사실) — 고치지 않음 |
| `k_timeline.csv` | 9 (K 9 · 준비 6 은 B/C 행 안) | 같은 시계로 준비 앱 시작 · 준비 common 시작 · 준비 마지막 AVAILABLE · 준비 run-log 끝 · K 앱 시작 · K runtime 생성 끝 · K warmup 끝 · K baseline 끝 · K common 시작 + 차이 열 (`last_available_to_k_app_start_s` · `last_available_to_k_common_s` · `runlog_end_to_k_app_start_s`) · 조건 A 는 `idle_from_prev_runlog_end_s` · 기울기 · `power_gap_*` (보간 0) |
| `deviation_ledger.csv` | 46 | 실행 46 전부 (K 9 · 준비 6 · P 18 · S 8 · 스모크 3 · S7 회귀 1 · M6 재현 1): 실제 시작 · 끝 시각 (반나절 라벨 **없음**) · NotificationShade · 시작 SKIN/AP/BAT · 띠 · SOC (M7 하한 30 기준 `soc_in_m7_band` · 새 40~80 은 `soc_in_new_band_reference_only` 참고 열 · 소급 0) · 충전 간격 · 재시도 · 블록 안 충전 0 |
| `coverage_m7.csv` | 41 | P 18 · 준비 6 · K 9 · S 8: 앱 power 첫/마지막 유효 표본 (common 기준 s) · 0/35/120/180 양측 표본 (허용 gap 2.5 s) · 표본 간격 · 결측 · host hal_cont 첫/마지막 · AP35 · AP180 · I/V 0 · 180 양측 (허용 gap 5 s) · 단위 · 부호 · 앱/host 분리 (이어붙임 0 · host J180 계산 0) |
| `provenance_m7.csv` | 46 | 세션마다 source commit `7ad2b18f` · APK `878b10b7…` (세션 기록 = 등록값 46/46) · 서명 `6394e51f…` · 계획 SHA · 매니페스트 SHA (계획 · push · 기기) · 투영 SHA · 입력 목록 SHA (`device_inputs.json`) · 빌드 시각 · 설치 시각 21:45:30 · 원장 줄 번호 (`freeze_m7.txt`) |
| `derive_index.json` | — | 요약 · 조민규 값 대조 |

## 조민규 값 대조 (재계산 · 기술만)

| 항목 | 조민규 (10/14 답) | 재계산 (`derive_index.json`) | 같은가 |
|---|---|---|---|
| 준비 마지막 AVAILABLE → K 앱 시작 | 216.6 ~ 219.5 s | 216.639 · 216.826 · 217.053 · 217.927 · 218.501 · 219.407 (B/C 6) | 같음 |
| 준비 마지막 AVAILABLE → K common 시작 | 251.5 ~ 253.8 s | 251.529 · 252.231 · 252.478 · 252.961 · 253.570 · 253.779 | 같음 |
| 준비 run-log 끝 → K 앱 시작 | 91.8 ~ 92.7 s (≈ 92) | 드라이버 값 91.752 · 92.085 · 92.104 · 92.134 · 92.648 · 92.692 (hal 오프셋 방법 92.87 ~ 93.14) | 같음 (91.752 는 반올림 차) |
| P 18 앱 power 마지막 유효 표본 | common + 179.498 ~ 179.930 s | 179.498 ~ 179.930 | 같음 |
| 앱 180 s 양측 표본 | 0/18 | 0/18 (120 s 양측은 18/18) | 같음 |
| host HAL AP35 · AP180 · I/V 0 · 180 양측 | 18/18 | 18/18 · 18/18 · 18/18 · 18/18 | 같음 |
| S6-C 13:22 | 0.6 s 뒤 실패 · succeeded 0 / unfinished 3000 · summary 없음 | 앱 활동 0.595 s · `environment/screen_off` (runtime_setup) · 0 / 3000 · summary 없음 | 같음 |
| 실행 46 · 표 74 (M6 28 포함) | 46 | deviation 46 행 (m7) · 세션 표 74 = 46 + m6 28 | 같음 |

해석 줄 (k_timeline `interpretation`): **요청 0 ≠ 열입력 0** — K 는 앱 시작 뒤 runtime 생성 · warmup · baseline 30 s 를 거쳐 common 이 시작한다 (K 앱 시작 → common ≈ 34.5 ~ 36 s). 92 s 는 "준비 run-log 끝 → K 앱 시작" 이고, 준비 마지막 AVAILABLE 은 그 run-log 끝보다 ≈ 124 s 앞 (cooling 60 + drain + pull). → 준비 부하 · 초기 열 · 시간대 · 재생성/warmup 이 섞인 이력 관찰이며 CPU/NPU 잔열만의 순수 비교라 부르지 않는다. 앱 전환 사이 power 공백 (`power_gap_s` ≈ 112 ~ 115 s) 은 보간하지 않는다.

## 회신 정정 (정정 전 → 후 · `조민규_회신_1014_159세션요청.md` 는 원문 보존 · 정정은 여기와 `조민규_회신_1014b_정정과_M8준비.md` §1)

| # | 정정 전 (회신 1014) | 정정 후 | 근거 · 파생표 |
|---|---|---|---|
| 1 | "준비 L-C ×6" | 준비 6 = **L-C 3 (idx 42 · 44 · 46) + L-N 3 (43 · 45 · 47)** | `deviation_ledger.csv` kind PREP · policy 열 |
| 2 | "M7-B 확인 30 · 30 × 6 min = 9 h" | **28 = P 12 + K 6 + 준비 4 + S 6** (+ 회귀 1 · 스모크는 판정 밖 · 별도 ID) · 종류별 시간 분리 → `schedule_m8.md` (M7-B 는 별도 행 · 차감 0) | M7-A `usage.json` 실측 |
| 3 | K 조건 B · C "준비 끝 → 90 s → K" 를 냉각 시간으로 | **92 s = 준비 run-log 끝 → K 앱 시작.** 준비 마지막 AVAILABLE → K 앱 시작 216.6 ~ 219.4 s · → K common 251.5 ~ 253.8 s · K 는 앱 시작 뒤 runtime 생성 · warmup · baseline 30 s 뒤 common → "CPU/NPU 잔열만의 순수 비교" 아님 · 다섯 시각을 같은 시계에 | `k_timeline.csv` |
| 4 | "P2 CONFIRM 은 되는 만큼" | **동의된 범위 아님** — 핵심 확인 5블록 완주 우선 · P2 는 DEV 부터 같은 블록의 대응 기준군과 함께 · 모듈별 완주 반복수 · 순서 · 종료 기준을 확인 전에 고정 · 못 끝내는 모듈 = "미완료 / 개발만" | `schedule_m8.md` · M8 계약표 |
| 5 | "P0 10 + P1 87 (→ 실측 77)" | 핵심 87 = 계측/기능 10 + DEV 22 + CONFIRM 55 (10 은 87 안) · "77 남음" 은 그 10 이 새 계약으로 실제 완료 · 수용된 뒤에만 | `schedule_m8.md` 검산 "159 = 87 + 56 + 16 · 10 중복 없음" |
| 6 | "P0-3 DEV3 는 M7-A 가 덮는다" | **재사용 기준을 조민규가 확정한 경우에만** 연결 · M7 APK · 기존 100요청 · 1.5/6 s · 900 ms 계약의 **전이 자료** 표기 유지 · 새 계약 확인 대체 아님 · M7-B 를 미리 차감하거나 87 에서 빼지 않음 | `provenance_m7.csv` (L-C idx 12 · 23 · 26 · L-G 14 · 19 · 28 행) |
| 7 | "readback 없음 → null" | 새 계약 (M8) = `.part → fsync → rename → 앱 readback 성공` 을 앱이 기록 (수행 · 성공 · 시각 · SHA 대조 · 실패) · host pull 시각 대체 금지 · M7 은 기존 output/persist 경계로 보존 (같은 응답 계약으로 비교 안 함) | M8 `response_m8.json` · 앱 B-2 |
| 8 | "cooling 60 → 90 이면 210 s" | 상수 변경만으로 PASS 아님 — common 기준 실제 계측 ≥ 210 s · 사전 60 s · J0/120/180 · AP35/180 양측 표본을 **검사기** (`coverage_check.py`) 로 · M7-A 는 앱 180 s 양측 0/18 · host 18/18 (앱/host 분리 · 이어붙임 0) | `coverage_m7.csv` |
| 9 | "current_now 20 ms 갱신 · charge_counter 30.6 s 고정 주기" | 읽기 주기 · 값 변화 간격 · 센서 갱신 시각 미제공을 나눠 적음 · 30.6 s 계단은 M6 E 조건의 관찰 (일반화 금지) · charge_counter · 전압 각각 원표본별 | M8 `session_m8.json` 계측 절 |
| 10 | S6-C a2 재사용 성공을 유효 1건으로 | **등록 재시도 상한 밖 추가 DEV** (`extra_dev_outside_retry_limit`) · 원 등록 S = 완료 5/6 + 실패 이력 (`invalid_1` · `invalid_2`) · 마지막 성공은 민감도 자료 · 실패도 소비 보존 · 섞인 열은 `mixed_columns.md` | `s_sessions_resolved.csv` |
| 11 | "서로 다른 반나절" | 충족 주장 안 함 — 실제 한밤 ~ 아침 실행 시각 보존 · NotificationShade (PREP1B · K1B · PREP1C · K1C · S6-C 13:22) · 시작 열 · SOC · 시간대 = 편차 원장 · M7 SOC 하한 30 과 새 40 ~ 80 구분 (소급 없음 · 참고 열 34/46) | `deviation_ledger.csv` |
| 12 | 탐지 GPU "R2 에서 첫 실행 됨" | R2 가 warmup/probe 인지 등록 요청인지 session/request ID · role · delegate 적용 · fallback/partition · 품질 · SHA 로 구분 — 그 전엔 "본요청 검증 완료" 아님 | `detection_gpu_evidence.md` (B-5) |
| 13 | 미상주 idle = "앱 없음 + host HAL" | 같은 Activity/sampler/logger 에서 runtime 만 없는 **`NO_RUNTIME`** arm (M8 `S26-M8-IDLE` block `NONE`) · 불가면 "host-only 진단" 으로 따로 이름 · 조건당 1회로 단정 안 함 | M8 앱 B-2 · `session_m8.json` |

## 명시 (조민규 §1 마지막)

- **M7-A 전체 ZIP `0f094a92…` 에는 APK 와 전체 소스가 없었다** → 조민규 쪽 독립 재빌드는 아직 아니다. APK 사본 = `results/m7_build/request-runner-debug_m7.apk` (커밋 안 함 · SHA `878b10b7…`) · 소스 = 커밋 `7ad2b18f` (브랜치 `s26-m6` · GitHub) · 서명 `6394e51f…` · 빌드 21:12:48 (깨끗한 빌드 2회 같은 SHA) · 설치 21:45:30. source · APK · signer · 계획 · 입력 SHA 의 연결은 `provenance_m7.csv` 한 행씩.
- 단위 · 부호: 앱 `current_raw` µA (BatteryManager CURRENT_NOW · 방전 음수 · 기기 스케일 미검증) · `charge_counter` µAh · `voltage` mV · 900 ms 표본; host HAL ℃ 0.1 단위 (2.3 s 목표 · 갱신 시각 미제공) · `dumpsys battery` current_now µA · voltage mV. 같은 gauge → 독립 전력 기준 아님.
- 이 폴더의 값은 전부 기술 (J · 열 · 정책 비교 · host J180 계산 0 — 조민규 몫).
