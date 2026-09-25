# ENERGY-THERMAL-COLLECT-03 실행 결과 — 첫 개발 세션 기술적 중단

2026-09-25. 실행 소스 HEAD `ffe2d32ce91211e42f15610b10715ad626cb4d96`, 작업 브랜치 `feature/arrival-scheduling-20260923`, 시작 clean. 사용자 승인8세션/6976진단/64warmup/7040추론/220분에 따라 plan_v5 스크립트를 정확히1회 실행했다. plan SHA-256 `8285b8d9d4d4fac9e70477d50ee6875aef3075c042e60ae71a600d3ee65cc01e`. **현재 stopped_no_resume, 재시도·대체·추가0.**

## gate·실행과 소비

현재 연결 A24 `192.168.219.103:39995`, SM-A245N/hardware R59W802RW5F/fingerprint 일치. 시작85%·비충전·28.2°C·thermal0·Awake/interactive·밝기81/수동0/자동꺼짐18000000ms를 실제 조회했다. 설치본 hash/프로젝트 signer가 후보와 일치해 **APK 전송0·설치0**. 모델·입력 staging1회/7파일, 세션 launch1회. 앱 resident memory admission과 warmup/적격성/기준온도 gate 통과 후 첫 CC_DG 직렬 부하를 시작했다. 새 설정 변경 없음.

| 항목 | 실제 기록 / 계획 분모 |
|---|---|
| 개발 | 시도1·완료0·기술적 실패1·미시도3 /4 |
| 확인 | 시도0·완료0·미시도4 /4 |
| runtime | 시작4·반환4 /32 |
| warmup | 시작8·반환8 /64 |
| 적격성 진단 | 시작2·lane 해제2 /16 |
| 작업 진단 | 시작645·lane 해제644 /6960 |
| 진단 합계 | 시작647·lane 해제646 /6976 |
| 명시적 host inference | 시작654·성공654의 기록 /7040 |
| staging | 1회·7파일 /8회·56파일 |
| 설치·APK 전송·재시도·대체·추가 | 모두0 |

작업 lane 해제644건은 모두 classification_CPU다. load-0-644는 request_start 이후 admission이 기록됐으나 host_inference 이벤트 없이 중단됐다. 요청 시작을 추론 완료로 세지 않는다. journal9407행 sequence 연속, 최종 app_cleanup 이벤트 및 cleanup.json까지 회수했다. **원 receipt의 보수적 상한(마지막 세션 작업 시작645~870, 진단647~872)은 수정하지 않는다.** 654는 직접 관측된 호출 수이며 미관측 호출을 성공으로 채우거나 다른 미시도 세션의 예정량을 실제로 세지 않는다.

## 중단 원인과 cleanup

앱 기록의 직접 원인: `stopped: sample: java.util.NoSuchElementException/null`. `EnergyCollectionActivity.kt`의 1초 sampler가 `snapshot()` 또는 이벤트 생성 중 예외를 받아 stop을 설정했고 scheduler의 healthy 검사가 이를 감지했다. host의 `app cleanup/completion` 오류는 실패한 앱 산출물을 적격 완료로 인정하지 않은 후속 판정이다. 이번 중단은 화면 query timeout이 아니다.

코드상 `snapshot()`은 다른 thread가 수정하는 ConcurrentHashMap `active`에 `toMap()`을 호출한다. 크기 분기와 iterator 사이 변경 가능성은 검토할 구체적 후보다. **예외 stack trace가 저장되지 않아 실제 발생 행은 미확정**이며 Kotlin 변환·다른 snapshot API 중 원인을 이 기록만으로 확정하지 않는다. GPU 결함·옛 CAL-02 또는 화면 timeout과 같은 원인이라고 주장하지 않는다. 이번에는 실행 코드/APK를 수정하거나 추가 기기 실행하지 않았다.

앱 `app_cleanup` 이벤트와 cleanup.json은 존재하지만 status=failed이며 기존 sample 예외를 포함한다. 코드상 lane close 이후 작성되는 이벤트이고 추가 close/flush 예외 문자열은 없지만 각 runtime 해제를 별도 성공 증명하는 기록은 없다. **정상 세션 완료가 아니다.** host 정상 회수/cleanup 뒤 검증 실패 경로의 prefix 회수·cleanup도 수행했다. 두 host cleanup 모두 completed, 마지막 ps에서 앱 프로세스 부재, thermal0 확인. tar654파일과 원본 prefix를 보존했다. 회수 실패를 앱 실행 실패와 혼동하지 않는다.

