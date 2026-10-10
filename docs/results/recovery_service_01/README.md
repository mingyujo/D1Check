# 회복 이력과 5phase 처리시간 — PC 분석

실측 추가 없이 기존 이력 통제 12세션의 준비 1,152요청과 후속 768요청을 재사용한다.
새 입력/정책/RL 학습이 아니다. 기존 원자료와 고정 모형은 보존한다.

## 결과 열람 전 고정한 분석 규칙

- 대상: 개발/이미 본 확인 각각 회복30/180 × CPU/PAR 4세션, C0 4세션은 준비와 AP 대조.
- 같은 task/backend/정책에서 회복180−30 처리시간 차이를 보고한다. 동일 ordinal을 연결하고 전체 요청과 네 ordinal 구간을 모두 공개한다. 구간과 요청은 독립 세션 반복이 아니다.
- 5phase는 기존 `dispatch→execution_start→output_ready→persist_complete→worker_release→lane_available`다. phase2는 전처리/호출/출력 준비를 포함한다. 실제 invocation과 execution→invocation을 별도 집계한다.
- numeric AP는 current HAL AP이며 Android monotonic clock의 조회 반환이 요청 dispatch 이전인 마지막 표본만 연결한다(최대10초). host wall clock으로 경계를 옮기지 않는다. 조회 신선도가 하드웨어 센서 갱신시각을 보증하지 않는다.
- AP/경과시간/실제 추론 겹침의 조정 연관은 진단이다. 실제 미래 AP·겹침은 예측 입력이 아니다. 회복기간과 시작 AP/시간순서의 연관은 인과적인 스로틀 식별과 다르다.
- 후보 구조 **하나**: 정책×task/backend별 개발 두 세션을 같은 가중으로 평균한 고정5phase 대조에 `phase2 *= exp(gain × (부하 전 AP − 개발평균 AP))`를 적용한다. 다른 phase는 같은 개발 평균으로 고정한다. gain은 개발 두 AP/로그 phase2 평균의 기울기이며 비음수로 제한한다. 확인은 추정/재선택에 사용하지 않는다.
- 두 개발점은 기울기의 잔차 자유도가0이고 한 회복기간을 제외하면 식별 불가다. 다른 세션의 전이로 평가하되 이미 본 자료의 사후 평가다. 원고정 모델과 같은 개발자료의 고정 대조를 둘 다 표시하여 재보정 효과와 AP 입력 효과를 분리한다.
- 후보는 시작 AP 하나를 사용하고 실행 중 일정한 벡터를 반환한다. **냉각 중 속도 회복을 전파하는 동적 모형은 아니다.** 시간/온도 반응 관계가 확인되지 않으면 기존 일정 엔진/RL을 바꾸지 않는다.
- 미측정 cell/식별되지 않는 기울기는 null. 개발 AP 범위 밖 호출은 기본 차단하며 별도 외삽 진단만 명시적으로 허용한다. 정확도 PASS·보편적 무스로틀·정책 우월성·strict 확대를 선언하지 않는다.
- 후보 재탐색/자료 선별/전체 시뮬레이션 배치/ADB/설치/추론/실측/빌드/새 기기 계획/claim 모두0.

## 재현

원자료 재추출(기기 명령 없음, 새 출력 경로):

```powershell
python -B -m tools.d1_recovery_service extract --raw-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension' --output output/recovery_service_fresh
```

공유 숫자 입력의 재분석은 `registration.json`의 입력/소스 해시와 일치하는 별도 폴더에 `run_v1/inputs.json`을 복사하고 다음을 실행한다.

```powershell
python -B -m tools.d1_recovery_service analyze --output output/recovery_service_fresh
python -B -m unittest tools.test_d1_recovery_service -v
```

실행/그림/최종 판독은 완료 후 이 안내에 연결한다. 새 자료나 검증 완료 그림으로 표현하지 않는다.
