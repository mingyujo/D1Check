# CPU 시작 전 정보 후보: 미채택

[한국어 판독](../../CPU_PREBASELINE_RESULTS_20261010.md) / [화면](index.html) / [사전 계약](analysis_contract.json) / [실제 소비](run_v1/receipt.json) / [검증](verification.json).

개발6의 부하 전 전력/CPU로 한 계수를3회 추정(회복시간 블록 제외2＋최종1)했다. 이미 본 확인6의0..120초 J MAE는 δ=0 보완식4.564→5.522J로 악화해 미채택한다. 실제 일정 조건부 비용·오프라인 기록 진단이며 온라인 정책/실시간 CPU API/독립 정확도 PASS가 아니다. AP·기본/RL/strict/experiment_ready=false는 유지한다.

- `run_v1/pre_inputs.json`, `pre_bins.csv`, `pre_features.csv`: 예측 전에 발생한 정보만의 공유 입력. 실제 미래 전력/AP/CPU는 없다.
- `run_v1/candidate_{30,180,final}.json`: 새 계수1개, 기존4전력계수·AP는 별도 frozen 파일 유지. 각 세션 결과를 보고 모델을 선택하지 않는다.
- `run_v1/energy_errors.csv`, `energy_curves.csv`: 모든12/모든창의 적분·부호 오차 및 누적경로. 관측과 예측을 구분한다.
- `readout_v1/paired_errors.csv`, `role_summary.csv`, `feature_and_idle_readout.csv`: 개선/악화·관측된 지원 밖 입력·사후 idle 표적 구분. 좋은 세션만 남기지 않는다.
- `source_amendment.json`, `source_snapshots/`: 새 후보 RMSE 표시의1줄 수정 기록. 최초 source/모델·receipt 불변, 계수 및 J 차이0, 재추정0. 올바른 RMSE는 `readout_v1/readout.json`.
- `figures/*.png`, `*.svg`: 같은 분모의 전량오차, C0의 시작 전 CPU/전력, C0 누적잔차. 새 실측 그림이 아니다.

## 작은 공유 입력으로 재현

저장소의 다른 frozen JSON/공유 입력이 함께 있어야 한다. 기본설정·RL·기기에는 적용되지 않는다.

```powershell
python -B -m unittest tools.test_d1_cpu_prebaseline -v
python -B docs/results/cpu_prebaseline_01/run_example.py --opt-in --output output/cpu_prebaseline_example.json
python -B docs/results/cpu_prebaseline_01/plot_results.py --output output/cpu_prebaseline_figures
python -B docs/results/cpu_prebaseline_01/readout.py --output output/cpu_prebaseline_readout
```

출력은 새 경로여야 한다. 예제/판독/그림 명령은 추정0·기기0이며 새 원자료가 필요하지 않다. readout은 별도 데이터 루트가 없으면 raw 검증을 생략했다고 숫자0으로 기록하며 관측값을 대체하지 않는다.

## 원본부터의 분석 재현

실제로 사용한 명령:

```powershell
python -B -m tools.d1_cpu_prebaseline --action prepare --external-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension' --output docs/results/cpu_prebaseline_01/run_v1
python -B -m tools.d1_cpu_prebaseline --action run --output docs/results/cpu_prebaseline_01/run_v1
python -B docs/results/cpu_prebaseline_01/readout.py --output docs/results/cpu_prebaseline_01/readout_v1 --external-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension'
```

`run_v1`은 완료되어 차단된다. 의도적인 원본 재현에는 별도의 새 출력 경로와 데이터 루트를 지정한다.3fit을 다시 시작하지 않고 위 공유 예제/판독으로 확인하는 것을 우선한다. 최신 source는 RMSE 표기만 고쳤으므로, 원run의 source 해시는 snapshot/amendment와 함께 확인한다.

원자료 의존성은 `run_v1/source_inventory.json`의12 `source_locations`를 기준으로 한다. 각 폴더의 `artifacts/history_boundary.json`, `trace_export/{sched,clock,loss,cpu,audit,export_binding}.csv/json`가 필요하다. raw 원본 확인에는 `thermal.jsonl`, `artifacts/conditioning_requests.json`, `system_activity.pftrace`도 필요하다. trace clock은 Android BOOTTIME exact이고 loss/unknown/coverage 부적격을0으로 채우지 않는다. 개인 파일 경로·기기 식별값·대용량trace를 공유물에 넣지 않았다.

CSV export는 세션 종료 후 생성됐으며 사건 시각상 pre 정보와 실제 사용 가능한 실시간 API를 혼동하지 않는다. A24 current raw=mA, 절대J 정확도 미인증. 다른 기기·임의 부하·다른 horizon·미검증 병행 전력으로 확장하지 않는다.
