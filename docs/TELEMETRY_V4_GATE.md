# TELEMETRY-V4-GATE

2026-09-21 KST. 기존 `task-profile-v3`와 별도인 `task-profile-v4`, schema_version=1을 구현했다. v4 Activity/adapter/model map/telemetry는 modelProbe source-set에만 있고 debug/release에 포함되지 않는다. formal v1, diagnostic v2, calibration-v1/image-v3, 기존 TaskProfileActivity/ProbeRawAdapter/ProbeTaskAdapter 및 decoder는 수정하지 않았다.

## 경계와 시계

모든 기기 timestamp는 `SystemClock.elapsedRealtimeNanos`다. Session/runtime/request UUID, task, requested backend, actual backend 확인 상태, worker, event sequence, terminal state를 기록한다. 전역 event의 해당 없는 identity는 null/not_applicable이며 임의 runtime을 붙이지 않는다.

| 범위 | 실제 기록 경계 |
| --- | --- |
| Session | session_start/end, workload_start/end |
| Runtime | creation_requested, model_file_open start/end, model_map start/end, interpreter_construction start/end, tensor_allocation start/end, runtime_ready, runtime_close start/end |
| GPU | delegate_creation/attachment/close start/end; CPU는 delegate not_applicable |
| Request | enqueue, worker_acquisition_start, worker_dispatch, queue_wait_end, active_service start/end, preprocess start/end, invocation start/end, output_readback start/end, decode_postprocess start/end, output_ready, normal persist_complete, worker_release start/end, request_terminal |
| Memory | runtime 생성 전, 각 runtime 상주 후, warmup/요청 전 admission, workload 전 admission, 500ms sampling, close 후 snapshot |

model_file_open은 검증된 파일의 mapping용 FileInputStream 열기이며 SHA 검증 IO 전체를 뜻하지 않는다. SHA/label/anchor 검증은 runtime creation_requested~ready의 setup에 포함된다. Android process fork 시각이나 GPU 내부 kernel/fence 경계는 관측하지 않아 만들지 않는다.

공식 inference는 기존 `val startedNs = elapsedRealtimeNanos(); interpreter.runForMultipleInputsOutputs(...); val finishedNs = elapsedRealtimeNanos()`의 동일한 세 줄이다. 내부에 logger 호출을 넣지 않았다. 두 timestamp를 반환 후 기록하고, 모든 event를 captured monotonic 시간순으로 병합해 sequence를 부여한다. 요청/동시 worker 사이 병합이며 timestamp를 logger 호출시각으로 바꾸지 않는다. 원본 timer block byte 비교 Python 테스트와 실제 artifact의 inference_ns=invocation_end-start 검증을 함께 사용한다.

긴급 active 종료는 output_ready, 일반은 persistence 완료다. 긴급 결과 저장과 worker release는 별도 점유시간에 들어간다. worker release start→Semaphore.release→end와 최종 request terminal을 분리한다. 최종 runtime_close는 interpreter/delegate 전체 정리를 감싼다. 닫힌 요청 identity는 runtime cleanup에 붙이지 않는다.

GPU event의 actual_backend는 `GPU_unverified`로 정직하게 기록한다. Native event를 사후 GPU로 덮어쓰지 않는다. 같은 session/PID의 full delegation·kernel 생성·fallback 부재를 host에서 검증한 receipt만 actual GPU로 승인한다. GPU 로그가 없으면 성공 artifact라도 gate를 통과할 수 없다.

## fail-closed 및 source contract

`tools/d1_telemetry_v4.py`와 event JSON Schema가 missing/duplicate/reversed event, 음수·다른 clock, session/request/runtime/worker/backend 불일치, 다른 protocol, terminal 이후 실행, stale manifest/hash·consumed UUID·동일 trace 재명명 replay를 거부한다. 성공에서는 정확한 runtime/request event 집합, 두 residency snapshot, setup/close가 workload 밖임, 모든 warmup/요청 terminal을 요구한다. Failure artifact는 성공으로 전용하지 않는다. 현재/이전 UUID registry 검사는 ingestion 시 수행하며 같은 저장 artifact의 read-only 재검증과 replay ingestion을 구분한다.

APK/input/model을 manifest/hash로 결합한다. 앱은 새 output root만 허용하고 120초 watchdog 및 요청·arrival bound를 유지한다. smoke manifest는 runtime당 warmup2회와 active≤8요청만 허용한다. 미래 `instrumentation_calibration` 입력은 warmup2~20/runtime 및 전체≤48/arrival≤60초/120초 bound를 지원하지만 **이번에는 실행하지 않는다**. 제공 plan 생성기는 오직4개 telemetry_smoke만 만든다.

## Resident control와 memory baseline gate

CPU-only는 classification/detection CPU runtime 두 개를 worker0의 단일 실행 lane에 사전 생성한다. 두 runtime 모두 동일한 warmup을 마친 뒤 timed workload를 시작한다. Runtime은 모든 요청이 끝나야 닫는다. Co-run은 CPU/GPU를 각 owner worker에 상주시켜 같은 setup/warmup 절차를 거친다. setup을 한 arm에만 active workload 비용으로 넣지 않는다. Native 모델 CPU thread=1 및 기존 preprocessing/decoder/출력 검증 계약을 유지한다.

`android-low-memory-resident-v1` baseline:

