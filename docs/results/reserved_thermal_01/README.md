> 최신 완료 결과는 [최종 요약](FINAL_SUMMARY.md)·[새192조건 화면](final_rule_only/index.html)·[최종 보고서](final_rule_only/REPORT.md)를 따른다. 아래는 단계2 최초 구현안/검토 이력이다. 최신 자율 실행 지시로 모델 전환 대기는 해제했고, 최종 판정은 현 후보 미채택·RL0이다.

# 기한 예약과 열 분산 규칙의 구현안 및 검토 인계

2026-10-08 KST · RESERVED-THERMAL-01 단계2 · Sol 구현

**최신 상태는 [48조건 pilot 완료](PILOT_REPORT.md)다.** [오프라인 비교 화면](pilot_index.html)·[전체480행](pilot_results.csv)·[432쌍](pilot_pairs.csv)·[진단48행](pilot_diagnostics.csv)·[그림5개](pilot_figures/)를 보존했다. 주24조건에서 강한Triton 대비 공동개선24, Band/EFT0이며 전체 일반 기한 실패53 vs기준36이다. 동결18소스/원4항목을 보존한 별도 수치adapter로 오류를 해결하고48행 완료했다. 누적71환경, 학습/기기0, 다음은 Astra 단계3이다. 원43검증·초기 수정/최종 pilot허가 판정을 보존했다. 아래 구현 설명과21개 PASS 및 대기 표현은 검토 전revision3 이력이다.

**구체 구현안과 작은 사례 검증을 완료했다. 48조건 성능 비교는 핵심식의 Astra 검토 전이므로 실행하지 않았다.** 본학습·기기 명령은0이다. 동일 모형에서 Band/Triton보다 낫다는 성능 근거는 아직 없다.

구현은 [새 adapter](../../../tools/d1_reserved_thermal.py), [등록/소유권/소비 실행기](../../../tools/d1_reserved_thermal_study.py), [수작업 및 엔진 검증](../../../tools/test_d1_reserved_thermal.py)에 있다. [단계 계획](../../RESERVED_THERMAL_STAGE_PLAN_20261008.md)에 따른 신규 경로이며 기존 정책·동결 모형·strict·experiment_ready=false를 유지했다. 내부 engine ABI는 기존 beam ID를 재사용하지만 공개 정책 ID는 `RESERVED_THERMAL_REQUEST_V1`이다. 과거 beam의 성능 행과 같은 정책으로 합치지 않는다.

## Astra가 검토할 구체 핵심식

새 임의 여유 비율을 넣는 대신 아래 보수적인 식을 구현했다. 이 식 자체가 아직 검토 대상이며 이미 확정된 성능 정책으로 표시하지 않는다.

### 완료 예약

처음 등장한 요청 i에 대해 현재 도착 큐의 long-context EFT 후속 일정을 끝까지 만든다.

`cap_i = min(원래 절대 응답/저장 기한_i, 최초 long-context EFT 예상 응답/저장 시각_i)`

cap은 한 번 발행하고 갱신하지 않는다. 이후 후보의 long-context 후속 일정이 기존 cap을 넘으면 탈락한다. 공개 단계에서 실제 응답이 cap을 넘거나 관측 overrun이 발생하면 파손 원인을 기록한다. 이미 실제 응답한 요청을 미래 지각으로 다시 세지 않는다. 실제 lane 반환은 별도다.

**검토 질문:** 이 식은 기존 EFT 예측만큼 빠른 완료를 요구하므로 원래 deadline보다 엄격하다. 시작시각을 고정한 것은 아니지만 열 분산의 선택 여지를 너무 줄이는가? 긴급/일반에 같은 최초 완료 cap을 쓰는 것과 기한 안의 여유를 배분하는 다른 식 중 어느 것을 채택할지 성능 비교 전에 결정해야 한다. long-context는 개발 스트레스 문맥이며 WCET나 실제 보장 상한이 아니다.

### 누적 에너지 예산

첫 발행 시:

`B = 지금까지 공개 실행 상태로 누적한 모형 J + 현재 도착 큐 EFT 후속 일정의 남은 J`

새 요청 A가 도착할 때만 같은 현재 상태에서 두 완성 계획을 비교한다.

`B_new = B_old + J_remaining(EFT(Q_old ∪ A)) - J_remaining(EFT(Q_old))`

후보의 `누적 모형 J + 후보 남은 J <= B + 수치 epsilon`일 때만 최적화 후보로 허용한다. 새 요청 ID별 credit은 한 번만 발행하며, 새 요청에 따른 차이가 음수여도0으로 자르지 않는다. 다른 callback에서는 예산을 새로 만들지 않는다. 시간창 밖이라 비용을 계산할 수 없으면 예산 적격으로 대체하지 않는다.

**검토 질문:** 새 요청의 에너지 증분은 시간배치/병행에 따라 달라질 수 있다. 현재 상태에서 계산한 signed credit을 장기 예산으로 누적하는 것이 연구 질문에 맞는가? 이 식은 실행 초기에 별도로 시작한 EFT/Band의 전체 결과 대비 에너지 비악화 보장이 아니다. 부적격 후보를 서비스 우선 fallback으로 실행하면 예산이 깨질 수 있고 그 기록을 남긴다.

