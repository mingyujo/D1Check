# 시작 전 전력 입력으로 AP 초기화 보완한 결과

**전력 변화를 기존 준비 잔열 상태에 넣는 후보를 구현·평가했지만 가열 방향 오류를 해결하지 못했다.** 이미 본 확인6의35..120초 AP MAE0.21160→0.21125°C는 극소 감소이고,35..180초 전체 관측표본은0.16630→0.16656°C로 악화했다. 계수의 이력별 차이와 입력 민감도가 커서 미채택한다. 실제 수정 대상과 부족한 근거를 기록으로 특정했으며 새 실측·원모형/기본/RL 교체는 없다.

## 후보 하나와 사전 고정

[이전 진단](AP_CONDITIONED_POWER_RESULTS_20261010.md)은 회복30 C0의AP 초기경로가 가열을 예측해 J오차가 증폭되는 사례를 찾았다. 기존 초기화는 AP/β/τ만 받고 pre 전력 변화를 사용하지 않았다. [실행 전 계약](results/ap_power_initialization_01/analysis_contract.json)에 기존 준비-memory H 상태의 입력만 추가하는 후보 하나를 고정했다.

```text
T' = −β(T − R) + H
H' = [κ × (P_pre − P_reference) − H] / τ
```

- β=0.0459325203/s와τ30초 고정. 새 상태·시정수·학습기·그리드를 만들지 않고 전역 κ 하나만 추정한다. R은 유효기준 추정량이며 주변온도가 아니다. H도 측정된 내부온도가 아니다.
- 이미 등록된 회복 AP의 첫 표본→마지막 표본 전체를 사용했다. 전력은 해당 시각 이전에 기록된 값을 다음 표본까지 유지하는 ZOH 입력이며 event/age≤2.5초,AP gap≤10초/조회 종료<35초를 검사한다. P_reference는 같은 구간 ZOH 시간평균이다. 부호 있는 평균 대비 편차이며 기기 소비전력을 음수로 만든 것이 아니다. 원자료와 에너지 적분의 기존 선형규칙은 바꾸지 않았다.
- 개발 세션마다 AP 첫값을 고정하고 R/Hfirst의2 nuisance 열을 제거한 뒤, pre AP와 전력응답만으로 κ≥0을 추정했다. 동일 세션 가중·회복30/180 block 제외2＋최종개발6 전체1, **전역fit3회**다. 개발 nuisance projection12묶음과 평가 local state 추정12회는 전역 계수와 구분한다. 확인은pre만 초기조건으로 사용하고 부하후AP는 맞추지 않는다.
- 관측된 마지막AP와 시각을 이전 초기화와 똑같이 유지한다. κ로 R/H를 보완하며 **anchor 이후 외부 전력 편차는0이라고 가정**한다. 미래 실측전력·AP를 넣지 않는다. 대상 부하의fast4/slow1·τ1920·원전력proxy는 기존 LOAD_SLOW 그대로다. 이 가정은 미래 환경이 실제로 일정하다는 인증이 아니다.
- 실제lane 일정 조건부 AP 재생이다. 예정 도착부터 일정/응답을 만드는 종단간 예측과 구분하며 live 입력 전달이나 실기기 동작을 새로 구현하지 않았다. κ0/고정초기상태로 실제 두 경로를 확인해 기존곡선 차이1.78e−14°C 이내였다.

## 계수 식별 가능성

| 추정 자료 | 비음수 κ(°C/J) | 비제약 추정값 |
|---|---:|---:|
| 회복30 개발 제외·회복180 개발3 | 0.052512 | 0.052512 |
| 회복180 개발 제외·회복30 개발3 | **0** | −0.064130 |
| 개발6 최종 | 0.039426 | 0.039426 |

