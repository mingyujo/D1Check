# MODEL-02A 모델·라벨·호스트 검증 inventory

- 조사일: 2026-09-18
- 상태: **MODEL_02A_CONDITIONAL_PASS**
- 상위 계획: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.4, [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)
- 범위: host에서 공식 배포 artifact·labels·metadata·tensor·고정 입력 출력을 검사했다. Android production, APK, 어떤 실기기의 CPU/GPU, delegation, 실제 이미지 품질은 검사하지 않았다.
- 저장 원칙: 모델 바이너리와 호스트 실행 산출물은 저장소/PR에 넣지 않는다. 이 문서에는 재현 가능한 URL·해시·계약·판정만 남긴다.

## 1. 판정

| 역할 | 후보 | MODEL-02A 판정 | 다음 단계 |
| --- | --- | --- | --- |
| 분류 | EfficientNet-Lite0 FLOAT32 v1 | **HOST_CONTRACT_PASS** | 외부 bundle을 별도로 고정한 뒤 MODEL-02B 기기별 CPU/GPU·품질·메모리 smoke 후보 |
| 탐지 1순위 | EfficientDet-Lite0 FLOAT32 v1 | **HOST_CONTRACT_PASS_RESEARCH_ONLY** | 외부 manifest로 검증하는 승인 기기 내부 비배포 probe만 허용; 저장소·APK·공유물 포함 금지 |
| 탐지 사전 대안 | SSD MobileNetV2 FLOAT32 v1 | **NOT_APPROVED** | license 공백과 decoded golden 미완료. 현재 후보를 대체하지 않으며 추가 진행하지 않음 |

두 PASS는 host 계약만 뜻한다. 각 Android 기기의 지원, GPU full delegation, latency, memory, 일반적인 실제 이미지 정확도는 미확인이다. EfficientDet exact binary의 metadata `license`는 비어 있고 exact license/NOTICE 연결은 확보하지 못했다. Google 공식 안내와 Apache-2.0 sample의 exact URL 사용은 비배포 연구 probe를 조건부 허용하는 위험 판단의 근거일 뿐 binary license의 증거로 전용하지 않는다.

## 2. 공식 출처와 byte identity

`latest`는 변할 수 있으므로 실험 후보는 `/1/` URL로 고정한다. 조사 시점의 `latest`와 v1은 각 후보에서 byte-identical이었다.

| 후보 | version-pinned URL | bytes | SHA-256 | latest와 동일 | Last-Modified / ETag |
| --- | --- | ---: | --- | --- | --- |
| EfficientNet-Lite0 FLOAT32 | `https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite` | 18,582,189 | `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0` | yes | 2023-04-26 / `0edae254acef24a66c3729fca3759655` |
| EfficientDet-Lite0 FLOAT32 | `https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite` | 13,836,895 | `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58` | yes | 2023-04-27 / `ca669b1df0ebe9a75ddcde57fe07a0d0` |
| SSD MobileNetV2 FLOAT32 | `https://storage.googleapis.com/mediapipe-models/object_detector/ssd_mobilenet_v2/float32/1/ssd_mobilenet_v2.tflite` | 11,316,189 | `b8ccb1a25d45455ba52e85f26531948e1cb75efeb94c7c3d456d54fd4d6fbdd2` | yes | 2023-05-03 / `83567e09570f0e84897294c4f1f722db` |

공식 후보 근거:

- [MediaPipe Image Classifier 모델 안내](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier)는 EfficientNet-Lite0 FLOAT32를 권장 후보로 제시한다.
- [MediaPipe Object Detector 모델 안내](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector)는 EfficientDet-Lite0 FLOAT32를 권장하고 SSD MobileNetV2 FLOAT32를 더 빠르고 가벼운 대안으로 제시한다.
- Google의 MediaPipe sample/benchmark source는 위 v1 EfficientNet/EfficientDet 객체 URL을 직접 사용한다. 이는 배포 주체·버전 경로 근거이며 별도의 binary license 증명은 아니다.

## 3. 라벨·index 계약

