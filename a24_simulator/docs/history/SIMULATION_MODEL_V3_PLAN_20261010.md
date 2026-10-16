# SIM-MODEL-V3-EXPERT-01 — 오차 감소 모형 개발·새 확인

2026-10-10. 사용자 “전문가 2~3명 토론…더 오차 적은 시뮬레이션” 지시와 A24 연결 유지 응답에 따른 새 작업이다. 기존 v2 작업·clock·확인·실패를 소급 변경하지 않는다. 시작HEAD ee653ac＋미커밋이며 다른 정책 파일럿/사용자 변경은 유지한다.

## 목적과 자료

주목표는 혼합 요청의 예정 도착→일정→온도/AP·기기 에너지 오차를 기존 원모형보다 줄이는 것이다. 단위가 다른 °C/J를 임의 가중합하지 않는다. 실제 일정 조건부 A와 예정 도착 B를 구분한다. 처리시간/P95는 이번 비용 계수 보정에 섞지 않고 원 서비스 모형을 고정한다.

개발은 기존13＋새 회복개발4=17만 사용한다. source는 old3/history30 3/history180 3/macro4/new_recovery4이며 source 균등→내부 세션 균등→표본/5초bin 균등이다. old CPU/PAR2와 history30/180 CPU/PAR 각2, 총6개에서 예정 manifest를 복원해 B를 구성한다. 기타 source에는 B 도착 계약이 없어 A 진단으로만 쓴다.

B6의 old2는 개발shape의 분류/탐지/혼합 burst, history4는 통계역할개발이지만 요청shape가 교대350ms confirmation 계약이다. 통계분할을바꾸지않고 shapevalidator의 역할을exact티켓에맞게넘긴다. 6개를전부동일도착조건으로표시하지않고각source/shape를기록한다.

기존 평가/확인22＋v2 확인4는 이미 본 자료다. 새 후보 선택/계수/강도 추정에 쓰지 않고 고정 뒤 사후 판독만 한다. 원모형 계수와 서비스 자체가 일부 old/history 개발을 사용했으므로 이번 source 제외/중첩 CV는 **고정 선행모형 조건부 보정 검증**이며 전체 모형의 완전 독립 OOF라고 부르지 않는다. 최종 판단은 새 기기 확인4로 한다.

## 세 검토 역할의 합의와 유한 후보

- 열: 원 AP를 동일한5기저로 정확히 표현해 prior로 쓴다. v2 회복4 전용 fitting의 분포 편향을 먼저 줄이며 새 RC 차수/β/τ 동시 탐색을 하지 않는다.
- 에너지: 미래 배경전력/유휴 평균을 예측 입력으로 가져오지 않는다. 기존 pre baseline을 우선 유지하고 관측 가능한 pre후반 전력의 작은 보정만 별도 후보로 둔다.
- 검증/서비스: 미래 실제점유/last_lane/AP·power 정답을 B wrapper에 넘기지 않는다. 원 서비스 고정으로 비용과 일정 오차를 분리하며 narrow TFLite invoke와 execute 전체 시간을 합쳐 학습하지 않는다.

AP 후보는 동일 fast4＋slow1 계수의 source-balanced ridge-NNLS, 초기 H 규제 α∈{0,0.5,1}이다. α1은 자유 R/H, α0은 H0 뒤 R 재추정, α0.5는 표준화 초기행렬의 H penalty1이다. last pre AP anchor와 알려진 history forcing 차감을 유지한다. β/slowτ1920/preτ30은 고정한다.

에너지 후보는 원 p4 중심 ridge-NNLS, gain∈{0,0.5,1}의 pre후반 전력 relaxation이다. gain0은 기존 baseline. P_late는 도착 전10..30초, P_pre는−20..30초이고 `E_add=gain(P_late−P_pre)[u−30(1−exp(−u/30))]`, u=max(0,t−35)다. 미래 전력은 표적에만 쓴다. 이 보정은 가정 기반이며 물리 원인을 식별했다는 뜻이 아니다.

두 head의 λ는 {0,0.01,0.1,1,10,100}만, 열18/에너지18 후보다. column norm D로 원 계수 penalty를 표준화한다. source 제외 외부5fold/내부4fold에서 head별 선택을 반복하고 최종 전체개발5fold 선택 뒤 한 번 적합한다. head fit 상한1000, PC 개발/코드 검증 예약3600초, 실패/원source변경 시 기록하고 무제한 grid 확대하지 않는다.

head 선택은 혼합 B의 source균등 AP MAE 또는0..120 절대J를 최우선, 최악 source/세션을 차례로 tie-break한다. 동률은 강한 ridge/작은 보정/단순 초기값 순이다. B가 없는 held source에는 A 평균을 사용하되 primary B 평균과 혼합해 개선을 선언하지 않는다. 회복/macro 전체 경로·등록창 J/duration·최악/방향/성공/P95는 별도로 공개한다. 선택/정규화/fold 기준은 결과 열람 뒤 바꾸지 않는다.

## 새 독립 확인

후보 모델·소스·개발manifest/hash·선택을 동결한 뒤 CPU→PAR→PAR→CPU4세션, 각96 교대350ms 요청/기한1.5·6초/원 모델·PNG·CPU1/최대2·검증CG_DC만 수행한다. 기존 APK2067aac0 점검만 하고 설치0이다. baseline30/common120/cooling60, 900ms sampler, numeric AP observe/status0, 기존 비충전/배터리≥20/BAT≤35/화면·메모리·출력동등성 gate를 유지한다. 시작AP/전력/시각과 실패를 기록한다.

새 task의 새 ID/UUID/미소비 namespace이며 이전 clock의 연장/재개로 표시하지 않는다. 새 기기 상한은 명시추론416=본384＋warmup32, runtime16, staging4/28파일, 설치/전송0, APK host pull1이다. 점검600＋4×765＋간격270＋분석600=4530초(75분30초), ADB종료포함5904/정상5704를 예약한다. 동일 순서 추가반복/대체/재시도0이다. 새 확인 뒤 fitting/λ·보정·모형선택 변경0이다.

새4 확인의 세션균등 AP MAE와120초 절대J가 각각 원모형보다 작아야 두 비용 head의 개선을 통과로 부른다. policy별/최악 세션과 모든 잔차도 보고하고, 평균이 개선돼도 policy일방의 악화는 숨기지 않는다. 서비스/P95/전체도착 기한성공은 원 서비스 고정 예측과 함께 보고하며 정확도·실제 정책 효과·에너지 절대 교정은 별도다. 실패하면 개선 미확정으로 기록하고 raw/실패를 보존한다.

## 참고 근거와 한계

[HotSpot ISCA2003](https://www.cs.virginia.edu/~skadron/Papers/hotspot_isca03.pdf)은 열 RC의 시간 응답·초기조건·센서 문제의 근거이며 A24 물리 계수의 출처가 아니다. [Cawley·Talbot JMLR2010](https://jmlr.org/papers/v11/cawley10a.html), [Varma·Simon BMC2006](https://link.springer.com/article/10.1186/1471-2105-7-91)는 선택과 평가를 분리할 근거다. 논문 수치/기기 계수를 그대로 복사하지 않는다. 전체 결과·재현코드·불확실성을 제공하고 기본/RL/strict/experiment_ready=false와 원모형/v2/사용자 변경을 보존한다.
