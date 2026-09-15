# s26/tools

S26 전용 보조 스크립트. 기존 `tools/`의 A24 검증된 스택은 **건드리지 않는다.**

## 있는 것

| 파일 | 역할 | 실행 시간 | 부작용 |
|---|---|---|---|
| `s26_collect.bat` | 기기 식별·열 센서·배터리·CPU 정보 수집 | 약 40초 | **없음 (읽기 전용)** |
| `s26_probe_npu.bat` | NPU·NNAPI 런타임 조사 | 약 15초 | **없음 (읽기 전용)** |

### 사용법

```
cd s26\tools
s26_collect.bat                 :: 기기 하나만 연결된 경우
s26_collect.bat R3KL3039J1V     :: 여러 대 연결된 경우 serial 지정
s26_probe_npu.bat R3KL3039J1V
```

결과는 `..\device\` 에 번호 붙은 txt로 떨어진다. adb는 `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`를 먼저 찾고, 없으면 PATH의 `adb`를 쓴다.

**USB 연결로 충분하다.** 두 스크립트 모두 안전 게이트를 타지 않는다.

### 전제

- 폰: 개발자 옵션 → USB 디버깅 ON, "이 컴퓨터에서 항상 허용" 승인
- 여러 기기가 붙어 있으면 `[0/8]`에서 목록을 보여주고 멈춘다 → serial을 인자로

## 넣을 예정

| 파일 | 역할 | 선행 조건 |
|---|---|---|
| `s26_device_adapter.py` | 기기 판별을 한 곳에 모은 설정 (`d1_logger_v4` / `orchestrator` / `thermal_dataset` 3곳이 공유) | 이식 항목 1 |
| `s26_prepare.ps1` | 측정 전 환경 세팅 (화면 타임아웃 연장, 원래 값 기록) + 종료 시 원복 | — |
| `s26_energy_verify.py` | 단계 2 — 1초 균일 샘플링으로 전류 적분 vs charge_counter 차분 교차검증 | 무선 adb |

## 규칙

- 기존 `tools/*.py`를 import해서 재사용하되 **수정하지 않는다.** 수정이 필요하면 본체 PR을 따로 올린다.
- 스크립트도 원시 출력을 그대로 파일로 남긴다. 파싱 결과만 남기지 않는다.
- 배치 파일은 **ASCII·CRLF**로 유지한다. 한글 echo는 코드페이지 문제로 깨진다.
- PowerShell 따옴표·경로 주의. 다중 기기 연결 시 `--serial` / serial 인자 필수.
