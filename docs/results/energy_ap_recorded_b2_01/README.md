# queue/201/B2 저장 dispatch 재생 입력

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
