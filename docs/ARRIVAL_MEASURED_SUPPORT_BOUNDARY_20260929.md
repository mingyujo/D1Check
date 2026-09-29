# 저장된 정책 일정에 대한 A24 동결 모형 지원 경계 — 2026-09-29

**판정 B: low·queue·burst의 저장된 CPU_URGENT·B2·B3 일정 135개 중 120초 전체를 A24 실측 기반 에너지와 AP 경로로 계산할 수 있는 사례는 0개다.** [직전 통합 감사](ENERGY_AP_POLICY_MEASUREMENT_AUDIT_20260929.md)의 측정 목록을 넓히지 않고, 실제 계산을 막는 첫 지점과 최소 해제 조건을 확정했다. 기존 PC 응답·완료 비교와 출처가 표시된 *가정 기반* 비용 탐색은 유지한다. 미지원 J·AP를 0이나 부분창 값으로 대신해 정책 순위를 만들지 않았다.

## 적용한 자료와 네 판정 층위

- 일정은 [기존 상대 경로 번들](results/arrival_policy_screen_01/repro_bundle/): `occupancy_segments.csv` 6,615구간, `service_metrics.csv`, `assumptions.json`의 low/queue/burst × 실현 간섭 1.0/1.5/2.0 × seed 201–205 × 3정책, **24예정 요청·120초**다. 이는 CAL-03 시간 입력으로 만든 **PC 일정**이며 기기에서 관측한 점유가 아니다. B2의 고정 배정은 그대로다. `predicted_interference`는 이 세 정책의 선택에 사용되지 않고 P에서만 쓰므로 새 값을 가정하지 않았다. 원본 해시는 [작은 요약](results/arrival_policy_screen_01/measured_support_01/audit_summary.json)에 있다.
- 계수 출처는 외부 `energy_ap_state_run_v5/development_freeze.json`, SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`이다. 개발 3세션의 **4 resident**·8상태 전체 기기 W·AP 1차식, 시작 AP 개발 관측 **32.5–34.0°C**이며 물리적 허용 한도가 아니다. 저장 PC 점유의 `idle`은 상태 이름만 `resident_idle`에 대응하며 실제 모델 resident 생성·이력은 그 CSV에서 검증되지 않는다. [COLLECT-05](ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md)의 DC_DG 1조건만 원래 프로토콜에서 확인됐고, [CG_DC DIAG-04](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md)는 새 프로토콜 사후 전이 진단이다. 오래된 CC_DG 고정 비교와 시작32.3°C 짧은 전환도 임의 도착 독립 확인이 아니다.
- **① 코드 반환:** `tools/d1_arrival_energy_research.py`는 동결 `energy_ap_state_regimen_fit_v1`의 임의 도착에서 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`, J/AP `null`을 반환한다. **② 계측 지원:** 135개 모두 임의 짧은 전환의 적합·확인 범위 밖이다. 저장 일정의 초기 AP **29°C는 미측정 탐색 가정**이고 개발 시작 범위 밖이어서 AP에는 별도의 차단도 있다. **③ 새로운 자료의 예측 오차:** 이 정책 일정에 대한 독립 확인은 0개다. **④ 정책 차이 식별:** ③의 조건별 오차·변동성이 없으므로 실측 기반 에너지/AP 우열은 미판정이다. 기존 한 세션의 오차를 보편 한도로 전용하지 않는다.

