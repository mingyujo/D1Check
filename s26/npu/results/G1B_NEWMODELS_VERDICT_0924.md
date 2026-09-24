# G1-B AOT 컴파일 결과 — 2026-09-24 (Colab, Ubuntu 24.04 x86_64) — **PASS (2/2)**

도구: `tools/COLAB_G1B_NEWMODELS.py` (무수정 실행) · `ai-edge-litert-nightly 2.3.0.dev20260922` +
`ai-edge-litert-sdk-samsung-nightly 2.3.0.dev20260922` · 타깃 `Samsung_E9965` · flatbuffers shim preloaded [P]
원본 산출물: `results/G1B_aot_manifest_20260924.json` (SHA `0111603796cd4e2d…`), `results/G1B_aot_report_20260924.txt`
(`C:\Users\rhoyo\Downloads\g1b_out.zip`, 12:27 에서 추출. manifest `generated_at 2026-09-24T03:20:14+0000`)

근거 라벨: `[P]` 실측 / `[D]` 문서 근거 / `[E]` 추정

| 입력 | 입력 SHA-256 (앞 16) | 산출물 | 크기 | 파티션 | 판정 |
|---|---|---|---|---|---|
| `efficientnet_lite0.tflite` (18,582,189 B) | `6c7ab0a6e5dcbf38` | `efficientnet_lite0_Samsung_E9965.tflite` (`311e4aac8fa1d8de…`) | **10,033,376 B** (0.54×) | **62 / 62 ops → 1 partition** (전 그래프 NPU) | PASS [P] |
| `efficientdet_lite0.tflite` (13,836,895 B) | `40338edf5ec70d43` | `efficientdet_lite0_Samsung_E9965.tflite` (`f51d082dbf68bef9…`) | **8,799,008 B** (0.64×) | **263 / 263 ops → 1 partition** | PASS [P] |

컴파일 시간 2.3 s / 4.0 s. 두 산출물 모두 `DISPATCH_OP` 1개, 비-dispatch 연산자 0개, `failed_backends: []` [P].
입력 해시는 조민규 `MODEL_02_INVENTORY.md` 고정값과 일치 [D]. `*_apply_plugin.tflite` 는 본 파일과 바이트 동일 [P].

## 읽는 법

- EfficientNet 산출물이 원본의 **0.54배** → MobileNet(0.53배)과 같이 가중치 FP16 저장 = NPU FP16 실행 [P+E].
  EfficientDet 은 **0.64배**로 절반보다 크다 — 이유 미확인 (FP32로 남은 상수가 있을 수 있음 [E])
- 두 모델 모두 **`npu_full` cell 후보**다. 단 아래 §종단간 주의와 §SDK skew 를 통과해야 측정값이 된다
- 판정은 **그래프 파티션** 판정이다. 기기에서 돈다는 뜻이 아니다 — 기기 스모크 미실시 (폰 미연결, 12:28)

## 종단간 주의 — "263/263"은 모델 그래프까지다

**(b) 원본 `efficientdet_lite0.tflite` 에 `TFLite_Detection_PostProcess` 가 있는가: SKIP — 원본 미확보.**
`g1b_out.zip` 에는 컴파일 산출물만 있고 원본은 없다. 원본에 대해서는 추측하지 않는다.

대신 **가진 파일(컴파일 산출물)** 을 flatbuffer 로 직접 읽은 결과 [P]:

| 모델 | 입력 | 출력 | `TFLite_Detection_PostProcess` 문자열 |
|---|---|---|---|
| EfficientNet-Lite0 | `images` FLOAT32 `[1,224,224,3]` | `Softmax` FLOAT32 `[1,1000]` | 없음 |
| EfficientDet-Lite0 | `serving_default_images:0` FLOAT32 `[1,320,320,3]` | **2개** — [0] `StatefulPartitionedCall:1` FLOAT32 `[1,19206,90]` (score), [1] `StatefulPartitionedCall:0` FLOAT32 `[1,19206,4]` (location) | 없음 |
| (대조) MobileNet V1 | `input` FLOAT32 `[1,224,224,3]` | `…/Reshape_1` FLOAT32 `[1,1001]` | 없음 |

