# 실제 실행·저장 복구·검산 계보

생산은 300 START/PREPARED/COMPLETE, FAIL 0이다. 첫 204건 종결 후 다음 START 전에 관리용 PowerShell 출력의 UTF-8 해석 오류로 중단했다. 204개 raw/config/prepared와 원장 byte prefix를 검증하고, 같은 정책·입력·seed의 아직 시작하지 않은 96건만 이어 실행했다. 첫 복구 준비의 import 경로 오류는 START 0건에서 보존했다. 원 동결 정책과 물리 소스는 수정하지 않았다.

최초 독립 감사는 35개 비용 재적분을 마친 뒤 반복 convolution 병목 때문에 등록된 감사 전용 인계로 종료했다. 저장 결과와 원 함수는 보존하고 과거 convolution 캐시만 추가한 별도 감사가 300건 전체를 검증했다. 감사 함수 동등성 204항목의 최대 차이는 2.381e-12다. 새 감사 첫 실행의 Windows 기본 인코딩 오류도 수치 작업 전에 실패로 남겼으며, 같은 소스를 Python -X utf8로 실행했다. 최초 35 + 전체 300 = 총 335개 저장 비용 재적분 소비다. 이것은 새 정책 환경이나 새 학습이 아니다.

- 실제 전체 감사 본문: sources/audit_state_full__0a9f201d57e1.py
- 실제 감사 캐시 진입점: sources/fast_audit_runner__78fdf1883b96.py
- 실제 운영 owner와 정확한 96건 복구: sources/ 아래의 SOURCE_MAP 원경로 RECOVERY_SOURCE_V2 대응 파일
- source_map은 원 절대경로·운영 등록·SHA를 복사본에 연결한다. 원 PC용 관리 명령을 새 호스트에서 그대로 재시작하지 않는다.
- receipts/rows 및 prepared 300개, 원 감사 35 proof, 새 감사의 전체 proof는 raw_part ZIP에 있다.
- 원 raw의 evidence.resource_selection은 부모의 오래된 설명 라벨이다. 실제 자원 배정은 routing_contract, 공개 입력, 후보/선택/dispatch와 독립 검산을 따른다. 설명을 고치려고 원 raw를 덮어쓰지 않았다.
- PUBLISH V3은 존재하지 않는 구형 등록 파일명 대신 실제 V3 등록을 포장하도록 경로만 수정했다. 정책·보고 산술·표본은 바꾸지 않았다.

전체 호스트의 다른 프로세스 명령은 배포하지 않는다. 감사 인계 대상 PID/시각과 비용 소비는 AUDIT_HANDOFF_IDENTITY.json으로 보존한다. 모든 파일의 원 바이트 SHA는 MANIFEST/SOURCE_MAP에 있다.

Windows 긴 경로의 Git 색인 오류를 방지하도록 운영 소스 복사본만 sources/의 짧은 이름으로 포장했다. 원 source/운영 등록/소스 바이트는 변경하지 않았고, SOURCE_MAP이 원경로·SHA·짧은 포장경로를 연결한다. 파일 이동은 이번에 생성한 배포 복사본 안에서만 수행했다.
