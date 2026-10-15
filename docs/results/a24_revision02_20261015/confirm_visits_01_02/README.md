# A24 독립 확인40 — 첫 두 방문의 완료9조건

2026-10-15. **확인40 중9조건·1,272요청을 회수했고 전량완료·출력PASS다.** 아직31조건은 실행 전이며 전체 확인 완료가 아니다. 사용자 지시로 둘째 방문의 혼합BASE 회수 후18:23:57에 조건 사이에서 중지하고 [별도 전류 반응 진단](../current_response_diag_01/README.md)을 수행했다. 이후 같은20:02기기종료/20:07저장 창에서 세 번째 방문으로 미시도 조건을 재개한다.

[오프라인 비교 화면](index.html) · [조건별 결과](sessions.csv) · [40조건 전체 원장](attempts.csv) · [시작 상태](run_context.csv) · [대응 차이](paired.csv) · [새5조건 원물ZIP](raw_window02_originals.zip) · [840원물SHA](RAW_WINDOW02_MANIFEST.json) · [첫4조건 원물·보고](../confirm40_window01/README.md)

첫 확인 블록의 혼합 병행은 분류96/96·탐지32/32를 모두 기한 내 완료했고 긴급P95는1.421초였다. 같은 직렬은 분류13/96·탐지10/32,긴급P95=11.049초다. 직렬의 AP12.34초 공백은 기존 최대10초를 넘으므로 그 군의 AP평균·최고값을 비교에서null로 유지했다. 이번 새5조건은 AP공백 모두 기준 내라 누적적격은8/9다. 부적격 군을 재실행하거나 기준을 완화하지 않는다.

새 저부하 직렬·병행 허용은 각각64건 모두 기한 내 완료했고 실제 병행 점유는0초다. 따라서 작은 비용 차이를 병행 자체의 효과로 해석하지 않는다. 분류252건은 CPU/GPU 모두 기한 내·출력PASS이고 P95는115.599/271.557ms다. 두 자원 평균AP는28.5807/28.5759℃,관측최고29.5/29.0℃였지만 시작상태·센서 캐시 나이를 완전히 통제한 인과효과나 표면온도 절감으로 주장하지 않는다. 다음 블록의 혼합직렬은128건 전량완료했으나 분류12/96·탐지10/32만 기한 내,긴급P95=10.724초였고 다른 대응군은 재개 후 평가한다.

조건부 에너지는 [기존12조건 사후분석](../conditional_energy_comparison/README.md)과 분리한다. 이9조건 화면의 공식J는null이다. 보상·정책·모형 계수·입력·기한·완료/실제자원반환 경계와 AP기준을 바꾸지 않았다. 미실행31조건을0성능으로 평균내지 않았다.

두 원방문의 원물은 편집하지 않고 새private 분석 스냅샷으로 복사한 뒤 원동결 분석기를 실행했다. 공개본은 AP 부적격을 그대로 가리고 그림·화면만 새로 생성했다. 이전4조건과 공유되는 모든 결과 필드가 정확히 같음을 검산했다. 원40조건 원장·1,272요청을 대조했고 그림의 한국어 표시·누락값 표시를 확인했다. 새5조건 원물840파일은 모든 ZIP멤버SHA가 원본과 같다.

```powershell
python -B tools/d1_a24_confirmation_visit_merge.py <NEW_PRIVATE_SNAPSHOT> <CLOSED_VISIT01_JOB> <CLOSED_VISIT02_JOB>
python -B tools/d1_a24_measurement_report.py <NEW_PRIVATE_SNAPSHOT/job.json> <ORIGINAL_ANALYSIS_ENGINE_ADAPTER> <NEW_PRIVATE_REPORT> --stage CONFIRM
python -B tools/d1_a24_suite_report_context.py <NEW_PRIVATE_SNAPSHOT/job.json> <NEW_PRIVATE_REPORT>
python -B tools/d1_a24_confirmation_publication.py <NEW_PRIVATE_REPORT> <NEW_PUBLIC_COPY>
```

스냅샷의 원장은 Windows경로 길이를 고려해 짧은Documents경로를 썼다. 첫 긴경로 복사 실패는 PC/측정0이며 미완성 스냅샷을 보존하고 다른 새경로로 재생성했다. 기존 원자료나 실제 측정의 실패가 아니다. 코드 기준HEAD25361be+신규파일SHA,기존179파일불변이다. 공개본의 [생성 기록](PUBLICATION_CONTEXT.json)과 원물manifest를 따른다.
