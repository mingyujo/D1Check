# ATC-DEADLINE-MEANAP-14 — 납기 안 응답시간 벌점 제거와 평균 AP 보상

상태: 등록 전 설계·구현 검토. 2026-10-12 사용자는 기존 학습을 계속 두고, 기한 안의 응답시간 증가 벌점을 제거하며 기한·납기 위반만 벌점으로 주는 보상을 별도로 실험하도록 승인했다. 이 문서의 준비 단계 신규 시뮬레이션·학습·기기 실행은 0회다. 등록 후 실제 14 실행은 별도 executions 원장에서 센다. 현재 12와 13, 이전 08~11의 등록·소스·입력·가중치·FAIL·PID·학습목표·종료시각 및 다른 채팅의 WIP는 바꾸지 않는다.

## 비교하는 보상

동일한 ATC 후보·DROP_FLAG_WAIT1 직접 PPO·물리 실행 계약에서 네 보상군을 새로 학습한다. 새 초기 시드 1201/1213/1217마다 네 군의 초기 network, 빈 Adam, action/shuffle RNG가 같아야 한다. 기존 학습 가중치·critic·Adam 재사용은 0이다.

| 군 | 시간·서비스 보상 | AP 학습 비용 | 분리하는 효과 |
|---|---|---|---|
| CURRENT_COST5 | 원 13 COST5와 동일: URGENT_HOLD, 기존 완료/응답 차이, 상대 P95 | 최고온도 성장 차이, 35~120초 | 같은 새 자료·시드에서 기존 목적 대조 |
| DEADLINE_PEAK120 | 기한 안 시간 보상 0, 절대 납기·미완료 비용만 유지 | 위와 동일 | 기한 안 응답속도 압력 제거와 미완료 비용 보너스 차단 |
| DEADLINE_MEAN120 | 위 DEADLINE 군과 동일 | 시간 평균 AP 차이, 35~120초 | 같은 창에서 최고온도→평균온도 목적 변경 |
| DEADLINE_MEAN180 | 위 DEADLINE 군과 동일 | 시간 평균 AP 차이, 35~180초 | 학습 목표 창과 기존 180초 냉각 꼬리 포함 효과 |

네 군 모두 에너지/AP 비용 가중치 5/5, 절대 서비스 여섯 채널 각 100이다. CURRENT_COST5만 기존 상대 P95 비용 가중치 20을 쓴다. 설계 가중치는 실제 지연 비용이나 °C↔J 환산값이 아니다. 마지막 비교는 창 변경의 효과까지 포함하므로 독립적인 온도 성능 효과로 과장하지 않는다. 네 군 모두 동일한 120초 요청·에너지 창과 기존 180초 AP 평가 종료를 사용한다. 학습 창 때문에 시뮬레이션·운영을 더 길게 대기시키지 않는다.

## 기한 안 시간 벌점을 완전히 제거하는 계약

DEADLINE 세 군에서는 reward return 채널 0을 모든 판단에서 0으로 하고 valid[0]=false로 둔다. 반환 reward 배열도 전부 0이다. 상대 P95 채널 9는 target[9]=0, valid[9]=false, episode costs[8]=0, 해당 actor 비용 가중치 0이다. 이 두 채널의 critic 오차·baseline·advantage가 actor에 남지 않아야 한다.

따라서 무응답 holding 면적, urgent_area, ATC와의 응답/완료 return 차이, 완료 시각 보너스, teacher-relative P95 potential, P95를 기준으로 한 비용 보너스 gate를 쓰지 않는다. 단순히 URGENT_HOLD 한 항만 제거하는 안은 제외한다. 완료의 보너스 대신 미완료 요청·unit에 대한 비용을 유지한다.

시간·서비스 비용은 기존의 절대 여섯 채널만 남는다.

| 채널 | 비용 정의 | 단위·정규화 |
|---|---|---|
| 긴급 선언 납기 위반 | 실제 긴급 응답이 해당 요청의 선언 deadline_offset을 넘거나 응답 누락 | 긴급 요청 수로 나눈 비율 |
| 긴급 원 기한 위반 | 실제 긴급 응답 1.5초 초과 또는 응답 누락 | 긴급 요청 수로 나눈 비율 |
| 일반 선언 납기 위반 | 실제 일반 응답이 해당 요청의 선언 deadline_offset을 넘거나 응답 누락 | 일반 요청 수로 나눈 비율 |
| 일반 원 기한 위반 | 실제 일반 응답 6초 초과 또는 응답 누락 | 일반 요청 수로 나눈 비율 |
| 미완료 unit | 실제 완료하지 못한 unit | 계획한 전체 unit 수로 나눈 비율 |
| 미완료 요청 | 실제 완료하지 못한 요청 | 전체 도착 요청 수로 나눈 비율 |

