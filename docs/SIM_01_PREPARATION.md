# SIM-01 준비 계약과 중단 지점

- 2026-09-20 / **SIM-01_INCOMPLETE**. 실제 scheduling simulation·formal workload 미실행.
- 이 문서는 PLAN 4.4의 준비 구현과 남은 실측 gate를 구분한다. 새 deadline은 `calibration_pending`이다.

## 구현한 독립 준비 작업

`tools/schemas/sim-input-preparation-v1.schema.json`과 `tools/d1_sim_prepare.py`는 **draft 준비 입력**만 처리한다. 완성된 service distribution을 받는 simulator나 TASK-02 production ledger가 아니다. 후속 frozen service/profile schema와 semantic import validator는 실제 adapter·측정 경계가 고정된 뒤 작성해야 한다. draft를 READY로 승격하는 실행 옵션은 없다.

| 영역 | 계약 |
| --- | --- |
| identity | protocol `sim-input-preparation-v1`, schema 1, PLAN `4.4`, 명시적 device ID |
| tasks | 2개 이상 task ID, model ID/hash, preprocessing ID, adapter pending/verified; task와 priority 독립 |
| capability | 모든 task×CPU/GPU cell의 passed/failed/unsupported/unverified와 evidence hash. raw 지원과 실제 task 승인을 구분 |
| workload | W-low/W-burst/W-peer/W-sustain 등 ID, synthetic assumption, 독립 task×urgent/normal 비율; 중복·NaN·잘못된 합 거부 |
| seed | `d1-seed-sha256-v1`: canonical UTF-8 JSON `[contract, master, partition, purpose, block]`의 SHA-256 앞 8바이트 unsigned big-endian. calibration/development/evaluation namespace 분리 |
| deadline·제약 | draft에서는 pending만 허용. 미검증 deadline·병행·반복 수를 숫자로 채우면 거부 |
| 정책 | `4.4/B0`, `4.4/B1`, `4.4/B2`, `4.4/B3`, `4.4/P` 의미를 PLAN과 고정 대조. 과거 B2와 혼합 금지 |
| provenance | task adapter/quality/solo/transition/concurrency/thermal-memory/holdout/freeze의 상대경로·SHA-256·상태. 이탈·symlink·누락·hash 불일치 거부 |
| no-op | 입력 검증과 deterministic digest/seed 예시만 계산. dispatch 0, 가상 완료 0, 비교 결과 null. 파일·ADB·모델 실행 없음 |

`SchedulingPolicy`는 향후 `decide(snapshot)` 인터페이스만 정의한다. snapshot은 now/queue/in-flight/capability/profile을, decision은 허용 start 목록 또는 다음 재평가 시각과 사유를 갖는다. 현재 B0~P의 scheduling 구현·튜닝·성능 비교는 없다. 목적은 공통 품질·안전·메모리·일반 서비스 제약 아래 긴급 기한 내 서비스와 완료 P95를 함께 개선하는 것이다. 국소 선택이 전역 P95 최적이라는 주장은 하지 않는다.

`request_kpis()`는 host 계약 테스트용 함수다. 예정 도착마다 terminal을 정확히 하나 요구하며 requested/actual backend, enqueue/execution/output/persistence/terminal의 단조 시각을 검사한다. urgent는 output-ready, normal은 persist-complete를 완료 시각으로 쓴다. 실패/거절/만료/취소/unfinished를 별도로 세고 late 성공을 실패로 바꾸지 않는다. 완료 nearest-rank P95와 전체 도착 분모의 service success/on-time rate를 함께 반환한다. deadline이 없으면 on-time rate는 null이다. 이것은 실제 파일 fsync/readback·UI·Android arrival generator가 구현됐다는 증거가 아니다.

```powershell
python -B -m unittest tools.test_d1_sim_prepare -v
python -B -m tools.d1_sim_prepare no-op --input C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/sim_input_draft.json --evidence-root C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920
```

외부 draft의 0.25씩 네 조합과 master seed 0은 schema/no-op 확인용 예시다. 실제 arrival trace·평가 seed·반복 수·부하를 동결한 것이 아니다. 이 명령의 exit 0은 draft 유효성이고 결과 status는 INCOMPLETE다.

## MODEL-02B 관측과 TASK-02 중단 이유

