# 공동 롤링 실행 첫 행동 선택기의 소규모 전체 요청 흐름 파일럿 준비

작업 `ROLLING-EXECUTION-PILOT-06`. 사용자 “소규모 전체 요청 흐름 파일럿 준비해” 지시로 **새 정책을 평가 경로에 연결하고 입력·정책·예산·판정·native gate를 준비했다. 본 배치와 native gate는 아직 실행하지 않았다.**

## 출발 근거와 이번 변경

[8개 공개 상태 진단](ROLLING_PREFIX_OPPORTUNITY_20261010.md)에서 기존과 다른 실행prefix 기회1개를 확인했다. 순간 몰림의 탐지4건을0.25초 늦춰 기한·긴급P95·예측J는 같고 예상최고AP는 약0.0142°C 낮았다. 이는 현재큐의 조건부 예측이며 전체 요청 흐름과 미래 도착까지의 개선은 아니다.

새 정책 ID는 `IE_ROLLING_EXECUTION_PREFIX_GLOBAL_KPI_WAIT025_V1`이다. `tools/d1_rolling_execution_prefix.py`가 원창4·CPU전용 최소여유·과업내EDD·원mean선별8/동일첫계획당최대2를 유지하고 실제 단건/동시쌍/대기 동치별로 예측한다. 기존 V2의 “전체계획1등→첫행동검사”와 별도 코드/ID로 보존한다. 최악 전체최고AP→J→기존후보순번으로 선택하며 같은Band행동·미래AP만감소·모호한출처는 이득으로 세지 않는다.

현재 공개큐·실제lane 소유·phase/since/dispatch·관측응답·credit·모형추정T/h/Band EMA만 쓴다. 실제 미래 도착/실현 잔여비용/기기내부열상태는 받지 않는다. WAIT예측은 새도착이 없다는 조건부 Band후속이며 실제 도착/AVAILABLE에서 취소·재판단한다. 선점·주파수·전력제한·NPU·새모델·새계수는 추가하지 않는다.

## 비교군과 고정 입력

|역할|정책 ID/의미|
|---|---|
|Band|공개판단의 기존 whole-request 대응 `BAND_HEFT_WHOLE_REQUEST_ADAPT_V1`|
|Triton|기존 고정instance/rate-off 요청 대응|
|OriginalV2|원 공동계획＋실제첫prefix검사 `IE_ROLLING_JOINT_ACTUAL_PREFIX_GUARD_WAIT025_V2`|
|ExecutionPrefix|이번 실제첫행동 직접선정 정책|

새 도착 seed `825060101/825060102`×낮은부하/큐몰림/순간몰림/지속부하×mean/short_context/long_context＝**24조건×4정책＝96행**이다. 두 seed의 기존등록 사용 이력을 검사했다. 세 문맥은 기존 처리시간 민감도이며 독립3반복/정밀확률오차범위가 아니다. 이전 확인24/48이나 이번진단8상태를 새 독립확인으로 재사용하지 않는다. 이 배치는 새로운 작은 **개발pilot**이며 최종확인/실기기 검증이 아니다.

모든 역할에 같은 티켓/입력/도착/기한/초기관측/자원/문맥/실현seed201/실현비용을 적용한다. 각 정책 예정1584건, 비교6336건과 native gate8건이다. 분류CPU/GPU·탐지CPU·CG_DC 최대2건만 허용한다. 응답은 분류OUTPUT_READY/탐지PERSISTED, 자원 반환은 실제AVAILABLE5단계다. 원 기한1.5/6초·J0..120초·AP35..180초1초격자·원모형SHA5682082a…/초기관측42f60312…를 고정했다.

기본정책·원V2·RL 체크포인트·strict·experiment_ready=false는 바꾸지 않는다. 별도 중단 중인 모형v2/실측7자료·미완성PAR·계수는 사용하거나 재개하지 않는다. 초기 열→처리속도회복 법칙도 추가하지 않는다.

## 실행 의미 gate4와 기능 검사

native gate는 다음4환경이고 성능 평가와 분리한다. 각2요청·계측은 같은 원모형이며 scripted choice는 gate에서만 사용한다.

1. D의0.25초 냉각 대기 중 C가 도착하면 대기를 취소하고 즉시 다시 선택한다.
2. D가CPU를 소유한 동안 phase/worker release로 hold를 끝내지 않고 실제AVAILABLE 뒤 C를 배정한다.
3. 허용된 C_GPU＋D_CPU 쌍은 첫dispatch 뒤 같은시각에 두 번째를 commit한다.
4. 일부러 stale pending을 주입해 둘째commit을 취소해도 요청을 보존하고 다시 배정한다.

