# 실제 에너지 오차 감소와 고정 AP 후보의 별도 비용 경로

**기존 자료만으로 에너지 오차를 낮춘 4계수 후보를 실제 추정·평가하고, 고정 AP 후보와 함께 호출하는 별도 API까지 구현했다.** 이전 토론의 제안 단계에서 끝내지 않았다. 단, 과거10세션 악화·무부하 배경변동·정책 차이 부호 문제 때문에 기본 시뮬레이터/RL/strict를 자동 교체하지 않는다.

## 구현·추정과 자료 역할

- 새 에너지식: `E(lo,hi)=P50·(hi−lo)+Σ p_state·실제 lane 점유시간`. 유휴 상수 보정 δ=0, 비음수 계수4개다. 원식·직전후보·원자료를 덮어쓰지 않았다.
- 원50초 pre-W, 같은 개발5초 구간·세션 균등 가중 최소제곱을 사용했다. 개발 `session_00..03`의4제외추정+최종1=정식fit5회. 수치 rank4/정규화 조건수1.00087은 수치 식별 근거이며 환경·배경의 인과 식별은 아니다.
- 최종 추가전력: 분류CPU0.807621 / 탐지CPU0.720310 / 분류GPU0.397905 / 분류GPU+탐지CPU1.099416W. 같은 모델·resident·프로토콜의 유효 계수이며 독립 부품의 순수 전력이 아니다.
- AP는 이미 동결한 `LOAD_SLOW`를 재사용했고 APfit0이다. 원AP전력proxy에 새 p4를 넣지 않았다. 기존 확인 개선을 이번 새 AP학습 성과로 표현하지 않는다.
- 개발 이외 과거29와 긴2는 학습에 사용하지 않았다. 다만 결과를 이미 본 뒤 후보를 정했으므로 **사후 평가**이며 새 blind 확인이 아니다. AP의 이번 개발 재생은 고정 최종후보를 개발 자료에서 계산한 in-sample 결과다. 에너지LOSO와 섞지 않는다. [역할 명시](results/energy_ap_zero_offset_01/run_v1/AP_evidence.json).

[추정 전 등록](results/energy_ap_zero_offset_01/registration.json) / [동결 receipt·hash](results/energy_ap_zero_offset_01/run_v1/fit_receipt.json) / [원후보](results/energy_ap_joint_followup_01/run_v1/candidate.json) / [새 후보](results/energy_ap_zero_offset_01/run_v1/candidate.json).

## 같은 시간창의 실제 결과

LOAD_A_LONG의 J/AP 공통 관측 구간은 `[37.417396683,2554.510266266]`초다. 에너지 관측2639.3775J, 원식2616.3173J, 새 후보2633.1907J다. **부호 있는 에너지 차이 −23.0602→−6.1868J, 절대오차73.2% 감소**다. 동일 구간 AP 원표본922개의MAE0.43731→0.17296°C, 최대절대오차1.899→1.234°C다. AP 마지막 표본2552.2474초 이후의 값을 만들지 않는다.

| LOAD 구간 | 원 에너지 차이 | 새 에너지 차이 | 원 AP MAE → 고정 후보 |
|---|---:|---:|---:|
| 원등록600초 `[35,635]` | −15.1508J | +2.0809J | 0.5437→0.1862°C |
| 실제 작업 존재 `[35,545.1858]` | −11.8073J | +5.4244J | 0.5291→0.1723°C |
| 덮인 회복 `[635,2554.5103]` | −7.6549J | −7.6549J | 0.4036→0.1686°C |
| J/AP 공통 관측 구간 | −23.0602J | −6.1868J | 0.4373→0.1730°C |

600초 새 에너지 상대차이는+0.277%, 긴 공통 관측 구간은−0.234%다. 서로 다른 시간창을 하나의 평균 정확도로 합치지 않는다. 회복 전체의끝0.578초는기존처럼미관측/null이다.

C0는 본작업과 상태노출이0이므로 새 전력4계수로 개선할 수 없다. 600초J차이−13.1476J, 긴 공통관측−36.0480J, AP MAE0.0908°C로원식과같다. 무부하의미래배경전력오차를해결했다고하지않는다.

## 모든 조건과 악화 보존

| 에너지 평가층위 / 창 | 세션 | 원 평균절대J | 새 평균절대J | 원보다 악화 |
|---|---:|---:|---:|---:|
| 개발 세션 제외 / 참고120초 | 4 | 12.6970 | 7.4570 | 1 |
| 개발 세션 제외 / 등록600초 | 4 | 40.7951 | 35.8584 | 1 |
| 이미 본 과거 / 참고120초 | 29 | 5.5222 | 5.1441 | 10 |
| 이미 본 긴2 / 등록600초 | 2 | 14.1492 | 7.6142 | 0 |

과거29의참고120초평균절대J는6.85% 감소했지만 전체 사례에 개선이 보장되지는 않는다. 과거개발3은4.1687→5.0200J로악화했고, 확인6은9.4242→9.1259, 지속8은4.6241→3.3799, 이력12는4.5084→4.3605J다. 각그룹의악화2/2/2/4를공개했다. AP의이전과거13악화도그대로남는다. [모든J창](results/energy_ap_zero_offset_01/run_v1/energy_errors.csv)·[그룹별](results/energy_ap_zero_offset_01/run_v1/archive_groups.csv)·[에너지악화](results/energy_ap_zero_offset_01/run_v1/retained_worsening.csv).

직전 **계수고정 δ삭제 진단**보다도 항상 좋지는 않다. 그진단의개발120초7.251/과거29의5.087J에비해이번재추정은7.457/5.144J다. 반면긴LOAD 공통창은진단−11.934→이번−6.187J다. 이미본결과의최저창/계수를골라최종모형을바꾸지않았고한family의사전고정평가로끝냈다.

