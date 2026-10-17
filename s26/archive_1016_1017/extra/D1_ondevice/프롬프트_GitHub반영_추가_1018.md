# 프롬프트 — GitHub 반영 추가분 (2026-10-18 00시)

> 영훈: `프롬프트_GitHub반영_1016_1017.md` 세션이 **push 까지 끝난 뒤** PC Claude Code 에 붙여 넣는다 →
> `C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\프롬프트_GitHub반영_추가_1018.md 읽고 그대로 끝까지 진행해`
> 그 세션이 아직 4단계 (커밋) 전이면, 이 내용을 그 세션 창에 "추가분도 같은 커밋에 넣어" 로 붙여도 된다.

## 0. 목적

1차 보관 (`s26-archive-1017`, T0 = 2026-10-17 23:54) 뒤에 생긴 것을 **같은 브랜치에 커밋 1개 더** 로 올린다.

## 1. 올릴 것

| 원본 (OneDrive `산공학회\` 기준) | 레포 경로 |
|---|---|
| `D1_ondevice\sim\out_cpu_whatif_1017\` 전부 (6 파일 · what-if 코드 2 · 출력 2 · README · SHA256SUMS) | `s26/archive_1016_1017/1017_sim/cpu_whatif_1017/` |
| `D1_ondevice\프롬프트_GitHub반영_추가_1018.md` (이 파일) | `s26/archive_1016_1017/extra/` |
| T0 (23:54) 뒤에 생기거나 바뀐 `D1_ondevice\` 의 결과물 · 문서 · 코드 · 프롬프트 (`archive_1017.py` 의 자동 발견 규칙으로 찾음 · `--until` 은 이 세션 시작 시각) | 같은 규칙의 위치 |

- **제외 (그대로)**: M9 측정이 쓰는 `sim\out_m9\` 와 `D1Check_m6` (측정 중일 수 있음 — M9 끝난 뒤 따로) · 임시 · 로그 · 개인 파일 · APK · 모델 · 50 MB 초과.

## 2. 순서

1. 원장 `D1_ondevice\push_1017\ledger.txt` 에 이어 쓴다. 1차 push 결과 (원격 `s26-archive-1017` SHA) 를 `git ls-remote` 로 확인 · 기록. 1차가 push 안 됐으면 멈추고 그 세션을 먼저 끝낸다 (질문 목록).
2. `C:\Users\rhoyo\AndroidStudioProjects\D1Check_push1017` 에서 `s26-archive-1017` 그대로 (새 클론 안 만듦).
3. 복사 → `out_cpu_whatif_1017\SHA256SUMS.txt` 재계산과 대조 → PAT 검사 (1차와 같은 정규식) → `MANIFEST` · `SHA256SUMS.txt` (보관 폴더 최상위) 에 추가분 줄 덧붙임.
4. `git add -f -- s26/archive_1016_1017` → `git diff --cached --name-only` 전부 `s26/archive_1016_1017/` 인지 확인 → 커밋 `s26: 10/17 보관 추가분 (CPU what-if · T0 뒤 문서)`.
5. push 전 검사 (1차 5단계와 같음) → `git push origin s26-archive-1017` (`--force` 금지) → `ls-remote` 대조.
6. 보고 = `D1_ondevice\push_1017\작업결과_1017_GitHub반영.md` 끝에 "## 추가분 (10/18)" 절: 커밋 SHA · 파일 수 · 뺀 것 · 질문.

## 3. GitHub 에 못 올리는 것 (보고서에 그대로 적는다)

다음 10/17 클라우드 실행의 원자료는 그 세션 작업 공간에만 있고 PC 에 없다 → 결과 문서 (프로젝트 문서 사본) 만 보관: A24 시뮬 v1 · S26 시뮬 v1 `all.jsonl` · 방법론 설정탐색 · 우위조건 A24 쪽 · 과부하 작은조정 · A24 규칙 이식. (CPU what-if 는 이번 추가분으로 코드 · 출력 보관됨.)
