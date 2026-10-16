# 순서·자원 배정·대기 분리 검증과 보완

2026-10-14 사용자 승인: 순서·자원 배정·대기의 효과를 각각 분리해 검증하고, 차이 반영이 부족하면 보완한다. 기존 GEN002 본학습·FINAL·계수·원장·다른 작업은 보존한다.

작업 `work/ROLLING-ATC-RL-37-V2-CAUSAL-20261014`, 출력 `outputs/ROLLING-ATC-RL-37/V2_CAUSAL_20261014`를 별도 계보로 만들었다. REGISTRATION SHA256 `6dc2371dd31a2638d2ee236728ec4339c4e5e669267d0315d5a765c473258352`. 소스·프로필·입력·잠재 서비스·816개 identity를 실행 전에 고정했다.

| 개입 | 고정 | 변경 |
|---|---|---|
| 순서 | 요청별 backend, 의도 WAIT0 | ready FIFO/EDD/LIFO |
| 배정 | 전체 FIFO dispatch 순서, 의도 WAIT0 | 분류 CPU/GPU/S26 NPU |
| 대기 | 전체 FIFO 순서, 요청별 backend | head가 실행가능할 때0/200/1000ms once-per-head 대기 |

Head-of-line blocking과 의도 대기를 구분한다. 센서/도착 사건이 대기를 중단해도 잔여 dose의 절대 종료시각을 보존하며, 실제 총 대기는12초 이하이다. 두 nonzero 정책이 모두12초를 쓰면 총량이 아닌 노출 패턴 차이로 해석한다. 미완료/서비스 손해/실제 개입0을 제외하지 않는다. 병행과 시간 변화는 고정할 교란이 아닌 개입의 매개 결과로 보고한다.

## 발견 및 구현 보완

S26의 원래 문맥 선택은 점유 상태에 따라 탐지CPU의 처리시간 pool과 subphase 비율을 바꾼다. 원본 hash sampling은 같은 context에서는 이미 순서 독립적이다. 순서만의 진단에서는 같은 요청/backend라는 조건만으로 잠재 작업량이 고정되지 않았다.

별도 `paired_service.py`와 controlled Device가 기존 요청/backend별5단계 벡터, context와 subphase envelope까지 고정한다. 원래 context 총효과 모드도 유지해 비교한다. 이 핀은 기제 진단을 위한 명시적 개입이며 새 물리 보정이나 실측 법칙으로 해석하지 않는다. 시동·전환·유휴 복귀의 미측정0계수와 M2 감속 가정은 임의 수치로 채우지 않는다.

## 예산과 순차 실행

2기기×4층×3부하(C3/C10/C11)×2반복×2문맥모드, 기기별8/9개 처방으로816환경이다. 원계획62262+진단816=63078으로 원137712 상한을 유지한다. 자체 heavy1/전체2와 모든 대상 드라이브8GiB를 START 전에 검사한다.

원본 학습·DEV·FINAL·독립감사가 PASS하고 원 작업자/감사 PID가 종료한 후, 같은 worker.lock을 얻어 실행한다. 실제 supervisor PID10040는 현재 WAITING_ORIGINAL이며 진단 환경·추가 heavy0이다. 이미 START된 identity는 재수집하지 않고 prepared raw/manifest가 온전한 경우에만 정확 복구한다.

## 검증 상태와 완료 조건

`TESTS.json`: 순수 통제·표본·격리 코드객체·복구·감사·슬롯/디스크 검증70개 PASS. 실제 Device 초기화/새 production환경/NN/optimizer0이다. 실제 816환경의 검증 완료를 뜻하지 않는다.

실행 후 모든 raw·manifest·START/COMPLETE·SHA, 요인 고정, 잠재 벡터/envelope, 동일 zero 처방의 사건/비용 궤적을 전수 재검산한다. EFFECTS의 처방 변경과 실제 공통 요청의 순서/배정 변경, 미완료 prefix와 실제 dose를 구분한다. MODEL_AND_CONTEXT_ROBUSTNESS에서 모든 모형과 문맥의 차이·반전을 공개한다.

그 결과를 읽고 순서/배정/WAIT 효과의 원인과 누락 경로를 검토한다. 근거 있는 추가 수정이 필요하면 별도 새 등록/출력에서 검증한다. 기존 FINAL로 다시 선정하거나 정책 격차를 키우도록 계수를 선택하지 않는다. 원 V2와 진단의 감사·문서·한국어 결과보고가 모두 끝난 뒤만 자동 확인을 일시정지한다.

등록 당시 HEAD `12d64923be824ce4c88fca074fbe38820f5a7d25`, detached/기존 WIP 보존. 현재 GEN002 원소스59개 SHA 불변. 새 기기/APK/물리fit/외부전송0.
