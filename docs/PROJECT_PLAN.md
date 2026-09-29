# D1Check 프로젝트 실행계획

## 2026-09-29 — 저온 시작 AP 유휴 반응의 최소 개발·확인 후보(실행 미승인)

[PC 설계·고정 계획](ENERGY_AP_IDLE_RESPONSE_PLAN_PC_20260929.md)은 같은 B2 재생 반복 대신 기존 APK의 release gate로 충분한 부하 전 유휴를 관측하고, 한 묶음 개발→구조 동결→다른 순서 두 묶음 독립 확인을 분리한다. 기존 동결 β·기울기는 유지하고 부하 전 AP에서 유효 유휴 기준만 세션별 계산한다. 총 2세션·명시적 추론≤64·ADB≤6,600·전체≤2,120초, 재시도0의 **미승인·미소비** 후보이며 결과에 맞춘 재보정/추가 세션이 아니다. 새 자료가 적격해도 저온 CG_DC/유휴의 조건부 AP 진단만 판정하고 정책 선택·strict 지원·물리적 주변온도 식별은 완료로 승격하지 않는다. 현재 기기·설치본/환경 및 실행 승인 전에는 Run 금지. 기존 동결/사후 후보/시뮬레이터 기본/`experiment_ready=false` 유지.

## 2026-09-29 — B2 저온 시작의 PC 잔차 결과

[원본 재현·센서 해상도 분할·별도 한 후보 비교](ARRIVAL_RECORDED_B2_RESIDUAL_MODEL_PC_20260929.md)를 마쳤다. 통합 J 오차는 부하/유휴 상쇄이고 AP는 초기값 누락이 아닌 유휴 반응의 조건 전이 문제다. 저온 세션에 유리했던 시작값 기준 후보는 따뜻한 개발·확인·다른 프로토콜 진단 모두에 불리해 **기본 채택하지 않는다**. 동결 W/AP 계수·strict 마스크·정책 코드는 유지한다. 다음 연구 결정은 같은 APK/관측 계약의 저온 유휴→짧은 CG_DC→유휴 **독립 확인 한 조건**의 필요성 검토다. 이번에는 계획·claim·기기 실행이 없고 반복 수/예산도 확정하지 않는다. 아래 기존 실행·준비 항목은 당시 기록이다.

## 2026-09-29 — B2 AP 관측 진단 v2 결과와 다음 PC 판독

[별도 승인 plan_v6의 1회 완료](ARRIVAL_RECORDED_B2_AP_OBSERVE_RUN01_20260929.md)로 저장 B2 24요청과 실제 CG_DC 1.683초, 공통120초 J/AP를 확보했다. 초기 AP29.9°C와 짧은 전환은 동결 strict 밖이므로 계산은 외삽 진단이다. 실제 lane 일정 조건부 계산과 온라인 정책/도착부터의 종단간 예측을 구분하며 동결식·지원 범위·`experiment_ready=false`를 바꾸지 않는다. 다음은 기존 개발·확인 자료에 대해 AP 외삽 잔차와 J 상태구간 상쇄를 **PC에서만** 비교한다. 실측 추가·정책 튜닝·정확도 PASS는 결정하지 않았다. 아래 PC 준비 항목은 실행 전 당시 상태의 역사 기록이다.

## 2026-09-29 — B2 시작 AP 관측과 모형 범위 분리

[별도 PC 계약](ARRIVAL_RECORDED_B2_AP_OBSERVE_PC_20260929.md)에 따라 개발 시작 범위 32.5–34.0°C를 기기 안전 gate로 사용하지 않는 opt-in `numeric-ap-observe-v2`를 준비했다. 기존 배터리·비충전·BAT·thermal·화면·메모리·앱 품질·numeric AP 신선도는 유지한다. 저장 B2 24요청·실제 release/배정·120초 공통창은 그대로며 범위 밖 관측은 외삽 진단으로만 판독한다. 새 서명 APK와 미승인 단일세션 plan_v6는 PC Check까지 완료했지만 현재 기기·실측은 미검증이고 승인/claim 없음. v5는 미소비 PC 초안·현재 코드 Check 불일치로 실행 대상이 아니다. 다음 결정은 별도 1회 실행 여부이며 기존 소비 plan_v3/v4는 재개하지 않는다. strict·동결·`experiment_ready=false` 불변.

## 2026-09-29 — 새 APK B2 기록 재생의 gate 종료

[plan_v4 1회 결과](ARRIVAL_RECORDED_B2_REPLAY_RUN02_20260929.md)는 APK 설치·환경/품질 준비와 runtime4·warmup8까지 도달했으나 시작 AP 28.8°C가 동결 개발 시작 범위 32.5–34.0°C 밖이라 host가 arm을 보내지 않고 실패 정리했다. 1시도·0완료, 공식창·본 요청0, lifecycle 취소 미관측이다. 모형 오차·짧은 전환 지원·B2 우열은 계속 미판정. 두 재생 계획 모두 `stopped_no_resume`이며 재실행하지 않는다. **다음은 기존 초기 AP 관측과 고정 gate의 적용 가능성만 PC에서 판독**한다. 온도를 맞추기 위한 즉석 가열·gate 완화·새 실측 자동 실행은 계획에 없다. 동결 모형·strict 지원·`experiment_ready=false` 유지.

## 2026-09-29 — 저장 B2 재생 종료 PC 판독

[최신 lifecycle 판독](ARRIVAL_RECORDED_B2_LIFECYCLE_PC_20260929.md)에서 baseline 실패 파일보다 host의 세션 종료 force-stop이 뒤라는 것을 확인했다. Activity 종료의 최초 외부 원인은 구 APK 기록으로 특정할 수 없다. Activity가 실행 자원을 소유하고 `onDestroy`에서 미완료 세션을 취소하는 구조를 유지하며, 부족했던 instance/callback/finish 사유 journal만 추가했다. 관련 실제 callback PC 테스트 7건과 별도 프로젝트 서명 APK 빌드·신원 검증을 완료했으나 새 APK는 미설치·기기 미확인이고 추가 기록 비용도 미계측이다. 다음 실행은 새 계획·별도 승인·현재 gate가 필요하며 이번에는 준비/실행하지 않는다. 소모 plan_v3 재실행 금지, 동결 J/AP 모형·미완료 확인·strict 지원·`experiment_ready=false` 유지.

## 2026-09-29 — 저장 B2 상태 전환 조건부 확인 경로

[단일 재생 계약](ARRIVAL_RECORDED_B2_REPLAY_PC_20260929.md)의 queue/seed201/실현 간섭1.5 B2_PC 한 일정만 대상으로 `RECORDED_B2_REPLAY_V1` 입력·Android 배정 gate·동결 모델 조건부 판독을 PC 구현하고 계획을 동결했다. [승인 실행 결과](ARRIVAL_RECORDED_B2_REPLAY_RUN01_20260929.md)는 runtime4·warmup8 완료 뒤 resident baseline 중 `lifecycle_cancelled`로 1시도·0완료, 본 작업·시작 AP gate·공식120초 창 미도달이다. plan_v3은 소비·종료되어 재실행하지 않는다. 앱 실패와 host 최상위 summary 누락 오류를 구분해 PC 판독을 수정했으나 과거 종료 trigger는 미확정이다. J/AP 오차·짧은 전환 지원·정책 성능 PASS는 미판정이다. 동결 파일과 기존 queue24 미소비 계획, strict 지원 제한, `experiment_ready=false` 유지. 시간축 대조는 위 최신 항목에서 완료했다.

## 2026-09-29 — 저장된 정책 일정의 실측 지원 마스크 적용

[구체적인 최초 차단·전체 차단](ARRIVAL_MEASURED_SUPPORT_BOUNDARY_20260929.md)을 저장 135개 일정에 적용했다. **완전한 A24 실측 기반 J/AP 정책·입력 사례는 현재 0개**다. 기존 PC 일정/응답과 가정 민감도는 재사용하지만 실측 모형 지원·독립 예측 확인·정책 차이 식별은 별도 단계로 둔다. 대표 queue/seed201/실현1.5 B2/B3/CPU 비교는 계수 누락 없이도 유휴↔짧은 단독↔CG_DC/DC_DG/CC_DG 전환, 실제 초기 AP와 동일 관측창의 독립 자료가 없어 동결 모형의 우열 계산으로 승격하지 않는다. 현 Android FIXED_SPLIT 도착 계획으로 B2/B3/CPU를 직접 실행했다고 주장하지 않는다. 고정 상태·전환 비용 확인과 실제 정책 직접 비교는 분리하고, 전자는 계수 재적합 없이 조건부 A와 예정 도착부터의 B를 따로 판독한다. burst/B3의 미계측 분류 CPU＋분류 GPU 9사례는 현재 제한 비교에서 제외한다. queue24/FIXED_SPLIT 계획은 미승인·미소비 보류; 별도 승인 없는 기기 실행·새 정책/가정 추가 없음. `experiment_ready=false` 유지.

## 2026-09-29 — 정책 실험 착수 범위와 24요청 실행 보류

[통합 감사](ENERGY_AP_POLICY_MEASUREMENT_AUDIT_20260929.md)의 **권고(새 정책·실측 채택 아님)**에 따라 현재 low/queue/burst의 CPU_URGENT·고정 B2·B3 응답/완료와 출처가 명시된 전력·AP 가정의 상충을 제한 PC 실험으로 읽는다. 동결 A24 상태 계수는 긴 블록·조건부 일정에서만 사용하며 임의 도착 strict의 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`를 유지한다. 임의 도착 정책의 실측 기반 우열을 주장하려면 B2의 CG_DC와 B3의 DC_DG, 유휴/단독 전환의 **공통창 전체** 에너지·AP·일정이 선택 차이보다 충분히 구분되는지 별도 확인해야 한다. 현재 Android 지원 상태/실제 joint 길이/프로토콜 비용을 입증하지 못해 새 세션·시간 예산은 확정하지 않는다. 준비된 queue24/FIXED_SPLIT 1세션은 좁은 도착 A/B 진단에는 유용하나 핵심 병행 검증의 필수 선행이 아니므로 실행을 보류하고 미승인·미소비로 보존한다. 추가 실측·RL·정책 튜닝은 이번 작업에 없으며 `experiment_ready=false`다.

## 2026-09-29 — 시작 AP gate 단일세션 확인 입력 준비

[별도 미승인 계획](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md)의 프로젝트 서명 APK·고정 queue24/FIXED_SPLIT·시작 AP 32.5–34.0°C·공통120초·전체1,300초/ADB3,000/추론32 상한을 PC에서 고정하고 Check했다. 다음 연구 단계는 현재 기기 gate를 거친 **한 세션의 프로토콜 전이 확인**이며 실행 승인은 아직 없다. 그 결과는 A(실제 일정 조건부 비용)와 B(예정 도착 종단간 일정/응답/비용)의 적격성과 오차를 분리해 읽는다. 병행 상태/개별 요청 전력·열→처리시간·다정책 동적 최적화의 검증은 이 입력의 완료 조건이 아니다. 동결 계수·과거 자료·`experiment_ready=false` 유지.

## 2026-09-29 — CC_DG 짧은 전환 진단 완료와 동적 모형 경계

이전 PC 점유 감사에서 필요성을 확인한 opt-in 10~20초 상태 전환을 [별도 1세션](ENERGY_AP_SHORT_TRANSITION_DIAG01_20260929.md)으로 구현·검증·실행했다. 실제 6개 pair 블록에서 공동 lane 점유가 각각 12.908초 이상 지속되어 관측 가능성은 확인했다. 그러나 시작 AP32.3°C가 개발 관측 하한32.5°C 밖이므로 동결 모형의 확인 오차로 쓰지 않는다. 기존 계수·정식 확인 분모·원본을 그대로 두고 임의 도착 strict의 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`를 유지한다. 다음 작업은 새 배치를 무조건 늘리는 대신 이 결과와 센서 갱신 주기를 사용해 정책 선택에 필요한 최소 전환 시간/입력을 PC에서 동결하는 것이다. 그 전에는 실측 기반 동적 정책 최적화 완료나 에너지 절감 검증을 주장하지 않는다. `experiment_ready=false`.

## 2026-09-29 — 짧은 전환 확인 계획의 실행 가능성 선행 판정

[한 입력의 PC 점유 감사](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md)에서 queue/seed201의 기존 Android 두 배정 중 `FIXED_SPLIT`에도 병행 점유가 없고 단독 구간은 센서 갱신보다 짧음을 확인했다. 기존 12세션 계획은 현재 소스 동일성 Check에 실패한다. 다음 작업은 **별도 opt-in 단일 세션 전환 재생/적격성의 PC 구현** 한 가지다. 실제 공동 점유·AP/전류 coverage·호출/ADB/시간 상한 및 새 APK/host 경계를 코드로 검증하기 전에는 숫자 예산이나 승인된 실측 계획을 만들지 않는다. 개발 동결 모형과 사후 전이 진단은 보존하며 도착 종단간 예측·정책 개발은 보류한다.

## 2026-09-29 — 동결 상태 모형의 조건부 전이 판정

[DIAG-04 전이 오차](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md)를 기존 개발3 동결값으로 PC 산출했다. CG_DC 고정 블록의 실제 일정이 주어진 경우에만 사후 진단을 허용하고 임의 도착에서는 지원 차단한다. 새 확인 자료에 맞춘 후보 모형 생성은 보류한다. 당시 다음 단계였던 Android 도착 재생 경로의 단일 입력 계측 가능성 검토는 위에서 완료했다. 새 실측은 아직 계획·소비하지 않았다. `experiment_ready=false` 유지.

## 2026-09-29 DIAG-04 정상 완료 — 정식 확인과 분리

사용자 자율 실측 승인으로 새 lifecycle APK의 기존 CG_DC 한 세션 진단을 완료했다. [결과](ENERGY_AP_DEVICE_SEGMENT_DIAG04_RESULTS_20260929.md): 앱 정상 cleanup·host 단일 사후 정리·회수 확인, 연결 소실 미관측. 이전 종료 원인은 여전히 미확정이다. 이후 PC 작업은 기존 동결 모형의 프로토콜 전이 적용 범위/오차 확인이며 추가 실측·재보정·정책 개발을 자동 시작하지 않는다. CG_DC/CC_DG 정식 확인 미완료와 `experiment_ready=false` 유지.

## 2026-09-29 DIAG-03 이후 lifecycle 증거와 host 정리 경계

