# B2 기록 일정의 numeric AP 관측 진단 v2 — 승인 1회 결과

**후속 PC 분석:** [센서 표본 해상도의 에너지 상쇄·AP 형태·한 후보의 불리한 교차자료 비교](ARRIVAL_RECORDED_B2_RESIDUAL_MODEL_PC_20260929.md)를 추가했다. 아래 49개 미세 구간의 양·음 잔차 합은 구간 나누기에 민감하며 독립 상태 전력 오차가 아니다. 기존 원본·수치·그림은 보존한다.

**판정:** plan_v6 한 세션이 완료되어 24/24 요청과 공통 120초 창을 회수했다. 시작 HAL AP **29.9°C**는 동결 모형 개발 시작 범위 32.5–34.0°C 밖이다. 따라서 아래 동결식 계산은 **외삽 진단**이며 strict 지원, 독립 정확도 PASS, 온라인 B2 검증 또는 정책 우월성의 증거가 아니다. 이전 plan_v3/v4 중단과 이번 완료 자료는 합치지 않는다.

## 동일성·실행·소비

- `energy_ap_recorded_b2_diag_plan_v6/collection_plan.json` SHA-256 `38c9eb2fc403ec7d849bd1f31d067e3ef2742f81801fe4c34eb7ec1f8ce00ced`; Check 통과 후 미소비 계획을 한 번 실행했다. 현 transport에서 동일 A24·fingerprint, 프로젝트 서명과 설치본을 실행기의 gate로 확인했다. 후보 APK SHA-256 `747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180`; 설치본 검증값도 같다. 기존 설치본은 달라 후보 push·데이터 보존 설치 각 1회였다. 동결 모형 SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`는 수정하지 않았다.
- 승인 상한 대비 실제: **1/1세션, 4/4 runtime, 8/8 warmup, 24/24 본 요청, 32/32 명시적 추론**, staging 1회·7/7파일, 설치본 확인 host pull 1/1회, APK push 1/1회·설치 1/1회. 실행기 ADB **812/3,200**명령과 사전 transport 선택 **1명령**을 합쳐 관측 총 **813/3,200**이다. 실행기 전체 경과 **285.594/1,300초**(사전 선택 시간 별도), 재시도·대체·추가 세션 0.
- `start_ap.accepted.json`에 HAL AP 29.9°C, `numeric-ap-observe-v2`, 개발 범위 밖, AP 조회 시작→실제 공통창 시작 **0.198초**, 3초 신선도 상한 충족이 기록됐다. 이는 센서 내부 갱신 시각의 증명이 아니다. 배터리·비충전·BAT·thermal·화면·메모리·품질 gate는 실행기에서 통과했다.
- 앱 `cleanup.json`은 `completed`, sampler 오류 없음. 58파일 회수 `recovery.json`은 `recovered`이며 prefix 오류 없음. host는 대상 패키지에 정상 완료 후 force-stop을 보내고 process inventory에서 부재를 확인한 `host_cleanup.json: completed`를 기록했다. 앱 자체 cleanup과 host force-stop은 별개다. 정상 receipt `completed_descriptive_only`, `experiment_ready=false`다.

## 일정과 관측

입력은 기존 queue/seed201/B2_PC/PC 실현 간섭 1.5의 24개 기록 요청·backend·dispatch 허용 하한이다. 간섭 1.5를 기기에 적용하거나 실제 처리시간을 PC 값으로 맞추지 않았다. 24개 모두 실제 시작·반환·worker release·lane 해제가 기록됐고 공통창 종료 때 미완료 0건이다. 최대 실제 dispatch−PC dispatch는 **0.049초**였다. 실제 상태는 idle **108.615초**, 탐지 CPU 단독 **9.696초**, 분류 GPU 단독 **0.006초**, 분류 GPU＋탐지 CPU 병행 **1.683초**다. 센서 표본은 전력 222개(AP 44개), 최대 간격 각각 **1.030초/4.175초**다. 병행이 관측됐지만 짧은 개별 요청 전력 계수를 식별할 해상도라는 뜻은 아니다.

공통창 관측 에너지 **154.696 J**, 실제 lane 상태·전환 시각과 관측 초기 AP를 넣은 동결식 계산 **155.758 J**, 예측−관측 **+1.062 J**(관측 대비 절대 **0.686%**)이다. 상태 49구간의 양의 잔차 합 **+3.056 J**, 음의 잔차 합 **−1.994 J**여서 전체 오차의 일부는 상쇄됐다. 센서보다 짧은 상태 구간의 개별 잔차는 센서 보간에 의존한다. AP 경로 MAE **3.555°C**, 최대 절대오차 **4.470°C**. 관측 최고 **31.6°C**, 예측 최고 **34.370°C**로 최고값 차이 **+2.770°C**다. 관측·예측 AP 경로 모두 개발 관측 경로 범위를 벗어난다.

에너지와 AP의 **수치 계산 가능**, 관측창의 **자료 적격**, 모형의 **경험적 지원**, **정확도 판정**을 구분한다. 전체창 적분·상태 매핑은 가능했으나 시작 AP와 짧은 전환이 strict 범위 밖이다. 작은 총 J 차이와 큰 AP 차이 모두 외삽 조건에서 관측된 진단값이다. 이후 실측 전력·AP를 예측 입력에 넣지 않았다. 전류 raw=mA 해석은 조건부이며 절대 에너지 정확도는 미인증이다. 계획상 120초 이외, 반대 방향 병행 DC_DG/CC_DG, 도착에서 일정까지의 종단간 예측, 실제 온라인 B2, 임의 도착 전체는 확인하지 않았다.

## 원본·공유 결과·재현

- 원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_diag_run_v6/FINAL_RECEIPT.json` (SHA-256 `4d5708d6cab1fff52db38357848951b7e9d958d26308966b8601fd97db1b3e4a`), 같은 폴더의 단일 세션 artifacts·host_commands·installation·analysis_readout. 원본은 수정하지 않았다.
- [작은 분석 요약·CSV·그림](results/energy_ap_recorded_b2_01/diag_v6/README.md), [통합 대시보드](results/arrival_policy_screen_01/dashboard.html). 공유 그림의 `dispatch.svg`는 기록 release와 실제 dispatch, `lanes.svg`는 실제 lane 점유다.
- 분석 재현에는 외부 원본 단일 세션과 동결 파일이 필요하다. 기록 일정 입력과 공유 CSV/SVG는 저장소에서 열 수 있다.

