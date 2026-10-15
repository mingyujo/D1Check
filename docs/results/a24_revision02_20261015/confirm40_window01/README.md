# 새 독립 확인40의 첫 방문 — 혼합4군 회수

**등록된 혼합4군·512요청을 전량 완료·출력 대조 PASS로 회수하고 16:15:55경 종료했다. 새 확인은 실행4/40회,36회 미실시다. 직렬 기준 군의 AP 관측창이 사전 간격 기준을 넘겨 열 효과 비교는 미판정이며, 에너지 J도 미판정이다.** 전체 독립 확인이 완료됐다는 뜻이 아니다.

[오프라인 화면](index.html) · [서비스·AP 적격성](sessions.csv) · [전체40 상태](attempts.csv) · [모든 예정 요청](requests.csv) · [소비 원장](GLOBAL_CONSUMPTION_LEDGER.json) · [시작 상태](run_context.csv) · [검증](VERIFICATION.json).

| 실행 순서 | 긴급 분류 기한 내 | 일반 탐지 기한 내 | 긴급 P95 | AP 창 적격 |
| --- | ---: | ---: | ---: | --- |
| 납기순 EDD | 25/96 | 5/32 | 9,310.465ms | 적격 |
| 200ms 대기 | 9/96 | 7/32 | 13,973.366ms | 적격 |
| 분류 GPU·탐지 CPU 병행 | 96/96 | 32/32 | 1,421.115ms | 적격 |
| 직렬 기준 | 13/96 | 10/32 | 11,049.071ms | **미적격:12.34초 공백** |

각 군128건 모두 서비스 창 안에 끝났고 요청 실패·미완료0, 출력512건 대조PASS다. 기한을 넘긴 요청을 실패·미완료0이라는 이유로 성공 처리하지 않는다. 일반 응답 P95도 CSV에 있다. 입력은 같은 승인 이미지 반복이며 과업 정확도나 다양한 이미지의 일반화를 검증한 실험이 아니다. 새 모델·RL·NPU 실행은 없다.

## 사전 고정 조건과 실행 경계

[원래40 동결](../../../team/a24-measurement-revision02-20261015/confirm40_after_dev8_20261015/README.md)의5블록×8군·5,720요청을 유지했다. 오늘은 첫M128 네 ID만 등록한 별도 방문으로 실행했다. 같은 bank·seed2026101551·C2.2초/D5초·공통4 runtime×2 warmup·응답/실제worker반환 경계·APK·179핵심 소스를 유지했다. D_GPU는 준비용이며 본요청은 탐지CPU만 허용한다.

첫 EDD 준비 후 최초 유효 창에서 기준27.3℃를 MAIN 전에 봉인했다. 후속군은 같은 기준과±0.5℃/안정60초/기울기0.1℃/분/최대600초를 적용했다. MAIN 직전 실제 읽기값은 EDD27.3/대기27.6/병행27.6/직렬27.3℃로 완전히 같지는 않다. 순서는 결과 전에 정했고 뒤36군을 유리한 조건으로 바꾸거나 오늘 추가하지 않았다.

실제 APP 시작은15:42:45/15:50:42/16:01:11/16:09:55 KST다. MAIN은15:44:38/15:53:38/16:03:31/16:12:18이다. 실제 실행 시작 HEAD는 `8ce0a70`이며 원179파일·coordinator 바이트를 종료 후에도 검증했다. manifest의 `source_commit=5190aff`는 준비 기준 커밋이고 실제 host 실행 HEAD와 구분한다. 같은21분 APP/5분 MAIN 여유, 기기16:33:25/전체16:38:25 상한 안에서 종료했다. 각 군의 DRAINED·journal close·실제 lane 반환·빈 소유 프로세스 종료를 확인했고 실행기 exit0·WINDOW_STOPPED를 보존했다.

## AP 공백은 그대로 미판정 처리한다

직렬 기준의 AP 읽기 중간시각은 origin+32.015827598초 다음이44.355827598초로 **12.34초** 간격이다. AP 창35~180초의 시작을 걸치는 공백이며 원래 최대10초를 넘겼다. 기존 분석기는 AP 평균을 null/`GAP_OR_DUPLICATE_TIMESTAMP`로 반환했다. 표본 최대값29.0℃는 관측된 하한일 뿐 완전한 창의 최고값이나 정책 비교용 값이 아니다.

