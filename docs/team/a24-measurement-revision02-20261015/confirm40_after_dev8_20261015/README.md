# 새 독립 확인 40회 — 응답·AP 범위 동결

사용자는 총상한 81회(기존 33 + 새 DEV 8 + 새 CONFIRM 40)와 **에너지 J 미판정 상태의 응답·AP 확인 진행, 계측 원인 진단 병행**을 승인했다. 기존 확인 자료는 합산하지 않는다. 새 확인은 별도 5블록 × 8군, 예정 5,720요청이다. DEV를 확인 자료로 재분류하지 않는다.

현재 방문에서는 등록 순서 첫 M128 네 군만 ORDER → WAIT200 → PAIR_G → BASE로 진행한다. 시간창은 기존 2026-10-15 14:08:25~16:38:25 KST를 유지하고 기기 명령은 16:33:25까지다. 새 APP에는 21분, MAIN에는 5분의 여유가 필요하다. 시간·냉각 조건 때문에 뒤 군을 시작할 수 없으면 미시작으로 남긴다. 실패·중단을 같은 ID로 재실행하지 않으며 확인 40회를 줄이거나 예산을 초기화하지 않는다.

## 무엇을 동결했는가

- [계획](plan.json): 새 40개 ID·전체 순서·요청 은행·seed를 결과 전에 고정했다. 첫 방문 네 ID는 [시간창](USER_WINDOW.json)에 제한한다.
- [분석](ANALYSIS_CONTRACT.json), [예측 부재 선언](PRE_MEASUREMENT_PREDICTIONS.json), [확인 동결](CONFIRM_FREEZE.json), [예산](BUDGET.json), [실행 계약](EXECUTION_CONTRACT.json).
- 기한 C=2.2초/D=5초, 관측·응답·실제 worker 반환·원 APK와 요청 의미를 유지한다. 검증 J, 실제 표면온도, 근거 없는 온도 초과 시간은 null이다. 독립 확인으로 숫자 예측 정확도가 검증되는 것은 아니다.
- 자료·완료·기한 분모와 시작 AP 차이를 함께 보고한다. 블록 5개가 모이기 전 신뢰구간이나 전체 확인 완료를 주장하지 않는다. 이번 결과로 정책을 조정하지 않는다.

## DEV 검증과 버전 경계

DEV 8군은 실제 1,144요청 완료·출력 PASS, 64회 준비 추론을 포함해 총 1,208회 추론을 수행했다. 실제 GPU 첫 군은 177파일 버전, 나머지 7군은 기존 177파일을 그대로 둔 179파일 버전이다. 준비 전 냉각만 별도 두 파일에서 수정했으며 APK·MAIN gate·요청·정책은 같다. [실제 기능 근거](FUNCTIONAL_EVIDENCE.json)는 각 군의 실제 source SHA를 구분한다. 모든 군이 동일한 전체 host 버전에서 직접 실행됐다고 주장하지 않는다. [추가 호환 검산](SOURCE_COMPATIBILITY_PC_AUDIT.json)은 PC 증거이며 별도 실기기 재검증이 아니다.

새 확인 coordinator는 기존 179파일 핵심을 변경하지 않는 별도 진입점이다. 정확한 SHA를 실행 계약과 PC 증거에 추가 결합했다. 40개 전체 승인 결합 검산과 실제 앱 parser의 40개 설정 검증을 PC에서 수행한다. 이것을 새 coordinator 실기기 통과로 선기록하지 않는다. 첫 방문 root는 한 번만 생성되며 존재하면 실행을 거절한다. 다음 방문은 남은 ID·전역 소비 원장·기준 이관을 다시 결합해야 하므로 현재 첫 방문 명령을 재사용하면 안 된다.

실행은 로컬 private job에만 기기 등록·입력·APK 경로가 들어간다. 명령은 아래와 같지만, 이미 실행된 첫 방문에는 다시 사용하지 않는다.

```powershell
python -B tools/d1_a24_confirm_registered_window.py output/a24_confirmation40_frozen_window01_20261015/job.json
# 실행 전 상태·시간창·미소비 ID 확인이 끝난 최초 방문에만:
python -B tools/d1_a24_confirm_registered_window.py output/a24_confirmation40_frozen_window01_20261015/job.json --execute-authorized
```

원물은 로컬 Documents의 `A24R02C1`, 메타는 `output/a24_confirmation40_frozen_window01_20261015`다. 원장/실제 APP/START/회수로 소비를 집계한다. 확인 전 기존 41시도/81, 새 확인 0/40이었다. 에너지 문제 해결 완료나 프로젝트 전체 완료를 뜻하지 않으며 `experiment_ready=false`를 유지한다.
