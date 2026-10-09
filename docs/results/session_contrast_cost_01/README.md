# 세션 편향 분리와 고정 AP basis 재추정

3개 검토 AI의 독립 검토·직접 반론·실제 결과 재토론4차 후, 같은개발13에서 일반/중심화의 전력4계수·AP5계수를20회 추정했다. 신규 추정이 없는 토론만의 결과가 아니다. 사람 전문가 인증도 아니다.

- [한국어 결과·개선과 악화](../../SESSION_CONTRAST_COST_RESULTS_20261010.md) / [결과 화면](index.html)
- [추정 전 토론](reviews/) / [결과 후 반론](reviews_post_eval/) / [원본·공유 hash](review_manifest.json) / [후속 hash](post_eval_review_manifest.json)
- [실제개발13 실행핵심·계측차](native13_contract_audit.json) / [유효 등록v2](registration_v2.json) / [첫등록 보존](registration.json) / [진입전오류](registration_entry_failure.json)
- [20추정모형·동결 receipt](run_v1/fit_receipt.json) / [개발묶음제외 선택](run_v1/selection.json) / [새모형 전체미채택](run_v1/adoption.json)
- [모든 방법J](run_v1/energy_errors.csv) / [AP](run_v1/AP_errors.csv) / [같은창 동결선택](run_v1/selected_joint_errors.csv) / [같은분모 요약](run_v1/selected_summary.csv)
- [저장B 비용](run_v1/B_saved_cost.csv) / [미기록B18](run_v1/B_unrecorded.csv) / [정책차](run_v1/paired_errors.csv) / [실제 API 검사](run_v1/entry_checks.json) / [검증](verification.json)

```powershell
python -B -m unittest tools.test_d1_session_contrast_cost -v
python -B docs/results/session_contrast_cost_01/run_example.py --opt-in --window registered600 --output output/session_contrast_LOAD.json
# 원자료나완료산출물을변경하지않고 새 폴더에서만 재현
python -B -m tools.d1_session_contrast_cost --action fit --output output/session_contrast_reproduce
python -B -m tools.d1_session_contrast_cost --action evaluate --output output/session_contrast_reproduce
python -B docs/results/session_contrast_cost_01/plot_results.py --output output/session_contrast_figures
```

작은 공유 입력·CSV와 기존 Python/NumPy/Matplotlib 환경만 필요하다. 기본 경로는 [직전 zero-offset+고정AP](../energy_ap_zero_offset_01/README.md)로 유지한다. 새 예제는 동일6 macro 맥락의 명시적 전이 진단이며 새독립확인/정책우월성/기기검증이 아니다. 새 head를 기존AP파일에 바꿔끼우지 않는다.

자료 역할은 개발13 / 추정미사용과거20 / 긴2다. 과거29평균과 새20평균을 직접 비교하지 않는다. 중심화로 개발 세션수준13개를 투영하지만 그값을 예측에 넣지 않는다. 고정β·시간계수의 사후 선정 이력이 있어 계수별 묶음제외를 전체수식의 독립OOF라 부르지 않는다. 새로운J/AP성공범위나정확도PASS를 사후로 정하지 않았다.

원식·기존후보·원자료·FAIL·소비계획·RL/strict/experiment_ready=false 보존. 기기/ADB/설치/실측/빌드/새계획/claim0이다.