| 출력 | 저장 일정에 대해 가능한 범위 | 첫 차단과 근거 |
|---|---|---|
| 일정·응답·기한·미완료 | 같은 엔진/입력의 **보존된 PC 결과** 135개를 읽을 수 있다. 실기기 종단간 예측 확인은 아니다. | 동결 전력/AP 지원 규칙 때문에 PC 일정 자체를 삭제하지 않는다. 요청별 `output_ready`·persist·worker release·lane available은 [기존 대표 trace](results/arrival_visualization_01/timeline.csv)에서 따로 구분하며, 점유 CSV는 120초의 lane 상태 구간만 보존한다. |
| 120초 전체 기기 에너지 J | **계산 불가**. 상태별 W 계수가 있어도 임의 도착 적용은 차단한다. | 모든 사례 t=0에서 regimen-only 지원 규칙. 대표 queue/201/1.5의 첫 구체 전환은 **0.000300초 `idle → detection:CPU`**. 개발의 긴 반복 블록에서 이 짧은 상태·대기·callback 전환을 확인하지 않았다. |
| AP 경로·최고·한도 초과 시간 | **계산 불가**. | 위 전환 차단에 더해 t=0의 미관측 초기 AP 29°C. 초기 AP를 임의로 32.5°C로 바꾸지 않는다. 같은 AP값이라도 이전 부하의 숨은 잔열은 동결 1차식에서 독립 확인되지 않았다. |
| 온도에 따른 처리시간 변화 | 미검증. 고정된 실현 처리시간을 쓰는 **가정상** 일정·열 제한 탐색에 반드시 필요한 식은 아니다. | OS 열 보호/스로틀을 없다고 가정하지 않으며 고온 지속 정책의 실제 응답은 주장하지 않는다. |

전체 [지원 상태 CSV](results/arrival_policy_screen_01/measured_support_01/support_status.csv)는 각 상태의 120초 점유, 전환 횟수, 누락 계수, 출력별 판정을 담는다. [첫 차단 CSV](results/arrival_policy_screen_01/measured_support_01/first_blockers.csv)는 출력별 270행이고 [전체 차단 CSV](results/arrival_policy_screen_01/measured_support_01/all_blockers.csv)는 근거 규칙과 구간별 6,759행이다. 이 행들은 **서로 독립인 6,759번 실패**가 아니라 한 일정에 중첩될 수 있는 규칙·전환 표시다. [대표 일정 SVG](results/arrival_policy_screen_01/measured_support_01/representative_schedule.svg)의 빨간 선은 미검증 전환이며 측정된 AP나 J가 아니다.

queue/seed201/실현1.5는 이 세 정책 비교에서 **동결 파일에 없는 상태 이름이 없는 최소 결손 묶음**이다. 저장 일정상 B2는 `classification:GPU+detection:CPU` **2.531초**, B3는 `detection:CPU+detection:GPU` **8.326초**, `classification:GPU+detection:CPU` **1.324초**, `classification:CPU+detection:GPU` **0.688초**를 사용한다. CPU_URGENT는 CPU 단독이다. 동결 상태 이름은 모두 있으나 한 정책의 여러 짧은 전환과 초기 열 상태가 아직 지원되지 않는다. 반면 **burst의 B3 9/45개**에는 동결 8상태에 없는 `classification:CPU+classification:GPU`가 추가로 나타난다(합계 약 0.667초). 이를 CC_DG/CG_DC/DC_DG와 합치거나 다른 상태 전력으로 대체하지 않는다. 전체 135개에는 6,480번의 PC 상태 전환이 있다. 같은 이름의 전력 평균이 존재해도 이 전환 전체가 예측 검증됐다는 뜻은 아니다.

## 최소 해결 명세와 종료 기준