원자료·사전 계약·기존 핵심 분석기는 바꾸지 않았다. 별도 [공개본 적격성 처리](PUBLICATION_CONTEXT.json)는 원래 engine 출력의 SHA를 보존하고 미적격 군이 들어간 AP 차이·구간·그림의 비교값을 비운다. 원래 관측 최고·미적격 상태·검사 전 기술적 차이는 CSV의 별도 필드에 남긴다. 기존 engine export는 로컬 원본 폴더에 그대로 있다. AP 간격 기준을 완화하거나 공백을 임의로 채우지 않았다.

적격3군의 AP 평균/관측최고는 EDD28.2226/29.4, 대기28.3970/29.4, 병행28.1660/29.7℃다. 이를 미적격 직렬 기준과 비교해 열 감소·증가를 확정하지 않는다. 온도는 HAL AP이며 실제 표면온도·물리적 센서 갱신 나이·정확도는 미검증이다. AP 한도 초과 시간도 근거 없는 한계를 만들어 계산하지 않는다.

## 현재 해석과 남은36회

이 조건에서는 병행 허용의 서비스 이점이 DEV에 이어 다시 관측됐다. 통로 동시 점유14.737초/앱 inference 호출 겹침2.646초이며 하드웨어 내부 연산 동시 시간을 직접 확인한 값은 아니다. EDD는 직렬보다 긴급 기한 준수는 높았지만 일반은 낮았다. 의도 대기는 실제16회·3.243초로 서비스가 악화됐다. 열·에너지 우위를 확인한 후보는 없다.

M128 비교당 독립 블록은1개라 서비스 신뢰구간을 만들지 않았다. 이 블록의 직렬 AP 부적격으로 M128 열 비교의 적격 쌍은0이다. 나머지 L64/C252·블록2~5는 미실시이며0성능으로 평균내지 않는다. 전체 예정 요청5,720 중 미실시36군의5,208요청은 진행 원장에 남고, 이번 실행512요청의 미완료0과 구분한다.

총상한81 중 기존33+DEV8+이번4=**45소비/36잔여**다. 실패·부적격 결과의 재실행·대체0, 기존 확인 자료 합산0이다. 다음은 등록 순서의 R02CONFIRM01 L64 PAIR_G→BASE, C252 CPU→GPU다. 첫 방문 명령/root는 재사용하지 않는다. 다음 방문의 시간창·전역 소비 SHA·미시도 ID·참조 기준을 결합한 뒤 남은36만 실행해야 한다. AP 부적격1군은 이번 예산에서 자동 재수집하지 않는다.

[에너지 조사](../energy_readout_audit/README.md)와 [공개 커널 검토](../energy_readout_audit/PUBLIC_KERNEL_REVIEW.md)는 별도다. 현재 설치 커널6.12와 참고5.10의 차이, vendor 접근 제한을 남겼고 임의×1000·×1210 교정은 없다. 확인 종료 후 읽기 전용 진단12명령을 추가했지만 추가APP·추론·START·claim·세션 소비0이다.

## 원물과 PC 재현

[실제 원물 ZIP](device_raw.zip)에4세션의 events·요청·경계·출력·센서·close 등576파일을 바이트 그대로 보존했다. [멤버·ZIP SHA](device_raw.sha256.json)를 제공한다. 모델·APK·승인 이미지·개인 target manifest·기기 일련번호는 넣지 않았다. 실제 원물은 로컬 `A24R02C1`, 메타는 `output/a24_confirmation40_frozen_window01_20261015`다.

```powershell
$env:PYTHONPATH='tools'
python -B -m unittest test_d1_a24_partial_confirm_publication test_d1_a24_energy_unit_forensics test_d1_a24_energy_readout_audit test_d1_a24_suite_report_context test_d1_a24_confirm_registered_window
# 보존된 로컬 private job/원물을 사용하며 모두 새 출력 폴더를 지정한다.
python -B tools/d1_a24_measurement_report.py output/a24_confirmation40_frozen_window01_20261015/job.json output/a24_confirmation40_frozen_window01_20261015/ANALYSIS_ENGINE_ADAPTER.json output/confirm4_engine_new --stage CONFIRM
python -B tools/d1_a24_suite_report_context.py output/a24_confirmation40_frozen_window01_20261015/job.json output/confirm4_engine_new
python -B tools/d1_a24_partial_confirm_publication.py output/confirm4_engine_new output/confirm4_public_new
```

순수 검사17개·정확40설정/5,720요청의 실제 앱parser PC검사1개 PASS다. 실기기 회수·출력 PASS, AP 관측 적격3/4, 에너지/실제표면온도 미검증을 별도로 기록했다. 사용자 WIP·다른 worktree·데스크톱 학습·S26은 보존하며 `experiment_ready=false`다.
