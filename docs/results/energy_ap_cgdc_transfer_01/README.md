# CG_DC 전이 확인 — PC 준비, 아직 실측 없음

[목적·예산·외부 계획·승인 후 명령](../../../docs/AP_CGDC_TRANSFER_PREP_20260930.md).

- `schedule.json`: 저장 burst/201/B2_PC/실현1.5에서 만든 **PC 예정 일정**. 도착0–4.840초는 원래 APK 격자 유지, dispatch 허용 시각만 +35초. 기기 일정·실측 결과가 아니다.
- `analysis_contract.json`: 기존 모형/후보 freeze와 관측/정보/판독 경계. 새 계수 적합·strict 확대·정책 순위 없음.
- `verification.json`: 현재 소스·계약·계획·검사 대응. 원자료나 기기 식별값을 포함하지 않는다.

입력 선정은 이미 고정한 연구용 서비스 guard와 같은 APK의 CG_DC 지원을 근거로 한다. 에너지/AP 오차가 작게 나오는 입력을 고른 것이 아니다. 현재 APK에서 불가능한 DC_DG/B3 재생을 대체 비용으로 채우지 않는다. 관측 시도0·claim0·기기 명령0; 상태는 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`.

```powershell
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m unittest tools.test_d1_ap_transfer_confirmation tools.test_d1_arrival_recorded_replay.RecordedReplayTest.test_inrange_followup_has_new_identity_but_same_recorded_work tools.test_d1_arrival_recorded_replay.RecordedReplayTest.test_actual_recovery_parser_accepts_recorded_gate_and_rejects_early_dispatch tools.test_d1_arrival_recorded_replay.RecordedReplayTest.test_validation_failure_does_not_repeat_completed_host_cleanup -v
```

위Python9검사는 저장 CSV와 자체 fixture를 이용한다. 현재Windows 실제계획Check는 외부의 원래 staging 모델/입력6파일, 참조출력4파일, 프로젝트 서명 APK/빌드 receipt, 개발3 freeze와 기존 유휴후보 freeze가 필요하다. 정확한 파일·SHA는 `collection_plan.json`에 있다. 이 대용량/개인환경 파일을 공유 bundle에 복사하지 않는다. 저장 일정 생성/fixture 테스트에는 기기 명령이 없으며 추가 실측을 호출하지 않는다.

분석 CSV는 적격한 미래 자료가 있을 때만 새 PC output에 생성한다. 자료가 부족하면 readout은 오류를 내며 원자료를 고치거나 전체 J/AP를0으로 채우지 않는다. 관측·원래식 외삽·후보 조건부 재구성·검증되지 않은 정책 출력을 구분한다. 전체120초 잔차와 부하후 AP 점수의 시간 분모는 서로 다르다.

Android 실제 contract 경계1건: 기존 격리 Gradle 환경에서 :benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.ArrivalRecordedReplayTest.delayedBurstReleasePassesActualContractsButShiftedArrivalFails --offline --no-daemon --no-configuration-cache 통과. 앱 본문 compile은 UP-TO-DATE, APK assemble/ADB는 호출하지 않는다.
