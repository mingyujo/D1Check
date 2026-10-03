# EffNet × NPU d100 600 s · N1300 2런째 사전 등록 — v1 (2026-10-04 03:3x KST, 7·8단계 측정 전 동결)

> 질문 ⑤: **스로틀 계단의 온도대가 모델에 무관한가** (EfficientNet-Lite0 AOT × NPU d100 600 s, 1런) · 꼬리: **NPU 600~1300 s 재현** (MobileNet N1300 2런째, 시작 SKIN 밴드 안).
> 이 파일이 든 커밋 SHA·시각이 동결 증거. 결과 뒤 고치지 않는다 (`_v2`). 표기: [P] 실측 · [D] 인용 · [E] 추정 · `미확인`.
> 근거: `프롬프트_밤측정_1003.md` 1-B-4 · `스로틀곡선_사전등록_0928.md` 1-1 · 1-6 (고정 스크립트 `sim\throttle_curve_0928.py` SHA `3182267894b23813802f0e3f3c3146fbbe2d52581bb494339f1dc623cb6d0b4e`) · `NPU1300_결과_1002.md` · `M2_결과_1002.md` §2 (6b H1·H2 NPU 600 s) · `C2_결과_0928.md` (EffNet NPU 60 s).

## 0. 명령 (dry-run 03:1x exit 0 [P], `model_expected` SHA 확인)

**7단계 EffNet × NPU d100 600 s** — 1002 판 4단계 600 s 판에 C2 의 EffNet AOT 인자 (`--npu-model-asset models/efficientnet_lite0_Samsung_E9965.tflite --npu-timed-input-spec lcg-rgb-127-128`) 를 더하고 seed·폴더만 바꿈:
```bat
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --mode pilot --resources NPU --npu-model-asset models/efficientnet_lite0_Samsung_E9965.tflite --npu-timed-input-spec lcg-rgb-127-128 --npu-run-only-span --npu-max-inference-spans 1000000 --duty-cycles 100 --duration 600 --warmup 20 --repeat 1 --seed 20261003 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --cooling-min-seconds 600 --runner-timeout-seconds 1200 --logger-exit-timeout-seconds 1800 --logger-keep-files-open --analyze-timeout-seconds 600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_EffN600_npu_1003
```
- dry-run manifest `config.npu.model_expected.sha256` = **`311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31`** (10,033,376 B, "this checkout's asset bytes") — 체크아웃 `npu-runner\src\main\assets\models\efficientnet_lite0_Samsung_E9965.tflite` SHA 와 같음 [P 0단계]. 설치본 APK 안의 자산도 같은 파일이어야 한다 — 러너 `npu_artifact_hash` 이벤트·run_metadata `model_sha256` 으로 확인 (다르면 "설치본 자산 불일치" 로 기록, 판정 조건).
- 예상 추론 ≤ 1/0.819 ms × 600 s ≈ 0.73 M [E, C2 d100 0.819 ms] → 상한 1 M 안 (여유 27 %). 러너 기한 1200 (60 + 600 + flush ~0.7 M 줄 ~1 분 → 1.8×) · logger 1800 · analyze 600 · 냉각 600. 시간 ~0.4 h · ~6 %p [E]. SOC 조건 ≥ 41.

**8단계 꼬리 N1300 2런째** — 1002 판 4단계 1300 s 명령 그대로 (seed 20260910 · 상한 2,000,000 · `--npu-run-only-span`), 폴더만:
```bat
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --mode pilot --resources NPU --npu-run-only-span --npu-max-inference-spans 2000000 --duty-cycles 100 --duration 1300 --warmup 20 --repeat 1 --seed 20260910 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --cooling-min-seconds 600 --runner-timeout-seconds 2700 --logger-exit-timeout-seconds 3600 --logger-keep-files-open --analyze-timeout-seconds 900 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_N1300_npu_r2_1003
```
- 시작 조건: SOC ≥ 46 · 지금 + 0.7 h + 30 분 ≤ 10:00. P1b-2 의 `밤측정_1003_권고_v2.md` 는 **없다** (0단계 확인) → 기본 꼬리 그대로.

## 1. 판정 — 고정 스크립트

