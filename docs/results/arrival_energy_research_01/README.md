# 합성 도착 연구 PC 계약 v1

이 폴더의 `scenario_manifest.json`은 기존 `d1_arrival_explore_batch.workload(..., 'evaluation')`에서 **low / queue / burst** 24요청씩만 추출한 ID·분모·SHA-256이다. 정책 성능 결과가 아니다. 기존 960실행을 다시 수행하거나 평가 자료로 B2를 다시 고르지 않았다.

재현(저장소 루트, Python 3):

```powershell
python -m unittest tools.test_d1_arrival_energy_research -v
python -m tools.d1_arrival_energy_research --manifest-out "$env:TEMP/d1-arrival-energy-manifest.json"
```

두 번째 명령은 출력 파일이 없을 때만 기록한다. 생성 JSON을 이 폴더의 manifest와 비교한다. `tools.d1_arrival_energy_research.aggregate(requests, result, horizon_ns=...)`는 기존 이벤트 엔진의 `ledger`를 받아 긴급 output_ready/일반 persist_complete, 전체 예정 요청 분모, 120초 공통창, lane release를 분리한다. 결과에 전력 profile이 없으면 에너지/AP는 `UNSUPPORTED_MISSING_ARRIVAL_STATE_PROFILE`과 `null`이다. `explicit_assumptions` profile을 명시적으로 넣는 경우에만 기존 `d1_energy_thermal.account`로 공통창의 상태별 기기 전체 에너지와 AP 경로를 탐색 계산한다. 그 수치는 실측 보정값이나 성능 판정이 아니다. 준비·냉각은 이 공통창 밖이며 별도 계측 전에는 0으로 더하지 않는다.

입력과 상태 지원 표, 정책 대응, 다음 계측의 목적은 [연구 계약](../../ARRIVAL_ENERGY_SYNTHETIC_RESEARCH_20260926.md)에 있다. Android 실행 명령이나 새 실측 승인은 없다.
