# C8 — 사용자 승인: 다음 혼합 묶음 먼저

**실제 시작:** 소스 커밋 `b5673818d39f129071ff10b2fe87d44485fe7425`, coordinator SHA `59b2bd530254eb768e9d66318fdc0ad912bd47056305ea30a52489f971db5fb3`에서 실행했다. [시작 문맥·결합 SHA](RUNTIME_CONTEXT.json). 첫 MAIN START는23:04:17 KST, 새 M128 기준은28.4℃/reference SHA `629807c36ba74dea58cc85e0324ad656fb8caf72b33220bd3b4e7063b30db96f`다. [본요청 전 기준 고정 증거](INITIAL_REFERENCE_COMMITMENT.json)·[원 reference](M128_REFERENCE_ORIGINAL.json)·[시작 승인](FIRST_START_APPROVAL.json). 이 사실만으로 정상 회수·서비스 성공·열 절감을 주장하지 않는다.

사용자는 **“다음 혼합 묶음부터 진행”**을 명시 선택했다. [준비해 검증한 순서 개정안](../cold_carry_deferral_draft_20261015/README.md)을 채택한다. 원40ID·5,720요청·예산81·정식58소비를 보존하며, 기존 온도 조건을 완화하지 않는다.

**이번 대상은 원ordinal18~21의 M128 WAIT200 → BASE → PAIR_G → ORDER, 최대4회**다. 미시작 L64 PAIR_G ordinal17은 원ID·27.1℃reference·미실행 상태를 그대로 두고 전체 순서의 맨 뒤로 미룬다. 새 전체 순서는 원0~16 → 원18~39 → 원17이다. 남은23회·3,368요청을 버리거나 대체하지 않는다. 최대4회가 이번 시간에 모두 완료된다는 뜻은 아니다.

**기기23:45 KST 종료 / 회수·저장23:50 전 완료 / 마지막5분 확보.** 새APP에는21분·MAIN에는5분 여유가 필요하다. 시간 또는 초기 상태 조건이 부족하면 미시작/사전거절로 보존한다. 같은 ID의 실제 APP를 재전송하거나 실패를 재수집하지 않는다.

[사용자 순서 승인](USER_ORDER_APPROVAL.json) · [시간창](USER_WINDOW.json) · [실행 계약](EXECUTION_CONTRACT.json) · [이번4개 PC 검산](PC_VERIFICATION.json) · [전체 남은23개 PC 검산](PREPARATION_PC23_VERIFICATION.json) · [관련33검사](REGRESSION_VERIFICATION.json) · [읽기전용 시작 점검](BEFORE_DEVICE_READONLY.json)

M128 기준은 **이번 첫 WAIT200의 공통 준비 상태에서, 원래 알고리즘으로 본요청 전에 정한다.** 결과를 보고 기준을 선택하지 않는다. 같은 묶음4군은 같은 원reference를 사용한다. 공통4resident·각2warmup/총8회, MAIN±0.5℃·60초·기울기·공백·600초, C기한2.2초/D기한5초, 응답/저장/실제lane반환 경계, 입력·지원 병행·품질·APK·core179는 바꾸지 않는다. 탐지GPU는 공통 워밍업 경로이며 MAIN 후보로 추가하지 않는다.

원자료 `Documents/A24R02C8`, 전역 예약·APP intent·owner `Documents/A24R02C8_GLOBAL`, 실제job `output/A24R02C8/job.json`이다. 상태는 실제owner·APP intent·START/close·outcome·WINDOW_STOPPED와 대조한다. 기기 연결이 끊기면 같은 신원만 최대20분과 남은 시간창 중 짧은 쪽까지 기다린다.

~~~powershell
$env:PYTHONIOENCODING='utf-8'
python -u -B tools/d1_a24_confirm_remaining.py execute output/A24R02C8/job.json --execute-authorized
~~~

이것은 이번 방문의 원명령이며 실행 후 재사용하지 않는다. 중지/이동 시 현재root의 STOP_AFTER_CURRENT.json을 write-once로 기록하고 현재 요청은 close·회수까지 마친다. C6/C7은 APP0에서 이미 종료됐다. [C7 닫힌 냉각 원기록](../../../results/a24_measurement_share_20261015/preAPP_visit_07_cooling/README.md)·[C6 원기록](../../../results/a24_measurement_share_20261015/preAPP_visit_06_cooling/README.md)을 보존한다.

새 순서는 본요청을 시작하기 전에 사용자 선택으로 고정했다. 초기온도·시간·환경 혼입을 완벽히 없앤 것은 아니며 실제 순서 변경을 보고서에서 공시한다. 상승량 보조 분석은 [기존17조건 진단](../../../results/a24_initial_state_diagnostic_20261015/README.md)으로 분리하며 새 실행 기준의 검증으로 승격하지 않는다. 에너지J 미판정·AP HAL 채널·표면 미검증·experiment_ready=false·사용자WIP·데스크톱/S26/NPU를 유지한다.
