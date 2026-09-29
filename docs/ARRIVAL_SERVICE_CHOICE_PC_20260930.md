# 저장된 동적 정책의 응답·완료 판독과 비용 비교 경계

2026-09-30 PC 판독. 착수 HEAD `0e254327891cf28a6d9aefab278f2294577db02b`, 작업 트리 clean. [기존 정책 지원 감사](ARRIVAL_MEASURED_SUPPORT_BOUNDARY_20260929.md)의 저장 135개 일정과 이미 선정된 `queue/seed201/실현 간섭1.5`를 재사용했다. 시뮬레이션 배치·실측·계수 적합은 수행하지 않았다.

## 판정

**저장된 PC 일정의 응답과 완료는 비교할 수 있지만, 이 사례에서 실측 기반 J·AP 정책 순위는 계산할 수 없다.** 1.5초 긴급·6초 일반 기한은 연구 입력이며 채택된 서비스 SLA가 아니다. 예정 24건 전체를 분모로 기한 내 완료를 세었고 완료 응답 P95와 구분했다. 저장 엔진은 실패·미완료도 기한 미준수로 세는 규칙을 사용한다. 이번 135개 저장 일정에는 미완료가 0개지만, 이를 실기기 서비스 성공으로 전용하지 않는다.

| queue/201/1.5 저장 PC 정책 | 완료 | 긴급 P95, 완료 응답 | 일반 평균, 완료 응답 | 긴급 기한 내 | 일반 기한 내 | 전체 기한 내 |
|---|---:|---:|---:|---:|---:|---:|
| CPU_URGENT | 24/24 | 641.346 ms | 4515.765 ms | 6/6 | 12/18 | 18/24 |
| B2_PC | 24/24 | 424.755 ms | 4188.833 ms | 6/6 | 14/18 | 20/24 |
| B3_SOLO_EFT_PC | 24/24 | 1014.998 ms | 4044.433 ms | 6/6 | 14/18 | 20/24 |

B2와 B3의 기한 내 완료 수는 같지만, B2 긴급 P95는 약 590.243 ms 짧고 B3 일반 평균은 약 144.400 ms 짧다. 응답만으로도 단일 승자를 확정하려면 어떤 손실을 허용할지 사전 기준이 필요하다. 영(0) 기한 미준수를 요구하면 이 대표 사례에서 세 정책 모두 해당 조건을 충족하지 못한다. 같은 queue/실현1.5의 5 seed 합계는 CPU 94/120, B2 100/120, B3 103/120 기한 내 완료다. 이는 **PC 입력 5개**의 기술 통계이며 독립 기기 세션 5개의 변동성 추정이 아니다. 전체 [135개 사례](results/arrival_service_choice_01/readout/service_cases.csv)와 [27개 입력군의 5 seed 집계](results/arrival_service_choice_01/readout/service_groups.csv)를 공개한다. 135개 중 55개만 해당 연구 기한 내 24/24이며, 채택된 SLA의 합격 사례 수가 아니다.

## 보수적 서비스 비교 규칙의 사후 판독 (2026-09-30)

과거 [허용폭 분석](ARRIVAL_DELTA_SELECTION_20260925.md)의 `δ=0`은 일반 요청의 기한 미준수 증가를 허용하지 않는 **탐색점**이었고, 실제 UX SLA로 채택되지 않았다. 이번 [연구용 규칙](results/arrival_service_guard_01/guard_contract.json)은 같은 trace·실현 간섭·seed의 `CPU_URGENT`를 기준으로, 예정 요청 24건의 전부 완료, 긴급·일반 기한 미준수 건수 비증가, 완료된 긴급 응답 P95 비증가를 동시에 요구한다. 일반 평균 응답은 보고하되 적격성 조건으로 사용하지 않는다. 기존 δ 분석을 소급 변경하거나 새로운 정확도 PASS·허용오차를 만든 규칙이 아니다. 이미 본 135개 PC 결과에 적용한 아래 숫자는 **사후 판독**이며, 향후 독립 자료에서 이 규칙을 고정해 평가할 수 있다는 것과 구분한다.

사전 선정 `queue/seed201/실현 간섭1.5`에서는 B2가 기준 대비 긴급 P95 −216.591 ms, 일반 기한 미준수 −2건으로 적격이고, B3는 일반 기한 미준수 −2건이지만 긴급 P95 +373.652 ms로 이 보수적 규칙에서 부적격이다. 45개 동일 입력의 저장 PC 쌍에서는 B2 21개, B3 22개가 각각 적격이며 둘 다 적격인 입력은 7개다. 이는 서로 다른 PC 입력에서의 개수이며 독립 실기기 반복 수나 정책 우수성의 확률이 아니다. [사례별 판독과 계약](results/arrival_service_guard_01/README.md)에 실패한 조건까지 남겼다.

