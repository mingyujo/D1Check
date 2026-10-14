# A24 노트북 사전 준비: 모델·입력 원물 감사

2026-10-14. **PC에서 원물의 확보·출처·바이트/SHA·전처리 결합을 확인했다. 새 APK의 실제 기기 검증은 `DEVICE_UNVERIFIED`다.** 원래 측정 자료·소비 원장·기기 상태를 변경하거나 기기를 조회하지 않았다.

## 확인 대상과 결과

기존 CAL-03와 Resident03 계획의 `source_files`가 지정한 승인 원본 6개를 읽기만 했다. 두 계획은 같은 6개 바이트/SHA에 결합되어 있다. 현재 노트북에서 모두 확보되어 있으며 정확한 SHA가 일치한다. 개인 절대경로는 `output/a24_laptop_prep_20261014/materials.private.json`에만 남겼다. 공유 가능한 메타데이터는 [MATERIALS_BINDING.json](MATERIALS_BINDING.json)에 있다.

| 원물 | 버전·범위 | 바이트 | SHA-256 |
| --- | --- | ---: | --- |
| `efficientnet_lite0.tflite` | EfficientNet-Lite0 float32 v1 | 18,582,189 | `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0` |
| `efficientdet_lite0.tflite` | EfficientDet-Lite0 float32 v1 | 13,836,895 | `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58` |
| `labels_without_background.txt` | 분류 모델 내장 associated file, 1,000행 | 10,473 | `e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f` |
| `labels.txt` | 탐지 모델 내장 associated file, sparse 90행 | 661 | `f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2` |
| `anchors.json` | 탐지 모델 metadata의 고정 anchor 19,206개를 canonical JSON으로 추출 | 1,438,467 | `e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc` |
| `00575b9132bb3746.png` | 승인 canonical sRGB PNG v2, 1024×683 RGB | 937,799 | `3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab` |

모델 출처는 [EfficientNet 고정 v1 URL](https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite), [EfficientDet 고정 v1 URL](https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite)이다. 이번 작업에서는 원래 확보한 파일을 검산했으며 다운로드·모델 호출을 하지 않았다. labels는 같은 모델 내부 ZIP associated bytes와 직접 대조했다. anchors는 같은 모델의 flatbuffer metadata만 파싱해 19,206개 좌표와 canonical JSON SHA가 모두 같음을 확인했다. anchors에 출처에 없는 좌표를 만들지 않았다.

