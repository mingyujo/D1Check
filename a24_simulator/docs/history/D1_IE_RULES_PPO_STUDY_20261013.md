# 산업공학 5규칙의 공통 자원 배정 비교와 PPO 결합

최신 실행은 V8/V9 보충 등록으로 전체 완료했다. 수치·소비·한계는 [완료 결과](D1_IE_RULES_PPO_RESULTS_20261013.md)를 따른다. 아래는 최초 등록 설계이며 초기 계산 예산·진행 상태의 역사 기록이다.


2026-10-13 KST. 작업 D1-IE-RULES-PPO-26. 사용자 승인: 24회차를 그대로 두고 SPT/WSPT/EDD/LST/ATC를 같은 자원 배정에서 비교하고, 에너지·평균온도를 확인한 뒤 유망 규칙과 PPO 후속 실험까지 설계·진행한다. 이 계약은 신규 환경/학습 전에 동결한다. 최초 등록 시 이번 환경/학습/fit/APK/기기0이며 기존 프로젝트 이력을 초기화하지 않는다.

## 목표와 증거 범위

같은 요청과 물리 모형에서 순위 규칙의 변화가 실제 실행 일정/자원 배정/병행을 바꾸고, 그 결과 J와 시간평균 AP가 달라지는지 검증한다. 특정 규칙/PPO 승리를 전제하지 않는다. 기존20/21의 기기별 세 프로필을 그대로 사용한다. CPU8W/GPU1W/NPU.4W 추가 실행 전력, 열/최근부하 감속과 탐지 실행 .35배는 탐색 가정이며 폰 실측값이 아니다. M6 최신 전력/열 모형과24의 학습/선정 결과는 섞지 않는다.

## 공통 실행·배정 계약

- 이미 도착·미시작 전체 큐, 최대64. 초과시 잘라내지 않고 오류 처리한다.
- C_CPU/C_GPU, S26 C_NPU, D_CPU 및 CG_DC/CN_DC 최대2만 지원한다. 실제AVAILABLE까지 점유, 비선점, 응답/점유 종료 분리, 임의 냉각대기0이다.
- 각 요청의 현재 물리적 합법 경로 중 `(예상 응답시간, 예상 점유시간, CPU/GPU/NPU 순서)` 최소 경로를 공통 배정기가 선택한다. 가용 요청이 있으면 실행하는 non-delay 계약이다. 5규칙과 PPO 모두 같은 배정기를 쓴다.
- 요청 순서가 가용 상태를 바꾸므로 최종 backend 수는 달라질 수 있다. 같은 배정 정책은 고정 backend 배정표를 뜻하지 않는다. 순위와 배정기의 상호작용을 보고한다.

## 5개 규칙의 앱 적용 정의

현재시간 t, 요청 도착 a, `d=a+min(선언 기한, 원 긴급1.5초/일반6초)`다. p는 공통 배정 경로의 예상 전체 점유시간, r은 그 경로의 요청 응답시간(긴급 OUTPUT_READY/일반 PERSISTED)이다. 추정에는 공개 기기별 평균·현재 관측·과거 활동만 사용한다. 미래 실현 처리시간/전체 큐 rollout/미래 J/AP는 사용하지 않는다.

|규칙|작은 값 우선의 요청 키|
|---|---|
|SPT|p|
|WSPT|p/w|
|EDD|d|
|LST|d-t-r|
|ATC|`-[log(w)-log(p/1s)-max(d-t-r,0)/(2*mean_ready_p)]`|

w는 긴급2/일반1의 연구 정책 입력이며 측정 경제 비용이 아니다. ATC k=2 고정, mean_ready_p는 현재 ready 요청들의 공통 경로 p 평균이다. 동점은 도착→ordinal→id다. 고전 ATC의 p를 납기여유에도 쓰는 원식과 달리 r을 사용해 응답/AVAILABLE 구분을 반영한 앱 변형이다. LST도 같은 응답 여유 변형이다. 고전 단일기계 최적성 보장을 이 이종자원 온라인 환경에 전용하지 않는다.

현재24 SPT의 통합 요청/점유경로 선택 및 EDD/ATC 경로 선택과 다른 별도 정의다. 24 규칙/소스/납기 정의는 변경하지 않는다.

## 자료·발견·학습·확인

새 TRAIN arrival seed926100101..108, DEV926200101/102, FINAL926300101..104다. 각 seed: 기기2×32/64요청2×steady/bursty2×원/선언기한2×프로필3=48조건, 균형 C:D=1:1이다. 전체 TRAIN384/DEV96/FINAL192. 기기별 초기/부하 생성은 기존21 방식, 공개 도착35~95초·단일32와합성1~3 units64를 구분한다. 예정 납기/프로필만 다른 입력은 같은 환경 난수 quantile을 대응한다. 학습seed와 환경 난수를 분리한다. 새 독립 기기 실측은 아니다.

주범위는 양 기기 light32/steady로 결과 전 고정한다. burst32/heavy64도 DEV/FINAL 전체 표에 남기며 실패/미완료/비용null을 삭제하지 않는다. 공통SLA 비용표는 모든 최종정책이 전량완료·원/선언 U/N 위반0인 조건 교집합이며 전체 분모/조건을 같이 보고한다. 정책별 성공행만 평균내지 않는다.

