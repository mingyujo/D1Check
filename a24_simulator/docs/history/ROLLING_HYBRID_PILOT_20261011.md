# 새 온도 보정 모형에서 공동 롤링 파일럿

작업 `ROLLING-HYBRID-PILOT-07`. 사용자 “새로운 시뮬레이션 만든걸로 이거진행하자” 지시로 준비된 전체 요청 흐름 파일럿을 최종 v3 thermal-only hybrid에 옮긴다. 구모형 준비본 `ROLLING-EXECUTION-PILOT-06`은 미실행 상태로 보존한다. **미소비 상한112회를 이관하며 추가112회 예산을 만들지 않는다.**

## 결과 확인 전 고정 범위

- 같은 입력825060101/102 × low/queue/burst/sustained × mean/short_context/long_context＝24조건, Band/Triton/원 공동 롤링 V2/실행 첫 행동 직접선정4역할＝96행. 도착·요청·기한·서비스 실현seed201·동일 초기 실측 preload를 유지한다.
- 최종 전달 모형 upstream SHA `6dd806bc30c5d69dd07237dc8fbe0bc09ed90a86fede4d86294ae14be2eb1196`. 공유 JSON의 개인 절대경로 하나만 저장소 상대경로로 바꾸고 별도 export SHA를 기록한다. 계수·α·λ·서비스·전력은 변경하지 않는다.
- 온도는 후보 선별·실제 첫 행동의 보호 조건·최종 AP 경로 모두 같은 새 head를 사용한다. 결과만 새 모형으로 다시 계산한 비교가 아니다. AP 초기 R/H 추정도 전달된 α0.5 식을 유지한다. 느린 부하항은 별도 추정 상태이며 관측 불가능한 실제 내부온도로 표시하지 않는다.
- CPU/GPU만, 분류CPU/GPU·탐지CPU·CG_DC 최대2건. 응답은 OUTPUT_READY/PERSISTED, lane 반환AVAILABLE. 원 5phase 처리시간·기한1.5/6초·J0..120·AP35..180초 격자1초·대기credit0.25초·창4·선별8 유지. 선점/주파수/전력제한/새학습/NPU/기기 실행0이다.
- native 기능 gate4 통과 후96행. 예상100/상한112, 원 누적9749환경/1449학습, 정상 완료9849/1449. 명시적run에서1시간clock을 한 번 시작하며 마지막5분 저장, 중단·재개로 초기화하지 않는다. 구모형 파일럿과 동시 실행하지 않는다.
- 동일 전량완료·긴급/일반 기한실패·긴급P95·J·전체최고AP 비악화를 **Band/Triton 양쪽·24조건 전부**에 요구한다. low/sustained 절대기한 실패0. 전량 유지 후 한 주부하의 모든seed/문맥에서 AP 또는J 엄격감소가 있어야 유망. epsilon0·원 판정 유지, 일반 평균 지연은 별도 공개한다.

## 근거의 한계

최종 새 모형은 CPU/PAR 각1회에서 AP 평균오차를 줄였으나 CPU 피크·최대오차는 악화했다. 이 파일럿의 여러 도착 형태는 **제한된 모형 탐색**이며 실기기 정책 검증·미측정 열 상태의 지원 확정이 아니다. 표면온도·안전한도 초과·폰 판단 에너지 계산은 null이다. 에너지 절대교정과 냉각에 따른 처리속도 회복은 미지원이며 이번 새 모형도 이를 해결하지 않는다. 평균오차보다 작은 AP 차이를 실제 폰 개선으로 확정하지 않는다.

기존 원모형 결과·v2/원v3 실패·모형 개발 기록·RL 체크포인트·사용자 미커밋·기본/strict/experiment_ready=false를 유지한다. 새 모형 개발 파일은 별도 작업 소유이며 수정하지 않는다. 추가 적합·실측 없이 frozen 모형만 읽는다.

