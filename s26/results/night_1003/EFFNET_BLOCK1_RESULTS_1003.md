# EffNet 개발 블록 1 결과 — 2026-10-04 밤 (8런 거울 순서, CPU·GPU × d50·d100, CompiledModel)

> **개발 블록이다 — 확인 블록 (10/4 밤, 자원 순서 바꾼 거울: G50 → G100 → C50 → C100 → C100 → C50 → G100 → G50, 재보정 없음) 전에는 결론이 아니다.** CI·검정력 주장 없음. 블록 수 2 고정.
> 판정 스크립트 `sim\night1003_judge_effblock.py` SHA `bd4bbd8776ec94fcba45c0bc0060d8e12c531e4cd2bea040102ff1a05d7e0039` (03:28:52, selftest 13/13) · 사전 등록 `sim\EffNet블록_사전등록_v1.md` · 커밋 `5d7681a` 03:31:41. 상호작용 규칙: EffNet CPU run-only d50/d100 vs MobileNet C5 0.88217 ±2 % = [0.8645, 0.8998].
> 표기: [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 원시 `D1Check_v4\results\S26_EffB1_<nn>_<cpu|gpu><duty>_1003` (git 무시). 판정 출력 `sim\out_1003\EffB1_block.json`.

## 1. 완주 [P `sim\out_1003\EffB1_block.json`, 판정 07:43]

**8/8 valid · 재시도 0 · 결측 0 · 관측 순서 = 거울 순서** (C50 → C100 → G50 → G100 → G100 → G50 → C100 → C50). 05:50:37 (6-1 게이트) ~ 07:41:37 (6-8 종료) = **1.85 h** · SOC 60 → 48 (**12 %p**) (예상 1.7 h · ~10 %p). 런 사이 게이트 대기 0 / 0 / 120 / 0 / 0 / 120 / 0 / 120 s (SKIN 31.3~31.6 · AP 30.2~31.1 · BAT 29.3~29.8). 모델 `6c7ab0a6…8bde0` 8/8 · 입력 `lcg-rgb-127-128` · LiteRT 2.2.0 · CompiledModel · 60 s · warmup 20 · seed 20261003 · 설치본 `5ac485e3…`.
**6-3 GPU 품질 게이트 (required, `npu-quality-gate`)**: **PASS** — `bit_identical_to_cpu false` · argmax 32/32 (약한 증거: 합성 입력 전부 argmax 21) · **cosine_min 1.0** · 기준 `CPU:/data/local/tmp/efficientnet_lite0.tflite` · 후보 GPU FP32 요청. benchmark-runner MobileNet CPU↔GPU synthetic 검사 passed (`accuracy_preflight.status passed`, 결과 파일 1개 — C2 때는 2개). **계획된 중단은 하지 않았다** (결과 파일 2개를 기다리는 사이 orchestrator 가 자체 stable 컨디셔닝 뒤 슬롯 시작; 슬롯 load_start HAL SKIN 30.8 · AP 29.9 · BAT 28.9 — 게이트 조건 안). 6-4~6-6 은 `off`, 게이트 인자는 그대로 (사전 등록 §2).

## 2. 런별 표 [P]

지연 = **run-only span** (`run_only_summary` 중앙, 주 지연) · wrr = write+run+read 전수 중앙 (보조). SKIN 상승 = load_end − load_start HAL. 전력 = d1check 표본 평균 W (단위 가정 · 비율 참고만). 증거 = `compiled_model_evidence.py evaluate --rule cpu|gpu`.

| 순번 | 셀 | 추론 수 | run-only ms | wrr ms | 10 s 칸 최대 배율 | 시작 SKIN | SKIN 상승 | AP 상승 | status 최대 | 잠정 W | 자원 증거 | 게이트 대기 | SOC |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 6-1 | C50 | 6,735 | **4.4152** | 4.4479 | 1.090 | 31.1 | +4.7 | +8.0 | 0 | 5.53 | PASS 62/62 XNNPACK | 120 | 60 |
| 6-2 | C100 | 13,699 | **4.3142** | 4.3455 | 1.025 | 30.6 | **+10.1** | **+26.0** | **1** | **11.05** | PASS 62/62 | 0 | 59 |
| 6-3 | G50 | 8,817 | **1.4191** | 3.3370 | 1.001 | 30.8 | +3.1 | +5.8 | 0 | 3.56 | PASS 62/62 LITERT_CL · GPU 자료 | 120 | 56 |
| 6-4 | G100 | 17,794 | **1.4105** | 3.3154 | 1.002 | 30.6 | +5.6 | +11.8 | 0 | 6.22 | PASS 62/62 LITERT_CL | 0 | 55 |
| 6-5 | G100 | 17,727 | **1.4400** | 3.3303 | 1.029 | 31.1 | +5.4 | +11.4 | 0 | 6.45 | PASS 62/62 LITERT_CL | 0 | 54 |
| 6-6 | G50 | 8,813 | **1.4470** | 3.3358 | 1.003 | 31.1 | +3.0 | +6.5 | 0 | 3.50 | PASS 62/62 LITERT_CL | 120 | 52 |
| 6-7 | C100 | 13,636 | **4.3369** | 4.3674 | 1.028 | 30.7 | +9.8 | +25.7 | 1 | 10.87 | PASS 62/62 XNNPACK | 0 | 51 |
| 6-8 | C50 | 6,753 | **4.4001** | 4.4335 | 1.066 | 31.3 | +4.7 | +8.5 | 0 | 5.47 | PASS 62/62 XNNPACK | 120 | 49 |

- GPU: run-only 1.41~1.45 ms 인데 wrr 3.32~3.34 ms — **write/read 가 지연의 57 %** (GPU 는 입출력 복사가 지배). CPU: run-only ≈ wrr (−0.7 %). 폴백 줄 0 · 부분 교체 0 → GPU 4런 전부 "GPU 자료".
- CPU d100 은 60 s 안에 SKIN +10 ℃ · AP +26 ℃ · status 1 · ~11 W — 60 s 자료를 지속 부하로 외삽하지 않는다 (0927→28 CPU4 Interpreter 는 30 s 진입 [P]). 60 s 안 10 s 칸 최대 배율은 CPU 1.03~1.09 · GPU ≤ 1.03 (런 안 둔화 작음).

## 3. 셀별 두 런 · 표류 [P]

| 셀 | 순번 | run-only ms (두 런) | 평균 | 차 (표류) | SKIN 상승 | 잠정 W |
|---|---|---|---:|---|---|---|
| C50 | 1 · 8 | 4.4152 · 4.4001 | **4.4077** | 0.015 (**0.34 %**) | 4.7 · 4.7 | 5.53 · 5.47 |
| C100 | 2 · 7 | 4.3142 · 4.3369 | **4.3255** | 0.023 (0.52 %) | 10.1 · 9.8 | 11.05 · 10.87 |
| G50 | 3 · 6 | 1.4191 · 1.4470 | **1.4330** | 0.028 (**1.95 %**) | 3.1 · 3.0 | 3.56 · 3.50 |
| G100 | 4 · 5 | 1.4105 · 1.4400 | **1.4253** | 0.029 (2.07 %) | 5.6 · 5.4 | 6.22 · 6.45 |

- 표류 지표: CPU 0.3~0.5 % · GPU ~2 % (GPU 두 런이 **둘 다 뒤 런이 느리다** — 선형 표류 또는 잔열 [E], 거울 순서는 선형 표류만 상쇄). 블록 1개라 CI·검정력 주장 없음.

## 4. 모델 × duty 상호작용 (사전 등록 §4, CPU 만) [P]

- EffNet CPU **run-only d50/d100 = 4.4077 / 4.3255 = 1.0190** (wrr 1.0193). MobileNet C5 CompiledModel CPU 0.88217 → 창 [0.8645, 0.8998] **밖** → **"상호작용 있음 — 2수준만으로는 부족"**.
- **방향이 반대다**: MobileNet CPU 는 d50 이 d100 보다 12 % 빠른데 (d100 이 60 s 안에 조여진다 — C5 d100 5런 폭 4.24~4.71), EffNet CPU 는 **d50 이 d100 보다 2 % 느리다**. EffNet d100 은 60 s 안 10 s 칸 최대 ×1.03 (조임 작음), d50 은 ×1.07~1.09 (가동 초마다 클럭 재상승 [E] — NPU d10 에서 본 것과 같은 방향). d25·d75 를 MobileNet 모양으로 보간할 수 없다.
- GPU: d50/d100 = 1.0054 (판정 안 함 — 기준 자료 없음). GPU 는 duty 에 거의 무관 (±1 %).

## 5. C2 (EffNet NPU 60 s) · MobileNet 과 나란히 — 참고 (엔진·span·설치본·세션 다름)

| 자원 (EffNet, CompiledModel, 이 밤 run-only) | d50 | d100 | 비고 |
|---|---|---|---|
| NPU AOT (C2 0928, write+run+read, 다른 설치본) | 0.822 | 0.819 ms | [D C2_결과 §2] |
| GPU FP32 요청 (이 밤) | **1.433** | **1.425** ms (wrr 3.34 / 3.32) | run-only 기준 NPU 의 1.74× · wrr 기준 4.1× [E 혼합 span] |
| CPU (이 밤) | **4.408** | **4.326** ms | NPU 의 5.3× (run-only) |
| MobileNet CPU C5 (0927, run-only) | 3.859 | 4.375 | EffNet CPU 가 d100 에서 1 % 빠름 — 모델이 무거운데 CPU 시간이 같다 [E: EffNet-Lite0 FLOPs ≈ MobileNet V1 ×0.7, 메모리 바운드] |

## 6. 반대 해석 (사전 등록 §5) · 한계

1. 거울 순서는 선형 표류만 상쇄 — GPU 두 런 차 2 % 는 뒤 런이 느린 방향 (잔열·SOC 60→48). 확인 블록(자원 순서 바꾼 거울)이 가른다
2. GPU 60 s 안 자기 둔화 — 10 s 칸 최대 ×1.03, 이 블록에선 보이지 않음 (MobileNet GPU 진입 55~80 s [P]) — 60 s 외삽 금지
3. CPU 스레드 수 `미확인` (CompiledModel CpuOptions 없음)
4. **개발 블록 1개 — 확인 블록 전엔 결론 아님.** 결과를 보고 셀·순서·블록 수를 바꾸지 않는다
5. 정밀도 4항목 (`compiled_model_evidence.py precision local_models\efficientnet_lite0.tflite`): ① 저장 FLOAT32 ② I/O FLOAT32 [1,224,224,3] → [1,1000] ③ CPU `Options(CPU)` CpuOptions 없음 / GPU `Options(GPU)`+`GpuOptions(FP32)` **요청** ④ 내부 연산 unknown (LiteRT 2.2.0 미노출)

**한 줄 (개발 블록, 결론 아님)**: EffNet-Lite0 CompiledModel, 60 s run-only: CPU 4.41 (d50) / 4.33 (d100) ms · GPU 1.43 / 1.43 ms — 8/8 valid, 셀 내 두 런 차 CPU ≤ 0.5 % · GPU ≤ 2 %. CPU 의 d50/d100 비 1.019 는 MobileNet 0.882 와 반대 방향 → **상호작용 있음** (d25·d75 보간 불가). 확인 블록 10/4 밤.