- 컴파일된 모델의 출력은 **디코드 전 raw 2개**다. 박스·클래스·점수·개수 4개 출력이 아니다 [P]
- 팀 인벤토리도 같은 바이너리를 "raw score/location, anchor decode·NMS 는 MediaPipe Tasks 가 모델 밖에서 수행"으로 적었다 [D]
- 따라서 **anchor 디코드 + NMS 는 NPU 그래프 밖, CPU 에서 돈다** [P 출력 형태 + D 인벤토리]. 검출 task 의 종단간
  서비스 시간 = NPU `run()` + CPU 후처리. "EfficientDet 이 전부 NPU" 라고 쓰지 않는다
- 검출 품질 게이트 설계: `runner/NPU_DETECTOR_GATE_NOTE.md`

## SDK skew — 두 배치가 다른 컴파일러로 만들어졌다

| 배치 | 모델 | `ai_edge_litert` / Samsung SDK | 기기 검증 |
|---|---|---|---|
| G1 (9/19) | MobileNet V1 FP32 · INT8 | `2.3.0.dev20260917` | **✅ G4 PASS** (9/24, dispatch main@9380426b + AAR 2.2.0 + ENN 2.4.20) |
| G1-B (9/24) | EfficientNet-Lite0 · EfficientDet-Lite0 | `2.3.0.dev20260922` | **미검증** |

- 우리 dispatch `.so` 는 LiteRT main@9380426b(9/18)로 빌드됐다. dev20260922 컴파일러가 만든 바이트코드를 이 dispatch 와
  폰 ENN 2.4.20 이 받는지는 **기기에서 돌려 봐야 안다** [E]
- 참고: dev20260917 산출물로도 dispatch 는 `Header verification failed - using old format` 를 찍고 정상 실행했다 [P]
  (`G4_GO_2026-09-24456_4289_…_NPU.txt`). 컴파일러↔dispatch 헤더 형식이 이미 어긋나 있다는 뜻이라, 9/22 판에서
  형식이 한 번 더 바뀌었으면 실패할 수 있다 [E]
- 스크립트가 `pip install` 버전을 고정하지 않아 그날의 최신 nightly 가 들어갔다. PyPI 에 dev20260917 은 아직 있다 [P].
  재현용 줄: `pip install ai-edge-litert-nightly==2.3.0.dev20260917 ai-edge-litert-sdk-samsung-nightly==2.3.0.dev20260917`
- **MobileNet 을 새 SDK 로 재컴파일하지 않았다.** 어젯밤 게이트 결과와 비교가 깨진다 — 영훈이 정한다
- `npu-runner/src/main/assets/models/aot_manifest.json` 은 두 배치의 **병합본**으로 바꾸고 모델마다
  `compile_batch`·`ai_edge_litert`·`ai_edge_litert_sdk_samsung`·`compiled_at` 필드를 붙였다. 원본 manifest 두 개는 무변경

## 산출물 위치 (라이선스 경계)

| 파일 | 위치 | git | APK |
|---|---|---|---|
| `efficientnet_lite0_Samsung_E9965.tflite` | `npu-runner/src/main/assets/models/` | 제외 (`*_Samsung_E9965.tflite`) | 들어감 (Apache-2.0 metadata [D]) |
| `efficientdet_lite0_Samsung_E9965.tflite` | `npu-runner/local_models/` | 제외 | **안 들어감** — 라이선스 귀속 미확인. `adb push` 후 `--es model_path` |
| G1-B manifest · report | `results/G1B_aot_*_20260924.*` | 커밋 | — |

## 다음

1. 폰 연결 후 EfficientNet NPU 스모크 1회 — dev20260922 바이트코드가 도는지 (위 SDK skew)
2. EfficientNet 품질 게이트: 입력 `--es input_spec lcg-rgb-127-128`, CPU 기준 = 원본 `efficientnet_lite0.tflite`
   (**원본은 아직 로컬에 없다** — 고정 URL 에서 받아 SHA `6c7ab0a6…` 확인 후 assets 또는 기기에)
3. EfficientDet: 검출 게이트 구현 전까지 품질 게이트는 `NOT_APPLICABLE` (출력 2개 안전장치). 스모크는 가능
