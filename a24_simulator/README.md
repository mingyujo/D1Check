# A24 통합 시뮬레이터와 스케줄링 정책 인계

**최신 원인 진단:** [A24에서 스케줄링별 차이가 작은 이유](docs/POLICY_GAP_DIAGNOSIS.md). 선택 경쟁·자원 제약·WAIT·고정 비용식·온도 피드백·RL 추가 기여를 실제24조건 저장 기록과 대조했습니다. 집계 소스와 수치/SHA를 함께 보존했으며 이번 추가 학습·실험은0입니다.

**최신 보완·학습 비교:** [긴급 납기 보호＋48요청 RL과 EDF](docs/PROTECTED48_COMPARISON.md) · [24조건 비교 화면](results/PROTECTED48_V2_20261016_01/index.html). 보완 RL은 새24조건 1152/1152 정시(기존RL1146), EDF 대비 총소비−0.04347%·작업증분−0.19978%·평균AP−0.005461℃이며 큰 폭 공동목표0/24입니다. 새학습64·DEV선정EP24·고정모형 유지·검산/NN재생/실화면PASS·예약OFF입니다. 아래 이전 버전은 보존합니다.


**최신 비교:** [비선점 EDF와 선정 RL의 동일 작업 구간 비교](results/EDF_CPU_FIRST_20261016_01/index.html) · [수치·검증 설명](docs/EDF_COMPARISON.md). 모바일 변형 규칙 대신 EDF를 사용하며, EDF는 예상 응답·비용으로 경로를 고르지 않습니다. 아래 기존 7정책 실행 화면·결과는 이전 버전으로 보존합니다.

**완료 범위와 파일 위치만 확인:** [완료·파일 안내](COMPLETED_AND_FILES.md)

**여기부터 읽으면 됩니다.** 이 폴더는 A24 분류·탐지 요청을 한 목록으로 만들고, 같은 처리시간·병행·열·조건부 전력 모형에서 정책을 비교하는 실행 정본입니다. 이전 연구 코드·원자료·실패·체크포인트·검증 증거도 연결했습니다. S26 계수를 A24에 전용하지 않습니다.

## 1. 바로 실행하기

Windows 10/11, Python 3.11, Node.js 22 이상이 필요합니다. Android 기기·ADB·GitHub 토큰은 시뮬레이터 실행에 필요 없습니다.

```powershell
cd a24_simulator
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
node experiments/protected48_v2_20261016/restore_budget.cjs
.venv\Scripts\python -B tools/run.py verify
.venv\Scripts\python -B tools/serve.py
```

브라우저에서 <http://127.0.0.1:8766/>를 엽니다. 포트를 바꾸려면 `tools/serve.py --port 8767`을 사용합니다. 검증은 폴더 안의 압축 자료를 `.cache/`에 해시 검증 후 풉니다. **GitHub 조회·예약·측정·학습은 자동으로 시작되지 않습니다.** 실행 버튼은 사용자가 요청한 계산만 시작하며 실패를 자동 재시도하지 않습니다.

