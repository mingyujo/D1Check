# 기한 예약·열 분산 규칙 48조건 pilot 결과

2026-10-08 KST · RESERVED-THERMAL-01 단계2 · Sol 실행 완료

**Triton 제한 해제/동시2 요청 adapter 대비 주평가24조건의 열·에너지는 함께 줄었으나, Band/EFT 대비 공동 개선은0이다. 전체 조건에서 일반 기한 실패도 더 많다.** 목표를 모두 만족한 우월한 정책으로 채택할 근거는 아직 없다. 다음은 Astra 단계3 검토이며 본학습은 시작하지 않았다.

## 비교 조건과 분모

고정4seed610810001–004 × low/queue/burst/sustained × mean/short/long =48조건이다. Triton5설정·Band whole-request 대응·SHARED_EFT·기존 자체2규칙·새 RESERVED_THERMAL_REQUEST_V1, 총10정책/480행이다. 완료된 기존432행을 입력·모형·소스·결과 SHA 확인 후 재사용하고 새48행만 평가했다. 기존 공개 개발/회귀 자료이며 새 holdout이 아니다.

정책당3,168예정 요청, 전체480행의 논리 요청31,680건이다. 모델·입력·도착·실현 비용·초기 상태·lane 자원은 같다. 분류 output-ready1.5초, 탐지 persist6초, J0–120초, AP35–180초를 유지한다. 최대2lane·비선점 전체 요청이며 실제 lane 반환까지 점유한다. A24의 검증된 상태 계수만 사용하고 기기 실행은0이다.

## 서비스 성적

| 정책 역할 | 예정/완료 | 긴급 실패 | 일반 기한 실패 | 전체48조건 전량 |
|---|---:|---:|---:|---:|
| 신규 기한 예약·열 분산 |3,168/3,168|0|53|48/48|
| Band 대응·EFT·Triton 제한 해제/동시2 각각 |3,168/3,168|0|36|48/48|
| 기존 에너지·열 규칙 |3,168/3,168|115|95|48/48|
| 기존 큐 전체 규칙 |3,168/3,168|57|81|48/48|
| Triton 동시1·동일 |3,168/3,057|1,030|747|36/48|
| Triton 동시1·분류 가중 |3,168/3,083|0|1,002|36/48|

미완료도 서비스 실패에 포함한다. 완료만 보고 실패를 제외하지 않는다. 신규의 low/sustained 주평가24조건은2,592/2,592완료·기한, queue는288완료 중40기한 실패, burst는288완료 중13기한 실패다. 과부하24조건을 제외하거나 평균 이득으로 실패를 상쇄하지 않았다.

`service_preserved`는 양쪽 전량 완료, 긴급/일반 실패수 비증가, 긴급P95 비증가를 모두 요구한다. 이 조건과 공통 비용 적격성을 통과한 쌍에만 열 개선형(AP 감소·J 비증가)과 공동 개선형(AP·J 동시 감소)을 표시한다. 원래 기한 전부 준수 여부도 별도 열로 남겼다. 비교 EPS1e−9는 숫자 처리용이며 물리적 개선 기준이 아니다.

## 열·에너지 비교

아래 평균은 같은 주평가24조건의 신규−기준이다. 모형 결과이며 실제 절감/표면온도 차이가 아니다.

| 기준 | 서비스 유지/24 | AP 최고값 평균 차이 | J 평균 차이 | AP 감소·J 비증가 / 공동 감소 |
|---|---:|---:|---:|---:|
| Triton 제한 해제 |24|−0.119788°C|−0.770236J|24 /24|
| Triton 동시2·동일/분류 가중 각각 |24|−0.119788°C|−0.770236J|24 /24|
| Band 전체 요청 대응 |24|−0.048470°C|+0.154012J|0 /0|
| SHARED_EFT |24|−0.059351°C|+0.088176J|0 /0|

전체48조건에서는 강한 Triton·Band·EFT 각각 서비스 유지38조건이다. Triton 제한 해제/동시2 각각 열 개선25·공동 개선24, Band/EFT 각각 열 개선1·공동 개선0이다. Band/EFT의 단1건(seed610810003/burst/short)은 J동일·AP약−0.000062776°C로, 실제로 확실한 개선이라고 해석할 크기가 아니다. 다른 기준/각조건 차이는 [432쌍 CSV](pilot_pairs.csv)에 모두 공개한다.

주평가에서 분류GPU 배정 총수는 신규630, EFT791, Band737, Triton 제한 해제1,224건이며 실제 병행시간 합계는 각각173.711/206.562/203.216/206.568초다. 새 규칙의 자원 선택/일정 변화와 열 차이가 함께 관측된다. 이 요약만으로 저장 계획·대기·자원 선택 각각의 인과 기여를 분리할 수 없다. Triton 대비 이득을 새 예약 설계만의 이득으로 주장하지 않는다.

## 계획 탐색·예약·판단 비용

