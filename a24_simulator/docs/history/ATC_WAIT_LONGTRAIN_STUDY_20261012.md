# ATC-WAIT1-LONGTRAIN-12: 고정 연결의 추가 학습 계약

상태: 구현·등록 준비. 사용자가 2026-10-12에 계속 진행과 유망한 구조의 장시간 강화학습을 승인했다. 기존 10/11은 완료된 별도 연구로 보존한다. 이번 신규 환경·학습·기기 실행은 등록 및 시작 전에는 각각 0회다. 실제 실행 이후 수치는 새 원장으로 갱신한다.

## 목적과 고정 구조

11회차 DROP_FLAG_WAIT1은 세 학습 seed 모두 주요 범위의 평균 P95/J/AP를 개선했지만 조건별 손해와 full 부하 실패가 남아 원 strict는 모두 FAIL이었다. 이번에는 연결·보상·모형을 고정한 채 학습 자료와 학습량을 늘려, 새 개발 자료에서 조건 손해가 줄어드는지 확인한다. 오래 학습하면 채택 기준을 통과한다는 전제는 두지 않는다.

현재 도착한 미시작 전체 큐 → ATC top4와 실행/복귀 coverage로 최대8요청 → 단일/허용 병행/필요 자원 대기 행동 → 물리 마스크 → 직접 PPO → 실행 또는 자원 사건 대기 → 실제 사건에서 미시작 요청 재판단을 유지한다. 선두 제한으로 되돌리지 않는다. formal rolling horizon 최적화가 아니라 사건 기반 온라인 스케줄링이다.

- 11의 DROP_FLAG_WAIT1/URGENT_HOLD 하나만 사용한다. 원 raw teacher 표식52·복귀·동점 처리·ATC rank/gap을 보존하면서 NN의 표식52만 숨긴다. 합법적 즉시 실행의 최대 ATC gap+1을 대기 logit에서 빼는 WAIT1 prior도 고정한다.
- 상태226, 행동당57, 패딩32, 최대8요청/자원 대기를 포함한29행동과 정규화·모델 구조·보상·학습률·8episode native 업데이트·고정 비용 가중치를 그대로 유지한다. 더 오래 학습하기 위해 서비스 비용을 낮추지 않는다.
- 미래 전체 큐 실행/응답/에너지/온도 rollout, 미래 도착과 실제 처리시간 입력은 금지한다. 사후 teacher 궤적은 학습 label 전용이다. 최종 추론은 가중치 고정 masked argmax와 기존 동점 처리다.
- 실제 AVAILABLE까지 점유, 긴급 OUTPUT_READY/일반 PERSISTED 응답, 비선점, C_CPU/C_GPU/D_CPU/CG_DC 및 최대2건만 허용한다. 냉각 대기·미지원 GPU/병행·NPU를 추가하지 않는다.
- EFT를 사용하지 않는다. FIFO_FIXED/FIFO_READY_FIXED/RR_READY/GREEDY_RESOURCE_FIFO/RuleEDD/RuleATC 6군은 독립 비교군이다. Greedy를 제안 정책 안에 넣지 않는다.

## 정확한 계승과 소비 분리

11의 세 seed1013/1019/1021의 DROP_FLAG_WAIT1 terminal4096을 전부 계승한다. 11에서 최종 확인 점수가 좋은 seed만 고르지 않는다. 각 seed의 원 terminal PT·부모 등록·source/입력 SHA를 고정하고 원본은 수정하지 않는다. 11의 최종 선정 PT가 terminal과 다르더라도 terminal4096을 사용한다.

새 wrapper만 구현한다. 정책/PPO/targets/engine는 11의 동결 코드를 재사용한다. source와 새 입력에 대한 dependencies 재결합은 명시적 migration receipt를 통해 한 번만 허용한다. network, Adam의 step/moment, action RNG, shuffle RNG, multipliers, pending0, 기존 episode/update 로그와 counters는 exact 복사·검산한다. 같은 schema/의미/설정/보상인지도 검사한다. 설정이나 상태 의미가 바뀌면 이 계승을 허용하지 않는다.

계승4096은 새 환경/학습으로 계수하지 않는다. `12 신규 학습 = 누적 episodes − 4096`이며 신규 native/Adam update도 원 counters와 차이로 보고한다. 원 학습 이력은 origin provenance로 보존한다. 새 원장에는 이번에 실제 시작한 환경·수집한 학습만 기록한다. 매 episode의 durable 저장과 accepted cursor/RNG/부분 batch 복원 계약을 유지하고 저장 시간·bytes 증가를 측정한다.