## 실행과 산출물

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_rolling_hybrid_model tools.test_d1_rolling_hybrid_pilot tools.test_d1_rolling_execution_prefix tools.test_d1_rolling_execution_pilot tools.test_d1_rolling_prefix_selection -v
python -B -X utf8 -m tools.d1_rolling_hybrid_pilot prepare
python -B -X utf8 -m tools.d1_rolling_hybrid_pilot run
```

공유 결과는 `docs/results/rolling_hybrid_pilot_07/`, 원 판단·실행 로그는 `output/rolling_hybrid_pilot_20261011_v1/`이다. 입력·모형·source SHA와 판정은 실행 전에 등록한다. 완료 뒤 조건별CSV/응답·J·AP·실행시간표/오프라인화면과 전체 판정을 여기에 추가한다. 통과해도 기본 정책을 자동 교체하지 않으며 미달 결과에 추가학습으로 구제하지 않는다.

## 완료 결과

gate4＋고정96행＝100환경, 실패0·학습/적합/기기0이다. 비교 요청6336/6336, gate8/8 전량 완료이며 누적9849환경/1449학습이다. 42순수검사·native gate4·전량96원장/응답/lane경계와 고정SHA 검사 PASS다. 서비스·성능 채택 판정은 별도이며 **두 롤링 후보 모두 미달**이다.

| 정책 | 예정/완료 | 긴급 기한 실패 | 일반 기한 실패 | 조건별 긴급P95 평균 | 조건별 J120 평균 | 조건별 최고AP 평균 |
|---|---:|---:|---:|---:|---:|---:|
| Band 판단규칙 대응 | 1584/1584 | 0 | 21 | 411.752ms | 152.274604J | 30.452170°C |
| Triton 판단규칙 대응 | 1584/1584 | 0 | 21 | 436.095ms | 152.740610J | 30.472198°C |
| 기존 공동 롤링 V2 | 1584/1584 | 0 | 21 | 411.751ms | 152.024998J | 30.442380°C |
| 첫 행동 직접선정 롤링 | 1584/1584 | 0 | 30 | 411.751ms | 152.032801J | 30.438887°C |

새 직접선정은 Band 대비 평균J−0.241803J/AP−0.013283°C이나 일반 기한실패＋9, 일반 응답 평균＋355.307ms다. 기존 롤링은 일반 실패를 유지하면서 J−0.249605J/AP−0.009791°C이나 일반 응답＋213.550ms이며, 일부 조건AP 또는Triton 대비P95/J가 악화했다. 전체평균으로 조건별 실패를 가리지 않는다. 2seed×3문맥의9실패 차이를 독립9반복으로 부르지 않는다. 에너지/AP 이득 규모는 실기기 확정 근거가 아니다.

각 정책 긴급684/일반900건이 예정·완료됐다. 긴급 기한실패율은 전부0%, 일반 기한내완료율은 Band/Triton/원롤링97.6667%, 새선택96.6667%다. 미완료0과 기한실패를 구분하고 실제 운영 성공률의 확률추정으로 일반화하지 않는다.

Band/Triton 양쪽48대응 중 기존롤링34/48, 새직접선정20/48만 전량유지 조건을 충족했다. low/sustained 주부하의 전조건 엄격비악화 조건 때문에 양쪽 maintenance/promising=false다. 주 low에서 AP는 두 롤링 모두 약＋0.004°C이며, sustained는 seed에 따라 방향이 달라 평균만으로 통과시킬 수 없다. 아주 작은 J＋7.1e−10J도 원epsilon0 판정에서 보존했으나 이 수치가 탈락의 실질 원인은 아니며 같은 조건의 기한 실패도 악화했다.

새 선택기의 Band와 다른 첫 행동402개 중 냉각대기393개다. Band와 같은 전체 일정은0/24이며, 알고리즘이 동작하지 않아 전부복귀한 결과가 아니다. 한 대표 실패(condition6, burst/mean)에서 일반 요청 `/22`의 응답은 Band5978.159→새6228.159ms로0.25초 늘어6초 기한을 넘었다. 이처럼 현재큐만 보는 조건부 보호는 이후 도착을 포함한 전체 서비스 보장이 아니다. 전체 계획을 함께 평가하는 기존 공동 롤링이 이번 자료에서는 일반 기한 실패를 더 잘 유지했다.

이번 추천은 **기존 기준 정책 유지**, 발전 후보는 직접선정보다 **기존 공동 롤링 V2**다. 주부하조건AP 손실·대기 누적·일반 완료시간을 먼저 진단해야 하며, 이 결과만으로 RL 본학습을 확대하지 않는다. 새 모형도 냉각→처리속도회복은 없으므로 모형 외 효과가 검증됐다는 해석은 불가하다.

배치 native 계산시간 합계136.141초이며 Band1.461/Triton1.193/원롤링69.279/새롤링64.208초다. 이 값은 PC 시뮬레이터 전체 시간이고 폰 정책판단 비용이 아니다. 콜백시간·예측수·대기·점유·병행시간은 [control_cost.csv](results/rolling_hybrid_pilot_07/control_cost.csv)에 분리했다. 원공통0증분제어비용 가정은 유지했다.

[전체 판독·그림](results/rolling_hybrid_pilot_07/README.md) · [오프라인 화면](results/rolling_hybrid_pilot_07/index.html) · [전체96행](results/rolling_hybrid_pilot_07/comparison.csv) · [조건별 차이](results/rolling_hybrid_pilot_07/paired_differences.csv).

보고서만 재생성하는 PC 명령은 `python -B -X utf8 -m tools.d1_rolling_hybrid_report`다. 완료된 `run` 재호출은 새실행을 시작하지 않고 완료보존 오류로 거절한다. 원시 gzip은 local에 보존하고 공유에는 모형/계약/입력/CSV/그림/검증만 포함한다.

Git 반영검사에서 기존 일부소스의 실행Windows CRLF/Git LF 차이를 확인했다. 내용은 exact동일하며 원실행 source SHA를 수정하지 않았다. 별도 `source_index_equivalence.json`에 실행byte/indexbyte/정규LF 해시를 기록하고 `python -B -X utf8 -m tools.d1_rolling_hybrid_shared_check`로 공유 내용만 읽기전용검사한다. 그 외 코드변경은 거절하며 이 검사는 native 실행권한/새소비계보를 만들지 않는다. 실제실행42검사와 공유검사3을구분한다.
