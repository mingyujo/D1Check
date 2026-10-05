# S26 export 20261005 — 조민규 §6 4묶음 (PC export, 기기 재측정 없음)

> 형식 기준: `origin/feature/arrival-scheduling-20260923:docs/team/S26_SCOPE_AND_INTERFACE_20261004.md` §6 (읽기만 — fetch + show, checkout 없음; 읽은 원격 HEAD `da5d798`).
> 약속 범위: 수락 회신 (`할일_1004.md` 8-4 "네 §6 4묶음 형식으로 10/5 에 올릴게") + 10/4 회신 (`HANDOFF_REPLY_20261004.md` §2 — 10/2·10/3 26실험 최소 export · C2 전기 원 시계열 · `sim\out_0928` · 구간별 귀속표).
> 생성기 `s26/tools/export_1005/make_export_20261005.py` — **구간 귀속 규칙을 표 생성 전에 커밋** (`2b1f06f` 14:23:29), 그 뒤 실행. results\ 는 읽기만.
> 표기: [P] 생성기 출력 · [D] 인용 · [E] 추정 · `미확인` · `missing`. **이 export 는 pilot·개발 자료다 — 정책 효과·검증 주장 없음. J 없음 (S26 J 미적격, `S26-THERMAL-SCOPE-02`).**

## 0. 범위

| 묶음 (그의 §6) | 10/2 · 10/3 26실험 | 10/4 · 10/5 런 | 파일 |
|---|---|---|---|
| 1 런 manifest/receipt/validation | 26 (EffN600 은 러너 JSONL 없음 — 안전 중단, 행만) | — | `b1_runs.csv` · `b1_runs.json` |
| 2 센서 표 (원표본) | 25 런 × (HAL · d1check) | — | `sensors/<실험>__thermal.csv` · `__d1check.csv` · `b2_sensor_inventory.csv` · `b2_files_sha256.csv` |
| 3 구간/요청 표 | 45 구간 · 전환 20 · 구간 귀속 45 | — | `b3_segments.csv` · `b3_transitions.csv` · `b3_attribution.csv` (+ 첫 실행 `b3_attribution_run1_labelbug.csv`) |
| 4 모형/정책 + raw inventory | 26 실험 파일 | **inventory 만** (N50P · G50P · GI300 · NI300 · EffN420 · EffB2 8 · N50P2 · NI300r2 · G50P2) | `b4_model_policy.md` · `b4_raw_inventory.csv` (904 파일 · 14.6 GB — 파일명·bytes·sha256 만) |
| C2 전기 원 시계열 + 판정 | C2 20런 (EffNet NPU, 9/28) | — | `c2_sensors/<run>__d1check.csv` · `__thermal.csv` · `c2/` (= `sim\out_0928` 사본 + `c2_analyze_0928.py`) |

- **원시 파일 (러너 JSONL · merged · logcat · 모델) 은 Git 밖**에 그대로 있다 — `b4_raw_inventory.csv` 의 해시로 대조한다. 그의 §6 "세부 불일치 재현에 필요한 런만 원본 요청" 그대로. **logcat 은 iccid·eSIM 줄이 있어 공유하지 않는다 (해시만).** 모델 바이너리 없음.
- 주소·시리얼 0: 생성기가 내보내는 모든 값을 `([0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}|R3KL[0-9A-Z]{7}` 로 검사하고 걸리면 멈춘다 · `experiment_manifest.json` 의 `device.serial`·fingerprint 는 복사하지 않는다 · `device_anon_id = S26-1`.

## 1. 묶음 1 — `b1_runs.csv` (실험당 1행)