## 상쇄와 정책 차이: 작은 전체 오차만으로 완료하지 않음

LOAD등록+회복prefix의5초bins 양/음J잔차합은원식+112.486/−135.291,새후보+118.212/−123.786J다. 합산은−22.806→−5.574J로작아지지만 **국소 절대잔차합은247.777→241.997J로소폭만 줄었다**. 양의잔차는오히려늘었다. 5초/10초결과는같은센서기록의집계이며독립반복표본이아니다. 혼합bin을독립병행전력으로해석하지않는다. 부하창완전포함bins510초와실제작업창510.1858초도구분한다. [상쇄·포함시간](results/energy_ap_zero_offset_01/run_v1/cancellation.csv).

기존CPU 긴급우선/PAR4짝의동일120초조건부에너지차이오차MAE는6.322→6.219J, 부호오판2/4로여전히정책순위를구분하지못한다. 새후보의작은개선을정책우월성으로전용하지않는다. [짝의방향·오차](results/energy_ap_zero_offset_01/run_v1/paired_errors.csv).

## 실제 사용 경로와 종단간 경계

[별도 비용API](../tools/d1_energy_ap_zero_offset.py)의 `forecast(case, context, folder, opt_in=True)`를구현했다. 기존AP scope의기기/모델/입력/CPU1·4resident/초기AP·준비이력·APK·관측variant·등록macro일정을검사하고,원50초전력창·시계종류·pre자료가35초이전에준비됐는지를추가검사한다. 등록맥락밖/RL요청/미지원상태/오래되거나미확인초기정보는차단한다. 미래AP·전류값은예측식에넣지않는다.

기존6개기록의원journal hash를확인하고,전력[-20,30]적분의마지막bracket `sensor_read_end_ns`가시작이전에반환됐음을확인했다. Android동일monotonic원점에대해기록한것이며host wallclock을직접비교하지않았다. 이값은하드웨어센서내부갱신시각보장이아니다. [초기정보가용증거](results/energy_ap_zero_offset_01/preload_availability.json). context는과거검증기록의assertion이며현재기기gate가아니다.

API의두출력은 **실제일정조건부 A**다. 신규도착부터일정·응답을생성한B 검증이아니다. 저장된forecast일정이있는과거17기록에는동일비용식을적용해B 비용투영만따로평가했다. 참고120초평균절대J6.1181→5.6808J,6악화다. 나머지12의예정일정은미기록으로남겼고실제미래일정으로대체하지않았다. 일정/응답엔진·RL환경을변경하지않았다. [B 별도 요약](results/energy_ap_zero_offset_01/run_v1/stored_B_summary.json).

## PC 오류 수정·검증과 재현

- 사전잔차표의빈순수5초구간을나누던오류는혼합bin·점유가중·미관측null로수정했다. 추정전오류이며후보fit을다시시작하지않았다. [보존](results/energy_ap_zero_offset_01/preflight_reporting_failure.json).
- 평가가정상완료되고receipt가저장된뒤CLI에서NumPy int64 요약을JSON으로직렬화하지못했다. 출력경계만수정했다. 최초등록·추정소스·test·완료결과를보존하고소스보완hash를별도기록했다. fit/evaluate/forecast등수치함수AST가불변임을확인했으며정식fit 재실행0이다. [출력오류](results/energy_ap_zero_offset_01/run_v1/CLI_OUTPUT_FAILURE.json)·[소스보완](results/energy_ap_zero_offset_01/source_amendment.json).
- 수치·입력·역할·rank·결측·구간가산성·미래target비사용·hash/중복차단7검증과출력형식1검증통과. 실제기존AP callback이아닌 **PC 비용API 진입**을시험했다. 6기록의guarded API 예제도계산했다. 기존부하·기본/RL/strict/experiment_ready=false는불변이다.

```powershell
# 개선 후보를 바로 호출하는 저장 LOAD 예제, fit/기기 실행 없음
python -B docs/results/energy_ap_zero_offset_01/run_example.py --opt-in --window matched --output output/zero_offset_LOAD_example.json
python -B -m unittest tools.test_d1_energy_ap_zero_offset -v
# 아래는 새 폴더에서만 수행하는 별도 재현; 기존 run_v1을 재실행하지 않는다.
python -B -m tools.d1_energy_ap_zero_offset --action fit --output output/zero_offset_reproduce
python -B -m tools.d1_energy_ap_zero_offset --action evaluate --output output/zero_offset_reproduce
python -B docs/results/energy_ap_zero_offset_01/plot_results.py --output output/zero_offset_figures
```

[대시보드·모든CSV](results/energy_ap_zero_offset_01/index.html) / [검증·현재소스hash](results/energy_ap_zero_offset_01/verification.json).새후보SHA `bf12fd70b5e84d984a01826c149d42a9736371a0efbf2290aab5b039628782bd`다. 원식·AP후보·기존자료byte는불변이다. A24 raw=mA 해석/절대J미인증/SOC·BAT·사용시간미검증/S26계수비혼합을유지한다.

**현재완료:** 기존자료의제한적에너지오차감소＋기존AP개선후보를실제호출가능한별도경로에연결.**미완료:** 무부하/예측불가능한배경변동,과거악화,정책차이판별,새독립에너지확인, 일반도착/열→처리시간.추가실측·새계획·claim·기기/ADB/설치/빌드·정책배치/RL학습은모두0이다. 새후보를만들거나이미본자료에서더좋아질때까지재추정하지않았다.
