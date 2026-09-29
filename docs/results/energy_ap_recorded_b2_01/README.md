# queue/201/B2 저장 dispatch 재생 입력

이 폴더는 **PC에서 고정한 실행 입력과 판독 계약**이다. 기기 결과가 아니다. [상세 보고서](../../ARRIVAL_RECORDED_B2_REPLAY_PC_20260929.md)와 [통합 대시보드](../arrival_policy_screen_01/dashboard.html)를 함께 읽는다.

- `source_schedule.json`: 기존 `timeline.csv`의 `explore/queue/B2_PC/seed201` 24개 요청, 실현 간섭1.5, 기록 dispatch를 실행 허용 하한으로 전환한 입력. PC 출력/완료시각은 **출처 메타데이터**이며 기기 시간을 강제로 맞추지 않는다. 저장 `occupancy_segments.csv`의 49개 상태 구간과 일치한다.
- `analysis_contract.json`: 120초 조건부 J/AP 오차와 결측·지원 밖 처리, 연구 해석 경계.
- 기존 동결 파일은 외부 `energy_ap_state_run_v5/development_freeze.json` SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`; 저장소에 복사하지 않는다.

기기 명령 없는 PC 검사:

```powershell
python -B -m unittest tools.test_d1_arrival_recorded_replay -v
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
```

APK와 원본 모델·입력은 저작권·크기 때문에 포함하지 않는다. 외부 계획은 `source_files` 6개, `references` 4개, 프로젝트 서명 APK와 검사 도구 및 동결 모형을 해시로 고정한다. 계획 상태는 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`이며 소비 claim·실측값·오차 그래프는 없다.
