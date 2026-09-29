# queue/201/B2 저장 dispatch 재생 입력

**최신 결과:** [numeric AP 관측 plan_v6 승인 1회 결과](../../ARRIVAL_RECORDED_B2_AP_OBSERVE_RUN01_20260929.md)는 24요청과 공통120초를 완료했다. [작은 CSV·그림](diag_v6/README.md)의 동결식 J/AP 계산은 시작 AP29.9°C와 짧은 전환 때문에 **외삽 진단**이다. 아래 PC 준비와 v3/v4 중단 설명은 그 당시 계약·상태 기록으로 남긴다.

[AP 관측 진단 v2의 PC 계약·새 미승인 계획](../../ARRIVAL_RECORDED_B2_AP_OBSERVE_PC_20260929.md)은 개발 시작 범위와 실행 적격성을 분리한다. [v2 판독 계약](diagnostic_analysis_contract_v2.json)은 범위 밖 수치가 계산돼도 외삽 진단으로만 표시한다. 기기 실행 결과는 아직 없다. 아래 v3/v4 중단과 기존 분석 계약은 보존한다.

별도 [새 lifecycle APK 재생 plan_v4의 결과](../../ARRIVAL_RECORDED_B2_REPLAY_RUN02_20260929.md)는 시작 AP **28.8°C**가 고정 범위 32.5–34.0°C 밖이라 본 요청 전 gate 중단이다. [작은 요약](run02_summary.json)의 J/AP `null`은 공통창 미진입을 뜻한다. plan_v3의 lifecycle 중단과 합치지 않으며 두 계획 모두 소비·종료됐다.

이 폴더는 **PC에서 고정한 실행 입력과 판독 계약**이다. [준비 계약](../../ARRIVAL_RECORDED_B2_REPLAY_PC_20260929.md), [승인 1회 중단 결과](../../ARRIVAL_RECORDED_B2_REPLAY_RUN01_20260929.md), [통합 대시보드](../arrival_policy_screen_01/dashboard.html)를 구분해 읽는다.

`run01_summary.json`은 외부 원본 receipt·진단 archive에서 만든 작은 파생 요약이다. runtime4·warmup8 뒤 resident baseline에서 lifecycle 취소됐고 공식 120초 창은 열리지 않았다. 실제 B2 일정·J·AP 오차는 **없음/null**이다. 원본 계획은 소비·종료됐으며 아래 `Check`는 더는 성공하는 재실행 절차가 아니다.

- `source_schedule.json`: 기존 `timeline.csv`의 `explore/queue/B2_PC/seed201` 24개 요청, 실현 간섭1.5, 기록 dispatch를 실행 허용 하한으로 전환한 입력. PC 출력/완료시각은 **출처 메타데이터**이며 기기 시간을 강제로 맞추지 않는다. 저장 `occupancy_segments.csv`의 49개 상태 구간과 일치한다.
- `analysis_contract.json`: 120초 조건부 J/AP 오차와 결측·지원 밖 처리, 연구 해석 경계.
- 기존 동결 파일은 외부 `energy_ap_state_run_v5/development_freeze.json` SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`; 저장소에 복사하지 않는다.

코드만 검증하는 기기 명령 없는 PC 검사:

```powershell
python -B -m unittest tools.test_d1_arrival_recorded_replay -v
```

APK와 원본 모델·입력은 저작권·크기 때문에 포함하지 않는다. 외부 계획은 `source_files` 6개, `references` 4개, 프로젝트 서명 APK와 검사 도구 및 동결 모형을 해시로 고정했다. 계획은 **`stopped_no_resume`**, 기존 FAIL·동결 모형과 `experiment_ready=false`는 그대로다.