선언 기한은 고정 조건에서 긴급 1.5초·일반 6초, 혼합 선언 조건에서 긴급 0.75/1/1.5초·일반 3/4.5/6초다. 응답이 기한과 같은 경우는 위반이 아니다. 선언 기한과 원 기한이 같으면 같은 위반을 두 채널에서 각 100으로 벌점한다. 이는 CURRENT와 서비스 채널을 같게 두기 위한 설계이며 두 개의 독립 실패 사건으로 해석하지 않는다. 원 미완료·분모·실패 기록을 축소하지 않는다.

실패 비용의 발생 시각과 사후 suffix 배분은 기존 CAUSAL 계약을 재사용한다. 이미 발생한 위반은 후속 판단의 suffix에 다시 넣지 않는다. 이것은 학습 label 계약이며 실제 운영의 납기 보장을 뜻하지 않는다. 물리 마스크는 납기·서비스 통과 여부를 보장하거나 판정하지 않는다.

## 에너지와 평균 AP 비용

에너지는 같은 case·실현의 RuleATC 사후 대조와 비교한 0~120초 모형 에너지 suffix 차이 /10J다. 상주 전력·고정 창은 같게 유지한다. 평균 AP는 실제 저장한 1초 간격 AP 곡선을 공통 창에서 선형 보간해 사다리꼴 적분한 값이다. 평균과 최고온도를 서로 바꿔 부르지 않는다.

학습 창 B가 120초 또는 180초일 때 고정된 전체 창의 길이 B−35초를 분모로 쓴다.

$$\bar T_{AP,B}=\frac{1}{B-35}\int_{35}^{B}\widetilde T_{AP}(u)\,du,$$

$$C_{AP,B}(t)=\frac{1}{0.1{}^\circ\mathrm C}\frac{1}{B-35}\int_{\max(35,t)}^{B}\bigl(\widetilde T_{\pi}(u)-\widetilde T_{ATC}(u)\bigr)\,du.$$

tilde는 저장된 1초 곡선의 선형 보간이다. decision이 1초 구간 중간에 있으면 그 구간을 같은 직선에서 잘라 적분한다. 남은 창 길이로 나누지 않는다. 판단 frame을 더 넣거나 빼도 같은 물리 궤적의 전체 면적·평균은 같아야 한다. reward/cost label은 사후에만 만들고 교사·미래 도착·실제 처리시간·미래 에너지·온도·평균 값을 온라인 NN 입력이나 후보에 넣지 않는다.

모든 군의 DEV 선정과 FINAL 비교는 공통 **평균 AP 35~180초**를 사용한다. 평균 AP 35~120초도 모든 군에서 함께 보고하며 최고 AP 35~180초도 보존한다. 완료한 군만 창을 짧게 잡거나 추가 idle 시간을 붙여 평균을 낮추지 않는다. 불완전·nonfinite·격자 누락을 0으로 채우지 않는다. J는 에너지, °C는 AP 온도이고 표면·배터리 온도나 열량이 아니다.

평균 AP는 요청·unit 전량 완료할 때 같은 일의 비용 지표로 적격이다. 미완료 궤적의 관측 시간평균은 observed_mean_ap_* 진단으로 남기고 equal-work 평균은 null로 보존한다. DEADLINE 세 군은 actual/reference가 요청·unit 미완료이면 energy/AP valid[1:3]=false로 하고 서비스 여섯 비용은 유지한다. 일 덜하기로 절감 보너스를 받지 않는다. 이때 양의 energy/AP 벌점도 함께 제외되므로, 미완료 궤적의 비용 신호 전체를 끄는 대가가 있다. 원13 GATED의 양의 비용 유지와 다르고 납기 보장 수단도 아니다. 절대 서비스 벌점과 DEV의 조건별 전량 완료·납기 적격 검사를 별도로 유지하며 이 보완을 단일 시간 벌점 제거 효과라고 주장하지 않는다. CURRENT_COST5는 원13 exact 대조를 유지한다. 모든 미완료 행·분모·비용 결측 수를 함께 보고하며 결측 행을 빼서 평균 개선으로 숨기지 않는다.

## 자료·가중치·비교군

12의 완료된 TRAIN 2816조건·DEV 176조건과 teacher 2816＋6규칙 DEV 1056＋원 모델 4096 DEV 528의 총 4400개 참조를 원 source·arrival_seed·realization·case signature·row/raw SHA로 검증해 복사한다. 원본은 읽기 전용이며 복사 참조의 14 신규 환경은 0이다. 12/13 FINAL·최종 선정·latest 학습 가중치는 14 학습/선정에 사용하지 않는다.

