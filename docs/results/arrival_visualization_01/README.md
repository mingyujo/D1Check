# D1Check 오프라인 PC 시각화

[대시보드](dashboard.html)는 파일을 바로 열면 된다. 서버·CDN·네트워크 요청이 없다. 기본 화면은 사전 대표 `queue / explore / CPU_URGENT`다. low·queue·burst, 8정책, strict·explore profile을 바꿔 볼 수 있다. 여기서 `profile`은 **PC 시간/병행 가정**이며 임의 도착의 측정된 전력·열 profile이 아니다.

| 그림 | PNG / SVG | 숫자 CSV | 근거 경계 |
|---|---|---|---|
| 대표 queue 응답 | [PNG](queue_response.png) / [SVG](queue_response.svg) | [service.csv](service.csv) | 기존 PC 평가 seed 201–205의 반복별 지표 평균 |
| 가정 민감도 | [PNG](sensitivity.png) / [SVG](sensitivity.svg) | [sensitivity.csv](sensitivity.csv) | P−B3 쌍차; 기본 3조건과 원본의 간섭·추정·부하·host 변경 총 12조건 |
| 고정 묶음 상충 | [PNG](fixed_tradeoff.png) / [SVG](fixed_tradeoff.svg) | [fixed_870_comparison.csv](fixed_870_comparison.csv) | **별도** A24 고정 870건 직렬/병행 실측 재생, 조건부 전류 단위 |
| 고정 묶음 에너지·AP 경로 | [PNG](fixed_model_path.png) / [SVG](fixed_model_path.svg) | [fixed_870_model_curve.csv](fixed_870_model_curve.csv) | **별도** 개발 동결 모형을 확인 시작 온도에 적용한 사후 모형 예측 |

[timeline.csv](timeline.csv)는 각 조합의 대표 seed 201 예정 도착·dispatch·실행·출력·저장·worker/lane 해제 경계다. 기존 bundle의 queue/explore 대표 trace 8개를 재사용하고 나머지 대표 trace **40개만** 같은 동결 입력으로 재생했다. 각 대표 trace의 긴급 P95·일반 평균·완료·기한·makespan 등 7지표를 원본 `arrival_explore_batch_v3/metrics.csv`의 같은 seed와 대조했다. 전체 960평가·126개발 실행은 반복하지 않았다. [원본 SHA-256](SOURCE_HASHES.json)을 함께 저장했다.

합성 도착의 에너지·AP는 상태별 계수가 미측정이므로 **계산 불가**다. 고정 870건 그래프의 J·AP를 low/queue/burst에 이식하지 않는다. 대시보드의 고정 묶음 그래프는 별도 참고 자료이며 시나리오/정책 필터 결과가 아니다. 확인 block에서 병행은 직렬보다 완료시간 126.319초·완료시점 에너지 143.341J 낮았지만, 공통 480초 에너지는 4.559J·AP 최고온도는 1.9°C 높았다. 각 arm의 개발/확인 독립 세션은 하나씩이므로 인과효과·반복 안정성·정책 우월성을 주장할 수 없다. 전류 raw의 A24 mA 해석과 절대 J 정확도는 조건부이며 BAT 모형은 미지원이다.

긴급 응답은 예정 도착→`output_ready`, 일반 응답은 예정 도착→`persist_complete`다. lane 해제는 별도다. P95는 각 반복의 완료 긴급 응답 6건에 nearest-rank를 적용한 값 5개의 평균이다. 미완료는 예정 전체 분모에 남긴다. 이번 선택 조건의 미완료는 0/120이지만 이는 다른 조건의 실패율 0을 뜻하지 않는다. 반복 5회는 독립 실기기 표본이 아니다.

저장소 루트에서 재현:

```powershell
python -m tools.d1_arrival_visualize --metrics 'C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_explore_batch_v3/metrics.csv' --output docs/results/arrival_visualization_01
python -m unittest tools.test_d1_arrival_visualize -v
```

기본 재현에는 위 로컬 기존 평가 `metrics.csv`가 필요하다. 이 원본은 Git 공유 대상이 아니지만 생성된 작은 CSV/그림/HTML은 포함됐다. 브라우저 확인은 설치된 Chrome의 로컬 `file://` headless 렌더 및 low/strict/B2, burst/explore/P 필터 이벤트로 수행했다. 실기기 합성 도착 수집은 미실행이며 `experiment_ready=false`다.
