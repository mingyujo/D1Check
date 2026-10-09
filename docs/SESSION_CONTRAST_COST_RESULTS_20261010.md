# 토론 후 실제 비교: AP 추가 개선과 전이 악화

**새 AP 후보는 LOAD의 긴 관측창 MAE를0.173→0.129°C로 더 줄였다. 같은600초에서 J/AP도 함께 개선됐다. 그러나 과거20의AP와긴창의J·정책차이는악화해전체모형교체는하지않는다.** 이전 zero-offset+고정LOAD_SLOW를주진단경로로유지하고,새후보는버전·hash가분리된명시적전이진단API로보존했다. 추가실측은없다.

## 토론이 실제 구현에 반영된 과정

세 검토 AI가 모형·식별·시뮬레이터 관점에서 독립검토와 직접반론을 수행했다. 사람 전문가 인증은 아니다. 초기중심화 가설→같은자료 대조 추가→고정AP basis 재추정 추가→실제결과 재검토의4차를 보존했다.

- 전력계수가세션배경편향을흡수할수있다는가설에는근거가있었다. 하지만새개발13과이전개발4를그냥비교하면자료확대와중심화효과가혼동되므로같은13의일반/중심화대조를추가했다.
- 고정AP를그대로쓰면추가AP개선이불가능하다는반론을수용했다. AP의기존수식·시간상수·원전력proxy를유지한채5계수만별도재추정했다.
- 실행후에는에너지에서일반방식이선택됐음을확인했다. 에너지개선을중심화의효과라고쓰지않는다. AP평가악화와냉각변화량악화도인정해전면교체를거부했다.

[실행 전 토론](results/session_contrast_cost_01/review_manifest.json) / [실행 후 반론·합의](results/session_contrast_cost_01/post_eval_review_manifest.json) / [최종 세 노트](results/session_contrast_cost_01/README.md).

## 동일13 자료의 유한 대조와 실제 소비

개발은과거개발3+이력개발6+macro개발4=13이다. 이전29아카이브중9가이번학습에사용됐으므로추정미사용평가는과거20+긴2=22로분리했다. 이전29평균과새20평균을직접비교하지않는다. 센서표본을독립세션으로나누지않았다.

실제manifest13의모델/runtime/tensor/입력/실행/품질기준·CPU1·4resident·기기는동일했다. 그러나baseline30↔120초,공통120↔600초,냉각60↔180초,기록version·APK는달랐다. **같은계측13반복이아닌여러프로토콜에서공통계수의전이를시험하는사후연구**다. [작은계약대조](results/session_contrast_cost_01/native13_contract_audit.json).

- 두방법:일반least-squares와세션내중심화least-squares. 계수는비음수로제한하되중심화된음수X/y는자르지않는다.
- 에너지X는5초구간의4상태실제lane점유시간, y는관측J−P50×5초다. 초기전력은원50초관측을유지했다.
- AP X는기존LOAD_SLOW의빠른4항+느린1항, y는관측AP−pre자료로만초기화한경로다. β/preparationτ30/slowτ1920/원전력proxy는고정했고grid탐색0이다.
- 중심화는개발중X와y에서각세션평균을함께빼는것이다. 학습에는추가세션수준13개가투영되므로전체학습자유도가4/5개뿐이라고하지않는다. 예측은원pre입력+원Xθ이며학습/평가세션평균·nuisance를더하지않는다.
- old/history30/history180/macro 네묶음제외4+최종1,두방법×E/AP=정식20fit(전력10/AP10)을완료했다. 네묶음은독립실측날짜4개가아니다. 시간상수prior가이미본자료로선택돼새계수제외평가는전체family의순수OOF가아니다.

개발묶음별평가만으로전력은일반13, AP는중심화13을선택·hash동결한뒤22를판독했다. 전력선택은같은등록창의절대J/시간(평균W차이),AP는절대경로MAE를source균등평균해비교했다. J/°C를섞는새가중치나평가후4조합탐색은없다. **선택은두새방법간순위이며직전모형비악화gate나정확도PASS가아니다.** [등록v2](results/session_contrast_cost_01/registration_v2.json) / [선택](results/session_contrast_cost_01/run_v1/selection.json) / [20fit receipt](results/session_contrast_cost_01/run_v1/fit_receipt.json).

## 추가 개선과 반드시 함께 보는 악화

아래는개발에서선택한전력일반/AP중심화의결과다. 모두이번추정에는쓰지않았지만이미열람한자료의사후평가다.

| LOAD 같은 구간 | 직전 J차이 → 새 J차이 | 직전 AP MAE → 새 AP |
|---|---:|---:|
| 등록600초 `[35,635]` | +2.0809→+0.9885J | 0.18615→0.16671°C |
| J/AP공통 `[37.417396683,2554.510266266]` | −6.1868→−7.1207J **악화** | 0.17296→0.12859°C |
| 덮인회복 `[635,2554.510266266]` | −7.6549→−7.6549J | 약0.1688→0.11657°C |

