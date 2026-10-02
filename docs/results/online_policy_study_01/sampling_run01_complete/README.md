# 전력 조회 주기 대조 — 적격4·중단1 별도 보존

`online_power_sampling_run_v1`의 첫2세션과 `run_v2`의 후속2세션을 연결했다. 원래4세션 계획은 냉각 관측 timeout으로 중단됐으며 연속 완주가 아니다. 중단 세션의 본96/warmup8 소비와 부분 공통창 기록은 원본에 보존하고 적격4의 평균에 넣지 않았다. 계수 적합0/정확도PASS 없음/experiment_ready=false.

- `sessions.csv`: 실제 전력 표본120/133, 위상8구간 중2/8, 전체120초 및35–120초J, 초기AP, 실제병행, 읽기 소요시간. 센서 read 소요시간은 CPU 사용시간/에너지 비용이 아니다.
- `paired_differences.csv`: 두 비교 모두900−1000ms. −4.200J/+0.300J, 방향 일치 없음. 두 block의 초기조건/간격 차이를 제거한 인과 효과가 아니다.
- `frozen_model_transfer.csv`/`frozen_model_paths.json`: 기존557fbe5b…동결식, 실제 일정·부하전AP와 전력만 입력. 사후 프로토콜 전이 계산이며 새 독립 정확도PASS가 아니다. Android의 role=development는500ms 입력 선택 필드이고, 이 자료로 모형을 개발/재적합한 것이 아니다.
- `consumption.json`: 총5시도/적격4/실패1, 본480+warmup40=520추론, runtime20/staging5·35파일/pull2/APK push·설치각1/ADB4144. 실패계획962.877초＋후속597.785초=작업1560.662초, 사이PC 준비 공백 별도. 앱cleanup4완료/실패세션미회수,host세션정리5＋설치정리1, 각계획 마지막ps 대상부재.

```powershell
python -B -m tools.d1_online_sampling_readout --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/online_power_sampling_plan_v2/collection_plan.json --model-freeze C:/Users/LG/Documents/D1Check_Arrival_Extension/online_policy_study_run_v4/model_freeze.json --output output/sampling_readout_fresh
python -B -m unittest tools.test_d1_online_sampling_study tools.test_d1_online_policy_study -q
```

재현에는 plan_v1/v2, 해당 두 원본의 계획에 연결된 artifacts/thermal/validated 및557fbe 동결JSON이 필요하다. 공유 CSV/그림은 기기 없이 열 수 있다. 첫 PC 그림 후처리에서 cp949 디코딩 오류가 발생해 수치파일은 생성됐으나 완료하지 못했다. UTF-8을 명시한 코드로 새 출력에 재현했으며 추가기기 실행은 없었다. 실패한PC출력은 무시하고 이 complete폴더만 사용한다.

현재 결론:900ms가 반복 부하의 표본 위상 분포를 넓히는 것은 관측됐다. 그것만으로 전력 모형 오차를 해결하지 못했다. 네 관측J 범위4.200J에 비해 부하전W 범위를120초로 전용한 변동은22.398J다. 이는 배경W 입력 가정의 민감도를 보여주며 배경의 실제 물리 원인을 식별한 것은 아니다. 다음은 기존13적격 세션을 사용한 **세션별20초 배경입력 대신 개발자료의 pooled resident 항**이라는 최소후보 하나의 식별성/사후 성능을 검토한다. 후보가 식별되고 유지할 근거가 있을 때만 별도 동결·신규 독립 확인으로 이어간다. 기존 동결값과 독립확인 지위는 그대로 보존한다.
