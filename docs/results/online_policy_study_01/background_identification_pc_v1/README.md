# 배경 활동 개발4: 입력 경계 수정과 단일 gamma 미채택

2026-10-03 · 기준 HEAD `9045ceabc12fbbd8d3016de6d52ce0867a8bea84` + 이번 미커밋 분석 변경에서 검증. **PC 작업 완료, 기기 명령·추론·새 계획·claim·APK 빌드 0.**

[대시보드](index.html) · [사전 적합 계약](analysis_contract.json) · [수치](evaluation/summary.json) · [후보/제외 평가](evaluation/candidate.json) · [CPU 동시성](evaluation/association.json) · [미래 예측](evaluation/display_metrics.json) · [검증](verification.json)

## 결론

확인된 **전력 초기화 구현 오류를 수정**했다. 추가한 한 개 gamma 후보는 **미채택**한다. gamma의 수치 계산 자체는 가능하지만, 네 개발 세션이 공통 양의 보정 효과를 지지하지 않는다. 이를 원인 미식별이라는 이유로 같은 개발 수집을 반복하거나 확인12세션을 자동 시작할 근거로 삼지 않는다. 기존 동결/default/strict/experiment_ready=false는 유지한다.

기존 AP 모형의 이 자료에서의 평균 조건부 MAE는 0.184408°C다. 이번 네 세션은 개발용·변경 프로토콜·두 수집 block이며 새로운 독립 예측 검증이 아니다. 낮은 평균오차를 모든 초기조건/이력의 오차 한도나 작은 정책 차이 판별 가능성으로 확대하지 않는다.

## 1. 해결한 구현 결함

동결 `separated_power_final/model.json`의 `energy_baseline_mode=session_preload`, `preload_power_window_s=[-20,30]` 및 원 개발 로더 `tools/d1_separated_power_study.py`는 부하 전 **−20~30초**를 요구한다. 최근 background 판독기는 generic online 로더를 재사용하면서 **10~30초**를 사용했다. C0 전용 경로에도 같은 문제가 있었다.

`d1_background_activity_result.load_inputs`가 모형에 기록된 창을 읽고, 결측/무효 창이면 거부하도록 수정했다. 기존 0~120초 적분·전류 단위·실제 lane 일정·전력계수·AP 초기화/계수는 변경하지 않았다. 개선 여부를 보고 창을 선택하지 않았다. 원본·기존 공유 결과를 덮어쓰지 않고 `--legacy-preload-window`로 과거 수치를 재현한다.

|개발 세션|관측120초 J|기존 예측 J|수정 예측 J|기존 오차 J|수정 오차 J|AP MAE °C (불변)|
|---|---:|---:|---:|---:|---:|---:|
|v4 C0_PRE|132.338|142.793|136.379|+10.455|+4.041|0.152|
|v4 CPU96|165.025|171.192|162.862|+6.168|−2.162|0.203|
|v6 PAR96|153.440|150.563|150.188|−2.877|−3.252|0.225|
|v6 C0_POST|129.789|143.740|133.374|+13.951|+3.585|0.157|

네 세션의 |120초 J 오차| 평균은 8.362695→3.260195J. PAR은 악화했고 그 결과도 보존했다. 전체 차이의 변화는 정확히 `120×(새 preloadW−기존 preloadW)`다. 원본 관측 J와 기존 예측 J·AP 점수 재현, AP 결과 불변을 확인했다. 누적 경로에는 구간별 상쇄가 남는다. 120초 총량만 보고 정확도 PASS를 부여하지 않는다.

이 수정은 PC 예측 입력 계약 복원이다. 앱·센서·실측 프로토콜을 새로 바꾸지 않았다. 현재 보고서 이전 background_activity_run01~04의 J 수치는 당시 10~30초 결과로 보존하며 이 표가 선택된 적격 네 세션의 정정값이다. 과거 gamma 적합 결과·다른 모형의 자체 초기화는 덮어쓰지 않는다.

## 2. 자료와 시간 경계