새 FINAL은 tentative 923910101~923910108의 8시드×11계열×2납기 factor=176조건이며 실제 전체 등록·inputs·seed registry에서 충돌을 검사한다. 새 초기 시드도 다른 등록과 충돌을 확인한다. 모든 계열을 유지하고 어려운 boundary6 조건을 제거하지 않는다.

최종은 FIFO_FIXED/FIFO_READY_FIXED/RR_READY/GREEDY_RESOURCE_FIFO/RuleEDD/RuleATC의 6독립 규칙＋12 DEV 선정 학습 모델＋3 원 4096 참고 모델의 21군, 176×21=3696행이다. origin1013/1019/1021을 새1201/1213/1217에 사전 대응하되 같은 초기 시드 계승이라고 부르지 않는다. Greedy/RR/FIFO는 독립 비교군이고 EFT·Band·Triton 새 실행은 0이다.

동일 시드·조건에서 CURRENT→DEADLINE_PEAK120, PEAK120→MEAN120, MEAN120→MEAN180의 인접 차이를 DEV의 같은 episode stage와 FINAL에서 분리한다. CURRENT 대 PEAK는 원13 exact를 보존하므로 시간 인센티브 제거와 미완료 energy/AP valid 보완이 함께 달라진다. 학습에 미완료가 있었다면 시간 벌점 하나만의 순수 효과라고 주장하지 않는다. 모든 군의 실제 미완료 학습 수와 비용 invalid 비율을 공개하고 미완료 0이어서 이 보완이 비활성이었는지도 검산한다. 같은 새 FINAL에서 ATC 및 각 독립 규칙·고정 origin도 비교한다. 12/13은 다른 FINAL 실현이므로 같은 condition 번호만으로 차감하지 않는다. 선정 episode가 다르면 보상과 개발 선정 절차가 합쳐진 효과이며 보상 하나의 순수 인과로 주장하지 않는다.

## 학습·선정·확대·중단

모델 worker 1개, PyTorch CPU thread 1개로 12모델을 순환 학습한다. 기존 12의 3worker와 13의 1worker를 그대로 두며 priority·affinity·종료시각을 바꾸지 않는다. 신규 14 등록부터 8시간 wall, 최종 3600초 reserve, 환경 경계에서 training 16GiB/final 8GiB 디스크 및 Windows available RAM 1.5GiB 보존 조건을 둔다. 공유 호스트의 학습/저장·판단 시간 간섭은 따로 공개한다. 실행 수를 무제한 성공으로 세지 않고 실제 시작·완료·실패·부분 업데이트를 센다.

fresh 512→1024→2048→powers2로 확대하며 수치 episode/environment 상한은 없다. 8episode 단위 원 native PPO loss·Adam·학습률·clip·entropy·shuffle 수학은 유지한다. actor가 선택할 여지가 없는 batch에서는 기존 critic-only 계약을 유지한다. 실제 첫 시드 4군의 총59episode 부분 저장·복원 proof를 수행해 15/15/15/14 episode, pending, native/Adam, action/shuffle RNG의 exact 복원을 확인한다. 이59회는 14 신규 학습 원장에 포함하며 감사로 두 번 세거나 재실행하지 않는다. 준비 순수 fixture와 실제 rollout을 구분한다.

공통 stage를 전12모델이 완료한 뒤에만 DEV 결과를 선택에 쓴다. 새 선정 적격 조건은 primary160의 각 조건에서 요청·unit 전량 완료 및 긴급/일반 선언·원 기한 실패 **모두 0**이다. 상대 P95 비악화 guard는 없다. missing/nonfinite 서비스/비용은 실패·invalid로 보존한다. 비용 선정 key는 네 군 모두 mean J→mean AP35~180→peak AP35~180→이른 checkpoint다. P95는 보고만 하고 비용/선정 tie key에 넣지 않는다. CP0를 학습한 모델처럼 대체하지 않는다. 적격 checkpoint가 없으면 실제 학습한 실패 후보를 표시하며 강제 PASS로 바꾸지 않는다.

기한 실패 조건의 사전 악화 함수에서 같은 군의 3시드 중 2시드 이상이 두 연속 stage 전환에서 악화하면 전 군을 함께 중단한다. 중단 함수에는 P95 증가를 넣지 않는다. 네 군 모두 사전 비용/절대 서비스 정체 조건을 3추가 stage 동안 만족할 때만 공유 정체 중단한다. 비용의 의미 있는 진전은 best eligible mean J가0.005J 이상 또는 mean AP180이0.0005°C 이상 줄고 다른 평균 비용·최고온도가 악화되지 않는 경우다. 서비스 위험 감소나 새 절대 납기 적격 모델 출현도 진전으로 기록한다. 이 수치는 확대 중단 설계값이지 기기의 유의 효과/정밀도가 아니다. 첫 trained512가 비교 기준이고 부분 미완료 stage는 선정하지 않는다. 다음 stage 예상시간과 최종·저장 reserve를 침범하면 환경 경계에서 저장 후 중단한다. 학습 도중 기준·seed·물리·라벨·등록 source를 바꾸거나 종료시각을 늘리지 않는다.