이 대표 입력에서는 B3의 J·AP가 유리하더라도 위 서비스 규칙의 비교 후보가 되지 않는다. 둘 다 적격인 7개 입력에서도 전체창 실측 기반 J·AP는 모두 미지원이다. 그중 burst 두 입력에는 별도 미계측 상태가 있고, 나머지에는 도착 전환·초기 AP 지원과 독립 예측 확인이 남는다. 따라서 적격성 선별은 비용 순위가 아니며, 사용자 서비스 요구가 긴급 P95 악화를 허용한다면 그 허용폭은 **새 독립 평가 전에** 별도로 정해야 한다. 이번 자료를 보고 B3가 들어오도록 기준을 조정하지 않았다.

## 같은 사례의 실측 모형 차단

[저장 지원 판정](results/arrival_policy_screen_01/measured_support_01/support_status.csv)에서 세 정책 모두 120초 전체 에너지에 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`, AP에는 `UNSUPPORTED_INITIAL_AP_AND_ARRIVAL_TRANSITIONS`가 적용된다. 초기 AP 29°C는 기기 관측이 아닌 PC 탐색 가정이다. 에너지의 첫 차단은 t=0의 장구간 전용 모형 범위, AP의 첫 차단은 초기조건 미관측이다. 첫 실제 전환은 세 일정 모두 t=0.000300초 `idle → detection:CPU`다. 따라서 J·AP를 0이나 가정 profile 수치로 채워 정책을 순위화하지 않았다.

대표 120초 일정의 모델별 병행 lane 점유는 B2의 `classification:GPU+detection:CPU` **2.531초**, B3의 `detection:CPU+detection:GPU` **8.326초**, `classification:GPU+detection:CPU` **1.324초**, `classification:CPU+detection:GPU` **0.688초**다. 이는 lane 점유이며 같은 시간만큼 GPU kernel이 겹쳤다는 뜻이 아니다. 각각 48회 상태 전환이 있고 CPU_URGENT도 유휴↔짧은 CPU 단독 전환을 사용한다. 이 사례에는 동결 파일에서 이름 자체가 없는 상태는 없지만, 긴 반복 블록의 상태별 평균 계수만으로 이러한 짧은 전환을 지원한다고 할 수 없다. [대표 일정 그림](results/arrival_policy_screen_01/measured_support_01/representative_schedule.svg)은 저장 PC 일정이다.

**최소 해제 조건:** 같은 A24·모델/입력·resident·센서 계약에서 유효한 실제 시작 AP, 짧은 단독/CG_DC/DC_DG/CC_DG와 유휴 전환의 실제 lane 경계, 전류·전압·AP, 공통120초 전체, 예정24건의 완료·실패를 확보하고 자료 적격성과 동결식 오차를 별도로 판정해야 한다. 이미 본 B2 단일 진단과 기존 장구간 개발값은 재사용하되 서로 다른 프로토콜을 독립 정책 확인으로 합치지 않는다. 실제 정책 선택을 확인하려면 B2·B3 직접 실행 일정도 필요하며, 현재 저장 PC 일정만으로는 이 증거가 없다. 상태 비용 확인과 정책 직접 비교는 서로 다른 완료 조건이다. 허용 에너지/AP 오차와 응답 손실 기준은 결과를 본 뒤 설정하지 않는다.

## 재현과 검증

[작은 결과와 출처 SHA](results/arrival_service_choice_01/README.md)는 기존 `service_metrics.csv`·`support_status.csv`를 읽는다. 입력의 저장 manifest SHA와 135개 키·24요청 분모·지원 차단을 검사한다. 개인 PC 원자료 경로 없이 새 출력 디렉터리로 재현한다.

```powershell
python -X utf8 -B -m tools.d1_arrival_service_choice --output "$env:TEMP/d1-service-choice-reproduce-new"
python -X utf8 -B -m unittest tools.test_d1_arrival_service_choice -v
```

2026-09-30 02:07 KST, 출발 HEAD `0e254327891cf28a6d9aefab278f2294577db02b`와 이번 미커밋 코드·문서에서 위 재현 명령 및 별도 CSV/JSON 분모 검사 PASS. 관련 PC 테스트 2건은 저장 결과의 135사례, 대표 18/24·20/24·20/24, B2/B3 응답 상충, 미지원 J·AP null, 전체 예정 요청 분모와 입력 불변을 확인했다. `git diff --check` 통과. 기기 명령 0회. 기존 동결 모형·원자료·FAIL·소비 계획과 `experiment_ready=false` 유지.
