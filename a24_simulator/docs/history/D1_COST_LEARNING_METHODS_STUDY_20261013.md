# 기기별 열·에너지 비용 학습 대조 계획 — D1-COST-LEARNING-METHODS-27

2026-10-13. 현재 **PREPARING / 등록·실제 수집 전**이다. 사용자는 전문가 토론 대안을 실제 실험하고 기기별 제약 차이를 검토하면서 자율적으로 발전시키는 후속 작업을 승인했다. 준비 단계 신규 환경/학습/native/기기 실행은0이며 과거 전체 실행 이력을0으로바꾸지않는다.

열·에너지 감소가 주목적이고 기한·납기는 지켜야 할 제약이다. 기한 안 응답시간·P95 단축 자체를 보상/선정 목표로삼지않는다. 원24 및 산업공학26과다른S26개발의source·등록·모델·입력·원자료·FAIL·보고를보존하고별도27만추가한다.

[상세 계약 초안](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/D1-COST-LEARNING-METHODS-27/PROTOCOL_DRAFT.md), [자료·선정 API 초안](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/D1-COST-LEARNING-METHODS-27/DATA_ANALYSIS_DESIGN_DRAFT.md). 정식source/input/프로토콜/clock/초기모델등록은주실행기가실행전에고정한다. 예정루트는 `D:/Codex-D1-COST-LEARNING-METHODS-27-20261013`이며기존C자료를삭제하거나이동하는작업이아니다.

## 실험 질문과 대조

1. 비용신호의합산상쇄를없앤Pareto형보상,전량완료gate,작은기기별비용척도가실제J/AP공동감소에기여하는가?
2. 서비스선행학습·ATC행동warm·GAE가같은기기노출량에서비용학습을개선하는가?
3. ATC특징의추가기여가있는가? 제한WAIT의행동기회확장이기한을지키며비용을줄이는가?

각기기CONTROL/PARETO_HARD/PARETO_EQUALWORK/COST_SCALE/SERVICE_FIRST/ATC_WARM/NO_ATC/GAE/WAIT의9군×fresh1571/1579/1583,총54모델이다. 전용학습이며모든군은의도된warm조작이전동형초기network·빈Adam·action/shuffleRNG에서시작한다. 기존학습가중치/Adam재사용0이다.

PARETO_HARD는CONTROL대비비용표현만, PARETO_EQUALWORK와COST_SCALE은PARETO_HARD대비각각gate와척도만변경하는대조다. 나머지는CONTROL상대각한축대조다. arm별로다른checkpoint/seed가선정된최종차이를순수단일원인효과라고하지않고matched-stageDEV와모든seed를함께보고한다.

SERVICE_FIRST는첫64episode서비스만학습한뒤CONTROL보상으로전환한다. ATC_WARM은사전64case행동BC소비를별도기록하고PPOAdam을빈상태로시작한다. NO_ATC는FIFO슬롯/EDD/SPT/마스크를유지하면서ATC특징17·19를state/candidate양쪽에서제거한다. GAE만gamma1/lambda.95를쓴다.

## 새 자료와 기기별 계약

TRAIN927100101~116 총1536(각기기768), DEV927200101/102 총192(각96), FINAL927300101/102 총192(각96)다. 기존물리pool과계수는그대로이고도착/자료분리를새로고정한다. 원24/26FINAL은학습/선정에쓰지않는다. primary는A24light32·steady24조건/S26light32모두48조건이다. 앞선결과를읽은뒤이번확인전에고정했다는설계시점을공개한다.

TRAIN은8episode당primary6/nonprimary2의75/25노출,각subset안정hash순서순환이다. 같은기기의모든arm·seed는같은case순서를본다. 반복rollout은새on-policy실행으로세되새입력/실측으로세지않는다. ATCreference는uniquecase별1회만세고SHA재사용한다. profile/선언기한을바꿔도같은입력quantile을맞춘다.

| 계약 | A24 | S26 |
|---|---|---|
| 분류 지원 | CPU/GPU | CPU/GPU/NPU 기존모형지원 |
| 탐지/병행 | 탐지CPU·CG_DC≤2 | 탐지CPU·CG_DC/CN_DC≤2 |
| optional WAIT | 100ms·누적1초 | 250ms·누적2초 |
| COST_SCALE | 5J/.1℃ | 2.5J/.05℃ |

사용자가기한·납기를기기별로새설계하도록선택했다. 기존초안U1.5/N6잠정유지는선택전이력이며원24/26은불변이다. 첫4×단일warm응답초안(A24U1.20/N2.5,S26U.30/N1.0)은S26명목6C burst의strong최단.0650848초×6>.30초라는nominal검사로등록전에대체하고`slo_preparation_history/WARM4X`에보존했다. 정책결과를본변경이아니며실제환경0/CP00이다.

최종새절대SLO는A24 U2.20/N5.0초,S26 U.80/N2.0초다. TRAIN세profile중지원분류최단(response[:2]+startup)의최악값/탐지CPU(response[:3]+startup)의최악값에각각명목burst폭6/4와queue·온도여유2를곱해50ms상향반올림했다. 기준은A24.181640507/.619471443초,S26.065084821/.248297715초다. originalmode는같은SLO, varied는A24urgent .5/.75/1배·나머지세쌍 .75/1/1.5배정수ns이며물리declared상한U2.5/N9를유지한다. startup·profile은변경하지않는다.

