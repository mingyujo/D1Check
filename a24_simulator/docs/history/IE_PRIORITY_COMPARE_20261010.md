# 산업공학 우선순위·CPU 병목 보호의 같은 조건 비교

작업 `IE-PRIORITY-COMPARE-02`. 사용자 “비교한번해봐” 지시로 EDD+ECT와 최소 여유시간, 임계비율, ATC, 최소 여유시간＋CPU 보호를 PC에서 비교한다. 성능 개선을 전제하지 않으며 RL 학습·실측·기기 실행은0이다.

## 결과 확인 전에 고정한 대응과 설정

제조업의 완료 납기는 앱의 기존 응답 완료에 대응한다. 분류는 OUTPUT_READY(2단계), 탐지는 PERSISTED(3단계)이며 자원 점유는 실제 AVAILABLE(5단계)까지다. CPU/GPU를 독립적으로 아무 작업이나 처리하는 기계로 가정하지 않고 원 CG_DC 조합만 허용한다. 전체 도착 큐를 우선순위로 정렬하고 같은 원 ECT로 자원을 배정한다. 선점·실행 중 이동·요청 삭제·새 냉각 대기·NPU·새 모델/계수는 추가하지 않는다.

|원 개념|이번 엔진 대응|보존|변경/생략·판정|
|---|---|---|---|
|EDD＋ECT|기존 절대 응답 기한순, 지원 backend의 예상 5단계 lane 종료 최소|원 기한·동점·자원대기·overrun 처리|원 `IE_EDD_ECT_LANE_PC_V1`과 wrapper의 실제 원장/전이/지표 일치 gate. 기존 제한 재현 유지|
|최소 여유 MS/MST|기한−ECT 선택 자원의 예상 응답 시각을 최소화|처리시간과 기한을 함께 고려|응답 경계·공개 자원 대기가 포함된 제한적 적용 B|
|임계비율 CR|남은 기한÷(ECT 경로 예상 응답−현재시각)을 최소화|상대적인 납기 긴박함|분모에 자원 대기도 포함한 response lead-time 적용 B; 제조의 순수 remaining processing과 동일하다고 하지 않음|
|ATC|`log(5단계 서비스시간)+max(0,기한−예상응답)/(k·평균5단계 서비스시간)` 최소화|짧은 점유와 납기 긴박함 결합|응답 여유와 lane 생산성 분리한 적용 B. 모든 w=1, k=2는 이번 사전 설정이며 보편 기본값/최적 튜닝값이 아님|
|자원 적합성·낮은 유연성 작업 보호|MST 선택 C의 CPU/GPU 경로별 현재 도착 D-only 후속 기한 위반 수 비교|CPU전용 탐지와 CPU/GPU 분류의 비대칭성|우리 자체 제한적 보호 규칙. C의 GPU 응답이 기한 내이고 D 위반 수가 엄격 감소할 때만 GPU로 변경. 다른 미배정 C·미도착 요청은 이 보호 예측에 미포함|

