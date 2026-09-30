# 저온 AP 조건부 진단의 실행 가능한 PC 경계

기존 개발/확인 두 세션을 재사용한다. 새 실측·새 후보·계수 재보정이 아니다. [통합 판정의 이번 보완](../../../AP_SIMULATION_CLOSURE_PC_20260930.md#6-저온-ap-출력의-pc-연결-2026-09-30)을 따른다.

- `inputs.json`: 원본에서 추출한 부하 전 AP·Android 상대시각/조회 bracket·실제 dispatch→lane 해제 구간·공통창 초기 AP·고정 β/상태 기울기. 비교 AP는 `prediction_inputs` 밖에 있다. 개인 transport/serial/원문 fingerprint와 모델 바이너리는 포함하지 않는다.
- `contract.json`: 동일 APK·모델·입력·resident·프로토콜의 내용 해시, 원래 동결/후보 절차 해시. 이 해시 통과는 경험적 일반화나 정확도 합격이 아니다. 관측 시작28.1/28.7°C를 새 지원 범위로 채택하지 않는다.
- `readout/ap_paths.csv`: 기존 예측/관측 두 경로의 동일 수치 재현. 새 정확도 그래프는 만들지 않는다.
- `readout/output_scope.csv`: 경로의 조건부 진단만 허용. AP 최고·한도 초과·전체 J·정책 순위는 지원 출력으로 제공하지 않는다.
- `readout/summary.json`: 개발 MAE0.487518°C, 확인 MAE0.417521°C. 각각 세션1개이며 표본54개를 독립 반복으로 세지 않는다. 이번 범위 판독은 사후 분석이고 원래 확인 역할은 유지한다.
- `readout/validation.json`: 관련12검사·소스 해시·동결 byte 보존·기기명령0.

실제 첫 dispatch 직전35.007초까지 부하 전 AP가 입력된다. 그 정보를 이용해 공통창 시작0초부터 사전 예측했다고 부르지 않는다. 처음부터 실현 일정이 주어진 조건부 경로(A)이며 도착부터 일정까지 생성하는 종단간 예측(B)은 아니다. 이후 AP/전류는 예측에 주입하지 않는다. AP 표본의 조회 bracket은 센서 내부 측정시각을 보장하지 않는다.

외부 원자료 없이 저장소 루트에서 **새 출력 폴더**로 재현:

```powershell
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_ap_low_temperature_scope --output "$env:TEMP/d1-low-ap-scope-reproduce-new"
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m unittest tools.test_d1_ap_low_temperature_scope -v
```

원문 byte/추출 대응을 다시 검사해야 할 때만:

```powershell
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_ap_low_temperature_scope --extract-external 'C:/Users/LG/Documents/D1Check_Arrival_Extension' --output "$env:TEMP/d1-low-ap-input-new"
```

의존 원본: `energy_ap_state_run_v5/development_freeze.json`, `energy_ap_idle_response_run_v1/FINAL_RECEIPT.json`·`ap_model_freeze.json`, 완료된 두 세션의 `validated.json`·`thermal.jsonl`·`artifacts/manifest.json`·`requests.json`·`common_boundary.json`·`cleanup.json`, `host_cleanup.json`, `ap_analysis/summary.json`·`ap_path.csv`. 기존 파일은 덮어쓰지 않는다. APK 빌드·설치·기기 명령·실행 claim 경로는 없다.

합격 허용폭과 정책 차이 판별력은 미판정이다. 단일 상태 후보는 유휴 중 상승→하강을 재현하지 못하므로 수학적으로 계산되는 곡선 최대값도 검증된 최고온도/열 안전 출력으로 쓰지 않는다. 고정 유휴 평형의 숨은 열·센서 지연 원인은 분리 미식별 상태를 유지한다.