모든12학습＋3origin의 weights/source/input/freezeUTC를 FINAL 전에 동결하고 masked argmax로 같은 새 자료를 한 번 확인한다. 확인 후 학습·튜닝·재선정·불리 조건 삭제는 0이다. 모든 시드·조건의 납기/완료와 P95 손해·평균 및 최고 AP·J 손해 수와 최악 손해를 공개한다. 평균 비용 이득으로 조건별 손해를 숨기지 않는다. 채택 후보는 선언한 범위에서 납기를 모두 지키고, 에너지 또는 평균 AP가 개선되며 다른 비용·최고온도 악화가 없는지 함께 검토한다.

## 실행과 오류 계약

온라인 경로는 ATC top4＋coverage 최대8 현재 미시작 요청 → 단일/CG_DC/필요 자원 WAIT → 물리 마스크 → PPO → 실제 사건마다 재판단이다. 상태226·행동57·패딩32·최대29행동·DROP_FLAG_WAIT1의 teacher표식 NN 비노출·ATC rank/gap/WAIT1 prior·정규화는 같다. 출력 준비만으로 자원을 풀지 않고 실제 AVAILABLE까지 owner를 유지한다. 긴급 OUTPUT_READY·일반 PERSISTED 응답과 자원 점유 종료를 나누고 비선점·지원 조합·최대2건을 유지한다. 임의 냉각 대기·NPU·D_GPU·3자원 조합은 추가하지 않는다.

objective/target 의미가 바뀌므로 상태·행동 ABI가 같아도 과거 가중치/critic을 새 목표의 가중치로 로드하지 않는다. 새 learner의 목표·valid·multipliers·source/input 검사를 별도로 고정한다. 모델 오류/불법 마스크/shape mismatch/소스·RNG 불일치는 실패를 보존하며 중단한다. 기존 동일 os.replace 재시도 IO helper의 SHA만 결합하고 정책 변경으로 세지 않는다. 저장/후처리 장애는 동일 등록으로만 복구한다.

## 보고·검증과 근거 경계

14의 새 deadline-only 판정과 과거 원 strict epsilon0 판정, 추가 release400ms 판정은 각각 별도 이름으로 보고한다. 새로운 사용자 목적에서 상대 P95 증가를 허용했다고 원 strict FAIL를 PASS로 다시 쓰지 않는다. FINAL raw 전체 SHA·모든 owner/응답/AVAILABLE·전체 물리 mask·native/Adam/RNG/pending/freeze·원장·선정/paired/평균 계산을 검산한 뒤에만 완료 receipt를 쓴다. 이후 후속 자동화는 12/13/14 전체 보고와 검산이 끝났을 때 종료한다.

확인된 사실: 기존 holding·완료 차이·상대 P95 라벨은 tools/d1_atc_waitlink_targets.py, tools/d1_atc_repair_targets.py, tools/d1_atc_delta_targets.py에 있고, 원13 가중치·fresh learner·자료/동결 계약은 tools/d1_atc_costguard_*.py가 근거다. 저장 curve는35~180의 고정1초 격자이며 기존14 이전 시간평균 보충집계는 outputs/DEADLINE_FIRST_AP_DEVELOPMENT_20261012.json과 outputs/DEADLINE_FIRST_EVALUATION_20261012.json이다. 원11 정책/물리·12 migration source92 및13 source99는 그대로다.

설계 가정: 납기 안 응답속도 압력 제거와 시간평균 AP 목적이 추가 비용 절감을 학습할 수 있다. 아직 결과가 아니다. 미확인: 전 조건·전 시드의 절대 납기 준수, 비용 손해 없는 개선, 장기 수렴, 실기기 판단 비용과 열/에너지 효능이다. A24 CPU 분류4/C_GPU188/D_CPU192 donor·동결 PC AP/에너지 모형·합성 n1 Curgent/Dnormal·유한 자료 반복의 한계는 남는다. 학습 횟수는 새 기기 관측 수가 아니며 PC 시간이나 모형 °C/J를 휴대폰의 독립 측정 효능으로 환산하지 않는다. NPU/S26/APK/기기/새실측/fit/외부 전송은 0이고 앱 기본·experiment_ready=false를 유지한다.