열: `experiment` · `date_group` · `device_anon_id` · `device_model` · `role` (전부 "pilot · 개발 자료") · `slot_status` · `validation_status` · `meta_*` (러너 `run_metadata` 화이트리스트: engine · litert_version · model_sha256 · precision · npu_accelerator_requested · npu_dispatch_lib_sha256 · npu_input_sha256 · npu_latency_boundary · npu_model_partition · cpu_threads · chain_* · pilot_* · energy_measurement …) · `load_start/end_mono_ns` · `load_start/end_wall_ms` (가장 가까운 러너 이벤트의 (mono, wall) 쌍으로 환산) · `planned_s` · `actual_load_s` · `completed_inference_count` · `inference_events`.
- APK hash: manifest·run_metadata 에 없다 → `installed_apk_note` 에 "npu-runner 설치본 `5ac485e3…` (10-02 23:56:58 이후) · 미확인" 로만 [D CLAUDE.md].
- CPU threads: npu-runner (CompiledModel) 는 `cpu_threads None` 을 기록한다 → 값 그대로 (`unknown`).
- delegate 귀속은 묶음 3 의 구간 표에서 — **구간 0 증거로 이후 구간을 인증하지 않는다.**

## 2. 묶음 2 — 센서 원표본

- `sensors/<실험>__thermal.csv`: thermalservice HAL 표본 원행 — `mono_ns` · `sample_before/after_mono_ns` · `sampling_uncertainty_ns` · AP · BAT · PA · SKIN (℃, HAL 문자열 그대로) · `thermal_status` · `parse_status` · `missing_sensors` · `analysis_phase`. 보간·요약 없음.
- `sensors/<실험>__d1check.csv`: d1check 표본 원행 — `mono_ns` · `wall_ms` · `elapsed_s` · `tick` · `current_raw` · `current_valid` · `voltage_mV` · `charge_counter_raw` · `charge_valid` · `plugged` · `battery_temp_C` · `thermal_status` · `headroom_now` · `analysis_phase`.
- **단위 해석**: `current_raw` = 원 정수 — µA 로 읽고 음수 = 방전으로 쓴다 **[E — 기기 문서 미확인; manifest `current_raw_policy raw_unscaled_unit_unverified`]** · `charge_counter_raw` = µAh 로 읽음 (계단 4,275 [P C2 gcd]) · sample age = HAL 행의 `sample_before/after` 와 `sampling_uncertainty_ns` (d1check 는 `elapsed_s`·`tick`).
- `b2_sensor_inventory.csv`: 런별 표본 수 · 중앙 간격 · 최대 공백 · 공백 > 3×중앙 수 · parse 실패 · current/charge invalid · plugged ≠ 0 수. 26실험 합: plugged ≠ 0 **0** · HAL 공백 > 3× **2** · d1check **4** [P].
- 1 s 요약을 쓰는 우리 규칙 = `d1sim/tools/extract_traces_v1.py` docstring (1 s 칸 = 그 칸 안 마지막 HAL 표본, 없으면 직전 · 전력 = −current_raw × voltage_mV / 1e9, current_valid 만 · 10 s 칸 HAL = 칸 시작에 가장 가까운 표본).
- **C2 계산·판정 코드**: 에너지 = `s26/tools/s26_energy.py` (레포에 이미 있음) · 판정 = `c2/c2_analyze_0928.py` (SHA `f21afc99…`) · 결과 = `c2/C2.json`·`C2.md`·`energy_*.csv` · 적분창 = baseline 60 s · load · cooling (CSV 열 그대로) · 허용오차 = `s26/docs/MEASUREMENT_DEFINITION.md` §10 (사후 등록 — CPU/GPU 80런 내부 일관성 FAIL, 절대 정확도 미인증) [D]. **1 Hz 온도·전류만으로 J 를 재현할 수 있다고 하지 않는다.**

## 3. 묶음 3 — 구간 · 전환 · 귀속

