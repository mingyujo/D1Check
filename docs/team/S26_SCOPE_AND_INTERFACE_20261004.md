# S26 범위 결정·평가 정의·입력 인계 — 2026-10-04

상태: **범위 변경 채택, S26 정책 효과·v2 확인은 미완료**. 결정 ID `S26-THERMAL-SCOPE-02`. 이번 작업은 PC 자료 확인·공유이며 기기 실행 승인이 아니다.

## 1. 담당자에게 보내는 결론

- 10/11 측정 동결·10/12 집필을 기준으로 **S26의 두 모델 XDEV-02 축소 재현을 필수 제출 범위에서 보류**한다. 미완료를 PASS나 실패로 바꾸지 않는다. 별도 절에서 검증된 분류 모델의 CPU/GPU/NPU, 열 이력과 처리율, 유예·부하 상한·자원 선택을 다룬다. 탐지·동시 병행까지 A24 수준으로 이식하는 작업은 이번 필수가 아니다.
- 연구 목표는 **응답·완료 요구를 지키면서 기기 전체 에너지와 열 부담을 줄일 수 있는 조건을 밝히는 것**이다. 서비스 조건은 가드, 에너지·열은 따로 보고하는 목적 지표다. 임의 가중합이나 항상 이득이라는 전제를 넣지 않는다. S26은 J 적격성이 확보되기 전까지 열/처리율 질문으로 제한한다.
- 하나의 연구 문제·평가 정의에 **기기별 프로필과 각자 검증한 실행기**를 연결한다. 지금 구현은 두 코드베이스다. “하나로 통합된 시뮬레이터 구현 완료”라고 쓰지 않는다. A24 CPU/GPU에 S26 NPU·열·전력 계수를 끼워 넣지 않는다. 코드 통합은 후속 후보이지 12/03 완료 보장이 아니다.
- **RL은 이번 제출 필수 범위에서 제외**한다. 강한 고정 배정·열 인지 규칙·대조군·명시적인 정보 우위가 있는 oracle로 질문에 답한다. 단순 규칙 실패만으로 RL 필요성이 입증되지는 않는다.
- S26 `CompiledModel / LiteRT 2.2.0 / GPU OpenCL / override 없음` 근거를 해당 모델·빌드·정밀도에 귀속한다. `Interpreter 1.4.2 GPU`는 현재 S26 지원 경로에서 제외한다. 9/15 override 80런은 보조 이력으로 분리한다. CompiledModel 통과가 Interpreter 지원을 입증하지 않는다.
- A24 APK의 PC 빌드·A24 실행 근거는 있지만 **S26 arrival 실행 통과 근거는 없다**. 기존 host `tools/d1_arrival_device.py::identify`는 A24 모델·fingerprint를 요구한다. 기존 APK/실행기를 그대로 S26에서 실행하라고 전달하지 않는다.

