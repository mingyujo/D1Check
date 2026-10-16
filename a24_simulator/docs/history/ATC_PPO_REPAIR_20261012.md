# ATC＋PPO 전문가 토론·최소 수리·독립 비교

2026-10-12 KST. 작업 `ATC-RESIDUAL-REPAIR-05`. 사용자 요청 ‘전문가끼리 토론해서 해결’에 따른 모바일/산업공학/RL 교차검토와 PC 구현·유한 검증이다. 현재 HEAD12d64923·기존 사용자 WIP/다른 동시 과제·원873 결과와 종료 소비를 보존한다. 앱 기본/experiment_ready=false 유지, 이번 APK·기기·물리fit·S26학습0이다.

## 토론에서 확인한 사실

- 873 선정모델48조건 전량의 물리 계약·응답/AVAILABLE·공개 입력·지원 검사에서 오류를 찾지 못했다. 미완료를 엔진 결함으로 설명할 근거가 없다.
- 단일 고정 요청에서 PPO는 분류 CPU0/GPU342, RuleATC는 CPU102/GPU240이었다. PPO의 GPU 고정과 요청재정렬에 P95/J/AP 손실이 동반됐다. 일부 납기 개선도 있었으므로 학습 전체가 무용하다고 단정하지 않는다.
- old flag52/e.base/fallback은 실제 RuleATC가 아닌 full-EDD L0다. actor rawlogit0의 greedy 초기 행동과 오류 복귀가 ATC 규칙을 보존하지 않았다. 이 역할 불일치를 먼저 수리한다.
- WAIT4914 중 현재 즉시 실행도 가능했던 WAIT는56이고 전부 손해라고 증명되지 않았다. 묶음 action 선택0이어도 같은 시각 연속 singles로 실제 CG_DC 병행458.869초가 있었다. ‘WAIT가 전부 원인’, ‘병행 미사용’ 설명은 기각했다.
- terminal I/U/N/Q를 모든 상태에 반복한 비용은 이미 발생한 실패도 후속 target에 남긴다. REINFORCE 자체의 수학적 불법은 아니지만 coarse credit/critic 분산 가설이다. old state에는 과거 요구/원cap 실패4개의 명시 관측도 없었다.
- incomplete32/256 episode의 J/AP는 최종 평가상null이지만 실제0..120 상태·AP경로는 있어 학습용prefix 신호를 구성할 수 있다. final eligibility와 training surrogate는 같은 것이 아니다.

## 해결할 수 없는 범위도 분리

현재 등록bootstrap 모형의 D_CPU 점유 최소는 n1=.605109847초, n2=1.205477232초, n3=1.804742693초다. sustained n2 탐지96개에 최소115.7258초가 필요한데 실제 자원창은35..120=85초다. 분류CPU 점유·도착지연을0으로 놓아도 최소26D 미완료/seed다. variable 각32개도 합115.690553초이며 가장 짧은79개에85.009927초가 필요해 최소18D/seed가 남는다. 이는 이 모형·한CPU lane 안의 낙관 하한이며 실제 휴대폰 보편 하한이 아니다.

기한을 늘리거나 과부하 요청을 삭제해 이 실패를 감추지 않는다. 새64의 지원된 단일입력32와 합성묶음 stress32를 층화해 진단하지만 원전체 strict FAIL을 primary-only PASS로 바꾸지 않는다. 혼잡 용량 문제는 보상 수정으로 모두 해결할 수 없다.

## 최소 수리와 대조

물리 mask, 전체큐 top4+보충≤8, PPO의 요청/CPU/GPU/CG_DC 선택 자유, 자원WAIT·ETA·비선점/AVAILABLE 계약은 유지한다. NoWAIT 운영 envelope, ATC 요청 hard lock, phase.since ETA 변경은 이번에 넣지 않아 원인을 섞지 않는다.

1. 실제 same-bank RuleATC의 합법 행동을 flag52·기본 greedy·동점·오류 복귀에 통일한다.
2. shared actor rawlogit0에 `log[9(M_legal−1)] × teacher_flag`를 forward 내부에서 더한다. 선택이2개 이상이면 초기 teacher 확률0.9, 초기 argmax는 정확히 RuleATC다. sample/logprob/ratio 모두 이 분포를 사용한다. 외부 epsilon-greedy는 없다.
3. current까지 도착한 ticket·실제 응답 또는 이미 지난 due로 요구/원cap U/N 실패율4개를 관측한다. 새 ABI state218=global28+8×20+2×15, action53/pad32, 새schema와 fresh weights다. 미래 계획 분모/실현 처리시간을 state에 넣지 않는다.
4. ANCHOR와 CAUSAL 각3seed를 비교한다. 이전ATC3개 고정 가중치도 동일 새 입력에서 재생한다.

| arm | actor/입력 | 학습 label |
| --- | --- | --- |
| ANCHOR | actualATC teacher prior0.9·past4state | V3 AP/J100/I/Ureq/Nreq/P95 목표 그대로. critic10에6target을padding하고 여분4는invalid/weight0. 기존I/U/N dual 유지 |
| CAUSAL | 같은입력/prior/10critic 초기 양식 | 실제 이벤트 이후 suffix return, 완료unit/미응답unitarea 및 모든episode120prefix·원/요구실패·terminalIunit/Ireq·Uholding |

CAUSAL은 credit만 바꾸는 순수 대조가 아니다. unitreward, prefixAP120, 원cap 채널, fixedweights를 묶은 새목적이다. ANCHOR도 teacher/state/critic 초기화를 바꿨다. old873와의 차이를 단일 원인에 귀속하지 않는다.

## CAUSAL 단위·정보 경계