- v4의 C0_PRE/CPU96 + v6의 PAR96/C0_POST만 사용. v4 실패를 성공 4세션으로 합치지 않는다. 서로 다른 수집 시점·이력·block을 보존한다.
- 정확한 원자료 의존 파일과 SHA는 [source_hashes.json](bundle/source_hashes.json). 외부 루트는 `C:/Users/LG/Documents/D1Check_Arrival_Extension`이다. 각 plan/receipt, artifacts manifest/requests/progress/cleanup/common_boundary/start_ap, thermal, 이미 검증된 trace_export/audit만 읽었다. traceprocessor·기기 재실행 없음.
- 에너지 common0~120초, AP common35초부터 각 냉각 종료 전 마지막 관측점(약178~180초). 시작 AP27.2/27.5/28.9/29.5°C로 원래 32.5~34.0°C 범위 밖. 실제 lane 일정 조건부 AP이며 postload 관측 AP는 예측 입력에 넣지 않는다.
- 실제 sampler midpoint와 공개 시각을 분리했다. 앱에 기록된 14×4=56개의 과거10초 전력 창은 `past_input_ready_ns`로 모두 재현(최대 차이 1.56e−15W). PC 후보의35+10n초 grid는 기존 보수적 event mono 공개 시각을 쓰며 앱이 실제로 이 예측을 발행했다고 하지 않는다. 앱의 task_residual은 당시 null이었고 PC에서 과거 lane 점유만 결합한다.
- A24 current raw=mA 조건부 해석, 절대 에너지 정확도 미인증. AP 시작값·유효 유휴 기준·주변 온도는 같은 의미가 아니다.

## 3. 사전 고정한 한 후보의 판정

기존 후보군 `T=T_frozen+δ`, `δ′=−βδ+γr`, `δ(35)=0`, `γ≥0`만 평가했다. r은 이미 공개된 과거10초 전체 전력에서 과거 task 증가전력과 올바른 preloadW를 뺀 값이다. β/k/g·원 전력계수·service·AP 초기화 고정, 세션별 같은 가중치로 gamma 하나만 적합. 새 구조·음의 gamma·CPU별 전력계수 탐색 0. 이번 결과를 보기 전에 계약 파일을 저장했지만 이전 결과들을 이미 본 사후 개발 연구라는 성격은 유지한다.

- 공통 무제약 gamma **−0.0205509432**, 등록된 γ≥0 최적값 **0**. 양의 보정이 지지되지 않는다.
- 세션별 무제약 gamma: C0_PRE **+0.122618**, CPU **−0.005529**, PAR **+0.019147**, C0_POST **−0.101121**. 센서 샘플 수53/54/55/56은 독립 세션 수가 아니다.
- 세션 제외 평균 MAE **0.184408→0.199300°C**, block 제외 **0.184408→0.203042°C**. 각 제외 결과와 학습 gamma를 모두 저장했다. 제외 평가도 모델 선택 후 독립 확인으로 부르지 않는다.
- nuisance 민감도(β/k/세션별 초기값·유효 기준)와 gamma의 정규화 행렬은 rank11/11·condition9.298, nuisance 투영 후 gamma basis 에너지34.64%가 남는다. 따라서 이 관측에서 완전한 선형 공선성/무자극 때문에 계산 불가능한 것은 아니다. 그러나 수치적 분리와 안정적·물리적 보정계수의 존재는 별개다. nuisance 계수는 재적합하지 않았고 숨은 열 상태·주변 온도를 실측했다고 하지 않는다.

과거10초 r을 미래에도 고정하는 **기존 후보의 에너지 보정**도 별도 진단했다(추정할 새 계수 없음). frozen service로 CPU/PAR 두 일정만 생성하고 C0는 알려진 유휴; 실제 미래 일정·전력·AP 입력은 없다. 10초 J MAE **0.884988→1.278181J**, 30초 **1.482205→2.999396J**로 악화했다. AP는 gamma0이라 동일(10초0.178374/30초0.179753°C). 모든 값은 세션별 평균 후 동일 가중치; J는 common120초 안의8/6발행점, AP는 냉각 끝 안의14/12발행점씩이다. 중첩 창을 독립 반복으로 취급하지 않는다. 가상 PC 발행이며 온라인 제어기나 독립 검증이 아니다.