순수검사32개 PASS:새adapter7＋준비/서비스판정8＋기존선택기17. 준비 검사에서 future arrival 취소, timer진행/credit소진, 어떤lane의AVAILABLE든 resourcehold종료, worker소유유지, 쌍commit/실패요청보존, 실제점유lane 재배정 거절, 긴급냉각거절을 확인했다. 누락/중복조건·미완료량·결측비용·서비스악화·주부하절대기한을 성공으로 세지 않는 판정과 공유물검사로 local 실행장부가 새로 생기지 않는 경계도 검사했다. 선택은 mock으로 주입한 **기능 검사**이며 native gate 통과나 성능 개선으로 표시하지 않는다. 이번 새 미래작업 예측/환경/학습/기기 시작은0이다.

## 예산·clock·재개

예상 native100＝gate4＋배치96, 상한112(실패포함), 학습0/기기0/튜닝0다. 기존9749환경/1449학습·닫힌IE480/480·진단170/792를 보존한다. 정상100을 완료하면 누적9849/1449, 상한소진이면9861/1449다. 같은태스크를 새폴더로 옮겨 새예산을 얻지 않는다.

**준비 시각은 실행 clock의 시작이 아니다.** 이번 `prepare/check`는 activation/owner/native장부를 생성하지 않는다. 다음 명시적 실행지시로 `run`을 호출할 때 gate전에1시간 wallclock/마지막5분저장을 한 번 시작한다. 이후 같은activation과 소비장부를 계승하며 재개로clock을 초기화하지 않는다. 완료조건은 source/input SHA가 같을 때만 재사용하며 실패ID 자동재실행·상한증가·실행source 몰래교체는 금지한다. 원시간을 넘긴 경우 새권한 없이clock을 새로 만들지 않는다.

## 판정과 산출물

완료/예정/실패·미완료·전체도착 기준 긴급·일반 기한실패, 긴급P95, 일반평균완료, J120, 같은AP최고/경로, 점유/병행·PC판단시간/대기/선택 수를 보고한다. 서비스·전체작업량 먼저, 에너지/AP 차이 나중이다. 전체미완료면 비용적격이 아니며 총J/AP를 null로 둔다. 표면온도·안전한도 초과시간·폰 제어J는 지원불가/null이다. PC판단부담은 기록하지만 기존0증분제어비용 가정을 임의로폰 실측으로 환산하지 않는다.

Band/Triton 양쪽과 **24조건 모두** 완료·긴급/일반 기한실패·긴급P95·J·AP 비악화, 주 low/sustained 절대기한을 요구한다. 이 유지조건을 만족하며 한 주부하군의 모든seed/문맥에서 AP 또는J가 엄격감소해야 유망이다. 최종epsilon0·동일원단위KPI이고 평균·최고seed로 조건별 손실을 가리지 않는다. 원V2의 대응차이도 전량 보고한다. 일반평균지연을 새하드제약으로 몰래추가하지 않으며 지연 상충은 계속 표시한다.

입력/정책/선정은 결과전에 동결한다. 결과 후 가중치·기한·허용오차·후보공간을 바꾸거나 추가학습·새실측으로 구제하지 않는다. 통과해도 앱기본/strict를 자동교체하지 않고 새독립확인과 실기기효과는 별도다. 미달이면 후속학습/확인을 자동확대하지 않는다.

## 준비 상태와 재현

[실행계약](results/rolling_execution_pilot_06/execution_contract.json) · [24입력＋gate](results/rolling_execution_pilot_06/cases.json) · [준비 화면](results/rolling_execution_pilot_06/index.html) · [검증](results/rolling_execution_pilot_06/preparation_verification.json).

```powershell
python -B -X utf8 -m tools.d1_rolling_execution_pilot check
python -B -X utf8 -m unittest tools.test_d1_rolling_execution_prefix tools.test_d1_rolling_execution_pilot tools.test_d1_rolling_prefix_selection -v
```

위 명령은 본 배치/기기를 실행하지 않는다. GitHub 공유물만 받은 경로에서도 `check`는 공유source/입력을 읽기전용검사하며 새local budget을 만들지 않는다. 사용자 실행지시 이후 원local 준비/소비계보에서 사용할 명령은 `python -B -X utf8 -m tools.d1_rolling_execution_pilot run`이며 gate4 PASS후 고정96행으로 이어진다. `prepare`는 이미 준비된 같은입력/source면 검사만 반환한다. 현재 native gate/본배치/학습/기기0, 실행clock 미시작·owner없음이다.
