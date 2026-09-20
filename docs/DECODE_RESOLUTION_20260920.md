# Detection decoded 원인 분리와 새 명시적 계약

외부 증거 E = `C:/Users/LG/Documents/D1Check_Decode_Resolution/`. 시작 HEAD `15e244c`, 조사 checkpoint `c4d3e6c`. 기존 artifact와 모델 ID는 보존한다. 아래 새 계약은 `explicit-image-task-v1`이며 기존 Tasks decoded 결과를 재해석하지 않는다.

## 최초 불일치 위치

1. **host CPU 대 A24 CPU의 기존 score 차이는 JPEG decode에서 시작한다.** 같은 JPEG SHA `85eb9ad2c6b0c397aa873faf97befc4a871d987cea822d9854617415778b6c8c`를 MediaPipe host가 읽은 RGB는 Android Bitmap/Pillow RGB와 47,984 channel 값이 다르고 최대 차이는 3이다. host Tasks에 Android와 같은 RGB를 주면 horse score가 0.6061195135에서 0.6078275442로 바뀐다. A24 CPU 0.6078266과의 차이는 약 9.44e-7이다. label/box 변환/JSON 단계의 문제가 아니다. E/`host_tasks_input_ablation.json`.
2. **기존 Tasks CPU/GPU에는 같은 전처리가 강제되지 않았다.** 공식 graph는 float GPU에서 GPU image preprocessing을 선택한다. CPU warpPerspective와 half-pixel resize를 분리한 ablation에서 score/box 변화가 재현된다. 내부 raw tensor를 제공하지 않는 Tasks의 GPU 정밀도와 전처리 효과 전부를 수치적으로 분리했다고 주장하지 않는다. 조사한 공개 source의 버전 경계는 E/`sources.json`에 남긴다.
3. **명시적 같은 tensor에서는 raw와 decoded 모두 기존 허용오차 통과.** E/`same_tensor_comparison_final.json`: host→A24 CPU raw 최대 절대오차 scores 4.1723e-7, boxes 3.9935e-6; CPU→GPU 각각 1.3709e-6, 5.8711e-6. 각 비교 1,805,364개 원소의 위반 0. decoded label/order 일치, score 차이 최대 8.3447e-7, box 차이 최대 5.3344e-5 px. score 0.001/box 2px 허용오차를 완화하지 않았다.
4. 새 진단에서는 Tasks GPU가 두 번 120초 내 완료되지 않았다. 독립 raw GPU는 완료됐다. 이를 기존 timeout과 동일 원인이라 단정하거나 Tasks GPU가 수정됐다고 기록하지 않는다. Tasks 경로를 새 실제 task adapter로 사용하지 않는다.

## 실제 모델 계약

- 모델: 기존 EfficientDet-Lite0 float32 version 1, SHA `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58`, 13,836,895 bytes. 원 URL `https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite`.
- 입력 slot 0/tensor index 0 `serving_default_images:0`, FLOAT32 `[1,320,320,3]`, quantization 없음.
- 출력 slot 0/tensor index 520 `StatefulPartitionedCall:1`, FLOAT32 `[1,19206,90]`: 이미 sigmoid된 class score. 출력 slot 1/tensor index 522 `StatefulPartitionedCall:0`, FLOAT32 `[1,19206,4]`: anchor-relative `(dy,dx,dh,dw)`. class/count 완성 tensor가 아니다.
- metadata의 19,206 fixed anchors `(cx,cy,w,h)`는 normalized. scale 모두 1, 크기는 exp 변환. `cy=dy*anchor_h+anchor_cy`, `cx=dx*anchor_w+anchor_cx`. 결과 box는 원본 이미지 pixel `(x,y,width,height)`로 변환하며 임의 clipping/정수화 없음.
- class offset 0, sparse 90행(실제 COCO 80 class 및 빈자리 10개) labels.txt. label SHA `f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2`. anchor JSON SHA `e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc`.
- threshold 0.5 inclusive, anchor별 argmax(동점 첫 index), class-agnostic greedy NMS IoU >0.3 제거, 결과 개수 제한 없음. NMS 전 score/anchor index 정렬, 최종 score desc/label/box 정렬. 결과 count는 accepted list 길이.
- 전처리 `rgb8-bilinear-q16-stretch-v1`: 방향이 적용된 RGB PNG, 정수 Q16 half-pixel bilinear, clamp와 round-half-up, 320 square stretch, crop/padding 없음, float32 `(RGB-127.5)/127.5`. JPEG decode가 요청별 runtime에 따라 바뀌지 않도록 canonical PNG를 external input으로 고정한다.
- 분류는 같은 resize 알고리즘의 224 square, 기존 metadata의 `(RGB-127)/128`, labels_without_background 1000행, top5 score desc/index tie.

## Host reference와 실제 품질의 경계

`python -m tools.d1_detection_contract --model <외부 모델> --image <RGB PNG> --output <새 외부 root>`는 ai-edge-litert 2.2.0 CPU 1-thread에서 같은 모델/전처리 3회 재현성을 검사한다. `golden.json`에 모델·입력·전처리·decoder hash, tensor metadata, raw hash, decoded 결과, runtime/version, 명령을 보존하고 f32le 파일을 별도 저장한다. host golden은 runtime equivalence reference이며 ground truth가 아니다.