전력응답 중 R/H로 흡수되지 않는 잔차 정보비율은0.6017,개발3열 scaled condition은2.24–8.68로 수치적으로 추정 가능했다. 하지만 부하 이력별 부호가 다르고, 관측AP가 ±0.05°C씩 독립적으로 바뀐다고 가정하면 최종 비음수 gain 범위는0..0.17110이다. 이것은 **결정론적 입력 민감도**이며 신뢰구간·절대센서정확도·실제반복변동성 인증이 아니다. 최종pre 잔차 RMS0.05747°C,계수와 그 의미를 분리한다. 모델의 안정성을 수치rank만으로 통과시키지 않았다.

[모든3fit와민감도](results/ap_power_initialization_01/run_v1/candidate_final.json) / [개발역할/입력/source 동결](results/ap_power_initialization_01/run_v1/registration.json).

## 전량 AP 평가: 극소 변화·방향 오류 유지

비교 기준은 **고정 LOAD_SLOW의 등록유휴 전체pre 초기화**이며 원래 동결AP 수식과의 새 비교가 아니다. 두 쪽 모두 같은query/마지막초기AP/시각/부하계수다. 과거 AP 결과를 이미 열람한 사후 평가로 분류한다. 표본 수를 독립세션으로 늘리지 않았다.

| 자료·AP 관측창 | 기존초기화 평균MAE | 전력입력 평균MAE | 판독 |
|---|---:|---:|---|
| 개발6·35..120초 | 0.17508°C | 0.17698°C | 악화 |
| 개발6·35..180초 | 0.13560°C | 0.13466°C | 극소 감소 |
| 확인6·35..120초 | 0.21160°C | 0.21125°C | 극소 감소 |
| 확인6·35..180초 | 0.16630°C | **0.16656°C** | 악화 |
| 확인6·실제lane해제후 관측표본 | 0.15317°C | 0.15317°C | 거의 동일 |

확인 전체창 평균최대절대오차0.62291→0.61967°C는 감소했지만,평균 최고온도 절대차이는0.08180→0.08505°C로 악화했다. 각창의 실제 첫/마지막AP표본 시각을 기록했으며 미관측 endpoint를 채워 완주값으로 만들지 않았다. [전12/부분·최대·최고·방향](results/ap_power_initialization_01/run_v1/AP_errors.csv) / [모든짝/악화](results/ap_power_initialization_01/readout_v1/AP_paired_errors.csv).

회복30 C0의35..120초 관측 변화는−0.400°C인데,기존+0.15713→후보**+0.14773°C**로 가열예측이 남았다. 같은창 MAE0.24369→0.23663°C 감소를 냉각방향 해결로 표현하지 않는다. 전체창도MAE0.28068→0.27344°C지만 뒤쪽에 실제 AP29.6°C 상승 구간이 있어 단조냉각/기기무활동을 전제하지 않는다. 외부 원인은 미확정이다.

## 계수를 키우면 방향이 해결되는가

[사후 산술 계약](results/ap_power_initialization_01/readout_contract.json)으로4C0/두창 모두 고정모형의 unit-power state derivative를 계산했다. 추가전역fit0/localAPfit0,전력basis projection4다. **필요값은 실제gain으로 쓰지 않았고 확인AP를 맞춰 선택하지 않았다.**

회복30 C0의35..120초 예측변화는 κ에 대해 `0.157130 − 0.238525×κ`이다. 가열→냉각 경계 κ≈0.65876은 최종0.03943의약16.7배이고,앞의가정한반올림범위상한0.17110보다높다. 이 값의 개발 profiled pre 잔차 RMS를 기존 이차식으로 계산하면0.05747→0.18374°C다. 방향을 억지로 바꾸면 개발 설명도 나빠진다. 이것은 새로운 계수의 채택/재학습이나 물리적 불가능성 증명이 아니라 **이 한가지 고정구조의 진단**이다.

[4C0 방향경계](results/ap_power_initialization_01/readout_v1/C0_direction_gain.csv) / [고정계수 이차잔차 산술](results/ap_power_initialization_01/readout_v1/direction_training_loss.csv). 센서반올림 가정과 정확도합격선을 혼동하지 않았다.