- ActivityManager.MemoryInfo의 availMem/threshold/lowMemory, memoryClass/largeMemoryClass, Debug.MemoryInfo PSS 및 thermal/battery를 같은 monotonic domain에 기록한다. snapshot start/end도 기록한다.
- `thermal==0 && !lowMemory && availMem-threshold > max(threshold, observed_peak_process_PSS)`를 요구한다. PSS/threshold가 없거나 유효하지 않아도 거부한다. 고정 MB를 임의 headroom으로 추가하지 않는다.
- reserve는 Android low-memory threshold와 이 실행에서 **이미 관측한** footprint에 근거한 보수적 baseline이다. 실제 최대 PSS·allocation 상한·OOM 불가능 보장이 아니다. memoryClass를 native/GPU PSS 상한으로 사용하지 않는다.
- Runtime 생성 직전, 각 invocation 직전, workload 시작 직전에 재검사한다. workload 전 gate가 거절되면 workload_start가 없어야 한다. 요청 실패/gate 거절 이후 신규 실행은 latch로 중단하고, 이미 실행 중인 native 호출은 임의 취소하지 않고 정리한다.
- 경계 및500ms sampled PSS 최대만 보고한다. runtime0/1/2개 상주 상태를 별도 기록하고, 장시간·다른 thermal/pressure 조건으로 일반화하지 않는다. 기존318,364kB를 v4의 hard limit으로 재해석하지 않는다.

## Paired 및 V2 joint 계약

Pair ID/seed/task mix/arrival/input/model/preprocessing/warmup/count/deadline null/thermal/memory/terminal 경계를 동일 hash로 결합한다. 두 arm은 새 session/request/runtime UUID를 갖고 seed로 사전 선택한 AB 또는 BA를 따른다. 실제 비교 검증에는 두 성공 receipt, 순서·기기 monotonic 시간·시작/종료 thermal drift가 필요하다. partial/failed pair는 거부한다. 이번 paired 계약의 dry-run 및 smoke 구조 확인은 정식 paired calibration이나 성능 비교가 아니다.

`service-v2-joint-v4` schema와 `joint_sample/resample_session`은 전체 session block을 선택해 provenance와 runtime identity를 보존한다. setup과 active를 서로 다른 session에서 독립 추출하지 않는다. 동일 runtime setup은 여러 요청에 참조되더라도 한번의 lifecycle 비용이며 요청마다 가산하지 않는다. queue wait/worker occupancy도 분리한다.

Invocation1=cold_first,2=early_after_cold,이후 warm이라는 ordinal label을 저장하되 **warm_qualified=false**다. 안정화 K를 승인한 것이 아니다. transition_after_setup 필드는 지원하지만 resident smoke에서 재생성 전환이 발생하지 않았으므로 observed=false/이유를 기록한다. 전환 비용을 임의 생성하지 않는다. 새 calibration에서 준비·전환/안정화 범위와 서비스모델을 별도로 검증해야 한다.

## 검증과 후속 작업

보고서/로그 root: `C:/Users/LG/Documents/D1Check_Telemetry_V4/run_20260920T144315Z/`.
Host 최종 검증: targeted Python29 PASS, 전체370(368 PASS·기존skip2), targeted V4 JVM11 PASS, debug JVM119 PASS, modelProbe JVM126 PASS, lintDebug/assembleDebug/modelProbe/release build/compileall/logger self-test/diff-check PASS. Debug/release에 v4 class·외부 EfficientNet/Det binary가 없음을 검사했다. 기존 APK는 `legacy_apks`에 hash 동일한 복사본으로 보존한다. 이전 보고서/원자료/동결 계약은 수정하지 않는다. 현재 build-output APK 경로가 새 APK로 바뀐 사실과 archive mapping은 legacy_preservation.json에 기록한다.

최종 smoke/판정/commit은 외부 FINAL_REPORT 및 Git 종료 기록을 따른다. 이 단계가 통과해도 SERVICE-MODEL-V2/SIM-01_READY를 뜻하지 않는다. 다음은 별도 승인된 bounded instrumentation calibration 계획을 새 UUID/seed/workload/quality/memory/thermal 계약으로 동결하는 일이다. 새 holdout·본 simulation/formal은 이번 범위 밖이다.

### 현재 종료 상태

**BLOCKED_DEVICE_CONNECTION**. 구현 checkpoint `60bd398`. 2026-09-20T15:50:26Z ADB devices 목록과15:50:59Z mDNS 서비스 목록이 모두 비었다. 확인되지 않은IP로접속하거나 다른기기에실행하지 않았다. 설치/Activity/실제smoke0회이므로 실제v4경계·memory API/admission·두runtime residency가통과했다고 주장하지 않는다. CPU/GPU lifecycle·residentCPUserial/co-run의4개 미실행계획은 `smoke_plan_v2/plan.json`에보존했다. 처음 host계획UTC표기실패는 `host_attempt1/failure.json`에남겼고 기기실패session은없다.

재개 명령(승인A24 한대연결 후): `python C:\Users\LG\Documents\D1Check_Telemetry_V4\run_20260920T144315Z\smoke_device.py`. 실행기는host gate/source/APK/manifest/input hash, SM-A245N/hardware serial/fingerprint/thermal0를 재검사한다. 네smoke만수행하며 기한·성공률 정책비교를 하지 않는다. 아직 Activity를시작하지않은UUID만 사용한다. 측정실패가발생하면 이전성공/실패출력을보존하고 실패UUID로재실행하지말아야한다.
