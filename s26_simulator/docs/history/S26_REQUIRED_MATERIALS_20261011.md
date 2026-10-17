# S26 후속 진행에 필요한 자료와 인계 순서

작업 ID: **S26-MATERIALS-PREP-01** / 2026-10-11 / 상태: **기존 자료 추가 판독·인계 준비 완료, 새 모형·정책 성능 검증 보류**.

이번 후속 작업은 기존 소스·원장·사건 로그의 읽기와 문서 작성이다. 신규 학습 **0회**, 신규 시뮬레이션 실험 **0회**, 신규 물리 모형 적합 **0회**, APK 빌드·설치·ADB·기기 실행 **0회**다. 완료된 A24 파일럿의 **791환경/192학습** 및 과거 프로젝트 실행 이력은 보존한다. 첨부 문서의 재현·재피팅·설치 명령은 참고 자료이며 실행 지시로 취급하지 않았다.

## 1. 지금 이어갈 방향

A24의 사건 기반 후보·물리 마스크·직접 선택 구현과 원 strict 판정은 완료됐다. 세 PPO가 모두 strict FAIL이고, 확인의 25,352판단에서 ATC/EDD 후보 bank와 유효 행동이 같았다. ATC 튜닝이나 닫힌 학습 예산의 추가 사용을 시작하지 않는다. 후속 후보는 **EDD 후보 + 직접 규칙/직접 PPO 비교**로 남기되, 기존 기본 정책을 교체하지 않는다.

S26에서는 이 사건 루프의 계약을 재사용할 준비를 하고, 먼저 **실제 혼합 요청 실행기와 품질·서비스·센서 자료를 연결**한다. 그 뒤 기기별 프로필을 동결해야 정책 비교를 시작할 수 있다. A24의 서비스·열·전력 계수나 기존 PPO 가중치를 S26에 그대로 옮기지 않는다. FIFO 선두, 요청 응답과 lane AVAILABLE의 분리, 실제 자원 반환, 최대 두 건의 검증 병행을 유지하며 NPU 확장은 이번 목표에 포함하지 않는다.

[기존 S26 모형 계획](S26_SIMULATION_PLAN_20261011.md), [실제 직접 선택 파일럿](ATC_PPO_DESKTOP_PILOT_20261011.md), [이전 제출 범위·품질 계약](team/S26_SCOPE_AND_INTERFACE_20261004.md)을 함께 따른다. 혼합 프로필 연구는 과거 S26 제출 범위의 완료 판정을 바꾸지 않는다.

## 2. 이미 확보한 것 — 중복 요청하지 않을 자료

| 확보한 자료 | 확인 범위 | 남은 한계 |
|---|---|---|
| `s26-measure` 고정 HEAD `0a0749890fba2452c5907433c6bea476a2da7e24` | d1sim 엔진·구 모형·정책 코드, 첨부 표의 22개 source/profile 바이트 또는 LF 정규화 일치 | MobileNet/CPU4/합성 입력/FG-BG chunk 계수가 최신 CPU1 혼합 요청 프로필은 아님 |
| `s26-mixreq` 고정 HEAD `21cba44faa5fff1fb9703b590aa536a6207f8de5` | 69개 manifest, 통합 원장 관측 48,480행의 7구간→5phase 정적 대응 | 69개가 모두 독립 유효 본 세션은 아님. smoke·warmup·실패를 구분 |
| `s26-quality20` 고정 HEAD `5857152ad8244c41975843ded77dd33024f38f2d` | Q20 manifest·이미지별 result JSON·판정·위임 집계·실행 코드 | 수치 출력 `.f32le` 자체는 해당 결과 tree에 없음. 별도 quality-runner의 결과 |
| 사용자 추가 네 문서 | APK 계약표·모형/세션/계수 연결표·재현 README·홀드아웃 검사 스크립트 | 타 환경 재현 주장을 읽었으며 이 PC에서 구 홀드아웃 1,200행 재실행은 하지 않음 |
| 공개 R4S 자료 | 실패 네 시도의 progress/HAL/manifest/validation, 공개 failure JSON·readout·driver 파일의 존재 | 개인 logcat 등 Git 밖 자료는 미판독. 통합 requests.json 미생성 원인과 복구 가능 범위는 분리 |

