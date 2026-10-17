# 여기서 S26 작업을 재개한다

최신 정본: **MULTI001_G004 3240환경·전수감사·분석·화면 검증 완료, 정책 우위/물리 예측 타당성 미입증**. [결과·AP 외삽 경계](MULTIRESOURCE_COMPARISON_KO.md), [재개·파일 지도](docs/G004_HANDOFF_KO.md). 새 RL0.

## 먼저 확인

1. 이 폴더의 AGENTS와 [STATUS](STATUS.md), [G004 인계](docs/G004_HANDOFF_KO.md), [전체 결과](MULTIRESOURCE_COMPARISON_KO.md)를 읽고 Git HEAD/CORE_MANIFEST와 대조한다.
2. 같은 PC의 정본은 `C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/S26-MULTIRESOURCE-20261017-G004`, 출력은 `C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/S26-MULTIRESOURCE-20261017-G004`다. 현재 CONTINUE와 실제 PID/명령/원장을 확인한다. 완료 생산/감사를 다시 실행하지 않는다.
3. 다른 PC에서는 data/MULTI_ARCHIVES.json에 따라 원장/raw/연결 의존성을 복원한다. 복제본은 추가 예산을 주지 않는다.

## 저장 결과만 확인하는 명령

```sh
node cli/s26.cjs verify
node cli/s26.cjs replay --comparison multiresource-v1 --capacity 3 --model CENTRAL
node cli/s26.cjs serve --view latest
node scripts/restore-multi.cjs --manifest data/MULTI_ARCHIVES.json
```

새 환경/NN/fit/RL을 만들지 않는다. source/MULTI001_G004의 생산 파이프라인 재실행은 금지한다. 현재 수정은 새 source/output/DEV/평가 계보에서 진행한다.

## 현재 판단

기존·신규 실측을 하나의 시간·AP·API전력 엔진에 연결했고3자원/공유CPU 경로와 상태 변화가 구현됐다. ATC는 대부분 EDF와 같으며, 큰 FIFO 차이는 CPU 서비스 가정과 AP 외삽에 의존한다. 3슬롯 CENTRAL/HIGH의 모든 예측peak는 AP 보정표본 최대46.6℃를 넘는다. 이를 실제 절감으로 채택하지 않는다. 엔진 보완 검증 전 새 RL0 유지.

고정 긴급0.8초/일반2초·전체128분모·전량완료 우선, 같은 자원/정보/기한 비교를 유지한다. 다른A24/37/38/SLO70/중지27·원자료/WIP/원V2gate/PAUSED자동화를 보존한다. 일회 재개 예약을 반복으로 확장하지 않는다.

## 어디에 있는가

- 최신 엔진/정책/packet/모형: experiments/multiresource_v1/
- raw/prepared/원장/실패/입력/소스 전체 연결: data/MULTI_ARCHIVES.json 및 G004 인계
- 모든조건/쌍/서비스/모형반전 CSV: experiments/multiresource_v1/results/
- 화면/QA/전수감사/지원범위 proof: experiments/multiresource_v1/evidence/
- 과거 STATE/FAIR/RARL/IE·원실측: 기존 하위 폴더와 data/ARCHIVES.json. 이전 결과를 G004 결과로 인용하지 않는다.
