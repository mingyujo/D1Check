# JOINT-REFIT-01

개발9·평가20의 공동 계수 재추정 후보 하나. 개발 교차 기준 실패·일반 적용 보류. 기존 RL/기본 모형을 자동 교체하지 않는다.

- [한국어 결과](../../JOINT_MODEL_REFINEMENT_RESULTS_20261008.md)
- [그림·모든 세션](run/index.html)
- [실행 전 계약](contract.json) · [호환성](compatibility.json) · [검증](verification.json)
- [원/후보 조건별 집계](run/comparison.csv) · [전체 세션](run/session_errors.csv)
- [개발 묶음 제외](run/development_folds.csv) · [모형 민감도](run/policy_model_sensitivity.csv)
- [공통120초 정책 차이](run/paired_errors.csv) · [80초 순차관측 보정](run/memory30_paired_errors.csv)
- [AP·누적에너지 경로](run/paths.csv) · [5초 구간/혼합](run/windows.csv)

저장소 루트에서 Python/NumPy/Matplotlib를 사용한다. 기존 출력은 보존하고 새 경로를 지정한다.

```powershell
python -B -m unittest tools.test_d1_joint_model_refinement -v
python -B -m tools.d1_joint_model_refinement freeze --output output/joint_refit_reproduction_v1
python -B -m tools.d1_joint_model_refinement evaluate --output output/joint_refit_reproduction_v1
python -B -m tools.d1_joint_model_report --output output/joint_refit_reproduction_v1
```

계약의 입력은 저장소에 공유된 `model_refinement_01/inputs.json.gz`, `history_model_refinement_01/inputs.json.gz`, 기존 `overnight_sustained_run01/model.json`, `energy_memory30_01/session_errors.csv`다. 계산 재현에 개인 PC 절대 경로나 외부 원자료가 필요하지 않다. 원 manifest 확인은 기존 로컬 원본에서 수행했고 호환성 파일에는 해시와 비교항목만 남겼다.

후보 구조/격자는 개발 적합 전에 고정했다. 이미 본 평가자료의 사후 평가이며 반복 실행을 새 독립 확인으로 부르지 않는다. 새로운 실행 출력이 있는 경로에 freeze/evaluate를 중복 실행하지 않는다. 출력된 예외는 timestamp 실패기록으로 보존하고 원자료를 변경하지 않는다.

에너지는0..120초, AP는각 세션 post35 실제표본창이다. B는기존14세션의예측일정재사용이며 새일정/응답성능검증이아니다. MEMORY30의35..115초 개선은 실행 중 관측에 의존하며 사전 정책 비교용이 아니다. 계수 범위는 확률적 신뢰구간이 아니다. current raw=mA의조건부해석·절대정확도미인증·experiment_ready=false를유지한다.
