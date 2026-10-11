# D1Check 데스크톱 64→512 학습량 연장 결과

세 PPO 모두 원 strict 최종 기준 미달이며 자동 채택은 0이다. 승인된 학습·평가 실행은 완료했다. 추가 학습 1,344회와 환경 2,200회 전량 완료, native 오류 0회다. 별도 기능 smoke는 3환경·72요청·학습0이다.

## 실행과 보존

- task `amount512_desktop_20261011_a`. 원 64 상태의 세 actor/critic/Adam/승수 및 공유 round-robin sampling RNG를 보존해 각 448회 추가했다. 세 독립 sampling stream이 아니다.
- 세 모델 각각 512에피소드·64update·실제 Adam step은 [상태 영수증](final_verification.json)에 기록했다. 원 dependency/settings/schema와 96개 ZIP 파일, 2,200 item SHA, 요청 원장, 선택 mask를 검산했다. 공유 session은 마지막 학습 경계1792환경/1344학습을 담고 최종 원장은 평가를 포함해2200환경이다.
- 실제 `REQUEST_STOP` 중지·재개 1회: 환경 경계에서 세 모델/partial batch/공유 RNG/cursor/소비를 저장, clock 정상 닫힘을 확인 후 같은 task로 재개했다. 강제 종료·예산/clock 초기화·학습 cached replay 0회.
- 상한 환경2300/학습1344/활성240분·저장10분. 실행 프로세스 wall 합계 21.850분, 중지휴식을 포함한 최초run→완료 wall 24.034분, 누적 active 21.764분, Windows process-tree CPU 20.595분. 중지휴식 131.057초는 active에서 제외된다.
- 다운로드·설치·문서 점검 합산 wall 178.882초, verify/unit/smoke/prepare 명령 wall 31.885초. 전자는 다운로드 프롬프트 mtime부터 첫검증까지의 합산 구간이며 설치 개별 CPU시간은 측정하지 않았다. 상세 [시간 원장](timings.json).
- parent 종료 소비500/192 유지. 이 V1 계보는2700환경/1536학습이다. STATUS의 전체 관련계보 기저14735/3181에 이번2200＋smoke3/1344만 더해16938/4525로 기록한다. 모든 과거 PPO를 합산한 프로젝트 총계는 아니다.
- Windows11 64bit/Ryzen5 5600/약16GB RAM/Python3.11.9/NumPy2.4.6/Torch2.11.0+cpu/Matplotlib3.10.9. 기존 호스트 NumPy2.1.3/Torch2.7.1+cu118는 유지하고 별도 venv를 썼다. 패키지 import 기본 스레드는6이지만 동결 learner는1스레드와 결정적 PyTorch 연산을 설정한다. OS/CPU 간 학습 비트 동일성을 주장하지 않는다. 다운로드 파일/venv/패키지 설치의 별도 시각 경계와 설치 구간은 [환경 영수증](environment.json)에 기록했다. 파일 시각은 네트워크/설치 전체 stopwatch와 구분한다.

## 같은 새 48조건의 원단위 결과

4 arrival seed×4부하×3모형문맥의 48조건이며 48독립 실측이 아니다. 7정책이 동일한 ticket/profile/initial/settings를 사용한다. 긴급 P95 표의 값은 48개 조건별 P95의 산술평균이며 모든 요청을 합친 pooled P95가 아니다. AP는35~180초 모형 내부 채널이고 J는120초 동결 모형 비용이다.

|정책|완료/예정|긴급 실패|일반 실패|긴급 P95 평균 ms|J120 평균 J|최고 AP 평균 °C|
|---|---:|---:|---:|---:|---:|---:|
|Band|3168/3168|0|40|352.020|152.279526|30.448681|
|Triton|3168/3168|0|39|390.176|152.744661|30.468728|
|JointList|3168/3168|0|40|401.722|152.280281|30.448789|
|CostList|3168/3168|0|40|401.722|152.280281|30.448789|
|PPO11_512|3168/3168|0|40|352.020|152.587427|30.461979|
|PPO23_512|3168/3168|0|40|418.403|152.366115|30.445298|
|PPO37_512|3168/3168|0|40|418.403|152.366115|30.445242|

