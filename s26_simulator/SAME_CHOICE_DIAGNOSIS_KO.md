# 왜 FIFO·EDF·롤링 ATC가 같은가

**같은 자원 배정기와 현재 요청 부하·가용 자원 제약의 조합이 직접 원인입니다.** 새 환경을 실행하지 않고 기존48조건의6,144배정과 동결 코드를 전수 추적했습니다.

| 원인 | 확인 결과 |
|---|---|
| 공통 배정기 | 같은 J+열 점수로 분류4,608건 모두NPU. NPU가 J proxy까지 가장 낮은 것은 아님 |
| 부하×마스크 | 복수 실행가능1,551회 전부같은 종류·priority·기한. 같은route ATC점수도 모두동점 |
| 순위가 사라지는 지점 | 전역FIFO·EDF선두는349회달랐지만 실제가용후보에서는0회 |
| WAIT | 이미냉각중일때만허용. 이번기록의냉각조건충족0회 |
| 엔진감도 | 기존동일입력·동일표본48쌍의직렬/병행 J·AP·곡선은모두다름 |

따라서 직전 결과는 **동일 배정기를 둔 요청 순서 비교**입니다. 전체 자원 최적화 방식의 기여가0이라는 판정이나 실기기 정확도 인증으로 확대하지 않습니다. 현재 비용proxy의 상태적응과 열→속도 연관모형에도 보완 여지가 있습니다.

[전체 원인·모형 한계·보완 방향](experiments/tie_diagnosis_v1/REPORT_KO.md) · [전수 집계](experiments/tie_diagnosis_v1/RESULT.json) · [별도18,082검사PASS](experiments/tie_diagnosis_v1/VERIFICATION_RESULT.json) · [코드·입력SHA·CSV·원자료](experiments/tie_diagnosis_v1/)

새 정책 환경·Simulator·CostState·NN·학습·fit·예약0. 원 물리·요청·납기·성공/실패 원장·과거 평가를 보존했습니다.
