# D1Check 현재 상태

- 갱신: 2026-09-20 재개 진행 중. A24 연결 복구·최종 APK 설치 확인; SIM-01 준비는 INCOMPLETE.
- 재개 E: C:/Users/LG/Documents/D1Check_Decode_Resolution/resume_20260920T090545Z/. 시작 adb5c38, clean. 이전 FINAL_REPORT.md와 모든 기존 결과 보존.
- 현재: 새 canonical 계약 네 cell 각각 20장 동등성 PASS, CPU↔GPU 직접 비교 40쌍 PASS. 8 session/80요청 완료. bounded profile 진행 중. 본 simulation/formal 미실행.
- [재개 상세](A24_RESUME_20260920.md). 탐지 CPU/GPU 공식 부분 주석 15/28 bbox 일치. 품질 승인과 동등성은 별도다.
- 신규 발견: 이전 외부 classification_reference_v2.py가 v2 manifest와 이전 PNG bytes를 혼용하고 선언 hash를 복사했다. 새 tools/d1_classification_reference.py는 실제 bytes/hash를 강제 연결하고 raw·tensor metadata·3회 재현성을 기록한다. 이전 잘못된 golden/실패 판정 보존.
- 검증: 신규 host generator targeted 11건 및 전체 Python 254건 PASS(기존 skip 2). Android 코드 변경 없음; 검증된 APK 8b805d3 그대로 설치·원격 hash 확인.
- 후속 validator: v3 raw hash 개수/형식·task/timing/geometry·cold 전환을 재검증한다. targeted 17건/전체 Python 258건 PASS(기존 skip 2). rehashed false warm 표기로 GPU 증거 검사를 우회하지 못하게 했다.
- 진행: solo 네 cell 각 2 session 완료, CPU↔GPU 전환 완료. matched solo/co-run/holdout 진행. host ADB daemon 조회 1회 실패는 Activity 시작 전이며 bounded start-server 1회 복구 후 새 UUID 사용.
- 이전 전송 UUID 86bea279-338f-4e8d-b2b2-f35d5efbd986의 잔존 조각 4개 소유/hash 확인 후 해당 device staging만 정리. host 조각은 실패 증거로 보존.
- 아래는 이전 종료 기록이다. 재개 결과가 확정되면 capability/profile/다음 행동을 갱신한다.
- 브랜치 feature/pre-simulation-ready-20260919, 시작 15e244c, 코드 checkpoint 9f68568. push/merge/rebase/master 전환 없음.
- 현재 작업: MODEL-02B decoded gate → TASK-02/PROFILE-02 준비. 본 simulation·formal·정책 비교 미실행.
- 외부 E: C:/Users/LG/Documents/D1Check_Decode_Resolution/. 상세 FINAL_REPORT.md, device_disconnect.json, verified_source_files.json.
- 장애: 08:21 UTC APK 전송 EOF/device offline, 08:22 UTC ADB 목록 비어 있음. 실기기 재시도 중단.
- 정리 미확인: /data/local/tmp/d1check-model-probe/86bea279-338f-4e8d-b2b2-f35d5efbd986. 이번 APK 임시 조각만 잔존 가능하며 기존 결과는 삭제하지 않는다.

## decoded 원인과 최종 구현

- [상세 계약](DECODE_RESOLUTION_20260920.md). 기존 host/A24 CPU 차이는 JPEG RGB decode부터 발생했다. 같은 RGB를 host Tasks에 주면 score 차이 0.001707 → 약 9.44e-7.
- Tasks CPU/GPU는 전처리 경로가 다르다. 명시적 동일 tensor의 host CPU↔A24 CPU↔A24 GPU raw/decoded는 기존 tolerance 통과. Tasks 내부 효과 전체와 과거 timeout 원인까지 확정하지 않았다.
- 신규 Tasks GPU 두 session은 120초 미완료, 독립 LiteRT GPU는 완료. Tasks를 실제 adapter/profile에서 제외했다. silent fallback 없음.
- 실제 10-image 실행은 완료했지만 한 PNG의 iCCP로 tensor/decoded 불일치. host ICC→sRGB 변환 및 metadata 없는 RGB PNG 계약으로 수정했다. 기존 데이터·threshold·tolerance는 보존했다.
- 최종: canonical-srgb-png-v2 / canonical-srgb-q16-stretch-v2 / explicit-image-task-v2 / task-profile-v3. **기기 설치·검증 전에 연결 단절**.
- 실제 read/decode/resize/inference/decoder, urgent output-ready, normal write/flush/fsync/rename/readback, 요청별 durable event·hash/provenance 검증 구현.
- bounded Activity에만 화면 유지 적용. 이전 invisible 진행 중단을 OS kill/native hang으로 확정하지 않는다.

## A24 capability와 품질