- **`sim\throttle_curve_0928.py analyze <result_dir> --duration 600|1300 --duty 100`** (**`--equilibrium` 없이** — 1-2 는 C1a 전용, NPU 확장 미등록: 영훈 결정 2026-09-28) — 1-1 진입 (+10 %, 그 칸 + 뒤 3칸) · 끝 60 s 배율 (지연·전력; "평형" 이라는 말은 쓰지 않는다) · 1-6 보존 5항목 (추론 건수는 러너 JSONL 기준) · `formal_npu_valid` False 정상 (pilot).
- **+ `sim\night1003_judge_npu600.py`** SHA-256 **`cc7d1559302dfa947b33cb216cbcb29c47a4d65c074eca0f918997d9e180f91f`** (17,481 B), 고정 **2026-10-04 03:29:54 KST**, 시험 **16/16 PASS** (`sim\out_1003\night1003_judge_npu600_selftest.txt` — 고정 analyze 경로를 **어젯밤 N1300_1002 에 돌려 진입 470 · 1계단 300 · 진입 온도 SKIN 39.9 · AP 44.3 재현** + 규칙 양방향 가짜 기록 11개 + 결정성). 레포 사본 `s26\tools\night_1003\`. 이 스크립트는 고정 analyze 를 subprocess 로 그대로 부르고(SHA 검사) 그 위에 1계단 시각(`fit_throttle_v1.step1_time`, +4.5 % 유지 첫 칸)과 계단 진입 SKIN·AP 만 더한다.
- 출력: `sim\out_1003\EffN600_analyze.json` · `EffN600_effnet_rule.json` · `N1300r2_analyze.json` · `N1300r2_rule.json` (결정적).

## 2. EffNet 비교 규칙 (지금 숫자로)

- **MobileNet 3런 기준** (N1300 · 6b H1 · H2) [P `NPU1300_결과_1002.md` · `M2_결과_1002.md` §2 · `M1_NPU_사전등록_v1.md` §3]: **1계단 SKIN ≈ 38.3 · AP ≈ 42.5 / 2계단(1-1 진입) SKIN ≈ 40.0 · AP ≈ 44.2** (3런 진입 온도 39.9/39.8 · 44.3/44.2/44.2; 1계단 시각 300·240·250 s, N1300 1계단 표본 SKIN 38.3 · AP 42.6 [P selftest 재계산]).
- **규칙**: EffNet 의 두 계단 진입 SKIN·AP (1계단 = +4.5 % 유지 첫 칸의 HAL 표본, 2계단 = 1-1 진입 칸의 HAL 표본) 가 위 네 값의 **±0.5 ℃ 안 (넷 다)** → **"계단 온도대 = 모델 무관 (1런)"**, 하나라도 밖 → **"모델 의존 후보"**. 1계단 또는 진입이 600 s 안에 없으면 "판정 불가 (…)" 로 적고 시각·온도만 기술.
- **계단 폭 (+%) 은 기술만** (1계단 수준 = step1~진입 칸 중앙 배율 · 2계단 첫 120 s 수준 · 끝 60 s 배율) — MobileNet +9 % / +12~13 % / +12 % [P] 와 나란히, 판정 아님.
- 반대 해석 (결과 전): 시작 SKIN 밴드(29.1~31.6) 밖 · SOC (세션 후반 40 %대) · 실내 온도 · 1런 · span 차이 (run-only, N1300 과 같음 · 6b H 는 write+run+read) · EffNet 절대 지연 ×1.10 (C2) 이라 추론 수·전력이 다르다 → "온도대" 비교지 "시각" 비교가 아님 — 시각 차이는 기술만.

## 3. N1300 2런째 규칙

- **1런째** `S26_N1300_npu_1002` [P `sim\out_1002\N1300_throttle_analyze.json`]: 1-1 진입 **470 s** · 1계단 **300 s** (step1_time 재계산 [P]) · 진입 SKIN 39.9 · AP 44.3 · 끝 60 s ×1.211 · 전력 ×0.760 · 시작 SKIN **28.3 (밴드 29.1~31.6 밖)**.
- **규칙**: 2런째의 **1계단 시각·진입 시각 차가 둘 다 ≤ 20 s** → **"재현"**, 아니면 "1런씩 보고". 시작 SKIN 이 밴드 안에서 시작한 사실을 적는다 (1런째는 밴드 밖). 끝 60 s 배율·600~1300 s 기울기(+0.25 %/분 [P 1런째]) 는 기술.
- 1-6 보존 5항목 OK · 캡처 결손 런 규칙 (끝 logcat 폭주 예상 — 판정은 러너 JSONL).

## 4. 금지

- 결과 보고 ±0.5 ℃ · ≤ 20 s 를 바꾸지 않는다 · `--equilibrium` 을 켜지 않는다 · 실제 주소·시리얼 금지 · 사전 등록 커밋 전에는 7·8단계를 시작하지 않는다