원 zero-epsilon gate를 그대로 재계산했다. gate 비교군은 Band/Triton/CostList이고 JointList도 원단위 대응 CSV에 함께 비교했다.

- PPO11_512: maintenance_pass=False, promising=False, promising_families=[].
- PPO23_512: maintenance_pass=False, promising=False, promising_families=[].
- PPO37_512: maintenance_pass=False, promising=False, promising_families=[].

PC 판단시간은 callback 기록의 평균/P95/합계로 [요약 CSV](summary.csv)와 [48조건 CSV](confirmation48.csv)에 기록했다. 이 시간은 폰 온라인 제어비용이 아니다. 모든 조건의 완료·실패·응답·J·AP 차이는 [대응 차이](paired_condition_deltas.csv)를 따른다.

## 64와512의 학습량 비교 범위

원64의 공개 저장 결과와 이번512의 **이미 본 개발24**를 같은 arrival/family/context/planned로 대응시켰다. 새 독립 확인으로 부르지 않는다.

- seed 11: 일반 실패 18→18, 긴급 P95 조건평균 변화 +0.000000ms, J +0.000000J, AP +0.000000°C.
- seed 23: 일반 실패 18→18, 긴급 P95 조건평균 변화 +50.871116ms, J +0.101492J, AP -0.004066°C.
- seed 37: 일반 실패 18→18, 긴급 P95 조건평균 변화 +70.078614ms, J -0.239067J, AP -0.016713°C.

신규 확인48에는 계획된512 세 PPO와 네 비교군만 실행했다. 다른 seed의 과거64 확인자료와 새512 자료를 직접 대응 효과로 합치지 않는다. 새48의64 actor 추가평가는 실행하지 않았으므로 학습량의 독립 인과효과·수렴을 확정할 수 없다. [개발 대응72행](development64_to512.csv)과 [실제 학습로그](learning_updates.csv)를 함께 보존한다.

## 한계와 다음 행동

학습량 증가만으로 개선을 보장하지 않는다. V1의 허용된 예측 비용 개선후보0이라는 기존 제약을 보존했으며 정책/보상/mask/기한/지원/optimizer/판정 기준 변경0이다. 기존 기본·strict·experiment_ready=false를 유지한다. 휴대폰/ADB/추가실측/NPU/새모형/하이퍼파라미터 탐색0이다. 냉각에 따른 속도 회복·표면 최고온도·폰 제어비용·실기기 절감은 이번 모형으로 새로 입증하지 않았다.

다음 행동은 이번 대응 결과를 검토하고, 제약과 최종KPI의 정렬이 필요하면 별도 설계·새승인·새독립자료로 검토하는 것이다. 이 task는 완료되었으며 남은 상한으로 자동 재실행하거나 확대하지 않는다.

## 보존 파일과 검증

[오프라인 화면](index.html) · [계약](execution_contract.json) · [전체 평가CSV](all_evaluations.csv) · [SHA/원장 검산](final_verification.json) · [ZIP검산](bundle_verification.json) · [seed이력 검산](registry_verification.json). 원 raw/item/PT/원장/동결 source는 로컬 archive에 보존하고 Git에는 작은 코드·설정·보고서만 반영한다. Git 반영·원격HEAD 결과는 별도 영수증으로 남긴다.

기능 검증 명령은 `python -B -X utf8 -m tools.d1_joint_amount_cli`, 지정13 unittest, 지정 `run-smoke`이며 모두 PASS다. 실행기준HEAD는8175aac95c82fa70860e07e2e7566797b92b7736, ZIP SHA는4d7e0fcf65591a2ec015604fb69ea8f10358c72e28f1703a18989f6f8546241c다.

사소한 호스트 오류: registry receipt 검사 첫 시도에서 공개 저장소에 없는 로컬 cases.json을 읽어 FileNotFoundError가 났다. 공개115파일/가용 receipt와 원export313seed/3구간을 구분해 검사했고 source/registry 수정 없이 충돌0을 확인했다. Git CLI dry-run은 인증부재로 실패하여 연결된 GitHub 앱의 commit/ref 경로를 사용했다. 첫 verify CPU시간은 venv redirector만 측정되어 총CPU에서 제외하고, 이후 stage는 Windows job의 자손까지 측정했다. 모든 오류는 환경/학습 소비0이며 원 로그를 보존한다.
