# 데스크톱 GEN002 참고 자료 인수 검산

2026-10-15. **기존 동결 소스·프로필의 인수는 완료했다. 이번 A24 8군의 수치 예측·최종 분석 계약·최종 PPO 선정 자료는 아직 없다.** 소스 읽기와 SHA 검산만 수행했으며 이 참고 코드의 import·시뮬레이션·학습·실측을 실행하지 않았다.

## 인수 버전과 바이트 검증

원격 전달 commit은 [`ec8a1424f9326bae80486e9182fc81e88ae318a1`](https://github.com/mingyujo/D1Check/tree/ec8a1424f9326bae80486e9182fc81e88ae318a1/docs/team/a24-laptop-measurements-20261014/desktop-reference)이다. [desktop-reference](desktop-reference/README.md) 아래 **73파일·4,049,289바이트**를 해당 Git blob에서 새 폴더에 write-once로 복사했다. 이미 복사한 파일을 덮어쓰지 않았다.

[FILES_SHA256.json](desktop-reference/FILES_SHA256.json)의 72개 항목과 자기 파일 1개의 exact file set을 확인했다. 목록에 등록된 72개 파일의 바이트 수·SHA-256·Git blob SHA-1 모두 일치하며, 자기 파일도 전달 commit의 원 blob과 일치한다. [SOURCE_PROVENANCE.json](desktop-reference/SOURCE_PROVENANCE.json)의 **소스59개·물리 프로필8개**를 [GEN002.json](desktop-reference/GEN002.json)의 원 등록 SHA와 전수 대조했다. 차이 0이다.

GEN002 자체 SHA-256은 `b3156ad8f300e85064f3cfdeb02b3c4a414c0b895e2d88465d6a6f1779e95327`이다. 당시 원 checkout HEAD만으로 미커밋 소스를 특정할 수 없으므로 GEN002와 개별 파일 SHA 및 이번 전달 commit을 함께 사용한다. 기존 노트북 worktree의 브랜치/HEAD를 이 commit으로 변경하거나 데스크톱 실행을 재시작하지 않았다.

## 도착한 자료와 없는 자료

| 항목 | 인수 판정 |
| --- | --- |
| GEN002 등록 소스59개, A24/S26 프로필 각4개 | 바이트 검산 완료, 기존 연구 참고 자료 |
| 이번 L64/C252/M128 8군의 strict FIFO/EDD·PAIR·고정 WAIT200 예측 adapter | 미작성/미선정 |
| 8군 J180·평균AP·납기·대응 정책차 수치 예측과 확인 전 봉인 | 미작성 |
| 새 실측의 sampling·clock alignment·적분법·max gap·오차 허용치·정확한 구간 분석까지 동결된 실행 계약 | 미동결 |
| 새 A24 실측용 최종 선정 PPO checkpoint | 미선정, 이 폴더에 checkpoint 바이트 없음 |
| 새 노트북 APK·승인 원물·tensor 결합 | 노트북의 별도 PC 준비 산출물에서 완료. 전달 당시 데스크톱 상태를 적은 원 AVAILABILITY는 수정하지 않음 |
| 새 실제 A24 초기 상태·센서·GPU·lane·품질 확인 | `DEVICE_UNVERIFIED` |

자료 부재와 접근 실패를 혼동하지 않는다. [AVAILABILITY](desktop-reference/AVAILABILITY.json)와 [ANALYSIS_CONTRACT_STATUS](desktop-reference/ANALYSIS_CONTRACT_STATUS.json)는 수치 예측/최종 계약이 없음을 명시한다. 과거 결과나 단순 평균 산술로 빈 예측표를 채우지 않았다. 기존 GEN002 `analysis.py`는 원 시뮬레이션 분석이며 이번 실측 최종 분석으로 표시하지 않는다.

## 기존 명목 시간과 새 참고 프로필의 관계

현재 64세션 계획 생성에 사용한 원 명목 자료 SHA는 `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`다. 새 A24 프로필4개도 이 원 서비스 anchor의 provenance를 보존한다. 입력 recipe의 C_CPU165.216ms/C_GPU304.829ms/D_CPU621.737ms는 해당 5구간 평균 합을 마이크로초 단위로 반올림한 명목값이다. 새 자료를 받았다는 이유로 이 값·M128 간격·기한·요청 수를 다시 선택하지 않았다.

| GEN002 A24 프로필 | SHA-256 | 해석 |
| --- | --- | --- |
| M0_frozen35 | `e886b848a46231f0aa9ca988c4ac38449f825622c92703455d47c4a9b15731f3` | 기존 관측 시간/전력 사전 자료를 사용한 연구 기준 |
| M1_coupled | `ee36899cc7c5ea17a689bbd746e8906866e846ceb0e68685d8faa17b20009df3` | 결합 열·일정 모형, 가정 경계 유지 |
| thermal_strong_Wscaled | `7dfad5abe6bc8982c5e6006a475c5c8291049be2dedfe287d109eccd23ab4d99` | 강한 열과 전력 변화의 가정 민감도 |
| thermal_strong_Wfixed | `952145cefbb5db540ff2b373894eddedb25f06a110b7b2cc8cf2139ce0cf53f8` | 강한 열과 고정 전력의 가정 민감도 |

네 프로필 모두 `evidence=hypothesis_only`, `hardware_validated=false`, `strict_eligible=false`, `experiment_ready=false`다. 기존 관측 자료가 계수의 근거라는 것과 새 A24 정책차가 검증됐다는 것을 구분한다. `measured35.data_role=previously seen development`, `independent_confirmation=false`도 유지된다. 유리한 프로필 하나를 사후 선택하지 않는다.

A24 서비스 anchor는 분류 CPU/GPU·탐지 CPU 세 조합만 갖고 최대 병행2다. 원 비용 anchor에 과거 탐지 GPU 항목이 남아 있다는 이유로 탐지 GPU를 새 요청 후보에 추가하지 않는다. S26/NPU 관련 소스는 원 인계 바이트 보존이며 이번 A24 구현·측정·학습 확장이 아니다.

새 실측 초기 AP gate와 연결된 초기 상태는 없다. 원 프로필은 과거 AP 이력/경계와 합성 갱신을 사용하며 reference AP는 실측 주변 공기 온도가 아니다. SKIN placeholder와 합성 온도2초/전력0.9초 관측을 새 폰의 센서 지원·cache/noise·갱신 검증으로 전용하지 않는다. 모델·이미지·tensor 바이트 및 기기 품질 결과도 이 참고 폴더에 없으므로 기존 승인 원물/출력 계약의 별도 결합과 새 기기 검증이 계속 필요하다.

## 그대로 새 실측 예측으로 사용할 수 없는 경계

원 `model/code/plant.py`를 읽어 WAIT가 새 도착·상태 사건에 종료될 수 있음을 확인했다. 이번 WAIT200은 사건과 무관하게 선택한 고정 timer dose를 유지하므로 동일 정책이 아니다. 원 `cases.py`에는 task 무작위 순서·jitter가 있으며 이번 대응 bank의 jitter0·고정 구성과 다르다.

원 경로의 persist 완료와 이번 일반 응답의 readback 성공, 미완료 때 원 180초 비용/열 null 처리와 새 실측의 관측 소비 보존도 구분해야 한다. strict 순서·전역직렬·PAIR·고정 WAIT·새 응답/AVAILABLE·초기 상태를 연결한 별도 adapter와 분석을 확인 자료 전에 등록/동결해야 한다. 이번 인수에서는 그 adapter나 새 예측 실행을 자동 추가하지 않았다.

## PLAN 줄바꿈 차이와 미소비 계획 보존

원 문서 commit `38d34c62111d8ea2b71b7a808db5bdf172e56b1d`의 PLAN SHA는 `29bbbdc882d273ddec769f748f86907866bb186423643d6f2546bbac55720225`다. 최초 Windows checkout 바이트 SHA `49c1b77ee3f10641545cd54b4f7d5834ed0bcd95665168c55a665b41c561d624`와의 차이는 LF14,981바이트가 CRLF97개/15,078바이트로 바뀐 것뿐이었다. 원 receipt와 CRLF 복사본을 ignored output에 보존하고 원 Git blob의 LF 바이트로 복원해 현재 PLAN SHA는 원 `29bbbdc8…20225`와 일치한다. `.gitattributes`에 정확 바이트 보존을 지정했다. **내용·계획 의미는 변경하지 않았다.**

원 등록 `plan_v3/plan.json` SHA `82d5108db8d44fc6785cbdc99f71baee01361e21abdd4c59df9544826cb93855`는 유지했다. I4→F4→DEV16→동결→CONFIRM40, 64세션/26bank, 요청 수·도착·납기·arm·미소비 상태를 변경하지 않았다.

## 데스크톱 중지·복구 전달 경계

사용자가 전달한 **EP813 자료 보존, EP814 복구 불가, 자동 retry/restart 금지**를 인계 조건으로 기록한다. 이 참고 폴더에는 실제 checkpoint/가변 원장이 없으므로 노트북이 EP813/814의 현재 데스크톱 상태를 독립 검증하거나 복구했다고 주장하지 않는다. 데스크톱 학습·원장·시뮬레이션을 건드리지 않았다.

검산 receipt는 `output/a24_laptop_prep_20261014/desktop_reference_receipt.json`이다. 이번 자료 인수의 코드 import 실행0·모형/시뮬레이션0·학습/optimizer0·새 추론0·실제 기기 명령0·계측0·START/claim0·측정 세션 소비0이다. **참고 자료 인수 완료는 실측 시작 또는 CONFIRM 동결 완료가 아니다.**
