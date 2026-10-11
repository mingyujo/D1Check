# 기한·자원 호환성 기반 공동 리스트 서비스 Envelope

새 사용자의 최종 방법론 요청에 따른 별도 버전이다. 기존 실패·모형·기한·지원·기본·체크포인트를 보존했고 새 정책을 자동 채택하지 않았다.

248/384환경·학습0·오류0·16230/16230요청 완료. gate4+개발48+확인192+대표4. 새 확인은833110101..104×4부하×3문맥이며 동시 새RL도 같은 사전등록 자료를 사용한다. 과거827 결과 재사용이나 새 독립 실측은 아니다.

## 정책과 결과

| 정책 | 일반 기한 위반 | 조건별 P95 평균ms | 평균 ΔJ | 평균 ΔAP°C |
|---|---:|---:|---:|---:|
| Band | 42 | 354.076018 | +0.000000 | +0.000000 |
| Triton | 42 | 388.544694 | +0.455516 | +0.018737 |
| JointList | 42 | 398.753454 | +0.003913 | -0.000205 |
| CostList | 42 | 398.753454 | +0.003913 | -0.000205 |

두 정책 모두 원 strict FAIL/유망0이다. JointList/CostList의 전체 완료·일반 위반 건수는 Band와 같지만 긴급 P95가 악화하고 에너지도 평균 증가했다. AP의 미세 평균 감소를 서비스 악화와 바꾸어 성공으로 처리하지 않는다.

JointList=CostList 정확 일정은48/48. 대표96은 두 정책 모두 Band와 전체 일정 exact이며 새 기기 재생0이다. 같은 대표의 중복2회 측정으로 절감을 주장하지 않는다.

## 왜 비용 대안이 남지 않았나

selection_diagnostics.json은 물리 허용/예측 허용/실행 가능한 고유 행동과 실제 WAIT를 구분한다. PAIR 실행 순서만 다른 두 슬롯은 같은 자원 행동으로 집계하여 informative 수를 부풀리지 않는다. 과거/초기 최고가 global AP를 고정하는 예측 슬롯도 따로 센다.

고정5phase의 에너지는 120초 기본 에너지+상태별 점유초×증분W다. 같은 CPU/GPU 작업 multiset과 서비스 벡터라도 CG_DC 병행초가 바뀌면 J가 바뀔 수 있다. pair 비가산계수는 -0.2979983819423944W다. 같은 routing/병행초일 때만 J가 불변이다. J_invariance.json은 실제 대응 차이와 해당 식의 잔차를 보존한다. 열 경로는 작업 시각·공통 초기 상태·180초 꼬리에 의존하므로 같은 J가 같은 AP를 보장하지 않는다.

전체 현재 큐의 완료/기한/지각을 먼저 최소화하고 드레인 ECT를 빠르게 해도 긴급 P95 비악화와 같은 목적은 아니다. 이 새버전의 더 큰 학습이나 규칙 추가가 개선을 보장하지 않는다. 모형 차이는 표면온도/실제 절감 검증이 아니며 고정5phase 모형에 냉각→속도 회복은 없다.

## 근거와 재현

[화면](index.html) · [설정/사전등록](execution_contract.json) · [KPI CSV](comparison.csv) · [선택 진단](selection_diagnostics.json) · [상태별 에너지](energy_decomposition.csv) · [불변성](J_invariance.json) · [대표 일정/해시](representative_receipt.json) · [검증](verification.json)

```powershell
python -B -X utf8 -m unittest tools.test_d1_service_envelope_policy -v
python -B -X utf8 -m tools.d1_service_envelope_run check
python -B -X utf8 -m tools.d1_service_envelope_report
```

후처리는 원 local gz가 있는 workspace에서만 수행한다. 새환경·학습·기기·fit0이며 완료 run/등록을 반복해 예산을 초기화하지 않는다. 강한 새학습 참조 API는 tools/d1_service_envelope_policy.py의 Controller(mode=JOINT), 같은 bank/encoder PPO는 mode=r.PPO다. 새 semantic SCHEMA·fresh actor만 허용한다. 기존 L0/32/512 actor는 재사용하지 않는다.


## Stored forecast guard attribution

[Guard attribution](guard_attribution.json): 866 physical/known AP-J-improving slot-events, admitted0; CPU-only alone273, CPU-only+fixed wait353, miss/lateness+CPU-only+fixed wait240. These are repeated slots, not independent trials. The first low witness has21 unarrived requests, so current-queue deadline/P95 preservation is not full-trace service proof. No new environments.
