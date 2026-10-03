# EffNet 개발 블록 사전 등록 — v1 (2026-10-04 03:2x KST, 6단계 측정 전 동결) — 조민규 방식

> **사전 등록 커밋 `5d7681aa81f0c2c021d9f3094e495eafb84368ed` 2026-10-04 03:31:41 KST** (레포 사본 `s26\results\night_1003\EFFNET_BLOCK_PREREG_v1.md`). 이 줄은 커밋 뒤 OneDrive 원본에만 덧붙였다. 6단계 시작 전.

> 설계 출처: `조민규_실험설계_GitHub확인_1003.md` §1·§3 (개발 블록 → 동결 → 확인 블록, 재보정 없음 · 세션 = 블록 · 블록 안 거울 순서 · 범위 밖 = unsupported · 블록 수·조건·중단 규칙을 첫 결과 전에 고정). 명령 원형 = `측정절차_연쇄모드_0928.md` §7 (EfficientNet × CPU · × GPU).
> 이 파일이 든 커밋 SHA·시각이 동결 증거. 결과 뒤 고치지 않는다 (`_v2`). 표기: [P] 실측 · [D] 인용 · [E] 추정 · `미확인`.
> **개발 블록이다 — 확인 블록(10/4 밤) 전에는 결론이 아니다.** CI·검정력 주장 없음.

## 1. 설계

- **한 세션 = 한 블록. 8런, 거울 순서** (셀마다 평균 순번 4.5 — 선형 표류만 산술적으로 상쇄; 비선형·잔열·carryover 는 남는다):

| 순번 | 셀 | 자원 · duty | preflight |
|---|---|---|---|
| 6-1 | C50 | CPU d50 | off |
| 6-2 | C100 | CPU d100 | off |
| 6-3 | G50 | GPU d50 | **required** (GPU 품질 게이트 1회) |
| 6-4 | G100 | GPU d100 | off |
| 6-5 | G100 | GPU d100 | off |
| 6-6 | G50 | GPU d50 | off |
| 6-7 | C100 | CPU d100 | off |
| 6-8 | C50 | CPU d50 | off |

- 런마다 orchestrator 1회 (`--duty-cycles X --repeat 1`) — 순서를 명령으로 고정. 런 사이 = 칸 시작 게이트 (`s26_start_gate.py`, HAL SKIN ≤ 32 · AP ≤ 32 · BAT ≤ 30 · plugged 0 · SOC 30~90). 모든 런 60 s · warmup 20 · seed 20261003 · `--npu-run-only-span` · 입력 `lcg-rgb-127-128` · 모델 `/data/local/tmp/efficientnet_lite0.tflite` (SHA `6c7ab0a6…8bde0`, 18,582,189 B — 0단계 기기 확인 [P]).
- **확인 블록 (10/4 밤, 지금 고정)**: 같은 8셀을 **자원 순서를 바꾼 거울** — G50 → G100 → C50 → C100 → C100 → C50 → G100 → G50. **재보정 없음** · 판정은 두 블록을 나란히 · **블록 수 2** (9번째 런·3번째 블록 없음 — 결과가 아슬아슬해도 늘리지 않는다).
- **블록은 한 세션 안에서 끝낸다** — 6단계 시작 SOC ≥ 45 (프롬프트 예산표: ~10 %p + 30 + 5) 가 안 되면 블록 전체를 다음 밤으로 (반만 하지 않는다). 시각 조건: 지금 + 1.7 h + 30 분 ≤ 10:00 (영훈 회수 시각).

## 2. 명령 (6-1 CPU 원형 · 6-3 GPU 원형) — dry-run 03:1x 전부 exit 0 [P]

```bat
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --mode pilot --resources NPU --npu-accelerator CPU --npu-model-path /data/local/tmp/efficientnet_lite0.tflite --npu-model-sha256 6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0 --npu-model-size 18582189 --npu-timed-input-spec lcg-rgb-127-128 --npu-run-only-span --accuracy-preflight off --duty-cycles 50 --duration 60 --warmup 20 --repeat 1 --seed 20261003 --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 1800 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_EffB1_01_cpu50_1003
```

