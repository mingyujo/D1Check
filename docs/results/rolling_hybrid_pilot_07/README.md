# 새 온도 보정 모형의 공동 롤링 비교

**파일럿 완료. 기존 공동 롤링이 새 첫 행동 직접선정보다 안정적이었지만, 두 후보 모두 Band·Triton 대비 전조건 채택 기준은 통과하지 못했다.**

[오프라인 화면](index.html) · [설계·판독 보고서](../../ROLLING_HYBRID_PILOT_20261011.md) · [96행](comparison.csv) · [조건별 차이](paired_differences.csv) · [판단·대기·점유](control_cost.csv) · [전체 판정](summary.json) · [실행 전 계약](execution_contract.json) · [동결 모형](model.json).

| 항목 | Band 대응 | Triton 대응 | 기존 공동 롤링 | 첫 행동 직접선정 |
|---|---:|---:|---:|---:|
| 완료/예정 |1584/1584|1584/1584|1584/1584|1584/1584|
| 긴급 기한실패 |0|0|0|0|
| 일반 기한실패 |21|21|21|30|
| 긴급P95 조건평균 (ms) |411.752|436.095|411.751|411.751|
| 일반응답 조건평균 (ms) |2162.746|2151.933|2376.296|2518.053|
| J120 조건평균 |152.274604|152.740610|152.024998|152.032801|
| 최고AP 조건평균 (°C) |30.452170|30.472198|30.442380|30.438887|

평균 비용 감소만으로 이겼다고 판단하지 않는다. 새 직접선정은 일반 기한실패가9건 늘었다. 원공동롤링은 기한실패 유지/J·AP 평균감소의 발전 후보지만 일부조건AP나Triton 대비P95/J가 악화했다. 모든24조건·양쪽기준 비악화와 주부하절대기한을 요구한 원판정은 양쪽false다. Band 전체프로그램이나 Triton서버를 실행한 비교가 아니라 기존 공개판단의 whole-request 대응이다.

정책당 긴급684/일반900건을 분모로 유지한다. 긴급 기한실패율0%, 일반 기한내완료율은 기준·원롤링97.6667%에서 새선택96.6667%로1%p 낮아졌다. 전량완료와 기한내완료는 별개다.

## 새 모형을 적용한 부분

최종 v3 thermal-only hybrid `6dd806bc…`의 같은 열head를 온라인선별·첫행동 보호·최종온도에 모두 적용했다. 결과만 새AP로 후처리한 비교가 아니다. α0.5 초기화·느린부하항을 전달식의 정확한 streaming 형태로 연결했고, 전달API로 만든 모든지원상태 fixture와 수치동등성을 확인했다. 개인경로 한개만 상대경로로 바꾼공유JSON은 별도exportSHA로 식별한다. 전력/처리시간은 원계수 exact, 새fit0이다.

이번2도착seed×4부하×3민감도문맥＝24조건이다. mean/short/long은 독립반복/신뢰구간이 아니다. 초기온도입력은같은실측preload이며 미래도착/실현잔여비용/실제내부온도를정책에제공하지않는다. 새hybrid는AP평균오차가줄었으나CPU최대/피크오차악화·정책각1회 검증한계가있다. 현재부하전부의엄격지원/실기기정책개선/표면온도감소를주장하지않는다. 냉각→속도회복·절대전력교정·폰판단J·안전한도초과는미지원이다.

## 차이가 생긴 곳

새선택기의 비Band첫행동402개 중393개는짧은냉각대기였다. 이번에는Band와완전히같은결과가아니다. 고정부하condition6의탐지 `/22`는Band5978.159ms→새6228.159ms로250ms지연해6초기한을넘었다. 현재큐의예측기한보호가나중도착과전체서비스를보장하지않는한계가드러났다. 평균일반지연도증가했으며미완료를누락해에너지이득을만든결과는아니다.

## 규모·검증·재현

42순수검사＋nativegate4 PASS, 전량96원장/지원/lane반환/응답경계/동일입력SHA PASS. gate8＋배치6336＝6344요청완료, native100/112·실패0, 새학습/적합/기기0이다. 기존미소비상한112의모형이관이며별도추가112가아니다. 누적환경9849/학습1449, 구모형prepared미실행·원결과/RL/다른모형작업/사용자변경보존. 기본/strict/experiment_ready=false불변이다.

```powershell
python -B -X utf8 -m tools.d1_rolling_hybrid_shared_check
python -B -X utf8 -m tools.d1_rolling_hybrid_pilot check
python -B -X utf8 -m unittest tools.test_d1_rolling_hybrid_model tools.test_d1_rolling_hybrid_pilot tools.test_d1_rolling_execution_prefix tools.test_d1_rolling_execution_pilot tools.test_d1_rolling_prefix_selection -v
python -B -X utf8 -m tools.d1_rolling_hybrid_report
```

`check`는 공유 source/입력검사도 가능하며local소비계보없이native재실행예산을만들지않는다. 원완료원자료는 `output/rolling_hybrid_pilot_20261011_v1/items/`다. 원자료없는clean clone은 공유CSV/그림으로결과를검토하고 `check`/순수검사를수행할수있다. 원자료는자동재실행하거나대용량으로공유하지않는다.

공유용 `d1_rolling_hybrid_shared_check`는 실행 시 Windows CRLF와 Git LF 차이만 기록된 내용 해시로 확인한다. 실제 native 실행계약의 원 byte SHA는 그대로 보존하고 그 이외의 코드 변경은 허용하지 않는다. 이 공유 검사는 실행 모듈을 import하지 않고 새 예산/환경을 만들지 않는다. 공유 검사 자체3검사도 PASS다. 원 `pilot check/run`은 실행 당시 strict byte SHA와 local 소비계보를 계속 요구한다.

PPT용그림5종은PNG/SVG로저장했다. 대표실행/온도는실행전고정condition9(지속부하/mean),35..55초시간표와35..180초AP경로다. 전체조건은CSV와조건지도에보존했다. 시뮬레이터전체PC시간과정책callback시간을분리하고폰실측시간/전력으로환산하지않았다.
