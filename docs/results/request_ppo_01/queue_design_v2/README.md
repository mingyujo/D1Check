# PPO v2 — 처리 가능한 주 실험과 과부하 평가

2026-10-06, REQUEST-PPO-FEASIBILITY-07. 부모 HEAD `435aa2533fc2704eb6a3c014f400a12afcffeea8`. **PC 실행 준비 완료·정식 Run 미실행·미소비**다. 사용자가 완료된 v1을 본 뒤 요청한 설계 개정이며 사후 개발이다. 기존 결과·동결 모형·기본/strict·`experiment_ready=false`를 보존한다.

[준비 및 v1 판독 화면](index.html), [새 계약·예산](training_plan.json), [입력/가능 일정 증거](preflight.json), [검증 기록](verification.json).

## 기존 v1 결과와 이번에 확인한 것

로컬 원본은 `output/queue_ppo_run_v1/resume_v1`이다. `RECEIPT_337a6e7999564035bb19278ef2c85875.json`에서 completed, 활성시간5770.077초, 학습12288/검증1440/시험1920/참조2288을 확인했다. 이관 참조복구2096·재계산학습 최대39·중단 미기록0–1은 별도다. 기존 raw/actor/receipt를 고치지 않았다. [원파일 SHA와 사후 판독](legacy_readout.json), [전체44행](legacy_policy_family.csv), [192조건의 가능성 판독](legacy_capacity.csv).

| v1 정책 | low 전량기한 /48 | sustained 전량기한 /48 | queue/burst 전량기한 /96 |
|---|---:|---:|---:|
| SHARED_EFT |48|48|0|
| HEAD11 |48|10|0|
| HEAD23 |48|42|0|
| HEAD37 |48|3|0|
| QUEUE11 |33|6|0|
| QUEUE23 |48|48|0|
| QUEUE37 |48|1|0|

여섯 actor는 기존 검증 조건에서 채택 부적격이다. HEAD37/QUEUE11은 update0이 선택됐다. QUEUE23은 적격 low/sustained96조건에서 SHARED_EFT와 J/AP가 같았고, 여섯 actor의 공동 비악화와 엄격 공동 감소는 모두0건이다. 기존 EFT_REFERENCE의8건은 PPO 성공이 아니다.

48조건은 도착16seed×3동결 처리문맥이며 실기기48세션이 아니다. 서로 다른 정책의 성공 부분집합 평균으로 전체 순위를 만들지 않는다. v1의 최초 실패·전체 실패 분모·성공표는 원래 의미를 유지한다.

### WAIT와 최초 실패: 확인된 경계와 미확인 원인

[최초실패 대표](legacy_first_failures.csv)는 각 actor×family에서 저장 순서상 최초 실패 조건 하나를 기계적으로 선택했다. [실제 유휴·대기 구간](legacy_idle_backlog.csv)은 이미 도착했지만 dispatch 전인 요청이 있고 두 lane가 모두 비어 있던 구간이다. 임의 시각 이동·미완료 삭제·새 엔진 재생은 하지 않았다.

대표 QUEUE11/low/610620001/mean의 첫 분류는 도착35.0초·기한36.5초·GPU dispatch36.343초·응답36.637054635초로 0.137054635초 늦었다. 이 조건의 all-lane idle+backlog 합은16.420998157초다. saved actions의 WAIT 횟수와 함께 기술할 수 있다. **원본 test ledger에는 각 결정 시점의 큐·WAIT/가드 이유가 없어 해당 지연 전체의 인과 원인은 확정하지 않는다.**

별도 PC 경계 fixture에서는 현재 평균 추정으로 CPU는 제시간 응답 가능한데 GPU는 이미 늦는 상황에서 v1 mask가 두 경로를 모두 허용함을 재현했다. v2는 같은 요청에 즉시 가능한 제시간 대안이 있을 때만 이미 늦는 backend를 제외한다. 모두 늦으면 진행을 유지한다. HEAD/QUEUE/SHARED_EDF/SHARED_EFT에 똑같이 적용하며 과거 결과를 재평가하지 않는다. 평균 추정 기반 규칙으로 실제 미래 기한 보장이라고 하지 않는다.

## 질문·입력·자료 역할

