# 온라인 정책 모형의 독립 확인 결과

실측 개발3(03의 성공2＋04의 새1)→계수 동결→04 확인6을 완료했다. [전체 보고서](../../../ONLINE_POLICY_MODEL_STUDY_20261002.md), [대시보드](index.html), [일정 그림](details/schedules.svg), [정밀 오차표](details/detailed_metrics.csv).

- 입력: A24·등록 resident4·분류 urgent24/탐지 normal72, +35초부터 개발500ms/확인550ms, common120초/냉각60초. CPU직렬/CG_DC병행/CG_DC직렬.
- 이후 관측 AP/전류/실제 일정을 예정도착 예측의 입력에 넣지 않는다. 초기 입력은 부하 전AP와10–30초W이다. 실제 계산은 회수 후이며 실시간 사전 발행이라고 하지 않는다.
- 독립 확인96/96마감은6개 모두 충족. 예정도착 에너지 오차 −0.291…−15.941J, AP MAE0.152…0.605°C. 정확도 PASS나 정책 우월성은 아니다. 에너지 작은차이와 AP최고0.1–0.2°C 차이를 확정할 정밀도가 부족하다.
- `same_initial_policy_predictions.csv`는 첫 CPU 확인의 같은 초기입력을 넣은 세 정책의 모형상 비교(1초 AP grid)다. 그 조합 모두를 동일 초기조건에서 실측한 것은 아니다.
- `actual_rows`의 주요 경계(dispatch/execution/output/persist/worker/lane와 scheduled/actual arrival)는 공통창 상대ns다. 원본에서 그대로 남긴 host inference/queue/deadline 필드는 절대Android monotonic일 수 있으므로 혼합 산술에 사용하지 않는다. 일관된 상대초 공유표는 `details/request_boundaries.csv`를 사용한다.
- lane 그림은30–100초 확대, 에너지 전체창은0–120초, 예측 이후 에너지는35–120초, AP 점수는각 실제관측35초 이후~180초다. 짧은 혼합 전력 표본을 개별 요청 전력으로 해석하지 않는다.
- raw=mA 조건부·절대J 미인증. 새로운 APK 구성 처리/시간공백/초기 이력 차이 보존. 기존 모형/strict/default/experiment_ready=false 불변.

```powershell
python -B -m tools.d1_simulator online-policy --case-id confirmation_0_CPU_URGENT_ONLINE_V1 --policy B2_PARALLEL_ONLINE_V1 --output output/online_parallel_fresh
```

공유 bundle만으로 재현 가능하다. output은 새 경로여야 한다. 지원되지 않는 도착/초기온도/thermal feedback/strict 선택은 차단한다. 원본 기반 재추출과 소비/소스/모형 해시는 보고서를 따른다. 이 폴더 이름 run02는 공유 번들 이름이며 외부 실행원본은 **online_policy_study_run_v4**, 재사용 개발은v3이다.
