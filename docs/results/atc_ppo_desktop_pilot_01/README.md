# ATC→직접 PPO 데스크톱 파일럿 — 2026-10-11

**세 PPO 모두 원 strict FAIL, 새 정책 채택0이다.** A24 구현·기능 검증·3seed 작은 학습·새 확인을 완료했다. S26은 별도 감사와7구간 adapter 검증만 완료했고 품질/정밀도·시각·혼합 비용프로필 gate가 남아 학습0이다.

새 task ATC-PPO-DESKTOP-PILOT-01: 환경791/1536, 실제학습192/384(A24 각seed64, S26 0), 누적실행활성5.722분/240분, 마지막10분 저장 경계 유지. 설치/ADB/기기/새물리모형 적합0이다. 과거 amount512와 종료 예산·원FAIL은 보존한다.

## 같은 새48조건의 원단위 결과

4arrival seed×4부하×3문맥. 48독립 실측이 아니다. P95는 조건별P95의 평균이며 pooled P95가 아니다. J는0..120초, AP는35..180초 모형 내부채널이다.

|정책|완료/예정|긴급 실패|일반 실패|P95 평균 ms|J 평균|최고AP 평균 °C|
|---|---:|---:|---:|---:|---:|---:|
|Band|3168/3168|0|48|364.456|152.274374|30.466456|
|Triton|3168/3168|0|48|398.925|152.729969|30.484420|
|EDD|3168/3168|0|74|304.797|152.407289|30.455501|
|Rule|3168/3168|0|48|364.456|152.323438|30.469080|
|PPO11|3168/3168|0|48|364.456|152.323438|30.469080|
|PPO23|3168/3168|0|48|398.925|152.729969|30.484420|
|PPO37|3168/3168|0|48|398.925|152.729969|30.484420|

PPO11은 같은 후보 Rule과 원단위 지표가 같다. PPO23/37은 Triton과 원단위 지표가 같다. 실제 일정 동일성은 schedule_identity.csv에48조건별로 별도 기록했다. 학습 update·gradient가 존재해도 규칙 이상의 추가 성능은 입증하지 못했다. 평균 개선으로 조건별 손실을 숨기지 않았고 epsilon0의 원 판정을 유지했다.

## 운영 구조와 정보 경계

작업별 FIFO 선두 → ATC top1 + 실행 가능한 선두/선두L0 보충 → CPU/GPU·CG_DC·자원WAIT → 물리mask → 고정 native PPO/규칙 → 사건 재판단. 최대요청2, 행동템플릿7, state90/action23이다. 실제 의미가 같은 자원WAIT는 중복 마스킹한다. candidate/action 생성·mask·encoder·복귀에서 큐 소진/미래AP/J/서비스 보호를 호출하지 않았다. 온라인 trap과 코드/원장 검사를 적용했다.

w_U2/w_N1,k2,구간EMA.1은 이 과제의 사전값이며 실제 지연비용/문헌 보편값이 아니다. 납기는1.5/6s, 지원C_CPU/C_GPU/D_CPU·CG_DC·비선점·실제AVAILABLE를 유지했다. AP/H/slow 중 현재 모형-환경 AP 관측만 신경망에 전달하며 숨은H/slow와 미래 도착/실현시간은 제외한다. 실기기AP 관측으로 검증 없이 바꿀 수 없다.

ATC/EDD 비교: {'banks_same': 25352, 'legal_same': 25352}. 원장에는 보충 후bank 차이와 실제 유효행동의 차이를 구분했다. 유효행동이 계속 같다면 ATC 탐색을 중단하고 EDD 후보 + 직접 선택을 후속 대안으로 둔다. 현재 추가 튜닝0이다.

## 학습·중지재개·오류 기록

새 actor/critic/Adam과 시드별 초기화·행동sample·minibatch shuffle RNG를 사용했다. 각각64episode/8update, 실제Adam step·gradient·승수·normalizer는 learning_updates.csv/checkpoint metadata에 있다. gamma1, GAE없음, AP peak telescope 주보상과 J증분·미완료/긴급/일반 실패율·P95 비용이다. E/Q가중치1은고정, I/U/N만목표0의dual 갱신이다. 원단위KPI와 보상은 다르다.

29episode 경계에서3모델의 부분경험2/2/1·nonempty Adam·각RNG·전체cursor를 원자 저장했다. 별도 프로세스의 복원 payload 전량 일치 PASS를 확인했고 소비/clock/optimizer를 초기화하지 않았다. best-validation 후보와 terminal64를 따로 보존했으며 이번에는 모든seed의 개발 선택이64였다. 확인 후 seed 선택/재튜닝은 하지 않았다.

