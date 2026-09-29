# plan_v6 단일세션 공유 판독

[결과와 해석 경계](../../../ARRIVAL_RECORDED_B2_AP_OBSERVE_RUN01_20260929.md) · [통합 화면](../../arrival_policy_screen_01/dashboard.html)

`summary.json`·`timing.csv`·`states.csv`·`energy_path.csv`·`ap_path.csv`는 외부 원본 한 세션에서 동결 분석기로 만든 작은 파생물이다. SVG 네 개는 그 CSV의 읽기 전용 시각화다. 시작 AP 29.9°C는 개발 범위 32.5–34.0°C 밖이므로 예측곡선은 **외삽 진단**이다. strict 지원·정확도 PASS·정책 우열로 사용하지 않는다. 원본 세션·동결 파일은 저장소에 포함되지 않는다.

공유 CSV만으로 그림 재생성:

```powershell
python -B tools/d1_arrival_recorded_replay_figures.py --bundle docs/results/energy_ap_recorded_b2_01/diag_v6 --output '<새 빈 그림 경로>'
```
