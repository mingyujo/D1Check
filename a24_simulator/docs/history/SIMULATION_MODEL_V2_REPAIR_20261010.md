# SIM-MODEL-V2-01-CLEANUP-REPAIR-01 — 종료 경합 수정과 남은 측정

2026-10-10. 기존 새모형/필요실측 진행 지시 범위의 구현 오류 수정이다. 원 Run/계획은 stopped_no_resume로 보존하며 재개하지 않는다. [원 사전 계획](SIMULATION_MODEL_V2_PLAN_20261010.md).

## 원 실패와 계측 판독

첫 개발A는 본작업863＋적격성4＋warmup8=875추론을 수행했다. runtime4, 본작업/적격성 request_start와 lane_available는 각각 총867개로 전수 대응한다. 공통 종료/냉각 종료/summary completed/cleanup completed 뒤 sampler가 닫힌 journal에 기록했다. sampler_failure 시각은 cleanup receipt보다21.823ms 뒤다. 앱 실패 파일과 원 stopped receipt는 그대로 보존한다. 앱 lifecycle PASS를 주지 않는다.

원 코드 samples.shutdownNow()는 이미 실행 중인 snapshot의 종료를 기다리지 않았다. 최소 수정은 sampler의 실제 종료를 최대3초 확인한 다음 runtime/journal을 닫는 것이다. 추론/부하/샘플 주기/초기 gate/요청/품질/지원/모형 수식은 바꾸지 않는다. 관련 실제 스레드 회귀/JVM 검증과 격리 APK 빌드·기존 프로젝트 서명 확인을 수행한다.

동일 첫 세션의 **계측 구간만** 별도 재판독한다. 예외가 정확히 sampler_snapshot_or_event/cleanup/journal closed 뒤이며, cleanup 이전 전체 실행·AP/전력 coverage·출력 품질·순서·시각 검사를 모두 통과할 때만 `eligible_measured_window_with_post_cleanup_failure`로 사용한다. `application_lifecycle_pass=false`와 원예외를 결과에 남긴다. 오류 파일 삭제/원 receipt 정정/첫 실측 반복은 없다.

## 새 단일사용 계획

- 첫 슬롯은 해당 원본/manifest/전파일 hash를 보존한 계측자료 재사용이다. 개발B/B/A3＋확인 회복A/B2＋확인CPU/PAR96각1=새7세션만 실행한다. 개발4자료가 모이면 같은 고정family 4LOSO＋최종1을 동결한다. 새 확인 후 재적합은 없다.
- 새로운 APK/manifest/실험ID/registry/output을 사용한다. 원APK와 새APK의 차이는 종료 경합 수정이며 데이터에는 APK별 프로토콜 차이를 표시한다. 데이터보존 업데이트 설치는 누적2회가 된다. 이는 오류 수정에 필요한 설치 추가이며 최초1회 약속을 지켰다고 보고하지 않는다.
- 새 본작업≤6432＋적격성20＋warmup56=명시추론≤6508, runtime28/staging7·49파일. 원 첫 세션을 포함한 총 물리 시도는8을 넘기지 않으며 원 허용 추론 상한7768 안에서 판독한다. 재사용 복사는 물리 실측으로 세지 않는다.
- 새 고정 관측4410초(73분30초), 준비600초/세션간630초. 새 host 예약14890초는 **원 claimed checkpoint의 monotonic＋16670초−1초**로 더 강하게 제한한다. 수리/빌드/대기/재판독 시간을 포함해 원 clock을 초기화하지 않는다. ADB 새상한25792/정상25442, 원소비1653을 더한27445는 원29448 이하이다.
- 환경/품질/숫자AP/20%/비충전/thermal0/900ms/기존화면 기준을 유지한다. 새 오류가 나면 원인과 소비를 기록한다. 센서 오류·관측 창·기한을 유리하게 바꾸지 않는다.

## 주장 경계

최종 자료는 정상 lifecycle7와 원 종료 실패 계측1의 혼합일 수 있다. 이를8개의 lifecycle PASS/동일 APK 검증으로 쓰지 않는다. 모형 개발·별도 확인과 실제 정책 우월성/모형 기본 채택은 분리하며 strict/experiment_ready=false를 유지한다. 원자료와 실패, 기존 STATUS의 사용자 부분과 다른 작업을 보존한다.