## 자료 분리와 적용 범위

새 TRAIN128seed×11family×2납기factor=2816조건, DEV8seed×22=176조건, FINAL8seed×22=176조건을 등록한다. 기존 seed registry와 로컬 입력을 검사해 각 namespace를 확정한다. 세 모델의 같은 episode에는 같은 도착·실제 처리시간 환경을 사용하고 행동 선택 RNG는 seed별로 분리한다.

idle/steady/release015·035·050·058·065/burst2·burst4/mix4/boundary6의 모든 계열과 fixed/declared 납기를 유지한다. 과거 유리·불리 case를 복사하거나 final seed를 골라 새 학습에 넣지 않는다. 도착 지터·실측 donor의 처리시간 표본·납기 순열은 새 환경 seed로 정한다. .65는 중앙 점유 뒤 기대 anchor일 뿐 실제 미래 해제시각에 도착을 맞추지 않는다.

새 teacher2816과 기본 DEV1056, inherited4096 DEV528도 실제 신규 시뮬레이션으로 계수한다. 교사를 미리 수집하더라도 정책 온라인 입력에는 넣지 않는다. 최종은 6규칙＋3선정 모델＋3inherited4096 모델의12군을 같은176조건에서 평가한다(2112행). 학습 전·후의 대응 비교로 추가 학습 효과를 ATC 대비 전체 정책 효과와 분리한다. 선정과 inherited 가중치가 같으면 해당 seed의 추가 효과0을 명시한다. 모든 모델 및 설정을 최종 환경 실행 전에 동결하고 최종 뒤에는 추가 학습·선정·문턱 변경을 하지 않는다.

같은 A24 donor C_CPU4/C_GPU188/D_CPU192 및 동결 에너지·AP 모형을 사용한다. CPU 분류4표본의 불확실성을 학습량으로 해결한 것으로 표시하지 않는다. 이번 n1의 분류=긴급/탐지=일반 합성 범위는 모바일 전체 workload·모든 우선순위 배치·새 실기기 확인으로 일반화하지 않는다. 물리 적합/새 실측/APK/S26/NPU/외부 전송은0이다. 11 결과를 이미 본 뒤 이어가는 적응 연구라는 이력도 남긴다.

## 개발 선정과 확대·중단

추가 업데이트 전에 inherited4096 세 모델을 새 DEV에서 평가해 추가 학습0 기준으로 잠근다. 누적8192/16384/32768/65536 이후의 powers2 단계로 확대하며 숫자 episode/environment 상한은 두지 않는다. 각 stage를 세 seed 모두 완료하고 native mechanics·조건별 서비스/P95·J/AP를 RuleATC와 같은 seed의 inherited4096 양쪽에 비교한다. 평균뿐 아니라 손해 조건 수·최악 손해·계열별 결과를 기록한다.

모델 선정은 DEV만으로 하고 inherited4096도 후보에 포함한다. RuleATC와 같은 seed의 inherited4096 양쪽에 대해 primary의 각 조건 서비스/P95 비악화를 만족한 후보를 우선한다. 적격 후보에서는 mean J→AP→P95→이른 checkpoint 순서로 선정한다. 비용의 조건별 손해·최악 손해는 별도로 공개하며 이 guard를 원 strict라고 부르지 않는다. 적격 후보가 없으면 서비스/응답/비용 위험 key로 실패 후보를 보고하되 guard 통과로 표시하지 않는다. 4096이 선정되면 이번 추가 학습 향상0을 명시한다. 높은 episode가 선정됐다는 이유만으로 추가 효과를 선언하지 않고 새 FINAL에서 inherited와 대응 비교한다. 최신 가중치 강제 선정·CP0 대체·seed 제외는 하지 않는다.

등록 전에 deterministic 확대 판정 함수를 코드와 문서로 확정한다. IE 권고는 다음과 같다.

