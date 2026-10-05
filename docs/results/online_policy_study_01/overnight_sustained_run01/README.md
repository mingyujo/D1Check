# 192요청 CPU/PAR 확인 결과와 제한 시뮬레이터

[한국어 보고서](../../../ENERGY_THERMAL_OVERNIGHT_RESULTS_20261004.md) · [결과 화면](index.html). 8/8 완료·본1536/warmup64·독립 전이 block. strict=false, policy_winner/accuracy_pass=null, experiment_ready=false. 기존96 확인·개발 계수를 변경하지 않았다.

## 원본 없이 재현

저장소 루트, Python/numpy/matplotlib 기존 환경에서:

```powershell
python -B -m unittest tools.test_d1_sustained_protocol tools.test_d1_arrival_recorded_replay tools.test_d1_sustained_readout
python -B -m tools.d1_sustained_readout predict --bundle docs/results/online_policy_study_01/overnight_sustained_run01 --index 0 --policy CPU_URGENT_ONLINE_V1 --output <새_PC_출력_CPU>
python -B -m tools.d1_sustained_readout predict --bundle docs/results/online_policy_study_01/overnight_sustained_run01 --index 0 --policy B2_PARALLEL_ONLINE_V1 --output <새_PC_출력_PAR>
```

이CLI는미래관측을사용하지않으며ADB/설치/추론0. 이초기의전체120초CPU185.389926J/PAR183.299134J,차이−2.090792J를재현한다. 관측정책우월성값이아니다. `--purpose energy-ap-policy-selection`은차단된다. 다른요청수/도착/작업조합을192모형지원이라고하지않는다.

## 원본으로 전체 판독 재현

```powershell
python -B -m tools.d1_sustained_readout analyze --plan <원본_sustained_confirmation_plan_v1/collection_plan.json> --output <새_PC_평가_경로>
```

필요파일:8세션`validated.json`,`artifacts/{manifest.json,requests.json,progress.jsonl,cleanup.json,common_boundary.json,start_ap.accepted.json}`,세션`thermal.jsonl`,원본`FINAL_RECEIPT.json`·`frozen_collection_plan.json`·host명령client결과/소비기록·원계수. plan의source/pathbinding을보존해야한다. 대용량원본은Git에없음. 원본경로는한국어보고서에명시했다.

## 파일과 판독

- metrics.csv:8세션×A실제일정조건부/B예정도착16행. J0~120초, APcommon35~실제coolingend의유효host표본.
- curves.csv:120개1초J경로와실제APquery시점경로. 없는필드는빈칸이며0채움아님.
- timing.csv/segments.csv:모든1536요청의실제/예측경계·상태. 늦거나누락된요청을삭제하지않음.
- pair_differences.csv:4쌍실제관측차이,초기AP/전력차이. −5.304~+11.682J·평균+1.195J·기술적SD8.069J,미래오차한도/인과효과미판정.
- counterfactual_differences.csv:8초기조건별동결모형의CPU/PAR차이. 실제정책비교와별도.
- model.json:기존frozen정확한bytes(SHA5682082a…);새모형아님. initial_inputs.json:등록입력과부하전AP이력/−20~30초W. 미래전력/온도미포함.
- summary.json/resources.json:판독상태·자료사용·해시. verification.json:8개독립적분/CSV/전체상태/동결검사. execution_summary.json:실제소비/종료를기기식별정보없이보존.
- session_00..07.png:관측/예측누적J·AP·잔차·실제/예측lane. 파랑분류/주황탐지.

rawcurrent=mA조건부·절대정확도미인증. 한창총오차가작아도구간상쇄가능. 일반도착·새온도·처리율스로틀·정밀정책선택은미지원. 향후반복/추가실측자동시작없음.
