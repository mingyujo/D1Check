# S26 이전 담당자에게 전달할 자료 요청문

S26 후속 혼합 요청 시뮬레이터·사건 기반 CPU/GPU 정책을 준비 중입니다. **새 실험부터 돌리지 말고 현재 보존한 자료**를 부탁드립니다. 없거나 기록하지 않은 항목은 `없음/미기록/미확인`으로 답해 주세요.

이미 Git의 measure `0a07498`, mixreq `21cba44`, quality20 `5857152` 코드·manifest·공개 요청/전력/HAL·Q20 결과표와 보내주신 네 문서를 확보했습니다. 공개 파일 전체를 다시 보낼 필요는 없습니다.

우선 다음을 부탁드립니다.

1. **최신 현황·자료 위치**: 이후 전체 commit과 로컬 변경/완료 영수증, P1l 병행 모형과 GH7/8의 완료·실패·미실행 여부. 같은 상태면 변경 없다고 알려주세요.
2. **APK와 실제 빌드 소스 연결**: request v2 `591cae72…`, v3 `b97a9784…`, quality `bc9701e3…`의 source commit·당시 미커밋 diff/파일 SHA·빌드 freeze·의존성 버전·기존 설치 SHA 확인 기록. APK 자체는 우선 보존 위치/크기/SHA만 주세요.
3. **Q20 CPU/GPU 수치 출력 원본**: `q20_1009a/{CPU,GPU}/*.run{0,1}.f32le` 80개(본문 약320KB), path/bytes/SHA 목록과 runtime 생성~첫 이미지 구간의 기존 위임 logcat. 이미 있는 result JSON·참조표는 다시 보내지 않아도 됩니다.
4. **혼합 실행기 품질 연결**: quality↔request v2/v3 `Runtimes.kt`/옵션/전처리 diff와 warmup·raw 출력 근거, GPU의 요청 FP32와 실제 내부 정밀도를 구별한 기록(확인 불가면 그대로), 탐지CPU의 참조 출력·decoder/anchors·기존 품질 판정 근거. Q20는 분류만이므로 탐지 근거도 필요합니다.
5. **Git 밖 센서·시계 설명과 기존 계측 기록**: current/voltage/charge 단위·부호·시각·갱신주기, HAL와 요청 단조시계의 연결, 당시 before/after bracket이 있다면 원본, CC 검증·충전/화면/OS 변경 이력. 기록하지 않은 시각을 새로 만들 필요는 없습니다.
6. **mixed CPU1 프로필이 이미 있다면**: source/schema/계수, 개발·검증 session ID/실패·제외 목록, 등록·판독 코드·오차와 resident/단독·병행 구분을 주세요. 없다면 `mixed 프로필 미작성`으로 충분합니다.

네 R4S 실패 시도의 공개 progress에서 각2,800/2,830/2,839/2,842 요청의 반환 사건을 확인했습니다. 통합 `requests.json`이 없는 이유와 **공개 progress/개별 event 이외에 원 row snapshot이 보존돼 있는지**만 우선 알려주세요. 공개 failure/readout/driver 파일은 우리가 회수하겠습니다. 재실험이나 누락 후반 시각 복원은 요청하지 않습니다.

구 홀드아웃 1,200행 재현은 별도 목적입니다. 나중에 필요하면 최종 HTML·d1viewer·build/refs/repro·freeze·원 JSONL inventory를 요청하겠습니다. NPU 확장·전체 과거 archive·새 설치는 이번 우선 요청에서 제외합니다.

각 항목은 **있음/없음/미기록/미확인 + 위치/전체 commit + bytes/SHA-256 + 설명**으로 회신해 주세요. 개인 정보가 있는 원 logcat은 필요한 창만 정제해 비공개로 전달하고, APK·모델·키를 공개 Git에 추가하지 않아도 됩니다. 다음 기기 확인을 위해 동일 기기의 OS/설치 변경 여부와 사용 가능한 시점도 기존 기록 또는 현재 알고 있는 범위로 알려주세요.

작성만 완료했으며 자동 전송하지 않았습니다. 세부 요청 이유와 단계별 재개 조건은 `S26_REQUIRED_MATERIALS_20261011.md`에 있습니다.
