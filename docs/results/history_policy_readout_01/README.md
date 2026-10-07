# 정책 차이와 이력 확인 잔차

[한국어 판독](../../HISTORY_POLICY_ERROR_READOUT_20261008.md) · [화면](index.html) · [전체1,920쌍](policy_context.csv) · [요약](policy_summary.csv) · [실제 이력 대조잔차](history_contrasts.csv).

새 측정·시뮬레이션·학습0. 저장192조건/2,112행과 원모형 확인6세션을 재사용했다. 모형의 작은 차이를 실제 절감·정확도PASS로 승격하지 않는다. `summary.json`의 large_effect_threshold/physical_policy_winner/confidence_interval은null이다.

- 정책차이: 후보R2−각기준, J0–120초/AP35–180초 모형격자. `service_preserved`는 전량·원실패 비증가·긴급P95 비증가이며 `both_all_deadlines`는 별도다.
- 이력대조: 실제일정 조건부PAR−CPU의 예측−관측 잔차, AP는 세션별실제post35표본창. 개발2대조/확인2대조와 최초조건 차이 보존. 다른프로토콜/부하의잔차를 보편한도·정책교정·신뢰구간으로사용하지 않음.
- 독립 단위는 실제실행/조건이다. 192PC조건이나 센서표본이6폰세션을 늘리지 않는다. 사후 규모판독·후보미채택 유지이며 열→처리시간/표면온도/SOC는미검증이다.

저장소만으로 재현한다. 외부원본·기기연결 불필요. 항상 새출력경로를 지정한다.

```powershell
python -X utf8 -B -m tools.d1_history_policy_readout --output output/history_policy_readout_reproduction
python -X utf8 -B -m unittest tools.test_d1_history_policy_readout -v
```

의존 파일은 `summary.json`의source_hashes6개다. J/AP이미지 생성에matplotlib과한글폰트(Malgun Gothic)가필요하다. 원모형·saved CSV의hash는불변이며 입력바인딩을보존한다. PNG/SVG는같은단위의정책차이/별도대조잔차규모로, 정책의실측예측확인그래프나오차막대가아니다.
