# 저장 CPU/B2 일정 직접 비교

[계약·예산·실행 결과](../../RECORDED_POLICY_COMPARE_20261002.md), [판독 계약](analysis_contract.json), [PC 검증](pc_verification.json).

입력은 기존 `docs/results/arrival_visualization_01/timeline.csv`의 explore/queue/201/CPU_URGENT,B2_PC이다. 전체 배치를 다시 계산하지 않았다. 기기에서 실제 duration을 강제하지 않는 기록 일정 재생이다.

PC 테스트:
```powershell
python -B -m unittest tools.test_d1_recorded_policy_comparison tools.test_d1_ap_bundle_confirmation -v
```

완료 또는 종료 receipt가 있는 원본의 PC 판독(항상 새 출력 폴더):
```powershell
python -B -m tools.d1_recorded_policy_readout --run <energy_recorded_policy_compare_run_v1> --output <new-output>
```
필요 원문: root frozen_collection_plan/FINAL_RECEIPT, 각 세션 validated/thermal.jsonl, artifacts의 manifest/common_boundary/requests/summary/cleanup/progress/start_ap.accepted.json. 원본은 외부 D1Check_Arrival_Extension에 있고 명령/설치 APK/기기 식별자는 공유하지 않는다.

출력은 observed 공통120초 J·AP·lane·서비스와 사전 두 쌍의 B2−CPU 기술 차이다. 자료가 없는 세션/쌍은 null/미완료. 정확도 PASS·온라인 정책·동적 모형 검증·통계적 우월성으로 해석하지 않는다. 기존 동결 모형·기본/strict·experiment_ready=false를 유지한다.

[완료 네 세션 화면](run01/index.html) · [수치](run01/summary.json) · [소비/해시 검증](run01/verification.json). 관측 그림·CSV/JSON은 위 CLI로 재현하며 공유 HTML에는 최종 판정 표와 문서 링크를 덧붙였다. plan_v1은 완료·소비 상태로 Check/Run 재실행 대상이 아니다.