새SLO는비용목적의여유scenario이지사용자실제SLA/납기보장이아니다. 6C/4N는명목mix폭이며실제cluster개수는변동하고queue/열/backlog로primary도실패할수있어이를조건제외로감추지않는다. legacy1.5/6은별도진단으로남긴다. q공개7키는그대로,case의service_caps_ns/service_contract와새declaredSHA에계약을고정한다. 도착·작업·units·환경seed·profile등전체grid불변을검산한다. 등록후결과맞춤완화0이다. 지원차이는기기별프로필/기존capability로다루며새NPU지원·GPU탐지·분류2건·3건병행·선점·이동을추가하지않는다. 실제AVAILABLE점유와긴급OUTPUT_READY/일반PERSISTED응답을분리한다.

공유새ABI는1457state/193slots×33candidate다. WAIT상태2개·행동특징1개를추가한별도schema이므로원1455/32가중치를그대로재사용하지않는다. 다른군추가값은0이고기본non-delay다. fullqueue≤64·FIFO슬롯·single-dispatch동시각재구축을유지한다. WAIT는normal-only와현재단일응답slack가드/실제경과누적예산이며미래큐시뮬레이션/납기보장/무제한냉각이아니다.

## 보상과 채택

원/선언긴급각20·일반각5, 미완료요청50+unit50벌점은유지한다. CONTROL 비용은무위반·전량완료시J0~120과정확한meanAP35~180의softsign합산이다. Pareto형은한비용악화를다른비용개선으로양수보상하지않는다. equal-work군도기한벌점을없애지않는다. reference/gate/미래실현은사후label전용이며온라인입력0이다.

DEV기기별완결128부터powers2단계를선정한다. primary전량완료·원/선언U/N무위반→ATC대비평균J/AP공동비악화/하나개선→각primarycasepeak차이≤0℃를검사한다. peak0는이번새상대연구guard이며실제폰안전온도인증/과거strict변경이아니다. 평균비용후보나peak손해가있으면비용후보/peak보호실패로표시하고전체채택을보류한다. 적격없으면diagnostic동결평가이며PASS대체0이다.

FINAL은6독립규칙EDD/ATC/FIFO_READY/RR_READY/Greedy_READY/SPT+전9군×3seed,각기기33×96=3168/총6336행이다. source/input/설정/모든선정모델SHA를확인전에동결하고maskedargmax1회,확인뒤seed/checkpoint/조건재선정0이다. 모든seed·전체96·heavy·원/선언·미완료/null·조건손해·최악값을공개한다. EFT/Band추가0이다.

## 실행·저장·검산

시작24시간wall/학습18시간/마지막6시간FINAL·감사reserve,episode/environment숫자capNone,환경worker최대2/Torch1/native메모리lock1,diskguard0/RAM2GiB환경경계·최대600초대기다. 실제IO/시간/RAM중단은소비·부분RNG/Adam/pending·identity를보존하고deadline을임의연장하지않는다. 실패identity재실행/삭제/성공대체0이다.

실행권위source는C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/D27_FROZEN_CODE_20261013의immutableCODEcache이며Dcode는백업이다. CODE_BASE와D1_D27_ARTIFACT_ROOT의중량BASE를분리한다. 실제27환경0에서lossless저장층(checkpoint torchsnapshot gzip1bytes단일write/SHA/exactload,NPZ·network메모리buffer단일write)을추가하며배열/정책/math/물리/SLO/9군변경0이다. 원24의D저장대기를진단한개선이고기존24는수정하지않는다. 등록직전최종source와pure74/IO새pure2예정의검증결과를한번고정한다.

첫128단계19,840환경+원20/새27동형·WAIT검사pilot6은계획값이다. 실제수치는시작/완료/실패원장에서세며기준label재사용을중복계수하지않는다. purePASS는실제pilotPASS가아니다. 수집기는실패원자료를먼저저장하고최종NN·physical/fullmask·reward/target·native/BC/Adam/RNG·원장SHA·AVAILABLE·freeze/산술을검산한다. 감사전POST완료receipt작성0이다.

어떤기기/arm의≥2seed가두연속완결stage전환에서primary위반penalty(20/5+미완료50)가엄격히증가하면공유중단한다. 모든54모델이최근3추가전환에서primarypenalty감소도없고,두stage모두equal-work유효인쌍에서meanDeltaJ가.005J초과또는meanDeltaAP가.0005℃초과개선된전환도없으면정체중단한다. 다음완결stage는`max(600초,직전전체stage소요×2.25)`가남은학습시간에들어갈때만확대한다. 이임계값은원strict/실측효능하한과다르며마지막전체완결stage로만선정한다.

미완료equal-workJ/AP는null,관측prefix/완료량은별도다. totalJ/기한내성공요청은서비스결합보조효율이며순수총J절감률이아니다. ℃/성공건수·성공행만골라평균내기0이다. J180/peak/고온구간과PC판단·저장·공유host간섭을별도로보고한다. CPU분류4표본·finitepool·8/1/.4W/열/감속/탐지.35배가정과폰미측정/품질지원의한계를공개한다.

완료는새자료비교/전수검산/후속정책추천또는보류와기록완료다. 서비스만충족하거나비용만줄고납기를놓치면목적달성으로판정하지않는다. 물리정확도·앱기본·원strict·실기기성능으로자동승격하지않는다.
