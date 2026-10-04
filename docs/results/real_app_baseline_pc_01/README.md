# 실제 앱 비교 대상 선정 — REAL-APP-BASELINE-PC-01

2026-10-04. **Ente Photos의 Android 전경 실행 중 배경 ML 시작 제어를 실제 앱 비교 대상으로 선정했다. 원앱 재현·성능 비교는 아직 완료되지 않았다.** 기존 [9/27 검토](../../ARRIVAL_BASELINE_REVIEW_20260927.md)를 재사용하고 직접 비교를 막는 경계만 확인했다. 수상 가능성이나 우리 정책의 우월성을 보장하는 선정이 아니다.

| 대상 | 근거와 선택 |
|---|---|
| Ente Photos | 공개 실제 앱의 제어 경로를 추적 가능. 이번 실제 앱 후보로 선정. CPU/GPU 배정기와는 제어 목적이 다름 |
| Band | 다중 DNN 연구 스케줄러. 강한 연구 비교 후보지만 상용 앱 기본 정책으로 부르지 않음. 현재 B3는 Band의 재현이 아님 |

## 고정한 원본 동작

소스 commit `a492f9db8e67def81d5f17c687f69b5778ec0df3`(2026-09-24 UTC)를 사용했다. 최신 배포 바이너리와의 일치는 확인하지 않았다. 원문 4파일 SHA는 [readiness.json](readiness.json)에 있다. 원문은 Git 밖 `C:/Users/LG/Documents/D1Check_Arrival_Extension/production_baseline_pc_20261004/`에 보존했다.

