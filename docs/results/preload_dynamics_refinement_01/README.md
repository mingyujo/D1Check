# 부하전 동역학 초기화 후보

[한국어 결과](../../PRELOAD_DYNAMICS_REFINEMENT_RESULTS_20261008.md) · [전체 그래프/172행](run/index.html) · [AP 후보](ap_candidate.json) · [계약](contract.json) · [검증](verification.json).

추가 실측 없이 AP 일부 오차 감소를 재현했다. 지속8 AP MAE0.381→0.335°C/최근14 0.329→0.307°C지만 새확인6 0.260→0.268°C로 악화한다. 첫값 고정 해제는 물리계수 변경이 아닌 초기조건 추정 변경이다. 전력 사전추세 외삽은 악화해 제외한다. 개발 기준 실패로 기본/RL/strict/experiment_ready=false 유지.

저장소 루트에서 Python/NumPy/Matplotlib로 새 출력에 재현한다. 입력은 기존 `model_refinement_01/inputs.json.gz`, `history_model_refinement_01/inputs.json.gz`, 원모형 JSON이며 개인PC 절대경로나 기기/외부원본 접근이 필요하지 않다.

```powershell
python -B -m unittest tools.test_d1_preload_dynamics_refinement -v
python -B -m tools.d1_preload_dynamics_refinement --output output/preload_dynamics_reproduction_v1
python -B -m tools.d1_preload_dynamics_report --output output/preload_dynamics_reproduction_v1
```

선택적 AP 후보 API의 예:

```python
from tools.d1_optional_preload_ap import forecast
from tools.d1_joint_model_refinement import panel
case = panel()[0][0]  # 보존한 실제 일정 조건부 예시
result = forecast(case['pre'], case['actual'], case['q'],
                  initializer='free-first-preload-v1')
```

명시적 opt-in만 허용한다. 예측에 관측 부하후 AP/전력을 넣지 않는다. 기존4지원 상태를 확인하며 수치 추정의 R/H를 주변온도/내부온도 실측으로 부르지 않는다. 이 호출을 실기기/독립 정확도 PASS로 해석하지 않는다.

[세션별 A/B/분할오차](run/session_errors.csv) · [조건별 집계](run/comparison.csv) · [부하전 초기값](run/initial_states.csv) · [5초구간](run/windows.csv) · [실측/예측 경로](run/paths.csv). J는0..120초, AP는각실제 post35 표본창이다. 조합은부품진단이며세번째적합구조가아니다. 이미본자료의사후평가·current raw=mA 조건부해석·절대정확도미인증을유지한다.