[PC 조사·수정](ENERGY_AP_DEVICE_SEGMENT_LIFECYCLE_PC_20260929.md): host의 회수 후 요약 거절로 발생한 두 번째 force-stop을 단일 cleanup 시도 기록으로 막고, 회수된 앱 원래 오류와 host 후처리 오류를 함께 남긴다. 앱은 기존 `onDestroy` 취소를 보존하면서 Activity callback·instance/finish 상태만 추가 기록한다. 무선 디버깅 스위치 OFF→ON은 사용자 관측이며 시각·주체·`onDestroy` 인과 관계는 미확정이다. 새 소스는 기존 설치 APK/계획과 동일하다고 보지 않는다. PC host 7건·Robolectric callback 2건 통과, 프로젝트 인증서로 새 APK를 빌드·검증했다. 기기 전송·설치·실행은 없었고 실제 lifecycle 원인도 미확정이다. 다음은 **별도 승인과 현재 기기 gate 아래 새 APK로 제한된 lifecycle 관찰을 할지 결정**하는 일이며 종료된 DIAG-03·미완료 CG_DC/CC_DG를 자동 실행하지 않는다. 동결 모형 재보정·정책 개발은 보류, `experiment_ready=false` 유지.

## 2026-09-28 진단1회 종료 — 연결 내성·모형 전이 미판정

[DIAG-03 실행 결과](ENERGY_AP_DEVICE_SEGMENT_DIAG03_RESULTS_20260928.md): 설치와 현재 gate·warmup/적격성은 통과했으나 앱이 `probe.arm` 전 온도 준비 중 `lifecycle_cancelled`로 실패했다. 연결 소실이 없었으므로 연결 소실 내성을 판정하지 않는다. 공식 baseline·본 부하·냉각 0, 진단 계획은 소비·종료됐고 추가 세션/사후 회수를 시작하지 않았다. 기존 동결값과 확인 범위를 승격하지 않는다. 다음 PC 작업은 앱 lifecycle 종료 증거와 요약 실패 후 중복 host cleanup 경계를 조사하는 것이며, 같은 계획 재실행·새 수집 자동 준비는 하지 않는다.

## 2026-09-28 ADB 연결 소실 뒤 세션 내부 진행 — 별도 진단 후보

[PC 구현·계측 계약](ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md)에 따라 새 진단 모드는 host 준비·품질·AP probe 승인을 유지하고, 그 뒤 한 세션의 공식 baseline·부하·냉각만 앱이 진행한다. 앱에 없는 numeric AP gate를 통과한 것으로 간주하지 않는다. 실측 기반 에너지/AP 모형의 지원 범위와 기존 개발 동결값은 유지하고, 새 APK/조회 경로 결과는 프로토콜 전이 진단으로 따로 판정한다. DIAG-03 1세션 후보는 PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED, 기기 실행0이며 별도 승인 전에는 소비하지 않는다. 다음 정식 수집·정책 개발·강화학습은 이 진단의 PC 통과만으로 착수하지 않는다.

## 2026-09-28 별도 확인2 실행 중단 — 모형 확인 확대 보류

[CONFIRM-06 결과](ENERGY_AP_CONFIRM06_RESULTS_20260928.md): 승인된 `CG_DC→CC_DG` 두 조건 계획을 한 번 실행했으나 첫 `CG_DC`의 baseline 중 ADB transport가 소실됐다. 앱은 host가 `baseline.arm`을 줄 수 없었던 뒤 60초 gate 상한에서 실패했고, 사용자 연결 복구 후 회수한 전체 journal에서 runtime4·warmup8·적격성4·**본 작업0**을 확인했다. 완료0/2, `CC_DG` 미시도, 새 예측 오차 없음. 동결 모형·기존 DC_DG 확인1을 유지하며 새 자료로 지원 범위/정확도를 승격하지 않는다. 이 계획과 단일 회수 claim은 종료됐고 재개하지 않는다. 다음은 새 수집이 아니라 ADB transport 소실 경계의 PC 진단이다. 새 정책·강화학습 보류와 `experiment_ready=false` 유지.

## 2026-09-28 동결 상태 모형의 남은 확인2 — 별도 미승인 후보

[COLLECT-05 PC 감사와 계획](ENERGY_AP_CONFIRM_FOLLOWUP_PC_20260928.md)에 따라 3초 ADB 조회 timeout의 내부 원인은 미확정이다. 0.25초 listing·2초 AP·10초 화면 등 관측 경로를 변경하면 기존 계측 부담 비교가 흐려져 이번에는 바꾸지 않았다. 개발3·확인 DC_DG1과 동결 모형을 보존하고, `CG_DC→CC_DG`만 새 ID/manifest로 평가하는 `ENERGY-AP-STATE-CONFIRM-06`을 PC 준비했다. 확인 중 fit 재호출은 금지하고 기존 동결 byte·분석 코드 해시를 검사한다. 새 block은 COLLECT-05의 재개/완주가 아니며 실행 승인·기기 gate는 별도다. 2세션 상한3,384추론·75분, 재시도0. 새 정책/강화학습 보류와 `experiment_ready=false` 유지.

## 2026-09-28 상태 모형 정식 수집의 부분 종료

성공한 host lifecycle 진단의 신원·checkpoint·실패 회수 경로를 새 `ENERGY-AP-STATE-COLLECT-05`에 연결하고 [결과](ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md)에 따라 한 번 실행했다. 기존 측정 설계와 APK를 유지하며 개발3세션을 완료·동결했고, 확인 DC_DG 1세션에서만 예측 오차를 얻었다. 다음 확인 세션의 ADB 조회 timeout으로 전체 6세션 계획은 `stopped_no_resume`; 동결 모형은 부분 진단으로 보존하며 정책 시뮬레이터 지원/정확도 범위로 자동 승격하지 않는다. 후속은 동일 계획 재실행이 아니라 timeout 명령 기록의 PC 대조다. 새 정책·강화학습 개발 보류와 에너지/AP 모델 독립 확인 우선, `experiment_ready=false`는 유지한다.

## 2026-09-28 host 종료·복구 경로 구현과 다음 최소 확인

[PC 구현/검증 계약](ENERGY_AP_HOST_LIFECYCLE_PC_20260928.md)에 따라 향후 수집의 parent/child 신원과 실행 ID, 단일 회수 owner를 연결했다. 살아 있는 child/parent나 신원 미확인에서는 복구 기기 명령을 막고, 종료 확인 후 남은 원 예산에서만 별도 1회 회수·cleanup을 허용한다. 같은 APK의 1세션 준비 관측 진단을 PC 준비했으나 **실행 승인은 아님**. 이 진단은 host 요청 종료까지 확인하며 앱의 준비 단계 정상 cleanup은 기존 APK의 별도 종료 경로가 없어 범위 밖이다. 다음은 새 진단 승인·실행 시 실제 host 수명/회수 경계를 관측하는 일 하나이며 기존 6세션 계획 재개는 아니다. 에너지·AP 모형·새 정책 개발/판정, `experiment_ready=false`는 그대로다.

## 2026-09-28 COLLECT-04 host 기록 결함 보완 — 재수집 승인 아님

[PC 종료 진단](ENERGY_AP_HOST_TERMINATION_PC_20260928.md)에서 기존 125초 제한은 이 수집 경로와 무관하고, 원래 host 종료 원인은 미확정으로 남았다. 실패 처리의 2차 예외가 정상 종료 receipt를 막는 재현 결함을 수정하고 향후 실행의 단계별 checkpoint·Python exit/표준출력·오류 보존을 추가했다. 이는 미래 별도 계획의 증거성을 높이는 host 수정이며 기존 `COLLECT-04`의 실행 의미·결과를 변경하거나 새 APK/실측 계획을 승인하지 않는다. 다음은 PC/실행 도구 수명 경계를 판단하고, 새 실측은 별도 목적·예산 없이는 시작하지 않는다. 상태별 에너지·AP 계수 미식별, 새 정책 보류, `experiment_ready=false` 유지.

## 2026-09-28 상태 모형 수집의 부분 중단과 후속 경계

설치 검증 APK를 재사용한 별도 `ENERGY-AP-STATE-COLLECT-04`는 [실제 결과](ENERGY_AP_STATE_COLLECT04_RESULTS_20260928.md)에 따라 첫 개발 `CC_DG` 세션의 공식 baseline·부하 이전 온도 준비에서 중단됐다. 계획은 PC 검증·동결됐고 현재 A24/설치본/환경 gate는 통과했지만 host 정상 종료 receipt가 없다. 완료0/6, 계수 동결·확인·오차 평가0으로서 상태 전력/AP 모형 지원 범위는 확대되지 않았다. 기존 계획·원본과 별도로 `stopped_no_resume`를 유지한다. 다음은 재수집이 아니라 host 종료·증거 회수 경계를 PC에서 진단한다. 새 정책·강화학습 보류, 원래 에너지·AP/응답 목표 및 `experiment_ready=false` 유지.

## 2026-09-27 에너지·AP 상태 모형과 별도 예측 확인 우선

사용자 지시에 따라 새 정책·강화학습 개발은 보류하고 **실측→모형 식별→다른 세션/전환으로 예측 오차 확인→지원된 조건만 정책 시뮬레이션** 순서를 우선한다. 소비 J와 배터리 잔량/사용시간을 구분한다. [ENERGY-AP-MODEL-BRIDGE-PC-02](ENERGY_AP_MODEL_BRIDGE_PC_20260927.md)는 기존 고정870건 A24 개발/확인 원본으로 CC_DG 네 점유 상태의 전체 평균전력을 조건부 추출했으나 확인 공통창의 정책 간 에너지 방향을 재현하지 못했다. AP는 경험 phase template만 있고 상태 전환 동역학은 미식별이다. 따라서 임의 도착의 B2 역방향·B3 joint·짧은 요청에 이 계수를 전용하지 않는다. 별도 수집은 상태 식별과 다른 전환 확인에 필요한 최소 후보로만 남기며 기존 12세션 정책 비교 계획을 자동 승계하지 않는다. 원래 응답·완료/에너지·발열 목표 및 S26/NPU 별도 범위는 유지하고 `experiment_ready=false`다.

## 2026-09-27 비교 기준선 출처 검토 — 목표·평가 구성 변경 없음

[기준선 검토](ARRIVAL_BASELINE_REVIEW_20260927.md)는 정책 도입 전 D1Check 앱 본체에 두 AI 과업의 혼합 요청 scheduler가 없었고, 구 benchmark는 반복 추론 계측기였음을 Git 이력·호출 경로에서 확인했다. CPU_FIFO/CPU_URGENT를 실사용 기본 정책이 아닌 자체 단순 기준으로 표시한다. 현 합성 연구는 동일 엔진의 CPU 순서 기준과 개발 고정 B2·축소 B3 등 강한 연구 기준을 유지하는 경로 C를 **권고**한다. Ente 공개 앱·MediaPipe 공식 task·Band 연구 프레임워크를 직접 실행·포팅한 비교로 부르지 않는다. 이 권고는 사용자 채택 전의 비교 설명이며 원래 발열·배터리·응답 목표, 기존 정책/실측 결과, `experiment_ready=false`를 바꾸지 않는다.

## 2026-09-27 작은 offline 개선의 온라인 정보 경계

[ARRIVAL-INFORMATION-CHECK-PC-01](ARRIVAL_INFORMATION_CHECK_PC_20260927.md)에서 기존 offline 발견 일정의 첫 CPU 배정만 V1의 GPU 첫 배정과 교체하고, 이후는 같은 기존 온라인 규칙으로 실행했다. 같은 관측 과거의 후속 도착·실현시간 분기에서 응답·에너지·AP 상충이 달라져 사전 비악화 조건을 만족하는 하나의 온라인 규칙을 도출하지 못했다. 새 정책/별도 확인 24요청은 수행하지 않는다. 기존 500ms는 작은 offline 진단의 연구용 손실폭이며 전체 시나리오 서비스 기준이 아니다. 원래 발열·배터리·응답 목표와 기존 정책·실측 계약은 유지하며, offline 결과는 정보 상한에 관한 탐색 참고로만 사용한다.

## 2026-09-27 작은 사례 offline 일정 기준: 완료한 PC 진단 범위

[ARRIVAL-OFFLINE-SCHEDULE-PC-01](ARRIVAL_OFFLINE_SCHEDULE_PC_20260927.md)은 기존 온라인 정책을 튜닝하지 않고 low/queue/burst의 시간순 2/3요청에서 CPU/GPU 배정과 유한 대기를 제한 열거했다. 동일 축소 trace로 CPU_URGENT·개발 고정 B2·B3·`THERMAL_ENERGY_PC_V1`을 다시 실행하고 기존 엔진의 실제 완료·공통창 에너지/AP 회계로 발견 일정을 검증했다. 세 사례의 지정 이산 공간은 완전 열거됐지만 응답 손실0에서 열·에너지 후보 대비 개선이 없고, 연구용 250/500ms 허용 시에만 일부 상충 개선이 있었다. 이 결과는 미래 정보·미측정 전력/AP 가정에 의존하며 온라인 구현 가능성, 전체24요청, 실기기 절감/열 안전으로 일반화하지 않는다. 다음에는 발견한 첫 선택이 현재 관측 정보로 구별 가능한지 **한 번의 trace 판정**을 수행한다. 별도 실측·정책 튜닝은 승인되지 않았고 `experiment_ready=false`다.

## 2026-09-27 온라인 에너지·AP 후보의 PC 탐색 범위

[ARRIVAL-THERMAL-FEEDBACK-PC-01](ARRIVAL_THERMAL_FEEDBACK_PC_20260927.md)은 기존 B2/B3/CPU_URGENT와 별도로 열·에너지 가정을 **실제 배정 판단**에 넣는 PC 후보를 구현·비교했다. 기존 P, Android 정책, CAL-03 동결값, 실기기 평가 계약은 변경하지 않는다. low/queue/burst 연구용 요청 기한 1.5/6초와 공통120초에서 응답·완료·기기 전체 에너지·AP 최고/한도 초과 시간을 함께 본다. 4개 사전 가정×기존 seed 2×새 PC seed 2의 결과는 모두 탐색이며 실제 절감/열 제약 검증이 아니다. 에너지 유리 profile에서도 응답/일반 서비스 손실이 남아 최종 우월성은 미입증이다. 다음은 새 실측을 자동 확대하지 않고, 대시보드의 상충과 미측정 joint 전력·AP·판단 비용이 실제 선택을 바꿀지 판단한다. `experiment_ready=false`를 유지한다.

## 2026-09-26 합성 도착 Android 관측 후보 — 실행 미승인

