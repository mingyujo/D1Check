# REPLAN-PC-01 PC 검증 기록

[계약](../../REPLAN_PC_01_20260925.md) / [소스](../../../tools/d1_arrival_interaction.py) / [테스트](../../../tools/test_d1_arrival_interaction.py)

버전 `arrival-interaction-pc-v1`. `c0524cb` 위 미커밋 구현을 검증했다. 실행 시점·정확한 소스 bytes/LF hash는 [VERIFICATION.json](VERIFICATION.json)에 있다. **PC 기능 검증이며 성능 평가가 아니다.** 실측·ADB·설치·추론·기존960배치·전체 빌드 실행은 없다.

## 실제 수행한 명령

저장소 root에서:

```powershell
python -X utf8 -m unittest tools.test_d1_arrival_interaction tools.test_d1_arrival_explore -v
python -X utf8 -m tools.d1_arrival_interaction --demo --output C:/Users/LG/Documents/D1Check_Arrival_Extension/replan_pc_01_v1/functional_demo.json
```

첫 명령은 새23건+직접 영향받는 기존 엔진15건, 총38건 통과했다. 두 번째 명령은 작은 합성3trace를 실행하고 수작업 기대 시각과 일치했다. 출력 파일은 덮어쓰지 않는다. 재현 시 `--output`에 **아직 없는 새 파일 경로**를 지정한다. 이 CLI에는 실기기·성능 배치·B2 선정 기능이 없다.

이 밖에 `git show c0524cb:tools/d1_arrival_explore.py`의 코드를 메모리에서 읽고 현재 엔진의 기본 호출과 같은 작은2요청 입력을 비교했다. CPU_URGENT/B2_PC/P_PAIR_COST_PC의 ledger·결정·전이·지표를 포함한 전체 반환값이 각각 일치했다. 기존 결과 재생성이나 P 개선 실험이 아니다. 새 테스트의 전체 기능 비활성 경로 비교와 함께 기본 동작 보존을 확인했다.

초회 테스트2건은 수작업 기대값에서 no-selection 판단의 남은 비용을 빠뜨려 실패했다. 기존 trace를 읽어 P=90에서 시작한12ns 판단이 L=100을 지나102에 끝나는 경우, 96~108 판단이 timer100을 지나가는 경우를 확인했다. 새 dispatch 기대를 각각117/120ns로 바로잡았다. 비용을 삭제하거나 구현을 유리하게 조정하지 않았다. 외부 `replan_pc_01_v1/tests_final.txt`를 보존했고, 조작 없는 on/off의 동일성을 비용0/비용양수 양쪽으로 보강한 최종38건 로그는 `tests_final_v2.txt`다. 이 보강은 테스트만 바꿨으며 demo 실행 코드/결과는 불변이다.

## 수작업 trace

모든 예제는 CPU 직렬, 합성 D→S=1초, S→O=2초, O→P=3초, P→W=0.4초, W→L=0.6초다. 판단 비용0도 기능 fixture의 가정이다. normal 분류는 t=0, urgent 탐지는 t=1에 도착한다. T=20초·drain=20초, 기본 idle=15초로 공통이다. **이 숫자는 기기 서비스시간이 아니다.**

| 조작 입력(초) | 요청 | dispatch | output_ready | persist | lane 해제 |
|---|---|---:|---:|---:|---:|
| 없음 | 배경 | 0 | 3 | 6 | 7 |
| 없음 | 대화형 | 7 | 10 | 13 | 14 |
| 0, 20 | 배경 | 15 | 18 | 21 | 22 |
| 0, 20 | 대화형 | 1 | 4 | 7 | 8 |
| 0, 1, 2 | 배경 | 17 | 20 | 23 | 24 |
| 0, 1, 2 | 대화형 | 1 | 4 | 7 | 8 |

[작은 기대/실제 시각 JSON](hand_trace_summary.json)에 배경 분모와 T/horizon의 완료량도 기록했다. 조작20이 배경 실행을 선점하지 않는 점, burst 후17에서 타이머가 여는 점, urgent도 이미 실행 중인 비선점 요청을 추월할 수 없는 점을 확인하는 예제다. 정책 순위·성능 이득을 계산한 표가 아니다.

전체 결정·gate·전이 로그는 담당자 PC 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/replan_pc_01_v1/functional_demo.json`에 있다. GitHub 공유물은 코드·계약·소규모 합성 요약뿐이다. 원 실측 자료·APK·모델·키는 포함하지 않는다.
