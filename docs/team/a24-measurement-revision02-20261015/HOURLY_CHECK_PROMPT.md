# 다른 채팅의 시간별 확인용 프롬프트

아래 내용을 복사해서 매시간 확인 작업에 사용한다. 이 파일을 만드는 것만으로 예약 메시지가 등록되는 것은 아니다.

```text
매시간 외부 GitHub에서 D1Check A24 실측 진행 상황을 읽고 한국어로 짧게 알려줘.

저장소: https://github.com/mingyujo/D1Check
확인할 브랜치: codex/a24-laptop-prep-20261014
진행 현황:
https://github.com/mingyujo/D1Check/blob/codex/a24-laptop-prep-20261014/docs/team/a24-measurement-revision02-20261015/LIVE_PROGRESS.md
기계 판독 상태:
https://raw.githubusercontent.com/mingyujo/D1Check/refs/heads/codex/a24-laptop-prep-20261014/docs/team/a24-measurement-revision02-20261015/LIVE_PROGRESS.json

매번 원격 최신 커밋과 위 파일의 마지막 갱신 시각을 확인해.
1. 원래 독립 확인40의 정상 완료·실패/시작거절·미실행과 현재 단계를 알려줘.
2. 별도 개정혼합4와 실패 보완12의 횟수는 원확인40과 분리해.
3. 새로 올라온 비교 묶음 ZIP·CSV·코드/APK/입력 버전·SHA 링크가 있으면 알려줘.
4. 문제가 있으면 문서에 기록된 원인·조치·남은 작업만 요약해.
5. J는 아직 미검증이며 AP는 HAL 보고값이다. 준비 완료·예산 소비·보상 증가를 실측 성공이나 에너지 절감으로 표현하지 마.
6. 60분 넘게 갱신이 없으면 'GitHub 진행 기록 갱신 지연'이라고 알려줘. 그것만으로 기기 측정이 중단됐다고 단정하지 마.

확인은 읽기 전용으로 해. 로컬 Git 상태만으로 원격 업로드를 추정하거나, 측정·재학습·재시작·설정 변경을 수행하지 마.
```
