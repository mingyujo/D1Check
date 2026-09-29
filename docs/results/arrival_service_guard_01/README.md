# 저장 PC 정책 일정의 보수적 서비스 비교 규칙

[판정과 연구 범위](../../ARRIVAL_SERVICE_CHOICE_PC_20260930.md). `guard_contract.json`은 같은 입력의 `CPU_URGENT` 대비 24건 전부 완료, 긴급·일반 기한 미준수 비증가, 긴급 P95 비증가를 연구용 비교 조건으로 고정한다. 과거 `δ=0` 탐색과 달리 긴급 P95 손실도 제한한다. 실제 UX SLA나 에너지·AP 정확도 기준은 아니다.

`readout/guard_cases.csv`는 저장 PC 135개 일정의 조건별 결과, `readout/guard_summary.json`은 대표 queue/seed201/실현 간섭1.5와 45개 동일 입력 쌍의 집계다. 기존 결과를 이미 본 뒤 정한 규칙이므로 이 판독은 사후 분석이다. 전체창 J·AP와 정책 비용 순위는 `null`이며, 적격 사례를 실측 기반 절감이나 독립 예측 검증으로 해석하지 않는다. 저장 입력의 SHA를 계약과 검사하며 원본 일정·동결 모형·기기에는 접근하지 않는다.

저장소 루트에서 존재하지 않는 새 출력 경로로 재현한다.

```powershell
python -X utf8 -B -m tools.d1_arrival_service_guard --output "$env:TEMP/d1-service-guard-reproduce-new"
python -X utf8 -B -m unittest tools.test_d1_arrival_service_guard -v
```