MS·CR 정의의 근거는 [생산 스케줄링 연구](https://www.mdpi.com/2073-431X/5/1/3), ATC는 [Vepsäläinen–Morton 연구](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.33.8.1035)다. 자원 적합성은 [LFJ-FM 연구](https://www.sciencedirect.com/science/article/abs/pii/S016763771300120X)의 개념만 참고했다. 그 연구의 선점·확률분포 가정과 최적성 결과를 우리 비선점 이종 자원에 전용하지 않는다. 원문 규칙 전체·산업 시스템·전역 최적 재현을 주장하지 않는다.

비교 역할은 EDD/MST/CR/ATC/보호5개＋기존 L0/Band 요청 단위 적용/Triton 요청 단위 적용/완료 비학습 TailRule4개, 총9개다. 다섯 산업공학 정책은 같은 ECT를 공유하며 보호만 명시한 GPU 경로 예외를 둔다. 모델/입력/기한/초기 상태/실현 비용/응답과 lane 반환/공통 관측창은 동일하다. ATC와 보호의 가중치·임계값 탐색0, 결과 후 튜닝0이다. 기본 정책·기존 RL·strict·experiment_ready=false는 보존한다.

## 작은 검증과 실행 계약

- 순수9검사: EDD/MST 차이, MST/CR 차이, ATC 식·고정 k, 보호 발동/비발동, 응답/실제 lane 반환 구분, 미래·미지원 입력 거절, 기존 EDD 결정 일치, overrun을0으로 대체하지 않음. 수작업 상태는 규칙 정의 검증이며 실측/실제 도달 가능한 전체 성능 증거가 아니다.
- 실제 gate16: 고정4작은 입력×기존EDD/새EDD/MST/보호. 새 EDD의 원장/전이/지표가 원 EDD와 같아야 비교 배치를 진행한다.
- 개발:822020101/102 ×낮은 부하/큐 몰림/순간 몰림/지속 부하×원3실현문맥＝24조건×9정책216회.
- 새 확인:822030101/102 ×같은4부하×같은3문맥＝24조건×9정책216회. 설정/조건을 결과 전에 고정하며 두 확인 도착 seed는 작은 파일럿 근거다. 원3문맥은 독립 반복이나 확률 오차 한도가 아니다.
- 예상16＋216＋216＝448환경, 새 cap480환경·학습0·45분/마지막5분 저장 예약이다. 원 누적9269환경/1449학습을 계승해 끝나면 예상9717/1449다. 닫힌 이전 tranche의 잔여132/12와 옛 실험 예산은 초기화하거나 재개하지 않는다.
- 완료·실패·미완료 분모, 긴급P95, 일반 기한 위반/완료, J120, AP35..180, 판단 시간/자원 점유를 보고한다. EDD 대비 차이와 별도로 기존 L0/Band/Triton 전조건 서비스·J/AP 기준을 적용한다. 평균 이득으로 조건별 악화를 가리지 않으며 임의 epsilon/SLA/열 한도를 추가하지 않는다.

## 진행 결과

48조건×9역할의 432행과 실제 회귀 gate16, 총448환경을 완료했다. 학습·기기 명령은0, 실패·미완료0이며 gate를 포함한 예정28,544요청 전량이 완료됐다. 기한 초과 성공은 완료와 별도로 분모에 남긴다. 누적9717환경/1449학습, 새상한480의 잔여32는 자동 재학습 예산이 아니다.

### 새 확인24조건의 결과

각 정책의 예정·완료는1584건이다. P95·J·AP는 조건별 값의 평균이며 전체 요청을 합친 P95가 아니다. AP는 같은 AP 채널의 조건별 최고값 평균이다.

|방법|긴급 기한 실패|일반 기한 실패|긴급 P95 평균 ms|J120 평균 J|최고 AP 평균 °C|
|---|---:|---:|---:|---:|---:|
|EDD＋ECT|0|37|295.451|152.448980|30.801173|
|최소 여유＋ECT|0|37|295.451|152.448980|30.801173|
|임계비율＋ECT|9|42|760.560|152.432066|30.821296|
|ATC＋ECT|0|37|295.451|152.448980|30.801173|
|최소 여유＋CPU 보호|0|36|295.451|152.447234|30.801983|
|기본 리스트 L0|0|18|339.101|152.312222|30.876933|
|Band 요청 단위 적용|0|18|339.101|152.292099|30.874164|
|Triton 요청 단위 적용|0|18|373.569|152.766719|30.915199|
|비학습 꼬리 비용 선택기 TailRule|0|18|339.101|152.275769|30.880173|

**최소 여유와 ATC는 개발·확인48조건 모두 EDD와 원장 및 전이가 정확히 같았다.** 다른 규칙이 구현됐는지는 수작업 반례로 확인했지만 이번 도착/기한/동결 비용에서는 실제 순서를 바꾸지 못했다. 이것을 해당 규칙의 일반적 무용성으로 해석하지 않는다.

CPU 보호는 개발3·확인1조건에서 실제 GPU 배정을 바꿨다. 개발 일반 실패37→34, 확인37→36이며 확인 평균 에너지는−0.001746J, 최고 AP는＋0.000810°C다. 열·에너지 공동 우위는 없고 매우 작은 모형 차이다. CR은 확인에서 긴급 실패9건과 일반 실패 증가를 만들었으므로 에너지 소폭 감소를 개선으로 채택하지 않는다.

L0/Band는 EDD보다 일반 서비스와 J가 좋지만 EDD의 긴급 P95·AP가 더 낮다. TailRule 역시 에너지와 AP의 상충이다. 기존 조건별 서비스·J·AP 비악화 판정에서 새 적격 후보는 없으므로 **기존 기준 유지, 새 방법론 채택 보류**다. 실제 Band/Triton 제품 전체보다 우월하다는 뜻은 아니다.

### 결과를 설명할 때 구분할 점

이번 EDD의 ECT는 지원 자원 전체에서 예상 5단계 lane 종료를 최소화하고, 최선 lane이 바쁘면 기다린다. 다른 작업을 먼저 채우지 않는다. L0는 현재 실행 가능한 후보 중 자원을 선택하고 작업 head를 채운다. 따라서 L0 대비 차이는 기한 순서뿐 아니라 자원 예약·대기/즉시 배정 구조를 포함한다. MST/CR/ATC의 EDD 대비 비교에는 같은 ECT가 유지된다.

동결5phase는 AP가 내려가면 서비스가 빨라지는 법칙을 포함하지 않는다. J120과 AP35..180은 기존 측정 계수의 모형 계산이며 표면 온도·미측정 제어 에너지·온도 한도 초과 시간은 계산 불가다. 3실현문맥은 민감도 조건이고 독립 표본/실측 오차 신뢰구간이 아니다. 확인 도착 seed2개의 작은 결과로 수렴·실기기 절감·전역 최적을 주장하지 않는다. 정책별 PC 콜백 시간도 호출 대상이 달라 그대로 폰 제어비용 우열로 전용하지 않는다.

## 검증·산출물·재현

순수 정의/실행 계약/기존 산업공학 검사20 PASS, 실제 EDD gate16 원장·전이·지표 exact PASS. 원장 감사448환경/28,544완료/112,341판단, 지원 CPU/GPU·CG_DC 병행만 허용, lane 중복·응답/AVAILABLE 혼동·요청 누락0이다. 응답 ns는 엔진이 절대/경과 시간을 각각 정수화하는 1ns 이내 차이를 반영했다. 실행 소스51해시와 원동결 입력이 보존됐으며 owner lock은 없다. 오프라인 화면432행·필터48행·그림6개 로드 PASS, 화면을 직접 확인했다.

- [오프라인 대시보드](results/ie_priority_compare_02/index.html)
- [전체 결과 CSV](results/ie_priority_compare_02/evaluation.csv)·[EDD 대비 차이](results/ie_priority_compare_02/EDD_paired_differences.csv)·[일정 동일성](results/ie_priority_compare_02/schedule_identity.csv)
- [응답·기한 그림](results/ie_priority_compare_02/02_응답과_기한.png)·[에너지·AP 그림](results/ie_priority_compare_02/03_에너지와_AP.png)·[대표 실행 시간표](results/ie_priority_compare_02/05_실행_시간표.png)
- [사전 등록](results/ie_priority_compare_02/registration.json)·[전체 원장 감사](results/ie_priority_compare_02/final_artifact_verification.json)·[브라우저 검증](results/ie_priority_compare_02/browser_verification.json)

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_ie_priority_compare tools.test_d1_ie_priority_compare_study tools.test_d1_ie_dispatch -v
python -B -X utf8 -m tools.d1_ie_priority_compare_check --run output/ie_priority_compare_20261010_v1
python -B -X utf8 -m tools.d1_ie_priority_compare_report --run output/ie_priority_compare_20261010_v1 --output docs/results/ie_priority_compare_02
python -B -X utf8 tools/d1_ie_priority_compare_browser_check.py docs/results/ie_priority_compare_02/index.html 432 48
```

위 명령은 끝난 로컬 원본을 검사·시각화하며 새 환경을 시작하지 않는다. 본 실행은 동일 모듈 `d1_ie_priority_compare_study`의 `--phase register`, `gate`, `development`, `confirmation` 순으로 했다. 완료 ID/폴더는 덮어쓰지 않으며 새 폴더로 예산·시간을 초기화하는 재실행은 차단된다. Git에는 작은 코드·사전 설정·CSV·그림·문서만 포함하고 압축 원본·모델·개인 경로·체크포인트는 로컬에 보존한다. 다른 대화의 기기 측정은 독립 작업으로 진행 중이며 이번 작업의 기기0과 구분한다.

## 추가 세 전문가 회의와 단일 보완의 종료

사용자 후속 지시로 모바일·산업공학·RL AI가 상호 검토했다. [토론·반론·합의·수정 기록](results/ie_priority_compare_02/expert_meeting.md). 기회0인 탐지-head backfill은 철회했고, CPU 대기보다 GPU 즉시 실행의 예상 응답이 빠른 분류-head만 현재 도착 전체 큐의 응답 비악화 조건으로 허용하는 별도 후보를 구현했다.

개발24＋회귀4＝28환경에서 실제 전환1회, 실패·긴급 P95는 원 EDD와 같고 평균J＋0.000408/AP＋0.000679로 미채택이다. 마지막 후속 일정 earliest 수정 후 저장6,803판단을 전량 재생해 선택 동일·허용1상태의 예측 일치를 확인했고, 최종 native gate4도 원EDD exact PASS다. 전환 카운터의 잘못된1584도 원자료를 보존한 채1로 정정했다. [개발24 전량](results/ie_priority_compare_02/response_development.csv)·[수정 소스/검증](results/ie_priority_compare_02/response_verification.json).

합계 **480환경/새학습0/기기0**, 원상한480 소진·누적9749환경/1449학습이다. 전체30,144요청 완료, 원비교432행＋별도개발24행이다. 예산·시계 초기화0, 새 후보 독립확인0이며 원48조건을 확인자료로 재포장하지 않았다. 새학습·실측·기준정책 교체0이다. 희소한 응답/lane 경계 보완이 현재 비용 목표를 개선하지 못했다는 뜻이며 RL 일반의 실패는 아니다.

추가 실행은 `python -B -X utf8 -m tools.d1_ie_response_backfill_study --output output/ie_priority_compare_20261010_v1`, 최종 재생/회귀는 `python -B -X utf8 -m tools.d1_ie_response_backfill_verify --run output/ie_priority_compare_20261010_v1`였다. 완료된 소비 계약은 재호출로 초기화되지 않는다. 종료 후 재검사는 위 `d1_ie_priority_compare_check`와 `tools.test_d1_ie_response_backfill`을 사용한다.
