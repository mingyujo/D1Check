# AP 두 이력 확인02 · 실측 결과

[한국어 보고서](../../../AP_BUNDLE_CONFIRM_RUN02_20261002.md) · [화면](index.html) · [점수](metrics.csv) · [고정 방향](fixed_directions.csv) · [작은 요약](summary.json) · [검증](verification.json).

한 묶음→두 반묶음의 변경 없는 후보 확인이며, 두 세션 정상 완료/회수했다. 각 세션24요청/8warmup/4runtime. APK push/설치/재시도0. 전력/열 계수 재적합0, 부하 후 AP는 평가 target이며 예측 입력이 아니다. 실제 시작 AP·실제 lane 일정·부하 전 유효 AP 기준을 사용한 조건부 재구성으로, 미래 일정 예측/온라인 B2 검증은 아니다. 각 이력의 독립 세션 수1과 표본 수를 구분한다.

120초 J는 정확한 공통창0–120초, raw=mA 조건부/절대 정확도 미인증. AP 오차는 보고서의 실제 표본 범위/미보간 구간을 따른다. 후보 MAE0.450/0.405°C이나 후기 재상승 미재현; 정확도 PASS/strict/정책 순위/experiment_ready 승격 없음.

## 재현

```powershell
python -X utf8 -B -m tools.d1_ap_bundle_readout --plan '<energy_ap_bundle_confirm_plan_v2/collection_plan.json>' --output '<새 PC 판독 폴더>'
```

동결 계획·분석 계약·source_code 해시와 원본 의존은 결과 보고서/검증 JSON에 연결했다. 현재 plan_v2는 소비·완료 상태이며 Run을 다시 호출하지 않는다. 로컬 외부 원본 `energy_ap_bundle_confirm_run_v2/`의 FINAL_RECEIPT, 두 세션 artifacts/{manifest,requests,progress,common_boundary,start_ap.accepted,cleanup,summary,warmup}, thermal.jsonl, validated/recovery/host_cleanup가 필요하다. 후보 freeze와 원래 development freeze도 별도 필요하다. 원본/설치본 APK/모델/키/기기 식별정보는 Git 공유물에 없다.

각 세션 폴더의 ap_paths/energy_path/phase_energy_residuals/actual_states CSV·점수·PNG는 위 실제 CLI 출력과 byte 동일하다. 공유 SVG는 Git 검사를 위해 줄 끝 공백만 제거했고 XML 속성/도형 의미 불변을 확인했다. 원본 SVG는 외부 CLI 출력에 보존했다. energy_path 끝120초는 기존 적분의 유효 bracket과 정확한 상태 시간×동결 W를 사용했고 원래 센서 시각만 있는 CSV도 frozen_reader_energy_path에 보존했다. actual_request_timing CSV는 회수 requests.json의 각 monotonic 시각−common_start_ns를 초로 변환한 직접 기록이며 ordinal/task/backend/terminal 분모24를 유지했다. 공유 summary는 개인 식별/원문 thermal을 제외한 별도 요약이다. 누락/계산 불가 값은 null 또는 빈 칸이며0으로 채우지 않는다.

pre_execution_verification은 실행 전 미소비/PC 상태의 당시 기록이며 수정하지 않았다. 실제 완료는 summary와verification에 따로 보존했다.
