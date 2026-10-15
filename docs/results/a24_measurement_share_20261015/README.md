# A24 측정 원자료 · 비교 블록 공유

공개 스냅샷 시점(UTC): **2026-10-15T10:38:17.886074+00:00**. 실측은 별도 실행 중이며 이 스냅샷은 이미 닫혀 회수된 세션만 포함한다. 새 독립 확인은 **15/40회, 2,224개 본요청 완료**다. 40회를 모두 끝낸 결과로 해석하지 않는다.

## 완료·실패·미완료 원장

| 구분 | 정상 종료 세션 | 해당 세션의 본요청 완료 | 실제 APP 실행 명령 |
|---|---:|---:|---:|
| LEGACY | 19 | 2,608 | 25 |
| NEW_CONFIRM | 15 | 2,224 | 16 |
| REV02_DEV8 | 8 | 1,144 | 8 |
| REV02_W1 | 1 | 252 | 2 |
| REV02_W3 | 0 | 0 | 1 |
| REV02_W4 | 2 | 504 | 2 |

- 정식 예산 소비 **57/81**: 종료된 시도 56 + 진행 중 1. 실제 APP 명령은 **54**이며 APP 이전 실패 3회와 구분한다.
- 별도 전류 반응 진단 APP 1회를 포함한 실제 APP 명령 합계는 **55**다. 진단은 정식 독립 확인으로 세지 않는다.
- 같은 session ID의 APP 재실행 명령 **0회**. 실패 슬롯을 성공으로 바꾸거나 미시도 슬롯을 소비한 것으로 세지 않는다.
- 실패한 동일 실행에서 추가 회수한 본요청 252건은 `supplemental_same_run_raw/`에 보존하며 정상 비교군으로 승격하지 않는다.
- [전체 118개 등록 슬롯](snapshot02/attempts_all.csv), [상태별 개수](snapshot02/COUNTS.json), [개인 식별값을 제외한 APP 명령 원장](snapshot02/APP_commands_no_private_ids.csv).

## 블록 단위 ZIP

완료된 블록을 우선 이용한다. 부분 블록에는 완료·실패·미시도를 모두 기록하고, 그 안에서 같은 recipe의 비교군만 완성된 경우 별도 subset ZIP도 제공한다. 전체 블록과 subset에는 같은 원물이 중복되므로 **ZIP별 횟수를 더하지 말고 session ID로 집계**한다. 표의 정상 종료는 회수·종료 상태이며 모든 과학적 KPI의 적격 판정은 아니다.

| 파일 | 정상 종료 / 등록군 | ZIP 바이트 |
|---|---:|---:|
| [LEGACY_CONFIRM_CONFIRM01.zip](snapshot02/blocks/LEGACY_CONFIRM_CONFIRM01.zip) | 2/8 | 652,974 |
| [LEGACY_DEV_DEV01.zip](snapshot02/blocks/LEGACY_DEV_DEV01.zip) | 7/8 | 1,663,410 |
| [LEGACY_DEV_DEV01_M128.zip](snapshot02/blocks/LEGACY_DEV_DEV01_M128.zip) | 4/4 | 910,951 |
| [LEGACY_DEV_DEV01_L64.zip](snapshot02/blocks/LEGACY_DEV_DEV01_L64.zip) | 2/2 | 276,084 |
| [LEGACY_DEV_DEV02.zip](snapshot02/blocks/LEGACY_DEV_DEV02.zip) | 8/8 | 2,050,494 |
| [LEGACY_F_F01.zip](snapshot02/blocks/LEGACY_F_F01.zip) | 2/4 | 951,625 |
| [LEGACY_F_F01_M128.zip](snapshot02/blocks/LEGACY_F_F01_M128.zip) | 2/2 | 448,910 |
| [LEGACY_I_I01.zip](snapshot02/blocks/LEGACY_I_I01.zip) | 0/1 | 5,640 |
| [LEGACY_I_I02.zip](snapshot02/blocks/LEGACY_I_I02.zip) | 0/1 | 5,913 |
| [LEGACY_I_I03.zip](snapshot02/blocks/LEGACY_I_I03.zip) | 0/2 | 23,751 |
| [NEW_CONFIRM_CONFIRM_R02CONFIRM01.zip](snapshot02/blocks/NEW_CONFIRM_CONFIRM_R02CONFIRM01.zip) | 8/8 | 1,987,605 |
| [NEW_CONFIRM_CONFIRM_R02CONFIRM02.zip](snapshot02/blocks/NEW_CONFIRM_CONFIRM_R02CONFIRM02.zip) | 7/8 | 1,861,679 |
| [NEW_CONFIRM_CONFIRM_R02CONFIRM02_M128.zip](snapshot02/blocks/NEW_CONFIRM_CONFIRM_R02CONFIRM02_M128.zip) | 4/4 | 912,523 |
| [NEW_CONFIRM_CONFIRM_R02CONFIRM02_C252.zip](snapshot02/blocks/NEW_CONFIRM_CONFIRM_R02CONFIRM02_C252.zip) | 2/2 | 810,601 |
| [REV02_DEV8_DEV_R02DEV01.zip](snapshot02/blocks/REV02_DEV8_DEV_R02DEV01.zip) | 8/8 | 1,977,533 |
| [REV02_W1_DEV_R02W01_C252.zip](snapshot02/blocks/REV02_W1_DEV_R02W01_C252.zip) | 1/2 | 483,307 |
| [REV02_W3_DEV_R02_CURRENT_BLOCK03.zip](snapshot02/blocks/REV02_W3_DEV_R02_CURRENT_BLOCK03.zip) | 0/2 | 78,398 |
| [REV02_W4_DEV_R02_PREPARED_BLOCK04.zip](snapshot02/blocks/REV02_W4_DEV_R02_PREPARED_BLOCK04.zip) | 2/2 | 817,365 |

