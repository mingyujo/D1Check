# ENERGY-THERMAL-COLLECT-02 — 첫 개발 세션 중단

설치 성공 후 첫 CC_DG 직렬 개발 세션에서 화면 관측 `dumpsys power`가2초 timeout을 넘어 계약대로 중단했다. **1시도·0완료·기술적 실패1·미시도7**(개발3/확인4). 재시도·대체·추가0. 계획/registry는 stopped_no_resume이며 자동 재개 금지다. 추정값 동결·확인·정책/시뮬레이터 연결은 하지 않았다. experiment_ready=false 유지.

## 실제 소비와 증거

- APK 전송1·업데이트 설치1 성공, 설치단계125.859초. 설치 hash `1e58655af1ede00062277669c718fd0881f5aadba31c0ed122445b7d0990d8e7`, 프로젝트 signer 일치. 입력 staging1회(7파일). 앱 시작1회.
- runtime4시작/4반환, warmup8시작/8반환, 적격성2시작/2반환.
- 작업 요청 최소746시작,745건 output/persist/worker/lane_available 확인(분류CPU678·탐지GPU67). 마지막은 `load-1-67`, detection_GPU, host_inference start, seq10901, thread108. journal10902행, 마지막 줄 불완전0. 회수 이후/강제 종료 전 추가 호출은 미확인이다.
- 실제 진단 시작748~872/6976, 명시적 추론 시작756~880/7040. 확인된 추론 반환755(작업745+적격성2+warmup8). 나머지7세션은 Activity 미시작으로 호출0. 미확인 범위를 예정량 또는0으로 채우지 않는다. 확인된 진단 완료747은 전체 출력 품질 검증747 PASS라는 뜻이 아니다.
- 설치 포함 claim→마지막 cleanup 명령 종료 **463.109초(약7분43초)**. 원 FINAL_RECEIPT의459.890초는 예외 진입 때 계산돼 후속 회수/cleanup 약3.219초가 빠져 있다. 원 receipt는 수정하지 않고 별도 분석에서 범위를 정정했다. 220분 상한 이내다.
- 앱 cleanup 미확인. failure_prefix/cleanup.json에는 JSON이 아니라 `cat: ... No such file or directory`가 저장돼 있다. 회수 파일 이름만으로 앱 종료 성공으로 인정하지 않는다. host force-stop/ps 기반 프로세스 부재/thermal0 확인. 추론 실행의 자체 실패나 native crash가 관측된 것은 아니다.

## 중단 원인과 한계

직접 원인은 host_commands/1099/client/result.json의 `dumpsys power` timeout2.016초다. 부분 stdout222612bytes·stderr0, host가 시작한 client만 종료/root_reaped=true이며 공유 daemon 종료는 하지 않았다. 마지막 부분 power 출력의 현재 상태 표시와 관계없이 계약은 조회 timeout 자체를 중단 조건으로 둔다. 실제 화면 꺼짐·무선 장애·GPU 교착을 원인으로 단정할 근거는 없다. 후속 회수/force-stop 명령은 반환했다. timeout 연장·gate 완화·코드 수정·재실행을 하지 않았다.

## 부분 에너지·열 분석

원시자료를 바꾸지 않고 기존 적분기/열 부담 함수를 사용했다. A24 raw mA가 유력하다는 **조건부 단위 가설**이며 기기 전체 소비다.

| 구간 | 관측시간 | 에너지 | 평균전력 |
|---|---:|---:|---:|
| resident baseline |120.027초|125.427J|1.045W|
| 회수된 부하 prefix |181.397초|314.168J|1.732W|

부하 prefix의 같은 baseline 대비 추가 소비는124.611J다. 해당 구간을 전체870작업 완료 에너지나 공통480초/냉각 포함 에너지로 대체하지 않는다. 완료 시점/전체완료량이 확보되지 않아 동일작업량 효율·병행효과 비교 불가다. 실제 lane 이벤트는 직렬이며 병행은 미시도다.

baseline AP 중앙값28.5°C, host 관측 AP28.2~32.3°C. 부분 열 부담505.216°C·s는173.499초의 유효 연결구간만 적분한 값이며 미관측 gap은 보간하지 않았다. 배터리 앱표본94%,27.6~28.8°C. 최초 실행 전 조회95%,27.0°C와 시점이 다르다. 온도/전력 지원 범위를 넓히거나 정확도 PASS를 부여하지 않는다.

## 시간 표현과 계획 보존

‘예상207분’을 **timeout 합산 예약시간206분40초**로 정정했다. 고정관측104분, 전체상한220분은 그대로다. 정상 평균시간·완주 가능한 시작 배터리 잔량은 미확인이다. 문서만 정정해 plan_v4 SHA `32ca541e9696aabb78431c82696893342f34304bfb4c423661698755f0578f9e`·APK·코드·조건·순서·timeout은 불변이다. 기존 PC 보고서/원본/FAIL·부분 결과·40값/20null·종료계획은 보존한다.

## 근거와 다음 행동

로컬 전용 root: `C:/Users/LG/Documents/D1Check_Arrival_Extension/`
- `energy_collection_run_v2/FINAL_RECEIPT.json`, `installation/installation_receipt.json`
- `energy_collection_run_v2/00_124857e4-3c25-5345-ad47-952986d7affd/failure_prefix/progress.jsonl`, `failure_host_cleanup.json`, `thermal.jsonl`
- `energy_collection_run_v2/host_commands/1099/client/` 및1100~1105 회수/cleanup
- `energy_collection_registry/ENERGY-THERMAL-COLLECT-02/stopped.json`
- `energy_collection_analysis_v1/partial_summary.json`, `REPRODUCE.py`

재현(저장소 루트, PC만):
```powershell
python -B C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_analysis_v1/REPRODUCE.py
```

다음 최소 행동은 기존 host 로그에서 화면 조회 시간·출력량과 필요한 상태 필드를 검토하는 PC 작업이다. 원인 분리 없이 timeout을 늘리거나 새 계획으로 자동 반복하지 않는다. 후속 실측은 별도 판단/승인이 필요하다. 이번 분석으로 현재 두 모델의 에너지·열 모형을 동결/검증하지 않는다.