실제 주석은 Open Images V7 공식 페이지가 제공하는 V5 validation bounding boxes와 원래 validation image metadata를 사용한다. 공식 URL·다운로드 시각·image/annotation SHA·저작자·원본 URL은 E/`validation_inputs/{source_manifest,subset_manifest}.json`. 주석 CC BY 4.0, 선택 이미지 metadata의 CC BY 2.0. 대용량 CSV/JPEG/PNG는 Git 밖에 있다.

모델 실행 전에 Bicycle/Car/Cat/Dog/Horse마다 정렬된 첫 4개 ID를 선택했다. group/depiction box는 제외하며 원본 normalized bbox를 원본 크기에 곱한다. 이 부분집합의 host 관측은 20장, 주석 box 28개 중 15개 일치(score≥0.5, 같은 label, IoU≥0.5). 부분 주석 때문에 unmatched prediction을 false positive로 단정하지 않고 mAP·전체 데이터셋 정확도·품질 승인으로 일반화하지 않는다. 정답 box/label을 새로 만들지 않았다.

## Provenance와 배포 제한

현재 float32 GCS binary의 metadata license는 null이고 exact weight NOTICE 귀속은 미확인이다. 저장소/Gradle AAR NOTICE/기존 manifest를 검색했으나 runtime Apache NOTICE를 모델 가중치 라이선스로 전용할 근거는 없었다. 현재 모델은 **기존에 허용된 실행자 직접 다운로드·비배포 연구 probe에 한해 유지**한다. APK/저장소/PR/팀 공유에 모델·anchor asset을 포함하지 않는다. 배포 라이선스 gate는 여전히 미완료다.

공식 대안 `https://www.kaggle.com/api/v1/models/tensorflow/efficientdet/tfLite/lite0-detection-metadata/1/download`도 확보했다. 내부 uint8 1.tflite SHA `2e04c53bfeac0ac2a30c057c7e2a777594ce39baaac35a92f74fb1e8c4fc4e0b`. float32 모델과 다른 4-output 계약이며 이번 runtime 동등성 해결에 섞지 않았다. 공식 model card와 provenance는 E/`model_candidate/`. 교체 승인 가능성과 실제 교체 완료는 구분한다.

## 실제 완료와 bounded profile

`TaskProfileActivity`는 modelProbe source set에만 있다. 외부 검증 모델·canonical PNG를 읽고 실제 LiteRT inference와 decoder를 실행한다. urgent 완료는 직렬화된 output-ready, normal 완료는 write/flush/fsync/rename/readback 이후다. UI 표시 시간은 별도이며 output-ready를 화면 표시 완료라고 하지 않는다. requested backend와 actual backend를 구분하고 GPU는 session/PID별 full-delegate 로그 확인 전까지 unverified다.

`task-profile-v1`은 새 UUID root, 요청 ledger, root-only provenance self-exclusion, 파일 hash/크기/허용 집합과 monotonic 완료 경계를 검증한다. 모델 검증은 session setup에서 제외되며 cold runtime 생성/전환은 service에 포함한다. 120초 hard bound, 최대 48요청, 최대 두 worker, CPU 1-thread, thermal status >1 중단. 500ms process PSS 표본은 연속 true peak가 아니며 온도는 에너지 측정이 아니다.

실측 결과와 실패 세션은 E/`profiles/`, 사전 recipe는 E/`profiling_plan.json` 및 `recipes/`. deadline/품질 승인 하한/서비스 안정성·holdout 오차 허용값은 별도 근거가 없으면 pending을 유지한다. 본 scheduling simulation·formal·정책 비교는 실행하지 않는다.

### ?? profile v2

20-image CPU session? Activity? invisible? ?? ?? ? 27?? ??? ??? host 120? timeout?? ???. OS ?? ??? ???? ???. 6? ?? result? ????? finalized service? ???? ???. `task-profile-v2`? bounded Activity?? show-when-locked/turn-screen-on/keep-screen-on? ???? ??? fsync event journal? ????. ?? ?? ??? ???? ???. v1 artifact? ???? validator? v1/v2? ????? ????. ?? ?? 20?? ??? ?? 10?? ????.

`service-observations-v1` schema? ???? ?? ?? artifact? cold/warm?task/backend/priority/role? ns ??? ?? ?? ?? ???? ????. ??? diagnostic_not_frozen?? deadline? ?? ?? ?? pending??. ?? frozen simulation profile? ??? ? ??.

### ?? canonical ?? ?? v2 / profile v3

?? 10?? ?? adapter ???? 001a794d1865ee47? ?? PNG?? tensor hash? ???. PNG iCCP? ?? Android? host? ?? ??? ????. host ICC?sRGB ablation? score ??? 0.00405?? ? 0.00056?? ???? ?? ????? ? bit ??? ????. E/icc_ablation.json? ??/??/Android ??? ????.

?? ??? `canonical-srgb-png-v2`: ?? JPEG? Pillow? decode, ICC? ??? LittleCMS perceptual intent 0?? sRGB ??(??? sRGB ??), ????? ??, ? RGB pixel container? ?? ancillary chunk ??. IHDR/IDAT/IEND ? chunk? ???? ?? ?? ????. ?? canonical_png_v2_final/manifest.json? ??/PNG/RGB/ICC hash? Pillow/LittleCMS ??? ????. ?? canonical_png? host_validation? ???? ? host_validation_v2?host_classification_v2? ????. generator ??? ID? canonical-srgb-q16-stretch-v2, adapter? explicit-image-task-v2, profile? task-profile-v3??. ?? binary????threshold?NMS?tolerance? ??? ???. ?? host ?? box ??? ??? 15/28?? ?? ??? ??? ????.