## 4. CPU 활동에서 새로 알 수 있는 것과 모르는 것

각 세션24개5초 bin, 8CPU coverage/loss/clock 적격을 재사용했다. bench/tracer/other CPU초와 task-state 비율, 전력 잔차를 동시 정렬했다. 전체96bin을 독립96세션으로 회귀/검정하지 않았다.

other CPU율과 `관측W−동결W`의 세션내 상관은 C0_PRE +0.172, CPU +0.415, PAR −0.185, C0_POST +0.519로 일관된 방향이 아니다. bench/tracer를 포함한 표는 association.json. task4상태·block/세션 intercept·CPU3열 rank11/11이나 condition180.443으로 근접 의존도 있다. 숫자만으로 특정 프로세스의 J를 귀속하거나 단위 CPU초당 전력을 만들지 않는다. GPU·무선·주파수/전압별 비용·시간 지연·이전 열 이력은 이 단순 동시성 표로 원인을 확정할 수 없다.

## 5. 현재 범위와 종료 판단

확인된 구현 오류 해결(A), 단일 사후 후보 구현·평가 후 미채택(B)에 해당한다. **현재 네 자료에 대해 배경 보정 없이 기존 동결식을 유지한다.** 후보를 통과시킬 목적으로 gamma 부호·추정 구간·계수·threshold를 바꾸지 않는다. 추가 개발4 반복 또는 미채택 후보 확인12를 즉시 권고하지 않는다.

남은 과제는 작은 정책 차이가 기존 독립 확인의 예측 오차·세션 변동과 구분되는지다. 이번 네 자료만으로 정책 우월성이나 임의 이력 일반화를 보장하지 않는다. 배경활동이 모든 기존 큰 오차의 원인이라는 가설도 입증되지 않았다. 새 실측의 필요성/예산을 이번 결과만으로 자동 확정하지 않았다.

**다음 PC 작업 하나:** 기존에 확보한 독립 확인6의 정책별 에너지·AP 오차를 동결 정책 차이와 대조하여, 결과 화면에 `차이 판정 가능/보류` 경계를 연결한다. 새 후보 탐색·실측·정책 튜닝을 먼저 하지 않는다.

## 6. 재현과 검증

공유 소형 bundle만으로 원래 자료의 선택된 sample/상태/trace bin과 동결모형을 재현한다. 기기 식별자·원시 PID·명령 로그·모델 바이너리는 공유하지 않는다. 모델 JSON은 기존 동결 수치의 byte동일 복제이며 새 기본 모형이 아니다.

```powershell
python -B -m tools.d1_background_identification analyze --bundle docs/results/online_policy_study_01/background_identification_pc_v1/bundle --output '<없는 새 출력 폴더>'
python -B -m tools.d1_background_identification_report --folder docs/results/online_policy_study_01/background_identification_pc_v1
python -B -m unittest tools.test_d1_background_activity_result tools.test_d1_background_identification -v
```

원자료에서 bundle 생성(외부 archive 필요, 기존 bundle 덮어쓰기 금지):
```powershell
python -B -m tools.d1_background_identification bundle --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output '<없는 새 bundle 폴더>'
```

이미 저장된 run03/run04의 과거 분석 수치 재현 명령에는 `--legacy-preload-window`를 붙인다. 미지정 시 모형에 동결된 −20~30초를 사용한다. 새 분석 출력은 반드시 다른 폴더다.

관련 검증은 비상수 preload 경계·AP불변·원래 오류보존·부분분모·미래 power/AP/lane 오염 차단·개발/확인 분리·무자극null·gamma 음수경계·CPU 비입력·rank·hash drift·실제 CLI의 공유물 수치 재현에 한정했다. 첫 테스트 fixture의 음수 시작 schedule은 실제 AP 계약 위반으로 실패해 C0 원래 연속 일정으로 수정했다(제품 코드나 assertion 완화 없음). 이후 전부 통과. 전체 과거 배치·Android 빌드·기기명령0. 그림을 직접 열어 축·범례·조건/시간창을 확인했다.
