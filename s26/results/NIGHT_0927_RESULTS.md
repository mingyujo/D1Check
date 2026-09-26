# 작업결과 0927 밤 측정 — C6 · C2 경로 스모크 · C1-probe · C5 · C4

> 2026-09-27 02:09 ~ 08:35 KST. 기기 S26 (SM-S942N) 무선 adb `<IP:PORT>`, `D1Check_v4` `s26-measure` (npu-runner APK 02:09 재설치, 빌드 산출물은 HEAD `9bd7a62` 소스 기준).
> 원시는 전부 `D1Check_v4\results\` (git 무시). raw logcat 은 커밋·공유하지 않았다 — 발췌만.

## 1. 한 줄 결론 — C1 을 해야 하는가

**사전 규칙상 답은 "C1a 1 조건(GPU d100 1800 s × 1) 추가"(C1-probe 판정 = 판단 보류), 내 권고는 "하지 않는다".**
C1-probe 가 보여준 것은 느린 수동 열 모드가 아니라 **기기의 능동 제어**다: GPU d100 연속 부하 ~55 s 부터 SoC 가 GPU 를 조여 **배터리 전력 6.5 → 2.6 W, 추론 지연 3.65 → 7.6 ms**, SKIN 은 ~38.4 ℃ 에 붙잡힌다. 그동안 **Android `thermal_status` 는 0 그대로**였다. 고정 duty 로 더 오래 돌리면 제어기 평형을 더 오래 재는 것뿐이다. 최종 결정은 §10.

## 2. 칸별 완주 · 시간 · 배터리 (예상 대비)

| 칸 | 결과 | 시각 | 실제 시간 | SOC | 예상 (절차서 §1) |
|---|---|---|---|---|---|
| C6 진단 스모크 (1차) | **운영자 중단** — `results\S26_C6_diag_0926_ABORTED_0215` (부적격·보존) | 02:10~02:18 | — | 90 → 89 | — |
| C6 진단 스모크 | **1/1 valid** | 02:24~02:34 | 10 min | 89 → 88 | ~11 min, ~1 %p |
| C2 경로 스모크 (게이트 단독 + timed 1런) | **통과** · timed 1/1 valid | 02:35~02:46 | 11 min | 88 → 87 | — |
| C1-probe (1차 기동) | **내 실수로 중단** (preflight optional) — `..._ABORTED_0248` (load 없음, 부적격·보존) | 02:48:36~46 | 10 s | — | — |
| C1-probe GPU d100 600 s × 2 | **2/2 valid**, 안전 중단 0 | 02:49~03:43 | 54 min | 87 → 78 (**9 %p**) | 사전 추정 없음 |
| C5 CompiledModel CPU 단독 | **20/20 valid** (`formal_npu_valid=False` 정상) | 03:47~07:33 | 3 h 46 min | 78 → 55 (23 %p) | ~4.0 h, ~23 %p |
| C4 NPU run-only span | **5/5 valid, `formal_npu_valid` 5/5** | 07:34~08:34 | 60 min | 55 → 48 (7 %p) | ~0.9 h, ~6 %p |

- 전체 02:09 → 08:35, **SOC 90 → 48 %** (지시문 예상 ~46 %). 30 % 게이트 걸림 0, 충전 0
- **지시와 다른 사실**: 시작 SOC 는 93 % 가 아니라 **90 %** (02:09 `dumpsys battery`, 비충전) → 90 % 초과 분기 불필요, 방전 대기 없음

## 3. C1-probe — 판정 · 궤적 · 스로틀 (상세 `sim\C1probe_결과_0927.md`)

사전 등록 `sim\C1probe_사전등록_v1.md` (02:11 동결 · §8 온도 게이트 02:24 · §9 preflight off 정정 02:48, 모두 load 데이터 전). 비교 기준 ΔT∞ = 9/14 strict GPU d100 5런 **6.28~6.98 ℃** → 느린 모드 문턱 7.98 ℃.

| 런 | load_start SKIN | 600 s 상승 | 끝 기울기 580~600 s | SKIN 최고 | 분류 |
|---|---:|---:|---:|---|---|
| r1 | 31.1 | **7.10 ℃** | −0.444 ℃/min | 38.7 @ 456 s | hold |
| r2 | 31.6 | **6.90 ℃** | −0.012 ℃/min | 38.8 @ 550 s | fit |

**판정: 판단 보류** (두 런이 갈림).

SKIN 궤적 60 s 간격 (r1 / r2): 0 s 31.1/31.6 · 60 36.7/37.1 · 120 37.7/38.0 · 180 38.0/38.1 · 240~600 **38.2~38.5 / 38.2~38.5**. AP 는 60~120 s 42.0~42.4 ℃ 최고, 이후 40.3~41 ℃ 로 내려감.

**스로틀 관측 (결과)**: `thermal_status` 두 런 모두 load 내내 0, `headroom_now` 0.66 → 0.78 정체. 그런데 10 s 구간 지연 중앙이 **50~60 s 에 꺾이기 시작** (3.65 → 3.73/3.81 → 4.06/4.25 ms), 540~600 s 7.6/7.2 ms. 배터리 전력 0~60 s 6.43/6.59 W → 540~600 s 2.59/2.82 W.
→ 사전등록 §5 대로 **60 s 이후는 gain 산정 제외**, 600 s 상승량은 "스로틀 이후 전력 변화 포함" 각주.
첫 60 s 지연 3.67/3.68 ms = 9/14 strict 60 s 런 3.60~3.66 ms → 세션 차이 아님.

**42 ℃**: 30 ℃ 근처 시작 · GPU d100 · 600 s 안에 SKIN **도달 못 함** [P] (최고 38.8), 끝 기울기 ≤ 0 이라 외삽 도달 시간 ∞ [E]. `열구속_외삽_0926.md` 의 "빠른 추정"은 38 ℃ 는 대략 맞고(실측 3~4 분) 42 ℃ 는 틀렸다. "느린 추정 ∞" 는 답은 맞았지만 이유(수동 1차 평형)가 틀렸다 — 능동 제어 평형이다 [E].

## 4. C6 — 3분법 ③ 중 무엇이 풀렸나

`results\S26_C6_diag_0927`, NPU d100 60 s, `--npu-diagnostic-logcat` 적용 확인 (manifest `diagnostic_logcat_tags: litert:V …`), `--accuracy-preflight off`.
76,094 추론, 지연 중앙 0.745 ms, load_start SKIN 31.0.

| ③ 항목 | 결과 |
|---|---|
| `tflite`·`litert` V/D 레벨 | **V/D 줄 0** → "그 레벨 출력 없음 (캡처 문제 아님)" 으로 기록. 9/25b formal 런도 V/D 0 |
| 분모 없는 태그의 부재 주장 | 풀리지 않음. 대신 **기대 마커 7종 전부 존재** (runtime_loaded · npu_accelerator_registered · dispatch_library_loaded · enn_loaded · enn_soc_config · dispatch_replacing · dispatch_buffer_info) |
| ENN 벤더 태그 | 풀리지 않음 (미확인 유지) |
| 핵심 이벤트 보존 | **29/29**, 추론 76,094/76,094 (보존율 1.0) → "핵심 증거 온전" |

- 캡처 태그별 줄 수: `I D1GPU` 76,123 · `I D1CHECK_EVENT` 480 · `I litert` 22 · `I tflite` 3 · `W litert` 1 · **`F litert` 1**
- `F litert` 는 `[litert_dispatch_invocation_context.cc:346] Model addr: …, Model size: 8900608` — **정보성 줄이 F 레벨로 찍힌 것**. 9/25b formal 런에도 같은 줄이 있다. `W` 는 "Compiler plugin path … model is pre-compiled" (9/25 동일)
- `Created TensorFlow Lite XNNPACK delegate for CPU` 줄이 1개 있다 (9/25b 도 1개) — 해석 미확인
- 발췌: `D1_ondevice\C6_litert_발췌_0927.txt` (litert/tflite 28줄, `iccid|Euicc|imsi|msisdn|phone` 제외 필터 후. 필터 걸린 줄 0)

## 5. C2 경로 스모크 — `/data/local/tmp` 읽기 가능

- 원본 push: `efficientnet_lite0.tflite` 18,582,189 B, 호스트·기기 SHA-256 모두 `6c7ab0a6…8bde0` [P]
- **preflight off 지시와 목적의 충돌**: timed 명령을 preflight off 로 돌리면 품질 게이트(=기준 파일 읽기)가 안 돈다. 그래서 **게이트 단독 스모크를 한 번 따로** 돌렸다 (`NpuRunnerActivity` `--ei quality_n 32 --es ref_model_path /data/local/tmp/efficientnet_lite0.tflite`, 32+50 추론, 1 s 미만):
  - **기준 파일 열림 · 게이트 PASS**: bit_identical 0/32 · argmax 32/32 · cosine_min 0.99985 · `reference_model_sha256 6c7ab0a6…` · `model_sha256 311e4aac…` (`results\S26_C2_pathsmoke_0927\summary-c2-path-smoke-0927.json`)
  - ⚠ 입력 `lcg-rgb-127-128` 32개가 **모두 argmax 21** 로 나온다 → argmax 32/32 는 약한 증거. cosine 이 실질 기준
- timed 1런 (pilot · duty 100 · preflight off, `results\S26_C2_pathsmoke_0927\timed`): **valid**, 67,963 추론, 지연 중앙 0.818 ms, `model_sha256 311e4aac…` · `npu_model_size_bytes 10033376` · `npu_input_spec lcg-rgb-127-128` 기록 [P]
- → **`run-as` 우회 불필요.** 절차서 §4 의 ⚠ 항목을 "확인됨" 으로 갱신함. C2 본 측정은 하지 않았다 (지시대로)

## 6. 7.2× 새 분해

| 비교 | CPU (CompiledModel, 원본 FP32 `d95b3c5e…`) | NPU (AOT FP16 추정) | 배율 |
|---|---:|---:|---:|
| 이전 7.2× — CPU 연속 스모크 3런 vs NPU timed (9/25) | 5.339 ms (write+run+read) | 0.743 ms | 7.19× |
| **같은 프로토콜 · write+run+read · d100** (C5 vs C4) | 4.407 ms (5런 중앙) | 0.7435 ms | **5.93×** |
| **같은 프로토콜 · `run_only` · d100** (C5 vs C4) — 절차서 사전 식 | 4.375 ms | 0.6903 ms | **6.34×** |

- 즉 7.2× 중 **프로토콜 성분(연속 스모크 vs timed duty)이 5.339 → 4.407 ms, 약 17 %** 였다 (세션도 다름). 같은 프로토콜로 맞추면 5.9×
- span 성분: NPU (0.7435 − 0.6903)/0.7435 = **7.2 %**, CPU (4.407 − 4.375)/4.407 = **0.7 %**. NPU 는 write/read 비중이 커서 `run_only` 배율이 오히려 커진다
- **각주 (필수): 남은 5.9×/6.3× 에는 저장 정밀도 성분이 그대로 들어 있다** (CPU 원본 FP32 vs NPU AOT FP16 추정 [E]). 내부 연산 정밀도는 세 자원 모두 unknown. "NPU 의 상한"·"자원만의 차이" 로 쓰지 않는다
- C5 duty 별 `run_only` 중앙 (5런): d25 3.837 · d50 3.859 · d75 4.065 · d100 4.375 ms. d100 5런 폭 4.24~4.71 (NPU 는 0.682~0.693)
- C4: write+run+read 5런 중앙 **0.7435 ms vs 9/25 d100 0.743 ms → +0.07 %, ±5 % 안 → 세션 차이 각주 불필요**. `run_only_summary` 5/5 런 load 끝에 존재, missing 0

## 7. 실행 조건 — 런별 [P]

| 칸 | 런 | plugged ≠ 0 표본 | max thermal_status | load_start SKIN | 밴드 29.1~31.6 | load_start BAT | SOC (런 시작) |
|---|---:|---:|---:|---|---|---|---|
| C6 | 1 | 0 | 0 | 31.0 | 안 | 29.1 | 89 |
| C2 timed | 1 | 0 | 0 | 31.2 | 안 | 29.4 | 88 |
| C1-probe | 2 | 0 | 0 | 31.1 · 31.6 | 안 (r2 경계) | 29.3 · 29.9 | 87 · 82 |
| C5 | 20 | 0 | 0 | 30.0~31.4 | 20/20 안 | 27.9~29.7 | 78 → 56 |
| C4 | 5 | 0 | 0 | 30.1~30.6 | 5/5 안 | 28.0~28.6 | 55 → 50 |

(`s26\tools\s26_run_conditions.py` 로 추출. plugged 는 텔레메트리 전 표본 기준)

**칸 시작 게이트** (HAL SKIN ≤ 32 · AP ≤ 32 · BAT ≤ 30 · 비충전 · SOC 30~90, 2 분 재확인, 02:24 문서화) — 대기 시간:
C6 0 s · C2 0 s · C1-probe 120 s (BAT 30.3) → 재기동 0 s · C5 120 s (BAT 30.1) · C4 preflight 전 0 s · **C4 preflight 후 0 s**. 로그 `gate_log.csv` (각 칸 결과 폴더에 사본 없음 — §9)

**preflight 가 폰을 데우는가**: C4 preflight(CPU↔GPU 합성+대표 입력, NPU 게이트) 약 5 s 전후 SKIN 30.4 → 30.8, AP 29.0 → 29.8, BAT 28.5 → 28.8. **이번 세션에선 작다.** 0926 02:10 preflight 도 전후 HAL SKIN 31.9 → 31.2 로 데운 흔적 없음

**⚠ 중단 원인에 대한 사실 정정**: 1차 C6 중단 사유였던 "capture 시작 SKIN 37.9 · AP 38.6" 은 `dumpsys thermalservice` 의 **`Cached temperatures` 블록(갱신 안 되는 옛 값)** 이다. 같은 캡처의 `Current temperatures from HAL` 은 SKIN 31.2 · AP 30.4 · BAT 29.5 로 밴드 안이었다 (그 런의 `raw\thermalservice.jsonl` 1행). orchestrator·logger 는 HAL 블록만 쓴다. 게이트 규칙 자체는 유효하므로 그대로 적용했고, 절차서 §0 에 "HAL 블록만 읽는다" 를 같이 적었다

## 8. 중단 · 재개

| 지점 | 무엇 | 처리 |
|---|---|---|
| 02:18 C6 1차 | 운영자 요청 중단 (위 §7 정정 참고). load 중. 런 `0dd05481` 미완 | 폴더명 `_ABORTED_0215` + `ABORTED_README.txt`(부적격·분석 제외·삭제 금지) |
| 02:48 C1-probe 1차 | 내가 `--accuracy-preflight optional` 로 띄움 → 10 s 뒤 중단 (preflight 만 끝, load 없음) | `_ABORTED_0248` + README, 사전등록 §9 정정 (load 데이터 전) |
| 07:35 C4 | **계획된 중단**: 같은 프로세스가 preflight 뒤 곧장 첫 슬롯을 시작하므로, preflight 결과 파일 생성 25 s 뒤 orchestrator 를 멈추고(러너 미기동, `runs\` 0개) 온도 게이트 → 같은 명령 + `--resume` | 슬롯 r001 `attempts 2` 로 남음 (1차는 stable 시작 대기 중 중단, 부하 없음). resume 은 CPU↔GPU preflight 를 **캐시 재사용**, NPU 게이트(32 추론)만 재실행. 공백 ~20 s — 세션 공변량 영향 없음 [E] |

## 9. 못 한 것 · 지시와 다르게 한 것

- **PC 절전 방지**: `powercfg` 로 설정을 바꾸지 않고, `SetThreadExecutionState` 를 부르는 숨은 PowerShell 프로세스로 대기 방지 (설정 변경 없음, 08:35 종료). 결과는 같다 — 6.4 h 무중단
- 폰 `screen_off_timeout` 600000 → 86400000 (02:09) → **600000 원복 (08:35)**. 밝기 0 수동 · 비행기 모드 ON + Wi-Fi 는 9/25 와 같아서 손대지 않음
- 출력 폴더 이름은 절차서의 `_0926` 대신 `_0927` (C6·C5·C4·C2). 명령 인자는 절차서 그대로 (+ C6 `--accuracy-preflight off`)
- 게이트·감시 스크립트 로그(`gate_log.csv`, `c1_skin_watch.csv`)는 세션 스크래치에 있다. C1 감시 로그만 결과 폴더에 복사함. 스크립트 3개는 `s26\tools\` 로 커밋 (§11)
- ENN 태그·NPU 코어 fd 직접 증거: 이번에도 **미확인** (루트 필요)
- C2 본 측정 · C9 · C7: 안 함 (지시대로 / 순서 밖)

## 10. 영훈이 결정해야 할 것 — 내일 낮/밤

1. **C1**: (a) 사전 규칙대로 C1a 1 조건 GPU d100 1800 s × 1 (~40 min, ~12 %p [E]) / (b) 내 권고: 하지 않음. 대신 → 2
2. **새로 생긴 질문 (권고)**: NPU·CPU 도 60 s 넘기면 조여지는가? **NPU d100 600 s × 1 + CPU(CompiledModel) d100 600 s × 1** (~40 min, ~10 %p [E]). "Android status 가 0 인데 처리량이 반으로 준다"가 GPU 만의 일인지가 승인통제 설계(어떤 신호를 볼 것인가)에 직결된다. 사전등록은 C1-probe 틀 재사용 가능
3. **C2 본 측정** (EfficientNet NPU formal 20런, ~3.7 h, ~18 %p): 전제 전부 확인됨 (AOT 가 NPU 로 돈다 · 기준 파일 읽힘 · SHA 기록). 한 세션 가능
4. **C9** (GPU 정밀도 설정 대조, ~1.2 h) — C1-probe 에서 GPU 가 스로틀되는 걸 봤으니 d100 60 s 는 괜찮지만 **60 s 넘기지 말 것**
5. 7.2× 문구 교체: "같은 엔진·같은 프로토콜 5.9× (write+run+read) / 6.3× (run_only), 저장 정밀도 성분 포함" 으로 `NPU_FORMAL_RESULTS.md` §3.1 에 사후 감사 판을 붙일지 (원문 취소선 보존 형식)
6. 조민규에게 전할 것: "S26 GPU 는 연속 d100 ~55 s 부터 thermal_status 0 인 채로 조여진다" — 그의 120 s 시나리오 해석에 영향

## 11. 커밋

`D1Check_v4` `s26-measure` 에 `s26: 밤 측정 C6·C1probe·C5·C4` (push 안 함). 포함: `s26\tools\s26_start_gate.py` · `s26_skin_watch.py` · `s26_c1probe_analyze.py`, `s26\results\NIGHT_0927_RESULTS.md`(이 문서 사본), C6 litert 발췌. `results\`(git 무시)·raw logcat·`local_models\` 는 커밋 안 함.
