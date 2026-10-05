# AP 종료형 연구 — 개발 중 조회 timeout으로 종료

2026-10-02 · [화면](index.html) · [설계·실행·최종 보고서](../../AP_MODEL_COMPLETION_STUDY_20261002.md)

**stopped_no_resume**. 사용자 승인으로 PC 구현/동결/Run1회 수행. 개발 C1만 적격 완료했고 L35 준비 중 시각정렬용 `/proc/uptime` 조회가2초timeout했다. 개발 나머지4·확인6 미시도,새적합/선택/동결/확인0. AP 모형 예측 실패나 과학적 식별 실패라고 판정하지 않는다. 계획을 다시 실행하지 않는다.

- 실제 기록: 시도2/완료1,warmup16/runtime8,본 요청 시작·반환0. 첫C 실제본0. 중단 세션은 원문73행 prefix/terminal미회수이므로 이후 미기록 범위를0으로 단정하지 않으며 상한24요청 내 미확인으로 남긴다. 공식창/시작 AP 승인도 미도달.
- staging2/14파일·설치본pull1·APKpush/설치0·ADB963·전체375.400초(사전상한12세션/288추론/38,800ADB/14,100초). 추가/재시도0. 입력파일push14와 APKpush0을 구분한다.
- C 앱cleanup completed. 중단 L35 앱cleanup미확인/manifest+progress부분회수·hostforce-stop1회,최종계획내ps 대상부재. host 원래stack/root+blockreceipt/checkpoint/시작식별 보존,tool exit1,종료 후 host PID부재 확인. 추가기기조회0.

## 부분C의 계산 범위

공통120초 관측132.482716J/기존W식147.052011J/차이+14.569295J. raw=mA 조건부·절대정확도미인증. 기존M0의AP는common35.344549–179.784549초/56표본에서MAE0.067274°C/최대0.385750°C/최고부호오차−0.243259°C. 부하 전63.46초/26표본만 초기화 입력이다. 단일 무부하/이미 고정된 후보의 부분 연구 기술평가이며 새후보확인·일반 정확도/정책PASS가 아니다. 초기AP29.7°C는원래개발범위밖이다.

[sessions.csv](sessions.csv)는 예정12개 분모와 미시도/부적격을 보존한다. 미지원/없는 값은 빈칸(null)이다. [AP곡선](control_ap.svg)은 완주한C1개만 그리며, 부하 또는 확인6개 그림으로 해석하지 않는다. [기술 판독](development_0_C_technical_readout.json)의 고정 방향 창은0을 포함하는 반올림 민감도에서 모두 방향 미식별이다.

## PC/기기 검증 구분

- 실제root→공용6세션 진입·개발/확인 freeze 경계와 합성계수/미식별/미래관측 입력 금지7검사 PASS. 실제PSCheck와 ADB 차단Check 기기0,기존원문6fixture M0 전파차0°C/새적합0.
- 추가 판독3검사 PASS: 명령 목적/timeout제한관측·중첩/목표0·빈CSV·결측null. 처음 새 판독의 빈명령CSV 결함을 고쳤으며 원래 실행timeout과 무관하다. 실제판독CLI와 공유수치/원본inventory 일치 확인. 기존모형/후보/계약SHA불변.
- uptime191중 정상190(중앙0.091480초/P990.209039초)/timeout1,listing512/thermal97. [명령용도·지연](development_command_groups.csv). 시간 중첩0,6nonzero는새경로test-e 부재확인. 뒤회수/cleanup성공으로연결이계속끊겼다고확정할수없다. 내부원인미확정/timeout이전고정조건유지.
- 가짜기기검사·원문재생·실제현재기기결과를구분한다. Android/APK변경0,새모형확인0,strict/default/experiment_ready=false 보존.

## 재현과 외부 의존

원본 `D1Check_Arrival_Extension/ap_completion_study_run_v1/FINAL_RECEIPT.json`과 `development` 전체,동결계획 `ap_completion_study_plan_v1`/입력/기존freeze/APK receipt는 외부에 있다. PC판독 `ap_completion_study_readout_v2/inventory.json`이4,960파일/110,483,976바이트의상대경로·hash를보존한다. 공유본의표/곡선은개인절대경로없이볼수있으며 원본 재분석에는 이 의존 파일들이 필요하다. APK·모델·개인식별·큰원본은공유하지않는다.

```powershell
python -X utf8 -B -m unittest tools.test_d1_ap_completion_study tools.test_d1_ap_completion_results -v
python -X utf8 -B -m tools.d1_ap_completion_results --plan '<archive>/ap_completion_study_plan_v1/study_plan.json' --output '<새 PC 판독 폴더>'
python -X utf8 -B docs/results/ap_completion_study_01/plot_control.py --output '<새 그림 폴더>'
```

계획 SHA `09b70105bf9f6f1d553c1d6abd12023d315d5b1c027c48486d84a66b47b14b86`; [소스·보존·검증 요약](verification.json). 데이터가 없으면 candidate계수를 만들지않는다. 다음PC경계는필수시각괄호/환경관측을유지한단일원격조회검증이며,새실측계획을자동만들지않는다.
