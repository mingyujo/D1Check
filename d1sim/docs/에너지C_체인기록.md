# 에너지 C 체인 기록 — 같은 일 B 체인 · 기한 인자 · dry-run · 칸 이름 (P1i 1-4, 2026-10-08 03:1x ~ 03:3x · 에너지 C 칸 0)

> 등록: `에너지_사전등록_v1.md` §6 (SHA 01314501…) + `에너지_사전등록_v2.md` (782b97a7…) · 원장 `sim\out_energy\freeze_energy.txt`. 표기 [P] 실측 · [D] 인용.

## 1. 체인 (새 파일 하나 — 기존 체인 수정 없음) · canonical SHA-256 [P `py tools\npu_chain.py validate`, exit 0]

| 칸 | 파일 (`tools\chains\`) | 구간 (label · 자원 · duty · s) | Σ s | canonical SHA-256 | 파일 SHA-256 |
|---|---|---|---|---|---|
| NAc (A) | `npu_eff_work100_v1.json` (그대로) | work_d100 NPU 100·300 → tail_idle NPU 1·600 | 900 | `4433e25923aa7aacfaa5f123466135e145b10100e27c7d416874abab8337f09c` | `ef9982ed17d010a447074d2930549558193170a61e321a5315139a02d10b02d0` |
| NBc (B) | **`npu_eff_work50eq_v1.json` (새)** | work_d50 NPU 50·**620** → tail_idle NPU 1·**280** | 900 | `ba74ed03e26ec5d7132c430504af544f6c9a7a0336c8a382ba715ecd2c12b4fa` | `bf3662e4807f4e90533a86ffd36150c7a42099cc1dfbdf9b7d0e7828dafa26de` |
| 스모크 N | `smoke_npu_eff_v1.json` (그대로) | work_d100 NPU 100·30 → tail_idle NPU 1·30 | 60 | `82ce7744d47c8fa783d46f86fa105a4ed62883d84e8cc44d2a451bca2a906eeb` | `ef42f0e3e7e7279ee5ca23b17a05b1641b1c6c83c8f2622986786e3bf6591ced` |

- 생성 `s26\tools\energy_1008\make_chain_c.py` [P]: ① 기존 `tools\chains\*.json` 33개를 `json.dumps(indent=2, ensure_ascii=False) + "\n"` 로 재직렬화 → **33/33 바이트 동일** ② `npu_chain.load_chain` 으로 틀 `npu_eff_work50_v1` canonical `168a5b53…` · A `4433e259…` · 스모크 `82ce7744…` 확인 ③ 같은 `build()` 에 틀 자신의 값 (660 / 240) 을 넣으면 틀 파일과 **바이트 동일** ④ `chain_id` → `npu_eff_work50eq_v1` · `duration_s` 660 → 620 · 240 → 280 만 바꿈 (duty 는 assert 로 50 · 1 확인).
- 틀과의 `git diff --no-index`: 바뀐 줄 = `chain_id` · 두 `duration_s` 뿐 [P]. 모델 `models/efficientnet_lite0_Samsung_E9965.tflite` · 입력 `lcg-rgb-127-128` · `per_segment` 그대로.

## 2. 기한 인자 (`밤1005e_체인기록.md` §2 의 NAe · NBe 행 · 스모크 N 행 그대로)

| 칸 | `--duration` | `--npu-max-inference-spans` | `--runner-timeout-seconds` | `--logger-exit-timeout-seconds` | `--analyze-timeout-seconds` | `--cooling-min-seconds` |
|---|---|---|---|---|---|---|
| NAc · NBc | 900 | 1,000,000 | 2700 | 1800 | 600 | 600 |
| 스모크 N | 60 | 100,000 | 900 | 600 | 300 | 60 |

명령 틀 (`밤1005e_체인기록.md` §2 그대로 — 체인 · 폴더만 바꿈):

```
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --npu-chain tools\chains\<체인>.json --duration <Σ> --npu-max-inference-spans <상한> --runner-timeout-seconds <r> --logger-exit-timeout-seconds <l> --logger-keep-files-open --analyze-timeout-seconds <a> --cooling-min-seconds <c> --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\<폴더>
```

## 3. orchestrator `--dry-run` [P 03:2x, `--serial 0.0.0.0:0` 가짜값 · 출력 스크래치 — 커밋 안 함 · `s26\tools\energy_1008\dryrun_table_c.py`]

| 칸 | exit | duration_s | chain_id | total | canonical (앞 8) | 파일 (앞 8) | 상한 | 구간 모델 SHA |
|---|---|---|---|---|---|---|---|---|
| NAc | 0 | 900 | npu_eff_work100_v1 | 900 | 4433e259 | ef9982ed | 1,000,000 | 311e4aac × 2 (10,033,376 B) |
| NBc | 0 | 900 | npu_eff_work50eq_v1 | 900 | ba74ed03 | bf3662e4 | 1,000,000 | 311e4aac × 2 |
| 스모크 N | 0 | 60 | smoke_npu_eff_v1 | 60 | 82ce7744 | ef42f0e3 | 100,000 | 311e4aac × 2 |

run_cell 의 실행 직전 검사 (dry-run 파일에서 `"sha256": "<canonical>"` 1줄 · `"duration_s": <Σ>,` 1줄) 를 세 칸 모두 만족 [P].

## 4. 칸 이름 · 폴더 · 순서 (등록 §6-3 · Cowork 10/8 결정)

| 세션 | 칸 순서 (드라이버 dry-run [P]) | 폴더 | 판정기 출력 |
|---|---|---|---|
| C1 | 스모크 N → NAc_b1 → NBc_b1 → NBc_b2 → NAc_b2 → NAc_b3 → NBc_b3 → NBc_b4 → NAc_b4 | `results\S26_<칸>_b<k>_1008c` · `S26_smokeN_1008c` | `sim\out_1008c\` |
| C2 | 스모크 N → NAc_b5 → NBc_b5 → NBc_b6 → NAc_b6 → NAc_b7 → NBc_b7 → NBc_b8 → NAc_b8 | `…_1009c` | `sim\out_1009c\` |

- 블록 k 홀수 = A → B · 짝수 = B → A. 모자란 블록은 `-Blocks "<k>,…"` 로 그 블록만 (두 칸 모두).
- 게이트 라벨 `NN_<칸>_b<k>` (C1 01 부터 · C2 는 `-SeqStart` 로 이어 씀). 재시도 · 감시 재측정 = `…_re`.

## 5. 드라이버 c (운영 helper — 측정 코드 · 판정 무변경) `s26\tools\energy_1008\`

| 파일 | 출처 | 바꾼 곳 |
|---|---|---|
| `session_driver_c.ps1` | `v3_1006\session_driver_v3b.ps1` | ① `-Session C1\|C2` 칸 표 · 거울 순서 · `-Blocks` ② 칸 0 스모크 N (상한만 · 판정 밖 · 실패해도 계속) ③ 하한 미달 → 바꾸지 않고 "하한 미달" 표시 실행 (`mark`) ④ 블록 시작 SOC ≥ 45 · 지금 + 85 분 ≤ 세션 끝 · 세션 첫 측정 칸 SOC ≥ 85 · 블록 둘째 칸 SOC 하한 30 ⑤ 밝기 0 고정 · 원래 값 `brightness_orig_c.json` (처음 한 번만 기록) · 끝에 원복 ⑥ 멈춤 · 재연결 · 재시도 = v3b ⑦ 감시 = v3b ⑧ 칸마다 `night1005e_judge_c.py run` · watchcheck · 모델 SHA · `energy_judge_v1.py qc` (E 숫자 없음) · 쌍 · cond 없음 |
| `run_cell_c.ps1` · `launch_cell_c.ps1` · `dryrun_c.ps1` · `stall_watch_c.ps1` · `start_watch_c.ps1` · `stall_selftest_c.ps1` | 같은 이름 `_v3b` | 호스트 폴더 `S26_host_energy_1008` · CSV `*_c` · helper 경로만 (`copy_helper_c.py` 로 정확 치환) |
| `restore_c.ps1` | `restore_v3b.ps1` | + 밝기 원복 · keep-awake 정지는 `-Full` 때만 |
| `keepawake_c.ps1` · `keepawake_c_screen.ps1` | `keepawake_v3b.ps1` · `keepawake_v3c.ps1` | 호스트 폴더 · 정지 파일 이름 |

- 멈춤 경로 시험 `stall_selftest_c.ps1` **3/3 PASS** [P 03:21 ~ 03:25 — T1 멈춤 68 s · T2 정상 종료 (열린 파일 쓰기 중 거짓 멈춤 없음) · T3 상한 98 s].
