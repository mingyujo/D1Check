# 데스크톱 이관: CPU/GPU 시뮬레이션과 PPO 학습량 비교

**데스크톱에서 반복 평가와 추가 학습을 할 수 있다.** 필요한 것은 측정에서 동결한 JSON 모형·초기 입력, Python 코드와 PPO 체크포인트다. Android Studio·ADB·휴대폰·APK·이미지 분류/탐지 TFLite 파일은 PC 시뮬레이션 실행에 필요하지 않다. CPU/GPU는 시뮬레이션 안에서 배정하는 휴대폰 자원이며 현재 PyTorch 학습은 CPU에서 수행한다. 데스크톱 GPU가 있다는 이유만으로 현재 학습이 빨라진다고 보장하지 않는다.

이번 기록은 **기존 PC의 격리 폴더에서 import·모형 로드·체크포인트 복원을 검산**한 것이다. 새 데스크톱에서 설치하거나 추가 학습한 결과는 아니다. 기존 종료 실행의 시간·예산을 초기화하거나 다시 시작하지 않았다.

## 바로 옮길 파일과 최종 검산

실행 ZIP은 로컬 `output/desktop_handoff_20261011_v1/D1Check-desktop-cpu-20261011.zip`이다. **1,743,807 B(약1.67MiB)**이며 Python/고정 자료/원terminal64 세개/seed 예약 목록/검산 명령을 포함한다. SHA-256은 `4d7e0fcf65591a2ec015604fb69ea8f10358c72e28f1703a18989f6f8546241c`이다. ZIP·PT는 Git에 넣지 않고 작은 설명·source·manifest만 공유한다.

압축을 풀고 `D1Check-desktop-cpu-20261011` 폴더에서 위 환경을 준비한 뒤 기본 명령을 실행한다.

```powershell
python -B -X utf8 -m tools.d1_joint_amount_cli
```

별도 폴더에서 기존 저장소의 PYTHONPATH와 Git 없이 기본검증·13순수검사를 통과했고, 동결 actor 세개로 **시뮬레이션3회/72요청 전량완료/학습0**의 실제 엔진 실행도 확인했다. 사용한 것은 이미 본 low/mean 개발 입력이므로 새 성능 확인으로 집계하지 않는다. 같은 PC의 격리 실행이며 다른 하드웨어에서 검증한 것은 아니다. 최종 학습 연장 전체를 실제로 실행한 것도 아니다.

처음에는 테스트용 등록에 seed-registry SHA가 없어 Git 없는 폴더의5검사가 실패했다. 실제 registry 잠금 기준은 유지하고 테스트 등록만 보완한 뒤13검사를 통과했다. 엔진3회는 정상 종료했지만 stdout JSON에 NumPy int64를 직접 넣은 출력 오류가 있었으며 formatter만 수정·검산했고 환경을 다시 실행하지 않았다. 원 실패와 원 source SHA는 보존했다. [패키지 영수증](bundle_receipt.json)·[파일 SHA](bundle_manifest.json)·[엔진3회](functional_smoke.json)·[출력 수정](smoke_stdout_repair.json)을 확인한다.

export한 예약 목록은313seed/3폐구간이다. 이는 이관 시점까지의 등록 자료를 보수적으로 정리한 것이며, 여러 PC가 이후 새 실험을 동시에 등록하는 전역 서비스가 아니다. 여러 PC에서 서로 다른 독립 평가를 한다면 새로운 seed 범위를 함께 관리해야 한다.

## 실제로 필요한 환경

| 항목 | 확인한 버전·필요성 |
|---|---|
| Python | 3.11.9, 현재 Windows 64bit |
| NumPy | 2.4.6, 모형·관측·학습 배열 계산 |
| PyTorch | 2.11.0+cpu, 자체 masked PPO·Adam·체크포인트 |
| Matplotlib | 3.10.9, 그림 생성 때만 필요 |
| SciPy·Pandas·Gymnasium·SB3·sb3-contrib·OR-Tools | 확인한 import/복원 경로에 불필요 |

