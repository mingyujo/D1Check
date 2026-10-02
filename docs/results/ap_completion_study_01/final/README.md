# 등록된 확인6과 조건부 AP 시뮬레이터

개발6(과거 적격 C1＋신규5)에서 사전 규칙으로 M1 미채택·M0 동결 후 확인2＋사용자 휴지 뒤 새4를 확보했다. 원래01/02 소비/중지/실패는 보존한다. [보고서](../../../AP_MODEL_COMPLETION_STUDY_20261002.md), [화면](index.html), [검증](verification.json).

## 공유 파일만 사용한 PC 재생

```powershell
python -B -m tools.d1_simulator ap-conditioned --case-id v2_confirmation_0_C --output output/ap_C_fresh
python -B -m tools.d1_simulator ap-conditioned --case-id v3_confirmation_2_SPLIT_DELAY30 --output output/ap_split_fresh
python -B -m unittest tools.test_d1_conditioned_ap_simulator -v
```

Python/NumPy와 이 저장소의 작은 `ap_cases.json`, `model.json`, `ap_resources.json`만 사용한다. ADB/설치/외부 원자료가 필요 없다. 실제 lane 일정＋common+35초 전 AP에 조건부이며 미래 AP·전류는 예측 입력에서 제외한다. 초기 E/H 추정이 허용된 관측 입력임을 숨기지 않는다. 등록되지 않은 입력/해시 변경/새 초기 AP는 차단한다. 새로운 도착부터의 정책 예측은 아니다.

`confirmation_scores.csv`는 AP 대상 시각·표본·MAE/최대/최고, 전체120초 관측J와 원래W식 외삽 차이를 제공한다. `ap_paths.csv`, `energy_paths.csv`, `directions.csv`, `phase_scores.csv`로 잔차/냉각 방향/구간을 재현한다. AP 변화량에 같은 anchor를 양쪽에서 빼도 잔차는 같으며 임의 평행 이동은 없다. 에너지1초 누적720점은 원래 적분 끝점과 일치한다. 시뮬레이터 AP route의 energy_j/정책 순위는 null이다. 전류raw=mA 조건부·절대정확도 미인증, 시작AP28.8–30.5°C는 기존 상태 모형 범위밖이다.

원본 재판독은 외부 두 study_plan/동결파일 및 세션별 manifest·validated·requests·progress·common_boundary·thermal이 필요하다. 외부 `ap_completion_remaining_readout_v3/inventory.json`이 원본 inventory다. 신규 root receipt는 `ap_completion_study_run_v3/FINAL_RECEIPT.json`, 과거2는 `ap_completion_study_run_v2/confirmation/FINAL_RECEIPT.json`에 있다. 재판독 CLI는 통합 보고서를 따른다. 이전 실행은 source109을 `ap_completion_pause_evidence_v2/execution_source`에 별도 보존했다.

현재 M0는 새 수식이 아니라 기존 고정 후보이며 M1을 확인 자료로 다시 맞추지 않았다. 조건당2세션·다른 block의 초기/주변/이력 차이를 변동성 보장으로 표현하지 않는다. 18방향 창 중2개 냉각 식별/재현,16개 unresolved이며 후자는 PASS가 아니다. 정확도 기준·정책 차이 판정은 미완료, strict/default/experiment_ready=false 유지. 추가 실측/후보/기기 계획을 자동 생성하지 않는다.

등록한 6파일은 `.gitattributes`의 정확한 줄바꿈 규칙으로 byte 해시를 보존한다. 별도 임시 경로에서 실제 `git checkout-index`로 6파일을 내보내 모두 등록 해시와 일치함을 확인했다. 원래 과학 코드·동결 파일의 byte는 바꾸지 않았다.
