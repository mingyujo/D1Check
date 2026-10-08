# EDD+ECT 보정 정책의 학습 전 검증 결과

2026-10-08 · `EDD-ECT-RESIDUAL-PROTOTYPE-01`

**실제 선택 폭과 작은 모형 열 개선 신호는 확인했다. 강한 기준선보다 좋은 학습 정책은 아직 없다.** 기한 검사 뒤 EDD+ECT를 우선하는 prior는 원 EDD 일정과12/12동일했다. 열 greedy는 저부하에서 약0.002°C의 grid AP 감소를 만들었지만, 지속 부하에서는 긴급 응답과 AP를 악화했다. 결과에 따라 설계의 B/C를 통과한 모형 탐색으로 기록하며 정책 채택이나 기기 성과로 승격하지 않는다.

[오프라인 화면](index.html) · [전체60행](results.csv) · [비교72행](pairs.csv) · [조건별 요약](policy_summary.csv) · [사전 등록](registration.json) · [완료/소비](completion.json) · [원 분기](branches.json) · [실제 실행 차이](physical_branches.json) · [집계와 gate](summary.json).

## 조건과 실행 규모

이전48개 개발 조건 중 최소 seed610810001의4부하×3처리문맥=12조건을 결과 전에 고정했다. 비교는 EDD+ECT·SHARED_EFT·Band 요청 적용·기한검사 prior·열 greedy의5정책이다. 총60행, 예정3,960건 모두 완료다. 부하별24/192요청, 긴급1.5초·일반6초, 모델5682082a·초기값42f60312·공통 J0..120/AP35..180초1초격자·실현seed201을 유지했다. 이 조건은 이미 본 합성 개발 자료이며 새 미열람 시험이나 휴대폰 실험이 아니다.

새 환경 시작91회=기능fixture6+비교60+분기24+실패1이다. 실패는 SHARED 행동 마스크가 리스트인 결과 형식을 정수로 처리한 집계 오류이며 정책·입력·선택·판정 기준은 변하지 않았다. [수정 계보](metadata_repair.json)로 기존 source/실패/clock을 보존하고 대체 실행도 사전 차감했다. 기존2,825+91=**2,916/20,000**, 잔여17,084다. 학습 episode·기기·ADB0회다.

## 판단과 재현 검증

- 원 EDD adapter와 새 BASE wrapper의 전체 요청 원장은 mean/short/long 세 문맥에서 동일했다. 순수 event 예측의 dispatch·응답·lane 반환도 엔진 일정과 일치했다(정수 표현≤1ns 대조, 원 기한 판정은 완화하지 않음).
- 판단 규칙14검증은 ECT lane 완료/응답 구분, 자원 대기 중 대안, 실제 점유·overrun·미래/비공개 입력 차단, 냉각 credit, 묶음 확정·취소, 전체 Q 검사, 후보 중복과109/68 schema, 공통 AP 계산을 확인했다. 이 중 불가능한 classCPU+classGPU 병행을 가정한 테스트 한 건을 지원된 detCPU+classGPU 사례로 바로잡았다. 초기 실패를 성능 실패로 섞지 않는다.
- 현재 관측 phase의 예상 끝이 이미 지나갔으면 잔여를0으로 만들지 않는다. 필요한 phase 잔여가 없으므로 보정을 중단하고 정확한 BASE로 복귀한다. lane 전체 잔여만 검사하던 이전 설계보다 구체화한 예측 가용성 경계다.
- 사전 지정한 최초 BASE/비BASE 적격 분기12쌍은 앞부분 실제 일정·공개 상태 hash가 같았고, 이후12/12에서 실제 dispatch 집합 또는 다음 공개 사건의 점유가 달랐다. 좋은 분기를 골라 다시 실행하지 않았다.
- 결과 판정6검증은 미완료·P95 증가·J 증가·약한 자기 기준만의 개선·잔존 기한 위반을 성공으로 처리하지 않음을 확인했다.

## 결과와 적용 범위

