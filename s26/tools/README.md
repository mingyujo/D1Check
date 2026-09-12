# s26/tools

S26 전용 스크립트 자리. 아직 비어 있다.

기존 `tools/`의 A24 검증된 스택은 **건드리지 않는다.** 여기에는 S26 작업에만 필요한 보조 스크립트를 둔다.

## 넣을 예정

| 파일 | 역할 | 선행 조건 |
|---|---|---|
| `collect_device_profile.ps1` | `docs/S26_DEVICE_PROFILE.md` §1~§4를 adb로 자동 수집해 원문 저장 | S26 연결 |
| `probe_npu.ps1` | logcat clear → NNAPI 프로브 유도 → `D1NPU` 로그 추출 | Benchmark Runner 설치 |
| `s26_device_adapter.py` | 기기 판별·센서 별칭을 한 곳에 모은 설정 (`d1_logger_v4` / `orchestrator` / `thermal_dataset` 3곳이 공유) | 이식 항목 1·2 |

## 규칙

- 기존 `tools/*.py`를 import해서 재사용하되 **수정하지 않는다**. 수정이 필요하면 본체 PR을 따로 올린다.
- 스크립트도 원시 출력을 그대로 파일로 남긴다. 파싱 결과만 남기지 않는다.
- PowerShell 따옴표·경로 주의 (기존에 자주 깨진 지점). 다중 기기 연결 시 `--serial` 필수.