각 ZIP 안에는 `BLOCK_STATUS.json`, `attempts.csv`, `VERSIONS.json`, `FILE_SHA256.json`, `raw/`, 가능한 host 종료 영수증·결과·기준값, 식별정보를 제외한 파생 manifest가 있다. [ZIP 자체의 SHA-256](snapshot02/BLOCK_BUNDLES.json)과 내부 모든 파일 SHA를 재검산했다. **포함한 원자료는 원본 바이트 그대로**이며 가공·필터링해 원물처럼 표시하지 않았다.

## 버전·변경 사항

- [파일별 소스 SHA 카탈로그](snapshot02/SOURCE_CATALOGS.json), [공개 코드 커밋과의 대응](snapshot02/CODE_BINDING.json): 현재 동결 핵심 소스 179개는 공개 커밋 `9a7ead1736fb7aff714b297d0d5586a65b83f00a`와 바이트 일치. 역사적 소스 버전은 각 세션의 별도 카탈로그로 구분한다. 준비 base commit을 실제 실행 HEAD라고 표시하지 않는다.
- [APK 버전·바이트·서명 SHA](snapshot02/APK_VERSIONS.json), [APK 빌드 영수증](snapshot02/apk_identities/), [모델·labels·anchors·이미지·tensor SHA와 원 출처](snapshot02/ASSET_VERSIONS.json). 구체적인 요청별 입력·실행 설정은 ZIP의 `public_manifests/`에 있다.
- 과거 I/F/DEV/CONFIRM, REV02 W1·W3·W4, 새 DEV8, 새 CONFIRM은 서로 합치지 않는다. 이전 실패·준비 중 중지·폐기된 미시도 계획도 보존했다.
- DEV8 첫 GPU는 177개 파일 host, 이후 7군은 준비 냉각 복구를 적용한 179개 파일 host다. MAIN 조건·APK·요청 의미는 유지했다.
- 새 CONFIRM은 최초 40회·5블록·5,720요청 계획과 고정 APK·179개 핵심 소스를 유지했다. 방문 간 재연결·전역 원장·전류 진단 후 복귀는 별도 coordinator에 묶었다. 블록 2 혼합 BASE와 PAIR 사이에 별도 진단이 있었고, 기존 27.9℃ 기준과 APK를 재확인했다. 전류 시간 이동 보정은 하지 않았다.

## 함께 볼 보고서와 진단 원물

- [DEV8 결과](../a24_revision02_20261015/dev_window01/README.md)
- [독립 확인 첫 9군 분석](../a24_revision02_20261015/confirm_visits_01_02/README.md)
- [전류 반응 진단 · 원자료 ZIP·CSV·그림](../a24_revision02_20261015/current_response_diag_01/README.md)
- [기존 에너지 읽기 감사](../a24_revision02_20261015/README.md)

에너지 J는 여전히 **미검증·미판정**이다. 전류·전압·전하량 원값을 포함했지만 단위 가설이나 지연 관찰을 절대 J·절감 검증으로 승격하지 않는다. AP는 기록된 HAL 온도 채널이며 검증된 표면온도가 아니다. 첫 확인 BASE의 AP 관측 공백 등 적격성은 분석 보고서와 해당 원물에서 별도 확인한다.

## 공유 제외와 재검산

기기 일련번호·연결주소·개인 경로가 든 원 manifest/식별 파일/전체 시스템 로그, 키·APK·모델·승인 이미지의 바이너리는 포함하지 않는다. 제외 파일의 이름·크기·SHA·이유는 각 ZIP의 `EXCLUDED_PRIVATE_OR_BINARY.json`에 남겼다. 식별값 제거 manifest는 파생본이라고 명시했다. 특히 탐지 모델 exact license/NOTICE 미확인에 따른 원 URL 직접 확보 원칙을 유지한다. 원본은 로컬에 보존했다.

원물 묶음 생성은 PC 전용이며 ADB·추론·계측·세션 소비가 0이다. 실측 실행기에는 변경을 가하지 않았다. 로컬 전용 job/root 경로를 담은 구성은 공유하지 않는다.

```powershell
$env:PYTHONPATH='tools'
python -B -m unittest test_d1_a24_measurement_share_bundle -v
python -B tools/d1_a24_measurement_share_bundle.py <local-config.json> <new-output-directory> <private-audit-directory>
```

ZIP을 받은 뒤 Python `zipfile`로 `FILE_SHA256.json`의 각 `path`를 읽어 `hashlib.sha256`와 대조할 수 있다. [스냅샷 실행 증거](snapshot02/SNAPSHOT.json)에 실행 시각과 묶음 생성 코드 SHA가 있다. PC mock 검증을 실기기 검증으로 표시하지 않는다.
