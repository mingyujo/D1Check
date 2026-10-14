# m8_instrumentation_check — 계측 확인 항목 (조민규 §5 · REQUEST P0-2 · 프롬프트 B-3 3) · 2026-10-14 · **전부 `미확인` (폰 0 단계) → D-1 스모크에서 `m8_probe.ps1` 로 지원/미지원 기록**

| 항목 | 상태 (B 단계) | 확인 방법 (실행 명령 · `m8_probe.ps1` 항목) | 오버헤드 측정 방법 (스모크 ID · 예산 원장) |
|---|---|---|---|
| Perfetto battery counters (`android.power` · battery_poll_ms 900 · power rails) | `미확인` (S26 user 빌드 · traced 데몬 · 데이터소스 노출 여부) | `perfetto --version` · `ps -A \| grep traced` · `perfetto --query \| grep android.power` (probe) → 지원이면 `adb shell perfetto -c perfetto_battery.cfg --txt -o …` (`m8_driver.perfetto_start` · P0 PERFETTO_ON) | P0 계측: L64 BASE off 1 · on 1 (같은 bank · 같은 게이트) — off/on 의 앱 power 표본 간격 · 결측 · host HAL cmd_ms 차이 (기록만 · "계측 동등성 정밀 검증" 아님) |
| CPU 주파수 (`/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq` · `policy*/scaling_cur_freq`) | `미확인` (읽기 권한 · 값 갱신) | probe `cpu_scaling_cur_freq` · `cpu_policy_cur_freq` · `cpu_online` (1회 읽기 · rc · ms 기록) | 지원이면 hal_cont 에 열 추가는 **다음 판** (지금은 1회 probe 만 — 모든 비교군 계측 조건을 같게 두기 위해 블록 중간에 켜지 않음) |
| GPU 주파수 (경로 후보: `/sys/kernel/gpu/gpu_clock` · `/sys/devices/platform/*.mali/clock` · `/sys/class/devfreq/*/cur_freq` · `/sys/class/misc/mali0/device/clock` · kgsl 은 Qualcomm 용) | `미확인` | probe `gpu_freq_candidates` · `gpu_devfreq` | 같음 |
| NPU 주파수 (경로 후보: `/sys/class/npu/npu0/*` · `/sys/devices/platform/*npu*/clock` · devfreq) | `미확인` | probe `npu_candidates` | 같음 |
| ADPF thermal headroom (`PowerManager.getThermalHeadroom(forecastSeconds)` · ≥ 10 s 간격 · 미지원 NaN = 결측) | `미확인` — **앱 API 이므로 M8-apk v1 에 미통합** (sampler 변경 = 모든 행에 영향 · 기존 행 보존 원칙) · `dumpsys thermalservice` 에 headroom 줄이 있으면 호스트에서 10 s 폴 | probe `thermal_headroom_dumpsys` | 앱 통합은 별도 판 (`BatterySampler` 변경 = sampler 영역 → M6/M7 행 보존과 충돌 → 새 sampler 행 분기 필요) · 질문으로 적음 |
| `thermal_status` (`PowerManager.currentThermalStatus`) | 지원 (앱 표본마다 · M6/M7 실측 0 ~ 2) | — | — |
| HAL AP/SKIN/BAT/PA (`dumpsys thermalservice`) | 지원 (읽기 2.3 s · 0.1 ℃ · 갱신 시각 미제공 · 값 변화 간격 AP 2.6 · SKIN 3.5 s 중앙 [P M6 E-T]) | hal_cont (`m7_hal_cont.ps1` 그대로) | 호스트 읽기 부하 (dumpsys) = 세션 hal.csv 2 s 와 두 겹 (M7 §7-2 와 같음) |
| 내부 전류/전압/전하 (`BatteryManager`) | 지원 (CURRENT_NOW µA 방전 음수 · CHARGE_COUNTER µAh · EXTRA_VOLTAGE mV · ENERGY_COUNTER 미지원 · sysfs 앱 읽기 불가 [P M6 E]) | 앱 900 ms (위상 기록) | 읽기 주기 ≠ 값 변화 간격 ≠ 센서 갱신 시각 (미제공) — 셋을 나눠 적음 · 30.6 s 계단은 M6 E 조건 관찰 (일반화 0) |
| `/sys/class/power_supply/battery/*` (셸) | `미확인` (앱에서는 FileNotFound · 셸 권한 다를 수 있음) | probe `power_supply_sysfs` | — |
| 외부 전력계 | 없음 | — | 내부 gauge 상대 비교 한계 명시 |
| CPU threads 실제 worker | `미확인` (설정 1 · `top -H` 파서 미완) | probe `top_threads_runner` (세션 중 1회) | 설정값 열과 관측 열 분리 |

- 규칙 (session_m8.json): 지원 · 미지원 · 미확인 셋 중 하나로만 남긴다 · 모든 비교군 (DEV · CONFIRM) 의 계측 조건을 같게 (P0 에서 정한 on/off 를 블록 중간에 바꾸지 않음) · 고빈도 polling 무조건 적용 금지.
- 산출: `results/S26_M8_PROBE/probe_<tag>_<ts>.txt` (rc · ms · 원문 · 시리얼 가림) → D-1 끝에 이 표의 상태 열을 갱신한 `m8_instrumentation_check_v2.md` (원본 보존).