두 모델의 raw CPU/GPU는 seed 0/1/2, 같은 입력 hash, 고정 tolerance와 full-delegation/no-fallback 검사를 통과했다. 그러나 탐지 Tasks GPU의 **decoded 결과는 Android CPU와 label 순서·box·score가 불일치**한다. host 새 golden과 Android CPU도 한 score 차이가 `0.0017070865`로 기존 `0.001` 기준을 넘었다. raw tensor PASS를 decoded task PASS로 대신할 수 없다.

Tasks wrapper는 raw `GpuDelegateProfile`의 세부 옵션과 CPU thread 설정을 그대로 노출하지 않는다. manifest의 raw GPU configuration hash가 Tasks 내부에 적용됐다고 해석하면 안 된다. Tasks GPU 로그의 delegate 이름은 `unknown`이므로 raw cell의 verified GPU 증거를 전용하지 않는다. 버전·decode·delegate 정밀도 차이는 원인 후보이며 아직 확정하지 않았다.

현재 안전한 연구 선택지는 (1) 같은 입력·정밀도 계약을 집행하는 decoded adapter를 검증하거나, (2) 검증된 탐지 CPU와 분류 GPU의 축소 배정을 검토하는 것이다. 후자는 탐지 CPU의 golden/품질 gate가 먼저 필요하고 현재 승인된 REDUCED_PASS가 아니다. 임계값 완화, 모델 교체, CPU fallback은 채택하지 않았다. 이 연구 판단 전 실제 두 adapter의 요청 완료·UI/영구 저장 구현을 승인된 것으로 연결하지 않는다.

## PROFILE-02의 실행 가능한 선행 준비 절차

다음 순서는 gate 해소 후 구현할 bounded profiling 절차다. 현재 존재하지 않는 profile CLI가 동작한다고 주장하지 않는다.

1. **입력 고정:** 각 task의 유효한 ground truth·license/provenance와 image split, 모델/labels/APK/preprocessing/adapter hash를 고정한다. 최소 20개 이미지 준비 목표는 품질 일반화를 보장하지 않는다. 현재 한 sample은 engineering golden일 뿐이다.
2. **한 요청 완료 경계:** 독립 arrival/enqueue부터 실제 read→decode→preprocess→prepare→inference/API→postprocess→urgent output 또는 normal write/flush/fsync/rename/readback→terminal까지 같은 monotonic clock으로 검증한다. 모든 실패를 원시 ledger에 남긴다.
3. **solo:** 승인된 task×backend×priority만 수행한다. cold와 warm을 분리하고 raw 3+1+10 probe 시간은 재사용하지 않는다. 기존 프로토콜의 독립 3~5 session 출발안과 최대 추가/안정성 규칙을 service 관측 전에 확정한다. 첫 구현부터 120초 이하의 bounded pilot chunk를 사용하고 긴 formal은 금지한다.
4. **전환:** 동일 메모리·worker 예산에서 CPU→GPU/GPU→CPU warm/cold를 별도로 기록한다. 준비·전환 비용과 full service를 중복 합산하지 않는다. 실패/미지원 방향은 명시적으로 제외한다.
5. **간섭:** 두 task의 합법적 CPU+GPU 조합만 solo 대응·동시 시작·고정 offset으로 측정한다. 품질·메모리·열 gate 전에는 병행 0개, 전체 in-flight 1을 유지한다. 측정 없는 간섭을 0으로 채우지 않는다.
6. **환경·memory:** 시작/종료와 시계열의 배터리/charging/screen/thermal을 연결한다. 이번 약 2초 간격 per-process PSS 최댓값은 sampled peak이고 연속 true peak·장치 전체 memory·에너지가 아니다. 안전 온도·cooling/stability policy는 PROFILE-02 전에 근거와 함께 동결해야 한다.
7. **동결:** service stability, 적법한 capability, 전환/간섭·실패, 독립 holdout과 사전 오차 기준을 확인한 뒤 device profile과 별도 frozen schema/validator를 만든다. `D(task,priority)`는 사용 근거 또는 명시적 engineering 목표와 실제 service에서 정한다. legacy N95/U95 공식을 새 두 작업에 자동 적용하지 않는다.

현재 adapter·quality·full service·전환·간섭·thermal safety 값·holdout·deadline·반복이 없다. 따라서 SIM-01_READY를 선언하거나 실제 scheduling simulation을 시작할 수 없다. 최소 다음 행동은 기존 tolerance를 유지한 탐지 decoded 입력/런타임 동등성 원인 규명과 유효한 품질 입력 확보다.