근거: [9/24 결정](../DECISIONS.md#s26-npu-20260924), [새 결정](../DECISIONS.md#s26-thermal-scope-02), [기존 프로토콜](../MULTITASK_EXPERIMENT_PROTOCOL.md), [A24 현재 결과](../ENERGY_THERMAL_OVERNIGHT_RESULTS_20261004.md).

## 2. 확인된 근거와 팀원 보고의 경계

읽은 S26 원격 버전은 `b4f7634a64e068c66cfaff4d5af4ab4548af4529`다. 원격 브랜치를 읽기 전용 fetch했으며 merge/checkout하지 않았다.

| 항목 | 현재 인계 판정 |
|---|---|
| [10/4 회신](https://github.com/mingyujo/D1Check/blob/b4f7634a64e068c66cfaff4d5af4ab4548af4529/s26/docs/HANDOFF_REPLY_20261004.md) | GPU/NPU 회복, GPU 페이싱, EffNet CPU/GPU 개발8런 등 문서·집계 확인. 전체 원시 추론을 재분석한 것은 아님 |
| [v1 holdout](https://github.com/mingyujo/D1Check/blob/b4f7634a64e068c66cfaff4d5af4ab4548af4529/s26/results/night_1003/MODEL_HOLDOUT_1003.md) | 가열 일부와 회복/재조임의 판독을 구분. v1 전체 통과로 표현하지 않음 |
| [EffNet 개발 블록](https://github.com/mingyujo/D1Check/blob/b4f7634a64e068c66cfaff4d5af4ab4548af4529/s26/results/night_1003/EFFNET_BLOCK1_RESULTS_1003.md) | 합성 입력·개발 자료. 실제 이미지 품질과 정책 독립 확인은 별도 |
| EffNet NPU 600초 | 안전 중단·최종 자료 없음이라는 회신을 보존. 완료 곡선으로 사용 금지 |
| 10/4 부하 의존·완전 유휴300초·NPU420초·v2 P1c/holdout | 사용자 전달 보고/예정. 이 버전에서 해당 완료 receipt를 확인하지 않았으므로 완료로 승격하지 않음 |
| 정책 V3 10/6–9 | 일정 제안. 도착·요청 경계·독립 확인의 실제 구현/완료 증거가 필요 |
| S26 에너지 | C2 일관성 FAIL, `raw_unverified` 유지. 동일 폰 상대 비교도 단위·경계·오차를 확인해야 함 |

S26의 빈칸은 A24급 재현과 비교할 때의 범위 차이다. 그 모든 칸을 채워야 S26 분류·순차 연구가 성립하는 것은 아니다. `3자원`은 선택 가능한 backend이며 **3건 동시 실행 검증**을 뜻하지 않는다. CPU 고온 피해자를 정책이 사용하지 않는다면 범위 밖으로 둘 수 있지만, 미측정을 보편적 NPU 우세로 정당화하지 않는다.

코드8–11일+측정6–8밤, 10/18–20 종료는 팀원의 추정이다. 통합·디버깅·독립 확인 의존성이 있어 납기 보장으로 쓰지 않는다. “50 charge-counter 계단≈10분”도 관측 전류에 달린 가정이다. 긴 창은 양자화 상대 영향을 줄일 수 있으나 기존 C2 오차 원인을 해결하거나 J 적격성을 자동 보장하지 않는다.

## 3. 결론 문구·정책 사전 등록에서 바로잡을 점

1. A24는 **검증한 조건에서 열→처리시간 연결이 미식별**이다. “스로틀이 없는 기기”로 일반화하지 않는다. AP와 J를 관측하고 예측한 근거는 있다. CPU/PAR 긴급 P95 약128–131ms 단축과 작은 J/AP 정책 차이의 **우열 미판정**을 구분한다. 차이가 실제로 작다는 동등성 검정을 한 것이 아니다.
2. S26의 NPU 속도·온도 순위는 같은 모델·품질·정밀도·입력·시간 경계·부하/완료량에서만 비교한다. `run-only`와 `write+run+read` 및 A24의 응답 시간을 섞지 않는다. 최대 duty에서 온도가 낮다는 것과 같은 요청 서비스를 더 적은 열/에너지로 완료한다는 것은 다른 질문이다.
3. OS thermal status=0과 처리율 감소가 함께 관측될 수 있다. 이는 OS 열 관리가 없다는 증거도, 특정 내부 스로틀 메커니즘의 단독 인과 증거도 아니다. `NpuManagerApprox`는 연구용 근사 정책 ID다. 실제 Android OS/NPU 관리 정책을 재현·능가했다고 주장하려면 별도 근거가 필요하다.
4. 같은 예정 도착·요청 수·기한·완료창으로 유예/부하 상한을 비교한다. 부하를 버리거나 공통창 밖으로 밀어 온도를 낮춘 결과를 절감으로 계산하지 않는다. 실패·만료·미완료 분모 및 tail 에너지/시간을 사전 고정한다. 평균부하만으로 버스트 지연 가드의 실현 가능성을 보장할 수 없다.
5. `m=max(5%, 2·CV)`는 제안된 screening 기준이지 측정 오차 한도·유의성·정책 우월성 기준이 아니다. CV의 단위·집계 대상·독립 런 수·기준선을 명시해야 한다. 절대 섭씨 온도에 퍼센트/CV를 적용하지 않는다. 온도는 Δ°C, 초과 시간은 초, 처리량은 요청/s로 별도 판독한다. 근거 없는 새 합격 숫자는 여기서 만들지 않는다.
6. 최소화 지표의 회수율 `(baseline-rule)/(baseline-oracle)`은 모든 항이 같은 단위/서비스 조건이고 분모가 양수이며 구분 가능한 경우에만 기술한다. “상한”이 성능 상한인지 비용 하한인지 명시한다. 실현 미래를 아는 oracle은 온라인 구현 가능한 정책과 구분한다. 분모가 0/불확실하면 비율은 null, 원래 차이만 제시한다.
7. P1d/폰 정책 결과를 보기 전에 모델·입력·부하 구간·기한·정책·KPI·중단/결측·허용 기준과 결과별 결론을 동결한다. 이미 본 모형 개발 자료와 독립 정책 확인을 구분한다. 결과를 본 v2 재적합 후 같은 holdout을 새로운 독립 확인이라고 부르지 않는다.

결과별 결론은 다음 범위에 한정한다.

- 서비스 가드 유지·모형 확인·폰 효과 방향이 일치하면 **등록된 S26 조건에서 해당 규칙의 효과**를 보고한다. A24 미검증을 대신 PASS 처리하지 않는다.
- 여지는 있지만 규칙 효과가 불확실하면 사용한 규칙/조건의 한계다. RL 필요성은 아직 미판정이다.
- 여지가 관측되지 않으면 **시험한 부하·자원·환경에서 추가 제어 이득을 확인하지 못했다**고 쓴다. “열 관리가 필요 없다”거나 두 기기 전체에 효과가 없다고 확대하지 않는다.
- 폰에서 뒤집히거나 holdout이 실패하면 모형/정책 전이 실패를 그대로 보고한다. 서로 다른 기기 latency·온도·J를 합쳐 평균 효과를 만들지 않는다.

프로젝트 결론의 질을 S26의 성공 여부 하나에 걸지 않는다. 공통 기여는 **지원된 기기별 근거로 어떤 제어를 비교할 수 있고, 서비스 요구와 오차 아래 어떤 효과를 구분했는지**다. 현재 A24의 CPU/PAR 결과는 제안 P가 강한 B2/B3보다 우수하다는 결과가 아니다.

## 4. 대표 입력·참조 출력: 바로 사용할 파일

[20이미지 목록·CPU reference JSON](s26_interface_20261004/quality_reference.json)은 기존 파일을 재추론 없이 추출했다. 이미지별 원 URL·출처/라이선스·JPEG/PNG/RGB/텐서 SHA, host CPU top5 및 **1000개 전체 float32 출력**을 담았다. 최신 A24 도착 부하는 이 중 `00575b9132bb3746` 한 이미지를 반복했다. 20이미지 전체를 도착 실측했다는 뜻이 아니다.

- 모델: EfficientNet-Lite0 float32, SHA `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0`. [기존 모델 원 URL](https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite). 모델은 Git에 포함하지 않는다.
- 라벨: 모델 내 `labels_without_background.txt`, 1000개/0기반, SHA `e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f`. ImageNet 정답 annotation이 아니라 출력 index 명칭이다. Open Images의 Bicycle 등 선택 클래스/탐지 box를 ImageNet 분류 정답으로 전용하지 않는다.
- 전처리: canonical-sRGB PNG, 224×224 stretch, Q16 half-pixel bilinear/round-half-up, RGB/NHWC/float32 `(RGB-127)/128`, crop/padding 없음. [실제 구현](../../tools/d1_classification_reference.py), [공유 resize](../../tools/d1_detection_contract.py). 이미지 재생성이 같은 byte/hash를 내지 않으면 임의로 새 hash를 받아들이지 않는다.
- 참조는 9/20 PC `ai-edge-litert 2.2.0` Interpreter CPU 1thread, deterministic3회 기록이다. S26 CompiledModel CPU 출력도 먼저 이 참조와 대조해야 한다. 참조가 분류 정확도 정답 또는 CompiledModel 검증 완료라는 뜻은 아니다.
- 기존 raw 동등성: 모든 값 finite, `abs(candidate-reference) <= 1e-4 + 1e-3*abs(reference)` 위반0. [비교 코드](../../tools/d1_probe_compare.py). 상대오차 표시 분모 epsilon=1e-6은 위 허용식과 별개다. 전체 float32 참조 bytes SHA는 JSON 값을 little-endian float32로 복원해 확인할 수 있다.
- 기존 arrival top5 확인은 같은 순서의 class index/label, 점수 절대차≤0.001이다([quality 코드](../../tools/d1_energy_collection.py)). raw 동등성과 서로 다른 검사다. 이 함수의 backend 동일성 검사를 그대로 CPU→NPU 비교에 호출하지 않는다. 모델/텐서 동일성, backend별 실제 위임 증거와 출력 동등성을 별도로 확인한다.
- NPU 양자화/AOT 변환으로 위 기준이 실패하면 실패를 보존한다. 그 결과를 본 뒤 tolerance를 늘리지 않는다. 다른 정밀도 품질 계약은 별도로 사전 고정해야 한다. 실세계 정확도 주장이 필요하면 별도 정답 corpus가 필요하며 현재 인계가 이를 대신하지 않는다.

외부 원본은 `C:/Users/LG/Documents/D1Check_Decode_Resolution/validation_inputs/canonical_png_v2_final/` 및 `resume_20260920T090545Z/host_classification_v3/<sample_id>/{golden.json,input.f32le,output_0.f32le}`다. PNG/텐서는 Git에 넣지 않았다. 이미지 URL·변환 환경으로 동일 bytes를 재현할 수 없으면 **이 20개 PNG 또는 대응 input.f32le만 별도 전달**하면 된다. 새 이미지 선택이나 S26 원본57MB×전체 요청은 우선 필요하지 않다.

휴대폰/추론 없이 인계 파일 검증:

```powershell
python -B -m tools.d1_s26_quality_handoff --bundle docs/team/s26_interface_20261004/quality_reference.json
```

외부 원본에서 다른 빈 경로로 재추출하려면 위 명령에 `--source-root '<D1Check_Decode_Resolution 경로>'`를 추가하고 `--bundle`에 새 파일을 지정한다. 기존 파일 덮어쓰기를 차단한다. 이 스크립트는 이미지·모델 추론이나 네트워크 접근을 하지 않는다.

## 5. §4와 실제 요청 경계 대응

근거: [MULTITASK §4](../MULTITASK_EXPERIMENT_PROTOCOL.md), [실제 Activity](../../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalEnergyActivity.kt), [현재 집계](../../tools/d1_online_policy_model.py). 모두 같은 Android `elapsedRealtimeNanos` 도메인이며 host wall clock과 직접 빼지 않는다.

| 인계 7경계 | A24 raw 필드 | 의미 / §4 대응 |
|---|---|---|
| dispatch | `dispatch_ns` | lane에 제출; 아직 worker 실행 시작 아님 |
| start | `execution_start_ns` | worker 시작 / service start. 실제 adapter 호출 시작 `host_inference_start_ns`도 별도 보존 |
| return | `host_inference_return_ns` | adapter.execute 반환. Android 기록이며 PC host clock 아님. 순수 kernel 종료와 동등하지 않음 |
| output_ready | `output_ready_ns` | 결과 사용 가능; urgent 완료 C_i |
| persist | `persist_complete_ns` | 현재 arrival의 write/fsync/rename 후 normal 완료 C_i. 현재 save에는 readback 없음; §4의 readback 포함 계약과 동일하다고 하지 않음 |
| worker_release | `worker_release_ns` | worker 반환 경계; scheduler lane이 아직 점유될 수 있음 |
| lane_available | `lane_available_ns` | scheduler callback에서 release/busy=false 직전 기록, 이후 pump가 다음 dispatch 허용. 물리 kernel 종료 시각 아님 |

추가 필수: `scheduled_arrival_ns`(예정), `actual_arrival_ns`(도착 callback), `enqueue_ns`(queue 수용), request/session ID, task/model/input/config hash, priority, deadline, requested/actual backend, 실행기/엔진/정밀도, terminal_status 및 원래 실패 사유. 전처리·invoke·후처리·I/O를 분해하지 못하면 합산 경계를 표시한다. `inference_ns` duration을 request response timestamp로 쓰지 않는다. 순차 모드에도 lane 해제 경계는 남긴다.

이 대응표는 §4와 실제 현재 경로의 차이도 보존한다. S26이 readback까지 구현하면 별도 종료 필드를 남기고, A24 현재 `persist_complete_ns`와 완전히 같은 비용이라고 pooling하지 않는다. 이번 인계에서 기존 Android 코드·저장 경계·과거 지표를 수정하지 않았다.

- urgent 1.5초 / normal 6초는 공통 **연구 기한**, 실제 사용자 SLA의 검증값이 아니다. 예정 도착은 이전 요청 완료와 독립적이다.
- response=`C_i-scheduled_arrival_ns`; queue 기반 보조 response=`C_i-enqueue_ns`. 도착 지연도 별도 보고한다.
- 완료 응답 P95는 nearest-rank `sorted[ceil(.95*n)-1]`. 완료0이면 null. 동시에 전체 예정 요청 기준 기한 내 완료율/서비스 성공률을 명시한다. 실패·거절·만료·취소·미완료를 삭제하지 않는다. 성공하되 지각한 요청은 성공과 deadline miss를 둘 다 표시한다.
- A24 현행 집계 이름 `actual_urgent_p95_ms`, `actual_deadline_met`, `planned`와 단위를 export에 유지한다. `actual_deadline_met/planned`와 단순 성공률은 다른 지표다. BG도 planned/completed/on-time/failed/unfinished를 함께 낸다.
- 열: AP/SKIN/BAT/PA sensor ID·단위·측정주기·결측을 구분. Δ°C·최고값·사전 정의한 임계 초과시간을 각각 보고한다. thermal status만으로 스로틀 시간 대체 금지. 지속가능 처리율/스로틀 기준과 warmup 제외 규칙을 사전 등록한다.

## 6. S26 최소 export와 전달 일정안

10/5 PC export 약속은 [담당자 회신](https://github.com/mingyujo/D1Check/blob/b4f7634a64e068c66cfaff4d5af4ab4548af4529/s26/docs/HANDOFF_REPLY_20261004.md)에 따른다. 부족한 형식은 지금 다음으로 고정해 전달한다.

1. 런 manifest/receipt/validation: 익명 device ID, 모델·입력·APK·소스·엔진·precision hash, CPU threads 또는 unknown, delegate/full/fallback 귀속, 개발/확인/실패, 시작/끝 monotonic 및 wall anchor, 계획 대비 완료량. segment0만으로 이후 segment의 delegate를 인증하지 않는다.
2. 센서 표: 원 monotonic timestamp·AP/BAT/PA/SKIN/status·전류 raw와 단위 해석·전압·charge counter·plug 상태·sample age. 1초 요약과 원표본 간격/공백·요약 규칙, 보간하지 않은 결측. C2 계산/판정 코드·단위·적분창 포함. 1Hz 온도만으로 J 재현 가능하다고 하지 않는다.
3. 구간/요청 표: 예정/실제 segment 경계·duty·추론 수·latency 정의/P50/P95·전환 분해·실패. V3는 위 요청 ledger와 trace/seed/policy/config hash, 전체 분모 추가. 아직 없으면 missing으로 둔다.
4. 모델/정책: v2 동결시각·hash·개발/holdout ID·오차·실패, 결과 전 정책 등록·고정 기준선·oracle 정보 범위. Git 밖 raw inventory의 파일명/bytes/hash. 세부 불일치 재현에 필요한 런만 원본 요청한다.

**인계 일정 제안(팀 합의 전):** 10/11 측정 동결 시 성공/실패/미완료 inventory와 모델·정책 hash, 10/12 S26 절 초안·표·그림·한계, 10/13 통합 문구 대조. 10/22 제출을 위한 새 측정 자동 연장이 아니다.

**분량 제안:** 본문2쪽 + 부록1쪽, 발표2장. 그림① 같은 모델/경계의 자원 성능·열 이력/회복, 그림② 등록 부하에서 서비스 가드와 규칙/강한 기준선/대조군 비교, 표① 모형 holdout 오차·실기기 정책 확인·미검증 범위. 정책 확인이 없으면 그림②를 결과처럼 만들지 않고 완료된 관측과 한계로 대체한다. J는 적격성 미확보 시 우열 그림에서 제외한다.

**다음 행동 하나:** S26 담당자가 이 인계 기준으로 P1d/V3의 결과 전 등록 파일(부하·가드·KPI·모형/정책 hash·미완료 처리)을 고정해 공유한다. 본 문서는 새 기기 실행 승인이나 정책 효과 통과 판정이 아니다.
