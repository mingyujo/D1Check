# 연구 원본 배포 — A24 실측과 시뮬레이션·소스

2026-10-11. 추가 실측 원본과 누락 코드 원본을 GitHub Release 첨부와 Git의 파일명세/복원 코드로 제공한다. 최종 수량·SHA·검증 결과는 summary/verification을 따른다. 새 학습·기기 실행은0이다.

- [범위와 복원 절차](../../RESEARCH_ORIGINALS_20261011.md)
- [원파일별 명세](files.json.gz)
- [집계와 Release 첨부 SHA](summary.json)
- [검증](verification.json)
- [회귀 검사에 필요한 선택 목록](verification_selection.json)

Release는 `https://github.com/mingyujo/D1Check/releases/tag/d1check-research-originals-20261011`이다. ZIP은 중복 제거된 SHA objects이며 manifest에 따라 원 경로를 복원한다. 당시 코드/데이터 bytes와 이식용 Git 코드의 차이를 숨기지 않는다. 원본 소스 사본에는 당시 호스트 경로 문자열이 남아 있으므로 메모리 경로 연결을 사용한다. 개인 사용자 문서·모델binary·APK·서명키·의존성 캐시는 첨부하지 않는다.

전체 복원이 필요 없으면 `--prefix workspace/tools/`처럼 namespace/원경로 prefix를 반복 지정할 수 있다. 검증 선택 목록의 `prefixes`를 사용하면 필수 원소스/모형/계획/raw만 복원할 수 있다. 서로 다른 원본을 같은 경로로 덮어쓰지 않는다.

원64→512 실험과 원실측은 완료/실패/중단 상태를 그대로 보존한다. 복원 뒤 이 task들을 자동 재실행하지 않는다. 기본/strict/experiment_ready=false와 제출 범위는 바뀌지 않는다.

## 완료 수량과 검증

- 원파일 609,166개 / 논리 9.201GiB, 중복 제거 568,431 SHA objects.
- 전체원본 ZIP 12개 / 압축 1.845GiB, 검증용 작은 ZIP 5.22MiB를 별도로 제공한다.
- 모든 원본 object SHA/ZIP SHA·GitHub 첨부 digest 일치, 검증용 원소스/raw 복원 뒤58회귀와 복원/경로5검사 PASS다. 원파일수정/추가학습/기기/실측0이다.
- 앞선23개 미공유 파일은 모두 원본 Release에 포함됐다. 자격증명 표식 파일 1개는 원본 공개에서 제외하며 값은 출력하지 않는다.
