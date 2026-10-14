# A24 실측 시작 전 별도 기기 확인

이 목록은 **나중의 기기 작업용**이다. 이번 사전 준비에서는 아래 조회·연결·설치·실행을 한 번도 수행하지 않는다. PC 검사와 APK 서명 검사는 기기 검증을 대신하지 않는다.

| 단계 | 아직 확인할 것 | 현재 상태 |
| --- | --- | --- |
| 대상·연결 | 단일 A24 serial, model, fingerprint, Android 버전, 드라이버와 고정 연결 방식 | DEVICE_UNVERIFIED |
| 설치·동일성 | 준비 APK SHA·서명과 설치 package의 일치, base/:model_probe/:a24_preparation PID와 중복 owner 없음; 조회 오류도 차단 | DEVICE_UNVERIFIED |
| 원물 | 기기로 옮긴 모델·labels·anchors·승인 PNG의 bytes/SHA 및 tensor SHA | DEVICE_UNVERIFIED |
| 런타임 | CPU 1 thread, LiteRT 1.4.2, strict GPU 설정·full delegation·무 silent fallback·출력 동등성 | DEVICE_UNVERIFIED |
| 공통 준비 | C_CPU/C_GPU/D_CPU/D_GPU 4개 상주·정해진 순서·각2 warmup, I unresident는0개 | DEVICE_UNVERIFIED |
| 환경 | 화면/밝기·통신·폰 위치/접촉·주변온도·SOC·방전/충전·USB 부하의 공통 조건 | DEVICE_UNVERIFIED |
| 계측 | 전류/전압/전하 단위·부호·실제 갱신주기·읽기 지연·결측·캐시, AP HAL 이름/유형 | DEVICE_UNVERIFIED |
| 시작 gate | runtime/warmup 준비 후 최소60초 AP 이력, 안정 기준·Tref 또는 산출식·허용범위·거절 규칙 | UNFROZEN / DEVICE_UNVERIFIED |
| 실제 실행 | FIFO head blocking·EDD tie·직렬·CG_DC 병행·반환 marker 뒤 AVAILABLE·WAIT timer/실제 dose | DEVICE_UNVERIFIED |
| 완료·분모 | C output, D write/flush/fsync/rename/readback, 실제 AVAILABLE, 실패/미완료 포함 예정 도착 분모 | DEVICE_UNVERIFIED |
| 회수 | 정상 summary+cleanup DRAINED·실제 worker 반환 확인, 회수본 재검산, 원본 이벤트/요청/센서/host HAL·읽기 시각·APK/입력/처방/세션 SHA·모든 시도 원장 | DEVICE_UNVERIFIED |

## 고정할 사항

I4→F4→DEV16 이후 CONFIRM40 전에 실행기·APK·입력·초기 gate·센서 주기/적분법/최대 gap·분석·사전 예측을 동결한다. 숫자 정확도 허용치를 확보하지 못하면 오차와 결측을 보고하며 PASS 허용치를 만들어 넣지 않는다. AP를 배터리 온도로 바꾸지 않고, J/AP 완전창 양쪽에 실제 표본이 없으면 해당 항목은 null이다.

주계획 64세션과 선택 후속 14/7/21세션은 분리한다. 후속은 이번 준비 계획에 포함하지 않았다. 실패를 삭제하거나 같은 세션을 retry/대체하지 않는다. I에서 지원되지 않는 Perfetto 카운터/센서는 UNSUPPORTED로 보존한다.

[분석 초안](ANALYSIS_CONTRACT_DRAFT.md)은 `frozen=false`이며 최종 분석 코드가 아니다. journal의 마지막 `fd.sync/close`는 cleanup 기록 다음이므로 host에서 별도 완료 시각을 관측하지 않는다. 실제 회수 무결성/내구성과 프로세스 종료까지 확인하는 후속 점검은 기기 미검증 항목으로 남긴다.

실제 시작에는 별도 사용자 실측 지시, 정확 APK/입력/도구 SHA, 하나의 새 기기 identity, 새 미소비 세션/원장, 실제 AP gate가 필요하다. 오늘 만든 DEVICE_UNVERIFIED manifest나 모의 결과를 승인 sidecar로 바꾸어 사용하지 않는다.

모델·원본 입력 6개와 tensor SHA 2개는 노트북에 확보되어 있다. 승인 이미지가1개라는 범위는 유지한다. 새 이미지 다양성/보편 정확도 연구를 하려면 별도 승인 입력·품질 근거를 준비한다. EfficientDet exact weight NOTICE 미확인 때문에 모델 binary를 APK·공개 저장소에 넣지 않는다.
