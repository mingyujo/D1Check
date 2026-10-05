
## gpu-d100-r001 · run 1f953a1e-d0e7-46a5-beae-a13fb4c33d1a · GPU
종료: runner duration_complete · run_summary {'slot_id': 'gpu-d100-r001', 'slot_status': 'completed', 'validation_status': 'valid', 'termination_reason': 'duration_complete', 'completed_inference_count': '98341', 'actual_load_duration_s': '600.006708242', 'achieved_duty_cycle_percent': '100'}
보존 검사 전체: OK
  1_load_duty: OK {"load_s": 600.006752226, "runner_achieved_duty": 100, "computed_active_pct": 99.96260779446771, "notes": []}
  2_count: OK {"jsonl": 98341, "run_summary": 98341, "fs_span": 98341, "fs_completed": 98341, "merged": 98341, "merged_note": null, "notes": []}
  3_telemetry: OK {"detail": {"d1check": {"n": 1476, "median_interval_s": 0.999995468, "nonmonotonic": 0, "gaps_gt3x": 0, "gap_at_load_s": [], "gap_len_s": []}, "thermalservice": {"n": 1460, "median_interval_s": 1.015, "nonmonotonic": 0, "gaps_gt3x": 0, "gap_at_load_s": [], "gap_len_s": []}}, "notes": []}
  4_resource: OK {"pid": "28225", "notes": [], "counts": {"xnn": 0, "gpu": 1, "gpu_kernels": 1, "dispatch": 0, "enn": 0, "dispatch_fail": 0}}
  5_power: OK {"samples": 1476, "plugged_nonzero": 0}
부하 600.007 s · 추론 98341 · ref(0~30 s) 3.6533 ms
진입(원 규칙 +10%·30 s): 60 s  (끝 경계 후보 —) · 처음 +10 % 넘은 구간 60 s
보조 전력 −15% 진입(기록만): 90 s · P0 6.574 W
진입 시 온도: {'t': 59.725025025, 'SKIN': 36.7, 'AP': 41.9, 'PA': 42.4, 'BAT': 33.6} · load_start {'t': 0.030025025, 'SKIN': 31.1, 'AP': 30.2, 'PA': 29.7, 'BAT': 29.3} (밴드 안) · 끝 {'t': 599.530025025, 'SKIN': 38.2, 'AP': 40.4, 'PA': 40.2, 'BAT': 36.9}
status: {'d1check': {'max': 0, 'changes': []}, 'thermalservice': {'max': 0, 'changes': []}}
headroom: {'grid': [(0, 0.5366667, 0.5268755), (60, 0.71999997, 0.8452254), (120, 0.7566667, 0.7762709), (180, 0.76666665, 0.78037125), (240, 0.77666664, 0.7893065), (300, 0.78000003, 0.7810632), (360, 0.77666664, 0.7750694), (420, 0.77666664, 0.77883947), (480, 0.78333336, 0.78085214), (540, 0.77666664, 0.76673675), (600, 0.7733334, 0.76376253)], 'now_min': 0.5366667, 'now_max': 0.79, 'h60_min': 0.5268755, 'h60_max': 0.935245}
끝 60 s: 지연 7.6132 ms (×2.084) · 전력 2.587 W (×0.394) · SKIN 기울기 -0.092 ℃/min · 전력 기울기 -0.552 W/min
| t (s) | 지연 중앙 ms | 전력 W | n | SKIN | AP | PA | BAT |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-60 | 3.667 | 6.43 | 16216 | 36.7 | 41.9 | 42.4 | 33.6 |
| 60-120 | 4.333 | 5.24 | 12661 | 37.7 | 41.7 | 41.6 | 35.2 |
| 120-180 | 5.614 | 3.92 | 10596 | 38.0 | 41.7 | 41.4 | 35.9 |
| 180-240 | 5.958 | 3.45 | 9831 | 38.4 | 41.3 | 41.2 | 36.4 |
| 240-300 | 6.440 | 3.19 | 9031 | 38.4 | 41.0 | 41.0 | 36.6 |
| 300-360 | 6.836 | 2.82 | 8517 | 38.3 | 40.8 | 40.7 | 36.7 |
| 360-420 | 7.021 | 2.67 | 8270 | 38.3 | 40.6 | 40.4 | 36.7 |
| 420-480 | 7.156 | 3.02 | 7956 | 38.5 | 40.6 | 40.6 | 37.0 |
| 480-540 | 7.555 | 2.37 | 7671 | 38.3 | 40.7 | 40.4 | 36.9 |
| 540-600 | 7.613 | 2.59 | 7592 | 38.2 | 40.4 | 40.2 | 36.9 |

