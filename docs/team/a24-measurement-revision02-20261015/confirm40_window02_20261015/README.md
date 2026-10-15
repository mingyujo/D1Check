# A24 확인40 둘째 방문

2026-10-15 사용자 재개 및 지금부터150분 승인. **17:37~20:07 KST, 기기 작업20:02 종료**, 마지막5분은 저장·회수다. 원40계획의 앞4회 완료·총45/81소비를 보존하고 미시도36만 원래 순서대로 진행한다. 이 문서는 실행 등록이며36회 완료를 뜻하지 않는다.

[시간창](USER_WINDOW.json) · [실행 연결](EXECUTION_CONTRACT.json) · [PC 검사](FOLLOWUP_PC_VERIFICATION.json) · [등록 상태](REGISTRATION.json) · [이전 전역 원장](../confirm40_after_dev8_20261015/GLOBAL_CONSUMPTION_LEDGER.json)

- 첫 순서: R02CONFIRM01 저부하 PAIR_G→BASE, 분류 CPU→GPU, 이후 블록2~5의 원 순서. 각 묶음은 원SELECT_FIRST/MATCH_FIXED 규칙을 유지한다.
- 새 실행기 `tools/d1_a24_confirm_followup_window.py`는 원179핵심소스·기존 coordinator·APK·계수·기한·요청은행·준비/MAIN gate를 변경하지 않는다. 전역 미소비 원장·이전 close와 원물SHA·새 시간창을 결합한다.
- 전역 세션 예약을 독점 생성하고 실제 APP 시작 명령 직전에 APP intent를 남긴다. 전송 여부가 불명확한 APP은 예산에 보수적으로 포함하고 자동 재전송하지 않는다. 기존4회 또는 이미 예약한 ID는 재실행할 수 없다.
- APP/NEW_SESSION에는21분, MAIN에는5분 이상 여유가 필요하다. 배터리10% 이상·비충전·동일기기·동일 화면 조건을 유지한다. 단절 시 동일물리기기+fingerprint를 확인하며 최대20분 기다리되 기기종료시각을 넘기지 않는다.
- IP:포트를 새 등록에 직접 넣은 첫 PC 조립은 원SAFE_NAME 검사에서 거부됐다. APP/실측0인 후보를 보존했다. 원등록·manifest를 그대로 사용하고 기존 ReconnectingAdbClient가 물리일련번호+fingerprint로 실제 현재 연결주소를 찾는 방식으로 해결했다. 주소형식 검사를 완화하지 않았다.
- 새 전역보호6검사 포함 관련19검사 PASS, 실제 남은36개 authorization 조립 PASS다. PC용 가상 reference는 실측 증거가 아니다. 실제 reference는 기기에서 기존 절차로 봉인한다.

private 실행job은 `output/a24_confirmation40_window02_20261015/binding_v2/job.json`, 실제 원물은 `Documents/A24R02C2`, 전역예약/APP intent는 `Documents/A24R02_CONFIRM_GLOBAL_20261015`다. `binding_v2` 이전 후보는 실행되지 않았다. `execution.log`·`OWNER_WINDOW.json`·실제 프로세스·`WINDOW_STOPPED.json`을 함께 확인해야 한다. 첫방문 및 이번 방문 실행 명령을 재개 버튼처럼 다시 호출하지 않는다.

현재 결과는 완료될 때 별도로 기록한다. 기존 첫방문의 AP 부적격1회·J미판정·실패대체0을 유지한다. [조건부 에너지 분석](../../../results/a24_revision02_20261015/conditional_energy_comparison/README.md)은 이전12군에 대한 별도 사후 분석이며 원확인 에너지 판정을 소급 변경하지 않는다.
