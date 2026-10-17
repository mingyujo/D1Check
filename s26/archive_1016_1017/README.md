# 10/16 · 10/17 결과물 보관 (S26 · 영훈 쪽)

이 폴더는 2026-10-16 · 10-17 에 만든 결과물 가운데 GitHub 에 없던 것을 한곳에 모은 것이다.
- 원본 = 영훈 PC OneDrive `산공학회\` 의 파일이다. 파일마다 원본 경로와 sha256 은 `MANIFEST.tsv` 에 있다.
- 내용은 고치지 않고 복사만 했다. `.gitattributes` 의 `* -text` 때문에 줄바꿈도 원본 바이트 그대로다.
- 기준 커밋 = `s26-m8` `1b3454c8a` (M8-B CONFIRM R21 R3 기록, 10/16 09:46). 이 위에 보관 커밋 1개만 얹었다.
- 측정 · 계산 · 재실행은 0 이다.

## 폴더

| 폴더 | 내용 | 실행 |
|---|---|---|
| `1016_M8B_R21/` | M8-B CONFIRM R21 의 보고서 `작업결과_1016_M8B_CONFIRM_R21.md` · 조민규 답 (10/16) · 프롬프트 2개 · 최종 원장 `out_m8/prep_ledger.txt` · 질문 #21~#24 `out_m8/questions_for_영훈.md` · 블록 묶음 zip 3개 `out_m8/bundles/` (`622cc822…` · `0986337c…` · `5dedc907…`) | PC Claude Code · 폰 실측 |
| `1017_sim/` | 10/17 시뮬 결과 전부. 아래 표 참고 | Cowork 클라우드 · 폰 0 |
| `1017_project_docs/` | claude.ai 프로젝트 문서 `claude/1017_*.md` 16개 사본 + `00_목록.md` (작성 시각 · 원자료 위치) | — |
| `extra/` | 10/16 00:00 뒤 수정됐지만 위 목록에 없던 파일 (자동 발견 · 원래 상대 경로 그대로). 없으면 폴더가 없다 | — |
| `MANIFEST.tsv` · `SHA256SUMS.txt` · `PAT_SCAN.txt` | 원본 ↔ 보관 대조 · 해시 · 무선 adb 주소 / 시리얼 검사 (zip · tgz 안까지) | — |

### `1017_sim/` 안

| 경로 | 실험 | 원 결과 문서 (`1017_project_docs/`) |
|---|---|---|
| `S26_SIM_v1/` | S26 시뮬레이터 측정 v1 · 등록 · 1,488회 표 | `1017_S26시뮬_측정결과_v1.md` |
| `S26_RL이식_가능성검토_1017.md` · `sim/rl_port_proto_1017/` | A24 롤링+ATC+RL 의 S26 이식 검토 · 시제품 (`drive.py` · `rl_bridge.cjs`) | `1017_S26_RL이식_가능성검토.md` |
| `sim/out_s26rl_1017/` | S26 RL (A24 PPO 무수정 이식, 3 seed × 512) · 등록 · 판정 · 원자료 · 체크포인트 | `1017_S26_RL실험_결과.md` |
| `sim/out_vd_1017/` | 가상 기기 6개 (NPU 감속 × GPU+NPU 동시) · `engine/` | `1017_가상기기_NPU쏠림없는조건_결과.md` |
| `가상기기_통합분석_1017.md` | E0 ~ E5 통합 재계산 · 결론 부합도 | `1017_가상기기_통합분석_결론부합도.md` |
| `zips/가상기기_전체_1017/` | E1E2 (스로틀 k · 잔차 RL) · E3 (NPU 열 취약) · E4 · E0 · E5 · `00_통합분석/` (`UNIFIED.csv` · `unify.py`) | 스로틀강도 · 가상기기_RL · NPU열취약 · 통합분석 |
| `zips/결과_1017_전체/` | 위 out_s26rl · out_vd · rl_port_proto 의 묶음판 | — |
| `zips/share_minkyu_1017/` · `zips/share_minkyu_1017_v2/` | 조민규 공유용 재현 묶음 (E1E2 · E3) | 가상기기_RL · NPU열취약 |
| `프롬프트/` | `프롬프트_시뮬설정탐색_1017.md` (PC 미실행) · `프롬프트_M9_병렬짝측정_1017.md` (M9 는 자기 브랜치 `s26-m9par` 로 따로 올린다) | — |

`zips/` 는 OneDrive 의 zip 을 푼 것이다. zip 파일 자체는 올리지 않았고, 원 zip 의 sha256 은 `MANIFEST.tsv` 의 종류 `zip원본` 줄에 있다.
- `결과_1017_전체.zip` `8fe1b10b…`
- `가상기기_전체_1017.zip` `75c6efa5…`
- `share_minkyu_1017.zip` `308f1ee0…`
- `share_minkyu_1017_v2.zip` `a4d7ba29…`

같은 파일이 여러 곳에 있다 (예: `checkpoints.tgz`). git 은 같은 내용을 한 번만 저장한다.

## 읽을 때 지킬 것

- `1017_sim/` 의 수치는 전부 **[시뮬 예측]** 이다. 폰 실측이 아니다.
- **가상 기기**는 실측 기반 모형을 확장한 가상 시뮬레이션이다. S26 성능이 아니다.
- 엔진은 조민규 브랜치의 것이다.
  - S26: `codex/s26-simulator-handoff-20261016` (`d23fbd1`)
  - A24: `codex/a24-simulator-handoff-20261016` (`9e04b4b`)
- `engine/` 폴더는 그 엔진 파일을 수정한 사본이다. 원 세션 기록에 따르면 스위치를 끄면 원본과 비트가 같다. `*.diff` 는 원본 대비 바뀐 부분이다.
- 코드 안의 `/home/claude/...` 경로는 클라우드 실행 경로가 그대로 남은 것이다. PC 에서 재현하려면 경로를 바꿔야 한다.
- `checkpoints.tgz` 는 S26 RL 실험의 PyTorch 체크포인트다 (3 seed).
- `out_s26rl_1017/` 은 A24 의 `policy_bridge.py` · `learner.py` 를 `A24_ROOT` 에서 불러온다. 이 두 파일은 이 폴더에 없다 (조민규 A24 브랜치에 있음).

## 레포에 이미 있어서 넣지 않은 것

- `CONFIRM_FREEZE_S26_R21_v1/v2.json` = 레포 `s26/results/m8_prep/CONFIRM_FREEZE_M8_R21_v1/v2.json` (git blob 이 같다)
- R21 블록 readout = 레포 `s26/results/m8_prep/confirm_r21/`
- `r21/` 의 에너지 적격성 · manifest 는 blob 이 같으면 넣지 않았다. 판정 결과는 `MANIFEST.tsv` 의 종류 `skip` 줄에 있다.

## PC 에 원자료가 없어서 못 넣은 것 (클라우드 세션 안에만 있었음)

아래 항목은 결과 문서(`1017_project_docs/`)만 있다.

| 문서 | 없는 것 |
|---|---|
| `1017_A24시뮬_측정결과_v1.md` | `a24_all.jsonl` `a98e89df…` · `a24_sim_runs_1017.csv` `0c71500b…` · `PREREG_A24_SIM_1017.md` `23ce83c5…` |
| `1017_S26시뮬_측정결과_v1.md` | 원자료 `all.jsonl` `d4410454…` (표 csv 와 등록은 있음) |
| `1017_시뮬방법론검토_설정탐색.md` | 설정 탐색 실행 코드 · 원자료 |
| `1017_우리규칙_우위조건_탐색.md` | A24 확인 16조건 원자료 · 코드 (S26 E0 는 `zips/가상기기_전체_1017/…/참고_실측모형/E0` 에 있음) |
| `1017_과부하_작은조정_결과.md` | `PREREG_OVERLOAD_SMALLADJ_1017.md` `7f251fb1…` · 확인 원자료 `87417d30…` · `run6.cjs` · `ocanal.py` |
| `1017_CPU다중스레드측정_타당성평가.md` | what-if 실행 코드 · 출력 |
| `1017_A24규칙_S26이식_결과.md` | `PREREG_A24PORT_1017.md` `6c480330…` · `atc_a24.cjs` |

## 일부러 뺀 것

- `CLAUDE.md`: Claude 지침 파일이고, 무선 adb 주소와 시리얼이 들어 있다.
- `keepawake*` 로그 · `.stop` 파일.
- `sim/out_m8/m8_confirm_r21_block*_stage/`: 묶음 zip 을 푼 내용과 같다.
- `sim/out_m9/`: M9 측정 결과는 자기 브랜치 `s26-m9par` 로 올린다.
