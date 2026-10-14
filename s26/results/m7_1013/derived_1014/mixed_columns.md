# mixed_columns — S6-C a2 13:22 (screenoff) 와 13:38 (성공) 이 섞인 열 (조민규 §1 · 원본 고치지 않음 · 기록만)

원인 (코드 사실): `S26_MIXREQ_21_…_a2_screenoff_1322\validated.json` 은 폴더를 옆으로 옮기기 **전**에 쓰였고 `device_dir` 가 `…_a2\device` (13:38 성공 폴더) 를 가리킨다.
`mixreq_readout.read_session` 이 `validated.device_dir` 를 따라 13:38 의 device 산출물 (requests.json · summary · progress) 을 읽어 13:22 행에 넣었고, `m7_table.session_rows` 는 그 readout 과
`start_band.jsonl` (label index21 · attempt 2 → 마지막 기록 = 13:38) · run log (같은 index · attempt 2 → 마지막 start) 를 attempt 로만 찾아 13:38 값을 13:22 행에 넣었다.
`m6_readout` 은 세션 JSON 을 `21_C_a2.json` 한 이름으로 쓰므로 뒤에 처리된 screenoff 폴더 (folder 열만 13:22) 가 13:38 폴더의 JSON 을 덮어썼다 (readout_S26_M7_S/sessions/21_C_a2.json).

| 열 | 13:22 행 값 (session_table_m7.csv) | 실제 13:22 (원시) | 비고 |
|---|---|---|---|
| start_time | 2026-10-14T13:22:03 | 13:22:03 (host/session_log — 맞음) | 13:22 고유 |
| end_time | 2026-10-14T13:22:05 | 13:22:05 (맞음) | 13:22 고유 |
| start_SKIN | 27.7 | 27.0 (driver start_state 12:59:44) · 띠 마지막 폴 25.9 (13:22:00) | **섞임 (13:38 값)** |
| start_AP | 25.7 | 25.2 / 23.7 | **섞임 (13:38 값)** |
| start_BAT | 25.9 | 24.4 / 22.7 | **섞임 (13:38 값)** |
| start_SOC | 74 | 75 | **섞임 (13:38 값)** |
| band_result | out_of_band_after_wait | out_of_band_after_wait (13:22 띠 대기 끝 — 같음) | 같은 값 (우연 · 섞임 아님) |
| previous_run | S6-C | S6-C a1 (11:05:09 끝) | **섞임 (13:38 값)** |
| gap_s | 978 | ≈ 8,210 (11:05:09 → 13:21:59) | **섞임 (13:38 값)** |
| charge_end_to_start_s | 3540.8 | 2,538.8 (12:39:44 분리 → 13:22:03) | **섞임 (13:38 값)** |
| hal_cont_path | C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6\results\S26_M7_HAL\hal_cont_S6-C_a2.csv | 같은 파일 이름 hal_cont_S6-C_a2.csv 에 12:59 ~ 13:22 구간이 이어 쓰임 (13:29 · 13:36 재시작 포함) | **섞임 (13:38 값)** |
| power_coverage_after_last_available_s |  | null (lane_available 0) | 13:22 고유 |
| hal_coverage_after_last_available_s |  | null | 13:22 고유 |
| last_lane_available_s | 710.514533438 | null (요청 0 dispatch) | **섞임 (13:38 값)** |
| completed | 3000 | 0 | **섞임 (13:38 값)** |
| urgent_p95_ms | 451.250821 | null | **섞임 (13:38 값)** |
| normal_p95_ms | 72856.771953 | null | **섞임 (13:38 값)** |
| deadline_met | 2295 | null | **섞임 (13:38 값)** |
| focus_apps | NotificationShade | NotificationShade (phone_watch 13:22 — 맞음 · 화면 꺼짐) | 13:22 고유 |

readout_S26_M7_S/sessions/21_C_a2.json: `folder` 만 screenoff 폴더 · `service` (3000/3000 · 긴급 P95 451.25) · `last_lane_available_s` 710.51 · `energy` · `thermal` · `summary` · `validated_rules`(eligible false 는 screenoff) 가 13:38 device 산출물 — 한 파일에 두 시도가 섞임.
readout_S26_M7_S/inventory.csv: index 21 attempt 2 행 2개 중 screenoff 행의 urgent_p95_ms · normal_p95_ms · deadline_met · completed · overlap_s · last_lane_available_s 가 13:38 값 (eligible False · reasons 는 13:22).

정정 = `s_sessions_resolved.csv` (folder + command_id + device app start + host start 한 행씩 · 원시 두 폴더 그대로). 원본 CSV · readout · 폴더는 고치지 않았다.
