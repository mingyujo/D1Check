# ENERGY-THERMAL-PC-01 공유 결과

[한국어 보고서·시간/단위 계약](../../ENERGY_THERMAL_PC_01_20260925.md), [추가 수집 후보](../../ENERGY_THERMAL_COLLECTION_PROPOSAL_20260925.md).

기존 MobileNet A24/S26 각80세션의 **사후 보정·내부 확인**이다. 현재 두 모델 절감·독립 기기 검증·정책 우월성 PASS가 아니다. A24 raw mA/S26 raw μA가 가장 유력하지만 절대 정확도는 미인증이다. 작은 온도 오차와 계수 식별성을 혼동하지 않는다.

| 파일 | 의미 |
|---|---|
| [device_summary.csv](device_summary.csv) | 기기별 샘플·단위 가설·범위 |
| [unit_summary.csv](unit_summary.csv) | 전체/60/120초 counter 일관성, 참값 검증 아님 |
| [condition_energy_summary.csv](condition_energy_summary.csv) | 실제 완료량당 에너지·조건별 전력, 기기 전체 |
| [thermal_fit.csv](thermal_fit.csv) | 기기/센서/상태별 계수와 식별성 진단 |
| [error_summary.csv](error_summary.csv) | 세션 단위 오차·잔차 요약 |
| [association_summary.csv](association_summary.csv) | 조건 내5세션 연관성, 인과/고온곡선 아님 |
| [real_record_partition_check.json](real_record_partition_check.json) | 대표 원자료2세션의 단계 적분 보존 |
| [legacy_replay_demo.json](legacy_replay_demo.json) | legacy 상태모형 회계·원시 적분 구분 |
| [engine_demo.json](engine_demo.json) | 기존 엔진 불변·합성 hand-check 820nJ; 실측값 아님 |
| [METHOD_FROZEN_BEFORE_FIT.json](METHOD_FROZEN_BEFORE_FIT.json) | 적합 전 분석 규칙/사후 내부 분리 |
| [VERIFICATION.json](VERIFICATION.json) | 대상 HEAD·소스 해시·명령·검증 범위 |
| [collection_budget_proposal.json](collection_budget_proposal.json) | 미승인8세션 후보의 산술 예산 |
| [legacy_A24_AP_example.json](legacy_A24_AP_example.json) | 첫 condition의 실제 보정 설정 예시; 단위/범위 조건부 |

그림은 고정 선택된 첫 condition/block4의 모든 센서를 표시한다. 열모형의 확인 오차는 단계 첫 실제 온도에 조건부이다. 에너지 그림은 조건별5세션 점이며 CI가 아니다. CPU/GPU마다60초 완료량이 다르므로 총J만으로 효율을 비교하지 않는다.

- A24: [열 PNG](A24_thermal.png) / [SVG](A24_thermal.svg), [에너지 PNG](A24_energy.png) / [SVG](A24_energy.svg)
- S26: [열 PNG](S26_thermal.png) / [SVG](S26_thermal.svg), [에너지 PNG](S26_energy.png) / [SVG](S26_energy.svg)

상세 그래프 원본은 로컬 전용 `Documents/D1Check_Arrival_Extension/energy_thermal_pc_v2/thermal_curves.csv`, `phase_energy.csv`, 전체 표본·provenance·`profiles_connected_v1.json`이다. 이 Windows 외부 경로는 GitHub에 포함되지 않는다. Python numpy/scipy/matplotlib가 있는 환경에서 저장소 root 기준:

```powershell
python -B -m unittest tools.test_d1_energy_thermal -v
python -B -m tools.d1_energy_thermal_analysis --a24 C:/Users/LG/Documents/D1Check_A24_formal_strict_20260911_114101 --s26 'C:/Users/LG/Documents/카카오톡 받은 파일/S26_formal_audit_20260915.zip' --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_thermal_pc_reproduce_NEW
python -B -m tools.d1_energy_thermal_report --analysis C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_thermal_pc_reproduce_NEW
```

추출 root는 새 경로를 사용한다. 이미 추출된 자료의 후처리만 필요하면 마지막 명령만 해당 root에 실행한다. 원본/기존 실험을 재실행하지 않으며 ADB·설치·추론은 없다. 모형 설정은 값뿐 아니라 기기/fingerprint/model hash/condition/sensor/시간·온도 범위를 함께 전달해야 한다. 미식별/미지원 상태는 오류이며 명시적 가정 모드로만 별도 탐색할 수 있다.

실제 보정 설정의 제한된 조건부 예제도 실행했다(초기AP27°C, load60초→cooling60초). 계산112.468J·종료27.027°C는 **모형 출력**이고 새 관측값이 아니다. 아래 Python은 저장소 root에서 재현한다.

```python
import json
from pathlib import Path
from tools.d1_energy_thermal import account
p = json.loads(Path('docs/results/energy_thermal_pc_01/legacy_A24_AP_example.json').read_text())
print(account([dict(start_s=0, end_s=60, state='legacy_load'),
               dict(start_s=60, end_s=120, state='legacy_cooling')], p,
    device=p['device'], model=p['model'], mode='conditional_prediction',
    initial_temperature={'AP': 27}, planned=1, completed=1,
    scope={k: p[k] for k in ('fingerprint', 'model_sha256', 'condition')}))
```