| 전체12조건 정책 | 긴급 실패 | 일반 실패 | 조건별 긴급P95 평균(ms) | 평균J | 평균 grid AP(°C) |
|---|---:|---:|---:|---:|---:|
| EDD+ECT |0|14|320.585950|152.413992|30.806121|
| SHARED_EFT |0|9|355.655865|152.320476|30.850062|
| Band 요청 적용 |0|9|355.655865|152.299685|30.845730|
| 기한검사 prior |0|14|320.585950|152.413992|30.806121|
| 열 greedy |0|15|381.718124|152.215243|30.840907|

모든 policy가792/792건을 완료했지만 전기한 조건은각6/12다. 평균 J가 작은 greedy를 전체 승자로 부를 수 없다. 주6(low/sustained)에서도 greedy의 긴급P95는327.498ms, Shared/Band225.117ms이며, 평균 AP31.259°C는 두 기준31.225/31.216°C보다 높다.

낮은 부하3처리문맥의 greedy는 세 기준 모두 대비 긴급P95/J 변화0, AP−0.002154..−0.002214°C다. 일반 평균 완료는각+55.556ms이며 전체 기한은 유지했다. 같은 **한 trace의 세 가정 문맥**이지 독립3seed의 물리 검증이 아니다. [0.1초+전이경계 추가 표본](ap_sampling_sensitivity.csv)의 감소도−0.004375..−0.004389°C로 방향을 유지하지만 연속 최고값 인증이나 실기기 분별 가능성을 뜻하지 않는다. 기존1초 KPI를 바꾸지 않는다.

지속 부하에서 Band 대비 greedy는 J−0.504..−0.578J와 함께 긴급P95+185.460..+224.723ms, AP+0.079716..+0.104940°C였다. 대기열/급증의 AP 감소 중에는 J 증가·일반 기한 손실이 남는다. 최초 분기 대안에서는 세 기준을 모두 만족하는 추가 C witness가 없었다.

따라서 B는 실제 실행 선택 폭, C는 작은 저부하 모형 신호에 한정해 PASS다. A의 비학습 규칙은 검증했고 RL archive는 별도 구현/검증 대상, D의 본학습 시간·입력·cache·회계 등록과 E의동결 검증은 미완료다. PPO/RL 성능·본학습0이다. 학습 진입 조건을 낮추거나 기존 기본 정책을 교체하지 않는다.

## 계산 비용과 후속 연결

prior는 총14,796projection/37.69초, greedy는29,859/119.46초다. 지속 greedy 환경 한 번의 PC wall은30.85..34.14초였다. 원모형의 차등 판단 비용0 가정과 PC 연산 비용을 분리하며, 이 값으로 휴대폰 소비 에너지나 응답 지연을 계산하지 않는다.

후속 actor/critic와 Adam·RNG·미완료 batch 저장 모듈은 [d1_edd_ect_residual_ppo.py](../../../tools/d1_edd_ect_residual_ppo.py)에 구현했고, 명시적인 tensor fixture에서 초기 prior0.9·강제 선택 RNG·actor gradient 제외·저장/복원 후 다음 optimizer/RNG 동등성3검증을 통과했다. 환경/학습 episode 검증을 대신하지 않는다. 기존 사라진 Adam/RNG를 복구했다는 뜻도 아니다.

현재 실제 다음 작업은 후속 시간·fresh split·세 참조 cache·누적 장부를 고정한 뒤,48episode 이내의 학습/재개 fixture로 새 정책의 동등성을 확인하는 것이다. 본학습은 그 결과와 D 등록을 통과한 경우에만 수행한다. 원 모형·계수·기본정책·strict·experiment_ready=false, 원 데이터·사용자 파일·다른 worktree는 유지한다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_edd_ect_residual_controller tools.test_d1_edd_ect_residual_report tools.test_d1_edd_ect_residual_ppo -v
```

위 명령은 환경0의 코드 검증이다. 완료 배치의 재호출 명령은 `python -B -m tools.d1_edd_ect_residual_study run`이지만, 완료 item을 읽어 확인할 뿐 새 실험을 추가하는 승인이 아니다. 공유 검증 명령과 SHA는 최종 검증 파일에서 확인한다. 환경 원시 파일과 checkpoint는 저장소 공유물에서 제외한다.
