# 단계2 최종 코드와 pilot 검토

2026-10-08 KST · RESERVED-THERMAL-01 · 판정 **PROCEED_PILOT**

현재 구현revision5·설계revision2·pilot등록2로 고정한 **48신규 환경 + 432재사용 = 480논리행**의 개발 pilot을 허용한다. 정책 채택·Band/Triton 대비 우월성·RL 실행 허가가 아니다. 사용자가 Sol로 전환한 뒤 실행하며 이번 검토에서는 실행하지 않았다.

## 검토 결과

이전 차단 사유는 해소됐다. `finish_retained`는 저장 일정의 각 절대 시작 하한을 유지하고 만료·충돌을 기록한다. 예약 cap은 최초 발행 이후 완화하지 않으며 신규 도착의 signed J credit만 같은 관측 상태에서 계산한다. 후보 탈락·탐색 실패·실제 요청 cap 초과·최종 J 잔액은 별도로 보존한다. overrun 중 처음 본 요청의 pending/발행 시점도 구분한다.

최초 campaign과 실패 장부를 유지하는 설계 개정, 실행 전 차감, 소스/입력 고정, 배타 owner, 완료 receipt와 항목 SHA를 확인하는 재개 경로를 검토했다. 기존 보호13소스·현재18소스·검증 기록·pilot/reuse manifest·48조건/432행 집합을 읽기 전용으로 다시 확인해 일치했다. 저장된 최종5fixture도 확인했다. 기존 43검증 PASS의 해시는 현재 코드와 같으며 이번에 환경을 사용하는 전체 suite를 반복하지 않았다.

## 남은 지적과 pilot 처리 조건

1. **경미한 집계 누락:** `d1_reserved_thermal.py`의 `terminal_audit`에서 `fallback_callbacks`는 `self.records`의 탐색 실패만 센다. `decide`가 `reserved_observed_overrun_EFT`로 조기 반환한 판단은 포함되지 않는다. 저장 fixture mixed는 15+overrun1, overrun은 16+overrun1이다. 원본 `result.decisions`에 두 reason이 남아 있으므로 성능 실행을 막는 원자료 손실은 아니다. Sol은 동결 정책 코드를 바꾸지 않고 후처리에서 `reserved_no_admitted_calendar_EFT`와 `reserved_observed_overrun_EFT`를 각각 집계하고 합계를 보고한다. 기존 열은 탐색 실패 횟수로 명시한다. `book.breaks`는 중복 제거된 사건이므로 callback 총계로 쓰지 않는다.
2. **예약과 예산은 절대 보장이 아니다:** cap의 long-context는 WCET가 아니며 J credit은 경로 의존 모형 장부다. 별도 EFT/Band 실행 대비 에너지 비증가를 보장하지 않는다. 최신 overrun fixture의 최종 잔액 −0.000976205149J와 내부 cap 초과는 그대로 공개한다. 원래 서비스 기한과 내부 예약을 구분한다.
3. **제한 탐색의 음성 결과 해석:** 64확장/beam8/깊이4는 상한이다. 모든 조합·깊이4 도달을 보장하지 않는다. 후보 적격 수·도달 깊이·탐색 한도·fallback을 함께 보고, 개선 후보가 없다는 결과를 개선 불가능 증명으로 쓰지 않는다.
4. **실행 중 중단 한계:** 재개는 저장 완료된 항목과 receipt가 일치할 때만 재사용한다. 파일 저장과 receipt 사이의 강제 종료는 자동 복구하지 않는다. 중단 시 기존 시작 소비를 유지하고 증거를 확인하며 파일/owner 삭제로 조용히 재시작하지 않는다.
5. **모형 경계:** AP 최적화의 전환점 포함 격자와 비교용 공통1초 격자를 구분한다. PC callback 시간은 기록하되 기기 제어 비용으로 환산하지 않는다. AP는 표면온도가 아니며 제어 비용0은 기존 모형 가정이다.

## Sol 실행 범위와 인계

- 48조건은 기존 공개 개발/회귀 자료이며 독립 holdout이 아니다. Triton5설정·Band whole-request adapter·EFT·기존 자체2규칙·신규1규칙을 모두 보존한다.
- 대표 trace는 등록된 seed610810001/mean/queue·sustained를 유지한다. 결과를 보고 조건·cap·예산식·계수·비교군을 변경하지 않는다.
- 먼저 완료량/미완료·원래 기한·긴급P95를 비교하고, 같은 서비스 요구를 만족할 때 APpeak/J를 해석한다. partial J와 AP 계산 불가를 구분한다. 내부 예약/예산 실패와 기준정책 대비 성능 실패도 구분한다.
- 누적21환경에서 시작한다. 오류 없이48회를 마치면 누적69, 단계2 잔여443, 전체 잔여19,931이다. 실패도 차감하며 단계2 상한512·총20,000을 유지한다. 본학습/기기/ADB0.
- 결과 CSV·대표 실행 기록·진단 요약·판단 비용·누적 소비를 보존하고 Astra 단계3으로 인계한다. RL 여부와 새 시험 계약은 그때 판정한다. 이번 단계에서 최종 Git 공유까지 완료했다고 보고하지 않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m tools.d1_reserved_thermal_study check
python -B -m tools.d1_reserved_thermal_study pilot
python -B -m tools.d1_reserved_thermal_study status
```

다음 사용자 입력:

> Sol로 단계2의 승인된48조건 pilot을 진행해. ASTRA_FINAL_REVIEW.md의 범위와 진단 집계 지적을 반영하고, 전체480행·원본 기록·비교 요약·누적 소비를 보존한 뒤 Astra 단계3 검토로 인계해. 본학습과 기기 실행은 시작하지 마.

## 검증 대상과 근거

검토 HEAD `a081d55e9cc9d1a732bee9bed9e1ca8535244b29` + 미커밋 코드/문서. 실제 브랜치·두 worktree 대조, owner 없음. 검토 명령은 `python -B -`에서 `check()`, `reference_rows()`, manifest/검증 SHA 동등성, 저장 fixture gzip의 판단 reason/장부를 읽었다. 환경/학습/기기 추가0, 누적21(성공20/과거실패1), pilot0. 사용자 파일·다른 worktree·별도 history 작업·기본 정책·strict·experiment_ready=false는 그대로다.

정확한 UTC·소스18 SHA·manifest SHA·소비는 [최종 검토 JSON](astra_review.json)에 고정한다. [Sol 검증](verification_repair.json), [pilot](pilot_manifest.json), [재사용](reuse_manifest.json), [초기 검토](ASTRA_REVIEW.md)를 함께 보존한다. 초기 검토 JSON은 `astra_review_initial.json`과 기존 local design_reviews에 보존한다.