| 후보 | 모델 내 associated file | 행·의미 | 파일 SHA-256 | 외부 공식 label과 관계 |
| --- | --- | --- | --- | --- |
| EfficientNet-Lite0 | `labels_without_background.txt` | 1000행, output index 0..999와 직접 대응 | `e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f` | 외부 1001행 `labels.txt`의 1..1000행과 정확히 동일. 외부 0행 `background`는 이 모델 output에 넣지 않음 |
| EfficientDet-Lite0 | `labels.txt` | 90행, 80 object + 10 `???`; score 마지막 축 index와 직접 대응 | `f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2` | 외부 공식 `labelmap.txt`와 byte-identical |
| SSD MobileNetV2 | `labels.txt` | 91행, 0행 `background` + 위 sparse 90행 | `f25af66ef3bd4df192d007985761c9a0479a6245f693b604c70c501188907ef6` | EfficientDet용 90행 파일을 대신 쓰면 한 칸씩 어긋남 |

외부 분류 `labels.txt`는 10,484 bytes, SHA-256 `536feacc519de3d418de26b2effb4d75694a8c4c0063e36499a46fa8061e2da9`다. 외부 탐지 `labelmap.txt`는 661 bytes이며 위 EfficientDet 내장 label과 같은 해시다. 기존 MobileNet V1의 1001행 라벨 blocker와 새 EfficientNet 계약은 별개다.

## 4. tensor·metadata 계약

| 후보 | input | normalization | raw output | metadata license |
| --- | --- | --- | --- | --- |
| EfficientNet-Lite0 | `images`, FLOAT32 `[1,224,224,3]` | `(RGB - 127.0) / 128.0` | `Softmax`, FLOAT32 `[1,1000]` | `Apache License. Version 2.0 ...` |
| EfficientDet-Lite0 | `serving_default_images:0`, FLOAT32 `[1,320,320,3]` | `(RGB - 127.5) / 127.5` | score `[1,19206,90]`, location `[1,19206,4]` | **null** |
| SSD MobileNetV2 | `serving_default_inputs:0`, FLOAT32 `[1,256,256,3]` | `(RGB - 127.5) / 127.5` | location `[1,12276,4]`, score `[1,12276,91]` | **null** |

EfficientDet/SSD의 일반 LiteRT Interpreter 출력은 후처리 전 anchor score와 box encoding이다. 이를 완성된 bounding box 결과로 부르지 않는다. MediaPipe Tasks ObjectDetector가 anchor decode/NMS/canonical result를 수행하므로 TASK-02에서 API 호출 경계와 postprocess 결과를 별도 계측해야 한다.

## 5. 고정 host smoke

검증 환경은 Linux x86_64, Python 3.12, `ai-edge-litert==2.2.0`, FLOAT32, CPU XNNPACK, thread 1이다. 좌표 기반으로 생성한 고정 RGB pattern을 metadata 정규화한 뒤 같은 Interpreter instance에서 3회 실행했다. 실행시간은 host 배선 참고일 뿐 어떤 Android 기기의 성능 자료도 아니다.

| 후보 | 결과 | 고정 output hash | host 호출시간 3회 |
| --- | --- | --- | --- |
| EfficientNet-Lite0 | 3회 동일, finite, 확률합 1.0 | `1631fd1c188034ac73b0589d117901bd41519631718a9adb94f7c0b0706efda2` | 17.520 / 18.630 / 11.166 ms |
| EfficientDet-Lite0 score | 3회 동일, finite | `0344b5e19ab41f362d36a44a3fc31b54f131738a6d52693d931e092885a4cb58` | 전체 raw invoke 24.124 / 23.933 / 23.289 ms |
| EfficientDet-Lite0 location | 3회 동일, finite | `c95e1b70982b45707eafd54499fbb496868e95895de877e921835378553d0056` | 위와 동일 |
| SSD MobileNetV2 score | 3회 동일, finite | `3fabd167d0952bdb64b0b1c713186b8aef43705f13c4b99ba79a2c1a21f61bc6` | 전체 raw invoke 20.270 / 12.502 / 11.816 ms |
| SSD MobileNetV2 location | 3회 동일, finite | `5e3d4383cd3de72b4f2e9e1e70cc73fe243f71c856ca500dde71f59d45a4318b` | 위와 동일 |