현재 공유소비는502/512·잔10입니다. 새 clone은 위 `restore_budget.cjs`로 정확397 child 원장을 먼저 복원합니다(이전 parent105 별도). 기존 원장이 다르면 덮거나 지우지 않고 차단합니다. 새 학습을 시작하려면 새 소스/입력/독립 평가/예산을 별도 등록해야 하며 완료된 operation을 재실행하지 않습니다. 전체 보완 학습 경험·Adam·RNG410파일은 [검증된 runtime ZIP](https://github.com/mingyujo/D1Check/releases/download/a24-simulator-handoff-20261016-v1/A24_PROTECTED48_V2_TRAINING_20261016.zip)과 `results/PROTECTED48_V2_20261016_01/RUNTIME_ARCHIVE.json`에 연결되어 있습니다.

`python -B tests/test_diagnostics.py`와 `node tests/test_design.cjs`로 단위 검사를 합니다. 현지 검증 버전과 결과는 [검증 기록](docs/VALIDATION.md)을 읽습니다. `reference/`의 역사적 실행기는 원 경로가 남은 보존 소스이므로 현재 실행 입구로 사용하지 않습니다.

저장 결과는 `node tests/audit_saved.cjs`로 새 환경 없이 검산합니다. 브라우저 회귀 검사는 `npm install`, `npx playwright install chromium` 후 서버를 켜고 `npm run test:browser`로 실행합니다. 기본포트는8766이고 환경변수 `PORT`로 바꿀 수 있습니다. `src/test_*`, `preflight_four_route.py`, `qa_four_route.cjs` 등 이전 등록용 probe는 원 학습 SHA 보존을 위해 남아 있는 역사적 코드이며 현재 검증 명령은 이 문단의 `tests/`를 따릅니다.

## 2. 무엇을 수정하면 되는가

| 목적 | 파일 |
|---|---|
| 브라우저·로컬 API | `src/index_v2.html`, `app.js`, `bulk.js`, `server_v2.cjs` |
| 요청·납기·부하 설계 | `src/bulk_design.cjs` |
| 정책과 모형 연결·결과 저장 | `src/lab_backend.py` |
| 사건·5단계 처리·자원 점유 | `src/interactive_kernel.py` |
| CPU/GPU 4경로 처리시간·전력 전이 | `src/four_route_model.py` |
| AP 온도 모형 | `src/thermal_four_route.py` |
| ATC 후보·RL 입력·마스크 | `src/policy_bridge_four_route.py` |
| 전체/작업 구간·동일 일정 진단 | `src/diagnostics.py` |
| PPO 신경망·Adam·RNG | `reference/rolling/learner.py` |
| 새 학습의 실행 정본 | `tools/shared_A24-MODEL-INTEGRATION-20261016_train_v2.py` |
| 선정된 정책·학습 결과 | `models/TRAINING_RESULT.json`, `TRAINING_COMPLETE.json` |
| 변경 재개 절차 | [HANDOFF.md](docs/HANDOFF.md) |

**실행 원자료·봉인 모형·이전 결과는 덮어쓰지 않습니다.** 소스를 바꾸면 별도 버전/출력/seed/예산 등록을 만들고 기존 SHA·실패 기록을 이어받습니다. 현재 모형이나 RL이 우수하다는 결론을 맞추기 위해 계수를 조정하지 않습니다.

## 3. 기기·처리·정책 계약

- 분류 C와 탐지 D가 모두 CPU/GPU를 선택합니다. 한 CPU lane·한 GPU lane에 각 한 요청, 최대 두 요청이 AVAILABLE까지 비선점 점유합니다. 같은 작업끼리의 CPU/GPU 병행도 선택 범위에 있습니다.
- 5단계는 dispatch→execution→output→persist→worker release→AVAILABLE입니다. 분류 응답은 output, 탐지 응답은 persist입니다. 응답했다고 자원을 즉시 반환하지 않습니다.
- RL은 사건 기반 롤링 상태에서 ATC 후보의 요청·CPU/GPU·WAIT를 선택합니다. 샘플된 미래 처리시간·완료시각·미래 온도를 입력에 넣지 않습니다.
- 비교군은 WAIT 제거, 명시적 CG/DC 고정 직렬, FIFO 자유배정, EDD, ATC, 모바일 납기·조건부 비용 규칙입니다. 이 모바일 규칙은 Android 운영체제 스케줄러 자체의 재현이 아닙니다.
- 같은 입력·초기 AP 이력·잠재 표본 seed·물리 모형으로 비교합니다. 정책이 같은 일정을 내면 그대로 표시합니다. 차이가 커야 성공이라는 규칙은 없습니다.

## 4. 이번 수정

일률적 `+1.5초`를 권장 기본값에서 제외했습니다. 분류 `2.2초`·탐지 `5초`는 기존 A24 실험 계약의 참조값이며 사용자 경험 SLA 인증이 아닙니다. 긴급 ×0.7·일반 ×1은 탐색 설계입니다. 분류/탐지 각각에 긴급·일반이 존재하도록 배치합니다. 임의 납기와 요청 목록은 계속 편집할 수 있습니다.

기본 설계는 48요청 × 분류 비율 25/75% × 일정/몰림 × 참조 부하 0.50/0.85/1.20의 **12조건**입니다. CG/DC 고정 경로의 명목 자원 점유로 도착 간격을 먼저 정하며, 정책 결과에 맞춰 부하를 고르지 않습니다. 실제 자유배정 시스템의 사용률 인증은 아닙니다. 3 seed 설계는36조건입니다.

전체 J* 0~180초·평균 AP 35~180초는 보존합니다. 추가로 모든 정책에 동일한 입력 기준 작업창(첫 도착~마지막 도착+15초), 기저/활동 증분, 작업창 최고온도·정확 일정 동일성·WAIT0을 보여줍니다. 작업을 끝내지 않아 소비가 적어진 경우를 절감으로 승격하지 않습니다.

이전 3경로 actor의 4경로 전이는 비교용으로 보존했습니다. 새 4경로 PPO는 새로 학습하고 EP16/32/64 중 별도 DEV만으로 선정합니다. EVAL을 보고 다시 고르지 않습니다. 상세 수치와 미달/악화는 [현재 결과](docs/CURRENT_RESULTS.md)를 읽습니다.

## 5. 자료와 검증 범위

기존39개와 M8 76개, 합계115 관측 세션이 통합 자료의 출처입니다. 미시도·불완전·지원 부족도 분모에서 제거하지 않습니다. `data/CORE_MANIFEST.json`은 모형 재구성과 원 자료 연결에 필요한 정확 파일, `RAW_ARCHIVES.json`은 수신 ZIP들의 원 위치·SHA·중복 관계입니다. `OLD_SOURCE_PROVENANCE.json`은 기존27개 저장 입력과 원시 멤버 선언의 한계를 포함합니다.

Git 폴더에는 실행·수정에 필요한 자료와 모델이 포함돼 있습니다. **모든 역사적 rollout/Adam/RNG/수신 영수증까지 복원**하려면 [전체 보존본](data/HISTORY_ARCHIVE.json)에 핀한 Release ZIP을 `python tools/download_history.py`로 한 번 받아 검증합니다. 해시별 저장으로 중복 원본의 바이트를 보존했으며, 폴더 이름·재포장을 추가 실측으로 세지 않습니다. 저장소의 다른 폴더를 읽지 않아도 현재 시뮬레이터를 실행할 수 있습니다.

## 6. 해석상 남은 한계

- J*는 역사적 조건부 비용식입니다. 전류/전하량 단위 미교정으로 **실측 J·에너지 오차·해당 CI는 null**입니다. AP HAL 온도는 표면온도가 아닙니다.
- 탐지 GPU 시간은 A24 과거 paired GPU/CPU 5단계 비율을 현재 CPU 벡터에 전이한 예측입니다. 현재 APK의 GPU 시간 측정으로 쓰지 않습니다.
- 새 CPU/GPU 조합의 열·전력은 작업/장치 가산과 공통 병행 항의 외삽입니다. 미측정 간섭은 독립 서비스 가정으로 표시합니다. 온도→전력/처리시간 피드백·wake/unload 비용을 임의로 추가하지 않았습니다.
- 통합 AP 모형의 기존 전체 일정 평가 숫자 범위는45/69세션이며 평균 세션 지연 MAE 약0.10024초·AP MAE 약0.35442℃입니다. 나머지 지원 부족20·사전 UNKNOWN4는 실패/미확인으로 남아 있습니다. 모든 새 혼합 부하의 정확도 인증은 아닙니다.
- 이미 본 자료를 개발에 썼으므로 fresh 실기기 독립 확인이 아닙니다. 새 RL 학습·소프트웨어 감사는 폰 설치·실제 정책 효과·출력 품질을 검증하지 않습니다. 과거10% J/0.5℃ 공동목표 미달과 RL 추가 우위 미입증도 보존합니다.

모델 `.tflite`·APK·기기 런타임은 재배포하지 않습니다. 원 EfficientDet exact binary의 귀속 미확인 경계를 유지하며 URL/해시 선언만 데이터에 있습니다. 이 시뮬레이터는 실제 추론 binary 없이 동작합니다.
