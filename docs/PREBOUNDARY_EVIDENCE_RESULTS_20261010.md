# 오차 원인의 실제 근거와 초기정보 보완 시험

**기존 기록에 있던 회복 AP를 분석 입력에서 제외한 사례와, 기준전력 구간에 추가 CPU 활동이 섞인 사례를 찾았다.** AP는 기존 계수·마지막 초기AP·시각을 그대로 두고 입력을 보완했을 때, 이미 본 확인6세션 MAE0.230→0.166°C로 감소했다. 에너지는 오차가 남는 구간과 실제 활동 차이를 수치로 특정했다. 새 실측은 없다.

## 1. 자료가 없는 것과 사용하지 않은 것을 구분

이력 실험의 원본은96요청 conditioning→등록회복30/180초→baseline30초→target 순서를 포함한다. 원모형 후속분석의 AP 초기화는 target기준−30초 이후만 받았다. 원자료에는 그보다 긴 **작업이 없는 등록회복 AP**가 남아 있었다.

- 기존 초기화:24–26표본·약60–64초.
- 복원한 초기화:회복30 조건36–37표본·약91–92초,회복180 조건95–96표본·약241–244초.
- 모든conditioning96요청의실제lane해제가회복시작보다앞임을원ledger로확인했다. 새입력은그회복시작이후만사용하며마지막AP값/시각은기존과완전히같다.
- 새입력은모두예측발행35초전에조회가끝났다. Android BOOTTIME 원점과query bracket을대조했고host wallclock을직접비교하지않았다. 미래온도·전력은예측입력에사용하지않는다.

새입력구간은결과를보고고른90/240초window가아니라 **이미등록된회복시작→예측전경계**다. 기존계약의짧은입력선택을소급해코드버그라고하지않고,현재확인한정보사용제약으로구분한다. [확보량·경계](results/preboundary_evidence_01/run_v1/availability.csv) / [원파일hash](results/preboundary_evidence_01/run_v1/source_inventory.json).

## 2. 계수 재보정 없이 AP 오차 감소를 재현

β/preparationτ30/LOAD_SLOW 빠른4계수·느린계수/τ1920을전부고정했다. 기존R/H 초기화에등록유휴pre를전달하는한가지변경만시험했다. 전역계수fit0,원/확장초기상태추정24회·AP경로재생24회다. 기존 원자료와과거결과는덮어쓰지않았다.

| 동일 세션분모 | 기존 짧은pre MAE | 등록유휴 전체pre MAE | 해석 |
|---|---:|---:|---|
| 기존개발6 | 0.13000°C | 0.13560°C | 소폭악화 |
| 이미본확인6 | 0.22962°C | 0.16630°C | **27.6%감소** |
| 확인회복30·3세션 | 0.23655°C | 0.20636°C | 감소 |
| 확인회복180·3세션 | 0.22269°C | 0.12624°C | 감소 |

확인6의평균최대절대오차는0.6900→0.6229°C로감소했지만평균최고온도절대차이는0.0561→0.0818°C로악화했다. 개발180세션3개도모두MAE악화했다. 따라서전체기본채택이나새정확도PASS로승격하지않는다. [모든12조건](results/preboundary_evidence_01/run_v1/AP_metrics.csv) / [역할별표](results/preboundary_evidence_01/run_v1/combined_readout.csv).

특히 `confirmation_180_C0`는본작업이0이다. **같은초기AP29.2°C/anchor34.391899759초/같은계수**에서MAE0.33886→0.06786°C로줄었다. 원짧은pre의유효유휴reference28.9598°C가긴pre에서는28.6168°C,초기화조건수5.865→1.854로바뀌었다. AP값을평행이동하거나새주변온도를입력한것이아니다. reference는관측pre의유효추정량이며주변온도나진짜내부열상태로인증하지않는다.

이것은 **C0를작업계수로재추정할때는못바꾸지만,원자료의초기정보를더사용하면C0 오차도바뀐다는구체적근거**다. 원자료가없다는포괄적설명은이사례에맞지않는다. 다만이미본자료의사후분석이고모든조건의일반화증거는아니다.

## 3. 에너지: 기준전력 구간의 실제 활동 차이

같은등록96conditioning/회복30/C0/4resident조건의개발·확인기록을대조했다. 날짜·초기AP·배터리까지동일한통제짝으로보지는않는다. 이미검증한Perfetto CSV를재사용했고8CPU 전구간coverage·loss0·BOOTTIME exact alignment를다시확인했다. 새TraceProcessor 실행/기기호출0이다.

| 구간 | 개발30_C0 | 확인30_C0 |
|---|---:|---:|
| pre50평균전체전력 | 0.97110W | 1.05272W |
| 이후35..120초평균전체전력 | 0.97500W | 0.97852W |
| pre50의other CPU seconds/wall second | 0.26568 | 0.39213 |
| 이후85초의other CPU seconds/wall second | 0.26553 | 0.28209 |

