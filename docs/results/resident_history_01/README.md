# 유휴 시간·이력 PC 판독 — 새 후보 미채택

[한국어 보고서](../../RESIDENT_IDLE_HISTORY_PC_20261001.md) · [화면](index.html).

- contract.json: 새 계산 전 고정한 창·분석 경계. 실행 계획/소비 기록이 아니다.
- inputs.json: 기존4세션＋완료 C/L2세션의 상대시간 전류/전압·resident/active·AP·실제 상태와 출처 해시. 개인 기기 식별정보/모델 바이너리 없음.
- readout/fixed_windows.csv: 유휴/전체 고정창의 적격성과 전력/AP. 빈 셀은 null이다.
- readout/idle_bins.csv, idle_bin_summary.csv, idle_history.png/svg: 상관된10초 기술적 집계, 독립 반복/보편 오차 한도 아님.
- readout/existing_candidate_scores.csv: 변경 없는 기존 prefix 가산식의 사후 점수.5loaded 중2개선/3악화. 후보 전체120초 값/정책 순위 없음.
- readout/summary.json/simulation_scope: 관측 재생·동결식 외삽·동적 J/AP 미판정 구분.
- verification.json: 실제 CLI 포함6PC검사·기존 결과/원문/두freeze 불변.

외부 원자료 없이 저장소 루트에서:

```powershell
python -X utf8 -B -m tools.d1_resident_history_analysis analyze --bundle docs/results/resident_history_01/inputs.json --contract docs/results/resident_history_01/contract.json --output '<새 PC 출력 폴더>'
python -X utf8 -B -m unittest tools.test_d1_resident_history_analysis -v
```

기존 출력 덮어쓰기 차단. AP/W 미래값을 후보 예측 입력으로 넣지 않음. 이전 개발/확인 역할은 원래 기록에 보존되지만 이번 분석은 모든 결과를 본 뒤의 사후 판독이다. 기기/빌드/추가 모형적합0, experiment_ready=false.