행동 frame i부터 다음 frame 또는120초까지 실제 결과를 label로 쓴다. 같은 시각 중복 frame은 시간 적분0이고 사건은 직전 행동 구간에 귀속한다. suffix는 이미 발생한 실패를 다음 target에서 제거한다. 입력은 현재 관측만이며 label 함수는 episode가 끝난 뒤만 호출한다.

- reward: 실제 AVAILABLE 완료의 n/plannedUnits credit − 미응답units의 시간적분/(plannedUnits×85초). 응답 이후 자원 점유를 미응답 holding으로 세지 않는다. 완료reward와 terminalI penalty는 같은 완료정보의 추가 가중 설계다.
- cost1: 모델의 실제prefix 증분J35..120/100J. state coverage0..120을 확인한다. 실제폰 정책소비 전력/측정에너지라고 주장하지 않는다.
- cost2: 모델 AP running peak35..120 증가/1°C. 전체 final AP35..180과 같다는 보장은 없다.
- cost3..6: U요구/U기존/N요구/N기존의 실패 각채널에1회/해당planned분모. 요구=원cap이면 같은 실패가 두채널에 있어 심한 지연의 추가 severity다. 미응답이고due가120뒤면terminal미응답실패를120에계상해기존전체분모평가와맞춘다. ‘실제due crossing만’이라고 부르지 않는다.
- cost7..8: 실제 AVAILABLE 미완료units/plannedUnits, 미완료요청/planned. cost9: 미응답urgent 요청초/(plannedUrgent×1.5초). unitarea85초와서로다른단위/크기다.
- weights: E/AP1, 네실패·Iunit/Ireq 각10, Uholding1. 10은 penalty 가중치이며 허용실패 target10이 아니다. CAUSAL은 고정, ANCHOR dual은 원설계다. 최종서비스허용치/strict는 완화하지 않는다.

실제prefix에서는unfinished owner를120까지계산하고미완료를0성공으로바꾸지않는다. 최종J/AP는전량완료조건만유효하고기존180초AP창을유지한다. AP/J 학습값을 최종 비용적격으로 전용하지 않는다.

## 독립 자료·선정·예산

new886 arrival train8×4부하×4factor=128/learner, dev2×4×4=32(단일primary16), final4×4×4=64(단일32+batchstress32)다. env realization886000201과공개hint886000301, actor211/223/227와action/shuffle독립RNG를고정했다. 873 final은원인분석에만썼고학습경험으로재사용하지않았다. 실측donor384와동결물리모형은공유하므로새기기독립검증은아니다.

각arm3seed64→128, 최대768신규학습이다. checkpoint0는 actualteacher/prior/actor마지막0의greedy 동형성을단위검사·4native 동일원장/전이로검증한기본fallback이며dev RuleATC32를중복환경없이참조한다. 개발단일16에서 I·완료unit·U/N요구/원cap·P95가조건별RuleATC보다나쁘지않은훈련checkpoint만후보다. 통과모델없으면0선정하고학습추가이득0이라고보고한다. dev서비스→J/AP lexicographic·earliesttie 후 SHA freeze, 최종64에는모델/설정을바꾸지않는다. zero모델을‘학습으로ATC능가’라고 설명하지 않는다.

예정2400=controls224+학습768+dev384+final1024에initialproof4를더한**2404환경**이다. 원등록expected2400은본matrix이고proof4는보충기록으로공개한다. cap2600환경/768학습/A24학습768/S26학습0·active3600초/reserve300초를유지한다. 실패도시작소비,추가튜닝/상한재개0이다. 실제59학습부분중지때6Adam/partial/모든RNG/cursor/clock을검산하고pausedPT도따로보존한다.

최종16roles는7규칙·old873 ATC3개동결·ANCHOR/CAUSAL6개다. 두기한·units/I/P95/J/AP의원단위 조건별차이, primary와stress, actualteacher와PPO일정/route/WAIT 차이를보여준다. 동일physical-bank인경우에도flag52/teacher가다르면새actor입력은다르므로기존bank_same bool을인코더동형성으로확장하지않는다. 전체strict는두기한보호와미완료보존·ε0을유지하고primary는분리진단이다.

## 구현과 현재 검증

새 `tools/d1_atc_repair_policy.py`, `mobile.py`, `engine.py`, `targets.py`, `ppo.py`, `budget.py`, `study.py`, `test_d1_atc_repair.py`를작성했다. native PPO 손실/mini-batch와원5phase/공개event engine을재사용한다. pure8검사는teacher0.9/logprob/물리행동동일/observedpast4/causal과거비용제거/응답과AVAILABLE분리/oldschema거부/native10channelloss와Adam·난수partial복원/모형capacity하한을검사해PASS했다. 단위검사는환경0이고정책우위나기기PASS가아니다.

등록이처음부터driver/targets/test·동결모형/CSV/old3PT SHA와입력/종료예산을포함한다. 이전소스/가중치/원장/문서와동시다른891/CommonCompare/S26작업을보존한다. 전문가 토론은 `docs/results/atc_ppo_repair_20261011`의mobile/ie/rl문서,최종납품은`outputs/ATC-RESIDUAL-REPAIR-05`에분리한다.


## 완료 결과 (2026-10-12)

2404환경/768학습/실패0,6모델각128/16update·CP0선정,개발의18432복수선택에서greedyoverride0이다. 최종1024행의CP0는ATC규칙과같고full/primarystrict모두FAIL·학습추가효과0이다. 원본실행/등록/예산·예전873이력을보존하고[최종수리결과](results/atc_ppo_repair_20261012/RESULTS.md)에근거를썼다. 이어06은576확인＋8사후진단=584환경/학습0,07은128확인＋16진단=144환경/학습0로별도비교했다. 롤링은현재사건마다미시작요청재판단이며미래계획최적화가아니다. 모든신규기기/APK/fit/S26/NPU실행0이다.
