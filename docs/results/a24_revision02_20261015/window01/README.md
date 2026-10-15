# 최초26.1℃ 묶음 W1 — 대응 비교 미완료

| 조건 | 예정 요청 | 본요청 완료 | 기한 내 | 긴급 P95 | AP 평균/관측최고 |
| --- | ---: | ---: | ---: | ---: | --- |
| 분류 GPU |252|252|252|271.841ms|27.2648/27.8℃|
| 분류 CPU |252|0|0|측정 안 됨|본요청 창 없음|

CPU는 준비 후600초 이력234회 중27.1~28.7℃·마지막27.7℃였으며25.6~26.6℃에 들어온 읽기는0회였다. 본요청0·워밍업8·예정252건 UNFINISHED를 보존했다. GPU의 출력252건은 기존 decoded 계약에 일치했다. 단일 승인 이미지 반복이며 전체 정확도 검증은 아니다.

두 군의 성능 우열·열 절감·J 절감은 판정할 수 없다. GPU의 AP는 HAL 읽기값이고 실제 표면온도/센서 갱신시각은 미검증이다. 검증J는 계산불가다. 이 기록은 시작 조건의 실행 가능성을 점검하는 개발 자료이며 기존/새 묶음과 합산하지 않는다.

[오프라인 화면](index.html) · [모든 시도](attempts.csv) · [예정504건](requests.csv) · [CPU 대기 진단](PRESTART_DIAGNOSTIC.json) · [사전 계약](../../../team/a24-measurement-revision02-20261015/window01/README.md)

원 tar/기기 이벤트/결과물/정확한 manifest/서명·원장·소스 스냅샷은 로컬에 보존한다. 공유물에는 모델/APK/키/개인 target·경로를 넣지 않는다. 실제 앱 parser/host 검사와 원161소스 불변은 사전 검증 기록을 따른다.

재분석(해당 개인 원물 필요): `python -B tools/d1_a24_measurement_report.py <job.json> <ANALYSIS_CONTRACT.json> <새결과폴더> --stage DEV`, 이어 `python -B tools/d1_a24_revision02_prestart_report.py <job.json> <새결과폴더>`.
사용한 시간창/실행ID를 재측정하지 않는다.