긴AP공통관측922표본의MAE는25.7% 더감소하고최대절대오차1.2343→1.1611°C다. 빠른CPU·탐지/GPU계수는조금커지고느린진폭은0.0071764→0.0063543으로줄었다. 이것은유효계수재추정이지새물리기제식별이아니다. 회복관측−0.700°C에대해전체회복예측변화는직전−0.633/새−0.567°C다. **냉각방향은같지만변화량오차는약0.067→0.133°C로악화**했다. 같은prefix표와전체회복방향의정확한끝표본은CSV에서구분한다. 끝전류표본누락은여전히전체회복J=null이다.

| 동일평가분모 | 직전 → 새 | 악화 |
|---|---:|---:|
| 추정미사용과거20·참고120초평균절대J | 5.4589→5.3847J | 11/20 |
| 같은20·J/AP공통관측AP평균MAE | 0.34393→0.35078°C **악화** | 12/20 |
| 같은20·35..120초AP평균MAE | 0.35542→0.37179°C **악화** | 13/20 |
| 지속CPU/PAR4짝·차이예측MAE | 6.2185→6.8991J **악화** | 부호오판2/4유지 |

AP 일반13의 과거20 평균0.32193°C는 중심화보다 좋았지만, 이를 본 뒤 선택을 바꾸지 않았다. 두 방법의 전량 표를 보존한다. C0의X/basis가0이므로 두head는 직전과 정확히 같으며 무부하·미래배경변동은 해결되지 않았다. 일부LOAD창의 공동개선을 시뮬레이터 전체 정확도 업그레이드로 표현하지 않는다. [모든방법](results/session_contrast_cost_01/run_v1/energy_errors.csv) / [AP](results/session_contrast_cost_01/run_v1/AP_errors.csv) / [동결선택J/AP표](results/session_contrast_cost_01/run_v1/selected_joint_errors.csv) / [최종미채택](results/session_contrast_cost_01/run_v1/adoption.json).

## 실제 API·검증·재현

[새API](../tools/d1_session_contrast_cost.py)는원macro6/초기정보/모델·입력·resident·프로토콜검사를유지한다. 새20모형·선택receipt·소스hash를확인하고새전력/AP를명시적으로불러온다. 원AP파일이나scope hash를바꿔끼우지않았다. 예측층위는실제일정조건부A이며필요창밖/null·RL사용차단을유지한다. 관측오차나profile별로자동버전을바꾸지않는다. 새독립확인/주사용채택은아니다.

- 단위검증4건:음수중심화보존·세션수준편향이있는합성E/AP계수복원·확인학습차단/rank·C0/미래target비사용. 합성fit2와정식fit20을구분했다.
- 실제새API에서미래AP/전력을999로바꿔도두예측불변,RL요청시두출력null,C0 AP항등을확인했다. 등록600초예제도실제호출했다. 기기안정성검증은아니다.
- 첫진입은직전보완전소스hash를복사한문제로추정전에실패했다. fit0/출력미생성이었고원등록·소스·오류를보존한후현재승인된소스byte를새등록v2로동결했다. 모델/원자료나완료fit을초기화하지않았다. [원오류](results/session_contrast_cost_01/registration_entry_failure.json).

```powershell
python -B -m unittest tools.test_d1_session_contrast_cost -v
# 원주진단경로는 그대로이며 아래는새전이후보의명시적예제다.
python -B docs/results/session_contrast_cost_01/run_example.py --opt-in --window registered600 --output output/session_contrast_LOAD.json
# 기존완료run_v1 대신새폴더에서만 별도재현한다.
python -B -m tools.d1_session_contrast_cost --action fit --output output/session_contrast_reproduce
python -B -m tools.d1_session_contrast_cost --action evaluate --output output/session_contrast_reproduce
python -B docs/results/session_contrast_cost_01/plot_results.py --output output/session_contrast_figures
```

저장B17은새개발3/추정미사용14의비용투영으로분리했고일정·응답·열→처리시간은새로검증하지않았다. 미기록B18은실제미래일정으로채우지않는다. 기존5/10초J상쇄숫자를새모형에전용하지않았다. A24 raw=mA/절대J미인증·SOC/BAT/사용시간미검증·S26계수비혼합을유지한다.

**종료판정:** 추가AP개선근거는LOAD등록조건에있으나새후보의전체교체는보류한다. 같은B2/긴C0재실측이나재보정은자동추가하지않는다. 추가자료를얻을때는새동결후독립예측확인, pre가비슷해도달라지는배경입력식별, 동일arrival의정책짝차판별중필요질문을먼저특정한다. 이번실패후보를확인하기위해실측을반복할필요는없다. 원모형·주진단경로·RL·strict·experiment_ready=false·원본/실패/소비계획을보존했고기기/ADB/실측/설치/빌드·새계획/claim0이다.
