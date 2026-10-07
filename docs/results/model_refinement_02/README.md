# 사후 부하 반응 후보

[보고서](../../MODEL_ROBUST_GAIN_20261007.md) · [화면](index.html). 개발3+기존확인6을 사후개발9로 사용, 지속8은 이번 적합제외지만 이미 열람한 평가다. 후보 미채택, 기본/strict/experiment_ready=false 유지.

저장소 루트에서:
```powershell
python -B -m unittest tools.test_d1_model_robust_gain tools.test_d1_model_refinement -v
python -B -m tools.d1_model_robust_gain --output output/model_refinement_02_reproduce_v1
```
새 출력경로가 필요하다. 입력은 ../model_refinement_01/inputs.json.gz와 기존 동결모형이며 원자료 없이 수치 재현 가능하다. 원본 출처는 앞선 source_inventory/raw_cache_audit를 참조한다. 입력·동결 파일을 수정하지 않는다. 경계AP/J 결측은 0으로 채우지 않는다. paths.csv.gz는 전체 A/B 실측–예측, windows.csv는5초 혼합상태/잔차, session_errors.csv는 공통창/구간/가열냉각, paired_errors.csv는4쌍, pre_features.csv는 사전관측 진단이다.
