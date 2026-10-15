# 시작 온도 문제의 별도 대응: 같은 비교군 6조건

**06:43 KST 실제6/6 정상 완료·640본요청 전량 회수·출력오류0·AP창6적격**이다. 저부하/혼합 각각 결과 전 고정한28.8℃ 기준을 공유했다. [실제종료](NEW6_WINDOW_STOPPED.json)·[실제시작버전](MATCHED6_RUNTIME_CONTEXT.json)·[최종보고서](../../../results/a24_final_measurements_20261016/README.md)를 확인한다. 원40 성공대체0이며Jnull/표면미검증/experiment_ready=false다. 아래03:16준비·구큐17설명은 당시 이력으로, 실제 실행은 새큐18에서TRACE2 뒤 최초 수행됐다.

03:16 KST 당시 **PC 준비만 완료, 추가 기기 명령·APP·MAIN·소비0**이었다. 진행 중 C11과 후속 큐17을 변경하거나 동시에 실행하지 않는 계약으로 준비했다.

사용자는 남은 실측·실패 재검사와 시작 온도 문제를 자율적으로 해결하도록 승인했다. 기존 개정혼합 PAIR의27.6℃ 시작 거절과 원저부하27.1℃ 장기 대기 이력을 보존하면서, 비교 대상을 함께 측정하는 유한한 보완 범위를 정했다. 원81+개정4+실패보완12=97의 원장·상한을 수정하지 않고 **새6회를 별도 예약**한다. 합산103은 이 지시를 구체화한 계산상 최대치이며, 사용자가 숫자103을 직접 지정했거나 무제한 재시도를 승인했다고 기록하지 않는다.

| 순서 | 같은 입력·도착·기한으로 측정할 조건 | 본요청 |
|---|---|---:|
| 1–2 | 저부하 직렬 BASE → 분류GPU·탐지CPU 병행 PAIR | 64씩 |
| 3–6 | 혼합 직렬 BASE → EDD → 병행 PAIR → 의도대기200ms | 128씩 |

총6시도·640본요청이다. 두 묶음은 각각 **첫 조건의 준비 후 첫 적격 안정60초에서 기준을 한번 정하고 같은 묶음의 나머지 조건과 공유**한다. 실제 MAIN 허용폭±0.5℃·기울기0.1℃/분·최대공백10초·준비후600초, 모델·입력·기한·응답/저장 완료·실제 자원 반환은 그대로다. 기존 요청 은행의 원바이트/SHA를 유지하며 실행 ID와 정책 ID만 구분한다. 각 ID는 한번만 실행한다.

이것은 관측 후 시작 조건을 개정한 개발 반복이다. 원래 확인40의 성공 횟수·독립5반복을 채우는 자료가 아니며, 이전 실패·미실행·소비를 지우지 않는다. 새저부하 BASE는 C10의 APP전달 실패 이후 새 비교 기준으로도 기록한다. 원C10 실패의 실제 워밍업은 여전히 미확인이다.

04:09 KST PC대조에서 C10 실패BASE와 새BASE는 **요청UUID를 제외한64건의내용·도착·기한·입력과 모델/runtime/target 및 실행설정이 모두 동일**함을 확인했다. 다만 seed메타데이터는2026101554→2026101553으로다르다. 이를숨기거나같은seed의원실행복구라고표시하지않는다. 새BASE는이실행내용이동일한실패사례의새반복으로연결하되초기열상태는개정하고, 실제성공은아직미확인이다. [정규화요청SHA·전체설정대조](C10_BASE_SEMANTIC_EQUIVALENCE.json). 추가7번째시도를만들지않는다.

기존 C11 → 미사용 개정ORDER → 실패보완12를 먼저 안전하게 닫은 뒤 시작한다. 시작 직전 동일폰/APK·SOC10% 이상·비충전·화면·빈프로세스·미사용 ID를 다시 확인한다. 같은 기기 재연결 최대20분, 사용자 중지·이동 우선, 작업자 기술상한 기기12:40/저장12:45 KST를 유지한다. 이 시각은 사용자 직접 지정 마감이 아니다.

## PC 검증과 실행

새 등록 validator/controller/runner를 별도로 추가했다. controller는 원 suite의 등록 import·자기경로·설명문만 다르며 실행 수명주기 원문이 동일하다. PC4검사와 실제6manifest의6authorization 결합이 통과했다. 빈 슬롯·옛 ID·추가 시도·서로 다른 입력·개별 재기준·MAIN 완화를 차단한다. 공통 runtime/APK는 수정·빌드·설치하지 않았다. **PC 검산을 실기기 완료로 표시하지 않는다.**

로컬 메타 `output/A24REBASE6/job.json`, 향후 원물 `Documents/A24REBASE6`, 별도 원장 `A24REBASE6_GLOBAL`이다. 메타의 SHA가 검증 버전이며 실제 시작 HEAD/미커밋 여부는 시작 영수증에 따로 기록한다.

```powershell
python -B -m unittest discover -s tools -p test_d1_a24_rebaseline6.py -v
python -B tools/d1_a24_rebaseline6_runner.py inspect output/A24REBASE6/job.json
# 기존 worker·후속큐가 종료되고 시작전 읽기 검사가 통과한 경우에만 최초1회
# python -u -B tools/d1_a24_rebaseline6_runner.py execute output/A24REBASE6/job.json --execute-authorized
```

[고정 계획](plan.json) · [입력·원템플릿 대응](TEMPLATES.json) · [PC검산](PC_VERIFICATION.json) · [파일 SHA](SOURCE_SHA256.json) · [분석 계약](ANALYSIS_CONTRACT.json)

에너지J 미판정, AP는HAL 보고값·물리표면 미검증, `experiment_ready=false`는 유지한다. 이 추가 측정으로 단위·센서 정확도·독립 모형 검증·정책 우수성이 입증되는 것은 아니다.
