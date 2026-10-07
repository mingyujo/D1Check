# 기존 규칙 재조합과 PPO 학습량 비교

2026-10-07, `RULES-RL-AMOUNT-10` **완료**. 재조합 → 별도6개 PPO 재학습/학습량 비교 → 동결 최종평가를 수행했다. 과거 정확한 연장 차단·원자료·모형·기본/strict/`experiment_ready=false`를 보존한다.

[한국어 결과 보고서](../../../REQUEST_RULES_RL_AMOUNT_20261007.md) · [오프라인 화면](index.html) · [학습량 요약](amount_summary.csv) · [최종 무결성 검증](final_integrity_verification.json).

적격 선택 정책은1,024/2,048/4,096/8,192에서3/3/4/4개였지만, 강한 SHARED_EFT 대비 공동 개선은 모두0건이다. 부적격 정책의 일부 조건 이득·재조합의 에너지–열–응답 상충은 전체 분모로 보존한다. 상한 도달·수렴 미확인이며 기본 정책을 바꾸지 않는다.

실제 소비: 본학습49,152episode/6,144PPO update + 이번fixture20episode/20update, RL환경68,754/80,000·재조합458/4,000·기기0. 최종192조건×55정책=10,560행 중3,650행은 기존/동일가중치의 같은 입력 결과를 재사용했다. 새로운 독립 실행으로 세지 않는다. 24terminal/48actor를 보존했고 원125파일·사용자8파일 SHA 및455,808실제 원시 요청의 서비스 경계를 확인했다.

worker는 KST03:28:32~14:00:31에 실행됐고 현재 종료됐다. I/O복구1건/학습 재계산0, 사용자실제일시정지0이다. 관측 도구의 대기 만료와 프로세스 종료는 구분했다. 자세한 소비·오류·역할·비교 한계는 보고서를 따른다.

## 결과 파일과 재현

- `training.csv` 6,144update, `validation.csv` 198검증시점: 학습/개발검증 곡선. optimizer 반복 표본과 환경 실행을 구분한다.
- `final_results.csv` 10,560행: 완료·기한·요청 분모·절대 J/AP/응답·latest/best·재사용 출처.
- `paired_differences.csv`: SHARED_EFT/EFT_REFERENCE 두 주요 기준의20,736행. 모든7기준의72,576짝 차이는 로컬gzip에 두고 `local_pair_manifest.json`으로 연결한다.
- `policy_summary.csv`:7기준×54비교정책×2층=756행. 부적격 비용은 진단값이며 성공 조건만 골라 전체 순위를 만들지 않는다.
- `input_manifest.json`·`recombination_inputs.json`: 입력/가능 일정/의미hash. 과거 노출과 새 구성의 역할을 구분한다.
- `checkpoint_manifest.json`·`final_freeze.json`·`cache_identity_audit.json`: terminal/latest/best의 구분과 code/actor/입력 동결·캐시 조건.
- 그림5종PNG/SVG: 개발검증, 학습, 최종latest/best 비용, 재조합, 최종서비스. 최종 서비스 그림의빨간x는latest,빨간+는best의검증부적격이다.
- `branch_audit.json`·`representative_recombination.json`: 놓친완성조합의원인/점수·실제배정.

