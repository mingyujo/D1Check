# 세 전문 검토 역할의 토론 — SIM-MODEL-V3-EXPERT-01

2026-10-10. 실제 인간 자문을 받은 기록이 아니라 서로 독립적으로 조사한 열동역학/모바일에너지/검증·서비스 AI 역할3개의 2라운드 검토다. root가 구현·최종 판정을 담당하며 원 raw/source/model은 보존한다.

## 1라운드 진단

열 역할은 v2 fastβ/slowτ1920/preτ30 고정 상태에서 회복개발4만의 계수 변경이 혼합 요청으로 옮겨진 점을 지적했다. 원AP의 fast4/slow0을 같은 기저로 옮기면 개발17에서 최대차7.82e−14°C로 원예측과 동일했다. 분류CPU 계수는0.008412→0.196184로23.3배, GPU0.054207→0.106216이다. 회복4는 joint≈120초/단독≈15~25초로 거의 같은분포여서 source4로 과대가중하면 전이 편향이 남는다.

에너지 역할은 원→v2의 상태추가전력 CC0.584→0.693/DC0.713→0.758/CG0.473→0.329/CG_DC0.888→1.102W를 확인했다. pre50초 baseline을120/533초 동안 고정한 가정과 회복4/혼합의 duty 분포 차이를 지적했다. 개발17의 pre와 미래순수idle 차이는 절대평균0.041809W이고 pre late−early와 미래shift 상관r=.372114에 그쳐 단순추세 보정의 근거는 약했다. 미래idle은 진단 표적이며 예측입력으로 쓰지 않았다.

검증 역할은 새CPU A→B 에너지추가오차≈0.135J, PAR≈0.128J로 이미 실제일정A에서도 악화한다는 점을 확인해 비용계수를 우선 원인으로 좁혔다. B 원모형/v2 기준은 AP MAE0.308299/0.339885°C, 절대J8.195309/10.748949J, policy×priority4층 P95절대오차25.106132/35.864985ms였다. 독립 실측은2세션이다.

## 2라운드 반박과 좁힌 선택

- 열 초기화의 심각한 rank 문제라는 가설은 약해졌다. 개발pre실제60~65초/condition5.76~6.31이다. ±0.05°C 독립 교란 가정의 미래최악0.207~0.231°C는 민감도이며 CI가 아니다. 계수 전이와 초기추정 민감도를 구분해 기존기저 ridge 우선·초기H0규제 보조만 남겼다.
- 미래idle drift가 있다고 pre기울기로 예측할 수 있는 것은 아니다. history180PAR은 pretrend−0.03095W이나 미래idle＋0.12913W였고, 기존baseline 후보도 확인에서 악화했다. 전source의 공통baseline으로 수축하면 실제 배경차를 지울 수 있어 기각했다. pre10..30의 작은 relaxation만 별도 gain 후보로 제한했다.
- 원계수/서비스가 일부개발 source를 이미 학습했으므로 원계수를 shrink prior로 넣은 CV를 전체모형 독립OOF라고 할 수 없다. 고정 선행모형 조건부 검증이라고 표시하고 새 확인4로 최종 평가한다. 기존확인22＋v2확인4로 선택하지 않는다.
- 좁은 invoke와 전체 execute를 비교하는 서비스 보정은 금지한다. 새회복 invocation은 TFLite invoke, arrival host bracket은전처리/후처리까지 포함한다. 서비스쪽 v2의 dispatch순간 GPU부재→CPU단독 context는 이후겹침을 놓쳤고 replay는cell별 서로다른세션을 섞었다. 이번 비용개선 실험은 원서비스를 고정해 원인분리를 우선하며 서비스확장은 별도 검증 없이는 채택하지 않는다.
- 조건ID로 좋은모형만 고르는 gate는 누수는 없어도 사후선별 일반화 문제를 남긴다. 미래actual duty/last_lane gate는 금지한다. 새로운 RC 차수·시간상수/다수특징을 동시에 늘리지 않는다.

## 실행 합의

[고정 계획](SIMULATION_MODEL_V3_PLAN_20261010.md)의 개발17/5source 균등, AP/energy각18개 유한후보, 조건부nested CV, headfit≤1000, 동결뒤CPU/PAR/PAR/CPU 새4만 진행한다. °C/J를 임의 합산하지 않고 혼합B를 주목표로 판독한다. 사용자는 A24 연결 유지 가능이라고 응답했다. 새확인 뒤 후행 보정/대체실측을 하지 않는다.

참고 논문은 [HotSpot](https://www.cs.virginia.edu/~skadron/Papers/hotspot_isca03.pdf), [DATE2018 Park·Lee·Cha](https://www.date-conference.com/proceedings-archive/2018/pdf/0771.pdf), [PowerTutor](https://web.eecs.umich.edu/~zmao/Papers/powertutor_cases2010.pdf), [Cawley·Talbot](https://jmlr.org/papers/v11/cawley10a.html)다. 신호/부하 상태·초기화/검증 분리의 근거만 참고하며 논문의 기기별 계수/정확도를 A24에 전용하지 않는다. 센서 μA 공식 설명과 A24의 프로젝트 mA 해석/절대교정 미인증도 구분한다.
