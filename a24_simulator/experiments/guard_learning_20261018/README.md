# 보호없는 paired학습과 원인 보완

동일한 원CP(seed3701/EP64), Adam, action/shuffle RNG에서 원ON/원OFF/보완OFF를 각각 신규32episode(16PPO업데이트) fine-tune한다. 새학습8입력=중간6/3배2, 4pass를 동일순서로 반복하며 EDF reference8과 원10+중간20의EVAL90을 합쳐194 native다. 최종신규EP32는 결과 전에 고정한다. 원10/중간20은 이미본 탐색입력이며 새로운formal test/다seed/수렴이라고 하지 않는다.

보완OFF는 최대8후보 안의 공개명목 에너지/전력head, 큐/지연의 저구간보존 로그꼬리, 자기완료 총소비(기저+증분), EDF동결창 평균열 비용을 쓴다. 에너지/열 가중치.5/.5와 납기8/4·미응답30은 유지하고 창밖미완료에도30의soft벌점을 추가한다. 원물리/입력/상대납기/CPU·GPU각1/WAIT12초·선두1.5초·공통모음은 불변이다. NN logit만 선택하며 긴급납기WAIT mask만 OFF다. 물리계수를 조정해 차이를 강제하지 않는다.

실제EDF H는 trainer 보상/사후검증라벨이고 actor case/입력/전망에는 없다. 전망은 현재visible최대8과owners의 공개명목work/minimum_speed로 모든후보공통의 유한창을 계산한다. 공개 자기완료총소비/공통창평균열의 비용형식을 실제label과 맞추되 두H값이같다고 하지 않는다. 예측정규화는 보이는요청수이며 전caseN에희석하지않는다. 모든 후보와원32차원NN ABI를 보존하고기존fixed ATCprior는0이다. 보완은묶음개입으로개별구성요소의기여를분해한것은아니다.

새208 cap은 중간부하미사용8이전+신규200이며194계획/잔14자동소비0이다. 등록/게시 전환경0·기존다른잔여불변·own1/global2·공유byte0mutex·C/D8GiB·2시간cap·새물리fit/기기0이다. 새8은행을위해기존timing모형1회복원하며actor에잠재/미래를주지않는다. 기존30은행은읽기재사용한다. 환경/등록을소비한경우재실행하지않고실패/미시작을구분한다.

모든194행(학습96/reference8/평가90)을기존232에덧붙여426행을표시한다. 납기/미완료/온도창/학습선정제외는비고에명시하고분모에서누락하지않는다. 원보호해제추론40과보호없이학습32를구분한다. 학습의모든BEFORE/AFTER/Adam/RNG/frame/cost와확률선택exactreplay, 평가NN전수Float64argmax/물리·잠재·납기·보상독립검산을남긴다. A24가설J*/AP이며실측기기우위/정확최적/다seed신뢰구간을주장하지않는다.

사용자의 2026-10-18 제약완화 허용에 따라 AST/import/합성snapshot 검사만 Python 최대3(가용RAM1GiB/논리코어4 이상)에서 허용한다. native/학습/모형복원/LP는 이 예외를 쓰지 않고 기존global2와공유byte0mutex를 유지한다. 실제20논리코어이나 당시가용RAM약1.9GB여서 두시뮬레이션 동시생산은 선택하지 않았다.

현재실행관리개정: 사용자가허용한독립결정론계산globalPython3/ownA24 1·single-thread·전용A24잠금과SHA고정peer/RAM/디스크검사를쓴다. 실제모형/입력/NN계약은불변이다. 원직렬소스와PREFLIGHT_RESULT는93e7784 및prestart_history에보존하고개정검사는PREFLIGHT_RESULT_V2로별도남긴다. 아직이단계OP는등록하지않았다.

개정저장감사: 모든TRAIN/EVAL의선택logprob·critic을raw에보존하고별도Float64로검산한다. 학습96의동일Torch선택/RNG뿐아니라48회의저장PPO/Adam/양RNG/로그산술도exactreplay하여동일AFTERsnapshot과대조한다. 이는저장산술검산이며새환경/학습자료/정책선정/실험조건을추가하지않는다. 원10입력의공개명목벡터13390개는기존RL호출에서상수/완전성을확인해40KB캐시로보존했고잠재timing/미래도착을추출하지않았다. 부분맵인원witness NOMINALS 재사용실패는별도기록하고사용하지않는다.