- NaN/불법 실행/모델·RNG 복원 불일치/원본 SHA 변경은 즉시 확대 중단하고 실패·소비를 보존한다.
- 새 DEV 서비스/P95 손해 조건 증가가 두 연속 stage 전환에서 세 seed 중 둘 이상에 발생하면 확대를 중단한다.
- 세 추가 stage에서 최선의 적격/위험 key가 개선되지 않고, RuleATC와 inherited 양쪽에 조건별 서비스/P95/J/AP 비악화를 만족하면서 같은 seed의 inherited4096 대비 mean J 최소0.005J의 추가 이득도 없으면 확대를 중단한다. 4096 기준을 세 추가 stage에 포함하지 않는다. 이0.005J는 개발 확대 판단값이며 원 strict epsilon0의 대체 허용오차가 아니다. 계승모델 자체의 ATC 대비 이득을 추가 학습 성공으로 세지 않는다.
- 시작부터 약6시간의 PC wall 예산에 teacher/DEV/확인·보고를 포함한다. 다음 stage 실측시간과 최종 reserve를 보고 확대 여부를 결정하며 최종 확인·저장 시간을 남긴다. 원자료·checkpoint 보존용8GiB 여유를 유지한다. 더 오래 쓰는 다음 회차는 이번 최종을 재튜닝하지 않는 별도 계약이다.

운영/저장 장애는 정책/물리/입력/선정 변경 없이 동일조건으로 복구할 수 있을 때만 재개한다. 10의 동일 os.replace 전송 재시도 helper는 SHA로 별도 결합하며 정책 개선으로 세지 않는다. 원 실패 이력은 삭제하지 않는다.

## 평가·보고·구현

원 strict는 기존 완료/units·절대 서비스·조건별4참조 서비스/P95/J/AP 비악화와 비용 이득, epsilon0를 유지한다. full176 및 primary160(boundary6 계열16조건 제외)을 모두 보고한다. 별도 사전 release80·400ms SLO는 조건부 효율 분석이며 원 strict 완화가 아니다. 일부 비교군이 그 SLO를 실패해도 실패 조건과 해당 비교군의 이점을 삭제하지 않는다.

모든3seed와 inherited 기준/선정 episode, source/input/가중치/동결 시각, 기존 대비 실제 신규 환경/학습/native/Adam update, 단계별 저장 비용과 판단시간 mean/P95/max·큐 증가, 전체 raw SHA·AVAILABLE/물리 mask를 검산한다. PC 시간과 모형 에너지를 휴대폰 판단시간·실측 에너지로 바꾸지 않는다. ATC와 EDD가 같으면 ATC 고유 효과를 주장하지 않으며 이번 회차에서 k/w를 튜닝하지 않는다. EDD 후보 직접 PPO의 별도 학습 대조는 후속으로 남긴다.

새 파일은 `tools/d1_atc_waitlong_migration.py`, `d1_atc_waitlong_budget.py`, `d1_atc_waitlong_study.py`, `d1_atc_waitlong_orchestrator.py`, `d1_atc_waitlong_report.py`, `test_d1_atc_waitlong.py`다. 테스트도 최초 source 등록에 포함한다. 기존 정책 코드와08~11 등록·모델·원자료·FAIL·다른 채팅 WIP는 변경하지 않는다.

실행 루트 `work/ATC-WAIT1-LONGTRAIN-12`, 보고 `outputs/ATC-WAIT1-LONGTRAIN-12`를 사용한다. 자동 확인은 의미 있는 완료/실패/필요 조치만 알리고 실행 중 중복 프로세스를 만들지 않는다. 완료 보고·검산이 끝나면 이번 후속 자동화를 중지한다. 이번 구조는 연구 후보이며 기본 정책/experiment_ready=false를 유지한다.

## 사실·가정·미확인

- 사실: 10/11 완료 보고·감사, 11 source/PPO/targets/engine와 terminal4096이 계승 근거다. 11의 원 strict FAIL과 CPU 표본4 약점은 그대로다.
- 설계 가정: 더 다양한 합성 도착/납기 자료와 더 긴 고정 학습이 일부 조건 손해를 줄일 수 있다. 아직 결과가 아니다.
- 미확인: 긴 학습의 안정성/추가 효과, 독립 처리시간 표본과 실제 기기에서 판단 비용을 포함한 효율, 모든 task/priority 조합의 일반성이다. 새 모바일 전문가 재검토는 통신 오류로 완료되지 않았으며 root가 기존 물리·자료 경계를 확인한다. IE 검토와 구현자의 RL 계승 감사는 범위를 구분해 기록한다.
