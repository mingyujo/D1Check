# 공동 롤링의 세 전문가 AI 재검토

[설계·토론·계산식·미완료](../../ROLLING_EXPERT_REVIEW_20261010.md) · [오프라인 화면](index.html) · [개발655판단 CSV](historical_forecast_audit.csv) · [근거·검증](verification.json)

모바일·산업공학·RL AI가 두 라운드의 상호 반론으로 **전체 계획1등 뒤 검사 대신 실행 첫 행동별 직접 선정**에 합의했다. 기존창4/선별8/계수/기한/CPU·GPU 지원은 보존하고 원형 선택기16정의검사를 완료했다. 공통과거최고/상태·행동동치/대기 의미의 마지막 반례를 수정했다.

기존 개발 통과633예측에서 미래AP감소289·전체최고AP감소208·J감소2, 미래AP만 감소/전체최고AP와J동률81건을 확인했다. 새 정책을 실행해81건을 줄였다는 성과가 아니다. 원대기 예측의 실제취소/재계획 의미는 미검증이다.

정책미연결·새환경/예측/학습/기기0·대안prefix실제기회미확정이다. 다음 최대8공개상태/216예측(선별복원포함792상한)의 사후진단은 제안이며 아직등록/실행0이다. 기존9749/1449·닫힌IE480/480·진행중다른실측/원자료/기본/strict/experiment_ready=false보존이다.

재현: `python -B -X utf8 -m unittest tools.test_d1_rolling_prefix_selection -v` 및 `python -B -X utf8 -m tools.d1_rolling_expert_review --output docs/results/rolling_expert_review_04`. 두 명령은 실제정책/학습/기기를 실행하지 않는다.
