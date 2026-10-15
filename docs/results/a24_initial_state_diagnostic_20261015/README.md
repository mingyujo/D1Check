# 시작 AP를 뺀 온도 변화 — 기존17조건 보조 분석

**서로 다른 안정온도에서 시작한 온도 상승량을 비교하는 것은 조건부로 가능하다.** 선형 열 모형에서 내부 평형·같은 열저항/열용량·같은 추가 소비전력이 성립하면, 시작온도를 뺀 열응답은 같을 수 있다. ‘시작온도가 다르면 상승량 비교는 항상 불가능하다’고 단정하지 않는다. 다만 현재 A24에서 이 가정을 입증한 것은 아니다.

사용자 질문 뒤 수행한 **사후 보조 진단**이다. 동결 확인의 초기조건·성공 판정·에너지 지원을 변경하지 않았다. 활성C7·새 실측·결과 기반 정책 조정은 포함하지 않는다. [계산 계약](analysis_contract.json) · [17조건 CSV](all17_sessions.csv) · [대응 차이 CSV](paired_differences.csv) · [요약](summary.json) · [원자료/코드 SHA](SOURCE_SHA256.json) · [PC 검증](PC_VERIFICATION.json)

## 무엇을 계산했나

기존에 닫힌 확인17조건·2,352본요청 전부를 대상으로 했다. 첫 요청은 공통 원점35초에 도착한다. 원점0~35초의 **요청 전 HAL AP 시간가중 평균**을 기준으로, 원래35~180초 AP 평균·관측 최고값에서 이를 뺐다. 이 기준은 순간 온도나 ‘내부 전체 평형’ 추정이 아니다. 시작 승인에서 기존60초 AP 이력을 검사한 것과 구분한다.

원래의 최대10초 공백 기준·사다리꼴 적분·경계 보간을 그대로 사용했다. 원 AP 또는 요청 전 창이 불완전하면 상대값도 미판정으로 남겼다. **17중16조건**에서 상대 진단이 가능했고, 기존 첫 혼합BASE의12.34초 공백은 그대로 보존했다. 요청 전 평균 AP 범위는 약27.157~28.316℃다.

## 확인한 차이

혼합 부하 블록2의 병행조건에서 직렬BASE를 뺀 값이다. 기한·완료 결과는 기존 분석을 유지한다.

| 지표 | 온도 차이 |
| --- | ---: |
| 요청 전 AP 차이 | +0.0294℃ |
| 원래 AP 평균 차이 | +0.0401℃ |
| 요청 전 값을 뺀 AP 평균 차이 | +0.0107℃ |
| 원래 관측 최고 AP 차이 | +0.3000℃ |
| 요청 전 값을 뺀 관측 최고 상승량 차이 | +0.2706℃ |

이 블록에서는 시작값을 빼도 열 개선으로 바뀌지 않는다. 이 작은 수치 차이는 센서 정확도·갱신 시각·모형 오차보다 확실한 절감을 입증하지 않는다. 혼합 블록1은 BASE AP 창이 부적격이므로 대응 온도 차이를 채우지 않았다.

**이 분석으로 ‘27.1℃ 대신 현재 안정온도를 사용해도 된다’는 새 실행 허가가 생기지 않는다.** 같은 정책을 여러 통제된 초기 평형에서 반복하고 처리속도·열응답·조건 차이를 확인해야 그 가정을 검증할 수 있다. 현재 자료는 그런 목적의 독립 초기온도 실험이 아니다. 상승량을 에너지 J로 환산하지 않으며 실제 표면온도도 검증하지 않았다.

## GitHub 파일만으로 재현

저장소 루트에서 새 출력 폴더로 실행한다. 기기·APK·모델·개인 등록정보를 사용하지 않는다. ZIP 안 raw 원바이트와 원 분석 JSON이 입력이다.

~~~powershell
$env:PYTHONIOENCODING='utf-8'
$apReplay='output/initial_AP_public_replay'
if (Test-Path -LiteralPath $apReplay) { throw '새 출력 폴더를 사용하세요.' }
foreach ($apBlock in 1..3) {
  $apTag='{0:D2}' -f $apBlock
  Expand-Archive -LiteralPath "docs/results/a24_measurement_share_20261015/confirmation_visit_03_05/blocks/NEW_CONFIRM_CONFIRM_R02CONFIRM$apTag.zip" -DestinationPath "$apReplay/block$apTag"
}
python -B tools/d1_a24_initial_state_diagnostic.py docs/results/a24_initial_state_diagnostic_20261015/SPEC_TEMPLATE.json output/initial_AP_public_results
~~~

노트북의 원 폴더와 공개3ZIP에서 따로 추출한 원자료로 각각 계산해 CSV 두 개 및 SOURCE_SHA256.json이 바이트 단위로 같음을 확인했다. 기존 원본5종씩의 SHA를 계산 전후 대조했으며 변경0, 추가 기기 명령·APP·MAIN·세션 소비0이다. 전체 물리 열 모형의 적합성이나 새 시작 조건의 실기기 검증을 뜻하지 않는다.
