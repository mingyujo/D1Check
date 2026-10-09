# 원 논문과 D1Check 설계의 대응

2026-10-09 공식출판사/학회/저자arXiv를확인했다. 아래는원알고리즘전체재현이아니라확인된설계개념의적용이다. 논문의성능숫자/설비/처리시간/지연값을폰의계수로사용하지않는다.

| 원 자료·버전 | 확인한 개념 | 가져오는 것 | 가져오지 않는 것/한계 |
|---|---|---|---|
| [Lassoued 등, Policy-Based DRL Hyperheuristics for JSSP](https://arxiv.org/html/2601.11189v1), arXiv2601.11189v1/2026-01-16, §4.1–4.3 | 실행가능후보와학습선택분리·작은행동집합·선택유지기간/credit assignment | 리스트기반후보/재정렬·중복효과제거·한원자선택/유한지연 | Petri-net 공장전체·x개작업동안규칙고정·makespan목적·논문우위수치. arXiv본문의JMS표기를보았지만정식권호/DOI는독립확인하지않아arXiv버전으로인용 |
| [Zhang 등, Learning to Dispatch for JSSP](https://papers.nips.cc/paper/2020/hash/11958dfee29b6709f48a9ba0387a2431-Abstract.html), NeurIPS2020 | 우선순위dispatch를학습하는정책·작업별표현공유 | 후보특징에공유score를주어slot순서와규칙이름에과적합하지않는구조 | GNN·다공정DAG·큰공장일반화주장. 현재2과업에는MLP로축소하는우리판단 |
| [Huang·Ontañón, Invalid Action Masking](https://arxiv.org/abs/2006.14171v3), v3/2022-05-31·FLAIRS2022 | 상태별실행불가행동제거와policy-gradient정당화 | 현재lane/지원/요청존재·credit가능마스크와rollout마스크보존 | AP예측필터/미래기한보장으로승격하지않음 |
| [Schulman 등, PPO](https://arxiv.org/abs/1707.06347v2), v2/2017-08-28 | clipped policy update와actor-critic | 기존native PPO최적화구조 유지·공유후보encoder | 논문hyperparameter가폰의최적값이라는주장·SB3중복구현 |
| [Achiam 등, CPO](https://proceedings.mlr.press/v70/achiam17a.html), ICML2017/PMLR70 | 목표reward와제약cost를분리하는CMDP | AP주보상/J·서비스별critic·signed제약평가 | CPO최적화기/near-constraint theorem을우리LagrangianPPO의보장으로전용하지않음 |
| [Ng·Harada·Russell, Policy Invariance / Reward Shaping](https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf), ICML1999 | 보상변환은목적을바꿀수있어합/종단조건확인필요 | 과거maxAP의증분이최종AP차이로정확히합쳐지는회계검사 | 임의밀집proxyreward/학습성능향상보장. 이번식은실제목적분해이며논문전체PBRS재현이아님 |
| [Henderson 등, Deep RL that Matters](https://arxiv.org/abs/1709.06560v3), v3/2019-01-30·AAAI2018 | 구현·평가변동과재현성에대한주의 | 학습3seed·seed전체보고·동일입력/예산/시간·원시KPI | 최고seed선별·3실현문맥을3독립도착반복으로간주·좁은물리CI |

Sutton/Precup/Singh의1999 [temporal abstraction](https://www.sciencedirect.com/science/article/pii/S0004370299000521)는출판사/저자페이지본문접근이차단됐고최근위첫논문의§4.3.4참조까지확인했다. 시간확장행동의연결은보조배경으로만남기며미열람본문의세부식/수치를전용하지않는다.2025 FJSP/MDPI일부본문도403/접근오류로세부결정규칙/설정은이번추천근거에서제외했다. 자료부재와접근제한을구분하며우회하지않았다.

선택한작은MLP·FIFO head축약·0.125/0.25초·56/28특징·signedλ·예산은논문원값이아닌D1Check제안이다. 관련논문존재는현재폰정책의성능입증이나전역최적성의근거가아니다.
