# C2 결과 — EfficientNet-Lite0 AOT × NPU formal 20런 (2026-09-28 04:09~07:17 KST)

> 명령: `측정절차_잠금해제_0926.md` §4 그대로 + 비상 감시 (`--emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3`) + `--stability-timeout-seconds 1800 --cooling-timeout-seconds 1800` (1-7, 실패 여유만 — 측정 정의 불변). 출력 `D1Check_v4\results\S26_C2_efficientnet_npu_0928`.
> 분석: `sim\c2_analyze_0928.py` (1-6 검사는 동결판 `throttle_curve_0928.py` 를 그대로 import) → `sim\out_0928\C2.md`·`C2.json` · 에너지 `s26\tools\s26_energy.py` → `sim\out_0928\energy_C2_efficientnet_npu.csv` · 핵심 이벤트 `tools\npu_key_event_retention.py` → `sim\out_0928\C2_retention.jsonl` · 추가 재계산 `sim\out_0928\recheck_0928.txt`.
> 표기: [P] 실측 · [D] 문서·코드 인용 · [E] 추정 · `미확인`. 시각 전부 2026-09-28 KST.

## 0. 한 줄

**20/20 valid · `formal_npu_valid` 20/20 · 1-6 보존 검사 20/20 OK.** EfficientNet-Lite0 NPU 지연 (write+run+read, 5런 중앙) **d25 0.824 · d50 0.822 · d75 0.821 · d100 0.819 ms** — 같은 엔진(CompiledModel NPU)·같은 timed 프로토콜의 MobileNet V1 NPU (9/25 formal) 보다 **×1.10** [P] — 모델+세션+빌드+입력 spec+비상 감시 설정의 복합 값이다 (§2). 잠정 에너지는 §11-4 ① 단위 판별은 통과했지만 ② 내부 일관성을 **통과하지 못해** 수치를 쓰지 않는다 (§4).

## 1. 실행과 판정 [P]