| 해결 유형 | 특정 차단 | 최소 조건과 완료 판정 |
|---|---|---|
| ① PC 필드·상태 매핑 | `task:backend`를 동결의 `task_backend`에 연결하고 유휴를 resident idle로 연결해야 한다. | 이번 읽기 전용 도구에서 정확한 문자열별 매핑, 120초의 무공백 분할, 저장 입력 SHA를 검사했다. 서로 다른 병행을 하나의 CPU+GPU로 합치지 않는다. 계수와 지원 범위는 바꾸지 않았다. |
| ② 기존 자료 재분석 | 개발3·DC_DG·CG_DC 블록에서 상태별 잔차, 센서 공백, 짧은 전환/이력 신호. | [기존 전이 분석](ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md)을 재사용한다. 새 프로토콜 CG_DC의 매핑 구간 +13.121J, AP 최고 +1.612°C 사후 오차가 있으나 임의 도착 지원을 해제할 독립 자료는 아니다. 이번에 같은 원본을 재적합/재분할하지 않았다. |
| ③ 계측·독립 예측 공백 | 대표 **queue/201/1.5의 CPU_URGENT·B2·B3**에 필요한 유휴↔모델별 단독↔CG_DC/DC_DG/CC_DG 짧은 점유·전환, 관측 시작 AP. | 정책별 직접 비교와 모형 확인을 구분한다. 같은 A24·두 모델/입력·runtime/resident·센서·프로토콜에서 사전 고정 도착/배정과 유효한 시작 AP를 사용해 **실제 lane 상태/경계, 전류·전압·AP 시각, 전체120초, 모든 예정 요청의 응답/미완료**를 기록한다. 조건부 A는 실제 상태·전환만 입력, 종단간 B는 예정 도착·사전 시간모형만 입력한다. 동결식을 확인 자료로 재보정하지 않고 공통창 J 부호/절대·누적 경로, AP MAE/최대/최고·한도 시간, 일정·응답 오차 및 정책 차이의 방향을 **별도로** 보고한다. 실제 pair 점유와 센서 coverage가 부족하면 해당 전환은 미완료로 둔다. 한 정책 1세션씩의 결과는 세션 변동성 보장이 아니다. 계측 방식이 바뀌면 별도 프로토콜 전이 확인이다. |
| ④ 현재 범위에서 제외 | burst/B3의 `classification:CPU+classification:GPU` 9사례 | 이 9사례는 상태 계수가 없으므로 **현재 제한 묶음에서 제외**한다. 나중에 이 행동이 정책 선택의 핵심일 때만 정확한 상태/전환 자료를 별도 확보한다. 나머지 사례도 ③ 이전에는 J/AP 미지원이다. |
| ⑤ 접근 불가 | A24 필수 파일은 이 PC에서 접근 가능했다. S26의 현재 두 모델 원본은 이 브랜치에서 확인되지 않는다. | S26은 별도 기기·모형이다. 두 모델의 manifest, exact 모델/입력·runtime·resident, 상태/시간/전류·전압·AP 원문과 receipt를 받기 전까지 A24 빈 계수를 S26으로 채우거나 S26을 지원 사례로 계산하지 않는다. |

**완료 범위:** ③의 자료 적격성은 유효한 시작 AP·시계 정렬·센서 공백·실제 상태·120초/24요청 분모로 판정한다. 예측 오차는 적격 자료에서만 숫자로 보고한다. 허용 오차와 정책 간 유의미한 차이 기준은 결과를 본 뒤 만들지 않으며, 근거가 없으면 정확도 PASS/우열을 보류한다. 온도→처리시간 곡선과 모든 초기 열 이력의 식별은 이 제한된 저열 비교의 완료 조건이 아니다. 짧은 요청별 W도 센서 해상도상 목표가 아니다. 계획만 존재하는 queue24/FIXED_SPLIT은 미승인·미소비로 유지한다.

**재현:** 저장 일정의 지원 마스크만 다시 만들며 시뮬레이터 배치를 실행하지 않는다. 저장소 루트에서 다음 명령을 실행한다. 외부 동결 파일을 가진 PC에서는 정확한 SHA를 다시 검사한다. 공유 산출물의 `frozen_support.json`만 사용할 때는 원본 byte 확인이 생략됐음이 `audit_summary.json`에 표시된다.

```powershell
python -X utf8 -B -m tools.d1_arrival_measured_support --frozen C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json
python -B -m unittest tools.test_d1_arrival_measured_support -v
```

원자료·동결 계수·FAIL·종료 계획과 `experiment_ready=false`는 변경하지 않았다. 이 CSV와 그림에는 새 실측이나 실측–예측 그래프가 없다.

PC 검증(출발 HEAD `aa257a016e3aedbecd748bebdcdbecb7fd966ef5`): 동결 byte 해시·저장 번들 입력 해시를 확인하고 135개 일정의 전체창 분할을 검사했다. 관련 unittest 4건 및 기존 번들의 별도 임시 폴더 렌더링을 통과했다. 번들의 이전 `dashboard_template.html` 해시만 현재 파일과 달라 manifest를 현재 템플릿의 정규화 텍스트 SHA에 맞게 고쳤으며, 정책 일정·기존 결과·계수는 바꾸지 않았다. 이 검증은 기기 예측 정확도 검증이 아니다.