2026-10-11 `git ls-remote --heads`에서 위 세 HEAD가 그대로임을 확인했고 `s26-parsim` 공개 branch는 조회되지 않았다. 따라서 기존 문서의 P1l 병행 프로필/GH 후속 완료 여부는 이전 담당자의 최신 영수증으로 확인해야 한다. 공개 branch가 없다는 사실만으로 로컬 작업도 없다고 단정하지 않는다.

R3/R4C는 각각 16×192요청, R4S는 16슬롯·18시도 중 유효14/실패4와 별도 준비·중지2다. 이미 본 자료의 재분석은 회고 개발·전이 판독이며 새 미열람 독립 확인이 아니다. NPU 포함 block N과 CPU/GPU block A, resident4/5, APK v2/v3를 한 프로필로 합치지 않는다.

## 3. 이번에 더 확인한 실패 자료

통합 `requests.json`이 없는 네 시도에도 공개 progress에 모든 예정 요청의 arrival 사건과 다음 수의 dispatch/output/persist/worker release/lane available 사건이 남아 있다. request ID의 고유성·manifest 포함 관계·각 단계의 ID 일치를 정적으로 확인한다. 세션별 원 실패와 원 readout 판정은 유지한다.

| 시도 폴더 끝부분 | 예정/arrival | 관측 dispatch·output·persist·AVAILABLE | 관측 dispatch 없는 요청 |
|---|---:|---:|---:|
| `13_CPU_URGENT_ONLINE_V1_a1` | 3,000 | 2,800 | 200 |
| `13_CPU_URGENT_ONLINE_V1_a2` | 3,000 | 2,830 | 170 |
| `14_CPU_URGENT_ONLINE_V1_a1` | 3,000 | 2,839 | 161 |
| `14_CPU_URGENT_ONLINE_V1_a2` | 3,000 | 2,842 | 158 |

합계 12,000예정 중 해당 반환 사건이 있는 요청은 11,311, dispatch 관측이 없는 요청은 689다. 이는 **관측 prefix의 사건 수**이며 새 성공·품질 판정이나 정확한 요청 원장 복원이 아니다. 기존 48,480 adapter PASS행에 합쳐 59,791 exact 행이라고 보고하지 않는다. 원 readout이 원장 부재로 기재한 수치도 덮어쓰지 않는다.

소스 `SessionEngine.kt`는 요청 row의 시간 필드를 기록한 뒤 별도 `event()`를 호출한다. 대표 R4C 192요청에서 progress `request_start.mono_ns`는 row `execution_start_ns`보다 최대 **1.359297ms**, `lane_available.mono_ns`는 row `lane_available_ns`보다 최대 **1.124570ms** 늦었다. 이 한 세션의 차이를 전체 실패 시도의 오차 상한으로 전용하지 않는다. 따라서 progress 시각을 정확한 7경계 원장 필드로 바꿔 넣거나 누락 종료 시각을 보간하지 않는다.

현재 확보하지 않은 공개 파일은 Git의 경로/commit으로 우리가 선택 회수할 수 있다. 실패 네 시도의 원본 전체를 다시 보내 달라는 요청은 우선 제외한다. 필요하면 `.event.json`과 공개 readout을 추가 분석하되 `.event.json` 저장이 실제 lane_available 이전이라는 코드 경계도 유지한다.

검산 결과와 원 근거 경로/SHA는 [추가 판독 기록](results/s26_materials_20261011/README.md), [실패 사건 표](results/s26_materials_20261011/failed_prefix.csv), [로그/원장 시간 차이](results/s26_materials_20261011/event_timestamp_deltas.csv), [자료 보유 표](results/s26_materials_20261011/session_inventory.csv)에 있다.

13의 a1/a2는 같은 session UUID와 request ID를 재사용하며 14도 같다. 재시도를 session UUID만으로 중복 제거하면 실제 실패 시도를 잃는다. 측정 식별자는 **고정 source tree + 시도 폴더/attempt + session UUID + 시간 anchor**로 두고, 동일 raw byte가 다른 export로 복사된 경우에만 원 측정과 연결해 한 번 센다. 동일 계획/요청 hash는 동일 측정의 증거가 아니다.

## 4. 이전 담당자에게 받을 자료 — 우선순위와 용도

