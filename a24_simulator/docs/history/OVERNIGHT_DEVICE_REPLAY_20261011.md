# A24 동결 일정 전향 실측 — OVERNIGHT-FROZEN-PLAN-DEVICE-01

사용자가 A24 연결과 필요한 실측·오류 수정·회의 준비를 승인한 2026-10-11 작업이다. PC 후보와 모형 선택에 새 실측 결과를 사용하지 않았다. 기존 중단 실험·실패·체크포인트·사용자 Android 변경을 보존하고 새 ID/clock/계획으로 실행했다.

## 무엇을 실제로 실행했는가

사전 고정한 같은 96건(공통 시작 +35초부터 350ms 교대, 긴급 분류48·일반 탐지48, 1.5초·6초 기한)에 대한 Band 대응 일정과 기존 리스트 선택 일정이다. ABBA 4세션, 설치 상한1·요청384·warmup32·runtime16이다. 원 APK의 replay는 CPU 일괄/B2 일괄과24건만 허용해, 별도 전체 소스 스냅샷에 opt-in `frozen-plan-96-cpu-gpu-replay-v2`를 추가했다. 기존 Android 작업트리와 앱 기본 정책은 수정하지 않았다. 프로젝트와 동일한 서명·패키지·버전을 확인하고 `pm install -r`로 자료를 보존했다.

판단 자체를 휴대폰에서 다시 계산한 온라인 Band/RL 실행은 아니다. PC 계획의 backend와 release 시각을 재생하며, 실제 lane가 AVAILABLE이 될 때까지 기다렸다. 분류CPU/GPU·탐지CPU만, CG_DC 두 작업 병행만 허용한다. CPU/GPU 분류 두 작업의 미검증 병행은 현재 owner로 차단하며 요청을 보존한다. 응답은 긴급 OUTPUT_READY/일반 PERSISTED, lane 재사용은 실제 AVAILABLE이다.

원 export가 common−35초 상대 좌표인 ABI 오류는 실측 전에 발견했다. PC 원장 자체는 이미35초도착이었으며 원장과 roundtrip 검산한 common0 export를 사용했다. 원 상대 자료와 빌드 오류·미설치 APK를 보존했다. 첫 Gradle SDK 환경 누락, sourceSets override와 기본서명 차이를 검사에서 차단하고 전체 프로젝트 스냅샷·설치 APK와 같은 기존 서명 경로로 보완했다. 서명 키·모델 원binary·대용량 raw는 공유하지 않는다.

## 실제 결과

| 순서 | 일정 | 완료 | 긴급 / 일반 기한 실패 | 긴급 P95 ms | 공통120초 조건부 J | 최고 AP °C | 초기 AP °C |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Band 대응 | 96 /96 | 0 / 0 | 295.943696 | 140.29025983555755 | 31.6 | 29.3 |
| 1 | 리스트 선택 | 96 /96 | 0 / 0 | 293.135465 | 144.0458325613602 | 31.7 | 29.3 |
| 2 | 리스트 선택 | 96 /96 | 0 / 0 | 295.789926 | 136.78123126414638 | 31.8 | 29.5 |
| 3 | Band 대응 | 96 /96 | 0 / 0 | 295.20585 | 141.5378947621531 | 32.2 | 29.6 |

종료 상태 `completed_descriptive_only`. 새 자료의 계수 적합0·온라인 정책 실행0이며, 실제 계획 재생은 4회·설치 1회다. 각 예정 요청의 실제 도착·응답·저장·AVAILABLE·기한 결과를 전량 CSV에 남겼다. 기한 지연이나 미완료가 있으면 비용 감소만으로 우위를 선언하지 않는다.

## 적용 범위와 모형 검증

두 순서 반전 쌍의 초기 AP 차이가 기존 환경매칭 폭0.5°C 안인지 별도로 표시했다. 이는 효과 허용 오차·열 안전 한도가 아니다. 배터리≥20%·비충전·BAT≤35°C·thermal status0·기존 화면 조건을 유지하며 절전 상태와 잔량을 기록했다. 초기 AP/잔량/배경 상태가 완전히 같다는 주장은 하지 않는다.

