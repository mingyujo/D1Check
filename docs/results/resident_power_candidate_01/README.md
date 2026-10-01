# 유휴 기준 가산 후보1 — 사후 평가, 채택하지 않음

[판정 보고서](../../RESIDENT_POWER_CANDIDATE_PC_20261001.md). 기존4세션의 부하 전 전력으로 상태 전력 전체를 같은 W만큼 옮긴 후보 하나다. 식·창은 계산 전에 고정했지만 결과를 이미 본 자료이므로 독립 확인은0이다. 2개선/2악화, 기본/strict/정책 비용 경로에는 연결하지 않았다.

- `contract.json`: 후보1개·식·정보 경계·결측·해석 계약. 실행 계획이 아니다.
- `inputs.json`: 기존 raw에서 추출한 상대시각 power 표본·resident/active 수·실제 상태·원래 W. 원문/모형 SHA 포함, device/session 식별자 제외. `relative_ns`는 공통창 시작 기준이며 PC 적분 때 고정 가상 origin을 더한다.
- `readout/scores.csv`: 첫 dispatch→120초, 부하 envelope, 이후 유휴의 동일 구간 관측/원래식/후보 J. 후보 전체120초 값은 제공하지 않는다.
- `readout/energy_paths.csv`, `comparison.png`/`comparison.svg`: 정보 시점 이후 누적 잔차. 결측은0으로 채우지 않는다.
- `readout/summary.json`, `verification.json`: 사후 판정·source/contract/code hash·검증. AP·동결 모델·strict 변경 없음.

저장소 안의 작은 입력만으로 재현할 수 있다. 기존 출력과 다른 새 폴더를 사용한다.

```powershell
python -X utf8 -B -m tools.d1_preload_power_candidate evaluate --bundle docs/results/resident_power_candidate_01/inputs.json --contract docs/results/resident_power_candidate_01/contract.json --output '<새 PC 출력 폴더>'
python -X utf8 -B -m unittest tools.test_d1_preload_power_candidate -v
```

원문 재추출에는 외부4세션의 FINAL_RECEIPT·validated·common_boundary·requests·progress·manifest·start_ap.accepted·before_session_battery·thermal과 원래 development_freeze가 필요하다. 원문 해시는 `inputs.json/source_hashes`, 정확한 run 이름은 `tools/d1_preload_power_candidate.py/SPECS`다. 재추출 명령은 `export --source-root '<외부 자료 루트>' --frozen '<원래 development_freeze.json>' --reference docs/results/energy_ap_cgdc_transfer_01/run01/idle_comparison/summary.json --output '<새 입력.json>'`이다. 원본이 없어도 위 evaluate는 가능하다.

다음은 무부하 대조가 포함된 최소 원인 분리 수집 설계의 확정이다. 아직 실행 계획/예산·소비 claim은 없고 이번 PC 작업의 기기 명령은0이다.