| 항목 | 결과 |
|---|---|
| 칸 게이트 (preflight 전) | 04:09:00 통과 (120 s 대기): HAL SKIN 31.4 · AP 30.2 · BAT 29.7 · SOC 64 · 비충전 [P `gate_log.csv`] |
| SOC 규칙 (1-4, ≥ 53 %) | 04:06:4x `dumpsys battery` level **64** → 진행 [운영자 기록] |
| accuracy preflight (benchmark-runner CPU↔GPU 출력 동등성 — **MobileNet V1 FP32 `d95b3c5e…` 대상, EfficientNet·NPU 와 무관**, formal 명령 요건이라 실행됨) | synthetic passed · representative passed · formal_gate passed (04:09:12·04:09:15 결과 파일) |
| **NPU 품질 게이트 `npu-quality-gate-v1`** (EfficientNet NPU 품질의 유일한 근거) | **PASS** — bit_identical **0/32** · argmax **32/32** · cosine_min **0.99984732** · cosine_mean 0.99996486 · 기준 `CPU:/data/local/tmp/efficientnet_lite0.tflite` (`reference_model_sha256 6c7ab0a6…8bde0` [P manifest]; 기기 파일 SHA 도 03:4x 에 같음 확인) · 후보 SHA `311e4aac…` · `evaluated_utc` 04:09:19 |
| ⚠ argmax | 합성 입력 `lcg-rgb-127-128` 32개가 **전부 argmax 21** (0927 경로 스모크와 같음) → **argmax 32/32 는 약한 증거, cosine 이 실질 기준** |
| 계획된 중단 | 04:09:44 [운영자 기록 — manifest 에는 중단 시각이 없고 04:09:21 safety_preflight 다음 단계가 04:10:25]. 이유: 같은 프로세스가 preflight 직후 곧장 첫 슬롯을 시작하므로, preflight 뒤 칸 온도 게이트를 다시 거치려고 (0927 C4 선례, `작업결과_0927_밤측정.md` §8). 방법: 결과 파일 2개 생성 + 25 s 뒤 `runs\` 0개 확인 후 정지 (첫 슬롯 `npu-d075-r001` 열 컨디셔닝 중, timed 러너 미기동). 게이트 04:10:16 즉시 통과 (SKIN 31.6 · AP 30.8 · BAT 29.8) → 같은 명령 + `--resume` 04:10:24 |
| resume | accuracy preflight `resume_reused true`. **NPU 게이트는 다시 돌리지 않았다** — manifest 기록은 1차 `npuq-ace8b6c6…` 하나(`evaluated_utc` 04:09:19, 중단 전) [P]; orchestrator 는 같은 후보·input_spec 의 passed 기록을 재사용한다 [D `d1_experiment_orchestrator.py:3373-3380`]. (0927 보고서는 C4 resume 때 게이트를 재실행했다고 적었다 — 처리가 달랐을 수 있다) |
| 슬롯 | **20/20 completed · valid · duration_complete** · `npu-d075-r001` 만 attempts 2 (1차는 컨디셔닝 중 계획 중단, 부하 없음) · 나머지 attempts 1 · 실패 0 · 종료 이벤트 20/20 logcat (폴백 0) |
| `formal_npu_valid` | **20/20 True** (9조건 전부) |
| 1-6 보존 검사 | **20/20 OK** — 부하 60 s · 계산 가동 24.99/49.99/74.99~75.00/99.99~100.00 % · 추론 JSONL = run_summary = file_summary = run_metadata (merged 도 같음 — merged 는 러너 JSONL 로 만든다) · 텔레메트리 단조 · 자원 증거 (npu_delegate_evidence verified · AOT 파티션 일치 · ENN 줄 D1GPU PID · dispatch 실패 0 · XNNPACK·GPU delegate 줄 0) · plugged 0 |
| 핵심 이벤트·logcat 보존 | 20/20 런 key events 전부 · 기대 마커 7종 20/20. logcat D1GPU 추론 사본 보존율 (추론 줄 기준) 런별 0.918~1.000 · **세션 전체 0.988** (834,017 / 844,007) · 100 % 미만 11런 [P `C2_retention.jsonl`] — 기준은 러너 JSONL |
| load_start SKIN | 30.8~31.2 ℃ — **20/20 밴드 안** |
| 안전 | orchestrator 비상 감시 관측 8,496 건 · 사유 0 · status 최대 0 [P manifest `runtime_safety`] · 호스트 SKIN 감시(npurunner 사본) 739 표본 (04:10:25~07:17:56 — 1차 preflight 구간은 감시 밖) 경보 0, 최고 35.4 ℃ |
| 시간·배터리 | 04:09:08 ~ 07:17:57 = **3.15 h** (orchestrator 기준; 앞 게이트 120 s 포함 시 3.18 h) · SOC 64 → 45 (**19 %p**, 호스트 감시 `battery_level` 04:10:25 → 07:17:56; 러너 `pilot_battery_pct` 기준 63 → 46 = 17 %p). 예상 ~3.7 h · ~18 %p [D `측정절차_잠금해제_0926.md` §1·§4 — MobileNet NPU 슬롯 간격 기준] |
| 모델·입력 | `model_sha256 311e4aac8fa1d8de…` 20/20 · `npu_input_spec lcg-rgb-127-128` 20/20 |

- ⚠ manifest `config.npu.quality_gate.reference` 문자열은 기본 표기 `CPU:models/mobilenet_v1_1.0_224.tflite` 이지만, 같은 블록의 `reference_path` 는 `/data/local/tmp/efficientnet_lite0.tflite` 이고 실행 기록 `npu_quality_preflight.quality_gate.reference` 도 같은 파일이다 [P] — 인용할 때 실행 기록 쪽을 쓴다

## 2. duty 별 지연·열 — MobileNet NPU 와 비교 [P]

지연 = 런별 `latency_median_ms` (write+run+read span) 의 5런 중앙. CV = 모집단 SD / 평균. MobileNet = `results\S26_NPU_formal_0925b` (9/25 formal 20런, 같은 npu-runner CompiledModel 경로, 다른 날·다른 설치본).

| duty | EfficientNet 지연 ms (범위) | CV | 추론 수 중앙 | SKIN 상승 중앙 ℃ | MobileNet 지연 ms (범위) | 추론 수 중앙 | SKIN 상승 중앙 ℃ | 지연 비 |
|---:|---|---:|---:|---:|---|---:|---:|---:|
| 25 | **0.8243** (0.8225~0.8266) | 0.16 % | 16,010 | 0.9 | 0.7487 (0.7460~0.7547) | 17,638 | 1.3 | **×1.101** |
| 50 | **0.8220** (0.8198~0.8245) | 0.22 % | 33,232 | 2.0 | 0.7459 (0.7417~0.7482) | 36,585 | 2.1 | **×1.102** |
| 75 | **0.8214** (0.8197~0.8234) | 0.14 % | 50,873 | 2.8 | 0.7464 (0.7438~0.7495) | 55,889 | 2.9 | **×1.101** |
| 100 | **0.8189** (0.8141~0.8214) | 0.30 % | 68,771 | 4.0 | 0.7427 (0.7400~0.7455) | 75,912 | 4.0 | **×1.103** |

- duty 에 따라 거의 변하지 않는다 (d25 → d100 −0.7 %). **런 안에서도 60 s 동안 느려지지 않았다** — 10 s 구간 중앙 / 처음 30 s 중앙이 d100 5런 0.987~1.012, 전 duty 20런 0.978~1.013 [P `recheck_0928.txt`, 고정판 `bins10`·`ref_latency`]. 단 **60 s 자료를 지속 부하로 외삽하지 않는다** — MobileNet NPU d100 165 s 1런은 ~100 s 부터 느려졌다 (150 s ×1.0997, `스로틀곡선_0928.md`). EfficientNet 은 60 s 를 넘는 자료가 없다
- **같은 설치본 대조**: 0927 C4 MobileNet NPU d100 5런 중앙 0.7435 ms [D `작업결과_0927_밤측정.md` §6] (npu-runner 9/27 02:09 설치본 = 오늘과 같음) → 0.8189 / 0.7435 = **×1.101**. 빌드 차이는 d100 배율을 바꾸지 않는다 — 남은 교란은 세션 + 입력 spec
- 0927 경로 스모크 timed 1런 (d100 0.818 ms [D `작업결과_0927_밤측정.md` §5]) 과 오늘 d100 0.8189 ms: +0.1 %
- 60 s SKIN 상승 중앙은 d100 에서 두 모델이 같다 (4.0 ℃; d25 는 0.9 vs 1.3 ℃) [P]. 전력이 같은지는 이 자료로 말하지 않는다 — 잠정 load W (5.21 vs 5.12 W) 는 §4 내부 일관성 FAIL 이고, 세션 간 차이 1.8 % 는 §11-4 ③ 기준(> 20 %) 밑이라 "구분 불가" 일 뿐이다 [E]
- 비교 조건 차이 (MobileNet 0925b 대비): 날짜·세션 (0925b 는 러너 시작 SOC 78 → 60 %) · 입력 spec (`lcg-unit` vs `lcg-rgb-127-128`) · 설치본 · **비상 감시 설정** (C2 만 켜짐 — load 단계 sparse dumpsys 관측 222회/20런 [P manifest]; 0925b 는 꺼짐, 냉각·컨디셔닝 timeout 900 s). 지연 비 ×1.10 은 이 모든 것의 **복합** 값이다

## 3. 정밀도 4항목 (MEASUREMENT_DEFINITION §11-3)

① 저장 정밀도: AOT 산출물 — 벤더 bytecode 라 파일에서 못 읽음 → FP16 은 **[E]** (MobileNet AOT 와 같은 처리) · ② I/O dtype: 입력 FLOAT32 `[1,224,224,3]` → 출력 FLOAT32 `[1,1000]`, 그래프 텐서는 입출력 2개뿐 [D `npu\results\NPU_FORMAL_RESULTS.md`:122 — AOT `311e4aac…` 기준]; 게이트 기록의 입력 정규화 `(RGB-127.0)/128.0` · ③ 실행 옵션: `CompiledModel` Accelerator NPU 단독 · ④ 내부 연산·누산: **unknown** (근거 없음)

## 4. 잠정 에너지 — 쓰지 않는다 [P]

`s26_energy.py` 적분 전류 / charge counter (`MEASUREMENT_DEFINITION.md` §10·§11-4 3분법):
- ① **단위 판별 PASS** — 런별 비율 0.800~1.056 이 전부 [0.5, 2] 안, 방전 음수
- ② **내부 일관성 FAIL** — 세션 합산 비율 **0.9410 (−5.9 %)**. 허용 = 3·σ_run/√N: §10 과 같은 모집단 σ 0.0723 로 **4.85 %** (표본 σ 0.0742 로는 4.98 %) → 5.9 % > 4.85 % — 어느 σ 로도 FAIL
- 같은 도구로 MobileNet 0925b: 0.9768 (−2.3 %) vs 모집단 σ 0.080 → 5.39 % (표본 σ 로 5.53 %) → PASS — 판정·허용오차 ±5.4 % 모두 §10.2 이전 보고와 같다
- 절대 정확도는 원래 미인증

| duty | EfficientNet load W | idle W | 순 mJ/추론 (**잠정, 사용 금지**) | MobileNet load W | 순 mJ/추론 (잠정) |
|---:|---:|---:|---:|---:|---:|
| 25 | 1.80 | 0.64 | 4.77 | 1.65 | 3.18 |
| 50 | 2.95 | 0.69 | 4.04 | 2.84 | 3.98 |
| 75 | 4.09 | 0.67 | 3.88 | 4.12 | 3.73 |
| 100 | 5.21 | 0.67 | 3.97 | 5.12 | 3.53 |

- ② FAIL 이라 에너지 수치는 **표에만 두고 결론에 쓰지 않는다**
- 참고 [P]: C1a 1300 s 는 같은 도구 비율 1.0000 (1런)

## 5. 반대 해석 (ground-truth)

| 해석 | 가장 강한 반대 해석 | 배제하나 |
|---|---|---|
| "EfficientNet 이 NPU 에서 돈다" | 조용히 CPU/GPU 로 떨어졌다 | **배제 (간접 증거 기준)** — bit_identical 0/32 (CPU 와 다름), formal_npu_valid 20/20 (dispatch 증거·ENN·AOT 파티션 일치), 20런 전부 XNNPACK 0 · GPU delegate 0 · dispatch 실패 0, `DispatchDelegate` 줄만으로 판정하지 않음. NPU 코어 fd 직접 증거는 미확인 (§6) |
| "품질 동등" | argmax 가 전부 21 이라 판별력이 없다 | 부분 — argmax 는 약한 증거. cosine_min 0.99985 가 실질 근거. 실제 이미지 품질은 이 게이트 밖 (대표 이미지셋 합의 대기) |
| "EfficientNet 은 MobileNet 보다 10 % 느리다" | 세션·입력 spec 차이 | 배제 못 함 — 같은 세션 대조는 없다. 같은 설치본 대조(0927 C4)로 빌드 요인은 d100 에서 빠졌다 (×1.101) |

## 6. 한계

- 60 s 칸 20런 — 지속 부하 거동은 이 자료로 모른다 (MobileNet NPU 165 s 1런 참고 — 모델이 다르다)
- NPU 코어 직접 증거(fd) 미확인 — 앱 프로세스 fd 에 npu 장치 없음, HAL 프로세스 확인은 루트 필요 [D `D1Check_v4\CLAUDE.md` §7-6]
- 에너지 ② 내부 일관성 FAIL