[새 별도 계약](ARRIVAL_ENERGY_ANDROID_PREP_20260926.md)은 기존 합성 연구 선택을 바꾸지 않고, `CPU_URGENT`와 `FIXED_SPLIT`의 low/queue/burst 각24요청을 Android에서 직접 재생하는 경로를 PC 준비했다. 동일 정책의 120초 공통창 기기 에너지·AP와 긴급/일반 응답·미완료 분모를 함께 관측하는 목적 A가 첫 단계다. 기존 강한 B2·B3/P 최종 비교나 임의 도착 상태별 전력·열 보정 B는 이번 2-arm/짧은 표본으로 대체하지 않는다. 개발6→규칙 동결→확인6 후보, runtime48/warmup96/요청288/총추론384, hard 177분은 **아직 미승인·미실행**이다. 기기/서명/환경·센서 coverage는 실행 직전 gate이며, 새 결과가 없으므로 `experiment_ready=false`와 과거 판정은 그대로다. 상세 재현은 [PC 검증](results/arrival_energy_android_prep_01/README.md)을 따른다. 아래는 이전 상태/계획이다.

## 2026-09-26 채택한 합성 연구 경로와 PC 경계

사용자는 **실측으로 보정한 모형과 출처를 밝힌 합성 조건**의 연구를 선택했다. [최소 시나리오·회계·지원 표](ARRIVAL_ENERGY_SYNTHETIC_RESEARCH_20260926.md)는 기존 low/queue/burst 24요청 trace와 연구용 1.5/6초 기한을 재사용한다. 실사용 SLA·배터리 절감은 주장하지 않고, 원래 긴급 응답/일반 완료와 기기 에너지/AP 목표를 유지한다. 새 PC 경로는 공통120초의 분모/응답 경계를 집계하지만 임의 도착의 기기 전력·AP 계수는 없으므로 실측 기반 에너지/열 정책 비교를 차단한다. 다음은 Android active 재생과 상태별 계측의 **PC 계약·샘플링/벽시계 타당성**을 확인해 최소 보정·독립 확인 예산을 동결하는 것이다. B2/P를 이번 결과로 재선정하거나 종료된 실측을 재개하지 않는다. `experiment_ready=false`와 기존 동결 profile/FAIL·S26/NPU 별도 범위는 유지한다. 아래 서비스 근거 또는 synthetic 선택 관련 문구는 이 결정 전 이력이다.

## 2026-09-26 채택한 중간 질문과 원래 목표로의 복귀 경로

사용자는 [고정 CC_DG 중간 질문](ENERGY_THERMAL_RESEARCH_SCOPE_20260926.md)을 채택했다. [최소 부족 항목·단계/중단 기준](ENERGY_THERMAL_TO_ORIGINAL_GOAL_PLAN_20260926.md)은 동일870건 직렬/병행의 상충을 기술하고, 별도로 원래 혼합 도착의 대화형/일반 서비스·기기 에너지·열 평가로 연결한다. 기존 요청별 engineering deadline을 묶음 기한이나 실사용 SLA로 전용하지 않고, AP 최고를 안전 한도로 채택하지 않는다. 현재 고정 모형은 동적 에너지 정책에 연결할 상태별 비용이 없으며 공통창 에너지 방향 재현도 실패했다. 다음은 근거 있는 서비스/최소 의미 절감 기준 또는 synthetic sensitivity 범위를 정하는 PC 계약이고, 필요한 실측은 그 결정을 바꿀 공백에만 별도 예산으로 설계한다. 새 실행·최종 성과 PASS/목표 축소 없음; 기존 FAIL·동결 profile·`experiment_ready=false` 유지. 아래 권고 기록은 채택 전 이력이다.

## 2026-09-26 후속 연구 질문 권고: 고정 묶음의 에너지·시간·AP 상충

[연구 설계 검토](ENERGY_THERMAL_RESEARCH_SCOPE_20260926.md)는 동일870건 CC_DG의 사전 완료기한 아래 공통480초 조건부 기기 에너지와 AP 경로를 비교하는 **중간 질문**을 권고한다. 이는 원래 겹쳐 도착하는 대화형/일반 요청의 동적 배정 목표를 변경하거나 고정 모형을 완성된 최적화로 승격하지 않는다. 29.1°C는 확인 두 세션에서 사후 관측한 일치 시작 AP이며 서비스 한도나 개발 기준이 아니다. 기한·최소 의미 절감량과 반복 변동성 근거는 아직 미정이다. 기존 동결 profile·FAIL·부분 결과·`experiment_ready=false`를 유지하며 새 실측/예산은 확정하지 않는다. 아래 고정 비교·제약 탐색은 기술 이력이다.

## 2026-09-26 현행 PC 판단 범위: 고정 CC_DG의 사용자 제약 탐색

[기록 기반 오차 분해·제약 탐색](ENERGY_OPERATIONAL_DECISION_PC_20260926.md)은 기존 동결 profile을 바꾸지 않고 공통480초 에너지 비교 오류를 공개한다. 선택 입력은 동일870건 CC_DG의 부하 시작→완료기한과 부하 AP 최고 **사용자 지정** 한도뿐이며, 미합의 서비스 수치를 만들지 않는다. 두 arm 모두 가능하면 완료시간·열 상충과 에너지 순위 불일치를 그대로 반환한다. 모형상 단일 후보도 정책 우월성/Android 안정성/동적 스케줄러 PASS가 아니다. 발열·배터리 필수 목표와 기존 FAIL·부분 결과·40값/20null·`experiment_ready=false`는 유지한다. 실제 서비스 최적화 주장은 별도 기준·독립 근거가 필요하며 새 실측은 승인되지 않았다. 아래의 고정 비교/후보 절은 이력이다.

## 2026-09-26 현행 범위: 고정 CC_DG 운영 결과의 제한된 PC 활용

[운영 비교](ENERGY_OPERATIONAL_PAIR_01_RESULTS_20260926.md)는 4/4세션 완료·종료됐다. [PC 연결](ENERGY_OPERATIONAL_SIM_CONNECTION_20260926.md)은 개발 직렬/병행 각1세션에서 A24·현재 두 모델·동일 870건 고정 묶음의 단계별 시간/조건부 기기 전체 전력/AP 경로를 동결해 확인 각1세션의 오차만 계산한다. 공통480초 에너지 차이 방향은 재현 실패했다. 정책·도착 스케줄러의 에너지/열 적격성을 확대하지 않고 미계측 운영 구간·BAT·다른 병행은 미지원으로 둔다. 발열·배터리 필수 목표, 과거 FAIL/부분 결과/40값/20null·`experiment_ready=false`와 S26/NPU 별도 범위는 유지한다. 아래 후보 문구는 실행 전의 이력이다.

## 2026-09-26 후속 PC 후보: 운영 비용을 포함한 한 조합 비교

[반복 중단 검토](ENERGY_DESIGN_REVIEW_20260926.md)에 따라 동일 초기 열 상태 질문과 실제 준비·대기 비용 질문을 분리한다. 발열·배터리·응답/완료 조건을 함께 다루는 목표와 기존 평가 FAIL은 유지한다. 첫 직렬 anchor에 맞추는 COLLECT-05는 종료·재개 금지다.

새 `ENERGY-OPERATIONAL-PAIR-01`은 PC 준비된 **권고 후보**이며 실행 승인이 아니다. CC_DG 개발2→관측 설정 동결→확인2, AB/BA 순서, 모든 arm에 같은 단기 직렬/병행 적격성·고정 resident120초 준비를 적용한다. 시작 온도를 기록하되 동일 열 상태/인과/정책 PASS를 주장하지 않는다. AP 공통 대역의 근거는 미확정이며 임의 숫자로 채우지 않는다. 반대배정·P 튜닝·일시정지 Android는 이번 범위 밖이다. 상세 예산/제한은 연결 보고서를 따른다. 새로운 실측 전까지 `experiment_ready=false`다.

> 2026-09-26 [COLLECT-05 종료](ENERGY_THERMAL_COLLECT05_RESULTS_20260926.md): 승인 plan_v9는 개발 CC_DG 직렬1세션만 적격 완료하고 다음 병행 후보에서 resident AP 사전 온도 준비 351.176초 상한으로 중단했다. 개발2시도·확인0, 동결/직렬병행 비교 없음, `stopped_no_resume`. ±0.5°C 최종 gate와 기존 FAIL·40값/20null·`experiment_ready=false`는 변경하지 않는다. 전체8세션 자동 재수집 대신 현 AP 경로·대기 비용으로 동등성 실현 가능성을 PC에서 판별한다. 아래 계획은 당시 이력이다.

> 2026-09-26 [COLLECT-04 온도 경로 분석과 COLLECT-05 PC 후보](ENERGY_THERMAL_TEMPERATURE_PREP_20260926.md): 공식 AP baseline +0.8°C 중단을 재현하고 준비 단계 재가열을 확인했다. 기존 ±0.5°C 최종 gate·직렬/병행·개발4→동결→확인4는 유지한 채 모든 세션의 resident 사전 관측 대기 최대360초를 새 계보에만 추가했다. 확인 병행 anchor 조회 결함을 수정하고 공식 baseline 재선택은 금지한다. 새 plan_v9의 268분 hard 상한/동일7040 추론 Check 통과, **기기 실행·새 예산 승인은 없음**. 시작 온도 준비 비용은 에너지·시간에 별도 포함하고 운영 냉각 비용과 구분한다. 기존 COLLECT-04는 재개하지 않는다. 아래 계획은 당시 이력이다.

> 2026-09-25 [COLLECT-04 PC 재준비](ENERGY_THERMAL_COLLECTION_REPREP_04_20260925.md) 완료. 수정 sampler APK와 같은 축소 관측 경로를 개발4→동결→확인4의 새 계보에 연결했다. 종료된 COLLECT-03/진단 표본은 분리하고 비교군·조건·중단 규칙을 유지한다. plan_v7/manifest/dry-run 통과, **기기 실행·새 예산 승인 없음**. 고정104분, timeout 예약206분40초, hard220분; 정상시간/배터리 완주 미확인. 기존 FAIL·부분 결과·experiment_ready=false와 발열·배터리 필수 목표 유지. 아래 문구는 당시 이력이다.

> 2026-09-25 [sampler PC 재현·수정](ENERGY_SAMPLER_PC_20260925.md). 과거 원인 확정 없이 실제 toMap 경쟁 결함과 실패 증거 게시를 보완했다. 다음 후보는 같은 실패 경로의 진단1세션(35분 상한, 미승인)이며 전체8세션이 아니다. 진단 자료를 정식 개발/확인 표본으로 전용하지 않고 관측 버전/새 APK 계보를 분리한다. 기존 목표·판정·experiment_ready=false 유지.

> 2026-09-25 [COLLECT-03 결과](ENERGY_THERMAL_COLLECT03_RESULTS_20260925.md): 승인 실행 후 첫 개발 세션 sampler NoSuchElementException으로 중단했다. 화면조회23회 성공과 부하중 장기 안정성은 구분한다. 동결/확인/직렬병행 비교 미완료, 새 실측 없이 PC snapshot 실패경로 검토가 다음 단계다. 기존 모든 판정·experiment_ready=false 유지.

> 2026-09-25 [에너지 직렬/병행 수집 재준비](ENERGY_THERMAL_COLLECTION_REPREP_20260925.md) PC 완료. 새 COLLECT-03 후보만 준비했고 실행 미승인이다. 개발/확인 모두 같은 축소 관측 경로, 기존 중단자료 제외, 비교군·작업량·기준·220분 상한 불변. 현재 기기 gate/부하 안정성 미확인. 발열·배터리 필수 목표와 experiment_ready=false 및 모든 과거 증거를 유지한다.

> 2026-09-25 [무추론 화면진단02](ENERGY_SCREEN_OBSERVE_02_20260925.md)32회 성공. 필터기기동작만 확인했으며 부하중안정성·에너지/열보정은 미검증이다. 다음은 새로운 관측방식으로 에너지수집을 재준비할 조건의 PC 검토이고 전체8세션 자동실행은 없다. 기존 목적·증거·experiment_ready=false 유지.

> 2026-09-25 [화면 관측 PC 진단·보완](ENERGY_SCREEN_DIAGNOSIS_PC_20260925.md) 완료. 새 host 필터/오류분류만 구현, 기기미검증. 다음은 미승인 무추론32조회·8분 이내 후보이며 전체8세션 재수집부터 시작하지 않는다. 기존 run_v2 중단·소비량·FAIL·실험준비false는 유지한다.

> 2026-09-25 실행 결과: [에너지·열 수집 부분 종료](ENERGY_THERMAL_COLLECTION_EXECUTION_20260925.md). 사용자 승인 후 설치1 성공, 개발 첫 세션의 화면 조회2초timeout으로 중단했다. 개발완료0·확인0·추정동결없음. 새 실측/재시도 없이 host 관측 경로의 PC 검토가 다음 단계다. 206분40초는 timeout 합산 예약이며 정상 예상시간이 아니다. 기존 실험·미확인 범위와 experiment_ready=false 보존. 아래 준비 당시 미승인 문구는 이력이다.

> 2026-09-25 최신 준비: [ENERGY-THERMAL-COLLECTION-PREP-02](ENERGY_THERMAL_COLLECTION_PREP_02_20260925.md). 사용자 요청에 따라 두 CPU/GPU 병행 조합과 같은 backend/작업량의 실제 직렬 대조를 별도 긴 세션 경로로 준비했다. 단독4경로는 직렬 내부 관측으로 중복을 줄이되 같은 초기온도의 독립 단독 실험으로 부르지 않는다. 개발4→동결→확인4, 진단6976/warmup64/총추론7040·상한220분은 **새 실행 승인 전 미실행**이다. 관련 PC 테스트23건·서명 APK·dry-run 완료. 기존 발열·배터리 필수 목표와 기기별 지원 경계, 일시정지 Android/P 튜닝 보류, FAIL/40값/20null/experiment_ready=false·S26/NPU 별도 협업을 유지한다. 아래 단독8세션 후보는 당시 이력이다.

