# Pre 전력의 AP 초기화 입력: 방향 오류 미해결·미채택

[보고서](../../AP_POWER_INITIALIZATION_RESULTS_20261010.md) / [화면](index.html) / [사전계약](analysis_contract.json) / [산술계약](readout_contract.json) / [검증](verification.json).

기존H 상태에중심화pre 전력을넣는후보1개/전역gain1개를개발6/반대block제외2＋최종1로추정했다. 확인6의35..120 MAE0.21160→0.21125°C는극소감소,전체관측35..180 0.16630→0.16656악화·회복30 가열방향오류유지로미채택이다. 기본/RL/strict/원계수/experiment_ready=false·기기0.

- `run_v1/pre_inputs.json`: 등록recovery AP와그시각전력event의ZOH driver만있다. 실제미래AP/전력값은없다. sampler gap/age≤2.5/조회hi<35,APgap≤10. 원J적분규칙은변경0이다.
- `run_v1/candidate_{30,180,final}.json`: global3fit,지역R/H nuisance와κ 분리,반올림민감도는신뢰구간/센서정확도아니다.
- `run_v1/AP_errors.csv`, `AP_paths.csv`, `initial_states.csv`:12전량·같은anchor/계수·부분관측끝·최대/최고/방향·악화포함.
- `run_v1/energy_link_*.csv`: 이전미채택전력관계식을재fit하지않은연결진단. 원전력모형 개선이나정책순위의결과가아니다.
- `readout_v1/C0_direction_gain.csv`, `direction_training_loss.csv`:4C0의예측방향경계와가상개발잔차. 큰gain을후보/forecast에적용0·추가fit0.
- `conditioning_availability.json`:기존96 conditioning/48 AP의새입력가능성 확인,한sourcecase의read-only표본·시간·hash. 새측정/초기상태해결을뜻하지않는다.
- `figures/*.png/svg`:전량오차·남은가열방향·gain식별·미채택전력관계의연결. 새 실측·물리원인·정확도PASS 없음.

```powershell
python -B -m unittest tools.test_d1_ap_power_initialization -v
# 아래는새출력 경로만:global fit/기기0
python -B docs/results/ap_power_initialization_01/run_example.py --opt-in --output output/ap_power_initialization_example.json
python -B docs/results/ap_power_initialization_01/readout.py --output output/ap_power_initialization_readout
python -B docs/results/ap_power_initialization_01/profile_loss.py --output output/ap_power_direction_training_loss.csv
python -B docs/results/ap_power_initialization_01/plot_results.py --output output/ap_power_initialization_figures
```

예제는pre-only 지역초기화1/AP재생1이며계수fit은없다. actual lane 일정이 주어진조건부cost이고예정도착부터의일정/응답생성이아니다. AP query시각과전력driver event는Android BOOTTIME상대축,consumer 실시간가용성은구현하지않았다.

실제분석명령:

```powershell
python -B -m tools.d1_ap_power_initialization --action prepare --output docs/results/ap_power_initialization_01/run_v1
python -B -m tools.d1_ap_power_initialization --action run --output docs/results/ap_power_initialization_01/run_v1
python -B docs/results/ap_power_initialization_01/readout.py --output docs/results/ap_power_initialization_01/readout_v1
python -B docs/results/ap_power_initialization_01/profile_loss.py --output docs/results/ap_power_initialization_01/readout_v1/direction_training_loss.csv
```

run_v1은소비돼차단된다. 의도적인원본재현에는별도새출력과공유repository 의존파일이필요하다. 기존결과/예제를우선하고끝난fit을불필요하게다시하지않는다. `registration.json` source/input hashes와`fit_receipt.json`3candidate hashes를검증한다.

새원자료조회없이공유history 입력·`preboundary_evidence_01/run_v1/expanded_pre.json`,기존 AP/모형/전력proxy 및`ap_conditioned_power_01/run_v1`관계계수를재사용한다. conditioning availability만외부원본3파일을read-only확인했다. APK/모델binary/키/대용량원본/기기식별정보는공유0이다. 절대J/센서정확도미인증·사후평가·기기계수비혼합·no default/RL/strict replacement를유지한다.
