# AP 두 부하 이력 일괄 확인01

[계획·실행·종료 보고서](../../AP_BUNDLE_CONFIRM_RUN01_20261001.md), [결과 화면](run01/index.html), [작은 요약](run01/summary.json).
기존 후보를 바꾸지 않은 확인2 묶음이다. 첫 기기 목록0대로 **claim 후 preflight 중단**, 두 세션 모두 미시도. 원본/registry는 소비·종료 상태로 보존하고 Run 재호출 금지. 기존 실패·동결 모형·strict/default/experiment_ready=false 유지.

- [사전 판독 계약](analysis_contract.json), [등록 입력; 실측 아님](planned_input.json), [검증/실행 소스·APK·manifest·freeze 해시](pre_execution_verification.json).
- 새 AP/J/일정 관측 없음, 그림 없음, candidate fit0. 관련26검사/실제PS Check 통과는 PC 준비 사실이다.
- APK 변경/빌드/전송/설치0. 원본 의존: 외부 `energy_ap_bundle_confirm_run_v1/FINAL_RECEIPT.json`, `host_checkpoints`, `host_commands/0000/client`와 계획/registry. 공유물에는 APK/키/모델/기기 식별정보/대용량 원본을 넣지 않았다.

당시625e5a8 버전 재현(PC만, 새 output; 최신 판독 코드에는 아래 검증 명령 사용):
```powershell
python -X utf8 -B -m tools.d1_ap_bundle_readout --plan '<energy_ap_bundle_confirm_plan_v1/collection_plan.json>' --output '<새 PC 폴더>'
python -X utf8 -B -m unittest tools.test_d1_ap_bundle_confirmation tools.test_d1_resident_control_plan tools.test_d1_ap_transfer_confirmation tools.test_d1_ap_transfer_report -q
```

현재 Check는 소비 경로를 만나 기기 명령 없이 거절해야 한다. 연결 복구를 이 계획의 재개·추가 실행으로 사용하지 않는다.


현재 판독 경로의 [PC 검증/CSV](readout_pc/index.html)는 기존 queue 원문 개발/확인 재생이며 새 burst 실측이 아니다. 부분 JSONL 소비 하한/미확인 null·반환 event·렌더링 오류 분리를 수정했다. [변경·원문 의존·고정 수치](../../AP_BUNDLE_CONFIRM_RUN01_20261001.md#pc-판독-경로-검증--2026-10-01).

```powershell
python -X utf8 -B -m unittest tools.test_d1_ap_bundle_readout -q
python -X utf8 -B -m tools.d1_ap_bundle_readout_check --source-plan '<energy_ap_idle_response_plan_v1/collection_plan.json>' --output '<새 PC 폴더>'
```

이 수정 후 옛 bundle plan_v1의 소스 해시와 현재 판독 해시는 다르므로 최신 코드가 옛 계획에 대한 재판독을 거절하는 것이 정상이다. 당시 결과/소비를 보존하고 source 검사를 우회하지 않는다. 새 실행 계획은 만들지 않았다.