```powershell
python -B -m tools.d1_arrival_recorded_replay_analysis --session 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_diag_run_v6/00_3b668459-14ec-59ee-81e0-e30ab635514a' --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' --output '<새 빈 PC 출력 경로>'
python -B tools/d1_arrival_recorded_replay_figures.py --bundle '<분석 출력 경로>' --output '<새 빈 그림 경로>'
```

PC 검증(2026-09-29, 분석 시작 HEAD `f95722e03634d146aaf546131ad549f5f9ce8feb`, 문서·그림 소스 미커밋 상태): `python -B -m unittest tools.test_d1_arrival_recorded_replay -q` **8건 통과**. 공유 `summary.json`과 외부 분석 출력의 SHA-256 동일, 상태 49구간 합계 120초, 예측−관측 J 수치, 대시보드의 그림 링크 4개와 `git diff --check`를 확인했다. 이 PC 검증은 실기기 예측 정확도 승격이 아니다.

다음 PC 작업 하나: 이번 **AP 경로 외삽 잔차와 짧은 상태 구간의 에너지 상쇄**를 기존 개발·DC_DG·CG_DC 자료의 초기조건·상태별 잔차와 대조해, 새 계수 없이 설명 가능한지 판정한다. 추가 실측이나 동결값 변경은 이 결과로 자동 결정하지 않는다.