> 2026-09-25 사용자 필수 목표 반영: **발열·배터리 최적화**를 동일 작업량·출력 품질·대화형 응답·일반 완료 제약과 함께 평가한다. 시간 중심 P 결과만으로 전체 목표를 종료/성공 처리하지 않는다. [ENERGY-THERMAL-PC-01](ENERGY_THERMAL_PC_01_20260925.md)에서 기존 MobileNet160세션의 조건부 에너지·상태 기반 열 보정과 격리 PC 회계를 완료했다. 현재 두 모델 절감 검증은 아니며 일시정지 Android 연결·P 튜닝은 보류한다. 다음은 [현재 두 모델 4단독 경로 수집 후보](ENERGY_THERMAL_COLLECTION_PROPOSAL_20260925.md)의 PC 실행 준비이며, 실측은 별도 승인 대상이다. 기기별 단위/계수·보정/사후 내부 확인·가정 탐색을 분리한다. 기존 목적/FAIL/부분 결과/40값/20null/종료 기록·experiment_ready=false와 S26/NPU 별도 협업은 유지한다. 아래는 당시 계획이다.

> 2026-09-25 별도 후속 개발 **REPLAN-PC-01 착수·PC 구현 완료**: [조작 기반 배경 시작 제한 계약](REPLAN_PC_01_20260925.md). 질문은 “조작 기반 배경 시작 제한과 요청 우선순위·정적 배정을 비교할 때, 대화형 AI 응답과 같은 배경 작업량의 완료 사이에 어떤 차이가 생기는가?”다. 기존 목적·주 결합 FAIL을 대체하지 않는다. 새 PC 경로만 구현·기능 검증했으며 Android/실기기·B2 선정·성능 평가·새 P는 미실행이다. 두 시작 규칙에 동일 정적 후보와 개발 예산, 공통 조작/요청·drain을 적용하고 평가 전에 고정한다. 공개 앱 규칙의 요청 단위 참고이며 Ente 전체 재현/실사용 분포/UI 개선을 주장하지 않는다. 특정 면담이나 δ 확정을 이번 PC 작업의 필수조건으로 두지 않는다. 다음은 필요한 Android 연결 및 제한된 개발→동결→평가의 별도 예산 준비이고, S26/NPU 채택·기존 증거·experiment_ready=false는 유지한다. 아래는 각 당시 기록이다.

> 최신 사후 분석(2026-09-25): [일반 서비스 δ 경계](ARRIVAL_DELTA_SELECTION_20260925.md). CPU긴급우선 대비 일반위반 증가δ 아래 긴급P95최소 기준에서 δ0은B2 9조건/CPU2조건/low동률이며 P단독최선은없다. 모든조건에하나를고정하면 δ<40/9%p에서CPU만적격이다. 기존CSV만사용했으며 P튜닝·추가시뮬레이션·실측없음. 다음은서비스요구결정이고 δ0/minimax/시나리오별oracle를최종요구·배포정책으로채택하지않는다. 기존FAIL·동결값·experiment_ready=false유지. 아래는당시계획이다.

> 최신 검토(2026-09-25): [B2·B3·P 서비스 비교](ARRIVAL_SERVICE_COMPARISON_20260925.md). 기존 시뮬레이션 재집계상 기본 큐 B2의 긴급 지연은 P보다 유리하지만 일반 기한 위반20/90 대17/90으로 서비스 상충이 남는다. 현재 P 튜닝을 보류하고 강한 정적 기준 중심의 제한적 정책 선택 문제로 정리하는 방향을 **권고**한다. 일반 서비스 목적·허용손실·최종 연구 범위는 아직 변경/채택하지 않는다. 추가 실측 없이 기존 결과·세션 분모·FAIL·experiment_ready=false를 유지한다. 배터리 시작20%의 사용자 승인과 실행 중 하한20%의 당시 구현 해석은 구분한다. 아래 계획은 각 당시 이력이다.

> 최신(2026-09-25): [확인 실측·PC 탐색 결과](ARRIVAL_FOLLOWUP_AND_EXPLORATION_20260925.md). 별도 승인 후속3세션/진단12/warmup24 완료·cleanup 확인, 기존개발/동결 불변. PC 시뮬레이터·B2선정·B3/P 후보/제거 비교를 실행했으나 P 우월성을 뒷받침하지 못했고 여러 조건에서 손해였다. 순수 관측 재생, strict 단독 가정 모드, 미검증 병행 탐색을 분리했다. 다음은 일반 서비스 제약과 강한 정적 기준의 검토이며 실험 확대를 자동 진행하지 않는다. PC 독립평가 준비 gate는 목적/허용손실·Android active 정책·한정 예측 정확도·새 paired 변동성 부족으로 BLOCKED, experiment_ready=false다. 아래 계획/미승인 문구는 각 당시 기록이다.

> 최신 PC 준비(2026-09-25): [CONFIRM-FOLLOWUP-01](ARRIVAL_CONFIRMATION_FOLLOWUP_20260925.md). 완료된개발6/동결은재사용하고누락B/A/F만새3세션/진단12/warmup24/설치0·상한30분으로제안했다. 기존확인E/D/C와는계획·날짜·host계측차이를구분하는조건별기술통계만허용한다. PC20건관련검증·서명/manifest/dry-run완료, 실기기미승인·미실행. ADB원인은5037접속실패범위를넘어미확정이며server재시작/기기명령없이관측경로를보완했다. 기존원계획부분종료·FAIL·40값/20null·experiment_ready=false를유지한다.

> 최신 실행(2026-09-25): [RECOVERY-02/COLLECT-03](ARRIVAL_INSTALL_RECOVERY_20260924.md). 새 승인으로 설치1 성공, 개발6 완료·동결 후 확인3 완료/4번째 staging ADB daemon5037 오류로 종료했다. 전체10시도/9완료/실행전실패1/미시도2, 진단36/48·warmup72/96, retry0. 27.959분·cleanup 확인. active/병행 확인은 미실행이므로 PC 정책값 연결/병행허용 확대 없음. 먼저 PC host daemon과 staging 증거를 점검하며 종료계획은 재개하지 않는다. 기존40값/20null/FAIL·B2/B3/P 비교 계약·experiment_ready=false 보존. 아래 기록은 각 당시 이력이다.

> 최신 실행(2026-09-24): [INSTALL-RECOVERY-01/COLLECT-02 결과](ARRIVAL_INSTALL_RECOVERY_20260924.md). 승인 스크립트1회가배터리50%<시작55% gate로종료됐다. 전송/설치/세션/추론0, hostcleanup확인·복구91.156초/workflow92.297초. 전체계획소비·재개금지, 새표본/PC연결없음. 먼저충전/비충전준비후새실행계획이필요하다. 기존값/FAIL/병행차단/experiment_ready=false유지. 아래미승인·준비상태는당시이력이다.

> 최신 PC 준비(2026-09-24): [설치 복구→COLLECT-02](ARRIVAL_INSTALL_RECOVERY_20260924.md) 실행안 완료·미승인. 부분 출력/timeout/host종료/identity 증거를 보존하는 별도 staging 설치를 준비했다. 복구600초+수집5490초=101.5분, 설치최대1·개발6→동결→확인6/48진단/96warmup, retry/대체/추가0 제안이다. 복구 verified/cleanup과 매 단계 exact설치본gate 후에만 수집하며 기존종료계획은재개하지않는다. Android/APK·추정값불변, PC28건통과, 실기기미실행·experiment_ready=false.

> 최신 실행(2026-09-24): [ARRIVAL-COLLECT-01 결과](ARRIVAL_INTEGRATED_COLLECTION_20260924.md). 12세션 승인 후 설치1회가120초 timeout으로 중단됐다. 세션0/12·진단0/48·warmup0/96, host cleanup/프로세스부재 및 이전설치APK 유지 확인. 계획은 claim/stopped로종료·재개금지, 새동결/확인/PC연결없음. 먼저 설치 단계 증거 보존을 갖춘 새 진단 PC 준비가 필요하며 추가 기기 실행은 별도승인이다. experiment_ready=false와 B2/B3/P·기존FAIL을 유지한다. 아래 준비/미승인 상태는 당시 이력이다.

> 최신 준비(2026-09-24): [ARRIVAL-COLLECT-01](ARRIVAL_INTEGRATED_COLLECTION_20260924.md)의 별도 Android active/shadow 계측·PC 대응·APK/계획 준비 완료, 실측 미승인·미실행. 엄격 CPU fallback은 전체 직렬이며 GPU 적응 배정 성능을 뜻하지 않는다. 판단 비용·큐 부하 전이·한정 병행을 분리하는6조건×개발/확인2단계(제안12세션/48진단/96warmup/설치2·91.5분)로 좁혔다. 성공해도 완전한B3/P·최선B2·정책성능/정확도PASS가 아니며 experiment_ready=false. 아래 날짜별 최신/현재 표현은 당시 이력이다.


> 최신 PC 작업(2026-09-24): [ARRIVAL-CAL03-CONNECT-01](ARRIVAL_CAL03_CONNECTION_20260924.md) 완료. CAL-03 priority별40관측과 개발자료의 공동 구간 통계를 별도 PC 정책·단독 이벤트 엔진에 연결했다. 기존 Android 정책/20null/동결fit/확인 판정은 불변이다. adaptive D→A와 부하·병행 전이 미검증 때문에 experiment_ready=false이며 완전한 B3/P 또는 정책 성능 PASS가 아니다. 새 앱 연결·실측·본simulation은 실행하지 않았다. 아래 현재/다음 표기는 각 당시 이력이며 최신 우선순위는 STATUS를 따른다.

> 현재 작업(2026-09-24): [ARRIVAL-STALL-OBS-DIAG-01](ARRIVAL_STALL_OBSERVATION_DIAGNOSTIC_20260924.md). 앱 변경 없는 새host 관측 진단1회가 완료됐다(runtime4/warmup8/정규1). 원인은 여전히 미확정이다. [CAL-03](ARRIVAL_TIMING_CAL03_PREPARATION_20260924.md)는 이후 승인받아 개발8→동결→확인8을 완료했다. [실행 결과](ARRIVAL_CAL03_EXECUTION_20260924.md)를 따른다. 초기 단독 추정40슬롯을 산출했으나 experiment_ready=false와 기존20null을 유지한다. 이전 통합 실패/CAL/초기화 진단을 재개하지 않는다. 결과는STATUS를 우선하며 성능보정/정책평가와구분한다.

- 2026-09-24 현재 후속: [ARRIVAL-WARMUP-REQUEST-DIAG-01](ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md) 승인1회 실행 후 host125초 timeout으로 종료. 설치1성공/세션1실패, runtime반환1·마지막GPU분류Interpreter start, warmup/정규호출수미확인. 총311.344/600초·회수/host cleanup완료·retry0. 보정준비완료가 아니며 다음은PC의lifecycle/Future/watchdog무기록조건검토다. 소비계획재실행금지, 기존20null·FAIL·부분결과불변.

