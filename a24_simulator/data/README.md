# 데이터 찾기

- `CORE_MANIFEST.json`: 실행·모형 적합·검산·원 자료 연결의 정확 파일 목록. `objects/`는 SHA별 압축 객체이며 원본 바이트를 바꾸지 않았습니다.
- `PATH_MAP.json`: 원 절대경로는 provenance ID입니다. 다른 PC에서는 패키지 객체로 해석합니다.
- `RAW_ARCHIVES.json` / `raw/`: 수신 ZIP의 원 위치·SHA·중복 관계와 실제 보존 바이트.84개 고유 ZIP이고 원 이름이 다른 동일 파일을 추가 관측으로 세지 않습니다.
- `OLD_SOURCE_PROVENANCE.json`: 기존39세션에 사용한27개 저장 입력과 native raw 멤버의 선언/검증 범위. 모든 과거 외부 raw가 로컬에서 재검증됐다는 뜻이 아닙니다.
- `HISTORY_ARCHIVE.json`: 전체 A24 과거 코드·원장·실패·학습 rollout·Adam/RNG·검증 결과11,295파일의 Release 보존본. 변경본의 새 학습 증거는 별도 `TRAINING_ARCHIVE.json`에 연결합니다.
- `EXCLUDED_RUNTIME_ARTIFACTS.json`: 과거 등록에 등장한 외부 Node 실행파일의 해시만 보존했습니다. Python/Node 설치는 requirements와 README를 따르며 실행파일을 데이터로 재배포하지 않습니다.

```powershell
python tools/data.py MODEL_INPUTS.json
python tools/data.py MODEL_INPUTS.json --sha f54df34f --export data/working/MODEL_INPUTS.json
```

`MODEL_INPUTS.json`은 통합 timing/AP 입력, `DATASET.json`은115세션 통합 투영, `M8_DATASET.json`은 M8 집계입니다. 원 실측·validated projection·모형 예측은 각 provenance 필드로 구분합니다. model/tensor 해시 선언은 실제 binary·품질·설치 delegate 검증을 대신하지 않습니다.

실측 J·에너지 오차·에너지 CI는 미교정으로 null입니다. 성공/실패/미시도/중복/역할·window를 유지하며 observed development를 fresh confirmation으로 바꾸지 않습니다.