먼저 **이미 있는 자료**와 위치를 요청한다. 없거나 당시 기록하지 않았다면 `없음/미기록/미확인`으로 답하면 된다. 자료 요청을 새 측정·새 설치·재피팅 지시로 바꾸지 않는다.

| 우선 | 받을 것 | 최소 내용·형식 | 이 자료로 해결할 질문 |
|---|---|---|---|
| P0-1 | 최신 작업 인덱스·완료 영수증 | 현재 branch/전체 commit, 작업명·등록/완료/실패/중단, 자료 위치, 최신 P1l 병행 프로필·GH7/8 여부. 이미 받은 세 HEAD 이후 변경이 없으면 그렇게 명시 | 고정 source와 로컬 후속 결과가 같은 계보인지, 이미 있는 프로필을 재개발할 필요가 있는지 |
| P0-2 | 실제 APK→빌드 소스→세션 연결 근거 | request v2 `591cae72…`, v3 `b97a9784…`, quality `bc9701e3…`의 전체 source commit, 당시 미커밋 diff 또는 파일 SHA, 빌드 freeze/명령/의존성 버전, 기존 설치본 SHA 영수증. APK 파일은 보존 여부/크기/SHA만 먼저 회신 | 빌드보다 늦은 commit을 exact source라고 추정한 부분을 해소하고 Q20 runtime 사본의 실제 연결을 검증 |
| P0-3 | Q20 CPU/GPU 수치 출력 원본과 원 위임 로그 | `q20_1009a/{CPU,GPU}/*.run{0,1}.f32le` **80파일, 출력 본문 약320,000byte**와 inventory(path/bytes/SHA), 원 logcat의 runtime 생성~첫 이미지 창. 이미 있는 JSON/참조 표는 재전송 불필요 | 요약만 읽은 상태에서 20장×2회 출력과 기존 판정기를 PC에서 재검산. 이는 분류 참조 일치이며 정답 정확도 인증이 아님 |
| P0-4 | request-runner 품질 전이 근거·GPU 정밀도 근거 | Q20와 request v2/v3의 `Runtimes.kt` 및 생성 옵션/전처리 변경 diff, 동일 입력 hash, request warmup/raw 출력/실제 위임 증거. GPU 요청 FP32와 실제 내부 연산/누산을 구별하는 기존 기록 또는 `확인 불가`. **탐지CPU 품질/decoder/anchors/출력 참조 근거도 별도** | 분류CPU/GPU·탐지CPU·CG_DC를 새 정책 후보로 승인할 수 있는 범위. Q20는 탐지를 검증하지 않았고 같은 모델/LiteRT만으로 다른 APK를 인증할 수 없음 |
| P1-1 | Git 밖 센서·시계 계약 및 계측 기록 | API/필드/단위·부호·유효값·샘플 시각 정의·갱신주기, 기존 clock before/after bracket이 있다면 원본, CC 눈금/단위 검증, 충전·화면·OS변경 이력. 공개 progress/HAL/driver/readout은 경로만 대응 | AP/SKIN 정렬과 J의 coverage·내부 일관성·불확실성. 기록되지 않은 bracket/sample age를 사후 생성하지 않음 |
| P1-2 | 최신 mixed CPU1 모형 또는 아직 없는 항목의 목록 | profile/schema/adapter source·계수, 개발/검증 session ID와 제외/실패 목록, fit/선택/판독 등록·버전·오차·시간창, 단독/병행 state 노출·resident 집합. P1l이 있다면 정확한 산출물/FAIL 포함. 없다면 `mixed 프로필 미작성` | 기존 MobileNet/CPU4/chunk와 구분되는 유한 S0/S1·T0/T1·E0 계약의 출발점. 기존 계수를 복사해 빈칸을 채우지 않음 |
| P2 선택 | 구 시뮬 홀드아웃 재현 패키지 | 최종 HTML SHA, `d1viewer/check_equal`와 웹 build/bundle/refs/repro, freeze·원 JSONL path/bytes/SHA·의존성. 전체 원자료는 특정 불일치가 발생한 뒤 선택 요청 | **구 d1sim v2.2의 행 재현**을 별도로 확인할 때만 필요. 혼합 요청 직접 PPO를 시작하는 필수 gate는 아님 |