1. DEV96×5=480 규칙 환경. 주 서비스 적격→벌점, light32 전체 적격→벌점, 주 평균J→평균AP→전체 미완료/벌점으로 사전 순서를 정한다. 첫 규칙은 energy-first, 둘째는 같은 service tier에서 thermal-first이며 실행 원장이 달라야 한다. 둘이 같으면 다음 순위의 다른 일정 규칙을 고른다. 모두 동형이면1개만 학습하고 중복을 공개한다. FINAL을 보며 규칙을 고르지 않는다.
2. 선정 규칙 최대2개와 DIRECT를 fresh1523/1529/1531로 학습한다. 최대3arm×3seed×96=864 학습, stage48/96. 같은 seed 초기NN/빈Adam/action·shuffle RNG와 같은96 요청열 순서를 맞춘다. 학습은 light32 steady72/bursty24, 기기별48회이며 새 TRAIN의 서로 다른96 case를 쓴다. 과부하는 학습 경험에서 제외한 사전 영역 선택이며 FINAL 전체 범위는 보존한다.
3. DIRECT는 전체 ready 요청을 검토한다. HYBRID는 선정 산업공학 규칙의 top4 ready 요청+가장 오래된 ready C/D 보충, 최대6 요청이다. 후보 밖 요청은 다음 사건에서 재검토하고 이미 실행 중 요청은 유지한다. PPO는 요청을 고르고 공통 배정기가 자원을 정한다. 자원 배정 학습을 섞지 않는다.
4. 동일1455/193×32 크기지만 새schema와 fresh 가중치다. DIRECT의 ATC/EDD/SPT 특징17:21은0, HYBRID에는 선정 규칙 rank/64와 선두flag만 넣는다. 산업공학 후보 제한+특징을 묶은 대조이며 순수 특징효과가 아니다. 신경망/PPO update는 기존 native를 재사용한다. 초기actor 마지막0·학습sample, DEV/FINAL maskedargmax다.
5. 보상은21의 서비스 우선/전량·무위반 때만 총J/평균AP 보너스를 동일 적용한다. 임의 비용 증폭/허용치 완화0이다. 비용항의 상쇄 가능성은 그대로 보고하되 양의 보상을 동시개선으로 해석하지 않는다. ATC 공통배정 reference96개는 사후 label만 제공하며 online feature0이다.
6. 각48/96 stage DEV light32 48조건에서 모든seed를 평가한다. 서비스·J·평균AP의 사전key로 checkpoint를 고르고, 최종 전에9개 이하 모델의SHA를 고정한다. 실패모델을CP0로 바꾸지 않는다. 기존24/21 weights는 초기화/후속 선정에 사용하지 않는다.
7. FINAL192×(5규칙+최대9PPO)=최대2688 고정추론을 수행한다. 새4arrival seed의 전체조건/주범위/공통SLA 표를 보고한다. 모든3학습seed/기기/프로필/도착형태의 손해를 보존한다. 확인 뒤 재학습/seed·checkpoint 재선정0이다.

## 평가·판정

서비스와 J는0~120초, AP는35~180초의 시간 적분/145초다. peak AP와 완료응답P95는 별도 보존한다. 결과는 총J와시간평균AP의 절대차·상대J%·조건별승동패/최악값·실행원장 동일성을 보고한다. 같은작업·서비스적격범위에서 두비용 평균이 동시 비악화이고 하나가 감소하면 후속연구 후보, 조건별손해/seed불안정은 별도 판단한다. 모든 비용이동형이면 효과미확인으로 종료한다. 상대부하/처리시간/전력/기한을 확인 뒤 바꿔 격차를 만들지 않는다.

## 계산 예산·보존·검증

예정 최대4992환경=DEV규칙480+reference96+학습864+DEV PPO864+FINAL2688, cap6000/학습864/총5400초·마지막900초reserve다. worker1/Torch1, available RAM1.5GiB·free disk1.5GiB를 환경 경계에서 확인하고 기존24의 실행·디스크를 삭제/중단하지 않는다. 경계시 부분소비/가중치를 보존하며 deadline을 자동연장하지 않는다. 현재 공유PC 비용은폰 시간/전력으로 환산하지 않는다.

원24 d24_data/study/recovery/test·원등록프로토콜SHA를 시작/종료에 대조한다. 기존21 native/plant 소스·사용자WIP·기기별 프로필을 보존하고 새파일work/d26_{policy,data,study}.py와test_d26.py만 구현한다. 문서 진행 항목은 기존문서 전체 이력을 유지하면서 추가한다.

순수5검사(공통배정/순위/후보상한/특징제거/오류경계), 각rollout 물리원장·배정일치·fullmask, 업데이트 전 NN forward 전량 재계산, 실제partial59 pending/NN/Adam/RNG exact복원, raw/NN SHA·MC telescope·FINAL matrix·소비원장·24SHA검사를 수행한다. fit/APK/기기/외부전송/앱기본교체0이다.

근거: work/repo/tools/d1_sched_dynamics_{policy,ppo,plant,study}.py, d1_sched_landscape_plant.py, work/d21_objective.py·d21_study.py, 기존21 profiles와등록. 고전규칙 https://riot.ieor.berkeley.edu/Applications/Scheduling/algorithms.html. 산출물은이폴더의RESULTS.md/CSV/선정SHA/FINAL_AUDIT.json 및 docs/D1_IE_RULES_PPO_STUDY_20261013.md다.
