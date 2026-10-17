# 검증과 재현

현재 근거는 `evidence/`의 파일과 SHA 원장을 확인한다. 이번 인계에서 기존 과학적 실험을 재실행하지 않는다.

- 기존 공통 plant444환경: 독립 Python 직접구간 적분/JS sweep, 원장·입력·후보·마스크·whole-vector·응답·센서·서비스879,721검사 PASS, 최대2.32e-11.
- 자원 선택기: 순수56검사, CPU/GPU/NPU 각각 선택 가능/지원병행/WAIT/공개입력 계약·알 수 없는 정책ID 거부.
- 새 P0 8환경: CPU/GPU/NPU/자동선택4조건의 dt.005/.0025 대조, 정시 건수 동일, J차이≤0.000716/AP≤0.00000240℃.
- 새 본48환경: 모든 기한·전량완료. 요청별 후보/선택의 Python 독립 산술 재생과 저장활동 비용56건 검산, 최대1.13e-11.
- 원감사에서 동적 P0 2건을 본48에 더해50으로 집계한 마지막 오류는 원 FAILED와56개의 완전 proof·112개의 cost영수증을 보존했다. 새 파생 finalizer가 exact proof/원raw SHA를 재검증하고 본48만 집계했다. 새 환경/비용 재적분 반복0, 최종452,636 누적 검사다.
- 최신 V4 화면: 실제 브라우저4,745검사, desktop/mobile/narrow9PNG 직접 검토, 저장값·집계·지원4lane 표시 PASS.

현재 standalone 인계 검증은 `node cli/s26.cjs verify`, `node --test tests/handoff.test.cjs`로 수행한다. 이 검사는 모델/코드 바이트·구조·저장 결과·마스크·반환 API와 HTTP 화면 바이트를 확인하며 새 Simulator·NN·optimizer·모델 적합을 만들지 않는다. 아카이브 원자료는 pack SHA→각 gzip blob SHA→복원 파일 SHA 순서로 확인한다.

수치 검산 PASS는 실기기 독립 정확도 PASS가 아니다. R21 사후 개발 오차·단위 미교정·초기 상태 제한을 STATUS와 함께 제시해야 한다.

인계 검증은 `evidence/HANDOFF_VERIFICATION.json`에 별도로 기록한다. 전체51,508 blob의 압축 해제/SHA, 60,878파일의 경로 연결, 원장207세션의 출처 포함, 핵심 파일 실제 복원·동일 파일 재사용을 확인했다. GitHub 공개 다운로드와 단일 폴더 ZIP의 최종 검증 기록은 [PUBLISH_VERIFICATION.json](https://github.com/mingyujo/D1Check/releases/download/s26-handoff-20261016/PUBLISH_VERIFICATION.json)에 연결한다. 원 수치 감사와 인계 포장 검증을 같은 검사 수로 합산하지 않는다.