고정 pattern은 runtime·tensor·label wiring 회귀용이며 모델 품질 표본이 아니다.

EfficientDet decoded golden은 누락된 `libGLESv2.so.2`를 저장소 밖 임시 system-library 디렉터리로 제공한 뒤 실행했다. MediaPipe Tasks `1.0.1`, CPU XNNPACK, score threshold `0.5`, 동일 ObjectDetector instance에서 공식 sample `cat_and_dog.jpg`(69,041 bytes, SHA-256 `cfa90c34bb93021165e48bd22cfc20dbbb0440ff638a54878939bf30d362e824`)를 3회 처리했다. 검출 순서의 `box=[x,y,width,height]`, `label`, full-precision `score`만 남기고 JSON key 정렬·공백 없는 UTF-8로 직렬화한 canonical result SHA-256은 세 번 모두 `83de431de773572d37ad8849bbca261ae92995fa6208f950823ccfbd40d60413`였다.

| label | score | box `(x, y, width, height)` |
| --- | ---: | --- |
| cat | `0.7802969217300415` | `(72, 162, 252, 191)` |
| dog | `0.7625645399093628` | `(303, 27, 249, 345)` |

host 호출시간은 환경 준비 상태에 따라 변동했으며 실기기 latency, deadline 또는 시뮬레이션 service time으로 기록하지 않는다. 이 표본은 Tasks decode/NMS/label wiring 회귀이며 일반 품질 평가가 아니다.

## 6. 라이선스 판정 근거와 한계

- EfficientNet exact binary의 TFLite metadata는 저자 `MediaPipe`와 Apache License 2.0 문자열을 포함한다. 공식 bucket/version URL·내장 label과 함께 host 후보 승인 근거로 사용한다.
- EfficientDet와 SSD exact binary는 저자 `MediaPipe`를 기록하지만 metadata license가 null이다. GCS response에도 license metadata가 없었다.
- TensorFlow/Kaggle의 공식 EfficientDet variants와 MediaPipe sample code에는 Apache-2.0 표기가 있다. 그러나 내려받아 확인한 공식 metadata TFLite는 4,563,519 bytes, SHA-256 `2e04c53bfeac0ac2a30c057c7e2a777594ce39baaac35a92f74fb1e8c4fc4e0b`, UINT8 입력·decoded 4-output으로 현재 GCS FLOAT32 binary와 byte/계약이 다르다. exact artifact license로 전용하지 않는다.
- COCO 학습 데이터 license나 architecture/source-code license는 배포된 weight file의 license를 자동으로 증명하지 않는다.
- 따라서 탐지 binary를 저장소·PR·APK·팀 공유 bundle·제출물에 넣지 않는다. Google 공식 안내와 sample의 exact URL 사용을 근거로 URL·bytes·SHA-256을 고정하고 각 실행자가 원 URL에서 직접 확보하는 승인 기기 내부 연구 probe만 조건부 허용한다. 이는 법적·재배포 승인이 아니며, 배포 전에는 공식 model card/NOTICE가 exact URL/hash를 사용 가능한 조건에 연결하거나 명시적으로 라이선스된 artifact로 교체해야 한다.

## 7. 다음 gate

1. `MODEL-02B-PREP`은 [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md)의 외부 manifest·app-private staging·비교·cleanup·판정 계약으로 완료했다.
2. `MODEL-02B-SEAM`에서 debug-only loader, raw/decoded adapter, host validator와 no-I/O dry-run을 구현·검증한다. binary는 Git/APK에 넣지 않는다.
3. 그 뒤 별도 승인된 `MODEL-02B` A24 pilot에서 CPU/GPU strict delegation, decoded result quality, memory, cold/warm을 측정하고, seam 통과 뒤 같은 계약으로 추가 기기를 probe한다. 배포가 필요해질 때까지 exact license 조사는 열린 제한으로 유지한다.

deadline은 `calibration_pending`, 서비스·효과·안전 수치는 `thresholds_pending`을 유지한다. 이번 host ms를 deadline이나 시뮬레이션 service time으로 사용하지 않는다.