## 에너지 연결은 별도 진단이다

이전 작업에서 **미채택한** pre AP/CPU→전력 관계의 계수는 다시 맞추지 않았다. AP초기상태만 바꿔 영향을 계산했다. 그관계와원4전력계수의120초 확인평균절대J는4.637→4.531,δ=0 4전력계수와의연결은4.326→4.307이다. 원전력모형의동일6세션3.913J보다낮지않다. 이 작은 변화로 에너지모형 개선/정책 차이 판별/원관계 채택을 주장하지 않는다. [모든J창·결측](results/ap_power_initialization_01/run_v1/energy_link_errors.csv) / [계수head별요약](results/ap_power_initialization_01/readout_v1/energy_link_summary.csv).

## 다음에 쓸 기존 자료의 실제 위치도 확인

같은 문제세션 원본에서96 conditioning 요청과그동안의AP48표본을 확인했다. 등록 구간120.066초 안의query bracket만세었고 AP29.0–31.1°C의2.1°C 변화를 기록했다. 파일3개는기존source hash와일치했다. **새세션/새표본/실측을추가한것이아니다.** 현재 이번후보는conditioning 후회복pre만사용했고,대상actual schedule에는앞선96 작업을넣지않는다. 기존 LOAD_SLOW도느린상태를target앞에서0으로시작하며그0이측정된빈상태라고하지않는flag가있다.

앞선부하의열영향은현재R/H추정에간접흡수되지만,conditioning입력과slow초기상태를명시적으로연결한것은아니다. 이것은 **코드에서확인한가정과아직사용하지않은기존정보**이며,과거오류의실제물리원인이나연결하면해결된다는증명은아니다. [원본field/표본/시간축/3hash](results/ap_power_initialization_01/conditioning_availability.json).

## 구현·검증·판정

새7경계시험통과: 합성 gain복원/firstAP반올림민감도,κ0 기존초기화일치,과거전력event/age,개발role·미식별/미래driver 차단,실제상태/anchor/horizon·미래관측독립,상수입력/equal-rate한계,소비분석 차단. 실제진입control2＋평가24 AP재생과기존36/96샘플초기정보를사용했으며동결filehash·원자료·FAIL/소비계획을보존했다. [버전·명령·정확count](results/ap_power_initialization_01/verification.json).

결론은 **실질적인 추가개선 근거 미확보·후보 미채택**이다. 추가적인전력정보자체가없었던문제와정보를넣어도이구조/계수가방향을못고친문제를구분했다. κ의미는관측상보완계수이지열용량인증이아니다. 실제일정조건부/사후평가·live 전달미구현,기본/RL/strict/experiment_ready=false·A24 raw=mA/절대J미인증·S26계수비혼합을유지한다. 이번기기/ADB/설치/추론/실측/빌드/새계획/claim/환경배치0이다.

다음 PC 행동 하나는 **기존conditioning96 실제일정·AP를고정 LOAD_SLOW의초기상태추정에연결해,느린상태0/유효기준흡수가오류에기여하는지검증하는것**이다. 새물리계수나좋은gain탐색부터하지않고,이미있는이전부하이력을사용하는입력/초기상태문제다. 이번에새후보/재fit/실측을자동추가하지않았다.같은B2재측정이나포괄적감사를다음행동으로두지않는다.

```powershell
python -B -m unittest tools.test_d1_ap_power_initialization -v
python -B docs/results/ap_power_initialization_01/run_example.py --opt-in --output output/ap_power_initialization_example.json
python -B docs/results/ap_power_initialization_01/plot_results.py --output output/ap_power_initialization_figures
```

[전량화면·그림](results/ap_power_initialization_01/index.html) / [공유 입력·추정/재현 명령](results/ap_power_initialization_01/README.md). 소비된run_v1은 재실행하지 않는다.
