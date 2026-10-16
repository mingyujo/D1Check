# SIM-MODEL-V2-01-ARRIVAL-HOST-REPAIR-01

2026-10-10 19:50 KST. 기존 사용자 새 모형·필요 실측 진행 지시 안의 PC 수집기 수정이다. 원 실행과 cleanup 수정 실행의 stopped 기록을 보존한다.

## 원인과 남은 실행

회복 실측 개발4와 확인2는 자료 적격성을 통과했다. CPU 도착 실행은 `arrival.poll`이 요구하는 `budget.adb_commands` 별칭 누락으로 첫 poll에서 KeyError가 났다. 원 실패 prefix는 runtime 시작2/반환1, warmup 시작0/반환0, 본작업 시작0/반환0이며 누락 구간은 성공으로 보지 않는다. warmup 승인은 전달되지 않았고 host cleanup은 완료됐다. 이 시도는 확인 자료에 포함하지 않는다.

수정은 기존 종료 계획 재개가 아니라 별도 ID/UUID와 미소비 경로의 CPU/PAR 각96 요청 실행이다. 완료된6 자료는 원 파일 바이트/해시를 그대로 복사하며, 개발 동결 파일도 그대로 사용한다. 새 fitting0, 확인 결과를 반영한 모형/기한/입력/창 변경0이다. 동일 APK2067aac0을 설치 전 점검하고 새 APK 설치는 하지 않는다.

## 한도와 명시적 변경

원 물리 실행 상한8은 PC 오류 시도1 때문에 총9로 개정한다. 원8회 준수를 주장하지 않는다. 기존6 계측＋실패1＋새2가9회다. 원 최초 clock16670초와 명시추론7768/ADB29448 전역 상한은 보존한다. 실패 시도의 추론 상한108(본작업96/warmup8/적격성0 및 runtime4별도)은 소비 불명 상한으로 별도 기록한다. 실제 확인은 durable prefix만 사용한다.

새 실행 상한은 본작업192＋warmup16=208, runtime8, staging2/14파일, installed host pull1, APK transfer/install0이다. 설치 점검600＋2×(stage120＋launch20＋poll485＋회수60＋cleanup45＋검증35)＋간격90＋분석600=2820초이며 원 clock 잔여와 작은 쪽을 적용한다. 정상ADB슬롯2952, 종료예약포함3052이며 prior9652와 합쳐도 전역상한 이하다. 완료한 자료의 본작업/적격성/warmup 실제 소비와 실패 upper＋새208이7768 이내인지 실행 전에 검사한다.

실측 오류와 원 cleanup 실패1을 모두 공개한다. 새 확인 뒤 재보정·threshold 선택·기본/RL 자동 채택은 하지 않는다. 모든 실패/전체도착/기한 내 성공/P95를 함께 보고하고 experiment_ready=false를 유지한다.
