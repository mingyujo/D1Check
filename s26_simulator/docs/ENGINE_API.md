# 공통 엔진 개발 입구

현재 Node 물리·정책 모듈은 이 폴더 안 상대경로만 사용한다. 외부 npm 패키지, 원 PC 절대경로, Android runtime을 읽지 않는다. 실행 입력은 gzip을 해제한 `data/engine_packet.json.gz`와 `examples/case.json` 형식이다.

## API 형태

다음은 **새 등록 작업자 안에서 사용할 호출 형태**다. 문서/화면 확인은 `cli/s26.cjs replay`로 한다. 이 예시는 인계 검증 중 실행하지 않았다.

```js
const fs = require('node:fs');
const zlib = require('node:zlib');
const { Simulator } = require('./src/s26_simulator_v2.cjs');
const packet = JSON.parse(zlib.gunzipSync(fs.readFileSync('data/engine_packet.json.gz')));
const config = JSON.parse(fs.readFileSync('examples/case.json', 'utf8'));
// 새 registration/source/input/budget/identity가 승인·봉인되고 START가 내구 저장된 뒤:
const scenario = packet.scenarios.find(s => s.id === config.scenario);
if (!scenario) throw Error('Scenario not in sealed packet');
const result = new Simulator(packet, scenario, config).run();
// result를 raw→prepared→row→terminal로 내구 저장하고 전수 감사한다.
```

설정 `policy`, `stream`, `scenario`, `dt_s`, `power_dt_s`, `cost_model`, `timing_variant`, `action_options`의 실제 필드는 `examples/case.json`과 source에서 확인한다. 화면의 `draw`/bank 라벨을 실행 설정 필드로 바꿔 넣지 않는다. 등록된 저수준 CLI는 gzip이 아닌 JSON packet을 받는다:

```text
node src/run_resource_case_v2.cjs <packet.json> <new-registered-config.json> <new-raw-output.json>
```

이 명령 자체는 전체 예산/worker lock/START 관리자가 아니다. `archive/work/S26-UNIFIED-DYNAMICS-20261016/run_resource_study_v2.py`, `register_resource_v2.cjs`, `guard_snapshot_v2.py`와 해당 `archive/outputs/.../RESOURCE_*OPERATION*`이 원 운영 계약의 근거다. 원 경로를 새 경로에 매핑한 **새 등록 관리 실행기**가 먼저 필요하다. 복원된 원 registration을 새 실험에 재사용하지 않는다.

## 입력과 출력 연결

- `packet.timing`: 실측 처리시간 회귀계수, bootstrap과 nuisance 구분.
- `packet.templates`: 요청별 whole-vector 단계와 동적 추론 잔차의 결합 표본. 단계들을 서로 무작위로 재조합하지 않는다.
- `packet.AP`, `packet.power`: 활동 구간에서 AP/API 비용을 생성하는 현재 채택 모형.
- `packet.scenarios`: 봉인 요청표·초기 센서/준비 이력. 화면의 `draw`는 등록 sample stream에 대응하는 합성 표본이며 추가 실측 세션이 아니다.
- `publicObservation()`: 현재 ready 요청·deadline·owner route·과거 전달 센서만 정책에 제공한다.
- `result.policy_decisions`: 전체 후보·마스크·명목 추정·선택 이유. `requests`에는 실제 응답/반납·자원 경로가 남는다.

Python 기준 함수 `research/coupled_engine.py`와 원 적합/수리 source도 포함한다. 연구 스크립트에는 원 경로가 있으므로 바로 실행하는 공통 CLI와 구분한다. 변환 모형의 단계 경계/단위/잔차를 바꿀 때는 Node/Python 비교와 별도 모델 정확도 검증을 모두 통과해야 한다.
