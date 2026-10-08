# 정책 계수 민감도: 저장 일정에 한정한 판독

[한국어 결과](../../POLICY_COEFFICIENT_SENSITIVITY_RESULTS_20261008.md) · [그림·96비교](run_v2/index.html) · [계약](contract.json) · [검증](verification.json).

- 입력: 첫 seed610880001의4family×3context×6policy, 저장72일정/4,752논리요청. [공유 압축 입력](inputs.json.gz)은필요한요청·lane경계·초기조건과원metric을포함한다.
- [수정후360비용](run_v2/costs.csv) · [480짝차이](run_v2/paired_variants.csv) · [96guard](run_v2/direction_guard.csv) · [72상태점유](run_v2/state_exposure.csv) · [집계](run_v2/summary.csv).
- 원모형＋공동개발9＋개발묶음제외3의다섯설정. 변형4개는미채택개발추정이며검증모형이아니다. 같은설정의두정책비용을짝지으며계수를조합해새가상모형을만들지않는다.
- 기존B일정에조건부인후처리. 새정책실행/계수적합/RL/기기0. 계수변경후정책재선택·전체오차범위·실제절감·독립확인은아니다.

저장소루트에서Python/NumPy/Matplotlib로재현한다. `prepare`는이미보존된범위를다시추출하는명령이며일반재현에필요하지않다. 개인PC절대경로나외부실측원본없이공유입력으로계산한다. 새출력경로를사용한다.

```powershell
python -B -m unittest tools.test_d1_policy_coefficient_sensitivity -v
python -B -m tools.d1_policy_coefficient_sensitivity run --output output/policy_coefficient_reproduction_v1
python -B -m tools.d1_policy_sensitivity_report --output output/policy_coefficient_reproduction_v1
```

면적은기존KPI의유효유휴R 초과AP35..180초적분이다. 초안 [run/](run/)과[contract_v1.json](contract_v1.json)은수정전기록으로보존했다. 초안의AP면적값은최신시작AP를잘못기준으로썼으므로그필드는판독에쓰지않는다. J/최고AP/96guard는수정후와정확히같다. 원시뮬레이터·원결과를변경한것이아니다.

지원외/결측은unavailable 또는진입거절이며0으로채우지않는다. 전기한충족과서비스비악화를먼저표시하고범위의부호를판독한다. EPS1e−9는수치동률용이다. 범위는신뢰구간이나정확도합격선이아니며엄밀한physical uncertainty를보장하지않는다. 기본모형/RL/strict/experiment_ready=false 유지.