- `b3_segments.csv`: 실험 · 구간 · label · 가속기 · 요청 duty · 계획 s · `start/end_mono_ns` · `start_wall_ms` · 실제 s · 추론 수 (창 안 · segment_end `inference_count` 가 있는 체인 구간은 전부 일치 [P]) · 종료 사유 · 지연 정의 (`npu_latency_boundary`: NPU·CompiledModel = writeFloat+run+readFloat) · P50 · P95 (nearest-rank `sorted[ceil(.95n)−1]`).
- `b3_transitions.csv`: 전환 20개 — 방향 · backend_switch · model_initialized · warmup · 전체 ms · env/model/buffer init ms · `unexplained_ms` = 전체 − (env + model + buffer) = **110~214 ms** [P]. ⚠ 이 정의에는 warmup 20 회가 들어 있다 — 10/2 보고의 "미설명 50~99 ms" (다른 정의) 와 숫자를 섞지 않는다.
- **`b3_attribution.csv` — 구간별 delegate 귀속** (규칙 = 생성기 docstring, 커밋 `2b1f06f` 에서 표 전에 고정):
  - 러너 PID (D1GPU 를 찍은 PID) 의 logcat 줄 · 구간 창 = [구간 0: run_metadata 시각 · 구간 i: 전환 i 시작] ~ 구간 끝 · 줄 시각 = 기기 현지 시각 (KST) · 셈: LITERT_CL 교체 줄 (GPU) · DispatchDelegate 교체 줄 (NPU) · 그 밖 교체 줄 · ENN 줄 · 실패/fallback 줄
  - 판정: 기대 가속기 교체 줄 ≥ 1 · 다른 가속기 줄 0 · 실패 0 → PASS · 교체 줄 0 이고 전환 `model_initialized false` → "재사용 — 구간 고유 증거 없음 (판정 안 함)" · 그 밖 FAIL
  - **결과 [P]: PASS 30 · 재사용 (판정 안 함) 11 · FAIL 4.** 재사용 11 = 같은 가속기·같은 모델로 이어지는 체인 구간 (M1-GPU · GPU 페이싱 · M1-GPU r2 · M1-NPU a·b 의 구간 1~) — 이 구간들의 delegate 는 **구간 고유 증거로 인증되지 않는다** (그의 §6 그대로).
  - **FAIL 4 = EffB1 CPU 4런**: 그 창에 `Replacing 62 out of 62 node(s) with delegate (TfLiteXNNPackDelegate)` 1줄 — CPU 자신의 XNNPACK 위임이다. 고정 규칙에 **CPU 기대 줄 범주가 없었다** (GPU·NPU 만 정의) → 규칙대로 FAIL 로 남긴다 (표를 본 뒤 규칙을 고치지 않는다). 다음 판에서 CPU 범주를 결과 전에 정한다.
  - **첫 실행의 구현 버그 (기록)**: 단일 런의 기대 가속기를 `run_metadata.resource` 로 읽었는데 npu-runner 는 이 필드를 항상 `NPU` 로 쓴다 → CPU·GPU 단일 런 9개가 FAIL. 규칙 문장 ("런 자원") 대로 실제 요청 가속기 `npu_accelerator_requested` 로 고쳐 다시 만들었다. 첫 실행 표 `b3_attribution_run1_labelbug.csv` 보존.
- **요청 ledger (V3)**: `missing` — S26 에는 아직 요청 경로 (예정 도착·enqueue·dispatch~lane_available) 가 없다. V3 를 구현하면 그의 §5 경계 7개 + 필수 필드로 낸다.

## 4. 묶음 4 — `b4_model_policy.md` · `b4_raw_inventory.csv`

- 모형 v2 동결·홀드아웃·오차·실패, v2.1 (오늘), 정책 결과 전 등록 (오늘, 시뮬 실행 전) — `b4_model_policy.md`.
- raw inventory: 실험 폴더 아래 모든 파일의 상대 경로 · bytes · sha256 (`scope` = full export / inventory only / C2 electrical · logcat 은 note "공유 금지, 해시만").

## 5. 재현

```
py s26\tools\export_1005\make_export_20261005.py --repo-out s26\exports\20261005 --git-out <Git 밖 폴더>
```
(`--skip-inventory` 면 묶음 4 해시 목록을 건너뛴다. 센서 표는 git-out 에 만들고 이 폴더로 복사했다 — `b2_files_sha256.csv` 가 git-out 경로 기준 해시.)

## 6. 한계

전부 pilot·개발 자료 · 1~2런 칸 · 전류 단위 미확인 · 에너지 절대 정확도 미인증 · 구간 귀속은 logcat 시각 (ms) 과 러너 (mono, wall) 쌍 환산에 기댄다 (창 경계 근처 줄은 어긋날 수 있다 [E]) · EffN600 은 러너 JSONL 이 없어 표 없음 · 10/4·10/5 런은 inventory 만 (표는 다음 export).
