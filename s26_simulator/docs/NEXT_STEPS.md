# 다음 사람이 바로 할 일

1. **처리 단계 전이 수리부터.** `research/fit_phase_transfer_v1.py`, `models/phase_transfer_NOT_ADOPTED.json.gz`, 원 `PHASE_TRAIN_ROWS/FINAL_MODELS/VALIDATION_ROWS`를 읽는다. 조건부 모델의 JS/Python 동등성을 확인하고 원 whole-vector의 상관과 exact0 단계, normal readback/persist/release 상대 위치를 보존하는 동적 적용을 설계한다. 현재 base physics를 조용히 덮어쓰지 않는다.
2. **모형 정확도와 정책 개입을 분리.** R21의 실제 활동에 고정한 비용 예측과 생성 일정의 비용 차이를 대조한다. CPU/GPU/NPU 자동 선택이 전부 NPU로 모이는 이유를 명목 시간·에너지/열 대리값, mask, queue/기한, 좁은 초기온도로 분해한다. 억지로 자원 사용률을 분산하거나 물리계수를 튜닝하지 않는다. GAP의 R21 악화·전체 손해도 유지한다.
3. **환경 검증 후 새 RL.** 새 소스·동결 모델·데이터/입력·환경/fit/cost-query 예산을 등록한다. DEV-only 선택/SHA봉인 후 별도 새 평가. 롤링+ATC joint 및 residual PPO, 필요시 승인된 IE 최적화 대안을 비교한다. 과거 RL을 최신 엔진 결과로 붙이거나 관찰한 평가로 다시 선정하지 않는다.

등록 cap512는 이미500소비했다. 남은12를 자동 재시도로 쓰지 않는다. 전체 공동 예산과 다른 기기 최신 예약을 확인하고 필요한 추가 범위를 별도 등록해야 한다. 기존 자동화는 PAUSED 유지다.

## 후속 산출물의 최소 판독

모든 학습seed·부하·초기이력·시간/비용 불확실성에서 서비스70/80/90/95/100%, 긴급/일반/전량완료, 응답 P95/납기손해/미완료, 실제 route/겹침/WAIT, J0~180·AP35~180·peak·180초 잔열을 함께 본다. 납기·완료량을 희생한 절감은 개선이 아니다. 조건부 변동 범위를 전체 모형 신뢰구간이나 독립 폰 표본으로 부르지 않는다.
