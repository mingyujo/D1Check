# 지속 입력 CPU/PAR PC 준비

완료: [8세션 실측·공유 예측](../overnight_sustained_run01/README.md). 아래 계획 계산은 실행 후 관측과 별도로 보존한다.

192요청/400ms 단일 후보. 기존96요청 경로를 유지한 opt-in 입력이며 새 계수/스로틀 가정 없음. CPU/PAR 각각192기한 충족·last lane112.02초라는 계획 계산을 확보했다. 예상PAR−CPU −2.090792J·최고AP +0.728389°C는 실측 결과가 아니다. 병행 예상20.996초이며 개별 요청 전력 계수 식별용이 아니다.

`preview_complete/requests.json`, `preview_complete/preview.csv`, `preview_complete/summary.json`은 기존 확인1 초기 입력을 사용한 계획 계산이다. 정확도·정책 우월성·일반 strict 지원은 미판정이다. 기존 모형 SHA5682082a…872db2 유지.

신규 입력/앱 validator, 실제 공유 host runner의 Check→단일claim→8세션/예외→단일cleanup 연결을 fake Device로 검증했다. Android10, Python18+판독4 통과. 해당 mock은 실기기 안정성 증거가 아니다. PowerShell Check는 기기명령0. 최초 APK 빌드의 서명 불일치를 배포 전에 발견하고 기존 프로젝트 키 경로로 격리 재빌드했다. 최종 APK와 소스 대응은 `preparation.json` 및 외부 `sustained_confirmation_build_v2/verified_build_receipt.json`을 따른다.

예산: 설치600초+8×세션700초+7×유휴90초=6830초. 세션당 stage/gate120+poll485+회수50+cleanup45=700초. poll485초에서 listing최대1940, thermal2초마다3명령 최대729, screen10초마다약49, gate/staging/승인/회수/cleanup 여유를 합친3200명령/세션과 설치200명령으로 총25800. 명령별 실행·reap는 기존 ObservedDevice deadline에서 예약하며 cap/잔여시간 부족이면 중단한다. 192개의 결과는 기존 단일 tar 회수35초를 재사용해 per-request pull을 만들지 않았다. 210초는 고정관측, 700초/6830초는 상한이지 정상완주 시간이나 보장이 아니다.

재현: `python -B -m unittest tools.test_d1_sustained_protocol tools.test_d1_arrival_recorded_replay tools.test_d1_sustained_readout`. PC 계획 계산: `python -B -m tools.d1_sustained_protocol --bundle docs/results/online_policy_study_01/separated_power_final --output <새폴더>` (정확한 원본 bundle 위치는 preview summary source_files 연결 참조).

현재 승인 실행의 실제 결과는 별도 결과 보고서/대시보드에서 판독하며 이 준비 문서의 예측을 관측으로 바꾸지 않는다. 추가2시도는 준비 문구만으로 자동 허용하지 않는다. 재현 코드 결함과 이전 종료·소비·소유권을 확인한 뒤 새ID/해시와 캠페인 전체 누적을 대조해야 한다.

공유 예측 경로는 기존 엔진의 explore와 정확한 입력 whitelist를 재사용한다. 일반128개 상한을 전역으로 넓히지 않고 `online-context-service-v1`+`sustained-confirmation-v1`에만192개를 허용한다. 기존96개·350ms와 기존24개 재생은 유지한다. 지원 검사는 비용 수식 계산 가능성과 독립 정확도/정책 선택을 구분한다. 온도에 따른 처리시간 변화 계수는 새로 만들지 않는다.

최초 실제 CPU 완료 자료를 PC 판독기로 읽어192분모, 시간순서,pre[-20,30]창,55 AP표본, 실제last lane112.040574초와 두 예측 경로의 연결을 확인했다. 이 확인은 전체8세션 완주 또는 정책 우월성 판정이 아니다. 추정/후속 입력 선정에는 사용하지 않았다.
