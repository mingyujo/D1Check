# ENERGY-THERMAL-COLLECT-04 결과 — baseline 동등성 gate 중단

2026-09-25, 실행 소스 `16ce73eaffcdd202e6f1b0433a00e9af5f459373`/clean. 승인된 [계약](ENERGY_THERMAL_COLLECTION_REPREP_04_20260925.md)과 plan_v7 SHA-256 `a1399e2ffc5579f948ff4c7e6ec5637417f6baee947132b76cfcb42d75696719`를 **한 번** 실행했다. 출력 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v4`, 소비 registry `energy_collection_registry/ENERGY-THERMAL-COLLECT-04`는 `stopped_no_resume`이다. 기존 COLLECT-02/03와 sampler 진단을 이번 정식 표본에 합치지 않았다.

실행 직전 동일 A24·fingerprint·설치본 APK SHA-256 `2874a97f93c21816fea683bd6403326443dd9c15e682919c4087788d22670931` 및 프로젝트 서명, 비충전 배터리 75%/31.8°C·thermal0·화면·메모리 gate를 확인했다. 동일 설치본으로 APK 전송·설치 각각 0회. 설정 변경, 재시도·대체·추가 0회. 승인 명령은 준비된 `RUN_AFTER_APPROVAL.ps1 -Action Run -Approved`였으며 **다시 실행하면 안 된다**.

| 단계·소비 | 실제 / 계획 |
|---|---:|
| 개발 세션 | 2시도·1완료·1 baseline gate 중단·2미시도 / 4 |
| 확인 세션 | 0시도·4미시도 / 4 |
| runtime | 시작·반환 8 / 32 |
| warmup | 시작·반환 16 / 64 |
| 진단 요청 | 시작·lane 해제 확인 874 / 6,976 |
| 명시적 추론 | 완료 근거 890 / 7,040 |
| staging | 2회·14파일 / 8회·56파일 |
| 전체 실행·cleanup | 1,024.188초 / 상한13,200초 |

첫 개발 조건 CC_DG 직렬은 작업 870건과 적격성 2건이 완료돼 `eligible_descriptive_only`다. 뒤따른 CC_DG 병행 세션은 runtime4·warmup8·적격성2 이후 resident baseline AP 중앙값이 **32.3°C**(41개 샘플)로 측정됐다. 직렬 세션의 **31.5°C**보다 **0.8°C** 높아 사전 허용차 **±0.5°C**를 초과했다. host는 load arm 전에 중단했다. 둘째 세션의 회수된 연속 journal에는 load 시작·요청 시작 기록이 없다. receipt의 미기록 호출 보수적 상한을 적용하면 실제 시작 건수 범위는 진단 **874–1,744/6,976**, 명시적 추론 **890–1,760/7,040**이다. 상한은 성공 건수가 아니며 0으로 소급 확정하지 않는다. 추가 냉각, gate 완화, 같은 계획 재실행은 하지 않았다.

첫 세션은 앱·host cleanup 완료. 둘째 앱 cleanup은 유효한 파일이 없어 **미확인**이며, host cleanup은 `am force-stop`·프로세스 부재·thermal0 확인 후 완료됐다. `failure_prefix/cleanup.json.invalid.bin`은 원격 파일이 없다는 `cat` 오류이며 앱 완료 기록이 아니다. 개발4 적격성을 충족하지 못해 **동결 설정 없음**, 확인4 미실행, 조건별 확인 오차 없음.

첫 직렬 단일 세션의 기술 통계: 동일 작업 870건 완료까지 327.208초, 기기 전체 에너지 **540.675 J**, 해당 세션 resident idle 대비 추가 소비 추정 **165.156 J**. 공통 480.098초 관측창 에너지는 **716.163 J**. AP baseline 중앙값 31.5°C, load 최고 34.9°C. 전류 raw의 A24 **mA 가설**에 따른 조건부 에너지이며 절대 정확도 미인증, CPU/GPU 개별 소비가 아니다. 병행 표본이 없어 완료시간·에너지·발열의 paired 차이와 절감 여부는 계산할 수 없다. 한 세션으로 정밀도, 정책 성능, 시뮬레이터 적격성 PASS를 부여하지 않는다.

외부 상세 보고서 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_analysis_v4/FINAL_REPORT.md`는 로컬 전용이고 GitHub 링크가 아니다. Git 공유 [작은 요약](results/energy_collection_execution_04/README.md)을 참고한다. 재현 명령은 아래와 같으며 **기기를 사용하지 않는다**.

```powershell
python -B C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_analysis_v4/REPRODUCE.py
```

다음 최소 행동은 PC에서 고정 냉각과 paired AP baseline gate의 양립성을 검토하는 것이다. 주변온도·잔열의 원인을 확정하거나 이 결과에 맞춰 허용폭을 소급 변경하지 않는다. 기존 FAIL·부분 결과·40개 동결값·20개 null·종료 계획과 `experiment_ready=false`를 보존한다.