공통120초 J는 기기 전체 배터리 전류 raw를 mA로 해석한 조건부 추정이며 절대 계측기 정확도가 인증되지 않았다. 온도는 같은 HAL AP 채널이며 표면 온도·안전 한도 초과시간은 계산 불가다. 1초 전류·약2초 AP 관측은 요청 단위 에너지나 GPU kernel 병행 측정이 아니다. 각 정책 n=2이므로 작은 차이의 유의성·실제품 우월성·전체 조건 채택 근거로 삼지 않는다.

모형 오차는 새 결과 fit0인 상태에서, 도착 전−20..30초 AP/전력만 초기 입력으로 쓴 A(실제 점유 조건부)와 B(동결 PC 점유 계획)를 나누어 계산했다. A는 실제 미래 점유를 알고 하는 사후 모형 검증이며 온라인 예측이 아니다. B는 기기별 실제 점유·미래 AP/전력을 입력에 넣지 않았다. 예정 service/실행 지연 오차는 각 요청의 PC 값과 실제 값으로 공개했다. 고정5phase·냉각에 따른 속도 회복 미지원·같은 초기조건 가정의 한계는 유지한다.

## 열어볼 파일과 재현

- [오프라인 화면](results/overnight_device_20261011/index.html)
- [384 요청 원장](results/overnight_device_20261011/requests.csv), [세션 성적](results/overnight_device_20261011/sessions.csv), [A/B 오차](results/overnight_device_20261011/model_errors.csv)
- [사전 실행 계약](results/overnight_device_20261011/execution_contract.json), [원본·계획 해시](results/overnight_device_20261011/summary.json)
- opt-in patch와 JVM 검증 코드는 같은 결과 폴더에 있다. 실제 APK에 포함된 사용자 WIP는 별도 private 스냅샷/전체 hash로 보존했으며 Git 원본과 조용히 합치지 않았다.

PC 기능 검증: `python -B -X utf8 -m unittest tools.test_d1_overnight_device_replay -v`. 결과 판독: `python -B -X utf8 -m tools.d1_overnight_device_report`. 실제 실행은 immutable local plan/동결 source/APK SHA와 미소비 registry가 필요하며, 이미 소비한 이번 ID를 새 기기실행으로 재사용하지 않는다. 측정 원자료는 `output/overnight_device_20261011_v1/run`에 보존한다.

## 보고 v2: 관측창을 구분한 AP·SKIN

앞 성적표 AP 최고는 실제0..120초 표본최고이며, PC 정책판정35..180초와 다른 창이다. 아래는 실제확보된35..180초 AP표본범위다. 표본없는180초끝부분을실측으로채우지않았고연속최고값은계산불가다. A/B오차는동일한실제query시각만비교한다. J는공통120초를그대로유지한다.

| 순서 | 첫 AP표본 초 | 마지막 AP표본 초 | 180초까지 표본없는 edge 초 | 관측 AP표본최고 °C |
|---:|---:|---:|---:|---:|
| 0 | 36.752 | 178.682 | 1.318 | 31.600 |
| 1 | 35.841 | 179.316 | 0.684 | 31.700 |
| 2 | 35.692 | 178.357 | 1.643 | 31.800 |
| 3 | 35.357 | 179.197 | 0.803 | 32.200 |

[관측창CSV](results/overnight_device_20261011/temperature_observation_windows.csv)에AP/SKIN별시작/끝/gap/clock오차/실제cooling끝을공개했다. HAL SKIN은보고된센서명채널이고최고표면온도또는지원열모형으로승격하지않는다. [별도source prerequisite](results/overnight_device_20261011/source_bundle/README.md)와manifest/patch를사용하면원user WIP를stage하지않고필요code를별도checkout에서검증할수있다. 원source와frozen판정은변경하지않았다.