새 PC의 설치는 아직 수행하지 않았다. 동일 버전을 준비하는 명령은 다음과 같다. 그림이 필요할 때만 보고용 requirements를 추가한다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install numpy==2.4.6
.\.venv\Scripts\python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.11.0+cpu
.\.venv\Scripts\python -m pip install -r docs/results/desktop_handoff_20261011/requirements-report.txt
```

이 문서의 core requirements는 위 두 패키지의 정확한 pin이다. PyTorch 설치 출처는 [공식 CPU wheel 목록](https://download.pytorch.org/whl/cpu/torch/)이다. Python/라이브러리 버전이 같아도 OS·CPU·수치 라이브러리가 다르면 이후 학습의 비트 단위 동일성을 자동 보장하지 않는다. 새 PC에서 먼저 패키지 SHA·상태 복원 검사를 통과해야 한다.

## 고정 입력과 작은 독립 payload

실제 모형 로드와 다음 에피소드용 controller 준비에서 읽은 JSON은 네 개다.

| 논리 경로 | 크기 |
|---|---:|
| `docs/results/list_candidate_rl_review_01/design_amendment_v4.json` | 16,669 B |
| `docs/results/online_policy_study_01/overnight_sustained_run01/model.json` | 3,689 B |
| `docs/results/online_policy_study_01/overnight_sustained_run01/initial_inputs.json` | 385,561 B |
| `docs/results/rolling_hybrid_pilot_07/model.json` | 3,941 B |

모형/controller의 실제 Python import closure는 **59개, 759,945 B**였다. 네 JSON을 합친 원본 총량은 **1,169,805 B**이다. 전체 저장소나 기존 대용량 output을 복사하지 않고 이 파일들을 원래 상대 경로로 담는 작은 독립 payload를 구성할 수 있다. 새 실행 CLI와 별도 등록·입력·예산 파일은 그 실행 계약에 따라 추가한다. 59개 목록은 import/복원 범위이며 아직 수행하지 않은 모든 명령의 의존성을 전부 검증했다는 뜻은 아니다.

세 PPO `.pt` 파일은 Android AI 모델 파일과 다르다. 기존 학습을 이어가려면 actor·critic·optimizer·RNG 등을 담은 이 세 파일이 필요하다. 파일당 약 1.18MB이고 원본은 비공유 로컬 output에 보존했다.

원본 source와 입력을 직접 stage하지 않았다. 이관 source에는 과거 기기 스크립트의 ADB 기본 경로 문자열 세 곳만 `D1CHECK_ADB` 환경변수로 바꾼 격리 복사본을 사용했다. 세 함수의 역할은 기기 실행용 PowerShell 문자열 생성이며 시뮬레이션·actor·controller 판단을 바꾸지 않는다. 56개 Python과 네 JSON은 원본 바이트 그대로다. 원 SHA, 실행 당시 유효 SHA, UTF-8/LF 정규화 SHA, portable SHA를 각각 남겨 같은 의미로 혼용하지 않는다. 공개 patch 명세에는 원 개인 경로가 포함된 삭제 줄을 넣지 않는다.

## 세 체크포인트의 실제 상태

| 학습 초기화 seed | 완료 학습 | update | Adam step | pending | SHA-256 앞 12자 |
|---|---:|---:|---:|---:|---|
| 11 | 64 | 8 | 96 | 0 | `338dacaaa875` |
| 23 | 64 | 8 | 96 | 0 | `4ddc0d0f3e50` |
| 37 | 64 | 8 | 96 | 0 | `67a5891357c7` |

각 파일은 actor·6출력 critic·14개 Adam parameter state·승수 5개·Python/NumPy/PyTorch RNG·에피소드 cursor·누적 소비·로그를 보존한다. `next_episode=64`이고 에피소드 경계에서 저장됐다. 같은 PC의 격리 source로 복원한 **16개 핵심 필드가 원본과 정확히 같았고**, 다음 에피소드용 controller 생성도 통과했다. 추가 에피소드나 optimizer update는 실행하지 않았다.

현재 checkpoint는 **서비스 envelope V1 후보 규칙 + 절대 서비스 비용 목적 V2**의 PPO다. 실제 정책 ID는 `JOINT_SERVICE_ENVELOPE_ABSOLUTE_MASKED_PPO_V2`, schema는 `e503673a51d2df599cc5c33a66e8c1d7787fe361eeea085f3e5ddee9ebaf2a1e`다. 이름의 V2만 보고 이후 서비스 envelope V2 후보 규칙과 같은 설계로 취급하면 안 된다. 행동·마스크·참조·목적을 바꾼 설계에는 이 optimizer/weights를 조용히 이어 붙이지 않는다.

원 세 learner는 seed 11/23/37로 각각 초기화한 뒤 round-robin 순서로 **하나의 전역 sampling RNG stream을 공유**했다. 독립된 세 action sampling stream으로 실행했다고 표현하지 않는다. 원 순서를 그대로 재현하려면 세 learner의 복원 순서와 마지막 session RNG, 다음 case cursor를 함께 고정해야 한다. seed별 RNG를 분리하는 새 실행은 기존 연속 실행과 동일하다는 주장과 구분해서 등록한다.

`last_controller_state`에는 `JointActual` 객체가 있는 진단 archive가 들어 있다. 이를 JSON digest에 바로 넣으면 직렬화 오류가 발생한다. 위 16필드 검사는 이 객체 전체의 JSON 동일성을 주장하지 않는다. 저장된 실행 중 engine을 재개하는 것이 아니라, 다음 에피소드에서 새 engine/controller를 만든다.

## 횟수를 늘릴 때 먼저 등록할 것

기존 작업은 500환경·192학습으로 닫혔다. 기존 `run`을 다시 실행하거나 old budget을 늘리는 방식으로 진행하지 않는다. 다음 정보를 가진 새 작업으로 등록해야 한다.

1. 부모 terminal 세 파일·등록 계약·표시만 수정한 revision·모형·입력·source의 SHA와 정확한 policy/schema/objective.
2. 세 초기화 seed에 동일하게 추가할 학습량과 update 간격. 기존 64에서 시작한다는 cursor와 sampling RNG 방식을 고정한다.
3. 학습·개발·새 확인의 입력/seed 분리. 이미 확인한 833 계열이나 이후 확인 자료를 새 독립 평가라고 다시 사용하지 않는다. 앞으로의 도착 seed는 미소비 여부를 전체 기존 등록 목록과 대조한다.
4. 학습·기준선 생성·개발 평가·확인 평가·fixture를 포함한 환경 총 상한, 학습 상한, wallclock, 마지막 저장 예약과 실행 전 소비 기록. 실패한 시작도 소비로 남긴다.
5. 종료/중단 시 actor·critic·Adam·RNG·승수·부분 batch·case cursor·소비를 함께 저장한다. 완료 조건과 동등 예산의 세 learner를 우선하며 최고 seed만 고르지 않는다.
6. 최종 서비스·완료량·긴급 P95·J·AP 기준을 유지하고, reward 증가나 더 많은 학습 자체를 개선으로 판정하지 않는다.

source의 줄바꿈만 정규화한 경우에도 원 checkpoint dependency 명세를 덮어쓰지 않는다. portable 허용 patch와 새 실행 source 명세를 추가로 잠가 원본 lineage와 구분한다. 이번 59파일 복사에는 서비스 envelope V2의 새 정책 source를 포함하지 않았다.

새 이관 CLI의 기본 명령은 검증만 수행한다. 원본 등록/체크포인트·portable patch 영수증을 포함한 최종 패키지에서 먼저 아래 명령을 실행한다.

```powershell
python -B -X utf8 -m tools.d1_joint_amount_cli
```

기본 동작은 verify-only이며 학습·환경 실행을 시작하지 않는다. `prepare`와 `run`에는 별도의 명시적 예산이 필요하다. 이번 모바일 담당의 검산은 위 CLI의 새 데스크톱 실행까지 포함하지 않으며, 격리 폴더의 모형/체크포인트 복원만 확인했다.

시뮬레이션 횟수를 늘려도 냉각에 따른 처리속도 회복·미측정 온라인 정책 비용·실제 최고 표면 온도를 새로 검증할 수는 없다. 현재 모형에서 가능한 방법론 비교와 실제 휴대폰 효과의 범위를 유지한다.

검산 근거: [로컬 격리 복원 영수증](portable_load_receipt.json), [portable 경로 치환 명세](portable_patch_receipt.json), [core 요구사항](requirements.txt). 실제 독립 payload와 세 checkpoint는 `output/desktop_handoff_20261011_v1`에 보존하며 Git에 binary·원장·개인 환경을 넣지 않는다.
