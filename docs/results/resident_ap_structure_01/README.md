# AP 상태별 가열·30초 잔열 분해 — 특정 조건만 개선

[한국어 결과/수식/악화/범위](../../RESIDENT_AP_STRUCTURE_RESULTS_20261009.md) · [최종 화면](run_v2/index.html) · [후보](run_v2/candidate.json) · [지원 API 조건](application_scope.json).

결과전PC구조등록/개발4LOSO/전체4최종fit/과거29전이진단이다. 모두이미열람한자료이므로독립확인아님. 새장구간MAE0.756→0.498°C,과거29는0.322→0.411°C·19악화,평균최고온도차도악화. 기본/RL/strict/experiment_ready=false유지·물리/기기/추론0.

run_v1의과거25차단은표기정규화결함,실측공백이아니다. 원결과를보존하고run_v2에서계수/개발평가를그대로재사용해수정전이를완료했다. 추가fit0. 현재답은run_v2이며대조중승자를새로고르지않았다.

## PC 재현

```powershell
python -B -m unittest tools.test_d1_resident_ap_structure -v

# 계수·개발 결과 재사용. 원본/기기 불필요, 새 출력 경로.
python -B -m tools.d1_resident_ap_structure --reuse-development docs/results/resident_ap_structure_01/run_v1 --output output/resident_ap_structure_reproduction

# 등록된 같은13fit을 처음부터 재현하려는 경우만; 새 탐색/상한 변경 아님.
python -B -m tools.d1_resident_ap_structure --output output/resident_ap_structure_full_reproduction
```

의존자료: `resident_identification_run_01/recorded_v3/inputs.json.gz`의4개개발, `model_refinement_01/inputs.json.gz`·`history_model_refinement_01/inputs.json.gz`의중복제외29개, `online_policy_study_01/overnight_sustained_run01/model.json`. 모두기존공유상대경로이며개인PC의대용량원본을요구하지않는다. 원모형SHA/입력SHA는registration·receipt에,과거파일의시작HEAD와동일byte는archive_source_snapshot에기록했다.

`forecast_candidate(case, original, candidate, context)`는candidate.json/application_scope.json을사용하는명시opt-in 계산API다. 장구간DEV_A/B 이외는null이며저수준predict의외삽계산가능성과구분한다. B도착부터의일정/응답/정책우열을검증한것이아니다. 부하전R/H만사용하며미래관측AP/전력은target이다. 에너지예측은기존과exact 동일.

API는자료메타데이터/입력검사이며기기실행허가나현재환경gate를대체하지않는다. 실제lane점유와정해진블록/완료30초상한을검사하고병행→단독label 변경은같은lane의연속점유로취급한다.
