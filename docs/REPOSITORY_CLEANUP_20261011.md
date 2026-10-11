# 사용하지 않는 생성 파일 정리

사용자의 파일 정리 요청으로 현재 작업 경로의 재생성 가능한 생성물만 삭제했다. 기준 HEAD는 `8175aac95c82fa70860e07e2e7566797b92b7736`이며 실행 중 학습/빌드와 다른 worktree를 먼저 확인했다. 소스·역사적 연구 자료를 참조가 적다는 이유로 삭제하지 않았다.

| 정리 대상 | 삭제 파일 | 논리 바이트 |
|---|---:|---:|
| Gradle 변환 캐시 |12,151|947,142,705|
| Android 빌드 중간물 |5,358|587,728,116|
| 오프라인 화면 검증용 임시 브라우저 프로필 |8,963|764,740,164|
| 원 Python 소스가 있는 바이트코드 캐시 |365|9,582,148|
| 합계 |26,837|2,309,193,133|

삭제 완료 폴더는3,943개다. 실제 C드라이브 여유는7,914,430,464→10,223,775,744바이트로 **약2.15GiB 증가**했다. NTFS 압축·다른 프로세스 쓰기의 영향 때문에 논리 크기와 실제 공간 차이를 구분한다.

삭제 전에 각 절대 경로가 저장소 내부의 허용된 생성물 범주인지 확인했다. Git 추적 파일, reparse/junction, 모델·checkpoint·APK·키·측정 데이터가 섞인 후보를 제외했고 파일 수·크기·수정 시각이 계획과 일치할 때만 같은 PowerShell에서 `Remove-Item -LiteralPath`를 수행했다. 긴 경로 등의 확인 오류가 있는18대상은 삭제하지 않았다. 원 조사에서 추가로 제외한35후보도 그대로 남겼다.

원 실측·PPO/DDQN checkpoint·실행 원장·동결 모델·source snapshot·검증 보고·APK outputs·assets·Gradle modules-2/wrapper·사용자의 미커밋 코드/HTML/PDF·다른 worktree는 보존했다. 별도 담당 작업의 `.gradle-resident-identification`과 `.gradle-history`도 유지했다. 사용자 변경과 배포 ZIP/terminal64 등을 포함한56파일의 전후 SHA가 같고, 기존10개 추적 변경 경로와 다른 worktree HEAD도 같았다.

정리 명세·대상별 결과·보존 검산은 로컬 `output/repository_cleanup_20261011_v1/{inventory.json,plan.json,deletion_results.jsonl,cleanup_receipt.json,verification.json}`에 있다. 개인 경로가 있는 원 오류는 로컬에만 보존한다. 새 환경/학습/기기 명령은0이며 정책·계수·기한·판정 변경도0이다. 코드가 바뀌지 않아 전체 Android 빌드를 반복하지 않았다. 다음 빌드와 화면 검증에서 필요한 생성물은 다시 만들어진다.

기능 확인은 `python -B -X utf8 -m tools.d1_joint_amount_cli`의 원source/모형/체크포인트/공유세션 복원 검증으로 제한한다. `-B`로 바이트코드를 다시 만들지 않고 추가 학습·시뮬레이션을 시작하지 않는다.
