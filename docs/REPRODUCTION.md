# 데이터 복원과 검산

Python 3.11 이상과 표준 라이브러리를 사용합니다.

```bash
git clone https://github.com/mingyujo/D1Check.git
cd D1Check
python tools/fetch_data.py
python tools/verify_submission.py
```

## 파일 복원

큰 파일은 공개 릴리스 ZIP에서 내려받습니다. `fetch_data.py`가 ZIP과 개별 파일의 SHA-256·크기를 확인한 뒤 `data/FILES.json`의 상대 경로로 복원합니다. 기존 파일이 다르면 덮어쓰지 않고 중단합니다. 내려받은 ZIP은 `.data-cache/`에 보관합니다.

```bash
python tools/fetch_data.py --match a24/
python tools/fetch_data.py --match s26/
```

## 검산 범위

- 공개 파일의 크기·SHA-256 확인
- A24 주 평가 9정책×4입력의 원시 요청에서 정시율·미응답·미완료·P95·예측 소비·평균 AP 재집계
- S26 주 평가 4정책×4입력의 원시 요청과 저장 적분값 재집계
- A24 교사 100%·BC 99.9512%, 고부하 정시율 하락, S26 긴급 P95 증가 확인

파일 해시만 확인하려면 `python tools/verify_submission.py --hashes-only`를 실행합니다. 파일이 누락되면 먼저 복원해야 합니다. 검산은 저장 결과의 무결성과 산술 재현을 확인하며, 시뮬레이션·학습·실기기 실험을 실행하지 않습니다.

## 원 코드

기기별 `a24_simulator/`와 `s26_simulator/`의 `experiments/`, `src/`에 모형·정책·실행 코드가 있습니다. 입력·체크포인트·평가 계약은 해당 실험의 JSON에 기록했습니다. 당시 절대 경로가 있는 메타데이터는 출처 기록이며 현재 파일 위치는 `data/FILES.json`을 따릅니다.

새 시뮬레이션을 실행할 때는 해당 세대의 의존성·경로·실행 계약을 확인하고 기존 결과와 다른 출력 폴더를 사용해야 합니다. 위 검산 명령은 새 실행 환경의 구성을 대신하지 않습니다. 측정 앱 소스와 Gradle 자료는 포함하며, APK·서명키·제3자 추론 모델은 배포하지 않습니다.

원자료 보관함에는 무결성 검사용 합성 fixture도 있습니다. `data/raw/4ddb6d…zip`, `data/raw/c6eebc…zip`은 손상 검출용 파일이며 실기기 측정·모형 적합 표본에 포함하지 않습니다. 적합·평가 표본은 각 실험의 입력·모형 매니페스트에서 확인합니다.
