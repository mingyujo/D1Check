# ENERGY-AP-DEVICE-SEGMENT-DIAG-03 실행 결과 — 2026-09-28

**결과: 중단, `stopped_no_resume`.** 승인된 plan SHA-256 `5ec12e31b90a17f6f56fdd38d077f0b244e4a19c2bf2ba99635343570ca09068`을 `Check` 후 1회 실행했다. 현재 A24·설치본·프로젝트 서명·환경 gate를 통과했고 새 APK SHA-256 `7589b96f18076c4bf7d178f3ae58c45c4e88348ef7f797ec5de60699d2e9c00d`의 push·데이터 보존 설치가 각각 1회 성공했다. 한 `CG_DC` 진단 세션에서 runtime 4·warmup 8·적격성 4호출은 시작·반환·lane 해제까지 기록됐다. **`probe.arm` 전 온도 준비 중 앱 `onDestroy`가 `lifecycle_cancelled`를 설정해 앱이 실패 종료**했다. 공식 baseline·본 부하·냉각·진단용 앱 자체 정상 완료는 없으며 추가 실행하지 않았다.

## numeric AP의 역할과 이번 판독

| 경계 | 확인 주체·규칙 | 연결·센서 실패 시 |
|---|---|---|
| 설치/세션 시작 | host `thermal()`이 AP mType=0 값을 기록하고 thermal status 0을 필수 확인; 화면·배터리·memory gate도 확인 | ADB 조회 실패·thermal status 위반은 중단. AP 값이 비어 있는 것만으로는 이 단계에서 단독 중단하지 않으며 아래 준비/분석에서 부적격 |
| `probe.arm` 전 | host의 resident 60초 AP 창: ≥20표본, 최대 gap10초·시계 불확실성≤2초, thermal 0. 고정 준비 120초 후 arm | 조건 미충족/읽기 실패면 arm 금지. 앱은 자체 360초 gate 상한 |
| 공식 baseline | host가 120초 AP 경로 ≥20표본을 확인하던 정식 경로와 달리, 새 **진단**은 앱이 arm 없이 다음 단계로 진행. host 관측은 사후 적격성 판정 | AP 결측이면 baseline/AP 분석 부적격. thermal status는 numeric AP 대체가 아님 |
| 실행 중·분석 | host가 연결 중 약 2초 AP 관측, 분석은 블록 AP gap≤10초·90초당 ≥20표본과 공통창 coverage 요구. 앱은 1Hz BAT·thermal status·화면·memory를 지속 확인 | numeric AP에 별도 실행 중 최고온도 중단 한도는 없다. host AP 소실은 자료 부적격·host 상태 미확인으로 기록하고 앱 성공으로 추정하지 않음 |

이번 세션에서 host AP 46표본(28.3–30.5°C), thermal status 0과 앱 전력/환경 표본 119개를 보존했다. 앱 화면 설정 표본은 모두 밝기81·수동·timeout18,000,000ms, 최저 배터리31%였다. 준비 AP 조건을 판정할 시점 전에 앱이 종료되어 `temperature_preparation_ready`와 `probe.arm`은 없다. AP 조건 위반이나 ADB 연결 소실이 이번 실패 원인이라는 증거는 없다. `baseline.ready`, `device_continuation`, 부하 구간 AP/에너지는 생성되지 않았다.

## 시간축·오류 계층

- host는 현재 단일 mDNS transport를 선택해 fingerprint/설치본을 확인했다. 모든 실행 client는 그 transport에 고정됐다. 513개 ADB client 기록에서 timeout은 0, 예상된 존재 확인용 exit 1 네 건 외 명령 실패는 없다. 의도적 연결 차단·자동 전환·재연결은 없었다.
- `warmup.arm`, `serial_probe.arm`은 전달됐고 host checkpoint에 `temperature_preparation_waiting`이 기록됐다. `probe.ready`에서 앱 실패 `cleanup`까지 105.175초. 앱 stack은 `EnergyCollectionActivity.healthy()` → `gate(probe)`이며 `stop=lifecycle_cancelled`; 이는 `onDestroy()`가 호출됐다는 코드상 경로다. **왜 Activity가 파괴됐는지는 원본에 기록되지 않아 미확정**이다. host의 첫 force-stop은 앱 실패 cleanup과 tar 회수 *뒤*여서 그 선행 원인으로 볼 수 없다.
- 앱 원본은 `session_failed`, `app_cleanup`, `cleanup.json(status=failed)`와 예외 종류·stack·스레드·단계를 보존했다. host는 `cleanup.json`을 보고 정상적인 완료 감시를 끝내고 14파일 archive를 회수했다. 이후 host cleanup의 force-stop·프로세스 부재·thermal 0 확인이 완료됐다. PC 요약기가 `summary.json` 부재를 `app completion/identity`로 거절해 host receipt는 `stopped_no_resume`가 됐다. 이 후속 오류는 원래 앱 `lifecycle_cancelled`를 지우지 않는다. 실패 처리에서 host cleanup이 한 번 더 호출된 기록도 원본에 남긴다.
- 이미 앱 terminal manifest/cleanup과 전체 archive가 회수됐으므로, 승인된 **조건부 사후 read-only 회수는 0회**다. 별도 회수를 중복 수행하지 않았다. 연결 소실 시 앱이 계속 실행되는지는 이번 실행에서 관측하지 못했다.