P0-2/4의 CPU `threads=1`은 설정값과 실제 실행 관측을 구분한다. runtime 사본 동일성은 버전명만 아닌 파일/옵션 비교로 확인한다. GPU dtype=float32, top1 일치, LITERT_CL 위임만으로 내부 FP32를 확인했다고 쓰지 않는다. 새 품질 계약이 필요하면 기존 Q20 보류를 보존하고 별도 사전 등록 후 새 독립 자료에서 확인한다. 기존 허용식을 결과에 맞춰 늘리지 않는다.

P1-1의 중요 한계: 대표 R4C 정기 power_sample239와 admission204를 합쳐 적분하지 않는다. 전류 raw는 방전 음수, 등록 해석은 μA이나 기기 scale/절대 정확도는 미인증이다. HAL의 `device_boottime_s`와 요청 단조시계를 연결하고 PC wall clock으로 latency를 만들지 않는다. 기존 E_int/E_cc 약4% 차이와 정책 짝차 부호 역전을 gain 조정으로 지우지 않는다. 과거 긴 창의 조건부 동등성 판정을 새120/720초의 J 정확도로 전용하지 않는다.

NPU 품질 출력/AOT/도구·3자원 동시 실행 자료는 이번에 요청하지 않는다. 과거 block N 자료는 실패·선택 편향 및 resident5 전이 분석을 위해 보존하되 NPU를 새 행동으로 넣지 않는다. APK·모델·키·개인 로그 전체를 공개 Git에 올리도록 요청하지 않는다. 기존 원 URL/비공개 보관 위치·정제한 필요한 기록부터 받는다.

## 5. 첫 번째 전달 묶음과 응답 양식

첫 묶음은 **P0-1/2/3/4 + P1-1의 설명표**면 된다. 공개 R3/R4C/R4S 107,032파일 전체나 과거 1.76GB 열 모형 archive를 다시 받을 필요는 없다. Q20 CPU/GPU 출력80개는 기존 Git 밖 파일이므로 작은 별도 묶음으로 받고, 원 PNG/모델/APK는 재검산 목적이 생긴 뒤 선택한다. 기존 입력20/CPU reference 인계 zip은 현재 manifest/참조와 연결되므로 수신 여부와 원본 위치를 확인하고 중복 제작하지 않는다.

각 항목에 `있음/없음/미기록/미확인`, 전체 commit 또는 상대경로, bytes, SHA-256, 측정/등록 시각, 설명을 붙인다. 바이너리와 JSON의 hash는 원 byte 기준이다. Git text의 LF/CRLF 차이는 별도 정규화 비교로 표시하며 원 hash를 바꾸지 않는다. 사용자/기기 식별정보를 가리면 정제본 hash와 원본 private hash를 구분한다.

복사해 전달할 짧은 요청은 [담당자 요청문](results/s26_materials_20261011/REQUEST_TO_S26_OWNER.md)에 있다. 이 문서를 작성했으며 실제 전송은 하지 않았다.

## 6. 자료가 오면 진행할 일과 gate

| 단계 | 진행할 작업 | 완료/보류 조건 |
|---|---|---|
| I0 수신 정적 확인 | 파일 inventory/hash/소스diff/원등록·결과 연결, 공개 자료 중복 제거 | Q20 raw를 재검산하더라도 APK 간 품질 전이를 자동 PASS로 만들지 않음 |
| I1 실행 적격성과 서비스 adapter | 승인된 CPU/GPU 경로·FIFO/7경계/응답/AVAILABLE/병행 및 실패 prefix를 정리 | 분류CPU·탐지CPU의 근거만 충족하면 그 범위의 CPU-only 서비스 진단은 가능. GPU가 미해결이면 CG_DC/라우팅 효과 평가와 학습은 보류 |
| I2 센서 coverage·state 식별 | current/CC/HAL 창·gap·resident4/5·단독/병행 노출·pair/day 분리 | 서비스·AP·SKIN·J를 각각 판정. J 미해결이면 서비스/열 연구는 가능하나 원 에너지 목표·strict 충족이나 에너지 보상 PPO 완료로 부르지 않음 |
| I3 유한 모형 계약 | S0/S1·T0/T1·E0 후보, 오차 기준·자료역할·호출/시간 상한 사전 고정 | 아직 혼합 프로필이 없으면 여기서 새 적합/검증 계획을 구체화. 이번 후속 작업에서는 fit·실험 실행0 |
| I4 고정 정책 비교 | 동일 요청·물리지원·기한·완료창에서 기존 S26 정책/EDD/ATC 직접 규칙 및 필요한 직접 PPO 비교 계획 | ATC/EDD가 동일하면 튜닝 중단. 새 상태/행동/기기 관측이면 fresh PPO, 학습/개발/최종 자료와 RNG 분리 |
| I5 독립 확인 | model/config/APK/품질/분석/최소 측정 질문·실행 예산 동결 | 현재 R3/R4C/R4S는 이미 본 자료. 필요할 때 새 기기 실행을 별도 등록하고 실패/중단까지 남김 |