- 주 질문: 처리 가능한 등록 입력에서 기한·전량작업을 유지하며 강한 SHARED_EFT 대비 J와 AP 부담을 개선하는가?
- 과부하 질문: 같은 전체 도착의 실패수·총지각·최대지각을 어떻게 바꾸는가? 주 학습·검증 선택에 과부하를 넣지 않는다. 과부하용 추가 학습은 없다.
- 기한은 분류 도착→output_ready1.5초, 탐지 도착→persist_complete6초. J0–120초, AP35–180초, 모든 lane 해제120초 이내다. 실제 앱 SLA는 아니다.
- 모형·resident·3cell(분류CPU/GPU urgent, 탐지CPU normal)·CG_DC·5단계 점유·비선점은 그대로다. 미래 도착/실현 처리시간/seed/family는 actor에 제공하지 않는다.
- 새로운 입력 seed는 train610700000–610700511, validation610710001–610710004, test610720001–610720016이다. 모든6learner는 같은 입력 순서를 사용한다. 이미 본 v1 시험은 이번 설계의 사후 분석 자료이며 새 독립 확인으로 재활용하지 않는다.
- low/sustained는 기존 생성규칙을 유지한다. low는24요청(6:18), sustained는192요청(96:96)이라 두 입력 차이를 순수 도착률 효과라고 부르지 않는다. 새로운 입력을 J/AP 성적에 따라 검색하지 않았다.
- train1024/validation24 모두 고정split 일정 witness가 유효하다. final test는 주96/과부하96이다. 같은 모형의3문맥이고 물리적 독립 반복이 아니다.

### 가능성 검사

필수 탐지CPU 응답 수요가 첫 탐지도착→마지막 탐지기한 창을 넘으면 해당 **동결 deterministic 문맥에서만** overload_proved다. 분류CPU와 lane tail을 제외한 보수적 필요조건이다. 이 한 창 검사의 통과는 가능성 증명이 아니다.

GPU 분류FIFO/CPU 탐지FIFO의 사전 구성 일정으로 모든 요청·응답기한·실제lane종료·허용병행을 검증한 경우 feasible_witness다. 필요조건은 통과하지만 witness가 실패하면 unknown이며 주 학습·검증을 차단한다. 새로운 계수나 시간분포를 추가하지 않는다. 증거 생성은 추정 정책 엔진을 실행하지 않는 PC 산술검사다. 이 witness는 actor가 미래 정보를 갖는다는 뜻도, SHARED_EFT와 같은 일정이라는 뜻도 아니다.

`preflight.json`에는1240개 case의 입력hash·분류·수요·창·witness hash/여유가 있다. 최소 주조건 witness 여유는1.198499211초다. 전체 요청 완료가 가능함을 보였을 뿐 PPO의 성공·실기기 용량을 인증하지 않는다. seed 외 실제도착/작업/등급/기한만 hash하여 split간 내용 중복도 검사한다. 접근 가능한 등록JSON/CSV와 기존 terminal manifest 이력은 확인하고 외부 미등록 이력은 미확인으로 남긴다.

## 학습·선택·판독 일치

PPO-Lagrange·HEAD/QUEUE·17출력·85관측·64×64·5value·Adam/GAE 설정은 유지한다. v1 aging/WAIT 가드에 위 backend 경계만 더한다. 다른 알고리즘·추가 품질티어·선점·DQN/SAC 탐색은 없다.

보상은 `-whole120초J/10`. 서비스 cost는 등급별 절대실패율이다. 열 cost는 `max(0,AP면적−동일입력SHARED_EFT면적)/100`, `max(0,최고AP−참조최고AP)`다. 열 penalty는 episode 마지막 의사결정에 귀속한다. dense 에너지/서비스 회계는 보존한다. 음의 열 차이가 다른 조건의 열 증가를 상쇄하지 않도록 원래 signed 평균cost를 개정했다. 단위공차1e-9 J/°C/°C·s는 수치 동등 처리이며 정확도 허용폭이 아니다.

비음수 cost의 기대0 목표와 조건별 비악화의 의도를 맞췄다. **유한학습·유한검증이 미관측 모든 입력의 무위반을 보장하지 않는다.** validation은 주24조건만 사용하며 무효/미완료→서비스위반사례/비율→열위반사례/양의초과→J→응답→이른update 순으로 선택한다. update0 포함, 적격 checkpoint가 없으면 채택 부적격 상태로6actor를 진단 시험에만 남긴다. test는6actor 동결 뒤 한 번 판독하고 최고시험seed를 고르지 않는다.

최종 판독은 전체2112행의 분모를 유지한다. 공동 비악화는 기한/전량작업을 지키고 J/peak/area가 모두 이하이면서 하나 이상 감소, 엄격 공동 감소는 세지표 모두 감소다. 상충·동률·서비스실패를 별도로 보존한다. 과부하의 실패·지각은 원분모로 비교하며 부적격 비용 차이를 전체 정책 순위에 사용하지 않는다. 원 J/AP 값은 모든 case의 test.csv에 남는다.

## 정확한 예산과 정지

| 항목 | 산식 | 횟수 |
|---|---|---:|
| 학습 |2변형×3학습seed×128update×8episode|6144|
| 검증 |6learner×5시점(0/32/64/96/128)×24조건|720|
| 최종 비참조 실행 |192조건×(6actor+4기준)|1920|
| SHARED_EFT 캐시 |train1024+val24+test192|1240|
| 합계 |위4항|**10024**|

