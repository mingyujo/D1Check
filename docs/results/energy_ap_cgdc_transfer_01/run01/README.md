# CG_DC 전이 확인1 — 2026-10-01 실제 관측

[보고서·소비·판독 경계](../../../AP_CGDC_TRANSFER_RUN01_20261001.md), [독립 HTML](index.html), [소비/검증 요약](summary.json), [원래식·후보 점수](report.json).

별도1세션은24요청/32명시적 추론 완료, 정확한120초 관측135.146493J 대 동결식155.730344J(+20.583851J). AP35.008859002–180.062298472초의 기존/후보 MAE5.831406/0.463463°C. 원래 burst/201 도착과 release35초 지연의 기록 재생이며 온라인B2/서비스 확인이 아니다. 시작 AP28.3°C/짧은 전환은 strict 지원 밖이다. 부하 전 AP25표본으로만 후보의 유효 유휴 기준을 계산하고 부하 후 재적합하지 않았다. 최고/한도/정책 순위/accuracy PASS는 미판정이다.

- `timing.csv`: ordinal 기준 예정·실제 도착/dispatch/output/persist/worker/lane. PC 미래 일정이 주어진 재생이다.
- `data/actual_states.csv`: dispatch→lane_available 상태. CG_DC1.466752초와 host inference 겹침0.910225초를 구분한다.
- `data/energy_path.csv`, `phase_energy_residuals.csv`: 정확한120초 누적 J와 부하 전/중/후 잔차. 세 구간 모두 양수다.
- `data/ap_paths.csv`: 실제 일정·부하 전 AP 조건부 진단. 정보 시점 이후만 출력하며 후반 재상승 형태 한계가 남는다.
- PNG/SVG3쌍: 관측·원래식 외삽·고정 후보를 구분한 실제 결과. 정확도 합격/정책 우열 그림이 아니다.
- `idle_comparison/`: 기존 B2·유휴 개발/확인·이번 전이의 사후 유휴 W/잔차 CSV·원문 해시·평균전력 PNG/SVG. 경계 혼합 제외 후에도 조건 차이가 남고 계수 재적합은 없다. 전체120초와 잘린 유휴 구간을 구분한다.
- `shared_inventory.json`: 작은 공유 묶음만의 크기/SHA. 원본 inventory/receipt·키/APK/모델/기기 식별정보는 외부에 보존한다.

원본 의존: 외부 `energy_ap_cgdc_transfer_run_v2`의 FINAL_RECEIPT, 같은 session artifacts의 manifest/requests/common_boundary/start_ap.accepted/progress/cleanup, host thermal.jsonl, 원래/후보 freeze. exact 경로/해시는 동결 collection_plan.json과 외부 inventory에 있다. CSV/그림 열람에는 외부 파일이 필요 없고 재분석에는 원본이 필요하다.

```powershell
# 기기 명령/claim 없이 PC 판독만, 기존 output과 다른 새 폴더를 지정한다.
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_ap_transfer_report --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/collection_plan.json' --output '<새 PC 출력 폴더>'
```

plan_v2는 소비·완료로 재실행 거절된다. 기존 미래 실측 준비 문구는 당시 이력이며 FAIL·모형·strict·`experiment_ready=false`를 유지한다.
