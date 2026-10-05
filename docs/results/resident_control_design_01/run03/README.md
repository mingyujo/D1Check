# Resident 대조 실행03 — 완료, 기술적 관측

[결과 화면](index.html) · [한국어 보고서와 재현 명령](../../../RESIDENT_CONTROL_RUN03_20261001.md).

- summary.json: 고정창 수치와 소비, strict=false/정확도 null.
- windows.csv: 고정창 J/W/AP, 결측 및 적격성; 빈 셀은 null이다.
- paths.csv: 관측 W/AP와 두 arm 동결식 진단 누적 J. energy_boundary는 적분 경계이며 센서 표본이 아니다.
- states.csv/partial_load_lanes.csv: 실제 lane 해제 기반 상태·시간.
- observed.png/svg: 기술적 관측과 외삽 에너지 진단; AP 예측이나 정책 우월성 그림 아님.
- verification.json: 원본/실행 소스/동결 해시 보존·4 PC 검사·CSV 일치.

조건당1세션·C→L 고정 순서. 부하 전 전력과 환경이 다르므로 차이를 인과효과로 사용하지 않는다. L 냉각후기 끝 결측은 원래 창 그대로 null이다. 원자료는 외부 energy_ap_resident_control_run_v3에 보존하며 이 공유 폴더는 원자료를 대체하지 않는다. 후보 적합·추가 실측 없음, experiment_ready=false.