| Cell | 기존 raw/진단 근거 | 최종 task 계약 |
| --- | --- | --- |
| classification CPU | 기존 raw PASS | UNVERIFIED: 새 이미지 기기 미실행 |
| classification GPU | 기존 strict full GPU/수치 PASS | UNVERIFIED: 새 이미지 기기 미실행 |
| detection CPU | 동일 tensor raw/decoded PASS | UNVERIFIED: 최종 색상 수정 미검증 |
| detection GPU | 동일 tensor raw/decoded PASS | UNVERIFIED: 최종 색상 수정 미검증 |

- runtime 미지원 판정은 아니다. 네 cell 및 classification GPU + detection CPU 축소 구성 승인 보류. requested/actual backend 분리 유지.
- 공식 Open Images validation 20장: V7 download의 V5 bbox, 주석 CC BY 4.0/선택 이미지 metadata CC BY 2.0. 원본·주석·ICC·RGB·PNG SHA/URL은 E/validation_inputs.
- host 품질: 지정 5-class bbox 28개 중 15개 일치(score≥0.5, IoU≥0.5). 작은 부분 주석 표본이며 전체 정확도·mAP·품질 승인 아님. host golden은 ground truth가 아니다.
- EfficientDet float32 SHA 40338edf...dbf58 유지. exact license/NOTICE 미확인, 기존 실행자 직접 확보·비배포 연구 probe 한정. 공식 uint8 대안 미채택. 외부 모델은 Git/APK에 없음.

## 실제 실행과 준비

- 신규 decode 진단 4 session: CPU complete 1, raw GPU complete 1, Tasks GPU 관련 timeout 2. E/device.
- profile 5 session: 사전조건 실패, appended ZIP 라벨 읽기 실패, 정상 1건 완료, 20건 미완료, 10건 완료(동등성 9/10). E/profiles.
- 예정 도착 33건 중 실행 완료 11건, failed/unfinished 22건 보존. 동등성까지 확인된 완료 10건. 서로 다른 디버깅 계약을 formal 분포로 합치지 않는다.
- 10건 session warm service 548.6~578.1ms, sampled peak PSS 193,526kB/thermal 0 관측. 미승인 이전 계약의 진단값이며 최신 profile로 전용 금지. 온도는 에너지가 아님.
- 최종 solo/전환/co-run/독립 holdout 미실측. 사전 bounded recipe/runner는 E에 준비했다.
- service-observations-v1 schema/집계는 diagnostic_not_frozen. B0/B1 순수 결정 함수, B2/B3/P 인터페이스·의미, workload/seed/KPI/no-op 준비. 정책 비교 없음.
- no-op: dispatch 0/가상 완료 0/비교 null/INCOMPLETE. deadline=calibration_pending; 품질 하한·안정성·holdout 오차·안전/서비스/반복 동결 pending.

## 검증과 보존

- 코드 9f68568. 명령 당시 bc07942 + 색상 계약 변경을 E/verified_source_files.json으로 연결한다.
- debug JVM 119/modelProbe JVM 115: failure/error/skip 0. Python 250: failure/error 0, Windows symlink skip 2. variant 중복을 고유 테스트로 합산하지 않는다.
- lintDebug error 0/warning 76; assembleDebug/modelProbe/release, compileall, logger self-test, no-op, diff check 통과. 최종 Gradle 342 task 중 22 실행/320 up-to-date.
- 최종 APK 8b805d3acfcede25fe6e4bcd17075d172c5ef66b425ff40ff29e2317ffce2489: host build/격리 PASS, **기기 미설치**.
- 마지막 설치 검증 APK 6b3b32cf37cc5590ab6adc68dd76d7c6a6a99629692d10696fc0de70d4a6f5b8: task-profile-v2. E/apks에 두 APK 보존.
- debug/release에 probe/MediaPipe/외부 새 모델 없음. legacy MobileNet 유지. app APK 격리도 확인.
- 모델·40개 canonical 이미지/원본/주석 쌍·42개 host raw 세트 hash 통과. 기존 probe 161파일은 설치 전 archive 4개에서 불변. 단절 이후 원격 최종 hash/정리는 미확인.
- formal v1/diagnostic v2/calibration-v1/image-v3/공식 timer/A24 80슬롯/S26/기존 보고서 보존. 이전 E0=C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/.

## 다음 행동

1. 승인 A24 ADB 연결 복구·fingerprint 확인 후 위 정확한 staging UUID만 확인·정리. 새 UUID로 최종 APK 설치/SHA 검증. 추가 모델·dataset 다운로드는 불필요하다.
2. 새 canonical 20장과 host_validation_v2/host_classification_v2로 네 cell을 10장 chunk별 검증. tensor/decoded·actual backend·공식 bbox 품질을 구분한다.
3. 통과 cell만 사전 solo/전환/최대 두 건 co-run/holdout 수행. 품질·안정성·holdout 오차·deadline 근거를 동결한 뒤 SIM-01 재판정. 본 simulation·formal은 계속 금지.