## 두 순서 반전 쌍의 평균과 범위

| 지표(리스트−Band) | 완료 쌍 | 평균 | 최소 | 최대 |
|---|---:|---:|---:|---:|
| energy_j_conditional_mA | 2 | -0.5005453861020186 | -4.756663498006702 | 3.755572725802665 |
| ap_peak_c | 2 | -0.15000000000000213 | -0.40000000000000213 | 0.09999999999999787 |
| urgent_p95_ms | 2 | -1.112077499999998 | -2.808230999999978 | 0.5840759999999818 |
| normal_mean_response_ms | 2 | 7.730284124999969 | 6.532871437499921 | 8.927696812500017 |
| urgent_failures | 2 | 0 | 0 | 0 |
| normal_failures | 2 | 0 | 0 | 0 |

이는 두 관측 쌍의 기술통계다. 효과·동등성·무효과의 통계적 증명이 아니다. 동일 초기 AP라도 열 이력·시스템 활동·SOC와 전체 에너지 변동이 같다는 보장은 없다. 실제 업무 완료·출력 품질·실제 AVAILABLE 준수는 새 검증 근거로 남기지만, 온라인 롤링/PPO의 기기 판단 비용·제어 에너지·전체 조건 우위는 미검증이다.

## 보고 초기 입력 오류와 보완

원 v1은 AP도 전력의−20..30초창으로잘라 원 AP초기화의55초 gate를통과하지못했다. 원 source와실패를private analysis_report_v1 및최종summary의cost_validation_error에보존했다. 보고v2는기존resident 분석과같이실제baseline 시작≤read_bracket<첫도착35초의전체idle AP를사용하고, warmup 완료≤baseline시작·최초실제work≥35초를검사했다. 전력은그대로−20..30초다. 새계수fit0이며, 측정된초기AP에서R/H를추정하는초기화와계수보정을구분했다. 기존55초검사를통과하지못하면원AP오차는null이며gate를낮추지않는다. 이는사후판독수정일뿐새기기실행0·정책/계수/seed/판정불변이다. [보완오차CSV](results/overnight_device_20261011/model_errors_v2.csv)에시작/끝/표본수·실제baseline·도착시각·지원여부를전량기록했다.

## 실행 장부와 재현 검산

ADB1748은 불변claim 후 수집기의 설치·session gate·poll·회수·cleanup 장부다. 별도사전읽기전용6명령은 device_identity_observation.json에보존했고, 최초대화의수동연결·battery·screen조회는tool history에별도로남는다. 따라서1748을대화전체명령수라고표시하지않는다. 설치1·실제4세션·본384＋warmup32=416·계수fit0·업무실패0이며4회등록은닫혔다. 새실측자동시작0이다.

공유결과의읽기전용재현검산: `python -B -X utf8 -m tools.d1_overnight_device_verify`. private raw가없으면공유CSV/patch/SHA/판정계약검산이라고표시하고, raw가있으면추가원본hash를검사한다. ADB·기기·학습·새환경·clock생성0이다. 원자료생성보고서는write-once이므로완료폴더에다시쓰기위해재실행하지않는다.

## Windows 공유 경로 보완

긴 검토 checkout에서 source bundle의 저장소 경로 중첩 때문에 `WinError206`이 발생했다. 내용이나 기기 오류가 아니다. 원 deep 11개 사본·manifest v1·실행 SHA는 로컬에 보존하고, 같은 bytes의 짧은 `source_bundle/flat/00_...` 사본과 logical 경로↔archive 경로를 담은 `manifest_v2.json`을 추가했다. verifier는 v2를 우선 읽고 v1 SHA와 동일 canonical source SHA를 검산한다. 원 user WIP·APK·정책·계수·실행 계약·CSV는 변경하지 않았고 추가 실측·학습0이다. Git 공유에서는 `source_bundle/prerequisites/**`만 제외한다.
