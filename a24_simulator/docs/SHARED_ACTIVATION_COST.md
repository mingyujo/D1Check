# 2번 보완: 공유 활성 비용과 유휴 잔류 비용

사용자 2026-10-17 지시: 모든 부분을 논리에 따라 수정할 수 있다. 이에 실측만으로 확정할 수 없는 기작도 **가설 모형**으로 명시하여 별도 세대에 구현한다. 실제 A24 에너지 모형의 정확도나 RL 우위를 입증했다고 해석하지 않는다.

## 등록한 변경

- 기존 단독 C_CPU/C_GPU/D_CPU 및 CG+DC 병행 계수를 보존한다. D_GPU 단독은 기존 가산 모형의 미측정 anchor를 유지한다.
- 공통 활성 성분 H를 `p(CG)+p(DC)-p(CG+DC)`로 정의한다. 기존 계수 차이를 공유 비용으로 설명하는 것은 가설이며 다른 가능한 원인을 배제한 인과 식별이 아니다.
- 다른 CPU/GPU 병행 조합도 공통 성분을 한 번만 지불한다고 가정한다. 모든 단독 동적 성분이 음수가 되지 않도록 H를 제한한다.
- 활성 중 공유 상태 z=1, 유휴 중 `dz/dt=-z/tau`로 둔다. 기본 tau=0.9초는 시나리오 기준이며 기존 센서 필터의 0.9초가 실제 하드웨어 잔류 시간임을 뜻하지 않는다. 기존 센서 저역통과 필터와 중복 적용하지 않는다.
- 같은 고정 평가창의 기저는 그대로 유지한다. 작업별 사용량, 확인된 병행 계수 차이, 미측정 병행의 공유 가정, 유휴 잔류 비용을 분해한다. 마지막 작업 후 잔류의 무한 적분은 증분에만 더해 평가창 끝으로 미루는 효과를 구분한다. 기저를 무한 시간 적분하지 않는다.
- 후보 평가 API도 같은 적분을 쓴다. 실제 과거와 현재 공개 명목 잔여시간만 받으며 미래 실제 처리시간·도착은 읽지 않는다. 공개 추정 오차와 이후 작업의 경쟁은 남는다.

공식 [Android 전력 항목](https://source.android.com/docs/core/power/values)은 awake/idle/active 상태를 구분하고, [Linux CPUFreq 문서](https://www.kernel.org/doc/html/latest/admin-guide/pm/cpufreq.html)는 이용률과 governor에 따른 주파수 조절을 설명한다. 이는 상태 의존 모형의 일반적 근거다. A24에 공유 레일 H나 0.9초 decay가 존재한다는 수치 근거는 아니다. 공식 예시 수치를 가져오지 않았다.

## 검증 계약

`experiments/shared_activation_20261017/OPERATION.json`: 기존 fresh12×5정책60일정과 선택 기회 V2의4입력×3정책12일정, 합계72저장 일정만 새 식으로 평가한다. H배율0/0.5/1/1.5 × tau0/0.225/0.9/3.6의16설정을 모두 보고한다. 정책별 격차가 큰 값을 골라 기본값으로 삼지 않는다. H를 바꿀 때도 기존 CG+DC 병행 계수는 잔차 보정으로 보존한다.

새 환경 START/fit/학습/실측/예약은 모두0이다. 원RL256=기존223+선택기회25+잔8, 별도RR잔1을 보존한다. 원 cost 모형과 결과·기본 UI·학습된 NN은 변경하지 않는다. 새 모형은 `CostObserver`로 명시 선택하는 연구용 세대다.

22개 해석적 계약 테스트, 등록72일정×16설정의2,520검사와 별도 구간 교집합/합집합20,462검사를 통과했다. 최대 산술 차이는1.42e-14이다. 결과 정본은 `results/SHARED_ACTIVATION_20261017_01/COMPLETE.json`, `AUDIT.json`, `COMPARISON.json`이다.

고정된 기본 가정에서 기존5정책의 평균 총비용 범위는89.5107~89.6876(0.1976%)에서86.5304~86.5573J*(0.03113%)로 오히려 줄었다. 이는 이미 만들어진 일정의 재평가이며 새 모형에 맞춰 정책을 학습하거나 실행한 결과가 아니다. 기본 가정을 큰 격차 설정으로 교체하지 않았다.

## 새 비용을 실제 선택에 연결하는 유한 대조

`experiments/shared_cost_policy_20261017/OPERATION_V2.json`에 새seed20269123·C50%/묶음2·4/기준·묶음의4입력×2정책=8 START를 등록했다. 기존 보호/50ms 모음 규칙/물리를 공유하고, 대조 정책은 기존 prior, 새 정책은 허용된 모든 후보의 새 모형 **전체 작업 잔류 포함 명목 증분** 중 최소를 고른다. NN은 사용하지 않는다. 긴급 보호 밖 일반 납기나 온도에 손해가 날 수 있으므로 모든 손해를 함께 보고한다. 이후 작업·미래 도착을 예측하는 다단계 최적화는 아니다.

원RL의미배정5와선택V1의미배정3만 이전했다:223+25+8=256. 전역 신규예약0·별도RR잔1은 그대로다. 새8은 공개 전 실행되지 않았으며 결과는 새 terminal/원장으로만 판정한다. 실행 전 단위검사에서 dependency import 순서 오류1을 발견했고 원소스/등록/오류를`prestart_v1`에 보존했다. 환경 START0인 V1은 퇴역, 같은8할당을 V2에서 사용하며 중복 예약하지 않았다. 수정 후4정책계약 PASS다.

## API

```python
# experiments/shared_activation_20261017를 sys.path에 추가한 별도 세대에서 사용
from cost_adapter import CostObserver
observer = CostObserver()  # shared_scale=1, idle_decay_s=0.9
result = observer.observe(summary, lo=35, hi=90)
candidate = observer.marginal(past_owners, nominal_reservations,
                             candidate_owner, now=now_s, horizon=90)
```

`observe()`의 `conditional_state_cost`는 새 식, `full_episode`는 종료 잔류를 포함한 전체 작업 증분이다. `marginal()`은 동일 식의 창내 및 전체 증분과 기작별 차이를 돌려준다. 원 모형과 같은 이름의 모듈이므로 같은 Python 프로세스에서 단순 import 이름을 섞지 말고 별도 세대 entrypoint 또는 명시 경로 로더를 사용한다.