- 총13,317판단 중 탐색 실패 EFT fallback6,693, overrun EFT fallback694, 합계7,387이다. 원본 `fallback_callbacks`는 탐색 실패만 세므로 [진단 CSV](pilot_diagnostics.csv)에 원본 decisions 기반 별도 수치를 추가했다. 중복 제거된 사건 수를 callback 수로 쓰지 않았다.
- 선택된 scoring callback은 기준계획5,732·저장계획191·새 탐색7이다. callback별 적격 후보의 AP/J 점수가 둘 이상인 경우230, 현재 EFT 후보보다 AP가 낮은 적격 후보가 있는 경우198이다. 후보 반복 횟수와 서로 다른 행동·미래 성과를 혼동하지 않는다. 이 정보만으로 RL이 개선할 수 있다고 결정하지 않는다.
- 내부 cap 초과 요청319건, 최종 내부 J 예산 충족25/48·초과23/48이다. 잔액 범위−0.173279~+0.175463J. EPS 수준의 작은 수치 차이도 원 판정 그대로다. 이 경로 의존 장부는 별도 EFT/Band 실행 대비 J 상한 보장이 아니다.
- 계획 scoring205,144회, PC callback 합계102.417초·최대150.324ms다. 이 시간은 실기기 판단 비용/에너지로 환산하지 않았다. 모든 place/long 검사 횟수는 아니며 모형의 제어 비용0 가정을 유지한다.

## 실행 오류·수정·재개

처음4조건 저장 후 queue/short에서 저장 시작 하한을 복원할 때 CPU 작업이0.333344019ns 겹쳤다. 원 place의1ns 허용과 비용 segment의 엄격한 점유 검사가 다르게 처리해 `detection_CPU+detection_CPU` 오류가 발생했다. 별도 fixture1회로 동일 원인을 재현하고 [실패 계획·겹침 근거](pilot_numeric_failure.json)를 [보완 등록](pilot_numeric_repair.json)의 해시에 고정했다.

동결18소스·기존4gzip·원 manifest는 수정하지 않았다. 별도 `d1_reserved_thermal_pilot_repair.py`가 저장계획의 지원되지 않는 양의 겹침≤1ns에 한해 시작을 lane 끝에 맞춘다. 실제로 큰 겹침은 오류로 거부한다. cap·기한·J 식·WAIT·계수·지원 상태를 완화하지 않는다. 신규3개 직접 검증 PASS(환경0), 실제 실패 조건을 포함한 남은44행 성공. 완료4행은 원 소스 실행, 나머지44행은 수치 보정 adapter 실행이라는 차이를 등록과 항목 binding에 명시했다. Astra는 이 제한적 실행 차이도 확인해야 한다.

완료48항목을 실제 재호출해 추가 환경0으로 재사용되는 것을 확인했다. 시작/실패 장부·원gzip/receipt는 보존했다. original runner `pilot`은 보완 항목을 원 binding으로 읽을 수 없으므로 아래 보완 재현 명령을 사용한다. 소스가 달라지면 조용히 재사용하지 않는다.

이번 실제 추가50환경 =48성공 pilot +1실패 pilot +1실패 재현 fixture다. 누적71환경(성공68/실패3), fixture22·pilot49, 전체 잔여19,929·단계2 잔여441. 누적 예정 요청3,277 중 성공 환경3,228완료, 실패3환경의49요청에는 완전한 완료 receipt가 없다. 전체 정책480행의31,680논리 요청과 실제 신규 소비를 구분한다. 본학습·기기·ADB·실측0.

## 근거와 재현

- [오프라인 화면](pilot_index.html), [전체480행](pilot_results.csv), [정책 요약](pilot_policy_summary.csv), [진단48행](pilot_diagnostics.csv), [432쌍](pilot_pairs.csv), [요약 JSON](pilot_summary.json).
- [대표 ledger](pilot_representative_ledger.csv)·[8개 대표 정책/trace 기록](pilot_representatives.json)은 사전 지정 seed610810001/mean/queue·sustained와 신규/Band/EFT/Triton 제한 해제다. 전체 원본은 `output/reserved_thermal_20261008_v1/pilot_items/`에 저장했다.
- [그림5개 PNG/SVG](pilot_figures/)는 전체 서비스·열/에너지 차이·lane 시간표·AP 경로·전체 조건 지도를 보여준다. AP 안전 임계값이 없어 초과시간은 계산 불가이며 표면온도와 구분한다.
- 시간표에서 파랑은 긴급 분류, 주황은 일반 탐지다. [오프라인 화면 검증](pilot_browser_verification.json)은 별도 headless Chrome의 로컬 파일 로딩·489표행·Band검색49행/해제489행·그림5개 로딩을 확인했다. 전체 그림과 수정된 시간표 제목·화면 screenshot도 육안 확인했다.
- [검증/해시](pilot_verification.json)에는 현재HEAD·미커밋·명령·18소스/보완 소스·입력/산출물 바인딩을 기록했다.48행 요청/lane/온라인 감사·공통 비용 재계산 통과, 별도 점유 적분 J 최대 차이2.842171e−14J다. 독립 실기기 검증이 아니다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_reserved_thermal_pilot_repair -v
python -B -m tools.d1_reserved_thermal_pilot_repair
python -B -m tools.d1_reserved_thermal_pilot_analysis
```

저장 상태가 온전하면 보완 실행 명령은 완료48항목을 재사용하고 환경을 추가하지 않는다. 원본 대용량 결과·개인 경로를 Git 공유물에 넣지 않는다. 이번 단계는 HEAD `a081d55e9cc9d1a732bee9bed9e1ca8535244b29`+미커밋이며 commit/push0, 보호 모형/기본 정책/strict/experiment_ready=false·사용자 파일·다른 worktree·별도 작업을 보존했다.

다음 입력(Astra):

> RESERVED-THERMAL-01 단계3을 검토해. PILOT_REPORT.md·480행·진단·pilot_numeric_repair.json을 확인하고, 전체 서비스 손실과 Band/EFT 대비 J 증가를 포함해 규칙만 진행/RL 진행/수정/보류를 판정해. 누적71환경, 본학습/기기0이며 RL 실행 계약은 아직 미동결이다. 진행을 허용할 때만 정확한 다음 Sol 범위와 입력을 고정해.