## gpu-d100-r002 · run 7f394fda-9e80-4dce-92fd-1d8c9c98d2c0 · GPU
종료: runner duration_complete · run_summary {'slot_id': 'gpu-d100-r002', 'slot_status': 'completed', 'validation_status': 'valid', 'termination_reason': 'duration_complete', 'completed_inference_count': '98110', 'actual_load_duration_s': '600.003784218', 'achieved_duty_cycle_percent': '100'}
보존 검사 전체: OK
  1_load_duty: OK {"load_s": 600.003813633, "runner_achieved_duty": 100, "computed_active_pct": 99.96784515754459, "notes": []}
  2_count: OK {"jsonl": 98110, "run_summary": 98110, "fs_span": 98110, "fs_completed": 98110, "merged": 98110, "merged_note": null, "notes": []}
  3_telemetry: OK {"detail": {"d1check": {"n": 1446, "median_interval_s": 0.999999258, "nonmonotonic": 0, "gaps_gt3x": 0, "gap_at_load_s": [], "gap_len_s": []}, "thermalservice": {"n": 1431, "median_interval_s": 1.015, "nonmonotonic": 0, "gaps_gt3x": 0, "gap_at_load_s": [], "gap_len_s": []}}, "notes": []}
  4_resource: OK {"pid": "22229", "notes": [], "counts": {"xnn": 0, "gpu": 1, "gpu_kernels": 1, "dispatch": 0, "enn": 0, "dispatch_fail": 0}}
  5_power: OK {"samples": 1446, "plugged_nonzero": 0}
부하 600.004 s · 추론 98110 · ref(0~30 s) 3.6551 ms
진입(원 규칙 +10%·30 s): 60 s  (끝 경계 후보 —) · 처음 +10 % 넘은 구간 60 s
보조 전력 −15% 진입(기록만): 60 s · P0 6.817 W
진입 시 온도: {'t': 60.380099713, 'SKIN': 37.1, 'AP': 42.0, 'PA': 42.5, 'BAT': 34.0} · load_start {'t': -0.229900287, 'SKIN': 31.6, 'AP': 30.9, 'PA': 30.2, 'BAT': 29.9} (밴드 안) · 끝 {'t': 599.225099713, 'SKIN': 38.5, 'AP': 40.7, 'PA': 40.6, 'BAT': 37.1}
status: {'d1check': {'max': 0, 'changes': []}, 'thermalservice': {'max': 0, 'changes': []}}
headroom: {'grid': [(0, 0.55333334, 0.54495716), (60, 0.73333335, 0.8548125), (120, 0.7633334, 0.78350246), (180, 0.7699999, 0.77673733), (240, 0.77666664, 0.77986604), (300, 0.77666664, 0.78195155), (360, 0.77666664, 0.7729436), (420, 0.77666664, 0.7738214), (480, 0.77666664, 0.77170247), (540, 0.78333336, 0.8028311), (600, 0.78333336, 0.7851054)], 'now_min': 0.55333334, 'now_max': 0.7933333, 'h60_min': 0.54495716, 'h60_max': 0.9532787}
끝 60 s: 지연 7.2063 ms (×1.972) · 전력 2.815 W (×0.413) · SKIN 기울기 -0.208 ℃/min · 전력 기울기 -0.394 W/min
| t (s) | 지연 중앙 ms | 전력 W | n | SKIN | AP | PA | BAT |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-60 | 3.681 | 6.59 | 16115 | 37.1 | 42.0 | 42.5 | 34.0 |
| 60-120 | 4.575 | 4.71 | 12279 | 38.0 | 42.0 | 42.3 | 35.5 |
| 120-180 | 5.616 | 3.73 | 10457 | 38.1 | 41.5 | 41.3 | 36.0 |
| 180-240 | 6.006 | 3.45 | 9654 | 38.4 | 41.2 | 41.1 | 36.4 |
| 240-300 | 6.398 | 3.02 | 9103 | 38.4 | 41.1 | 40.8 | 36.7 |
| 300-360 | 6.788 | 2.85 | 8578 | 38.3 | 40.7 | 40.5 | 36.8 |
| 360-420 | 7.392 | 2.67 | 7867 | 38.2 | 40.3 | 40.2 | 36.8 |
| 420-480 | 7.394 | 2.53 | 7861 | 38.3 | 40.6 | 40.5 | 36.8 |
| 480-540 | 7.022 | 2.85 | 8182 | 38.5 | 42.1 | 41.7 | 36.9 |
| 540-600 | 7.206 | 2.82 | 8014 | 38.5 | 40.7 | 40.6 | 37.1 |

(JSON: C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_0928\ref_C1probe.json)