```bat
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --mode pilot --resources NPU --npu-accelerator GPU --npu-gpu-precision FP32 --npu-model-path /data/local/tmp/efficientnet_lite0.tflite --npu-model-sha256 6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0 --npu-model-size 18582189 --npu-timed-input-spec lcg-rgb-127-128 --npu-input-spec lcg-rgb-127-128 --npu-reference-path /data/local/tmp/efficientnet_lite0.tflite --npu-run-only-span --accuracy-preflight required --gpu-profile gpu-fp32-strict-v1 --duty-cycles 50 --duration 60 --warmup 20 --repeat 1 --seed 20261003 --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 1800 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_EffB1_03_gpu50_1003
```

- 나머지 6런 = 위 원형에서 `--duty-cycles` · 폴더 (`S26_EffB1_<순번 2자리>_<cpu|gpu><duty>_1003`) 만. **GPU 6-4·6-5·6-6 은 `--accuracy-preflight off`, 품질 게이트 인자(`--npu-input-spec` · `--npu-reference-path` · `--gpu-profile`)는 그대로 둔다** — 1-B dry-run 에서 `validate_cli` 가 `off` 와 함께 받았고 (exit 0), 6-3 과 폰 쪽 인자를 같게 유지하기 위해 (차이 = `--accuracy-preflight` 하나). dry-run 대조: 인자를 빼면 `config.npu.quality_gate.input_spec` 만 `lcg-unit` 으로 바뀌고 `timed_input_spec` 은 같다 [P].
- **GPU 품질 게이트 (6-3 만 required, C2 방식)**: preflight 결과 파일 생성 뒤 **25 s 뒤 `runs\` 0개 확인 → orchestrator 정지 → 칸 게이트 → 같은 명령 + `--resume`** (`C2_결과_0928.md` §1 "계획된 중단"). 기준 = 절차서 §7: **cosine_min ≥ 0.99 가 실질 기준** (합성 입력 32개가 EffNet 에서 전부 argmax 21 [P C2] → argmax 32/32 는 약한 증거) · **비트 동일 = 실패** (CPU 로 돈 것). `required` 는 benchmark-runner 의 MobileNet CPU↔GPU 검사도 돌린다 (EffNet 과 무관, 실패해도 칸을 막는다 — `--gpu-profile gpu-fp32-strict-v1`).
- **게이트 실패 갈림길**: 6-3 품질 게이트 FAIL → **GPU 4런 하지 않음**, 블록은 CPU 4런 (6-1·6-2·6-7·6-8) 으로 끝낸다 (기록).
- **런 실패**: 60 s 블록 런이 실패하면 같은 런을 **1회 재시도**, 또 실패면 그 런 **결측**으로 두고 블록 순서를 계속 (재시도·결측을 표에).

## 3. 분석 (지금 고정) — 고정 스크립트 `sim\night1003_judge_effblock.py`

- SHA-256 · 고정 시각 · 합성 시험 결과는 이 파일 끝 "동결 기록" 에 (6단계 전). 레포 사본 `s26\tools\night_1003\`. 손 계산으로 판정하지 않는다. 출력 `sim\out_1003\EffB1_block.json` (결정적).
- **런별**: `latency_median_ms` — **주 지연 = run-only span** (`run_only_summary.detail.median_ns`, `--npu-run-only-span`) · write+run+read 전수 중앙(보조) · 추론 수 · SKIN 상승 (load_end − load_start HAL SKIN) · 잠정 전력 (d1check 표본 평균 W — 단위 가정·절대 정확도 미인증, 비율 참고만) · 자원 증거 · 게이트 대기 · 시작 SOC · 10 s 칸 배율 (런 안 둔화 기술).
- **셀별**: 두 런 값 · 평균 · 두 런 차 (표류 지표 |a−b|/mean).
- **자원 증거** = `compiled_model_evidence.py evaluate --rule cpu` / `--rule gpu` (규칙 v1 — CPU `cef07604…` · GPU `36615b9e…`): **X < Y 면 규칙을 풀지 말고 "규칙 밖(X/Y)"** · GPU **X/Y < 0.9 또는 폴백 줄이면 그 런은 GPU 자료 아님**. EfficientNet 은 CPU 규칙에 처음 쓰는 모델 (XNNPACK 교체 줄 노드 수가 다를 수 있다 — 규칙은 X = Y 만 본다).
- **정밀도 4항목 1회** (절차서 §7): `compiled_model_evidence.py precision local_models\efficientnet_lite0.tflite` → ① 저장 FLOAT32 ② I/O FLOAT32 [1,224,224,3]→[1,1000] ③ CPU `Options(CPU)` CpuOptions 없음(스레드 `미확인`) / GPU `Options(GPU)`+`GpuOptions(FP32)` **요청** ④ unknown.

## 4. 모델 × duty 상호작용 규칙 (CPU 만, 지금 숫자로)

- **MobileNet 기준 비** (C5 0927, CompiledModel CPU, 5런 중앙) — 1-B 에서 결과 파일로 계산 [P]:
  - **run-only** (`results\S26_C5_cpu_compiled_0927\runs\<run_id>\gpu\*.jsonl` 의 `run_only_summary` 이벤트 `detail.median_ns`, 5런 중앙): d50 **3.8593** / d100 **4.3748** ms → **0.88217** ← **판정에 쓰는 값** (EffNet 블록도 run-only span)
  - write+run+read (`runs\<run_id>\merged\summary.json` `inference_latency.median_ms`, 5런 중앙): d50 3.8825 / d100 4.4072 → 0.88095 (보조)
  - (`작업결과_0927_밤측정.md`:82 의 "run_only d50 3.859 · d100 4.375" 와 일치)
- **규칙**: EffNet CPU **run-only d50/d100 비 (셀 평균 비)** 가 **0.88217 × (1 ± 0.02) = [0.8645, 0.8998]** 안 → **"상호작용 없음 — d25·d75 는 MobileNet 모양으로 보간 가능"**, 밖 → **"상호작용 있음 — 2수준만으로는 부족"**. 셀이 결측이면 "판정 불가".
- **GPU 는 판정 안 함** (MobileNet CompiledModel GPU d50 자료가 없다 — Interpreter 9/14 비는 엔진이 달라 참고로만). 비는 기록한다.

## 5. 반대 해석 (결과 전)

1. 거울 순서는 **선형 표류만** 상쇄 — 세션 후반(SOC 40 %대·실내 온도)·잔열(직전 런의 열)은 두 런 차에 남는다 → 셀별 두 런 차를 표류 지표로 그대로 적는다
2. GPU 런은 60 s 안에 스스로 조여지기 시작할 수 있다 (MobileNet GPU d100 진입 55~80 s [P]) → 10 s 칸 배율을 기술, "60 s 자료를 지속 부하로 외삽하지 않는다"
3. CPU CompiledModel 스레드 수 `미확인` — 엔진 조건으로만
4. 개발 블록 1개 — 확인 블록(자원 순서 바꾼 거울) 전에는 결론 아님. **결과를 보고 셀·순서·블록 수를 바꾸지 않는다**
5. C2 (EffNet NPU 0928) · MobileNet (C5 CPU · M2 GPU) 와의 비교는 엔진·span·설치본·세션 차이를 표시한 **참고**

## 6. 금지

- 결과 보고 규칙·상호작용 창·블록 수를 바꾸지 않는다 · 블록을 쪼개지 않는다 · 실제 주소·시리얼 금지 · 사전 등록 커밋 전에는 6단계를 시작하지 않는다

## 7. 동결 기록 (6단계 전에 채움)

- 판정 스크립트 `sim\night1003_judge_effblock.py` SHA-256 **`bd4bbd8776ec94fcba45c0bc0060d8e12c531e4cd2bea040102ff1a05d7e0039`** (26,915 B), 고정 **2026-10-04 03:28:52 KST**, 합성 양방향 시험 **13/13 PASS** (`sim\out_1003\night1003_judge_effblock_selftest.txt`: 거울 순서 파싱 · 비 0.882 → 없음 · 0.956 → 있음 · 셀 결측 → 판정 불가 · 런 1개 셀 · 연쇄 런 거부 · manifest 없음 오류 · 결정성). 레포 사본 `s26\tools\night_1003\night1003_judge_effblock.py` (같은 SHA). 6단계 자료는 아직 없다 (이 시각 2단계 M1-NPU (a) 종료 중).
- 호출: `py sim\night1003_judge_effblock.py block results\S26_EffB1_01_cpu50_1003 … results\S26_EffB1_08_cpu50_1003 --gate-log results\S26_night_1003_host\gate_log_1003.csv --out sim\out_1003\EffB1_block.json`
