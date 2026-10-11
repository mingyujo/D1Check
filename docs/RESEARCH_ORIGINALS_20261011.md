# 실측·시뮬레이션·연구 코드 원본의 GitHub 배포

작업 ID: RAW-ORIGINALS-GITHUB-01 / 2026-10-11. 사용자의 추가 실측 원본·누락 코드 원본 게시 지시에 따른다. 앞선 이관에서 제외했던 원시 연구 데이터와 당시 소스 사본을 이번에 별도 게시한다. 이전 공개 여부 기록은 당시 이력으로 보존한다.

## 저장 위치와 범위

대용량 파일은 GitHub Release `d1check-research-originals-20261011`의 ZIP 첨부로 배포한다. Git 저장소에는 파일별 SHA-256·원 경로·첨부/ZIP member 대응 명세와 다운로드/검증/복원 도구를 둔다. Git clone만으로 첨부가 자동 내려오지는 않으므로 아래 절차를 사용한다.

- [배포 결과·검증](results/research_originals_20261011/README.md)
- [파일 명세](results/research_originals_20261011/files.json.gz)
- [집계·첨부 해시](results/research_originals_20261011/summary.json)
- [복원 도구](../tools/d1_research_originals.py)
- [원 코드의 경로 이식 검증 실행기](../tools/d1_research_originals_tests.py)

`workspace`는 이 프로젝트의 output/원 코드/분석 자료, `external`은 별도 D1Check_Arrival_Extension 연구 폴더다. 내용이 같은 파일은 같은 SHA object를 사용하고 복원할 때 모든 원 경로에 동일한 원 bytes를 쓴다. 정상 완료뿐 아니라 실패·중단·부분 실측·원장·계획·동결 상태와 자체 RL checkpoint를 보존한다. 과거 Adam/RNG가 이미 없어졌던 실행은 복원되지 않는다.

원본 소스의 당시 경로 문자열·코드·데이터 bytes를 바꾸지 않는다. 이식용 공개 코드와 당시 원본 코드는 구분한다. 라이선스 미확인 Android 모델 binary, APK/AOT, 서명키/실제 자격증명, 의존성/빌드 캐시, 개인 문서, 입력 이미지 자산은 제외한다. 원본에 자격증명 표식이 있으면 그 파일을 공개하지 않고 이유만 남긴다. 입력 이미지/모델은 기존 원URL·SHA·라이선스 규칙에 따라 별도 확보한다.

S26의 기존 d1sim/mixed/quality 원자료와 코드는 기존 세 고정 브랜치에 있다. 별도 원격 tree의 존재를 확인하며 재작성/강제merge하지 않는다. 이 A24 원본 첨부와 S26의 모형/계수를 섞지 않는다. 전체 S26 blob의 SHA-256 감사가 완료됐다고 주장하지 않는다.

## 데스크톱 복원

저장소 루트에서 호환 Python으로 실행한다. 먼저 대상 디스크 여유와 summary의 논리 용량·압축 용량을 확인한다. 전체 복원은 논리 용량만큼 공간이 필요하며 검사 목적이면 필요한 prefix만 복원할 수 있다.

```powershell
python -B -X utf8 -m tools.d1_research_originals download
python -B -X utf8 -m tools.d1_research_originals verify
python -B -X utf8 -m tools.d1_research_originals restore
```

기본 복원 위치는 `output/research_originals_restored_20261011`이고 기존 작업 코드/출력을 덮어쓰지 않는다. 기존 대상 bytes가 다르면 실패한다. 같은 bytes이면 재사용한다. 다운로드/복원 실패의 부분 파일은 남겨 조사하며 자동 삭제·덮어쓰기하지 않는다.

원소스와 필수 raw만의 검증은 [배포 결과](results/research_originals_20261011/README.md)의 선택 명세를 따른다. 원소스 전체 회귀 예시는 아래다.

```powershell
python -B -X utf8 -m tools.d1_research_originals_tests --snapshot output/research_originals_restored_20261011 --report output/research_originals_restored_20261011/original_suite_verification.json
```

실행기는 원파일을 고치지 않고 **메모리에 읽은 절대경로 문자열/경로 키만** 복원 위치로 연결한다. 원 bytes SHA, 수치·boolean·배열·요청 경계·계수·판정은 바꾸지 않는다. 원 실험의 Windows 경로를 다른 데스크톱에 그대로 요구하지 않는다. 실패하면 실제 누락/환경/경로를 기록하고 과거 판정을 완화하지 않는다.

## 후속 작업 경계

복원은 과거 종료 namespace/clock/seed를 새 실험으로 만드는 일이 아니다. 실측 실행기·ADB·설치·이전 학습 task를 자동 실행하지 않는다. 신규 학습/기기 명령/추가 실측은 이번 배포에서0이다. 새 ATC→PPO 구현은 [기존 전달 프롬프트](DESKTOP_ATC_PPO_PROMPT_20261011.md)를 따르되 원자료 사용이 필요한 부분은 이번 복원을 먼저 수행한다. 원모형/과거 FAIL/기본/strict/experiment_ready=false와 사용자 WIP/다른 worktree를 보존한다.