### 후보 탐색과 선택

저장 후속 일정과 현재 EFT 계획을 포함하고, 도착4요청·깊이4·beam8·최대64확장·기존 WAIT 제한을 재사용한다. 각 sequence는 전체 현재 큐를 완료한 뒤 검사한다. 현재 prefix가 예약/J 검사를 통과하지 못해도 탐색 후보로 이어가며 완료 계획 점수로 폭을 제한한다. 이는 모든 조합을 찾는 완전 탐색이 아니다.

적격 후보는 `지금까지 최고 AP를 포함한 예상 최고 AP → 예상 전체 J → 긴급 예상 응답 → sequence` 순으로 선택한다. 기존 제어의 손해를 되돌린다는 가정은 없다. 실제 기기 제어 비용과 무제한 미래 도착의 기한 보장도 없다.

## 검증과 실제 소비

- 새16검증 + 기존 AP면적/경계5회귀 = **21개 검증 통과**. 최신 명령과 소스 바인딩은 [verification.json](verification.json)에 있다.
- 최초 실행에서 반환 tuple을 잘못 해석한 후처리 오류1환경과, overrun이 기준정책 조기 반환 때문에 장부에 기록되지 않은 단위검증 실패를 확인했다. 반환 형식과 기록 위치를 수정하고 원 실패와 등록 revision을 보존했다.
- 전체 실제 환경 시작 **11회**, 모두 fixture다. 성공10회/실패1회이며, 관측 응답 장부·누적 J 검증 추가 후5사례를 다시 실행한 비용을 포함한다. 총31예정 요청, 성공 환경의 완료30요청이며 실패 환경1예정 요청의 완료 receipt는 없다.
- 최신 버전의 고유5사례는 single/mixed/future-suffix 두 경우/long-context overrun, 총15예정 요청 모두 완료·기한 충족·실제 lane 해제 확인이다. 작은 수작업 사례이며 정책 우월성/독립 확인 자료가 아니다.
- 사전 성능 배치0, 본학습0, 기기/ADB/실측0. 총20,000환경 중19,989회, 단계2의512환경 중501회가 남았다. 모델 전환으로 소비를 초기화하지 않는다.
- 최초 수집 관련 별도 commit 이후 HEAD `e73d6e956587a75f1129882591473664b2f78895`에서 작업했다. 이번 파일은 미커밋이다. 기존13개 의존 소스/모형 hash 검사를 통과하고 사용자 파일·다른 worktree를 보존했다.

[campaign.json](campaign.json)은 전체 예산과 보호 파일, [implementation_registration.json](implementation_registration.json)은 현재 실행 소스와 핵심식, [fixture_summary.json](fixture_summary.json)은 최신5사례의 원 지표를 보존한다. fixture 비용값을 본 성능 결과처럼 순위화하지 않는다. ignored `output/reserved_thermal_20261008_v1/`에는 원 gzip ledger·등록1/2/3·누적 실행 장부·실패가 있다.

## 실행 및 현재 gate

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
# 읽기 전용 등록/모형/소비 검사. 환경 실행0.
python -B -m tools.d1_reserved_thermal_study check
python -B -m tools.d1_reserved_thermal_study status
# 검증 재실행은5fixture 환경을 추가 소비한다.
python -B -m unittest tools.test_d1_reserved_thermal tools.test_d1_joint_queue_area -v
```

기존 CLI는 검토 파일이 없어서0추가 소비로 차단됐다. 현재는 [검토 파일](astra_review.json)의 `REVISE_BEFORE_RUN` 때문에 환경 시작 전에 거부한다. pilot 배치 실행기와 임시 경로의 gate 검증은 Sol 보완에서 완성했으며, 현재 소스/명세의 최종 Astra 확인을 기다린다. 실행 범위와 새 근거는 [SOL_REPAIR.md](SOL_REPAIR.md)를 따른다.

## 검토 전에 사용한 인계 기록

다음 문구로 최초 Astra 검토를 요청했고 현재 완료했다. [계획](../../RESERVED_THERMAL_STAGE_PLAN_20261008.md)의 “임의 새 여유 비율·허용 오차가 필요하면 … Astra 설계 검토로 먼저 인계” 및 “핵심 예약/J 갱신식의 새 선택이 필요하면 성능 배치 전 검토” 경계에 따른 기록이다. Sol 보완도 완료했으며 현재 다음 모델은 SOL_REPAIR.md의 Astra다.

> RESERVED-THERMAL-01 단계2 구현안과 docs/results/reserved_thermal_01/README.md를 검토해. 최초 EFT 완료 cap과 signed arrival energy credit 식이 연구 목표에 맞는지 판정하고 정확한 식을 고정해. 현재 11/512환경·본학습0이고 48조건 pilot은 미실행이다. RL을 바로 시작하지 말고, 수정/동결 후 Sol이 단계2 pilot을 마무리하도록 다음 지시를 알려줘.
