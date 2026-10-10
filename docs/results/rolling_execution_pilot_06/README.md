# 실행 첫 행동 선택기:전체 요청 흐름 파일럿 준비

[범위·정책·예산·판정](../../ROLLING_EXECUTION_PILOT_PREP_20261010.md) · [실행계약](execution_contract.json) · [입력](cases.json) · [준비 화면](index.html) · [준비 검증](preparation_verification.json)

새요청2seed×4부하×3문맥24조건×Band/Triton/원V2/새선택기4정책＝96행. 실제실행의미gate4후 총100환경예상/상한112·학습/기기0이다. 원계수/초기관측/기한/CG_DC/작업량/원관측창과기존정책은보존한다.

정책연결·순수32검사·입력/소스고정완료. **native gate/본배치 미실행**, 미래작업예측/학습/기기0·실행clock미시작이다. 결과나 성능개선으로 표시하지 않는다.

준비 재검사: `python -B -X utf8 -m tools.d1_rolling_execution_pilot check`. 이후 실행지시가 있을 때만 `python -B -X utf8 -m tools.d1_rolling_execution_pilot run`을 호출한다. 같은 task/clock/소비는 새폴더/재개로초기화하지 않는다. 중단 중인 별도기기실측은 재개하지 않는다.
