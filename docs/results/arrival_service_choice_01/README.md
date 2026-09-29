# 저장된 도착 정책의 응답·완료 판독

[한국어 결과와 지원 경계](../../ARRIVAL_SERVICE_CHOICE_PC_20260930.md). `readout/service_cases.csv`는 low/queue/burst × 실현 간섭 1.0/1.5/2.0 × seed201–205 × CPU_URGENT/B2/B3의 저장 PC 일정 135개다. `readout/service_groups.csv`는 각 5 seed 집계 27행이다. 완료 응답 지표와 전체 예정 요청 기준 기한 내 완료를 분리한다. `readout/representative.json`은 사전 선정 queue/201/1.5의 세 정책과 저장 PC 상태 이름·120초 점유·지원 차단·출처 SHA를 담는다. J·AP는 `null` 또는 CSV 빈 칸이며 0이 아니다.

저장소 루트에서 새로운 출력 경로로 재현한다. 기존 일정 엔진이나 기기 실행은 호출하지 않는다.

```powershell
python -X utf8 -B -m tools.d1_arrival_service_choice --output "$env:TEMP/d1-service-choice-reproduce-new"
python -X utf8 -B -m unittest tools.test_d1_arrival_service_choice -v
```

연구용 긴급1.5초/일반6초는 실제 SLA가 아니다. 기존 B2/B3 정책·A24 동결 계수·측정 범위는 변경하지 않았다.
