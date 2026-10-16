# S26 통합 시뮬레이터 완성 계약 — S26-INTEGRATED-SIM-03

사용자 “이걸로 s26 시뮤레이터 완성해”에 따라 현재 원자료로 **120초 CPU/GPU/NPU 서비스·에너지·AP/SKIN 비용 엔진과 CLI·검증·재현 bundle**을 완성한다. 구현완료와 실측정확성/품질/채택판정을 구분한다. 기존 미식별·GPU열0/8·지속감속미확인 판정은 보존한다. 모델에 A24 계수를 쓰지 않는다.

## 계산 전 고정

- HEAD12d64923 detached+기존WIP. 옛 S266소스/3weights/S0/비용profile·동시A24 소스/예산/프로세스는 변경하지 않는다. 새로운4소스와검사를별도파일로작성하며 초기 등록에 SHA를 포함한다.
- SS12 원자료/최종 AVAILABLE 가공값은 `outputs/S26-M5-INTAKE-02/prepared_observed_sessions.json`; 원본ae1d956/판정5940061/GPUf7ac05a. 적합·선정에는 **개발00~05만** 사용한다. 개발 내부 거울블록 `[0,1,2]`/`[3,4,5]` 두 fold로 hyperparameter를선정하고개발6전체로동결한다. 확인06~11 및 R3/R4C/R4S는동결뒤읽는다. 이미공개된확인자료이므로 새맹검이라고부르지 않는다.
- 서비스는기존R3 S0 intact5phase/키샘플/공개평균과split을유지한다. dispatch→실행→output→persist→release→AVAILABLE, 긴급output/일반persist 응답분리, 비선점·C_CPU/GPU/NPU·D_CPU·CG_DC/CN_DC≤2다. 미지원조합/중복/3건/NPU탐지거부. 기본정책/품질gate완료로자동승격0이다.

## 새 비용 식

`u=(CPU,GPU,NPU)`는현재줄점유, `h`는전체활동기억이다. 어느줄이라도바쁘면h=1, 모두유휴일때 `dh/dt=-h/τ`(τ0은즉시0). **단일요청시간을늘리거나전체큐를미래시뮬레이션하지않는다.** 이 h는측정되지않은클럭을뜻하지않으며짧은빈틈에남는증분전력의대리상태다.

`φ=(u_CPU,u_GPU,u_NPU,h)`, `P=Ppre+a·φ`, `J=∫Pdt`.
AP/SKIN 각각 `dy_f/dt=β(φ-y_f)`, `dy_s/dt=β/10(φ-y_s)`,
`T=R+(T0-R)e^(-βt)+g·(m y_f+(1-m)y_s)`.
단위는s/W/J/℃. Ppre는사전30초실측평균, R은사전마지막10초평균, T0는공통시작전실측. h0=0, fast/slow필터0은초기화가정이며초기잔류열은T0−R항으로만표현한다. CPU작업공유/활동가산성/느린시정수10배는가정이다. θ6상태의원공식계수와다른새4성분정의이며등록5W상한판정을바꾸지 않는다.

계수a∈[0,10]W/g∈[0,60]℃는새대리기저의수치보호범위(실측상한아님), λ `[0,.1,1]`의비음수boxridge. 목적은세션균등 `mean(residual²)+λ mean((coef/bound)²)`다. 전력과열을별도로맞추며열역학적결합·온도→서비스감속은미지원이다.

- 전력 후보: τ `[0,.1,.5,2,5]`×λ3 =15. 각2fold적합/평가와개발6적합＝45fit. 개발CV5초창RMSE_W를우선, J절대상대오차·후보순번으로동률처리한다.
- 열 후보: 선정τ를고정, β `[.01,.03,.06,.12,.25]`×m `[1,.6]`×λ3 =30, AP/SKIN 각각2fold+전체＝90fit씩. 개발CV세션평균 `MAE+.25×|peak_error|`·순번으로선정한다. 실제센서시각에서해석적필터를평가한다.
- 계수동결뒤 두개발블록을paired bootstrap40회(seed63012), 고정설정전력/AP/SKIN각1fit＝120fit. 총 **345fit**;두블록재표집은독립40표본/모집단신뢰구간이아니며실제로가능한세블록조합의민감도다. hyperparameter재선정/확인뒤튜닝0.
- cap400fit/256서비스환경/학습0/활성1200초·저장120초. 예정224환경＝새24조건×8군192＋사전정한4조건×8군의구서비스동일성대조32. 순수해석적합성검사는서비스환경0이며모든실제simulate시작은소비원장에계수한다. 실패도소비하고무한확대하지 않는다.

## 통합 실행과 비교

새IntegratedDevice는원서비스의현재dispatch/실제AVAILABLE 사건에만cost.advance/dispatch/available을연결한다. 자원반환과같은시각의도착/dispatch는release먼저, 진행중요청이동0. PPO에는원192state/64행동ABI만전달하며추가비용state/미래실현/전체큐rollout을주입하지 않는다. 기존서비스PPO3개는가중치고정argmax로재사용하고 **새비용을학습한PPO로표시하지 않는다**.

24조건은finite low/steady/burst/overload4와실제80초요청이계속들어오는sustained_relaxed(C400ms/D800ms),sustained_loaded(C100ms/D300ms)2 ×원/가변기한2×seed2다. finite64요청과35~115초지속요청을분리하며“120초관측=120초부하”라고쓰지 않는다. 모든기한은원1.5/6상한이하다. FIFO_READY/EFT/EDD/ATC/FIFO_HOL/PPO501/503/509를같은도착·잠재서비스키·초기조건에서비교한다. 주기/부하/기한은공학적입력이고실측도착분포라고주장하지 않는다.

서비스판정은120초에서종료한다. 비용은미완료여부와무관하게실제창내점유를적분해prefix값도보존한다. 전량완료시에만기존energy_j/peak_ap_c필드를적격표시하며불완료로낮아진비용을절감으로판정하지 않는다. 180초열냉각은120초때모든줄이AVAILABLE인경우에만제공하고그외null이다. 최대180초는120초서비스＋60초관측이며3분지속실행지원이아니다.

전체J120, AP/SKIN peak·mean0~120와35~120/35~180,미완료·원/요구납기실패·P95·완료율을함께기록한다. 새모형의간이오차screen은SS확인J≤10%/AP MAE≤1℃≥4/6·정책마다≥1/2로보고하지만담당자공식판정이나새독립확인PASS로승격하지 않는다. R3/R4C/R4S전이오차·baseline이상·상한활성/노출/계수불확실성도전부공개한다.

## 산출과 종료

`tools/d1_s26_integrated_cost.py`(새활동기억과해석적적분), `d1_s26_integrated.py`(서비스연결·CLI), `d1_s26_integrated_build.py`(유한적합/동결/회고평가), `d1_s26_integrated_verify.py`(224환경·보존/누수/결과감사), `test_d1_s26_integrated.py`와`outputs/S26-INTEGRATED-SIM-03/` model.json/README/CSV/trace/manifest/repro입력이다.

코드계약·cold/directprefix·증분/일괄수치일치·구서비스원장동일·동결소스/weights/입력SHA·실제모형오차를검사한다. 구현을완료한뒤모형screen이FAIL이어도결과를보존하고추가fit/학습으로구제하지 않는다. `implementation_complete=true`와 `strict_eligible=false/experiment_ready=false`를구분한다. 기기/APK/새PPO학습은실행하지 않는다.
