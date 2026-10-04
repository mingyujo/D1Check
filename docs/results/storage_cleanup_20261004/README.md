# 외부 저장 공간 정리 — 2026-10-04

기준 HEAD `59a47b5`. 사용자 요청에 따라 D1Check_Arrival_Extension의 재생성 가능한 빌드 중간물만 삭제했다.

| 항목 | 결과 |
|---|---|
| 정리 전 파일 크기 합계 | 25,966,029,197바이트 / 24.18GiB / 666,428파일 |
| 가장 큰 폴더 | ente_baseline_build_pc_v1: 6,854,018,309바이트 / 6.38GiB |
| 삭제 | 162디렉터리 / 7,754,552,262바이트 / 7.22GiB |
| C: 여유 공간 | 최초7.47GiB → 검증 시14.32GiB |
| 보존 해시 검사 | 최종 APK34개 포함294파일 SHA-256 일치 |
| 삭제 대상 잔존 | 0 |

Ente 폴더는 Rust target 약2.51GiB, Cargo registry 약1.60GiB와 Flutter/Rust 도구를 포함했다. 나머지 용량은 버전별 Android 빌드와 다수 실측·분석·계획 기록의 누적이다.

삭제 범위는 허용 목록으로 지정한 Android 빌드 모듈의 intermediates/tmp/kotlin과 Ente upstream/rust/target이다. 소스·잠금 파일로 재생성할 수 있으나 다음 빌드에서 다시 컴파일해야 한다. 최종 APK·outputs·reports·test-results, 원자료·실패·동결 모형·계획·소비 registry·키·도구 설치본은 삭제하지 않았다. 다른 worktree와 사용자 HTML도 보존했다.

실제 C: 여유는 8,019,218,432 → 15,372,414,976바이트다. 논리 파일 크기 합계와 실제 디스크 확보량은 다르며, 다른 프로세스의 공간 사용도 영향을 준다.

## 검증과 기록

실행 중 컴파일 프로세스 부재, 절대 경로/허용 목록/재분석 지점 검사 후 PowerShell Remove-Item -LiteralPath로 삭제했다. Windows 긴 경로와 PowerShell JSON 배열 처리 오류는 삭제 전 검증에서 차단됐고 명시적 경로 처리를 수정한 뒤 진행했다. 이전 턴의 자동 삭제 거부 기록은 당시 사실로 보존한다. 이번 사용자 정리 요청 후 삭제는 성공했다.

상세 스크립트·후보·크기·보존 해시·receipt·verification.json:
`C:/Users/LG/Documents/D1Check_Arrival_Extension/storage_cleanup_pc_20261004_v1/`

cleanup_receipt.json과 cleanup_receipt_extra.json에 실제 삭제를 기록했다. 해당 스크립트는 재실행 계획이 아니다. 공유 요약은 summary.json이다.

기기 명령·실측·APK 빌드0. 정책·모형·strict·experiment_ready=false 불변. 다음 작업은 에너지·열을 실제 선택 기준에 연결하는 정책 후보 정의이며 Ente 빌드나 실측을 자동 재개하지 않는다.
