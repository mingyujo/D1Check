# S26 자료 회수 준비·기존 실패 사건 판독

2026-10-11 **S26-MATERIALS-PREP-01**. [전체 인계 계획](../../S26_REQUIRED_MATERIALS_20261011.md) · [복사해 전달할 요청문](REQUEST_TO_S26_OWNER.md).

기존 A24 파일럿은 종료된 상태다. 이번에는 S26 공개 자료와 사용자가 전달한 계약표의 남은 의존성을 정리했다. 새 학습0·시뮬레이션 실험0·물리 적합0·APK/ADB/기기0이다.

| 파일 | 내용 |
|---|---|
| `session_inventory.csv` | 기존 audit의 69manifest, 원 역할·통합 원장 유무·관측행·원 판정. 새 적격성 승인 아님 |
| `failed_prefix.csv` | 네 실패 시도, 예정12,000/관측 반환11,311/dispatch 관측 없음689. 원 실패 보존 |
| `event_timestamp_deltas.csv` | 대표 R4C 192요청에서 progress 기록시각과 exact 원장 경계의 차이(ns) |
| `verification.json` | 고정 HEAD·선택 source SHA/bytes·공개 파일 존재·집계 assertions·0회 실행 범위 |
| `analyze_existing.py` | 저장된 기존 audit와 고정 tree를 읽는 정적 분석 재현 source |

실패 시도는 통합 `requests.json`이 없지만 progress에는 요청별 반환 사건이 있다. log timestamp는 row timestamp 이후 기록되므로 exact phase/latency 복원으로 해석하지 않는다. 실패 시도의 수치 출력을 검증하거나 전체 요청·결과 파일의 SHA를 재검사한 것은 아니다. 기존 adapter PASS 48,480행과 prefix 사건11,311건은 서로 다른 근거이며 합산하지 않는다.

공개 R4S `session_failure.json`, readout/driver/inventory의 경로가 실제 고정 tree에 있음을 확인했다. sparse checkout에서 안 보인 파일을 공개 누락으로 잘못 요청하지 않는다. Q20 CPU/GPU 결과 tree는 각21 JSON만 있고 수치 `.f32le` 출력은 없어 이전 담당자의 별도 파일을 요청한다.

각 slot의 a1/a2는 session UUID와 request ID를 재사용한다. 측정은 시도 폴더/attempt와 시간 anchor까지 포함해 식별하고, UUID만으로 재시도를 제거하지 않는다.

재현 명령(기존 `s26_audit.json`과 같은 고정3tree가 준비된 PC, 개인 절대경로는 인자로 지정):

```powershell
python -B docs/results/s26_materials_20261011/analyze_existing.py --workspace '<고정3tree가 있는 폴더>' --prior-audit '<기존 s26_audit.json>' --out '<새 빈 결과 폴더>'
```

이 명령은 정적 분석용이며 Android/시뮬레이션/학습 함수를 호출하지 않는다. 이번 실행은 HEAD `13137fb499990cd2b31dc9ede2c4a927690b745b`＋본 문서/정적 분석 source 변경에서 위 명령의 인자만 실제 로컬 경로로 지정해 수행했다. 폰 판단시간·소비 에너지 또는 새 독립 기기 확인의 근거로 사용하지 않는다.