이미지 원출처는 [Open Images validation JPEG](https://open-images-dataset.s3.amazonaws.com/validation/00575b9132bb3746.jpg)이며 원 JPEG SHA는 `ef667f3f27d9a3d1faa7a84c8c54587faef0845a7a6e620aa0fd5fcfaf0a005f`다. Ed Uthman의 [ACT_3289](https://www.flickr.com/photos/euthman/5402229494), CC BY 2.0이다. 승인 파생 PNG는 기존 JPEG→sRGB 변환·metadata 제거의 완성 바이트를 재사용했다. 새 JPEG decode나 다른 이미지로 교체하지 않았다. canonical PNG의 chunk 제한과 RGB SHA `ca6c2e2bf77bfd8c9240404f516a17eb21c24ba34159ce2e3722bf8aaf225455`도 확인했다.

## 입력 tensor 결합 검산

모델 Interpreter를 만들거나 추론하지 않고 승인 RGB·정수 Q16 half-pixel bilinear resize·FLOAT32 정규화만 수행했다. 기존 CAL-03 CPU reference의 input tensor SHA와 모두 같았다.

| 작업 | 입력 tensor | 바이트 | SHA-256 |
| --- | --- | ---: | --- |
| 분류 | FLOAT32 little-endian RGB NHWC `[1,224,224,3]`, `(RGB-127)/128` | 602,112 | `603328d02dfc2b1aa356b26b0f14b9e70f8cdb80609c89fd171bcf4c3ff85462` |
| 탐지 | FLOAT32 little-endian RGB NHWC `[1,320,320,3]`, `(RGB-127.5)/127.5` | 1,228,800 | `e1ce665bedf565285adccc4098433e338b9cdb08d681e0c0d424cae521e273ad` |

adapter는 `explicit-image-task-v2`, 전처리는 `canonical-srgb-q16-stretch-v2`, 원본 입력 계약은 `canonical-srgb-png-v2`다. 탐지는 sigmoid score와 anchor-relative box를 기존 threshold 0.5/NMS IoU 0.3으로 해석하며 모델·라벨·anchor·출력 허용오차를 바꾸지 않는다.

이번 64/128/252 요청 bank에는 **현재 A24 arrival에서 승인·실측한 한 PNG를 모든 입력 슬롯에 반복 결합**할 수 있다. 이미지 순열 seed가 달라도 한 이미지이므로 이미지 순열 효과는 없다. 개발2블록·확인5블록의 새 ID/실행순서와 기기 반복은 구분하되 이를 새 이미지 품질·미관측 이미지 일반화 또는 새 도착 분포 검증이라고 부르지 않는다. 요청 수를 독립 이미지 수나 독립 측정 세션 수로 세지 않는다. 다른 19장 연구 이미지가 존재하는 사실만으로 이번 A24 혼합 요청의 승인 입력을 확대하지 않았다.

## 런타임·지원 경계

기존 승인값은 Android LiteRT 1.4.2, CPU thread 1, XNNPACK, `gpu-fp32-strict-v1`이다. GPU 설정 SHA는 `58ee1a9dad76bb62d85dedae9204790863eacc7d8c3c0da404505616ca098068`, precision loss 허용은 false다. GPU 내부 FP16 실제 실행 여부는 API로 노출되지 않으며 float32 모델 또는 strict 옵션만으로 확정하지 않는다.

새 주계획의 요청 후보는 분류 CPU/GPU·탐지 CPU와 검증된 `classification_GPU+detection_CPU` 최대2병행이다. 과거 탐지 GPU CAL-03 시간 기록이 있다는 사실을 새 주계획의 탐지 GPU admission 또는 단독 에너지/AP 검증으로 전용하지 않는다. 탐지 GPU 요청은 제외한다. 새 실행기는 기존과 같은4개 runtime(C_CPU/C_GPU/D_CPU/D_GPU)을 모든 STANDARD arm에서 같은 순서·각2회 warmup으로 유지한다. DG는 상주/워밍업에만 포함하며 본 요청 후보가 아니다. I의 unresident는 runtime0이다. 목록 동일성을 새 APK의 기기검증 완료로 해석하지 않는다.

이 감사는 원물과 기존 source 계약의 결합을 검산했다. 새 실행기/APK에 동일값이 실제 집행되는지는 PC 테스트·APK 정적 검사와 나중의 I/F 기기 검증에서 별도로 확인한다. 기존 host/reference의 PASS를 새 APK 실기기 PASS로 옮기지 않는다.

## 부족한 항목과 기기 실행 전 조치

- 승인 모델·labels·anchors·한 PNG 및 두 입력 tensor SHA는 **누락 없음**이다. 승인 범위 안에서 임의 대체가 필요하지 않다.
- 새 APK에서 GPU full delegation·출력 품질/CPU thread·실제 lane AVAILABLE·pair·WAIT·열보호가 유지되는지는 `DEVICE_UNVERIFIED`다. 원본과 일치하는 APK/manifest SHA를 동결한 뒤 I4/F4에서 확인해야 한다.
- 최신 기기 serial/fingerprint/드라이버·센서/AP 채널·충전/USB·실제 갱신주기와 초기 AP gate는 조회하지 않았다. 기기 등록과 계측 I4에서 확인하며 실패/미지원 항목을 null/UNSUPPORTED로 남긴다.
- EfficientDet exact 가중치 license/NOTICE 귀속은 기존과 같이 미확인이다. 비배포 연구 원본 확보만 유지하며 모델·anchor·이미지 바이트를 공개 저장소/APK/공유 ZIP에 넣지 않는다.
- CONFIRM 전 Tref 또는 그 산출식·허용범위, 센서 적분법/최대 gap/계측 오차 허용치, APK·입력·계측·초기 조건·분석을 동결해야 한다. PC에서 센서값이나 품질 PASS를 만들어 채우지 않는다.

PC 재검산은 private audit의 `python -B output/a24_laptop_prep_20261014/audit_materials_pc.py`다. 이 스크립트는 기존 원물 읽기와 SHA·metadata·전처리 검사만 수행하며 공개 대상에서 제외한다. 재검산 결과 6파일·내장 labels·anchor metadata·canonical RGB·두 tensor 결합 모두 PASS다. 검증 원본은 `materials.private.json`, 공유 메타데이터는 `materials.binding.json`/`MATERIALS_BINDING.json`이다.

원물 감사의 기존 별도 Python 환경은 NumPy2.4.6·Pillow12.2.0·flatbuffers25.12.19와 MediaPipe1.0.1의 schema 파일만 사용했다. ML 런타임을 import하지 않았다. 정확 schema/전처리/감사 스크립트 SHA는 [MATERIAL_AUDIT_DEPENDENCIES.json](MATERIAL_AUDIT_DEPENDENCIES.json)에 기록했다. 실제 수집 host의 `.venv-a24`는 이 패키지들 없이 표준 라이브러리만 사용한다. 두 환경을 혼동하지 않는다.

**본 감사의 실제 기기 명령 0·추론 0·계측 0·START/claim 0·측정 세션 소비 0.** 과거 측정 원장이나 세션을 재사용하지 않았다.