최종 표는192×11=2112행이다. 기본 Run 1회·자동 재학습/추가 알고리즘/추가seed0, 최대활성5400초(90분), 마지막120초 receipt 예약. 원 배치 대비 수행수로 선형 환산한 참고시간은 약54분이나 시간·수렴 보장이 아니다. checkpoint를 쓰는 추가 비용도 있다. Python/native 전체 정지를 항상 watchdog으로 해결한다고 가정하지 않는다. 정상 Ctrl+C는 현재 단위 종료 뒤 paused이며, 공백은 별도 기록하고 Resume 활성시간을 누적한다. 두 번째 Ctrl+C·강제 종료는 clean pause로 인증하지 않는다.

v2 plan SHA별 소비 claim은 **정식 Run 때만** 새로 생성한다. 완료/중단 뒤 새 출력 경로로 같은 계획을 반복하는 것도 차단한다. Resume는 같은 paused 출력·소스/환경/hash·원래claim 소유권을 요구한다. v1 checkpoint 이관은 지원하지 않는다. 기존 계획/원본의 consumed 상태를 초기화하지 않는다.

## 검증·후속 실행

최종 관련14시험과 실제PowerShell Check가 통과했다. fixture의 실제학습→검증→동결→주/과부하시험→receipt·두 경로 actor/CSV byte일치·원래오류와receipt오류 분리를 검사했다. Check는 정책엔진/optimizer 호출금지 mock와 파일목록/claim 부재로 확인했다. 개발 중 선언필드 context 중복과 검증키numpy정수 JSON 직렬화 문제는 PC에서 수정했다. 개발fixture와 정식학습·실기기 결과는 구분한다. 정확한 최종 대상·명령/시각·PC 소비는 verification.json을 따른다.

```powershell
Set-Location 'C:\Users\LG\AndroidStudioProjects\D1Check-model02b'
& '.\tools\RUN_QUEUE_PPO_V2.ps1' -Action Check -Output 'output/queue_ppo_feasible_v2' -Python 'C:\Users\LG\AppData\Local\Programs\Python\Python311\python.exe'
# 사용자가 정식 학습을 시작할 때만:
& '.\tools\RUN_QUEUE_PPO_V2.ps1' -Action Run -Output 'output/queue_ppo_feasible_v2' -Python 'C:\Users\LG\AppData\Local\Programs\Python\Python311\python.exe'
# Ctrl+C 한 번 → paused/프로세스 종료 확인 → 동일 폴더 재개:
& '.\tools\RUN_QUEUE_PPO_V2.ps1' -Action Resume -Output 'output/queue_ppo_feasible_v2' -Python 'C:\Users\LG\AppData\Local\Programs\Python\Python311\python.exe'
& '.\tools\RUN_QUEUE_PPO_V2.ps1' -Action Status -Output 'output/queue_ppo_feasible_v2'
```

다른 PC에서는 검증한 Python3.11.9/Torch2.11.0+cpu/NumPy2.4.6 환경을 지정한다. wrapper는 이 호출에만 MKL순차/UTF8을 설정한다. 입력/계약/소스변경·손상·활성/미확인 owner·소비/완료재실행은 차단한다.

학습 진행에는 에너지/실패cost/열cost/승수, WAIT·단일합법행동 수, return/advantage scale을 남긴다. 최종 결정 기록에는 당시 공개 큐/lane·평균시간 가드 전후 예측을 남기되 actor 입력을 늘리지는 않았다. actual lane 해제 전 재사용·미래정보 입력은 기존 엔진 경계를 유지한다.

원본 없이 공유 판독은 위CSV/JSON에서 읽을 수 있다. 원본으로 동일 판독을 재생성하려면 `python -B -m tools.d1_queue_ppo_design --legacy-root <v1/resume_v1>`을 현재 결과 디렉터리가 없는 **별도 checkout**에서 사용한다. 기존 evidence 덮어쓰기는 차단한다. Check와 이후 v2 실행에는 Git 밖 v1 raw/actor가 필요하지 않다.

## 결과 이후 종료 조건과 남은 범위

개선 후보·상충·동률·제약실패 중 나온 결과로 종료한다. 좋은 결과가 나올 때까지 후보/보상/seed를 반복 교체하지 않는다. J/AP가 작게 좋아져도 실제 controller 비용·동일입력 대응 차이 식별·독립폰 확인은 별도다. 초기 열 이력 하나와 세 고정 서비스문맥의 일반화를 보장하지 않는다. 열→처리시간은 없으며 AP 면적은 유효유휴기준 초과의 유한창 대리지표다. 창 밖 잔열 이동을 전체 발열 감소라고 하지 않는다. S26 계수·스로틀을 A24에 넣지 않는다.

다음 행동 하나: 위Check를 확인하고 사용자의 터미널에서 v2 Run을 시작한다. 이번 PC 준비에서는 Run/Resume·실측·기기명령·정식소비claim을 생성하지 않았다.
