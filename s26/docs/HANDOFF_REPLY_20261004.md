# S26 인계(10/3) 회신 — 2026-10-04

> 대상: [S26 담당자 전달 — 완료 항목과 남은 계측 (2026-10-03)](https://github.com/mingyujo/D1Check/blob/feature/arrival-scheduling-20260923/docs/team/S26_HANDOFF_20261003.md) (`6bd1802`)
> 기준: `s26-measure` `ca1126a` (10/3→04 밤 커밋). 인계 문서가 본 `cea8eae` 뒤에 커밋 8개가 있다 — P1b 시뮬 v1 6개 + 밤 사전 등록 `5d7681a` + 밤 결과 `ca1126a`.
> 표기: [P] 실측·파일 확인 / [D] 문서 인용 / [E] 추정. 협업 회신이며 새 실행 승인이나 동결 계획이 아니다. 이 문서 작성 중 기기 명령 0.

## 0. 요약

- 인계 문서의 S26 완료 표(C2 20런 · N1300 1런 · M2 양방향 · M1 1런)는 우리 기록과 같다 [P M1·C2 판정 출력 · D 10/3 재계산 기록].
- 그 뒤 10/3 밤: **M1 독립 1런 완료**(같은 명령·seed·경계, 회복 10 s 계단형 — 1런째 20 s 와 재현). 그 밖에 NPU 회복 2런, GPU 페이싱 1런, EffNet CPU·GPU 개발 블록 8런. EffNet NPU 600 s 는 안전 비상 중단으로 자료가 없다.
- 공유·PC 보완 4항목 중 일부는 이미 GitHub 에 있다. 나머지(런별 최소 export · C2 전기 원 시계열 · `out_0928` · 구간별 증거 귀속)는 **10/5 까지 PC 작업으로 올린다.** 기기 재측정은 하지 않는다.
- 실측: 오늘 밤 1순위는 EffNet 확인 블록이다. M2 CPU 피해자는 순차 실행 범위에서는 하지 않는다(§3). N1300 독립 1런은 600~1300 s 를 근거로 쓸 때만 한다.
- 확인 부탁 2개(§5): S26 의 서류 범위, 대표 입력·참조 출력·품질 기준.

## 1. `cea8eae` 뒤에 추가된 S26 결과 (10/3→04 밤 · 전부 pilot · npu-runner 설치본 `5ac485e3…` 재설치 없음)

| 칸 | 결과 [P] | 문서 (`s26/results/night_1003/`) |
|---|---|---|
| M1-GPU 2런째 — GPU d10 60 → d100 1200 → d10 300 s, 1런째와 같은 명령·seed 20261002 | valid · 회복 **10 s 계단형**(1런째 20 s, 차 10 s → 등록 규칙상 "재현") · 가열 진입 60 s · 540~600 s ×2.27 · 끝 SKIN 38.7 ℃ · load 시작 SKIN 30.9 ℃(밴드 안) | `M1_GPU2_RESULTS_1003.md` |
| M1-NPU ×2 — NPU d10 60 → d100 600 → d10 600 s | 두 런 다 **20 s(10 s bin) 안 계단형 회복** · 해제 때 SKIN 41.4 · AP 43.9 ℃ → SKIN 문턱 아님(H-skin 기각), 타이머와 다른 문턱은 못 가름 · 540~600 s ×1.21 | `M1_NPU_RESULTS_1003.md` |
| GPU 페이싱 — d100 600 → d10 60 → d100 300 s | 60 s 휴지로 회복한 GPU 가 d100 복귀 뒤 **첫 10 s 만 식은 속도, 다음 10 s 칸에 ×2.0 재조임** → 60 s 휴지는 재조임을 늦추지 못했다(1런) | `GPU_PACING_RESULTS_1003.md` |
| EffNet-Lite0 CPU·GPU 개발 블록 — CompiledModel, d50·d100, 셀당 2런, 거울 순서 C50 C100 G50 G100 G100 G50 C100 C50 | 8/8 valid · run-only 중앙 **CPU 4.41 / 4.33 ms · GPU 1.43 / 1.43 ms**(d50 / d100; GPU write+run+read 3.34 / 3.32 ms) · 셀 안 두 런 차 CPU 0.34 / 0.52 % · GPU 1.95 / 2.07 % · 자원 증거 8/8(CPU 62/62 XNNPACK · GPU 62/62 LITERT_CL) · GPU 품질 게이트 PASS(합성 입력) | `EFFNET_BLOCK1_RESULTS_1003.md` · 사전 등록 `EFFNET_BLOCK_PREREG_v1.md` |
| EffNet × NPU d100 600 s | **FAILED** — orchestrator 안전 비상 중단(`battery_temperature_emergency`, BAT 42.2 ℃, 부하 약 591 s 시점) · 러너 자료 없음 · 인용 금지 | `NPU600_EFFNET_RESULTS_1003.md` |

- 판정은 전부 측정 전에 SHA 를 고정한 스크립트의 출력이다(§2-4 표). 원시는 git 밖이다(§2-1).
- 개발 블록은 결론이 아니다. 확인 블록(자원 순서를 바꾼 거울 G50 G100 C50 C100 C100 C50 G100 G50, 재보정 없음)은 사전 등록이 동결된 상태로 10/4 밤 예정이다.
- 10/3 밤 MobileNet NPU 600 s 두 런도 끝 BAT 41.6~41.7 ℃ 였다 — **NPU d100 600 s 급은 지금 BAT 42 ℃ 기본 한도에 닿는다** [P]. 10/2 N1300 의 최고 BAT 는 40.9 ℃ 였다.
- 모형 대조(시뮬 v1 예측을 측정 전 커밋): 가열 구간은 맞고, 해제·재조임 시각(실측 10~20 s, 모형 30~50 s)과 냉각은 틀렸다 → `MODEL_HOLDOUT_1003.md`.

## 2. 공유·PC 보완 4항목 — 있는 것 / 없는 것 / 할 일

### 2-1. 10/2 밤 자료 (N1300 · M1 · M2/M2r)

- **GitHub 에 있음** — `s26/results/out_1002/`: 구간 경계와 구간별 지연 `*_segments.json` · 판정 `M1_judge.json` `M2_npu_judge.json` `M2r_gpu_judge.json` · `N1300_table.json`·throttle analyze · 엔진 대조 `M2_H{1,2}_engine.json` · 호스트 게이트·세션·SKIN 감시 로그 · 사전 등록 동결 기록 `M1M2_v1_freeze.txt`.
- **영훈 PC 에만 있음** — 런 폴더 `results\S26_*_1002\` (M1 예) [P 폴더 목록]:
  - `experiment_manifest.json`(약 1.4 MB): 무선 adb 주소와 PC 경로가 들어 있어 그대로 공유하지 않는다
  - `exports-v2/` 4파일: `thermal_timeseries.csv` 는 1 Hz AP·BAT·PA·SKIN·thermal_status 만 있고 전류·전압 열이 없다
  - `runs/<id>/merged/`: `latency_timeline.csv`(약 57 MB, 추론별 current_raw·voltage_mV·charge_counter_raw·센서) · `events.jsonl`(약 112 MB) · `summary.json` · `delegate_evidence.json` · `npu_delegate_evidence.json`
  - `runs/<id>/raw/`: `logcat.txt`(약 60 MB) · `logcat.jsonl` · `thermalservice.jsonl`, 러너 `gpu-events-*.jsonl`(약 103 MB)
- **할 일 (10/5 까지, PC 작업)** — 10/2 13실험 + 10/3 13실험의 런별 최소 export 를 `s26/results/export_1002_1003/<실험>/` 에:
  1. `exports-v2` 4파일 (기존 `after_0925/exports_v2/` 와 같은 형식)
  2. manifest 정리본 — 실행 조건 · validation · 게이트 · 설치본/모델/입력/체인 SHA · 구간 경계 · cleanup 기록만 남기고 주소·경로·시리얼은 뺀다
  3. 1 s 표 — mono_ns 기준 current_raw · voltage_mV · charge_counter_raw · plugged · AP/BAT/PA/SKIN · thermal_status · 추론 수 · 지연 중앙 (merged 에서 추출, 보간 없음)
  4. 구간별 증거 귀속표 (2-2)
  5. 원본 파일 목록 + SHA-256 (원본은 PC 에 보존)

### 2-2. 자원 증거 — 연쇄 구간별 귀속 · 미설명 전환 시간

- 우리도 10/2 밤 보고서에 코드 과제(P3)로 적어 둔 항목이다: 연쇄 런에서 `npu_delegate_evidence` 가 **구간 0 모델로 manifest 를 찾는 문제**, 구간별 증거 귀속, `transitions_explained` 미설명 50~99 ms [D]. 코드는 아직 고치지 않았다.
- 10/3 밤 연쇄 4슬롯도 같은 표시다 — 전환 창 131~214 ms 중 32~116 ms 미설명, 허용오차는 바꾸지 않았다 [P].
- 단일 자원 런(EffNet 블록 8런)은 런별 증거가 PASS 라 귀속 문제가 없다 [P].
- **할 일**: 보존된 원시 logcat 의 delegate 교체·dispatch 줄(PID 포함)을 구간 경계 시각으로 나눠 **구간별 귀속표**를 PC 에서 만든다. 판정 규칙(구간마다 기대 가속기 줄 ≥ 1 · 다른 가속기 줄 0 · fallback 0)은 표를 보기 전에 고정한다. 기기 재측정은 아니다.

### 2-3. 에너지 — C2 단위 판별 PASS / 내부 일관성 FAIL 의 근거

- 판정(`C2_RESULTS_0928.md` §4): ① 단위 판별 PASS — 런별 비 0.800~1.056 이 [0.5, 2] 안, 방전 음수. ② 내부 일관성 FAIL — 세션 합 비 0.9410(−5.9 %), 허용 3σ/√N = 4.85 %(모집단 σ 0.0723; 표본 σ 0.0742 면 4.98 %). 어느 σ 로도 FAIL [P 이 회신 작성 중 재계산 일치].
- 도구 `s26/tools/s26_energy.py` 는 GitHub 에 있다. 판정 산출 `energy_C2_efficientnet_npu.csv`(20런 × baseline/load/cooling/total 창별 적분 µAh · charge counter 변화 · 비 · 전압)는 **영훈 PC `sim\out_0928\` 에만 있다** → `s26/results/out_0928/` 로 올린다.
- 새로 확인 [P]: C2 의 charge counter 변화량은 **전부 4,275 µAh 의 배수**다(한 계단 약 4.3 mAh). 59 s 부하 창에는 0~3 계단뿐이고 일관성 검사 창(284~551 s)에도 4~12 계단이다. 그래서 부하 창 J 는 charge counter 로 검증할 수 없다. FAIL 이 창·정렬 문제인지 전류 적분 쪽 편향인지는 이 자료로 가르지 않는다 [E].
- 원 전류·전압·charge counter 시계열은 GitHub `exports_v2/thermal_timeseries.csv` 에 **없다**(30열, 센서·status 만) [P] → 2-1 의 1 s 표에 C2 20런도 넣는다.
- 에너지는 계속 `raw_unverified` 로 두고 결론에 J 를 쓰지 않는다. A24 raw=mA 해석이나 전력·열 상수를 S26 에 옮기지 않는다.

### 2-4. 보고서 경로 ↔ GitHub 경로 · 실행 당시 판정기 SHA

보고서의 `sim\…` 은 영훈 PC 의 분석 폴더다. GitHub 대응:

| 보고서 경로 | GitHub (`s26-measure`) |
|---|---|
| `sim\out_1002\*` | `s26/results/out_1002/*` |
| `sim\{NPU1300,M2,M1}_결과_1002.md` · `M1M2_사전등록_v1.md` | `s26/results/{NPU1300,M2,M1}_RESULTS_1002.md` · `M1M2_PREREG_v1.md` |
| `sim\m1m2_judge_1002.py` | `s26/tools/s26_m1m2_judge_1002.py` |
| `sim\throttle_curve_0928.py` | `s26/tools/s26_throttle_curve_0928.py` |
| `sim\*_결과_1003.md` · `sim\out_1003\*` · 사전 등록 3개 | `s26/results/night_1003/*_RESULTS_1003.md` · `night_1003/out_1003/*` · `*_PREREG_v1.md` |
| `sim\night1003_judge*.py` · `predict_pacing_v1_1003.py` | `s26/tools/night_1003/` |
| `sim\out_0928\*` (C1a·C2·C600·M3·N165 판정 JSON · 에너지 CSV · recheck) | **없음 → `s26/results/out_0928/` 로 추가** |
| `D1Check_v4\results\…` (원시) | git 밖 — 2-1 export 와 SHA 목록으로 대신한다 |

| 묶음 | 판정기 SHA-256 (측정 전 고정) | 사전 등록 · 동결 | 설치본 |
|---|---|---|---|
| 10/2 밤 (N1300 · M2 · M1) | `s26_m1m2_judge_1002.py` `ea282d4a…5b28` | `M1M2_PREREG_v1.md` `002a47a7…6da67` (10/3 01:36:19 KST, `out_1002/M1M2_v1_freeze.txt`) | npu-runner `5ac485e3…` (10/2 23:56:58 설치) |
| 10/3 밤 | `night1003_judge.py` `a5ceab41…0f50` · `_pacing` `516116b4…83c7` · `_effblock` `bd4bbd87…0039` · `_npu600` `cc7d1559…0f91f` | 커밋 `5d7681a` (10/4 03:31) · 원장 `night_1003/freeze_1003.txt` · 측정 시작 HEAD `4092f15` | 같음 |

## 3. 남은 실측 — 목적별

| 인계 문서의 목적 | 우리 상태 | 계획 |
|---|---|---|
| 두 작업 대표 입력 품질 | 합성 32입력 게이트만 있다(C2 NPU · 10/3 GPU; 32개 argmax 가 전부 21 이라 판별력이 약하다). 대표 이미지 품질 0. EfficientDet 은 NPU AOT·raw 2출력 스모크뿐이고 decode/NMS·CPU/GPU 는 없다 [P] | 대표 입력·참조 출력·기준을 받으면(§5-2) EffNet CPU/GPU/NPU 출력 덤프 1세션 → CPU 기준과 비교. 기준은 결과 전에 고정. EfficientDet 은 §5-1 답에 따라 |
| 요청 단위 종단간 시간 | S26 러너에는 요청 단위 기록이 없다 [P] | 정책 확인용 폰 재생(10/6~9 계획) 코드를 만들 때 dispatch / start / return / output / persist / worker_release / lane_available 을 그 이름 그대로 기록하고, 예정 요청 전체의 성공·실패·미완료 분모를 남긴다 |
| 사용 정책의 기기별 비용 | 단독: EffNet NPU 20런(C2) · CPU/GPU 개발 블록 8런 · MobileNet 3자원. 전환: GPU↔NPU 연쇄(M2 ABBA). 전후 유휴: 런마다 baseline 60 s 와 냉각 구간 telemetry. **동시 병행 없음**(러너가 순차) [P] | 오늘 밤 확인 블록으로 EffNet CPU/GPU 칸을 채운다. 병행은 §5-1 답에 따라 |
| 독립 확인 (동결 → 별도 실행) | 시뮬 v0·v1 예측을 측정 전에 커밋하고 다음 밤 자료로 대조했다(§1 마지막 줄) | 모형 동결 → 폰 재생으로 확인(재보정 없음) → S26 측정 동결 10/11 |
| N1300 독립 1런 | 없음. NPU d100 600 s 가열은 5런 있다(N1300 앞 600 s · M2r H1·H2 · M1-NPU a·b) [P] | 600~1300 s 를 정책 근거로 쓸 때만, 밤 맨 앞(시작 BAT 가 낮을 때)에 1런. 지금은 BAT 42 ℃ 한도 때문에 시작 조건 없이는 못 돈다 |
| M1 독립 1런 | **완료** (§1, 10 s 재현) | — |
| 완전 유휴 d0 회복 | 없음(d10 탐침만) | d10 결과를 d0 으로 간주하지 않는다. 정책의 유예가 d0 대기를 쓰면 "고정 대기 → 짧은 probe" 체인을 사전 등록해 추가한다(후보) |
| M2 CPU 피해자 | 없음 | **순차 실행 범위에서는 하지 않는다** — "뜨거우면 CPU" 배정은 NPU 에 지배된다: CPU 가 가장 빨리 뜨거워지고(60 s SKIN 상승 EffNet d100 CPU +9.95 ℃ 2런 · GPU +5.5 ℃ 2런 · NPU +4.0 ℃ C2 d100 5런 중앙, NPU 는 9/28·다른 설치본) 가장 조여진 NPU(MobileNet 540~600 s ×1.21, 약 0.9 ms)도 CPU(MobileNet CompiledModel run-only 3.86~4.38 ms)보다 4배 넘게 빠르다 [P MobileNet; EffNet NPU 는 60 s 넘는 자료가 없어 E]. 두 작업 병행(§5-1 (나))이면 두 번째 작업의 자원으로 CPU 가 다시 후보가 되므로 그때 다시 본다 |
| EffNet × CPU 20런 | 20런 대신 MULTITASK §8 방식(세션 = 블록 · 거울 순서 · 블록 수 2 고정 · 개발/확인) | 개발 블록 완료 · 확인 블록 10/4 밤 |

## 4. 하지 않는 것

- S26 계수·전력/열 상수를 A24 에, MobileNet 결과를 EfficientDet 에 옮기지 않는다
- J 확정값이나 SOC·사용시간 절감은 주장하지 않는다. 열 보호·품질 게이트·BAT 한도를 완화하지 않고, 같은 장시간 실험을 자동으로 반복하지 않는다
- 브랜치 merge 는 하지 않는다. 모델/AOT·APK·키·원시 logcat/JSONL·기기 고유 식별은 Git 에 올리지 않는다(작은 CSV/JSON · 판정 · SHA 만)

## 5. 확인 부탁

1. **S26 의 서류 범위**
   - (가) S26 을 별도 절로 쓴다: NPU 를 포함한 3자원 순위(EffNet NPU < GPU < CPU; A24 MobileNet 은 CPU < GPU), 열 스로틀이 처리율을 바꾸는 모양(GPU ×2.0~2.3 계단 · NPU ×1.09 → ×1.21 계단 · 10~20 s 해제 · 짧은 휴지 무효), 그에 맞춘 열 인지 배정. 네 발표 완료표의 미완료 칸 "열에 따른 처리율과 열 피드백 정책 검증" 을 채우는 쪽이다.
   - (나) A24 CPU_URGENT/PAR 두 작업 비교를 S26 에서 재현한다: EfficientDet CPU/GPU · decode/NMS · 품질, 동시 병행, 요청 경계가 모두 새로 필요해 10/11 측정 동결 안에는 빠듯하다 [E]. (나)라면 네 arrival 앱을 SM-S942N 에서 빌드·실행할 수 있는지(A24 전용으로 고정된 부분)도 알려줘.
2. **대표 입력과 품질 기준** — A24 계약의 대표 입력(이미지 목록·SHA 또는 전처리 텐서), 참조 출력, 품질 판정 기준을 공유 가능한 형태로. 받으면 결과 전에 고정하고 같은 기준으로 S26 EffNet 3자원 품질을 잰다.

## 6. 일정 (제안)

| 날짜 | 할 일 |
|---|---|
| 10/4 | 이 회신 · 10/3 밤 push · 밤 EffNet 확인 블록 |
| 10/5 | §2 PC export · `out_0928` · 구간별 귀속표 |
| 대표 입력을 받은 뒤 | 대표 입력 품질 1세션 |
| 10/6~9 | 정책 확인 폰 재생 (요청 경계 기록) |
| 10/11 | S26 측정 동결 |
