# Resident 식별 실행 — 개발4 완료, AP gate 실패

[한국어 결과/소비/한계](../../RESIDENT_IDENTIFICATION_RESULTS_20261009.md) · [화면](recorded_v3/index.html) · [원본 SHA](recorded_v3/inventory.json) · [실제소비](consumption.json).

개발4는정상이고확인4는미시도다. 원인beta 상한 경계해, 새모형동결/독립확인/기본교체없음. 코드3행 소비요약수정은AP모형해결과별개이며APK는바꾸지않았다. 원본receipt의2회수오류/소비요약오류도보존한다.

## 재현 (PC만, 새로운 출력 경로)

```powershell
# 공유 입력만으로 첫 사전등록 holdout/61grid 재현. 새 구조·상한 탐색 아님.
python -B -m tools.d1_resident_first_fold_diagnostic --inputs docs/results/resident_identification_run_01/recorded_v3/inputs.json.gz --original-model docs/results/online_policy_study_01/overnight_sustained_run01/model.json --output output/resident_first_fold_reproduction

# 원본 FINAL_RECEIPT/validated/manifest/AP 승인·cleanup 의존. 기기 명령/fit 없음.
python -B -m tools.d1_resident_identification_results --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_identification_plan_v3/collection_plan.json --output output/resident_results_reproduction

# 변경한 실제 host 실패 경계. FakeDevice만 사용.
python -B -m unittest tools.test_d1_energy_host_failure -v
```

원본 root `energy_ap_resident_identification_run_v3`의4개 `validated.json`/`host_cleanup.json`/`artifacts/cleanup.json`/`artifacts/start_ap.accepted.json`, terminal receipt와plan폴더8manifest가전체출력의정확한의존성이다. 원본목록hash는inventory에있다. 공유inputs는독립4개개발세션, 관측기준시간·AP·실제상태·전력만포함하며기기식별값/모델tensor없음. `first_fold.json`의원개발ID와공유session_00..03은순서가같고숫자는정확재현했다.

창정의: origin0=부하시작35초전; 120초J0..120 / 긴635초J0..635 / 공식600초35..635 / AP약35..815를구분한다. AP/에너지그림의x축은동일하나에너지곡선은635초에서끝난다. 미시도4는관측·예측null이고그림없음. candidate 첫fold는개발용진단·상한에붙은미채택값이며독립확인으로표시하지않는다.