일반적인 자료 대응은 PC에서 진행한다. 닫힌 A24 task를 재개하거나 S26 성능을 가상으로 채우지 않는다. 이번 신규 성능 실험 예산은 **0환경/0학습/0기기**다. 다음 적합·실험의 상한은 자료 적격성과 식별성 확인 뒤 새 계약에 수치로 등록할 값이며, 남은 A24 cap을 S26 승인으로 승계하지 않는다.

직접 정책의 이벤트→후보→mask→추론에는 전체 대기 큐의 미래 drain/응답/J/열 rollout을 다시 넣지 않는다. 평가 환경의 미래 정답과 정책의 현재 관측 API를 분리한다. 물리 mask는 서비스나 strict 합격을 보장하지 않는다. 실기기 HAL 입력·현재 관측 보정도 A24 환경 관측과 다른 adapter이므로 독립적으로 검증한다.

## 7. 남는 사용자 결정

지금 자료 회수와 정적 감사에는 추가 결정이 필요하지 않다. 자료를 확인한 뒤 필요한 경우에만 ① 품질 gate를 충족한 CPU-only 진단을 먼저 할지, GPU까지 연결 후 혼합 정책 비교를 할지, ② 새 독립 기기 확인의 한 질문·기기 사용 가능 시점·실행 예산을 정한다. 기존 strict나 품질 기준의 완화는 이번 선택지에 넣지 않는다.

## 8. 사실·설계 선택·미확인 사항과 근거

| 구분 | 내용 | 근거 |
|---|---|---|
| 확인된 사실 | A24 세 strict FAIL, ATC/EDD 동일, 완료된 예산·원장 | `docs/results/atc_ppo_desktop_pilot_01/README.md`, `schedule_identity.csv`, `summary.json` |
| 확인된 사실 | S26 고정3tree·69manifest/48,480 adapter행·Q20의 APK 귀속 | `s26_audit_summary.json`, 기존 `s26_audit.json`, 사용자 APK 계약표/계수 연결표 |
| 이번 추가 사실 | 실패 progress의 request ID·사건 수, 대표192요청의 로그시각 차이, 공개 failure/readout 존재 | `results/s26_materials_20261011/verification.json` 및 해당 CSV, mixreq 고정 tree `SessionEngine.kt` |
| 설계 선택 | P0 기존자료부터, 공개 원장 중복 요청 제외, Q20 CPU/GPU raw80개 우선 | 실제 tree inventory와 Q20 result JSON에 있는 output_file/sha |
| 설계 선택 | 직접 사건 루프 재사용, fresh 기기 프로필/모델, 최소 S0/S1·T0/T1·E0 | 기존 직접 설계·파일럿과 `S26_SIMULATION_PLAN_20261011.md` |
| 미확인 | 실제 APK/source exact 연결, GPU 내부 precision, mixed 품질 전이, private sensor/clock 증거, 최신 P1l/GH 로컬 결과 | 위 P0/P1 요청. 없음/미기록이면 지원·결론 범위를 제한 |
| 미확인 | 새 mixed 모형의 서비스/열/J 예측 오차, 새 독립 확인, 휴대폰 판단시간/에너지 | 이번 후속 신규 fit/실험/학습/기기0. PC static 판독 시간은 폰 성능 근거가 아님 |

작업 시작 Git은 `feature/arrival-scheduling-20260923`에 게시된 `13137fb499990cd2b31dc9ede2c4a927690b745b`의 별도 detached checkout이며 시작 tree는 clean이었다. 원 사용자 변경이 있는 다른 checkout은 수정하지 않았다. 검증 기준 HEAD와 이번 문서/집계 source SHA는 verification에 기록한다. 적용 지침은 repository root `AGENTS.md`다.
