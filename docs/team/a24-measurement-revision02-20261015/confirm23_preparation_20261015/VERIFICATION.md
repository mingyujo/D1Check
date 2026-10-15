# 남은23회 준비 검증

검증 대상은 기존 공개 HEAD `09aa8663e76301de6b93ced34b66b8b2cee481cc`에 새 준비 실행기·테스트·문서를 더한 작업 트리다. 정확한 신규 파일 SHA와 검증 시각은 [회귀 검증 영수증](REGRESSION_VERIFICATION.json), [PC 조립](PC_VERIFICATION.json), [버전](VERSIONS.json), [파일 목록](FILES_SHA256.json)에 남겼다.

- 실제23개 manifest/authorization·입력·모델·기한·지원 경로를 변경하지 않고 기존 validator로 조립 검산했다. 새 그룹의 아직 없는 온도 기준은 PC scratch에서만 mock으로 생성했고, 첫 L64의 기준은 실제27.1℃ 원파일을 그대로 사용했다. 검산 뒤 실행 가능한 scratch는 제거했다.
- 새 이력 검사10건과 기존 C3/한 조건/범위 회귀17건, 합계27건 PASS다. 완료 슬롯 제외·예산·순서·APP 중복·이전 데이터 변경·기준 재선정 차단, 준비 job 실행 거절, 시간창 등록의 무실행, 읽기 전용 명령 제한을 포함한다.
- 한 PC 단위 fixture에서 준비 출력 폴더와 가상 기기 결과 폴더를 같은 위치로 잡아 한 검사가 실패했다. 실제 구성의 `output/`과 `Documents/`처럼 두 역할을 나누어 fixture를 수정했고 최종27검사는 모두 통과했다. 실제 실행 코드의 경로 제한이나 판정 기준은 완화하지 않았다.
- 읽기 전용 `find`는 고정된 조회 인자만 허용한다. `find -delete`, install/push/am start/settings put/mv 등 변경 동작은 ADB 호출 전에 차단한다.
- 실제 연결 점검은 별도16명령으로 신원·설치APK·배터리·화면·소유 프로세스·예정 ID의 remote 폴더 충돌을 확인했다. 기기 점검 결과와 PC mock을 합쳐 새 추론·MAIN 온도·에너지 검증 완료라고 표시하지 않는다.

```powershell
$env:PYTHONPATH='tools'
python -B -m unittest test_d1_a24_confirm_remaining test_d1_a24_confirm_after_diagnostic test_d1_a24_confirm_one_more test_d1_a24_confirm_registered_window -v
python -B tools/d1_a24_confirm_remaining.py inspect output/a24_confirm23_ready_20261015_v2/job.json
```

기존 APK·179개 핵심 파일·원자료·실험 계약의 SHA는 유지했다. 새 Android 빌드나 APK 설치는 필요하지 않아 수행하지 않았다. 원 worktree의 미커밋 코드·HTML/PDF와 데스크톱/S26/NPU 작업은 보존했다. 새 런타임 폴더·소유 원장·APP/START/claim·세션 소비는0이며 정식 예산58/81 상태는 변하지 않았다.