일반 구현 오류를 숨기지 않았다: 처음 schema 중복 keyword와 합성ATC 반례값을 순수 검증에서 수정(환경0), S26 CSV codec 철자 수정(환경0), 중지영수증 Settings JSON 체크섬 오류 수정(29학습 상태/소비 그대로), 첫Band 평가 후 결과이름 기록의 eager default 오류1환경을 원장에 실패로 보존하고 retry1을 추가했다. 뒤의 두 수정은 driver의 metadata/중지재개 단계 처리뿐이며 정책/학습식/가중치/Adam/RNG/등록 예산은 바꾸지 않았다. registration·원source/diff·effective SHA 영수증을 보존했다.

PRIVATE_RAW_REQUIRED 3suite는 실행하지 않았다. 원자료 없는44검사, 새계약/PPO11검사, S26 adapter2검사, 원동결demo3정책/288요청, 실행gate8은 별도 범위다. 단위시험의 합성gradient/수식 검증을 실제환경 학습episode로 세지 않는다.

## S26 추가자료의 적용

고정3tree 및 사용자 추가4문서를 읽었다. 69manifest, 48480관측요청의7구간→5phase 연결을 검산했다. R4S18attempt/유효14/요청원장 없는 실패4를 분리하고 준비·warmup을 성공으로 채우지 않았다. 추가 연결표의source/profile22개는바이트 또는LF 정규화일치다.

Q20의 품질은 quality-runner의 모델·20텐서·CompiledModel 계약에 귀속한다. 혼합request-runner나npu-runner의 포괄적 품질 승격이 아니다. GPU실제정밀도 보류를 유지하며 NPU/탐지GPU/3병행을 후보에 추가하지 않았다. 기존MobileNet/CPU4/chunk 열계수를 새CPU1 mixed로 전용하지 않았다.

대표R4C의 정기power_sample239와 admission 센서204를 재확인하고 적분대상은239로 분리했다. μA와mA를 섞지 않았다. HAL AP/SKIN을 분리했으며 before/after bracket 미관측을 보존한다. 앱/계수 바이트일치와 실제 정책 정확도/독립확인은 다르다. 첨부 홀드아웃 재현 스크립트는 실행하지 않았고 HTML/d1viewer 미제공·구모형 참조로 기록했다.

## 판정과 다음

기존앱 기본·strict·experiment_ready=false 유지. 새파일럿만 놓고 PPO11과Rule이 동률이면 단순한Rule을 우선하지만 Rule도Band 대비J/AP 손실이 있어 기본 교체 후보로 채택하지 않는다. 모든3seed 실패이므로 NoWait/열특징제거·128/512 확대·남은budget 자동사용0이다. 더 많은학습이 해결한다거나 RL일반실패/수렴이라고 결론내리지 않는다.

PC 판단시간의 평균/P95/최대·실제큐크기별값은 decision_times.csv다. live의selection_inference_and_reply는추론+선택+reply준비를포함한다. 순수forward는저장관측100개/seed·warm10의추론재생에서따로측정하고동결행동일치를확인했다(신규환경/학습0). live callback과posthoc replay를동일시간으로합치지않는다. callback밖관측/coldimport·설치는분리한다. 이시간은폰시간/에너지가아니다. 별도합성큰큐시험0이다.

## 파일·재현

[대시보드](index.html) · [사전등록](registration.json) · [검증](verification.json) · [전체CSV](all_study_rows.csv) · [48조건](confirmation48.csv) · [대응차이](paired_condition_deltas.csv) · [학습로그](learning_updates.csv) · [판단시간](decision_times.csv) · [S26 감사](s26_audit_summary.json)

공개source의 단위검증: python -B -X utf8 -m unittest tools.test_d1_atc_direct tools.test_d1_s26_mixed_audit -v. 종료run의check/report는 로컬raw·checkpoint가 있는PC에서만 실행한다: python -B -X utf8 -m tools.d1_atc_direct_study --run-root <기존run> check; python -B -X utf8 -m tools.d1_atc_direct_report --run-root <기존run> --output <보고폴더>. 이 명령은 신규환경/학습0이다.

완료task의register/run을 새예산으로 반복하지 않는다. raw/item/checkpoint는로컬에 보존하고공유는작은source/설정/CSV/그림/HTML/검증metadata만이다. 새실행은별도사용자범위·seed예약·유한계약이필요하다.
