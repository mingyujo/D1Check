# 데스크톱 Codex 전달 프롬프트

> **완료 실험 — 다시 시작하지 않는다.** 원64→512/amount512_desktop_20261011_a는 [최종 결과](results/desktop_amount512_20261011/README.md)의 추가1,344학습·2,200환경·세 strict FAIL로 종료됐다. 아래 명령은 원 이력이며 새 ATC 작업은 [새 프롬프트](DESKTOP_ATC_PPO_PROMPT_20261011.md)를 따른다.

아래 내용을 새 데스크톱 Codex 세션에 붙여 넣는다. 이 문서는 실행 가능한 범위를 전달하며 이 노트북에서 추가 학습을 시작하는 명령이 아니다. GitHub 실행 ZIP 배포는 사용자의 최신 요청으로 허용한다. ZIP 속 자체 PPO 상태 세개만 추가 공유하고 APK·TFLite·원시 실측·키·개인 경로는 계속 제외한다.

## 복사할 프롬프트

```text
D1Check의 동결 A24 CPU/GPU 시뮬레이터와 현재 PPO를 이 데스크톱에서 내려받아 검증하고, 같은 설정의 학습량 연장·평가·결과 분석까지 진행하라. 계획 제시에 그치지 말고 아래 승인 범위 안에서 실행하라. 한국어로 보고하라.

저장소: https://github.com/mingyujo/D1Check
브랜치: feature/arrival-scheduling-20260923
먼저 AGENTS.md, docs/PROJECT_STATUS.md와 관련 PLAN/DECISIONS를 읽고 실제 Git 상태를 대조하라. 사용자 변경과 다른 worktree는 보존한다. 이미 저장소가 있으면 무조건 reset/clean하지 않는다.

다운로드할 파일:
docs/results/desktop_handoff_20261011/D1Check-desktop-cpu-20261011.zip
Raw URL:
https://raw.githubusercontent.com/mingyujo/D1Check/feature/arrival-scheduling-20260923/docs/results/desktop_handoff_20261011/D1Check-desktop-cpu-20261011.zip
크기: 1,743,807바이트
SHA-256: 4d7e0fcf65591a2ec015604fb69ea8f10358c72e28f1703a18989f6f8546241c

공식 GitHub 경로에서 받고 SHA와 ZIP 항목의 bundle_manifest.json을 검증한다. Raw 접근에 인증이 필요하면 정상적인 인증 Git clone/gh 다운로드를 사용하고 접근 제한을 우회하지 않는다. 토큰/키를 출력하거나 공유물에 넣지 않는다. SHA가 다르면 다른 파일로 대체하지 말고 중단·보고한다.

기존 폴더를 덮지 않는 짧은 별도 작업경로에 압축을 푼다. ZIP의 D1Check-desktop-cpu-20261011 폴더에서 실행한다. 최신 저장소 코드를 ZIP의 동결 코드에 섞지 않는다. 저장소의 docs/DESKTOP_JOINT_RL_AMOUNT_20261011.md와 docs/results/desktop_handoff_20261011/README.md도 확인한다.

Python3.11.9/Windows64와 NumPy2.4.6/PyTorch2.11.0+cpu가 기준이다. 먼저 실제 OS/Python/CPU/RAM/디스크·필수 라이브러리를 확인하고 격리 venv를 준비한다. 이미 호환 환경이 있으면 재설치하지 않는다. 필수 패키지는 NumPy/Torch, Matplotlib은 보고서용 선택이다. 공식 배포처를 사용하며 CPU 실행으로 진행한다. 다른 OS/CPU에서도 동일 비트 결과가 보장된다고 주장하지 않는다.

학습 전 아래를 순서대로 통과시킨다(venv Python 사용).
1. python -B -X utf8 -m tools.d1_joint_amount_cli
2. python -B -X utf8 -m unittest tools.test_d1_joint_amount_session tools.test_d1_joint_amount_ledger -v
3. python -B -X utf8 -m tools.d1_desktop_package_smoke run-smoke
이미 완료한 smoke가 있으면 completion/원장/SHA를 확인하여 재실행하지 않는다. smoke는 이미 본 low/mean 개발입력3환경/72요청/학습0이며 새 성능 확인이 아니다.

이번 새 데스크톱 과제는 같은 V1 서비스 envelope + 절대서비스 목적v2의 학습량 비교다. 원 세 terminal64의 actor/critic/Adam/승수와 공유 sampling RNG를 보존한다. 세 모델은 초기화 seed11/23/37이고 공유 round-robin RNG 세션이며 독립3 sampling stream으로 표현하지 않는다. 다른 서비스 envelope V2에 이 actor를 이어 붙이지 않는다. 알고리즘/상태/행동/mask/보상/계수/기한/지원/최종판정은 변경하지 않는다. Band는 비교군이며 자체 JointList가 기본/복귀/학습참조/예측후속이다.

승인하는 새 범위:
- 세 모델 모두64→512, 각448추가·총1,344학습.
- 예정2,200환경: teacher448 + 학습1,344 + 개발72 + 새 확인48조건×7정책336.
- 이 연장 task의 환경 상한2,300, 학습 상한1,344.
- 사전검증 smoke 별도상한3환경/학습0.
- 실제 run 누적활성240분, 마지막10분 저장 예약. 검증·설치·다운로드 시간도 별도로 기록한다.
- NPU/ADB/기기 추론/설치/추가실측0, 새 AI 모델/새 알고리즘/하이퍼파라미터 탐색0.
- 과거 종료500환경/192학습 및 프로젝트 기존 소비는 초기화하지 않고 별도 계승한다.

사용할 새 task ID: amount512_desktop_20261011_a
학습 arrival seed 시작: 860010001(등록상860010001..860010112)
확인 arrival seeds: 860020101 860020102 860020103 860020104
원 registry와 데스크톱의 추가 등록 이력을 대조한다. 이미 같은 task가 있다면 새task를 만들어 중복 실행하지 말고 기존 상태를 검증·재개한다. 다른 과제와 seed가 겹치면 fresh로 재해석하지 말고 중단·보고한다.

검증 통과 뒤 최초 한 번만 준비한다:
python -B -X utf8 -m tools.d1_joint_amount_cli prepare --task amount512_desktop_20261011_a --target 512 --arrival-start 860010001 --confirm-seeds 860020101 860020102 860020103 860020104 --native-cap 2300 --learning-cap 1344 --active-minutes 240 --reserve-minutes 10
이어서 실행한다:
python -B -X utf8 -m tools.d1_joint_amount_cli run --task amount512_desktop_20261011_a

중지 요청은 task폴더의 REQUEST_STOP 파일로 처리해 현재 환경 경계에서 세 모델/공유RNG/case-nextseed/소비/active 시간을 저장한다. 정상 재개 시 REQUEST_STOP을 없애고 같은run을 사용한다. 강제 종료·미완성 checkpoint·소비/cursor 불일치를 성공으로 처리하거나 예산/clock을 초기화하지 않는다. 시간·상한에 도달하면 상태와 미완료 범위를 저장해 종료하며 자동 확대하지 않는다.

일반 경로/파서/설치/문서/시각화 오류는 원인을 기록하고 해결하라. 등록 뒤 source 잠금 오류를 무시하거나 계약을 덮지 않는다. 호스트만 고치는 경우에도 원source/상태/소비/clock과 변경근거를 보존해 검증한다. 정책 의미 변경·마스크 완화·보상 튜닝·optimizer 초기화·학습cached replay로 오류를 우회하지 않는다.

완료 후 Band/Triton/JointList/CostList와 세 PPO를 같은 새48조건에서 원단위로 비교한다. 전체 예정 대비 완료/미완료·긴급P95/기한실패·일반기한실패·J120초·모형AP35..180초·판단시간·실제 wall/active/CPU시간을 기록한다. 48조건은4arrival seed×4부하×3모형문맥이며48독립 실측이 아니다. 이미 본 개발24를 새 독립 확인으로 부르지 않는다. 보상 증가를 성능 개선으로 대신하지 않는다.

현재는 전체 조건의 서비스/AP/J 우위가 미입증이며 V1의 허용된 예측 비용 개선후보가0이라는 한계가 있다. 학습량만 늘리면 개선되거나512에서 수렴했다는 결론을 전제하지 않는다. 냉각에 따른 속도 회복·최고 표면온도·온라인 폰 제어비용·실제 기기절감은 이 모형으로 새로 입증할 수 없다. 원strict/기본/experiment_ready=false 유지다.

별도 ID에 설정/seed/버전/상태SHA/전체 원장·checkpoint를 보존하고 CSV·한국어 그림·오프라인 화면·결론을 작성하라. raw/PT/venv/키/개인경로는 추가 Git commit에 넣지 말고 작은 코드·설정·보고서만 기록한다. 원 source와 종료실험은 보존한다. 프로젝트 문서에 이번 데스크톱의 실제 소비·완료/중단·다음 행동을 기록하고 authorized branch에 commit/push 후 실제 원격HEAD를 확인한다. 중간에 성공을 과장하지 말고 진행량·남은시간·저장상태를 간결하게 보고하라.
```

## 배포와 실행의 경계

이 ZIP은 약1.66MiB의 프로젝트 자체 정책 상태/동결 모형/코드다. 최신 사용자 지시에 따라 이 한 파일만 GitHub에서 받도록 배포한다. Android의 이미지 분류/탐지 모델 파일은 포함하지 않는다. 원 대용량 측정 데이터·나머지 checkpoint·실행기기 자료는 여전히 로컬 보존한다. 새 데스크톱의 위 과제는 프롬프트를 전달한 뒤 수행되며 현재 노트북에서 자동 실행하지 않는다.