## 승인 대비 실제 소비

| 항목 | 승인 상한 | 확인된 소비 |
|---|---:|---:|
| 세션 | 1 | 1시도·0완료 |
| runtime / warmup / 적격성 / 본 작업 | 4 / 8 / 4 / 1,680 | 4 / 8 / 4 / **0** (앱 실패 stack·완결 journal) |
| 명시적 추론 | 1,692 | 12반환·lane 해제 확인 |
| staging | 1회·7파일 | 1회·7파일 |
| 설치본 확인 pull / APK push / 설치 | 각 최대1회 | 각 1회 성공, 설치 SHA 일치 |
| ADB / 본 실행 시간 | 11,000 / 2,700초 | 513 / 193.094초 |
| 조건부 사후 회수 | 12명령 / 90초 | 0 / 0초 |
| 재시도·대체·추가 | 0 | 0 |

설치 preflight는 53.531초였고, APK push 12.437초·설치 23.156초·이전 설치본 확인 pull 10.547초가 단계 기록에 있다. APK 재전송·재설치나 이 계획의 재시작은 금지한다. host의 호출 부재만으로 0이라 정한 것이 아니라, 앱의 실패 지점·완결 journal·cleanup에서 본 부하 미진입을 확인했다.

## 자료·모형 판정과 보존

정식 개발 3세션·동결 모형·DC_DG 확인은 수정하지 않았다. 이번 새 APK/계측 경로는 프로토콜 전이 진단이고 CG_DC·CC_DG의 동일 조건 확인으로 합치지 않는다. baseline/부하·냉각이 없어 공통창 에너지, AP 예측 오차, 모형 정확도나 연결 소실 내성을 계산할 수 없다. `experiment_ready=false`, 기존 FAIL·원자료·종료 계획을 유지한다. A24 raw 전류=mA 조건부 해석과 절대 J 정확도 미인증도 동일하다.

원본: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_device_segment_diag_run_v3\FINAL_RECEIPT.json`, 같은 폴더의 `host_checkpoints`, `host_commands`, 세션 `artifacts`·`artifacts.tar`; archive SHA-256 `a090c9803f5b5dd3fc97b8534edf4eae4d4d0d4a5f85b4b4b0765e9519b73964`. 별도 registry의 `stopped.json`과 계획 폴더 `host_entry_*/end.json`을 보존한다. [작은 요약](results/energy_ap_device_segment_01/diag03_summary.json)은 원본과 분리했다.

재현(PC 읽기 전용): 아래 명령으로 원본 종료 상태와 앱의 마지막 단계·호출 기록을 다시 읽을 수 있다. `Check`/`Run`은 소비된 계획에 다시 호출하지 않는다.

```powershell
$r='C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v3'
python -B -c "import json,pathlib,collections; r=pathlib.Path(r'$r'); s=next(r.glob('00_*')); h=json.loads((r/'FINAL_RECEIPT.json').read_text(encoding='utf-8')); a=[json.loads(x) for x in (s/'artifacts/progress.jsonl').read_text(encoding='utf-8').splitlines()]; print(h['status'],h['error'],h['adb_command_slots']); print(collections.Counter((x.get('phase'),x.get('kind')) for x in a if x.get('kind') in ('request_start','worker_release','lane_available','session_failed','app_cleanup')))"
```

다음 한 작업은 재측정이 아니라 `onDestroy` 원인 경계와 실패 후 host cleanup 중복 호출을 PC 기록·코드로 좁히는 것이다.
