# m8_instrumentation_check_v2 — D-1 probe 결과 반영 (2026-10-14 23:57 · `results/S26_M8_PROBE/probe_d1b_20261014_235713.txt` · 읽기만 · v1 원본 보존)

| 항목 | 상태 [P probe] | 근거 | 다음 |
|---|---|---|---|
| Perfetto battery counters (`android.power`) | **지원 후보** — `perfetto --version` v54.0 · `traced` · `traced_probes` 실행 중 · `perfetto --query` 에 `android.power` (traced_probes) 데이터소스 등록 | probe `perfetto_*` | P0 PERFETTO_ON (L64 BASE) 에서 `adb shell perfetto -c m8_perfetto_battery.cfg --txt` 실제 기록 · pull · 크기 → 지원/미지원 확정 · off 세션과 앱 표본 간격 · 결측 · cmd_ms 비교 (기록만) |
| CPU 주파수 | **지원** — `/sys/devices/system/cpu/cpu0..9/cpufreq/scaling_cur_freq` 읽힘 (유휴 672,000 ~ 2,208,000 kHz · policy0/3/6/9 · online 0-9 · 1회 324 ms) | probe `cpu_*` | 연속 기록 열 추가는 다음 판 (블록 중간에 계측 조건 바꾸지 않음) · 세션 중 1회 읽기만 (오버헤드 ≈ 0.3 s/회) |
| GPU 주파수 | **부분** — `/sys/kernel/gpu/gpu_clock` 읽힘 (유휴 0) · mali/kgsl/g3d 경로 없음 · devfreq 권한 거부 | probe `gpu_*` | 부하 중 값 확인 (P0 기능 세션 중 1회 읽기 — 블록 밖) |
| NPU 주파수 | **미지원 (셸 권한)** — `/sys/class/devfreq/17000030.devfreq_npu0 · 17000040.devfreq_npu1` 존재하나 `cur_freq` Permission denied · npu/dsp sysfs 없음 | probe `gpu_devfreq` · `npu_candidates` | 경로는 확인 · 값은 root 없이 불가 → 미지원 기록 |
| ADPF thermal headroom | **미확인 (앱 API 미통합)** — `dumpsys thermalservice` 에 'Temperature headroom thresholds [NaN, 0.833, 0.9, 1.0, 1.067, 1.5, 2.5]' (문턱만 · 현재 headroom 값은 앱 `getThermalHeadroom` 필요) | probe `thermal_headroom_dumpsys` | sampler 분기 (M8 행만) 다음 판 · 질문 #5 |
| thermal_zone sysfs | 미지원 (Permission denied · M6 와 같음) | probe `thermal_zones` | HAL (dumpsys) 그대로 |
| `/sys/class/power_supply` (셸) | 미지원 (Permission denied · 앱도 FileNotFound) | probe `power_supply_sysfs` | BatteryManager API 그대로 |
| CPU threads 실제 worker | 미확인 (probe 시각에 앱 미실행 → `top -H` 행 0) | probe `top_threads_runner` | 세션 중 `top -H` 1회 (mixreq_session `top_h.txt` 가 세션마다 남김 · 파서 다음 판) |
| HAL AP/SKIN/BAT/PA · BatteryManager · thermal_status | 지원 (M6/M7 실측) | — | 그대로 |

- 규칙 유지: 지원 · 미지원 · 미확인 셋 중 하나 · 모든 비교군 계측 조건 같게 (P0 에서 Perfetto on/off 2세션만 다름 · DEV/CONFIRM 블록은 전부 off).
- 1차 probe (`probe_d1_20261014_235638.txt`) 는 스크립트 따옴표 오류로 셸 명령이 깨진 기록 (보존 · 사용 안 함).
