# 바로 이어서 작업하는 방법

## 1. 확인만 할 때

`node cli/s26.cjs verify` → `node cli/s26.cjs replay` → `node cli/s26.cjs serve` 순서로 확인한다. 설치형 Android 앱·ADB·원 PC·torch 없이 가능하다. 화면의 값은 기존 저장 결과이며 새 환경을 만들지 않는다.

## 2. 어디를 수정하는가

| 변경 목적 | 파일 |
|---|---|
| 물리 상태/추론 진행/응답/반납 연결 | `src/s26_simulator.cjs` |
| AP·양의 API 전력의 수식 | `src/dynamic_cost_math_v2.cjs` |
| 순서·자원·짧은 WAIT의 공개 입력 정책 | `src/rolling_action_v2.cjs` |
| 정책 연결·지원 ID·public observation·배정 로그 | `src/s26_simulator_v2.cjs` |
| 등록된 단일 실행의 원시 결과 저장 형식 | `src/run_resource_case_v2.cjs` |
| 모델/표본 | `data/engine_packet.json.gz`; `models/`는 설명·수리 후보용 원모형도 포함 |
| 단계 적합/교차검증 | `research/timing_model.py`, `research/fit_phase_transfer_v1.py` |
| 현재 화면/집계 | `web/index.html`, `research/view_templates/` 및 아카이브의 build/QA 스크립트 |

`data/engine_packet.json.gz` 안의 `timing`, `AP`, `power`가 현재 실행 모형이다. `models/phase_transfer_NOT_ADOPTED.json.gz`를 덮어 넣는 것만으로 단계 전이 수리가 완료되는 것은 아니다. 원 whole-vector 잔차/응답/해제 위치와 동적 적용 방법을 명시하고 검증해야 한다.

## 3. 실제 새 실행 전

호출 형식과 필드 연결은 [ENGINE_API.md](docs/ENGINE_API.md)에 있다. 저장 결과 확인과 새 환경 실행을 구분한다.

1. 새 코드 세대와 목표, 물리/정책 변경, 참조 입력, 예산, DEV/평가 분리 및 실패 복구 방식을 사전등록한다.
2. 원512 중500소비/12잔여는 공동 계보 예산이다. 복제본마다12가 생기지 않는다. 공동 관리자가 최신 원장/모든 다른 실험/디스크/실제 작업자·잠금을 확인해야 한다.
3. 저수준 실행기를 직접 실행하기 전에 START를 내구 저장하고, raw→prepared→row→terminal로 저장한다. 실패·미완료·이미 소비된 미저장 identity를 새 성공으로 수집하지 않는다.
4. 정책은 현재 도착한 요청·선언 기한·과거 dispatch/응답/AVAILABLE·이미 전달된 센서와 동결 명목 예측만 받는다. 미래 실제 도착/응답/잠재표본을 주지 않는다.
5. 실행 후 전체 입력·후보·마스크·선택·자원 점유·응답 경계·AP/API비용·소비·실패를 검산한다. 실제 새 RL이면 Adam/별도 RNG/경험·체크포인트/선정 시각과 새 평가도 포함한다.

## 4. 과거 자료와 원본 소스 찾기

`node scripts/restore-data.cjs --group all`로 이 폴더 안 `archive/`에 복원한다. `archive/work/<작업ID>`와 `archive/outputs/<작업ID>`가 일대일 대응한다. `incoming/`은 받은 원묶음/정정/동결 파일이다. 파일별 원래 출처·SHA는 캐시의 카탈로그와 `node cli/s26.cjs locate <원본 경로 일부>`로 찾는다.

과거 운영 스크립트에는 원 PC 절대경로·Windows 잠금·상위 도구가 있다. 이들을 원 등록인 것처럼 경로만 바꿔 실행하지 않는다. 현재 `src/`는 상대경로만 쓰는 작업 복사본이며, 과거 코드/기록은 재현 근거와 새 구현의 참고다. 원 운영 등록을 재현하려면 필요한 의존성·런타임·자료와 새 경로 매핑을 별도 등록한다.

## 5. 넘겨줄 때 유지할 결론

새 주정책은 GPU 고정을 없앴다. 현재 동질적 요청/좁은 초기온도에서는 NPU가 모두 선택되었다. 이를 모든 부하에서 NPU 최적, RL 학습 완료, 실물 에너지 절감 증명으로 확대하지 않는다. 기존 GPU 고정 FIFO/EDF 결과와는 선택 공간이 다르므로 표의 큰 차이를 순서 정책의 공정한 우위로 해석하지 않는다.
