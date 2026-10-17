# G004 현재 정본과 복원 입구

관측 시각: 2026-10-17T12:54:17.780Z. **계획만 있는 인계가 아니다.** 새 CPU/GPU/NPU 슬롯·공유 CPU·열 속도 엔진의 실행/소스/봉인 입력/원장/raw/복구 기록을 포함한다. G004 계산·화면 단계는 완료됐으며 예측 타당성/정책 우위와 새 RL은 미완료다. 중간 스냅샷과 최종 보존 manifest를 구분한다.

## 실제 완료와 미완료

- G004 P0 72 + DEV 576 + fresh EVAL 2,592 = **3,240 START/PREPARED/COMPLETE**. 새 RL 0.
- 독립 전수 감사 **44,694,517검사 PASS**. 저장 활동 3,240건 비용·진행률 재계산, 공개 입력/행동 재생 완료. 실기기 물리 정확도 인증은 아니다.
- 분석 PASS: 전체 조건/서비스 수준/손해/모형 반전/조건부 재표집 CI. HTML 생성 완료. 최초 QA의 브라우저 의존성/집계기대값 실패는 보존했고, 새 파생 QA V5와3화면 직접 검토는 완료했다. AP 지원 범위 밖 예측을 표시하는 V2 화면이 최신이다.
- 처음 2,711건 뒤 다음 START 기록을 열기 전 권한 오류로 중단. 저장된 2,711건 전수 검산 뒤 **봉인된 미시작 529건만** 원 소스/seed/DEV 동결로 이어 완료했다. 소비된 identity를 재수집하지 않았다. 첨부의 2,731은 선행 세대 P0 20 + G004 2,711을 합친 당시 수이며 현재 G004 완료 수는 3,240이다.
- G001~G003의 P0 20건/수치 단계 실패3과 G004 운영 중단1/QA 실패를 보존했다. 실패가 전혀 없었다고 보고하지 않는다.

## 같은 PC에서 어디를 볼까

- 작업 정본: `C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/S26-MULTIRESOURCE-20261017-G004`의 `CONTINUE.md`.
- 결과 정본: `C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/S26-MULTIRESOURCE-20261017-G004`의 `CONTINUE.json`. 오래된 PID/상태가 있으면 이 인계 시점의 실제 종료/영수증과 대조한다.
- 동결 엔진: work의 `source_generations/MULTI001_G004/`. 원 `prepare`/생산 파이프라인은 재실행하지 않는다.
- START/terminal 원장은 outputs 루트의 `receipts.jsonl`, 설정/raw/prepared와 행은 `PRODUCTION/`이다. 완료 감사는 그 안 `AUDIT_V1/FINAL_AUDIT.json`.
- 복구: `RECOVERY_UNSTARTED_20261017/REGISTRATION_V4.json`와 `RUNTIME_V4/RECOVERY_PROOF.json`.
- 최신 후속: `ANALYSIS_V1/`, `WEB_VIEW_V2/`, `BROWSER_QA_V5/`, `SUPPORT_DIAGNOSTIC_V1/`. 최초 `WEB_VIEW_V1/`·`BROWSER_QA_V1/`·`POSTRUN_DISPATCH_RUNTIME_V1/FAILURE.json`도 이력으로 보존한다.

## GitHub 복제본에서 파일 찾기

| 내용 | 이 폴더 안 경로 |
|---|---|
| 소스20개·입력·보정모형 | `experiments/multiresource_v1/source/MULTI001_G004/`, `PACKET.json.gz`, `calibration/` |
| 최신 관측/핵심 증거 | `experiments/multiresource_v1/STATUS.json`, `evidence/` — INTERIM_STATUS/interim_evidence는 이전 중간본 |
| 전체 work/output·연결 의존성/원장 | `data/MULTI_ARCHIVES.json`의 별도 Release 자산 |
| 관측·가정·수치 검증 범위 | `experiments/multiresource_v1/README.md`, `docs/MULTIRESOURCE_MODEL_KO.md` |
| 기존 실측/과거 정책 아카이브 | `data/ARCHIVES.json` — 기존 Release 보존 |

Node20 이상으로 `s26_simulator` 안에서:

```sh
node cli/s26.cjs verify
node scripts/restore-multi.cjs --manifest data/MULTI_ARCHIVES.json --filter work/S26-MULTIRESOURCE-20261017-G004
node scripts/restore-multi.cjs --manifest data/MULTI_ARCHIVES.json --filter outputs/S26-MULTIRESOURCE-20261017-G004
# 필요한 연결 의존성/원장을 포함한 전체 복원
node scripts/restore-multi.cjs --manifest data/MULTI_ARCHIVES.json
```

복원 위치는 `archive/multiresource/`이며 원PC 폴더를 덮지 않는다. `.cache/s26-multi-final-catalog.json.gz` 카탈로그의 각 `path/source/sha256`가 복원 상대경로와 원 절대경로를 연결한다. `connected_dependencies`, `calibration_dependencies`, `connected_ledgers`도 포함하며 같은 바이트는 내용 SHA로 중복 저장을 줄였다. 최종 카탈로그17,038개 파일, pack 약1.932GB, 복원 데이터 약2.060GB이며 캐시/복원에 더해8GiB 여유를 검사한다. 원PC 밖에서는 역사적 절대경로 명령을 그대로 실행하지 말고 새 호스트 경로/공동 잠금/예산을 별도 운영 등록한다.

## 예측/비교 해석

원 처리단계 벡터8,636개와 기존·신규228세션(AP210/전력209 적격)을 연결했다. 별도56fit/OOF 감사 포함. pair/triple·CPU 서비스 prefix는 명시적 전이 가정이며 실제3자원 실측 검증이 아니다. FIFO/EDF/ATC에 동일 롤링 배정/자원 후보/정보/긴급.8·일반2초/128분모를 적용한다. 작업 종류×우선순위가 결합된 합성 부하라는 한계와 구조모형별 손해를 함께 읽는다. `NO_THERMAL_HARM`은 후보명이며 실제 열 무손해 보장이 아니다.

최신 확인 예약124,838/137,712. Multi3328 공유예약에서 선행20+G0043240=3260소비/68미사용. 복제본은 새 예산을 부여하지 않는다. 원 V2 EP814/gate, 다른A24/37/38/SLO70/중지27/WIP/PAUSED자동화를 보존한다. 실제 worker/명령/생성/원장부터 확인하고 중복 실행하지 않는다.


최신 판독: [MULTIRESOURCE_COMPARISON_KO](../MULTIRESOURCE_COMPARISON_KO.md). 저장 분석/원수치는 그대로, AP26~46.6℃ 지원 범위 밖 표시만 파생뷰V2에서 추가했다. 최종아카이브는 검증된중간pack을재사용하고감사/뷰/최신인계의새바이트만추가pack으로저장한다. 두릴리스URL은manifest가연결하며원pack재압축/원파일이동0이다.