원 receipt elapsed277.485초는 최종 실패 회수/cleanup 전 값이다. claim UTC→마지막 cleanup 조회 종료 UTC는 **279.631초**(벽시계 기준), 첫 기록 client→마지막 client monotonic 범위277.906초다. 별도 사전 환경 gate4.359초, 사전 gate 시작→마지막 cleanup까지294.617초(벽시계)이며 PC Check/상태 확인을 포함해도220분 상한 이내다. 서로 다른 시계를 직접 빼지 않았고 원 receipt는 재기록하지 않았다.

## 부분 분석과 비교 불가 범위

원본을 변경하지 않는 `tools/d1_energy_collection_partial.py`로 journal·thermal·화면·host 기록을 집계했다. 기존 에너지 적분 함수/단위 가설을 사용했다. 기존 실측/전체 테스트/배치는 재실행하지 않았다.

- 실제 수집 세션 화면 gate/poll **23/23 성공**, 최대0.719초. 기록된 범위의 부하 동작일 뿐 이후 안정성·과거 timeout 해결·내부 dumpsys 비용 감소를 증명하지 않는다.
- 저장된 power sample237개는 배터리84%·28.2°C·비충전·thermal0·interactive/admission 조건을 만족했다. 연속 미관측 구간을 보장하지 않는다. host AP 관측27.8~32.4°C(센서 온도, 표면/주변온도 아님).
- resident baseline120.015초: 기기 전체 **139.089J**, 평균1.159W.
- 부하 시작→마지막 저장 power sample101.322초: 기기 전체 **191.764J**, 평균1.893W. 같은 세션 baseline 평균 대비 추가 추정 **74.340J**.
- 위 에너지는 A24 raw를 mA로 해석한 조건부 적분이며 절대 정확도는 미인증. 기기 전체 소비이지 CPU 직접 소비가 아니다. 부분 관측 완료량과 적분 종료는 같은 경계가 아니므로 요청당 에너지로 나누지 않는다.
- 부하 종료·동일 작업량 완료·공통480초 창·냉각은 미완료. 해당 에너지/완료시간은 **미산출**이다. 병행 표본0, 직렬/병행 overlap 비교 불가. 기존 run_v2 부분에너지를 합치지 않는다.

개발 적격 완료0으로 추정 동결 없음, 확인0. 조건당 개발1/확인1 설계는 애초 독립 세션 각1의 제한이며 현재는 그 조건도 채우지 못했다. 정책 우월성·열/에너지 절감·시뮬레이터 적격성 PASS 없음. 기존 FAIL·부분 결과·40값·20null·종료계획·experiment_ready=false 유지.

## 다음 최소 행동

**PC에서 ConcurrentHashMap snapshot 변환의 변경 경쟁과 예외 stack 보존을 점검·재현하는 한 묶음**이 우선이다. 이번 결과만으로 timeout을 늘리거나 전체8세션 새 수집을 자동 준비/실행하지 않는다. 원인이 확인되면 최소 수정·관련 실패 경로 검증 후 별도 승인 범위를 정한다. 원인이 확인되지 않으면 그 사실을 유지한다.

## 근거와 재현

외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension`:
- `energy_collection_preflight_v3/receipt.json` 및 실제 환경 원문
- `energy_collection_run_v3/FINAL_RECEIPT.json`, 첫 세션 `artifacts/progress.jsonl`, `cleanup.json`, recovery_prefix/failure_prefix, `host_cleanup.json`, `failure_host_cleanup.json`, host_commands
- `energy_collection_registry/ENERGY-THERMAL-COLLECT-03/claimed.json`, `stopped.json`
- `energy_collection_analysis_v3/partial_summary.json` 및 `FINAL_REPORT.md`

[공유 요약](results/energy_collection_execution_03/partial_summary.json). 상세 원자료/APK/키는 Git에 포함하지 않는다.

```powershell
python -B -m tools.d1_energy_collection_partial --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v3 --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_analysis_v3/partial_summary.json
```
위 명령을 실제 실행했다. 재현 시 기존 output을 덮어쓰지 않도록 새 파일명을 사용한다. 실행 계획은 소비됐으므로 RUN_AFTER_APPROVAL을 다시 실행하지 않는다.
