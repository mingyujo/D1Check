# 기한 예약과 열 분산 규칙 보완 결과

2026-10-08 KST · RESERVED-THERMAL-01 단계2 · Sol 구현과 검증

후속 최종 검토: **PROCEED_PILOT**. [최종 판정과 다음 Sol 입력](ASTRA_FINAL_REVIEW.md)에 따라48신규 환경만 실행할 수 있다. 아래의 검토 대기/차단 표현은 보완 완료 당시 이력이며 현재 판정은 `astra_review.json`을 따른다. 이번 검토 추가환경0, 누적21 유지.

**Astra가 요구한 보완과 pilot 실행기 준비를 완료했다. 다음은 Astra의 최종 소스 확인이다.** 성능 pilot은 아직0회다. 43개 검증이 통과했고 실제 엔진 fixture10회를 추가했다. 누적21환경(성공20/과거 실패1), 본학습·기기는0이다. 정책 우수성은 아직 판정하지 않는다.

## 반영한 변경

| Astra 조건 | 구현과 검증 |
|---|---|
| 후속 일정의 시각 보존 | `finish_retained`가 각 미실행 작업의 절대 시작 하한을 보존한다. 반복 callback·빠른 lane 반환·새 요청에도 간격을 유지하고, 충돌/시각 만료는 별도 기록한다. 실제 사용 중 lane과 long-context cap 검사를 유지한다. |
| WAIT 한도 유지 | 저장된 목표시각과 최대0.25초 wake-up을 분리한다. 도착 후2초의 의도적 대기를 확대하지 않는다. cap·예산은 새 계획 선택으로 재발행하지 않는다. |
| 예약/에너지/탐색 실패 분리 | 후보별 cap 탈락·J 탈락·공통창 불가, callback fallback, 요청별 실제 cap 초과와 원래 기한 실패를 따로 저장한다. 빈 큐에서도 관측 overrun을 기록한다. |
| 최종 장부 | 최종 B·공통120초 J·잔액·충족 여부·전량/부분작업 여부를 기록한다. retrospective ledger 감사는 온라인 결정에 입력하지 않는다. 누적 소비와 잔여 idle 비용도 보존한다. |
| 예측 불가 도착 | 최초 관측시각·pending·실제 발행시각을 기록한다. 알려지지 않은 잔여 비용은0으로 넣지 않는다. |
| 설계 개정과 검토 gate | 최초 campaign/등록1–3/실패 장부를 보존했다. 검토 원본을 별도 보관하고 부모 SHA가 있는 설계revision2·구현revision4/5를 추가했다. 식 변경과 오래된 active 등록을 거부한다. 원 상태가 없으면 공유 campaign을 보고 예산 재생성을 거부하며 owner가 있으면 등록을 바꾸지 않는다. gate는 임시 경로에서 파일 부재/수정 필요/해시 불일치/일치 허가를 검증한다. |
| 432행 재사용 | 완료된 Band/Triton 실행 바인딩·원 설정/소스·입력·결과 hash·요청 수·48조건×9정책의 정확한 집합을 대조했다. 행별 원 파일SHA와 원 origin을 보존하는 재사용 manifest를 작성했다. |
| pilot 구현 | 48신규 환경의 시작 전 차감·항목별 원본 저장·완료 receipt·재개 캐시·480행 저장 경로를 구현했다. owner는 자기 PID의 lock만 해제한다. 검토 거부 시 시작 전 차단한다. 실행 전 소스 보완은 pilot 등록revision1/2로 보존하며, 성능 시작 뒤에는 manifest를 교체하지 않는다. |

최초 완료 cap, signed arrival credit, AP 우선 선택, 64확장/beam8/깊이4 상한은 유지했다. [검토서](ASTRA_REVIEW.md)의 보완 범위 밖인 일반 cap 완화·새 물리 계수·그림자 EFT·학습을 추가하지 않았다.