- [ComputeController](https://github.com/ente-io/ente/blob/a492f9db8e67def81d5f17c687f69b5778ec0df3/mobile/apps/photos/lib/services/machine_learning/compute_controller.dart): Android 기본 사용자 조작 유예 15초. 전경 초기화에서도 타이머를 시작한다. 건강 상태·조작·compute block을 함께 확인한다. 설정 override와 force/bypass 경로는 이번 대표 비교 범위에서 제외한다.
- [MLService](https://github.com/ente-io/ente/blob/a492f9db8e67def81d5f17c687f69b5778ec0df3/mobile/apps/photos/lib/services/machine_learning/ml_service.dart): controller 이벤트→runAllML/stopActiveRun, 중복 실행 및 프로세스 lock, 동기화·이미지 indexing·clustering·cache 단계로 이어진다. D1Check의 두 모델 요청 큐와 같은 작업이 아니다.
- [MLRunControl](https://github.com/ente-io/ente/blob/a492f9db8e67def81d5f17c687f69b5778ec0df3/mobile/apps/photos/lib/services/machine_learning/ml_run_control.dart): 최초 중단 사유를 유지하고 새 단계 시작을 막는 협력적 종료. 진행 중 작업의 단계 경계와 D1 요청의 lane 해제는 동일하지 않다.
- [DeviceHealthPolicy](https://github.com/ente-io/ente/blob/a492f9db8e67def81d5f17c687f69b5778ec0df3/mobile/apps/photos/lib/services/machine_learning/device_health_policy.dart): 배터리·온도·thermal·표본 유효성을 사용한다. 그 기준을 D1Check 안전 기준으로 복사하거나 보편적 안전 인증으로 해석하지 않는다.

## PC에서 확인한 비교 오류

기존 `tools/d1_arrival_interaction.py`를 재사용했다. **Ente Dart 실행이 아니라 D1 이식 규칙의 경계 검사**다. 미래 조작이 없고 건강/자원이 허용되는 경우의 최소 시작 대기이며 실제 응답시간 측정이 아니다.

| 요청 도착(초) | 앞선 조작(초) | 최소 대기(초) | D1 일반 기한 6초와 관계 |
|---:|---|---:|---|
| 0 | 0 | 15 | 실행시간 0이어도 위반 |
| 1 | 0 | 14 | 실행시간 0이어도 위반 |
| 10 | 0 | 5 | 실제 처리시간 없이는 판정 불가 |
| 15 | 0 | 0 | 기한 충족을 뜻하지 않음 |
| 15 | 0, 14 | 14 | 타이머 재설정으로 위반 |
| 0 | 없음 | 0 | D1 초기 idle. Ente 전경 초기화와 다름 |

따라서 15초 제어를 그대로 6초 요청 기한과 비교해 이겼다고 하면 목적이 다른 기준선을 불리하게 만든다. 또한 D1의 urgent 예외, 요청 단위 drain, 초기 idle은 원앱과 다르다. 기존 이식 코드는 **실제 앱에서 착안한 메커니즘 실험**으로만 사용할 수 있다. Ente를 그대로 재현했다고 이름을 바꾸지 않는다. J/AP/실측 응답은 null이며 새 성능 순위표를 만들지 않았다.

## 실제 앱 개선 주장을 위한 최소 연결 명세

권고 경로는 **같은 Ente 작업 안의 원래 제어와 변경 제어 비교**다. D1Check 모델로 Ente 모델을 바꾸어 승패를 만들지 않는다. B2/B3는 기존 D1 연구에서 강한 대조군으로 계속 유지한다.

1. 먼저 위 commit의 원래 전경 indexing 경로를 PC에서 빌드하고, controller 승인/거절·최초 중단 사유·indexing 시작/완료를 연결한다. 모델·runtime·사진 목록/hash·캐시 및 동기화 상태·완료 출력 경계를 고정해야 한다. 원본 소스 라이선스를 유지하며 현재 D1 소스에 원문을 복사하지 않았다.
2. 원래 실행과 계측만 추가한 실행을 구분한다. 같은 사진의 같은 처리 완료/품질, 같은 화면 상호작용·환경 조건에서 비교해야 한다. 계측 비용을 0으로 가정하지 않는다.
3. 그 후에만 시작 허용/유예를 바꾸는 개입을 별도 분기로 구현할 수 있다. 기존 D1의 backend 비용 정책은 이 admission 제어에 바로 꽂을 수 없다. 이번에는 새로운 정책을 구현하거나 채택하지 않았다.
4. 원앱은 화면 반응을 보호하며 배경 작업을 수행한다. **실제 전경 반응·프레임 지연과 배경 완료량/완료시간**이 필요하다. D1의 1.5/6초 연구 기한을 원앱 SLA로 부르지 않는다. 동일 공통창 J/AP 및 미완료 분모·창 이후 잔여 작업을 함께 보고, 사전 허용 가능한 전경 악화 기준이 없으면 우월성 PASS를 부여하지 않는다.
5. 원앱 workload의 전력/열을 기존 A24 두 모델 계수로 대신 예측하지 않는다. 원앱 재현과 대응 개입 검증 전에는 실측 계획·반복 수·절감률을 확정하지 않는다.

**현재 상태:** 후보와 소스 경계는 선정 완료, 원앱 비교 실행은 준비 미완료. Flutter/Dart 원앱 callback·빌드·실기기 성능은 이번에 실행하지 않았다. 실제 앱보다 낫다는 주장은 미입증이다. 다음 행동은 하나: **고정한 Ente 전경 indexing의 원본 PC 빌드와 최소 이벤트 계측 연결**. 다시 포괄적 후보 감사를 반복하지 않는다.

## 검증과 재현

검증 대상 HEAD `90948f7ff592aacfb72fe6146af7532058b46edf` + 이번 미커밋 검사 코드/문서. 2026-10-04 KST에 원문4파일 해시 확인, 6경계 산술 검사, 기존 상호작용 gate 관련 4테스트 통과. 원문 손상 검출·기존 출력 덮어쓰기 거부도 확인했다. 실제 앱 동등성/장치 성능 검증은 아니다.

```powershell
python -B -m tools.d1_real_app_baseline_check --output "$env:TEMP/d1-real-app-readiness-new.json"
python -B -m unittest tools.test_d1_arrival_interaction.InteractionTest.test_before_exact_after_expiry tools.test_d1_arrival_interaction.InteractionTest.test_reset_and_stale_expiry_no_new_decision tools.test_d1_arrival_interaction.InteractionTest.test_decision_in_flight_cancel_retains_queue_and_spent_cost tools.test_d1_arrival_interaction.InteractionTest.test_running_request_finishes_and_lane_not_released_at_output_or_persist -v
```

새 출력 경로를 사용한다. 원문까지 확인하려면 첫 명령에 `--source-dir <위 원문4파일 디렉터리>`를 추가한다. 원문 없이도 gate 검사는 가능하지만 `source_bytes_verified=false`로 기록한다. 기기 명령·추론·실측·APK 빌드·새 실행 계획·claim 모두 0. 기존 모형/결과/strict/`experiment_ready=false`는 불변이다.