공유CSV만으로 그림·화면을 재현한다(환경·학습0, 원checkpoint불필요).

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_rules_rl_report --shared-source docs/results/request_ppo_01/rules_rl_amount_v1 --output output/rules_rl_amount_20261007_v1/shared_reproduce
```

로컬원본이있을때 전체 서비스/상태/일부원시비용 검증을 다시 할 수 있다. 완료실험은 재실행하지 않는다.

```powershell
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_rules_rl_verify
```

## 승인과 계산

벽시계16시간(보수적 KST10/7 03:00~19:00), 재조합 환경4,000회, RL환경80,000회, HEAD/QUEUE×seed11/23/37 각각 최대8,192학습, 기기0. fixture·검증·최종 평가·복구 재계산을 모두 이번 장부에 포함한다. 과거114환경/12학습 fixture는 이전 작업 소비로 별도 보존한다.

최대 본학습49,152+개발 검증4,752+공유참조8,216+마지막/검증선택 정책 최종평가9,216=71,336RL환경 실행. 같은 가중치·입력 결과의 재사용은 실제 실행으로 다시 세지 않는다. 재조합 A/B의 최종192조건 비교는 재조합 예산에서 계산한다. 기준5정책의 기존 평가960행은 입력·코드·모형 해시를 확인해 재사용한다. 마무리90분을 남기고 새 학습을 중단한다.

환경 실행·학습episode·PPO update(8episode)·실제 Adam step(minibatch 업데이트)을 구분한다. PC 판단 시간은 기기 연산 시간이나 에너지 절감으로 바꾸지 않는다.

## 재조합

기존 `d1_pareto_beam.py` 및 `d1_joint_queue_area.py`의 순서/배정·EFT 후속·long 문맥 서비스 guard·J/최고AP/AP면적 guard를 재사용했다. 추가 WAIT를0으로 고정하고 이미 도착한 상위3요청을 대상으로 한다. A는prefix 판정과beam폭8/node상한64, B는완성 순서×지원backend 조합을 만든 뒤 같은 판정을 적용한다. 기존4요청/WAIT beam과 범위 차이를 밝히며 새 스케줄링 계열로 부르지 않는다.

실제 지원은분류CPU/GPU·탐지CPU라 CCD는24개, CDD는12개 완성 순서/배정 조합이다. 첫 행동은현재 즉시 가능한 경로만 허용하고 기준EFT 행동을 반드시 남긴다. 이후 예측의 자원 대기는 새 의도적 WAIT가 아니다. 이미 도착한 전체큐에 같은 기존 후속 처리를 적용한다. 미래도착·seed·trace명·실현문맥은콜백 입력에 없다.

개발seed610710001/2와 확인610720001/2, CCD/CDD, 기존3처리문맥, EFT/A/B 총72환경 실행. 원래seed는 이미 노출된 값이고 3요청의 동시 도착을구성한 새진단이다. 독립실기기 확인이나새미관측 holdout으로 과장하지 않는다. 개발에서서비스악화→열악화→J악화→평균J→면적 순으로 EFT가선택됐으며, 확인결과로 다시고르지않는다. A/B 모두RL 최종비교의진단군에남긴다.

## RL 설계와 보존

기존v2의85관측·17행동·64×64 actor/5value·masked PPO-Lagrange·Adam lr0.0003/eps1e-5·4epoch/256minibatch·clip0.2·entropy0.01·gradient clip0.5·KL0.03·GAE0.95를 그대로 호출한다. 보상·서비스/양의 열초과cost·승수갱신도기존 함수를사용한다. 총학습길이종속 스케줄은없다.

첫1,024입력은기존v2와같다. 이후610730000~610731535(3,072episode), 조건부연장610750000~610752047(4,096episode), low/sustained교대·누적인덱스의3문맥회전이다. 개발 검증은원24조건을32update마다재사용한다. 최종시험은원192조건으로과거노출된사후대응 비교다. 입력의가능일정witness와split 간의미hash비중복은학습 전에 산술검사했다. 실패한입력을성적좋은seed로교체하지않는다.

6개를32update씩순환하여공통1,024/2,048/4,096지점을먼저확보한다. 각지점에서마지막actor+critic/Adam/RNG/승수/진행/선택상태의terminal archive와best-validation actor를분리한다. rolling checkpoint는두세대이고milestone은불변이다. 완료episode/update·검증블록 경계에서저장하므로중간환경state는없다. 학습중인각learner의RNG를교체복원하고보존helper가미래RNG를소비하지않는다.

## 결과 전에 고정한 연장 규칙

4,096 직전416/448/480/512update의동일24조건 개발검증을 사용한다.

- 개선 지속:512의기존사전식key가416보다좋거나416이후누적best가선택됐다.
- 관측 정체:네시점의8개key성분이1e-9이내로같고416이후누적best가없다. 전역수렴을뜻하지않는다.
- 정체 불확실:위둘에해당하지않는변동·회귀를포함한다.

하나라도개선지속/불확실이면남은예산안에서6개모두8,192까지연장한다. 공통지점과미완성지점을구분한다. 최종시험은연장결정과모든정책동결뒤에만연다. 성적을보고보상·기한·seed·가드를바꾸거나새초기화를하지않는다.

## 실행·복구·저장

로컬원본: `output/rules_rl_amount_20261007_v1/`. campaign/consumption JSONL, 사용자승인원문, source/input manifest, rl/learners의rolling/terminal PT, actors JSON, evaluation의압축ledger/결정기록을보존한다. 기존대용량자료는Git에추가하지않는다.

이번worker의PID·명령·소스해시는worker_process.json, 표준출력/오류는worker.stdout.log/worker.stderr.log다. 현재worker는정상종료했고owner lock은없다. 실행중/상태불명확에서중복실행하지않으며오류원문/마지막온전한state/소비를보존한다. 같은원인PC입출력재개최대2회이며학습수치·정책결함은자동처음부터재학습하지않는다.

```powershell
# 읽기 전용 상태 확인
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_rl_amount_campaign --action Status
```

Run/Register는소비된출력에다시호출하지않는다. Resume는동일소스/환경·정상중지또는입출력실패의온전한state만허용한다. 권한·네트워크제한우회/강제push/사용자변경덮어쓰기는하지않는다.

최종CSV·그림·한국어보고서·오프라인화면·재현명령을공유했다. 소프트웨어검증/모형효과/실기기효과를구분한다. 실제기기공동절감·에너지적격성·독립정책확인은이번PC작업으로완료되지않았다.