## 검증과 소비

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_reserved_thermal tools.test_d1_joint_queue_area -v
```

새 규칙38개와 기존 AP면적/경계5개, **43개 PASS**다. 최초 환경 없는28개 검사, 보완40개 검사도 통과했으며 중복 합산하지 않는다. 40개 통과 뒤 원 상태 소실/owner 보호와 성능 전 manifest 개정 검증3개를 추가하여43개로 다시 확인했다. 두 전체 검증에서 각각5fixture 환경을 소비했다. 위 전체 명령은5fixture 환경을 시작하므로 수정 없이 반복 실행하지 않는다.

- 최신5사례15예정 요청 모두 완료·기한 충족, 실제 lane 중복 없음.
- 저장 간격0.25초 보존, 고정 일정의 `누적 J + 남은 J` 일치, 과거 입력이 같은 모든 callback의 미래 suffix 독립성을 확인했다.
- signed credit의 양/음 산술은 계측 값을 주입한 단위검증이다. 물리적 에너지 개선 사례로 쓰지 않는다.
- pilot의48항목 저장/재개/변조된 캐시 거부는 엔진·회계를 mock한 격리 I/O 검증이다. **48환경 성능 실행으로 세지 않는다.** 실제 정책 실행은5fixture뿐이다.
- long-context overrun fixture의 최종 잔액은 약 **−0.000976205149 J**, 예산 충족은false로 기록한다. mixed/overrun의 내부 cap 위반1건은 원래 서비스 기한 위반과 구분한다. 이는 검증 사례의 모형 장부이며 실기기 효과가 아니다.

누적 실제21환경은 최초11+이번10이다. 총61예정 요청, 성공 환경에서60완료이며 최초 실패1환경의1요청 완료 receipt는 없다. 남은 전체19,979·단계2 491환경이다. 소비 초기화·원 실패 삭제는 없다. 이번 본학습·기기/ADB/실측·commit/push는0이다.

[새 검증 바인딩](verification_repair.json), [최신5fixture 행](fixture_summary.json), [현재 코드 등록](implementation_registration.json), [pilot manifest](pilot_manifest.json), [재사용 근거](reuse_manifest.json)를 보존했다. 원 [verification.json](verification.json)과 Astra 반례는 그대로 남겼다.

`projections`/`projection_host_s`는 새 adapter의 완성 mean 계획 비용/온도 scoring 호출과 PC 소요시간이다. 모든 `place` 호출이나 legacy reference ABI 계산의 횟수로 해석하지 않는다. callback 전체 시간은 별도 저장한다. AP의 최적화 격자와 기존 비교 격자 차이도 pilot manifest에 명시했다.

## 현재 실행 경로

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
# 모두 환경 시작0인 검사/등록 정보 조회다.
python -B -m tools.d1_reserved_thermal_study check
python -B -m tools.d1_reserved_thermal_study status
python -B -m tools.d1_reserved_thermal_study prepare-pilot
# 최종 Astra 허가 전에는 시작 전에 거부된다.
python -B -m tools.d1_reserved_thermal_study pilot
```

pilot은 현재 `astra_review.json`의 `REVISE_BEFORE_RUN` 때문에 차단된다. 현재 `source_hashes`와 `specification()`에 일치하는 최종 검토가 있어야 실행된다. 캐시는 같은 소스/설정/입력 binding, 완료 receipt의 gzip SHA, 원 요청/lane 감사가 일치할 때만 재사용한다. 원본은 `output/reserved_thermal_20261008_v1/`의 자기 경로에만 저장한다.

pilot manifest는48조건×10정책=480행, 신규48/재사용432로 고정했다. 대표는 seed610810001·mean·queue/sustained다. 완료된 기존 공개 자료를 사용한 개발 pilot이며 새 holdout이 아니다. 성능 CSV·전체 그림·화면은 pilot/최종 평가 이후 생성한다.

## Astra에 전달할 입력

> RESERVED-THERMAL-01의 SOL_REPAIR.md와 verification_repair.json을 검토해. 저장 일정 하한·장부/원인 분리·설계revision·pilot 실행기가 ASTRA_REVIEW.md의 수정 계약을 충족하는지 확인해. 현재 누적21/512환경, 43검증 PASS, 성능 pilot/본학습/기기0이다. 코드와 pilot/reuse manifest가 적합하면 현재 source_hashes·design에 바인딩된 PROCEED_PILOT 판정을 남겨서 Sol이48신규 환경/480논리행 pilot만 실행하도록 해. 아직 RL을 허가하지 마.

현재 `astra_review.json`은 검토 전 코드에 대한 수정 판정 기록이다. 새 PASS나 실행 허가로 덮어쓰지 않았다. 원 검토 JSON은 설계revision의 원본 SHA로 local `design_reviews`에도 보존했다. 기본 엔진·정책·동결 모형·strict·experiment_ready=false·사용자 파일·다른 worktree·별도 history recovery 작업은 보존했다.

최종 등록/검증 HEAD는 `a081d55e9cc9d1a732bee9bed9e1ca8535244b29`다. 병행한 history recovery 작업의 별도 commit으로 HEAD가 전진했고 이번18소스 바인딩과 보호13소스는 일치했다. 이번 코드와 문서는 미커밋·미push이며, 다른 작업의 commit을 이번 보완 완료 commit으로 보고하지 않는다.