확인기록의pre 전력은개발보다8.4%높지만이후는0.36%차이다. pre의other CPU 활동도약47.6%많았다. 같은확인기록안에서는8core non-idle 비중6.35→4.98%,전력1.05272→0.97852W로함께줄었다. benchmark·tracer의초당CPU 시간은그변화에비해거의같았다. [4C0/8구간 원수치](results/preboundary_evidence_01/run_v1/matched_C0_CPU_context.csv).

**벤치마크lane가유휴여도기기전체활동은일정하지않았다는근거**다. `other`는기존TraceProcessor 분류이며특정다른앱·ADB·GPU·무선원인을확정하지않는다. CPU활동과전력의동시변화는관측association이고74mW 전체를CPU의인과적소비로귀속한것이아니다. 이후CPU/전력은원인분해에만사용하고예측입력에넣지않았다.

현재전력식의유휴는 `P50×시간`이다. C0/작업종료후state추가전력0이므로네작업계수를얼마나바꿔도이오차는바뀌지않는다.

- 긴C0의postlane2519.807초:pre0.978328W/관측평균0.992734W,차이−36.299J.
- 긴LOAD의postlane2009.324초:pre0.981371W/관측평균0.986844W,차이−10.998J.
- 이는해당유휴구간의state계수불변오차이며전체에너지의불가피한오차하한은아니다. 부하오차와상쇄될수있다. [35자료 유휴분해](results/preboundary_evidence_01/run_v1/idle_energy_attribution.csv).

따라서에너지의다음보완대상은새로운CPU/GPU계수반복이아닌 **pre 기준전력에섞인일시활동과이후기준부하의차이를예측가능한입력으로구분하는것**이다. 이미기록된시작전CPU활동·AP·전력과등록회복이있어PC에서먼저검토할수있다. 단일최근값또는긴pre평균을미래전체에상수로복사하는것은이차이를해결한다고보장하지않는다. [사전전력정보와사후분해구분](results/preboundary_evidence_01/run_v1/prepower_information.csv).

## 4. 추가로 시험한 부하 전 선택 규칙의 한계

전체pre를무조건사용하는방식도개발180에서악화하므로, 두초기화를마지막pre AP 한표본의부하전예측오차로선택하는규칙을별도등록해한번시험했다. 이후AP는선택에사용하지않았다. 전역계수fit0/지역상태추정36/경로재생12,숫자동률은기존짧은pre 유지다.

확인6MAE0.22962→0.21443°C로만줄었고가장큰C0개선사례에서짧은pre를잘못선택했다. **약2–3초선행검사성공이120초reference 예측성공은아니라는반례**다. 결과를본뒤다른holdout길이·threshold·좋은세션선택을추가하지않았다. 이규칙은미채택이며전체기본/주진단/RL/strict는그대로다. [사전등록](results/preboundary_evidence_01/preonly_choice_registration.json) / [전량판독](results/preboundary_evidence_01/run_v1/preonly_choice.csv).

## 5. 센서·해시·실제 경계 검증

원thermal 기록의AP는모두 `Current temperatures from HAL`의AP와일치했다. `Cached temperatures`의AP는다른값인경우가많았지만그값을예측/관측입력으로사용하지않았다. HAL값과cached값의혼동은이오차의확인된원인이아니다. 조회시각확인이하드웨어내부갱신시각·절대센서정확도인증은아니다.

재사용한36 raw 파일hash·trace export16파일hash·최종모형/초기입력hash를보존했다. 예전소비자료2개는원본내용hash로v6재사용위치를찾았고재수집/소비초기화는하지않았다. 단위시험3건:미래target비사용·시작후반환pre 차단·긴상수pre가새offset을만들지않음. 동일AP anchor/conditioning96 lane완전해제/소스byte불변을검증했다.

```powershell
python -B -m unittest tools.test_d1_preboundary_evidence -v
# 공유된새초기입력으로기록AP진단만계산,계수fit/기기0
python -B docs/results/preboundary_evidence_01/run_example.py --opt-in --output output/preboundary_C0.json
python -B docs/results/preboundary_evidence_01/plot_results.py --output output/preboundary_figures
```

[화면·그림·재현](results/preboundary_evidence_01/README.md) / [검증](results/preboundary_evidence_01/verification.json).AP계수·원자료·FAIL·소비계획·기본/RL/strict·experiment_ready=false를보존했다. A24 raw=mA/절대J미인증과S26계수비혼합을유지한다. 이번기기/ADB/추론/실측/설치/빌드·새실측계획/claim·전역계수fit0이다.

**확정된다음PC질문:** 저장된pre CPU활동이일시적으로높은때를구분하면,이후기준전력의예측오차를줄일수있는가. 기존4C0와같은12이력의trace가있으므로이를추정미사용세션에서검사하는것이먼저다. 미래활동을미리알았다고가정하지않고,AP초기화와에너지기준값의새근거를분리한다. 또하나의동일B2 실측을먼저할필요는없다.
