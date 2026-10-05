# 전력 잔차와 표본 위상 민감도

기존 개발3·확인6의 전력 계수/오차를 보존한 사후 분석이다. 새 후보 적합0. `cases.csv`와 `windows.csv`는 각각 세션과 사전 지정 구간의 산술 분해다. `phase_counts.csv`는 요청4개 반복 주기의8등분별 실제 표본 수이며, 내부 센서 갱신 또는 편향의 직접 측정이 아니다.

`diagnosis.json`은 정확한 원본 파일 해시와 leave-session-out의 수치 rank/계수를 보존한다. rank 부족일 때 출력된 진단 NNLS 숫자는 식별된 물리 계수로 사용할 수 없다. charge raw 단위도 독립 인증되지 않았다.

`sampling_contract.json`은 새4세션 실행 전에 고정한 ABBA 비교 계약이다. 동일 새APK/부하에서 전력조회1000/900/900/1000ms를 비교한다. 900ms의 추가 계측 비용 및 세션변동을 분리할 절대 기준이 없으므로, 차이를 기존 자료에서 보정해 빼지 않는다. 확인 후 원래 모형 재적합도 하지 않는다.

재현:

```powershell
python -B -m tools.d1_online_power_diagnosis --root C:/Users/LG/Documents/D1Check_Arrival_Extension/online_policy_study_run_v4 --output output/power_diagnosis_fresh
```

외부 의존 파일은 위 root의 `development_cases.json`, `confirmation_cases.json`, `model_freeze.json` 세 개다. 새 결과는 별도 `sampling_run01`에 연결하며, 기존 `run02`의 독립 확인 수치와 합치지 않는다.