- 2026-09-24 `ARRIVAL-WARMUP-DIAG-01`: [첫 CPU warmup 진단 결과](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md) 승인 실행 완료. 설치1·세션1·runtime4반환·첫CPU warmup1/명시적inference총1·평가요청0, 181.0/600초·retry/대체/추가0·회수/cleanup 완료. CAL-02 원인미확정·동기 자료 보정/정책평가 제외·20null/experiment_ready=false 유지. 계획 종료/재실행 금지. 다음은 PC 미관측 warmup/요청 경계 정리이며 후속 실측은 별도 계획·승인 대상.
- 2026-09-24 A24 후속 `ARRIVAL-INIT-DIAG-01`: [초기화 단일 진단 결과](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md) 승인 실행 완료. 설치1·세션1·runtime4반환·warmup/명시적추론0·209.047초/600초·retry/대체/추가0, 회수와cleanup 완료. CAL-02 실패는 미재현·원인 미확정이며 보정 완료가 아니다. 소비 계획은 종료/재실행 금지, 다음은 PC 단계 경계·잔여 가설 정리다. CAL-02 재개·후속 실측 자동 실행 없음.
- 2026-09-24 협업 결정 `S26-NPU-COLLAB-01` **채택/검증 대기**: S26을 XDEV-02 기기로 선정하고 별도 npu-runner/CompiledModel NPU 개발을 A24와 병행한다. 정확한 기기 identity·모델별 실행 장치/품질은 아직 확인 대상이다. 계약 모델 EfficientNet-Lite0 / EfficientDet-Lite0의 NPU 지원·품질·성능은 미검증이며 MobileNet 팀원 보고를 전용하지 않는다. [팀 안내](team/README.md), [채택 범위·판정 기준](DECISIONS.md#s26-npu-20260924)을 먼저 읽는다. CPU/GPU 재현과 NPU 확장은 별도 평가이며 A24 런타임 교체·기존 정책의3자원 지원 완료를 뜻하지 않는다.
- 2026-09-24 현재 추가 작업: `ARRIVAL-FAILURE-DIAG-PC-01`. CAL-02는 설치 성공 후 첫 세션 기록 누락으로 종료했다. [실패 진단 보완](ARRIVAL_FAILURE_DIAGNOSIS_20260924.md)의 코드·PC 검증을 완료했으며 정지 원인은 미확정이다. 추가 기기 진단은 별도 준비/승인 대상이고 중단16세션 계획은 재개하지 않는다. 아래 개정4.4 목표·기존 평가 FAIL·동결 simulation 의미는 유지한다.

아래 개정4.4 본문·일정표와 날짜별 후속 기록은 당시 계획/판정 이력이다. 현재 A24 두 adapter·독립 도착 실행·198요청 독립 평가는 완료됐고 주 판정은 FAIL이다. 본문의 후보/미구현/예정 문구를 최신 구현 상태로 읽지 않는다. 현재 상태는 STATUS가 우선하며, 4절의 NPU 제외 및9절의 추가 기기 기능 제한은 이번 채택 범위에서 대체한다. 기존 B2/B3/P 목표·동결 실험 계약을 소급 변경하지 않는다.

- 개정: 4.4 / 2026-09-18 / A24 주평가와 추가 Android 기기 고정정책 재현평가 분리
- 기준 코드: `df8192aa61eebacf83df7a7815f0c60c8bbf4004`의 `master`. 이 개정은 문서 변경이며 새 모델·스케줄러 구현 또는 실기기 PASS가 아니다.
- 이전 확장 작업: `ARRIVAL-EXT-01` — 기존 support-constrained 계획 동결을 보존하고, 별도 [비동시 도착 앱 내부 스케줄링 계약](ARRIVAL_SCHEDULING_EXTENSION_20260923.md)의 실측 경로를 평가한다. 이전 `SIM-PLAN-02-SUPPORT`는 [동결 계약](SUPPORT_SIMULATION_PROTOCOL.md)과 receipt `SUPPORT_SIMULATION_FREEZE_20260922.json`에서 `SIMULATION_PLAN_READY` 상태를 유지한다. 새 확장의 A24 smoke·개발 pilot 19세션과 독립 평가 27세션을 완료했고 새 본 simulation은 미실행이다.
- 현재 bounded simulation의 deadline은 사전 quantile/multiplier 규칙으로 계산한 공통 복수 engineering scenario다. 사용자 절대 SLA나 정책 우월성 기준을 승인한 것은 아니다. 이전 calibration_pending 기록은 역사적 근거로 보존한다.
- 유지: A24 개발·주평가, 기존 80슬롯과 diagnostic v1/v2 원본, CALIB-01B PASS, 실패를 포함한 전체 도착 분모. 추가: 정책 동결 후 최소 한 대의 다른 Android 기기에서 축소 재현평가.
- 전환: 단일 분류 모델은 기존 기준선으로 보존하고, 서로 다른 두 AI 작업의 요청 배정 문제를 새 주평가로 준비한다. 구체 모델과 마감시간은 아직 미확정이다.
- 문서 역할: 이 문서는 목표·우선순위, [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)는 혼합 요청·후보·선행 연구의 근거와 한계, [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)는 exact model/label/hash/tensor·host 판정, [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md)는 기기 이식 가능한 외부 모델 probe 계약, [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)는 새 다기기 실험 계약, [CALIBRATION_PROTOCOL.md](CALIBRATION_PROTOCOL.md)는 구현된 legacy 단일 모델 계약, [PROJECT_STATUS.md](PROJECT_STATUS.md)는 현재 진행 상태다.

## 현재 PC 단계의 명시적 축소 범위

2026-09-23 추가 작업은 위 2026-09-22 support-constrained PC 계약의 결과·가정을 바꾸지 않는다. 새 protocol `arrival-scheduler-v1`은 A24에서 독립 도착·실제 두 모델·resident runtime·비선점 queue 배정의 실측 확장이다. 개발 pilot 19세션으로 정책·분석 규칙을 고정한 뒤 독립 평가 27세션을 완료했다. 조건부 정책은 normal 처리효율을 개선했지만 CPU 긴급 우선 대비 urgent P95 10% 최소효과를 충족하지 못해 주 결합 기준은 실패했다. [PC 후처리와 적합성 계획](ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md)은 이 판정을 재현하고 확장 simulator의 지원·미지원 경계를 분리한다. 새 본 시뮬레이션과 추가 holdout은 별도 계획·승인 대상이며, 평가 자료를 보정과 검증에 함께 쓰지 않는다.

2026-09-22 사용자 지시를 채택했다. 아래 장기 개정4.4의 다중 도착률·등급 반전·추가 기기 목표는 현재 PC 계약의 완료 조건이 아니다. 현재 모델은 구현·gate를 통과한 exact 분류/탐지이며 A24 thermal0/resident/non-preemptive, warm 교환가능성 가정과 측정된 전체 co-run만 허용한다. 12개 offset0·분류 urgent6/탐지 normal6 배치와 54개 복수 deadline budget, 5paired atom 전수 평가로 제한한다. CPU FIFO/urgent/정적/항상 허용 co-run/시작 전 adaptive를 비교하며 STATIC=CPU FIFO alias를 숨기지 않는다.

주 결과는 Pareto frontier, epsilon=0/0.5/1은 예측 trade-off 구간의 sensitivity다. 임의 실질효과·허용손실 단일값을 만들지 않는다. exact bootstrap3125·low/central/high·5LOSO로 제한 모형 민감도를 보고한다. 반사실적 순서 효과·staggered overlap·장기 thermal·새 transition·다른 기기는 OUT_OF_SUPPORT다. 가정은 실측 검증 사실이 아니다. 사용자 절대 SLA는 calibration_pending, 복수 engineering deadline은 동결되어 있다.

다음 `SIM-RUN-01-SUPPORT`는 별도 승인 후 본 실행, 그 후 `SIM-DEVICE-CONFIRM-01`은 선택 정책의 A24 소규모 paired 확인 계획이다. 이 순서로 장기 목표와 현재 증거를 구분한다.

## 1. 한 문장으로 설명하는 프로젝트

**D1Check는 한 Android 앱에 겹쳐 들어오는 서로 다른 AI 요청에 대해, 무엇을 먼저 실행하고 CPU/GPU 중 어느 실행 경로를 쓰며 언제 병행할지를 결정하여 대화형 요청의 기한 준수와 응답속도를 높이고 백그라운드 작업의 서비스를 보장하는 앱 수준 스케줄러다.**

대회 가제는 **「스마트폰 다중 AI 작업의 마감시간·실행 간섭을 고려한 자원 배정」**이다. 긴급은 사용자가 결과를 기다리는 대화형 요청을 뜻하며 재난·의료 판단이 아니다. 연구 질문은 “기기·작업별로 미리 고른 좋은 고정 배정과 단순 우선순위보다, 현재 큐와 실행 간섭을 고려한 배정이 언제 얼마나 유리한가?”다.

수상 가능성은 보장할 수 없다. 측정 도구의 규모보다 실제 사용 문제, 강한 기준정책 대비 효과, 효과의 원인과 적용 한계를 명확히 보이는 데 개발 시간을 쓴다. 동적 정책이 이기지 못한 조건도 결과다.

## 2. 연구 범위·혼합 요청 조건·대표 시연

연구 범위는 **한 앱에서 제한된 CPU/GPU를 공유하는 여러 AI 요청의 배정 문제**다. 특정 사진 정리 기능에 한정하지 않는다. 실제 구현할 작업은 우선 분류와 객체탐지 두 종류로 제한하되, 여러 요청 조건에서 같은 정책의 적용 범위와 한계를 검증한다.

| 구분 | 이 계획의 역할 | 확정/검증 상태 |
| --- | --- | --- |
| 연구 문제 | 실행 순서·실행 경로·병행 여부 결정 | 주제 유지 |
| 실제 작업 | 분류·객체탐지의 독립 모델과 전·후처리 | 후보, MODEL-02/TASK-02에서 승인·구현 |
| 주평가 조건 | 일반 backlog 중 긴급 burst, 지속 혼합 요청 | 부하·작업 비율·도착 기록을 개발 뒤 동결 |
| 보조 조건 | 낮은 부하, 동일 등급 요청의 동시 도착 | overhead·일반성·공정성 확인; primary 실패를 대체하지 않음 |
| 대표 시연 | 사진 자동 태그·색인 중 선택 사진의 객체탐지 | 이해를 돕는 후보이며 연구 범위의 필수 제약이 아님 |

`task_id`와 긴급/일반 등급은 독립 필드다. 분류도 대화형 요청이 될 수 있고 객체탐지도 일반 요청이 될 수 있다. 기본 시연에서 분류=일반/탐지=긴급을 쓰더라도 평가 계약에서는 이를 하드코딩하지 않는다. 최소 한 사전 지정 보조 조건에서 등급 배치를 바꿔 특정 모델의 속도와 우선순위 효과를 구분한다.

사진 정리 시연을 채택한다면 누적 사진의 태그·색인은 일반 결과의 durable persistence/readback, 선택 사진의 box/label은 긴급 output-ready로 연결한다. 다른 시연을 골라도 task별 입력·출력·완료 경계를 먼저 고정하고 정책마다 같은 실제 작업을 수행한다. 시연을 늘리는 것이 연구의 필수 목표는 아니다.

SCOPE-02 조사 결과는 [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)에 기록했다. 모바일 multi-DNN·이종 프로세서 scheduling 문제와 관련 연구는 확인했지만 한 앱에서의 실제 도착 빈도·burst 분포를 입증한 사용자 로그는 확보하지 못했다. 따라서 W-burst/W-sustain의 arrival trace는 합성 실험 조건으로 공시한다. 사용 관찰·기록 또는 3~5명의 짧은 과업 인터뷰는 가능한 보조 근거지만 특정 사진 기능의 수요 인터뷰를 모든 개발의 선행 조건으로 만들지 않는다. 작은 인터뷰 표본으로 시장 수요·채택률·실사용 도착 분포를 추정하지 않는다.

통역·OCR·게임·LLM은 향후 작업 유형의 예시다. 현재 두 시각 모델을 검증한 결과로 그 작업들의 성능을 주장하지 않는다. 다른 앱이나 OS 스케줄러를 제어하는 구현도 아니다. 실측 없는 작업을 `sleep()`이나 분류 반복 횟수 변경으로 흉내 내고 실제 다중 AI 검증으로 표시하지 않는다.

## 3. 산업공학적 기여와 검증 가설

| 산업공학 관점 | 이 프로젝트의 구체 내용 | 제출 증거 |
| --- | --- | --- |
| 대기행렬·서비스 수준 | 우선순위, burst 도착, 대기와 과부하, 일반 작업 starvation | 전체 도착 로그, 긴급 P95·기한 내 완료율, 일반 backlog |
| 이종 자원 배정 | 작업별 CPU/GPU 적합성, 준비·전환 비용, 비선점 실행 | 작업×실행 경로 프로파일, 배정 결정 로그 |
| 제약하의 의사결정 | 메모리·열 안전·일반 최소 서비스 하에서 긴급 지연 최소화 | 제약 준수표, 강한 기준정책 대비 대응 비교 |
| 실험계획·통계 | 같은 arrival trace, 순서 무작위화, 개발/평가 분리 | 독립 세션 효과 크기·신뢰구간, 실패·제외 기록 |
| 이산사건 시뮬레이션 | 실측 서비스시간·간섭으로 실험 범위 확장 | 별도 실기기 holdout으로 보정 오차 검증 |
| 외적 타당성 | A24에서 정책을 고정한 뒤 다른 Android 기기에서 무재튜닝 축소 재현 | 기기별 결과와 `device × policy` 차이, 실패·미지원 cell |

가설 H1: 누적 작업 중 대화형 요청이 도착하면 단독 실행보다 지연·기한 위반이 증가한다. H2: 기한·현재 자원 점유·간섭을 고려한 정책 P가 개발 자료로 선정한 고정 정책 및 단순 동적 정책보다 서비스 제약 아래 유리한 조건이 있다. H3: 무조건 병렬 실행보다 선택적 직렬/병렬 허용이 낫다. H4: A24에서 고정한 정책 논리와 사전 calibration 규칙이 추가 기기에서도 코드·임계값 사후 조정 없이 안전하게 동작하며, 우세 backend가 달라도 기준정책 대비 방향 또는 적용 한계를 재현한다. H1부터 실측하며 H2~H4의 성립을 전제하지 않는다.

열 스로틀링 발생은 성공의 필수조건이 아니다. 관측 가능한 열 상태가 안정적인 조건에서도 H2가 성립하면 의미가 있다. 시스템 thermal status가 0이라는 사실만으로 하드웨어 스로틀링 부재를 확정하지 않으며, 미검증 온도를 에너지 절감률로 바꾸지 않는다.

## 4. 범위와 모델 선택

2026-09-24 적용 보완: S26 CPU/GPU는 model-probe-v1 계열 확인 후 동결 정책 축소 재현을 별도로 통과해야 XDEV-02 완료다. NPU는 별도 엔진·모델 변환·정밀도·품질 계약으로 개발한다. 기기별 지원 경로를 정책 입력으로 다루는 구조는 **개발→동결→독립 평가** 순서이며 현재 미구현/미검증이다. 한 모델만 지원하면 그 모델로 제한하고, 개별 CPU/GPU/NPU 지원을3건 병행 가능성으로 바꾸지 않는다. A24의 기존 런타임·실험과 열 상수/전환비용을 새 엔진에 전용하지 않는다. 아래 원래 범위 문구는 개정4.4 이력이다.

- 기기 역할: Galaxy A24는 개발·주평가 기기다. A24에서 정책과 분석법을 동결한 뒤 최소 한 대의 다른 Android 기기를 외부검증 기기로 사용한다. 가능하면 SoC·성능 등급이 다른 두 번째 기기를 고르고, 세 번째 기기는 일정이 허용할 때만 추가한다.
- 기존 S26 formal은 보조 사례일 뿐 새 두 작업의 외부검증을 대체하지 않는다. S26을 다시 사용할 수 있다면 다른 기기와 동일한 새 probe/profile/evaluation 계약을 통과한 결과만 재현평가로 인정한다.
- 주평가: 두 실제 task adapter, CPU와 검증된 GPU 실행 경로, 일반/긴급 요청. 먼저 전체 한 건 실행을 완성한 후 PROFILE-02의 간섭 측정을 통과한 조합만 최대 두 건 병행한다.
- 비선점 단위: 모델 내부 추론을 중단하지 않는다. 최초 구현은 이미지 한 건의 전·후처리와 완료 경계를 포함한 service 단위를 끝낸다. 레이어 분할·OS 주파수 제어는 제외한다.
- 모델 품질·입력 해상도·정밀도·전처리·후처리 임계값은 정책 간 동일하게 고정한다. 모델 크기나 정확도를 낮춰 얻은 이득을 스케줄링 이득에 포함하지 않는다.
- NPU·강화학습은 필수 범위 밖이다. 추가 기기는 CPU/GPU 중 실제 검증된 cell만 사용하며, 기기별 지원 차이를 숨기기 위한 compatibility override나 silent fallback을 도입하지 않는다. 신규 런타임으로의 전면 이전도 필요성이 입증될 때만 한다.

| 역할 | 먼저 검증할 후보 | 선택 이유와 상태 |
| --- | --- | --- |
| 과거 비교 기준 | 기존 MobileNet V1 | 80슬롯과 CALIB-01B 재현용. 원 모델·파일·해시 보존. 1001행 라벨 출처 미확인 문제는 해결된 것으로 처리하지 않음 |
| 새 분류 작업 | EfficientNet-Lite0 FLOAT32 v1 | host source/hash/tensor/내장 1000 labels·Apache-2.0 metadata 확인. A24 CPU/GPU canonical 계약 동등성 및 bounded profile 확인; 품질 수용·추가 기기 검증은 pending |
| 새 객체탐지 작업 | EfficientDet-Lite0 FLOAT32 v1 | source/hash/tensor/내장 labels·raw/decoded CPU output 확인. exact binary license 귀속은 미입증이므로 승인 기기 내부의 비배포 연구 probe만 조건부 허용; 저장소·APK·공유 bundle 포함 금지 |

이는 최신 모델 경연이 아니다. 공개된 [분류 모델 안내](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier)와 [탐지 모델 안내](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector)는 후보의 근거이며, 표의 다른 기기 성능을 A24 성능으로 사용하지 않는다. 파일을 확보한 뒤 실제 출력 tensor/metadata·label index를 검사해야 한다. 공식 문서가 있다는 이유만으로 특정 파일의 라이선스·1000/1001행 대응·GPU full delegation이 검증된 것은 아니다.

MODEL-02A 결과는 [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)에 기록한다. EfficientNet 분류는 host 계약을 통과했다. EfficientDet는 exact binary license 귀속이 확인되지 않았지만 Google 공식 안내와 Apache-2.0 sample이 고정 v1 URL을 직접 내려받아 쓰는 사실, raw/decoded host golden을 확인했다. 이는 법적·재배포 승인이 아니다. URL·byte count·SHA-256을 고정하고 binary를 저장소·PR·APK·팀 공유물에 넣지 않으며 각 실행자가 원 URL에서 직접 확보하는 **승인 기기 내부 비배포 연구 평가만 조건부 허용**한다. 배포가 필요해지면 exact license/NOTICE를 확보하거나 명시적으로 라이선스된 artifact로 교체한다. MODEL-02B는 동일 외부 manifest와 probe 코드로 각 기기의 CPU/GPU 실행 가능성, 실제 delegation/fallback, 품질, 메모리, 초기화 비용을 확인한다. 첫 pilot과 full profile은 A24에서 수행하고, 추가 기기는 정책 동결 뒤 같은 계약의 축소 profile을 수행한다. TASK-02에서만 사용자 경로와 공통 runner에 연결한다. GPU가 항상 불리하거나 미지원이면 그 사실을 받아들이고 큐 순서·동시성 제한의 효과를 검토한다.

## 5. 기존 구현과 새 구현의 경계

기준 commit의 calibration은 MobileNet FLOAT32 `[1,224,224,3] -> [1,1001]`와 image-v3 전처리에 고정돼 있다. 새 모델을 asset 교체만으로 넣을 수 없다. CALIB-01B의 119개 JVM 테스트 통과는 두 작업 지원이나 새 모델의 정확도·성능 통과가 아니다.

재사용할 것은 입력 read/decode·EXIF, monotonic event, queue/terminal 계약, 결과 영구 저장, exact artifact set/provenance 검증, CPU/GPU 준비·정리 경계다. TASK-02에서 모델별 전처리·출력 tensor·후처리와 label mapping을 명시하는 adapter, `task_id`/`model_id`, 독립 도착 발생기, 정책 공통 runner를 추가한다. 기존 core inference 타이머는 보존한다. 새 모델 API 내부를 계측할 수 없으면 API 호출 시간으로 따로 이름 붙이고 `Interpreter.run()`이라고 부르지 않는다.

formal v1, diagnostic v2, `calibration-v1`/schema 2, `android-mobilenet-v1-image-v3`는 그대로 보존한다. 새 task/arrival/result 계약은 별도 `multitask-v1`(예약 ID, 미구현)로 버전 관리하며 기존 CLI·manifest에 없는 옵션이 이미 작동한다고 문서화하지 않는다.

기존 `CALIB-01C-INPUT`은 legacy 단일 모델 입력 준비로 보류·재계획한다. 검증된 1001행 라벨을 꾸며서 통과시키지 않고 기존 blocker를 기록한다. 새 모델의 자체 검증된 labels를 쓰는 경로와 과거 라벨의 출처 해결은 별개다. 기존 8장 이미지는 연결 확인용이며 새 두 작업의 정확도 평가 데이터로 자동 승격하지 않는다.

## 6. 스케줄러 의사결정

요청 i는 예정 도착 a_i, enqueue e_i, 작업 k_i, 등급 u_i, 마감 d_i, 입력 hash, 허용 실행 경로 집합 E_i를 갖는다. 상태는 대기열, 현재 실행 요청·잔여시간 추정, warm 인스턴스, 메모리, 열 관측이다. 결정은 다음 요청, 실행 경로, 지금 시작/대기 및 허용된 병행 조합이다. CPU/GPU는 독립된 공장이 아니라 CPU 전·후처리와 메모리 등을 공유하므로 완전 독립 자원으로 모델링하지 않는다.

사전적 목적은 (1) 안전·품질·메모리·일반 최소 서비스 제약, (2) 긴급 기한 위반 최소화, (3) 긴급 완료 응답 P95 최소화다. 일반 서비스 하한과 허용 감소폭은 개발 단계에서 고정하고 최종 평가 후 완화하지 않는다. 가중치 최적화나 전역 최적해를 주장하지 않는다.

첫 P는 설명 가능한 규칙으로 구현한다. 새 요청·완료·열 상태 변경 시 현재까지 관측한 정보만 사용해 후보를 평가한다. 예상 완료에는 기다림, 읽기·전처리, 준비·전환, 추론, 후처리·필요한 저장 및 현재 co-run 간섭을 포함한다. 긴급은 등급 내 EDF, 일반은 공통 aging/최대 대기 규칙을 사용하며, 검증되지 않은 병행 후보는 제외한다. 예측 오차가 큰 상태에는 보수적인 프로파일 또는 직렬 실행을 사용한다. 사용하지 않는 GPU로 일부러 보내거나 평가 trace의 미래 도착을 미리 읽지 않는다.

구현은 각 실행 경로의 후보 요청과 허용 병행 조합만 열거하는 작은 dispatch 규칙에서 시작한다. 공통 aging으로 보호할 일반 요청과 서비스 제약을 먼저 적용하고, 남은 후보의 현재 대기 긴급 요청에 대한 예상 기한 위반 수·예상 지각량·예상 완료 순으로 비교한다. 동률은 예정 도착과 request ID로 해소한다. 대기를 선택할 때 다음 완료/기한/aging 경계에 재평가하도록 하며 무기한 대기하지 않는다. 이 국소 규칙은 전체 기간의 P95 최적화를 보장하지 않으므로 실제 전체 지표로 평가한다.

결정마다 선택·배제 사유, 예상 완료와 실제 완료, 정책 계산 시간을 기록한다. “열-aware AI” 같은 이름보다 어떤 관측 때문에 무엇을 바꿨는지 설명할 수 있어야 한다.

## 7. 반드시 넘어야 할 기준정책

| ID | 정책 | 비교 목적 |
| --- | --- | --- |
| B0 | calibration에서 고른 task별 고정 경로 + FIFO, 직렬 | 단순 기준 |
| B1 | 같은 고정 경로 + 긴급 우선/등급 내 EDF + 공통 aging, 직렬 | 순서 효과 |
| B2 | 개발 자료에서 고른 최선의 정적 정책: CPU-only 포함 task별 CPU/GPU 고정 배정, 직렬 또는 검증된 고정 병행, 단순 thermal pacing | 강한 정적 기준 |
| B3 | B1의 순서·aging + 단독 프로파일로 earliest-finish 경로 선택, 검증된 병행 허용 | 단순 동적 기준 |
| P | 같은 공통 규칙 + co-run 간섭·준비 비용을 고려한 예상 완료 및 시작/대기 결정 | 제안정책 |

B2는 같은 장치의 모든 합법적 task별 배정 후보(두 task·두 경로면 최대 4개), CPU-only, 고정 병행 허용/금지를 개발 자료에서 비교해 하나를 사전 고정한다. 단독 최속 경로를 그대로 B2로 가정하지 않는다. B3도 준비 비용은 고려하되 pairwise 간섭 보정은 하지 않아 P의 추가 요소를 식별한다. 평가 때마다 B2를 바꾸는 oracle을 사용하지 않는다.

정확도·열 안전·큐 상한·admission/expiry/drain 규칙·일반 서비스 목표·가용 모델 인스턴스 예산은 공통이다. 주비교 B2/B3/P의 지원 경로와 합법적 병행 조합은 동일하며 B2만 개발 단계에서 선택을 고정한다. B0/B1의 직렬 제한은 순서 효과를 보기 위한 명시적 기준 조건이다. CPU thread 수와 CPU 전·후처리 worker 예산도 고정한다. 다른 thread 수나 메모리 상한을 P에게만 주지 않는다. B2/B3/P에 동일 개발 데이터와 사전 제한된 튜닝 예산을 적용한다.

개발 결과가 유망하면 P의 (a) backend 고정, (b) 병행 금지, (c) 간섭 보정 제거를 필요한 조건에서 각각 비교한다. 열 변화가 작으면 thermal 제거 비교는 생략하고 이유를 남긴다. 단순히 B0만 이겼다는 이유로 동적 배정의 기여를 주장하지 않는다.

## 8. 측정과 공정한 평가

측정·deadline·arrival·통계 계약은 [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)를 따른다. **주평가는 A24에서 두 실제 모델을 실행하고, 요청의 도착 시각·등급·작업 비율만 합성·재생하는 실측 실험이다. 정책 동결 뒤 최소 한 대의 추가 Android 기기에서 같은 코드와 계약으로 축소 재현평가를 한다.** 모델 실행을 계산 모형으로 대체한 시뮬레이션과 구분한다.

| 방법 | 실제로 실행/계산하는 것 | 용도 |
| --- | --- | --- |
| 실기기 혼합 요청 재생 | 고정 도착 기록 + 실제 read/전처리/CPU·GPU 추론/후처리·저장 | 정책 효과의 주증거 |
| 실측 기반 이산사건 시뮬레이션 | 서비스시간·준비 비용·간섭 분포로 가상 큐와 자원 상태 계산 | 검증된 범위의 부하·burst·비율 민감도 탐색 |
| 대표 사용자 시연 | 사용자가 버튼/입력으로 실제 요청 생성 | 이해·사용 흐름 확인; 정량 반복 실험을 대체하지 않음 |

기기 간 실험은 두 묶음을 분리한다. `absolute-SLA`는 모든 기기에 같은 millisecond deadline과 같은 도착 trace를 적용해 실제 사용자 경험 차이를 본다. `capacity-normalized`는 각 기기의 동결된 단독 처리능력으로 부하를 스케일해 정책 구조의 재현성을 본다. 두 결과를 합치거나 유리한 묶음만 선택하지 않는다. 원시 latency를 기기 사이에서 단순 pooling하지 않고 기기별 효과를 먼저 보고한다.

시뮬레이션은 별도 실기기 holdout에서 오차를 검증한 뒤 사용한다. 데이터가 없을 때 임의 서비스시간으로 정책 동작을 확인하는 것은 개발용 toy 검증이며 성능 증거가 아니다. 자원이 부족하면 보조 시뮬레이션 범위를 줄이고 실기기 주비교를 우선한다. 핵심 측정 원칙은 다음과 같다.

- 주평가 시간은 예정 도착부터 output-ready/필요한 저장 완료까지다. enqueue 기준 시간도 별도 보고하여 발생기 지연을 드러낸다. 사용자 화면에 실제 표시된 시각은 UI 보조 지표로 구분한다.
- 완료 요청 P95와 전체 도착 기준 기한 내 완료율을 함께 보고한다. 오류·거절·만료·취소·종료 시 미완료를 숨기지 않는다.
- 단독/동시 실행의 서비스시간, cold/warm·전환, peak memory, scheduler overhead를 먼저 측정한다. 새 모델에서 측정한 CPU/GPU 우열을 사용한다.
- calibration/development/evaluation의 seed와 session을 분리한다. 입력 이미지도 가능하면 분리하고 재사용하면 해당 제한을 공시한다. 같은 도착 기록으로 정책을 대응 비교하고 순서는 block마다 무작위화한다.
- 저부하, 일반 작업 중 긴급 burst, 지속 혼합 부하를 포함한다. 열 스트레스는 선택적 별도 실험이다. 일부 조건만 골라 전체 상황에서 우수하다고 쓰지 않는다.
- deadline은 사용 요구와 실측 가능성을 함께 검토해 사전 고정한다. 사용 요구 근거가 없으면 engineering target이라고 표시한다. 성능을 본 뒤 낮은 위반율이 나오도록 deadline을 늘리지 않는다.
- 시뮬레이션은 실측으로 보정하고 별도 세션으로 검증한다. 실기기에서 측정하지 않은 OCR/통역/게임의 성능을 분류 지연에 임의 배수를 곱해 주장하지 않는다.

## 9. 단계·완료 조건·일정

현재 진행은 [팀 안내의 상태표](team/README.md)와 STATUS를 따른다. 아래09-18 일정은 이력이며 실제 완료일/현재 미구현 목록이 아니다. S26 별도 모듈 개발을 금지하던 이전 축소 조건은2026-09-24 채택 범위에서 대체됐다. S26 재현평가의 동결·품질·전체 실패 분모 요건과 A24 결과 보존은 유지한다.

일정은 안내문상 2026-10-22 17:00 KST 제출에 맞춘 내부 목표다. 공식 변경 공지는 제출 전에 다시 확인한다. 아래 단계는 실행계획이며 이번 문서 수정으로 완료되지 않는다.

| 작업 | 내부 목표 | 완료 조건 | 불충족 시 |
| --- | --- | --- | --- |
| SCOPE-02 | 09-17 완료 | `completed_with_open_gates`: 혼합 조건·합성 가정, 공식 안내/label 후보, 선행 연구·대회 적합성·선택적 시연을 근거 문서에 기록 | exact artifact/license·실기기 성능과 최근 대회 전체 중복 감사는 후속 gate; 특정 앱 수요를 입증한 것으로 쓰지 않음 |
| MODEL-02A/B | 09-18~09-23 | 분류 host PASS와 탐지 비배포 조건부 PASS; 기기 비종속 외부 manifest/seam을 고정한 뒤 A24 CPU·GPU 후보 smoke 및 품질·메모리 확인 | 배포 필요 시 exact license/NOTICE 또는 artifact 교체; GPU 미지원은 unsupported, 동적 자원 주장은 재검토 |
| TASK-02 | 09-24~09-28 | 두 실제 adapter, 독립 arrival, UI 결과·저장, 실패 포함 ledger와 validator 동작 테스트 | 단일 모델 pipeline을 다중 작업 완성으로 표시하지 않음 |
| PROFILE-02 | 09-29~10-03 | A24 단독/전환/허용 co-run full profile, thermal 연결, deadline·입력·주평가 규칙 고정 | 불안정 원인 수정; 병행은 이득 없으면 금지 |
| SCHED-02 | 10-04~10-08 | B0~B3/P 개발 비교, 구성요소 제거 비교, feasibility 판정, 평가 설정 freeze | B2/B3와 차이 없으면 복잡한 정책 확대 중단 |
| EVAL-02 | 10-09~10-13 | A24 실제 모델+합성 도착의 독립 세션 평가, 효과크기·불확실성·서비스 제약·실패 공시 | 판정 불충분 또는 고정 정책 우세로 기록 |
| XDEV-02 | 10-13~10-16 | 동결한 APK·모델·정책으로 추가 Android 기기 1대 이상 probe→축소 profile→`absolute-SLA`/`capacity-normalized` 재현평가 | 확보 기기·미지원 cell·실패를 그대로 보고하고 A24 결과를 모든 기기로 일반화하지 않음 |
| SUBMIT-02 | 10-16~10-20 | 15쪽 이내/10MB 이내 익명 PDF, 재현 자료, 학생별 기여·시연 | 미확인 효과를 기대효과 수치로 대체하지 않음 |

10월 8일까지 A24 기본 비교가 불가능하면 모델·NPU·강화학습을 추가하지 않는다. 추가 기기용 별도 기능을 만들지 않고 같은 runner와 host 도구의 이식성만 유지한다. A24 평가가 끝나기 전 추가 기기 결과로 정책을 튜닝하지 않는다. 남은 기간에는 동작하는 범위에서 결과와 제한을 정리한다. 역할은 사용근거·입력, Android·측정, 정책·분석, 통합·발표로 나누되 팀원 수에 맞춰 겸임하고 서로의 산출물을 교차 검토한다. AI가 제안한 설계·코드는 학생이 설명·검증할 수 있어야 한다.

### 2026-09-22 PC 계획 감사 amendment (현재 적용)

연구 질문은 A24 joint empirical 분포 아래 상태 기반 앱 요청 배정이 CPU-only·정적 정책보다 긴급 응답/deadline을 개선하면서 일반 완료율·makespan·throughput·메모리/열 손실을 사전 범위에 유지할 수 있는가다. 상충관계 자체는 비신규이며 현재 실측은 calibration이다. 기존 4.4 B0~B3/P는 보존하고 PC 계약은 별도 SP1 namespace를 사용한다.

목적은 epsilon-constraint 후 사전적 urgent miss/P95 순위다. 현재 offset0·분류 urgent6/탐지 normal6·고정 순서 trace는 재정렬·staggered overlap·선택적 co-run의 반사실적 서비스 모형을 제공하지 않는다. 미측정 overlap/4runtime/dynamic reload 금지를 유지하며 FIFO/urgent CPU/정적/항상 co-run/적응형을 비교할 지원 모형, adaptive estimator, 실질효과·허용 손실, workload/반복/drain, simulator hash는 미해결이다. 임의 null 해제나 과거 10%/2%p 자동 채택은 금지한다.

이번 master seed2026092201·정책과 계획의 부분 명세·원본 hash·consumed registry·host validator/no-op을 동결한다. 사용자 절대 SLA는 calibration_pending이고 기존 복수 engineering deadline의 전 후보를 보존한다. 현재 작업 완료는 audit/부분 계약 동결이며 사용자가 요청한 SIMULATION_PLAN_READY 달성은 아니다. 다음 ID는 SIM-PLAN-02-SUPPORT-DECISION: 새 측정 없이 반사실적 모형의 허용 가정/범위를 먼저 결정한다. 이후 정책 효과 실기기 확인·최소 추가 Android 한 대 재현이라는 전체 연구 계획은 남긴다.

### 2026-09-21 bounded descriptive amendment (입력 범위 유지)

사용자지시에따라 정확30세션계획을채택한다. 아래이전160/280설계는역사적기록이며실행하지않는다. Simulation v1은workload전setup·admit된resident runtime·관측dispatch/queue만허용하고dynamic unload/reload transition필수gate를제거한다. 정확cold populationP95·request90%PI·독립holdout80을요구하지않고, 실측cold/early/warm jointblock·complete5session/cell/5pair·quality/memory/thermal·관측요약/bootstrap/LOSO/sensitivity로제한한다. 성능보증을낮춰기존실패를통과시킨것이아니라주장범위를제한한새descriptive protocol이다. 이전holdout80.38%실패및원자료불변. 현재단계의추가기기일반화는주장하지않고기존연구전체의후속외부재현계획과구분한다.

### 2026-09-21 empirical protocol amendment

새 protocol의 scheduler는 PI를 사용하지 않으므로 request-level PI coverage90%를 새 SIM-01 필수 gate에서 제거한다. 기존 prediction model의 독립 holdout80.38% 실패를 취소하거나 재평가하지 않는다. 기존 holdout 및 v4 smoke는 consumed development다. 신규 v4 session joint block의 provenance·cell/state·독립 분포 drift/정밀도·paired completeness·품질·memory/thermal·deterministic replay로 대체하며 승인 기준은 신규 자료 전에 hash로 고정한다. [정확한 수치·표본수·한계](EMPIRICAL_CALIBRATION_PROTOCOL.md). 본 정책 운영성과 검증·deadline·미지원 전환 범위는 계속 gate이며 현재 SIM-01_INCOMPLETE다.

### SIM-01 준비 gate (2026-09-19 사용자 요청)

이번 실행에서 시뮬레이션 본 실험은 금지한다. `SIM_01_READY`는 MODEL-02B 기기/품질/artifact gate와 TASK-02 실제 완료 경계, PROFILE-02의 기기별 service·transition·thermal·capability 근거를 확보한 뒤 선언한다. 추가로 독립 device profile schema, workload/request class, arrival/service/deadline/thermal 입력, B0~B3/P 결정·목적·제약, seed/반복/KPI, manifest/schema/validator, no-op 검증, 저장/provenance·실행 명령이 있어야 한다. 어느 하나라도 없으면 INCOMPLETE 또는 구체 장애로 BLOCKED다. 기존 smoke 시간을 service profile로 바꾸거나 pending deadline을 임의 숫자로 채우지 않는다. 보조 simulation은 위 8절과 MULTITASK 9절의 실측 보정·holdout 조건을 유지한다.

2026-09-20 초기 준비 기록: draft simulation schema/semantic validator/no-op, seed namespace, B0~B3/P 의미·인터페이스와 host KPI 계약 테스트를 구현했다. 당시에는 decoded gate 실패로 draft를 INCOMPLETE로만 반환했다. 이후 네 cell의 decoded gate는 통과했지만, 독립 holdout·서비스 모델·deadline/메모리 계약이 미동결이므로 현재도 INCOMPLETE다. 실제 scheduler나 frozen service-profile 구현 완료를 뜻하지 않는다. 초기 절차는 [SIM_01_PREPARATION.md](SIM_01_PREPARATION.md), 현재 근거와 최소 다음 행동은 [SERVICE_MODEL_FREEZE_20260920.md](SERVICE_MODEL_FREEZE_20260920.md)를 따른다.

## 10. 성공·축소·중단 판정

성공 수치는 아직 `thresholds_pending`이다. 기존 제안인 긴급 P95 10% 이상 감소, 일반 기한 내 완료율 감소 2%p 이내는 개발 참고값으로만 보존한다. 일반 서비스의 절대 하한, 긴급 위반율의 허용 차이, 효과크기·신뢰구간 기준은 평가 전에 동결하며 결과를 보고 유리한 지표로 갈아타지 않는다.

| 관측 | 해석과 행동 |
| --- | --- |
| P가 B2와 B3 대비 긴급 서비스를 개선하고 일반·품질·안전 제약도 만족 | 적용 가능한 조건을 한정해 정책 기여 보고 |
| 긴급만 빨라지지만 일반이 사전 서비스 제약을 만족 | 유효한 서비스 우선순위 개선. 전체 효율 향상으로 과장하지 않음 |
| 일반 요청 포기·오류 증가 때문에 완료 P95만 감소 | 성공 아님 |
| B0 대비만 개선, B2/B3 대비 추가 효과 없음 | 우선순위 또는 고정 정책을 채택; 동적 자원 선택의 우수성 주장 중단 |
| 열 스로틀링은 관측되지 않았지만 대기·간섭 감소 | 스케줄링 결과로 유효; 열 개선 주장은 제외 |
| CPU-only가 모든 허용 부하에서 최선 | A24의 정적 선택·동시성 제한 결과로 축소. GPU 사용률을 목표로 하지 않음 |
| 추가 기기에서 P의 우위가 재현되지 않음 | 기기×정책 상호작용과 적용 조건을 결과로 보고하고 범용 우수성 주장 중단 |
| 추가 기기의 GPU가 unsupported/unverified | 해당 기기는 CPU/queue 정책 축소 재현만 수행하고 GPU 결과를 추정하지 않음 |
| 혼합 요청 문제의 근거·강한 기준 대비 개선·재현성 모두 부족 | 주제의 추가 개발 투입을 재검토 |

## 11. 대회에 보여줄 결과와 차별성

대회 안내문의 창의성·전공지식 활용·결과물 활용가능성에 맞춰 다음 증거를 만든다. “처음으로 CPU/GPU를 선택했다”는 주장은 하지 않는다.

| 평가 관점 | 제출물에서 보여줄 것 |
| --- | --- |
| 실제 문제·실무 적용 | 혼합 요청에서 대기·경합이 생기는 근거, 합성 패턴의 가정과 범위, 대표 시연 |
| 전공지식 | 자원 배정·기한·서비스 제약, 강한 기준정책, 대응 실험·불확실성 |
| 창의성 | 자원 단독 속도만이 아니라 동시 실행 간섭을 보고 병행 여부까지 결정한 효과 |
| 직접 구현·검증 | 동일 도착 기록의 B2/B3/P A24 실측, 실제 두 모델 결과, request ledger, 동결 정책의 추가 기기 재현 |
| 활용·확장 | task adapter 계약과 기기별 capability probe/recalibration 절차; 검증하지 않은 모델·기기 일반화 금지 |

보고서 15쪽 배분안: 1 제목·핵심 결과, 2 사용 문제, 3 실제 문제 근거, 4 기존 연구·범위, 5 의사결정 모형, 6 구현·완료 경계, 7 모델·입력·품질, 8 단독/간섭 실측, 9 정책·기준정책, 10 공정한 실험 설계, 11 긴급 결과, 12 일반 서비스·안전, 13 구성요소 제거·민감도, 14 활용·한계·학생 기여, 15 결론·참고문헌. 결과 페이지는 실제 측정값이 생긴 뒤 채운다. 소속 대학·지도교수 등 식별 표시는 제출본에서 제외한다.

주요 그림은 긴급 P95와 일반 기한 내 완료율을 함께 보여주는 정책 비교, 부하/간섭에 따른 유리한 정책 영역, 요청별 Gantt·선택 사유다. APK·raw·manifest·분석 코드는 해시와 버전으로 연결해 재현 패키지를 만든다. 원자료와 새 결과는 합치지 않는다.

## 12. 관련 근거와 주장 범위

2026-09-17 확인. 상세 조사와 주장 경계는 [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md)에 있다. 아래 자료는 기능·기존 연구의 근거이며 실제 앱의 보급률이나 D1Check의 성능 우수성을 증명하지 않는다.

- [2026년 대회 공식 페이지](https://kiie.org/Conference/ConferenceView.asp?AC=2&CODE=CI20260701&CpPage=) 및 사용자 제공 `2026년_제22회_대학생프로젝트_경진대회_안내문_및_참가신청서_0727.pdf` 1~2쪽: 실무 결과·창의성·전공지식·활용성, 표지 포함 15쪽·10MB, 학생 주도와 중복 응모 제한. 공개 공식 목록과 접근 가능한 프로그램에서 동일 제목을 확인하지 못했지만 최근 3개년 전체 출품작 감사가 아니므로 독창성이 확정된 것은 아니다.
- [Google Acceleration Service](https://developers.google.com/edge/litert/android/acceleration_service): 모델과 기기에 맞는 가속 설정 평가가 이미 존재한다. 기기별 초기 calibration 자체를 독창성으로 주장하지 않는다.
- [Sung et al., USENIX ATC 2023](https://www.usenix.org/conference/atc23/presentation/sung): 모바일 multi-instance DNN의 앱 수준 적응형 스케줄링 연구가 존재한다. 본 계획은 한 앱·A24·설명 가능한 요청 단위 정책의 재현 가능한 검증으로 범위를 제한한다. 해당 논문 대비 성능 우위를 주장하려면 별도 직접 비교가 필요하다.
- [Band, MobiSys 2022](https://doi.org/10.1145/3498361.3538948), [Pantheon, MobiSys 2024](https://lixianghan.github.io/), [CoDL, MobiSys 2022](https://doi.org/10.1145/3498361.3538932): 이종 프로세서 multi-DNN 조정, GPU preemption, operator 단위 CPU/GPU co-execution이 이미 연구됐다. D1Check는 whole-request 비선점·service-level 제약·A24 실증으로 범위를 좁히며 최초성이나 직접 성능 우위를 주장하지 않는다.
- [Android Thermal API](https://developer.android.com/games/optimize/adpf/thermal): 열 관측·부하 조절 기능과 기기별 지원 한계. thermal status 0을 스로틀링 부재의 확증으로 사용하지 않는다.

## 13. 보존하는 기존 증거와 한계

아래는 기존 감사에 기록된 결과다. 이번 개정에서 원시자료를 재분석하지 않았으며 새 두 작업의 성능으로 전용하지 않는다.

| 증거 | 확인한 내용 | 아직 주장할 수 없는 내용 |
| --- | --- | --- |
| A24 formal 80슬롯 | CPU 중앙 지연 약 41.2 ms, GPU 약 131.6 ms, GPU/CPU 약 3.196. CPU 1/2/4 스레드 차이는 매우 작고 위치 변경 민감도 검사에서도 CPU 우세 방향 유지 | 모든 모델·부하에서 CPU가 우세하다는 일반화. 위치·주변온도 영향 제거 |
| S26 formal 80슬롯 | 원시자료 감사와 지연 재계산 통과. GPU가 pooled CPU보다 duty별 약 1.062~1.201배 빠르고 20개 block-duty 대응 비교 모두 GPU 우세. 모든 GPU run은 31/31 노드 full delegation, fallback 없음 | compatibility-list override 없는 결과로 일반화. 측정 APK와 Git 소스의 완전한 cryptographic binding |
| 기기 간 입력·설정 기록 | 모델, LiteRT 1.4.2, strict profile 설정, 대표 텐서 내용·전처리·라벨 해시 일치 | 두 기기의 전체 실험 계약과 소스가 완전히 동일하다는 주장 |
| 온도 | S26의 20개 block-duty 대응 비교에서 GPU AP 온도 상승이 모두 더 낮게 관측됨 | 동일 완료량에서 더 효율적임, 에너지 절감, 기기 간 AP 센서의 직접 동등성 |
| diagnostic v2 | trace-off/on 실기기 경로 확인. trace에서 sched 및 gpu_frequency 표본 확인 | GPU 내부 실행시간, fence, H2D/D2H 분해, 실제 FP32/FP16 확인 |
| CPU 설정 | CPU1/2/4 조건에서 뚜렷한 속도 이득이 관측되지 않음 | 실제 worker 수 또는 스레드 증가 효과에 대한 인과 결론 |

추가 주의사항:

- 대표 텐서셋은 정확도 preflight 입력이다. 실제 timed load 입력이 대표 이미지라고 가정하지 않는다. 새 요청 실험에서는 사용한 입력 바이트·생성 방식과 정확도 검사 입력을 구분하여 기록한다.
- A24 warm-up 설정은 5, S26 보고서 표기는 20 s이다. 원본 명령과 코드로 값의 단위·적용 위치를 확인하고 새 비교에서는 통일한다.
- S26은 `gpu_compatibility_list_supported=false`, `formal_gpu_compat_list_override=true`였다. compatibility-list override 사실을 모든 비교 결과에 공시한다.
- S26의 tensor container 해시는 A24와 다르다. 기록된 텐서 내용 해시는 같지만 컨테이너 차이를 직접 검증하지는 않았다.
- S26 `dataset_manifest`의 accuracy/pilot 문구는 수정이 필요하다. 원본은 보존하고 수정 설명 또는 새 export로 정정한다.
- A24의 약 22·72번째 장소 이동, 재시도와 실제 duty 차이는 기존 분석의 제한으로 유지한다.
- 실제 FP32/FP16 하드웨어 실행 여부는 unknown이다. GPU 내부 H2D/GPU/D2H 및 fence timing도 확보되지 않았다.
- 에너지 단위가 검증되지 않았으므로 J/mWh와 에너지 절감률을 사용하지 않는다.
- 측정 당시 설치 APK와 Git 소스의 완전한 cryptographic binding이 부족하다.
- S26 재시도 raw run 하나는 failure 기록이 불완전하다.
- 기존 formal 데이터, diagnostic v2 trace-off, trace-on, 새 스케줄러 실험을 서로 구분한다. 프로토콜 변경 자료를 동일 반복으로 합치지 않는다.

CALIB-01B는 FIX4까지 구현·host 검증·감사를 완료했다. 기록상 Kotlin/JVM 119건·실패/오류/skip 0, Python 195건·실패/오류 0·기존 skip 1, lint error 0/warning 76, compileall·logger self-test·assembleDebug PASS다. 기존 모델의 실기기 이미지 calibration, 새 두 모델 지원, 동적 정책 개선은 각각 미완료이며 별도로 검증한다.

2026-09-20 후속: [DECODE_RESOLUTION_20260920.md](DECODE_RESOLUTION_20260920.md)의 최초 종료는 연결 단절로 BLOCKED_EXTERNAL_INPUT이었다. 이후 [재개 결과](A24_RESUME_20260920.md)에서 최종 APK 설치·네 cell·bounded PROFILE-02를 실제 검증했다. 31개 실기기 session과 별도 host preflight 실패1건을 보존한다. 두 작업 모두 solo CPU가 빠르며, 분류 CPU 초기 호출의 큰 서비스 오차를 cold boolean만으로 설명할 수 없어 frozen profile로 승격하지 않았다. 개정4.4의 품질/profile/holdout/동결 완료 조건은 유지하고 SIM-01_INCOMPLETE다. 본 simulation·formal·정책 비교는 미실행이다.

2026-09-20 SERVICE-MODEL-FREEZE: [후속 분석](SERVICE_MODEL_FREEZE_20260920.md)에서 calibration24/과거 holdout4/사후 진단1 session을 분리하고 seed20260920, 새 prospective acceptance, 6후보와 공통 입력 준비 schema/validator/no-op을 기록했다. 이미 본 자료를 독립 holdout으로 재사용하지 않는다. backend equivalence와 절대 accuracy는 분리하며, 최신 사용자 지시대로 실제 정확도를 임의 생성하지 않고 검증된 cell의 출력 품질 보존을 scheduling 제약으로 사용한다. A24 solo CPU 우세를 반영하되 GPU 전체 지배는 미입증이다. 미검증 co-run/thermal/memory/deadline을 동결한 것으로 취급하지 않는다. 새 독립 검증이 없고 coverage도 미달이므로 frozen model은 발행하지 않았다.


## 2026-09-23 추가 작업: ARRIVAL-FIXED-01

현재 후속 질문은 같은 신규 paired workload에서 조건부 선택이 **기존 고정 분리(urgent CPU/normal GPU)**보다 어떤 조건·지표에 유리한지이다. [별도 설계](ARRIVAL_FIXED_SPLIT_COMPARISON_20260923.md)에 따라 CPU_URGENT/FIXED_SPLIT/CONDITIONAL을 burst·low·queue에서 함께 측정한다. 기존 주 평가 FAIL·10% 최소효과·동결 simulation/formal 계약은 그대로다.
PC 준비 완료, 새 실측 미실행. 각 조건3 block/27세션·162요청·216warmup 최소안 권장; 각6 block/54세션·324요청·432warmup 정밀안은 대안이다. retry/대체/추가0, 새 예산 별도 승인 전 ADB/설치/측정 금지. margin 없는 효과 추정 연구이며 고정 대비 분산·검정력·동등성은 아직 미확인이다. 주 비교·지표·CI/누락/중단 규칙과 실제 명령은 새 계약을 따른다.
완료 조건: 정확한 정책 감사, 동일 runtime/도착·seed·순서·예산의 새 manifest, PC 테스트/dry-run, 보존 검증, 실행 가능한 승인안·재개 문서. 위 PC 조건은 완료, 실기기 검증은 다음 승인 단계다.


2026-09-23 실행 후 갱신: 최소27세션안 승인 후24시도/23완료에서 무선 ADB 연결이 단절되어 동결 규칙대로 종료했다. 실패는24번째 FIXED_SPLIT burst 세션의 Activity 실행 전 thermal 확인이다. retry/대체/추가0, 재연결 후 cleanup만 완료했다. 142평가요청·184warmup 실행, 계획162/216 중 미실행분 보존. [부분 결과](ARRIVAL_FIXED_SPLIT_RESULTS_20260923.md)는 burst C−F 완전2pair의 urgent +72.27%/normal−61.69% 상충을 기술하되 주 CI/전체 평가 완료를 주장하지 않는다. 새 정책/성공 기준 변경 없음. 추가 실측은 별도 계획·승인 필요이며 남은 예산으로 이번 run을 자동 재개하지 않는다.

## 2026-09-24 추가 작업: ARRIVAL-TIMING-DEV-01

현재 목표는 CONDITIONAL의 시간 경계·잔여 추정·판단 재현 보완이다. [별도 개발 계약](ARRIVAL_TIMING_DEV_20260924.md)의 새 protocol/ID로만 구현하고 기존 B3/P 정의·기존 정책·동결 결과를 소급 변경하지 않는다. 이번 산출물은 완전한 B3/P나 성능 개선 검증이 아니다. 간섭·EDF/aging·Band 이식은 범위 밖이다.

완료 조건: dispatch/실행/host inference/output/persist/worker release/실제 scheduler availability 구분, 관측 당시 입력과 null 결정을 포함한 bounded trace, phase별 추정/UNKNOWN 처리, 위험 시나리오의 관련 PC 테스트, 후속 질문과 미확정 설정 공개. 설계·최소 구현·PC 검증은 완료했다. 네 cell×5구간 budget은 null이며 실기기 검증/실험 READY는 미완료다. 이후 별도 시간 경계 보정 계획·예산 판단부터 진행하며 기존 중단 run을 이어 실행하지 않는다.

## 2026-09-24 추가 작업: ARRIVAL-TIMING-CAL-01

후속 상태: CAL-01은 설치 서명 불일치로 phase 소비·중단됐다(세션0). [CAL-02 복구 후보](APK_SIGNING_RECOVERY_20260924.md)는 기존 키로 동일 바이너리를 별도 재서명하고 설치·phase 소비 전 서명 검사를 추가한다. 기존 연구 질문/예산 구조/관측 계약은 동일하나 새 APK·실험 ID·세션/registry·출력으로 분리하며 실행 승인은 별도 대기다. 앱 삭제/데이터 초기화나 기존 계획 재실행으로 우회하지 않는다.

CAL-02 후속: 승인 후 업데이트 설치는 성공했으나 첫 세션 필수 기록 누락으로 종료했다. 세션1/16·완료0·미시도15, 실제 요청/warmup 호출 수 미확인, fit/확인 단계 미실행. [종료 보고](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md). 위 후보/승인 대기는 과거 상태이고 현재는 중단·재실행 금지다. 서명 호환성과 시간 경계 실측 검증을 구분하며 PC 원인 진단이 다음 단계다.

실제 시간 경계 보정의 첫 단계로 **추정값 없는 고정 backend 단독 진단**을 분리한다. task/backend/priority8조건, persist_all, 네 runtime resident·각2warmup·CPU thread1을 유지한다. 기존20 budget을 사후 의미 변경하지 않고 별도 관측 v2의40슬롯과 응답/lane 목적별 N/A를 기록한다. 고정 진단의 판단 비용은 적응형 판단 비용의 대체가 아니며 null/UNKNOWN·실험 준비 미완료는 유지한다.

PC 완료 조건은 calibration 전용 경로, 기존 정책/자료 호환, 성공·실패·null 호출/worker release·실제 callback 계측, 소비/중단/재시도 차단, APK 격리 패키징·새 plan/manifest·dry-run·문서다. 제안은 개발8+확인8세션·64진단요청·128warmup, retry/대체/추가0이다. fit은 한 개발 session/조건의 중앙값·범위만 기술하고 freeze 후 새 확인 session의 오차를 보고한다. 이 작은 예산으로 정밀도/검정력/tail·P 우수성을 주장하지 않는다. 이번에 기기 실행하지 않으며 기존 fixed-split 미시도분과 합치지 않는다.

## 2026-09-27 ENERGY-AP-STATE-COLLECT-03 — 별도 미승인 모형 수집 후보

발열·배터리·응답이라는 최종 목표는 유지한다. 새 정책/강화학습은 보류하고 A24 현재 두 모델의 기기 전체 J와 AP 경로를 먼저 보정·확인한다. [별도 계약](ENERGY_AP_STATE_COLLECTION_PREP_20260927.md)에 따라 기존 4세션/144분 산술 후보 대신 CC_DG·CG_DC·탐지 CPU＋GPU의 개발3→동결→확인3을 PC에서 준비했다. 동일 250ms 반복 구간의 전력·AP 전환까지만 식별하며 임의 도착·요청별 순간 비용·정책 절감은 미검증이다. 전체 상한 230분/추론 최대 10,152회는 **제안 예산**이며 실행 승인이 아니다. Android/host/분석/계획/서명 APK/PC dry-run 준비 완료, ADB·설치·실측 0. 이후 기기 gate와 독립 확인 오차가 실제로 확보되기 전 `experiment_ready=false`와 과거 FAIL/동결값을 유지한다.

2026-09-27 후속: 위 예산의 plan_v3 실행은 사용자가 승인했으나 [실행 전 gate](ENERGY_AP_STATE_COLLECTION_PREFLIGHT_20260927.md)에서 `adb devices -l`의 연결 기기가 0대였다. serial/fingerprint를 확인할 수 없어 `Run`을 시작하지 않았다. 이 착수 시도에서 세션·추론·설치 소비는 0이며 동결·확인도 없다. 과거의 “미승인 후보” 기록은 준비 당시 상태로 보존한다. 같은 턴에서 자동 재연결·재실행하지 않고 A24 연결 및 현재 gate 확인을 기다린다.

연결 복구 뒤 같은 plan_v3의 실행은 승인 범위에서 한 번 시작했으나 [결과 보고](ENERGY_AP_STATE_COLLECT03_RESULTS_20260927.md)와 같이 APK 전송 client 120초 timeout으로 `stopped_no_resume`가 됐다. 전송 1회 시도, 설치·세션·추론·동결·확인 0이다. 기존 소비 registry를 초기화하지 않는다. [PC 전송 진단·별도 배포 복구안](ENERGY_AP_DEPLOY_RECOVERY_PC_20260927.md)은 이전 복구기의 단계형 전송/해시/설치를 재사용했다. 이 새 ID의 [승인 실행](ENERGY_AP_DEPLOY_RECOVERY_RESULTS_20260927.md)도 무선 후보 push 1회가 120초 timeout되어 원격 hash·설치·수집 없이 `stopped_no_resume`로 종료됐다. 기존 설치본 pull 1회와 실패 후 기존 설치본 해시는 확인됐으나 원격 진행량과 지연 원인은 미확정이다. 두 종료 계획을 재개하지 않으며, 이후 전송 진단·배포·수집은 각각 별도 ID·예산·승인으로 판단한다. 에너지·AP 모형 계수와 검증 상태는 이전 그대로다.
## 2026-09-29 최소 도착 확인의 실행 전 gate

[PC 설계·차단 판정](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md)에 따라 기존 queue 24요청/FIXED_SPLIT과 공통120초를 하나의 후보 입력으로 고정했다. 시작 AP 개발 범위32.5–34.0°C, 실제 공통창 시작과의 시각 일치가 필수다. 현 Android arrival 앱은 numeric AP를 읽지 못하고 resident baseline 후 즉시 작업을 시작한다. 준비 중 host 온도 gate나 사후 신선 표본을 실행 gate로 대체하지 않는다. 현재 입력은 `PC_INPUT_FIXED_RUN_BLOCKED`이며 별도 실측 ID·예산·승인 후 Run은 아직 없다. 먼저 실제 시작 경계에서 작업0회 중단을 보장하는 최소 경로와 계측 프로토콜 영향을 PC에서 해결한다. 기존 동결 모형의 임의 도착 strict 지원은 확대하지 않고 A(관측 일정 조건부 비용)와 B(예정 도착부터의 종단간 일정/비용)를 분리해 후속 평가한다.
## 2026-09-29 시작 AP 기능 후속 구현 완료

사용자 후속 범위에 따라 실제 arrival 경로에 opt-in 1회 시작 승인/앱 최종 freshness 검사/30초 실패 종료를 구현했다. [계측 비용과24요청 완료 기준](ENERGY_AP_ARRIVAL_CONFIRMATION_PC_20260929.md)을 고정했다. 시작 전 최대5 ADB 명령 의존을 명시하며 부하 중 handshake는 추가하지 않았다. 서명 APK·실기기·새 계획 예산은 미완료로 남기고 과거 차단 계획을 실행하지 않는다.
