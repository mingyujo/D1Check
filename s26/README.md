# s26 — Galaxy S26 측정 작업 폴더

담당: 영훈 (산업공학회 D1 과제) · 생성 2026-09-12
목표: **같은 S26 한 대에서 CPU / GPU / NPU를 동일 프로토콜로 측정**하고, 그 결과를 시뮬레이터의 자원 선택표로 쓴다.

이 폴더는 `D1CHECK_STAGE_GATE_PLAN.md`의 **단계 3B(S26 NPU 자격·비교)** 산출물이 모이는 곳이다.
기존 A24 측정 스택(`app/`, `benchmark-runner/`, `telemetry-contract/`, `tools/`)은 건드리지 않는다.

---

## 왜 새 폴더인가

| | A24 (SM-A245N) | S26 |
|---|---|---|
| NPU 실행 경로 | 없음 | **있음 (검증 대상)** |
| 현재 측정 스택 | CPU/GPU 검증 완료 | 미이식 |
| `formal_gpu_valid` | 통과 가능 | **기기 모델 하드코딩 때문에 항상 false** |

A24의 CPU/GPU 결과에 다른 기기의 NPU 결과를 한 선택 공간처럼 붙이면 안 된다. 두 기기 차이에는 자원뿐 아니라 SoC·센서·OS·배터리·열설계가 전부 섞여 있다. **S26에서 CPU/GPU 기준선도 같은 프로토콜로 다시 잰다.**

---

## 문서

| 파일 | 내용 |
|---|---|
| [`docs/MEASUREMENT_DEFINITION.md`](docs/MEASUREMENT_DEFINITION.md) | **먼저 읽을 것.** 현재 코드가 실제로 재는 것 전부 — AI 항목, 6개 측정 계층, 결과 CSV 컬럼(74/61/30), 범위 한계 |
| [`docs/S26_DEVICE_PROFILE.md`](docs/S26_DEVICE_PROFILE.md) | S26 기기 정보 수집 체크리스트 + adb 명령. **코드 짜기 전에 이걸 먼저 채운다** |
| [`docs/A24_TO_S26_PORTING.md`](docs/A24_TO_S26_PORTING.md) | 고쳐야 할 하드코딩 15곳 + NPU 추가 순서 |
| `tools/` | S26 전용 스크립트 자리 |

---

## 작업 순서

```
0. 기기 확보 → docs/S26_DEVICE_PROFILE.md 전부 채우기      ← 지금 여기
     · 정확한 모델 번호 / SoC / Android 버전 / LiteRT·vendor delegate 지원
     · dumpsys thermalservice 센서 이름 전체 목록
     · Benchmark Runner "Probe NNAPI devices" → D1NPU 로그
1. 기기 판별 하드코딩 제거 (device adapter)                 ← 이게 없으면 S26 데이터가 전부 제외됨
2. 센서 이름 매핑 일반화
3. S26 CPU/GPU 기준선 재측정 (A24와 같은 프로토콜)
4. NPU 실행 경로 추가 (resource enum → Intent → engine → delegate 증거)
5. CPU/GPU/NPU 동일 기기 비교표
```

**1·2번을 건너뛰고 4번부터 하면 안 된다.** 측정은 되는데 `model_eligible=false`로 전부 걸러져서 데이터가 남지 않는다.

---

## 규칙

- **원본 보존**: 실패·중단 이력, 기존 판정을 지우지 않는다
- **0으로 대체 금지**: 미지원 조합·검증 실패를 측정값 0이나 null→0으로 바꾸지 않는다
- **증거 없음 ≠ 실패 증거**: delegate 증거가 없다고 CPU fallback이 확정된 게 아니다. `unverified`로 적는다
- **사후 기준 변경 금지**: 판정 기준은 결과를 보기 전에 기록한다. 바꿔야 하면 별도 버전의 탐색 실험으로 분리한다
- **해시·버전 기록**: 모델·APK·전처리·프로필·판정 정책의 버전과 해시를 남긴다
- **기기 혼합 금지**: 기기별 측정값은 하나의 자원 선택표로 직접 섞지 않는다

---

## 조민규님 작업과의 관계

조민규님도 S26 NPU 측정기를 만드는 중(2026-09-12 기준)이다. **중복 작업을 피하려면 착수 전에 분담을 맞출 것.**
제안 분담: 측정기 본체(runner NPU 실행 경로)는 조민규님, 기기 판별 일반화 + S26 CPU/GPU 기준선 재측정 + 판정·export 경로는 영훈.
